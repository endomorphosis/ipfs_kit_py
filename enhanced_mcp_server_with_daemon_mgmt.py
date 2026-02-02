"""Compatibility shim for legacy imports.

Some legacy tests/importers expect `enhanced_mcp_server_with_daemon_mgmt` to be
importable as a top-level module.

The implementation lives under `ipfs_kit_py.mcp`.
"""

from ipfs_kit_py.mcp.enhanced_mcp_server_with_daemon_mgmt import (  # noqa: F401
    EnhancedMCPServerWithDaemonMgmt,
)

__all__ = ["EnhancedMCPServerWithDaemonMgmt"]
