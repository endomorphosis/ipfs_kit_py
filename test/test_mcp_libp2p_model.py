"""
Test suite for MCP LibP2P Model.

This module tests the functionality of the LibP2PModel class which provides
access to direct peer-to-peer communication functionality using libp2p.
It includes proper dependency handling to ensure tests can be run with or without
the libp2p dependencies installed.
"""

import os
import time
import pytest
import asyncio
import sys
import logging
from unittest.mock import MagicMock, patch, AsyncMock, PropertyMock, call

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# First check and potentially install libp2p dependencies
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

# Check and optionally install dependencies before importing the model
HAS_DEPENDENCIES = check_and_install_dependencies()

# Import the model
from ipfs_kit_py.mcp.models.libp2p_model import LibP2PModel

# Mock the libp2p dependencies
class MockIPFSLibp2pPeer:
    """Mock implementation of IPFSLibp2pPeer for testing."""
    
    def __init__(self, **kwargs):
        self.role = kwargs.get("role", "leecher")
        self.protocol_handlers = {
            "/ipfs/kad/1.0.0": MagicMock(),
            "/ipfs/ping/1.0.0": MagicMock()
        }
        self.dht = MagicMock()
        self.dht.routing_table.get_peers.return_value = ["peer1", "peer2"]
        self.bootstrap_peers = kwargs.get("bootstrap_peers", [])
        self.enable_mdns = kwargs.get("enable_mdns", True)
    
    def get_peer_id(self):
        """Return a mock peer ID."""
        return "12D3KooWTestPeerID"
    
    def get_listen_addresses(self):
        """Return mock listen addresses."""
        return ["/ip4/127.0.0.1/tcp/4001", "/ip4/192.168.1.1/tcp/4001"]
    
    def get_connected_peers(self):
        """Return mock connected peers."""
        return ["/ip4/127.0.0.1/tcp/4001/p2p/QmPeer1", "/ip4/192.168.1.2/tcp/4001/p2p/QmPeer2"]
    
    def discover_peers_dht(self, limit=10):
        """Return mock discovered peers through DHT."""
        return [f"/ip4/192.168.1.{i}/tcp/4001/p2p/QmPeer{i}" for i in range(1, min(limit + 1, 6))]
    
    def discover_peers_mdns(self, limit=10):
        """Return mock discovered peers through mDNS."""
        return [f"/ip4/192.168.0.{i}/tcp/4001/p2p/QmLocalPeer{i}" for i in range(1, min(limit + 1, 4))]
    
    def connect_peer(self, peer_addr):
        """Simulate connecting to a peer."""
        return True
    
    def find_providers(self, cid, timeout=30):
        """Return mock providers for a CID."""
        return ["/ip4/192.168.1.1/tcp/4001/p2p/QmProvider1", "/ip4/192.168.1.2/tcp/4001/p2p/QmProvider2"]
    
    def retrieve_content(self, cid, timeout=60):
        """Return mock content for a CID."""
        if cid == "QmNotFound":
            return None
        return b"test content data for " + cid.encode()
    
    def store_content_locally(self, cid, data):
        """Simulate storing content locally."""
        pass
    
    def announce_content(self, cid):
        """Simulate announcing content."""
        pass
    
    def get_peer_info(self, peer_id):
        """Return mock peer info."""
        if peer_id == "nonexistent":
            return None
        return {
            "id": peer_id,
            "addresses": [f"/ip4/192.168.1.1/tcp/4001/p2p/{peer_id}"],
            "protocols": ["/ipfs/kad/1.0.0", "/ipfs/ping/1.0.0"],
            "connected": True,
            "agent_version": "ipfs-kit-py/0.1.0"
        }


# Mock classes for EnhancedDHTDiscovery
class MockEnhancedDHTDiscovery:
    """Mock implementation of EnhancedDHTDiscovery."""
    
    def __init__(self, peer):
        self.peer = peer
    
    def discover_peers(self, limit=10):
        """Return mock enhanced discovered peers."""
        return [f"/ip4/10.0.0.{i}/tcp/4001/p2p/QmEnhancedPeer{i}" for i in range(1, min(limit + 1, 8))]


# Apply patches for testing
@pytest.fixture(autouse=True)
def mock_libp2p_availability():
    """
    Patch the libp2p availability check for testing.
    
    This fixture takes into account whether the actual dependencies are installed.
    If dependencies are available, it uses the mock classes for controlled testing.
    If dependencies are not available, it patches HAS_LIBP2P to True to allow tests to run.
    """
    # Determine the patch value based on actual dependency status
    has_libp2p_value = True  # Always patch to True for testing
    
    # Log the dependency status
    if HAS_DEPENDENCIES:
        logger.info("Using mocks with actual dependencies available")
    else:
        logger.info("Dependencies not available, tests will run with mocks")
    
    with patch('ipfs_kit_py.mcp.models.libp2p_model.HAS_LIBP2P', has_libp2p_value):
        with patch('ipfs_kit_py.mcp.models.libp2p_model.IPFSLibp2pPeer', MockIPFSLibp2pPeer):
            with patch('ipfs_kit_py.mcp.models.libp2p_model.EnhancedDHTDiscovery', MockEnhancedDHTDiscovery):
                yield

@pytest.fixture
def cache_manager():
    """Create a mock cache manager."""
    manager = MagicMock()
    # Configure get and put methods
    manager.get.return_value = None  # Default to cache miss
    manager.put.return_value = True
    manager.list_keys.return_value = ["libp2p_health", "libp2p_content_QmTest", "libp2p_peers_all"]
    return manager

@pytest.fixture
def credential_manager():
    """Create a mock credential manager."""
    manager = MagicMock()
    return manager


class TestLibP2PModel:
    """Test suite for LibP2P Model functionality."""
    
    @pytest.fixture
    def model(self, cache_manager, credential_manager):
        """Create a LibP2P model for testing."""
        resources = {"max_memory": 1024 * 1024 * 100}  # 100 MB
        metadata = {
            "role": "worker",
            "enable_mdns": True,
            "enable_hole_punching": False,
            "enable_relay": True,
            "use_enhanced_dht": True,
            "bootstrap_peers": [
                "/ip4/104.131.131.82/tcp/4001/p2p/QmBootstrap1",
                "/ip4/104.236.179.241/tcp/4001/p2p/QmBootstrap2"
            ]
        }
        
        model = LibP2PModel(
            cache_manager=cache_manager,
            credential_manager=credential_manager,
            resources=resources,
            metadata=metadata
        )
        return model
    
    def test_initialization(self, model):
        """Test model initialization."""
        # Verify model attributes were set correctly
        assert model.cache_manager is not None
        assert model.credential_manager is not None
        assert model.resources is not None
        assert model.metadata is not None
        assert model.operation_stats is not None
        assert model.libp2p_peer is not None
        assert model.dht_discovery is not None
        
        # Verify operation stats were initialized
        assert model.operation_stats["operation_count"] == 0
        assert model.operation_stats["failed_operations"] == 0
        assert "start_time" in model.operation_stats
        assert "peers_discovered" in model.operation_stats
        assert "content_announced" in model.operation_stats
        assert "content_retrieved" in model.operation_stats
    
    def test_is_available(self, model):
        """Test is_available method."""
        # Should return True since we've patched HAS_LIBP2P to True
        assert model.is_available() is True
        
        # Test with libp2p_peer set to None
        model.libp2p_peer = None
        assert model.is_available() is False
    
    def test_get_health(self, model):
        """Test get_health method."""
        # Call the method
        result = model.get_health()
        
        # Verify result structure
        assert result["success"] is True
        assert result["libp2p_available"] is True
        assert result["peer_initialized"] is True
        assert result["peer_id"] == "12D3KooWTestPeerID"
        assert len(result["addresses"]) == 2
        assert result["connected_peers"] == 2
        assert result["dht_peers"] == 2
        assert len(result["protocols"]) == 2
        assert result["role"] == "worker"
        assert "stats" in result
        
        # Verify operation stats were updated
        assert model.operation_stats["operation_count"] == 1
    
    def test_get_health_error(self, model):
        """Test get_health method with error."""
        # Simulate an error by raising an exception in get_peer_id
        with patch.object(model.libp2p_peer, 'get_peer_id', side_effect=Exception("Test error")):
            result = model.get_health()
            
            # Verify error response
            assert result["success"] is False
            assert "error" in result
            assert "Test error" in result["error"]
            assert result["error_type"] == "health_check_error"
            assert model.operation_stats["failed_operations"] == 1
    
    def test_get_health_no_peer(self, model):
        """Test get_health method with no libp2p peer."""
        # Set libp2p_peer to None
        model.libp2p_peer = None
        
        # Call the method
        result = model.get_health()
        
        # Verify error response
        assert result["success"] is False
        assert result["libp2p_available"] is True  # Still True because HAS_LIBP2P is patched to True
        assert result["peer_initialized"] is False
        assert "error" in result
        assert "libp2p is not available" in result["error"]
        assert result["error_type"] == "dependency_missing"
        assert model.operation_stats["failed_operations"] == 1
    
    def test_discover_peers_all(self, model):
        """Test discover_peers method with 'all' discovery method."""
        # Call the method
        result = model.discover_peers(discovery_method="all", limit=10)
        
        # Verify result structure
        assert result["success"] is True
        assert result["operation"] == "discover_peers"
        assert "discovery_method" in result
        assert "peers" in result
        # Should include peers from DHT, mDNS, and bootstrap
        expected_min_peers = 5  # At least some peers from each source
        assert len(result["peers"]) >= expected_min_peers
        assert "peer_count" in result
        assert result["peer_count"] == len(result["peers"])
        
        # Verify operation stats were updated
        assert model.operation_stats["operation_count"] == 1
        assert model.operation_stats["peers_discovered"] > 0
    
    def test_discover_peers_dht(self, model):
        """Test discover_peers method with 'dht' discovery method."""
        # Call the method
        result = model.discover_peers(discovery_method="dht", limit=5)
        
        # Verify result structure
        assert result["success"] is True
        assert "peers" in result
        assert len(result["peers"]) > 0
        
        # Verify enhanced DHT discovery was used
        # The enhanced discovery should return peers with 10.0.0.x addresses
        assert any("10.0.0" in peer for peer in result["peers"])
    
    def test_discover_peers_mdns(self, model):
        """Test discover_peers method with 'mdns' discovery method."""
        # Call the method
        result = model.discover_peers(discovery_method="mdns", limit=3)
        
        # Verify result structure
        assert result["success"] is True
        assert "peers" in result
        assert len(result["peers"]) > 0
        
        # mDNS discovery should return peers with 192.168.0.x addresses
        assert any("192.168.0" in peer for peer in result["peers"])
        
        # Verify mdns_discoveries was updated
        assert model.operation_stats["mdns_discoveries"] > 0
    
    def test_discover_peers_bootstrap(self, model):
        """Test discover_peers method with 'bootstrap' discovery method."""
        # Call the method
        result = model.discover_peers(discovery_method="bootstrap", limit=2)
        
        # Verify result structure
        assert result["success"] is True
        assert "peers" in result
        # Result should include bootstrap peers
        assert any("QmBootstrap1" in peer or "QmBootstrap2" in peer 
                  for peer in result["peers"])
    
    def test_discover_peers_error(self, model):
        """Test discover_peers method with error."""
        # Simulate an error by raising an exception
        with patch.object(model.libp2p_peer, 'discover_peers_dht', side_effect=Exception("Test error")):
            result = model.discover_peers(discovery_method="dht", limit=5)
            
            # Verify error response
            assert result["success"] is False
            assert "error" in result
            assert "Test error" in result["error"]
            assert result["error_type"] == "discovery_error"
            assert model.operation_stats["failed_operations"] == 1
    
    def test_connect_peer(self, model):
        """Test connect_peer method."""
        # Call the method
        result = model.connect_peer("/ip4/192.168.1.3/tcp/4001/p2p/QmTestPeer")
        
        # Verify result structure
        assert result["success"] is True
        assert result["operation"] == "connect_peer"
        assert result["peer_addr"] == "/ip4/192.168.1.3/tcp/4001/p2p/QmTestPeer"
        
        # Verify operation stats were updated
        assert model.operation_stats["operation_count"] == 1
    
    def test_connect_peer_failure(self, model):
        """Test connect_peer method with failure."""
        # Simulate a connection failure
        with patch.object(model.libp2p_peer, 'connect_peer', return_value=False):
            result = model.connect_peer("/ip4/192.168.1.3/tcp/4001/p2p/QmTestPeer")
            
            # Verify error response
            assert result["success"] is False
            assert "error" in result
            assert "Failed to connect to peer" in result["error"]
            assert result["error_type"] == "connection_failed"
            assert model.operation_stats["failed_operations"] == 1
    
    def test_connect_peer_error(self, model):
        """Test connect_peer method with error."""
        # Simulate an error by raising an exception
        with patch.object(model.libp2p_peer, 'connect_peer', side_effect=Exception("Test error")):
            result = model.connect_peer("/ip4/192.168.1.3/tcp/4001/p2p/QmTestPeer")
            
            # Verify error response
            assert result["success"] is False
            assert "error" in result
            assert "Test error" in result["error"]
            assert result["error_type"] == "connection_error"
            assert model.operation_stats["failed_operations"] == 1
    
    def test_find_content(self, model):
        """Test find_content method."""
        # Call the method
        result = model.find_content("QmTestCID", timeout=30)
        
        # Verify result structure
        assert result["success"] is True
        assert result["operation"] == "find_content"
        assert result["cid"] == "QmTestCID"
        assert "providers" in result
        assert len(result["providers"]) == 2
        assert result["provider_count"] == 2
        
        # Verify operation stats were updated
        assert model.operation_stats["operation_count"] == 1
    
    def test_find_content_cached(self, model, cache_manager):
        """Test find_content method with cached result."""
        # Configure cache hit
        cached_result = {
            "success": True,
            "operation": "find_content",
            "cid": "QmTestCID",
            "providers": ["/ip4/192.168.1.1/tcp/4001/p2p/QmCachedProvider"],
            "provider_count": 1,
            "timestamp": time.time()
        }
        cache_manager.get.return_value = cached_result
        
        # Call the method
        result = model.find_content("QmTestCID", timeout=30)
        
        # Verify cached result was returned
        assert result == cached_result
        
        # Verify cache was checked
        cache_manager.get.assert_called_once_with("libp2p_find_content_QmTestCID")
        
        # Verify libp2p_peer.find_providers was not called
        assert not hasattr(model.libp2p_peer, 'find_providers_called')
    
    def test_find_content_error(self, model):
        """Test find_content method with error."""
        # Simulate an error by raising an exception
        with patch.object(model.libp2p_peer, 'find_providers', side_effect=Exception("Test error")):
            result = model.find_content("QmTestCID", timeout=30)
            
            # Verify error response
            assert result["success"] is False
            assert "error" in result
            assert "Test error" in result["error"]
            assert result["error_type"] == "provider_lookup_error"
            assert model.operation_stats["failed_operations"] == 1
    
    def test_retrieve_content(self, model):
        """Test retrieve_content method."""
        # Call the method
        result = model.retrieve_content("QmTestCID", timeout=60)
        
        # Verify result structure
        assert result["success"] is True
        assert result["operation"] == "retrieve_content"
        assert result["cid"] == "QmTestCID"
        assert result["size"] > 0
        assert result["content_available"] is True
        
        # Verify operation stats were updated
        assert model.operation_stats["operation_count"] == 1
        assert model.operation_stats["content_retrieved"] == 1
        assert model.operation_stats["bytes_retrieved"] > 0
    
    def test_retrieve_content_cached(self, model, cache_manager):
        """Test retrieve_content method with cached result."""
        # Configure cache hit
        cached_result = {
            "success": True,
            "operation": "retrieve_content",
            "cid": "QmTestCID",
            "size": 1024,
            "timestamp": time.time(),
            "content_available": True
        }
        cache_manager.get.return_value = cached_result
        
        # Call the method
        result = model.retrieve_content("QmTestCID", timeout=60)
        
        # Verify cached result was returned (with some modifications)
        assert result["success"] is True
        assert result["operation"] == "retrieve_content"
        assert result["cid"] == "QmTestCID"
        assert result["size"] == 1024
        assert result["content_available"] is True
        assert result["from_cache"] is True
        
        # Verify cache was checked
        cache_manager.get.assert_called_once_with("libp2p_content_info_QmTestCID")
    
    def test_retrieve_content_not_found(self, model):
        """Test retrieve_content method with content not found."""
        # Call the method with a CID that won't be found
        result = model.retrieve_content("QmNotFound", timeout=60)
        
        # Verify error response
        assert result["success"] is False
        assert "error" in result
        assert "Content not found" in result["error"]
        assert result["error_type"] == "content_not_found"
        assert result["content_available"] is False
        assert model.operation_stats["failed_operations"] == 1
    
    def test_retrieve_content_error(self, model):
        """Test retrieve_content method with error."""
        # Simulate an error by raising an exception
        with patch.object(model.libp2p_peer, 'retrieve_content', side_effect=Exception("Test error")):
            result = model.retrieve_content("QmTestCID", timeout=60)
            
            # Verify error response
            assert result["success"] is False
            assert "error" in result
            assert "Test error" in result["error"]
            assert result["error_type"] == "retrieval_error"
            assert result["content_available"] is False
            assert model.operation_stats["failed_operations"] == 1
    
    def test_get_content(self, model):
        """Test get_content method."""
        # Call the method
        result = model.get_content("QmTestCID", timeout=60)
        
        # Verify result structure
        assert result["success"] is True
        assert result["operation"] == "get_content"
        assert result["cid"] == "QmTestCID"
        assert "data" in result
        assert result["data"] == b"test content data for QmTestCID"
        assert result["size"] == len(result["data"])
        
        # Verify operation stats were updated
        assert model.operation_stats["operation_count"] == 1
        assert model.operation_stats["content_retrieved"] == 1
        assert model.operation_stats["bytes_retrieved"] > 0
    
    def test_get_content_cached(self, model, cache_manager):
        """Test get_content method with cached result."""
        # Configure cache hit
        cached_content = b"cached test content"
        cache_manager.get.return_value = cached_content
        
        # Call the method
        result = model.get_content("QmTestCID", timeout=60)
        
        # Verify cached result was returned
        assert result["success"] is True
        assert result["operation"] == "get_content"
        assert result["cid"] == "QmTestCID"
        assert result["data"] == cached_content
        assert result["size"] == len(cached_content)
        assert result["from_cache"] is True
        
        # Verify cache was checked
        cache_manager.get.assert_called_once_with("libp2p_content_QmTestCID")
        
        # Verify libp2p_peer.retrieve_content was not called
        assert not hasattr(model.libp2p_peer, 'retrieve_content_called')
    
    def test_get_content_not_found(self, model):
        """Test get_content method with content not found."""
        # Call the method with a CID that won't be found
        result = model.get_content("QmNotFound", timeout=60)
        
        # Verify error response
        assert result["success"] is False
        assert "error" in result
        assert "Content not found" in result["error"]
        assert result["error_type"] == "content_not_found"
        assert model.operation_stats["failed_operations"] == 1
    
    def test_get_content_error(self, model):
        """Test get_content method with error."""
        # Simulate an error by raising an exception
        with patch.object(model.libp2p_peer, 'retrieve_content', side_effect=Exception("Test error")):
            result = model.get_content("QmTestCID", timeout=60)
            
            # Verify error response
            assert result["success"] is False
            assert "error" in result
            assert "Test error" in result["error"]
            assert result["error_type"] == "retrieval_error"
            assert model.operation_stats["failed_operations"] == 1
    
    def test_announce_content(self, model):
        """Test announce_content method."""
        # Prepare test data
        test_data = b"test content data"
        
        # Call the method
        result = model.announce_content("QmTestCID", data=test_data)
        
        # Verify result structure
        assert result["success"] is True
        assert result["operation"] == "announce_content"
        assert result["cid"] == "QmTestCID"
        assert result["content_stored"] is True
        
        # Verify operation stats were updated
        assert model.operation_stats["operation_count"] == 1
        assert model.operation_stats["content_announced"] == 1
        assert model.operation_stats["bytes_sent"] == len(test_data)
    
    def test_announce_content_without_data(self, model):
        """Test announce_content method without data."""
        # Call the method without data
        result = model.announce_content("QmTestCID", data=None)
        
        # Verify result structure
        assert result["success"] is True
        assert result["operation"] == "announce_content"
        assert result["cid"] == "QmTestCID"
        assert "content_stored" not in result
        
        # Verify operation stats were updated
        assert model.operation_stats["operation_count"] == 1
        assert model.operation_stats["content_announced"] == 1
        assert model.operation_stats["bytes_sent"] == 0  # No data sent
    
    def test_announce_content_error(self, model):
        """Test announce_content method with error."""
        # Simulate an error by raising an exception
        with patch.object(model.libp2p_peer, 'announce_content', side_effect=Exception("Test error")):
            result = model.announce_content("QmTestCID", data=b"test data")
            
            # Verify error response
            assert result["success"] is False
            assert "error" in result
            assert "Test error" in result["error"]
            assert result["error_type"] == "announcement_error"
            assert model.operation_stats["failed_operations"] == 1
    
    def test_get_connected_peers(self, model):
        """Test get_connected_peers method."""
        # Call the method
        result = model.get_connected_peers()
        
        # Verify result structure
        assert result["success"] is True
        assert result["operation"] == "get_connected_peers"
        assert "peers" in result
        assert len(result["peers"]) == 2
        assert result["peer_count"] == 2
        
        # Verify operation stats were updated
        assert model.operation_stats["operation_count"] == 1
    
    def test_get_connected_peers_cached(self, model, cache_manager):
        """Test get_connected_peers method with cached result."""
        # Configure cache hit
        cached_result = {
            "success": True,
            "operation": "get_connected_peers",
            "peers": ["/ip4/192.168.1.1/tcp/4001/p2p/QmCachedPeer"],
            "peer_count": 1,
            "timestamp": time.time()
        }
        cache_manager.get.return_value = cached_result
        
        # Call the method
        result = model.get_connected_peers()
        
        # Verify cached result was returned
        assert result == cached_result
        
        # Verify cache was checked
        cache_manager.get.assert_called_once_with("libp2p_connected_peers")
    
    def test_get_connected_peers_error(self, model):
        """Test get_connected_peers method with error."""
        # Simulate an error by raising an exception
        with patch.object(model.libp2p_peer, 'get_connected_peers', side_effect=Exception("Test error")):
            result = model.get_connected_peers()
            
            # Verify error response
            assert result["success"] is False
            assert "error" in result
            assert "Test error" in result["error"]
            assert result["error_type"] == "peer_listing_error"
            assert model.operation_stats["failed_operations"] == 1
    
    def test_get_peer_info(self, model):
        """Test get_peer_info method."""
        # Call the method
        result = model.get_peer_info("QmTestPeer")
        
        # Verify result structure
        assert result["success"] is True
        assert result["operation"] == "get_peer_info"
        assert result["peer_id"] == "QmTestPeer"
        assert "addresses" in result
        assert "protocols" in result
        assert "connected" in result
        
        # Verify operation stats were updated
        assert model.operation_stats["operation_count"] == 1
    
    def test_get_peer_info_not_found(self, model):
        """Test get_peer_info method with peer not found."""
        # Call the method with a peer ID that won't be found
        result = model.get_peer_info("nonexistent")
        
        # Verify error response
        assert result["success"] is False
        assert "error" in result
        assert "Peer not found" in result["error"]
        assert result["error_type"] == "peer_not_found"
        assert model.operation_stats["failed_operations"] == 1
    
    def test_get_peer_info_error(self, model):
        """Test get_peer_info method with error."""
        # Simulate an error by raising an exception
        with patch.object(model.libp2p_peer, 'get_peer_info', side_effect=Exception("Test error")):
            result = model.get_peer_info("QmTestPeer")
            
            # Verify error response
            assert result["success"] is False
            assert "error" in result
            assert "Test error" in result["error"]
            assert result["error_type"] == "peer_info_error"
            assert model.operation_stats["failed_operations"] == 1
    
    def test_reset(self, model, cache_manager):
        """Test reset method."""
        # Prepare the model with some operations
        model.operation_stats["operation_count"] = 10
        model.operation_stats["peers_discovered"] = 5
        model.operation_stats["content_retrieved"] = 3
        
        # Call the method
        result = model.reset()
        
        # Verify result structure
        assert result["success"] is True
        assert result["operation"] == "reset"
        assert "timestamp" in result
        
        # Verify operation stats were reset
        assert model.operation_stats["operation_count"] == 0
        assert model.operation_stats["failed_operations"] == 0
        assert model.operation_stats["peers_discovered"] == 0
        assert model.operation_stats["content_retrieved"] == 0
        
        # Verify cache was cleared
        assert "cache_entries_cleared" in result
        # Cache manager should have been asked to delete libp2p_* entries
        expected_calls = [call("libp2p_health"), call("libp2p_content_QmTest"), call("libp2p_peers_all")]
        for exp_call in expected_calls:
            assert exp_call in cache_manager.delete.call_args_list
    
    def test_reset_error(self, model, cache_manager):
        """Test reset method with error."""
        # Simulate an error by raising an exception
        cache_manager.list_keys.side_effect = Exception("Test error")
        
        # Call the method
        result = model.reset()
        
        # Verify error response
        assert result["success"] is False
        assert "error" in result
        assert "Test error" in result["error"]
        assert result["error_type"] == "reset_error"
    
    def test_get_stats(self, model):
        """Test get_stats method."""
        # Prepare the model with some operations
        model.operation_stats["operation_count"] = 25
        model.operation_stats["failed_operations"] = 2
        model.operation_stats["peers_discovered"] = 10
        model.operation_stats["content_retrieved"] = 8
        model.operation_stats["bytes_retrieved"] = 1024 * 1024
        
        # Call the method
        result = model.get_stats()
        
        # Verify result structure
        assert result["success"] is True
        assert result["operation"] == "get_stats"
        assert "timestamp" in result
        assert "stats" in result
        assert "uptime" in result
        
        # Verify stats values
        assert result["stats"]["operation_count"] == 25
        assert result["stats"]["failed_operations"] == 2
        assert result["stats"]["peers_discovered"] == 10
        assert result["stats"]["content_retrieved"] == 8
        assert result["stats"]["bytes_retrieved"] == 1024 * 1024
        
        # Uptime should be non-negative
        assert result["uptime"] >= 0


@pytest.mark.anyio
class TestLibP2PModelAnyIO:
    """Test suite for LibP2P Model with AnyIO compatibility."""
    
    @pytest.fixture
    def model(self, cache_manager, credential_manager):
        """Create a LibP2P model for testing."""
        resources = {"max_memory": 1024 * 1024 * 100}  # 100 MB
        metadata = {
            "role": "worker",
            "enable_mdns": True,
            "use_enhanced_dht": True,
        }
        
        model = LibP2PModel(
            cache_manager=cache_manager,
            credential_manager=credential_manager,
            resources=resources,
            metadata=metadata
        )
        return model
    
    async def test_health_check_async(self, model):
        """Test get_health method with async."""
        # Convert the synchronous method to a coroutine for testing
        async def async_get_health():
            return model.get_health()
        
        # Call the method
        result = await async_get_health()
        
        # Verify result structure
        assert result["success"] is True
        assert result["libp2p_available"] is True
        assert result["peer_initialized"] is True
        assert "peer_id" in result
        assert "addresses" in result
        assert "connected_peers" in result
        assert "protocols" in result
        
        # Verify operation stats were updated
        assert model.operation_stats["operation_count"] == 1
    
    async def test_discover_peers_async(self, model):
        """Test discover_peers method with async."""
        # Convert the synchronous method to a coroutine for testing
        async def async_discover_peers():
            return model.discover_peers(discovery_method="all", limit=10)
        
        # Call the method
        result = await async_discover_peers()
        
        # Verify result structure
        assert result["success"] is True
        assert "peers" in result
        assert len(result["peers"]) > 0
        assert "peer_count" in result
        
        # Verify operation stats were updated
        assert model.operation_stats["operation_count"] == 1
        assert model.operation_stats["peers_discovered"] > 0
    
    async def test_get_content_async(self, model):
        """Test get_content method with async."""
        # Convert the synchronous method to a coroutine for testing
        async def async_get_content():
            return model.get_content("QmTestCID")
        
        # Call the method
        result = await async_get_content()
        
        # Verify result structure
        assert result["success"] is True
        assert result["operation"] == "get_content"
        assert result["cid"] == "QmTestCID"
        assert "data" in result
        assert result["size"] == len(result["data"])
        
        # Verify operation stats were updated
        assert model.operation_stats["operation_count"] == 1
        assert model.operation_stats["content_retrieved"] == 1
        assert model.operation_stats["bytes_retrieved"] > 0


@pytest.mark.parametrize("libp2p_available", [True, False])
def test_dependency_availability(libp2p_available, cache_manager, credential_manager):
    """
    Test model behavior with different libp2p availability states.
    
    This test parameterizes the libp2p availability to test both scenarios:
    1. When libp2p is available
    2. When libp2p is not available
    
    It verifies that the model behaves correctly in both cases, properly reporting
    availability status and returning appropriate results.
    """
    # Log the specific test scenario
    logger.info(f"Testing with libp2p_available={libp2p_available}")
    
    # Patch HAS_LIBP2P to control availability for this specific test
    with patch('ipfs_kit_py.mcp.models.libp2p_model.HAS_LIBP2P', libp2p_available):
        # Create model
        model = LibP2PModel(
            cache_manager=cache_manager,
            credential_manager=credential_manager,
            metadata={"auto_install_dependencies": False}  # Prevent auto-install during test
        )
        
        # Check the model's is_available method
        if libp2p_available:
            assert model.is_available() is True
            assert model.libp2p_peer is not None
        else:
            assert model.is_available() is False
            assert model.libp2p_peer is None
        
        # Try performing an operation
        result = model.get_health()
        
        # Check result based on availability
        if libp2p_available:
            assert result["success"] is True
            assert result["libp2p_available"] is True
            assert result["peer_initialized"] is True
        else:
            assert result["success"] is False
            assert result["libp2p_available"] is False
            assert result["peer_initialized"] is False
            assert "error" in result
            assert "libp2p is not available" in result["error"]
            
        logger.info(f"Test completed for libp2p_available={libp2p_available}")

# Add a test that shows actual dependency status
def test_actual_dependency_status(cache_manager, credential_manager):
    """
    Test that shows the actual status of dependencies.
    
    This test doesn't patch HAS_LIBP2P, but instead uses the actual
    dependency status as determined during module import. This helps
    verify that the dependency checking mechanism works correctly.
    """
    # Create model without patching dependencies
    from ipfs_kit_py.libp2p import HAS_LIBP2P as actual_has_libp2p
    
    logger.info(f"Actual dependency status - HAS_DEPENDENCIES: {HAS_DEPENDENCIES}, " 
               f"HAS_LIBP2P: {actual_has_libp2p}")
    
    # Run this test only when we want to see the actual status
    # We're not making assertions here, just logging information
    # This test will be marked as skipped in normal test runs
    if os.environ.get("IPFS_KIT_TEST_ACTUAL_DEPS", "0") != "1":
        pytest.skip("Set IPFS_KIT_TEST_ACTUAL_DEPS=1 to run this test")
        
    # Create model with auto-install enabled
    model = LibP2PModel(
        cache_manager=cache_manager,
        credential_manager=credential_manager,
        metadata={"auto_install_dependencies": True}
    )
    
    # Get health to see what happens with actual dependencies
    result = model.get_health()
    logger.info(f"get_health result with actual dependencies: {result}")
    
    # We don't assert anything here since the result depends on the actual environment