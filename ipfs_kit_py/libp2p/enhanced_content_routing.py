"""
Enhanced Content Routing for libp2p Integration with MCP Server.

This module provides advanced content routing and discovery mechanisms for libp2p,
going beyond basic DHT-based content routing to provide more reliable and
efficient content discovery and retrieval.
"""

import os
import sys
import time
import asyncio
import logging
import json
from typing import Dict, List, Any, Optional, Callable, Union, Tuple, Set
import threading
import random
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_TTL = 3600  # 1 hour cache TTL
MAX_PROVIDERS = 50  # Maximum providers to track per CID
REPUTATION_BOOST = 5  # Reputation boost for successful content provision
REPUTATION_PENALTY = 2  # Reputation penalty for failed content provision


class ContentProviderEntry:
    """Represents a content provider for a specific CID."""
    
    def __init__(self, peer_id: str, source: str = "unknown"):
        """
        Initialize a content provider entry.
        
        Args:
            peer_id: The peer ID of the provider
            source: Where this provider info came from (e.g., 'dht', 'local', 'pubsub')
        """
        self.peer_id = peer_id
        self.source = source
        self.first_seen = time.time()
        self.last_verified = 0  # 0 means never verified
        self.success_count = 0
        self.failure_count = 0
        self.last_success = 0
        self.last_failure = 0
        self.latency_ms = []  # List of latencies in milliseconds
        self.avg_latency_ms = 0
        self.reputation = 0  # Provider reputation score
    
    def record_success(self, latency_ms: Optional[float] = None):
        """
        Record a successful content retrieval.
        
        Args:
            latency_ms: Optional latency of the retrieval in milliseconds
        """
        self.success_count += 1
        self.last_success = time.time()
        self.last_verified = time.time()
        self.reputation += REPUTATION_BOOST
        
        # Update latency tracking
        if latency_ms is not None:
            self.latency_ms.append(latency_ms)
            # Keep only last 10 latency measurements
            if len(self.latency_ms) > 10:
                self.latency_ms.pop(0)
            # Update average latency
            self.avg_latency_ms = sum(self.latency_ms) / len(self.latency_ms)
    
    def record_failure(self):
        """Record a failed content retrieval."""
        self.failure_count += 1
        self.last_failure = time.time()
        self.reputation = max(0, self.reputation - REPUTATION_PENALTY)
    
    def is_reliable(self) -> bool:
        """Check if this provider is considered reliable."""
        if self.success_count == 0:
            return False
        
        if self.failure_count > self.success_count * 2:
            return False
            
        if self.reputation <= 0:
            return False
            
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the entry to a dictionary representation."""
        return {
            "peer_id": self.peer_id,
            "source": self.source,
            "first_seen": self.first_seen,
            "last_verified": self.last_verified,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_success": self.last_success,
            "last_failure": self.last_failure,
            "avg_latency_ms": self.avg_latency_ms,
            "reputation": self.reputation,
            "is_reliable": self.is_reliable(),
        }


class CIDProviderCache:
    """Cache of content providers for CIDs."""
    
    def __init__(self, max_providers: int = MAX_PROVIDERS, ttl: int = DEFAULT_TTL):
        """
        Initialize the CID provider cache.
        
        Args:
            max_providers: Maximum number of providers to track per CID
            ttl: Time-to-live for cache entries in seconds
        """
        self.providers = {}  # Map of CID to list of ContentProviderEntry
        self.max_providers = max_providers
        self.ttl = ttl
        self.lock = threading.RLock()
    
    def add_provider(self, cid: str, peer_id: str, source: str = "unknown"):
        """
        Add a provider for a CID.
        
        Args:
            cid: The content ID
            peer_id: The provider peer ID
            source: The source of this provider information
        """
        with self.lock:
            # Create entry for CID if it doesn't exist
            if cid not in self.providers:
                self.providers[cid] = []
            
            # Check if provider already exists
            for provider in self.providers[cid]:
                if provider.peer_id == peer_id:
                    # Update source if applicable
                    if source != "unknown":
                        provider.source = source
                    return
            
            # Add new provider
            self.providers[cid].append(ContentProviderEntry(peer_id, source))
            
            # If we have too many providers, remove the least reliable ones
            if len(self.providers[cid]) > self.max_providers:
                self._prune_providers(cid)
    
    def get_providers(self, cid: str) -> List[ContentProviderEntry]:
        """
        Get providers for a CID.
        
        Args:
            cid: The content ID
            
        Returns:
            List of ContentProviderEntry objects
        """
        with self.lock:
            if cid not in self.providers:
                return []
            
            # Filter out expired entries
            now = time.time()
            valid_providers = [
                p for p in self.providers[cid] 
                if p.last_verified == 0 or now - p.last_verified < self.ttl
            ]
            
            # Update providers list if we filtered any out
            if len(valid_providers) != len(self.providers[cid]):
                self.providers[cid] = valid_providers
            
            return valid_providers
    
    def get_best_providers(self, cid: str, limit: int = 5) -> List[ContentProviderEntry]:
        """
        Get the best providers for a CID based on reputation and latency.
        
        Args:
            cid: The content ID
            limit: Maximum number of providers to return
            
        Returns:
            List of ContentProviderEntry objects
        """
        providers = self.get_providers(cid)
        
        # Sort providers by reliability and performance
        providers.sort(key=lambda p: (
            p.is_reliable(),  # First sort by reliability (True > False)
            p.reputation,     # Then by reputation (higher > lower)
            -p.avg_latency_ms if p.avg_latency_ms > 0 else 0,  # Then by latency (lower > higher)
            p.success_count,  # Then by success count (higher > lower)
            -p.failure_count  # Then by failure count (lower > higher)
        ), reverse=True)
        
        return providers[:limit]
    
    def record_success(self, cid: str, peer_id: str, latency_ms: Optional[float] = None):
        """
        Record a successful content retrieval.
        
        Args:
            cid: The content ID
            peer_id: The provider peer ID
            latency_ms: Optional latency in milliseconds
        """
        with self.lock:
            if cid not in self.providers:
                return
            
            for provider in self.providers[cid]:
                if provider.peer_id == peer_id:
                    provider.record_success(latency_ms)
                    return
    
    def record_failure(self, cid: str, peer_id: str):
        """
        Record a failed content retrieval.
        
        Args:
            cid: The content ID
            peer_id: The provider peer ID
        """
        with self.lock:
            if cid not in self.providers:
                return
            
            for provider in self.providers[cid]:
                if provider.peer_id == peer_id:
                    provider.record_failure()
                    return
    
    def _prune_providers(self, cid: str):
        """
        Prune the provider list for a CID to stay within max_providers.
        
        Args:
            cid: The content ID
        """
        if cid not in self.providers:
            return
        
        providers = self.providers[cid]
        
        if len(providers) <= self.max_providers:
            return
        
        # Sort providers by reliability and performance (like get_best_providers)
        providers.sort(key=lambda p: (
            p.is_reliable(),
            p.reputation,
            -p.avg_latency_ms if p.avg_latency_ms > 0 else 0,
            p.success_count,
            -p.failure_count
        ), reverse=True)
        
        # Keep only the best providers
        self.providers[cid] = providers[:self.max_providers]
    
    def remove_provider(self, cid: str, peer_id: str):
        """
        Remove a provider for a CID.
        
        Args:
            cid: The content ID
            peer_id: The provider peer ID
        """
        with self.lock:
            if cid not in self.providers:
                return
            
            self.providers[cid] = [
                p for p in self.providers[cid] if p.peer_id != peer_id
            ]
    
    def clear_cid(self, cid: str):
        """
        Clear all providers for a CID.
        
        Args:
            cid: The content ID
        """
        with self.lock:
            if cid in self.providers:
                del self.providers[cid]
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self.lock:
            total_providers = sum(len(providers) for providers in self.providers.values())
            reliable_providers = sum(
                sum(1 for p in providers if p.is_reliable())
                for providers in self.providers.values()
            )
            
            return {
                "cids": len(self.providers),
                "total_providers": total_providers,
                "reliable_providers": reliable_providers,
                "avg_providers_per_cid": total_providers / len(self.providers) if self.providers else 0
            }


class QueryResult:
    """Represents the result of a content query operation."""
    
    def __init__(self, cid: str):
        """
        Initialize a query result.
        
        Args:
            cid: The queried content ID
        """
        self.cid = cid
        self.timestamp = time.time()
        self.providers = []  # List of provider peer IDs
        self.provider_info = {}  # Map of peer_id to provider info
        self.successful = False
        self.duration_ms = 0
        self.error = None
        self.data = None  # Actual content data if retrieved
        self.data_source = None  # Peer ID that provided the data
    
    def add_provider(self, peer_id: str, info: Optional[Dict[str, Any]] = None):
        """
        Add a provider to the result.
        
        Args:
            peer_id: The provider peer ID
            info: Optional additional provider info
        """
        if peer_id not in self.providers:
            self.providers.append(peer_id)
            
            if info:
                self.provider_info[peer_id] = info
    
    def set_successful(self, duration_ms: float, data_source: Optional[str] = None):
        """
        Mark the query as successful.
        
        Args:
            duration_ms: Query duration in milliseconds
            data_source: Optional peer ID that provided the data
        """
        self.successful = True
        self.duration_ms = duration_ms
        self.data_source = data_source
    
    def set_error(self, error):
        """
        Set the error for a failed query.
        
        Args:
            error: The error that occurred
        """
        self.successful = False
        self.error = str(error)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the query result to a dictionary representation."""
        return {
            "cid": self.cid,
            "timestamp": self.timestamp,
            "providers": self.providers,
            "provider_count": len(self.providers),
            "successful": self.successful,
            "duration_ms": self.duration_ms,
            "has_data": self.data is not None,
            "data_source": self.data_source,
            "error": self.error
        }


class EnhancedContentRouter:
    """
    Enhanced Content Router for libp2p.
    
    Provides advanced content routing capabilities beyond basic DHT
    content routing, including provider reputation, multi-strategy
    discovery, and intelligent caching.
    """
    
    def __init__(self, peer, ttl: int = DEFAULT_TTL):
        """
        Initialize the enhanced content router.
        
        Args:
            peer: The libp2p peer instance
            ttl: Cache TTL in seconds
        """
        self.peer = peer
        self.provider_cache = CIDProviderCache(ttl=ttl)
        self.query_history = {}  # Map of CID to list of QueryResult
        self.max_history_per_cid = 10
        
        # Register with pubsub for provider announcements if possible
        self._setup_pubsub_discovery()
        
        # Discovery strategies and their weights
        self.strategies = [
            ("cache", self._discover_from_cache, 1.0),  # Check cache first
            ("dht", self._discover_from_dht, 0.8),  # Then check DHT
            ("pubsub", self._discover_from_pubsub, 0.6),  # Then check pubsub
            ("recursive", self._discover_recursive, 0.4),  # Then try recursive discovery
        ]
    
    def _setup_pubsub_discovery(self):
        """Set up pubsub-based content provider discovery."""
        self.pubsub_topic = "ipfs-kit/providers"
        self.pubsub_providers = {}  # Map of CID to set of provider peer IDs
        
        # Try to subscribe to the provider topic
        try:
            if hasattr(self.peer, "pubsub_subscribe") and callable(self.peer.pubsub_subscribe):
                self.peer.pubsub_subscribe(self.pubsub_topic, self._handle_provider_message)
                logger.debug(f"Subscribed to provider pubsub topic: {self.pubsub_topic}")
            else:
                logger.debug(f"Peer does not support pubsub_subscribe, pubsub discovery disabled")
        except Exception as e:
            logger.warning(f"Failed to set up pubsub discovery: {e}")
    
    def _handle_provider_message(self, message):
        """
        Handle a provider announcement message from pubsub.
        
        Args:
            message: The pubsub message
        """
        try:
            # Parse the message
            if hasattr(message, "data"):
                data = json.loads(message.data.decode("utf-8"))
            else:
                data = json.loads(message)
            
            # Get the CID and provider
            cid = data.get("cid")
            provider_id = data.get("provider")
            source = data.get("source", "pubsub")
            
            if not cid or not provider_id:
                return
            
            # Add to pubsub providers
            if cid not in self.pubsub_providers:
                self.pubsub_providers[cid] = set()
            self.pubsub_providers[cid].add(provider_id)
            
            # Add to provider cache
            self.provider_cache.add_provider(cid, provider_id, source)
            
        except Exception as e:
            logger.error(f"Error handling provider message: {e}")
    
    def announce_provider(self, cid: str):
        """
        Announce this peer as a provider for a CID.
        
        Args:
            cid: The content ID to announce for
        """
        try:
            if hasattr(self.peer, "pubsub_publish") and callable(self.peer.pubsub_publish):
                # Create provider announcement message
                message = json.dumps({
                    "cid": cid,
                    "provider": self.peer.get_peer_id(),
                    "timestamp": time.time(),
                    "ttl": DEFAULT_TTL
                }).encode("utf-8")
                
                # Publish to the provider topic
                self.peer.pubsub_publish(self.pubsub_topic, message)
                logger.debug(f"Announced provider for {cid}")
                
                # Also add ourselves to the provider cache
                self.provider_cache.add_provider(cid, self.peer.get_peer_id(), "local")
            else:
                logger.debug(f"Peer does not support pubsub_publish, provider announcement skipped")
        except Exception as e:
            logger.warning(f"Failed to announce provider for {cid}: {e}")
    
    async def find_providers(self, cid: str, limit: int = 5) -> List[str]:
        """
        Find providers for a CID using enhanced discovery strategies.
        
        Args:
            cid: The content ID to find providers for
            limit: Maximum number of providers to return
            
        Returns:
            List of provider peer IDs
        """
        # Create a new query result
        query = QueryResult(cid)
        start_time = time.time()
        
        # Try each discovery strategy in order of weight until we find enough providers
        for strategy_name, strategy_func, _ in sorted(self.strategies, key=lambda s: s[2], reverse=True):
            try:
                logger.debug(f"Trying {strategy_name} strategy for {cid}")
                providers = await strategy_func(cid)
                
                for provider in providers:
                    query.add_provider(provider)
                    
                    # Break if we have enough providers
                    if len(query.providers) >= limit:
                        break
                
                # Break if we have enough providers
                if len(query.providers) >= limit:
                    break
                    
            except Exception as e:
                logger.warning(f"Error in {strategy_name} strategy for {cid}: {e}")
        
        # Set query result information
        duration_ms = (time.time() - start_time) * 1000
        if query.providers:
            query.set_successful(duration_ms)
        else:
            query.set_error("No providers found")
        
        # Add to query history
        self._add_to_query_history(cid, query)
        
        return query.providers[:limit]
    
    async def retrieve_content(self, cid: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Retrieve content for a CID from the best available provider.
        
        Args:
            cid: The content ID to retrieve
            
        Returns:
            Tuple of (content_data, provider_id) or (None, None) if not found
        """
        # First, check if we have the content locally
        local_data = await self._check_local_content(cid)
        if local_data:
            return local_data, self.peer.get_peer_id()
        
        # Find providers
        providers = await self.find_providers(cid)
        
        if not providers:
            logger.warning(f"No providers found for {cid}")
            return None, None
        
        # Try each provider until we get the content
        for provider_id in providers:
            try:
                start_time = time.time()
                content = await self._retrieve_from_provider(cid, provider_id)
                
                if content:
                    # Record success
                    duration_ms = (time.time() - start_time) * 1000
                    self.provider_cache.record_success(cid, provider_id, duration_ms)
                    
                    # Update query history
                    for query in self._get_query_history(cid):
                        if provider_id in query.providers and not query.data_source:
                            query.data_source = provider_id
                            query.duration_ms = duration_ms
                            query.successful = True
                    
                    return content, provider_id
                else:
                    # Record failure
                    self.provider_cache.record_failure(cid, provider_id)
            except Exception as e:
                logger.warning(f"Error retrieving {cid} from {provider_id}: {e}")
                # Record failure
                self.provider_cache.record_failure(cid, provider_id)
        
        logger.warning(f"Failed to retrieve {cid} from any provider")
        return None, None
    
    async def _check_local_content(self, cid: str) -> Optional[bytes]:
        """
        Check if we have the content locally.
        
        Args:
            cid: The content ID to check
            
        Returns:
            Content data if available locally, None otherwise
        """
        try:
            # Try different methods based on what the peer supports
            if hasattr(self.peer, "get_content_data") and callable(self.peer.get_content_data):
                data = await self.peer.get_content_data(cid)
                return data
            elif hasattr(self.peer, "retrieve_content") and callable(self.peer.retrieve_content):
                data = self.peer.retrieve_content(cid)
                return data
            elif hasattr(self.peer, "has_content") and callable(self.peer.has_content):
                has_content = await self.peer.has_content(cid) if asyncio.iscoroutinefunction(self.peer.has_content) else self.peer.has_content(cid)
                
                if has_content:
                    # Try to get the data
                    if hasattr(self.peer, "get_block") and callable(self.peer.get_block):
                        data = await self.peer.get_block(cid) if asyncio.iscoroutinefunction(self.peer.get_block) else self.peer.get_block(cid)
                        return data
            
            return None
        except Exception as e:
            logger.warning(f"Error checking local content for {cid}: {e}")
            return None
    
    async def _retrieve_from_provider(self, cid: str, provider_id: str) -> Optional[bytes]:
        """
        Retrieve content from a specific provider.
        
        Args:
            cid: The content ID to retrieve
            provider_id: The provider peer ID
            
        Returns:
            Content data if successful, None otherwise
        """
        # Try direct transfer protocol if available
        if hasattr(self.peer, "request_content_direct") and callable(self.peer.request_content_direct):
            try:
                content = await self.peer.request_content_direct(provider_id, cid)
                if content:
                    return content
            except Exception as e:
                logger.debug(f"Direct transfer failed for {cid} from {provider_id}: {e}")
        
        # Otherwise try to connect and use standard bitswap
        try:
            # Connect to the peer if not already connected
            if hasattr(self.peer, "connect_peer") and callable(self.peer.connect_peer):
                connected = await self.peer.connect_peer(provider_id) if asyncio.iscoroutinefunction(self.peer.connect_peer) else self.peer.connect_peer(provider_id)
                
                if not connected:
                    logger.warning(f"Failed to connect to provider {provider_id}")
                    return None
            
            # Try to get the content using standard methods
            if hasattr(self.peer, "get_block") and callable(self.peer.get_block):
                content = await self.peer.get_block(cid) if asyncio.iscoroutinefunction(self.peer.get_block) else self.peer.get_block(cid)
                return content
                
            return None
        except Exception as e:
            logger.warning(f"Error retrieving {cid} from {provider_id}: {e}")
            return None
    
    async def _discover_from_cache(self, cid: str) -> List[str]:
        """
        Discover providers from the local cache.
        
        Args:
            cid: The content ID to find providers for
            
        Returns:
            List of provider peer IDs
        """
        # Get best providers from cache
        best_providers = self.provider_cache.get_best_providers(cid)
        return [p.peer_id for p in best_providers]
    
    async def _discover_from_dht(self, cid: str) -> List[str]:
        """
        Discover providers from the DHT.
        
        Args:
            cid: The content ID to find providers for
            
        Returns:
            List of provider peer IDs
        """
        providers = []
        
        try:
            # Try to find providers using DHT
            if hasattr(self.peer, "find_providers") and callable(self.peer.find_providers):
                dht_providers = await self.peer.find_providers(cid) if asyncio.iscoroutinefunction(self.peer.find_providers) else self.peer.find_providers(cid)
                
                # Handle different provider formats
                for provider in dht_providers:
                    if isinstance(provider, str):
                        provider_id = provider
                    elif isinstance(provider, dict) and "id" in provider:
                        provider_id = provider["id"]
                    else:
                        continue
                    
                    # Add to our result list
                    providers.append(provider_id)
                    
                    # Also add to our cache
                    self.provider_cache.add_provider(cid, provider_id, "dht")
            
            return providers
        except Exception as e:
            logger.warning(f"Error discovering providers from DHT for {cid}: {e}")
            return []
    
    async def _discover_from_pubsub(self, cid: str) -> List[str]:
        """
        Discover providers from pubsub announcements.
        
        Args:
            cid: The content ID to find providers for
            
        Returns:
            List of provider peer IDs
        """
        if cid in self.pubsub_providers:
            return list(self.pubsub_providers[cid])
        return []
    
    async def _discover_recursive(self, cid: str) -> List[str]:
        """
        Discover providers recursively by asking other peers.
        
        Args:
            cid: The content ID to find providers for
            
        Returns:
            List of provider peer IDs
        """
        providers = []
        
        # Only try recursive discovery if we have the enhanced discovery protocol
        if hasattr(self.peer, "discover_content_recursive") and callable(self.peer.discover_content_recursive):
            try:
                remote_providers = await self.peer.discover_content_recursive(cid, depth=1)
                
                # Process results
                for provider in remote_providers:
                    if isinstance(provider, dict) and "peer_id" in provider:
                        provider_id = provider["peer_id"]
                        providers.append(provider_id)
                        
                        # Add to cache
                        self.provider_cache.add_provider(cid, provider_id, "recursive")
                        
            except Exception as e:
                logger.warning(f"Error in recursive discovery for {cid}: {e}")
        
        return providers
    
    def _add_to_query_history(self, cid: str, query: QueryResult):
        """
        Add a query result to the history.
        
        Args:
            cid: The content ID
            query: The QueryResult to add
        """
        if cid not in self.query_history:
            self.query_history[cid] = []
        
        # Add the new query
        self.query_history[cid].append(query)
        
        # Keep only the most recent queries
        if len(self.query_history[cid]) > self.max_history_per_cid:
            self.query_history[cid] = self.query_history[cid][-self.max_history_per_cid:]
    
    def _get_query_history(self, cid: str) -> List[QueryResult]:
        """
        Get the query history for a CID.
        
        Args:
            cid: The content ID
            
        Returns:
            List of QueryResult objects
        """
        return self.query_history.get(cid, [])
    
    def get_providers(self, cid: str) -> List[Dict[str, Any]]:
        """
        Get all known providers for a CID.
        
        Args:
            cid: The content ID
            
        Returns:
            List of provider information dictionaries
        """
        providers = self.provider_cache.get_providers(cid)
        return [p.to_dict() for p in providers]
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get router statistics.
        
        Returns:
            Dictionary with router statistics
        """
        stats = {
            "cache_stats": self.provider_cache.get_stats(),
            "query_history": {
                "total_cids": len(self.query_history),
                "total_queries": sum(len(queries) for queries in self.query_history.values()),
                "successful_queries": sum(
                    sum(1 for q in queries if q.successful)
                    for queries in self.query_history.values()
                )
            }
        }
        
        return stats


class RecursiveContentRouter(EnhancedContentRouter):
    """
    Enhanced Content Router with recursive lookup capabilities.
    
    This router extends the base EnhancedContentRouter with more aggressive
    recursive content discovery through connected peers.
    """
    
    def __init__(self, peer, ttl: int = DEFAULT_TTL):
        """
        Initialize the recursive content router.
        
        Args:
            peer: The libp2p peer instance
            ttl: Cache TTL in seconds
        """
        super().__init__(peer, ttl)
        
        # Adjust strategy weights to favor recursive discovery
        self.strategies = [
            ("cache", self._discover_from_cache, 1.0),
            ("recursive", self._discover_recursive, 0.9),  # Higher weight for recursive
            ("dht", self._discover_from_dht, 0.8),
            ("pubsub", self._discover_from_pubsub, 0.7),
        ]
    
    async def _discover_recursive(self, cid: str) -> List[str]:
        """
        Enhanced recursive discovery that tries multiple connected peers.
        
        Args:
            cid: The content ID to find providers for
            
        Returns:
            List of provider peer IDs
        """
        providers = set()
        
        # Get connected peers
        if hasattr(self.peer, "get_connected_peers") and callable(self.peer.get_connected_peers):
            connected_peers = self.peer.get_connected_peers()
            
            # Select a random subset of peers to query
            if len(connected_peers) > 5:
                peers_to_query = random.sample(connected_peers, 5)
            else:
                peers_to_query = connected_peers
            
            # Query each peer for providers
            for peer_id in peers_to_query:
                try:
                    # Skip ourselves
                    if peer_id == self.peer.get_peer_id():
                        continue
                    
                    # Check if the peer has the enhanced discovery protocol
                    has_protocol = False
                    if hasattr(self.peer, "has_protocol") and callable(self.peer.has_protocol):
                        has_protocol = await self.peer.has_protocol(
                            peer_id, 
                            "/ipfs-kit/discovery/1.0.0"
                        ) if asyncio.iscoroutinefunction(self.peer.has_protocol) else self.peer.has_protocol(
                            peer_id, 
                            "/ipfs-kit/discovery/1.0.0"
                        )
                    
                    if has_protocol:
                        # Use the enhanced discovery protocol
                        if hasattr(self.peer, "discover_content_recursive") and callable(self.peer.discover_content_recursive):
                            remote_providers = await self.peer.discover_content_recursive(cid, depth=1)
                            
                            # Process results
                            for provider in remote_providers:
                                if isinstance(provider, dict) and "peer_id" in provider:
                                    provider_id = provider["peer_id"]
                                    providers.add(provider_id)
                                    
                                    # Add to cache
                                    self.provider_cache.add_provider(cid, provider_id, "recursive")
                    else:
                        # Try a direct DHT query
                        protocol = "/ipfs/kad/1.0.0"  # Standard DHT protocol
                        
                        if hasattr(self.peer, "open_protocol_stream") and callable(self.peer.open_protocol_stream):
                            try:
                                # Add this peer to our DHT routing table
                                if hasattr(self.peer, "add_to_routing_table") and callable(self.peer.add_to_routing_table):
                                    self.peer.add_to_routing_table(peer_id)
                                    
                                # This is a simplified version - in practice you'd need to implement the DHT protocol
                                async with await self.peer.open_protocol_stream(peer_id, protocol) as stream:
                                    # In reality you'd formulate a proper DHT FIND_PROVIDER message
                                    # This is just a placeholder for the concept
                                    await stream.write(f"FIND_PROVIDER:{cid}".encode())
                                    response = await stream.read()
                                    
                                    # Parse response
                                    # Again, this is a conceptual simplification
                                    if response:
                                        provider_ids = response.decode().split(",")
                                        for provider_id in provider_ids:
                                            if provider_id.strip():
                                                providers.add(provider_id.strip())
                                                
                                                # Add to cache
                                                self.provider_cache.add_provider(cid, provider_id, "dht_query")
                            except Exception as e:
                                logger.debug(f"Error querying peer {peer_id} for providers: {e}")
                
                except Exception as e:
                    logger.debug(f"Error in recursive provider discovery with peer {peer_id}: {e}")
        
        # Also try the base implementation
        base_providers = await super()._discover_recursive(cid)
        providers.update(base_providers)
        
        return list(providers)


def get_enhanced_dht_discovery():
    """Get the appropriate enhanced content router class based on capabilities."""
    try:
        # Check if we have recursive capabilities
        return RecursiveContentRouter
    except:
        # Fall back to base implementation
        return EnhancedContentRouter


def apply_to_peer(peer, role="seeder"):
    """
    Apply the enhanced content router to a peer.
    
    Args:
        peer: The libp2p peer instance
        role: The peer's role (seeder or leecher)
        
    Returns:
        The created content router instance
    """
    try:
        # Create the router based on role
        if role == "seeder":
            # Seeders need more aggressive content advertising
            router = RecursiveContentRouter(peer)
        else:
            # Regular enhanced router for leechers
            router = EnhancedContentRouter(peer)
        
        # Attach the router to the peer
        peer.content_router = router
        
        # Add convenience methods
        peer.find_providers_enhanced = router.find_providers
        peer.retrieve_content_enhanced = router.retrieve_content
        peer.get_provider_stats = router.get_stats
        
        logger.info(f"Applied enhanced content router to peer")
        return router
    except Exception as e:
        logger.error(f"Failed to apply enhanced content router: {e}")
        return None
