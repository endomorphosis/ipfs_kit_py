#!/usr/bin/env python3
"""Lightweight MCP server entrypoint used by tests.

Some unit tests exec `mcp/ipfs_kit/mcp/enhanced_mcp_server_with_daemon_mgmt.py`.
The main, feature-rich MCP implementation lives elsewhere in the repo and may
pull in optional dependencies or try to manage daemons.

This shim provides a minimal, fast, and side-effect-free JSON-RPC loop that
supports:
- `initialize`
- `tools/list`
- `tools/call` (best-effort stub responses)

It is intentionally conservative: it does not start background services and
does not touch global user state.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional


def _tool(name: str, description: str = "") -> Dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {"type": "object", "properties": {}},
    }


TOOLS: List[Dict[str, Any]] = [
    _tool("search_stats", "Return search capability flags"),
    _tool("search_index_content", "Index content for later search"),
    _tool("search_text", "Text search (may be unavailable)"),
    _tool("search_vector", "Vector search (may be unavailable)"),
    _tool("search_graph", "Graph search (may be unavailable)"),
    _tool("search_hybrid", "Hybrid search across methods"),
    _tool("search_sparql", "SPARQL query over RDF graph"),
]


def _result_text(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload),
            }
        ]
    }


def handle_message(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = message.get("method")
    params = message.get("params") or {}
    msg_id = message.get("id")

    if method == "notifications/initialized" or (isinstance(method, str) and method.startswith("notifications/")):
        return None

    try:
        if method == "initialize":
            result = {
                "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                "serverInfo": {"name": "ipfs-kit-mcp-test-shim", "version": "0.1.0"},
                "capabilities": {"tools": {}},
            }
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            tool_name = (params or {}).get("name")
            # Best-effort, deterministic stub outputs.
            if tool_name == "search_stats":
                result = _result_text(
                    {
                        "success": True,
                        "vector_search_available": False,
                        "graph_search_available": False,
                        "sparql_available": False,
                        "total_indexed_content": 0,
                    }
                )
            else:
                result = _result_text(
                    {
                        "success": False,
                        "error": f"Tool not implemented in test shim: {tool_name}",
                    }
                )
        else:
            raise Exception(f"Unknown method: {method}")

        if msg_id is None:
            return None
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    except Exception as e:
        if msg_id is None:
            return None
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32603, "message": str(e)},
        }


def main() -> int:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue

        response = handle_message(message)
        if response is not None:
            print(json.dumps(response), flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
