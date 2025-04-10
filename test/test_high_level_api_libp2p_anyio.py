"""Tests for the high-level API libp2p integration with AnyIO support."""

import os
import sys
import time
import pytest
import anyio

from ipfs_kit_py.high_level_api import IPFSSimpleAPI
from ipfs_kit_py.high_level_api.libp2p_integration_anyio import (
    inject_libp2p_into_high_level_api,
    apply_high_level_api_integration
)

# Skip tests if libp2p is not available
try:
    from ipfs_kit_py.libp2p import HAS_LIBP2P
    from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer
except ImportError:
    HAS_LIBP2P = False

# Mark the entire module as requiring libp2p
pytestmark = pytest.mark.skipif(not HAS_LIBP2P, reason="libp2p is not available")


class TestHighLevelAPILibP2PAnyIO:
    """Test the AnyIO version of the high-level API libp2p integration."""

    @pytest.fixture
    def api_instance(self):
        """Create a high-level API instance with libp2p integration."""
        # Create a simple API instance
        api = IPFSSimpleAPI(role="leecher")
        
        # Apply the libp2p integration using the AnyIO version
        inject_libp2p_into_high_level_api(api.__class__)
        
        # Return the instance
        return api

    def test_integration_adds_methods(self, api_instance):
        """Test that the integration adds the required methods to the API."""
        # Check that the methods have been added
        assert hasattr(api_instance, "discover_peers")
        assert hasattr(api_instance, "connect_to_peer")
        assert hasattr(api_instance, "get_connected_peers")
        assert hasattr(api_instance, "request_content_from_peer")
        assert hasattr(api_instance, "get_libp2p_peer_id")

    def test_get_libp2p_peer_id(self, api_instance):
        """Test the get_libp2p_peer_id method."""
        # With proper mocking, we'd need to mock the libp2p_peer instance
        # Here we'll just verify the method doesn't throw an error
        result = api_instance.get_libp2p_peer_id()
        
        # Since we may not have a real libp2p peer, we'll just check the structure
        assert "success" in result
        assert "operation" in result
        assert "timestamp" in result
        assert result["operation"] == "get_libp2p_peer_id"

    def test_discover_peers_structure(self, api_instance):
        """Test the structure of the discover_peers method."""
        # With proper mocking, we'd need to mock libp2p discovery
        # Here we'll just verify the method handles errors gracefully
        result = api_instance.discover_peers(timeout=1)  # Short timeout to avoid long waits
        
        # Check the basic structure
        assert "success" in result
        assert "operation" in result
        assert "timestamp" in result
        assert "peers" in result
        assert isinstance(result["peers"], list)
        assert result["operation"] == "discover_peers"

    @pytest.mark.asyncio
    async def test_request_content_anyio_timeout(self, api_instance):
        """Test that the request_content_from_peer method handles timeouts properly with AnyIO."""
        # This test will verify the AnyIO timeout functionality
        # We'll request a non-existent CID with a very short timeout
        result = api_instance.request_content_from_peer(
            peer_id="QmNonExistentPeer",
            cid="QmNonExistentCID",
            timeout=0.1  # Very short timeout
        )
        
        # Check that the operation failed gracefully
        assert "success" in result
        assert result["success"] is False
        assert "error" in result
        # The error message should contain "timeout" or "timed out"
        assert ("timeout" in result["error"].lower() or 
                "timed out" in result["error"].lower())

    @pytest.mark.anyio
    async def test_anyio_vs_asyncio_behavior(self):
        """Test that the AnyIO integration works with both asyncio and trio backends."""
        # Create a simple API instance
        api = IPFSSimpleAPI(role="leecher")
        
        # Apply the libp2p integration using the AnyIO version
        inject_libp2p_into_high_level_api(api.__class__)
        
        # Test running with the current anyio backend
        async def test_discovery():
            # Call discover peers, which uses AnyIO internally
            result = api.discover_peers(timeout=1)  # Short timeout
            assert "success" in result
            assert "operation" in result
            assert result["operation"] == "discover_peers"
            return result
        
        # Run the test
        result = await test_discovery()
        assert result["operation"] == "discover_peers"


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])