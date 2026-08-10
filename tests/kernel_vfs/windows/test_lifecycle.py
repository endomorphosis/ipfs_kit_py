"""KVFS-601: WinFsp drive/directory mount lifecycle and cleanup.

Acceptance coverage:

* same operations object mounts through WinFsp FUSE compatibility;
* recovery precedes 15-second readiness;
* drive-letter and directory forms validate;
* status/heartbeat bind resources;
* stop/crash/repeated unmount release drive/directory/process/lease and
  preserve WAL state without a foreground worker hang.

Hermetic: no live WinFsp mount, no fusepy import side effect at module load.
"""

from __future__ import annotations

import ast
import sys
import threading
import time
from pathlib import Path

import pytest

from ipfs_kit_py.core.vfs.host_contracts import HostPlatform, MountLifecycleState
from ipfs_kit_py.kernel_vfs.operations import KernelVFSOperations
from ipfs_kit_py.kernel_vfs import windows as win_mod
from ipfs_kit_py.kernel_vfs.windows import (
    CONTRACT_VERSION,
    DEFAULT_READINESS_TIMEOUT_SECONDS,
    SCHEMA_VERSION,
    TASK_ID,
    WindowsLifecycleError,
    WindowsLifecycleErrorCode,
    WindowsMountLifecycle,
    WindowsMountLifecycle_V1,
    WindowsMountMode,
    WindowsMountPhase,
    WindowsMountRootError,
    WindowsMountState,
    WindowsMountStatus_V1,
    WindowsMountHeartbeat_V1,
    WindowsReadinessError,
    WindowsResourceLeaseError,
    WinFspFuseCompatAdapter,
    assert_no_fusepy_import,
    build_windows_mount_lifecycle,
    mount_modes,
    mount_phases,
    mount_root_kinds,
    mount_windows,
)
from ipfs_kit_py.kernel_vfs.windows_semantics import MountRootKind

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = PACKAGE_ROOT / "ipfs_kit_py" / "kernel_vfs" / "windows.py"

# Capture fuse modules present before import so inertness checks stay honest.
_PREEXISTING_FUSE_MODULES = {
    name for name in ("fuse", "fusepy") if name in sys.modules
}


# ---------------------------------------------------------------------------
# Schema / inertness
# ---------------------------------------------------------------------------


def test_declared_module_exists() -> None:
    assert MODULE_PATH.is_file()
    assert MODULE_PATH.stat().st_size > 0


def test_schema_versions_and_aliases() -> None:
    assert TASK_ID == "KVFS-601"
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert WindowsMountLifecycle_V1.endswith("@1")
    assert WindowsMountStatus_V1.endswith("@1")
    assert WindowsMountHeartbeat_V1.endswith("@1")
    assert DEFAULT_READINESS_TIMEOUT_SECONDS == 15.0
    assert "hermetic" in mount_modes()
    assert "native" in mount_modes()
    assert "drive_letter" in mount_root_kinds()
    assert "directory" in mount_root_kinds()
    assert WindowsMountPhase.RECOVER.value in mount_phases()
    assert WindowsMountPhase.READY.value in mount_phases()
    assert "KVFS-601" in MODULE_PATH.read_text(encoding="utf-8")
    assert "15" in MODULE_PATH.read_text(encoding="utf-8")


def test_module_import_is_inert() -> None:
    """Importing windows lifecycle must not hard-import fusepy or load WinFsp."""

    assert_no_fusepy_import()
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(MODULE_PATH))
    banned = frozenset({"fuse", "fusepy"})
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".", 1)[0] not in banned
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module:
                assert module.split(".", 1)[0] not in banned
    # No new fuse modules introduced solely by our import.
    for name in ("fuse", "fusepy"):
        if name not in _PREEXISTING_FUSE_MODULES:
            assert name not in sys.modules
    assert "LoadLibrary" not in source


# ---------------------------------------------------------------------------
# Drive-letter and directory form validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,canonical",
    [
        ("Z:", "Z:"),
        ("z:", "Z:"),
        ("Y:\\", "Y:"),
    ],
)
def test_drive_letter_forms_validate(raw: str, canonical: str) -> None:
    root = WindowsMountLifecycle.validate_root(
        raw, kind=MountRootKind.DRIVE_LETTER
    )
    assert root.kind is MountRootKind.DRIVE_LETTER
    assert root.canonical == canonical


@pytest.mark.parametrize(
    "raw",
    ["", "1:", "ZZ:", "not-a-drive", "C:extra", "\\\\share\\path"],
)
def test_invalid_drive_letter_forms_reject(raw: str) -> None:
    with pytest.raises(WindowsMountRootError) as exc_info:
        WindowsMountLifecycle.validate_root(
            raw, kind=MountRootKind.DRIVE_LETTER
        )
    assert exc_info.value.code is WindowsLifecycleErrorCode.ROOT


@pytest.mark.parametrize(
    "raw",
    [
        "/mnt/winfsp",
        "/tmp/kvfs-mount",
        "C:\\Mounts\\ipfs",
        "D:/data/mount",
    ],
)
def test_directory_forms_validate(raw: str) -> None:
    root = WindowsMountLifecycle.validate_root(
        raw, kind=MountRootKind.DIRECTORY
    )
    assert root.kind is MountRootKind.DIRECTORY
    assert root.canonical


@pytest.mark.parametrize(
    "raw",
    ["", "relative", "./here", "../escape", "Z:", "Z:\\"],
)
def test_invalid_directory_forms_reject(raw: str) -> None:
    with pytest.raises(WindowsMountRootError):
        WindowsMountLifecycle.validate_root(raw, kind=MountRootKind.DIRECTORY)


def test_auto_detect_drive_vs_directory() -> None:
    drive = WindowsMountLifecycle.validate_root("W:")
    assert drive.kind is MountRootKind.DRIVE_LETTER
    directory = WindowsMountLifecycle.validate_root("/var/mnt/kvfs")
    assert directory.kind is MountRootKind.DIRECTORY


# ---------------------------------------------------------------------------
# Same operations object through WinFsp FUSE compatibility
# ---------------------------------------------------------------------------


def test_same_operations_object_bound_through_adapter(tmp_path: Path) -> None:
    ops = KernelVFSOperations.with_memory_storage(
        platform=HostPlatform.WINDOWS,
        mount_id="mount:shared-ops",
    )
    assert ops.lifecycle is MountLifecycleState.UNINITIALIZED

    with WindowsMountLifecycle(
        tmp_path / "state-ops",
        mount_id="mount:shared-ops",
        operations=ops,
        mode=WindowsMountMode.HERMETIC,
    ) as life:
        receipt = life.mount("Z:", kind=MountRootKind.DRIVE_LETTER)
        assert receipt.success is True
        assert receipt.ready is True
        assert life.operations is ops
        assert life.adapter is not None
        assert isinstance(life.adapter, WinFspFuseCompatAdapter)
        assert life.adapter.operations is ops
        assert life.adapter.to_record()["binding"] == "winfsp_fuse_compat"
        assert ops.lifecycle is MountLifecycleState.READY
        # Adapter dispatches into the same operations object.
        result = life.adapter.dispatch("statfs", path="/")
        assert result.success is True
        # Identity: adapter and lifecycle share one operations instance.
        assert id(life.adapter.operations) == id(ops)
        assert id(life.operations) == id(ops)


def test_fuse_compat_adapter_rejects_non_operations() -> None:
    with pytest.raises(WindowsLifecycleError) as exc_info:
        WinFspFuseCompatAdapter(object())  # type: ignore[arg-type]
    assert exc_info.value.code is WindowsLifecycleErrorCode.VALIDATION


# ---------------------------------------------------------------------------
# Recovery precedes 15-second readiness
# ---------------------------------------------------------------------------


def test_recovery_precedes_ready_within_15_seconds(tmp_path: Path) -> None:
    started = time.monotonic()
    with WindowsMountLifecycle(
        tmp_path / "state-ready",
        mount_id="mount:ready",
        readiness_timeout_seconds=DEFAULT_READINESS_TIMEOUT_SECONDS,
    ) as life:
        receipt = life.mount("/mnt/kvfs-ready", kind=MountRootKind.DIRECTORY)
        elapsed = time.monotonic() - started
        assert receipt.success is True
        assert receipt.ready is True
        assert receipt.recovery_complete is True
        assert elapsed < DEFAULT_READINESS_TIMEOUT_SECONDS
        assert receipt.elapsed_seconds < DEFAULT_READINESS_TIMEOUT_SECONDS
        assert receipt.readiness_timeout_seconds == 15.0

        phases = list(receipt.phases)
        assert WindowsMountPhase.RECOVER.value in phases
        assert WindowsMountPhase.READY.value in phases
        assert phases.index(WindowsMountPhase.RECOVER.value) < phases.index(
            WindowsMountPhase.READY.value
        )
        # Durable ready receipt also records recovery-before-ready.
        ready_payload = win_mod._read_json(life.ready_path)
        assert ready_payload.get("ready") is True
        assert ready_payload.get("recovery_complete") is True
        ready_phases = list(ready_payload.get("phases") or [])
        assert ready_phases.index("recover") < ready_phases.index("ready")

        life.wait_ready(timeout_seconds=1.0)
        assert life.ready is True
        assert life.recovery_complete is True


def test_ready_requires_recovery_complete_flag(tmp_path: Path) -> None:
    with WindowsMountLifecycle(tmp_path / "state-flag") as life:
        life.mount("V:")
        status = life.status()
        assert status.ready is True
        assert status.recovery_complete is True
        # Ready file must not claim ready without recovery_complete.
        payload = win_mod._read_json(life.ready_path)
        assert payload["ready"] is True
        assert payload["recovery_complete"] is True


def test_idempotent_mount_when_already_ready(tmp_path: Path) -> None:
    with WindowsMountLifecycle(tmp_path / "state-idem") as life:
        first = life.mount("U:")
        second = life.mount("U:")
        assert first.success is True
        assert second.success is True
        assert second.detail.get("idempotent") is True
        assert life.ready is True


# ---------------------------------------------------------------------------
# Status / heartbeat bind resources
# ---------------------------------------------------------------------------


def _assert_resources_bound(resources: dict) -> None:
    assert resources["mount_id"]
    assert resources["pid"] > 0
    assert resources["mount_root"]
    assert resources["mount_root_kind"] in ("drive_letter", "directory")
    assert resources["state_directory"]
    assert resources["wal_directory"]
    assert resources["cache_directory"]
    assert resources["runtime_directory"]
    assert resources["process_id"]
    assert resources["state_lease_holder_id"]
    assert resources["resource_lease_holder_id"]


def test_status_and_heartbeat_bind_resources_drive(tmp_path: Path) -> None:
    with WindowsMountLifecycle(
        tmp_path / "state-status-drive",
        mount_id="mount:status-drive",
    ) as life:
        life.mount("T:", kind=MountRootKind.DRIVE_LETTER)
        status = life.status()
        assert status.state is WindowsMountState.READY
        assert status.ready is True
        rec = status.to_record()
        _assert_resources_bound(rec["resources"])
        assert rec["resources"]["drive_letter"] == "T:"
        assert rec["resources"]["pid"] == life.pid
        assert rec["resources"]["state_directory"] == str(life.state_directory)
        assert rec["resources"]["wal_directory"] == str(life.wal_directory)
        assert rec["resources"]["cache_directory"] == str(life.cache_directory)

        hb = life.heartbeat()
        hb_rec = hb.to_record()
        _assert_resources_bound(hb_rec["resources"])
        assert hb_rec["pid"] == life.pid
        assert hb_rec["ready"] is True
        assert hb_rec["process_id"] == life.process_id
        assert life.heartbeat_path.is_file()
        assert life.status_path.is_file()


def test_status_and_heartbeat_bind_resources_directory(tmp_path: Path) -> None:
    mount_dir = "/mnt/kvfs-bind"
    with WindowsMountLifecycle(
        tmp_path / "state-status-dir",
        mount_id="mount:status-dir",
    ) as life:
        life.mount(mount_dir, kind=MountRootKind.DIRECTORY)
        status = life.status()
        resources = status.to_record()["resources"]
        _assert_resources_bound(resources)
        assert resources["directory_path"] == mount_dir
        assert resources["drive_letter"] == ""
        hb = life.heartbeat()
        assert hb.resources.directory_path == mount_dir


# ---------------------------------------------------------------------------
# Exclusive leases
# ---------------------------------------------------------------------------


def test_exclusive_drive_lease_fences_concurrent_mount(tmp_path: Path) -> None:
    lease_root = tmp_path / "shared-leases"
    first = WindowsMountLifecycle(
        tmp_path / "state-a",
        mount_id="mount:a",
        lease_root=lease_root,
        holder_id="holder:a",
    )
    second = WindowsMountLifecycle(
        tmp_path / "state-b",
        mount_id="mount:b",
        lease_root=lease_root,
        holder_id="holder:b",
    )
    try:
        first.mount("S:", kind=MountRootKind.DRIVE_LETTER)
        assert first.resource_lease_held is True
        with pytest.raises(WindowsResourceLeaseError):
            second.mount("S:", kind=MountRootKind.DRIVE_LETTER)
    finally:
        first.close()
        second.close()
    # After release, another mount can acquire.
    third = WindowsMountLifecycle(
        tmp_path / "state-c",
        mount_id="mount:c",
        lease_root=lease_root,
        holder_id="holder:c",
    )
    try:
        receipt = third.mount("S:", kind=MountRootKind.DRIVE_LETTER)
        assert receipt.success is True
    finally:
        third.close()


def test_exclusive_directory_lease_fences_concurrent_mount(
    tmp_path: Path,
) -> None:
    lease_root = tmp_path / "dir-leases"
    path = "/mnt/exclusive-kvfs"
    first = WindowsMountLifecycle(
        tmp_path / "dstate-a",
        lease_root=lease_root,
        holder_id="h-dir-a",
    )
    second = WindowsMountLifecycle(
        tmp_path / "dstate-b",
        lease_root=lease_root,
        holder_id="h-dir-b",
    )
    try:
        first.mount(path, kind=MountRootKind.DIRECTORY)
        with pytest.raises(WindowsResourceLeaseError):
            second.mount(path, kind=MountRootKind.DIRECTORY)
    finally:
        first.close()
        second.close()


# ---------------------------------------------------------------------------
# Stop / crash / repeated unmount release resources + preserve WAL
# ---------------------------------------------------------------------------


def test_stop_releases_resources_and_preserves_wal(tmp_path: Path) -> None:
    state = tmp_path / "state-stop"
    with WindowsMountLifecycle(state, mount_id="mount:stop") as life:
        life.mount("R:")
        assert life.resource_lease_held is True
        assert life.state_lease_held is True
        assert life.worker is not None
        assert life.wal_state_preserved() is True
        marker_before = life.wal_directory.joinpath(
            "wal-preserve.marker"
        ).read_text(encoding="utf-8")

        receipt = life.stop()
        assert receipt.success is True
        assert receipt.state is WindowsMountState.STOPPED
        assert life.ready is False
        assert life.resource_leases_released() is True
        assert life.process_released() is True
        assert life.worker is None
        assert not life.ready_path.exists()
        assert not life.process_path.exists()
        # WAL preserved.
        assert life.wal_state_preserved() is True
        assert life.wal_directory.is_dir()
        assert life.wal_directory.joinpath("wal-preserve.marker").is_file()
        marker_after = life.wal_directory.joinpath(
            "wal-preserve.marker"
        ).read_text(encoding="utf-8")
        assert marker_after == marker_before
        assert receipt.detail.get("wal_preserved") is True


def test_crash_releases_resources_and_preserves_wal(tmp_path: Path) -> None:
    state = tmp_path / "state-crash"
    life = WindowsMountLifecycle(state, mount_id="mount:crash")
    try:
        life.mount("/mnt/crash-kvfs")
        assert life.ready is True
        receipt = life.crash()
        assert receipt.success is True
        assert receipt.state is WindowsMountState.CRASHED
        assert life.ready is False
        assert life.resource_leases_released() is True
        assert life.process_released() is True
        assert life.wal_state_preserved() is True
        assert receipt.detail.get("wal_preserved") is True
        assert "WAL preserved" in receipt.message
    finally:
        life.close()


def test_repeated_unmount_is_idempotent_and_non_hanging(
    tmp_path: Path,
) -> None:
    with WindowsMountLifecycle(tmp_path / "state-repeat") as life:
        life.mount("Q:")
        first = life.unmount()
        assert first.success is True
        # Repeated unmount must not hang the foreground.
        started = time.monotonic()
        second = life.unmount()
        third = life.stop()
        elapsed = time.monotonic() - started
        assert second.success is True
        assert third.success is True
        assert elapsed < 2.0
        assert life.resource_leases_released() is True
        assert life.wal_state_preserved() is True


def test_foreground_does_not_hang_on_worker(tmp_path: Path) -> None:
    """Mount/unmount/status complete without blocking on a FUSE loop."""

    done = threading.Event()
    errors: list[BaseException] = []

    def run() -> None:
        try:
            with WindowsMountLifecycle(tmp_path / "state-hang") as life:
                life.mount("P:")
                for _ in range(5):
                    life.heartbeat()
                    life.status()
                life.unmount()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            done.set()

    thread = threading.Thread(target=run, name="kvfs-601-hang-probe")
    thread.start()
    finished = done.wait(timeout=10.0)
    assert finished is True, "foreground mount path hung beyond 10s"
    thread.join(timeout=1.0)
    assert not errors


def test_stop_timeout_does_not_block_indefinitely(tmp_path: Path) -> None:
    life = WindowsMountLifecycle(
        tmp_path / "state-timeout",
        stop_timeout_seconds=0.5,
    )
    try:
        life.mount("O:")
        started = time.monotonic()
        life.stop()
        assert time.monotonic() - started < 3.0
    finally:
        life.close()


# ---------------------------------------------------------------------------
# Factory / convenience / records
# ---------------------------------------------------------------------------


def test_build_and_mount_windows_helpers(tmp_path: Path) -> None:
    life = build_windows_mount_lifecycle(
        tmp_path / "state-factory",
        mount_id="mount:factory",
        mode="hermetic",
    )
    try:
        receipt = life.mount("N:")
        assert receipt.success is True
        record = life.to_record()
        assert record["task_id"] == "KVFS-601"
        assert record["ready"] is True
        assert record["schema"] == WindowsMountLifecycle_V1
    finally:
        life.close()

    life2, receipt2 = mount_windows(
        "/mnt/helper",
        tmp_path / "state-helper",
        kind=MountRootKind.DIRECTORY,
    )
    try:
        assert receipt2.success is True
        assert life2.ready is True
    finally:
        life2.close()


def test_native_mode_capability_gap_is_typed(tmp_path: Path) -> None:
    """Native mode fails closed with a typed error when WinFsp is absent.

    On hermetic Linux validation WinFsp is unavailable; the lifecycle must
    not hang or silently claim support. When capability is present the
    mount may succeed, but still uses the child/worker path (no foreground
    FUSE hang).
    """

    life = WindowsMountLifecycle(
        tmp_path / "state-native",
        mode=WindowsMountMode.NATIVE,
        readiness_timeout_seconds=5.0,
    )
    try:
        try:
            receipt = life.mount("M:", kind=MountRootKind.DRIVE_LETTER)
        except WindowsLifecycleError as exc:
            # Capability/native failure is typed; never leaves a ready mount.
            assert exc.code in (
                WindowsLifecycleErrorCode.NATIVE,
                WindowsLifecycleErrorCode.INTERNAL,
                WindowsLifecycleErrorCode.RECOVERY,
                WindowsLifecycleErrorCode.LEASE,
            )
            assert life.ready is False
        else:
            # Capability present: still no foreground hang; worker-backed.
            assert receipt.success is True
            assert life.ready is True
            assert life.worker is not None
            assert life.mode is WindowsMountMode.NATIVE
    finally:
        life.close()


def test_wait_ready_fails_when_not_started(tmp_path: Path) -> None:
    with WindowsMountLifecycle(tmp_path / "state-wait") as life:
        with pytest.raises(WindowsReadinessError):
            life.wait_ready(timeout_seconds=0.05)


def test_context_manager_closes_cleanly(tmp_path: Path) -> None:
    with WindowsMountLifecycle(tmp_path / "state-ctx") as life:
        life.mount("L:")
        assert life.ready is True
    assert life.state in (
        WindowsMountState.STOPPED,
        WindowsMountState.CREATED,
    )
    # WAL still on disk after close.
    assert (tmp_path / "state-ctx" / "durable" / "wal-preserve.marker").is_file()
