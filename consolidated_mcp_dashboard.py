"""Repository-root compatibility shim.

Some tests import or copy `consolidated_mcp_dashboard.py` from the repository root.
The implementation lives in the package under `ipfs_kit_py.consolidated_mcp_dashboard`.
"""

from ipfs_kit_py.consolidated_mcp_dashboard import ConsolidatedMCPDashboard

__all__ = ["ConsolidatedMCPDashboard"]
