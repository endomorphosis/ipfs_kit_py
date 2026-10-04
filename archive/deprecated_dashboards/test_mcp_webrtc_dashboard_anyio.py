"""
Test WebRTC Dashboard Controller with AnyIO support.

This test file focuses on testing the WebRTC Dashboard Controller's functionality
with AnyIO async/await patterns, ensuring proper handling of API endpoints and
integration with the WebRTC monitoring system.
"""

import os
import json
import time
import uuid
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

import anyio
ASYNC_BACKEND = "async" "io"
import sniffio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.testclient import TestClient as StarletteTestClient
from http import HTTPStatus

from ipfs_kit_py.mcp.controllers.webrtc_dashboard_controller_anyio import (
    WebRTCDashboardControllerAnyIO,
    create_webrtc_dashboard_router_anyio
)

# Create a mock WebRTCMonitor class for testing
class MockWebRTCMonitor:
    """Mock implementation of WebRTCMonitor for testing."""
    
    def __init__(self):
        """Initialize with test data."""
        self.connections = {
            "test-conn-1": {
                "connection_id": "test-conn-1",
                "content_cid": "QmTestCID1",
                "status": "active",
                "start_time": time.time() - 60,
                "end_time": None,
                "quality": 80,
                "peer_id": "test-peer-1"
            },
            "test-conn-2": {
                "connection_id": "test-conn-2",
                "content_cid": "QmTestCID2",
                "status": "closed",
                "start_time": time.time() - 120,
                "end_time": time.time() - 30,
                "quality": 60,
                "peer_id": "test-peer-2"
            }
        }
        
        self.operations = [
            {
                "operation": "stream_content",
                "connection_id": "test-conn-1",
                "timestamp": time.time() - 60,
                "success": True,
                "start_time": time.time() - 60,
                "end_time": None
            },
            {
                "operation": "close_connection",
                "connection_id": "test-conn-2",
                "timestamp": time.time() - 30,
                "success": True,
                "start_time": time.time() - 35,
                "end_time": time.time() - 30
            }
        ]
        
        self.task_tracker = MagicMock()
        self.task_tracker.tasks = {
            "task-1": {
                "task_id": "task-1",
                "name": "streaming",
                "created_at": time.time() - 60,
                "completed": False,
                "completed_at": None,
                "error": None
            },
            "task-2": {
                "task_id": "task-2",
                "name": "buffer_handling",
                "created_at": time.time() - 50,
                "completed": True,
                "completed_at": time.time() - 40,
                "error": None
            }
        }
    
    async def record_connection(self, connection_id, content_cid, status):
        """Record a connection (async mock)."""
        self.connections[connection_id] = {
            "connection_id": connection_id,
            "content_cid": content_cid,
            "status": status,
            "start_time": time.time(),
            "end_time": None,
            "quality": 80,
            "peer_id": f"peer-{connection_id}"
        }
        return True
    
    async def record_operation(self, operation, connection_id, success=True, error=None):
        """Record an operation (async mock)."""
        op = {
            "operation": operation,
            "connection_id": connection_id,
            "timestamp": time.time(),
            "success": success,
            "start_time": time.time(),
            "end_time": time.time() if success else None,
            "error": error
        }
        self.operations.append(op)
        return True

@pytest.mark.anyio
class TestWebRTCDashboardControllerAnyIO:
    """Test WebRTC Dashboard Controller with AnyIO support."""
    
    @pytest.fixture(autouse=True)
    async def setup(self):
        """Set up test environment before each test."""
        # Create a mock WebRTC model
        self.mock_webrtc_model = MagicMock()
        
        # Add async methods
        self.mock_webrtc_model.stream_content_webrtc = AsyncMock()
        self.mock_webrtc_model.close_webrtc_connection = AsyncMock()
        self.mock_webrtc_model.close_all_webrtc_connections = AsyncMock()
        self.mock_webrtc_model.set_webrtc_quality = AsyncMock()
        
        # Create a mock WebRTC monitor
        self.mock_webrtc_monitor = MockWebRTCMonitor()
        
        # Create controller instance
        self.controller = WebRTCDashboardControllerAnyIO(
            webrtc_model=self.mock_webrtc_model,
            webrtc_monitor=self.mock_webrtc_monitor
        )
        
        # Create FastAPI app with router
        self.app = FastAPI()
        self.router = create_webrtc_dashboard_router_anyio(
            webrtc_model=self.mock_webrtc_model,
            webrtc_monitor=self.mock_webrtc_monitor
        )
        self.app.include_router(self.router)
        
        # Create a test client
        self.client = TestClient(self.app)
        
        # Create temporary directory for static files
        self.static_dir = self.controller._get_static_dir()
        os.makedirs(self.static_dir, exist_ok=True)
        
        # Create a sample dashboard HTML file
        with open(os.path.join(self.static_dir, "webrtc_dashboard.html"), "w") as f:
            f.write("<html><body><h1>WebRTC Dashboard Test</h1></body></html>")
        
        yield
        
        # Cleanup if needed

    @pytest.mark.anyio
    async def test_get_backend(self):
        """Test that get_backend returns the expected value."""
        # This tests the backend detection in an async context
        async with anyio.create_task_group() as tg:
            backend = self.controller.get_backend()
            assert backend in {ASYNC_BACKEND, "trio"}
            
    @pytest.mark.anyio
    async def test_get_dashboard_endpoint(self):
        """Test that the dashboard endpoint returns the expected HTML."""
        response = self.client.get("/api/v0/webrtc/dashboard")
        assert response.status_code == 200
        assert "<h1>WebRTC Dashboard Test</h1>" in response.text
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        
    @pytest.mark.anyio
    async def test_get_connections_endpoint(self):
        """Test that the connections endpoint returns the expected data."""
        response = self.client.get("/api/v0/webrtc/connections")
        assert response.status_code == 200
        data = response.json()
        
        assert "connections" in data
        assert len(data["connections"]) == 2
        assert data["connections"][0]["connection_id"] == "test-conn-1"
        assert data["connections"][1]["connection_id"] == "test-conn-2"
        assert data["connections"][0]["content_cid"] == "QmTestCID1"
        assert data["connections"][1]["content_cid"] == "QmTestCID2"
        
    @pytest.mark.anyio
    async def test_get_operations_endpoint(self):
        """Test that the operations endpoint returns the expected data."""
        response = self.client.get("/api/v0/webrtc/operations")
        assert response.status_code == 200
        data = response.json()
        
        assert "operations" in data
        assert len(data["operations"]) == 2
        assert data["operations"][0]["operation"] == "stream_content"
        assert data["operations"][1]["operation"] == "close_connection"
        assert data["operations"][0]["connection_id"] == "test-conn-1"
        assert data["operations"][1]["connection_id"] == "test-conn-2"
        
    @pytest.mark.anyio
    async def test_get_tasks_endpoint(self):
        """Test that the tasks endpoint returns the expected data."""
        response = self.client.get("/api/v0/webrtc/tasks")
        assert response.status_code == 200
        data = response.json()
        
        assert "tasks" in data
        assert len(data["tasks"]) == 2
        assert data["tasks"][0]["task_id"] == "task-1"
        assert data["tasks"][1]["task_id"] == "task-2"
        assert data["tasks"][0]["name"] == "streaming"
        assert data["tasks"][1]["name"] == "buffer_handling"
        assert data["tasks"][0]["completed"] is False
        assert data["tasks"][1]["completed"] is True
        
    @pytest.mark.anyio
    async def test_test_connection_endpoint(self):
        """Test that the test_connection endpoint works correctly."""
        # Configure mock response
        response = self.client.post("/api/v0/webrtc/test_connection")
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "connection_id" in data
        assert data["message"] == "Test connection successful"
        
        # Verify the mock was used correctly
        assert len(self.mock_webrtc_monitor.connections) >= 3  # Original 2 plus new one
        
    @pytest.mark.anyio
    async def test_stream_content_endpoint(self):
        """Test that the stream_content endpoint works correctly."""
        # Configure mock response
        self.mock_webrtc_model.stream_content_webrtc.return_value = {
            "success": True,
            "connection_id": "test-stream-1",
            "message": "Streaming started"
        }
        
        # Make the request
        response = self.client.post(
            "/api/v0/webrtc/stream",
            json={"cid": "QmTestContent", "quality": 85}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["connection_id"] == "test-stream-1"
        assert data["message"] == "Streaming started successfully"
        
        # Verify the mock was called correctly
        self.mock_webrtc_model.stream_content_webrtc.assert_called_once()
        args, kwargs = self.mock_webrtc_model.stream_content_webrtc.call_args
        assert args[0] == "QmTestContent"
        assert kwargs["quality"] == 85
        
    @pytest.mark.anyio
    async def test_stream_content_error_handling(self):
        """Test error handling in the stream_content endpoint."""
        # Configure mock to raise an exception
        self.mock_webrtc_model.stream_content_webrtc.side_effect = Exception("Test error")
        
        # Make the request
        response = self.client.post(
            "/api/v0/webrtc/stream",
            json={"cid": "QmTestContent"}
        )
        
        assert response.status_code == 200  # API returns 200 even for errors
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert "Test error" in data["error"]
        
        # Verify error was recorded
        recorded_error = False
        for op in self.mock_webrtc_monitor.operations:
            if op["operation"] == "stream_content" and op["success"] is False:
                recorded_error = True
                break
                
        assert recorded_error
        
    @pytest.mark.anyio
    async def test_close_connection_endpoint(self):
        """Test that the close_connection endpoint works correctly."""
        # Configure mock response
        self.mock_webrtc_model.close_webrtc_connection.return_value = {
            "success": True,
            "connection_id": "test-conn-1"
        }
        
        # Make the request
        response = self.client.post("/api/v0/webrtc/close/test-conn-1")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "message" in data
        assert "test-conn-1" in data["message"]
        
        # Verify the mock was called correctly
        self.mock_webrtc_model.close_webrtc_connection.assert_called_once_with("test-conn-1")
        
    @pytest.mark.anyio
    async def test_close_all_connections_endpoint(self):
        """Test that the close_all_connections endpoint works correctly."""
        # Configure mock response
        self.mock_webrtc_model.close_all_webrtc_connections.return_value = {
            "success": True,
            "count": 2
        }
        
        # Make the request
        response = self.client.post("/api/v0/webrtc/close_all")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "message" in data
        assert "All connections closed" in data["message"]
        
        # Verify the mock was called correctly
        self.mock_webrtc_model.close_all_webrtc_connections.assert_called_once()
        
    @pytest.mark.anyio
    async def test_set_quality_endpoint(self):
        """Test that the set_quality endpoint works correctly."""
        # Configure mock response
        self.mock_webrtc_model.set_webrtc_quality.return_value = {
            "success": True,
            "connection_id": "test-conn-1",
            "quality": 75
        }
        
        # Make the request
        response = self.client.post(
            "/api/v0/webrtc/quality/test-conn-1",
            json={"quality": 75}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "message" in data
        assert "Quality set to 75" in data["message"]
        
        # Verify the mock was called correctly
        self.mock_webrtc_model.set_webrtc_quality.assert_called_once_with("test-conn-1", 75)
        
    @pytest.mark.anyio
    async def test_stream_test_content_endpoint(self):
        """Test that the stream_test_content endpoint works correctly."""
        # Configure mock response
        self.mock_webrtc_model.stream_content_webrtc.return_value = {
            "success": True,
            "connection_id": "test-stream-2"
        }
        
        # Make the request
        response = self.client.post("/api/v0/webrtc/stream_test_content")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["connection_id"] == "test-stream-2"
        
        # Verify the mock was called correctly
        self.mock_webrtc_model.stream_content_webrtc.assert_called_once()
        args, kwargs = self.mock_webrtc_model.stream_content_webrtc.call_args
        assert args[0] == "QmTest123"  # Test CID used in the endpoint
        
    @pytest.mark.anyio
    async def test_no_model_error_handling(self):
        """Test error handling when no WebRTC model is available."""
        # Create a controller with no model
        controller = WebRTCDashboardControllerAnyIO(
            webrtc_model=None,
            webrtc_monitor=self.mock_webrtc_monitor
        )
        
        # Create a router with the controller
        app = FastAPI()
        router = create_webrtc_dashboard_router_anyio(
            webrtc_model=None,
            webrtc_monitor=self.mock_webrtc_monitor
        )
        app.include_router(router)
        
        # Create a test client
        client = TestClient(app)
        
        # Test stream content endpoint
        response = client.post(
            "/api/v0/webrtc/stream",
            json={"cid": "QmTestContent"}
        )
        
        assert response.status_code == 200  # Should still return 200
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert "WebRTC model not available" in data["error"]
        
    @pytest.mark.anyio
    async def test_missing_cid_validation(self):
        """Test validation when CID is missing in stream request."""
        # Make the request without CID
        response = self.client.post(
            "/api/v0/webrtc/stream",
            json={"quality": 85}
        )
        
        assert response.status_code == 200  # Still returns 200 for API compatibility
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        assert "Content CID is required" in data["error"]
        
    @pytest.mark.anyio
    async def test_anyio_compatibility_with_sync_methods(self):
        """Test compatibility with sync methods when using AnyIO."""
        # Create a model with sync methods instead of async
        sync_model = MagicMock()
        sync_model.stream_content_webrtc = MagicMock(return_value={
            "success": True,
            "connection_id": "sync-test"
        })
        
        # Create a controller with the sync model
        controller = WebRTCDashboardControllerAnyIO(
            webrtc_model=sync_model,
            webrtc_monitor=self.mock_webrtc_monitor
        )
        
        # Create a router with the controller
        app = FastAPI()
        router = create_webrtc_dashboard_router_anyio(
            webrtc_model=sync_model,
            webrtc_monitor=self.mock_webrtc_monitor
        )
        app.include_router(router)
        
        # Create a test client
        client = TestClient(app)
        
        # Test stream content endpoint
        response = client.post(
            "/api/v0/webrtc/stream",
            json={"cid": "QmTestContent"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["connection_id"] == "sync-test"
        
        # Verify sync method was called
        sync_model.stream_content_webrtc.assert_called_once()