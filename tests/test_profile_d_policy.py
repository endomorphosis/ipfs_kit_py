"""Profile D bridge coverage for the IPFS Kit package and transport paths."""

import asyncio
import json

from ipfs_kit_py.mcp.profile_d_policy import evaluate_execution_policy
from ipfs_kit_py.mcp_server.p2p_transport import handle_stream_message
from ipfs_kit_py.mcp_server.server import MCPServer, create_http_app


def test_ipfs_kit_uses_datasets_profile_d_export() -> None:
    result = evaluate_execution_policy(
        actor="did:key:kit",
        action="pin.add",
        resource="bafycontent",
        policy={
            "clauses": [
                {
                    "clause_type": "permission",
                    "actor": "did:key:kit",
                    "action": "pin.add",
                    "resource": "bafycontent",
                }
            ]
        },
    )

    assert result["decision"] == "allow"
    assert result["policy_source"] == "explicit"
    assert result["zkp_certificate"]["status"] == "statement_ready"
    assert result["zkp_certificate"]["zero_knowledge"] is False


def test_ipfs_kit_http_and_p2p_paths_share_canonical_profile_d_evaluation() -> None:
    server = MCPServer()
    request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "mcp++/policy/evaluate",
        "params": {
            "actor": "did:key:kit",
            "action": "pin.add",
            "policy": {
                "clauses": [
                    {
                        "clause_type": "prohibition",
                        "actor": "did:key:kit",
                        "action": "pin.add",
                    }
                ]
            },
            "request_zkp_certificate": True,
        },
    }

    async def call_http() -> tuple[int, dict]:
        sent = []
        body = json.dumps(request["params"]).encode()

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            sent.append(message)

        await create_http_app(server)(
            {"type": "http", "method": "POST", "path": "/mcp/policy/evaluate", "headers": []},
            receive,
            send,
        )
        return sent[0]["status"], json.loads(sent[1]["body"])

    http_status, http_response = asyncio.run(call_http())
    p2p_response = json.loads(asyncio.run(handle_stream_message(json.dumps(request).encode(), server.handle)))
    initialization = asyncio.run(server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}))

    assert "mcp++/deontic-policy" in initialization["result"]["capabilities"]["mcpPlusPlusProfiles"]
    assert http_status == 200
    assert http_response["decision"] == "deny"
    assert p2p_response["result"]["decision"] == "deny"
    assert p2p_response["result"]["zkp_certificate"]["status"] == "statement_ready"
