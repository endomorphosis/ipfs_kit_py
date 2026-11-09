"""
Test suite for MCP WebRTC Controller.

This module tests the functionality of the WebRTCController class
which provides HTTP endpoints for WebRTC streaming, connection management,
and resource monitoring.
"""

import pytest
import json
import time
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

# Import the controller class
try:
    from ipfs_kit_py.mcp.controllers.webrtc_controller import WebRTCController
except ImportError:
    # If AnyIO migration has occurred, import from the AnyIO version
    from ipfs_kit_py.mcp.controllers.webrtc_controller_anyio import WebRTCController


class TestWebRTCControllerInitialization:
    """Test initialization and route registration of WebRTCController."""

    def test_init_with_webrtc_support(self):
        """Test controller initialization with WebRTC support."""
        # Mock WebRTC model
        mock_ipfs_model = MagicMock()
        
        # Mock that WebRTC support is available
        with patch("ipfs_kit_py.mcp.controllers.webrtc_controller.WebRTCController._check_dependencies", 
                  return_value=True):
            controller = WebRTCController(mock_ipfs_model)
            
            # Verify controller is initialized correctly
            assert controller.ipfs_model == mock_ipfs_model
            assert controller._has_dependencies is True
            assert hasattr(controller, "active_servers")
            assert hasattr(controller, "active_connections")
    
    def test_init_without_webrtc_support(self):
        """Test controller initialization without WebRTC support."""
        # Mock WebRTC model
        mock_ipfs_model = MagicMock()
        
        # Mock that WebRTC support is not available
        with patch("ipfs_kit_py.mcp.controllers.webrtc_controller.WebRTCController._check_dependencies", 
                  return_value=False):
            controller = WebRTCController(mock_ipfs_model)
            
            # Verify controller is initialized correctly
            assert controller.ipfs_model == mock_ipfs_model
            assert controller._has_dependencies is False
    
    def test_route_registration(self):
        """Test that all routes are registered correctly."""
        # Mock WebRTC model and router
        mock_ipfs_model = MagicMock()
        mock_router = MagicMock(spec=APIRouter)
        
        # Initialize controller and register routes
        controller = WebRTCController(mock_ipfs_model)
        controller.register_routes(mock_router)
        
        # Verify that add_api_route was called for each endpoint
        expected_routes = [
            # Check routes
            "/webrtc/check",
            
            # Stream management routes
            "/webrtc/stream",
            "/webrtc/stream/stop/{server_id}",
            
            # Connection management routes
            "/webrtc/connections",
            "/webrtc/connections/{connection_id}/stats",
            "/webrtc/connections/{connection_id}/close",
            "/webrtc/connections/close-all",
            "/webrtc/connections/quality",
            
            # Resource monitoring routes
            "/webrtc/stats/resources",
            
            # Benchmark routes
            "/webrtc/benchmark"
        ]
        
        route_calls = [call.args[0] for call in mock_router.add_api_route.call_args_list]
        
        # Verify expected route registrations
        for route in expected_routes:
            assert any(route in call for call in route_calls), f"Route {route} was not registered"


class TestWebRTCController:
    """Test WebRTC streaming and connection operations for WebRTCController."""
    
    @pytest.fixture
    def controller_with_app(self):
        """Create a controller with a FastAPI app for testing HTTP endpoints."""
        # Create FastAPI app and router
        app = FastAPI()
        router = APIRouter()
        
        # Mock IPFS model
        mock_ipfs_model = MagicMock()
        
        # Set up mock operations
        
        # Stream operations
        mock_ipfs_model.start_webrtc_streaming.return_value = {
            "success": True,
            "server_id": "server123",
            "address": "127.0.0.1",
            "port": 8080,
            "content_cid": "testcid",
            "ice_servers": [{"urls": "stun:stun.example.com:19302"}],
            "connection_id": "conn123"
        }
        
        mock_ipfs_model.stop_webrtc_streaming.return_value = {
            "success": True,
            "server_id": "server123",
            "message": "Streaming server stopped successfully"
        }
        
        # Connection operations
        mock_ipfs_model.get_webrtc_connections.return_value = {
            "success": True,
            "connections": [
                {
                    "connection_id": "conn123",
                    "server_id": "server123",
                    "created_at": time.time(),
                    "status": "active",
                    "content_cid": "testcid",
                    "client_info": {"ip": "127.0.0.1", "user_agent": "test-client"}
                }
            ],
            "total": 1
        }
        
        mock_ipfs_model.get_webrtc_connection_stats.return_value = {
            "success": True,
            "connection_id": "conn123",
            "stats": {
                "bytes_sent": 1024,
                "bytes_received": 256,
                "packets_sent": 10,
                "packets_received": 5,
                "bitrate_outgoing": 512000,
                "bitrate_incoming": 128000,
                "latency_ms": 15,
                "packet_loss_percentage": 0.5,
                "resolution": "1280x720",
                "framerate": 30,
                "duration_seconds": 60
            }
        }
        
        mock_ipfs_model.close_webrtc_connection.return_value = {
            "success": True,
            "connection_id": "conn123",
            "message": "Connection closed successfully"
        }
        
        mock_ipfs_model.close_all_webrtc_connections.return_value = {
            "success": True,
            "closed_connections": 1,
            "message": "All connections closed successfully"
        }
        
        mock_ipfs_model.set_webrtc_quality.return_value = {
            "success": True,
            "connection_id": "conn123",
            "new_quality": {
                "resolution": "1280x720",
                "framerate": 30,
                "bitrate": 500000
            }
        }
        
        # Resource stats
        mock_ipfs_model.get_webrtc_resource_stats.return_value = {
            "success": True,
            "resources": {
                "cpu_percent": 25.5,
                "memory_percent": 30.2,
                "disk_percent": 45.8,
                "network_rx_bytes": 1048576,
                "network_tx_bytes": 2097152
            }
        }
        
        # Benchmark operations
        mock_ipfs_model.run_webrtc_benchmark.return_value = {
            "success": True,
            "benchmark_id": "bench123",
            "results": {
                "max_bitrate_mbps": 10.5,
                "avg_latency_ms": 25.3,
                "packet_loss_percent": 0.2,
                "cpu_utilization_percent": 35.0,
                "connection_setup_time_ms": 150,
                "test_duration_seconds": 30,
                "resolution_tests": [
                    {"resolution": "1280x720", "framerate": 30, "success": True},
                    {"resolution": "1920x1080", "framerate": 30, "success": True}
                ]
            }
        }
        
        # Initialize controller with mock dependencies check
        with patch("ipfs_kit_py.mcp.controllers.webrtc_controller.WebRTCController._check_dependencies", 
                  return_value=True):
            controller = WebRTCController(mock_ipfs_model)
            controller.register_routes(router)
            
            # Add active server and connection for tests that need them
            controller.active_servers["server123"] = {
                "server_id": "server123",
                "address": "127.0.0.1",
                "port": 8080,
                "content_cid": "testcid",
                "started_at": time.time(),
                "process": None
            }
            
            controller.active_connections["conn123"] = {
                "connection_id": "conn123",
                "server_id": "server123",
                "created_at": time.time(),
                "status": "active",
                "content_cid": "testcid",
                "client_info": {"ip": "127.0.0.1", "user_agent": "test-client"}
            }
            
            # Mount router to app
            app.include_router(router, prefix="/api/v0")
            
            # Create test client
            client = TestClient(app)
            
            return {
                "app": app,
                "client": client,
                "controller": controller,
                "ipfs_model": mock_ipfs_model
            }
    
    def test_check_webrtc_support(self, controller_with_app):
        """Test checking WebRTC dependencies."""
        client = controller_with_app["client"]
        
        # Test with WebRTC support
        response = client.get("/api/v0/webrtc/check")
        assert response.status_code == 200
        assert response.json() == {"webrtc_support": True}
        
        # Modify controller to test without WebRTC support
        controller_with_app["controller"]._has_dependencies = False
        response = client.get("/api/v0/webrtc/check")
        assert response.status_code == 200
        assert response.json() == {"webrtc_support": False}
    
    def test_start_stream(self, controller_with_app):
        """Test starting a WebRTC stream."""
        client = controller_with_app["client"]
        ipfs_model = controller_with_app["ipfs_model"]
        
        # Test starting stream with minimal parameters
        response = client.post(
            "/api/v0/webrtc/stream",
            json={"content_cid": "testcid"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "server_id" in data
        assert "connection_id" in data
        assert data["content_cid"] == "testcid"
        
        # Verify model method was called
        ipfs_model.start_webrtc_streaming.assert_called_once()
        
        # Test starting stream with all parameters
        ipfs_model.start_webrtc_streaming.reset_mock()
        response = client.post(
            "/api/v0/webrtc/stream",
            json={
                "content_cid": "testcid2",
                "address": "0.0.0.0",
                "port": 9000,
                "quality": {
                    "resolution": "1920x1080",
                    "framerate": 60,
                    "bitrate": 1000000
                },
                "ice_servers": [
                    {"urls": "stun:stun.example.com:19302"},
                    {"urls": "turn:turn.example.com:3478", "username": "user", "credential": "pass"}
                ]
            }
        )
        
        assert response.status_code == 200
        
        # Verify model method was called with custom parameters
        call_kwargs = ipfs_model.start_webrtc_streaming.call_args.kwargs
        assert call_kwargs["content_cid"] == "testcid2"
        assert call_kwargs["address"] == "0.0.0.0"
        assert call_kwargs["port"] == 9000
        assert call_kwargs["quality"]["resolution"] == "1920x1080"
        assert call_kwargs["quality"]["framerate"] == 60
        assert call_kwargs["quality"]["bitrate"] == 1000000
        assert len(call_kwargs["ice_servers"]) == 2
    
    def test_stop_stream(self, controller_with_app):
        """Test stopping a WebRTC stream."""
        client = controller_with_app["client"]
        ipfs_model = controller_with_app["ipfs_model"]
        
        # Test stopping existing stream
        response = client.post("/api/v0/webrtc/stream/stop/server123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["server_id"] == "server123"
        assert "message" in data
        
        # Verify model method was called
        ipfs_model.stop_webrtc_streaming.assert_called_once_with(server_id="server123")
        
        # Test stopping non-existent stream
        ipfs_model.stop_webrtc_streaming.reset_mock()
        ipfs_model.stop_webrtc_streaming.return_value = {
            "success": False,
            "error": "Server not found",
            "error_type": "not_found"
        }
        
        response = client.post("/api/v0/webrtc/stream/stop/nonexistent")
        assert response.status_code == 404  # Not found
        assert "Server not found" in response.json()["detail"]
    
    def test_list_connections(self, controller_with_app):
        """Test listing WebRTC connections."""
        client = controller_with_app["client"]
        ipfs_model = controller_with_app["ipfs_model"]
        
        # Test getting connections list
        response = client.get("/api/v0/webrtc/connections")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "connections" in data
        assert len(data["connections"]) == 1
        assert data["connections"][0]["connection_id"] == "conn123"
        
        # Verify model method was called
        ipfs_model.get_webrtc_connections.assert_called_once()
    
    def test_get_connection_stats(self, controller_with_app):
        """Test getting WebRTC connection statistics."""
        client = controller_with_app["client"]
        ipfs_model = controller_with_app["ipfs_model"]
        
        # Test getting stats for existing connection
        response = client.get("/api/v0/webrtc/connections/conn123/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["connection_id"] == "conn123"
        assert "stats" in data
        assert "bitrate_outgoing" in data["stats"]
        assert "resolution" in data["stats"]
        
        # Verify model method was called
        ipfs_model.get_webrtc_connection_stats.assert_called_once_with(connection_id="conn123")
        
        # Test getting stats for non-existent connection
        ipfs_model.get_webrtc_connection_stats.reset_mock()
        ipfs_model.get_webrtc_connection_stats.return_value = {
            "success": False,
            "error": "Connection not found",
            "error_type": "not_found"
        }
        
        response = client.get("/api/v0/webrtc/connections/nonexistent/stats")
        assert response.status_code == 404  # Not found
        assert "Connection not found" in response.json()["detail"]
    
    def test_close_connection(self, controller_with_app):
        """Test closing a WebRTC connection."""
        client = controller_with_app["client"]
        ipfs_model = controller_with_app["ipfs_model"]
        
        # Test closing existing connection
        response = client.post("/api/v0/webrtc/connections/conn123/close")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["connection_id"] == "conn123"
        assert "message" in data
        
        # Verify model method was called
        ipfs_model.close_webrtc_connection.assert_called_once_with(connection_id="conn123")
        
        # Test closing non-existent connection
        ipfs_model.close_webrtc_connection.reset_mock()
        ipfs_model.close_webrtc_connection.return_value = {
            "success": False,
            "error": "Connection not found",
            "error_type": "not_found"
        }
        
        response = client.post("/api/v0/webrtc/connections/nonexistent/close")
        assert response.status_code == 404  # Not found
        assert "Connection not found" in response.json()["detail"]
    
    def test_close_all_connections(self, controller_with_app):
        """Test closing all WebRTC connections."""
        client = controller_with_app["client"]
        ipfs_model = controller_with_app["ipfs_model"]
        
        # Test closing all connections
        response = client.post("/api/v0/webrtc/connections/close-all")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "closed_connections" in data
        assert "message" in data
        
        # Verify model method was called
        ipfs_model.close_all_webrtc_connections.assert_called_once()
    
    def test_set_quality(self, controller_with_app):
        """Test setting WebRTC streaming quality."""
        client = controller_with_app["client"]
        ipfs_model = controller_with_app["ipfs_model"]
        
        # Test setting quality for existing connection
        response = client.post(
            "/api/v0/webrtc/connections/quality",
            json={
                "connection_id": "conn123",
                "resolution": "1280x720",
                "framerate": 30,
                "bitrate": 500000
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["connection_id"] == "conn123"
        assert "new_quality" in data
        
        # Verify model method was called
        call_kwargs = ipfs_model.set_webrtc_quality.call_args.kwargs
        assert call_kwargs["connection_id"] == "conn123"
        assert call_kwargs["resolution"] == "1280x720"
        assert call_kwargs["framerate"] == 30
        assert call_kwargs["bitrate"] == 500000
        
        # Test setting quality for non-existent connection
        ipfs_model.set_webrtc_quality.reset_mock()
        ipfs_model.set_webrtc_quality.return_value = {
            "success": False,
            "error": "Connection not found",
            "error_type": "not_found"
        }
        
        response = client.post(
            "/api/v0/webrtc/connections/quality",
            json={
                "connection_id": "nonexistent",
                "resolution": "1280x720",
                "framerate": 30,
                "bitrate": 500000
            }
        )
        
        assert response.status_code == 404  # Not found
        assert "Connection not found" in response.json()["detail"]
    
    def test_get_resource_stats(self, controller_with_app):
        """Test getting WebRTC resource statistics."""
        client = controller_with_app["client"]
        ipfs_model = controller_with_app["ipfs_model"]
        
        # Test getting resource stats
        response = client.get("/api/v0/webrtc/stats/resources")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "resources" in data
        assert "cpu_percent" in data["resources"]
        assert "memory_percent" in data["resources"]
        
        # Verify model method was called
        ipfs_model.get_webrtc_resource_stats.assert_called_once()
    
    def test_run_benchmark(self, controller_with_app):
        """Test running WebRTC benchmark."""
        client = controller_with_app["client"]
        ipfs_model = controller_with_app["ipfs_model"]
        
        # Test running benchmark with minimal parameters
        response = client.post("/api/v0/webrtc/benchmark", json={})
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "benchmark_id" in data
        assert "results" in data
        
        # Verify model method was called
        ipfs_model.run_webrtc_benchmark.assert_called_once()
        
        # Test running benchmark with custom parameters
        ipfs_model.run_webrtc_benchmark.reset_mock()
        response = client.post(
            "/api/v0/webrtc/benchmark",
            json={
                "duration_seconds": 60,
                "test_resolutions": ["1280x720", "1920x1080"],
                "test_framerates": [30, 60],
                "test_bitrates": [1000000, 2000000],
                "stun_servers": ["stun:stun.example.com:19302"]
            }
        )
        
        assert response.status_code == 200
        
        # Verify model method was called with custom parameters
        call_kwargs = ipfs_model.run_webrtc_benchmark.call_args.kwargs
        assert call_kwargs["duration_seconds"] == 60
        assert call_kwargs["test_resolutions"] == ["1280x720", "1920x1080"]
        assert call_kwargs["test_framerates"] == [30, 60]
        assert call_kwargs["test_bitrates"] == [1000000, 2000000]
        assert call_kwargs["stun_servers"] == ["stun:stun.example.com:19302"]
    
    def test_operations_without_webrtc_support(self, controller_with_app):
        """Test WebRTC operations without WebRTC support."""
        client = controller_with_app["client"]
        controller_with_app["controller"]._has_dependencies = False
        
        # Test starting stream without WebRTC support
        response = client.post(
            "/api/v0/webrtc/stream",
            json={"content_cid": "testcid"}
        )
        assert response.status_code == 400  # Bad request
        assert "WebRTC is not available" in response.json()["detail"]
        
        # Test stopping stream without WebRTC support
        response = client.post("/api/v0/webrtc/stream/stop/server123")
        assert response.status_code == 400  # Bad request
        assert "WebRTC is not available" in response.json()["detail"]
        
        # Test listing connections without WebRTC support
        response = client.get("/api/v0/webrtc/connections")
        assert response.status_code == 400  # Bad request
        assert "WebRTC is not available" in response.json()["detail"]


class TestResourceManagement:
    """Test resource management functionality of WebRTCController."""
    
    def test_server_tracking(self):
        """Test tracking of streaming servers."""
        # Mock IPFS model
        mock_ipfs_model = MagicMock()
        
        # Initialize controller
        with patch("ipfs_kit_py.mcp.controllers.webrtc_controller.WebRTCController._check_dependencies", 
                  return_value=True):
            controller = WebRTCController(mock_ipfs_model)
            
            # Add test server
            server_info = {
                "server_id": "server123",
                "address": "127.0.0.1",
                "port": 8080,
                "content_cid": "testcid",
                "started_at": time.time()
            }
            controller.active_servers["server123"] = server_info
            
            # Test server tracking
            assert "server123" in controller.active_servers
            assert controller.active_servers["server123"]["content_cid"] == "testcid"
            
            # Test server removal
            controller._remove_server("server123")
            assert "server123" not in controller.active_servers
    
    def test_connection_tracking(self):
        """Test tracking of WebRTC connections."""
        # Mock IPFS model
        mock_ipfs_model = MagicMock()
        
        # Initialize controller
        with patch("ipfs_kit_py.mcp.controllers.webrtc_controller.WebRTCController._check_dependencies", 
                  return_value=True):
            controller = WebRTCController(mock_ipfs_model)
            
            # Add test connection
            connection_info = {
                "connection_id": "conn123",
                "server_id": "server123",
                "created_at": time.time(),
                "status": "active",
                "content_cid": "testcid",
                "client_info": {"ip": "127.0.0.1", "user_agent": "test-client"}
            }
            controller.active_connections["conn123"] = connection_info
            
            # Test connection tracking
            assert "conn123" in controller.active_connections
            assert controller.active_connections["conn123"]["status"] == "active"
            
            # Test connection status update
            controller._update_connection_status("conn123", "idle")
            assert controller.active_connections["conn123"]["status"] == "idle"
            
            # Test connection removal
            controller._remove_connection("conn123")
            assert "conn123" not in controller.active_connections
    
    def test_cleanup_system(self):
        """Test the automatic cleanup system."""
        # Mock IPFS model
        mock_ipfs_model = MagicMock()
        
        # Initialize controller with mock cleanup method
        with patch("ipfs_kit_py.mcp.controllers.webrtc_controller.WebRTCController._check_dependencies", 
                  return_value=True):
            with patch("ipfs_kit_py.mcp.controllers.webrtc_controller.WebRTCController._start_cleanup_task"):
                controller = WebRTCController(mock_ipfs_model)
                
                # Mock cleanup method
                controller._cleanup_resources = MagicMock()
                
                # Test manual cleanup trigger
                controller._cleanup_resources.reset_mock()
                controller._trigger_cleanup()
                controller._cleanup_resources.assert_called_once()
                
                # Test cleanup result
                controller._cleanup_resources.return_value = {
                    "servers_closed": 1,
                    "connections_closed": 2
                }
                
                result = controller._trigger_cleanup()
                assert result["servers_closed"] == 1
                assert result["connections_closed"] == 2


@pytest.mark.anyio
class TestWebRTCControllerAnyIO:
    """Test suite for the AnyIO version of the WebRTCController."""
    
    @pytest.fixture
    async def async_controller(self):
        """Create a controller with async model for AnyIO testing."""
        # Mock IPFS model with async methods
        mock_ipfs_model = AsyncMock()
        
        # Set up mock operations
        mock_ipfs_model.start_webrtc_streaming.return_value = {
            "success": True,
            "server_id": "server123",
            "address": "127.0.0.1",
            "port": 8080,
            "content_cid": "testcid",
            "connection_id": "conn123"
        }
        
        mock_ipfs_model.get_webrtc_connections.return_value = {
            "success": True,
            "connections": [
                {
                    "connection_id": "conn123",
                    "server_id": "server123",
                    "created_at": time.time(),
                    "status": "active"
                }
            ]
        }
        
        # Initialize controller with mock dependencies check
        with patch("ipfs_kit_py.mcp.controllers.webrtc_controller_anyio.WebRTCController._check_dependencies", 
                  return_value=True):
            with patch("ipfs_kit_py.mcp.controllers.webrtc_controller_anyio.WebRTCController._start_cleanup_task"):
                controller = WebRTCController(mock_ipfs_model)
                
                # Add active server and connection for tests that need them
                controller.active_servers["server123"] = {
                    "server_id": "server123",
                    "address": "127.0.0.1",
                    "port": 8080,
                    "content_cid": "testcid",
                    "started_at": time.time()
                }
                
                controller.active_connections["conn123"] = {
                    "connection_id": "conn123",
                    "server_id": "server123",
                    "created_at": time.time(),
                    "status": "active"
                }
                
                return {
                    "controller": controller,
                    "ipfs_model": mock_ipfs_model
                }
    
    @pytest.mark.anyio
    async def test_async_start_stream(self, async_controller):
        """Test async version of start_stream method."""
        controller = async_controller["controller"]
        ipfs_model = async_controller["ipfs_model"]
        
        # Call the async method directly
        result = await controller.start_stream(
            content_cid="testcid",
            address="127.0.0.1",
            port=8080
        )
        
        # Verify result
        assert result["success"] is True
        assert result["server_id"] == "server123"
        assert result["content_cid"] == "testcid"
        
        # Verify model method was called with correct parameters
        call_kwargs = ipfs_model.start_webrtc_streaming.call_args.kwargs
        assert call_kwargs["content_cid"] == "testcid"
        assert call_kwargs["address"] == "127.0.0.1"
        assert call_kwargs["port"] == 8080
    
    @pytest.mark.anyio
    async def test_async_list_connections(self, async_controller):
        """Test async version of list_connections method."""
        controller = async_controller["controller"]
        ipfs_model = async_controller["ipfs_model"]
        
        # Call the async method directly
        result = await controller.list_connections()
        
        # Verify result
        assert result["success"] is True
        assert "connections" in result
        assert len(result["connections"]) == 1
        
        # Verify model method was called
        ipfs_model.get_webrtc_connections.assert_called_once()
    
    @pytest.mark.anyio
    async def test_async_run_benchmark(self, async_controller):
        """Test async version of run_benchmark method."""
        controller = async_controller["controller"]
        ipfs_model = async_controller["ipfs_model"]
        
        # Set up mock benchmark response
        ipfs_model.run_webrtc_benchmark.return_value = {
            "success": True,
            "benchmark_id": "bench123",
            "results": {
                "max_bitrate_mbps": 10.5,
                "avg_latency_ms": 25.3
            }
        }
        
        # Call the async method directly
        result = await controller.run_benchmark(
            duration_seconds=60,
            test_resolutions=["1280x720", "1920x1080"]
        )
        
        # Verify result
        assert result["success"] is True
        assert result["benchmark_id"] == "bench123"
        assert "results" in result
        
        # Verify model method was called with correct parameters
        call_kwargs = ipfs_model.run_webrtc_benchmark.call_args.kwargs
        assert call_kwargs["duration_seconds"] == 60
        assert call_kwargs["test_resolutions"] == ["1280x720", "1920x1080"]


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])