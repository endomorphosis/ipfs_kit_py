"""Final MCP reorganization validation.

This repository previously carried legacy MCP server entrypoints (e.g.
`mcp.consolidated_final_mcp_server`) and references to a historical `ipfs_kit`
package layout.

The supported entrypoint is now:
- `ipfs_kit_py.mcp.servers.unified_mcp_server.create_mcp_server`

These tests are deterministic and avoid starting external daemons.
"""

from __future__ import annotations

import pytest


def test_unified_server_smoke():
    from ipfs_kit_py.mcp.servers.unified_mcp_server import UnifiedMCPServer, create_mcp_server

    server = create_mcp_server(auto_start_daemons=False, auto_start_lotus_daemon=False)
    assert isinstance(server, UnifiedMCPServer)

    assert hasattr(server, "tools")
    assert isinstance(server.tools, dict)
    assert len(server.tools) > 0

    # A stable, low-cost tool that should always be registered.
    assert "ipfs_version" in server.tools


@pytest.mark.anyio
async def test_unified_integration_wrapper_smoke():
    from ipfs_kit_py.mcp.servers.unified_mcp_server import IPFSKitIntegration

    integration = IPFSKitIntegration(auto_start_daemons=False, auto_start_lotus_daemon=False)
    result = await integration.execute_ipfs_operation("ipfs_version")
    assert isinstance(result, dict)
    assert ("success" in result) or ("error" in result)
