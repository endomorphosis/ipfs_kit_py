"""End-to-end interop tests for the ipfs_kit_py MCP++ server.

Proves the four surfaces share one registry & contract: Python imports, CLI,
MCP JSON-RPC (stdio + HTTP/Hypercorn), and the generated JS SDK.
"""
import json
import subprocess
import sys
from pathlib import Path

import anyio
import pytest

PKG = Path(__file__).resolve().parents[2]  # ipfs_kit_py/ root
sys.path.insert(0, str(PKG))

from ipfs_kit_py.mcp_server import HierarchicalToolManager  # noqa: E402
from ipfs_kit_py.mcp_server.server import MCPServer  # noqa: E402
from ipfs_kit_py.mcp_server.tools import ipfs_tools  # noqa: E402
from ipfs_kit_py.mcp_server.js_sdk import generate  # noqa: E402


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


def test_mcp_jsonrpc_tools_list_and_call():
    s = MCPServer()
    lst = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert len(lst["result"]["tools"]) == 28
    init = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 2, "method": "initialize"})
    assert init["result"]["serverInfo"]["name"] == "ipfs_kit_py-mcpplusplus"
    call = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                "params": {"name": "ipfs_tools/ipfs_cat", "arguments": {"cid": "bafy"}}})
    assert call["result"]["status"] == "success"


def test_cli_surface_matches():
    out = subprocess.run([sys.executable, "-m", "ipfs_kit_py.mcp_server.cli",
                          "pin_tools", "pin_add", "--cid", "bafy"],
                         capture_output=True, text=True, cwd=str(PKG))
    assert json.loads(out.stdout)["status"] == "success"


def test_js_sdk_mirrors_python_tools():
    src = generate.render()
    py = {s["name"] for s in HierarchicalToolManager().all_tool_schemas()}
    for name in py:
        assert f'"{name}"' in src
    assert "IpfsKitMcpClient" in src


def test_http_transport_hypercorn():
    import time
    import urllib.request
    proc = subprocess.Popen(
        [sys.executable, "-m", "ipfs_kit_py.mcp_server.server", "--transport", "http", "--port", "8067"],
        cwd=str(PKG), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(20):
            try:
                req = urllib.request.Request(
                    "http://127.0.0.1:8067",
                    data=b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}',
                    headers={"content-type": "application/json"})
                body = json.loads(urllib.request.urlopen(req, timeout=2).read())
                assert len(body["result"]["tools"]) == 28
                break
            except Exception:
                time.sleep(0.5)
        else:
            pytest.fail("http server never came up")
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_mfs_and_swarm_groups():
    tm = HierarchicalToolManager()
    cats = {c["name"] for c in tm.list_categories()}
    assert {"mfs_tools", "swarm_tools"} <= cats
    assert anyio.run(tm.dispatch, "mfs_tools", "files_ls", {"path": "/"})["status"] == "success"
    assert anyio.run(tm.dispatch, "swarm_tools", "node_id", {})["status"] == "success"


def test_mcppp_envelope_accepted():
    s = MCPServer()
    call = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 9, "method": "tools/call",
                               "params": {"name": "pin_tools/pin_rm", "arguments": {"cid": "bafy"},
                                          "_mcppp_envelope": {"toolName": "pin_rm"}}})
    assert call["result"]["status"] == "success"


def test_name_car_pinset_groups():
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


def test_swissknife_manifest_in_sync():
    """Dashboard manifest must match the server's generated manifest."""
    dash = PKG.parents[2] / "swissknife" / "src" / "services" / "mcp-ipfs-kit-tools-manifest.json"
    if dash.exists():
        assert dash.read_text() == generate.render_manifest(), "swissknife manifest stale: resync"


def test_profile_b_receipt_emitted():
    """tools/call with profile_b returns canonical CID receipt (B)."""
    s = MCPServer()
    call = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 11, "method": "tools/call",
                               "params": {"name": "pin_tools/pin_rm", "arguments": {"cid": "bafy"},
                                          "profile_b": True}})
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
    assert len(ifaces) == len(s.tm.all_tool_schemas())
    d = ifaces[0]
    for k in ("namespace", "name", "input_schema", "output_schema", "errors", "semantic_tags", "compatibility"):
        assert k in d
    assert d["namespace"].startswith("ipfs_kit/")


def test_profile_e_dag_chains_events():
    """Profile E: profile_b calls append linked DAG events; frontier is latest."""
    s = MCPServer()
    for i in range(2):
        anyio.run(s.handle, {"jsonrpc": "2.0", "id": 100 + i, "method": "tools/call",
                             "params": {"name": "pin_tools/pin_rm", "arguments": {"cid": "bafy"}, "profile_b": True}})
    fr = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 200, "method": "mcp++/dag/frontier"})["result"]
    assert fr["count"] == 2 and len(fr["frontier"]) == 1
    assert s._dag[1]["parents"] == [s._dag[0]["event_cid"]]


def test_profile_c_ucan_validate():
    """Profile C: valid root->leaf chain grants, escalation denied."""
    s = MCPServer()
    chain = [
        {"issuer": "did:a", "audience": "did:b", "capabilities": [{"resource": "ipfs", "ability": "*"}]},
        {"issuer": "did:b", "audience": "did:c", "capabilities": [{"resource": "ipfs", "ability": "read"}]},
    ]
    ok = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 30, "method": "mcp++/ucan/validate",
                             "params": {"chain": chain, "resource": "ipfs", "ability": "read", "actor": "did:c"}})
    assert ok["result"]["allowed"] is True
    bad = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 31, "method": "mcp++/ucan/validate",
                              "params": {"chain": chain, "resource": "ipfs", "ability": "write", "actor": "did:c"}})
    assert bad["result"]["allowed"] is False


def test_profile_d_policy_evaluate():
    s = MCPServer()
    allow = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 32, "method": "mcp++/policy/evaluate",
                                "params": {"tool": "ipfs_add", "risk": 0.1}})["result"]
    deny = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 33, "method": "mcp++/policy/evaluate",
                               "params": {"tool": "ipfs_add", "deny": ["ipfs_add"]}})["result"]
    assert allow["decision"] == "allow" and deny["decision"] == "deny"


def test_all_five_profiles_smoke():
    """One server exercises A,B,C,D,E + base MCP in a single flow."""
    s = MCPServer()
    init = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    profs = init["result"]["capabilities"]["experimental"]["mcp++"]["profiles"]
    assert all(profs.get(k) for k in ("A_interface_descriptors", "B_cid_envelopes", "C_ucan_unsigned", "D_policy", "E_dag_events"))
    assert anyio.run(s.handle, {"jsonrpc": "2.0", "id": 2, "method": "mcp++/interfaces"})["result"]["interfaces"]
    pol = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 3, "method": "mcp++/policy/evaluate", "params": {"tool": "ipfs_add"}})
    assert pol["result"]["decision"] == "allow"
    chain = [{"issuer": "did:a", "audience": "did:c", "capabilities": [{"resource": "ipfs", "ability": "read"}]}]
    assert anyio.run(s.handle, {"jsonrpc": "2.0", "id": 4, "method": "mcp++/ucan/validate",
                               "params": {"chain": chain, "resource": "ipfs", "ability": "read", "actor": "did:c"}})["result"]["allowed"]
    call = anyio.run(s.handle, {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                               "params": {"name": "pin_tools/pin_rm", "arguments": {"cid": "bafy"}, "profile_b": True}})
    assert call["result"]["_mcppp"]["receipt_cid"].startswith("bafkrei")
    assert anyio.run(s.handle, {"jsonrpc": "2.0", "id": 6, "method": "mcp++/dag/frontier"})["result"]["count"] == 1


def test_p2p_transport_roundtrip():
    """Profile E: a tools/call routed through the libp2p framing returns the
    same result as stdio/HTTP, without requiring py-libp2p to be installed."""
    from ipfs_kit_py.mcp_server.p2p_transport import handle_stream_message, PROTOCOL_ID
    assert PROTOCOL_ID == "/mcp+p2p/1.0.0"
    s = MCPServer()
    req = json.dumps({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                      "params": {"name": "pin_tools/get_pinset", "arguments": {}}}).encode()
    resp = json.loads(anyio.run(handle_stream_message, req, s.handle))
    assert resp["result"]["status"] == "success"


def test_fastmcp_registrar_covers_full_registry():
    """Backwards-compat: FastMCP registration exposes the same 28 tools, one
    registry, callable through the same dispatch codepath."""
    from ipfs_kit_py.mcp_server.fastmcp_app import register_fastmcp

    class _FakeApp:
        def __init__(self): self.tools = {}
        def add_tool(self, fn, name=None, description=""): self.tools[name] = fn

    app = _FakeApp()
    names = register_fastmcp(app)
    assert len(names) == 28 and set(names) == set(app.tools)
    r = anyio.run(app.tools["pin_rm"], {"cid": "bafy"})
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
