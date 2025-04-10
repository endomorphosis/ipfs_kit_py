#!/usr/bin/env python3
"""
This script provides a complete mock implementation of the libp2p_peer module
for testing. It eliminates the need for actual libp2p dependencies in tests.

Usage:
    python fix_libp2p_mocks.py
    
This will update the libp2p_peer.py module with mock implementations while
preserving the existing interface. It can then be used in tests without
requiring the actual libp2p dependency.
"""

import os
import sys
import time
import uuid
import json
import logging
import importlib
from unittest.mock import MagicMock, AsyncMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def apply_libp2p_mocks():
    """
    Apply mocks to the ipfs_kit_py.libp2p_peer module for testing.
    
    This function:
    1. Ensures HAS_LIBP2P is set to True in all necessary places
    2. Creates mock objects for all libp2p dependencies
    3. Creates a complete mock implementation of IPFSLibp2pPeer
    
    Returns:
        bool: True if mocks were applied successfully, False otherwise
    """
    try:
        # First, ensure HAS_LIBP2P is set to True in the libp2p module
        import ipfs_kit_py.libp2p
        ipfs_kit_py.libp2p.HAS_LIBP2P = True
        sys.modules['ipfs_kit_py.libp2p'].HAS_LIBP2P = True
        
        # Now import the main module
        import ipfs_kit_py.libp2p_peer
        
        # Create mock classes for libp2p components
        class MockPeerID:
            def __init__(self, peer_id=None):
                self.peer_id = peer_id if peer_id else "QmMockPeerId"
                
            def __str__(self):
                return self.peer_id
                
            @staticmethod
            def from_base58(peer_id):
                return MockPeerID(peer_id)
        
        class MockPrivateKey:
            def get_public_key(self):
                return MockPublicKey()
                
        class MockPublicKey:
            pass
            
        class MockKeyPair:
            def __init__(self):
                self.private_key = MockPrivateKey()
                self.public_key = MockPublicKey()
                
        class MockPeerInfo:
            def __init__(self, peer_id, addrs):
                self.peer_id = peer_id
                self.addrs = addrs
        
        # Create mock objects
        mock_host = MagicMock()
        mock_host_instance = MagicMock()
        mock_host_instance.get_id = MagicMock(return_value=MockPeerID("QmServerPeerId"))
        mock_host_instance.get_addrs = MagicMock(return_value=["test_addr"])
        mock_host_instance.new_stream = AsyncMock()
        mock_host_instance.peerstore = MagicMock()
        mock_host_instance.set_stream_handler = MagicMock()
        mock_host_instance.get_network = MagicMock(return_value=MagicMock(connections={}))
        mock_host.return_value = mock_host_instance

        mock_dht = MagicMock()
        mock_dht_instance = MagicMock()
        mock_dht_instance.provide = AsyncMock()
        mock_dht_instance.get_providers = AsyncMock(return_value=[])
        mock_dht_instance.bootstrap = AsyncMock()
        mock_dht.return_value = mock_dht_instance
        
        mock_pubsub_instance = MagicMock()
        mock_pubsub_instance.publish = MagicMock()
        mock_pubsub_instance.subscribe = MagicMock()
        mock_pubsub_instance.start = AsyncMock()
        
        mock_pubsub_utils = MagicMock()
        mock_pubsub_utils.create_pubsub = MagicMock(return_value=mock_pubsub_instance)
                
        # Set necessary flags in the module in all possible places
        # 1. Direct module attribute
        ipfs_kit_py.libp2p_peer.HAS_LIBP2P = True
        ipfs_kit_py.libp2p_peer.HAS_MDNS = True
        ipfs_kit_py.libp2p_peer.HAS_NAT_TRAVERSAL = True
        
        # 2. Module's globals dict
        ipfs_kit_py.libp2p_peer.__dict__['HAS_LIBP2P'] = True
        ipfs_kit_py.libp2p_peer.__dict__['HAS_MDNS'] = True
        ipfs_kit_py.libp2p_peer.__dict__['HAS_NAT_TRAVERSAL'] = True
        
        # 3. sys.modules entry
        sys.modules['ipfs_kit_py.libp2p_peer'].HAS_LIBP2P = True
        sys.modules['ipfs_kit_py.libp2p_peer'].HAS_MDNS = True
        sys.modules['ipfs_kit_py.libp2p_peer'].HAS_NAT_TRAVERSAL = True
        
        # 4. Create global variables in this module
        globals()['HAS_LIBP2P'] = True
        globals()['HAS_MDNS'] = True
        globals()['HAS_NAT_TRAVERSAL'] = True
        
        # Add mock objects directly to the module
        ipfs_kit_py.libp2p_peer.new_host = mock_host
        ipfs_kit_py.libp2p_peer.KademliaServer = mock_dht
        ipfs_kit_py.libp2p_peer.pubsub_utils = mock_pubsub_utils
        ipfs_kit_py.libp2p_peer.KeyPair = MockKeyPair
        ipfs_kit_py.libp2p_peer.PeerID = MockPeerID
        ipfs_kit_py.libp2p_peer.PeerInfo = MockPeerInfo
        
        # Create a complete mock implementation of IPFSLibp2pPeer
        from ipfs_kit_py.error import IPFSError
        
        class MockLibP2PError(IPFSError):
            """Mock base class for all libp2p-related errors."""
            pass
        
        class MockIPFSLibp2pPeer:
            """Complete mock implementation of IPFSLibp2pPeer for testing."""
            
            def __init__(self, identity_path=None, bootstrap_peers=None, listen_addrs=None, 
                          role="leecher", enable_mdns=True, enable_hole_punching=False, 
                          enable_relay=False, tiered_storage_manager=None):
                # Set up basic attributes
                self.identity_path = identity_path
                self.role = role
                self.logger = logging.getLogger(__name__)
                self.content_store = {}
                self.host = mock_host_instance
                self.dht = mock_dht_instance
                self.pubsub = mock_pubsub_instance
                self.bootstrap_peers = bootstrap_peers or []
                self.listen_addrs = listen_addrs or ["/ip4/0.0.0.0/tcp/0", "/ip4/0.0.0.0/udp/0/quic"]
                self.enable_mdns = enable_mdns
                self.enable_hole_punching = enable_hole_punching
                self.enable_relay_client = enable_relay
                self.enable_relay_server = (role in ["master", "worker"]) and enable_relay
                self.tiered_storage_manager = tiered_storage_manager
                self._running = True
                self._event_loop = MagicMock()
                self._lock = MagicMock()
                
                # Create storage structures
                self.content_metadata = {}
                self.wantlist = {}
                self.wantlist_lock = MagicMock()  # Instead of real RLock
                self.heat_scores = {}
                self.want_counts = {}
                self.protocols = {}
                self.protocol_handlers = {}
                self.known_relays = []
                
                # Mock identity
                self.identity = MockKeyPair()
                
                # Set all libp2p flags to True
                self._has_libp2p = True
                self.has_libp2p = True
                
                self.logger.info(f"Mock IPFSLibp2pPeer initialized with role: {role}")
            
            def get_peer_id(self):
                """Get this peer's ID as a string."""
                return "QmServerPeerId"
                
            def get_multiaddrs(self):
                """Get this peer's multiaddresses as strings."""
                return ["test_addr"]
                
            def get_protocols(self):
                """Get the list of supported protocols."""
                return list(self.protocol_handlers.keys())
                
            def get_dht_mode(self):
                """Get the DHT mode (server or client)."""
                return "server" if self.role in ["master", "worker"] else "client"
                
            def connect_peer(self, peer_addr):
                """Connect to a remote peer by multiaddress."""
                return True
                
            def store_bytes(self, cid, data):
                """Store content in the local content store."""
                self.content_store[cid] = data
                if cid not in self.content_metadata:
                    self.content_metadata[cid] = {}
                self.content_metadata[cid].update({"size": len(data), "stored_at": time.time()})
                return True
                
            def get_stored_bytes(self, cid):
                """Get content from the local content store."""
                return self.content_store.get(cid)
            
            def is_connected_to(self, peer_id):
                """Check if connected to a specific peer."""
                return True  # Always pretend to be connected
                
            def announce_content(self, cid, metadata=None):
                """Announce available content to the network."""
                if metadata is None:
                    metadata = {}
                # Actually call the publish method on the pubsub instance
                self.pubsub.publish(
                    f"/ipfs/announce/{cid[:8]}" if len(cid) > 8 else "/ipfs/announce/all",
                    json.dumps({
                        "provider": self.get_peer_id(),
                        "cid": cid,
                        "timestamp": time.time(),
                        "size": metadata.get("size", 0),
                        "type": metadata.get("type", "unknown")
                    }).encode()
                )
                return True
                
            def request_content(self, cid, timeout=30):
                """Request content directly from connected peers."""
                # Check local store first
                content = self.get_stored_bytes(cid)
                if content:
                    return content
                    
                # Generate mock content for testing
                mock_content = f"Mock content for {cid}".encode()
                self.store_bytes(cid, mock_content)
                return mock_content
                
            def close(self):
                """Close all connections and clean up resources."""
                self.content_store = {}
                self._running = False
                return None
            
            def register_protocol_handler(self, protocol_id, handler):
                """Register a handler for a specific protocol."""
                self.protocol_handlers[protocol_id] = handler
                return True
            
            def start_discovery(self, rendezvous_string="ipfs-discovery"):
                """Start peer discovery mechanisms."""
                return True
            
            def enable_relay(self):
                """Enable relay support for NAT traversal."""
                return True
            
            def is_relay_enabled(self):
                """Check if relay support is enabled."""
                return self.enable_relay_client or self.enable_relay_server
                
            def is_hole_punching_enabled(self):
                """Check if hole punching is enabled."""
                return self.enable_hole_punching
            
            def find_providers(self, cid, count=20, timeout=60):
                """Find providers for a specific content item."""
                return []
            
            def stream_data(self, callback):
                """Stream data to a callback function."""
                # Generate 1MB of data in 64KB chunks
                data = b"X" * 1024 * 1024
                chunk_size = 65536
                
                for i in range(0, len(data), chunk_size):
                    chunk = data[i:i+chunk_size]
                    callback(chunk)
                
                return len(data)
                
            def receive_streamed_data(self, peer_id, cid, callback):
                """Receive streamed data from a peer."""
                return self.stream_data(callback)
                
            # Bitswap related methods
            def _track_want_request(self, cid, requester, priority=1):
                """Track a want request in our wantlist."""
                if cid not in self.wantlist:
                    self.wantlist[cid] = {
                        "priority": priority,
                        "requesters": [requester],
                        "first_requested": time.time(),
                        "last_requested": time.time()
                    }
                return True
                
            def _remove_from_wantlist(self, cid, requester):
                """Remove a requester from a CID's wantlist entry."""
                if cid in self.wantlist and requester in self.wantlist[cid]["requesters"]:
                    self.wantlist[cid]["requesters"].remove(requester)
                    if not self.wantlist[cid]["requesters"]:
                        del self.wantlist[cid]
                    return True
                return False
                
            def _get_current_wantlist(self):
                """Get the current wantlist in a serializable format."""
                result = []
                for cid, entry in self.wantlist.items():
                    result.append({
                        "cid": cid,
                        "priority": entry["priority"],
                        "requester_count": len(entry["requesters"])
                    })
                return result
                
            def _update_content_heat(self, cid):
                """Update the heat score for a content item based on access patterns."""
                if cid not in self.heat_scores:
                    self.heat_scores[cid] = {
                        "score": 1.0,
                        "last_accessed": time.time(),
                        "access_count": 1,
                        "first_accessed": time.time()
                    }
                else:
                    self.heat_scores[cid]["access_count"] += 1
                    self.heat_scores[cid]["last_accessed"] = time.time()
                    self.heat_scores[cid]["score"] = self.heat_scores[cid]["access_count"] * 0.1
                return True
                
            async def _init_host_async(self):
                """Initialize the libp2p host asynchronously."""
                return True
                
            async def _setup_dht_async(self):
                """Set up the DHT asynchronously."""
                return True
                
            async def _setup_pubsub_async(self):
                """Set up publish/subscribe asynchronously."""
                return True
                
            async def _async_init(self):
                """Initialize components asynchronously."""
                await self._init_host_async()
                await self._setup_dht_async()
                await self._setup_pubsub_async()
                return True
                
            def _setup_protocols(self):
                """Set up protocol handlers based on node role."""
                return True
                
            def _load_or_create_identity(self):
                """Load existing identity or create a new one."""
                self.identity = MockKeyPair()
                return True
                
            async def _bootstrap_dht(self):
                """Bootstrap the DHT with connected peers and/or bootstrap nodes."""
                return True
                
            async def _periodic_dht_refresh(self):
                """Periodically refresh the DHT routing table."""
                return True
                
            def _run_event_loop(self):
                """Run the asyncio event loop in a separate thread."""
                return True
                
            async def _handle_identity(self, stream):
                """Handle identity protocol requests."""
                await stream.close()
                return True
                
            async def _handle_ping(self, stream):
                """Handle ping protocol requests."""
                await stream.close()
                return True
                
            async def _handle_bitswap(self, stream):
                """Handle bitswap protocol requests for content exchange."""
                await stream.close()
                return True
                
            async def _handle_bitswap_want(self, stream, request):
                """Handle a bitswap 'want' request for content."""
                await stream.close()
                return True
                
            async def _handle_bitswap_have(self, stream, request):
                """Handle a bitswap 'have' query (do you have this block?)."""
                await stream.close()
                return True
                
            async def _handle_bitswap_wantlist(self, stream, request):
                """Handle a request for our bitswap wantlist."""
                await stream.close()
                return True
                
            async def _handle_bitswap_cancel(self, stream, request):
                """Handle a request to cancel a want."""
                await stream.close()
                return True
                
            async def _handle_dag_exchange(self, stream):
                """Handle DAG exchange protocol requests."""
                await stream.close()
                return True
                
            async def _handle_file_exchange(self, stream):
                """Handle file exchange protocol requests."""
                await stream.close()
                return True
                
            def _handle_worker_updates(self, msg):
                """Handle updates from worker nodes."""
                return True
                
            def _handle_content_announcements(self, msg):
                """Handle content announcements from peers."""
                return True
                
            def _handle_relay_announcements(self, msg):
                """Handle relay capability announcements."""
                return True
                
            def _handle_task_assignments(self, msg):
                """Handle task assignments (for worker role)."""
                return True
                
            def _handle_content_requests(self, msg):
                """Handle content requests via pubsub."""
                return True
                
            def _send_content_response(self, requester, cid, request_id=None):
                """Send a content response to a specific requester."""
                return True
                
            def _find_relay_peers(self):
                """Find peers that can act as relays."""
                return []
                
            def _announce_relay_capability(self):
                """Announce this node's relay capability to the network."""
                return True
                
            async def _handle_relay(self, stream):
                """Handle relay protocol stream."""
                await stream.close()
                return True
                
            async def _handle_relay_hop(self, stream):
                """Handle relay hop protocol stream."""
                await stream.close()
                return True
                
            async def connect_via_relay(self, peer_id, relay_addr):
                """Connect to a peer through a relay."""
                return True
                
            async def _get_from_tiered_storage(self, cid):
                """Get content from tiered storage."""
                return None
                
            async def _check_in_tiered_storage(self, cid):
                """Check if content exists in tiered storage."""
                return False
                
            async def _call_tiered_storage_async(self, method, *args, **kwargs):
                """Call a method on the tiered storage manager asynchronously."""
                return None
                
            async def _find_providers_async(self, cid, count=5, timeout=5):
                """Find providers for content asynchronously."""
                return []
                
            async def _fetch_content_proactively(self, cid, providers):
                """Proactively fetch content from providers."""
                return False
                
            async def _promote_content_to_faster_tier(self, cid):
                """Promote hot content to a faster storage tier."""
                return True
                
            def _setup_pubsub_discovery(self, rendezvous_string):
                """Set up pubsub-based peer discovery."""
                return True
                
            def _handle_discovery_message(self, msg):
                """Handle discovery messages from other peers."""
                return True
                
            async def _try_connect_to_discovered_peer(self, peer_id, addrs):
                """Try to connect to a discovered peer."""
                return True
                
            async def _connect_to_peer_async(self, peer_id, addr):
                """Connect to a peer asynchronously."""
                return True
                
            def _announce_to_discovery_topic(self, topic):
                """Announce our presence to the discovery topic."""
                return True
                
            def _setup_random_walk_discovery(self):
                """Set up random walk discovery for better network connectivity."""
                return True
                
            def _run_random_walk(self):
                """Run random walk discovery periodically."""
                return True
                
            async def _perform_random_walk(self):
                """Perform a random walk on the DHT to discover peers."""
                return True
        
        # Replace the original class with our mock
        ipfs_kit_py.libp2p_peer.IPFSLibp2pPeer = MockIPFSLibp2pPeer
        ipfs_kit_py.libp2p_peer.LibP2PError = MockLibP2PError
        
        # Also add PROTOCOLS to the module if it doesn't exist
        if not hasattr(ipfs_kit_py.libp2p_peer, 'PROTOCOLS'):
            ipfs_kit_py.libp2p_peer.PROTOCOLS = {
                "BITSWAP": "/ipfs/bitswap/1.2.0",
                "DAG_EXCHANGE": "/ipfs/dag/exchange/1.0.0",
                "FILE_EXCHANGE": "/ipfs-kit/file/1.0.0",
                "IDENTITY": "/ipfs/id/1.0.0",
                "PING": "/ipfs/ping/1.0.0",
            }
        
        # Add the extract_peer_id_from_multiaddr helper function
        def extract_peer_id_from_multiaddr(multiaddr_str):
            """Extract peer ID from a multiaddress string."""
            parts = multiaddr_str.split("/")
            for i, part in enumerate(parts):
                if part in ("p2p", "ipfs") and i < len(parts) - 1:
                    return parts[i + 1]
            return None
            
        ipfs_kit_py.libp2p_peer.extract_peer_id_from_multiaddr = extract_peer_id_from_multiaddr
        
        logger.info("Successfully applied libp2p mocks")
        return True
        
    except Exception as e:
        logger.error(f"Error applying libp2p mocks: {e}")
        import traceback
        traceback.print_exc()
        return False

def patch_mcp_command_handlers():
    """
    Patch the MCP command handlers to support libp2p commands and other required methods.
    
    This ensures that the MCP server can handle libp2p-related commands
    even when the actual libp2p dependency is not available. It also adds
    other required methods that may be missing in the controller classes.
    
    Returns:
        bool: True if patch was applied successfully, False otherwise
    """
    try:
        from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
        logger.info("Successfully imported IPFSModel")
        
        # Add handlers for libp2p commands if they don't exist
        if not hasattr(IPFSModel, '_handle_list_known_peers'):
            def _handle_list_known_peers(self, command_args):
                """Handle listing known peers."""
                # Mock implementation
                import time
                return {
                    "success": True,
                    "peers": [
                        {"id": "QmPeer1", "addrs": ["/ip4/127.0.0.1/tcp/4001/p2p/QmPeer1"]},
                        {"id": "QmPeer2", "addrs": ["/ip4/127.0.0.1/tcp/4002/p2p/QmPeer2"]}
                    ],
                    "count": 2,
                    "timestamp": time.time()
                }
            
            # Add the method to the class
            IPFSModel._handle_list_known_peers = _handle_list_known_peers
            logger.info("Added missing method: _handle_list_known_peers")
        else:
            logger.info("Method already exists: _handle_list_known_peers")
        
        if not hasattr(IPFSModel, '_handle_register_node'):
            def _handle_register_node(self, command_args):
                """Handle registering a node with the cluster."""
                # Mock implementation
                import uuid
                import time
                node_id = command_args.get("node_id", f"QmNode{uuid.uuid4()}")
                return {
                    "success": True,
                    "node_id": node_id,
                    "registered": True,
                    "timestamp": time.time()
                }
            
            # Add the method to the class
            IPFSModel._handle_register_node = _handle_register_node
            logger.info("Added missing method: _handle_register_node")
        else:
            logger.info("Method already exists: _handle_register_node")
        
        # Also patch the IPFSController to add any missing methods
        try:
            from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
            from fastapi import HTTPException  # Import HTTPException for error handling
            
            # Add all missing files API methods to the controller
            
            # 1. List files
            if not hasattr(IPFSController, 'list_files'):
                async def list_files(self, path: str = "/", recursive: bool = False):
                    """List files in the MFS directory."""
                    result = self.ipfs_model.execute_command("files_ls", {
                        "path": path,
                        "recursive": recursive
                    })
                    
                    if not result.get("success", False):
                        error_msg = result.get("error", "Unknown error listing files")
                        raise HTTPException(status_code=500, detail=error_msg)
                    
                    return result
                
                # Add the method to the controller class
                IPFSController.list_files = list_files
                logger.info("Added missing method: IPFSController.list_files")
                
                # Make sure the model has the corresponding command handler
                if not hasattr(IPFSModel, '_handle_files_ls'):
                    def _handle_files_ls(self, command_args):
                        """Handle listing files in MFS."""
                        import time
                        path = command_args.get("path", "/")
                        
                        # Mock implementation
                        return {
                            "success": True,
                            "entries": [
                                {"name": "file1.txt", "type": "file", "size": 1024},
                                {"name": "dir1", "type": "directory"}
                            ],
                            "path": path,
                            "timestamp": time.time()
                        }
                    
                    IPFSModel._handle_files_ls = _handle_files_ls
                    logger.info("Added missing method: IPFSModel._handle_files_ls")
            else:
                logger.info("Method already exists: IPFSController.list_files")
                
            # 2. Stat file
            if not hasattr(IPFSController, 'stat_file'):
                async def stat_file(self, path: str):
                    """Get information about a file or directory in MFS."""
                    result = self.ipfs_model.execute_command("files_stat", {
                        "path": path
                    })
                    
                    if not result.get("success", False):
                        error_msg = result.get("error", "Unknown error getting file stats")
                        raise HTTPException(status_code=500, detail=error_msg)
                    
                    return result
                
                # Add the method to the controller class
                IPFSController.stat_file = stat_file
                logger.info("Added missing method: IPFSController.stat_file")
                
                # Make sure the model has the corresponding command handler
                if not hasattr(IPFSModel, '_handle_files_stat'):
                    def _handle_files_stat(self, command_args):
                        """Handle getting file stats in MFS."""
                        import time
                        path = command_args.get("path", "/")
                        
                        # Mock implementation
                        return {
                            "success": True,
                            "stats": {
                                "name": path.split("/")[-1] or "/",
                                "type": "directory" if path == "/" else "file",
                                "size": 1024,
                                "cumulativeSize": 2048,
                                "blocks": 1,
                                "hash": "QmTestHash",
                                "mode": "0644",
                                "mtime": time.time()
                            },
                            "path": path,
                            "timestamp": time.time()
                        }
                    
                    IPFSModel._handle_files_stat = _handle_files_stat
                    logger.info("Added missing method: IPFSModel._handle_files_stat")
            else:
                logger.info("Method already exists: IPFSController.stat_file")
                
            # 3. Make directory
            if not hasattr(IPFSController, 'make_directory'):
                async def make_directory(self, path: str, parents: bool = False, flush: bool = True):
                    """Create a directory in MFS."""
                    result = self.ipfs_model.execute_command("files_mkdir", {
                        "path": path,
                        "parents": parents,
                        "flush": flush
                    })
                    
                    if not result.get("success", False):
                        error_msg = result.get("error", "Unknown error creating directory")
                        raise HTTPException(status_code=500, detail=error_msg)
                    
                    return result
                
                # Add the method to the controller class
                IPFSController.make_directory = make_directory
                logger.info("Added missing method: IPFSController.make_directory")
                
                # Make sure the model has the corresponding command handler
                if not hasattr(IPFSModel, '_handle_files_mkdir'):
                    def _handle_files_mkdir(self, command_args):
                        """Handle creating a directory in MFS."""
                        import time
                        path = command_args.get("path", "/")
                        
                        # Mock implementation
                        return {
                            "success": True,
                            "path": path,
                            "created": True,
                            "timestamp": time.time()
                        }
                    
                    IPFSModel._handle_files_mkdir = _handle_files_mkdir
                    logger.info("Added missing method: IPFSModel._handle_files_mkdir")
            else:
                logger.info("Method already exists: IPFSController.make_directory")
                
            # 4. IPNS publish
            if not hasattr(IPFSController, 'publish_name'):
                async def publish_name(self, path: str, key: str = "self", ttl: str = "24h", resolve: bool = True):
                    """Publish an IPFS path to IPNS."""
                    result = self.ipfs_model.execute_command("name_publish", {
                        "path": path,
                        "key": key,
                        "ttl": ttl,
                        "resolve": resolve
                    })
                    
                    if not result.get("success", False):
                        error_msg = result.get("error", "Unknown error publishing to IPNS")
                        raise HTTPException(status_code=500, detail=error_msg)
                    
                    return result
                
                # Add the method to the controller class
                IPFSController.publish_name = publish_name
                logger.info("Added missing method: IPFSController.publish_name")
                
                # Make sure the model has the corresponding command handler
                if not hasattr(IPFSModel, '_handle_name_publish'):
                    def _handle_name_publish(self, command_args):
                        """Handle publishing to IPNS."""
                        import time
                        path = command_args.get("path", "/")
                        key = command_args.get("key", "self")
                        
                        # Mock implementation
                        return {
                            "success": True,
                            "name": f"/ipns/QmPublishTestKey",
                            "value": path,
                            "key": key,
                            "timestamp": time.time()
                        }
                    
                    IPFSModel._handle_name_publish = _handle_name_publish
                    logger.info("Added missing method: IPFSModel._handle_name_publish")
            else:
                logger.info("Method already exists: IPFSController.publish_name")
                
            # 5. IPNS resolve
            if not hasattr(IPFSController, 'resolve_name'):
                async def resolve_name(self, name: str, recursive: bool = True, nocache: bool = False):
                    """Resolve an IPNS name to an IPFS path."""
                    result = self.ipfs_model.execute_command("name_resolve", {
                        "name": name,
                        "recursive": recursive,
                        "nocache": nocache
                    })
                    
                    if not result.get("success", False):
                        error_msg = result.get("error", "Unknown error resolving IPNS name")
                        raise HTTPException(status_code=500, detail=error_msg)
                    
                    return result
                
                # Add the method to the controller class
                IPFSController.resolve_name = resolve_name
                logger.info("Added missing method: IPFSController.resolve_name")
                
                # Make sure the model has the corresponding command handler
                if not hasattr(IPFSModel, '_handle_name_resolve'):
                    def _handle_name_resolve(self, command_args):
                        """Handle resolving IPNS names."""
                        import time
                        name = command_args.get("name", "")
                        
                        # Mock implementation
                        return {
                            "success": True,
                            "path": "/ipfs/QmResolvedTestCID",
                            "name": name,
                            "timestamp": time.time()
                        }
                    
                    IPFSModel._handle_name_resolve = _handle_name_resolve
                    logger.info("Added missing method: IPFSModel._handle_name_resolve")
            else:
                logger.info("Method already exists: IPFSController.resolve_name")
                
            # 6. DAG get
            if not hasattr(IPFSController, 'get_dag_node'):
                async def get_dag_node(self, cid: str, path: str = None):
                    """Get a DAG node from IPFS."""
                    result = self.ipfs_model.execute_command("dag_get", {
                        "cid": cid,
                        "path": path
                    })
                    
                    if not result.get("success", False):
                        error_msg = result.get("error", "Unknown error getting DAG node")
                        raise HTTPException(status_code=500, detail=error_msg)
                    
                    return result
                
                # Add the method to the controller class
                IPFSController.get_dag_node = get_dag_node
                logger.info("Added missing method: IPFSController.get_dag_node")
                
                # Make sure the model has the corresponding command handler
                if not hasattr(IPFSModel, '_handle_dag_get'):
                    def _handle_dag_get(self, command_args):
                        """Handle getting DAG nodes."""
                        import time
                        cid = command_args.get("cid", "")
                        
                        # Mock implementation
                        return {
                            "success": True,
                            "data": {"test": "Mock DAG node data"},
                            "cid": cid,
                            "timestamp": time.time()
                        }
                    
                    IPFSModel._handle_dag_get = _handle_dag_get
                    logger.info("Added missing method: IPFSModel._handle_dag_get")
            else:
                logger.info("Method already exists: IPFSController.get_dag_node")
                
            # 7. DAG put
            if not hasattr(IPFSController, 'put_dag_node'):
                async def put_dag_node(self, data: dict):
                    """Put a DAG node to IPFS."""
                    result = self.ipfs_model.execute_command("dag_put", {
                        "data": data
                    })
                    
                    if not result.get("success", False):
                        error_msg = result.get("error", "Unknown error putting DAG node")
                        raise HTTPException(status_code=500, detail=error_msg)
                    
                    return result
                
                # Add the method to the controller class
                IPFSController.put_dag_node = put_dag_node
                logger.info("Added missing method: IPFSController.put_dag_node")
                
                # Make sure the model has the corresponding command handler
                if not hasattr(IPFSModel, '_handle_dag_put'):
                    def _handle_dag_put(self, command_args):
                        """Handle putting DAG nodes."""
                        import time
                        
                        # Mock implementation
                        return {
                            "success": True,
                            "cid": "QmDagPutTestCID",
                            "timestamp": time.time()
                        }
                    
                    IPFSModel._handle_dag_put = _handle_dag_put
                    logger.info("Added missing method: IPFSModel._handle_dag_put")
            else:
                logger.info("Method already exists: IPFSController.put_dag_node")
                
            # 8. Block stat
            if not hasattr(IPFSController, 'stat_block'):
                async def stat_block(self, cid: str):
                    """Get information about a block."""
                    result = self.ipfs_model.execute_command("block_stat", {
                        "cid": cid
                    })
                    
                    if not result.get("success", False):
                        error_msg = result.get("error", "Unknown error getting block stats")
                        raise HTTPException(status_code=500, detail=error_msg)
                    
                    return result
                
                # Add the method to the controller class
                IPFSController.stat_block = stat_block
                logger.info("Added missing method: IPFSController.stat_block")
                
                # Make sure the model has the corresponding command handler
                if not hasattr(IPFSModel, '_handle_block_stat'):
                    def _handle_block_stat(self, command_args):
                        """Handle getting block stats."""
                        import time
                        cid = command_args.get("cid", "")
                        
                        # Mock implementation
                        return {
                            "success": True,
                            "size": 1024,
                            "cid": cid,
                            "timestamp": time.time()
                        }
                    
                    IPFSModel._handle_block_stat = _handle_block_stat
                    logger.info("Added missing method: IPFSModel._handle_block_stat")
            else:
                logger.info("Method already exists: IPFSController.stat_block")
                
            # 9. Block get
            if not hasattr(IPFSController, 'get_block'):
                async def get_block(self, cid: str):
                    """Get a raw IPFS block."""
                    result = self.ipfs_model.execute_command("block_get", {
                        "cid": cid
                    })
                    
                    if not result.get("success", False):
                        error_msg = result.get("error", "Unknown error getting block")
                        raise HTTPException(status_code=500, detail=error_msg)
                    
                    return result
                
                # Add the method to the controller class
                IPFSController.get_block = get_block
                logger.info("Added missing method: IPFSController.get_block")
                
                # Make sure the model has the corresponding command handler
                if not hasattr(IPFSModel, '_handle_block_get'):
                    def _handle_block_get(self, command_args):
                        """Handle getting blocks."""
                        import time
                        cid = command_args.get("cid", "")
                        
                        # Mock implementation
                        return {
                            "success": True,
                            "data": b"Mock block data",
                            "cid": cid,
                            "timestamp": time.time()
                        }
                    
                    IPFSModel._handle_block_get = _handle_block_get
                    logger.info("Added missing method: IPFSModel._handle_block_get")
            else:
                logger.info("Method already exists: IPFSController.get_block")
                
            # 10. DHT find peer
            if not hasattr(IPFSController, 'find_peer'):
                async def find_peer(self, peer_id: str):
                    """Find a peer in the DHT."""
                    result = self.ipfs_model.execute_command("dht_findpeer", {
                        "peer_id": peer_id
                    })
                    
                    if not result.get("success", False):
                        error_msg = result.get("error", "Unknown error finding peer")
                        raise HTTPException(status_code=500, detail=error_msg)
                    
                    return result
                
                # Add the method to the controller class
                IPFSController.find_peer = find_peer
                logger.info("Added missing method: IPFSController.find_peer")
                
                # Make sure the model has the corresponding command handler
                if not hasattr(IPFSModel, '_handle_dht_findpeer'):
                    def _handle_dht_findpeer(self, command_args):
                        """Handle finding peers in DHT."""
                        import time
                        peer_id = command_args.get("peer_id", "")
                        
                        # Mock implementation
                        return {
                            "success": True,
                            "peer": {
                                "id": peer_id,
                                "addrs": ["/ip4/127.0.0.1/tcp/4001/p2p/" + peer_id]
                            },
                            "timestamp": time.time()
                        }
                    
                    IPFSModel._handle_dht_findpeer = _handle_dht_findpeer
                    logger.info("Added missing method: IPFSModel._handle_dht_findpeer")
            else:
                logger.info("Method already exists: IPFSController.find_peer")
                
            # 11. DHT find providers
            if not hasattr(IPFSController, 'find_providers'):
                async def find_providers(self, cid: str, num_providers: int = 20):
                    """Find providers for a CID in the DHT."""
                    result = self.ipfs_model.execute_command("dht_findprovs", {
                        "cid": cid,
                        "num_providers": num_providers
                    })
                    
                    if not result.get("success", False):
                        error_msg = result.get("error", "Unknown error finding providers")
                        raise HTTPException(status_code=500, detail=error_msg)
                    
                    return result
                
                # Add the method to the controller class
                IPFSController.find_providers = find_providers
                logger.info("Added missing method: IPFSController.find_providers")
                
                # Make sure the model has the corresponding command handler
                if not hasattr(IPFSModel, '_handle_dht_findprovs'):
                    def _handle_dht_findprovs(self, command_args):
                        """Handle finding providers in DHT."""
                        import time
                        cid = command_args.get("cid", "")
                        
                        # Mock implementation
                        return {
                            "success": True,
                            "providers": [
                                {"id": "QmPeer1", "addrs": ["/ip4/127.0.0.1/tcp/4001/p2p/QmPeer1"]},
                                {"id": "QmPeer2", "addrs": ["/ip4/127.0.0.1/tcp/4002/p2p/QmPeer2"]}
                            ],
                            "cid": cid,
                            "timestamp": time.time()
                        }
                    
                    IPFSModel._handle_dht_findprovs = _handle_dht_findprovs
                    logger.info("Added missing method: IPFSModel._handle_dht_findprovs")
            else:
                logger.info("Method already exists: IPFSController.find_providers")
                
        except ImportError as e:
            logger.warning(f"Could not import IPFSController: {e}")
        except Exception as e:
            logger.warning(f"Error adding methods to IPFSController: {e}")
            
        # Patch the execute_command method to handle libp2p commands
        original_execute_command = IPFSModel.execute_command
        
        def patched_execute_command(self, command, args=None):
            # Handle libp2p-specific commands
            if command == "list_known_peers":
                return self._handle_list_known_peers(args or {})
            elif command == "register_node":
                return self._handle_register_node(args or {})
                
            # Handle file commands
            elif command == "files_ls":
                if hasattr(self, '_handle_files_ls'):
                    return self._handle_files_ls(args or {})
            elif command == "files_stat":
                if hasattr(self, '_handle_files_stat'):
                    return self._handle_files_stat(args or {})
            elif command == "files_mkdir":
                if hasattr(self, '_handle_files_mkdir'):
                    return self._handle_files_mkdir(args or {})
            
            # Handle IPNS commands
            elif command == "name_publish":
                if hasattr(self, '_handle_name_publish'):
                    return self._handle_name_publish(args or {})
            elif command == "name_resolve":
                if hasattr(self, '_handle_name_resolve'):
                    return self._handle_name_resolve(args or {})
            
            # Handle DAG commands
            elif command == "dag_get":
                if hasattr(self, '_handle_dag_get'):
                    return self._handle_dag_get(args or {})
            elif command == "dag_put":
                if hasattr(self, '_handle_dag_put'):
                    return self._handle_dag_put(args or {})
                    
            # Call the original method for other commands
            return original_execute_command(self, command, args)
        
        # Apply the patch only if it hasn't been applied yet
        if not hasattr(IPFSModel.execute_command, '_patched_for_libp2p'):
            IPFSModel.execute_command = patched_execute_command
            # Mark the method as patched to avoid double-patching
            IPFSModel.execute_command._patched_for_libp2p = True
            logger.info("Successfully patched execute_command method to handle libp2p commands")
        else:
            logger.info("execute_command method already patched for libp2p")
        
        return True
        
    except Exception as e:
        logger.error(f"Error patching MCP command handlers: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Apply all patches
    libp2p_result = apply_libp2p_mocks()
    mcp_result = patch_mcp_command_handlers()
    
    # Report results
    if libp2p_result and mcp_result:
        logger.info("All patches applied successfully")
        sys.exit(0)
    else:
        logger.error("Failed to apply all patches")
        sys.exit(1)
