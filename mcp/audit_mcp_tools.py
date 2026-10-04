#!/usr/bin/env python3
# mcp/audit_mcp_tools.py

"""
Compatibility shim for audit MCP tools.

This module provides a compatibility layer for the audit MCP tools,
following the standard pattern used throughout the codebase.
"""

# Import all tools from the core implementation
from ipfs_kit_py.mcp.servers.audit_mcp_tools import *  # noqa: F401,F403

# Expose tool registry
from ipfs_kit_py.mcp.servers.audit_mcp_tools import AUDIT_MCP_TOOLS  # noqa: F401

__all__ = [
    "audit_view",
    "audit_query",
    "audit_export",
    "audit_report",
    "audit_statistics",
    "audit_track_backend",
    "audit_track_vfs",
    "audit_integrity_check",
    "audit_retention_policy",
    "AUDIT_MCP_TOOLS"
]
