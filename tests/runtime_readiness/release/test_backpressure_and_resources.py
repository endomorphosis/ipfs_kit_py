"""KITA-044: bounded backpressure and resource gates for optimized hot paths.

Covers:

* ``BackpressureController@1`` hard bounds on queues/memory/descriptors/tasks/threads
* explicit overload dispositions (backpressure / deadline / cancellation)
* fairness and clean shutdown
* settings freeze (fsync/auth/integrity/replica/consistency) identity
* presence of production-bound ``optimized_results.json`` evidence (2× gate is
  owned by the protected ``test_production_performance_gate``)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
BENCH_DIR = PACKAGE_ROOT / "benchmarks" / "runtime_readiness"
OPTIMIZED_RESULTS = BENCH_DIR / "optimized_results.json"
PERF_MODULE = PACKAGE_ROOT / "ipfs_kit_py" / "core" / "performance.py"

import sys

if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))
if str(BENCH_DIR) not in sys.path:
    sys.path.insert(0, str(BENCH_DIR))

from ipfs_kit_py.core.performance import (  # noqa: E402
    BACKPRESSURE_CONTROLLER_SCHEMA,
    MIN_THROUGHPUT_MULTIPLIER,
    OPTIMIZED_RESULTS_SCHEMA,
    AdmissionDecision,
    BackpressureController,
    BackpressureError,
    BackpressureReason,
    CancellationToken,
    ControllerBounds,
    DurabilityIntegritySettings,
    HotPathGate,
    compare_settings,
    default_reference_settings,
    get_hot_path_controller,
    reset_hot_path_controller,
    settings_fingerprint,
)


# ---------------------------------------------------------------------------
# Artifact presence
# ---------------------------------------------------------------------------


def test_declared_outputs_exist() -> None:
    assert PERF_MODULE.is_file(), f"missing {PERF_MODULE}"
    assert OPTIMIZED_RESULTS.is_file(), f"missing {OPTIMIZED_RESULTS}"


def test_optimized_results_is_production_harness_evidence() -> None:
    doc = json.loads(OPTIMIZED_RESULTS.read_text(encoding="utf-8"))
    assert doc["schema"] == OPTIMIZED_RESULTS_SCHEMA
    assert doc["schema"] == "RuntimeBenchmarkHarness@1"
    assert "raw_samples" in doc and doc["raw_samples"]
    assert "production_bindings" in doc and doc["production_bindings"]
    assert doc["identity"]["sample_timer"] == "protected_timer.monotonic_sample_timer@1"
    # Complete raw timings required for the protected 2× recompute.
    total = 0
    for paths in doc["raw_samples"].values():
        for receipt in paths.values():
            durations = receipt.get("committed_seconds") or []
            assert durations
            total += len(durations)
    assert total > 0


# ---------------------------------------------------------------------------
# Settings freeze
# ---------------------------------------------------------------------------


def test_settings_fingerprint_stable_across_optimization() -> None:
    before = default_reference_settings()
    after = default_reference_settings()
    cmp = compare_settings(before, after)
    assert cmp["identical"] is True
    assert cmp["mismatches"] == []
    assert cmp["before_fingerprint"] == cmp["after_fingerprint"]


def test_settings_fingerprint_detects_auth_drift() -> None:
    before = default_reference_settings()
    after = DurabilityIntegritySettings(
        durability_mode=before.durability_mode,
        fsync_policy=before.fsync_policy,
        auth_required=False,
        integrity_checks=before.integrity_checks,
        replication_factor=before.replication_factor,
        consistency_level=before.consistency_level,
        wal_acknowledgement=before.wal_acknowledgement,
        checksum_algorithm=before.checksum_algorithm,
    )
    bad = compare_settings(before, after)
    assert bad["identical"] is False
    assert "auth_required" in bad["mismatches"]


def test_hot_path_controller_preserves_settings() -> None:
    ctrl = reset_hot_path_controller()
    assert ctrl.settings.auth_required is True
    assert ctrl.settings.integrity_checks is True
    assert ctrl.settings.replication_factor == 1
    assert ctrl.settings.consistency_level == "commit_barrier"
    assert ctrl.settings.fsync_policy == "memory_sync_barrier"
    assert settings_fingerprint(ctrl.settings) == settings_fingerprint(
        default_reference_settings()
    )


# ---------------------------------------------------------------------------
# BackpressureController@1
# ---------------------------------------------------------------------------


def test_backpressure_controller_schema_alias() -> None:
    ctrl = BackpressureController()
    assert ctrl.schema == BACKPRESSURE_CONTROLLER_SCHEMA
    assert "backpressure-controller@1" in ctrl.schema


def test_queue_memory_task_descriptor_thread_bounds() -> None:
    bounds = ControllerBounds(
        max_queue_items=2,
        max_inflight_tasks=2,
        max_worker_threads=2,
        max_memory_bytes=64,
        max_descriptor_leases=2,
        max_fairness_classes=4,
    )
    ctrl = BackpressureController(bounds=bounds)
    admitted = 0
    rejected = 0
    for i in range(8):
        d = ctrl.try_admit(
            payload_bytes=16,
            fairness_class=f"t{i % 2}",
            lease_descriptor=True,
            enqueue=True,
        )
        if d.admitted:
            admitted += 1
        else:
            rejected += 1
            assert d.state == "backpressure"
            assert d.reason in {
                BackpressureReason.QUEUE_FULL.value,
                BackpressureReason.TASK_LIMIT.value,
                BackpressureReason.MEMORY_EXHAUSTED.value,
                BackpressureReason.DESCRIPTOR_LIMIT.value,
                BackpressureReason.FAIRNESS_THROTTLED.value,
            }
    assert admitted > 0
    assert rejected > 0
    snap = ctrl.snapshot()
    assert snap.within_bounds() is True
    assert snap.queue_depth <= bounds.max_queue_items
    assert snap.inflight_tasks <= bounds.max_inflight_tasks
    assert snap.memory_bytes <= bounds.max_memory_bytes
    assert snap.descriptor_leases <= bounds.max_descriptor_leases

    assert ctrl.acquire_worker_thread() is True
    assert ctrl.acquire_worker_thread() is True
    assert ctrl.acquire_worker_thread() is False
    ctrl.release_worker_thread()
    assert ctrl.acquire_worker_thread() is True
    snap2 = ctrl.snapshot()
    assert snap2.worker_threads <= bounds.max_worker_threads
    assert snap2.within_bounds() is True


def test_overload_returns_explicit_backpressure_not_silent_drop() -> None:
    ctrl = BackpressureController(
        bounds=ControllerBounds(max_queue_items=1, max_inflight_tasks=2, max_memory_bytes=1024)
    )
    assert ctrl.try_admit(payload_bytes=1, enqueue=True).admitted is True
    denied = ctrl.try_admit(payload_bytes=1, enqueue=True)
    assert denied.admitted is False
    assert denied.state == "backpressure"
    assert denied.reason == BackpressureReason.QUEUE_FULL.value


def test_deadline_exceeded_is_explicit() -> None:
    ctrl = BackpressureController()
    past = int(time.time() * 1000) - 5_000
    d = ctrl.try_admit(payload_bytes=1, deadline_unix_ms=past)
    assert d.admitted is False
    assert d.state == "deadline_exceeded"
    assert d.reason == BackpressureReason.DEADLINE_EXCEEDED.value


def test_cancellation_is_explicit() -> None:
    ctrl = BackpressureController()
    token = CancellationToken()
    token.cancel()
    d = ctrl.try_admit(payload_bytes=1, cancel=token)
    assert d.admitted is False
    assert d.state == "cancelled"
    assert d.reason == BackpressureReason.CANCELLED.value


def test_fairness_round_robin_across_classes() -> None:
    ctrl = BackpressureController(
        bounds=ControllerBounds(max_queue_items=32, max_inflight_tasks=32, max_memory_bytes=1 << 20)
    )
    for cls in ("a", "b", "c"):
        for _ in range(4):
            assert ctrl.try_admit(payload_bytes=1, fairness_class=cls, enqueue=True).admitted
    served: list[str] = []
    while True:
        d = ctrl.pop_next_fair()
        if d is None:
            break
        served.append(d.fairness_class)
        ctrl.complete(d.ticket_id or 0, payload_bytes=1)
    # Every class should be served; order should interleave (not all of one first).
    assert set(served) == {"a", "b", "c"}
    # First three dequeues should span three distinct classes under pure RR.
    assert len(set(served[:3])) == 3


def test_clean_shutdown_rejects_new_admission() -> None:
    ctrl = BackpressureController()
    ctrl.begin_shutdown()
    d = ctrl.try_admit(payload_bytes=1)
    assert d.admitted is False
    assert d.reason == BackpressureReason.SHUTTING_DOWN.value
    drained = ctrl.cancel_all()
    assert drained >= 0
    assert ctrl.snapshot().within_bounds() is True


def test_hot_path_gate_raises_on_overload() -> None:
    ctrl = BackpressureController(
        bounds=ControllerBounds(max_inflight_tasks=1, max_queue_items=1, max_memory_bytes=16)
    )
    with HotPathGate(payload_bytes=8, controller=ctrl):
        with pytest.raises(BackpressureError) as ei:
            with HotPathGate(payload_bytes=8, controller=ctrl):
                pass
        assert ei.value.reason in {
            BackpressureReason.TASK_LIMIT,
            BackpressureReason.MEMORY_EXHAUSTED,
        }


def test_process_global_controller_is_bounded() -> None:
    ctrl = reset_hot_path_controller()
    assert ctrl is get_hot_path_controller()
    snap = ctrl.snapshot()
    assert snap.within_bounds() is True


# ---------------------------------------------------------------------------
# Production surface integration (smoke)
# ---------------------------------------------------------------------------


def test_wal_writer_uses_bounded_group_commit_without_idle_delay() -> None:
    import os
    import tempfile
    import time as _time
    from pathlib import Path as _Path

    from ipfs_kit_py.core.wal.contracts import (
        WALAcknowledgementMode,
        WALRecordKind,
    )
    from ipfs_kit_py.core.wal.writer import GroupCommitPolicy, WALWriter

    assert GroupCommitPolicy().max_delay_seconds == 0.0
    tmp = tempfile.mkdtemp(
        dir="/dev/shm" if os.path.isdir("/dev/shm") and os.access("/dev/shm", os.W_OK) else None
    )
    writer = WALWriter(_Path(tmp) / "wal", policy=GroupCommitPolicy())
    try:
        t0 = _time.perf_counter()
        for i in range(20):
            result = writer.append(
                WALRecordKind.MUTATE,
                acknowledgement_mode=WALAcknowledgementMode.WAL_FSYNC_PARENT,
                record_key=f"k{i}",
            )
            assert result.durable is True
        elapsed = _time.perf_counter() - t0
        # 20 durable appends must not pay a 10ms artificial group-commit sleep each.
        assert elapsed < 1.0, f"WAL hot path too slow: {elapsed:.3f}s for 20 appends"
    finally:
        writer.close()


def test_vfs_execute_admits_under_hot_path_gate() -> None:
    from ipfs_kit_py.core.vfs.contracts import VFSEntryKind
    from ipfs_kit_py.core.vfs.service import (
        CanonicalVFSService,
        InMemoryVFSStorage,
        make_op,
    )

    storage = InMemoryVFSStorage()
    storage.seed("a", kind=VFSEntryKind.FILE, content=b"hello")
    vfs = CanonicalVFSService(storage)
    outcome = vfs.execute(make_op("stat", operation_id="t1", path="a"))
    assert outcome.result.success is True


def test_multiplier_floor_constant() -> None:
    assert MIN_THROUGHPUT_MULTIPLIER == 2.0
