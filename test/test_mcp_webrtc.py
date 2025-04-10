#!/usr/bin/env python3
"""
Tests for the MCP WebRTC controller implementation.

These tests verify that:
1. The WebRTC controller initializes correctly
2. Dependency checking works as expected
3. Streaming operations function properly
4. Connection management works correctly
5. Performance benchmarking is working
6. Quality adjustment is functional
"""

import os
import sys
import json
import time
import tempfile
import unittest
from unittest.mock import MagicMock, patch, call
from pathlib import Path

# Ensure ipfs_kit_py is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Try to import FastAPI
try:
    from fastapi import FastAPI, Request, Response, APIRouter
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("FastAPI not available, skipping HTTP tests")

# Import MCP server and components
try:
    from ipfs_kit_py.mcp import MCPServer
    from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
    from ipfs_kit_py.mcp.controllers.webrtc_controller import (
        WebRTCController,
        StreamRequest,
        QualityRequest,
        BenchmarkRequest
    )
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("MCP server not available, skipping tests")

@unittest.skipIf(not MCP_AVAILABLE, "MCP server not available")
class TestMCPWebRTC(unittest.TestCase):
    """Tests for the MCP WebRTC controller implementation."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a temp directory for the cache
        self.temp_dir = tempfile.mkdtemp(prefix="ipfs_mcp_test_")
        
        # Mock the IPFS API with WebRTC operation responses
        self.mock_ipfs_api = MagicMock()
        
        # Setup mock responses for WebRTC operations
        # Dependency check
        self.mock_ipfs_api.check_webrtc_dependencies.return_value = {
            "success": True,
            "dependencies": {
                "aiortc": True,
                "av": True,
                "opencv-python": True,
                "numpy": True
            },
            "webrtc_available": True
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
        
        # Create WebRTC controller instance for testing
        self.webrtc_controller = WebRTCController(self.mcp_server.models["ipfs"])
        
        # Create a FastAPI router for testing
        self.router = APIRouter()
        self.webrtc_controller.register_routes(self.router)
    
    def tearDown(self):
        """Clean up after each test."""
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_controller_initialization(self):
        """Test that the WebRTC controller initializes correctly."""
        # Verify that the controller is initialized
        self.assertIsInstance(self.webrtc_controller, WebRTCController)
        
        # Verify that it has a reference to the IPFS model
        self.assertEqual(self.webrtc_controller.ipfs_model, self.mcp_server.models["ipfs"])
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_check_dependencies(self):
        """Test the dependency checking endpoint."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.check_webrtc_dependencies.return_value = {
            "success": True,
            "dependencies": {
                "aiortc": True,
                "av": True,
                "opencv-python": True,
                "numpy": True
            },
            "webrtc_available": True,
            "installation_command": "pip install aiortc av opencv-python numpy"
        }
        
        # Call the dependency checking endpoint
        result = await self.webrtc_controller.check_dependencies()
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertTrue(result["webrtc_available"])
        self.assertEqual(len(result["dependencies"]), 4)
        self.assertEqual(result["installation_command"], "pip install aiortc av opencv-python numpy")
        
        # Verify that the model was called correctly
        self.mock_ipfs_api.check_webrtc_dependencies.assert_called_once()
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_stream_content(self):
        """Test the content streaming endpoint."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.stream_content_webrtc.return_value = {
            "success": True,
            "server_id": "server-123",
            "url": "https://localhost:8080/stream/server-123",
            "cid": "QmTest123"
        }
        
        # Create stream request
        request = StreamRequest(
            cid="QmTest123",
            address="127.0.0.1",
            port=8080,
            quality="high",
            ice_servers=[{"urls": ["stun:stun.l.google.com:19302"]}],
            benchmark=True
        )
        
        # Call the streaming endpoint
        result = await self.webrtc_controller.stream_content(request)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["server_id"], "server-123")
        self.assertEqual(result["url"], "https://localhost:8080/stream/server-123")
        
        # Verify that the model was called correctly
        self.mock_ipfs_api.stream_content_webrtc.assert_called_with(
            cid="QmTest123",
            listen_address="127.0.0.1",
            port=8080,
            quality="high",
            ice_servers=[{"urls": ["stun:stun.l.google.com:19302"]}],
            enable_benchmark=True
        )
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_stop_streaming(self):
        """Test the stop streaming endpoint."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.stop_webrtc_streaming.return_value = {
            "success": True,
            "server_id": "server-123",
            "status": "stopped"
        }
        
        # Call the stop streaming endpoint
        result = await self.webrtc_controller.stop_streaming("server-123")
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["server_id"], "server-123")
        self.assertEqual(result["status"], "stopped")
        
        # Verify that the model was called correctly
        self.mock_ipfs_api.stop_webrtc_streaming.assert_called_with(server_id="server-123")
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_list_connections(self):
        """Test the connection listing endpoint."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.list_webrtc_connections.return_value = {
            "success": True,
            "connections": [
                {
                    "id": "conn-123",
                    "peer_id": "peer-123",
                    "cid": "QmTest123",
                    "start_time": time.time(),
                    "status": "active",
                    "quality": "high",
                    "bandwidth": 2500000  # 2.5 Mbps
                },
                {
                    "id": "conn-456",
                    "peer_id": "peer-456",
                    "cid": "QmTest456",
                    "start_time": time.time(),
                    "status": "active",
                    "quality": "medium",
                    "bandwidth": 1000000  # 1 Mbps
                }
            ]
        }
        
        # Call the connection listing endpoint
        result = await self.webrtc_controller.list_connections()
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(len(result["connections"]), 2)
        self.assertEqual(result["connections"][0]["id"], "conn-123")
        self.assertEqual(result["connections"][1]["id"], "conn-456")
        
        # Verify that the model was called correctly
        self.mock_ipfs_api.list_webrtc_connections.assert_called_once()
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_get_connection_stats(self):
        """Test the connection statistics endpoint."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.get_webrtc_connection_stats.return_value = {
            "success": True,
            "connection_id": "conn-123",
            "stats": {
                "bytes_sent": 1000000,
                "bytes_received": 100000,
                "packets_sent": 1000,
                "packets_received": 100,
                "nack_count": 5,
                "frame_rate": 30,
                "resolution": "1280x720",
                "bandwidth": 2500000,  # 2.5 Mbps
                "jitter": 10,  # ms
                "latency": 50,  # ms
                "packet_loss": 0.1  # 0.1%
            }
        }
        
        # Call the connection statistics endpoint
        result = await self.webrtc_controller.get_connection_stats("conn-123")
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["connection_id"], "conn-123")
        self.assertEqual(result["stats"]["bandwidth"], 2500000)
        self.assertEqual(result["stats"]["resolution"], "1280x720")
        
        # Verify that the model was called correctly
        self.mock_ipfs_api.get_webrtc_connection_stats.assert_called_with(connection_id="conn-123")
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_close_connection(self):
        """Test the connection closure endpoint."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.close_webrtc_connection.return_value = {
            "success": True,
            "connection_id": "conn-123",
            "status": "closed"
        }
        
        # Call the connection closure endpoint
        result = await self.webrtc_controller.close_connection("conn-123")
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["connection_id"], "conn-123")
        self.assertEqual(result["status"], "closed")
        
        # Verify that the model was called correctly
        self.mock_ipfs_api.close_webrtc_connection.assert_called_with(connection_id="conn-123")
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_close_all_connections(self):
        """Test the close all connections endpoint."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.close_all_webrtc_connections.return_value = {
            "success": True,
            "closed_count": 2,
            "connections": ["conn-123", "conn-456"]
        }
        
        # Call the close all connections endpoint
        result = await self.webrtc_controller.close_all_connections()
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["closed_count"], 2)
        self.assertEqual(len(result["connections"]), 2)
        
        # Verify that the model was called correctly
        self.mock_ipfs_api.close_all_webrtc_connections.assert_called_once()
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_set_quality(self):
        """Test the quality setting endpoint."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.set_webrtc_quality.return_value = {
            "success": True,
            "connection_id": "conn-123",
            "quality": "high",
            "previous_quality": "medium"
        }
        
        # Create quality request
        request = QualityRequest(
            connection_id="conn-123",
            quality="high"
        )
        
        # Call the quality setting endpoint
        result = await self.webrtc_controller.set_quality(request)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["connection_id"], "conn-123")
        self.assertEqual(result["quality"], "high")
        self.assertEqual(result["previous_quality"], "medium")
        
        # Verify that the model was called correctly
        self.mock_ipfs_api.set_webrtc_quality.assert_called_with(
            connection_id="conn-123",
            quality="high"
        )
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_run_benchmark(self):
        """Test the benchmark endpoint."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.run_webrtc_benchmark.return_value = {
            "success": True,
            "benchmark_id": "bench-123",
            "report_path": "/tmp/benchmark/report.html",
            "summary": {
                "cid": "QmTest123",
                "duration": 60,
                "average_bandwidth": 2500000,  # 2.5 Mbps
                "peak_bandwidth": 3500000,  # 3.5 Mbps
                "average_frame_rate": 29.7,
                "dropped_frames": 5,
                "latency": {
                    "min": 45,  # ms
                    "max": 120,  # ms
                    "avg": 52  # ms
                },
                "packet_loss": 0.2,  # 0.2%
                "score": 85  # Quality score out of 100
            }
        }
        
        # Create benchmark request
        request = BenchmarkRequest(
            cid="QmTest123",
            duration=60,
            format="html",
            output_dir="/tmp/benchmark"
        )
        
        # Call the benchmark endpoint
        result = await self.webrtc_controller.run_benchmark(request)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["benchmark_id"], "bench-123")
        self.assertEqual(result["report_path"], "/tmp/benchmark/report.html")
        self.assertEqual(result["summary"]["cid"], "QmTest123")
        self.assertEqual(result["summary"]["duration"], 60)
        self.assertEqual(result["summary"]["score"], 85)
        
        # Verify that the model was called correctly
        self.mock_ipfs_api.run_webrtc_benchmark.assert_called_with(
            cid="QmTest123",
            duration_seconds=60,
            report_format="html",
            output_dir="/tmp/benchmark"
        )
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_dependencies_not_available(self):
        """Test dependency checking when WebRTC is not available."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.check_webrtc_dependencies.return_value = {
            "success": True,
            "dependencies": {
                "aiortc": False,
                "av": False,
                "opencv-python": True,
                "numpy": True
            },
            "webrtc_available": False,
            "installation_command": "pip install aiortc av"
        }
        
        # Call the dependency checking endpoint
        result = await self.webrtc_controller.check_dependencies()
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertFalse(result["webrtc_available"])
        self.assertFalse(result["dependencies"]["aiortc"])
        self.assertFalse(result["dependencies"]["av"])
        self.assertEqual(result["installation_command"], "pip install aiortc av")
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_get_status(self):
        """Test the WebRTC status endpoint."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.get_webrtc_status.return_value = {
            "success": True,
            "status": "active",
            "active_connections": 2,
            "total_connections": 10,
            "uptime_seconds": 3600,
            "resources": {
                "cpu_usage": 15.2,  # percentage
                "memory_usage": 128.5,  # MB
                "bandwidth_usage": 5.5  # Mbps
            },
            "timestamp": time.time()
        }
        
        # Call the status endpoint
        result = await self.webrtc_controller.get_status()
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "active")
        self.assertEqual(result["active_connections"], 2)
        self.assertEqual(result["total_connections"], 10)
        self.assertEqual(result["resources"]["cpu_usage"], 15.2)
        
        # Verify that the model was called correctly
        self.mock_ipfs_api.get_webrtc_status.assert_called_once()
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_get_peers(self):
        """Test the WebRTC peers endpoint."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.get_webrtc_peers.return_value = {
            "success": True,
            "peers": [
                {
                    "id": "peer-123",
                    "address": "192.168.1.100",
                    "connections": 2,
                    "first_seen": time.time() - 3600,  # 1 hour ago
                    "last_seen": time.time(),
                    "capabilities": ["video", "audio", "data"],
                    "status": "connected"
                },
                {
                    "id": "peer-456",
                    "address": "192.168.1.101",
                    "connections": 1,
                    "first_seen": time.time() - 7200,  # 2 hours ago
                    "last_seen": time.time() - 600,  # 10 minutes ago
                    "capabilities": ["video", "data"],
                    "status": "disconnected"
                }
            ],
            "count": 2,
            "timestamp": time.time()
        }
        
        # Call the peers endpoint
        result = await self.webrtc_controller.get_peers()
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(len(result["peers"]), 2)
        self.assertEqual(result["peers"][0]["id"], "peer-123")
        self.assertEqual(result["peers"][0]["status"], "connected")
        self.assertEqual(result["peers"][1]["id"], "peer-456")
        self.assertEqual(result["peers"][1]["status"], "disconnected")
        self.assertEqual(result["count"], 2)
        
        # Verify that the model was called correctly
        self.mock_ipfs_api.get_webrtc_peers.assert_called_once()
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    async def test_stream_content_error_handling(self):
        """Test error handling in the stream content endpoint."""
        # Configure the mock response to simulate an error
        self.mock_ipfs_api.stream_content_webrtc.return_value = {
            "success": False,
            "error": "WebRTC dependencies not available",
            "dependencies": {
                "aiortc": False,
                "av": False
            }
        }
        
        # Create stream request
        request = StreamRequest(
            cid="QmTest123",
            quality="high"
        )
        
        # Call the streaming endpoint and expect an exception
        try:
            await self.webrtc_controller.stream_content(request)
            self.fail("HTTPException should have been raised")
        except Exception as e:
            # Verify that the exception contains the expected error message
            self.assertIn("WebRTC dependencies not available", str(e))
        
        # Verify that the model was called correctly
        self.mock_ipfs_api.stream_content_webrtc.assert_called_with(
            cid="QmTest123",
            listen_address="127.0.0.1",  # Default value
            port=8080,  # Default value
            quality="high",
            ice_servers=[{"urls": ["stun:stun.l.google.com:19302"]}],  # Default value
            enable_benchmark=False  # Default value
        )

if __name__ == "__main__":
    unittest.main()