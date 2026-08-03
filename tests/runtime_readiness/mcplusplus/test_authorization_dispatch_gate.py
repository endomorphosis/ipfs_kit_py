"""Regression coverage for the fail-closed MCP tool authorization gate."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import pytest

from ipfs_kit_py.mcp.profile_d_policy import policy_root
from ipfs_kit_py.mcp_server import mcplusplus
from ipfs_kit_py.mcp_server.authorization import semantic_decision_cid
from ipfs_kit_py.mcp_server.mcplusplus.event_dag import EventDAGStore
from ipfs_kit_py.mcp_server.server import MCPServer, create_http_app


TOOL = "pin_tools/pin_rm"
RESOURCE = "ipfs://tenant-a/pins/bafy-test"
ACTOR = "did:key:tenant-a-client"
BEARER = "eyJ.not-a-real-bearer-token.signature"


class _Ledger:
    def __init__(self, available: bool = True) -> None:
        self.available = available


@dataclass
class _Verification:
    allowed: bool
    code: str = "ok"

    @property
    def reason(self) -> str:
        return self.code

    def to_receipt(self) -> dict[str, Any]:
        # The raw token is intentional: the gate must redact even a bad
        # verifier extension rather than copying its receipt wholesale.
        return {"schema": "test-receipt", "allowed": self.allowed, "code": self.code,
                "chain_length": 1, "token": BEARER}


class _Verifier:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.calls: list[dict[str, Any]] = []

    def verify(self, chain: Any, **kwargs: Any) -> _Verification:
        self.calls.append({"chain": chain, **kwargs})
        return _Verification(self.allowed, "ok" if self.allowed else "capability_denied")


class _PolicyProvider:
    def __init__(self, available: bool = True, decision: str = "allow") -> None:
        self.available = available
        self.decision = decision
        self.calls: list[dict[str, Any]] = []

    def metadata(self) -> dict[str, Any]:
        return {"provider": "test-canonical-profile-d", "available": self.available, "fail_closed": True}

    def evaluate(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {
            "decision": self.decision,
            "policy_root": policy_root(kwargs.get("policy"), kwargs.get("policy_text")),
        }


def _valid_envelope(arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool": TOOL,
        "resource": RESOURCE,
        "ability": TOOL,
        "actor": ACTOR,
        "ucan": BEARER,
        "policy_root": policy_root(arguments.get("policy"), arguments.get("policy_text")),
        "request_id": "request-authorization-42",
        "transaction_id": "request-authorization-42",
    }


def _params() -> dict[str, Any]:
    arguments = {"resource": RESOURCE, "cid": "bafy-test", "private_input": "do-not-audit-this"}
    return {"name": TOOL, "arguments": arguments, "_mcppp_envelope": _valid_envelope(arguments)}


def _server(tmp_path, *, validator_available: bool = True, verifier_allowed: bool = True,
            ledger_available: bool = True, provider_available: bool = True,
            policy_decision: str = "allow") -> tuple[MCPServer, EventDAGStore, list[tuple[str, str, dict[str, Any]]], _Verifier, _PolicyProvider]:
    dag = EventDAGStore(storage_dir=str(tmp_path / "durable-audit"))
    verifier, provider = _Verifier(verifier_allowed), _PolicyProvider(provider_available, policy_decision)
    server = MCPServer(
        event_dag=dag,
        policy_provider=provider,
        ucan_ledger=_Ledger(ledger_available),
        ucan_verifier=verifier,
        envelope_validator=mcplusplus.validate_packet if validator_available else None,
        validator_available=validator_available,
    )
    calls: list[tuple[str, str, dict[str, Any]]] = []

    async def dispatch(category: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        calls.append((category, tool, arguments))
        return {"status": "ok"}

    server.tm.dispatch = dispatch
    return server, dag, calls, verifier, provider


def _call(server: MCPServer, params: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(server.handle({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": params}))


async def _rest_policy_evaluate(server: MCPServer) -> dict[str, Any]:
    """Exercise the public REST alias instead of its internal MCP route."""

    app = create_http_app(server)
    request_body = json.dumps({"actor": ACTOR, "action": TOOL, "resource": RESOURCE}).encode("utf-8")
    sent: list[dict[str, Any]] = []
    received = False

    async def receive() -> dict[str, Any]:
        nonlocal received
        if received:
            return {"type": "http.disconnect"}
        received = True
        return {"type": "http.request", "body": request_body, "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    await app(
        {
            "type": "http",
            "method": "POST",
            "path": "/mcp/policy/evaluate",
            "query_string": b"",
            "headers": [],
        },
        receive,
        send,
    )
    assert sent[0]["status"] == 200
    return json.loads(sent[1]["body"])


def test_allowed_dispatch_binds_every_effect_to_the_same_authorization_identity(tmp_path) -> None:
    server, dag, calls, verifier, _provider = _server(tmp_path)

    response = _call(server, _params())

    assert response["result"]["status"] == "ok"
    assert len(calls) == 1
    assert verifier.calls == [{
        "chain": BEARER, "expected_resource": RESOURCE, "expected_ability": TOOL,
        "expected_audience": ACTOR, "request_bounds": {},
    }]
    authorization = response["result"]["_authorization"]
    assert authorization["request_id"] == authorization["transaction_id"] == "request-authorization-42"
    events = dag.history(limit=10)["events"]
    allowed = next(event for event in events if event["event_type"] == "authorization.decision")
    effect = next(event for event in events if event["event_type"] == "authorization.effect")
    assert (allowed["request_id"], allowed["transaction_id"]) == (effect["request_id"], effect["transaction_id"])
    assert effect["parents"] == [allowed["event_cid"]]
    assert effect["authorization_event_cid"] == allowed["event_cid"]
    rendered = json.dumps(events, sort_keys=True)
    assert BEARER not in rendered and "do-not-audit-this" not in rendered
    assert "token" not in allowed["ucan_receipt"]


@pytest.mark.parametrize("case", [
    "missing_envelope", "validator_unavailable", "tool_mismatch", "resource_mismatch",
    "ability_mismatch", "policy_root_mismatch", "ucan_denied", "policy_denied",
    "provider_unavailable", "ledger_unavailable",
])
def test_every_negative_authorization_case_stops_before_the_handler(tmp_path, case: str) -> None:
    options: dict[str, Any] = {}
    if case == "validator_unavailable":
        options["validator_available"] = False
    elif case == "ucan_denied":
        options["verifier_allowed"] = False
    elif case == "policy_denied":
        options["policy_decision"] = "deny"
    elif case == "provider_unavailable":
        options["provider_available"] = False
    elif case == "ledger_unavailable":
        options["ledger_available"] = False
    server, dag, calls, _verifier, _provider = _server(tmp_path, **options)
    params = _params()
    envelope = params["_mcppp_envelope"]
    if case == "missing_envelope":
        params.pop("_mcppp_envelope")
    elif case == "tool_mismatch":
        envelope["tool"] = "other/tool"
    elif case == "resource_mismatch":
        envelope["resource"] = "ipfs://tenant-b/pins/bafy-test"
    elif case == "ability_mismatch":
        envelope["ability"] = "other/tool"
    elif case == "policy_root_mismatch":
        envelope["policy_root"] = "sha256:wrong"

    response = _call(server, params)

    assert response["error"]["data"]["authorization"] == "denied"
    assert calls == []
    assert dag.history(limit=10)["count"] >= 1


def test_policy_route_and_advertisement_share_the_injected_canonical_provider(tmp_path) -> None:
    server, _dag, _calls, _verifier, provider = _server(tmp_path)

    initialized = asyncio.run(server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}))
    evaluated = asyncio.run(_rest_policy_evaluate(server))

    metadata = initialized["result"]["profile_metadata"]["mcp++/deontic-policy"]
    assert metadata["provider"] == "test-canonical-profile-d"
    assert "mcp++/deontic-policy" in initialized["result"]["capabilities"]["mcpPlusPlusProfiles"]
    assert evaluated["decision"] == "allow"
    assert provider.calls[0]["action"] == TOOL


def test_semantic_decision_cid_binds_principal_resource_policy_and_identity() -> None:
    basis = {
        "schema": "ipfs-kit.authorization-audit@1",
        "event_type": "authorization.decision",
        "decision": "deny",
        "reason": "policy_denied",
        "tool": TOOL,
        "actor_digest": "sha256:actor-a",
        "resource_digest": "sha256:resource-a",
        "ability": TOOL,
        "policy_root": "sha256:policy-a",
        "request_identity_digest": "sha256:request-a",
    }
    baseline = semantic_decision_cid(basis)

    for field, replacement in (
        ("actor_digest", "sha256:actor-b"),
        ("resource_digest", "sha256:resource-b"),
        ("ability", "pin_tools/pin_add"),
        ("policy_root", "sha256:policy-b"),
        ("request_identity_digest", "sha256:request-b"),
    ):
        assert semantic_decision_cid({**basis, field: replacement}) != baseline
