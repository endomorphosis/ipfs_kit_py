"""
libp2p model for MCP integration.

This model provides access to direct peer-to-peer communication functionality
using libp2p, without requiring the full IPFS daemon. It enables peer discovery,
content routing, and direct content exchange between peers.
"""

import logging
import os
import sys
import time
import json
import uuid
from typing import Dict, List, Any, Optional, Union, Callable

# Configure logger
logger = logging.getLogger(__name__)

# Initialize enhanced_content_routing logger
enhanced_logger = logging.getLogger(__name__)

# Core IPFS Kit imports
from ipfs_kit_py.error import (
    IPFSConnectionError,
    IPFSTimeoutError,
    IPFSContentNotFoundError,
    IPFSError
)

# Import global module-level variables to avoid UnboundLocalError in class methods
# Define default values for when imports fail - these will be used if imports fail
HAS_LIBP2P = False

def check_dependencies():
    return False
    
def install_dependencies(force=False):
    return False

# Try to import from ipfs_kit_py.libp2p first (preferred source)
try:
    # Check libp2p availability from the module
    from ipfs_kit_py.libp2p import HAS_LIBP2P, check_dependencies, install_dependencies
except ImportError:
    # In case of import error, we'll use fallback sources
    logging.getLogger(__name__).warning("Failed to import ipfs_kit_py.libp2p dependencies")
    
    # Try to import directly from install_libp2p as first backup
    try:
        from install_libp2p import HAS_LIBP2P, check_dependencies, install_dependencies
    except ImportError:
        # Try to import from libp2p_peer as second backup (for mock testing)
        try:
            from ipfs_kit_py.libp2p_peer import HAS_LIBP2P
        except ImportError:
            # If all imports fail, we'll use the default values defined above
            logging.getLogger(__name__).warning("Failed to import all libp2p dependency sources")

# Ensure we have a valid HAS_LIBP2P variable in this module's global scope
# This prevents UnboundLocalError when accessing HAS_LIBP2P later
globals()['HAS_LIBP2P'] = HAS_LIBP2P

# Import libp2p peer if available
if HAS_LIBP2P:
    from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer, LibP2PError
    # Apply protocol extensions
    from ipfs_kit_py.libp2p import apply_protocol_extensions_to_instance
    # Import DHT discovery
    from ipfs_kit_py.libp2p import get_enhanced_dht_discovery
    EnhancedDHTDiscovery = get_enhanced_dht_discovery()
    
    # Import enhanced content routing
    try:
        from ipfs_kit_py.libp2p.enhanced_content_routing import (
            EnhancedContentRouter,
            RecursiveContentRouter,
            apply_to_peer
        )
        HAS_ENHANCED_ROUTING = True
        logger.debug("Enhanced content routing is available")
    except ImportError:
        logger.debug("Enhanced content routing is not available")
        HAS_ENHANCED_ROUTING = False

# Note: loggers are already defined at the top of the file

class LibP2PModel:
    # Class logger
    logger = logging.getLogger(__name__)
    """
    Model for libp2p-based peer-to-peer operations.
    
    This model provides access to direct peer-to-peer communication functionality
    using libp2p, without requiring the full IPFS daemon. It handles peer discovery,
    content routing, and direct content exchange.
    
    Attributes:
        libp2p_peer: The underlying IPFSLibp2pPeer instance
        cache_manager: Optional cache manager for improved performance
        credential_manager: Optional credential manager for secure communication
        operation_stats: Statistics about operations performed
    """

    def __init__(
        self,
        libp2p_peer_instance=None,
        cache_manager=None,
        credential_manager=None,
        resources=None,
        metadata=None,
    ):
        """
        Initialize the libp2p model.
        
        Args:
            libp2p_peer_instance: Optional pre-configured libp2p peer instance
            cache_manager: Optional cache manager for caching results
            credential_manager: Optional credential manager for secure access
            resources: Optional resources configuration dictionary
            metadata: Optional metadata dictionary
        """
        # Store configuration
        self.cache_manager = cache_manager
        self.credential_manager = credential_manager
        self.resources = resources or {}
        self.metadata = metadata or {}
        
        # Initialize operation statistics
        self.operation_stats = {
            "operation_count": 0,
            "failed_operations": 0,
            "start_time": time.time(),
            "peers_discovered": 0,
            "content_announced": 0,
            "content_retrieved": 0,
            "bytes_retrieved": 0,
            "bytes_sent": 0,
            "dht_lookups": 0,
            "dht_successful_lookups": 0,
            "mdns_discoveries": 0,
            "pubsub_messages_sent": 0,
            "pubsub_messages_received": 0,
            "connections_established": 0,
            "connection_failures": 0,
            "pubsub_subscriptions": 0,
            "protocol_negotiations": 0,
            "bitswap_exchanges": 0,
            "relay_connections": 0,
            "last_operation_time": time.time(),
        }
        
        # Initialize topic subscription handlers
        self.topic_handlers = {}
        
        # Use a dict to track active subscriptions
        self.active_subscriptions = {}
        
        # Dict to cache peer connection information
        self.peer_info_cache = {}
        
        # Check if libp2p is available
        libp2p_available = HAS_LIBP2P  # Local copy to avoid using the global directly
        
        # Re-check in case something changed since importing 
        if not libp2p_available:
            # Attempt to check dependencies again
            check_dependencies()
            # Get the result without modifying our module-level variable
            # We'll just use the result to decide whether to attempt installation
            libp2p_available = 'ipfs_kit_py.libp2p' in sys.modules and getattr(sys.modules['ipfs_kit_py.libp2p'], 'HAS_LIBP2P', False)
            
            if not libp2p_available and self.metadata.get("auto_install_dependencies", False):
                logger.info("Auto-installing libp2p dependencies...")
                success = install_dependencies()
                if success:
                    # Try to import dependencies again after installation
                    try:
                        import importlib
                        # If the module exists, reload it to get new imports
                        if 'ipfs_kit_py.libp2p' in sys.modules:
                            importlib.reload(sys.modules['ipfs_kit_py.libp2p'])
                            # Check if installation was successful (without using global)
                            if hasattr(sys.modules['ipfs_kit_py.libp2p'], 'HAS_LIBP2P') and sys.modules['ipfs_kit_py.libp2p'].HAS_LIBP2P:
                                logger.info("Successfully installed libp2p dependencies")
                                # We don't need to modify the module-level variable
                                # We'll just use the functions based on the imports below
                    except (ImportError, KeyError):
                        logger.warning("Failed to reload libp2p module after installation")
            elif not libp2p_available:
                logger.warning("libp2p dependencies are not available. P2P functionality will be limited.")
        
        # Initialize libp2p peer
        if libp2p_peer_instance:
            # Use provided instance
            self.libp2p_peer = libp2p_peer_instance
            logger.info("Using provided libp2p peer instance")
        elif libp2p_available:
            # Create new instance with role-based configuration
            try:
                # Extract configuration from metadata
                role = self.metadata.get("role", "leecher")
                enable_mdns = self.metadata.get("enable_mdns", True)
                enable_hole_punching = self.metadata.get("enable_hole_punching", False)
                enable_relay = self.metadata.get("enable_relay", True)
                identity_path = self.metadata.get("identity_path", os.path.expanduser("~/.ipfs_kit/libp2p/identity.key"))
                
                # Get bootstrap peers from configuration or use defaults
                bootstrap_peers = self.metadata.get("bootstrap_peers", [
                    "/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ",
                    "/ip4/104.236.179.241/tcp/4001/p2p/QmSoLPppuBtQSGwKDZT2M73ULpjvfd3aZ6ha4oFGL1KrGM",
                    "/ip4/104.236.76.40/tcp/4001/p2p/QmSoLV4Bbm51jM9C4gDYZQ9Cy3U6aXMJDAbzgu2fzaDs64",
                    "/ip4/128.199.219.111/tcp/4001/p2p/QmSoLSafTMBsPKadTEgaXctDQVcqN88CNLHXMkTNwMKPnu"
                ])
                
                # Create the libp2p peer instance
                self.libp2p_peer = IPFSLibp2pPeer(
                    identity_path=identity_path,
                    bootstrap_peers=bootstrap_peers,
                    role=role,
                    enable_mdns=enable_mdns,
                    enable_hole_punching=enable_hole_punching,
                    enable_relay=enable_relay,
                    metadata=self.metadata
                )
                
                # Apply protocol extensions to support additional protocols
                apply_protocol_extensions_to_instance(self.libp2p_peer)
                
                # Initialize enhanced DHT discovery if available
                if EnhancedDHTDiscovery and self.metadata.get("use_enhanced_dht", True):
                    self.dht_discovery = EnhancedDHTDiscovery(self.libp2p_peer)
                else:
                    self.dht_discovery = None
                
                logger.info(f"Initialized libp2p peer with ID: {self.libp2p_peer.get_peer_id()}")
                
                # If auto-start is enabled, start the peer
                if self.metadata.get("auto_start", True):
                    started = self.libp2p_peer.start()
                    if started:
                        logger.info("LibP2P peer started successfully")
                    else:
                        logger.warning("Failed to start LibP2P peer")
                
            except Exception as e:
                logger.error(f"Failed to create libp2p peer: {str(e)}")
                self.libp2p_peer = None
        else:
            # libp2p not available
            self.libp2p_peer = None
            logger.warning("libp2p functionality disabled due to missing dependencies")
    
    def _is_available_sync(self) -> bool:
        """
        Internal synchronous implementation to check if libp2p functionality is available.
        
        Returns:
            bool: True if libp2p is available, False otherwise
        """
        return HAS_LIBP2P and self.libp2p_peer is not None
        
    def is_available(self) -> bool:
        """
        Check if libp2p functionality is available.
        
        Returns:
            bool: True if libp2p is available, False otherwise
        """
        return self._is_available_sync()
        
    async def is_available(self) -> bool:
        """
        Async version of is_available for use with async controllers.
        
        Returns:
            bool: True if libp2p is available, False otherwise
        """
        # Use anyio to run the synchronous version in a thread
        # This ensures it returns a proper coroutine that can be awaited
        import anyio
        return await anyio.to_thread.run_sync(lambda: self._is_available_sync())
    
    def get_health(self) -> Dict[str, Any]:
        """
        Get health information about the libp2p peer.
        
        Returns:
            Dict containing health status information
        """
        self.operation_stats["operation_count"] += 1
        
        # Prepare health information
        result = {
            "success": False,
            "libp2p_available": HAS_LIBP2P,
            "peer_initialized": self.libp2p_peer is not None,
            "operation": "get_health",
            "timestamp": time.time()
        }
        
        # Return early if libp2p is not available
        if not self._is_available_sync():
            result["error"] = "libp2p is not available"
            result["error_type"] = "dependency_missing"
            self.operation_stats["failed_operations"] += 1
            return result
        
        try:
            # Get peer ID
            peer_id = self.libp2p_peer.get_peer_id()
            
            # Get listen addresses
            addrs = self.libp2p_peer.get_listen_addresses()
            
            # Get connected peers
            connected_peers = self.libp2p_peer.get_connected_peers()
            
            # Get DHT routing table size if available
            dht_peers = 0
            if self.libp2p_peer.dht:
                dht_peers = len(self.libp2p_peer.dht.routing_table.get_peers())
            
            # Add collected information to result
            result.update({
                "success": True,
                "peer_id": peer_id,
                "addresses": addrs,
                "connected_peers": len(connected_peers),
                "dht_peers": dht_peers,
                "protocols": list(self.libp2p_peer.protocol_handlers.keys()),
                "role": self.libp2p_peer.role
            })
            
            # Add stats to result
            result["stats"] = {
                "operation_count": self.operation_stats["operation_count"],
                "peers_discovered": self.operation_stats["peers_discovered"],
                "content_retrieved": self.operation_stats["content_retrieved"],
                "content_announced": self.operation_stats["content_announced"],
                "bytes_retrieved": self.operation_stats["bytes_retrieved"],
                "bytes_sent": self.operation_stats["bytes_sent"],
                "uptime": time.time() - self.operation_stats["start_time"]
            }
            
            # Cache result if cache manager is available
            if self.cache_manager:
                self.cache_manager.put(
                    "libp2p_health", 
                    result, 
                    ttl=60  # Cache for 60 seconds
                )
            
            return result
            
        except Exception as e:
            # Handle any errors
            logger.error(f"Error getting libp2p peer health: {str(e)}")
            result["error"] = f"Error getting health information: {str(e)}"
            result["error_type"] = "health_check_error"
            self.operation_stats["failed_operations"] += 1
            return result
            
    async def get_health(self) -> Dict[str, Any]:
        """
        Async version of get_health for use with async controllers.
        
        Returns:
            Dict containing health status information
        """
        # Define a helper function to avoid recursive call
        def _get_health_sync():
            # Call the original method directly to avoid recursion
            original_method = LibP2PModel.get_health.__func__
            return original_method(self)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_get_health_sync)
        
    async def discover_peers(self, discovery_method: str = "all", limit: int = 10) -> Dict[str, Any]:
        """
        Async version of discover_peers for use with async controllers.
        
        Args:
            discovery_method: Discovery method to use ("dht", "mdns", "bootstrap", "all")
            limit: Maximum number of peers to discover
            
        Returns:
            Dict containing discovered peers and status information
        """
        # Define a helper function to avoid parameter issues
        def _discover_peers_sync():
            return LibP2PModel.discover_peers(self, discovery_method, limit)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_discover_peers_sync)
        
    async def connect_peer(self, peer_addr: str) -> Dict[str, Any]:
        """
        Async version of connect_peer for use with async controllers.
        
        Args:
            peer_addr: Peer multiaddress to connect to
            
        Returns:
            Dict with connection status
        """
        # Define a helper function to avoid parameter issues
        def _connect_peer_sync():
            return LibP2PModel.connect_peer(self, peer_addr)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_connect_peer_sync)
        
    async def disconnect_peer(self, peer_id: str) -> Dict[str, Any]:
        """
        Async version of disconnect_peer for use with async controllers.
        
        Args:
            peer_id: Peer ID to disconnect from
            
        Returns:
            Dict with disconnection status
        """
        # Define a helper function to avoid parameter issues
        def _disconnect_peer_sync():
            return LibP2PModel.disconnect_peer(self, peer_id)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_disconnect_peer_sync)
        
    async def find_content(self, cid: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Async version of find_content for use with async controllers.
        
        Args:
            cid: Content ID to find
            timeout: Timeout in seconds for the operation
            
        Returns:
            Dict with content providers information
        """
        # Define a helper function to avoid parameter issues
        def _find_content_sync():
            return LibP2PModel.find_content(self, cid, timeout)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_find_content_sync)
        
    
    async def retrieve_content(self, cid: str, timeout: int = 60) -> Dict[str, Any]:
        """

        Async version of retrieve_content for use with async controllers.
        
        """
        # Define a helper function to avoid parameter issues
        def _retrieve_content_sync():
            return LibP2PModel.retrieve_content(self, cid, timeout)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_retrieve_content_sync)
        
    
    async def get_content(self, cid: str, timeout: int = 60) -> Dict[str, Any]:
        """

        Async version of get_content for use with async controllers.
        
        """
        # Define a helper function to avoid parameter issues
        def _get_content_sync():
            return LibP2PModel.get_content(self, cid, timeout)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_get_content_sync)
        
    
    async def announce_content(self, cid: str, data: Optional[bytes] = None) -> Dict[str, Any]:
        """

        Async version of announce_content for use with async controllers.
        
        """
        # Define a helper function to avoid parameter issues
        def _announce_content_sync():
            return LibP2PModel.announce_content(self, cid, data)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_announce_content_sync)
        
    
    async def get_connected_peers(self) -> Dict[str, Any]:
        """

        Async version of get_connected_peers for use with async controllers.
        
        """
        # Define a helper function to avoid parameter issues
        def _get_connected_peers_sync():
            return LibP2PModel.get_connected_peers(self)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(lambda: self.get_connected_peers())
        
    
    async def get_peer_info(self, peer_id: str) -> Dict[str, Any]:
        """

        Async version of get_peer_info for use with async controllers.
        
        """
        # Define a helper function to avoid parameter issues
        def _get_peer_info_sync():
            return LibP2PModel.get_peer_info(self, peer_id)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_get_peer_info_sync)
        
    
    async def reset(self) -> Dict[str, Any]:
        """

        Async version of reset for use with async controllers.
        
        """
        # Define a helper function to avoid parameter issues
        def _reset_sync():
            return LibP2PModel.reset(self)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_reset_sync)
        
    
    async def start(self) -> Dict[str, Any]:
        """

        Async version of start for use with async controllers.
        
        """
        # Define a helper function to avoid parameter issues
        def _start_sync():
            return LibP2PModel.start(self)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_start_sync)
        
    
    async def stop(self) -> Dict[str, Any]:
        """

        Async version of stop for use with async controllers.
        
        """
        # Define a helper function to avoid parameter issues
        def _stop_sync():
            return LibP2PModel.stop(self)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_stop_sync)
        
    
    async def dht_find_peer(self, peer_id: str, timeout: int = 30) -> Dict[str, Any]:
        """

        Async version of dht_find_peer for use with async controllers.
        
        """
        # Define a helper function to avoid parameter issues
        def _dht_find_peer_sync():
            return LibP2PModel.dht_find_peer(self, peer_id, timeout)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_dht_find_peer_sync)
        
    
    async def dht_provide(self, cid: str) -> Dict[str, Any]:
        """

        Async version of dht_provide for use with async controllers.
        
        """
        # Define a helper function to avoid parameter issues
        def _dht_provide_sync():
            return LibP2PModel.dht_provide(self, cid)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_dht_provide_sync)
        
    
    async def dht_find_providers(self, cid: str, timeout: int = 30, limit: int = 20) -> Dict[str, Any]:
        """

        Async version of dht_find_providers for use with async controllers.
        
        """
        # Define a helper function to avoid parameter issues
        def _dht_find_providers_sync():
            return LibP2PModel.dht_find_providers(self, cid, timeout, limit)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_dht_find_providers_sync)
        
    
    async def pubsub_publish(self, topic: str, message: Union[str, bytes, Dict[str, Any]]) -> Dict[str, Any]:
        """

        Async version of pubsub_publish for use with async controllers.
        
        """
        # Define a helper function to avoid parameter issues
        def _pubsub_publish_sync():
            return LibP2PModel.pubsub_publish(self, topic, message)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_pubsub_publish_sync)
        
    
    async def pubsub_subscribe(self, topic: str, handler_id: Optional[str] = None) -> Dict[str, Any]:
        """

        Async version of pubsub_subscribe for use with async controllers.
        
        """
        # Define a helper function to avoid parameter issues
        def _pubsub_subscribe_sync():
            return LibP2PModel.pubsub_subscribe(self, topic, handler_id)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_pubsub_subscribe_sync)
        
    
    async def pubsub_unsubscribe(self, topic: str, handler_id: Optional[str] = None) -> Dict[str, Any]:
        """

        Async version of pubsub_unsubscribe for use with async controllers.
        
        """
        # Define a helper function to avoid parameter issues
        def _pubsub_unsubscribe_sync():
            return LibP2PModel.pubsub_unsubscribe(self, topic, handler_id)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_pubsub_unsubscribe_sync)
        
    
    async def pubsub_get_topics(self) -> Dict[str, Any]:
        """

        Async version of pubsub_get_topics for use with async controllers.
        
        """
        # Define a helper function to avoid parameter issues
        def _pubsub_get_topics_sync():
            return LibP2PModel.pubsub_get_topics(self)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_pubsub_get_topics_sync)
        
    
    async def pubsub_get_peers(self, topic: Optional[str] = None) -> Dict[str, Any]:
        """

        Async version of pubsub_get_peers for use with async controllers.
        
        """
        # Define a helper function to avoid parameter issues
        def _pubsub_get_peers_sync():
            return LibP2PModel.pubsub_get_peers(self, topic)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_pubsub_get_peers_sync)
        
    
    async def register_message_handler(self, handler_id: str, protocol_id: str, description: Optional[str] = None) -> Dict[str, Any]:
        """
        Async version of register_message_handler for use with async controllers.
        
        Args:
            handler_id: Unique identifier for the handler
            protocol_id: Protocol ID to handle
            description: Optional description of the handler
            
        Returns:
            Dict with registration status
        """
        # Create a dummy handler function
        def dummy_handler(message):
            pass
        
        # Define a helper function to avoid parameter issues
        def _register_message_handler_sync():
            return LibP2PModel.register_message_handler(self, protocol_id, dummy_handler, handler_id)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_register_message_handler_sync)
        
    
    async def unregister_message_handler(self, handler_id: str, protocol_id: str) -> Dict[str, Any]:
        """

        Async version of unregister_message_handler for use with async controllers.
        
        Args:
            handler_id: ID of the handler to unregister
            protocol_id: Protocol ID the handler is registered for
            
        Returns:
            Dict with unregistration status
        
        """
        # Define a helper function to avoid parameter issues
        def _unregister_message_handler_sync():
            return LibP2PModel.unregister_message_handler(self, handler_id, protocol_id)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_unregister_message_handler_sync)
        
    
    async def list_message_handlers(self) -> Dict[str, Any]:
        """

        Async version of list_message_handlers for use with async controllers.
        
        """
        # Define a helper function to avoid parameter issues
        def _list_message_handlers_sync():
            return LibP2PModel.list_message_handlers(self)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_list_message_handlers_sync)
        
    async def publish_message(self, topic: str, message: str) -> Dict[str, Any]:
        """
        Async version of publish_message for use with async controllers.
        
        Args:
            topic: Topic to publish to
            message: Message to publish
            
        Returns:
            Dict with publish status
        """
        # We'll use the pubsub_publish method since they're essentially the same
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(LibP2PModel.pubsub_publish, self, topic, message)
        
    async def subscribe_topic(self, topic: str) -> Dict[str, Any]:
        """
        Async version of subscribe_topic for use with async controllers.
        
        Args:
            topic: Topic to subscribe to
            
        Returns:
            Dict with subscription status
        """
        # We'll use pubsub_subscribe without a handler_id
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(LibP2PModel.pubsub_subscribe, self, topic)
        
    async def unsubscribe_topic(self, topic: str) -> Dict[str, Any]:
        """
        Async version of unsubscribe_topic for use with async controllers.
        
        Args:
            topic: Topic to unsubscribe from
            
        Returns:
            Dict with unsubscription status
        """
        # We'll use pubsub_unsubscribe without a handler_id
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(LibP2PModel.pubsub_unsubscribe, self, topic)
        
    
    async def peer_info(self) -> Dict[str, Any]:
        """

        Async version of peer_info for use with async controllers.
        
        """
        # Define a helper function to avoid parameter issues
        def _peer_info_sync():
            return LibP2PModel.peer_info(self)
            
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_peer_info_sync)
    
    def discover_peers(self, discovery_method: str = "all", limit: int = 10) -> Dict[str, Any]:
        """
        Discover peers using various discovery mechanisms.
        
        Args:
            discovery_method: Discovery method to use ("dht", "mdns", "bootstrap", "all")
            limit: Maximum number of peers to discover
            
        Returns:
            Dict containing discovered peers and status information
        """
        self.operation_stats["operation_count"] += 1
        
        # Prepare result
        result = {
            "success": False,
            "operation": "discover_peers",
            "discovery_method": discovery_method,
            "timestamp": time.time(),
            "peers": []
        }
        
        # Return early if libp2p is not available
        if not self._is_available_sync():
            result["error"] = "libp2p is not available"
            result["error_type"] = "dependency_missing"
            self.operation_stats["failed_operations"] += 1
            return result
        
        try:
            peers = []
            
            # Perform discovery based on method
            if discovery_method in ["dht", "all"]:
                # Use DHT for discovery
                if self.dht_discovery:
                    # Use enhanced DHT discovery
                    dht_peers = self.dht_discovery.discover_peers(limit=limit)
                    peers.extend(dht_peers)
                elif self.libp2p_peer.dht:
                    # Use basic DHT discovery
                    self.operation_stats["dht_lookups"] += 1
                    dht_peers = self.libp2p_peer.discover_peers_dht(limit=limit)
                    peers.extend(dht_peers)
                    if dht_peers:
                        self.operation_stats["dht_successful_lookups"] += 1
            
            if discovery_method in ["mdns", "all"] and self.libp2p_peer.enable_mdns:
                # Use mDNS for local discovery
                mdns_peers = self.libp2p_peer.discover_peers_mdns(limit=limit)
                peers.extend(mdns_peers)
                if mdns_peers:
                    self.operation_stats["mdns_discoveries"] += len(mdns_peers)
            
            if discovery_method in ["bootstrap", "all"]:
                # Connect to bootstrap peers
                bootstrap_peers = self.libp2p_peer.bootstrap_peers
                for peer_addr in bootstrap_peers:
                    try:
                        success = self.libp2p_peer.connect_peer(peer_addr)
                        if success:
                            peers.append(peer_addr)
                    except Exception as e:
                        logger.debug(f"Failed to connect to bootstrap peer {peer_addr}: {str(e)}")
            
            # Remove duplicates and limit results
            unique_peers = list(set(peers))[:limit]
            
            # Update stats
            self.operation_stats["peers_discovered"] += len(unique_peers)
            
            # Set result
            result["success"] = True
            result["peers"] = unique_peers
            result["peer_count"] = len(unique_peers)
            
            # Cache result if cache manager is available
            if self.cache_manager:
                self.cache_manager.put(
                    f"libp2p_peers_{discovery_method}", 
                    result, 
                    ttl=60  # Cache for 60 seconds
                )
            
            return result
        
        except Exception as e:
            # Handle any errors
            logger.error(f"Error discovering peers: {str(e)}")
            result["error"] = f"Error discovering peers: {str(e)}"
            result["error_type"] = "discovery_error"
            self.operation_stats["failed_operations"] += 1
            return result
    
    def connect_peer(self, peer_addr: str) -> Dict[str, Any]:
        """
        Connect to a specific peer using multiaddr.
        
        Args:
            peer_addr: Peer multiaddress to connect to
            
        Returns:
            Dict with connection status
        """
        self.operation_stats["operation_count"] += 1
        
        # Prepare result
        result = {
            "success": False,
            "operation": "connect_peer",
            "peer_addr": peer_addr,
            "timestamp": time.time()
        }
        
        # Return early if libp2p is not available
        if not self._is_available_sync():
            result["error"] = "libp2p is not available"
            result["error_type"] = "dependency_missing"
            self.operation_stats["failed_operations"] += 1
            return result
        
        try:
            # Attempt to connect to peer
            success = self.libp2p_peer.connect_peer(peer_addr)
            
            if success:
                result["success"] = True
                
                # Get connected peer info
                try:
                    peer_info = self.libp2p_peer.get_peer_info(peer_addr)
                    result["peer_info"] = peer_info
                except Exception as e:
                    logger.debug(f"Connected to peer but couldn't get info: {str(e)}")
            else:
                result["error"] = f"Failed to connect to peer: {peer_addr}"
                result["error_type"] = "connection_failed"
                self.operation_stats["failed_operations"] += 1
            
            return result
            
        except Exception as e:
            # Handle any errors
            logger.error(f"Error connecting to peer {peer_addr}: {str(e)}")
            result["error"] = f"Error connecting to peer: {str(e)}"
            result["error_type"] = "connection_error"
            self.operation_stats["failed_operations"] += 1
            return result
    
    def find_content(self, cid: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Find content providers for a specific CID.
        
        Args:
            cid: Content ID to find
            timeout: Timeout in seconds for the operation
            
        Returns:
            Dict with content providers information
        """
        self.operation_stats["operation_count"] += 1
        
        # Prepare result
        result = {
            "success": False,
            "operation": "find_content",
            "cid": cid,
            "timestamp": time.time(),
            "providers": []
        }
        
        # Check cache first if available
        if self.cache_manager:
            cached_result = self.cache_manager.get(f"libp2p_find_content_{cid}")
            if cached_result:
                return cached_result
        
        # Return early if libp2p is not available
        if not self._is_available_sync():
            result["error"] = "libp2p is not available"
            result["error_type"] = "dependency_missing"
            self.operation_stats["failed_operations"] += 1
            return result
        
        try:
            # Find providers for CID
            providers = self.libp2p_peer.find_providers(cid, timeout=timeout)
            
            # Update result
            result["success"] = True
            result["providers"] = providers
            result["provider_count"] = len(providers)
            
            # Cache result if cache manager is available
            if self.cache_manager and providers:
                self.cache_manager.put(
                    f"libp2p_find_content_{cid}", 
                    result, 
                    ttl=300  # Cache for 5 minutes
                )
            
            return result
            
        except Exception as e:
            # Handle any errors
            logger.error(f"Error finding content providers for {cid}: {str(e)}")
            result["error"] = f"Error finding content providers: {str(e)}"
            result["error_type"] = "provider_lookup_error"
            self.operation_stats["failed_operations"] += 1
            return result
    
    def retrieve_content(self, cid: str, timeout: int = 60) -> Dict[str, Any]:
        """
        Retrieve content directly from peers using bitswap.
        
        Args:
            cid: Content ID to retrieve
            timeout: Timeout in seconds for the operation
            
        Returns:
            Dict with retrieved content information
        """
        self.operation_stats["operation_count"] += 1
        
        # Prepare result
        result = {
            "success": False,
            "operation": "retrieve_content",
            "cid": cid,
            "timestamp": time.time()
        }
        
        # Check cache first if available
        if self.cache_manager:
            cached_result = self.cache_manager.get(f"libp2p_content_info_{cid}")
            if cached_result and cached_result.get("success"):
                # Only return cached content info, not the actual data
                # This ensures we don't use stale content data from cache
                return {
                    "success": True,
                    "operation": "retrieve_content",
                    "cid": cid,
                    "timestamp": time.time(),
                    "size": cached_result.get("size", 0),
                    "from_cache": True,
                    "content_available": True
                }
        
        # Return early if libp2p is not available
        if not self._is_available_sync():
            result["error"] = "libp2p is not available"
            result["error_type"] = "dependency_missing"
            self.operation_stats["failed_operations"] += 1
            return result
        
        try:
            # Attempt to retrieve content
            content_data = self.libp2p_peer.retrieve_content(cid, timeout=timeout)
            
            if content_data:
                # Update stats
                self.operation_stats["content_retrieved"] += 1
                self.operation_stats["bytes_retrieved"] += len(content_data)
                
                # Update result
                result["success"] = True
                result["size"] = len(content_data)
                result["content_available"] = True
                
                # Store content in cache if available
                if self.cache_manager:
                    # Cache the content data
                    self.cache_manager.put(
                        f"libp2p_content_{cid}", 
                        content_data, 
                        ttl=3600  # Cache for 1 hour
                    )
                    
                    # Cache content info without the actual data
                    self.cache_manager.put(
                        f"libp2p_content_info_{cid}", 
                        {
                            "success": True,
                            "cid": cid,
                            "size": len(content_data),
                            "timestamp": time.time(),
                            "content_available": True
                        }, 
                        ttl=3600  # Cache for 1 hour
                    )
            else:
                result["error"] = f"Content not found: {cid}"
                result["error_type"] = "content_not_found"
                result["content_available"] = False
                self.operation_stats["failed_operations"] += 1
            
            return result
            
        except Exception as e:
            # Handle any errors
            logger.error(f"Error retrieving content {cid}: {str(e)}")
            result["error"] = f"Error retrieving content: {str(e)}"
            result["error_type"] = "retrieval_error"
            result["content_available"] = False
            self.operation_stats["failed_operations"] += 1
            return result
    
    def get_content(self, cid: str, timeout: int = 60) -> Dict[str, Any]:
        """
        Get content directly from peers and return the actual data.
        
        Args:
            cid: Content ID to retrieve
            timeout: Timeout in seconds for the operation
            
        Returns:
            Dict with content data and metadata
        """
        self.operation_stats["operation_count"] += 1
        
        # Prepare result
        result = {
            "success": False,
            "operation": "get_content",
            "cid": cid,
            "timestamp": time.time()
        }
        
        # Check cache first if available
        if self.cache_manager:
            cached_content = self.cache_manager.get(f"libp2p_content_{cid}")
            if cached_content:
                return {
                    "success": True,
                    "operation": "get_content",
                    "cid": cid,
                    "timestamp": time.time(),
                    "data": cached_content,
                    "size": len(cached_content),
                    "from_cache": True
                }
        
        # Return early if libp2p is not available
        if not self._is_available_sync():
            result["error"] = "libp2p is not available"
            result["error_type"] = "dependency_missing"
            self.operation_stats["failed_operations"] += 1
            return result
        
        try:
            # Attempt to retrieve content
            content_data = self.libp2p_peer.retrieve_content(cid, timeout=timeout)
            
            if content_data:
                # Update stats
                self.operation_stats["content_retrieved"] += 1
                self.operation_stats["bytes_retrieved"] += len(content_data)
                
                # Update result
                result["success"] = True
                result["data"] = content_data
                result["size"] = len(content_data)
                
                # Store content in cache if available
                if self.cache_manager:
                    self.cache_manager.put(
                        f"libp2p_content_{cid}", 
                        content_data, 
                        ttl=3600  # Cache for 1 hour
                    )
            else:
                result["error"] = f"Content not found: {cid}"
                result["error_type"] = "content_not_found"
                self.operation_stats["failed_operations"] += 1
            
            return result
            
        except Exception as e:
            # Handle any errors
            logger.error(f"Error retrieving content {cid}: {str(e)}")
            result["error"] = f"Error retrieving content: {str(e)}"
            result["error_type"] = "retrieval_error"
            self.operation_stats["failed_operations"] += 1
            return result
    
    def announce_content(self, cid: str, data: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Announce content availability to the network.
        
        Args:
            cid: Content ID to announce
            data: Optional content data to store locally
            
        Returns:
            Dict with announcement status
        """
        self.operation_stats["operation_count"] += 1
        
        # Prepare result
        result = {
            "success": False,
            "operation": "announce_content",
            "cid": cid,
            "timestamp": time.time()
        }
        
        # Return early if libp2p is not available
        if not self._is_available_sync():
            result["error"] = "libp2p is not available"
            result["error_type"] = "dependency_missing"
            self.operation_stats["failed_operations"] += 1
            return result
        
        try:
            # If data provided, store locally first
            if data is not None:
                self.libp2p_peer.store_content_locally(cid, data)
                result["content_stored"] = True
                
                # Update statistics
                self.operation_stats["bytes_sent"] += len(data)
                
                # Store in cache if available
                if self.cache_manager:
                    self.cache_manager.put(
                        f"libp2p_content_{cid}", 
                        data, 
                        ttl=3600  # Cache for 1 hour
                    )
            
            # Announce to network
            self.libp2p_peer.announce_content(cid)
            
            # Update result and stats
            result["success"] = True
            self.operation_stats["content_announced"] += 1
            
            return result
            
        except Exception as e:
            # Handle any errors
            logger.error(f"Error announcing content {cid}: {str(e)}")
            result["error"] = f"Error announcing content: {str(e)}"
            result["error_type"] = "announcement_error"
            self.operation_stats["failed_operations"] += 1
            return result
    
    def get_connected_peers(self) -> Dict[str, Any]:
        """
        Get information about currently connected peers.
        
        Returns:
            Dict with connected peers information
        """
        self.operation_stats["operation_count"] += 1
        
        # Prepare result
        result = {
            "success": False,
            "operation": "get_connected_peers",
            "timestamp": time.time(),
            "peers": []
        }
        
        # Return early if libp2p is not available
        if not self._is_available_sync():
            result["error"] = "libp2p is not available"
            result["error_type"] = "dependency_missing"
            self.operation_stats["failed_operations"] += 1
            return result
        
        try:
            # Get connected peers
            peers = self.libp2p_peer.get_connected_peers()
            
            # Update result
            result["success"] = True
            result["peers"] = peers
            result["peer_count"] = len(peers)
            
            # Cache result if cache manager is available
            if self.cache_manager:
                self.cache_manager.put(
                    "libp2p_connected_peers", 
                    result, 
                    ttl=30  # Cache for 30 seconds
                )
            
            return result
            
        except Exception as e:
            # Handle any errors
            logger.error(f"Error getting connected peers: {str(e)}")
            result["error"] = f"Error getting connected peers: {str(e)}"
            result["error_type"] = "peer_listing_error"
            self.operation_stats["failed_operations"] += 1
            return result
    
    def get_peer_info(self, peer_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific peer.
        
        Args:
            peer_id: Peer ID to get information about
            
        Returns:
            Dict with peer information
        """
        self.operation_stats["operation_count"] += 1
        
        # Prepare result
        result = {
            "success": False,
            "operation": "get_peer_info",
            "peer_id": peer_id,
            "timestamp": time.time()
        }
        
        # Return early if libp2p is not available
        if not self._is_available_sync():
            result["error"] = "libp2p is not available"
            result["error_type"] = "dependency_missing"
            self.operation_stats["failed_operations"] += 1
            return result
        
        try:
            # Get peer information
            peer_info = self.libp2p_peer.get_peer_info(peer_id)
            
            if peer_info:
                # Update result
                result["success"] = True
                result.update(peer_info)
            else:
                result["error"] = f"Peer not found: {peer_id}"
                result["error_type"] = "peer_not_found"
                self.operation_stats["failed_operations"] += 1
            
            return result
            
        except Exception as e:
            # Handle any errors
            logger.error(f"Error getting peer info for {peer_id}: {str(e)}")
            result["error"] = f"Error getting peer info: {str(e)}"
            result["error_type"] = "peer_info_error"
            self.operation_stats["failed_operations"] += 1
            return result
    
    def reset(self) -> Dict[str, Any]:
        """
        Reset the model, clearing caches and statistics.
        
        Returns:
            Dict with reset status
        """
        # Prepare result
        result = {
            "success": False,
            "operation": "reset",
            "timestamp": time.time()
        }
        
        try:
            # Reset operation stats
            old_start_time = self.operation_stats["start_time"]
            
            self.operation_stats = {
                "operation_count": 0,
                "failed_operations": 0,
                "start_time": old_start_time,
                "peers_discovered": 0,
                "content_announced": 0,
                "content_retrieved": 0,
                "bytes_retrieved": 0,
                "bytes_sent": 0,
                "dht_lookups": 0,
                "dht_successful_lookups": 0,
                "mdns_discoveries": 0,
                "last_operation_time": time.time(),
            }
            
            # Clear caches if cache manager is available
            if self.cache_manager:
                # Delete all libp2p related cache entries
                keys_to_delete = []
                
                # Collect keys to delete
                for key in self.cache_manager.list_keys():
                    if key.startswith("libp2p_"):
                        keys_to_delete.append(key)
                
                # Delete collected keys
                for key in keys_to_delete:
                    self.cache_manager.delete(key)
                
                result["cache_entries_cleared"] = len(keys_to_delete)
            
            # Update result
            result["success"] = True
            
            return result
            
        except Exception as e:
            # Handle any errors
            logger.error(f"Error resetting libp2p model: {str(e)}")
            result["error"] = f"Error resetting: {str(e)}"
            result["error_type"] = "reset_error"
            return result
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get operation statistics.
        
        Returns:
            Dict with operation statistics
        """
        stats = {
            "success": True,
            "operation": "get_stats",
            "timestamp": time.time(),
            "stats": self.operation_stats,
            "uptime": time.time() - self.operation_stats["start_time"]
        }
        
        # Get additional stats from libp2p peer if available
        if self._is_available_sync() and hasattr(self.libp2p_peer, "get_detailed_stats"):
            detailed_stats = self.libp2p_peer.get_detailed_stats()
            stats["detailed"] = detailed_stats
            
        return stats
        
    def start(self) -> Dict[str, Any]:
        """
        Start the libp2p peer if it's not already running.
        
        Returns:
            Dict with start status
        """
        self.operation_stats["operation_count"] += 1
        
        # Prepare result
        result = {
            "success": False,
            "operation": "start",
            "timestamp": time.time()
        }
        
        # Check if libp2p is available
        if not HAS_LIBP2P:
            # Re-check dependencies in case they changed since initialization
            check_dependencies()
            if not HAS_LIBP2P:
                result["error"] = "libp2p dependencies are not available"
                result["error_type"] = "dependency_missing"
                self.operation_stats["failed_operations"] += 1
                return result
        
        try:
            # If already initialized, just report success
            if self.libp2p_peer and self.libp2p_peer._running:
                result["success"] = True
                result["already_running"] = True
                return result
            
            # If we have a peer but it's not running, try to start it
            if self.libp2p_peer and not self.libp2p_peer._running:
                started = self.libp2p_peer.start()
                if started:
                    result["success"] = True
                    result["newly_started"] = True
                    return result
                else:
                    result["error"] = "Failed to start libp2p peer"
                    result["error_type"] = "start_error"
                    self.operation_stats["failed_operations"] += 1
                    return result
            
            # Otherwise, create a new peer instance
            # Extract configuration from metadata
            role = self.metadata.get("role", "leecher")
            enable_mdns = self.metadata.get("enable_mdns", True)
            enable_hole_punching = self.metadata.get("enable_hole_punching", False)
            enable_relay = self.metadata.get("enable_relay", True)
            identity_path = self.metadata.get("identity_path", os.path.expanduser("~/.ipfs_kit/libp2p/identity.key"))
            
            # Get bootstrap peers from configuration or use defaults
            bootstrap_peers = self.metadata.get("bootstrap_peers", [
                "/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ",
                "/ip4/104.236.179.241/tcp/4001/p2p/QmSoLPppuBtQSGwKDZT2M73ULpjvfd3aZ6ha4oFGL1KrGM",
                "/ip4/104.236.76.40/tcp/4001/p2p/QmSoLV4Bbm51jM9C4gDYZQ9Cy3U6aXMJDAbzgu2fzaDs64",
                "/ip4/128.199.219.111/tcp/4001/p2p/QmSoLSafTMBsPKadTEgaXctDQVcqN88CNLHXMkTNwMKPnu"
            ])
            
            # Create the libp2p peer instance
            self.libp2p_peer = IPFSLibp2pPeer(
                identity_path=identity_path,
                bootstrap_peers=bootstrap_peers,
                role=role,
                enable_mdns=enable_mdns,
                enable_hole_punching=enable_hole_punching,
                enable_relay=enable_relay,
                metadata=self.metadata
            )
            
            # Apply protocol extensions to support additional protocols
            if hasattr(self.libp2p_peer, "apply_protocol_extensions"):
                self.libp2p_peer.apply_protocol_extensions()
            
            # Initialize enhanced DHT discovery if available
            if EnhancedDHTDiscovery and self.metadata.get("use_enhanced_dht", True):
                self.dht_discovery = EnhancedDHTDiscovery(self.libp2p_peer)
            else:
                self.dht_discovery = None
            
            self.logger.info(f"Initialized libp2p peer with ID: {self.libp2p_peer.get_peer_id()}")
            
            # Start the peer explicitly
            if not self.libp2p_peer._running:
                started = self.libp2p_peer.start()
                if started:
                    result["success"] = True
                    result["newly_started"] = True
                else:
                    result["error"] = "Failed to start newly created libp2p peer"
                    result["error_type"] = "start_error"
                    self.operation_stats["failed_operations"] += 1
                    return result
            else:
                result["success"] = True
                result["newly_created"] = True
                
            return result
            
        except Exception as e:
            # Handle any errors
            self.logger.error(f"Error starting libp2p peer: {str(e)}")
            result["error"] = f"Error starting libp2p peer: {str(e)}"
            result["error_type"] = "start_error"
            self.operation_stats["failed_operations"] += 1
            return result
    
    def stop(self) -> Dict[str, Any]:
        """
        Stop the libp2p peer.
        
        Returns:
            Dict with stop status
        """
        self.operation_stats["operation_count"] += 1
        
        # Prepare result
        result = {
            "success": False,
            "operation": "stop",
            "timestamp": time.time()
        }
        
        # Return early if libp2p is not available
        if not self._is_available_sync():
            result["error"] = "libp2p is not available"
            result["error_type"] = "dependency_missing"
            self.operation_stats["failed_operations"] += 1
            return result
        
        try:
            # Stop the peer
            self.libp2p_peer.close()
            
            # Update result
            result["success"] = True
            
            return result
            
        except Exception as e:
            # Handle any errors
            self.logger.error(f"Error stopping libp2p peer: {str(e)}")
            result["error"] = f"Error stopping libp2p peer: {str(e)}"
            result["error_type"] = "stop_error"
            self.operation_stats["failed_operations"] += 1
            return result
    
    def dht_find_peer(self, peer_id: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Find a peer's addresses using the DHT.
        
        Args:
            peer_id: Peer ID to find
            timeout: Timeout in seconds
            
        Returns:
            Dict with peer information
        """
        self.operation_stats["operation_count"] += 1
        self.operation_stats["dht_lookups"] += 1
        
        # Prepare result
        result = {
            "success": False,
            "operation": "dht_find_peer",
            "peer_id": peer_id,
            "timestamp": time.time()
        }
        
        # Return early if libp2p is not available
        if not self._is_available_sync():
            result["error"] = "libp2p is not available"
            result["error_type"] = "dependency_missing"
            self.operation_stats["failed_operations"] += 1
            return result
        
        # Check if DHT is available
        if not self.libp2p_peer.dht:
            result["error"] = "DHT is not available"
            result["error_type"] = "dht_unavailable"
            self.operation_stats["failed_operations"] += 1
            return result
        
        try:
            # Use the DHT to find the peer
            addresses = self.libp2p_peer.find_peer_addresses(peer_id, timeout=timeout)
            
            if addresses:
                result["success"] = True
                result["addresses"] = addresses
                self.operation_stats["dht_successful_lookups"] += 1
            else:
                result["error"] = f"Peer not found: {peer_id}"
                result["error_type"] = "peer_not_found"
                self.operation_stats["failed_operations"] += 1
            
            return result
            
        except Exception as e:
            # Handle any errors
            self.logger.error(f"Error finding peer {peer_id}: {str(e)}")
            result["error"] = f"Error finding peer: {str(e)}"
            result["error_type"] = "dht_lookup_error"
            self.operation_stats["failed_operations"] += 1
            return result
    
    def dht_provide(self, cid: str) -> Dict[str, Any]:
        """
        Announce to the DHT that we are providing a CID.
        
        Args:
            cid: Content ID to announce
            
        Returns:
            Dict with announcement status
        """
        self.operation_stats["operation_count"] += 1
        
        # Prepare result
        result = {
            "success": False,
            "operation": "dht_provide",
            "cid": cid,
            "timestamp": time.time()
        }
        
        # Return early if libp2p is not available
        if not self._is_available_sync():
            result["error"] = "libp2p is not available"
            result["error_type"] = "dependency_missing"
            self.operation_stats["failed_operations"] += 1
            return result
        
        # Check if DHT is available
        if not self.libp2p_peer.dht:
            result["error"] = "DHT is not available"
            result["error_type"] = "dht_unavailable"
            self.operation_stats["failed_operations"] += 1
            return result
        
        try:
            # Announce content to the DHT
            success = self.libp2p_peer.provide_content(cid)
            
            if success:
                result["success"] = True
                self.operation_stats["content_announced"] += 1
            else:
                result["error"] = "Failed to announce content to DHT"
                result["error_type"] = "dht_provide_error"
                self.operation_stats["failed_operations"] += 1
            
            return result
            
        except Exception as e:
            # Handle any errors
            self.logger.error(f"Error announcing content {cid} to DHT: {str(e)}")
            result["error"] = f"Error announcing content to DHT: {str(e)}"
            result["error_type"] = "dht_provide_error"
            self.operation_stats["failed_operations"] += 1
            return result
    
    def dht_find_providers(self, cid: str, timeout: int = 30, limit: int = 20) -> Dict[str, Any]:
        """
        Find providers for a CID using the DHT.
        
        Args:
            cid: Content ID to find providers for
            timeout: Timeout in seconds
            limit: Maximum number of providers to return
            
        Returns:
            Dict with provider information
        """
        self.operation_stats["operation_count"] += 1
        self.operation_stats["dht_lookups"] += 1
        
        # Prepare result
        result = {
            "success": False,
            "operation": "dht_find_providers",
            "cid": cid,
            "timestamp": time.time(),
            "providers": []
        }
        
        # Return early if libp2p is not available
        if not self._is_available_sync():
            result["error"] = "libp2p is not available"
            result["error_type"] = "dependency_missing"
            self.operation_stats["failed_operations"] += 1
            return result
        
        # Check if DHT is available
        if not self.libp2p_peer.dht:
            result["error"] = "DHT is not available"
            result["error_type"] = "dht_unavailable"
            self.operation_stats["failed_operations"] += 1
            return result
        
        try:
            # Find providers using the DHT
            providers = self.libp2p_peer.find_providers(cid, timeout=timeout)
            
            # Limit number of providers if needed
            if providers and len(providers) > limit:
                providers = providers[:limit]
            
            result["success"] = True
            result["providers"] = providers
            result["provider_count"] = len(providers)
            
            if providers:
                self.operation_stats["dht_successful_lookups"] += 1
            
            return result
            
        except Exception as e:
            # Handle any errors
            self.logger.error(f"Error finding providers for {cid}: {str(e)}")
            result["error"] = f"Error finding providers: {str(e)}"
            result["error_type"] = "dht_lookup_error"
            self.operation_stats["failed_operations"] += 1
            return result
    
    def pubsub_publish(self, topic: str, message: Union[str, bytes, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Publish a message to a PubSub topic.
        
        Args:
            topic: Topic to publish to
            message: Message to publish (string, bytes, or JSON-serializable dict)
            
        Returns:
            Dict with publish status
        """
        self.operation_stats["operation_count"] += 1
        
        # Prepare result
        result = {
            "success": False,
            "operation": "pubsub_publish",
            "topic": topic,
            "timestamp": time.time()
        }
        
        # Return early if libp2p is not available
        if not self._is_available_sync():
            result["error"] = "libp2p is not available"
            result["error_type"] = "dependency_missing"
            self.operation_stats["failed_operations"] += 1
            return result
        
        # Check if PubSub is available
        if not self.libp2p_peer.pubsub:
            result["error"] = "PubSub is not available"
            result["error_type"] = "pubsub_unavailable"
            self.operation_stats["failed_operations"] += 1
            return result
        
        try:
            # Prepare message
            if isinstance(message, dict):
                message_data = json.dumps(message).encode("utf-8")
            elif isinstance(message, str):
                message_data = message.encode("utf-8")
            else:
                message_data = message
                
            # Publish the message
            success = self.libp2p_peer.publish_message(topic, message_data)
            
            if success:
                result["success"] = True
                self.operation_stats["pubsub_messages_sent"] += 1
            else:
                result["error"] = "Failed to publish message"
                result["error_type"] = "pubsub_publish_error"
                self.operation_stats["failed_operations"] += 1
            
            return result
            
        except Exception as e:
            # Handle any errors
            self.logger.error(f"Error publishing to topic {topic}: {str(e)}")
            result["error"] = f"Error publishing message: {str(e)}"
            result["error_type"] = "pubsub_publish_error"
            self.operation_stats["failed_operations"] += 1
            return result
    
    def pubsub_subscribe(self, topic: str, handler_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Subscribe to a PubSub topic.
        
        Args:
            topic: Topic to subscribe to
            handler_id: Optional ID to associate with this subscription
            
        Returns:
            Dict with subscription status
        """
        self.operation_stats["operation_count"] += 1
        
        # Generate a handler ID if not provided
        if handler_id is None:
            handler_id = f"handler_{uuid.uuid4()}"
        
        # Prepare result
        result = {
            "success": False,
            "operation": "pubsub_subscribe",
            "topic": topic,
            "handler_id": handler_id,
            "timestamp": time.time()
        }
        
        # Return early if libp2p is not available
        if not self._is_available_sync():
            result["error"] = "libp2p is not available"
            result["error_type"] = "dependency_missing"
            self.operation_stats["failed_operations"] += 1
            return result
        
        # Check if PubSub is available
        if not self.libp2p_peer.pubsub:
            result["error"] = "PubSub is not available"
            result["error_type"] = "pubsub_unavailable"
            self.operation_stats["failed_operations"] += 1
            return result
        
        try:
            # Add subscription to our tracking
            if topic not in self.active_subscriptions:
                self.active_subscriptions[topic] = {}
            
            # Create a message handler that will forward to registered handlers
            def message_handler(message):
                # Store message in cache if available
                if self.cache_manager:
                    cache_key = f"libp2p_pubsub_message_{topic}_{message['seqno'].hex()}"
                    self.cache_manager.put(cache_key, message, ttl=3600)
                
                # Update stats
                self.operation_stats["pubsub_messages_received"] += 1
                
                # Try to decode as JSON if not binary data
                try:
                    message_data = message["data"]
                    message_text = message_data.decode("utf-8")
                    try:
                        message_json = json.loads(message_text)
                        message["data_json"] = message_json
                    except json.JSONDecodeError:
                        pass
                except UnicodeDecodeError:
                    # Binary message, leave as is
                    pass
                
                # If we have handlers registered through the API
                if topic in self.topic_handlers:
                    for h_id, h_func in self.topic_handlers[topic].items():
                        try:
                            h_func(message)
                        except Exception as handler_error:
                            self.logger.warning(f"Error in message handler {h_id}: {str(handler_error)}")
            
            # Register the handler
            success = self.libp2p_peer.subscribe(topic, message_handler)
            
            if success:
                # Store subscription in our internal tracking
                self.active_subscriptions[topic][handler_id] = {
                    "handler_id": handler_id,
                    "subscribed_at": time.time()
                }
                
                # Update stats
                self.operation_stats["pubsub_subscriptions"] += 1
                
                result["success"] = True
            else:
                result["error"] = "Failed to subscribe to topic"
                result["error_type"] = "pubsub_subscribe_error"
                self.operation_stats["failed_operations"] += 1
            
            return result
            
        except Exception as e:
            # Handle any errors
            self.logger.error(f"Error subscribing to topic {topic}: {str(e)}")
            result["error"] = f"Error subscribing to topic: {str(e)}"
            result["error_type"] = "pubsub_subscribe_error"
            self.operation_stats["failed_operations"] += 1
            return result
    
    def pubsub_unsubscribe(self, topic: str, handler_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Unsubscribe from a PubSub topic.
        
        Args:
            topic: Topic to unsubscribe from
            handler_id: Optional specific handler ID to unsubscribe
            
        Returns:
            Dict with unsubscribe status
        """
        self.operation_stats["operation_count"] += 1
        
        # Prepare result
        result = {
            "success": False,
            "operation": "pubsub_unsubscribe",
            "topic": topic,
            "timestamp": time.time()
        }
        
        # Return early if libp2p is not available
        if not self._is_available_sync():
            result["error"] = "libp2p is not available"
            result["error_type"] = "dependency_missing"
            self.operation_stats["failed_operations"] += 1
            return result
        
        # Check if PubSub is available
        if not self.libp2p_peer.pubsub:
            result["error"] = "PubSub is not available"
            result["error_type"] = "pubsub_unavailable"
            self.operation_stats["failed_operations"] += 1
            return result
        
        try:
            # Unsubscribe from topic
            success = self.libp2p_peer.unsubscribe(topic)
            
            if success:
                # If handler_id is specified, only remove that handler
                if handler_id and topic in self.active_subscriptions:
                    if handler_id in self.active_subscriptions[topic]:
                        del self.active_subscriptions[topic][handler_id]
                        if not self.active_subscriptions[topic]:
                            del self.active_subscriptions[topic]
                    result["handler_id"] = handler_id
                    result["handler_removed"] = True
                # Otherwise remove all handlers for the topic
                elif topic in self.active_subscriptions:
                    handlers_count = len(self.active_subscriptions[topic])
                    del self.active_subscriptions[topic]
                    result["handlers_removed"] = handlers_count
                
                result["success"] = True
            else:
                result["error"] = "Failed to unsubscribe from topic"
                result["error_type"] = "pubsub_unsubscribe_error"
                self.operation_stats["failed_operations"] += 1
            
            return result
            
        except Exception as e:
            # Handle any errors
            self.logger.error(f"Error unsubscribing from topic {topic}: {str(e)}")
            result["error"] = f"Error unsubscribing from topic: {str(e)}"
            result["error_type"] = "pubsub_unsubscribe_error"
            self.operation_stats["failed_operations"] += 1
            return result
    
    def pubsub_get_topics(self) -> Dict[str, Any]:
        """
        Get a list of topics we're subscribed to.
        
        Returns:
            Dict with topics information
        """
        self.operation_stats["operation_count"] += 1
        
        # Prepare result
        result = {
            "success": False,
            "operation": "pubsub_get_topics",
            "timestamp": time.time(),
            "topics": []
        }
        
        # Return early if libp2p is not available
        if not self._is_available_sync():
            result["error"] = "libp2p is not available"
            result["error_type"] = "dependency_missing"
            self.operation_stats["failed_operations"] += 1
            return result
        
        # Check if PubSub is available
        if not self.libp2p_peer.pubsub:
            result["error"] = "PubSub is not available"
            result["error_type"] = "pubsub_unavailable"
            self.operation_stats["failed_operations"] += 1
            return result
        
        try:
            # Get list of topics
            topics = self.libp2p_peer.get_topics()
            
            # Add details about our subscriptions
            topic_details = []
            for topic in topics:
                detail = {
                    "topic": topic,
                    "handlers": []
                }
                
                # Add handler details if we have any
                if topic in self.active_subscriptions:
                    detail["handlers"] = list(self.active_subscriptions[topic].values())
                
                topic_details.append(detail)
            
            result["success"] = True
            result["topics"] = topics
            result["topic_count"] = len(topics)
            result["topic_details"] = topic_details
            
            return result
            
        except Exception as e:
            # Handle any errors
            self.logger.error(f"Error getting topics: {str(e)}")
            result["error"] = f"Error getting topics: {str(e)}"
            result["error_type"] = "pubsub_topics_error"
            self.operation_stats["failed_operations"] += 1
            return result
    
    def pubsub_get_peers(self, topic: Optional[str] = None) -> Dict[str, Any]:
        """
        Get peers subscribed to a topic.
        
        Args:
            topic: Optional topic to get peers for. If None, get all peers.
            
        Returns:
            Dict with peers information
        """
        self.operation_stats["operation_count"] += 1
        
        # Prepare result
        result = {
            "success": False,
            "operation": "pubsub_get_peers",
            "timestamp": time.time(),
            "peers": []
        }
        
        # Add topic to result if specified
        if topic:
            result["topic"] = topic
        
        # Return early if libp2p is not available
        if not self._is_available_sync():
            result["error"] = "libp2p is not available"
            result["error_type"] = "dependency_missing"
            self.operation_stats["failed_operations"] += 1
            return result
        
        # Check if PubSub is available
        if not self.libp2p_peer.pubsub:
            result["error"] = "PubSub is not available"
            result["error_type"] = "pubsub_unavailable"
            self.operation_stats["failed_operations"] += 1
            return result
        
        try:
            # Get peers for the topic or all peers
            if topic:
                peers = self.libp2p_peer.get_topic_peers(topic)
                result["peer_count"] = len(peers)
            else:
                # Get all topics first
                topics = self.libp2p_peer.get_topics()
                
                # Then get peers for each topic
                topic_peers = {}
                for t in topics:
                    t_peers = self.libp2p_peer.get_topic_peers(t)
                    topic_peers[t] = t_peers
                
                # Get unique peers across all topics
                all_peers = set()
                for t, t_peers in topic_peers.items():
                    all_peers.update(t_peers)
                
                peers = list(all_peers)
                result["peer_count"] = len(peers)
                result["topic_peers"] = topic_peers
            
            result["success"] = True
            result["peers"] = peers
            
            return result
            
        except Exception as e:
            # Handle any errors
            self.logger.error(f"Error getting peers for topic {topic}: {str(e)}")
            result["error"] = f"Error getting peers: {str(e)}"
            result["error_type"] = "pubsub_peers_error"
            self.operation_stats["failed_operations"] += 1
            return result
    
    def register_message_handler(self, topic: str, handler_function: Callable, handler_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Register a message handler for a topic.
        
        Args:
            topic: Topic to handle messages for
            handler_function: Function to call when messages are received
            handler_id: Optional ID for the handler
            
        Returns:
            Dict with registration status
        """
        self.operation_stats["operation_count"] += 1
        
        # Generate a handler ID if not provided
        if handler_id is None:
            handler_id = f"handler_{uuid.uuid4()}"
        
        # Prepare result
        result = {
            "success": False,
            "operation": "register_message_handler",
            "topic": topic,
            "handler_id": handler_id,
            "timestamp": time.time()
        }
        
        try:
            # Initialize handler dictionary if needed
            if not hasattr(self, "topic_handlers"):
                self.topic_handlers = {}
            
            # Initialize topic handlers if needed
            if topic not in self.topic_handlers:
                self.topic_handlers[topic] = {}
            
            # Add the handler
            self.topic_handlers[topic][handler_id] = handler_function
            
            # Subscribe to the topic if not already subscribed
            if self.is_available() and self.libp2p_peer.pubsub:
                # Check if we're already subscribed
                if topic not in self.active_subscriptions:
                    # Subscribe to the topic
                    subscribe_result = self.pubsub_subscribe(topic, handler_id)
                    if not subscribe_result.get("success", False):
                        # If subscribe failed, return the error
                        return subscribe_result
            
            result["success"] = True
            
            return result
            
        except Exception as e:
            # Handle any errors
            self.logger.error(f"Error registering message handler for topic {topic}: {str(e)}")
            result["error"] = f"Error registering message handler: {str(e)}"
            result["error_type"] = "handler_registration_error"
            self.operation_stats["failed_operations"] += 1
            return result
    
    def unregister_message_handler(self, topic: str, handler_id: str) -> Dict[str, Any]:
        """
        Unregister a message handler for a topic.
        
        Args:
            topic: Topic the handler is registered for
            handler_id: ID of the handler to unregister
            
        Returns:
            Dict with unregistration status
        """
        self.operation_stats["operation_count"] += 1
        
        # Prepare result
        result = {
            "success": False,
            "operation": "unregister_message_handler",
            "topic": topic,
            "handler_id": handler_id,
            "timestamp": time.time()
        }
        
        try:
            # Check if the handler exists
            if not hasattr(self, "topic_handlers") or topic not in self.topic_handlers or handler_id not in self.topic_handlers[topic]:
                result["error"] = f"Handler {handler_id} not found for topic {topic}"
                result["error_type"] = "handler_not_found"
                self.operation_stats["failed_operations"] += 1
                return result
            
            # Remove the handler
            del self.topic_handlers[topic][handler_id]
            
            # If no more handlers for this topic, clean up the topic entry
            if not self.topic_handlers[topic]:
                del self.topic_handlers[topic]
            
            result["success"] = True
            
            return result
            
        except Exception as e:
            # Handle any errors
            self.logger.error(f"Error unregistering message handler {handler_id} for topic {topic}: {str(e)}")
            result["error"] = f"Error unregistering message handler: {str(e)}"
            result["error_type"] = "handler_unregistration_error"
            self.operation_stats["failed_operations"] += 1
            return result
    
    def list_message_handlers(self) -> Dict[str, Any]:
        """
        List all registered message handlers.
        
        Returns:
            Dict with handlers information
        """
        self.operation_stats["operation_count"] += 1
        
        # Prepare result
        result = {
            "success": True,
            "operation": "list_message_handlers",
            "timestamp": time.time(),
            "handlers": {}
        }
        
        try:
            # Check if we have any handlers
            if hasattr(self, "topic_handlers"):
                # Build handler information
                for topic, handlers in self.topic_handlers.items():
                    result["handlers"][topic] = {
                        handler_id: {
                            "handler_id": handler_id,
                            "topic": topic,
                            "function_name": handler_func.__name__ if hasattr(handler_func, "__name__") else str(handler_func)
                        }
                        for handler_id, handler_func in handlers.items()
                    }
                
                result["handler_count"] = sum(len(handlers) for handlers in self.topic_handlers.values())
                result["topic_count"] = len(self.topic_handlers)
            else:
                result["handlers"] = {}
                result["handler_count"] = 0
                result["topic_count"] = 0
            
            return result
            
        except Exception as e:
            # Handle any errors
            self.logger.error(f"Error listing message handlers: {str(e)}")
            result["error"] = f"Error listing message handlers: {str(e)}"
            result["error_type"] = "handler_listing_error"
            self.operation_stats["failed_operations"] += 1
            return result
            
    def peer_info(self) -> Dict[str, Any]:
        """
        Get information about the current peer.
        
        Returns:
            Dict with peer information
        """
        self.operation_stats["operation_count"] += 1
        
        # Prepare result
        result = {
            "success": False,
            "operation": "peer_info",
            "timestamp": time.time()
        }
        
        # Return early if libp2p is not available
        if not self._is_available_sync():
            result["error"] = "libp2p is not available"
            result["error_type"] = "dependency_missing"
            self.operation_stats["failed_operations"] += 1
            return result
            
        try:
            # Get peer ID
            peer_id = self.libp2p_peer.get_peer_id()
            
            # Get listen addresses
            addrs = self.libp2p_peer.get_listen_addresses()
            
            # Get connected peers
            connected_peers = self.libp2p_peer.get_connected_peers()
            
            # Get DHT routing table size if available
            dht_peers = 0
            if self.libp2p_peer.dht:
                dht_peers = len(self.libp2p_peer.dht.routing_table.get_peers())
            
            # Update result with collected information
            result.update({
                "success": True,
                "peer_id": peer_id,
                "addresses": addrs,
                "connected_peers": len(connected_peers),
                "dht_peers": dht_peers,
                "protocols": list(self.libp2p_peer.protocol_handlers.keys()),
                "role": self.libp2p_peer.role
            })
            
            return result
            
        except Exception as e:
            # Handle any errors
            logger.error(f"Error getting peer info: {str(e)}")
            result["error"] = f"Error getting peer info: {str(e)}"
            result["error_type"] = "peer_info_error"
            self.operation_stats["failed_operations"] += 1
            return result
            
    def _check_and_install_dependencies(self) -> bool:
        """
        Check if libp2p dependencies are available and install them if needed.
        
        Returns:
            bool: True if dependencies are available or successfully installed
        """
        global HAS_LIBP2P
        
        # Skip if dependencies are already available
        if HAS_LIBP2P:
            return True
        
        # Re-check in case environment has changed
        check_dependencies()
        if HAS_LIBP2P:
            return True
        
        # Check if auto-install is enabled
        if self.metadata.get("auto_install_dependencies", False):
            self.logger.info("Auto-installing libp2p dependencies...")
            
            # Get install location
            install_dir = self.metadata.get("dependency_install_dir", None)
            
            # Try to install dependencies
            success = install_dependencies(install_dir=install_dir)
            
            if success:
                # Re-check dependencies after installation
                check_dependencies()
                if HAS_LIBP2P:
                    self.logger.info("Successfully installed libp2p dependencies")
                    return True
            
            # Installation failed
            self.logger.warning("Failed to install libp2p dependencies")
            return False
        
        # Auto-install not enabled
        return False