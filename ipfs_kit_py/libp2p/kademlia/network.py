"""
Kademlia network implementation for libp2p.

This module implements a Kademlia Distributed Hash Table (DHT) for content
routing in libp2p. The implementation provides the core functionality needed 
for finding content providers and announcing content availability.

Key features:
- Content provider announcement
- Provider discovery
- Peer discovery
- Content value storage and retrieval
- Integration with the libp2p network stack
"""

import anyio
import json
import logging
import random
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple, Union

try:
    import base58
except ImportError:
    # Fallback implementation if base58 is not available
    class FallbackBase58:
        @staticmethod
        def b58decode(v):
            """Simple fallback for base58 decode."""
            # This is a basic implementation of base58 decoding
            # It's not as efficient as the real base58 library but will work for testing
            ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
            result = 0
            for c in v:
                result = result * 58 + ALPHABET.find(c)
            # Convert to bytes with big endian
            return result.to_bytes((result.bit_length() + 7) // 8, 'big')
            
    base58 = FallbackBase58

# Import constants or create defaults
try:
    from ipfs_kit_py.libp2p.tools.constants import (
        ALPHA_VALUE,
        MAX_PROVIDERS_PER_KEY,
        CLOSER_PEER_COUNT
    )
except ImportError:
    # Default values if constants module not available
    ALPHA_VALUE = 3
    MAX_PROVIDERS_PER_KEY = 20
    CLOSER_PEER_COUNT = 16

# Configure logger
logger = logging.getLogger(__name__)

class Provider:
    """Provider information for a key."""
    
    def __init__(self, peer_id, addrs=None):
        """Initialize provider with peer ID and addresses."""
        self.peer_id = peer_id
        self.addrs = addrs or []
        self.timestamp = time.time()
    
    def __str__(self):
        """String representation of provider."""
        return f"Provider(peer_id={self.peer_id}, addrs_count={len(self.addrs)})"
        
    def __repr__(self):
        """Detailed representation of provider."""
        return f"Provider(peer_id={self.peer_id}, addrs={self.addrs}, timestamp={self.timestamp})"
        
    def to_dict(self):
        """Convert provider to dictionary representation."""
        return {
            "id": str(self.peer_id),
            "addrs": [str(addr) for addr in self.addrs],
            "timestamp": self.timestamp
        }

class KademliaServer:
    """Kademlia DHT server implementation.
    
    This implements a simplified Kademlia DHT for content routing in libp2p.
    It provides functionality for announcing content availability and
    discovering peers that can provide specific content.
    """
    
    # Protocol versions that this implementation supports
    # Following semver: MAJOR.MINOR.PATCH
    SUPPORTED_PROTOCOL_VERSIONS = [
        "/ipfs/kad/1.0.0",  # Original version
        "/ipfs/kad/2.0.0",  # Enhanced with proper iterative lookups and distance calculations
    ]
    DEFAULT_PROTOCOL_VERSION = "/ipfs/kad/2.0.0"  # Preferred version
    
    def __init__(self, peer_id, key_pair=None, protocol_id=None, endpoint=None, ksize=20, alpha=ALPHA_VALUE):
        """Initialize the Kademlia server.
        
        Args:
            peer_id: The peer ID of this node
            key_pair: Optional key pair for signing
            protocol_id: Protocol ID for Kademlia messages
            endpoint: Host to use for network communication
            ksize: Size of k-buckets (maximum number of peers per bucket)
            alpha: Alpha parameter for parallel lookups
        """
        self.peer_id = peer_id
        self.key_pair = key_pair
        
        # Set protocol version, validating against supported versions
        if protocol_id:
            if protocol_id in self.SUPPORTED_PROTOCOL_VERSIONS:
                self.protocol_id = protocol_id
            else:
                logger.warning(f"Unsupported protocol version {protocol_id}, falling back to {self.DEFAULT_PROTOCOL_VERSION}")
                self.protocol_id = self.DEFAULT_PROTOCOL_VERSION
        else:
            self.protocol_id = self.DEFAULT_PROTOCOL_VERSION
            
        self.endpoint = endpoint
        self.ksize = ksize
        self.alpha = alpha
        
        # Storage for providers
        self.providers = {}  # key -> List[Provider]
        
        # Storage for values
        self.storage = {}  # key -> value
        
        # Storage for seen message IDs to prevent duplicate processing
        self.seen_messages = set()
        self.max_seen_messages = 1000
        
        # Track the last time we did a refresh
        self.last_refresh = time.time()
        
        # Initialize active lookups tracking
        self.active_lookups = {}
        
        # Track announced keys for periodic republishing
        self.announced_keys = set()
        
        logger.debug(f"Initialized KademliaServer with peer_id={peer_id}, ksize={ksize}, alpha={alpha}, protocol={self.protocol_id}")
        
    async def negotiate_protocol_version(self, peer_id, timeout=10):
        """Negotiate the Kademlia protocol version with a peer.
        
        This implements protocol negotiation by selecting the highest
        mutually supported version between this node and the peer.
        
        Args:
            peer_id: The peer to negotiate with
            timeout: Maximum negotiation time in seconds
            
        Returns:
            The negotiated protocol version or None if negotiation failed
        """
        try:
            # In a complete implementation, this would:
            # 1. Open a stream to the peer using multistream select
            # 2. Propose supported protocol versions
            # 3. Receive peer's supported versions
            # 4. Select highest mutually supported version
            
            # For this simplified implementation, we'll simulate successful negotiation
            supported_versions = self.SUPPORTED_PROTOCOL_VERSIONS
            
            # If we have an endpoint with protocol negotiation capabilities, use it
            if self.endpoint and hasattr(self.endpoint, "negotiate_protocol"):
                return await self.endpoint.negotiate_protocol(peer_id, supported_versions, timeout)
            
            # Fallback to default protocol version if no negotiation is possible
            return self.DEFAULT_PROTOCOL_VERSION
            
        except Exception as e:
            logger.debug(f"Protocol negotiation failed with peer {peer_id}: {e}")
            return None
    
    async def bootstrap(self, bootstrap_nodes=None):
        """Bootstrap the DHT with initial nodes.
        
        Args:
            bootstrap_nodes: List of nodes to use for bootstrapping
        
        Returns:
            Number of successfully contacted bootstrap nodes
        """
        if bootstrap_nodes is None:
            bootstrap_nodes = []  # Use empty list if none provided
        
        logger.debug(f"Bootstrapping DHT with {len(bootstrap_nodes)} nodes")
        
        # Track successful bootstraps
        successful = 0
        
        # Ping each bootstrap node
        for node in bootstrap_nodes:
            try:
                # Send a ping to verify the node is alive
                response = await self._send_ping(node)
                if response:
                    successful += 1
                    
                    # Perform a lookup of our own ID to populate routing table
                    if successful == 1:  # Only do this once
                        await self.find_peer(str(self.peer_id))
            except Exception as e:
                logger.debug(f"Error bootstrapping with node {node}: {str(e)}")
        
        logger.info(f"Successfully bootstrapped with {successful} nodes")
        return successful
    
    async def provide(self, key, timeout=30):
        """Announce that this peer can provide a value for the given key.
        
        This implementation follows the Kademlia protocol by:
        1. Finding the closest peers to the key
        2. Sending them AddProvider messages
        3. Tracking the key for periodic republishing
        
        Args:
            key: The key (usually a CID) to announce
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if announcement was successful, False otherwise
        """
        try:
            logger.debug(f"Announcing provider for key: {key}")
            
            # Add to local storage first
            if self.endpoint:
                self._add_provider(key, self.peer_id, self.endpoint.get_addrs())
            else:
                self._add_provider(key, self.peer_id, [])
            
            # Track for periodic republishing
            self.announced_keys.add(key)
            
            # Generate lookup ID from key
            lookup_id = str(key)  # Simplified for this implementation
            
            # Create a set to track peers we've already announced to
            announced_peers = set()
            success_count = 0
            
            # Find the closest peers to the key
            closest_peers = []
            if self.endpoint and hasattr(self.endpoint, "get_routing_table"):
                routing_table = self.endpoint.get_routing_table()
                if routing_table:
                    closest_peers = routing_table.get_closest_peers(lookup_id, CLOSER_PEER_COUNT)
            
            # If we couldn't get peers from the routing table, try to find them through the DHT
            if not closest_peers and self.endpoint:
                try:
                    # Use find_peer with a dummy peer ID to populate routing table
                    # This is a common Kademlia trick
                    await self.find_peer(self.peer_id, timeout=timeout/2)
                    
                    # Try getting peers from routing table again
                    if hasattr(self.endpoint, "get_routing_table"):
                        routing_table = self.endpoint.get_routing_table()
                        if routing_table:
                            closest_peers = routing_table.get_closest_peers(lookup_id, CLOSER_PEER_COUNT)
                except Exception as e:
                    logger.warning(f"Error finding closest peers: {e}")
            
            # If we still don't have any peers, return partial success
            # (we've stored locally at least)
            if not closest_peers:
                logger.info(f"No peers found to announce provider for key {key}, stored locally")
                return True
            
            # Send AddProvider messages to the closest peers
            start_time = time.time()
            for peer in closest_peers:
                # Check timeout
                if time.time() - start_time > timeout:
                    logger.warning(f"Provider announcement timed out after {success_count} successful announcements")
                    break
                    
                peer_id = peer.get("id") if isinstance(peer, dict) else str(peer)
                
                # Skip if we've already announced to this peer
                if peer_id in announced_peers:
                    continue
                
                # Track this peer
                announced_peers.add(peer_id)
                
                # Send AddProvider message
                success = await self._send_add_provider(peer_id, key)
                if success:
                    success_count += 1
            
            # Consider the operation successful if we announced to at least one peer
            # or if we stored locally (always true)
            logger.debug(f"Successfully announced provider for key {key} to {success_count} peers")
            return True
            
        except Exception as e:
            logger.error(f"Error providing key {key}: {str(e)}")
            return False
    
    async def _send_add_provider(self, peer_id, key):
        """Send AddProvider message to a peer.
        
        Args:
            peer_id: ID of the peer to send to
            key: The key we're providing
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # In a complete implementation, we would:
            # 1. Open a stream to the peer using the Kademlia protocol
            # 2. Send an AddProvider message with our peer ID and addresses
            # 3. Parse the response to confirm receipt
            
            # For this simplified implementation, we'll simulate sending the message
            if self.endpoint and hasattr(self.endpoint, "send_add_provider"):
                return await self.endpoint.send_add_provider(
                    peer_id, 
                    key, 
                    self.peer_id, 
                    self.endpoint.get_addrs() if hasattr(self.endpoint, "get_addrs") else []
                )
            
            # If no endpoint, pretend we sent it successfully
            return True
            
        except Exception as e:
            logger.debug(f"Error sending AddProvider to peer {peer_id} for key {key}: {e}")
            return False
    
    async def find_providers(self, key, count=MAX_PROVIDERS_PER_KEY, timeout=30):
        """Find peers that can provide a value for the given key.
        
        Args:
            key: The key (usually a CID) to find providers for
            count: Maximum number of providers to return
            timeout: Maximum time to wait in seconds
            
        Returns:
            List of Provider objects
        """
        try:
            logger.debug(f"Finding providers for key: {key}")
            
            # Check local storage first
            local_providers = self._get_providers(key)
            
            # Start with what we know locally
            providers = local_providers.copy() if local_providers else []
            
            # Check if we have enough providers locally
            if providers and len(providers) >= count:
                logger.debug(f"Found enough providers locally for {key}")
                return providers[:count]
            
            # Create a lookup ID from the key
            lookup_id = str(key)  # Simplified for this implementation
            
            # Track closest peers we've found
            closest_peers = []
            queried_peers = set()
            
            # Start with up to alpha closest known peers
            if self.endpoint and hasattr(self.endpoint, "get_routing_table"):
                routing_table = self.endpoint.get_routing_table()
                if routing_table:
                    closest_peers = routing_table.get_closest_peers(lookup_id, self.alpha)
            
            # If we don't have a routing table or couldn't get peers, return what we have locally
            if not closest_peers:
                logger.debug(f"No peers found in routing table for key {key}")
                # Return any local providers we have
                providers.sort(key=lambda p: p.timestamp, reverse=True)
                return providers[:count]
            
            # Track active lookup
            lookup_id = f"find-providers-{key}-{time.time()}"
            self.active_lookups[lookup_id] = {
                "start_time": time.time(),
                "target": key,
                "closest_peers": [],
                "queried_peers": set(),
                "found_providers": len(providers)
            }
            
            # Main lookup loop
            start_time = time.time()
            while closest_peers and time.time() - start_time < timeout:
                # Break if we have enough providers
                if len(providers) >= count:
                    break
                    
                # Get the next peers to query (up to alpha)
                peers_to_query = []
                for peer in closest_peers[:self.alpha]:
                    peer_id = peer.get("id") if isinstance(peer, dict) else str(peer)
                    if peer_id not in queried_peers:
                        peers_to_query.append(peer)
                        queried_peers.add(peer_id)
                
                if not peers_to_query:
                    break  # No more peers to query
                
                # Query these peers in parallel
                query_results = await self._query_peers_for_providers(peers_to_query, key, timeout)
                
                # Process results and update closest_peers
                for result in query_results:
                    # Add any providers we found
                    if result and "providers" in result:
                        for provider_info in result["providers"]:
                            # Create Provider object from info
                            if isinstance(provider_info, dict):
                                provider_id = provider_info.get("id") or provider_info.get("peer_id")
                                addrs = provider_info.get("addrs") or provider_info.get("multiaddrs") or []
                                
                                # Check if we already have this provider
                                existing = False
                                for existing_provider in providers:
                                    if existing_provider.peer_id == provider_id:
                                        existing = True
                                        # Update addresses if needed
                                        if addrs:
                                            existing_provider.addrs = addrs
                                            existing_provider.timestamp = time.time()
                                        break
                                
                                if not existing:
                                    # Add new provider
                                    providers.append(Provider(provider_id, addrs))
                    
                    # Add newly discovered peers to our list
                    if result and "closest" in result:
                        for new_peer in result["closest"]:
                            new_id = new_peer.get("id") if isinstance(new_peer, dict) else str(new_peer)
                            if new_id not in queried_peers:
                                closest_peers.append(new_peer)
                
                # Re-sort closest peers
                closest_peers.sort(key=lambda p: self._distance(str(p.get("id") if isinstance(p, dict) else p), lookup_id))
            
            # Clean up active lookup
            if lookup_id in self.active_lookups:
                self.active_lookups[lookup_id]["found_providers"] = len(providers)
                self.active_lookups[lookup_id]["end_time"] = time.time()
            
            # Sort providers by timestamp (most recent first) and return up to count
            providers.sort(key=lambda p: p.timestamp, reverse=True)
            return providers[:count]
            
        except Exception as e:
            logger.error(f"Error finding providers for key {key}: {str(e)}")
            return []
    
    async def _query_peers_for_providers(self, peers, key, timeout):
        """Query a list of peers for providers of a key.
        
        Args:
            peers: List of peers to query
            key: The key we're looking for providers for
            timeout: Maximum time to wait
            
        Returns:
            List of query results from peers
        """
        tasks = []
        for peer in peers:
            peer_id = peer.get("id") if isinstance(peer, dict) else str(peer)
            task = self._query_peer_for_providers(peer_id, key, timeout)
            tasks.append(task)
            
        # Wait for all queries to complete or timeout
        try:
            results = await anyio.gather(*tasks, return_exceptions=True)
            
            # Process results, filtering out exceptions
            valid_results = []
            for result in results:
                if isinstance(result, Exception):
                    logger.debug(f"Query error: {result}")
                    continue
                valid_results.append(result)
                
            return valid_results
            
        except Exception as e:
            logger.error(f"Error querying peers for providers: {e}")
            return []
    
    async def _query_peer_for_providers(self, peer_id, key, timeout, max_retries=2):
        """Query a specific peer for providers of a key with retry logic.
        
        Args:
            peer_id: ID of the peer to query
            key: The key we're looking for providers for
            timeout: Maximum time to wait
            max_retries: Maximum number of retry attempts
            
        Returns:
            Query result or None if failed
        """
        retries = 0
        backoff_time = 0.5  # Start with 500ms backoff
        
        while retries <= max_retries:
            try:
                # If this isn't the first attempt, wait with exponential backoff
                if retries > 0:
                    await anyio.sleep(backoff_time)
                    # Double backoff time for next retry (exponential backoff)
                    backoff_time *= 2
                    logger.debug(f"Retry {retries}/{max_retries} querying peer {peer_id} for providers of {key}")
                
                # Before querying, negotiate protocol version if not yet done
                protocol_id = await self.negotiate_protocol_version(peer_id, timeout=min(timeout, 5))
                if not protocol_id:
                    # If we can't negotiate a protocol, try the default
                    protocol_id = self.DEFAULT_PROTOCOL_VERSION
                
                # In a complete implementation, we would:
                # 1. Open a stream to the peer using the negotiated Kademlia protocol
                # 2. Send a GetProviders message for the key
                # 3. Parse the response and return results
                
                # Try sending with the specified protocol version
                if self.endpoint and hasattr(self.endpoint, "send_get_providers"):
                    result = await self.endpoint.send_get_providers(peer_id, key, timeout, protocol_id=protocol_id)
                    
                    # If successful, return immediately
                    if result is not None:
                        return result
                else:
                    # Return empty result if no endpoint
                    return {"providers": [], "closest": []}
                
                # Increment retry counter only for specific errors that warrant a retry
                # For this example, if result is None, we'll retry
                retries += 1
                
            except Exception as e:
                error_type = type(e).__name__
                
                # Determine if this error is retryable
                retryable_errors = [
                    "ConnectionError",
                    "TimeoutError", 
                    "StreamResetError",
                    "ProtocolNotSupportedError",
                    "TemporaryFailure"
                ]
                
                # Check if this is a retryable error
                if error_type in retryable_errors:
                    logger.debug(f"Retryable error ({error_type}) querying peer {peer_id} for providers of {key}: {e}")
                    retries += 1
                    continue
                else:
                    # Non-retryable error
                    logger.debug(f"Non-retryable error ({error_type}) querying peer {peer_id} for providers of {key}: {e}")
                    return None
        
        # If we've exhausted all retries, return None
        logger.debug(f"Failed to query peer {peer_id} for providers of {key} after {max_retries} retries")
        return None
    
    async def get_providers(self, key, count=MAX_PROVIDERS_PER_KEY):
        """Alias for find_providers for compatibility with libp2p."""
        return await self.find_providers(key, count)
        
    async def get_value(self, key):
        """Alias for find_value for compatibility with libp2p."""
        return await self.find_value(key)
        
    async def put_value(self, key, value):
        """Alias for store_value for compatibility with libp2p."""
        return await self.store_value(key, value)
    
    async def find_peer(self, peer_id, timeout=30):
        """Find specified peer in the DHT.
        
        Args:
            peer_id: The peer ID to find
            timeout: Maximum time to wait in seconds
            
        Returns:
            List of peer info dictionaries, or empty list if not found
        """
        try:
            logger.debug(f"Finding peer: {peer_id}")
            
            # Create a lookup ID from the peer ID hash
            lookup_id = str(peer_id)  # Simplified for this implementation
            
            # Track closest peers we've found
            closest_peers = []
            queried_peers = set()
            
            # Start with up to alpha closest known peers
            if self.endpoint and hasattr(self.endpoint, "get_routing_table"):
                routing_table = self.endpoint.get_routing_table()
                if routing_table:
                    closest_peers = routing_table.get_closest_peers(lookup_id, self.alpha)
            
            # If we don't have a routing table or couldn't get peers, return empty
            if not closest_peers:
                logger.debug(f"No peers found in routing table for {peer_id}")
                return []
            
            # Set up progress tracking
            found_peer = False
            peer_info = None
            
            # Track active lookups
            lookup_id = f"find-peer-{peer_id}-{time.time()}"
            self.active_lookups[lookup_id] = {
                "start_time": time.time(),
                "target": peer_id,
                "closest_peers": [],
                "queried_peers": set(),
                "found": False
            }
            
            # Main lookup loop
            start_time = time.time()
            while closest_peers and time.time() - start_time < timeout:
                # Get the next peers to query (up to alpha)
                peers_to_query = []
                for peer in closest_peers[:self.alpha]:
                    peer_id = peer.get("id") if isinstance(peer, dict) else str(peer)
                    if peer_id not in queried_peers:
                        peers_to_query.append(peer)
                        queried_peers.add(peer_id)
                
                if not peers_to_query:
                    break  # No more peers to query
                
                # Query these peers in parallel
                query_results = await self._query_peers_for_peer(peers_to_query, peer_id, timeout)
                
                # Process results and update closest_peers
                for result in query_results:
                    # Check if we found the target peer
                    if result and "peers" in result:
                        for p in result["peers"]:
                            p_id = p.get("id") if isinstance(p, dict) else str(p)
                            if p_id == peer_id:
                                found_peer = True
                                peer_info = p
                                break
                    
                    # Add newly discovered peers to our list
                    if result and "closest" in result:
                        for new_peer in result["closest"]:
                            new_id = new_peer.get("id") if isinstance(new_peer, dict) else str(new_peer)
                            if new_id not in queried_peers:
                                closest_peers.append(new_peer)
                
                # If we found the target peer, stop looking
                if found_peer:
                    break
                
                # Re-sort closest peers (using heuristic of peer ID for this simplified implementation)
                closest_peers.sort(key=lambda p: self._distance(str(p.get("id") if isinstance(p, dict) else p), lookup_id))
            
            # Clean up active lookup
            if lookup_id in self.active_lookups:
                self.active_lookups[lookup_id]["found"] = found_peer
                self.active_lookups[lookup_id]["end_time"] = time.time()
            
            # Return the peer info if found, otherwise empty list
            if found_peer and peer_info:
                return [peer_info]
            return []
            
        except Exception as e:
            logger.error(f"Error finding peer {peer_id}: {str(e)}")
            return []
    
    def _distance(self, id1, id2):
        """Calculate the XOR distance between two IDs."""
        return calculate_xor_distance(id1, id2)
        
# Helper functions for consistent ID handling and distance calculation
def normalize_id_to_bytes(id_str_or_bytes):
    """Normalize an ID to bytes consistently.
    
    Args:
        id_str_or_bytes: ID as string or bytes
        
    Returns:
        Bytes representation of the ID
    """
    if isinstance(id_str_or_bytes, bytes):
        return id_str_or_bytes
    
    if isinstance(id_str_or_bytes, str):
        if id_str_or_bytes.startswith("Qm") or id_str_or_bytes.startswith("12"):  # Base58 CID or PeerID
            try:
                return base58.b58decode(id_str_or_bytes)
            except Exception as e:
                logger.debug(f"Error decoding base58 ID: {e}, falling back to UTF-8")
                pass  # Fall back to UTF-8
        
        # Default to UTF-8
        return id_str_or_bytes.encode('utf-8')
    
    # Unexpected type, just convert to string and then bytes
    return str(id_str_or_bytes).encode('utf-8')

def calculate_xor_distance(id1, id2):
    """Calculate the XOR distance between two IDs consistently.
    
    This implements the proper Kademlia XOR distance metric. It handles different
    ID formats (string, bytes, base58-encoded) and ensures consistent results.
    
    Args:
        id1: First ID (string or bytes)
        id2: Second ID (string or bytes)
        
    Returns:
        Integer representing the XOR distance
    """
    # Normalize IDs to bytes with proper encoding
    id1_bytes = normalize_id_to_bytes(id1)
    id2_bytes = normalize_id_to_bytes(id2)
    
    # Ensure both IDs have the same length
    max_len = max(len(id1_bytes), len(id2_bytes))
    id1_bytes = id1_bytes.ljust(max_len, b'\x00')
    id2_bytes = id2_bytes.ljust(max_len, b'\x00')
    
    # Calculate XOR distance (as an integer for easy comparison)
    distance = 0
    for i in range(max_len):
        byte_distance = id1_bytes[i] ^ id2_bytes[i]
        # Left-shift based on byte position for proper distance ordering
        # This ensures MSB differences are more significant
        distance |= byte_distance << (8 * (max_len - i - 1))
            
    return distance
    
    async def _query_peers_for_peer(self, peers, target_peer_id, timeout):
        """Query a list of peers for information about a target peer.
        
        Args:
            peers: List of peers to query
            target_peer_id: The peer ID we're looking for
            timeout: Maximum time to wait
            
        Returns:
            List of query results from peers
        """
        tasks = []
        for peer in peers:
            peer_id = peer.get("id") if isinstance(peer, dict) else str(peer)
            task = self._query_peer_for_peer(peer_id, target_peer_id, timeout)
            tasks.append(task)
            
        # Wait for all queries to complete or timeout
        try:
            results = await anyio.gather(*tasks, return_exceptions=True)
            
            # Process results, filtering out exceptions
            valid_results = []
            for result in results:
                if isinstance(result, Exception):
                    logger.debug(f"Query error: {result}")
                    continue
                valid_results.append(result)
                
            return valid_results
            
        except Exception as e:
            logger.error(f"Error querying peers: {e}")
            return []
    
    async def _query_peer_for_peer(self, peer_id, target_peer_id, timeout, max_retries=2):
        """Query a specific peer for information about a target peer with retry logic.
        
        Args:
            peer_id: ID of the peer to query
            target_peer_id: ID of the peer we're looking for
            timeout: Maximum time to wait
            max_retries: Maximum number of retry attempts
            
        Returns:
            Query result or None if failed
        """
        retries = 0
        backoff_time = 0.5  # Start with 500ms backoff
        
        while retries <= max_retries:
            try:
                # If this isn't the first attempt, wait with exponential backoff
                if retries > 0:
                    await anyio.sleep(backoff_time)
                    # Double backoff time for next retry (exponential backoff)
                    backoff_time *= 2
                    logger.debug(f"Retry {retries}/{max_retries} querying peer {peer_id} for peer {target_peer_id}")
                
                # Before querying, negotiate protocol version if not yet done
                protocol_id = await self.negotiate_protocol_version(peer_id, timeout=min(timeout, 5))
                if not protocol_id:
                    # If we can't negotiate a protocol, try the default
                    protocol_id = self.DEFAULT_PROTOCOL_VERSION
                
                # In a complete implementation, we would:
                # 1. Open a stream to the peer using the negotiated Kademlia protocol
                # 2. Send a FindNode message for the target peer
                # 3. Parse the response and return results
                
                # Try sending with the specified protocol version
                if self.endpoint and hasattr(self.endpoint, "send_find_node"):
                    result = await self.endpoint.send_find_node(peer_id, target_peer_id, timeout, protocol_id=protocol_id)
                    
                    # If successful, return immediately
                    if result is not None:
                        return result
                else:
                    # Return empty result if no endpoint
                    return {"peers": [], "closest": []}
                
                # Increment retry counter only for specific errors that warrant a retry
                # For this example, if result is None, we'll retry
                retries += 1
                
            except Exception as e:
                error_type = type(e).__name__
                
                # Determine if this error is retryable
                retryable_errors = [
                    "ConnectionError",
                    "TimeoutError",
                    "StreamResetError",
                    "ProtocolNotSupportedError",
                    "TemporaryFailure"
                ]
                
                # Check if this is a retryable error
                if error_type in retryable_errors:
                    logger.debug(f"Retryable error ({error_type}) querying peer {peer_id} for peer {target_peer_id}: {e}")
                    retries += 1
                    continue
                else:
                    # Non-retryable error
                    logger.debug(f"Non-retryable error ({error_type}) querying peer {peer_id} for peer {target_peer_id}: {e}")
                    return None
        
        # If we've exhausted all retries, return None
        logger.debug(f"Failed to query peer {peer_id} for peer {target_peer_id} after {max_retries} retries")
        return None
    
    async def find_value(self, key, timeout=30):
        """Find a value in the DHT.
        
        Args:
            key: The key to find
            timeout: Maximum time to wait in seconds
            
        Returns:
            The value if found, None otherwise
        """
        try:
            # Check local storage first
            if key in self.storage:
                logger.debug(f"Found value for key {key} in local storage")
                return self.storage[key]
                
            logger.debug(f"Finding value for key: {key}")
            
            # Create a lookup ID from the key
            lookup_id = str(key)  # Simplified for this implementation
            
            # Track closest peers we've found
            closest_peers = []
            queried_peers = set()
            
            # Start with up to alpha closest known peers
            if self.endpoint and hasattr(self.endpoint, "get_routing_table"):
                routing_table = self.endpoint.get_routing_table()
                if routing_table:
                    closest_peers = routing_table.get_closest_peers(lookup_id, self.alpha)
            
            # If we don't have a routing table or couldn't get peers, return None
            if not closest_peers:
                logger.debug(f"No peers found in routing table for key {key}")
                return None
            
            # Set up progress tracking
            found_value = None
            
            # Track active lookup
            lookup_id = f"find-value-{key}-{time.time()}"
            self.active_lookups[lookup_id] = {
                "start_time": time.time(),
                "target": key,
                "closest_peers": [],
                "queried_peers": set(),
                "found": False
            }
            
            # Main lookup loop
            start_time = time.time()
            while closest_peers and time.time() - start_time < timeout:
                # Get the next peers to query (up to alpha)
                peers_to_query = []
                for peer in closest_peers[:self.alpha]:
                    peer_id = peer.get("id") if isinstance(peer, dict) else str(peer)
                    if peer_id not in queried_peers:
                        peers_to_query.append(peer)
                        queried_peers.add(peer_id)
                
                if not peers_to_query:
                    break  # No more peers to query
                
                # Query these peers in parallel
                query_results = await self._query_peers_for_value(peers_to_query, key, timeout)
                
                # Process results and update closest_peers
                for result in query_results:
                    # Check if we found the value
                    if result and "value" in result:
                        found_value = result["value"]
                        break
                    
                    # Add newly discovered peers to our list
                    if result and "closest" in result:
                        for new_peer in result["closest"]:
                            new_id = new_peer.get("id") if isinstance(new_peer, dict) else str(new_peer)
                            if new_id not in queried_peers:
                                closest_peers.append(new_peer)
                
                # If we found the value, stop looking
                if found_value is not None:
                    break
                
                # Re-sort closest peers
                closest_peers.sort(key=lambda p: self._distance(str(p.get("id") if isinstance(p, dict) else p), lookup_id))
            
            # Clean up active lookup
            if lookup_id in self.active_lookups:
                self.active_lookups[lookup_id]["found"] = found_value is not None
                self.active_lookups[lookup_id]["end_time"] = time.time()
            
            # If we found the value, store it locally and implement caching along the return path
            if found_value is not None:
                logger.debug(f"Found value for key {key} in DHT")
                self.storage[key] = found_value
                
                # Implement Kademlia's caching along the return path
                # Store the value at the k/2 closest nodes that we queried but didn't have the value
                # This speeds up future retrievals by creating cached copies closer to requestors
                try:
                    # Sort peers we've queried by XOR distance to the key
                    sorted_peers = sorted(
                        list(queried_peers),
                        key=lambda p: calculate_xor_distance(p, key)
                    )
                    
                    # Take the closest k/2 peers (half of the k-bucket size)
                    cache_limit = min(len(sorted_peers), self.ksize // 2)
                    closest_peers_for_caching = sorted_peers[:cache_limit]
                    
                    # Cache the value at these peers in parallel
                    cache_tasks = []
                    for peer_id in closest_peers_for_caching:
                        task = self._send_store_value(peer_id, key, found_value)
                        cache_tasks.append(task)
                    
                    # Wait for all cache operations to complete or timeout
                    if cache_tasks:
                        logger.debug(f"Caching value for key {key} along return path at {len(cache_tasks)} peers")
                        # Use a short timeout to avoid delaying the response
                        cache_results = await anyio.gather(*cache_tasks, return_exceptions=True)
                        successful_caches = sum(1 for r in cache_results if r is True)
                        logger.debug(f"Successfully cached at {successful_caches}/{len(cache_tasks)} peers")
                except Exception as e:
                    # Don't let caching errors affect the main operation
                    logger.warning(f"Error during return path caching for key {key}: {e}")
            
            return found_value
            
        except Exception as e:
            logger.error(f"Error finding value for key {key}: {str(e)}")
            return None
    
    async def _query_peers_for_value(self, peers, key, timeout):
        """Query a list of peers for a value.
        
        Args:
            peers: List of peers to query
            key: The key we're looking for
            timeout: Maximum time to wait
            
        Returns:
            List of query results from peers
        """
        tasks = []
        for peer in peers:
            peer_id = peer.get("id") if isinstance(peer, dict) else str(peer)
            task = self._query_peer_for_value(peer_id, key, timeout)
            tasks.append(task)
            
        # Wait for all queries to complete or timeout
        try:
            results = await anyio.gather(*tasks, return_exceptions=True)
            
            # Process results, filtering out exceptions
            valid_results = []
            for result in results:
                if isinstance(result, Exception):
                    logger.debug(f"Query error: {result}")
                    continue
                valid_results.append(result)
                
            return valid_results
            
        except Exception as e:
            logger.error(f"Error querying peers for value: {e}")
            return []
    
    async def _query_peer_for_value(self, peer_id, key, timeout, max_retries=2):
        """Query a specific peer for a value with retry logic for transient failures.
        
        Args:
            peer_id: ID of the peer to query
            key: The key we're looking for
            timeout: Maximum time to wait
            max_retries: Maximum number of retry attempts
            
        Returns:
            Query result or None if failed
        """
        retries = 0
        backoff_time = 0.5  # Start with 500ms backoff
        
        while retries <= max_retries:
            try:
                # If this isn't the first attempt, wait with exponential backoff
                if retries > 0:
                    await anyio.sleep(backoff_time)
                    # Double backoff time for next retry (exponential backoff)
                    backoff_time *= 2
                    logger.debug(f"Retry {retries}/{max_retries} querying peer {peer_id} for value of {key}")
                
                # Before querying, negotiate protocol version if not yet done
                protocol_id = await self.negotiate_protocol_version(peer_id, timeout=min(timeout, 5))
                if not protocol_id:
                    # If we can't negotiate a protocol, try the default
                    protocol_id = self.DEFAULT_PROTOCOL_VERSION
                    
                # In a complete implementation, we would:
                # 1. Open a stream to the peer using the negotiated Kademlia protocol
                # 2. Send a FindValue message for the key
                # 3. Parse the response and return results
                
                # Try sending with the specified protocol version
                if self.endpoint and hasattr(self.endpoint, "send_find_value"):
                    result = await self.endpoint.send_find_value(peer_id, key, timeout, protocol_id=protocol_id)
                    
                    # If successful, return immediately
                    if result is not None:
                        return result
                else:
                    # Return empty result if no endpoint
                    return {"value": None, "closest": []}
                    
                # Increment retry counter only for specific errors that warrant a retry
                # For this example, if result is None, we'll retry
                retries += 1
                
            except Exception as e:
                error_type = type(e).__name__
                
                # Determine if this error is retryable
                retryable_errors = [
                    "ConnectionError",
                    "TimeoutError",
                    "StreamResetError",
                    "ProtocolNotSupportedError",
                    "TemporaryFailure"
                ]
                
                # Check if this is a retryable error
                if error_type in retryable_errors:
                    logger.debug(f"Retryable error ({error_type}) querying peer {peer_id} for value of {key}: {e}")
                    retries += 1
                    continue
                else:
                    # Non-retryable error
                    logger.debug(f"Non-retryable error ({error_type}) querying peer {peer_id} for value of {key}: {e}")
                    return None
        
        # If we've exhausted all retries, return None
        logger.debug(f"Failed to query peer {peer_id} for value of {key} after {max_retries} retries")
        return None
    
    async def store_value(self, key, value, timeout=30, replicate=True):
        """Store a value in the DHT.
        
        This implementation follows the Kademlia protocol by:
        1. Storing the value locally
        2. Finding the closest peers to the key
        3. Sending them store requests to replicate the value
        
        Args:
            key: The key under which to store the value
            value: The value to store
            timeout: Maximum time to wait in seconds
            replicate: Whether to replicate the value to other peers
            
        Returns:
            True if storing was successful, False otherwise
        """
        try:
            logger.debug(f"Storing value for key: {key}")
            
            # Store locally first
            self.storage[key] = value
            
            # If we don't want to replicate, return success after local storage
            if not replicate:
                logger.debug(f"Value stored locally for key {key}, no replication requested")
                return True
                
            # Generate lookup ID from key
            lookup_id = str(key)
            
            # Create a set to track peers we've already sent to
            store_peers = set()
            success_count = 0
            
            # Find the closest peers to the key
            closest_peers = []
            if self.endpoint and hasattr(self.endpoint, "get_routing_table"):
                routing_table = self.endpoint.get_routing_table()
                if routing_table:
                    closest_peers = routing_table.get_closest_peers(lookup_id, CLOSER_PEER_COUNT)
            
            # If we couldn't get peers from the routing table, try to find them through the DHT
            if not closest_peers and self.endpoint:
                try:
                    # Use find_peer with a dummy peer ID to populate routing table
                    await self.find_peer(self.peer_id, timeout=timeout/2)
                    
                    # Try getting peers from routing table again
                    if hasattr(self.endpoint, "get_routing_table"):
                        routing_table = self.endpoint.get_routing_table()
                        if routing_table:
                            closest_peers = routing_table.get_closest_peers(lookup_id, CLOSER_PEER_COUNT)
                except Exception as e:
                    logger.warning(f"Error finding closest peers: {e}")
            
            # If we still don't have any peers, return partial success
            # (we've stored locally at least)
            if not closest_peers:
                logger.info(f"No peers found to replicate value for key {key}, stored locally")
                return True
            
            # Send store requests to the closest peers
            start_time = time.time()
            for peer in closest_peers:
                # Check timeout
                if time.time() - start_time > timeout:
                    logger.warning(f"Store operation timed out after {success_count} successful replications")
                    break
                    
                peer_id = peer.get("id") if isinstance(peer, dict) else str(peer)
                
                # Skip if we've already sent to this peer
                if peer_id in store_peers:
                    continue
                    
                # Track this peer
                store_peers.add(peer_id)
                
                # Send store request
                success = await self._send_store_value(peer_id, key, value)
                if success:
                    success_count += 1
            
            # Consider the operation successful if we replicated to at least one peer
            # or if we stored locally (always true)
            logger.debug(f"Successfully stored value for key {key}, replicated to {success_count} peers")
            return True
            
        except Exception as e:
            logger.error(f"Error storing value for key {key}: {str(e)}")
            return False
    
    async def _send_store_value(self, peer_id, key, value, max_retries=2):
        """Send a store request to a peer with retry logic for transient failures.
        
        Args:
            peer_id: ID of the peer to send to
            key: The key under which to store the value
            value: The value to store
            max_retries: Maximum number of retry attempts
            
        Returns:
            True if successful, False otherwise
        """
        retries = 0
        backoff_time = 0.5  # Start with 500ms backoff
        
        while retries <= max_retries:
            try:
                # If this isn't the first attempt, wait with exponential backoff
                if retries > 0:
                    await anyio.sleep(backoff_time)
                    # Double backoff time for next retry (exponential backoff)
                    backoff_time *= 2
                    logger.debug(f"Retry {retries}/{max_retries} sending Store to peer {peer_id} for key {key}")
                
                # Before sending, negotiate protocol version if not yet done
                protocol_id = await self.negotiate_protocol_version(peer_id, timeout=5)
                if not protocol_id:
                    # If we can't negotiate a protocol, try the default
                    protocol_id = self.DEFAULT_PROTOCOL_VERSION
                
                # In a complete implementation, we would:
                # 1. Open a stream to the peer using the Kademlia protocol
                # 2. Send a Store message with the key and value
                # 3. Parse the response to confirm receipt
                
                # For this simplified implementation, we'll simulate sending the message
                if self.endpoint and hasattr(self.endpoint, "send_store"):
                    result = await self.endpoint.send_store(peer_id, key, value, protocol_id=protocol_id)
                    
                    # If successful, return immediately
                    if result:
                        return True
                    
                    # If result is False (not None), it means the operation failed but in a way that might succeed with a retry
                    retries += 1
                    continue
                
                # If no endpoint, pretend we sent it successfully
                return True
                
            except Exception as e:
                error_type = type(e).__name__
                
                # Determine if this error is retryable
                retryable_errors = [
                    "ConnectionError",
                    "TimeoutError",
                    "StreamResetError",
                    "ProtocolNotSupportedError",
                    "TemporaryFailure"
                ]
                
                # Check if this is a retryable error
                if error_type in retryable_errors:
                    logger.debug(f"Retryable error ({error_type}) sending Store to peer {peer_id} for key {key}: {e}")
                    retries += 1
                    continue
                else:
                    # Non-retryable error
                    logger.debug(f"Non-retryable error ({error_type}) sending Store to peer {peer_id} for key {key}: {e}")
                    return False
        
        # If we've exhausted all retries, return False
        logger.debug(f"Failed to send Store to peer {peer_id} for key {key} after {max_retries} retries")
        return False
    
    def _add_provider(self, key, peer_id, addrs=None):
        """Add a provider for a key to local storage.
        
        Args:
            key: The key (usually a CID)
            peer_id: The peer ID of the provider
            addrs: List of multiaddresses for the peer
            
        Returns:
            None
        """
        # Initialize provider list if needed
        if key not in self.providers:
            self.providers[key] = []
            
        # Check if provider already exists
        for provider in self.providers[key]:
            if provider.peer_id == peer_id:
                # Update addresses and timestamp
                provider.addrs = addrs or []
                provider.timestamp = time.time()
                return
                
        # Add new provider
        self.providers[key].append(Provider(peer_id, addrs))
        
        # Limit number of providers per key
        if len(self.providers[key]) > MAX_PROVIDERS_PER_KEY:
            # Sort by timestamp (newest first) and trim
            self.providers[key].sort(key=lambda p: p.timestamp, reverse=True)
            self.providers[key] = self.providers[key][:MAX_PROVIDERS_PER_KEY]
    
    def _get_providers(self, key):
        """Get providers for a key from local storage.
        
        Args:
            key: The key (usually a CID)
            
        Returns:
            List of Provider objects
        """
        return self.providers.get(key, [])
    
    async def _send_ping(self, node):
        """Send a ping to a node to check if it's alive.
        
        Args:
            node: The node to ping
            
        Returns:
            True if ping was successful, False otherwise
        """
        try:
            # In a full implementation, this would send a ping message
            # to the node and wait for a response.
            #
            # For our mock implementation, we just return success
            return True
            
        except Exception as e:
            logger.debug(f"Error pinging node {node}: {str(e)}")
            return False
            
    async def refresh(self, republish=True, refresh_buckets=True, bucket_count=5, timeout=60):
        """Refresh the DHT routing table and republish keys.
        
        This enhanced implementation follows the Kademlia protocol by:
        1. Refreshing k-buckets by performing lookups for IDs in each bucket
        2. Prioritizing buckets that need refreshing based on age, usage, and fullness
        3. Republishing stored keys and provider announcements with importance-based ordering
        4. Periodic cleanup of expired data
        5. Metrics tracking for optimization
        
        Args:
            republish: Whether to republish announced keys
            refresh_buckets: Whether to refresh routing table buckets
            bucket_count: Maximum number of buckets to refresh
            timeout: Maximum time to spend on refresh operation
            
        Returns:
            True if refresh was successful, False otherwise
        """
        try:
            logger.debug("Refreshing DHT routing table")
            
            # Update last refresh time
            self.last_refresh = time.time()
            refresh_start = time.time()
            
            # Track operation metrics
            metrics = {
                "bucket_refreshes": 0,
                "bucket_refresh_failures": 0,
                "keys_republished": 0,
                "republish_failures": 0,
                "skipped_buckets": 0,
                "skipped_keys": 0,
                "routing_table_nodes": 0,
                "total_time": 0
            }
            
            # First, clean up expired entries in seen_messages and storage
            self._clean_seen_messages()
            self._expire_old_data()
            
            # Refresh buckets by performing lookups for IDs in each bucket
            if refresh_buckets and self.endpoint:
                # Get the routing table if available
                routing_table = None
                if hasattr(self.endpoint, "get_routing_table"):
                    routing_table = self.endpoint.get_routing_table()
                
                # Identify buckets that need refreshing
                buckets_to_refresh = self._identify_priority_buckets(routing_table, bucket_count)
                
                # Refresh each selected bucket
                refreshed_buckets = 0
                for bucket_idx in buckets_to_refresh:
                    # Check if we're out of time
                    if time.time() - refresh_start > timeout:
                        logger.warning(f"Refresh operation timed out after {refreshed_buckets}/{len(buckets_to_refresh)} bucket refreshes")
                        metrics["skipped_buckets"] = len(buckets_to_refresh) - refreshed_buckets
                        break
                        
                    try:
                        # Generate a random ID in this bucket
                        random_id = self._generate_random_id_in_bucket(bucket_idx)
                        
                        # Perform lookup to populate routing table with carefully managed timeout
                        remaining_time = timeout - (time.time() - refresh_start)
                        bucket_timeout = min(10, max(1, remaining_time / (len(buckets_to_refresh) - refreshed_buckets)))
                        
                        logger.debug(f"Refreshing bucket {bucket_idx} with lookup for ID {random_id} (timeout: {bucket_timeout:.1f}s)")
                        await self.find_peer(random_id, timeout=bucket_timeout)
                        metrics["bucket_refreshes"] += 1
                        refreshed_buckets += 1
                        
                        # Mark bucket as refreshed if the method is available
                        if routing_table and hasattr(routing_table, "mark_bucket_refreshed"):
                            routing_table.mark_bucket_refreshed(bucket_idx)
                        
                    except Exception as e:
                        logger.warning(f"Error refreshing bucket {bucket_idx}: {e}")
                        metrics["bucket_refresh_failures"] += 1
                
                # Track stats
                if routing_table and hasattr(routing_table, "size"):
                    metrics["routing_table_nodes"] = routing_table.size()
                
                logger.debug(f"Successfully refreshed {refreshed_buckets} buckets")
            
            # Check for timeout before proceeding to republishing
            if time.time() - refresh_start > timeout:
                logger.warning("Refresh operation timed out before republishing keys")
                metrics["total_time"] = time.time() - refresh_start
                return metrics["bucket_refreshes"] > 0
            
            # Republish announced keys (content provider records)
            if republish and self.announced_keys:
                # Get prioritized keys to republish
                keys_to_republish = self._get_prioritized_keys_for_republish(timeout - (time.time() - refresh_start))
                
                # Republish keys
                for key, priority in keys_to_republish:
                    # Check if we're out of time
                    if time.time() - refresh_start > timeout:
                        logger.warning(f"Republish operation timed out after {metrics['keys_republished']}/{len(keys_to_republish)} keys")
                        metrics["skipped_keys"] = len(keys_to_republish) - metrics["keys_republished"]
                        break
                        
                    try:
                        # Calculate appropriate timeout based on priority and remaining time
                        remaining_time = timeout - (time.time() - refresh_start)
                        key_timeout = min(10, max(1, remaining_time / (len(keys_to_republish) - metrics["keys_republished"])))
                        
                        # Use weighted timeout based on priority - more important keys get more time
                        key_timeout = min(key_timeout * (0.5 + priority/2), remaining_time)
                        
                        # Republish with calculated timeout
                        await self.provide(key, timeout=key_timeout)
                        metrics["keys_republished"] += 1
                        
                    except Exception as e:
                        logger.warning(f"Error republishing key {key}: {e}")
                        metrics["republish_failures"] += 1
            else:
                logger.debug("Skipping republish - no announced keys or republish disabled")
            
            # Calculate success based on overall operations
            success = metrics["bucket_refreshes"] > 0 or metrics["keys_republished"] > 0
            
            # Record total time
            metrics["total_time"] = time.time() - refresh_start
            
            # Log performance metrics
            logger.debug(f"DHT refresh completed in {metrics['total_time']:.2f}s: "
                        f"{metrics['bucket_refreshes']} buckets refreshed, "
                        f"{metrics['keys_republished']} keys republished")
            
            return success
            
        except Exception as e:
            logger.error(f"Error refreshing DHT: {str(e)}")
            return False
            
    def _identify_priority_buckets(self, routing_table, bucket_count):
        """Identify which routing table buckets need refreshing with priority ordering.
        
        This method provides smart bucket prioritization based on:
        1. Age of bucket (older buckets have higher priority)
        2. Fullness of bucket (emptier buckets have higher priority)
        3. Distance from local ID (further buckets have higher priority)
        4. Usage statistics (less used buckets have higher priority)
        
        Args:
            routing_table: The routing table if available
            bucket_count: Maximum number of buckets to refresh
            
        Returns:
            List of bucket indices to refresh, prioritized
        """
        buckets_to_refresh = []
        
        # First approach: use needs_refresh method if available (most efficient)
        if routing_table and hasattr(routing_table, "needs_refresh"):
            buckets_to_refresh = routing_table.needs_refresh()
            logger.debug(f"Found {len(buckets_to_refresh)} buckets that need refreshing")
            # Limit to requested count
            if len(buckets_to_refresh) > bucket_count:
                # Prioritize buckets with higher indices (more distant peers)
                buckets_to_refresh.sort(reverse=True)
                buckets_to_refresh = buckets_to_refresh[:bucket_count]
            return buckets_to_refresh
            
        # Second approach: manually analyze the routing table buckets
        elif routing_table and hasattr(routing_table, "buckets"):
            # Use dictionary-style buckets with sparse representation
            if isinstance(routing_table.buckets, dict):
                # Create a priority score for each bucket
                now = time.time()
                bucket_priorities = []
                
                for bucket_idx, bucket in routing_table.buckets.items():
                    # Skip empty buckets
                    if not bucket or len(bucket) == 0:
                        continue
                        
                    # Calculate bucket age if possible
                    bucket_age = None
                    if hasattr(bucket, "last_updated"):
                        bucket_age = now - bucket.last_updated
                    
                    # Calculate priority score
                    score = self._calculate_bucket_priority(
                        bucket_idx, bucket, bucket_age, routing_table.bucket_size
                    )
                    
                    bucket_priorities.append((bucket_idx, score))
                
                # Sort buckets by priority score (highest first)
                bucket_priorities.sort(key=lambda x: x[1], reverse=True)
                
                # Take the highest priority buckets up to bucket_count
                buckets_to_refresh = [b[0] for b in bucket_priorities[:bucket_count]]
                logger.debug(f"Selected {len(buckets_to_refresh)} priority buckets from dictionary structure")
                return buckets_to_refresh
                
            # Use list-style buckets with fixed representation
            elif isinstance(routing_table.buckets, list):
                now = time.time()
                bucket_priorities = []
                
                for i, bucket in enumerate(routing_table.buckets):
                    if not bucket:  # Skip empty buckets
                        continue
                        
                    # Calculate bucket age if possible
                    bucket_age = None
                    if hasattr(bucket, "last_updated"):
                        bucket_age = now - bucket.last_updated
                    
                    # Calculate priority score
                    score = self._calculate_bucket_priority(
                        i, bucket, bucket_age, 
                        routing_table.bucket_size if hasattr(routing_table, "bucket_size") else 20
                    )
                    
                    bucket_priorities.append((i, score))
                
                # Sort buckets by priority score (highest first)
                bucket_priorities.sort(key=lambda x: x[1], reverse=True)
                
                # Take the highest priority buckets up to bucket_count
                buckets_to_refresh = [b[0] for b in bucket_priorities[:bucket_count]]
                logger.debug(f"Selected {len(buckets_to_refresh)} priority buckets from list structure")
                return buckets_to_refresh
        
        # Fallback: random selection of buckets
        buckets_to_refresh = random.sample(range(256), min(bucket_count, 256))
        logger.debug(f"Selected {len(buckets_to_refresh)} random buckets for refresh")
        return buckets_to_refresh
    
    def _calculate_bucket_priority(self, bucket_idx, bucket, bucket_age, bucket_size):
        """Calculate a priority score for a routing table bucket.
        
        Higher scores indicate higher refresh priority.
        
        Args:
            bucket_idx: Index of the bucket
            bucket: The bucket object
            bucket_age: Age of the bucket in seconds since last update
            bucket_size: Maximum capacity of the bucket
            
        Returns:
            Priority score (higher is more important to refresh)
        """
        score = 0
        
        # Factor 1: Age - Older buckets have higher priority
        # Score increases with age (up to 10 points for buckets >24 hours old)
        if bucket_age is not None:
            hours_old = bucket_age / 3600
            score += min(10, hours_old / 2.4)  # Max 10 points at 24 hours
        
        # Factor 2: Fullness - Less filled buckets have higher priority
        # We want to discover more peers for sparse buckets
        if hasattr(bucket, "__len__") and bucket_size > 0:
            fullness = len(bucket) / bucket_size
            # Score increases as fullness decreases (up to 8 points for empty buckets)
            score += 8 * (1 - fullness)
        
        # Factor 3: Distance - Further buckets have higher priority
        # This ensures better coverage of the ID space
        # Add up to 6 points for distance (buckets far from our ID)
        normalized_distance = bucket_idx / 256 if isinstance(bucket_idx, int) else 0
        score += 6 * normalized_distance
        
        # Factor 4: Usage - Less used buckets need more refresh
        if hasattr(bucket, "usage_count"):
            # Normalize usage - lower is better (up to 4 points for unused buckets)
            normalized_usage = min(1.0, bucket.usage_count / 100)
            score += 4 * (1 - normalized_usage)
        
        return score
        
    def _get_prioritized_keys_for_republish(self, available_time):
        """Get a prioritized list of keys to republish based on age and importance.
        
        Args:
            available_time: Time available for republishing in seconds
            
        Returns:
            List of (key, priority) tuples ordered by priority (higher first)
        """
        if not self.announced_keys:
            return []
            
        # Take a snapshot of the announced keys
        announced_keys = list(self.announced_keys)
        logger.debug(f"Prioritizing {len(announced_keys)} keys for republishing")
        
        # Calculate priority for each key based on age and other factors
        key_priorities = []
        now = time.time()
        
        for key in announced_keys:
            # Start with default priority
            priority = 0.5  # 0-1 scale, higher is more important
            
            # Factor 1: Age of provider record
            age = 0
            if key in self.providers:
                # Find oldest provider timestamp
                for provider in self.providers[key]:
                    if provider.timestamp < now - age:
                        age = now - provider.timestamp
            
            # Normalize age to 0-1 (1.0 = REPUBLISH_INTERVAL old)
            normalized_age = min(1.0, age / REPUBLISH_INTERVAL)
            priority += 0.4 * normalized_age  # Age contributes up to 0.4 to priority
            
            # Factor 2: Content importance
            # For this implementation, we assume all keys are equally important
            # In a real system, you might track popularity or other metrics
            
            # Skip keys that don't need republishing yet (less than 25% of republish interval)
            if normalized_age < 0.25:
                logger.debug(f"Skipping recent key {key} (age: {age/3600:.1f}h)")
                continue
                
            key_priorities.append((key, priority))
        
        # Sort by priority (highest first)
        key_priorities.sort(key=lambda x: x[1], reverse=True)
        
        # Adjust number of keys based on available time
        # Assume we need roughly 1 second per key (conservative estimate)
        keys_to_republish = key_priorities[:min(len(key_priorities), int(available_time))]
        
        logger.debug(f"Selected {len(keys_to_republish)} keys for republishing")
        return keys_to_republish
    
    def _expire_old_data(self):
        """Clean up expired data from storage and provider records."""
        # Remove expired seen messages
        self._clean_seen_messages()
        
        # Clean up old provider records
        now = time.time()
        expiration_time = REPUBLISH_INTERVAL * 2  # Expire after 2x republish interval
        expired_keys = []
        
        for key, providers in self.providers.items():
            # Remove individual expired providers
            valid_providers = []
            for provider in providers:
                if now - provider.timestamp < expiration_time:
                    valid_providers.append(provider)
            
            # Update or mark key for removal
            if valid_providers:
                self.providers[key] = valid_providers
            else:
                expired_keys.append(key)
        
        # Remove empty provider entries
        for key in expired_keys:
            del self.providers[key]
            # Also remove from announced keys if present
            if key in self.announced_keys:
                self.announced_keys.remove(key)
        
        # Log cleanup results
        if expired_keys:
            logger.debug(f"Expired {len(expired_keys)} provider records during cleanup")
    
    def _clean_seen_messages(self):
        """Clean up old seen message IDs to prevent memory growth."""
        if len(self.seen_messages) > self.max_seen_messages:
            # Remove oldest entries
            overflow = len(self.seen_messages) - (self.max_seen_messages // 2)
            if overflow > 0:
                # Convert to list, sort by age, and keep only the newest messages
                # In a real implementation we would track timestamps for each message
                # For this simple implementation, just remove random entries
                message_ids = list(self.seen_messages)
                random.shuffle(message_ids)
                for msg_id in message_ids[:overflow]:
                    self.seen_messages.remove(msg_id)
                    
                logger.debug(f"Cleaned up {overflow} old message IDs")
    
    def _generate_random_id_in_bucket(self, bucket_idx):
        """Generate a random ID that falls within the given bucket.
        
        Args:
            bucket_idx: The index of the bucket (0-255)
            
        Returns:
            A random ID string
        """
        # Start with local peer ID
        if hasattr(self, 'peer_id') and self.peer_id:
            base_id = str(self.peer_id)
        else:
            # Generate a random ID if we don't have a peer ID
            base_id = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=32))
            
        # Convert to byte array for manipulation
        id_bytes = bytearray(base_id.encode('utf-8'))
        
        # Bit manipulation to ensure the ID falls in the desired bucket
        # This is a simplified version to demonstrate the concept
        byte_idx = bucket_idx // 8
        bit_pos = bucket_idx % 8
        
        if byte_idx < len(id_bytes):
            # Flip the bit at the specified position
            id_bytes[byte_idx] ^= (1 << bit_pos)
            
            # Randomize all bits after this position
            for i in range(byte_idx, len(id_bytes)):
                # For the first byte, only randomize bits after the flipped bit
                if i == byte_idx:
                    mask = (1 << bit_pos) - 1
                    id_bytes[i] = (id_bytes[i] & ~mask) | (random.randint(0, 255) & mask)
                else:
                    # For all other bytes, completely randomize
                    id_bytes[i] = random.randint(0, 255)
                    
        # Convert back to string
        return id_bytes.decode('utf-8', errors='replace')