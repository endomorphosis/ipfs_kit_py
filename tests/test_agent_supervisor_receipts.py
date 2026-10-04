import asyncio
import json

from ipfs_kit_py.mcp_server.agent_supervisor_receipts import (
    AgentSupervisorReceiptResolver,
    CAPABILITY_ID,
    MAX_LIMIT,
    METHOD,
    descriptor,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import DurableCoordinationStore
from ipfs_kit_py.mcp_server.p2p_transport import handle_stream_message
from ipfs_kit_py.mcp_server.server import (
    MCPServer,
    _agent_supervisor_rest_binding,
    create_http_app,
)


async def _asgi_request(app, method, path, *, body=None, query=b""):
    request_events = [{
        "type": "http.request",
        "body": json.dumps(body).encode() if body is not None else b"",
        "more_body": False,
    }]
    response_events = []

    async def receive():
        return request_events.pop(0)

    async def send(event):
        response_events.append(event)

    await app({
        "type": "http",
        "method": method,
        "path": path,
        "query_string": query,
    }, receive, send)
    status = next(event["status"] for event in response_events if event["type"] == "http.response.start")
    payload = b"".join(event.get("body", b"") for event in response_events if event["type"] == "http.response.body")
    return status, json.loads(payload) if payload else None


def test_resolves_only_verified_immutable_receipts_and_preserves_transport_parity(tmp_path):
    store = DurableCoordinationStore(tmp_path / "coordination")
    stored = store.put({
        "schema": "swissknife/agent-supervisor/receipt@1",
        "kind": "AgentSupervisorReceipt",
        "receipt_id": "receipt-live-1",
        "created_at": "2026-07-13T12:00:00+00:00",
        "decision": "observed",
    })
    server = MCPServer(AgentSupervisorReceiptResolver(store))
    request = {
        "jsonrpc": "2.0", "id": "receipt-1", "method": METHOD,
        "params": {"receipt_ids": ["receipt-live-1"]},
    }

    http_result = asyncio.run(server.handle(request))
    p2p_result = json.loads(asyncio.run(
        handle_stream_message(json.dumps(request).encode(), server.handle)
    ))

    assert p2p_result["id"] == http_result["id"]
    assert p2p_result["result"]["state"] == http_result["result"]["state"]
    assert p2p_result["result"]["data"] == http_result["result"]["data"]
    assert http_result["result"]["state"] == "available"
    assert http_result["result"]["owner"] == "ipfs_kit_py"
    assert http_result["result"]["data"] == [{
        "receipt_id": "receipt-live-1",
        "cid": stored["cid"],
        "owner": "ipfs_kit_py",
        "created_at": "2026-07-13T12:00:00+00:00",
    }]
    store.close()


def test_missing_receipt_and_wrong_owner_fail_closed(tmp_path):
    store = DurableCoordinationStore(tmp_path / "coordination")
    resolver = AgentSupervisorReceiptResolver(store)

    missing = resolver.read({"receipt_ids": ["receipt-does-not-exist"]})
    assert missing["state"] == "unavailable"
    assert missing["reason"] == "receipt_unavailable"
    assert "receipt-does-not-exist" in missing["message"]

    denied = resolver.read({"owner": "ipfs_datasets_py", "receipt_ids": []})
    assert denied["state"] == "denied"
    assert denied["reason"] == "scope_not_allowed"
    assert denied["owner"] == "ipfs_kit_py"
    store.close()


def test_gateway_envelope_is_mediated_and_correlation_is_preserved(tmp_path):
    store = DurableCoordinationStore(tmp_path / "coordination")
    stored = store.put({
        "schema": "ipfs_kit.agent_supervisor_receipt.v1",
        "receipt_id": "receipt-envelope",
        "status": "completed",
        "target_id": "SVD-094",
    })
    resolver = AgentSupervisorReceiptResolver(store)
    invocation = {
        "capability_id": CAPABILITY_ID,
        "owner": "ipfs_kit_py",
        "method": METHOD,
        "access": "read",
        "policy_class": "read",
        "payload": {
            "receipt_ids": [stored["cid"]],
            "status": "completed",
            "target_id": "SVD-094",
        },
        "correlation_id": "corr-receipt-envelope",
    }

    result = resolver.read(invocation)

    assert result["state"] == "available"
    assert result["correlation_id"] == "corr-receipt-envelope"
    assert result["data"][0]["receipt_id"] == "receipt-envelope"

    denied = resolver.read({**invocation, "method": "agent_supervisor.logs.read"})
    assert denied == {
        "state": "denied",
        "capability_id": CAPABILITY_ID,
        "owner": "ipfs_kit_py",
        "reason": "scope_not_allowed",
        "message": f"{METHOD} requires method={METHOD}",
        "policy_class": "read",
        "correlation_id": "corr-receipt-envelope",
    }
    store.close()


def test_filters_pagination_and_validation_match_console_schema(tmp_path):
    store = DurableCoordinationStore(tmp_path / "coordination")
    for index in range(3):
        store.put({
            "schema": "ipfs_kit.agent_supervisor_receipt.v1",
            "receipt_id": f"receipt-{index}",
            "status": "completed" if index != 1 else "failed",
            "normalized_target": f"task:SVD-09{index}",
            "created_at_ms": index + 1,
        })
    resolver = AgentSupervisorReceiptResolver(store)

    page = resolver.read({"status": "completed", "limit": 1, "cursor": "1"})
    target = resolver.read({"target_id": "SVD-092"})

    assert page["state"] == "available" and len(page["data"]) == 1
    assert target["state"] == "available"
    assert [item["receipt_id"] for item in target["data"]] == ["receipt-2"]
    assert resolver.read({"limit": MAX_LIMIT + 1})["state"] == "denied"
    assert resolver.read({"cursor": "opaque"})["reason"] == "scope_not_allowed"
    assert resolver.read({"receipt_ids": [""]})["reason"] == "scope_not_allowed"
    assert resolver.read({"unexpected": True})["reason"] == "scope_not_allowed"
    store.close()


def test_read_is_non_mutating_and_corrupt_blocks_fail_closed(tmp_path):
    store = DurableCoordinationStore(tmp_path / "coordination")
    stored = store.put({
        "schema": "ipfs_kit.agent_supervisor_receipt.v1",
        "receipt_id": "receipt-corrupt",
        "created_at_ms": 1,
    })
    resolver = AgentSupervisorReceiptResolver(store)
    block = store._block_path(stored["cid"])
    before = {path: path.read_bytes() for path in store.blocks_dir.rglob("*.json")}

    assert resolver.read({"receipt_ids": [stored["cid"]]})["state"] == "available"
    assert {path: path.read_bytes() for path in store.blocks_dir.rglob("*.json")} == before

    block.write_text('{"schema":"tampered"}', encoding="utf-8")
    unavailable = resolver.read({"receipt_ids": [stored["cid"]]})
    assert unavailable["state"] == "unavailable"
    assert unavailable["reason"] == "receipt_unavailable"
    store.close()


def test_receipt_method_is_in_tools_interfaces_and_rest_binding(tmp_path):
    store = DurableCoordinationStore(tmp_path / "coordination")
    server = MCPServer(AgentSupervisorReceiptResolver(store))

    tools = asyncio.run(server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}))
    interfaces = asyncio.run(server.handle({"jsonrpc": "2.0", "id": 2, "method": "mcp++/interfaces"}))
    assert any(item["name"] == METHOD and item["owner"] == "ipfs_kit_py" for item in tools["result"]["tools"])
    assert any(item["name"] == METHOD and item["owner"] == "ipfs_kit_py" for item in interfaces["result"]["interfaces"])
    assert _agent_supervisor_rest_binding("GET", "/mcp/agent-supervisor/receipts") == (METHOD, {})
    assert _agent_supervisor_rest_binding("POST", "/mcp/agent-supervisor/receipts") == (METHOD, {})
    assert _agent_supervisor_rest_binding("GET", "/mcp/agent-supervisor/receipts/bafy123") == (
        METHOD, {"receipt_ids": ["bafy123"]},
    )
    assert _agent_supervisor_rest_binding("POST", "/mcp/agent-supervisor/receipts/bafy123") is None

    schema = descriptor()
    assert schema["inputSchema"]["properties"]["limit"]["maximum"] == 500
    assert {"status", "target_id", "receipt_ids"} <= set(schema["inputSchema"]["properties"])
    assert schema["outputSchema"]["properties"]["data"]["items"]["properties"]["owner"] == {
        "const": "ipfs_kit_py",
    }
    store.close()


def test_http_gateway_envelope_and_direct_cid_routes_share_verified_resolver(tmp_path):
    store = DurableCoordinationStore(tmp_path / "coordination")
    stored = store.put({
        "schema": "ipfs_kit.agent_supervisor_receipt.v1",
        "receipt_id": "receipt-http",
        "created_at": "2026-07-13T12:00:00+00:00",
    })
    server = MCPServer(AgentSupervisorReceiptResolver(store))
    app = create_http_app(server)
    before_dag = json.dumps(server._dag._state, sort_keys=True)
    invocation = {
        "capability_id": CAPABILITY_ID,
        "owner": "ipfs_kit_py",
        "method": METHOD,
        "access": "read",
        "policy_class": "read",
        "payload": {"receipt_ids": ["receipt-http"]},
        "correlation_id": "corr-http",
    }

    post_status, post_result = asyncio.run(_asgi_request(
        app, "POST", "/mcp/agent-supervisor/receipts", body=invocation,
    ))
    get_status, get_result = asyncio.run(_asgi_request(
        app, "GET", f"/mcp/agent-supervisor/receipts/{stored['cid']}",
    ))
    rpc_status, rpc_result = asyncio.run(_asgi_request(
        app,
        "POST",
        "/mcp/agent-supervisor/receipts",
        body={
            "jsonrpc": "2.0",
            "id": "receipt-http-rpc",
            "method": METHOD,
            "params": {"receipt_ids": ["receipt-http"]},
        },
    ))

    assert post_status == get_status == rpc_status == 200
    assert post_result["state"] == get_result["state"] == "available"
    assert post_result["data"] == get_result["data"]
    assert rpc_result["id"] == "receipt-http-rpc"
    assert rpc_result["result"]["data"] == get_result["data"]
    assert post_result["correlation_id"] == "corr-http"
    assert json.dumps(server._dag._state, sort_keys=True) == before_dag
    store.close()
