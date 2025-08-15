from fastapi.testclient import TestClient
from consolidated_mcp_dashboard import ConsolidatedMCPDashboard


def test_websocket_initial_includes_deprecations():
    inst = ConsolidatedMCPDashboard({"port":0})
    client = TestClient(inst.app)
    with client.websocket_connect("/ws") as ws:
        first = ws.receive_json()
    assert first.get("type") == "system_update"
    deps = first.get("deprecations")
    assert isinstance(deps, list)
    overview = next((d for d in deps if d.get("endpoint") == "/api/system/overview"), None)
    assert overview is not None
    assert overview.get("remove_in") == "3.2.0"
    mig = overview.get("migration") or {}
    assert mig.get("health") == "/api/system/health"
    assert mig.get("status") == "/api/mcp/status"
    assert mig.get("metrics") == "/api/metrics/system"
