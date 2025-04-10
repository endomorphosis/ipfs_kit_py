#!/usr/bin/env python3
"""
Tests for the MCP WebRTC controller implementation using AnyIO.

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
import pytest
from unittest.mock import MagicMock, patch, call, AsyncMock
from pathlib import Path

# Import anyio instead of asyncio
import anyio

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

# AnyIO-specific test class using pytest
@pytest.mark.skipif(not MCP_AVAILABLE, reason="MCP server not available")
class TestMCPWebRTCAnyIO:
    """Tests for the MCP WebRTC controller implementation using AnyIO."""
    
    @pytest.fixture(autouse=True)
    async def setup(self):
        """Set up test environment before each test."""
        # Create a temp directory for the cache
        self.temp_dir = tempfile.mkdtemp(prefix="ipfs_mcp_test_anyio_")
        
        # Mock the IPFS API with WebRTC operation responses
        self.mock_ipfs_api = MagicMock()
        
        # Convert async methods to AsyncMock
        self.mock_ipfs_api.check_webrtc_dependencies_async = AsyncMock(return_value={
            "success": True,
            "dependencies": {
                "aiortc": True,
                "av": True,
                "opencv-python": True,
                "numpy": True
            },
            "webrtc_available": True
        })
        
        self.mock_ipfs_api.stream_content_webrtc_async = AsyncMock(return_value={
            "success": True,
            "server_id": "server-123",
            "url": "https://localhost:8080/stream/server-123",
            "cid": "QmTest123"
        })
        
        self.mock_ipfs_api.stop_webrtc_streaming_async = AsyncMock(return_value={
            "success": True,
            "server_id": "server-123",
            "status": "stopped"
        })
        
        self.mock_ipfs_api.list_webrtc_connections_async = AsyncMock(return_value={
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
        })
        
        self.mock_ipfs_api.get_webrtc_connection_stats_async = AsyncMock(return_value={
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
        })
        
        self.mock_ipfs_api.close_webrtc_connection_async = AsyncMock(return_value={
            "success": True,
            "connection_id": "conn-123",
            "status": "closed"
        })
        
        self.mock_ipfs_api.close_all_webrtc_connections_async = AsyncMock(return_value={
            "success": True,
            "closed_count": 2,
            "connections": ["conn-123", "conn-456"]
        })
        
        self.mock_ipfs_api.set_webrtc_quality_async = AsyncMock(return_value={
            "success": True,
            "connection_id": "conn-123",
            "quality": "high",
            "previous_quality": "medium"
        })
        
        self.mock_ipfs_api.run_webrtc_benchmark_async = AsyncMock(return_value={
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
        })
        
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
        
        yield
        
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.anyio
    async def test_controller_initialization_async(self):
        """Test that the WebRTC controller initializes correctly."""
        # Verify that the controller is initialized
        assert isinstance(self.webrtc_controller, WebRTCController)
        
        # Verify that it has a reference to the IPFS model
        assert self.webrtc_controller.ipfs_model == self.mcp_server.models["ipfs"]
    
    @pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
    @pytest.mark.anyio
    async def test_check_dependencies_async(self):
        """Test the dependency checking endpoint."""
        # Mock the async version of the method
        self.mock_ipfs_api.check_webrtc_dependencies_async.return_value = {
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
        
        # Patch the controller method to use the async version
        with patch.object(self.webrtc_controller, 'check_dependencies', 
                          side_effect=self.webrtc_controller.check_dependencies_async):
            # Call the dependency checking endpoint
            result = await self.webrtc_controller.check_dependencies_async()
            
            # Verify the result
            assert result["success"] is True
            assert result["webrtc_available"] is True
            assert len(result["dependencies"]) == 4
            assert result["installation_command"] == "pip install aiortc av opencv-python numpy"
            
            # Verify that the async model method was called correctly
            self.mock_ipfs_api.check_webrtc_dependencies_async.assert_called_once()
    
    @pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
    @pytest.mark.anyio
    async def test_stream_content_async(self):
        """Test the content streaming endpoint."""
        # Create stream request
        request = StreamRequest(
            cid="QmTest123",
            address="127.0.0.1",
            port=8080,
            quality="high",
            ice_servers=[{"urls": ["stun:stun.l.google.com:19302"]}],
            benchmark=True
        )
        
        # Patch the controller method to use the async version
        with patch.object(self.webrtc_controller, 'stream_content', 
                          side_effect=self.webrtc_controller.stream_content_async):
            # Call the streaming endpoint
            result = await self.webrtc_controller.stream_content_async(request)
            
            # Verify the result
            assert result["success"] is True
            assert result["server_id"] == "server-123"
            assert result["url"] == "https://localhost:8080/stream/server-123"
            
            # Verify that the async model method was called correctly
            self.mock_ipfs_api.stream_content_webrtc_async.assert_called_with(
                cid="QmTest123",
                listen_address="127.0.0.1",
                port=8080,
                quality="high",
                ice_servers=[{"urls": ["stun:stun.l.google.com:19302"]}],
                enable_benchmark=True
            )
    
    @pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
    @pytest.mark.anyio
    async def test_stop_streaming_async(self):
        """Test the stop streaming endpoint."""
        # Patch the controller method to use the async version
        with patch.object(self.webrtc_controller, 'stop_streaming', 
                          side_effect=self.webrtc_controller.stop_streaming_async):
            # Call the stop streaming endpoint
            result = await self.webrtc_controller.stop_streaming_async("server-123")
            
            # Verify the result
            assert result["success"] is True
            assert result["server_id"] == "server-123"
            assert result["status"] == "stopped"
            
            # Verify that the async model method was called correctly
            self.mock_ipfs_api.stop_webrtc_streaming_async.assert_called_with(server_id="server-123")
    
    @pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
    @pytest.mark.anyio
    async def test_list_connections_async(self):
        """Test the connection listing endpoint."""
        # Patch the controller method to use the async version
        with patch.object(self.webrtc_controller, 'list_connections', 
                          side_effect=self.webrtc_controller.list_connections_async):
            # Call the connection listing endpoint
            result = await self.webrtc_controller.list_connections_async()
            
            # Verify the result
            assert result["success"] is True
            assert len(result["connections"]) == 2
            assert result["connections"][0]["id"] == "conn-123"
            assert result["connections"][1]["id"] == "conn-456"
            
            # Verify that the async model method was called correctly
            self.mock_ipfs_api.list_webrtc_connections_async.assert_called_once()
    
    @pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
    @pytest.mark.anyio
    async def test_get_connection_stats_async(self):
        """Test the connection statistics endpoint."""
        # Patch the controller method to use the async version
        with patch.object(self.webrtc_controller, 'get_connection_stats', 
                          side_effect=self.webrtc_controller.get_connection_stats_async):
            # Call the connection statistics endpoint
            result = await self.webrtc_controller.get_connection_stats_async("conn-123")
            
            # Verify the result
            assert result["success"] is True
            assert result["connection_id"] == "conn-123"
            assert result["stats"]["bandwidth"] == 2500000
            assert result["stats"]["resolution"] == "1280x720"
            
            # Verify that the async model method was called correctly
            self.mock_ipfs_api.get_webrtc_connection_stats_async.assert_called_with(connection_id="conn-123")
    
    @pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
    @pytest.mark.anyio
    async def test_close_connection_async(self):
        """Test the connection closure endpoint."""
        # Patch the controller method to use the async version
        with patch.object(self.webrtc_controller, 'close_connection', 
                          side_effect=self.webrtc_controller.close_connection_async):
            # Call the connection closure endpoint
            result = await self.webrtc_controller.close_connection_async("conn-123")
            
            # Verify the result
            assert result["success"] is True
            assert result["connection_id"] == "conn-123"
            assert result["status"] == "closed"
            
            # Verify that the async model method was called correctly
            self.mock_ipfs_api.close_webrtc_connection_async.assert_called_with(connection_id="conn-123")
    
    @pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
    @pytest.mark.anyio
    async def test_close_all_connections_async(self):
        """Test the close all connections endpoint."""
        # Patch the controller method to use the async version
        with patch.object(self.webrtc_controller, 'close_all_connections', 
                          side_effect=self.webrtc_controller.close_all_connections_async):
            # Call the close all connections endpoint
            result = await self.webrtc_controller.close_all_connections_async()
            
            # Verify the result
            assert result["success"] is True
            assert result["closed_count"] == 2
            assert len(result["connections"]) == 2
            
            # Verify that the async model method was called correctly
            self.mock_ipfs_api.close_all_webrtc_connections_async.assert_called_once()
    
    @pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
    @pytest.mark.anyio
    async def test_set_quality_async(self):
        """Test the quality setting endpoint."""
        # Create quality request
        request = QualityRequest(
            connection_id="conn-123",
            quality="high"
        )
        
        # Patch the controller method to use the async version
        with patch.object(self.webrtc_controller, 'set_quality', 
                          side_effect=self.webrtc_controller.set_quality_async):
            # Call the quality setting endpoint
            result = await self.webrtc_controller.set_quality_async(request)
            
            # Verify the result
            assert result["success"] is True
            assert result["connection_id"] == "conn-123"
            assert result["quality"] == "high"
            assert result["previous_quality"] == "medium"
            
            # Verify that the async model method was called correctly
            self.mock_ipfs_api.set_webrtc_quality_async.assert_called_with(
                connection_id="conn-123",
                quality="high"
            )
    
    @pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
    @pytest.mark.anyio
    async def test_run_benchmark_async(self):
        """Test the benchmark endpoint."""
        # Create benchmark request
        request = BenchmarkRequest(
            cid="QmTest123",
            duration=60,
            format="html",
            output_dir="/tmp/benchmark"
        )
        
        # Patch the controller method to use the async version
        with patch.object(self.webrtc_controller, 'run_benchmark', 
                          side_effect=self.webrtc_controller.run_benchmark_async):
            # Call the benchmark endpoint
            result = await self.webrtc_controller.run_benchmark_async(request)
            
            # Verify the result
            assert result["success"] is True
            assert result["benchmark_id"] == "bench-123"
            assert result["report_path"] == "/tmp/benchmark/report.html"
            assert result["summary"]["cid"] == "QmTest123"
            assert result["summary"]["duration"] == 60
            assert result["summary"]["score"] == 85
            
            # Verify that the async model method was called correctly
            self.mock_ipfs_api.run_webrtc_benchmark_async.assert_called_with(
                cid="QmTest123",
                duration_seconds=60,
                report_format="html",
                output_dir="/tmp/benchmark"
            )
    
    @pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
    @pytest.mark.anyio
    async def test_dependencies_not_available_async(self):
        """Test dependency checking when WebRTC is not available."""
        # Configure the mock response for this specific test
        self.mock_ipfs_api.check_webrtc_dependencies_async.return_value = {
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
        
        # Patch the controller method to use the async version
        with patch.object(self.webrtc_controller, 'check_dependencies', 
                          side_effect=self.webrtc_controller.check_dependencies_async):
            # Call the dependency checking endpoint
            result = await self.webrtc_controller.check_dependencies_async()
            
            # Verify the result
            assert result["success"] is True
            assert result["webrtc_available"] is False
            assert result["dependencies"]["aiortc"] is False
            assert result["dependencies"]["av"] is False
            assert result["installation_command"] == "pip install aiortc av"
    
    @pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
    @pytest.mark.anyio
    async def test_stream_content_error_handling_async(self):
        """Test error handling in the stream content endpoint."""
        # Configure the mock response to simulate an error
        self.mock_ipfs_api.stream_content_webrtc_async.return_value = {
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
        
        # Patch the controller method to use the async version
        with patch.object(self.webrtc_controller, 'stream_content', 
                          side_effect=self.webrtc_controller.stream_content_async):
            # Call the streaming endpoint and expect an exception
            with pytest.raises(Exception) as excinfo:
                await self.webrtc_controller.stream_content_async(request)
            
            # Verify that the exception contains the expected error message
            assert "WebRTC dependencies not available" in str(excinfo.value)
            
            # Verify that the model was called correctly
            self.mock_ipfs_api.stream_content_webrtc_async.assert_called_with(
                cid="QmTest123",
                listen_address="127.0.0.1",  # Default value
                port=8080,  # Default value
                quality="high",
                ice_servers=[{"urls": ["stun:stun.l.google.com:19302"]}],  # Default value
                enable_benchmark=False  # Default value
            )
    
    @pytest.mark.anyio
    async def test_anyio_sleep_integration(self):
        """Test the integration with anyio.sleep."""
        
        # Create a method that uses sleep to simulate network delay
        async def stream_with_delay_async(cid, delay=0.1):
            # Simulate network or processing delay
            await anyio.sleep(delay)
            
            # Mock result
            return {
                "success": True,
                "server_id": "server-123",
                "url": f"https://localhost:8080/stream/{cid}",
                "cid": cid
            }
        
        # Mock implementation
        self.mock_ipfs_api.stream_content_webrtc_async = AsyncMock(side_effect=stream_with_delay_async)
        
        # Create stream request
        request = StreamRequest(
            cid="QmTest123",
            quality="high"
        )
        
        # Call the streaming endpoint with the delayed implementation
        start_time = time.time()
        result = await self.mock_ipfs_api.stream_content_webrtc_async("QmTest123", delay=0.1)
        end_time = time.time()
        
        # Verify the result
        assert result["success"] is True
        assert result["server_id"] == "server-123"
        assert result["cid"] == "QmTest123"
        
        # Verify the delay
        elapsed = end_time - start_time
        assert elapsed >= 0.1, f"Expected delay of at least 0.1s, but got {elapsed}s"

if __name__ == "__main__":
    unittest.main()