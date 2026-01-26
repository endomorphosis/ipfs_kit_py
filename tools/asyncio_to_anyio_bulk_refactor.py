#!/usr/bin/env python3
"""Bulk refactor helper: asyncio -> AnyIO (safe mechanical transforms).

This is intentionally conservative: it applies only transformations that are
very likely to be correct without deeper control-flow/context analysis.

It also emits a report of remaining "hard" asyncio constructs that typically
need manual refactoring (task groups, event loops, gather/wait_for, etc.).

Usage:
  # report only (no edits)
  python tools/asyncio_to_anyio_bulk_refactor.py --check

  # apply safe edits in-place
  python tools/asyncio_to_anyio_bulk_refactor.py --apply

  # limit to a subset
  python tools/asyncio_to_anyio_bulk_refactor.py --apply --include ipfs_kit_py/routing

Exit codes:
  0: success
  1: --check found files that would change or hard-patterns present
  2: usage / unexpected failure
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GLOB = "ipfs_kit_py/**/*.py"


SAFE_REWRITES: List[Tuple[str, str]] = [
    # Awaited sleep
    (r"\bawait\s+asyncio\.sleep\(", "await anyio.sleep("),
    # Awaited to_thread
    (r"\bawait\s+asyncio\.to_thread\(", "await anyio.to_thread.run_sync("),
    # Mis-migrations: anyio.get_event_loop().run_in_executor(None, ...) -> anyio.to_thread.run_sync(...)
    (r"\bawait\s+anyio\.get_event_loop\(\)\.run_in_executor\(\s*None\s*,\s*", "await anyio.to_thread.run_sync("),
    # Cancellation exception
    (r"\bexcept\s+asyncio\.CancelledError\s*:\s*$", "except anyio.get_cancelled_exc_class():"),
    # Basic primitives
    (r"\basyncio\.Event\(", "anyio.Event("),
    (r"\basyncio\.Lock\(", "anyio.Lock("),
    (r"\basyncio\.Semaphore\(", "anyio.Semaphore("),
    # Entry-point runner
    (r"\basyncio\.run\(", "anyio.run("),
]


HARD_PATTERNS: Dict[str, str] = {
    r"\basyncio\.create_task\(": "Needs AnyIO task group context (create_task -> task_group.start_soon)",
    r"\basyncio\.gather\(": "Needs AnyIO task group / nursery equivalent",
    r"\basyncio\.wait_for\(": "Usually convert to anyio.fail_after/move_on_after",
    r"\basyncio\.new_event_loop\(": "Manual: event loop creation is asyncio-specific",
    r"\basyncio\.get_running_loop\(": "Manual: event loop access is asyncio-specific",
    r"\basyncio\.get_event_loop\(": "Manual: event loop access is asyncio-specific",
    r"\bloop\.run_until_complete\(": "Manual: run_until_complete is asyncio loop API",
    r"\banyio\.get_event_loop\(": "Manual/bug: anyio has no get_event_loop(); use anyio.run/anyio.from_thread.run",
    r"\basyncio\.Future\b": "Manual: Futures are asyncio-specific",
    r"\basyncio\.Task\b": "Manual: Task typing / APIs are asyncio-specific",
    r"\basyncio\.Queue\b": "Manual: consider anyio.create_memory_object_stream",
}


ANYIO_IMPORT_RE = re.compile(r"^\s*(from\s+anyio\b|import\s+anyio\b)", re.M)
SNIFFIO_IMPORT_RE = re.compile(r"^\s*(from\s+sniffio\b|import\s+sniffio\b)", re.M)
THREADING_IMPORT_RE = re.compile(r"^\s*(from\s+threading\b|import\s+threading\b)", re.M)


SYNC_BRIDGE_HELPER_RE = re.compile(r"^\s*def\s+_run_async_from_sync\s*\(", re.M)


SYNC_BRIDGE_HELPER = (
    "\n\n"
    "def _run_async_from_sync(async_fn, *args, **kwargs):\n"
    "    \"\"\"Run an async callable from sync code.\n\n"
    "    - If called from an AnyIO worker thread, uses `anyio.from_thread.run`.\n"
    "    - If called from plain sync code, uses `anyio.run`.\n"
    "    - If called while an async library is running in this thread, runs the\n"
    "      call in a dedicated helper thread.\n"
    "    \"\"\"\n"
    "    try:\n"
    "        return anyio.from_thread.run(async_fn, *args, **kwargs)\n"
    "    except RuntimeError:\n"
    "        pass\n\n"
    "    try:\n"
    "        sniffio.current_async_library()\n"
    "    except sniffio.AsyncLibraryNotFoundError:\n"
    "        return anyio.run(async_fn, *args, **kwargs)\n\n"
    "    result = []\n"
    "    error = []\n\n"
    "    def _thread_main() -> None:\n"
    "        try:\n"
    "            result.append(anyio.run(async_fn, *args, **kwargs))\n"
    "        except BaseException as exc:  # noqa: BLE001\n"
    "            error.append(exc)\n\n"
    "    t = threading.Thread(target=_thread_main, daemon=True)\n"
    "    t.start()\n"
    "    t.join()\n"
    "    if error:\n"
    "        raise error[0]\n"
    "    return result[0] if result else None\n"
)


def _insert_import(source: str, import_line: str) -> str:
    if re.search(rf"^\\s*{re.escape(import_line)}\\s*$", source, re.M):
        return source

    lines = source.splitlines(True)
    insert_at = 0

    # Preserve shebang
    if lines and lines[0].startswith("#!"):
        insert_at = 1

    # Skip encoding line
    if insert_at < len(lines) and re.match(r"^#\\s*coding\\s*[:=]", lines[insert_at]):
        insert_at += 1

    # Skip module docstring
    if insert_at < len(lines) and re.match(r"^\\s*(\"\"\"|''')", lines[insert_at]):
        quote = "\"\"\"" if "\"\"\"" in lines[insert_at] else "'''"
        insert_at += 1
        while insert_at < len(lines):
            if quote in lines[insert_at]:
                insert_at += 1
                break
            insert_at += 1
        while insert_at < len(lines) and lines[insert_at].strip() == "":
            insert_at += 1

    # Place alongside other imports
    for i in range(insert_at, min(insert_at + 120, len(lines))):
        if re.match(r"^\\s*(import\\s+\\w|from\\s+\\w)", lines[i]):
            insert_at = i
            break

    lines.insert(insert_at, f"{import_line}\n")
    return "".join(lines)


def _ensure_sync_bridge_helper(source: str) -> str:
    if not re.search(r"\b_run_async_from_sync\b", source) or SYNC_BRIDGE_HELPER_RE.search(source):
        return source

    # Ensure imports required by the helper
    source = _insert_anyio_import(source)
    if not SNIFFIO_IMPORT_RE.search(source):
        source = _insert_import(source, "import sniffio")
    if not THREADING_IMPORT_RE.search(source):
        source = _insert_import(source, "import threading")

    lines = source.splitlines(True)
    insert_at = 0

    # Preserve shebang
    if lines and lines[0].startswith("#!"):
        insert_at = 1

    # Skip encoding
    if insert_at < len(lines) and re.match(r"^#\\s*coding\\s*[:=]", lines[insert_at]):
        insert_at += 1

    # Skip module docstring
    if insert_at < len(lines) and re.match(r"^\\s*(\"\"\"|''')", lines[insert_at]):
        quote = "\"\"\"" if "\"\"\"" in lines[insert_at] else "'''"
        insert_at += 1
        while insert_at < len(lines):
            if quote in lines[insert_at]:
                insert_at += 1
                break
            insert_at += 1
        while insert_at < len(lines) and lines[insert_at].strip() == "":
            insert_at += 1

    # Insert after import block
    last_import = None
    for i in range(insert_at, min(insert_at + 240, len(lines))):
        if re.match(r"^\\s*(import\\s+|from\\s+)", lines[i]):
            last_import = i
            continue
        if last_import is not None:
            insert_at = last_import + 1
            break

    lines.insert(insert_at, SYNC_BRIDGE_HELPER)
    return "".join(lines)


def _apply_sync_bridge_rewrites(source: str) -> Tuple[str, Dict[str, int]]:
    """Opt-in rewrites for common sync wrappers around async calls."""

    applied: Dict[str, int] = {}
    new_source = source

    spacer = r"(?:(?P=indent)[ \t]*(?:#.*)?\n)*"

    # 1) anyio.get_event_loop() + run_until_complete(...)  -> _run_async_from_sync(...)
    pat_anyio_loop_return = re.compile(
        r"^(?P<indent>[ \t]*)loop\s*=\s*anyio\.get_event_loop\(\)\s*$\n"
        + spacer
        + r"(?P=indent)return\s+loop\.run_until_complete\(\s*(?P<call>[\w\.]+)\((?P<args>.*?)\)\s*\)\s*$",
        re.M | re.S,
    )

    pat_anyio_loop_assign = re.compile(
        r"^(?P<indent>[ \t]*)loop\s*=\s*anyio\.get_event_loop\(\)\s*$\n"
        + spacer
        + r"(?P=indent)(?P<var>\w+)\s*=\s*loop\.run_until_complete\(\s*(?P<call>[\w\.]+)\((?P<args>.*?)\)\s*\)\s*$",
        re.M | re.S,
    )

    def repl_anyio_loop(m: re.Match) -> str:
        indent = m.group("indent")
        call = m.group("call")
        args = m.group("args").strip()
        if args:
            return f"{indent}return _run_async_from_sync({call}, {args})"
        return f"{indent}return _run_async_from_sync({call})"

    new_source, n = pat_anyio_loop_return.subn(repl_anyio_loop, new_source)
    if n:
        applied["anyio.get_event_loop+run_until_complete (return)"] = n

    def repl_anyio_loop_assign(m: re.Match) -> str:
        indent = m.group("indent")
        var = m.group("var")
        call = m.group("call")
        args = m.group("args").strip()
        if args:
            return f"{indent}{var} = _run_async_from_sync({call}, {args})"
        return f"{indent}{var} = _run_async_from_sync({call})"

    new_source, n = pat_anyio_loop_assign.subn(repl_anyio_loop_assign, new_source)
    if n:
        applied["anyio.get_event_loop+run_until_complete (assign)"] = n

    # 2) asyncio new loop try/finally wrapper (assignment)
    pat_asyncio_try_assign = re.compile(
        r"^(?P<indent>[ \t]*)loop\s*=\s*asyncio\.new_event_loop\(\)\s*$\n"
        r"(?P=indent)asyncio\.set_event_loop\(loop\)\s*$\n"
        r"(?P=indent)try:\s*$\n"
        r"(?P=indent)[ \t]+(?P<var>\w+)\s*=\s*loop\.run_until_complete\(\s*(?P<call>[\w\.]+)\((?P<args>.*?)\)\s*\)\s*$\n"
        r"(?P=indent)finally:\s*$\n"
        r"(?P=indent)[ \t]+loop\.close\(\)\s*$\n",
        re.M | re.S,
    )

    def repl_asyncio_try_assign(m: re.Match) -> str:
        indent = m.group("indent")
        var = m.group("var")
        call = m.group("call")
        args = m.group("args").strip()
        if args:
            return f"{indent}{var} = _run_async_from_sync({call}, {args})\n"
        return f"{indent}{var} = _run_async_from_sync({call})\n"

    new_source, n = pat_asyncio_try_assign.subn(repl_asyncio_try_assign, new_source)
    if n:
        applied["asyncio.new_event_loop try/finally (assign)"] = n

    # 3) asyncio new loop try/finally wrapper (return)
    pat_asyncio_try_return = re.compile(
        r"^(?P<indent>[ \t]*)loop\s*=\s*asyncio\.new_event_loop\(\)\s*$\n"
        r"(?P=indent)asyncio\.set_event_loop\(loop\)\s*$\n"
        r"(?P=indent)try:\s*$\n"
        r"(?P=indent)[ \t]+return\s+loop\.run_until_complete\(\s*(?P<call>[\w\.]+)\((?P<args>.*?)\)\s*\)\s*$\n"
        r"(?P=indent)finally:\s*$\n"
        r"(?P=indent)[ \t]+loop\.close\(\)\s*$\n",
        re.M | re.S,
    )

    def repl_asyncio_try_return(m: re.Match) -> str:
        indent = m.group("indent")
        call = m.group("call")
        args = m.group("args").strip()
        if args:
            return f"{indent}return _run_async_from_sync({call}, {args})\n"
        return f"{indent}return _run_async_from_sync({call})\n"

    new_source, n = pat_asyncio_try_return.subn(repl_asyncio_try_return, new_source)
    if n:
        applied["asyncio.new_event_loop try/finally (return)"] = n

    # 4) asyncio get_event_loop/new_event_loop wrapper (common CLI sync pattern)
    pat_asyncio_get_event_loop = re.compile(
        r"^(?P<indent>[ \t]*)try:\s*$\n"
        r"(?P=indent)[ \t]+loop\s*=\s*asyncio\.get_event_loop\(\)\s*$\n"
        + spacer
        + r"(?P=indent)except\s+RuntimeError:\s*$\n"
        r"(?P=indent)[ \t]+loop\s*=\s*asyncio\.new_event_loop\(\)\s*$\n"
        r"(?P=indent)[ \t]+asyncio\.set_event_loop\(loop\)\s*$\n"
        + spacer
        + r"(?P=indent)return\s+loop\.run_until_complete\(\s*(?P<call>[\w\.]+)\((?P<args>.*?)\)\s*\)\s*$",
        re.M | re.S,
    )

    def repl_asyncio_get_event_loop(m: re.Match) -> str:
        indent = m.group("indent")
        call = m.group("call")
        args = m.group("args").strip()
        if args:
            return f"{indent}return _run_async_from_sync({call}, {args})"
        return f"{indent}return _run_async_from_sync({call})"

    new_source, n = pat_asyncio_get_event_loop.subn(repl_asyncio_get_event_loop, new_source)
    if n:
        applied["asyncio.get_event_loop try/except + run_until_complete"] = n

    # 5) loop = asyncio.get_event_loop(); return loop.run_until_complete(...)
    pat_asyncio_loop_direct = re.compile(
        r"^(?P<indent>[ \t]*)loop\s*=\s*asyncio\.get_event_loop\(\)\s*$\n"
        + spacer
        + r"(?P=indent)return\s+loop\.run_until_complete\(\s*(?P<call>[\w\.]+)\((?P<args>.*?)\)\s*\)\s*$",
        re.M | re.S,
    )

    new_source, n = pat_asyncio_loop_direct.subn(repl_anyio_loop, new_source)
    if n:
        applied["asyncio.get_event_loop+run_until_complete"] = n

    # If any bridge rewrites were applied, ensure helper exists.
    if applied:
        new_source = _ensure_sync_bridge_helper(new_source)

    return new_source, applied


@dataclass
class FileResult:
    path: str
    changed: bool
    rewrites_applied: Dict[str, int] = field(default_factory=dict)
    hard_hits: Dict[str, int] = field(default_factory=dict)


def _iter_python_files(root: Path, include: List[str]) -> Iterable[Path]:
    if include:
        for inc in include:
            p = (root / inc).resolve()
            if p.is_file() and p.suffix == ".py":
                yield p
            elif p.is_dir():
                yield from p.rglob("*.py")
    else:
        yield from (root / "ipfs_kit_py").rglob("*.py")


def _insert_anyio_import(source: str) -> str:
    if ANYIO_IMPORT_RE.search(source):
        return source

    # Only insert if we introduced/need anyio usage.
    if "anyio." not in source and "import anyio" not in source:
        return source

    lines = source.splitlines(True)

    # Preserve shebang and module docstring.
    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1

    # Skip encoding line
    if insert_at < len(lines) and re.match(r"^#\s*coding\s*[:=]", lines[insert_at]):
        insert_at += 1

    # If a docstring exists, insert after it.
    if insert_at < len(lines) and re.match(r"^\s*(\"\"\"|''')", lines[insert_at]):
        quote = "\"\"\"" if "\"\"\"" in lines[insert_at] else "'''"
        insert_at += 1
        while insert_at < len(lines):
            if quote in lines[insert_at]:
                insert_at += 1
                break
            insert_at += 1
        # Consume blank lines after docstring
        while insert_at < len(lines) and lines[insert_at].strip() == "":
            insert_at += 1

    # Insert before the first import if we can find one soon.
    for i in range(insert_at, min(insert_at + 80, len(lines))):
        if re.match(r"^\s*(import\s+\w|from\s+\w)", lines[i]):
            insert_at = i
            break

    lines.insert(insert_at, "import anyio\n")
    return "".join(lines)


def _apply_rewrites(path: Path, source: str, bridges: bool) -> Tuple[str, Dict[str, int]]:
    applied: Dict[str, int] = {}
    new_source = source

    for pattern, replacement in SAFE_REWRITES:
        regex = re.compile(pattern, re.M)
        new_source, n = regex.subn(replacement, new_source)
        if n:
            applied[pattern] = n

    if bridges:
        new_source, bridge_applied = _apply_sync_bridge_rewrites(new_source)
        for k, v in bridge_applied.items():
            applied[f"bridge:{k}"] = v

    # If we made any replacements that introduce anyio usage, add import.
    if new_source != source:
        new_source = _insert_anyio_import(new_source)

    return new_source, applied


def _scan_hard_patterns(source: str) -> Dict[str, int]:
    hits: Dict[str, int] = {}
    for pattern in HARD_PATTERNS:
        n = len(re.findall(pattern, source))
        if n:
            hits[pattern] = n
    return hits


def process_file(path: Path, apply: bool) -> FileResult:
    original = path.read_text(encoding="utf-8")
    rewritten, applied = _apply_rewrites(path, original, bridges=getattr(process_file, "_bridges", False))
    hard_hits = _scan_hard_patterns(rewritten)

    changed = rewritten != original
    if apply and changed:
        path.write_text(rewritten, encoding="utf-8")

    return FileResult(
        path=str(path.relative_to(DEFAULT_ROOT)),
        changed=changed,
        rewrites_applied=applied,
        hard_hits=hard_hits,
    )


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Report changes/hard patterns; do not edit")
    mode.add_argument("--apply", action="store_true", help="Apply safe rewrites in-place")

    parser.add_argument(
        "--bridges",
        action="store_true",
        help=(
            "Also rewrite common sync wrappers around async calls (loop+run_until_complete patterns) "
            "into an AnyIO sync->async bridge helper. Opt-in because it's more invasive than safe rewrites."
        ),
    )

    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Limit to files/dirs (workspace-relative). Can be repeated.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON report.",
    )

    args = parser.parse_args(argv)

    # Thread bridges flag through to process_file without changing its signature.
    setattr(process_file, "_bridges", bool(args.bridges))

    results: List[FileResult] = []
    any_changes = False
    any_hard = False

    for path in _iter_python_files(DEFAULT_ROOT, args.include):
        # Skip vendored/virtualenv folders if user points include too wide
        if any(part in {".venv", ".venv_zt_validate", ".pytest_cache", "__pycache__"} for part in path.parts):
            continue
        try:
            res = process_file(path, apply=args.apply)
        except UnicodeDecodeError:
            continue

        results.append(res)
        any_changes = any_changes or res.changed
        any_hard = any_hard or bool(res.hard_hits)

    summary = {
        "mode": "apply" if args.apply else "check",
        "files_scanned": len(results),
        "files_changed": sum(1 for r in results if r.changed),
        "files_with_hard_patterns": sum(1 for r in results if r.hard_hits),
        "hard_patterns": {pat: desc for pat, desc in HARD_PATTERNS.items()},
    }

    if args.json:
        print(json.dumps({"summary": summary, "results": [r.__dict__ for r in results]}, indent=2))
    else:
        print(f"Scanned {summary['files_scanned']} files")
        print(f"Would change / changed: {summary['files_changed']} files")
        print(f"Files with hard patterns: {summary['files_with_hard_patterns']} files")

        # Show top offenders (by hard hits)
        offenders = sorted(
            (r for r in results if r.hard_hits),
            key=lambda r: sum(r.hard_hits.values()),
            reverse=True,
        )
        if offenders:
            print("\nTop hard-pattern files:")
            for r in offenders[:20]:
                total = sum(r.hard_hits.values())
                print(f"  - {r.path}: {total} hard hits")

        changed = [r for r in results if r.changed]
        if changed:
            print("\nFiles with safe rewrites:")
            for r in changed[:40]:
                counts = sum(r.rewrites_applied.values())
                print(f"  - {r.path}: {counts} rewrites")
            if len(changed) > 40:
                print(f"  ... ({len(changed) - 40} more)")

    # For --check, return non-zero if work remains.
    if args.check and (any_changes or any_hard):
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        raise SystemExit(2)
