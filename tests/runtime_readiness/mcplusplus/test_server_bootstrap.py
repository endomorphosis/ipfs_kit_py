"""Regression coverage for the MCP++ bootstrap boundary."""

from __future__ import annotations

import anyio
import os
from pathlib import Path
import subprocess
import sys

from ipfs_kit_py.mcp_server import MCPServer
from ipfs_kit_py.mcp_server.mcplusplus.event_dag import EventDAGStore
from ipfs_kit_py.mcp_server.tools import resolve_tool_route


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


def test_event_dag_can_be_injected_explicitly(tmp_path):
    """Embedders can share provenance storage without an implicit global."""
    dag = EventDAGStore(storage_dir=str(tmp_path / "injected-event-dag"))
    server = MCPServer(event_dag=dag)

    assert server._dag is dag


def test_initialize_advertises_only_canonical_supported_profiles(monkeypatch):
    """Profile D is advertised conditionally with the other canonical profiles."""
    from ipfs_kit_py.mcp_server import server as server_module

    capabilities = {
        "profiles": {
            "A_interface_descriptors": True,
            "B_cid_envelopes": True,
            "C_ucan_unsigned": True,
            "D_policy": False,
            "E_dag_events": True,
            "E_p2p_transport": False,
            "G_risk_scheduling": True,
        },
    }
    monkeypatch.setattr(server_module.mcplusplus, "get_capabilities", lambda: capabilities)

    response = anyio.run(MCPServer().handle, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    advertised = response["result"]["capabilities"]["mcpPlusPlusProfiles"]

    assert advertised == [
        "mcp++/interface-descriptors",
        "mcp++/cid-envelopes",
        "mcp++/ucan",
        "mcp++/event-dag",
        "mcp++/risk-scheduling",
    ]
    assert "mcp++/deontic-policy" not in advertised


def test_tools_call_resolves_names_through_the_shared_tool_registry():
    """Qualified and unqualified names both use the tools-owned registry."""
    assert resolve_tool_route("pin_tools/pin_rm") == ("pin_tools", "pin_rm")
    assert resolve_tool_route("pin_rm") == ("pin_tools", "pin_rm")
    assert resolve_tool_route("missing_tools/pin_rm") is None


def test_transport_entrypoints_do_not_import_fastapi_at_bootstrap():
    """The minimal MCP install can load all transport entry points unaided."""
    package_root = Path(__file__).resolve().parents[3]
    environment = {**os.environ, "PYTHONPATH": str(package_root)}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from ipfs_kit_py.mcp_server import MCPServer, serve_http, serve_p2p, serve_stdio; "
            "MCPServer(); import sys; assert 'fastapi' not in sys.modules",
        ],
        cwd=package_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
