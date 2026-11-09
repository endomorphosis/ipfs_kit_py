"""
libp2p mock implementations for testing.

This module provides mock implementations of the libp2p functionality for testing.
It can be used to enable tests that require libp2p without having the actual
dependency installed.

Usage:
    from ipfs_kit_py.libp2p.libp2p_mocks import apply_libp2p_mocks
    apply_libp2p_mocks()  # This will apply mocks to necessary modules
"""

import logging
import json
import time
import uuid
from unittest.mock import MagicMock, AsyncMock
import sys

# Configure logger
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
                        enable_relay=False, tiered_storage_manager=None, **kwargs):
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
                
            def get_listen_addresses(self):
                """Get listen addresses."""
                return self.listen_addrs
                
            def get_connected_peers(self):
                """Get list of connected peers."""
                return ["QmPeer1", "QmPeer2"]
                
            def connect_peer(self, peer_addr):
                """Connect to a remote peer by multiaddress."""
                return True
                
            def store_content_locally(self, cid, data):
                """Store content in the local content store."""
                self.content_store[cid] = data
                if cid not in self.content_metadata:
                    self.content_metadata[cid] = {}
                self.content_metadata[cid].update({"size": len(data), "stored_at": time.time()})
                return True
                
            def store_bytes(self, cid, data):
                """Store content in the local content store."""
                return self.store_content_locally(cid, data)
                
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
                
            def retrieve_content(self, cid, timeout=30):
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
                
            def start(self):
                """Start the peer."""
                self._running = True
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
                
            def find_peer_addresses(self, peer_id, timeout=30):
                """Find peer addresses in DHT."""
                return ["/ip4/127.0.0.1/tcp/4001/p2p/" + peer_id]
                
            def provide_content(self, cid):
                """Provide content to the DHT."""
                return True
            
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
                
            def get_peer_info(self, peer_id):
                """Get peer information."""
                return {
                    "id": peer_id,
                    "addresses": [f"/ip4/127.0.0.1/tcp/4001/p2p/{peer_id}"],
                    "protocols": ["ipfs/bitswap/1.2.0"],
                    "connected": True,
                    "last_seen": time.time()
                }
                
            def get_detailed_stats(self):
                """Get detailed statistics."""
                return {
                    "connections": 2,
                    "dht_lookups": 5,
                    "content_retrieved": 10,
                    "bytes_transferred": 1024,
                    "uptime": 3600
                }
                
            def subscribe(self, topic, handler):
                """Subscribe to a topic with handler."""
                return True
                
            def unsubscribe(self, topic):
                """Unsubscribe from a topic."""
                return True
                
            def get_topics(self):
                """Get list of subscribed topics."""
                return ["test_topic"]
                
            def get_topic_peers(self, topic):
                """Get peers for a topic."""
                return ["QmPeer1", "QmPeer2"]
                
            def publish_message(self, topic, message):
                """Publish a message to a topic."""
                return True
            
            def discover_peers_dht(self, limit=10):
                """Discover peers using DHT."""
                return ["QmPeer1", "QmPeer2"]
                
            def discover_peers_mdns(self, limit=10):
                """Discover peers using mDNS."""
                return ["QmPeer3", "QmPeer4"]
                
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
        
        # Replace the original class with our mock if it's imported
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
                
            # 6. DHT find peer
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
                
            # 7. DHT find providers
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
            
        # Add execute_command method if it doesn't exist
        if not hasattr(IPFSModel, 'execute_command'):
            def execute_command(self, command, **kwargs):
                """
                Execute a command against the IPFS daemon.
                
                This is a mock implementation that handles libp2p-specific commands.
                """
                command_args = kwargs
                result = {
                    "success": False,
                    "command": command,
                    "timestamp": time.time()
                }
                
                # Handle libp2p commands
                if command.startswith("libp2p_"):
                    # Extract the specific libp2p operation
                    libp2p_command = command[7:]  # Remove "libp2p_" prefix
                    
                    # Handle connect peer
                    if libp2p_command == "connect_peer":
                        peer_addr = command_args.get("peer_addr")
                        result["success"] = True
                        result["result"] = {
                            "connected": True,
                            "peer_id": peer_addr.split("/")[-1] if isinstance(peer_addr, str) else "unknown"
                        }
                        
                    # Handle get peers
                    elif libp2p_command == "get_peers":
                        result["success"] = True
                        result["peers"] = [
                            {"id": "QmPeer1", "addrs": ["/ip4/127.0.0.1/tcp/4001/p2p/QmPeer1"]},
                            {"id": "QmPeer2", "addrs": ["/ip4/127.0.0.1/tcp/4002/p2p/QmPeer2"]}
                        ]
                        
                    # Handle publish
                    elif libp2p_command == "publish":
                        topic = command_args.get("topic", "")
                        message = command_args.get("message", "")
                        result["success"] = True
                        result["result"] = {
                            "published": True,
                            "topic": topic,
                            "message_size": len(message) if isinstance(message, str) else 0
                        }
                        
                    # Handle subscribe
                    elif libp2p_command == "subscribe":
                        topic = command_args.get("topic", "")
                        result["success"] = True
                        result["result"] = {
                            "subscribed": True,
                            "topic": topic
                        }
                        
                    # Handle announce content
                    elif libp2p_command == "announce_content":
                        cid = command_args.get("cid", "")
                        result["success"] = True
                        result["result"] = {
                            "announced": True,
                            "cid": cid
                        }
                    
                    # Handle get node ID
                    elif libp2p_command == "get_node_id":
                        result["success"] = True
                        result["result"] = {
                            "node_id": "QmMockNodeId"
                        }
                        
                    # Handle unknown libp2p command
                    else:
                        result["success"] = False
                        result["error"] = f"Unknown libp2p command: {libp2p_command}"
                
                # Handle other commands that would be passed to the IPFS daemon
                else:
                    result["success"] = False
                    result["error"] = f"Command not implemented in mock: {command}"
                
                return result
                
            # Add the execute_command method to the IPFSModel class
            IPFSModel.execute_command = execute_command
            logger.info("Added missing method: IPFSModel.execute_command")
        else:
            logger.info("execute_command method already patched for libp2p")
        
        return True
        
    except Exception as e:
        logger.error(f"Error patching MCP command handlers: {e}")
        import traceback
        traceback.print_exc()
        return False