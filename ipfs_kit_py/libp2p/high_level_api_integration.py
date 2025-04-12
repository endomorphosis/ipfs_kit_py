"""
IPFS Kit High-Level API LibP2P Integration

This module implements the integration between the IPFS Kit High-Level API
and the enhanced libp2p discovery mechanism, allowing direct P2P content retrieval
and peer discovery through the simplified high-level API interface.

The integration uses dependency injection to avoid circular imports, where the
high-level API class is passed as a parameter rather than being imported directly.
This module adds methods like discover_peers, connect_to_peer, and request_content_from_peer
to the high-level API class.
"""

import logging
import time
import anyio
import json
import uuid
from typing import Any, Dict, List, Optional, Union, Type, Callable

# Import the libp2p dependency flag
from . import HAS_LIBP2P

# Configure logger
logger = logging.getLogger(__name__)

# Check for high-level API availability
# Note: We don't import directly to avoid circular imports
# The actual class will be passed via dependency injection
HAS_HIGH_LEVEL_API = False
try:
    # Check if the high level API module exists
    import importlib
    try:
        # Try to import as a module, not as a package
        importlib.import_module("ipfs_kit_py.high_level_api")
        HAS_HIGH_LEVEL_API = True
        logger.debug("High-level API module is available")
    except (ImportError, ValueError) as e:
        logger.debug(f"High-level API module is not available: {e}")
        HAS_HIGH_LEVEL_API = False
except ImportError:
    logger.warning("Failed to check for high-level API module")
    HAS_HIGH_LEVEL_API = False

def extend_high_level_api_class(high_level_api_cls):
    """Extend the IPFSSimpleAPI class with libp2p peer discovery functionality.

    This function adds the discover_peers and related methods to the
    IPFSSimpleAPI class, allowing direct peer discovery without using
    the full IPFS daemon.

    Args:
        high_level_api_cls: The IPFSSimpleAPI class to extend
    """
    if not HAS_HIGH_LEVEL_API:
        logger.warning("High-level API not available")
        return high_level_api_cls

    # Check if the class is already extended
    if hasattr(high_level_api_cls, "discover_peers") and hasattr(high_level_api_cls, "connect_to_peer"):
        return high_level_api_cls

    def discover_peers(self, discovery_method="all", max_peers=20, timeout=30, topic=None):
        """Discover peers in the IPFS network using libp2p.

        This method uses enhanced peer discovery mechanisms to find IPFS peers
        without relying solely on the IPFS daemon. It combines mDNS local discovery,
        DHT-based peer finding, and bootstrap peer connections.

        Args:
            discovery_method: Method to use for discovery ('dht', 'mdns', 'pubsub', 'all')
            max_peers: Maximum number of peers to discover
            timeout: Maximum time to wait for discovery in seconds
            topic: Optional topic for pubsub-based discovery

        Returns:
            Dictionary with peer information including IDs and multiaddresses
        """
        logger = getattr(self, "logger", logging.getLogger(__name__))
        result = {
            "success": False,
            "peers": [],
            "timestamp": time.time(),
            "operation": "discover_peers"
        }

        try:
            # First check if we have a libp2p_peer instance
            if not hasattr(self, "libp2p_peer"):
                # Try to create a libp2p peer if not already available
                try:
                    from ..libp2p_peer import IPFSLibp2pPeer, HAS_LIBP2P

                    if not HAS_LIBP2P:
                        result["error"] = "libp2p is not available"
                        return result

                    # Create the peer with the appropriate role
                    role = getattr(self, "role", "leecher")
                    self.libp2p_peer = IPFSLibp2pPeer(role=role)
                    logger.info(f"Created libp2p peer with role {role}")

                    # Initialize components
                    from ..libp2p.p2p_integration import register_libp2p_with_ipfs_kit
                    if hasattr(self, "kit"):
                        # If we have an IPFSKit instance, register with it
                        register_libp2p_with_ipfs_kit(self.kit, self.libp2p_peer)
                        logger.info("Registered libp2p peer with IPFSKit")

                except (ImportError, Exception) as e:
                    result["error"] = f"Failed to create libp2p peer: {str(e)}"
                    return result

            # Set up the discovery sources
            discovery_sources = []
            if discovery_method == "all":
                discovery_sources = ["mdns", "dht", "pubsub"]
            elif discovery_method in ["mdns", "dht", "pubsub"]:
                discovery_sources = [discovery_method]
            else:
                result["error"] = f"Invalid discovery method: {discovery_method}"
                return result

            # Start timers
            start_time = time.time()
            discovered_peers = {}

            # Start discovery with the provided parameters
            for source in discovery_sources:
                if time.time() - start_time > timeout:
                    break  # Timeout reached

                remaining_time = max(1, timeout - (time.time() - start_time))
                source_peers = []

                try:
                    if source == "mdns":
                        # Local network discovery
                        self.libp2p_peer.start_discovery("ipfs-discovery")
                        # Sleep a bit to let mDNS work
                        import anyio
                        loop = anyio.get_event_loop()
                        loop.run_until_complete(anyio.sleep(min(2, remaining_time)))

                    elif source == "dht":
                        # Import our enhanced discovery
                        from .enhanced_dht_discovery import EnhancedDHTDiscovery

                        # Create discovery component if it doesn't exist
                        if not hasattr(self, "dht_discovery"):
                            self.dht_discovery = EnhancedDHTDiscovery(
                                self.libp2p_peer,
                                role=getattr(self, "role", "leecher")
                            )

                        # Find random peers in the DHT
                        import uuid
                        random_key = f"random-{uuid.uuid4()}"

                        async def find_dht_peers():
                            return await self.dht_discovery._find_random_peers_async(
                                random_key,
                                max(max_peers - len(discovered_peers), 5)
                            )

                        loop = anyio.get_event_loop()
                        dht_peers = loop.run_until_complete(
                            anyio.wait_for(find_dht_peers(), timeout=remaining_time)
                        )

                        source_peers = dht_peers or []

                    elif source == "pubsub":
                        # Topic-based discovery
                        discovery_topic = topic or "ipfs-kit-discovery"

                        # Try to find peers subscribed to this topic
                        try:
                            if hasattr(self.libp2p_peer, "pubsub"):
                                # Get peers subscribed to the topic
                                ps_peers = self.libp2p_peer.pubsub.get_peers_subscribed(discovery_topic)

                                for peer_id in ps_peers:
                                    peer_info = {
                                        "id": str(peer_id),
                                        "addresses": [],
                                        "source": "pubsub"
                                    }

                                    # Try to get multiaddresses
                                    try:
                                        peer = self.libp2p_peer.host.get_peerstore().get_peer(peer_id)
                                        if peer:
                                            peer_info["addresses"] = [str(addr) for addr in peer.addrs]
                                    except Exception:
                                        pass

                                    source_peers.append(peer_info)

                                # Also publish to the topic to announce ourselves
                                import json
                                self.libp2p_peer.pubsub.publish(
                                    discovery_topic,
                                    json.dumps({
                                        "announce": True,
                                        "peer_id": self.libp2p_peer.get_peer_id(),
                                        "timestamp": time.time()
                                    }).encode()
                                )
                        except Exception as e:
                            logger.warning(f"PubSub peer discovery error: {e}")

                except Exception as e:
                    logger.warning(f"Error in {source} discovery: {e}")
                    continue

                # Add discovered peers
                for peer in source_peers:
                    peer_id = peer.get("id")
                    if not peer_id:
                        continue

                    if peer_id not in discovered_peers:
                        peer["source"] = source
                        discovered_peers[peer_id] = peer

                # Check if we've found enough peers
                if len(discovered_peers) >= max_peers:
                    break

            # Also check directly connected peers
            if hasattr(self.libp2p_peer, "host") and hasattr(self.libp2p_peer.host, "get_network"):
                try:
                    connections = self.libp2p_peer.host.get_network().connections

                    for peer_id in connections:
                        str_id = str(peer_id)
                        if str_id not in discovered_peers:
                            peer_info = {
                                "id": str_id,
                                "addresses": [],
                                "source": "connected"
                            }

                            # Try to get peer information from peerstore
                            try:
                                peer = self.libp2p_peer.host.get_peerstore().get_peer(peer_id)
                                if peer:
                                    peer_info["addresses"] = [str(addr) for addr in peer.addrs]
                            except Exception:
                                pass

                            discovered_peers[str_id] = peer_info
                except Exception as e:
                    logger.warning(f"Error checking connected peers: {e}")

            # Update the result
            result["peers"] = list(discovered_peers.values())
            result["peer_count"] = len(result["peers"])
            result["discovery_time"] = time.time() - start_time
            result["discovery_sources"] = discovery_sources
            result["success"] = True

            return result

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error discovering peers: {e}")
            return result

    def connect_to_peer(self, peer_address, timeout=30):
        """Connect to a peer directly using libp2p.

        Args:
            peer_address: The peer multiaddress to connect to
                         (e.g. "/ip4/1.2.3.4/tcp/4001/p2p/QmPeerId")
            timeout: Maximum time to wait for connection in seconds

        Returns:
            Dictionary with connection result
        """
        logger = getattr(self, "logger", logging.getLogger(__name__))
        result = {
            "success": False,
            "operation": "connect_to_peer",
            "timestamp": time.time(),
            "address": peer_address
        }

        try:
            # Check if we have a libp2p peer
            if not hasattr(self, "libp2p_peer"):
                # Try to initialize via discover_peers
                discover_result = self.discover_peers(timeout=5)
                if not discover_result["success"]:
                    result["error"] = "No libp2p peer available and initialization failed"
                    return result

            # Try to connect
            connected = self.libp2p_peer.connect_peer(peer_address)

            if connected:
                # Extract peer ID from the multiaddress
                peer_id = None
                try:
                    # The multiaddress format is like "/ip4/1.2.3.4/tcp/4001/p2p/QmPeerId"
                    # Extract the peer ID from the end
                    parts = peer_address.split("/")
                    if "p2p" in parts:
                        p2p_index = parts.index("p2p")
                        if p2p_index + 1 < len(parts):
                            peer_id = parts[p2p_index + 1]
                except Exception:
                    pass

                result["success"] = True
                result["peer_id"] = peer_id
                logger.info(f"Successfully connected to peer {peer_id}")
            else:
                result["error"] = "Failed to connect to peer"

            return result

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error connecting to peer: {e}")
            return result

    def get_connected_peers(self):
        """Get a list of currently connected peers.

        Returns:
            Dictionary with peer information
        """
        logger = getattr(self, "logger", logging.getLogger(__name__))
        result = {
            "success": False,
            "peers": [],
            "operation": "get_connected_peers",
            "timestamp": time.time()
        }

        try:
            # Check if we have a libp2p peer
            if not hasattr(self, "libp2p_peer"):
                result["error"] = "No libp2p peer available"
                return result

            # Get connected peers
            connected_peers = []

            # First try the direct host network connections
            if hasattr(self.libp2p_peer, "host") and hasattr(self.libp2p_peer.host, "get_network"):
                connections = self.libp2p_peer.host.get_network().connections

                for peer_id in connections:
                    peer_info = {
                        "id": str(peer_id),
                        "addresses": []
                    }

                    # Try to get peer information from peerstore
                    try:
                        peer = self.libp2p_peer.host.get_peerstore().get_peer(peer_id)
                        if peer:
                            peer_info["addresses"] = [str(addr) for addr in peer.addrs]
                    except Exception:
                        pass

                    connected_peers.append(peer_info)

            # If we didn't get any peers through the direct method, try alternative
            if not connected_peers and hasattr(self.libp2p_peer, "get_connected_peers"):
                # This is a simplified implementation
                peer_ids = self.libp2p_peer.get_connected_peers()
                for peer_id in peer_ids:
                    connected_peers.append({"id": peer_id, "addresses": []})

            result["peers"] = connected_peers
            result["peer_count"] = len(connected_peers)
            result["success"] = True

            return result

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error getting connected peers: {e}")
            return result

    def request_content_from_peer(self, peer_id, cid, timeout=30):
        """Request content directly from a specific peer.

        Args:
            peer_id: The ID of the peer to request from
            cid: Content ID to request
            timeout: Maximum time to wait for content in seconds

        Returns:
            Dictionary with the content result
        """
        logger = getattr(self, "logger", logging.getLogger(__name__))
        result = {
            "success": False,
            "operation": "request_content_from_peer",
            "timestamp": time.time(),
            "peer_id": peer_id,
            "cid": cid
        }

        try:
            # Check if we have a libp2p peer
            if not hasattr(self, "libp2p_peer"):
                result["error"] = "No libp2p peer available"
                return result

            # Request content
            content = self.libp2p_peer.request_content(cid, timeout=timeout)

            if content:
                result["success"] = True
                result["content"] = content
                result["size"] = len(content)
                logger.info(f"Successfully retrieved content {cid} from peer {peer_id}")
            else:
                result["error"] = "Failed to retrieve content"

            return result

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error requesting content from peer: {e}")
            return result

    def get_libp2p_peer_id(self):
        """Get the libp2p peer ID for this node.

        Returns:
            Dictionary with peer ID information
        """
        logger = getattr(self, "logger", logging.getLogger(__name__))
        result = {
            "success": False,
            "operation": "get_libp2p_peer_id",
            "timestamp": time.time()
        }

        try:
            # Check if we have a libp2p peer
            if not hasattr(self, "libp2p_peer"):
                # Try to initialize
                discover_result = self.discover_peers(timeout=5)
                if not discover_result["success"]:
                    result["error"] = "No libp2p peer available and initialization failed"
                    return result

            # Get the peer ID
            peer_id = self.libp2p_peer.get_peer_id()

            if peer_id:
                result["success"] = True
                result["peer_id"] = peer_id

                # Get addresses if available
                if hasattr(self.libp2p_peer, "get_multiaddrs"):
                    result["addresses"] = self.libp2p_peer.get_multiaddrs()

                # Get protocols if available
                if hasattr(self.libp2p_peer, "get_protocols"):
                    result["protocols"] = self.libp2p_peer.get_protocols()
            else:
                result["error"] = "Failed to get peer ID"

            return result

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error getting peer ID: {e}")
            return result

    # Add methods to high_level_api_cls
    high_level_api_cls.discover_peers = discover_peers
    high_level_api_cls.connect_to_peer = connect_to_peer
    high_level_api_cls.get_connected_peers = get_connected_peers
    high_level_api_cls.request_content_from_peer = request_content_from_peer
    high_level_api_cls.get_libp2p_peer_id = get_libp2p_peer_id

    return high_level_api_cls


def apply_high_level_api_integration(api_class=None):
    """Apply the High-Level API integration using dependency injection.

    This function extends the provided API class with libp2p peer discovery.
    Instead of importing the class (which causes circular imports), it accepts
    the class as a parameter.

    Args:
        api_class: The IPFSSimpleAPI class to extend. If None, no integration is performed.

    Returns:
        bool: True if successful, False otherwise
    """
    logger = logging.getLogger(__name__)

    try:
        # If no class is provided, we can't do the integration
        if api_class is None:
            logger.info("No API class provided, integration will be applied when called explicitly")
            return True

        # Extend the class
        extend_high_level_api_class(api_class)
        logger.info(f"Successfully applied libp2p integration to {api_class.__name__}")
        return True

    except Exception as e:
        logger.error(f"Failed to apply High-Level API integration: {e}")
        return False


# We no longer auto-apply the integration to avoid circular imports
# Instead, the main module should call apply_high_level_api_integration(api_class)
# This is a better design using dependency injection