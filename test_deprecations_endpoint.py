from fastapi.testclient import TestClient
from consolidated_mcp_dashboard import ConsolidatedMCPDashboard

def test_deprecations_endpoint_lists_overview():
    inst = ConsolidatedMCPDashboard({"port":0})
    client = TestClient(inst.app)
    r = client.get("/api/system/deprecations")
    assert r.status_code == 200
    data = r.json()
    items = data.get("deprecated") or []
    overview = next((i for i in items if i.get("endpoint") == "/api/system/overview"), None)
    assert overview is not None
    assert overview.get("remove_in") == "3.2.0"
    mig = overview.get("migration") or {}
    assert mig.get("health") == "/api/system/health"
    assert mig.get("status") == "/api/mcp/status"
    assert mig.get("metrics") == "/api/metrics/system"
