"""FastMCP backwards-compat registrar.

Standard MCP clients use the reference ``mcp.server.FastMCP``. This registrar
exposes every tool from the canonical TOOL_GROUPS registry — the same surface
the native JSON-RPC server, CLI, Python imports, and JS/TS SDK use — so no
parallel tool list is maintained. Mirrors the ipfs_datasets_py pattern.

Usage:
    from mcp.server import FastMCP
    from ipfs_kit_py.mcp_server.fastmcp_app import register_fastmcp
    app = FastMCP("ipfs_kit_py-mcpplusplus")
    register_fastmcp(app)
"""
from __future__ import annotations

from typing import Any, Dict, List

from .hierarchical_tool_manager import HierarchicalToolManager


def register_fastmcp(
    app: Any,
    tm: HierarchicalToolManager | None = None,
    *,
    server: Any | None = None,
) -> List[str]:
    """Register tools through the canonical server and AuthorizationGate."""

    if server is None:
        from .server import MCPServer

        server = MCPServer()
    tm = tm or HierarchicalToolManager()
    server.tm = tm
    registered: List[str] = []
    for schema in tm.all_tool_schemas():
        category, tool, name = schema["category"], schema["name"], schema["name"]
        desc = schema.get("description", "")

        def _make(cat: str, tl: str):
            async def _handler(
                arguments: Dict[str, Any] | None = None,
                mcppp_envelope: Dict[str, Any] | None = None,
                profile_b: bool = False,
            ) -> Dict[str, Any]:
                response = await server.handle(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": f"{cat}/{tl}",
                            "arguments": arguments or {},
                            "_mcppp_envelope": mcppp_envelope,
                            **({"profile_b": True} if profile_b else {}),
                        },
                    }
                )
                if "result" in response:
                    return response["result"]
                return {"status": "error", "error": response["error"]}
            return _handler

        handler = _make(category, tool)
        handler.__name__ = name
        handler.__doc__ = desc
        app.add_tool(handler, name=name, description=desc)
        registered.append(name)
    return registered


def build_app(name: str = "ipfs_kit_py-mcpplusplus") -> Any:
    """Construct a FastMCP app with all tools registered. Requires the mcp pkg."""
    from mcp.server import FastMCP  # type: ignore
    app = FastMCP(name)
    register_fastmcp(app)
    return app
