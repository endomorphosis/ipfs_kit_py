"""
Test suite for MCP Peer WebSocket Controller AnyIO version.

This module tests the functionality of the PeerWebSocketControllerAnyIO class
which provides asynchronous HTTP endpoints for WebSocket-based peer discovery
with AnyIO support.
"""

import pytest
import json
import time
import uuid
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI, APIRouter, WebSocket
from fastapi.testclient import TestClient

# Import the controller and models
from ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio import (
    PeerWebSocketControllerAnyIO, StartServerRequest, ConnectToServerRequest,
    PeerWebSocketResponse, StartServerResponse, ConnectToServerResponse,
    DiscoveredPeersResponse
)

# Mock implementation for testing
class MockPeerWebSocketControllerAnyIO(PeerWebSocketControllerAnyIO):
    """Mock version of PeerWebSocketControllerAnyIO for testing."""

    def __init__(self, ipfs_model=None):
        """Initialize with a mock model if not provided."""
        if ipfs_model is None:
            ipfs_model = MagicMock()

        # Call parent constructor with mocked dependencies
        with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.HAS_PEER_WEBSOCKET', True):
            with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.PeerInfo'):
                with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.PeerWebSocketServer'):
                    with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.PeerWebSocketClient'):
                        with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.register_peer_websocket'):
                            super().__init__(ipfs_model)

        # Override value after initialization
        self._has_peer_websocket = True

        # Create mock server and client
        self.peer_websocket_server = MagicMock()
        self.peer_websocket_server.connections = {}
        self.peer_websocket_server.peers = {}
        self.peer_websocket_server.start = AsyncMock(return_value=True)
        self.peer_websocket_server.stop = AsyncMock(return_value=True)

        self.peer_websocket_client = MagicMock()
        self.peer_websocket_client.start = AsyncMock(return_value=True)
        self.peer_websocket_client.stop = AsyncMock(return_value=True)
        self.peer_websocket_client.connect_to_discovery_server = AsyncMock(return_value=True)
        self.peer_websocket_client.get_discovered_peers = MagicMock(return_value=[
            MagicMock(
                peer_id="peer-1",
                multiaddrs=["/ip4/127.0.0.1/tcp/4001/p2p/peer-1"],
                role="worker",
                capabilities=["ipfs"],
                to_dict=lambda: {
                    "peer_id": "peer-1",
                    "multiaddrs": ["/ip4/127.0.0.1/tcp/4001/p2p/peer-1"],
                    "role": "worker",
                    "capabilities": ["ipfs"]
                }
            ),
            MagicMock(
                peer_id="peer-2",
                multiaddrs=["/ip4/127.0.0.1/tcp/4001/p2p/peer-2"],
                role="leecher",
                capabilities=["ipfs", "mcp"],
                to_dict=lambda: {
                    "peer_id": "peer-2",
                    "multiaddrs": ["/ip4/127.0.0.1/tcp/4001/p2p/peer-2"],
                    "role": "leecher",
                    "capabilities": ["ipfs", "mcp"]
                }
            )
        ])
        self.peer_websocket_client.get_peer_by_id = MagicMock(return_value=MagicMock(
            peer_id="peer-1",
            multiaddrs=["/ip4/127.0.0.1/tcp/4001/p2p/peer-1"],
            role="worker",
            capabilities=["ipfs"],
            to_dict=lambda: {
                "peer_id": "peer-1",
                "multiaddrs": ["/ip4/127.0.0.1/tcp/4001/p2p/peer-1"],
                "role": "worker",
                "capabilities": ["ipfs"]
            }
        ))

        # Create mock local peer info
        self.local_peer_info = MagicMock()
        self.local_peer_info.peer_id = "local-peer"
        self.local_peer_info.multiaddrs = ["/ip4/127.0.0.1/tcp/4001/p2p/local-peer"]
        self.local_peer_info.role = "master"
        self.local_peer_info.capabilities = ["ipfs", "mcp"]
        self.local_peer_info.to_dict = MagicMock(return_value={
            "peer_id": "local-peer",
            "multiaddrs": ["/ip4/127.0.0.1/tcp/4001/p2p/local-peer"],
            "role": "master",
            "capabilities": ["ipfs", "mcp"]
        })


class TestPeerWebSocketControllerAnyIOInitialization:
    """Test initialization and basic setup of PeerWebSocketControllerAnyIO."""

    def test_init_with_websocket_support(self):
        """Test controller initialization with WebSocket support."""
        # Create mock model
        mock_model = MagicMock()

        # Create controller with WebSocket support
        with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.HAS_PEER_WEBSOCKET', True):
            controller = PeerWebSocketControllerAnyIO(mock_model)

            # Verify initialization
            assert controller.ipfs_model == mock_model
            assert controller.peer_websocket_server is None
            assert controller.peer_websocket_client is None
            assert controller.local_peer_info is None

    def test_init_without_websocket_support(self):
        """Test controller initialization without WebSocket support."""
        # Create mock model
        mock_model = MagicMock()

        # Create controller without WebSocket support
        with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.HAS_PEER_WEBSOCKET', False):
            controller = PeerWebSocketControllerAnyIO(mock_model)

            # Verify initialization
            assert controller.ipfs_model == mock_model
            assert controller.peer_websocket_server is None
            assert controller.peer_websocket_client is None
            assert controller.local_peer_info is None

    def test_register_routes(self):
        """Test route registration."""
        # Create mock router and model
        mock_router = MagicMock(spec=APIRouter)
        mock_model = MagicMock()

        # Create controller and register routes
        with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.HAS_PEER_WEBSOCKET', True):
            with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.register_peer_websocket') as mock_register:
                controller = PeerWebSocketControllerAnyIO(mock_model)
                controller.register_routes(mock_router)

        # Verify routes were registered
        expected_routes = [
            "/peer/websocket/check",
            "/peer/websocket/server/start",
            "/peer/websocket/server/stop",
            "/peer/websocket/server/status",
            "/peer/websocket/client/connect",
            "/peer/websocket/client/disconnect",
            "/peer/websocket/peers",
            "/peer/websocket/peers/{peer_id}"
        ]

        # Check that all expected routes were registered
        call_args_list = mock_router.add_api_route.call_args_list
        registered_paths = [args[0][0] for args in call_args_list]

        for route in expected_routes:
            assert route in registered_paths, f"Route {route} was not registered"

    def test_get_backend(self):
        """Test get_backend method."""
        # Create controller with mock model
        controller = MockPeerWebSocketControllerAnyIO()

        # Test outside of async context
        assert controller.get_backend() is None

        # Can't easily test in async context here, will test in the TestPeerWebSocketControllerAnyIO class


@pytest.mark.anyio
class TestPeerWebSocketControllerAnyIO:
    """Test AnyIO-specific functionality of PeerWebSocketControllerAnyIO."""

    @pytest.fixture
    def mock_ipfs_model(self):
        """Create a mock IPFS model."""
        return MagicMock()

    @pytest.fixture
    def controller(self, mock_ipfs_model):
        """Create PeerWebSocketControllerAnyIO with mock model."""
        return MockPeerWebSocketControllerAnyIO(mock_ipfs_model)

    @pytest.fixture
    def app_client(self, controller):
        """Create FastAPI test client with controller routes."""
        app = FastAPI()
        router = APIRouter()
        controller.register_routes(router)
        app.include_router(router)
        return TestClient(app)

    @pytest.mark.anyio
    async def test_check_websocket_support(self, controller):
        """Test check_websocket_support method."""
        result = await controller.check_websocket_support()

        # Verify result
        assert result["success"] is True
        assert "operation_id" in result
        assert "timestamp" in result
        assert result["websocket_available"] is True

    @pytest.mark.anyio
    async def test_start_server(self, controller):
        """Test start_server method."""
        # Create request
        request = StartServerRequest(
            host="127.0.0.1",
            port=8765,
            max_peers=100,
            heartbeat_interval=30,
            peer_ttl=300,
            role="master",
            capabilities=["ipfs", "mcp"]
        )

        # Call method
        result = await controller.start_server(request)

        # Verify that server was started
        controller.peer_websocket_server.start.assert_awaited_once_with(
            host="127.0.0.1",
            port=8765
        )

        # Verify result
        assert result["success"] is True
        assert "operation_id" in result
        assert "timestamp" in result
        assert result["server_url"] == "ws://127.0.0.1:8765"
        assert "peer_info" in result

    @pytest.mark.anyio
    async def test_stop_server(self, controller):
        """Test stop_server method."""
        # Call method
        result = await controller.stop_server()

        # Verify that server was stopped
        controller.peer_websocket_server.stop.assert_awaited_once()

        # Verify result
        assert result["success"] is True
        assert "operation_id" in result
        assert "timestamp" in result
        assert "message" in result
        assert controller.peer_websocket_server is None

    @pytest.mark.anyio
    async def test_get_server_status(self, controller):
        """Test get_server_status method."""
        # Set up server with some connections and peers
        controller.peer_websocket_server.connections = {
            "conn1": MagicMock(),
            "conn2": MagicMock()
        }
        controller.peer_websocket_server.peers = {
            "peer1": MagicMock(),
            "peer2": MagicMock(),
            "peer3": MagicMock()
        }

        # Call method
        result = await controller.get_server_status()

        # Verify result
        assert result["success"] is True
        assert "operation_id" in result
        assert "timestamp" in result
        assert result["running"] is True
        assert result["peers_connected"] == 2
        assert result["known_peers"] == 3
        assert "local_peer" in result

    @pytest.mark.anyio
    async def test_connect_to_server(self, controller):
        """Test connect_to_server method."""
        # Create request
        request = ConnectToServerRequest(
            server_url="ws://example.com:8765",
            auto_connect=True,
            reconnect_interval=30,
            max_reconnect_attempts=5
        )

        # Call method
        result = await controller.connect_to_server(request)

        # Verify that client was started and connected
        controller.peer_websocket_client.start.assert_awaited_once()
        controller.peer_websocket_client.connect_to_discovery_server.assert_awaited_once_with(
            "ws://example.com:8765"
        )

        # Verify result
        assert result["success"] is True
        assert "operation_id" in result
        assert "timestamp" in result
        assert result["connected"] is True
        assert result["server_url"] == "ws://example.com:8765"

    @pytest.mark.anyio
    async def test_disconnect_from_server(self, controller):
        """Test disconnect_from_server method."""
        # Call method
        result = await controller.disconnect_from_server()

        # Verify that client was stopped
        controller.peer_websocket_client.stop.assert_awaited_once()

        # Verify result
        assert result["success"] is True
        assert "operation_id" in result
        assert "timestamp" in result
        assert "message" in result
        assert controller.peer_websocket_client is None

    @pytest.mark.anyio
    async def test_get_discovered_peers(self, controller):
        """Test get_discovered_peers method."""
        # Call method without filters
        result = await controller.get_discovered_peers()

        # Verify that peers were retrieved
        controller.peer_websocket_client.get_discovered_peers.assert_called_once_with(
            filter_role=None,
            filter_capabilities=None
        )

        # Verify result
        assert result["success"] is True
        assert "operation_id" in result
        assert "timestamp" in result
        assert "peers" in result
        assert len(result["peers"]) == 2
        assert result["count"] == 2

        # Call method with filters
        controller.peer_websocket_client.get_discovered_peers.reset_mock()
        result = await controller.get_discovered_peers(filter_role="worker", filter_capabilities="ipfs,mcp")

        # Verify that peers were retrieved with filters
        controller.peer_websocket_client.get_discovered_peers.assert_called_once_with(
            filter_role="worker",
            filter_capabilities=["ipfs", "mcp"]
        )

    @pytest.mark.anyio
    async def test_get_peer_by_id(self, controller):
        """Test get_peer_by_id method."""
        # Call method
        result = await controller.get_peer_by_id("peer-1")

        # Verify that peer was retrieved
        controller.peer_websocket_client.get_peer_by_id.assert_called_once_with("peer-1")

        # Verify result
        assert result["success"] is True
        assert "operation_id" in result
        assert "timestamp" in result
        assert "peer" in result
        assert result["peer"]["peer_id"] == "peer-1"

    @pytest.mark.anyio
    async def test_get_peer_by_id_not_found(self, controller):
        """Test get_peer_by_id method with non-existent peer."""
        # Mock get_peer_by_id to return None
        controller.peer_websocket_client.get_peer_by_id.return_value = None

        # Call method
        result = await controller.get_peer_by_id("nonexistent-peer")

        # Verify result
        assert result["success"] is False
        assert "operation_id" in result
        assert "timestamp" in result
        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.anyio
    async def test_shutdown(self, controller):
        """Test shutdown method."""
        # Call method
        await controller.shutdown()

        # Verify that server and client were stopped
        controller.peer_websocket_server.stop.assert_awaited_once()
        controller.peer_websocket_client.stop.assert_awaited_once()

        # Verify resources were cleaned up
        assert controller.peer_websocket_server is None
        assert controller.peer_websocket_client is None


@pytest.mark.skip("HTTP endpoint tests requiring complex setup")
class TestPeerWebSocketControllerAnyIOHTTPEndpoints:
    """Test HTTP endpoints of PeerWebSocketControllerAnyIO."""

    @pytest.fixture
    def mock_ipfs_model(self):
        """Create a mock IPFS model."""
        return MagicMock()

    @pytest.fixture
    def app_client(self, mock_ipfs_model):
        """Create FastAPI test client with controller routes."""
        app = FastAPI()
        router = APIRouter()

        # Create controller with mocked WebSocket support
        with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.HAS_PEER_WEBSOCKET', True):
            with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.register_peer_websocket'):
                controller = MockPeerWebSocketControllerAnyIO(mock_ipfs_model)
                controller.register_routes(router)

        app.include_router(router)
        return TestClient(app)

    def test_check_websocket_support_endpoint(self, app_client):
        """Test /peer/websocket/check endpoint."""
        response = app_client.get("/peer/websocket/check")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "websocket_available" in data

    def test_start_server_endpoint(self, app_client):
        """Test /peer/websocket/server/start endpoint."""
        response = app_client.post(
            "/peer/websocket/server/start",
            json={
                "host": "127.0.0.1",
                "port": 8765,
                "max_peers": 100,
                "heartbeat_interval": 30,
                "peer_ttl": 300,
                "role": "master",
                "capabilities": ["ipfs", "mcp"]
            }
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "server_url" in data
        assert "peer_info" in data

    def test_stop_server_endpoint(self, app_client):
        """Test /peer/websocket/server/stop endpoint."""
        response = app_client.post("/peer/websocket/server/stop")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "message" in data

    def test_get_server_status_endpoint(self, app_client):
        """Test /peer/websocket/server/status endpoint."""
        response = app_client.get("/peer/websocket/server/status")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "running" in data

    def test_connect_to_server_endpoint(self, app_client):
        """Test /peer/websocket/client/connect endpoint."""
        response = app_client.post(
            "/peer/websocket/client/connect",
            json={
                "server_url": "ws://example.com:8765",
                "auto_connect": True,
                "reconnect_interval": 30,
                "max_reconnect_attempts": 5
            }
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["connected"] is True
        assert data["server_url"] == "ws://example.com:8765"

    def test_disconnect_from_server_endpoint(self, app_client):
        """Test /peer/websocket/client/disconnect endpoint."""
        response = app_client.post("/peer/websocket/client/disconnect")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "message" in data

    def test_get_discovered_peers_endpoint(self, app_client):
        """Test /peer/websocket/peers endpoint."""
        response = app_client.get("/peer/websocket/peers")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "peers" in data
        assert len(data["peers"]) == 2
        assert data["count"] == 2

    def test_get_discovered_peers_with_filters_endpoint(self, app_client):
        """Test /peer/websocket/peers endpoint with filters."""
        response = app_client.get("/peer/websocket/peers?filter_role=worker&filter_capabilities=ipfs,mcp")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "peers" in data

    def test_get_peer_by_id_endpoint(self, app_client):
        """Test /peer/websocket/peers/{peer_id} endpoint."""
        response = app_client.get("/peer/websocket/peers/peer-1")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "peer" in data
        assert data["peer"]["peer_id"] == "peer-1"

    def test_get_peer_by_id_not_found_endpoint(self, app_client):
        """Test /peer/websocket/peers/{peer_id} endpoint with non-existent peer."""
        # Need to modify the mock controller to return None for this specific peer ID
        # This is more complex in HTTP tests, so we'll skip the implementation


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
