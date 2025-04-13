"""
Recursive and Delegated Content Routing implementation for IPFS Kit.

This module enhances the content routing capabilities of the libp2p implementation
by providing recursive content lookup and delegated routing through trusted nodes.
These features improve content discoverability in the network while reducing the load
on resource-constrained devices.
"""

# Add the function for enhanced routing that is imported in other modules
def enhance_with_recursive_routing(peer_instance):
    """
    Enhance a libp2p peer instance with recursive routing capabilities.
    
    Args:
        peer_instance: The IPFSLibp2pPeer instance to enhance
    
    Returns:
        The enhanced peer instance
    """
    from ipfs_kit_py.libp2p.enhanced_dht_discovery import get_enhanced_dht_discovery
    
    # If the peer has a DHT, enhance it with recursive routing
    if hasattr(peer_instance, 'dht') and peer_instance.dht:
        # Get the enhanced DHT discovery class
        EnhancedDHTDiscovery = get_enhanced_dht_discovery()
        
        # Create an enhanced DHT discovery instance
        dht_discovery = EnhancedDHTDiscovery(peer_instance)
        
        # Create a recursive content router
        recursive_router = RecursiveContentRouter(dht_discovery)
        
        # Add the recursive router to the peer
        peer_instance.recursive_router = recursive_router
        
        # Enhance the find_providers method
        original_find_providers = peer_instance.find_providers
        
        def enhanced_find_providers(cid, timeout=30):
            """Enhanced version of find_providers that uses recursive routing."""
            # For synchronous API compatibility, we'll use the event loop directly
            import anyio
            
            try:
                # Create a new event loop if necessary
                try:
                    loop = anyio.get_event_loop()
                except RuntimeError:
                    loop = anyio.new_event_loop()
                    anyio.set_event_loop(loop)
                
                # Run the recursive find with a timeout
                future = recursive_router.find_providers(cid, timeout=timeout)
                return loop.run_until_complete(anyio.wait_for(future, timeout=timeout))
            except Exception as e:
                # Fall back to original method on error
                import logging
                logging.getLogger(__name__).warning(f"Error in recursive routing: {e}, falling back to standard DHT")
                return original_find_providers(cid, timeout)
        
        # Apply the enhancement
        peer_instance.find_providers = enhanced_find_providers
        
    return peer_instance

import anyio
import json
import logging
import random
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import base58
from multiaddr import Multiaddr

from .enhanced_dht_discovery import EnhancedDHTDiscovery


class RecursiveContentRouter:
    """
    Recursive content router that implements advanced lookup strategies.
    
    This class extends the basic DHT content router with:
    - Recursive lookup for content through multiple levels of peers
    - Lookup depth control to manage network traffic
    - Parallel queries to optimize lookup speed
    - Success probability estimation based on network topology
    """
    
    def __init__(self, dht_discovery, max_recursion_depth=3, parallel_queries=5):
        """
        Initialize the recursive content router.
        
        Args:
            dht_discovery: EnhancedDHTDiscovery instance to use
            max_recursion_depth: Maximum recursion depth for lookups
            parallel_queries: Number of parallel queries to perform
        """
        self.dht_discovery = dht_discovery
        self.max_recursion_depth = max_recursion_depth
        self.parallel_queries = parallel_queries
        self.logger = logging.getLogger(__name__)
        
        # Query tracking
        self.ongoing_queries = {}  # CID -> {peers_queried, results, etc.}
        self.query_results_cache = {}  # CID -> {timestamp, providers}
        
        # Statistics
        self.stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "average_depth": 0,
            "average_time": 0,
            "cache_hits": 0,
        }
    
    async def find_providers(self, cid, count=5, timeout=30):
        """
        Find providers for a content ID using recursive routing.
        
        Args:
            cid: Content ID to find providers for
            count: Maximum number of providers to return
            timeout: Maximum time to spend searching
            
        Returns:
            List of provider information dictionaries
        """
        # Check cache first
        cached = self._check_cache(cid, count)
        if cached:
            self.stats["cache_hits"] += 1
            return cached
        
        # Start a new query
        query_id = f"{cid}_{time.time()}"
        self.ongoing_queries[query_id] = {
            "cid": cid,
            "start_time": time.time(),
            "peers_queried": set(),
            "peers_to_query": set(),
            "results": [],
            "depth": 0,
            "completed": False
        }
        
        # Start recursive search
        try:
            results = await anyio.wait_for(
                self._recursive_find(query_id),
                timeout=timeout
            )
            
            # Update cache
            self._update_cache(cid, results)
            
            # Update statistics
            query_time = time.time() - self.ongoing_queries[query_id]["start_time"]
            query_depth = self.ongoing_queries[query_id]["depth"]
            
            self.stats["total_queries"] += 1
            if results:
                self.stats["successful_queries"] += 1
            
            # Update moving averages
            if self.stats["total_queries"] > 1:
                self.stats["average_depth"] = (
                    (self.stats["average_depth"] * (self.stats["total_queries"] - 1) + query_depth) / 
                    self.stats["total_queries"]
                )
                self.stats["average_time"] = (
                    (self.stats["average_time"] * (self.stats["total_queries"] - 1) + query_time) / 
                    self.stats["total_queries"]
                )
            else:
                self.stats["average_depth"] = query_depth
                self.stats["average_time"] = query_time
            
            # Clean up
            del self.ongoing_queries[query_id]
            
            return results[:count]
            
        except anyio.TimeoutError:
            self.logger.warning(f"Recursive lookup for {cid} timed out")
            
            # Return partial results if any
            if query_id in self.ongoing_queries:
                results = self.ongoing_queries[query_id]["results"]
                del self.ongoing_queries[query_id]
                return results[:count]
            
            return []
            
        except Exception as e:
            self.logger.error(f"Error in recursive lookup for {cid}: {e}")
            
            # Clean up
            if query_id in self.ongoing_queries:
                del self.ongoing_queries[query_id]
                
            return []
    
    async def _recursive_find(self, query_id):
        """
        Perform recursive provider lookup.
        
        Args:
            query_id: ID of the ongoing query
            
        Returns:
            List of provider information
        """
        query = self.ongoing_queries[query_id]
        cid = query["cid"]
        
        # Initial query using direct DHT discovery
        direct_providers = await self._query_direct(cid)
        
        if direct_providers:
            # Add to results
            self._add_providers_to_results(query_id, direct_providers, source="direct")
            
            # If we have enough results, return early
            if len(query["results"]) >= 5:
                query["completed"] = True
                return query["results"]
        
        # Get initial peers to query from k-buckets
        initial_peers = self._get_initial_peers(cid)
        query["peers_to_query"].update(initial_peers)
        
        # Recursive lookup until max depth or no more peers to query
        while (query["depth"] < self.max_recursion_depth and 
               query["peers_to_query"] and 
               not query["completed"]):
               
            # Increment depth
            query["depth"] += 1
            
            # Select peers to query in this round
            peers_this_round = []
            for _ in range(min(self.parallel_queries, len(query["peers_to_query"]))):
                if not query["peers_to_query"]:
                    break
                peer = self._select_best_peer(query)
                query["peers_to_query"].remove(peer)
                peers_this_round.append(peer)
                query["peers_queried"].add(peer)
            
            if not peers_this_round:
                break
                
            # Query these peers in parallel
            tasks = [self._query_peer(query_id, peer, cid) for peer in peers_this_round]
            results = await anyio.gather(*tasks, return_exceptions=True)
            
            # Process results
            next_peers = set()
            for peer, result in zip(peers_this_round, results):
                if isinstance(result, Exception):
                    self.logger.debug(f"Error querying peer {peer} for {cid}: {result}")
                    continue
                    
                providers, suggested_peers = result
                
                # Add found providers to results
                if providers:
                    self._add_providers_to_results(query_id, providers, source=f"depth_{query['depth']}")
                    
                # Add suggested peers to query next
                for suggested_peer in suggested_peers:
                    if (suggested_peer not in query["peers_queried"] and 
                        suggested_peer not in query["peers_to_query"]):
                        next_peers.add(suggested_peer)
            
            # Add next peers to query
            query["peers_to_query"].update(next_peers)
            
            # Check if we have enough results
            if len(query["results"]) >= 5:
                query["completed"] = True
                break
        
        query["completed"] = True
        return query["results"]
    
    async def _query_direct(self, cid):
        """
        Query providers directly using the DHT discovery.
        
        Args:
            cid: Content ID to find providers for
            
        Returns:
            List of provider information
        """
        try:
            # Use the underlying DHT discovery for direct lookup
            providers_future = self.dht_discovery.find_providers(cid, count=5)
            providers = await anyio.wrap_future(providers_future)
            return providers
        except Exception as e:
            self.logger.warning(f"Error in direct query for {cid}: {e}")
            return []
    
    async def _query_peer(self, query_id, peer_id, cid):
        """
        Query a peer for providers and suggested next peers.
        
        Args:
            query_id: ID of the ongoing query
            peer_id: ID of the peer to query
            cid: Content ID to query for
            
        Returns:
            Tuple of (providers_list, suggested_peers_set)
        """
        try:
            # Connect to the peer if not connected
            await self._ensure_peer_connection(peer_id)
            
            # Open a stream using content routing protocol
            protocol_id = "/ipfs/kad/1.0.0"  # Kademlia DHT protocol
            stream = await self.dht_discovery.libp2p_peer.host.new_stream(
                peer_id, 
                [protocol_id]
            )
            
            try:
                # Create request message (simplified format)
                request = {
                    "type": "FIND_PROVIDERS",
                    "key": base58.b58encode(self._decode_cid(cid)).decode(),
                    "count": 20
                }
                
                # Send request
                await stream.write(json.dumps(request).encode() + b"\n")
                
                # Read response
                response_data = await stream.read(1024 * 1024)  # 1MB max
                if not response_data:
                    return [], []
                
                # Parse response
                response = json.loads(response_data.decode())
                
                # Extract providers
                providers = []
                for provider_info in response.get("providers", []):
                    provider = {
                        "peer_id": provider_info.get("id"),
                        "multiaddrs": provider_info.get("addrs", []),
                        "connection_type": "recursive",
                        "first_seen": time.time(),
                        "last_seen": time.time(),
                        "reputation": 0.5  # Default reputation
                    }
                    providers.append(provider)
                
                # Extract closer peers
                closer_peers = set()
                for peer_info in response.get("closer_peers", []):
                    peer_id = peer_info.get("id")
                    if peer_id:
                        closer_peers.add(peer_id)
                
                return providers, closer_peers
                
            finally:
                await stream.close()
                
        except Exception as e:
            self.logger.debug(f"Error querying peer {peer_id} for {cid}: {e}")
            return [], []
    
    async def _ensure_peer_connection(self, peer_id):
        """
        Ensure we have a connection to the peer.
        
        Args:
            peer_id: ID of the peer to connect to
        """
        # Check if already connected
        if self.dht_discovery.libp2p_peer.host.get_network().is_connected(peer_id):
            return
            
        # Try to connect
        peer_info = self.dht_discovery.libp2p_peer.host.get_peerstore().get_peer(peer_id)
        if not peer_info:
            raise ValueError(f"No peer info for {peer_id}")
            
        await self.dht_discovery.libp2p_peer.host.connect(peer_info)
    
    def _get_initial_peers(self, cid):
        """
        Get initial peers to query from k-buckets.
        
        Args:
            cid: Content ID to find providers for
            
        Returns:
            Set of peer IDs to query
        """
        # Get peers from appropriate k-buckets
        # In a real implementation, we would use the XOR distance
        # between the CID and peer IDs to select relevant buckets
        
        # For simplicity, just get some peers from the DHT discovery
        peers = set()
        
        # Get connected peers
        for bucket in self.dht_discovery.k_buckets:
            peers.update(bucket)
            if len(peers) >= 10:
                break
                
        return peers
    
    def _select_best_peer(self, query):
        """
        Select the best peer to query next based on various factors.
        
        Args:
            query: Current query state
            
        Returns:
            Peer ID of the selected peer
        """
        # In a real implementation, we would use various metrics to select
        # the best peer, such as RTT, success rate, XOR distance, etc.
        
        # For simplicity, just pick a random peer
        return random.choice(list(query["peers_to_query"]))
    
    def _add_providers_to_results(self, query_id, providers, source):
        """
        Add providers to query results with deduplication.
        
        Args:
            query_id: ID of the ongoing query
            providers: List of providers to add
            source: Source of these providers (for logging)
        """
        query = self.ongoing_queries[query_id]
        
        # Track existing peer IDs in results
        existing_peer_ids = {p["peer_id"] for p in query["results"]}
        
        # Add new providers
        for provider in providers:
            peer_id = provider["peer_id"]
            if peer_id not in existing_peer_ids:
                query["results"].append(provider)
                existing_peer_ids.add(peer_id)
                
                # Add to DHT discovery provider cache
                self.dht_discovery.add_provider(
                    query["cid"],
                    peer_id,
                    provider.get("multiaddrs"),
                    provider.get("connection_type"),
                    provider.get("reputation", 0.5)
                )
    
    def _check_cache(self, cid, count):
        """
        Check if providers for this CID are in the cache.
        
        Args:
            cid: Content ID to check
            count: Number of providers to return
            
        Returns:
            List of providers if cached, empty list otherwise
        """
        if cid in self.query_results_cache:
            cache_entry = self.query_results_cache[cid]
            
            # Check if cache is still valid (10 minute TTL)
            if time.time() - cache_entry["timestamp"] < 600:
                return cache_entry["providers"][:count]
                
            # Cache expired
            del self.query_results_cache[cid]
            
        return []
    
    def _update_cache(self, cid, providers):
        """
        Update the cache with providers for a CID.
        
        Args:
            cid: Content ID to cache
            providers: List of providers to cache
        """
        self.query_results_cache[cid] = {
            "timestamp": time.time(),
            "providers": providers
        }
        
        # Limit cache size
        if len(self.query_results_cache) > 1000:
            # Remove oldest entries
            oldest_cids = sorted(
                self.query_results_cache.keys(),
                key=lambda k: self.query_results_cache[k]["timestamp"]
            )[:100]
            
            for old_cid in oldest_cids:
                del self.query_results_cache[old_cid]
    
    def _decode_cid(self, cid_str):
        """
        Decode a CID string to bytes.
        
        Args:
            cid_str: CID string to decode
            
        Returns:
            Bytes representation of the CID
        """
        try:
            # Try to use proper CID decoding if available
            from multiformats import CID
            cid_obj = CID.decode(cid_str)
            return cid_obj.buffer
        except (ImportError, Exception) as e:
            # Fallback to simple base58 decoding
            try:
                return base58.b58decode(cid_str)
            except Exception:
                # Last resort: just use the string as bytes
                return cid_str.encode()
    
    def get_stats(self):
        """
        Get router statistics.
        
        Returns:
            Dictionary of router statistics
        """
        return {
            "total_queries": self.stats["total_queries"],
            "successful_queries": self.stats["successful_queries"],
            "success_rate": (
                self.stats["successful_queries"] / self.stats["total_queries"]
                if self.stats["total_queries"] > 0 else 0
            ),
            "average_depth": self.stats["average_depth"],
            "average_time": self.stats["average_time"],
            "cache_hits": self.stats["cache_hits"],
            "ongoing_queries": len(self.ongoing_queries),
            "cache_size": len(self.query_results_cache)
        }
    
    
class DelegatedContentRouter:
    """
    Delegated content router that offloads lookup to trusted nodes.
    
    This is particularly useful for resource-constrained devices (leechers)
    that want to minimize their DHT participation while still being able
    to discover content.
    """
    
    def __init__(self, libp2p_peer, delegate_peers=None, fallback_router=None):
        """
        Initialize delegated content router.
        
        Args:
            libp2p_peer: The LibP2P peer instance
            delegate_peers: List of peer IDs to use as delegates
            fallback_router: Router to use if delegation fails
        """
        self.libp2p_peer = libp2p_peer
        self.delegate_peers = delegate_peers or []
        self.fallback_router = fallback_router
        self.logger = logging.getLogger(__name__)
        
        # Delegate statistics
        self.delegate_stats = {}  # peer_id -> stats
        
        # Protocol constants
        self.PROTOCOL_ID = "/ipfs/delegated-routing/1.0.0"
        
        # Register protocol handler
        if self.libp2p_peer and self.libp2p_peer.host:
            self.libp2p_peer.host.set_stream_handler(
                self.PROTOCOL_ID,
                self._handle_delegation_request
            )
    
    def set_delegate_peers(self, peers):
        """
        Set the list of delegate peers.
        
        Args:
            peers: List of peer IDs to use as delegates
        """
        self.delegate_peers = peers
    
    async def find_providers(self, cid, count=5, timeout=30, **kwargs):
        """
        Find providers for a content ID by delegating to other peers.
        
        Args:
            cid: Content ID to find providers for
            count: Maximum number of providers to return
            timeout: Maximum time to spend searching
            **kwargs: Additional arguments for delegation
            
        Returns:
            List of provider information dictionaries
        """
        if not self.delegate_peers:
            self.logger.warning("No delegate peers configured")
            if self.fallback_router:
                return await self.fallback_router.find_providers(cid, count, timeout)
            return []
        
        # Select delegate peers to query
        delegates_to_query = self._select_delegates(count=3)
        if not delegates_to_query:
            if self.fallback_router:
                return await self.fallback_router.find_providers(cid, count, timeout)
            return []
        
        # Query delegates in parallel
        tasks = [
            self._query_delegate(delegate, cid, count, timeout/2)
            for delegate in delegates_to_query
        ]
        
        results = await anyio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        all_providers = []
        providers_by_id = {}  # For deduplication
        
        for delegate, result in zip(delegates_to_query, results):
            if isinstance(result, Exception):
                self.logger.warning(f"Error querying delegate {delegate}: {result}")
                # Update delegate stats
                self._update_delegate_stats(delegate, success=False)
                continue
            
            if result:
                # Update delegate stats
                self._update_delegate_stats(delegate, success=True, providers_found=len(result))
                
                # Add providers (with deduplication)
                for provider in result:
                    peer_id = provider.get("peer_id")
                    if peer_id and peer_id not in providers_by_id:
                        providers_by_id[peer_id] = provider
                        all_providers.append(provider)
        
        # If we didn't get any results, try fallback
        if not all_providers and self.fallback_router:
            self.logger.info(f"No providers found via delegates, trying fallback for {cid}")
            return await self.fallback_router.find_providers(cid, count, timeout/2)
        
        return all_providers[:count]
    
    async def _query_delegate(self, delegate_id, cid, count, timeout):
        """
        Query a delegate peer for providers.
        
        Args:
            delegate_id: ID of the delegate peer
            cid: Content ID to find providers for
            count: Maximum number of providers to return
            timeout: Maximum time to wait for response
            
        Returns:
            List of provider information dictionaries
        """
        try:
            # Ensure we're connected to the delegate
            await self._ensure_delegate_connection(delegate_id)
            
            # Open a stream to the delegate
            stream = await anyio.wait_for(
                self.libp2p_peer.host.new_stream(delegate_id, [self.PROTOCOL_ID]),
                timeout=timeout/3
            )
            
            try:
                # Create request
                request = {
                    "type": "FIND_PROVIDERS",
                    "cid": cid,
                    "count": count,
                    "options": {
                        "timeout": int(timeout * 1000)  # Convert to milliseconds
                    }
                }
                
                # Send request
                await stream.write(json.dumps(request).encode() + b"\n")
                
                # Wait for response
                response_data = await anyio.wait_for(
                    stream.read(1024 * 1024),  # 1MB max
                    timeout=timeout
                )
                
                if not response_data:
                    return []
                
                # Parse response
                response = json.loads(response_data.decode())
                
                # Extract providers
                providers = []
                for provider_info in response.get("providers", []):
                    provider = {
                        "peer_id": provider_info.get("id"),
                        "multiaddrs": provider_info.get("addrs", []),
                        "connection_type": "delegated",
                        "first_seen": time.time(),
                        "last_seen": time.time(),
                        "reputation": 0.5,  # Default reputation
                        "delegate": delegate_id  # Track which delegate found this
                    }
                    providers.append(provider)
                
                return providers
                
            finally:
                await stream.close()
                
        except anyio.TimeoutError:
            self.logger.warning(f"Timeout querying delegate {delegate_id} for {cid}")
            return []
            
        except Exception as e:
            self.logger.warning(f"Error querying delegate {delegate_id} for {cid}: {e}")
            return []
    
    async def _ensure_delegate_connection(self, delegate_id):
        """
        Ensure we have a connection to the delegate peer.
        
        Args:
            delegate_id: ID of the delegate peer to connect to
        """
        try:
            # Check if already connected
            if self.libp2p_peer.host.get_network().is_connected(delegate_id):
                return
                
            # Try to connect
            peer_info = self.libp2p_peer.host.get_peerstore().get_peer(delegate_id)
            if not peer_info:
                addrs = self._get_bootstrap_addresses_for_peer(delegate_id)
                if not addrs:
                    raise ValueError(f"No addresses for delegate {delegate_id}")
                
                # Create peer info
                peer_info = {
                    "id": delegate_id,
                    "addrs": [Multiaddr(addr) for addr in addrs]
                }
                
            await self.libp2p_peer.host.connect(peer_info)
            
        except Exception as e:
            self.logger.warning(f"Error connecting to delegate {delegate_id}: {e}")
            raise
    
    def _get_bootstrap_addresses_for_peer(self, peer_id):
        """
        Get bootstrap addresses for a peer ID.
        
        Args:
            peer_id: Peer ID to find addresses for
            
        Returns:
            List of multiaddress strings
        """
        # This would typically come from a configuration file or bootstrap list
        # For now, return an empty list as a placeholder
        return []
    
    def _select_delegates(self, count=3):
        """
        Select the best delegate peers based on past performance.
        
        Args:
            count: Number of delegates to select
            
        Returns:
            List of selected delegate peer IDs
        """
        if not self.delegate_peers:
            return []
            
        if len(self.delegate_peers) <= count:
            return self.delegate_peers.copy()
            
        # If we have stats, use them to select delegates
        if self.delegate_stats:
            # Sort by success rate and response time
            sorted_delegates = sorted(
                [p for p in self.delegate_peers if p in self.delegate_stats],
                key=lambda p: (
                    self.delegate_stats[p].get("success_rate", 0),
                    -self.delegate_stats[p].get("avg_response_time", float('inf'))
                ),
                reverse=True
            )
            
            if len(sorted_delegates) >= count:
                return sorted_delegates[:count]
                
            # Add remaining delegates that don't have stats
            remaining = [p for p in self.delegate_peers if p not in self.delegate_stats]
            return sorted_delegates + remaining[:count - len(sorted_delegates)]
        
        # No stats yet, just pick randomly
        return random.sample(self.delegate_peers, min(count, len(self.delegate_peers)))
    
    def _update_delegate_stats(self, delegate_id, success=True, providers_found=0, response_time=None):
        """
        Update statistics for a delegate peer.
        
        Args:
            delegate_id: ID of the delegate peer
            success: Whether the query was successful
            providers_found: Number of providers found
            response_time: Response time in seconds
        """
        if delegate_id not in self.delegate_stats:
            self.delegate_stats[delegate_id] = {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "total_providers_found": 0,
                "success_rate": 0,
                "response_times": [],
                "avg_response_time": 0,
                "last_used": 0
            }
            
        stats = self.delegate_stats[delegate_id]
        stats["total_requests"] += 1
        stats["last_used"] = time.time()
        
        if success:
            stats["successful_requests"] += 1
            stats["total_providers_found"] += providers_found
        else:
            stats["failed_requests"] += 1
            
        stats["success_rate"] = stats["successful_requests"] / stats["total_requests"]
        
        if response_time is not None:
            stats["response_times"].append(response_time)
            # Keep only the last 50 response times
            if len(stats["response_times"]) > 50:
                stats["response_times"] = stats["response_times"][-50:]
            stats["avg_response_time"] = sum(stats["response_times"]) / len(stats["response_times"])
    
    async def _handle_delegation_request(self, stream):
        """
        Handle a delegated routing request from another peer.
        
        This is called when we are acting as a delegate for others.
        
        Args:
            stream: The stream from the requesting peer
        """
        try:
            # Read request
            request_data = await stream.read_until(b"\n", 1024 * 10)
            if not request_data:
                await stream.close()
                return
                
            # Parse request
            request = json.loads(request_data.decode().strip())
            
            # Validate request type
            if request.get("type") != "FIND_PROVIDERS":
                self.logger.warning(f"Unsupported request type: {request.get('type')}")
                await stream.write(json.dumps({"error": "Unsupported request type"}).encode() + b"\n")
                await stream.close()
                return
                
            # Extract parameters
            cid = request.get("cid")
            if not cid:
                await stream.write(json.dumps({"error": "Missing CID"}).encode() + b"\n")
                await stream.close()
                return
                
            count = int(request.get("count", 5))
            timeout_ms = int(request.get("options", {}).get("timeout", 30000))
            timeout = timeout_ms / 1000  # Convert to seconds
            
            # Handle the request using our routing capabilities
            providers = []
            
            # Use recursive routing if available
            if hasattr(self, "recursive_router") and self.recursive_router:
                try:
                    providers = await self.recursive_router.find_providers(
                        cid,
                        count=count,
                        timeout=timeout*0.8  # Leave some time for response
                    )
                except Exception as e:
                    self.logger.warning(f"Error using recursive routing: {e}")
            
            # If we have a fallback and no providers yet, try it
            if not providers and self.fallback_router:
                try:
                    providers = await self.fallback_router.find_providers(
                        cid,
                        count=count,
                        timeout=timeout*0.8  # Leave some time for response
                    )
                except Exception as e:
                    self.logger.warning(f"Error using fallback routing: {e}")
            
            # Format response
            response = {
                "providers": [
                    {
                        "id": p.get("peer_id"),
                        "addrs": p.get("multiaddrs", [])
                    }
                    for p in providers if p.get("peer_id")
                ]
            }
            
            # Send response
            await stream.write(json.dumps(response).encode() + b"\n")
            
        except Exception as e:
            self.logger.error(f"Error handling delegation request: {e}")
            try:
                await stream.write(json.dumps({"error": str(e)}).encode() + b"\n")
            except:
                pass
                
        finally:
            await stream.close()
                
    def get_stats(self):
        """
        Get statistics about delegated routing.
        
        Returns:
            Dictionary of statistics
        """
        # Calculate overall statistics
        total_requests = 0
        successful_requests = 0
        total_providers_found = 0
        active_delegates = 0
        
        for stats in self.delegate_stats.values():
            total_requests += stats.get("total_requests", 0)
            successful_requests += stats.get("successful_requests", 0)
            total_providers_found += stats.get("total_providers_found", 0)
            if time.time() - stats.get("last_used", 0) < 3600:  # Active in last hour
                active_delegates += 1
        
        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "success_rate": successful_requests / total_requests if total_requests > 0 else 0,
            "total_providers_found": total_providers_found,
            "providers_per_request": total_providers_found / successful_requests if successful_requests > 0 else 0,
            "delegate_count": len(self.delegate_peers),
            "active_delegates": active_delegates,
            "delegates": self.delegate_stats.copy()
        }


class ProviderRecordManager:
    """
    Advanced provider record manager for maintaining content provider information.
    
    This class implements sophisticated provider record management with:
    - Record expiration based on configurable TTL
    - Provider reputation tracking and scoring
    - Content affinity analysis for predictive content routing
    - Provider capabilities tracking (e.g., bandwidth, latency, supported protocols)
    """
    
    def __init__(self, ttl=24*3600, max_records=10000):
        """
        Initialize the provider record manager.
        
        Args:
            ttl: Time-to-live for provider records in seconds (default 24 hours)
            max_records: Maximum number of records to maintain
        """
        self.ttl = ttl
        self.max_records = max_records
        self.logger = logging.getLogger(__name__)
        
        # Provider records storage
        self.records = {}  # cid -> list of provider records
        self.peer_capabilities = {}  # peer_id -> capabilities dict
        self.content_affinities = {}  # peer_id -> list of related CIDs
        
        # Indexes for efficient lookup
        self.peer_to_content = {}  # peer_id -> set of CIDs
        
        # Background maintenance
        self.last_cleanup = time.time()
        self.cleanup_interval = 3600  # 1 hour
    
    def add_provider(self, cid, peer_id, multiaddrs=None, protocols=None, metadata=None):
        """
        Add or update a provider record.
        
        Args:
            cid: Content ID
            peer_id: ID of the provider peer
            multiaddrs: List of multiaddresses for the peer
            protocols: List of supported protocols
            metadata: Additional metadata about the provider
            
        Returns:
            Updated provider record
        """
        # Initialize records for this CID if needed
        if cid not in self.records:
            self.records[cid] = []
            
        # Check if we already have a record for this peer
        existing = None
        for record in self.records[cid]:
            if record["peer_id"] == peer_id:
                existing = record
                break
                
        now = time.time()
        
        if existing:
            # Update existing record
            existing["last_updated"] = now
            existing["expiration"] = now + self.ttl
            
            if multiaddrs:
                existing["multiaddrs"] = multiaddrs
                
            if protocols:
                existing["protocols"] = protocols
                
            if metadata:
                # Update metadata with new values
                if "metadata" not in existing:
                    existing["metadata"] = {}
                existing["metadata"].update(metadata)
                
            record = existing
            
        else:
            # Create new record
            record = {
                "peer_id": peer_id,
                "multiaddrs": multiaddrs or [],
                "protocols": protocols or [],
                "added": now,
                "last_updated": now,
                "expiration": now + self.ttl,
                "reputation": 0.5,  # Initial neutral reputation
                "successful_retrievals": 0,
                "failed_retrievals": 0
            }
            
            if metadata:
                record["metadata"] = metadata
                
            self.records[cid].append(record)
            
            # Update indexes
            if peer_id not in self.peer_to_content:
                self.peer_to_content[peer_id] = set()
            self.peer_to_content[peer_id].add(cid)
        
        # Update content affinity
        self._update_content_affinity(peer_id, cid)
        
        # Check if we need to run maintenance
        if now - self.last_cleanup > self.cleanup_interval:
            self._run_maintenance()
            
        return record
    
    def get_providers(self, cid, count=None, include_expired=False):
        """
        Get providers for a content ID.
        
        Args:
            cid: Content ID to get providers for
            count: Maximum number of providers to return
            include_expired: Whether to include expired records
            
        Returns:
            List of provider records
        """
        if cid not in self.records:
            return []
            
        now = time.time()
        providers = []
        
        for record in self.records[cid]:
            # Skip expired records unless explicitly requested
            if not include_expired and record["expiration"] < now:
                continue
                
            providers.append(record)
            
        # Sort by reputation (higher is better)
        providers.sort(key=lambda r: r.get("reputation", 0), reverse=True)
        
        # Limit to requested count
        if count is not None:
            providers = providers[:count]
            
        return providers
    
    def update_retrieval_result(self, peer_id, cid, success, latency=None, bytes_received=None):
        """
        Update provider statistics based on content retrieval results.
        
        Args:
            peer_id: ID of the provider peer
            cid: Content ID that was retrieved
            success: Whether the retrieval was successful
            latency: Latency of the retrieval in seconds
            bytes_received: Amount of data received
            
        Returns:
            Updated reputation score
        """
        # Find the provider record
        if cid not in self.records:
            return None
            
        record = None
        for r in self.records[cid]:
            if r["peer_id"] == peer_id:
                record = r
                break
                
        if not record:
            return None
            
        # Update retrieval statistics
        if success:
            record["successful_retrievals"] = record.get("successful_retrievals", 0) + 1
        else:
            record["failed_retrievals"] = record.get("failed_retrievals", 0) + 1
            
        total_retrievals = record.get("successful_retrievals", 0) + record.get("failed_retrievals", 0)
        
        # Calculate success rate
        success_rate = 0.5  # Default neutral value
        if total_retrievals > 0:
            success_rate = record.get("successful_retrievals", 0) / total_retrievals
            
        # Update latency statistics if provided
        if latency is not None:
            if "latencies" not in record:
                record["latencies"] = []
                
            record["latencies"].append(latency)
            # Keep only the last 50 latencies
            if len(record["latencies"]) > 50:
                record["latencies"] = record["latencies"][-50:]
                
            record["average_latency"] = sum(record["latencies"]) / len(record["latencies"])
            
        # Update throughput statistics if provided
        if bytes_received is not None and latency is not None and latency > 0:
            throughput = bytes_received / latency  # bytes per second
            
            if "throughputs" not in record:
                record["throughputs"] = []
                
            record["throughputs"].append(throughput)
            # Keep only the last 50 throughputs
            if len(record["throughputs"]) > 50:
                record["throughputs"] = record["throughputs"][-50:]
                
            record["average_throughput"] = sum(record["throughputs"]) / len(record["throughputs"])
            
        # Calculate new reputation score
        # Weight factors for different components
        success_weight = 0.6
        latency_weight = 0.2
        throughput_weight = 0.2
        
        # Start with success rate
        reputation = success_weight * success_rate
        
        # Add latency factor if available
        if "average_latency" in record and record["average_latency"] > 0:
            # Transform latency to a 0-1 score (lower is better)
            # 5 seconds is considered good (score 0.8), 30+ seconds is poor (score 0.2)
            latency_score = max(0.2, min(0.8, 5 / record["average_latency"]))
            reputation += latency_weight * latency_score
            
        # Add throughput factor if available
        if "average_throughput" in record and record["average_throughput"] > 0:
            # Transform throughput to a 0-1 score (higher is better)
            # 1MB/s is considered good (score 0.8), 100KB/s is poor (score 0.2)
            min_good_throughput = 1024 * 1024  # 1 MB/s
            min_acceptable_throughput = 100 * 1024  # 100 KB/s
            
            throughput_score = 0.2
            if record["average_throughput"] >= min_good_throughput:
                throughput_score = 0.8
            elif record["average_throughput"] > min_acceptable_throughput:
                # Scale between 0.2 and 0.8
                scale = (record["average_throughput"] - min_acceptable_throughput) / (min_good_throughput - min_acceptable_throughput)
                throughput_score = 0.2 + scale * 0.6
                
            reputation += throughput_weight * throughput_score
            
        # Update the reputation
        record["reputation"] = reputation
        
        # Extend expiration time for active providers
        record["expiration"] = time.time() + self.ttl
        
        return reputation
    
    def add_peer_capability(self, peer_id, capability, value):
        """
        Add or update a peer capability.
        
        Args:
            peer_id: ID of the peer
            capability: Name of the capability
            value: Value of the capability
        """
        if peer_id not in self.peer_capabilities:
            self.peer_capabilities[peer_id] = {}
            
        self.peer_capabilities[peer_id][capability] = value
    
    def get_peer_capabilities(self, peer_id):
        """
        Get capabilities for a peer.
        
        Args:
            peer_id: ID of the peer
            
        Returns:
            Dictionary of capabilities
        """
        return self.peer_capabilities.get(peer_id, {})
    
    def filter_providers_by_capability(self, providers, capability, min_value=None, max_value=None):
        """
        Filter providers based on a capability.
        
        Args:
            providers: List of provider records
            capability: Capability to filter on
            min_value: Minimum acceptable value
            max_value: Maximum acceptable value
            
        Returns:
            Filtered list of provider records
        """
        result = []
        
        for provider in providers:
            peer_id = provider["peer_id"]
            capabilities = self.get_peer_capabilities(peer_id)
            
            if capability not in capabilities:
                continue
                
            value = capabilities[capability]
            
            if min_value is not None and value < min_value:
                continue
                
            if max_value is not None and value > max_value:
                continue
                
            result.append(provider)
            
        return result
    
    def remove_provider(self, cid, peer_id):
        """
        Remove a provider record.
        
        Args:
            cid: Content ID
            peer_id: ID of the provider peer
            
        Returns:
            True if the record was removed, False otherwise
        """
        if cid not in self.records:
            return False
            
        for i, record in enumerate(self.records[cid]):
            if record["peer_id"] == peer_id:
                # Remove from records
                self.records[cid].pop(i)
                
                # Update indexes
                if peer_id in self.peer_to_content:
                    self.peer_to_content[peer_id].discard(cid)
                    if not self.peer_to_content[peer_id]:
                        del self.peer_to_content[peer_id]
                        
                # Clean up empty record lists
                if not self.records[cid]:
                    del self.records[cid]
                    
                return True
                
        return False
    
    def find_related_content(self, cid, count=5):
        """
        Find content related to the given CID based on content affinity.
        
        Args:
            cid: Content ID to find related content for
            count: Maximum number of related CIDs to return
            
        Returns:
            List of related content IDs
        """
        if cid not in self.records:
            return []
            
        # Get providers for this CID
        providers = self.get_providers(cid)
        if not providers:
            return []
            
        # Track content co-occurrences
        content_scores = {}
        
        # For each provider, check what other content they provide
        for provider in providers:
            peer_id = provider["peer_id"]
            
            # Get content provided by this peer
            if peer_id in self.peer_to_content:
                for other_cid in self.peer_to_content[peer_id]:
                    if other_cid != cid:
                        # Increment co-occurrence count
                        content_scores[other_cid] = content_scores.get(other_cid, 0) + 1
        
        # Sort by score
        related = sorted(content_scores.keys(), key=lambda k: content_scores[k], reverse=True)
        
        return related[:count]
    
    def _update_content_affinity(self, peer_id, cid):
        """
        Update content affinity tracking.
        
        Args:
            peer_id: ID of the peer
            cid: Content ID
        """
        if peer_id not in self.content_affinities:
            self.content_affinities[peer_id] = []
            
        # Check if already in affinity list
        if cid in self.content_affinities[peer_id]:
            # Move to end of list (most recent)
            self.content_affinities[peer_id].remove(cid)
            
        # Add to end of list
        self.content_affinities[peer_id].append(cid)
        
        # Limit list size
        max_affinity_size = 100
        if len(self.content_affinities[peer_id]) > max_affinity_size:
            self.content_affinities[peer_id] = self.content_affinities[peer_id][-max_affinity_size:]
    
    def _run_maintenance(self):
        """
        Run maintenance operations like expiring old records and enforcing limits.
        """
        self.logger.debug("Running provider record maintenance")
        now = time.time()
        
        # Track expired records to remove
        expired_records = []  # (cid, peer_id) pairs
        
        # Check for expired records
        for cid, providers in self.records.items():
            for provider in providers:
                if provider["expiration"] < now:
                    expired_records.append((cid, provider["peer_id"]))
        
        # Remove expired records
        for cid, peer_id in expired_records:
            self.remove_provider(cid, peer_id)
            
        # Enforce maximum records limit
        total_records = sum(len(providers) for providers in self.records.values())
        
        if total_records > self.max_records:
            # Sort all records by last_updated (oldest first)
            all_records = []
            for cid, providers in self.records.items():
                for provider in providers:
                    all_records.append((cid, provider["peer_id"], provider["last_updated"]))
                    
            all_records.sort(key=lambda r: r[2])
            
            # Remove oldest records until we're under the limit
            to_remove = total_records - self.max_records
            for cid, peer_id, _ in all_records[:to_remove]:
                self.remove_provider(cid, peer_id)
                
        # Update last cleanup time
        self.last_cleanup = now
        
        self.logger.debug(f"Maintenance complete. Removed {len(expired_records)} expired records")
    
    def get_stats(self):
        """
        Get statistics about provider records.
        
        Returns:
            Dictionary of statistics
        """
        total_records = sum(len(providers) for providers in self.records.values())
        
        # Calculate average records per CID
        avg_records_per_cid = 0
        if self.records:
            avg_records_per_cid = total_records / len(self.records)
            
        # Calculate average reputation
        total_reputation = 0
        reputation_count = 0
        
        for providers in self.records.values():
            for provider in providers:
                if "reputation" in provider:
                    total_reputation += provider["reputation"]
                    reputation_count += 1
                    
        avg_reputation = 0
        if reputation_count > 0:
            avg_reputation = total_reputation / reputation_count
            
        return {
            "total_records": total_records,
            "cid_count": len(self.records),
            "peer_count": len(self.peer_to_content),
            "avg_records_per_cid": avg_records_per_cid,
            "avg_reputation": avg_reputation,
            "last_maintenance": self.last_cleanup
        }


class ContentRoutingSystem:
    """
    Comprehensive content routing system that integrates multiple routing strategies.
    
    This class provides a unified content routing interface that strategically selects
    from available routing mechanisms based on the client's role, resource constraints,
    and query characteristics.
    """
    
    def __init__(self, libp2p_peer, dht_discovery=None, role="leecher"):
        """
        Initialize the content routing system.
        
        Args:
            libp2p_peer: The LibP2P peer instance
            dht_discovery: EnhancedDHTDiscovery instance (if available)
            role: The node role (master, worker, or leecher)
        """
        self.libp2p_peer = libp2p_peer
        self.dht_discovery = dht_discovery
        self.role = role
        self.logger = logging.getLogger(__name__)
        
        # Initialize component routers
        self.recursive_router = None
        self.delegated_router = None
        self.provider_manager = None
        
        # Configure based on role
        self._configure_for_role()
        
        # Stats
        self.router_usage = {
            "recursive": 0,
            "delegated": 0,
            "direct": 0
        }
    
    def _configure_for_role(self):
        """Configure routing components based on node role."""
        # For all roles, initialize the provider manager
        self.provider_manager = ProviderRecordManager()
        
        # Configure based on role
        if self.role == "master":
            # Masters use recursive routing and act as delegates
            if self.dht_discovery:
                self.recursive_router = RecursiveContentRouter(
                    self.dht_discovery,
                    max_recursion_depth=3,
                    parallel_queries=8
                )
                
            # Master nodes don't use delegation but provide it to others
            self.delegated_router = DelegatedContentRouter(
                self.libp2p_peer,
                fallback_router=self.recursive_router
            )
            
            # Link the delegation router to the recursive router
            if hasattr(self.delegated_router, "recursive_router"):
                self.delegated_router.recursive_router = self.recursive_router
                
        elif self.role == "worker":
            # Workers use recursive routing with moderate depth
            if self.dht_discovery:
                self.recursive_router = RecursiveContentRouter(
                    self.dht_discovery,
                    max_recursion_depth=2,
                    parallel_queries=4
                )
                
            # Workers can also use delegation in some cases
            master_peers = self._get_master_peers()
            if master_peers:
                self.delegated_router = DelegatedContentRouter(
                    self.libp2p_peer,
                    delegate_peers=master_peers,
                    fallback_router=self.recursive_router
                )
                
        elif self.role == "leecher":
            # Leechers primarily use delegation to minimize DHT participation
            master_peers = self._get_master_peers()
            worker_peers = self._get_worker_peers()
            
            # Combine master and worker peers as potential delegates
            potential_delegates = master_peers + worker_peers
            
            if potential_delegates:
                self.delegated_router = DelegatedContentRouter(
                    self.libp2p_peer,
                    delegate_peers=potential_delegates,
                    fallback_router=None
                )
                
            # Leechers use minimal recursive routing as a last resort
            if self.dht_discovery:
                self.recursive_router = RecursiveContentRouter(
                    self.dht_discovery,
                    max_recursion_depth=1,  # Minimal recursion
                    parallel_queries=2
                )
                
                # Update fallback router for delegation
                if self.delegated_router:
                    self.delegated_router.fallback_router = self.recursive_router
    
    def _get_master_peers(self):
        """Get list of known master peers from the peerstore."""
        # This would normally come from cluster configuration
        # or dynamic discovery mechanisms
        return []
    
    def _get_worker_peers(self):
        """Get list of known worker peers from the peerstore."""
        # This would normally come from cluster configuration
        # or dynamic discovery mechanisms
        return []
    
    async def find_providers(self, cid, count=5, timeout=30, routing_preference=None, **kwargs):
        """
        Find providers for a content ID using the most appropriate routing strategy.
        
        Args:
            cid: Content ID to find providers for
            count: Maximum number of providers to return
            timeout: Maximum time to spend searching
            routing_preference: Preferred routing strategy ("recursive", "delegated", "direct")
            **kwargs: Additional arguments for specific routing strategies
            
        Returns:
            List of provider information dictionaries
        """
        # Check if providers already in local records
        local_providers = self.provider_manager.get_providers(cid, count)
        if local_providers and len(local_providers) >= count:
            return local_providers
            
        # Strategy selection based on preference or role
        if routing_preference:
            strategy = routing_preference
        else:
            # Choose based on role
            if self.role == "master":
                strategy = "recursive"
            elif self.role == "worker":
                # Workers try delegation first, then recursive
                strategy = "delegated" if self.delegated_router else "recursive"
            else:  # leecher
                # Leechers almost always use delegation
                strategy = "delegated" if self.delegated_router else "recursive"
        
        # Execute the chosen strategy
        providers = []
        
        if strategy == "recursive" and self.recursive_router:
            try:
                self.logger.debug(f"Using recursive routing for {cid}")
                providers = await self.recursive_router.find_providers(cid, count, timeout)
                self.router_usage["recursive"] += 1
            except Exception as e:
                self.logger.warning(f"Recursive routing failed for {cid}: {e}")
                
        elif strategy == "delegated" and self.delegated_router:
            try:
                self.logger.debug(f"Using delegated routing for {cid}")
                providers = await self.delegated_router.find_providers(cid, count, timeout)
                self.router_usage["delegated"] += 1
            except Exception as e:
                self.logger.warning(f"Delegated routing failed for {cid}: {e}")
                
        elif strategy == "direct" and self.dht_discovery:
            try:
                self.logger.debug(f"Using direct DHT routing for {cid}")
                providers_future = self.dht_discovery.find_providers(cid, count=count)
                providers = await anyio.wait_for(anyio.wrap_future(providers_future), timeout)
                self.router_usage["direct"] += 1
            except Exception as e:
                self.logger.warning(f"Direct routing failed for {cid}: {e}")
        
        # Fallback if primary strategy failed
        if not providers:
            self.logger.info(f"Primary routing strategy {strategy} failed for {cid}, trying fallbacks")
            
            # Try other available strategies
            if strategy != "delegated" and self.delegated_router:
                try:
                    self.logger.debug(f"Trying delegated routing fallback for {cid}")
                    providers = await self.delegated_router.find_providers(cid, count, timeout/2)
                    self.router_usage["delegated"] += 1
                except Exception as e:
                    self.logger.warning(f"Delegated routing fallback failed for {cid}: {e}")
                    
            if not providers and strategy != "recursive" and self.recursive_router:
                try:
                    self.logger.debug(f"Trying recursive routing fallback for {cid}")
                    providers = await self.recursive_router.find_providers(cid, count, timeout/2)
                    self.router_usage["recursive"] += 1
                except Exception as e:
                    self.logger.warning(f"Recursive routing fallback failed for {cid}: {e}")
                    
            if not providers and strategy != "direct" and self.dht_discovery:
                try:
                    self.logger.debug(f"Trying direct DHT routing fallback for {cid}")
                    providers_future = self.dht_discovery.find_providers(cid, count=count)
                    providers = await anyio.wait_for(anyio.wrap_future(providers_future), timeout/2)
                    self.router_usage["direct"] += 1
                except Exception as e:
                    self.logger.warning(f"Direct routing fallback failed for {cid}: {e}")
        
        # Add all found providers to our provider manager
        for provider in providers:
            self.provider_manager.add_provider(
                cid,
                provider.get("peer_id"),
                provider.get("multiaddrs"),
                provider.get("protocols", []),
                provider.get("metadata", {})
            )
            
        # Return providers (including any we had locally)
        all_providers = self.provider_manager.get_providers(cid, count)
        
        return all_providers
    
    async def provide(self, cid, announce=True):
        """
        Announce that we can provide a specific content.
        
        Args:
            cid: Content ID to provide
            announce: Whether to announce to the network
            
        Returns:
            Boolean indicating success
        """
        try:
            # Add to provider manager
            self.provider_manager.add_provider(
                cid,
                self.libp2p_peer.host.get_id().pretty(),
                [str(addr) for addr in self.libp2p_peer.host.get_addrs()],
                ["/ipfs/bitswap/1.2.0"]
            )
            
            # Announce to the network if requested
            if announce:
                if hasattr(self.libp2p_peer, "announce_content"):
                    self.libp2p_peer.announce_content(cid)
                    
                if self.dht_discovery:
                    await anyio.wrap_future(
                        self.dht_discovery.libp2p_peer.host.get_dht().provide_async(cid)
                    )
                    
            return True
            
        except Exception as e:
            self.logger.warning(f"Error providing {cid}: {e}")
            return False
    
    async def retrieve_content(self, cid, options=None):
        """
        Retrieve content from the best available provider.
        
        Args:
            cid: Content ID to retrieve
            options: Dictionary of options like timeout, max_size, etc.
            
        Returns:
            Content data or None if not found
        """
        if options is None:
            options = {}
            
        timeout = options.get("timeout", 60)
        max_size = options.get("max_size", 10 * 1024 * 1024)  # 10MB default
        
        # Find providers
        providers = await self.find_providers(cid, count=5, timeout=timeout/3)
        
        if not providers:
            self.logger.warning(f"No providers found for {cid}")
            return None
            
        # Try each provider until successful
        for provider in providers:
            peer_id = provider.get("peer_id")
            
            try:
                self.logger.debug(f"Attempting to retrieve {cid} from {peer_id}")
                
                # Track start time for latency measurement
                start_time = time.time()
                
                # Retrieve content
                content = await self._retrieve_from_peer(
                    peer_id,
                    cid,
                    timeout=timeout/2,
                    max_size=max_size
                )
                
                if content:
                    # Successful retrieval
                    retrieval_time = time.time() - start_time
                    
                    # Update provider statistics
                    self.provider_manager.update_retrieval_result(
                        peer_id,
                        cid,
                        success=True,
                        latency=retrieval_time,
                        bytes_received=len(content)
                    )
                    
                    return content
                    
                # Failed retrieval
                self.provider_manager.update_retrieval_result(
                    peer_id,
                    cid,
                    success=False
                )
                
            except Exception as e:
                self.logger.warning(f"Error retrieving {cid} from {peer_id}: {e}")
                
                # Update provider statistics
                self.provider_manager.update_retrieval_result(
                    peer_id,
                    cid,
                    success=False
                )
                
        self.logger.warning(f"Failed to retrieve {cid} from any provider")
        return None
    
    async def _retrieve_from_peer(self, peer_id, cid, timeout, max_size):
        """
        Retrieve content from a specific peer.
        
        Args:
            peer_id: ID of the peer to retrieve from
            cid: Content ID to retrieve
            timeout: Maximum time to wait
            max_size: Maximum content size
            
        Returns:
            Content data or None
        """
        try:
            # Connect to the peer
            peer_info = self.libp2p_peer.host.get_peerstore().get_peer(peer_id)
            await self.libp2p_peer.host.connect(peer_info)
            
            # Open a stream with bitswap protocol
            stream = await anyio.wait_for(
                self.libp2p_peer.host.new_stream(peer_id, ["/ipfs/bitswap/1.2.0"]),
                timeout=10
            )
            
            try:
                # Create request message
                request = {
                    "type": "want-block",
                    "cid": cid,
                    "cancel": False
                }
                
                # Send request
                await stream.write(json.dumps(request).encode())
                
                # Read response in chunks
                content = b""
                chunk_size = 1024 * 16  # 16KB chunks
                
                start_time = time.time()
                
                while True:
                    remaining_time = timeout - (time.time() - start_time)
                    if remaining_time <= 0:
                        raise anyio.TimeoutError("Retrieval timed out")
                        
                    chunk = await anyio.wait_for(
                        stream.read(chunk_size),
                        timeout=remaining_time
                    )
                    
                    if not chunk:
                        break
                        
                    content += chunk
                    
                    # Check size limit
                    if len(content) > max_size:
                        raise ValueError(f"Content too large ({len(content)} > {max_size})")
                        
                return content
                
            finally:
                await stream.close()
                
        except Exception as e:
            self.logger.warning(f"Error retrieving from peer {peer_id}: {e}")
            return None
    
    def get_stats(self):
        """
        Get comprehensive statistics from all routing components.
        
        Returns:
            Dictionary of statistics
        """
        stats = {
            "router_usage": self.router_usage.copy(),
            "provider_manager": self.provider_manager.get_stats() if self.provider_manager else None
        }
        
        if self.recursive_router:
            stats["recursive_router"] = self.recursive_router.get_stats()
            
        if self.delegated_router:
            stats["delegated_router"] = self.delegated_router.get_stats()
            
        return stats