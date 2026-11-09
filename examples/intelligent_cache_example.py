"""
Example demonstrating the intelligent cache management features.

This script demonstrates how to use the IntelligentCacheManager to optimize
cache performance through predictive eviction and dynamic tiering based on access patterns.
"""

import time
import os
import logging
import random
import json
import threading
from datetime import datetime
import matplotlib.pyplot as plt

from ipfs_kit_py.cache import (
    IntelligentCacheManager, 
    AccessPattern, 
    PredictiveModel,
    IntelligentCacheStrategyProvider
)
from ipfs_kit_py.ipfs_kit import IPFSKit

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('intelligent_cache_example')

# Create a class that extends IntelligentCacheManager to implement actual tier storage
class ExampleCacheManager(IntelligentCacheManager):
    """Example implementation of IntelligentCacheManager with simulated tiers."""
    
    def __init__(self):
        """Initialize with smaller tier sizes for the example."""
        super().__init__(
            base_path=os.path.expanduser("~/.ipfs_kit/example_cache"),
            memory_tier_size=5 * 1024 * 1024,  # 5MB
            ssd_tier_size=20 * 1024 * 1024,    # 20MB
            hdd_tier_size=50 * 1024 * 1024,    # 50MB
            min_observations=20,               # Lower for example
            training_interval=300,             # 5 minutes for example
            enable_predictive_prefetch=True,
            enable_auto_rebalance=True
        )
        
        # Actual storage for the tiers (simulated)
        self.memory_storage = {}
        self.ssd_storage = {}
        self.hdd_storage = {}
        
        # Current sizes for tracking
        self._update_tier_usage()
        
        logger.info(
            f"ExampleCacheManager initialized with tier sizes: "
            f"Memory={self.tier_sizes['memory']/1024/1024:.1f}MB, "
            f"SSD={self.tier_sizes['ssd']/1024/1024:.1f}MB, "
            f"HDD={self.tier_sizes['hdd']/1024/1024:.1f}MB"
        )
    
    def _update_tier_usage(self):
        """Update tier usage based on actual storage."""
        self.tier_usage['memory'] = sum(len(data) for data in self.memory_storage.values())
        self.tier_usage['ssd'] = sum(len(data) for data in self.ssd_storage.values())
        self.tier_usage['hdd'] = sum(len(data) for data in self.hdd_storage.values())
    
    def get_current_tier(self, cid):
        """Implementation that checks actual tiers for content presence."""
        if cid in self.memory_storage:
            return 'memory'
        elif cid in self.ssd_storage:
            return 'ssd'
        elif cid in self.hdd_storage:
            return 'hdd'
        else:
            return None
    
    def store_content(self, cid, data, tier=None):
        """Store content in the appropriate tier."""
        current_tier = self.get_current_tier(cid)
        if current_tier:
            # Remove from current tier first
            self.remove_content(cid)
        
        # Auto-select optimal tier if not specified
        if tier is None:
            tier = self.get_optimal_tier(cid)
        
        # Store in specified tier
        size = len(data)
        
        # Check if there's enough space
        if tier == 'memory' and self.tier_usage['memory'] + size > self.tier_sizes['memory']:
            # Not enough space, get eviction candidates
            required_space = size - (self.tier_sizes['memory'] - self.tier_usage['memory'])
            candidates = self.get_eviction_candidates(tier, required_space)
            
            # Evict content if candidates found
            for evict_cid, _ in candidates:
                # Move to slower tier instead of removing
                self.promote_or_demote(evict_cid, 'memory', 'ssd')
                if self.tier_usage['memory'] + size <= self.tier_sizes['memory']:
                    break
        
        # Do the same for SSD tier
        if tier == 'ssd' and self.tier_usage['ssd'] + size > self.tier_sizes['ssd']:
            required_space = size - (self.tier_sizes['ssd'] - self.tier_usage['ssd'])
            candidates = self.get_eviction_candidates(tier, required_space)
            
            for evict_cid, _ in candidates:
                self.promote_or_demote(evict_cid, 'ssd', 'hdd')
                if self.tier_usage['ssd'] + size <= self.tier_sizes['ssd']:
                    break
        
        # For HDD tier, just evict if necessary
        if tier == 'hdd' and self.tier_usage['hdd'] + size > self.tier_sizes['hdd']:
            required_space = size - (self.tier_sizes['hdd'] - self.tier_usage['hdd'])
            candidates = self.get_eviction_candidates(tier, required_space)
            
            for evict_cid, _ in candidates:
                self.remove_content(evict_cid)
                if self.tier_usage['hdd'] + size <= self.tier_sizes['hdd']:
                    break
        
        # Store in the appropriate tier
        if tier == 'memory':
            self.memory_storage[cid] = data
        elif tier == 'ssd':
            self.ssd_storage[cid] = data
        else:  # hdd
            self.hdd_storage[cid] = data
        
        # Record the access and update sizes
        content_type = 'text/plain'  # For example
        self.record_access(cid, size_bytes=size, content_type=content_type, tier=tier)
        self._update_tier_usage()
        
        logger.debug(f"Stored content {cid[:8]} in {tier} tier, size={size/1024:.1f}KB")
        
        return tier
    
    def retrieve_content(self, cid):
        """Retrieve content from whatever tier it's in."""
        current_tier = self.get_current_tier(cid)
        if current_tier is None:
            return None
        
        # Get from appropriate tier
        if current_tier == 'memory':
            data = self.memory_storage[cid]
        elif current_tier == 'ssd':
            data = self.ssd_storage[cid]
        else:  # hdd
            data = self.hdd_storage[cid]
        
        # Record access
        self.record_access(cid, tier=current_tier)
        
        # Check if prefetching would be helpful
        optimal_tier = self.get_optimal_tier(cid)
        if optimal_tier != current_tier:
            # Content is in wrong tier, schedule movement
            if current_tier == 'hdd' and optimal_tier in ('memory', 'ssd'):
                # Promote to faster tier
                self.promote_or_demote(cid, current_tier, optimal_tier)
        
        return data
    
    def promote_or_demote(self, cid, from_tier, to_tier):
        """Move content from one tier to another."""
        if from_tier == to_tier:
            return
        
        # Get the data from source tier
        if from_tier == 'memory':
            data = self.memory_storage.get(cid)
        elif from_tier == 'ssd':
            data = self.ssd_storage.get(cid)
        else:  # hdd
            data = self.hdd_storage.get(cid)
        
        if data is None:
            logger.warning(f"Content {cid[:8]} not found in {from_tier} tier")
            return False
        
        # Remove from source tier
        if from_tier == 'memory':
            del self.memory_storage[cid]
        elif from_tier == 'ssd':
            del self.ssd_storage[cid]
        else:  # hdd
            del self.hdd_storage[cid]
        
        # Add to destination tier
        if to_tier == 'memory':
            self.memory_storage[cid] = data
        elif to_tier == 'ssd':
            self.ssd_storage[cid] = data
        else:  # hdd
            self.hdd_storage[cid] = data
        
        # Update tier usage
        self._update_tier_usage()
        
        logger.debug(f"Moved content {cid[:8]} from {from_tier} to {to_tier}")
        return True
    
    def remove_content(self, cid):
        """Remove content from all tiers."""
        removed = False
        
        if cid in self.memory_storage:
            del self.memory_storage[cid]
            removed = True
        
        if cid in self.ssd_storage:
            del self.ssd_storage[cid]
            removed = True
        
        if cid in self.hdd_storage:
            del self.hdd_storage[cid]
            removed = True
        
        if removed:
            self._update_tier_usage()
            logger.debug(f"Removed content {cid[:8]}")
        
        return removed
    
    def get_tier_stats(self):
        """Get detailed stats about tiers."""
        return {
            'memory': {
                'size': self.tier_usage['memory'],
                'capacity': self.tier_sizes['memory'],
                'utilization': 100 * self.tier_usage['memory'] / self.tier_sizes['memory'],
                'items': len(self.memory_storage)
            },
            'ssd': {
                'size': self.tier_usage['ssd'],
                'capacity': self.tier_sizes['ssd'],
                'utilization': 100 * self.tier_usage['ssd'] / self.tier_sizes['ssd'],
                'items': len(self.ssd_storage)
            },
            'hdd': {
                'size': self.tier_usage['hdd'],
                'capacity': self.tier_sizes['hdd'],
                'utilization': 100 * self.tier_usage['hdd'] / self.tier_sizes['hdd'],
                'items': len(self.hdd_storage)
            }
        }

# Example 1: Basic functionality
def example_basic_functionality():
    """Demonstrate basic functionality of the intelligent cache manager."""
    logger.info("Running Example 1: Basic Functionality")
    
    # Create the cache manager
    cache = ExampleCacheManager()
    
    # Generate some test content
    contents = []
    for i in range(30):
        # Create content with varying sizes
        size = random.randint(10, 1000) * 1024  # 10KB to 1MB
        data = b"X" * size
        cid = f"test-{i:04d}"
        contents.append((cid, data))
        
        # Store in cache (let it determine tier)
        cache.store_content(cid, data)
        
        # Random access to previously stored content
        if i > 0:
            # Access some previous content
            for _ in range(3):
                idx = random.randint(0, i-1)
                prev_cid = contents[idx][0]
                cache.retrieve_content(prev_cid)
    
    # Print stats
    tier_stats = cache.get_tier_stats()
    access_stats = cache.get_access_stats()
    
    logger.info("Tier Stats:")
    for tier, stats in tier_stats.items():
        logger.info(f"  {tier.upper()}: {stats['items']} items, " 
                   f"{stats['size']/1024/1024:.2f}MB " 
                   f"({stats['utilization']:.1f}% used)")
    
    logger.info("Access Stats:")
    logger.info(f"  Patterns tracked: {access_stats['pattern_count']}")
    logger.info(f"  Avg retention score: {access_stats['avg_retention_score']:.3f}")
    logger.info(f"  Avg reaccess probability: {access_stats['avg_reaccess_probability']:.3f}")
    logger.info(f"  Avg hours until next access: {access_stats['avg_hours_until_next_access']:.1f}")
    
    # Train models
    logger.info("Training predictive models...")
    training_results = cache.train_models(force=True)
    logger.info(f"Training results: {training_results}")
    
    # Clean up
    cache.cleanup()
    logger.info("Example 1 completed")
    
    return cache

# Example 2: Simulate realistic access patterns
def example_realistic_patterns():
    """Demonstrate realistic access patterns and cache adaptation."""
    logger.info("Running Example 2: Realistic Access Patterns")
    
    # Create cache manager
    cache = ExampleCacheManager()
    
    # Track metrics over time
    metrics = {
        'timestamps': [],
        'memory_utilization': [],
        'ssd_utilization': [],
        'hdd_utilization': [],
        'hit_rates': []
    }
    
    # Create content with different access patterns
    content_groups = {
        'hot': [],     # Frequently accessed 
        'warm': [],    # Occasionally accessed
        'cold': []     # Rarely accessed
    }
    
    # Generate content for each group
    for group, count in [('hot', 5), ('warm', 10), ('cold', 20)]:
        for i in range(count):
            # Size varies by group (hot = smaller, cold = larger)
            if group == 'hot':
                size = random.randint(10, 100) * 1024  # 10-100KB
            elif group == 'warm':
                size = random.randint(100, 500) * 1024  # 100-500KB
            else:
                size = random.randint(500, 2000) * 1024  # 500KB-2MB
                
            data = b"X" * size
            cid = f"{group}-{i:04d}"
            content_groups[group].append((cid, data))
            
            # Initial storage - let cache determine tier
            cache.store_content(cid, data)
    
    # Function to record metrics
    def record_metrics():
        tier_stats = cache.get_tier_stats()
        
        metrics['timestamps'].append(time.time())
        metrics['memory_utilization'].append(tier_stats['memory']['utilization'])
        metrics['ssd_utilization'].append(tier_stats['ssd']['utilization'])
        metrics['hdd_utilization'].append(tier_stats['hdd']['utilization'])
        
        # Calculate simulated hit rate
        # In a real system, this would be actual hit rate
        hits = len(cache.memory_storage) * 4 + len(cache.ssd_storage) * 2
        total = len(cache.memory_storage) + len(cache.ssd_storage) + len(cache.hdd_storage)
        if total > 0:
            hit_rate = hits / total
        else:
            hit_rate = 0
        metrics['hit_rates'].append(hit_rate)
    
    # Record initial metrics
    record_metrics()
    
    # Simulate 30 minutes of access patterns
    sim_time = 30 * 60  # 30 minutes in seconds
    interval = 30  # 30 seconds per cycle
    cycles = sim_time // interval
    
    for cycle in range(cycles):
        current_time = time.strftime("%H:%M:%S")
        logger.info(f"Cycle {cycle+1}/{cycles} at {current_time}")
        
        # Access hot content frequently
        for _ in range(10):  # 10 accesses per cycle
            cid, _ = random.choice(content_groups['hot'])
            cache.retrieve_content(cid)
        
        # Access warm content occasionally
        if cycle % 3 == 0:  # every 3 cycles
            for _ in range(3):
                cid, _ = random.choice(content_groups['warm'])
                cache.retrieve_content(cid)
        
        # Access cold content rarely
        if cycle % 10 == 0:  # every 10 cycles
            cid, _ = random.choice(content_groups['cold'])
            cache.retrieve_content(cid)
        
        # Add new content occasionally
        if cycle % 5 == 0:  # every 5 cycles
            group = random.choice(['hot', 'warm', 'cold'])
            size = random.randint(50, 1000) * 1024  # 50KB to 1MB
            data = b"X" * size
            cid = f"{group}-new-{cycle:04d}"
            content_groups[group].append((cid, data))
            cache.store_content(cid, data)
        
        # Perform manual rebalance every 5 cycles
        if cycle % 5 == 0:
            logger.info("Rebalancing tiers...")
            rebalance_stats = cache.rebalance_tiers()
            logger.info(f"Rebalance operations: {len(rebalance_stats['operations'])}")
        
        # Record metrics
        record_metrics()
        
        # Sleep a bit to simulate time passing
        time.sleep(0.1)  # Don't actually wait 30 seconds
    
    # Train models with accumulated data
    logger.info("Training models with accumulated data...")
    cache.train_models(force=True)
    
    # Plot metrics
    plt.figure(figsize=(12, 8))
    
    # Plot tier utilization
    plt.subplot(2, 1, 1)
    timestamps = [(t - metrics['timestamps'][0])/60 for t in metrics['timestamps']]  # Convert to minutes
    plt.plot(timestamps, metrics['memory_utilization'], 'r-', label='Memory Tier')
    plt.plot(timestamps, metrics['ssd_utilization'], 'g-', label='SSD Tier')
    plt.plot(timestamps, metrics['hdd_utilization'], 'b-', label='HDD Tier')
    plt.xlabel('Time (minutes)')
    plt.ylabel('Utilization (%)')
    plt.title('Cache Tier Utilization Over Time')
    plt.legend()
    plt.grid(True)
    
    # Plot hit rate
    plt.subplot(2, 1, 2)
    plt.plot(timestamps, metrics['hit_rates'], 'k-')
    plt.xlabel('Time (minutes)')
    plt.ylabel('Simulated Hit Rate')
    plt.title('Cache Hit Rate Over Time')
    plt.grid(True)
    
    plt.tight_layout()
    plt.savefig('intelligent_cache_metrics.png')
    logger.info("Metrics saved to intelligent_cache_metrics.png")
    
    # Print final stats
    tier_stats = cache.get_tier_stats()
    logger.info("Final Tier Stats:")
    for tier, stats in tier_stats.items():
        logger.info(f"  {tier.upper()}: {stats['items']} items, " 
                   f"{stats['size']/1024/1024:.2f}MB " 
                   f"({stats['utilization']:.1f}% used)")
    
    # Analyze where different content groups ended up
    tier_distribution = {'hot': {}, 'warm': {}, 'cold': {}}
    for group, items in content_groups.items():
        tier_counts = {'memory': 0, 'ssd': 0, 'hdd': 0, 'missing': 0}
        for cid, _ in items:
            tier = cache.get_current_tier(cid)
            if tier:
                tier_counts[tier] += 1
            else:
                tier_counts['missing'] += 1
        tier_distribution[group] = tier_counts
    
    logger.info("Content Group Distribution:")
    for group, counts in tier_distribution.items():
        total = sum(counts.values())
        logger.info(f"  {group.upper()} content ({total} items):")
        for tier, count in counts.items():
            if total > 0:
                logger.info(f"    {tier.upper()}: {count} items ({100*count/total:.1f}%)")
    
    # Cleanup
    cache.cleanup()
    logger.info("Example 2 completed")
    
    return cache, metrics

# Example 3: Machine Learning Strategy Comparison
def example_strategy_comparison():
    """Compare different cache eviction strategies."""
    logger.info("Running Example 3: Strategy Comparison")
    
    # Create cache manager
    cache = ExampleCacheManager()
    
    # Generate a dataset with mixed content
    contents = []
    for i in range(50):
        # Create content with varying sizes
        size = random.randint(50, 500) * 1024  # 50KB to 500KB
        data = b"X" * size
        cid = f"comp-{i:04d}"
        contents.append((cid, data))
        
        # Store in cache
        cache.store_content(cid, data)
        
        # Simulate some accesses to build up patterns
        if i > 0:
            # Create some locality of reference
            # Recent items are more likely to be accessed
            for _ in range(5):
                max_range = max(1, i-1)
                if random.random() < 0.7:
                    # 70% chance of accessing recent items
                    idx = random.randint(max(0, i-5), max_range)
                else:
                    # 30% chance of accessing older items
                    idx = random.randint(0, max_range)
                prev_cid = contents[idx][0]
                cache.retrieve_content(prev_cid)
    
    # Train models with the access pattern data
    logger.info("Training models...")
    training_results = cache.train_models(force=True)
    
    # Get strategy provider
    strategy_provider = IntelligentCacheStrategyProvider(cache)
    
    # Available strategies
    strategies = {
        'ML-based': strategy_provider.get_ml_based_strategy(),
        'Heuristic': strategy_provider.get_heuristic_strategy(),
        'LRU': strategy_provider.get_lru_strategy(),
        'LFU': strategy_provider.get_lfu_strategy(),
        'Size-aware': strategy_provider.get_size_aware_strategy(),
        'Latency-optimized': strategy_provider.get_latency_optimized_strategy(),
        'Balanced': strategy_provider.get_balanced_strategy()
    }
    
    # Compare eviction candidates from each strategy
    logger.info("Comparing eviction candidates from each strategy:")
    
    results = {}
    for name, strategy in strategies.items():
        # Get eviction candidates for each tier
        memory_candidates = []
        with cache.pattern_lock:
            # Only check items actually in memory tier
            memory_cids = list(cache.memory_storage.keys())
            
            # Score each item
            scores = [(cid, strategy(cid)) for cid in memory_cids]
            
            # Sort by score (ascending, lower is more evictable)
            scores.sort(key=lambda x: x[1])
            
            # Take top 5
            memory_candidates = scores[:5]
        
        results[name] = memory_candidates
        
        logger.info(f"\n{name} Strategy - Top 5 Memory Tier Eviction Candidates:")
        for i, (cid, score) in enumerate(memory_candidates):
            # Get additional info about the item
            with cache.pattern_lock:
                if cid in cache.access_patterns:
                    pattern = cache.access_patterns[cid]
                    logger.info(f"  {i+1}. {cid[:8]} - Score: {score:.4f}, "
                               f"Accesses: {pattern.access_count}, "
                               f"Size: {pattern.size_bytes/1024:.1f}KB")
                else:
                    logger.info(f"  {i+1}. {cid[:8]} - Score: {score:.4f}")
    
    # Add a test where we compare strategies in a cache-under-pressure scenario
    logger.info("\nTesting strategies under memory pressure...")
    
    def test_strategy(strategy_name, strategy_func):
        # Reset cache state
        test_cache = ExampleCacheManager()
        
        # Fill memory tier close to capacity
        memory_used = 0
        memory_limit = test_cache.tier_sizes['memory'] * 0.9  # 90% full
        
        # Create items with access patterns
        items = []
        while memory_used < memory_limit:
            size = random.randint(50, 200) * 1024  # 50-200KB
            data = b"X" * size
            cid = f"{strategy_name}-{len(items):04d}"
            test_cache.store_content(cid, data, tier='memory')
            items.append((cid, data, size))
            memory_used += size
            
            # Random accesses to create patterns
            if len(items) > 1:
                for _ in range(3):
                    idx = random.randint(0, len(items)-2)
                    test_cache.retrieve_content(items[idx][0])
        
        # Record initial state
        initial_items = len(test_cache.memory_storage)
        initial_size = test_cache.tier_usage['memory']
        
        # Create a custom eviction function that uses the strategy
        def custom_evict(required_space):
            # Get all memory items
            memory_cids = list(test_cache.memory_storage.keys())
            
            # Score each item using the strategy
            scores = [(cid, strategy_func(cid)) for cid in memory_cids]
            
            # Sort by score (ascending, lower is more evictable)
            scores.sort(key=lambda x: x[1])
            
            # Evict until we have enough space
            space_freed = 0
            evicted = 0
            for cid, _ in scores:
                size = len(test_cache.memory_storage[cid])
                # Actually remove from memory tier (move to SSD)
                test_cache.promote_or_demote(cid, 'memory', 'ssd')
                space_freed += size
                evicted += 1
                if space_freed >= required_space:
                    break
            
            return space_freed, evicted
        
        # Now add large item that requires eviction
        pressure_size = int(test_cache.tier_sizes['memory'] * 0.3)  # 30% of memory
        pressure_data = b"X" * pressure_size
        pressure_cid = f"{strategy_name}-pressure"
        
        # Calculate required eviction
        available = test_cache.tier_sizes['memory'] - test_cache.tier_usage['memory']
        required = pressure_size - available
        
        # Evict using strategy
        freed, evicted = custom_evict(required)
        
        # Now store the pressure item
        test_cache.store_content(pressure_cid, pressure_data, tier='memory')
        
        # Get final state
        final_items = len(test_cache.memory_storage)
        final_size = test_cache.tier_usage['memory']
        
        # Record access count distribution of evicted items
        access_counts = []
        sizes = []
        for cid, _, size in items:
            if test_cache.get_current_tier(cid) != 'memory':
                # This item was evicted
                with test_cache.pattern_lock:
                    if cid in test_cache.access_patterns:
                        pattern = test_cache.access_patterns[cid]
                        access_counts.append(pattern.access_count)
                        sizes.append(size)
        
        # Calculate metrics
        avg_access_count = sum(access_counts) / max(1, len(access_counts))
        avg_size = sum(sizes) / max(1, len(sizes))
        
        return {
            'strategy': strategy_name,
            'initial_items': initial_items,
            'initial_size': initial_size,
            'final_items': final_items,
            'final_size': final_size,
            'items_evicted': evicted,
            'space_freed': freed,
            'avg_access_count_evicted': avg_access_count,
            'avg_size_evicted': avg_size
        }
    
    # Test each strategy
    strategy_results = []
    for name, strategy in strategies.items():
        logger.info(f"Testing {name} strategy...")
        result = test_strategy(name, strategy)
        strategy_results.append(result)
    
    # Print comparison
    logger.info("\nStrategy Performance Under Pressure:")
    for result in strategy_results:
        logger.info(f"  {result['strategy']}:")
        logger.info(f"    Items before: {result['initial_items']}, after: {result['final_items']}")
        logger.info(f"    Size before: {result['initial_size']/1024/1024:.2f}MB, "
                   f"after: {result['final_size']/1024/1024:.2f}MB")
        logger.info(f"    Items evicted: {result['items_evicted']}")
        logger.info(f"    Avg access count of evicted items: {result['avg_access_count_evicted']:.1f}")
        logger.info(f"    Avg size of evicted items: {result['avg_size_evicted']/1024:.1f}KB")
    
    # Cleanup
    cache.cleanup()
    logger.info("Example 3 completed")
    
    return cache, strategy_results

# Main function to run all examples
def main():
    """Run all examples of intelligent cache management."""
    logger.info("Starting intelligent cache examples")
    
    # Run example 1: Basic functionality
    cache1 = example_basic_functionality()
    
    logger.info("---------------------------------------")
    
    # Run example 2: Realistic patterns
    cache2, metrics = example_realistic_patterns()
    
    logger.info("---------------------------------------")
    
    # Run example 3: Strategy comparison
    cache3, strategy_results = example_strategy_comparison()
    
    logger.info("All examples completed")

# Run the main function
if __name__ == "__main__":
    main()