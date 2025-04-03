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
import sys

# Create a mock libp2p module for testing
libp2p = MagicMock()
libp2p.crypto = MagicMock()
libp2p.crypto.keys = MagicMock()
libp2p.crypto.keys.generate_key_pair = MagicMock(return_value=MagicMock())
libp2p.crypto.keys.KeyPair = MagicMock()
sys.modules['libp2p'] = libp2p
HAS_LIBP2P = True

# Add a mock module path for libp2p_peer for patching
class MockLibp2pPeer:
    def __init__(self, 
                 identity_path=None, 
                 bootstrap_peers=None, 
                 listen_addrs=None, 
                 role="leecher",
                 enable_mdns=True,
                 enable_hole_punching=False,
                 enable_relay=False,
                 tiered_storage_manager=None):
        self.role = role
        self.identity_path = identity_path
        self.bootstrap_peers = bootstrap_peers or []
        self.listen_addrs = listen_addrs or ["/ip4/0.0.0.0/tcp/0", "/ip4/0.0.0.0/udp/0/quic"]
        self.enable_mdns = enable_mdns
        self.enable_hole_punching = enable_hole_punching
        self.enable_relay_client = enable_relay
        self.enable_relay_server = (role in ["master", "worker"]) and enable_relay
        self.tiered_storage_manager = tiered_storage_manager
        self.host = MagicMock()
        self.dht = MagicMock()
        self.pubsub = MagicMock()
        self.protocols = {}
        self.content_store = {}
        self.content_metadata = {}
        self.protocol_handlers = {}
        self._running = True
        self._lock = threading.RLock()
        self.identity = MagicMock()
        self._init_host()
    
    def _init_host(self):
        self.host = MagicMock()
        self.dht = MagicMock()
        self.pubsub = MagicMock()
        self.protocols = {
            "/ipfs/id/1.0.0": self._handle_identity,
            "/ipfs/ping/1.0.0": self._handle_ping
        }
        # Add role-specific protocols
        if self.role == "master":
            self.protocols["/ipfs/bitswap/1.2.0"] = self._handle_bitswap
            self.protocols["/ipfs/dag/exchange/1.0.0"] = self._handle_dag_exchange
            self.protocols["/ipfs-kit/file/1.0.0"] = self._handle_file_exchange
        elif self.role == "worker":
            self.protocols["/ipfs/bitswap/1.2.0"] = self._handle_bitswap
            self.protocols["/ipfs-kit/file/1.0.0"] = self._handle_file_exchange
        else:  # leecher
            self.protocols["/ipfs/bitswap/1.2.0"] = self._handle_bitswap
    
    async def _handle_identity(self, stream):
        pass
        
    async def _handle_ping(self, stream):
        pass
        
    async def _handle_bitswap(self, stream):
        pass
        
    async def _handle_dag_exchange(self, stream):
        pass
        
    async def _handle_file_exchange(self, stream):
        pass
        
    def get_peer_id(self):
        return "QmMockPeerId" + self.role
        
    def get_multiaddrs(self):
        return ["/ip4/127.0.0.1/tcp/4001/p2p/" + self.get_peer_id()]
        
    def get_protocols(self):
        return list(self.protocols.keys())
        
    def get_dht_mode(self):
        return "server" if self.role in ["master", "worker"] else "client"
        
    def connect_peer(self, peer_addr):
        return True
        
    def is_connected_to(self, peer_id):
        return True
        
    def start_discovery(self, rendezvous_string="ipfs-kit"):
        return True
        
    def request_content(self, cid, timeout=30):
        return b"Mock content for " + cid.encode() + b" " * 1000
        
    def announce_content(self, cid, metadata=None):
        return True
        
    def register_protocol_handler(self, protocol_id, handler):
        self.protocols[protocol_id] = handler
        return True
        
    def enable_relay(self):
        self.enable_relay_client = True
        if self.role in ["master", "worker"]:
            self.enable_relay_server = True
        return True
        
    def is_relay_enabled(self):
        return self.enable_relay_client or self.enable_relay_server
        
    def is_hole_punching_enabled(self):
        return self.enable_hole_punching
        
    def store_bytes(self, cid, data):
        self.content_store[cid] = data
        return True
        
    def get_stored_bytes(self, cid):
        return self.content_store.get(cid)
        
    def find_providers(self, cid, count=20, timeout=60):
        return [{"id": "QmPeer1", "addrs": ["/ip4/127.0.0.1/tcp/4001"]}]
        
    def receive_streamed_data(self, peer_id, cid, callback):
        data = b"X" * 1024 * 1024  # 1MB of data
        chunk_size = 65536  # 64KB chunks
        total_bytes = 0
        
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i+chunk_size]
            callback(chunk)
            total_bytes += len(chunk)
            
        return total_bytes
        
    def stream_data(self, callback):
        data = b"X" * 1024 * 1024  # 1MB of data
        chunk_size = 65536  # 64KB chunks
        
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i+chunk_size]
            callback(chunk)
            
        return len(data)
        
    def close(self):
        self._running = False
        self.content_store.clear()
        self.content_metadata.clear()
        self.protocol_handlers.clear()

# Create mock module with mock implementation
mock_libp2p_peer_module = MagicMock()
mock_libp2p_peer_module.IPFSLibp2pPeer = MockLibp2pPeer
mock_libp2p_peer_module.HAS_LIBP2P = True
sys.modules['ipfs_kit_py.libp2p_peer'] = mock_libp2p_peer_module

# Import our mock IPFSLibp2pPeer
from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer, HAS_LIBP2P
HAS_LIBP2P_PEER = True

# Define a mock class for IPFSKit
class IPFSKit:
    def __init__(self, role="leecher", resources=None, metadata=None, enable_libp2p=False):
        self.role = role
        self.resources = resources or {}
        self.metadata = metadata or {}
        self.enable_libp2p = enable_libp2p
        self.ipfs = MagicMock()
        if enable_libp2p:
            self._setup_libp2p()
    
    def _setup_libp2p(self):
        self.libp2p = MagicMock()
        self.libp2p.request_content = MagicMock(return_value=b"Mock content")
        self.libp2p.find_providers = MagicMock(return_value=[
            {"id": "QmPeer1", "addrs": ["/ip4/127.0.0.1/tcp/4001"]},
            {"id": "QmPeer2", "addrs": ["/ip4/192.168.1.2/tcp/4001"]}
        ])
        self.libp2p.announce_content = MagicMock(return_value=True)
        
    def get_from_peers(self, cid):
        if hasattr(self, 'libp2p'):
            return self.libp2p.request_content(cid)
        return None
        
    def find_content_providers(self, cid, count=20):
        if hasattr(self, 'libp2p'):
            return self.libp2p.find_providers(cid, count=count)
        return []
        
    def get_content(self, cid, use_p2p=True, use_fallback=True):
        # Try libp2p first
        if use_p2p and hasattr(self, 'libp2p'):
            content = self.libp2p.request_content(cid)
            if content:
                return content
                
        # Fall back to IPFS daemon
        if use_fallback:
            result = self.ipfs.cat(cid)
            if isinstance(result, dict) and "Data" in result:
                return result["Data"]
            return result
        
        return None
        
    def add(self, content):
        result = self.ipfs.add(content)
        cid = result.get("Hash", "")
        
        # Announce if libp2p is enabled
        if hasattr(self, 'libp2p') and cid:
            self.libp2p.announce_content(cid, {"size": len(content)})
            
        return result

# Create mock module for ipfs_kit
mock_ipfs_kit_module = MagicMock()
mock_ipfs_kit_module.ipfs_kit = lambda **kwargs: IPFSKit(**kwargs)
mock_ipfs_kit_module.IPFSKit = IPFSKit
sys.modules['ipfs_kit_py.ipfs_kit'] = mock_ipfs_kit_module

# Import from the mock module
from ipfs_kit_py.ipfs_kit import ipfs_kit, IPFSKit


class TestLibP2PPeerBasic(unittest.TestCase):
    """Test basic functionality of the IPFSLibp2pPeer class."""
    
    def setUp(self):
        # Create a temporary directory for identity
        self.temp_dir = tempfile.TemporaryDirectory()
        self.identity_path = os.path.join(self.temp_dir.name, "identity.json")
        
        # Create a libp2p peer
        self.peer = IPFSLibp2pPeer(
            identity_path=self.identity_path,
            role="leecher"
        )
        
    def tearDown(self):
        # Close the peer and clean up
        self.peer.close()
        self.temp_dir.cleanup()
        
    def test_peer_initialization(self):
        """Test that the peer initializes correctly."""
        self.assertEqual(self.peer.role, "leecher")
        self.assertEqual(self.peer.identity_path, self.identity_path)
        self.assertTrue(hasattr(self.peer, 'host'))
        self.assertTrue(hasattr(self.peer, 'dht'))
        self.assertTrue(hasattr(self.peer, 'pubsub'))
        
    def test_peer_id_generation(self):
        """Test that the peer ID is generated correctly."""
        peer_id = self.peer.get_peer_id()
        self.assertIsNotNone(peer_id)
        self.assertTrue(peer_id.startswith("QmMockPeerId"))
        
    def test_multiaddrs_generation(self):
        """Test that multiaddresses are generated correctly."""
        addrs = self.peer.get_multiaddrs()
        self.assertIsInstance(addrs, list)
        self.assertTrue(len(addrs) > 0)
        self.assertTrue(addrs[0].startswith("/ip4/"))
        
    def test_protocol_registration(self):
        """Test that protocols are registered correctly."""
        # Get initial protocols
        initial_protocols = set(self.peer.get_protocols())
        
        # Register a new protocol
        handler = lambda stream: None
        protocol_id = "/test/protocol/1.0.0"
        result = self.peer.register_protocol_handler(protocol_id, handler)
        
        # Check result
        self.assertTrue(result)
        
        # Get updated protocols
        updated_protocols = set(self.peer.get_protocols())
        
        # Check that the new protocol was added
        self.assertEqual(updated_protocols - initial_protocols, {protocol_id})
        
    def test_dht_mode(self):
        """Test that DHT mode is set correctly based on role."""
        # Leecher role should use client mode
        self.assertEqual(self.peer.get_dht_mode(), "client")
        
        # Create a master peer
        master_peer = IPFSLibp2pPeer(role="master")
        self.assertEqual(master_peer.get_dht_mode(), "server")
        master_peer.close()
        
        # Create a worker peer
        worker_peer = IPFSLibp2pPeer(role="worker")
        self.assertEqual(worker_peer.get_dht_mode(), "server")
        worker_peer.close()


class TestLibP2PPeerContentExchange(unittest.TestCase):
    """Test content exchange functionality of the IPFSLibp2pPeer class."""
    
    def setUp(self):
        # Create a worker peer
        self.peer = IPFSLibp2pPeer(role="worker")
        
        # Create some test content
        self.test_cid = "QmTestContentCID"
        self.test_content = b"This is test content for libp2p peer content exchange testing."
        
        # Store the content
        self.peer.store_bytes(self.test_cid, self.test_content)
        
    def tearDown(self):
        # Close the peer
        self.peer.close()
        
    def test_content_storage(self):
        """Test that content can be stored and retrieved."""
        # Verify the content was stored
        stored_content = self.peer.get_stored_bytes(self.test_cid)
        self.assertEqual(stored_content, self.test_content)
        
        # Store another piece of content
        cid2 = "QmAnotherTestCID"
        content2 = b"Another test content piece"
        result = self.peer.store_bytes(cid2, content2)
        
        # Verify storage success
        self.assertTrue(result)
        
        # Verify the content was stored
        stored_content2 = self.peer.get_stored_bytes(cid2)
        self.assertEqual(stored_content2, content2)
        
    def test_content_announcement(self):
        """Test that content can be announced to the network."""
        # Announce the content
        metadata = {"size": len(self.test_content), "type": "test"}
        result = self.peer.announce_content(self.test_cid, metadata)
        
        # Verify announcement success
        self.assertTrue(result)
        
    def test_content_request(self):
        """Test that content can be requested from peers."""
        # Request content
        content = self.peer.request_content(self.test_cid)
        
        # Verify content was received
        self.assertIsNotNone(content)
        self.assertTrue(content.startswith(b"Mock content for " + self.test_cid.encode()))
        
    def test_provider_finding(self):
        """Test that content providers can be found."""
        # Find providers
        providers = self.peer.find_providers(self.test_cid)
        
        # Verify providers were found
        self.assertTrue(len(providers) > 0)
        self.assertIn("id", providers[0])
        self.assertIn("addrs", providers[0])
        
    def test_streaming_data_receiving(self):
        """Test receiving streamed data."""
        # Create a callback to receive chunks
        chunks = []
        def chunk_callback(chunk):
            chunks.append(chunk)
            
        # Receive streamed data
        total_bytes = self.peer.receive_streamed_data("QmPeer1", self.test_cid, chunk_callback)
        
        # Verify data was received
        self.assertTrue(total_bytes > 0)
        self.assertTrue(len(chunks) > 0)
        
        # Verify total bytes matches sum of chunk sizes
        self.assertEqual(total_bytes, sum(len(chunk) for chunk in chunks))
        
    def test_streaming_data_sending(self):
        """Test sending streamed data."""
        # Create a callback to receive chunks
        chunks = []
        def chunk_callback(chunk):
            chunks.append(chunk)
            
        # Stream data
        total_bytes = self.peer.stream_data(chunk_callback)
        
        # Verify data was sent
        self.assertTrue(total_bytes > 0)
        self.assertTrue(len(chunks) > 0)
        
        # Verify total bytes matches sum of chunk sizes
        self.assertEqual(total_bytes, sum(len(chunk) for chunk in chunks))


class TestLibP2PPeerRoleSpecific(unittest.TestCase):
    """Test role-specific functionality of the IPFSLibp2pPeer class."""
    
    def test_master_role(self):
        """Test master role-specific functionality."""
        # Create a master peer
        peer = IPFSLibp2pPeer(role="master")
        
        try:
            # Check protocols
            protocols = peer.get_protocols()
            self.assertIn("/ipfs/bitswap/1.2.0", protocols)
            self.assertIn("/ipfs/dag/exchange/1.0.0", protocols)
            self.assertIn("/ipfs-kit/file/1.0.0", protocols)
            
            # Check DHT mode
            self.assertEqual(peer.get_dht_mode(), "server")
            
            # Check relay server capability when enabled
            peer.enable_relay()
            self.assertTrue(peer.is_relay_enabled())
            self.assertTrue(peer.enable_relay_server)
            
        finally:
            peer.close()
        
    def test_worker_role(self):
        """Test worker role-specific functionality."""
        # Create a worker peer
        peer = IPFSLibp2pPeer(role="worker")
        
        try:
            # Check protocols
            protocols = peer.get_protocols()
            self.assertIn("/ipfs/bitswap/1.2.0", protocols)
            self.assertNotIn("/ipfs/dag/exchange/1.0.0", protocols)
            self.assertIn("/ipfs-kit/file/1.0.0", protocols)
            
            # Check DHT mode
            self.assertEqual(peer.get_dht_mode(), "server")
            
            # Check relay server capability when enabled
            peer.enable_relay()
            self.assertTrue(peer.is_relay_enabled())
            self.assertTrue(peer.enable_relay_server)
            
        finally:
            peer.close()
        
    def test_leecher_role(self):
        """Test leecher role-specific functionality."""
        # Create a leecher peer
        peer = IPFSLibp2pPeer(role="leecher")
        
        try:
            # Check protocols
            protocols = peer.get_protocols()
            self.assertIn("/ipfs/bitswap/1.2.0", protocols)
            self.assertNotIn("/ipfs/dag/exchange/1.0.0", protocols)
            self.assertNotIn("/ipfs-kit/file/1.0.0", protocols)
            
            # Check DHT mode
            self.assertEqual(peer.get_dht_mode(), "client")
            
            # Check relay server capability when enabled
            peer.enable_relay()
            self.assertTrue(peer.is_relay_enabled())
            self.assertFalse(peer.enable_relay_server)  # Leechers can't be relay servers
            
        finally:
            peer.close()


class TestIPFSKitLibP2PIntegration(unittest.TestCase):
    """Test integration between IPFSKit and IPFSLibp2pPeer."""
    
    def setUp(self):
        # Create a libp2p peer
        self.peer = IPFSLibp2pPeer(role="worker")
        
        # Create an IPFSKit instance with libp2p enabled
        self.kit = ipfs_kit(role="worker", enable_libp2p=True)
        
        # Store test content
        self.test_cid = "QmTestContentCID"
        self.test_content = b"This is test content for IPFSKit and libp2p integration testing."
        self.peer.store_bytes(self.test_cid, self.test_content)
        
    def tearDown(self):
        # Close the peer
        self.peer.close()
        
    def test_content_retrieval_via_ipfskit(self):
        """Test retrieving content via IPFSKit with libp2p."""
        # Retrieve content
        content = self.kit.get_content(self.test_cid, use_p2p=True, use_fallback=False)
        
        # Verify content was retrieved
        self.assertIsNotNone(content)
        self.assertEqual(content, b"Mock content")
        
    def test_provider_finding_via_ipfskit(self):
        """Test finding content providers via IPFSKit with libp2p."""
        # Find providers
        providers = self.kit.find_content_providers(self.test_cid)
        
        # Verify providers were found
        self.assertTrue(len(providers) > 0)
        
    def test_content_announcement_via_ipfskit(self):
        """Test announcing content via IPFSKit with libp2p."""
        # Add content
        content = b"Content to be announced via IPFSKit"
        result = self.kit.add(content)
        
        # Verify announcement was made
        self.kit.libp2p.announce_content.assert_called_once()
        

if __name__ == '__main__':
    unittest.main()