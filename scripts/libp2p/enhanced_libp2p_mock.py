#!/usr/bin/env python3
"""
Enhanced mock implementation of the libp2p_peer module for testing.

This script provides a complete mock implementation of IPFSLibp2pPeer with
all necessary methods. It properly addresses issues in the test that require
specific method implementations.
"""

import os
import sys
import json
import time
import uuid
import logging
import threading
import unittest.mock
from unittest.mock import MagicMock, AsyncMock
from typing import Any, Dict, List, Optional, Set, Union, Callable

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Set HAS_LIBP2P to True for mocking
HAS_LIBP2P = True
HAS_MDNS = True
HAS_NAT_TRAVERSAL = True

# Define protocol constants like the real module
PROTOCOLS = {
    "BITSWAP": "/ipfs/bitswap/1.2.0",
    "DAG_EXCHANGE": "/ipfs/dag/exchange/1.0.0",
    "FILE_EXCHANGE": "/ipfs-kit/file/1.0.0",
    "IDENTITY": "/ipfs/id/1.0.0",
    "PING": "/ipfs/ping/1.0.0",
}

# Define error class
class LibP2PError(Exception):
    """Base class for all libp2p-related errors."""
    pass

# Create mock host, DHT, and PubSub classes
class MockHost:
    def __init__(self, *args, **kwargs):
        self.peer_id = "QmServerPeerId"
        self.addrs = ["/ip4/127.0.0.1/tcp/4001/p2p/QmServerPeerId"]
        self.network = MagicMock()
        self.network.connections = {}
        self.network.listen = MagicMock()
        self.peerstore = MagicMock()
        self.set_stream_handler = MagicMock()
        self.get_id = MagicMock(return_value=self.peer_id)
        self.get_addrs = MagicMock(return_value=self.addrs)
        self.new_stream = AsyncMock()
        self.get_network = MagicMock(return_value=self.network)

    async def connect(self, peer_info):
        logger.debug(f"Mock connecting to peer: {peer_info}")
        return True

class MockDHT:
    def __init__(self, *args, **kwargs):
        self.provide = AsyncMock()
        self.get_providers = AsyncMock(return_value=[])
        self.find_peer = AsyncMock(return_value=[])
        self.bootstrap = AsyncMock()

class MockPubSub:
    def __init__(self, *args, **kwargs):
        self.start = AsyncMock()
        self.stop = MagicMock()
        self.publish = MagicMock()
        self.subscribe = MagicMock()

class MockKeyPair:
    def __init__(self):
        self.private_key = MagicMock()
        self.public_key = MagicMock()

class MockPeerID:
    @staticmethod
    def from_base58(peer_id):
        return f"PeerID({peer_id})"

# Now create the complete mock IPFSLibp2pPeer class
class IPFSLibp2pPeer:
    """Complete mock implementation of IPFSLibp2pPeer with all required methods."""

    def __init__(
        self,
        identity_path: Optional[str] = None,
        bootstrap_peers: Optional[List[str]] = None,
        listen_addrs: Optional[List[str]] = None,
        role: str = "leecher",
        enable_mdns: bool = True,
        enable_hole_punching: bool = False,
        enable_relay: bool = False,
        tiered_storage_manager: Optional[Any] = None,
    ):
        """Initialize a libp2p peer for direct IPFS content exchange."""
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"Creating mock IPFSLibp2pPeer with role={role}")

        # Store configuration
        self.role = role
        self.identity_path = identity_path
        self.bootstrap_peers = bootstrap_peers or []
        self.enable_mdns = enable_mdns
        self.enable_hole_punching = enable_hole_punching
        self.enable_relay_client = enable_relay
        self.enable_relay_server = (role in ["master", "worker"]) and enable_relay
        self.tiered_storage_manager = tiered_storage_manager

        # Default listen addresses if none provided
        if listen_addrs is None:
            listen_addrs = ["/ip4/0.0.0.0/tcp/0", "/ip4/0.0.0.0/udp/0/quic"]
        self.listen_addrs = listen_addrs

        # Component initialization
        self.host = MockHost()
        self.dht = MockDHT()
        self.pubsub = MockPubSub()
        self.protocols = {}
        self.content_store = {}  # Local content store (CID -> bytes)
        self.content_metadata = {}  # Metadata for stored content
        self.protocol_handlers = {}  # Protocol handlers (protocol_id -> handler_function)
        self._running = True
        self._event_loop = None
        self._lock = threading.RLock()

        # Bitswap protocol specific data structures
        self.wantlist = {}  # Tracking wanted CIDs: {cid: {priority, requesters: [peer_ids]}}
        self.wantlist_lock = threading.RLock()  # For thread-safe access
        self.heat_scores = {}  # Track content "heat" for prioritization {cid: score}
        self.want_counts = {}  # Count of how many times a CID is wanted {cid: count}
        self.known_relays = []

        # Create mock identity
        self.identity = MockKeyPair()

        self.logger.debug(f"Mock IPFSLibp2pPeer initialized with ID: {self.get_peer_id()}")

    # Core API methods
    def get_peer_id(self) -> str:
        """Get this peer's ID as a string."""
        return "QmServerPeerId"

    def get_multiaddrs(self) -> List[str]:
        """Get this peer's multiaddresses as strings."""
        return ["/ip4/127.0.0.1/tcp/4001/p2p/QmServerPeerId"]

    def get_protocols(self) -> List[str]:
        """Get the list of supported protocols."""
        return list(PROTOCOLS.values())

    def get_dht_mode(self) -> str:
        """Get the DHT mode (server or client)."""
        if self.role in ["master", "worker"]:
            return "server"
        return "client"

    def connect_peer(self, peer_addr: str) -> bool:
        """Connect to a remote peer by multiaddress."""
        self.logger.debug(f"Mock connecting to peer address: {peer_addr}")
        return True

    def is_connected_to(self, peer_id: str) -> bool:
        """Check if connected to a specific peer."""
        # Always return True for testing
        return True

    def start_discovery(self, rendezvous_string: str = "ipfs-kit") -> bool:
        """Start peer discovery mechanisms."""
        self.logger.debug(f"Mock starting discovery with rendezvous={rendezvous_string}")
        return True

    def enable_relay(self) -> bool:
        """Enable relay support for NAT traversal."""
        self.logger.debug("Mock enabling relay support")
        return True

    def is_relay_enabled(self) -> bool:
        """Check if relay support is enabled."""
        return self.enable_relay_client or self.enable_relay_server

    def is_hole_punching_enabled(self) -> bool:
        """Check if hole punching is enabled."""
        return self.enable_hole_punching

    def register_protocol_handler(self, protocol_id: str, handler: Callable) -> bool:
        """Register a handler for a specific protocol."""
        self.protocol_handlers[protocol_id] = handler
        self.logger.debug(f"Mock registered handler for protocol: {protocol_id}")
        return True

    def store_bytes(self, cid: str, data: bytes) -> bool:
        """Store content in the local content store."""
        self.content_store[cid] = data
        # Store metadata
        if cid not in self.content_metadata:
            self.content_metadata[cid] = {}

        self.content_metadata[cid].update({"size": len(data), "stored_at": time.time()})
        self.logger.debug(f"Mock stored {len(data)} bytes for CID: {cid}")
        return True

    def get_stored_bytes(self, cid: str) -> Optional[bytes]:
        """Get content from the local content store."""
        return self.content_store.get(cid)

    def announce_content(self, cid: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Announce available content to the network."""
        self.logger.debug(f"Mock announcing content: {cid}")
        return True

    def find_providers(self, cid: str, count: int = 20, timeout: int = 60) -> List[Dict[str, Any]]:
        """Find providers for a specific content item."""
        # Return mock providers
        return [
            {"id": f"QmPeer{i}", "addrs": [f"/ip4/127.0.0.1/tcp/4001/p2p/QmPeer{i}"], "source": "mock"}
            for i in range(count)
        ]

    def request_content(self, cid: str, timeout: int = 30) -> Optional[bytes]:
        """Request content directly from connected peers."""
        # Check local store first
        local_content = self.get_stored_bytes(cid)
        if local_content:
            return local_content

        # Generate mock data if not in local store
        mock_content = f"Mock content for {cid}".encode()
        self.store_bytes(cid, mock_content)
        self.logger.debug(f"Mock created content for: {cid}")
        return mock_content

    def receive_streamed_data(self, peer_id: str, cid: str, callback: Callable[[bytes], None]) -> int:
        """Receive streamed data from a peer."""
        # Generate mock data
        data = b"X" * 1024 * 1024  # 1MB of data
        chunk_size = 65536  # 64KB chunks
        total_bytes = 0

        for i in range(0, len(data), chunk_size):
            chunk = data[i:i+chunk_size]
            callback(chunk)
            total_bytes += len(chunk)

        return total_bytes

    def stream_data(self, callback: Callable[[bytes], None]) -> int:
        """Stream data to a callback function."""
        # Generate mock data
        data = b"X" * 1024 * 1024  # 1MB of data
        chunk_size = 65536  # 64KB chunks

        for i in range(0, len(data), chunk_size):
            chunk = data[i:i+chunk_size]
            callback(chunk)

        return len(data)

    def close(self) -> None:
        """Close all connections and clean up resources."""
        self.logger.debug("Mock closing libp2p peer")
        self.content_store.clear()
        self.content_metadata.clear()
        self.protocol_handlers.clear()
        self.wantlist.clear()
        self.heat_scores.clear()
        self.want_counts.clear()
        self._running = False

# Mock module-level functions
def extract_peer_id_from_multiaddr(multiaddr_str: str) -> Optional[str]:
    """Extract peer ID from a multiaddress string."""
    try:
        # Check if multiaddr contains p2p/ipfs protocol
        parts = multiaddr_str.split("/")
        for i, part in enumerate(parts):
            if part in ("p2p", "ipfs") and i < len(parts) - 1:
                return parts[i + 1]

        return None
    except Exception:
        return None

# Create mock module-level functions and classes
new_host = MockHost
KademliaServer = MockDHT
pubsub_utils = MagicMock()
pubsub_utils.create_pubsub = MagicMock(return_value=MockPubSub())
KeyPair = MockKeyPair
PeerID = MockPeerID

def apply_to_module():
    """
    Apply these mocks to the actual module.

    This function:
    1. Sets HAS_LIBP2P and other flags to True
    2. Replaces the IPFSLibp2pPeer class with our mock
    3. Adds all necessary mock functions and classes
    """
    import ipfs_kit_py.libp2p_peer

    # Set necessary flags
    ipfs_kit_py.libp2p_peer.HAS_LIBP2P = True
    ipfs_kit_py.libp2p_peer.HAS_MDNS = True
    ipfs_kit_py.libp2p_peer.HAS_NAT_TRAVERSAL = True

    # Set in module globals dict
    ipfs_kit_py.libp2p_peer.__dict__['HAS_LIBP2P'] = True
    ipfs_kit_py.libp2p_peer.__dict__['HAS_MDNS'] = True
    ipfs_kit_py.libp2p_peer.__dict__['HAS_NAT_TRAVERSAL'] = True

    # Set in sys.modules
    sys.modules['ipfs_kit_py.libp2p_peer'].HAS_LIBP2P = True
    sys.modules['ipfs_kit_py.libp2p_peer'].HAS_MDNS = True
    sys.modules['ipfs_kit_py.libp2p_peer'].HAS_NAT_TRAVERSAL = True

    # Replace the class
    ipfs_kit_py.libp2p_peer.IPFSLibp2pPeer = IPFSLibp2pPeer
    ipfs_kit_py.libp2p_peer.LibP2PError = LibP2PError

    # Add mock functions and classes
    ipfs_kit_py.libp2p_peer.new_host = new_host
    ipfs_kit_py.libp2p_peer.KademliaServer = KademliaServer
    ipfs_kit_py.libp2p_peer.pubsub_utils = pubsub_utils
    ipfs_kit_py.libp2p_peer.KeyPair = KeyPair
    ipfs_kit_py.libp2p_peer.PeerID = PeerID
    ipfs_kit_py.libp2p_peer.extract_peer_id_from_multiaddr = extract_peer_id_from_multiaddr
    ipfs_kit_py.libp2p_peer.PROTOCOLS = PROTOCOLS

    logger.info("Successfully applied comprehensive libp2p mocks to module")
    return True

if __name__ == "__main__":
    result = apply_to_module()
    sys.exit(0 if result else 1)
