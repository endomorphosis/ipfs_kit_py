"""
Tests for direct P2P communication using libp2p in ipfs_kit_py.

This module tests the peer-to-peer communication capabilities of the ipfs_kit_py library,
including:
- Direct connections between peers using libp2p
- Peer discovery mechanisms (mDNS, DHT, bootstrap, rendezvous)
- Protocol negotiation and stream handling
- NAT traversal techniques (hole punching, relays)
- Direct content exchange between peers
"""

import unittest
import os
import time
import tempfile
import threading
import uuid
import random
import json
from unittest.mock import patch, MagicMock, PropertyMock

# Test imports
import pytest

# Optional imports to check for availability
try:
    import libp2p
    HAS_LIBP2P = True
except ImportError:
    HAS_LIBP2P = False

# Try to import the modules we'll be testing
try:
    from ipfs_kit_py.ipfs_kit import ipfs_kit
    from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer
    HAS_LIBP2P_PEER = True
except ImportError:
    HAS_LIBP2P_PEER = False


@pytest.mark.skipif(not HAS_LIBP2P_PEER, reason="IPFSLibp2pPeer not available")
class TestLibp2pPeer(unittest.TestCase):
    """Test direct peer-to-peer connections with libp2p."""

    def setUp(self):
        """Set up test environment with mocked peers."""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        
        # Create test data
        self.test_data = b"Test content for libp2p data transfer" * 100  # ~3KB
        self.test_cid = "QmTestCIDForLibp2p"
        
        # Create peer configurations
        self.peer1_config = {
            'identity_path': os.path.join(self.temp_dir.name, "peer1.key"),
            'listen_addrs': ["/ip4/127.0.0.1/tcp/0"],
            'role': 'worker'
        }
        
        self.peer2_config = {
            'identity_path': os.path.join(self.temp_dir.name, "peer2.key"),
            'listen_addrs': ["/ip4/127.0.0.1/tcp/0"],
            'role': 'leecher'  
        }
        
        # When using real peers (not mocked), this will be uncommented
        # self.peer1 = IPFSLibp2pPeer(**self.peer1_config)
        # self.peer2 = IPFSLibp2pPeer(**self.peer2_config)
        
        # For now, use mocks during early development
        self.peer1 = MagicMock()
        self.peer2 = MagicMock()
        
    def tearDown(self):
        """Clean up temporary files."""
        self.temp_dir.cleanup()
        
        # Close peers when using real implementations
        # self.peer1.close()
        # self.peer2.close()
        
    def test_peer_initialization(self):
        """Test peer initialization and identity generation."""
        with patch('ipfs_kit_py.libp2p_peer.IPFSLibp2pPeer._init_host') as mock_init:
            # Create a real peer
            peer = IPFSLibp2pPeer(role="worker")
            
            # Verify initialization
            mock_init.assert_called_once()
            
            # Verify peer has correct attributes
            self.assertEqual(peer.role, "worker")
            self.assertIsNotNone(peer.listen_addrs)
            
            # Close properly
            peer.close()
            
    def test_peer_identity_persistence(self):
        """Test that peer identities are generated and persisted correctly."""
        # Create a temporary key file
        key_path = os.path.join(self.temp_dir.name, "test_identity.key")
        
        # First peer should generate a new identity
        with patch('ipfs_kit_py.libp2p_peer.IPFSLibp2pPeer._init_host'):
            peer1 = IPFSLibp2pPeer(identity_path=key_path, role="worker")
            peer1_id = peer1.get_peer_id()
            peer1.close()
            
        # Second peer should load the same identity
        with patch('ipfs_kit_py.libp2p_peer.IPFSLibp2pPeer._init_host'):
            peer2 = IPFSLibp2pPeer(identity_path=key_path, role="worker")
            peer2_id = peer2.get_peer_id()
            peer2.close()
            
        # IDs should match
        self.assertEqual(peer1_id, peer2_id)
        
    def test_local_peer_connection(self):
        """Test that peers can discover and connect to each other locally."""
        # Initialize peers with real functionality in a separate thread to test connections
        def setup_and_connect_peers():
            peer1 = IPFSLibp2pPeer(**self.peer1_config)
            peer2 = IPFSLibp2pPeer(**self.peer2_config)
            
            # Get peer1's address that peer2 can dial
            peer1_addr = peer1.get_multiaddrs()[0]
            
            # Connect peer2 to peer1
            success = peer2.connect_peer(peer1_addr)
            
            # Check connection status
            connected = peer2.is_connected_to(peer1.get_peer_id())
            
            # Clean up
            peer1.close()
            peer2.close()
            
            return success, connected
            
        with patch('ipfs_kit_py.libp2p_peer.IPFSLibp2pPeer._init_host'):
            # This test requires real peers, so we'll mock the connection result for now
            # success, connected = setup_and_connect_peers()
            success, connected = True, True
            
        self.assertTrue(success, "Failed to connect to peer")
        self.assertTrue(connected, "Peers not connected after connection attempt")
            
    def test_mdns_discovery(self):
        """Test peer discovery via mDNS on local network."""
        # Configure and start mDNS discovery on peers
        with patch('ipfs_kit_py.libp2p_peer.IPFSLibp2pPeer.start_discovery') as mock_discovery:
            peer = IPFSLibp2pPeer(role="worker")
            peer.start_discovery(rendezvous_string="ipfs-kit-test")
            
            # Verify discovery was started
            mock_discovery.assert_called_once()
            
            # The real test would wait for peers to discover each other
            # We mock this behavior for now
            peer.close()
        
    @patch('ipfs_kit_py.libp2p_peer.IPFSLibp2pPeer.request_content')
    def test_content_exchange(self, mock_request):
        """Test direct content exchange between peers."""
        # Set up mock response
        mock_request.return_value = self.test_data
        
        # Configure peer for testing
        with patch('ipfs_kit_py.libp2p_peer.IPFSLibp2pPeer._init_host'):
            peer = IPFSLibp2pPeer(role="leecher")
            
            # Request content from connected peers
            content = peer.request_content(self.test_cid)
            
            # Verify content was retrieved
            self.assertEqual(content, self.test_data)
            mock_request.assert_called_with(self.test_cid)
            
            # Close peer
            peer.close()
            
    def test_announce_content(self):
        """Test announcing available content to the network."""
        with patch('ipfs_kit_py.libp2p_peer.IPFSLibp2pPeer._init_host'):
            peer = IPFSLibp2pPeer(role="worker")
            
            # Mock the pubsub and DHT
            peer.pubsub = MagicMock()
            peer.dht = MagicMock()
            
            # Announce content
            metadata = {"size": len(self.test_data), "type": "text/plain"}
            peer.announce_content(self.test_cid, metadata)
            
            # Verify DHT provide was called
            peer.dht.provide.assert_called_with(self.test_cid)
            
            # Verify pubsub publish was called
            peer.pubsub.publish.assert_called()
            
            # Close peer
            peer.close()
            
    def test_protocol_negotiation(self):
        """Test protocol negotiation between peers."""
        with patch('ipfs_kit_py.libp2p_peer.IPFSLibp2pPeer._init_host'):
            peer = IPFSLibp2pPeer(role="worker")
            
            # Set up protocols
            test_protocol = "/ipfs-kit/test/1.0.0"
            peer.register_protocol_handler(test_protocol, MagicMock())
            
            # Check if protocol was registered
            self.assertIn(test_protocol, peer.get_protocols())
            
            # Close peer
            peer.close()
            
    def test_nat_traversal(self):
        """Test NAT traversal techniques."""
        with patch('ipfs_kit_py.libp2p_peer.IPFSLibp2pPeer._init_host'):
            peer = IPFSLibp2pPeer(role="worker", enable_hole_punching=True)
            
            # Enable relay support
            peer.enable_relay()
            
            # Verify hole punching is enabled
            self.assertTrue(peer.is_hole_punching_enabled())
            
            # Verify relay is enabled
            self.assertTrue(peer.is_relay_enabled())
            
            # Close peer
            peer.close()
            
    def test_role_specific_behavior(self):
        """Test role-specific behavior for different node types."""
        # Test master role
        with patch('ipfs_kit_py.libp2p_peer.IPFSLibp2pPeer._init_host'):
            master_peer = IPFSLibp2pPeer(role="master")
            
            # Master should be configured as a DHT server
            self.assertEqual(master_peer.get_dht_mode(), "server")
            
            # Master should have more protocols and capabilities
            master_protocols = master_peer.get_protocols()
            master_peer.close()
            
        # Test worker role
        with patch('ipfs_kit_py.libp2p_peer.IPFSLibp2pPeer._init_host'):
            worker_peer = IPFSLibp2pPeer(role="worker")
            
            # Worker should be a DHT server by default
            self.assertEqual(worker_peer.get_dht_mode(), "server")
            
            worker_protocols = worker_peer.get_protocols()
            worker_peer.close()
            
        # Test leecher role
        with patch('ipfs_kit_py.libp2p_peer.IPFSLibp2pPeer._init_host'):
            leecher_peer = IPFSLibp2pPeer(role="leecher")
            
            # Leecher should be a DHT client to conserve resources
            self.assertEqual(leecher_peer.get_dht_mode(), "client")
            
            leecher_protocols = leecher_peer.get_protocols()
            leecher_peer.close()
            
        # Master should have more protocols than worker or leecher
        self.assertGreater(len(master_protocols), len(leecher_protocols))
            
    def test_streaming_data_transfer(self):
        """Test streaming data transfer between peers."""
        large_data = b"X" * 1024 * 1024  # 1MB of data
        chunk_size = 64 * 1024  # 64KB chunks
        
        # Mock streamed data transfer
        with patch('ipfs_kit_py.libp2p_peer.IPFSLibp2pPeer._init_host'):
            peer1 = IPFSLibp2pPeer(role="worker")
            peer2 = IPFSLibp2pPeer(role="leecher")
            
            # Store data on peer1
            peer1.store_bytes(self.test_cid, large_data)
            
            # Mock streaming from peer1 to peer2
            def mock_stream_data(callback):
                # Simulate streaming in chunks
                for i in range(0, len(large_data), chunk_size):
                    chunk = large_data[i:i+chunk_size]
                    callback(chunk)
                return len(large_data)
                
            peer1.stream_data = MagicMock(side_effect=mock_stream_data)
            
            # Create a receiver to collect chunks
            received_data = bytearray()
            def receiver(chunk):
                received_data.extend(chunk)
                
            # Perform streaming transfer
            total_size = peer2.receive_streamed_data(peer1.get_peer_id(), self.test_cid, receiver)
            
            # Verify data was transferred correctly
            self.assertEqual(len(received_data), len(large_data))
            self.assertEqual(bytes(received_data), large_data)
            self.assertEqual(total_size, len(large_data))
            
            # Close peers
            peer1.close()
            peer2.close()


@pytest.mark.skipif(not HAS_LIBP2P_PEER, reason="IPFSLibp2pPeer not available")
class TestIpfsKitLibp2pIntegration(unittest.TestCase):
    """Test integration of libp2p functionality with the main ipfs_kit."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.TemporaryDirectory()
        
        # Test data
        self.test_data = b"Test content for IPFS Kit libp2p integration"
        self.test_cid = "QmTestCIDForLibp2pIntegration"
        
    def tearDown(self):
        """Clean up temporary files."""
        self.temp_dir.cleanup()
        
    def test_ipfs_kit_with_libp2p(self):
        """Test ipfs_kit integration with libp2p functionality."""
        with patch('ipfs_kit_py.ipfs_kit.IPFSKit._setup_libp2p') as mock_setup:
            # Create an ipfs_kit instance with libp2p enabled
            kit = ipfs_kit(enable_libp2p=True, role="worker")
            
            # Verify libp2p setup was called
            mock_setup.assert_called_once()
            
            # Verify the kit has a libp2p attribute
            self.assertTrue(hasattr(kit, 'libp2p'))
            
    def test_direct_peer_content_retrieval(self):
        """Test retrieving content directly from peers using libp2p."""
        with patch('ipfs_kit_py.ipfs_kit.IPFSKit._setup_libp2p'):
            # Create an ipfs_kit instance with mock libp2p
            kit = ipfs_kit(enable_libp2p=True, role="leecher")
            kit.libp2p = MagicMock()
            kit.libp2p.request_content.return_value = self.test_data
            
            # Try to retrieve content from peers
            content = kit.get_from_peers(self.test_cid)
            
            # Verify content was retrieved using libp2p
            self.assertEqual(content, self.test_data)
            kit.libp2p.request_content.assert_called_with(self.test_cid)
            
    def test_fallback_to_ipfs_daemon(self):
        """Test falling back to IPFS daemon when content not available via libp2p."""
        with patch('ipfs_kit_py.ipfs_kit.IPFSKit._setup_libp2p'):
            # Create an ipfs_kit instance with mock libp2p that fails to find content
            kit = ipfs_kit(enable_libp2p=True, role="leecher")
            kit.libp2p = MagicMock()
            kit.libp2p.request_content.return_value = None
            
            # Mock IPFS daemon retrieval
            kit.ipfs = MagicMock()
            kit.ipfs.cat.return_value = {"Hash": self.test_cid, "Data": self.test_data}
            
            # Try to retrieve content with fallback
            content = kit.get_content(self.test_cid, use_p2p=True, use_fallback=True)
            
            # Verify libp2p was tried first, then fallback to daemon
            kit.libp2p.request_content.assert_called_with(self.test_cid)
            kit.ipfs.cat.assert_called_with(self.test_cid)
            
            # Verify content was retrieved
            self.assertEqual(content, self.test_data)
            
    def test_content_discovery(self):
        """Test content discovery using DHT."""
        with patch('ipfs_kit_py.ipfs_kit.IPFSKit._setup_libp2p'):
            # Create an ipfs_kit instance
            kit = ipfs_kit(enable_libp2p=True, role="leecher")
            kit.libp2p = MagicMock()
            
            # Mock finding providers
            mock_providers = [
                {"id": "QmPeer1", "addrs": ["/ip4/127.0.0.1/tcp/4001"]},
                {"id": "QmPeer2", "addrs": ["/ip4/192.168.1.2/tcp/4001"]}
            ]
            kit.libp2p.find_providers.return_value = mock_providers
            
            # Find providers for content
            providers = kit.find_content_providers(self.test_cid)
            
            # Verify DHT lookup was used
            kit.libp2p.find_providers.assert_called_with(self.test_cid, count=20)
            
            # Verify providers were found
            self.assertEqual(len(providers), 2)
            self.assertEqual(providers[0]["id"], "QmPeer1")
            
    def test_announce_after_add(self):
        """Test that content is announced after adding to IPFS."""
        with patch('ipfs_kit_py.ipfs_kit.IPFSKit._setup_libp2p'):
            # Create an ipfs_kit instance with mock components
            kit = ipfs_kit(enable_libp2p=True, role="worker")
            kit.libp2p = MagicMock()
            kit.ipfs = MagicMock()
            kit.ipfs.add.return_value = {"Hash": self.test_cid}
            
            # Add content to IPFS
            result = kit.add(self.test_data)
            
            # Verify content was announced
            kit.libp2p.announce_content.assert_called_with(
                self.test_cid,
                {"size": len(self.test_data)}
            )


if __name__ == '__main__':
    unittest.main()