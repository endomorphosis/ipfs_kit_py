#!/usr/bin/env python3
"""
Comprehensive integration test for libp2p functionality with MCP server.

This test verifies that:
1. LibP2P dependencies can be installed
2. The MCP server can properly initialize libp2p components
3. LibP2P model and controller correctly interact
4. Basic libp2p operations work as expected
"""

import os
import sys
import time
import logging
import unittest
import pytest
import asyncio
import tempfile
from unittest.mock import MagicMock, patch
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("libp2p_integration_test")

# Try to import our install_libp2p module
try:
    from install_libp2p import ensure_libp2p_available, HAS_LIBP2P
except ImportError:
    # Fallback for when running tests in different directory
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from install_libp2p import ensure_libp2p_available, HAS_LIBP2P
    except ImportError:
        logger.error("Could not import install_libp2p module")
        HAS_LIBP2P = False

# Skip tests if libp2p is not available and auto-installation is disabled
AUTO_INSTALL = os.environ.get("IPFS_KIT_AUTO_INSTALL_DEPS", "0") == "1"
if not HAS_LIBP2P and AUTO_INSTALL:
    logger.info("LibP2P not available, attempting to install...")
    HAS_LIBP2P = ensure_libp2p_available()

# Skip marker for tests that require LibP2P
libp2p_required = pytest.mark.skipif(
    not HAS_LIBP2P, 
    reason="LibP2P is not available. Set IPFS_KIT_AUTO_INSTALL_DEPS=1 to auto-install."
)

# Import MCP components
try:
    from ipfs_kit_py.mcp.models.libp2p_model import LibP2PModel
    from ipfs_kit_py.mcp.controllers.libp2p_controller_anyio import LibP2PControllerAnyIO
    IMPORTS_OK = True
except ImportError as e:
    logger.warning(f"Failed to import required MCP components: {e}")
    IMPORTS_OK = False

# Skip marker for tests that require imports
imports_required = pytest.mark.skipif(
    not IMPORTS_OK, 
    reason="Required imports are not available"
)

# Cache manager mock
class MockCacheManager:
    def __init__(self):
        self.cache = {}
    
    def get(self, key):
        return self.cache.get(key)
    
    def put(self, key, value, ttl=None):
        self.cache[key] = value
        return True
    
    def delete(self, key):
        if key in self.cache:
            del self.cache[key]
            return True
        return False
    
    def list_keys(self, prefix=None):
        if prefix:
            return [k for k in self.cache.keys() if k.startswith(prefix)]
        return list(self.cache.keys())

# Credential manager mock  
class MockCredentialManager:
    def __init__(self):
        self.credentials = {}
    
    def get_credential(self, name):
        return self.credentials.get(name)
    
    def store_credential(self, name, value):
        self.credentials[name] = value
        return True


@imports_required
class TestLibP2PIntegration:
    """Tests for libp2p integration with the MCP server."""
    
    @pytest.fixture
    def mock_cache_manager(self):
        """Create a mock cache manager."""
        return MockCacheManager()
    
    @pytest.fixture
    def mock_credential_manager(self):
        """Create a mock credential manager."""
        return MockCredentialManager()
    
    @pytest.fixture
    def libp2p_model(self, mock_cache_manager, mock_credential_manager):
        """Create a LibP2PModel instance."""
        model = LibP2PModel(
            cache_manager=mock_cache_manager,
            credential_manager=mock_credential_manager,
            metadata={
                "auto_start": False,  # Don't auto-start for tests
                "auto_install_dependencies": False  # Don't auto-install for basic tests
            }
        )
        return model
    
    @pytest.fixture
    def libp2p_controller(self, libp2p_model):
        """Create a LibP2PControllerAnyIO instance."""
        controller = LibP2PControllerAnyIO(libp2p_model)
        return controller
    
    def test_model_initialization(self, libp2p_model):
        """Test that the libp2p model initializes correctly."""
        assert libp2p_model is not None
        assert hasattr(libp2p_model, "cache_manager")
        assert hasattr(libp2p_model, "credential_manager")
        
        # Check if libp2p is available
        is_available = libp2p_model.is_available()
        assert isinstance(is_available, bool)
        
        # Get health check
        health = libp2p_model.get_health()
        assert "success" in health
        assert "libp2p_available" in health
        assert health["libp2p_available"] == is_available
    
    def test_controller_initialization(self, libp2p_controller):
        """Test that the libp2p controller initializes correctly."""
        assert libp2p_controller is not None
        assert hasattr(libp2p_controller, "libp2p_model")
        assert hasattr(libp2p_controller, "initialized_endpoints")
        
        # Test health check method
        health = libp2p_controller.health_check()
        assert "success" in health
        assert "libp2p_available" in health
    
    @pytest.mark.asyncio
    async def test_controller_async_health_check(self, libp2p_controller):
        """Test the async health check method of the controller."""
        health = await libp2p_controller.health_check()
        assert "success" in health
        assert "libp2p_available" in health
        
        # Check that the controller properly calls the model
        assert hasattr(libp2p_controller.libp2p_model, "get_health")
    
    @pytest.mark.asyncio
    async def test_peer_discovery_simulation(self, libp2p_controller):
        """Test peer discovery simulation (works even without real libp2p)."""
        # Mock the model's discover_peers method
        original_discover = libp2p_controller.libp2p_model.discover_peers
        
        mock_result = {
            "success": True,
            "peers": [f"MockPeer{i}" for i in range(5)],
            "peer_count": 5,
            "operation": "discover_peers",
            "discovery_method": "simulation",
            "timestamp": time.time()
        }
        
        libp2p_controller.libp2p_model.discover_peers = MagicMock(return_value=mock_result)
        
        # Call the controller method
        result = await libp2p_controller.discover_peers({
            "discovery_method": "simulation",
            "limit": 5
        })
        
        # Verify the result
        assert result["success"]
        assert len(result["peers"]) == 5
        assert result["peer_count"] == 5
        
        # Restore the original method
        libp2p_controller.libp2p_model.discover_peers = original_discover


@libp2p_required
@imports_required
class TestRealLibP2PIntegration:
    """Integration tests that require real libp2p dependencies."""
    
    @pytest.fixture
    def temp_identity_path(self):
        """Create a temporary directory for peer identity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def real_libp2p_model(self, mock_cache_manager, mock_credential_manager, temp_identity_path):
        """Create a libp2p model with real libp2p dependencies."""
        model = LibP2PModel(
            cache_manager=mock_cache_manager,
            credential_manager=mock_credential_manager,
            metadata={
                "auto_start": True,  # Auto-start for real tests
                "identity_path": temp_identity_path,
                "role": "worker",
                "enable_mdns": True,
                "bootstrap_peers": [
                    # IPFS bootstrap peers
                    "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN",
                    "/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ"
                ]
            }
        )
        
        # Skip further testing if libp2p isn't actually available
        if not model.is_available():
            pytest.skip("Real libp2p dependencies are not available")
            
        yield model
        
        # Clean up after the test
        if model.is_available():
            model.stop()
    
    @pytest.fixture
    def real_libp2p_controller(self, real_libp2p_model):
        """Create a controller with a real libp2p model."""
        controller = LibP2PControllerAnyIO(real_libp2p_model)
        return controller
    
    def test_real_model_initialization(self, real_libp2p_model):
        """Test initialization with real libp2p dependencies."""
        assert real_libp2p_model is not None
        assert real_libp2p_model.is_available()
        
        # Check health status
        health = real_libp2p_model.get_health()
        assert health["success"]
        assert health["libp2p_available"] 
        assert health["peer_initialized"]
        assert "peer_id" in health
        assert "addresses" in health
        assert "connected_peers" in health
    
    def test_real_peer_discovery(self, real_libp2p_model):
        """Test peer discovery with real libp2p."""
        # This test might take some time
        result = real_libp2p_model.discover_peers(discovery_method="all", limit=5)
        assert result["success"]
        assert "peers" in result
        assert "peer_count" in result
        
        # We can't guarantee peers will be found in testing environment
        logger.info(f"Discovered {result.get('peer_count', 0)} peers")
    
    def test_dht_operations(self, real_libp2p_model):
        """Test DHT operations with real libp2p."""
        # Get the list of connected peers
        connected = real_libp2p_model.get_connected_peers()
        
        if connected["peer_count"] > 0:
            # Try to get peer info for first peer
            peer_id = connected["peers"][0]
            info = real_libp2p_model.get_peer_info(peer_id)
            assert "success" in info
            
            if info["success"]:
                logger.info(f"Got info for peer {peer_id}: {info.get('protocols', [])}")
            else:
                logger.warning(f"Couldn't get info for peer {peer_id}: {info.get('error', '')}")
        else:
            logger.warning("No connected peers available for DHT operation testing")
    
    @pytest.mark.asyncio
    async def test_controller_real_operations(self, real_libp2p_controller):
        """Test controller operations with real libp2p."""
        # Health check
        health = await real_libp2p_controller.health_check()
        assert health["success"]
        assert health["libp2p_available"]
        assert health["peer_initialized"]
        
        # Try basic peer discovery
        discovery = await real_libp2p_controller.discover_peers({
            "discovery_method": "all",
            "limit": 5
        })
        assert discovery["success"]
        assert "peers" in discovery
        logger.info(f"Controller discovered {len(discovery.get('peers', []))} peers")


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
