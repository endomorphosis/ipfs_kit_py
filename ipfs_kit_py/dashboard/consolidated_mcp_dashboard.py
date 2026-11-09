"""Compatibility shim for tests and legacy entrypoints.

The consolidated dashboard implementation lives in
`ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard`.

Some integration tests and older scripts expect a top-level
`consolidated_mcp_dashboard.py` file in the repository root that exposes the
`ConsolidatedMCPDashboard` class.
"""

from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard


__all__ = ["ConsolidatedMCPDashboard"]


if __name__ == "__main__":  # pragma: no cover
    # Delegate to the real module's CLI behavior by instantiating and running.
    import os

    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8081"))
    data_dir = os.environ.get("MCP_DATA_DIR")
    debug = os.environ.get("MCP_DEBUG", "0") in ("1", "true", "True")

    app = ConsolidatedMCPDashboard({"host": host, "port": port, "data_dir": data_dir, "debug": debug})
    app.run_sync()
