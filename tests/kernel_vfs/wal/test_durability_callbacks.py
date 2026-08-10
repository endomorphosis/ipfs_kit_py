"""KVFS-300: Map flush, fsync, release, and deferred errors to durability receipts.

Acceptance coverage:

* fsync waits for configured WAL and backend file/parent-directory durability;
* flush is repeatable and reports deferred errors consistently;
* release is idempotent and creates no false durability;
* timeout / cancel / ENOSPC / EIO traces never acknowledge lost data.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ipfs_kit_py.core.vfs.host_contracts import DurabilityMode, HostCallbackKind, HostErrno
from ipfs_kit_py.core.wal.contracts import WALAcknowledgementMode, ack_requirements_for
from ipfs_kit_py.kernel_vfs import durability as dur_mod
from ipfs_kit_py.kernel_vfs.durability import (
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    TASK_ID,
    DeferredErrorState,
    DeferredErrorState_V1,
    DurabilityCallbackKind,
    DurabilityCoordinator,
    DurabilityCoordinator_V1,
    DurabilityDisposition,
    DurabilityErrorCode,
    DurabilityFaultError,
    DurabilityFaultKind,
    DurabilityMedia,
    DurabilityProtocolError,
    DurabilityReceipt,
    DurabilityReceipt_V1,
    DurabilityRequirements,
    DurabilityTraceKind,
    all_mode_requirements,
    build_durability_coordinator,
    durability_callbacks,
    durability_modes,
    effective_fsync_mode,
    fault_kinds,
    host_callback_for,
    path_to_ref,
    requirements_for,
    wal_ack_mode_for,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = PACKAGE_ROOT / "ipfs_kit_py" / "kernel_vfs" / "durability.py"


# ---------------------------------------------------------------------------
# Schema / vocabulary
# ---------------------------------------------------------------------------


def test_schema_versions_and_aliases() -> None:
    assert TASK_ID == "KVFS-300"
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert DurabilityCoordinator_V1.endswith("@1")
    assert DurabilityReceipt_V1.endswith("@1")
    assert DeferredErrorState_V1.endswith("@1")
    assert durability_callbacks() == ("flush", "fsync", "release")
    assert durability_modes() == (
        "buffered",
        "wal_file_sync",
        "wal_parent_sync",
        "wal_and_backend",
        "committed_visible",
    )
    assert fault_kinds() == ("timeout", "cancel", "enospc", "eio")
    assert "KVFS-300" in MODULE_PATH.read_text(encoding="utf-8")


def test_path_to_ref_and_host_callback_mapping() -> None:
    assert path_to_ref("docs/a/b").startswith("path:")
    assert "/" not in path_to_ref("docs/a/b")
    assert host_callback_for(DurabilityCallbackKind.FSYNC) is HostCallbackKind.FSYNC
    assert host_callback_for("flush") is HostCallbackKind.FLUSH
    assert host_callback_for("release") is HostCallbackKind.RELEASE


def test_effective_fsync_mode_never_buffered() -> None:
    assert effective_fsync_mode(DurabilityMode.BUFFERED) is DurabilityMode.WAL_AND_BACKEND
    assert effective_fsync_mode(DurabilityMode.WAL_FILE_SYNC) is DurabilityMode.WAL_FILE_SYNC
    assert effective_fsync_mode("committed_visible") is DurabilityMode.COMMITTED_VISIBLE


def test_requirements_table_covers_all_modes() -> None:
    reqs = all_mode_requirements()
    assert len(reqs) == len(DurabilityMode)
    by_mode = {r.mode: r for r in reqs}

    buffered = by_mode[DurabilityMode.BUFFERED]
    assert buffered.may_claim_durable is False
    assert buffered.requires_wal_file_fsync is False

    wal_file = by_mode[DurabilityMode.WAL_FILE_SYNC]
    assert wal_file.requires_wal_file_fsync is True
    assert wal_file.requires_wal_parent_directory_fsync is False
    assert wal_file.requires_backend_file_fsync is False
    assert wal_file.may_claim_durable is True

    wal_parent = by_mode[DurabilityMode.WAL_PARENT_SYNC]
    assert wal_parent.requires_wal_file_fsync is True
    assert wal_parent.requires_wal_parent_directory_fsync is True
    assert wal_parent.requires_backend_file_fsync is False

    wal_backend = by_mode[DurabilityMode.WAL_AND_BACKEND]
    assert wal_backend.requires_wal_file_fsync is True
    assert wal_backend.requires_backend_file_fsync is True
    assert wal_backend.requires_backend_effect is True

    committed = by_mode[DurabilityMode.COMMITTED_VISIBLE]
    assert committed.requires_wal_file_fsync is True
    assert committed.requires_wal_parent_directory_fsync is True
    assert committed.requires_backend_file_fsync is True
    assert committed.requires_backend_parent_directory_fsync is True
    assert committed.requires_backend_effect is True
    assert committed.may_claim_durable is True

    # WAL ack mapping is consistent with core contracts.
    assert wal_ack_mode_for(DurabilityMode.WAL_FILE_SYNC) is WALAcknowledgementMode.WAL_FSYNC
    assert (
        wal_ack_mode_for(DurabilityMode.WAL_PARENT_SYNC)
        is WALAcknowledgementMode.WAL_FSYNC_PARENT
    )
    assert (
        wal_ack_mode_for(DurabilityMode.COMMITTED_VISIBLE)
        is WALAcknowledgementMode.BACKEND_DURABLE
    )
    ack = ack_requirements_for(WALAcknowledgementMode.BACKEND_DURABLE)
    assert ack.requires_file_fsync is True
    assert ack.requires_parent_directory_fsync is True
    assert ack.requires_backend_effect is True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coord(**kwargs: object) -> DurabilityCoordinator:
    return DurabilityCoordinator(**kwargs)  # type: ignore[arg-type]


def _register(
    coord: DurabilityCoordinator,
    handle_id: int = 1,
    *,
    generation: int = 1,
    path: str = "docs/file.bin",
    dirty: bool = True,
    effect_id: str = "",
) -> None:
    coord.register_handle(
        handle_id,
        generation=generation,
        path=path,
        dirty=dirty,
        effect_id=effect_id or f"effect:{handle_id}",
    )


# ---------------------------------------------------------------------------
# fsync waits for configured WAL and backend durability
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mode,expect_wal_file,expect_wal_parent,expect_backend_file,expect_backend_parent",
    [
        (DurabilityMode.WAL_FILE_SYNC, True, False, False, False),
        (DurabilityMode.WAL_PARENT_SYNC, True, True, False, False),
        (DurabilityMode.WAL_AND_BACKEND, True, False, True, False),
        (DurabilityMode.COMMITTED_VISIBLE, True, True, True, True),
    ],
)
def test_fsync_waits_for_configured_wal_and_backend_boundaries(
    mode: DurabilityMode,
    expect_wal_file: bool,
    expect_wal_parent: bool,
    expect_backend_file: bool,
    expect_backend_parent: bool,
) -> None:
    with _coord(durability_mode=mode) as coord:
        _register(coord, 7, path="ns/a.bin")
        receipt = coord.fsync(7, generation=1)
        assert receipt.success is True
        assert receipt.callback is DurabilityCallbackKind.FSYNC
        assert receipt.durability_mode is mode
        assert receipt.durable is True
        assert receipt.acknowledged_data is True
        assert receipt.observed_effect is True
        assert receipt.wal_file_fsync is expect_wal_file
        assert receipt.wal_parent_directory_fsync is expect_wal_parent
        assert receipt.backend_file_fsync is expect_backend_file
        assert receipt.backend_parent_directory_fsync is expect_backend_parent
        assert receipt.fsync_receipt_id
        assert receipt.requirements is not None
        assert receipt.requirements.mode is mode

        kinds = coord.trace.kinds()
        if expect_wal_file:
            assert DurabilityTraceKind.WAL_FILE_SYNC.value in kinds
        if expect_wal_parent:
            assert DurabilityTraceKind.WAL_PARENT_SYNC.value in kinds
        if expect_backend_file:
            assert DurabilityTraceKind.BACKEND_FILE_SYNC.value in kinds
        if expect_backend_parent:
            assert DurabilityTraceKind.BACKEND_PARENT_SYNC.value in kinds
        assert DurabilityTraceKind.FSYNC.value in kinds

        # Media observations match the wait ladder.
        obs_names = {o.boundary for o in coord.media.observations}
        if expect_wal_file:
            assert "wal_file_fsync" in obs_names
        if expect_wal_parent:
            assert "wal_parent_directory_fsync" in obs_names
        if expect_backend_file:
            assert "backend_file_fsync" in obs_names
        if expect_backend_parent:
            assert "backend_parent_directory_fsync" in obs_names

        record = receipt.to_record()
        assert record["schema"] == DurabilityReceipt_V1
        assert record["durable"] is True
        assert record["acknowledged_data"] is True
        assert record["callback"] == "fsync"


def test_fsync_upgrades_buffered_mode_before_success() -> None:
    with _coord(durability_mode=DurabilityMode.BUFFERED) as coord:
        _register(coord, 3, path="buf.bin")
        receipt = coord.fsync(3, generation=1)
        assert receipt.success is True
        assert receipt.durability_mode is DurabilityMode.WAL_AND_BACKEND
        assert receipt.durability_mode is not DurabilityMode.BUFFERED
        assert receipt.durable is True
        assert receipt.wal_file_fsync is True
        assert receipt.backend_file_fsync is True
        # Policy guard: constructing buffered fsync success is forbidden.
        with pytest.raises(DurabilityProtocolError):
            DurabilityReceipt(
                receipt_id="receipt:bad",
                callback=DurabilityCallbackKind.FSYNC,
                disposition=DurabilityDisposition.SUCCESS,
                success=True,
                durable=True,
                durability_mode=DurabilityMode.BUFFERED,
                acknowledged_data=True,
                wal_file_fsync=True,
                fsync_receipt_id="fsync:x",
            )


def test_fsync_ordering_wal_before_backend() -> None:
    order: list[str] = []

    class TrackingMedia(DurabilityMedia):
        def wal_file_fsync(self, *, handle_key: str = ""):
            order.append("wal_file")
            return super().wal_file_fsync(handle_key=handle_key)

        def wal_parent_directory_fsync(self, *, handle_key: str = ""):
            order.append("wal_parent")
            return super().wal_parent_directory_fsync(handle_key=handle_key)

        def backend_file_fsync(self, path: str, *, handle_key: str = "", effect_id: str = ""):
            order.append("backend_file")
            return super().backend_file_fsync(
                path, handle_key=handle_key, effect_id=effect_id
            )

        def backend_parent_directory_fsync(self, path: str, *, handle_key: str = ""):
            order.append("backend_parent")
            return super().backend_parent_directory_fsync(path, handle_key=handle_key)

    media = TrackingMedia()
    with _coord(
        durability_mode=DurabilityMode.COMMITTED_VISIBLE, media=media
    ) as coord:
        _register(coord, 1, path="order.bin")
        receipt = coord.fsync(1, generation=1)
        assert receipt.success is True
        assert order == ["wal_file", "wal_parent", "backend_file", "backend_parent"]


def test_fsync_receipt_satisfies_wal_ack_requirements() -> None:
    with _coord(durability_mode=DurabilityMode.COMMITTED_VISIBLE) as coord:
        _register(coord, 2, path="ack.bin", effect_id="effect:ack")
        receipt = coord.fsync(2, generation=1)
        assert receipt.wal_fsync_receipt is not None
        wal_ack = ack_requirements_for(WALAcknowledgementMode.BACKEND_DURABLE)
        assert receipt.wal_fsync_receipt.satisfies(wal_ack)
        assert receipt.backend_effect_id == "effect:ack"


# ---------------------------------------------------------------------------
# flush is repeatable and reports deferred errors consistently
# ---------------------------------------------------------------------------


def test_flush_is_repeatable_and_non_durable() -> None:
    with _coord() as coord:
        _register(coord, 10, path="flush.bin", dirty=True)
        first = coord.flush(10, generation=1)
        second = coord.flush(10, generation=1)
        third = coord.flush(10, generation=1)
        assert first.success is True
        assert second.success is True
        assert third.success is True
        assert first.durable is False
        assert second.durable is False
        assert third.durable is False
        assert first.acknowledged_data is False
        assert second.idempotent is True
        assert third.idempotent is True
        assert first.flush_count == 1
        assert second.flush_count == 2
        assert third.flush_count == 3
        assert second.disposition is DurabilityDisposition.IDEMPOTENT
        # Flush must not manufacture durability even under committed mode.
        assert coord.durability_mode is DurabilityMode.COMMITTED_VISIBLE
        with pytest.raises(DurabilityProtocolError):
            DurabilityReceipt(
                receipt_id="receipt:bad-flush",
                callback=DurabilityCallbackKind.FLUSH,
                disposition=DurabilityDisposition.SUCCESS,
                success=True,
                durable=True,
                durability_mode=DurabilityMode.COMMITTED_VISIBLE,
                acknowledged_data=True,
            )


def test_flush_reports_deferred_errors_consistently() -> None:
    with _coord() as coord:
        _register(coord, 11, path="def.bin")
        deferred = coord.set_deferred_error(
            11,
            generation=1,
            errno=HostErrno.EIO,
            message="simulated writeback failure",
        )
        assert isinstance(deferred, DeferredErrorState)
        assert deferred.errno is HostErrno.EIO

        first = coord.flush(11, generation=1)
        second = coord.flush(11, generation=1)
        third = coord.flush(11, generation=1)

        assert first.success is False
        assert second.success is False
        assert third.success is False
        assert first.deferred_error is True
        assert second.deferred_error is True
        assert third.deferred_error is True
        assert first.errno is HostErrno.EIO
        assert second.errno is first.errno
        assert third.errno is first.errno
        assert first.error_code == DurabilityErrorCode.DEFERRED.value
        assert second.error_code == first.error_code
        assert second.idempotent is True
        assert third.idempotent is True
        assert first.durable is False
        assert first.acknowledged_data is False
        assert second.acknowledged_data is False
        # Report counts advance consistently.
        assert first.deferred is not None
        assert second.deferred is not None
        assert first.deferred.report_count == 1
        assert second.deferred.report_count == 2
        assert third.deferred is not None
        assert third.deferred.report_count == 3
        assert first.message == "simulated writeback failure"
        assert second.message == first.message


def test_fsync_surfaces_deferred_error_and_does_not_acknowledge() -> None:
    with _coord(durability_mode=DurabilityMode.COMMITTED_VISIBLE) as coord:
        _register(coord, 12, path="block.bin", dirty=True)
        coord.set_deferred_error(
            12,
            generation=1,
            errno=HostErrno.ENOSPC,
            error_code=DurabilityErrorCode.ENOSPC,
            message="disk full on writeback",
        )
        receipt = coord.fsync(12, generation=1)
        assert receipt.success is False
        assert receipt.deferred_error is True
        assert receipt.errno is HostErrno.ENOSPC
        assert receipt.durable is False
        assert receipt.acknowledged_data is False
        assert receipt.wal_file_fsync is False
        assert receipt.backend_file_fsync is False
        # Dirty remains (fsync did not clear under deferred error).
        assert coord.is_dirty(12, generation=1) is True
        # Media must not have advanced durability observations.
        assert coord.media.observations == ()


def test_flush_after_clearing_deferred_via_release_is_not_on_live_handle() -> None:
    with _coord() as coord:
        _register(coord, 13, path="gone.bin")
        coord.set_deferred_error(13, generation=1, errno=HostErrno.EIO)
        coord.release(13, generation=1)
        # Released handle generation is sticky; flush must not resurrect it.
        with pytest.raises(dur_mod.DurabilityError) as excinfo:
            coord.flush(13, generation=1)
        assert excinfo.value.code is DurabilityErrorCode.RELEASED
        assert excinfo.value.errno is HostErrno.EBADF


# ---------------------------------------------------------------------------
# release is idempotent and creates no false durability
# ---------------------------------------------------------------------------


def test_release_is_idempotent_and_non_durable() -> None:
    with _coord() as coord:
        _register(coord, 20, path="rel.bin", dirty=True)
        first = coord.release(20, generation=1)
        second = coord.release(20, generation=1)
        third = coord.release(20, generation=1)

        assert first.success is True
        assert first.already_released is False
        assert first.durable is False
        assert first.acknowledged_data is False
        assert first.observed_effect is False
        assert first.disposition is DurabilityDisposition.SUCCESS

        assert second.success is True
        assert second.already_released is True
        assert second.idempotent is True
        assert second.durable is False
        assert second.acknowledged_data is False
        assert second.disposition is DurabilityDisposition.ALREADY_RELEASED

        assert third.success is True
        assert third.already_released is True
        assert third.durable is False
        assert third.acknowledged_data is False

        assert coord.is_released(20, generation=1) is True
        assert coord.is_dirty(20, generation=1) is False

        with pytest.raises(DurabilityProtocolError):
            DurabilityReceipt(
                receipt_id="receipt:bad-release",
                callback=DurabilityCallbackKind.RELEASE,
                disposition=DurabilityDisposition.SUCCESS,
                success=True,
                durable=True,
                durability_mode=DurabilityMode.COMMITTED_VISIBLE,
                acknowledged_data=True,
            )


def test_release_does_not_manufacture_durability_for_dirty_bytes() -> None:
    with _coord(durability_mode=DurabilityMode.COMMITTED_VISIBLE) as coord:
        _register(coord, 21, path="nodur.bin", dirty=True, effect_id="effect:dirty")
        receipt = coord.release(21, generation=1)
        assert receipt.success is True
        assert receipt.durable is False
        assert receipt.acknowledged_data is False
        assert receipt.detail.get("dirty_at_release") is True
        assert receipt.detail.get("manufactured_durability") is False
        # No fsync media observations from release.
        assert coord.media.observations == ()
        # Trace confirms non-durable release.
        release_events = [
            e for e in coord.trace.events() if e.kind is DurabilityTraceKind.RELEASE
        ]
        assert release_events
        assert all(e.detail.get("durable") is False for e in release_events)


def test_release_clears_deferred_error_without_acknowledging() -> None:
    with _coord() as coord:
        _register(coord, 22, path="clr.bin")
        coord.set_deferred_error(22, generation=1, errno=HostErrno.EIO)
        receipt = coord.release(22, generation=1)
        assert receipt.success is True
        assert receipt.durable is False
        assert receipt.detail.get("deferred_error_cleared") is True
        assert coord.get_deferred_error(22, generation=1) is None


def test_unknown_release_is_idempotent_success() -> None:
    with _coord() as coord:
        receipt = coord.release(999, generation=3)
        assert receipt.success is True
        assert receipt.already_released is True
        assert receipt.durable is False
        assert receipt.acknowledged_data is False


# ---------------------------------------------------------------------------
# timeout / cancel / ENOSPC / EIO never acknowledge lost data
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fault,boundary,errno,disposition",
    [
        (
            DurabilityFaultKind.TIMEOUT,
            "before_wal_file_fsync",
            HostErrno.ETIMEDOUT,
            DurabilityDisposition.TIMED_OUT,
        ),
        (
            DurabilityFaultKind.CANCEL,
            "after_wal_file_fsync",
            HostErrno.ECANCELED,
            DurabilityDisposition.CANCELLED,
        ),
        (
            DurabilityFaultKind.ENOSPC,
            "before_backend_file_fsync",
            HostErrno.ENOSPC,
            DurabilityDisposition.FAILED,
        ),
        (
            DurabilityFaultKind.EIO,
            "before_backend_parent_fsync",
            HostErrno.EIO,
            DurabilityDisposition.FAILED,
        ),
        (
            DurabilityFaultKind.TIMEOUT,
            "after_fsync",
            HostErrno.ETIMEDOUT,
            DurabilityDisposition.TIMED_OUT,
        ),
        (
            DurabilityFaultKind.EIO,
            "before_fsync",
            HostErrno.EIO,
            DurabilityDisposition.FAILED,
        ),
    ],
)
def test_fault_traces_never_acknowledge_lost_data(
    fault: DurabilityFaultKind,
    boundary: str,
    errno: HostErrno,
    disposition: DurabilityDisposition,
) -> None:
    def inject(name: str, _handle_key: str = "") -> None:
        if name == boundary:
            raise DurabilityFaultError(
                f"injected {fault.value} at {boundary}",
                fault=fault,
                detail={"boundary": boundary},
            )

    with _coord(
        durability_mode=DurabilityMode.COMMITTED_VISIBLE,
        fault_injector=inject,
    ) as coord:
        _register(coord, 30, path="fault.bin", dirty=True)
        receipt = coord.fsync(30, generation=1)
        assert receipt.success is False
        assert receipt.durable is False
        assert receipt.acknowledged_data is False
        assert receipt.errno is errno
        assert receipt.disposition is disposition
        assert receipt.detail.get("lost_data_acknowledged") is False
        assert receipt.detail.get("acknowledged_data") is False
        assert receipt.detail.get("fault") == fault.value

        # Explicit policy: failed receipts cannot claim durability.
        with pytest.raises(DurabilityProtocolError):
            DurabilityReceipt(
                receipt_id="receipt:bad-fault",
                callback=DurabilityCallbackKind.FSYNC,
                disposition=disposition,
                success=False,
                durable=True,
                durability_mode=DurabilityMode.COMMITTED_VISIBLE,
                errno=errno,
                acknowledged_data=True,
            )

        fault_events = [
            e for e in coord.trace.events() if e.kind is DurabilityTraceKind.FAULT
        ]
        assert fault_events
        for event in fault_events:
            assert event.success is False
            assert event.detail.get("acknowledged_data") is False

        fsync_events = [
            e for e in coord.trace.events() if e.kind is DurabilityTraceKind.FSYNC
        ]
        assert fsync_events
        assert all(e.success is False for e in fsync_events)
        assert all(e.detail.get("acknowledged_data") is False for e in fsync_events)


def test_inject_fault_receipt_for_all_fault_kinds() -> None:
    with _coord() as coord:
        for fault in DurabilityFaultKind:
            for callback in DurabilityCallbackKind:
                receipt = coord.inject_fault_receipt(
                    callback,
                    fault,
                    handle_id=40,
                    generation=1,
                    path="inj.bin",
                )
                assert receipt.success is False
                assert receipt.durable is False
                assert receipt.acknowledged_data is False
                assert receipt.detail.get("lost_data_acknowledged") is False
                assert receipt.errno is not HostErrno.OK


def test_enospc_and_eio_on_flush_path_via_deferred() -> None:
    with _coord() as coord:
        _register(coord, 41, path="space.bin")
        coord.set_deferred_error(
            41,
            generation=1,
            errno=HostErrno.ENOSPC,
            error_code=DurabilityErrorCode.ENOSPC,
            message="ENOSPC deferred",
        )
        a = coord.flush(41, generation=1)
        b = coord.flush(41, generation=1)
        assert a.errno is HostErrno.ENOSPC
        assert b.errno is HostErrno.ENOSPC
        assert a.acknowledged_data is False
        assert b.acknowledged_data is False

        coord2 = _coord()
        _register(coord2, 42, path="io.bin")
        coord2.set_deferred_error(
            42,
            generation=1,
            errno=HostErrno.EIO,
            error_code=DurabilityErrorCode.EIO,
            message="EIO deferred",
        )
        c = coord2.fsync(42, generation=1)
        assert c.success is False
        assert c.errno is HostErrno.EIO
        assert c.acknowledged_data is False
        coord2.close()


# ---------------------------------------------------------------------------
# End-to-end callback path + records
# ---------------------------------------------------------------------------


def test_open_write_flush_fsync_release_receipt_path() -> None:
    with _coord(durability_mode=DurabilityMode.COMMITTED_VISIBLE) as coord:
        _register(coord, 50, path="e2e.bin", dirty=True, effect_id="effect:e2e")
        flushed = coord.flush(50, generation=1)
        assert flushed.success is True
        assert flushed.durable is False

        synced = coord.fsync(50, generation=1)
        assert synced.success is True
        assert synced.durable is True
        assert synced.acknowledged_data is True
        assert synced.wal_file_fsync is True
        assert synced.wal_parent_directory_fsync is True
        assert synced.backend_file_fsync is True
        assert synced.backend_parent_directory_fsync is True

        released = coord.release(50, generation=1)
        assert released.success is True
        assert released.durable is False
        assert released.acknowledged_data is False

        again = coord.release(50, generation=1)
        assert again.already_released is True
        assert again.durable is False

        assert len(coord.receipts) >= 4
        assert coord.last_receipt is again
        record = coord.to_record()
        assert record["schema"] == DurabilityCoordinator_V1
        assert record["task_id"] == "KVFS-300"
        assert record["durability_mode"] == "committed_visible"


def test_build_durability_coordinator_helper(tmp_path: Path) -> None:
    coord = build_durability_coordinator(
        durability_mode="wal_file_sync",
        directory=tmp_path / "dur",
    )
    try:
        assert coord.durability_mode is DurabilityMode.WAL_FILE_SYNC
        _register(coord, 1, path="h.bin")
        receipt = coord.fsync(1)
        assert receipt.success is True
        assert receipt.wal_file_fsync is True
        assert receipt.wal_parent_directory_fsync is False
    finally:
        coord.close()


def test_receipt_failure_cannot_claim_ok_errno() -> None:
    with pytest.raises(DurabilityProtocolError):
        DurabilityReceipt(
            receipt_id="receipt:bad-errno",
            callback=DurabilityCallbackKind.FLUSH,
            disposition=DurabilityDisposition.FAILED,
            success=False,
            durable=False,
            durability_mode=DurabilityMode.BUFFERED,
            errno=HostErrno.OK,
        )


def test_success_cannot_carry_deferred_error_flag() -> None:
    with pytest.raises(DurabilityProtocolError):
        DurabilityReceipt(
            receipt_id="receipt:bad-def",
            callback=DurabilityCallbackKind.FLUSH,
            disposition=DurabilityDisposition.SUCCESS,
            success=True,
            durable=False,
            durability_mode=DurabilityMode.BUFFERED,
            deferred_error=True,
        )


def test_module_exports_match_task_surface() -> None:
    assert hasattr(dur_mod, "DurabilityCoordinator")
    assert hasattr(dur_mod, "DurabilityReceipt")
    assert hasattr(dur_mod, "DeferredErrorState")
    assert hasattr(dur_mod, "requirements_for")
    assert isinstance(requirements_for(DurabilityMode.WAL_FILE_SYNC), DurabilityRequirements)
    assert DurabilityCoordinator is dur_mod.DurabilityCoordinator
