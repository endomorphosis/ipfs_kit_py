#!/usr/bin/env python3
"""Pytest-discoverable VFS/MCP integration tests."""

import json
import os
import sys
from pathlib import Path

import pytest


project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

pytestmark = pytest.mark.anyio


async def test_vfs_core_import_and_backend_registry():
    from ipfs_kit_py.ipfs_fsspec import get_vfs

    vfs = get_vfs()
    assert vfs is not None

    backends = vfs.registry.list_backends()
    assert isinstance(backends, list)
    assert len(backends) >= 1


async def test_unified_mcp_tools_list_only_executable_tools():
    from ipfs_kit_py.mcp.servers.unified_mcp_server import create_mcp_server

    server = create_mcp_server(auto_start_daemons=False, auto_start_lotus_daemon=False)
    listing = await server.handle_tools_list({})
    tools = listing.get("tools", [])
    names = {tool.get("name") for tool in tools if isinstance(tool, dict)}

    assert "vfs_list_mounts" in names
    assert "system_health" in names
    assert "ipfs_version" in names
    assert "ipfs_id" in names
    assert "ipfs_add" not in names


async def test_unified_mcp_non_executable_tool_returns_explicit_error_code():
    from ipfs_kit_py.mcp.servers.unified_mcp_server import create_mcp_server

    server = create_mcp_server(auto_start_daemons=False, auto_start_lotus_daemon=False)
    response = await server.handle_tools_call({"name": "ipfs_add", "arguments": {"path": "/tmp/x"}})

    payload = json.loads(((response.get("content") or [{}])[0]).get("text", "{}"))
    assert payload.get("success") is False
    assert payload.get("code") == "tool_not_executable"
    assert response.get("isError") is True


async def test_unified_mcp_advertised_tools_execute_without_not_implemented():
    from ipfs_kit_py.mcp.servers.unified_mcp_server import create_mcp_server

    server = create_mcp_server(auto_start_daemons=False, auto_start_lotus_daemon=False)
    listing = await server.handle_tools_list({})
    tools = listing.get("tools", [])
    names = [tool.get("name") for tool in tools if isinstance(tool, dict) and isinstance(tool.get("name"), str)]

    for name in names:
        arguments = {}
        if name == "vfs_mount":
            arguments = {
                "source": "/",
                "mount_point": "/tmp/vfs-mcp-integration-mount",
                "read_only": True,
            }

        response = await server.handle_tools_call({"name": name, "arguments": arguments})
        content = (response.get("content") or [{}])[0]
        parsed = json.loads(content.get("text", "{}"))

        assert parsed.get("code") != "not_implemented", f"{name} advertised but not executable"


async def test_vfs_roundtrip_via_mcp_call_surface():
    from ipfs_kit_py.ipfs_fsspec import get_vfs
    from ipfs_kit_py.mcp.servers.unified_mcp_server import create_mcp_server

    mount_point = "/tmp/vfs-mcp-roundtrip"
    server = create_mcp_server(auto_start_daemons=False, auto_start_lotus_daemon=False)

    vfs = get_vfs()
    vfs.unmount(mount_point)
    vfs.mount(mount_point, "memory", "/", read_only=False)

    write_response = await server.handle_tools_call(
        {
            "name": "vfs_write",
            "arguments": {
                "path": f"{mount_point}/integration.txt",
                "content": "mcp-integration",
                "create_dirs": True,
            },
        }
    )
    write_payload = json.loads(((write_response.get("content") or [{}])[0]).get("text", "{}"))
    assert write_payload.get("success") is True

    read_response = await server.handle_tools_call(
        {
            "name": "vfs_read",
            "arguments": {"path": f"{mount_point}/integration.txt"},
        }
    )
    read_payload = json.loads(((read_response.get("content") or [{}])[0]).get("text", "{}"))
    assert read_payload.get("success") is True
    assert read_payload.get("content") == "mcp-integration"

    await server.handle_tools_call(
        {
            "name": "vfs_unmount",
            "arguments": {"mount_point": mount_point},
        }
    )
