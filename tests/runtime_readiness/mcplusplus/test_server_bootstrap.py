"""Regression coverage for the MCP++ bootstrap boundary."""

from __future__ import annotations

import anyio

from ipfs_kit_py.mcp_server import MCPServer


def test_mcppp_envelope_bootstrap_constructs_a_usable_event_dag(tmp_path, monkeypatch):
    """Construction imports the persistent store used by Profile B and E."""
    monkeypatch.setenv("MCPPLUSPLUS_EVENT_DAG_DIR", str(tmp_path / "event-dag"))
    server = MCPServer()

    response = anyio.run(
        server.handle,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "pin_tools/pin_rm",
                "arguments": {"cid": "bafy"},
                "_mcppp_envelope": {"toolName": "pin_rm"},
            },
        },
    )

    assert response["result"]["status"] == "success"
    assert response["result"]["_mcppp"]["event_cid"].startswith("bafkrei")


def test_public_server_export_is_lazy_and_profile_registry_is_advertised():
    """The public package facade exposes the constructor without HTTP imports."""
    server = MCPServer()
    response = anyio.run(server.handle, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})

    profiles = response["result"]["capabilities"]["experimental"]["mcp++"]["profiles"]
    assert profiles["A_interface_descriptors"] is True
    assert profiles["D_policy"] is True
