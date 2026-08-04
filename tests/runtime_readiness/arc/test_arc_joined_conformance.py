"""Joined ARC conformance coverage for coherence, recovery, and bounded cost.

The trace corpus is generated from deterministic seeds so this test is both a
large differential run and a small, reviewable source artifact.  It exercises
the synchronized implementation, not a test-only cache.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from threading import Event
import time
import tracemalloc

import pytest

from ipfs_kit_py.arc_cache import CacheBinding, GenerationBoundARC
from ipfs_kit_py.cache.arc.cache import AdaptiveReplacementCache
from ipfs_kit_py.cache.arc.concurrency import FillStatus, SingleFlightARC
from ipfs_kit_py.cache.arc.contracts import ARCConfig
from ipfs_kit_py.cache.arc.reference import ARCReferenceModel, minimal_trace_strategy
from ipfs_kit_py.core.replication.contracts import BackendCapability, BackendInventory, ReplicaPolicy
from ipfs_kit_py.core.replication.integrity import IntegrityVerifier, ReplicaContent
from ipfs_kit_py.core.replication.reconciler import ReconciliationOutcome, ReplicaReconciler
from ipfs_kit_py.core.vfs.contracts import VFSOperationKind
from ipfs_kit_py.core.vfs.service import CanonicalVFSService, InMemoryVFSStorage, VFSExecuteRequest, make_op
from ipfs_kit_py.core.wal.coordinator import WALTransactionCoordinator, WALTransactionCrash


TRACE_SEED_COUNT = 2_048
CONCURRENT_SCHEDULE_COUNT = 256
OPERATIONS_PER_CONCURRENT_SCHEDULE = 8
MIN_HIT_MISS_SPEEDUP = 2.5
MAX_MEMORY_OVERHEAD_BYTES = 512 * 1024


def _binding(
    content_id: str,
    version: str,
    *,
    generation: str,
    policy: str = "public",
) -> CacheBinding:
    return CacheBinding(
        content_id=content_id,
        version=version,
        namespace="joined-conformance",
        policy=policy,
        serializer="bytes@1",
        generation=generation,
    )


def _get(cache: GenerationBoundARC, binding: CacheBinding) -> bytes | None:
    return cache.get(binding, authorize=lambda _: True, consistent=lambda _: True)


def test_thousands_of_seeded_traces_match_reference_and_preserve_every_invariant() -> None:
    """A generated corpus catches list/accounting errors without golden dumps."""

    digest = hashlib.sha256()
    for seed in range(TRACE_SEED_COUNT):
        config, operations = minimal_trace_strategy(seed, max_ops=32)
        reference = ARCReferenceModel(config)
        actual = AdaptiveReplacementCache(config)

        expected_trace = reference.run_trace(operations)
        actual_trace = actual.run_trace(operations)
        assert actual_trace == expected_trace, f"differential mismatch for seed {seed}"
        actual.assert_invariants()
        snapshot = actual.snapshot()
        assert snapshot.current_size == snapshot.t1_size + snapshot.t2_size
        assert snapshot.current_size <= config.capacity_bytes
        assert set(snapshot.t1_keys).isdisjoint(snapshot.t2_keys)
        assert set(snapshot.b1_keys).isdisjoint(snapshot.b2_keys)
        assert not (set(snapshot.t1_keys) | set(snapshot.t2_keys)) & (
            set(snapshot.b1_keys) | set(snapshot.b2_keys)
        )
        digest.update(repr((seed, actual_trace, snapshot)).encode("utf-8"))

    # This makes accidentally reducing the generated corpus observable while
    # deliberately not pinning implementation-private ordering as a fixture.
    assert TRACE_SEED_COUNT >= 2_000
    assert digest.digest() != b"\0" * hashlib.sha256().digest_size


def test_thousands_of_concurrent_operations_remain_linearizable_and_invariant_safe() -> None:
    """Independent writes make every legal lock ordering converge identically."""

    total_operations = 0
    with ThreadPoolExecutor(max_workers=OPERATIONS_PER_CONCURRENT_SCHEDULE) as executor:
        for schedule in range(CONCURRENT_SCHEDULE_COUNT):
            config = ARCConfig(
                capacity_bytes=16 * 1024,
                max_live_entries=OPERATIONS_PER_CONCURRENT_SCHEDULE + 2,
                max_ghost_entries=OPERATIONS_PER_CONCURRENT_SCHEDULE + 2,
            )
            cache = AdaptiveReplacementCache(config)
            start = Event()
            rows = [
                (f"schedule:{schedule}:key:{offset}", f"value:{schedule}:{offset}".encode())
                for offset in range(OPERATIONS_PER_CONCURRENT_SCHEDULE)
            ]

            def put_after_start(key: str, value: bytes) -> tuple[str, bool]:
                assert start.wait(timeout=5)
                return key, cache.put(key, value)

            futures = [executor.submit(put_after_start, key, value) for key, value in rows]
            start.set()
            assert dict(future.result(timeout=5) for future in futures) == {
                key: True for key, _ in rows
            }
            cache.assert_invariants()
            assert {key for key, _ in rows} == set(cache.snapshot().t1_keys) | set(cache.snapshot().t2_keys)
            for key, value in rows:
                assert cache.get(key) == value
            cache.assert_invariants()
            total_operations += len(rows)

    assert total_operations >= 2_000


def test_restart_identity_and_checksum_corruption_rejection_are_atomic(tmp_path: Path) -> None:
    source = GenerationBoundARC(ARCConfig(capacity_bytes=32 * 1024, max_live_entries=64))
    bindings = tuple(
        _binding(f"cid:restart:{index}", f"version:{index}", generation="restart-1")
        for index in range(24)
    )
    for index, binding in enumerate(bindings):
        assert source.put(binding, f"payload:{index}".encode())

    state = tmp_path / "arc-restart.json"
    assert source.persist(state)

    restored = GenerationBoundARC(ARCConfig(capacity_bytes=32 * 1024, max_live_entries=64))
    assert restored.restore(state)
    for index, binding in enumerate(bindings):
        assert _get(restored, binding) == f"payload:{index}".encode()

    # A checksum-validity failure must be a safe miss and retain the target's
    # current live state; it must never partially import an entry.
    resident = _binding("cid:resident", "version:resident", generation="restart-1")
    target = GenerationBoundARC(ARCConfig(capacity_bytes=32 * 1024, max_live_entries=64))
    assert target.put(resident, b"resident")
    envelope = json.loads(state.read_text(encoding="utf-8"))
    envelope["entries"][0]["binding"]["version"] = "tampered-version"
    state.write_text(json.dumps(envelope), encoding="utf-8")
    assert not target.restore(state)
    assert _get(target, resident) == b"resident"
    assert target.metrics().persistence_corrupt == 1


class _ReplicaBackend:
    """Small in-memory boundary implementing the reconciler's backend protocol."""

    def __init__(self, backend_id: str, objects: dict[str, ReplicaContent] | None = None) -> None:
        self.backend_id = backend_id
        self.objects = dict(objects or {})

    def read(self, content_ref: str) -> ReplicaContent | None:
        return self.objects.get(content_ref)

    def write(self, content_ref: str, content: ReplicaContent, *, idempotency_key: str) -> None:
        self.objects[content_ref] = content

    def delete(self, content_ref: str, *, idempotency_key: str) -> None:
        self.objects.pop(content_ref, None)


def test_vfs_wal_index_rebuild_and_replica_events_change_only_exact_bindings(tmp_path: Path) -> None:
    """Project real lifecycle records to ARC identity changes and check scope."""

    cache = GenerationBoundARC(ARCConfig(capacity_bytes=32 * 1024, max_live_entries=64))
    unrelated = _binding("cid:unrelated", "version:1", generation="g1")
    assert cache.put(unrelated, b"unrelated")

    vfs = CanonicalVFSService(InMemoryVFSStorage(), clock=lambda: 1_700_000_000_000)
    directory = vfs.execute(
        make_op(VFSOperationKind.MKDIR, operation_id="joined-mkdir", path="objects")
    )
    assert directory.success
    created = vfs.execute(
        make_op(VFSOperationKind.CREATE, operation_id="joined-create", path="objects/item"),
        VFSExecuteRequest(payload=b"vfs-one"),
    )
    assert created.success
    old = _binding(
        created.result.resulting_content_cid,
        created.result.resulting_version_cid,
        generation="vfs-1",
    )
    assert cache.put(old, b"cached-vfs-one")

    replaced = vfs.execute(
        make_op(VFSOperationKind.REPLACE, operation_id="joined-replace", path="objects/item"),
        VFSExecuteRequest(payload=b"vfs-two"),
    )
    assert replaced.success
    # A VFS update invalidates the exact old version; rebuilding the lookup
    # index then admits only the canonical version returned by the service.
    assert cache.invalidate(old) == 1
    rebuilt = _binding(
        replaced.result.resulting_content_cid,
        replaced.result.resulting_version_cid,
        generation="vfs-2",
    )
    assert cache.put(rebuilt, b"cached-vfs-two")
    assert _get(cache, old) is None
    assert _get(cache, rebuilt) == b"cached-vfs-two"
    assert _get(cache, unrelated) == b"unrelated"

    deleted = vfs.execute(make_op(VFSOperationKind.DELETE, operation_id="joined-delete", path="objects/item"))
    assert deleted.success
    assert cache.invalidate(rebuilt) == 1
    assert _get(cache, rebuilt) is None
    assert _get(cache, unrelated) == b"unrelated"

    # A committed WAL record is replayed after a crash onto a fresh in-memory
    # index.  The replay callback has the same exact-binding invalidation.
    wal_binding = _binding("cid:wal", "version:1", generation="wal-1")
    replay_cache = GenerationBoundARC(ARCConfig(capacity_bytes=32 * 1024, max_live_entries=64))
    assert replay_cache.put(wal_binding, b"stale-after-crash")

    def crash_after_commit(boundary: str, _transaction_id: str) -> None:
        if boundary == "after_commit":
            raise WALTransactionCrash(boundary)

    coordinator = WALTransactionCoordinator(tmp_path / "wal", crash_injector=crash_after_commit)
    try:
        with pytest.raises(WALTransactionCrash):
            coordinator.execute(
                {"kind": "cache-invalidate", "binding": wal_binding.to_dict()},
                lambda: None,
                lambda: None,
                transaction_id="joined-wal-transaction",
                effect_id="joined-wal-effect",
            )
    finally:
        coordinator.close()
    recovered = WALTransactionCoordinator(tmp_path / "wal")
    try:
        assert recovered.recover(
            replay_effect=lambda _intent, _effect_id: replay_cache.invalidate(wal_binding),
            rollback_effect=lambda _intent, _effect_id: None,
        ) == {"replayed": 1, "rolled_back": 0}
    finally:
        recovered.close()
    assert _get(replay_cache, wal_binding) is None

    # A converged replica version is the only version retained after its index
    # is rebuilt.  The reconciler verifies bytes and version before reporting
    # convergence, so this is not a provider-declared metadata shortcut.
    content_ref = "cid:replica-object"
    authoritative = ReplicaContent(b"replica-payload", "replica-v2")
    backends = {
        "replica-a": _ReplicaBackend("replica-a", {content_ref: authoritative}),
        "replica-b": _ReplicaBackend("replica-b"),
    }
    inventory = BackendInventory(
        "joined-inventory",
        tuple(BackendCapability(name, f"domain-{index}", 4096) for index, name in enumerate(backends)),
    )
    receipt = ReplicaReconciler(backends).reconcile(
        content_ref=content_ref,
        content_size_bytes=len(authoritative.payload),
        expected_digest=IntegrityVerifier().digest(authoritative.payload),
        expected_version_id=authoritative.version_id,
        policy=ReplicaPolicy("joined-policy", 1, 2, 2, 2),
        inventory=inventory,
    )
    assert receipt.outcome is ReconciliationOutcome.CONVERGED
    stale_replica = _binding(content_ref, "replica-v1", generation="replica-v1")
    converged_replica = _binding(content_ref, "replica-v2", generation="replica-v2")
    assert cache.put(stale_replica, b"stale-replica")
    assert cache.advance_generation(content_ref, "replica-v2", namespace="joined-conformance") == 1
    assert cache.put(converged_replica, authoritative.payload)
    assert _get(cache, stale_replica) is None
    assert _get(cache, converged_replica) == authoritative.payload
    assert _get(cache, unrelated) == b"unrelated"


def _expensive_cold_value() -> bytes:
    value = b"joined-cold-path"
    for _ in range(256):
        value = hashlib.sha256(value).digest()
    return value


def _per_operation_seconds(iterations: int, operation) -> float:
    started = time.perf_counter()
    for _ in range(iterations):
        operation()
    return (time.perf_counter() - started) / iterations


def test_hit_miss_speedup_memory_ceiling_and_cold_failure_visibility() -> None:
    cache = AdaptiveReplacementCache(
        ARCConfig(capacity_bytes=128 * 1024, max_live_entries=1024, max_ghost_entries=1024)
    )
    flights = SingleFlightARC(cache)
    assert flights.get_or_fill_result("benchmark:hot", _expensive_cold_value).status is FillStatus.FILLED

    hit_seconds = _per_operation_seconds(
        128, lambda: flights.get_or_fill_result("benchmark:hot", _expensive_cold_value)
    )
    counter = 0

    def cold() -> None:
        nonlocal counter
        result = flights.get_or_fill_result(f"benchmark:cold:{counter}", _expensive_cold_value)
        counter += 1
        assert result.status is FillStatus.FILLED

    cold_seconds = _per_operation_seconds(16, cold)
    assert cold_seconds / hit_seconds >= MIN_HIT_MISS_SPEEDUP

    # A hit must avoid a filler, while a genuine cold-path exception must stay
    # visible as FAILED instead of being disguised as a cache miss or success.
    assert flights.get_or_fill_result(
        "benchmark:hot", lambda: (_ for _ in ()).throw(AssertionError("hit called filler"))
    ).status is FillStatus.HIT
    failed = flights.get_or_fill_result(
        "benchmark:failure", lambda: (_ for _ in ()).throw(RuntimeError("cold failure"))
    )
    assert failed.status is FillStatus.FAILED
    assert isinstance(failed.error, RuntimeError)

    tracemalloc.start()
    try:
        baseline = tracemalloc.get_traced_memory()[0]
        measured = AdaptiveReplacementCache(
            ARCConfig(capacity_bytes=128 * 1024, max_live_entries=256, max_ghost_entries=256)
        )
        payload_bytes = 0
        for index in range(128):
            value = bytes([index]) * 256
            payload_bytes += len(value)
            assert measured.put(f"memory:{index}", value)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak - baseline - payload_bytes <= MAX_MEMORY_OVERHEAD_BYTES


def test_conformance_receipt_has_no_excluded_only_gate() -> None:
    receipt = Path(__file__).parents[3] / "docs/runtime_readiness/arc_conformance.json"
    specification = json.loads(receipt.read_text(encoding="utf-8"))
    assert specification["exclusion_policy"] == {
        "excluded_only_gate": False,
        "mandatory_in_default_ci": True,
    }
    assert specification["randomized_invariants"]["seed_count"] >= TRACE_SEED_COUNT
    assert specification["performance"]["minimum_hit_miss_speedup"] >= MIN_HIT_MISS_SPEEDUP
    assert specification["performance"]["maximum_memory_overhead_bytes"] <= MAX_MEMORY_OVERHEAD_BYTES
