"""Joined convergence coverage for the runtime-readiness replication contract."""

from __future__ import annotations

import importlib.util
import json
import random
import sys
import types
from pathlib import Path

import pytest

from ipfs_kit_py.arc_cache import CacheBinding, GenerationBoundARC
from ipfs_kit_py.backends.provider_adapters import (
    ProviderAdapterCatalog,
    ProviderAvailability,
    UnsupportedProviderError,
)
from ipfs_kit_py.cache.arc.contracts import ARCConfig
from ipfs_kit_py.core.buckets.contracts import (
    BackendCapability as BucketBackendCapability,
    BucketIdentity,
    BucketManifest,
    BucketPolicy as CatalogPolicy,
    BucketReplica,
    BucketReplicaRole,
)
from ipfs_kit_py.core.buckets.service import (
    BucketService,
    CompensationRequiredError,
    InMemoryBucketBackend,
    ObjectNotFoundError,
)
from ipfs_kit_py.core.operation_contracts import ErrorCode, OperationState
from ipfs_kit_py.core.replication.contracts import (
    BackendCapability,
    BackendInventory,
    ReplicaPolicy,
)
from ipfs_kit_py.core.replication.integrity import IntegrityVerifier, ReplicaContent
from ipfs_kit_py.core.replication.reconciler import ReconciliationOutcome, ReplicaReconciler
from ipfs_kit_py.core.wal.coordinator import WALTransactionCoordinator, WALTransactionCrash


CHAOS_SEED_COUNT = 64
COMMITTED_VERSION = "version-2"
COMMITTED_PAYLOAD = b"committed-v2"


def _load_graphrag_modules() -> dict[str, types.ModuleType]:
    """Load GraphRAG without importing optional package-level integrations."""

    root = Path(__file__).resolve().parents[3] / "ipfs_kit_py" / "graphrag"
    package_name = "ipfs_kit_py.graphrag_joined_convergence"
    package = types.ModuleType(package_name)
    package.__path__ = [str(root)]
    sys.modules[package_name] = package
    modules: dict[str, types.ModuleType] = {}
    for name in ("contracts", "storage", "projections", "service"):
        qualified_name = f"{package_name}.{name}"
        spec = importlib.util.spec_from_file_location(qualified_name, root / f"{name}.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[qualified_name] = module
        spec.loader.exec_module(module)
        modules[name] = module
    return modules


def _bucket_manifest(name: str) -> BucketManifest:
    return BucketManifest(
        identity_record=BucketIdentity("primary", name),
        policy=CatalogPolicy(f"{name}-policy", quota_bytes=4096, quota_objects=16, replica_count=2),
        backend_capability=BucketBackendCapability("primary", 4096, 16),
        replicas=(
            BucketReplica("primary", BucketReplicaRole.PRIMARY),
            BucketReplica("replica", BucketReplicaRole.REPLICA),
        ),
    )


def _cache_binding(content_id: str, version: str, generation: str) -> CacheBinding:
    return CacheBinding(
        content_id=content_id,
        version=version,
        namespace="joined-convergence",
        policy="public",
        serializer="bytes@1",
        generation=generation,
    )


def _cache_get(cache: GenerationBoundARC, binding: CacheBinding) -> bytes | None:
    return cache.get(binding, authorize=lambda _: True, consistent=lambda _: True)


def _graph_manifest(contracts: types.ModuleType):
    return contracts.GraphRAGIndexManifest(
        "joined-convergence-index",
        "index-1",
        "model-1",
        "tokenizer-1",
        3,
        contracts.GraphRAGMetric.COSINE,
        "source-1",
        "source-version-1",
    )


def _graph_content(contracts: types.ModuleType, document_id: str, version_id: str, payload: str, *, tombstone_of: str = ""):
    provenance = contracts.GraphRAGProvenance("source-1", "source-version-1", f"source-{document_id}")
    if tombstone_of:
        return contracts.GraphRAGContent(
            document_id,
            version_id,
            "",
            provenance,
            contracts.GraphRAGContentState.TOMBSTONED,
            tombstone_of,
        )
    return contracts.GraphRAGContent(document_id, version_id, payload, provenance)


class _ReplicaBackend:
    def __init__(self, backend_id: str, objects: dict[str, ReplicaContent] | None = None) -> None:
        self.backend_id = backend_id
        self.objects = dict(objects or {})
        self.writes: list[str] = []

    def read(self, content_ref: str) -> ReplicaContent | None:
        return self.objects.get(content_ref)

    def write(self, content_ref: str, content: ReplicaContent, *, idempotency_key: str) -> None:
        self.writes.append(idempotency_key)
        self.objects[content_ref] = content

    def delete(self, content_ref: str, *, idempotency_key: str) -> None:
        self.objects.pop(content_ref, None)


class _PlacementBackend(InMemoryBucketBackend):
    def __init__(self) -> None:
        super().__init__()
        self.fail_put = False
        self.fail_delete = False

    def put_object(self, manifest, key, data, metadata):  # type: ignore[no-untyped-def]
        if self.fail_put:
            self.calls.append(("put_object", f"{manifest.identity.catalog_key}/{key}"))
            return False
        return super().put_object(manifest, key, data, metadata)

    def delete_object(self, manifest, key, metadata):  # type: ignore[no-untyped-def]
        if self.fail_delete:
            self.calls.append(("delete_object", f"{manifest.identity.catalog_key}/{key}"))
            return False
        return super().delete_object(manifest, key, metadata)


def _recover_committed_wal(directory: Path, effect_id: str) -> tuple[set[str], int]:
    def crash_after_commit(boundary: str, _: str) -> None:
        if boundary == "after_commit":
            raise WALTransactionCrash(boundary)

    coordinator = WALTransactionCoordinator(directory, crash_injector=crash_after_commit)
    with pytest.raises(WALTransactionCrash):
        coordinator.execute(
            {"version": COMMITTED_VERSION},
            lambda: None,
            lambda: None,
            transaction_id=f"transaction-{effect_id}",
            effect_id=effect_id,
        )
    coordinator.close()

    delivered: set[str] = set()
    duplicate_effects = 0

    def replay(intent: dict[str, str], recovered_effect_id: str) -> None:
        nonlocal duplicate_effects
        assert intent["version"] == COMMITTED_VERSION
        if recovered_effect_id in delivered:
            duplicate_effects += 1
        delivered.add(recovered_effect_id)

    recovered = WALTransactionCoordinator(directory)
    assert recovered.recover(replay_effect=replay, rollback_effect=lambda *_: None) == {
        "replayed": 1,
        "rolled_back": 0,
    }
    assert recovered.recover(replay_effect=replay, rollback_effect=lambda *_: None) == {
        "replayed": 0,
        "rolled_back": 0,
    }
    recovered.close()
    return delivered, duplicate_effects


def _reconcile_replicas(content_ref: str) -> tuple[object, _ReplicaBackend, _ReplicaBackend]:
    authoritative = ReplicaContent(COMMITTED_PAYLOAD, COMMITTED_VERSION)
    primary = _ReplicaBackend("primary", {content_ref: authoritative})
    replica = _ReplicaBackend("replica", {content_ref: ReplicaContent(b"stale", "version-1")})
    policy = ReplicaPolicy("joined-policy", 1, 2, 2, 2)
    inventory = BackendInventory(
        "joined-snapshot",
        (
            BackendCapability("primary", "domain-primary", 4096),
            BackendCapability("replica", "domain-replica", 4096),
        ),
    )
    reconciler = ReplicaReconciler({"primary": primary, "replica": replica})
    receipt = reconciler.reconcile(
        content_ref=content_ref,
        content_size_bytes=len(COMMITTED_PAYLOAD),
        expected_digest=IntegrityVerifier().digest(COMMITTED_PAYLOAD),
        expected_version_id=COMMITTED_VERSION,
        policy=policy,
        inventory=inventory,
        source=authoritative,
    )
    assert receipt.outcome is ReconciliationOutcome.CONVERGED
    assert set(receipt.verified_backend_ids) == {"primary", "replica"}
    assert len(receipt.verified_backend_ids) == policy.desired_replicas
    second = reconciler.reconcile(
        content_ref=content_ref,
        content_size_bytes=len(COMMITTED_PAYLOAD),
        expected_digest=IntegrityVerifier().digest(COMMITTED_PAYLOAD),
        expected_version_id=COMMITTED_VERSION,
        policy=policy,
        inventory=inventory,
        source=authoritative,
    )
    assert second.outcome is ReconciliationOutcome.CONVERGED
    assert not second.actions
    return receipt, primary, replica


def _run_seeded_schedule(tmp_path: Path, seed: int, graph_modules: dict[str, types.ModuleType]) -> tuple[str, ...]:
    primary = InMemoryBucketBackend()
    replica = InMemoryBucketBackend()
    bucket_service = BucketService({"primary": primary, "replica": replica})
    bucket_name = f"joined-{seed}"
    manifest = _bucket_manifest(bucket_name)
    bucket_service.create_bucket(manifest, idempotency_key=f"create-{seed}")

    content_ref = f"cid:joined-{seed}"
    stale_binding = _cache_binding(content_ref, "version-1", "generation-1")
    committed_binding = _cache_binding(content_ref, COMMITTED_VERSION, "generation-2")
    cache = GenerationBoundARC(ARCConfig(capacity_bytes=4096, max_live_entries=8))
    assert cache.put(stale_binding, b"stale")
    graph_service = graph_modules["service"].GraphRAGService(
        tmp_path / f"graph-{seed}", _graph_manifest(graph_modules["contracts"])
    )
    state: dict[str, object] = {}
    trace: list[str] = []

    def run(action: str) -> None:
        if action == "wal":
            state["effects"], state["duplicates"] = _recover_committed_wal(tmp_path / f"wal-{seed}", f"effect-{seed}")
        elif action == "bucket":
            state["metadata"] = bucket_service.put_object(
                manifest.identity.catalog_key,
                "object",
                COMMITTED_PAYLOAD,
                idempotency_key=f"put-{seed}",
            )
        elif action == "replica":
            state["receipt"], state["primary_replica"], state["secondary_replica"] = _reconcile_replicas(content_ref)
        elif action == "cache":
            assert cache.invalidate(stale_binding) == 1
            assert cache.put(committed_binding, COMMITTED_PAYLOAD)
        elif action == "index":
            document_id = f"document-{seed}"
            graph_service.apply(_graph_content(graph_modules["contracts"], document_id, "version-1", "stale"))
            graph_service.apply(_graph_content(graph_modules["contracts"], document_id, COMMITTED_VERSION, "committed"))
            state["document_id"] = document_id
        else:  # pragma: no cover - protects future additions to the schedule.
            raise AssertionError(f"unknown convergence action: {action}")

    dependencies = {"wal": set(), "bucket": {"wal"}, "replica": {"bucket"}, "cache": {"bucket"}, "index": {"bucket"}}
    remaining = list(dependencies)
    random.Random(seed).shuffle(remaining)
    completed: set[str] = set()
    while remaining:
        deferred: list[str] = []
        progressed = False
        for action in remaining:
            if not dependencies[action] <= completed:
                trace.append(f"defer:{action}")
                deferred.append(action)
                continue
            trace.append(action)
            run(action)
            completed.add(action)
            progressed = True
        assert progressed, f"chaos schedule made no progress: {remaining}"
        remaining = deferred

    assert state["effects"] == {f"effect-{seed}"}
    assert state["duplicates"] == 0
    assert bucket_service.get_object(manifest.identity.catalog_key, "object").data == COMMITTED_PAYLOAD
    assert _cache_get(cache, stale_binding) is None
    assert _cache_get(cache, committed_binding) == COMMITTED_PAYLOAD
    assert graph_service.current_content(state["document_id"]).version_id == COMMITTED_VERSION
    receipt = state["receipt"]
    assert len(receipt.verified_backend_ids) == 2
    # The reconciler owns the opaque idempotency key, but a second pass must not
    # issue another placement after the verified receipt has converged.
    assert len(state["secondary_replica"].writes) == 1
    return tuple(trace)


def test_seeded_chaos_schedules_converge_bucket_wal_cache_index_and_replicas(tmp_path: Path) -> None:
    graph_modules = _load_graphrag_modules()
    traces = {_run_seeded_schedule(tmp_path, seed, graph_modules) for seed in range(CHAOS_SEED_COUNT)}
    assert len(traces) > 1


def test_tombstoned_content_cannot_resurrect_and_cache_drops_deleted_versions(tmp_path: Path) -> None:
    graph_modules = _load_graphrag_modules()
    contracts = graph_modules["contracts"]
    graph_service = graph_modules["service"].GraphRAGService(tmp_path / "graph", _graph_manifest(contracts))
    document_id = "deleted-document"
    graph_service.apply(_graph_content(contracts, document_id, "version-1", "old"))
    graph_service.apply(_graph_content(contracts, document_id, COMMITTED_VERSION, "committed"))
    graph_service.delete_content(
        _graph_content(contracts, document_id, "version-3", "", tombstone_of=COMMITTED_VERSION)
    )
    assert document_id not in {node.document_id for node in graph_service.clean_rebuild().projection.nodes}
    with pytest.raises(graph_modules["service"].GraphRAGVersionError):
        graph_service.apply(_graph_content(contracts, document_id, "version-4", "resurrected"))

    cache = GenerationBoundARC(ARCConfig(capacity_bytes=4096, max_live_entries=4))
    old_binding = _cache_binding("cid:deleted", COMMITTED_VERSION, "generation-2")
    assert cache.put(old_binding, COMMITTED_PAYLOAD)
    assert cache.invalidate(old_binding) == 1
    assert _cache_get(cache, old_binding) is None


def test_partial_bucket_placement_has_durable_compensation_receipt() -> None:
    primary = _PlacementBackend()
    replica = _PlacementBackend()
    bucket_service = BucketService({"primary": primary, "replica": replica})
    manifest = _bucket_manifest("partial-placement")
    bucket_service.create_bucket(manifest, idempotency_key="create-partial")
    replica.fail_put = True
    primary.fail_delete = True

    with pytest.raises(CompensationRequiredError) as failure:
        bucket_service.put_object(
            manifest.identity.catalog_key,
            "object",
            COMMITTED_PAYLOAD,
            idempotency_key="partial-put",
        )
    pending = bucket_service.pending_compensations
    assert len(pending) == 1
    assert pending[0].operation_id == failure.value.operation_id
    assert pending[0].action == "rollback_put_object"
    with pytest.raises(ObjectNotFoundError):
        bucket_service.get_object(manifest.identity.catalog_key, "object")

    primary.fail_delete = False
    assert bucket_service.recover_pending(failure.value.operation_id) == (failure.value.operation_id,)
    assert not bucket_service.pending_compensations
    assert (manifest.identity.catalog_key, "object") not in primary.objects


def test_unsupported_provider_blocks_without_storage_fallback() -> None:
    adapter = ProviderAdapterCatalog().resolve("lotus")
    assert adapter.availability is ProviderAvailability.UNSUPPORTED
    assert not adapter.status().supports_storage
    with pytest.raises(UnsupportedProviderError) as failure:
        adapter.require_storage("put", idempotency_key="joined-convergence")
    assert failure.value.error.code is ErrorCode.UNSUPPORTED
    assert failure.value.error.state is OperationState.UNSUPPORTED


def test_replica_conformance_descriptor_declares_mandatory_joined_guarantees() -> None:
    descriptor_path = Path(__file__).resolve().parents[3] / "docs" / "runtime_readiness" / "replica_conformance.json"
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    assert descriptor["schema"] == "ipfs_kit_py/runtime-readiness/replica-conformance@1"
    assert descriptor["suite"] == "tests/runtime_readiness/replication/test_joined_convergence.py"
    assert descriptor["seeded_chaos"]["seed_count"] == CHAOS_SEED_COUNT
    assert descriptor["exclusion_policy"] == {"excluded_only_gate": False, "mandatory_in_default_ci": True}
    assert set(descriptor["invariants"]) == {
        "cache_and_index",
        "deletion",
        "partial_placement",
        "provider_capability",
        "replica_verification",
        "wal_idempotency",
    }
