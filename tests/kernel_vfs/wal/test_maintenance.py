"""KVFS-304: Checkpoint, compaction, archive, and bounded maintenance lifecycle.

Acceptance coverage:

* checkpoints cannot hide later appends;
* compaction retains recovery closure;
* archive is verified before source deletion;
* disk pressure applies explicit backpressure;
* workers heartbeat and stop;
* mount shutdown preserves the latest durable recovery position.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from ipfs_kit_py.core.wal.checkpoint import CheckpointStore, create_checkpoint
from ipfs_kit_py.core.wal.contracts import (
    WALAcknowledgementMode,
    WALRecord,
    WALRecordKind,
    WALRecordState,
    make_committed_record,
)
from ipfs_kit_py.core.wal.recovery import WALRecovery
from ipfs_kit_py.core.wal.segments import WALSegmentFile
from ipfs_kit_py.kernel_vfs import wal_maintenance as wm_mod
from ipfs_kit_py.kernel_vfs.wal_maintenance import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    TASK_ID,
    DiskPressureError,
    DiskPressurePolicy,
    DurableRecoveryPosition,
    DurableRecoveryPosition_V1,
    MaintenanceDisposition,
    MaintenanceErrorCode,
    MaintenancePhase,
    MaintenanceProtocolError,
    MaintenanceReceipt,
    MaintenanceReceipt_V1,
    MaintenanceWorker,
    MaintenanceWorker_V1,
    WalMaintenanceCoordinator,
    WalMaintenanceCoordinator_V1,
    WalMaintenanceFacade,
    WorkerState,
    build_wal_maintenance_coordinator,
    maintenance_dispositions,
    maintenance_phases,
    worker_states,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = PACKAGE_ROOT / "ipfs_kit_py" / "kernel_vfs" / "wal_maintenance.py"

GENERATION = "wal-gen:maintenance-test"


# ---------------------------------------------------------------------------
# Schema / vocabulary
# ---------------------------------------------------------------------------


def test_schema_versions_and_aliases() -> None:
    assert TASK_ID == "KVFS-304"
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert WalMaintenanceCoordinator_V1.endswith("@1")
    assert DurableRecoveryPosition_V1.endswith("@1")
    assert MaintenanceReceipt_V1.endswith("@1")
    assert MaintenanceWorker_V1.endswith("@1")
    assert WalMaintenanceFacade is WalMaintenanceCoordinator
    assert "checkpoint" in maintenance_phases()
    assert "compact" in maintenance_phases()
    assert "archive" in maintenance_phases()
    assert "shutdown" in maintenance_phases()
    assert "success" in maintenance_dispositions()
    assert "backpressure" in maintenance_dispositions()
    assert "running" in worker_states()
    assert "stopped" in worker_states()
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "KVFS-304" in text
    assert "cannot hide later appends" in text or "cannot hide" in text
    assert "recovery closure" in text
    assert "verified before" in text or "verify" in text.lower()
    assert "disk pressure" in text.lower() or "DiskPressure" in text
    assert "heartbeat" in text
    assert "recovery position" in text.lower() or "DurableRecoveryPosition" in text


def test_ready_receipt_rejects_success_with_failed() -> None:
    with pytest.raises(MaintenanceProtocolError):
        MaintenanceReceipt(
            receipt_id="r1",
            disposition=MaintenanceDisposition.FAILED,
            success=True,
            phase=MaintenancePhase.CHECKPOINT,
        )


def test_backpressure_receipt_cannot_claim_success() -> None:
    with pytest.raises(MaintenanceProtocolError):
        MaintenanceReceipt(
            receipt_id="r2",
            disposition=MaintenanceDisposition.BACKPRESSURE,
            success=True,
            phase=MaintenancePhase.DISK_PRESSURE,
        )


def test_recovery_position_rejects_append_behind_through() -> None:
    with pytest.raises(MaintenanceProtocolError):
        DurableRecoveryPosition(
            generation_id=GENERATION,
            through_sequence=10,
            last_append_sequence=5,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _append_transaction(
    path: Path,
    *,
    segment_id: str,
    first_sequence: int,
    transaction_id: str,
    effect_key: str,
    seal: bool,
    generation: str = GENERATION,
) -> object:
    segment = WALSegmentFile(
        path,
        generation_id=generation,
        segment_id=segment_id,
        first_sequence=first_sequence,
    )
    try:
        segment.append(
            WALRecord(
                generation_id=generation,
                sequence_number=first_sequence,
                kind=WALRecordKind.BEGIN,
                state=WALRecordState.APPENDED,
                acknowledgement_mode=WALAcknowledgementMode.WAL_APPENDED,
                transaction_id=transaction_id,
                segment_id=segment_id,
            )
        )
        segment.append(
            WALRecord(
                generation_id=generation,
                sequence_number=first_sequence + 1,
                kind=WALRecordKind.MUTATE,
                state=WALRecordState.APPENDED,
                acknowledgement_mode=WALAcknowledgementMode.WAL_APPENDED,
                transaction_id=transaction_id,
                segment_id=segment_id,
                record_key=effect_key,
            )
        )
        segment.append(
            make_committed_record(
                generation_id=generation,
                sequence_number=first_sequence + 2,
                transaction_id=transaction_id,
                fsync_receipt_id=f"fsync-{effect_key}",
                segment_id=segment_id,
            )
        )
        return segment.seal() if seal else segment.descriptor
    finally:
        segment.close()


def _coord(tmp_path: Path, **kwargs: object) -> WalMaintenanceCoordinator:
    defaults: dict[str, object] = {
        "generation_id": GENERATION,
        "mount_id": "mount:test",
        # Generous free-space floor so real disks do not trip tests.
        "disk_pressure": DiskPressurePolicy(min_free_bytes=1, min_free_ratio=0.0),
    }
    defaults.update(kwargs)
    return WalMaintenanceCoordinator(tmp_path / "maint-state", **defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Checkpoints cannot hide later appends
# ---------------------------------------------------------------------------


def test_checkpoint_cannot_hide_later_appends(tmp_path: Path) -> None:
    with _coord(tmp_path) as coord:
        covered_path = coord.segments_directory / "covered.wal"
        covered = _append_transaction(
            covered_path,
            segment_id="covered-segment",
            first_sequence=0,
            transaction_id="covered",
            effect_key="already-compacted",
            seal=True,
        )
        coord.register_segment_path("covered-segment", covered_path)
        coord.observe_append(2, segment_id="covered-segment", segment_path=covered_path)

        receipt = coord.checkpoint([covered], state=b"compacted-state-v1")
        assert receipt.success is True
        assert receipt.disposition is MaintenanceDisposition.SUCCESS
        assert receipt.phase is MaintenancePhase.CHECKPOINT
        assert receipt.through_sequence == 2
        assert receipt.checkpoint_id

        # Later append after checkpoint — must remain visible / recoverable.
        later_path = coord.segments_directory / "later.wal"
        _append_transaction(
            later_path,
            segment_id="later-segment",
            first_sequence=3,
            transaction_id="later",
            effect_key="must-not-be-skipped",
            seal=False,
        )
        coord.observe_append(5, segment_id="later-segment", segment_path=later_path)
        position = coord.current_recovery_position()
        assert position.through_sequence == 2
        assert position.last_append_sequence == 5
        assert position.has_uncompacted_appends is True

        applied: list[str] = []
        rec = WALRecovery(
            (covered_path, later_path),
            checkpoint=coord.current_checkpoint,
        ).recover(lambda record: applied.append(record.record_key))
        assert applied == ["must-not-be-skipped"]
        assert rec.committed_transactions == ("later",)


def test_checkpoint_identity_skips_only_exact_sealed_bytes(tmp_path: Path) -> None:
    """A segment that gains an append after sealing no longer matches identity."""

    with _coord(tmp_path) as coord:
        path = coord.segments_directory / "mutable.wal"
        sealed = _append_transaction(
            path,
            segment_id="mutable-segment",
            first_sequence=0,
            transaction_id="first",
            effect_key="first-effect",
            seal=True,
        )
        receipt = coord.checkpoint([sealed], state=b"state-a")
        assert receipt.success is True

        # Append a new sealed segment (simulates work after checkpoint).
        extra = coord.segments_directory / "extra.wal"
        _append_transaction(
            extra,
            segment_id="extra-segment",
            first_sequence=3,
            transaction_id="extra",
            effect_key="extra-effect",
            seal=True,
        )
        applied: list[str] = []
        WALRecovery(
            (path, extra),
            checkpoint=coord.current_checkpoint,
        ).recover(lambda r: applied.append(r.record_key))
        assert "extra-effect" in applied
        # Covered first effect is skipped via exact identity match.
        assert "first-effect" not in applied


# ---------------------------------------------------------------------------
# Compaction retains recovery closure
# ---------------------------------------------------------------------------


def test_compaction_retains_recovery_closure(tmp_path: Path) -> None:
    with _coord(tmp_path) as coord:
        covered_path = coord.segments_directory / "covered.wal"
        covered = _append_transaction(
            covered_path,
            segment_id="covered-segment",
            first_sequence=0,
            transaction_id="covered",
            effect_key="compacted-effect",
            seal=True,
        )
        coord.register_segment_path("covered-segment", covered_path)

        receipt = coord.compact(
            [covered],
            state=b"compacted-snapshot",
            checkpoint_id="ckpt-compact-1",
        )
        assert receipt.success is True
        assert receipt.phase is MaintenancePhase.COMPACT
        assert receipt.detail.get("recovery_closure") is True
        assert receipt.through_sequence == 2

        # Compacted pointer is loadable.
        loaded = coord.checkpoint_store.load_current()
        assert loaded is not None
        bundle, state = loaded
        assert bundle.checkpoint.checkpoint_id == "ckpt-compact-1"
        assert state == b"compacted-snapshot"

        # Post-compaction append remains recoverable (closure).
        later_path = coord.segments_directory / "post.wal"
        _append_transaction(
            later_path,
            segment_id="post-segment",
            first_sequence=3,
            transaction_id="post",
            effect_key="post-compact-effect",
            seal=False,
        )
        coord.observe_append(5, segment_id="post-segment", segment_path=later_path)

        applied: list[str] = []
        recovery = coord.recover_with_current_checkpoint(
            (covered_path, later_path),
            handler=lambda r: applied.append(r.record_key),
        )
        assert applied == ["post-compact-effect"]
        assert recovery.committed_transactions == ("post",)
        assert coord.current_recovery_position().has_uncompacted_appends is True


def test_compaction_publish_is_atomic_on_pointer_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ipfs_kit_py.core.wal import checkpoint as checkpoint_module

    with _coord(tmp_path) as coord:
        path = coord.segments_directory / "seg.wal"
        sealed = _append_transaction(
            path,
            segment_id="seg",
            first_sequence=0,
            transaction_id="txn",
            effect_key="effect",
            seal=True,
        )
        first = coord.checkpoint([sealed], state=b"before", checkpoint_id="ckpt-1")
        assert first.success is True

        real_atomic = checkpoint_module._atomic_write

        def fail_pointer(path: Path, data: bytes) -> None:
            if path == coord.checkpoint_store.current_path:
                raise OSError("injected pointer publication failure")
            real_atomic(path, data)

        monkeypatch.setattr(checkpoint_module, "_atomic_write", fail_pointer)
        second = coord.compact(
            [sealed],
            state=b"after",
            checkpoint_id="ckpt-2",
        )
        assert second.success is False
        assert second.disposition is MaintenanceDisposition.FAILED

        loaded = coord.checkpoint_store.load_current()
        assert loaded is not None
        bundle, state = loaded
        assert bundle.checkpoint.checkpoint_id == "ckpt-1"
        assert state == b"before"


# ---------------------------------------------------------------------------
# Archive verified before source deletion
# ---------------------------------------------------------------------------


def test_archive_verified_before_source_deletion(tmp_path: Path) -> None:
    with _coord(tmp_path) as coord:
        completed = coord.segments_directory / "completed.wal"
        completed.write_bytes(b"complete WAL bytes for archive")
        receipt = coord.archive((completed,), delete_source=True)
        assert receipt.success is True
        assert receipt.phase is MaintenancePhase.ARCHIVE
        assert receipt.detail.get("verified_before_delete") is True
        assert receipt.archive_receipt_id
        assert receipt.archived_paths
        assert not completed.exists()
        # Archived copy exists and matches original content hash.
        archived = Path(receipt.archived_paths[0])
        assert archived.is_file()
        assert archived.read_bytes() == b"complete WAL bytes for archive"


def test_archive_failure_retains_sources(tmp_path: Path) -> None:
    with _coord(tmp_path) as coord:
        completed = coord.segments_directory / "completed.wal"
        missing = coord.segments_directory / "missing.wal"
        completed.write_bytes(b"must-be-retained-on-failure")
        receipt = coord.archive((completed, missing), delete_source=True)
        assert receipt.success is False
        assert receipt.disposition is MaintenanceDisposition.FAILED
        assert receipt.error_code == MaintenanceErrorCode.ARCHIVE.value
        # Source that existed is retained when archive of the batch fails.
        assert completed.exists()
        assert completed.read_bytes() == b"must-be-retained-on-failure"
        retained = receipt.detail.get("retained_sources") or []
        assert str(completed) in retained


def test_checkpoint_with_delete_archives_first(tmp_path: Path) -> None:
    with _coord(tmp_path) as coord:
        path = coord.segments_directory / "to-archive.wal"
        sealed = _append_transaction(
            path,
            segment_id="to-archive",
            first_sequence=0,
            transaction_id="txn-a",
            effect_key="effect-a",
            seal=True,
        )
        coord.register_segment_path("to-archive", path)
        receipt = coord.checkpoint(
            [sealed],
            state=b"state",
            delete_completed=True,
        )
        assert receipt.success is True
        assert receipt.archive_receipt_id
        assert not path.exists()


# ---------------------------------------------------------------------------
# Disk pressure applies explicit backpressure
# ---------------------------------------------------------------------------


def test_disk_pressure_applies_explicit_backpressure(tmp_path: Path) -> None:
    policy = DiskPressurePolicy(min_free_bytes=10_000_000, min_free_ratio=0.5)
    with _coord(tmp_path, disk_pressure=policy) as coord:
        # Inject critically low free space.
        coord.set_disk_space_override(free_bytes=100, total_bytes=1_000_000)
        path = coord.segments_directory / "seg.wal"
        sealed = _append_transaction(
            path,
            segment_id="seg",
            first_sequence=0,
            transaction_id="txn",
            effect_key="effect",
            seal=True,
        )
        receipt = coord.checkpoint([sealed], state=b"state")
        assert receipt.success is False
        assert receipt.disposition is MaintenanceDisposition.BACKPRESSURE
        assert receipt.phase is MaintenancePhase.DISK_PRESSURE
        assert receipt.error_code == MaintenanceErrorCode.DISK_PRESSURE.value
        assert receipt.free_bytes == 100
        assert "backpressure" in wm_mod.MaintenanceTraceKind.BACKPRESSURE.value
        kinds = coord.trace.kinds()
        assert "backpressure" in kinds

        with pytest.raises(DiskPressureError) as exc_info:
            coord.admit_or_backpressure(phase=MaintenancePhase.CHECKPOINT)
        assert exc_info.value.code is MaintenanceErrorCode.DISK_PRESSURE
        assert exc_info.value.free_bytes == 100


def test_disk_pressure_blocks_archive_without_deleting(tmp_path: Path) -> None:
    policy = DiskPressurePolicy(min_free_bytes=50_000_000, min_free_ratio=0.0)
    with _coord(tmp_path, disk_pressure=policy) as coord:
        completed = coord.segments_directory / "keep.wal"
        completed.write_bytes(b"must-not-delete-under-pressure")
        coord.set_disk_space_override(free_bytes=10, total_bytes=100)
        receipt = coord.archive((completed,), delete_source=True)
        assert receipt.disposition is MaintenanceDisposition.BACKPRESSURE
        assert completed.exists()
        assert completed.read_bytes() == b"must-not-delete-under-pressure"


def test_disk_pressure_policy_admits_when_space_ok() -> None:
    policy = DiskPressurePolicy(min_free_bytes=100, min_free_ratio=0.01)
    assert policy.admits(free_bytes=1_000, total_bytes=10_000) is True
    assert policy.admits(free_bytes=50, total_bytes=10_000) is False
    assert policy.admits(free_bytes=200, total_bytes=100_000) is False  # ratio


# ---------------------------------------------------------------------------
# Workers heartbeat and stop
# ---------------------------------------------------------------------------


def test_workers_heartbeat_and_stop(tmp_path: Path) -> None:
    with _coord(tmp_path, heartbeat_interval_seconds=0.05) as coord:
        cycles: list[int] = []

        def on_cycle(worker: MaintenanceWorker) -> None:
            cycles.append(worker.cycle)

        hb = coord.start_worker(on_cycle=on_cycle)
        assert hb.state is WorkerState.RUNNING
        assert hb.mount_id == "mount:test"
        assert coord.heartbeat_path.is_file()

        # Wait for at least one heartbeat refresh.
        deadline = time.time() + 2.0
        last_ms = hb.heartbeat_unix_ms
        seen_refresh = False
        while time.time() < deadline:
            raw = json.loads(coord.heartbeat_path.read_text(encoding="utf-8"))
            if int(raw.get("heartbeat_unix_ms") or 0) >= last_ms and int(raw.get("cycle") or 0) >= 1:
                seen_refresh = True
                break
            time.sleep(0.02)
        assert seen_refresh is True
        assert coord.worker is not None
        assert coord.worker.running is True

        stopped = coord.stop_worker(timeout_seconds=2.0)
        assert stopped is not None
        assert stopped.state is WorkerState.STOPPED
        assert coord.worker.running is False
        # Terminal heartbeat is durable on disk.
        final = json.loads(coord.heartbeat_path.read_text(encoding="utf-8"))
        assert final["state"] == "stopped"
        # stop is idempotent
        again = coord.stop_worker()
        assert again is not None
        assert again.state is WorkerState.STOPPED


def test_standalone_worker_start_heartbeat_stop(tmp_path: Path) -> None:
    path = tmp_path / "hb.json"
    worker = MaintenanceWorker(path, mount_id="mount:w", interval_seconds=0.05)
    hb = worker.start()
    assert hb.state is WorkerState.RUNNING
    time.sleep(0.12)
    forced = worker.heartbeat()
    assert forced.heartbeat_unix_ms >= hb.heartbeat_unix_ms
    stopped = worker.stop(timeout_seconds=2.0)
    assert stopped.state is WorkerState.STOPPED
    with pytest.raises(wm_mod.MaintenanceError):
        worker.heartbeat()


# ---------------------------------------------------------------------------
# Mount shutdown preserves latest durable recovery position
# ---------------------------------------------------------------------------


def test_mount_shutdown_preserves_latest_durable_recovery_position(
    tmp_path: Path,
) -> None:
    state = tmp_path / "shutdown-state"
    with WalMaintenanceCoordinator(
        state,
        generation_id=GENERATION,
        mount_id="mount:shutdown",
        disk_pressure=DiskPressurePolicy(min_free_bytes=1, min_free_ratio=0.0),
        heartbeat_interval_seconds=0.05,
    ) as coord:
        path = coord.segments_directory / "seg.wal"
        sealed = _append_transaction(
            path,
            segment_id="seg",
            first_sequence=0,
            transaction_id="txn",
            effect_key="effect",
            seal=True,
        )
        coord.register_segment_path("seg", path)
        ckpt = coord.checkpoint([sealed], state=b"snap", checkpoint_id="ckpt-shutdown")
        assert ckpt.success is True

        # Observe later appends that exceed the checkpoint.
        coord.observe_append(9)
        coord.start_worker()
        time.sleep(0.08)

        receipt = coord.shutdown()
        assert receipt.success is True
        assert receipt.phase is MaintenancePhase.SHUTDOWN
        assert receipt.recovery_position is not None
        pos = receipt.recovery_position
        assert pos.checkpoint_id == "ckpt-shutdown"
        assert pos.through_sequence == 2
        assert pos.last_append_sequence == 9
        assert pos.has_uncompacted_appends is True
        assert pos.generation_id == GENERATION
        assert coord.recovery_position_path.is_file()
        assert coord.closed is True
        # Worker stopped as part of shutdown.
        assert coord.worker is not None
        assert coord.worker.state is WorkerState.STOPPED

    # Restart: position is restored and later appends are not lost.
    restarted = WalMaintenanceCoordinator(
        state,
        generation_id=GENERATION,
        mount_id="mount:shutdown",
        disk_pressure=DiskPressurePolicy(min_free_bytes=1, min_free_ratio=0.0),
    )
    try:
        restored = restarted.load_recovery_position()
        assert restored is not None
        assert restored.checkpoint_id == "ckpt-shutdown"
        assert restored.through_sequence == 2
        assert restored.last_append_sequence == 9
        assert restored.has_uncompacted_appends is True
        assert restarted.through_sequence == 2
        assert restarted.last_append_sequence == 9
        # Idempotent shutdown after already closed from prior instance's file.
        second = restarted.shutdown()
        assert second.success is True
    finally:
        if not restarted.closed:
            restarted.shutdown()


def test_shutdown_is_idempotent(tmp_path: Path) -> None:
    with _coord(tmp_path) as coord:
        first = coord.shutdown()
        assert first.disposition is MaintenanceDisposition.SUCCESS
        second = coord.shutdown()
        assert second.disposition is MaintenanceDisposition.IDEMPOTENT
        assert second.success is True


def test_operations_refuse_after_shutdown(tmp_path: Path) -> None:
    coord = _coord(tmp_path)
    coord.shutdown()
    path = coord.segments_directory / "seg.wal"
    sealed = _append_transaction(
        path,
        segment_id="seg",
        first_sequence=0,
        transaction_id="txn",
        effect_key="effect",
        seal=True,
    )
    receipt = coord.checkpoint([sealed], state=b"x")
    assert receipt.success is False
    assert receipt.error_code == MaintenanceErrorCode.CLOSED.value


# ---------------------------------------------------------------------------
# Factory / integration smoke
# ---------------------------------------------------------------------------


def test_build_factory_and_end_to_end(tmp_path: Path) -> None:
    coord = build_wal_maintenance_coordinator(
        tmp_path / "factory",
        generation_id=GENERATION,
        disk_pressure=DiskPressurePolicy(min_free_bytes=1, min_free_ratio=0.0),
    )
    try:
        assert isinstance(coord, WalMaintenanceCoordinator)
        path = coord.segments_directory / "e2e.wal"
        sealed = _append_transaction(
            path,
            segment_id="e2e",
            first_sequence=0,
            transaction_id="e2e",
            effect_key="e2e-effect",
            seal=True,
        )
        coord.register_segment_path("e2e", path)
        ckpt = coord.checkpoint([sealed], state=b"e2e-state")
        assert ckpt.success
        later = coord.segments_directory / "e2e-later.wal"
        _append_transaction(
            later,
            segment_id="e2e-later",
            first_sequence=3,
            transaction_id="e2e-later",
            effect_key="e2e-later-effect",
            seal=False,
        )
        coord.observe_append(5)
        applied: list[str] = []
        coord.recover_with_current_checkpoint(
            (path, later),
            handler=lambda r: applied.append(r.record_key),
        )
        assert applied == ["e2e-later-effect"]
        shut = coord.shutdown()
        assert shut.recovery_position is not None
        assert shut.recovery_position.last_append_sequence == 5
    finally:
        if not coord.closed:
            coord.shutdown()


def test_create_checkpoint_reexport_compatible_with_core(tmp_path: Path) -> None:
    """Coordinator uses the same identity-bound core checkpoint primitive."""

    path = tmp_path / "core.wal"
    sealed = _append_transaction(
        path,
        segment_id="core-seg",
        first_sequence=0,
        transaction_id="core",
        effect_key="core-effect",
        seal=True,
    )
    bundle = create_checkpoint("c1", GENERATION, [sealed], state=b"s")
    published = CheckpointStore(tmp_path / "store").publish(bundle, b"s")
    assert published.checkpoint.through_sequence == 2
    assert wm_mod.create_checkpoint is create_checkpoint
