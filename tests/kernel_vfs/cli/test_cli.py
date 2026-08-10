"""KVFS-702: mount/doctor/status/unmount CLI, status schema, observability.

Acceptance coverage:

* doctor/mount/unmount/status have machine JSON and human output;
* foreground mode;
* explicit safe options;
* bounded readiness/stop timeouts;
* PID/lease validation and idempotent cleanup;
* status exposes platform, mount, recovery/WAL, ARC, handles, errors and
  heartbeat without secrets or high-cardinality paths.
"""

from __future__ import annotations

import io
import json
import os
import signal
import time
from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.cli import kernel_vfs as cli
from ipfs_kit_py.kernel_vfs import status as status_mod
from ipfs_kit_py.kernel_vfs.linux import (
    DEFAULT_READINESS_TIMEOUT_SECONDS,
    LinuxMountConfig,
    LinuxMountLifecycle,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
CLI_MODULE = PACKAGE_ROOT / "ipfs_kit_py" / "cli" / "kernel_vfs.py"
STATUS_MODULE = PACKAGE_ROOT / "ipfs_kit_py" / "kernel_vfs" / "status.py"


# ---------------------------------------------------------------------------
# Declared outputs / schema identity
# ---------------------------------------------------------------------------


def test_declared_output_modules_exist() -> None:
    assert CLI_MODULE.is_file()
    assert STATUS_MODULE.is_file()
    assert Path(__file__).resolve().is_file()


def test_task_and_schema_identity() -> None:
    assert cli.TASK_ID == "KVFS-702"
    assert cli.CLI_SCHEMA == "KernelVFSCLI@1"
    assert status_mod.TASK_ID == "KVFS-702"
    assert status_mod.STATUS_SCHEMA.endswith("@1")
    assert status_mod.KernelVFSStatus_V1 == status_mod.STATUS_SCHEMA
    assert "platform" in status_mod.REQUIRED_STATUS_SECTIONS
    assert "mount" in status_mod.REQUIRED_STATUS_SECTIONS
    assert "recovery" in status_mod.REQUIRED_STATUS_SECTIONS
    assert "wal" in status_mod.REQUIRED_STATUS_SECTIONS
    assert "arc" in status_mod.REQUIRED_STATUS_SECTIONS
    assert "handles" in status_mod.REQUIRED_STATUS_SECTIONS
    assert "errors" in status_mod.REQUIRED_STATUS_SECTIONS
    assert "heartbeat" in status_mod.REQUIRED_STATUS_SECTIONS


def test_cli_module_documents_acceptance_surface() -> None:
    text = CLI_MODULE.read_text(encoding="utf-8")
    assert "KVFS-702" in text
    assert "foreground" in text
    assert "readiness" in text
    assert "allow_other" in text
    assert "idempotent" in text.lower() or "Idempotent" in text


# ---------------------------------------------------------------------------
# Parser surface
# ---------------------------------------------------------------------------


def test_parser_exposes_doctor_mount_status_unmount() -> None:
    parser = cli.build_parser()
    # Subparsers registered.
    actions = {a.dest: a for a in parser._actions if getattr(a, "dest", None)}
    assert "command" in actions
    for command in ("doctor", "mount", "status", "unmount"):
        # parse_args with --help would exit; instead parse minimal.
        if command == "doctor":
            args = parser.parse_args([command, "--json"])
        elif command == "status":
            args = parser.parse_args([command, "--state-dir", "/tmp/x", "--json"])
        elif command == "unmount":
            args = parser.parse_args([command, "--state-dir", "/tmp/x", "--json"])
        else:
            args = parser.parse_args(
                [
                    command,
                    "--mountpoint",
                    "/tmp/m",
                    "--state-dir",
                    "/tmp/s",
                    "--no-foreground",
                    "--json",
                ]
            )
        assert args.command == command


def test_mount_parser_has_foreground_readiness_timeouts_and_safe_options() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "mount",
            "--mountpoint",
            "/mnt/x",
            "--state-dir",
            "/var/x",
            "--foreground",
            "--readiness",
            "--readiness-timeout",
            "10",
            "--stop-timeout",
            "3",
            "-o",
            "ro",
            "-o",
            "fsname=ipfs",
            "--json",
        ]
    )
    assert args.foreground is True
    assert args.readiness is True
    assert args.readiness_timeout == 10.0
    assert args.stop_timeout == 3.0
    assert args.options == ["ro", "fsname=ipfs"]


# ---------------------------------------------------------------------------
# Safe options
# ---------------------------------------------------------------------------


def test_safe_options_admit_allowlist_and_default_permissions() -> None:
    result = cli.admit_safe_mount_options(["ro", "fsname=ipfs-kit", "max_read=65536"])
    assert "default_permissions" in result.admitted
    assert "ro" in result.admitted
    assert "fsname=ipfs-kit" in result.admitted
    assert any(item.startswith("max_read=") for item in result.admitted)
    assert result.allow_other is False


def test_safe_options_reject_injection_and_forbidden() -> None:
    with pytest.raises(cli.OptionValidationError) as exc:
        cli.admit_safe_mount_options(["allow_root"])
    assert exc.value.code == "OPTION_FORBIDDEN"

    with pytest.raises(cli.OptionValidationError) as exc2:
        cli.admit_safe_mount_options(["modules=evil"])
    assert exc2.value.code in {"OPTION_FORBIDDEN", "OPTION_NOT_ALLOWLISTED"}

    with pytest.raises(cli.OptionValidationError) as exc3:
        cli.admit_safe_mount_options(["ro;id"])
    assert exc3.value.code == "OPTION_INJECTION"

    with pytest.raises(cli.OptionValidationError) as exc4:
        cli.admit_safe_mount_options(["unknown_opt"])
    assert exc4.value.code == "OPTION_NOT_ALLOWLISTED"


def test_allow_other_requires_explicit_opt_in_and_warning() -> None:
    with pytest.raises(cli.OptionValidationError) as exc:
        cli.admit_safe_mount_options(
            ["allow_other"],
            allow_other_explicit=False,
        )
    assert exc.value.code == "ALLOW_OTHER_NOT_EXPLICIT"

    with pytest.raises(cli.OptionValidationError) as exc2:
        cli.admit_safe_mount_options(
            ["allow_other"],
            allow_other_explicit=True,
            acknowledge_allow_other_warning=False,
        )
    assert exc2.value.code == "ALLOW_OTHER_WARNING_REQUIRED"

    ok = cli.admit_safe_mount_options(
        ["allow_other"],
        allow_other_explicit=True,
        acknowledge_allow_other_warning=True,
    )
    assert ok.allow_other is True
    assert "allow_other" in ok.admitted
    assert ok.warnings


# ---------------------------------------------------------------------------
# Bounded timeouts
# ---------------------------------------------------------------------------


def test_readiness_and_stop_timeouts_are_bounded() -> None:
    assert cli.bound_readiness_timeout(None) == cli.DEFAULT_READINESS_TIMEOUT_SECONDS
    assert cli.bound_readiness_timeout(10.0) == 10.0
    assert cli.MAX_READINESS_TIMEOUT_SECONDS == DEFAULT_READINESS_TIMEOUT_SECONDS == 15.0
    with pytest.raises(cli.TimeoutBoundError) as exc:
        cli.bound_readiness_timeout(30.0)
    assert exc.value.code == "READINESS_TIMEOUT_BOUND"

    assert cli.bound_stop_timeout(None) == cli.DEFAULT_STOP_TIMEOUT_SECONDS
    assert cli.bound_stop_timeout(5.0) == 5.0
    with pytest.raises(cli.TimeoutBoundError):
        cli.bound_stop_timeout(100.0)

    # Doctor budget hard-caps at 5s.
    assert cli.bound_doctor_budget(10.0) == cli.MAX_DOCTOR_BUDGET_SECONDS


# ---------------------------------------------------------------------------
# Status schema / observability
# ---------------------------------------------------------------------------


def test_status_redacts_secrets_and_suppresses_high_cardinality() -> None:
    dirty = {
        "schema": status_mod.STATUS_SCHEMA,
        "platform": {"name": "linux"},
        "mount": {"mount_id": "mount:1", "api_key": "super-secret"},
        "recovery": {"recovery_complete": True},
        "wal": {"generation": "g1"},
        "arc": {"generation": 1, "entries": 2},
        "handles": {"open_handles": 0},
        "errors": [],
        "heartbeat": {"sequence": 1},
        "paths": ["/a", "/b", "/c"],
        "nested": {
            "access_token": "tok",
            "path_stats": {"/hot/1": 1, "/hot/2": 2, "/hot/3": 3},
        },
        "note": "Authorization: Bearer abc.def.ghi",
    }
    cleaned = status_mod.sanitize_status_payload(dirty)
    assert cleaned["mount"]["api_key"] == status_mod.REDACTED
    assert cleaned["nested"]["access_token"] == status_mod.REDACTED
    assert cleaned["note"] == status_mod.REDACTED
    assert cleaned["paths"]["suppressed"] is True
    assert cleaned["paths"]["count"] == 3
    assert cleaned["nested"]["path_stats"]["suppressed"] is True
    encoded = json.dumps(cleaned)
    assert "super-secret" not in encoded
    assert "abc.def" not in encoded


def test_build_status_exposes_required_sections_without_secrets() -> None:
    status = status_mod.build_status_from_lifecycle_records(
        status_raw={
            "mount_id": "mount:t",
            "pid": os.getpid(),
            "mountpoint": "/mnt/t",
            "state_directory": "/var/t",
            "lifecycle_state": "ready",
            "ready": True,
            "recovery_complete": True,
            "lease_held": True,
            "holder_id": "holder:1",
            "mounted": True,
            "wal": {"generation": "wal-gen:1", "position": "p0", "directory": "/var/t/wal"},
            "cache": {"generation": 7, "entries": 3, "directory": "/var/t/cache"},
            "workers": {"running": 1},
            "open_callbacks": 2,
            "status_unix_ms": int(time.time() * 1000),
            "heartbeat_unix_ms": int(time.time() * 1000),
        },
        heartbeat_raw={
            "pid": os.getpid(),
            "sequence": 4,
            "heartbeat_unix_ms": int(time.time() * 1000),
            "workers_running": 1,
            "open_callbacks": 2,
            "wal": {"generation": "wal-gen:1", "position": "p0"},
            "cache": {"generation": 7, "entries": 3},
        },
        readiness_raw={
            "ready": True,
            "recovery_complete": True,
            "recovery_phases": ["acquire_lease", "replay_wal", "enter_ready"],
        },
    )
    record = status.to_record()
    for section in status_mod.REQUIRED_STATUS_SECTIONS:
        assert section in record
    assert record["platform"]["name"]
    assert record["mount"]["mount_id"] == "mount:t"
    assert record["mount"]["pid"] == os.getpid()
    assert record["recovery"]["recovery_complete"] is True
    assert record["wal"]["generation"] == "wal-gen:1"
    assert record["arc"]["generation"] == 7
    assert record["handles"]["open_handles"] == 2
    assert record["heartbeat"]["sequence"] == 4
    assert isinstance(record["errors"], list)
    problems = status_mod.validate_status_record(record)
    assert problems == []
    status_mod.assert_no_secrets(record)
    human = status_mod.format_status_human(status)
    assert "platform" in human.lower() or "Platform" in human or "linux" in human.lower()
    assert "wal" in human.lower()
    assert "arc" in human.lower()
    assert "heartbeat" in human.lower()


# ---------------------------------------------------------------------------
# Doctor command
# ---------------------------------------------------------------------------


def test_doctor_json_and_human_output() -> None:
    out = io.StringIO()
    err = io.StringIO()
    rc = cli.run(["doctor", "--json"], stdout=out, stderr=err)
    # Doctor exits 0 when the probe completes (capability may still be absent).
    assert rc == 0, err.getvalue() + out.getvalue()
    payload = json.loads(out.getvalue())
    assert payload["command"] == "doctor"
    assert payload["schema"] == cli.CLI_SCHEMA
    assert payload["task_id"] == "KVFS-702"
    assert payload["mounted"] is False
    assert "doctor" in payload
    assert isinstance(payload["doctor"], dict)

    out_h = io.StringIO()
    rc_h = cli.run(["doctor"], stdout=out_h, stderr=err)
    assert rc_h == 0
    text = out_h.getvalue()
    assert "doctor" in text.lower() or "Kernel VFS doctor" in text
    assert "mounted" in text.lower() or "available" in text.lower() or "support" in text.lower()


def test_doctor_never_claims_mounted() -> None:
    envelope = cli.cmd_doctor(cli.build_parser().parse_args(["doctor", "--json"]))
    assert envelope["mounted"] is False


# ---------------------------------------------------------------------------
# Mount / status / unmount integration (hermetic lifecycle)
# ---------------------------------------------------------------------------


def _mount_argv(tmp_path: Path, *extra: str) -> list[str]:
    mountpoint = tmp_path / "mnt"
    state = tmp_path / "state"
    mountpoint.mkdir()
    state.mkdir()
    argv = [
        "mount",
        "--mountpoint",
        str(mountpoint),
        "--state-dir",
        str(state),
        "--no-foreground",
        "--readiness",
        "--readiness-timeout",
        "10",
        "--stop-timeout",
        "5",
        "--hermetic",
        "--mount-id",
        "mount:cli-test",
        *extra,
    ]
    return argv


def test_mount_status_unmount_json_and_human(tmp_path: Path) -> None:
    # Mount (non-foreground so the test returns after readiness).
    out = io.StringIO()
    err = io.StringIO()
    rc = cli.run(_mount_argv(tmp_path, "--json"), stdout=out, stderr=err)
    assert rc == 0, err.getvalue() + out.getvalue()
    mount_payload = json.loads(out.getvalue())
    assert mount_payload["ok"] is True
    assert mount_payload["command"] == "mount"
    assert mount_payload["ready"] is True
    assert mount_payload["recovery_complete"] is True
    assert mount_payload["foreground"] is False
    assert mount_payload["pid"]
    assert "status" in mount_payload
    status = mount_payload["status"]
    for section in status_mod.REQUIRED_STATUS_SECTIONS:
        assert section in status
    assert status["wal"]["generation"]
    assert "generation" in status["arc"]
    assert "open_handles" in status["handles"] or "open_callbacks" in status["handles"]
    assert "sequence" in status["heartbeat"] or "heartbeat_unix_ms" in status["heartbeat"]
    status_mod.assert_no_secrets(status)

    state_dir = tmp_path / "state"

    # Status JSON.
    out_s = io.StringIO()
    rc_s = cli.run(
        ["status", "--state-dir", str(state_dir), "--json"],
        stdout=out_s,
        stderr=err,
    )
    assert rc_s == 0, out_s.getvalue() + err.getvalue()
    status_payload = json.loads(out_s.getvalue())
    assert status_payload["command"] == "status"
    assert "status" in status_payload
    assert status_payload["status"]["mount"]["mount_id"] == "mount:cli-test"
    assert status_payload["status"]["platform"]
    assert status_payload["status"]["recovery"]["recovery_complete"] is True

    # Status human.
    out_sh = io.StringIO()
    rc_sh = cli.run(
        ["status", "--state-dir", str(state_dir)],
        stdout=out_sh,
        stderr=err,
    )
    assert rc_sh == 0
    human = out_sh.getvalue()
    assert "mount" in human.lower()
    assert "wal" in human.lower()
    assert "arc" in human.lower() or "generation" in human.lower()
    assert "heartbeat" in human.lower()

    # Unmount JSON.
    out_u = io.StringIO()
    rc_u = cli.run(
        ["unmount", "--state-dir", str(state_dir), "--json", "--stop-timeout", "5"],
        stdout=out_u,
        stderr=err,
    )
    assert rc_u == 0, out_u.getvalue() + err.getvalue()
    unmount_payload = json.loads(out_u.getvalue())
    assert unmount_payload["ok"] is True
    assert unmount_payload["command"] == "unmount"
    assert unmount_payload["success"] is True
    assert "pid_validation" in unmount_payload or "pid_validation" in (
        unmount_payload.get("unmount") or {}
    )

    # Idempotent second unmount.
    out_u2 = io.StringIO()
    rc_u2 = cli.run(
        ["unmount", "--state-dir", str(state_dir), "--json"],
        stdout=out_u2,
        stderr=err,
    )
    assert rc_u2 == 0
    second = json.loads(out_u2.getvalue())
    assert second["ok"] is True
    assert second["success"] is True
    # Second call should be idempotent (or still successful cleanup).
    assert second.get("idempotent") is True or second["success"] is True

    # Human unmount.
    out_uh = io.StringIO()
    rc_uh = cli.run(
        ["unmount", "--state-dir", str(state_dir)],
        stdout=out_uh,
        stderr=err,
    )
    assert rc_uh == 0
    assert "unmount" in out_uh.getvalue().lower()


def test_mount_human_output(tmp_path: Path) -> None:
    out = io.StringIO()
    err = io.StringIO()
    rc = cli.run(_mount_argv(tmp_path), stdout=out, stderr=err)
    assert rc == 0, err.getvalue() + out.getvalue()
    text = out.getvalue()
    assert "mount" in text.lower()
    assert "ready" in text.lower()
    # Cleanup.
    state = tmp_path / "state"
    cli.run(["unmount", "--state-dir", str(state), "--json"], stdout=io.StringIO(), stderr=err)


def test_mount_rejects_state_mount_overlap(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    shared.mkdir()
    out = io.StringIO()
    err = io.StringIO()
    rc = cli.run(
        [
            "mount",
            "--mountpoint",
            str(shared),
            "--state-dir",
            str(shared),
            "--no-foreground",
            "--json",
        ],
        stdout=out,
        stderr=err,
    )
    assert rc != 0
    payload = json.loads(out.getvalue())
    assert payload["ok"] is False
    assert payload["code"] == "STATE_MOUNT_OVERLAP"


def test_mount_rejects_unsafe_option_via_cli(tmp_path: Path) -> None:
    out = io.StringIO()
    err = io.StringIO()
    rc = cli.run(
        _mount_argv(tmp_path, "--json", "-o", "allow_root"),
        stdout=out,
        stderr=err,
    )
    assert rc != 0
    payload = json.loads(out.getvalue())
    assert payload["ok"] is False
    assert "OPTION" in payload["code"] or "option" in payload["message"].lower()


def test_mount_mirrors_ready_dir(tmp_path: Path) -> None:
    mountpoint = tmp_path / "mnt"
    state = tmp_path / "state"
    ready = tmp_path / "ready"
    wal = tmp_path / "wal"
    cache = tmp_path / "cache"
    mountpoint.mkdir()
    state.mkdir()
    ready.mkdir()
    wal.mkdir()
    cache.mkdir()
    out = io.StringIO()
    err = io.StringIO()
    rc = cli.run(
        [
            "mount",
            "--mountpoint",
            str(mountpoint),
            "--state-dir",
            str(state),
            "--wal-dir",
            str(wal),
            "--cache-dir",
            str(cache),
            "--ready-dir",
            str(ready),
            "--no-foreground",
            "--json",
            "--hermetic",
        ],
        stdout=out,
        stderr=err,
    )
    assert rc == 0, err.getvalue() + out.getvalue()
    assert (state / "ready.json").is_file()
    assert (ready / "ready.json").exists()
    cli.run(
        ["unmount", "--state-dir", str(state), "--json"],
        stdout=io.StringIO(),
        stderr=err,
    )


def test_unmount_missing_state_is_idempotent(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-state"
    out = io.StringIO()
    rc = cli.run(
        ["unmount", "--state-dir", str(missing), "--json"],
        stdout=out,
        stderr=io.StringIO(),
    )
    assert rc == 0
    payload = json.loads(out.getvalue())
    assert payload["ok"] is True
    assert payload["idempotent"] is True


def test_pid_validation_reports_stale(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    # Fake a dead PID in status/heartbeat.
    dead_pid = 2**22  # unlikely to be alive
    while True:
        try:
            os.kill(dead_pid, 0)
            dead_pid += 1
            if dead_pid > 2**22 + 1000:
                break
        except ProcessLookupError:
            break
        except OSError:
            break
    (state / "status.json").write_text(
        json.dumps(
            {
                "mount_id": "mount:stale",
                "pid": dead_pid,
                "mountpoint": str(tmp_path / "mnt"),
                "state_directory": str(state),
                "lifecycle_state": "ready",
                "ready": True,
                "recovery_complete": True,
                "lease_held": True,
                "holder_id": "holder:stale",
                "wal": {"generation": "g"},
                "cache": {"generation": 1},
                "workers": {},
                "open_callbacks": 0,
                "mounted": True,
                "status_unix_ms": int(time.time() * 1000),
            }
        ),
        encoding="utf-8",
    )
    (state / "heartbeat.json").write_text(
        json.dumps(
            {
                "mount_id": "mount:stale",
                "pid": dead_pid,
                "mountpoint": str(tmp_path / "mnt"),
                "state_directory": str(state),
                "lifecycle_state": "ready",
                "wal": {"generation": "g", "position": "p"},
                "cache": {"generation": 1, "entries": 0},
                "heartbeat_unix_ms": int(time.time() * 1000) - 60_000,
                "sequence": 1,
            }
        ),
        encoding="utf-8",
    )

    validation = cli._validate_pid_and_lease(state)
    assert validation["recorded_pid"] == dead_pid
    assert validation["pid_alive"] is False
    assert validation["stale"] is True

    out = io.StringIO()
    rc = cli.run(
        ["status", "--state-dir", str(state), "--json"],
        stdout=out,
        stderr=io.StringIO(),
    )
    # Status always exits 0 when a report is produced; ok may be false for stale PID.
    assert rc == 0
    payload = json.loads(out.getvalue())
    assert payload["command"] == "status"
    assert payload["status"]["mount"]["pid"] == dead_pid
    assert payload["status"]["mount"]["pid_alive"] is False
    assert payload.get("ok") is False or payload["status"].get("ok") is False
    errors = payload["status"]["errors"]
    assert any(
        isinstance(e, dict) and e.get("code") == "STALE_PID" for e in errors
    )

    # Unmount against stale state is still successful / idempotent cleanup.
    out_u = io.StringIO()
    rc_u = cli.run(
        ["unmount", "--state-dir", str(state), "--json"],
        stdout=out_u,
        stderr=io.StringIO(),
    )
    assert rc_u == 0
    unmount = json.loads(out_u.getvalue())
    assert unmount["ok"] is True


def test_unmount_preserves_recovery_state(tmp_path: Path) -> None:
    out = io.StringIO()
    err = io.StringIO()
    rc = cli.run(_mount_argv(tmp_path, "--json"), stdout=out, stderr=err)
    assert rc == 0, err.getvalue()
    state = tmp_path / "state"
    assert (state / "recovery").exists() or (state / "recovery-preserved").exists()
    out_u = io.StringIO()
    rc_u = cli.run(
        ["unmount", "--state-dir", str(state), "--json"],
        stdout=out_u,
        stderr=err,
    )
    assert rc_u == 0
    payload = json.loads(out_u.getvalue())
    unmount = payload.get("unmount") or {}
    # Recovery tree must remain after unmount.
    assert (state / "recovery").exists() or (state / "recovery-preserved").exists()
    if "recovery_preserved" in unmount:
        assert unmount["recovery_preserved"] is True


def test_foreground_flag_defaults_true() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(
        ["mount", "--mountpoint", "/m", "--state-dir", "/s"]
    )
    assert args.foreground is True
    args2 = parser.parse_args(
        ["mount", "--mountpoint", "/m", "--state-dir", "/s", "--no-foreground"]
    )
    assert args2.foreground is False


def test_main_entry_point_doctor() -> None:
    # main() is the console script target.
    rc = cli.main(["doctor", "--json"])
    assert rc == 0


def test_collect_status_from_live_lifecycle(tmp_path: Path) -> None:
    """Status collector reads live lifecycle receipts without secrets."""
    mountpoint = tmp_path / "mnt"
    state = tmp_path / "state"
    mountpoint.mkdir()
    state.mkdir()
    life = LinuxMountLifecycle(
        LinuxMountConfig(
            mountpoint=mountpoint,
            state_directory=state,
            mount_id="mount:status-live",
            hermetic=True,
            readiness_timeout_seconds=10.0,
            heartbeat_interval_seconds=0.05,
        )
    )
    try:
        life.start(wait_ready=True)
        time.sleep(0.15)
        status = status_mod.collect_status_from_state_directory(state)
        record = status.to_record()
        assert record["ready"] is True or status.ready is True
        assert record["mount"]["mount_id"] == "mount:status-live"
        assert record["platform"]
        assert record["wal"]["generation"]
        assert "generation" in record["arc"]
        assert "open_handles" in record["handles"] or "open_callbacks" in record["handles"]
        assert record["heartbeat"]
        status_mod.assert_no_secrets(record)
        # No high-cardinality path lists.
        for key in status_mod.HIGH_CARDINALITY_KEYS:
            assert key not in record
    finally:
        life.unmount(timeout_seconds=5.0, sig=signal.SIGTERM)


def test_cli_error_json_on_missing_status_state_dir() -> None:
    out = io.StringIO()
    rc = cli.run(
        ["status", "--json"],
        stdout=out,
        stderr=io.StringIO(),
    )
    assert rc == cli.EXIT_USAGE
    payload = json.loads(out.getvalue())
    assert payload["ok"] is False
    assert payload["code"] == "STATE_DIR_REQUIRED"


def test_dispatch_unknown_command_not_reachable_via_parser() -> None:
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["not-a-command"])


def test_mount_option_record_written(tmp_path: Path) -> None:
    out = io.StringIO()
    err = io.StringIO()
    rc = cli.run(
        _mount_argv(tmp_path, "--json", "-o", "ro"),
        stdout=out,
        stderr=err,
    )
    assert rc == 0, err.getvalue()
    options_path = tmp_path / "state" / "cli-mount-options.json"
    assert options_path.is_file()
    raw = json.loads(options_path.read_text(encoding="utf-8"))
    assert "default_permissions" in raw["options"]["admitted"]
    assert "ro" in raw["options"]["admitted"]
    assert "password" not in json.dumps(raw)
    cli.run(
        ["unmount", "--state-dir", str(tmp_path / "state"), "--json"],
        stdout=io.StringIO(),
        stderr=err,
    )
