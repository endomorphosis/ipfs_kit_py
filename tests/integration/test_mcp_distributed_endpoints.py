"""
Test for the MCP Distributed Controller endpoints.

This module focuses specifically on testing the endpoints identified as untested
in the MCP_COMPREHENSIVE_TEST_REPORT.md:
1. /distributed/status - Get distributed system status
2. /distributed/peers - List distributed peers
3. /distributed/ping - Ping a distributed peer
"""

import json
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

# Try to import FastAPI
try:
    from fastapi import FastAPI, Request, Response, APIRouter
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("FastAPI not available, skipping HTTP tests")

from ipfs_kit_py.mcp.controllers.distributed_controller import DistributedController


@unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
class TestMCPDistributedEndpoints(unittest.TestCase):
    """Test case for the MCP Distributed Controller endpoints."""

    def setUp(self):
        """Set up test environment."""
        # Create a mock IPFS model
        self.mock_ipfs_model = MagicMock()
        
        # Create a Distributed controller with the mock model
        self.controller = DistributedController(self.mock_ipfs_model)
        
        # Create a FastAPI app and test client
        self.app = FastAPI()
        router = APIRouter()
        self.controller.register_routes(router)
        self.app.include_router(router)
        self.client = TestClient(self.app)
        
        # Print all registered routes for debugging
        print("\nRegistered routes:")
        for route in self.app.routes:
            print(f"  {route.methods} {route.path}")

    def test_get_status(self):
        """Test the status endpoint."""
        # Set up mock return value for get_distributed_status
        self.mock_ipfs_model.execute_command.return_value = {
            "success": True,
            "operation": "get_distributed_status",
            "status": "active",
            "role": "master",
            "node_id": "Node123",
            "cluster_id": "Cluster456",
            "peers_count": 3,
            "active_tasks": 5,
            "queued_tasks": 2,
            "resources": {
                "cpu_usage": 45.5,
                "memory_usage": 1200,
                "disk_usage": 50000
            },
            "uptime_seconds": 3600,
            "timestamp": 1712345678
        }
        
        # Make API request
        response = self.client.get("/distributed/status")
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "get_distributed_status")
        self.assertEqual(data["status"], "active")
        self.assertEqual(data["role"], "master")
        self.assertEqual(data["node_id"], "Node123")
        self.assertEqual(data["cluster_id"], "Cluster456")
        self.assertEqual(data["peers_count"], 3)
        self.assertEqual(data["active_tasks"], 5)
        
        # Verify model method was called correctly
        self.mock_ipfs_model.execute_command.assert_called_with(
            command="get_distributed_status",
            args=[],
            params={}
        )
    
    def test_get_peers(self):
        """Test the peers endpoint."""
        # Set up mock return value for get_distributed_peers
        self.mock_ipfs_model.execute_command.return_value = {
            "success": True,
            "operation": "get_distributed_peers",
            "peers": [
                {
                    "id": "Peer1",
                    "address": "/ip4/192.168.1.100/tcp/4001/p2p/Peer1",
                    "role": "worker",
                    "status": "online",
                    "resources": {
                        "cpu_cores": 4,
                        "memory_gb": 8,
                        "disk_gb": 500
                    },
                    "capabilities": ["storage", "compute"],
                    "last_seen": 1712345678
                },
                {
                    "id": "Peer2",
                    "address": "/ip4/192.168.1.101/tcp/4001/p2p/Peer2",
                    "role": "worker",
                    "status": "online",
                    "resources": {
                        "cpu_cores": 8,
                        "memory_gb": 16,
                        "disk_gb": 1000
                    },
                    "capabilities": ["storage", "compute", "transcode"],
                    "last_seen": 1712345679
                }
            ],
            "count": 2,
            "cluster_id": "Cluster456",
            "timestamp": 1712345680
        }
        
        # Make API request
        response = self.client.get("/distributed/peers")
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "get_distributed_peers")
        self.assertEqual(len(data["peers"]), 2)
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["cluster_id"], "Cluster456")
        
        # Verify details of first peer
        peer = data["peers"][0]
        self.assertEqual(peer["id"], "Peer1")
        self.assertEqual(peer["role"], "worker")
        self.assertEqual(peer["status"], "online")
        self.assertEqual(peer["resources"]["cpu_cores"], 4)
        
        # Verify model method was called correctly
        self.mock_ipfs_model.execute_command.assert_called_with(
            command="get_distributed_peers",
            args=[],
            params={}
        )
    
    def test_get_peers_with_status_filter(self):
        """Test the peers endpoint with status filter."""
        # Set up mock return value
        self.mock_ipfs_model.execute_command.return_value = {
            "success": True,
            "operation": "get_distributed_peers",
            "peers": [
                {
                    "id": "Peer1",
                    "address": "/ip4/192.168.1.100/tcp/4001/p2p/Peer1",
                    "role": "worker",
                    "status": "online",
                    "last_seen": 1712345678
                }
            ],
            "count": 1,
            "cluster_id": "Cluster456",
            "timestamp": 1712345680
        }
        
        # Make API request with status filter
        response = self.client.get("/distributed/peers?status=online")
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["peers"]), 1)
        
        # Verify model method was called with correct parameters
        self.mock_ipfs_model.execute_command.assert_called_with(
            command="get_distributed_peers",
            args=[],
            params={"status": "online"}
        )
    
    def test_ping_peer(self):
        """Test the ping peer endpoint."""
        # Set up mock return value for ping_distributed_peer
        self.mock_ipfs_model.execute_command.return_value = {
            "success": True,
            "operation": "ping_distributed_peer",
            "peer_id": "Peer1",
            "reachable": True,
            "latency_ms": 25.5,
            "hops": 1,
            "timestamp": 1712345680
        }
        
        # Make API request
        response = self.client.get("/distributed/ping/Peer1")
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "ping_distributed_peer")
        self.assertEqual(data["peer_id"], "Peer1")
        self.assertTrue(data["reachable"])
        self.assertEqual(data["latency_ms"], 25.5)
        self.assertEqual(data["hops"], 1)
        
        # Verify model method was called correctly
        self.mock_ipfs_model.execute_command.assert_called_with(
            command="ping_distributed_peer",
            args=["Peer1"],
            params={}
        )
    
    def test_error_handling(self):
        """Test error handling in Distributed controller."""
        # Set up mock to raise an exception
        self.mock_ipfs_model.execute_command.side_effect = Exception("Test error")
        
        # Make API request
        response = self.client.get("/distributed/status")
        
        # Verify response is an error response
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("error", data)
        self.assertIn("Test error", data["error"])


if __name__ == "__main__":
    unittest.main()