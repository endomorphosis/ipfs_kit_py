#!/usr/bin/env python3
import pytest
from fastapi.testclient import TestClient
from merged_dashboard import ModernizedComprehensiveDashboard

@pytest.fixture
def client():
    dashboard = ModernizedComprehensiveDashboard()
    return TestClient(dashboard.app)

def test_get_services(client):
    response = client.get("/api/services")
    assert response.status_code == 200
    assert response.json() == {
        "ipfs": "stopped",
        "lotus": "running",
        "cluster": "stopped",
        "lassie": "stopped"
    }

def test_get_backends(client):
    response = client.get("/api/backends")
    assert response.status_code == 200
    assert response.json() == {'wip': 'work in progress'}

def test_get_peers(client):
    response = client.get("/api/peers")
    assert response.status_code == 200
    assert response.json() == {'connected_peers': [], 'total_peers': 0}

def test_get_services_from_dashboard(client):
    response = client.get("/api/services")
    assert response.status_code == 200
    assert response.json() == {
        "ipfs": "stopped",
        "lotus": "running",
        "cluster": "stopped",
        "lassie": "stopped"
    }
