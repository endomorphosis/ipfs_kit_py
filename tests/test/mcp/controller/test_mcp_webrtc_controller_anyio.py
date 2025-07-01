"""
Test suite for MCP WebRTC Controller AnyIO version.

This module tests the functionality of the WebRTCControllerAnyIO class
which provides asynchronous HTTP endpoints for WebRTC streaming, connection
management, and resource monitoring.
"""

import pytest
import json
import time
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient

from ipfs_kit_py.mcp.controllers.webrtc_controller_anyio import (
    WebRTCControllerAnyIO, WebRTCResponse, ResourceStatsResponse, StreamRequest,
    StreamResponse, ConnectionResponse, ConnectionsListResponse, 
    ConnectionStatsResponse, DependencyResponse, BenchmarkRequest, BenchmarkResponse,
    QualityRequest
)


class TestWebRTCControllerAnyIOInitialization:
    """Test initialization and basic setup of WebRTCControllerAnyIO."""

    def test_init(self):
        """Test controller initialization."""
        # Create mock model
        mock_model = MagicMock()
        
        # Create controller
        controller = WebRTCControllerAnyIO(mock_model)
        
        # Verify initialization
        assert controller.ipfs_model == mock_model
        assert isinstance(controller.active_streaming_servers, dict)
        assert isinstance(controller.active_connections, dict)
        assert controller.is_shutting_down is False
        
    def test_register_routes(self):
        """Test route registration."""
        # Create mock router and model
        mock_router = MagicMock(spec=APIRouter)
        mock_model = MagicMock()
        
        # Create controller and register routes
        controller = WebRTCControllerAnyIO(mock_model)
        controller.register_routes(mock_router)
        
        # Verify routes were registered
        expected_routes = [
            "/webrtc/check",
            "/webrtc/stream",
            "/webrtc/stream/stop/{server_id}",
            "/webrtc/connections",
            "/webrtc/connections/{connection_id}/stats",
            "/webrtc/connections/{connection_id}/close",
            "/webrtc/connections/close-all",
            "/webrtc/connections/quality",
            "/webrtc/benchmark",
            "/webrtc/stats/resources"
        ]
        
        # Check that all expected routes were registered
        call_args_list = mock_router.add_api_route.call_args_list
        registered_paths = [args[0][0] for args in call_args_list]
        
        for route in expected_routes:
            assert route in registered_paths, f"Route {route} was not registered"


@pytest.mark.anyio
class TestWebRTCControllerAnyIO:
    """Test AnyIO-specific functionality of WebRTCControllerAnyIO."""
    
    @pytest.fixture
    def mock_webrtc_model(self):
        """Create a mock WebRTC model with async methods."""
        model = MagicMock()
        
        # Set up model to ensure sync methods are not used
        # We'll track if these are called, which would be incorrect
        model.check_webrtc_dependencies = MagicMock(return_value={
            "success": True,
            "dependencies": {
                "aiortc": True,
                "aiohttp": True,
                "av": True
            },
            "webrtc_available": True
        })
        
        model.stream_content_webrtc = MagicMock(return_value={
            "success": True,
            "server_id": "test-server-1",
            "url": "http://localhost:8080/webrtc/test-server-1"
        })
        
        model.stop_webrtc_streaming = MagicMock(return_value={
            "success": True,
            "server_id": "test-server-1",
            "message": "Streaming server stopped successfully"
        })
        
        model.list_webrtc_connections = MagicMock(return_value={
            "success": True,
            "connections": [
                {
                    "id": "conn-1",
                    "server_id": "test-server-1",
                    "peer_id": "peer-1",
                    "status": "active"
                }
            ]
        })
        
        model.get_webrtc_connection_stats = MagicMock(return_value={
            "success": True,
            "connection_id": "conn-1",
            "stats": {
                "bandwidth": 1000000,
                "latency": 50,
                "packets_sent": 100,
                "packets_received": 95
            }
        })
        
        model.close_webrtc_connection = MagicMock(return_value={
            "success": True,
            "connection_id": "conn-1",
            "message": "Connection closed successfully"
        })
        
        model.close_all_webrtc_connections = MagicMock(return_value={
            "success": True,
            "connections_closed": 2,
            "message": "All connections closed successfully"
        })
        
        model.set_webrtc_quality = MagicMock(return_value={
            "success": True,
            "connection_id": "conn-1",
            "quality": "high"
        })
        
        model.run_webrtc_benchmark = MagicMock(return_value={
            "success": True,
            "benchmark_id": "bench-1",
            "report_path": "/tmp/benchmark-report.json",
            "summary": {
                "average_bitrate": 5000000,
                "peak_bitrate": 8000000,
                "average_latency": 25
            }
        })
        
        return model
    
    @pytest.fixture
    def controller(self, mock_webrtc_model):
        """Create WebRTCControllerAnyIO with mock model."""
        # Initialize controller with mock cleanup task
        with patch("ipfs_kit_py.mcp.controllers.webrtc_controller_anyio.WebRTCControllerAnyIO._start_cleanup_task"):
            controller = WebRTCControllerAnyIO(mock_webrtc_model)
            
            # Set up active streaming servers for testing
            controller.active_streaming_servers["test-server-1"] = {
                "cid": "QmTestCid",
                "started_at": time.time(),
                "address": "127.0.0.1",
                "port": 8080,
                "url": "http://localhost:8080/webrtc/test-server-1"
            }
            
            # Set up active connections for testing
            controller.active_connections["conn-1"] = {
                "added_at": time.time(),
                "server_id": "test-server-1",
                "peer_id": "peer-1",
                "quality": "medium"
            }
            
            return controller
    
    @pytest.fixture
    def app_client(self, controller):
        """Create FastAPI test client with controller routes."""
        app = FastAPI()
        router = APIRouter()
        controller.register_routes(router)
        app.include_router(router)
        return TestClient(app)
    
    @pytest.mark.anyio
    async def test_check_dependencies(self, controller, mock_webrtc_model):
        """Test check_dependencies method."""
        result = await controller.check_dependencies()
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_webrtc_model.check_webrtc_dependencies.assert_called_once()
        
        # Verify result
        assert result["success"] is True
        assert result["webrtc_available"] is True
        assert "dependencies" in result
        assert result["dependencies"]["aiortc"] is True
    
    @pytest.mark.anyio
    async def test_stream_content(self, controller, mock_webrtc_model):
        """Test stream_content method."""
        # Create request
        request = StreamRequest(
            cid="QmTestCid",
            address="127.0.0.1",
            port=8080,
            quality="medium",
            ice_servers=[{"urls": ["stun:stun.l.google.com:19302"]}],
            benchmark=False,
            buffer_size=30,
            prefetch_threshold=0.5,
            use_progressive_loading=True
        )
        
        # Call method
        result = await controller.stream_content(request)
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_webrtc_model.stream_content_webrtc.assert_called_once()
        
        # Verify result
        assert result["success"] is True
        assert result["server_id"] == "test-server-1"
        
        # Verify server was added to tracking
        assert "test-server-1" in controller.active_streaming_servers
    
    @pytest.mark.anyio
    async def test_stop_streaming(self, controller, mock_webrtc_model):
        """Test stop_streaming method."""
        result = await controller.stop_streaming("test-server-1")
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_webrtc_model.stop_webrtc_streaming.assert_called_once_with(server_id="test-server-1")
        
        # Verify result
        assert result["success"] is True
        assert result["server_id"] == "test-server-1"
        
        # Verify server was removed from tracking
        assert "test-server-1" not in controller.active_streaming_servers
    
    @pytest.mark.anyio
    async def test_list_connections(self, controller, mock_webrtc_model):
        """Test list_connections method."""
        result = await controller.list_connections()
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_webrtc_model.list_webrtc_connections.assert_called_once()
        
        # Verify result
        assert result["success"] is True
        assert "connections" in result
        assert len(result["connections"]) == 1
        assert result["connections"][0]["id"] == "conn-1"
    
    @pytest.mark.anyio
    async def test_get_connection_stats(self, controller, mock_webrtc_model):
        """Test get_connection_stats method."""
        result = await controller.get_connection_stats("conn-1")
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_webrtc_model.get_webrtc_connection_stats.assert_called_once_with(connection_id="conn-1")
        
        # Verify result
        assert result["success"] is True
        assert result["connection_id"] == "conn-1"
        assert "stats" in result
        assert "bandwidth" in result["stats"]
        assert "latency" in result["stats"]
    
    @pytest.mark.anyio
    async def test_close_connection(self, controller, mock_webrtc_model):
        """Test close_connection method."""
        result = await controller.close_connection("conn-1")
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_webrtc_model.close_webrtc_connection.assert_called_once_with(connection_id="conn-1")
        
        # Verify result
        assert result["success"] is True
        assert result["connection_id"] == "conn-1"
        
        # Verify connection was removed from tracking
        assert "conn-1" not in controller.active_connections
    
    @pytest.mark.anyio
    async def test_close_all_connections(self, controller, mock_webrtc_model):
        """Test close_all_connections method."""
        result = await controller.close_all_connections()
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_webrtc_model.close_all_webrtc_connections.assert_called_once()
        
        # Verify result
        assert result["success"] is True
        assert "connections_closed" in result
        
        # Verify all connections were removed from tracking
        assert len(controller.active_connections) == 0
    
    @pytest.mark.anyio
    async def test_set_quality(self, controller, mock_webrtc_model):
        """Test set_quality method."""
        # Create request
        request = QualityRequest(
            connection_id="conn-1",
            quality="high"
        )
        
        # Call method
        result = await controller.set_quality(request)
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_webrtc_model.set_webrtc_quality.assert_called_once_with(
            connection_id="conn-1",
            quality="high"
        )
        
        # Verify result
        assert result["success"] is True
        assert result["connection_id"] == "conn-1"
        assert "quality" in result
        
        # Verify connection quality was updated in tracking
        assert controller.active_connections["conn-1"]["quality"] == "high"
    
    @pytest.mark.anyio
    async def test_run_benchmark(self, controller, mock_webrtc_model):
        """Test run_benchmark method."""
        # Create request
        request = BenchmarkRequest(
            cid="QmTestCid",
            duration=60,
            format="json",
            output_dir="/tmp"
        )
        
        # Call method
        result = await controller.run_benchmark(request)
        
        # Verify async pattern: sync model method was called via to_thread.run_sync
        mock_webrtc_model.run_webrtc_benchmark.assert_called_once_with(
            cid=request.cid,
            duration_seconds=request.duration,
            report_format=request.format,
            output_dir=request.output_dir
        )
        
        # Verify result
        assert result["success"] is True
        assert result["benchmark_id"] == "bench-1"
        assert "report_path" in result
        assert "summary" in result
        
        # Verify benchmark is tracked in streaming servers
        assert "bench-1" in controller.active_streaming_servers
        assert controller.active_streaming_servers["bench-1"]["is_benchmark"] is True
    
    @pytest.mark.anyio
    async def test_get_resources_endpoint(self, controller):
        """Test get_resources_endpoint method."""
        result = await controller.get_resources_endpoint()
        
        # Verify result
        assert result["success"] is True
        assert "servers" in result
        assert "connections" in result
        assert "timestamp" in result
        assert "is_shutting_down" in result
        assert "cleanup_task_active" in result
    
    @pytest.mark.anyio
    async def test_delayed_cleanup(self, controller):
        """Test delayed_cleanup created by run_benchmark."""
        # Create mock anyio functions to test delayed_cleanup
        with patch("ipfs_kit_py.mcp.controllers.webrtc_controller_anyio.anyio") as mock_anyio:
            # Mock create_task to capture the delayed_cleanup function
            async def fake_create_task(coro):
                # Directly call the coroutine to test it
                await coro
            
            mock_anyio.create_task.side_effect = fake_create_task
            mock_anyio.sleep = AsyncMock()
            
            # Create benchmark request
            request = BenchmarkRequest(
                cid="QmTestCid",
                duration=10,  # Short duration for test
                format="json"
            )
            
            # Run benchmark which should schedule cleanup
            await controller.run_benchmark(request)
            
            # Verify anyio.sleep was called with correct duration (benchmark duration + buffer)
            mock_anyio.sleep.assert_called_once_with(15)  # 10 + 5 second buffer


class TestWebRTCControllerAnyIOHTTPEndpoints:
    """Test HTTP endpoints of WebRTCControllerAnyIO."""
    
    @pytest.fixture
    def mock_webrtc_model(self):
        """Create a mock WebRTC model."""
        model = MagicMock()
        
        # Set up mock responses
        model.check_webrtc_dependencies = MagicMock(return_value={
            "success": True,
            "dependencies": {
                "aiortc": True,
                "aiohttp": True,
                "av": True
            },
            "webrtc_available": True,
            "installation_command": "pip install aiortc"
        })
        
        model.stream_content_webrtc = MagicMock(return_value={
            "success": True,
            "server_id": "test-server-1",
            "url": "http://localhost:8080/webrtc/test-server-1"
        })
        
        model.stop_webrtc_streaming = MagicMock(return_value={
            "success": True,
            "server_id": "test-server-1",
            "message": "Streaming server stopped successfully"
        })
        
        model.list_webrtc_connections = MagicMock(return_value={
            "success": True,
            "connections": [
                {
                    "id": "conn-1",
                    "server_id": "test-server-1",
                    "peer_id": "peer-1",
                    "status": "active"
                }
            ]
        })
        
        model.get_webrtc_connection_stats = MagicMock(return_value={
            "success": True,
            "connection_id": "conn-1",
            "stats": {
                "bandwidth": 1000000,
                "latency": 50,
                "packets_sent": 100,
                "packets_received": 95
            }
        })
        
        model.close_webrtc_connection = MagicMock(return_value={
            "success": True,
            "connection_id": "conn-1",
            "message": "Connection closed successfully"
        })
        
        model.close_all_webrtc_connections = MagicMock(return_value={
            "success": True,
            "connections_closed": 2,
            "message": "All connections closed successfully"
        })
        
        model.set_webrtc_quality = MagicMock(return_value={
            "success": True,
            "connection_id": "conn-1",
            "quality": "high"
        })
        
        model.run_webrtc_benchmark = MagicMock(return_value={
            "success": True,
            "benchmark_id": "bench-1",
            "report_path": "/tmp/benchmark-report.json",
            "summary": {
                "average_bitrate": 5000000,
                "peak_bitrate": 8000000,
                "average_latency": 25
            }
        })
        
        return model
    
    @pytest.fixture
    def app_client(self, mock_webrtc_model):
        """Create FastAPI test client with controller routes."""
        # Create FastAPI app
        app = FastAPI()
        router = APIRouter()
        
        # Create controller with mock cleanup task
        with patch("ipfs_kit_py.mcp.controllers.webrtc_controller_anyio.WebRTCControllerAnyIO._start_cleanup_task"):
            controller = WebRTCControllerAnyIO(mock_webrtc_model)
            controller.register_routes(router)
            
            # Set up active streaming servers for testing
            controller.active_streaming_servers["test-server-1"] = {
                "cid": "QmTestCid",
                "started_at": time.time(),
                "address": "127.0.0.1",
                "port": 8080,
                "url": "http://localhost:8080/webrtc/test-server-1"
            }
            
            # Set up active connections for testing
            controller.active_connections["conn-1"] = {
                "added_at": time.time(),
                "server_id": "test-server-1",
                "peer_id": "peer-1",
                "quality": "medium"
            }
        
        app.include_router(router)
        return TestClient(app)
    
    def test_check_dependencies_endpoint(self, app_client, mock_webrtc_model):
        """Test /webrtc/check endpoint."""
        response = app_client.get("/webrtc/check")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["webrtc_available"] is True
        assert "dependencies" in data
        assert "installation_command" in data
        
        # Verify model method was called
        mock_webrtc_model.check_webrtc_dependencies.assert_called_once()
    
    def test_stream_endpoint(self, app_client, mock_webrtc_model):
        """Test /webrtc/stream endpoint."""
        response = app_client.post(
            "/webrtc/stream",
            json={
                "cid": "QmTestCid",
                "address": "127.0.0.1",
                "port": 8080,
                "quality": "medium",
                "ice_servers": [{"urls": ["stun:stun.l.google.com:19302"]}],
                "benchmark": False,
                "buffer_size": 30,
                "prefetch_threshold": 0.5,
                "use_progressive_loading": True
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["server_id"] == "test-server-1"
        
        # Verify model method was called with correct parameters
        call_kwargs = mock_webrtc_model.stream_content_webrtc.call_args.kwargs
        assert call_kwargs["cid"] == "QmTestCid"
        assert call_kwargs["listen_address"] == "127.0.0.1"
        assert call_kwargs["port"] == 8080
        assert call_kwargs["quality"] == "medium"
        assert call_kwargs["buffer_size"] == 30
        assert call_kwargs["prefetch_threshold"] == 0.5
        assert call_kwargs["use_progressive_loading"] is True
    
    def test_stop_streaming_endpoint(self, app_client, mock_webrtc_model):
        """Test /webrtc/stream/stop/{server_id} endpoint."""
        response = app_client.post("/webrtc/stream/stop/test-server-1")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["server_id"] == "test-server-1"
        
        # Verify model method was called
        mock_webrtc_model.stop_webrtc_streaming.assert_called_once_with(server_id="test-server-1")
    
    def test_list_connections_endpoint(self, app_client, mock_webrtc_model):
        """Test /webrtc/connections endpoint."""
        response = app_client.get("/webrtc/connections")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "connections" in data
        assert len(data["connections"]) == 1
        
        # Verify model method was called
        mock_webrtc_model.list_webrtc_connections.assert_called_once()
    
    def test_get_connection_stats_endpoint(self, app_client, mock_webrtc_model):
        """Test /webrtc/connections/{connection_id}/stats endpoint."""
        response = app_client.get("/webrtc/connections/conn-1/stats")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["connection_id"] == "conn-1"
        assert "stats" in data
        
        # Verify model method was called
        mock_webrtc_model.get_webrtc_connection_stats.assert_called_once_with(connection_id="conn-1")
    
    def test_close_connection_endpoint(self, app_client, mock_webrtc_model):
        """Test /webrtc/connections/{connection_id}/close endpoint."""
        response = app_client.post("/webrtc/connections/conn-1/close")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["connection_id"] == "conn-1"
        
        # Verify model method was called
        mock_webrtc_model.close_webrtc_connection.assert_called_once_with(connection_id="conn-1")
    
    def test_close_all_connections_endpoint(self, app_client, mock_webrtc_model):
        """Test /webrtc/connections/close-all endpoint."""
        response = app_client.post("/webrtc/connections/close-all")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "connections_closed" in data
        
        # Verify model method was called
        mock_webrtc_model.close_all_webrtc_connections.assert_called_once()
    
    def test_set_quality_endpoint(self, app_client, mock_webrtc_model):
        """Test /webrtc/connections/quality endpoint."""
        response = app_client.post(
            "/webrtc/connections/quality",
            json={
                "connection_id": "conn-1",
                "quality": "high"
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["connection_id"] == "conn-1"
        
        # Verify model method was called
        mock_webrtc_model.set_webrtc_quality.assert_called_once_with(
            connection_id="conn-1",
            quality="high"
        )
    
    def test_run_benchmark_endpoint(self, app_client, mock_webrtc_model):
        """Test /webrtc/benchmark endpoint."""
        response = app_client.post(
            "/webrtc/benchmark",
            json={
                "cid": "QmTestCid",
                "duration": 60,
                "format": "json",
                "output_dir": "/tmp"
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["benchmark_id"] == "bench-1"
        
        # Verify model method was called
        mock_webrtc_model.run_webrtc_benchmark.assert_called_once_with(
            cid="QmTestCid",
            duration_seconds=60,
            report_format="json",
            output_dir="/tmp"
        )
    
    def test_get_resources_endpoint(self, app_client):
        """Test /webrtc/stats/resources endpoint."""
        response = app_client.get("/webrtc/stats/resources")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "servers" in data
        assert "connections" in data
        assert "timestamp" in data
    
    def test_error_handling(self, app_client, mock_webrtc_model):
        """Test error handling in endpoints."""
        # Set up model to return an error
        mock_webrtc_model.get_webrtc_connection_stats.return_value = {
            "success": False,
            "error": "Connection not found",
            "error_type": "not_found"
        }
        
        # Test endpoint that should return a 404
        response = app_client.get("/webrtc/connections/nonexistent/stats")
        
        # Verify response
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "Connection not found" in data["detail"]


class TestWebRTCControllerResourceManagement:
    """Test resource management functionality of WebRTCControllerAnyIO."""
    
    @pytest.fixture
    def controller(self):
        """Create WebRTCControllerAnyIO for resource management tests."""
        # Create mock IPFS model
        mock_model = MagicMock()
        
        # Create controller with mock cleanup task
        with patch("ipfs_kit_py.mcp.controllers.webrtc_controller_anyio.WebRTCControllerAnyIO._start_cleanup_task"):
            controller = WebRTCControllerAnyIO(mock_model)
            return controller
    
    def test_server_tracking(self, controller):
        """Test tracking of streaming servers."""
        # Add a server to tracking
        server_info = {
            "cid": "QmTestCid",
            "started_at": time.time(),
            "address": "127.0.0.1",
            "port": 8080,
            "url": "http://localhost:8080/webrtc/test-server-1"
        }
        controller.active_streaming_servers["test-server-1"] = server_info
        
        # Verify it was added
        assert "test-server-1" in controller.active_streaming_servers
        assert controller.active_streaming_servers["test-server-1"]["cid"] == "QmTestCid"
        
        # Get resource stats
        stats = controller.get_resource_stats()
        
        # Verify stats contain server information
        assert stats["servers"]["count"] == 1
        assert len(stats["servers"]["servers"]) == 1
        assert stats["servers"]["servers"][0]["id"] == "test-server-1"
    
    def test_connection_tracking(self, controller):
        """Test tracking of WebRTC connections."""
        # Add a connection to tracking
        connection_info = {
            "added_at": time.time(),
            "server_id": "test-server-1",
            "peer_id": "peer-1",
            "quality": "medium"
        }
        controller.active_connections["conn-1"] = connection_info
        
        # Verify it was added
        assert "conn-1" in controller.active_connections
        assert controller.active_connections["conn-1"]["server_id"] == "test-server-1"
        
        # Get resource stats
        stats = controller.get_resource_stats()
        
        # Verify stats contain connection information
        assert stats["connections"]["count"] == 1
        assert len(stats["connections"]["connections"]) == 1
        assert stats["connections"]["connections"][0]["id"] == "conn-1"
    
    @pytest.mark.anyio
    async def test_resource_cleanup_on_shutdown(self, controller):
        """Test resource cleanup during shutdown."""
        # Add servers and connections for testing cleanup
        controller.active_streaming_servers["server-1"] = {
            "cid": "QmTestCid1",
            "started_at": time.time(),
            "address": "127.0.0.1",
            "port": 8080
        }
        controller.active_streaming_servers["server-2"] = {
            "cid": "QmTestCid2",
            "started_at": time.time(),
            "address": "127.0.0.1",
            "port": 8081
        }
        
        controller.active_connections["conn-1"] = {
            "added_at": time.time(),
            "server_id": "server-1"
        }
        controller.active_connections["conn-2"] = {
            "added_at": time.time(),
            "server_id": "server-2"
        }
        
        # Mock the anyio module to avoid actual sleep
        with patch("ipfs_kit_py.mcp.controllers.webrtc_controller_anyio.anyio") as mock_anyio:
            # Mock to_thread.run_sync to return immediately
            mock_anyio.to_thread.run_sync = AsyncMock()
            
            # Call shutdown
            await controller.shutdown()
            
            # Verify is_shutting_down flag was set
            assert controller.is_shutting_down is True
            
            # Verify all servers were cleaned up
            assert len(controller.active_streaming_servers) == 0
            
            # Verify all connections were cleaned up
            assert len(controller.active_connections) == 0
            
            # Verify close_all_webrtc_connections was called
            mock_anyio.to_thread.run_sync.assert_called()


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])