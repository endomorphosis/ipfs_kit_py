"""Backwards-compatible import shims for the MCP dashboard.

Some tests and older code import `ConsolidatedMCPDashboard` from
`ipfs_kit_py.consolidated_mcp_dashboard`. The implementation lives under
`ipfs_kit_py.mcp.dashboard`.
"""

from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard

__all__ = ["ConsolidatedMCPDashboard"]
