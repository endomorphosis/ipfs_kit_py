"""
IPFS FSSpec integration module for IPFS Kit.

This module provides a filesystem-like interface to IPFS content using the
fsspec specification, enabling unified access across different storage backends.
The implementation includes tiered caching with memory-mapped files for high
performance access to IPFS content.

Key features:
- Standard filesystem interface (open, read, write, ls, etc.)
- Transparent content addressing via IPFS CIDs
- Multi-tier caching for optimized performance
- Memory-mapped access for large files
- Unix socket support for high-performance local operations
- Integration with data science tools and libraries
- Performance metrics collection and optimization

Performance characteristics:
- Memory cache access: ~1ms latency
- Disk cache access: ~10-50ms latency
- Network access: ~100-1000ms latency (depends on network conditions)
- Memory-mapped files provide efficient random access for large files
- Adaptive caching uses recency, frequency, and size to optimize cache utilization
"""

import os
import io
import mmap
import math
import time
import json
import uuid
import logging
import tempfile
import requests
import shutil
import threading
import statistics
import collections
from typing import Dict, List, Optional, Union, Any, BinaryIO, Tuple, Iterator, Counter, Deque

try:
    # Try to import Unix socket adapter for better local performance
    import requests_unixsocket
    UNIX_SOCKET_AVAILABLE = True
except ImportError:
    UNIX_SOCKET_AVAILABLE = False

try:
    # Import fsspec components
    from fsspec.spec import AbstractFileSystem
    from fsspec.implementations.local import LocalFileSystem
    FSSPEC_AVAILABLE = True
except ImportError:
    # Create placeholder for documentation/type hints
    class AbstractFileSystem:
        pass
    class LocalFileSystem:
        pass
    FSSPEC_AVAILABLE = False
    
# Import enhanced cache implementation
try:
    from .tiered_cache import ARCache, DiskCache, TieredCacheManager
    ENHANCED_CACHE_AVAILABLE = True
except ImportError:
    # If enhanced cache is not available, we'll use the older implementation
    ENHANCED_CACHE_AVAILABLE = False
    # Define a fallback warning
    import warnings
    warnings.warn(
        "Enhanced cache implementation not available. Using legacy cache implementation. "
        "Install with 'pip install -e .' to enable enhanced caching with full ARC algorithm support."
    )

from .error import (
    IPFSError, IPFSConnectionError, IPFSTimeoutError, IPFSContentNotFoundError,
    IPFSValidationError, IPFSConfigurationError, IPFSPinningError,
    create_result_dict, handle_error, perform_with_retry
)
from .validation import validate_cid, validate_path, is_valid_cid

# Configure logger
logger = logging.getLogger(__name__)

class ARCache:
    """Adaptive Replacement Cache for optimized memory caching.
    
    This implements a simplified version of the ARC algorithm which balances
    between recently used and frequently used items for better cache hit rates.
    """
    
    def __init__(self, maxsize: int = 100 * 1024 * 1024):
        """Initialize the AR Cache.
        
        Args:
            maxsize: Maximum size of the cache in bytes
        """
        self.maxsize = maxsize
        self.current_size = 0
        self.cache = {}  # CID -> (data, metadata)
        self.access_stats = {}  # CID -> access statistics
        self.logger = logging.getLogger(__name__ + ".ARCache")
        
    def get(self, key: str) -> Optional[bytes]:
        """Get an item from the cache.
        
        Args:
            key: The cache key (typically a CID)
            
        Returns:
            The cached data or None if not found
        """
        item = self.cache.get(key)
        if item is None:
            self.logger.debug(f"Cache miss for key: {key}")
            return None
            
        # Update access statistics
        self._update_stats(key, 'hit')
        self.logger.debug(f"Cache hit for key: {key}")
        
        # Return the cached data
        return item[0]
        
    def put(self, key: str, data: bytes, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Store an item in the cache.
        
        Args:
            key: The cache key (typically a CID)
            data: The data to cache
            metadata: Optional metadata about the cached item
            
        Returns:
            True if the item was cached, False if it didn't fit
        """
        data_size = len(data)
        
        # Check if this item is too large for the cache
        if data_size > self.maxsize:
            self.logger.debug(f"Item too large for cache: {data_size} > {self.maxsize}")
            return False
            
        # If we already have this item, update it
        if key in self.cache:
            old_size = len(self.cache[key][0])
            self.current_size = self.current_size - old_size + data_size
            self.cache[key] = (data, metadata or {})
            self._update_stats(key, 'update')
            return True
            
        # Check if we need to make room
        while self.current_size + data_size > self.maxsize and self.cache:
            self._evict_one()
            
        # Store the new item
        self.cache[key] = (data, metadata or {})
        self.current_size += data_size
        self._update_stats(key, 'add')
        
        self.logger.debug(f"Added item to cache: {key}, size: {data_size}, total: {self.current_size}")
        return True
        
    def contains(self, key: str) -> bool:
        """Check if an item is in the cache.
        
        Args:
            key: The cache key (typically a CID)
            
        Returns:
            True if the item is in the cache, False otherwise
        """
        return key in self.cache
        
    def evict(self, key: str) -> bool:
        """Explicitly remove an item from the cache.
        
        Args:
            key: The cache key (typically a CID)
            
        Returns:
            True if the item was in the cache and removed, False otherwise
        """
        if key not in self.cache:
            return False
            
        data_size = len(self.cache[key][0])
        del self.cache[key]
        self.current_size -= data_size
        
        if key in self.access_stats:
            del self.access_stats[key]
            
        self.logger.debug(f"Evicted item from cache: {key}, freed: {data_size}")
        return True
        
    def _update_stats(self, key: str, action: str) -> None:
        """Update access statistics for an item.
        
        Args:
            key: The cache key (typically a CID)
            action: What happened to the item ('hit', 'add', or 'update')
        """
        if key not in self.access_stats:
            self.access_stats[key] = {
                'access_count': 0,
                'first_access': time.time(),
                'last_access': time.time(),
                'heat_score': 0.0
            }
            
        stats = self.access_stats[key]
        stats['access_count'] += 1
        stats['last_access'] = time.time()
        
        # Calculate heat score
        age = stats['last_access'] - stats['first_access']
        frequency = stats['access_count']
        recency = 1.0 / (1.0 + (time.time() - stats['last_access']) / 3600)  # Decay by hour
        
        # Heat formula: combination of frequency and recency with age boost
        # Higher values mean the item is "hotter" and should be kept in cache
        stats['heat_score'] = frequency * recency * (1 + min(10, age / 86400))  # Age boost (max 10x)
        
    def _evict_one(self) -> bool:
        """Evict the coldest item from the cache.
        
        Returns:
            True if an item was evicted, False if the cache was empty
        """
        if not self.cache:
            return False
            
        # Find the coldest item
        if not self.access_stats:
            # If no stats, remove an arbitrary item
            key = next(iter(self.cache.keys()))
        else:
            # Find item with lowest heat score
            key = min(
                [k for k in self.access_stats.keys() if k in self.cache],
                key=lambda k: self.access_stats[k]['heat_score']
            )
            
        return self.evict(key)

class DiskCache:
    """Disk-based cache for IPFS content.
    
    This provides persistent caching of IPFS content on disk for faster
    retrieval without requiring network access. It supports metadata storage
    and efficient organization of cached files.
    """
    
    def __init__(self, directory: str, size_limit: int = 1024 * 1024 * 1024):
        """Initialize the disk cache.
        
        Args:
            directory: Directory to store cached files
            size_limit: Maximum size of the cache in bytes (default: 1GB)
        """
        self.directory = os.path.expanduser(directory)
        self.size_limit = size_limit
        self.current_size = 0
        self.index_path = os.path.join(self.directory, "cache_index.json")
        self.metadata = {}  # CID -> metadata
        self.logger = logging.getLogger(__name__ + ".DiskCache")
        
        # Create cache directory if it doesn't exist
        os.makedirs(self.directory, exist_ok=True)
        
        # Load existing index
        self._load_index()
        
    def _load_index(self) -> None:
        """Load the cache index from disk."""
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, 'r') as f:
                    index_data = json.load(f)
                    self.metadata = index_data.get('metadata', {})
                    self.current_size = index_data.get('size', 0)
            except (json.JSONDecodeError, IOError) as e:
                self.logger.error(f"Failed to load cache index: {e}")
                self.metadata = {}
                self._recalculate_size()
        else:
            self.metadata = {}
            self._recalculate_size()
            
    def _save_index(self) -> None:
        """Save the cache index to disk."""
        try:
            index_data = {
                'metadata': self.metadata,
                'size': self.current_size,
                'updated': time.time()
            }
            
            # Write to temporary file first for atomic update
            with tempfile.NamedTemporaryFile(
                mode='w', dir=self.directory, delete=False
            ) as temp:
                json.dump(index_data, temp)
                temp_path = temp.name
                
            # Rename for atomic update
            shutil.move(temp_path, self.index_path)
            
        except (IOError, OSError) as e:
            self.logger.error(f"Failed to save cache index: {e}")
            
    def _recalculate_size(self) -> None:
        """Recalculate the total size of cached files."""
        total_size = 0
        for cid, metadata in list(self.metadata.items()):
            file_path = self._get_cache_path(cid)
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                metadata['size'] = size
                total_size += size
            else:
                # Clean up metadata for missing files
                del self.metadata[cid]
                
        self.current_size = total_size
        self.logger.debug(f"Recalculated cache size: {self.current_size} bytes")
        
    def _get_cache_path(self, cid: str) -> str:
        """Get the file path for a CID's content.
        
        Args:
            cid: The Content Identifier
            
        Returns:
            Absolute path to the cached content file
        """
        # Use the first few characters as a directory prefix for better organization
        prefix = cid[:4]
        prefix_dir = os.path.join(self.directory, prefix)
        os.makedirs(prefix_dir, exist_ok=True)
        
        return os.path.join(prefix_dir, cid)
        
    def _get_metadata_path(self, cid: str) -> str:
        """Get the file path for a CID's metadata.
        
        Args:
            cid: The Content Identifier
            
        Returns:
            Absolute path to the metadata file
        """
        return self._get_cache_path(cid) + ".metadata"
        
    def get(self, cid: str) -> Optional[bytes]:
        """Get content from the disk cache.
        
        Args:
            cid: The Content Identifier
            
        Returns:
            The cached data or None if not found
        """
        if cid not in self.metadata:
            return None
            
        file_path = self._get_cache_path(cid)
        if not os.path.exists(file_path):
            # Clean up metadata for missing file
            del self.metadata[cid]
            self._save_index()
            return None
            
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
                
            # Update access time
            self.metadata[cid]['last_access'] = time.time()
            self.metadata[cid]['access_count'] = self.metadata[cid].get('access_count', 0) + 1
            self._save_index()
            
            return data
            
        except IOError as e:
            self.logger.error(f"Failed to read from cache: {e}")
            return None
            
    def get_metadata(self, cid: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a cached item.
        
        Args:
            cid: The Content Identifier
            
        Returns:
            Metadata dictionary or None if not found
        """
        if cid not in self.metadata:
            return None
            
        return self.metadata.get(cid, {})
            
    def put(self, cid: str, data: bytes, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Store content in the disk cache.
        
        Args:
            cid: The Content Identifier
            data: The data to cache
            metadata: Optional metadata about the cached item
            
        Returns:
            True if the content was cached, False otherwise
        """
        data_size = len(data)
        
        # Check if we need to make room
        if self.current_size + data_size > self.size_limit:
            self._make_room(data_size)
            
        file_path = self._get_cache_path(cid)
        
        try:
            # Write to a temporary file first
            with tempfile.NamedTemporaryFile(
                dir=os.path.dirname(file_path), delete=False
            ) as temp:
                temp.write(data)
                temp_path = temp.name
                
            # Move the file for atomic write
            shutil.move(temp_path, file_path)
            
            # Update metadata
            self.metadata[cid] = metadata or {}
            self.metadata[cid].update({
                'size': data_size,
                'added_time': time.time(),
                'last_access': time.time(),
                'access_count': 1
            })
            
            # Write metadata to separate file for per-file access
            meta_path = self._get_metadata_path(cid)
            try:
                with open(meta_path, 'w') as f:
                    json.dump(self.metadata[cid], f)
            except (IOError, OSError) as e:
                self.logger.warning(f"Failed to write metadata file: {e}")
            
            # Update cache size
            self.current_size += data_size
            self._save_index()
            
            return True
            
        except (IOError, OSError) as e:
            self.logger.error(f"Failed to write to cache: {e}")
            return False
            
    def update_metadata(self, cid: str, metadata: Dict[str, Any]) -> bool:
        """Update metadata for a cached item.
        
        Args:
            cid: The Content Identifier
            metadata: New metadata to merge with existing
            
        Returns:
            True if metadata was updated, False otherwise
        """
        if cid not in self.metadata:
            return False
            
        try:
            # Update in-memory metadata
            self.metadata[cid].update(metadata)
            
            # Update the metadata file
            meta_path = self._get_metadata_path(cid)
            with open(meta_path, 'w') as f:
                json.dump(self.metadata[cid], f)
                
            # Save the index
            self._save_index()
            return True
            
        except (IOError, OSError) as e:
            self.logger.error(f"Failed to update metadata: {e}")
            return False
            
    def _make_room(self, needed_size: int) -> None:
        """Make room in the cache for new content.
        
        Args:
            needed_size: The amount of space needed in bytes
        """
        # If we need more space than the entire cache, just clear it
        if needed_size > self.size_limit:
            self.clear()
            return
            
        # Calculate how much space we need to free
        to_free = self.current_size + needed_size - self.size_limit
        
        if to_free <= 0:
            return
            
        # Sort items by "coldness" (low access count, old access time)
        items = list(self.metadata.items())
        items.sort(key=lambda x: (
            x[1].get('access_count', 0),  # Frequency
            x[1].get('last_access', 0)    # Recency
        ))
        
        freed = 0
        evicted_items = []
        for cid, meta in items:
            if freed >= to_free:
                break
                
            file_path = self._get_cache_path(cid)
            meta_path = self._get_metadata_path(cid)
            size = meta.get('size', 0)
            
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
                if os.path.exists(meta_path):
                    os.remove(meta_path)
                    
                del self.metadata[cid]
                self.current_size -= size
                freed += size
                evicted_items.append((cid, size))
                
            except OSError as e:
                self.logger.error(f"Failed to remove cache item: {e}")
                
        self._save_index()
        
        if evicted_items:
            self.logger.debug(f"Evicted {len(evicted_items)} items, freed {freed} bytes")
        
    def clear(self) -> None:
        """Clear the entire cache."""
        try:
            # Remove all files but keep the directory structure
            for cid in list(self.metadata.keys()):
                file_path = self._get_cache_path(cid)
                meta_path = self._get_metadata_path(cid)
                
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
                if os.path.exists(meta_path):
                    os.remove(meta_path)
                    
            # Reset metadata and size
            self.metadata = {}
            self.current_size = 0
            self._save_index()
            
        except OSError as e:
            self.logger.error(f"Failed to clear cache: {e}")
            
    def contains(self, cid: str) -> bool:
        """Check if a CID is in the cache.
        
        Args:
            cid: The Content Identifier
            
        Returns:
            True if the content is in the cache, False otherwise
        """
        if cid not in self.metadata:
            return False
            
        file_path = self._get_cache_path(cid)
        return os.path.exists(file_path)

class TieredCacheManager:
    """Manages hierarchical caching with Adaptive Replacement policy.
    
    This class implements a multi-tier storage system with automatic migration
    between tiers based on access patterns, content value, and tier health.
    Tiers are arranged in a hierarchy from fastest/smallest to slowest/largest.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the tiered cache system.
        
        Args:
            config: Configuration dictionary for cache tiers. Can include:
                {
                    # Basic two-tier configuration (backward compatible)
                    'memory_cache_size': 100MB,
                    'local_cache_size': 1GB,
                    'local_cache_path': '/path/to/cache',
                    'max_item_size': 50MB,
                    'min_access_count': 2,
                    
                    # Advanced multi-tier configuration
                    'tiers': {
                        'memory': {
                            'size': 50MB, 
                            'type': 'memory',
                            'priority': 1
                        },
                        'disk': {
                            'size': 10GB,
                            'type': 'disk',
                            'path': '/path/to/disk/cache',
                            'priority': 2
                        },
                        'ipfs_local': {
                            'type': 'ipfs',
                            'priority': 3
                        },
                        # Add more tiers as needed
                    },
                    
                    # Policies for automatic migration
                    'default_tier': 'memory',
                    'promotion_threshold': 3,  # Access count to trigger promotion
                    'demotion_threshold': 30,  # Days inactive to trigger demotion
                    'replication_policy': 'high_value'  # or 'all', 'none'
                }
        """
        self.config = config or {
            'memory_cache_size': 100 * 1024 * 1024,  # 100MB
            'local_cache_size': 1 * 1024 * 1024 * 1024,  # 1GB
            'local_cache_path': os.path.expanduser('~/.ipfs_cache'),
            'max_item_size': 50 * 1024 * 1024,  # 50MB
            'min_access_count': 2
        }
        
        # Initialize basic two-tier caches (for backward compatibility)
        self.memory_cache = ARCache(maxsize=self.config['memory_cache_size'])
        self.disk_cache = DiskCache(
            directory=self.config['local_cache_path'],
            size_limit=self.config['local_cache_size']
        )
        
        # Initialize multi-tier storage if configured
        self.tiers = {}
        if 'tiers' in self.config:
            # Set up advanced multi-tier storage
            self._setup_tiers()
            
            # Set default tier
            self.default_tier = self.config.get('default_tier', 'memory')
            
            # Migration policies
            self.promotion_threshold = self.config.get('promotion_threshold', 3)
            self.demotion_threshold = self.config.get('demotion_threshold', 30)
            self.replication_policy = self.config.get('replication_policy', 'high_value')
            self.heat_threshold = self.config.get('heat_threshold', 5.0)
        
        # Access statistics for heat scoring
        self.access_stats = {}
        self.logger = logging.getLogger(__name__ + ".TieredCacheManager")
        
        # Content metadata store
        self.content_metadata = {}
        
        # Setup periodic maintenance tasks
        self._setup_maintenance_tasks()
        
    def _setup_tiers(self) -> None:
        """Set up storage tiers from configuration."""
        tier_config = self.config.get('tiers', {})
        
        for tier_name, tier_config in tier_config.items():
            tier_type = tier_config.get('type')
            
            if tier_type == 'memory':
                # Memory tier
                size = tier_config.get('size', 100 * 1024 * 1024)  # Default 100MB
                self.tiers[tier_name] = {
                    'type': 'memory',
                    'cache': ARCache(maxsize=size),
                    'priority': tier_config.get('priority', 999),
                    'size': size,
                    'stats': {'hits': 0, 'misses': 0, 'puts': 0}
                }
                
            elif tier_type == 'disk':
                # Disk tier
                size = tier_config.get('size', 1 * 1024 * 1024 * 1024)  # Default 1GB
                path = tier_config.get('path', os.path.expanduser(f'~/.ipfs_cache/{tier_name}'))
                
                self.tiers[tier_name] = {
                    'type': 'disk',
                    'cache': DiskCache(directory=path, size_limit=size),
                    'priority': tier_config.get('priority', 999),
                    'path': path,
                    'size': size,
                    'stats': {'hits': 0, 'misses': 0, 'puts': 0}
                }
                
            # Additional tier types can be set up here
            # They require specialized handlers in get/put methods
        
        # Sort tiers by priority (ascending = faster tiers first)
        self.tier_order = sorted(
            self.tiers.keys(), 
            key=lambda t: self.tiers[t].get('priority', 999)
        )
        
        self.logger.info(f"Initialized tiered storage with tiers: {self.tier_order}")
        
    def _setup_maintenance_tasks(self) -> None:
        """Set up periodic maintenance tasks for the tiered storage system."""
        # Setup done by the system when maintenance is needed
        self.maintenance_scheduled = False
        self.last_maintenance = time.time()
        
        # Check interval (in seconds)
        self.maintenance_interval = self.config.get('maintenance_interval', 3600)  # Default 1 hour
        
    def _run_maintenance(self) -> None:
        """Run periodic maintenance tasks for the tiered storage system."""
        current_time = time.time()
        
        # Skip if maintenance ran recently
        if current_time - self.last_maintenance < self.maintenance_interval:
            return
            
        self.logger.info("Running tiered storage maintenance...")
        
        try:
            # Check for demotions (items that haven't been accessed in a while)
            self._check_for_demotions()
            
            # Check tier health
            self._check_tier_health()
            
            # Apply replication policy for high-value content
            self._apply_replication_policy()
            
            # Update last maintenance time
            self.last_maintenance = current_time
            
        except Exception as e:
            self.logger.error(f"Error during maintenance: {e}")
            
    def _check_for_demotions(self) -> None:
        """Check for content that should be demoted to lower tiers."""
        # This method is a placeholder that should be implemented
        # in the IPFSFileSystem class since it requires item migration
        pass
        
    def _check_tier_health(self) -> Dict[str, bool]:
        """Check the health of all tiers."""
        health_status = {}
        
        # Check basic tiers
        try:
            # Check memory tier
            health_status['memory'] = True  # Memory is always available
            
            # Check disk tier
            disk_path = self.config.get('local_cache_path')
            if disk_path and os.path.exists(disk_path) and os.access(disk_path, os.W_OK):
                health_status['disk'] = True
            else:
                health_status['disk'] = False
                self.logger.warning(f"Disk tier health check failed: {disk_path}")
                
        except Exception as e:
            self.logger.error(f"Error checking tier health: {e}")
            
        # Check advanced tiers if configured
        for tier_name in self.tiers:
            try:
                tier = self.tiers[tier_name]
                if tier['type'] == 'memory':
                    health_status[tier_name] = True  # Memory is always available
                elif tier['type'] == 'disk':
                    path = tier.get('path')
                    if path and os.path.exists(path) and os.access(path, os.W_OK):
                        health_status[tier_name] = True
                    else:
                        health_status[tier_name] = False
                        self.logger.warning(f"Tier {tier_name} health check failed: {path}")
                
                # Additional tier type health checks can be added here
                
            except Exception as e:
                health_status[tier_name] = False
                self.logger.error(f"Error checking {tier_name} tier health: {e}")
                
        return health_status
        
    def _apply_replication_policy(self) -> None:
        """Apply replication policy for content based on its value."""
        # This method is a placeholder that should be implemented
        # in the IPFSFileSystem class since it requires cross-tier operations
        pass
    
    def get(self, key: str, metrics=None) -> Optional[bytes]:
        """Get content from the fastest available cache tier.
        
        Args:
            key: The cache key (typically a CID)
            metrics: Optional performance metrics collector
            
        Returns:
            The cached content or None if not found
        """
        # Try the multi-tier storage first if configured
        if self.tiers:
            return self._get_from_tiers(key, metrics)
            
        # Fall back to basic two-tier storage
        return self._get_from_basic_tiers(key, metrics)
        
    def _get_from_tiers(self, key: str, metrics=None) -> Optional[bytes]:
        """Get content from the multi-tier storage system.
        
        Args:
            key: The cache key (typically a CID)
            metrics: Optional performance metrics collector
            
        Returns:
            The cached content or None if not found
        """
        # Check each tier in order (fastest to slowest)
        for tier_name in self.tier_order:
            tier = self.tiers[tier_name]
            cache = tier['cache']
            
            # Try to get content from this tier
            start_time = time.time()
            content = None
            
            if tier['type'] == 'memory':
                content = cache.get(key)
            elif tier['type'] == 'disk':
                content = cache.get(key)
            # Add other tier types here
            
            if content is not None:
                # Update tier stats
                tier['stats']['hits'] += 1
                
                # Update access metrics if provided
                if metrics:
                    elapsed = time.time() - start_time
                    metrics.record_operation_time(f'cache_{tier_name}_get', elapsed)
                    metrics.record_cache_access(f'{tier_name}_hit')
                
                # Update content access stats
                self._update_stats(key, f'{tier_name}_hit')
                
                # Get content metadata
                metadata = self._get_content_metadata(key, tier_name)
                
                # Check if content should be promoted to faster tiers
                if tier_name != self.tier_order[0]:  # If not already in fastest tier
                    access_count = metadata.get('access_count', 0)
                    if access_count >= self.promotion_threshold:
                        # Mark for promotion (actual promotion happens in filesystem)
                        metadata['promotion_candidate'] = True
                        metadata['promote_to'] = self.tier_order[0]
                        metadata['current_tier'] = tier_name
                        self._update_content_metadata(key, metadata)
                
                return content
            else:
                # Record miss for this tier
                tier['stats']['misses'] += 1
        
        # If we get here, content was not found in any tier
        self._update_stats(key, 'miss')
        if metrics:
            metrics.record_cache_access('miss')
            
        return None
        
    def _get_from_basic_tiers(self, key: str, metrics=None) -> Optional[bytes]:
        """Get content from the basic two-tier storage.
        
        Args:
            key: The cache key (typically a CID)
            metrics: Optional performance metrics collector
            
        Returns:
            The cached content or None if not found
        """
        # Try memory cache first (fastest)
        start_time = time.time()
        content = self.memory_cache.get(key)
        if content is not None:
            self._update_stats(key, 'memory_hit')
            if metrics:
                metrics.record_cache_access('memory_hit')
                elapsed = time.time() - start_time
                metrics.record_operation_time('cache_memory_get', elapsed)
            return content
            
        # Try disk cache next
        disk_start_time = time.time()
        content = self.disk_cache.get(key)
        if content is not None:
            # Promote to memory cache if it fits
            if len(content) <= self.config['max_item_size']:
                self.memory_cache.put(key, content)
            self._update_stats(key, 'disk_hit')
            if metrics:
                metrics.record_cache_access('disk_hit')
                elapsed = time.time() - disk_start_time
                metrics.record_operation_time('cache_disk_get', elapsed)
            return content
            
        # Cache miss
        self._update_stats(key, 'miss')
        if metrics:
            metrics.record_cache_access('miss')
            elapsed = time.time() - start_time
            metrics.record_operation_time('cache_miss', elapsed)
        return None
    
    def put(self, key: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Store content in appropriate cache tiers.
        
        Args:
            key: The cache key (typically a CID)
            content: The content to cache
            metadata: Additional metadata about the content
        """
        # Use multi-tier storage if configured
        if self.tiers:
            self._put_in_tiers(key, content, metadata)
            return
            
        # Fall back to basic two-tier storage
        self._put_in_basic_tiers(key, content, metadata)
        
    def _put_in_tiers(self, key: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Store content in the multi-tier storage system.
        
        Args:
            key: The cache key (typically a CID)
            content: The content to cache
            metadata: Additional metadata about the content
        """
        size = len(content)
        
        # Update metadata
        if metadata is None:
            metadata = {}
        metadata.update({
            'size': size,
            'added_time': time.time(),
            'last_access': time.time(),
            'access_count': 1,
            'current_tier': self.default_tier
        })
        
        # Store in default tier first
        default_tier = self.tiers.get(self.default_tier)
        if default_tier:
            if default_tier['type'] == 'memory' and size > self.config.get('max_item_size', 50 * 1024 * 1024):
                # Too big for memory, find the next tier
                for tier_name in self.tier_order:
                    tier = self.tiers[tier_name]
                    if tier['type'] != 'memory':
                        # Found a non-memory tier
                        cache = tier['cache']
                        cache.put(key, content, metadata)
                        tier['stats']['puts'] += 1
                        metadata['current_tier'] = tier_name
                        break
            else:
                # Store in default tier
                cache = default_tier['cache']
                cache.put(key, content, metadata)
                default_tier['stats']['puts'] += 1
        
        # Check if we should replicate to other tiers based on policy
        if self.replication_policy != 'none':
            # High-value content gets replicated to slower/more durable tiers
            if self.replication_policy == 'all' or (
                self.replication_policy == 'high_value' and 
                metadata.get('high_value', False)
            ):
                # Replicate to other tiers (based on priority)
                for tier_name in self.tier_order[1:]:  # Skip the first/fastest tier
                    tier = self.tiers[tier_name]
                    cache = tier['cache']
                    # We might apply different policies for different tier types
                    if tier['type'] == 'disk':  # Always replicate to disk
                        cache.put(key, content, metadata)
                        tier['stats']['puts'] += 1
                    # Other tier types can have custom replication logic
        
        # Store content metadata
        self._update_content_metadata(key, metadata)
        
    def _put_in_basic_tiers(self, key: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Store content in the basic two-tier storage.
        
        Args:
            key: The cache key (typically a CID)
            content: The content to cache
            metadata: Additional metadata about the content
        """
        size = len(content)
        
        # Update metadata
        if metadata is None:
            metadata = {}
        metadata.update({
            'size': size,
            'added_time': time.time(),
            'last_access': time.time(),
            'access_count': 1
        })
        
        # Store in memory cache if size appropriate
        if size <= self.config['max_item_size']:
            self.memory_cache.put(key, content)
            
        # Store in disk cache
        self.disk_cache.put(key, content, metadata)
        
    def get_heat_score(self, key: str) -> float:
        """Get the heat score for a cache item.
        
        Args:
            key: The cache key (typically a CID)
            
        Returns:
            Heat score value, or 0 if not available
        """
        if key in self.access_stats:
            return self.access_stats[key].get('heat_score', 0.0)
        return 0.0
        
    def get_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a cached item.
        
        Args:
            key: The cache key (typically a CID)
            
        Returns:
            Metadata dictionary or None if not found
        """
        return self._get_content_metadata(key)
        
    def _get_content_metadata(self, key: str, tier_name: Optional[str] = None) -> Dict[str, Any]:
        """Get metadata for content from the appropriate tier.
        
        Args:
            key: The cache key (typically a CID)
            tier_name: Optional tier name to check specifically
            
        Returns:
            Metadata dictionary (empty if not found)
        """
        # Check in-memory metadata store first
        if key in self.content_metadata:
            return self.content_metadata[key]
            
        metadata = {}
        
        # Try to get from multi-tier storage
        if self.tiers:
            if tier_name and tier_name in self.tiers:
                # Check specific tier
                tier = self.tiers[tier_name]
                if tier['type'] == 'disk':
                    meta = tier['cache'].get_metadata(key)
                    if meta:
                        metadata = meta
            else:
                # Check all tiers
                for tier_name in self.tier_order:
                    tier = self.tiers[tier_name]
                    if tier['type'] == 'disk':
                        meta = tier['cache'].get_metadata(key)
                        if meta:
                            metadata = meta
                            break
        else:
            # Try basic disk cache
            metadata = self.disk_cache.get_metadata(key) or {}
        
        # Cache metadata for future use
        self.content_metadata[key] = metadata
        return metadata
    
    def _update_content_metadata(self, key: str, metadata: Dict[str, Any]) -> None:
        """Update metadata for a cache item.
        
        Args:
            key: The cache key (typically a CID)
            metadata: New metadata to update
        """
        # Update in-memory store
        if key in self.content_metadata:
            self.content_metadata[key].update(metadata)
        else:
            self.content_metadata[key] = metadata
            
        # Try to update in multi-tier storage
        if self.tiers:
            # Get current tier
            current_tier = metadata.get('current_tier', self.default_tier)
            if current_tier in self.tiers:
                tier = self.tiers[current_tier]
                if tier['type'] == 'disk':
                    tier['cache'].update_metadata(key, metadata)
        else:
            # Try basic disk cache
            self.disk_cache.update_metadata(key, metadata)
        
    def _update_stats(self, key: str, access_type: str) -> None:
        """Update access statistics for content item.
        
        Args:
            key: The cache key (typically a CID)
            access_type: Type of access (e.g., 'memory_hit', 'disk_hit', or 'miss')
        """
        if key not in self.access_stats:
            self.access_stats[key] = {
                'access_count': 0,
                'first_access': time.time(),
                'last_access': time.time(),
                'tier_hits': {'memory': 0, 'disk': 0, 'miss': 0}
            }
            
        stats = self.access_stats[key]
        stats['access_count'] += 1
        stats['last_access'] = time.time()
        
        # Update tier-specific hits if this is a traditional tier access
        if access_type == 'memory_hit':
            stats['tier_hits']['memory'] += 1
        elif access_type == 'disk_hit':
            stats['tier_hits']['disk'] += 1
        elif access_type == 'miss':
            stats['tier_hits']['miss'] += 1
        else:
            # Handle multi-tier hit types (format: "tiername_hit")
            if access_type.endswith('_hit'):
                tier_name = access_type.split('_')[0]
                if tier_name not in stats['tier_hits']:
                    stats['tier_hits'][tier_name] = 0
                stats['tier_hits'][tier_name] += 1
            
        # Recalculate heat score
        age = stats['last_access'] - stats['first_access']
        frequency = stats['access_count']
        recency = 1.0 / (1.0 + (time.time() - stats['last_access']) / 3600)  # Decay by hour
        
        # Heat formula: combination of frequency and recency with age boost
        # Higher values indicate "hotter" content that should be kept in faster tiers
        stats['heat_score'] = frequency * recency * (1 + min(10, age / 86400))  # Age boost (max 10x)
        
        # Update content metadata
        metadata = self._get_content_metadata(key)
        metadata['access_count'] = stats['access_count']
        metadata['last_access'] = stats['last_access']
        metadata['heat_score'] = stats['heat_score']
        self._update_content_metadata(key, metadata)
        
    def evict(self, target_size: Optional[int] = None) -> int:
        """Intelligent eviction based on heat scores and tier.
        
        Args:
            target_size: Amount of space to free up, defaults to 10% of memory cache
            
        Returns:
            Amount of space freed in bytes
        """
        if target_size is None:
            # Default to 10% of memory cache
            target_size = self.config['memory_cache_size'] // 10
            
        # Find coldest items for eviction
        items = sorted(
            self.access_stats.items(),
            key=lambda x: x[1]['heat_score']
        )
        
        freed = 0
        for key, stats in items:
            if freed >= target_size:
                break
                
            # Check multi-tier storage first if configured
            if self.tiers:
                # Find which tier contains this item
                metadata = self._get_content_metadata(key)
                current_tier = metadata.get('current_tier', self.default_tier)
                
                if current_tier in self.tiers:
                    tier = self.tiers[current_tier]
                    if tier['type'] == 'memory':
                        # Evict from memory tier
                        cache = tier['cache']
                        if isinstance(cache, ARCache) and cache.contains(key):
                            size = metadata.get('size', 0)
                            cache.evict(key)
                            freed += size
            else:
                # Check basic memory cache
                if self.memory_cache.contains(key):
                    size = stats.get('size', 0)
                    self.memory_cache.evict(key)
                    freed += size
                
        return freed

class IPFSMemoryFile(io.BytesIO):
    """File-like object for IPFS content in memory."""
    
    def __init__(self, fs, path, data, mode="rb"):
        """Initialize the memory file.
        
        Args:
            fs: The filesystem object
            path: Path/CID of the file
            data: The file data
            mode: File mode (only 'rb' supported)
        """
        super().__init__(data)
        self.fs = fs
        self.path = path
        self.mode = mode
        self.size = len(data)
        
    def __repr__(self):
        return f"<IPFSMemoryFile {self.path} {self.mode}>"

class PerformanceMetrics:
    """Collect and analyze performance metrics for IPFS filesystem operations.
    
    This class provides comprehensive tools to measure and analyze various performance
    aspects of the IPFS filesystem, including latency, bandwidth, cache efficiency,
    and tier-specific metrics.
    
    Features:
    - Latency tracking for all operations
    - Bandwidth monitoring for data transfers
    - Cache hit/miss rates across all tiers
    - Tier-specific performance analytics
    - Time-series data for trend analysis
    - Periodic logging and persistence
    """
    
    def __init__(self, max_samples=1000, enable_metrics=True, metrics_config=None):
        """Initialize the performance metrics collector.
        
        Args:
            max_samples: Maximum number of timing samples to keep per operation
            enable_metrics: Whether to collect metrics (disable for production use if needed)
            metrics_config: Dictionary with configuration options for metrics collection
                {
                    'collection_interval': 60,  # Seconds between metrics collection
                    'log_directory': '/path/to/metrics/logs',
                    'track_bandwidth': True,
                    'track_latency': True,
                    'track_cache_hits': True,
                    'retention_days': 30  # How long to keep metrics logs
                }
        """
        self.enable_metrics = enable_metrics
        self.max_samples = max_samples
        
        # Default configuration
        self.config = metrics_config or {
            'collection_interval': 60,  # Every minute
            'log_directory': os.path.expanduser('~/.ipfs_metrics'),
            'track_bandwidth': True,
            'track_latency': True,
            'track_cache_hits': True,
            'retention_days': 30
        }
        
        # Create log directory if needed
        if self.enable_metrics and self.config.get('log_directory'):
            os.makedirs(self.config['log_directory'], exist_ok=True)
        
        # Operation timing data
        self.operation_times = collections.defaultdict(
            lambda: collections.deque(maxlen=max_samples)
        )
        
        # Operation counts
        self.operation_counts = collections.Counter()
        
        # Basic cache statistics
        self.cache_stats = {
            "memory_hits": 0,
            "disk_hits": 0,
            "misses": 0,
            "total": 0
        }
        
        # Advanced multi-tier metrics
        self.metrics = {
            'latency': {},  # operation -> list of timings
            'bandwidth': {
                'inbound': [],  # List of {timestamp, size, source} dicts
                'outbound': []  # List of {timestamp, size, destination} dicts
            },
            'cache': {
                'hits': 0,
                'misses': 0,
                'hit_rate': 0.0
            },
            'tiers': {}  # tier_name -> {hits, misses, hit_rate, etc.}
        }
        
        # Time-series data for historical analysis
        self.time_series = {
            'timestamps': [],
            'latency_avg': {},  # operation -> list of avg latencies at each timestamp
            'bandwidth': {
                'inbound': [],
                'outbound': []
            },
            'cache_hit_rate': []
        }
        
        # Thread synchronization
        self.lock = threading.RLock()
        
        # Logger
        self.logger = logging.getLogger(__name__ + ".PerformanceMetrics")
        
        # Start metrics collection thread if enabled
        self.collection_thread = None
        if self.enable_metrics and self.config.get('collection_interval'):
            self._start_collection_thread()
            
    def _start_collection_thread(self):
        """Start a background thread for periodic metrics collection."""
        def collection_loop():
            while self.enable_metrics:
                try:
                    self._collect_metrics()
                except Exception as e:
                    self.logger.error(f"Error in metrics collection: {e}")
                
                # Sleep for the collection interval
                time.sleep(self.config['collection_interval'])
        
        self.collection_thread = threading.Thread(
            target=collection_loop, 
            daemon=True,
            name="IPFSMetricsCollector"
        )
        self.collection_thread.start()
        
    def _collect_metrics(self):
        """Collect current metrics and store time-series data."""
        timestamp = time.time()
        
        with self.lock:
            # Record timestamp
            self.time_series['timestamps'].append(timestamp)
            
            # Calculate average latencies
            latency_avgs = {}
            for op, times in self.operation_times.items():
                if times:
                    latency_avgs[op] = statistics.mean(times)
                    # Add to time series
                    if op not in self.time_series['latency_avg']:
                        self.time_series['latency_avg'][op] = []
                    self.time_series['latency_avg'][op].append(latency_avgs[op])
            
            # Calculate bandwidth for the last interval
            current_inbound = 0
            current_outbound = 0
            cutoff_time = timestamp - self.config['collection_interval']
            
            # Calculate inbound bandwidth
            for entry in self.metrics['bandwidth']['inbound']:
                if entry['timestamp'] >= cutoff_time:
                    current_inbound += entry['size']
            
            # Calculate outbound bandwidth
            for entry in self.metrics['bandwidth']['outbound']:
                if entry['timestamp'] >= cutoff_time:
                    current_outbound += entry['size']
                    
            # Add to time series
            self.time_series['bandwidth']['inbound'].append(current_inbound)
            self.time_series['bandwidth']['outbound'].append(current_outbound)
            
            # Calculate current cache hit rate
            total = self.metrics['cache']['hits'] + self.metrics['cache']['misses']
            current_hit_rate = 0
            if total > 0:
                current_hit_rate = self.metrics['cache']['hits'] / total
            self.time_series['cache_hit_rate'].append(current_hit_rate)
            
            # Calculate tier-specific metrics
            for tier_name, tier_stats in self.metrics.get('tiers', {}).items():
                tier_total = tier_stats.get('hits', 0) + tier_stats.get('misses', 0)
                if tier_total > 0:
                    tier_stats['hit_rate'] = tier_stats.get('hits', 0) / tier_total
            
            # Write metrics to log if enabled
            if self.config.get('log_directory'):
                self._write_metrics_to_log(timestamp, latency_avgs, current_inbound, current_outbound)
                
            # Clean up old time series data if it gets too large
            max_points = 24 * 60 * 60 / self.config['collection_interval']
            if len(self.time_series['timestamps']) > max_points:
                self._truncate_time_series()
                
    def _write_metrics_to_log(self, timestamp, latency_avgs, inbound, outbound):
        """Write current metrics to log file.
        
        Args:
            timestamp: Current timestamp
            latency_avgs: Dictionary of average latencies by operation
            inbound: Current inbound bandwidth
            outbound: Current outbound bandwidth
        """
        # Create log filename based on date
        date_str = time.strftime("%Y-%m-%d", time.localtime(timestamp))
        log_file = os.path.join(self.config['log_directory'], f"ipfs_metrics_{date_str}.jsonl")
        
        # Create metrics entry
        entry = {
            'timestamp': timestamp,
            'latency': latency_avgs,
            'bandwidth': {
                'inbound': inbound,
                'outbound': outbound
            },
            'cache': {
                'hits': self.metrics['cache']['hits'],
                'misses': self.metrics['cache']['misses'],
                'hit_rate': self.metrics['cache']['hit_rate']
            },
            'tiers': self.metrics.get('tiers', {})
        }
        
        # Append to log file
        try:
            with open(log_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception as e:
            self.logger.error(f"Failed to write metrics to log: {e}")
            
        # Clean up old logs if needed
        self._cleanup_old_logs()
            
    def _cleanup_old_logs(self):
        """Remove log files older than retention period."""
        if not self.config.get('retention_days'):
            return
            
        retention_seconds = self.config['retention_days'] * 24 * 60 * 60
        current_time = time.time()
        log_dir = self.config['log_directory']
        
        try:
            for filename in os.listdir(log_dir):
                if not filename.startswith('ipfs_metrics_'):
                    continue
                    
                file_path = os.path.join(log_dir, filename)
                file_age = current_time - os.path.getmtime(file_path)
                
                if file_age > retention_seconds:
                    os.remove(file_path)
                    self.logger.debug(f"Removed old metrics log: {filename}")
        except Exception as e:
            self.logger.error(f"Error cleaning up old logs: {e}")
            
    def _truncate_time_series(self):
        """Truncate time series data to prevent unbounded growth."""
        # Keep only the most recent data points
        cutoff = len(self.time_series['timestamps']) // 2
        
        self.time_series['timestamps'] = self.time_series['timestamps'][cutoff:]
        self.time_series['bandwidth']['inbound'] = self.time_series['bandwidth']['inbound'][cutoff:]
        self.time_series['bandwidth']['outbound'] = self.time_series['bandwidth']['outbound'][cutoff:]
        self.time_series['cache_hit_rate'] = self.time_series['cache_hit_rate'][cutoff:]
        
        for op in self.time_series['latency_avg']:
            self.time_series['latency_avg'][op] = self.time_series['latency_avg'][op][cutoff:]
        
    def record_operation_time(self, operation, elapsed_time):
        """Record the execution time of an operation.
        
        Args:
            operation: Name of the operation (e.g., 'read', 'ls', 'cat')
            elapsed_time: Time taken in seconds
        """
        if not self.enable_metrics:
            return
            
        with self.lock:
            self.operation_times[operation].append(elapsed_time)
            self.operation_counts[operation] += 1
            
            # Update advanced metrics
            if operation not in self.metrics['latency']:
                self.metrics['latency'][operation] = []
            self.metrics['latency'][operation].append(elapsed_time)
            
            # Trim to max samples if needed
            if len(self.metrics['latency'][operation]) > self.max_samples:
                self.metrics['latency'][operation] = self.metrics['latency'][operation][-self.max_samples:]
    
    def record_cache_access(self, access_type):
        """Record cache access statistics.
        
        Args:
            access_type: Type of cache access ('memory_hit', 'disk_hit', 'tier_name_hit', or 'miss')
        """
        if not self.enable_metrics:
            return
            
        with self.lock:
            # Update basic stats
            self.cache_stats["total"] += 1
            
            if access_type == "memory_hit":
                self.cache_stats["memory_hits"] += 1
            elif access_type == "disk_hit":
                self.cache_stats["disk_hits"] += 1
            elif access_type == "miss":
                self.cache_stats["misses"] += 1
            
            # Update advanced metrics
            if access_type.endswith('_hit'):
                self.metrics['cache']['hits'] += 1
                
                # Handle tier-specific hits
                if '_' in access_type:
                    tier_name = access_type.split('_')[0]
                    if tier_name not in self.metrics.get('tiers', {}):
                        self.metrics.setdefault('tiers', {})[tier_name] = {'hits': 0, 'misses': 0}
                    self.metrics['tiers'][tier_name]['hits'] += 1
            else:
                self.metrics['cache']['misses'] += 1
                
                # Update tiers miss counts if applicable
                if '_' in access_type and access_type.endswith('_miss'):
                    tier_name = access_type.split('_')[0]
                    if tier_name not in self.metrics.get('tiers', {}):
                        self.metrics.setdefault('tiers', {})[tier_name] = {'hits': 0, 'misses': 0}
                    self.metrics['tiers'][tier_name]['misses'] += 1
            
            # Update hit rate
            total = self.metrics['cache']['hits'] + self.metrics['cache']['misses']
            if total > 0:
                self.metrics['cache']['hit_rate'] = self.metrics['cache']['hits'] / total
    
    def record_bandwidth(self, direction, size, source=None, destination=None):
        """Record bandwidth consumption.
        
        Args:
            direction: 'inbound' or 'outbound'
            size: Number of bytes transferred
            source: Source of the data (for inbound transfers)
            destination: Destination of the data (for outbound transfers)
        """
        if not self.enable_metrics or not self.config.get('track_bandwidth'):
            return
            
        with self.lock:
            entry = {
                'timestamp': time.time(),
                'size': size
            }
            
            if direction == 'inbound':
                if source:
                    entry['source'] = source
                self.metrics['bandwidth']['inbound'].append(entry)
                
                # Trim if too many entries
                if len(self.metrics['bandwidth']['inbound']) > self.max_samples:
                    self.metrics['bandwidth']['inbound'] = self.metrics['bandwidth']['inbound'][-self.max_samples:]
                    
            elif direction == 'outbound':
                if destination:
                    entry['destination'] = destination
                self.metrics['bandwidth']['outbound'].append(entry)
                
                # Trim if too many entries
                if len(self.metrics['bandwidth']['outbound']) > self.max_samples:
                    self.metrics['bandwidth']['outbound'] = self.metrics['bandwidth']['outbound'][-self.max_samples:]
    
    def record_data_transfer(self, operation, bytes_transferred, connection_type=None, **kwargs):
        """Record data transfer with detailed connection type metrics.
        
        This method tracks data transfers with connection-specific details
        to help analyze performance differences between connection types
        (unix socket vs HTTP vs gateway).
        
        Args:
            operation: Type of operation ('fetch', 'put', 'stream', etc.)
            bytes_transferred: Number of bytes transferred
            connection_type: Connection type used ('unix_socket', 'http', 'gateway', etc.)
            **kwargs: Additional metadata for the transfer (e.g. gateway_url)
        """
        if not self.enable_metrics or not self.config.get('track_bandwidth'):
            return
        
        # Determine direction based on operation
        direction = 'inbound'
        if operation in ('put', 'upload', 'push'):
            direction = 'outbound'
            
        with self.lock:
            # Create basic entry
            entry = {
                'timestamp': time.time(),
                'size': bytes_transferred,
                'operation': operation
            }
            
            # Add connection type if provided
            if connection_type:
                entry['connection_type'] = connection_type
                
            # Add any additional metadata
            entry.update(kwargs)
            
            # Store in appropriate direction
            if direction == 'inbound':
                self.metrics['bandwidth']['inbound'].append(entry)
                
                # Track connection-specific stats
                if connection_type:
                    if 'connection_stats' not in self.metrics:
                        self.metrics['connection_stats'] = {}
                    
                    if connection_type not in self.metrics['connection_stats']:
                        self.metrics['connection_stats'][connection_type] = {
                            'bytes_received': 0,
                            'bytes_sent': 0,
                            'operations': collections.Counter(),
                            'transfer_rates': []
                        }
                    
                    # Update stats
                    self.metrics['connection_stats'][connection_type]['bytes_received'] += bytes_transferred
                    self.metrics['connection_stats'][connection_type]['operations'][operation] += 1
                    
                    # Calculate and store transfer rate if duration is available
                    if 'duration' in kwargs:
                        duration = kwargs['duration']
                        if duration > 0:
                            rate = bytes_transferred / duration  # bytes per second
                            self.metrics['connection_stats'][connection_type]['transfer_rates'].append({
                                'timestamp': time.time(),
                                'rate': rate,
                                'size': bytes_transferred
                            })
                            
                            # Trim if too many entries
                            if len(self.metrics['connection_stats'][connection_type]['transfer_rates']) > self.max_samples:
                                self.metrics['connection_stats'][connection_type]['transfer_rates'] = \
                                    self.metrics['connection_stats'][connection_type]['transfer_rates'][-self.max_samples:]
                
                # Trim if too many entries
                if len(self.metrics['bandwidth']['inbound']) > self.max_samples:
                    self.metrics['bandwidth']['inbound'] = self.metrics['bandwidth']['inbound'][-self.max_samples:]
                    
            elif direction == 'outbound':
                self.metrics['bandwidth']['outbound'].append(entry)
                
                # Track connection-specific stats
                if connection_type:
                    if 'connection_stats' not in self.metrics:
                        self.metrics['connection_stats'] = {}
                    
                    if connection_type not in self.metrics['connection_stats']:
                        self.metrics['connection_stats'][connection_type] = {
                            'bytes_received': 0,
                            'bytes_sent': 0,
                            'operations': collections.Counter(),
                            'transfer_rates': []
                        }
                    
                    # Update stats
                    self.metrics['connection_stats'][connection_type]['bytes_sent'] += bytes_transferred
                    self.metrics['connection_stats'][connection_type]['operations'][operation] += 1
                    
                    # Calculate and store transfer rate if duration is available
                    if 'duration' in kwargs:
                        duration = kwargs['duration']
                        if duration > 0:
                            rate = bytes_transferred / duration  # bytes per second
                            self.metrics['connection_stats'][connection_type]['transfer_rates'].append({
                                'timestamp': time.time(),
                                'rate': rate,
                                'size': bytes_transferred
                            })
                            
                            # Trim if too many entries
                            if len(self.metrics['connection_stats'][connection_type]['transfer_rates']) > self.max_samples:
                                self.metrics['connection_stats'][connection_type]['transfer_rates'] = \
                                    self.metrics['connection_stats'][connection_type]['transfer_rates'][-self.max_samples:]
                
                # Trim if too many entries
                if len(self.metrics['bandwidth']['outbound']) > self.max_samples:
                    self.metrics['bandwidth']['outbound'] = self.metrics['bandwidth']['outbound'][-self.max_samples:]
    
    def record_tier_metrics(self, tier_name, operation_type, operation_result):
        """Record tier-specific metrics.
        
        Args:
            tier_name: Name of the storage tier
            operation_type: Type of operation ('get', 'put', 'list', etc.)
            operation_result: Result of the operation (success/failure info)
        """
        if not self.enable_metrics:
            return
            
        with self.lock:
            # Initialize tier metrics if needed
            if tier_name not in self.metrics.get('tiers', {}):
                self.metrics.setdefault('tiers', {})[tier_name] = {
                    'hits': 0,
                    'misses': 0,
                    'operations': collections.Counter()
                }
                
            # Record operation
            self.metrics['tiers'][tier_name]['operations'][operation_type] += 1
            
            # Add any custom metrics from the operation result
            if isinstance(operation_result, dict):
                for key, value in operation_result.items():
                    if key in ('latency', 'size', 'status'):
                        if key not in self.metrics['tiers'][tier_name]:
                            self.metrics['tiers'][tier_name][key] = []
                        self.metrics['tiers'][tier_name][key].append(value)
                        
                        # Trim if needed
                        if len(self.metrics['tiers'][tier_name][key]) > self.max_samples:
                            self.metrics['tiers'][tier_name][key] = self.metrics['tiers'][tier_name][key][-self.max_samples:]
    
    def get_operation_stats(self, operation=None):
        """Get statistics for operation timings.
        
        Args:
            operation: Optional operation name to filter by
            
        Returns:
            Dictionary with operation statistics
        """
        if not self.enable_metrics:
            return {"metrics_disabled": True}
            
        with self.lock:
            if operation:
                # Stats for a specific operation
                times = list(self.operation_times[operation])
                if not times:
                    return {"count": 0, "no_data": True}
                    
                return {
                    "count": self.operation_counts[operation],
                    "mean": statistics.mean(times),
                    "median": statistics.median(times),
                    "min": min(times),
                    "max": max(times),
                    "p95": self._percentile(times, 95),
                    "p99": self._percentile(times, 99) if len(times) >= 100 else None
                }
            else:
                # Stats for all operations
                result = {"total_operations": sum(self.operation_counts.values())}
                
                for op, count in self.operation_counts.items():
                    times = list(self.operation_times[op])
                    if times:
                        result[op] = {
                            "count": count,
                            "mean": statistics.mean(times),
                            "median": statistics.median(times)
                        }
                    else:
                        result[op] = {"count": count, "no_data": True}
                
                return result
    
    def get_cache_stats(self):
        """Get cache performance statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        if not self.enable_metrics:
            return {"metrics_disabled": True}
            
        with self.lock:
            stats = self.cache_stats.copy()
            
            # Calculate hit rates
            total = stats["total"]
            if total > 0:
                stats["memory_hit_rate"] = stats["memory_hits"] / total
                stats["disk_hit_rate"] = stats["disk_hits"] / total
                stats["overall_hit_rate"] = (stats["memory_hits"] + stats["disk_hits"]) / total
                stats["miss_rate"] = stats["misses"] / total
            
            return stats
    
    def get_bandwidth_stats(self, interval_seconds=None):
        """Get bandwidth statistics.
        
        Args:
            interval_seconds: Timeframe to consider (defaults to all available data)
            
        Returns:
            Dictionary with bandwidth statistics
        """
        if not self.enable_metrics:
            return {"metrics_disabled": True}
            
        with self.lock:
            stats = {
                "inbound_total": 0,
                "outbound_total": 0,
                "inbound_rate": 0,
                "outbound_rate": 0
            }
            
            # Filter by time interval if specified
            cutoff_time = 0
            if interval_seconds:
                cutoff_time = time.time() - interval_seconds
            
            # Calculate totals
            inbound_bytes = 0
            for entry in self.metrics['bandwidth']['inbound']:
                if entry['timestamp'] >= cutoff_time:
                    inbound_bytes += entry['size']
                    
            outbound_bytes = 0
            for entry in self.metrics['bandwidth']['outbound']:
                if entry['timestamp'] >= cutoff_time:
                    outbound_bytes += entry['size']
            
            stats["inbound_total"] = inbound_bytes
            stats["outbound_total"] = outbound_bytes
            
            # Calculate rates if interval specified
            if interval_seconds:
                stats["inbound_rate"] = inbound_bytes / interval_seconds
                stats["outbound_rate"] = outbound_bytes / interval_seconds
                stats["interval_seconds"] = interval_seconds
            
            return stats
            
    def get_connection_stats(self, connection_type=None, interval_seconds=None):
        """Get connection-specific performance statistics.
        
        This provides detailed metrics on the performance of different connection types
        (unix_socket, http, gateway) to help identify performance differences and optimize
        connection selection.
        
        Args:
            connection_type: Optional specific connection type to analyze
            interval_seconds: Timeframe to consider (defaults to all available data)
            
        Returns:
            Dictionary with connection performance statistics
        """
        if not self.enable_metrics:
            return {"metrics_disabled": True}
            
        with self.lock:
            # Check if we have connection stats
            if 'connection_stats' not in self.metrics:
                return {"no_data": True}
                
            # Filter by time interval if specified
            cutoff_time = 0
            if interval_seconds:
                cutoff_time = time.time() - interval_seconds
                
            # Get stats for a specific connection type
            if connection_type:
                if connection_type not in self.metrics['connection_stats']:
                    return {"connection_type": connection_type, "no_data": True}
                    
                conn_stats = self.metrics['connection_stats'][connection_type]
                
                # Basic stats
                result = {
                    "connection_type": connection_type,
                    "bytes_received": conn_stats['bytes_received'],
                    "bytes_sent": conn_stats['bytes_sent'],
                    "operations_count": sum(conn_stats['operations'].values()),
                    "operations_by_type": dict(conn_stats['operations'])
                }
                
                # Calculate transfer rates
                if 'transfer_rates' in conn_stats:
                    rates = [
                        entry['rate'] 
                        for entry in conn_stats['transfer_rates']
                        if entry['timestamp'] >= cutoff_time
                    ]
                    
                    if rates:
                        result["transfer_rate"] = {
                            "mean": statistics.mean(rates),
                            "median": statistics.median(rates),
                            "min": min(rates),
                            "max": max(rates),
                            "samples": len(rates)
                        }
                        
                        # Convert to human-readable MB/s
                        for key in ["mean", "median", "min", "max"]:
                            if key in result["transfer_rate"]:
                                result["transfer_rate"][f"{key}_mbs"] = result["transfer_rate"][key] / (1024 * 1024)
                
                return result
                
            # Get comparative stats for all connection types
            else:
                result = {
                    "connection_types": list(self.metrics['connection_stats'].keys()),
                    "comparison": {}
                }
                
                # Calculate comparison metrics
                for conn_type, conn_stats in self.metrics['connection_stats'].items():
                    # Calculate average transfer rate
                    rates = [
                        entry['rate'] 
                        for entry in conn_stats.get('transfer_rates', [])
                        if entry['timestamp'] >= cutoff_time
                    ]
                    
                    avg_rate = 0
                    if rates:
                        avg_rate = statistics.mean(rates)
                    
                    # Add to comparison
                    result["comparison"][conn_type] = {
                        "bytes_received": conn_stats['bytes_received'],
                        "bytes_sent": conn_stats['bytes_sent'],
                        "operations_count": sum(conn_stats['operations'].values()),
                        "avg_transfer_rate": avg_rate,
                        "avg_transfer_rate_mbs": avg_rate / (1024 * 1024)
                    }
                
                # Calculate relative performance (compared to fastest)
                if len(result["comparison"]) > 1:
                    # Find fastest connection type
                    fastest_conn = max(
                        result["comparison"].items(),
                        key=lambda x: x[1]["avg_transfer_rate"]
                    )[0]
                    fastest_rate = result["comparison"][fastest_conn]["avg_transfer_rate"]
                    
                    # Calculate relative performance
                    if fastest_rate > 0:
                        for conn_type in result["comparison"]:
                            conn_rate = result["comparison"][conn_type]["avg_transfer_rate"]
                            relative_perf = conn_rate / fastest_rate
                            result["comparison"][conn_type]["relative_performance"] = relative_perf
                    
                    result["fastest_connection"] = fastest_conn
                
                return result
    
    def get_tier_stats(self, tier_name=None):
        """Get tier-specific performance statistics.
        
        Args:
            tier_name: Optional tier name to filter by
            
        Returns:
            Dictionary with tier statistics
        """
        if not self.enable_metrics:
            return {"metrics_disabled": True}
            
        with self.lock:
            if tier_name:
                # Stats for a specific tier
                if tier_name not in self.metrics.get('tiers', {}):
                    return {"tier": tier_name, "no_data": True}
                    
                return self.metrics['tiers'][tier_name].copy()
            else:
                # Stats for all tiers
                return {
                    name: stats.copy() 
                    for name, stats in self.metrics.get('tiers', {}).items()
                }
    
    def analyze_metrics(self):
        """Analyze collected metrics data to provide useful insights.
        
        Returns:
            Dictionary with metrics analysis results
        """
        if not self.enable_metrics:
            return {"metrics_disabled": True}
            
        with self.lock:
            analysis = {
                "latency_avg": {},
                "bandwidth_total": {
                    "inbound": 0,
                    "outbound": 0
                },
                "cache_hit_rate": self.metrics['cache']['hit_rate'],
                "tier_hit_rates": {},
                "recommendations": []
            }
            
            # Calculate average latencies
            for op, times in self.metrics['latency'].items():
                if times:
                    analysis["latency_avg"][op] = statistics.mean(times)
            
            # Calculate total bandwidth
            for entry in self.metrics['bandwidth']['inbound']:
                analysis["bandwidth_total"]["inbound"] += entry['size']
                
            for entry in self.metrics['bandwidth']['outbound']:
                analysis["bandwidth_total"]["outbound"] += entry['size']
            
            # Calculate tier hit rates
            for tier_name, tier_stats in self.metrics.get('tiers', {}).items():
                tier_total = tier_stats.get('hits', 0) + tier_stats.get('misses', 0)
                if tier_total > 0:
                    hit_rate = tier_stats.get('hits', 0) / tier_total
                    analysis["tier_hit_rates"][tier_name] = hit_rate
                    
            # Add connection performance metrics if available
            if 'connection_stats' in self.metrics:
                analysis["connection_performance"] = {}
                
                for conn_type, stats in self.metrics['connection_stats'].items():
                    rates = [entry['rate'] for entry in stats.get('transfer_rates', [])]
                    if rates:
                        analysis["connection_performance"][conn_type] = {
                            "avg_transfer_rate": statistics.mean(rates),
                            "bytes_transferred": stats['bytes_received'] + stats['bytes_sent'],
                            "operations_count": sum(stats['operations'].values())
                        }
                
                # Compare socket vs HTTP performance
                if 'unix_socket' in analysis["connection_performance"] and 'http' in analysis["connection_performance"]:
                    socket_rate = analysis["connection_performance"]['unix_socket']["avg_transfer_rate"]
                    http_rate = analysis["connection_performance"]['http']["avg_transfer_rate"]
                    
                    if socket_rate > 0 and http_rate > 0:
                        ratio = socket_rate / http_rate
                        analysis["unix_socket_performance"] = {
                            "http_ratio": ratio,
                            "percent_faster": (ratio - 1) * 100
                        }
            
            # Generate recommendations based on metrics
            if self.metrics['cache']['hit_rate'] < 0.5:
                analysis["recommendations"].append(
                    "Consider increasing cache sizes to improve hit rate"
                )
            
            # Look for imbalanced tier usage
            tier_hit_rates = list(analysis["tier_hit_rates"].values())
            if tier_hit_rates and len(tier_hit_rates) > 1 and statistics.stdev(tier_hit_rates) > 0.3:
                analysis["recommendations"].append(
                    "Consider rebalancing content across tiers for more even utilization"
                )
            
            # Check for slow operations
            slow_ops = []
            for op, avg_time in analysis["latency_avg"].items():
                if avg_time > 0.5:  # Operations taking more than 500ms
                    slow_ops.append(op)
                    
            if slow_ops:
                analysis["recommendations"].append(
                    f"Optimize slow operations: {', '.join(slow_ops)}"
                )
                
            # Add connection-specific recommendations
            if 'connection_performance' in analysis:
                if 'unix_socket' not in analysis['connection_performance'] and 'http' in analysis['connection_performance']:
                    analysis["recommendations"].append(
                        "Configure Unix socket support for better performance (2-3x faster than HTTP)"
                    )
                elif 'unix_socket' in analysis['connection_performance'] and 'http' in analysis['connection_performance']:
                    socket_rate = analysis["connection_performance"]['unix_socket']["avg_transfer_rate"]
                    http_rate = analysis["connection_performance"]['http']["avg_transfer_rate"]
                    
                    if socket_rate < http_rate:
                        analysis["recommendations"].append(
                            "Unix socket performing slower than HTTP - check socket configuration"
                        )
                
            return analysis
            
    def generate_connection_report(self, interval_seconds=3600):
        """Generate a detailed report comparing connection type performance.
        
        This report is specifically focused on analyzing the performance differences
        between Unix socket and HTTP API connections to help optimize configuration.
        
        Args:
            interval_seconds: Time period to analyze (default: last hour)
            
        Returns:
            Detailed report as multi-line string
        """
        if not self.enable_metrics:
            return "Performance metrics disabled"
            
        with self.lock:
            # Get connection stats for the time period
            conn_stats = self.get_connection_stats(interval_seconds=interval_seconds)
            
            # Check if we have enough data
            if conn_stats.get('no_data', False) or 'comparison' not in conn_stats:
                return "Insufficient connection data for comparison report"
                
            # Get bandwidth stats
            bandwidth_stats = self.get_bandwidth_stats(interval_seconds=interval_seconds)
            
            # Start building the report
            total_bytes = bandwidth_stats['inbound_total'] + bandwidth_stats['outbound_total']
            total_bytes_mb = total_bytes / (1024 * 1024)
            
            lines = [
                "IPFS Connection Performance Report",
                "=================================",
                f"Report period: Last {interval_seconds/3600:.1f} hours",
                f"Total data transferred: {total_bytes_mb:.2f} MB",
                ""
            ]
            
            # Add connection type comparison
            if 'comparison' in conn_stats:
                lines.append("Connection Type Performance Comparison:")
                lines.append("-----------------------------------------")
                
                # Get connection types in order of performance
                sorted_conns = sorted(
                    conn_stats['comparison'].items(),
                    key=lambda x: x[1].get('avg_transfer_rate', 0),
                    reverse=True
                )
                
                # Add a row for each connection type
                for conn_type, stats in sorted_conns:
                    transfer_rate = stats.get('avg_transfer_rate_mbs', 0)
                    relative_perf = stats.get('relative_performance', 1.0)
                    total_data = (stats['bytes_received'] + stats['bytes_sent']) / (1024 * 1024)
                    operation_count = stats['operations_count']
                    
                    lines.extend([
                        f"Connection Type: {conn_type.upper()}",
                        f"  Transfer Rate: {transfer_rate:.2f} MB/s",
                        f"  Relative Speed: {relative_perf:.2f}x" if 'relative_performance' in stats else "",
                        f"  Total Operations: {operation_count}",
                        f"  Total Data: {total_data:.2f} MB",
                        ""
                    ])
                    
            # Add Unix socket vs HTTP comparison
            socket_stats = conn_stats['comparison'].get('unix_socket')
            http_stats = conn_stats['comparison'].get('http')
            
            if socket_stats and http_stats:
                socket_rate = socket_stats.get('avg_transfer_rate', 0)
                http_rate = http_stats.get('avg_transfer_rate', 0)
                
                if socket_rate > 0 and http_rate > 0:
                    speedup = socket_rate / http_rate
                    
                    lines.extend([
                        "Unix Socket vs HTTP Performance:",
                        "---------------------------------",
                        f"Unix Socket: {socket_stats.get('avg_transfer_rate_mbs', 0):.2f} MB/s",
                        f"HTTP API: {http_stats.get('avg_transfer_rate_mbs', 0):.2f} MB/s",
                        f"Speedup: {speedup:.2f}x ({(speedup-1)*100:.1f}% faster)",
                        ""
                    ])
                    
                    # Detailed socket performance analysis
                    lines.extend([
                        "Socket Performance Analysis:",
                        f"  Operations: {socket_stats.get('operations_count', 0)} (vs. {http_stats.get('operations_count', 0)} for HTTP)",
                        f"  Data Received: {socket_stats.get('bytes_received', 0) / (1024*1024):.2f} MB",
                        f"  Data Sent: {socket_stats.get('bytes_sent', 0) / (1024*1024):.2f} MB",
                        ""
                    ])
                    
                    # Add best connection recommendation
                    if socket_rate > http_rate:
                        lines.extend([
                            "Recommendation: Continue using Unix socket for optimal performance.",
                            f"Unix socket is {speedup:.2f}x faster than HTTP API."
                        ])
                    else:
                        lines.extend([
                            "Recommendation: Investigate Unix socket configuration.",
                            "HTTP API is currently outperforming Unix socket, which is unusual.",
                            "Check socket permissions, path, and daemon configuration."
                        ])
            
            return "\n".join(lines)
    
    def reset_metrics(self):
        """Reset all metrics to initial state."""
        with self.lock:
            # Reset operation metrics
            self.operation_times.clear()
            self.operation_counts.clear()
            
            # Reset cache stats
            self.cache_stats = {
                "memory_hits": 0,
                "disk_hits": 0,
                "misses": 0,
                "total": 0
            }
            
            # Reset advanced metrics
            self.metrics = {
                'latency': {},
                'bandwidth': {
                    'inbound': [],
                    'outbound': []
                },
                'cache': {
                    'hits': 0,
                    'misses': 0,
                    'hit_rate': 0.0
                },
                'tiers': {}
            }
            
            # Reset time series
            self.time_series = {
                'timestamps': [],
                'latency_avg': {},
                'bandwidth': {
                    'inbound': [],
                    'outbound': []
                },
                'cache_hit_rate': []
            }
            
    def _percentile(self, data, percentile):
        """Calculate a percentile value from a list of data points.
        
        Args:
            data: List of numeric values
            percentile: Percentile to calculate (0-100)
            
        Returns:
            Percentile value
        """
        data = sorted(data)
        k = (len(data) - 1) * (percentile / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        
        if f == c:
            return data[int(k)]
        
        d0 = data[int(f)] * (c - k)
        d1 = data[int(c)] * (k - f)
        return d0 + d1
    
    def get_time_series_data(self, metric_type, operation=None, interval=None):
        """Get time series data for a specific metric type.
        
        Args:
            metric_type: Type of metric ('latency', 'bandwidth', 'cache_hit_rate')
            operation: Optional operation name for latency data
            interval: Optional time interval to filter by (in seconds)
            
        Returns:
            Dictionary with time series data
        """
        if not self.enable_metrics:
            return {"metrics_disabled": True}
            
        with self.lock:
            result = {'timestamps': []}
            
            # Filter by time interval if specified
            if interval:
                cutoff_time = time.time() - interval
                indices = [i for i, ts in enumerate(self.time_series['timestamps']) if ts >= cutoff_time]
                result['timestamps'] = [self.time_series['timestamps'][i] for i in indices]
            else:
                result['timestamps'] = self.time_series['timestamps'].copy()
            
            if not result['timestamps']:
                return {'no_data': True}
                
            if metric_type == 'latency':
                if operation:
                    if operation in self.time_series['latency_avg']:
                        values = self.time_series['latency_avg'][operation]
                        if interval:
                            values = [values[i] for i in indices]
                        result['values'] = values
                else:
                    result['operations'] = {}
                    for op, values in self.time_series['latency_avg'].items():
                        if interval:
                            values = [values[i] for i in indices if i < len(values)]
                        result['operations'][op] = values
                    
            elif metric_type == 'bandwidth':
                result['inbound'] = self.time_series['bandwidth']['inbound'].copy()
                result['outbound'] = self.time_series['bandwidth']['outbound'].copy()
                if interval:
                    result['inbound'] = [result['inbound'][i] for i in indices if i < len(result['inbound'])]
                    result['outbound'] = [result['outbound'][i] for i in indices if i < len(result['outbound'])]
                    
            elif metric_type == 'cache_hit_rate':
                values = self.time_series['cache_hit_rate'].copy()
                if interval:
                    values = [values[i] for i in indices if i < len(values)]
                result['values'] = values
                
            return result
            
    def __str__(self):
        """Get a string representation of current metrics."""
        if not self.enable_metrics:
            return "Performance metrics disabled"
            
        with self.lock:
            cache_stats = self.get_cache_stats()
            op_counts = dict(self.operation_counts)
            bandwidth_stats = self.get_bandwidth_stats(3600)  # Last hour
            connection_stats = self.get_connection_stats(interval_seconds=3600)  # Last hour
            
            lines = [
                "IPFS Filesystem Performance Metrics:",
                "------------------------------------",
                f"Total operations: {sum(op_counts.values())}",
                f"Operations by type: {dict(op_counts)}",
                "",
                "Cache Statistics:",
                f"  Memory hits: {cache_stats['memory_hits']}",
                f"  Disk hits: {cache_stats['disk_hits']}",
                f"  Misses: {cache_stats['misses']}",
                f"  Total accesses: {cache_stats['total']}",
            ]
            
            if cache_stats["total"] > 0:
                lines.extend([
                    f"  Memory hit rate: {cache_stats['memory_hit_rate']:.2%}",
                    f"  Disk hit rate: {cache_stats['disk_hit_rate']:.2%}",
                    f"  Overall hit rate: {cache_stats['overall_hit_rate']:.2%}",
                    f"  Miss rate: {cache_stats['miss_rate']:.2%}",
                ])
                
            # Add bandwidth information
            lines.extend([
                "",
                "Bandwidth Statistics (Last Hour):",
                f"  Inbound: {bandwidth_stats['inbound_total'] / 1024 / 1024:.2f} MB",
                f"  Outbound: {bandwidth_stats['outbound_total'] / 1024 / 1024:.2f} MB",
                f"  Inbound rate: {bandwidth_stats['inbound_rate'] / 1024:.2f} KB/s",
                f"  Outbound rate: {bandwidth_stats['outbound_rate'] / 1024:.2f} KB/s",
            ])
            
            # Add connection-specific information
            if not connection_stats.get('no_data') and 'comparison' in connection_stats:
                lines.extend([
                    "",
                    "Connection Performance (Last Hour):"
                ])
                
                # Add comparison information if available
                if connection_stats.get('fastest_connection'):
                    lines.append(f"  Fastest connection: {connection_stats['fastest_connection']}")
                
                # Add details for each connection type
                for conn_type, stats in connection_stats['comparison'].items():
                    transfer_rate = stats.get('avg_transfer_rate_mbs', 0)
                    relative_perf = stats.get('relative_performance', 1.0)
                    
                    lines.extend([
                        f"  {conn_type.upper()}:",
                        f"    Transfer rate: {transfer_rate:.2f} MB/s",
                        f"    Data received: {stats['bytes_received'] / 1024 / 1024:.2f} MB",
                        f"    Operations: {stats['operations_count']}",
                    ])
                    
                    if 'relative_performance' in stats:
                        lines.append(f"    Relative speed: {relative_perf:.2f}x")
                        
                    lines.append("")  # Add blank line between connection types
            
            # Add tier-specific information
            tier_stats = self.get_tier_stats()
            if tier_stats and not isinstance(tier_stats, dict) or not tier_stats.get('metrics_disabled'):
                lines.extend([
                    "",
                    "Tier Statistics:"
                ])
                
                for tier_name, stats in tier_stats.items():
                    hit_rate = 0
                    hits = stats.get('hits', 0)
                    misses = stats.get('misses', 0)
                    if hits + misses > 0:
                        hit_rate = hits / (hits + misses)
                        
                    lines.extend([
                        f"  {tier_name}:",
                        f"    Hits: {hits}",
                        f"    Misses: {misses}",
                        f"    Hit rate: {hit_rate:.2%}"
                    ])
            
            return "\n".join(lines)


class IPFSMappedFile:
    """Memory-mapped file for IPFS content.
    
    This provides efficient random access to large files by using the OS
    memory-mapping facilities. Memory-mapped files offer several advantages:
    
    1. Zero-copy reading: The OS handles file-to-memory mapping efficiently
    2. Lazy loading: Only requested parts of the file are loaded into memory
    3. Shared memory: Multiple processes can share the same memory-mapped file
    4. Random access: Efficient seeking and reading from arbitrary positions
    5. System cache utilization: Benefits from the OS page cache
    
    This implementation includes resource tracking and proper cleanup to prevent
    memory and file descriptor leaks.
    """
    
    def __init__(self, fs, path, mmap_obj, temp_path, mode="rb", file_descriptor=None):
        """Initialize the memory-mapped file.
        
        Args:
            fs: The filesystem object
            path: Path/CID of the file
            mmap_obj: The memory-mapped object
            temp_path: Path to the temporary file
            mode: File mode (only 'rb' supported)
            file_descriptor: Optional file descriptor to track for cleanup
        """
        self.fs = fs
        self.path = path
        self.mmap = mmap_obj
        self.temp_path = temp_path
        self.mode = mode
        self.size = self.mmap.size()
        self.closed = False
        self.pos = 0
        self.file_descriptor = file_descriptor
        self.last_access_time = time.time()
        self.access_count = 0
        
        # Register with resource tracker if available
        if hasattr(fs, '_resource_tracker'):
            fs._resource_tracker.register_mmap(self)
            
        # Log creation for debugging
        if hasattr(fs, 'logger'):
            fs.logger.debug(
                f"Created memory-mapped file for {path}: "
                f"{self.size/1024/1024:.2f}MB at {self.temp_path}"
            )
        
    def __repr__(self):
        return f"<IPFSMappedFile {self.path} {self.mode} size={self.size/1024/1024:.2f}MB>"
        
    def read(self, size=-1):
        """Read data from the file.
        
        Args:
            size: Maximum number of bytes to read, or -1 for all
            
        Returns:
            The bytes read
        """
        if self.closed:
            raise ValueError("I/O operation on closed file")
            
        # Update access statistics
        self.last_access_time = time.time()
        self.access_count += 1
            
        if size == -1:
            size = self.size - self.pos
            
        # Ensure we don't read past the end of the file
        size = min(size, self.size - self.pos)
        if size <= 0:
            return b''
            
        try:
            data = self.mmap[self.pos:self.pos + size]
            self.pos += len(data)
            return data
        except (ValueError, IndexError) as e:
            if hasattr(self.fs, 'logger'):
                self.fs.logger.error(
                    f"Error reading from memory-mapped file {self.path}: {str(e)} "
                    f"(pos={self.pos}, size={size}, mmap_size={self.size})"
                )
            raise
        
    def read_direct(self, offset, size):
        """Read directly from a specific position without changing the file pointer.
        
        This is useful for random access patterns where you need to read from
        various parts of the file without changing the current position.
        
        Args:
            offset: The offset in bytes from the start of the file
            size: Number of bytes to read
            
        Returns:
            The bytes read
        """
        if self.closed:
            raise ValueError("I/O operation on closed file")
            
        # Update access statistics
        self.last_access_time = time.time()
        self.access_count += 1
        
        # Ensure bounds are valid
        if offset < 0 or offset >= self.size:
            return b''
            
        # Adjust size if needed
        size = min(size, self.size - offset)
        if size <= 0:
            return b''
            
        # Read from the specified position
        return self.mmap[offset:offset + size]
        
    def seek(self, offset, whence=0):
        """Change the file position.
        
        Args:
            offset: The offset in bytes
            whence: 0=start, 1=current position, 2=end
            
        Returns:
            The new position
        """
        if self.closed:
            raise ValueError("I/O operation on closed file")
            
        # Track access for resource management
        self.last_access_time = time.time()
        
        # Calculate new position
        if whence == 0:  # Start
            new_pos = offset
        elif whence == 1:  # Current
            new_pos = self.pos + offset
        elif whence == 2:  # End
            new_pos = self.size + offset
        else:
            raise ValueError(f"Invalid whence value: {whence}")
        
        # Ensure position is within bounds
        self.pos = max(0, min(new_pos, self.size))
        return self.pos
        
    def tell(self):
        """Get the current file position.
        
        Returns:
            The current position in bytes
        """
        if self.closed:
            raise ValueError("I/O operation on closed file")
        return self.pos
        
    def close(self):
        """Close the file and release resources."""
        if not self.closed:
            try:
                # Close memory map
                if hasattr(self, 'mmap') and self.mmap:
                    self.mmap.close()
                    self.mmap = None
                
                # Close file descriptor if we're tracking it
                if hasattr(self, 'file_descriptor') and self.file_descriptor is not None:
                    try:
                        os.close(self.file_descriptor)
                    except OSError:
                        pass
                    self.file_descriptor = None
                
                # Remove temporary file
                if hasattr(self, 'temp_path') and self.temp_path:
                    try:
                        os.unlink(self.temp_path)
                    except OSError:
                        pass
                    self.temp_path = None
                
                # Log closure if logger available
                if hasattr(self.fs, 'logger'):
                    self.fs.logger.debug(f"Closed memory-mapped file for {self.path}")
                
                # Unregister from resource tracker
                if hasattr(self.fs, '_resource_tracker'):
                    self.fs._resource_tracker.unregister_mmap(self)
                    
            except Exception as e:
                # Log error but continue cleanup
                if hasattr(self.fs, 'logger'):
                    self.fs.logger.error(f"Error closing memory-mapped file {self.path}: {str(e)}")
            
            finally:
                self.closed = True
                
                # Remove from filesystem's open files set if possible
                if hasattr(self.fs, '_open_files') and self in self.fs._open_files:
                    self.fs._open_files.remove(self)
            
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def __del__(self):
        """Ensure resources are released when object is garbage collected."""
        self.close()
        
    def readable(self):
        """Check if the file is readable."""
        return not self.closed
        
    def seekable(self):
        """Check if the file supports seeking."""
        return not self.closed
        
    def get_access_stats(self):
        """Get access statistics for the file.
        
        Returns:
            Dictionary with access statistics
        """
        return {
            "path": self.path,
            "size": self.size,
            "access_count": self.access_count,
            "last_access_time": self.last_access_time,
            "age": time.time() - self.last_access_time,
            "temp_path": self.temp_path
        }
        
    def writable(self):
        return False
        
    def seekable(self):
        return True

class IPFSFileSystem(AbstractFileSystem):
    """FSSpec-compatible filesystem interface with tiered caching."""
    
    protocol = "ipfs"
    
    def __init__(self, 
                 ipfs_path=None, 
                 socket_path=None, 
                 role="leecher", 
                 cache_config=None, 
                 use_mmap=True,
                 enable_metrics=True,
                 metrics_config=None,
                 gateway_urls=None,
                 gateway_only=False,
                 use_gateway_fallback=False,
                 **kwargs):
        """Initialize a high-performance IPFS filesystem interface.
        
        Args:
            ipfs_path: Path to IPFS config directory
            socket_path: Path to Unix socket (for high-performance on Linux)
            role: Node role ("master", "worker", "leecher")
            cache_config: Configuration for the tiered cache system
            use_mmap: Whether to use memory-mapped files for large content
            enable_metrics: Whether to collect performance metrics
            metrics_config: Configuration for metrics collection and analysis
            gateway_urls: List of IPFS gateway URLs to use (e.g. ["https://ipfs.io/ipfs/"])
            gateway_only: If True, only use gateways (ignore local daemon)
            use_gateway_fallback: If True, try gateways if local daemon fails
            **kwargs: Additional arguments passed to AbstractFileSystem
        """
        if not FSSPEC_AVAILABLE:
            raise ImportError("fsspec is required for IPFSFileSystem")
            
        # Initialize the parent class
        super().__init__(**kwargs)
        
        # Set up basic attributes
        self.ipfs_path = ipfs_path or os.environ.get("IPFS_PATH", "~/.ipfs")
        self.ipfs_path = os.path.expanduser(self.ipfs_path)
        self.socket_path = socket_path
        self.role = role
        self.use_mmap = use_mmap
        
        # Gateway configuration
        self.gateway_urls = gateway_urls or []
        self.gateway_only = gateway_only
        self.use_gateway_fallback = use_gateway_fallback
        
        # Keep track of open files for cleanup
        self._open_files = set()
        
        # Generate a correlation ID for tracking operations
        self.correlation_id = str(uuid.uuid4())
        
        # Initialize logger
        self.logger = logging.getLogger(__name__ + ".IPFSFileSystem")
        
        # Initialize connection to IPFS
        self._setup_ipfs_connection()
        
        # Initialize performance metrics collection
        self.metrics = PerformanceMetrics(enable_metrics=enable_metrics, config=metrics_config)
        
        # Initialize tiered cache system with default configuration if not provided
        if not cache_config:
            cache_config = self._get_default_cache_config()
        
        self.cache_config = cache_config
        # Use enhanced cache implementation if available
        if ENHANCED_CACHE_AVAILABLE:
            # Add ARC-specific configurations if not present
            if cache_config and not cache_config.get('arc'):
                # Role-specific ARC configurations
                if self.role == "master":
                    # Master nodes focus on broad content coverage
                    cache_config['arc'] = {
                        'ghost_list_size': 2048,  # Larger ghost lists for better adaptation
                        'initial_p': 0,  # Completely adaptive
                        'max_p_percent': 0.7,  # Bias more toward T1 (recency) for diverse content
                        'frequency_weight': 0.6,  # Slightly less focus on frequency
                        'recency_weight': 0.4,  # More emphasis on recency for diverse workloads
                        'heat_decay_hours': 2.0,  # Slower decay for more stable content value
                        'access_boost': 1.5,  # Moderate boost for recent access
                        'enable_stats': True,  # Collect performance statistics
                    }
                elif self.role == "worker":
                    # Worker nodes focus on efficient processing
                    cache_config['arc'] = {
                        'ghost_list_size': 1536,  # Medium ghost lists
                        'initial_p': 0,  # Start adaptive
                        'max_p_percent': 0.5,  # Balanced between recency and frequency
                        'frequency_weight': 0.7,  # More weight on frequency for predictable workloads
                        'recency_weight': 0.3,  # Less emphasis on recency
                        'heat_decay_hours': 1.0,  # Standard decay
                        'access_boost': 2.0,  # Strong boost for working set
                        'enable_stats': True,  # Collect performance statistics
                    }
                else:  # leecher
                    # Leecher nodes optimize for small datasets and bursts
                    cache_config['arc'] = {
                        'ghost_list_size': 1024,  # Standard ghost lists
                        'initial_p': 0,  # Start adaptive
                        'max_p_percent': 0.3,  # Bias toward T2 (frequency) for common content
                        'frequency_weight': 0.8,  # Heavy focus on frequency for repeated access
                        'recency_weight': 0.2,  # Less emphasis on recency
                        'heat_decay_hours': 0.5,  # Fast decay for quickly changing workloads
                        'access_boost': 3.0,  # Strong boost for very recent access
                        'enable_stats': True,  # Collect performance statistics
                    }
                self.logger.info("Added enhanced ARC configuration to cache config")
                
            self.logger.info("Using enhanced ARC cache implementation with ghost lists")
            # Enhanced ARCache with full ARC algorithm and ghost lists
            self.cache = TieredCacheManager(config=cache_config)
        else:
            self.logger.warning("Using legacy cache implementation - for best performance, install with enhanced cache support")
            # Legacy implementation (for backward compatibility)
            self.cache = TieredCacheManager(config=cache_config)
        
        # Initialize additional tier management
        self._setup_tier_management()
     
    def _setup_ipfs_connection(self):
        """Set up the appropriate IPFS connection based on available interfaces.
        
        This method configures the optimal connection to the IPFS API:
        1. Unix socket (fastest, lowest latency, Linux/macOS only)
        2. Localhost HTTP API (standard option)
        3. Gateway fallback (if configured)
        
        Unix socket provides ~2-3x performance improvement over HTTP for local operations.
        """
        # Keep track of connection type for metrics
        self.connection_type = "http"
        self.connection_details = {}
        
        # Check if we should use gateway only mode
        if self.gateway_only:
            self.api_base = None
            self.session = requests.Session()
            self.connection_type = "gateway"
            self.logger.info("Using gateway-only mode for IPFS access")
            return

        # Try to find the socket path if not explicitly provided
        if not self.socket_path:
            self.socket_path = self._detect_socket_path()
            
        # Prefer Unix socket on Linux/macOS for performance
        if self.socket_path and os.path.exists(self.socket_path):
            if not UNIX_SOCKET_AVAILABLE:
                self.logger.warning(
                    "Unix socket available at %s but requests_unixsocket not installed. "
                    "Using HTTP API instead. For better performance, install the "
                    "requests_unixsocket package with: pip install requests_unixsocket", 
                    self.socket_path
                )
                self.api_base = "http://127.0.0.1:5001/api/v0"
                self.session = requests.Session()
            else:
                # Clean the socket path to ensure proper URL formatting
                socket_path_cleaned = self.socket_path
                # Remove leading slash for proper URL formatting
                if socket_path_cleaned.startswith('/'):
                    socket_path_cleaned = socket_path_cleaned[1:]
                # Encode path for URL safety
                import urllib.parse
                socket_path_encoded = urllib.parse.quote_plus(socket_path_cleaned)
                
                # Use consistent socket path format throughout the codebase
                self.api_base = f"http+unix://{socket_path_encoded}/api/v0"
                self.session = requests.Session()
                self.session.mount("http+unix://", requests_unixsocket.UnixAdapter())
                self.connection_type = "unix_socket"
                self.connection_details = {"socket_path": self.socket_path}
                self.logger.info("Using Unix socket for high-performance IPFS API access: %s", self.socket_path)
                
                # Verify connection works
                try:
                    response = self.session.post(f"{self.api_base}/id")
                    if response.status_code != 200:
                        self.logger.warning(
                            "Unix socket connection test failed with status %d. "
                            "Falling back to HTTP API", 
                            response.status_code
                        )
                        self.api_base = "http://127.0.0.1:5001/api/v0"
                        self.session = requests.Session()
                        self.connection_type = "http"
                except Exception as e:
                    self.logger.warning(
                        "Unix socket connection test failed: %s. "
                        "Falling back to HTTP API", 
                        str(e)
                    )
                    self.api_base = "http://127.0.0.1:5001/api/v0"
                    self.session = requests.Session()
                    self.connection_type = "http"
        else:
            # Fall back to HTTP API
            self.api_base = "http://127.0.0.1:5001/api/v0"
            self.session = requests.Session()
            self.logger.info("Using HTTP API for IPFS access (no Unix socket available)")
            
    def _detect_socket_path(self):
        """Detect the IPFS API Unix socket path on the system.
        
        Returns:
            Detected socket path or None if not found
        """
        # Common socket paths to check
        common_paths = [
            # Default kubo socket path
            os.path.join(self.ipfs_path, "api"),
            # Alternative paths
            os.path.join(self.ipfs_path, "api.sock"),
            os.path.join(self.ipfs_path, "ipfs.sock"),
            # System-wide paths
            "/var/run/ipfs/api",
            "/var/run/ipfs.sock",
            "/var/run/ipfs/ipfs.sock",
            # Snap package path
            "/run/snap.ipfs/ipfs.sock"
        ]
        
        # Check if any of these paths exist
        for path in common_paths:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                self.logger.debug("Detected IPFS Unix socket at: %s", expanded_path)
                return expanded_path
        
        # Check if API config specifies a Unix socket
        api_file = os.path.join(self.ipfs_path, "api")
        if os.path.exists(api_file):
            try:
                with open(api_file, 'r') as f:
                    api_multiaddr = f.read().strip()
                    # Check if it's a Unix socket address
                    if api_multiaddr.startswith('/unix/'):
                        socket_path = api_multiaddr.replace('/unix/', '')
                        if os.path.exists(socket_path):
                            self.logger.debug("Found Unix socket from API file: %s", socket_path)
                            return socket_path
            except (IOError, OSError) as e:
                self.logger.debug("Failed to read API file: %s", str(e))
                
        return None
            
    def _get_default_cache_config(self):
        """Get default configuration for cache tiers based on role.
        
        Returns:
            Dictionary with default cache configuration
        """
        config = {
            'memory_cache_size': 100 * 1024 * 1024,  # 100MB
            'local_cache_size': 1 * 1024 * 1024 * 1024,  # 1GB
            'local_cache_path': os.path.expanduser('~/.ipfs_cache'),
            'max_item_size': 50 * 1024 * 1024,  # 50MB
            'min_access_count': 2,
            'promotion_threshold': 3,  # Access count for promotion
            'demotion_threshold': 30,  # Days inactive for demotion
            'replication_policy': 'high_value',  # Replicate items with high heat score
            'default_tier': 'memory',
            'tiers': {}
        }
        
        # Configure role-specific tiers
        if self.role == "master":
            # Master role has more storage and sophisticated tiers
            config['tiers'] = {
                'memory': {
                    'type': 'memory',
                    'size': 200 * 1024 * 1024,  # 200MB
                    'priority': 1
                },
                'disk': {
                    'type': 'disk',
                    'size': 10 * 1024 * 1024 * 1024,  # 10GB
                    'path': os.path.expanduser('~/.ipfs_cache/disk'),
                    'priority': 2
                },
                'ipfs_local': {
                    'type': 'ipfs',
                    'node_type': 'local',
                    'priority': 3
                },
                'ipfs_cluster': {
                    'type': 'ipfs_cluster',
                    'priority': 4
                }
            }
        elif self.role == "worker":
            # Worker has moderate storage capacity
            config['tiers'] = {
                'memory': {
                    'type': 'memory',
                    'size': 100 * 1024 * 1024,  # 100MB
                    'priority': 1
                },
                'disk': {
                    'type': 'disk',
                    'size': 5 * 1024 * 1024 * 1024,  # 5GB
                    'path': os.path.expanduser('~/.ipfs_cache/disk'),
                    'priority': 2
                },
                'ipfs_local': {
                    'type': 'ipfs',
                    'node_type': 'local',
                    'priority': 3
                }
            }
        else:  # leecher
            # Leecher has minimal storage for efficiency
            config['tiers'] = {
                'memory': {
                    'type': 'memory',
                    'size': 50 * 1024 * 1024,  # 50MB
                    'priority': 1
                },
                'disk': {
                    'type': 'disk',
                    'size': 1 * 1024 * 1024 * 1024,  # 1GB
                    'path': os.path.expanduser('~/.ipfs_cache/disk'),
                    'priority': 2
                }
            }
            
        return config
        
    def _setup_tier_management(self):
        """Set up the hierarchical storage management based on configuration."""
        # Set up tier ordering by priority
        self.tier_order = []
        
        if hasattr(self.cache, 'tiers') and self.cache.tiers:
            # Sort tiers by priority (lower number = higher priority)
            self.tier_order = sorted(
                self.cache.tiers.keys(),
                key=lambda k: self.cache.tiers[k].get('priority', 999)
            )
            
            # Initialize tier statistics
            self.tier_stats = {
                tier: {
                    'access_count': 0,
                    'hit_rate': 0.0,
                    'total_size': 0,
                    'item_count': 0,
                    'last_health_check': 0
                } for tier in self.tier_order
            }
            
            # Set default tier
            self.default_tier = self.cache_config.get('default_tier', self.tier_order[0] if self.tier_order else 'memory')
            
            # Start health check and maintenance threads if we have multiple tiers
            if len(self.tier_order) > 1:
                self._start_tier_maintenance()
        else:
            # Basic two-tier system
            self.tier_order = ['memory', 'disk']
            self.default_tier = 'memory'
            self.tier_stats = {
                'memory': {'access_count': 0, 'hit_rate': 0.0, 'total_size': 0, 'item_count': 0},
                'disk': {'access_count': 0, 'hit_rate': 0.0, 'total_size': 0, 'item_count': 0}
            }
            
    def _start_tier_maintenance(self):
        """Start background maintenance for hierarchical storage tiers."""
        # Check for demotions every hour
        maintenance_thread = threading.Thread(
            target=self._maintenance_worker,
            daemon=True
        )
        maintenance_thread.start()
            
    def _maintenance_worker(self):
        """Background worker for tier maintenance tasks."""
        while True:
            try:
                # Check tier health
                for tier_name in self.tier_order:
                    self._check_tier_health(tier_name)
                
                # Check for content to demote
                self._check_for_demotions()
                
                # Check replication policies
                self._apply_replication_policies()
                
                # Verify content integrity periodically
                if hasattr(self, '_content_integrity_check_interval'):
                    self._verify_all_content_integrity()
                
            except Exception as e:
                self.logger.error(f"Error in tier maintenance worker: {str(e)}")
                
            # Sleep before next maintenance cycle
            time.sleep(3600)  # 1 hour
            
    def _migrate_to_tier(self, cid: str, source_tier: str, target_tier: str) -> Dict[str, Any]:
        """Migrate content from one storage tier to another.
        
        Args:
            cid: Content identifier to migrate
            source_tier: Current tier name
            target_tier: Target tier name
            
        Returns:
            Dictionary with migration results
        """
        self.logger.info(f"Migrating {cid} from {source_tier} to {target_tier}")
        
        result = {
            "success": False,
            "cid": cid,
            "source_tier": source_tier,
            "target_tier": target_tier,
            "timestamp": time.time()
        }
        
        try:
            # Get content from source tier
            data = self._get_from_tier(cid, source_tier)
            if data is None:
                result["error"] = f"Content not found in {source_tier} tier"
                return result
                
            # Store in target tier
            put_result = self._put_in_tier(cid, data, target_tier)
            if not put_result.get("success", False):
                result["error"] = put_result.get("error", "Unknown error storing in target tier")
                return result
                
            # Update metadata to reflect new tier
            metadata = self.cache.get_metadata(cid) or {}
            metadata["current_tier"] = target_tier
            metadata["migration_history"] = metadata.get("migration_history", [])
            metadata["migration_history"].append({
                "from": source_tier,
                "to": target_tier,
                "timestamp": time.time()
            })
            self.cache._update_content_metadata(cid, metadata)
            
            # Update metrics
            if self.metrics:
                self.metrics.record_event(
                    event_type="migration",
                    data={
                        "cid": cid,
                        "size": len(data),
                        "source_tier": source_tier,
                        "target_tier": target_tier
                    }
                )
                
            result["success"] = True
            
        except Exception as e:
            self.logger.error(f"Error migrating content: {str(e)}")
            result["error"] = str(e)
            
        return result
        
    def _get_from_tier(self, cid: str, tier_name: str) -> Optional[bytes]:
        """Get content from a specific storage tier.
        
        Args:
            cid: Content identifier
            tier_name: Tier name to retrieve from
            
        Returns:
            Content data or None if not found
        """
        if not hasattr(self.cache, 'tiers') or tier_name not in self.cache.tiers:
            self.logger.warning(f"Tier {tier_name} not found")
            return None
            
        tier = self.cache.tiers[tier_name]
        tier_type = tier.get('type')
        
        try:
            if tier_type == 'memory':
                # Get from memory cache
                return tier['cache'].get(cid)
                
            elif tier_type == 'disk':
                # Get from disk cache
                return tier['cache'].get(cid)
                
            elif tier_type == 'ipfs' or tier_type == 'ipfs_local':
                # Get from local IPFS daemon
                response = self.session.post(
                    f"{self.api_base}/cat", 
                    params={"arg": cid}
                )
                if response.status_code == 200:
                    return response.content
                    
            elif tier_type == 'ipfs_cluster':
                # Get from IPFS cluster
                # This typically goes through the same IPFS daemon interface
                # but we'd check cluster allocation first
                response = self.session.post(
                    f"{self.api_base}/cat", 
                    params={"arg": cid}
                )
                if response.status_code == 200:
                    return response.content
                    
            else:
                self.logger.warning(f"Unsupported tier type: {tier_type}")
                
        except Exception as e:
            self.logger.error(f"Error retrieving from tier {tier_name}: {str(e)}")
            
        return None
        
    def _put_in_tier(self, cid: str, data: bytes, tier_name: str) -> Dict[str, Any]:
        """Store content in a specific storage tier.
        
        Args:
            cid: Content identifier
            data: Content data
            tier_name: Target tier name
            
        Returns:
            Dictionary with results
        """
        result = {
            "success": False,
            "cid": cid,
            "tier": tier_name,
            "timestamp": time.time()
        }
        
        if not hasattr(self.cache, 'tiers') or tier_name not in self.cache.tiers:
            result["error"] = f"Tier {tier_name} not found"
            return result
            
        tier = self.cache.tiers[tier_name]
        tier_type = tier.get('type')
        
        try:
            if tier_type == 'memory':
                # Store in memory cache
                tier['cache'].put(cid, data)
                result["success"] = True
                
            elif tier_type == 'disk':
                # Store in disk cache with metadata
                metadata = {
                    "cid": cid,
                    "size": len(data),
                    "current_tier": tier_name,
                    "added_time": time.time()
                }
                tier['cache'].put(cid, data, metadata)
                result["success"] = True
                
            elif tier_type == 'ipfs' or tier_type == 'ipfs_local':
                # Add to local IPFS daemon
                # Use ipfs.add() implementation to add the content
                # For simplicity in this example, we'll just ensure it's pinned
                response = self.session.post(
                    f"{self.api_base}/pin/add", 
                    params={"arg": cid}
                )
                if response.status_code == 200:
                    result["success"] = True
                else:
                    result["error"] = f"Failed to pin content in IPFS: {response.text}"
                    
            elif tier_type == 'ipfs_cluster':
                # Add to IPFS cluster
                # This would typically use the cluster API to pin across the cluster
                # For simplicity, we'll use a direct IPFS pin in this example
                response = self.session.post(
                    f"{self.api_base}/pin/add", 
                    params={"arg": cid}
                )
                if response.status_code == 200:
                    result["success"] = True
                else:
                    result["error"] = f"Failed to pin content in IPFS: {response.text}"
                
            else:
                result["error"] = f"Unsupported tier type: {tier_type}"
                
        except Exception as e:
            self.logger.error(f"Error storing in tier {tier_name}: {str(e)}")
            result["error"] = str(e)
            
        return result
        
    def _check_for_promotions(self, cid: str) -> None:
        """Check if content should be promoted to a higher tier.
        
        Args:
            cid: Content identifier to check
        """
        current_tier = self._get_content_tier(cid)
        if not current_tier:
            return
            
        # Get content heat score
        heat_score = self.cache.get_heat_score(cid)
        
        # Get access count
        metadata = self.cache.get_metadata(cid) or {}
        access_count = metadata.get('access_count', 0)
        
        # Check if we should promote based on access count
        promotion_threshold = self.cache_config.get('promotion_threshold', 3)
        
        if access_count >= promotion_threshold:
            # Find a higher priority tier
            current_tier_index = self.tier_order.index(current_tier) if current_tier in self.tier_order else -1
            
            if current_tier_index > 0:  # There's a higher priority tier available
                target_tier = self.tier_order[current_tier_index - 1]
                self._migrate_to_tier(cid, current_tier, target_tier)
                
    def _check_for_demotions(self) -> None:
        """Check all content for possible demotion to lower tiers based on inactivity."""
        # Get all content metadata
        all_metadata = {}
        
        # If we have a metadata index, use it
        if hasattr(self.cache, 'content_metadata'):
            all_metadata = self.cache.content_metadata
        
        # Otherwise, scan each tier for metadata
        else:
            for tier_name in self.tier_order:
                tier = self.cache.tiers.get(tier_name)
                if tier and tier.get('type') == 'disk':
                    # Disk tiers have metadata
                    disk_cache = tier.get('cache')
                    if hasattr(disk_cache, 'metadata'):
                        all_metadata.update(disk_cache.metadata)
        
        # Calculate demotion threshold timestamp
        demotion_threshold_days = self.cache_config.get('demotion_threshold', 30)
        threshold_time = time.time() - (demotion_threshold_days * 24 * 3600)
        
        # Check each content item
        for cid, metadata in all_metadata.items():
            last_accessed = metadata.get('last_accessed', 0)
            current_tier = metadata.get('current_tier', self.default_tier)
            
            # If not accessed recently and not already in lowest tier
            if last_accessed < threshold_time:
                current_tier_index = self.tier_order.index(current_tier) if current_tier in self.tier_order else -1
                
                if current_tier_index >= 0 and current_tier_index < len(self.tier_order) - 1:
                    # There's a lower priority tier available
                    target_tier = self.tier_order[current_tier_index + 1]
                    self._migrate_to_tier(cid, current_tier, target_tier)
                    
    def _check_tier_health(self, tier_name: str) -> bool:
        """Check if a storage tier is healthy and available.
        
        Args:
            tier_name: Name of the tier to check
            
        Returns:
            Boolean indicating if tier is healthy
        """
        if not hasattr(self.cache, 'tiers') or tier_name not in self.cache.tiers:
            return False
            
        tier = self.cache.tiers.get(tier_name)
        tier_type = tier.get('type')
        
        try:
            # Update last health check timestamp
            self.tier_stats[tier_name]['last_health_check'] = time.time()
            
            if tier_type == 'memory':
                # Memory tier is always considered healthy if we can access it
                return True
                
            elif tier_type == 'disk':
                # Check if disk is accessible and has space
                disk_cache = tier.get('cache')
                if not disk_cache:
                    return False
                    
                # Check disk space
                try:
                    directory = disk_cache.directory
                    if not os.path.exists(directory):
                        os.makedirs(directory, exist_ok=True)
                        
                    # Check write access by creating a test file
                    test_file = os.path.join(directory, f"health_check_{uuid.uuid4()}.tmp")
                    with open(test_file, 'wb') as f:
                        f.write(b"health check")
                    os.remove(test_file)
                    return True
                except Exception as e:
                    self.logger.error(f"Disk tier health check failed: {str(e)}")
                    return False
                    
            elif tier_type == 'ipfs' or tier_type == 'ipfs_local':
                # Check IPFS daemon health by making a simple API call
                response = self.session.post(f"{self.api_base}/id")
                return response.status_code == 200
                
            elif tier_type == 'ipfs_cluster':
                # Check IPFS cluster health
                # In a real implementation, would check cluster status API
                response = self.session.post(f"{self.api_base}/id")
                return response.status_code == 200
                
            else:
                self.logger.warning(f"Unknown tier type for health check: {tier_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error checking tier health for {tier_name}: {str(e)}")
            return False
            
    def _get_content_tier(self, cid: str) -> Optional[str]:
        """Determine which tier currently contains the content.
        
        Args:
            cid: Content identifier
            
        Returns:
            Tier name or None if not found
        """
        # Check metadata first for quick lookup
        metadata = self.cache.get_metadata(cid)
        if metadata and 'current_tier' in metadata:
            return metadata['current_tier']
            
        # Otherwise, check each tier
        for tier_name in self.tier_order:
            tier = self.cache.tiers.get(tier_name)
            if not tier:
                continue
                
            tier_type = tier.get('type')
            
            if tier_type == 'memory' and 'cache' in tier:
                if tier['cache'].contains(cid):
                    return tier_name
                    
            elif tier_type == 'disk' and 'cache' in tier:
                if tier['cache'].contains(cid):
                    return tier_name
                    
            elif tier_type in ('ipfs', 'ipfs_local', 'ipfs_cluster'):
                # Check if pinned in IPFS
                try:
                    response = self.session.post(
                        f"{self.api_base}/pin/ls", 
                        params={"arg": cid}
                    )
                    if response.status_code == 200:
                        return tier_name
                except Exception:
                    pass
                    
        return None
        
    def _apply_replication_policies(self) -> None:
        """Apply content replication policies across tiers based on configuration."""
        replication_policy = self.cache_config.get('replication_policy', 'high_value')
        
        if replication_policy == 'none':
            return
            
        # Get all content metadata
        all_metadata = {}
        
        # If we have a metadata index, use it
        if hasattr(self.cache, 'content_metadata'):
            all_metadata = self.cache.content_metadata
        
        # For high_value policy, replicate important content across tiers
        if replication_policy == 'high_value':
            for cid, metadata in all_metadata.items():
                heat_score = metadata.get('heat_score', 0)
                
                # For very hot items, ensure they're in memory and replicated
                if heat_score > 10.0:  # Arbitrary threshold
                    # Ensure in memory tier
                    memory_tier = self.tier_order[0] if self.tier_order else 'memory'
                    self._ensure_in_tier(cid, memory_tier)
                    
                    # Also ensure in IPFS for resilience if we have an IPFS tier
                    ipfs_tiers = [t for t in self.tier_order if 
                                 self.cache.tiers.get(t, {}).get('type') in ('ipfs', 'ipfs_local', 'ipfs_cluster')]
                    if ipfs_tiers:
                        self._ensure_in_tier(cid, ipfs_tiers[0])
        
    def _ensure_in_tier(self, cid: str, tier_name: str) -> bool:
        """Ensure content is available in a specific tier.
        
        Args:
            cid: Content identifier
            tier_name: Target tier name
            
        Returns:
            Boolean indicating success
        """
        # First check if already in tier
        if self._is_in_tier(cid, tier_name):
            return True
            
        # Get content from any available tier
        for source_tier in self.tier_order:
            data = self._get_from_tier(cid, source_tier)
            if data:
                # Found content, put in target tier
                result = self._put_in_tier(cid, data, tier_name)
                return result.get('success', False)
                
        return False
    
    def _is_in_tier(self, cid: str, tier_name: str) -> bool:
        """Check if content is available in a specific tier.
        
        Args:
            cid: Content identifier
            tier_name: Tier name to check
            
        Returns:
            Boolean indicating if content is in tier
        """
        if not hasattr(self.cache, 'tiers') or tier_name not in self.cache.tiers:
            return False
            
        tier = self.cache.tiers.get(tier_name)
        tier_type = tier.get('type')
        
        try:
            if tier_type == 'memory' and 'cache' in tier:
                return tier['cache'].contains(cid)
                
            elif tier_type == 'disk' and 'cache' in tier:
                return tier['cache'].contains(cid)
                
            elif tier_type in ('ipfs', 'ipfs_local', 'ipfs_cluster'):
                # Check if pinned in IPFS
                response = self.session.post(
                    f"{self.api_base}/pin/ls", 
                    params={"arg": cid}
                )
                return response.status_code == 200
                
        except Exception as e:
            self.logger.debug(f"Error checking if {cid} is in tier {tier_name}: {str(e)}")
            
        return False
        
    def _check_replication_policy(self, cid: str, data: bytes) -> None:
        """Check replication policy for a specific content item.
        
        Args:
            cid: Content identifier
            data: Content data
        """
        policy = self.cache_config.get('replication_policy', 'high_value')
        
        if policy == 'none':
            return
            
        # Get heat score
        heat_score = self.cache.get_heat_score(cid)
        
        # For high_value policy, replicate hot content
        if policy == 'high_value' and heat_score > 5.0:
            # Replicate to higher durability tiers
            for tier_name in self.tier_order:
                tier = self.cache.tiers.get(tier_name)
                if not tier:
                    continue
                    
                # Skip memory tier as we're focusing on durable storage
                if tier.get('type') == 'memory':
                    continue
                    
                # Try to put in this tier for replication
                self._put_in_tier(cid, data, tier_name)
                
    def _compute_hash(self, data: bytes) -> str:
        """Compute a hash for content verification.
        
        Args:
            data: Content data
            
        Returns:
            Hash string
        """
        import hashlib
        return hashlib.sha256(data).hexdigest()
        
    def _verify_content_integrity(self, cid: str) -> Dict[str, Any]:
        """Verify content integrity across tiers.
        
        Args:
            cid: Content identifier
            
        Returns:
            Dictionary with verification results
        """
        result = {
            "success": True,
            "cid": cid,
            "timestamp": time.time(),
            "verified_tiers": 0,
            "corrupted_tiers": []
        }
        
        # Get content from first available tier
        reference_data = None
        reference_hash = None
        reference_tier = None
        
        for tier_name in self.tier_order:
            data = self._get_from_tier(cid, tier_name)
            if data:
                reference_data = data
                reference_hash = self._compute_hash(data)
                reference_tier = tier_name
                break
                
        if not reference_data:
            result["success"] = False
            result["error"] = "Content not found in any tier"
            return result
            
        # Now verify against all other tiers
        for tier_name in self.tier_order:
            if tier_name == reference_tier:
                # Already verified, this is our reference
                result["verified_tiers"] += 1
                continue
                
            data = self._get_from_tier(cid, tier_name)
            if not data:
                # Not in this tier
                continue
                
            # Compare hash
            tier_hash = self._compute_hash(data)
            if tier_hash != reference_hash:
                result["success"] = False
                result["corrupted_tiers"].append({
                    "tier": tier_name,
                    "expected_hash": reference_hash,
                    "actual_hash": tier_hash
                })
            else:
                result["verified_tiers"] += 1
                
        return result
        
    def _verify_all_content_integrity(self) -> Dict[str, Any]:
        """Verify integrity of all cached content across tiers.
        
        Returns:
            Summary dictionary with verification results
        """
        summary = {
            "success": True,
            "timestamp": time.time(),
            "total_verified": 0,
            "corrupted": []
        }
        
        # Get all content CIDs
        all_cids = set()
        
        # If we have a metadata index, use it
        if hasattr(self.cache, 'content_metadata'):
            all_cids.update(self.cache.content_metadata.keys())
        
        # Otherwise, scan each tier
        else:
            for tier_name in self.tier_order:
                tier = self.cache.tiers.get(tier_name)
                if not tier:
                    continue
                    
                tier_type = tier.get('type')
                
                if tier_type == 'disk' and 'cache' in tier:
                    disk_cache = tier.get('cache')
                    if hasattr(disk_cache, 'metadata'):
                        all_cids.update(disk_cache.metadata.keys())
        
        # Verify each CID
        for cid in all_cids:
            verification = self._verify_content_integrity(cid)
            summary["total_verified"] += 1
            
            if not verification["success"]:
                summary["success"] = False
                summary["corrupted"].append({
                    "cid": cid,
                    "corrupted_tiers": verification["corrupted_tiers"]
                })
                
        return summary
        
    def _path_to_cid(self, path):
        """Convert a path to a CID.
        
        Args:
            path: Path or CID string
            
        Returns:
            The CID extracted from the path
        """
        # If it's already a CID, return it
        if is_valid_cid(path):
            return path
            
        # Strip ipfs:// prefix if present
        if path.startswith("ipfs://"):
            path = path[7:]
            
        # Handle IPFS paths
        if path.startswith("/ipfs/"):
            parts = path.split("/")
            if len(parts) > 2 and is_valid_cid(parts[2]):
                return parts[2]
                
        # Last resort: assume the path is a CID
        return path
        
    def _fetch_from_ipfs(self, cid):
        """Fetch content from IPFS, with support for gateway fallback.
        
        This method optimizes content retrieval by:
        1. Using Unix socket if available (fastest local communication)
        2. Falling back to HTTP API if socket is not available
        3. Using configured gateways as last resort
        
        Args:
            cid: The Content Identifier
            
        Returns:
            The content as bytes
            
        Raises:
            IPFSContentNotFoundError: If content is not found
            IPFSConnectionError: If all connection methods fail
            IPFSTimeoutError: If operations timeout
        """
        # Skip local daemon if gateway_only is enabled
        if not self.gateway_only:
            fetch_start = time.time()
            
            try:
                # Attempt to fetch from local daemon
                connection_type = getattr(self, 'connection_type', 'http')
                
                # Log connection type for debugging
                self.logger.debug(f"Fetching {cid} via {connection_type} connection")
                
                # Optimize buffer size for Unix socket connections
                if connection_type == 'unix_socket':
                    # Unix sockets can handle larger buffers without TCP overhead
                    timeout = 60  # Longer timeout for large files
                    stream = True  # Stream the response for large files
                else:
                    timeout = 30
                    stream = False
                
                # Make the API request
                response = self.session.post(
                    f"{self.api_base}/cat",
                    params={"arg": cid},
                    timeout=timeout,
                    stream=stream
                )
                
                # Check for success
                if response.status_code == 200:
                    # Handle streaming response if enabled
                    if stream and response.headers.get('content-length') and int(response.headers.get('content-length', 0)) > 10 * 1024 * 1024:
                        # For large files, read in chunks to avoid memory issues
                        chunks = []
                        for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
                            if chunk:
                                chunks.append(chunk)
                        content = b''.join(chunks)
                    else:
                        # For smaller files, read all at once
                        content = response.content
                        
                    # Record performance metrics
                    fetch_elapsed = time.time() - fetch_start
                    if hasattr(self, 'metrics'):
                        metric_key = f'ipfs_fetch_{connection_type}'
                        self.metrics.record_operation_time(metric_key, fetch_elapsed)
                        
                        # Track data size for bandwidth metrics
                        if hasattr(self.metrics, 'record_data_transfer'):
                            self.metrics.record_data_transfer(
                                operation='fetch', 
                                bytes_transferred=len(content),
                                connection_type=connection_type
                            )
                    
                    # Log performance information
                    size_kb = len(content) / 1024
                    self.logger.debug(
                        f"Retrieved {cid} via {connection_type} in {fetch_elapsed:.3f}s ({size_kb:.1f}KB, "
                        f"{size_kb/fetch_elapsed:.1f}KB/s)"
                    )
                    
                    return content
                    
                # Handle error 
                error_msg = response.text
                if response.status_code == 404:
                    self.logger.debug(f"Content not found: {cid} via {connection_type}")
                    if not self.use_gateway_fallback:
                        raise IPFSContentNotFoundError(f"Content not found: {cid}")
                else:
                    self.logger.warning(
                        f"Failed to fetch content via {connection_type}: {error_msg}"
                    )
                    if not self.use_gateway_fallback:
                        raise IPFSError(f"Failed to fetch content: {error_msg}")
                        
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                error_type = "timeout" if isinstance(e, requests.exceptions.Timeout) else "connection"
                self.logger.warning(
                    f"{error_type.capitalize()} error fetching {cid} via {connection_type}: {str(e)}"
                )
                
                if not self.use_gateway_fallback:
                    if isinstance(e, requests.exceptions.ConnectionError):
                        raise IPFSConnectionError(f"Failed to connect to IPFS API: {str(e)}")
                    else:
                        raise IPFSTimeoutError(f"Timeout fetching content: {str(e)}")
                # Otherwise continue to gateway fallback
                
        # Try gateway fallback if enabled and local daemon failed (or skipped)
        if self.gateway_only or self.use_gateway_fallback:
            return self._fetch_from_gateway(cid)
                
        # If we get here without returning, neither local daemon nor gateways worked
        raise IPFSContentNotFoundError(f"Content not found after trying all available sources: {cid}")
        
    def _fetch_from_gateway(self, cid):
        """Fetch content from IPFS gateway(s).
        
        This method implements smart gateway selection and performance tracking:
        1. Tries multiple gateways in configured order
        2. Collects detailed performance metrics for each attempt
        3. Streams large files to avoid memory issues
        4. Provides detailed error information if all gateways fail
        
        Args:
            cid: The Content Identifier
            
        Returns:
            The content as bytes
            
        Raises:
            IPFSConnectionError: If all gateways fail
            IPFSContentNotFoundError: If content is not found on any gateway
        """
        fetch_start = time.time()
        errors = []
        
        if not self.gateway_urls:
            raise IPFSConnectionError("No gateway URLs configured")
            
        # Track gateway performance for future optimization
        gateway_stats = {}
        
        # Try each gateway in order
        for gateway_url in self.gateway_urls:
            gateway_start = time.time()
            try:
                # Format the URL depending on gateway style
                if "{cid}" in gateway_url:
                    # Template URL (handles both subdomain and path gateways)
                    url = gateway_url.format(cid=cid)
                else:
                    # Standard path gateway
                    url = f"{gateway_url.rstrip('/')}/{cid}"
                
                self.logger.debug(f"Fetching {cid} from gateway: {url}")
                
                # Use HEAD request first to check availability and get content length
                head_start = time.time()
                head_response = self.session.head(
                    url, 
                    timeout=10,
                    allow_redirects=True
                )
                head_elapsed = time.time() - head_start
                
                # If HEAD request failed, skip to next gateway
                if head_response.status_code != 200:
                    errors.append(f"Gateway {gateway_url} HEAD returned status {head_response.status_code}")
                    continue
                
                # Determine if we should stream based on content length
                content_length = int(head_response.headers.get('content-length', 0))
                stream = content_length > 10 * 1024 * 1024  # Stream if > 10MB
                
                # Use GET for gateway requests (standard HTTP semantics)
                get_start = time.time()
                response = self.session.get(
                    url, 
                    timeout=60 if stream else 30,
                    stream=stream
                )
                
                # Check for success
                if response.status_code == 200:
                    # Handle streaming based on size
                    if stream:
                        # Read in chunks to avoid memory issues
                        chunks = []
                        chunk_start = time.time()
                        bytes_received = 0
                        
                        for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
                            if chunk:
                                chunks.append(chunk)
                                bytes_received += len(chunk)
                                
                                # Log progress for large files
                                if content_length > 100 * 1024 * 1024:  # > 100MB
                                    progress = bytes_received / content_length * 100
                                    self.logger.debug(
                                        f"Gateway download progress: {progress:.1f}% "
                                        f"({bytes_received/1024/1024:.1f}/{content_length/1024/1024:.1f} MB)"
                                    )
                        
                        content = b''.join(chunks)
                        chunk_elapsed = time.time() - chunk_start
                        
                        # Record detailed metrics for streaming
                        if hasattr(self, 'metrics'):
                            self.metrics.record_operation_time('gateway_streaming', chunk_elapsed)
                            
                            if hasattr(self.metrics, 'record_data_transfer'):
                                self.metrics.record_data_transfer(
                                    operation='gateway_fetch', 
                                    bytes_transferred=len(content),
                                    connection_type='gateway',
                                    gateway_url=gateway_url
                                )
                    else:
                        # For smaller files, read all at once
                        content = response.content
                    
                    # Record metrics for gateway fetch time
                    fetch_elapsed = time.time() - fetch_start
                    gateway_elapsed = time.time() - gateway_start
                    
                    if hasattr(self, 'metrics'):
                        self.metrics.record_operation_time('gateway_fetch', fetch_elapsed)
                        
                        # Record per-gateway metrics
                        metric_key = f'gateway_{gateway_url.replace("https://", "").replace("http://", "").split(".")[0]}'
                        self.metrics.record_operation_time(metric_key, gateway_elapsed)
                    
                    # Log performance details
                    size_mb = len(content) / (1024 * 1024)
                    transfer_rate = size_mb / gateway_elapsed
                    
                    self.logger.info(
                        f"Retrieved {cid} from gateway {gateway_url} in {gateway_elapsed:.3f}s "
                        f"({size_mb:.2f}MB, {transfer_rate:.2f}MB/s)"
                    )
                    
                    # Store performance stats for future gateway selection optimization
                    gateway_stats[gateway_url] = {
                        'latency': head_elapsed,
                        'throughput': transfer_rate,
                        'success': True
                    }
                    
                    # Store gateway stats if we have a cache
                    if hasattr(self, 'cache') and hasattr(self.cache, 'gateway_performance'):
                        self.cache.gateway_performance[gateway_url] = gateway_stats[gateway_url]
                    
                    return content
                    
                # Otherwise, add error and try next gateway
                errors.append(f"Gateway {gateway_url} returned status {response.status_code}")
                
                # Store failure stats
                gateway_stats[gateway_url] = {
                    'latency': head_elapsed,
                    'success': False,
                    'status_code': response.status_code
                }
                
            except requests.exceptions.RequestException as e:
                error_type = type(e).__name__
                error_msg = str(e)
                errors.append(f"Gateway {gateway_url} {error_type}: {error_msg}")
                
                # Store error stats
                gateway_stats[gateway_url] = {
                    'success': False,
                    'error_type': error_type,
                    'error_message': error_msg
                }
                
                continue
                
        # If we get here, all gateways failed
        error_details = "\n".join(errors)
        
        # Log detailed error information for diagnostics
        self.logger.error(
            f"Failed to fetch {cid} from all gateways ({len(self.gateway_urls)}). "
            f"Error details:\n{error_details}"
        )
        
        raise IPFSConnectionError(f"Failed to fetch content from all gateways:\n{error_details}")
            
    def _create_file_object(self, path, content, mode):
        """Create the appropriate file-like object based on content size.
        
        Args:
            path: Path or CID of the file
            content: File content as bytes
            mode: File mode
            
        Returns:
            A file-like object for the content
        """
        if self.use_mmap and len(content) > 10 * 1024 * 1024:  # >10MB
            # Create temp file and memory-map it
            fd, temp_path = tempfile.mkstemp()
            with os.fdopen(fd, "wb") as f:
                f.write(content)
            
            # Memory map the file
            fd = os.open(temp_path, os.O_RDONLY)
            mmap_obj = mmap.mmap(fd, 0, access=mmap.ACCESS_READ)
            os.close(fd)  # Close the file descriptor
            
            # Create the mapped file object
            file_obj = IPFSMappedFile(self, path, mmap_obj, temp_path, mode)
            self._open_files.add(file_obj)
            return file_obj
        else:
            # Create a memory file
            file_obj = IPFSMemoryFile(self, path, content, mode)
            self._open_files.add(file_obj)
            return file_obj
    
    def _time_operation(self, operation_name, func, *args, **kwargs):
        """Measure the execution time of an operation.
        
        Args:
            operation_name: Name of the operation for metrics
            func: Function to execute
            args: Positional arguments for the function
            kwargs: Keyword arguments for the function
            
        Returns:
            Result from the function
        """
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            elapsed = time.time() - start_time
            self.metrics.record_operation_time(operation_name, elapsed)
            
    def _open(self, path, mode="rb", **kwargs):
        """Open an IPFS object as a file-like object.
        
        Args:
            path: Path or CID of the file
            mode: File mode (only 'rb' supported)
            **kwargs: Additional arguments
            
        Returns:
            A file-like object for reading from IPFS
        """
        return self._time_operation('open', self._open_impl, path, mode, **kwargs)
            
    def _open_impl(self, path, mode="rb", **kwargs):
        """Implementation of open operation with metrics collection.
        
        Args:
            path: Path or CID of the file
            mode: File mode (only 'rb' supported)
            **kwargs: Additional arguments
            
        Returns:
            A file-like object for reading from IPFS
        """
        if mode not in ["rb", "r"]:
            raise NotImplementedError("Only read modes supported")
            
        # Convert path to CID if necessary
        cid = self._path_to_cid(path)
        
        # Get current content tier if available
        current_tier = self._get_content_tier(cid)
        
        # Check cache layers
        content = self.cache.get(cid, metrics=self.metrics)
        if content is not None:
            self.logger.debug(f"Cache hit for {cid}")
            # Track access for promotion consideration
            if current_tier:
                self._check_for_promotions(cid)
            return self._create_file_object(path, content, mode)
            
        # Not in cache, try to get from any available tier
        if hasattr(self, 'tier_order') and self.tier_order:
            self.logger.debug(f"Checking tiers for {cid}")
            # Try each tier in priority order
            for tier_name in self.tier_order:
                # Skip if tier is unhealthy
                if not self._check_tier_health(tier_name):
                    continue
                
                self.logger.debug(f"Checking tier {tier_name} for {cid}")
                content = self._get_from_tier(cid, tier_name)
                if content is not None:
                    self.logger.debug(f"Found {cid} in tier {tier_name}")
                    # Found in a tier, update tier placement if needed
                    if current_tier != tier_name:
                        metadata = self.cache.get_metadata(cid) or {}
                        metadata['current_tier'] = tier_name
                        self.cache._update_content_metadata(cid, metadata)
                        
                    # Store in cache for faster access
                    self.cache.put(cid, content, metadata={
                        "size": len(content), 
                        "path": path,
                        "current_tier": tier_name
                    })
                    
                    # Check replication policy
                    self._check_replication_policy(cid, content)
                    
                    return self._create_file_object(path, content, mode)
        
        # Fallback to regular IPFS fetch if not found in any tier
        self.logger.debug(f"Cache miss for {cid}, fetching from IPFS")
        fetch_start = time.time()
        content = self._fetch_from_ipfs(cid)
        fetch_elapsed = time.time() - fetch_start
        self.metrics.record_operation_time('ipfs_fetch', fetch_elapsed)
        
        if content is not None:
            # Determine target tier based on content size and access patterns
            if hasattr(self, 'default_tier'):
                target_tier = self.default_tier
            else:
                target_tier = 'memory'
                
            # Cache content for future access
            cache_start = time.time()
            metadata = {
                "size": len(content), 
                "path": path,
                "current_tier": target_tier,
                "added_time": time.time(),
                "last_accessed": time.time(),
                "access_count": 1
            }
            self.cache.put(cid, content, metadata=metadata)
            cache_elapsed = time.time() - cache_start
            self.metrics.record_operation_time('cache_put', cache_elapsed)
            
            # Check replication policy for new content
            self._check_replication_policy(cid, content)
        
        return self._create_file_object(path, content, mode)
    
    def ls(self, path, detail=True, **kwargs):
        """List objects in a directory/prefix.
        
        Args:
            path: Path or CID of the directory
            detail: If True, return a list of dictionaries with file details,
                    otherwise return a list of file names
            **kwargs: Additional arguments
            
        Returns:
            List of files, either as details or just names
        """
        try:
            # Convert path to CID if necessary
            cid = self._path_to_cid(path)
            
            # Make the API request for object links
            response = self.session.post(
                f"{self.api_base}/ls",
                params={"arg": cid}
            )
            
            # Check for success
            if response.status_code != 200:
                if response.status_code == 404:
                    raise IPFSContentNotFoundError(f"Directory not found: {cid}")
                else:
                    raise IPFSError(f"Failed to list directory: {response.text}")
            
            # Parse the response
            result = response.json()
            objects = result.get("Objects", [])
            
            if not objects:
                return []
                
            # Process links
            entries = []
            for obj in objects:
                links = obj.get("Links", [])
                for link in links:
                    entry = {
                        "name": link.get("Name", ""),
                        "size": link.get("Size", 0),
                        "type": "directory" if link.get("Type") == 1 else "file",
                        "hash": link.get("Hash", "")
                    }
                    
                    # Add ipfs:// protocol for full path
                    entry["path"] = f"ipfs://{entry['hash']}"
                    
                    entries.append(entry)
            
            # Return entries in requested format
            if detail:
                return entries
            else:
                return [entry["name"] for entry in entries]
                
        except (IPFSContentNotFoundError, IPFSError) as e:
            raise e
        except Exception as e:
            raise IPFSError(f"Failed to list directory: {str(e)}")
    
    def find(self, path, maxdepth=None, **kwargs):
        """Find all files under a path.
        
        Args:
            path: Path or CID of the starting directory
            maxdepth: Maximum depth to recurse
            **kwargs: Additional arguments
            
        Returns:
            List of all files and directories
        """
        # Start with the root path
        to_visit = [path]
        found = []
        current_depth = 0
        
        # Keep track of visited directories to avoid cycles
        visited = set()
        
        while to_visit and (maxdepth is None or current_depth <= maxdepth):
            path = to_visit.pop(0)
            
            # Avoid revisiting
            cid = self._path_to_cid(path)
            if cid in visited:
                continue
                
            visited.add(cid)
            
            try:
                # List contents
                entries = self.ls(path, detail=True)
                found.extend(entries)
                
                # Add directories to visit
                if maxdepth is None or current_depth < maxdepth:
                    dirs = [entry for entry in entries if entry["type"] == "directory"]
                    to_visit.extend([entry["path"] for entry in dirs])
                    
            except Exception:
                # Skip errors
                continue
                
            current_depth += 1
            
        return found
    
    def glob(self, path, **kwargs):
        """Find files by glob pattern.
        
        Args:
            path: Path pattern to match
            **kwargs: Additional arguments
            
        Returns:
            List of matching files
        """
        # Not fully implemented, as glob patterns don't easily map to IPFS
        # This basic implementation just forwards to find for now
        return self.find(path, **kwargs)
    
    def info(self, path, **kwargs):
        """Get information about a path.
        
        Args:
            path: Path or CID to get info about
            **kwargs: Additional arguments
            
        Returns:
            Dictionary with file information
        """
        try:
            # Convert path to CID if necessary
            cid = self._path_to_cid(path)
            
            # Make the API request for object stat
            response = self.session.post(
                f"{self.api_base}/object/stat",
                params={"arg": cid}
            )
            
            # Check for success
            if response.status_code != 200:
                if response.status_code == 404:
                    raise IPFSContentNotFoundError(f"Object not found: {cid}")
                else:
                    raise IPFSError(f"Failed to get info: {response.text}")
            
            # Parse the response
            stat = response.json()
            
            # Format the result
            info = {
                "name": path,
                "size": stat.get("CumulativeSize", 0),
                "hash": cid,
                "type": "directory" if stat.get("DataSize", 0) < 100 else "file",
                "raw": stat
            }
            
            return info
                
        except (IPFSContentNotFoundError, IPFSError) as e:
            raise e
        except Exception as e:
            raise IPFSError(f"Failed to get info: {str(e)}")
    
    def copy(self, path1, path2, **kwargs):
        """Copy within IPFS is a no-op since content is immutable."""
        # IPFS content is content-addressed and immutable, so copying
        # is essentially just creating another reference to the same content
        return None
    
    def cat(self, path, **kwargs):
        """Get file content as bytes.
        
        Args:
            path: Path or CID of the file
            **kwargs: Additional arguments
            
        Returns:
            File content as bytes
        """
        return self._time_operation('cat', self._cat_impl, path, **kwargs)
    
    def _cat_impl(self, path, **kwargs):
        """Implementation of cat operation with metrics collection.
        
        Args:
            path: Path or CID of the file
            **kwargs: Additional arguments
            
        Returns:
            File content as bytes
        """
        # Convert path to CID if necessary
        cid = self._path_to_cid(path)
        
        # Get current content tier if available
        current_tier = self._get_content_tier(cid)
        
        # Check cache first
        content = self.cache.get(cid, metrics=self.metrics)
        if content is not None:
            # Track access for promotion consideration
            if current_tier:
                self._check_for_promotions(cid)
            return content
        
        # Not in cache, try to get from any available tier
        if hasattr(self, 'tier_order') and self.tier_order:
            # Try each tier in priority order
            for tier_name in self.tier_order:
                # Skip if tier is unhealthy
                if not self._check_tier_health(tier_name):
                    continue
                    
                content = self._get_from_tier(cid, tier_name)
                if content is not None:
                    # Found in a tier, update tier placement if needed
                    if current_tier != tier_name:
                        metadata = self.cache.get_metadata(cid) or {}
                        metadata['current_tier'] = tier_name
                        self.cache._update_content_metadata(cid, metadata)
                        
                    # Store in cache
                    self.cache.put(cid, content, metadata={
                        "size": len(content), 
                        "path": path,
                        "current_tier": tier_name
                    })
                    
                    # Check replication policy
                    self._check_replication_policy(cid, content)
                    
                    return content
        
        # Fallback to regular IPFS fetch if not found in any tier
        fetch_start = time.time()
        content = self._fetch_from_ipfs(cid)
        fetch_elapsed = time.time() - fetch_start
        self.metrics.record_operation_time('ipfs_fetch', fetch_elapsed)
        
        if content is not None:
            # Determine target tier based on content size and access patterns
            if hasattr(self, 'default_tier'):
                target_tier = self.default_tier
            else:
                target_tier = 'memory'
                
            # Cache for future access
            cache_start = time.time()
            metadata = {
                "size": len(content), 
                "path": path,
                "current_tier": target_tier,
                "added_time": time.time(),
                "last_accessed": time.time(),
                "access_count": 1
            }
            self.cache.put(cid, content, metadata=metadata)
            cache_elapsed = time.time() - cache_start
            self.metrics.record_operation_time('cache_put', cache_elapsed)
            
            # Check replication policy for new content
            self._check_replication_policy(cid, content)
        
        return content
        
    def get_performance_metrics(self):
        """Get performance metrics for this filesystem.
        
        Returns:
            Dictionary with performance metrics
        """
        # Get general operation stats
        operation_stats = self.metrics.get_operation_stats()
        
        # Get cache stats
        cache_stats = self.metrics.get_cache_stats()
        
        # Get network stats
        network_stats = {}
        if 'ipfs_fetch' in operation_stats:
            network_stats['ipfs_fetch'] = operation_stats['ipfs_fetch']
        
        # Combine all stats
        return {
            "operations": operation_stats,
            "cache": cache_stats,
            "network": network_stats,
        }
        
    def reset_metrics(self):
        """Reset all performance metrics."""
        self.metrics.reset_metrics()
        
    def analyze_tiered_storage(self):
        """Analyze the tiered storage system and provide comprehensive report.
        
        Returns:
            Dictionary with analysis of tiered storage system
        """
        result = {
            "timestamp": time.time(),
            "role": self.role,
            "tiers": {},
            "content_distribution": {},
            "migration_stats": {},
            "health": {},
            "recommendations": []
        }
        
        # Skip if not using tiered storage
        if not hasattr(self, 'tier_order') or not self.tier_order:
            result["using_tiered_storage"] = False
            return result
            
        result["using_tiered_storage"] = True
        result["tier_count"] = len(self.tier_order)
        result["tier_order"] = self.tier_order
        
        # Analyze each tier
        for tier_name in self.tier_order:
            tier = self.cache.tiers.get(tier_name)
            if not tier:
                continue
                
            tier_type = tier.get('type')
            
            # Basic tier info
            tier_info = {
                "type": tier_type,
                "priority": tier.get('priority'),
                "health": self._check_tier_health(tier_name)
            }
            
            # Type-specific info
            if tier_type == 'memory':
                if 'cache' in tier:
                    tier_info["size"] = tier.get('size', 0)
                    tier_info["used"] = tier['cache'].current_size
                    tier_info["item_count"] = len(tier['cache'].cache)
                    tier_info["utilization"] = tier['cache'].current_size / tier.get('size', 1) * 100
                    
            elif tier_type == 'disk':
                if 'cache' in tier:
                    tier_info["path"] = tier.get('path')
                    tier_info["size"] = tier.get('size', 0)
                    tier_info["used"] = tier['cache'].current_size
                    tier_info["item_count"] = len(tier['cache'].metadata) if hasattr(tier['cache'], 'metadata') else 0
                    tier_info["utilization"] = tier['cache'].current_size / tier.get('size', 1) * 100
                    
            elif tier_type in ('ipfs', 'ipfs_local', 'ipfs_cluster'):
                # Get IPFS stats
                try:
                    response = self.session.post(f"{self.api_base}/stats/repo")
                    if response.status_code == 200:
                        stats = response.json()
                        tier_info["repo_size"] = stats.get("RepoSize", 0)
                        tier_info["storage_max"] = stats.get("StorageMax", 0)
                        tier_info["num_objects"] = stats.get("NumObjects", 0)
                except Exception as e:
                    self.logger.debug(f"Error getting IPFS stats: {str(e)}")
                    
            result["tiers"][tier_name] = tier_info
            
        # Analyze content distribution across tiers
        distribution = {}
        migration_counts = {}
        
        # Get all content metadata
        all_metadata = {}
        
        # If we have a metadata index, use it
        if hasattr(self.cache, 'content_metadata'):
            all_metadata = self.cache.content_metadata
        
        # Otherwise, scan each tier for metadata
        else:
            for tier_name in self.tier_order:
                tier = self.cache.tiers.get(tier_name)
                if tier and tier.get('type') == 'disk':
                    # Disk tiers have metadata
                    disk_cache = tier.get('cache')
                    if hasattr(disk_cache, 'metadata'):
                        all_metadata.update(disk_cache.metadata)
                        
        # Analyze content distribution and migrations
        for cid, metadata in all_metadata.items():
            # Count by current tier
            current_tier = metadata.get('current_tier', 'unknown')
            distribution[current_tier] = distribution.get(current_tier, 0) + 1
            
            # Analyze migrations
            if 'migration_history' in metadata:
                migrations = metadata['migration_history']
                for migration in migrations:
                    source = migration.get('from', 'unknown')
                    target = migration.get('to', 'unknown')
                    key = f"{source}->{target}"
                    migration_counts[key] = migration_counts.get(key, 0) + 1
                    
        result["content_distribution"] = distribution
        result["migration_stats"] = migration_counts
        
        # Generate recommendations
        if hasattr(self, 'tier_stats'):
            for tier_name, stats in self.tier_stats.items():
                tier_info = result["tiers"].get(tier_name, {})
                
                # Check for cache effectiveness
                if 'hit_rate' in stats and stats['hit_rate'] < 0.4:  # Less than 40% hit rate
                    result["recommendations"].append({
                        "type": "cache_optimization",
                        "tier": tier_name,
                        "issue": "low_hit_rate",
                        "description": f"Low hit rate ({stats['hit_rate']:.1%}) for {tier_name} tier",
                        "suggestion": "Consider adjusting cache size or promotion threshold"
                    })
                    
                # Check for space utilization
                if 'utilization' in tier_info and tier_info['utilization'] > 90:  # Over 90% full
                    result["recommendations"].append({
                        "type": "capacity_planning",
                        "tier": tier_name,
                        "issue": "high_utilization",
                        "description": f"High utilization ({tier_info['utilization']:.1f}%) for {tier_name} tier",
                        "suggestion": "Consider increasing tier capacity or adjusting eviction policy"
                    })
        
        # Overall system health
        result["health"]["all_tiers_healthy"] = all(
            result["tiers"][t].get("health", False) for t in self.tier_order
        )
        
        return result
    
    def get(self, path, local_path, **kwargs):
        """Download file from IPFS to local filesystem.
        
        Args:
            path: Path or CID of the file
            local_path: Local file path to save to
            **kwargs: Additional arguments
            
        Returns:
            None
        """
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        
        # Get content
        content = self.cat(path)
        
        # Write to local file
        with open(local_path, 'wb') as f:
            f.write(content)
            
        return None
    
    def put(self, local_path, path, **kwargs):
        """Upload file to IPFS.
        
        Args:
            local_path: Local file path to upload
            path: Destination path/CID in IPFS (ignored as IPFS uses content addressing)
            **kwargs: Additional arguments
            
        Returns:
            The CID of the uploaded content
        """
        try:
            # Read local file
            with open(local_path, 'rb') as f:
                data = f.read()
                
            # Make the API request to add content
            files = {'file': (os.path.basename(local_path), data)}
            response = self.session.post(
                f"{self.api_base}/add",
                files=files,
                params={"cid-version": 1}
            )
            
            # Check for success
            if response.status_code != 200:
                raise IPFSError(f"Failed to upload content: {response.text}")
                
            # Parse the response
            result = response.json()
            cid = result.get("Hash")
            
            if not cid:
                raise IPFSError("No CID returned in IPFS response")
                
            # Cache the content
            self.cache.put(cid, data, metadata={"size": len(data), "path": path})
            
            return cid
                
        except Exception as e:
            raise IPFSError(f"Failed to upload file: {str(e)}")
    
    def exists(self, path, **kwargs):
        """Check if a path exists in IPFS.
        
        Args:
            path: Path or CID to check
            **kwargs: Additional arguments
            
        Returns:
            True if the path exists, False otherwise
        """
        try:
            # Convert path to CID if necessary
            cid = self._path_to_cid(path)
            
            # Check cache first
            if self.cache.get(cid) is not None:
                return True
                
            # Make the API request
            response = self.session.post(
                f"{self.api_base}/object/stat",
                params={"arg": cid}
            )
            
            # Check for success
            return response.status_code == 200
                
        except Exception:
            return False
    
    def isdir(self, path):
        """Check if a path is a directory.
        
        Args:
            path: Path or CID to check
            
        Returns:
            True if the path is a directory, False otherwise
        """
        try:
            # Get info about the path
            info = self.info(path)
            
            # Check if it's a directory
            return info["type"] == "directory"
                
        except Exception:
            return False
    
    def isfile(self, path):
        """Check if a path is a file.
        
        Args:
            path: Path or CID to check
            
        Returns:
            True if the path is a file, False otherwise
        """
        try:
            # Get info about the path
            info = self.info(path)
            
            # Check if it's a file
            return info["type"] == "file"
                
        except Exception:
            return False
    
    def walk(self, path, maxdepth=None, **kwargs):
        """Walk a directory tree.
        
        Args:
            path: Path or CID of the starting directory
            maxdepth: Maximum depth to recurse
            **kwargs: Additional arguments
            
        Returns:
            Generator yielding (dirpath, dirnames, filenames) tuples
        """
        # List the directory
        try:
            entries = self.ls(path, detail=True)
        except Exception:
            return
            
        # Split into directories and files
        dirs = [entry["name"] for entry in entries if entry["type"] == "directory"]
        files = [entry["name"] for entry in entries if entry["type"] == "file"]
        
        # Yield the current level
        yield (path, dirs, files)
        
        # Recurse into subdirectories
        if maxdepth is None or maxdepth > 0:
            next_maxdepth = None if maxdepth is None else maxdepth - 1
            for subdir in dirs:
                subpath = f"{path}/{subdir}" if path.endswith("/") else f"{path}/{subdir}"
                yield from self.walk(subpath, maxdepth=next_maxdepth, **kwargs)
    
    def rm(self, path, recursive=False, **kwargs):
        """Remove content from IPFS (not implemented).
        
        IPFS is a content-addressed system where content is permanent and immutable.
        Removing content means unpinning it, which may eventually make it unavailable
        but doesn't guarantee immediate removal.
        
        Args:
            path: Path or CID to remove
            recursive: If True, recursively remove directories
            **kwargs: Additional arguments
            
        Raises:
            NotImplementedError: This operation is not supported
        """
        raise NotImplementedError(
            "Content removal in IPFS involves unpinning, which requires "
            "using the pin_rm method instead. Use fs.unpin(path) to "
            "unpin content, making it eligible for garbage collection."
        )
    
    def mkdir(self, path, create_parents=True, **kwargs):
        """Create a directory in IPFS (not directly implemented).
        
        IPFS directories are created indirectly by adding content with a directory
        structure or by creating empty directories with the MFS API. This simplified
        implementation creates an empty directory.
        
        Args:
            path: Path for the new directory
            create_parents: If True, create parent directories as needed
            **kwargs: Additional arguments
            
        Returns:
            The CID of the created directory
        """
        try:
            # Make the API request to create an empty directory
            response = self.session.post(
                f"{self.api_base}/object/new",
                params={"arg": "unixfs-dir"}
            )
            
            # Check for success
            if response.status_code != 200:
                raise IPFSError(f"Failed to create directory: {response.text}")
                
            # Parse the response
            result = response.json()
            cid = result.get("Hash")
            
            if not cid:
                raise IPFSError("No CID returned in IPFS response")
                
            return cid
                
        except Exception as e:
            raise IPFSError(f"Failed to create directory: {str(e)}")
    
    # IPFS-specific methods
    
    def pin(self, path, tier=None):
        """Pin content to the local IPFS node or specified tier.
        
        Args:
            path: Path or CID to pin
            tier: Optional tier name to pin to (None for local IPFS pinning)
            
        Returns:
            Dictionary with pin operation result
        """
        try:
            # Convert path to CID if necessary
            cid = self._path_to_cid(path)
            
            # If tier specified, ensure content in that tier
            if tier is not None and hasattr(self, 'tier_order'):
                if tier not in self.cache.tiers:
                    raise ValueError(f"Tier '{tier}' not found")
                    
                # Get content (probably from cache)
                content = self.cat(cid)
                if content is None:
                    raise IPFSContentNotFoundError(f"Content not found: {cid}")
                    
                # Ensure in specified tier
                result = self._ensure_in_tier(cid, tier)
                if not result:
                    raise IPFSError(f"Failed to ensure content in tier '{tier}'")
                    
                # Update metadata to track pinning
                metadata = self.cache.get_metadata(cid) or {}
                metadata['pinned'] = True
                metadata['pin_time'] = time.time()
                metadata['current_tier'] = tier
                self.cache._update_content_metadata(cid, metadata)
                
                return {
                    "success": True,
                    "cid": cid,
                    "pinned_in_tier": tier
                }
                
            # Otherwise, fallback to standard IPFS pinning
            response = self.session.post(
                f"{self.api_base}/pin/add",
                params={"arg": cid}
            )
            
            # Check for success
            if response.status_code != 200:
                raise IPFSError(f"Failed to pin content: {response.text}")
                
            # Parse the response
            result = response.json()
            pins = result.get("Pins", [])
            
            return {
                "success": True,
                "operation": "pin",
                "pins": pins,
                "count": len(pins)
            }
                
        except Exception as e:
            return {
                "success": False,
                "operation": "pin",
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def unpin(self, path):
        """Unpin content from the local IPFS node.
        
        Args:
            path: Path or CID to unpin
            
        Returns:
            Dictionary with unpin operation result
        """
        try:
            # Convert path to CID if necessary
            cid = self._path_to_cid(path)
            
            # Make the API request
            response = self.session.post(
                f"{self.api_base}/pin/rm",
                params={"arg": cid}
            )
            
            # Check for success
            if response.status_code != 200:
                raise IPFSError(f"Failed to unpin content: {response.text}")
                
            # Parse the response
            result = response.json()
            pins = result.get("Pins", [])
            
            return {
                "success": True,
                "operation": "unpin",
                "pins": pins,
                "count": len(pins)
            }
                
        except Exception as e:
            return {
                "success": False,
                "operation": "unpin",
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def get_pins(self):
        """Get list of pinned content.
        
        Returns:
            Dictionary with pinned content
        """
        try:
            # Make the API request
            response = self.session.post(
                f"{self.api_base}/pin/ls",
                params={"type": "all"}
            )
            
            # Check for success
            if response.status_code != 200:
                raise IPFSError(f"Failed to list pins: {response.text}")
                
            # Parse the response
            result = response.json()
            pins = result.get("Keys", {})
            
            return {
                "success": True,
                "operation": "get_pins",
                "pins": pins,
                "count": len(pins)
            }
                
        except Exception as e:
            return {
                "success": False,
                "operation": "get_pins",
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def publish_to_ipns(self, path, key=None):
        """Publish content to IPNS.
        
        Args:
            path: Path or CID to publish
            key: Key to use for publishing
            
        Returns:
            Dictionary with publish operation result
        """
        try:
            # Convert path to CID if necessary
            cid = self._path_to_cid(path)
            
            # Prepare parameters
            params = {"arg": cid}
            if key:
                params["key"] = key
                
            # Make the API request
            response = self.session.post(
                f"{self.api_base}/name/publish",
                params=params
            )
            
            # Check for success
            if response.status_code != 200:
                raise IPFSError(f"Failed to publish to IPNS: {response.text}")
                
            # Parse the response
            result = response.json()
            name = result.get("Name")
            value = result.get("Value")
            
            return {
                "success": True,
                "operation": "publish_to_ipns",
                "name": name,
                "value": value
            }
                
        except Exception as e:
            return {
                "success": False,
                "operation": "publish_to_ipns",
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def resolve_ipns(self, name):
        """Resolve an IPNS name to a CID.
        
        Args:
            name: IPNS name to resolve
            
        Returns:
            Dictionary with resolve operation result
        """
        try:
            # Make the API request
            response = self.session.post(
                f"{self.api_base}/name/resolve",
                params={"arg": name}
            )
            
            # Check for success
            if response.status_code != 200:
                raise IPFSError(f"Failed to resolve IPNS name: {response.text}")
                
            # Parse the response
            result = response.json()
            path = result.get("Path")
            
            return {
                "success": True,
                "operation": "resolve_ipns",
                "name": name,
                "path": path
            }
                
        except Exception as e:
            return {
                "success": False,
                "operation": "resolve_ipns",
                "error": str(e),
                "error_type": type(e).__name__
            }
            
    def __getstate__(self):
        """Custom state for pickle serialization."""
        state = self.__dict__.copy()
        # Remove unpicklable objects
        if "_open_files" in state:
            state["_open_files"] = set()
        if "session" in state:
            del state["session"]
        if "cache" in state:
            del state["cache"]
        return state
        
    def __setstate__(self, state):
        """Restore state from pickle."""
        self.__dict__.update(state)
        # Reinitialize unpicklable objects
        self._open_files = set()
        self._setup_ipfs_connection()
        self.cache = TieredCacheManager(config=state.get("config"))
        
    def close(self):
        """Close all open file handles and clean up resources."""
        # Close all open files
        for file_obj in list(self._open_files):
            try:
                file_obj.close()
            except Exception:
                pass
        self._open_files.clear()
        
        # Close the session
        if hasattr(self, "session"):
            self.session.close()
        
        super().close()