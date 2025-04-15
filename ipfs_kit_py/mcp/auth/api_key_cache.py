"""
API Key Cache Module for MCP Server Authentication

This module implements an efficient caching mechanism for API keys
to reduce database load and improve response times for API-based authentication.

Features:
- In-memory LRU cache for fast validation
- Optional distributed cache using Redis
- Automatic expiration and TTL management
- Thread-safe implementation
- Cache invalidation hooks
"""

import time
import logging
import threading
from typing import Dict, Optional, Any, Tuple, Set, List, Union, Callable
import hashlib
import json
from functools import lru_cache
import weakref

# Set up logging
logger = logging.getLogger(__name__)

class ApiKeyCache:
    """
    Memory-efficient cache for API key validation.
    
    This class implements a two-level cache system:
    1. Fast in-memory LRU cache for active keys
    2. Optional Redis-backed distributed cache for shared environments
    
    It optimizes the API key validation process by reducing storage lookups.
    """
    
    def __init__(
        self, 
        max_size: int = 1000, 
        ttl_seconds: int = 300,
        redis_client = None,
        cache_prefix: str = "apikey:",
        negative_cache_ttl: int = 30
    ):
        """
        Initialize the API key cache.
        
        Args:
            max_size: Maximum number of keys to cache in memory
            ttl_seconds: Time-to-live for cached keys in seconds
            redis_client: Optional Redis client for distributed caching
            cache_prefix: Prefix for Redis cache keys
            negative_cache_ttl: TTL for negative cache entries (failed lookups)
        """
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._negative_ttl = negative_cache_ttl
        self._redis = redis_client
        self._prefix = cache_prefix
        
        # Two-level cache system
        # 1. Token hash to API key data cache (main positive cache)
        self._cache: Dict[str, Dict[str, Any]] = {}
        
        # 2. Negative cache for keys that don't exist (to prevent repeated lookups)
        self._negative_cache: Dict[str, float] = {}
        
        # Additional indexes for fast access patterns
        # Key ID to token hash mapping
        self._id_to_hash: Dict[str, str] = {}
        
        # User ID to set of key IDs mapping (for invalidation)
        self._user_keys: Dict[str, Set[str]] = {}
        
        # Lock for thread-safety
        self._lock = threading.RLock()
        
        # Statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "inserts": 0,
            "invalidations": 0,
            "negative_hits": 0,
            "redis_hits": 0
        }
        
        logger.info(f"API Key Cache initialized with max_size={max_size}, ttl={ttl_seconds}s")
    
    def get(self, api_key_hash: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Get API key data from cache.
        
        Args:
            api_key_hash: Hashed API key token
            
        Returns:
            Tuple of (found, data)
        """
        with self._lock:
            # Check negative cache first
            current_time = time.time()
            if api_key_hash in self._negative_cache:
                neg_time = self._negative_cache[api_key_hash]
                if current_time - neg_time < self._negative_ttl:
                    # Still in negative cache TTL
                    self._stats["negative_hits"] += 1
                    return False, None
                else:
                    # Expired negative cache entry
                    del self._negative_cache[api_key_hash]
            
            # Check in-memory cache
            if api_key_hash in self._cache:
                entry = self._cache[api_key_hash]
                
                # Check if entry is expired
                if current_time > entry.get("_cache_expires_at", float('inf')):
                    # Expired, remove from cache
                    self._remove_from_cache(api_key_hash)
                    self._stats["misses"] += 1
                    return False, None
                
                # Update access time
                entry["_cache_last_accessed"] = current_time
                self._stats["hits"] += 1
                
                # Return a copy to prevent cache pollution
                result = entry.copy()
                # Remove cache metadata
                for key in list(result.keys()):
                    if key.startswith("_cache_"):
                        del result[key]
                        
                return True, result
            
            # If not in memory cache, try Redis if available
            if self._redis:
                try:
                    redis_key = f"{self._prefix}{api_key_hash}"
                    data = self._redis.get(redis_key)
                    if data:
                        try:
                            api_key_data = json.loads(data)
                            # Store in local cache for faster subsequent access
                            self._add_to_cache(api_key_hash, api_key_data)
                            self._stats["redis_hits"] += 1
                            return True, api_key_data
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in Redis for API key {api_key_hash}")
                except Exception as e:
                    logger.error(f"Redis error in API key cache: {e}")
            
            # Not found in any cache
            self._stats["misses"] += 1
            return False, None
    
    def set(self, api_key_hash: str, api_key_data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """
        Add API key data to cache.
        
        Args:
            api_key_hash: Hashed API key token
            api_key_data: API key data to cache
            ttl: Optional custom TTL in seconds
        """
        if not api_key_data:
            logger.warning("Attempted to cache empty API key data")
            return
            
        with self._lock:
            # Remove from negative cache if present
            if api_key_hash in self._negative_cache:
                del self._negative_cache[api_key_hash]
                
            # Add to in-memory cache
            self._add_to_cache(api_key_hash, api_key_data, ttl)
            
            # Add to Redis if available
            if self._redis:
                try:
                    redis_key = f"{self._prefix}{api_key_hash}"
                    redis_ttl = ttl or self._ttl_seconds
                    self._redis.setex(
                        redis_key,
                        redis_ttl,
                        json.dumps(api_key_data)
                    )
                except Exception as e:
                    logger.error(f"Redis error setting API key cache: {e}")
            
            self._stats["inserts"] += 1
    
    def _add_to_cache(self, api_key_hash: str, api_key_data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """
        Add API key data to in-memory cache with proper metadata.
        
        Args:
            api_key_hash: Hashed API key token
            api_key_data: API key data to cache
            ttl: Optional custom TTL in seconds
        """
        current_time = time.time()
        
        # Make a copy to avoid modifying the original
        entry = api_key_data.copy()
        
        # Add cache metadata
        entry["_cache_added_at"] = current_time
        entry["_cache_last_accessed"] = current_time
        entry["_cache_expires_at"] = current_time + (ttl or self._ttl_seconds)
        
        # Add to main cache
        self._cache[api_key_hash] = entry
        
        # Update indexes for faster access
        key_id = entry.get("id")
        user_id = entry.get("user_id")
        
        if key_id:
            self._id_to_hash[key_id] = api_key_hash
            
        if user_id:
            if user_id not in self._user_keys:
                self._user_keys[user_id] = set()
            self._user_keys[user_id].add(key_id)
        
        # If cache is full, remove least recently used item
        if len(self._cache) > self._max_size:
            self._evict_lru()
    
    def _evict_lru(self) -> None:
        """Remove the least recently used item from cache."""
        if not self._cache:
            return
            
        # Find key with oldest last_accessed time
        oldest_key = None
        oldest_time = float('inf')
        
        for key, entry in self._cache.items():
            last_accessed = entry.get("_cache_last_accessed", 0)
            if last_accessed < oldest_time:
                oldest_time = last_accessed
                oldest_key = key
        
        if oldest_key:
            self._remove_from_cache(oldest_key)
    
    def _remove_from_cache(self, api_key_hash: str) -> None:
        """
        Remove an item from cache and all indexes.
        
        Args:
            api_key_hash: Hashed API key token
        """
        if api_key_hash not in self._cache:
            return
            
        entry = self._cache[api_key_hash]
        key_id = entry.get("id")
        user_id = entry.get("user_id")
        
        # Update indexes
        if key_id and key_id in self._id_to_hash:
            del self._id_to_hash[key_id]
            
        if user_id and user_id in self._user_keys and key_id in self._user_keys[user_id]:
            self._user_keys[user_id].remove(key_id)
            if not self._user_keys[user_id]:
                del self._user_keys[user_id]
        
        # Remove from main cache
        del self._cache[api_key_hash]
    
    def set_negative(self, api_key_hash: str) -> None:
        """
        Add an entry to the negative cache.
        
        Args:
            api_key_hash: Hashed API key token
        """
        with self._lock:
            self._negative_cache[api_key_hash] = time.time()
            
            # Keep negative cache from growing too large
            if len(self._negative_cache) > self._max_size:
                # Remove oldest entries
                current_time = time.time()
                expired_keys = [
                    k for k, v in self._negative_cache.items() 
                    if current_time - v > self._negative_ttl
                ]
                
                # Remove expired entries
                for k in expired_keys:
                    del self._negative_cache[k]
                
                # If still too many, remove oldest
                if len(self._negative_cache) > self._max_size:
                    oldest_keys = sorted(
                        self._negative_cache.items(), 
                        key=lambda x: x[1]
                    )[:len(self._negative_cache) - self._max_size]
                    
                    for k, _ in oldest_keys:
                        del self._negative_cache[k]
    
    def invalidate(self, api_key_hash: str) -> None:
        """
        Invalidate a specific API key in cache.
        
        Args:
            api_key_hash: Hashed API key token
        """
        with self._lock:
            # Remove from in-memory cache
            self._remove_from_cache(api_key_hash)
            
            # Remove from Redis if available
            if self._redis:
                try:
                    redis_key = f"{self._prefix}{api_key_hash}"
                    self._redis.delete(redis_key)
                except Exception as e:
                    logger.error(f"Redis error invalidating API key cache: {e}")
            
            self._stats["invalidations"] += 1
    
    def invalidate_by_id(self, key_id: str) -> None:
        """
        Invalidate an API key by its ID.
        
        Args:
            key_id: API key ID
        """
        with self._lock:
            if key_id in self._id_to_hash:
                api_key_hash = self._id_to_hash[key_id]
                self.invalidate(api_key_hash)
    
    def invalidate_user_keys(self, user_id: str) -> int:
        """
        Invalidate all API keys for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of keys invalidated
        """
        with self._lock:
            count = 0
            if user_id in self._user_keys:
                for key_id in list(self._user_keys[user_id]):
                    if key_id in self._id_to_hash:
                        api_key_hash = self._id_to_hash[key_id]
                        self.invalidate(api_key_hash)
                        count += 1
            return count
    
    def clear(self) -> None:
        """Clear all caches."""
        with self._lock:
            self._cache.clear()
            self._negative_cache.clear()
            self._id_to_hash.clear()
            self._user_keys.clear()
            
            # Clear Redis cache if available
            if self._redis:
                try:
                    pattern = f"{self._prefix}*"
                    keys = self._redis.keys(pattern)
                    if keys:
                        self._redis.delete(*keys)
                except Exception as e:
                    logger.error(f"Redis error clearing API key cache: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_ratio = self._stats["hits"] / total_requests if total_requests > 0 else 0
            
            stats = {
                "size": len(self._cache),
                "negative_size": len(self._negative_cache),
                "max_size": self._max_size,
                "ttl_seconds": self._ttl_seconds,
                "hit_ratio": hit_ratio,
                "total_users_tracked": len(self._user_keys),
                "total_key_ids_tracked": len(self._id_to_hash),
                **self._stats
            }
            
            return stats
    
    def hash_token(self, token: str) -> str:
        """
        Create a consistent hash of an API token for cache keys.
        
        Args:
            token: Raw API token
            
        Returns:
            Hashed token suitable for cache keys
        """
        return hashlib.sha256(token.encode()).hexdigest()


class ApiKeyValidator:
    """
    High-performance API key validator with caching.
    
    This class provides cached validation of API keys to improve
    performance for frequent API key checks. It works with the 
    AuthenticationService to validate keys efficiently.
    """
    
    def __init__(
        self,
        auth_service,
        cache_size: int = 1000,
        cache_ttl: int = 300,
        redis_client = None
    ):
        """
        Initialize API key validator.
        
        Args:
            auth_service: Authentication service instance
            cache_size: Maximum size of the validation cache
            cache_ttl: Time-to-live for cache entries in seconds
            redis_client: Optional Redis client for distributed caching
        """
        self.auth_service = auth_service
        self.cache = ApiKeyCache(
            max_size=cache_size,
            ttl_seconds=cache_ttl,
            redis_client=redis_client
        )
        
        # Register hooks with auth service (if available)
        if hasattr(auth_service, 'register_key_invalidation_hook'):
            auth_service.register_key_invalidation_hook(self._invalidation_hook)
    
    async def validate_key(
        self, 
        api_key: str, 
        ip_address: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Validate an API key using the cache when possible.
        
        Args:
            api_key: API key to validate
            ip_address: Optional client IP address for IP restrictions
            
        Returns:
            Tuple of (valid, key_data, error_message)
        """
        # Create a unique hash for this key
        key_hash = self.cache.hash_token(api_key)
        
        # Check cache first
        found, key_data = self.cache.get(key_hash)
        if found:
            # Key found in cache, now perform lightweight validation
            
            # Check if key is active
            if not key_data.get("active", True):
                return False, None, "API key is inactive"
            
            # Check if key has expired
            expires_at = key_data.get("expires_at")
            if expires_at and expires_at < time.time():
                # Expired key, invalidate cache and report
                self.cache.invalidate(key_hash)
                return False, None, "API key has expired"
            
            # Check IP restrictions
            if key_data.get("allowed_ips") and ip_address:
                # This needs to be checked every time since the IP can change
                if not self._check_ip_allowed(ip_address, key_data.get("allowed_ips", [])):
                    return False, None, "IP address not allowed for this API key"
            
            # Key is valid - update last used time in actual storage
            # without blocking the current request
            if hasattr(self.auth_service, 'update_api_key_last_used'):
                # Don't await - fire and forget to update last_used
                import asyncio
                asyncio.create_task(
                    self.auth_service.update_api_key_last_used(key_data.get("id"))
                )
            
            return True, key_data, ""
        
        # Not in cache, do full validation
        valid, key_obj, error = await self.auth_service.verify_api_key(api_key, ip_address)
        
        if valid and key_obj:
            # Add to cache for future requests
            key_dict = key_obj.dict() if hasattr(key_obj, 'dict') else dict(key_obj)
            self.cache.set(key_hash, key_dict)
            return True, key_dict, ""
        else:
            # Add to negative cache to prevent repeated lookups of invalid keys
            self.cache.set_negative(key_hash)
            return False, None, error
    
    def _check_ip_allowed(self, ip_address: str, allowed_ips: List[str]) -> bool:
        """
        Check if an IP address is allowed.
        
        Args:
            ip_address: Client IP address
            allowed_ips: List of allowed IP addresses or CIDR ranges
            
        Returns:
            True if IP is allowed
        """
        # Implement IP validation without requiring ipaddress module
        # This is moved from the auth service to make validation faster
        
        # Simple exact match first (most common case)
        if ip_address in allowed_ips:
            return True
        
        # Then try CIDR matches if needed
        try:
            import ipaddress
            client_ip = ipaddress.ip_address(ip_address)
            
            for allowed_ip in allowed_ips:
                if "/" in allowed_ip:
                    # CIDR notation
                    network = ipaddress.ip_network(allowed_ip, strict=False)
                    if client_ip in network:
                        return True
        except ImportError:
            # If ipaddress module not available, only do exact matching
            pass
        except Exception:
            # Any other error, default to not allowed
            pass
            
        return False
    
    def invalidate_key(self, api_key: str) -> None:
        """
        Invalidate a specific API key in cache.
        
        Args:
            api_key: API key to invalidate
        """
        key_hash = self.cache.hash_token(api_key)
        self.cache.invalidate(key_hash)
    
    def invalidate_key_by_id(self, key_id: str) -> None:
        """
        Invalidate an API key by its ID.
        
        Args:
            key_id: API key ID
        """
        self.cache.invalidate_by_id(key_id)
    
    def invalidate_user_keys(self, user_id: str) -> int:
        """
        Invalidate all API keys for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of keys invalidated
        """
        return self.cache.invalidate_user_keys(user_id)
    
    def clear_cache(self) -> None:
        """Clear the entire validation cache."""
        self.cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        return self.cache.get_stats()
    
    def _invalidation_hook(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Handle cache invalidation events from the auth service.
        
        Args:
            event_type: Type of event (e.g., 'key_revoked', 'user_disabled')
            data: Event data
        """
        if event_type == 'key_revoked' and 'key_id' in data:
            self.invalidate_key_by_id(data['key_id'])
        elif event_type == 'user_keys_revoked' and 'user_id' in data:
            self.invalidate_user_keys(data['user_id'])
        elif event_type == 'user_disabled' and 'user_id' in data:
            self.invalidate_user_keys(data['user_id'])


# Optional Redis connection helper
def create_redis_client(config: Dict[str, Any]) -> Any:
    """
    Create a Redis client if configured.
    
    Args:
        config: Redis configuration
        
    Returns:
        Redis client or None
    """
    redis_url = config.get("url")
    if not redis_url:
        return None
        
    try:
        import redis
        
        # Create client based on configuration
        client = redis.from_url(
            redis_url,
            socket_timeout=config.get("timeout", 1.0),
            socket_connect_timeout=config.get("connect_timeout", 1.0),
            socket_keepalive=config.get("keepalive", True),
            health_check_interval=config.get("health_check_interval", 30),
            retry_on_timeout=config.get("retry", True)
        )
        
        # Test connection
        client.ping()
        return client
    except ImportError:
        logger.warning("Redis package not installed, distributed caching disabled")
        return None
    except Exception as e:
        logger.error(f"Error connecting to Redis: {e}")
        return None