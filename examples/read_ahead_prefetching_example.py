#!/usr/bin/env python3
"""
Example demonstrating the Read-Ahead Prefetching capabilities of ipfs_kit_py.

This example shows how to use read-ahead prefetching to improve
performance by loading content before it's explicitly requested.
"""

import os
import time
import random
import uuid
import threading
import logging
from typing import Dict, List, Tuple, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import the ipfs_kit_py package
try:
    from ipfs_kit_py.ipfs_kit import IPFSKit
    from ipfs_kit_py.cache.read_ahead_prefetching import (
        ReadAheadPrefetchManager,
        SequentialPrefetchStrategy,
        TemporalPrefetchStrategy,
        HybridPrefetchStrategy
    )
except ImportError:
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from ipfs_kit_py.ipfs_kit import IPFSKit
    from ipfs_kit_py.cache.read_ahead_prefetching import (
        ReadAheadPrefetchManager,
        SequentialPrefetchStrategy,
        TemporalPrefetchStrategy,
        HybridPrefetchStrategy
    )

# Create a logger for this example
logger = logging.getLogger("read_ahead_example")

class ContentRegistry:
    """Simple registry to track content for our example."""

    def __init__(self):
        """Initialize the content registry."""
        self.content = {}
        self.access_times = {}
        self._lock = threading.RLock()

    def add_content(self, content_data: bytes) -> str:
        """Add content to the registry.

        Args:
            content_data: The content data

        Returns:
            CID-like identifier for the content
        """
        with self._lock:
            # Generate a CID-like identifier
            cid = f"Qm{uuid.uuid4().hex[:40]}"
            self.content[cid] = content_data
            self.access_times[cid] = []
            return cid

    def get_content(self, cid: str) -> bytes:
        """Get content from the registry.

        Args:
            cid: The content identifier

        Returns:
            The content data
        """
        with self._lock:
            # Record access time
            self.access_times[cid].append(time.time())

            # Simulate network latency for first access
            if len(self.access_times[cid]) == 1:
                time.sleep(0.1)  # 100ms simulated latency

            return self.content.get(cid, b"")

    def generate_related_content(self, count: int = 10, linked_groups: int = 3) -> List[str]:
        """Generate related content for testing prefetching.

        Creates groups of content that are related to each other.

        Args:
            count: Total number of content items to generate
            linked_groups: Number of linked groups to create

        Returns:
            List of content identifiers
        """
        all_cids = []

        # Create linked groups of content
        items_per_group = count // linked_groups
        for group in range(linked_groups):
            group_cids = []

            # Generate content for this group
            for i in range(items_per_group):
                # Create content with group and sequence identifiers
                content = f"Group {group} Item {i} Data: {uuid.uuid4().hex}".encode()
                cid = self.add_content(content)
                group_cids.append(cid)
                all_cids.append(cid)

        return all_cids

def simulate_sequential_access(prefetch_manager, registry, cids):
    """Simulate sequential access pattern to test prefetching."""
    logger.info("Starting sequential access simulation...")

    # Access each CID in sequence
    access_times = {}
    hit_count = 0

    for i, cid in enumerate(cids):
        # Record start time
        start_time = time.time()

        # Check if this was prefetched
        was_hit = prefetch_manager.check_prefetched(cid)
        if was_hit:
            hit_count += 1

        # Get content (and record access for prefetching)
        content = registry.get_content(cid)
        prefetch_manager.record_access(cid)

        # Record access time
        access_times[cid] = time.time() - start_time

        # Log progress periodically
        if (i + 1) % 5 == 0:
            logger.info(f"Accessed {i + 1}/{len(cids)} items, prefetch hits: {hit_count}")

        # Small delay between requests
        time.sleep(0.05)

    # Calculate metrics
    avg_time = sum(access_times.values()) / len(access_times)
    hit_rate = hit_count / len(cids) if len(cids) > 0 else 0

    logger.info(f"Sequential access complete: {len(cids)} items, {hit_count} prefetch hits")
    logger.info(f"Hit rate: {hit_rate:.2%}, Average access time: {avg_time*1000:.2f}ms")

    return hit_rate, avg_time, access_times

def simulate_temporal_access(prefetch_manager, registry, cids, repetitions=3, interval=0.5):
    """Simulate temporal access pattern with regular repeating access."""
    logger.info("Starting temporal access simulation...")

    # Select a subset of CIDs to access repeatedly
    regular_cids = random.sample(cids, min(5, len(cids)))

    # Initialize metrics
    access_times = {}
    hit_count = 0
    total_accesses = 0

    # Access each regular CID multiple times with consistent intervals
    for rep in range(repetitions):
        logger.info(f"Starting repetition {rep + 1}/{repetitions}...")

        for cid in regular_cids:
            # Record start time
            start_time = time.time()

            # Check if this was prefetched
            was_hit = prefetch_manager.check_prefetched(cid)
            if was_hit:
                hit_count += 1

            # Get content (and record access for prefetching)
            content = registry.get_content(cid)
            prefetch_manager.record_access(cid)

            # Record access time
            if cid not in access_times:
                access_times[cid] = []
            access_times[cid].append(time.time() - start_time)

            total_accesses += 1

            # Wait for the interval
            time.sleep(interval)

    # Also access some random CIDs to provide variety
    for _ in range(10):
        random_cid = random.choice(cids)

        # Record start time
        start_time = time.time()

        # Check if this was prefetched
        was_hit = prefetch_manager.check_prefetched(random_cid)
        if was_hit:
            hit_count += 1

        # Get content (and record access for prefetching)
        content = registry.get_content(random_cid)
        prefetch_manager.record_access(random_cid)

        # Record access time
        if random_cid not in access_times:
            access_times[random_cid] = []
        access_times[random_cid].append(time.time() - start_time)

        total_accesses += 1

        # Random delay
        time.sleep(random.uniform(0.2, 1.0))

    # Calculate metrics
    all_times = [t for times in access_times.values() for t in times]
    avg_time = sum(all_times) / len(all_times) if all_times else 0
    hit_rate = hit_count / total_accesses if total_accesses > 0 else 0

    logger.info(f"Temporal access complete: {total_accesses} accesses, {hit_count} prefetch hits")
    logger.info(f"Hit rate: {hit_rate:.2%}, Average access time: {avg_time*1000:.2f}ms")

    return hit_rate, avg_time, access_times

def simulate_mixed_access(prefetch_manager, registry, cids):
    """Simulate a mixed access pattern with both sequential and temporal elements."""
    logger.info("Starting mixed access pattern simulation...")

    # Initialize metrics
    access_times = {}
    hit_count = 0
    total_accesses = 0

    # First, do some sequential access
    sequential_sets = 3
    seq_items_per_set = 5

    for s in range(sequential_sets):
        # Get a sequential subset
        start_idx = random.randint(0, max(0, len(cids) - seq_items_per_set - 1))
        seq_subset = cids[start_idx:start_idx + seq_items_per_set]

        for cid in seq_subset:
            # Record start time
            start_time = time.time()

            # Check if this was prefetched
            was_hit = prefetch_manager.check_prefetched(cid)
            if was_hit:
                hit_count += 1

            # Get content (and record access for prefetching)
            content = registry.get_content(cid)
            prefetch_manager.record_access(cid)

            # Record access time
            if cid not in access_times:
                access_times[cid] = []
            access_times[cid].append(time.time() - start_time)

            total_accesses += 1

            # Small delay between sequential requests
            time.sleep(0.05)

        # Larger delay between sets
        time.sleep(0.5)

    # Now, do some temporal access (repeated access to the same items)
    temporal_items = random.sample(cids, 3)
    repetitions = 3

    for rep in range(repetitions):
        for cid in temporal_items:
            # Record start time
            start_time = time.time()

            # Check if this was prefetched
            was_hit = prefetch_manager.check_prefetched(cid)
            if was_hit:
                hit_count += 1

            # Get content (and record access for prefetching)
            content = registry.get_content(cid)
            prefetch_manager.record_access(cid)

            # Record access time
            if cid not in access_times:
                access_times[cid] = []
            access_times[cid].append(time.time() - start_time)

            total_accesses += 1

            # Regular delay for temporal pattern
            time.sleep(0.3)

    # Finally, add some random accesses
    for _ in range(5):
        random_cid = random.choice(cids)

        # Record start time
        start_time = time.time()

        # Check if this was prefetched
        was_hit = prefetch_manager.check_prefetched(random_cid)
        if was_hit:
            hit_count += 1

        # Get content (and record access for prefetching)
        content = registry.get_content(random_cid)
        prefetch_manager.record_access(random_cid)

        # Record access time
        if random_cid not in access_times:
            access_times[random_cid] = []
        access_times[random_cid].append(time.time() - start_time)

        total_accesses += 1

        # Random delay
        time.sleep(random.uniform(0.1, 0.8))

    # Calculate metrics
    all_times = [t for times in access_times.values() for t in times]
    avg_time = sum(all_times) / len(all_times) if all_times else 0
    hit_rate = hit_count / total_accesses if total_accesses > 0 else 0

    logger.info(f"Mixed access complete: {total_accesses} accesses, {hit_count} prefetch hits")
    logger.info(f"Hit rate: {hit_rate:.2%}, Average access time: {avg_time*1000:.2f}ms")

    return hit_rate, avg_time, access_times

def compare_strategies(registry, cids):
    """Compare different prefetching strategies."""
    logger.info("\n=== Comparing Prefetch Strategies ===\n")

    strategies = {
        "Sequential": SequentialPrefetchStrategy(),
        "Temporal": TemporalPrefetchStrategy(window_size=2.0),
        "Hybrid": HybridPrefetchStrategy({
            SequentialPrefetchStrategy(): 0.6,
            TemporalPrefetchStrategy(window_size=2.0): 0.4
        })
    }

    results = {}

    for strategy_name, strategy in strategies.items():
        logger.info(f"\nTesting strategy: {strategy_name}")

        # Create a prefetch manager with this strategy
        prefetch_manager = ReadAheadPrefetchManager(
            fetch_fn=registry.get_content,
            max_prefetch_workers=2,
            max_prefetch_queue=10,
            enable_metrics=True
        )

        # Set the strategy
        prefetch_manager.strategies[strategy_name.lower()] = strategy
        prefetch_manager.set_strategy(strategy_name.lower())

        # Run mixed access pattern test
        hit_rate, avg_time, _ = simulate_mixed_access(prefetch_manager, registry, cids)

        # Get metrics
        metrics = prefetch_manager.get_metrics()

        # Store results
        results[strategy_name] = {
            "hit_rate": hit_rate,
            "avg_access_time": avg_time,
            "completed_prefetches": metrics.get("prefetch_completed", 0),
            "hit_rate_internal": metrics.get("hit_rate", 0)
        }

        # Shutdown the prefetch manager
        prefetch_manager.shutdown()

    # Print comparison results
    logger.info("\n=== Strategy Comparison Results ===\n")
    logger.info(f"{'Strategy':<12} {'Hit Rate':<10} {'Avg Time':<15} {'Prefetches':<15}")
    logger.info("-" * 50)

    for strategy_name, result in results.items():
        logger.info(
            f"{strategy_name:<12} "
            f"{result['hit_rate']:.2%:<10} "
            f"{result['avg_access_time']*1000:.2f} ms{'':5} "
            f"{result['completed_prefetches']:<15}"
        )

def main():
    """Main function running the read-ahead prefetching example."""
    logger.info("=== Read-Ahead Prefetching Example ===")

    # Create a content registry
    registry = ContentRegistry()

    # Generate test content
    logger.info("Generating test content...")
    cids = registry.generate_related_content(count=30, linked_groups=5)
    logger.info(f"Generated {len(cids)} content items in 5 linked groups")

    # Create a prefetch manager
    prefetch_manager = ReadAheadPrefetchManager(
        fetch_fn=registry.get_content,
        max_prefetch_workers=2,
        max_prefetch_queue=10,
        enable_metrics=True
    )

    try:
        # Test sequential access pattern
        logger.info("\n=== Testing Sequential Access Pattern ===\n")
        prefetch_manager.set_strategy("sequential")
        sequential_hit_rate, sequential_avg_time, _ = simulate_sequential_access(
            prefetch_manager, registry, cids[:20])

        # Show metrics from the prefetch manager
        logger.info("\nSequential Access Metrics:")
        metrics = prefetch_manager.get_metrics()
        logger.info(f"  - Prefetch Requested: {metrics.get('prefetch_requested', 0)}")
        logger.info(f"  - Prefetch Completed: {metrics.get('prefetch_completed', 0)}")
        logger.info(f"  - Prefetch Hits: {metrics.get('prefetch_hits', 0)}")
        logger.info(f"  - Prefetch Misses: {metrics.get('prefetch_misses', 0)}")
        logger.info(f"  - Hit Rate: {metrics.get('hit_rate', 0):.2%}")

        # Reset for next test
        prefetch_manager.shutdown()
        prefetch_manager = ReadAheadPrefetchManager(
            fetch_fn=registry.get_content,
            max_prefetch_workers=2,
            max_prefetch_queue=10,
            enable_metrics=True
        )

        # Test temporal access pattern
        logger.info("\n=== Testing Temporal Access Pattern ===\n")
        prefetch_manager.set_strategy("temporal")
        temporal_hit_rate, temporal_avg_time, _ = simulate_temporal_access(
            prefetch_manager, registry, cids, repetitions=3, interval=0.3)

        # Show metrics from the prefetch manager
        logger.info("\nTemporal Access Metrics:")
        metrics = prefetch_manager.get_metrics()
        logger.info(f"  - Prefetch Requested: {metrics.get('prefetch_requested', 0)}")
        logger.info(f"  - Prefetch Completed: {metrics.get('prefetch_completed', 0)}")
        logger.info(f"  - Prefetch Hits: {metrics.get('prefetch_hits', 0)}")
        logger.info(f"  - Prefetch Misses: {metrics.get('prefetch_misses', 0)}")
        logger.info(f"  - Hit Rate: {metrics.get('hit_rate', 0):.2%}")

        # Reset again
        prefetch_manager.shutdown()

        # Compare different strategies
        compare_strategies(registry, cids)

        # Final summary
        logger.info("\n=== Example Complete ===\n")
        logger.info("This example demonstrated read-ahead prefetching with different access patterns:")
        logger.info("  1. Sequential access: prefetching next items in a sequence")
        logger.info("  2. Temporal access: prefetching items that are accessed at regular intervals")
        logger.info("  3. Mixed access: combining multiple access patterns")
        logger.info("\nMultiple prefetching strategies were compared:")
        logger.info("  - Sequential strategy: optimized for sequential access patterns")
        logger.info("  - Temporal strategy: optimized for regular, repeating access patterns")
        logger.info("  - Hybrid strategy: combines multiple strategies with weighted scoring")

    finally:
        # Clean up
        if prefetch_manager:
            prefetch_manager.shutdown()

if __name__ == "__main__":
    main()
