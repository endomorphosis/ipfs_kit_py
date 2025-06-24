#!/usr/bin/env python3
"""
Distributed Controller Test Script using FastAPI TestClient
"""

import json
import time
import sys
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
from ipfs_kit_py.mcp.controllers.distributed_controller import DistributedController

def setup_test_app():
    """Set up a FastAPI test app with the distributed controller."""
    # Create FastAPI app
    app = FastAPI(title="IPFS MCP Server Test")

    # Create model and controller
    model = IPFSModel()
    controller = DistributedController(model)

    # Create router and register controller routes
    router = APIRouter()
    controller.register_routes(router)

    # Include router in app with proper prefix
    app.include_router(router, prefix="/api/v0/mcp")

    return app

def run_test(client, endpoint, method="GET", data=None, test_name=None, expected_status=200):
    """Run a test on a specific endpoint."""
    if test_name is None:
        test_name = f"{method} {endpoint}"

    print(f"\n[TEST] {test_name}")
    print(f"Request: {method} {endpoint}")

    if data and isinstance(data, dict):
        try:
            print(f"Data: {json.dumps(data)}")
        except:
            print(f"Data: [Complex data structure]")

    start_time = time.time()
    try:
        if method.upper() == "GET":
            response = client.get(endpoint)
        elif method.upper() == "POST":
            response = client.post(endpoint, json=data)
        elif method.upper() == "DELETE":
            response = client.delete(endpoint)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        elapsed = time.time() - start_time
        print(f"Status: {response.status_code}")
        print(f"Time: {elapsed:.3f}s")

        try:
            response_data = response.json()
            print(f"Response: {json.dumps(response_data, indent=2)}")
        except:
            print(f"Response: {response.text[:500]}...")

        # Check status
        success = response.status_code == expected_status
        if success:
            print(f"✅ Test passed: {test_name}")
        else:
            print(f"❌ Test failed: {test_name}")
            print(f"Expected status: {expected_status}, got: {response.status_code}")

        return response

    except Exception as e:
        print(f"Error: {str(e)}")
        print(f"❌ Test failed: {test_name}")
        return None

def test_discover_peers(client):
    """Test peer discovery."""
    print("\n=== Testing Peer Discovery ===")

    discovery_data = {
        "discovery_methods": ["mdns", "dht", "bootstrap"],
        "max_peers": 10,
        "timeout_seconds": 5,
        "discovery_namespace": "ipfs-kit-test"
    }

    response = run_test(
        client,
        "/api/v0/mcp/distributed/peers/discover",
        "POST",
        data=discovery_data,
        test_name="Discover Peers"
    )

    return response and response.status_code == 200

def test_list_peers(client):
    """Test listing known peers."""
    print("\n=== Testing List Known Peers ===")

    response = run_test(
        client,
        "/api/v0/mcp/distributed/peers/list",
        "GET",
        test_name="List Known Peers"
    )

    return response and response.status_code == 200

def test_register_node(client):
    """Test node registration."""
    print("\n=== Testing Node Registration ===")

    node_data = {
        "role": "worker",
        "capabilities": ["storage", "compute"],
        "resources": {
            "cpu_count": 4,
            "memory_gb": 8,
            "disk_gb": 100
        },
        "address": "127.0.0.1:4001"
    }

    response = run_test(
        client,
        "/api/v0/mcp/distributed/nodes/register",
        "POST",
        data=node_data,
        test_name="Register Node"
    )

    return response and response.status_code == 200

def test_state_sync(client):
    """Test state synchronization endpoint."""
    print("\n=== Testing State Synchronization ===")

    response = run_test(
        client,
        "/api/v0/mcp/distributed/state/sync2",
        "POST",
        data={},
        test_name="State Synchronization (Simple)"
    )

    return response and response.status_code == 200

def run_all_tests():
    """Run all distributed controller tests."""
    print("\n=== Running Distributed Controller Tests with FastAPI TestClient ===")

    # Create test app
    app = setup_test_app()
    client = TestClient(app)

    success_count = 0
    total_tests = 4

    # Test 1: Discover Peers
    if test_discover_peers(client):
        success_count += 1

    # Test 2: List Peers
    if test_list_peers(client):
        success_count += 1

    # Test 3: Register Node
    if test_register_node(client):
        success_count += 1

    # Test 4: State Sync
    if test_state_sync(client):
        success_count += 1

    # Print summary
    print("\n=== Test Summary ===")
    print(f"Total tests: {total_tests}")
    print(f"Successful: {success_count}")
    print(f"Failed: {total_tests - success_count}")
    print(f"Success rate: {success_count/total_tests:.1%}")

    return success_count == total_tests

if __name__ == "__main__":
    # Run all tests
    success = run_all_tests()
    sys.exit(0 if success else 1)
