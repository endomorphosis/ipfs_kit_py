#!/usr/bin/env python3
"""Thin entrypoint wrapper for legacy test paths.

The real server implementation lives in:
`ipfs_kit_py.mcp.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt`.

Some tests invoke this server by executing this script path directly.
"""

import anyio


def _run() -> None:
    from ipfs_kit_py.mcp.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt import main as real_main

    anyio.run(real_main)


if __name__ == "__main__":
    _run()
