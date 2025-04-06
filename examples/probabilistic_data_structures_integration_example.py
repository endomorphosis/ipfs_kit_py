#!/usr/bin/env python3
"""
Integration example showcasing the use of probabilistic data structures in IPFS Kit.

This example demonstrates:
1. Using probabilistic data structures for IPFS content management
2. Integrating with the tiered cache system for efficient access pattern tracking
3. Building a real-time content dashboard with minimal memory overhead
4. Scaling to handle millions of CIDs while keeping memory usage low

Probabilistic data structures provide significant memory savings for large-scale
IPFS deployments while maintaining mathematically bounded error rates.
"""

import os
import sys
import time
import random
import hashlib
import tempfile
import shutil
from collections import Counter
import argparse
import logging

# Import IPFS Kit if available
try:
    from ipfs_kit_py.ipfs_kit import IPFSKit
    from ipfs_kit_py.tiered_cache import TieredCacheManager
    from ipfs_kit_py.cache.probabilistic_data_structures import (
        ProbabilisticDataStructureManager,
        BloomFilter,
        HyperLogLog,
        CountMinSketch,
        CuckooFilter,
        MinHash,
        TopK
    )
    IPFS_KIT_AVAILABLE = True
except ImportError:
    IPFS_KIT_AVAILABLE = False
    print("IPFS Kit not installed. Running in simulation mode.")


def setup_logging(level=logging.INFO):
    """Set up logging configuration."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def generate_random_cid(prefix="Qm"):
    """Generate a random CID-like string for testing."""
    random_bytes = os.urandom(32)
    hash_hex = hashlib.sha256(random_bytes).hexdigest()
    return f"{prefix}{hash_hex[:44]}"


def create_test_content(size_kb=10):
    """Create random content of specified size in KB."""
    return os.urandom(size_kb * 1024)


def simulate_content_access(cids, simulation_params):
    """Simulate realistic content access patterns.
    
    Args:
        cids: List of CIDs to simulate access for
        simulation_params: Parameters controlling the simulation
        
    Returns:
        Tuple of (access_sequence, true_frequencies)
    """
    logger = logging.getLogger(__name__)
    logger.info("Simulating content access patterns...")
    
    total_accesses = simulation_params.get('total_accesses', 100000)
    zipf_param = simulation_params.get('zipf_param', 1.2)
    temporal_locality = simulation_params.get('temporal_locality', 0.7)
    
    # Try using numpy for Zipfian distribution if available
    try:
        import numpy as np
        # Generate ranks with Zipfian distribution
        ranks = np.random.zipf(zipf_param, total_accesses)
        # Convert ranks to indices within range of CIDs
        indices = [min(len(cids) - 1, rank % len(cids)) for rank in ranks]
    except ImportError:
        # Fallback to approximation using Pareto
        logger.info("Numpy not available, using Pareto approximation for Zipfian distribution")
        indices = []
        for _ in range(total_accesses):
            # Approximate Zipfian with Pareto distribution
            rank = min(len(cids) - 1, int(random.paretovariate(zipf_param - 1)))
            indices.append(rank)
    
    # Apply temporal locality (recent items are more likely to be accessed again)
    if temporal_locality > 0:
        logger.info(f"Applying temporal locality factor: {temporal_locality}")
        recent_items = []  # Queue of recently accessed items
        recent_capacity = 100  # Size of recent items queue
        
        access_sequence = []
        for i in range(total_accesses):
            if random.random() < temporal_locality and recent_items:
                # Choose from recent items
                cid = random.choice(recent_items)
                access_sequence.append(cid)
            else:
                # Choose using Zipfian distribution
                cid = cids[indices[i % len(indices)]]
                access_sequence.append(cid)
            
            # Update recent items queue
            if cid in recent_items:
                recent_items.remove(cid)  # Move to front of queue
            recent_items.insert(0, cid)
            if len(recent_items) > recent_capacity:
                recent_items.pop()  # Remove oldest
    else:
        # Simple Zipfian distribution without temporal effects
        access_sequence = [cids[i] for i in indices]
    
    # Count actual frequencies
    true_frequencies = Counter(access_sequence)
    
    logger.info(f"Generated {total_accesses} access events for {len(set(access_sequence))} unique CIDs")
    
    return access_sequence, true_frequencies


def setup_probabilistic_data_structures():
    """Set up a manager with all probabilistic data structures.
    
    Returns:
        ProbabilisticDataStructureManager instance
    """
    # Create the manager
    manager = ProbabilisticDataStructureManager()
    
    # Add a Bloom filter for content existence checks
    manager.create_bloom_filter(
        name="content_filter",
        capacity=1_000_000,  # Support up to 1M items
        false_positive_rate=0.01  # 1% false positive rate
    )
    
    # Add a HyperLogLog for unique content counting
    manager.create_hyperloglog(
        name="unique_counter",
        precision=14  # ~0.8% error with ~20KB memory
    )
    
    # Add a Count-Min Sketch for frequency estimation
    manager.create_count_min_sketch(
        name="content_frequency",
        width=2000,
        depth=5
    )
    
    # Add a Cuckoo filter for content that needs deletion support
    manager.create_cuckoo_filter(
        name="recent_content",
        capacity=10000,
        fingerprint_size=16
    )
    
    # Add a TopK tracker for popular content
    manager.create_topk(
        name="popular_content",
        k=100,  # Track top 100 items
        width=2000,
        depth=5
    )
    
    return manager


def demo_content_tracking(manager, cids, access_sequence, true_frequencies):
    """Demonstrate tracking content with probabilistic data structures.
    
    Args:
        manager: ProbabilisticDataStructureManager instance
        cids: List of all CIDs
        access_sequence: Sequence of CID accesses
        true_frequencies: True access frequencies for comparison
        
    Returns:
        Results dictionary with performance metrics
    """
    logger = logging.getLogger(__name__)
    logger.info("=== Content Tracking Demonstration ===")
    
    # Get references to structures
    bloom = manager.get_structure("content_filter")
    hll = manager.get_structure("unique_counter")
    cms = manager.get_structure("content_frequency")
    cuckoo = manager.get_structure("recent_content")
    topk = manager.get_structure("popular_content")
    
    # Process the access sequence
    logger.info(f"Processing {len(access_sequence)} access events...")
    start_time = time.time()
    
    for i, cid in enumerate(access_sequence):
        # Add to all structures
        bloom.add(cid)
        hll.add(cid)
        cms.add(cid)
        cuckoo.add(cid)
        topk.add(cid)
        
        # Periodically log progress
        if (i+1) % 10000 == 0:
            elapsed = time.time() - start_time
            rate = (i+1) / elapsed
            logger.info(f"Processed {i+1} events in {elapsed:.2f}s ({rate:.0f} events/s)")
    
    total_time = time.time() - start_time
    logger.info(f"Completed processing in {total_time:.2f}s")
    
    # Calculate memory usage
    memory_usage = {
        "bloom": bloom.get_info()["memory_usage_bytes"] / 1024,  # KB
        "hll": hll.get_info()["memory_usage_bytes"] / 1024,
        "cms": cms.get_info()["memory_usage_bytes"] / 1024,
        "cuckoo": cuckoo.get_info()["memory_usage_bytes"] / 1024,
        "topk": topk.get_info()["memory_usage_bytes"] / 1024,
        "total": sum(
            structure.get_info()["memory_usage_bytes"]
            for structure in manager.structures.values()
        ) / 1024
    }
    
    # For comparison, calculate memory usage of exact data structures
    exact_counter_size = sum(
        sys.getsizeof(k) + sys.getsizeof(v)
        for k, v in true_frequencies.items()
    ) / 1024  # KB
    
    unique_cids = set(access_sequence)
    exact_set_size = sum(sys.getsizeof(cid) for cid in unique_cids) / 1024  # KB
    
    exact_memory = {
        "counter": exact_counter_size,
        "set": exact_set_size,
        "total": exact_counter_size + exact_set_size
    }
    
    # Analyze accuracy
    # 1. Check HyperLogLog accuracy
    true_unique = len(unique_cids)
    estimated_unique = hll.count()
    hll_error = abs(estimated_unique - true_unique) / true_unique * 100
    
    # 2. Check frequency estimation accuracy
    # Sample a few CIDs with different frequencies
    sample_cids = []
    
    # Get top 5 frequent CIDs
    top_cids = [cid for cid, _ in true_frequencies.most_common(5)]
    sample_cids.extend(top_cids)
    
    # Get 5 medium frequency CIDs
    medium_cids = [cid for cid, _ in true_frequencies.most_common(50)[20:25]]
    sample_cids.extend(medium_cids)
    
    # Get 5 low frequency CIDs
    low_cids = [cid for cid, _ in true_frequencies.most_common()[len(true_frequencies)//2:len(true_frequencies)//2+5]]
    sample_cids.extend(low_cids)
    
    frequency_errors = []
    for cid in sample_cids:
        true_freq = true_frequencies[cid]
        est_freq = cms.estimate_count(cid)
        error = (est_freq - true_freq) / true_freq * 100 if true_freq > 0 else 0
        frequency_errors.append((cid, true_freq, est_freq, error))
    
    # 3. Check TopK accuracy
    topk_items = dict(topk.get_top_k())
    true_top = dict(true_frequencies.most_common(len(topk_items)))
    
    # Calculate precision and recall
    true_top_set = set(true_top.keys())
    topk_set = set(topk_items.keys())
    intersection = true_top_set.intersection(topk_set)
    
    precision = len(intersection) / len(topk_set) if topk_set else 0
    recall = len(intersection) / len(true_top_set) if true_top_set else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    # 4. Check Bloom filter false positive rate
    # Generate random CIDs that weren't in the dataset
    test_cids = [generate_random_cid() for _ in range(1000)]
    false_positives = sum(1 for cid in test_cids if cid in bloom)
    false_positive_rate = false_positives / len(test_cids) * 100
    
    # Display results
    logger.info("\nPerformance Results:")
    logger.info(f"Processing rate: {len(access_sequence) / total_time:.0f} events/second")
    
    logger.info("\nMemory Usage (KB):")
    for name, usage in memory_usage.items():
        logger.info(f"  {name:10}: {usage:.2f} KB")
    
    logger.info("\nExact Data Structure Memory (KB):")
    for name, usage in exact_memory.items():
        logger.info(f"  {name:10}: {usage:.2f} KB")
    
    logger.info(f"\nMemory savings: {(1 - memory_usage['total'] / exact_memory['total']) * 100:.1f}%")
    
    logger.info("\nAccuracy Metrics:")
    logger.info(f"  Unique CIDs: True={true_unique}, Estimated={estimated_unique}, Error={hll_error:.2f}%")
    logger.info(f"  TopK accuracy: Precision={precision:.2f}, Recall={recall:.2f}, F1={f1:.2f}")
    logger.info(f"  Bloom filter false positive rate: {false_positive_rate:.2f}%")
    
    logger.info("\nFrequency Estimation Samples:")
    logger.info(f"{'CID':20} {'True':>10} {'Estimated':>10} {'Error %':>10}")
    logger.info("-" * 60)
    for cid, true_freq, est_freq, error in frequency_errors[:5]:
        logger.info(f"{cid[:17]}... {true_freq:10d} {est_freq:10d} {error:10.2f}")
    
    # Create results dictionary
    results = {
        "processing_time": total_time,
        "processing_rate": len(access_sequence) / total_time,
        "memory_usage": memory_usage,
        "exact_memory": exact_memory,
        "memory_savings": (1 - memory_usage['total'] / exact_memory['total']) * 100,
        "accuracy": {
            "hll_error": hll_error,
            "topk_precision": precision,
            "topk_recall": recall,
            "topk_f1": f1,
            "bloom_false_positive_rate": false_positive_rate
        }
    }
    
    return results


def demo_tiered_cache_integration():
    """Demonstrate integration with tiered cache system.
    
    Returns:
        Results dictionary
    """
    logger = logging.getLogger(__name__)
    logger.info("=== Tiered Cache Integration Demonstration ===")
    
    if not IPFS_KIT_AVAILABLE:
        logger.info("IPFS Kit not available. Skipping this demonstration.")
        return None
    
    # Create a temporary directory for the cache
    cache_dir = tempfile.mkdtemp()
    
    try:
        # Configure the tiered cache with probabilistic data structures
        cache_config = {
            'memory_cache_size': 10 * 1024 * 1024,  # 10MB memory cache
            'local_cache_size': 50 * 1024 * 1024,   # 50MB disk cache
            'local_cache_path': cache_dir,
            'max_item_size': 5 * 1024 * 1024,       # 5MB max item size for memory
            'min_access_count': 2,                  # Promote to memory after 2 accesses
            'use_probabilistic_structures': True     # Enable probabilistic data structures
        }
        
        # Create the cache manager
        cache = TieredCacheManager(config=cache_config)
        logger.info("Created tiered cache with probabilistic data structures enabled")
        
        # Get the PDS manager
        pds_manager = cache.get_probabilistic_data_structures()
        
        # Check if PDS manager exists
        if pds_manager is None:
            logger.error("PDS manager not available. Please enable probabilistic data structures.")
            return None
        
        # Generate test data - 100 content items with varying sizes
        logger.info("Generating test content...")
        cids = [generate_random_cid() for _ in range(100)]
        contents = {cid: create_test_content(size_kb=random.randint(10, 500)) for cid in cids}
        
        # Simulate access patterns
        logger.info("Simulating access patterns...")
        simulation_params = {
            'total_accesses': 50000,
            'zipf_param': 1.2,
            'temporal_locality': 0.7
        }
        access_sequence, true_frequencies = simulate_content_access(cids, simulation_params)
        
        # Process the access sequence through the cache
        logger.info("Processing access sequence through cache...")
        hits = {'memory': 0, 'disk': 0}
        misses = 0
        start_time = time.time()
        
        for i, cid in enumerate(access_sequence):
            # Get content through cache
            result = cache.get(cid)
            
            if result is None:
                # Cache miss - add content to cache
                cache.put(cid, contents[cid], metadata={
                    'size': len(contents[cid]),
                    'cid': cid,
                    'created_at': time.time()
                })
                misses += 1
            else:
                # Cache hit - update stats
                if result.get('source') == 'memory':
                    hits['memory'] += 1
                elif result.get('source') == 'disk':
                    hits['disk'] += 1
            
            # Periodically print progress
            if (i+1) % 10000 == 0:
                elapsed = time.time() - start_time
                logger.info(f"Processed {i+1} accesses in {elapsed:.2f}s " 
                            f"({(i+1)/elapsed:.0f} ops/s)")
                logger.info(f"Hits: Memory={hits['memory']}, Disk={hits['disk']}, Misses={misses}")
        
        total_time = time.time() - start_time
        logger.info(f"Completed processing in {total_time:.2f}s")
        
        # Calculate cache statistics
        total_accesses = len(access_sequence)
        memory_hit_rate = hits['memory'] / total_accesses * 100
        disk_hit_rate = hits['disk'] / total_accesses * 100
        overall_hit_rate = (hits['memory'] + hits['disk']) / total_accesses * 100
        miss_rate = misses / total_accesses * 100
        
        logger.info("\nCache Performance:")
        logger.info(f"Total accesses: {total_accesses}")
        logger.info(f"Memory hits: {hits['memory']} ({memory_hit_rate:.2f}%)")
        logger.info(f"Disk hits: {hits['disk']} ({disk_hit_rate:.2f}%)")
        logger.info(f"Misses: {misses} ({miss_rate:.2f}%)")
        logger.info(f"Overall hit rate: {overall_hit_rate:.2f}%")
        
        # Get PDS usage statistics
        if pds_manager.has_structure("content_frequency"):
            cms = pds_manager.get_structure("content_frequency")
            
            logger.info("\nTopK Content Items:")
            if pds_manager.has_structure("popular_content"):
                topk = pds_manager.get_structure("popular_content")
                top_items = topk.get_top_k(10)  # Get top 10
                
                logger.info(f"{'CID':45} {'Estimated Access Count':>25}")
                logger.info("-" * 70)
                for cid, count in top_items:
                    true_count = true_frequencies.get(cid, 0)
                    error = (count - true_count) / true_count * 100 if true_count > 0 else 0
                    logger.info(f"{cid} {count:25d} (true: {true_count}, error: {error:.2f}%)")
        
        # Get unique content count
        if pds_manager.has_structure("unique_counter"):
            hll = pds_manager.get_structure("unique_counter")
            unique_count = hll.count()
            true_unique = len(set(access_sequence))
            error = abs(unique_count - true_unique) / true_unique * 100
            logger.info(f"\nUnique content items: {unique_count} (true: {true_unique}, error: {error:.2f}%)")
        
        # Memory usage comparison
        pds_memory = sum(structure.get_info().get('memory_usage_bytes', 0) / 1024
                         for structure in pds_manager.structures.values())
        
        logger.info(f"\nProbabilistic data structures memory usage: {pds_memory:.2f} KB")
        
        # Create results dictionary
        results = {
            "processing_time": total_time,
            "processing_rate": len(access_sequence) / total_time,
            "hit_rates": {
                "memory": memory_hit_rate,
                "disk": disk_hit_rate,
                "overall": overall_hit_rate,
                "miss": miss_rate
            },
            "pds_memory_usage": pds_memory
        }
        
        return results
        
    finally:
        # Clean up
        shutil.rmtree(cache_dir)


def demo_ipfs_kit_integration():
    """Demonstrate integration with IPFS Kit."""
    logger = logging.getLogger(__name__)
    logger.info("=== IPFS Kit Integration Demonstration ===")
    
    if not IPFS_KIT_AVAILABLE:
        logger.info("IPFS Kit not available. Skipping this demonstration.")
        return None
    
    try:
        # Initialize IPFS Kit in test mode
        kit = IPFSKit(role="leecher", test_mode=True)
        logger.info("Initialized IPFS Kit in test mode")
        
        # Create a PDS manager for content tracking
        manager = ProbabilisticDataStructureManager()
        
        # Add specialized data structures
        manager.create_bloom_filter("local_content", capacity=1000000, false_positive_rate=0.01)
        manager.create_hyperloglog("unique_content", precision=14)
        manager.create_count_min_sketch("access_frequency", width=2000, depth=5)
        manager.create_topk("popular_content", k=100, width=2000, depth=5)
        
        # Generate test content
        logger.info("Generating test content...")
        num_items = 100
        content_items = [f"Test content {i}" for i in range(num_items)]
        cids = []
        
        # Add content to IPFS
        logger.info(f"Adding {num_items} content items to IPFS...")
        for content in content_items:
            result = kit.add(content.encode())
            if result.get("success"):
                cids.append(result.get("cid"))
        
        logger.info(f"Added {len(cids)} items to IPFS")
        
        # Simulate content access with realisitc patterns
        logger.info("Simulating content access patterns...")
        simulation_params = {
            'total_accesses': 10000,
            'zipf_param': 1.3,  # More skewed popularity distribution
            'temporal_locality': 0.8  # Higher temporal locality
        }
        access_sequence, true_frequencies = simulate_content_access(cids, simulation_params)
        
        # Track access patterns using PDS manager
        logger.info("Processing access sequence with PDS manager...")
        start_time = time.time()
        
        for i, cid in enumerate(access_sequence):
            # Update all structures
            for name, structure in manager.structures.items():
                structure.add(cid)
            
            # Simulate content retrieval
            kit.cat(cid)
            
            # Periodically log progress
            if (i+1) % 1000 == 0:
                elapsed = time.time() - start_time
                logger.info(f"Processed {i+1} accesses in {elapsed:.2f}s " 
                            f"({(i+1)/elapsed:.0f} ops/s)")
        
        total_time = time.time() - start_time
        logger.info(f"Completed processing in {total_time:.2f}s")
        
        # Generate content dashboard
        logger.info("\nIPFS Content Dashboard:")
        
        # 1. Unique content count
        hll = manager.get_structure("unique_content")
        unique_count = hll.count()
        true_unique = len(set(access_sequence))
        logger.info(f"Unique content items: {unique_count} (true: {true_unique})")
        
        # 2. Most popular content
        topk = manager.get_structure("popular_content")
        popular_items = topk.get_top_k(10)  # Top 10
        
        logger.info("\nMost Popular Content:")
        logger.info(f"{'CID':45} {'Access Count':>15}")
        logger.info("-" * 65)
        for cid, count in popular_items:
            logger.info(f"{cid} {count:15d}")
        
        # 3. Access frequency distribution
        cms = manager.get_structure("access_frequency")
        
        # Sample frequencies at different percentiles
        sample_cids = []
        # Top 10%
        top_10_percent = int(len(cids) * 0.1)
        if top_10_percent > 0:
            sample_cids.extend(random.sample(cids[:top_10_percent], min(5, top_10_percent)))
        
        # Middle 50%
        middle_start = int(len(cids) * 0.25)
        middle_end = int(len(cids) * 0.75)
        middle_range = cids[middle_start:middle_end]
        if len(middle_range) > 0:
            sample_cids.extend(random.sample(middle_range, min(5, len(middle_range))))
        
        # Bottom 10%
        bottom_10_percent = int(len(cids) * 0.9)
        bottom_range = cids[bottom_10_percent:]
        if len(bottom_range) > 0:
            sample_cids.extend(random.sample(bottom_range, min(5, len(bottom_range))))
        
        logger.info("\nAccess Frequency Distribution:")
        logger.info(f"{'Percentile':15} {'CID':45} {'Access Count':>15}")
        logger.info("-" * 80)
        
        # Sort CIDs by frequency
        sorted_cids = sorted(cids, key=lambda x: true_frequencies.get(x, 0), reverse=True)
        
        # Display frequencies at different percentiles
        percentiles = [0, 25, 50, 75, 90, 99]
        for p in percentiles:
            idx = min(int(len(sorted_cids) * p / 100), len(sorted_cids) - 1)
            if idx < len(sorted_cids):
                cid = sorted_cids[idx]
                est_count = cms.estimate_count(cid)
                true_count = true_frequencies.get(cid, 0)
                logger.info(f"{p:15d}% {cid} {est_count:15d} (true: {true_count})")
        
        # 4. Memory usage statistics
        total_pds_memory = sum(structure.get_info().get('memory_usage_bytes', 0) 
                               for structure in manager.structures.values())
        
        logger.info(f"\nTotal memory usage for content analytics: {total_pds_memory / 1024:.2f} KB")
        
        # Create results dictionary
        results = {
            "processing_time": total_time,
            "processing_rate": len(access_sequence) / total_time,
            "unique_content": {
                "estimated": unique_count,
                "true": true_unique,
                "error": abs(unique_count - true_unique) / true_unique * 100
            },
            "memory_usage": total_pds_memory / 1024,  # KB
            "popular_content": popular_items
        }
        
        return results
    
    except Exception as e:
        logger.exception(f"IPFS Kit integration demonstration failed: {e}")
        return None


def visualize_results(results):
    """Create visualizations of results if matplotlib is available."""
    logger = logging.getLogger(__name__)
    
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        
        logger.info("Creating visualizations...")
        
        # Create figure with multiple subplots
        plt.figure(figsize=(15, 10))
        
        # Plot 1: Memory usage comparison
        if 'content_tracking' in results and 'memory_usage' in results['content_tracking']:
            mem_data = results['content_tracking']
            pds_memory = mem_data['memory_usage']
            exact_memory = mem_data['exact_memory']
            
            plt.subplot(2, 2, 1)
            
            # Create grouped bar chart
            structures = ['bloom', 'hll', 'cms', 'cuckoo', 'topk']
            pds_values = [pds_memory.get(s, 0) for s in structures]
            
            x = np.arange(len(structures))
            width = 0.35
            
            plt.bar(x, pds_values, width, label='Probabilistic')
            
            # Add exact comparison where applicable
            if 'counter' in exact_memory:
                plt.bar([2], [exact_memory['counter']], width, alpha=0.5, label='Exact Counter')
            if 'set' in exact_memory:
                plt.bar([0], [exact_memory['set']], width, alpha=0.5, label='Exact Set')
            
            plt.xlabel('Data Structure')
            plt.ylabel('Memory Usage (KB)')
            plt.title('Memory Usage Comparison')
            plt.xticks(x, structures)
            plt.legend()
            
            # Add total memory text
            plt.text(0.5, 0.9, 
                    f"Total PDS: {pds_memory['total']:.1f} KB\nExact: {exact_memory['total']:.1f} KB\nSavings: {mem_data['memory_savings']:.1f}%", 
                    horizontalalignment='center',
                    verticalalignment='center',
                    transform=plt.gca().transAxes,
                    bbox=dict(facecolor='white', alpha=0.8))
        
        # Plot 2: Accuracy metrics
        if 'content_tracking' in results and 'accuracy' in results['content_tracking']:
            acc_data = results['content_tracking']['accuracy']
            
            plt.subplot(2, 2, 2)
            
            metrics = ['HLL Error', 'Bloom FP Rate', 'TopK Precision', 'TopK Recall', 'TopK F1']
            values = [
                acc_data.get('hll_error', 0),
                acc_data.get('bloom_false_positive_rate', 0),
                acc_data.get('topk_precision', 0) * 100,
                acc_data.get('topk_recall', 0) * 100,
                acc_data.get('topk_f1', 0) * 100
            ]
            
            plt.bar(metrics, values)
            plt.xlabel('Metric')
            plt.ylabel('Value (%)')
            plt.title('Accuracy Metrics')
            plt.xticks(rotation=45)
            plt.ylim(0, 100)
            
            # Add horizontal line at 1% for reference
            plt.axhline(y=1, color='r', linestyle='--', alpha=0.7, label='1% threshold')
            plt.legend()
        
        # Plot 3: Cache hit rates
        if 'tiered_cache' in results and 'hit_rates' in results['tiered_cache']:
            hit_data = results['tiered_cache']['hit_rates']
            
            plt.subplot(2, 2, 3)
            
            categories = ['Memory Hits', 'Disk Hits', 'Overall Hits', 'Misses']
            values = [
                hit_data.get('memory', 0),
                hit_data.get('disk', 0),
                hit_data.get('overall', 0),
                hit_data.get('miss', 0)
            ]
            
            plt.bar(categories, values)
            plt.xlabel('Category')
            plt.ylabel('Rate (%)')
            plt.title('Cache Performance')
            plt.ylim(0, 100)
        
        # Plot 4: Processing rate
        plt.subplot(2, 2, 4)
        
        demo_types = []
        rates = []
        
        if 'content_tracking' in results:
            demo_types.append('Content Tracking')
            rates.append(results['content_tracking'].get('processing_rate', 0))
            
        if 'tiered_cache' in results:
            demo_types.append('Tiered Cache')
            rates.append(results['tiered_cache'].get('processing_rate', 0))
            
        if 'ipfs_kit' in results:
            demo_types.append('IPFS Kit')
            rates.append(results['ipfs_kit'].get('processing_rate', 0))
        
        plt.bar(demo_types, rates)
        plt.xlabel('Demonstration')
        plt.ylabel('Processing Rate (events/second)')
        plt.title('Performance Comparison')
        
        plt.tight_layout()
        plt.savefig('probabilistic_data_structures_results.png')
        logger.info("Visualization saved as 'probabilistic_data_structures_results.png'")
        
    except ImportError:
        logger.info("Matplotlib not available. Skipping visualizations.")


def main():
    """Main function running all demonstrations."""
    parser = argparse.ArgumentParser(description="Probabilistic Data Structures Integration Example")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--cids", type=int, default=1000, help="Number of CIDs to generate")
    parser.add_argument("--accesses", type=int, default=100000, help="Number of access events to simulate")
    args = parser.parse_args()
    
    logger = setup_logging(level=logging.DEBUG if args.debug else logging.INFO)
    logger.info("Starting Probabilistic Data Structures Integration Example")
    
    # Generate test data
    logger.info(f"Generating {args.cids} test CIDs...")
    cids = [generate_random_cid() for _ in range(args.cids)]
    
    # Simulate access patterns
    simulation_params = {
        'total_accesses': args.accesses,
        'zipf_param': 1.2,
        'temporal_locality': 0.7
    }
    access_sequence, true_frequencies = simulate_content_access(cids, simulation_params)
    
    # Set up probabilistic data structures
    logger.info("Setting up probabilistic data structures...")
    manager = setup_probabilistic_data_structures()
    
    # Run demonstrations and collect results
    results = {}
    
    try:
        # Basic content tracking demo
        ct_results = demo_content_tracking(manager, cids, access_sequence, true_frequencies)
        results['content_tracking'] = ct_results
        
        # Tiered cache integration demo
        tc_results = demo_tiered_cache_integration()
        if tc_results:
            results['tiered_cache'] = tc_results
        
        # IPFS Kit integration demo
        ik_results = demo_ipfs_kit_integration()
        if ik_results:
            results['ipfs_kit'] = ik_results
        
        # Create visualizations
        visualize_results(results)
        
        # Display summary
        logger.info("\n=== Demonstration Summary ===")
        logger.info("Probabilistic data structures provide significant memory savings")
        logger.info("while maintaining mathematically bounded error rates.")
        
        if 'content_tracking' in results:
            logger.info(f"Memory savings: {results['content_tracking']['memory_savings']:.1f}%")
            logger.info(f"Processing rate: {results['content_tracking']['processing_rate']:.0f} events/second")
        
        logger.info("\nBenefits for IPFS content management:")
        logger.info("1. Efficient tracking of millions of CIDs with minimal memory")
        logger.info("2. Real-time content popularity analytics")
        logger.info("3. Optimized caching decisions based on access patterns")
        logger.info("4. Scalable content tracking even on resource-constrained devices")
        
    except Exception as e:
        logger.exception(f"Demonstration failed: {e}")
        return 1
    
    logger.info("\nProbabilistic Data Structures Integration Example completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())