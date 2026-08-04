"""Regression coverage for the MCP++ bootstrap boundary."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import anyio

from ipfs_kit_py.mcp_server import MCPServer
from ipfs_kit_py.mcp_server.mcplusplus.event_dag import EventDAGStore
from ipfs_kit_py.mcp_server.tools import resolve_tool_route


def test_legacy_unsigned_envelope_fails_closed_into_the_durable_event_dag(tmp_path, monkeypatch):
    """Construction imports the durable audit store and rejects legacy grants."""
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

    assert response["error"]["data"]["authorization"] == "denied"
    assert server._dag.history(limit=10)["count"] == 1


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

    class _UnavailablePolicyProvider:
        available = False

        @staticmethod
        def metadata():
            return {
                "provider": "unavailable-test-provider",
                "available": False,
                "fail_closed": True,
            }

    capabilities = {
        "profiles": {
            "A_interface_descriptors": True,
            "B_cid_envelopes": True,
            "C_ucan_signed": True,
            "D_policy": False,
            "E_dag_events": True,
            "E_p2p_transport": False,
            "G_risk_scheduling": True,
        },
    }
    monkeypatch.setattr(server_module.mcplusplus, "get_capabilities", lambda: capabilities)

    response = anyio.run(
        MCPServer(policy_provider=_UnavailablePolicyProvider()).handle,
        {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
    )
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
    # Prefer the package under test, but keep any approved site-packages roots
    # already present in PYTHONPATH (sealed validation sets PYTHONNOUSERSITE=1
    # and injects those roots via PYTHONPATH). Overwriting PYTHONPATH entirely
    # drops core deps such as anyio and fails hermetic bootstrap incorrectly.
    package_root_s = str(package_root)
    existing = os.environ.get("PYTHONPATH", "").strip()
    pythonpath = (
        os.pathsep.join([package_root_s, existing]) if existing else package_root_s
    )
    environment = {**os.environ, "PYTHONPATH": pythonpath}
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
