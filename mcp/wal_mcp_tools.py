#!/usr/bin/env python3
"""
Compatibility shim for WAL MCP tools.

This module re-exports WAL MCP tools from their canonical location
in ipfs_kit_py/mcp/servers/ for backward compatibility and test patching.

Architecture:
  ipfs_kit_py/storage_wal.py (core)
      ↓
  ipfs_kit_py/mcp/servers/wal_mcp_tools.py (MCP integration)
      ↓
  mcp/wal_mcp_tools.py (this shim - for compatibility)
      ↓
  MCP Server → JS SDK → Dashboard
"""

from ipfs_kit_py.mcp.servers.wal_mcp_tools import (
    WAL_MCP_TOOLS,
    WAL_TOOL_HANDLERS,
    handle_wal_status,
    handle_wal_list_operations,
    handle_wal_get_operation,
    handle_wal_wait_for_operation,
    handle_wal_cleanup,
    handle_wal_retry_operation,
    handle_wal_cancel_operation,
    handle_wal_add_operation,
)

__all__ = [
    "WAL_MCP_TOOLS",
    "WAL_TOOL_HANDLERS",
    "handle_wal_status",
    "handle_wal_list_operations",
    "handle_wal_get_operation",
    "handle_wal_wait_for_operation",
    "handle_wal_cleanup",
    "handle_wal_retry_operation",
    "handle_wal_cancel_operation",
    "handle_wal_add_operation",
]
