import pytest
from fastapi.testclient import TestClient
from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard


def test_websocket_initial_payload_sequence():
    inst = ConsolidatedMCPDashboard({"port": 0})
    client = TestClient(inst.app)
    with client.websocket_connect("/ws") as ws:
        first = ws.receive_json()
        second = ws.receive_json()
    # First message should be system_update with status payload
    assert first.get("type") == "system_update"
    data = first.get("data") or {}
    assert data.get("success") is True
    # Second message should be metrics snapshot
    assert second.get("type") == "metrics"
    # Required metric-ish keys
    assert "ts" in second
    # Ensure counts present in status
    counts = (data.get("data") or {}).get("data", {}).get("counts") or (data.get("data") or {}).get("counts") or {}
    for ck in ("services_active", "backends", "buckets", "pins", "requests"):
        assert ck in counts
