"""CLI surface: every MCP tool is also a CLI command.

Usage: ipfs-kit-mcp-tools <category> <tool> --key val ...
Same registry, same codepath as the MCP server and Python imports.
"""
from __future__ import annotations

import json
import sys

import anyio

from .hierarchical_tool_manager import HierarchicalToolManager


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    tm = HierarchicalToolManager()
    if not argv or argv[0] in ("-h", "--help"):
        print("categories:", ", ".join(c["name"] for c in tm.list_categories()))
        return 0
    if argv[0] == "list" and len(argv) == 1:
        for cat in tm.list_categories():
            print(f"{cat['name']}: {', '.join(tm.list_tools(cat['name']))}")
        return 0
    if len(argv) < 2:
        print("usage: <category> <tool> [--k v ...]", file=sys.stderr)
        return 2
    category, tool, rest = argv[0], argv[1], argv[2:]
    params = {}
    i = 0
    while i < len(rest):
        if rest[i].startswith("--"):
            key = rest[i][2:]
            val = rest[i + 1] if i + 1 < len(rest) else "true"
            try:
                val = json.loads(val)
            except Exception:
                pass
            params[key] = val
            i += 2
        else:
            i += 1
    result = anyio.run(tm.dispatch, category, tool, params, backend="trio")
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
