"""
Filesystem Journal MCP Tools - Compatibility Shim

This module provides a compatibility shim for filesystem journal MCP tools,
following the established pattern for MCP tool organization.

Pattern: ipfs_kit_py/mcp/servers/ (implementation) → mcp/ (shim) → MCP Server
"""

# Import all tools from the actual implementation
try:
    from ipfs_kit_py.mcp.servers.fs_journal_mcp_tools import (
        journal_enable,
        journal_status,
        journal_list_entries,
        journal_checkpoint,
        journal_recover,
        journal_mount,
        journal_mkdir,
        journal_write,
        journal_read,
        journal_rm,
        journal_mv,
        journal_ls,
        MCP_TOOLS
    )
except ImportError:
    # Fallback for direct execution
    from ipfs_kit_py.mcp.servers.fs_journal_mcp_tools import *

__all__ = [
    'journal_enable',
    'journal_status',
    'journal_list_entries',
    'journal_checkpoint',
    'journal_recover',
    'journal_mount',
    'journal_mkdir',
    'journal_write',
    'journal_read',
    'journal_rm',
    'journal_mv',
    'journal_ls',
    'MCP_TOOLS'
]
