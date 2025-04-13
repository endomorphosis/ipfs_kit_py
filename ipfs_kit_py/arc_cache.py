"""
Adaptive Replacement Cache (ARC) for IPFS content.

This module implements an Adaptive Replacement Cache that balances between 
recency and frequency of access for optimal caching performance.
"""

import logging
from typing import Dict, Any, Optional, Set, Tuple, List, Union
import time

from .api_stability import experimental_api, beta_api, stable_api
import math
import mmap
import os
import shutil
import tempfile
import time
import uuid
import json
import collections
from collections import defaultdict
import datetime
import concurrent.futures
import struct
import hashlib
import array
import bisect
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Deque, Iterator, Callable

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    from pyarrow import compute as pc
    from pyarrow.dataset import dataset
    HAS_PYARROW = True
except ImportError:
    HAS_PYARROW = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# Check for optional mmh3 package (faster hashing for probabilistic data structures)
try:
    import mmh3
    HAS_MMH3 = True
except ImportError:
    HAS_MMH3 = False

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
        self.ghost_list_size = self.config.get("ghost_list_size", 1024)

        # Target size for T1 (p is adaptive)
        self.p = self.config.get("initial_p", 0)
        self.max_p = self.maxsize * self.config.get(
            "max_p_percent", 0.5
        )  # p can grow up to 50% of cache

        # Weights for heat score calculation
        self.frequency_weight = self.config.get("frequency_weight", 0.7)
        self.recency_weight = self.config.get("recency_weight", 0.3)
        self.recent_access_boost = self.config.get("access_boost", 2.0)
        self.heat_decay_hours = self.config.get("heat_decay_hours", 1.0)

        # How often to prune ghost lists (in items)
        self.ghost_list_pruning = self.config.get("ghost_list_pruning", 128)

        # Enable detailed performance tracking
        self.enable_stats = self.config.get("enable_stats", True)

        # Access statistics for items
        self.access_stats = {}

        # Performance metrics
        if self.enable_stats:
            self.stats = {
                "hits": {"t1": 0, "t2": 0, "b1": 0, "b2": 0},
                "misses": 0,
                "operations": 0,
                "evictions": {"t1": 0, "t2": 0},
                "promotions": {"b1_to_t2": 0, "b2_to_t2": 0, "t1_to_t2": 0},
                "p_adjustments": 0,
                "ghost_list_hits": 0,
            }

    def __contains__(self, key: str) -> bool:
        """Check if a key is in the cache.

        Args:
            key: CID or identifier of the content

        Returns:
            True if the key is in the cache, False otherwise
        """
        return key in self.T1 or key in self.T2

    def contains(self, key: str) -> bool:
        """Check if a key is in the cache (convenience method for API consistency).

        Args:
            key: CID or identifier of the content

        Returns:
            True if the key is in the cache, False otherwise
        """
        return key in self
        
    def evict(self, key: str) -> bool:
        """Explicitly evict an item from the cache.
        
        Args:
            key: CID or identifier of the content to evict
            
        Returns:
            True if the item was evicted, False if it wasn't in the cache
        """
        # Check if in T1
        if key in self.T1:
            value = self.T1.pop(key)
            size = len(value)
            self.T1_size -= size
            self.current_size -= size
            
            # Add to B1 ghost list
            self.B1[key] = True
            
            # Update stats
            if self.enable_stats:
                self.stats["evictions"]["t1"] += 1
                
            logger.debug(f"Explicitly evicted {key} ({size} bytes) from T1 to B1 ghost list")
            return True
            
        # Check if in T2
        if key in self.T2:
            value = self.T2.pop(key)
            size = len(value)
            self.T2_size -= size
            self.current_size -= size
            
            # Add to B2 ghost list
            self.B2[key] = True
            
            # Update stats
            if self.enable_stats:
                self.stats["evictions"]["t2"] += 1
                
            logger.debug(f"Explicitly evicted {key} ({size} bytes) from T2 to B2 ghost list")
            return True
            
        # Not in cache
        return False

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
                self.stats["p_adjustments"] += 1
                self.stats["hits"]["b1"] += 1
                self.stats["ghost_list_hits"] += 1

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
                self.stats["promotions"]["b1_to_t2"] += 1

            return True

        # Case 2: key in B2 (frequently evicted)
        if key in self.B2:
            # Decrease the target size for T2
            adjustment = max(len(self.B1) // max(len(self.B2), 1), 1)
            old_p = self.p
            self.p = max(self.p - adjustment, 0)

            # Record p adjustment if significant
            if self.enable_stats and abs(self.p - old_p) > 0:
                self.stats["p_adjustments"] += 1
                self.stats["hits"]["b2"] += 1
                self.stats["ghost_list_hits"] += 1

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
                self.stats["promotions"]["b2_to_t2"] += 1

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
        evict_key = min(self.T1.keys(), key=lambda k: self.access_stats[k]["last_access"])
        evict_value = self.T1.pop(evict_key)

        # Update size tracking
        evict_size = len(evict_value)
        self.T1_size -= evict_size

        # Add to B1 ghost list
        self.B1[evict_key] = True

        # Clean up extremely old items from B1 when it gets too large
        if len(self.B1) > self.ghost_list_size:
            # Sort by last access time and remove oldest entries
            items_to_remove = (
                len(self.B1) - self.ghost_list_size + (self.ghost_list_size // 5)
            )  # Remove extra 20% to avoid frequent pruning
            oldest_keys = sorted(
                self.B1.keys(), key=lambda k: self.access_stats.get(k, {}).get("last_access", 0)
            )[:items_to_remove]

            for old_key in oldest_keys:
                self.B1.pop(old_key)

            logger.debug(f"Pruned {len(oldest_keys)} old entries from B1 ghost list")

        # Track eviction in stats
        if self.enable_stats:
            self.stats["evictions"]["t1"] += 1

        logger.debug(f"Evicted {evict_key} ({evict_size} bytes) from T1 to B1 ghost list")

    def _evict_from_t2(self) -> None:
        """Evict an item from T2 (frequent cache).

        In the ARC algorithm, items evicted from T2 go into the B2 ghost list,
        which helps track items that were frequently accessed but had to be removed.
        """
        if not self.T2:
            return

        # Find item to evict (least heat score)
        evict_key = min(self.T2.keys(), key=lambda k: self.access_stats[k]["heat_score"])
        evict_value = self.T2.pop(evict_key)

        # Update size tracking
        evict_size = len(evict_value)
        self.T2_size -= evict_size

        # Add to B2 ghost list
        self.B2[evict_key] = True

        # Clean up ghost list when it gets too large
        if len(self.B2) > self.ghost_list_size:
            # Sort by heat score and remove coldest entries
            items_to_remove = (
                len(self.B2) - self.ghost_list_size + (self.ghost_list_size // 5)
            )  # Remove extra 20%
            coldest_keys = sorted(
                self.B2.keys(), key=lambda k: self.access_stats.get(k, {}).get("heat_score", 0)
            )[:items_to_remove]

            for cold_key in coldest_keys:
                self.B2.pop(cold_key)

            logger.debug(f"Pruned {len(coldest_keys)} cold entries from B2 ghost list")

        # Track eviction in stats
        if self.enable_stats:
            self.stats["evictions"]["t2"] += 1

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
            self.stats["operations"] += 1

        # Initialize stats for new items
        if key not in self.access_stats:
            self.access_stats[key] = {
                "first_access": current_time,
                "last_access": current_time,
                "access_count": 0,
                "heat_score": 0.0,
                "hits": {"t1": 0, "t2": 0, "b1": 0, "b2": 0, "miss": 0},
            }

        stats = self.access_stats[key]
        stats["access_count"] += 1
        stats["last_access"] = current_time

        # Update hit counters
        if access_type == "hit_t1":
            stats["hits"]["t1"] += 1
            if self.enable_stats:
                self.stats["hits"]["t1"] += 1
        elif access_type == "hit_t2":
            stats["hits"]["t2"] += 1
            if self.enable_stats:
                self.stats["hits"]["t2"] += 1
        elif access_type == "miss":
            stats["hits"]["miss"] += 1
            if self.enable_stats:
                self.stats["misses"] += 1

        # Compute heat score using the configurable weights and parameters
        age = max(0.001, current_time - stats["first_access"])  # Age in seconds (avoid div by 0)
        recency = 1.0 / (
            1.0 + (current_time - stats["last_access"]) / (3600 * self.heat_decay_hours)
        )
        frequency = stats["access_count"] / age  # Accesses per second

        # Boost factor for items that have been accessed recently
        recent_access_threshold = 3600 * self.heat_decay_hours
        recent_boost = (
            self.recent_access_boost
            if (current_time - stats["last_access"]) < recent_access_threshold
            else 1.0
        )

        # Combine factors into heat score using configurable weights
        stats["heat_score"] = (
            frequency * self.frequency_weight + recency * self.recency_weight
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
            total_accesses = self.stats["operations"]
            if total_accesses > 0:
                t1_hits = self.stats["hits"]["t1"]
                t2_hits = self.stats["hits"]["t2"]
                ghost_hits = self.stats["ghost_list_hits"]

                t1_hit_rate = t1_hits / total_accesses
                t2_hit_rate = t2_hits / total_accesses
                ghost_hit_rate = ghost_hits / total_accesses

        # Comprehensive statistics with ARC-specific metrics
        stats = {
            "maxsize": self.maxsize,
            "current_size": self.current_size,
            "utilization": self.current_size / self.maxsize if self.maxsize > 0 else 0,
            "item_count": len(self.T1) + len(self.T2),
            "hit_rate": hit_rate,
            "T1": {
                "count": len(self.T1),
                "size": self.T1_size,
                "percent": len(self.T1) / max(1, len(self.T1) + len(self.T2)) * 100,
                "hit_rate": t1_hit_rate,
            },
            "T2": {
                "count": len(self.T2),
                "size": self.T2_size,
                "percent": len(self.T2) / max(1, len(self.T1) + len(self.T2)) * 100,
                "hit_rate": t2_hit_rate,
            },
            "ghost_entries": {
                "B1": len(self.B1),
                "B2": len(self.B2),
                "total": len(self.B1) + len(self.B2),
                "hit_rate": ghost_hit_rate,
            },
            "arc_balance": {
                "p": self.p,
                "p_percent": self.p / self.maxsize if self.maxsize > 0 else 0,
                "max_p": self.max_p,
                "p_adjustments": self.stats.get("p_adjustments", 0) if self.enable_stats else 0,
            },
            "evictions": self.stats.get("evictions", {}) if self.enable_stats else {},
            "promotions": self.stats.get("promotions", {}) if self.enable_stats else {},
            "configuration": {
                "ghost_list_size": self.ghost_list_size,
                "frequency_weight": self.frequency_weight,
                "recency_weight": self.recency_weight,
                "heat_decay_hours": self.heat_decay_hours,
                "recent_access_boost": self.recent_access_boost,
            },
        }

        # Calculate balance metrics to see if the cache is appropriately adapting
        if len(self.T1) + len(self.T2) > 0:
            # Measure how well the cache is handling the workload
            t1_t2_ratio = len(self.T1) / max(1, len(self.T2))
            stats["arc_balance"]["t1_t2_ratio"] = t1_t2_ratio

            # Measure ghost list effectiveness
            if len(self.B1) + len(self.B2) > 0:
                b1_b2_ratio = len(self.B1) / max(1, len(self.B2))
                stats["ghost_entries"]["b1_b2_ratio"] = b1_b2_ratio

            # Calculate adaptation effectiveness
            if self.enable_stats and self.stats["operations"] > 0:
                adaptivity = self.stats.get("p_adjustments", 0) / self.stats["operations"]
                stats["arc_balance"]["adaptivity"] = adaptivity

        return stats

    def _calculate_hit_rate(self) -> float:
        """Calculate the cache hit rate.

        Returns:
            Hit rate as a float between 0 and 1
        """
        hits = sum(
            stats["hits"]["t1"] + stats["hits"]["t2"] for stats in self.access_stats.values()
        )
        misses = sum(stats["hits"]["miss"] for stats in self.access_stats.values())
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
            ghost_hits = self.stats.get("ghost_list_hits", 0)
            total_operations = self.stats.get("operations", 0)

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
        p_adjustments = self.stats.get("p_adjustments", 0) if self.enable_stats else 0
        adaptivity_rate = p_adjustments / max(1, total_operations)

        # Heat score distribution
        heat_scores = [stats["heat_score"] for stats in self.access_stats.values()]
        heat_metrics = {}

        if heat_scores:
            heat_metrics = {
                "min": min(heat_scores),
                "max": max(heat_scores),
                "avg": sum(heat_scores) / len(heat_scores),
            }

            # Calculate quartiles if we have enough data
            if len(heat_scores) >= 4:
                sorted_scores = sorted(heat_scores)
                q1_idx = len(sorted_scores) // 4
                q2_idx = len(sorted_scores) // 2
                q3_idx = q1_idx * 3

                heat_metrics["quartiles"] = {
                    "q1": sorted_scores[q1_idx],
                    "q2": sorted_scores[q2_idx],  # median
                    "q3": sorted_scores[q3_idx],
                }

        return {
            "algorithm": "Adaptive Replacement Cache (ARC)",
            "ghost_entries": {
                "B1": len(self.B1),
                "B2": len(self.B2),
                "total": len(self.B1) + len(self.B2),
                "max_size": self.ghost_list_size,
                "utilization": ghost_utilization,
                "hit_rate": ghost_hit_rate,
                "b1_b2_ratio": b1_b2_ratio,
            },
            "cache_composition": {
                "T1_count": len(self.T1),
                "T2_count": len(self.T2),
                "T1_percent": t1_percent,
                "T2_percent": t2_percent,
                "t1_t2_ratio": t1_t2_ratio,
            },
            "arc_balance": {
                "p": self.p,
                "p_percent": self.p / self.maxsize if self.maxsize > 0 else 0,
                "max_p": self.max_p,
                "p_adjustments": p_adjustments,
                "adaptivity_rate": adaptivity_rate,
            },
            "heat_score_metrics": heat_metrics,
            "configuration": {
                "frequency_weight": self.frequency_weight,
                "recency_weight": self.recency_weight,
                "heat_decay_hours": self.heat_decay_hours,
                "access_boost": self.recent_access_boost,
            },
            "performance": {
                "hit_rate": self._calculate_hit_rate(),
                "utilization": self.current_size / self.maxsize if self.maxsize > 0 else 0,
                "operations": total_operations,
                "evictions": self.stats.get("evictions", {}) if self.enable_stats else {},
                "promotions": self.stats.get("promotions", {}) if self.enable_stats else {},
            },
        }


from .api_stability import stable_api, beta_api, experimental_api, deprecated

class BloomFilter:
    """Bloom filter for fast set membership tests with tunable false positive rate.
    
    A Bloom filter is a space-efficient probabilistic data structure that is used to test
    whether an element is a member of a set. False positives are possible, but false 
    negatives are not. Elements can be added to the set, but not removed.
    
    This implementation uses multiple hash functions for better distribution and
    provides methods to:
    - Add elements to the filter
    - Test if elements are in the filter
    - Estimate the current false positive probability
    - Save/load the filter state
    - Merge multiple filters
    
    It's highly effective for early negative filtering in queries where we can 
    quickly determine that a partition doesn't contain certain CIDs.
    """
    
    @beta_api(since="0.19.0")
    def __init__(self, capacity: int = 10000, error_rate: float = 0.01, seed: int = 42):
        """Initialize a Bloom filter with specified capacity and error rate.
        
        Args:
            capacity: Expected number of elements
            error_rate: Desired false positive rate (0 to 1)
            seed: Random seed for hash functions
        """
        if not (0 < error_rate < 1):
            raise ValueError("Error rate must be between 0 and 1")
            
        # Calculate optimal filter size and number of hash functions
        self.capacity = capacity
        self.error_rate = error_rate
        
        # Calculate optimal bit array size (m = -capacity * ln(error_rate) / (ln(2)^2))
        # Formula from: https://en.wikipedia.org/wiki/Bloom_filter#Optimal_number_of_hash_functions
        n = capacity
        p = error_rate
        m = math.ceil(-n * math.log(p) / (math.log(2) ** 2))
        
        # Calculate optimal number of hash functions (k = m/n * ln(2))
        k = math.ceil((m / n) * math.log(2))
        
        # Create the bit array (represented as an array of bytes)
        self.bit_size = m
        self.bit_array_size = (m + 7) // 8  # Number of bytes needed
        self.bit_array = bytearray(self.bit_array_size)
        
        # Set optimal hash functions count (min 2, max 16)
        self.hash_count = max(2, min(k, 16))
        
        # Set seed for hash functions
        self.seed = seed
        
        # Track number of elements added
        self.count = 0
        
    def _get_hash_values(self, item: Any) -> List[int]:
        """Generate multiple hash values for an item.
        
        Args:
            item: Item to hash
            
        Returns:
            List of hash values
        """
        # Convert item to bytes if needed
        if not isinstance(item, bytes):
            if isinstance(item, str):
                item_bytes = item.encode('utf-8')
            else:
                item_bytes = str(item).encode('utf-8')
        else:
            item_bytes = item
            
        # Generate multiple hash values using either mmh3 (faster) or built-in hashlib
        if HAS_MMH3:
            # Use MurmurHash3 for faster hashing
            hash_values = []
            for i in range(self.hash_count):
                # Use different seed for each hash function
                h = mmh3.hash(item_bytes, self.seed + i) % self.bit_size
                hash_values.append(h)
        else:
            # Use double hashing to simulate multiple hash functions
            # Based on: https://www.eecs.harvard.edu/~michaelm/postscripts/rsa2008.pdf
            h1 = int.from_bytes(hashlib.md5(item_bytes).digest()[:8], byteorder='little')
            h2 = int.from_bytes(hashlib.sha1(item_bytes).digest()[:8], byteorder='little')
            
            hash_values = [(h1 + i * h2) % self.bit_size for i in range(self.hash_count)]
            
        return hash_values
        
    def add(self, item: Any) -> None:
        """Add an item to the Bloom filter.
        
        Args:
            item: Item to add
        """
        hash_values = self._get_hash_values(item)
        
        for h in hash_values:
            # Calculate byte index and bit position
            byte_index = h // 8
            bit_position = h % 8
            
            # Set the bit
            self.bit_array[byte_index] |= (1 << bit_position)
        
        self.count += 1
        
    def batch_add(self, items: List[Any]) -> None:
        """Add multiple items to the Bloom filter.
        
        Args:
            items: List of items to add
        """
        for item in items:
            self.add(item)
    
    def contains(self, item: Any) -> bool:
        """Check if an item might be in the set.
        
        Args:
            item: Item to check
            
        Returns:
            True if the item might be in the set, False if definitely not
        """
        hash_values = self._get_hash_values(item)
        
        for h in hash_values:
            # Calculate byte index and bit position
            byte_index = h // 8
            bit_position = h % 8
            
            # Check if bit is set
            if not (self.bit_array[byte_index] & (1 << bit_position)):
                return False
                
        return True
        
    def batch_contains(self, items: List[Any]) -> List[bool]:
        """Check if multiple items might be in the set.
        
        Args:
            items: List of items to check
            
        Returns:
            List of booleans indicating set membership
        """
        return [self.contains(item) for item in items]
    
    def current_false_positive_rate(self) -> float:
        """Estimate the current false positive rate based on fill level.
        
        Returns:
            Estimated false positive probability
        """
        # Probability formula: (1 - e^(-k*n/m))^k
        # where k = hash functions, n = inserted elements, m = bit array size
        k = self.hash_count
        n = self.count
        m = self.bit_size
        
        if m == 0:
            return 1.0
            
        return (1 - math.exp(-(k * n) / m)) ** k
        
    def serialized_size(self) -> int:
        """Get the size of the serialized Bloom filter in bytes.
        
        Returns:
            Size in bytes
        """
        # Size = bit array + metadata
        return self.bit_array_size + 40  # Metadata ~40 bytes
    
    def reset(self) -> None:
        """Reset the Bloom filter to its initial empty state."""
        self.bit_array = bytearray(self.bit_array_size)
        self.count = 0
        
    def serialize(self) -> bytes:
        """Serialize the Bloom filter to bytes.
        
        Returns:
            Serialized filter as bytes
        """
        # Format: 
        # - capacity (8 bytes)
        # - error_rate (8 bytes)
        # - hash_count (4 bytes)
        # - count (8 bytes)
        # - seed (4 bytes)
        # - bit_array (variable)
        
        metadata = struct.pack('>QdIQI', 
                              self.capacity,
                              self.error_rate,
                              self.hash_count,
                              self.count,
                              self.seed)
                              
        return metadata + bytes(self.bit_array)
        
    @classmethod
    def deserialize(cls, data: bytes) -> 'BloomFilter':
        """Create a Bloom filter from serialized data.
        
        Args:
            data: Serialized filter data
            
        Returns:
            Deserialized BloomFilter
        """
        header_size = struct.calcsize('>QdIQI')
        
        if len(data) < header_size:
            raise ValueError("Serialized data is too short")
            
        # Unpack metadata
        capacity, error_rate, hash_count, count, seed = struct.unpack('>QdIQI', data[:header_size])
        
        # Create filter with same parameters
        bloom_filter = cls(capacity=capacity, error_rate=error_rate, seed=seed)
        bloom_filter.hash_count = hash_count
        bloom_filter.count = count
        
        # Load bit array
        bloom_filter.bit_array = bytearray(data[header_size:])
        
        return bloom_filter
        
    def merge(self, other: 'BloomFilter') -> bool:
        """Merge another Bloom filter into this one.
        
        Args:
            other: Another BloomFilter instance
            
        Returns:
            True if merge was successful, False otherwise
        """
        # Check if filters are compatible
        if (self.bit_size != other.bit_size or
            self.hash_count != other.hash_count):
            return False
            
        # Merge bit arrays with OR operation
        for i in range(min(len(self.bit_array), len(other.bit_array))):
            self.bit_array[i] |= other.bit_array[i]
            
        # Update count (this is approximate after merging)
        self.count += other.count
        
        return True


class HyperLogLog:
    """HyperLogLog implementation for efficient cardinality estimation.
    
    HyperLogLog is a probabilistic algorithm for estimating the number of distinct
    elements in a dataset with minimal memory usage. It's particularly useful for:
    - Estimating unique CIDs in a large dataset without storing all CIDs
    - Approximating query result sizes before executing expensive operations
    - Tracking dataset growth over time
    - Supporting cardinality-based query optimization
    
    This implementation includes:
    - Configurable precision for memory vs. accuracy tradeoff
    - Bias correction for accurate small cardinality estimation
    - Serialization/deserialization for persistence
    - Merging capability for distributed operation
    """
    
    @beta_api(since="0.19.0")
    def __init__(self, precision: int = 14, seed: int = 42):
        """Initialize a HyperLogLog counter.
        
        Args:
            precision: Precision parameter (p), determines accuracy vs. memory usage
                     Higher values increase accuracy but use more memory
                     Valid values: 4-16 (recommended: 10-14)
            seed: Random seed for hash function
        """
        if not 4 <= precision <= 16:
            raise ValueError("Precision must be between 4 and 16")
            
        self.precision = precision
        self.seed = seed
        
        # Number of registers (m = 2^precision)
        self.m = 1 << precision
        
        # Bit mask to extract register index
        self.index_mask = self.m - 1
        
        # Initialize registers
        self.registers = bytearray(self.m)
        
        # Bias correction for small cardinalities
        self.alpha = self._get_alpha(self.m)
        
    def _get_alpha(self, m: int) -> float:
        """Calculate the alpha correction factor based on register count.
        
        Args:
            m: Number of registers
            
        Returns:
            Alpha correction factor
        """
        if m == 16:
            return 0.673
        elif m == 32:
            return 0.697
        elif m == 64:
            return 0.709
        else:
            # For m >= 128, alpha = 0.7213/(1 + 1.079/m)
            return 0.7213 / (1.0 + 1.079 / m)
    
    def _hash(self, item: Any) -> int:
        """Hash an item to a 64-bit value.
        
        Args:
            item: Item to hash
            
        Returns:
            64-bit hash value
        """
        # Convert item to bytes if needed
        if not isinstance(item, bytes):
            if isinstance(item, str):
                item_bytes = item.encode('utf-8')
            else:
                item_bytes = str(item).encode('utf-8')
        else:
            item_bytes = item
            
        # Use MurmurHash3 if available
        if HAS_MMH3:
            # Get 128-bit hash and take first 64 bits
            h1, h2 = mmh3.hash64(item_bytes, self.seed)
            return h1
        else:
            # Use SHA-256 and take first 8 bytes
            h = hashlib.sha256(item_bytes).digest()
            return int.from_bytes(h[:8], byteorder='little')
    
    def add(self, item: Any) -> None:
        """Add an item to the HyperLogLog counter.
        
        Args:
            item: Item to add
        """
        # Get 64-bit hash of the item
        x = self._hash(item)
        
        # Extract register index (first p bits)
        j = x & self.index_mask
        
        # Count leading zeros in the remaining bits (& with a mask to ignore used bits)
        w = x >> self.precision
        
        # Calculate leading zeros (+1 because we count from 1)
        leading_zeros = 1
        while w & 1 == 0 and leading_zeros <= 64 - self.precision:
            leading_zeros += 1
            w >>= 1
            
        # Update register if new value is larger
        self.registers[j] = max(self.registers[j], leading_zeros)
        
    def batch_add(self, items: List[Any]) -> None:
        """Add multiple items to the HyperLogLog counter.
        
        Args:
            items: List of items to add
        """
        for item in items:
            self.add(item)
    
    def count(self) -> int:
        """Estimate the number of distinct elements.
        
        Returns:
            Estimated cardinality
        """
        # Calculate the harmonic mean of register values
        sum_inv = 0.0
        for r in self.registers:
            sum_inv += 2 ** -r
            
        # Apply correction
        E = self.alpha * self.m ** 2 / sum_inv
        
        # Apply small/large range corrections
        if E <= 2.5 * self.m:  # Small range correction
            # Count number of registers equal to 0
            zeros = sum(1 for r in self.registers if r == 0)
            if zeros > 0:
                # Linear counting for small cardinalities
                return int(self.m * math.log(self.m / zeros))
        
        if E <= (1.0 / 30.0) * (1 << 32):  # No large range correction needed
            return int(E)
            
        # Large range correction when E > 2^32/30
        return int(-(1 << 32) * math.log(1 - E / (1 << 32)))
        
    def merge(self, other: 'HyperLogLog') -> bool:
        """Merge another HyperLogLog counter into this one.
        
        Args:
            other: Another HyperLogLog instance
            
        Returns:
            True if merge was successful, False otherwise
        """
        # Check if counters are compatible
        if self.precision != other.precision or self.m != other.m:
            return False
            
        # Merge by taking max of register values
        for i in range(self.m):
            self.registers[i] = max(self.registers[i], other.registers[i])
            
        return True
        
    def reset(self) -> None:
        """Reset the counter to its initial empty state."""
        self.registers = bytearray(self.m)
        
    def serialize(self) -> bytes:
        """Serialize the HyperLogLog counter to bytes.
        
        Returns:
            Serialized counter as bytes
        """
        # Format:
        # - precision (4 bytes)
        # - seed (4 bytes)
        # - registers (variable)
        
        header = struct.pack('>II', self.precision, self.seed)
        return header + bytes(self.registers)
        
    @classmethod
    def deserialize(cls, data: bytes) -> 'HyperLogLog':
        """Create a HyperLogLog counter from serialized data.
        
        Args:
            data: Serialized counter data
            
        Returns:
            Deserialized HyperLogLog
        """
        header_size = struct.calcsize('>II')
        
        if len(data) < header_size:
            raise ValueError("Serialized data is too short")
            
        # Unpack header
        precision, seed = struct.unpack('>II', data[:header_size])
        
        # Create counter with same parameters
        hll = cls(precision=precision, seed=seed)
        
        # Load registers
        register_data = data[header_size:]
        expected_size = 1 << precision
        
        if len(register_data) != expected_size:
            raise ValueError(f"Invalid register data size: {len(register_data)}, expected {expected_size}")
            
        hll.registers = bytearray(register_data)
        
        return hll


class CountMinSketch:
    """Count-Min Sketch for frequency estimation in data streams.
    
    A Count-Min Sketch is a probabilistic data structure for estimating frequencies
    of elements in a data stream. It provides sublinear space complexity while allowing
    for fast queries with guaranteed error bounds.
    
    This implementation features:
    - Configurable width/depth for memory vs. accuracy tradeoff
    - Conservative update optimization for improved accuracy
    - Point and heavy hitter queries
    - Serialization for persistence
    - Merging capability for distributed operation
    
    It's particularly useful for:
    - Identifying popular CIDs or content types
    - Finding frequent access patterns
    - Supporting intelligent prefetching based on frequency data
    - Analyzing distribution of metadata values without storing all records
    """
    
    @beta_api(since="0.19.0")
    def __init__(self, width: int = 2048, depth: int = 5, seed: int = 42):
        """Initialize a Count-Min Sketch.
        
        Args:
            width: Number of counters per hash function (larger = more accurate)
            depth: Number of hash functions (larger = less probability of collision)
            seed: Random seed for hash functions
        """
        self.width = width
        self.depth = depth
        self.seed = seed
        
        # Initialize sketch matrix of size depth x width
        self.counters = np.zeros((depth, width), dtype=np.int32)
        
        # Track total items for statistical purposes
        self.total = 0
        
    def _get_indices(self, item: Any) -> List[int]:
        """Get hash indices for an item.
        
        Args:
            item: Item to hash
            
        Returns:
            List of hash values (one per hash function)
        """
        # Convert item to bytes if needed
        if not isinstance(item, bytes):
            if isinstance(item, str):
                item_bytes = item.encode('utf-8')
            else:
                item_bytes = str(item).encode('utf-8')
        else:
            item_bytes = item
        
        indices = []
        
        if HAS_MMH3:
            # Use MurmurHash3 for all hash functions with different seeds
            for i in range(self.depth):
                h = mmh3.hash(item_bytes, seed=self.seed + i) % self.width
                indices.append(h)
        else:
            # Use double-hashing technique with MD5 and SHA-1
            h1 = int.from_bytes(hashlib.md5(item_bytes).digest()[:8], byteorder='little')
            h2 = int.from_bytes(hashlib.sha1(item_bytes).digest()[:8], byteorder='little')
            
            for i in range(self.depth):
                # Linearly combine the two hash functions with different coefficients
                h = (h1 + i * h2) % self.width
                indices.append(h)
                
        return indices
        
    def add(self, item: Any, count: int = 1) -> None:
        """Increment counters for an item.
        
        Args:
            item: Item to add
            count: Count to add (default: 1)
        """
        if count <= 0:
            return
            
        indices = self._get_indices(item)
        
        # Update counters
        for i, index in enumerate(indices):
            self.counters[i, index] += count
            
        self.total += count
        
    def batch_add(self, items: List[Tuple[Any, int]]) -> None:
        """Add multiple items with counts to the sketch.
        
        Args:
            items: List of (item, count) tuples
        """
        for item, count in items:
            self.add(item, count)
    
    def estimate_count(self, item: Any) -> int:
        """Estimate frequency of an item.
        
        Args:
            item: Item to estimate
            
        Returns:
            Estimated frequency (minimum of all counter values)
        """
        indices = self._get_indices(item)
        
        # Use minimum count as estimate
        count = min(self.counters[i, index] for i, index in enumerate(indices))
        
        return int(count)
        
    def batch_estimate(self, items: List[Any]) -> List[int]:
        """Estimate frequencies for multiple items.
        
        Args:
            items: List of items to estimate
            
        Returns:
            List of estimated frequencies
        """
        return [self.estimate_count(item) for item in items]
        
    def heavy_hitters(self, threshold: float) -> List[Tuple[Any, int]]:
        """Find heavy hitters in a dataset using a separate item dictionary.
        
        This method is for demonstration only, as Count-Min Sketch by itself
        cannot identify the actual heavy hitter items without maintaining
        a separate dictionary of items. In practice, this would be used
        in conjunction with a separate data structure tracking candidate items.
        
        Args:
            threshold: Minimum fraction of total count to be considered a heavy hitter
            items: Dictionary of items to check
            
        Returns:
            List of (item, estimated_count) for heavy hitters
        """
        # In practice, you need to track candidate items separately
        # This is just a placeholder to demonstrate the concept
        logger.warning("Heavy hitters detection requires tracking items externally")
        return []
        
    def merge(self, other: 'CountMinSketch') -> bool:
        """Merge another Count-Min Sketch into this one.
        
        Args:
            other: Another CountMinSketch instance
            
        Returns:
            True if merge was successful, False otherwise
        """
        # Check if sketches are compatible
        if self.width != other.width or self.depth != other.depth:
            return False
            
        # Merge by adding counter values
        self.counters += other.counters
        self.total += other.total
        
        return True
        
    def reset(self) -> None:
        """Reset the sketch to its initial empty state."""
        self.counters = np.zeros((self.depth, self.width), dtype=np.int32)
        self.total = 0
        
    def error_bound(self, confidence: float = 0.95) -> float:
        """Calculate the error bound for frequency estimates.
        
        Args:
            confidence: Confidence level (0.0-1.0)
            
        Returns:
            Maximum expected absolute error with given confidence
        """
        # Error bound formula: e * n, where:
        # e = 2.718..., n = total items
        # Probability that estimate exceeds true frequency by e*n is 1/e
        # For confidence level c, error is -ln(1-c)/width * total
        
        if not 0 < confidence < 1:
            raise ValueError("Confidence must be between 0 and 1")
            
        # Calculate error bound
        return -math.log(1 - confidence) / self.width * self.total
        
    def relative_error(self, confidence: float = 0.95) -> float:
        """Calculate the relative error for frequency estimates.
        
        Args:
            confidence: Confidence level (0.0-1.0)
            
        Returns:
            Maximum expected relative error with given confidence
        """
        # A very small total count will make this meaningless
        if self.total < 100:
            return float('inf')
            
        # Relative error = absolute error / total
        return self.error_bound(confidence) / self.total
        
    def serialize(self) -> bytes:
        """Serialize the Count-Min Sketch to bytes.
        
        Returns:
            Serialized sketch as bytes
        """
        # Format:
        # - width (4 bytes)
        # - depth (4 bytes)
        # - seed (4 bytes)
        # - total (8 bytes)
        # - counters (numpy array)
        
        header = struct.pack('>IIIQ', self.width, self.depth, self.seed, self.total)
        
        # Serialize numpy array
        counter_bytes = self.counters.tobytes()
        
        return header + counter_bytes
        
    @classmethod
    def deserialize(cls, data: bytes) -> 'CountMinSketch':
        """Create a Count-Min Sketch from serialized data.
        
        Args:
            data: Serialized sketch data
            
        Returns:
            Deserialized CountMinSketch
        """
        header_size = struct.calcsize('>IIIQ')
        
        if len(data) < header_size:
            raise ValueError("Serialized data is too short")
            
        # Unpack header
        width, depth, seed, total = struct.unpack('>IIIQ', data[:header_size])
        
        # Create sketch with same parameters
        cms = cls(width=width, depth=depth, seed=seed)
        cms.total = total
        
        # Load counters
        counter_data = data[header_size:]
        expected_size = width * depth * np.dtype(np.int32).itemsize
        
        if len(counter_data) != expected_size:
            raise ValueError(f"Invalid counter data size: {len(counter_data)}, expected {expected_size}")
            
        cms.counters = np.frombuffer(counter_data, dtype=np.int32).reshape(depth, width)
        
        return cms


class MinHash:
    """MinHash implementation for estimating similarity between sets.
    
    MinHash is a technique for quickly estimating how similar two sets are.
    It's used in locality-sensitive hashing and is particularly good for:
    - Finding similar content collections
    - Identifying nearly-duplicate CIDs
    - Clustering related content
    - Supporting similarity-based queries
    
    This implementation supports:
    - Configurable signature size for accuracy vs. memory tradeoff
    - Jaccard similarity estimation
    - Efficient batch processing
    - Serialization for persistence
    """
    
    @beta_api(since="0.19.0")
    def __init__(self, num_hashes: int = 128, seed: int = 42):
        """Initialize a MinHash with specified number of hash functions.
        
        Args:
            num_hashes: Number of hash functions to use
            seed: Random seed for hash functions
        """
        self.num_hashes = num_hashes
        self.seed = seed
        
        # Initialize signature values to maximum possible value
        self.signature = np.ones(num_hashes, dtype=np.uint32) * np.iinfo(np.uint32).max
        
        # Create hash function parameters
        self.hash_coefs = self._generate_hash_params()
        
    def _generate_hash_params(self) -> List[Tuple[int, int]]:
        """Generate hash function parameters.
        
        Returns:
            List of (a, b) tuples for hash functions
        """
        # Seed random number generator
        rng = np.random.RandomState(self.seed)
        
        # Generate random coefficients for hash functions
        # Using y = (a*x + b) % PRIME formula for universal hashing
        PRIME = 2147483647  # 2^31 - 1, a Mersenne prime
        
        # Generate 'a' and 'b' coefficients for each hash function
        # 'a' should be non-zero, 'b' can be any value in [0, PRIME-1]
        a_vals = rng.randint(1, PRIME, size=self.num_hashes)
        b_vals = rng.randint(0, PRIME, size=self.num_hashes)
        
        return list(zip(a_vals, b_vals))
        
    def _hash_item(self, item: Any) -> int:
        """Hash an item to a 32-bit value.
        
        Args:
            item: Item to hash
            
        Returns:
            32-bit hash value
        """
        # Convert item to bytes if needed
        if not isinstance(item, bytes):
            if isinstance(item, str):
                item_bytes = item.encode('utf-8')
            else:
                item_bytes = str(item).encode('utf-8')
        else:
            item_bytes = item
            
        # Use MurmurHash3 if available, otherwise use FNV hash
        if HAS_MMH3:
            return mmh3.hash(item_bytes, self.seed) & 0xFFFFFFFF
        else:
            # FNV-1a hash
            FNV_PRIME = 16777619
            FNV_OFFSET = 2166136261
            
            hash_val = FNV_OFFSET
            for byte in item_bytes:
                hash_val = hash_val ^ byte
                hash_val = (hash_val * FNV_PRIME) & 0xFFFFFFFF
                
            return hash_val
    
    def add(self, item: Any) -> None:
        """Add an item to the MinHash signature.
        
        Args:
            item: Item to add
        """
        # Get base hash for the item
        hash_val = self._hash_item(item)
        
        # Apply each hash function and update signature
        PRIME = 2147483647  # 2^31 - 1
        
        for i, (a, b) in enumerate(self.hash_coefs):
            # Universal hashing function: (a*x + b) % PRIME
            h = (a * hash_val + b) % PRIME
            
            # Update signature (keep minimum value)
            if h < self.signature[i]:
                self.signature[i] = h
                
    def batch_add(self, items: List[Any]) -> None:
        """Add multiple items to the MinHash signature.
        
        Args:
            items: List of items to add
        """
        for item in items:
            self.add(item)
            
    def similarity(self, other: 'MinHash') -> float:
        """Estimate Jaccard similarity with another MinHash.
        
        Args:
            other: Another MinHash instance
            
        Returns:
            Estimated Jaccard similarity (0.0-1.0)
        """
        # Check if signatures have compatible size
        if len(self.signature) != len(other.signature):
            raise ValueError("MinHash signatures must have the same size")
            
        # Count matching positions
        matches = np.sum(self.signature == other.signature)
        
        # Estimate similarity
        return matches / len(self.signature)
        
    def reset(self) -> None:
        """Reset the MinHash to its initial empty state."""
        self.signature = np.ones(self.num_hashes, dtype=np.uint32) * np.iinfo(np.uint32).max
        
    def serialize(self) -> bytes:
        """Serialize the MinHash to bytes.
        
        Returns:
            Serialized MinHash as bytes
        """
        # Format:
        # - num_hashes (4 bytes)
        # - seed (4 bytes)
        # - signature (variable)
        
        header = struct.pack('>II', self.num_hashes, self.seed)
        
        # Serialize numpy array
        sig_bytes = self.signature.tobytes()
        
        return header + sig_bytes
        
    @classmethod
    def deserialize(cls, data: bytes) -> 'MinHash':
        """Create a MinHash from serialized data.
        
        Args:
            data: Serialized MinHash data
            
        Returns:
            Deserialized MinHash
        """
        header_size = struct.calcsize('>II')
        
        if len(data) < header_size:
            raise ValueError("Serialized data is too short")
            
        # Unpack header
        num_hashes, seed = struct.unpack('>II', data[:header_size])
        
        # Create MinHash with same parameters
        minhash = cls(num_hashes=num_hashes, seed=seed)
        
        # Load signature
        sig_data = data[header_size:]
        expected_size = num_hashes * np.dtype(np.uint32).itemsize
        
        if len(sig_data) != expected_size:
            raise ValueError(f"Invalid signature data size: {len(sig_data)}, expected {expected_size}")
            
        minhash.signature = np.frombuffer(sig_data, dtype=np.uint32)
        
        return minhash


class ParquetCIDCache:
    """Parquet-based CID cache for IPFS content with advanced partitioning strategies.
    
    This cache stores CID metadata in an efficient columnar format using Apache Parquet.
    It provides fast querying, filtering, and advanced analytics over CID data, while 
    integrating with the adaptive replacement cache system.
    
    Benefits:
    - Columnar storage for efficient queries and filters
    - Optimized for analytical queries across large CID collections
    - Schema-enforced data validation
    - Memory-efficient batch operations
    - Predicate pushdown for efficient filtering
    - Integration with PyArrow ecosystem
    - Zero-copy access via Arrow C Data Interface
    - Data type-specific prefetching optimizations
    - Efficient batch operations for multiple CIDs
    - Asynchronous APIs for non-blocking operations
    
    Performance Optimizations:
    - Batch Operations: Process multiple CIDs at once with batch_get() and batch_put()
    - Zero-Copy Access: Use Arrow C Data Interface for efficient cross-process sharing
    - Async Operations: Non-blocking I/O with async_get() and async_put()
    - Intelligent Cache Management: Predictive eviction based on access patterns
    - Read-Ahead Prefetching: Smart prefetching for commonly accessed content
    
    Advanced Partitioning Strategies:
    - Time-based: Organize by temporal patterns (hour, day, week, month, year)
      * Efficient time series analysis
      * Automatic partition pruning for time-bounded queries
      * Time-based retention policies
    
    - Content-type: Group by content types (image, video, document, etc.)
      * Optimized compression by content category
      * Efficient content type specific queries
      * Similar-content grouping for related access
    
    - Size-based: Partition by content size categories
      * Optimized storage for different content sizes
      * Performance tuning based on size characteristics
      * Efficient large vs. small content management
    
    - Access-pattern: Group by access frequency/heat
      * Hot/cold data separation
      * Tier-aware partitioning
      * Performance optimization for frequent access
    
    - Hybrid: Combine multiple strategies for complex workloads
      * Multi-level partitioning (e.g., time+content type)
      * Customized for specific workload characteristics
      * Optimal for complex query patterns
    """
    
    @stable_api(since="0.19.0")
    def __init__(self, 
                 directory: str = "~/.ipfs_parquet_cache", 
                 max_partition_rows: int = 100000,
                 auto_sync: bool = True,
                 sync_interval: int = 300,
                 enable_c_data_interface: bool = False,
                 compression_optimization: str = "auto",
                 prefetch_config: Optional[Dict[str, Any]] = None,
                 partitioning_strategy: str = "default",
                 advanced_partitioning_config: Optional[Dict[str, Any]] = None,
                 probabilistic_config: Optional[Dict[str, Any]] = None):
        """Initialize the Parquet CID cache.
        
        Args:
            directory: Directory to store Parquet files
            max_partition_rows: Maximum number of rows per partition file
            auto_sync: Whether to automatically sync in-memory data to disk
            sync_interval: How often to sync to disk in seconds
            enable_c_data_interface: Whether to enable zero-copy access via Arrow C Data Interface
            compression_optimization: Compression strategy: "auto" (analyze data), 
                                     "speed" (optimize for speed), "size" (optimize for size),
                                     or "balanced" (balance between speed and size)
            prefetch_config: Configuration for data type-specific prefetching:
                            {
                                "enable_type_specific_prefetch": True,  # Enable data type optimizations
                                "max_concurrent_prefetch": 8,           # Maximum concurrent prefetch operations
                                "parquet_prefetch": {                   # Parquet-specific settings
                                    "row_group_lookahead": 2,           # Number of row groups to prefetch ahead
                                    "prefetch_statistics": True,        # Prefetch column statistics
                                    "max_prefetch_size_mb": 64,         # Maximum prefetch size in MB
                                    "metadata_only_columns": ["cid", "size_bytes", "added_timestamp"]  # Columns for metadata-only prefetch
                                },
                                "arrow_batch_size": 10000,             # Batch size for Arrow record batches
                                "prefetch_priority": {                 # Priority tiers for prefetching
                                    "high": ["cid", "size_bytes", "heat_score"],
                                    "medium": ["added_timestamp", "source", "mimetype"],
                                    "low": ["properties", "validation_timestamp"]
                                }
                            }
            partitioning_strategy: Strategy for partitioning data:
                                  "default": Simple sequential partitioning
                                  "time": Time-based partitioning by added_timestamp
                                  "content_type": Group by content types
                                  "size": Size-based partitioning
                                  "access_pattern": Group by access frequency
                                  "hybrid": Combine multiple strategies
            advanced_partitioning_config: Configuration for advanced partitioning:
                                         {
                                             "time_partitioning": {
                                                 "interval": "day",  # "hour", "day", "week", "month", "year"
                                                 "column": "added_timestamp",  # Column to partition by
                                                 "format": "%Y-%m-%d",  # Directory format
                                                 "max_partitions": 90,  # Max number of time partitions to keep
                                             },
                                             "content_type_partitioning": {
                                                 "column": "mimetype",  # Column to partition by
                                                 "default_partition": "unknown",  # Default for missing values
                                                 "max_types": 20,  # Maximum number of content type partitions
                                                 "group_similar": True,  # Group similar types
                                             },
                                             "size_partitioning": {
                                                 "column": "size_bytes",  # Column to partition by
                                                 "boundaries": [10240, 102400, 1048576, 10485760],  # Size boundaries in bytes
                                                 "labels": ["tiny", "small", "medium", "large", "xlarge"]  # Labels for size ranges
                                             },
                                             "access_pattern_partitioning": {
                                                 "column": "heat_score",  # Column to partition by
                                                 "boundaries": [0.1, 0.5, 0.9],  # Score boundaries
                                                 "labels": ["cold", "warm", "hot", "critical"]  # Labels for partitions
                                             },
                                             "hybrid_partitioning": {
                                                 "primary": "time",  # Primary strategy
                                                 "secondary": "content_type"  # Secondary strategy
                                             }
                                         }
            probabilistic_config: Configuration for probabilistic data structures:
                                 {
                                     "enable_probabilistic": True,   # Master toggle for probabilistic features
                                     "bloom_filter": {                # Bloom filter configuration
                                         "enabled": True,
                                         "capacity": 10000,           # Expected number of elements
                                         "error_rate": 0.01,          # False positive rate (1%)
                                         "per_partition": True,       # Create filter per partition
                                         "serialize": True            # Whether to persist filters
                                     },
                                     "hyperloglog": {                 # HyperLogLog configuration
                                         "enabled": True,
                                         "precision": 14,             # Precision parameter (4-16)
                                         "per_column": ["mimetype", "storage_tier"],  # Create counter per column value
                                         "serialize": True            # Whether to persist counters
                                     },
                                     "count_min_sketch": {            # Count-Min Sketch configuration
                                         "enabled": True,
                                         "width": 2048,               # Width of sketch matrix
                                         "depth": 5,                  # Depth of sketch matrix (hash functions)
                                         "track_columns": ["mimetype", "storage_tier"],  # Columns to track
                                         "serialize": True            # Whether to persist sketches
                                     },
                                     "minhash": {                    # MinHash configuration
                                         "enabled": False,            # Disabled by default (more specialized)
                                         "num_hashes": 128,           # Number of hash functions
                                         "similarity_threshold": 0.7, # Threshold for similarity comparisons
                                         "serialize": True            # Whether to persist signatures
                                     }
                                 }
        """
        if not HAS_PYARROW:
            raise ImportError("PyArrow is required for ParquetCIDCache. Install with pip install pyarrow")
        
        # Check if PyArrow Plasma is available
        self.has_plasma = False
        try:
            import pyarrow.plasma as plasma
            self.has_plasma = True
            self.plasma = plasma
        except ImportError:
            if enable_c_data_interface:
                logger.warning("PyArrow Plasma not available. C Data Interface will be disabled.")
                logger.warning("To enable, install with: pip install ipfs_kit_py[arrow]")
            
        self.directory = os.path.expanduser(directory)
        self.max_partition_rows = max_partition_rows
        self.auto_sync = auto_sync
        self.sync_interval = sync_interval
        self.last_sync_time = time.time()
        self.enable_c_data_interface = enable_c_data_interface and self.has_plasma
        self.compression_optimization = compression_optimization
        
        # Create directories
        os.makedirs(self.directory, exist_ok=True)
        
        # Initialize schema for CID data
        self.schema = self._create_schema()
        
        # In-memory record batch for fast access/writes
        self.in_memory_batch = None
        self.modified_since_sync = False
        
        # Set partitioning strategy
        self.partitioning_strategy = partitioning_strategy
        
        # Set default advanced partitioning configuration if none provided
        self.advanced_partitioning_config = advanced_partitioning_config or self._get_default_partitioning_config()
        
        # Track current partition info
        self.partitions = self._discover_partitions()
        self.current_partition_id = max(self.partitions.keys()) if self.partitions else 0
        
        # Current time partition info (if using time-based partitioning)
        self.current_time_partition = None
        if self.partitioning_strategy == "time":
            self.current_time_partition = self._get_current_time_partition()
        
        # Shared memory for C Data Interface
        self.plasma_client = None
        self.c_data_interface_handle = None
        self.current_object_id = None
        
        # Worker thread pool for async operations
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=8, thread_name_prefix="ParquetCIDCache"
        )
        
        # For asyncio compatibility
        try:
            import anyio
            self.has_asyncio = True
            # Create event loop for background tasks if needed
            self.loop = anyio.get_event_loop() if anyio.get_event_loop().is_running() else None
        except ImportError:
            self.has_asyncio = False
            
        # Initialize probabilistic data structures
        self.probabilistic_config = probabilistic_config or self._get_default_probabilistic_config()
        self.enable_probabilistic = self.probabilistic_config.get("enable_probabilistic", False)
        
        if self.enable_probabilistic:
            # Bloom filters (one per partition by default)
            self.bloom_filters = {}
            self.bloom_config = self.probabilistic_config.get("bloom_filter", {})
            self.bloom_enabled = self.bloom_config.get("enabled", True)
            
            # HyperLogLog counters (for cardinality estimation)
            self.hyperloglog_counters = {}
            self.hll_config = self.probabilistic_config.get("hyperloglog", {})
            self.hll_enabled = self.hll_config.get("enabled", True)
            
            # Count-Min Sketches (for frequency estimation)
            self.count_min_sketches = {}
            self.cms_config = self.probabilistic_config.get("count_min_sketch", {})
            self.cms_enabled = self.cms_config.get("enabled", True)
            
            # MinHash signatures (for similarity estimation)
            self.minhash_signatures = {}
            self.minhash_config = self.probabilistic_config.get("minhash", {})
            self.minhash_enabled = self.minhash_config.get("enabled", False)
            
            # Load previously serialized probabilistic data structures if they exist
            self._load_probabilistic_data_structures()
        else:
            self.bloom_enabled = False
            self.hll_enabled = False
            self.cms_enabled = False
            self.minhash_enabled = False
            self.has_asyncio = False
            self.loop = None
            logger.warning("AsyncIO not available, async operations will be limited")
        
        # Load current partition into memory
        self._load_current_partition()
        
        # Start sync timer if auto_sync enabled
        if auto_sync:
            import threading
            self.sync_timer = threading.Timer(sync_interval, self._sync_timer_callback)
            self.sync_timer.daemon = True
            self.sync_timer.start()
            
        # Create compression config based on specified strategy
        self.default_compression_config = self._get_default_compression_config()
        
        # Initialize prefetch configuration
        self.prefetch_config = self._initialize_prefetch_config(prefetch_config)
        
        # Create a prefetch queue for background operations
        self.prefetch_queue = collections.deque(maxlen=100)
        self.prefetch_in_progress = set()
        self.prefetch_stats = {
            "total_prefetch_operations": 0,
            "successful_prefetch_operations": 0,
            "total_prefetch_bytes": 0,
            "prefetch_hits": 0,
            "prefetch_misses": 0,
            "type_specific_prefetch_operations": {
                "parquet": 0,
                "arrow": 0, 
                "columnar": 0,
                "generic": 0
            },
            "prefetch_latency_ms": []
        }
        
        # Track content types for better prefetching
        self.content_type_registry = {}
        
        logger.info(f"Initialized ParquetCIDCache with compression optimization: {compression_optimization}")
            
    def _create_schema(self) -> pa.Schema:
        """Create the Arrow schema for CID cache data."""
        return pa.schema([
            # Core CID data
            pa.field('cid', pa.string()),  # The content identifier
            pa.field('size_bytes', pa.int64()),  # Size of the content
            
            # Metadata about content
            pa.field('mimetype', pa.string()),  # MIME type if known
            pa.field('filename', pa.string()),  # Original filename if available
            pa.field('extension', pa.string()),  # File extension
            
            # Storage information
            pa.field('storage_tier', pa.string()),  # Current storage tier
            pa.field('is_pinned', pa.bool_()),  # Whether content is pinned
            pa.field('local_path', pa.string()),  # Local filesystem path if cached
            
            # Cache analytics
            pa.field('added_timestamp', pa.timestamp('ms')),  # When first added to cache
            pa.field('last_accessed', pa.timestamp('ms')),  # Last access time
            pa.field('access_count', pa.int32()),  # Number of accesses
            pa.field('heat_score', pa.float32()),  # Computed heat score
            
            # Content source
            pa.field('source', pa.string()),  # Where the content came from (ipfs, s3, storacha, huggingface)
            pa.field('source_details', pa.string()),  # Source-specific details (repo, bucket, etc.)
            
            # CID specific data to optimize compression
            pa.field('cid_version', pa.int8()),  # CID version (0 or 1)
            pa.field('multihash_type', pa.string()),  # Hash algorithm used
            
            # Content validity
            pa.field('valid', pa.bool_()),  # Whether content is valid/available
            pa.field('validation_timestamp', pa.timestamp('ms')),  # When last validated
            
            # Extensible properties
            pa.field('properties', pa.map_(pa.string(), pa.string()))  # Key-value pairs for extensions
        ])
    
    def _get_partition_path(self, partition_id: int) -> str:
        """Get the path for a specific partition."""
        return os.path.join(self.directory, f"cid_cache_{partition_id:06d}.parquet")

    @beta_api(since="0.19.0")
    def _get_default_partitioning_config(self) -> Dict[str, Any]:
        """Get default partitioning configuration.
        
        Returns:
            Dictionary with default partitioning configuration
        """
        return {
            "strategy": "default",
            "time_based": {
                "enabled": False,
                "column": "added_timestamp",
                "interval": "day",
                "max_partitions": 90,
                "format": "%Y-%m-%d"
            },
            "content_type": {
                "enabled": False,
                "column": "mimetype",
                "default_partition": "unknown",
                "max_types": 20,
                "group_similar": True
            },
            "size_based": {
                "enabled": False,
                "column": "size_bytes",
                "boundaries": [1024, 1024*1024, 10*1024*1024, 100*1024*1024],
                "labels": ["tiny", "small", "medium", "large", "huge"]
            },
            "access_pattern": {
                "enabled": False,
                "column": "heat_score",
                "boundaries": [0.1, 0.5, 0.8],
                "labels": ["cold", "warm", "hot", "very_hot"]
            },
            "hybrid": {
                "enabled": False,
                "primary": "time",
                "secondary": "content_type"
            }
        }
        
    @beta_api(since="0.19.0")
    def _optimize_compression(self, table: pa.Table) -> Dict[str, Any]:
        """Optimize compression and encoding settings based on table content.
        
        This method analyzes the table's content characteristics and selects
        the most appropriate compression algorithm, compression level, and
        encoding options for each column type.
        
        Args:
            table: The Arrow table to analyze
        
        Returns:
            Dictionary with optimized compression and encoding settings
        """
        # Check if we're using "auto" optimization
        if self.compression_optimization != "auto":
            return self._get_default_compression_config()
            
        # Start with default settings
        result = {
            "compression": "zstd",
            "compression_level": 3,  # Default: balanced between speed and size
            "use_dictionary": True,
            "dictionary_pagesize_limit": 1024 * 1024,  # 1MB default
            "data_page_size": 2 * 1024 * 1024,  # 2MB default
            "use_byte_stream_split": False,
            "column_encoding": {},
            "stats": {}
        }
        
        # Skip detailed analysis if the table is very small
        if table.num_rows < 100:
            return result
        
        # Check if we have numpy for calculations
        try:
            import numpy as np
            import pandas as pd
            HAS_NUMPY = True
        except ImportError:
            HAS_NUMPY = False
            
        if not HAS_NUMPY:
            return result
        
        # Analyze each column to determine best encoding strategy
        total_string_size = 0
        num_string_columns = 0
        numeric_columns = []
        boolean_columns = []
        string_columns = []
        binary_columns = []
        timestamp_columns = []
        
        for i, field in enumerate(table.schema):
            col_name = field.name
            col = table.column(i)
            
            # Collect column type statistics
            if pa.types.is_string(field.type):
                string_columns.append(col_name)
                
                # Calculate average string length and unique ratio
                values = col.to_numpy()
                non_null_mask = pd.notna(values)
                non_null_values = values[non_null_mask]
                
                if len(non_null_values) > 0:
                    avg_length = np.mean([len(str(x)) for x in non_null_values])
                    unique_ratio = len(set(non_null_values)) / len(non_null_values)
                    
                    # Track total string data size for tuning dict encoding
                    total_string_size += sum(len(str(x)) for x in non_null_values)
                    num_string_columns += 1
                    
                    # Determine encoding strategy for strings
                    if unique_ratio < 0.1:  # Many repeated values
                        result["column_encoding"][col_name] = {
                            "use_dictionary": True,
                            "dictionary_values_ratio": 1.0  # Use dictionary for all values
                        }
                    elif avg_length > 100 and unique_ratio > 0.8:  # Long, unique strings
                        result["column_encoding"][col_name] = {
                            "use_dictionary": False  # Dictionary would waste space
                        }
                    else:
                        # Default: use dictionary with standard settings
                        result["column_encoding"][col_name] = {
                            "use_dictionary": True
                        }
                        
                    # Record statistics for diagnostics
                    result["stats"][col_name] = {
                        "avg_length": avg_length,
                        "unique_ratio": unique_ratio,
                        "encoding": result["column_encoding"][col_name]["use_dictionary"]
                    }
                    
            elif pa.types.is_binary(field.type):
                binary_columns.append(col_name)
                # For binary data (like raw CIDs), usually dictionary is not helpful
                result["column_encoding"][col_name] = {
                    "use_dictionary": False
                }
                    
            elif pa.types.is_boolean(field.type):
                boolean_columns.append(col_name)
                # For boolean columns, run-length encoding is most efficient
                result["column_encoding"][col_name] = {
                    "use_dictionary": False,
                    "use_run_length": True
                }
                
            elif pa.types.is_timestamp(field.type):
                timestamp_columns.append(col_name)
                # For timestamp data, byte_stream_split works well
                result["column_encoding"][col_name] = {
                    "use_dictionary": False,
                    "use_byte_stream_split": True
                }
                
            elif (pa.types.is_integer(field.type) or 
                  pa.types.is_floating(field.type)):
                numeric_columns.append(col_name)
                
                # For numeric data, analyze value distribution
                values = col.to_numpy()
                non_null_mask = ~np.isnan(values) if np.issubdtype(values.dtype, np.floating) else ~pd.isna(values)
                non_null_values = values[non_null_mask]
                
                if len(non_null_values) > 0:
                    unique_ratio = len(set(non_null_values)) / len(non_null_values)
                    
                    # Check for sequential values (good for run-length encoding)
                    is_sequential = False
                    if len(non_null_values) > 1:
                        diffs = np.diff(sorted(non_null_values))
                        is_sequential = np.all(diffs == 1) or np.all(diffs == 0)
                    
                    # Determine encoding strategy for numeric data
                    if unique_ratio < 0.1:  # Lots of repeated values
                        result["column_encoding"][col_name] = {
                            "use_dictionary": True
                        }
                    elif is_sequential:  # Sequential values
                        result["column_encoding"][col_name] = {
                            "use_run_length": True,
                            "use_dictionary": False
                        }
                    else:  # Normal numeric data
                        result["column_encoding"][col_name] = {
                            "use_byte_stream_split": True,
                            "use_dictionary": False
                        }
                        
                    # Record statistics for diagnostics
                    result["stats"][col_name] = {
                        "unique_ratio": unique_ratio,
                        "is_sequential": is_sequential
                    }
        
        # Set global compression settings based on data characteristics
        
        # Choose compression algorithm
        # 1. If data has lots of strings with repetition, zstd excels
        # 2. If data is primarily numeric, lz4 is faster with good compression
        # 3. If smaller size is critical and speed less so, zstd at higher levels
        if num_string_columns > 0 and total_string_size > 1024*1024:  # > 1MB of string data
            result["compression"] = "zstd"
            
            # Set compression level based on unique ratio in string columns
            avg_unique_ratio = sum(
                result["stats"].get(col, {}).get("unique_ratio", 0.5) 
                for col in string_columns
            ) / max(1, len(string_columns))
            
            if avg_unique_ratio < 0.2:  # Highly redundant data
                result["compression_level"] = 7  # Higher compression for repetitive data
            elif avg_unique_ratio > 0.8:  # Highly unique data
                result["compression_level"] = 3  # Lower compression for unique data
            else:
                result["compression_level"] = 5  # Middle ground
        elif len(numeric_columns) > len(table.column_names) / 2:
            # Primarily numeric data - optimize for speed
            if all(result["stats"].get(col, {}).get("is_sequential", False) for col in numeric_columns):
                # Sequential numeric data compresses extremely well with zstd
                result["compression"] = "zstd"
                result["compression_level"] = 9  # Max compression
            else:
                result["compression"] = "lz4"  # Fast compression for numeric data
                
        # Special case: CID-specific optimizations
        if 'cid' in table.column_names:
            # CIDs have special structure we can optimize for
            result["column_encoding"]["cid"] = {
                "use_dictionary": True,
                "dictionary_values_ratio": 1.0  # Always use dict encoding for CIDs
            }
        
        # Enable byte stream split for numeric columns if we have enough of them
        if len(numeric_columns) > 3:
            result["use_byte_stream_split"] = True
        
        # Optimize dictionary page size based on string data
        if total_string_size > 0:
            # Scale dictionary size with data size, but with reasonable bounds
            dict_size = min(max(256 * 1024, total_string_size // 10), 8 * 1024 * 1024)
            result["dictionary_pagesize_limit"] = dict_size
        
        # Set data page size based on row count
        if table.num_rows > 100000:
            # Larger pages for big tables
            result["data_page_size"] = 4 * 1024 * 1024  # 4MB
        elif table.num_rows < 1000:
            # Smaller pages for small tables
            result["data_page_size"] = 256 * 1024  # 256KB
            
        # Add summary statistics
        result["stats"]["summary"] = {
            "row_count": table.num_rows,
            "string_columns": len(string_columns),
            "numeric_columns": len(numeric_columns),
            "boolean_columns": len(boolean_columns),
            "timestamp_columns": len(timestamp_columns),
            "binary_columns": len(binary_columns),
            "compression_algorithm": result["compression"],
            "compression_level": result["compression_level"]
        }
        
        return result
        
    def _initialize_prefetch_config(self, user_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Initialize prefetch configuration with user overrides.
        
        Args:
            user_config: User-provided prefetch configuration
            
        Returns:
            Dictionary with resolved prefetch configuration
        """
        # Default prefetch configuration
        default_config = {
            "enable_type_specific_prefetch": True,
            "max_concurrent_prefetch": 8,
            "parquet_prefetch": {
                "row_group_lookahead": 2,
                "prefetch_statistics": True,
                "max_prefetch_size_mb": 64,
                "metadata_only_columns": ["cid", "size_bytes", "added_timestamp", "heat_score", "mimetype"]
            },
            "arrow_batch_size": 10000,
            "prefetch_priority": {
                "high": ["cid", "size_bytes", "heat_score"],
                "medium": ["added_timestamp", "source", "mimetype"],
                "low": ["properties", "validation_timestamp"]
            },
            "adaptive_prefetch": True,
            "prefetch_timeout_ms": 5000,  # 5 seconds timeout for prefetch operations
            "content_type_detection": True
        }
        
        # Apply user overrides if provided
        if user_config:
            # Deep merge user config with defaults
            def deep_merge(d1, d2):
                """Deep merge two dictionaries."""
                result = d1.copy()
                for k, v in d2.items():
                    if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                        result[k] = deep_merge(result[k], v)
                    else:
                        result[k] = v
                return result
                
            return deep_merge(default_config, user_config)
            
        return default_config
        
    def _get_default_compression_config(self) -> Dict[str, Any]:
        """Get default compression configuration based on selected strategy.
        
        Returns:
            Dictionary with default compression settings
        """
        if self.compression_optimization == "speed":
            return {
                "compression": "lz4",
                "compression_level": None,  # LZ4 doesn't use compression level
                "use_dictionary": False,  # Dictionary encoding adds overhead
                "dictionary_pagesize_limit": 512 * 1024,  # 512KB - smaller for speed
                "data_page_size": 1 * 1024 * 1024,  # 1MB - smaller pages for faster random access
                "use_byte_stream_split": False,  # Disable for speed
                "column_encoding": {},
                "stats": {
                    "summary": {
                        "optimization_strategy": "speed"
                    }
                }
            }
        elif self.compression_optimization == "size":
            return {
                "compression": "zstd",
                "compression_level": 9,  # Maximum compression
                "use_dictionary": True,  # Better compression with dictionaries
                "dictionary_pagesize_limit": 4 * 1024 * 1024,  # 4MB - larger dictionary for better compression
                "data_page_size": 8 * 1024 * 1024,  # 8MB - larger pages for better compression
                "use_byte_stream_split": True,  # Enable for better numeric compression
                "column_encoding": {},
                "stats": {
                    "summary": {
                        "optimization_strategy": "size"
                    }
                }
            }
        elif self.compression_optimization == "balanced" or self.compression_optimization == "auto":
            return {
                "compression": "zstd",
                "compression_level": 3,  # Balanced compression
                "use_dictionary": True,
                "dictionary_pagesize_limit": 1024 * 1024,  # 1MB
                "data_page_size": 2 * 1024 * 1024,  # 2MB
                "use_byte_stream_split": False,
                "column_encoding": {},
                "stats": {
                    "summary": {
                        "optimization_strategy": "balanced"
                    }
                }
            }
        else:
            # Fall back to balanced if unknown strategy specified
            logger.warning(f"Unknown compression optimization strategy: {self.compression_optimization}, using 'balanced'")
            return {
                "compression": "zstd",
                "compression_level": 3,
                "use_dictionary": True,
                "dictionary_pagesize_limit": 1024 * 1024,
                "data_page_size": 2 * 1024 * 1024,
                "use_byte_stream_split": False,
                "column_encoding": {},
                "stats": {
                    "summary": {
                        "optimization_strategy": "balanced (fallback)"
                    }
                }
            }
    def _discover_partitions(self) -> Dict[int, Dict[str, Any]]:
        """Discover existing partition files."""
        partitions = {}
        for filename in os.listdir(self.directory):
            if not filename.startswith('cid_cache_') or not filename.endswith('.parquet'):
                continue
                
            try:
                # Extract partition ID from filename
                partition_id = int(filename.split('_')[2].split('.')[0])
                partition_path = os.path.join(self.directory, filename)
                
                try:
                    # Get metadata without loading full content
                    metadata = pq.read_metadata(partition_path)
                    
                    partitions[partition_id] = {
                        'path': partition_path,
                        'size': os.path.getsize(partition_path),
                        'rows': metadata.num_rows,
                        'created': os.path.getctime(partition_path),
                        'modified': os.path.getmtime(partition_path)
                    }
                except Exception as e:
                    logger.warning(f"Invalid partition file {filename}: {e}")
            
            except Exception as e:
                logger.warning(f"Invalid partition file {filename}: {e}")
                
        return partitions
    
    def _load_current_partition(self) -> None:
        """Load the current partition into memory for fast access."""
        if self.current_partition_id in self.partitions:
            partition_path = self.partitions[self.current_partition_id]['path']
            
            try:
                # Check if file exists and has records
                if os.path.exists(partition_path) and self.partitions[self.current_partition_id]['rows'] > 0:
                    # Read using memory mapping for performance
                    table = pq.read_table(partition_path, memory_map=True)
                    
                    # Convert to record batch for efficient updates
                    self.in_memory_batch = table.to_batches()[0]
                else:
                    # Create empty batch with schema
                    self.in_memory_batch = pa.RecordBatch.from_pandas(
                        pd.DataFrame(), schema=self.schema
                    )
                
                # Export to C Data Interface if enabled
                if self.enable_c_data_interface:
                    self._export_to_c_data_interface()
                    
            except Exception as e:
                logger.error(f"Error loading partition {partition_path}: {e}")
                # Create empty batch
                self.in_memory_batch = None
        else:
            # Create a new partition file
            self.in_memory_batch = None
        
        # Export to C Data Interface if enabled, even for empty batches
        if self.enable_c_data_interface and self.in_memory_batch is None:
            self._export_to_c_data_interface()
            
    @stable_api(since="0.19.0")
    def contains(self, cid: str) -> bool:
        """Check if a CID is in the cache.
        
        Args:
            cid: Content identifier
            
        Returns:
            True if CID is in cache, False otherwise
        """
        # First use Bloom filters for fast negative responses if probabilistic structures are enabled
        if self.enable_probabilistic and self.bloom_enabled and self.bloom_filters:
            # First check if the CID is in any Bloom filter
            # Bloom filters can have false positives but not false negatives
            # So if ALL Bloom filters report the CID is not present, it's definitely not in the cache
            cid_might_exist = False
            
            # Check global bloom filter if it exists
            if "global" in self.bloom_filters:
                cid_might_exist = cid in self.bloom_filters["global"]
                if not cid_might_exist:
                    logger.debug(f"Bloom filter reports CID {cid} definitely not in cache")
                    return False
            
            # If per-partition filters exist, check them too
            if not cid_might_exist and self.bloom_config.get("per_partition", True):
                # Check each partition's Bloom filter
                for partition_id, bloom_filter in self.bloom_filters.items():
                    if partition_id != "global" and cid in bloom_filter:
                        cid_might_exist = True
                        break
                
                if not cid_might_exist:
                    logger.debug(f"No partition Bloom filters contain CID {cid}")
                    return False
                    
            # At this point, the CID might exist (or it's a false positive)
            # Continue with standard checks

        # Check in-memory batch
        if self.in_memory_batch is not None:
            table = pa.Table.from_batches([self.in_memory_batch])
            mask = pc.equal(pc.field('cid'), pa.scalar(cid))
            filtered = table.filter(mask)
            if filtered.num_rows > 0:
                return True
                
        # Check all partitions
        try:
            # If Bloom filters indicate which partitions might contain the CID,
            # we could optimize by checking only those partitions
            # This is an optimization that could be implemented for very large caches
            # with many partitions
            
            ds = dataset(self.directory, format="parquet")
            filter_expr = pc.equal(pc.field('cid'), pa.scalar(cid))
            result = ds.to_table(filter=filter_expr, columns=['cid'])
            
            # Update access statistics if found
            if result.num_rows > 0 and self.enable_probabilistic:
                # Update frequency statistics if Count-Min Sketch is enabled
                if self.cms_enabled and self.count_min_sketches:
                    self._update_frequency_statistics(cid, "access")
                    
            return result.num_rows > 0
            
        except Exception as e:
            logger.error(f"Error checking if CID {cid} exists: {e}")
            return False
    
    @experimental_api(since="0.19.0")
    async def async_contains(self, cid: str) -> bool:
        """Async version of contains.
        
        Args:
            cid: Content identifier
            
        Returns:
            True if CID is in cache, False otherwise
        """
        if not self.has_asyncio:
            # Fallback to thread pool if asyncio not available
            return await self._run_in_thread_pool(self.contains, cid)
            
        # First check in-memory batch (fast, do this in current thread)
        if self.in_memory_batch is not None:
            table = pa.Table.from_batches([self.in_memory_batch])
            mask = pc.equal(pc.field('cid'), pa.scalar(cid))
            filtered = table.filter(mask)
            if filtered.num_rows > 0:
                return True
                
        # Delegate disk operations to a background thread
        return await self._run_in_thread_pool(self._contains_on_disk, cid)
    
    def _contains_on_disk(self, cid: str) -> bool:
        """Check if a CID exists in on-disk partitions.
        
        Args:
            cid: Content identifier
            
        Returns:
            True if CID exists in on-disk partitions, False otherwise
        """
        try:
            ds = dataset(self.directory, format="parquet")
            filter_expr = pc.equal(pc.field('cid'), pa.scalar(cid))
            result = ds.to_table(filter=filter_expr, columns=['cid'])
            return result.num_rows > 0
        except Exception as e:
            logger.error(f"Error checking if CID {cid} exists on disk: {e}")
            return False
    
    @stable_api(since="0.19.0")
    def get_metadata(self, cid: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a CID.
        
        Args:
            cid: Content identifier
            
        Returns:
            Dictionary with metadata for the CID or None if not found
        """
        # First check in-memory batch
        if self.in_memory_batch is not None:
            table = pa.Table.from_batches([self.in_memory_batch])
            mask = pc.equal(pc.field('cid'), pa.scalar(cid))
            filtered = table.filter(mask)
            if filtered.num_rows > 0:
                # Convert to Python dict
                return filtered.to_pydict()
                
        # Check all partitions
        try:
            ds = dataset(self.directory, format="parquet")
            filter_expr = pc.equal(pc.field('cid'), pa.scalar(cid))
            result = ds.to_table(filter=filter_expr)
            
            if result.num_rows > 0:
                # Update access statistics
                self._update_access_stats(cid)
                
                # Convert first row to dict
                return {col: result[col][0].as_py() for col in result.column_names}
            return None
        except Exception as e:
            logger.error(f"Error getting metadata for CID {cid}: {e}")
            return None
            
    @beta_api(since="0.19.0")
    def batch_get_metadata(self, cids: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """Get metadata for multiple CIDs in a single batch operation.
        
        This method optimizes metadata retrieval by batching multiple requests
        into a single query, reducing overhead and improving performance.
        
        Args:
            cids: List of content identifiers
            
        Returns:
            Dictionary mapping CIDs to their metadata (None for CIDs not found)
        """
        if not cids:
            return {}
            
        # Initialize results dictionary
        results = {cid: None for cid in cids}
        
        # First check in-memory batch for all CIDs
        if self.in_memory_batch is not None:
            table = pa.Table.from_batches([self.in_memory_batch])
            
            # Filter for all requested CIDs at once
            mask = pc.is_in(pc.field('cid'), pa.array(cids))
            filtered = table.filter(mask)
            
            if filtered.num_rows > 0:
                # Convert to Python dict
                filtered_dict = filtered.to_pydict()
                
                # Create a mapping from CID to row index
                cid_to_idx = {cid: i for i, cid in enumerate(filtered_dict['cid'])}
                
                # Update results for found CIDs
                for cid in cids:
                    if cid in cid_to_idx:
                        idx = cid_to_idx[cid]
                        results[cid] = {col: filtered_dict[col][idx] for col in filtered_dict}
        
        # Find CIDs that weren't in memory
        missing_cids = [cid for cid in cids if results[cid] is None]
        
        if missing_cids:
            try:
                # Create dataset from all partitions
                ds = dataset(self.directory, format="parquet")
                
                # Filter for all missing CIDs at once
                filter_expr = pc.is_in(pc.field('cid'), pa.array(missing_cids))
                result_table = ds.to_table(filter=filter_expr)
                
                if result_table.num_rows > 0:
                    # Convert to Python dict
                    result_dict = result_table.to_pydict()
                    
                    # Create a mapping from CID to row index
                    cid_to_idx = {cid: i for i, cid in enumerate(result_dict['cid'])}
                    
                    # Update results for found CIDs
                    for cid in missing_cids:
                        if cid in cid_to_idx:
                            idx = cid_to_idx[cid]
                            results[cid] = {col: result_dict[col][idx] for col in result_dict}
                            
                            # Update access statistics
                            self._update_access_stats(cid)
                
            except Exception as e:
                logger.error(f"Error in batch_get_metadata for {len(missing_cids)} CIDs: {e}")
        
        return results
            
    @experimental_api(since="0.19.0")
    async def async_get_metadata(self, cid: str) -> Optional[Dict[str, Any]]:
        """Async version of get_metadata.
        
        Args:
            cid: Content identifier
            
        Returns:
            Dictionary with metadata for the CID or None if not found
        """
        if not self.has_asyncio:
            # Fallback to thread pool if asyncio not available
            return await self._run_in_thread_pool(self.get_metadata, cid)
            
        # First check in-memory batch (fast, do this in the current thread)
        if self.in_memory_batch is not None:
            table = pa.Table.from_batches([self.in_memory_batch])
            mask = pc.equal(pc.field('cid'), pa.scalar(cid))
            filtered = table.filter(mask)
            if filtered.num_rows > 0:
                # Convert to Python dict
                return filtered.to_pydict()
        
        # Delegate disk access to a background thread
        return await self._run_in_thread_pool(self._get_metadata_from_disk, cid)
    
    def _get_metadata_from_disk(self, cid: str) -> Optional[Dict[str, Any]]:
        """Helper to get metadata from disk for async operations.
        
        Args:
            cid: Content identifier
            
        Returns:
            Dictionary with metadata or None if not found
        """
        try:
            ds = dataset(self.directory, format="parquet")
            filter_expr = pc.equal(pc.field('cid'), pa.scalar(cid))
            result = ds.to_table(filter=filter_expr)
            
            if result.num_rows > 0:
                # Update access statistics
                self._update_access_stats(cid)
                
                # Convert first row to dict
                return {col: result[col][0].as_py() for col in result.column_names}
            return None
        except Exception as e:
            logger.error(f"Error getting metadata for CID {cid}: {e}")
            return None
            
    async def _run_in_thread_pool(self, func, *args, **kwargs):
        """Run a function in the thread pool.
        
        Args:
            func: Function to run
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            Result of the function
        """
        import anyio
        
        # Submit the task to the thread pool
        return await anyio.get_event_loop().run_in_executor(
            self.thread_pool, 
            lambda: func(*args, **kwargs)
        )
            
    @stable_api(since="0.19.0")
    def put_metadata(self, cid: str, metadata: Dict[str, Any]) -> bool:
        """Store metadata for a CID.
        
        Args:
            cid: Content identifier
            metadata: Dictionary with metadata to store
            
        Returns:
            True if stored successfully, False otherwise
        """
        try:
            # Prepare record data with schema validation
            current_time_ms = int(time.time() * 1000)
            
            record = {
                'cid': cid,
                'size_bytes': metadata.get('size_bytes', 0),
                'mimetype': metadata.get('mimetype', ''),
                'filename': metadata.get('filename', ''),
                'extension': metadata.get('extension', ''),
                'storage_tier': metadata.get('storage_tier', 'unknown'),
                'is_pinned': metadata.get('is_pinned', False),
                'local_path': metadata.get('local_path', ''),
                'added_timestamp': metadata.get('added_timestamp', current_time_ms),
                'last_accessed': current_time_ms,
                'access_count': metadata.get('access_count', 1),
                'heat_score': metadata.get('heat_score', 0.0),
                'source': metadata.get('source', 'unknown'),
                'source_details': metadata.get('source_details', ''),
                'multihash_type': metadata.get('multihash_type', ''),
                'cid_version': metadata.get('cid_version', 1),
                'valid': metadata.get('valid', True),
                'validation_timestamp': current_time_ms,
                'properties': metadata.get('properties', {})
            }
            
            # Create arrays for record batch
            arrays = []
            for field in self.schema:
                field_name = field.name
                if field_name in record:
                    value = record[field_name]
                    
                    # Convert timestamp values to proper format
                    if field.type == pa.timestamp('ms'):
                        if isinstance(value, (int, float)):
                            # If timestamp is already in milliseconds
                            arrays.append(pa.array([value], type=field.type))
                        else:
                            # Convert datetime or other format
                            arrays.append(pa.array([current_time_ms], type=field.type))
                    else:
                        arrays.append(pa.array([value], type=field.type))
                else:
                    # Use None for missing fields
                    arrays.append(pa.array([None], type=field.type))
                    
            # Create a new record batch
            new_batch = pa.RecordBatch.from_arrays(arrays, schema=self.schema)
            
            # Add to existing batch or create new one
            if self.in_memory_batch is None:
                self.in_memory_batch = new_batch
            else:
                # If CID already exists, remove it first
                table = pa.Table.from_batches([self.in_memory_batch])
                mask = pc.equal(pc.field('cid'), pa.scalar(cid))
                existing = table.filter(mask)
                
                if existing.num_rows > 0:
                    # Remove existing entries
                    inverse_mask = pc.invert(mask)
                    filtered_table = table.filter(inverse_mask)
                    filtered_batches = filtered_table.to_batches()
                    
                    if filtered_batches:
                        batch_without_cid = filtered_batches[0]
                        self.in_memory_batch = pa.concat_batches([batch_without_cid, new_batch])
                    else:
                        self.in_memory_batch = new_batch
                else:
                    # Append new record
                    self.in_memory_batch = pa.concat_batches([self.in_memory_batch, new_batch])
            
            # Check if we need to rotate partition
            if self.in_memory_batch.num_rows >= self.max_partition_rows:
                self._write_current_partition()
                self.current_partition_id += 1
                self.in_memory_batch = None
                
            self.modified_since_sync = True
            
            # Update C Data Interface if enabled
            if self.enable_c_data_interface:
                self._export_to_c_data_interface()
            
            # Update probabilistic data structures if enabled
            if self.enable_probabilistic:
                # Update Bloom filters
                if self.bloom_enabled:
                    self._update_bloom_filters(cid)
                
                # Update HyperLogLog counters for cardinality estimation
                if self.hll_enabled:
                    # Update cardinality for specific fields
                    for field_name in self.hll_config.get("per_column", []):
                        if field_name in record and record[field_name]:
                            field_value = record[field_name]
                            self._update_cardinality_statistics(field_name, field_value, cid)
                
                # Update Count-Min Sketch for frequency tracking
                if self.cms_enabled:
                    # Track frequency for specific fields
                    for field_name in self.cms_config.get("track_columns", []):
                        if field_name in record and record[field_name]:
                            field_value = record[field_name]
                            self._update_frequency_statistics(f"{field_name}:{field_value}", "add")
                
                # Update MinHash signatures if enabled
                if self.minhash_enabled:
                    # We might update MinHash signatures based on properties or metadata
                    # This is a more advanced use case that would be implementation-specific
                    pass
                
                # Periodically save probabilistic data structures if configured
                if random.random() < 0.05:  # ~5% chance to save on each update to avoid excessive I/O
                    self._save_probabilistic_data_structures()
            
            # Check if we should sync to disk
            if self.auto_sync and (time.time() - self.last_sync_time > self.sync_interval):
                self.sync()
                
            return True
                
        except Exception as e:
            logger.error(f"Error putting metadata for CID {cid}: {e}")
            return False
            
    @beta_api(since="0.19.0")
    def batch_put_metadata(self, cid_metadata_map: Dict[str, Dict[str, Any]]) -> Dict[str, bool]:
        """Store metadata for multiple CIDs in a single batch operation.
        
        This method optimizes metadata storage by batching multiple updates into a
        single operation, significantly reducing overhead for bulk operations.
        
        Args:
            cid_metadata_map: Dictionary mapping CIDs to their respective metadata
            
        Returns:
            Dictionary mapping CIDs to success status (True if stored successfully)
        """
        if not cid_metadata_map:
            return {}
            
        # Initialize results dictionary
        results = {cid: False for cid in cid_metadata_map.keys()}
        
        try:
            current_time_ms = int(time.time() * 1000)
            
            # Prepare data for all records
            all_records = []
            for cid, metadata in cid_metadata_map.items():
                record = {
                    'cid': cid,
                    'size_bytes': metadata.get('size_bytes', 0),
                    'mimetype': metadata.get('mimetype', ''),
                    'filename': metadata.get('filename', ''),
                    'extension': metadata.get('extension', ''),
                    'storage_tier': metadata.get('storage_tier', 'unknown'),
                    'is_pinned': metadata.get('is_pinned', False),
                    'local_path': metadata.get('local_path', ''),
                    'added_timestamp': metadata.get('added_timestamp', current_time_ms),
                    'last_accessed': current_time_ms,
                    'access_count': metadata.get('access_count', 1),
                    'heat_score': metadata.get('heat_score', 0.0),
                    'source': metadata.get('source', 'unknown'),
                    'source_details': metadata.get('source_details', ''),
                    'multihash_type': metadata.get('multihash_type', ''),
                    'cid_version': metadata.get('cid_version', 1),
                    'valid': metadata.get('valid', True),
                    'validation_timestamp': current_time_ms,
                    'properties': metadata.get('properties', {})
                }
                all_records.append(record)
            
            # First, identify and remove existing CIDs from the in-memory batch
            existing_cids = set(cid_metadata_map.keys())
            if self.in_memory_batch is not None:
                table = pa.Table.from_batches([self.in_memory_batch])
                
                # Filter out records for CIDs we're updating
                mask = pc.is_in(pc.field('cid'), pa.array(list(existing_cids)))
                existing_records = table.filter(mask)
                
                # Keep records that aren't being updated
                inverse_mask = pc.invert(mask)
                remaining_records = table.filter(inverse_mask)
                
                # Convert remaining records to record batch
                if remaining_records.num_rows > 0:
                    remaining_batch = remaining_records.to_batches()[0]
                else:
                    remaining_batch = None
            else:
                remaining_batch = None
            
            # Create arrays for new record batch
            # For each field, create an array with values from all records
            arrays = []
            for field in self.schema:
                field_name = field.name
                field_values = []
                
                for record in all_records:
                    if field_name in record:
                        value = record[field_name]
                        
                        # Convert timestamp values to proper format
                        if field.type == pa.timestamp('ms') and not isinstance(value, (int, float)):
                            value = current_time_ms
                            
                        field_values.append(value)
                    else:
                        field_values.append(None)
                
                arrays.append(pa.array(field_values, type=field.type))
            
            # Create a new record batch with all new/updated records
            new_batch = pa.RecordBatch.from_arrays(arrays, schema=self.schema)
            
            # Combine with remaining records if any
            if remaining_batch is not None:
                self.in_memory_batch = pa.concat_batches([remaining_batch, new_batch])
            else:
                self.in_memory_batch = new_batch
            
            # Check if we need to rotate partition
            if self.in_memory_batch.num_rows >= self.max_partition_rows:
                self._write_current_partition()
                self.current_partition_id += 1
                self.in_memory_batch = None
            
            self.modified_since_sync = True
            
            # Update C Data Interface if enabled
            if self.enable_c_data_interface:
                self._export_to_c_data_interface()
            
            # Check if we should sync to disk
            if self.auto_sync and (time.time() - self.last_sync_time > self.sync_interval):
                self.sync()
            
            # All records successfully stored
            for cid in cid_metadata_map.keys():
                results[cid] = True
                
        except Exception as e:
            logger.error(f"Error in batch_put_metadata for {len(cid_metadata_map)} CIDs: {e}")
            # Individual CIDs that failed were already marked as False in results
            
        return results
            
    async def async_put_metadata(self, cid: str, metadata: Dict[str, Any]) -> bool:
        """Async version of put_metadata.
        
        Args:
            cid: Content identifier
            metadata: Dictionary with metadata to store
            
        Returns:
            True if stored successfully, False otherwise
        """
        if not self.has_asyncio:
            # Fallback to thread pool if asyncio not available
            return await self._run_in_thread_pool(self.put_metadata, cid, metadata)
            
    async def async_batch_put_metadata(self, cid_metadata_map: Dict[str, Dict[str, Any]]) -> Dict[str, bool]:
        """Async version of batch_put_metadata.
        
        This method provides a non-blocking way to store metadata for multiple CIDs
        in a single batch operation, ideal for high-throughput asynchronous workflows.
        
        Args:
            cid_metadata_map: Dictionary mapping CIDs to their respective metadata
            
        Returns:
            Dictionary mapping CIDs to success status (True if stored successfully)
        """
        if not self.has_asyncio:
            # Fallback to thread pool if asyncio not available
            return await self._run_in_thread_pool(self.batch_put_metadata, cid_metadata_map)
            
        # Delegate the actual work to a background thread to avoid blocking the event loop
        # with potentially expensive operations
        return await self._run_in_thread_pool(self.batch_put_metadata, cid_metadata_map)
        
    async def async_batch_get_metadata(self, cids: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """Async version of batch_get_metadata.
        
        This method provides a non-blocking way to retrieve metadata for multiple CIDs
        in a single batch operation, ideal for high-throughput asynchronous workflows.
        
        Args:
            cids: List of content identifiers
            
        Returns:
            Dictionary mapping CIDs to their metadata (None for CIDs not found)
        """
        if not self.has_asyncio:
            # Fallback to thread pool if asyncio not available
            return await self._run_in_thread_pool(self.batch_get_metadata, cids)
            
        # Delegate the actual work to a background thread to avoid blocking the event loop
        return await self._run_in_thread_pool(self.batch_get_metadata, cids)
        
    async def _async_disk_operations(self, needs_rotation: bool) -> None:
            mask = pc.equal(pc.field('cid'), pa.scalar(cid))
            existing = table.filter(mask)
            
            if existing.num_rows > 0:
                # Remove existing entries
                inverse_mask = pc.invert(mask)
                filtered_table = table.filter(inverse_mask)
                filtered_batches = filtered_table.to_batches()
                
                if filtered_batches:
                    batch_without_cid = filtered_batches[0]
                    self.in_memory_batch = pa.concat_batches([batch_without_cid, new_batch])
                else:
                    self.in_memory_batch = new_batch
            else:
                # Append new record
                self.in_memory_batch = pa.concat_batches([self.in_memory_batch, new_batch])
        
            needs_rotation = self.in_memory_batch.num_rows >= self.max_partition_rows
            self.modified_since_sync = True
        
            # Delegate disk operations to a background thread
            if needs_rotation or (self.auto_sync and (time.time() - self.last_sync_time > self.sync_interval)):
                # Run disk operations in background
                anyio.create_task(self._async_disk_operations(needs_rotation))
        
            # Update C Data Interface if enabled (in background)
            if self.enable_c_data_interface:
                anyio.create_task(self._run_in_thread_pool(self._export_to_c_data_interface))
            
            return True
            
    async def _async_disk_operations(self, needs_rotation: bool) -> None:
        """Perform asynchronous disk operations.
        
        Args:
            needs_rotation: Whether partition rotation is needed
        """
        try:
            if needs_rotation:
                await self._run_in_thread_pool(self._write_current_partition)
                self.current_partition_id += 1
                self.in_memory_batch = None
            elif self.auto_sync and (time.time() - self.last_sync_time > self.sync_interval):
                await self._run_in_thread_pool(self.sync)
        except Exception as e:
            logger.error(f"Error in async disk operations: {e}")
            
    def _update_access_stats(self, cid: str) -> None:
        """Update access statistics for a CID.
        
        Args:
            cid: Content identifier
        """
        try:
            # Get current metadata
            metadata = self.get_metadata(cid)
            if not metadata:
                return
                
            # Update access count and last_accessed
            current_time_ms = int(time.time() * 1000)
            
            # Calculate new heat score
            access_count = metadata.get('access_count', 0) + 1
            last_accessed = current_time_ms
            added_timestamp = metadata.get('added_timestamp', current_time_ms)
            
            # Heat score formula similar to ARCache
            age_hours = max(0.001, (current_time_ms - added_timestamp) / (1000 * 3600))
            recency = 1.0 / (1.0 + (current_time_ms - last_accessed) / (1000 * 3600))
            frequency = access_count / age_hours
            
            # Combined heat score (adjust weights as needed)
            heat_score = (frequency * 0.7) + (recency * 0.3)
            
            # Update metadata
            metadata.update({
                'access_count': access_count,
                'last_accessed': last_accessed,
                'heat_score': heat_score
            })
            
            # Store updated metadata
            self.put_metadata(cid, metadata)
            
        except Exception as e:
            logger.error(f"Error updating access stats for CID {cid}: {e}")
    
    @beta_api(since="0.19.0")
    def _write_current_partition(self) -> None:
        """Write current in-memory batch to parquet file with optimized compression and encoding.
        
        This method now supports different partitioning strategies:
        1. Default: Sequential partitioning with integer IDs
        2. Time-based: Organizing data by timestamp
        3. Content-type: Grouping by content types
        4. Size-based: Partitioning by content size
        5. Access-pattern: Grouping by access frequency
        6. Hybrid: Combining multiple strategies
        """
        if self.in_memory_batch is None or self.in_memory_batch.num_rows == 0:
            return
            
        # Convert batch to table
        table = pa.Table.from_batches([self.in_memory_batch])
        
        # Determine partitioning approach
        if self.partitioning_strategy == "default":
            # Traditional sequential partitioning
            partition_path = self._get_partition_path(self.current_partition_id)
            partitions_to_write = [(partition_path, table)]
        else:
            # Advanced partitioning - group records by partition
            partitions_to_write = self._partition_table_by_strategy(table)
            
        # Update partitioning info if needed (especially for time-based)
        self._update_partitioning()
        
        # Analyze table to determine optimal compression settings
        # Create customized compression and encoding settings based on table content
        compression_config = self._optimize_compression(table)
        
        # Write each partition
        for partition_path, partition_table in partitions_to_write:
            try:
                # Write with optimized compression and encoding settings
                pq.write_table(
                    partition_table, 
                    partition_path,
                    compression=compression_config["compression"],
                    compression_level=compression_config["compression_level"],
                    use_dictionary=compression_config["use_dictionary"],
                    dictionary_pagesize_limit=compression_config["dictionary_pagesize_limit"],
                    data_page_size=compression_config["data_page_size"],
                    use_byte_stream_split=compression_config["use_byte_stream_split"],
                    write_statistics=True,
                    column_encoding=compression_config["column_encoding"]
                )
                
                # Get partition ID for tracking - use filename for advanced partitioning
                if self.partitioning_strategy == "default":
                    partition_id = self.current_partition_id
                else:
                    # Extract partition ID from filename for advanced partitioning
                    partition_id = os.path.splitext(os.path.basename(partition_path))[0]
                
                # Update partitions metadata
                self.partitions[partition_id] = {
                    'path': partition_path,
                    'size': os.path.getsize(partition_path),
                    'rows': partition_table.num_rows,
                    'created': os.path.getctime(partition_path),
                    'modified': os.path.getmtime(partition_path),
                    'compression_stats': compression_config["stats"],
                    'partitioning_strategy': self.partitioning_strategy
                }
                
                logger.debug(f"Wrote partition {partition_id} with {partition_table.num_rows} rows using {compression_config['compression']} compression")
                
            except Exception as e:
                logger.error(f"Error writing partition {partition_path}: {e}")
                
        # Reset in-memory batch after writing
        self.in_memory_batch = None
        self.modified_since_sync = False
        self.last_sync_time = time.time()
        
    @beta_api(since="0.19.0")
    def _partition_table_by_strategy(self, table: pa.Table) -> List[Tuple[str, pa.Table]]:
        """Partition a table according to the current strategy.
        
        Args:
            table: Table to partition
            
        Returns:
            List of (partition_path, partition_table) tuples
        """
        # Convert to pandas for easier filtering and manipulation
        df = table.to_pandas()
        
        partitions = []
        
        if self.partitioning_strategy == "time":
            # Time-based partitioning
            config = self.advanced_partitioning_config["time_partitioning"]
            column = config.get("column", "added_timestamp")
            fmt = config.get("format", "%Y-%m-%d")
            
            # Check if column exists
            if column not in df.columns:
                # Fall back to default partitioning if column missing
                logger.warning(f"Time partitioning column '{column}' not found in table, using current time partition")
                partition_path = os.path.join(self.directory, f"time_{self.current_time_partition}.parquet")
                partitions.append((partition_path, table))
                return partitions
            
            # Group by time period
            time_groups = {}
            
            for idx, row in df.iterrows():
                timestamp_value = row.get(column)
                
                if timestamp_value is None:
                    # Use current partition for records without timestamp
                    time_key = self.current_time_partition
                else:
                    # Convert timestamp to datetime
                    if isinstance(timestamp_value, (int, float)):
                        # Assume milliseconds since epoch
                        dt = datetime.datetime.fromtimestamp(timestamp_value / 1000)
                    elif isinstance(timestamp_value, datetime.datetime):
                        dt = timestamp_value
                    else:
                        # Use current partition for invalid formats
                        time_key = self.current_time_partition
                        if time_key not in time_groups:
                            time_groups[time_key] = []
                        time_groups[time_key].append(idx)
                        continue
                        
                    # Format according to interval
                    time_key = dt.strftime(fmt)
                
                # Add to appropriate group
                if time_key not in time_groups:
                    time_groups[time_key] = []
                time_groups[time_key].append(idx)
            
            # Create a table for each time group
            for time_key, indices in time_groups.items():
                partition_df = df.iloc[indices]
                partition_table = pa.Table.from_pandas(partition_df, schema=self.schema)
                partition_path = os.path.join(self.directory, f"time_{time_key}.parquet")
                partitions.append((partition_path, partition_table))
                
        elif self.partitioning_strategy == "content_type":
            # Content-type based partitioning
            config = self.advanced_partitioning_config["content_type_partitioning"]
            column = config.get("column", "mimetype")
            default_partition = config.get("default_partition", "unknown")
            group_similar = config.get("group_similar", True)
            
            # Check if column exists
            if column not in df.columns:
                # Fall back to default partition if column missing
                logger.warning(f"Content type column '{column}' not found in table, using default content type")
                partition_path = os.path.join(self.directory, f"type_{default_partition}.parquet")
                partitions.append((partition_path, table))
                return partitions
            
            # Group by content type
            content_type_groups = {}
            
            for idx, row in df.iterrows():
                content_type = row.get(column, default_partition)
                
                if not content_type or content_type == "":
                    content_type = default_partition
                    
                # Normalize if grouping similar types
                if group_similar:
                    content_type = self._normalize_content_type(content_type)
                
                # Add to appropriate group
                if content_type not in content_type_groups:
                    content_type_groups[content_type] = []
                content_type_groups[content_type].append(idx)
            
            # Create a table for each content type group
            for content_type, indices in content_type_groups.items():
                partition_df = df.iloc[indices]
                partition_table = pa.Table.from_pandas(partition_df, schema=self.schema)
                partition_path = os.path.join(self.directory, f"type_{content_type}.parquet")
                partitions.append((partition_path, partition_table))
                
        elif self.partitioning_strategy == "size":
            # Size-based partitioning
            config = self.advanced_partitioning_config["size_partitioning"]
            column = config.get("column", "size_bytes")
            boundaries = config.get("boundaries", [10240, 102400, 1048576, 10485760])
            labels = config.get("labels", ["tiny", "small", "medium", "large", "xlarge"])
            
            # Check if column exists
            if column not in df.columns:
                # Fall back to smallest partition if column missing
                logger.warning(f"Size column '{column}' not found in table, using smallest size category")
                partition_path = os.path.join(self.directory, f"size_{labels[0]}.parquet")
                partitions.append((partition_path, table))
                return partitions
            
            # Group by size category
            size_groups = {}
            
            for idx, row in df.iterrows():
                size = row.get(column, 0)
                if not isinstance(size, (int, float)):
                    size = 0
                    
                # Determine size category
                category_index = 0
                for i, boundary in enumerate(boundaries):
                    if size >= boundary:
                        category_index = i + 1
                    else:
                        break
                        
                # Get appropriate label
                if category_index < len(labels):
                    size_label = labels[category_index]
                else:
                    size_label = labels[-1]  # Use last label if beyond all boundaries
                
                # Add to appropriate group
                if size_label not in size_groups:
                    size_groups[size_label] = []
                size_groups[size_label].append(idx)
            
            # Create a table for each size group
            for size_label, indices in size_groups.items():
                partition_df = df.iloc[indices]
                partition_table = pa.Table.from_pandas(partition_df, schema=self.schema)
                partition_path = os.path.join(self.directory, f"size_{size_label}.parquet")
                partitions.append((partition_path, partition_table))
                
        elif self.partitioning_strategy == "access_pattern":
            # Access pattern partitioning
            config = self.advanced_partitioning_config["access_pattern_partitioning"]
            column = config.get("column", "heat_score")
            boundaries = config.get("boundaries", [0.1, 0.5, 0.9])
            labels = config.get("labels", ["cold", "warm", "hot", "critical"])
            
            # Check if column exists
            if column not in df.columns:
                # Fall back to coldest partition if column missing
                logger.warning(f"Heat score column '{column}' not found in table, using coldest access category")
                partition_path = os.path.join(self.directory, f"access_{labels[0]}.parquet")
                partitions.append((partition_path, table))
                return partitions
            
            # Group by heat score category
            heat_groups = {}
            
            for idx, row in df.iterrows():
                heat_score = row.get(column, 0.0)
                if not isinstance(heat_score, (int, float)):
                    heat_score = 0.0
                    
                # Determine heat category
                category_index = 0
                for i, boundary in enumerate(boundaries):
                    if heat_score >= boundary:
                        category_index = i + 1
                    else:
                        break
                        
                # Get appropriate label
                if category_index < len(labels):
                    heat_label = labels[category_index]
                else:
                    heat_label = labels[-1]  # Use last label if beyond all boundaries
                
                # Add to appropriate group
                if heat_label not in heat_groups:
                    heat_groups[heat_label] = []
                heat_groups[heat_label].append(idx)
            
            # Create a table for each heat group
            for heat_label, indices in heat_groups.items():
                partition_df = df.iloc[indices]
                partition_table = pa.Table.from_pandas(partition_df, schema=self.schema)
                partition_path = os.path.join(self.directory, f"access_{heat_label}.parquet")
                partitions.append((partition_path, partition_table))
                
        elif self.partitioning_strategy == "hybrid":
            # Hybrid partitioning (hierarchical)
            config = self.advanced_partitioning_config["hybrid_partitioning"]
            primary = config.get("primary", "time")
            secondary = config.get("secondary", "content_type")
            
            # Temporarily switch to primary strategy
            original_strategy = self.partitioning_strategy
            self.partitioning_strategy = primary
            
            # Get primary partitions
            primary_partitions = self._partition_table_by_strategy(table)
            
            # For each primary partition, apply secondary partitioning
            hybrid_partitions = []
            self.partitioning_strategy = secondary
            
            for primary_path, primary_table in primary_partitions:
                # Extract primary key from filename
                primary_key = os.path.splitext(os.path.basename(primary_path))[0]
                
                # Apply secondary partitioning to this primary partition
                secondary_partitions = self._partition_table_by_strategy(primary_table)
                
                # Combine primary and secondary keys
                for secondary_path, secondary_table in secondary_partitions:
                    secondary_key = os.path.splitext(os.path.basename(secondary_path))[0]
                    hybrid_path = os.path.join(self.directory, f"{primary_key}_{secondary_key}.parquet")
                    hybrid_partitions.append((hybrid_path, secondary_table))
            
            # Restore original strategy
            self.partitioning_strategy = original_strategy
            
            partitions = hybrid_partitions
        else:
            # Unknown strategy, fall back to default
            partition_path = self._get_partition_path(self.current_partition_id)
            partitions.append((partition_path, table))
            
        return partitions
    
    @stable_api(since="0.19.0")
    def sync(self) -> bool:
        """Sync in-memory data to disk.
        
        Returns:
            True if synced successfully, False otherwise
        """
        if not self.modified_since_sync:
            return True
            
        try:
            self._write_current_partition()
            return True
        except Exception as e:
            logger.error(f"Error syncing to disk: {e}")
            return False
    
    @experimental_api(since="0.19.0")
    async def async_sync(self) -> bool:
        """Async version of sync.
        
        Returns:
            True if synced successfully, False otherwise
        """
        if not self.modified_since_sync:
            return True
            
        # Run the sync operation in a background thread
        return await self._run_in_thread_pool(self.sync)
            
    def _sync_timer_callback(self) -> None:
        """Callback for sync timer."""
        if self.modified_since_sync:
            self.sync()
            
        # Restart timer
        if self.auto_sync:
            import threading
            self.sync_timer = threading.Timer(self.sync_interval, self._sync_timer_callback)
            self.sync_timer.daemon = True
            self.sync_timer.start()
    
    def _export_to_c_data_interface(self, custom_table=None, name_suffix=None) -> Dict[str, Any]:
        """Export the cache data to Arrow C Data Interface for zero-copy access.
        
        This allows other processes and languages to access the cache data without copying.
        The implementation uses Apache Arrow's Plasma store for shared memory management,
        enabling efficient cross-process and cross-language data sharing with zero-copy overhead.
        
        Args:
            custom_table: Optional custom table to export instead of the in-memory batch
            name_suffix: Optional suffix to add to the object name for identification
            
        Returns:
            Dictionary with C Data Interface handle information or None on failure
        """
        if not self.enable_c_data_interface or not self.has_plasma:
            return None
            
        try:
            # Create or connect to plasma store
            if not self.plasma_client:
                # Create a plasma store socket path in the cache directory
                plasma_socket = os.path.join(self.directory, "plasma.sock")
                # Check if the plasma store is already running
                if not os.path.exists(plasma_socket):
                    # Auto-start plasma store if not running (requires running as a daemon)
                    self._start_plasma_store()
                
                self.plasma_client = self.plasma.connect(plasma_socket)
                
            # Create shared table for C Data Interface
            if custom_table is not None:
                shared_table = custom_table
            elif self.in_memory_batch is not None:
                shared_table = pa.Table.from_batches([self.in_memory_batch])
            else:
                # Create empty table with schema
                empty_arrays = []
                for field in self.schema:
                    empty_arrays.append(pa.array([], type=field.type))
                shared_table = pa.Table.from_arrays(empty_arrays, schema=self.schema)
                
            # Generate object ID for the table
            # Use a deterministic ID based on params to allow other processes to predict it
            if name_suffix:
                id_seed = f"{self.directory}_{name_suffix}_{time.time()}"
            else:
                id_seed = f"{self.directory}_{self.current_partition_id}_{time.time()}"
            
            hash_bytes = hashlib.md5(id_seed.encode()).digest()[:20]
            object_id = self.plasma.ObjectID(hash_bytes)
            
            # If object already exists with this ID, delete it first
            if self.plasma_client.contains(object_id):
                self.plasma_client.delete([object_id])
            
            # Create and seal the object
            data_size = shared_table.nbytes
            buffer = self.plasma_client.create(object_id, data_size)
            
            # Write the table to the buffer
            writer = pa.RecordBatchStreamWriter(
                pa.FixedSizeBufferWriter(buffer), shared_table.schema
            )
            writer.write_table(shared_table)
            writer.close()
            
            # Seal the object
            self.plasma_client.seal(object_id)
            
            # Store the object ID for reference
            if name_suffix is None:
                self.current_object_id = object_id
            
            # Create handle with metadata
            handle = {
                "object_id": object_id.binary().hex(),
                "plasma_socket": os.path.join(self.directory, "plasma.sock"),
                "schema_json": self.schema.to_string(),
                "num_rows": shared_table.num_rows,
                "timestamp": time.time(),
                "directory": self.directory,
                "partition_id": self.current_partition_id,
                "access_info": {
                    "python": {
                        "import": "import pyarrow as pa\nimport pyarrow.plasma as plasma",
                        "code": f"client = plasma.connect('{os.path.join(self.directory, 'plasma.sock')}')\nobject_id = plasma.ObjectID.from_hex('{object_id.binary().hex()}')\nbuffer = client.get(object_id)\nreader = pa.ipc.open_stream(buffer)\ntable = reader.read_all()"
                    },
                    "cpp": {
                        "import": "#include <arrow/api.h>\n#include <arrow/io/api.h>\n#include <arrow/ipc/api.h>\n#include <plasma/client.h>",
                        "code": f"std::shared_ptr<plasma::PlasmaClient> client;\nplasma::Connect(\"{os.path.join(self.directory, 'plasma.sock')}\", \"\", 0, &client);\nplasma::ObjectID object_id = plasma::ObjectID::from_binary(\"{object_id.binary().hex()}\");\nstd::shared_ptr<arrow::Buffer> buffer;\nclient->Get(&object_id, 1, -1, &buffer);\nauto reader = arrow::ipc::RecordBatchStreamReader::Open(std::make_shared<arrow::io::BufferReader>(buffer));\nstd::shared_ptr<arrow::Table> table;\nreader->ReadAll(&table);"
                    },
                    "rust": {
                        "import": "use arrow::ipc::reader::StreamReader;\nuse plasma::PlasmaClient;",
                        "code": f"let mut client = PlasmaClient::connect(\"{os.path.join(self.directory, 'plasma.sock')}\", \"\").unwrap();\nlet object_id = hex::decode(\"{object_id.binary().hex()}\").unwrap();\nlet buffer = client.get(&object_id, -1).unwrap();\nlet reader = StreamReader::try_new(&buffer[..]).unwrap();\nlet table = reader.into_table().unwrap();"
                    }
                }
            }
            
            # Save handle for instance access
            if name_suffix is None:
                self.c_data_interface_handle = handle
            
            # Write handle to disk for other processes to discover
            # Use different files for different objects if name_suffix is provided
            if name_suffix:
                cdi_path = os.path.join(self.directory, f"c_data_interface_{name_suffix}.json")
            else:
                cdi_path = os.path.join(self.directory, "c_data_interface.json")
                
            with open(cdi_path, "w") as f:
                json.dump(handle, f)
                
            logger.debug(f"Exported cache data to C Data Interface at {cdi_path}")
            return handle
            
        except Exception as e:
            logger.error(f"Failed to export cache to C Data Interface: {e}")
            return None
            
    def _start_plasma_store(self, memory_limit_mb=1000):
        """Start a plasma store process if one isn't already running.
        
        Args:
            memory_limit_mb: Memory limit for the plasma store in MB
        
        Returns:
            True if plasma store started successfully, False otherwise
        """
        try:
            plasma_socket = os.path.join(self.directory, "plasma.sock")
            
            # Don't start if already running
            if os.path.exists(plasma_socket):
                return True
                
            # Import necessary modules
            from subprocess import Popen, PIPE, DEVNULL
            
            # Start plasma store process
            cmd = [
                sys.executable, "-m", "pyarrow.plasma",
                "-s", plasma_socket,
                "-m", str(memory_limit_mb * 1024 * 1024)
            ]
            
            # Start process detached from parent
            process = Popen(
                cmd,
                stdout=DEVNULL,
                stderr=PIPE,
                start_new_session=True  # Detach from parent process
            )
            
            # Check if process started successfully
            time.sleep(0.5)  # Give it a moment to start
            if process.poll() is None:  # None means it's still running
                logger.info(f"Started plasma store at {plasma_socket} with {memory_limit_mb}MB limit")
                return True
            else:
                error = process.stderr.read().decode('utf-8')
                logger.error(f"Failed to start plasma store: {error}")
                return False
                
        except Exception as e:
            logger.error(f"Error starting plasma store: {e}")
            return False
    
    def query(self, filters: List[Tuple[str, str, Any]] = None, 
             columns: List[str] = None,
             sort_by: str = None,
             limit: int = None,
             parallel: bool = False,
             max_workers: Optional[int] = None,
             use_probabilistic: Optional[bool] = None) -> Dict[str, List]:
        """Query the CID cache with filters.
        
        This method leverages probabilistic data structures to optimize query performance
        when appropriate:
        
        1. Bloom filters: For fast negative lookups to skip entire partitions
        2. HyperLogLog: For estimating result cardinality before full execution
        3. Count-Min Sketch: For frequency analysis in skewed distributions
        
        Args:
            filters: List of filter tuples (field, op, value)
                     e.g. [("size_bytes", ">", 1024), ("mimetype", "==", "image/jpeg")]
            columns: List of columns to return (None for all)
            sort_by: Field to sort by
            limit: Maximum number of results to return
            parallel: Whether to use parallel execution for complex queries
            max_workers: Maximum number of worker threads (defaults to CPU count)
            use_probabilistic: Whether to use probabilistic optimizations (defaults to global setting)
            
        Returns:
            Dictionary with query results
        """
        # Determine whether to use probabilistic optimizations
        if use_probabilistic is None:
            use_probabilistic = self.enable_probabilistic
        
        # Use parallel execution if requested and appropriate
        if parallel:
            return self.parallel_query(filters, columns, sort_by, limit, max_workers, use_probabilistic)
        
        start_time = time.time()
        query_stats = {
            "partitions_scanned": 0,
            "partitions_skipped": 0,
            "bloom_filter_hits": 0,
            "final_result_count": 0,
            "estimated_result_count": None
        }
            
        try:
            # First check if we can use Bloom filters for early pruning
            partition_files = []
            cid_equals_filter = None
            
            if use_probabilistic and self.bloom_enabled and filters:
                # Check if we have a filter on the CID field with equality
                for field, op, value in filters:
                    if field == "cid" and op == "==":
                        cid_equals_filter = value
                        break
                
                # If we have a CID equality filter and Bloom filters enabled
                if cid_equals_filter:
                    # Check each partition's Bloom filter to see if the CID might be present
                    filtered_partitions = []
                    
                    # For each partition that has a Bloom filter
                    for partition_id, bloom_filter in self.bloom_filters.items():
                        partition_path = self._get_partition_path(partition_id)
                        if os.path.exists(partition_path):
                            # Check if the CID might be in this partition
                            if bloom_filter.contains(cid_equals_filter):
                                filtered_partitions.append(partition_path)
                                query_stats["bloom_filter_hits"] += 1
                            else:
                                # Definitely not in this partition
                                query_stats["partitions_skipped"] += 1
                    
                    # Use filtered partitions for query
                    partition_files = filtered_partitions
            
            # Use all partitions if no early pruning or no matching bloom filters
            if not partition_files:
                # Fallback to scanning all partitions
                import glob
                partition_files = glob.glob(os.path.join(self.directory, "*.parquet"))
                
            query_stats["partitions_scanned"] = len(partition_files)
            
            # Try to estimate cardinality using HyperLogLog
            if use_probabilistic and self.hll_enabled and filters:
                estimated_count = self._estimate_result_cardinality(filters)
                if estimated_count is not None:
                    query_stats["estimated_result_count"] = estimated_count
                    
                    # Early termination if estimated count is 0 and we have high confidence
                    if estimated_count == 0 and len(self.hyperloglog_counters) > 0:
                        logger.debug(f"Early termination based on HyperLogLog estimate of 0 results")
                        return {}
            
            # Create dataset from selected partitions
            if partition_files:
                ds = dataset(partition_files, format="parquet")
            else:
                ds = dataset(self.directory, format="parquet")
            
            # Build filter expression
            filter_expr = self._build_filter_expression(filters)
            
            # Execute query
            table = ds.to_table(filter=filter_expr, columns=columns)
            
            # Apply sorting if specified
            if sort_by and sort_by in table.column_names:
                # Sort indices
                indices = pc.sort_indices(table[sort_by])
                table = table.take(indices)
                
            # Apply limit if specified
            if limit and limit < table.num_rows:
                table = table.slice(0, limit)
            
            query_stats["final_result_count"] = table.num_rows
            query_stats["query_time_ms"] = (time.time() - start_time) * 1000
            logger.debug(f"Query stats: {query_stats}")
                
            # Update frequency statistics if enabled
            if use_probabilistic and self.cms_enabled and table.num_rows > 0:
                self._update_frequency_statistics(table)
                
            # Convert to Python dictionary
            return table.to_pydict()
            
        except Exception as e:
            logger.error(f"Error querying CID cache: {e}")
            return {}
            
    def _build_filter_expression(self, filters: List[Tuple[str, str, Any]] = None) -> Optional[pc.Expression]:
        """Build a PyArrow compute filter expression from a list of filter tuples.
        
        Args:
            filters: List of filter tuples (field, op, value)
            
        Returns:
            PyArrow compute expression, or None if no filters
        """
        filter_expr = None
        if not filters:
            return None
            
        for field, op, value in filters:
            field_expr = pc.field(field)
            
            if op == "==":
                expr = pc.equal(field_expr, pa.scalar(value))
            elif op == "!=":
                expr = pc.not_equal(field_expr, pa.scalar(value))
            elif op == ">":
                expr = pc.greater(field_expr, pa.scalar(value))
            elif op == ">=":
                expr = pc.greater_equal(field_expr, pa.scalar(value))
            elif op == "<":
                expr = pc.less(field_expr, pa.scalar(value))
            elif op == "<=":
                expr = pc.less_equal(field_expr, pa.scalar(value))
            elif op == "in":
                if not isinstance(value, (list, tuple)):
                    value = [value]
                expr = pc.is_in(field_expr, pa.array(value))
            elif op == "contains":
                expr = pc.match_substring(field_expr, value)
            else:
                logger.warning(f"Unsupported operator: {op}")
                continue
                
            # Combine expressions with AND
            if filter_expr is None:
                filter_expr = expr
            else:
                filter_expr = pc.and_(filter_expr, expr)
                
        return filter_expr
            
    @beta_api(since="0.19.0")
    def parallel_query(self, filters: List[Tuple[str, str, Any]] = None, 
                      columns: List[str] = None,
                      sort_by: str = None,
                      limit: int = None,
                      max_workers: Optional[int] = None,
                      use_probabilistic: Optional[bool] = None) -> Dict[str, List]:
        """Execute a query using parallel processing for improved performance.
        
        This method distributes query execution across multiple threads to scan
        partitions in parallel, significantly improving performance for large
        datasets and complex queries. It's particularly effective when:
        
        1. The dataset has many partitions (especially with advanced partitioning)
        2. The query contains complex filtering conditions
        3. The system has multiple CPUs available
        
        It also leverages probabilistic data structures for additional optimizations:
        
        1. Bloom filters for fast negative lookups to skip entire partitions
        2. HyperLogLog for accurate cardinality estimation
        3. Count-Min Sketch for frequency tracking in streaming workloads
        
        Args:
            filters: List of filter tuples (field, op, value)
            columns: List of columns to return (None for all)
            sort_by: Field to sort by
            limit: Maximum number of results to return
            max_workers: Maximum number of worker threads (defaults to CPU count)
            use_probabilistic: Whether to use probabilistic optimizations (defaults to global setting)
            
        Returns:
            Dictionary with query results
        """
        start_time = time.time()
        result_stats = {
            "partitions_processed": 0,
            "partitions_with_matches": 0,
            "partitions_skipped": 0,
            "bloom_filter_hits": 0,
            "total_matches": 0,
            "estimated_matches": None,
            "execution_time_ms": 0
        }
        
        # Determine whether to use probabilistic optimizations
        if use_probabilistic is None:
            use_probabilistic = self.enable_probabilistic
        
        try:
            # Determine max workers based on system capabilities
            if max_workers is None:
                import os
                max_workers = min(os.cpu_count() or 4, 8)  # Default to min(cpu_count, 8)
            
            # Get list of candidate partition files
            import glob
            partition_files = []
            cid_equals_filter = None
            
            # Check if we can use Bloom filters for early pruning
            if use_probabilistic and self.bloom_enabled and filters:
                # Check if we have a filter on the CID field with equality
                for field, op, value in filters:
                    if field == "cid" and op == "==":
                        cid_equals_filter = value
                        break
                
                # If we have a CID equality filter and Bloom filters enabled
                if cid_equals_filter:
                    # Check each partition's Bloom filter to see if the CID might be present
                    filtered_partitions = []
                    
                    # For each partition that has a Bloom filter
                    for partition_id, bloom_filter in self.bloom_filters.items():
                        partition_path = self._get_partition_path(partition_id)
                        if os.path.exists(partition_path):
                            # Check if the CID might be in this partition
                            if bloom_filter.contains(cid_equals_filter):
                                filtered_partitions.append(partition_path)
                                result_stats["bloom_filter_hits"] += 1
                            else:
                                # Definitely not in this partition
                                result_stats["partitions_skipped"] += 1
                    
                    # Use filtered partitions for query
                    partition_files = filtered_partitions
            
            # If no Bloom filter pruning or no matches, use all partitions
            if not partition_files:
                partition_files = glob.glob(os.path.join(self.directory, "*.parquet"))
            
            if not partition_files:
                logger.warning(f"No partition files found in {self.directory}")
                return {}
            
            # Try to estimate cardinality using HyperLogLog
            if use_probabilistic and self.hll_enabled and filters:
                estimated_count = self._estimate_result_cardinality(filters)
                if estimated_count is not None:
                    result_stats["estimated_matches"] = estimated_count
                    
                    # Early termination if estimated count is 0 and we have high confidence
                    if estimated_count == 0 and len(self.hyperloglog_counters) > 0:
                        logger.debug(f"Early termination based on HyperLogLog estimate of 0 results")
                        return {}
            
            # Build filter expression once to reuse
            filter_expr = self._build_filter_expression(filters)
            
            # Create a thread pool for parallel processing
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit each partition file for processing
                futures = []
                for file_path in partition_files:
                    future = executor.submit(
                        self._process_partition, 
                        file_path, 
                        filter_expr, 
                        columns
                    )
                    futures.append(future)
                
                # Collect results as they complete
                tables = []
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result_table, partition_stats = future.result()
                        result_stats["partitions_processed"] += 1
                        
                        if result_table is not None and result_table.num_rows > 0:
                            tables.append(result_table)
                            result_stats["partitions_with_matches"] += 1
                            result_stats["total_matches"] += result_table.num_rows
                    except Exception as e:
                        logger.error(f"Error processing partition: {e}")
            
            # If no results, return empty dict
            if not tables:
                result_stats["execution_time_ms"] = (time.time() - start_time) * 1000
                logger.info(f"Parallel query completed with no results: {result_stats}")
                return {}
            
            # Combine all tables into a single result
            combined_table = pa.concat_tables(tables)
            
            # Update frequency statistics if enabled
            if use_probabilistic and self.cms_enabled and combined_table.num_rows > 0:
                self._update_frequency_statistics(combined_table)
            
            # Apply sorting if specified
            if sort_by and sort_by in combined_table.column_names:
                # For large result sets, sorting can be expensive, so do it efficiently
                if combined_table.num_rows > 100000:
                    # More efficient sorting with chunking for large tables
                    indices = self._parallel_sort(combined_table, sort_by, max_workers)
                    combined_table = combined_table.take(indices)
                else:
                    # Direct sorting for smaller tables
                    indices = pc.sort_indices(combined_table[sort_by])
                    combined_table = combined_table.take(indices)
            
            # Apply limit if specified
            if limit and limit < combined_table.num_rows:
                combined_table = combined_table.slice(0, limit)
            
            # Convert result to dictionary
            result_dict = combined_table.to_pydict()
            
            # Record execution time
            result_stats["execution_time_ms"] = (time.time() - start_time) * 1000
            
            # Log performance metrics
            logger.info(f"Parallel query completed: {result_stats}")
            
            return result_dict
            
        except Exception as e:
            logger.error(f"Error in parallel query: {e}")
            result_stats["execution_time_ms"] = (time.time() - start_time) * 1000
            result_stats["error"] = str(e)
            logger.info(f"Parallel query failed: {result_stats}")
            return {}
    
    def _process_partition(self, file_path: str, filter_expr: Optional[pc.Expression], 
                          columns: Optional[List[str]]) -> Tuple[Optional[pa.Table], Dict[str, Any]]:
        """Process a single partition file for parallel query execution.
        
        Args:
            file_path: Path to the parquet file
            filter_expr: Precompiled filter expression
            columns: Optional list of columns to retrieve
            
        Returns:
            Tuple of (result_table, stats_dict)
        """
        start_time = time.time()
        stats = {
            "file_path": file_path,
            "file_size": os.path.getsize(file_path),
            "row_count": 0,
            "matched_rows": 0,
            "processing_time_ms": 0
        }
        
        try:
            # Create a dataset from just this file
            ds = dataset(file_path, format="parquet")
            
            # Get row count
            stats["row_count"] = ds.count_rows()
            
            # Execute the query against this partition
            table = ds.to_table(filter=filter_expr, columns=columns)
            
            # Record stats
            stats["matched_rows"] = table.num_rows
            stats["processing_time_ms"] = (time.time() - start_time) * 1000
            
            return table, stats
        except Exception as e:
            logger.error(f"Error processing partition {file_path}: {e}")
            stats["error"] = str(e)
            stats["processing_time_ms"] = (time.time() - start_time) * 1000
            return None, stats
            
    @beta_api(since="0.19.0")
    def _parallel_sort(self, table: pa.Table, sort_column: str, max_workers: int) -> pa.Array:
        """Perform efficient parallel sorting for large tables.
        
        This method implements a parallel merge sort algorithm specialized for
        PyArrow tables. It divides the table into chunks, sorts each chunk in
        parallel, and then merges the sorted chunks efficiently.
        
        Args:
            table: PyArrow table to sort
            sort_column: Column name to sort by
            max_workers: Maximum number of worker threads
            
        Returns:
            Sorted indices array
        """
        # Determine chunk size based on table size and worker count
        chunk_size = max(1000, table.num_rows // (max_workers * 2))
        
        # Get array to sort
        sort_array = table[sort_column]
        
        # Define worker function for sorting chunks
        def sort_chunk(start_idx, end_idx):
            # Create a dictionary mapping values to their original positions
            chunk = sort_array.slice(start_idx, end_idx - start_idx)
            chunk_with_positions = list(zip(chunk.to_pylist(), range(start_idx, end_idx)))
            
            # Sort by values
            sorted_chunk = sorted(chunk_with_positions, key=lambda x: x[0])
            
            # Return the original positions in sorted order
            return [pos for _, pos in sorted_chunk]
        
        # Divide the array into chunks and submit sorting tasks
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for i in range(0, table.num_rows, chunk_size):
                end_idx = min(i + chunk_size, table.num_rows)
                future = executor.submit(sort_chunk, i, end_idx)
                futures.append(future)
            
            # Collect sorted chunks
            sorted_chunks = [future.result() for future in futures]
        
        # Merge sorted chunks (simplified version)
        if len(sorted_chunks) == 1:
            # Only one chunk, no merging needed
            return pa.array(sorted_chunks[0])
        else:
            # Merge chunks using numpy for efficiency
            import numpy as np
            
            # Convert chunks to numpy arrays for efficient manipulation
            np_chunks = [np.array(chunk) for chunk in sorted_chunks]
            
            # Get values for merging
            chunk_values = []
            for chunk_indices in np_chunks:
                chunk_values.append(np.array([sort_array[i].as_py() for i in chunk_indices]))
            
            # Merge chunks
            merged_indices = []
            chunk_positions = [0] * len(np_chunks)
            
            # While we haven't exhausted all chunks
            while True:
                # Find the chunk with the smallest current value
                candidates = []
                for i, pos in enumerate(chunk_positions):
                    if pos < len(np_chunks[i]):
                        candidates.append((chunk_values[i][pos], i))
                
                if not candidates:
                    break
                
                # Get the smallest value and its chunk
                _, chunk_idx = min(candidates)
                
                # Add the corresponding index to the merged result
                merged_indices.append(np_chunks[chunk_idx][chunk_positions[chunk_idx]])
                chunk_positions[chunk_idx] += 1
            
            return pa.array(merged_indices)
            
    async def async_query(self, filters: List[Tuple[str, str, Any]] = None, 
                         columns: List[str] = None,
                         sort_by: str = None,
                         limit: int = None,
                         parallel: bool = False,
                         max_workers: Optional[int] = None) -> Dict[str, List]:
        """Async version of query.
        
        Args:
            filters: List of filter tuples (field, op, value)
                     e.g. [("size_bytes", ">", 1024), ("mimetype", "==", "image/jpeg")]
            columns: List of columns to return (None for all)
            sort_by: Field to sort by
            limit: Maximum number of results to return
            parallel: Whether to use parallel execution for complex queries
            max_workers: Maximum number of worker threads (defaults to CPU count)
            
        Returns:
            Dictionary with query results
        """
        if not self.has_asyncio:
            # Fallback to thread pool if asyncio not available
            return await self._run_in_thread_pool(
                self.query, filters, columns, sort_by, limit, parallel, max_workers
            )
        
        # Run the query in a background thread since it's I/O heavy
        return await self._run_in_thread_pool(
            self.query, filters, columns, sort_by, limit, parallel, max_workers
        )
        
    @beta_api(since="0.19.0")
    async def async_parallel_query(self, filters: List[Tuple[str, str, Any]] = None,
                                  columns: List[str] = None,
                                  sort_by: str = None,
                                  limit: int = None,
                                  max_workers: Optional[int] = None) -> Dict[str, List]:
        """Async version of parallel_query.
        
        This method provides a non-blocking way to execute parallel queries,
        ideal for applications that need to maintain responsiveness while
        performing complex queries on large datasets.
        
        Args:
            filters: List of filter tuples (field, op, value)
            columns: List of columns to return (None for all)
            sort_by: Field to sort by
            limit: Maximum number of results to return
            max_workers: Maximum number of worker threads (defaults to CPU count)
            
        Returns:
            Dictionary with query results
        """
        if not self.has_asyncio:
            # Fallback to thread pool if asyncio not available
            return await self._run_in_thread_pool(
                self.parallel_query, filters, columns, sort_by, limit, max_workers
            )
            
        # Execute parallel query in thread pool
        return await self._run_in_thread_pool(
            self.parallel_query, filters, columns, sort_by, limit, max_workers
        )
    
    def get_c_data_interface(self) -> Optional[Dict[str, Any]]:
        """Get the C Data Interface handle for external access.
        
        Returns:
            Dictionary with C Data Interface metadata or None if not enabled
        """
        return self.c_data_interface_handle
        
    def register_content_type(self, cid: str, content_type: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Register content type information for better prefetching.
        
        Args:
            cid: Content identifier
            content_type: Type of content ('parquet', 'arrow', 'columnar', etc.)
            metadata: Additional metadata for type-specific optimizations
        """
        if not self.prefetch_config.get("enable_type_specific_prefetch", True):
            return
            
        self.content_type_registry[cid] = {
            "type": content_type,
            "metadata": metadata or {},
            "registered_at": time.time()
        }
        
    def detect_content_type(self, cid: str, content_bytes: Optional[bytes] = None, 
                           metadata: Optional[Dict[str, Any]] = None) -> str:
        """Detect the content type for a CID.
        
        Args:
            cid: Content identifier
            content_bytes: Optional content bytes for detection
            metadata: Optional metadata with mimetype info
            
        Returns:
            Detected content type string
        """
        # If already registered, return the known type
        if cid in self.content_type_registry:
            return self.content_type_registry[cid]["type"]
            
        # If we have metadata with mimetype
        if metadata and "mimetype" in metadata:
            mimetype = metadata["mimetype"]
            
            # Check for Parquet files
            if mimetype in ["application/vnd.apache.parquet", "application/parquet"]:
                return "parquet"
                
            # Check for Arrow files
            if mimetype in ["application/vnd.apache.arrow", "application/arrow"]:
                return "arrow"
                
            # Check for columnar data formats
            if mimetype in ["application/octet-stream", "application/vnd.apache.orc", 
                           "application/vnd.apache.avro"]:
                # Further analyze based on extension or metadata
                extension = metadata.get("extension", "")
                if extension in [".parquet", ".arrow", ".orc", ".avro"]:
                    return extension[1:]  # Remove the dot
                    
                return "columnar"
        
        # If we have content bytes, try to detect from content
        if content_bytes and len(content_bytes) > 8:
            # Check Parquet magic bytes (PAR1)
            if content_bytes[:4] == b'PAR1' or content_bytes[-4:] == b'PAR1':
                return "parquet"
                
            # Check Arrow magic bytes (ARROW1)
            if content_bytes[:6] == b'ARROW1':
                return "arrow"
        
        # Default to generic
        return "generic"

    def prefetch_parquet_rowgroups(self, cid: str, content_handle: Any, 
                                  row_group_indices: Optional[List[int]] = None,
                                  columns: Optional[List[str]] = None,
                                  timeout_ms: Optional[int] = None) -> Dict[str, Any]:
        """Prefetch specific row groups from a Parquet file.
        
        This method optimizes access to Parquet files by prefetching row groups
        in a streaming fashion, exploiting Parquet's columnar format for efficient
        data access.
        
        Args:
            cid: Content identifier
            content_handle: File handle, path, or BytesIO object containing Parquet data
            row_group_indices: List of row group indices to prefetch (None for all)
            columns: List of columns to prefetch (None for all)
            timeout_ms: Maximum time to spend prefetching in milliseconds
            
        Returns:
            Dictionary with prefetch operation results
        """
        if not self.prefetch_config.get("enable_type_specific_prefetch", True):
            return {"success": False, "reason": "type-specific prefetching disabled"}
            
        # Record start time for metrics
        start_time = time.time()
        
        # Get timeout from config if not specified
        if timeout_ms is None:
            timeout_ms = self.prefetch_config.get("prefetch_timeout_ms", 5000)
            
        result = {
            "success": False,
            "operation": "prefetch_parquet_rowgroups",
            "cid": cid,
            "prefetched_bytes": 0,
            "prefetched_row_groups": 0,
            "prefetched_columns": 0,
            "duration_ms": 0
        }
        
        try:
            # Open the Parquet file
            pf = pq.ParquetFile(content_handle)
            
            # If no row groups specified, use configuration
            if row_group_indices is None:
                # Get lookahead setting from config
                lookahead = self.prefetch_config.get("parquet_prefetch", {}).get("row_group_lookahead", 2)
                # Prefetch a reasonable number of row groups
                row_group_indices = list(range(min(lookahead, pf.num_row_groups)))
                
            # If no columns specified, use priority columns from config
            if columns is None:
                # Get metadata-only columns from config
                metadata_columns = self.prefetch_config.get("parquet_prefetch", {}).get(
                    "metadata_only_columns", ["cid", "size_bytes", "added_timestamp"]
                )
                # Get high priority columns from config
                high_priority = self.prefetch_config.get("prefetch_priority", {}).get(
                    "high", []
                )
                # Combine metadata and high priority columns
                columns = list(set(metadata_columns + high_priority))
            
            # Set maximum prefetch size from config
            max_prefetch_size_mb = self.prefetch_config.get("parquet_prefetch", {}).get("max_prefetch_size_mb", 64)
            max_prefetch_bytes = max_prefetch_size_mb * 1024 * 1024
            
            # Track prefetched data
            prefetched_bytes = 0
            prefetched_row_groups = 0
            prefetched_columns_set = set()
            
            # Check if we should prefetch statistics
            prefetch_statistics = self.prefetch_config.get("parquet_prefetch", {}).get("prefetch_statistics", True)
            
            # Prefetch statistics if enabled - this can dramatically improve future query performance
            if prefetch_statistics:
                # Access metadata to prefetch statistics
                metadata = pf.metadata
                for col in pf.schema:
                    col_name = col.name
                    if columns and col_name not in columns:
                        continue
                        
                    # Access statistics for each column (this pulls them into memory)
                    for row_group_idx in row_group_indices:
                        if row_group_idx < metadata.num_row_groups:
                            try:
                                # Just accessing the statistics prefetches them
                                # Estimate size of statistics (~100 bytes per column stats)
                                prefetched_bytes += 100
                                prefetched_columns_set.add(col_name)
                            except Exception:
                                # Some columns might not have statistics
                                pass
            
            # Create a batched reader for the specified row groups and columns
            total_rows = 0
            for row_group_idx in row_group_indices:
                # Check timeout
                if (time.time() - start_time) * 1000 > timeout_ms:
                    result["timeout"] = True
                    break
                    
                # Check size limit
                if prefetched_bytes >= max_prefetch_bytes:
                    result["size_limit_reached"] = True
                    break
                    
                try:
                    # Read the row group
                    table = pf.read_row_group(row_group_idx, columns=columns)
                    
                    # Update counters
                    row_count = table.num_rows
                    total_rows += row_count
                    prefetched_bytes += table.nbytes
                    prefetched_row_groups += 1
                    prefetched_columns_set.update(table.column_names)
                    
                    # If we're using Arrow C Data Interface, export to shared memory
                    if self.enable_c_data_interface and self.has_plasma:
                        self._export_to_c_data_interface(table, f"{cid}_rg{row_group_idx}")
                except Exception as e:
                    logger.warning(f"Error prefetching row group {row_group_idx} for {cid}: {e}")
            
            # Update result with stats
            result["success"] = prefetched_row_groups > 0
            result["prefetched_bytes"] = prefetched_bytes
            result["prefetched_row_groups"] = prefetched_row_groups
            result["prefetched_columns"] = len(prefetched_columns_set)
            result["prefetched_rows"] = total_rows
            result["prefetched_columns_list"] = list(prefetched_columns_set)
            
            # Update global prefetch stats
            self.prefetch_stats["total_prefetch_operations"] += 1
            self.prefetch_stats["type_specific_prefetch_operations"]["parquet"] += 1
            self.prefetch_stats["successful_prefetch_operations"] += 1
            self.prefetch_stats["total_prefetch_bytes"] += prefetched_bytes
            
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error prefetching Parquet row groups for {cid}: {e}")
            
        # Record elapsed time
        elapsed_ms = (time.time() - start_time) * 1000
        result["duration_ms"] = elapsed_ms
        self.prefetch_stats["prefetch_latency_ms"].append(elapsed_ms)
            
        return result
        
    def prefetch_content(self, cid: str, content_handle: Any = None, 
                        content_type: Optional[str] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Prefetch content based on detected type and optimized strategies.
        
        This method dispatches to type-specific prefetching strategies based on
        the content type, providing optimized prefetching for different data formats.
        
        Args:
            cid: Content identifier
            content_handle: File handle, path, or bytes object with content
            content_type: Optional explicit content type, or will be auto-detected
            metadata: Additional metadata about the content
            
        Returns:
            Dictionary with prefetch results
        """
        # Skip if prefetching disabled
        if not self.prefetch_config.get("enable_type_specific_prefetch", True):
            return {"success": False, "reason": "prefetching disabled"}
            
        # Skip if already prefetching this CID
        if cid in self.prefetch_in_progress:
            return {"success": False, "reason": "already prefetching", "cid": cid}
            
        # Add to in-progress set
        self.prefetch_in_progress.add(cid)
        
        try:
            # Detect content type if not provided
            if not content_type:
                # Try from registry first
                if cid in self.content_type_registry:
                    content_type = self.content_type_registry[cid]["type"]
                # Otherwise detect from content if possible
                elif content_handle is not None:
                    # If it's bytes-like, use it directly
                    if isinstance(content_handle, (bytes, bytearray, memoryview)):
                        content_bytes = content_handle
                    # If it's a string path, open and read a small header
                    elif isinstance(content_handle, str) and os.path.exists(content_handle):
                        with open(content_handle, 'rb') as f:
                            content_bytes = f.read(1024)  # Just read enough for detection
                    # For other file-like objects, read a header
                    elif hasattr(content_handle, 'read') and callable(content_handle.read):
                        if hasattr(content_handle, 'tell') and hasattr(content_handle, 'seek'):
                            current_pos = content_handle.tell()
                            content_bytes = content_handle.read(1024)
                            content_handle.seek(current_pos)  # Restore position
                        else:
                            # Can't seek, so can't safely read header
                            content_bytes = None
                    else:
                        content_bytes = None
                        
                    content_type = self.detect_content_type(cid, content_bytes, metadata)
                else:
                    # Default to generic if we can't detect
                    content_type = "generic"
                    
            # Register the content type for future use
            self.register_content_type(cid, content_type, metadata)
            
            # Dispatch to the appropriate prefetch method based on content type
            if content_type == "parquet":
                return self.prefetch_parquet_rowgroups(cid, content_handle)
            elif content_type == "arrow":
                # Placeholder for Arrow-specific prefetching
                # Add implementation for Arrow-specific optimizations
                pass
            elif content_type == "columnar":
                # Placeholder for generic columnar data formats
                # Add implementation for columnar-format optimizations
                pass
            
            # Generic fallback
            # For non-specialized types, we can still do basic prefetching
            # This is a placeholder for any basic prefetching logic
            return {"success": False, "reason": f"No specialized prefetching for {content_type}"}
            
        except Exception as e:
            logger.error(f"Error in prefetch_content for {cid}: {e}")
            return {"success": False, "error": str(e), "error_type": type(e).__name__}
        finally:
            # Remove from in-progress set
            self.prefetch_in_progress.discard(cid)
    
    @beta_api(since="0.19.0")
    def batch_prefetch(self, cids: List[str], metadata: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
        """Prefetch multiple CIDs in a batch operation for improved efficiency.
        
        This method optimizes the prefetching process by batching multiple requests
        together, which reduces overhead and improves throughput. It's particularly
        useful for applications that need to access multiple related items in sequence.
        
        Args:
            cids: List of content identifiers to prefetch
            metadata: Optional metadata for each CID (used for content type detection)
            
        Returns:
            Dictionary mapping CIDs to their prefetch results
        """
        if not cids:
            return {}
            
        # Initialize results
        results = {cid: {"success": False, "reason": "Not processed"} for cid in cids}
        
        # Skip CIDs that are already being prefetched
        filtered_cids = [cid for cid in cids if cid not in self.prefetch_in_progress]
        
        # Group CIDs by content type for optimized batch processing
        content_type_groups = {}
        
        # First pass: determine content types for grouping
        for cid in filtered_cids:
            # Mark as in-progress
            self.prefetch_in_progress.add(cid)
            
            # Get content type from registry or detect if possible
            if cid in self.content_type_registry:
                content_type = self.content_type_registry[cid]["type"]
            elif metadata and cid in metadata:
                cid_metadata = metadata[cid]
                content_type = self.detect_content_type(cid, None, cid_metadata)
            else:
                # Default to generic if we can't determine
                content_type = "generic"
                
            # Group by content type
            if content_type not in content_type_groups:
                content_type_groups[content_type] = []
            content_type_groups[content_type].append(cid)
            
        # Process each content type group with type-specific optimizations
        for content_type, type_cids in content_type_groups.items():
            if content_type == "parquet":
                # Specialized batch processing for Parquet files
                parquet_results = self._batch_prefetch_parquet(type_cids, metadata)
                results.update(parquet_results)
            elif content_type == "arrow":
                # Specialized batch processing for Arrow files
                arrow_results = self._batch_prefetch_arrow(type_cids, metadata)
                results.update(arrow_results)
            else:
                # Generic handling for other content types
                # Process each CID individually but in an optimized batch context
                for cid in type_cids:
                    try:
                        result = self.prefetch_content(cid, None, metadata.get(cid) if metadata else None)
                        results[cid] = result
                    except Exception as e:
                        results[cid] = {
                            "success": False,
                            "error": str(e),
                            "error_type": type(e).__name__
                        }
                    finally:
                        # Remove from in-progress set
                        self.prefetch_in_progress.discard(cid)
        
        # Collect statistics
        successful = sum(1 for cid, result in results.items() if result.get("success", False))
        total_ops = len(cids)
        
        # Update global statistics
        self.prefetch_stats["total_prefetch_operations"] += total_ops
        self.prefetch_stats["successful_prefetch_operations"] += successful
        
        return results
        
    @experimental_api(since="0.19.0")
    async def async_batch_prefetch(self, cids: List[str], metadata: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
        """Async version of batch_prefetch.
        
        This method provides a non-blocking interface for prefetching multiple CIDs,
        allowing the calling code to continue execution while prefetching happens
        in the background.
        
        Args:
            cids: List of content identifiers to prefetch
            metadata: Optional metadata for each CID (used for content type detection)
            
        Returns:
            Dictionary mapping CIDs to their prefetch results
        """
        if not self.has_asyncio:
            # Fallback to thread pool if asyncio not available
            return await self._run_in_thread_pool(self.batch_prefetch, cids, metadata)
            
        if not cids:
            return {}
            
        # Create task groups for concurrent execution
        import anyio
        
        # Initialize results
        results = {cid: {"success": False, "reason": "Not processed"} for cid in cids}
        
        # Skip CIDs that are already being prefetched
        filtered_cids = [cid for cid in cids if cid not in self.prefetch_in_progress]
        
        # Group by content type for optimized batch processing
        content_type_groups = {}
        
        # First pass: determine content types for grouping (non-blocking)
        for cid in filtered_cids:
            # Mark as in-progress
            self.prefetch_in_progress.add(cid)
            
            # Get or detect content type
            if cid in self.content_type_registry:
                content_type = self.content_type_registry[cid]["type"]
            elif metadata and cid in metadata:
                cid_metadata = metadata[cid]
                # We'll do type detection in a background thread since it might involve I/O
                content_type = await self._run_in_thread_pool(
                    self.detect_content_type, cid, None, cid_metadata
                )
            else:
                # Default to generic
                content_type = "generic"
                
            # Group by content type
            if content_type not in content_type_groups:
                content_type_groups[content_type] = []
            content_type_groups[content_type].append(cid)
        
        # Create tasks for each content type group
        tasks = []
        
        for content_type, type_cids in content_type_groups.items():
            if content_type == "parquet":
                # Create task for Parquet batch processing
                task = anyio.create_task(
                    self._async_batch_prefetch_parquet(type_cids, metadata)
                )
                tasks.append((content_type, task))
            elif content_type == "arrow":
                # Create task for Arrow batch processing
                task = anyio.create_task(
                    self._async_batch_prefetch_arrow(type_cids, metadata)
                )
                tasks.append((content_type, task))
            else:
                # Generic processing - create individual tasks
                for cid in type_cids:
                    cid_metadata = metadata.get(cid) if metadata else None
                    task = anyio.create_task(
                        self._async_prefetch_content(cid, cid_metadata)
                    )
                    tasks.append((cid, task))
        
        # Await all tasks and collect results
        for key, task in tasks:
            try:
                task_result = await task
                
                # Process results based on the task type
                if isinstance(key, str) and key in content_type_groups:
                    # This is a content type group result
                    results.update(task_result)
                else:
                    # This is an individual CID result
                    results[key] = task_result
            except Exception as e:
                # Handle task failure
                if isinstance(key, str) and key in content_type_groups:
                    # Mark all CIDs in this group as failed
                    for cid in content_type_groups[key]:
                        results[cid] = {
                            "success": False,
                            "error": f"Batch task failed: {str(e)}",
                            "error_type": type(e).__name__
                        }
                else:
                    # Mark individual CID as failed
                    results[key] = {
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                    
                # Remove from in-progress set
                if isinstance(key, str) and key in content_type_groups:
                    for cid in content_type_groups[key]:
                        self.prefetch_in_progress.discard(cid)
                else:
                    self.prefetch_in_progress.discard(key)
        
        # Collect statistics
        successful = sum(1 for cid, result in results.items() if result.get("success", False))
        total_ops = len(cids)
        
        # Update global statistics
        self.prefetch_stats["total_prefetch_operations"] += total_ops
        self.prefetch_stats["successful_prefetch_operations"] += successful
        
        return results
    
    async def _async_prefetch_content(self, cid: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Async implementation of prefetch_content."""
        try:
            # Delegate to thread pool for I/O operations
            result = await self._run_in_thread_pool(
                self.prefetch_content, cid, None, metadata
            )
            return result
        finally:
            # Remove from in-progress set
            self.prefetch_in_progress.discard(cid)
    
    async def _async_batch_prefetch_parquet(self, cids: List[str], metadata: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
        """Async implementation of batch prefetch for Parquet files."""
        try:
            # For now, delegate to thread pool
            # In a future implementation, this could be fully async with native async Parquet support
            return await self._run_in_thread_pool(
                self._batch_prefetch_parquet, cids, metadata
            )
        finally:
            # Remove all from in-progress
            for cid in cids:
                self.prefetch_in_progress.discard(cid)
    
    async def _async_batch_prefetch_arrow(self, cids: List[str], metadata: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
        """Async implementation of batch prefetch for Arrow files."""
        try:
            # For now, delegate to thread pool
            # In a future implementation, this could be fully async with native async Arrow support
            return await self._run_in_thread_pool(
                self._batch_prefetch_arrow, cids, metadata
            )
        finally:
            # Remove all from in-progress
            for cid in cids:
                self.prefetch_in_progress.discard(cid)
    
    def _batch_prefetch_parquet(self, cids: List[str], metadata: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
        """Batch prefetch implementation specialized for Parquet files.
        
        Args:
            cids: List of Parquet file CIDs to prefetch
            metadata: Optional metadata for the CIDs
            
        Returns:
            Dictionary mapping CIDs to prefetch results
        """
        results = {}
        
        # Update type-specific statistics
        self.prefetch_stats["type_specific_prefetch_operations"]["parquet"] += len(cids)
        
        # For each Parquet file, prefetch row groups and metadata
        for cid in cids:
            try:
                # Individual prefetch but with batch context awareness
                result = self.prefetch_content(cid, None, metadata.get(cid) if metadata else None)
                results[cid] = result
            except Exception as e:
                results[cid] = {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            finally:
                # Remove from in-progress set
                self.prefetch_in_progress.discard(cid)
                
        return results
    
    def _batch_prefetch_arrow(self, cids: List[str], metadata: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
        """Batch prefetch implementation specialized for Arrow files.
        
        Args:
            cids: List of Arrow file CIDs to prefetch
            metadata: Optional metadata for the CIDs
            
        Returns:
            Dictionary mapping CIDs to prefetch results
        """
        results = {}
        
        # Update type-specific statistics
        self.prefetch_stats["type_specific_prefetch_operations"]["arrow"] += len(cids)
        
        # Arrow-specific batch optimizations would go here
        # For now, process individually but in a batch context
        for cid in cids:
            try:
                result = self.prefetch_content(cid, None, metadata.get(cid) if metadata else None)
                results[cid] = result
            except Exception as e:
                results[cid] = {
                    "success": False, 
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            finally:
                # Remove from in-progress set
                self.prefetch_in_progress.discard(cid)
                
        return results
    
    @beta_api(since="0.19.0")
    def get_prefetch_stats(self) -> Dict[str, Any]:
        """Get statistics about prefetching operations.
        
        Returns:
            Dictionary with prefetch statistics
        """
        stats_copy = dict(self.prefetch_stats)
        
        # Calculate derived metrics
        total_ops = stats_copy["total_prefetch_operations"]
        if total_ops > 0:
            stats_copy["success_rate"] = stats_copy["successful_prefetch_operations"] / total_ops
            
        # Hits and misses
        total_accesses = stats_copy["prefetch_hits"] + stats_copy["prefetch_misses"]
        if total_accesses > 0:
            stats_copy["hit_rate"] = stats_copy["prefetch_hits"] / total_accesses
            
        # Calculate latency statistics if we have data
        latencies = stats_copy["prefetch_latency_ms"]
        if latencies:
            stats_copy["latency_stats"] = {
                "min_ms": min(latencies),
                "max_ms": max(latencies),
                "avg_ms": sum(latencies) / len(latencies),
                "total_ms": sum(latencies),
                "count": len(latencies)
            }
            
            # Calculate percentiles if we have enough data
            if len(latencies) >= 10:
                sorted_latencies = sorted(latencies)
                p50_idx = len(sorted_latencies) // 2
                p90_idx = int(len(sorted_latencies) * 0.9)
                p99_idx = int(len(sorted_latencies) * 0.99)
                
                stats_copy["latency_stats"]["p50_ms"] = sorted_latencies[p50_idx]
                stats_copy["latency_stats"]["p90_ms"] = sorted_latencies[p90_idx]
                stats_copy["latency_stats"]["p99_ms"] = sorted_latencies[p99_idx]
        
        # Content type distribution
        type_ops = stats_copy["type_specific_prefetch_operations"]
        type_sum = sum(type_ops.values())
        if type_sum > 0:
            stats_copy["type_distribution"] = {k: v / type_sum for k, v in type_ops.items()}
            
        # Return the enriched stats
        return stats_copy
        
    @experimental_api(since="0.19.0")
    async def async_get_prefetch_stats(self) -> Dict[str, Any]:
        """Async version of get_prefetch_stats.
        
        Returns:
            Dictionary with prefetch statistics
        """
        if not self.has_asyncio:
            # Fallback to thread pool if asyncio not available
            return await self._run_in_thread_pool(self.get_prefetch_stats)
            
        # Since this is just reading in-memory stats, we can implement it directly
        # without delegating to a background thread for better performance
        stats_copy = dict(self.prefetch_stats)
        
        # Calculate derived metrics
        total_ops = stats_copy["total_prefetch_operations"]
        if total_ops > 0:
            stats_copy["success_rate"] = stats_copy["successful_prefetch_operations"] / total_ops
            
        # Hits and misses
        total_accesses = stats_copy["prefetch_hits"] + stats_copy["prefetch_misses"]
        if total_accesses > 0:
            stats_copy["hit_rate"] = stats_copy["prefetch_hits"] / total_accesses
            
        # Calculate latency statistics if we have data
        latencies = stats_copy["prefetch_latency_ms"]
        if latencies:
            stats_copy["latency_stats"] = {
                "min_ms": min(latencies),
                "max_ms": max(latencies),
                "avg_ms": sum(latencies) / len(latencies),
                "total_ms": sum(latencies),
                "count": len(latencies)
            }
            
            # Calculate percentiles if we have enough data
            if len(latencies) >= 10:
                sorted_latencies = sorted(latencies)
                p50_idx = len(sorted_latencies) // 2
                p90_idx = int(len(sorted_latencies) * 0.9)
                p99_idx = int(len(sorted_latencies) * 0.99)
                
                stats_copy["latency_stats"]["p50_ms"] = sorted_latencies[p50_idx]
                stats_copy["latency_stats"]["p90_ms"] = sorted_latencies[p90_idx]
                stats_copy["latency_stats"]["p99_ms"] = sorted_latencies[p99_idx]
        
        # Content type distribution
        type_ops = stats_copy["type_specific_prefetch_operations"]
        type_sum = sum(type_ops.values())
        if type_sum > 0:
            stats_copy["type_distribution"] = {k: v / type_sum for k, v in type_ops.items()}
            
        return stats_copy
        
    @stable_api(since="0.19.0")
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        in_memory_rows = self.in_memory_batch.num_rows if self.in_memory_batch is not None else 0
        
        total_rows = in_memory_rows
        total_size = 0
        partition_stats = []
        
        # Calculate stats for each partition
        for partition_id, partition in self.partitions.items():
            total_rows += partition.get('rows', 0)
            total_size += partition.get('size', 0)
            partition_stats.append({
                'id': partition_id,
                'rows': partition.get('rows', 0),
                'size_bytes': partition.get('size', 0),
                'created': partition.get('created', 0),
                'modified': partition.get('modified', 0)
            })
            
        # Count by storage tier
        tier_counts = {}
        try:
            ds = dataset(self.directory, format="parquet")
            tier_table = ds.to_table(columns=["storage_tier"])
            
            # Use value_counts to count tiers
            if "storage_tier" in tier_table.column_names:
                storage_tiers = tier_table["storage_tier"].to_numpy()
                for tier in set(storage_tiers):
                    tier_counts[tier] = int((storage_tiers == tier).sum())
        except Exception as e:
            logger.error(f"Error counting storage tiers: {e}")
        
        stats_dict = {
            'total_rows': total_rows,
            'total_size_bytes': total_size,
            'partition_count': len(self.partitions),
            'current_partition_id': self.current_partition_id,
            'in_memory_rows': in_memory_rows,
            'partitions': partition_stats,
            'directory': self.directory,
            'by_storage_tier': tier_counts,
            'last_sync_time': self.last_sync_time,
            'modified_since_sync': self.modified_since_sync
        }
        
        # Add C Data Interface info if enabled
        if self.enable_c_data_interface:
            stats_dict['c_data_interface_enabled'] = True
            if self.c_data_interface_handle:
                stats_dict['c_data_interface'] = {
                    'available': True,
                    'plasma_socket': self.c_data_interface_handle.get('plasma_socket'),
                    'num_rows': self.c_data_interface_handle.get('num_rows'),
                    'timestamp': self.c_data_interface_handle.get('timestamp')
                }
            else:
                stats_dict['c_data_interface'] = {'available': False}
        else:
            stats_dict['c_data_interface_enabled'] = False
        
        # Add prefetch stats if enabled
        if hasattr(self, 'prefetch_config') and self.prefetch_config.get("enable_type_specific_prefetch", True):
            stats_dict['prefetch_enabled'] = True
            stats_dict['prefetch_stats'] = self.get_prefetch_stats()
            stats_dict['content_type_registry_size'] = len(self.content_type_registry)
        else:
            stats_dict['prefetch_enabled'] = False
            
        return stats_dict
        
    @stable_api(since="0.19.0")
    def delete(self, cid: str) -> bool:
        """Delete a CID from the cache.
        
        Args:
            cid: Content identifier
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            # Remove from in-memory batch if present
            if self.in_memory_batch is not None:
                table = pa.Table.from_batches([self.in_memory_batch])
                mask = pc.equal(pc.field('cid'), pa.scalar(cid))
                
                # Count matches in memory
                in_memory_matches = table.filter(mask).num_rows
                
                if in_memory_matches > 0:
                    # Create new batch without this CID
                    inverse_mask = pc.invert(mask)
                    filtered_table = table.filter(inverse_mask)
                    
                    if filtered_table.num_rows > 0:
                        self.in_memory_batch = filtered_table.to_batches()[0]
                    else:
                        self.in_memory_batch = None
                        
                    self.modified_since_sync = True
                    
            # Check for matches in other partitions
            # This is an expensive operation that reprocesses all partitions
            # In production, consider a more efficient approach with a deletion log
            match_found = False
            
            for partition_id, partition in list(self.partitions.items()):
                if partition_id == self.current_partition_id:
                    continue  # Skip current partition (handled in memory)
                    
                partition_path = partition['path']
                if not os.path.exists(partition_path):
                    continue
                    
                table = pq.read_table(partition_path)
                mask = pc.equal(pc.field('cid'), pa.scalar(cid))
                matches = table.filter(mask).num_rows
                
                if matches > 0:
                    match_found = True
                    
                    # Create new table without this CID
                    inverse_mask = pc.invert(mask)
                    filtered_table = table.filter(inverse_mask)
                    
                    # Write back to file
                    pq.write_table(
                        filtered_table,
                        partition_path,
                        compression='zstd',
                        compression_level=5,
                        use_dictionary=True,
                        write_statistics=True
                    )
                    
                    # Update partition metadata
                    self.partitions[partition_id]['rows'] = filtered_table.num_rows
                    self.partitions[partition_id]['size'] = os.path.getsize(partition_path)
                    self.partitions[partition_id]['modified'] = os.path.getmtime(partition_path)
            
            # Write in-memory changes if we found matches
            if self.modified_since_sync:
                self.sync()
            
            # Update C Data Interface if enabled
            if self.enable_c_data_interface:
                self._export_to_c_data_interface()
                
            return in_memory_matches > 0 or match_found
            
        except Exception as e:
            logger.error(f"Error deleting CID {cid}: {e}")
            return False
    
    @experimental_api(since="0.19.0")
    async def async_delete(self, cid: str) -> bool:
        """Async version of delete.
        
        Args:
            cid: Content identifier
            
        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.has_asyncio:
            # Fallback to thread pool if asyncio not available
            return await self._run_in_thread_pool(self.delete, cid)
        
        try:
            # Process in-memory batch in current thread (fast)
            in_memory_matches = 0
            if self.in_memory_batch is not None:
                table = pa.Table.from_batches([self.in_memory_batch])
                mask = pc.equal(pc.field('cid'), pa.scalar(cid))
                
                # Count matches in memory
                in_memory_matches = table.filter(mask).num_rows
                
                if in_memory_matches > 0:
                    # Create new batch without this CID
                    inverse_mask = pc.invert(mask)
                    filtered_table = table.filter(inverse_mask)
                    
                    if filtered_table.num_rows > 0:
                        self.in_memory_batch = filtered_table.to_batches()[0]
                    else:
                        self.in_memory_batch = None
                        
                    self.modified_since_sync = True
            
            # Process disk partitions in background thread
            match_found = await self._run_in_thread_pool(self._delete_from_disk_partitions, cid)
            
            # If either in-memory or disk operations found matches, schedule background operations
            if in_memory_matches > 0 or match_found:
                if self.modified_since_sync:
                    # Schedule sync in background
                    anyio.create_task(self._run_in_thread_pool(self.sync))
                
                # Update C Data Interface if enabled (in background)
                if self.enable_c_data_interface:
                    anyio.create_task(self._run_in_thread_pool(self._export_to_c_data_interface))
            
            return in_memory_matches > 0 or match_found
            
        except Exception as e:
            logger.error(f"Error in async_delete for CID {cid}: {e}")
            return False
    
    def _delete_from_disk_partitions(self, cid: str) -> bool:
        """Delete a CID from on-disk partitions.
        
        Args:
            cid: Content identifier
            
        Returns:
            True if found and deleted from any partition, False otherwise
        """
        match_found = False
        
        for partition_id, partition in list(self.partitions.items()):
            if partition_id == self.current_partition_id:
                continue  # Skip current partition (handled in memory)
                
            partition_path = partition['path']
            if not os.path.exists(partition_path):
                continue
                
            try:
                table = pq.read_table(partition_path)
                mask = pc.equal(pc.field('cid'), pa.scalar(cid))
                matches = table.filter(mask).num_rows
                
                if matches > 0:
                    match_found = True
                    
                    # Create new table without this CID
                    inverse_mask = pc.invert(mask)
                    filtered_table = table.filter(inverse_mask)
                    
                    # Write back to file
                    pq.write_table(
                        filtered_table,
                        partition_path,
                        compression='zstd',
                        compression_level=5,
                        use_dictionary=True,
                        write_statistics=True
                    )
                    
                    # Update partition metadata
                    self.partitions[partition_id]['rows'] = filtered_table.num_rows
                    self.partitions[partition_id]['size'] = os.path.getsize(partition_path)
                    self.partitions[partition_id]['modified'] = os.path.getmtime(partition_path)
            except Exception as e:
                logger.error(f"Error processing partition {partition_id} for delete: {e}")
                
        return match_found
    
    def get_all_cids(self) -> List[str]:
        """Get all CIDs in the cache.
        
        Returns:
            List of all CIDs in the cache
        """
        try:
            ds = dataset(self.directory, format="parquet")
            table = ds.to_table(columns=["cid"])
            return table["cid"].to_pylist()
        except Exception as e:
            logger.error(f"Error getting all CIDs: {e}")
            return []
    
    async def async_get_all_cids(self) -> List[str]:
        """Async version of get_all_cids.
        
        Returns:
            List of all CIDs in the cache
        """
        # Run the operation in a background thread
        return await self._run_in_thread_pool(self.get_all_cids)
    
    def clear(self) -> None:
        """Clear the entire cache."""
        try:
            # Delete all partition files
            for partition in self.partitions.values():
                try:
                    if os.path.exists(partition['path']):
                        os.remove(partition['path'])
                except Exception as e:
                    logger.error(f"Error removing partition file {partition['path']}: {e}")
                    
            # Reset state
            self.partitions = {}
            self.current_partition_id = 0
            self.in_memory_batch = None
            self.modified_since_sync = False
            self.last_sync_time = time.time()
            
            # Update C Data Interface with empty data
            if self.enable_c_data_interface:
                self._export_to_c_data_interface()
            
            logger.debug("Cleared ParquetCIDCache")
            
        except Exception as e:
            logger.error(f"Error clearing ParquetCIDCache: {e}")
            
    def cleanup(self):
        """Release resources used by the cache."""
        try:
            # Make sure data is synced to disk
            if self.modified_since_sync:
                self.sync()
                
            # Stop sync timer if running
            if hasattr(self, 'sync_timer') and self.sync_timer:
                self.sync_timer.cancel()
                
            # Close Plasma client if it exists
            if self.plasma_client:
                try:
                    # Remove our object from plasma if it exists
                    if self.current_object_id and self.plasma_client.contains(self.current_object_id):
                        self.plasma_client.delete([self.current_object_id])
                    self.plasma_client.disconnect()
                    self.plasma_client = None
                except Exception as e:
                    logger.error(f"Error closing plasma client: {e}")
            
            # Shutdown thread pool
            if hasattr(self, 'thread_pool'):
                try:
                    self.thread_pool.shutdown(wait=False)
                except Exception as e:
                    logger.error(f"Error shutting down thread pool: {e}")
                    
            logger.debug("Cleaned up ParquetCIDCache resources")
            
        except Exception as e:
            logger.error(f"Error during ParquetCIDCache cleanup: {e}")
            
    def __del__(self):
        """Destructor to ensure proper cleanup."""
        self.cleanup()
    
    @staticmethod
    def access_via_c_data_interface(cache_dir: str, 
                                    name_suffix: str = None,
                                    object_id_hex: str = None,
                                    start_plasma_if_needed: bool = False,
                                    plasma_memory_mb: int = 1000,
                                    wait_for_object: bool = False,
                                    wait_timeout_sec: float = 10.0,
                                    return_pandas: bool = False) -> Dict[str, Any]:
        """Access ParquetCIDCache from another process via Arrow C Data Interface.
        
        This static method enables external processes to access the cache data
        without copying it. This is particularly useful for:
        - Multi-language access (C++, Rust, JavaScript, Go, TypeScript)
        - Zero-copy data exchange with other processes
        - Low-latency access for performance-critical operations
        
        Args:
            cache_dir: Directory where the ParquetCIDCache is stored
            name_suffix: Optional name suffix to identify a specific exported table
                         when multiple tables have been exported (e.g., "metadata", "stats")
            object_id_hex: Optional specific object ID to access (if you already know it)
            start_plasma_if_needed: Whether to automatically start the Plasma store if not found
            plasma_memory_mb: Memory allocation for Plasma store if auto-starting (in MB)
            wait_for_object: Whether to wait for the object if it's not immediately available
            wait_timeout_sec: Maximum time to wait for object availability (in seconds)
            return_pandas: Whether to convert Arrow table to pandas DataFrame in result
            
        Returns:
            Dictionary with access information and the Arrow Table, or error details
        """
        result = {
            "success": False,
            "operation": "access_via_c_data_interface",
            "timestamp": time.time()
        }
        
        try:
            # Check if PyArrow and Plasma are available
            import pyarrow as pa
            try:
                import pyarrow.plasma as plasma
            except ImportError:
                result["error"] = "PyArrow Plasma not available. Install with: pip install ipfs_kit_py[arrow]"
                result["install_command"] = "pip install ipfs_kit_py[arrow]"
                return result
                
            # Find C Data Interface metadata file
            cache_dir = os.path.expanduser(cache_dir)
            
            # Build metadata file path with optional suffix
            if name_suffix:
                cdi_path = os.path.join(cache_dir, f"c_data_interface_{name_suffix}.json")
                # Also check the default path as fallback
                default_cdi_path = os.path.join(cache_dir, "c_data_interface.json")
            else:
                cdi_path = os.path.join(cache_dir, "c_data_interface.json")
                default_cdi_path = None
                
            # Verify metadata file existence
            if not os.path.exists(cdi_path):
                if default_cdi_path and os.path.exists(default_cdi_path):
                    cdi_path = default_cdi_path
                    result["warning"] = f"Using default metadata file instead of suffixed version"
                else:
                    # Check if there are any other metadata files
                    all_metadata_files = [f for f in os.listdir(cache_dir) 
                                         if f.startswith("c_data_interface") and f.endswith(".json")]
                    if all_metadata_files:
                        result["error"] = f"C Data Interface metadata not found at {cdi_path}. Available options: {all_metadata_files}"
                    else:
                        result["error"] = f"No C Data Interface metadata found in {cache_dir}"
                    return result
            
            # Load C Data Interface metadata
            try:
                with open(cdi_path, "r") as f:
                    cdi_metadata = json.load(f)
                    result["metadata_path"] = cdi_path
            except json.JSONDecodeError as e:
                result["error"] = f"Invalid JSON in metadata file at {cdi_path}: {str(e)}"
                return result
                
            # Connect to plasma store
            plasma_socket = cdi_metadata.get("plasma_socket")
            
            # If specific object ID was provided, use it instead of the one in metadata
            if object_id_hex:
                cdi_metadata["object_id"] = object_id_hex
                
            # Handle missing or invalid plasma store
            if not plasma_socket or not os.path.exists(plasma_socket):
                if start_plasma_if_needed:
                    # Attempt to start a plasma store
                    result["plasma_started"] = True
                    try:
                        plasma_socket, plasma_process = ParquetCIDCache._start_plasma_store_static(
                            memory_limit_mb=plasma_memory_mb
                        )
                        result["plasma_socket"] = plasma_socket
                        result["plasma_process"] = plasma_process
                        # Update metadata with new socket
                        cdi_metadata["plasma_socket"] = plasma_socket
                    except Exception as e:
                        result["error"] = f"Failed to start Plasma store: {str(e)}"
                        return result
                else:
                    result["error"] = f"Plasma socket not found at {plasma_socket}"
                    result["help"] = "Set start_plasma_if_needed=True to automatically start the Plasma store"
                    return result
                
            # Connect to plasma store
            try:
                plasma_client = plasma.connect(plasma_socket)
                result["plasma_socket"] = plasma_socket
            except Exception as e:
                result["error"] = f"Failed to connect to Plasma store at {plasma_socket}: {str(e)}"
                return result
            
            # Get object ID
            object_id_hex = cdi_metadata.get("object_id")
            if not object_id_hex:
                result["error"] = "Object ID not found in metadata"
                return result
                
            # Convert hex to binary object ID
            try:
                object_id = plasma.ObjectID(bytes.fromhex(object_id_hex))
            except ValueError as e:
                result["error"] = f"Invalid object ID format: {object_id_hex}, error: {str(e)}"
                return result
            
            # Wait for object if requested
            if wait_for_object and not plasma_client.contains(object_id):
                start_time = time.time()
                while not plasma_client.contains(object_id):
                    time.sleep(0.1)  # Check every 100ms
                    if time.time() - start_time > wait_timeout_sec:
                        result["error"] = f"Timeout waiting for object {object_id_hex}"
                        return result
                        
                # Record how long we waited
                result["wait_time_sec"] = time.time() - start_time
            
            # Check if object exists in plasma store
            if not plasma_client.contains(object_id):
                # Look for objects with similar ID prefixes
                all_objects = list(plasma_client.list().keys())
                similar_objects = [obj.binary().hex() for obj in all_objects 
                                  if obj.binary().hex().startswith(object_id_hex[:8])]
                
                if similar_objects:
                    result["error"] = f"Object {object_id_hex} not found in plasma store. Similar objects: {similar_objects}"
                    result["help"] = "Try with one of the similar object IDs or set wait_for_object=True"
                else:
                    result["error"] = f"Object {object_id_hex} not found in plasma store and no similar objects found"
                    result["available_objects"] = [obj.binary().hex() for obj in all_objects]
                    
                return result
                
            # Get the object from plasma store
            try:
                buffer = plasma_client.get_buffers([object_id])[object_id]
                reader = pa.RecordBatchStreamReader(buffer)
                table = reader.read_all()
            except Exception as e:
                result["error"] = f"Failed to read object from Plasma store: {str(e)}"
                return result
            
            # Convert to pandas if requested
            if return_pandas:
                try:
                    import pandas as pd
                    df = table.to_pandas()
                    result["dataframe"] = df
                    result["conversion"] = "arrow_to_pandas"
                except ImportError:
                    result["warning"] = "Could not convert to pandas: pandas not installed"
                except Exception as e:
                    result["warning"] = f"Error converting to pandas: {str(e)}"
            
            # Success!
            result["success"] = True
            result["table"] = table
            result["schema"] = table.schema
            result["num_rows"] = table.num_rows
            result["metadata"] = cdi_metadata
            result["object_id"] = object_id_hex
            result["access_method"] = "c_data_interface"
            result["plasma_client"] = plasma_client  # Return for cleanup
            
            return result
            
        except ImportError as e:
            result["error"] = f"Required module not available: {str(e)}"
            if "plasma" in str(e).lower():
                result["install_command"] = "pip install ipfs_kit_py[arrow]"
            elif "pyarrow" in str(e).lower():
                result["install_command"] = "pip install pyarrow"
            return result
        except Exception as e:
            result["error"] = f"Error accessing via C Data Interface: {str(e)}"
            import traceback
            result["traceback"] = traceback.format_exc()
            return result
    
    @staticmethod
    def _start_plasma_store_static(memory_limit_mb=1000, plasma_directory=None, use_hugepages=False):
        """Static version of _start_plasma_store to use without an instance.
        
        Args:
            memory_limit_mb: Memory limit for the plasma store in MB
            plasma_directory: Directory for plasma store files (default: /tmp)
            use_hugepages: Whether to use huge pages for better performance
            
        Returns:
            Tuple of (socket_path, plasma_process)
        """
        import subprocess
        import tempfile
        import pyarrow as pa
        import pyarrow.plasma as plasma
        import atexit
        import os
        
        # Create a unique socket path
        socket_fd, socket_path = tempfile.mkstemp(prefix="plasma_", suffix=".sock")
        os.close(socket_fd)
        os.unlink(socket_path)
        
        # Start the plasma store process
        cmd = [
            "plasma_store",
            "-m", str(memory_limit_mb * 1024 * 1024),  # Convert MB to bytes
            "-s", socket_path
        ]
        
        if plasma_directory:
            cmd.extend(["-d", plasma_directory])
            
        if use_hugepages:
            cmd.append("-h")
            
        plasma_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        
        # Register cleanup on exit
        def cleanup_plasma():
            if plasma_process.poll() is None:
                plasma_process.terminate()
                plasma_process.wait(timeout=5)
                
        atexit.register(cleanup_plasma)
        
        # Wait a moment for the store to start
        import time
        time.sleep(0.5)
        
        # Check if the process is still running
        if plasma_process.poll() is not None:
            stdout, stderr = plasma_process.communicate()
            raise RuntimeError(
                f"Plasma store failed to start: {stderr.decode('utf-8')}"
            )
            
        return socket_path, plasma_process
    
    @staticmethod
    def c_data_interface_example():
        """Example of using the C Data Interface for zero-copy access.
        
        This method provides example code for accessing the ParquetCIDCache
        from other processes or languages using the Arrow C Data Interface.
        """
        # Python example with enhanced options
        python_example = """
        # External process accessing the cache via C Data Interface
        from ipfs_kit_py.cache.schema_column_optimization import ParquetCIDCache
        
        # Basic access - requires plasma store already running
        result = ParquetCIDCache.access_via_c_data_interface("~/.ipfs_parquet_cache")
        
        # Advanced options
        result = ParquetCIDCache.access_via_c_data_interface(
            cache_dir="~/.ipfs_parquet_cache",
            name_suffix="metadata",                # Access a specific named export
            start_plasma_if_needed=True,           # Auto-start plasma if not found
            plasma_memory_mb=2000,                 # 2GB memory for plasma store
            wait_for_object=True,                  # Wait if object not immediately available
            wait_timeout_sec=30.0,                 # Wait up to 30 seconds
            return_pandas=True                     # Convert to pandas DataFrame
        )
        
        if result["success"]:
            if "dataframe" in result:
                # Access as pandas DataFrame
                df = result["dataframe"]
                print(f"Successfully accessed cache with {len(df)} records")
                
                # Perform pandas operations
                metadata_by_size = df.sort_values("size_bytes", ascending=False).head(10)
                print(f"Largest items: {metadata_by_size['cid'].tolist()}")
            else:
                # Access the Arrow table directly without copying
                table = result["table"]
                print(f"Successfully accessed cache with {table.num_rows} records")
                
                # Use the table for queries
                cids = table.column("cid").to_pylist()
                
            # Always clean up the plasma client when done
            if "plasma_client" in result:
                # This doesn't terminate the plasma store, just disconnects this client
                del result["plasma_client"]
        else:
            print(f"Error: {result['error']}")
            if "help" in result:
                print(f"Help: {result['help']}")
            if "install_command" in result:
                print(f"Try installing required packages: {result['install_command']}")
                
        # Access in a context manager pattern (recommended)
        def access_parquet_cache(cache_dir, **kwargs):
            """ + '"""Context manager for accessing ParquetCIDCache safely."""' + """
            result = None
            try:
                result = ParquetCIDCache.access_via_c_data_interface(cache_dir, **kwargs)
                yield result
            finally:
                # Clean up resources when done
                if result and result.get("success") and "plasma_client" in result:
                    del result["plasma_client"]
        
        # Usage with context manager
        with access_parquet_cache("~/.ipfs_parquet_cache", start_plasma_if_needed=True) as result:
            if result["success"]:
                table = result["table"]
                # Use the table safely, cleanup will happen automatically
                print(f"Processing {table.num_rows} records")
        """
        
        # C++ example using Arrow C++
        cpp_example = """
        // C++ example for accessing ParquetCIDCache via Arrow C Data Interface
        #include <arrow/api.h>
        #include <arrow/io/api.h>
        #include <arrow/ipc/api.h>
        #include <arrow/json/api.h>
        #include <arrow/plasma/client.h>
        #include <arrow/table.h>
        #include <arrow/filesystem/filesystem.h>
        
        #include <iostream>
        #include <string>
        #include <fstream>
        #include <memory>
        #include <chrono>
        #include <thread>
        
        // For JSON parsing
        #include <nlohmann/json.hpp>
        using json = nlohmann::json;
        
        using namespace arrow;
        
        // Helper class for accessing ParquetCIDCache from C++
        class ParquetCIDCacheAccess {
        public:
            // Constructor with enhanced options
            ParquetCIDCacheAccess(
                const std::string& cache_dir,
                const std::string& name_suffix = "",
                bool wait_for_object = false,
                double wait_timeout_sec = 10.0)
                : cache_dir_(cache_dir),
                  name_suffix_(name_suffix),
                  wait_for_object_(wait_for_object),
                  wait_timeout_sec_(wait_timeout_sec),
                  connected_(false),
                  success_(false) {
                  
                // Construct metadata path
                std::string metadata_path;
                if (!name_suffix.empty()) {
                    metadata_path = cache_dir + "/c_data_interface_" + name_suffix + ".json";
                    // Check if file exists, if not use default
                    if (!FileExists(metadata_path)) {
                        metadata_path = cache_dir + "/c_data_interface.json";
                    }
                } else {
                    metadata_path = cache_dir + "/c_data_interface.json";
                }
                
                // Load metadata
                if (!LoadMetadata(metadata_path)) {
                    std::cerr << "Failed to load metadata from " << metadata_path << std::endl;
                    return;
                }
                
                // Connect to plasma store
                if (!ConnectToPlasmaStore()) {
                    std::cerr << "Failed to connect to plasma store at " 
                              << plasma_socket_ << std::endl;
                    return;
                }
                
                // Get the object
                if (!GetObject()) {
                    std::cerr << "Failed to get object " << object_id_hex_ << std::endl;
                    return;
                }
                
                success_ = true;
            }
            
            ~ParquetCIDCacheAccess() {
                // Clean up resources
                if (connected_) {
                    client_->Disconnect();
                }
            }
            
            // Check if successfully connected and loaded
            bool success() const { return success_; }
            
            // Get the loaded table
            std::shared_ptr<Table> table() const { return table_; }
            
            // Get error message if any
            const std::string& error() const { return error_; }
            
        private:
            std::string cache_dir_;
            std::string name_suffix_;
            bool wait_for_object_;
            double wait_timeout_sec_;
            bool connected_;
            bool success_;
            std::string error_;
            
            std::string plasma_socket_;
            std::string object_id_hex_;
            std::shared_ptr<plasma::PlasmaClient> client_;
            std::shared_ptr<Table> table_;
            
            // Check if file exists
            bool FileExists(const std::string& path) {
                std::ifstream f(path);
                return f.good();
            }
            
            // Load metadata from JSON file
            bool LoadMetadata(const std::string& path) {
                try {
                    std::ifstream file(path);
                    if (!file.is_open()) {
                        error_ = "Failed to open metadata file: " + path;
                        return false;
                    }
                    
                    json metadata = json::parse(file);
                    plasma_socket_ = metadata["plasma_socket"];
                    object_id_hex_ = metadata["object_id"];
                    
                    return true;
                } catch (const std::exception& e) {
                    error_ = std::string("Error parsing metadata: ") + e.what();
                    return false;
                }
            }
            
            // Connect to the plasma store
            bool ConnectToPlasmaStore() {
                try {
                    client_ = std::make_shared<plasma::PlasmaClient>();
                    auto status = client_->Connect(plasma_socket_);
                    if (!status.ok()) {
                        error_ = "Failed to connect to plasma store: " + status.ToString();
                        return false;
                    }
                    
                    connected_ = true;
                    return true;
                } catch (const std::exception& e) {
                    error_ = std::string("Error connecting to plasma store: ") + e.what();
                    return false;
                }
            }
            
            // Get object from plasma store
            bool GetObject() {
                try {
                    // Convert hex to binary object ID
                    plasma::ObjectID object_id = plasma::ObjectID::from_binary(
                        plasma::hex_to_binary(object_id_hex_));
                    
                    // Wait for object if requested
                    if (wait_for_object_) {
                        auto start_time = std::chrono::steady_clock::now();
                        bool contains = false;
                        
                        while (!contains) {
                            auto status = client_->Contains(object_id, &contains);
                            if (!status.ok()) {
                                error_ = "Error checking if plasma store contains object: " + 
                                         status.ToString();
                                return false;
                            }
                            
                            if (contains) break;
                            
                            // Check timeout
                            auto current_time = std::chrono::steady_clock::now();
                            double elapsed_sec = std::chrono::duration<double>(
                                current_time - start_time).count();
                                
                            if (elapsed_sec > wait_timeout_sec_) {
                                error_ = "Timeout waiting for object " + object_id_hex_;
                                return false;
                            }
                            
                            // Sleep a bit before checking again
                            std::this_thread::sleep_for(std::chrono::milliseconds(100));
                        }
                    }
                    
                    // Check if object exists
                    bool contains = false;
                    auto status = client_->Contains(object_id, &contains);
                    if (!status.ok()) {
                        error_ = "Error checking if plasma store contains object: " + 
                                 status.ToString();
                        return false;
                    }
                    
                    if (!contains) {
                        error_ = "Object not found in plasma store: " + object_id_hex_;
                        return false;
                    }
                    
                    // Get the object from plasma store
                    std::shared_ptr<Buffer> buffer;
                    status = client_->Get(&object_id, 1, -1, &buffer);
                    if (!status.ok()) {
                        error_ = "Failed to get object from plasma store: " + status.ToString();
                        return false;
                    }
                    
                    // Read the record batch
                    auto buffer_reader = std::make_shared<io::BufferReader>(buffer);
                    auto result = ipc::RecordBatchStreamReader::Open(buffer_reader);
                    if (!result.ok()) {
                        error_ = "Failed to open record batch reader: " + 
                                 result.status().ToString();
                        return false;
                    }
                    
                    auto reader = result.ValueOrDie();
                    result = reader->ReadAll(&table_);
                    if (!result.ok()) {
                        error_ = "Failed to read table: " + result.status().ToString();
                        return false;
                    }
                    
                    return true;
                } catch (const std::exception& e) {
                    error_ = std::string("Error getting object: ") + e.what();
                    return false;
                }
            }
        };
        
        // Example program to access ParquetCIDCache from C++
        int main() {
            // Configuration
            std::string cache_dir = "/home/user/.ipfs_parquet_cache";
            std::string name_suffix = "metadata";
            bool wait_for_object = true;
            double wait_timeout_sec = 10.0;
            
            // Access cache
            ParquetCIDCacheAccess cache_access(
                cache_dir, name_suffix, wait_for_object, wait_timeout_sec);
                
            if (!cache_access.success()) {
                std::cerr << "Failed to access cache: " << cache_access.error() << std::endl;
                return 1;
            }
            
            // Successfully accessed the cache, now use the table
            auto table = cache_access.table();
            std::cout << "Successfully accessed cache with " << table->num_rows() 
                      << " rows and " << table->num_columns() << " columns" << std::endl;
                      
            // Get the CID column (assuming it exists)
            auto cid_array = std::static_pointer_cast<StringArray>(table->GetColumnByName("cid"));
            if (!cid_array) {
                std::cerr << "CID column not found in table" << std::endl;
                return 1;
            }
            
            // Print the first few CIDs
            int num_to_print = std::min(10, static_cast<int>(cid_array->length()));
            std::cout << "First " << num_to_print << " CIDs:" << std::endl;
            for (int i = 0; i < num_to_print; i++) {
                std::cout << i << ": " << cid_array->GetString(i) << std::endl;
            }
            
            // Example: find the largest items (assuming size_bytes column exists)
            auto size_array = std::static_pointer_cast<Int64Array>(
                table->GetColumnByName("size_bytes"));
                
            if (size_array) {
                // Print the 5 largest items
                std::cout << "\\nLargest items:" << std::endl;
                
                // This is a simplified approach; in a real application, you'd use
                // Arrow compute functions to sort and slice efficiently
                std::vector<std::pair<int64_t, std::string>> items;
                for (int i = 0; i < std::min(100, static_cast<int>(table->num_rows())); i++) {
                    items.push_back({size_array->Value(i), cid_array->GetString(i)});
                }
                
                // Sort by size (descending)
                std::sort(items.begin(), items.end(), 
                         [](const auto& a, const auto& b) { return a.first > b.first; });
                
                // Print top 5
                for (int i = 0; i < std::min(5, static_cast<int>(items.size())); i++) {
                    std::cout << i + 1 << ": " << items[i].second << " (" 
                              << items[i].first << " bytes)" << std::endl;
                }
            }
            
            return 0;
        }
        """
        
        # Rust example using Arrow Rust
        rust_example = """
        // Rust example for accessing ParquetCIDCache via Arrow C Data Interface
        use std::fs::File;
        use std::path::{Path, PathBuf};
        use std::time::{Duration, Instant};
        use std::thread::sleep;
        
        use arrow::array::{StringArray, Int64Array, StructArray, Array};
        use arrow::datatypes::Schema;
        use arrow::record_batch::RecordBatch;
        use arrow::ipc::reader::StreamReader;
        use serde_json::Value;
        
        // Optional, if available in your environment:
        // use plasma::PlasmaClient;
        
        // Helper struct for accessing ParquetCIDCache from Rust
        struct ParquetCIDCacheAccess {
            table: Option<RecordBatch>,
            schema: Option<Schema>,
            error: Option<String>,
            plasma_socket: Option<String>,
            object_id_hex: Option<String>,
        }
        
        impl ParquetCIDCacheAccess {
            // Create a new instance with options
            pub fn new(
                cache_dir: &str,
                name_suffix: Option<&str>,
                wait_for_object: bool,
                wait_timeout_sec: f64,
            ) -> Self {
                let mut result = ParquetCIDCacheAccess {
                    table: None,
                    schema: None,
                    error: None,
                    plasma_socket: None,
                    object_id_hex: None,
                };
                
                // Determine metadata path
                let mut metadata_path = PathBuf::from(cache_dir);
                if let Some(suffix) = name_suffix {
                    metadata_path.push(format!("c_data_interface_{}.json", suffix));
                    
                    // Check if file exists, if not use default
                    if !metadata_path.exists() {
                        metadata_path = PathBuf::from(cache_dir).join("c_data_interface.json");
                    }
                } else {
                    metadata_path.push("c_data_interface.json");
                }
                
                // Load metadata
                let metadata = match Self::load_metadata(&metadata_path) {
                    Ok(m) => m,
                    Err(e) => {
                        result.error = Some(format!("Failed to load metadata: {}", e));
                        return result;
                    }
                };
                
                // Extract plasma socket and object ID
                result.plasma_socket = match metadata["plasma_socket"].as_str() {
                    Some(s) => Some(s.to_string()),
                    None => {
                        result.error = Some("Plasma socket not found in metadata".to_string());
                        return result;
                    }
                };
                
                result.object_id_hex = match metadata["object_id"].as_str() {
                    Some(s) => Some(s.to_string()),
                    None => {
                        result.error = Some("Object ID not found in metadata".to_string());
                        return result;
                    }
                };
                
                // Access plasma store and load table
                // Note: For a complete implementation, you would use the plasma crate
                // For this example, we'll simulate with a file-based approach for simplicity
                
                // In a real implementation, you would:
                // 1. Connect to the plasma store
                // 2. Get the object
                // 3. Read the table
                
                // For this example, we simulate by reading from a parquet file
                // This is NOT zero-copy, but demonstrates the interface
                // Assume there's a corresponding parquet file next to the metadata
                let parquet_path = metadata_path.with_extension("parquet");
                if parquet_path.exists() {
                    match arrow::parquet::arrow::reader::ParquetFileArrowReader::try_new(
                        File::open(parquet_path).unwrap()
                    ) {
                        Ok(mut reader) => {
                            match reader.get_record_reader_by_index(0) {
                                Ok(mut batch_reader) => {
                                    match batch_reader.next() {
                                        Some(Ok(batch)) => {
                                            result.schema = Some(batch.schema());
                                            result.table = Some(batch);
                                        },
                                        _ => {
                                            result.error = Some("Failed to read record batch".to_string());
                                        }
                                    }
                                },
                                Err(e) => {
                                    result.error = Some(format!("Failed to get record reader: {}", e));
                                }
                            }
                        },
                        Err(e) => {
                            result.error = Some(format!("Failed to open parquet file: {}", e));
                        }
                    }
                } else {
                    // Implement actual plasma access in a real application
                    result.error = Some(format!(
                        "This example requires Arrow Plasma integration. \\
                         For a complete implementation, use the plasma crate."
                    ));
                }
                
                result
            }
            
            // Check if successfully loaded
            pub fn success(&self) -> bool {
                self.table.is_some()
            }
            
            // Get error message if any
            pub fn error(&self) -> Option<&str> {
                self.error.as_deref()
            }
            
            // Helper function to load metadata
            fn load_metadata(path: &Path) -> Result<Value, String> {
                let file = File::open(path)
                    .map_err(|e| format!("Failed to open metadata file: {}", e))?;
                    
                serde_json::from_reader(file)
                    .map_err(|e| format!("Failed to parse metadata: {}", e))
            }
        }
        
        // Example usage
        fn main() -> Result<(), Box<dyn std::error::Error>> {
            // Configuration
            let cache_dir = "/home/user/.ipfs_parquet_cache";
            let name_suffix = Some("metadata");
            let wait_for_object = true;
            let wait_timeout_sec = 10.0;
            
            // Access cache
            let cache_access = ParquetCIDCacheAccess::new(
                cache_dir, 
                name_suffix,
                wait_for_object,
                wait_timeout_sec
            );
            
            if !cache_access.success() {
                eprintln!("Failed to access cache: {}", 
                         cache_access.error().unwrap_or("Unknown error"));
                return Ok(());
            }
            
            // Successfully accessed the cache, now use the table
            let table = cache_access.table.unwrap();
            println!("Successfully accessed cache with {} rows and {} columns", 
                    table.num_rows(), table.num_columns());
                    
            // Get the CID column (assuming it exists)
            let cid_column = table.column_by_name("cid")
                .ok_or("CID column not found")?;
                
            let cid_array = cid_column.as_any()
                .downcast_ref::<StringArray>()
                .ok_or("CID column is not a string array")?;
                
            // Print the first few CIDs
            let num_to_print = std::cmp::min(10, cid_array.len());
            println!("First {} CIDs:", num_to_print);
            for i in 0..num_to_print {
                println!("{}: {}", i, cid_array.value(i));
            }
            
            // Example: find the largest items (assuming size_bytes column exists)
            if let Some(size_column) = table.column_by_name("size_bytes") {
                if let Some(size_array) = size_column.as_any().downcast_ref::<Int64Array>() {
                    // Print the 5 largest items
                    println!("\\nLargest items:");
                    
                    // This is a simplified approach
                    let mut items: Vec<(i64, &str)> = (0..std::cmp::min(100, table.num_rows()))
                        .map(|i| (size_array.value(i), cid_array.value(i)))
                        .collect();
                        
                    // Sort by size (descending)
                    items.sort_by(|a, b| b.0.cmp(&a.0));
                    
                    // Print top 5
                    for (i, (size, cid)) in items.iter().take(5).enumerate() {
                        println!("{}: {} ({} bytes)", i + 1, cid, size);
                    }
                }
            }
            
            Ok(())
        }
        """
        
        # JavaScript/TypeScript example
        typescript_example = """
        // TypeScript example for accessing ParquetCIDCache via Arrow JS
        // Note: This requires Arrow.js and appropriate Node.js bindings
        
        import * as fs from 'fs';
        import * as path from 'path';
        // You would need to install Apache Arrow for JS:
        // npm install apache-arrow
        import { Table, Schema, RecordBatchStreamReader } from 'apache-arrow';
        
        // Helper class for accessing ParquetCIDCache
        class ParquetCIDCacheAccess {
          private table?: Table;
          private schema?: Schema;
          private error?: string;
          private plasma_socket?: string;
          private object_id_hex?: string;
          
          constructor(
            private cachePath: string,
            private nameSuffix?: string,
            private waitForObject = false,
            private waitTimeoutSec = 10.0
          ) {
            this.init();
          }
          
          private init(): void {
            try {
              // Determine metadata file path
              let metadataPath: string;
              if (this.nameSuffix) {
                metadataPath = path.join(
                  this.cachePath, 
                  `c_data_interface_${this.nameSuffix}.json`
                );
                
                // Check if file exists, if not use default
                if (!fs.existsSync(metadataPath)) {
                  metadataPath = path.join(this.cachePath, 'c_data_interface.json');
                }
              } else {
                metadataPath = path.join(this.cachePath, 'c_data_interface.json');
              }
              
              // Check if metadata file exists
              if (!fs.existsSync(metadataPath)) {
                this.error = `Metadata file not found: ${metadataPath}`;
                return;
              }
              
              // Load metadata
              const metadata = JSON.parse(fs.readFileSync(metadataPath, 'utf-8'));
              this.plasma_socket = metadata.plasma_socket;
              this.object_id_hex = metadata.object_id;
              
              // In a full implementation, you would connect to the plasma store
              // and retrieve the data using Arrow IPC
              // This is not fully implementable in pure JavaScript without additional bindings
              
              // Instead, we'll demonstrate how you would normally access an Arrow table
              // Assuming there's a corresponding Arrow file or Parquet file
              const arrowFilePath = path.join(
                this.cachePath, 
                `${this.nameSuffix || 'default'}.arrow`
              );
              
              if (fs.existsSync(arrowFilePath)) {
                // Read the Arrow file
                const buffer = fs.readFileSync(arrowFilePath);
                this.table = Table.from(new Uint8Array(buffer));
                this.schema = this.table.schema;
              } else {
                this.error = 'Full implementation requires native Arrow plasma bindings';
              }
            } catch (err) {
              this.error = `Error accessing cache: ${err.message}`;
            }
          }
          
          // Check if successfully loaded
          public success(): boolean {
            return !!this.table;
          }
          
          // Get the table
          public getTable(): Table | undefined {
            return this.table;
          }
          
          // Get error message if any
          public getError(): string | undefined {
            return this.error;
          }
        }
        
        // Example usage
        async function main() {
          // Configuration
          const cacheDir = '/home/user/.ipfs_parquet_cache';
          const nameSuffix = 'metadata';
          const waitForObject = true;
          const waitTimeoutSec = 10.0;
          
          // Access cache
          const cacheAccess = new ParquetCIDCacheAccess(
            cacheDir,
            nameSuffix,
            waitForObject,
            waitTimeoutSec
          );
          
          if (!cacheAccess.success()) {
            console.error(`Failed to access cache: ${cacheAccess.getError()}`);
            return;
          }
          
          // Successfully accessed the cache, now use the table
          const table = cacheAccess.getTable()!;
          console.log(`Successfully accessed cache with ${table.count()} rows and ${table.numCols} columns`);
          
          // Get the CID column (assuming it exists)
          const cidColumn = table.getChild('cid');
          if (!cidColumn) {
            console.error('CID column not found');
            return;
          }
          
          // Print the first few CIDs
          const numToPrint = Math.min(10, table.count());
          console.log(`First ${numToPrint} CIDs:`);
          for (let i = 0; i < numToPrint; i++) {
            console.log(`${i}: ${cidColumn.get(i)}`);
          }
          
          // Example: find the largest items (assuming size_bytes column exists)
          const sizeColumn = table.getChild('size_bytes');
          if (sizeColumn) {
            // Print the 5 largest items
            console.log('\\nLargest items:');
            
            // This is a simplified approach
            const items = [];
            for (let i = 0; i < Math.min(100, table.count()); i++) {
              items.push({
                size: sizeColumn.get(i),
                cid: cidColumn.get(i)
              });
            }
            
            // Sort by size (descending)
            items.sort((a, b) => b.size - a.size);
            
            // Print top 5
            items.slice(0, 5).forEach((item, i) => {
              console.log(`${i + 1}: ${item.cid} (${item.size} bytes)`);
            });
          }
        }
        
        main().catch(console.error);
        """
            
        # C++ Example
        cpp_example = """
        #include <arrow/api.h>
        #include <arrow/io/api.h>
        #include <arrow/ipc/api.h>
        #include <arrow/util/logging.h>
        #include <plasma/client.h>
        
        #include <iostream>
        #include <fstream>
        #include <string>
        #include <nlohmann/json.hpp>
        
        using json = nlohmann::json;
        
        int main() {
            // Read the C Data Interface metadata
            std::string metadata_path = "/home/user/.ipfs_parquet_cache/c_data_interface.json";
            std::ifstream f(metadata_path);
            
            if (!f.is_open()) {
                std::cerr << "Failed to open metadata file" << std::endl;
                return 1;
            }
            
            // Parse JSON metadata
            json metadata = json::parse(f);
            std::string plasma_socket = metadata["plasma_socket"];
            std::string object_id_hex = metadata["object_id"];
            
            // Connect to Plasma store
            std::shared_ptr<plasma::PlasmaClient> client;
            plasma::Connect(plasma_socket, "", 0, &client);
            
            // Create ObjectID from hex string
            plasma::ObjectID object_id = plasma::ObjectID::from_binary(
                plasma::hex_to_binary(object_id_hex));
            
            // Retrieve the object from Plasma store
            std::shared_ptr<arrow::Buffer> buffer;
            client->Get(&object_id, 1, -1, &buffer);
            
            // Read the Arrow table
            auto reader = std::make_shared<arrow::io::BufferReader>(buffer);
            auto batch_reader = arrow::ipc::RecordBatchStreamReader::Open(reader).ValueOrDie();
            std::shared_ptr<arrow::Table> table;
            batch_reader->ReadAll(&table);
            
            // Now we can access the table data without copying
            std::cout << "Table has " << table->num_rows() << " rows" << std::endl;
            
            // Access CIDs column if it exists
            int cid_idx = table->schema()->GetFieldIndex("cid");
            if (cid_idx >= 0) {
                auto cid_array = std::static_pointer_cast<arrow::StringArray>(table->column(cid_idx));
                for (int i = 0; i < std::min(5, (int)table->num_rows()); i++) {
                    std::cout << "CID " << i << ": " << cid_array->GetString(i) << std::endl;
                }
            }
            
            // Clean up
            client->Disconnect();
            
            return 0;
        }
        """
        
        # Rust Example
        rust_example = """
        use std::fs::File;
        use arrow::array::StringArray;
        use arrow::datatypes::Schema;
        use arrow::record_batch::RecordBatch;
        
        fn main() -> Result<(), Box<dyn std::error::Error>> {
            // Read metadata file
            let metadata_path = "/home/user/.ipfs_parquet_cache/c_data_interface.json";
            let file = File::open(metadata_path)?;
            let metadata: serde_json::Value = serde_json::from_reader(file)?;
            
            // Get plasma store socket and object ID
            let plasma_socket = metadata["plasma_socket"].as_str().unwrap();
            let object_id_hex = metadata["object_id"].as_str().unwrap();
            
            // Connect to plasma store
            let mut client = plasma::PlasmaClient::connect(plasma_socket)?;
            
            // Convert hex to binary object ID
            let object_id = hex::decode(object_id_hex)?;
            
            // Get the object
            let buffer = client.get(&object_id, -1)?;
            
            // Read as Arrow record batch
            let reader = arrow::ipc::reader::StreamReader::try_new(&buffer[..])?;
            let schema = reader.schema();
            println!("Schema: {:?}", schema);
            
            // Read first batch
            if let Some(batch) = reader.next() {
                let batch = batch?;
                println!("Batch has {} rows", batch.num_rows());
                
                // Access CID column if available
                if let Some(cid_idx) = schema.fields()
                    .iter()
                    .position(|f| f.name() == "cid")
                {
                    let cid_array = batch
                        .column(cid_idx)
                        .as_any()
                        .downcast_ref::<StringArray>()
                        .unwrap();
                        
                    for i in 0..std::cmp::min(5, batch.num_rows()) {
                        println!("CID {}: {}", i, cid_array.value(i));
                    }
                }
            }
            
            // Disconnect
            client.disconnect()?;
            
            Ok(())
        }
        """
        
        return {
            "python_example": python_example,
            "cpp_example": cpp_example,
            "rust_example": rust_example,
            "note": "These examples demonstrate zero-copy access to the cache data across languages."
        }

