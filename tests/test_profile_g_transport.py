import json
import asyncio
import pytest

from ipfs_kit_py.mcp_server.mcplusplus.profile_g_transport import (
    METHODS,
    ProfileGDispatcher,
    configure_dispatcher,
)
from ipfs_kit_py.mcp_server.p2p_transport import handle_stream_message
from ipfs_kit_py.mcp_server.server import MCPServer, _profile_g_rest_binding


def test_profile_g_jsonrpc_and_profile_e_have_semantic_parity():
    dispatcher = ProfileGDispatcher(
        lambda method, params: {"method": method, "params": dict(params)}
    )
    configure_dispatcher(dispatcher)
    server = MCPServer()
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "mcp++/schedule/status",
        "params": {"task_cid": "bafy-task"},
    }
    http_result = asyncio.run(server.handle(request))
    p2p_bytes = asyncio.run(handle_stream_message(json.dumps(request).encode(), server.handle))
    assert json.loads(p2p_bytes) == http_result


def test_profile_g_descriptor_and_rest_bindings_are_complete():
    metadata = ProfileGDispatcher().metadata
    assert metadata["methods"] == list(METHODS)
    assert _profile_g_rest_binding("POST", "/mcp/goals/bafy-goal/select") == (
        "mcp++/goals/select",
        {"goal_cid": "bafy-goal"},
    )
    assert _profile_g_rest_binding("POST", "/mcp/schedule/claims/bafy-claim/release") == (
        "mcp++/schedule/release",
        {"claim_cid": "bafy-claim"},
    )


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/mcp/goals/bafy-goal/select"),
        ("POST", "/mcp/schedule/claims/bafy-claim/unknown"),
        ("POST", "/mcp/goals/bafy-goal/select/extra"),
        ("GET", "/mcp/interfaces"),
        (None, "/mcp/schedule/frontier"),
        ("GET", None),
    ],
)
def test_legacy_profile_g_binding_rejects_non_profile_or_unmatched_routes(method, path):
    assert _profile_g_rest_binding(method, path) is None


def test_legacy_profile_g_binding_uses_the_canonical_registry(monkeypatch):
    import ipfs_kit_py.mcp_server.server as server_module

    calls = []

    def resolve(method, path):
        calls.append((method, path))
        return "mcp++/schedule/status", {"task_cid": "registry-selected"}

    monkeypatch.setattr(server_module, "resolve_rest_route", resolve)
    assert server_module._profile_g_rest_binding("GET", "/provided-to-registry") == (
        "mcp++/schedule/status", {"task_cid": "registry-selected"}
    )
    assert calls == [("GET", "/provided-to-registry")]
