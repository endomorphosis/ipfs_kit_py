import unittest
from unittest.mock import MagicMock, patch
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import json


class TestMCPDiscoveryController(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        # Create mock MCP Discovery model
        self.mock_discovery_model = MagicMock()
        
        # Import the controller
        from ipfs_kit_py.mcp.controllers.mcp_discovery_controller import MCPDiscoveryController
        
        # Create controller with mock
        self.controller = MCPDiscoveryController(self.mock_discovery_model)
        
        # Set up FastAPI router and app
        self.router = APIRouter()
        self.controller.register_routes(self.router)
        self.app = FastAPI()
        self.app.include_router(self.router)
        self.client = TestClient(self.app)
    
    def test_initialization(self):
        """Test controller initialization."""
        self.assertEqual(self.controller.discovery_model, self.mock_discovery_model)
    
    def test_route_registration(self):
        """Test route registration."""
        route_paths = [route.path for route in self.router.routes]
        self.assertIn("/discovery/status", route_paths)
        self.assertIn("/discovery/announce", route_paths)
        self.assertIn("/discovery/find", route_paths)
        self.assertIn("/discovery/list", route_paths)
    
    def test_handle_status_request(self):
        """Test handling status request."""
        # Configure mock response
        self.mock_discovery_model.get_status.return_value = {
            "success": True,
            "active": True,
            "protocols": ["mDNS", "DHT", "PubSub"],
            "peer_id": "QmYourPeerId",
            "connected_peers": 5,
            "known_servers": 10,
            "uptime_seconds": 3600
        }
        
        # Send request
        response = self.client.get("/discovery/status")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertTrue(response_data["active"])
        self.assertEqual(response_data["peer_id"], "QmYourPeerId")
        self.assertEqual(response_data["connected_peers"], 5)
        
        # Verify model was called
        self.mock_discovery_model.get_status.assert_called_once()
    
    def test_handle_announce_request(self):
        """Test handling announce request."""
        # Configure mock response
        self.mock_discovery_model.announce_server.return_value = {
            "success": True,
            "server_id": "server-123",
            "peer_id": "QmYourPeerId",
            "protocols": ["HTTP", "WebSocket"],
            "addresses": ["/ip4/127.0.0.1/tcp/9001", "/ip4/192.168.1.100/tcp/9001"],
            "timestamp": 1672531200,
            "ttl_seconds": 3600
        }
        
        # Create request
        request_data = {
            "protocols": ["HTTP", "WebSocket"],
            "addresses": ["/ip4/127.0.0.1/tcp/9001", "/ip4/192.168.1.100/tcp/9001"],
            "ttl_seconds": 3600
        }
        
        # Send request
        response = self.client.post("/discovery/announce", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["server_id"], "server-123")
        self.assertEqual(response_data["peer_id"], "QmYourPeerId")
        
        # Verify model was called with correct parameters
        self.mock_discovery_model.announce_server.assert_called_once_with(
            protocols=["HTTP", "WebSocket"],
            addresses=["/ip4/127.0.0.1/tcp/9001", "/ip4/192.168.1.100/tcp/9001"],
            ttl_seconds=3600
        )
    
    def test_handle_find_request(self):
        """Test handling find request."""
        # Configure mock response
        self.mock_discovery_model.find_servers.return_value = {
            "success": True,
            "results": [
                {
                    "server_id": "server-123",
                    "peer_id": "QmPeer1",
                    "protocols": ["HTTP", "WebSocket"],
                    "addresses": ["/ip4/192.168.1.101/tcp/9001"],
                    "last_seen": 1672531200,
                    "latency_ms": 15
                },
                {
                    "server_id": "server-456",
                    "peer_id": "QmPeer2",
                    "protocols": ["HTTP"],
                    "addresses": ["/ip4/192.168.1.102/tcp/9001"],
                    "last_seen": 1672531100,
                    "latency_ms": 25
                }
            ],
            "count": 2,
            "search_time_ms": 50.5
        }
        
        # Create request
        request_data = {
            "protocol": "HTTP",
            "max_results": 10,
            "timeout_ms": 1000
        }
        
        # Send request
        response = self.client.post("/discovery/find", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(len(response_data["results"]), 2)
        self.assertEqual(response_data["results"][0]["server_id"], "server-123")
        self.assertEqual(response_data["results"][1]["peer_id"], "QmPeer2")
        
        # Verify model was called with correct parameters
        self.mock_discovery_model.find_servers.assert_called_once_with(
            protocol="HTTP",
            max_results=10,
            timeout_ms=1000
        )
    
    def test_handle_list_request(self):
        """Test handling list request."""
        # Configure mock response
        self.mock_discovery_model.list_known_servers.return_value = {
            "success": True,
            "servers": [
                {
                    "server_id": "server-123",
                    "peer_id": "QmPeer1",
                    "protocols": ["HTTP", "WebSocket"],
                    "addresses": ["/ip4/192.168.1.101/tcp/9001"],
                    "last_seen": 1672531200,
                    "is_local": True
                },
                {
                    "server_id": "server-456",
                    "peer_id": "QmPeer2",
                    "protocols": ["HTTP"],
                    "addresses": ["/ip4/192.168.1.102/tcp/9001"],
                    "last_seen": 1672531100,
                    "is_local": False
                }
            ],
            "count": 2,
            "local_count": 1,
            "remote_count": 1
        }
        
        # Send request
        response = self.client.get("/discovery/list")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(len(response_data["servers"]), 2)
        self.assertEqual(response_data["count"], 2)
        self.assertEqual(response_data["local_count"], 1)
        self.assertEqual(response_data["servers"][0]["server_id"], "server-123")
        self.assertTrue(response_data["servers"][0]["is_local"])
        
        # Verify model was called
        self.mock_discovery_model.list_known_servers.assert_called_once()
    
    def test_handle_connect_request(self):
        """Test handling connect request."""
        # Configure mock response
        self.mock_discovery_model.connect_to_server.return_value = {
            "success": True,
            "server_id": "server-123",
            "peer_id": "QmPeer1",
            "protocols": ["HTTP", "WebSocket"],
            "connection_established": True,
            "latency_ms": 15,
            "connection_time_ms": 50.5
        }
        
        # Create request
        request_data = {
            "server_id": "server-123"
        }
        
        # Send request
        response = self.client.post("/discovery/connect", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["server_id"], "server-123")
        self.assertTrue(response_data["connection_established"])
        
        # Verify model was called with correct parameters
        self.mock_discovery_model.connect_to_server.assert_called_once_with(
            server_id="server-123"
        )
    
    # Test error cases
    def test_handle_find_error(self):
        """Test handling find error."""
        # Configure mock to return error
        self.mock_discovery_model.find_servers.return_value = {
            "success": False,
            "error": "Discovery service unavailable",
            "error_type": "DiscoveryError"
        }
        
        # Create request
        request_data = {
            "protocol": "HTTP",
            "max_results": 10,
            "timeout_ms": 1000
        }
        
        # Send request
        response = self.client.post("/discovery/find", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 500)
        response_data = response.json()
        self.assertEqual(response_data["detail"]["error"], "Discovery service unavailable")
        self.assertEqual(response_data["detail"]["error_type"], "DiscoveryError")
    
    def test_handle_connect_error(self):
        """Test handling connect error."""
        # Configure mock to return error
        self.mock_discovery_model.connect_to_server.return_value = {
            "success": False,
            "error": "Server not found",
            "error_type": "ServerNotFoundError",
            "server_id": "server-unknown"
        }
        
        # Create request
        request_data = {
            "server_id": "server-unknown"
        }
        
        # Send request
        response = self.client.post("/discovery/connect", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 500)
        response_data = response.json()
        self.assertEqual(response_data["detail"]["error"], "Server not found")
        self.assertEqual(response_data["detail"]["error_type"], "ServerNotFoundError")
    
    def test_handle_validation_error(self):
        """Test handling validation error."""
        # Send request with missing required fields
        response = self.client.post("/discovery/find", json={})
        
        # Check response
        self.assertEqual(response.status_code, 400)
        # Validation errors return detailed information about missing fields
        self.assertIn("detail", response.json())
    
    def test_unavailable_service(self):
        """Test behavior when Discovery service is unavailable."""
        # Set controller to indicate dependencies are not available
        self.controller._has_dependencies = False
        
        # Send request
        response = self.client.get("/discovery/status")
        
        # Check response - should indicate service unavailable
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn("not available", response_data["detail"])