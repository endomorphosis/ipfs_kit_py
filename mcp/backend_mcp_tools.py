#!/usr/bin/env python3
"""
Compatibility shim for Backend MCP tools.

This module re-exports Backend MCP tools from their canonical location
in ipfs_kit_py/mcp/servers/ for backward compatibility and test patching.

Architecture:
  ipfs_kit_py/backend_manager.py (core)
      ↓
  ipfs_kit_py/mcp/servers/backend_mcp_tools.py (MCP integration)
      ↓
  mcp/backend_mcp_tools.py (this shim - for compatibility)
      ↓
  MCP Server → JS SDK → Dashboard
"""

from ipfs_kit_py.mcp.servers.backend_mcp_tools import (
    BACKEND_MCP_TOOLS,
    BACKEND_TOOL_HANDLERS,
    handle_backend_create,
    handle_backend_list,
    handle_backend_get_info,
    handle_backend_update,
    handle_backend_delete,
    handle_backend_test_connection,
    handle_backend_get_statistics,
    handle_backend_list_pin_mappings,
)

__all__ = [
    "BACKEND_MCP_TOOLS",
    "BACKEND_TOOL_HANDLERS",
    "handle_backend_create",
    "handle_backend_list",
    "handle_backend_get_info",
    "handle_backend_update",
    "handle_backend_delete",
    "handle_backend_test_connection",
    "handle_backend_get_statistics",
    "handle_backend_list_pin_mappings",
]
