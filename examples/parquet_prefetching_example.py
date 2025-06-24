#!/usr/bin/env python3
"""
Example demonstrating ParquetCIDCache with read-ahead prefetching.

This example shows how to use the PrefetchingParquetCIDCache to improve
performance by integrating the read-ahead prefetching system with
a ParquetCIDCache.
"""

import os
import time
import random
import uuid
import tempfile
import logging
import threading
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Set, Tuple, Optional, Any, Callable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create a logger for this example
logger = logging.getLogger("parquet_prefetch_example")

# Import the ipfs_kit_py package
try:
    from ipfs_kit_py.cache.parquet_prefetch_integration import PrefetchingParquetCIDCache, ParquetCIDCacheFactory
except ImportError:
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from ipfs_kit_py.cache.parquet_prefetch_integration import PrefetchingParquetCIDCache, ParquetCIDCacheFactory

# Create a simple mock for ParquetCIDCache
class MockParquetCIDCache:
    """Mock implementation of ParquetCIDCache for demonstration purposes."""

    def __init__(self, base_path=None, max_size=1024*1024*100,
                 enable_metrics=True, cache_latency=0.05):
        """Initialize the mock cache.

        Args:
            base_path: Base path for cache storage
            max_size: Maximum cache size in bytes
            enable_metrics: Whether to enable metrics collection
            cache_latency: Simulated cache latency in seconds for misses
        """
        self.content = {}
        self.metadata = {}
        self.base_path = base_path or tempfile.mkdtemp()
        self.max_size = max_size
        self.enable_metrics = enable_metrics
        self.cache_latency = cache_latency

        # Statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "puts": 0,
            "invalidations": 0
        }
        self._lock = threading.RLock()

        logger.info(f"Initialized mock ParquetCIDCache at {self.base_path}")

    def get(self, cid: str, **kwargs) -> Dict[str, Any]:
        """Get content from the cache.

        Args:
            cid: Content identifier

        Returns:
            Dictionary with operation result and data if successful
        """
        result = {
            "success": False,
            "operation": "get",
            "timestamp": time.time(),
            "cache_hit": False
        }

        with self._lock:
            if cid in self.content:
                # Cache hit
                result["success"] = True
                result["data"] = self.content[cid]
                result["cache_hit"] = True
                self.stats["hits"] += 1
            else:
                # Cache miss - simulate fetch latency
                time.sleep(self.cache_latency)

                # Since this is a mock, we'll generate some content
                data = f"Generated content for {cid}: {uuid.uuid4().hex}".encode()
                self.content[cid] = data

                result["success"] = True
                result["data"] = data
                result["cache_hit"] = False
                self.stats["misses"] += 1

        return result

    def put(self, cid: str, data: Any, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Put content into the cache.

        Args:
            cid: Content identifier
            data: Content data
            metadata: Optional metadata

        Returns:
            Dictionary with operation result
        """
        result = {
            "success": False,
            "operation": "put",
            "timestamp": time.time()
        }

        with self._lock:
            self.content[cid] = data
            if metadata:
                self.metadata[cid] = metadata
            self.stats["puts"] += 1
            result["success"] = True

        return result

    def invalidate(self, cid: str, **kwargs) -> Dict[str, Any]:
        """Invalidate content in the cache.

        Args:
            cid: Content identifier

        Returns:
            Dictionary with operation result
        """
        result = {
            "success": False,
            "operation": "invalidate",
            "timestamp": time.time()
        }

        with self._lock:
            if cid in self.content:
                del self.content[cid]
                if cid in self.metadata:
                    del self.metadata[cid]
                self.stats["invalidations"] += 1
                result["success"] = True
            else:
                result["success"] = True
                result["message"] = "CID not in cache"

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            total = self.stats["hits"] + self.stats["misses"]
            hit_rate = self.stats["hits"] / total if total > 0 else 0

            return {
                "hits": self.stats["hits"],
                "misses": self.stats["misses"],
                "puts": self.stats["puts"],
                "invalidations": self.stats["invalidations"],
                "hit_rate": hit_rate,
                "content_count": len(self.content),
                "size_estimate": sum(len(data) for data in self.content.values())
            }

# Create content relationships for content-aware prefetching
class ContentGraph:
    """Graph of content relationships for content-aware prefetching."""

    def __init__(self):
        """Initialize the content graph."""
        self.relationships = {}
        self._lock = threading.RLock()

    def add_relationship(self, from_cid: str, to_cid: str, weight: float = 1.0):
        """Add a relationship between two content items.

        Args:
            from_cid: Source CID
            to_cid: Target CID
            weight: Relationship strength (0.0-1.0)
        """
        with self._lock:
            if from_cid not in self.relationships:
                self.relationships[from_cid] = []

            # Check if relationship already exists
            for i, (cid, w) in enumerate(self.relationships[from_cid]):
                if cid == to_cid:
                    # Update weight
                    self.relationships[from_cid][i] = (cid, max(w, weight))
                    return

            # Add new relationship
            self.relationships[from_cid].append((to_cid, weight))

    def get_related_content(self, cid: str) -> List[Tuple[str, float]]:
        """Get content related to the given CID.

        Args:
            cid: Content identifier

        Returns:
            List of (related_cid, relationship_weight) tuples
        """
        with self._lock:
            if cid not in self.relationships:
                return []

            # Return sorted by weight (highest first)
            relationships = self.relationships[cid]
            relationships.sort(key=lambda x: x[1], reverse=True)
            return relationships

    def create_content_groups(self, group_count: int, items_per_group: int, inter_group_links: int = 2) -> List[str]:
        """Create groups of related content for testing.

        Args:
            group_count: Number of content groups to create
            items_per_group: Number of items in each group
            inter_group_links: Number of links between different groups

        Returns:
            List of all content IDs created
        """
        all_cids = []
        groups = []

        # Create groups
        for g in range(group_count):
            group_cids = []

            # Create items in this group
            for i in range(items_per_group):
                cid = f"Qm{uuid.uuid4().hex[:40]}"
                group_cids.append(cid)
                all_cids.append(cid)

            groups.append(group_cids)

            # Create intra-group relationships
            for i, cid1 in enumerate(group_cids):
                # Connect to the next 3 items (or fewer if near the end)
                for j in range(1, min(4, items_per_group - i)):
                    cid2 = group_cids[i + j]
                    # Higher weight for closer items
                    weight = 1.0 - (j * 0.2)
                    self.add_relationship(cid1, cid2, weight)

                    # Bidirectional with slightly lower weight in reverse
                    self.add_relationship(cid2, cid1, weight * 0.8)

        # Create inter-group relationships
        for _ in range(inter_group_links):
            # Pick two random groups
            group1_idx = random.randint(0, group_count - 1)
            group2_idx = random.randint(0, group_count - 1)
            while group2_idx == group1_idx:
                group2_idx = random.randint(0, group_count - 1)

            # Pick random items from each group
            cid1 = random.choice(groups[group1_idx])
            cid2 = random.choice(groups[group2_idx])

            # Create relationship
            weight = random.uniform(0.3, 0.7)
            self.add_relationship(cid1, cid2, weight)
            self.add_relationship(cid2, cid1, weight * 0.9)

        return all_cids

def run_benchmark(title, cache, cids, sequential=True, repetitions=1, content_graph=None):
    """Run a benchmark test on the cache.

    Args:
        title: Title for the benchmark
        cache: Cache instance to test
        cids: List of content IDs to access
        sequential: Whether to access CIDs sequentially or randomly
        repetitions: Number of times to repeat the access pattern
        content_graph: Optional content graph for logging

    Returns:
        Dictionary with benchmark results
    """
    logger.info(f"\n=== {title} ===\n")

    # Initialize metrics
    access_times = []
    cache_hits = 0
    prefetch_hits = 0
    total_gets = 0

    # Run the benchmark
    for rep in range(repetitions):
        logger.info(f"Starting repetition {rep + 1}/{repetitions}")

        # Determine access order
        if sequential:
            access_cids = cids.copy()
        else:
            access_cids = random.sample(cids, len(cids))

        # Access each CID
        for i, cid in enumerate(access_cids):
            # Get content and record time
            start_time = time.time()
            result = cache.get(cid)
            access_time = time.time() - start_time

            # Record metrics
            access_times.append(access_time)
            total_gets += 1

            if result.get("cache_hit", False):
                cache_hits += 1

            if result.get("prefetch_hit", False):
                prefetch_hits += 1

            # Log progress
            if (i + 1) % 20 == 0 or i == len(access_cids) - 1:
                logger.info(f"Processed {i + 1}/{len(access_cids)} items")

                # Log some stats
                cache_hit_rate = cache_hits / total_gets
                prefetch_hit_rate = prefetch_hits / total_gets
                avg_access_time = sum(access_times) / len(access_times)

                logger.info(f"  Cache Hit Rate: {cache_hit_rate:.2%}")
                logger.info(f"  Prefetch Hit Rate: {prefetch_hit_rate:.2%}")
                logger.info(f"  Average Access Time: {avg_access_time * 1000:.2f} ms")

            # If we have content relationships, log them
            if content_graph and i % 20 == 0:
                related = content_graph.get_related_content(cid)
                if related:
                    related_str = ", ".join([f"{c[:8]}({w:.2f})" for c, w in related[:3]])
                    logger.info(f"  Related to {cid[:8]}: {related_str}")

            # Small delay between requests
            time.sleep(0.01)

    # Calculate final metrics
    cache_hit_rate = cache_hits / total_gets
    prefetch_hit_rate = prefetch_hits / total_gets
    avg_access_time = sum(access_times) / len(access_times)

    # Get stats from the cache
    try:
        cache_stats = cache.get_stats()
    except:
        cache_stats = {}

    # Log results
    logger.info(f"\n=== {title} Results ===\n")
    logger.info(f"Total Gets: {total_gets}")
    logger.info(f"Cache Hits: {cache_hits} ({cache_hit_rate:.2%})")
    logger.info(f"Prefetch Hits: {prefetch_hits} ({prefetch_hit_rate:.2%})")
    logger.info(f"Average Access Time: {avg_access_time * 1000:.2f} ms")

    # Return results
    return {
        "title": title,
        "total_gets": total_gets,
        "cache_hits": cache_hits,
        "cache_hit_rate": cache_hit_rate,
        "prefetch_hits": prefetch_hits,
        "prefetch_hit_rate": prefetch_hit_rate,
        "avg_access_time": avg_access_time,
        "access_times": access_times,
        "cache_stats": cache_stats
    }

def compare_strategies():
    """Compare different prefetching strategies."""
    logger.info("\n=== Comparing Prefetching Strategies ===\n")

    # Create content graph for content-aware prefetching
    content_graph = ContentGraph()
    cids = content_graph.create_content_groups(
        group_count=5,
        items_per_group=10,
        inter_group_links=5
    )

    # Create content relationship function for content-aware prefetching
    def get_related_content(cid):
        return content_graph.get_related_content(cid)

    # Strategies to test
    strategies = [
        ("No Prefetching", None),
        ("Sequential", "sequential"),
        ("Temporal", "temporal"),
        ("Hybrid", "hybrid"),
        ("Content-Aware", "content_aware")
    ]

    # Run benchmarks
    results = []

    for name, strategy in strategies:
        logger.info(f"\nTesting strategy: {name}")

        # Create the cache
        if strategy is None:
            # Base cache without prefetching
            cache = MockParquetCIDCache(
                max_size=1024*1024*10,
                cache_latency=0.05
            )
        else:
            # Cache with prefetching
            base_cache = MockParquetCIDCache(
                max_size=1024*1024*10,
                cache_latency=0.05
            )

            cache = PrefetchingParquetCIDCache(
                base_cache=base_cache,
                prefetch_strategy=strategy,
                max_prefetch_workers=2,
                max_prefetch_queue=10,
                enable_content_aware=strategy == "content_aware",
                content_relationship_fn=get_related_content if strategy == "content_aware" else None
            )

        # Run mixed access pattern benchmark
        result = run_benchmark(
            title=f"Strategy: {name}",
            cache=cache,
            cids=cids,
            sequential=False,
            repetitions=2,
            content_graph=content_graph
        )

        # Add strategy name
        result["strategy"] = name
        results.append(result)

        # Clean up
        if hasattr(cache, "shutdown"):
            cache.shutdown()

    # Visualize results
    visualize_comparison(results)

    return results

def visualize_comparison(results):
    """Visualize strategy comparison results.

    Args:
        results: List of benchmark results
    """
    try:
        import matplotlib.pyplot as plt

        # Prepare data
        strategies = [r["strategy"] for r in results]
        hit_rates = [r["prefetch_hit_rate"] * 100 for r in results]
        access_times = [r["avg_access_time"] * 1000 for r in results]

        # Create figure with two subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

        # Plot hit rates
        bars1 = ax1.bar(strategies, hit_rates, color='skyblue')
        ax1.set_title('Prefetch Hit Rate')
        ax1.set_xlabel('Strategy')
        ax1.set_ylabel('Hit Rate (%)')
        ax1.grid(axis='y', linestyle='--', alpha=0.7)

        # Add value labels
        for bar in bars1:
            height = bar.get_height()
            ax1.annotate(f'{height:.1f}%',
                         xy=(bar.get_x() + bar.get_width() / 2, height),
                         xytext=(0, 3),
                         textcoords="offset points",
                         ha='center', va='bottom')

        # Plot access times
        bars2 = ax2.bar(strategies, access_times, color='salmon')
        ax2.set_title('Average Access Time')
        ax2.set_xlabel('Strategy')
        ax2.set_ylabel('Time (ms)')
        ax2.grid(axis='y', linestyle='--', alpha=0.7)

        # Add value labels
        for bar in bars2:
            height = bar.get_height()
            ax2.annotate(f'{height:.1f} ms',
                         xy=(bar.get_x() + bar.get_width() / 2, height),
                         xytext=(0, 3),
                         textcoords="offset points",
                         ha='center', va='bottom')

        plt.tight_layout()
        plt.savefig('prefetch_comparison.png')
        logger.info("Saved visualization to prefetch_comparison.png")

    except ImportError:
        logger.warning("Matplotlib not available. Skipping visualization.")
    except Exception as e:
        logger.error(f"Error generating visualization: {e}")

def main():
    """Main function running the prefetching ParquetCIDCache example."""
    logger.info("=== ParquetCIDCache with Read-Ahead Prefetching Example ===")

    # Part 1: Basic usage demonstration
    logger.info("\n=== Basic Usage Demonstration ===\n")

    # Create a base cache
    base_cache = MockParquetCIDCache(
        max_size=1024*1024*10,
        cache_latency=0.05  # 50ms simulated latency
    )

    # Create a prefetching cache wrapper
    prefetching_cache = PrefetchingParquetCIDCache(
        base_cache=base_cache,
        prefetch_strategy="sequential",
        max_prefetch_workers=2,
        max_prefetch_queue=10,
        max_memory_usage=1024*1024*10,  # 10MB
        prefetch_threshold=0.3
    )

    # Generate some test content IDs
    cids = [f"Qm{uuid.uuid4().hex[:40]}" for _ in range(50)]

    # Run a benchmark
    sequential_results = run_benchmark(
        title="Sequential Access with Prefetching",
        cache=prefetching_cache,
        cids=cids,
        sequential=True,
        repetitions=2
    )

    # Display prefetching statistics
    logger.info("\nPrefetching Statistics:")
    stats = prefetching_cache.get_stats()
    if "prefetch_stats" in stats:
        prefetch_stats = stats["prefetch_stats"]
        logger.info(f"  Prefetched Gets: {prefetch_stats.get('prefetched_gets', 0)}")
        logger.info(f"  Prefetch Hits: {prefetch_stats.get('prefetch_hits', 0)}")
        logger.info(f"  Prefetch Hit Rate: {prefetch_stats.get('prefetch_hit_rate', 0):.2%}")

    # Part 2: Strategy comparison
    compare_strategies()

    # Part 3: Factory demonstration
    logger.info("\n=== Factory Pattern Demonstration ===\n")

    # Create a new cache using the factory
    factory_cache = ParquetCIDCacheFactory.create_with_prefetching(
        base_cache_cls=MockParquetCIDCache,
        prefetch_strategy="hybrid",
        max_prefetch_workers=3,
        max_memory_usage=1024*1024*20,  # 20MB
        max_size=1024*1024*50,  # base cache size of 50MB
        cache_latency=0.05
    )

    # Run a simple test
    factory_results = run_benchmark(
        title="Factory-created Cache Test",
        cache=factory_cache,
        cids=cids,
        sequential=False,
        repetitions=1
    )

    # Summary
    logger.info("\n=== Example Summary ===\n")
    logger.info("This example demonstrated:")
    logger.info("1. Basic usage of PrefetchingParquetCIDCache")
    logger.info("2. Comparison of different prefetching strategies")
    logger.info("3. Factory pattern for easy cache creation")
    logger.info("4. Performance benefits of read-ahead prefetching")

    # Clean up
    prefetching_cache.shutdown()
    factory_cache.shutdown()

if __name__ == "__main__":
    main()
