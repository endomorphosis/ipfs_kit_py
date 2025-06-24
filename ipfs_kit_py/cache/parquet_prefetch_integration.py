"""
Integration of read-ahead prefetching with ParquetCIDCache.

This module provides integration between the ParquetCIDCache and
the read-ahead prefetching system, enabling efficient prefetching
of content based on access patterns.
"""

import os
import time
import logging
import threading
from typing import Dict, List, Set, Tuple, Optional, Any, Union, Callable

from .read_ahead_prefetching import (
    ReadAheadPrefetchManager,
    SequentialPrefetchStrategy,
    TemporalPrefetchStrategy,
    HybridPrefetchStrategy,
    ContentAwarePrefetchStrategy
)

logger = logging.getLogger(__name__)

class PrefetchingParquetCIDCache:
    """ParquetCIDCache with integrated read-ahead prefetching capabilities."""

    def __init__(self,
                base_cache,  # The base ParquetCIDCache instance
                prefetch_strategy: str = "hybrid",
                max_prefetch_workers: int = 2,
                max_prefetch_queue: int = 20,
                max_memory_usage: int = 1024 * 1024 * 100,  # 100MB
                prefetch_threshold: float = 0.3,
                enable_content_aware: bool = False,
                content_relationship_fn: Optional[Callable] = None):
        """Initialize the prefetching cache wrapper.

        Args:
            base_cache: The base ParquetCIDCache instance to wrap
            prefetch_strategy: Strategy to use ("sequential", "temporal", "hybrid")
            max_prefetch_workers: Maximum number of prefetch worker threads
            max_prefetch_queue: Maximum size of prefetch queue
            max_memory_usage: Maximum memory for prefetched content
            prefetch_threshold: Minimum score threshold for prefetching (0.0-1.0)
            enable_content_aware: Whether to enable content-aware prefetching
            content_relationship_fn: Function that returns related content given a CID
        """
        self.base_cache = base_cache
        self.prefetch_threshold = prefetch_threshold
        self.enable_content_aware = enable_content_aware

        # Create prefetch manager
        self.prefetch_manager = ReadAheadPrefetchManager(
            fetch_fn=self._fetch_content,
            max_prefetch_workers=max_prefetch_workers,
            max_prefetch_queue=max_prefetch_queue,
            max_memory_usage=max_memory_usage,
            enable_metrics=True,
            prefetch_threshold=prefetch_threshold
        )

        # Add content-aware strategy if enabled and function provided
        if enable_content_aware and content_relationship_fn:
            content_strategy = ContentAwarePrefetchStrategy(content_relationship_fn)
            self.prefetch_manager.add_custom_strategy("content_aware", content_strategy)

            # Create new hybrid strategy that includes content awareness
            hybrid_strategy = HybridPrefetchStrategy({
                SequentialPrefetchStrategy(): 0.4,
                TemporalPrefetchStrategy(): 0.3,
                content_strategy: 0.3
            })
            self.prefetch_manager.add_custom_strategy("hybrid_content", hybrid_strategy)
            prefetch_strategy = "hybrid_content"

        # Set the active strategy
        self.prefetch_manager.set_strategy(prefetch_strategy)

        # Statistics
        self.stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "prefetch_hits": 0,
            "total_gets": 0,
            "prefetched_gets": 0
        }
        self._lock = threading.RLock()

    def _fetch_content(self, cid: str) -> Any:
        """Fetch content from the base cache for prefetching.

        This is used by the prefetch manager to load content
        in background threads.

        Args:
            cid: Content identifier to fetch

        Returns:
            The content data from the base cache
        """
        try:
            # Use the base cache to get the content, bypassing prefetch recording
            result = self.base_cache.get(cid)

            # Check if the get was successful
            if isinstance(result, dict) and result.get("success", False):
                return result.get("data")
            return result
        except Exception as e:
            logger.warning(f"Error prefetching content {cid}: {e}")
            return None

    def get(self, cid: str, **kwargs) -> Dict[str, Any]:
        """Get content from the cache with prefetching support.

        Args:
            cid: Content identifier to get
            **kwargs: Additional arguments to pass to the base cache

        Returns:
            Dictionary with operation result and data if successful
        """
        with self._lock:
            self.stats["total_gets"] += 1

            # Check if this was prefetched
            was_prefetched = self.prefetch_manager.check_prefetched(cid)
            if was_prefetched:
                self.stats["prefetched_gets"] += 1

        # Get from base cache
        result = self.base_cache.get(cid, **kwargs)

        # Update cache hit/miss stats
        with self._lock:
            if result.get("success", False):
                if "cache_hit" in result and result["cache_hit"]:
                    self.stats["cache_hits"] += 1
                else:
                    self.stats["cache_misses"] += 1

                # Update prefetch hit stats
                if was_prefetched:
                    self.stats["prefetch_hits"] += 1
                    # Add prefetch hit info to result
                    result["prefetch_hit"] = True

        # Record the access to update patterns (must happen after get to avoid recursion)
        # Pass context with information about this access
        context = {
            "timestamp": time.time(),
            "cache_hit": result.get("cache_hit", False),
            "kwargs": kwargs
        }
        self.prefetch_manager.record_access(cid, context)

        return result

    def put(self, cid: str, data: Any, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Put content into the cache.

        Args:
            cid: Content identifier
            data: Content data to store
            metadata: Optional metadata about the content
            **kwargs: Additional arguments to pass to the base cache

        Returns:
            Dictionary with operation result
        """
        # Add to base cache
        result = self.base_cache.put(cid, data, metadata, **kwargs)

        # No need to record this for prefetching since it's not a get operation

        return result

    def invalidate(self, cid: str, **kwargs) -> Dict[str, Any]:
        """Invalidate content in the cache.

        Args:
            cid: Content identifier to invalidate
            **kwargs: Additional arguments to pass to the base cache

        Returns:
            Dictionary with operation result
        """
        # Invalidate in base cache
        result = self.base_cache.invalidate(cid, **kwargs)

        # No prefetching-specific handling needed for invalidation

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the prefetching cache.

        Returns:
            Dictionary with cache and prefetching statistics
        """
        with self._lock:
            # Get prefetch manager metrics
            prefetch_metrics = self.prefetch_manager.get_metrics()

            # Calculate hit rates
            total_gets = self.stats["total_gets"]
            prefetched_gets = self.stats["prefetched_gets"]

            cache_hit_rate = (self.stats["cache_hits"] / total_gets) if total_gets > 0 else 0
            prefetch_hit_rate = (self.stats["prefetch_hits"] / prefetched_gets) if prefetched_gets > 0 else 0
            prefetch_contribution_rate = (self.stats["prefetch_hits"] / total_gets) if total_gets > 0 else 0

            # Combine stats
            combined_stats = {
                "cache_stats": {
                    "gets": total_gets,
                    "hits": self.stats["cache_hits"],
                    "misses": self.stats["cache_misses"],
                    "hit_rate": cache_hit_rate
                },
                "prefetch_stats": {
                    "prefetched_gets": prefetched_gets,
                    "prefetch_hits": self.stats["prefetch_hits"],
                    "prefetch_hit_rate": prefetch_hit_rate,
                    "prefetch_contribution_rate": prefetch_contribution_rate,
                    "current_strategy": self.prefetch_manager.current_strategy
                },
                "prefetch_metrics": prefetch_metrics
            }

            # Try to get base cache stats if method exists
            if hasattr(self.base_cache, "get_stats"):
                try:
                    base_stats = self.base_cache.get_stats()
                    combined_stats["base_cache_stats"] = base_stats
                except:
                    pass

            return combined_stats

    def set_prefetch_strategy(self, strategy_name: str) -> bool:
        """Change the active prefetch strategy.

        Args:
            strategy_name: Name of the strategy to use

        Returns:
            True if strategy was set, False if not found
        """
        return self.prefetch_manager.set_strategy(strategy_name)

    def add_custom_prefetch_strategy(self, name: str, strategy) -> None:
        """Add a custom prefetch strategy.

        Args:
            name: Name to identify the strategy
            strategy: The strategy instance
        """
        self.prefetch_manager.add_custom_strategy(name, strategy)

    def shutdown(self) -> None:
        """Shutdown the prefetch manager."""
        if hasattr(self, 'prefetch_manager'):
            self.prefetch_manager.shutdown()

    def __del__(self):
        """Cleanup when instance is garbage collected."""
        self.shutdown()

    # Delegate all other methods to the base cache
    def __getattr__(self, name):
        """Delegate method calls to the base cache."""
        return getattr(self.base_cache, name)


class ParquetCIDCacheFactory:
    """Factory for creating ParquetCIDCache instances with read-ahead prefetching."""

    @staticmethod
    def create_with_prefetching(
            base_cache_cls,
            prefetch_strategy: str = "hybrid",
            max_prefetch_workers: int = 2,
            max_prefetch_queue: int = 20,
            max_memory_usage: int = 1024 * 1024 * 100,
            content_relationship_fn: Optional[Callable] = None,
            **base_cache_args) -> PrefetchingParquetCIDCache:
        """Create a new ParquetCIDCache with prefetching capabilities.

        Args:
            base_cache_cls: The base ParquetCIDCache class to instantiate
            prefetch_strategy: Strategy to use ("sequential", "temporal", "hybrid")
            max_prefetch_workers: Maximum number of prefetch worker threads
            max_prefetch_queue: Maximum size of prefetch queue
            max_memory_usage: Maximum memory for prefetched content
            content_relationship_fn: Function for content-aware prefetching
            **base_cache_args: Arguments to pass to the base cache constructor

        Returns:
            A PrefetchingParquetCIDCache instance
        """
        # Create the base cache
        base_cache = base_cache_cls(**base_cache_args)

        # Create and return the prefetching wrapper
        return PrefetchingParquetCIDCache(
            base_cache=base_cache,
            prefetch_strategy=prefetch_strategy,
            max_prefetch_workers=max_prefetch_workers,
            max_prefetch_queue=max_prefetch_queue,
            max_memory_usage=max_memory_usage,
            enable_content_aware=content_relationship_fn is not None,
            content_relationship_fn=content_relationship_fn
        )
