"""
libp2p model for MCP integration.

This model provides access to direct peer-to-peer communication functionality
using libp2p, without requiring the full IPFS daemon. It enables peer discovery,
content routing, and direct content exchange between peers.
"""

import logging
import os
import time
import json
from typing import Dict, List, Any, Optional, Union

# Core IPFS Kit imports
from ipfs_kit_py.error import (
    IPFSConnectionError,
    IPFSTimeoutError,
    IPFSContentNotFoundError
)

# Check libp2p availability
from ipfs_kit_py.libp2p import HAS_LIBP2P, check_dependencies, install_dependencies

# Import libp2p peer if available
if HAS_LIBP2P:
    from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer, LibP2PError
    # Apply protocol extensions
    from ipfs_kit_py.libp2p import apply_protocol_extensions_to_instance
    # Import DHT discovery
    from ipfs_kit_py.libp2p import get_enhanced_dht_discovery
    EnhancedDHTDiscovery = get_enhanced_dht_discovery()

# Configure logger
logger = logging.getLogger(__name__)

class LibP2PModel:
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
            "last_operation_time": time.time(),
        }
        
        # Check if libp2p is available
        if not HAS_LIBP2P:
            check_dependencies()  # Re-check in case something changed
            if not HAS_LIBP2P:
                if self.metadata.get("auto_install_dependencies", False):
                    logger.info("Auto-installing libp2p dependencies...")
                    install_dependencies()
                else:
                    logger.warning("libp2p dependencies are not available. P2P functionality will be limited.")
        
        # Initialize libp2p peer
        if libp2p_peer_instance:
            # Use provided instance
            self.libp2p_peer = libp2p_peer_instance
            logger.info("Using provided libp2p peer instance")
        elif HAS_LIBP2P:
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
            except Exception as e:
                logger.error(f"Failed to create libp2p peer: {str(e)}")
                self.libp2p_peer = None
        else:
            # libp2p not available
            self.libp2p_peer = None
            logger.warning("libp2p functionality disabled due to missing dependencies")
    
    def is_available(self) -> bool:
        """
        Check if libp2p functionality is available.
        
        Returns:
            bool: True if libp2p is available, False otherwise
        """
        return HAS_LIBP2P and self.libp2p_peer is not None
    
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
        if not self.is_available():
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
        if not self.is_available():
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
        if not self.is_available():
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
        if not self.is_available():
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
        if not self.is_available():
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
        if not self.is_available():
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
        if not self.is_available():
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
        if not self.is_available():
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
        if not self.is_available():
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
        return {
            "success": True,
            "operation": "get_stats",
            "timestamp": time.time(),
            "stats": self.operation_stats,
            "uptime": time.time() - self.operation_stats["start_time"]
        }