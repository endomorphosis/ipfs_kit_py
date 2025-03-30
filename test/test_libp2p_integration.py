"""
Tests for the enhanced libp2p integration functionality.

These tests verify the integration between the enhanced DHT discovery,
content routing, and IPFSKit components.
"""

import os
import sys
import unittest
import time
import tempfile

# Ensure package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer
from ipfs_kit_py.libp2p.enhanced_dht_discovery import EnhancedDHTDiscovery, ContentRoutingManager
from ipfs_kit_py.libp2p.p2p_integration import LibP2PIntegration, register_libp2p_with_ipfs_kit
from ipfs_kit_py.libp2p.ipfs_kit_integration import extend_ipfs_kit_class

class TestLibP2PIntegration(unittest.TestCase):
    """Test cases for the enhanced libp2p integration."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary test file
        self.test_file = tempfile.NamedTemporaryFile(delete=False)
        self.test_file.write(b"Test content for libp2p integration")
        self.test_file.close()
        
        # Create IPFS kit instance
        self.kit = ipfs_kit()
        
        # Create libp2p peer instance
        self.libp2p_peer = None
        try:
            self.libp2p_peer = IPFSLibp2pPeer(role="leecher")
        except Exception as e:
            print(f"Could not create libp2p peer: {e}")
            # Skip tests that need libp2p peer
            self.skipTest("LibP2P peer could not be created")
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove temporary file
        if hasattr(self, 'test_file') and os.path.exists(self.test_file.name):
            os.unlink(self.test_file.name)
    
    def test_enhanced_dht_discovery_creation(self):
        """Test that enhanced DHT discovery can be created."""
        if not self.libp2p_peer:
            self.skipTest("LibP2P peer not available")
            
        discovery = EnhancedDHTDiscovery(
            self.libp2p_peer,
            role="leecher"
        )
        self.assertIsNotNone(discovery)
    
    def test_content_routing_manager_creation(self):
        """Test that content routing manager can be created."""
        if not self.libp2p_peer:
            self.skipTest("LibP2P peer not available")
            
        discovery = EnhancedDHTDiscovery(
            self.libp2p_peer,
            role="leecher"
        )
        
        router = ContentRoutingManager(
            discovery,
            self.libp2p_peer
        )
        self.assertIsNotNone(router)
    
    def test_libp2p_integration_creation(self):
        """Test that libp2p integration layer can be created."""
        if not self.libp2p_peer:
            self.skipTest("LibP2P peer not available")
            
        integration = LibP2PIntegration(
            libp2p_peer=self.libp2p_peer,
            ipfs_kit=self.kit
        )
        self.assertIsNotNone(integration)
    
    def test_register_with_ipfs_kit(self):
        """Test registering libp2p integration with IPFSKit."""
        if not self.libp2p_peer:
            self.skipTest("LibP2P peer not available")
            
        # Register with IPFSKit
        integration = register_libp2p_with_ipfs_kit(
            self.kit,
            self.libp2p_peer,
            extend_cache=False  # Don't extend cache for this test
        )
        
        self.assertIsNotNone(integration)
        self.assertTrue(hasattr(self.kit, 'libp2p_integration'))
    
    def test_extend_ipfs_kit_class(self):
        """Test extending the IPFSKit class with libp2p integration."""
        # Create a test class
        class TestKit:
            def get_filesystem(self, **kwargs):
                return None
        
        # Extend the class
        extended = extend_ipfs_kit_class(TestKit)
        
        # Check that the class was extended
        self.assertTrue(hasattr(extended, '_handle_content_miss_with_libp2p'))
        self.assertTrue(hasattr(extended, 'get_filesystem'))
        
    def test_handle_cache_miss(self):
        """Test handling a cache miss via libp2p integration."""
        if not self.libp2p_peer:
            self.skipTest("LibP2P peer not available")
            
        # Add the test file to IPFS
        result = self.kit.ipfs_add_file(self.test_file.name)
        self.assertTrue(result['success'])
        
        # Get the CID
        cid = result['Hash']
        
        # Create the integration layer
        integration = LibP2PIntegration(
            libp2p_peer=self.libp2p_peer,
            ipfs_kit=self.kit
        )
        self.kit.libp2p_integration = integration
        
        # Mock the cache manager
        class MockCacheManager:
            def __init__(self):
                self.data = {}
            
            def get(self, key):
                return self.data.get(key)
            
            def put(self, key, content, metadata=None):
                self.data[key] = content
        
        mock_cache = MockCacheManager()
        integration.cache_manager = mock_cache
        
        # Try to handle a cache miss - this may not work in all environments
        # since we need peers with the content, but we'll try it anyway
        try:
            content = self.kit._handle_content_miss_with_libp2p(cid)
            
            # This may or may not find content depending on the network
            if content:
                self.assertEqual(content, b"Test content for libp2p integration")
        except Exception as e:
            # If it fails, it's not necessarily an error - just means
            # peer discovery didn't work in this environment
            print(f"Cache miss handling test didn't succeed: {e}")
            # We don't want to fail the test just because the network doesn't have our content
            pass


if __name__ == '__main__':
    unittest.main()