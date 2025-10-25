from fastapi.testclient import TestClient
from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard

def test_deprecation_hit_counts_increment():
    inst = ConsolidatedMCPDashboard({"port":0})
    client = TestClient(inst.app)
    # Call deprecated endpoint multiple times
    for _ in range(3):
        r = client.get("/api/system/overview")
        assert r.status_code == 200
    # Fetch deprecations
    r = client.get("/api/system/deprecations")
    assert r.status_code == 200
    data = r.json()
    items = data.get("deprecated") or []
    overview = next((i for i in items if i.get("endpoint") == "/api/system/overview"), None)
    assert overview is not None
    # Expect at least 3 hits (could be more if other internal calls count)
    assert overview.get("hits", 0) >= 3
