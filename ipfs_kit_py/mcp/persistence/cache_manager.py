"""
Cache Manager for the MCP server.

This module provides a caching layer for operation results 
with support for persistence across restarts.
"""

import os
import json
import time
import logging
import threading
import pickle
from typing import Dict, Any, Optional, Tuple, List
import tempfile

# Configure logger
logger = logging.getLogger(__name__)

class MCPCacheManager:
    """
    Cache Manager for the MCP server.
    
    Provides memory and disk caching for operation results with
    automatic cleanup and persistence.
    """
    
    def __init__(self, 
                base_path: str = None, 
                memory_limit: int = 100 * 1024 * 1024,  # 100 MB
                disk_limit: int = 1024 * 1024 * 1024,  # 1 GB
                debug_mode: bool = False):
        """
        Initialize the Cache Manager.
        
        Args:
            base_path: Base path for cache persistence
            memory_limit: Maximum memory cache size in bytes
            disk_limit: Maximum disk cache size in bytes
            debug_mode: Enable debug logging
        """
        self.base_path = base_path or os.path.expanduser("~/.ipfs_kit/mcp/cache")
        self.memory_limit = memory_limit
        self.disk_limit = disk_limit
        self.debug_mode = debug_mode
        
        # Create cache directories
        # First ensure base path exists
        os.makedirs(self.base_path, exist_ok=True)
        
        # Initialize memory cache
        self.memory_cache = {}
        self.memory_cache_size = 0
        
        # Set up disk cache path and ensure it exists
        self.disk_cache_path = os.path.join(self.base_path, "disk_cache")
        os.makedirs(self.disk_cache_path, exist_ok=True)
        
        logger.debug(f"Cache directories created at {self.base_path} and {self.disk_cache_path}")
        
        # Metadata for cache entries
        self.metadata = {}
        self.metadata_path = os.path.join(self.base_path, "metadata.json")
        self._load_metadata()
        
        # Cache stats
        self.stats = {
            "memory_hits": 0,
            "disk_hits": 0,
            "misses": 0,
            "memory_evictions": 0,
            "disk_evictions": 0,
            "put_operations": 0,
            "get_operations": 0,
            "memory_size": 0,
            "disk_size": 0
        }
        
        # Lock for thread safety
        self.lock = threading.RLock()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self.cleanup_thread.start()
        
        logger.info(f"Cache Manager initialized with {memory_limit/1024/1024:.1f} MB memory cache, "
                   f"{disk_limit/1024/1024/1024:.1f} GB disk cache")
    
    def _load_metadata(self):
        """Load cache metadata from disk."""
        if os.path.exists(self.metadata_path):
            try:
                with open(self.metadata_path, 'r') as f:
                    self.metadata = json.load(f)
                logger.info(f"Loaded cache metadata with {len(self.metadata)} entries")
            except Exception as e:
                logger.error(f"Error loading cache metadata: {e}")
                # Start with empty metadata
                self.metadata = {}
        else:
            # No metadata file exists yet
            self.metadata = {}
    
    def _save_metadata(self):
        """Save cache metadata to disk."""
        try:
            with open(self.metadata_path, 'w') as f:
                json.dump(self.metadata, f)
        except Exception as e:
            logger.error(f"Error saving cache metadata: {e}")
    
    def _cleanup_worker(self):
        """Background thread for cache cleanup."""
        # Flag to indicate if thread should stop
        self._stop_cleanup = False
        self._cleanup_thread_running = True
        
        try:
            while not self._stop_cleanup:
                try:
                    # Sleep for a bit - use short sleeps to check for stop flag more frequently
                    for _ in range(60):  # Check every minute in 1-second increments
                        if self._stop_cleanup:
                            break
                        time.sleep(1)
                    
                    if self._stop_cleanup:
                        break
                    
                    # Check if cleanup is needed and if directories exist
                    with self.lock:
                        # Verify that directories exist before attempting cleanup
                        if not os.path.exists(self.base_path):
                            logger.warning(f"Cache base path {self.base_path} no longer exists, skipping cleanup")
                            continue
                            
                        if not os.path.exists(self.disk_cache_path):
                            logger.warning(f"Disk cache path {self.disk_cache_path} no longer exists, skipping cleanup")
                            continue
                        
                        memory_usage = self.memory_cache_size
                        if memory_usage > self.memory_limit * 0.9:  # 90% full
                            self._evict_from_memory(memory_usage - self.memory_limit * 0.7)  # Target 70% usage
                            
                        # Check disk usage
                        try:
                            disk_usage = self._get_disk_cache_size()
                            if disk_usage > self.disk_limit * 0.9:  # 90% full
                                self._evict_from_disk(disk_usage - self.disk_limit * 0.7)  # Target 70% usage
                        except (FileNotFoundError, OSError) as e:
                            logger.warning(f"Disk cache access error during cleanup: {e}")
                            
                        # Save metadata periodically
                        try:
                            self._save_metadata()
                        except (FileNotFoundError, OSError) as e:
                            logger.warning(f"Metadata save error during cleanup: {e}")
                        
                except Exception as e:
                    logger.error(f"Error in cache cleanup worker: {e}")
                    # Sleep briefly after an error to avoid tight error loops
                    for _ in range(5):  # 5-second sleep in 1-second increments
                        if self._stop_cleanup:
                            break
                        time.sleep(1)
        finally:
            logger.info("Cache cleanup worker thread exiting")
            self._cleanup_thread_running = False
            
    def stop_cleanup_thread(self):
        """Stop the cleanup thread gracefully."""
        if hasattr(self, '_cleanup_thread_running') and self._cleanup_thread_running:
            logger.info("Stopping cache cleanup thread")
            self._stop_cleanup = True
            # Wait for thread to exit (with timeout)
            start_time = time.time()
            while self._cleanup_thread_running and time.time() - start_time < 5:
                time.sleep(0.1)
            logger.info("Cache cleanup thread stopped")
            
    def __del__(self):
        """Destructor to ensure cleanup resources."""
        self.stop_cleanup_thread()
    
    def _get_disk_cache_size(self) -> int:
        """Get the current disk cache size in bytes."""
        total_size = 0
        for key in os.listdir(self.disk_cache_path):
            file_path = os.path.join(self.disk_cache_path, key)
            if os.path.isfile(file_path):
                total_size += os.path.getsize(file_path)
        return total_size
    
    def _evict_from_memory(self, bytes_to_free: int):
        """
        Evict items from memory cache to free up space.
        
        Args:
            bytes_to_free: Number of bytes to free
        """
        logger.debug(f"Evicting {bytes_to_free / 1024 / 1024:.1f} MB from memory cache")
        
        # Get list of keys with their metadata
        items = []
        for key, value in self.memory_cache.items():
            if key in self.metadata:
                # Build (key, score, size) tuple for sorting
                score = self._calculate_score(key)
                size = self.metadata[key].get("size", 0)
                items.append((key, score, size))
        
        # Sort by score (lowest first to evict)
        items.sort(key=lambda x: x[1])
        
        # Evict until we've freed enough space
        freed = 0
        for key, score, size in items:
            if freed >= bytes_to_free:
                break
                
            # Evict from memory
            if key in self.memory_cache:
                del self.memory_cache[key]
                freed += size
                self.stats["memory_evictions"] += 1
                self.memory_cache_size -= size
                
                # Update metadata
                self.metadata[key]["in_memory"] = False
                
                logger.debug(f"Evicted key {key} from memory cache, size: {size/1024:.1f} KB, score: {score:.3f}")
        
        logger.debug(f"Freed {freed / 1024 / 1024:.1f} MB from memory cache")
    
    def _evict_from_disk(self, bytes_to_free: int):
        """
        Evict items from disk cache to free up space.
        
        Args:
            bytes_to_free: Number of bytes to free
        """
        logger.debug(f"Evicting {bytes_to_free / 1024 / 1024:.1f} MB from disk cache")
        
        # Build list of (key, score, size) tuples
        items = []
        for key, meta in self.metadata.items():
            if meta.get("on_disk", False):
                score = self._calculate_score(key)
                size = meta.get("size", 0)
                items.append((key, score, size))
        
        # Sort by score (lowest first to evict)
        items.sort(key=lambda x: x[1])
        
        # Evict until we've freed enough space
        freed = 0
        for key, score, size in items:
            if freed >= bytes_to_free:
                break
                
            # Remove from disk
            disk_path = os.path.join(self.disk_cache_path, self._key_to_filename(key))
            if os.path.exists(disk_path):
                try:
                    os.unlink(disk_path)
                    freed += size
                    self.stats["disk_evictions"] += 1
                    
                    # Update metadata
                    self.metadata[key]["on_disk"] = False
                    
                    logger.debug(f"Evicted key {key} from disk cache, size: {size/1024:.1f} KB, score: {score:.3f}")
                    
                except Exception as e:
                    logger.error(f"Error removing cache file {disk_path}: {e}")
        
        logger.debug(f"Freed {freed / 1024 / 1024:.1f} MB from disk cache")
    
    def _calculate_score(self, key: str) -> float:
        """
        Calculate a score for cache entry priority.
        
        Higher scores mean higher priority (less likely to be evicted).
        Score is based on recency, frequency, and size.
        
        Args:
            key: Cache key
            
        Returns:
            Score value (higher is better)
        """
        meta = self.metadata.get(key, {})
        
        # Get base metrics
        access_count = meta.get("access_count", 0)
        last_access = meta.get("last_access", 0)
        size = meta.get("size", 0)
        
        # Calculate recency factor (0-1, higher is more recent)
        current_time = time.time()
        time_since_access = current_time - last_access
        recency = max(0, 1.0 - (time_since_access / (24 * 60 * 60)))  # 1 day decay
        
        # Calculate frequency factor
        frequency = min(1.0, access_count / 10.0)  # Max out at 10 accesses
        
        # Calculate size penalty (smaller items preferred)
        size_factor = max(0.1, 1.0 - (size / (10 * 1024 * 1024)))  # 10MB is minimum score
        
        # Combine factors
        score = (recency * 0.4 + frequency * 0.4 + size_factor * 0.2)
        
        return score
    
    def _key_to_filename(self, key: str) -> str:
        """
        Convert a cache key to a filename safe format.
        
        Args:
            key: Cache key
            
        Returns:
            Filename for the key
        """
        # Replace unsafe characters
        safe_key = key.replace("/", "_").replace(":", "_")
        
        # Hash long keys
        if len(safe_key) > 100:
            import hashlib
            safe_key = hashlib.md5(key.encode()).hexdigest()
        
        return safe_key
    
    def put(self, key: str, value: Any, metadata: Dict[str, Any] = None) -> bool:
        """
        Store a value in the cache.
        
        Args:
            key: Cache key
            value: Value to store
            metadata: Additional metadata for the value
            
        Returns:
            True if the value was stored successfully
        """
        with self.lock:
            self.stats["put_operations"] += 1
            
            # Calculate value size
            try:
                # Serialize to get size
                value_bytes = pickle.dumps(value)
                size = len(value_bytes)
            except Exception as e:
                logger.error(f"Error serializing value for key {key}: {e}")
                return False
            
            # Update metadata
            if key not in self.metadata:
                self.metadata[key] = {
                    "created_at": time.time(),
                    "access_count": 0
                }
            
            self.metadata[key].update({
                "last_access": time.time(),
                "size": size,
                "in_memory": True
            })
            
            # Add user-provided metadata
            if metadata:
                self.metadata[key].update(metadata)
            
            # Store in memory if it fits
            if size <= self.memory_limit * 0.1:  # Don't store items > 10% of limit
                # Check if we need to make room
                if self.memory_cache_size + size > self.memory_limit:
                    self._evict_from_memory(size)
                
                # Store in memory
                self.memory_cache[key] = value
                self.memory_cache_size += size
                self.metadata[key]["in_memory"] = True
                
                if self.debug_mode:
                    logger.debug(f"Stored key {key} in memory, size: {size/1024:.1f} KB")
            
            # Store on disk
            temp_path = None
            try:
                # Make sure disk_cache_path exists
                if not os.path.exists(self.disk_cache_path):
                    os.makedirs(self.disk_cache_path, exist_ok=True)
                
                disk_path = os.path.join(self.disk_cache_path, self._key_to_filename(key))
                
                # Check disk cache size
                disk_size = self._get_disk_cache_size()
                if disk_size + size > self.disk_limit:
                    self._evict_from_disk(size)
                
                # Write to temporary file first
                with tempfile.NamedTemporaryFile(delete=False, dir=self.disk_cache_path) as tf:
                    tf.write(value_bytes)
                    temp_path = tf.name
                
                # Atomic move to final location
                os.replace(temp_path, disk_path)
                temp_path = None  # Mark as moved so we don't try to clean it up
                self.metadata[key]["on_disk"] = True
                
                if self.debug_mode:
                    logger.debug(f"Stored key {key} on disk, size: {size/1024:.1f} KB")
                
                return True
                
            except Exception as e:
                logger.error(f"Error storing key {key} on disk: {e}")
                # Clean up temp file if it exists
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except Exception as cleanup_error:
                        logger.error(f"Error cleaning up temporary file {temp_path}: {cleanup_error}")
                
                # Still return True if we stored in memory
                return key in self.memory_cache
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        with self.lock:
            self.stats["get_operations"] += 1
            
            # Try memory cache first
            if key in self.memory_cache:
                self.stats["memory_hits"] += 1
                
                # Update metadata
                if key in self.metadata:
                    self.metadata[key]["last_access"] = time.time()
                    self.metadata[key]["access_count"] = self.metadata[key].get("access_count", 0) + 1
                
                if self.debug_mode:
                    logger.debug(f"Memory cache hit for key {key}")
                
                return self.memory_cache[key]
            
            # Check disk cache
            try:
                # Make sure disk_cache_path exists
                if not os.path.exists(self.disk_cache_path):
                    os.makedirs(self.disk_cache_path, exist_ok=True)
                    
                disk_path = os.path.join(self.disk_cache_path, self._key_to_filename(key))
                if os.path.exists(disk_path):
                    file_obj = None
                    try:
                        file_obj = open(disk_path, 'rb')
                        file_data = file_obj.read()
                        value = pickle.loads(file_data)
                        
                        self.stats["disk_hits"] += 1
                        
                        # Update metadata
                        if key in self.metadata:
                            self.metadata[key]["last_access"] = time.time()
                            self.metadata[key]["access_count"] = self.metadata[key].get("access_count", 0) + 1
                        
                        # Promote to memory if it fits
                        size = len(file_data)
                        if size <= self.memory_limit * 0.1:  # Don't store items > 10% of limit
                            # Check if we need to make room
                            if self.memory_cache_size + size > self.memory_limit:
                                self._evict_from_memory(size)
                            
                            # Store in memory
                            self.memory_cache[key] = value
                            self.memory_cache_size += size
                            if key in self.metadata:
                                self.metadata[key]["in_memory"] = True
                            
                            if self.debug_mode:
                                logger.debug(f"Promoted key {key} to memory cache, size: {size/1024:.1f} KB")
                        
                        if self.debug_mode:
                            logger.debug(f"Disk cache hit for key {key}")
                        
                        return value
                        
                    except (IOError, pickle.PickleError) as e:
                        logger.error(f"Error reading/unpickling cache file {disk_path}: {e}")
                        # Try to remove corrupted file
                        try:
                            os.unlink(disk_path)
                            logger.warning(f"Removed corrupted cache file: {disk_path}")
                        except Exception as del_error:
                            logger.error(f"Error removing corrupted cache file: {del_error}")
                    finally:
                        # Ensure file is closed
                        if file_obj:
                            file_obj.close()
            except Exception as e:
                logger.error(f"Unexpected error accessing disk cache for key {key}: {e}")
            
            # Cache miss
            self.stats["misses"] += 1
            if self.debug_mode:
                logger.debug(f"Cache miss for key {key}")
            
            return None
    
    def delete(self, key: str) -> bool:
        """
        Delete a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if the value was deleted
        """
        with self.lock:
            deleted = False
            
            # Remove from memory if present
            if key in self.memory_cache:
                size = self.metadata.get(key, {}).get("size", 0)
                del self.memory_cache[key]
                self.memory_cache_size -= size
                deleted = True
                
                if self.debug_mode:
                    logger.debug(f"Deleted key {key} from memory cache")
            
            # Remove from disk if present
            disk_path = os.path.join(self.disk_cache_path, self._key_to_filename(key))
            if os.path.exists(disk_path):
                try:
                    os.unlink(disk_path)
                    deleted = True
                    
                    if self.debug_mode:
                        logger.debug(f"Deleted key {key} from disk cache")
                        
                except Exception as e:
                    logger.error(f"Error deleting cache file {disk_path}: {e}")
            
            # Remove metadata
            if key in self.metadata:
                del self.metadata[key]
            
            return deleted
    
    def clear(self) -> bool:
        """
        Clear all cache entries.
        
        Returns:
            True if the cache was cleared successfully
        """
        with self.lock:
            try:
                # Clear memory cache
                self.memory_cache = {}
                self.memory_cache_size = 0
                
                # Clear disk cache
                for filename in os.listdir(self.disk_cache_path):
                    file_path = os.path.join(self.disk_cache_path, filename)
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                
                # Clear metadata
                self.metadata = {}
                if os.path.exists(self.metadata_path):
                    os.unlink(self.metadata_path)
                
                # Reset stats
                self.stats = {
                    "memory_hits": 0,
                    "disk_hits": 0,
                    "misses": 0,
                    "memory_evictions": 0,
                    "disk_evictions": 0,
                    "put_operations": 0,
                    "get_operations": 0,
                    "memory_size": 0,
                    "disk_size": 0
                }
                
                logger.info("Cache cleared")
                return True
                
            except Exception as e:
                logger.error(f"Error clearing cache: {e}")
                return False
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get information about the cache.
        
        Returns:
            Dictionary with cache statistics
        """
        with self.lock:
            # Update size stats
            self.stats["memory_size"] = self.memory_cache_size
            self.stats["disk_size"] = self._get_disk_cache_size()
            
            # Calculate hit rates
            total_gets = self.stats["memory_hits"] + self.stats["disk_hits"] + self.stats["misses"]
            memory_hit_rate = self.stats["memory_hits"] / total_gets if total_gets > 0 else 0
            disk_hit_rate = self.stats["disk_hits"] / total_gets if total_gets > 0 else 0
            overall_hit_rate = (self.stats["memory_hits"] + self.stats["disk_hits"]) / total_gets if total_gets > 0 else 0
            
            return {
                "stats": self.stats,
                "memory_hit_rate": memory_hit_rate,
                "disk_hit_rate": disk_hit_rate,
                "overall_hit_rate": overall_hit_rate,
                "memory_usage": self.memory_cache_size,
                "memory_limit": self.memory_limit,
                "memory_usage_percent": (self.memory_cache_size / self.memory_limit) * 100 if self.memory_limit > 0 else 0,
                "disk_usage": self.stats["disk_size"],
                "disk_limit": self.disk_limit,
                "disk_usage_percent": (self.stats["disk_size"] / self.disk_limit) * 100 if self.disk_limit > 0 else 0,
                "item_count": len(self.metadata),
                "memory_item_count": len(self.memory_cache),
                "timestamp": time.time()
            }
            
    def list_keys(self) -> List[str]:
        """
        List all cache keys.
        
        Returns:
            List of all cache keys
        """
        with self.lock:
            # Combine keys from memory and metadata
            keys = set(self.memory_cache.keys())
            keys.update(self.metadata.keys())
            return list(keys)