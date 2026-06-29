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
    assert len(lst["result"]["tools"]) == 17
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
                assert len(body["result"]["tools"]) == 17
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
