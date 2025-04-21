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
from typing import Dict, Any, Optional, Union, Callable

# Configure logger
logger = logging.getLogger(__name__)

# Initialize enhanced_content_routing logger
enhanced_logger = logging.getLogger(__name__)

# Core IPFS Kit imports

# Import global module-level variables to avoid UnboundLocalError in class methods
# Define default values for when imports fail - these will be used if imports fail
HAS_LIBP2P = False


def check_dependencies():
    """
    Check if libp2p dependencies are available.
    This is a stub that will be replaced if imports succeed.

    Returns:
        bool: False (stub implementation)
    """
    logging.getLogger(__name__).debug("Using stub check_dependencies function")
    return False


def install_dependencies(force=False):
    """
    Install libp2p dependencies.
    This is a stub that will be replaced if imports succeed.

    Args:
        force: Whether to force reinstallation

    Returns:
        bool: False (stub implementation)
    """
    logging.getLogger(__name__).debug("Using stub install_dependencies function")
    return False


# Setup logger for import diagnostics
import_logger = logging.getLogger(__name__)

# Try to import from ipfs_kit_py.libp2p first (preferred source)
try:
    # Check libp2p availability from the module
    from ipfs_kit_py.libp2p import HAS_LIBP2P, check_dependencies, install_dependencies

    import_logger.debug("Successfully imported from ipfs_kit_py.libp2p")
except ImportError as e:
    # In case of import error, we'll use fallback sources
    import_logger.warning(f"Failed to import ipfs_kit_py.libp2p dependencies: {e}")

    # Try to import directly from install_libp2p as first backup
    try:
        from install_libp2p import HAS_LIBP2P, check_dependencies, install_dependencies

        import_logger.debug("Successfully imported from install_libp2p")
    except ImportError as e:
        import_logger.warning(f"Failed to import install_libp2p: {e}")

        # Try to import from libp2p_peer as second backup (for mock testing)
        try:
            from ipfs_kit_py.libp2p_peer import HAS_LIBP2P

            import_logger.debug("Successfully imported HAS_LIBP2P from ipfs_kit_py.libp2p_peer")
        except ImportError as e:
            # If all imports fail, we'll use the default values defined above
            import_logger.warning(f"Failed to import all libp2p dependency sources: {e}")
            import_logger.warning("Using default values (HAS_LIBP2P=False)")
except Exception as e:
    # Catch any other exceptions during import
    import_logger.error(f"Unexpected error during libp2p imports: {e}")
    import_logger.warning("Using default values (HAS_LIBP2P=False)")

# Ensure we have a valid HAS_LIBP2P variable in this module's global scope
# This prevents UnboundLocalError when accessing HAS_LIBP2P later
globals()["HAS_LIBP2P"] = HAS_LIBP2P

# Import libp2p peer if available
if HAS_LIBP2P:
    from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer

    # Apply protocol extensions
    from ipfs_kit_py.libp2p import apply_protocol_extensions_to_instance

    # Import DHT discovery
    from ipfs_kit_py.libp2p import get_enhanced_dht_discovery

    EnhancedDHTDiscovery = get_enhanced_dht_discovery()

    # Import enhanced content routing
    try:
        from ipfs_kit_py.libp2p.enhanced_content_routing import EnhancedContentRouter, RecursiveContentRouter, apply_to_peer

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
    def __init__(self, 
                 libp2p_peer_instance=None,
                 cache_manager=None,
                 credential_manager=None,
                 resources=None,
                 metadata=None):
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
            libp2p_available = "ipfs_kit_py.libp2p" in sys.modules and getattr(
                sys.modules["ipfs_kit_py.libp2p"], "HAS_LIBP2P", False)

            if not libp2p_available and self.metadata.get("auto_install_dependencies", False):
                logger.info("Auto-installing libp2p dependencies...")
                success = install_dependencies()
                if success:
                    # Try to import dependencies again after installation
                    try:
                        import importlib

                        # If the module exists, reload it to get new imports
                        if "ipfs_kit_py.libp2p" in sys.modules:
                            importlib.reload(sys.modules["ipfs_kit_py.libp2p"])
                            # Check if installation was successful (without using global)
                            if (
                                hasattr(sys.modules["ipfs_kit_py.libp2p"], "HAS_LIBP2P")
                                and sys.modules["ipfs_kit_py.libp2p"].HAS_LIBP2P):
                                logger.info("Successfully installed libp2p dependencies")
                                # We don't need to modify the module-level variable
                                # We'll just use the functions based on the imports below
                    except (ImportError, KeyError):
                        logger.warning("Failed to reload libp2p module after installation")
            elif not libp2p_available:
                logger.warning(
                    "libp2p dependencies are not available. P2P functionality will be limited.")

        # Initialize libp2p peer
        if libp2p_peer_instance:
            # Use provided instance
            self.libp2p_peer = libp2p_peer_instance
            logger.info("Using provided libp2p peer instance")
        elif self.metadata.get("test_mode", False):
            # Create a mock peer for testing to avoid event loop issues
            logger.info("Creating mock libp2p peer for test mode")

            # Use unittest.mock if available, otherwise create a simple object
            try:
                from unittest.mock import MagicMock

                self.libp2p_peer = MagicMock()
                # Add basic functionality for tests
                self.libp2p_peer.get_peer_id.return_value = "QmTestPeerId123456789"
                self.libp2p_peer.get_listen_addresses.return_value = ["/ip4/127.0.0.1/tcp/10000"]
                self.libp2p_peer.get_connected_peers.return_value = []
                self.libp2p_peer._running = True
                self.libp2p_peer.start.return_value = True
                self.libp2p_peer.is_available.return_value = True
            except ImportError:
                # Create a simple mock object if MagicMock isn't available
                class SimpleMock:
                    def get_peer_id(self):
                        return "QmTestPeerId123456789"

                    def get_listen_addresses(self):
                        return ["/ip4/127.0.0.1/tcp/10000"]

                    def get_connected_peers(self):
                        return []

                    def start(self):
                        return True

                    def is_available(self):
                        return True

                self.libp2p_peer = SimpleMock()
                self.libp2p_peer._running = True

            logger.info(f"Initialized mock libp2p peer with ID: {self.libp2p_peer.get_peer_id()}")
        elif libp2p_available:
            # Create new instance with role-based configuration
            try:
                # Extract configuration from metadata
                role = self.metadata.get("role", "leecher")
                enable_mdns = self.metadata.get("enable_mdns", True)
                enable_hole_punching = self.metadata.get("enable_hole_punching", False)
                enable_relay = self.metadata.get("enable_relay", True)
                identity_path = self.metadata.get(
                    "identity_path",
                    os.path.expanduser("~/.ipfs_kit/libp2p/identity.key"))

                # Get bootstrap peers from configuration or use defaults
                bootstrap_peers = self.metadata.get(
                    "bootstrap_peers",
                    [
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
                    metadata=self.metadata)

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
        try:
            # First check global variable
            if not HAS_LIBP2P:
                return False

            # Then check if we have a peer instance
            if self.libp2p_peer is None:
                return False

            # Additional check for required attributes to ensure it's properly initialized
            return hasattr(self.libp2p_peer, "get_peer_id")
        except Exception as e:
            # Log the error for debugging
            self.logger.error(f"Error checking libp2p availability: {e}")
            return False

    def is_available(self) -> bool:
        """
        Check if libp2p functionality is available.

        Returns:
            bool: True if libp2p is available, False otherwise
        """
        return self._is_available_sync()

    async def is_available_async(self) -> bool:
        """
        Async version of is_available for use with async controllers.

        Returns:
            bool: True if libp2p is available, False otherwise
        """
        try:
            # Use anyio to run the synchronous version in a thread
            # This ensures it returns a proper coroutine that can be awaited
            import anyio

            return await anyio.to_thread.run_sync(lambda: self._is_available_sync())
        except Exception as e:
            # Ensure we don't crash when availability check fails
            self.logger.error(f"Error in async is_available check: {e}")
            return False

    def get_health(self) -> Dict[str, Any]:
        """
        Get comprehensive health information about the libp2p peer.

        Returns:
            Dict containing detailed health status information
        """
        self.operation_stats["operation_count"] += 1

        # Prepare health information with basic data that's always available
        result = {
            "success": False,
            "operation": "get_health",
            "timestamp": time.time(),
            "dependency_status": {
                "libp2p_available": HAS_LIBP2P,
                "has_peer_instance": self.libp2p_peer is not None,
            },
            "library_versions": {
                "python": sys.version.split()[0],
                # We'll add more version info below if available
            }
        }

        # Check if we can access module versions safely
        try:
            import pkg_resources

            try:
                # Try to get libp2p version if installed
                libp2p_version = pkg_resources.get_distribution("libp2p").version
                result["library_versions"]["libp2p"] = libp2p_version
            except pkg_resources.DistributionNotFound:
                result["library_versions"]["libp2p"] = "not_installed"

            # Add ipfs_kit_py version
            try:
                ipfs_kit_version = pkg_resources.get_distribution("ipfs_kit_py").version
                result["library_versions"]["ipfs_kit_py"] = ipfs_kit_version
            except pkg_resources.DistributionNotFound:
                # Might be running from source without installation
                result["library_versions"]["ipfs_kit_py"] = "development"
        except Exception as pkg_err:
            # Non-fatal error when checking package versions
            self.logger.debug(f"Couldn't determine package versions: {pkg_err}")

        # Add comprehensive availability check with error details if any
        try:
            availability_result = self._is_available_sync()
            result["dependency_status"]["availability_check_success"] = True
            result["peer_available"] = availability_result
        except Exception as avail_err:
            result["dependency_status"]["availability_check_success"] = False
            result["dependency_status"]["availability_check_error"] = str(avail_err)
            result["peer_available"] = False

        # Add detailed dependency information
        try:
            # Check for key libp2p modules
            import importlib.util

            libp2p_modules = {
                "libp2p.core": importlib.util.find_spec("libp2p.core") is not None,
                "libp2p.network": importlib.util.find_spec("libp2p.network") is not None,
                "libp2p.peer": importlib.util.find_spec("libp2p.peer") is not None,
                "libp2p.crypto": importlib.util.find_spec("libp2p.crypto") is not None,
                "libp2p.kademlia": importlib.util.find_spec("libp2p.kademlia") is not None,
            }
            result["dependency_status"]["libp2p_modules"] = libp2p_modules
        except Exception as module_err:
            # Non-fatal error when checking modules
            self.logger.debug(f"Couldn't check for libp2p modules: {module_err}")

        # Return limited info if libp2p is not available
        if not result["peer_available"]:
            result["success"] = True  # Still consider it a successful check
            result["status"] = "unavailable"
            result["error"] = "libp2p is not available"
            result["error_type"] = "dependency_missing"
            result["recommendations"] = [
                "Install libp2p dependencies with `pip install libp2p` or equivalent",
                "Set auto_install_dependencies=True in metadata to enable auto-installation",
                "Ensure proper Python version (3.7+) for libp2p compatibility",
            ]
            self.operation_stats["failed_operations"] += 1
            return result

        # If we get here, we should have a working peer instance to query
        try:
            # Add initialization status
            if hasattr(self.libp2p_peer, "_running"):
                result["running"] = self.libp2p_peer._running
            else:
                result["running"] = "unknown"  # Can't determine if running

            # Get peer ID with error handling
            try:
                peer_id = self.libp2p_peer.get_peer_id()
                result["peer_id"] = peer_id
            except Exception as peer_id_err:
                result["peer_id_error"] = str(peer_id_err)

            # Get listen addresses with error handling
            try:
                addrs = self.libp2p_peer.get_listen_addresses()
                result["addresses"] = addrs
            except Exception as addr_err:
                result["addresses_error"] = str(addr_err)

            # Get connected peers with error handling
            try:
                connected_peers = self.libp2p_peer.get_connected_peers()
                result["connected_peers"] = len(connected_peers)
                # Include the first few peer IDs for diagnostics
                if connected_peers:
                    result["connected_peer_sample"] = connected_peers[:5]
            except Exception as peer_err:
                result["connected_peers_error"] = str(peer_err)

            # Get DHT routing table size if available
            try:
                dht_peers = 0
                dht_available = False
                if hasattr(self.libp2p_peer, "dht") and self.libp2p_peer.dht:
                    dht_available = True
                    if hasattr(self.libp2p_peer.dht, "routing_table") and hasattr(
                        self.libp2p_peer.dht.routing_table, "get_peers"):
                        dht_peers = len(self.libp2p_peer.dht.routing_table.get_peers())

                result["dht_available"] = dht_available
                if dht_available:
                    result["dht_peers"] = dht_peers
            except Exception as dht_err:
                result["dht_error"] = str(dht_err)

            # Get protocols with error handling
            try:
                if hasattr(self.libp2p_peer, "protocol_handlers"):
                    result["protocols"] = list(self.libp2p_peer.protocol_handlers.keys())
                else:
                    result["protocols"] = []
            except Exception as proto_err:
                result["protocols_error"] = str(proto_err)

            # Get role with error handling
            try:
                result["role"] = self.libp2p_peer.role
            except Exception as role_err:
                result["role_error"] = str(role_err)

            # Add stats to result with error handling
            try:
                # Include only the most relevant stats to keep response size manageable
                result["stats"] = {
                    "operation_count": self.operation_stats["operation_count"],
                    "failed_operations": self.operation_stats["failed_operations"],
                    "peers_discovered": self.operation_stats["peers_discovered"],
                    "content_retrieved": self.operation_stats["content_retrieved"],
                    "content_announced": self.operation_stats["content_announced"],
                    "bytes_retrieved": self.operation_stats["bytes_retrieved"],
                    "bytes_sent": self.operation_stats["bytes_sent"],
                    "uptime": time.time() - self.operation_stats["start_time"],
                }
            except Exception as stats_err:
                result["stats_error"] = str(stats_err)

            # Add extended component status
            result["components"] = {}

            # Check dht_discovery component
            if hasattr(self, "dht_discovery"):
                result["components"]["dht_discovery"] = {
                    "available": self.dht_discovery is not None,
                }
                if self.dht_discovery is not None:
                    try:
                        # Get any available status info
                        if hasattr(self.dht_discovery, "get_status"):
                            status = self.dht_discovery.get_status()
                            result["components"]["dht_discovery"]["status"] = status
                    except Exception as disc_err:
                        result["components"]["dht_discovery"]["error"] = str(disc_err)

            # Check pubsub component
            if hasattr(self.libp2p_peer, "pubsub"):
                result["components"]["pubsub"] = {"available": self.libp2p_peer.pubsub is not None}
                if self.libp2p_peer.pubsub is not None:
                    try:
                        # Get basic pubsub info
                        if hasattr(self.libp2p_peer, "get_topics"):
                            topics = self.libp2p_peer.get_topics()
                            result["components"]["pubsub"]["topic_count"] = len(topics)
                            # Include the first few topics for diagnostics
                            if topics:
                                result["components"]["pubsub"]["topic_sample"] = topics[:5]
                    except Exception as pubsub_err:
                        result["components"]["pubsub"]["error"] = str(pubsub_err)

            # Overall status is successful if we got this far
            result["success"] = True
            result["status"] = "healthy" if result.get("connected_peers", 0) > 0 else "initialized"

            # Cache result if cache manager is available
            if self.cache_manager:
                try:
                    self.cache_manager.put(
                        "libp2p_health",
                        result,
                        ttl=60,  # Cache for 60 seconds
                    )
                except Exception as cache_err:
                    self.logger.debug(f"Failed to cache health info: {cache_err}")

            return result

        except Exception as e:
            # Handle any errors during health check
            self.logger.error(f"Error getting libp2p peer health: {str(e)}")
            result["error"] = f"Error getting health information: {str(e)}"
            result["error_type"] = "health_check_error"
            result["status"] = "error"
            result["success"] = False  # Health check failed
            self.operation_stats["failed_operations"] += 1

            # Still try to include any information we might have
            if hasattr(self.libp2p_peer, "_running"):
                result["running"] = self.libp2p_peer._running

            # Add recommendations for troubleshooting
            result["recommendations"] = [
                "Check libp2p dependencies are properly installed",
                "Verify network connectivity for peer connections",
                "Check for any initialization errors in logs",
                "Try restarting the libp2p peer with model.start()",
            ]

            return result

    async def get_health_async(self) -> Dict[str, Any]:
        """
        Async version of get_health for use with async controllers.

        Returns:
            Dict containing detailed health status information
        """
        try:
            # Create a separate function to avoid calling the async method
            # Call the sync implementation directly
            def _get_health_sync(self):
                # Call the implementation directly by accessing the class dictionary
                return self.get_health()

            # Use anyio to run the synchronous version in a thread
            import anyio

            return await anyio.to_thread.run_sync(_get_health_sync)
        except Exception as e:
            # Handle errors in async execution
            self.logger.error(f"Error in async get_health: {e}")
            # Return a minimal result with error information
            return {
                "success": False,
                "operation": "get_health",
                "timestamp": time.time(),
                "error": f"Async execution error: {str(e)}",
                "error_type": "async_execution_error",
                "dependency_status": {
                    "libp2p_available": HAS_LIBP2P,
                    "has_peer_instance": self.libp2p_peer is not None,
                },
                "status": "error",
            }

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
        def _discover_peers_sync(self):
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
        def _connect_peer_sync(self):
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
        def _disconnect_peer_sync(self):
            return LibP2PModel.disconnect_peer(self, peer_id)

        # Use anyio to run the synchronous version in a thread
        import anyio

        return await anyio.to_thread.run_sync(_disconnect_peer_sync)

    async def find_content(self, cid: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Async version of find_content for use with async controllers.

        Args:
            cid: Content ID to find
            timeout: Maximum time to wait for content discovery
        """
        # Define a helper function to avoid parameter issues
        def _find_content_sync(self):
            return self._find_content_impl(cid, timeout)

        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(_find_content_sync)

    def _find_content_impl(self, cid: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Internal implementation for content finding logic.
        
        Args:
            cid: Content ID to find
            timeout: Maximum time to wait for content discovery
            
        Returns:
            Dict with content discovery results
        """
        result = {
            "success": False,
            "operation": "find_content",
            "cid": cid,
            "timestamp": time.time()
        }
        
        # Implementation would go here
        
        return result
