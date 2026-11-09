"""
Cache Manager Module for IPFS Kit

This module provides a multi-tier caching system with:
- Memory-based caching (L1)
- Disk-based caching (L2)
- LRU (Least Recently Used) eviction
- LFU (Least Frequently Used) eviction
- TTL (Time To Live) management
- Cache invalidation strategies
- Hit/miss rate tracking

Part of Phase 9: Performance Optimization
"""

import logging
import time
import pickle
import hashlib
from datetime import datetime, timedelta
from collections import OrderedDict, defaultdict
from typing import Any, Optional, Dict, List, Callable
from pathlib import Path
from threading import RLock

logger = logging.getLogger(__name__)


class CacheEntry:
    """Represents a cached value with metadata"""
    
    def __init__(self, key: str, value: Any, ttl: Optional[float] = None):
        """
        Initialize cache entry
        
        Args:
            key: Cache key
            value: Cached value
            ttl: Time to live in seconds (None = no expiration)
        """
        self.key = key
        self.value = value
        self.created_at = time.time()
        self.accessed_at = self.created_at
        self.access_count = 0
        self.ttl = ttl
        self.expires_at = self.created_at + ttl if ttl else None
    
    def is_expired(self) -> bool:
        """Check if entry has expired"""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def touch(self):
        """Update access metadata"""
        self.accessed_at = time.time()
        self.access_count += 1
    
    def size_bytes(self) -> int:
        """Estimate size in bytes"""
        try:
            return len(pickle.dumps(self.value))
        except:
            return 0


class LRUCache:
    """Least Recently Used cache implementation"""
    
    def __init__(self, max_size: int = 1000):
        """
        Initialize LRU cache
        
        Args:
            max_size: Maximum number of entries
        """
        self.max_size = max_size
        self.cache = OrderedDict()
        self.lock = RLock()
    
    def get(self, key: str) -> Optional[CacheEntry]:
        """Get entry and move to end (most recent)"""
        with self.lock:
            if key not in self.cache:
                return None
            
            entry = self.cache.pop(key)
            if entry.is_expired():
                return None
            
            entry.touch()
            self.cache[key] = entry
            return entry
    
    def set(self, key: str, entry: CacheEntry):
        """Set entry, evict oldest if at capacity"""
        with self.lock:
            if key in self.cache:
                self.cache.pop(key)
            
            self.cache[key] = entry
            
            if len(self.cache) > self.max_size:
                # Remove oldest (first) entry
                self.cache.popitem(last=False)
    
    def delete(self, key: str) -> bool:
        """Delete entry"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    def clear(self):
        """Clear all entries"""
        with self.lock:
            self.cache.clear()
    
    def get_all_keys(self) -> List[str]:
        """Get all keys"""
        with self.lock:
            return list(self.cache.keys())
    
    def size(self) -> int:
        """Get number of entries"""
        return len(self.cache)


class LFUCache:
    """Least Frequently Used cache implementation"""
    
    def __init__(self, max_size: int = 1000):
        """
        Initialize LFU cache
        
        Args:
            max_size: Maximum number of entries
        """
        self.max_size = max_size
        self.cache: Dict[str, CacheEntry] = {}
        self.lock = RLock()
    
    def get(self, key: str) -> Optional[CacheEntry]:
        """Get entry and update access count"""
        with self.lock:
            if key not in self.cache:
                return None
            
            entry = self.cache[key]
            if entry.is_expired():
                del self.cache[key]
                return None
            
            entry.touch()
            return entry
    
    def set(self, key: str, entry: CacheEntry):
        """Set entry, evict least frequently used if at capacity"""
        with self.lock:
            self.cache[key] = entry
            
            if len(self.cache) > self.max_size:
                # Find entry with lowest access count
                least_used = min(
                    self.cache.items(),
                    key=lambda x: x[1].access_count
                )
                del self.cache[least_used[0]]
    
    def delete(self, key: str) -> bool:
        """Delete entry"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    def clear(self):
        """Clear all entries"""
        with self.lock:
            self.cache.clear()
    
    def get_all_keys(self) -> List[str]:
        """Get all keys"""
        with self.lock:
            return list(self.cache.keys())
    
    def size(self) -> int:
        """Get number of entries"""
        return len(self.cache)


class DiskCache:
    """Disk-based cache for larger/persistent storage"""
    
    def __init__(self, cache_dir: Path, max_size_mb: int = 100):
        """
        Initialize disk cache
        
        Args:
            cache_dir: Directory for cache files
            max_size_mb: Maximum cache size in MB
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.lock = RLock()
    
    def _get_path(self, key: str) -> Path:
        """Get file path for key"""
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"
    
    def get(self, key: str) -> Optional[CacheEntry]:
        """Get entry from disk"""
        with self.lock:
            path = self._get_path(key)
            if not path.exists():
                return None
            
            try:
                with open(path, 'rb') as f:
                    entry = pickle.load(f)
                
                if entry.is_expired():
                    path.unlink()
                    return None
                
                entry.touch()
                return entry
            except Exception as e:
                logger.error(f"Error loading from disk cache: {e}")
                return None
    
    def set(self, key: str, entry: CacheEntry):
        """Set entry on disk"""
        with self.lock:
            # Check total cache size
            self._enforce_size_limit()
            
            path = self._get_path(key)
            try:
                with open(path, 'wb') as f:
                    pickle.dump(entry, f)
            except Exception as e:
                logger.error(f"Error writing to disk cache: {e}")
    
    def delete(self, key: str) -> bool:
        """Delete entry from disk"""
        with self.lock:
            path = self._get_path(key)
            if path.exists():
                path.unlink()
                return True
            return False
    
    def clear(self):
        """Clear all entries"""
        with self.lock:
            for path in self.cache_dir.glob("*.cache"):
                path.unlink()
    
    def get_all_keys(self) -> List[str]:
        """Get all keys (slow operation)"""
        keys = []
        for path in self.cache_dir.glob("*.cache"):
            try:
                with open(path, 'rb') as f:
                    entry = pickle.load(f)
                    keys.append(entry.key)
            except:
                pass
        return keys
    
    def size(self) -> int:
        """Get number of entries"""
        return len(list(self.cache_dir.glob("*.cache")))
    
    def _enforce_size_limit(self):
        """Enforce maximum cache size"""
        total_size = sum(
            f.stat().st_size
            for f in self.cache_dir.glob("*.cache")
        )
        
        if total_size > self.max_size_bytes:
            # Delete oldest files
            files = sorted(
                self.cache_dir.glob("*.cache"),
                key=lambda f: f.stat().st_mtime
            )
            
            for f in files:
                if total_size <= self.max_size_bytes:
                    break
                size = f.stat().st_size
                f.unlink()
                total_size -= size


class CacheManager:
    """
    Multi-tier cache manager
    
    Provides a unified interface for multi-tier caching with:
    - L1: Memory cache (LRU or LFU)
    - L2: Disk cache (persistent)
    - Automatic tier promotion/demotion
    - Cache statistics tracking
    """
    
    def __init__(
        self,
        memory_policy: str = 'lru',
        memory_size: int = 1000,
        disk_size_mb: int = 100,
        cache_dir: Optional[Path] = None,
        enable_disk: bool = True
    ):
        """
        Initialize cache manager
        
        Args:
            memory_policy: 'lru' or 'lfu'
            memory_size: Maximum memory cache entries
            disk_size_mb: Maximum disk cache size in MB
            cache_dir: Directory for disk cache
            enable_disk: Enable disk caching
        """
        # Memory cache (L1)
        if memory_policy == 'lru':
            self.memory_cache = LRUCache(max_size=memory_size)
        elif memory_policy == 'lfu':
            self.memory_cache = LFUCache(max_size=memory_size)
        else:
            raise ValueError(f"Unknown policy: {memory_policy}")
        
        # Disk cache (L2)
        self.enable_disk = enable_disk
        if enable_disk:
            if cache_dir is None:
                cache_dir = Path.home() / ".ipfs_kit" / "cache"
            self.disk_cache = DiskCache(cache_dir, max_size_mb=disk_size_mb)
        else:
            self.disk_cache = None
        
        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'memory_hits': 0,
            'disk_hits': 0,
            'sets': 0,
            'deletes': 0,
            'invalidations': 0
        }
        
        logger.info(f"Cache Manager initialized (policy={memory_policy}, disk={enable_disk})")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache
        
        Checks L1 (memory) first, then L2 (disk) if enabled.
        Promotes disk hits to memory cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        # Try memory cache first
        entry = self.memory_cache.get(key)
        if entry:
            self.stats['hits'] += 1
            self.stats['memory_hits'] += 1
            return entry.value
        
        # Try disk cache if enabled
        if self.enable_disk and self.disk_cache:
            entry = self.disk_cache.get(key)
            if entry:
                self.stats['hits'] += 1
                self.stats['disk_hits'] += 1
                
                # Promote to memory cache
                self.memory_cache.set(key, entry)
                
                return entry.value
        
        # Cache miss
        self.stats['misses'] += 1
        return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        memory_only: bool = False
    ):
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None = no expiration)
            memory_only: Only cache in memory, not disk
        """
        entry = CacheEntry(key, value, ttl)
        
        # Always set in memory cache
        self.memory_cache.set(key, entry)
        
        # Optionally set in disk cache
        if not memory_only and self.enable_disk and self.disk_cache:
            self.disk_cache.set(key, entry)
        
        self.stats['sets'] += 1
    
    def delete(self, key: str) -> bool:
        """
        Delete value from cache
        
        Args:
            key: Cache key
            
        Returns:
            True if key was deleted, False if not found
        """
        deleted = False
        
        # Delete from memory
        if self.memory_cache.delete(key):
            deleted = True
        
        # Delete from disk
        if self.enable_disk and self.disk_cache:
            if self.disk_cache.delete(key):
                deleted = True
        
        if deleted:
            self.stats['deletes'] += 1
        
        return deleted
    
    def invalidate_pattern(self, pattern: str):
        """
        Invalidate all keys matching a pattern
        
        Args:
            pattern: Pattern to match (supports * wildcard)
        """
        import fnmatch
        
        count = 0
        
        # Get all keys from both tiers
        all_keys = set(self.memory_cache.get_all_keys())
        if self.enable_disk and self.disk_cache:
            all_keys.update(self.disk_cache.get_all_keys())
        
        # Delete matching keys
        for key in all_keys:
            if fnmatch.fnmatch(key, pattern):
                self.delete(key)
                count += 1
        
        self.stats['invalidations'] += count
        logger.info(f"Invalidated {count} cache entries matching '{pattern}'")
    
    def clear(self, tier: str = 'all'):
        """
        Clear cache
        
        Args:
            tier: 'memory', 'disk', or 'all'
        """
        if tier in ('memory', 'all'):
            self.memory_cache.clear()
            logger.info("Memory cache cleared")
        
        if tier in ('disk', 'all') and self.enable_disk and self.disk_cache:
            self.disk_cache.clear()
            logger.info("Disk cache cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache statistics
        """
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        stats = {
            'total_requests': total_requests,
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'hit_rate_percent': round(hit_rate, 2),
            'memory_hits': self.stats['memory_hits'],
            'disk_hits': self.stats['disk_hits'],
            'sets': self.stats['sets'],
            'deletes': self.stats['deletes'],
            'invalidations': self.stats['invalidations'],
            'memory_size': self.memory_cache.size(),
            'disk_size': self.disk_cache.size() if self.enable_disk and self.disk_cache else 0,
        }
        
        return stats
    
    def reset_statistics(self):
        """Reset statistics counters"""
        self.stats = {
            'hits': 0,
            'misses': 0,
            'memory_hits': 0,
            'disk_hits': 0,
            'sets': 0,
            'deletes': 0,
            'invalidations': 0
        }
        logger.info("Cache statistics reset")
