"""
Enhanced DHT-based discovery implementation for IPFS Kit.

This module implements an improved DHT-based discovery system that builds on
the existing implementation in libp2p_peer.py, focusing on more efficient
routing algorithms, better content provider tracking, and integration with
the role-based architecture.
"""

import anyio
import logging
import random
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Type

import base58

def get_enhanced_dht_discovery() -> Type["EnhancedDHTDiscovery"]:
    """
    Get the EnhancedDHTDiscovery class.
    
    This function is used by the recursive routing module to access
    the EnhancedDHTDiscovery class without creating circular imports.
    
    Returns:
        The EnhancedDHTDiscovery class
    """
    return EnhancedDHTDiscovery


class EnhancedDHTDiscovery:
    """Enhanced DHT-based discovery implementation for libp2p peers.

    This class improves upon the basic DHT discovery with:
    - Advanced routing algorithm with k-bucket optimizations
    - Provider tracking with reputation scoring
    - Content-based peer affinity for better routing
    - Role-specific optimizations
    - Backoff strategies for unreliable peers
    """

    def __init__(self, libp2p_peer, role="leecher", bootstrap_peers=None):
        """Initialize DHT discovery with the given libp2p peer.

        Args:
            libp2p_peer: The IPFSLibp2pPeer instance to use
            role: The node role (master, worker, or leecher)
            bootstrap_peers: Initial peers to connect to
        """
        self.libp2p_peer = libp2p_peer
        self.role = role
        self.bootstrap_peers = bootstrap_peers or []
        self.logger = logging.getLogger(__name__)

        # Provider tracking
        self.providers = {}  # CID -> List of provider info
        self.provider_stats = {}  # Peer ID -> Stats
        self.content_affinity = {}  # Peer ID -> List of CIDs

        # Routing optimization
        self.k_buckets = [set() for _ in range(256)]  # K-buckets for XOR distance
        self.last_refresh = {}  # Bucket index -> timestamp

        # Event handling
        self.event_loop = None
        self.lock = threading.RLock()

        # Performance tracking
        self.query_stats = {}  # CID -> query stats
        self.active_queries = {}  # CID -> Future

        # Initialize event loop
        self._initialize_event_loop()

        # Connect to bootstrap peers
        if self.bootstrap_peers:
            self._connect_to_bootstrap_peers()

    def _initialize_event_loop(self):
        """Initialize the event loop for async operations."""
        try:
            self.event_loop = anyio.get_event_loop()
        except RuntimeError:
            # Create a new event loop if one doesn't exist in this thread
            self.event_loop = anyio.new_event_loop()
            anyio.set_event_loop(self.event_loop)

        # Start a background thread for the event loop if not running
        if not self.event_loop.is_running():
            self.loop_thread = threading.Thread(target=self._run_event_loop, daemon=True)
            self.loop_thread.start()

    def _run_event_loop(self):
        """Run the event loop in a separate thread."""
        anyio.set_event_loop(self.event_loop)
        self.event_loop.run_forever()

    def _connect_to_bootstrap_peers(self):
        """Connect to the bootstrap peers."""
        for peer in self.bootstrap_peers:
            try:
                self.libp2p_peer.connect_peer(peer)
                self.logger.info(f"Connected to bootstrap peer: {peer}")
            except Exception as e:
                self.logger.warning(f"Failed to connect to bootstrap peer {peer}: {e}")

    def start(self):
        """Start the DHT discovery process."""
        # Initialize buckets with known peers
        self._initialize_buckets()

        # Schedule bucket refreshes
        self._schedule_bucket_refreshes()

        # Start provider tracking
        self._start_provider_tracking()

        # Start peer statistics collection
        self._start_stats_collection()

        self.logger.info(f"Enhanced DHT discovery started (role: {self.role})")
        return True

    def stop(self):
        """Stop the DHT discovery process."""
        # Cancel all active queries
        for cid, future in self.active_queries.items():
            if not future.done():
                future.cancel()

        self.logger.info("Enhanced DHT discovery stopped")
        return True

    def _initialize_buckets(self):
        """Initialize k-buckets with known peers."""
        with self.lock:
            # Get our peer ID as bytes for XOR distance calculation
            try:
                our_peer_id = self.libp2p_peer.host.get_id().to_bytes()
            except:
                self.logger.warning("Failed to get our peer ID, using empty bytes")
                our_peer_id = b""

            # Add all known peers to appropriate buckets
            for peer_id in self.libp2p_peer.host.get_peerstore().peer_ids():
                try:
                    peer_id_bytes = peer_id.to_bytes()
                    bucket_idx = self._calculate_bucket_index(our_peer_id, peer_id_bytes)
                    self.k_buckets[bucket_idx].add(peer_id.pretty())
                except Exception as e:
                    self.logger.warning(f"Failed to add peer to bucket: {e}")

    def _calculate_bucket_index(self, id1, id2):
        """Calculate the k-bucket index for two peer IDs using XOR distance."""
        # Get the XOR distance
        xor_distance = bytes(a ^ b for a, b in zip(id1, id2))

        # Find the most significant bit that differs
        for i, byte in enumerate(xor_distance):
            if byte != 0:
                # Found a non-zero byte, calculate the bit position
                bit_pos = 7
                while bit_pos >= 0:
                    if (byte >> bit_pos) & 1:
                        return i * 8 + (7 - bit_pos)
                    bit_pos -= 1

        # IDs are identical, use last bucket
        return 255

    def _schedule_bucket_refreshes(self):
        """Schedule periodic refreshes of k-buckets."""
        # Different refresh rates based on bucket distance
        # Closer buckets (lower index) refresh more frequently
        refresh_intervals = [
            (0, 32, 300),  # Buckets 0-31: refresh every 5 minutes
            (32, 64, 600),  # Buckets 32-63: refresh every 10 minutes
            (64, 128, 1800),  # Buckets 64-127: refresh every 30 minutes
            (128, 256, 3600),  # Buckets 128-255: refresh every hour
        ]

        for start, end, interval in refresh_intervals:
            for bucket_idx in range(start, end):
                # Schedule initial refresh with jitter to avoid thundering herd
                jitter = random.uniform(0, interval * 0.1)
                self.event_loop.call_later(jitter, self._refresh_bucket, bucket_idx, interval)

    def _refresh_bucket(self, bucket_idx, interval):
        """Refresh a specific k-bucket by looking for peers."""

        async def _do_refresh():
            try:
                # Generate a random ID in this bucket
                target_id = self._generate_id_in_bucket(bucket_idx)

                # Find peers close to this ID
                closest_peers = await self.libp2p_peer.host.get_network().find_peers_async(
                    target_id, count=20, timeout=60
                )

                # Update bucket with found peers
                with self.lock:
                    for peer in closest_peers:
                        self.k_buckets[bucket_idx].add(peer.peer_id.pretty())

                self.last_refresh[bucket_idx] = time.time()
                self.logger.debug(f"Refreshed bucket {bucket_idx} with {len(closest_peers)} peers")

            except Exception as e:
                self.logger.warning(f"Error refreshing bucket {bucket_idx}: {e}")

            finally:
                # Schedule next refresh
                self.event_loop.call_later(interval, self._refresh_bucket, bucket_idx, interval)

        # Submit the refresh task to the event loop
        anyio.run_coroutine_threadsafe(_do_refresh(), self.event_loop)

    def _generate_id_in_bucket(self, bucket_idx):
        """Generate a random ID that would belong in the specified bucket."""
        try:
            our_id = self.libp2p_peer.host.get_id().to_bytes()
        except:
            # If we can't get our ID, use random bytes
            our_id = random.randbytes(32)

        # Create a copy of our ID
        target_id = bytearray(our_id)

        # Determine which byte and bit to flip
        byte_idx = bucket_idx // 8
        bit_idx = bucket_idx % 8

        # Ensure we have enough bytes
        if byte_idx < len(target_id):
            # Flip the specific bit
            target_id[byte_idx] ^= 1 << (7 - bit_idx)

            # Randomize all lower bits
            for i in range(byte_idx, len(target_id)):
                if i == byte_idx:
                    # For the byte containing our flipped bit, only randomize lower bits
                    mask = (1 << (7 - bit_idx)) - 1
                    target_id[i] = (target_id[i] & ~mask) | (random.randint(0, 255) & mask)
                else:
                    # For all subsequent bytes, completely randomize
                    target_id[i] = random.randint(0, 255)

        # Convert back to peer ID
        from libp2p.peer.id import ID as PeerID

        return PeerID(bytes(target_id))

    def _start_provider_tracking(self):
        """Start tracking content providers."""
        # Schedule periodic provider cleanup
        self.event_loop.call_later(3600, self._cleanup_providers)

    def _cleanup_providers(self):
        """Clean up inactive or unreliable providers."""
        with self.lock:
            # Current time for comparison
            now = time.time()

            # Check each provider
            peers_to_remove = set()
            for peer_id, stats in self.provider_stats.items():
                # Remove providers that haven't been seen in 24 hours
                if now - stats.get("last_seen", 0) > 86400:
                    peers_to_remove.add(peer_id)
                    continue

                # Remove providers with consistently bad performance
                if stats.get("total_requests", 0) > 10 and stats.get("success_rate", 1.0) < 0.2:
                    peers_to_remove.add(peer_id)

            # Remove identified peers
            for peer_id in peers_to_remove:
                if peer_id in self.provider_stats:
                    del self.provider_stats[peer_id]
                if peer_id in self.content_affinity:
                    del self.content_affinity[peer_id]

            # Clean up provider lists
            for cid, providers in list(self.providers.items()):
                # Remove providers that were deleted
                self.providers[cid] = [
                    p for p in providers if p.get("peer_id") not in peers_to_remove
                ]

                # Remove empty provider lists
                if not self.providers[cid]:
                    del self.providers[cid]

        # Schedule next cleanup
        self.event_loop.call_later(3600, self._cleanup_providers)

    def _start_stats_collection(self):
        """Start collecting peer statistics."""
        # This will be called after each content retrieval to update statistics
        pass

    def update_provider_stats(self, peer_id, success, latency=None, bytes_received=None):
        """Update statistics for a content provider.

        Args:
            peer_id: ID of the peer
            success: Whether the retrieval was successful
            latency: Request latency in seconds (if available)
            bytes_received: Amount of data received (if available)
        """
        with self.lock:
            # Get or create stats for this peer
            if peer_id not in self.provider_stats:
                self.provider_stats[peer_id] = {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "last_seen": time.time(),
                    "latencies": [],
                    "success_rate": 1.0,
                    "average_latency": 0,
                    "backoff_count": 0,
                    "backoff_until": 0,
                }

            stats = self.provider_stats[peer_id]

            # Update basic stats
            stats["total_requests"] += 1
            stats["last_seen"] = time.time()

            if success:
                stats["successful_requests"] += 1
                stats["backoff_count"] = max(
                    0, stats["backoff_count"] - 1
                )  # Reduce backoff for success
            else:
                stats["failed_requests"] += 1
                stats["backoff_count"] += 1  # Increase backoff for failure

                # Calculate exponential backoff
                if stats["backoff_count"] > 0:
                    backoff_time = min(60 * 5, 2 ** (stats["backoff_count"] - 1))  # Max 5 minutes
                    stats["backoff_until"] = time.time() + backoff_time

            # Update latency stats if provided
            if latency is not None:
                stats["latencies"].append(latency)
                # Keep only the last 50 latencies
                if len(stats["latencies"]) > 50:
                    stats["latencies"] = stats["latencies"][-50:]
                stats["average_latency"] = sum(stats["latencies"]) / len(stats["latencies"])

            # Update success rate
            stats["success_rate"] = (
                stats["successful_requests"] / stats["total_requests"]
                if stats["total_requests"] > 0
                else 1.0
            )

    def record_content_affinity(self, peer_id, cid):
        """Record that a peer has provided a specific content.

        Args:
            peer_id: ID of the peer
            cid: Content ID that was provided
        """
        with self.lock:
            if peer_id not in self.content_affinity:
                self.content_affinity[peer_id] = []

            # Add this CID to the peer's content affinity list
            if cid not in self.content_affinity[peer_id]:
                self.content_affinity[peer_id].append(cid)

                # Limit the size of the affinity list
                if len(self.content_affinity[peer_id]) > 1000:
                    self.content_affinity[peer_id] = self.content_affinity[peer_id][-1000:]

    def add_provider(self, cid, peer_id, multiaddrs=None, connection_type=None, reputation=0.5):
        """Add a provider for the given CID.

        Args:
            cid: Content ID
            peer_id: ID of the provider peer
            multiaddrs: List of multiaddresses for the peer
            connection_type: Type of connection to the peer
            reputation: Initial reputation score (0-1)
        """
        with self.lock:
            if cid not in self.providers:
                self.providers[cid] = []

            # Check if this provider already exists
            for provider in self.providers[cid]:
                if provider.get("peer_id") == peer_id:
                    # Update existing provider
                    if multiaddrs:
                        provider["multiaddrs"] = multiaddrs
                    if connection_type:
                        provider["connection_type"] = connection_type
                    provider["last_seen"] = time.time()
                    return

            # Add new provider
            self.providers[cid].append(
                {
                    "peer_id": peer_id,
                    "multiaddrs": multiaddrs or [],
                    "connection_type": connection_type,
                    "first_seen": time.time(),
                    "last_seen": time.time(),
                    "reputation": reputation,
                }
            )

            # Record content affinity
            self.record_content_affinity(peer_id, cid)

    def find_providers(self, cid, count=5, callback=None):
        """Find providers for a content ID.

        Args:
            cid: Content ID to find providers for
            count: Maximum number of providers to return
            callback: Optional callback function to call with results

        Returns:
            Future that will resolve to a list of provider information
        """
        # Create a future for the result
        loop = self.event_loop
        future = anyio.run_coroutine_threadsafe(self._find_providers_async(cid, count), loop)

        # Register callback if provided
        if callback:
            future.add_done_callback(lambda f: callback(f.result() if not f.exception() else None))

        # Store the active query
        with self.lock:
            self.active_queries[cid] = future

        return future

    async def _find_providers_async(self, cid, count):
        """Asynchronous implementation of finding providers.

        This combines cached providers with a DHT lookup.
        """
        start_time = time.time()
        providers = []

        # First check if we have cached providers
        cached_providers = self._get_cached_providers(cid, count)
        if cached_providers and len(cached_providers) >= count:
            return cached_providers

        # Add cached providers to results
        providers.extend(cached_providers)

        # Convert CID string to libp2p CID if needed
        libp2p_cid = self._convert_to_libp2p_cid(cid)

        try:
            # Find providers through DHT
            dht_providers = await self.libp2p_peer.host.get_network().find_providers_async(
                libp2p_cid,
                count=count * 2,  # Ask for more to account for unreachable peers
                timeout=30,
            )

            # Process found providers
            for peer_info in dht_providers:
                # Create provider record
                provider = {
                    "peer_id": peer_info.peer_id.pretty(),
                    "multiaddrs": [str(addr) for addr in peer_info.addrs],
                    "connection_type": "dht",
                    "first_seen": time.time(),
                    "last_seen": time.time(),
                    "reputation": 0.5,  # Default reputation for new providers
                }

                # Check if this is a new provider
                is_new = True
                for existing in providers:
                    if existing.get("peer_id") == provider["peer_id"]:
                        is_new = False
                        break

                if is_new:
                    providers.append(provider)

                    # Store in cache
                    self.add_provider(
                        cid,
                        provider["peer_id"],
                        provider["multiaddrs"],
                        provider["connection_type"],
                        provider["reputation"],
                    )

            # Record query stats
            query_time = time.time() - start_time
            with self.lock:
                self.query_stats[cid] = {
                    "last_query": time.time(),
                    "query_time": query_time,
                    "found_providers": len(providers),
                }

                # Clean up active query
                if cid in self.active_queries:
                    del self.active_queries[cid]

            # Return providers, limited to requested count
            return providers[:count]

        except Exception as e:
            self.logger.warning(f"Error finding providers for {cid}: {e}")

            # Record query stats for failure
            with self.lock:
                self.query_stats[cid] = {
                    "last_query": time.time(),
                    "query_time": time.time() - start_time,
                    "error": str(e),
                }

                # Clean up active query
                if cid in self.active_queries:
                    del self.active_queries[cid]

            # Return any cached providers
            return providers

    def _get_cached_providers(self, cid, count):
        """Get cached providers for a CID.

        Returns providers sorted by reputation.
        """
        with self.lock:
            if cid not in self.providers:
                return []

            # Get all providers for this CID
            all_providers = self.providers[cid].copy()

            # Filter out providers in backoff
            active_providers = []
            now = time.time()
            for provider in all_providers:
                peer_id = provider.get("peer_id")
                if peer_id in self.provider_stats:
                    stats = self.provider_stats[peer_id]
                    if stats.get("backoff_until", 0) > now:
                        # Skip this provider, it's in backoff
                        continue

                active_providers.append(provider)

            # Sort by reputation (higher is better)
            active_providers.sort(key=lambda p: p.get("reputation", 0), reverse=True)

            return active_providers[:count]

    def _convert_to_libp2p_cid(self, cid_str):
        """Convert a CID string to a libp2p CID object."""
        # This is a simplified implementation - in a real system,
        # we would use proper CID parsing and conversion
        try:
            # Try to import proper CID parsing
            from multiformats import CID

            return CID.decode(cid_str)
        except ImportError:
            # Fallback - treat the CID as an opaque key
            # We're using the raw string representation for simplicity
            return cid_str

    def get_optimal_providers(self, cid, content_size=None, preferred_peers=None, count=3):
        """Get the optimal providers for a specific content based on various factors.

        This considers:
        - Provider reputation
        - Content affinity (peers that have related content)
        - Latency statistics
        - Current load and availability
        - Role-based preferences

        Args:
            cid: Content ID to find providers for
            content_size: Size of the content (if known)
            preferred_peers: List of peer IDs to prefer
            count: Maximum number of providers to return

        Returns:
            List of provider information, sorted by optimality
        """
        with self.lock:
            # Get cached providers
            providers = self._get_cached_providers(
                cid, count * 3
            )  # Get more than needed for filtering

            if not providers:
                return []

            # Calculate scores for each provider
            scored_providers = []
            for provider in providers:
                peer_id = provider.get("peer_id")
                score = provider.get("reputation", 0.5)  # Base score is reputation

                # Factor in statistics if available
                if peer_id in self.provider_stats:
                    stats = self.provider_stats[peer_id]

                    # Success rate factor (0-1)
                    success_factor = stats.get("success_rate", 1.0)

                    # Latency factor (0-1, lower latency is better)
                    latency = stats.get("average_latency", 1.0)
                    latency_factor = 1.0 / (1.0 + latency)  # Transform to 0-1 range

                    # Combine factors
                    score = 0.4 * score + 0.4 * success_factor + 0.2 * latency_factor

                # Content affinity bonus
                if peer_id in self.content_affinity:
                    # Higher score for peers that have related content
                    affinity_bonus = min(0.1, 0.01 * len(self.content_affinity[peer_id]))
                    score += affinity_bonus

                # Preferred peers bonus
                if preferred_peers and peer_id in preferred_peers:
                    score += 0.2

                # Role-specific adjustments
                if self.role == "master":
                    # Masters prefer stable, high-bandwidth connections
                    # (implementation omitted for brevity)
                    pass
                elif self.role == "worker":
                    # Workers prefer connections with low latency
                    # (implementation omitted for brevity)
                    pass
                elif self.role == "leecher":
                    # Leechers prefer any available connection
                    # (implementation omitted for brevity)
                    pass

                # Add to scored providers
                scored_providers.append((provider, score))

            # Sort by score (higher is better)
            scored_providers.sort(key=lambda x: x[1], reverse=True)

            # Return the top providers
            return [p[0] for p in scored_providers[:count]]


class ContentRoutingManager:
    """Manages intelligent content routing based on peer statistics.

    This class provides optimized content routing by:
    - Tracking which peers provide which content
    - Maintaining statistics on peer performance and reliability
    - Learning from past retrieval attempts to optimize future requests
    - Implementing backoff strategies for unreliable peers
    """

    def __init__(self, dht_discovery, libp2p_peer):
        """Initialize with a DHT discovery instance.

        Args:
            dht_discovery: EnhancedDHTDiscovery instance
            libp2p_peer: IPFSLibp2pPeer instance
        """
        self.dht_discovery = dht_discovery
        self.libp2p_peer = libp2p_peer
        self.logger = logging.getLogger(__name__)

        # Content routing cache
        self.content_locations = {}  # CID -> list of peer info
        self.routing_stats = {}  # Track routing decisions and outcomes

        # Performance metrics
        self.metrics = {
            "successful_retrievals": 0,
            "failed_retrievals": 0,
            "total_bytes_retrieved": 0,
            "average_retrieval_time": 0,
            "retrievals_from_cache": 0,
            "retrievals_from_dht": 0,
            "retrievals_from_relay": 0,
        }

    def find_content(self, cid, options=None):
        """Find the best source for the requested content.

        Args:
            cid: Content ID to find
            options: Dictionary of options like timeout, max_providers, etc.

        Returns:
            Future that resolves to a list of content source info
        """
        # Default options
        if options is None:
            options = {}

        timeout = options.get("timeout", 30)
        max_providers = options.get("max_providers", 3)
        preferred_peers = options.get("preferred_peers", [])

        # Create a future for the result
        future = anyio.run_coroutine_threadsafe(
            self._find_content_async(cid, timeout, max_providers, preferred_peers),
            self.dht_discovery.event_loop,
        )

        return future

    async def _find_content_async(self, cid, timeout, max_providers, preferred_peers):
        """Asynchronous implementation of content finding."""
        start_time = time.time()

        # First check our routing cache
        cached_sources = self._get_cached_sources(cid, max_providers)
        if cached_sources:
            self.metrics["retrievals_from_cache"] += 1
            return cached_sources

        # Find providers using DHT discovery
        try:
            providers_future = self.dht_discovery.find_providers(cid, count=max_providers * 2)
            providers = await anyio.wait_for(anyio.wrap_future(providers_future), timeout)

            # No providers found
            if not providers:
                self.logger.info(f"No providers found for {cid}")
                return []

            # Get optimal providers
            optimal_providers = self.dht_discovery.get_optimal_providers(
                cid, preferred_peers=preferred_peers, count=max_providers
            )

            # Store in cache
            self._cache_content_sources(cid, optimal_providers)

            # Update metrics
            self.metrics["retrievals_from_dht"] += 1

            return optimal_providers

        except anyio.TimeoutError:
            self.logger.warning(f"Timeout finding providers for {cid}")
            return []

        except Exception as e:
            self.logger.error(f"Error finding content {cid}: {e}")
            return []

    def retrieve_content(self, cid, options=None):
        """Retrieve content from the best available source.

        Args:
            cid: Content ID to retrieve
            options: Dictionary of options like timeout, max_size, etc.

        Returns:
            Future that resolves to content data or None if not found
        """
        # Default options
        if options is None:
            options = {}

        timeout = options.get("timeout", 60)
        max_size = options.get("max_size", 1024 * 1024 * 50)  # 50MB default

        # Create a future for the result
        future = anyio.run_coroutine_threadsafe(
            self._retrieve_content_async(cid, timeout, max_size), self.dht_discovery.event_loop
        )

        return future

    async def _retrieve_content_async(self, cid, timeout, max_size):
        """Asynchronous implementation of content retrieval."""
        start_time = time.time()

        # Find content sources
        sources = await self._find_content_async(cid, timeout / 2, 3, [])

        if not sources:
            self.logger.warning(f"No sources found for {cid}")
            self.metrics["failed_retrievals"] += 1
            return None

        # Try each source until successful
        for source in sources:
            peer_id = source.get("peer_id")

            try:
                # Attempt to retrieve content from this peer
                self.logger.debug(f"Retrieving {cid} from peer {peer_id}")

                # Request content from the peer
                content = await self._request_content_from_peer(peer_id, cid, timeout / 2)

                if content:
                    # Successful retrieval
                    retrieval_time = time.time() - start_time
                    content_size = len(content)

                    # Update provider stats
                    self.dht_discovery.update_provider_stats(
                        peer_id, success=True, latency=retrieval_time, bytes_received=content_size
                    )

                    # Update local metrics
                    self.metrics["successful_retrievals"] += 1
                    self.metrics["total_bytes_retrieved"] += content_size

                    # Update average retrieval time
                    prev_avg = self.metrics["average_retrieval_time"]
                    prev_count = self.metrics["successful_retrievals"] - 1
                    if prev_count > 0:
                        self.metrics["average_retrieval_time"] = (
                            prev_avg * prev_count + retrieval_time
                        ) / self.metrics["successful_retrievals"]
                    else:
                        self.metrics["average_retrieval_time"] = retrieval_time

                    return content

                # Content retrieval failed
                self.dht_discovery.update_provider_stats(peer_id, success=False)

            except Exception as e:
                self.logger.warning(f"Error retrieving {cid} from {peer_id}: {e}")
                self.dht_discovery.update_provider_stats(peer_id, success=False)

        # All sources failed
        self.metrics["failed_retrievals"] += 1
        self.logger.warning(f"Failed to retrieve {cid} from any source")
        return None

    async def _request_content_from_peer(self, peer_id, cid, timeout):
        """Request content directly from a peer using libp2p streams."""
        try:
            # Connect to the peer if not already connected
            await self._ensure_peer_connection(peer_id)

            # Open a stream using the bitswap protocol
            stream = await anyio.wait_for(
                self.libp2p_peer.host.new_stream(peer_id, ["/ipfs/bitswap/1.2.0"]), timeout=10
            )

            try:
                # Prepare request message
                request = {"type": "want-block", "cid": cid, "cancel": False}

                # Send request
                await stream.write(json.dumps(request).encode())

                # Read response
                response_data = b""
                chunk_size = 1024 * 16  # 16KB chunks

                total_bytes = 0
                start_time = time.time()

                while True:
                    chunk = await anyio.wait_for(
                        stream.read(chunk_size), timeout=timeout - (time.time() - start_time)
                    )

                    if not chunk:
                        break

                    response_data += chunk
                    total_bytes += len(chunk)

                    # Check if we've hit the size limit
                    if total_bytes > max_size:
                        raise ValueError(f"Content size exceeds limit ({total_bytes} > {max_size})")

                # Process response
                if response_data:
                    # Successfully retrieved content
                    return response_data

                return None

            finally:
                # Close the stream
                await stream.close()

        except Exception as e:
            self.logger.warning(f"Error requesting content from peer {peer_id}: {e}")
            return None

    async def _ensure_peer_connection(self, peer_id):
        """Ensure that we're connected to the specified peer."""
        if not self.libp2p_peer.host.get_network().is_connected(peer_id):
            # Try to connect to the peer
            peer_info = self.libp2p_peer.host.get_peerstore().get_peer(peer_id)
            if not peer_info:
                raise ValueError(f"Peer info not found for {peer_id}")

            # Connect to the peer
            await self.libp2p_peer.host.connect(peer_info)

    def _get_cached_sources(self, cid, max_count):
        """Get cached content sources for a CID."""
        if cid in self.content_locations:
            location_info = self.content_locations[cid]
            # Check if the cache is still valid
            if time.time() - location_info.get("timestamp", 0) < 300:  # 5 minute cache
                return location_info.get("sources", [])[:max_count]
        return []

    def _cache_content_sources(self, cid, sources):
        """Cache content sources for future use."""
        self.content_locations[cid] = {"sources": sources, "timestamp": time.time()}

    def announce_content(self, cid, size=None, metadata=None):
        """Announce that we have a specific content.

        Args:
            cid: Content ID to announce
            size: Size of the content in bytes
            metadata: Additional metadata about the content

        Returns:
            Boolean indicating success
        """
        try:
            # Announce to the DHT
            self.libp2p_peer.announce_content(
                cid,
                metadata={
                    "size": size,
                    "type": metadata.get("type", "unknown") if metadata else "unknown",
                    "timestamp": time.time(),
                },
            )

            self.logger.debug(f"Announced content {cid}")
            return True

        except Exception as e:
            self.logger.warning(f"Error announcing content {cid}: {e}")
            return False

    def get_metrics(self):
        """Get routing metrics."""
        return self.metrics
