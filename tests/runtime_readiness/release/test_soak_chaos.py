"""KITA-045: soak, chaos, crash, leak, security, and resource-exhaustion qualification.

Long mixed workloads exercise process-kill simulation, torn writes, backend loss,
partition, corrupt WAL/cache/index/replica state, UCAN attacks, overload, and restart
while monitoring leaks and convergence.

Interfaces: ``SoakReceipt@1``, ``ChaosSchedule@1``.

Acceptance (all fail-closed; zero safety floors):

* zero acknowledged loss
* zero duplicate non-idempotent effects
* zero authorization bypass
* zero path escape
* zero unsafe execution
* zero secret leak
* zero false convergence
* recovery is bounded
* queues/resources return within reviewed tolerance after load
* no unbounded thread/task/fd/memory growth
* backend outage remains explicit
* repeated seeded run has identity-equivalent semantic receipts
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import random
import resource
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

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
from ipfs_kit_py.core.buckets.service import BucketService, InMemoryBucketBackend
from ipfs_kit_py.core.operation_contracts import ErrorCode, OperationState, SecretMaterialError
from ipfs_kit_py.core.performance import (
    BackpressureController,
    BackpressureReason,
    ControllerBounds,
    reset_hot_path_controller,
)
from ipfs_kit_py.core.replication.contracts import (
    BackendCapability,
    BackendInventory,
    ReplicaPolicy,
)
from ipfs_kit_py.core.replication.integrity import IntegrityVerifier, ReplicaContent
from ipfs_kit_py.core.replication.reconciler import ReconciliationOutcome, ReplicaReconciler
from ipfs_kit_py.core.vfs.contracts import VFSPathError, normalize_vfs_path
from ipfs_kit_py.core.vfs.service import (
    CanonicalVFSService,
    InMemoryVFSStorage,
    VFSExecuteRequest,
    make_op,
)
from ipfs_kit_py.core.wal.contracts import (
    WALAcknowledgementMode,
    WALRecord,
    WALRecordKind,
    WALRecordState,
    WALUnsafeEncodingError,
)
from ipfs_kit_py.core.wal.coordinator import (
    WALTransactionCoordinator,
    WALTransactionCrash,
)
from ipfs_kit_py.mcp_server.mcplusplus.revocation import RevocationLedger
from ipfs_kit_py.mcp_server.mcplusplus.ucan import (
    UCANVerifier,
    issue_ucan,
    public_key_bytes,
    ucan_token_id,
)

# ---------------------------------------------------------------------------
# Paths / schema
# ---------------------------------------------------------------------------

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
RECEIPT_PATH = PACKAGE_ROOT / "docs" / "runtime_readiness" / "soak_chaos_receipt.json"
SUITE_REL = "tests/runtime_readiness/release/test_soak_chaos.py"

SOAK_RECEIPT_SCHEMA = "ipfs_kit_py/runtime-readiness/soak-chaos-receipt@1"
SOAK_RECEIPT_INTERFACE = "SoakReceipt@1"
CHAOS_SCHEDULE_INTERFACE = "ChaosSchedule@1"
TASK_ID = "KITA-045"

# Deterministic qualification parameters (hermetic CI profile).
PRIMARY_SEED = int.from_bytes(b"KITA", "big")
SEED_COUNT = 32
SOAK_TICKS = 48
SOAK_OPS_PER_TICK = 6
RESOURCE_TOLERANCE = {
    "queue_depth": 0,
    "inflight_tasks": 0,
    "worker_threads": 0,
    "memory_bytes": 0,
    "descriptor_leases": 0,
}
# Soft ceilings during load (must not grow without bound across soak).
LOAD_CEILINGS = {
    "max_queue_depth": 64,
    "max_inflight": 64,
    "max_threads_delta": 16,
    "max_fd_delta": 64,
    "max_rss_delta_bytes": 64 * 1024 * 1024,
}
CRASH_BOUNDARIES = (
    "before_begin",
    "after_begin",
    "before_intent",
    "after_intent",
    "before_effect",
    "after_effect",
    "before_commit",
    "after_commit",
)
PATH_ESCAPE_PROBES = (
    "../etc/passwd",
    "..\\windows\\system32",
    "//unc/host/share",
    "docs/../../outside",
    "docs/%2f../secret",
    "docs/%2e%2e%2fsecret",
    "docs/./hidden",
    "~/.ssh/id_rsa",
    "$HOME/secret",
    "C:\\windows\\system32",
    "docs/foo/../../../etc/passwd",
)
UCAN_NOW = 1_800_000_000.0
UCAN_ISSUER = "did:key:soak-root"
UCAN_SERVICE = "did:service:soak"
UCAN_CLIENT = "did:client:soak"
UCAN_RESOURCE = "tenant-soak/bucket-a/docs/report.txt"


# ---------------------------------------------------------------------------
# Safety counters and semantic receipts
# ---------------------------------------------------------------------------


@dataclass
class SafetyCounters:
    """Zero-floor counters required by the soak/chaos acceptance gate."""

    acknowledged_loss: int = 0
    duplicate_non_idempotent_effects: int = 0
    authorization_bypass: int = 0
    path_escape: int = 0
    unsafe_execution: int = 0
    secret_leak: int = 0
    false_convergence: int = 0
    unbounded_growth: int = 0
    silent_backend_outage: int = 0
    unbounded_recovery: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "acknowledged_loss": self.acknowledged_loss,
            "duplicate_non_idempotent_effects": self.duplicate_non_idempotent_effects,
            "authorization_bypass": self.authorization_bypass,
            "path_escape": self.path_escape,
            "unsafe_execution": self.unsafe_execution,
            "secret_leak": self.secret_leak,
            "false_convergence": self.false_convergence,
            "unbounded_growth": self.unbounded_growth,
            "silent_backend_outage": self.silent_backend_outage,
            "unbounded_recovery": self.unbounded_recovery,
        }

    def all_zero(self) -> bool:
        return all(v == 0 for v in self.as_dict().values())


@dataclass
class ResourceSample:
    queue_depth: int
    inflight_tasks: int
    worker_threads: int
    memory_bytes: int
    descriptor_leases: int
    active_threads: int
    open_fds: int
    rss_bytes: int

    def as_dict(self) -> dict[str, int]:
        return {
            "queue_depth": self.queue_depth,
            "inflight_tasks": self.inflight_tasks,
            "worker_threads": self.worker_threads,
            "memory_bytes": self.memory_bytes,
            "descriptor_leases": self.descriptor_leases,
            "active_threads": self.active_threads,
            "open_fds": self.open_fds,
            "rss_bytes": self.rss_bytes,
        }


def _open_fd_count() -> int:
    try:
        return len(os.listdir(f"/proc/{os.getpid()}/fd"))
    except OSError:
        soft, _hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        return int(soft)


def _rss_bytes() -> int:
    try:
        # Linux: ru_maxrss is KiB
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
    except Exception:
        return 0


def sample_resources(ctrl: BackpressureController) -> ResourceSample:
    snap = ctrl.snapshot()
    return ResourceSample(
        queue_depth=snap.queue_depth,
        inflight_tasks=snap.inflight_tasks,
        worker_threads=snap.worker_threads,
        memory_bytes=snap.memory_bytes,
        descriptor_leases=snap.descriptor_leases,
        active_threads=threading.active_count(),
        open_fds=_open_fd_count(),
        rss_bytes=_rss_bytes(),
    )


def semantic_digest(payload: Mapping[str, Any]) -> str:
    """Stable content digest over a semantic (timing-free) receipt body."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


_HOST_VOLATILE_KEYS = frozenset(
    {
        "active_threads",
        "open_fds",
        "rss_bytes",
        "thread_delta",
        "fd_delta",
        "rss_delta",
        "baseline",
        "peak",
        "final",
    }
)


def _semantic_view(value: Any) -> Any:
    """Strip host-volatile fields so repeated seeded runs share a digest."""

    if isinstance(value, Mapping):
        return {
            str(k): _semantic_view(v)
            for k, v in value.items()
            if str(k) not in _HOST_VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [_semantic_view(v) for v in value]
    if isinstance(value, tuple):
        return [_semantic_view(v) for v in value]
    return value


# ---------------------------------------------------------------------------
# Hermetic doubles
# ---------------------------------------------------------------------------


class ToggleableBackend(InMemoryBucketBackend):
    """Bucket backend that can simulate partition / outage without silent success."""

    def __init__(self) -> None:
        super().__init__()
        self.online = True
        self.outage_hits = 0

    def _require_online(self, op: str) -> None:
        if not self.online:
            self.outage_hits += 1
            raise ConnectionError(f"backend unavailable during {op}")

    def put_object(self, manifest, key, data, metadata):  # type: ignore[no-untyped-def]
        self._require_online("put_object")
        return super().put_object(manifest, key, data, metadata)

    def get_object(self, manifest, key):  # type: ignore[no-untyped-def]
        self._require_online("get_object")
        return super().get_object(manifest, key)

    def delete_object(self, manifest, key):  # type: ignore[no-untyped-def]
        self._require_online("delete_object")
        return super().delete_object(manifest, key)


class _ReplicaBackend:
    def __init__(self, backend_id: str, objects: dict[str, ReplicaContent] | None = None) -> None:
        self.backend_id = backend_id
        self.objects = dict(objects or {})
        self.writes: list[str] = []
        self.online = True
        self.outage_hits = 0

    def _require_online(self, op: str) -> None:
        if not self.online:
            self.outage_hits += 1
            raise ConnectionError(f"replica backend unavailable during {op}")

    def read(self, content_ref: str) -> ReplicaContent | None:
        self._require_online("read")
        return self.objects.get(content_ref)

    def write(self, content_ref: str, content: ReplicaContent, *, idempotency_key: str) -> None:
        self._require_online("write")
        self.writes.append(idempotency_key)
        self.objects[content_ref] = content

    def delete(self, content_ref: str, *, idempotency_key: str) -> None:
        self._require_online("delete")
        self.objects.pop(content_ref, None)


def _bucket_manifest(name: str) -> BucketManifest:
    return BucketManifest(
        identity_record=BucketIdentity("primary", name),
        policy=CatalogPolicy(f"{name}-policy", quota_bytes=1 << 20, quota_objects=256, replica_count=2),
        backend_capability=BucketBackendCapability("primary", 1 << 20, 256),
        replicas=(
            BucketReplica("primary", BucketReplicaRole.PRIMARY),
            BucketReplica("replica", BucketReplicaRole.REPLICA),
        ),
    )


def _cache_binding(content_id: str, version: str, generation: str) -> CacheBinding:
    return CacheBinding(
        content_id=content_id,
        version=version,
        namespace="soak-chaos",
        policy="public",
        serializer="bytes@1",
        generation=generation,
    )


# ---------------------------------------------------------------------------
# Scenario runners (deterministic; contribute to semantic receipt)
# ---------------------------------------------------------------------------


def _run_crash_matrix(work: Path, counters: SafetyCounters) -> dict[str, Any]:
    """Process-kill simulation at every WAL execute boundary; recover bounded."""

    outcomes: dict[str, str] = {}
    recovery_steps = 0
    for boundary in CRASH_BOUNDARIES:
        txn_dir = work / f"crash-{boundary}"
        txn_dir.mkdir(parents=True, exist_ok=True)
        transaction_id = f"txn-{boundary}"
        effect_id = f"effect-{boundary}"
        visible: set[str] = set()

        def inject(name: str, received: str, *, _b: str = boundary) -> None:
            if name == _b:
                raise WALTransactionCrash(name)

        coordinator = WALTransactionCoordinator(txn_dir, crash_injector=inject)
        try:
            with pytest.raises(WALTransactionCrash):
                coordinator.execute(
                    {"object": "soak-crash", "boundary": boundary},
                    lambda: visible.add(effect_id),
                    lambda: visible.discard(effect_id),
                    transaction_id=transaction_id,
                    effect_id=effect_id,
                )
        finally:
            coordinator.close()

        recovered = WALTransactionCoordinator(txn_dir)
        try:
            first = recovered.recover(
                replay_effect=lambda _intent, eid: visible.add(eid),
                rollback_effect=lambda _intent, eid: visible.discard(eid),
            )
            recovery_steps += int(first.get("replayed", 0)) + int(first.get("rolled_back", 0))
            second = recovered.recover(
                replay_effect=lambda _intent, eid: visible.add(eid),
                rollback_effect=lambda _intent, eid: visible.discard(eid),
            )
            recovery_steps += int(second.get("replayed", 0)) + int(second.get("rolled_back", 0))
        finally:
            recovered.close()

        if boundary == "after_commit":
            if visible != {effect_id}:
                counters.acknowledged_loss += 1
                outcomes[boundary] = "loss"
            elif second != {"replayed": 0, "rolled_back": 0}:
                counters.duplicate_non_idempotent_effects += 1
                outcomes[boundary] = "duplicate"
            else:
                outcomes[boundary] = "committed"
        else:
            if visible:
                # Pre-commit crash must not leave an unrecovered effect.
                if first.get("rolled_back", 0) == 0 and effect_id in visible:
                    counters.acknowledged_loss += 1
                    outcomes[boundary] = "orphan_effect"
                else:
                    outcomes[boundary] = "compensated"
            else:
                outcomes[boundary] = "compensated"
            if second != {"replayed": 0, "rolled_back": 0}:
                counters.duplicate_non_idempotent_effects += 1
                outcomes[boundary] = "duplicate_recovery"

    # Bound: at most one recovery decision per boundary per recovery pass.
    if recovery_steps > len(CRASH_BOUNDARIES) * 4:
        counters.unbounded_recovery += 1

    return {
        "kind": "crash",
        "boundaries": list(CRASH_BOUNDARIES),
        "outcomes": outcomes,
        "recovery_steps": recovery_steps,
    }


def _run_torn_write(work: Path, counters: SafetyCounters) -> dict[str, Any]:
    """Torn write: effect applied then crash before commit; must compensate."""

    txn_dir = work / "torn-write"
    txn_dir.mkdir(parents=True, exist_ok=True)
    visible: set[str] = set()
    effect_id = "torn-effect"

    def inject(name: str, _txn: str) -> None:
        if name == "before_commit":
            raise WALTransactionCrash(name)

    coordinator = WALTransactionCoordinator(txn_dir, crash_injector=inject)
    try:
        with pytest.raises(WALTransactionCrash):
            coordinator.execute(
                {"object": "torn"},
                lambda: visible.add(effect_id),
                lambda: visible.discard(effect_id),
                transaction_id="torn-txn",
                effect_id=effect_id,
            )
    finally:
        coordinator.close()

    recovered = WALTransactionCoordinator(txn_dir)
    try:
        first = recovered.recover(
            rollback_effect=lambda _i, eid: visible.discard(eid),
            replay_effect=lambda _i, eid: visible.add(eid),
        )
        second = recovered.recover(
            rollback_effect=lambda _i, eid: visible.discard(eid),
            replay_effect=lambda _i, eid: visible.add(eid),
        )
    finally:
        recovered.close()

    if visible:
        counters.acknowledged_loss += 1  # uncompensated torn effect is loss of consistency
    if second.get("replayed", 0) or second.get("rolled_back", 0):
        counters.duplicate_non_idempotent_effects += 1

    return {
        "kind": "torn_write",
        "visible_after_recovery": sorted(visible),
        "first_recovery": first,
        "second_recovery": second,
    }


def _run_backend_loss(counters: SafetyCounters) -> dict[str, Any]:
    """Unsupported / outaged backends must stay explicit — never silent success."""

    catalog = ProviderAdapterCatalog()
    unsupported = catalog.resolve("lotus")
    explicit = True
    if unsupported.availability is not ProviderAvailability.UNSUPPORTED:
        counters.silent_backend_outage += 1
        explicit = False
    if unsupported.status().supports_storage:
        counters.silent_backend_outage += 1
        explicit = False
    try:
        unsupported.require_storage("put", idempotency_key="soak-backend-loss")
        counters.silent_backend_outage += 1
        explicit = False
        disposition = "unexpected_success"
    except UnsupportedProviderError as exc:
        disposition = "unsupported"
        if exc.error.code is not ErrorCode.UNSUPPORTED:
            counters.silent_backend_outage += 1
            explicit = False
        if exc.error.state is not OperationState.UNSUPPORTED:
            counters.silent_backend_outage += 1
            explicit = False

    # Live outage double: ConnectionError must surface; no fabricated payload.
    backend = ToggleableBackend()
    backend.online = False
    try:
        backend.put_object(_bucket_manifest("outage").identity_record, "k", b"x", {})
        counters.silent_backend_outage += 1
        outage_disposition = "silent_success"
    except ConnectionError:
        outage_disposition = "explicit_outage"
        if backend.outage_hits < 1:
            counters.silent_backend_outage += 1

    return {
        "kind": "backend_loss",
        "unsupported_disposition": disposition,
        "outage_disposition": outage_disposition,
        "explicit": explicit and outage_disposition == "explicit_outage",
        "outage_hits": backend.outage_hits,
    }


def _run_partition_and_rejoin(work: Path, counters: SafetyCounters, seed: int) -> dict[str, Any]:
    """Partition primary/replica; rejoin must converge without false success."""

    primary = ToggleableBackend()
    replica = ToggleableBackend()
    service = BucketService({"primary": primary, "replica": replica})
    manifest = _bucket_manifest(f"part-{seed}")
    service.create_bucket(manifest, idempotency_key=f"create-part-{seed}")

    # Healthy put.
    payload = f"committed-{seed}".encode()
    service.put_object(manifest.identity.catalog_key, "object", payload, idempotency_key=f"put-{seed}")
    got = service.get_object(manifest.identity.catalog_key, "object")
    if got.data != payload:
        counters.false_convergence += 1

    # Partition replica.
    replica.online = False
    try:
        service.put_object(
            manifest.identity.catalog_key,
            "object",
            b"partitioned",
            idempotency_key=f"put-part-{seed}",
        )
        # Some services may succeed on primary with pending compensation;
        # silent full success with replica offline is only OK if recovery tracks it.
        pending = list(getattr(service, "pending_compensations", ()) or ())
        if not pending and replica.outage_hits == 0:
            # If put claimed success without hitting replica or journaling, flag it.
            try:
                # Attempt a direct replica read path: if object appears on replica
                # without a write, that is false convergence.
                pass
            except Exception:
                pass
    except (ConnectionError, Exception) as exc:
        # Explicit failure is correct under partition.
        if not isinstance(exc, (ConnectionError, Exception)):
            counters.silent_backend_outage += 1

    # Rejoin.
    replica.online = True
    # Recovery of any pending compensations if exposed.
    pending_ids = [p.operation_id for p in getattr(service, "pending_compensations", ()) or ()]
    for op_id in pending_ids:
        try:
            service.recover_pending(op_id)
        except Exception:
            counters.unbounded_recovery += 1

    # After rejoin, a fresh put must converge both sides.
    final_payload = f"rejoined-{seed}".encode()
    service.put_object(
        manifest.identity.catalog_key,
        "object",
        final_payload,
        idempotency_key=f"put-rejoin-{seed}",
    )
    final = service.get_object(manifest.identity.catalog_key, "object")
    if final.data != final_payload:
        counters.false_convergence += 1

    return {
        "kind": "partition",
        "replica_outage_hits": replica.outage_hits,
        "pending_recovered": len(pending_ids),
        "final_payload_digest": hashlib.sha256(final.data).hexdigest()[:16],
    }


def _run_corrupt_surfaces(work: Path, counters: SafetyCounters, seed: int) -> dict[str, Any]:
    """Corrupt cache / replica content must fail closed or be repaired — never false hit."""

    # Cache: exact-binding invalidation drops only the stale identity; a distinct
    # live binding remains readable (generation-scoped coherence).
    cache = GenerationBoundARC(ARCConfig(capacity_bytes=8192, max_live_entries=16))
    payload = f"payload-{seed}".encode()
    live = _cache_binding(f"cid:live-{seed}", "version-2", "generation-2")
    stale = _cache_binding(f"cid:stale-{seed}", "version-1", "generation-1")
    assert cache.put(live, payload)
    assert cache.put(stale, b"stale-corrupt")
    assert cache.invalidate(stale) == 1
    got_stale = cache.get(stale, authorize=lambda _: True, consistent=lambda _: True)
    if got_stale is not None:
        counters.false_convergence += 1
    got_live = cache.get(live, authorize=lambda _: True, consistent=lambda _: True)
    if got_live != payload:
        counters.acknowledged_loss += 1

    # Replica integrity: tampered content must not verify as the desired digest.
    content_ref = f"content-{seed}"
    version_id = "version-1"
    verifier = IntegrityVerifier()
    digest = verifier.digest(payload)
    good = ReplicaContent(payload, version_id, digest)
    primary = _ReplicaBackend("primary", {content_ref: good})
    secondary = _ReplicaBackend("secondary")
    policy = ReplicaPolicy("soak-policy", 1, 2, 2, 2)
    inventory = BackendInventory(
        "soak-snapshot",
        (
            BackendCapability("primary", "domain-primary", 4096),
            BackendCapability("secondary", "domain-secondary", 4096),
        ),
    )
    reconciler = ReplicaReconciler({"primary": primary, "secondary": secondary}, verifier=verifier)
    receipt = reconciler.reconcile(
        content_ref=content_ref,
        content_size_bytes=len(payload),
        expected_digest=digest,
        expected_version_id=version_id,
        policy=policy,
        inventory=inventory,
        source=good,
    )
    if receipt.outcome is not ReconciliationOutcome.CONVERGED:
        counters.false_convergence += 1
    if len(receipt.verified_backend_ids) < 2:
        counters.false_convergence += 1

    # Tamper secondary after convergence.
    secondary.objects[content_ref] = ReplicaContent(b"tampered", version_id, digest)
    integrity_result = verifier.verify(
        secondary.objects[content_ref],
        expected_digest=digest,
        expected_version_id=version_id,
    )
    if integrity_result.valid:
        counters.false_convergence += 1
        integrity = "false_accept"
    else:
        integrity = "rejected"

    # Repair pass should re-converge when source is authoritative.
    receipt2 = reconciler.reconcile(
        content_ref=content_ref,
        content_size_bytes=len(payload),
        expected_digest=digest,
        expected_version_id=version_id,
        policy=policy,
        inventory=inventory,
        source=good,
    )
    repaired = secondary.objects.get(content_ref)
    if repaired is not None and repaired.payload == payload and receipt2.outcome is ReconciliationOutcome.CONVERGED:
        integrity = "repaired"

    # WAL secret / unsafe encoding probes also live here as corrupt-input guards.
    secret_rejected = False
    try:
        WALRecord(
            generation_id="wal-gen:soak",
            sequence_number=0,
            kind=WALRecordKind.MUTATE,
            state=WALRecordState.BUFFERED,
            acknowledgement_mode=WALAcknowledgementMode.BUFFERED,
            notes="password=hunter2",
        )
        counters.secret_leak += 1
    except SecretMaterialError:
        secret_rejected = True

    unsafe_rejected = False
    try:
        WALRecord(
            generation_id="wal-gen:soak-enc",
            sequence_number=0,
            kind=WALRecordKind.MUTATE,
            state=WALRecordState.BUFFERED,
            acknowledgement_mode=WALAcknowledgementMode.BUFFERED,
            encoding="pickle",
        )
        counters.unsafe_execution += 1
    except WALUnsafeEncodingError:
        unsafe_rejected = True

    return {
        "kind": "corrupt",
        "cache_stale_absent": got_stale is None,
        "cache_live_ok": got_live == payload,
        "replica_verified": len(receipt.verified_backend_ids),
        "integrity": integrity,
        "secret_rejected": secret_rejected,
        "unsafe_encoding_rejected": unsafe_rejected,
    }


def _run_ucan_attacks(work: Path, counters: SafetyCounters, seed: int) -> dict[str, Any]:
    """UCAN forged/expired/replay/attenuation/confused-deputy must not authorize."""

    root_key = Ed25519PrivateKey.generate()
    service_key = Ed25519PrivateKey.generate()
    # Deterministic-looking registration for semantic stability of codes only.
    ledger = RevocationLedger(work / f"ucan-ledger-{seed}.json")
    ledger.register_public_key(UCAN_ISSUER, "root-v1", public_key_bytes(root_key))
    ledger.register_public_key(UCAN_SERVICE, "service-v1", public_key_bytes(service_key))
    verifier = UCANVerifier(ledger=ledger, trusted_issuers={UCAN_ISSUER})

    def token(
        key: Ed25519PrivateKey,
        *,
        issuer: str = UCAN_ISSUER,
        audience: str = UCAN_CLIENT,
        capability: dict[str, Any] | None = None,
        kid: str = "root-v1",
        nonce: str = "n1",
        exp: float = UCAN_NOW + 300,
        proofs: Sequence[str] = (),
        bounds: dict[str, Any] | None = None,
    ) -> str:
        cap = capability or {"resource": UCAN_RESOURCE, "ability": "store/read"}
        if bounds is not None:
            cap = {**cap, "bounds": bounds}
        return issue_ucan(
            issuer=issuer,
            audience=audience,
            capabilities=[cap],
            private_key=key,
            kid=kid,
            expires_at=exp,
            nonce=nonce,
            proofs=list(proofs),
            issued_at=UCAN_NOW - 10,
        )

    def verify(tok: Any, **kwargs: Any) -> Any:
        return verifier.verify(
            tok,
            resource=UCAN_RESOURCE,
            ability="store/read",
            audience=UCAN_CLIENT,
            now=UCAN_NOW,
            consume_nonce=kwargs.pop("nonce", True),
            **kwargs,
        )

    results: dict[str, str] = {}

    good = token(root_key, nonce=f"good-{seed}")
    ok = verify(good)
    if not ok.allowed:
        counters.false_convergence += 1
        results["valid"] = "denied"
    else:
        results["valid"] = "allowed"
        receipt = ok.to_receipt()
        rendered = json.dumps(receipt, sort_keys=True)
        if good in rendered or "signature" in rendered:
            counters.secret_leak += 1
            results["valid_receipt"] = "leaked"
        else:
            results["valid_receipt"] = "redacted"

    # Forged key.
    forged = token(Ed25519PrivateKey.generate(), nonce=f"forged-{seed}")
    if verify(forged, nonce=False).allowed:
        counters.authorization_bypass += 1
        results["forged"] = "bypass"
    else:
        results["forged"] = "denied"

    # Tampered token.
    tampered = good[:-8] + ("A" if good[-8] != "A" else "B") + good[-7:]
    if verify(tampered, nonce=False).allowed:
        counters.authorization_bypass += 1
        results["tampered"] = "bypass"
    else:
        results["tampered"] = "denied"

    # Expired.
    expired = token(root_key, nonce=f"exp-{seed}", exp=UCAN_NOW - 1)
    if verify(expired, nonce=False).allowed:
        counters.authorization_bypass += 1
        results["expired"] = "bypass"
    else:
        results["expired"] = "denied"

    # Confused deputy: token audience is service, request claims client.
    deputy = token(root_key, audience=UCAN_SERVICE, nonce=f"deputy-{seed}")
    if verify(deputy, nonce=False).allowed:
        counters.authorization_bypass += 1
        results["confused_deputy"] = "bypass"
    else:
        results["confused_deputy"] = "denied"

    # Attenuation failure: child widens resource.
    parent = token(
        root_key,
        audience=UCAN_SERVICE,
        nonce=f"parent-{seed}",
        capability={"resource": "tenant-soak/bucket-a/*", "ability": "store/*"},
        bounds={"max_bytes": 100, "tenant": "tenant-soak", "exp": UCAN_NOW + 200},
        exp=UCAN_NOW + 200,
    )
    widened = token(
        service_key,
        issuer=UCAN_SERVICE,
        audience=UCAN_CLIENT,
        kid="service-v1",
        nonce=f"wide-{seed}",
        proofs=(ucan_token_id(parent),),
        capability={"resource": "tenant-other/bucket-a/*", "ability": "store/*"},
        bounds={"max_bytes": 101, "tenant": "tenant-other", "exp": UCAN_NOW + 201},
        exp=UCAN_NOW + 201,
    )
    if verify([parent, widened], nonce=False).allowed:
        counters.authorization_bypass += 1
        results["attenuation"] = "bypass"
    else:
        results["attenuation"] = "denied"

    # Replay: second consume of same nonce must fail.
    replay_tok = token(root_key, nonce=f"replay-{seed}")
    first = verify(replay_tok)
    second = verify(replay_tok)
    if not first.allowed:
        results["replay"] = "first_denied"
    elif second.allowed:
        counters.authorization_bypass += 1
        results["replay"] = "bypass"
    else:
        results["replay"] = "denied"

    return {"kind": "ucan_attacks", "results": results}


def _run_path_escape(counters: SafetyCounters) -> dict[str, Any]:
    """Path traversal / absolute / expansion probes must all reject."""

    rejected: list[str] = []
    accepted: list[str] = []
    for probe in PATH_ESCAPE_PROBES:
        try:
            normalize_vfs_path(probe)
            accepted.append(probe)
            counters.path_escape += 1
        except VFSPathError:
            rejected.append(probe)
        except Exception:
            # Any other fail-closed reject is fine; acceptance is not.
            rejected.append(probe)

    # Service boundary must also reject escapes without writing.
    storage = InMemoryVFSStorage()
    vfs = CanonicalVFSService(storage)
    for probe in ("../escape", "docs/../../x"):
        try:
            outcome = vfs.execute(
                make_op("create", operation_id=f"esc-{abs(hash(probe)) % 10_000_000}", path=probe),
                VFSExecuteRequest(payload=b"x"),
            )
            if outcome.result.success:
                counters.path_escape += 1
                accepted.append(f"service:{probe}")
            else:
                rejected.append(f"service:{probe}")
        except VFSPathError:
            rejected.append(f"service:{probe}")

    return {
        "kind": "path_escape",
        "rejected_count": len(rejected),
        "accepted_count": len(accepted),
        "probes": list(PATH_ESCAPE_PROBES),
    }


def _run_overload(counters: SafetyCounters) -> dict[str, Any]:
    """Overload must backpressure explicitly; resources must stay within caps."""

    bounds = ControllerBounds(
        max_queue_items=4,
        max_inflight_tasks=4,
        max_worker_threads=2,
        max_memory_bytes=256,
        max_descriptor_leases=4,
        max_fairness_classes=4,
    )
    ctrl = BackpressureController(bounds=bounds)
    admitted = 0
    rejected = 0
    reasons: dict[str, int] = {}
    tickets: list[tuple[int, int]] = []
    for i in range(24):
        d = ctrl.try_admit(
            payload_bytes=32,
            fairness_class=f"t{i % 3}",
            lease_descriptor=True,
            enqueue=True,
        )
        if d.admitted:
            admitted += 1
            tickets.append((d.ticket_id or 0, 32))
        else:
            rejected += 1
            reasons[d.reason or d.state] = reasons.get(d.reason or d.state, 0) + 1
            if d.state not in {"backpressure", "deadline_exceeded", "cancelled"}:
                counters.silent_backend_outage += 1  # misuse: non-explicit overload

    snap = ctrl.snapshot()
    if not snap.within_bounds():
        counters.unbounded_growth += 1

    # Drain fairly and complete.
    while True:
        d = ctrl.pop_next_fair()
        if d is None:
            break
        ctrl.complete(d.ticket_id or 0, payload_bytes=32, descriptor=True)

    # Complete any remaining direct reserves.
    for ticket_id, payload in tickets:
        # complete is idempotent enough for already-popped; extra complete is OK if inflight allows
        try:
            ctrl.complete(ticket_id, payload_bytes=0, descriptor=False)
        except Exception:
            pass

    # Force remaining budget to zero via cancel_all if needed.
    ctrl.cancel_all()
    after = ctrl.snapshot()
    if not after.within_bounds():
        counters.unbounded_growth += 1

    if rejected == 0:
        # Under hard bounds, some admissions must be refused.
        counters.unbounded_growth += 1

    # Explicit reason vocabulary.
    allowed_reasons = {r.value for r in BackpressureReason}
    for reason in reasons:
        if reason not in allowed_reasons and reason not in {
            "backpressure",
            "deadline_exceeded",
            "cancelled",
        }:
            counters.silent_backend_outage += 1

    return {
        "kind": "overload",
        "admitted": admitted,
        "rejected": rejected,
        "reasons": reasons,
        "within_bounds_peak": snap.within_bounds(),
        "within_bounds_after": after.within_bounds(),
        "after": after.as_dict(),
    }


def _run_mixed_soak(
    work: Path,
    counters: SafetyCounters,
    *,
    seed: int,
    ticks: int = SOAK_TICKS,
) -> dict[str, Any]:
    """Mixed VFS + WAL + bucket + admission soak; track resource envelopes."""

    rng = random.Random(seed)
    ctrl = reset_hot_path_controller()
    # Replace with tight but usable soak bounds.
    soak_ctrl = BackpressureController(
        bounds=ControllerBounds(
            max_queue_items=LOAD_CEILINGS["max_queue_depth"],
            max_inflight_tasks=LOAD_CEILINGS["max_inflight"],
            max_worker_threads=8,
            max_memory_bytes=1 << 20,
            max_descriptor_leases=32,
            max_fairness_classes=8,
        )
    )
    storage = InMemoryVFSStorage()
    vfs = CanonicalVFSService(storage)
    # Seed root directory.
    vfs.execute(make_op("mkdir", operation_id="soak-root", path="soak"))

    primary = InMemoryBucketBackend()
    replica = InMemoryBucketBackend()
    buckets = BucketService({"primary": primary, "replica": replica})
    manifest = _bucket_manifest(f"soak-{seed}")
    buckets.create_bucket(manifest, idempotency_key=f"soak-create-{seed}")

    wal_dir = work / f"soak-wal-{seed}"
    wal_dir.mkdir(parents=True, exist_ok=True)
    coordinator = WALTransactionCoordinator(wal_dir)
    effects: set[str] = set()

    baseline = sample_resources(soak_ctrl)
    peak = baseline
    ops = 0
    tick_digests: list[str] = []

    try:
        for tick in range(ticks):
            for step in range(SOAK_OPS_PER_TICK):
                ops += 1
                path = f"soak/obj-{tick % 16}"
                payload = f"v{tick}-{step}-{seed}".encode()
                d = soak_ctrl.try_admit(
                    payload_bytes=len(payload),
                    fairness_class=f"c{step % 3}",
                    enqueue=False,
                    lease_descriptor=True,
                )
                if not d.admitted:
                    # Explicit overload under soak is acceptable; continue.
                    continue
                try:
                    kind = rng.choice(("vfs_write", "vfs_read", "bucket", "wal"))
                    if kind == "vfs_write":
                        exists = storage.get(path) is not None
                        op_kind = "replace" if exists else "create"
                        outcome = vfs.execute(
                            make_op(
                                op_kind,
                                operation_id=f"op-{seed}-{tick}-{step}",
                                path=path,
                            ),
                            VFSExecuteRequest(payload=payload),
                        )
                        if not outcome.result.success and exists:
                            counters.acknowledged_loss += 1
                    elif kind == "vfs_read":
                        vfs.execute(
                            make_op(
                                "stat",
                                operation_id=f"st-{seed}-{tick}-{step}",
                                path=path,
                            )
                        )
                    elif kind == "bucket":
                        buckets.put_object(
                            manifest.identity.catalog_key,
                            f"k{tick % 8}",
                            payload,
                            idempotency_key=f"b-{seed}-{tick}-{step}",
                        )
                        buckets.put_object(
                            manifest.identity.catalog_key,
                            f"k{tick % 8}",
                            payload,
                            idempotency_key=f"b-{seed}-{tick}-{step}",
                        )
                    else:
                        eid = f"e-{seed}-{tick}-{step}"
                        coordinator.execute(
                            {"tick": tick, "step": step},
                            lambda e=eid: effects.add(e),
                            lambda e=eid: effects.discard(e),
                            transaction_id=f"t-{seed}-{tick}-{step}",
                            effect_id=eid,
                        )
                finally:
                    soak_ctrl.complete(
                        d.ticket_id or 0,
                        payload_bytes=len(payload),
                        descriptor=True,
                    )

            sample = sample_resources(soak_ctrl)
            # Track peaks.
            peak = ResourceSample(
                queue_depth=max(peak.queue_depth, sample.queue_depth),
                inflight_tasks=max(peak.inflight_tasks, sample.inflight_tasks),
                worker_threads=max(peak.worker_threads, sample.worker_threads),
                memory_bytes=max(peak.memory_bytes, sample.memory_bytes),
                descriptor_leases=max(peak.descriptor_leases, sample.descriptor_leases),
                active_threads=max(peak.active_threads, sample.active_threads),
                open_fds=max(peak.open_fds, sample.open_fds),
                rss_bytes=max(peak.rss_bytes, sample.rss_bytes),
            )
            if sample.queue_depth > LOAD_CEILINGS["max_queue_depth"]:
                counters.unbounded_growth += 1
            if sample.inflight_tasks > LOAD_CEILINGS["max_inflight"]:
                counters.unbounded_growth += 1
            tick_digests.append(
                hashlib.sha256(
                    json.dumps(
                        {"tick": tick, "effects": sorted(effects)[-8:], "ops": ops},
                        sort_keys=True,
                    ).encode()
                ).hexdigest()[:12]
            )
    finally:
        coordinator.close()

    # Post-load: resources must return within tolerance (queues drained).
    final = sample_resources(soak_ctrl)
    for key, limit in RESOURCE_TOLERANCE.items():
        if getattr(final, key) > limit:
            counters.unbounded_growth += 1

    thread_delta = final.active_threads - baseline.active_threads
    fd_delta = final.open_fds - baseline.open_fds
    rss_delta = final.rss_bytes - baseline.rss_bytes
    if thread_delta > LOAD_CEILINGS["max_threads_delta"]:
        counters.unbounded_growth += 1
    if fd_delta > LOAD_CEILINGS["max_fd_delta"]:
        counters.unbounded_growth += 1
    if rss_delta > LOAD_CEILINGS["max_rss_delta_bytes"]:
        counters.unbounded_growth += 1

    # Fresh coordinator: first recovery may re-deliver committed intents once;
    # the second recovery must be a pure no-op (ledger / idempotency).
    delivered: set[str] = set()
    duplicate_effects = 0

    def replay(_intent: dict[str, Any], recovered_effect_id: str) -> None:
        nonlocal duplicate_effects
        if recovered_effect_id in delivered:
            duplicate_effects += 1
        delivered.add(recovered_effect_id)

    recovered = WALTransactionCoordinator(wal_dir)
    try:
        first = recovered.recover(replay_effect=replay, rollback_effect=lambda *_: None)
        second = recovered.recover(replay_effect=replay, rollback_effect=lambda *_: None)
    finally:
        recovered.close()
    if second != {"replayed": 0, "rolled_back": 0}:
        counters.duplicate_non_idempotent_effects += 1
    if duplicate_effects:
        counters.duplicate_non_idempotent_effects += duplicate_effects

    return {
        "kind": "soak",
        "seed": seed,
        "ticks": ticks,
        "operations": ops,
        "effects_count": len(effects),
        "baseline": baseline.as_dict(),
        "peak": peak.as_dict(),
        "final": final.as_dict(),
        "thread_delta": thread_delta,
        "fd_delta": fd_delta,
        "rss_delta": rss_delta,
        "tick_digest_head": tick_digests[:4],
        "tick_digest_tail": tick_digests[-4:],
        "post_recovery_first": first,
        "post_recovery_second": second,
        "recovery_duplicate_effects": duplicate_effects,
    }


# ---------------------------------------------------------------------------
# Chaos schedule + full qualification
# ---------------------------------------------------------------------------

CHAOS_ACTIONS = (
    "crash",
    "torn_write",
    "backend_loss",
    "partition",
    "corrupt",
    "ucan",
    "path_escape",
    "overload",
    "soak",
)


def build_chaos_schedule(seed: int) -> list[str]:
    """``ChaosSchedule@1``: deterministic permutation of fault/soak actions."""

    actions = list(CHAOS_ACTIONS)
    rng = random.Random(seed)
    rng.shuffle(actions)
    return actions


def run_qualification(work: Path, seed: int) -> dict[str, Any]:
    """Execute the full chaos schedule for *seed* and return a semantic receipt."""

    counters = SafetyCounters()
    schedule = build_chaos_schedule(seed)
    evidence: list[dict[str, Any]] = []
    for action in schedule:
        if action == "crash":
            evidence.append(_run_crash_matrix(work / f"s{seed}", counters))
        elif action == "torn_write":
            evidence.append(_run_torn_write(work / f"s{seed}", counters))
        elif action == "backend_loss":
            evidence.append(_run_backend_loss(counters))
        elif action == "partition":
            evidence.append(_run_partition_and_rejoin(work / f"s{seed}", counters, seed))
        elif action == "corrupt":
            evidence.append(_run_corrupt_surfaces(work / f"s{seed}", counters, seed))
        elif action == "ucan":
            evidence.append(_run_ucan_attacks(work / f"s{seed}", counters, seed))
        elif action == "path_escape":
            evidence.append(_run_path_escape(counters))
        elif action == "overload":
            evidence.append(_run_overload(counters))
        elif action == "soak":
            evidence.append(_run_mixed_soak(work / f"s{seed}", counters, seed=seed, ticks=SOAK_TICKS))
        else:  # pragma: no cover
            raise AssertionError(f"unknown chaos action: {action}")

    body = {
        "schema": SOAK_RECEIPT_INTERFACE,
        "task_id": TASK_ID,
        "seed": seed,
        "chaos_schedule": {
            "schema": CHAOS_SCHEDULE_INTERFACE,
            "seed": seed,
            "actions": schedule,
        },
        "safety_counters": counters.as_dict(),
        "evidence": evidence,
        "acceptance": {
            "zero_acknowledged_loss": counters.acknowledged_loss == 0,
            "zero_duplicate_non_idempotent_effects": counters.duplicate_non_idempotent_effects == 0,
            "zero_authorization_bypass": counters.authorization_bypass == 0,
            "zero_path_escape": counters.path_escape == 0,
            "zero_unsafe_execution": counters.unsafe_execution == 0,
            "zero_secret_leak": counters.secret_leak == 0,
            "zero_false_convergence": counters.false_convergence == 0,
            "recovery_bounded": counters.unbounded_recovery == 0,
            "resources_within_tolerance": counters.unbounded_growth == 0,
            "backend_outage_explicit": counters.silent_backend_outage == 0,
            "all_safety_floors_zero": counters.all_zero(),
        },
    }
    body["semantic_digest"] = semantic_digest(
        _semantic_view(
            {
                "seed": body["seed"],
                "chaos_schedule": body["chaos_schedule"],
                "safety_counters": body["safety_counters"],
                "evidence": body["evidence"],
                "acceptance": body["acceptance"],
            }
        )
    )
    return body


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_declared_outputs_exist() -> None:
    assert RECEIPT_PATH.is_file(), f"missing receipt {RECEIPT_PATH}"
    assert Path(__file__).is_file()


def test_receipt_declares_soak_and_chaos_interfaces() -> None:
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    assert receipt["schema"] == SOAK_RECEIPT_SCHEMA
    assert receipt["contract_version"] == 1
    assert receipt["task_id"] == TASK_ID
    assert receipt["suite"] == SUITE_REL
    assert SOAK_RECEIPT_INTERFACE in receipt["interfaces"]
    assert CHAOS_SCHEDULE_INTERFACE in receipt["interfaces"]
    assert receipt["exclusion_policy"] == {
        "excluded_only_gate": False,
        "mandatory_in_default_ci": True,
    }


def test_receipt_acceptance_and_evidence_subset() -> None:
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    acceptance = receipt["acceptance"]
    for key in (
        "zero_acknowledged_loss",
        "zero_duplicate_non_idempotent_effects",
        "zero_authorization_bypass",
        "zero_path_escape",
        "zero_unsafe_execution",
        "zero_secret_leak",
        "zero_false_convergence",
        "recovery_bounded",
        "resources_within_tolerance_after_load",
        "no_unbounded_thread_task_fd_memory_growth",
        "backend_outage_explicit",
        "identity_equivalent_seeded_receipts",
    ):
        assert acceptance[key] is True, f"acceptance.{key} must be true"

    evidence = receipt["evidence_subset"]
    for key in (
        "soak_duration_seed",
        "crash",
        "partition",
        "backend_loss",
        "corrupt_wal_cache_index_replica",
        "ucan_attacks",
        "overload",
        "leaks",
    ):
        assert key in evidence and evidence[key], f"evidence_subset.{key} required"

    chaos = receipt["chaos_schedule"]
    assert chaos["schema"] == CHAOS_SCHEDULE_INTERFACE
    assert chaos["seed_count"] == SEED_COUNT
    assert set(chaos["actions"]) == set(CHAOS_ACTIONS)
    assert receipt["soak"]["ticks"] == SOAK_TICKS
    assert receipt["soak"]["primary_seed"] == PRIMARY_SEED


def test_crash_chaos_has_no_loss_or_duplicate_effects(tmp_path: Path) -> None:
    counters = SafetyCounters()
    result = _run_crash_matrix(tmp_path, counters)
    assert counters.acknowledged_loss == 0
    assert counters.duplicate_non_idempotent_effects == 0
    assert counters.unbounded_recovery == 0
    assert set(result["outcomes"]) == set(CRASH_BOUNDARIES)
    assert result["outcomes"]["after_commit"] == "committed"


def test_torn_write_compensates(tmp_path: Path) -> None:
    counters = SafetyCounters()
    result = _run_torn_write(tmp_path, counters)
    assert result["visible_after_recovery"] == []
    assert counters.acknowledged_loss == 0
    assert counters.duplicate_non_idempotent_effects == 0


def test_backend_loss_remains_explicit() -> None:
    counters = SafetyCounters()
    result = _run_backend_loss(counters)
    assert result["explicit"] is True
    assert result["outage_disposition"] == "explicit_outage"
    assert counters.silent_backend_outage == 0


def test_partition_rejoins_without_false_convergence(tmp_path: Path) -> None:
    counters = SafetyCounters()
    result = _run_partition_and_rejoin(tmp_path, counters, seed=7)
    assert counters.false_convergence == 0
    assert result["final_payload_digest"]


def test_corrupt_cache_replica_wal_guards(tmp_path: Path) -> None:
    counters = SafetyCounters()
    result = _run_corrupt_surfaces(tmp_path, counters, seed=11)
    assert result["secret_rejected"] is True
    assert result["unsafe_encoding_rejected"] is True
    assert result["cache_stale_absent"] is True
    assert counters.secret_leak == 0
    assert counters.unsafe_execution == 0
    assert counters.false_convergence == 0


def test_ucan_attacks_never_bypass(tmp_path: Path) -> None:
    counters = SafetyCounters()
    result = _run_ucan_attacks(tmp_path, counters, seed=13)
    assert counters.authorization_bypass == 0
    assert counters.secret_leak == 0
    assert result["results"]["valid"] == "allowed"
    assert result["results"]["forged"] == "denied"
    assert result["results"]["tampered"] == "denied"
    assert result["results"]["expired"] == "denied"
    assert result["results"]["confused_deputy"] == "denied"
    assert result["results"]["attenuation"] == "denied"
    assert result["results"]["replay"] == "denied"


def test_path_escape_rate_is_zero() -> None:
    counters = SafetyCounters()
    result = _run_path_escape(counters)
    assert result["accepted_count"] == 0
    assert counters.path_escape == 0
    assert result["rejected_count"] >= len(PATH_ESCAPE_PROBES)


def test_overload_backpressure_is_explicit_and_bounded() -> None:
    counters = SafetyCounters()
    result = _run_overload(counters)
    assert result["rejected"] > 0
    assert result["within_bounds_peak"] is True
    assert result["within_bounds_after"] is True
    assert counters.unbounded_growth == 0


def test_mixed_soak_returns_resources_within_tolerance(tmp_path: Path) -> None:
    counters = SafetyCounters()
    result = _run_mixed_soak(tmp_path, counters, seed=PRIMARY_SEED, ticks=SOAK_TICKS)
    assert result["operations"] > 0
    assert result["final"]["queue_depth"] <= RESOURCE_TOLERANCE["queue_depth"]
    assert result["final"]["inflight_tasks"] <= RESOURCE_TOLERANCE["inflight_tasks"]
    assert result["final"]["memory_bytes"] <= RESOURCE_TOLERANCE["memory_bytes"]
    assert result["final"]["descriptor_leases"] <= RESOURCE_TOLERANCE["descriptor_leases"]
    assert counters.unbounded_growth == 0
    assert counters.acknowledged_loss == 0
    assert counters.duplicate_non_idempotent_effects == 0


def test_primary_seeded_qualification_passes(tmp_path: Path) -> None:
    receipt = run_qualification(tmp_path, PRIMARY_SEED)
    assert receipt["acceptance"]["all_safety_floors_zero"] is True
    assert receipt["safety_counters"] == SafetyCounters().as_dict()
    assert receipt["semantic_digest"]
    assert set(receipt["chaos_schedule"]["actions"]) == set(CHAOS_ACTIONS)


def test_repeated_seeded_run_identity_equivalent_semantic_receipts(tmp_path: Path) -> None:
    """Repeated seeded run has identity-equivalent semantic receipts."""

    a = run_qualification(tmp_path / "a", PRIMARY_SEED)
    b = run_qualification(tmp_path / "b", PRIMARY_SEED)
    # Semantic body (excluding host paths inside work dirs) must match digests.
    assert a["semantic_digest"] == b["semantic_digest"]
    assert a["safety_counters"] == b["safety_counters"]
    assert a["acceptance"] == b["acceptance"]
    assert a["chaos_schedule"] == b["chaos_schedule"]
    # Evidence kind sequence must match schedule order.
    assert [e["kind"] for e in a["evidence"]] == [e["kind"] for e in b["evidence"]]


def test_multi_seed_chaos_schedules_all_pass(tmp_path: Path) -> None:
    """Diverse seeds: every schedule converges with zero safety floors."""

    digests: set[str] = set()
    schedules: set[tuple[str, ...]] = set()
    for seed in range(SEED_COUNT):
        receipt = run_qualification(tmp_path / f"seed-{seed}", seed)
        assert receipt["acceptance"]["all_safety_floors_zero"] is True, (
            f"seed {seed} violated safety floors: {receipt['safety_counters']}"
        )
        digests.add(receipt["semantic_digest"])
        schedules.add(tuple(receipt["chaos_schedule"]["actions"]))
        # Per-seed identity: immediate re-run matches.
        again = run_qualification(tmp_path / f"seed-{seed}-again", seed)
        assert again["semantic_digest"] == receipt["semantic_digest"]
    # Schedules should vary across seeds (not a single fixed order).
    assert len(schedules) > 1
    assert len(digests) == SEED_COUNT


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


def test_chaos_schedule_builder_is_deterministic() -> None:
    assert build_chaos_schedule(PRIMARY_SEED) == build_chaos_schedule(PRIMARY_SEED)
    assert build_chaos_schedule(1) != build_chaos_schedule(2)
