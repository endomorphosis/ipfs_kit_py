#!/usr/bin/env python3
"""Shim entrypoint for integration tests.

Delegates to the lightweight MCP HTTP server implementation bundled in
ipfs_kit_py.mcp.enhanced_mcp_server_with_config.
"""

from ipfs_kit_py.mcp.enhanced_mcp_server_with_config import main


if __name__ == "__main__":
    raise SystemExit(main())
