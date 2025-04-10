#!/usr/bin/env python3
"""
Tests for the MCP Distributed controller implementation.

These tests verify that:
1. The Distributed controller initializes correctly
2. Peer discovery endpoints work as expected
3. Node registration functionality works correctly
4. Cluster-wide cache operations work as intended
5. State operations and synchronization function properly
6. Distributed task submission and management work correctly
7. WebSocket event system functions as expected
"""

import os
import sys
import json
import time
import tempfile
import unittest
import asyncio
from unittest.mock import MagicMock, patch, call, AsyncMock
from pathlib import Path

# Ensure ipfs_kit_py is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Try to import FastAPI
try:
    from fastapi import FastAPI, Request, Response, APIRouter, WebSocket
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("FastAPI not available, skipping HTTP tests")

# Import MCP server and components
try:
    from ipfs_kit_py.mcp import MCPServer
    from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
    from ipfs_kit_py.mcp.controllers.distributed_controller import (
        DistributedController, 
        PeerDiscoveryRequest,
        ClusterCacheRequest,
        ClusterStateRequest,
        NodeRegistrationRequest,
        DistributedTaskRequest
    )
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("MCP server not available, skipping tests")

class MockWebSocket:
    """Mock WebSocket for testing WebSocket endpoints."""
    
    def __init__(self):
        self.sent_messages = []
        self.client_state = 1  # Connected
        self.received_queue = asyncio.Queue()
        
    async def accept(self):
        return
        
    async def send_json(self, data):
        self.sent_messages.append(data)
        
    async def send_text(self, text):
        self.sent_messages.append(text)
        
    async def receive_json(self):
        # Return a default subscription request
        return {
            "type": "subscribe",
            "events": ["node_status", "task_status"]
        }
        
    async def receive_text(self):
        # If there's something in the queue, return it
        if not self.received_queue.empty():
            return await self.received_queue.get()
        # Otherwise raise an exception to simulate disconnection
        raise Exception("Connection closed")
        
    async def close(self):
        self.client_state = 0  # Disconnected
        
    def add_received_message(self, message):
        """Add a message to the receive queue for testing."""
        self.received_queue.put_nowait(message)

@unittest.skipIf(not MCP_AVAILABLE, "MCP server not available")
class TestMCPDistributed(unittest.TestCase):
    """Tests for the MCP Distributed controller implementation."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a temp directory for the cache
        self.temp_dir = tempfile.mkdtemp(prefix="ipfs_mcp_test_")
        
        # Mock the IPFS API with distributed operation responses
        self.mock_ipfs_api = MagicMock()
        
        # Setup mock responses for distributed operations
        # Peer discovery
        self.mock_ipfs_api.execute_command.return_value = {
            "success": True,
            "operation": "execute_command",
            "peers": [
                {"id": "Peer1", "address": "/ip4/127.0.0.1/tcp/4001/p2p/Peer1", "role": "worker"},
                {"id": "Peer2", "address": "/ip4/192.168.1.100/tcp/4001/p2p/Peer2", "role": "leecher"}
            ],
            "discovery_methods_used": ["mdns", "dht"]
        }
        
        # Node registration
        self.mock_ipfs_api.execute_command.return_value = {
            "success": True,
            "operation": "execute_command",
            "node_id": "Node1",
            "role": "worker",
            "status": "online",
            "cluster_id": "Cluster1",
            "master_address": "/ip4/127.0.0.1/tcp/9096/p2p/Master1"
        }
        
        # Initialize the MCP server
        self.mcp_server = MCPServer(
            debug_mode=True,
            isolation_mode=True,
            persistence_path=self.temp_dir
        )
        
        # Replace the ipfs_kit instance with our mock
        self.mcp_server.ipfs_kit = self.mock_ipfs_api
        
        # Reinitialize the IPFS model with our mock
        self.mcp_server.models["ipfs"] = IPFSModel(self.mock_ipfs_api, self.mcp_server.persistence)
        
        # Create Distributed controller instance for testing
        self.distributed_controller = DistributedController(self.mcp_server.models["ipfs"])
        
        # Create a FastAPI router for testing
        self.router = APIRouter()
        self.distributed_controller.register_routes(self.router)
    
    def tearDown(self):
        """Clean up after each test."""
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_controller_initialization(self):
        """Test that the Distributed controller initializes correctly."""
        # Verify that the controller is initialized
        self.assertIsInstance(self.distributed_controller, DistributedController)
        
        # Verify that it has a reference to the IPFS model
        self.assertEqual(self.distributed_controller.ipfs_model, self.mcp_server.models["ipfs"])
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_discover_peers(self):
        """Test the peer discovery endpoint."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.execute_command.return_value = {
            "success": True,
            "operation": "discover_peers",
            "peers": [
                {"id": "Peer1", "address": "/ip4/127.0.0.1/tcp/4001/p2p/Peer1", "role": "worker"},
                {"id": "Peer2", "address": "/ip4/192.168.1.100/tcp/4001/p2p/Peer2", "role": "leecher"}
            ],
            "discovery_methods_used": ["mdns", "dht"]
        }
        
        # Create peer discovery request
        request = PeerDiscoveryRequest(
            discovery_methods=["mdns", "dht", "bootstrap"],
            max_peers=5,
            timeout_seconds=10,
            discovery_namespace="test-cluster"
        )
        
        # Call the peer discovery endpoint
        result = await self.distributed_controller.discover_peers(request)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(len(result["peers"]), 2)
        self.assertEqual(result["total_peers_found"], 2)
        self.assertEqual(result["discovery_methods_used"], ["mdns", "dht"])
        
        # Verify that the model was called correctly
        self.mock_ipfs_api.execute_command.assert_called_with(
            command="discover_peers",
            args=[],
            params={
                "discovery_methods": ["mdns", "dht", "bootstrap"],
                "max_peers": 5,
                "timeout_seconds": 10,
                "discovery_namespace": "test-cluster"
            }
        )
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_register_node(self):
        """Test the node registration endpoint."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.execute_command.return_value = {
            "success": True,
            "operation": "register_node",
            "node_id": "Node1",
            "role": "worker",
            "status": "online",
            "cluster_id": "Cluster1",
            "master_address": "/ip4/127.0.0.1/tcp/9096/p2p/Master1",
            "peers": [
                {"id": "Peer1", "address": "/ip4/127.0.0.1/tcp/4001/p2p/Peer1", "role": "master"}
            ]
        }
        
        # Create node registration request
        request = NodeRegistrationRequest(
            role="worker",
            capabilities=["storage", "compute"],
            resources={"cpu_cores": 4, "memory_gb": 8},
            address="/ip4/192.168.1.101/tcp/4001"
        )
        
        # Call the node registration endpoint
        result = await self.distributed_controller.register_node(request)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["node_id"], "Node1")
        self.assertEqual(result["role"], "worker")
        self.assertEqual(result["status"], "online")
        self.assertEqual(result["cluster_id"], "Cluster1")
        self.assertEqual(result["master_address"], "/ip4/127.0.0.1/tcp/9096/p2p/Master1")
        self.assertEqual(len(result["peers"]), 1)
        
        # Verify that the model was called correctly
        self.mock_ipfs_api.execute_command.assert_called_with(
            command="register_node",
            args=[],
            params={
                "node_id": None,
                "role": "worker",
                "capabilities": ["storage", "compute"],
                "resources": {"cpu_cores": 4, "memory_gb": 8},
                "address": "/ip4/192.168.1.101/tcp/4001",
                "metadata": None
            }
        )
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_cache_operation(self):
        """Test the cluster-wide cache operation endpoint."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.execute_command.return_value = {
            "success": True,
            "operation": "cluster_cache_operation",
            "value": {"config": {"max_connections": 100}},
            "nodes_affected": 3,
            "propagation_status": {
                "Node1": "success",
                "Node2": "success",
                "Node3": "success"
            }
        }
        
        # Create cache operation request
        request = ClusterCacheRequest(
            operation="put",
            key="config",
            value={"max_connections": 100},
            propagate=True,
            ttl_seconds=3600
        )
        
        # Call the cache operation endpoint
        result = await self.distributed_controller.cache_operation(request)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "put")
        self.assertEqual(result["key"], "config")
        self.assertEqual(result["value"], {"config": {"max_connections": 100}})
        self.assertEqual(result["nodes_affected"], 3)
        self.assertEqual(len(result["propagation_status"]), 3)
        
        # Verify that the model was called correctly
        self.mock_ipfs_api.execute_command.assert_called_with(
            command="cluster_cache_operation",
            args=["put"],
            params={
                "key": "config",
                "value": {"max_connections": 100},
                "metadata": None,
                "propagate": True,
                "ttl_seconds": 3600
            }
        )
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_state_operation(self):
        """Test the cluster state operation endpoint."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.execute_command.return_value = {
            "success": True,
            "operation": "cluster_state_operation",
            "value": {"status": "online"},
            "update_count": 1
        }
        
        # Create state operation request
        request = ClusterStateRequest(
            operation="update",
            path="nodes.Node1.status",
            value="online"
        )
        
        # Call the state operation endpoint
        result = await self.distributed_controller.state_operation(request)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "update")
        self.assertEqual(result["path"], "nodes.Node1.status")
        self.assertEqual(result["value"], {"status": "online"})
        self.assertEqual(result["update_count"], 1)
        
        # Verify that the model was called correctly
        self.mock_ipfs_api.execute_command.assert_called_with(
            command="cluster_state_operation",
            args=["update"],
            params={
                "path": "nodes.Node1.status",
                "value": "online",
                "query_filter": None,
                "subscription_id": None
            }
        )
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_submit_task(self):
        """Test the distributed task submission endpoint."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.execute_command.return_value = {
            "success": True,
            "operation": "submit_distributed_task",
            "task_id": "Task1",
            "status": "pending",
            "assigned_to": "Node2"
        }
        
        # Create task submission request
        request = DistributedTaskRequest(
            task_type="process_dataset",
            parameters={"cid": "QmDataset123", "algorithm": "feature_extraction"},
            priority=8,
            target_role="worker"
        )
        
        # Call the task submission endpoint
        result = await self.distributed_controller.submit_task(request)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["task_id"], "Task1")
        self.assertEqual(result["task_type"], "process_dataset")
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["assigned_to"], "Node2")
        
        # Verify that the model was called correctly
        self.mock_ipfs_api.execute_command.assert_called_with(
            command="submit_distributed_task",
            args=["process_dataset"],
            params={
                "parameters": {"cid": "QmDataset123", "algorithm": "feature_extraction"},
                "priority": 8,
                "target_role": "worker",
                "target_node": None,
                "timeout_seconds": None
            }
        )
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_get_task_status(self):
        """Test the task status endpoint."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.execute_command.return_value = {
            "success": True,
            "operation": "get_distributed_task_status",
            "task_id": "Task1",
            "task_type": "process_dataset",
            "status": "processing",
            "assigned_to": "Node2",
            "progress": 50.0
        }
        
        # Call the task status endpoint
        result = await self.distributed_controller.get_task_status("Task1")
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["task_id"], "Task1")
        self.assertEqual(result["task_type"], "process_dataset")
        self.assertEqual(result["status"], "processing")
        self.assertEqual(result["assigned_to"], "Node2")
        self.assertEqual(result["progress"], 50.0)
        
        # Verify that the model was called correctly
        self.mock_ipfs_api.execute_command.assert_called_with(
            command="get_distributed_task_status",
            args=["Task1"],
            params={}
        )
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_cancel_task(self):
        """Test the task cancellation endpoint."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.execute_command.return_value = {
            "success": True,
            "operation": "cancel_distributed_task",
            "task_id": "Task1",
            "task_type": "process_dataset",
            "status": "cancelled",
            "assigned_to": "Node2"
        }
        
        # Call the task cancellation endpoint
        result = await self.distributed_controller.cancel_task("Task1")
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["task_id"], "Task1")
        self.assertEqual(result["task_type"], "process_dataset")
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(result["assigned_to"], "Node2")
        
        # Verify that the model was called correctly
        self.mock_ipfs_api.execute_command.assert_called_with(
            command="cancel_distributed_task",
            args=["Task1"],
            params={}
        )
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_list_tasks(self):
        """Test the task listing endpoint."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.execute_command.return_value = {
            "success": True,
            "operation": "list_distributed_tasks",
            "tasks": [
                {
                    "task_id": "Task1",
                    "task_type": "process_dataset",
                    "status": "processing",
                    "assigned_to": "Node2",
                    "progress": 50.0
                },
                {
                    "task_id": "Task2",
                    "task_type": "train_model",
                    "status": "pending",
                    "assigned_to": None,
                    "progress": 0.0
                }
            ],
            "total_count": 2,
            "active_count": 1,
            "pending_count": 1
        }
        
        # Call the task listing endpoint
        result = await self.distributed_controller.list_tasks(
            filter_status="processing",
            filter_type=None,
            filter_node=None
        )
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(len(result["tasks"]), 2)
        self.assertEqual(result["total_count"], 2)
        self.assertEqual(result["active_count"], 1)
        self.assertEqual(result["pending_count"], 1)
        
        # Verify that the model was called correctly
        self.mock_ipfs_api.execute_command.assert_called_with(
            command="list_distributed_tasks",
            args=[],
            params={
                "filter_status": "processing",
                "filter_type": None,
                "filter_node": None
            }
        )
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_websocket_events(self):
        """Test the WebSocket events endpoint."""
        # Create a mock websocket
        websocket = MockWebSocket()
        
        # Setup event listener mock
        self.mock_ipfs_api.add_event_listener = MagicMock()
        self.mock_ipfs_api.remove_event_listener = MagicMock()
        
        # Configure the event subscription response
        self.mock_ipfs_api.execute_command.return_value = {
            "success": True,
            "operation": "register_event_subscription",
            "subscription_id": "sub-123"
        }
        
        # Run the WebSocket handler in a separate task
        task = asyncio.create_task(
            self.distributed_controller.cluster_events_websocket(websocket)
        )
        
        # Give the task time to start
        await asyncio.sleep(0.1)
        
        # Verify that subscription confirmation was sent
        self.assertEqual(len(websocket.sent_messages), 1)
        self.assertEqual(websocket.sent_messages[0]["type"], "subscription_confirmed")
        
        # Verify that the event listener was added
        self.mock_ipfs_api.add_event_listener.assert_called_once()
        
        # Add a ping message to test handling
        websocket.add_received_message("ping")
        await asyncio.sleep(0.1)
        
        # Verify pong response
        self.assertEqual(len(websocket.sent_messages), 2)
        self.assertEqual(websocket.sent_messages[1], "pong")
        
        # Add a subscription update message
        websocket.add_received_message(json.dumps({
            "type": "update_subscription",
            "params": {
                "events": ["node_status", "task_status", "peer_discovery"]
            }
        }))
        await asyncio.sleep(0.1)
        
        # Verify subscription update was processed
        self.assertEqual(len(websocket.sent_messages), 3)
        self.assertEqual(websocket.sent_messages[2]["type"], "subscription_updated")
        
        # Verify that the subscription was updated
        self.mock_ipfs_api.execute_command.assert_called_with(
            command="update_event_subscription",
            args=[websocket.sent_messages[0]["subscription_id"]],
            params={"events": ["node_status", "task_status", "peer_discovery"]}
        )
        
        # Cancel the task to simulate client disconnect
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # Verify that cleanup was performed
        self.mock_ipfs_api.execute_command.assert_called_with(
            command="unregister_event_subscription",
            args=[websocket.sent_messages[0]["subscription_id"]],
            params={}
        )
        self.mock_ipfs_api.remove_event_listener.assert_called_once()

if __name__ == "__main__":
    unittest.main()