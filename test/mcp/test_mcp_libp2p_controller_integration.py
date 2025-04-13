"""
Integration tests for the LibP2P Controller in the MCP server.

This module verifies that the LibP2P Controller is properly integrated
with the MCP server architecture, focusing on:
1. Proper registration of routes in the server
2. Correct functioning of endpoints when accessed via the server
3. Error handling and graceful degradation when libp2p is not available
4. Testing that the AnyIO version works properly with the server
"""

import pytest
import logging
import asyncio
import os
import sys
import json
import time
from unittest.mock import MagicMock, patch, AsyncMock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check FastAPI availability
try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logger.warning("FastAPI not available, will skip controller integration tests")

# Check and potentially install libp2p dependencies
try:
    from install_libp2p import install_dependencies_auto, check_dependency, HAS_LIBP2P
    HAS_INSTALL_LIBP2P = True
except ImportError:
    HAS_INSTALL_LIBP2P = False
    HAS_LIBP2P = False
    logger.warning("install_libp2p module not available, using mock dependencies")

# Check AnyIO availability
try:
    import anyio
    HAS_ANYIO = True
except ImportError:
    HAS_ANYIO = False
    logger.warning("AnyIO not available, will skip AnyIO-specific tests")

# Skip all tests if FastAPI is not available
pytestmark = pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not installed")

class TestLibP2PControllerServerIntegration:
    """Test suite for integrating the LibP2P Controller with MCP server."""
    
    @pytest.fixture
    def libp2p_model(self):
        """Create a mock LibP2P model for testing."""
        model = MagicMock()
        
        # Set basic availability
        model.is_available.return_value = True
        
        # Configure health check
        model.get_health.return_value = {
            "success": True,
            "libp2p_available": True,
            "peer_initialized": True,
            "peer_id": "test-peer-id",
            "addresses": ["/ip4/127.0.0.1/tcp/4001"],
            "connected_peers": 0,
            "dht_peers": 0,
            "protocols": [],
            "role": "leecher",
            "stats": {
                "operation_count": 0,
                "peers_discovered": 0,
                "content_retrieved": 0
            }
        }
        
        # Configure peer discovery
        model.discover_peers.return_value = {
            "success": True,
            "operation": "discover_peers",
            "peers": [
                "/ip4/127.0.0.1/tcp/4001/p2p/12D3KooWPeer1",
                "/ip4/192.168.1.1/tcp/4001/p2p/12D3KooWPeer2"
            ],
            "peer_count": 2
        }
        
        # Configure peer connection
        model.connect_peer.return_value = {
            "success": True,
            "operation": "connect_peer",
            "peer_addr": "/ip4/127.0.0.1/tcp/4001/p2p/12D3KooWPeer1"
        }
        
        # Configure DHT operations
        model.dht_find_peer.return_value = {
            "success": True,
            "operation": "dht_find_peer",
            "peer_id": "12D3KooWPeer1",
            "addresses": ["/ip4/127.0.0.1/tcp/4001"]
        }
        
        model.dht_provide.return_value = {
            "success": True,
            "operation": "dht_provide",
            "cid": "QmTest123"
        }
        
        model.dht_find_providers.return_value = {
            "success": True,
            "operation": "dht_find_providers",
            "cid": "QmTest123",
            "providers": [
                "/ip4/127.0.0.1/tcp/4001/p2p/12D3KooWPeer1",
                "/ip4/192.168.1.1/tcp/4001/p2p/12D3KooWPeer2"
            ]
        }
        
        # Configure content operations
        model.find_content.return_value = {
            "success": True,
            "cid": "QmTest123",
            "providers": [
                "/ip4/127.0.0.1/tcp/4001/p2p/12D3KooWPeer1",
                "/ip4/192.168.1.1/tcp/4001/p2p/12D3KooWPeer2"
            ],
            "provider_count": 2
        }
        
        model.retrieve_content.return_value = {
            "success": True,
            "cid": "QmTest123",
            "size": 13,
            "data": b'{"test": true}',
            "provider": "/ip4/127.0.0.1/tcp/4001/p2p/12D3KooWPeer1"
        }
        
        model.get_content.return_value = {
            "success": True,
            "cid": "QmTest123",
            "size": 13,
            "data": b'{"test": true}'
        }
        
        model.announce_content.return_value = {
            "success": True,
            "cid": "QmTest123",
            "size": 13,
            "announced_to_peers": 2
        }
        
        # Configure PubSub operations
        model.pubsub_publish.return_value = {
            "success": True,
            "operation": "pubsub_publish",
            "topic": "test-topic",
            "message_id": "msg123"
        }
        
        model.pubsub_subscribe.return_value = {
            "success": True,
            "operation": "pubsub_subscribe",
            "topic": "test-topic"
        }
        
        model.pubsub_unsubscribe.return_value = {
            "success": True,
            "operation": "pubsub_unsubscribe",
            "topic": "test-topic"
        }
        
        model.pubsub_get_topics.return_value = {
            "success": True,
            "operation": "pubsub_get_topics",
            "topics": ["test-topic1", "test-topic2"]
        }
        
        model.pubsub_get_peers.return_value = {
            "success": True,
            "operation": "pubsub_get_peers",
            "topic": "test-topic",
            "peers": ["peer1", "peer2"]
        }
        
        # Configure message handlers
        model.register_message_handler.return_value = {
            "success": True,
            "operation": "register_message_handler",
            "handler_id": "test-handler",
            "protocol_id": "/test/1.0.0"
        }
        
        model.unregister_message_handler.return_value = {
            "success": True,
            "operation": "unregister_message_handler",
            "handler_id": "test-handler",
            "protocol_id": "/test/1.0.0"
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
            ]
        }
        
        # Configure lifecycle operations
        model.start.return_value = {
            "success": True,
            "action": "start",
            "status": "running"
        }
        
        model.stop.return_value = {
            "success": True,
            "action": "stop",
            "status": "stopped"
        }
        
        # Configure peer info
        model.get_peer_info.return_value = {
            "success": True,
            "operation": "get_peer_info",
            "peer_id": "peer1",
            "addresses": ["/ip4/127.0.0.1/tcp/4001"],
            "connected": True
        }
        
        model.get_connected_peers.return_value = {
            "success": True,
            "operation": "get_connected_peers",
            "peers": [
                {
                    "id": "peer1",
                    "addresses": ["/ip4/127.0.0.1/tcp/4001"],
                    "latency_ms": 10
                }
            ],
            "count": 1
        }
        
        # Configure stats
        model.get_stats.return_value = {
            "success": True,
            "operation": "get_stats",
            "operations": {
                "discover_peers": 1,
                "connect_peer": 1,
                "dht_lookup": 1
            }
        }
        
        # Configure reset
        model.reset.return_value = {
            "success": True,
            "operation": "reset",
            "message": "LibP2P state reset successfully"
        }
        
        return model
    
    @pytest.fixture
    def mcp_server(self, libp2p_model):
        """Create an MCP server with the LibP2P controller."""
        # Import MCP server
        try:
            from ipfs_kit_py.mcp.server import MCPServer
            # Create server with mock components
            server = MCPServer(debug_mode=True)
            
            # Replace models with mocks
            server.models = {"libp2p": libp2p_model}
            
            # Initialize controllers
            from ipfs_kit_py.mcp.controllers.libp2p_controller import LibP2PController
            server.controllers = {
                "libp2p": LibP2PController(libp2p_model)
            }
            
            # Create FastAPI app
            server.app = FastAPI(title="MCP Server Test")
            
            # Register routes
            router = server.register_controllers()
            
            # Include the router in the app
            server.app.include_router(router)
            
            return server
        except ImportError as e:
            pytest.skip(f"MCP server not available: {str(e)}")
            return None
    
    @pytest.fixture
    def client(self, mcp_server):
        """Create a test client for the MCP server."""
        if mcp_server is None:
            pytest.skip("MCP server not available")
        return TestClient(mcp_server.app)
    
    def test_server_health(self, client, libp2p_model):
        """Test the MCP server health endpoint with LibP2P integration."""
        response = client.get("/health")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "controllers" in data
        assert "libp2p" in data["controllers"]
        
        # Verify the model method was called
        libp2p_model.get_health.assert_called_once()
    
    def test_libp2p_health(self, client, libp2p_model):
        """Test the LibP2P health endpoint via MCP server."""
        response = client.get("/libp2p/health")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["libp2p_available"] is True
        assert data["peer_initialized"] is True
        assert "peer_id" in data
        assert "addresses" in data
        assert "protocols" in data
        
        # Verify the model method was called
        libp2p_model.get_health.assert_called_once()
    
    def test_discover_peers(self, client, libp2p_model):
        """Test the discover peers endpoint via MCP server."""
        response = client.post(
            "/libp2p/discover",
            json={"discovery_method": "all", "limit": 10}
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "peers" in data
        assert len(data["peers"]) == 2
        assert "peer_count" in data
        
        # Verify the model method was called with correct arguments
        libp2p_model.discover_peers.assert_called_once_with(
            discovery_method="all",
            limit=10
        )
    
    def test_get_peers(self, client, libp2p_model):
        """Test the get peers endpoint via MCP server."""
        response = client.get("/libp2p/peers?method=all&limit=10")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "peers" in data
        assert len(data["peers"]) == 2
        
        # Verify the model method was called with correct arguments
        libp2p_model.discover_peers.assert_called_once_with(
            discovery_method="all",
            limit=10
        )
    
    def test_connect_peer(self, client, libp2p_model):
        """Test the connect peer endpoint via MCP server."""
        response = client.post(
            "/libp2p/connect",
            json={"peer_addr": "/ip4/127.0.0.1/tcp/4001/p2p/12D3KooWPeer1"}
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify the model method was called with correct arguments
        libp2p_model.connect_peer.assert_called_once_with(
            peer_addr="/ip4/127.0.0.1/tcp/4001/p2p/12D3KooWPeer1"
        )
    
    def test_find_providers(self, client, libp2p_model):
        """Test the find providers endpoint via MCP server."""
        response = client.get("/libp2p/providers/QmTest123?timeout=60")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cid"] == "QmTest123"
        assert "providers" in data
        assert len(data["providers"]) == 2
        
        # Verify the model method was called with correct arguments
        libp2p_model.find_content.assert_called_once_with(
            cid="QmTest123",
            timeout=60
        )
    
    def test_retrieve_content_info(self, client, libp2p_model):
        """Test the retrieve content info endpoint via MCP server."""
        response = client.get("/libp2p/content/info/QmTest123?timeout=60")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cid"] == "QmTest123"
        assert "size" in data
        assert "provider" in data
        
        # Verify the model method was called with correct arguments
        libp2p_model.retrieve_content.assert_called_once_with(
            cid="QmTest123",
            timeout=60
        )
    
    def test_retrieve_content(self, client, libp2p_model):
        """Test the retrieve content endpoint via MCP server."""
        response = client.get("/libp2p/content/QmTest123?timeout=60")
        
        # Check response
        assert response.status_code == 200
        assert response.content == b'{"test": true}'
        assert response.headers["Content-Type"] == "application/json"
        assert response.headers["X-Content-CID"] == "QmTest123"
        
        # Verify the model method was called with correct arguments
        libp2p_model.get_content.assert_called_once_with(
            cid="QmTest123",
            timeout=60
        )
    
    def test_announce_content(self, client, libp2p_model):
        """Test the announce content endpoint via MCP server."""
        response = client.post(
            "/libp2p/announce",
            json={"cid": "QmTest123", "data": b'{"test": true}'.decode('latin1')}
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cid"] == "QmTest123"
        assert "announced_to_peers" in data
        
        # Verify model method was called (note: we can't verify exact binary data due to encoding issues)
        assert libp2p_model.announce_content.called
    
    def test_get_connected_peers(self, client, libp2p_model):
        """Test the get connected peers endpoint via MCP server."""
        response = client.get("/libp2p/connected")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "peers" in data
        assert len(data["peers"]) == 1
        assert "count" in data
        
        # Verify the model method was called
        libp2p_model.get_connected_peers.assert_called_once()
    
    def test_get_peer_info(self, client, libp2p_model):
        """Test the get peer info endpoint via MCP server."""
        response = client.get("/libp2p/peer/peer1")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["peer_id"] == "peer1"
        assert "addresses" in data
        assert data["connected"] is True
        
        # Verify the model method was called with correct arguments
        libp2p_model.get_peer_info.assert_called_once_with(
            peer_id="peer1"
        )
    
    def test_get_stats(self, client, libp2p_model):
        """Test the get stats endpoint via MCP server."""
        response = client.get("/libp2p/stats")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "operations" in data
        
        # Verify the model method was called
        libp2p_model.get_stats.assert_called_once()
    
    def test_reset(self, client, libp2p_model):
        """Test the reset endpoint via MCP server."""
        response = client.post("/libp2p/reset")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "message" in data
        
        # Verify the model method was called
        libp2p_model.reset.assert_called_once()
    
    def test_start_peer(self, client, libp2p_model):
        """Test the start peer endpoint via MCP server."""
        response = client.post("/libp2p/start")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "start"
        assert data["status"] == "running"
        
        # Verify the model method was called
        libp2p_model.start.assert_called_once()
    
    def test_stop_peer(self, client, libp2p_model):
        """Test the stop peer endpoint via MCP server."""
        response = client.post("/libp2p/stop")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "stop"
        assert data["status"] == "stopped"
        
        # Verify the model method was called
        libp2p_model.stop.assert_called_once()
    
    def test_dht_find_peer(self, client, libp2p_model):
        """Test the DHT find peer endpoint via MCP server."""
        response = client.post(
            "/libp2p/dht/find_peer",
            json={"peer_id": "12D3KooWPeer1", "timeout": 30}
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["peer_id"] == "12D3KooWPeer1"
        assert "addresses" in data
        
        # Verify the model method was called with correct arguments
        libp2p_model.dht_find_peer.assert_called_once_with(
            peer_id="12D3KooWPeer1",
            timeout=30
        )
    
    def test_dht_provide(self, client, libp2p_model):
        """Test the DHT provide endpoint via MCP server."""
        response = client.post(
            "/libp2p/dht/provide",
            json={"cid": "QmTest123"}
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cid"] == "QmTest123"
        
        # Verify the model method was called with correct arguments
        libp2p_model.dht_provide.assert_called_once_with(
            cid="QmTest123"
        )
    
    def test_dht_find_providers(self, client, libp2p_model):
        """Test the DHT find providers endpoint via MCP server."""
        response = client.post(
            "/libp2p/dht/find_providers",
            json={"cid": "QmTest123", "timeout": 30, "limit": 20}
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cid"] == "QmTest123"
        assert "providers" in data
        
        # Verify the model method was called with correct arguments
        libp2p_model.dht_find_providers.assert_called_once_with(
            cid="QmTest123",
            timeout=30,
            limit=20
        )
    
    def test_pubsub_publish(self, client, libp2p_model):
        """Test the pubsub publish endpoint via MCP server."""
        response = client.post(
            "/libp2p/pubsub/publish",
            json={"topic": "test-topic", "message": "Hello, world!"}
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["topic"] == "test-topic"
        assert "message_id" in data
        
        # Verify the model method was called with correct arguments
        libp2p_model.pubsub_publish.assert_called_once_with(
            topic="test-topic",
            message="Hello, world!"
        )
    
    def test_pubsub_subscribe(self, client, libp2p_model):
        """Test the pubsub subscribe endpoint via MCP server."""
        response = client.post(
            "/libp2p/pubsub/subscribe",
            json={"topic": "test-topic", "handler_id": "test-handler"}
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["topic"] == "test-topic"
        
        # Verify the model method was called with correct arguments
        libp2p_model.pubsub_subscribe.assert_called_once_with(
            topic="test-topic",
            handler_id="test-handler"
        )
    
    def test_pubsub_unsubscribe(self, client, libp2p_model):
        """Test the pubsub unsubscribe endpoint via MCP server."""
        response = client.post(
            "/libp2p/pubsub/unsubscribe",
            json={"topic": "test-topic", "handler_id": "test-handler"}
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["topic"] == "test-topic"
        
        # Verify the model method was called with correct arguments
        libp2p_model.pubsub_unsubscribe.assert_called_once_with(
            topic="test-topic",
            handler_id="test-handler"
        )
    
    def test_pubsub_get_topics(self, client, libp2p_model):
        """Test the pubsub get topics endpoint via MCP server."""
        response = client.get("/libp2p/pubsub/topics")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "topics" in data
        assert len(data["topics"]) == 2
        
        # Verify the model method was called
        libp2p_model.pubsub_get_topics.assert_called_once()
    
    def test_pubsub_get_peers(self, client, libp2p_model):
        """Test the pubsub get peers endpoint via MCP server."""
        response = client.get("/libp2p/pubsub/peers?topic=test-topic")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "peers" in data
        assert len(data["peers"]) == 2
        assert "topic" in data
        
        # Verify the model method was called with correct arguments
        libp2p_model.pubsub_get_peers.assert_called_once_with("test-topic")
    
    def test_register_message_handler(self, client, libp2p_model):
        """Test the register message handler endpoint via MCP server."""
        response = client.post(
            "/libp2p/handlers/register",
            json={
                "handler_id": "test-handler",
                "protocol_id": "/test/1.0.0",
                "description": "Test handler"
            }
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["handler_id"] == "test-handler"
        assert data["protocol_id"] == "/test/1.0.0"
        
        # Verify the model method was called with correct arguments
        libp2p_model.register_message_handler.assert_called_once_with(
            handler_id="test-handler",
            protocol_id="/test/1.0.0",
            description="Test handler"
        )
    
    def test_unregister_message_handler(self, client, libp2p_model):
        """Test the unregister message handler endpoint via MCP server."""
        response = client.post(
            "/libp2p/handlers/unregister",
            json={
                "handler_id": "test-handler",
                "protocol_id": "/test/1.0.0"
            }
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["handler_id"] == "test-handler"
        assert data["protocol_id"] == "/test/1.0.0"
        
        # Verify the model method was called with correct arguments
        libp2p_model.unregister_message_handler.assert_called_once_with(
            handler_id="test-handler",
            protocol_id="/test/1.0.0"
        )
    
    def test_list_message_handlers(self, client, libp2p_model):
        """Test the list message handlers endpoint via MCP server."""
        response = client.get("/libp2p/handlers/list")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "handlers" in data
        assert len(data["handlers"]) == 1
        assert data["handlers"][0]["handler_id"] == "test-handler"
        
        # Verify the model method was called
        libp2p_model.list_message_handlers.assert_called_once()
    
    def test_unavailable_libp2p(self, client, libp2p_model):
        """Test behavior when LibP2P is not available."""
        # Configure model to simulate LibP2P being unavailable
        libp2p_model.is_available.return_value = False
        libp2p_model.get_health.return_value = {
            "success": False,
            "libp2p_available": False,
            "peer_initialized": False,
            "error": "libp2p is not available",
            "error_type": "dependency_missing"
        }
        
        # Test health endpoint
        response = client.get("/libp2p/health")
        
        # Check response - should still return data but with failure status
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["libp2p_available"] is False
        assert data["peer_initialized"] is False
        assert "error" in data
        
        # Test functional endpoint - should return error
        response = client.get("/libp2p/peers")
        
        # Expect HTTP exception with 503 status
        assert response.status_code == 503
        data = response.json()
        assert "detail" in data
        assert "not available" in data["detail"]


@pytest.mark.anyio
# @pytest.mark.skipif(...) - removed by fix_all_tests.py
class TestLibP2PControllerAnyioServerIntegration:
    """Test suite for integrating the AnyIO version of LibP2P Controller with MCP server."""
    
    @pytest.fixture
    def libp2p_model(self):
        """Create a mock LibP2P model for testing with AnyIO support."""
        model = AsyncMock()
        
        # Set basic availability
        model.is_available.return_value = True
        
        # Configure health check
        model.get_health.return_value = {
            "success": True,
            "libp2p_available": True,
            "peer_initialized": True,
            "peer_id": "test-peer-id",
            "addresses": ["/ip4/127.0.0.1/tcp/4001"],
            "connected_peers": 0,
            "dht_peers": 0,
            "protocols": [],
            "role": "leecher",
            "stats": {
                "operation_count": 0,
                "peers_discovered": 0,
                "content_retrieved": 0
            }
        }
        
        # Configure discover peers
        model.discover_peers.return_value = {
            "success": True,
            "operation": "discover_peers",
            "peers": [
                "/ip4/127.0.0.1/tcp/4001/p2p/12D3KooWPeer1",
                "/ip4/192.168.1.1/tcp/4001/p2p/12D3KooWPeer2"
            ],
            "peer_count": 2
        }
        
        # Configure peer connection
        model.connect_peer.return_value = {
            "success": True,
            "operation": "connect_peer",
            "peer_addr": "/ip4/127.0.0.1/tcp/4001/p2p/12D3KooWPeer1"
        }
        
        # Configure DHT operations
        model.dht_find_peer.return_value = {
            "success": True,
            "operation": "dht_find_peer",
            "peer_id": "12D3KooWPeer1",
            "addresses": ["/ip4/127.0.0.1/tcp/4001"]
        }
        
        model.dht_provide.return_value = {
            "success": True,
            "operation": "dht_provide",
            "cid": "QmTest123"
        }
        
        model.dht_find_providers.return_value = {
            "success": True,
            "operation": "dht_find_providers",
            "cid": "QmTest123",
            "providers": [
                "/ip4/127.0.0.1/tcp/4001/p2p/12D3KooWPeer1",
                "/ip4/192.168.1.1/tcp/4001/p2p/12D3KooWPeer2"
            ]
        }
        
        # Configure content operations
        model.find_content.return_value = {
            "success": True,
            "cid": "QmTest123",
            "providers": [
                "/ip4/127.0.0.1/tcp/4001/p2p/12D3KooWPeer1",
                "/ip4/192.168.1.1/tcp/4001/p2p/12D3KooWPeer2"
            ],
            "provider_count": 2
        }
        
        model.retrieve_content.return_value = {
            "success": True,
            "cid": "QmTest123",
            "size": 13,
            "data": b'{"test": true}',
            "provider": "/ip4/127.0.0.1/tcp/4001/p2p/12D3KooWPeer1"
        }
        
        model.get_content.return_value = {
            "success": True,
            "cid": "QmTest123",
            "size": 13,
            "data": b'{"test": true}'
        }
        
        model.announce_content.return_value = {
            "success": True,
            "cid": "QmTest123",
            "size": 13,
            "announced_to_peers": 2
        }
        
        # Configure PubSub operations
        model.pubsub_publish.return_value = {
            "success": True,
            "operation": "pubsub_publish",
            "topic": "test-topic",
            "message_id": "msg123"
        }
        
        model.pubsub_subscribe.return_value = {
            "success": True,
            "operation": "pubsub_subscribe",
            "topic": "test-topic"
        }
        
        model.pubsub_unsubscribe.return_value = {
            "success": True,
            "operation": "pubsub_unsubscribe",
            "topic": "test-topic"
        }
        
        model.pubsub_get_topics.return_value = {
            "success": True,
            "operation": "pubsub_get_topics",
            "topics": ["test-topic1", "test-topic2"]
        }
        
        model.pubsub_get_peers.return_value = {
            "success": True,
            "operation": "pubsub_get_peers",
            "topic": "test-topic",
            "peers": ["peer1", "peer2"]
        }
        
        # Configure message handlers
        model.register_message_handler.return_value = {
            "success": True,
            "operation": "register_message_handler",
            "handler_id": "test-handler",
            "protocol_id": "/test/1.0.0"
        }
        
        model.unregister_message_handler.return_value = {
            "success": True,
            "operation": "unregister_message_handler",
            "handler_id": "test-handler",
            "protocol_id": "/test/1.0.0"
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
            ]
        }
        
        # Configure lifecycle operations
        model.start.return_value = {
            "success": True,
            "action": "start",
            "status": "running"
        }
        
        model.stop.return_value = {
            "success": True,
            "action": "stop",
            "status": "stopped"
        }
        
        # Configure peer info
        model.get_peer_info.return_value = {
            "success": True,
            "operation": "get_peer_info",
            "peer_id": "peer1",
            "addresses": ["/ip4/127.0.0.1/tcp/4001"],
            "connected": True
        }
        
        model.get_connected_peers.return_value = {
            "success": True,
            "operation": "get_connected_peers",
            "peers": [
                {
                    "id": "peer1",
                    "addresses": ["/ip4/127.0.0.1/tcp/4001"],
                    "latency_ms": 10
                }
            ],
            "count": 1
        }
        
        # Configure stats
        model.get_stats.return_value = {
            "success": True,
            "operation": "get_stats",
            "operations": {
                "discover_peers": 1,
                "connect_peer": 1,
                "dht_lookup": 1
            }
        }
        
        # Configure reset
        model.reset.return_value = {
            "success": True,
            "operation": "reset",
            "message": "LibP2P state reset successfully"
        }
        
        return model
    
    @pytest.fixture
    def mcp_server(self, libp2p_model):
        """Create an MCP server with the AnyIO version of LibP2P controller."""
        try:
            # Try to import AnyIO version of MCP server
            from ipfs_kit_py.mcp.server_anyio import MCPServer as MCPServerAnyIO
            # Create server with mock components
            server = MCPServerAnyIO(debug_mode=True)
            
            # Replace models with mocks
            server.models = {"libp2p": libp2p_model}
            
            # Initialize controllers
            from ipfs_kit_py.mcp.controllers.libp2p_controller_anyio import LibP2PControllerAnyIO
            server.controllers = {
                "libp2p": LibP2PControllerAnyIO(libp2p_model)
            }
            
            # Create FastAPI app
            server.app = FastAPI(title="MCP Server AnyIO Test")
            
            # Register routes
            router = server.register_controllers()
            
            # Include the router in the app
            server.app.include_router(router)
            
            return server
        except ImportError as e:
            pytest.skip(f"AnyIO MCP server not available: {str(e)}")
            return None
    
    @pytest.fixture
    def client(self, mcp_server):
        """Create a test client for the AnyIO MCP server."""
        if mcp_server is None:
            pytest.skip("AnyIO MCP server not available")
        return TestClient(mcp_server.app)
    
    async def test_health_check(self, client, libp2p_model):
        """Test the LibP2P health endpoint with AnyIO support."""
        response = client.get("/libp2p/health")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "libp2p_available" in data
        assert "peer_initialized" in data
        
        # AnyIO version should use the _async methods internally
        assert libp2p_model.get_health.called
    
    async def test_discover_peers(self, client, libp2p_model):
        """Test the discover peers endpoint with AnyIO support."""
        response = client.post(
            "/libp2p/discover",
            json={"discovery_method": "all", "limit": 10}
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "peers" in data
        
        # AnyIO version should use the _async methods internally
        assert libp2p_model.discover_peers.called
        
    async def test_get_peers(self, client, libp2p_model):
        """Test the get peers endpoint with AnyIO support."""
        response = client.get("/libp2p/peers?method=all&limit=10")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "peers" in data
        assert len(data["peers"]) == 2
        
        # Verify the model method was called
        assert libp2p_model.discover_peers.called
    
    async def test_connect_peer(self, client, libp2p_model):
        """Test the connect peer endpoint with AnyIO support."""
        response = client.post(
            "/libp2p/connect",
            json={"peer_addr": "/ip4/127.0.0.1/tcp/4001/p2p/12D3KooWPeer1"}
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        
        # Verify the model method was called
        assert libp2p_model.connect_peer.called
    
    async def test_find_providers(self, client, libp2p_model):
        """Test the find providers endpoint with AnyIO support."""
        response = client.get("/libp2p/providers/QmTest123?timeout=60")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "providers" in data
        
        # Verify the model method was called
        assert libp2p_model.find_content.called
    
    async def test_retrieve_content_info(self, client, libp2p_model):
        """Test the retrieve content info endpoint with AnyIO support."""
        response = client.get("/libp2p/content/info/QmTest123?timeout=60")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "cid" in data
        
        # Verify the model method was called
        assert libp2p_model.retrieve_content.called
    
    async def test_retrieve_content(self, client, libp2p_model):
        """Test the retrieve content endpoint with AnyIO support."""
        response = client.get("/libp2p/content/QmTest123?timeout=60")
        
        # Check response
        assert response.status_code == 200
        assert response.content == b'{"test": true}'
        
        # Verify the model method was called
        assert libp2p_model.get_content.called
    
    async def test_announce_content(self, client, libp2p_model):
        """Test the announce content endpoint with AnyIO support."""
        response = client.post(
            "/libp2p/announce",
            json={"cid": "QmTest123", "data": b'{"test": true}'.decode('latin1')}
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "cid" in data
        
        # Verify the model method was called
        assert libp2p_model.announce_content.called
    
    async def test_get_connected_peers(self, client, libp2p_model):
        """Test the get connected peers endpoint with AnyIO support."""
        response = client.get("/libp2p/connected")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "peers" in data
        
        # Verify the model method was called
        assert libp2p_model.get_connected_peers.called
    
    async def test_get_peer_info(self, client, libp2p_model):
        """Test the get peer info endpoint with AnyIO support."""
        response = client.get("/libp2p/peer/peer1")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "peer_id" in data
        
        # Verify the model method was called
        assert libp2p_model.get_peer_info.called
    
    async def test_get_stats(self, client, libp2p_model):
        """Test the get stats endpoint with AnyIO support."""
        response = client.get("/libp2p/stats")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "operations" in data
        
        # Verify the model method was called
        assert libp2p_model.get_stats.called
    
    async def test_reset(self, client, libp2p_model):
        """Test the reset endpoint with AnyIO support."""
        response = client.post("/libp2p/reset")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "message" in data
        
        # Verify the model method was called
        assert libp2p_model.reset.called
    
    async def test_start_peer(self, client, libp2p_model):
        """Test the start peer endpoint with AnyIO support."""
        response = client.post("/libp2p/start")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "action" in data
        assert data["action"] == "start"
        
        # Verify the model method was called
        assert libp2p_model.start.called
    
    async def test_stop_peer(self, client, libp2p_model):
        """Test the stop peer endpoint with AnyIO support."""
        response = client.post("/libp2p/stop")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "action" in data
        assert data["action"] == "stop"
        
        # Verify the model method was called
        assert libp2p_model.stop.called
    
    async def test_dht_find_peer(self, client, libp2p_model):
        """Test the DHT find peer endpoint with AnyIO support."""
        response = client.post(
            "/libp2p/dht/find_peer",
            json={"peer_id": "12D3KooWPeer1", "timeout": 30}
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "peer_id" in data
        assert "addresses" in data
        
        # Verify the model method was called
        assert libp2p_model.dht_find_peer.called
    
    async def test_dht_provide(self, client, libp2p_model):
        """Test the DHT provide endpoint with AnyIO support."""
        response = client.post(
            "/libp2p/dht/provide",
            json={"cid": "QmTest123"}
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "cid" in data
        
        # Verify the model method was called
        assert libp2p_model.dht_provide.called
    
    async def test_dht_find_providers(self, client, libp2p_model):
        """Test the DHT find providers endpoint with AnyIO support."""
        response = client.post(
            "/libp2p/dht/find_providers",
            json={"cid": "QmTest123", "timeout": 30, "limit": 20}
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "cid" in data
        assert "providers" in data
        
        # Verify the model method was called
        assert libp2p_model.dht_find_providers.called
    
    async def test_pubsub_publish(self, client, libp2p_model):
        """Test the pubsub publish endpoint with AnyIO support."""
        response = client.post(
            "/libp2p/pubsub/publish",
            json={"topic": "test-topic", "message": "Hello, world!"}
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "topic" in data
        assert "message_id" in data
        
        # Verify the model method was called
        assert libp2p_model.pubsub_publish.called
    
    async def test_pubsub_subscribe(self, client, libp2p_model):
        """Test the pubsub subscribe endpoint with AnyIO support."""
        response = client.post(
            "/libp2p/pubsub/subscribe",
            json={"topic": "test-topic", "handler_id": "test-handler"}
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "topic" in data
        
        # Verify the model method was called
        assert libp2p_model.pubsub_subscribe.called
    
    async def test_pubsub_unsubscribe(self, client, libp2p_model):
        """Test the pubsub unsubscribe endpoint with AnyIO support."""
        response = client.post(
            "/libp2p/pubsub/unsubscribe",
            json={"topic": "test-topic", "handler_id": "test-handler"}
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "topic" in data
        
        # Verify the model method was called
        assert libp2p_model.pubsub_unsubscribe.called
    
    async def test_pubsub_get_topics(self, client, libp2p_model):
        """Test the pubsub get topics endpoint with AnyIO support."""
        response = client.get("/libp2p/pubsub/topics")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "topics" in data
        
        # Verify the model method was called
        assert libp2p_model.pubsub_get_topics.called
    
    async def test_pubsub_get_peers(self, client, libp2p_model):
        """Test the pubsub get peers endpoint with AnyIO support."""
        response = client.get("/libp2p/pubsub/peers?topic=test-topic")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "peers" in data
        assert "topic" in data
        
        # Verify the model method was called
        assert libp2p_model.pubsub_get_peers.called
    
    async def test_register_message_handler(self, client, libp2p_model):
        """Test the register message handler endpoint with AnyIO support."""
        response = client.post(
            "/libp2p/handlers/register",
            json={
                "handler_id": "test-handler",
                "protocol_id": "/test/1.0.0",
                "description": "Test handler"
            }
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "handler_id" in data
        assert "protocol_id" in data
        
        # Verify the model method was called
        assert libp2p_model.register_message_handler.called
    
    async def test_unregister_message_handler(self, client, libp2p_model):
        """Test the unregister message handler endpoint with AnyIO support."""
        response = client.post(
            "/libp2p/handlers/unregister",
            json={
                "handler_id": "test-handler",
                "protocol_id": "/test/1.0.0"
            }
        )
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "handler_id" in data
        assert "protocol_id" in data
        
        # Verify the model method was called
        assert libp2p_model.unregister_message_handler.called
    
    async def test_list_message_handlers(self, client, libp2p_model):
        """Test the list message handlers endpoint with AnyIO support."""
        response = client.get("/libp2p/handlers/list")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "handlers" in data
        
        # Verify the model method was called
        assert libp2p_model.list_message_handlers.called
        
    async def test_unavailable_libp2p(self, client, libp2p_model):
        """Test behavior when LibP2P is not available in AnyIO controller."""
        # Configure model to simulate LibP2P being unavailable
        libp2p_model.is_available.return_value = False
        libp2p_model.get_health.return_value = {
            "success": False,
            "libp2p_available": False,
            "peer_initialized": False,
            "error": "libp2p is not available",
            "error_type": "dependency_missing"
        }
        
        # Test health endpoint
        response = client.get("/libp2p/health")
        
        # Check response - should still return data but with failure status
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["libp2p_available"] is False
        assert data["peer_initialized"] is False
        assert "error" in data
        
        # Test functional endpoint - should return error
        response = client.get("/libp2p/peers")
        
        # Expect HTTP exception with 503 status
        assert response.status_code == 503
        data = response.json()
        assert "detail" in data
        assert "not available" in data["detail"]


# @pytest.mark.skipif(...) - removed by fix_all_tests.py
class TestLibP2PControllerComparison:
    """Test suite for comparing standard and AnyIO versions of the LibP2P controller."""
    
    @pytest.fixture
    def libp2p_model(self):
        """Create a mock LibP2P model for testing."""
        model = MagicMock()
        
        # Set basic availability
        model.is_available.return_value = True
        
        # Configure health check
        model.get_health.return_value = {
            "success": True,
            "libp2p_available": True,
            "peer_initialized": True,
            "peer_id": "test-peer-id",
            "addresses": ["/ip4/127.0.0.1/tcp/4001"],
            "connected_peers": 0,
            "dht_peers": 0,
            "protocols": [],
            "role": "leecher",
            "stats": {
                "operation_count": 0,
                "peers_discovered": 0,
                "content_retrieved": 0
            }
        }
        
        # Configure discover peers
        model.discover_peers.return_value = {
            "success": True,
            "operation": "discover_peers",
            "peers": [
                "/ip4/127.0.0.1/tcp/4001/p2p/12D3KooWPeer1",
                "/ip4/192.168.1.1/tcp/4001/p2p/12D3KooWPeer2"
            ],
            "peer_count": 2
        }
        
        # Configure DHT find peer
        model.dht_find_peer.return_value = {
            "success": True,
            "operation": "dht_find_peer",
            "peer_id": "12D3KooWPeer1",
            "addresses": ["/ip4/127.0.0.1/tcp/4001"]
        }
        
        return model
    
    @pytest.fixture
    def mcp_standard_server(self, libp2p_model):
        """Create an MCP server with the standard LibP2P controller."""
        try:
            from ipfs_kit_py.mcp.server import MCPServer
            # Create server with mock components
            server = MCPServer(debug_mode=True)
            
            # Replace models with mocks
            server.models = {"libp2p": libp2p_model}
            
            # Initialize controllers
            from ipfs_kit_py.mcp.controllers.libp2p_controller import LibP2PController
            server.controllers = {
                "libp2p": LibP2PController(libp2p_model)
            }
            
            # Create FastAPI app
            server.app = FastAPI(title="MCP Standard Server Test")
            
            # Register routes
            router = server.register_controllers()
            
            # Include the router in the app
            server.app.include_router(router)
            
            return server
        except ImportError as e:
            pytest.skip(f"MCP server not available: {str(e)}")
            return None
    
    @pytest.fixture
    def mcp_anyio_server(self, libp2p_model):
        """Create an MCP server with the AnyIO version of LibP2P controller."""
        try:
            from ipfs_kit_py.mcp.server_anyio import MCPServer as MCPServerAnyIO
            # Create server with mock components
            server = MCPServerAnyIO(debug_mode=True)
            
            # Replace models with mocks
            server.models = {"libp2p": libp2p_model}
            
            # Initialize controllers
            from ipfs_kit_py.mcp.controllers.libp2p_controller_anyio import LibP2PControllerAnyIO
            server.controllers = {
                "libp2p": LibP2PControllerAnyIO(libp2p_model)
            }
            
            # Create FastAPI app
            server.app = FastAPI(title="MCP AnyIO Server Test")
            
            # Register routes
            router = server.register_controllers()
            
            # Include the router in the app
            server.app.include_router(router)
            
            return server
        except ImportError as e:
            pytest.skip(f"AnyIO MCP server not available: {str(e)}")
            return None
    
    @pytest.fixture
    def standard_client(self, mcp_standard_server):
        """Create a test client for the standard MCP server."""
        if mcp_standard_server is None:
            pytest.skip("Standard MCP server not available")
        return TestClient(mcp_standard_server.app)
    
    @pytest.fixture
    def anyio_client(self, mcp_anyio_server):
        """Create a test client for the AnyIO MCP server."""
        if mcp_anyio_server is None:
            pytest.skip("AnyIO MCP server not available")
        return TestClient(mcp_anyio_server.app)
    
    def test_health_check_comparison(self, standard_client, anyio_client):
        """Compare health check responses between standard and AnyIO controllers."""
        # Get responses from both implementations
        standard_response = standard_client.get("/libp2p/health")
        anyio_response = anyio_client.get("/libp2p/health")
        
        # Both should be successful
        assert standard_response.status_code == 200
        assert anyio_response.status_code == 200
        
        # Extract data
        standard_data = standard_response.json()
        anyio_data = anyio_response.json()
        
        # Validate basic fields match
        assert standard_data["success"] == anyio_data["success"]
        assert standard_data["libp2p_available"] == anyio_data["libp2p_available"]
        assert standard_data["peer_initialized"] == anyio_data["peer_initialized"]
        assert standard_data["peer_id"] == anyio_data["peer_id"]
        
        # AnyIO might have extra dependency info
        if "dependencies" in anyio_data:
            assert isinstance(anyio_data["dependencies"], dict)
            assert "libp2p_available" in anyio_data["dependencies"]
    
    def test_discover_peers_comparison(self, standard_client, anyio_client):
        """Compare peer discovery between standard and AnyIO controllers."""
        # Create request payload
        payload = {"discovery_method": "all", "limit": 10}
        
        # Get responses from both implementations
        standard_response = standard_client.post("/libp2p/discover", json=payload)
        anyio_response = anyio_client.post("/libp2p/discover", json=payload)
        
        # Both should be successful
        assert standard_response.status_code == 200
        assert anyio_response.status_code == 200
        
        # Extract data
        standard_data = standard_response.json()
        anyio_data = anyio_response.json()
        
        # Validate response fields match
        assert standard_data["success"] == anyio_data["success"]
        assert standard_data["peers"] == anyio_data["peers"]
        assert standard_data["peer_count"] == anyio_data["peer_count"]
    
    def test_dht_find_peer_comparison(self, standard_client, anyio_client):
        """Compare DHT find peer between standard and AnyIO controllers."""
        # Create request payload
        payload = {"peer_id": "12D3KooWPeer1", "timeout": 30}
        
        # Get responses from both implementations
        standard_response = standard_client.post("/libp2p/dht/find_peer", json=payload)
        anyio_response = anyio_client.post("/libp2p/dht/find_peer", json=payload)
        
        # Both should be successful
        assert standard_response.status_code == 200
        assert anyio_response.status_code == 200
        
        # Extract data
        standard_data = standard_response.json()
        anyio_data = anyio_response.json()
        
        # Validate response fields match
        assert standard_data["success"] == anyio_data["success"]
        assert standard_data["peer_id"] == anyio_data["peer_id"]
        assert standard_data["addresses"] == anyio_data["addresses"]
    
    def test_unavailable_comparison(self, standard_client, anyio_client, libp2p_model):
        """Compare error handling when LibP2P is not available."""
        # Configure model to simulate LibP2P being unavailable
        libp2p_model.is_available.return_value = False
        libp2p_model.get_health.return_value = {
            "success": False,
            "libp2p_available": False,
            "peer_initialized": False,
            "error": "libp2p is not available",
            "error_type": "dependency_missing"
        }
        
        # Test health endpoint for both implementations
        standard_health = standard_client.get("/libp2p/health")
        anyio_health = anyio_client.get("/libp2p/health")
        
        # Both should return 200 for health check but with failure status
        assert standard_health.status_code == 200
        assert anyio_health.status_code == 200
        assert not standard_health.json()["success"]
        assert not anyio_health.json()["success"]
        
        # Test functional endpoint for both implementations
        standard_peers = standard_client.get("/libp2p/peers")
        anyio_peers = anyio_client.get("/libp2p/peers")
        
        # Both should return 503 Service Unavailable
        assert standard_peers.status_code == 503
        assert anyio_peers.status_code == 503
        assert "not available" in standard_peers.json()["detail"]
        assert "not available" in anyio_peers.json()["detail"]
    
    @pytest.mark.parametrize("endpoint", [
        "/libp2p/health",
        "/libp2p/stats",
        "/libp2p/pubsub/topics",
        "/libp2p/handlers/list",
    ])
    def test_get_endpoints_comparison(self, standard_client, anyio_client, endpoint):
        """Compare GET endpoints between standard and AnyIO controllers."""
        # Get responses from both implementations
        standard_response = standard_client.get(endpoint)
        anyio_response = anyio_client.get(endpoint)
        
        # Both should have the same status code
        assert standard_response.status_code == anyio_response.status_code
        
        # If successful, check that the structure is the same
        if standard_response.status_code == 200:
            standard_data = standard_response.json()
            anyio_data = anyio_response.json()
            
            # Both should have success field with the same value
            assert "success" in standard_data
            assert "success" in anyio_data
            assert standard_data["success"] == anyio_data["success"]
    
    @pytest.mark.parametrize("endpoint, payload", [
        ("/libp2p/reset", {}),
        ("/libp2p/start", {}),
        ("/libp2p/stop", {}),
        ("/libp2p/dht/provide", {"cid": "QmTest123"}),
        ("/libp2p/pubsub/publish", {"topic": "test-topic", "message": "Hello, world!"}),
    ])
    def test_post_endpoints_comparison(self, standard_client, anyio_client, endpoint, payload):
        """Compare POST endpoints between standard and AnyIO controllers."""
        # Get responses from both implementations
        standard_response = standard_client.post(endpoint, json=payload)
        anyio_response = anyio_client.post(endpoint, json=payload)
        
        # Both should have the same status code
        assert standard_response.status_code == anyio_response.status_code
        
        # If successful, check that the structure is the same
        if standard_response.status_code == 200:
            standard_data = standard_response.json()
            anyio_data = anyio_response.json()
            
            # Both should have success field with the same value
            assert "success" in standard_data
            assert "success" in anyio_data
            assert standard_data["success"] == anyio_data["success"]