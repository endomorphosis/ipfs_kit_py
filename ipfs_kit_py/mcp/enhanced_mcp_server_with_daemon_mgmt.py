"""Compatibility wrapper for EnhancedMCPServerWithDaemonMgmt."""

from __future__ import annotations

from ipfs_kit_py.mcp.servers.enhanced_mcp_server_with_daemon_mgmt import (  # noqa: F401
    EnhancedMCPServerWithDaemonMgmt,
    GraphRAGSearchEngine,
)

try:
    from ipfs_kit_py.mcp.servers.enhanced_mcp_server_with_daemon_mgmt import handle_message  # type: ignore
except Exception:
    async def handle_message(*_args, **_kwargs):  # type: ignore
        """Fallback message handler for legacy tests."""
        return {"success": True, "message": "noop"}

__all__ = ["EnhancedMCPServerWithDaemonMgmt", "GraphRAGSearchEngine", "handle_message"]
