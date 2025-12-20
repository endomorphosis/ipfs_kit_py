"""Unified MCP Dashboard (compatibility entrypoint).

The codebase historically referenced `UnifiedMCPDashboard` as the main dashboard
class. The actively maintained implementation is the refactored dashboard.

This module keeps the legacy import path working.
"""

from ipfs_kit_py.mcp.dashboard.refactored_unified_mcp_dashboard import (
	RefactoredUnifiedMCPDashboard as UnifiedMCPDashboard,
)

__all__ = ["UnifiedMCPDashboard"]

