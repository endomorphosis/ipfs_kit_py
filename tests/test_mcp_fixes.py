"""Regression/smoke tests for MCP server fixes.

The historical test suite referenced deprecated server modules that no longer ship.
This file now validates the supported, canonical MCP server entrypoints.
"""

from __future__ import annotations

import pytest


def test_unified_server_import_and_tool_registry():
	from ipfs_kit_py.mcp.servers.unified_mcp_server import UnifiedMCPServer, create_mcp_server

	server = create_mcp_server(auto_start_daemons=False, auto_start_lotus_daemon=False)
	assert isinstance(server, UnifiedMCPServer)

	# Tool registry should exist even when daemons are not started.
	assert hasattr(server, "tools")
	assert isinstance(server.tools, dict)
	assert len(server.tools) > 0


@pytest.mark.anyio
async def test_compat_integration_wrapper_is_stable():
	from ipfs_kit_py.mcp.servers.unified_mcp_server import IPFSKitIntegration

	integration = IPFSKitIntegration(auto_start_daemons=False, auto_start_lotus_daemon=False)
	result = await integration.execute_ipfs_operation("ipfs_version")
	assert isinstance(result, dict)
	# Either a success payload or a structured error.
	assert ("success" in result) or ("error" in result)
