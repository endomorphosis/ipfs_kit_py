#!/usr/bin/env python3
"""Per-track supervisor wrapper for ipfs_kit_py todo boards."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = REPO_ROOT.parent
ACCELERATE_ROOT = WORKSPACE_ROOT / "ipfs_datasets_py" / "ipfs_accelerate_py"

if ACCELERATE_ROOT.exists():
    sys.path.insert(0, str(ACCELERATE_ROOT))


TRACKS = {
    "ipfs_kit_vfs_graphrag": {
        "todo_path": REPO_ROOT / "TODO_VFS_GRAPHRAG_INDEXING.md",
        "task_prefix": "## vfs-graphrag-",
    },
    "ipfs_kit_walrus_fsspec": {
        "todo_path": REPO_ROOT / "TODO_WALRUS_FSSPEC.md",
        "task_prefix": "## walrus-fsspec-",
    },
    "ipfs_kit_fsspec_backends": {
        "todo_path": REPO_ROOT / "TODO_FSSPEC_BACKENDS.md",
        "task_prefix": "## fsspec-backends-",
    },
}


def _arg_value(argv: list[str], name: str) -> str:
    try:
        index = argv.index(name)
    except ValueError:
        return ""
    if index + 1 >= len(argv):
        return ""
    return argv[index + 1]


def _has_arg(argv: list[str], name: str) -> bool:
    return name in argv


def _without_arg_pair(argv: list[str], name: str) -> list[str]:
    cleaned: list[str] = []
    index = 0
    while index < len(argv):
        if argv[index] == name:
            index += 2
            continue
        cleaned.append(argv[index])
        index += 1
    return cleaned


def build_supervisor_args(argv: list[str]) -> list[str]:
    state_prefix = _arg_value(argv, "--state-prefix")
    try:
        track = TRACKS[state_prefix]
    except KeyError as exc:
        known = ", ".join(sorted(TRACKS))
        raise SystemExit(f"unknown ipfs_kit_py todo supervisor state prefix: {state_prefix!r}; expected one of: {known}") from exc

    todo_path = Path(track["todo_path"])
    if not todo_path.exists():
        raise SystemExit(f"todo file does not exist: {todo_path}")

    args = list(argv)
    args = _without_arg_pair(args, "--todo-path")
    args = _without_arg_pair(args, "--task-prefix")

    if not _has_arg(args, "--state-dir"):
        args.extend(["--state-dir", str(REPO_ROOT / "data" / "agent_supervisor" / "ipfs_kit_todo" / "state")])
    if not _has_arg(args, "--state-prefix"):
        args.extend(["--state-prefix", state_prefix])

    args.extend(["--todo-path", str(todo_path)])
    args.extend(["--task-prefix", str(track["task_prefix"])])
    return args


def main(argv: list[str] | None = None) -> None:
    from ipfs_accelerate_py.agent_supervisor.todo_daemon.implementation_supervisor import main as supervisor_main

    supervisor_main(build_supervisor_args(list(sys.argv[1:] if argv is None else argv)))


if __name__ == "__main__":
    main()
