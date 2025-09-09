import pytest
from fastapi.testclient import TestClient
from consolidated_mcp_dashboard import ConsolidatedMCPDashboard


def test_overview_endpoint_structure():
    inst = ConsolidatedMCPDashboard({"port": 0})
    client = TestClient(inst.app)
    r = client.get("/api/system/overview")
    assert r.status_code == 200
    assert r.headers.get("x-deprecated") == "true"
    data = r.json()
    # Required top-level keys
    for key in ("success", "deprecated", "status", "health", "metrics", "migration"):
        assert key in data, f"missing key: {key}"
    assert data["deprecated"] is True
    # Status payload shape basics
    status = data["status"]
    assert isinstance(status, dict)
    counts = status.get("counts") or {}
    for ck in ("services_active", "backends", "buckets", "pins", "requests"):
        assert ck in counts
    # Metrics minimal fields
    metrics = data["metrics"]
    assert "ts" in metrics
    # Migration map
    migration = data["migration"]
    assert migration.get("health") == "/api/system/health"
    assert migration.get("status") == "/api/mcp/status"
    assert migration.get("metrics") == "/api/metrics/system"


def test_overview_endpoint_warning_logged_once(caplog):
    inst = ConsolidatedMCPDashboard({"port": 0})
    client = TestClient(inst.app)
    caplog.set_level("WARNING")
    client.get("/api/system/overview")
    first_count = sum(1 for r in caplog.records if "/api/system/overview is deprecated" in r.message)
    client.get("/api/system/overview")
    second_count = sum(1 for r in caplog.records if "/api/system/overview is deprecated" in r.message)
    # Only one new log expected overall
    assert first_count == 1
    assert second_count == 1
