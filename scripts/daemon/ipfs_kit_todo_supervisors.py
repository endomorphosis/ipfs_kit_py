#!/usr/bin/env python3
"""Launch and manage supervised ipfs_kit_py todo daemon tracks."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = REPO_ROOT.parent
ACCELERATE_ROOT = WORKSPACE_ROOT / "ipfs_datasets_py" / "ipfs_accelerate_py"
STATE_ROOT = REPO_ROOT / "data" / "agent_supervisor" / "ipfs_kit_todo"
STATE_DIR = STATE_ROOT / "state"
MASTER_DIR = STATE_ROOT / "master"
MASTER_LOG = MASTER_DIR / "ipfs_kit_todo.master.log"
MASTER_PID = MASTER_DIR / "ipfs_kit_todo.master.pid"
STAMP = "ipfs_kit_todo"


if ACCELERATE_ROOT.exists():
    sys.path.insert(0, str(ACCELERATE_ROOT))
    os.environ["PYTHONPATH"] = f"{ACCELERATE_ROOT}{os.pathsep}{os.environ.get('PYTHONPATH', '')}".rstrip(os.pathsep)


TRACKS = (
    ("vfs-graphrag", "ipfs_kit_vfs_graphrag"),
    ("walrus-fsspec", "ipfs_kit_walrus_fsspec"),
    ("fsspec-backends", "ipfs_kit_fsspec_backends"),
)


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        from ipfs_accelerate_py.agent_supervisor.todo_daemon.core import pid_alive

        return bool(pid_alive(pid))
    except Exception:
        return False


def _read_pid(path: Path) -> int | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
        return int(text) if text else None
    except Exception:
        return None


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _track_paths(state_prefix: str) -> dict[str, Path]:
    return {
        "supervisor_pid": STATE_DIR / f"{state_prefix}_supervisor.pid",
        "daemon_pid": STATE_DIR / f"{state_prefix}_managed_daemon.pid",
        "supervisor_status": STATE_DIR / f"{state_prefix}_supervisor_status.json",
        "supervisor_log": STATE_DIR / f"{state_prefix}_8h_run_{STAMP}.log",
        "daemon_state": STATE_DIR / f"{state_prefix}_state.json",
        "daemon_progress": STATE_DIR / f"{state_prefix}_progress.json",
    }


def build_runner_args(args: argparse.Namespace, *, detach: bool) -> list[str]:
    supervisor_script = REPO_ROOT / "scripts" / "daemon" / "ipfs_kit_todo_supervisor.py"
    runner_args = [
        "--repo-root",
        str(REPO_ROOT),
        "--duration-seconds",
        str(args.duration_seconds),
        "--heartbeat-interval-seconds",
        str(args.heartbeat_interval_seconds),
        "--supervisor-status-stale-seconds",
        str(args.supervisor_status_stale_seconds),
        "--stop-grace-seconds",
        str(args.stop_grace_seconds),
        "--stamp",
        STAMP,
        "--master-dir",
        str(MASTER_DIR),
        "--master-log",
        str(MASTER_LOG),
        "--master-pid-path",
        str(MASTER_PID),
        "--label",
        "ipfs-kit-todo-supervisors",
        "--python-executable",
        sys.executable,
    ]
    for name, state_prefix in TRACKS:
        runner_args.extend(
            [
                "--implementation-track",
                "|".join((name, str(supervisor_script), str(STATE_DIR), state_prefix)),
            ]
        )

    common_args = [
        "--implement" if args.implement else "--no-implement",
        "--check-interval",
        str(args.check_interval),
        "--daemon-interval",
        str(args.daemon_interval),
        "--stale-seconds",
        str(args.stale_seconds),
        "--max-restarts",
        str(args.max_restarts),
    ]
    if args.implementation_command:
        common_args.extend(["--implementation-command", args.implementation_command])
    for item in common_args:
        runner_args.append(f"--common-arg={item}")
    if detach:
        runner_args.append("--detach")
    return runner_args


def run_multi_supervisor(args: argparse.Namespace, *, detach: bool) -> int:
    from ipfs_accelerate_py.agent_supervisor.multi_supervisor_runner import main as multi_supervisor_main

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    MASTER_DIR.mkdir(parents=True, exist_ok=True)
    return int(multi_supervisor_main(build_runner_args(args, detach=detach)) or 0)


def status_payload() -> dict[str, Any]:
    master_pid = _read_pid(MASTER_PID)
    tracks: list[dict[str, Any]] = []
    for name, state_prefix in TRACKS:
        paths = _track_paths(state_prefix)
        supervisor_pid = _read_pid(paths["supervisor_pid"])
        daemon_pid = _read_pid(paths["daemon_pid"])
        supervisor_status = _read_json(paths["supervisor_status"])
        tracks.append(
            {
                "name": name,
                "state_prefix": state_prefix,
                "supervisor_pid": supervisor_pid,
                "supervisor_alive": _pid_alive(supervisor_pid),
                "daemon_pid": daemon_pid,
                "daemon_alive": _pid_alive(daemon_pid),
                "supervisor_status": supervisor_status.get("state") or supervisor_status.get("status") or "unknown",
                "updated_at": supervisor_status.get("updated_at") or supervisor_status.get("heartbeat_at") or "",
                "log_path": str(paths["supervisor_log"]),
                "status_path": str(paths["supervisor_status"]),
            }
        )
    return {
        "schema": "ipfs_kit_py.todo_supervisors.status.v1",
        "repo_root": str(REPO_ROOT),
        "master_pid": master_pid,
        "master_alive": _pid_alive(master_pid),
        "master_log": str(MASTER_LOG),
        "master_pid_path": str(MASTER_PID),
        "state_dir": str(STATE_DIR),
        "tracks": tracks,
    }


def print_status(*, as_json: bool) -> int:
    payload = status_payload()
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(f"master_pid={payload['master_pid'] or 'unknown'} master_alive={payload['master_alive']}")
    print(f"master_log={payload['master_log']}")
    for track in payload["tracks"]:
        print(
            " ".join(
                (
                    f"{track['name']}:",
                    f"supervisor_pid={track['supervisor_pid'] or 'unknown'}",
                    f"supervisor_alive={track['supervisor_alive']}",
                    f"daemon_pid={track['daemon_pid'] or 'unknown'}",
                    f"daemon_alive={track['daemon_alive']}",
                    f"status={track['supervisor_status']}",
                )
            )
        )
    return 0


def stop_processes(args: argparse.Namespace) -> int:
    from ipfs_accelerate_py.agent_supervisor.todo_daemon.core import remove_runtime_marker, terminate_pid_tree

    stopped: list[int] = []
    for path in [MASTER_PID]:
        pid = _read_pid(path)
        if pid and terminate_pid_tree(pid, grace_seconds=args.stop_grace_seconds):
            stopped.append(pid)
        remove_runtime_marker(path)
    for _name, state_prefix in TRACKS:
        paths = _track_paths(state_prefix)
        for path in (paths["supervisor_pid"], paths["daemon_pid"]):
            pid = _read_pid(path)
            if pid and terminate_pid_tree(pid, grace_seconds=args.stop_grace_seconds):
                stopped.append(pid)
            remove_runtime_marker(path)
    print(json.dumps({"stopped_pids": stopped, "stopped_count": len(stopped)}, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage supervised ipfs_kit_py todo daemon tracks")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_runtime_options(target: argparse.ArgumentParser) -> None:
        target.add_argument("--implement", action="store_true", help="Allow autonomous implementation attempts")
        target.add_argument("--implementation-command", default="")
        target.add_argument("--duration-seconds", type=float, default=float(os.environ.get("IPFS_KIT_TODO_DURATION_SECONDS", "31536000")))
        target.add_argument("--heartbeat-interval-seconds", type=float, default=60.0)
        target.add_argument("--supervisor-status-stale-seconds", type=float, default=600.0)
        target.add_argument("--stop-grace-seconds", type=float, default=20.0)
        target.add_argument("--check-interval", type=float, default=60.0)
        target.add_argument("--daemon-interval", type=float, default=300.0)
        target.add_argument("--stale-seconds", type=float, default=1800.0)
        target.add_argument("--max-restarts", type=int, default=10)

    start_parser = subparsers.add_parser("start", help="Start the three supervisors detached")
    add_runtime_options(start_parser)

    run_parser = subparsers.add_parser("run", help="Run the three supervisors in the foreground")
    add_runtime_options(run_parser)

    status_parser = subparsers.add_parser("status", help="Show supervisor and daemon status")
    status_parser.add_argument("--json", action="store_true")

    stop_parser = subparsers.add_parser("stop", help="Stop the master, supervisors, and managed daemons")
    stop_parser.add_argument("--stop-grace-seconds", type=float, default=20.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "start":
        return run_multi_supervisor(args, detach=True)
    if args.command == "run":
        return run_multi_supervisor(args, detach=False)
    if args.command == "status":
        return print_status(as_json=args.json)
    if args.command == "stop":
        return stop_processes(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
