"""Compatibility shim for dashboard imports.

Tests expect a repository-root `consolidated_mcp_dashboard.py`. This shim
re-exports the actual implementation from the package.
"""

from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import (  # noqa: F401
    ConsolidatedMCPDashboard,
)

__all__ = ["ConsolidatedMCPDashboard"]
