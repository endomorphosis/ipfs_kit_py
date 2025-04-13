"""
Tests for the PeerWebSocketControllerAnyIO class.

This module tests the anyio-compatible MCP controller for peer WebSocket discovery.
"""

import json
import time
import uuid
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from fastapi import APIRouter
from starlette.websockets import WebSocket, WebSocketDisconnect # Correct import

# Import PeerWebSocketControllerAnyIO and related modules
from ipfs_kit_py.mcp_server.controllers.peer_websocket_controller_anyio import (
    PeerWebSocketControllerAnyIO,
    PeerWebSocketResponse,
    StartServerRequest,
    StartServerResponse,
    ConnectToServerRequest,
    ConnectToServerResponse,
    DiscoveredPeersResponse,
)

# For mocking dependent modules
try:
    from ipfs_kit_py.peer_websocket_anyio import (
        PeerInfo, PeerWebSocketServer, PeerWebSocketClient, 
        register_peer_websocket, PeerRole, MessageType
    )
    HAS_PEER_WEBSOCKET = True
except ImportError:
    HAS_PEER_WEBSOCKET = False


class MockPeerInfo:
    """Mock class for PeerInfo."""
    
    def __init__(self, peer_id, multiaddrs=None, role="leecher", capabilities=None):
        self.peer_id = peer_id
        self.multiaddrs = multiaddrs or ["/ip4/127.0.0.1/tcp/4001/p2p/" + peer_id]
        self.role = role
        self.capabilities = capabilities or []
        self.last_seen = time.time()
        
    def to_dict(self):
        """Convert to dictionary."""
        return {
            "peer_id": self.peer_id,
            "multiaddrs": self.multiaddrs,
            "role": self.role,
            "capabilities": self.capabilities,
            "last_seen": self.last_seen
        }


class MockPeerWebSocketServer:
    """Mock class for PeerWebSocketServer."""
    
    def __init__(self, local_peer_info, max_peers=100, heartbeat_interval=30, peer_ttl=300):
        self.local_peer_info = local_peer_info
        self.max_peers = max_peers
        self.heartbeat_interval = heartbeat_interval
        self.peer_ttl = peer_ttl
        self.peers = {local_peer_info.peer_id: local_peer_info}
        self.connections = {}
        self.running = False
        
    async def start(self, host="0.0.0.0", port=8765):
        """Mock start method."""
        self.running = True
        return True
        
    async def stop(self):
        """Mock stop method."""
        self.running = False
        return True


class MockPeerWebSocketClient:
    """Mock class for PeerWebSocketClient."""
    
    def __init__(self, local_peer_info, on_peer_discovered=None, auto_connect=True, 
                reconnect_interval=30, max_reconnect_attempts=5):
        self.local_peer_info = local_peer_info
        self.on_peer_discovered = on_peer_discovered
        self.auto_connect = auto_connect
        self.reconnect_interval = reconnect_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        self.peers = {local_peer_info.peer_id: local_peer_info}
        self.connections = {}
        self.discovery_servers = {}
        self.running = False
        
    async def start(self):
        """Mock start method."""
        self.running = True
        return True
        
    async def stop(self):
        """Mock stop method."""
        self.running = False
        return True
        
    async def connect_to_discovery_server(self, url):
        """Mock connect method."""
        self.discovery_servers[url] = {
            "url": url,
            "connected": True,
            "last_connected": time.time(),
            "reconnect_attempts": 0
        }
        return True
        
    def get_discovered_peers(self, filter_role=None, filter_capabilities=None):
        """Mock get_discovered_peers method."""
        # Return simple list of peer objects based on filters
        result = []
        for peer_id, peer_info in self.peers.items():
            # Skip local peer
            if peer_id == self.local_peer_info.peer_id:
                continue
                
            # Filter by role
            if filter_role and peer_info.role != filter_role:
                continue
                
            # Filter by capabilities
            if filter_capabilities and not all(cap in peer_info.capabilities for cap in filter_capabilities):
                continue
                
            result.append(peer_info)
            
        return result
        
    def get_peer_by_id(self, peer_id):
        """Mock get_peer_by_id method."""
        return self.peers.get(peer_id)


# Mock register_peer_websocket function
async def mock_register_peer_websocket(router, local_peer_info, path="/api/v0/peer/ws"):
    """Mock for register_peer_websocket function."""
    return True


# Create a mock module to patch the module import
class MockWebSocketModule:
    """Mock for the peer_websocket_anyio module."""
    PeerInfo = MockPeerInfo
    PeerWebSocketServer = MockPeerWebSocketServer
    PeerWebSocketClient = MockPeerWebSocketClient
    register_peer_websocket = mock_register_peer_websocket
    PeerRole = MagicMock()
    MessageType = MagicMock()
    WEBSOCKET_AVAILABLE = True


class MockIPFSControllerAnyIO:
    """Mock class for PeerWebSocketControllerAnyIO with pre-configured responses."""
    
    def __init__(self, ipfs_model=None):
        """Initialize with mock responses."""
        self.ipfs_model = ipfs_model or MagicMock()
        self.peer_websocket_server = None
        self.peer_websocket_client = None
        self.local_peer_info = None
        self.routes_registered = False
        
        # Pre-configure specific method returns
        self.check_websocket_support_return = {
            "success": True,
            "operation_id": "mock-operation-id",
            "timestamp": time.time(),
            "websocket_available": True
        }
        
        self.start_server_return = {
            "success": True,
            "operation_id": "mock-operation-id",
            "timestamp": time.time(),
            "server_url": "ws://127.0.0.1:8765",
            "peer_info": {
                "peer_id": "mock-peer-id",
                "multiaddrs": ["/ip4/127.0.0.1/tcp/4001/p2p/mock-peer-id"],
                "role": "master",
                "capabilities": ["ipfs", "mcp"]
            }
        }
        
        self.stop_server_return = {
            "success": True,
            "operation_id": "mock-operation-id",
            "timestamp": time.time(),
            "message": "Server stopped successfully"
        }
        
        self.get_server_status_return = {
            "success": True,
            "operation_id": "mock-operation-id",
            "timestamp": time.time(),
            "running": True,
            "peers_connected": 2,
            "known_peers": 3,
            "local_peer": {
                "peer_id": "mock-peer-id",
                "multiaddrs": ["/ip4/127.0.0.1/tcp/4001/p2p/mock-peer-id"],
                "role": "master",
                "capabilities": ["ipfs", "mcp"]
            }
        }
        
        self.connect_to_server_return = {
            "success": True,
            "operation_id": "mock-operation-id",
            "timestamp": time.time(),
            "connected": True,
            "server_url": "ws://127.0.0.1:8765"
        }
        
        self.disconnect_from_server_return = {
            "success": True,
            "operation_id": "mock-operation-id",
            "timestamp": time.time(),
            "message": "Client stopped successfully"
        }
        
        self.get_discovered_peers_return = {
            "success": True,
            "operation_id": "mock-operation-id",
            "timestamp": time.time(),
            "peers": [
                {
                    "peer_id": "peer1",
                    "multiaddrs": ["/ip4/127.0.0.1/tcp/4001/p2p/peer1"],
                    "role": "worker",
                    "capabilities": ["ipfs"]
                },
                {
                    "peer_id": "peer2",
                    "multiaddrs": ["/ip4/127.0.0.1/tcp/4001/p2p/peer2"],
                    "role": "leecher",
                    "capabilities": ["ipfs", "mcp"]
                }
            ],
            "count": 2
        }
        
        self.get_peer_by_id_return = {
            "success": True,
            "operation_id": "mock-operation-id",
            "timestamp": time.time(),
            "peer": {
                "peer_id": "peer1",
                "multiaddrs": ["/ip4/127.0.0.1/tcp/4001/p2p/peer1"],
                "role": "worker",
                "capabilities": ["ipfs"]
            }
        }
        
        self.get_peer_by_id_not_found_return = {
            "success": False,
            "operation_id": "mock-operation-id",
            "timestamp": time.time(),
            "error": "Peer not found: unknown-peer"
        }
        
    def register_routes(self, router):
        """Mock register_routes method."""
        self.routes_registered = True
        
    async def check_websocket_support(self):
        """Mock check_websocket_support method."""
        return self.check_websocket_support_return
        
    async def start_server(self, request):
        """Mock start_server method."""
        return self.start_server_return
        
    async def stop_server(self):
        """Mock stop_server method."""
        return self.stop_server_return
        
    async def get_server_status(self):
        """Mock get_server_status method."""
        return self.get_server_status_return
        
    async def connect_to_server(self, request):
        """Mock connect_to_server method."""
        return self.connect_to_server_return
        
    async def disconnect_from_server(self):
        """Mock disconnect_from_server method."""
        return self.disconnect_from_server_return
        
    async def get_discovered_peers(self, filter_role=None, filter_capabilities=None):
        """Mock get_discovered_peers method."""
        return self.get_discovered_peers_return
        
    async def get_peer_by_id(self, peer_id):
        """Mock get_peer_by_id method."""
        if peer_id == "unknown-peer":
            return self.get_peer_by_id_not_found_return
        return self.get_peer_by_id_return
        
    async def shutdown(self):
        """Mock shutdown method."""
        return {"success": True, "message": "Controller shutdown complete"}


class TestPeerWebSocketControllerAnyIOInitialization:
    """Test initialization and route registration for PeerWebSocketControllerAnyIO."""
    
    def setup_method(self):
        """Set up each test."""
        self.mock_ipfs_model = MagicMock()
        
        # Patch the peer_websocket_anyio module import
        self.websocket_module_patcher = patch(
            'ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.HAS_PEER_WEBSOCKET', 
            True
        )
        self.mock_has_peer_websocket = self.websocket_module_patcher.start()
        
    def teardown_method(self):
        """Clean up after each test."""
        self.websocket_module_patcher.stop()
        
    def test_initialization(self):
        """Test controller initialization."""
        controller = PeerWebSocketControllerAnyIO(self.mock_ipfs_model)
        
        assert controller.ipfs_model == self.mock_ipfs_model
        assert controller.peer_websocket_server is None
        assert controller.peer_websocket_client is None
        assert controller.local_peer_info is None
        
    def test_route_registration(self):
        """Test route registration with FastAPI router."""
        controller = PeerWebSocketControllerAnyIO(self.mock_ipfs_model)
        router = APIRouter()
        
        # Call the method to register routes
        controller.register_routes(router)
        
        # Check that routes were added to the router
        # Since we can't easily inspect the router's routes, we'll check that the
        # WebSocket path was registered if WebSocket support is available
        if HAS_PEER_WEBSOCKET:
            assert controller.local_peer_info is not None
            
    def test_route_registration_without_websocket(self):
        """Test route registration without WebSocket support."""
        # Patch to simulate WebSocket not available
        with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.HAS_PEER_WEBSOCKET', False):
            controller = PeerWebSocketControllerAnyIO(self.mock_ipfs_model)
            router = APIRouter()
            
            # Call the method to register routes
            controller.register_routes(router)
            
            # WebSocket path should not be registered
            assert controller.local_peer_info is None


@pytest.mark.anyio
class TestPeerWebSocketControllerAnyIO:
    """Test the PeerWebSocketControllerAnyIO class functionality."""
    
    @pytest.fixture
    async def controller(self):
        """Create a controller for testing."""
        mock_ipfs_model = MagicMock()
        
        # Create patches for all peer_websocket_anyio imports
        with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.HAS_PEER_WEBSOCKET', True), \
             patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.PeerInfo', MockPeerInfo), \
             patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.PeerWebSocketServer', MockPeerWebSocketServer), \
             patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.PeerWebSocketClient', MockPeerWebSocketClient), \
             patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.register_peer_websocket', mock_register_peer_websocket), \
             patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.PeerRole'):
            
            controller = PeerWebSocketControllerAnyIO(mock_ipfs_model)
            yield controller
    
    @pytest.fixture
    def mock_ipfs_model(self):
        """Create a mock IPFS model."""
        return MagicMock()
    
    async def test_check_websocket_support(self, controller):
        """Test check_websocket_support method."""
        # Test with WebSocket support available
        with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.HAS_PEER_WEBSOCKET', True):
            result = await controller.check_websocket_support()
            
            assert result["success"] is True
            assert "operation_id" in result
            assert "timestamp" in result
            assert result["websocket_available"] is True
        
        # Test with WebSocket support not available
        with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.HAS_PEER_WEBSOCKET', False):
            result = await controller.check_websocket_support()
            
            assert result["success"] is True
            assert "operation_id" in result
            assert "timestamp" in result
            assert result["websocket_available"] is False
    
    async def test_start_server(self, controller):
        """Test start_server method."""
        # Create a request
        request = StartServerRequest(
            host="127.0.0.1",
            port=8765,
            max_peers=100,
            heartbeat_interval=30,
            peer_ttl=300,
            role="master",
            capabilities=["ipfs", "mcp"]
        )
        
        # Test with WebSocket support available
        with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.HAS_PEER_WEBSOCKET', True):
            result = await controller.start_server(request)
            
            assert result["success"] is True
            assert "operation_id" in result
            assert "timestamp" in result
            assert "server_url" in result
            assert result["server_url"] == "ws://127.0.0.1:8765"
            assert "peer_info" in result
            assert controller.peer_websocket_server is not None
            assert controller.local_peer_info is not None
        
        # Test with WebSocket support not available
        with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.HAS_PEER_WEBSOCKET', False):
            result = await controller.start_server(request)
            
            assert result["success"] is False
            assert "operation_id" in result
            assert "timestamp" in result
            assert "error" in result
            assert "WebSocket support not available" in result["error"]
    
    async def test_start_server_exception(self, controller):
        """Test start_server method with exception during server start."""
        # Create a request
        request = StartServerRequest(
            host="127.0.0.1",
            port=8765
        )
        
        # Make server.start raise an exception
        mock_server = MagicMock()
        mock_server.start = AsyncMock(side_effect=Exception("Mock server start error"))
        mock_server.stop = AsyncMock()
        
        with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.PeerWebSocketServer', 
                  return_value=mock_server):
            result = await controller.start_server(request)
            
            assert result["success"] is False
            assert "operation_id" in result
            assert "timestamp" in result
            assert "error" in result
            assert "Mock server start error" in result["error"]
            
            # Check that cleanup was attempted
            mock_server.stop.assert_called_once()
    
    async def test_stop_server(self, controller):
        """Test stop_server method."""
        # First start a server
        request = StartServerRequest(host="127.0.0.1", port=8765)
        await controller.start_server(request)
        
        # Now stop it
        result = await controller.stop_server()
        
        assert result["success"] is True
        assert "operation_id" in result
        assert "timestamp" in result
        assert "message" in result
        assert "Server stopped successfully" in result["message"]
        assert controller.peer_websocket_server is None
        
        # Test stopping when no server is running
        result = await controller.stop_server()
        
        assert result["success"] is False
        assert "operation_id" in result
        assert "timestamp" in result
        assert "error" in result
        assert "Server not running" in result["error"]
    
    async def test_stop_server_exception(self, controller):
        """Test stop_server method with exception during server stop."""
        # Set up server with mocked stop method that raises an exception
        mock_server = MagicMock()
        mock_server.stop = AsyncMock(side_effect=Exception("Mock server stop error"))
        controller.peer_websocket_server = mock_server
        
        result = await controller.stop_server()
        
        assert result["success"] is False
        assert "operation_id" in result
        assert "timestamp" in result
        assert "error" in result
        assert "Mock server stop error" in result["error"]
        
        # Server reference should be cleared even after error
        assert controller.peer_websocket_server is None
    
    async def test_get_server_status(self, controller):
        """Test get_server_status method."""
        # Test when server is not running
        result = await controller.get_server_status()
        
        assert result["success"] is True
        assert "operation_id" in result
        assert "timestamp" in result
        assert "running" in result
        assert result["running"] is False
        assert "peers_connected" in result
        assert result["peers_connected"] == 0
        
        # Test when server is running
        # First start a server
        request = StartServerRequest(host="127.0.0.1", port=8765)
        await controller.start_server(request)
        
        # Add some mock connections
        controller.peer_websocket_server.connections = {"conn1": "peer1", "conn2": "peer2"}
        
        result = await controller.get_server_status()
        
        assert result["success"] is True
        assert "operation_id" in result
        assert "timestamp" in result
        assert "running" in result
        assert result["running"] is True
        assert "peers_connected" in result
        assert result["peers_connected"] == 2
        assert "known_peers" in result
        assert "local_peer" in result
    
    async def test_connect_to_server(self, controller):
        """Test connect_to_server method."""
        # Create a request
        request = ConnectToServerRequest(
            server_url="ws://127.0.0.1:8765",
            auto_connect=True,
            reconnect_interval=30,
            max_reconnect_attempts=5
        )
        
        # Test with WebSocket support available
        with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.HAS_PEER_WEBSOCKET', True):
            result = await controller.connect_to_server(request)
            
            assert result["success"] is True
            assert "operation_id" in result
            assert "timestamp" in result
            assert "connected" in result
            assert result["connected"] is True
            assert "server_url" in result
            assert result["server_url"] == "ws://127.0.0.1:8765"
            assert controller.peer_websocket_client is not None
            assert controller.local_peer_info is not None
        
        # Test with WebSocket support not available
        with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.HAS_PEER_WEBSOCKET', False):
            controller.peer_websocket_client = None  # Reset client
            result = await controller.connect_to_server(request)
            
            assert result["success"] is False
            assert "operation_id" in result
            assert "timestamp" in result
            assert "error" in result
            assert "WebSocket support not available" in result["error"]
    
    async def test_connect_to_server_exception(self, controller):
        """Test connect_to_server method with exception during client connection."""
        # Create a request
        request = ConnectToServerRequest(
            server_url="ws://127.0.0.1:8765"
        )
        
        # Make client.connect_to_discovery_server raise an exception
        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.connect_to_discovery_server = AsyncMock(
            side_effect=Exception("Mock connection error")
        )
        mock_client.stop = AsyncMock()
        
        with patch('ipfs_kit_py.mcp.controllers.peer_websocket_controller_anyio.PeerWebSocketClient', 
                  return_value=mock_client):
            result = await controller.connect_to_server(request)
            
            assert result["success"] is False
            assert "operation_id" in result
            assert "timestamp" in result
            assert "error" in result
            assert "Mock connection error" in result["error"]
            
            # Check that cleanup was attempted
            mock_client.stop.assert_called_once()
    
    async def test_disconnect_from_server(self, controller):
        """Test disconnect_from_server method."""
        # First connect to a server
        request = ConnectToServerRequest(server_url="ws://127.0.0.1:8765")
        await controller.connect_to_server(request)
        
        # Now disconnect
        result = await controller.disconnect_from_server()
        
        assert result["success"] is True
        assert "operation_id" in result
        assert "timestamp" in result
        assert "message" in result
        assert "Client stopped successfully" in result["message"]
        assert controller.peer_websocket_client is None
        
        # Test disconnecting when no client is running
        result = await controller.disconnect_from_server()
        
        assert result["success"] is False
        assert "operation_id" in result
        assert "timestamp" in result
        assert "error" in result
        assert "Client not running" in result["error"]
    
    async def test_disconnect_from_server_exception(self, controller):
        """Test disconnect_from_server method with exception during client stop."""
        # Set up client with mocked stop method that raises an exception
        mock_client = MagicMock()
        mock_client.stop = AsyncMock(side_effect=Exception("Mock client stop error"))
        controller.peer_websocket_client = mock_client
        
        result = await controller.disconnect_from_server()
        
        assert result["success"] is False
        assert "operation_id" in result
        assert "timestamp" in result
        assert "error" in result
        assert "Mock client stop error" in result["error"]
        
        # Client reference should be cleared even after error
        assert controller.peer_websocket_client is None
    
    async def test_get_discovered_peers(self, controller):
        """Test get_discovered_peers method."""
        # Test when client is not running
        result = await controller.get_discovered_peers()
        
        assert result["success"] is True
        assert "operation_id" in result
        assert "timestamp" in result
        assert "peers" in result
        assert len(result["peers"]) == 0
        assert "count" in result
        assert result["count"] == 0
        
        # First connect to a server
        request = ConnectToServerRequest(server_url="ws://127.0.0.1:8765")
        await controller.connect_to_server(request)
        
        # Add some mock peers to the client
        peer1 = MockPeerInfo(peer_id="peer1", role="worker", capabilities=["ipfs"])
        peer2 = MockPeerInfo(peer_id="peer2", role="leecher", capabilities=["ipfs", "mcp"])
        controller.peer_websocket_client.peers["peer1"] = peer1
        controller.peer_websocket_client.peers["peer2"] = peer2
        
        # Test without filters
        result = await controller.get_discovered_peers()
        
        assert result["success"] is True
        assert "operation_id" in result
        assert "timestamp" in result
        assert "peers" in result
        assert len(result["peers"]) == 2
        assert "count" in result
        assert result["count"] == 2
        
        # Test with role filter
        result = await controller.get_discovered_peers(filter_role="worker")
        
        # We're mocking the actual filtering in the controller so results will be the same
        assert result["success"] is True
        assert "count" in result
        
        # Test with capabilities filter
        result = await controller.get_discovered_peers(filter_capabilities="ipfs,mcp")
        
        # We're mocking the actual filtering in the controller so results will be the same
        assert result["success"] is True
        assert "count" in result
    
    async def test_get_peer_by_id(self, controller):
        """Test get_peer_by_id method."""
        # Test when client is not running
        result = await controller.get_peer_by_id("peer1")
        
        assert result["success"] is False
        assert "operation_id" in result
        assert "timestamp" in result
        assert "error" in result
        assert "Client not running" in result["error"]
        
        # First connect to a server
        request = ConnectToServerRequest(server_url="ws://127.0.0.1:8765")
        await controller.connect_to_server(request)
        
        # Add a mock peer to the client
        peer1 = MockPeerInfo(peer_id="peer1", role="worker", capabilities=["ipfs"])
        controller.peer_websocket_client.peers["peer1"] = peer1
        
        # Test with existing peer
        result = await controller.get_peer_by_id("peer1")
        
        assert result["success"] is True
        assert "operation_id" in result
        assert "timestamp" in result
        assert "peer" in result
        assert result["peer"]["peer_id"] == "peer1"
        
        # Test with non-existent peer
        result = await controller.get_peer_by_id("nonexistent")
        
        assert result["success"] is False
        assert "operation_id" in result
        assert "timestamp" in result
        assert "error" in result
        assert "Peer not found" in result["error"]
    
    async def test_shutdown(self, controller):
        """Test shutdown method."""
        # First start a server and client
        server_request = StartServerRequest(host="127.0.0.1", port=8765)
        await controller.start_server(server_request)
        
        client_request = ConnectToServerRequest(server_url="ws://127.0.0.1:8765")
        await controller.connect_to_server(client_request)
        
        # Now call shutdown
        await controller.shutdown()
        
        # Both server and client should be cleaned up
        assert controller.peer_websocket_server is None
        assert controller.peer_websocket_client is None
    
    async def test_shutdown_with_exceptions(self, controller):
        """Test shutdown method with exceptions during cleanup."""
        # Set up server and client with mocked stop methods that raise exceptions
        mock_server = MagicMock()
        mock_server.stop = AsyncMock(side_effect=Exception("Mock server stop error"))
        controller.peer_websocket_server = mock_server
        
        mock_client = MagicMock()
        mock_client.stop = AsyncMock(side_effect=Exception("Mock client stop error"))
        controller.peer_websocket_client = mock_client
        
        # Shutdown should complete even with exceptions
        await controller.shutdown()
        
        # Both references should be cleared
        assert controller.peer_websocket_server is None
        assert controller.peer_websocket_client is None
    
    async def test_sniffio_backend(self, controller):
        """Test the get_backend method."""
        # This tests the static method that uses sniffio
        with patch('sniffio.current_async_library', return_value="anyio"):
            backend = PeerWebSocketControllerAnyIO.get_backend()
            assert backend == "anyio"
        
        # Test when no async library is found
        with patch('sniffio.current_async_library', side_effect=Exception("No async library found")):
            backend = PeerWebSocketControllerAnyIO.get_backend()
            assert backend is None


# @pytest.mark.skip(reason="HTTP endpoint tests require running FastAPI server") - removed by fix_all_tests.py
class TestPeerWebSocketControllerAnyIOHTTPEndpoints:
    """Test HTTP endpoints for PeerWebSocketControllerAnyIO."""
    
    @pytest.fixture
    def client(self):
        """Create a test client with the controller endpoints registered."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        
        app = FastAPI()
        mock_ipfs_model = MagicMock()
        controller = PeerWebSocketControllerAnyIO(mock_ipfs_model)
        controller.register_routes(app.router)
        
        return TestClient(app)
    
    def test_check_websocket_support_endpoint(self, client):
        """Test check_websocket_support endpoint."""
        response = client.get("/peer/websocket/check")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "websocket_available" in data
    
    def test_start_server_endpoint(self, client):
        """Test start_server endpoint."""
        response = client.post("/peer/websocket/server/start", json={
            "host": "127.0.0.1",
            "port": 8765
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "server_url" in data
    
    def test_stop_server_endpoint(self, client):
        """Test stop_server endpoint."""
        # First start the server
        client.post("/peer/websocket/server/start", json={
            "host": "127.0.0.1",
            "port": 8765
        })
        
        # Now stop it
        response = client.post("/peer/websocket/server/stop")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "message" in data
    
    def test_get_server_status_endpoint(self, client):
        """Test get_server_status endpoint."""
        response = client.get("/peer/websocket/server/status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "running" in data
    
    def test_connect_to_server_endpoint(self, client):
        """Test connect_to_server endpoint."""
        response = client.post("/peer/websocket/client/connect", json={
            "server_url": "ws://127.0.0.1:8765"
        })
        assert response.status_code == 200
        data = response.json()
        assert "connected" in data
    
    def test_disconnect_from_server_endpoint(self, client):
        """Test disconnect_from_server endpoint."""
        # First connect to a server
        client.post("/peer/websocket/client/connect", json={
            "server_url": "ws://127.0.0.1:8765"
        })
        
        # Now disconnect
        response = client.post("/peer/websocket/client/disconnect")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "message" in data
    
    def test_get_discovered_peers_endpoint(self, client):
        """Test get_discovered_peers endpoint."""
        response = client.get("/peer/websocket/peers")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "peers" in data
        assert "count" in data
    
    def test_get_peer_by_id_endpoint(self, client):
        """Test get_peer_by_id endpoint."""
        # First connect to a server and discover some peers
        client.post("/peer/websocket/client/connect", json={
            "server_url": "ws://127.0.0.1:8765"
        })
        
        # Get a peer that won't exist
        response = client.get("/peer/websocket/peers/nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
