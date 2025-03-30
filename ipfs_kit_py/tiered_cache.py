"""
Tiered caching system with Adaptive Replacement Cache (ARC) for IPFS content.

This module implements a sophisticated multi-tier caching system for IPFS content
with automatic migration between tiers based on content access patterns.
"""

import os
import time
import math
import uuid
import mmap
import logging
import tempfile
import shutil
from typing import Dict, List, Optional, Union, Any, Tuple, Set

# Initialize logger
logger = logging.getLogger(__name__)

class ARCache:
    """Adaptive Replacement Cache for memory-based caching of IPFS content.
    
    This implementation uses a modified ARC algorithm that considers both 
    recency and frequency of access patterns, while also accounting for 
    content size to optimize memory usage.
    
    The ARC algorithm provides several advantages over traditional LRU or LFU:
    1. Automatically balances between recency and frequency
    2. Uses ghost lists to track recently evicted items for better adaptivity
    3. Dynamically adjusts to changing access patterns
    4. Maintains history for intelligent admission and eviction
    5. Avoids cache pollution from one-time scans or frequency bias
    """
    
    def __init__(self, maxsize: int = 100 * 1024 * 1024, config: Optional[Dict[str, Any]] = None):
        """Initialize the Adaptive Replacement Cache.
        
        Args:
            maxsize: Maximum size of the cache in bytes (default: 100MB)
            config: Additional configuration parameters for ARC algorithm
        """
        self.maxsize = maxsize
        self.current_size = 0
        
        # Initialize configuration
        self.config = config or {}
        
        # ARC algorithm uses four lists:
        # T1: Recently accessed items that are in cache
        # B1: Recently accessed items that have been evicted from cache (ghost list)
        # T2: Frequently accessed items that are in cache
        # B2: Frequently accessed items that have been evicted from cache (ghost list)
        self.T1 = {}  # Recent cache
        self.T2 = {}  # Frequent cache
        self.B1 = {}  # Ghost entries for recent (not consuming actual cache space)
        self.B2 = {}  # Ghost entries for frequent (not consuming actual cache space)
        
        # Size tracking for each list
        self.T1_size = 0
        self.T2_size = 0
        
        # Maximum size for ghost lists
        self.ghost_list_size = self.config.get('ghost_list_size', 1024)
        
        # Target size for T1 (p is adaptive)
        self.p = self.config.get('initial_p', 0)
        self.max_p = self.maxsize * self.config.get('max_p_percent', 0.5)  # p can grow up to 50% of cache
        
        # Weights for heat score calculation
        self.frequency_weight = self.config.get('frequency_weight', 0.7)
        self.recency_weight = self.config.get('recency_weight', 0.3)
        self.recent_access_boost = self.config.get('access_boost', 2.0)
        self.heat_decay_hours = self.config.get('heat_decay_hours', 1.0)
        
        # How often to prune ghost lists (in items)
        self.ghost_list_pruning = self.config.get('ghost_list_pruning', 128)
        
        # Enable detailed performance tracking
        self.enable_stats = self.config.get('enable_stats', True)
        
        # Access statistics for items
        self.access_stats = {}
        
        # Performance metrics
        if self.enable_stats:
            self.stats = {
                'hits': {'t1': 0, 't2': 0, 'b1': 0, 'b2': 0},
                'misses': 0,
                'operations': 0,
                'evictions': {'t1': 0, 't2': 0},
                'promotions': {'b1_to_t2': 0, 'b2_to_t2': 0, 't1_to_t2': 0},
                'p_adjustments': 0,
                'ghost_list_hits': 0
            }
        
    def __contains__(self, key: str) -> bool:
        """Check if a key is in the cache.
        
        Args:
            key: CID or identifier of the content
            
        Returns:
            True if the key is in the cache, False otherwise
        """
        return key in self.T1 or key in self.T2
    
    def __len__(self) -> int:
        """Get the number of items in the cache.
        
        Returns:
            Number of items in the cache
        """
        return len(self.T1) + len(self.T2)
    
    def get(self, key: str) -> Optional[bytes]:
        """Get content from the cache.
        
        Args:
            key: CID or identifier of the content
            
        Returns:
            Content if found, None otherwise
        """
        # Check if in T1 (recently accessed)
        if key in self.T1:
            # Move from T1 to T2 (recent -> frequent)
            item = self.T1.pop(key)
            item_size = len(item)
            self.T1_size -= item_size
            self.T2[key] = item
            self.T2_size += item_size
            self._update_stats(key, "hit_t1")
            return item
            
        # Check if in T2 (frequently accessed)
        if key in self.T2:
            # Already in T2, keep it there
            self._update_stats(key, "hit_t2")
            return self.T2[key]
            
        # Cache miss
        self._update_stats(key, "miss")
        return None
        
    def put(self, key: str, value: bytes) -> bool:
        """Store content in the cache.
        
        Args:
            key: CID or identifier of the content
            value: Content to store
            
        Returns:
            True if stored successfully, False otherwise
        """
        if not isinstance(value, bytes):
            logger.warning(f"Cache only accepts bytes, got {type(value)}")
            return False
            
        value_size = len(value)
        
        # Don't cache items larger than the max cache size
        if value_size > self.maxsize:
            logger.warning(f"Item size ({value_size}) exceeds cache capacity ({self.maxsize})")
            return False
            
        # If already in cache, just update it
        if key in self.T1:
            old_size = len(self.T1[key])
            self.T1[key] = value
            self.T1_size = self.T1_size - old_size + value_size
            self._update_stats(key, "update_t1")
            return True
            
        if key in self.T2:
            old_size = len(self.T2[key])
            self.T2[key] = value
            self.T2_size = self.T2_size - old_size + value_size
            self._update_stats(key, "update_t2")
            return True
            
        # Case 1: key in B1 (recently evicted)
        if key in self.B1:
            # Increase the target size for T2
            adjustment = max(len(self.B2) // max(len(self.B1), 1), 1)
            old_p = self.p
            self.p = min(self.p + adjustment, self.max_p)
            
            # Record p adjustment if significant
            if self.enable_stats and abs(self.p - old_p) > 0:
                self.stats['p_adjustments'] += 1
                self.stats['hits']['b1'] += 1
                self.stats['ghost_list_hits'] += 1
                
            # Log information about ghost list hit
            logger.debug(f"Ghost hit in B1 for {key}, adjusted p from {old_p} to {self.p}")
            
            self._replace(value_size)
            
            # Move from B1 to T2
            self.B1.pop(key)
            self.T2[key] = value
            self.T2_size += value_size
            self._update_stats(key, "promote_b1_to_t2")
            
            # Record promotion in stats
            if self.enable_stats:
                self.stats['promotions']['b1_to_t2'] += 1
                
            return True
            
        # Case 2: key in B2 (frequently evicted)
        if key in self.B2:
            # Decrease the target size for T2
            adjustment = max(len(self.B1) // max(len(self.B2), 1), 1)
            old_p = self.p
            self.p = max(self.p - adjustment, 0)
            
            # Record p adjustment if significant
            if self.enable_stats and abs(self.p - old_p) > 0:
                self.stats['p_adjustments'] += 1
                self.stats['hits']['b2'] += 1
                self.stats['ghost_list_hits'] += 1
                
            # Log information about ghost list hit
            logger.debug(f"Ghost hit in B2 for {key}, adjusted p from {old_p} to {self.p}")
            
            self._replace(value_size)
            
            # Move from B2 to T2
            self.B2.pop(key)
            self.T2[key] = value
            self.T2_size += value_size
            self._update_stats(key, "promote_b2_to_t2")
            
            # Record promotion in stats
            if self.enable_stats:
                self.stats['promotions']['b2_to_t2'] += 1
                
            return True
            
        # Case 3: new item
        # Ensure we have space
        self._replace(value_size)
        
        # Add to T1 (recent items)
        self.T1[key] = value
        self.T1_size += value_size
        self._update_stats(key, "new_t1")
        
        # Make sure current_size is accurate
        self.current_size = self.T1_size + self.T2_size
        
        return True
    
    def _replace(self, required_size: int) -> None:
        """Make room for a new item by evicting old ones.
        
        Args:
            required_size: Size of the item that needs space
        """
        # Check if we need to evict anything
        while self.current_size + required_size > self.maxsize and (self.T1 or self.T2):
            # Case 1: T1 larger than target
            if self.T1_size > self.p:
                self._evict_from_t1()
            # Case 2: T2 should be reduced
            elif self.T2_size > 0:
                self._evict_from_t2()
            # Case 3: Default to T1
            elif self.T1_size > 0:
                self._evict_from_t1()
            else:
                # Cache is empty or can't free enough space
                break
                
            # Update current size
            self.current_size = self.T1_size + self.T2_size
                
    def _evict_from_t1(self) -> None:
        """Evict an item from T1 (recent cache).
        
        In the ARC algorithm, items evicted from T1 go into the B1 ghost list,
        which doesn't consume cache space but tracks history to guide adaptive behavior.
        """
        if not self.T1:
            return
            
        # Find item to evict (LRU policy)
        evict_key = min(self.T1.keys(), key=lambda k: self.access_stats[k]['last_access'])
        evict_value = self.T1.pop(evict_key)
        
        # Update size tracking
        evict_size = len(evict_value)
        self.T1_size -= evict_size
        
        # Add to B1 ghost list
        self.B1[evict_key] = True
        
        # Clean up extremely old items from B1 when it gets too large
        if len(self.B1) > self.ghost_list_size:
            # Sort by last access time and remove oldest entries
            items_to_remove = len(self.B1) - self.ghost_list_size + (self.ghost_list_size // 5)  # Remove extra 20% to avoid frequent pruning
            oldest_keys = sorted(
                self.B1.keys(), 
                key=lambda k: self.access_stats.get(k, {}).get('last_access', 0)
            )[:items_to_remove]
            
            for old_key in oldest_keys:
                self.B1.pop(old_key)
            
            logger.debug(f"Pruned {len(oldest_keys)} old entries from B1 ghost list")
            
        # Track eviction in stats
        if self.enable_stats:
            self.stats['evictions']['t1'] += 1
            
        logger.debug(f"Evicted {evict_key} ({evict_size} bytes) from T1 to B1 ghost list")
    
    def _evict_from_t2(self) -> None:
        """Evict an item from T2 (frequent cache).
        
        In the ARC algorithm, items evicted from T2 go into the B2 ghost list,
        which helps track items that were frequently accessed but had to be removed.
        """
        if not self.T2:
            return
            
        # Find item to evict (least heat score)
        evict_key = min(self.T2.keys(), key=lambda k: self.access_stats[k]['heat_score'])
        evict_value = self.T2.pop(evict_key)
        
        # Update size tracking
        evict_size = len(evict_value)
        self.T2_size -= evict_size
        
        # Add to B2 ghost list
        self.B2[evict_key] = True
        
        # Clean up ghost list when it gets too large
        if len(self.B2) > self.ghost_list_size:
            # Sort by heat score and remove coldest entries
            items_to_remove = len(self.B2) - self.ghost_list_size + (self.ghost_list_size // 5)  # Remove extra 20%
            coldest_keys = sorted(
                self.B2.keys(), 
                key=lambda k: self.access_stats.get(k, {}).get('heat_score', 0)
            )[:items_to_remove]
            
            for cold_key in coldest_keys:
                self.B2.pop(cold_key)
                
            logger.debug(f"Pruned {len(coldest_keys)} cold entries from B2 ghost list")
            
        # Track eviction in stats
        if self.enable_stats:
            self.stats['evictions']['t2'] += 1
            
        logger.debug(f"Evicted {evict_key} ({evict_size} bytes) from T2 to B2 ghost list")
    
    def _update_stats(self, key: str, access_type: str) -> None:
        """Update access statistics for content item.
        
        Args:
            key: CID or identifier of the content
            access_type: Type of access (hit_t1, hit_t2, miss, etc.)
        """
        current_time = time.time()
        
        # Track operation in stats if enabled
        if self.enable_stats:
            self.stats['operations'] += 1
            
        # Initialize stats for new items
        if key not in self.access_stats:
            self.access_stats[key] = {
                'first_access': current_time,
                'last_access': current_time,
                'access_count': 0,
                'heat_score': 0.0,
                'hits': {
                    't1': 0,
                    't2': 0,
                    'b1': 0,
                    'b2': 0,
                    'miss': 0
                }
            }
            
        stats = self.access_stats[key]
        stats['access_count'] += 1
        stats['last_access'] = current_time
        
        # Update hit counters
        if access_type == "hit_t1":
            stats['hits']['t1'] += 1
            if self.enable_stats:
                self.stats['hits']['t1'] += 1
        elif access_type == "hit_t2":
            stats['hits']['t2'] += 1
            if self.enable_stats:
                self.stats['hits']['t2'] += 1
        elif access_type == "miss":
            stats['hits']['miss'] += 1
            if self.enable_stats:
                self.stats['misses'] += 1
                
        # Compute heat score using the configurable weights and parameters
        age = max(0.001, current_time - stats['first_access'])  # Age in seconds (avoid div by 0)
        recency = 1.0 / (1.0 + (current_time - stats['last_access']) / (3600 * self.heat_decay_hours))
        frequency = stats['access_count'] / age  # Accesses per second
        
        # Boost factor for items that have been accessed recently
        recent_access_threshold = 3600 * self.heat_decay_hours
        recent_boost = self.recent_access_boost if (current_time - stats['last_access']) < recent_access_threshold else 1.0
        
        # Combine factors into heat score using configurable weights
        stats['heat_score'] = (
            frequency * self.frequency_weight + 
            recency * self.recency_weight
        ) * recent_boost
        
        # Log detailed access information
        logger.debug(
            f"Updated stats for {key}: access={access_type}, "
            f"count={stats['access_count']}, heat={stats['heat_score']:.4f}"
        )
            
    def clear(self) -> None:
        """Clear the cache completely."""
        self.T1.clear()
        self.T2.clear()
        self.B1.clear()
        self.B2.clear()
        self.T1_size = 0
        self.T2_size = 0
        self.current_size = 0
        self.p = 0
        
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the ARC cache.
        
        Provides detailed information on cache utilization, hit rates,
        ghost list effectiveness, and adaptive behavior metrics.
        
        Returns:
            Dictionary with detailed cache statistics
        """
        # Calculate hit rates for detailed reporting
        hit_rate = self._calculate_hit_rate()
        t1_hit_rate = 0
        t2_hit_rate = 0
        ghost_hit_rate = 0
        
        # Get hit counts from global stats
        if self.enable_stats:
            total_accesses = self.stats['operations']
            if total_accesses > 0:
                t1_hits = self.stats['hits']['t1']
                t2_hits = self.stats['hits']['t2']
                ghost_hits = self.stats['ghost_list_hits']
                
                t1_hit_rate = t1_hits / total_accesses
                t2_hit_rate = t2_hits / total_accesses
                ghost_hit_rate = ghost_hits / total_accesses
        
        # Comprehensive statistics with ARC-specific metrics
        stats = {
            'maxsize': self.maxsize,
            'current_size': self.current_size,
            'utilization': self.current_size / self.maxsize if self.maxsize > 0 else 0,
            'item_count': len(self.T1) + len(self.T2),
            'hit_rate': hit_rate,
            'T1': {
                'count': len(self.T1),
                'size': self.T1_size,
                'percent': len(self.T1) / max(1, len(self.T1) + len(self.T2)) * 100,
                'hit_rate': t1_hit_rate,
            },
            'T2': {
                'count': len(self.T2),
                'size': self.T2_size,
                'percent': len(self.T2) / max(1, len(self.T1) + len(self.T2)) * 100,
                'hit_rate': t2_hit_rate,
            },
            'ghost_entries': {
                'B1': len(self.B1),
                'B2': len(self.B2),
                'total': len(self.B1) + len(self.B2),
                'hit_rate': ghost_hit_rate,
            },
            'arc_balance': {
                'p': self.p,
                'p_percent': self.p / self.maxsize if self.maxsize > 0 else 0,
                'max_p': self.max_p,
                'p_adjustments': self.stats.get('p_adjustments', 0) if self.enable_stats else 0,
            },
            'evictions': self.stats.get('evictions', {}) if self.enable_stats else {},
            'promotions': self.stats.get('promotions', {}) if self.enable_stats else {},
            'configuration': {
                'ghost_list_size': self.ghost_list_size,
                'frequency_weight': self.frequency_weight,
                'recency_weight': self.recency_weight,
                'heat_decay_hours': self.heat_decay_hours,
                'recent_access_boost': self.recent_access_boost,
            }
        }
        
        # Calculate balance metrics to see if the cache is appropriately adapting
        if len(self.T1) + len(self.T2) > 0:
            # Measure how well the cache is handling the workload
            t1_t2_ratio = len(self.T1) / max(1, len(self.T2))
            stats['arc_balance']['t1_t2_ratio'] = t1_t2_ratio
            
            # Measure ghost list effectiveness
            if len(self.B1) + len(self.B2) > 0:
                b1_b2_ratio = len(self.B1) / max(1, len(self.B2))
                stats['ghost_entries']['b1_b2_ratio'] = b1_b2_ratio
                
            # Calculate adaptation effectiveness
            if self.enable_stats and self.stats['operations'] > 0:
                adaptivity = self.stats.get('p_adjustments', 0) / self.stats['operations']
                stats['arc_balance']['adaptivity'] = adaptivity
        
        return stats
    
    def _calculate_hit_rate(self) -> float:
        """Calculate the cache hit rate.
        
        Returns:
            Hit rate as a float between 0 and 1
        """
        hits = sum(stats['hits']['t1'] + stats['hits']['t2'] for stats in self.access_stats.values())
        misses = sum(stats['hits']['miss'] for stats in self.access_stats.values())
        total = hits + misses
        
        return hits / total if total > 0 else 0.0
        
    def get_arc_metrics(self) -> Dict[str, Any]:
        """Get detailed ARC-specific metrics for advanced monitoring.
        
        This method provides insights into the ARC algorithm's inner workings,
        including ghost list effectiveness, adaptivity, cache utilization
        patterns, and balance between recency and frequency caching.
        
        Returns:
            Dictionary with detailed ARC metrics
        """
        # Calculate ghost list hit rates
        ghost_hits = 0
        total_operations = 0
        
        if self.enable_stats:
            ghost_hits = self.stats.get('ghost_list_hits', 0)
            total_operations = self.stats.get('operations', 0)
            
        ghost_hit_rate = ghost_hits / max(1, total_operations)
        
        # Calculate T1/T2 balance metrics
        t1_percent = len(self.T1) / max(1, len(self.T1) + len(self.T2)) * 100
        t2_percent = 100 - t1_percent
        
        # Calculate ghost list effectiveness
        ghost_utilization = (len(self.B1) + len(self.B2)) / max(1, self.ghost_list_size) * 100
        
        # Calculate balance ratios
        t1_t2_ratio = len(self.T1) / max(1, len(self.T2))
        b1_b2_ratio = len(self.B1) / max(1, len(self.B2))
        
        # Adaptivity metrics
        p_adjustments = self.stats.get('p_adjustments', 0) if self.enable_stats else 0
        adaptivity_rate = p_adjustments / max(1, total_operations)
        
        # Heat score distribution
        heat_scores = [stats['heat_score'] for stats in self.access_stats.values()]
        heat_metrics = {}
        
        if heat_scores:
            heat_metrics = {
                'min': min(heat_scores),
                'max': max(heat_scores),
                'avg': sum(heat_scores) / len(heat_scores)
            }
            
            # Calculate quartiles if we have enough data
            if len(heat_scores) >= 4:
                sorted_scores = sorted(heat_scores)
                q1_idx = len(sorted_scores) // 4
                q2_idx = len(sorted_scores) // 2
                q3_idx = q1_idx * 3
                
                heat_metrics['quartiles'] = {
                    'q1': sorted_scores[q1_idx],
                    'q2': sorted_scores[q2_idx],  # median
                    'q3': sorted_scores[q3_idx]
                }
        
        return {
            'algorithm': 'Adaptive Replacement Cache (ARC)',
            'ghost_entries': {
                'B1': len(self.B1),
                'B2': len(self.B2),
                'total': len(self.B1) + len(self.B2),
                'max_size': self.ghost_list_size,
                'utilization': ghost_utilization,
                'hit_rate': ghost_hit_rate,
                'b1_b2_ratio': b1_b2_ratio
            },
            'cache_composition': {
                'T1_count': len(self.T1),
                'T2_count': len(self.T2),
                'T1_percent': t1_percent,
                'T2_percent': t2_percent,
                't1_t2_ratio': t1_t2_ratio
            },
            'arc_balance': {
                'p': self.p,
                'p_percent': self.p / self.maxsize if self.maxsize > 0 else 0,
                'max_p': self.max_p,
                'p_adjustments': p_adjustments,
                'adaptivity_rate': adaptivity_rate
            },
            'heat_score_metrics': heat_metrics,
            'configuration': {
                'frequency_weight': self.frequency_weight,
                'recency_weight': self.recency_weight,
                'heat_decay_hours': self.heat_decay_hours,
                'access_boost': self.recent_access_boost
            },
            'performance': {
                'hit_rate': self._calculate_hit_rate(),
                'utilization': self.current_size / self.maxsize if self.maxsize > 0 else 0,
                'operations': total_operations,
                'evictions': self.stats.get('evictions', {}) if self.enable_stats else {},
                'promotions': self.stats.get('promotions', {}) if self.enable_stats else {}
            }
        }


class DiskCache:
    """Disk-based persistent cache for IPFS content.
    
    This cache stores content on disk with proper indexing and size management.
    It uses a simple directory structure with content-addressed files.
    """
    
    def __init__(self, directory: str = "~/.ipfs_cache", 
                 size_limit: int = 1 * 1024 * 1024 * 1024):
        """Initialize the disk cache.
        
        Args:
            directory: Directory to store cached files
            size_limit: Maximum size of the cache in bytes (default: 1GB)
        """
        self.directory = os.path.expanduser(directory)
        self.size_limit = size_limit
        self.index_file = os.path.join(self.directory, "cache_index.json")
        self.index = {}
        self.current_size = 0
        
        # Create cache directory if it doesn't exist
        os.makedirs(self.directory, exist_ok=True)
        
        # Load existing index
        self._load_index()
        
        # Verify cache integrity
        self._verify_cache()
        
    def _load_index(self) -> None:
        """Load the cache index from disk."""
        try:
            if os.path.exists(self.index_file):
                import json
                with open(self.index_file, 'r') as f:
                    data = json.load(f)
                    # Validate index data to ensure it's a dict of dict entries
                    if isinstance(data, dict) and all(isinstance(v, dict) for v in data.values()):
                        self.index = data
                        logger.debug(f"Loaded cache index with {len(self.index)} entries")
                    else:
                        logger.warning(f"Invalid cache index format - creating new index")
                        self.index = {}
            else:
                self.index = {}
                logger.debug("No existing cache index found, creating new one")
        except Exception as e:
            logger.error(f"Error loading cache index: {e}")
            self.index = {}
            
    def _save_index(self) -> None:
        """Save the cache index to disk."""
        try:
            import json
            with open(self.index_file, 'w') as f:
                json.dump(self.index, f)
        except Exception as e:
            logger.error(f"Error saving cache index: {e}")
            
    def _verify_cache(self) -> None:
        """Verify cache integrity and recalculate size."""
        valid_entries = {}
        calculated_size = 0
        
        # If index is empty or has no entries yet, just return
        if not self.index:
            return
            
        for key, entry in self.index.items():
            # Skip entries without a filename (shouldn't happen but check to be safe)
            if 'filename' not in entry:
                logger.warning(f"Cache entry {key} missing filename field")
                continue
                
            file_path = os.path.join(self.directory, entry['filename'])
            if os.path.exists(file_path):
                # Update file size in case it changed
                actual_size = os.path.getsize(file_path)
                entry['size'] = actual_size
                valid_entries[key] = entry
                calculated_size += actual_size
            else:
                logger.warning(f"Cache entry {key} points to missing file {entry['filename']}")
                
        # Update index and size
        self.index = valid_entries
        self.current_size = calculated_size
        
        logger.debug(f"Cache verification complete: {len(self.index)} valid entries, {self.current_size} bytes")
        
    def get(self, key: str) -> Optional[bytes]:
        """Get content from the cache.
        
        Args:
            key: CID or identifier of the content
            
        Returns:
            Content if found, None otherwise
        """
        if key not in self.index:
            return None
            
        entry = self.index[key]
        file_path = os.path.join(self.directory, entry['filename'])
        
        try:
            # Check if file still exists
            if not os.path.exists(file_path):
                logger.warning(f"Cache entry exists but file missing: {file_path}")
                del self.index[key]
                self._save_index()
                return None
                
            # Update access time
            entry['last_access'] = time.time()
            
            # Read the file
            with open(file_path, 'rb') as f:
                content = f.read()
                
            # Update index
            self._save_index()
            
            return content
            
        except Exception as e:
            logger.error(f"Error reading from disk cache: {e}")
            return None
            
    def put(self, key: str, value: bytes, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Store content in the cache.
        
        Args:
            key: CID or identifier of the content
            value: Content to store
            metadata: Additional metadata to store with the content
            
        Returns:
            True if stored successfully, False otherwise
        """
        if not isinstance(value, bytes):
            logger.warning(f"Cache only accepts bytes, got {type(value)}")
            return False
            
        value_size = len(value)
        
        # Don't cache items larger than the max cache size
        if value_size > self.size_limit:
            logger.warning(f"Item size ({value_size}) exceeds cache capacity ({self.size_limit})")
            return False
            
        # Make room if needed
        if self.current_size + value_size > self.size_limit:
            self._make_room(value_size)
            
        # Generate a filename based on the key
        filename = f"{key.replace('/', '_')}.bin"
        if len(filename) > 255:  # Avoid filename length issues
            filename = f"{key[:10]}_{uuid.uuid4()}_{key[-10:]}.bin"
            
        file_path = os.path.join(self.directory, filename)
        
        try:
            # Write the file
            with open(file_path, 'wb') as f:
                f.write(value)
                
            # Update index
            current_time = time.time()
            self.index[key] = {
                'filename': filename,
                'size': value_size,
                'added': current_time,
                'last_access': current_time,
                'access_count': 1,
                'metadata': metadata or {}
            }
            
            # Update current size
            self.current_size += value_size
            
            # Save index
            self._save_index()
            
            return True
            
        except Exception as e:
            logger.error(f"Error writing to disk cache: {e}")
            # Clean up partial file if it exists
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            return False
            
    def _make_room(self, required_size: int) -> None:
        """Make room in the cache by evicting entries.
        
        Args:
            required_size: Size of the item that needs space
        """
        # If the cache is empty or we need more space than the entire cache,
        # just clear everything
        if not self.index or required_size > self.size_limit:
            self.clear()
            return
            
        # Calculate how much space we need to free
        space_to_free = self.current_size + required_size - self.size_limit
        
        # Sort entries by heat score (combination of recency and frequency)
        def heat_score(entry):
            age = time.time() - entry['added']
            recency = 1.0 / (1.0 + (time.time() - entry['last_access']) / 86400)  # Decay over days
            frequency = entry.get('access_count', 1)
            return frequency * recency / math.sqrt(1 + age / 86400)  # Decrease score with age (sqrt to make it less aggressive)
            
        sorted_entries = sorted(
            [(k, v) for k, v in self.index.items()],
            key=lambda x: heat_score(x[1])
        )
        
        # Evict entries until we have enough space
        freed_space = 0
        evicted_count = 0
        
        for key, entry in sorted_entries:
            if freed_space >= space_to_free:
                break
                
            # Delete the file
            file_path = os.path.join(self.directory, entry['filename'])
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"Error removing cache file {file_path}: {e}")
                
            # Update tracking
            freed_space += entry['size']
            self.current_size -= entry['size']
            evicted_count += 1
            
            # Remove from index
            del self.index[key]
            
        logger.debug(f"Made room in cache by evicting {evicted_count} entries, freed {freed_space} bytes")
        
        # Save updated index
        self._save_index()
        
    def clear(self) -> None:
        """Clear the cache completely."""
        # Delete all cache files
        for entry in self.index.values():
            file_path = os.path.join(self.directory, entry['filename'])
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"Error removing cache file {file_path}: {e}")
                
        # Reset index and size
        self.index = {}
        self.current_size = 0
        
        # Save empty index
        self._save_index()
        
        logger.debug("Cache cleared completely")
        
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache.
        
        Returns:
            Dictionary with cache statistics
        """
        # Count by file type
        type_counts = {}
        for entry in self.index.values():
            file_type = entry.get('metadata', {}).get('mimetype', 'unknown')
            if file_type not in type_counts:
                type_counts[file_type] = 0
            type_counts[file_type] += 1
            
        # Get age distribution
        current_time = time.time()
        age_distribution = {
            'under_1hour': 0,
            '1hour_to_1day': 0,
            '1day_to_1week': 0,
            'over_1week': 0
        }
        
        for entry in self.index.values():
            age = current_time - entry['added']
            if age < 3600:  # 1 hour
                age_distribution['under_1hour'] += 1
            elif age < 86400:  # 1 day
                age_distribution['1hour_to_1day'] += 1
            elif age < 604800:  # 1 week
                age_distribution['1day_to_1week'] += 1
            else:
                age_distribution['over_1week'] += 1
                
        return {
            'size_limit': self.size_limit,
            'current_size': self.current_size,
            'utilization': self.current_size / self.size_limit if self.size_limit > 0 else 0,
            'entry_count': len(self.index),
            'by_type': type_counts,
            'age_distribution': age_distribution,
            'directory': self.directory
        }


class TieredCacheManager:
    """Manages hierarchical caching with Adaptive Replacement policy.
    
    This class coordinates multiple cache tiers, providing a unified interface
    for content retrieval and storage with automatic migration between tiers.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the tiered cache system.
        
        Args:
            config: Configuration dictionary for cache tiers
                {
                    'memory_cache_size': 100MB,
                    'local_cache_size': 1GB,
                    'local_cache_path': '/path/to/cache',
                    'max_item_size': 50MB,
                    'min_access_count': 2,
                    'enable_memory_mapping': True
                }
        """
        self.config = config or {
            'memory_cache_size': 100 * 1024 * 1024,  # 100MB
            'local_cache_size': 1 * 1024 * 1024 * 1024,  # 1GB
            'local_cache_path': os.path.expanduser('~/.ipfs_cache'),
            'max_item_size': 50 * 1024 * 1024,  # 50MB
            'min_access_count': 2,
            'enable_memory_mapping': True
        }
        
        # Initialize cache tiers with enhanced ARC implementation
        arc_config = self.config.get('arc', {})
        self.memory_cache = ARCache(
            maxsize=self.config['memory_cache_size'],
            config=arc_config
        )
        self.disk_cache = DiskCache(
            directory=self.config['local_cache_path'],
            size_limit=self.config['local_cache_size']
        )
        
        # Log configuration
        logger.info(
            f"Initialized enhanced ARC cache with {self.config['memory_cache_size']/1024/1024:.1f}MB memory, "
            f"{self.config['local_cache_size']/1024/1024/1024:.1f}GB disk cache, "
            f"ghost_list_size={arc_config.get('ghost_list_size', 1024)}"
        )
        
        # Memory-mapped file tracking
        self.enable_mmap = self.config.get('enable_memory_mapping', True)
        self.mmap_store = {}  # path -> (file_obj, mmap_obj)
        
        # Access statistics for heat scoring
        self.access_stats = {}
        
        logger.info(f"Initialized tiered cache system with {self.config['memory_cache_size']/1024/1024:.1f}MB memory cache, "
                   f"{self.config['local_cache_size']/1024/1024/1024:.1f}GB disk cache")
        
    def get(self, key: str) -> Optional[bytes]:
        """Get content from the fastest available cache tier.
        
        Args:
            key: CID or identifier of the content
            
        Returns:
            Content if found, None otherwise
        """
        # Try memory cache first (fastest)
        content = self.memory_cache.get(key)
        if content is not None:
            self._update_stats(key, 'memory_hit')
            return content
            
        # Try disk cache next
        content = self.disk_cache.get(key)
        if content is not None:
            # Promote to memory cache if it fits
            if len(content) <= self.config['max_item_size']:
                self.memory_cache.put(key, content)
                logger.debug(f"Promoted {key} from disk to memory cache")
            self._update_stats(key, 'disk_hit')
            return content
            
        # Cache miss
        self._update_stats(key, 'miss')
        return None
        
    def get_mmap(self, key: str) -> Optional[mmap.mmap]:
        """Get content as a memory-mapped file for large items.
        
        Args:
            key: CID or identifier of the content
            
        Returns:
            Memory-mapped file object if found and mmap is enabled, None otherwise
        """
        if not self.enable_mmap:
            return None
            
        # Check if already memory-mapped
        if key in self.mmap_store:
            self._update_stats(key, 'mmap_hit')
            return self.mmap_store[key][1]  # Return mmap object
            
        # Not mapped yet, check disk cache
        content = self.disk_cache.get(key)
        if content is None:
            self._update_stats(key, 'miss')
            return None
            
        # Create temp file and memory-map it
        try:
            fd, temp_path = tempfile.mkstemp()
            with os.fdopen(fd, "wb") as f:
                f.write(content)
            
            # Memory map the file - use string mode flag, not int
            file_obj = open(temp_path, "rb")
            mmap_obj = mmap.mmap(
                file_obj.fileno(),
                0,
                access=mmap.ACCESS_READ
            )
            
            # Track for cleanup
            self.mmap_store[key] = (file_obj, mmap_obj, temp_path)
            
            self._update_stats(key, 'mmap_create')
            return mmap_obj
            
        except Exception as e:
            logger.error(f"Error creating memory-mapped file for {key}: {e}")
            return None
        
    def put(self, key: str, content: bytes, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Store content in appropriate cache tiers.
        
        Args:
            key: CID or identifier of the content
            content: Content to store
            metadata: Additional metadata for the content
            
        Returns:
            True if stored successfully, False otherwise
        """
        if not isinstance(content, bytes):
            logger.warning(f"Cache only accepts bytes, got {type(content)}")
            return False
            
        size = len(content)
        
        # Always store in disk cache for persistence
        disk_result = self.disk_cache.put(key, content, metadata)
        
        # Store in memory cache if size appropriate
        memory_result = False
        if size <= self.config['max_item_size']:
            memory_result = self.memory_cache.put(key, content)
            
        # Update metadata
        if metadata is None:
            metadata = {}
            
        current_time = time.time()
        access_metadata = {
            'size': size,
            'added_time': current_time,
            'last_access': current_time,
            'access_count': 1,
            'tiers': []
        }
        
        if memory_result:
            access_metadata['tiers'].append('memory')
        if disk_result:
            access_metadata['tiers'].append('disk')
            
        # Add to access stats
        self._update_stats(key, 'put', access_metadata)
        
        return disk_result or memory_result
        
    def _update_stats(self, key: str, access_type: str, 
                     metadata: Optional[Dict[str, Any]] = None) -> None:
        """Update access statistics for content item.
        
        Args:
            key: CID or identifier of the content
            access_type: Type of access (memory_hit, disk_hit, miss, put)
            metadata: Additional metadata for new entries
        """
        current_time = time.time()
        
        if key not in self.access_stats:
            # Initialize stats for new items
            self.access_stats[key] = {
                'access_count': 0,
                'first_access': current_time,
                'last_access': current_time,
                'tier_hits': {'memory': 0, 'disk': 0, 'mmap': 0, 'miss': 0},
                'heat_score': 0.0,
                'size': metadata.get('size', 0) if metadata else 0
            }
        
        stats = self.access_stats[key]
        stats['access_count'] += 1
        stats['last_access'] = current_time
        
        # Update hit counters
        if access_type == 'memory_hit':
            stats['tier_hits']['memory'] += 1
        elif access_type == 'disk_hit':
            stats['tier_hits']['disk'] += 1
        elif access_type == 'mmap_hit' or access_type == 'mmap_create':
            stats['tier_hits']['mmap'] += 1
        elif access_type == 'miss':
            stats['tier_hits']['miss'] += 1
            
        # Update size if provided
        if metadata and 'size' in metadata:
            stats['size'] = metadata['size']
            
        # Recalculate heat score
        age = stats['last_access'] - stats['first_access']
        frequency = stats['access_count']
        recency = 1.0 / (1.0 + (current_time - stats['last_access']) / 3600)  # Decay by hour
        
        # Heat formula: combination of frequency and recency with age boost
        stats['heat_score'] = frequency * recency * (1 + math.log(1 + age / 86400))
        
    def evict(self, target_size: Optional[int] = None) -> int:
        """Intelligent eviction based on heat scores and tier.
        
        Args:
            target_size: Target amount of memory to free (default: 10% of memory cache)
            
        Returns:
            Amount of memory freed in bytes
        """
        if target_size is None:
            # Default to 10% of memory cache
            target_size = self.config['memory_cache_size'] / 10
            
        # Find coldest items for eviction
        items = sorted(
            self.access_stats.items(),
            key=lambda x: x[1]['heat_score']
        )
        
        freed = 0
        evicted_count = 0
        
        for key, stats in items:
            if freed >= target_size:
                break
                
            # Only evict from memory cache here
            size = stats.get('size', 0)
            
            if key in self.memory_cache:
                self.memory_cache.get(key)  # This will trigger ARCache's internal eviction
                freed += size
                evicted_count += 1
                logger.debug(f"Evicted {key} from memory cache")
                
            # Clean up any memory-mapped files
            if key in self.mmap_store:
                file_obj, mmap_obj, temp_path = self.mmap_store[key]
                try:
                    mmap_obj.close()
                    file_obj.close()
                    os.remove(temp_path)
                except Exception as e:
                    logger.error(f"Error cleaning up memory-mapped file for {key}: {e}")
                del self.mmap_store[key]
                freed += size
                
        logger.debug(f"Evicted {evicted_count} items, freed {freed} bytes")
        return freed
        
    def clear(self, tiers: Optional[List[str]] = None) -> None:
        """Clear specified cache tiers or all if not specified.
        
        Args:
            tiers: List of tiers to clear ('memory', 'disk', 'mmap')
        """
        if tiers is None or 'memory' in tiers:
            self.memory_cache.clear()
            logger.debug("Cleared memory cache")
            
        if tiers is None or 'disk' in tiers:
            self.disk_cache.clear()
            logger.debug("Cleared disk cache")
            
        if tiers is None or 'mmap' in tiers:
            # Clean up memory-mapped files
            for key, (file_obj, mmap_obj, temp_path) in self.mmap_store.items():
                try:
                    mmap_obj.close()
                    file_obj.close()
                    os.remove(temp_path)
                except Exception as e:
                    logger.error(f"Error cleaning up memory-mapped file for {key}: {e}")
            self.mmap_store = {}
            logger.debug("Cleared memory-mapped files")
        
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics about all cache tiers.
        
        Returns:
            Dictionary with detailed cache statistics
        """
        memory_stats = self.memory_cache.get_stats()
        disk_stats = self.disk_cache.get_stats()
        
        # Calculate aggregate statistics
        total_storage = memory_stats['current_size'] + disk_stats['current_size']
        
        # Calculate hit rates
        memory_hits = sum(stats['tier_hits']['memory'] for stats in self.access_stats.values())
        disk_hits = sum(stats['tier_hits']['disk'] for stats in self.access_stats.values())
        mmap_hits = sum(stats['tier_hits']['mmap'] for stats in self.access_stats.values())
        misses = sum(stats['tier_hits']['miss'] for stats in self.access_stats.values())
        
        total_requests = memory_hits + disk_hits + mmap_hits + misses
        hit_rate = (memory_hits + disk_hits + mmap_hits) / max(1, total_requests)
        
        # Enhanced ARC metrics
        arc_metrics = {}
        if hasattr(self.memory_cache, 'get_arc_metrics'):
            arc_metrics = self.memory_cache.get_arc_metrics()
        else:
            # Extract ARC-specific metrics from memory_stats
            arc_metrics = {
                'ghost_entries': memory_stats.get('ghost_entries', {}),
                'arc_balance': memory_stats.get('arc_balance', {}),
                'T1_T2_balance': {
                    'T1_percent': memory_stats.get('T1', {}).get('percent', 0),
                    'T2_percent': memory_stats.get('T2', {}).get('percent', 0)
                }
            }
        
        return {
            'timestamp': time.time(),
            'hit_rate': hit_rate,
            'total_storage': total_storage,
            'total_items': len(self.access_stats),
            'memory_cache': memory_stats,
            'disk_cache': disk_stats,
            'mmap_files': len(self.mmap_store),
            'hits': {
                'memory': memory_hits,
                'disk': disk_hits,
                'mmap': mmap_hits,
                'miss': misses
            },
            'arc_metrics': arc_metrics,  # Enhanced ARC metrics
            'config': self.config,
            'adaptivity_metrics': {
                'ghost_list_hit_rate': arc_metrics.get('ghost_entries', {}).get('hit_rate', 0),
                'p_adaptations': arc_metrics.get('arc_balance', {}).get('p_adjustments', 0),
                'T1_T2_ratio': memory_stats.get('T1', {}).get('count', 0) / max(1, memory_stats.get('T2', {}).get('count', 0)),
                'B1_B2_ratio': arc_metrics.get('ghost_entries', {}).get('b1_b2_ratio', 1.0)
            }
        }