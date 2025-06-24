"""
Test the integration of the LibP2PController with the MCP server using our TestLibP2PModel.

This test demonstrates how the TestLibP2PModel mock implementation can be used
to test the full MCP server stack without requiring actual libp2p dependencies.
It focuses on verifying that the controller correctly handles the mock model's responses
when integrated with the full MCP server.
"""

import os
import time
import json
import logging
import pytest
import uuid
from unittest.mock import MagicMock, patch

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import TestLibP2PModel from our integration test file
from test.test_mcp_libp2p_integration import TestLibP2PModel, HAS_LIBP2P

# Import server and controller
try:
    from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import
except ImportError:
    pytest.skip("MCPServer not available", allow_module_level=True)

try:
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    pytest.skip("FastAPI TestClient not available", allow_module_level=True)

# Skip all tests if FastAPI is not available
pytestmark = pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI TestClient not installed")


class TestMCPLibP2PServerIntegration:
    """Test the integration of LibP2PController with the MCP server."""

    @pytest.fixture
    def test_libp2p_model(self):
        """Create a TestLibP2PModel instance for testing."""
        from ipfs_kit_py.mcp.persistence.cache_manager import MCPCacheManager

        # Create a cache manager for the model
        cache_manager = MCPCacheManager(
            base_path="/tmp/test_libp2p_cache",
            debug_mode=True
        )

        # Create the model with proper dependencies
        model = TestLibP2PModel(
            cache_manager=cache_manager,
            resources={"max_memory": 100 * 1024 * 1024},
            metadata={"role": "worker"}
        )

        # Pre-populate model's content store with some test content
        model.content_store = {
            "QmTestCID1": b'{"test": "content1"}',
            "QmTestCID2": b'{"test": "content2"}'
        }

        # Set up attributes for get_health and other methods
        model.peer_id = "12D3KooWTestPeerID1234"
        model.addresses = ["/ip4/127.0.0.1/tcp/4001", "/ip4/192.168.1.1/tcp/4001"]
        model.protocols = ["/ipfs/kad/1.0.0", "/ipfs/ping/1.0.0"]

        # Force libp2p availability to True for tests by default
        # Individual tests can modify this as needed
        model.has_libp2p = True

        return model

    @pytest.fixture
    def mcp_server(self, test_libp2p_model):
        """
        Create an MCP server instance with our test LibP2P model.

        This fixture patches the LibP2PModel class in the server's models dictionary
        to use our TestLibP2PModel implementation instead.
        """
        # Create the MCP server with debug mode and isolation
        server = MCPServer(
            debug_mode=True,
            isolation_mode=True,
            persistence_path="/tmp/test_mcp_server"
        )

        # Verify libp2p controller exists
        if "libp2p" not in server.controllers:
            # If it's not registered, we need to add it manually
            # First register the model
            server.models["libp2p"] = test_libp2p_model

            # Then try to import and create the controller
            try:
                from ipfs_kit_py.mcp.controllers.libp2p_controller import LibP2PController
                server.controllers["libp2p"] = LibP2PController(test_libp2p_model)
            except ImportError as e:
                pytest.skip(f"LibP2PController not available: {e}")
        else:
            # Replace the LibP2P model with our test model
            server.models["libp2p"] = test_libp2p_model

            # Update the controller's model reference to use our test model
            server.controllers["libp2p"].libp2p_model = test_libp2p_model

        return server

    @pytest.fixture
    def client(self, mcp_server):
        """Create a FastAPI test client for the MCP server."""
        # Create a FastAPI app for the test
        from fastapi import FastAPI
        app = FastAPI()

        # Register the MCP server with the app
        mcp_server.register_with_app(app, prefix="")

        return TestClient(app)

    def test_server_status(self, client):
        """Test the MCP server status endpoint with our test model."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "controllers" in data
        assert "libp2p" in data["controllers"]
        assert data["controllers"]["libp2p"] is True

    def test_libp2p_health_endpoint(self, client, test_libp2p_model):
        """Test the LibP2P health endpoint."""
        # Simulate different behavior based on whether real libp2p is available
        if not HAS_LIBP2P:
            # When using our mock and libp2p is not available, health should return 503
            test_libp2p_model.has_libp2p = False
            response = client.get("/libp2p/health")
            assert response.status_code == 503
            data = response.json()
            assert "detail" in data
            assert "libp2p service unavailable" in data["detail"]
        else:
            # When using our mock but reporting libp2p as available, health should return 200
            test_libp2p_model.has_libp2p = True
            response = client.get("/libp2p/health")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["libp2p_available"] is True
            assert data["peer_id"] == test_libp2p_model.peer_id

    def test_discover_peers_endpoint(self, client, test_libp2p_model):
        """Test the peers discovery endpoint."""
        # Setup discover_peers method to return some test peers
        test_peers = [
            {"id": "peer1", "address": "/ip4/127.0.0.1/tcp/4001", "source": "dht"},
            {"id": "peer2", "address": "/ip4/192.168.1.1/tcp/4001", "source": "mdns"}
        ]
        test_libp2p_model.peer_discovery_result = {
            "success": True,
            "peers": test_peers,
            "peer_count": len(test_peers)
        }

        # Test endpoints only if libp2p availability is reported
        if not HAS_LIBP2P:
            # Skip this test when libp2p isn't available - our mock will return 503
            return

        # Test the peers endpoint
        response = client.get("/libp2p/peers")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "peers" in data
        assert len(data["peers"]) == len(test_peers)

        # Test the discover endpoint
        response = client.post("/libp2p/discover", json={"discovery_method": "all", "limit": 10})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "peers" in data
        assert len(data["peers"]) == len(test_peers)

    def test_content_operations(self, client, test_libp2p_model):
        """Test content-related endpoints."""
        # Skip this test when libp2p isn't available - our mock will return 503
        if not HAS_LIBP2P:
            return

        # Test getting content information
        response = client.get("/libp2p/content/info/QmTestCID1")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cid"] == "QmTestCID1"

        # Test retrieving content data
        response = client.get("/libp2p/content/QmTestCID1")
        assert response.status_code == 200
        assert response.content == b'{"test": "content1"}'

        # Test announcing content
        test_content = b'{"test": "new content"}'
        response = client.post("/libp2p/announce", json={
            "cid": "QmNewTestCID",
            "data": test_content.decode()  # Convert bytes to string for JSON
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cid"] == "QmNewTestCID"

        # Verify the content was stored in the mock model
        assert "QmNewTestCID" in test_libp2p_model.content_store

    def test_find_providers(self, client, test_libp2p_model):
        """Test the find providers endpoint."""
        # Skip this test when libp2p isn't available - our mock will return 503
        if not HAS_LIBP2P:
            return

        # Setup test providers
        test_providers = [
            "/ip4/192.168.1.1/tcp/4001/p2p/QmProvider1",
            "/ip4/192.168.1.2/tcp/4001/p2p/QmProvider2"
        ]
        test_libp2p_model.providers_result = {
            "success": True,
            "cid": "QmTestCID1",
            "providers": test_providers,
            "provider_count": len(test_providers)
        }

        # Test the providers endpoint
        response = client.get("/libp2p/providers/QmTestCID1")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cid"] == "QmTestCID1"
        assert "providers" in data
        assert len(data["providers"]) == len(test_providers)

    def test_connect_peer(self, client, test_libp2p_model):
        """Test the connect peer endpoint."""
        # Skip this test when libp2p isn't available - our mock will return 503
        if not HAS_LIBP2P:
            return

        # Test connecting to a peer
        test_peer_addr = "/ip4/192.168.1.3/tcp/4001/p2p/QmTestPeer"
        test_libp2p_model.connect_result = {
            "success": True,
            "peer_addr": test_peer_addr
        }

        response = client.post("/libp2p/connect", json={"peer_addr": test_peer_addr})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["peer_addr"] == test_peer_addr

    def test_error_handling(self, client, test_libp2p_model):
        """Test error handling in the MCP server."""
        # Skip this test when libp2p isn't available - our mock will return 503
        if not HAS_LIBP2P:
            return

        # Configure model to return an error for get_content
        test_libp2p_model.error_mode = True
        test_libp2p_model.error_type = "content_not_found"
        test_libp2p_model.error_message = "Content not found"

        # Test content retrieval with error
        response = client.get("/libp2p/content/QmNonExistentCID")

        # For content not found, we expect a 404 response
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "Content not found" in data["detail"]

        # Configure model to return a different error
        test_libp2p_model.error_type = "generic_error"
        test_libp2p_model.error_message = "Some other error"

        # Test again with a different error type
        response = client.get("/libp2p/content/QmNonExistentCID")

        # For other errors, we expect a 500 response
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Some other error" in data["detail"]

    def test_dependency_handling(self, client, test_libp2p_model):
        """Test handling of missing libp2p dependencies."""
        # Test with HAS_LIBP2P = False
        with patch('test.test_mcp_libp2p_integration.HAS_LIBP2P', False):
            # Force our model to report not available
            test_libp2p_model.has_libp2p = False

            # Health check should return service unavailable
            response = client.get("/libp2p/health")
            assert response.status_code == 503

            # Content operations should also fail
            response = client.get("/libp2p/content/QmTestCID1")
            assert response.status_code == 503

            # Peers discovery should fail
            response = client.get("/libp2p/peers")
            assert response.status_code == 503

        # Test with HAS_LIBP2P = True but libp2p_peer = None
        with patch('test.test_mcp_libp2p_integration.HAS_LIBP2P', True):
            # Set our model to report available but have no peer
            test_libp2p_model.has_libp2p = True
            test_libp2p_model.libp2p_peer = None

            # Health check should have specific error
            response = client.get("/libp2p/health")
            assert response.status_code == 503
            data = response.json()
            assert "detail" in data
            assert "libp2p service unavailable" in data["detail"]


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
