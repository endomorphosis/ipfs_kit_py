#!/usr/bin/env python3
"""
Simple test script to verify the libp2p fallback works correctly with a mock FastAPI request
"""

import sys
import json
import anyio
import random
import uuid
from fastapi import Request, Response, APIRouter
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Import the model and controller classes
from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
from ipfs_kit_py.mcp.controllers.distributed_controller import DistributedController

async def test_libp2p_api_fallback():
    """Test that our libp2p fallback implementation works through the API endpoints."""
    print("Creating test FastAPI app...")
    app = FastAPI()
    
    # Create model and controller
    print("Initializing model and controller...")
    model = IPFSModel()
    controller = DistributedController(model)
    
    # Create router and register controller routes
    router = APIRouter()
    controller.register_routes(router)
    
    # Include router in app
    app.include_router(router)
    
    # Create test client
    client = TestClient(app)
    
    # Test discover_peers endpoint
    print("\nTesting /distributed/peers/discover endpoint...")
    discover_response = client.post(
        "/distributed/peers/discover",
        json={
            "discovery_methods": ["mdns", "dht", "bootstrap"],
            "max_peers": 10,
            "timeout_seconds": 5
        }
    )
    discover_data = discover_response.json()
    print(f"Status code: {discover_response.status_code}")
    print(f"Success: {discover_data.get('success', False)}")
    print(f"Peers found: {len(discover_data.get('peers', []))}")
    if "peers" in discover_data and discover_data["peers"]:
        print(f"Sample peer: {discover_data['peers'][0]}")
    
    # Test list_known_peers endpoint
    print("\nTesting /distributed/peers/list endpoint...")
    list_response = client.get("/distributed/peers/list")
    list_data = list_response.json()
    print(f"Status code: {list_response.status_code}")
    print(f"Success: {list_data.get('success', False)}")
    print(f"Peers found: {len(list_data.get('peers', []))}")
    if "peers" in list_data and list_data["peers"]:
        print(f"Sample peer: {list_data['peers'][0]}")
    
    # Test register_node endpoint
    print("\nTesting /distributed/nodes/register endpoint...")
    node_id = f"test_node_{uuid.uuid4()}"
    register_response = client.post(
        "/distributed/nodes/register",
        json={
            "node_id": node_id,
            "role": "worker",
            "capabilities": ["storage", "compute"],
            "resources": {
                "cpu_count": 4,
                "memory_gb": 8,
                "disk_gb": 100
            },
            "address": "127.0.0.1:4001"
        }
    )
    register_data = register_response.json()
    print(f"Status code: {register_response.status_code}")
    print(f"Success: {register_data.get('success', False)}")
    print(f"Node ID: {register_data.get('node_id')}")
    print(f"Role: {register_data.get('role')}")
    print(f"Status: {register_data.get('status')}")
    print(f"Cluster ID: {register_data.get('cluster_id')}")
    print(f"Peers: {len(register_data.get('peers', []))}")
    
    # Test simple_sync endpoint (which should always work)
    print("\nTesting /distributed/state/sync2 endpoint...")
    sync_response = client.post("/distributed/state/sync2")
    sync_data = sync_response.json()
    print(f"Status code: {sync_response.status_code}")
    print(f"Success: {sync_data.get('success', False)}")
    print(f"Sync type: {sync_data.get('sync_type')}")
    print(f"Nodes synced: {sync_data.get('nodes_synced')}")
    
    # Return True if all tests passed
    all_success = (
        discover_response.status_code == 200 and 
        list_response.status_code == 200 and 
        register_response.status_code == 200 and
        sync_response.status_code == 200
    )
    return all_success

if __name__ == "__main__":
    # Run the test
    result = anyio.run(test_libp2p_api_fallback())
    
    if result:
        print("\n✅ All API endpoints were successfully tested")
        sys.exit(0)
    else: 
        print("\n❌ One or more API endpoint tests failed")
        sys.exit(1)
