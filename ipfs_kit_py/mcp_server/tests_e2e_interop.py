"""End-to-end interop tests for the ipfs_kit_py MCP++ server.

Proves the four surfaces share one registry & contract: Python imports, CLI,
MCP JSON-RPC (stdio + HTTP/Hypercorn), and the generated JS SDK.
"""
import hashlib
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import anyio
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

PKG = Path(__file__).resolve().parents[2]  # ipfs_kit_py/ root
sys.path.insert(0, str(PKG))

from ipfs_kit_py.backends.ipfs_backend import HermeticIPFSFixtureAdapter  # noqa: E402
from ipfs_kit_py.mcp.profile_d_policy import (  # noqa: E402
    get_profile_d_policy_provider,
    policy_root,
)
from ipfs_kit_py.mcp_server import (  # noqa: E402
    HierarchicalToolManager,
    cli,
    core_operations,
    mcplusplus,
)
from ipfs_kit_py.mcp_server.js_sdk import generate  # noqa: E402
from ipfs_kit_py.mcp_server.mcplusplus.event_dag import EventDAGStore  # noqa: E402
from ipfs_kit_py.mcp_server.mcplusplus.revocation import RevocationLedger  # noqa: E402
from ipfs_kit_py.mcp_server.mcplusplus.ucan import (  # noqa: E402
    UCANVerifier,
    issue_ucan,
    public_key_bytes,
)
from ipfs_kit_py.mcp_server.server import MCPServer  # noqa: E402
from ipfs_kit_py.mcp_server.tools import ipfs_tools  # noqa: E402


ACTOR = "did:client:e2e"
ISSUER = "did:key:e2e-root"
RESOURCE = "ipfs://e2e/fixture"


def _policy(tool: str, clause_type: str = "permission") -> dict:
    return {
        "policy_id": f"e2e-{clause_type}-{tool.replace('/', '-')}",
        "version": "v1",
        "clauses": [
            {
                "clause_type": clause_type,
                "actor": ACTOR,
                "action": tool,
                "resource": RESOURCE,
            }
        ],
    }


class _HermeticCoreBackend:
    """Legacy MCP facade backed by the certified hermetic IPFS fixture.

    This is an explicit test binding, never an automatic production fallback.
    Every successful mutating operation records a real fixture-adapter effect.
    """

    def __init__(self, root: Path) -> None:
        self.adapter = HermeticIPFSFixtureAdapter(root)
        self.pins: set[str] = set()
        self.content_paths: dict[str, str] = {}

    @staticmethod
    def _path(namespace: str, identity: str) -> str:
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return f"{namespace}/{digest}"

    async def ipfs_add(self, file_path: str, recursive: bool = False) -> dict:
        del recursive
        source = Path(file_path)
        data = source.read_bytes()
        result = await self.adapter.put(
            self._path("content", str(source.resolve())),
            data,
            idempotency_key=f"add:{source.resolve()}:{hashlib.sha256(data).hexdigest()}",
        )
        self.content_paths[result.resulting_content_cid] = self._path(
            "content", str(source.resolve())
        )
        return {
            "success": True,
            "cid": result.resulting_content_cid,
            "size": len(data),
            "backend_id": self.adapter.backend_id,
        }

    async def ipfs_cat(self, cid: str) -> dict:
        result = await self.adapter.get(self.content_paths[cid])
        return {"success": True, "cid": cid, "content": result.data}

    async def ipfs_dag_put(self, data: dict) -> dict:
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        result = await self.adapter.put(
            self._path("dag", encoded.decode()),
            encoded,
            idempotency_key=f"dag:{hashlib.sha256(encoded).hexdigest()}",
        )
        self.content_paths[result.resulting_content_cid] = self._path(
            "dag", encoded.decode()
        )
        return {"success": True, "cid": result.resulting_content_cid}

    async def ipfs_pin_add(self, cid: str, recursive: bool = True) -> dict:
        result = await self.adapter.put(
            self._path("pins", cid),
            cid.encode(),
            metadata={"recursive": bool(recursive)},
            idempotency_key=f"pin:{cid}:{bool(recursive)}",
        )
        self.pins.add(cid)
        return {
            "success": True,
            "pinned": cid,
            "content_cid": result.resulting_content_cid,
        }

    async def ipfs_pin_rm(self, cid: str, recursive: bool = True) -> dict:
        del recursive
        if cid not in self.pins:
            return {
                "success": False,
                "error": "pin does not exist",
                "error_type": "not_found",
            }
        await self.adapter.delete(self._path("pins", cid))
        self.pins.remove(cid)
        return {"success": True, "unpinned": cid}

    async def ipfs_pin_ls(self) -> dict:
        return {"success": True, "pins": {cid: {"type": "recursive"} for cid in sorted(self.pins)}}

    async def ipfs_get_pinset(self) -> dict:
        return {"success": True, "pinset": sorted(self.pins)}

    async def files_ls(self, path: str = "/", long: bool = False) -> dict:
        del long
        result = await self.adapter.list("" if path == "/" else path.lstrip("/"))
        return {"success": True, "entries": list(result.items)}

    async def ipfs_id(self) -> dict:
        return {"success": True, "id": self.adapter.backend_id}

    async def name_publish(self, path: str) -> dict:
        result = await self.adapter.put(
            "ipns/current",
            path.encode(),
            idempotency_key=f"ipns:{path}",
        )
        return {
            "success": True,
            "name": "k51-hermetic-e2e",
            "value": path,
            "content_cid": result.resulting_content_cid,
        }

    async def create_car(self, roots: list[str], blocks=None) -> dict:
        encoded = json.dumps(
            {"roots": roots, "blocks": blocks or []},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        result = await self.adapter.put(
            self._path("car", encoded.decode()),
            encoded,
            idempotency_key=f"car:{hashlib.sha256(encoded).hexdigest()}",
        )
        return {"success": True, "cid": result.resulting_content_cid, "roots": roots}


@pytest.fixture
def hermetic_core_backend(tmp_path):
    backend = _HermeticCoreBackend(tmp_path / "core-backend")
    with core_operations.use_core_backend(backend):
        yield backend


class _AuthorizedServer:
    def __init__(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        self.key = Ed25519PrivateKey.generate()
        self.ledger = RevocationLedger(root / "ucan-ledger.json")
        self.ledger.register_public_key(
            ISSUER,
            "root-v1",
            public_key_bytes(self.key),
        )
        self.verifier = UCANVerifier(
            ledger=self.ledger,
            trusted_issuers={ISSUER},
        )
        self.dag = EventDAGStore(storage_dir=str(root / "event-dag"))
        self.server = MCPServer(
            event_dag=self.dag,
            policy_provider=get_profile_d_policy_provider(),
            ucan_ledger=self.ledger,
            ucan_verifier=self.verifier,
            envelope_validator=mcplusplus.validate_packet,
            validator_available=True,
        )
        self._nonce = 0

    def token(
        self,
        tool: str,
        *,
        resource: str = RESOURCE,
        audience: str = ACTOR,
    ) -> str:
        self._nonce += 1
        now = time.time()
        return issue_ucan(
            issuer=ISSUER,
            audience=audience,
            capabilities=[{"resource": resource, "ability": tool}],
            private_key=self.key,
            kid="root-v1",
            expires_at=now + 300,
            issued_at=now - 1,
            nonce=f"e2e-{self._nonce}",
        )

    def call_params(
        self,
        tool: str,
        arguments: dict,
        *,
        profile_b: bool = False,
    ) -> dict:
        allow_policy = _policy(tool)
        bound_arguments = {
            **arguments,
            "resource": RESOURCE,
            "policy": allow_policy,
        }
        request_id = f"e2e-request-{self._nonce + 1}"
        envelope = {
            "tool": tool,
            "resource": RESOURCE,
            "ability": tool,
            "actor": ACTOR,
            "ucan": self.token(tool),
            "policy_root": policy_root(allow_policy),
            "request_id": request_id,
            "transaction_id": request_id,
        }
        return {
            "name": tool,
            "arguments": bound_arguments,
            "_mcppp_envelope": envelope,
            **({"profile_b": True} if profile_b else {}),
        }

    def call(self, tool: str, arguments: dict, *, profile_b: bool = False, request_id: int = 1):
        return anyio.run(
            self.server.handle,
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": self.call_params(tool, arguments, profile_b=profile_b),
            },
        )


def _server(tmp_path: Path, label: str) -> _AuthorizedServer:
    return _AuthorizedServer(tmp_path / label)


def test_python_import_surface(tmp_path, hermetic_core_backend):
    source = tmp_path / "payload.txt"
    source.write_text("canonical hermetic payload")
    r = anyio.run(ipfs_tools.ipfs_add, str(source))
    assert r["status"] == "success"
    assert r["_dispatch"]["request_id"]


def test_dispatch_and_schema_parity(hermetic_core_backend):
    tm = HierarchicalToolManager()
    schemas = tm.all_tool_schemas()
    assert {s["name"] for s in schemas} >= {"ipfs_add", "pin_add", "dag_put", "cluster_status"}
    r = anyio.run(tm.dispatch, "dag_tools", "dag_put", {"data": {"a": 1}})
    assert r["status"] == "success"


def test_mcp_jsonrpc_tools_list_and_call(tmp_path, hermetic_core_backend):
    harness = _server(tmp_path, "jsonrpc")
    lst = anyio.run(harness.server.handle, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert len(lst["result"]["tools"]) == len(harness.server.tm.all_tool_schemas()) + 1
    init = anyio.run(harness.server.handle, {"jsonrpc": "2.0", "id": 2, "method": "initialize"})
    assert init["result"]["serverInfo"]["name"] == "ipfs_kit_py-mcpplusplus"
    call = harness.call("pin_tools/pin_add", {"cid": "bafy"}, request_id=3)
    assert call["result"]["status"] == "success"
    assert call["result"]["_authorization"]["decision"] == "allow"


def test_cli_surface_matches(tmp_path, capsys, hermetic_core_backend):
    harness = _server(tmp_path, "cli")

    assert (
        cli.main(
            ["pin_tools", "pin_add", "--cid", "bafy"],
            server=harness.server,
        )
        == 1
    )
    denied = json.loads(capsys.readouterr().out)
    assert denied["error"]["data"]["authorization"] == "denied"

    params = harness.call_params("pin_tools/pin_add", {"cid": "bafy"})
    arguments = params["arguments"]
    assert (
        cli.main(
            [
                "pin_tools",
                "pin_add",
                "--cid",
                "bafy",
                "--resource",
                RESOURCE,
                "--policy",
                json.dumps(arguments["policy"]),
                "--mcppp-envelope",
                json.dumps(params["_mcppp_envelope"]),
            ],
            server=harness.server,
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "success"


def test_js_sdk_mirrors_python_tools():
    src = generate.render()
    py = {s["name"] for s in HierarchicalToolManager().all_tool_schemas()}
    for name in py:
        assert f'"{name}"' in src
    assert "IpfsKitMcpClient" in src
    assert "_mcppp_envelope" in src
    assert "signed MCP++ authorization envelope required" in src


def test_http_transport_hypercorn():
    """Exercise the advertised Hypercorn transport on an ephemeral loopback port."""

    assert "hypercorn>=0.16.0" in (PKG / "requirements.txt").read_text()
    assert '"hypercorn>=0.16.0"' in (PKG / "pyproject.toml").read_text()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "ipfs_kit_py.mcp_server.server",
            "--transport",
            "http",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(PKG),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        import urllib.request

        for _ in range(20):
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}",
                    data=b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}',
                    headers={"content-type": "application/json"},
                )
                payload = json.loads(urllib.request.urlopen(req, timeout=2).read())
                assert len(payload["result"]["tools"]) == (
                    len(HierarchicalToolManager().all_tool_schemas()) + 1
                )
                break
            except Exception:
                time.sleep(0.5)
        else:
            pytest.fail("Hypercorn HTTP transport never became ready")
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_mfs_and_swarm_groups(hermetic_core_backend):
    tm = HierarchicalToolManager()
    cats = {c["name"] for c in tm.list_categories()}
    assert {"mfs_tools", "swarm_tools"} <= cats
    assert anyio.run(tm.dispatch, "mfs_tools", "files_ls", {"path": "/"})["status"] == "success"
    assert anyio.run(tm.dispatch, "swarm_tools", "node_id", {})["status"] == "success"


def test_mcppp_envelope_accepted(tmp_path, hermetic_core_backend):
    harness = _server(tmp_path, "envelope")
    call = harness.call("pin_tools/pin_add", {"cid": "bafy"}, request_id=9)
    assert call["result"]["status"] == "success"
    assert call["result"]["_authorization"]["ability"] == "pin_tools/pin_add"


def test_name_car_pinset_groups(hermetic_core_backend):
    tm = HierarchicalToolManager()
    cats = {c["name"] for c in tm.list_categories()}
    assert {"name_tools", "car_tools"} <= cats
    assert anyio.run(tm.dispatch, "name_tools", "name_publish", {"path": "/ipfs/bafy"})["status"] == "success"
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
    assert "McpPlusPlusAuthorizationEnvelope" in src
    assert "_mcppp_envelope" in src


def test_swissknife_manifest_in_sync():
    """Dashboard manifest must match the server's generated manifest."""
    dash = PKG.parents[2] / "swissknife" / "src" / "services" / "mcp-ipfs-kit-tools-manifest.json"
    if dash.exists():
        assert dash.read_text() == generate.render_manifest(), "swissknife manifest stale: resync"


def test_profile_b_receipt_emitted(tmp_path, hermetic_core_backend):
    """tools/call with profile_b returns canonical CID receipt (B)."""
    harness = _server(tmp_path, "profile-b")
    call = harness.call(
        "pin_tools/pin_add",
        {"cid": "bafy"},
        profile_b=True,
        request_id=11,
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
    for k in ("namespace", "name", "input_schema", "output_schema", "errors", "semantic_tags", "compatibility"):
        assert k in d
    assert d["namespace"].startswith("ipfs_kit/")


def test_profile_e_dag_chains_events(tmp_path, hermetic_core_backend):
    """Profile E records an isolated authorization -> result/effect causal DAG."""
    harness = _server(tmp_path, "profile-e")
    calls = []
    for i in range(2):
        calls.append(
            harness.call(
                "pin_tools/pin_add",
                {"cid": f"bafy-{i}"},
                profile_b=True,
                request_id=100 + i,
            )
        )
    fr = anyio.run(
        harness.server.handle,
        {"jsonrpc": "2.0", "id": 200, "method": "mcp++/dag/frontier"},
    )["result"]
    events = harness.dag.history(limit=20)["events"]
    decisions = {
        event["request_id"]: event
        for event in events
        if event.get("event_type") == "authorization.decision"
        and event.get("decision") == "allow"
    }
    effects = [
        event
        for event in events
        if event.get("event_type") == "authorization.effect"
    ]
    profile_events = {
        event["event_cid"]: event
        for event in events
        if event.get("event_cid") in {
            call["result"]["_mcppp"]["event_cid"] for call in calls
        }
    }
    assert fr["count"] == len(events) == 6
    assert len(decisions) == len(effects) == len(profile_events) == 2
    for call in calls:
        request_id = call["result"]["_authorization"]["request_id"]
        decision = decisions[request_id]
        profile_event = profile_events[call["result"]["_mcppp"]["event_cid"]]
        effect = next(event for event in effects if event["request_id"] == request_id)
        assert profile_event["parents"] == [decision["event_cid"]]
        assert effect["parents"] == [decision["event_cid"]]


def test_profile_c_ucan_validate(tmp_path):
    """Profile C grants signed capabilities and rejects unsigned downgrade."""
    harness = _server(tmp_path, "profile-c")
    token = harness.token("ipfs/read", resource="ipfs")
    ok = anyio.run(
        harness.server.handle,
        {
            "jsonrpc": "2.0",
            "id": 30,
            "method": "mcp++/ucan/validate",
            "params": {
                "token": token,
                "resource": "ipfs",
                "ability": "ipfs/read",
                "actor": ACTOR,
            },
        },
    )
    assert ok["result"]["allowed"] is True
    unsigned = {
        "issuer": ISSUER,
        "audience": ACTOR,
        "capabilities": [{"resource": "ipfs", "ability": "ipfs/read"}],
    }
    bad = anyio.run(
        harness.server.handle,
        {
            "jsonrpc": "2.0",
            "id": 31,
            "method": "mcp++/ucan/validate",
            "params": {
                "chain": [unsigned],
                "resource": "ipfs",
                "ability": "ipfs/read",
                "actor": ACTOR,
            },
        },
    )
    assert bad["result"]["allowed"] is False


def test_profile_d_policy_evaluate(tmp_path):
    harness = _server(tmp_path, "profile-d")
    tool = "ipfs_tools/ipfs_add"
    common = {
        "actor": ACTOR,
        "action": tool,
        "resource": RESOURCE,
    }
    allow = anyio.run(
        harness.server.handle,
        {
            "jsonrpc": "2.0",
            "id": 32,
            "method": "mcp++/policy/evaluate",
            "params": {**common, "policy": _policy(tool)},
        },
    )["result"]
    deny = anyio.run(
        harness.server.handle,
        {
            "jsonrpc": "2.0",
            "id": 33,
            "method": "mcp++/policy/evaluate",
            "params": {**common, "policy": _policy(tool, "prohibition")},
        },
    )["result"]
    assert allow["decision"] == "allow" and deny["decision"] == "deny"
    missing = anyio.run(
        harness.server.handle,
        {
            "jsonrpc": "2.0",
            "id": 34,
            "method": "mcp++/policy/evaluate",
            "params": common,
        },
    )
    assert missing["error"]["data"]["reason"] == "policy_provider_unavailable"


def test_all_five_profiles_smoke(tmp_path, hermetic_core_backend):
    """One server exercises A,B,C,D,E + base MCP in a single flow."""
    harness = _server(tmp_path, "all-profiles")
    s = harness.server
    init = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    profs = init["result"]["capabilities"]["experimental"]["mcp++"]["profiles"]
    assert all(profs.get(k) for k in ("A_interface_descriptors", "B_cid_envelopes", "C_ucan_signed", "D_policy", "E_dag_events"))
    assert "C_ucan_unsigned" not in profs
    assert anyio.run(s.handle, {"jsonrpc": "2.0", "id": 2, "method": "mcp++/interfaces"})["result"]["interfaces"]
    tool = "pin_tools/pin_add"
    pol = anyio.run(
        s.handle,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "mcp++/policy/evaluate",
            "params": {
                "actor": ACTOR,
                "action": tool,
                "resource": RESOURCE,
                "policy": _policy(tool),
            },
        },
    )
    assert pol["result"]["decision"] == "allow"
    token = harness.token("ipfs/read", resource="ipfs")
    assert anyio.run(
        s.handle,
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "mcp++/ucan/validate",
            "params": {
                "token": token,
                "resource": "ipfs",
                "ability": "ipfs/read",
                "actor": ACTOR,
            },
        },
    )["result"]["allowed"]
    call = harness.call(tool, {"cid": "bafy"}, profile_b=True, request_id=5)
    assert call["result"]["_mcppp"]["receipt_cid"].startswith("bafkrei")
    assert anyio.run(
        s.handle,
        {"jsonrpc": "2.0", "id": 6, "method": "mcp++/dag/frontier"},
    )["result"]["count"] == 3


def test_p2p_transport_roundtrip(tmp_path, hermetic_core_backend):
    """Profile E: a tools/call routed through the libp2p framing returns the
    same result as stdio/HTTP, without requiring py-libp2p to be installed."""
    from ipfs_kit_py.mcp_server.p2p_transport import PROTOCOL_ID, handle_stream_message
    assert PROTOCOL_ID == "/mcp+p2p/1.0.0"
    harness = _server(tmp_path, "p2p")
    req = json.dumps({
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": harness.call_params("pin_tools/get_pinset", {}),
    }).encode()
    resp = json.loads(anyio.run(handle_stream_message, req, harness.server.handle))
    assert resp["result"]["status"] == "success"
    assert resp["result"]["_authorization"]["decision"] == "allow"


def test_fastmcp_registrar_covers_full_registry(tmp_path, hermetic_core_backend):
    """Backwards-compat: FastMCP registration exposes every registry tool, one
    registry, callable through the same dispatch codepath."""
    from ipfs_kit_py.mcp_server.fastmcp_app import register_fastmcp

    class _FakeApp:
        def __init__(self): self.tools = {}
        def add_tool(self, fn, name=None, description=""): self.tools[name] = fn

    app = _FakeApp()
    harness = _server(tmp_path, "fastmcp")
    names = register_fastmcp(app, server=harness.server)
    canonical_names = {
        schema["name"] for schema in HierarchicalToolManager().all_tool_schemas()
    }
    assert len(names) == len(canonical_names)
    assert set(names) == set(app.tools) == canonical_names
    import inspect

    parameters = inspect.signature(app.tools["pin_add"]).parameters
    assert "mcppp_envelope" in parameters
    assert "_mcppp_envelope" not in parameters
    denied = anyio.run(app.tools["pin_add"], {"cid": "bafy"})
    assert denied["status"] == "error"
    assert denied["error"]["data"]["authorization"] == "denied"

    params = harness.call_params("pin_tools/pin_add", {"cid": "bafy"})

    async def authorized_call():
        return await app.tools["pin_add"](
            arguments=params["arguments"],
            mcppp_envelope=params["_mcppp_envelope"],
        )

    r = anyio.run(authorized_call)
    assert r["status"] == "success"


def test_initialize_handshake():
    """Standard MCP clients call initialize first; server returns protocol +
    capabilities (backwards-compat handshake)."""
    s = MCPServer()
    r = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                             "params": {"protocolVersion": "2025-06-18"}})
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
