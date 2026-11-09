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


def register_fastmcp(app: Any, tm: HierarchicalToolManager | None = None) -> List[str]:
    """Register all registry tools on a FastMCP app; return registered names."""
    tm = tm or HierarchicalToolManager()
    registered: List[str] = []
    for schema in tm.all_tool_schemas():
        category, tool, name = schema["category"], schema["name"], schema["name"]
        desc = schema.get("description", "")

        def _make(cat: str, tl: str):
            async def _handler(arguments: Dict[str, Any] | None = None) -> Dict[str, Any]:
                return await tm.dispatch(cat, tl, arguments or {})
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
