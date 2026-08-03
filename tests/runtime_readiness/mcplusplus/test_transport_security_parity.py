"""KITA-033: MCP++ authorization and result parity across stdio, HTTP, and P2P.

Proves that the single AuthorizationGate admits or denies identically on every
transport framing, that denials share a canonical code + decision CID with zero
dispatch, that allowed results share semantic CIDs after transport normalization,
and that signed-token security (downgrade, confused deputy, revocation, replay)
is backed by real cryptography — never MagicMock-only evidence.
"""

from __future__ import annotations

import asyncio
import base64
import json
import socket
import time
import urllib.request
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ipfs_kit_py.backends.ipfs_backend import HermeticIPFSFixtureAdapter
from ipfs_kit_py.mcp.profile_d_policy import get_profile_d_policy_provider, policy_root
from ipfs_kit_py.mcp_server import core_operations, mcplusplus
from ipfs_kit_py.mcp_server.authorization import semantic_decision_cid
from ipfs_kit_py.mcp_server.mcplusplus import artifacts
from ipfs_kit_py.mcp_server.mcplusplus.event_dag import EventDAGStore
from ipfs_kit_py.mcp_server.mcplusplus.revocation import RevocationLedger
from ipfs_kit_py.mcp_server.mcplusplus.ucan import (
    UCANVerifier,
    issue_ucan,
    public_key_bytes,
    ucan_token_id,
)
from ipfs_kit_py.mcp_server.p2p_transport import PROTOCOL_ID, handle_stream_message
from ipfs_kit_py.mcp_server.server import MCPServer, create_http_app, handle_stdio_line
import ipfs_kit_py.mcp_server.authorization as authorization_module


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRANSPORTS: tuple[str, ...] = ("stdio", "http", "p2p")
TOOL = "pin_tools/pin_add"
RESOURCE = "ipfs://tenant-a/pins/bafy-test"
ACTOR = "did:client:tenant-a"
ISSUER = "did:key:root-tenant-a"
SERVICE = "did:service:tenant-a"
DEPUTY = "did:client:confused-deputy"
FIXED_TS = "2026-01-01T00:00:00+00:00"
CONFORMANCE_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "runtime_readiness"
    / "mcplusplus_conformance.json"
)

ALLOW_POLICY: dict[str, Any] = {
    "policy_id": "tenant-a-allow-pin-rm",
    "version": "v1",
    "clauses": [
        {
            "clause_type": "permission",
            "actor": "*",
            "action": TOOL,
            "resource": "ipfs://tenant-a/*",
        }
    ],
}

DENY_POLICY: dict[str, Any] = {
    "policy_id": "tenant-a-deny-pin-rm",
    "version": "v1",
    "clauses": [
        {
            "clause_type": "prohibition",
            "actor": "*",
            "action": TOOL,
            "resource": "ipfs://tenant-a/*",
        }
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _b64json(value: dict[str, Any]) -> str:
    return (
        base64.urlsafe_b64encode(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        )
        .decode()
        .rstrip("=")
    )


def semantic_result_cids(response: Mapping[str, Any]) -> dict[str, Any]:
    """Extract every Profile-B CID plus the production semantic result."""

    result = response.get("result") or {}
    meta = result.get("_mcppp") or {}
    return {
        "status": result.get("status"),
        "body": artifacts.semantic_result_payload(
            {
                key: value
                for key, value in result.items()
                if key not in {"_mcppp", "_authorization"}
            }
        ),
        "interface_cid": meta.get("interface_cid"),
        "input_cid": meta.get("input_cid"),
        "intent_cid": meta.get("intent_cid"),
        "decision_cid": meta.get("decision_cid"),
        "output_cid": meta.get("output_cid"),
        "receipt_cid": meta.get("receipt_cid"),
        "event_cid": meta.get("event_cid"),
        "content_cid": (result.get("result") or {}).get("content_cid"),
        "version": (result.get("result") or {}).get("version"),
        "transaction_cid": (result.get("result") or {}).get("transaction_cid"),
        "authorization_decision": (result.get("_authorization") or {}).get("decision"),
        "authorization_tool": (result.get("_authorization") or {}).get("tool"),
        "authorization_ability": (result.get("_authorization") or {}).get("ability"),
        "authorization_policy_root": (result.get("_authorization") or {}).get("policy_root"),
    }


# ---------------------------------------------------------------------------
# Fixture environment: real crypto, real ledger, real Profile D
# ---------------------------------------------------------------------------


class _HermeticCoreBackend:
    """Explicit MCP core binding backed by the certified fixture adapter."""

    def __init__(self, root: Path) -> None:
        self.adapter = HermeticIPFSFixtureAdapter(root)
        self.fail = False

    async def ipfs_pin_add(self, cid: str, recursive: bool = True) -> dict[str, Any]:
        if self.fail:
            return {
                "success": False,
                "error": "hermetic pin precondition rejected",
                "error_type": "precondition_failed",
                "pinned": cid,
            }
        result = await self.adapter.put(
            f"pins/{cid}",
            cid.encode("utf-8"),
            metadata={"recursive": bool(recursive)},
            idempotency_key=f"pin-add:{cid}:{bool(recursive)}",
        )
        transaction_cid = artifacts.compute_artifact_cid(
            {
                "operation": result.operation,
                "backend_id": result.canonical_result.backend_id,
                "content_cid": result.resulting_content_cid,
                "effect_count": result.observed_effect_count,
            }
        )
        return {
            "success": True,
            "pinned": cid,
            "content_cid": result.resulting_content_cid,
            "version": result.observed_effect_count,
            "transaction_cid": transaction_cid,
            "backend_id": result.canonical_result.backend_id,
        }


class _Harness:
    """Per-transport hermetic server with a dispatch spy and durable ledger."""

    def __init__(
        self,
        root: Path,
        *,
        nonce_seed: str,
        root_key: Ed25519PrivateKey | None = None,
    ) -> None:
        self.root = root
        self.nonce_seed = nonce_seed
        self.nonce_counter = 0
        self.root_key = root_key or Ed25519PrivateKey.generate()
        self.ledger = RevocationLedger(root / "ucan-revocation-ledger.json")
        self.ledger.register_public_key(ISSUER, "root-v1", public_key_bytes(self.root_key))
        self.verifier = UCANVerifier(ledger=self.ledger, trusted_issuers={ISSUER})
        assert type(self.verifier).__name__ == "UCANVerifier"
        assert type(self.ledger).__name__ == "RevocationLedger"
        self.dag = EventDAGStore(storage_dir=str(root / "event-dag"))
        self.provider = get_profile_d_policy_provider()
        assert self.provider.available is True
        self.server = MCPServer(
            event_dag=self.dag,
            policy_provider=self.provider,
            ucan_ledger=self.ledger,
            ucan_verifier=self.verifier,
            envelope_validator=mcplusplus.validate_packet,
            validator_available=True,
        )
        self.backend = _HermeticCoreBackend(root / "backend")
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        original_dispatch = self.server.tm.dispatch

        async def dispatch(category: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
            self.calls.append((category, tool, dict(arguments)))
            return await original_dispatch(category, tool, arguments)

        self.server.tm.dispatch = dispatch  # type: ignore[method-assign]

    def next_nonce(self, label: str) -> str:
        self.nonce_counter += 1
        return f"{self.nonce_seed}-{label}-{self.nonce_counter}"

    def issue(
        self,
        *,
        audience: str = ACTOR,
        resource: str = RESOURCE,
        ability: str = TOOL,
        nonce: str | None = None,
        exp_delta: float = 300.0,
        nbf_delta: float | None = None,
        kid: str = "root-v1",
        key: Ed25519PrivateKey | None = None,
        proofs: tuple[str, ...] = (),
        issuer: str = ISSUER,
        bounds: Mapping[str, Any] | None = None,
    ) -> str:
        now = time.time()
        capability: dict[str, Any] = {"resource": resource, "ability": ability}
        if bounds is not None:
            capability["bounds"] = dict(bounds)
        return issue_ucan(
            issuer=issuer,
            audience=audience,
            capabilities=[capability],
            private_key=key or self.root_key,
            kid=kid,
            expires_at=now + exp_delta,
            not_before=(now + nbf_delta) if nbf_delta is not None else None,
            nonce=nonce or self.next_nonce("token"),
            proofs=proofs,
            issued_at=now - 10,
        )

    def arguments(self, *, policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return {
            "resource": RESOURCE,
            "cid": "bafy-test",
            "policy": dict(policy or ALLOW_POLICY),
            "private_input": "do-not-audit-this-secret",
        }

    def envelope(
        self,
        arguments: Mapping[str, Any],
        token: str,
        *,
        request_id: str,
        actor: str = ACTOR,
        tool: str = TOOL,
        resource: str = RESOURCE,
        ability: str = TOOL,
        policy: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "tool": tool,
            "resource": resource,
            "ability": ability,
            "actor": actor,
            "ucan": token,
            "policy_root": policy_root(policy or arguments.get("policy"), arguments.get("policy_text")),
            "request_id": request_id,
            "transaction_id": request_id,
        }

    def message(
        self,
        *,
        params: dict[str, Any] | None = None,
        request_id: int = 7,
        profile_b: bool = False,
    ) -> dict[str, Any]:
        body = params if params is not None else {}
        if profile_b:
            body = {**body, "profile_b": True}
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": body,
        }

    def invoke(self, transport: str, message: Mapping[str, Any]) -> dict[str, Any]:
        with core_operations.use_core_backend(self.backend):
            return _run(TRANSPORT_CALLERS[transport](self.server, message))


def _freeze_auth_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authorization_module, "_now", lambda: FIXED_TS)


async def call_stdio(server: MCPServer, message: Mapping[str, Any]) -> dict[str, Any]:
    encoded = json.dumps(message, separators=(",", ":")) + "\n"
    response_line = await handle_stdio_line(server, encoded)
    assert response_line is not None and response_line.endswith("\n")
    return json.loads(response_line)


async def call_http(server: MCPServer, message: Mapping[str, Any]) -> dict[str, Any]:
    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    config = Config()
    config.bind = [f"127.0.0.1:{port}"]
    config.accesslog = None
    config.errorlog = None
    stopped = asyncio.Event()
    task = asyncio.create_task(
        serve(
            create_http_app(server),
            config,
            shutdown_trigger=stopped.wait,
        )
    )

    def post() -> dict[str, Any]:
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/mcp",
            data=json.dumps(message, separators=(",", ":")).encode("utf-8"),
            headers={"content-type": "application/json"},
        )
        return json.loads(urllib.request.urlopen(request, timeout=2).read())

    try:
        last_error: Exception | None = None
        for _ in range(40):
            if task.done():
                await task
                raise AssertionError("Hypercorn stopped before serving the request")
            try:
                return await asyncio.to_thread(post)
            except Exception as error:
                last_error = error
                await asyncio.sleep(0.025)
        raise AssertionError("Hypercorn HTTP framing never became ready") from last_error
    finally:
        stopped.set()
        await asyncio.wait_for(task, timeout=5)


async def call_p2p(server: MCPServer, message: Mapping[str, Any]) -> dict[str, Any]:
    raw = json.dumps(message).encode("utf-8")
    response = await handle_stream_message(raw, server.handle)
    assert PROTOCOL_ID == "/mcp+p2p/1.0.0"
    if not response:
        return {}
    return json.loads(response)


TRANSPORT_CALLERS: dict[str, Callable[[MCPServer, Mapping[str, Any]], Awaitable[dict[str, Any]]]] = {
    "stdio": call_stdio,
    "http": call_http,
    "p2p": call_p2p,
}


def _run(coro: Awaitable[Any]) -> Any:
    return asyncio.run(coro)


def _latest_decision(dag: EventDAGStore) -> dict[str, Any]:
    events = dag.history(limit=50)["events"]
    decisions = [event for event in events if event.get("event_type") == "authorization.decision"]
    assert decisions, "expected an authorization.decision audit event"
    return decisions[0]


# ---------------------------------------------------------------------------
# Conformance artifact presence
# ---------------------------------------------------------------------------


def test_mcplusplus_conformance_artifact_declares_transport_security_gate() -> None:
    assert CONFORMANCE_PATH.is_file(), f"missing conformance report: {CONFORMANCE_PATH}"
    report = json.loads(CONFORMANCE_PATH.read_text(encoding="utf-8"))
    assert report["schema"] == "ipfs_kit_py/runtime-readiness/mcplusplus-conformance@1"
    assert report["task_id"] == "KITA-033"
    assert report["interfaces"] == ["MCPPlusPlusSecurityReceipt@1"]
    assert set(report["transports"]) == set(TRANSPORTS)
    assert report["acceptance"]["zero_dispatch_on_denial"] is True
    assert report["acceptance"]["no_magicmock_only_security_evidence"] is True
    assert "signed_to_unsigned_downgrade" in report["adversarial_corpus"]
    assert "confused_deputy" in report["adversarial_corpus"]
    assert "revocation_replay_restart" in report["adversarial_corpus"]


# ---------------------------------------------------------------------------
# Denial parity: same code + decision CID, zero dispatch, every transport
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case",
    [
        "missing_envelope",
        "tool_mismatch",
        "resource_mismatch",
        "ability_mismatch",
        "policy_root_mismatch",
        "policy_denied",
        "unsigned_token",
        "tampered_token",
        "algorithm_downgrade",
        "confused_deputy",
        "expired",
        "forged_key",
    ],
)
def test_denial_code_and_decision_cid_match_across_transports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """Every denial yields the same canonical code/decision CID and zero dispatch.

    One shared issuer key and one shared envelope are exercised on independent
    transport servers so decision event digests are transport-invariant when
    the authorization clock is frozen.
    """

    _freeze_auth_clock(monkeypatch)
    shared_key = Ed25519PrivateKey.generate()
    # Build one adversarial signed request, then replay it against independent
    # per-transport ledgers.  A token is consumed only within one ledger, so
    # even policy-denied requests retain identical raw durable event CIDs.
    seed = _Harness(tmp_path / "seed" / case, nonce_seed=f"seed-{case}", root_key=shared_key)
    arguments = seed.arguments(
        policy=DENY_POLICY if case == "policy_denied" else ALLOW_POLICY
    )
    base_params: dict[str, Any] = {"name": TOOL, "arguments": arguments}
    shared_envelope: dict[str, Any] | None = None

    if case != "missing_envelope":
        if case == "unsigned_token":
            signed = seed.issue(nonce="shared-unsigned")
            token = ".".join(signed.split(".")[:2])
        elif case == "tampered_token":
            signed = seed.issue(nonce="shared-tamper")
            token = signed[:-10] + ("A" if signed[-10] != "A" else "B") + signed[-9:]
        elif case == "algorithm_downgrade":
            signed = seed.issue(nonce="shared-downgrade")
            _header, payload, signature = signed.split(".")
            token = (
                _b64json({"alg": "none", "kid": "root-v1", "typ": "UCAN", "v": 1})
                + "."
                + payload
                + "."
                + signature
            )
        elif case == "confused_deputy":
            # Token is bound to DEPUTY; envelope claims ACTOR (confused deputy).
            token = seed.issue(audience=DEPUTY, nonce="shared-deputy")
        elif case == "expired":
            token = seed.issue(nonce="shared-expired", exp_delta=-5)
        elif case == "forged_key":
            forged = Ed25519PrivateKey.generate()
            token = seed.issue(nonce="shared-forged", key=forged)
        else:
            token = seed.issue(nonce=f"shared-{case}")

        shared_envelope = seed.envelope(
            arguments,
            token,
            request_id=f"deny-{case}",
            actor=ACTOR,
        )
        if case == "tool_mismatch":
            shared_envelope["tool"] = "other/tool"
        elif case == "resource_mismatch":
            shared_envelope["resource"] = "ipfs://tenant-b/pins/bafy-test"
        elif case == "ability_mismatch":
            shared_envelope["ability"] = "other/tool"
        elif case == "policy_root_mismatch":
            shared_envelope["policy_root"] = "sha256:wrong-policy-root"
        base_params["_mcppp_envelope"] = shared_envelope

    receipts: dict[str, dict[str, Any]] = {}
    for transport in TRANSPORTS:
        harness = _Harness(
            tmp_path / transport / case,
            nonce_seed=f"{transport}-{case}",
            root_key=shared_key,
        )
        params = dict(base_params)
        message = harness.message(params=params)
        response = harness.invoke(transport, message)

        assert "error" in response, f"{transport}/{case}: expected denial, got {response}"
        error = response["error"]
        assert error["data"]["authorization"] == "denied"
        reason = error["data"]["reason"]
        assert harness.calls == [], f"{transport}/{case}: dispatch must not run on denial"

        decision = _latest_decision(harness.dag)
        assert decision["decision"] == "deny"
        assert decision["reason"] == reason
        # Secrets must never appear in durable audit evidence.
        rendered = json.dumps(decision, sort_keys=True)
        assert "do-not-audit-this-secret" not in rendered
        envelope = params.get("_mcppp_envelope")
        if isinstance(envelope, Mapping) and "ucan" in envelope:
            assert envelope["ucan"] not in rendered

        receipts[transport] = {
            "reason": reason,
            "decision_cid": decision["event_cid"],
            "semantic_decision_cid": decision["semantic_decision_cid"],
            "wire_code": error["code"],
        }
        assert decision["semantic_decision_cid"] == semantic_decision_cid(decision)

    baseline = receipts["stdio"]
    for transport in TRANSPORTS[1:]:
        assert receipts[transport]["reason"] == baseline["reason"], (
            f"{case}: denial code diverged on {transport}"
        )
        assert receipts[transport]["decision_cid"] == baseline["decision_cid"], (
            f"{case}: raw decision event_cid diverged on {transport}"
        )
        assert (
            receipts[transport]["semantic_decision_cid"]
            == baseline["semantic_decision_cid"]
        ), f"{case}: semantic decision CID diverged on {transport}"
        assert receipts[transport]["wire_code"] == baseline["wire_code"]


# ---------------------------------------------------------------------------
# Allowed operations: semantic result / content / version / transaction CIDs
# ---------------------------------------------------------------------------


def test_allowed_result_cids_match_after_transport_normalization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Allowed ops yield identical semantic CIDs after transport normalization."""

    _freeze_auth_clock(monkeypatch)
    normalized: dict[str, dict[str, Any]] = {}
    shared_key = Ed25519PrivateKey.generate()
    seed = _Harness(tmp_path / "allow" / "seed", nonce_seed="allow", root_key=shared_key)
    arguments = seed.arguments()
    token = seed.issue(nonce="allow-shared-token")
    envelope = seed.envelope(arguments, token, request_id="allow-shared-request")

    for transport in TRANSPORTS:
        harness = _Harness(
            tmp_path / "allow" / transport,
            nonce_seed=f"allow-{transport}",
            root_key=shared_key,
        )
        message = harness.message(
            params={
                "name": TOOL,
                "arguments": arguments,
                "_mcppp_envelope": envelope,
            },
            profile_b=True,
        )
        response = harness.invoke(transport, message)
        assert "result" in response, response
        assert response["result"]["status"] == "success"
        assert len(harness.calls) == 1
        assert harness.calls[0][0] == "pin_tools"
        assert harness.calls[0][1] == "pin_add"
        assert harness.backend.adapter.effect_count == 1

        decision = _latest_decision(harness.dag)
        assert decision["decision"] == "allow"
        effect = next(
            event
            for event in harness.dag.history(limit=20)["events"]
            if event.get("event_type") == "authorization.effect"
        )
        assert effect["authorization_event_cid"] == decision["event_cid"]
        assert effect["parents"] == [decision["event_cid"]]

        normalized[transport] = semantic_result_cids(response)
        for cid_field in (
            "interface_cid",
            "input_cid",
            "intent_cid",
            "decision_cid",
            "output_cid",
            "receipt_cid",
            "event_cid",
        ):
            assert normalized[transport][cid_field]
        assert normalized[transport]["content_cid"].startswith("bafkrei")
        assert normalized[transport]["version"] == 1
        assert normalized[transport]["transaction_cid"].startswith("bafkrei")
        assert normalized[transport]["authorization_decision"] == "allow"

    baseline = normalized["stdio"]
    for transport in TRANSPORTS[1:]:
        assert normalized[transport] == baseline, (
            f"semantic result parity failed for {transport}: "
            f"{normalized[transport]} != {baseline}"
        )

    error_token = seed.issue(nonce="allow-shared-error-token")
    error_envelope = seed.envelope(
        arguments,
        error_token,
        request_id="allow-shared-error-request",
    )
    normalized_errors: dict[str, dict[str, Any]] = {}
    for transport in TRANSPORTS:
        harness = _Harness(
            tmp_path / "allow-error" / transport,
            nonce_seed=f"allow-error-{transport}",
            root_key=shared_key,
        )
        harness.backend.fail = True
        response = harness.invoke(
            transport,
            harness.message(
                params={
                    "name": TOOL,
                    "arguments": arguments,
                    "_mcppp_envelope": error_envelope,
                },
                profile_b=True,
            ),
        )
        assert response["result"]["status"] == "error"
        assert response["result"]["_authorization"]["decision"] == "allow"
        assert len(harness.calls) == 1
        assert harness.backend.adapter.effect_count == 0
        normalized_errors[transport] = semantic_result_cids(response)

    assert normalized_errors["http"] == normalized_errors["stdio"]
    assert normalized_errors["p2p"] == normalized_errors["stdio"]


# ---------------------------------------------------------------------------
# Signed-to-unsigned downgrade and confused deputy (explicit fail-closed)
# ---------------------------------------------------------------------------


def test_signed_to_unsigned_downgrade_fails_on_every_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_auth_clock(monkeypatch)
    codes: dict[str, str] = {}
    for transport in TRANSPORTS:
        harness = _Harness(tmp_path / "downgrade" / transport, nonce_seed=f"dg-{transport}")
        arguments = harness.arguments()
        signed = harness.issue(nonce=harness.next_nonce("signed"))
        unsigned = ".".join(signed.split(".")[:2])
        envelope = harness.envelope(arguments, unsigned, request_id="downgrade-1")
        response = harness.invoke(
            transport,
            harness.message(
                params={"name": TOOL, "arguments": arguments, "_mcppp_envelope": envelope}
            ),
        )
        assert harness.calls == []
        assert response["error"]["data"]["authorization"] == "denied"
        codes[transport] = response["error"]["data"]["reason"]
        assert codes[transport] in {
            "ucan_denied",
            "unsigned_or_malformed_token",
        } or codes[transport] == "ucan_denied"
    assert len(set(codes.values())) == 1


def test_confused_deputy_fails_on_every_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A UCAN issued for another audience cannot authorize the claiming actor."""

    _freeze_auth_clock(monkeypatch)
    for transport in TRANSPORTS:
        harness = _Harness(tmp_path / "deputy" / transport, nonce_seed=f"cd-{transport}")
        arguments = harness.arguments()
        token = harness.issue(audience=DEPUTY, nonce=harness.next_nonce("deputy"))
        # Envelope claims ACTOR while token audience is DEPUTY.
        envelope = harness.envelope(
            arguments, token, request_id="confused-deputy-1", actor=ACTOR
        )
        response = harness.invoke(
            transport,
            harness.message(
                params={"name": TOOL, "arguments": arguments, "_mcppp_envelope": envelope}
            ),
        )
        assert harness.calls == []
        assert response["error"]["data"]["authorization"] == "denied"
        assert response["error"]["data"]["reason"] == "ucan_denied"


# ---------------------------------------------------------------------------
# Restart preserves revocation and replay protection
# ---------------------------------------------------------------------------


def test_restart_preserves_revocation_and_replay_across_transports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_auth_clock(monkeypatch)
    root = tmp_path / "durable"
    harness = _Harness(root, nonce_seed="restart")

    replay_token = harness.issue(nonce="durable-replay-nonce")
    arguments = harness.arguments()
    envelope = harness.envelope(arguments, replay_token, request_id="replay-1")
    first = harness.invoke(
        "stdio",
        harness.message(
            params={"name": TOOL, "arguments": arguments, "_mcppp_envelope": envelope}
        ),
    )
    assert "result" in first and first["result"]["status"] == "success"

    # Process restart: new verifier over the same durable ledger path.
    restarted_ledger = RevocationLedger(harness.ledger.path)
    restarted_verifier = UCANVerifier(ledger=restarted_ledger, trusted_issuers={ISSUER})
    restarted_dag = EventDAGStore(storage_dir=str(root / "event-dag-restart"))
    restarted = MCPServer(
        event_dag=restarted_dag,
        policy_provider=get_profile_d_policy_provider(),
        ucan_ledger=restarted_ledger,
        ucan_verifier=restarted_verifier,
        envelope_validator=mcplusplus.validate_packet,
        validator_available=True,
    )
    restart_calls: list[Any] = []

    async def no_dispatch(category: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        restart_calls.append((category, tool, arguments))
        return {"status": "ok"}

    restarted.tm.dispatch = no_dispatch  # type: ignore[method-assign]

    for transport in TRANSPORTS:
        env = harness.envelope(
            arguments, replay_token, request_id=f"replay-again-{transport}"
        )
        response = _run(
            TRANSPORT_CALLERS[transport](
                restarted,
                {
                    "jsonrpc": "2.0",
                    "id": 40,
                    "method": "tools/call",
                    "params": {
                        "name": TOOL,
                        "arguments": arguments,
                        "_mcppp_envelope": env,
                    },
                },
            )
        )
        assert response["error"]["data"]["authorization"] == "denied"
        assert response["error"]["data"]["reason"] == "ucan_denied"
    assert restart_calls == []

    # Revocation survives restart independently of replay.
    revoked_token = issue_ucan(
        issuer=ISSUER,
        audience=ACTOR,
        capabilities=[{"resource": RESOURCE, "ability": TOOL}],
        private_key=harness.root_key,
        kid="root-v1",
        expires_at=time.time() + 300,
        nonce="durable-revocation-nonce",
        issued_at=time.time() - 10,
    )
    restarted_ledger.revoke(ucan_token_id(revoked_token), reason="operator revoke")
    for transport in TRANSPORTS:
        env = harness.envelope(
            arguments, revoked_token, request_id=f"revoked-{transport}"
        )
        response = _run(
            TRANSPORT_CALLERS[transport](
                restarted,
                {
                    "jsonrpc": "2.0",
                    "id": 41,
                    "method": "tools/call",
                    "params": {
                        "name": TOOL,
                        "arguments": arguments,
                        "_mcppp_envelope": env,
                    },
                },
            )
        )
        assert response["error"]["data"]["authorization"] == "denied"
        assert response["error"]["data"]["reason"] == "ucan_denied"
    assert restart_calls == []


# ---------------------------------------------------------------------------
# No MagicMock-only security evidence
# ---------------------------------------------------------------------------


def test_positive_security_evidence_uses_real_crypto_and_attenuation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Positive claims use real crypto; attenuation failures cross every wire."""

    _freeze_auth_clock(monkeypatch)

    # Positive security claims in this suite only come from real UCANVerifier.
    real = _Harness(tmp_path / "real", nonce_seed="real")
    assert isinstance(real.verifier, UCANVerifier)
    assert isinstance(real.ledger, RevocationLedger)
    token = real.issue(nonce=real.next_nonce("real-ok"))
    verified = real.verifier.verify(
        token,
        expected_resource=RESOURCE,
        expected_ability=TOOL,
        expected_audience=ACTOR,
    )
    assert verified.allowed is True
    receipt = verified.to_receipt()
    assert "signature" not in json.dumps(receipt)
    assert token not in json.dumps(receipt)

    # End-to-end allow through real crypto on all transports.
    for transport in TRANSPORTS:
        h = _Harness(tmp_path / "real-e2e" / transport, nonce_seed=f"re-{transport}")
        assert type(h.verifier) is UCANVerifier
        assert "MagicMock" not in type(h.verifier).__name__
        args = h.arguments()
        tok = h.issue(nonce=h.next_nonce("e2e"))
        env = h.envelope(args, tok, request_id=f"real-{transport}")
        response = h.invoke(
            transport,
            h.message(
                params={"name": TOOL, "arguments": args, "_mcppp_envelope": env},
                profile_b=True,
            ),
        )
        assert response["result"]["status"] == "success"
        assert len(h.calls) == 1

    shared_root = Ed25519PrivateKey.generate()
    service_key = Ed25519PrivateKey.generate()
    now = time.time()
    parent = issue_ucan(
        issuer=ISSUER,
        audience=SERVICE,
        capabilities=[
            {
                "resource": "ipfs://tenant-a/*",
                "ability": "pin_tools/*",
                "bounds": {"tenant": "tenant-a", "max_bytes": 1024},
            }
        ],
        private_key=shared_root,
        kid="root-v1",
        expires_at=now + 300,
        nonce="attenuation-parent",
        issued_at=now - 10,
    )
    leaf = issue_ucan(
        issuer=SERVICE,
        audience=ACTOR,
        capabilities=[
            {
                "resource": RESOURCE,
                "ability": TOOL,
                "bounds": {"tenant": "tenant-a", "max_bytes": 512},
            }
        ],
        private_key=service_key,
        kid="service-v1",
        expires_at=now + 240,
        nonce="attenuation-leaf",
        proofs=(ucan_token_id(parent),),
        issued_at=now - 5,
    )
    escalated = issue_ucan(
        issuer=SERVICE,
        audience=ACTOR,
        capabilities=[
            {
                "resource": "ipfs://tenant-b/pins/bafy-test",
                "ability": TOOL,
                "bounds": {"tenant": "tenant-b", "max_bytes": 2048},
            }
        ],
        private_key=service_key,
        kid="service-v1",
        expires_at=now + 240,
        nonce="attenuation-escalated",
        proofs=(ucan_token_id(parent),),
        issued_at=now - 5,
    )
    future = issue_ucan(
        issuer=ISSUER,
        audience=ACTOR,
        capabilities=[{"resource": RESOURCE, "ability": TOOL}],
        private_key=shared_root,
        kid="root-v1",
        expires_at=now + 300,
        not_before=now + 120,
        nonce="future-nbf",
        issued_at=now - 1,
    )
    bounded = issue_ucan(
        issuer=ISSUER,
        audience=ACTOR,
        capabilities=[
            {
                "resource": RESOURCE,
                "ability": TOOL,
                "bounds": {"tenant": "tenant-a", "max_bytes": 10},
            }
        ],
        private_key=shared_root,
        kid="root-v1",
        expires_at=now + 300,
        nonce="request-bounds",
        issued_at=now - 1,
    )

    denied_evidence: dict[str, dict[str, dict[str, str]]] = {}
    for transport in TRANSPORTS:
        allowed = _Harness(
            tmp_path / "attenuation" / "allowed" / transport,
            nonce_seed=f"attenuation-allowed-{transport}",
            root_key=shared_root,
        )
        allowed.ledger.register_public_key(
            SERVICE,
            "service-v1",
            public_key_bytes(service_key),
        )
        args = allowed.arguments()
        env = allowed.envelope(
            args,
            [parent, leaf],
            request_id="attenuation-valid",
        )
        env["request_bounds"] = {"tenant": "tenant-a", "max_bytes": 512}
        response = allowed.invoke(
            transport,
            allowed.message(
                params={
                    "name": TOOL,
                    "arguments": args,
                    "_mcppp_envelope": env,
                }
            ),
        )
        assert response["result"]["status"] == "success"
        assert len(allowed.calls) == 1

        denied_evidence[transport] = {}
        cases = (
            (
                "cross_tenant_escalation",
                [parent, escalated],
                "ipfs://tenant-b/pins/bafy-test",
                {"tenant": "tenant-b", "max_bytes": 2048},
            ),
            ("future_nbf", future, RESOURCE, {}),
            (
                "request_bounds",
                bounded,
                RESOURCE,
                {"tenant": "tenant-b", "max_bytes": 11},
            ),
        )
        for label, token, resource, request_bounds in cases:
            denied = _Harness(
                tmp_path / "attenuation" / label / transport,
                nonce_seed=f"{label}-{transport}",
                root_key=shared_root,
            )
            denied.ledger.register_public_key(
                SERVICE,
                "service-v1",
                public_key_bytes(service_key),
            )
            policy = {
                "policy_id": f"{label}-allow-policy",
                "version": "v1",
                "clauses": [
                    {
                        "clause_type": "permission",
                        "actor": "*",
                        "action": TOOL,
                        "resource": resource,
                    }
                ],
            }
            case_args = {
                "resource": resource,
                "cid": "bafy-test",
                "policy": policy,
            }
            case_env = denied.envelope(
                case_args,
                token,
                request_id=f"{label}-shared",
                resource=resource,
                policy=policy,
            )
            case_env["request_bounds"] = request_bounds
            rejected = denied.invoke(
                transport,
                denied.message(
                    params={
                        "name": TOOL,
                        "arguments": case_args,
                        "_mcppp_envelope": case_env,
                    }
                ),
            )
            assert rejected["error"]["data"]["authorization"] == "denied"
            assert rejected["error"]["data"]["reason"] == "ucan_denied"
            assert denied.calls == []
            decision = _latest_decision(denied.dag)
            assert decision["semantic_decision_cid"] == semantic_decision_cid(
                decision
            )
            denied_evidence[transport][label] = {
                "reason": rejected["error"]["data"]["reason"],
                "event_cid": decision["event_cid"],
                "semantic_decision_cid": decision["semantic_decision_cid"],
            }

    assert denied_evidence["http"] == denied_evidence["stdio"]
    assert denied_evidence["p2p"] == denied_evidence["stdio"]


def test_transport_callers_cover_stdio_http_and_p2p_framing(tmp_path: Path) -> None:
    assert set(TRANSPORT_CALLERS) == {"stdio", "http", "p2p"}
    assert PROTOCOL_ID == "/mcp+p2p/1.0.0"

    # The default server must select the always-available production validator,
    # and a malformed envelope must fail before any backend is considered.
    server = MCPServer(
        event_dag=EventDAGStore(storage_dir=str(tmp_path / "default-validator-dag"))
    )
    assert server.authorization_gate.validator_available is True
    assert server.authorization_gate.envelope_validator is mcplusplus.validate_packet
    arguments = {
        "resource": RESOURCE,
        "cid": "bafy-test",
        "policy": ALLOW_POLICY,
    }
    malformed = {
        "tool": TOOL,
        "resource": RESOURCE,
        "ability": TOOL,
        # actor deliberately absent
        "ucan": "signed.token.placeholder",
        "policy_root": policy_root(ALLOW_POLICY),
        "request_id": "malformed-default",
        "transaction_id": "malformed-default",
    }
    response = _run(
        call_stdio(
            server,
            {
                "jsonrpc": "2.0",
                "id": 99,
                "method": "tools/call",
                "params": {
                    "name": TOOL,
                    "arguments": arguments,
                    "_mcppp_envelope": malformed,
                },
            },
        )
    )
    assert response["error"]["data"] == {
        "authorization": "denied",
        "reason": "invalid_envelope",
    }
