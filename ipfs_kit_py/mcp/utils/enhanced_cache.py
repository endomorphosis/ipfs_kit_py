"""
Enhanced Caching System for MCP Server

This module provides an optimized caching system for the MCP server,
addressing the caching improvements mentioned in the MCP roadmap.

Features:
- Multi-level caching (memory, shared memory, distributed)
- Configurable TTL and eviction policies
- Memory usage optimization with size limits
- Thread-safe operations
- Performance metrics tracking
- Automatic pruning of expired entries
"""

import time
import logging
import threading
import hashlib
import json
from typing import Dict, Any, Optional, Tuple, List, Union, Callable
from datetime import datetime
from functools import lru_cache
from collections import OrderedDict

# Configure logger
logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.info("Redis not available. Distributed caching will be disabled.")


class CacheMetrics:
    """Track cache performance metrics."""
    
    def __init__(self):
        """Initialize metrics counters."""
        self.hits = 0
        self.misses = 0
        self.inserts = 0
        self.updates = 0
        self.evictions = 0
        self.expirations = 0
        self.errors = 0
        
        # Timing metrics (in milliseconds)
        self.total_get_time = 0
        self.total_set_time = 0
        self.get_calls = 0
        self.set_calls = 0
    
    def record_hit(self):
        """Record a cache hit."""
        self.hits += 1
    
    def record_miss(self):
        """Record a cache miss."""
        self.misses += 1
    
    def record_insert(self):
        """Record a new item insertion."""
        self.inserts += 1
    
    def record_update(self):
        """Record an item update."""
        self.updates += 1
    
    def record_eviction(self):
        """Record an item eviction."""
        self.evictions += 1
    
    def record_expiration(self):
        """Record an item expiration."""
        self.expirations += 1
    
    def record_error(self):
        """Record an error."""
        self.errors += 1
    
    def record_get_time(self, duration_ms: float):
        """Record time taken for a get operation."""
        self.total_get_time += duration_ms
        self.get_calls += 1
    
    def record_set_time(self, duration_ms: float):
        """Record time taken for a set operation."""
        self.total_set_time += duration_ms
        self.set_calls += 1
    
    @property
    def hit_ratio(self) -> float:
        """Calculate the cache hit ratio."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0
    
    @property
    def avg_get_time_ms(self) -> float:
        """Calculate the average get operation time in milliseconds."""
        return self.total_get_time / self.get_calls if self.get_calls > 0 else 0
    
    @property
    def avg_set_time_ms(self) -> float:
        """Calculate the average set operation time in milliseconds."""
        return self.total_set_time / self.set_calls if self.set_calls > 0 else 0
    
    def reset(self):
        """Reset all metrics."""
        self.__init__()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to a dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_ratio": self.hit_ratio,
            "inserts": self.inserts,
            "updates": self.updates,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "errors": self.errors,
            "avg_get_time_ms": self.avg_get_time_ms,
            "avg_set_time_ms": self.avg_set_time_ms,
            "get_calls": self.get_calls,
            "set_calls": self.set_calls
        }
    
    def __str__(self) -> str:
        """Return a string representation of the metrics."""
        return (
            f"CacheMetrics(hits={self.hits}, misses={self.misses}, "
            f"hit_ratio={self.hit_ratio:.2f}, inserts={self.inserts}, "
            f"updates={self.updates}, evictions={self.evictions}, "
            f"expirations={self.expirations}, errors={self.errors}, "
            f"avg_get_time_ms={self.avg_get_time_ms:.2f}, "
            f"avg_set_time_ms={self.avg_set_time_ms:.2f})"
        )


class LRUCache:
    """
    Memory-efficient LRU (Least Recently Used) cache implementation.
    
    This cache uses OrderedDict for efficient O(1) operations while
    maintaining a strict memory limit.
    """
    
    def __init__(self, max_size_bytes: int = 50 * 1024 * 1024, max_items: int = 10000):
        """
        Initialize the LRU cache.
        
        Args:
            max_size_bytes: Maximum memory size in bytes
            max_items: Maximum number of items
        """
        self._cache: OrderedDict = OrderedDict()
        self._key_sizes: Dict[str, int] = {}  # Track size of each entry
        self._current_size_bytes = 0
        self._max_size_bytes = max_size_bytes
        self._max_items = max_items
        self._lock = threading.RLock()
        self.metrics = CacheMetrics()
    
    def get(self, key: str) -> Tuple[bool, Any]:
        """
        Get an item from the cache.
        
        Args:
            key: The cache key
            
        Returns:
            Tuple of (found, value)
        """
        start_time = time.time()
        
        with self._lock:
            try:
                if key in self._cache:
                    # Move to end (most recently used)
                    value = self._cache.pop(key)
                    self._cache[key] = value
                    self.metrics.record_hit()
                    self.metrics.record_get_time((time.time() - start_time) * 1000)
                    return True, value
                else:
                    self.metrics.record_miss()
                    self.metrics.record_get_time((time.time() - start_time) * 1000)
                    return False, None
            except Exception as e:
                logger.error(f"Error getting from LRU cache: {e}")
                self.metrics.record_error()
                self.metrics.record_get_time((time.time() - start_time) * 1000)
                return False, None
    
    def set(self, key: str, value: Any) -> bool:
        """
        Set an item in the cache.
        
        Args:
            key: The cache key
            value: The value to store
            
        Returns:
            True if successful, False otherwise
        """
        start_time = time.time()
        
        with self._lock:
            try:
                # Estimate size of the value
                value_size = self._estimate_size(value)
                
                # If single value is larger than max size, don't cache it
                if value_size > self._max_size_bytes:
                    logger.warning(f"Value for key {key} exceeds max cache size ({value_size} bytes)")
                    self.metrics.record_error()
                    self.metrics.record_set_time((time.time() - start_time) * 1000)
                    return False
                
                # If key exists, update it
                if key in self._cache:
                    # Remove old size from total
                    old_size = self._key_sizes.get(key, 0)
                    self._current_size_bytes -= old_size
                    
                    # Update with new value
                    self._cache[key] = value
                    self._key_sizes[key] = value_size
                    self._current_size_bytes += value_size
                    
                    # Move to end (most recently used)
                    self._cache.move_to_end(key)
                    
                    self.metrics.record_update()
                else:
                    # Make room if needed
                    while (len(self._cache) >= self._max_items or 
                           self._current_size_bytes + value_size > self._max_size_bytes):
                        if not self._cache:
                            # Cache is empty but new item is still too large
                            logger.warning(f"Cannot add item to cache, max size exceeded")
                            self.metrics.record_error()
                            self.metrics.record_set_time((time.time() - start_time) * 1000)
                            return False
                        
                        # Remove least recently used item
                        oldest_key, _ = self._cache.popitem(last=False)
                        oldest_size = self._key_sizes.pop(oldest_key, 0)
                        self._current_size_bytes -= oldest_size
                        self.metrics.record_eviction()
                    
                    # Add new item
                    self._cache[key] = value
                    self._key_sizes[key] = value_size
                    self._current_size_bytes += value_size
                    self.metrics.record_insert()
                
                self.metrics.record_set_time((time.time() - start_time) * 1000)
                return True
            except Exception as e:
                logger.error(f"Error setting in LRU cache: {e}")
                self.metrics.record_error()
                self.metrics.record_set_time((time.time() - start_time) * 1000)
                return False
    
    def delete(self, key: str) -> bool:
        """
        Delete an item from the cache.
        
        Args:
            key: The cache key
            
        Returns:
            True if item was deleted, False if not found
        """
        with self._lock:
            if key in self._cache:
                # Remove item
                del self._cache[key]
                
                # Update size tracking
                size = self._key_sizes.pop(key, 0)
                self._current_size_bytes -= size
                
                return True
            return False
    
    def clear(self):
        """Clear the entire cache."""
        with self._lock:
            self._cache.clear()
            self._key_sizes.clear()
            self._current_size_bytes = 0
    
    def _estimate_size(self, value: Any) -> int:
        """
        Estimate the memory size of a value in bytes.
        
        Args:
            value: The value to estimate
            
        Returns:
            Estimated size in bytes
        """
        try:
            # For basic types, use direct size check
            if isinstance(value, (str, bytes, bytearray)):
                return len(value)
            elif isinstance(value, (int, float, bool, type(None))):
                return 8  # Rough estimate for primitive types
            
            # For complex types, serialize to get rough estimate
            # This isn't perfectly accurate but provides an upper bound
            serialized = json.dumps(value, default=str)
            return len(serialized.encode('utf-8'))
        except Exception as e:
            logger.warning(f"Error estimating value size: {e}")
            # Return a conservative default
            return 1024
    
    @property
    def info(self) -> Dict[str, Any]:
        """Get information about the cache state."""
        with self._lock:
            return {
                "items_count": len(self._cache),
                "max_items": self._max_items,
                "current_size_bytes": self._current_size_bytes,
                "max_size_bytes": self._max_size_bytes,
                "size_percentage": self._current_size_bytes / self._max_size_bytes * 100 if self._max_size_bytes > 0 else 0,
                "metrics": self.metrics.to_dict()
            }


class TTLCache:
    """
    Time-based cache with automatic expiration of items.
    
    This cache stores values with a time-to-live (TTL) and
    automatically expires entries when they reach their TTL.
    """
    
    def __init__(self, default_ttl_seconds: int = 300, max_size_bytes: int = 50 * 1024 * 1024, 
                 max_items: int = 10000, cleanup_interval: int = 60):
        """
        Initialize the TTL cache.
        
        Args:
            default_ttl_seconds: Default TTL for cached items
            max_size_bytes: Maximum memory size in bytes
            max_items: Maximum number of items
            cleanup_interval: Interval in seconds between cleanup runs
        """
        self._cache: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}  # key -> expiration timestamp
        self._key_sizes: Dict[str, int] = {}  # Track size of each entry
        
        self._default_ttl = default_ttl_seconds
        self._max_size_bytes = max_size_bytes
        self._max_items = max_items
        self._current_size_bytes = 0
        
        self._lock = threading.RLock()
        self.metrics = CacheMetrics()
        
        # Start cleanup thread
        self._cleanup_interval = cleanup_interval
        self._stop_cleanup = threading.Event()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="ttl-cache-cleanup"
        )
        self._cleanup_thread.start()
    
    def get(self, key: str) -> Tuple[bool, Any]:
        """
        Get an item from the cache.
        
        Args:
            key: The cache key
            
        Returns:
            Tuple of (found, value)
        """
        start_time = time.time()
        
        with self._lock:
            try:
                # Check if key exists and is not expired
                if key in self._cache and key in self._expiry:
                    expiry_time = self._expiry[key]
                    
                    if time.time() < expiry_time:
                        # Not expired
                        value = self._cache[key]
                        self.metrics.record_hit()
                        self.metrics.record_get_time((time.time() - start_time) * 1000)
                        return True, value
                    else:
                        # Expired, remove it
                        self._remove_item(key)
                        self.metrics.record_expiration()
                
                # Key not found or expired
                self.metrics.record_miss()
                self.metrics.record_get_time((time.time() - start_time) * 1000)
                return False, None
            except Exception as e:
                logger.error(f"Error getting from TTL cache: {e}")
                self.metrics.record_error()
                self.metrics.record_get_time((time.time() - start_time) * 1000)
                return False, None
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """
        Set an item in the cache with a TTL.
        
        Args:
            key: The cache key
            value: The value to store
            ttl_seconds: Time-to-live in seconds, uses default if None
            
        Returns:
            True if successful, False otherwise
        """
        start_time = time.time()
        
        with self._lock:
            try:
                # Use specified TTL or default
                ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
                expiry_time = time.time() + ttl
                
                # Estimate size of the value
                value_size = self._estimate_size(value)
                
                # If single value is larger than max size, don't cache it
                if value_size > self._max_size_bytes:
                    logger.warning(f"Value for key {key} exceeds max cache size ({value_size} bytes)")
                    self.metrics.record_error()
                    self.metrics.record_set_time((time.time() - start_time) * 1000)
                    return False
                
                # If key exists, update it
                if key in self._cache:
                    # Remove old size from total
                    old_size = self._key_sizes.get(key, 0)
                    self._current_size_bytes -= old_size
                    
                    # Update with new value
                    self._cache[key] = value
                    self._expiry[key] = expiry_time
                    self._key_sizes[key] = value_size
                    self._current_size_bytes += value_size
                    
                    self.metrics.record_update()
                else:
                    # Make room if needed
                    self._make_room(value_size)
                    
                    # Add new item
                    self._cache[key] = value
                    self._expiry[key] = expiry_time
                    self._key_sizes[key] = value_size
                    self._current_size_bytes += value_size
                    
                    self.metrics.record_insert()
                
                self.metrics.record_set_time((time.time() - start_time) * 1000)
                return True
            except Exception as e:
                logger.error(f"Error setting in TTL cache: {e}")
                self.metrics.record_error()
                self.metrics.record_set_time((time.time() - start_time) * 1000)
                return False
    
    def delete(self, key: str) -> bool:
        """
        Delete an item from the cache.
        
        Args:
            key: The cache key
            
        Returns:
            True if item was deleted, False if not found
        """
        with self._lock:
            if key in self._cache:
                self._remove_item(key)
                return True
            return False
    
    def clear(self):
        """Clear the entire cache."""
        with self._lock:
            self._cache.clear()
            self._expiry.clear()
            self._key_sizes.clear()
            self._current_size_bytes = 0
    
    def _remove_item(self, key: str):
        """
        Remove an item from the cache.
        
        Args:
            key: The cache key
        """
        if key in self._cache:
            del self._cache[key]
        
        if key in self._expiry:
            del self._expiry[key]
        
        # Update size tracking
        size = self._key_sizes.pop(key, 0)
        self._current_size_bytes -= size
    
    def _make_room(self, new_item_size: int):
        """
        Make room for a new item by removing old or expired items.
        
        Args:
            new_item_size: Size of the new item in bytes
        """
        # First, remove expired items
        current_time = time.time()
        expired_keys = [k for k, exp in self._expiry.items() if current_time > exp]
        
        for key in expired_keys:
            self._remove_item(key)
            self.metrics.record_expiration()
        
        # If still not enough room, remove items by earliest expiry
        while (len(self._cache) >= self._max_items or 
               self._current_size_bytes + new_item_size > self._max_size_bytes):
            if not self._expiry:
                # No items left to remove
                break
            
            # Find item with earliest expiry
            earliest_key = min(self._expiry.items(), key=lambda x: x[1])[0]
            self._remove_item(earliest_key)
            self.metrics.record_eviction()
    
    def _cleanup_loop(self):
        """Background thread to clean up expired items."""
        while not self._stop_cleanup.wait(self._cleanup_interval):
            try:
                self._cleanup_expired()
            except Exception as e:
                logger.error(f"Error in TTL cache cleanup: {e}")
    
    def _cleanup_expired(self):
        """Remove all expired items from the cache."""
        with self._lock:
            current_time = time.time()
            expired_keys = [k for k, exp in self._expiry.items() if current_time > exp]
            
            for key in expired_keys:
                self._remove_item(key)
                self.metrics.record_expiration()
            
            if expired_keys:
                logger.debug(f"TTL cache cleanup: removed {len(expired_keys)} expired items")
    
    def _estimate_size(self, value: Any) -> int:
        """
        Estimate the memory size of a value in bytes.
        
        Args:
            value: The value to estimate
            
        Returns:
            Estimated size in bytes
        """
        try:
            # For basic types, use direct size check
            if isinstance(value, (str, bytes, bytearray)):
                return len(value)
            elif isinstance(value, (int, float, bool, type(None))):
                return 8  # Rough estimate for primitive types
            
            # For complex types, serialize to get rough estimate
            serialized = json.dumps(value, default=str)
            return len(serialized.encode('utf-8'))
        except Exception as e:
            logger.warning(f"Error estimating value size: {e}")
            # Return a conservative default
            return 1024
    
    def shutdown(self):
        """Gracefully shut down the cache."""
        self._stop_cleanup.set()
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5.0)
    
    @property
    def info(self) -> Dict[str, Any]:
        """Get information about the cache state."""
        with self._lock:
            current_time = time.time()
            return {
                "items_count": len(self._cache),
                "max_items": self._max_items,
                "current_size_bytes": self._current_size_bytes,
                "max_size_bytes": self._max_size_bytes,
                "size_percentage": self._current_size_bytes / self._max_size_bytes * 100 if self._max_size_bytes > 0 else 0,
                "expired_items": sum(1 for exp in self._expiry.values() if current_time > exp),
                "metrics": self.metrics.to_dict()
            }


class MultiLevelCache:
    """
    Multi-level caching system with tiered storage.
    
    This class implements a multi-level cache with memory, shared memory,
    and distributed caching options for optimal performance.
    """
    
    def __init__(
        self,
        name: str = "mcp-cache",
        memory_cache_size_mb: int = 50,
        memory_cache_items: int = 10000,
        default_ttl_seconds: int = 300,
        redis_client = None,
        redis_prefix: str = "mcp:",
        enable_memory_cache: bool = True,
        enable_redis_cache: bool = True
    ):
        """
        Initialize the multi-level cache.
        
        Args:
            name: Cache name used for identification
            memory_cache_size_mb: Size of memory cache in MB
            memory_cache_items: Maximum items in memory cache
            default_ttl_seconds: Default TTL for cached items
            redis_client: Redis client for distributed caching
            redis_prefix: Prefix for Redis keys
            enable_memory_cache: Whether to use memory caching
            enable_redis_cache: Whether to use Redis caching
        """
        self.name = name
        self.default_ttl = default_ttl_seconds
        
        # Initialize memory cache
        self._memory_cache = None
        if enable_memory_cache:
            self._memory_cache = TTLCache(
                default_ttl_seconds=default_ttl_seconds,
                max_size_bytes=memory_cache_size_mb * 1024 * 1024,
                max_items=memory_cache_items
            )
        
        # Initialize Redis cache
        self._redis = None
        self._redis_prefix = redis_prefix
        if enable_redis_cache and redis_client and REDIS_AVAILABLE:
            self._redis = redis_client
        
        # If Redis is enabled but no client provided, try to create one
        elif enable_redis_cache and REDIS_AVAILABLE and not redis_client:
            try:
                import redis
                self._redis = redis.Redis(host='localhost', port=6379, db=0)
                logger.info(f"Connected to Redis for {name} cache")
            except Exception as e:
                logger.warning(f"Could not connect to Redis: {e}")
        
        # Track overall metrics
        self.metrics = CacheMetrics()
        
        logger.info(
            f"Initialized multi-level cache '{name}' with "
            f"memory cache: {'enabled' if self._memory_cache else 'disabled'}, "
            f"Redis cache: {'enabled' if self._redis else 'disabled'}"
        )
    
    def get(self, key: str) -> Tuple[bool, Any]:
        """
        Get a value from the cache.
        
        Args:
            key: The cache key
            
        Returns:
            Tuple of (found, value)
        """
        start_time = time.time()
        
        try:
            # Try memory cache first
            if self._memory_cache:
                found, value = self._memory_cache.get(key)
                if found:
                    self.metrics.record_hit()
                    self.metrics.record_get_time((time.time() - start_time) * 1000)
                    return True, value
            
            # Try Redis cache
            if self._redis:
                redis_key = f"{self._redis_prefix}{key}"
                redis_value = self._redis.get(redis_key)
                
                if redis_value:
                    try:
                        # Parse the value
                        value = json.loads(redis_value)
                        
                        # Store in memory cache for faster access next time
                        if self._memory_cache:
                            self._memory_cache.set(key, value)
                        
                        self.metrics.record_hit()
                        self.metrics.record_get_time((time.time() - start_time) * 1000)
                        return True, value
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in Redis for key {key}")
            
            # Not found in any cache
            self.metrics.record_miss()
            self.metrics.record_get_time((time.time() - start_time) * 1000)
            return False, None
        except Exception as e:
            logger.error(f"Error in cache get: {e}")
            self.metrics.record_error()
            self.metrics.record_get_time((time.time() - start_time) * 1000)
            return False, None
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """
        Set a value in the cache.
        
        Args:
            key: The cache key
            value: The value to store
            ttl_seconds: Time-to-live in seconds, uses default if None
            
        Returns:
            True if successful, False otherwise
        """
        start_time = time.time()
        success = False
        
        try:
            # Use specified TTL or default
            ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
            
            # Set in memory cache
            if self._memory_cache:
                memory_success = self._memory_cache.set(key, value, ttl)
                success = success or memory_success
            
            # Set in Redis cache
            if self._redis:
                try:
                    redis_key = f"{self._redis_prefix}{key}"
                    redis_value = json.dumps(value, default=str)
                    redis_success = self._redis.set(redis_key, redis_value, ex=ttl)
                    success = success or bool(redis_success)
                except Exception as e:
                    logger.warning(f"Error setting value in Redis: {e}")
            
            if success:
                self.metrics.record_set_time((time.time() - start_time) * 1000)
                self.metrics.record_insert()
            
            return success
        except Exception as e:
            logger.error(f"Error in cache set: {e}")
            self.metrics.record_error()
            self.metrics.record_set_time((time.time() - start_time) * 1000)
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete a value from the cache.
        
        Args:
            key: The cache key
            
        Returns:
            True if successful, False otherwise
        """
        success = False
        
        try:
            # Delete from memory cache
            if self._memory_cache:
                memory_success = self._memory_cache.delete(key)
                success = success or memory_success
            
            # Delete from Redis cache
            if self._redis:
                redis_key = f"{self._redis_prefix}{key}"
                redis_success = self._redis.delete(redis_key)
                success = success or bool(redis_success)
            
            return success
        except Exception as e:
            logger.error(f"Error in cache delete: {e}")
            return False
    
    def clear(self):
        """Clear all cache levels."""
        try:
            # Clear memory cache
            if self._memory_cache:
                self._memory_cache.clear()
            
            # Clear Redis cache (for this prefix only)
            if self._redis:
                pattern = f"{self._redis_prefix}*"
                cursor = 0
                while True:
                    cursor, keys = self._redis.scan(cursor, pattern, 100)
                    if keys:
                        self._redis.delete(*keys)
                    if cursor == 0:
                        break
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
    
    def shutdown(self):
        """Gracefully shut down the cache."""
        if self._memory_cache:
            self._memory_cache.shutdown()
    
    @property
    def info(self) -> Dict[str, Any]:
        """Get information about the cache state."""
        result = {
            "name": self.name,
            "default_ttl": self.default_ttl,
            "memory_cache": self._memory_cache.info if self._memory_cache else None,
            "redis_cache": {"enabled": self._redis is not None},
            "overall_metrics": self.metrics.to_dict()
        }
        
        # Add Redis info if available
        if self._redis:
            try:
                # Count keys with our prefix
                pattern = f"{self._redis_prefix}*"
                keys_count = 0
                cursor = 0
                while True:
                    cursor, keys = self._redis.scan(cursor, pattern, 100)
                    keys_count += len(keys)
                    if cursor == 0:
                        break
                
                result["redis_cache"]["keys_count"] = keys_count
            except Exception as e:
                logger.warning(f"Error getting Redis info: {e}")
        
        return result


# Helper function for creating function-level cache
def cached(ttl_seconds: int = 300, max_size: int = 128):
    """
    Create a cached version of a function.
    
    Args:
        ttl_seconds: Time-to-live for cached results
        max_size: Maximum number of cached results
        
    Returns:
        Decorated function
    """
    def decorator(func):
        # Create a cache instance for this function
        cache = TTLCache(default_ttl_seconds=ttl_seconds, max_items=max_size, 
                         max_size_bytes=10 * 1024 * 1024)  # 10 MB limit
        
        def wrapper(*args, **kwargs):
            # Create a cache key from function name and arguments
            key_parts = [func.__name__]
            
            # Add positional arguments
            for arg in args:
                key_parts.append(str(arg))
            
            # Add keyword arguments (sorted for consistency)
            for k in sorted(kwargs.keys()):
                key_parts.append(f"{k}={kwargs[k]}")
            
            # Create a hash from all parts
            key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            
            # Try to get from cache
            found, value = cache.get(key)
            if found:
                return value
            
            # Call the function
            result = func(*args, **kwargs)
            
            # Store result in cache
            cache.set(key, result)
            
            return result
        
        # Attach cache to the wrapper for inspection/clearing
        wrapper.cache = cache
        wrapper.clear_cache = cache.clear
        
        return wrapper
    
    return decorator


# Create a global cache instance for shared use
global_cache = MultiLevelCache(
    name="mcp-global",
    memory_cache_size_mb=100,  # 100 MB
    memory_cache_items=20000,
    default_ttl_seconds=600
)
