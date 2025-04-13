"""
IPFS LibP2P peer implementation for direct peer-to-peer communication.

This module provides direct peer-to-peer communication functionality using libp2p,
enabling content retrieval, peer discovery, and protocol negotiation without
requiring the full IPFS daemon. The implementation is based on the libp2p reference
documentation and the python-peer example in libp2p-universal-connectivity.

Key features:
- Direct peer connections using libp2p
- Content discovery via DHT and mDNS
- NAT traversal through hole punching and relays
- Protocol negotiation for various content exchange patterns
- Integration with the role-based architecture (master/worker/leecher)

This implementation uses anyio for backend-agnostic async operations.
"""

import anyio
import json
import logging
import os
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Union, Type

# Configure logger
logger = logging.getLogger(__name__)

# Import from our libp2p package for dependency management
# This ensures consistent HAS_LIBP2P flag across modules
from ipfs_kit_py.libp2p import HAS_LIBP2P, check_dependencies, install_dependencies, compatible_new_host

# Set defaults for optional features
HAS_MDNS = False
HAS_NAT_TRAVERSAL = False

# Import our compatibility modules
from ipfs_kit_py.libp2p.crypto_compat import (
    serialize_private_key, 
    generate_key_pair, 
    load_private_key,
    create_key_pair
)

# Import libp2p modules only if dependencies are available
if HAS_LIBP2P:
    logger.debug("libp2p dependencies are available, importing required modules")
    try:
        import libp2p
        
        # Handle missing pubsub_utils gracefully
        HAS_PUBSUB = True
        try:
            import libp2p.tools.pubsub.utils as pubsub_utils
        except ImportError as e:
            HAS_PUBSUB = False
            logger.warning(f"libp2p.tools.pubsub module not available: {e}. PubSub functionality will be limited.")
            # Import our custom pubsub implementation
            from ipfs_kit_py.libp2p.tools.pubsub.utils import create_pubsub
            
        from libp2p import new_host
        from libp2p.crypto.keys import KeyPair, PrivateKey, PublicKey
        
        # Import serialization functions - using our compatibility version
        try:
            from libp2p.crypto.serialization import deserialize_private_key
        except ImportError as e:
            logger.warning(f"deserialize_private_key not found in libp2p.crypto.serialization: {e}")
            # Use compatibility version
            deserialize_private_key = load_private_key
                    
        # Try to import other required modules with graceful fallbacks
        HAS_KADEMLIA = True
        try:
            from libp2p.kademlia.network import KademliaServer
        except ImportError as e:
            HAS_KADEMLIA = False
            logger.warning(f"libp2p.kademlia module not available: {e}. DHT functionality will be limited.")
            # Use our custom implementation
            from ipfs_kit_py.libp2p.kademlia.network import KademliaServer
            
        from libp2p.network.exceptions import SwarmException
        
        try:
            from libp2p.network.stream.exceptions import StreamError
            from libp2p.network.stream.net_stream_interface import INetStream
        except ImportError as e:
            logger.warning(f"libp2p.network.stream modules not available: {e}. Streaming functionality will be limited.")
            # Define a minimal StreamError class
            class StreamError(Exception):
                """Error in stream operations."""
                pass
            
        from libp2p.peer.id import ID as PeerID
        from libp2p.peer.peerinfo import PeerInfo
        
        try:
            from libp2p.tools.constants import ALPHA_VALUE
        except ImportError as e:
            # Define a fallback if the constant isn't available
            ALPHA_VALUE = 3
            logger.warning(f"libp2p.tools.constants module not available: {e}. Using default ALPHA_VALUE={ALPHA_VALUE}.")
            # Import from our constants
            from ipfs_kit_py.libp2p.tools.constants import ALPHA_VALUE
            
        try:
            from libp2p.typing import TProtocol
        except ImportError as e:
            # Define a fallback type if needed
            from typing import NewType
            TProtocol = NewType('TProtocol', str)
            logger.warning(f"libp2p.typing module not available: {e}. Using fallback TProtocol type.")
            # Import from our typing module
            from ipfs_kit_py.libp2p.typing import TProtocol

        # Optional imports for discovery - these don't affect basic functionality
        try:
            import libp2p.discovery.mdns as mdns
            HAS_MDNS = True
            logger.debug("mDNS discovery support is available")
        except ImportError as e:
            HAS_MDNS = False
            logger.debug(f"mDNS discovery support is not available: {e}")

        # Optional NAT traversal imports - these don't affect basic functionality
        try:
            from libp2p.transport.tcp.tcp import TCP
            from libp2p.transport.upgrader import TransportUpgrader
            HAS_NAT_TRAVERSAL = True
            logger.debug("NAT traversal support is available")
        except ImportError as e:
            HAS_NAT_TRAVERSAL = False
            logger.debug(f"NAT traversal support is not available: {e}")
    except ImportError as e:
        # If any critical import fails, mark everything as unavailable
        # But don't modify the HAS_LIBP2P flag from the libp2p package
        logger.error(f"Failed to import required libp2p modules: {e}")
        HAS_MDNS = False
        HAS_NAT_TRAVERSAL = False
else:
    logger.warning("libp2p dependencies are not available, peer-to-peer functionality will be limited")
    HAS_NAT_TRAVERSAL = False

# Local imports
from ipfs_kit_py.error import (
    IPFSConfigurationError,
    IPFSConnectionError,
    IPFSContentNotFoundError,
    IPFSError,
    IPFSTimeoutError,
    IPFSValidationError,
)

# Content exchange protocols
PROTOCOLS = {
    "BITSWAP": "/ipfs/bitswap/1.2.0",
    "DAG_EXCHANGE": "/ipfs/dag/exchange/1.0.0",
    "FILE_EXCHANGE": "/ipfs-kit/file/1.0.0",
    "IDENTITY": "/ipfs/id/1.0.0",
    "PING": "/ipfs/ping/1.0.0",
}


# Define a new error type for libp2p operations
class LibP2PError(IPFSError):
    """Base class for all libp2p-related errors."""

    pass


class IPFSLibp2pPeer:
    """Direct peer-to-peer connection interface for IPFS content exchange.

    This class implements direct peer communication using libp2p, enabling
    content discovery, retrieval, and exchange without requiring the full IPFS
    daemon. It follows the role-based architecture, with different behaviors
    for master, worker, and leecher roles.

    Attributes:
        role: Node role ("master", "worker", or "leecher")
        host: libp2p host instance
        dht: Distributed Hash Table for content routing
        pubsub: Publish/subscribe system for messaging
        protocols: Registered protocol handlers
    """

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
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize a libp2p peer for direct IPFS content exchange.

        Args:
            identity_path: Path to store/load peer identity
            bootstrap_peers: List of peers to connect to initially
            listen_addrs: Network addresses to listen on
            role: This node's role in the cluster
            enable_mdns: Whether to enable mDNS discovery
            enable_hole_punching: Whether to enable hole punching for NAT traversal
            enable_relay: Whether to enable relay support
            tiered_storage_manager: Optional tiered storage manager for content storage
        """
        # Set up logger
        self.logger = logging.getLogger(__name__)
        
        # Declare global variable upfront to avoid shadowing
        global HAS_LIBP2P
        
        # Initialize metadata dictionary - moved earlier to fix attribute access issue
        self.metadata = metadata or {}
        
        # Auto-install dependencies on first run if they're not already installed
        if not self.metadata.get("skip_dependency_check", False):
            if not self._check_and_install_dependencies():
                raise ImportError("libp2p is not available and automatic installation failed")

        # Store configuration
        self.role = role
        self.identity_path = identity_path
        self.bootstrap_peers = bootstrap_peers or []
        self.enable_mdns = enable_mdns and HAS_MDNS
        self.enable_hole_punching = enable_hole_punching and HAS_NAT_TRAVERSAL
        self.enable_relay_client = enable_relay and HAS_NAT_TRAVERSAL
        self.enable_relay_server = (
            (role in ["master", "worker"]) and enable_relay and HAS_NAT_TRAVERSAL
        )
        self.tiered_storage_manager = tiered_storage_manager

        # Default listen addresses if none provided
        if listen_addrs is None:
            listen_addrs = ["/ip4/0.0.0.0/tcp/0", "/ip4/0.0.0.0/udp/0/quic"]
        self.listen_addrs = listen_addrs

        # Component initialization
        self.host = None
        self.dht = None
        self.pubsub = None
        self.protocols = {}
        self.content_store = {}  # Local content store (CID -> bytes)
        self.content_metadata = {}  # Metadata for stored content
        self.protocol_handlers = {}  # Protocol handlers (protocol_id -> handler_function)
        self._running = False
        self._lock = threading.RLock()

        # Bitswap protocol specific data structures
        self.wantlist = {}  # Tracking wanted CIDs: {cid: {priority, requesters: [peer_ids]}}
        self.wantlist_lock = threading.RLock()  # For thread-safe access
        self.heat_scores = {}  # Track content "heat" for prioritization {cid: score}
        self.want_counts = {}  # Count of how many times a CID is wanted {cid: count}

        # Initialize components
        try:
            self._load_or_create_identity()

            # Create anyio task group for background tasks
            self._task_group = None
            
            # Flag to track if task group is initialized
            self._task_group_initialized = False
            
            # Set up components synchronously
            try:
                # Try with newer anyio version that supports timeout
                anyio.run(self._async_init, timeout=30)
            except TypeError:
                # Fallback for older anyio versions that don't support timeout
                anyio.run(self._async_init)

            # Connect to bootstrap peers
            if bootstrap_peers:
                for peer in bootstrap_peers:
                    self.connect_peer(peer)

            # Start discovery
            if enable_mdns:
                self.start_discovery()

            # Initialize empty known relays list
            self.known_relays = []

            self._running = True
            self.logger.info(f"libp2p peer initialized with ID: {self.get_peer_id()}")
        except Exception as e:
            self.logger.error(f"Failed to initialize libp2p peer: {str(e)}")
            # Clean up any resources that were initialized
            self.close()
            raise LibP2PError(f"Failed to initialize libp2p peer: {str(e)}")

    async def _init_task_group(self):
        """Initialize the task group for background tasks."""
        if not self._task_group_initialized:
            self._task_group = anyio.create_task_group()
            await self._task_group.__aenter__()
            self._task_group_initialized = True

    async def _async_init(self):
        """Initialize components asynchronously."""
        # Initialize the task group
        await self._init_task_group()
        
        # Initialize components in sequence
        await self._init_host_async()
        self._setup_protocols()
        await self._setup_dht_async()
        await self._setup_pubsub_async()

    async def _init_host_async(self):
        """Initialize the libp2p host asynchronously."""
        # Create libp2p host using our compatibility wrapper
        try:
            self.host = compatible_new_host(
                key_pair=self.identity,
                listen_addrs=self.listen_addrs,
                transport_opt=["/ip4/0.0.0.0/tcp/0"],
                muxer_opt=["/mplex/6.7.0"],
                sec_opt=["/secio/1.0.0"],
                peerstore_opt=None,
            )

            # Start the host (already might be done in compatible_new_host)
            try:
                if hasattr(self.host, 'get_network') and hasattr(self.host.get_network(), 'listen'):
                    self.host.get_network().listen()
            except Exception as e:
                self.logger.debug(f"Note: Network may already be listening: {e}")

            addresses = [str(addr) for addr in self.host.get_addrs()]
            self.logger.info(f"Peer {self.get_peer_id()} listening on: {', '.join(addresses)}")
        except Exception as e:
            self.logger.error(f"Failed to create host: {str(e)}")
            raise LibP2PError(f"Failed to create libp2p host: {str(e)}")

    async def _setup_dht_async(self):
        """Set up the DHT asynchronously."""
        # Determine DHT mode based on role
        dht_mode = "server" if self.role in ["master", "worker"] else "client"

        # Create and start Kademlia DHT
        self.dht = KademliaServer(
            peer_id=self.host.get_id(),
            endpoint=self.host,
            protocol_id="/ipfs/kad/1.0.0",
            ksize=20,
            alpha=ALPHA_VALUE,
        )

        # Bootstrap the DHT with connected peers
        await self._bootstrap_dht()

        self.logger.info(f"DHT initialized in {dht_mode} mode")

    async def _setup_pubsub_async(self):
        """Set up publish/subscribe asynchronously."""
        # Check if pubsub module is available
        if not HAS_PUBSUB:
            self.logger.warning("PubSub functionality disabled due to missing libp2p.tools.pubsub module")
            self.pubsub = None
            return
            
        # Initialize pubsub with GossipSub
        self.pubsub = pubsub_utils.create_pubsub(
            host=self.host,
            router_type="gossipsub",
            cache_size=128,
            strict_signing=True,
            sign_key=self.identity.private_key,
        )

        # Start pubsub
        await self.pubsub.start()

        # Subscribe to topics based on role
        if self.role == "master":
            # Master subscribes to worker updates and content announcements
            await self.pubsub.subscribe(
                topic_id="ipfs-kit/workers", handler=self._handle_worker_updates
            )

            await self.pubsub.subscribe(
                topic_id="ipfs-kit/content-announce", handler=self._handle_content_announcements
            )

            # Master also subscribes to relay announcements
            await self.pubsub.subscribe(
                topic_id="ipfs-kit/relay-announce", handler=self._handle_relay_announcements
            )

        elif self.role == "worker":
            # Worker subscribes to task assignments and content requests
            await self.pubsub.subscribe(
                topic_id="ipfs-kit/tasks", handler=self._handle_task_assignments
            )

            await self.pubsub.subscribe(
                topic_id="ipfs-kit/content-requests", handler=self._handle_content_requests
            )

            # Workers also subscribe to relay announcements
            await self.pubsub.subscribe(
                topic_id="ipfs-kit/relay-announce", handler=self._handle_relay_announcements
            )

        else:  # leecher
            # Leecher subscribes to content announcements
            await self.pubsub.subscribe(
                topic_id="ipfs-kit/content-announce", handler=self._handle_content_announcements
            )

            # Leechers also subscribe to relay announcements
            await self.pubsub.subscribe(
                topic_id="ipfs-kit/relay-announce", handler=self._handle_relay_announcements
            )

    def _load_or_create_identity(self):
        """Load existing identity or create a new one."""
        if not self.identity_path:
            # If no path provided, create an ephemeral identity
            # Use our compatibility module to create key pair
            self.identity = generate_key_pair()
            return

        # Expand path if needed
        self.identity_path = os.path.expanduser(self.identity_path)

        if os.path.exists(self.identity_path):
            # Load existing identity
            try:
                with open(self.identity_path, "rb") as f:
                    key_data = f.read()
                private_key = deserialize_private_key(key_data)
                self.identity = KeyPair(private_key, private_key.get_public_key())
                self.logger.debug(f"Loaded identity from {self.identity_path}")
            except Exception as e:
                self.logger.error(f"Failed to load identity: {str(e)}")
                # Fall back to creating a new identity using our compatibility module
                self.identity = generate_key_pair()
        else:
            # Create a new identity using our compatibility module
            self.identity = generate_key_pair()

            # Save identity to file
            try:
                os.makedirs(os.path.dirname(self.identity_path), exist_ok=True)
                with open(self.identity_path, "wb") as f:
                    key_data = serialize_private_key(self.identity.private_key)
                    f.write(key_data)
                self.logger.debug(f"Created and saved new identity to {self.identity_path}")
            except Exception as e:
                self.logger.error(f"Failed to save identity: {str(e)}")

    def _init_host(self):
        """Initialize the libp2p host with appropriate options."""
        # Create libp2p host using our compatibility wrapper
        try:
            self.host = compatible_new_host(
                key_pair=self.identity,
                listen_addrs=self.listen_addrs,
                transport_opt=["/ip4/0.0.0.0/tcp/0"],
                muxer_opt=["/mplex/6.7.0"],
                sec_opt=["/secio/1.0.0"],
                peerstore_opt=None,
            )

            # Start the host (already might be done in compatible_new_host)
            try:
                if hasattr(self.host, 'get_network') and hasattr(self.host.get_network(), 'listen'):
                    self.host.get_network().listen()
            except Exception as e:
                self.logger.debug(f"Note: Network may already be listening: {e}")

            addresses = [str(addr) for addr in self.host.get_addrs()]
            self.logger.info(f"Peer {self.get_peer_id()} listening on: {', '.join(addresses)}")
        except Exception as e:
            self.logger.error(f"Failed to create host: {str(e)}")
            raise LibP2PError(f"Failed to create libp2p host: {str(e)}")

    def _setup_protocols(self):
        """Set up protocol handlers based on node role."""
        # Common protocols for all roles
        self.register_protocol_handler(PROTOCOLS["IDENTITY"], self._handle_identity)
        self.register_protocol_handler(PROTOCOLS["PING"], self._handle_ping)

        # Role-specific protocols
        if self.role == "master":
            # Master has all protocols
            self.register_protocol_handler(PROTOCOLS["BITSWAP"], self._handle_bitswap)
            self.register_protocol_handler(PROTOCOLS["DAG_EXCHANGE"], self._handle_dag_exchange)
            self.register_protocol_handler(PROTOCOLS["FILE_EXCHANGE"], self._handle_file_exchange)
        elif self.role == "worker":
            # Worker has content exchange protocols
            self.register_protocol_handler(PROTOCOLS["BITSWAP"], self._handle_bitswap)
            self.register_protocol_handler(PROTOCOLS["FILE_EXCHANGE"], self._handle_file_exchange)
        else:  # leecher
            # Leecher has minimal protocols for basic content retrieval
            self.register_protocol_handler(PROTOCOLS["BITSWAP"], self._handle_bitswap)

    def _setup_dht(self):
        """Set up the DHT for content routing."""
        # Determine DHT mode based on role
        dht_mode = "server" if self.role in ["master", "worker"] else "client"

        # Create and start Kademlia DHT
        self.dht = KademliaServer(
            peer_id=self.host.get_id(),
            endpoint=self.host,
            protocol_id="/ipfs/kad/1.0.0",
            ksize=20,
            alpha=ALPHA_VALUE,
        )

        # Use the async version with anyio.run
        anyio.run(self._bootstrap_dht)

        self.logger.info(f"DHT initialized in {dht_mode} mode")

    async def _bootstrap_dht(self):
        """Bootstrap the DHT with connected peers and/or bootstrap nodes."""
        try:
            # Start with a delay to allow connections to establish
            await anyio.sleep(2)

            # Collect peer IDs from connected peers
            connected_peers = []
            for peer_id_obj in self.host.get_network().connections:
                connected_peers.append(peer_id_obj)

            # Bootstrap the DHT with connected peers
            if connected_peers:
                self.logger.info(f"Bootstrapping DHT with {len(connected_peers)} connected peers")
                await self.dht.bootstrap(connected_peers)
            else:
                self.logger.warning("No connected peers available for DHT bootstrapping")

            # Schedule periodic DHT refresh for better routing table maintenance
            if self._task_group_initialized:
                self._task_group.start_soon(self._periodic_dht_refresh)
            else:
                self.logger.warning("Task group not initialized, skipping periodic DHT refresh")

        except Exception as e:
            self.logger.error(f"DHT bootstrapping error: {str(e)}")

    async def _periodic_dht_refresh(self):
        """Periodically refresh the DHT routing table."""
        while self._running:
            try:
                # Refresh routing table every 15 minutes
                await anyio.sleep(900)  # 15 minutes

                # Skip if we're not running anymore
                if not self._running:
                    break

                self.logger.debug("Refreshing DHT routing table")
                await self.dht.bootstrap([])  # Empty list triggers just a refresh

            except anyio.get_cancelled_exc_class():
                # Handle task cancellation
                break
            except Exception as e:
                self.logger.error(f"DHT refresh error: {str(e)}")
                await anyio.sleep(60)  # Backoff on errors

    def _setup_pubsub(self):
        """Set up publish/subscribe for messaging."""
        # Check if pubsub module is available
        if not HAS_PUBSUB:
            self.logger.warning("PubSub functionality disabled due to missing libp2p.tools.pubsub module")
            self.pubsub = None
            return
            
        # Initialize pubsub with GossipSub
        self.pubsub = pubsub_utils.create_pubsub(
            host=self.host,
            router_type="gossipsub",
            cache_size=128,
            strict_signing=True,
            sign_key=self.identity.private_key,
        )

        # Start pubsub
        self.pubsub.start()

        # Subscribe to topics based on role
        if self.role == "master":
            # Master subscribes to worker updates and content announcements
            self.pubsub.subscribe(topic_id="ipfs-kit/workers", handler=self._handle_worker_updates)

            self.pubsub.subscribe(
                topic_id="ipfs-kit/content-announce", handler=self._handle_content_announcements
            )
        elif self.role == "worker":
            # Worker subscribes to task assignments and content requests
            self.pubsub.subscribe(topic_id="ipfs-kit/tasks", handler=self._handle_task_assignments)

            self.pubsub.subscribe(
                topic_id="ipfs-kit/content-requests", handler=self._handle_content_requests
            )
        else:  # leecher
            # Leecher subscribes to content announcements
            self.pubsub.subscribe(
                topic_id="ipfs-kit/content-announce", handler=self._handle_content_announcements
            )

    # Protocol Handlers

    async def _handle_identity(self, stream) -> None:
        """Handle identity protocol requests."""
        try:
            # Read request
            request_data = await stream.read()

            # Send identity information
            identity_info = {
                "id": self.get_peer_id(),
                "addresses": [str(addr) for addr in self.host.get_addrs()],
                "protocols": list(self.protocol_handlers.keys()),
                "role": self.role,
                "timestamp": time.time(),
            }

            await stream.write(json.dumps(identity_info).encode())

        except Exception as e:
            self.logger.error(f"Error handling identity request: {str(e)}")
        finally:
            await stream.close()

    async def _handle_ping(self, stream) -> None:
        """Handle ping protocol requests."""
        try:
            # Read ping data
            ping_data = await stream.read()

            # Send the same data back (pong)
            await stream.write(ping_data)

        except Exception as e:
            self.logger.error(f"Error handling ping: {str(e)}")
        finally:
            await stream.close()

    async def _handle_bitswap(self, stream) -> None:
        """Handle bitswap protocol requests for content exchange.

        This implementation follows a simplified version of the IPFS Bitswap protocol,
        with enhancements for tiered storage integration and role-specific optimizations.
        """
        try:
            # Read request
            request_data = await stream.read()
            request = json.loads(request_data.decode())

            # Process different bitswap message types
            if "type" not in request:
                request["type"] = "want"  # Default to legacy mode

            if request["type"] == "want":
                await self._handle_bitswap_want(stream, request)
            elif request["type"] == "have":
                await self._handle_bitswap_have(stream, request)
            elif request["type"] == "wantlist":
                await self._handle_bitswap_wantlist(stream, request)
            elif request["type"] == "cancel":
                await self._handle_bitswap_cancel(stream, request)
            else:
                # Unknown message type
                await stream.write(
                    json.dumps(
                        {"type": "error", "error": f"Unknown message type: {request['type']}"}
                    ).encode()
                )

        except Exception as e:
            self.logger.error(f"Error handling bitswap request: {str(e)}")
        finally:
            await stream.close()

    async def _handle_bitswap_want(self, stream, request):
        """Handle a bitswap 'want' request for content."""
        if "cid" not in request:
            await stream.write(
                json.dumps({"type": "error", "error": "Missing CID in want request"}).encode()
            )
            return

        cid = request["cid"]
        priority = request.get("priority", 1)  # Default normal priority
        requester = request.get("requester", str(stream.mplex_conn.peer_id))

        # Track request in wantlist for analytics (if master or worker)
        if self.role in ["master", "worker"]:
            self._track_want_request(cid, requester, priority)

        # Check if we have the content in our local store
        if cid in self.content_store:
            # We have the content in memory
            content = self.content_store[cid]

            # Update metadata
            if cid in self.content_metadata:
                self.content_metadata[cid]["last_accessed"] = time.time()
                if "access_count" in self.content_metadata[cid]:
                    self.content_metadata[cid]["access_count"] += 1
                else:
                    self.content_metadata[cid]["access_count"] = 1

            # Send response with metadata and content
            response = {
                "type": "block",
                "cid": cid,
                "metadata": {"size": len(content), "timestamp": time.time()},
            }

            # Send metadata first as JSON
            await stream.write(json.dumps(response).encode() + b"\n")

            # Then send the actual content
            await stream.write(content)
            self.logger.debug(f"Sent content for CID {cid} ({len(content)} bytes)")

            # Update stats for role-based optimization
            if self.role in ["master", "worker"]:
                self._update_content_heat(cid)

            return

        # Check if we have the content in tiered storage (integration point)
        stored_content = await self._get_from_tiered_storage(cid)
        if stored_content:
            # We have the content in tiered storage

            # Cache in memory if we're a master or worker and content is small enough
            if self.role in ["master", "worker"] and len(stored_content) < 10 * 1024 * 1024:  # 10MB
                self.store_bytes(cid, stored_content)

            # Send response with metadata and content
            response = {
                "type": "block",
                "cid": cid,
                "metadata": {
                    "size": len(stored_content),
                    "timestamp": time.time(),
                    "source": "tiered_storage",
                },
            }

            # Send metadata first as JSON
            await stream.write(json.dumps(response).encode() + b"\n")

            # Then send the actual content
            await stream.write(stored_content)
            self.logger.debug(
                f"Sent content for CID {cid} from tiered storage ({len(stored_content)} bytes)"
            )

            return

        # We don't have the content - try to find providers
        if self.role in ["master", "worker"]:
            # Masters and workers try to find other providers
            providers = await self._find_providers_async(cid, count=5, timeout=5)

            if providers:
                # Send provider info to requester
                response = {
                    "type": "providers",
                    "cid": cid,
                    "providers": providers,
                    "timestamp": time.time(),
                }
                await stream.write(json.dumps(response).encode())
                self.logger.debug(
                    f"Sent provider list for CID {cid} with {len(providers)} providers"
                )

                # Additionally, if we're a master, fetch the content proactively
                if self.role == "master" and priority > 1:  # Only for higher priority requests
                    # Start proactive fetching via task group if available, otherwise with anyio.run
                    if self._task_group_initialized:
                        self._task_group.start_soon(self._fetch_content_proactively, cid, providers)
                    else:
                        # Run without waiting for result
                        async def run_fetch():
                            await self._fetch_content_proactively(cid, providers)
                        
                        try:
                            anyio.run(run_fetch)
                        except Exception as e:
                            self.logger.error(f"Error in proactive fetch: {str(e)}")

                return

        # If we get here, we don't have the content and couldn't find providers
        await stream.write(
            json.dumps({"type": "error", "error": "Content not found", "cid": cid}).encode()
        )

    async def _handle_bitswap_have(self, stream, request):
        """Handle a bitswap 'have' query (do you have this block?)."""
        if "cid" not in request:
            await stream.write(
                json.dumps({"type": "error", "error": "Missing CID in have request"}).encode()
            )
            return

        cid = request["cid"]

        # Check memory storage
        have_in_memory = cid in self.content_store

        # Check tiered storage if not in memory
        have_in_storage = False
        if not have_in_memory:
            have_in_storage = await self._check_in_tiered_storage(cid)

        # Respond with availability
        response = {
            "type": "have",
            "cid": cid,
            "have": have_in_memory or have_in_storage,
            "location": "memory" if have_in_memory else "storage" if have_in_storage else None,
            "timestamp": time.time(),
        }

        # Include additional metadata if available
        if cid in self.content_metadata:
            response["metadata"] = self.content_metadata[cid]

        await stream.write(json.dumps(response).encode())

    async def _handle_bitswap_wantlist(self, stream, request):
        """Handle a request for our bitswap wantlist."""
        # Only masters and workers maintain wantlists
        if self.role not in ["master", "worker"]:
            await stream.write(
                json.dumps({"type": "wantlist", "wantlist": [], "timestamp": time.time()}).encode()
            )
            return

        # Get our current wantlist
        wantlist = self._get_current_wantlist()

        # Respond with our wantlist
        response = {"type": "wantlist", "wantlist": wantlist, "timestamp": time.time()}

        await stream.write(json.dumps(response).encode())

    async def _handle_bitswap_cancel(self, stream, request):
        """Handle a request to cancel a want."""
        if "cid" not in request:
            await stream.write(
                json.dumps({"type": "error", "error": "Missing CID in cancel request"}).encode()
            )
            return

        cid = request["cid"]
        requester = request.get("requester", str(stream.mplex_conn.peer_id))

        # Remove from wantlist if tracked
        self._remove_from_wantlist(cid, requester)

        # Acknowledge cancellation
        response = {"type": "cancel", "cid": cid, "success": True, "timestamp": time.time()}

        await stream.write(json.dumps(response).encode())

    async def _handle_dag_exchange(self, stream) -> None:
        """Handle DAG exchange protocol requests."""
        # Similar to bitswap but optimized for IPLD DAGs
        # Implementation will depend on specific DAG exchange protocol
        await stream.close()

    async def _handle_file_exchange(self, stream) -> None:
        """Handle file exchange protocol requests."""
        try:
            # Read request
            request_data = await stream.read()
            request = json.loads(request_data.decode())

            # Process request
            if "cid" in request and "range" in request:
                cid = request["cid"]
                range_start = request["range"].get("start", 0)
                range_end = request["range"].get("end", None)

                # Check if we have the content
                if cid in self.content_store:
                    content = self.content_store[cid]

                    # Apply range if specified
                    if range_end is not None:
                        content = content[range_start:range_end]
                    else:
                        content = content[range_start:]

                    # Send the content
                    await stream.write(content)
                    self.logger.debug(f"Sent file range for CID {cid}")
                else:
                    # We don't have the content
                    await stream.write(json.dumps({"error": "Content not found"}).encode())
            else:
                # Invalid request
                await stream.write(json.dumps({"error": "Invalid request"}).encode())

        except Exception as e:
            self.logger.error(f"Error handling file exchange request: {str(e)}")
        finally:
            await stream.close()

    # PubSub Handlers

    def _handle_worker_updates(self, msg):
        """Handle updates from worker nodes."""
        try:
            data = json.loads(msg["data"].decode())
            self.logger.debug(f"Worker update from {msg['from']}: {data}")
            # Process worker updates based on specific implementation needs
        except Exception as e:
            self.logger.error(f"Error handling worker update: {str(e)}")

    def _handle_content_announcements(self, msg):
        """Handle content announcements from peers."""
        try:
            data = json.loads(msg["data"].decode())
            self.logger.debug(f"Content announcement from {msg['from']}: {data}")

            if "cid" in data:
                # Store the announcement in metadata
                cid = data["cid"]
                provider = data.get("provider")

                if provider:
                    # Track the provider for this content
                    if "providers" not in self.content_metadata:
                        self.content_metadata["providers"] = {}

                    if cid not in self.content_metadata["providers"]:
                        self.content_metadata["providers"][cid] = []

                    # Add provider if not already in list
                    if provider not in self.content_metadata["providers"][cid]:
                        self.content_metadata["providers"][cid].append(provider)

                    # Store any additional metadata
                    if "metadata" not in self.content_metadata:
                        self.content_metadata["metadata"] = {}

                    if cid not in self.content_metadata["metadata"]:
                        self.content_metadata["metadata"][cid] = {}

                    # Extract and store relevant metadata
                    for key in ["size", "timestamp", "type", "name"]:
                        if key in data:
                            self.content_metadata["metadata"][cid][key] = data[key]

                # Update DHT if we're a master or worker
                if self.role in ["master", "worker"] and self.dht:
                    # Start a task to provide the CID to the DHT
                    if self._task_group_initialized:
                        # Use task group if available
                        async def provide_in_dht(content_id):
                            await self.dht.provide(content_id)
                        
                        self._task_group.start_soon(provide_in_dht, cid)
                    else:
                        # Fallback to anyio.run
                        async def provide_cid():
                            await self.dht.provide(cid)
                        try:
                            anyio.run(provide_cid)
                        except Exception as e:
                            self.logger.error(f"Error providing CID to DHT: {e}")

        except Exception as e:
            self.logger.error(f"Error handling content announcement: {str(e)}")

    def _handle_relay_announcements(self, msg):
        """Handle relay capability announcements."""
        try:
            data = json.loads(msg["data"].decode())
            self.logger.debug(f"Relay announcement from {msg['from']}: {data}")

            if "peer_id" in data and "addrs" in data and "capabilities" in data:
                peer_id = data["peer_id"]
                addrs = data["addrs"]
                capabilities = data["capabilities"]

                # Only process if this peer advertises relay capability
                if "relay" in capabilities:
                    # Store in known relays
                    if not hasattr(self, "known_relays"):
                        self.known_relays = []

                    # Format for storage
                    relay_info = {
                        "id": peer_id,
                        "addrs": addrs,
                        "protocols": data.get("protocols", []),
                        "timestamp": data.get("timestamp", time.time()),
                    }

                    # Check if already known
                    for i, relay in enumerate(self.known_relays):
                        if relay["id"] == peer_id:
                            # Update existing entry
                            self.known_relays[i] = relay_info
                            return

                    # Add new relay
                    self.known_relays.append(relay_info)
                    self.logger.info(f"Added relay peer: {peer_id}")

                    # Store best address for direct connection
                    for addr in addrs:
                        # Skip circuit relay addresses
                        if "/p2p-circuit/" not in addr:
                            relay_info["addr"] = addr
                            break

        except Exception as e:
            self.logger.error(f"Error handling relay announcement: {str(e)}")

    def _handle_task_assignments(self, msg):
        """Handle task assignments (for worker role)."""
        if self.role != "worker":
            return

        try:
            data = json.loads(msg["data"].decode())
            self.logger.debug(f"Task assignment from {msg['from']}: {data}")
            # Process task assignment based on specific implementation needs
        except Exception as e:
            self.logger.error(f"Error handling task assignment: {str(e)}")

    def _handle_content_requests(self, msg):
        """Handle content requests via pubsub."""
        try:
            data = json.loads(msg["data"].decode())
            self.logger.debug(f"Content request from {msg['from']}: {data}")

            if "cid" in data:
                cid = data["cid"]
                requester = data.get("requester")

                # Check if we have the content
                if cid in self.content_store:
                    # Respond directly to the requester if specified
                    if requester:
                        self._send_content_response(requester, cid, data.get("request_id"))

        except Exception as e:
            self.logger.error(f"Error handling content request: {str(e)}")

    # Public API

    def _check_and_install_dependencies(self):
        """
        Check if libp2p dependencies are available and attempt to install them if not.
        
        Returns:
            bool: True if dependencies are available or successfully installed, False otherwise
        """
        global HAS_LIBP2P, HAS_PUBSUB
        
        if not HAS_LIBP2P:
            self.logger.warning("libp2p is not available. Attempting to install dependencies...")
            
            # Try to install dependencies
            if install_dependencies():
                self.logger.info("Successfully installed libp2p dependencies")
                # Re-import necessary components after successful installation
                import libp2p
                # Handle missing pubsub_utils gracefully
                HAS_PUBSUB = True
                try:
                    import libp2p.tools.pubsub.utils as pubsub_utils
                except ImportError as e:
                    HAS_PUBSUB = False
                    self.logger.warning(f"libp2p.tools.pubsub module not available: {e}. PubSub functionality will be limited.")
                    
                # We already have compatible_new_host from our import above
                # from libp2p import new_host
                from libp2p.crypto.keys import KeyPair
                from libp2p.kademlia.network import KademliaServer
                HAS_LIBP2P = True
                return True
            else:
                self.logger.error("libp2p is not available and automatic installation failed. Install with pip install libp2p")
                return False
        
        return True
    
    def get_peer_id(self) -> str:
        """Get this peer's ID as a string."""
        if self.host:
            return str(self.host.get_id())
        return None

    def get_multiaddrs(self) -> List[str]:
        """Get this peer's multiaddresses as strings."""
        if self.host:
            return [str(addr) for addr in self.host.get_addrs()]
        return []

    def get_protocols(self) -> List[str]:
        """Get the list of supported protocols."""
        return list(self.protocol_handlers.keys())

    def get_dht_mode(self) -> str:
        """Get the DHT mode (server or client)."""
        if self.role in ["master", "worker"]:
            return "server"
        return "client"

    def connect_peer(self, peer_addr: str) -> bool:
        """Connect to a remote peer by multiaddress.

        Args:
            peer_addr: Multiaddress of the peer to connect to

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Parse the multiaddress
            from multiaddr import Multiaddr

            maddr = Multiaddr(peer_addr)

            # Extract peer ID from multiaddress
            peer_id_str = None
            for proto in maddr.protocols():
                if proto.code == 421:  # p2p protocol
                    peer_id_str = maddr.value_for_protocol(421)
                    break

            if not peer_id_str:
                self.logger.error(f"No peer ID found in multiaddress: {peer_addr}")
                return False

            # Create peer ID
            peer_id = PeerID.from_base58(peer_id_str)

            # Create peer info
            peer_info = PeerInfo(peer_id, [maddr])

            # Connect to peer using anyio run for sync usage of async function
            async def connect():
                await self.host.connect(peer_info)

            # Run with anyio directly
            try:
                anyio.run(connect)
                self.logger.info(f"Connected to peer: {peer_id_str}")
                return True
            except Exception as inner_e:
                self.logger.error(f"Connection failed: {str(inner_e)}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to connect to peer {peer_addr}: {str(e)}")
            return False

    def is_connected_to(self, peer_id: str) -> bool:
        """Check if connected to a specific peer.

        Args:
            peer_id: ID of the peer to check

        Returns:
            True if connected, False otherwise
        """
        try:
            peer_id_obj = PeerID.from_base58(peer_id)

            # Check connections
            connections = self.host.get_network().connections
            for conn_peer_id in connections:
                if str(conn_peer_id) == str(peer_id_obj):
                    return True

            return False

        except Exception as e:
            self.logger.error(f"Error checking connection: {str(e)}")
            return False

    def start_discovery(self, rendezvous_string: str = "ipfs-kit") -> bool:
        """Start peer discovery mechanisms.

        Args:
            rendezvous_string: Identifier for local network discovery

        Returns:
            True if discovery started, False otherwise
        """
        try:
            # Start mDNS discovery if available
            if self.enable_mdns and HAS_MDNS:
                # Create and start mDNS service
                self.mdns = mdns.MDNSDiscovery(self.host, service_tag=rendezvous_string)
                self.mdns.start()

                # Set up discovery notification handler
                async def handle_mdns_discovery(peer_info):
                    peer_id = peer_info.get("id")
                    addrs = peer_info.get("addrs", [])

                    if not peer_id or not addrs:
                        return

                    # Skip self
                    if peer_id == self.get_peer_id():
                        return

                    self.logger.info(f"mDNS discovered peer: {peer_id}")

                    # Try to connect if not already connected
                    if not self.is_connected_to(peer_id):
                        for addr in addrs:
                            addr_str = str(addr)
                            # Skip relay addresses initially
                            if "/p2p-circuit/" in addr_str:
                                continue

                            success = await self._connect_to_peer_async(peer_id, addr)
                            if success:
                                self.logger.info(f"Connected to mDNS peer: {peer_id}")
                                break

                # Register handler if available
                if hasattr(self.mdns, "register_peer_handler"):
                    self.mdns.register_peer_handler(handle_mdns_discovery)

                self.logger.info(f"Started mDNS discovery with service tag: {rendezvous_string}")

            # Connect to bootstrap peers
            for peer in self.bootstrap_peers:
                self.connect_peer(peer)

            # Set up pubsub discovery
            self._setup_pubsub_discovery(rendezvous_string)

            # Set up random walk discovery for better network connectivity
            self._setup_random_walk_discovery()

            return True

        except Exception as e:
            self.logger.error(f"Failed to start discovery: {str(e)}")
            return False

    def _setup_pubsub_discovery(self, rendezvous_string: str) -> None:
        """Set up pubsub-based peer discovery."""
        if not self.pubsub:
            return

        discovery_topic = f"ipfs-kit/discovery/{rendezvous_string}"

        # Subscribe to discovery topic
        self.pubsub.subscribe(topic_id=discovery_topic, handler=self._handle_discovery_message)

        # Announce ourselves
        self._announce_to_discovery_topic(discovery_topic)

        self.logger.info(f"Subscribed to discovery topic: {discovery_topic}")

    def _handle_discovery_message(self, msg):
        """Handle discovery messages from other peers."""
        try:
            # Parse announcement
            data = json.loads(msg["data"].decode())
            sender = msg.get("from")

            # Skip our own messages
            if sender == self.get_peer_id():
                return

            # Process peer announcement
            if "peer_id" in data and "addrs" in data:
                peer_id = data["peer_id"]
                addrs = data["addrs"]

                self.logger.debug(f"Received discovery announcement from {peer_id}")

                # Store peer in peerstore
                for addr_str in addrs:
                    try:
                        from multiaddr import Multiaddr

                        addr = Multiaddr(addr_str)
                        self.host.peerstore.add_addr(
                            PeerID.from_base58(peer_id), addr, 600  # 10 minutes validity
                        )
                    except Exception as e:
                        self.logger.debug(f"Error adding peer address: {str(e)}")

                # Try to connect if not already connected
                if not self.is_connected_to(peer_id) and self.role != "leecher":
                    # Schedule connection attempt via task group or anyio.run
                    if self._task_group_initialized:
                        self._task_group.start_soon(self._try_connect_to_discovered_peer, peer_id, addrs)
                    else:
                        # Run in background with anyio.run
                        try:
                            anyio.run(self._try_connect_to_discovered_peer, peer_id, addrs)
                        except Exception as e:
                            self.logger.error(f"Error connecting to discovered peer: {str(e)}")

        except json.JSONDecodeError:
            self.logger.debug("Received malformed discovery message")
        except Exception as e:
            self.logger.error(f"Error handling discovery message: {str(e)}")

    async def _try_connect_to_discovered_peer(self, peer_id, addrs):
        """Try to connect to a discovered peer."""
        # Skip connection if we're already at capacity and we're a leecher
        if self.role == "leecher" and len(self.host.get_network().connections) >= 10:
            return

        # Try each address
        for addr_str in addrs:
            try:
                # Skip relay addresses initially unless we're a master
                if "/p2p-circuit/" in addr_str and self.role != "master":
                    continue

                success = await self._connect_to_peer_async(peer_id, addr_str)
                if success:
                    self.logger.info(f"Connected to discovered peer: {peer_id}")
                    return

            except Exception as e:
                self.logger.debug(f"Error connecting to {peer_id} at {addr_str}: {str(e)}")

        # If direct connection failed and relay is enabled, try relayed connection
        if self.enable_relay_client and self.role != "leecher":
            # Find potential relays
            relays = self._find_relay_peers()

            # Try each relay
            for relay in relays:
                try:
                    relay_addr = relay["addr"]
                    success = await self.connect_via_relay(peer_id, relay_addr)
                    if success:
                        self.logger.info(f"Connected to {peer_id} via relay {relay['id']}")
                        return
                except Exception as e:
                    self.logger.debug(f"Error connecting via relay: {str(e)}")

    async def _connect_to_peer_async(self, peer_id, addr):
        """Connect to a peer asynchronously."""
        try:
            # Create peer ID
            peer_id_obj = PeerID.from_base58(peer_id)

            # Create multiaddr
            from multiaddr import Multiaddr

            maddr = Multiaddr(addr) if isinstance(addr, str) else addr

            # Create peer info
            peer_info = PeerInfo(peer_id_obj, [maddr])

            # Connect to peer
            await self.host.connect(peer_info)
            return True

        except Exception as e:
            self.logger.debug(f"Failed to connect to peer {peer_id}: {str(e)}")
            return False

    def _announce_to_discovery_topic(self, topic: str) -> None:
        """Announce our presence to the discovery topic."""
        if not self.pubsub:
            return

        # Create announcement
        announcement = {
            "peer_id": self.get_peer_id(),
            "addrs": self.get_multiaddrs(),
            "protocols": self.get_protocols(),
            "role": self.role,
            "timestamp": time.time(),
        }

        # Publish to discovery topic
        self.pubsub.publish(topic_id=topic, data=json.dumps(announcement).encode())

        self.logger.debug(f"Announced presence to discovery topic: {topic}")

        # Schedule via task group if available, otherwise use threading as fallback
        if self._task_group_initialized:
            async def scheduled_announcement():
                await anyio.sleep(300)  # 5 minutes
                self._announce_to_discovery_topic(topic)
            
            self._task_group.start_soon(scheduled_announcement)
        else:
            # Fallback to threading if task group not available
            threading.Timer(300, lambda: self._announce_to_discovery_topic(topic)).start()

    def _setup_random_walk_discovery(self) -> None:
        """Set up random walk discovery for better network connectivity."""
        # Only master and worker nodes perform random walks
        if self.role == "leecher":
            return

        # Start random walk thread
        self._random_walk_thread = threading.Thread(target=self._run_random_walk, daemon=True)
        self._random_walk_thread.start()

        self.logger.debug("Started random walk discovery")

    def _run_random_walk(self) -> None:
        """Run random walk discovery periodically."""
        # Wait for initial connections
        time.sleep(60)

        while self._running:
            try:
                # Sleep between walks
                time.sleep(1800)  # 30 minutes

                # Skip if we're not running anymore
                if not self._running:
                    break

                # Perform random walk with anyio
                anyio.run(self._perform_random_walk)

            except Exception as e:
                self.logger.error(f"Error in random walk: {str(e)}")
                time.sleep(60)  # Backoff on errors

    async def _perform_random_walk(self) -> None:
        """Perform a random walk on the DHT to discover peers."""
        if not self.dht:
            return

        self.logger.debug("Performing random walk discovery")

        try:
            # Generate a random key
            import random

            random_key = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=20))

            # Find closest peers to random key
            peers = await self.dht.find_peer(random_key)

            # Connect to discovered peers
            for peer_info in peers:
                peer_id = peer_info.get("id")

                # Skip self
                if peer_id == self.get_peer_id():
                    continue

                # Connect if not already connected
                if not self.is_connected_to(peer_id):
                    addrs = peer_info.get("addrs", [])
                    for addr in addrs:
                        try:
                            success = await self._connect_to_peer_async(peer_id, addr)
                            if success:
                                self.logger.debug(f"Connected to peer from random walk: {peer_id}")
                                break
                        except Exception as e:
                            self.logger.debug(f"Failed to connect: {str(e)}")

        except Exception as e:
            self.logger.error(f"Error performing random walk: {str(e)}")

    def _find_relay_peers(self) -> List[Dict[str, Any]]:
        """Find peers that can act as relays."""
        relays = []

        # Check if we've received relay announcements
        if hasattr(self, "known_relays"):
            relays.extend(self.known_relays)

        # Check manually configured relays
        for peer in self.bootstrap_peers:
            # Simple heuristic - assume bootstrap peers can relay
            relay_id = extract_peer_id_from_multiaddr(peer)
            if relay_id:
                relays.append({"id": relay_id, "addr": peer})

        return relays
        
    def publish_to_topic(self, topic_id: str, data: Union[str, bytes]) -> Dict[str, Any]:
        """Publish data to a GossipSub topic.
        
        Args:
            topic_id: The topic to publish to
            data: The data to publish (bytes or string)
            
        Returns:
            Dict with publication result
        """
        result = {
            "success": False,
            "operation": "publish_to_topic",
            "topic": topic_id,
            "timestamp": time.time(),
        }
        
        try:
            if not self.pubsub:
                result["error"] = "PubSub not available"
                result["error_type"] = "missing_pubsub"
                return result
                
            # Ensure data is bytes
            if isinstance(data, str):
                data_bytes = data.encode('utf-8')
            else:
                data_bytes = data
                
            # Handle sync and async APIs
            try:
                # Use anyio for async API
                async def publish_async():
                    await self.pubsub.publish(topic_id, data_bytes)
                    return True
                    
                # Run the publish operation
                if hasattr(self.pubsub.publish, "__code__") and "async" in self.pubsub.publish.__code__.co_flags:
                    # It's an async method, use anyio to run it
                    success = anyio.run(publish_async)
                else:
                    # It's a sync method, call directly
                    success = self.pubsub.publish(topic_id, data_bytes)
                    
                result["success"] = bool(success)
                return result
                
            except RuntimeError as e:
                if "no running event loop" in str(e):
                    # We're in a context where we can't create a new event loop
                    # Try to get or create an event loop in the current thread
                    try:
                        import anyio
                        loop = anyio.get_event_loop()
                        # Run the async function in this loop
                        success = loop.run_until_complete(publish_async())
                        result["success"] = bool(success)
                        return result
                    except Exception as inner_e:
                        result["error"] = f"Failed to publish in existing loop: {str(inner_e)}"
                        result["error_type"] = "event_loop_error"
                        self.logger.error(f"Error publishing to topic {topic_id}: {inner_e}")
                        return result
                else:
                    raise
                    
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            self.logger.error(f"Error publishing to topic {topic_id}: {e}")
            
        return result
            
    def subscribe_to_topic(self, topic_id: str, handler: Callable) -> Dict[str, Any]:
        """Subscribe to a GossipSub topic with a handler function.
        
        Args:
            topic_id: The topic to subscribe to
            handler: Function to call with received messages
            
        Returns:
            Dict with subscription result
        """
        result = {
            "success": False,
            "operation": "subscribe_to_topic",
            "topic": topic_id,
            "timestamp": time.time(),
        }
        
        try:
            if not self.pubsub:
                result["error"] = "PubSub not available"
                result["error_type"] = "missing_pubsub"
                return result
                
            # Check if we need to wrap the handler
            if not isinstance(handler, (types.FunctionType, types.MethodType)):
                result["error"] = f"Invalid handler type: {type(handler)}"
                result["error_type"] = "invalid_handler"
                return result
                
            # Handle both async and sync APIs
            try:
                # Use anyio for async API
                async def subscribe_async():
                    await self.pubsub.subscribe(topic_id, handler)
                    return True
                    
                # Run the subscribe operation
                if hasattr(self.pubsub.subscribe, "__code__") and "async" in self.pubsub.subscribe.__code__.co_flags:
                    # It's an async method, use anyio to run it
                    success = anyio.run(subscribe_async)
                else:
                    # It's a sync method, call directly
                    success = self.pubsub.subscribe(topic_id, handler)
                    
                result["success"] = bool(success)
                return result
                
            except RuntimeError as e:
                if "no running event loop" in str(e):
                    # We're in a context where we can't create a new event loop
                    # Try to get or create an event loop in the current thread
                    try:
                        import anyio
                        loop = anyio.get_event_loop()
                        # Run the async function in this loop
                        success = loop.run_until_complete(subscribe_async())
                        result["success"] = bool(success)
                        return result
                    except Exception as inner_e:
                        result["error"] = f"Failed to subscribe in existing loop: {str(inner_e)}"
                        result["error_type"] = "event_loop_error"
                        self.logger.error(f"Error subscribing to topic {topic_id}: {inner_e}")
                        return result
                else:
                    raise
                    
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            self.logger.error(f"Error subscribing to topic {topic_id}: {e}")
            
        return result
        
    def unsubscribe_from_topic(self, topic_id: str, handler: Optional[Callable] = None) -> Dict[str, Any]:
        """Unsubscribe from a GossipSub topic.
        
        Args:
            topic_id: The topic to unsubscribe from
            handler: Optional specific handler to unsubscribe (if None, unsubscribe from all handlers)
            
        Returns:
            Dict with unsubscription result
        """
        result = {
            "success": False,
            "operation": "unsubscribe_from_topic",
            "topic": topic_id,
            "timestamp": time.time(),
        }
        
        try:
            if not self.pubsub:
                result["error"] = "PubSub not available"
                result["error_type"] = "missing_pubsub"
                return result
                
            # Handle both async and sync APIs
            try:
                # Use anyio for async API
                async def unsubscribe_async():
                    await self.pubsub.unsubscribe(topic_id, handler)
                    return True
                    
                # Run the unsubscribe operation
                if hasattr(self.pubsub.unsubscribe, "__code__") and "async" in self.pubsub.unsubscribe.__code__.co_flags:
                    # It's an async method, use anyio to run it
                    success = anyio.run(unsubscribe_async)
                else:
                    # It's a sync method, call directly
                    success = self.pubsub.unsubscribe(topic_id, handler)
                    
                result["success"] = bool(success)
                return result
                
            except RuntimeError as e:
                if "no running event loop" in str(e):
                    # We're in a context where we can't create a new event loop
                    # Try to get or create an event loop in the current thread
                    try:
                        import anyio
                        loop = anyio.get_event_loop()
                        # Run the async function in this loop
                        success = loop.run_until_complete(unsubscribe_async())
                        result["success"] = bool(success)
                        return result
                    except Exception as inner_e:
                        result["error"] = f"Failed to unsubscribe in existing loop: {str(inner_e)}"
                        result["error_type"] = "event_loop_error"
                        self.logger.error(f"Error unsubscribing from topic {topic_id}: {inner_e}")
                        return result
                else:
                    raise
                    
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            self.logger.error(f"Error unsubscribing from topic {topic_id}: {e}")
            
        return result
        
    def get_topic_peers(self, topic_id: str) -> Dict[str, Any]:
        """Get peers subscribed to a topic.
        
        Args:
            topic_id: The topic to get peers for
            
        Returns:
            Dict with peer information
        """
        result = {
            "success": False,
            "operation": "get_topic_peers",
            "topic": topic_id,
            "timestamp": time.time(),
            "peers": []
        }
        
        try:
            if not self.pubsub:
                result["error"] = "PubSub not available"
                result["error_type"] = "missing_pubsub"
                return result
                
            # Check if the method exists
            if not hasattr(self.pubsub, "get_peers"):
                result["error"] = "get_peers method not available on pubsub implementation"
                result["error_type"] = "missing_method"
                return result
                
            # Call the method
            peers = self.pubsub.get_peers(topic_id)
            
            # Convert to list of strings if needed
            peer_list = [str(peer) for peer in peers] if peers else []
            
            result["success"] = True
            result["peers"] = peer_list
            result["count"] = len(peer_list)
            
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            self.logger.error(f"Error getting peers for topic {topic_id}: {e}")
            
        return result
        
    def list_topics(self) -> Dict[str, Any]:
        """List all topics we're subscribed to.
        
        Returns:
            Dict with topic information
        """
        result = {
            "success": False,
            "operation": "list_topics",
            "timestamp": time.time(),
            "topics": []
        }
        
        try:
            if not self.pubsub:
                result["error"] = "PubSub not available"
                result["error_type"] = "missing_pubsub"
                return result
                
            # Check if the method exists
            if hasattr(self.pubsub, "get_topics"):
                topics = self.pubsub.get_topics()
            elif hasattr(self.pubsub, "topics") and isinstance(self.pubsub.topics, (list, tuple, set)):
                topics = self.pubsub.topics
            elif hasattr(self.pubsub, "subscriptions") and isinstance(self.pubsub.subscriptions, dict):
                topics = list(self.pubsub.subscriptions.keys())
            else:
                result["error"] = "Cannot determine topics - method not available"
                result["error_type"] = "missing_method"
                return result
                
            # Convert to list of strings if needed
            topic_list = [str(topic) for topic in topics] if topics else []
            
            result["success"] = True
            result["topics"] = topic_list
            result["count"] = len(topic_list)
            
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            self.logger.error(f"Error listing topics: {e}")
            
        return result

    def enable_relay(self) -> bool:
        """Enable relay support for NAT traversal.

        Returns:
            True if relay enabled, False otherwise
        """
        if not HAS_NAT_TRAVERSAL:
            self.logger.warning("NAT traversal support not available")
            return False

        try:
            # Register relay protocol handler
            self.host.set_stream_handler("/libp2p/circuit/relay/0.1.0", self._handle_relay)

            # Set up client or server based on role
            if self.role in ["master", "worker"]:
                # Act as a relay server
                self.enable_relay_server = True
                self.logger.info("Relay server enabled")

                # Register additional relay discovery protocols
                self.host.set_stream_handler(
                    "/libp2p/circuit/relay/hop/1.0.0", self._handle_relay_hop
                )
                self.host.peerstore.add_supported_protocol(
                    self.host.get_id(), "/libp2p/circuit/relay/hop/1.0.0"
                )

                # Announce relay capability via pubsub
                self._announce_relay_capability()
            else:
                # Act as a relay client only
                self.enable_relay_client = True
                self.logger.info("Relay client enabled")

            return True

        except Exception as e:
            self.logger.error(f"Failed to enable relay: {str(e)}")
            return False

    def _announce_relay_capability(self):
        """Announce this node's relay capability to the network."""
        try:
            if not self.pubsub:
                return

            # Create announcement
            announcement = {
                "peer_id": self.get_peer_id(),
                "addrs": self.get_multiaddrs(),
                "timestamp": time.time(),
                "capabilities": ["relay"],
                "protocols": ["/libp2p/circuit/relay/0.1.0", "/libp2p/circuit/relay/hop/1.0.0"],
            }

            # Publish to relay discovery topic
            self.pubsub.publish(
                topic_id="ipfs-kit/relay-announce", data=json.dumps(announcement).encode()
            )

            self.logger.debug("Announced relay capability to the network")

            # Schedule periodic announcements
            threading.Timer(3600, self._announce_relay_capability).start()  # Announce every hour

        except Exception as e:
            self.logger.error(f"Error announcing relay capability: {str(e)}")

    async def _handle_relay(self, stream) -> None:
        """Handle relay protocol stream."""
        try:
            # Read relay request with timeout
            with anyio.fail_after(10.0):  # 10-second read timeout
                request_data = await stream.read()

            # Process based on whether we're a relay server or client
            if self.enable_relay_server:
                # Handle relay requests if we're a server
                try:
                    # Parse request data and set up relay circuit
                    # This would involve complex logic specific to the relay implementation
                    # For now, we just acknowledge the request

                    # Send success response with timeout
                    with anyio.fail_after(5.0):  # 5-second write timeout
                        await stream.write(json.dumps({"status": "success"}).encode())

                except Exception as e:
                    # Send error response with timeout
                    with anyio.fail_after(5.0):  # 5-second write timeout
                        await stream.write(json.dumps({"status": "error", "error": str(e)}).encode())
            else:
                # If we're not a relay server, reject the request
                with anyio.fail_after(5.0):  # 5-second write timeout
                    await stream.write(
                        json.dumps(
                            {"status": "error", "error": "This node is not a relay server"}
                        ).encode()
                    )

        except anyio.TimeoutError as e:
            self.logger.error(f"Timeout handling relay stream: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error handling relay stream: {str(e)}")
        finally:
            # Ensure stream is closed with timeout
            with anyio.move_on_after(2.0):  # Don't wait more than 2 seconds to close
                await stream.close()

    async def _handle_relay_hop(self, stream) -> None:
        """Handle relay hop protocol stream."""
        try:
            # Read hop request with timeout
            with anyio.fail_after(10.0):  # 10-second read timeout
                request_data = await stream.read()

            # Only master and worker nodes can serve as relay hops
            if self.role in ["master", "worker"] and self.enable_relay_server:
                # Process hop request
                # This would require specific implementation based on the circuit relay spec

                # Send acknowledgement with timeout
                with anyio.fail_after(5.0):  # 5-second write timeout
                    await stream.write(json.dumps({"status": "success"}).encode())
            else:
                # If we can't serve as a hop, reject the request with timeout
                with anyio.fail_after(5.0):  # 5-second write timeout
                    await stream.write(
                        json.dumps(
                            {"status": "error", "error": "This node cannot serve as a relay hop"}
                        ).encode()
                    )

        except anyio.TimeoutError as e:
            self.logger.error(f"Timeout handling relay hop: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error handling relay hop: {str(e)}")
        finally:
            # Ensure stream is closed with timeout
            with anyio.move_on_after(2.0):  # Don't wait more than 2 seconds to close
                await stream.close()

    async def connect_via_relay(self, peer_id: str, relay_addr: str) -> bool:
        """Connect to a peer through a relay.

        Args:
            peer_id: ID of the peer to connect to
            relay_addr: Multiaddress of the relay node

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Construct relay address
            # Format: /ip4/relay-ip/tcp/port/p2p/relay-peer-id/p2p-circuit/p2p/target-peer-id
            relay_peer_id = extract_peer_id_from_multiaddr(relay_addr)
            if not relay_peer_id:
                self.logger.error(f"Invalid relay address: {relay_addr}")
                return False

            # Construct the full circuit address
            circuit_addr = f"{relay_addr}/p2p-circuit/p2p/{peer_id}"

            # Create multiaddress
            from multiaddr import Multiaddr

            circuit_maddr = Multiaddr(circuit_addr)

            # Create peer info
            target_peer_id = PeerID.from_base58(peer_id)
            peer_info = PeerInfo(target_peer_id, [circuit_maddr])

            # Connect through relay
            await self.host.connect(peer_info)

            self.logger.info(f"Connected to {peer_id} via relay {relay_peer_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to connect via relay: {str(e)}")
            return False

    def is_relay_enabled(self) -> bool:
        """Check if relay support is enabled.

        Returns:
            True if relay enabled, False otherwise
        """
        # Implementation will depend on how relay is tracked
        return self.enable_relay_client or self.enable_relay_server

    def is_hole_punching_enabled(self) -> bool:
        """Check if hole punching is enabled.

        Returns:
            True if hole punching enabled, False otherwise
        """
        return self.enable_hole_punching

    def register_protocol_handler(self, protocol_id: str, handler: Callable) -> bool:
        """Register a handler for a specific protocol.

        Args:
            protocol_id: Protocol identifier string
            handler: Async function to handle protocol streams

        Returns:
            True if registration successful, False otherwise
        """
        try:
            # Register the protocol handler with the host
            self.host.set_stream_handler(protocol_id, handler)

            # Store in our protocol handlers dict
            self.protocol_handlers[protocol_id] = handler

            self.logger.debug(f"Registered handler for protocol: {protocol_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to register protocol handler: {str(e)}")
            return False

    def store_bytes(self, cid: str, data: bytes) -> bool:
        """Store content in the local content store.

        Args:
            cid: Content identifier
            data: Content data

        Returns:
            True if storage successful, False otherwise
        """
        try:
            with self._lock:
                self.content_store[cid] = data

                # Store metadata
                if cid not in self.content_metadata:
                    self.content_metadata[cid] = {}

                self.content_metadata[cid].update({"size": len(data), "stored_at": time.time()})

            self.logger.debug(f"Stored {len(data)} bytes for CID: {cid}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to store content: {str(e)}")
            return False

    def get_stored_bytes(self, cid: str) -> Optional[bytes]:
        """Get content from the local content store.

        Args:
            cid: Content identifier

        Returns:
            Content data or None if not found
        """
        with self._lock:
            return self.content_store.get(cid)

    def announce_content(self, cid: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Announce available content to the network.

        Args:
            cid: Content identifier
            metadata: Optional metadata about the content

        Returns:
            True if announcement successful, False otherwise
        """
        try:
            # Include default metadata if not provided
            if metadata is None:
                metadata = {}

            # Add announcement metadata
            announcement = {
                "cid": cid,
                "provider": self.get_peer_id(),
                "timestamp": time.time(),
                "addrs": self.get_multiaddrs(),
            }

            # Add user-provided metadata
            announcement.update(metadata)

            # Announce via DHT
            if self.dht:
                # Provide to DHT
                async def provide_content():
                    await self.dht.provide(cid)

                # Use task group if available, otherwise run with anyio
                if self._task_group_initialized:
                    self._task_group.start_soon(provide_content)
                else:
                    try:
                        # Run with anyio directly
                        anyio.run(provide_content)
                    except RuntimeError as e:
                        if "no running event loop" in str(e):
                            # We're in a context where we can't create a new event loop
                            # Try to get or create an event loop in the current thread
                            try:
                                import anyio
                                loop = anyio.get_event_loop()
                                # Run the coroutine in this loop
                                loop.run_until_complete(provide_content())
                            except Exception as inner_e:
                                self.logger.warning(f"Could not run provide_content in asyncio loop: {inner_e}")
                        else:
                            raise

            # Announce via pubsub
            if self.pubsub:
                self.publish_to_topic(
                    topic_id="ipfs-kit/content-announce", data=json.dumps(announcement).encode()
                )

            self.logger.debug(f"Announced content: {cid}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to announce content: {str(e)}")
            return False

    def find_providers(self, cid: str, count: int = 20, timeout: int = 60) -> List[Dict[str, Any]]:
        """Find providers for a specific content item.

        Args:
            cid: Content identifier to search for
            count: Maximum number of providers to find
            timeout: Maximum time to wait in seconds

        Returns:
            List of provider info dictionaries
        """
        providers = []

        try:
            # First check local metadata
            if "providers" in self.content_metadata and cid in self.content_metadata["providers"]:
                local_providers = self.content_metadata["providers"][cid]

                # Convert to provider info format
                for provider_id in local_providers:
                    providers.append(
                        {
                            "id": provider_id,
                            "addrs": [],  # Would need to retrieve addresses from peerstore
                        }
                    )

            # Then search DHT if we need more
            if len(providers) < count and self.dht:

                async def find_in_dht():
                    try:
                        # Use anyio timeout instead of asyncio
                        with anyio.fail_after(timeout):
                            dht_providers = await self.dht.get_providers(cid, count=count - len(providers))
                            
                            # Convert to provider info format and merge lists
                            dht_results = []
                            for provider in dht_providers:
                                provider_info = {
                                    "id": str(provider.peer_id),
                                    "addrs": [str(addr) for addr in provider.addrs],
                                }
                                
                                # Only add if not already in the list
                                if not any(p["id"] == provider_info["id"] for p in providers):
                                    dht_results.append(provider_info)
                                    
                            return dht_results
                    except TimeoutError:
                        self.logger.warning(f"DHT provider lookup timed out for {cid}")
                        return []

                # Run with anyio
                dht_results = anyio.run(find_in_dht)
                
                # Add results to providers list
                providers.extend(dht_results)

            return providers

        except Exception as e:
            self.logger.error(f"Error finding providers: {str(e)}")
            return providers  # Return whatever we found so far

    def request_content(self, cid: str, timeout: int = 30) -> Optional[bytes]:
        """Request content directly from connected peers.

        Args:
            cid: Content identifier to request
            timeout: Maximum time to wait in seconds

        Returns:
            Content data or None if not found
        """
        # First check local store
        local_content = self.get_stored_bytes(cid)
        if local_content:
            return local_content

        # Find providers
        providers = self.find_providers(cid)

        # Try requesting from each provider
        for provider in providers:
            try:
                provider_id = provider["id"]

                # Create request
                request = {
                    "cid": cid,
                    "requester": self.get_peer_id(),
                    "timestamp": time.time(),
                    "request_id": str(uuid.uuid4()),
                }

                # Open stream to provider with anyio
                async def request_from_peer():
                    try:
                        # Create stream
                        stream = await self.host.new_stream(
                            peer_id=PeerID.from_base58(provider_id),
                            protocol_id=PROTOCOLS["BITSWAP"],
                        )

                        # Send request
                        await stream.write(json.dumps(request).encode())

                        # Read response with anyio timeout
                        with anyio.fail_after(timeout):
                            response = await stream.read()

                        # Close stream
                        await stream.close()

                        # Check if response is an error message
                        try:
                            error_check = json.loads(response.decode())
                            if isinstance(error_check, dict) and "error" in error_check:
                                self.logger.warning(
                                    f"Provider returned error: {error_check['error']}"
                                )
                                return None
                        except json.JSONDecodeError:
                            # Not JSON, so it's probably the actual content
                            pass

                        return response
                    except StreamError as e:
                        self.logger.error(f"Stream error: {str(e)}")
                        return None
                    except TimeoutError:
                        self.logger.warning(f"Timeout requesting content from {provider_id}")
                        return None

                # Run with anyio
                try:
                    content = anyio.run(request_from_peer)

                    if content:
                        # Store for future use
                        self.store_bytes(cid, content)
                        return content

                except Exception as inner_e:
                    self.logger.warning(f"Error requesting content: {str(inner_e)}")
                    continue

            except Exception as e:
                self.logger.error(f"Error requesting from provider {provider['id']}: {str(e)}")
                continue

        # If we get here, we couldn't retrieve the content
        return None

    def receive_streamed_data(
        self, peer_id: str, cid: str, callback: Callable[[bytes], None]
    ) -> int:
        """Receive streamed data from a peer.

        Args:
            peer_id: Peer to receive from
            cid: Content identifier
            callback: Function to call with each chunk of data

        Returns:
            Total bytes received
        """
        total_bytes = 0

        try:
            # Create request
            request = {
                "cid": cid,
                "range": {"start": 0, "end": None},  # Full content
                "requester": self.get_peer_id(),
                "timestamp": time.time(),
                "request_id": str(uuid.uuid4()),
            }

            # Open stream to provider
            async def receive_stream():
                nonlocal total_bytes

                # Create stream
                stream = await self.host.new_stream(
                    peer_id=PeerID.from_base58(peer_id), protocol_id=PROTOCOLS["FILE_EXCHANGE"]
                )

                # Send request
                await stream.write(json.dumps(request).encode())

                # Read response in chunks
                chunk_size = 65536  # 64KB chunks
                while True:
                    chunk = await stream.read(chunk_size)
                    if not chunk:
                        break

                    # Call callback with chunk
                    callback(chunk)
                    total_bytes += len(chunk)

                # Close stream
                await stream.close()

                return total_bytes

            # Run with anyio
            try:
                total_bytes = anyio.run(receive_stream)
            except Exception as inner_e:
                self.logger.error(f"Error in stream receive: {str(inner_e)}")

            return total_bytes

        except Exception as e:
            self.logger.error(f"Error receiving streamed data: {str(e)}")
            return total_bytes

    def stream_data(self, callback: Callable[[bytes], None]) -> int:
        """Stream data to a callback function.

        This is a mock method to support testing; the real implementation
        would stream content from the content store.

        Args:
            callback: Function to call with each chunk of data

        Returns:
            Total bytes streamed
        """
        # Mock implementation for testing
        data = b"X" * 1024 * 1024  # 1MB of data
        chunk_size = 65536  # 64KB chunks

        for i in range(0, len(data), chunk_size):
            chunk = data[i : i + chunk_size]
            callback(chunk)

        return len(data)

    def _send_content_response(
        self, requester: str, cid: str, request_id: Optional[str] = None
    ) -> bool:
        """Send a content response to a specific requester.

        Args:
            requester: Peer ID of the requester
            cid: Content identifier
            request_id: Optional request identifier for correlation

        Returns:
            True if response sent, False otherwise
        """
        try:
            # Get the content
            content = self.get_stored_bytes(cid)
            if not content:
                return False

            # Open stream to requester
            async def send_response():
                try:
                    # Create stream
                    stream = await self.host.new_stream(
                        peer_id=PeerID.from_base58(requester), protocol_id=PROTOCOLS["BITSWAP"]
                    )

                    # Send content with timeout
                    with anyio.fail_after(30.0):  # 30-second timeout for sending
                        await stream.write(content)

                    # Close stream with timeout
                    with anyio.move_on_after(5.0):  # Don't wait more than 5 seconds to close
                        await stream.close()

                    return True
                except Exception as inner_e:
                    self.logger.error(f"Error in send_response: {str(inner_e)}")
                    return False

            # Run with anyio
            try:
                return anyio.run(send_response)
            except Exception as inner_e:
                self.logger.error(f"Error running send_response: {str(inner_e)}")
                return False

        except Exception as e:
            self.logger.error(f"Error sending content response: {str(e)}")
            return False

    # Bitswap related methods

    def _track_want_request(self, cid: str, requester: str, priority: int = 1) -> None:
        """Track a want request in our wantlist.

        Args:
            cid: Content identifier
            requester: Peer ID of requester
            priority: Priority of want (1-5, higher is more important)
        """
        with self.wantlist_lock:
            if cid not in self.wantlist:
                self.wantlist[cid] = {
                    "priority": priority,
                    "requesters": [],
                    "first_requested": time.time(),
                }

            # Update existing entry
            entry = self.wantlist[cid]

            # Use highest priority
            entry["priority"] = max(entry["priority"], priority)

            # Add requester if not already tracked
            if requester not in entry["requesters"]:
                entry["requesters"].append(requester)

            # Update last request time
            entry["last_requested"] = time.time()

            # Track count for analytics
            if cid not in self.want_counts:
                self.want_counts[cid] = 0
            self.want_counts[cid] += 1

    def _remove_from_wantlist(self, cid: str, requester: str) -> bool:
        """Remove a requester from a CID's wantlist entry.

        Args:
            cid: Content identifier
            requester: Peer ID of requester

        Returns:
            True if removed, False otherwise
        """
        with self.wantlist_lock:
            if cid not in self.wantlist:
                return False

            entry = self.wantlist[cid]

            if requester in entry["requesters"]:
                entry["requesters"].remove(requester)

                # If no more requesters, remove the entry
                if not entry["requesters"]:
                    del self.wantlist[cid]

                return True

            return False

    def _get_current_wantlist(self) -> List[Dict[str, Any]]:
        """Get our current wantlist in a serializable format.

        Returns:
            List of wantlist entries
        """
        result = []

        with self.wantlist_lock:
            for cid, entry in self.wantlist.items():
                # Create simplified entry for sharing
                result.append(
                    {
                        "cid": cid,
                        "priority": entry["priority"],
                        "requester_count": len(entry["requesters"]),
                    }
                )

        return result

    def _update_content_heat(self, cid: str) -> None:
        """Update the heat score for a content item based on access patterns.

        Args:
            cid: Content identifier
        """
        current_time = time.time()

        # Get or create heat score entry
        if cid not in self.heat_scores:
            self.heat_scores[cid] = {
                "score": 1.0,
                "last_accessed": current_time,
                "access_count": 1,
                "first_accessed": current_time,
            }
            return

        # Update existing entry
        entry = self.heat_scores[cid]
        entry["access_count"] += 1

        # Calculate time factors
        recency = 1.0 / (1.0 + (current_time - entry["last_accessed"]) / 3600)  # Decay by hour
        frequency = min(entry["access_count"], 100)  # Cap frequency factor
        age_days = (current_time - entry["first_accessed"]) / 86400
        age_boost = 1.0 + 0.1 * min(age_days, 30)  # 10% boost per day up to 30 days

        # Update score: combination of frequency, recency, and age
        entry["score"] = frequency * recency * age_boost
        entry["last_accessed"] = current_time

        # Trigger cache prioritization if very hot
        if entry["score"] > 10 and self.tiered_storage_manager:
            # Request promotion to faster storage tier
            # Schedule via task group if available, otherwise use anyio.run
            if self._task_group_initialized:
                self._task_group.start_soon(self._promote_content_to_faster_tier, cid)
            else:
                # Run in background without waiting for result
                async def run_promotion():
                    await self._promote_content_to_faster_tier(cid)
                
                try:
                    anyio.run(run_promotion)
                except Exception as e:
                    self.logger.error(f"Error promoting content: {str(e)}")

    async def _promote_content_to_faster_tier(self, cid: str) -> None:
        """Promote hot content to a faster storage tier.

        Args:
            cid: Content identifier
        """
        if not self.tiered_storage_manager:
            return

        try:
            # Only for master/worker roles
            if self.role not in ["master", "worker"]:
                return

            self.logger.debug(f"Promoting hot content {cid} to faster storage tier")

            # Request tier promotion from tiered storage manager
            # This is an integration point - implementation depends on tiered storage interface
            if hasattr(self.tiered_storage_manager, "promote"):
                await self._call_tiered_storage_async("promote", cid)

        except Exception as e:
            self.logger.error(f"Error promoting content to faster tier: {str(e)}")

    async def _get_from_tiered_storage(self, cid: str) -> Optional[bytes]:
        """Get content from tiered storage.

        Args:
            cid: Content identifier

        Returns:
            Content bytes or None if not found
        """
        if not self.tiered_storage_manager:
            return None

        try:
            # Try to get content from tiered storage
            content = await self._call_tiered_storage_async("get", cid)

            # Record access for heat tracking
            if content and self.role in ["master", "worker"]:
                self._update_content_heat(cid)

            return content

        except Exception as e:
            self.logger.error(f"Error getting content from tiered storage: {str(e)}")
            return None

    async def _check_in_tiered_storage(self, cid: str) -> bool:
        """Check if content exists in tiered storage.

        Args:
            cid: Content identifier

        Returns:
            True if content exists, False otherwise
        """
        if not self.tiered_storage_manager:
            return False

        try:
            # Check if content exists in tiered storage
            exists = await self._call_tiered_storage_async("exists", cid)
            return bool(exists)

        except Exception as e:
            self.logger.error(f"Error checking content in tiered storage: {str(e)}")
            return False

    async def _call_tiered_storage_async(self, method: str, *args, **kwargs) -> Any:
        """Call a method on the tiered storage manager asynchronously.

        This handles both async and sync implementations of the tiered storage manager.

        Args:
            method: Method name to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result of the method call
        """
        if not self.tiered_storage_manager or not hasattr(self.tiered_storage_manager, method):
            return None

        try:
            # Get the method
            func = getattr(self.tiered_storage_manager, method)

            # Check if it's an async method
            import inspect
            if inspect.iscoroutinefunction(func):
                # Directly await it
                return await func(*args, **kwargs)
            else:
                # Run sync method in thread to avoid blocking
                return await anyio.to_thread.run_sync(func, *args, **kwargs)

        except Exception as e:
            self.logger.error(f"Error calling tiered storage method {method}: {str(e)}")
            return None

    async def _find_providers_async(
        self, cid: str, count: int = 5, timeout: int = 5
    ) -> List[Dict[str, Any]]:
        """Find providers for content asynchronously.

        Args:
            cid: Content identifier
            count: Maximum number of providers to find
            timeout: Maximum time to wait in seconds

        Returns:
            List of provider info dictionaries
        """
        providers = []

        try:
            # First check local metadata
            if "providers" in self.content_metadata and cid in self.content_metadata["providers"]:
                local_providers = self.content_metadata["providers"][cid]

                # Get provider details if available
                for provider_id in local_providers:
                    if len(providers) >= count:
                        break

                    # Add basic provider info
                    providers.append({"id": provider_id, "source": "local_metadata"})

            # If we need more, check DHT
            if len(providers) < count and self.dht:
                try:
                    # Wait for DHT providers with anyio timeout
                    with anyio.fail_after(timeout):
                        dht_providers = await self.dht.get_providers(cid)

                        # Add unique providers from DHT
                        for provider in dht_providers:
                            if len(providers) >= count:
                                break

                            provider_id = str(provider.peer_id)

                            # Skip if already in results
                            if any(p["id"] == provider_id for p in providers):
                                continue

                            # Add provider info
                            providers.append(
                                {
                                    "id": provider_id,
                                    "addrs": [str(addr) for addr in provider.addrs],
                                    "source": "dht",
                                }
                            )

                except anyio.TimeoutError:
                    self.logger.debug(f"DHT provider lookup timed out for {cid}")
                    pass

            return providers

        except Exception as e:
            self.logger.error(f"Error finding providers asynchronously: {str(e)}")
            return providers

    async def _fetch_content_proactively(self, cid: str, providers: List[Dict[str, Any]]) -> bool:
        """Proactively fetch content from providers.

        Args:
            cid: Content identifier
            providers: List of providers to try

        Returns:
            True if content was fetched, False otherwise
        """
        # Only master and worker roles do proactive fetching
        if self.role not in ["master", "worker"]:
            return False

        # Skip if we already have the content
        if cid in self.content_store:
            return True

        # Check if already in tiered storage
        if await self._check_in_tiered_storage(cid):
            return True

        self.logger.debug(f"Proactively fetching content {cid} from {len(providers)} providers")

        # Try each provider in sequence
        for provider in providers:
            try:
                provider_id = provider["id"]

                # Skip self
                if provider_id == self.get_peer_id():
                    continue

                # Create request
                request = {
                    "type": "want",
                    "cid": cid,
                    "priority": 3,  # Medium-high priority
                    "requester": self.get_peer_id(),
                }

                # Get peer ID
                peer_id_obj = PeerID.from_base58(provider_id)

                # Open stream to provider
                try:
                    # Connect to provider if not already connected
                    if not self.is_connected_to(provider_id) and "addrs" in provider:
                        for addr in provider["addrs"]:
                            try:
                                await self._connect_to_peer_async(provider_id, addr)
                                break
                            except Exception:
                                continue

                    # Create stream
                    stream = await self.host.new_stream(
                        peer_id=peer_id_obj, protocol_id=PROTOCOLS["BITSWAP"]
                    )

                    # Send request
                    await stream.write(json.dumps(request).encode())

                    # Read response header (JSON metadata)
                    response_header = await stream.read_until(b"\n")

                    # Parse header
                    try:
                        header = json.loads(response_header.decode().strip())

                        # Check if it's a block response
                        if header.get("type") == "block":
                            # Read content data
                            content_size = header.get("metadata", {}).get("size", 0)
                            content = await stream.read(content_size)

                            # Store content
                            if content:
                                self.store_bytes(cid, content)
                                self.logger.info(
                                    f"Successfully fetched content {cid} from {provider_id}"
                                )
                                await stream.close()
                                return True
                    except json.JSONDecodeError:
                        # Not JSON, try treating as raw content
                        content = response_header
                        additional = await stream.read()
                        if additional:
                            content += additional

                        # Store if it seems like valid content
                        if len(content) > 0:
                            self.store_bytes(cid, content)
                            self.logger.info(f"Fetched raw content {cid} from {provider_id}")
                            await stream.close()
                            return True

                    # Close stream
                    await stream.close()

                except StreamError as e:
                    self.logger.error(f"Stream error with {provider_id}: {str(e)}")
                    continue

            except Exception as e:
                self.logger.error(f"Error fetching from provider {provider.get('id')}: {str(e)}")
                continue

        self.logger.warning(f"Failed to fetch content {cid} from any provider")
        return False

    def publish_to_topic(self, topic_id: str, data: Union[str, bytes]) -> Dict[str, Any]:
        """Publish data to a GossipSub topic.
        
        Args:
            topic_id: The topic to publish to
            data: The data to publish (bytes or string)
            
        Returns:
            Dict with publication result
        """
        result = {
            "success": False,
            "operation": "publish_to_topic",
            "timestamp": time.time(),
            "topic": topic_id
        }
        
        if not hasattr(self, "pubsub") or not self.pubsub:
            result["error"] = "PubSub not available"
            result["error_type"] = "missing_pubsub"
            return result
            
        # Ensure data is bytes
        if isinstance(data, str):
            data_bytes = data.encode('utf-8')
        else:
            data_bytes = data
            
        try:
            # Check if pubsub has a publish method that's either sync or async
            pubsub_publish = getattr(self.pubsub, "publish", None)
            
            if pubsub_publish:
                # Determine if it's an async method
                import inspect
                is_async = inspect.iscoroutinefunction(pubsub_publish)
                
                if is_async:
                    # Define async task
                    async def publish_async():
                        return await self.pubsub.publish(topic_id, data_bytes)
                    
                    # Try to get a running event loop or create a new one
                    try:
                        loop = anyio.get_event_loop()
                    except RuntimeError:
                        # No running event loop
                        loop = anyio.new_event_loop()
                        anyio.set_event_loop(loop)
                    
                    # Use anyio to run the task
                    try:
                        import anyio
                        publish_result = anyio.run(publish_async)
                        result["publish_result"] = publish_result
                        result["success"] = True
                    except Exception as e:
                        result["error"] = f"Error publishing to topic: {str(e)}"
                        self.logger.error(f"Error in async publish: {e}")
                else:
                    # Synchronous publish method
                    publish_result = self.pubsub.publish(topic_id, data_bytes)
                    result["publish_result"] = publish_result
                    result["success"] = True
            else:
                result["error"] = "No publish method available in PubSub object"
        except Exception as e:
            result["error"] = f"Unexpected error in publish_to_topic: {str(e)}"
            self.logger.error(f"Error publishing to topic {topic_id}: {e}")
            
        return result
        
    def subscribe_to_topic(self, topic_id: str, handler: Callable) -> Dict[str, Any]:
        """Subscribe to a GossipSub topic with a handler function.
        
        Args:
            topic_id: The topic to subscribe to
            handler: Function to handle incoming messages
            
        Returns:
            Dict with subscription result
        """
        result = {
            "success": False,
            "operation": "subscribe_to_topic",
            "timestamp": time.time(),
            "topic": topic_id
        }
        
        if not hasattr(self, "pubsub") or not self.pubsub:
            result["error"] = "PubSub not available"
            result["error_type"] = "missing_pubsub"
            return result
            
        try:
            # Check if pubsub has a subscribe method
            pubsub_subscribe = getattr(self.pubsub, "subscribe", None)
            
            if pubsub_subscribe:
                # Determine if it's an async method
                import inspect
                is_async = inspect.iscoroutinefunction(pubsub_subscribe)
                
                if is_async:
                    # Define async task
                    async def subscribe_async():
                        return await self.pubsub.subscribe(topic_id, handler)
                    
                    # Try to get a running event loop or create a new one
                    try:
                        loop = anyio.get_event_loop()
                    except RuntimeError:
                        # No running event loop
                        loop = anyio.new_event_loop()
                        anyio.set_event_loop(loop)
                    
                    # Use anyio to run the task
                    try:
                        import anyio
                        subscription = anyio.run(subscribe_async)
                        result["subscription"] = str(subscription)
                        result["success"] = True
                    except Exception as e:
                        result["error"] = f"Error subscribing to topic: {str(e)}"
                        self.logger.error(f"Error in async subscribe: {e}")
                else:
                    # Synchronous subscribe method
                    subscription = self.pubsub.subscribe(topic_id, handler)
                    result["subscription"] = str(subscription)
                    result["success"] = True
            else:
                result["error"] = "No subscribe method available in PubSub object"
        except Exception as e:
            result["error"] = f"Unexpected error in subscribe_to_topic: {str(e)}"
            self.logger.error(f"Error subscribing to topic {topic_id}: {e}")
            
        return result
        
    def unsubscribe_from_topic(self, topic_id: str, handler: Optional[Callable] = None) -> Dict[str, Any]:
        """Unsubscribe from a GossipSub topic.
        
        Args:
            topic_id: The topic to unsubscribe from
            handler: Optional specific handler to unsubscribe
            
        Returns:
            Dict with unsubscription result
        """
        result = {
            "success": False,
            "operation": "unsubscribe_from_topic",
            "timestamp": time.time(),
            "topic": topic_id
        }
        
        if not hasattr(self, "pubsub") or not self.pubsub:
            result["error"] = "PubSub not available"
            result["error_type"] = "missing_pubsub"
            return result
            
        try:
            # Check if pubsub has an unsubscribe method
            pubsub_unsubscribe = getattr(self.pubsub, "unsubscribe", None)
            
            if pubsub_unsubscribe:
                # Determine if it's an async method
                import inspect
                is_async = inspect.iscoroutinefunction(pubsub_unsubscribe)
                
                if is_async:
                    # Define async task
                    async def unsubscribe_async():
                        if handler:
                            return await self.pubsub.unsubscribe(topic_id, handler)
                        else:
                            return await self.pubsub.unsubscribe(topic_id)
                    
                    # Try to get a running event loop or create a new one
                    try:
                        loop = anyio.get_event_loop()
                    except RuntimeError:
                        # No running event loop
                        loop = anyio.new_event_loop()
                        anyio.set_event_loop(loop)
                    
                    # Use anyio to run the task
                    try:
                        import anyio
                        unsubscribe_result = anyio.run(unsubscribe_async)
                        result["unsubscribe_result"] = unsubscribe_result
                        result["success"] = True
                    except Exception as e:
                        result["error"] = f"Error unsubscribing from topic: {str(e)}"
                        self.logger.error(f"Error in async unsubscribe: {e}")
                else:
                    # Synchronous unsubscribe method
                    if handler:
                        unsubscribe_result = self.pubsub.unsubscribe(topic_id, handler)
                    else:
                        unsubscribe_result = self.pubsub.unsubscribe(topic_id)
                    result["unsubscribe_result"] = unsubscribe_result
                    result["success"] = True
            else:
                result["error"] = "No unsubscribe method available in PubSub object"
        except Exception as e:
            result["error"] = f"Unexpected error in unsubscribe_from_topic: {str(e)}"
            self.logger.error(f"Error unsubscribing from topic {topic_id}: {e}")
            
        return result
        
    def get_topic_peers(self, topic_id: str) -> Dict[str, Any]:
        """Get peers subscribed to a topic.
        
        Args:
            topic_id: The topic to get peers for
            
        Returns:
            Dict with peer information
        """
        result = {
            "success": False,
            "operation": "get_topic_peers",
            "timestamp": time.time(),
            "topic": topic_id,
            "peers": []
        }
        
        if not hasattr(self, "pubsub") or not self.pubsub:
            result["error"] = "PubSub not available"
            result["error_type"] = "missing_pubsub"
            return result
            
        try:
            # First try the direct method if available
            if hasattr(self.pubsub, "get_peers_subscribed"):
                peers = self.pubsub.get_peers_subscribed(topic_id)
                result["peers"] = [str(peer) for peer in peers]
                result["peer_count"] = len(result["peers"])
                result["success"] = True
                return result
                
            # Try alternate method name
            if hasattr(self.pubsub, "get_peers"):
                peers = self.pubsub.get_peers(topic_id)
                result["peers"] = [str(peer) for peer in peers]
                result["peer_count"] = len(result["peers"])
                result["success"] = True
                return result
                
            # Try to access topic subscribers directly if available
            if hasattr(self.pubsub, "topics") and topic_id in self.pubsub.topics:
                topic = self.pubsub.topics[topic_id]
                if hasattr(topic, "peers"):
                    peers = topic.peers
                    result["peers"] = [str(peer) for peer in peers]
                    result["peer_count"] = len(result["peers"])
                    result["success"] = True
                    return result
                    
            result["error"] = "Unable to get peers for topic - no supported method found"
        except Exception as e:
            result["error"] = f"Unexpected error in get_topic_peers: {str(e)}"
            self.logger.error(f"Error getting peers for topic {topic_id}: {e}")
            
        return result
        
    def list_topics(self) -> Dict[str, Any]:
        """List all topics we're subscribed to.
        
        Returns:
            Dict with topic information
        """
        result = {
            "success": False,
            "operation": "list_topics",
            "timestamp": time.time(),
            "topics": []
        }
        
        if not hasattr(self, "pubsub") or not self.pubsub:
            result["error"] = "PubSub not available"
            result["error_type"] = "missing_pubsub"
            return result
            
        try:
            # First try the direct method if available
            if hasattr(self.pubsub, "get_topics"):
                topics = self.pubsub.get_topics()
                result["topics"] = [str(topic) for topic in topics]
                result["topic_count"] = len(result["topics"])
                result["success"] = True
                return result
                
            # Try to access topics directly if available as a dict
            if hasattr(self.pubsub, "topics") and isinstance(self.pubsub.topics, dict):
                result["topics"] = list(self.pubsub.topics.keys())
                result["topic_count"] = len(result["topics"])
                result["success"] = True
                return result
                
            # Try to access subscriptions if available
            if hasattr(self.pubsub, "subscriptions"):
                if isinstance(self.pubsub.subscriptions, dict):
                    result["topics"] = list(self.pubsub.subscriptions.keys())
                elif isinstance(self.pubsub.subscriptions, list):
                    result["topics"] = self.pubsub.subscriptions
                else:
                    result["topics"] = []
                result["topic_count"] = len(result["topics"])
                result["success"] = True
                return result
                
            result["error"] = "Unable to list topics - no supported method found"
        except Exception as e:
            result["error"] = f"Unexpected error in list_topics: {str(e)}"
            self.logger.error(f"Error listing topics: {e}")
            
        return result
    
    def integrate_enhanced_dht_discovery(self):
        """Integrate the enhanced DHT discovery system with this peer.
        
        This adds the more advanced discovery capabilities from enhanced_dht_discovery.py,
        improving content routing, peer discovery, and network metrics.
        
        Returns:
            Dict with integration result
        """
        result = {
            "success": False,
            "operation": "integrate_enhanced_dht_discovery",
            "timestamp": time.time()
        }
        
        try:
            # Import the enhanced discovery classes
            from ipfs_kit_py.libp2p.enhanced_dht_discovery import EnhancedDHTDiscovery, ContentRoutingManager
            
            # Create the enhanced discovery component
            self.enhanced_discovery = EnhancedDHTDiscovery(
                libp2p_peer=self,
                role=self.role,
                bootstrap_peers=self.bootstrap_peers
            )
            
            # Create the content routing manager
            self.content_router = ContentRoutingManager(
                dht_discovery=self.enhanced_discovery,
                libp2p_peer=self
            )
            
            # Start the discovery system
            self.enhanced_discovery.start()
            
            result["success"] = True
            result["message"] = "Successfully integrated enhanced DHT discovery"
            self.logger.info("Enhanced DHT discovery integrated and started")
            
        except ImportError as e:
            result["error"] = f"Failed to import enhanced DHT discovery: {str(e)}"
            self.logger.error(f"Enhanced DHT discovery integration failed - import error: {e}")
        except Exception as e:
            result["error"] = f"Failed to integrate enhanced DHT discovery: {str(e)}"
            self.logger.error(f"Enhanced DHT discovery integration failed: {e}")
            
        return result

    def find_providers_enhanced(self, cid: str, count: int = 5, timeout: int = 30) -> Dict[str, Any]:
        """Find providers for content using the enhanced discovery system.
        
        This method uses the advanced provider tracking and reputation system to find 
        the most reliable sources for specific content.
        
        Args:
            cid: Content ID to find providers for
            count: Maximum number of providers to return
            timeout: Maximum time to wait in seconds
            
        Returns:
            Dict with provider information
        """
        result = {
            "success": False,
            "operation": "find_providers_enhanced",
            "timestamp": time.time(),
            "cid": cid,
            "providers": []
        }
        
        # First check if enhanced discovery is available
        if not hasattr(self, "enhanced_discovery") or not hasattr(self, "content_router"):
            # Try to integrate it
            integration_result = self.integrate_enhanced_dht_discovery()
            if not integration_result["success"]:
                result["error"] = "Enhanced discovery not available"
                # Fall back to regular find_providers
                try:
                    regular_result = self.find_providers(cid, count=count, timeout=timeout)
                    result["providers"] = regular_result.get("providers", [])
                    result["success"] = regular_result.get("success", False)
                    result["fallback_to_standard"] = True
                    return result
                except Exception as e:
                    result["error"] = f"Both enhanced and standard provider search failed: {str(e)}"
                    return result
        
        try:
            # Use the content router to find optimal providers
            future = self.content_router.find_content(
                cid, 
                options={
                    "timeout": timeout,
                    "max_providers": count
                }
            )
            
            # Wait for the result with timeout
            import anyio
            providers = future.result(timeout=timeout)
            
            if providers:
                result["providers"] = providers
                result["provider_count"] = len(providers)
                result["success"] = True
            else:
                result["error"] = "No providers found"
                
            return result
                
        except ImportError as e:
            result["error"] = f"Enhanced DHT discovery not available: {str(e)}"
            self.logger.error(f"Error in enhanced provider search - import error: {e}")
            return result
        except Exception as e:
            result["error"] = f"Error finding providers: {str(e)}"
            self.logger.error(f"Error in enhanced provider search: {e}")
            return result

    def close(self) -> None:
        """Close all connections and clean up resources."""
        if not self._running:
            return

        try:
            # Stop pubsub
            if self.pubsub:
                try:
                    self.pubsub.stop()
                except Exception as e:
                    self.logger.error(f"Error stopping pubsub: {str(e)}")

            # Close host (and all streams)
            if self.host:
                try:
                    # Close network connections
                    network = self.host.get_network()
                    
                    # Define async close function
                    async def close_connections():
                        for conn in network.connections.values():
                            try:
                                # Close with timeout to avoid hanging
                                with anyio.move_on_after(5.0):
                                    await conn.close()
                            except Exception as e:
                                self.logger.warning(f"Error closing connection: {str(e)}")
                    
                    # Run with anyio
                    anyio.run(close_connections)
                except Exception as e:
                    self.logger.error(f"Error closing host connections: {str(e)}")

            # Stop task group if it was initialized
            if self._task_group_initialized and self._task_group:
                try:
                    async def close_task_group():
                        await self._task_group.__aexit__(None, None, None)
                        self._task_group_initialized = False
                    
                    anyio.run(close_task_group)
                except Exception as e:
                    self.logger.error(f"Error closing task group: {str(e)}")

            # Stop mDNS discovery
            if hasattr(self, "mdns") and self.mdns:
                try:
                    self.mdns.stop()
                except Exception as e:
                    self.logger.error(f"Error stopping mDNS: {str(e)}")

            # Clear stores
            self.content_store.clear()
            self.content_metadata.clear()
            self.protocol_handlers.clear()
            self.wantlist.clear()
            self.heat_scores.clear()
            self.want_counts.clear()

            self._running = False
            self.logger.info("libp2p peer shut down")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {str(e)}")


# Helper functions
def publish_to_topic(self, topic_id: str, data: Union[str, bytes]) -> Dict[str, Any]:
    """Publish data to a GossipSub topic.
    
    Args:
        topic_id: The topic to publish to
        data: The data to publish (string or bytes)
        
    Returns:
        Dict with publish result
    """
    result = {
        "success": False,
        "operation": "publish_to_topic",
        "timestamp": time.time(),
        "topic": topic_id
    }
    
    if not self.pubsub:
        result["error"] = "PubSub is not available"
        return result
        
    # Ensure data is bytes
    if isinstance(data, str):
        data_bytes = data.encode('utf-8')
    else:
        data_bytes = data
        
    try:
        # Check if pubsub has a publish method that's either sync or async
        pubsub_publish = getattr(self.pubsub, "publish", None)
        
        if pubsub_publish:
            # Determine if it's an async method
            import inspect
            is_async = inspect.iscoroutinefunction(pubsub_publish)
            
            if is_async:
                # Define async task
                async def publish_async():
                    return await self.pubsub.publish(topic_id, data_bytes)
                
                # Try to get a running event loop or create a new one
                try:
                    loop = anyio.get_event_loop()
                except RuntimeError:
                    # No running event loop
                    loop = anyio.new_event_loop()
                    anyio.set_event_loop(loop)
                
                # Use anyio to run the task
                try:
                    publish_result = anyio.run(publish_async)
                    result["publish_result"] = publish_result
                    result["success"] = True
                except Exception as e:
                    result["error"] = f"Error publishing to topic: {str(e)}"
                    self.logger.error(f"Error in async publish: {e}")
            else:
                # Synchronous publish method
                publish_result = self.pubsub.publish(topic_id, data_bytes)
                result["publish_result"] = publish_result
                result["success"] = True
        else:
            result["error"] = "No publish method available in PubSub object"
    except Exception as e:
        result["error"] = f"Unexpected error in publish_to_topic: {str(e)}"
        self.logger.error(f"Error publishing to topic {topic_id}: {e}")
        
    return result
    
def subscribe_to_topic(self, topic_id: str, handler: Callable) -> Dict[str, Any]:
    """Subscribe to a GossipSub topic with a handler function.
    
    Args:
        topic_id: The topic to subscribe to
        handler: Function to handle incoming messages
        
    Returns:
        Dict with subscription result
    """
    result = {
        "success": False,
        "operation": "subscribe_to_topic",
        "timestamp": time.time(),
        "topic": topic_id
    }
    
    if not self.pubsub:
        result["error"] = "PubSub is not available"
        return result
        
    try:
        # Check if pubsub has a subscribe method
        pubsub_subscribe = getattr(self.pubsub, "subscribe", None)
        
        if pubsub_subscribe:
            # Determine if it's an async method
            import inspect
            is_async = inspect.iscoroutinefunction(pubsub_subscribe)
            
            if is_async:
                # Define async task
                async def subscribe_async():
                    return await self.pubsub.subscribe(topic_id, handler)
                
                # Try to get a running event loop or create a new one
                try:
                    loop = anyio.get_event_loop()
                except RuntimeError:
                    # No running event loop
                    loop = anyio.new_event_loop()
                    anyio.set_event_loop(loop)
                
                # Use anyio to run the task
                try:
                    subscription = anyio.run(subscribe_async)
                    result["subscription"] = str(subscription)
                    result["success"] = True
                except Exception as e:
                    result["error"] = f"Error subscribing to topic: {str(e)}"
                    self.logger.error(f"Error in async subscribe: {e}")
            else:
                # Synchronous subscribe method
                subscription = self.pubsub.subscribe(topic_id, handler)
                result["subscription"] = str(subscription)
                result["success"] = True
        else:
            result["error"] = "No subscribe method available in PubSub object"
    except Exception as e:
        result["error"] = f"Unexpected error in subscribe_to_topic: {str(e)}"
        self.logger.error(f"Error subscribing to topic {topic_id}: {e}")
        
    return result
    
def unsubscribe_from_topic(self, topic_id: str, handler: Optional[Callable] = None) -> Dict[str, Any]:
    """Unsubscribe from a GossipSub topic.
    
    Args:
        topic_id: The topic to unsubscribe from
        handler: Optional specific handler to unsubscribe
        
    Returns:
        Dict with unsubscription result
    """
    result = {
        "success": False,
        "operation": "unsubscribe_from_topic",
        "timestamp": time.time(),
        "topic": topic_id
    }
    
    if not self.pubsub:
        result["error"] = "PubSub is not available"
        return result
        
    try:
        # Check if pubsub has an unsubscribe method
        pubsub_unsubscribe = getattr(self.pubsub, "unsubscribe", None)
        
        if pubsub_unsubscribe:
            # Determine if it's an async method
            import inspect
            is_async = inspect.iscoroutinefunction(pubsub_unsubscribe)
            
            if is_async:
                # Define async task
                async def unsubscribe_async():
                    if handler:
                        return await self.pubsub.unsubscribe(topic_id, handler)
                    else:
                        return await self.pubsub.unsubscribe(topic_id)
                
                # Try to get a running event loop or create a new one
                try:
                    loop = anyio.get_event_loop()
                except RuntimeError:
                    # No running event loop
                    loop = anyio.new_event_loop()
                    anyio.set_event_loop(loop)
                
                # Use anyio to run the task
                try:
                    unsubscribe_result = anyio.run(unsubscribe_async)
                    result["unsubscribe_result"] = unsubscribe_result
                    result["success"] = True
                except Exception as e:
                    result["error"] = f"Error unsubscribing from topic: {str(e)}"
                    self.logger.error(f"Error in async unsubscribe: {e}")
            else:
                # Synchronous unsubscribe method
                if handler:
                    unsubscribe_result = self.pubsub.unsubscribe(topic_id, handler)
                else:
                    unsubscribe_result = self.pubsub.unsubscribe(topic_id)
                result["unsubscribe_result"] = unsubscribe_result
                result["success"] = True
        else:
            result["error"] = "No unsubscribe method available in PubSub object"
    except Exception as e:
        result["error"] = f"Unexpected error in unsubscribe_from_topic: {str(e)}"
        self.logger.error(f"Error unsubscribing from topic {topic_id}: {e}")
        
    return result
    
def get_topic_peers(self, topic_id: str) -> Dict[str, Any]:
    """Get peers subscribed to a topic.
    
    Args:
        topic_id: The topic to get peers for
        
    Returns:
        Dict with peer information
    """
    result = {
        "success": False,
        "operation": "get_topic_peers",
        "timestamp": time.time(),
        "topic": topic_id,
        "peers": []
    }
    
    if not self.pubsub:
        result["error"] = "PubSub is not available"
        return result
        
    try:
        # First try the direct method if available
        if hasattr(self.pubsub, "get_peers_subscribed"):
            peers = self.pubsub.get_peers_subscribed(topic_id)
            result["peers"] = [str(peer) for peer in peers]
            result["peer_count"] = len(result["peers"])
            result["success"] = True
            return result
            
        # Try alternate method name
        if hasattr(self.pubsub, "get_peers"):
            peers = self.pubsub.get_peers(topic_id)
            result["peers"] = [str(peer) for peer in peers]
            result["peer_count"] = len(result["peers"])
            result["success"] = True
            return result
            
        # Try to access topic subscribers directly if available
        if hasattr(self.pubsub, "topics") and topic_id in self.pubsub.topics:
            topic = self.pubsub.topics[topic_id]
            if hasattr(topic, "peers"):
                peers = topic.peers
                result["peers"] = [str(peer) for peer in peers]
                result["peer_count"] = len(result["peers"])
                result["success"] = True
                return result
                
        result["error"] = "Unable to get peers for topic - no supported method found"
    except Exception as e:
        result["error"] = f"Unexpected error in get_topic_peers: {str(e)}"
        self.logger.error(f"Error getting peers for topic {topic_id}: {e}")
        
    return result
    
def list_topics(self) -> Dict[str, Any]:
    """List all topics we're subscribed to.
    
    Returns:
        Dict with topic information
    """
    result = {
        "success": False,
        "operation": "list_topics",
        "timestamp": time.time(),
        "topics": []
    }
    
    if not self.pubsub:
        result["error"] = "PubSub is not available"
        return result
        
    try:
        # First try the direct method if available
        if hasattr(self.pubsub, "get_topics"):
            topics = self.pubsub.get_topics()
            result["topics"] = [str(topic) for topic in topics]
            result["topic_count"] = len(result["topics"])
            result["success"] = True
            return result
            
        # Try to access topics directly if available as a dict
        if hasattr(self.pubsub, "topics") and isinstance(self.pubsub.topics, dict):
            result["topics"] = list(self.pubsub.topics.keys())
            result["topic_count"] = len(result["topics"])
            result["success"] = True
            return result
            
        # Try to access subscriptions if available
        if hasattr(self.pubsub, "subscriptions"):
            if isinstance(self.pubsub.subscriptions, dict):
                result["topics"] = list(self.pubsub.subscriptions.keys())
            elif isinstance(self.pubsub.subscriptions, list):
                result["topics"] = self.pubsub.subscriptions
            else:
                result["topics"] = []
            result["topic_count"] = len(result["topics"])
            result["success"] = True
            return result
            
        result["error"] = "Unable to list topics - no supported method found"
    except Exception as e:
        result["error"] = f"Unexpected error in list_topics: {str(e)}"
        self.logger.error(f"Error listing topics: {e}")
        
    return result

def integrate_enhanced_dht_discovery(self):
    """Integrate the enhanced DHT discovery system with this peer.
    
    This adds the more advanced discovery capabilities from enhanced_dht_discovery.py,
    improving content routing, peer discovery, and network metrics.
    
    Returns:
        Dict with integration result
    """
    result = {
        "success": False,
        "operation": "integrate_enhanced_dht_discovery",
        "timestamp": time.time()
    }
    
    try:
        # Import the enhanced discovery classes
        from .libp2p.enhanced_dht_discovery import EnhancedDHTDiscovery, ContentRoutingManager
        
        # Create the enhanced discovery component
        self.enhanced_discovery = EnhancedDHTDiscovery(
            libp2p_peer=self,
            role=self.role,
            bootstrap_peers=self.bootstrap_peers
        )
        
        # Create the content routing manager
        self.content_router = ContentRoutingManager(
            dht_discovery=self.enhanced_discovery,
            libp2p_peer=self
        )
        
        # Start the discovery system
        self.enhanced_discovery.start()
        
        result["success"] = True
        result["message"] = "Successfully integrated enhanced DHT discovery"
        self.logger.info("Enhanced DHT discovery integrated and started")
        
    except ImportError as e:
        result["error"] = f"Failed to import enhanced DHT discovery: {str(e)}"
        self.logger.error(f"Enhanced DHT discovery integration failed - import error: {e}")
    except Exception as e:
        result["error"] = f"Failed to integrate enhanced DHT discovery: {str(e)}"
        self.logger.error(f"Enhanced DHT discovery integration failed: {e}")
        
    return result

def find_providers_enhanced(self, cid: str, count: int = 5, timeout: int = 30) -> Dict[str, Any]:
    """Find providers for content using the enhanced discovery system.
    
    This method uses the advanced provider tracking and reputation system to find 
    the most reliable sources for specific content.
    
    Args:
        cid: Content ID to find providers for
        count: Maximum number of providers to return
        timeout: Maximum time to wait in seconds
        
    Returns:
        Dict with provider information
    """
    result = {
        "success": False,
        "operation": "find_providers_enhanced",
        "timestamp": time.time(),
        "cid": cid,
        "providers": []
    }
    
    # First check if enhanced discovery is available
    if not hasattr(self, "enhanced_discovery") or not hasattr(self, "content_router"):
        # Try to integrate it
        integration_result = self.integrate_enhanced_dht_discovery()
        if not integration_result["success"]:
            result["error"] = "Enhanced discovery not available"
            # Fall back to regular find_providers
            try:
                regular_result = self.find_providers(cid, count=count, timeout=timeout)
                result["providers"] = regular_result.get("providers", [])
                result["success"] = regular_result.get("success", False)
                result["fallback_to_standard"] = True
                return result
            except Exception as e:
                result["error"] = f"Both enhanced and standard provider search failed: {str(e)}"
                return result
    
    try:
        # Use the content router to find optimal providers
        future = self.content_router.find_content(
            cid, 
            options={
                "timeout": timeout,
                "max_providers": count
            }
        )
        
        # Wait for the result with timeout
        providers = future.result(timeout=timeout)
        
        if providers:
            result["providers"] = providers
            result["provider_count"] = len(providers)
            result["success"] = True
        else:
            result["error"] = "No providers found"
            
        return result
            
    except ImportError as e:
        result["error"] = f"Enhanced DHT discovery not available: {str(e)}"
        self.logger.error(f"Error in enhanced provider search - import error: {e}")
        return result
    except Exception as e:
        result["error"] = f"Error finding providers: {str(e)}"
        self.logger.error(f"Error in enhanced provider search: {e}")
        return result

def extract_peer_id_from_multiaddr(multiaddr_str: str) -> Optional[str]:
    """Extract peer ID from a multiaddress string.

    Args:
        multiaddr_str: Multiaddress as string

    Returns:
        Peer ID or None if not found
    """
    try:
        # Check if multiaddr contains p2p/ipfs protocol
        parts = multiaddr_str.split("/")
        for i, part in enumerate(parts):
            if part in ("p2p", "ipfs") and i < len(parts) - 1:
                return parts[i + 1]

        return None

    except Exception:
        return None

# Add start method to IPFSLibp2pPeer class
def start(self) -> bool:
    """Start the libp2p peer if it's not already running.
    
    Returns:
        bool: True if successful, False otherwise
    """
    if self._running:
        self.logger.debug("LibP2P peer is already running")
        return True
        
    try:
        # We're already initialized in __init__, so just set running flag if needed
        self._running = True
        self.logger.info(f"LibP2P peer {self.get_peer_id()} started successfully")
        return True
    except Exception as e:
        self.logger.error(f"Failed to start libp2p peer: {str(e)}")
        return False

# Add the method to the class
IPFSLibp2pPeer.start = start
