"""Compatibility shim for legacy imports.

Re-exports the standalone VFS MCP server from the canonical package location
under `ipfs_kit_py.mcp.servers`.
"""

from ipfs_kit_py.mcp.servers.standalone_vfs_mcp_server import *  # noqa: F403
