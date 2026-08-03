"""Authenticated CLI surface for the canonical MCP tool registry.

Usage: ipfs-kit-mcp-tools <category> <tool> --key val \
    --mcppp-envelope '<signed-envelope-json>'

Tool calls pass through :class:`MCPServer`, including its AuthorizationGate;
the CLI does not provide a privileged dispatch bypass.
"""
from __future__ import annotations

import json
import sys

import anyio

from .hierarchical_tool_manager import HierarchicalToolManager


def main(argv=None, *, server=None) -> int:
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
    envelope = params.pop("mcppp-envelope", None)
    profile_b = bool(params.pop("profile-b", False))
    if server is None:
        from .server import MCPServer

        server = MCPServer()
    response = anyio.run(
        server.handle,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": f"{category}/{tool}",
                "arguments": params,
                "_mcppp_envelope": envelope,
                **({"profile_b": True} if profile_b else {}),
            },
        },
        backend="trio",
    )
    if isinstance(response, dict) and "result" in response:
        output = response["result"]
        exit_code = 0 if output.get("status") == "success" else 1
    else:
        output = {
            "status": "error",
            "error": (response or {}).get("error", "empty MCP response"),
        }
        exit_code = 1
    print(json.dumps(output, indent=2, default=str))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
