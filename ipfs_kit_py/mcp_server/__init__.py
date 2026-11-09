"""ipfs_kit_py MCP++ server package.

A single tool registry powers four interoperable surfaces:
  * Python imports — ``from ipfs_kit_py.mcp_server.tools.ipfs_tools import ipfs_add``
  * CLI           — ``ipfs-kit-mcp-tools ipfs_tools ipfs_add --file_path x``
  * MCP server    — JSON-RPC tools/list + tools/call (stdio/http/p2p)
  * JavaScript    — generated SDK mirroring the same tool defs (dashboard)

Aligned to the Mcp-Plus-Plus canonical packet spec for third-party interop.
"""
from .hierarchical_tool_manager import HierarchicalToolManager
from .tools import TOOL_GROUPS

__all__ = ["HierarchicalToolManager", "TOOL_GROUPS"]
