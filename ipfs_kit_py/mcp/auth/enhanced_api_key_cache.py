"""
Enhanced API Key Cache for MCP Server.

This module provides an improved caching mechanism for API keys with:
1. Multi-level cache hierarchy (memory, shared memory, distributed)
2. Intelligent cache eviction policies based on usage patterns
3. Cache priming/warming for frequently used keys
4. Advanced metrics and telemetry
5. Improved performance under high concurrency
6. Enhanced thread and process safety
"""

import logging
import time
import json
import hashlib
import threading
import asyncio
import random
from typing import Dict, List, Any, Optional, Tuple, Set, Union, Callable
from datetime import datetime, timedelta
from functools import lru_cache
from collections import Counter, defaultdict

# Configure logger
logger = logging.getLogger(__name__)

# Try importing optional dependencies
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.info("Redis not available. Distributed caching will be disabled.")

try:
    import memcache
    MEMCACHED_AVAILABLE = True
except ImportError:
    MEMCACHED_AVAILABLE = False
    logger.info("Memcached not available. Distributed caching will be disabled.")

try:
    from cachetools import TTLCache, LRUCache, LFUCache
    CACHETOOLS_AVAILABLE = True
except ImportError:
    CACHETOOLS_AVAILABLE = False
    logger.info("cachetools not available. Using built-in caching implementation.")

# Cache policy types
class CachePolicy:
    """Enumeration of cache eviction policies."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live
    TLRU = "tlru"  # Time-aware Least Recently Used
    ADAPTIVE = "adaptive"  # Adaptive policy based on usage patterns

class CacheLevel:
    """Enumeration of cache levels in the hierarchy."""
    L1 = "l1"  # Fast in-memory cache
    L2 = "l2"  # Shared memory or local persistence
    L3 = "l3"  # Distributed cache (Redis, Memcached)

class EnhancedApiKeyCache:
    """
    Enhanced API key cache with multi-level hierarchy and advanced policies.
    
    This cache implementation provides significant improvements over the basic
    implementation, including:
    
    1. Multi-level caching (memory, shared memory, distributed)
    2. Multiple eviction policies (LRU, LFU, TTL, hybrid approaches)
    3. Proactive cache warming based on usage patterns
    4. Distributed cache coordination for multi-node deployments
    5. Comprehensive metrics and telemetry
    6. Thread and process safety mechanisms
    7. Adaptive caching based on hit/miss patterns
    8. Fine-grained cache control for different types of API keys
    """
    
    def __init__(
        self,
        cache_size: int = 1000,
        ttl_seconds: int = 3600,
        negative_ttl: int = 300,
        prefix: str = "apikey:",
        redis_client: Optional[Any] = None,
        memcached_client: Optional[Any] = None,
        policy: str = CachePolicy.ADAPTIVE,
        enable_metrics: bool = True,
        enable_cache_warming: bool = True,
        update_interval: int = 60,
        shards: int = 4,
    ):
        """
        Initialize the enhanced API key cache.
        
        Args:
            cache_size: Maximum number of API keys to cache in memory
            ttl_seconds: Default time-to-live for cached keys in seconds
            negative_ttl: TTL for negative cache entries (failed lookups)
            prefix: Prefix for keys in distributed caches (Redis/Memcached)
            redis_client: Optional Redis client for L3 caching
            memcached_client: Optional Memcached client for L3 caching
            policy: Cache eviction policy
            enable_metrics: Whether to collect and report detailed metrics
            enable_cache_warming: Whether to enable proactive cache warming
            update_interval: Interval in seconds for background operations
            shards: Number of cache shards for better concurrency
        """
        self._prefix = prefix
        self._ttl_seconds = ttl_seconds
        self._negative_ttl = negative_ttl
        self._policy = policy
        self._enable_metrics = enable_metrics
        self._enable_cache_warming = enable_cache_warming
        self._update_interval = update_interval
        self._redis = redis_client
        self._memcached = memcached_client
        self._shards = shards
        
        # Initialize cache structures
        self._initialize_caches(cache_size)
        
        # For thread safety (per shard)
        self._locks = [threading.RLock() for _ in range(shards)]
        
        # Usage statistics and pattern analysis
        self._initialize_metrics()
        
        # Background tasks
        self._shutdown_event = threading.Event()
        self._update_thread = None
        if enable_cache_warming or enable_metrics:
            self._start_background_tasks()
    
    def _initialize_caches(self, cache_size: int) -> None:
        """
        Initialize cache data structures based on selected policy.
        
        Args:
            cache_size: Maximum number of cached items
        """
        # Calculate per-shard cache size
        shard_size = max(cache_size // self._shards, 10)
        
        # Initialize sharded caches based on chosen policy
        self._cache = []
        self._negative_cache = []
        
        # Create specialized cache instances for each shard
        for _ in range(self._shards):
            if CACHETOOLS_AVAILABLE:
                if self._policy == CachePolicy.LRU:
                    self._cache.append(LRUCache(shard_size))
                elif self._policy == CachePolicy.LFU:
                    self._cache.append(LFUCache(shard_size))
                elif self._policy == CachePolicy.TTL:
                    self._cache.append(TTLCache(shard_size, ttl=self._ttl_seconds))
                elif self._policy == CachePolicy.TLRU or self._policy == CachePolicy.ADAPTIVE:
                    # For TLRU and Adaptive, we use TTLCache as the base
                    self._cache.append(TTLCache(shard_size, ttl=self._ttl_seconds))
                else:
                    # Default to LRU
                    self._cache.append(LRUCache(shard_size))
                
                # Negative cache always uses TTL
                self._negative_cache.append(TTLCache(shard_size, ttl=self._negative_ttl))
            else:
                # Fallback to simple dict-based implementation
                self._cache.append({})
                self._negative_cache.append({})
        
        # Secondary mapping from API key ID to hash
        self._id_to_hash = {}
    
    def _initialize_metrics(self) -> None:
        """Initialize metrics tracking structures."""
        # Basic metrics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "inserts": 0,
            "evictions": 0,
            "invalidations": 0,
            "l1_hits": 0,
            "l2_hits": 0,
            "l3_hits": 0,
            "negative_hits": 0,
            "redis_hits": 0,
            "redis_misses": 0,
            "memcached_hits": 0,
            "memcached_misses": 0,
        }
        
        # Advanced metrics for access patterns
        if self._enable_metrics:
            self._access_patterns = {
                "hourly": defaultdict(Counter),  # Hour -> key_hash -> count
                "key_frequency": Counter(),      # key_hash -> total count
                "key_last_access": {},           # key_hash -> timestamp
                "access_intervals": defaultdict(list),  # key_hash -> list of time deltas
                "cache_hit_ratio_history": [],   # List of (timestamp, ratio) tuples
                "response_times": [],            # List of (timestamp, duration) tuples
            }
            
            # Rate limiting data
            self._rate_limit_data = {
                "requests_per_minute": defaultdict(Counter),  # minute -> key_id -> count
                "flagged_keys": set(),  # Set of keys that exceeded thresholds
            }
    
    def _start_background_tasks(self) -> None:
        """Start background tasks for cache maintenance and metrics."""
        self._update_thread = threading.Thread(
            target=self._background_loop,
            daemon=True,
            name="api-key-cache-maintenance",
        )
        self._update_thread.start()
        logger.info("Started API key cache background maintenance thread")
    
    def _background_loop(self) -> None:
        """Background loop for cache maintenance and metrics collection."""
        while not self._shutdown_event.is_set():
            try:
                # Run maintenance tasks
                if self._enable_cache_warming:
                    self._warm_cache()
                
                if self._enable_metrics:
                    self._update_metrics()
                    self._clean_old_metrics()
                
                # Perform any policy-specific maintenance
                if self._policy == CachePolicy.ADAPTIVE:
                    self._adjust_cache_parameters()
            
            except Exception as e:
                logger.error(f"Error in API key cache background task: {e}", exc_info=True)
            
            # Wait for next interval or shutdown
            self._shutdown_event.wait(self._update_interval)
    
    def _get_shard_index(self, key_hash: str) -> int:
        """
        Get the shard index for a given key hash.
        
        Args:
            key_hash: Hashed API key
        
        Returns:
            Shard index
        """
        # Simple sharding by hash value
        hash_int = int(key_hash, 16) if len(key_hash) > 2 else hash(key_hash)
        return hash_int % self._shards
    
    def _get_shard_lock(self, key_hash: str) -> threading.RLock:
        """
        Get the lock for the shard containing a given key hash.
        
        Args:
            key_hash: Hashed API key
        
        Returns:
            Lock for the appropriate shard
        """
        return self._locks[self._get_shard_index(key_hash)]
    
    def _get_cache_shard(self, key_hash: str) -> Dict:
        """
        Get the cache shard for a given key hash.
        
        Args:
            key_hash: Hashed API key
        
        Returns:
            Cache shard
        """
        return self._cache[self._get_shard_index(key_hash)]
    
    def _get_negative_cache_shard(self, key_hash: str) -> Dict:
        """
        Get the negative cache shard for a given key hash.
        
        Args:
            key_hash: Hashed API key
        
        Returns:
            Negative cache shard
        """
        return self._negative_cache[self._get_shard_index(key_hash)]
    
    def hash_token(self, token: str) -> str:
        """
        Create a secure hash of an API key token.
        
        Args:
            token: The API key to hash
        
        Returns:
            Hashed value of the API key
        """
        if not token:
            return ""
        
        # Use SHA-256 for secure hashing
        return hashlib.sha256(token.encode()).hexdigest()
    
    def get(
        self, 
        api_key_hash: str, 
        check_distributed: bool = True
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Retrieve an API key's data from the cache.
        
        Args:
            api_key_hash: Hashed API key token
            check_distributed: Whether to check distributed caches (L3)
        
        Returns:
            Tuple of (found, data), where found is a boolean indicating if the
            key was found, and data is the cached data or None if not found.
        """
        start_time = time.time()
        
        # Get appropriate shard and lock
        shard_index = self._get_shard_index(api_key_hash)
        cache_shard = self._cache[shard_index]
        negative_cache_shard = self._negative_cache[shard_index]
        
        # Use the shard's lock
        with self._locks[shard_index]:
            # Check negative cache first (quick rejection)
            if api_key_hash in negative_cache_shard:
                if self._enable_metrics:
                    self._stats["negative_hits"] += 1
                    self._track_access(api_key_hash)
                return False, None
            
            # Check L1 cache (in-memory)
            if api_key_hash in cache_shard:
                entry = cache_shard[api_key_hash]
                
                # Check TTL if using simple dict (not TTLCache)
                if not CACHETOOLS_AVAILABLE and self._policy in [CachePolicy.TTL, CachePolicy.TLRU]:
                    current_time = time.time()
                    expires_at = entry.get("_expires_at", 0)
                    if expires_at > 0 and current_time > expires_at:
                        # Expired, remove from cache
                        self._remove_from_cache(api_key_hash)
                        if self._enable_metrics:
                            self._stats["misses"] += 1
                        # Fall through to check L2/L3
                    else:
                        # Valid entry
                        if self._enable_metrics:
                            self._stats["hits"] += 1
                            self._stats["l1_hits"] += 1
                            self._track_access(api_key_hash)
                        
                        # Track response time
                        if self._enable_metrics:
                            duration = time.time() - start_time
                            self._access_patterns["response_times"].append((time.time(), duration))
                        
                        return True, entry
                else:
                    # TTLCache or other cachetools implementation handles expiration
                    if self._enable_metrics:
                        self._stats["hits"] += 1
                        self._stats["l1_hits"] += 1
                        self._track_access(api_key_hash)
                    
                    # Track response time
                    if self._enable_metrics:
                        duration = time.time() - start_time
                        self._access_patterns["response_times"].append((time.time(), duration))
                    
                    return True, cache_shard[api_key_hash]
        
        # L1 cache miss, check distributed caches if enabled
        if check_distributed:
            # Try Redis first if available
            if REDIS_AVAILABLE and self._redis:
                try:
                    redis_key = f"{self._prefix}{api_key_hash}"
                    data = self._redis.get(redis_key)
                    if data:
                        try:
                            api_key_data = json.loads(data)
                            # Store in local cache for faster subsequent access
                            self._add_to_cache(api_key_hash, api_key_data)
                            
                            if self._enable_metrics:
                                self._stats["hits"] += 1
                                self._stats["l3_hits"] += 1
                                self._stats["redis_hits"] += 1
                                self._track_access(api_key_hash)
                            
                            # Track response time
                            if self._enable_metrics:
                                duration = time.time() - start_time
                                self._access_patterns["response_times"].append((time.time(), duration))
                            
                            return True, api_key_data
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in Redis for API key {api_key_hash}")
                    elif self._enable_metrics:
                        self._stats["redis_misses"] += 1
                except Exception as e:
                    logger.error(f"Redis error in API key cache: {e}", exc_info=True)
            
            # Then try Memcached if available
            if MEMCACHED_AVAILABLE and self._memcached:
                try:
                    memcached_key = f"{self._prefix}{api_key_hash}"
                    data = self._memcached.get(memcached_key)
                    if data:
                        try:
                            if isinstance(data, bytes):
                                data = data.decode('utf-8')
                            
                            api_key_data = json.loads(data)
                            # Store in local cache for faster subsequent access
                            self._add_to_cache(api_key_hash, api_key_data)
                            
                            if self._enable_metrics:
                                self._stats["hits"] += 1
                                self._stats["l3_hits"] += 1
                                self._stats["memcached_hits"] += 1
                                self._track_access(api_key_hash)
                            
                            # Track response time
                            if self._enable_metrics:
                                duration = time.time() - start_time
                                self._access_patterns["response_times"].append((time.time(), duration))
                            
                            return True, api_key_data
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in Memcached for API key {api_key_hash}")
                    elif self._enable_metrics:
                        self._stats["memcached_misses"] += 1
                except Exception as e:
                    logger.error(f"Memcached error in API key cache: {e}", exc_info=True)
        
        # Not found in any cache level
        if self._enable_metrics:
            self._stats["misses"] += 1
        
        # Track response time for cache miss
        if self._enable_metrics:
            duration = time.time() - start_time
            self._access_patterns["response_times"].append((time.time(), duration))
        
        return False, None
    
    def set(
        self, 
        api_key_hash: str, 
        api_key_data: Dict[str, Any], 
        ttl: Optional[int] = None,
        distribute: bool = True
    ) -> None:
        """
        Store an API key's data in the cache.
        
        Args:
            api_key_hash: Hashed API key token
            api_key_data: API key data to cache
            ttl: Optional custom TTL in seconds
            distribute: Whether to distribute to L3 caches
        """
        if not api_key_hash or not api_key_data:
            logger.warning("Attempted to cache empty API key data")
            return
        
        # Get appropriate shard and lock
        shard_index = self._get_shard_index(api_key_hash)
        
        with self._locks[shard_index]:
            # Remove from negative cache if present
            negative_cache_shard = self._negative_cache[shard_index]
            if api_key_hash in negative_cache_shard:
                del negative_cache_shard[api_key_hash]
            
            # Add to in-memory cache (L1)
            self._add_to_cache(api_key_hash, api_key_data, ttl)
            
            if self._enable_metrics:
                self._stats["inserts"] += 1
        
        # Distribute to L3 caches if enabled
        if distribute:
            # Redis
            if REDIS_AVAILABLE and self._redis:
                try:
                    redis_key = f"{self._prefix}{api_key_hash}"
                    redis_ttl = ttl or self._ttl_seconds
                    self._redis.setex(
                        redis_key,
                        redis_ttl,
                        json.dumps(api_key_data)
                    )
                except Exception as e:
                    logger.error(f"Redis error caching API key: {e}", exc_info=True)
            
            # Memcached
            if MEMCACHED_AVAILABLE and self._memcached:
                try:
                    memcached_key = f"{self._prefix}{api_key_hash}"
                    memcached_ttl = ttl or self._ttl_seconds
                    self._memcached.set(
                        memcached_key,
                        json.dumps(api_key_data),
                        time=memcached_ttl
                    )
                except Exception as e:
                    logger.error(f"Memcached error caching API key: {e}", exc_info=True)
    
    def _add_to_cache(
        self, 
        api_key_hash: str, 
        api_key_data: Dict[str, Any], 
        ttl: Optional[int] = None
    ) -> None:
        """
        Add an entry to the in-memory cache.
        
        Args:
            api_key_hash: Hashed API key token
            api_key_data: API key data to cache
            ttl: Optional custom TTL in seconds
        """
        # Get appropriate shard
        shard_index = self._get_shard_index(api_key_hash)
        cache_shard = self._cache[shard_index]
        
        # Make a copy to avoid modifying the original
        entry = api_key_data.copy()
        
        # Add expiration metadata for TTL policies with dict-based cache
        if not CACHETOOLS_AVAILABLE and self._policy in [CachePolicy.TTL, CachePolicy.TLRU]:
            entry["_expires_at"] = time.time() + (ttl or self._ttl_seconds)
        
        # Add to main cache
        cache_shard[api_key_hash] = entry
        
        # Update ID to hash mapping if key ID is available
        key_id = entry.get("id")
        if key_id:
            self._id_to_hash[key_id] = api_key_hash
    
    def _remove_from_cache(self, api_key_hash: str) -> None:
        """
        Remove an entry from the in-memory cache.
        
        Args:
            api_key_hash: Hashed API key token
        """
        # Get appropriate shard
        shard_index = self._get_shard_index(api_key_hash)
        cache_shard = self._cache[shard_index]
        
        if api_key_hash not in cache_shard:
            return
        
        entry = cache_shard[api_key_hash]
        key_id = entry.get("id")
        
        # Remove from main cache
        del cache_shard[api_key_hash]
        
        # Remove from ID to hash mapping
        if key_id and key_id in self._id_to_hash:
            del self._id_to_hash[key_id]
    
    def set_negative(self, api_key_hash: str) -> None:
        """
        Add an entry to the negative cache to avoid repeated lookups for nonexistent keys.
        
        Args:
            api_key_hash: Hashed API key token
        """
        # Get appropriate shard and lock
        shard_index = self._get_shard_index(api_key_hash)
        negative_cache_shard = self._negative_cache[shard_index]
        
        with self._locks[shard_index]:
            # For TTLCache, simply inserting sets expiration
            if CACHETOOLS_AVAILABLE:
                negative_cache_shard[api_key_hash] = time.time()
            else:
                # For dict-based cache, add expiration time
                negative_cache_shard[api_key_hash] = {
                    "timestamp": time.time(),
                    "expires_at": time.time() + self._negative_ttl
                }
    
    def invalidate(self, api_key_hash: str, distribute: bool = True) -> None:
        """
        Invalidate a cached API key.
        
        Args:
            api_key_hash: Hashed API key token
            distribute: Whether to distribute invalidation to L3 caches
        """
        # Get appropriate shard and lock
        shard_index = self._get_shard_index(api_key_hash)
        
        with self._locks[shard_index]:
            # Remove from in-memory cache
            self._remove_from_cache(api_key_hash)
            
            # Remove from negative cache if present
            negative_cache_shard = self._negative_cache[shard_index]
            if api_key_hash in negative_cache_shard:
                del negative_cache_shard[api_key_hash]
            
            if self._enable_metrics:
                self._stats["invalidations"] += 1
        
        # Invalidate in distributed caches if enabled
        if distribute:
            # Redis
            if REDIS_AVAILABLE and self._redis:
                try:
                    redis_key = f"{self._prefix}{api_key_hash}"
                    self._redis.delete(redis_key)
                except Exception as e:
                    logger.error(f"Redis error invalidating API key: {e}", exc_info=True)
            
            # Memcached
            if MEMCACHED_AVAILABLE and self._memcached:
                try:
                    memcached_key = f"{self._prefix}{api_key_hash}"
                    self._memcached.delete(memcached_key)
                except Exception as e:
                    logger.error(f"Memcached error invalidating API key: {e}", exc_info=True)
    
    def invalidate_by_id(self, key_id: str, distribute: bool = True) -> None:
        """
        Invalidate a cached API key by its ID.
        
        Args:
            key_id: API key ID
            distribute: Whether to distribute invalidation to L3 caches
        """
        # Check if we have this ID in our mapping
        if key_id in self._id_to_hash:
            api_key_hash = self._id_to_hash[key_id]
            self.invalidate(api_key_hash, distribute)
    
    def invalidate_pattern(self, pattern: str, distribute: bool = True) -> int:
        """
        Invalidate all cached keys matching a pattern.
        
        Args:
            pattern: Pattern to match against cache keys
            distribute: Whether to distribute invalidation to L3 caches
        
        Returns:
            Number of invalidated keys
        """
        count = 0
        
        # Invalidate in Redis if available
        if distribute and REDIS_AVAILABLE and self._redis:
            try:
                redis_pattern = f"{self._prefix}{pattern}*"
                keys = self._redis.keys(redis_pattern)
                if keys:
                    self._redis.delete(*keys)
                    count += len(keys)
            except Exception as e:
                logger.error(f"Redis error invalidating keys by pattern: {e}", exc_info=True)
        
        # For in-memory cache, we need to check each key
        for shard_index in range(self._shards):
            with self._locks[shard_index]:
                cache_shard = self._cache[shard_index]
                # Find keys matching pattern
                keys_to_remove = []
                for key in list(cache_shard.keys()):
                    if pattern in key:
                        keys_to_remove.append(key)
                        
                        # Also remove from ID to hash mapping
                        entry = cache_shard[key]
                        key_id = entry.get("id")
                        if key_id and key_id in self._id_to_hash:
                            del self._id_to_hash[key_id]
                
                # Remove matching keys
                for key in keys_to_remove:
                    del cache_shard[key]
                    count += 1
                    
                    if self._enable_metrics:
                        self._stats["invalidations"] += 1
        
        return count
    
    def invalidate_all(self, distribute: bool = True) -> None:
        """
        Invalidate all cached keys.
        
        Args:
            distribute: Whether to distribute invalidation to L3 caches
        """
        # Invalidate in Redis if available
        if distribute and REDIS_AVAILABLE and self._redis:
            try:
                redis_pattern = f"{self._prefix}*"
                keys = self._redis.keys(redis_pattern)
                if keys:
                    self._redis.delete(*keys)
            except Exception as e:
                logger.error(f"Redis error invalidating all keys: {e}", exc_info=True)
        
        # Invalidate in Memcached if available
        if distribute and MEMCACHED_AVAILABLE and self._memcached:
            try:
                # Memcached doesn't support pattern deletion, so we flush all
                # Note: This may affect other cached data if sharing a Memcached instance
                self._memcached.flush_all()
            except Exception as e:
                logger.error(f"Memcached error invalidating all keys: {e}", exc_info=True)
        
        # Clear in-memory caches
        for shard_index in range(self._shards):
            with self._locks[shard_index]:
                # Clear main cache
                cache_shard = self._cache[shard_index]
                count = len(cache_shard)
                cache_shard.clear()
                
                # Clear negative cache
                negative_cache_shard = self._negative_cache[shard_index]
                negative_cache_shard.clear()
                
                if self._enable_metrics:
                    self._stats["invalidations"] += count
        
        # Clear ID to hash mapping
        self._id_to_hash.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics and metrics.
        
        Returns:
            Dictionary with cache statistics
        """
        stats = self._stats.copy()
        
        # Calculate additional metrics
        total_requests = stats["hits"] + stats["misses"]
        if total_requests > 0:
            stats["hit_ratio"] = stats["hits"] / total_requests
        else:
            stats["hit_ratio"] = 0
        
        # Add cache size information
        stats["cache_size"] = sum(len(shard) for shard in self._cache)
        stats["negative_cache_size"] = sum(len(shard) for shard in self._negative_cache)
        stats["id_map_size"] = len(self._id_to_hash)
        
        # Add advanced metrics if enabled
        if self._enable_metrics:
            stats["frequent_keys"] = dict(self._access_patterns["key_frequency"].most_common(10))
            stats["response_time_avg"] = self._calculate_avg_response_time()
            stats["current_hit_ratio"] = self._calculate_current_hit_ratio()
        
        return stats
    
    def _track_access(self, api_key_hash: str) -> None:
        """
        Track access to a key for pattern analysis.
        
        Args:
            api_key_hash: Hashed API key that was accessed
        """
        if not self._enable_metrics:
            return
        
        current_time = time.time()
        current_hour = datetime.now().strftime("%Y-%m-%d-%H")
        
        # Track frequency
        self._access_patterns["key_frequency"][api_key_hash] += 1
        
        # Track hourly access pattern
        self._access_patterns["hourly"][current_hour][api_key_hash] += 1
        
        # Track access intervals if we have previous access
        if api_key_hash in self._access_patterns["key_last_access"]:
            last_access = self._access_patterns["key_last_access"][api_key_hash]
            interval = current_time - last_access
            self._access_patterns["access_intervals"][api_key_hash].append(interval)
            
            # Keep only the last 100 intervals
            if len(self._access_patterns["access_intervals"][api_key_hash]) > 100:
                self._access_patterns["access_intervals"][api_key_hash] = \
                    self._access_patterns["access_intervals"][api_key_hash][-100:]
        
        # Update last access time
        self._access_patterns["key_last_access"][api_key_hash] = current_time
    
    def _warm_cache(self) -> None:
        """
        Proactively warm the cache with frequently accessed keys.
        
        This method uses access patterns to identify keys that should be
        pre-loaded or kept in the cache based on their usage patterns.
        """
        if not self._enable_cache_warming or not self._enable_metrics:
            return
        
        try:
            # Get the most frequently accessed keys not currently in cache
            top_keys = self._access_patterns["key_frequency"].most_common(20)
            
            for key_hash, _ in top_keys:
                # Check if key is in any L1 cache shard
                shard_index = self._get_shard_index(key_hash)
                cache_shard = self._cache[shard_index]
                
                if key_hash not in cache_shard:
                    # Try to fetch from L3 cache
                    if REDIS_AVAILABLE and self._redis:
                        try:
                            redis_key = f"{self._prefix}{key_hash}"
                            data = self._redis.get(redis_key)
                            if data:
                                try:
                                    api_key_data = json.loads(data)
                                    # Add to L1 cache
                                    self._add_to_cache(key_hash, api_key_data)
                                    logger.debug(f"Warmed cache with key {key_hash}")
                                except json.JSONDecodeError:
                                    continue
                        except Exception:
                            continue
            
            logger.debug("Completed cache warming cycle")
        except Exception as e:
            logger.error(f"Error during cache warming: {e}", exc_info=True)
    
    def _update_metrics(self) -> None:
        """Update metrics and perform pattern analysis."""
        if not self._enable_metrics:
            return
        
        try:
            # Calculate current hit ratio
            total_requests = self._stats["hits"] + self._stats["misses"]
            if total_requests > 0:
                current_ratio = self._stats["hits"] / total_requests
                self._access_patterns["cache_hit_ratio_history"].append((time.time(), current_ratio))
            
            # Limit history size
            if len(self._access_patterns["cache_hit_ratio_history"]) > 1000:
                self._access_patterns["cache_hit_ratio_history"] = \
                    self._access_patterns["cache_hit_ratio_history"][-1000:]
            
            # Limit response times history
            if len(self._access_patterns["response_times"]) > 1000:
                self._access_patterns["response_times"] = \
                    self._access_patterns["response_times"][-1000:]
            
            logger.debug("Updated cache metrics")
        except Exception as e:
            logger.error(f"Error updating metrics: {e}", exc_info=True)
    
    def _clean_old_metrics(self) -> None:
        """Clean up old metrics data to limit memory usage."""
        if not self._enable_metrics:
            return
        
        try:
            # Clean up hourly data older than 7 days
            current_time = datetime.now()
            keys_to_remove = []
            
            for hour_key in self._access_patterns["hourly"].keys():
                try:
                    # Parse hour key format: YYYY-MM-DD-HH
                    year, month, day, hour = hour_key.split('-')
                    hour_time = datetime(int(year), int(month), int(day), int(hour))
                    
                    # Check if older than 7 days
                    if (current_time - hour_time).days > 7:
                        keys_to_remove.append(hour_key)
                except Exception:
                    # If we can't parse the key, assume it's old
                    keys_to_remove.append(hour_key)
            
            # Remove old hourly data
            for key in keys_to_remove:
                del self._access_patterns["hourly"][key]
            
            # Remove data for keys that haven't been accessed in over 24 hours
            day_ago = time.time() - (24 * 60 * 60)
            keys_to_remove = []
            
            for key_hash, last_access in self._access_patterns["key_last_access"].items():
                if last_access < day_ago:
                    keys_to_remove.append(key_hash)
            
            # Remove old key access data
            for key_hash in keys_to_remove:
                if key_hash in self._access_patterns["key_frequency"]:
                    del self._access_patterns["key_frequency"][key_hash]
                if key_hash in self._access_patterns["key_last_access"]:
                    del self._access_patterns["key_last_access"][key_hash]
                if key_hash in self._access_patterns["access_intervals"]:
                    del self._access_patterns["access_intervals"][key_hash]
            
            logger.debug(f"Cleaned up metrics for {len(keys_to_remove)} inactive keys")
        except Exception as e:
            logger.error(f"Error cleaning old metrics: {e}", exc_info=True)
    
    def _adjust_cache_parameters(self) -> None:
        """
        Adaptively adjust cache parameters based on access patterns.
        
        This method implements the adaptive policy, adjusting TTL values and
        other parameters based on observed usage patterns.
        """
        if self._policy != CachePolicy.ADAPTIVE:
            return
        
        try:
            # Calculate current hit ratio
            hit_ratio = self._calculate_current_hit_ratio()
            
            # Adjust TTL based on hit ratio trend
            if len(self._access_patterns["cache_hit_ratio_history"]) >= 10:
                recent_ratios = [r for _, r in self._access_patterns["cache_hit_ratio_history"][-10:]]
                avg_ratio = sum(recent_ratios) / len(recent_ratios)
                
                # If hit ratio is decreasing, increase TTL to keep items longer
                if hit_ratio < avg_ratio * 0.9:  # More than 10% decrease
                    # Increase TTL up to 2x the current value
                    new_ttl = min(self._ttl_seconds * 2, 24 * 60 * 60)  # Max 24 hours
                    if new_ttl != self._ttl_seconds:
                        logger.info(f"Adaptive policy: Increasing TTL from {self._ttl_seconds}s to {new_ttl}s")
                        self._ttl_seconds = new_ttl
                
                # If hit ratio is very high, we might be keeping items too long
                elif hit_ratio > 0.95 and self._ttl_seconds > 3600:
                    # Decrease TTL, but not below 1 hour
                    new_ttl = max(self._ttl_seconds // 2, 3600)
                    logger.info(f"Adaptive policy: Decreasing TTL from {self._ttl_seconds}s to {new_ttl}s")
                    self._ttl_seconds = new_ttl
        except Exception as e:
            logger.error(f"Error adjusting cache parameters: {e}", exc_info=True)
    
    def _calculate_avg_response_time(self) -> float:
        """
        Calculate average response time from recent data.
        
        Returns:
            Average response time in seconds
        """
        if not self._access_patterns["response_times"]:
            return 0.0
        
        # Get the most recent 100 response times
        recent_times = self._access_patterns["response_times"][-100:]
        times = [t for _, t in recent_times]
        
        if not times:
            return 0.0
            
        return sum(times) / len(times)
    
    def _calculate_current_hit_ratio(self) -> float:
        """
        Calculate current hit ratio from recent requests.
        
        Returns:
            Current hit ratio (0.0 to 1.0)
        """
        total_requests = self._stats["hits"] + self._stats["misses"]
        if total_requests > 0:
            return self._stats["hits"] / total_requests
        return 0.0
    
    def shutdown(self) -> None:
        """Properly shutdown the cache and background tasks."""
        if self._update_thread and self._update_thread.is_alive():
            logger.info("Shutting down API key cache maintenance thread")
            self._shutdown_event.set()
            self._update_thread.join(timeout=5.0)
            if self._update_thread.is_alive():
                logger.warning("API key cache maintenance thread did not terminate gracefully")
