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
import tempfile
from typing import Dict, Any, Optional, List

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
        debug_mode: bool = False,
        config: Dict[str, Any] = None
    ):
        """
        Initialize the Cache Manager.

        Args:
            base_path: Base path for cache persistence
            memory_limit: Memory cache size limit in bytes
            disk_limit: Disk cache size limit in bytes
            debug_mode: Enable debug logging
            config: Additional configuration options
        """
        self.base_path = base_path or os.path.join(tempfile.gettempdir(), "mcp_cache")
        self.memory_limit = memory_limit
        self.disk_limit = disk_limit
        self.debug_mode = debug_mode
        self.config = config or {}
        
        # Initialize cache structures
        self.memory_cache = {}
        self.disk_cache_index = {}
        self.cache_lock = threading.RLock()
        
        # Create base directory if it doesn't exist
        os.makedirs(self.base_path, exist_ok=True)
        
        logger.info(f"Initialized MCPCacheManager at {self.base_path}")
        if self.debug_mode:
            logger.debug(f"Cache limits: memory={self.memory_limit}, disk={self.disk_limit}")
    
    def get(self, key: str) -> Any:
        """
        Get an item from the cache.
        
        Args:
            key: Cache key to retrieve
            
        Returns:
            The cached value or None if not found
        """
        with self.cache_lock:
            # Check memory cache first
            if key in self.memory_cache:
                if self.debug_mode:
                    logger.debug(f"Memory cache hit for key: {key}")
                return self.memory_cache[key]
                
            # Check disk cache if not in memory
            if key in self.disk_cache_index:
                if self.debug_mode:
                    logger.debug(f"Disk cache hit for key: {key}")
                return self._load_from_disk(key)
                
            return None
    
    def put(self, key: str, value: Any) -> bool:
        """
        Store an item in the cache.
        
        Args:
            key: Cache key
            value: Value to store
            
        Returns:
            True if successful, False otherwise
        """
        with self.cache_lock:
            try:
                # Store in memory cache
                self.memory_cache[key] = value
                
                # TODO: Implement memory limit enforcement
                # TODO: Implement disk cache persistence
                
                if self.debug_mode:
                    logger.debug(f"Stored key in memory cache: {key}")
                return True
            except Exception as e:
                logger.error(f"Error storing key {key} in cache: {str(e)}")
                return False
    
    def remove(self, key: str) -> bool:
        """
        Remove an item from the cache.
        
        Args:
            key: Cache key to remove
            
        Returns:
            True if removed, False if not found or error
        """
        with self.cache_lock:
            removed = False
            
            # Remove from memory cache
            if key in self.memory_cache:
                del self.memory_cache[key]
                removed = True
                
            # Remove from disk cache if present
            if key in self.disk_cache_index:
                try:
                    disk_path = self._get_disk_path(key)
                    if os.path.exists(disk_path):
                        os.remove(disk_path)
                    del self.disk_cache_index[key]
                    removed = True
                except Exception as e:
                    logger.error(f"Error removing key {key} from disk cache: {str(e)}")
            
            return removed
    
    def clear(self) -> bool:
        """
        Clear all cache entries.
        
        Returns:
            True if successful, False otherwise
        """
        with self.cache_lock:
            try:
                # Clear memory cache
                self.memory_cache.clear()
                
                # Clear disk cache
                for key in list(self.disk_cache_index.keys()):
                    try:
                        disk_path = self._get_disk_path(key)
                        if os.path.exists(disk_path):
                            os.remove(disk_path)
                    except Exception as e:
                        logger.warning(f"Error removing disk cache file for key {key}: {str(e)}")
                        
                self.disk_cache_index.clear()
                
                logger.info("Cache cleared")
                return True
            except Exception as e:
                logger.error(f"Error clearing cache: {str(e)}")
                return False
    
    def exists(self, key: str) -> bool:
        """
        Check if a key exists in the cache.
        
        Args:
            key: Cache key to check
            
        Returns:
            True if key exists, False otherwise
        """
        with self.cache_lock:
            return key in self.memory_cache or key in self.disk_cache_index
    
    def _get_disk_path(self, key: str) -> str:
        """
        Get the disk path for a cache key.
        
        Args:
            key: Cache key
            
        Returns:
            Full path to the disk cache file
        """
        # Create a safe filename from the key
        safe_key = "".join(c if c.isalnum() else "_" for c in key)
        return os.path.join(self.base_path, f"{safe_key}.cache")
    
    def _load_from_disk(self, key: str) -> Any:
        """
        Load a value from disk cache.
        
        Args:
            key: Cache key
            
        Returns:
            The cached value or None if not found
        """
        try:
            disk_path = self._get_disk_path(key)
            if not os.path.exists(disk_path):
                if key in self.disk_cache_index:
                    del self.disk_cache_index[key]
                return None
                
            with open(disk_path, "rb") as f:
                value = pickle.load(f)
                
            # Move to memory cache for faster access next time
            self.memory_cache[key] = value
            
            return value
        except Exception as e:
            logger.error(f"Error loading key {key} from disk cache: {str(e)}")
            return None
    
    def _save_to_disk(self, key: str, value: Any) -> bool:
        """
        Save a value to disk cache.
        
        Args:
            key: Cache key
            value: Value to store
            
        Returns:
            True if successful, False otherwise
        """
        try:
            disk_path = self._get_disk_path(key)
            
            with open(disk_path, "wb") as f:
                pickle.dump(value, f)
                
            self.disk_cache_index[key] = {
                "path": disk_path,
                "timestamp": time.time(),
                "size": os.path.getsize(disk_path)
            }
            
            return True
        except Exception as e:
            logger.error(f"Error saving key {key} to disk cache: {str(e)}")
            return False
