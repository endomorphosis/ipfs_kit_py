"""
Integration test for libp2p with the MCP server.

This module tests the integration between libp2p functionality and the MCP server,
verifying that content routing works as expected and that the API endpoints
properly expose libp2p functionality.
"""

import importlib.util
import logging
import os
import tempfile
from unittest.mock import MagicMock

import pytest

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("libp2p_mcp_integration_test")

# Check if dependencies are available without importing everything


HAS_LIBP2P = importlib.util.find_spec("libp2p") is not None
if HAS_LIBP2P:
    from ipfs_kit_py.libp2p import HAS_LIBP2P  # Re-import to confirm
    from ipfs_kit_py.libp2p.enhanced_content_routing import (
        apply_to_peer,
    )  # Import only what's needed
    from ipfs_kit_py.mcp.controllers.libp2p_controller import LibP2PController
    from ipfs_kit_py.mcp.controllers.libp2p_controller_anyio import LibP2PControllerAnyIO
    from ipfs_kit_py.mcp.models.libp2p_model import LibP2PModel
else:
    # Define stubs if libp2p is not available
    class LibP2PModel:
        pass

    class LibP2PController:
        pass

    class LibP2PControllerAnyIO:
        pass

    def apply_to_peer(*args, **kwargs):
        pass

    logger.warning("libp2p dependencies not found. Skipping related tests.")


# Skip tests if libp2p is not available
libp2p_not_available = not HAS_LIBP2P
skip_if_no_libp2p = pytest.mark.skipif(libp2p_not_available, reason="libp2p is not available")


# Create a cache manager mock for tests
class MockCacheManager:
    def __init__(self):
        self.cache = {}

    def get(self, key):
        return self.cache.get(key)

    def put(self, key, value, ttl = None):
        self.cache[key] = value

    def delete(self, key):
        if key in self.cache:
            del self.cache[key]

    def list_keys(self):
        return list(self.cache.keys())


# Create fixtures for testing
@pytest.fixture
def temp_identity_path():
    """Fixture to provide a temporary identity file path."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        yield tmp.name
    # Clean up
    try:
        os.unlink(tmp.name)
    except Exception:
        pass


@pytest.fixture
def mock_cache_manager():
    """Fixture to provide a mock cache manager."""
    return MockCacheManager()


@pytest.fixture
def libp2p_model(temp_identity_path, mock_cache_manager):
    """Fixture to create a LibP2PModel instance."""
    if not HAS_LIBP2P:
        # Return a mock model if libp2p is not available
        mock_model = MagicMock(spec=LibP2PModel)
        mock_model.is_available.return_value = False
        return mock_model

    # Create a real model if libp2p is available
    metadata = {
        "auto_start": False,  # Don't start automatically
        "identity_path": temp_identity_path,
        "role": "leecher",
        "enable_mdns": False,  # Disable mDNS for tests
        "enable_hole_punching": False,  # Disable NAT traversal for tests
        "bootstrap_peers": [,
            "/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ"
        ],
    }

    model = LibP2PModel(cache_manager=mock_cache_manager, metadata=metadata)

    # Always return the model
    return model


@pytest.fixture
def libp2p_controller(libp2p_model):
    """Fixture to create a LibP2PController instance."""
    return LibP2PController(libp2p_model)


@pytest.fixture
def libp2p_controller_anyio(libp2p_model):
    """Fixture to create a LibP2PControllerAnyIO instance."""
    return LibP2PControllerAnyIO(libp2p_model)


@pytest.fixture
def mock_fastapi_router():
    """Fixture to provide a mock FastAPI router."""

    class MockRouter:
        def __init___v2(self):
            self.routes = []

        def add_api_route(self, path, endpoint, **kwargs):
            self.routes.append({"path": path, "endpoint": endpoint, "kwargs": kwargs})

    return MockRouter()


# Define tests
@skip_if_no_libp2p
class TestLibP2PIntegration:
    """Test suite for libp2p integration with MCP server."""

    def test_model_initialization(self, libp2p_model):
        """Test that the LibP2PModel initializes correctly."""
        assert libp2p_model is not None
        assert libp2p_model.is_available()

    def test_get_health(self, libp2p_model):
        """Test the get_health method of LibP2PModel."""
        # Start the peer
        result = libp2p_model.start()
        assert result["success"]

        # Get health information
        health = libp2p_model.get_health()
        assert health["success"]
        assert health["peer_available"]  # Changed from libp2p_available
        assert health["peer_initialized"]
        assert "peer_id" in health

        # Stop the peer to clean up
        libp2p_model.stop()

    def test_controller_endpoint_registration(self, libp2p_controller, mock_fastapi_router):
        """Test registering endpoints with the API router."""
        # Register routes
        libp2p_controller.register_routes(mock_fastapi_router)

        # Check that routes were registered
        assert len(mock_fastapi_router.routes) > 0

        # Check for important routes
        paths = [route["path"] for route in mock_fastapi_router.routes]
        assert "/libp2p/health" in paths
        assert "/libp2p/discover" in paths
        assert "/libp2p/peers" in paths
        assert "/libp2p/connect" in paths
        assert "/libp2p/providers/{cid}" in paths

    def test_anyio_controller_endpoint_registration(
        self, libp2p_controller_anyio, mock_fastapi_router
    ):
        """Test registering endpoints with the API router using AnyIO controller."""
        # Register routes
        libp2p_controller_anyio.register_routes(mock_fastapi_router)

        # Check that routes were registered
        assert len(mock_fastapi_router.routes) > 0

        # Check for important routes
        paths = [route["path"] for route in mock_fastapi_router.routes]
        assert "/libp2p/health" in paths
        assert "/libp2p/discover" in paths
        assert "/libp2p/peers" in paths
        assert "/libp2p/connect" in paths
        assert "/libp2p/providers/{cid}" in paths

    def test_enhanced_content_router_integration(self, libp2p_model):
        """Test integration with the enhanced content router."""
        # Start the peer
        result = libp2p_model.start()
        assert result["success"]

        try:
            # Apply enhanced content router
            router = apply_to_peer(libp2p_model.libp2p_peer, role=libp2p_model.libp2p_peer.role)
            assert router is not None

            # Check that the content router was attached
            assert hasattr(libp2p_model.libp2p_peer, "content_router")
            assert libp2p_model.libp2p_peer.content_router is not None

            # Check router functionality
            stats = router.get_stats()
            assert isinstance(stats, dict)
        finally:
            # Stop the peer to clean up
            libp2p_model.stop()

    def test_discover_peers(self, libp2p_model):
        """Test discovering peers."""
        # Start the peer
        result = libp2p_model.start()
        assert result["success"]

        try:
            # Discover peers
            result = libp2p_model.discover_peers(discovery_method="dht", limit=5)
            assert result["success"]
        finally:
            # Stop the peer to clean up
            libp2p_model.stop()

    @pytest.mark.asyncio
    async def test_async_health_check(self, libp2p_controller_anyio):
        """Test the async health check endpoint."""

        # Add a response class for the test
        class Response:
            # DISABLED REDEFINITION
            self.content = content
            self.status_code = status_code
            self.media_type = media_type

        # Call the async health check endpoint
        response = await libp2p_controller_anyio.health_check_async()
        assert response is not None

        # If libp2p is available, check response content
        if HAS_LIBP2P and libp2p_controller_anyio.libp2p_model.is_available():
            assert getattr(response, "success", False)


# Run tests if module is executed directly
if __name__ == "__main__":
    # Run the tests with pytest
    pytest.main(["-xvs", __file__])
