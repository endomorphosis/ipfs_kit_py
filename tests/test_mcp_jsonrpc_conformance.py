#!/usr/bin/env python3
"""Base-MCP conformance tests for the consolidated dashboard JSON-RPC endpoint.

Verifies that a *stock* MCP client can complete the standard handshake against
``POST /mcp`` (initialize -> notifications/initialized -> tools/list ->
tools/call) and that responses match the MCP 2024-11-05 wire shapes, while the
legacy path-based REST routes remain intact (backwards compatibility).
"""

import os
import sys
from pathlib import Path

import pytest

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

os.environ.setdefault("IPFS_KIT_FAST_INIT", "1")

starlette_testclient = pytest.importorskip("starlette.testclient")
pytest.importorskip("fastapi")

from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard  # noqa: E402


@pytest.fixture(scope="module")
def client():
    dashboard = ConsolidatedMCPDashboard({"port": 8004})
    return starlette_testclient.TestClient(dashboard.app)


def _rpc(client, body):
    return client.post("/mcp", json=body)


def test_initialize_handshake(client):
    resp = _rpc(client, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp.status_code == 200
    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 1
    result = body["result"]
    assert result["protocolVersion"] == "2024-11-05"
    assert result["serverInfo"]["name"] == "mcp++"
    assert result["serverInfo"]["version"] == "1.0.0"
    assert result["capabilities"]["tools"]["listChanged"] is True
    assert "experimental" in result["capabilities"]


def test_initialized_notification_has_no_response_body(client):
    resp = _rpc(client, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    # Notifications carry no id and must not produce a JSON-RPC response.
    assert resp.status_code == 202
    assert resp.content in (b"", b"null")


def test_ping(client):
    resp = _rpc(client, {"jsonrpc": "2.0", "id": 7, "method": "ping"})
    assert resp.status_code == 200
    assert resp.json() == {"jsonrpc": "2.0", "id": 7, "result": {}}


def test_tools_list_shape(client):
    resp = _rpc(client, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert resp.status_code == 200
    tools = resp.json()["result"]["tools"]
    assert isinstance(tools, list) and tools
    for tool in tools:
        assert set(("name", "description", "inputSchema")).issubset(tool.keys())
    assert any(t["name"] == "health_check" for t in tools)


def test_tools_call_returns_mcp_content(client):
    resp = _rpc(
        client,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "health_check", "arguments": {}},
        },
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert isinstance(result["content"], list)
    assert result["content"][0]["type"] == "text"
    assert result["isError"] is False


def test_unknown_method_returns_method_not_found(client):
    resp = _rpc(client, {"jsonrpc": "2.0", "id": 4, "method": "does/not/exist"})
    assert resp.status_code == 200
    assert resp.json()["error"]["code"] == -32601


def test_batch_request(client):
    resp = _rpc(
        client,
        [
            {"jsonrpc": "2.0", "id": 10, "method": "ping"},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 11, "method": "tools/list"},
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    ids = sorted(item["id"] for item in body)
    assert ids == [10, 11]


def test_legacy_rest_routes_still_work(client):
    assert client.get("/api/mcp/status").status_code == 200
    assert client.get("/mcp/tools/list").status_code == 200
    call = client.post(
        "/mcp/tools/call",
        json={"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "health_check", "arguments": {}}},
    )
    assert call.status_code == 200
    assert call.json()["id"] == 9


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
