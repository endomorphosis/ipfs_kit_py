"""Opt-in integration test for daemon initialization.

This test is intentionally gated behind `IPFS_KIT_RUN_LONG_INTEGRATION=1`.
It validates that the supported unified MCP integration path can successfully
talk to a running IPFS daemon.

It does not start heavyweight HTTP server variants.
"""

from __future__ import annotations

import os

import pytest


def _skip_long_integration() -> None:
    if os.environ.get("IPFS_KIT_RUN_LONG_INTEGRATION") != "1":
        pytest.skip("Set IPFS_KIT_RUN_LONG_INTEGRATION=1 to run daemon initialization test")


@pytest.mark.anyio
async def test_daemon_initialization(ipfs_api_v0_url: str):
    _skip_long_integration()

    # Ensure the IPFS daemon is reachable (fixture bootstraps best-effort).
    assert isinstance(ipfs_api_v0_url, str)
    assert ipfs_api_v0_url

    from ipfs_kit_py.mcp.servers.unified_mcp_server import IPFSKitIntegration

    integration = IPFSKitIntegration(auto_start_daemons=False, auto_start_lotus_daemon=False)
    result = await integration.execute_ipfs_operation("ipfs_version")

    assert isinstance(result, dict)
    if result.get("success") is False:
        pytest.fail(f"ipfs_version failed under long integration: {result.get('error') or result}")
