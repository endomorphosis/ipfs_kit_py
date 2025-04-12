"""
Test suite for MCP LibP2P Controller.

This module tests the functionality of the LibP2PController class
which provides HTTP endpoints for direct peer-to-peer communication,
peer discovery, content routing, and direct content exchange.

It includes proper dependency handling to ensure tests can run with or
without the libp2p dependencies installed, focusing primarily on the
controller's API interface rather than actual libp2p functionality.
"""

import json
import os
import sys
import pytest
import anyio
import logging
from unittest.mock import MagicMock, patch, AsyncMock

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check FastAPI availability first
try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logger.warning("FastAPI not available, will skip controller tests")

# Check and potentially install libp2p dependencies
from install_libp2p import install_dependencies_auto, check_dependency

# Flag to track whether we've attempted to install dependencies
INSTALL_ATTEMPTED = False
# Flag to track whether dependencies are available
HAS_DEPENDENCIES = False

def check_and_install_dependencies():
    """Check for dependencies and optionally install them."""
    global INSTALL_ATTEMPTED, HAS_DEPENDENCIES
    
    # Skip if we've already tried
    if INSTALL_ATTEMPTED:
        return HAS_DEPENDENCIES
    
    INSTALL_ATTEMPTED = True
    
    # Check if dependencies are already installed
    all_installed = True
    missing_deps = []
    for dep in ["libp2p", "multiaddr", "base58", "cryptography"]:
        installed, version = check_dependency(dep)
        if not installed:
            all_installed = False
            missing_deps.append(dep)
    
    # If all dependencies are already available, we're good
    if all_installed:
        logger.info("All libp2p dependencies are available")
        HAS_DEPENDENCIES = True
        return True
    
    # Check if we should auto-install
    auto_install = os.environ.get("IPFS_KIT_AUTO_INSTALL_DEPS", "0") == "1"
    force_install = os.environ.get("IPFS_KIT_FORCE_INSTALL_DEPS", "0") == "1"
    
    if auto_install or force_install:
        logger.info(f"Attempting to install missing dependencies: {', '.join(missing_deps)}")
        success = install_dependencies_auto(force=force_install)
        if success:
            logger.info("Successfully installed libp2p dependencies")
            HAS_DEPENDENCIES = True
            return True
        else:
            logger.warning("Failed to install libp2p dependencies")
            return False
    else:
        logger.warning(f"Missing libp2p dependencies and auto-install is disabled: {', '.join(missing_deps)}")
        logger.info("Set IPFS_KIT_AUTO_INSTALL_DEPS=1 to enable auto-installation")
        return False

# Check and optionally install dependencies
HAS_DEPENDENCIES = check_and_install_dependencies()

# Import the controller - we'll still import it even if dependencies are missing
# since we're mocking the model anyway, but we'll log the status
try:
    from ipfs_kit_py.mcp.controllers.libp2p_controller import LibP2PController
    logger.info("Successfully imported LibP2PController")
except ImportError as e:
    logger.error(f"Failed to import LibP2PController: {e}")
    # We'll re-raise this only if FastAPI is available, otherwise tests are skipped anyway
    if FASTAPI_AVAILABLE:
        raise

# Skip all tests if FastAPI is not available
pytestmark = pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not installed")


class TestLibP2PController:
    """Test suite for LibP2P Controller functionality."""

    @pytest.fixture
    def libp2p_model(self):
        """
        Create a mock LibP2P model.
        
        This fixture creates a mock model that simulates the behavior of the real
        LibP2PModel class without requiring actual libp2p dependencies to be installed.
        The model returns pre-defined responses that match the expected structure.
        """
        model = AsyncMock()
        
        # Set libp2p availability based on our dependency check
        model.is_available.return_value = HAS_DEPENDENCIES
        
        # Configure model method return values
        model.get_peers.return_value = {
            "success": True,
            "operation": "get_peers",
            "peers": [
                {"id": "peer1", "address": "/ip4/127.0.0.1/tcp/4001", "connected": True},
                {"id": "peer2", "address": "/ip4/192.168.1.1/tcp/4001", "connected": False}
            ],
            "timestamp": 1234567890.123
        }
        
        model.connect_peer.return_value = {
            "success": True,
            "operation": "connect_peer",
            "peer_id": "peer1",
            "address": "/ip4/127.0.0.1/tcp/4001",
            "timestamp": 1234567890.123
        }
        
        model.disconnect_peer.return_value = {
            "success": True,
            "operation": "disconnect_peer",
            "peer_id": "peer1",
            "timestamp": 1234567890.123
        }
        
        model.publish_message.return_value = {
            "success": True,
            "operation": "publish_message",
            "topic": "test-topic",
            "message_id": "msg123",
            "timestamp": 1234567890.123
        }
        
        model.subscribe_topic.return_value = {
            "success": True,
            "operation": "subscribe_topic",
            "topic": "test-topic",
            "timestamp": 1234567890.123
        }
        
        model.unsubscribe_topic.return_value = {
            "success": True,
            "operation": "unsubscribe_topic",
            "topic": "test-topic",
            "timestamp": 1234567890.123
        }
        
        model.dht_find_peer.return_value = {
            "success": True,
            "operation": "dht_find_peer",
            "peer_id": "peer1",
            "addresses": ["/ip4/127.0.0.1/tcp/4001"],
            "timestamp": 1234567890.123
        }
        
        model.dht_provide.return_value = {
            "success": True,
            "operation": "dht_provide",
            "cid": "QmTest123",
            "timestamp": 1234567890.123
        }
        
        model.dht_find_providers.return_value = {
            "success": True,
            "operation": "dht_find_providers",
            "cid": "QmTest123",
            "providers": ["peer1", "peer2"],
            "timestamp": 1234567890.123
        }
        
        model.peer_info.return_value = {
            "success": True,
            "operation": "peer_info",
            "peer_id": "self-id",
            "addresses": ["/ip4/127.0.0.1/tcp/4001"],
            "protocols": ["ipfs/0.1.0", "libp2p/0.1.0"],
            "agent_version": "ipfs-kit-py/0.1.0",
            "timestamp": 1234567890.123
        }

        # Configure model for error conditions
        model.libp2p_available = True
        
        return model

    @pytest.fixture
    def app(self, libp2p_model):
        """Create a FastAPI app with the LibP2P controller routes registered."""
        app = FastAPI()
        controller = LibP2PController(libp2p_model)
        controller.register_routes(app.router)
        return app

    @pytest.fixture
    def client(self, app):
        """Create a test client for the FastAPI app."""
        return TestClient(app)
    
    def test_register_routes(self, libp2p_model):
        """Test that routes are properly registered."""
        app = FastAPI()
        router = app.router
        
        # Count routes before registration
        pre_routes = len(router.routes)
        
        # Register routes
        controller = LibP2PController(libp2p_model)
        controller.register_routes(router)
        
        # Verify routes were added
        post_routes = len(router.routes)
        assert post_routes > pre_routes, "No routes were registered"
        
        # Check for specific routes
        route_paths = [route.path for route in router.routes]
        assert "/libp2p/peers" in route_paths
        assert "/libp2p/connect" in route_paths
        assert "/libp2p/disconnect" in route_paths
        assert "/libp2p/publish" in route_paths
        assert "/libp2p/subscribe" in route_paths
        assert "/libp2p/unsubscribe" in route_paths
        assert "/libp2p/dht/findpeer" in route_paths
        assert "/libp2p/dht/provide" in route_paths
        assert "/libp2p/dht/findproviders" in route_paths
        assert "/libp2p/info" in route_paths
    
    def test_get_peers(self, client, libp2p_model):
        """Test the get_peers endpoint."""
        response = client.get("/libp2p/peers")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "peers" in data
        assert len(data["peers"]) == 2
        assert data["peers"][0]["id"] == "peer1"
        assert data["peers"][1]["id"] == "peer2"
        
        # Verify the model method was called
        libp2p_model.get_peers.assert_called_once()
    
    def test_connect_peer(self, client, libp2p_model):
        """Test the connect_peer endpoint."""
        response = client.post(
            "/libp2p/connect",
            json={"peer_id": "peer1", "address": "/ip4/127.0.0.1/tcp/4001"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["peer_id"] == "peer1"
        
        # Verify the model method was called with correct arguments
        libp2p_model.connect_peer.assert_called_once_with(
            peer_id="peer1", 
            address="/ip4/127.0.0.1/tcp/4001"
        )
    
    def test_disconnect_peer(self, client, libp2p_model):
        """Test the disconnect_peer endpoint."""
        response = client.post(
            "/libp2p/disconnect",
            json={"peer_id": "peer1"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["peer_id"] == "peer1"
        
        # Verify the model method was called with correct arguments
        libp2p_model.disconnect_peer.assert_called_once_with(peer_id="peer1")
    
    def test_publish_message(self, client, libp2p_model):
        """Test the publish_message endpoint."""
        response = client.post(
            "/libp2p/publish",
            json={"topic": "test-topic", "message": "Hello, world!"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["topic"] == "test-topic"
        assert "message_id" in data
        
        # Verify the model method was called with correct arguments
        libp2p_model.publish_message.assert_called_once_with(
            topic="test-topic", 
            message="Hello, world!"
        )
    
    def test_subscribe_topic(self, client, libp2p_model):
        """Test the subscribe_topic endpoint."""
        response = client.post(
            "/libp2p/subscribe",
            json={"topic": "test-topic"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["topic"] == "test-topic"
        
        # Verify the model method was called with correct arguments
        libp2p_model.subscribe_topic.assert_called_once_with(topic="test-topic")
    
    def test_unsubscribe_topic(self, client, libp2p_model):
        """Test the unsubscribe_topic endpoint."""
        response = client.post(
            "/libp2p/unsubscribe",
            json={"topic": "test-topic"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["topic"] == "test-topic"
        
        # Verify the model method was called with correct arguments
        libp2p_model.unsubscribe_topic.assert_called_once_with(topic="test-topic")
    
    def test_dht_find_peer(self, client, libp2p_model):
        """Test the dht_find_peer endpoint."""
        response = client.post(
            "/libp2p/dht/findpeer",
            json={"peer_id": "peer1"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["peer_id"] == "peer1"
        assert "addresses" in data
        
        # Verify the model method was called with correct arguments
        libp2p_model.dht_find_peer.assert_called_once_with(peer_id="peer1")
    
    def test_dht_provide(self, client, libp2p_model):
        """Test the dht_provide endpoint."""
        response = client.post(
            "/libp2p/dht/provide",
            json={"cid": "QmTest123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cid"] == "QmTest123"
        
        # Verify the model method was called with correct arguments
        libp2p_model.dht_provide.assert_called_once_with(cid="QmTest123")
    
    def test_dht_find_providers(self, client, libp2p_model):
        """Test the dht_find_providers endpoint."""
        response = client.post(
            "/libp2p/dht/findproviders",
            json={"cid": "QmTest123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cid"] == "QmTest123"
        assert "providers" in data
        assert len(data["providers"]) == 2
        
        # Verify the model method was called with correct arguments
        libp2p_model.dht_find_providers.assert_called_once_with(cid="QmTest123")
    
    def test_peer_info(self, client, libp2p_model):
        """Test the peer_info endpoint."""
        response = client.get("/libp2p/info")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "peer_id" in data
        assert "addresses" in data
        assert "protocols" in data
        
        # Verify the model method was called
        libp2p_model.peer_info.assert_called_once()
    
    def test_error_handling(self, client, libp2p_model):
        """Test error handling in the LibP2P controller."""
        # Configure model to simulate error
        libp2p_model.get_peers.return_value = {
            "success": False,
            "operation": "get_peers",
            "error": "Failed to get peers",
            "timestamp": 1234567890.123
        }
        
        response = client.get("/libp2p/peers")
        
        # Even though the operation failed, the API should still return 200
        # with the error information in the response body
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "error" in data
        assert data["error"] == "Failed to get peers"
    
    def test_libp2p_unavailable(self, client, libp2p_model):
        """Test behavior when LibP2P is unavailable."""
        # Configure model to simulate LibP2P being unavailable
        libp2p_model.libp2p_available = False
        libp2p_model.get_peers.return_value = {
            "success": False,
            "operation": "get_peers",
            "error": "LibP2P is not available",
            "error_type": "LibP2PUnavailableError",
            "timestamp": 1234567890.123
        }
        
        response = client.get("/libp2p/peers")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "error" in data
        assert "LibP2P is not available" in data["error"]
    
    def test_async_error_handling(self, client, libp2p_model):
        """Test async error handling in the LibP2P controller."""
        # Configure model to raise exception during async operation
        libp2p_model.dht_find_peer.side_effect = Exception("Network error")
        
        response = client.post(
            "/libp2p/dht/findpeer",
            json={"peer_id": "peer1"}
        )
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Network error" in data["detail"]


@pytest.mark.anyio
class TestLibP2PControllerAnyIO:
    """Test suite for the AnyIO version of the LibP2P controller."""
    
    @pytest.fixture
    def libp2p_model(self):
        """
        Create a mock LibP2P model with async methods.
        
        This fixture creates a mock model that works with the AnyIO version of the controller.
        It includes comprehensive mock responses for all controller methods.
        """
        model = AsyncMock()
        
        # Set libp2p availability based on our dependency check
        model.is_available.return_value = HAS_DEPENDENCIES
        model.libp2p_available = HAS_DEPENDENCIES
        
        # Configure model method return values for basic peer operations
        model.get_peers.return_value = {
            "success": True,
            "operation": "get_peers",
            "peers": [
                {"id": "peer1", "address": "/ip4/127.0.0.1/tcp/4001", "connected": True},
                {"id": "peer2", "address": "/ip4/192.168.1.1/tcp/4001", "connected": False}
            ],
            "timestamp": 1234567890.123
        }
        
        model.connect_peer.return_value = {
            "success": True,
            "operation": "connect_peer",
            "peer_id": "peer1",
            "address": "/ip4/127.0.0.1/tcp/4001",
            "timestamp": 1234567890.123
        }
        
        model.disconnect_peer.return_value = {
            "success": True,
            "operation": "disconnect_peer",
            "peer_id": "peer1",
            "timestamp": 1234567890.123
        }
        
        # Configure model method return values for DHT operations
        model.dht_find_peer.return_value = {
            "success": True,
            "operation": "dht_find_peer",
            "peer_id": "peer1",
            "addresses": ["/ip4/127.0.0.1/tcp/4001"],
            "timestamp": 1234567890.123
        }
        
        model.dht_provide.return_value = {
            "success": True,
            "operation": "dht_provide",
            "cid": "QmTest123",
            "timestamp": 1234567890.123
        }
        
        model.dht_find_providers.return_value = {
            "success": True,
            "operation": "dht_find_providers",
            "cid": "QmTest123",
            "providers": ["peer1", "peer2"],
            "timestamp": 1234567890.123
        }
        
        # Configure model method return values for PubSub operations
        model.pubsub_publish.return_value = {
            "success": True,
            "operation": "pubsub_publish",
            "topic": "test-topic",
            "message_id": "msg123",
            "timestamp": 1234567890.123
        }
        
        model.pubsub_subscribe.return_value = {
            "success": True,
            "operation": "pubsub_subscribe",
            "topic": "test-topic",
            "timestamp": 1234567890.123
        }
        
        model.pubsub_unsubscribe.return_value = {
            "success": True,
            "operation": "pubsub_unsubscribe",
            "topic": "test-topic",
            "timestamp": 1234567890.123
        }
        
        model.pubsub_get_topics.return_value = {
            "success": True,
            "operation": "pubsub_get_topics",
            "topics": ["test-topic1", "test-topic2"],
            "timestamp": 1234567890.123
        }
        
        model.pubsub_get_peers.return_value = {
            "success": True,
            "operation": "pubsub_get_peers",
            "peers": ["peer1", "peer2"],
            "topic": "test-topic",
            "timestamp": 1234567890.123
        }
        
        # Configure model method return values for message handlers
        model.register_message_handler.return_value = {
            "success": True,
            "operation": "register_message_handler",
            "handler_id": "test-handler",
            "protocol_id": "/test/1.0.0",
            "timestamp": 1234567890.123
        }
        
        model.unregister_message_handler.return_value = {
            "success": True,
            "operation": "unregister_message_handler",
            "handler_id": "test-handler",
            "protocol_id": "/test/1.0.0",
            "timestamp": 1234567890.123
        }
        
        model.list_message_handlers.return_value = {
            "success": True,
            "operation": "list_message_handlers",
            "handlers": [
                {
                    "handler_id": "test-handler",
                    "protocol_id": "/test/1.0.0",
                    "description": "Test handler"
                }
            ],
            "timestamp": 1234567890.123
        }
        
        # Configure model method return values for lifecycle management
        model.start.return_value = {
            "success": True,
            "action": "start",
            "status": "running",
            "timestamp": 1234567890.123
        }
        
        model.stop.return_value = {
            "success": True,
            "action": "stop",
            "status": "stopped",
            "timestamp": 1234567890.123
        }
        
        # Configure model method return values for peer information
        model.peer_info.return_value = {
            "success": True,
            "operation": "peer_info",
            "peer_id": "self-id",
            "addresses": ["/ip4/127.0.0.1/tcp/4001"],
            "protocols": ["ipfs/0.1.0", "libp2p/0.1.0"],
            "agent_version": "ipfs-kit-py/0.1.0",
            "timestamp": 1234567890.123
        }
        
        # Configure model method return values for content operations
        model.find_content.return_value = {
            "success": True,
            "operation": "find_content",
            "cid": "QmTest123",
            "providers": [
                "/ip4/192.168.1.1/tcp/4001/p2p/12D3KooWPeer1",
                "/ip4/192.168.1.2/tcp/4001/p2p/12D3KooWPeer2"
            ],
            "provider_count": 2,
            "timestamp": 1234567890.123
        }
        
        model.retrieve_content.return_value = {
            "success": True,
            "operation": "retrieve_content",
            "cid": "QmTest123",
            "size": 1024,
            "provider": "/ip4/192.168.1.1/tcp/4001/p2p/12D3KooWPeer1",
            "metadata": {
                "content_type": "application/json",
                "retrieved_at": 1234567890.123
            },
            "timestamp": 1234567890.123
        }
        
        model.get_content.return_value = {
            "success": True,
            "operation": "get_content",
            "cid": "QmTest123",
            "size": 1024,
            "data": b'{"test": "content"}',
            "timestamp": 1234567890.123
        }
        
        model.announce_content.return_value = {
            "success": True,
            "operation": "announce_content",
            "cid": "QmTest123",
            "size": 1024,
            "announced_to_peers": 3,
            "timestamp": 1234567890.123
        }
        
        # Configure model method return values for health and stats
        model.get_health.return_value = {
            "success": True,
            "libp2p_available": True,
            "peer_initialized": True,
            "peer_id": "12D3KooWA9BxgkQS2vRED8GZBCVURjEDZHnCxpXQj6Yhc8G5PBL7",
            "addresses": ["/ip4/127.0.0.1/tcp/4001"],
            "connected_peers": 3,
            "dht_peers": 5,
            "protocols": ["/ipfs/kad/1.0.0", "/ipfs/ping/1.0.0"],
            "role": "master",
            "stats": {
                "operations": 10,
                "bytes_sent": 1024,
                "bytes_received": 2048
            },
            "timestamp": 1234567890.123
        }
        
        model.get_stats.return_value = {
            "success": True,
            "operation": "get_stats",
            "operations": {
                "discover_peers": 5,
                "connect_peer": 3,
                "find_content": 10,
                "retrieve_content": 7,
                "announce_content": 2
            },
            "traffic": {
                "bytes_sent": 10240,
                "bytes_received": 20480,
                "requests_sent": 20,
                "responses_received": 18
            },
            "uptime_seconds": 3600,
            "timestamp": 1234567890.123
        }
        
        model.reset.return_value = {
            "success": True,
            "operation": "reset",
            "message": "LibP2P state reset successfully",
            "connections_closed": 2,
            "stats_reset": True,
            "timestamp": 1234567890.123
        }
        
        # Configure model method return values for connected peers
        model.get_connected_peers.return_value = {
            "success": True,
            "operation": "get_connected_peers",
            "peers": [
                {
                    "id": "peer1",
                    "addresses": ["/ip4/127.0.0.1/tcp/4001"],
                    "protocols": ["/ipfs/0.1.0"],
                    "latency_ms": 15,
                    "connection_time": 1234567890.0
                }
            ],
            "count": 1,
            "timestamp": 1234567890.123
        }
        
        model.get_peer_info.return_value = {
            "success": True,
            "operation": "get_peer_info",
            "peer_id": "peer1",
            "addresses": ["/ip4/127.0.0.1/tcp/4001"],
            "protocols": ["/ipfs/0.1.0"],
            "agent_version": "ipfs-kit-py/0.1.0",
            "connected": True,
            "last_seen": 1234567890.0,
            "timestamp": 1234567890.123
        }
        
        model.discover_peers.return_value = {
            "success": True,
            "operation": "discover_peers",
            "peers": [
                {"id": "peer1", "address": "/ip4/127.0.0.1/tcp/4001", "source": "mdns"},
                {"id": "peer2", "address": "/ip4/192.168.1.1/tcp/4001", "source": "dht"}
            ],
            "peer_count": 2,
            "method": "all",
            "timestamp": 1234567890.123
        }
        
        return model
    
    @pytest.fixture
    def controller(self, libp2p_model):
        """Create a LibP2PController instance."""
        # Import the AnyIO version if available, otherwise use the regular version
        try:
            from ipfs_kit_py.mcp.controllers.libp2p_controller_anyio import LibP2PController as LibP2PControllerAnyIO
            return LibP2PControllerAnyIO(libp2p_model)
        except ImportError:
            from ipfs_kit_py.mcp.controllers.libp2p_controller import LibP2PController
            return LibP2PController(libp2p_model)
    
    async def test_get_peers_async(self, controller, libp2p_model):
        """Test the get_peers method directly with async."""
        # Create mock request
        mock_request = MagicMock()
        
        # Call method directly
        result = await controller.get_peers(mock_request)
        
        # Verify result
        assert result["success"] is True
        assert "peers" in result
        assert len(result["peers"]) == 2
        
        # Verify model method was called
        libp2p_model.get_peers.assert_called_once()
    
    async def test_connect_peer_async(self, controller, libp2p_model):
        """Test the connect_peer method directly with async."""
        # Create mock request data
        class MockConnectRequest:
            def __init__(self):
                self.peer_id = "peer1"
                self.address = "/ip4/127.0.0.1/tcp/4001"
        
        # Call method directly
        result = await controller.connect_peer(MockConnectRequest())
        
        # Verify model method was called with correct arguments
        libp2p_model.connect_peer.assert_called_once_with(
            peer_id="peer1", 
            address="/ip4/127.0.0.1/tcp/4001"
        )
    
    async def test_dht_find_peer_async(self, controller, libp2p_model):
        """Test the dht_find_peer method directly with async."""
        # Create mock request data
        class MockDHTFindPeerRequest:
            def __init__(self):
                self.peer_id = "peer1"
                self.timeout = 30
        
        # Call method directly
        result = await controller.dht_find_peer(MockDHTFindPeerRequest())
        
        # Verify result
        assert result["success"] is True
        assert result["peer_id"] == "peer1"
        assert "addresses" in result
        
        # Verify model method was called with correct arguments
        libp2p_model.dht_find_peer.assert_called_once_with(peer_id="peer1", timeout=30)
    
    async def test_dht_provide_async(self, controller, libp2p_model):
        """Test the dht_provide method directly with async."""
        # Create mock request data
        class MockDHTProvideRequest:
            def __init__(self):
                self.cid = "QmTest123"
        
        # Call method directly
        result = await controller.dht_provide(MockDHTProvideRequest())
        
        # Verify result
        assert result["success"] is True
        assert result["cid"] == "QmTest123"
        
        # Verify model method was called with correct arguments
        libp2p_model.dht_provide.assert_called_once_with(cid="QmTest123")
    
    async def test_dht_find_providers_async(self, controller, libp2p_model):
        """Test the dht_find_providers method directly with async."""
        # Create mock request data
        class MockDHTFindProvidersRequest:
            def __init__(self):
                self.cid = "QmTest123"
                self.timeout = 30
                self.limit = 20
        
        # Call method directly
        result = await controller.dht_find_providers(MockDHTFindProvidersRequest())
        
        # Verify result
        assert result["success"] is True
        assert result["cid"] == "QmTest123"
        assert "providers" in result
        
        # Verify model method was called with correct arguments
        libp2p_model.dht_find_providers.assert_called_once_with(
            cid="QmTest123", timeout=30, limit=20
        )
    
    async def test_pubsub_publish_async(self, controller, libp2p_model):
        """Test the pubsub_publish method directly with async."""
        # Create mock request data
        class MockPubSubPublishRequest:
            def __init__(self):
                self.topic = "test-topic"
                self.message = "Hello, world!"
        
        # Call method directly
        result = await controller.pubsub_publish(MockPubSubPublishRequest())
        
        # Verify result
        assert result["success"] is True
        assert result["topic"] == "test-topic"
        assert "message_id" in result
        
        # Verify model method was called with correct arguments
        libp2p_model.pubsub_publish.assert_called_once_with(
            topic="test-topic", message="Hello, world!"
        )
    
    async def test_pubsub_subscribe_async(self, controller, libp2p_model):
        """Test the pubsub_subscribe method directly with async."""
        # Create mock request data
        class MockPubSubSubscribeRequest:
            def __init__(self):
                self.topic = "test-topic"
                self.handler_id = "test-handler"
        
        # Call method directly
        result = await controller.pubsub_subscribe(MockPubSubSubscribeRequest())
        
        # Verify result
        assert result["success"] is True
        assert result["topic"] == "test-topic"
        
        # Verify model method was called with correct arguments
        libp2p_model.pubsub_subscribe.assert_called_once_with(
            topic="test-topic", handler_id="test-handler"
        )
    
    async def test_pubsub_unsubscribe_async(self, controller, libp2p_model):
        """Test the pubsub_unsubscribe method directly with async."""
        # Create mock request data
        class MockPubSubUnsubscribeRequest:
            def __init__(self):
                self.topic = "test-topic"
                self.handler_id = "test-handler"
        
        # Call method directly
        result = await controller.pubsub_unsubscribe(MockPubSubUnsubscribeRequest())
        
        # Verify result
        assert result["success"] is True
        assert result["topic"] == "test-topic"
        
        # Verify model method was called with correct arguments
        libp2p_model.pubsub_unsubscribe.assert_called_once_with(
            topic="test-topic", handler_id="test-handler"
        )
    
    async def test_pubsub_get_topics_async(self, controller, libp2p_model):
        """Test the pubsub_get_topics method directly with async."""
        # Call method directly
        result = await controller.pubsub_get_topics()
        
        # Verify result
        assert result["success"] is True
        assert "topics" in result
        assert len(result["topics"]) == 2
        
        # Verify model method was called
        libp2p_model.pubsub_get_topics.assert_called_once()
    
    async def test_pubsub_get_peers_async(self, controller, libp2p_model):
        """Test the pubsub_get_peers method directly with async."""
        # Call method directly with topic parameter
        result = await controller.pubsub_get_peers(topic="test-topic")
        
        # Verify result
        assert result["success"] is True
        assert "peers" in result
        assert len(result["peers"]) == 2
        
        # Verify model method was called with correct arguments
        libp2p_model.pubsub_get_peers.assert_called_once_with("test-topic")
    
    async def test_message_handler_management_async(self, controller, libp2p_model):
        """Test message handler management methods directly with async."""
        # Create mock register request
        class MockMessageHandlerRequest:
            def __init__(self):
                self.handler_id = "test-handler"
                self.protocol_id = "/test/1.0.0"
                self.description = "Test handler"
        
        # Register handler
        register_result = await controller.register_message_handler(MockMessageHandlerRequest())
        assert register_result["success"] is True
        assert register_result["handler_id"] == "test-handler"
        assert register_result["protocol_id"] == "/test/1.0.0"
        
        # Verify model method was called with correct arguments
        libp2p_model.register_message_handler.assert_called_once_with(
            handler_id="test-handler", 
            protocol_id="/test/1.0.0",
            description="Test handler"
        )
        
        # List handlers
        list_result = await controller.list_message_handlers()
        assert list_result["success"] is True
        assert "handlers" in list_result
        assert len(list_result["handlers"]) == 1
        
        # Verify model method was called
        libp2p_model.list_message_handlers.assert_called_once()
        
        # Unregister handler
        unregister_result = await controller.unregister_message_handler(MockMessageHandlerRequest())
        assert unregister_result["success"] is True
        assert unregister_result["handler_id"] == "test-handler"
        assert unregister_result["protocol_id"] == "/test/1.0.0"
        
        # Verify model method was called with correct arguments
        libp2p_model.unregister_message_handler.assert_called_once_with(
            handler_id="test-handler", 
            protocol_id="/test/1.0.0"
        )
    
    async def test_start_stop_peer_async(self, controller, libp2p_model):
        """Test the start_peer and stop_peer methods directly with async."""
        # Start peer
        start_result = await controller.start_peer()
        assert start_result["success"] is True
        assert start_result["action"] == "start"
        assert start_result["status"] == "running"
        
        # Verify model method was called
        libp2p_model.start.assert_called_once()
        
        # Stop peer
        stop_result = await controller.stop_peer()
        assert stop_result["success"] is True
        assert stop_result["action"] == "stop"
        assert stop_result["status"] == "stopped"
        
        # Verify model method was called
        libp2p_model.stop.assert_called_once()
    
    async def test_health_check_async(self, controller, libp2p_model):
        """Test the health_check method directly with async."""
        # Call method directly
        result = await controller.health_check()
        
        # Verify result
        assert result["success"] is True
        assert result["libp2p_available"] is True
        assert result["peer_initialized"] is True
        assert "peer_id" in result
        assert "addresses" in result
        assert "connected_peers" in result
        assert "protocols" in result
        
        # Verify model method was called
        libp2p_model.get_health.assert_called_once()
    
    async def test_content_operations_async(self, controller, libp2p_model):
        """Test content operations directly with async."""
        # Test find_providers
        find_result = await controller.find_providers(cid="QmTest123", timeout=60)
        assert find_result["success"] is True
        assert find_result["cid"] == "QmTest123"
        assert "providers" in find_result
        assert find_result["provider_count"] == 2
        
        # Verify model method was called with correct arguments
        libp2p_model.find_content.assert_called_once_with(cid="QmTest123", timeout=60)
        
        # Test retrieve_content_info
        libp2p_model.find_content.reset_mock()
        info_result = await controller.retrieve_content_info(cid="QmTest123", timeout=60)
        assert info_result["success"] is True
        assert info_result["cid"] == "QmTest123"
        assert "size" in info_result
        assert "provider" in info_result
        assert "metadata" in info_result
        
        # Verify model method was called with correct arguments
        libp2p_model.retrieve_content.assert_called_once_with(cid="QmTest123", timeout=60)
        
        # Test retrieve_content
        content_result = await controller.retrieve_content(cid="QmTest123", timeout=60)
        assert content_result.status_code == 200
        assert content_result.body == b'{"test": "content"}'
        assert content_result.headers["Content-Type"] == "application/json"
        assert content_result.headers["X-Content-CID"] == "QmTest123"
        
        # Verify model method was called with correct arguments
        libp2p_model.get_content.assert_called_once_with(cid="QmTest123", timeout=60)
        
        # Test announce_content
        class MockContentDataRequest:
            def __init__(self):
                self.cid = "QmTest123"
                self.data = b'{"test": "content"}'
        
        announce_result = await controller.announce_content(MockContentDataRequest())
        assert announce_result["success"] is True
        assert announce_result["cid"] == "QmTest123"
        assert "announced_to_peers" in announce_result
        
        # Verify model method was called with correct arguments
        libp2p_model.announce_content.assert_called_once_with(
            cid="QmTest123", data=b'{"test": "content"}'
        )
    
    async def test_peer_discovery_and_info_async(self, controller, libp2p_model):
        """Test peer discovery and info methods directly with async."""
        # Test discover_peers
        class MockPeerDiscoveryRequest:
            def __init__(self):
                self.discovery_method = "all"
                self.limit = 10
        
        discover_result = await controller.discover_peers(MockPeerDiscoveryRequest())
        assert discover_result["success"] is True
        assert "peers" in discover_result
        assert discover_result["peer_count"] == 2
        
        # Verify model method was called with correct arguments
        libp2p_model.discover_peers.assert_called_once_with(
            discovery_method="all", limit=10
        )
        
        # Test get_connected_peers
        connected_result = await controller.get_connected_peers()
        assert connected_result["success"] is True
        assert "peers" in connected_result
        assert connected_result["count"] == 1
        
        # Verify model method was called
        libp2p_model.get_connected_peers.assert_called_once()
        
        # Test get_peer_info
        info_result = await controller.get_peer_info(peer_id="peer1")
        assert info_result["success"] is True
        assert info_result["peer_id"] == "peer1"
        assert "addresses" in info_result
        assert "protocols" in info_result
        
        # Verify model method was called with correct arguments
        libp2p_model.get_peer_info.assert_called_once_with(peer_id="peer1")
    
    async def test_stats_and_reset_async(self, controller, libp2p_model):
        """Test stats and reset methods directly with async."""
        # Test get_stats
        stats_result = await controller.get_stats()
        assert stats_result["success"] is True
        assert "operations" in stats_result
        assert "traffic" in stats_result
        assert "uptime_seconds" in stats_result
        
        # Verify model method was called
        libp2p_model.get_stats.assert_called_once()
        
        # Test reset
        reset_result = await controller.reset()
        assert reset_result["success"] is True
        assert "message" in reset_result
        assert "connections_closed" in reset_result
        assert "stats_reset" in reset_result
        
        # Verify model method was called
        libp2p_model.reset.assert_called_once()
    
    async def test_async_error_handling_direct(self, controller, libp2p_model):
        """Test async error handling by calling methods directly."""
        # Configure model to raise exception during async operation
        libp2p_model.get_peers.side_effect = Exception("Network error")
        
        # Create mock request
        mock_request = MagicMock()
        
        # Expect exception to be caught and converted to error response
        with pytest.raises(Exception):
            await controller.get_peers(mock_request)
    
    async def test_service_unavailable(self, controller, libp2p_model):
        """Test handling of service unavailable."""
        # Configure model to report libp2p as unavailable
        libp2p_model.is_available.return_value = False
        
        # Create mock request
        mock_request = MagicMock()
        
        # Expect HTTP exception with 503 status code
        with pytest.raises(HTTPException) as excinfo:
            await controller.get_peers(mock_request)
        
        # Verify exception details
        assert excinfo.value.status_code == 503
        assert "libp2p is not available" in str(excinfo.value.detail)
            
class TestNewLibP2PEndpoints:
    """Test suite for new endpoints in the LibP2P Controller."""
    
    @pytest.fixture
    def libp2p_model(self):
        """
        Create a mock LibP2P model with support for newer endpoints.
        
        This fixture creates a mock model for testing newer endpoints in the controller.
        It respects the actual dependency status to simulate real-world behavior.
        """
        model = AsyncMock()
        
        # Configure model method return values for newer endpoints
        model.is_available.return_value = HAS_DEPENDENCIES
        
        # Health check operation
        model.get_health.return_value = {
            "success": True,
            "libp2p_available": True,
            "peer_initialized": True,
            "peer_id": "12D3KooWA9BxgkQS2vRED8GZBCVURjEDZHnCxpXQj6Yhc8G5PBL7",
            "addresses": ["/ip4/127.0.0.1/tcp/4001"],
            "connected_peers": 3,
            "dht_peers": 5,
            "protocols": ["/ipfs/kad/1.0.0", "/ipfs/ping/1.0.0"],
            "role": "master",
            "stats": {
                "operations": 10,
                "bytes_sent": 1024,
                "bytes_received": 2048
            }
        }
        
        # Content operations
        model.find_content.return_value = {
            "success": True,
            "cid": "QmTestCID",
            "providers": [
                "/ip4/192.168.1.1/tcp/4001/p2p/12D3KooWPeer1",
                "/ip4/192.168.1.2/tcp/4001/p2p/12D3KooWPeer2"
            ],
            "provider_count": 2
        }
        
        model.retrieve_content.return_value = {
            "success": True,
            "cid": "QmTestCID",
            "size": 1024,
            "provider": "/ip4/192.168.1.1/tcp/4001/p2p/12D3KooWPeer1",
            "metadata": {
                "content_type": "application/json",
                "retrieved_at": 1234567890.123
            }
        }
        
        model.get_content.return_value = {
            "success": True,
            "cid": "QmTestCID",
            "size": 1024,
            "data": b'{"test": "content"}'
        }
        
        model.announce_content.return_value = {
            "success": True,
            "cid": "QmTestCID",
            "size": 1024,
            "announced_to_peers": 3
        }
        
        # Stats and management operations
        model.get_stats.return_value = {
            "success": True,
            "operations": {
                "discover_peers": 5,
                "connect_peer": 3,
                "find_content": 10,
                "retrieve_content": 7,
                "announce_content": 2
            },
            "traffic": {
                "bytes_sent": 10240,
                "bytes_received": 20480,
                "requests_sent": 20,
                "responses_received": 18
            },
            "uptime_seconds": 3600
        }
        
        model.reset.return_value = {
            "success": True,
            "message": "LibP2P state reset successfully",
            "connections_closed": 2,
            "stats_reset": True
        }
        
        return model
    
    @pytest.fixture
    def app(self, libp2p_model):
        """Create a FastAPI app with the LibP2P controller routes registered."""
        app = FastAPI()
        controller = LibP2PController(libp2p_model)
        controller.register_routes(app.router)
        return app
        
    @pytest.fixture
    def client(self, app):
        """Create a test client for the FastAPI app."""
        return TestClient(app)
    
    def test_health_check(self, client, libp2p_model):
        """Test the libp2p health check endpoint."""
        response = client.get("/libp2p/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["libp2p_available"] is True
        assert data["peer_initialized"] is True
        assert "peer_id" in data
        assert "addresses" in data
        assert "connected_peers" in data
        assert "protocols" in data
        
        # Verify model method was called
        libp2p_model.get_health.assert_called_once()
    
    def test_find_providers(self, client, libp2p_model):
        """Test finding providers for a specific CID."""
        response = client.get("/libp2p/providers/QmTestCID")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cid"] == "QmTestCID"
        assert "providers" in data
        assert len(data["providers"]) == 2
        
        # Verify model method was called with correct parameters
        libp2p_model.find_content.assert_called_once()
        
        # Test with custom timeout parameter
        libp2p_model.find_content.reset_mock()
        response = client.get("/libp2p/providers/QmTestCID?timeout=60")
        
        assert response.status_code == 200
        
        # Verify timeout parameter was passed
        call_kwargs = libp2p_model.find_content.call_args.kwargs
        assert call_kwargs["timeout"] == 60
    
    def test_retrieve_content_info(self, client, libp2p_model):
        """Test retrieving content metadata."""
        response = client.get("/libp2p/content/info/QmTestCID")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cid"] == "QmTestCID"
        assert "size" in data
        assert "provider" in data
        assert "metadata" in data
        
        # Verify model method was called with correct parameters
        libp2p_model.retrieve_content.assert_called_once()
    
    def test_retrieve_content(self, client, libp2p_model):
        """Test retrieving actual content data."""
        mock_content = b'{"test": "content"}'
        libp2p_model.get_content.return_value = {
            "success": True,
            "cid": "QmTestCID",
            "size": len(mock_content),
            "data": mock_content
        }
        
        response = client.get("/libp2p/content/QmTestCID")
        
        assert response.status_code == 200
        assert response.content == mock_content
        assert response.headers["Content-Type"] == "application/json"
        assert "X-Content-CID" in response.headers
        
        # Verify model method was called with correct parameters
        libp2p_model.get_content.assert_called_once()
    
    def test_announce_content(self, client, libp2p_model):
        """Test content announcement endpoint."""
        response = client.post(
            "/libp2p/announce",
            json={
                "cid": "QmTestCID",
                "data": "SGVsbG8gV29ybGQ="  # Base64 encoded 'Hello World'
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cid"] == "QmTestCID"
        assert "announced_to_peers" in data
        
        # Verify model method was called with correct parameters
        libp2p_model.announce_content.assert_called_once()
    
    def test_get_stats(self, client, libp2p_model):
        """Test getting operation statistics."""
        response = client.get("/libp2p/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "operations" in data
        assert "traffic" in data
        assert "uptime_seconds" in data
        
        # Verify model method was called
        libp2p_model.get_stats.assert_called_once()
    
    def test_reset(self, client, libp2p_model):
        """Test resetting the LibP2P state."""
        response = client.post("/libp2p/reset")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "message" in data
        assert "connections_closed" in data
        assert "stats_reset" in data
        
        # Verify model method was called
        libp2p_model.reset.assert_called_once()