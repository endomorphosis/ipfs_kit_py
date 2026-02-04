"""IPLD/DAG tool availability smoke test.

This suite previously targeted deprecated MCP server variants.
It now asserts that the canonical unified MCP server exposes the expected IPLD tools.
"""

from __future__ import annotations


def test_unified_server_exposes_ipld_tools():
	from ipfs_kit_py.mcp.servers.unified_mcp_server import create_mcp_server

	server = create_mcp_server(auto_start_daemons=False, auto_start_lotus_daemon=False)
	tool_names = {tool.get("name") for tool in server.tools}

	# IPLD-ish operations should be present even if execution requires a daemon.
	assert "ipfs_dag_get" in tool_names
	assert "ipfs_dag_put" in tool_names
	assert "ipfs_block_get" in tool_names
