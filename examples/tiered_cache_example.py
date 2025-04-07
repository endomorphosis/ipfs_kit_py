#!/usr/bin/env python3
"""
Example demonstrating the tiered caching system for IPFS content.

This script shows how to use the TieredCacheManager for efficient
content storage and retrieval with automatic migration between tiers.
"""

import os
import time
import random
import argparse
import logging
from typing import Dict, Any

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ipfs_kit_py.tiered_cache_manager import TieredCacheManager


def setup_logging(level=logging.INFO):
    """Set up logging configuration."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def create_sample_content(size_kb: int) -> bytes:
    """Create sample content of a specific size.
    
    Args:
        size_kb: Size of content to create in kilobytes
        
    Returns:
        Binary content of specified size
    """
    # Create semi-random data (more compressible than fully random)
    chunk_size = 1024  # 1KB chunks
    num_chunks = size_kb
    
    # Create different patterns for variety
    chunks = []
    for i in range(num_chunks):
        if i % 4 == 0:
            # Pattern 1: Repeated bytes
            chunks.append(bytes([i % 256]) * chunk_size)
        elif i % 4 == 1:
            # Pattern 2: Counting sequence
            chunks.append(bytes(range(i % 256, (i % 256) + (chunk_size % 256))) * (chunk_size // 256 + 1))
        elif i % 4 == 2:
            # Pattern 3: Alternating bytes
            chunks.append(bytes([i % 256, (i + 1) % 256] * (chunk_size // 2)))
        else:
            # Pattern 4: Random data
            chunks.append(random.randbytes(chunk_size))
            
    return b''.join(chunks)


def demo_basic_usage(logger):
    """Demonstrate basic cache usage with small content."""
    logger.info("=== Basic Usage Demo ===")
    
    # Create cache with default settings
    cache = TieredCacheManager()
    logger.info("Created cache with default settings")
    
    # Create some test content
    small_content = create_sample_content(5)  # 5KB
    logger.info(f"Created 5KB test content: {small_content[:20]}...")
    
    # Store in cache
    key = "test_small_content"
    start_time = time.time()
    cache.put(key, small_content)
    put_time = time.time() - start_time
    logger.info(f"Stored content with key '{key}' in {put_time:.6f} seconds")
    
    # First retrieval (should be from memory)
    start_time = time.time()
    retrieved = cache.get(key)
    first_get_time = time.time() - start_time
    logger.info(f"First retrieval took {first_get_time:.6f} seconds")
    
    # Second retrieval (should be faster)
    start_time = time.time()
    retrieved = cache.get(key)
    second_get_time = time.time() - start_time
    logger.info(f"Second retrieval took {second_get_time:.6f} seconds")
    
    # Verify content integrity
    if retrieved == small_content:
        logger.info("Content integrity verified ✓")
    else:
        logger.error("Content integrity check failed!")
        
    # Print cache stats
    stats = cache.get_stats()
    logger.info(f"Memory cache utilization: {stats['memory_cache']['utilization']:.1%}")
    logger.info(f"Disk cache utilization: {stats['disk_cache']['utilization']:.1%}")
    logger.info(f"Hit rate: {stats['hit_rate']:.1%}")
    
    return {
        "put_time": put_time,
        "first_get_time": first_get_time,
        "second_get_time": second_get_time,
        "speedup": first_get_time / second_get_time if second_get_time > 0 else float('inf')
    }


def demo_tiered_access(logger):
    """Demonstrate tiered access with automatic promotion/demotion."""
    logger.info("\n=== Tiered Access Demo ===")
    
    # Create cache with small memory limit to force tier movements
    config = {
        'memory_cache_size': 50 * 1024,  # 50KB memory cache
        'local_cache_size': 10 * 1024 * 1024,  # 10MB disk cache
        'local_cache_path': os.path.expanduser('~/.ipfs_example_cache'),
        'max_item_size': 20 * 1024,  # Items up to 20KB go to memory
        'min_access_count': 2,  # Items need 2+ accesses to stay in memory
    }
    cache = TieredCacheManager(config=config)
    logger.info("Created cache with 50KB memory / 10MB disk configuration")
    
    # Create various sizes of content
    content_sizes = [5, 15, 30, 45]  # in KB
    contents = {}
    retrieval_times = {}
    
    for size in content_sizes:
        key = f"content_{size}kb"
        contents[key] = create_sample_content(size)
        
        # Store content
        cache.put(key, contents[key])
        logger.info(f"Stored {size}KB content with key '{key}'")
        
        # Track which tier it should be in
        expected_tier = "memory" if size <= 20 else "disk"
        logger.info(f"Expected to be in {expected_tier} tier")
        
        # Check actual location
        in_memory = key in cache.memory_cache
        in_disk = key in cache.disk_cache.index
        actual_tiers = []
        if in_memory:
            actual_tiers.append("memory")
        if in_disk:
            actual_tiers.append("disk")
        logger.info(f"Actually in tiers: {', '.join(actual_tiers)}")
        
        # First access
        start_time = time.time()
        _ = cache.get(key)
        first_time = time.time() - start_time
        
        # Second access
        start_time = time.time()
        _ = cache.get(key)
        second_time = time.time() - start_time
        
        retrieval_times[key] = {
            "first": first_time,
            "second": second_time,
            "ratio": first_time / second_time if second_time > 0 else float('inf')
        }
        
        logger.info(f"Access times - First: {first_time:.6f}s, Second: {second_time:.6f}s, " 
                   f"Speedup: {retrieval_times[key]['ratio']:.1f}x")
                   
    # Verify cache stats for tier distribution
    stats = cache.get_stats()
    memory_items = stats['memory_cache']['item_count']
    disk_items = stats['disk_cache']['entry_count']
    logger.info(f"Final cache state - Memory: {memory_items} items, Disk: {disk_items} items")
    
    # Test eviction by storing large content
    large_content = create_sample_content(100)  # 100KB (exceeds memory cache)
    cache.put("large_content", large_content)
    logger.info("Added 100KB content to trigger eviction")
    
    # Check what was evicted
    for size in content_sizes:
        key = f"content_{size}kb"
        in_memory = key in cache.memory_cache
        logger.info(f"After eviction: '{key}' is{'' if in_memory else ' not'} in memory cache")
    
    return retrieval_times


def demo_memory_mapping(logger):
    """Demonstrate memory-mapped file access for large content."""
    logger.info("\n=== Memory Mapping Demo ===")
    
    # Create cache with default settings
    cache = TieredCacheManager()
    
    # Create a relatively large file
    large_content = create_sample_content(1000)  # 1MB
    logger.info("Created 1MB test content")
    
    # Store in cache
    cache.put("large_file", large_content)
    logger.info("Stored large content in cache")
    
    # Regular access timing
    start_time = time.time()
    _ = cache.get("large_file")
    regular_time = time.time() - start_time
    logger.info(f"Regular access took {regular_time:.6f} seconds")
    
    # Mmap access timing
    start_time = time.time()
    mmap_obj = cache.get_mmap("large_file")
    mmap_init_time = time.time() - start_time
    logger.info(f"Memory-map initialization took {mmap_init_time:.6f} seconds")
    
    # Read a chunk via mmap
    start_time = time.time()
    _ = mmap_obj[1024:2048]  # Read 1KB at offset 1KB
    mmap_read_time = time.time() - start_time
    logger.info(f"Memory-map chunk read took {mmap_read_time:.6f} seconds")
    
    # Random access timing comparison
    random_positions = [random.randint(0, len(large_content) - 1024) for _ in range(10)]
    
    # Regular random access (needs to load entire content first)
    start = time.time()
    for pos in random_positions:
        _ = large_content[pos:pos+1024]
    regular_random_time = (time.time() - start) / len(random_positions)
    logger.info(f"Regular random access (avg): {regular_random_time:.6f} seconds per 1KB chunk")
    
    # Mmap random access
    start = time.time()
    for pos in random_positions:
        _ = mmap_obj[pos:pos+1024]
    mmap_random_time = (time.time() - start) / len(random_positions)
    logger.info(f"Memory-map random access (avg): {mmap_random_time:.6f} seconds per 1KB chunk")
    
    # Speed comparison
    speedup = regular_random_time / mmap_random_time if mmap_random_time > 0 else float('inf')
    logger.info(f"Memory mapping provides {speedup:.1f}x speedup for random access")
    
    return {
        "regular_access": regular_time,
        "mmap_init": mmap_init_time,
        "mmap_read": mmap_read_time,
        "regular_random": regular_random_time,
        "mmap_random": mmap_random_time,
        "random_speedup": speedup
    }


def demo_cache_stats(logger):
    """Demonstrate cache statistics collection and analysis."""
    logger.info("\n=== Cache Statistics Demo ===")
    
    # Create cache with default settings
    cache = TieredCacheManager()
    
    # Create varied content with different access patterns
    for i in range(10):
        key = f"stats_item_{i}"
        # Varied sizes from 1KB to 10KB
        size = (i + 1) * 1024
        content = create_sample_content(size // 1024)
        cache.put(key, content, {"type": "test", "index": i})
        logger.info(f"Added item {i} ({size} bytes)")
        
        # Access with different patterns
        access_count = i % 5 + 1  # 1 to 5 accesses
        for _ in range(access_count):
            cache.get(key)
            time.sleep(0.01)  # Small delay
    
    # Get and display stats
    stats = cache.get_stats()
    
    logger.info("Cache Statistics Summary:")
    logger.info(f"- Total items: {stats['total_items']}")
    logger.info(f"- Memory cache utilization: {stats['memory_cache']['utilization']:.1%}")
    logger.info(f"- Disk cache utilization: {stats['disk_cache']['utilization']:.1%}")
    logger.info(f"- Hit rate: {stats['hit_rate']:.1%}")
    logger.info(f"- Memory hits: {stats['hits']['memory']}")
    logger.info(f"- Disk hits: {stats['hits']['disk']}")
    logger.info(f"- Misses: {stats['hits']['miss']}")
    
    # Memory cache distribution
    logger.info("\nMemory Cache Tier:")
    logger.info(f"- T1 (recent) items: {stats['memory_cache']['T1']['count']}")
    logger.info(f"- T2 (frequent) items: {stats['memory_cache']['T2']['count']}")
    logger.info(f"- Ghost entries (B1+B2): {stats['memory_cache']['ghost_entries']['B1'] + stats['memory_cache']['ghost_entries']['B2']}")
    logger.info(f"- Target balance (p): {stats['memory_cache']['target_size']['p_percent']:.1%}")
    
    return stats


def main():
    """Main function demonstrating tiered cache usage."""
    parser = argparse.ArgumentParser(description="Tiered cache demo")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    
    logger = setup_logging(level=logging.DEBUG if args.debug else logging.INFO)
    logger.info("Starting tiered cache demonstration")
    
    # Run demonstration scenarios
    try:
        # Basic usage demonstration
        basic_results = demo_basic_usage(logger)
        
        # Tiered access demonstration
        tiered_results = demo_tiered_access(logger)
        
        # Memory mapping demonstration
        mmap_results = demo_memory_mapping(logger)
        
        # Cache statistics demonstration
        stats_results = demo_cache_stats(logger)
        
        # Display summary results
        logger.info("\n=== Demonstration Summary ===")
        logger.info(f"Basic usage speedup: {basic_results['speedup']:.1f}x")
        logger.info(f"Memory mapping random access speedup: {mmap_results['random_speedup']:.1f}x")
        logger.info(f"Overall cache hit rate: {stats_results['hit_rate']:.1%}")
        
    except Exception as e:
        logger.exception(f"Demonstration failed: {e}")
        return 1
        
    logger.info("Tiered cache demonstration completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())