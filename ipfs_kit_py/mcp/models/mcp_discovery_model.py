"""
MCP Discovery Model for automatic MCP server discovery and collaboration.

This model enables MCP servers to discover each other, advertise capabilities,
and collaborate on handling requests. It works via multiple transport layers:
- Direct libp2p peer discovery (DHT, mDNS)
- WebSocket-based discovery for NAT traversal
- Optional manual configuration

Discovered servers can be queried for capabilities and used to offload requests.
"""

import logging
import json
import time
import uuid
import random
import hashlib
from typing import Dict, List, Any, Optional, Callable
from threading import Lock
from ipfs_kit_py.libp2p import HAS_LIBP2P

# Try to import relevant dependencies
try:
    #     from ipfs_kit_py.peer_websocket_anyio import PeerInfo, PeerRole, MessageType
    # Unused import commented out

    HAS_PEER_WEBSOCKET = True
except ImportError:
    try:
        #         from ipfs_kit_py.peer_websocket import PeerInfo, PeerRole, MessageType
        # Unused import commented out

        HAS_PEER_WEBSOCKET = True
    except ImportError:
        HAS_PEER_WEBSOCKET = False

# Import LibP2P availability check


# Configure logger
logger = logging.getLogger(__name__)

# MCP Server feature set version and protocol ID
MCP_PROTOCOL_VERSION = "1.0.0"
MCP_PROTOCOL_ID = "/ipfs-kit-py/mcp-discovery/1.0.0"


# Define MCP server roles
class MCPServerRole:
    """MCP server roles for the discovery protocol."""
    MASTER = "master"  # Coordinates across servers, handles high-level operations
    WORKER = "worker"  # Processes specific tasks, handles computational work
    HYBRID = "hybrid"  # Both master and worker capabilities
    EDGE = "edge"  # Limited capabilities, typically client-facing


# Define message types for server-to-server communication
class MCPMessageType:
    """Message types for MCP server communication."""
    ANNOUNCE = "announce"  # Server announcing its presence
    CAPABILITIES = "capabilities"  # Server capabilities advertisement
    HEALTH = "health"  # Health check request/response
    TASK_REQUEST = "task_request"  # Request to process a task
    TASK_RESPONSE = "task_response"  # Response with task results
    DISCOVERY = "discovery"  # Request for known servers
    SHUTDOWN = "shutdown"  # Graceful shutdown notification


class MCPServerCapabilities:
    """Standard capability flags for MCP servers."""
    # Handling capabilities
    IPFS_DAEMON = "ipfs_daemon"  # Has IPFS daemon running
    IPFS_CLUSTER = "ipfs_cluster"  # Has IPFS cluster functionality
    LIBP2P = "libp2p"  # Has libp2p direct functionality

    # Storage backend capabilities
    S3 = "s3"  # Has S3 storage backend
    STORACHA = "storacha"  # Has Storacha storage backend
    FILECOIN = "filecoin"  # Has Filecoin storage backend
    HUGGINGFACE = "huggingface"  # Has HuggingFace integration
    LASSIE = "lassie"  # Has Lassie retrieval capability

    # Feature capabilities
    WEBRTC = "webrtc"  # Has WebRTC streaming capability
    FS_JOURNAL = "fs_journal"  # Has filesystem journal capability
    PEER_WEBSOCKET = "peer_websocket"  # Has peer websocket capability
    DISTRIBUTED = "distributed"  # Has distributed coordination
    AI_ML = "ai_ml"  # Has AI/ML integration
    ARIA2 = "aria2"  # Has Aria2 download capability


class MCPFeatureSet:
    """Represents a set of features that an MCP server supports."""
    def __init__(self, features: List[str], version: str = MCP_PROTOCOL_VERSION):
        self.features = set(features)
        self.version = version
        # Create a unique hash of this feature set for comparing compatibility
        feature_string = ",".join(sorted(self.features)) + "|" + self.version
        self.feature_hash = hashlib.sha256(feature_string.encode()).hexdigest()

    def is_compatible_with(self, other: "MCPFeatureSet") -> bool:
        """Check if this feature set is compatible with another feature set."""
        # For now, simple version match is sufficient
        # In the future, we could have more sophisticated compatibility checks
        return self.version == other.version

    def shares_features_with(self, other: "MCPFeatureSet", min_shared: int = 1) -> bool:
        """Check if this feature set shares at least min_shared features with another set."""
        shared_features = self.features.intersection(other.features)
        return len(shared_features) >= min_shared

    def can_handle_request(self, required_features: List[str]) -> bool:
        """Check if this feature set can handle a request requiring specific features."""
        required = set(required_features)
        return required.issubset(self.features)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "features": list(self.features),
            "version": self.version,
            "feature_hash": self.feature_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPFeatureSet":
        """Create from dictionary representation."""
        return cls(
            features=data.get("features", []),
            version=data.get("version", MCP_PROTOCOL_VERSION),
        )


class MCPServerInfo:
    """Information about an MCP server for discovery and coordination."""
    def __init__(self,
        server_id: str,
        role: str,
        feature_set: MCPFeatureSet,
        api_endpoint: Optional[str] = None,
        websocket_endpoint: Optional[str] = None,
        libp2p_peer_id: Optional[str] = None,
        libp2p_addresses: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize MCP server information.

        Args:
            server_id: Unique identifier for this server
            role: Server role (master, worker, hybrid, edge)
            feature_set: Set of features/capabilities this server supports
            api_endpoint: HTTP API endpoint for this server (optional)
            websocket_endpoint: WebSocket endpoint for this server (optional)
            libp2p_peer_id: libp2p peer ID for direct communication (optional)
            libp2p_addresses: libp2p multiaddresses for this server (optional)
            metadata: Additional server metadata
        """
        self.server_id = server_id
        self.role = role
        self.feature_set = feature_set
        self.api_endpoint = api_endpoint
        self.websocket_endpoint = websocket_endpoint
        self.libp2p_peer_id = libp2p_peer_id
        self.libp2p_addresses = libp2p_addresses or []
        self.metadata = metadata or {}
        self.last_seen = time.time()
        self.first_seen = time.time()
        self.health_status = {"healthy": True, "last_checked": time.time()}

    def to_dict_v2(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "server_id": self.server_id,
            "role": self.role,
            "feature_set": self.feature_set.to_dict(),
            "api_endpoint": self.api_endpoint,
            "websocket_endpoint": self.websocket_endpoint,
            "libp2p_peer_id": self.libp2p_peer_id,
            "libp2p_addresses": self.libp2p_addresses,
            "metadata": self.metadata,
            "last_seen": self.last_seen,
            "first_seen": self.first_seen,
            "health_status": self.health_status,
        }

    @classmethod
    def from_dict_v2(cls, data: Dict[str, Any]) -> "MCPServerInfo":
        """Create from dictionary representation."""
        server_info = cls(
            server_id=data.get("server_id", str(uuid.uuid4())),
            role=data.get("role", MCPServerRole.EDGE),
            feature_set=MCPFeatureSet.from_dict(data.get("feature_set", {"features": []})),
            api_endpoint=data.get("api_endpoint"),
            websocket_endpoint=data.get("websocket_endpoint"),
            libp2p_peer_id=data.get("libp2p_peer_id"),
            libp2p_addresses=data.get("libp2p_addresses", []),
            metadata=data.get("metadata", {}),
        )

        # Restore timestamps
        server_info.last_seen = data.get("last_seen", time.time())
        server_info.first_seen = data.get("first_seen", time.time())
        server_info.health_status = data.get(
            "health_status", {"healthy": True, "last_checked": time.time()}
        )

        return server_info


class MCPDiscoveryModel:
    """
    Model for MCP server discovery and collaboration.

    This model enables MCP servers to discover each other, advertise capabilities,
    and collaborate on handling requests. It works with both direct libp2p peer
    discovery and WebSocket-based discovery for environments with NAT/firewalls.
    """
    def __init__(self,
        server_id: Optional[str] = None,
        role: str = MCPServerRole.MASTER,
        features: Optional[List[str]] = None,
        libp2p_model = None,
        ipfs_model = None,
        cache_manager = None,
        credential_manager = None,
        resources = None,
        metadata = None):
        """
        Initialize the MCP discovery model.

        Args:
            server_id: Unique identifier for this server (generated if not provided)
            role: Server role (master, worker, hybrid, edge)
            features: List of features/capabilities this server supports
            libp2p_model: Optional libp2p model for direct peer discovery
            ipfs_model: Optional IPFS model for IPFS daemon integration
            cache_manager: Optional cache manager for caching results
            credential_manager: Optional credential manager for secure access
            resources: Optional resources configuration dictionary
            metadata: Optional metadata dictionary
        """
        # Core attributes
        self.server_id = server_id or f"mcp-{str(uuid.uuid4())[:8]}"
        self.role = role
        self.resources = resources or {}
        self.metadata = metadata or {}

        # Store optional components
        self.libp2p_model = libp2p_model
        self.ipfs_model = ipfs_model
        self.cache_manager = cache_manager
        self.credential_manager = credential_manager

        # Determine available features
        if features is None:
            features = self._detect_available_features()
        self.feature_set = MCPFeatureSet(features)

        # Create server info for this server
        self.server_info = self._create_local_server_info()

        # Track discovered servers
        self.known_servers = {}  # server_id -> MCPServerInfo
        self.server_lock = Lock()  # For thread-safe access to server list

        # Create feature hash groups for compatible servers
        self.feature_groups = {}  # feature_hash -> [server_id, ...]

        # Store task handlers for collaborative processing
        self.task_handlers = {}  # task_type -> handler_function

        # Statistics
        self.stats = {
            "servers_discovered": 0,
            "announcements_sent": 0,
            "announcements_received": 0,
            "tasks_dispatched": 0,
            "tasks_received": 0,
            "tasks_processed": 0,
            "discovery_requests": 0,
            "health_checks": 0,
            "start_time": time.time(),
        }

        # Determine if websocket discovery is available
        self.has_websocket = HAS_PEER_WEBSOCKET

        # Determine if libp2p discovery is available - ensure attribute is always set
        # Set default value first to ensure attribute always exists even if code below fails
        self.has_libp2p = False

        # Then attempt to check actual availability if libp2p appears to be available
        if HAS_LIBP2P and self.libp2p_model:
            try:
                # Use synchronous version to avoid async coroutine warning
                if hasattr(self.libp2p_model, "_is_available_sync"):
                    available = self.libp2p_model._is_available_sync()
                    self.has_libp2p = bool(available)  # Convert to bool for safety
                else:
                    # Fallback to checking attribute existence without calling
                    self.has_libp2p = True
            except Exception as e:
                logger.warning(f"Error checking libp2p availability: {e}")
                # Keep default False value

        logger.info(
            f"MCP Discovery Model initialized with ID {self.server_id} and role {self.role}"
        )
        logger.info(f"Features: {', '.join(self.feature_set.features)}")

    def _detect_available_features(self) -> List[str]:
        """
        Detect available features based on loaded components and controllers.

        Returns:
            List of detected features as strings
        """
        features = []

        # Check for libp2p availability - safely
        try:
            if HAS_LIBP2P and self.libp2p_model:
                # Use the synchronous version of is_available to avoid coroutine warnings
                if hasattr(self.libp2p_model, "_is_available_sync"):
                    if self.libp2p_model._is_available_sync():
                        features.append(MCPServerCapabilities.LIBP2P)
                elif hasattr(self.libp2p_model, "is_available"):
                    # Fallback to checking if the attribute exists (but don't call it if it's async)
                    features.append(MCPServerCapabilities.LIBP2P)
        except Exception as e:
            logger.warning(f"Error detecting libp2p feature availability: {e}")

        # Check WebSocket availability
        if HAS_PEER_WEBSOCKET:
            features.append(MCPServerCapabilities.PEER_WEBSOCKET)

        # Detect IPFS features
        if self.ipfs_model:
            features.append(MCPServerCapabilities.IPFS_DAEMON)

            # Check for IPFS Cluster
            try:
                if hasattr(self.ipfs_model, "ipfs_cluster_service") or hasattr(
                    self.ipfs_model, "ipfs_cluster_follow"):
                    features.append(MCPServerCapabilities.IPFS_CLUSTER)
            except (AttributeError, Exception):
                pass

        # Return detected features (will be extended with controller detection at MCP server level)
        return features

    def _create_local_server_info(self) -> MCPServerInfo:
        """
        Create server info for this local server.

        Returns:
            MCPServerInfo object representing this server
        """
        api_endpoint = None
        websocket_endpoint = None
        libp2p_peer_id = None
        libp2p_addresses = []

        # Extract API endpoint from metadata if available
        if "api_endpoint" in self.metadata:
            api_endpoint = self.metadata["api_endpoint"]

        # Extract WebSocket endpoint from metadata if available
        if "websocket_endpoint" in self.metadata:
            websocket_endpoint = self.metadata["websocket_endpoint"]

        # Get libp2p peer ID and addresses if available
        # Safely access has_libp2p attribute (should always be set by now, but be defensive)
        if getattr(self, "has_libp2p", False) and self.libp2p_model:
            try:
                peer_health = self.libp2p_model.get_health()
                if peer_health.get("success", False):
                    libp2p_peer_id = peer_health.get("peer_id")
                    libp2p_addresses = peer_health.get("addresses", [])
            except Exception as e:
                logger.warning(f"Error getting libp2p peer info: {e}")

        # Create server info
        return MCPServerInfo(
            server_id=self.server_id,
            role=self.role,
            feature_set=self.feature_set,
            api_endpoint=api_endpoint,
            websocket_endpoint=websocket_endpoint,
            libp2p_peer_id=libp2p_peer_id,
            libp2p_addresses=libp2p_addresses,
            metadata={
                "version": MCP_PROTOCOL_VERSION,
                "uptime": 0,  # Will be updated when needed
                "resources": self.resources,
            }
        )

    def update_server_info(self, **kwargs) -> Dict[str, Any]:
        """
        Update local server info with new values.

        Args:
            **kwargs: Key-value pairs to update in server info

        Returns:
            Dict with updated server info
        """
        # Update server info attributes
        for key, value in kwargs.items():
            if hasattr(self.server_info, key):
                setattr(self.server_info, key, value)
            elif key == "features":
                # Special case for updating features
                self.feature_set = MCPFeatureSet(value)
                self.server_info.feature_set = self.feature_set
            elif key == "metadata":
                # Update metadata dict
                self.server_info.metadata.update(value)

        # Always update uptime in metadata
        self.server_info.metadata["uptime"] = time.time() - self.stats["start_time"]

        # Return updated server info
        return self.server_info.to_dict_v2()

    def announce_server(self) -> Dict[str, Any]:
        """
        Announce this server to the network.

        Uses both libp2p pubsub and WebSocket for discovery.

        Returns:
            Dict with announcement status
        """
        # Prepare result
        result = {
            "success": False,
            "operation": "announce_server",
            "timestamp": time.time(),
            "announcement_channels": [],
        }

        # Update server info before announcing
        self.update_server_info()

        # Get announcement message
        announcement = {
            "message_type": MCPMessageType.ANNOUNCE,
            "server_info": self.server_info.to_dict_v2(),
            "timestamp": time.time(),
        }

        # Try to announce via libp2p - safely access attribute and check deps
        if getattr(self, "has_libp2p", False) and self.libp2p_model:
            try:
                # Use libp2p model to broadcast via pubsub
                pubsub_topic = f"/ipfs-kit-py/mcp-discovery/{self.feature_set.version}"
                message_data = json.dumps(announcement).encode("utf-8")

                # Use libp2p model's pubsub functionality - safely access nested attributes
                if (
                    hasattr(self.libp2p_model, "libp2p_peer")
                    and self.libp2p_model.libp2p_peer
                    and hasattr(self.libp2p_model.libp2p_peer, "pubsub_publish")
                ):
                    self.libp2p_model.libp2p_peer.pubsub_publish(pubsub_topic, message_data)
                    result["announcement_channels"].append("libp2p_pubsub")
            except Exception as e:
                logger.warning(f"Error announcing via libp2p: {e}")

        # Try to announce via WebSocket
        if self.has_websocket:
            try:
                # This is just a placeholder since the actual implementation
                # would depend on your WebSocket client implementation
                # For now, we'll just log it
                logger.info(f"Would announce server via WebSocket: {self.server_id}")
                result["announcement_channels"].append("websocket")
            except Exception as e:
                logger.warning(f"Error announcing via WebSocket: {e}")

        # Update statistics
        self.stats["announcements_sent"] += 1

        # Set success based on at least one channel working
        result["success"] = len(result["announcement_channels"]) > 0

        return result

    def discover_servers(self,
        methods: Optional[List[str]] = None,
        compatible_only: bool = True,
        feature_requirements: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Discover MCP servers in the network.

        Args:
            methods: List of discovery methods to use ("libp2p", "websocket", "manual")
            compatible_only: Only return servers with compatible feature sets
            feature_requirements: Only return servers with these specific features

        Returns:
            Dict with discovered servers
        """
        # Prepare result
        result = {
            "success": False,
            "operation": "discover_servers",
            "timestamp": time.time(),
            "methods": methods or ["all"],
            "servers": [],
        }

        # Use all available methods if not specified - safely access attributes
        if methods is None or "all" in methods:
            methods = []
            if getattr(self, "has_libp2p", False):
                methods.append("libp2p")
            if getattr(self, "has_websocket", False):
                methods.append("websocket")
            methods.append("manual")  # Always include manually configured servers

        # Track new discoveries
        new_servers = 0

        # Use libp2p for discovery - safely access attributes and check deps
        if "libp2p" in methods and getattr(self, "has_libp2p", False) and self.libp2p_model:
            try:
                # Use libp2p model to discover peers
                if hasattr(self.libp2p_model, "discover_peers"):
                    peers_result = self.libp2p_model.discover_peers(
                        discovery_method="all", limit=100
                    )

                if peers_result.get("success", False):
                    for peer_addr in peers_result.get("peers", []):
                        try:
                            # Try to get server info from the peer
                            # This would require implementing a libp2p protocol for MCP discovery
                            # For now, we'll just log it
                            logger.debug(f"Discovered potential MCP server via libp2p: {peer_addr}")
                        except Exception as e:
                            logger.debug(f"Error processing libp2p peer {peer_addr}: {e}")
            except Exception as e:
                logger.warning(f"Error discovering servers via libp2p: {e}")

        # Use WebSocket for discovery
        if "websocket" in methods and self.has_websocket:
            try:
                # This is just a placeholder since the actual implementation
                # would depend on your WebSocket client implementation
                # For now, we'll just log it
                logger.debug("Would discover servers via WebSocket")
            except Exception as e:
                logger.warning(f"Error discovering servers via WebSocket: {e}")

        # Filter known servers based on criteria
        with self.server_lock:
            filtered_servers = []

            for server_id, server_info in self.known_servers.items():
                # Skip our own server
                if server_id == self.server_id:
                    continue

                # Filter by compatibility if requested
                if compatible_only and not self.feature_set.is_compatible_with(
                    server_info.feature_set
                ):
                    continue

                # Filter by feature requirements if specified
                if feature_requirements and not server_info.feature_set.can_handle_request(
                    feature_requirements
                ):
                    continue

                # Add to filtered list
                filtered_servers.append(server_info.to_dict_v2())

        # Update result
        result["success"] = True
        result["servers"] = filtered_servers
        result["server_count"] = len(filtered_servers)
        result["new_servers"] = new_servers

        # Update statistics
        self.stats["discovery_requests"] += 1

        return result

    def register_server(self, server_info_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Register a server from discovery.

        Args:
            server_info_dict: Dictionary representation of server info

        Returns:
            Dict with registration status
        """
        # Prepare result
        result = {
            "success": False,
            "operation": "register_server",
            "timestamp": time.time(),
        }

        try:
            # Parse server info
            server_info = MCPServerInfo.from_dict_v2(server_info_dict)

            # Skip our own server
            if server_info.server_id == self.server_id:
                result["success"] = True
                result["message"] = "Skipped registering own server"
                return result

            # Add or update server in known servers
            with self.server_lock:
                is_new = server_info.server_id not in self.known_servers

                if is_new:
                    # Track as new discovery
                    self.stats["servers_discovered"] += 1

                # Update or add server info
                self.known_servers[server_info.server_id] = server_info

                # Update feature hash groups
                feature_hash = server_info.feature_set.feature_hash
                if feature_hash not in self.feature_groups:
                    self.feature_groups[feature_hash] = []
                if server_info.server_id not in self.feature_groups[feature_hash]:
                    self.feature_groups[feature_hash].append(server_info.server_id)

            # Return success
            result["success"] = True
            result["server_id"] = server_info.server_id
            result["is_new"] = is_new

            # Log discovery
            if is_new:
                logger.info(
                    f"Discovered new MCP server: {server_info.server_id} (role: {server_info.role})"
                )
            else:
                logger.debug(f"Updated existing MCP server: {server_info.server_id}")

        except Exception as e:
            logger.error(f"Error registering server: {e}")
            result["error"] = str(e)

        return result

    def get_server_info(self, server_id: str) -> Dict[str, Any]:
        """
        Get information about a specific server.

        Args:
            server_id: ID of the server to get info for

        Returns:
            Dict with server information or error
        """
        # Prepare result
        result = {
            "success": False,
            "operation": "get_server_info",
            "timestamp": time.time(),
            "server_id": server_id,
        }

        # Check if this is our own server
        if server_id == self.server_id:
            # Update our server info first
            self.update_server_info()
            result["success"] = True
            result["server_info"] = self.server_info.to_dict_v2()
            result["is_local"] = True
            return result

        # Look for server in known servers
        with self.server_lock:
            if server_id in self.known_servers:
                result["success"] = True
                result["server_info"] = self.known_servers[server_id].to_dict_v2()
                result["is_local"] = False
                return result

        # Server not found
        result["error"] = f"Server not found: {server_id}"
        return result

    def get_compatible_servers(self, feature_requirements: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get all servers with compatible feature sets.

        Args:
            feature_requirements: Optional list of required features

        Returns:
            Dict with compatible servers
        """
        # Prepare result
        result = {
            "success": True,
            "operation": "get_compatible_servers",
            "timestamp": time.time(),
            "servers": [],
        }

        # Get compatible servers
        with self.server_lock:
            # First filter by feature hash for quick compatibility check
            compatible_server_ids = []

            # If we have specific feature requirements, we need to check each server
            if feature_requirements:
                for server_id, server_info in self.known_servers.items():
                    # Skip our own server
                    if server_id == self.server_id:
                        continue

                    # Check if server can handle required features
                    if server_info.feature_set.can_handle_request(feature_requirements):
                        compatible_server_ids.append(server_id)
            else:
                # Without specific requirements, we can use feature hash groups for faster matching
                our_feature_hash = self.feature_set.feature_hash
                for server_id in self.feature_groups.get(our_feature_hash, []):
                    # Skip our own server
                    if server_id == self.server_id:
                        continue

                    compatible_server_ids.append(server_id)

            # Get server info for compatible servers
            compatible_servers = []
            for server_id in compatible_server_ids:
                if server_id in self.known_servers:
                    compatible_servers.append(self.known_servers[server_id].to_dict_v2())

        # Update result
        result["servers"] = compatible_servers
        result["server_count"] = len(compatible_servers)

        return result

    def check_server_health(self, server_id: str) -> Dict[str, Any]:
        """
        Check health status of a specific server.

        Args:
            server_id: ID of the server to check

        Returns:
            Dict with health status
        """
        # Prepare result
        result = {
            "success": False,
            "operation": "check_server_health",
            "timestamp": time.time(),
            "server_id": server_id,
        }

        # Update statistics
        self.stats["health_checks"] += 1

        # Check if this is our own server
        if server_id == self.server_id:
            # For local server, we can immediately return healthy
            result["success"] = True
            result["healthy"] = True
            result["is_local"] = True
            return result

        # Look for server in known servers
        with self.server_lock:
            if server_id not in self.known_servers:
                result["error"] = f"Server not found: {server_id}"
                return result

            server_info = self.known_servers[server_id]

        # Check health based on available connection methods
        health_checked = False

        # Try HTTP API if available
        if server_info.api_endpoint:
            try:
                # This would be an actual HTTP request to the server's health endpoint
                # For now, we'll just simulate a response based on last_seen time
                time_since_last_seen = time.time() - server_info.last_seen
                is_healthy = time_since_last_seen < 300

                # Update server health info
                with self.server_lock:
                    if server_id in self.known_servers:
                        self.known_servers[server_id].health_status = {
                            "healthy": is_healthy,
                            "last_checked": time.time(),
                        }

                result["healthy"] = is_healthy
                result["health_source"] = "api"
                health_checked = True

            except Exception as e:
                logger.warning(f"Error checking health via API for {server_id}: {e}")

        # Try WebSocket if API failed and WebSocket is available
        if not health_checked and server_info.websocket_endpoint:
            try:
                # This would be an actual WebSocket health check
                # For now, we'll just simulate a response based on last_seen time
                time_since_last_seen = time.time() - server_info.last_seen
                is_healthy = time_since_last_seen < 300

                # Update server health info
                with self.server_lock:
                    if server_id in self.known_servers:
                        self.known_servers[server_id].health_status = {
                            "healthy": is_healthy,
                            "last_checked": time.time(),
                        }

                result["healthy"] = is_healthy
                result["health_source"] = "websocket"
                health_checked = True

            except Exception as e:
                logger.warning(f"Error checking health via WebSocket for {server_id}: {e}")

        # Try libp2p if other methods failed and libp2p is available - safely access attributes
        if (
            not health_checked
            and server_info.libp2p_peer_id
            and getattr(self, "has_libp2p", False)
            and self.libp2p_model
        ):
            try:
                # This would be a direct libp2p health check
                # For now, we'll just simulate a response based on last_seen time
                time_since_last_seen = time.time() - server_info.last_seen
                is_healthy = time_since_last_seen < 300

                # Update server health info
                with self.server_lock:
                    if server_id in self.known_servers:
                        self.known_servers[server_id].health_status = {
                            "healthy": is_healthy,
                            "last_checked": time.time(),
                        }

                result["healthy"] = is_healthy
                result["health_source"] = "libp2p"
                health_checked = True

            except Exception as e:
                logger.warning(f"Error checking health via libp2p for {server_id}: {e}")

        # If we couldn't check health, return last known health status
        if not health_checked:
            with self.server_lock:
                if server_id in self.known_servers:
                    result["healthy"] = self.known_servers[server_id].health_status.get(
                        "healthy", False
                    )
                    result["health_source"] = "last_known"
                    result["last_checked"] = self.known_servers[server_id].health_status.get(
                        "last_checked", 0
                    )
                    health_checked = True

        # Set success based on whether we could check health
        result["success"] = health_checked

        return result

    def remove_server(self, server_id: str) -> Dict[str, Any]:
        """
        Remove a server from known servers.

        Args:
            server_id: ID of the server to remove

        Returns:
            Dict with removal status
        """
        # Prepare result
        result = {
            "success": False,
            "operation": "remove_server",
            "timestamp": time.time(),
            "server_id": server_id,
        }

        # Can't remove our own server
        if server_id == self.server_id:
            result["error"] = "Cannot remove local server"
            return result

        # Remove server from known servers
        with self.server_lock:
            if server_id in self.known_servers:
                # Get server info before removing
                server_info = self.known_servers[server_id]

                # Remove from known servers
                del self.known_servers[server_id]

                # Remove from feature groups
                feature_hash = server_info.feature_set.feature_hash
                if (
                    feature_hash in self.feature_groups
                    and server_id in self.feature_groups[feature_hash]
                ):
                    self.feature_groups[feature_hash].remove(server_id)

                result["success"] = True
            else:
                result["error"] = f"Server not found: {server_id}"

        return result

    def clean_stale_servers(self, max_age_seconds: int = 3600) -> Dict[str, Any]:
        """
        Remove servers that haven't been seen for a specified time.

        Args:
            max_age_seconds: Maximum age in seconds before a server is considered stale

        Returns:
            Dict with cleanup status
        """
        # Prepare result
        result = {
            "success": True,
            "operation": "clean_stale_servers",
            "timestamp": time.time(),
            "max_age_seconds": max_age_seconds,
            "removed_servers": [],
        }

        # Calculate cutoff time
        cutoff_time = time.time() - max_age_seconds

        # Find and remove stale servers
        with self.server_lock:
            for server_id, server_info in list(self.known_servers.items()):
                # Skip our own server
                if server_id == self.server_id:
                    continue

                # Check if server is stale
                if server_info.last_seen < cutoff_time:
                    # Get feature hash before removing
                    feature_hash = server_info.feature_set.feature_hash

                    # Remove server
                    del self.known_servers[server_id]

                    # Remove from feature groups
                    if (
                        feature_hash in self.feature_groups
                        and server_id in self.feature_groups[feature_hash]
                    ):
                        self.feature_groups[feature_hash].remove(server_id)

                    # Add to removed list
                    result["removed_servers"].append(server_id)

        # Update result
        result["removed_count"] = len(result["removed_servers"])

        return result

    def register_task_handler(self, task_type: str, handler: Callable) -> Dict[str, Any]:
        """
        Register a handler for a specific task type.

        Args:
            task_type: Type of task the handler can process
            handler: Function to handle the task

        Returns:
            Dict with registration status
        """
        # Prepare result
        result = {
            "success": True,
            "operation": "register_task_handler",
            "timestamp": time.time(),
            "task_type": task_type,
        }

        # Register handler
        self.task_handlers[task_type] = handler

        return result

    def dispatch_task(
        self,
        task_type: str,
        task_data: Any,
        required_features: Optional[List[str]] = None,
        preferred_server_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dispatch a task to a compatible server.

        Args:
            task_type: Type of task to dispatch
            task_data: Data for the task
            required_features: Features required to process the task
            preferred_server_id: ID of preferred server to use

        Returns:
            Dict with dispatch status and results
        """
        # Prepare result
        result = {
            "success": False,
            "operation": "dispatch_task",
            "timestamp": time.time(),
            "task_type": task_type,
        }

        # Check if we can handle the task locally
        can_handle_locally = task_type in self.task_handlers

        # If specific features are required, check if we have them
        if required_features and not self.feature_set.can_handle_request(required_features):
            can_handle_locally = False

        # If we can handle locally, do it
        if can_handle_locally and (
            preferred_server_id is None or preferred_server_id == self.server_id
        ):
            try:
                # Call task handler
                handler = self.task_handlers[task_type]
                task_result = handler(task_data)

                # Update statistics
                self.stats["tasks_processed"] += 1

                # Update result
                result["success"] = True
                result["server_id"] = self.server_id
                result["task_result"] = task_result
                result["processed_locally"] = True

                return result
            except Exception as e:
                logger.error(f"Error processing task locally: {e}")
                # Fall through to remote processing

        # Find a compatible server to handle the task
        target_server_id = None
        target_server = None

        # Use preferred server if specified
        if preferred_server_id and preferred_server_id != self.server_id:
            with self.server_lock:
                if preferred_server_id in self.known_servers:
                    server_info = self.known_servers[preferred_server_id]

                    # Check if server has required features
                    if not required_features or server_info.feature_set.can_handle_request(
                        required_features
                    ):
                        # Check if server is healthy
                        if server_info.health_status.get("healthy", False):
                            target_server_id = preferred_server_id
                            target_server = server_info

        # Find another compatible server if preferred server not available
        if target_server_id is None:
            compatible_servers = self.get_compatible_servers(feature_requirements=required_features)

            if (
                compatible_servers.get("success", False)
                and compatible_servers.get("server_count", 0) > 0
            ):
                # Pick a random compatible server
                server_dict = random.choice(compatible_servers["servers"])
                target_server_id = server_dict["server_id"]

                with self.server_lock:
                    if target_server_id in self.known_servers:
                        target_server = self.known_servers[target_server_id]

        # If we didn't find a suitable server, return error
        if target_server_id is None or target_server is None:
            result["error"] = "No compatible server found for task"
            return result

        # Dispatch task to the selected server
        try:
            # Update statistics
            self.stats["tasks_dispatched"] += 1

            # Create a simulated successful result for now
            # In a real implementation, this would involve:
            # 1. Creating a task request message
            # 2. Sending it to the target server
            # 3. Waiting for a response
            # 4. Processing the response

            # For now, we'll just simulate a successful result
            task_result = {
                "success": True,
                "message": f"Task {task_type} processed by {target_server_id}",
                "timestamp": time.time(),
            }

            # Update our result
            result["success"] = True
            result["server_id"] = target_server_id
            result["task_result"] = task_result
            result["processed_locally"] = False

            return result

        except Exception as e:
            logger.error(f"Error dispatching task to server {target_server_id}: {e}")
            result["error"] = f"Error dispatching task: {str(e)}"
            return result

    def handle_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a message from another MCP server.

        Args:
            message_data: Message data received

        Returns:
            Dict with handling status and response
        """
        # Prepare result
        result = {
            "success": False,
            "operation": "handle_message",
            "timestamp": time.time(),
        }

        try:
            # Extract message type
            message_type = message_data.get("message_type")

            if not message_type:
                result["error"] = "Missing message type"
                return result

            # Handle different message types
            if message_type == MCPMessageType.ANNOUNCE:
                # Handle server announcement
                if "server_info" in message_data:
                    # Register the server
                    register_result = self.register_server(message_data["server_info"])

                    # Copy registration result
                    result.update(register_result)

                    # Update statistics
                    self.stats["announcements_received"] += 1
                else:
                    result["error"] = "Missing server info in announcement"

            elif message_type == MCPMessageType.CAPABILITIES:
                # Handle capabilities message
                if "server_info" in message_data:
                    # Update server capabilities
                    register_result = self.register_server(message_data["server_info"])

                    # Copy registration result
                    result.update(register_result)
                else:
                    result["error"] = "Missing server info in capabilities message"

            elif message_type == MCPMessageType.HEALTH:
                # Handle health check request/response
                if "server_id" in message_data:
                    # Check health of requested server
                    server_id = message_data["server_id"]
                    health_result = self.check_server_health(server_id)

                    # Copy health result
                    result.update(health_result)
                else:
                    result["error"] = "Missing server ID in health message"

            elif message_type == MCPMessageType.TASK_REQUEST:
                # Handle task request
                if "task_type" in message_data and "task_data" in message_data:
                    # Process task
                    task_type = message_data["task_type"]
                    task_data = message_data["task_data"]

                    if task_type in self.task_handlers:
                        # Call task handler
                        handler = self.task_handlers[task_type]
                        task_result = handler(task_data)

                        # Update result
                        result["success"] = True
                        result["task_result"] = task_result

                        # Update statistics
                        self.stats["tasks_received"] += 1
                        self.stats["tasks_processed"] += 1
                    else:
                        result["error"] = f"No handler for task type: {task_type}"
                else:
                    result["error"] = "Missing task information in task request"

            elif message_type == MCPMessageType.DISCOVERY:
                # Handle server discovery request
                discovery_result = self.discover_servers()

                # Copy discovery result
                result.update(discovery_result)

                # Update statistics
                self.stats["discovery_requests"] += 1

            elif message_type == MCPMessageType.SHUTDOWN:
                # Handle graceful shutdown notification
                if "server_id" in message_data:
                    # Remove the server
                    remove_result = self.remove_server(message_data["server_id"])

                    # Copy removal result
                    result.update(remove_result)
                else:
                    result["error"] = "Missing server ID in shutdown message"

            else:
                result["error"] = f"Unknown message type: {message_type}"

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            result["error"] = f"Error handling message: {str(e)}"

        return result

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the discovery model.

        Returns:
            Dict with statistics
        """
        # Prepare result
        result = {"success": True, "operation": "get_stats", "timestamp": time.time()}

        # Update uptime
        uptime = time.time() - self.stats["start_time"]

        # Count servers by role
        role_counts = {}
        with self.server_lock:
            for server_info in self.known_servers.values():
                role = server_info.role
                if role not in role_counts:
                    role_counts[role] = 0
                role_counts[role] += 1

        # Add stats to result
        result["stats"] = {
            "uptime": uptime,
            "servers_discovered": self.stats["servers_discovered"],
            "known_servers": len(self.known_servers),
            "servers_by_role": role_counts,
            "announcements_sent": self.stats["announcements_sent"],
            "announcements_received": self.stats["announcements_received"],
            "tasks_dispatched": self.stats["tasks_dispatched"],
            "tasks_received": self.stats["tasks_received"],
            "tasks_processed": self.stats["tasks_processed"],
            "discovery_requests": self.stats["discovery_requests"],
            "health_checks": self.stats["health_checks"],
        }

        return result

    def reset(self) -> Dict[str, Any]:
        """
        Reset the discovery model, clearing all state.

        Returns:
            Dict with reset status
        """
        # Prepare result
        result = {"success": True, "operation": "reset", "timestamp": time.time()}

        # Save start time
        start_time = self.stats["start_time"]

        # Clear known servers
        with self.server_lock:
            self.known_servers = {}
            self.feature_groups = {}

        # Reset statistics
        self.stats = {
            "servers_discovered": 0,
            "announcements_sent": 0,
            "announcements_received": 0,
            "tasks_dispatched": 0,
            "tasks_received": 0,
            "tasks_processed": 0,
            "discovery_requests": 0,
            "health_checks": 0,
            "start_time": start_time,  # Preserve start time
        }

        return result