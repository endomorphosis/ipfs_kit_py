"""
MCP (Model-Controller-Persistence) Server for IPFS Kit.

This module provides a structured server implementation that:
1. Separates data models from controller logic
2. Provides consistent persistence patterns
3. Facilitates test-driven development through clean interfaces

The MCP pattern is particularly useful for IPFS Kit as it allows:
- Isolated testing of IPFS operations
- Mock implementations of network dependencies
- Clear boundaries between components
"""

__all__ = ["MCPServer"]


def __getattr__(name: str):
    """Keep the legacy server export without loading its HTTP stack eagerly."""

    if name == "MCPServer":
        from ipfs_kit_py.mcp.server_bridge import MCPServer

        globals()[name] = MCPServer
        return MCPServer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
