"""End-to-end interop tests for the ipfs_kit_py MCP++ server.

Proves the four surfaces share one registry & contract: Python imports, CLI,
MCP JSON-RPC (stdio + HTTP ASGI), and the generated JS SDK.

These tests are hermetic: they inject the deterministic ``_StubKit`` backend,
use real Ed25519 UCANs + Profile D policy for authorized ``tools/call`` paths,
and isolate durable EventDAG / revocation state under pytest's ``tmp_path``.
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

import anyio
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

PKG = Path(__file__).resolve().parents[2]  # ipfs_kit_py/ root
sys.path.insert(0, str(PKG))

from ipfs_kit_py.mcp.profile_d_policy import get_profile_d_policy_provider, policy_root  # noqa: E402
from ipfs_kit_py.mcp_server import HierarchicalToolManager  # noqa: E402
from ipfs_kit_py.mcp_server import core_operations  # noqa: E402
from ipfs_kit_py.mcp_server.js_sdk import generate  # noqa: E402
from ipfs_kit_py.mcp_server.mcplusplus.event_dag import EventDAGStore  # noqa: E402
from ipfs_kit_py.mcp_server.mcplusplus.revocation import RevocationLedger  # noqa: E402
from ipfs_kit_py.mcp_server.mcplusplus.ucan import (  # noqa: E402
    UCANVerifier,
    issue_ucan,
    public_key_bytes,
)
from ipfs_kit_py.mcp_server.server import MCPServer, create_http_app  # noqa: E402
from ipfs_kit_py.mcp_server.tools import ipfs_tools  # noqa: E402

ISSUER = "did:key:e2e-interop-root"
ACTOR = "did:client:e2e-interop"
RESOURCE = "ipfs://tenant-e2e/pins/bafy"
ALLOW_POLICY: dict[str, Any] = {
    "policy_id": "e2e-allow",
    "version": "v1",
    "clauses": [
        {
            "clause_type": "permission",
            "actor": "*",
            "action": "*",
            "resource": "ipfs://tenant-e2e/*",
        }
    ],
}


@pytest.fixture(autouse=True)
def _hermetic_stub_kit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use the deterministic stub backend so interop does not need a live daemon."""

    monkeypatch.setattr(core_operations, "_kit", core_operations._StubKit())


def _authorized_server(tmp_path: Path) -> tuple[MCPServer, Ed25519PrivateKey]:
    root_key = Ed25519PrivateKey.generate()
    ledger = RevocationLedger(tmp_path / "ucan-revocation-ledger.json")
    ledger.register_public_key(ISSUER, "root-v1", public_key_bytes(root_key))
    verifier = UCANVerifier(ledger=ledger, trusted_issuers={ISSUER})
    dag = EventDAGStore(storage_dir=str(tmp_path / "event-dag"))
    server = MCPServer(
        event_dag=dag,
        policy_provider=get_profile_d_policy_provider(),
        ucan_ledger=ledger,
        ucan_verifier=verifier,
        envelope_validator=lambda _envelope: None,
        validator_available=True,
    )
    return server, root_key


def _issue(
    root_key: Ed25519PrivateKey,
    *,
    ability: str,
    resource: str = RESOURCE,
    audience: str = ACTOR,
    nonce: str | None = None,
) -> str:
    now = time.time()
    return issue_ucan(
        issuer=ISSUER,
        audience=audience,
        capabilities=[{"resource": resource, "ability": ability}],
        private_key=root_key,
        kid="root-v1",
        expires_at=now + 300,
        nonce=nonce or f"e2e-{uuid.uuid4().hex}",
        issued_at=now - 10,
    )


def _envelope(
    *,
    tool: str,
    token: str,
    arguments: Mapping[str, Any],
    request_id: str,
    resource: str = RESOURCE,
    actor: str = ACTOR,
) -> dict[str, Any]:
    return {
        "tool": tool,
        "resource": resource,
        "ability": tool,
        "actor": actor,
        "ucan": token,
        "policy_root": policy_root(arguments.get("policy"), arguments.get("policy_text")),
        "request_id": request_id,
        "transaction_id": request_id,
    }


def _auth_params(
    root_key: Ed25519PrivateKey,
    *,
    name: str,
    cid: str = "bafy",
    request_id: str = "e2e-1",
    profile_b: bool = False,
) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "resource": RESOURCE,
        "cid": cid,
        "policy": dict(ALLOW_POLICY),
    }
    token = _issue(root_key, ability=name)
    params: dict[str, Any] = {
        "name": name,
        "arguments": arguments,
        "_mcppp_envelope": _envelope(
            tool=name, token=token, arguments=arguments, request_id=request_id
        ),
    }
    if profile_b:
        params["profile_b"] = True
    return params


def test_python_import_surface():
    r = anyio.run(ipfs_tools.ipfs_add, "x")
    assert r["status"] == "success"
    assert "request_id" in r


def test_dispatch_and_schema_parity():
    tm = HierarchicalToolManager()
    schemas = tm.all_tool_schemas()
    assert {s["name"] for s in schemas} >= {"ipfs_add", "pin_add", "dag_put", "cluster_status"}
    r = anyio.run(tm.dispatch, "dag_tools", "dag_put", {"data": {"a": 1}})
    assert r["status"] == "success"


def test_mcp_jsonrpc_tools_list_and_call(tmp_path: Path):
    s, key = _authorized_server(tmp_path)
    lst = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert len(lst["result"]["tools"]) == len(s.tm.all_tool_schemas()) + 1
    init = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 2, "method": "initialize"})
    assert init["result"]["serverInfo"]["name"] == "ipfs_kit_py-mcpplusplus"
    call = anyio.run(
        s.handle,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": _auth_params(key, name="ipfs_tools/ipfs_cat", request_id="e2e-cat"),
        },
    )
    assert call["result"]["status"] == "success"


def test_cli_surface_matches(capsys: pytest.CaptureFixture[str]):
    """CLI shares HierarchicalToolManager dispatch with the other surfaces.

    Invoked in-process so the hermetic ``_StubKit`` fixture applies (a
    subprocess would rebuild a real kit without the daemon/method bridges).
    """
    from ipfs_kit_py.mcp_server.cli import main

    rc = main(["pin_tools", "pin_add", "--cid", "bafy"])
    captured = capsys.readouterr()
    assert rc == 0, captured.err or captured.out
    assert json.loads(captured.out)["status"] == "success"


def test_js_sdk_mirrors_python_tools():
    src = generate.render()
    py = {s["name"] for s in HierarchicalToolManager().all_tool_schemas()}
    for name in py:
        assert f'"{name}"' in src
    assert "IpfsKitMcpClient" in src


def test_http_transport_asgi(tmp_path: Path):
    """HTTP framing uses the shared ASGI app (Hypercorn is optional at runtime)."""

    s, key = _authorized_server(tmp_path)
    app = create_http_app(s)
    message = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
    }
    body = json.dumps(message).encode("utf-8")
    sent: list[dict[str, Any]] = []
    received = False

    async def receive() -> dict[str, Any]:
        nonlocal received
        if received:
            return {"type": "http.disconnect"}
        received = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(part: dict[str, Any]) -> None:
        sent.append(part)

    async def run() -> None:
        await app(
            {
                "type": "http",
                "method": "POST",
                "path": "/mcp",
                "query_string": b"",
                "headers": [],
            },
            receive,
            send,
        )

    anyio.run(run)
    assert sent[0]["status"] in {200, 202}
    payload = json.loads(sent[1]["body"])
    assert len(payload["result"]["tools"]) == len(HierarchicalToolManager().all_tool_schemas()) + 1


def test_mfs_and_swarm_groups():
    tm = HierarchicalToolManager()
    cats = {c["name"] for c in tm.list_categories()}
    assert {"mfs_tools", "swarm_tools"} <= cats
    assert anyio.run(tm.dispatch, "mfs_tools", "files_ls", {"path": "/"})["status"] == "success"
    assert anyio.run(tm.dispatch, "swarm_tools", "node_id", {})["status"] == "success"


def test_mcppp_envelope_accepted(tmp_path: Path):
    s, key = _authorized_server(tmp_path)
    call = anyio.run(
        s.handle,
        {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": _auth_params(key, name="pin_tools/pin_rm", request_id="e2e-env"),
        },
    )
    assert call["result"]["status"] == "success"


def test_name_car_pinset_groups():
    tm = HierarchicalToolManager()
    cats = {c["name"] for c in tm.list_categories()}
    assert {"name_tools", "car_tools"} <= cats
    assert (
        anyio.run(tm.dispatch, "name_tools", "name_publish", {"path": "/ipfs/bafy"})["status"]
        == "success"
    )
    assert anyio.run(tm.dispatch, "car_tools", "create_car", {"roots": ["bafy"]})["status"] == "success"
    assert anyio.run(tm.dispatch, "pin_tools", "get_pinset", {})["status"] == "success"


def test_generated_artifacts_not_stale():
    """The committed JS SDK + manifest must equal a fresh regeneration."""
    assert generate.SDK_PATH.read_text() == generate.render(), "JS SDK stale: run generate"
    assert generate.MANIFEST_PATH.read_text() == generate.render_manifest(), "manifest stale: run generate"
    assert generate.TS_SDK_PATH.read_text() == generate.render_ts(), "TS SDK stale: run generate"


def test_ts_sdk_typed_tool_names():
    """TS SDK exposes a typed ToolName union derived from the same registry."""
    src = generate.TS_SDK_PATH.read_text()
    assert "export type ToolName = keyof typeof TOOLS" in src
    assert "pin_rm" in src and "ipfs_add" in src


def test_swissknife_manifest_in_sync():
    """Dashboard manifest must match the server's generated manifest."""
    dash = PKG.parents[2] / "swissknife" / "src" / "services" / "mcp-ipfs-kit-tools-manifest.json"
    if dash.exists():
        assert dash.read_text() == generate.render_manifest(), "swissknife manifest stale: resync"


def test_profile_b_receipt_emitted(tmp_path: Path):
    """tools/call with profile_b returns canonical CID receipt (B)."""
    s, key = _authorized_server(tmp_path)
    call = anyio.run(
        s.handle,
        {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": _auth_params(
                key, name="pin_tools/pin_rm", request_id="e2e-b", profile_b=True
            ),
        },
    )
    meta = call["result"]["_mcppp"]
    for k in ("input_cid", "intent_cid", "decision_cid", "output_cid", "receipt_cid", "success"):
        assert k in meta
    assert meta["receipt_cid"].startswith("bafkrei") and meta["success"] is True


def test_cid_algorithm_is_kubo_cidv1_base32():
    """Kit's artifact CID is a Kubo-conformant CIDv1 (raw/sha256/base32)."""
    from ipfs_kit_py.mcp_server.mcplusplus import artifacts as kit_art

    cid = kit_art.compute_artifact_cid({"b": 2, "a": 1, "tool": "pin_rm"})
    assert cid.startswith("bafkrei") and len(cid) == 59
    try:
        from multiformats import CID, multihash
    except Exception:
        pytest.skip("multiformats not installed")
    body = kit_art.canonicalize_artifact({"b": 2, "a": 1, "tool": "pin_rm"})
    mh = multihash.digest(body, "sha2-256")
    assert cid == str(CID("base32", 1, "raw", mh))


def test_profile_a_interfaces():
    """Profile A: mcp++/interfaces yields descriptors for every tool."""
    s = MCPServer()
    res = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 12, "method": "mcp++/interfaces"})
    ifaces = res["result"]["interfaces"]
    assert len(ifaces) == len(s.tm.all_tool_schemas()) + 1
    d = ifaces[0]
    for k in (
        "namespace",
        "name",
        "input_schema",
        "output_schema",
        "errors",
        "semantic_tags",
        "compatibility",
    ):
        assert k in d
    assert d["namespace"].startswith("ipfs_kit/")


def test_profile_e_dag_chains_events(tmp_path: Path):
    """Profile E: profile_b calls append linked DAG events; frontier is latest."""
    s, key = _authorized_server(tmp_path)
    for i in range(2):
        anyio.run(
            s.handle,
            {
                "jsonrpc": "2.0",
                "id": 100 + i,
                "method": "tools/call",
                "params": _auth_params(
                    key,
                    name="pin_tools/pin_rm",
                    request_id=f"e2e-e-{i}",
                    profile_b=True,
                ),
            },
        )
    fr = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 200, "method": "mcp++/dag/frontier"})[
        "result"
    ]
    # authorization.decision + authorization.effect + profile_b event per call
    assert fr["count"] >= 2 and len(fr["frontier"]) >= 1
    history = s._dag.history(limit=50)["events"]
    # At least two profile-b / effect-linked records exist after two authorized calls.
    assert len(history) >= 2


def test_profile_c_ucan_validate(tmp_path: Path):
    """Profile C: signed UCAN grants expected ability; escalation denied."""
    s, key = _authorized_server(tmp_path)
    token = _issue(key, ability="read", resource="ipfs")
    ok = anyio.run(
        s.handle,
        {
            "jsonrpc": "2.0",
            "id": 30,
            "method": "mcp++/ucan/validate",
            "params": {
                "chain": token,
                "resource": "ipfs",
                "ability": "read",
                "actor": ACTOR,
            },
        },
    )
    assert ok["result"]["allowed"] is True
    bad = anyio.run(
        s.handle,
        {
            "jsonrpc": "2.0",
            "id": 31,
            "method": "mcp++/ucan/validate",
            "params": {
                "chain": token,
                "resource": "ipfs",
                "ability": "write",
                "actor": ACTOR,
            },
        },
    )
    assert bad["result"]["allowed"] is False


def test_profile_d_policy_evaluate(tmp_path: Path):
    s, _key = _authorized_server(tmp_path)
    allow_policy = {
        "policy_id": "e2e-d-allow",
        "version": "v1",
        "clauses": [
            {
                "clause_type": "permission",
                "actor": "*",
                "action": "ipfs_add",
                "resource": "*",
            }
        ],
    }
    deny_policy = {
        "policy_id": "e2e-d-deny",
        "version": "v1",
        "clauses": [
            {
                "clause_type": "prohibition",
                "actor": "*",
                "action": "ipfs_add",
                "resource": "*",
            }
        ],
    }
    allow = anyio.run(
        s.handle,
        {
            "jsonrpc": "2.0",
            "id": 32,
            "method": "mcp++/policy/evaluate",
            "params": {
                "tool": "ipfs_add",
                "actor": "anonymous",
                "resource": "ipfs://x",
                "policy": allow_policy,
            },
        },
    )["result"]
    deny = anyio.run(
        s.handle,
        {
            "jsonrpc": "2.0",
            "id": 33,
            "method": "mcp++/policy/evaluate",
            "params": {
                "tool": "ipfs_add",
                "actor": "anonymous",
                "resource": "ipfs://x",
                "policy": deny_policy,
            },
        },
    )["result"]
    assert allow["decision"] == "allow" and deny["decision"] == "deny"


def test_all_five_profiles_smoke(tmp_path: Path):
    """One server exercises A,B,C,D,E + base MCP in a single flow."""
    s, key = _authorized_server(tmp_path)
    init = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    profs = init["result"]["capabilities"]["experimental"]["mcp++"]["profiles"]
    assert all(
        profs.get(k)
        for k in (
            "A_interface_descriptors",
            "B_cid_envelopes",
            "C_ucan_unsigned",
            "D_policy",
            "E_dag_events",
        )
    )
    assert anyio.run(s.handle, {"jsonrpc": "2.0", "id": 2, "method": "mcp++/interfaces"})[
        "result"
    ]["interfaces"]
    pol = anyio.run(
        s.handle,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "mcp++/policy/evaluate",
            "params": {
                "tool": "ipfs_add",
                "actor": "anonymous",
                "resource": "ipfs://x",
                "policy": {
                    "policy_id": "smoke-allow",
                    "version": "v1",
                    "clauses": [
                        {
                            "clause_type": "permission",
                            "actor": "*",
                            "action": "ipfs_add",
                            "resource": "*",
                        }
                    ],
                },
            },
        },
    )
    assert pol["result"]["decision"] == "allow"
    token = _issue(key, ability="read", resource="ipfs")
    assert anyio.run(
        s.handle,
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "mcp++/ucan/validate",
            "params": {
                "chain": token,
                "resource": "ipfs",
                "ability": "read",
                "actor": ACTOR,
            },
        },
    )["result"]["allowed"]
    call = anyio.run(
        s.handle,
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": _auth_params(
                key, name="pin_tools/pin_rm", request_id="e2e-smoke", profile_b=True
            ),
        },
    )
    assert call["result"]["_mcppp"]["receipt_cid"].startswith("bafkrei")
    assert (
        anyio.run(s.handle, {"jsonrpc": "2.0", "id": 6, "method": "mcp++/dag/frontier"})[
            "result"
        ]["count"]
        >= 1
    )


def test_p2p_transport_roundtrip(tmp_path: Path):
    """A tools/call routed through libp2p framing returns the same result as stdio."""
    from ipfs_kit_py.mcp_server.p2p_transport import PROTOCOL_ID, handle_stream_message

    assert PROTOCOL_ID == "/mcp+p2p/1.0.0"
    s, key = _authorized_server(tmp_path)
    params = _auth_params(key, name="pin_tools/get_pinset", request_id="e2e-p2p")
    # get_pinset uses empty args but still needs resource binding for the gate.
    params["arguments"]["resource"] = RESOURCE
    req = json.dumps(
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": params}
    ).encode()
    resp = json.loads(anyio.run(handle_stream_message, req, s.handle))
    assert resp["result"]["status"] == "success"


def test_fastmcp_registrar_covers_full_registry():
    """Backwards-compat: FastMCP registration exposes the full registry, one
    registry, callable through the same dispatch codepath."""
    from ipfs_kit_py.mcp_server.fastmcp_app import register_fastmcp

    class _FakeApp:
        def __init__(self):
            self.tools = {}

        def add_tool(self, fn, name=None, description=""):
            self.tools[name] = fn

    app = _FakeApp()
    names = register_fastmcp(app)
    expected = {s["name"] for s in HierarchicalToolManager().all_tool_schemas()}
    assert set(names) == expected == set(app.tools)
    assert len(names) == len(expected)
    r = anyio.run(app.tools["pin_rm"], {"cid": "bafy"})
    assert r["status"] == "success"


def test_initialize_handshake():
    """Standard MCP clients call initialize first; server returns protocol +
    capabilities (backwards-compat handshake)."""
    s = MCPServer()
    r = anyio.run(
        s.handle,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18"},
        },
    )
    assert r["result"]["protocolVersion"]
    assert "tools" in r["result"]["capabilities"]


def test_notifications_get_no_reply():
    """JSON-RPC notifications (no id) — e.g. notifications/initialized — must be
    accepted silently with no response, per spec."""
    s = MCPServer()
    assert anyio.run(s.handle, {"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    # An id-bearing unknown notifications/* is still a no-op result, not error
    r = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 2, "method": "notifications/cancelled"})
    assert "error" not in r
