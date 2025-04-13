"""
Test suite for MCP Peer Websocket Controller.

This module tests the functionality of the PeerWebSocketController class
which provides HTTP and WebSocket endpoints for peer discovery.
"""

import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI, APIRouter
from starlette.websockets import WebSocket, WebSocketDisconnect # Correct import
from fastapi.testclient import TestClient
from pydantic import BaseModel

# Import the controller class
try:
    from ipfs_kit_py.mcp.controllers.peer_websocket_controller import PeerWebSocketController
except ImportError:
    # If AnyIO migration has occurred, import from the AnyIO version
    from ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio import PeerWebSocketController


class TestPeerWebSocketControllerInitialization:
    """Test initialization and route registration of PeerWebSocketController."""

    def test_init_with_websocket_support(self):
        """Test controller initialization with WebSocket support."""
        # Mock PeerWebSocketModel
        mock_model = MagicMock()
        
        # Mock that websocket support is available
        with patch("ipfs_kit_py.mcp.controllers.peer_websocket_controller.PeerWebSocketController._check_dependencies", 
                  return_value=True):
            controller = PeerWebSocketController(mock_model)
            
            # Verify controller is initialized correctly
            assert controller.peer_websocket_model == mock_model
            assert controller._has_dependencies is True
    
    def test_init_without_websocket_support(self):
        """Test controller initialization without WebSocket support."""
        # Mock PeerWebSocketModel
        mock_model = MagicMock()
        
        # Mock that websocket support is not available
        with patch("ipfs_kit_py.mcp.controllers.peer_websocket_controller.PeerWebSocketController._check_dependencies", 
                  return_value=False):
            controller = PeerWebSocketController(mock_model)
            
            # Verify controller is initialized correctly
            assert controller.peer_websocket_model == mock_model
            assert controller._has_dependencies is False
    
    def test_route_registration(self):
        """Test that all routes are registered correctly."""
        # Mock PeerWebSocketModel and router
        mock_model = MagicMock()
        mock_router = MagicMock(spec=APIRouter)
        
        # Initialize controller and register routes
        controller = PeerWebSocketController(mock_model)
        controller.register_routes(mock_router)
        
        # Verify that add_api_route was called for each endpoint
        expected_routes = [
            # Check routes
            "/peer/websocket/check",
            
            # Server routes
            "/peer/websocket/server/start",
            "/peer/websocket/server/stop",
            "/peer/websocket/server/status",
            
            # Client routes
            "/peer/websocket/client/connect",
            "/peer/websocket/client/disconnect",
            
            # Peer routes
            "/peer/websocket/peers",
            "/peer/websocket/peers/{peer_id}"
        ]
        
        route_calls = [call.args[0] for call in mock_router.add_api_route.call_args_list]
        websocket_calls = [call.args[0] for call in mock_router.add_websocket_route.call_args_list]
        
        # Verify expected route registrations
        for route in expected_routes:
            assert any(route in call for call in route_calls), f"Route {route} was not registered"
        
        # Verify websocket endpoint is registered
        assert "/peer/websocket" in websocket_calls or any("/peer/websocket" in call for call in route_calls), \
            "WebSocket endpoint was not registered"


class TestPeerWebSocketServerOperations:
    """Test server-related operations for PeerWebSocketController."""
    
    @pytest.fixture
    def controller_with_app(self):
        """Create a controller with a FastAPI app for testing HTTP endpoints."""
        # Create FastAPI app and router
        app = FastAPI()
        router = APIRouter()
        
        # Mock PeerWebSocketModel
        mock_model = MagicMock()
        
        # Set up mock server operations
        mock_model.start_server.return_value = {
            "success": True,
            "message": "Server started successfully",
            "server_info": {
                "host": "127.0.0.1",
                "port": 8765,
                "is_running": True,
                "connected_peers": 0,
                "max_peers": 10
            }
        }
        
        mock_model.stop_server.return_value = {
            "success": True,
            "message": "Server stopped successfully"
        }
        
        mock_model.get_server_status.return_value = {
            "success": True,
            "server_info": {
                "host": "127.0.0.1",
                "port": 8765,
                "is_running": True,
                "connected_peers": 2,
                "max_peers": 10,
                "uptime_seconds": 120
            }
        }
        
        # Initialize controller with mock dependencies check
        with patch("ipfs_kit_py.mcp.controllers.peer_websocket_controller.PeerWebSocketController._check_dependencies", 
                  return_value=True):
            controller = PeerWebSocketController(mock_model)
            controller.register_routes(router)
            
            # Mount router to app
            app.include_router(router, prefix="/api/v0")
            
            # Create test client
            client = TestClient(app)
            
            return {
                "app": app,
                "client": client,
                "controller": controller,
                "model": mock_model
            }
    
    def test_check_websocket_support(self, controller_with_app):
        """Test the endpoint to check WebSocket support."""
        client = controller_with_app["client"]
        
        # Test with WebSocket support
        response = client.get("/api/v0/peer/websocket/check")
        assert response.status_code == 200
        assert response.json() == {"websocket_support": True}
        
        # Modify controller to test without WebSocket support
        controller_with_app["controller"]._has_dependencies = False
        response = client.get("/api/v0/peer/websocket/check")
        assert response.status_code == 200
        assert response.json() == {"websocket_support": False}
    
    def test_start_server(self, controller_with_app):
        """Test starting the WebSocket server."""
        client = controller_with_app["client"]
        model = controller_with_app["model"]
        
        # Test starting server with default parameters
        response = client.post("/api/v0/peer/websocket/server/start")
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "server_info" in response.json()
        
        # Verify model method was called with default parameters
        model.start_server.assert_called_once()
        
        # Test starting server with custom parameters
        model.start_server.reset_mock()
        response = client.post(
            "/api/v0/peer/websocket/server/start",
            json={
                "host": "0.0.0.0",
                "port": 9000,
                "max_peers": 20,
                "node_role": "worker",
                "capabilities": ["storage", "processing"]
            }
        )
        assert response.status_code == 200
        
        # Verify model method was called with custom parameters
        call_kwargs = model.start_server.call_args.kwargs
        assert call_kwargs["host"] == "0.0.0.0"
        assert call_kwargs["port"] == 9000
        assert call_kwargs["max_peers"] == 20
        assert call_kwargs["node_role"] == "worker"
        assert call_kwargs["capabilities"] == ["storage", "processing"]
    
    def test_stop_server(self, controller_with_app):
        """Test stopping the WebSocket server."""
        client = controller_with_app["client"]
        model = controller_with_app["model"]
        
        # Test stopping server
        response = client.post("/api/v0/peer/websocket/server/stop")
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "message" in response.json()
        
        # Verify model method was called
        model.stop_server.assert_called_once()
    
    def test_get_server_status(self, controller_with_app):
        """Test getting the WebSocket server status."""
        client = controller_with_app["client"]
        model = controller_with_app["model"]
        
        # Test getting server status
        response = client.get("/api/v0/peer/websocket/server/status")
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "server_info" in response.json()
        
        # Verify model method was called
        model.get_server_status.assert_called_once()
        
        # Test server status when model returns error
        model.get_server_status.return_value = {
            "success": False,
            "error": "Server not running",
            "error_type": "server_error"
        }
        
        response = client.get("/api/v0/peer/websocket/server/status")
        assert response.status_code == 200  # Still 200 as the model returns structured error
        assert response.json()["success"] is False
        assert "error" in response.json()
    
    def test_start_server_without_websocket_support(self, controller_with_app):
        """Test starting server without WebSocket support."""
        client = controller_with_app["client"]
        controller_with_app["controller"]._has_dependencies = False
        
        # Test starting server without WebSocket support
        response = client.post("/api/v0/peer/websocket/server/start")
        assert response.status_code == 400  # Bad request
        assert response.json()["detail"].startswith("WebSocket support is not available")


class TestPeerWebSocketClientOperations:
    """Test client-related operations for PeerWebSocketController."""
    
    @pytest.fixture
    def controller_with_app(self):
        """Create a controller with a FastAPI app for testing client HTTP endpoints."""
        # Create FastAPI app and router
        app = FastAPI()
        router = APIRouter()
        
        # Mock PeerWebSocketModel
        mock_model = MagicMock()
        
        # Set up mock client operations
        mock_model.connect_to_server.return_value = {
            "success": True,
            "message": "Connected to server successfully",
            "connection_info": {
                "server_url": "ws://127.0.0.1:8765",
                "connected": True,
                "peer_id": "client123",
                "auto_reconnect": True
            }
        }
        
        mock_model.disconnect_from_server.return_value = {
            "success": True,
            "message": "Disconnected from server successfully"
        }
        
        # Initialize controller with mock dependencies check
        with patch("ipfs_kit_py.mcp.controllers.peer_websocket_controller.PeerWebSocketController._check_dependencies", 
                  return_value=True):
            controller = PeerWebSocketController(mock_model)
            controller.register_routes(router)
            
            # Mount router to app
            app.include_router(router, prefix="/api/v0")
            
            # Create test client
            client = TestClient(app)
            
            return {
                "app": app,
                "client": client,
                "controller": controller,
                "model": mock_model
            }
    
    def test_connect_to_server(self, controller_with_app):
        """Test connecting to a WebSocket server."""
        client = controller_with_app["client"]
        model = controller_with_app["model"]
        
        # Test connecting with default parameters
        response = client.post(
            "/api/v0/peer/websocket/client/connect",
            json={"server_url": "ws://example.com:8765"}
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "connection_info" in response.json()
        
        # Verify model method was called with correct parameters
        call_kwargs = model.connect_to_server.call_args.kwargs
        assert call_kwargs["server_url"] == "ws://example.com:8765"
        
        # Test connecting with custom parameters
        model.connect_to_server.reset_mock()
        response = client.post(
            "/api/v0/peer/websocket/client/connect",
            json={
                "server_url": "ws://example.com:9000",
                "auto_reconnect": True,
                "reconnect_interval": 30,
                "node_role": "worker",
                "capabilities": ["storage", "compute"]
            }
        )
        assert response.status_code == 200
        
        # Verify model method was called with custom parameters
        call_kwargs = model.connect_to_server.call_args.kwargs
        assert call_kwargs["server_url"] == "ws://example.com:9000"
        assert call_kwargs["auto_reconnect"] is True
        assert call_kwargs["reconnect_interval"] == 30
        assert call_kwargs["node_role"] == "worker"
        assert call_kwargs["capabilities"] == ["storage", "compute"]
    
    def test_connect_without_server_url(self, controller_with_app):
        """Test connection attempt without server URL."""
        client = controller_with_app["client"]
        
        # Test connecting without server_url
        response = client.post("/api/v0/peer/websocket/client/connect", json={})
        assert response.status_code == 422  # Unprocessable entity (validation error)
    
    def test_disconnect_from_server(self, controller_with_app):
        """Test disconnecting from a WebSocket server."""
        client = controller_with_app["client"]
        model = controller_with_app["model"]
        
        # Test disconnecting
        response = client.post("/api/v0/peer/websocket/client/disconnect")
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "message" in response.json()
        
        # Verify model method was called
        model.disconnect_from_server.assert_called_once()
    
    def test_connect_without_websocket_support(self, controller_with_app):
        """Test connecting without WebSocket support."""
        client = controller_with_app["client"]
        controller_with_app["controller"]._has_dependencies = False
        
        # Test connecting without WebSocket support
        response = client.post(
            "/api/v0/peer/websocket/client/connect",
            json={"server_url": "ws://example.com:8765"}
        )
        assert response.status_code == 400  # Bad request
        assert response.json()["detail"].startswith("WebSocket support is not available")


class TestPeerDiscoveryOperations:
    """Test peer discovery operations for PeerWebSocketController."""
    
    @pytest.fixture
    def controller_with_app(self):
        """Create a controller with a FastAPI app for testing peer discovery endpoints."""
        # Create FastAPI app and router
        app = FastAPI()
        router = APIRouter()
        
        # Mock PeerWebSocketModel
        mock_model = MagicMock()
        
        # Set up mock peer operations
        mock_model.get_discovered_peers.return_value = {
            "success": True,
            "peers": [
                {
                    "id": "peer1",
                    "address": "127.0.0.1",
                    "port": 8765,
                    "role": "master",
                    "capabilities": ["storage", "processing"],
                    "last_seen": 1622547750.123,
                    "metadata": {"version": "1.0.0"}
                },
                {
                    "id": "peer2",
                    "address": "192.168.1.10",
                    "port": 8765,
                    "role": "worker",
                    "capabilities": ["storage"],
                    "last_seen": 1622547740.456,
                    "metadata": {"version": "1.0.0"}
                }
            ],
            "total": 2
        }
        
        mock_model.get_peer_by_id.return_value = {
            "success": True,
            "peer": {
                "id": "peer1",
                "address": "127.0.0.1",
                "port": 8765,
                "role": "master",
                "capabilities": ["storage", "processing"],
                "last_seen": 1622547750.123,
                "metadata": {"version": "1.0.0"},
                "connection_info": {
                    "connected": True,
                    "latency_ms": 15,
                    "connection_time": 1622547700.789
                }
            }
        }
        
        # Initialize controller with mock dependencies check
        with patch("ipfs_kit_py.mcp.controllers.peer_websocket_controller.PeerWebSocketController._check_dependencies", 
                  return_value=True):
            controller = PeerWebSocketController(mock_model)
            controller.register_routes(router)
            
            # Mount router to app
            app.include_router(router, prefix="/api/v0")
            
            # Create test client
            client = TestClient(app)
            
            return {
                "app": app,
                "client": client,
                "controller": controller,
                "model": mock_model
            }
    
    def test_get_discovered_peers(self, controller_with_app):
        """Test retrieving discovered peers."""
        client = controller_with_app["client"]
        model = controller_with_app["model"]
        
        # Test getting all peers
        response = client.get("/api/v0/peer/websocket/peers")
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert len(response.json()["peers"]) == 2
        
        # Verify model method was called with no filters
        model.get_discovered_peers.assert_called_with()
        
        # Test with role filter
        model.get_discovered_peers.reset_mock()
        response = client.get("/api/v0/peer/websocket/peers?role=worker")
        assert response.status_code == 200
        
        # Verify model method was called with role filter
        model.get_discovered_peers.assert_called_with(role="worker")
        
        # Test with capabilities filter
        model.get_discovered_peers.reset_mock()
        response = client.get("/api/v0/peer/websocket/peers?capabilities=storage")
        assert response.status_code == 200
        
        # Verify model method was called with capabilities filter
        model.get_discovered_peers.assert_called_with(capabilities=["storage"])
        
        # Test with both filters
        model.get_discovered_peers.reset_mock()
        response = client.get("/api/v0/peer/websocket/peers?role=worker&capabilities=storage,processing")
        assert response.status_code == 200
        
        # Verify model method was called with both filters
        model.get_discovered_peers.assert_called_with(role="worker", capabilities=["storage", "processing"])
    
    def test_get_peer_by_id(self, controller_with_app):
        """Test retrieving a specific peer by ID."""
        client = controller_with_app["client"]
        model = controller_with_app["model"]
        
        # Test getting existing peer
        response = client.get("/api/v0/peer/websocket/peers/peer1")
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["peer"]["id"] == "peer1"
        
        # Verify model method was called with correct peer_id
        model.get_peer_by_id.assert_called_with(peer_id="peer1")
        
        # Test getting non-existent peer
        model.get_peer_by_id.return_value = {
            "success": False,
            "error": "Peer not found",
            "error_type": "not_found"
        }
        
        response = client.get("/api/v0/peer/websocket/peers/nonexistent")
        assert response.status_code == 404  # Not found
        assert response.json()["detail"] == "Peer not found"
    
    def test_peer_operations_without_websocket_support(self, controller_with_app):
        """Test peer operations without WebSocket support."""
        client = controller_with_app["client"]
        controller_with_app["controller"]._has_dependencies = False
        
        # Test getting peers without WebSocket support
        response = client.get("/api/v0/peer/websocket/peers")
        assert response.status_code == 400  # Bad request
        assert response.json()["detail"].startswith("WebSocket support is not available")
        
        # Test getting specific peer without WebSocket support
        response = client.get("/api/v0/peer/websocket/peers/peer1")
        assert response.status_code == 400  # Bad request
        assert response.json()["detail"].startswith("WebSocket support is not available")


@pytest.mark.anyio
class TestPeerWebSocketControllerAnyIO:
    """Test suite for the AnyIO version of the PeerWebSocketController."""
    
    @pytest.fixture
    async def async_controller(self):
        """Create a controller with async model for AnyIO testing."""
        # Mock PeerWebSocketModel with async methods
        mock_model = AsyncMock()
        
        # Set up mock server/client operations
        mock_model.start_server.return_value = {
            "success": True,
            "message": "Server started successfully",
            "server_info": {
                "host": "127.0.0.1",
                "port": 8765,
                "is_running": True
            }
        }
        
        mock_model.get_discovered_peers.return_value = {
            "success": True,
            "peers": [
                {
                    "id": "peer1",
                    "role": "master",
                    "last_seen": 1622547750.123
                }
            ]
        }
        
        # Initialize controller with mock dependencies check
        with patch("ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.PeerWebSocketController._check_dependencies", 
                  return_value=True):
            controller = PeerWebSocketController(mock_model)
            
            return {
                "controller": controller,
                "model": mock_model
            }
    
    @pytest.mark.anyio
    async def test_async_start_server(self, async_controller):
        """Test async version of start_server method."""
        controller = async_controller["controller"]
        model = async_controller["model"]
        
        # Call the async method directly
        result = await controller.start_server(
            host="0.0.0.0",
            port=9000,
            max_peers=20
        )
        
        # Verify result
        assert result["success"] is True
        assert "server_info" in result
        
        # Verify model method was called with correct parameters
        call_kwargs = model.start_server.call_args.kwargs
        assert call_kwargs["host"] == "0.0.0.0"
        assert call_kwargs["port"] == 9000
        assert call_kwargs["max_peers"] == 20
    
    @pytest.mark.anyio
    async def test_async_get_discovered_peers(self, async_controller):
        """Test async version of get_discovered_peers method."""
        controller = async_controller["controller"]
        model = async_controller["model"]
        
        # Call the async method directly
        result = await controller.get_discovered_peers(
            role="worker",
            capabilities=["storage"]
        )
        
        # Verify result
        assert result["success"] is True
        
        # Verify model method was called with correct parameters
        call_kwargs = model.get_discovered_peers.call_args.kwargs
        assert call_kwargs["role"] == "worker"
        assert call_kwargs["capabilities"] == ["storage"]
    
    @pytest.mark.anyio
    async def test_async_websocket_handler(self, async_controller):
        """Test async WebSocket endpoint handler."""
        controller = async_controller["controller"]
        
        # Create mock WebSocket
        mock_websocket = AsyncMock()
        
        # Mock the model's handle_websocket method
        async_controller["model"].handle_websocket.return_value = {
            "success": True,
            "message": "WebSocket connection handled successfully"
        }
        
        # Test successful WebSocket handling
        await controller.websocket_endpoint(mock_websocket)
        
        # Verify model's handle_websocket was called with the websocket
        async_controller["model"].handle_websocket.assert_called_once_with(mock_websocket)
        
        # Test WebSocket exception handling
        async_controller["model"].handle_websocket.reset_mock()
        async_controller["model"].handle_websocket.side_effect = WebSocketDisconnect(code=1000)
        
        # Should handle the exception without errors
        await controller.websocket_endpoint(mock_websocket)
        
        # Verify model's handle_websocket was called
        async_controller["model"].handle_websocket.assert_called_once_with(mock_websocket)


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
