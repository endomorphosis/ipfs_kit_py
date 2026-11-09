#!/usr/bin/env python3
"""Adapter-level VFS conformance checks for legacy MCP servers.

These tests verify that legacy MCP VFS adapters delegate canonical mount
lifecycle/path-resolution operations to the shared VFS contract layer.
"""

import sys
import json
from pathlib import Path

import anyio


repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from ipfs_kit_py.mcp.servers import enhanced_mcp_server_with_vfs as enhanced_server
from ipfs_kit_py.mcp.servers import enhanced_mcp_server_with_daemon_mgmt as daemon_mgmt_server
from ipfs_kit_py.mcp.servers import standalone_vfs_mcp_server as standalone_server
from ipfs_kit_py.mcp.servers import unified_mcp_server as unified_server


def test_enhanced_adapter_delegates_canonical_mount_ops(monkeypatch):
    monkeypatch.setattr(enhanced_server, "HAS_CONTRACT_VFS", True)

    async def fake_mount(ipfs_path, mount_point):
        return {
            "success": True,
            "mounted": True,
            "ipfs_path": ipfs_path,
            "mount_point": mount_point,
        }

    async def fake_unmount(mount_point):
        return {"success": True, "unmounted": True, "mount_point": mount_point}

    async def fake_list_mounts():
        return {
            "success": True,
            "count": 1,
            "mounts": [{"mount_point": "/m", "backend": "ipfs"}],
        }

    async def fake_resolve(local_path):
        return {"success": True, "resolved": True, "local_path": local_path, "resolved_path": "/ipfs/QmTest/file.txt"}

    monkeypatch.setattr(enhanced_server, "contract_vfs_mount", fake_mount)
    monkeypatch.setattr(enhanced_server, "contract_vfs_unmount", fake_unmount)
    monkeypatch.setattr(enhanced_server, "contract_vfs_list_mounts", fake_list_mounts)
    monkeypatch.setattr(enhanced_server, "contract_vfs_resolve_path", fake_resolve)

    adapter = enhanced_server.VFSIntegration.__new__(enhanced_server.VFSIntegration)

    mount_result = anyio.run(adapter._vfs_mount, "/ipfs/QmTest", "/m")
    assert mount_result["success"] is True
    assert mount_result["operation"] == "vfs_mount"

    unmount_result = anyio.run(adapter._vfs_unmount, "/m")
    assert unmount_result["success"] is True
    assert unmount_result["operation"] == "vfs_unmount"

    list_result = anyio.run(adapter._vfs_list_mounts)
    assert list_result["success"] is True
    assert list_result["operation"] == "vfs_list_mounts"
    assert list_result["count"] == 1

    resolve_result = anyio.run(adapter._vfs_resolve_path, "/m/file.txt")
    assert resolve_result["success"] is True
    assert resolve_result["operation"] == "vfs_resolve_path"
    assert resolve_result["resolved"] is True


def test_enhanced_dispatch_routes_new_vfs_operations(monkeypatch):
    monkeypatch.setattr(enhanced_server, "HAS_VFS", True)

    adapter = enhanced_server.VFSIntegration.__new__(enhanced_server.VFSIntegration)

    async def fake_unmount(**kwargs):
        return {"success": True, "operation": "vfs_unmount", "kwargs": kwargs}

    async def fake_list_mounts(**kwargs):
        return {"success": True, "operation": "vfs_list_mounts", "kwargs": kwargs}

    async def fake_resolve(**kwargs):
        return {"success": True, "operation": "vfs_resolve_path", "kwargs": kwargs}

    adapter._vfs_unmount = fake_unmount
    adapter._vfs_list_mounts = fake_list_mounts
    adapter._vfs_resolve_path = fake_resolve

    unmount_result = anyio.run(lambda: adapter.execute_vfs_operation("vfs_unmount", mount_point="/m"))
    assert unmount_result["success"] is True
    assert unmount_result["operation"] == "vfs_unmount"

    list_result = anyio.run(lambda: adapter.execute_vfs_operation("vfs_list_mounts"))
    assert list_result["success"] is True
    assert list_result["operation"] == "vfs_list_mounts"

    resolve_result = anyio.run(lambda: adapter.execute_vfs_operation("vfs_resolve_path", local_path="/m/a.txt"))
    assert resolve_result["success"] is True
    assert resolve_result["operation"] == "vfs_resolve_path"


def test_standalone_adapter_delegates_canonical_mount_ops(monkeypatch):
    monkeypatch.setattr(standalone_server, "HAS_CONTRACT_VFS", True)

    async def fake_mount(ipfs_path, mount_point):
        return {
            "success": True,
            "mounted": True,
            "ipfs_path": ipfs_path,
            "mount_point": mount_point,
        }

    async def fake_unmount(mount_point):
        return {"success": True, "unmounted": True, "mount_point": mount_point}

    async def fake_list_mounts():
        return {
            "success": True,
            "count": 1,
            "mounts": [{"mount_point": "/m", "backend": "ipfs"}],
        }

    async def fake_resolve(local_path):
        return {"success": True, "resolved": True, "local_path": local_path, "resolved_path": "/ipfs/QmTest/file.txt"}

    monkeypatch.setattr(standalone_server, "contract_vfs_mount", fake_mount)
    monkeypatch.setattr(standalone_server, "contract_vfs_unmount", fake_unmount)
    monkeypatch.setattr(standalone_server, "contract_vfs_list_mounts", fake_list_mounts)
    monkeypatch.setattr(standalone_server, "contract_vfs_resolve_path", fake_resolve)

    adapter = standalone_server.StandaloneVFS.__new__(standalone_server.StandaloneVFS)

    mount_result = anyio.run(adapter.vfs_mount, "/ipfs/QmTest", "/m")
    assert mount_result["success"] is True
    assert mount_result["operation"] == "vfs_mount"

    unmount_result = anyio.run(adapter.vfs_unmount, "/m")
    assert unmount_result["success"] is True
    assert unmount_result["operation"] == "vfs_unmount"

    list_result = anyio.run(adapter.vfs_list_mounts)
    assert list_result["success"] is True
    assert list_result["operation"] == "vfs_list_mounts"
    assert list_result["count"] == 1

    resolve_result = anyio.run(adapter.vfs_resolve_path, "/m/file.txt")
    assert resolve_result["success"] is True
    assert resolve_result["operation"] == "vfs_resolve_path"
    assert resolve_result["resolved"] is True


def test_standalone_highlevel_batch_supports_new_mount_lifecycle_ops(monkeypatch):
    adapter = standalone_server.StandaloneVFS.__new__(standalone_server.StandaloneVFS)

    async def fake_mount(**kwargs):
        return {"success": True, "operation": "vfs_mount", "kwargs": kwargs}

    async def fake_unmount(**kwargs):
        return {"success": True, "operation": "vfs_unmount", "kwargs": kwargs}

    async def fake_list_mounts(**kwargs):
        return {"success": True, "operation": "vfs_list_mounts", "kwargs": kwargs}

    async def fake_resolve(**kwargs):
        return {"success": True, "operation": "vfs_resolve_path", "kwargs": kwargs}

    adapter.vfs_mount = fake_mount
    adapter.vfs_unmount = fake_unmount
    adapter.vfs_list_mounts = fake_list_mounts
    adapter.vfs_resolve_path = fake_resolve

    result = anyio.run(
        lambda: adapter.highlevel_batch_process(
            [
                {"type": "vfs_mount", "params": {"ipfs_path": "/", "mount_point": "/m"}},
                {"type": "vfs_unmount", "params": {"mount_point": "/m"}},
                {"type": "vfs_list_mounts", "params": {}},
                {"type": "vfs_resolve_path", "params": {"local_path": "/m/a.txt"}},
            ]
        )
    )

    assert result["success"] is True
    assert result["operations_count"] == 4
    assert all(entry["success"] is True for entry in result["results"])


def test_legacy_mcp_tool_schemas_expose_new_vfs_operations():
    enhanced_mcp = enhanced_server.MCPServer.__new__(enhanced_server.MCPServer)
    standalone_mcp = standalone_server.MCPServer.__new__(standalone_server.MCPServer)

    enhanced_tools = enhanced_server.MCPServer._define_tools(enhanced_mcp)
    standalone_tools = standalone_server.MCPServer._define_tools(standalone_mcp)

    for operation in ("vfs_unmount", "vfs_list_mounts", "vfs_resolve_path"):
        assert operation in enhanced_tools
        assert operation in standalone_tools


def test_unified_mcp_dispatches_vfs_tools_and_exposes_resolve_path(monkeypatch):
    monkeypatch.setattr(unified_server, "HAS_CANONICAL_VFS", True)

    monkeypatch.setattr(unified_server, "vfs_list_mounts", lambda: {"success": True, "count": 0, "mounts": []})
    monkeypatch.setattr(
        unified_server,
        "vfs_resolve_path",
        lambda local_path: {
            "success": True,
            "resolved": True,
            "local_path": local_path,
            "resolved_path": "/ipfs/QmResolved",
        },
    )

    server = unified_server.create_mcp_server(register_all_tools=False)

    listed_tools = anyio.run(server.handle_tools_list)
    tool_names = {tool["name"] for tool in listed_tools["tools"] if isinstance(tool, dict) and "name" in tool}
    assert "vfs_resolve_path" in tool_names

    mounts_result = anyio.run(lambda: server.handle_tools_call({"name": "vfs_list_mounts", "arguments": {}}))
    assert mounts_result["isError"] is False

    payload_mounts = json.loads(mounts_result["content"][0]["text"])
    assert payload_mounts["success"] is True
    assert payload_mounts["count"] == 0

    resolve_result = anyio.run(
        lambda: server.handle_tools_call({"name": "vfs_resolve_path", "arguments": {"local_path": "/m/a.txt"}})
    )
    assert resolve_result["isError"] is False

    payload_resolve = json.loads(resolve_result["content"][0]["text"])
    assert payload_resolve["success"] is True
    assert payload_resolve["resolved"] is True


def test_daemon_mgmt_server_dispatches_vfs_tools(monkeypatch):
    monkeypatch.setattr(daemon_mgmt_server, "HAS_CANONICAL_VFS", True)
    monkeypatch.setattr(daemon_mgmt_server, "vfs_list_mounts", lambda: {"success": True, "count": 2, "mounts": []})

    server = daemon_mgmt_server.EnhancedMCPServerWithDaemonMgmt.__new__(daemon_mgmt_server.EnhancedMCPServerWithDaemonMgmt)

    result = anyio.run(
        lambda: server.handle_tools_call({"name": "vfs_list_mounts", "arguments": {}})
    )
    assert result["isError"] is False

    payload = json.loads(result["content"][0]["text"])
    assert payload["success"] is True
    assert payload["count"] == 2


def test_legacy_servers_blocked_in_production_without_override(monkeypatch):
    monkeypatch.setenv("IPFS_KIT_MCP_MODE", "production")
    monkeypatch.delenv("IPFS_KIT_ALLOW_LEGACY_MCP", raising=False)

    try:
        enhanced_server.MCPServer()
        assert False, "Expected production guard to block enhanced legacy server"
    except RuntimeError as e:
        assert "deprecated and blocked" in str(e)

    try:
        standalone_server.MCPServer()
        assert False, "Expected production guard to block standalone legacy server"
    except RuntimeError as e:
        assert "deprecated and blocked" in str(e)

    try:
        daemon_mgmt_server.EnhancedMCPServerWithDaemonMgmt()
        assert False, "Expected production guard to block daemon-mgmt legacy server"
    except RuntimeError as e:
        assert "deprecated and blocked" in str(e)
