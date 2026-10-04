#!/usr/bin/env python3
"""
Compatibility shim for Pin MCP tools.

This module re-exports Pin MCP tools from their canonical location
in ipfs_kit_py/mcp/servers/ for backward compatibility and test patching.

Architecture:
  ipfs_kit_py/pin_manager.py (core)
      ↓
  ipfs_kit_py/mcp/servers/pin_mcp_tools.py (MCP integration)
      ↓
  mcp/pin_mcp_tools.py (this shim - for compatibility)
      ↓
  MCP Server → JS SDK → Dashboard
"""

from ipfs_kit_py.mcp.servers.pin_mcp_tools import (
    PIN_MCP_TOOLS,
    PIN_TOOL_HANDLERS,
    handle_pin_add,
    handle_pin_list,
    handle_pin_remove,
    handle_pin_get_info,
    handle_pin_list_pending,
    handle_pin_verify,
    handle_pin_update,
    handle_pin_get_statistics,
)

__all__ = [
    "PIN_MCP_TOOLS",
    "PIN_TOOL_HANDLERS",
    "handle_pin_add",
    "handle_pin_list",
    "handle_pin_remove",
    "handle_pin_get_info",
    "handle_pin_list_pending",
    "handle_pin_verify",
    "handle_pin_update",
    "handle_pin_get_statistics",
]
