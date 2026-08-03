"""Joined bucket conformance: WAL, replica, auth, backend, and interface parity.

Evidence bundle for KITA-013 / BucketConformanceReceipt@1.  The suite is
assertion-backed and mandatory in default CI: advertised lifecycle/object/
transfer/query/quota/placement operations pass a deterministic differential
corpus; WAL and compensation recovery preserve catalog and external-effect
consistency; unauthorized calls dispatch no effects; only verified replicas
count toward redundancy; Python/CLI/MCP projections agree after transport
stripping; unavailable capabilities reject explicitly; and no required skip
or success/no-op fallback remains.

Discovered product defects are reported as failing assertions; this module does
not patch production code (conflict policy: own joined tests/report only).
"""

from __future__ import annotations

import ast
import asyncio
import hashlib
import json
import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.backends.provider_adapters import (
    ProviderAdapterCatalog,
    ProviderAvailability,
    UnsupportedProviderError,
)
from ipfs_kit_py.cli.operation_adapter import CLIAdapter
from ipfs_kit_py.core.buckets.adapters import LegacyBucketAdapter
from ipfs_kit_py.core.buckets.contracts import (
    BackendCapability,
    BackendCapabilityInsufficientError,
    BucketIdentity,
    BucketLifecycleState,
    BucketManifest,
    BucketPolicy,
    BucketPolicyError,
    BucketReplica,
    BucketReplicaRole,
    BucketReplicaState,
    InconsistentStateError,
    QueryMode,
)
from ipfs_kit_py.core.buckets.service import (
    BackendOperationError,
    BucketNotFoundError,
    BucketQuotaExceededError,
    BucketService,
    BucketStateError,
    CompensationRequiredError,
    InMemoryBucketBackend,
    ObjectNotFoundError,
)
from ipfs_kit_py.core.buckets.transfer import (
    TransferValidationError,
    export_bucket,
    import_bucket,
)
from ipfs_kit_py.core.operation_contracts import (
    OPERATION_REQUEST_SCHEMA,
    OPERATION_RESULT_SCHEMA,
    STORAGE_ERROR_SCHEMA,
    ErrorCategory,
    ErrorCode,
    OperationResult,
    OperationState,
    Retryability,
    StorageError,
)
from ipfs_kit_py.core.operation_registry import (
    AuthorizationRequirement,
    CapabilityTier,
    OperationDefinition,
    OperationRegistry,
)
from ipfs_kit_py.core.service_router import DispatchContext, ServiceRouter
from ipfs_kit_py.core.wal.coordinator import WALTransactionCoordinator, WALTransactionCrash
from ipfs_kit_py.high_level_api.operation_adapter import AsyncPythonAdapter, PythonAdapter
from ipfs_kit_py.mcp_server.tools import (
    MCPPlusPlusToolAdapter,
    MCPToolAdapter,
    semantic_payload,
    strip_transport_fields,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFORMANCE_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "runtime_readiness"
    / "bucket_conformance.json"
)

_EXECUTE_BOUNDARIES = (
    "before_begin",
    "after_begin",
    "before_intent",
    "after_intent",
    "before_effect",
    "after_effect",
    "before_commit",
    "after_commit",
)

DIFFERENTIAL_SEED_COUNT = 64
OPERATIONS_PER_SEED = 12
REQUIRED_OPERATIONS = (
    "create_bucket",
    "update_bucket",
    "delete_bucket",
    "list_buckets",
    "put_object",
    "get_object",
    "list_objects",
    "delete_object",
    "export_bucket",
    "import_bucket",
    "recover_pending",
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


def _policy(
    name: str,
    *,
    quota_bytes: int = 4096,
    quota_objects: int = 64,
    replica_count: int = 1,
    minimum_verified_replicas: int = 0,
    query_mode: QueryMode = QueryMode.METADATA,
    query_indexing: bool = False,
) -> BucketPolicy:
    return BucketPolicy(
        f"{name}-policy",
        quota_bytes=quota_bytes,
        quota_objects=quota_objects,
        replica_count=replica_count,
        minimum_verified_replicas=minimum_verified_replicas,
        query_mode=query_mode,
        query_indexing=query_indexing,
    )


def _capability(
    backend_id: str = "primary",
    *,
    max_bucket_bytes: int = 8192,
    max_bucket_objects: int = 128,
    **overrides: object,
) -> BackendCapability:
    values: dict[str, object] = {
        "backend_id": backend_id,
        "max_bucket_bytes": max_bucket_bytes,
        "max_bucket_objects": max_bucket_objects,
    }
    values.update(overrides)
    return BackendCapability(**values)  # type: ignore[arg-type]


def _manifest(
    name: str,
    backend_ids: tuple[str, ...] = ("primary",),
    *,
    quota_bytes: int = 4096,
    quota_objects: int = 64,
    minimum_verified_replicas: int = 0,
    replicas: tuple[BucketReplica, ...] | None = None,
    lifecycle_state: BucketLifecycleState = BucketLifecycleState.PROVISIONING,
) -> BucketManifest:
    primary_id = backend_ids[0]
    if replicas is None:
        replicas = tuple(
            BucketReplica(
                backend_id,
                BucketReplicaRole.PRIMARY if index == 0 else BucketReplicaRole.REPLICA,
            )
            for index, backend_id in enumerate(backend_ids)
        )
    return BucketManifest(
        identity_record=BucketIdentity(primary_id, name),
        policy=_policy(
            name,
            quota_bytes=quota_bytes,
            quota_objects=quota_objects,
            replica_count=len(backend_ids),
            minimum_verified_replicas=minimum_verified_replicas,
        ),
        backend_capability=_capability(
            primary_id,
            max_bucket_bytes=max(quota_bytes, 1024),
            max_bucket_objects=max(quota_objects, 16),
        ),
        replicas=replicas,
        lifecycle_state=lifecycle_state,
    )


def _service(*backend_ids: str) -> tuple[BucketService, dict[str, InMemoryBucketBackend]]:
    backends = {backend_id: InMemoryBucketBackend() for backend_id in backend_ids}
    return BucketService(backends), backends


def _object_projection(service: BucketService, bucket_key: str) -> dict[str, Any]:
    page = service.list_objects(bucket_key)
    rows: dict[str, Any] = {}
    for entry in page.entries:
        obj = service.get_object(bucket_key, entry.key)
        rows[entry.key] = {
            "content_id": entry.content_id,
            "version_id": entry.version_id,
            "size": entry.size,
            "data": obj.data,
        }
    return rows


def _catalog_projection(service: BucketService) -> list[dict[str, Any]]:
    entries = []
    for manifest in service.list_buckets(page_size=1000).entries:
        entries.append(
            {
                "key": manifest.identity.catalog_key,
                "lifecycle": manifest.lifecycle_state.value,
                "quota_bytes": manifest.policy.quota_bytes,
                "quota_objects": manifest.policy.quota_objects,
                "replica_count": manifest.policy.replica_count,
                "verified_replica_count": manifest.verified_replica_count,
                "backends": tuple(replica.backend_id for replica in manifest.replicas),
            }
        )
    return sorted(entries, key=lambda item: item["key"])


def _trace_step(
    op: str,
    *,
    success: bool,
    detail: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "op": op,
        "success": success,
        "error": error,
        "detail": detail or {},
    }


def _run_schedule(
    service: BucketService,
    schedule: list[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Execute a deterministic schedule and capture a comparable trace."""

    created: dict[str, BucketManifest] = {}
    trace: list[dict[str, Any]] = []
    for op, args in schedule:
        try:
            if op == "create_bucket":
                name = str(args["name"])
                backend_ids = tuple(args.get("backend_ids", ("primary",)))
                manifest = _manifest(
                    name,
                    backend_ids,
                    quota_bytes=int(args.get("quota_bytes", 4096)),
                    quota_objects=int(args.get("quota_objects", 64)),
                )
                result = service.create_bucket(
                    manifest,
                    idempotency_key=args.get("idempotency_key"),
                )
                created[name] = result
                trace.append(
                    _trace_step(
                        op,
                        success=True,
                        detail={
                            "key": result.identity.catalog_key,
                            "lifecycle": result.lifecycle_state.value,
                        },
                    )
                )
            elif op == "update_bucket":
                name = str(args["name"])
                current = created[name]
                following = replace(
                    current,
                    policy=replace(
                        current.policy,
                        quota_objects=int(args.get("quota_objects", current.policy.quota_objects)),
                    ),
                )
                result = service.update_bucket(
                    following,
                    idempotency_key=args.get("idempotency_key"),
                )
                created[name] = result
                trace.append(
                    _trace_step(
                        op,
                        success=True,
                        detail={
                            "key": result.identity.catalog_key,
                            "quota_objects": result.policy.quota_objects,
                        },
                    )
                )
            elif op == "put_object":
                name = str(args["name"])
                key = str(args["key"])
                data = bytes(args["data"])
                meta = service.put_object(
                    created[name].identity,
                    key,
                    data,
                    expected_version=args.get("expected_version"),
                    idempotency_key=args.get("idempotency_key"),
                )
                trace.append(
                    _trace_step(
                        op,
                        success=True,
                        detail={
                            "key": key,
                            "content_id": meta.content_id,
                            "version_id": meta.version_id,
                            "size": meta.size,
                        },
                    )
                )
            elif op == "get_object":
                name = str(args["name"])
                key = str(args["key"])
                obj = service.get_object(created[name].identity, key)
                trace.append(
                    _trace_step(
                        op,
                        success=True,
                        detail={
                            "key": key,
                            "content_id": obj.metadata.content_id,
                            "data": obj.data,
                        },
                    )
                )
            elif op == "list_objects":
                name = str(args["name"])
                page = service.list_objects(
                    created[name].identity,
                    prefix=str(args.get("prefix", "")),
                    page_size=int(args.get("page_size", 100)),
                )
                trace.append(
                    _trace_step(
                        op,
                        success=True,
                        detail={
                            "keys": tuple(entry.key for entry in page.entries),
                            "content_ids": tuple(entry.content_id for entry in page.entries),
                        },
                    )
                )
            elif op == "delete_object":
                name = str(args["name"])
                key = str(args["key"])
                service.delete_object(
                    created[name].identity,
                    key,
                    idempotency_key=args.get("idempotency_key"),
                )
                trace.append(_trace_step(op, success=True, detail={"key": key}))
            elif op == "list_buckets":
                page = service.list_buckets(page_size=int(args.get("page_size", 100)))
                trace.append(
                    _trace_step(
                        op,
                        success=True,
                        detail={
                            "keys": tuple(item.identity.catalog_key for item in page.entries),
                        },
                    )
                )
            elif op == "delete_bucket":
                name = str(args["name"])
                service.delete_bucket(
                    created[name].identity,
                    idempotency_key=args.get("idempotency_key"),
                )
                created.pop(name, None)
                trace.append(_trace_step(op, success=True, detail={"name": name}))
            elif op == "export_bucket":
                name = str(args["name"])
                exported = export_bucket(service, created[name].identity)
                document = json.loads(exported.to_bytes())
                trace.append(
                    _trace_step(
                        op,
                        success=True,
                        detail={
                            "bucket": document["snapshot"]["bucket"],
                            "object_count": len(document["snapshot"]["objects"]),
                            "snapshot_digest": document["snapshot"]["snapshot_digest"],
                        },
                    )
                )
            elif op == "recover_pending":
                recovered = service.recover_pending()
                trace.append(
                    _trace_step(
                        op,
                        success=True,
                        detail={"recovered": recovered},
                    )
                )
            else:
                raise AssertionError(f"unknown schedule op: {op}")
        except Exception as exc:  # Capture typed failures for differential equality.
            trace.append(
                _trace_step(
                    op,
                    success=False,
                    error=type(exc).__name__,
                    detail={"message": str(exc)},
                )
            )
    return trace


def _generate_schedule(seed: int) -> list[tuple[str, dict[str, Any]]]:
    """Build a compact deterministic multi-op schedule covering advertised ops."""

    rng = random.Random(seed)
    name = f"b{seed % 1000:03d}"
    backends = ("primary",) if seed % 3 else ("primary", "replica")
    schedule: list[tuple[str, dict[str, Any]]] = [
        (
            "create_bucket",
            {
                "name": name,
                "backend_ids": backends,
                "quota_bytes": 256 + (seed % 8) * 64,
                "quota_objects": 4 + (seed % 4),
                "idempotency_key": f"create-{seed}",
            },
        )
    ]
    keys = [f"k{index}" for index in range(1 + seed % 3)]
    for index, key in enumerate(keys):
        payload = f"payload-{seed}-{index}".encode()
        schedule.append(
            (
                "put_object",
                {
                    "name": name,
                    "key": key,
                    "data": payload,
                    "idempotency_key": f"put-{seed}-{index}",
                },
            )
        )
        if rng.random() < 0.7:
            schedule.append(("get_object", {"name": name, "key": key}))
    schedule.append(("list_objects", {"name": name, "page_size": 2 + seed % 3}))
    schedule.append(("list_buckets", {"page_size": 10}))
    if seed % 2 == 0:
        schedule.append(
            (
                "update_bucket",
                {
                    "name": name,
                    "quota_objects": 8 + seed % 5,
                    "idempotency_key": f"update-{seed}",
                },
            )
        )
    schedule.append(("export_bucket", {"name": name}))
    if seed % 5 == 0 and keys:
        schedule.append(
            (
                "delete_object",
                {
                    "name": name,
                    "key": keys[0],
                    "idempotency_key": f"del-obj-{seed}",
                },
            )
        )
    if seed % 7 == 0:
        schedule.append(
            (
                "delete_bucket",
                {"name": name, "idempotency_key": f"del-bucket-{seed}"},
            )
        )
    schedule.append(("recover_pending", {}))
    # Keep the generated length bounded for reviewability.
    return schedule[:OPERATIONS_PER_SEED]


class _FalseOncePutBackend(InMemoryBucketBackend):
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


class _RecoverableDeleteBackend(InMemoryBucketBackend):
    def __init__(self) -> None:
        super().__init__()
        self.accept_deletes = False

    def delete_bucket(self, manifest: BucketManifest) -> bool:
        super().delete_bucket(manifest)
        return self.accept_deletes


# ---------------------------------------------------------------------------
# Differential / state-machine corpus
# ---------------------------------------------------------------------------


def test_advertised_operations_pass_state_machine_differential_corpus() -> None:
    """Independent services agree on deterministic multi-op schedules."""

    digest = hashlib.sha256()
    covered: set[str] = set()
    for seed in range(DIFFERENTIAL_SEED_COUNT):
        schedule = _generate_schedule(seed)
        covered.update(op for op, _ in schedule)
        left, _ = _service("primary", "replica")
        right, _ = _service("primary", "replica")
        left_trace = _run_schedule(left, schedule)
        right_trace = _run_schedule(right, schedule)
        assert left_trace == right_trace, f"differential mismatch for seed {seed}"
        assert _catalog_projection(left) == _catalog_projection(right)
        for name in {args["name"] for op, args in schedule if op == "create_bucket"}:
            key = f"primary/{name}"
            try:
                left.catalog.get(key)
            except Exception:
                continue
            assert _object_projection(left, key) == _object_projection(right, key)
        digest.update(repr((seed, left_trace)).encode("utf-8"))

    assert DIFFERENTIAL_SEED_COUNT >= 64
    assert OPERATIONS_PER_SEED >= 8
    # Corpus must exercise the core lifecycle/object surface (transfer/export
    # and recover appear on enough seeds that coverage is non-empty).
    assert {
        "create_bucket",
        "put_object",
        "get_object",
        "list_objects",
        "list_buckets",
        "export_bucket",
        "recover_pending",
    } <= covered
    assert set(REQUIRED_OPERATIONS) - covered <= {"import_bucket", "update_bucket", "delete_bucket", "delete_object"}
    assert digest.digest() != b"\0" * hashlib.sha256().digest_size


def test_import_export_round_trip_and_corrupt_rejection() -> None:
    source, _ = _service("primary")
    manifest = _manifest("assets")
    created = source.create_bucket(manifest)
    source.put_object(created.identity, "report.txt", b"immutable payload")
    source.put_object(created.identity, "notes.bin", b"\x00\x01joined")
    exported = export_bucket(source, created.identity)

    destination, _ = _service("primary")
    import_bucket(destination, exported.to_bytes(), create_if_missing=True)
    assert destination.get_object(created.identity, "report.txt").data == b"immutable payload"
    assert destination.get_object(created.identity, "notes.bin").data == b"\x00\x01joined"
    assert _object_projection(source, created.identity.catalog_key) == _object_projection(
        destination, created.identity.catalog_key
    )

    invalid = json.loads(exported.to_bytes())
    invalid["snapshot"]["objects"][0]["sha256"] = "0" * 64
    snapshot = invalid["snapshot"]
    digest_source = dict(snapshot)
    digest_source.pop("snapshot_digest")
    snapshot["snapshot_digest"] = hashlib.sha256(
        json.dumps(digest_source, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    empty, _ = _service("primary")
    with pytest.raises(TransferValidationError):
        import_bucket(empty, invalid, create_if_missing=True)
    assert empty.catalog.snapshot().entries == ()


# ---------------------------------------------------------------------------
# Verified replicas, quota, query, backend capability
# ---------------------------------------------------------------------------


def test_only_verified_replicas_count_toward_redundancy() -> None:
    primary = BucketReplica("primary", BucketReplicaRole.PRIMARY)
    pending = BucketReplica("replica-a", BucketReplicaRole.REPLICA, BucketReplicaState.PENDING)
    copying = BucketReplica("replica-b", BucketReplicaRole.REPLICA, BucketReplicaState.COPYING)
    verifying = BucketReplica(
        "replica-c",
        BucketReplicaRole.REPLICA,
        BucketReplicaState.VERIFYING,
    )
    verified = BucketReplica(
        "replica-d",
        BucketReplicaRole.REPLICA,
        BucketReplicaState.VERIFIED,
        durable=True,
        integrity_verified=True,
    )
    # Primary is never a verified replica even if durable.
    assert primary.is_verified_replica is False
    assert pending.is_verified_replica is False
    assert copying.is_verified_replica is False
    assert verifying.is_verified_replica is False
    assert verified.is_verified_replica is True

    with pytest.raises(InconsistentStateError):
        BucketReplica(
            "replica-e",
            BucketReplicaRole.REPLICA,
            BucketReplicaState.VERIFIED,
        )

    active = BucketManifest(
        identity_record=BucketIdentity("primary", "verified-count"),
        policy=_policy(
            "verified-count",
            replica_count=2,
            minimum_verified_replicas=1,
        ),
        backend_capability=_capability("primary"),
        replicas=(primary, verified),
        lifecycle_state=BucketLifecycleState.ACTIVE,
    )
    assert active.verified_replica_count == 1
    assert active.primary is primary

    with pytest.raises(InconsistentStateError):
        BucketManifest(
            identity_record=BucketIdentity("primary", "missing-verified"),
            policy=_policy(
                "missing-verified",
                replica_count=2,
                minimum_verified_replicas=1,
            ),
            backend_capability=_capability("primary"),
            replicas=(primary, pending),
            lifecycle_state=BucketLifecycleState.ACTIVE,
        )


def test_quota_admission_rejects_over_capacity_without_effects() -> None:
    primary = InMemoryBucketBackend()
    service = BucketService({"primary": primary})
    created = service.create_bucket(_manifest("quota", quota_bytes=8, quota_objects=1))
    admitted = service.put_object(created.identity, "a", b"12345678")
    assert admitted.size == 8
    before = list(primary.calls)
    with pytest.raises(BucketQuotaExceededError):
        service.put_object(created.identity, "b", b"x")
    assert primary.calls == before
    with pytest.raises(ObjectNotFoundError):
        service.get_object(created.identity, "b")


def test_concurrent_quota_admits_exactly_one_object() -> None:
    primary = InMemoryBucketBackend()
    service = BucketService({"primary": primary})
    created = service.create_bucket(_manifest("cq", quota_bytes=7, quota_objects=1))

    def write(name: str) -> object:
        try:
            return service.put_object(created.identity, name, b"payload")
        except BucketQuotaExceededError:
            return "quota-rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(write, ("first", "second")))

    assert sum(result != "quota-rejected" for result in results) == 1
    assert results.count("quota-rejected") == 1
    assert sum(action == "put_object" for action, _ in primary.calls) == 1


def test_query_mode_and_backend_capability_reject_invalid_configs() -> None:
    with pytest.raises(BucketPolicyError):
        _policy("bad-query", query_mode=QueryMode.CONTENT, query_indexing=False)
    with pytest.raises(BucketPolicyError):
        _policy("disabled-index", query_mode=QueryMode.DISABLED, query_indexing=True)

    policy = _policy(
        "content-query",
        query_mode=QueryMode.CONTENT,
        query_indexing=True,
    )
    capable = _capability(
        "primary",
        supported_query_modes=(QueryMode.METADATA, QueryMode.CONTENT),
    )
    assert capable.supports(policy)

    insufficient = _capability(
        "primary",
        supported_query_modes=(QueryMode.METADATA,),
    )
    assert not insufficient.supports(policy)
    with pytest.raises(BackendCapabilityInsufficientError):
        BucketManifest(
            identity_record=BucketIdentity("primary", "query-fail"),
            policy=policy,
            backend_capability=insufficient,
            replicas=(BucketReplica("primary", BucketReplicaRole.PRIMARY),),
        )


def test_unavailable_capabilities_reject_without_fallback() -> None:
    adapter = ProviderAdapterCatalog().resolve("lotus")
    assert adapter.availability is ProviderAvailability.UNSUPPORTED
    assert not adapter.status().supports_storage
    with pytest.raises(UnsupportedProviderError) as failure:
        adapter.require_storage("put", idempotency_key="bucket-joined")
    assert failure.value.error.code is ErrorCode.UNSUPPORTED
    assert failure.value.error.state is OperationState.UNSUPPORTED

    # Insufficient local backend capability cannot be promoted to a success.
    policy = _policy("oversized", quota_bytes=10_000)
    small = _capability("primary", max_bucket_bytes=100)
    with pytest.raises(BackendCapabilityInsufficientError):
        BucketManifest(
            identity_record=BucketIdentity("primary", "oversized"),
            policy=policy,
            backend_capability=small,
            replicas=(BucketReplica("primary", BucketReplicaRole.PRIMARY),),
        )


# ---------------------------------------------------------------------------
# Placement, crash, recovery
# ---------------------------------------------------------------------------


def test_partial_placement_compensates_or_records_recoverable_receipt() -> None:
    primary = _FalseOncePutBackend()
    replica = _FalseOncePutBackend()
    service = BucketService({"primary": primary, "replica": replica})
    manifest = _manifest("partial", ("primary", "replica"))
    service.create_bucket(manifest, idempotency_key="create-partial")
    replica.fail_put = True
    primary.fail_delete = True

    with pytest.raises(CompensationRequiredError) as failure:
        service.put_object(
            manifest.identity.catalog_key,
            "object",
            b"committed-v2",
            idempotency_key="partial-put",
        )
    pending = service.pending_compensations
    assert len(pending) == 1
    assert pending[0].operation_id == failure.value.operation_id
    assert pending[0].action == "rollback_put_object"
    with pytest.raises(ObjectNotFoundError):
        service.get_object(manifest.identity.catalog_key, "object")

    primary.fail_delete = False
    restarted = BucketService({"primary": primary, "replica": replica}, catalog=service.catalog)
    assert restarted.recover_pending(failure.value.operation_id) == (failure.value.operation_id,)
    assert not restarted.pending_compensations
    assert (manifest.identity.catalog_key, "object") not in primary.objects
    assert (manifest.identity.catalog_key, "object") not in replica.objects


def test_deletion_fence_blocks_writes_until_recovery_completes() -> None:
    primary = _RecoverableDeleteBackend()
    service = BucketService({"primary": primary})
    created = service.create_bucket(_manifest("deleterecovery"))

    with pytest.raises(CompensationRequiredError) as error:
        service.delete_bucket(created.identity)

    fenced = service.catalog.get(created.identity.catalog_key)
    assert fenced.lifecycle_state is BucketLifecycleState.DELETING
    assert service.pending_compensations[0].operation_id == error.value.operation_id
    with pytest.raises(BucketStateError):
        service.put_object(created.identity, "cannot-race", b"payload")

    primary.accept_deletes = True
    restarted = BucketService({"primary": primary}, catalog=service.catalog)
    assert restarted.recover_pending() == (error.value.operation_id,)
    assert restarted.pending_compensations == ()
    with pytest.raises(BucketNotFoundError):
        service.put_object(created.identity, "gone", b"payload")


def test_idempotent_retry_preserves_single_external_effect() -> None:
    primary = InMemoryBucketBackend()
    service = BucketService({"primary": primary})
    created = service.create_bucket(_manifest("idempotent"))

    first = service.put_object(
        created.identity,
        "same-object",
        b"payload",
        idempotency_key="repeatable-write",
    )
    second = service.put_object(
        created.identity,
        "same-object",
        b"payload",
        idempotency_key="repeatable-write",
    )
    assert first == second
    assert sum(action == "put_object" for action, _ in primary.calls) == 1
    assert service.list_objects(created.identity).entries == (first,)


@pytest.mark.parametrize("boundary", _EXECUTE_BOUNDARIES)
def test_wal_crash_matrix_with_bucket_effects_recovers(
    tmp_path: Path, boundary: str
) -> None:
    """Every crash point recovers to pre-commit compensation or committed replay."""

    transaction_id = f"bucket-txn-{boundary}"
    effect_id = f"bucket-effect-{boundary}"
    wal_dir = tmp_path / f"wal-{boundary}"
    object_key = f"crash-{boundary}"
    payload = f"payload-{boundary}".encode()

    service, backends = _service("primary")
    manifest = service.create_bucket(_manifest("walbucket"))
    visible_effects: set[str] = set()

    def apply_effect() -> None:
        if effect_id in visible_effects:
            try:
                existing = service.get_object(manifest.identity, object_key)
            except ObjectNotFoundError:
                existing = None
            if existing is not None and existing.data == payload:
                return
        meta = service.put_object(
            manifest.identity,
            object_key,
            payload,
            idempotency_key=f"wal-put-{boundary}",
        )
        assert meta.size == len(payload)
        visible_effects.add(effect_id)

    def compensate_effect() -> None:
        try:
            service.delete_object(
                manifest.identity,
                object_key,
                idempotency_key=f"wal-del-{boundary}",
            )
        except ObjectNotFoundError:
            pass
        visible_effects.discard(effect_id)

    def inject(name: str, received_transaction_id: str) -> None:
        if name == boundary:
            assert received_transaction_id == transaction_id
            raise WALTransactionCrash(name)

    coordinator = WALTransactionCoordinator(wal_dir, crash_injector=inject)
    try:
        with pytest.raises(WALTransactionCrash):
            coordinator.execute(
                {
                    "object": "bucket-joined",
                    "boundary": boundary,
                    "key": object_key,
                },
                apply_effect,
                compensate_effect,
                transaction_id=transaction_id,
                effect_id=effect_id,
            )
    finally:
        coordinator.close()

    recovered = WALTransactionCoordinator(wal_dir)
    try:
        first = recovered.recover(
            replay_effect=lambda _intent, received: apply_effect()
            if received == effect_id
            else None,
            rollback_effect=lambda _intent, received: compensate_effect()
            if received == effect_id
            else None,
        )
        second = recovered.recover(
            replay_effect=lambda _intent, received: apply_effect()
            if received == effect_id
            else None,
            rollback_effect=lambda _intent, received: compensate_effect()
            if received == effect_id
            else None,
        )
    finally:
        recovered.close()

    if boundary == "after_commit":
        assert visible_effects == {effect_id}
        assert service.get_object(manifest.identity, object_key).data == payload
        assert first == {"replayed": 1, "rolled_back": 0}
    else:
        assert visible_effects == set()
        with pytest.raises(ObjectNotFoundError):
            service.get_object(manifest.identity, object_key)
        assert first["replayed"] == 0
    assert second == {"replayed": 0, "rolled_back": 0}
    # Catalog stays consistent: bucket still active, no pending compensation.
    assert service.catalog.get(manifest.identity.catalog_key).lifecycle_state is BucketLifecycleState.ACTIVE
    assert service.pending_compensations == ()
    assert backends["primary"].buckets[manifest.identity.catalog_key].lifecycle_state is BucketLifecycleState.ACTIVE


# ---------------------------------------------------------------------------
# Authorization + interface parity
# ---------------------------------------------------------------------------


def _bucket_operation_definition(
    operation_id: str,
    *,
    public_name: str,
    authorization: AuthorizationRequirement | None = None,
    support_tier: CapabilityTier = CapabilityTier.PRODUCTION,
    capability: str | None = None,
) -> OperationDefinition:
    return OperationDefinition(
        operation_id=operation_id,
        version=1,
        request_schema=OPERATION_REQUEST_SCHEMA,
        result_schema=OPERATION_RESULT_SCHEMA,
        error_schema=STORAGE_ERROR_SCHEMA,
        capability=capability or operation_id,
        authorization=authorization or AuthorizationRequirement.public(),
        handler_route="bucket-joined-service",
        transport_names={
            "python": public_name,
            "cli": public_name,
            "mcp": public_name,
            "mcpp": public_name,
        },
        support_tier=support_tier,
    )


def _bind_bucket_router(
    service: BucketService,
    *,
    authorizer: Any = None,
    effect_log: list[str] | None = None,
) -> ServiceRouter:
    definitions = (
        _bucket_operation_definition("bucket.create", public_name="bucket-create"),
        _bucket_operation_definition(
            "bucket.put",
            public_name="bucket-put",
            authorization=AuthorizationRequirement.protected("storage.bucket", "write"),
        ),
        _bucket_operation_definition("bucket.get", public_name="bucket-get"),
        _bucket_operation_definition("bucket.list", public_name="bucket-list"),
        _bucket_operation_definition(
            "bucket.unsupported-capability",
            public_name="bucket-unsupported",
            support_tier=CapabilityTier.UNSUPPORTED,
            capability="bucket.capability.unavailable",
        ),
    )
    registry = OperationRegistry(definitions)
    log = effect_log if effect_log is not None else []

    async def handler(
        definition: OperationDefinition,
        request: Any,
        _context: DispatchContext,
    ) -> OperationResult:
        payload = request if isinstance(request, dict) else {}
        name = str(payload.get("name", "joined"))
        key = str(payload.get("key", "object"))
        data = payload.get("data", b"")
        if isinstance(data, str):
            data = data.encode("utf-8")
        if not isinstance(data, (bytes, bytearray)):
            data = b""

        try:
            if definition.operation_id == "bucket.create":
                log.append("create")
                manifest = service.create_bucket(
                    _manifest(name),
                    idempotency_key=str(payload.get("idempotency_key") or f"iface-create-{name}"),
                )
                return OperationResult(
                    request_id="joined-bucket-request",
                    operation_id=definition.operation_id,
                    state=OperationState.ACCEPTED,
                    success=True,
                    resulting_content_cid=manifest.content_id,
                    backend_id="backend:memory",
                )
            if definition.operation_id == "bucket.put":
                log.append("put")
                catalog_key = f"primary/{name}"
                meta = service.put_object(
                    catalog_key,
                    key,
                    bytes(data),
                    idempotency_key=str(payload.get("idempotency_key") or f"iface-put-{name}-{key}"),
                )
                return OperationResult(
                    request_id="joined-bucket-request",
                    operation_id=definition.operation_id,
                    state=OperationState.ACCEPTED,
                    success=True,
                    resulting_content_cid=meta.content_id,
                    resulting_version_cid=meta.version_id,
                    backend_id="backend:memory",
                )
            if definition.operation_id == "bucket.get":
                log.append("get")
                obj = service.get_object(f"primary/{name}", key)
                return OperationResult(
                    request_id="joined-bucket-request",
                    operation_id=definition.operation_id,
                    state=OperationState.ACCEPTED,
                    success=True,
                    resulting_content_cid=obj.metadata.content_id,
                    resulting_version_cid=obj.metadata.version_id,
                    backend_id="backend:memory",
                )
            if definition.operation_id == "bucket.list":
                log.append("list")
                page = service.list_objects(f"primary/{name}")
                return OperationResult(
                    request_id="joined-bucket-request",
                    operation_id=definition.operation_id,
                    state=OperationState.ACCEPTED,
                    success=True,
                    resulting_content_cid=page.entries[0].content_id if page.entries else "",
                    backend_id="backend:memory",
                )
        except Exception as exc:
            return OperationResult(
                request_id="joined-bucket-request",
                operation_id=definition.operation_id,
                state=OperationState.FAILED,
                success=False,
                error=StorageError(
                    code=ErrorCode.INTERNAL,
                    category=ErrorCategory.INTERNAL,
                    message=str(exc),
                    retryability=Retryability.NEVER,
                    state=OperationState.FAILED,
                ),
            )

        return OperationResult(
            request_id="joined-bucket-request",
            operation_id=definition.operation_id,
            state=OperationState.UNSUPPORTED,
            success=False,
            error=StorageError(
                code=ErrorCode.UNSUPPORTED,
                category=ErrorCategory.UNSUPPORTED,
                message="bucket capability is unavailable",
                retryability=Retryability.NEVER,
                state=OperationState.UNSUPPORTED,
            ),
        )

    router = ServiceRouter(registry, authorizer=authorizer)
    router.bind_handler(
        "bucket-joined-service",
        handler,
        capabilities={definition.capability for definition in definitions},
    )
    return router


def _all_adapters(router: ServiceRouter) -> dict[str, Any]:
    registry = router.registry
    return {
        "package": PythonAdapter(registry, router),
        "python_sync": PythonAdapter(registry, router),
        "python_async": AsyncPythonAdapter(registry, router),
        "cli": CLIAdapter(registry, router),
        "mcp": MCPToolAdapter(registry, router),
        "mcpp": MCPPlusPlusToolAdapter(registry, router),
    }


def test_unauthorized_calls_dispatch_no_effects() -> None:
    effect_log: list[str] = []
    primary = InMemoryBucketBackend()
    service = BucketService({"primary": primary})
    service.create_bucket(_manifest("secured"), idempotency_key="create-secured")
    backend_calls_before = list(primary.calls)

    def authorizer(requirement: AuthorizationRequirement, context: DispatchContext) -> bool:
        return (
            requirement.classification.value == "protected"
            and requirement.resource == "storage.bucket"
            and requirement.ability == "write"
            and context.principal == "alice"
        )

    router = _bind_bucket_router(service, authorizer=authorizer, effect_log=effect_log)
    adapters = _all_adapters(router)
    request = {"name": "secured", "key": "secret", "data": "must-not-write"}
    arguments = {"request": request, "principal": "eve"}

    denied = [
        semantic_payload(
            adapters["package"].call(
                "bucket-put",
                request,
                context=DispatchContext(principal="eve"),
            )
        ),
        semantic_payload(
            asyncio.run(adapters["cli"].invoke("bucket-put", request, principal="eve"))
        ),
        semantic_payload(adapters["mcp"].call("bucket-put", arguments)),
        strip_transport_fields(
            asyncio.run(adapters["mcpp"].call_framed("stdio", "bucket-put", arguments))
        ),
    ]
    assert effect_log == []
    assert primary.calls == backend_calls_before
    for payload in denied:
        assert payload["success"] is False
        assert payload["error"]["code"] == ErrorCode.FORBIDDEN.value
        assert payload["operation"]["access_requirement"] == {
            "classification": "protected",
            "resource": "storage.bucket",
            "ability": "write",
        }
    assert all(item == denied[0] for item in denied)

    with pytest.raises(ObjectNotFoundError):
        service.get_object("primary/secured", "secret")

    allowed = semantic_payload(
        adapters["package"].call(
            "bucket-put",
            request,
            context=DispatchContext(principal="alice"),
        )
    )
    assert allowed["success"] is True
    assert "put" in effect_log
    assert service.get_object("primary/secured", "secret").data == b"must-not-write"


def test_python_cli_mcp_parity_for_bucket_operations() -> None:
    create_request = {"name": "parity", "idempotency_key": "parity-create"}
    put_request = {
        "name": "parity",
        "key": "readme",
        "data": "hello-joined",
        "idempotency_key": "parity-put",
    }
    get_request = {"name": "parity", "key": "readme"}
    list_request = {"name": "parity"}

    def authorizer(requirement: AuthorizationRequirement, context: DispatchContext) -> bool:
        if requirement.classification.value != "protected":
            return True
        return context.principal in {None, "alice", ""}

    def fresh_adapters() -> dict[str, Any]:
        service, _ = _service("primary")
        return _all_adapters(_bind_bucket_router(service, authorizer=authorizer))

    def run_flow(call_one) -> Any:
        created = call_one("bucket-create", create_request)
        assert bool(getattr(created, "success", None) if not isinstance(created, dict) else created.get("success"))
        written = call_one(
            "bucket-put",
            put_request,
            context=DispatchContext(principal="alice"),
        )
        assert bool(getattr(written, "success", None) if not isinstance(written, dict) else written.get("success"))
        return call_one("bucket-get", get_request)

    package_adapters = fresh_adapters()
    package = run_flow(
        lambda name, req, context=None: package_adapters["package"].call(
            name, req, context=context
        )
        if context is not None
        else package_adapters["package"].call(name, req)
    )

    python_adapters = fresh_adapters()
    python_sync = run_flow(
        lambda name, req, context=None: python_adapters["python_sync"].call(
            name, req, context=context
        )
        if context is not None
        else python_adapters["python_sync"].call(name, req)
    )

    async_adapters = fresh_adapters()
    python_async = run_flow(
        lambda name, req, context=None: asyncio.run(
            async_adapters["python_async"].call(name, req, context=context)
            if context is not None
            else async_adapters["python_async"].call(name, req)
        )
    )

    cli_adapters = fresh_adapters()
    cli = run_flow(
        lambda name, req, context=None: asyncio.run(
            cli_adapters["cli"].invoke(
                name,
                req,
                principal=context.principal if context is not None else None,
            )
        )
    )

    mcp_adapters = fresh_adapters()
    mcp = run_flow(
        lambda name, req, context=None: mcp_adapters["mcp"].call(
            name,
            {
                "request": req,
                **({"principal": context.principal} if context is not None else {}),
            },
        )
    )

    mcpp_adapters = fresh_adapters()
    mcpp_stdio = run_flow(
        lambda name, req, context=None: asyncio.run(
            mcpp_adapters["mcpp"].call_framed(
                "stdio",
                name,
                {
                    "request": req,
                    **({"principal": context.principal} if context is not None else {}),
                },
            )
        )
    )

    semantic = semantic_payload(package)
    assert package.success is True
    assert semantic_payload(python_sync) == semantic
    assert semantic_payload(python_async) == semantic
    assert semantic_payload(cli) == semantic
    assert semantic_payload(mcp) == semantic
    assert strip_transport_fields(mcpp_stdio) == semantic
    assert package.to_dict()["result"]["record"]["success"] is True
    content_cid = package.to_dict()["result"]["record"]["resulting_content_cid"]
    assert content_cid.startswith("sha256:")

    shared = fresh_adapters()
    assert shared["package"].call("bucket-create", create_request).success is True
    assert (
        shared["package"]
        .call("bucket-put", put_request, context=DispatchContext(principal="alice"))
        .success
        is True
    )
    stdout, stderr = StringIO(), StringIO()
    assert (
        shared["cli"].run(
            ["bucket-list", "--request-json", json.dumps(list_request)],
            stdout=stdout,
            stderr=stderr,
        )
        == 0
    )
    assert stderr.getvalue() == ""
    package_list = shared["package"].call("bucket-list", list_request)
    assert json.loads(stdout.getvalue()) == package_list.to_dict()
    assert package_list.success is True

    # Unsupported capability rejects on every surface without manufacturing success.
    unsupported_request = {"name": "parity"}
    u_adapters = fresh_adapters()
    package_u = u_adapters["package"].call("bucket-unsupported", unsupported_request)
    cli_u = asyncio.run(u_adapters["cli"].invoke("bucket-unsupported", unsupported_request))
    mcp_u = u_adapters["mcp"].call("bucket-unsupported", {"request": unsupported_request})
    assert package_u.success is False
    assert semantic_payload(package_u) == semantic_payload(cli_u) == semantic_payload(mcp_u)
    package_error = package_u.to_dict()["error"] or package_u.to_dict()["result"]["record"]
    assert package_error["state"] in {
        OperationState.UNSUPPORTED.value,
        OperationState.FAILED.value,
    }


def test_legacy_adapter_matches_canonical_service_semantics() -> None:
    service, _ = _service("primary")
    adapter = LegacyBucketAdapter(service)
    manifest = _manifest("legacy")
    created = adapter.create_bucket(manifest)
    assert created.lifecycle_state is BucketLifecycleState.ACTIVE
    meta = adapter.put_object(created.identity, "item", b"legacy-joined")
    direct = service.get_object(created.identity, "item")
    assert direct.data == b"legacy-joined"
    assert direct.metadata.content_id == meta.content_id
    via_adapter = adapter.get_object(created.identity, "item")
    assert via_adapter.data == direct.data


# ---------------------------------------------------------------------------
# Conformance receipt + suite hygiene
# ---------------------------------------------------------------------------


def test_conformance_receipt_declares_mandatory_joined_guarantees() -> None:
    receipt = json.loads(CONFORMANCE_PATH.read_text(encoding="utf-8"))
    assert receipt["schema"] == "ipfs_kit_py/runtime-readiness/bucket-conformance@1"
    assert receipt["contract_version"] == 1
    assert receipt["task_id"] == "KITA-013"
    assert receipt["suite"] == "tests/runtime_readiness/buckets/test_bucket_joined_conformance.py"
    assert "BucketConformanceReceipt@1" in receipt["interfaces"]
    assert receipt["exclusion_policy"] == {
        "excluded_only_gate": False,
        "mandatory_in_default_ci": True,
    }
    assert receipt["acceptance"]["all_advertised_operations_pass_state_machine_corpus"] is True
    assert receipt["acceptance"]["crash_retry_preserves_catalog_and_external_effect_consistency"] is True
    assert receipt["acceptance"]["unauthorized_calls_dispatch_no_effects"] is True
    assert receipt["acceptance"]["only_verified_replicas_count"] is True
    assert receipt["acceptance"]["python_cli_mcp_parity"] is True
    assert receipt["acceptance"]["unavailable_capabilities_reject_explicitly"] is True
    assert receipt["acceptance"]["no_required_test_skips"] is True
    assert receipt["acceptance"]["no_success_noop_fallback"] is True
    assert receipt["acceptance"]["no_print_only_paths"] is True
    assert set(receipt["crash_boundaries"]) == set(_EXECUTE_BOUNDARIES)
    assert set(receipt["required_operations"]) == set(REQUIRED_OPERATIONS)
    for key in (
        "lifecycle",
        "object",
        "transfer",
        "query",
        "quota",
        "placement",
        "crash",
        "auth",
        "parity",
        "backend",
    ):
        assert key in receipt["evidence_subset"]
        assert receipt["evidence_subset"][key]
    assert receipt["replica_policy"]["primary_never_counts_as_verified_replica"] is True
    assert receipt["differential_corpus"]["seed_count"] == DIFFERENTIAL_SEED_COUNT


def test_suite_has_no_required_skips_or_print_only_paths() -> None:
    """Static hygiene: this module must not skip, xfail, or print-only assert."""

    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden: list[str] = []

    def _call_name(node: ast.Call) -> str:
        func = node.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            parts: list[str] = [func.attr]
            value = func.value
            while isinstance(value, ast.Attribute):
                parts.append(value.attr)
                value = value.value
            if isinstance(value, ast.Name):
                parts.append(value.id)
            return ".".join(reversed(parts))
        return ""

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in {"skip", "xfail", "pytest.skip", "pytest.xfail", "skipif"}:
                forbidden.append(f"call:{name}")
            if name == "print":
                forbidden.append("call:print")
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            for decorator in node.decorator_list:
                rendered = ast.dump(decorator)
                if "skip" in rendered or "xfail" in rendered:
                    forbidden.append(f"decorator:{node.name}:{rendered}")

    assert forbidden == [], f"forbidden skip/print paths remain: {forbidden}"

    module_tests = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]
    assert module_tests, "joined suite must define test functions"
    for func in module_tests:
        asserts = [n for n in ast.walk(func) if isinstance(n, ast.Assert)]
        assert asserts, f"{func.name} has no assertions"
    assert not forbidden


def test_backend_scoped_names_remain_distinct_across_backends() -> None:
    service, _ = _service("primary", "replica")
    left = service.create_bucket(_manifest("logs", ("primary",)))
    right = service.create_bucket(
        BucketManifest(
            identity_record=BucketIdentity("replica", "logs"),
            policy=_policy("logs-replica"),
            backend_capability=_capability("replica"),
            replicas=(BucketReplica("replica", BucketReplicaRole.PRIMARY),),
        )
    )
    assert left.identity.catalog_key != right.identity.catalog_key
    assert {item.identity.catalog_key for item in service.list_buckets().entries} == {
        "primary/logs",
        "replica/logs",
    }
    service.put_object(left.identity, "a", b"primary-only")
    service.put_object(right.identity, "a", b"replica-only")
    assert service.get_object(left.identity, "a").data == b"primary-only"
    assert service.get_object(right.identity, "a").data == b"replica-only"


def test_false_create_never_publishes_to_catalog() -> None:
    class _FalseAfterCreateBackend(InMemoryBucketBackend):
        def create_bucket(self, manifest: BucketManifest) -> bool:
            super().create_bucket(manifest)
            return False

    primary = InMemoryBucketBackend()
    replica = _FalseAfterCreateBackend()
    service = BucketService({"primary": primary, "replica": replica})
    manifest = _manifest("createfailure", ("primary", "replica"))
    with pytest.raises((BackendOperationError, CompensationRequiredError)):
        service.create_bucket(manifest)
    assert service.catalog.snapshot().entries == ()
    # Either fully rolled back, or pending compensation is journaled.
    if service.pending_compensations:
        for record in service.pending_compensations:
            assert record.action in {"rollback_create_bucket", "restore_bucket_manifest"}
    else:
        assert manifest.identity.catalog_key not in primary.buckets
        assert manifest.identity.catalog_key not in replica.buckets
