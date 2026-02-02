"""Compatibility shim for `mcp.vfs_version_mcp_tools`.

The actual implementation lives under `ipfs_kit_py.mcp.servers.vfs_version_mcp_tools`.
This module exists so legacy imports and tests can keep working.
"""

from ipfs_kit_py.mcp.servers.vfs_version_mcp_tools import *  # noqa: F403
