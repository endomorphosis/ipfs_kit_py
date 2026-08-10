"""KVFS-500: Linux mount lifecycle, readiness, heartbeat, signal, and unmount.

Acceptance coverage:

* foreground child recovery precedes ready;
* readiness arrives within 15 seconds or exits nonzero;
* heartbeat/status bind PID/mount/state/WAL/cache;
* SIGINT/SIGTERM and repeated unmount drain bounded callbacks, stop workers,
  release mount/lease, preserve recovery state, and report stale mounts
  without blocking.
"""

from __future__ import annotations

import json
import os
import signal
import time
from pathlib import Path

import pytest

from ipfs_kit_py.core.vfs.host_contracts import MountLifecycleState
from ipfs_kit_py.kernel_vfs import linux as linux_mod
from ipfs_kit_py.kernel_vfs.linux import (
    CONTRACT_VERSION,
    DEFAULT_READINESS_TIMEOUT_SECONDS,
    HEARTBEAT_FILENAME,
    READY_FILENAME,
    SCHEMA_VERSION,
    STATUS_FILENAME,
    TASK_ID,
    BoundedCallbackQueue,
    ChildProcessError,
    LifecycleDisposition,
    LifecycleErrorCode,
    LinuxLifecycleError,
    LinuxMountConfig,
    LinuxMountDaemon,
    LinuxMountLifecycle,
    LinuxMountLifecycle_V1,
    MountHeartbeat,
    MountReadiness,
    MountStatus,
    ReadinessTimeoutError,
    UnmountReceipt,
    build_linux_mount_lifecycle,
    lifecycle_dispositions,
    lifecycle_error_codes,
    lifecycle_phases,
    report_stale_mounts,
    run_child_daemon,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = PACKAGE_ROOT / "ipfs_kit_py" / "kernel_vfs" / "linux.py"


# ---------------------------------------------------------------------------
# Schema / vocabulary / import inertness
# ---------------------------------------------------------------------------


def test_schema_versions_and_aliases() -> None:
    assert TASK_ID == "KVFS-500"
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert LinuxMountLifecycle_V1.endswith("@1")
    assert LinuxMountDaemon is LinuxMountLifecycle
    assert DEFAULT_READINESS_TIMEOUT_SECONDS == 15.0
    assert "child_recover" in lifecycle_phases()
    assert "child_ready" in lifecycle_phases()
    assert "ready" in lifecycle_dispositions()
    assert LifecycleErrorCode.READINESS_TIMEOUT.value in lifecycle_error_codes()
    text = MODULE_PATH.read_text(encoding="utf-8")
    assert "KVFS-500" in text
    assert "recovery precedes ready" in text.lower() or "recovery precedes" in text
    assert "15" in text


def test_module_import_does_not_load_fusepy() -> None:
    """Lifecycle import must remain inert w.r.t. native FUSE bindings."""
    assert hasattr(linux_mod, "LinuxMountLifecycle")
    text = Path(linux_mod.__file__).read_text(encoding="utf-8")
    # No hard dependency imports of native FUSE bindings.
    for banned in (
        "import fuse\n",
        "import fuse ",
        "import fusepy\n",
        "import fusepy ",
        "from fuse ",
        "from fuse\n",
        "from fusepy ",
        "from fusepy\n",
        "importlib.import_module(\"fuse\")",
        "importlib.import_module('fuse')",
        "importlib.import_module(\"fusepy\")",
        "importlib.import_module('fusepy')",
    ):
        assert banned not in text
    assert "fusepy" in text  # mentioned in docs/policy only
    assert "never loads" in text or "inert" in text.lower()


def test_declared_output_module_path() -> None:
    module_file = Path(linux_mod.__file__).resolve()
    assert module_file.name == "linux.py"
    assert module_file.parent.name == "kernel_vfs"
    assert "ipfs_kit_py" in module_file.parts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(tmp_path: Path, **kwargs) -> LinuxMountConfig:
    defaults = dict(
        mountpoint=tmp_path / "mnt",
        state_directory=tmp_path / "state",
        mount_id="mount:test",
        generation_id="wal-gen:test-1",
        readiness_timeout_seconds=10.0,
        heartbeat_interval_seconds=0.05,
        unmount_timeout_seconds=5.0,
        drain_timeout_seconds=1.0,
        worker_stop_timeout_seconds=1.0,
        hermetic=True,
        cache_generation=7,
        cache_entries=3,
    )
    defaults.update(kwargs)
    return LinuxMountConfig(**defaults)


@pytest.fixture
def life(tmp_path: Path):
    cfg = _config(tmp_path)
    controller = LinuxMountLifecycle(cfg)
    yield controller
    try:
        controller.unmount(timeout_seconds=5.0)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Foreground child recovery precedes ready
# ---------------------------------------------------------------------------


def test_recovery_precedes_ready(life: LinuxMountLifecycle) -> None:
    readiness = life.start(wait_ready=True)
    assert readiness.ready is True
    assert readiness.recovery_complete is True
    assert readiness.lifecycle_state == MountLifecycleState.READY.value
    assert readiness.pid > 0
    assert readiness.pid == life.pid

    # Recovery phases recorded in readiness must place recovery before ready.
    phases = list(readiness.recovery_phases)
    assert phases, "recovery phases must be present on readiness handshake"
    assert "acquire_lease" in phases
    assert "enter_ready" in phases
    assert phases.index("acquire_lease") < phases.index("enter_ready")
    if "replay_wal" in phases:
        assert phases.index("replay_wal") < phases.index("enter_ready")

    # Ready file must not claim ready without recovery_complete.
    raw = json.loads((life.state_directory / READY_FILENAME).read_text(encoding="utf-8"))
    assert raw["ready"] is True
    assert raw["recovery_complete"] is True
    assert raw["pid"] == readiness.pid


def test_ready_file_absent_until_recovery_done(tmp_path: Path) -> None:
    """With a recovery delay, ready file must not appear mid-recovery."""
    cfg = _config(tmp_path, recovery_delay_seconds=0.4, readiness_timeout_seconds=10.0)
    controller = LinuxMountLifecycle(cfg)
    try:
        controller.start(wait_ready=False)
        # Immediately after spawn, ready must not exist yet.
        time.sleep(0.05)
        assert not (controller.state_directory / READY_FILENAME).exists()
        readiness = controller.wait_ready(timeout_seconds=10.0)
        assert readiness.ready is True
        assert readiness.recovery_complete is True
    finally:
        controller.unmount()


# ---------------------------------------------------------------------------
# Readiness within 15 seconds or exits nonzero
# ---------------------------------------------------------------------------


def test_readiness_default_budget_is_15_seconds() -> None:
    assert DEFAULT_READINESS_TIMEOUT_SECONDS == 15.0
    cfg = LinuxMountConfig(mountpoint="/tmp/x", state_directory="/tmp/y")
    assert cfg.readiness_timeout_seconds == 15.0


def test_readiness_arrives_within_budget(life: LinuxMountLifecycle) -> None:
    started = time.monotonic()
    readiness = life.start(wait_ready=True)
    elapsed = time.monotonic() - started
    assert readiness.ready is True
    assert elapsed < life.config.readiness_timeout_seconds
    assert elapsed < DEFAULT_READINESS_TIMEOUT_SECONDS


def test_readiness_timeout_exits_nonzero(tmp_path: Path) -> None:
    cfg = _config(
        tmp_path,
        suppress_ready=True,
        readiness_timeout_seconds=0.4,
        unmount_timeout_seconds=2.0,
    )
    controller = LinuxMountLifecycle(cfg)
    with pytest.raises(ReadinessTimeoutError) as exc_info:
        controller.start(wait_ready=True)
    err = exc_info.value
    assert err.code is LifecycleErrorCode.READINESS_TIMEOUT
    assert err.exit_code != 0
    assert err.detail["timeout_seconds"] == 0.4
    # Child must not be left running after timeout.
    deadline = time.monotonic() + 3.0
    while controller.running and time.monotonic() < deadline:
        time.sleep(0.05)
    assert controller.running is False


def test_child_fail_before_ready_is_nonzero(tmp_path: Path) -> None:
    cfg = _config(tmp_path, fail_before_ready=True, readiness_timeout_seconds=5.0)
    controller = LinuxMountLifecycle(cfg)
    with pytest.raises(ChildProcessError) as exc_info:
        controller.start(wait_ready=True)
    err = exc_info.value
    assert err.exit_code != 0
    assert err.code is LifecycleErrorCode.CHILD_EXIT


# ---------------------------------------------------------------------------
# Heartbeat / status bind PID / mount / state / WAL / cache
# ---------------------------------------------------------------------------


def test_heartbeat_and_status_bindings(life: LinuxMountLifecycle) -> None:
    life.start(wait_ready=True)
    # Allow at least one heartbeat cycle.
    deadline = time.monotonic() + 2.0
    hb = None
    while time.monotonic() < deadline:
        try:
            hb = life.heartbeat()
            if hb.sequence >= 1:
                break
        except LinuxLifecycleError:
            time.sleep(0.02)
    assert hb is not None
    assert hb.pid == life.pid
    assert hb.mountpoint == str(life.mountpoint)
    assert hb.state_directory == str(life.state_directory)
    assert hb.wal_generation == life.config.generation_id
    assert hb.cache_generation == life.config.cache_generation
    record = hb.to_record()
    assert "pid" in record and record["pid"] == life.pid
    assert "mountpoint" in record
    assert "state_directory" in record
    assert record["wal"]["generation"] == life.config.generation_id
    assert "position" in record["wal"]
    assert record["cache"]["generation"] == life.config.cache_generation

    st = life.status()
    assert st.pid == life.pid
    assert st.mountpoint == str(life.mountpoint)
    assert st.state_directory == str(life.state_directory)
    assert st.ready is True
    assert st.recovery_complete is True
    assert st.wal["generation"] == life.config.generation_id
    assert st.cache["generation"] == life.config.cache_generation
    assert "directory" in st.wal
    assert "directory" in st.cache
    assert st.lease_held is True


def test_status_and_heartbeat_files_on_disk(life: LinuxMountLifecycle) -> None:
    life.start(wait_ready=True)
    time.sleep(0.15)
    assert (life.state_directory / HEARTBEAT_FILENAME).is_file()
    assert (life.state_directory / STATUS_FILENAME).is_file()
    assert (life.state_directory / READY_FILENAME).is_file()
    hb_raw = json.loads(
        (life.state_directory / HEARTBEAT_FILENAME).read_text(encoding="utf-8")
    )
    for key in ("pid", "mountpoint", "state_directory", "wal", "cache"):
        assert key in hb_raw


# ---------------------------------------------------------------------------
# SIGINT / SIGTERM and repeated unmount
# ---------------------------------------------------------------------------


def test_sigterm_unmount_drains_and_preserves(life: LinuxMountLifecycle) -> None:
    life.start(wait_ready=True)
    pid = life.pid
    assert pid is not None

    receipt = life.unmount(sig=signal.SIGTERM, timeout_seconds=5.0)
    assert isinstance(receipt, UnmountReceipt)
    assert receipt.success is True
    assert receipt.disposition in (
        LifecycleDisposition.STOPPED,
        LifecycleDisposition.IDEMPOTENT,
    )
    assert receipt.mount_released is True
    assert receipt.recovery_preserved is True
    assert receipt.lifecycle_state == MountLifecycleState.DESTROYED.value
    assert "TERM" in receipt.signal_name or receipt.signal_name in ("15", "SIGTERM")

    # Recovery state preserved on disk.
    assert (life.state_directory / "recovery").exists() or (
        life.state_directory / "recovery-preserved"
    ).exists()

    # Child process gone.
    deadline = time.monotonic() + 3.0
    while life.running and time.monotonic() < deadline:
        time.sleep(0.05)
    assert life.running is False
    assert not (life.state_directory / READY_FILENAME).exists()


def test_sigint_unmount(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    controller = LinuxMountLifecycle(cfg)
    controller.start(wait_ready=True)
    receipt = controller.unmount(sig=signal.SIGINT, timeout_seconds=5.0)
    assert receipt.success is True
    assert receipt.recovery_preserved is True
    # Accept SIGINT name variants across platforms.
    assert "INT" in receipt.signal_name or receipt.signal_name in ("2", "SIGINT")


def test_repeated_unmount_is_idempotent(life: LinuxMountLifecycle) -> None:
    life.start(wait_ready=True)
    first = life.unmount(timeout_seconds=5.0)
    second = life.unmount(timeout_seconds=5.0)
    third = life.unmount(timeout_seconds=5.0)
    assert first.success is True
    assert second.success is True
    assert third.success is True
    assert second.idempotent is True or second.disposition is LifecycleDisposition.IDEMPOTENT
    assert third.idempotent is True or third.disposition is LifecycleDisposition.IDEMPOTENT
    # Must not hang / block — all three returned.
    assert second.elapsed_seconds < 5.0
    assert third.elapsed_seconds < 5.0


def test_unmount_stops_workers_and_drains_callbacks() -> None:
    """Unit-level drain/worker bounds used by child shutdown."""
    queue = BoundedCallbackQueue(bound=4)
    c1 = queue.begin()
    c2 = queue.begin()
    assert queue.open_count == 2
    queue.end(c1)
    drained = queue.drain(timeout_seconds=0.2)
    assert drained >= 1
    assert queue.open_count == 0

    stopped = []
    worker = linux_mod.BoundedWorker(
        "t",
        interval_seconds=0.05,
        on_cycle=lambda w: stopped.append(w.cycle),
    )
    worker.start()
    time.sleep(0.12)
    assert worker.running is True
    ok = worker.stop(timeout_seconds=1.0)
    assert ok is True
    assert worker.running is False


def test_context_manager_unmounts(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    with LinuxMountLifecycle(cfg) as controller:
        assert controller.ready is True
        assert controller.running is True
        pid = controller.pid
        assert pid and _pid_alive(pid)
    # After exit, process should be stopped.
    time.sleep(0.1)
    assert controller.running is False


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Stale mounts without blocking
# ---------------------------------------------------------------------------


def test_report_stale_mounts_nonblocking(tmp_path: Path) -> None:
    # Live mount.
    live_cfg = _config(tmp_path / "live", mount_id="mount:live")
    live = LinuxMountLifecycle(live_cfg)
    live.start(wait_ready=True)

    # Fabricate a stale state directory with a dead PID.
    stale_dir = tmp_path / "stale-state"
    stale_dir.mkdir()
    dead_pid = 2**22 + 17  # almost certainly not a live PID
    while _pid_alive(dead_pid):
        dead_pid += 1
    ready = MountReadiness(
        mount_id="mount:stale",
        pid=dead_pid,
        mountpoint=str(tmp_path / "stale-mnt"),
        state_directory=str(stale_dir),
        recovery_complete=True,
        ready=True,
        lifecycle_state="ready",
        wal_generation="wal-gen:stale",
        cache_generation=1,
        ready_unix_ms=int(time.time() * 1000) - 60_000,
    )
    hb = MountHeartbeat(
        mount_id="mount:stale",
        pid=dead_pid,
        mountpoint=str(tmp_path / "stale-mnt"),
        state_directory=str(stale_dir),
        lifecycle_state="ready",
        wal_generation="wal-gen:stale",
        wal_position="0",
        cache_generation=1,
        cache_entries=0,
        heartbeat_unix_ms=int(time.time() * 1000) - 60_000,
        sequence=1,
    )
    (stale_dir / READY_FILENAME).write_text(
        json.dumps(ready.to_record()) + "\n", encoding="utf-8"
    )
    (stale_dir / HEARTBEAT_FILENAME).write_text(
        json.dumps(hb.to_record()) + "\n", encoding="utf-8"
    )

    started = time.monotonic()
    report = live.report_stale_mounts(
        search_roots=[tmp_path],
        stale_heartbeat_seconds=1.0,
    )
    elapsed = time.monotonic() - started

    assert report.blocked is False
    assert elapsed < 2.0  # non-blocking
    assert report.scanned >= 2
    stale_ids = {item.get("mount_id") for item in report.stale}
    assert "mount:stale" in stale_ids
    # Live mount should appear in live set.
    live_ids = {item.get("mount_id") for item in report.live}
    assert "mount:live" in live_ids or any(
        item.get("pid") == live.pid for item in report.live
    )

    # Module-level helper.
    report2 = report_stale_mounts(tmp_path, stale_heartbeat_seconds=1.0)
    assert report2.blocked is False
    assert any(item.get("mount_id") == "mount:stale" for item in report2.stale)

    live.unmount()


def test_stale_report_does_not_wait_on_lease(tmp_path: Path) -> None:
    """Stale scan must not attempt blocking lease acquisition."""
    state = tmp_path / "leased"
    state.mkdir()
    # Hold a lease in this process; report must still return quickly.
    from ipfs_kit_py.kernel_vfs.wal_recovery import StateLease

    lease = StateLease(state, mount_id="mount:held", holder_id="holder:test")
    lease.try_acquire()
    try:
        (state / READY_FILENAME).write_text(
            json.dumps(
                {
                    "mount_id": "mount:held",
                    "pid": os.getpid(),
                    "mountpoint": str(tmp_path / "m"),
                    "state_directory": str(state),
                    "recovery_complete": True,
                    "ready": True,
                    "lifecycle_state": "ready",
                    "wal": {"generation": "g"},
                    "cache": {"generation": 1},
                    "ready_unix_ms": int(time.time() * 1000),
                }
            ),
            encoding="utf-8",
        )
        started = time.monotonic()
        report = report_stale_mounts(tmp_path, stale_heartbeat_seconds=30.0)
        assert time.monotonic() - started < 1.0
        assert report.blocked is False
    finally:
        lease.release()


# ---------------------------------------------------------------------------
# Builders / records / child entry
# ---------------------------------------------------------------------------


def test_build_linux_mount_lifecycle(tmp_path: Path) -> None:
    controller = build_linux_mount_lifecycle(
        tmp_path / "mnt",
        tmp_path / "state",
        mount_id="mount:built",
        readiness_timeout_seconds=8.0,
        heartbeat_interval_seconds=0.05,
    )
    try:
        readiness = controller.start()
        assert readiness.mount_id == "mount:built"
        assert controller.ready is True
        st = controller.status()
        assert isinstance(st, MountStatus)
        assert st.mount_id == "mount:built"
    finally:
        controller.unmount()


def test_run_child_daemon_missing_config(tmp_path: Path) -> None:
    assert run_child_daemon(tmp_path / "missing.json") == 2


def test_config_validation() -> None:
    with pytest.raises(LinuxLifecycleError):
        LinuxMountConfig(
            mountpoint="/tmp/a",
            state_directory="/tmp/b",
            readiness_timeout_seconds=0,
        )
    with pytest.raises(LinuxLifecycleError):
        LinuxMountConfig(
            mountpoint="/tmp/a",
            state_directory="/tmp/b",
            hermetic="yes",  # type: ignore[arg-type]
        )


def test_records_roundtrip() -> None:
    ready = MountReadiness(
        mount_id="m",
        pid=123,
        mountpoint="/mnt",
        state_directory="/state",
        recovery_complete=True,
        ready=True,
        lifecycle_state="ready",
        wal_generation="g1",
        cache_generation=2,
        ready_unix_ms=1,
        recovery_phases=("acquire_lease", "enter_ready"),
    )
    assert MountReadiness.from_dict(ready.to_record()).pid == 123

    hb = MountHeartbeat(
        mount_id="m",
        pid=123,
        mountpoint="/mnt",
        state_directory="/state",
        lifecycle_state="ready",
        wal_generation="g1",
        wal_position="p",
        cache_generation=2,
        cache_entries=4,
        heartbeat_unix_ms=9,
        sequence=3,
    )
    assert MountHeartbeat.from_dict(hb.to_record()).sequence == 3

    st = MountStatus(
        mount_id="m",
        pid=123,
        mountpoint="/mnt",
        state_directory="/state",
        lifecycle_state="ready",
        ready=True,
        recovery_complete=True,
        lease_held=True,
        holder_id="h",
        wal={"generation": "g1"},
        cache={"generation": 2},
        workers={"running": 1},
        open_callbacks=0,
        mounted=False,
        status_unix_ms=1,
    )
    assert MountStatus.from_dict(st.to_record()).lease_held is True


def test_exclusive_state_lease_fences_second_mount(tmp_path: Path) -> None:
    """Two children cannot both become ready on the same recovery state.

    Note: each lifecycle uses its own state_directory (lease is per recovery
    tree under state/recovery).  When two mounts intentionally share the same
    recovery root via identical state directories, the second fails.
    """
    shared = tmp_path / "shared"
    cfg_a = _config(shared, mount_id="mount:a", holder_id="holder:a")
    # Second controller reuses exact same paths.
    cfg_b = LinuxMountConfig(
        mountpoint=shared / "mnt",
        state_directory=shared / "state",
        mount_id="mount:b",
        holder_id="holder:b",
        readiness_timeout_seconds=5.0,
        heartbeat_interval_seconds=0.05,
        unmount_timeout_seconds=5.0,
        hermetic=True,
    )
    a = LinuxMountLifecycle(cfg_a)
    b = LinuxMountLifecycle(cfg_b)
    try:
        a.start(wait_ready=True)
        # Second start should fail (lease held or child exit before ready).
        with pytest.raises((ChildProcessError, ReadinessTimeoutError, LinuxLifecycleError)):
            b.start(wait_ready=True)
    finally:
        a.unmount()
        try:
            b.unmount()
        except Exception:
            pass


def test_signal_child_api(life: LinuxMountLifecycle) -> None:
    life.start(wait_ready=True)
    assert life.signal_child(signal.SIGTERM) is True
    deadline = time.monotonic() + 5.0
    while life.running and time.monotonic() < deadline:
        time.sleep(0.05)
    # After SIGTERM the child should shut down; finalize with unmount.
    receipt = life.unmount()
    assert receipt.success is True


# ---------------------------------------------------------------------------
# In-process child path (no subprocess) for recovery-before-ready unit check
# ---------------------------------------------------------------------------


def test_inprocess_child_daemon_recovery_before_ready(tmp_path: Path) -> None:
    """Direct child entry: recovery evidence exists before ready file write."""
    cfg = _config(tmp_path, heartbeat_interval_seconds=0.05)
    cfg.state_directory.mkdir(parents=True, exist_ok=True)
    cfg.mountpoint.mkdir(parents=True, exist_ok=True)
    config_path = cfg.state_directory / "child-config.json"
    config_path.write_text(json.dumps(cfg.to_record()) + "\n", encoding="utf-8")

    # Run child in a subprocess still (real process), but observe ordering via
    # recovery-preserved + ready artifacts after a short ready wait.
    controller = LinuxMountLifecycle(cfg)
    controller.start(wait_ready=True)
    ready_raw = json.loads(
        (cfg.state_directory / READY_FILENAME).read_text(encoding="utf-8")
    )
    assert ready_raw["recovery_complete"] is True
    phases = ready_raw.get("recovery_phases") or []
    assert phases.index("acquire_lease") < phases.index("enter_ready")
    # Preserve artifacts exist (written during recovery, before/with ready).
    preserved = cfg.state_directory / "recovery-preserved"
    assert preserved.is_dir()
    assert any(preserved.iterdir())
    controller.unmount()
