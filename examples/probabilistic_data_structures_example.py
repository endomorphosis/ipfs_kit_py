#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Example usage of Probabilistic Data Structures module.

This example demonstrates:
1. Using different probabilistic data structures for various use cases
2. Performance and memory comparisons with exact data structures
3. Applications in IPFS content management
4. Accuracy/memory tradeoffs with different parameters
5. Integration with tiered cache system
"""

import time
import random
import os
import sys
import matplotlib.pyplot as plt
import numpy as np
from typing import List, Set, Dict, Tuple, Any
from collections import Counter

# Import our probabilistic data structures module
from ipfs_kit_py.cache.probabilistic_data_structures import (
    BloomFilter,
    HyperLogLog,
    CountMinSketch,
    CuckooFilter,
    MinHash,
    TopK,
    ProbabilisticDataStructureManager,
    HashFunction
)

# For comparison with exact data structures
# Use sets, dictionaries, and counters from Python's standard library

def compare_bloom_vs_set():
    """
    Compare Bloom filter vs Python set for membership testing.
    Demonstrates space efficiency and false positive tradeoffs.
    """
    print("\n=== Bloom Filter vs. Python Set ===\n")
    
    # Parameters for experiment
    num_elements = 1_000_000  # 1 million elements
    test_elements = 100_000   # Elements to test
    false_positive_rates = [0.1, 0.01, 0.001, 0.0001]  # Different error rates
    
    # Generate test data
    members = set(f"item_{i}" for i in range(num_elements))
    non_members = set(f"item_{num_elements + i}" for i in range(test_elements))
    
    # Test set (baseline)
    print("Testing Python set (exact membership):")
    start_time = time.time()
    member_result = sum(1 for x in random.sample(list(members), test_elements) if x in members)
    non_member_result = sum(1 for x in random.sample(list(non_members), test_elements) if x in members)
    set_time = time.time() - start_time
    
    set_size = sys.getsizeof(members) / (1024 * 1024)  # Size in MB
    print(f"  Time: {set_time:.4f} seconds")
    print(f"  Memory: {set_size:.2f} MB")
    print(f"  Accuracy: 100% (exact)")
    print(f"  False positives: 0/{test_elements}")
    
    # Test Bloom filters with different false positive rates
    results = []
    for error_rate in false_positive_rates:
        print(f"\nTesting Bloom filter (error rate: {error_rate}):")
        bloom = BloomFilter(capacity=num_elements, false_positive_rate=error_rate)
        
        # Add all members
        start_time = time.time()
        for item in members:
            bloom.add(item)
        add_time = time.time() - start_time
        
        # Test members
        start_time = time.time()
        member_hits = sum(1 for x in random.sample(list(members), test_elements) if x in bloom)
        # Test non-members
        non_member_hits = sum(1 for x in random.sample(list(non_members), test_elements) if x in bloom)
        query_time = time.time() - start_time
        
        # Calculate statistics
        size_bits = bloom.size
        size_mb = size_bits / (8 * 1024 * 1024)  # Convert bits to MB
        false_positive_rate = non_member_hits / test_elements
        
        print(f"  Time (add): {add_time:.4f} seconds")
        print(f"  Time (query): {query_time:.4f} seconds")
        print(f"  Memory: {size_mb:.2f} MB")
        print(f"  Bit array size: {size_bits} bits")
        print(f"  Hash functions: {bloom.hash_count}")
        print(f"  True positives: {member_hits}/{test_elements} ({member_hits/test_elements:.2%})")
        print(f"  False positives: {non_member_hits}/{test_elements} ({false_positive_rate:.4%})")
        
        # Save results for plotting
        results.append({
            "error_rate": error_rate,
            "size_mb": size_mb,
            "false_positive_rate": false_positive_rate,
            "query_time": query_time,
        })
    
    # Create plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    
    # Plot memory usage vs. error rate
    error_rates = [r["error_rate"] for r in results]
    sizes = [r["size_mb"] for r in results]
    ax1.semilogx(error_rates, sizes, 'o-', linewidth=2, markersize=8)
    ax1.axhline(y=set_size, color='r', linestyle='--', label=f'Python Set ({set_size:.2f} MB)')
    ax1.set_xlabel('False Positive Rate')
    ax1.set_ylabel('Memory Usage (MB)')
    ax1.set_title('Memory Usage vs. Error Rate')
    ax1.grid(True)
    ax1.legend()
    
    # Plot actual vs. target error rate
    actual_fp_rates = [r["false_positive_rate"] for r in results]
    ax2.loglog(error_rates, actual_fp_rates, 'o-', linewidth=2, markersize=8, label='Actual')
    ax2.loglog(error_rates, error_rates, 'r--', label='Target')
    ax2.set_xlabel('Target False Positive Rate')
    ax2.set_ylabel('Actual False Positive Rate')
    ax2.set_title('False Positive Rate: Actual vs. Target')
    ax2.grid(True)
    ax2.legend()
    
    plt.tight_layout()
    plt.savefig('bloom_filter_comparison.png')
    print(f"\nComparison plot saved as 'bloom_filter_comparison.png'")


def cardinality_estimation_hyperloglog():
    """
    Demonstrate HyperLogLog for estimating unique element counts.
    Shows memory efficiency vs. accuracy tradeoff with different precision values.
    """
    print("\n=== HyperLogLog Cardinality Estimation ===\n")
    
    # Parameters
    max_items = 10_000_000  # 10 million
    precision_values = [10, 12, 14, 16]  # Different precision settings
    
    # Generate test data with different cardinalities
    cardinalities = [10_000, 100_000, 1_000_000, 10_000_000]
    
    # Dictionary to store results
    results = []
    
    # First, measure exact counting with set
    print("Exact counting with Python set:")
    for cardinality in cardinalities:
        data = [f"item_{random.randint(0, cardinality-1)}" for _ in range(max_items)]
        
        # Exact count using a set
        start_time = time.time()
        exact_count = len(set(data))
        exact_time = time.time() - start_time
        exact_memory = sys.getsizeof(set(data)) / (1024 * 1024)  # Size in MB
        
        print(f"  Cardinality {cardinality}: {exact_count} (took {exact_time:.4f}s, {exact_memory:.2f} MB)")
    
    # Then test HyperLogLog with different precision values
    for precision in precision_values:
        print(f"\nHyperLogLog with precision {precision}:")
        
        for cardinality in cardinalities:
            # Create a new dataset with known cardinality
            data = [f"item_{random.randint(0, cardinality-1)}" for _ in range(max_items)]
            true_count = len(set(data))
            
            # Create HyperLogLog estimator
            hll = HyperLogLog(precision=precision)
            
            # Add all items
            start_time = time.time()
            for item in data:
                hll.add(item)
            add_time = time.time() - start_time
            
            # Get the estimate
            start_time = time.time()
            estimated_count = hll.count()
            estimate_time = time.time() - start_time
            
            # Calculate error
            error_percent = abs(estimated_count - true_count) / true_count * 100
            
            # Memory usage
            memory_bytes = 2**precision  # Each register is 1 byte
            memory_kb = memory_bytes / 1024
            
            print(f"  Cardinality {cardinality}:")
            print(f"    True count: {true_count}")
            print(f"    Estimated: {estimated_count}")
            print(f"    Error: {error_percent:.2f}%")
            print(f"    Memory: {memory_kb:.2f} KB ({(memory_bytes)} bytes)")
            print(f"    Add time: {add_time:.4f}s")
            print(f"    Estimate time: {estimate_time:.4f}s")
            
            # Store results for plotting
            results.append({
                "precision": precision,
                "cardinality": cardinality,
                "true_count": true_count,
                "estimated_count": estimated_count,
                "error_percent": error_percent,
                "memory_kb": memory_kb
            })
    
    # Plot results
    plt.figure(figsize=(15, 10))
    
    # Plot 1: Error vs Precision
    plt.subplot(2, 2, 1)
    for cardinality in cardinalities:
        data = [(r["precision"], r["error_percent"]) for r in results if r["cardinality"] == cardinality]
        precisions, errors = zip(*data)
        plt.plot(precisions, errors, 'o-', label=f"Cardinality {cardinality}")
    
    plt.xlabel('Precision')
    plt.ylabel('Error (%)')
    plt.title('HyperLogLog Error vs. Precision')
    plt.grid(True)
    plt.legend()
    
    # Plot 2: Memory vs Precision
    plt.subplot(2, 2, 2)
    precisions = sorted(list(set(r["precision"] for r in results)))
    memories = [2**p / 1024 for p in precisions]  # KB
    
    plt.semilogy(precisions, memories, 'o-')
    plt.xlabel('Precision')
    plt.ylabel('Memory (KB)')
    plt.title('HyperLogLog Memory Usage vs. Precision')
    plt.grid(True)
    
    # Plot 3: Memory-Accuracy Tradeoff
    plt.subplot(2, 2, 3)
    for cardinality in cardinalities:
        data = [(r["memory_kb"], r["error_percent"]) for r in results if r["cardinality"] == cardinality]
        memories, errors = zip(*data)
        plt.loglog(memories, errors, 'o-', label=f"Cardinality {cardinality}")
    
    plt.xlabel('Memory (KB)')
    plt.ylabel('Error (%)')
    plt.title('HyperLogLog Memory-Accuracy Tradeoff')
    plt.grid(True)
    plt.legend()
    
    # Plot 4: Estimated vs True
    plt.subplot(2, 2, 4)
    for precision in precision_values:
        data = [(r["true_count"], r["estimated_count"]) for r in results if r["precision"] == precision]
        true_counts, estimated_counts = zip(*data)
        plt.loglog(true_counts, estimated_counts, 'o-', label=f"Precision {precision}")
    
    # Add perfect estimation line
    plt.loglog([min(cardinalities), max(cardinalities)], 
              [min(cardinalities), max(cardinalities)], 
              'k--', label='Perfect Estimation')
    
    plt.xlabel('True Count')
    plt.ylabel('Estimated Count')
    plt.title('HyperLogLog Estimated vs. True Count')
    plt.grid(True)
    plt.legend()
    
    plt.tight_layout()
    plt.savefig('hyperloglog_evaluation.png')
    print(f"\nHyperLogLog evaluation plot saved as 'hyperloglog_evaluation.png'")


def frequency_estimation_count_min_sketch():
    """
    Demonstrate Count-Min Sketch for frequency estimation.
    Compares memory usage vs accuracy with different parameters.
    """
    print("\n=== Count-Min Sketch Frequency Estimation ===\n")
    
    # Generate data with a Zipfian distribution (some items are much more frequent)
    def generate_zipfian_data(n, zipf_param=1.1, unique_items=1000):
        # Generate ranks following Zipf distribution
        ranks = np.random.zipf(zipf_param, n)
        # Map to a smaller range of unique items
        return [f"item_{rank % unique_items}" for rank in ranks]
    
    # Parameters
    n_items = 1_000_000  # 1 million data points
    unique_items = 10_000  # Number of unique items
    
    # Generate data
    print(f"Generating Zipfian data ({n_items} items)...")
    data = generate_zipfian_data(n_items, zipf_param=1.2, unique_items=unique_items)
    
    # Compute exact frequencies (ground truth)
    print("Computing exact frequencies...")
    start_time = time.time()
    true_counts = Counter(data)
    exact_time = time.time() - start_time
    exact_memory = sys.getsizeof(true_counts) / (1024 * 1024)  # MB
    
    # Select a few items with different frequencies to track
    items_to_track = [
        max(true_counts.items(), key=lambda x: x[1])[0],  # Most frequent
        min(true_counts.items(), key=lambda x: x[1])[0],  # Least frequent
        list(true_counts.keys())[len(true_counts) // 2],  # Median frequency
        list(true_counts.keys())[len(true_counts) // 4],  # 25th percentile
        list(true_counts.keys())[3 * len(true_counts) // 4]  # 75th percentile
    ]
    
    # Track their true frequencies
    tracked_frequencies = {item: true_counts[item] for item in items_to_track}
    print(f"Items to track: {tracked_frequencies}")
    
    print(f"\nExact counting with Counter:")
    print(f"  Time: {exact_time:.4f} seconds")
    print(f"  Memory: {exact_memory:.2f} MB")
    print(f"  Unique items: {len(true_counts)}")
    
    # Test Count-Min Sketch with different parameters
    width_values = [100, 500, 1000, 5000, 10000]
    depth_values = [3, 5, 7, 10]
    
    results = []
    
    for width in width_values:
        for depth in depth_values:
            # Create sketch with specified parameters
            cms = CountMinSketch(width=width, depth=depth)
            
            # Add all items
            start_time = time.time()
            for item in data:
                cms.add(item)
            add_time = time.time() - start_time
            
            # Estimate frequencies for tracked items
            start_time = time.time()
            estimates = {item: cms.estimate_count(item) for item in items_to_track}
            query_time = time.time() - start_time
            
            # Calculate errors
            relative_errors = {item: (estimates[item] - true_counts[item]) / true_counts[item] 
                             for item in items_to_track}
            
            # Memory usage
            memory_usage = cms.get_info()['memory_usage_bytes'] / (1024 * 1024)  # MB
            
            # Store results
            result = {
                "width": width,
                "depth": depth,
                "add_time": add_time,
                "query_time": query_time,
                "memory_mb": memory_usage,
                "estimates": estimates,
                "true_counts": {item: true_counts[item] for item in items_to_track},
                "relative_errors": relative_errors,
                "mean_error": sum(abs(e) for e in relative_errors.values()) / len(relative_errors)
            }
            results.append(result)
            
            print(f"\nCount-Min Sketch (width={width}, depth={depth}):")
            print(f"  Add time: {add_time:.4f} seconds")
            print(f"  Query time: {query_time:.4f} seconds")
            print(f"  Memory: {memory_usage:.4f} MB")
            print(f"  Estimates vs. True counts:")
            for item in items_to_track:
                print(f"    {item}: {estimates[item]} vs. {true_counts[item]} "
                     f"(error: {relative_errors[item]:.2%})")
            print(f"  Mean relative error: {result['mean_error']:.2%}")
    
    # Create plots
    plt.figure(figsize=(15, 10))
    
    # Plot 1: Memory vs Parameters
    plt.subplot(2, 2, 1)
    # Create a grid of width and depth combinations
    width_depth_grid = [(r["width"], r["depth"]) for r in results]
    memory_values = [r["memory_mb"] for r in results]
    
    # Create scatter plot
    scatter = plt.scatter([wd[0] for wd in width_depth_grid], 
                        [wd[1] for wd in width_depth_grid],
                        c=memory_values, s=100, cmap='viridis')
    plt.colorbar(scatter, label='Memory (MB)')
    
    plt.xlabel('Width')
    plt.ylabel('Depth')
    plt.title('Count-Min Sketch: Memory Usage vs. Parameters')
    plt.grid(True)
    
    # Plot 2: Error vs Parameters
    plt.subplot(2, 2, 2)
    error_values = [r["mean_error"] for r in results]
    
    scatter = plt.scatter([wd[0] for wd in width_depth_grid], 
                        [wd[1] for wd in width_depth_grid],
                        c=error_values, s=100, cmap='viridis_r')
    plt.colorbar(scatter, label='Mean Relative Error')
    
    plt.xlabel('Width')
    plt.ylabel('Depth')
    plt.title('Count-Min Sketch: Error vs. Parameters')
    plt.grid(True)
    
    # Plot 3: Memory-Error Tradeoff
    plt.subplot(2, 2, 3)
    
    for depth in depth_values:
        # Filter results for this depth
        depth_results = [r for r in results if r["depth"] == depth]
        
        # Sort by memory
        depth_results.sort(key=lambda r: r["memory_mb"])
        
        memories = [r["memory_mb"] for r in depth_results]
        errors = [r["mean_error"] for r in depth_results]
        
        plt.plot(memories, errors, 'o-', label=f"Depth {depth}")
    
    plt.axhline(y=0, color='k', linestyle='--', label='Perfect Accuracy')
    plt.xlabel('Memory (MB)')
    plt.ylabel('Mean Relative Error')
    plt.title('Count-Min Sketch: Memory-Error Tradeoff')
    plt.grid(True)
    plt.legend()
    
    # Plot 4: Comparison with exact counting
    plt.subplot(2, 2, 4)
    
    # Find best and worst configurations
    best_result = min(results, key=lambda r: r["mean_error"])
    worst_result = max(results, key=lambda r: r["mean_error"])
    
    configurations = [
        ("Counter (Exact)", {item: true_counts[item] for item in items_to_track}),
        (f"CMS (Best: w={best_result['width']}, d={best_result['depth']})", best_result["estimates"]),
        (f"CMS (Worst: w={worst_result['width']}, d={worst_result['depth']})", worst_result["estimates"])
    ]
    
    # Plot estimates vs true counts for each configuration
    for i, (name, estimates) in enumerate(configurations):
        plt.scatter(
            [true_counts[item] for item in items_to_track],
            [estimates[item] for item in items_to_track],
            label=name,
            s=100,
            alpha=0.7
        )
    
    # Perfect estimation line
    max_count = max(true_counts.values())
    plt.plot([0, max_count], [0, max_count], 'k--', label='Perfect Estimation')
    
    plt.xlabel('True Count')
    plt.ylabel('Estimated Count')
    plt.title('Count-Min Sketch: Estimated vs. True Count')
    plt.grid(True)
    plt.legend()
    
    plt.tight_layout()
    plt.savefig('count_min_sketch_evaluation.png')
    print(f"\nCount-Min Sketch evaluation plot saved as 'count_min_sketch_evaluation.png'")


def compare_cuckoo_vs_bloom():
    """
    Compare Cuckoo filter with Bloom filter for membership testing.
    Demonstrates tradeoffs in terms of memory, false positives, and deletion support.
    """
    print("\n=== Cuckoo Filter vs. Bloom Filter ===\n")
    
    # Parameters
    capacity = 1_000_000  # 1 million elements
    false_positive_rate = 0.01  # 1% false positive rate
    delete_count = 10_000  # Number of items to delete later
    
    # Generate test data (strings that will hash differently)
    items = [f"item_{i}" for i in range(capacity)]
    items_to_delete = items[:delete_count]
    
    # Create a Bloom filter
    bloom = BloomFilter(capacity=capacity, false_positive_rate=false_positive_rate)
    
    # Create a Cuckoo filter with equivalent parameters
    # For 1% false positive rate with 4-entry buckets, we need 2^8 = 256 fingerprints
    # so 8-bit fingerprints
    cuckoo = CuckooFilter(capacity=capacity, fingerprint_size=8)
    
    # Add items to Bloom filter
    print("Adding items to Bloom filter...")
    bloom_add_start = time.time()
    for item in items:
        bloom.add(item)
    bloom_add_time = time.time() - bloom_add_start
    
    # Add items to Cuckoo filter
    print("Adding items to Cuckoo filter...")
    cuckoo_add_start = time.time()
    for item in items:
        cuckoo.add(item)
    cuckoo_add_time = time.time() - cuckoo_add_start
    
    # Generate query data - mix of members and non-members
    query_members = random.sample(items, 10_000)
    query_non_members = [f"nonexistent_{i}" for i in range(10_000)]
    
    # Test Bloom filter queries
    bloom_member_start = time.time()
    bloom_true_positives = sum(1 for item in query_members if item in bloom)
    bloom_member_time = time.time() - bloom_member_start
    
    bloom_nonmember_start = time.time()
    bloom_false_positives = sum(1 for item in query_non_members if item in bloom)
    bloom_nonmember_time = time.time() - bloom_nonmember_start
    
    # Test Cuckoo filter queries
    cuckoo_member_start = time.time()
    cuckoo_true_positives = sum(1 for item in query_members if item in cuckoo)
    cuckoo_member_time = time.time() - cuckoo_member_start
    
    cuckoo_nonmember_start = time.time()
    cuckoo_false_positives = sum(1 for item in query_non_members if item in cuckoo)
    cuckoo_nonmember_time = time.time() - cuckoo_nonmember_start
    
    # Delete items from Cuckoo filter (Bloom filter cannot delete)
    print("Deleting items from Cuckoo filter...")
    delete_start = time.time()
    for item in items_to_delete:
        cuckoo.remove(item)
    delete_time = time.time() - delete_start
    
    # Test queries after deletion
    deleted_query_time = time.time()
    deleted_in_cuckoo = sum(1 for item in items_to_delete if item in cuckoo)
    deleted_in_bloom = sum(1 for item in items_to_delete if item in bloom)
    deleted_query_time = time.time() - deleted_query_time
    
    # Get memory usage
    bloom_size = bloom.get_info()["size"] / 8 / 1024 / 1024  # Convert bits to MB
    cuckoo_size = sum(len(bucket) for bucket in cuckoo.buckets) * cuckoo.fingerprint_size / 8 / 1024 / 1024  # MB
    
    # Print results
    print("\nResults:")
    print(f"Bloom Filter:")
    print(f"  Add time: {bloom_add_time:.4f}s")
    print(f"  Member query time: {bloom_member_time:.4f}s")
    print(f"  Non-member query time: {bloom_nonmember_time:.4f}s")
    print(f"  Memory usage: {bloom_size:.2f} MB")
    print(f"  True positives: {bloom_true_positives}/10000 ({bloom_true_positives/100:.2f}%)")
    print(f"  False positives: {bloom_false_positives}/10000 ({bloom_false_positives/100:.2f}%)")
    print(f"  After deletion attempt: {deleted_in_bloom}/{delete_count} still present (should be {delete_count})")
    
    print(f"\nCuckoo Filter:")
    print(f"  Add time: {cuckoo_add_time:.4f}s")
    print(f"  Member query time: {cuckoo_member_time:.4f}s")
    print(f"  Non-member query time: {cuckoo_nonmember_time:.4f}s")
    print(f"  Memory usage: {cuckoo_size:.2f} MB")
    print(f"  True positives: {cuckoo_true_positives}/10000 ({cuckoo_true_positives/100:.2f}%)")
    print(f"  False positives: {cuckoo_false_positives}/10000 ({cuckoo_false_positives/100:.2f}%)")
    print(f"  Delete time: {delete_time:.4f}s")
    print(f"  After deletion: {deleted_in_cuckoo}/{delete_count} still present (should be 0)")
    
    # Plot results
    plt.figure(figsize=(15, 8))
    
    # Plot 1: Time Comparison
    plt.subplot(1, 3, 1)
    operations = ['Add', 'Query (Member)', 'Query (Non-member)', 'Delete']
    bloom_times = [bloom_add_time, bloom_member_time, bloom_nonmember_time, 0]  # Bloom can't delete
    cuckoo_times = [cuckoo_add_time, cuckoo_member_time, cuckoo_nonmember_time, delete_time]
    
    x = range(len(operations))
    width = 0.35
    
    plt.bar([i - width/2 for i in x], bloom_times, width, label='Bloom Filter')
    plt.bar([i + width/2 for i in x], cuckoo_times, width, label='Cuckoo Filter')
    
    plt.xlabel('Operation')
    plt.ylabel('Time (seconds)')
    plt.title('Operation Time Comparison')
    plt.xticks(x, operations)
    plt.grid(True, axis='y')
    plt.legend()
    
    # Plot 2: Memory Comparison
    plt.subplot(1, 3, 2)
    plt.bar(['Bloom Filter', 'Cuckoo Filter'], [bloom_size, cuckoo_size])
    plt.xlabel('Filter Type')
    plt.ylabel('Memory Usage (MB)')
    plt.title('Memory Usage Comparison')
    plt.grid(True, axis='y')
    
    # Plot 3: Accuracy Comparison
    plt.subplot(1, 3, 3)
    metrics = ['True Positives', 'False Positives', 'Deleted Items Present']
    bloom_metrics = [bloom_true_positives/100, bloom_false_positives/100, deleted_in_bloom/delete_count*100]
    cuckoo_metrics = [cuckoo_true_positives/100, cuckoo_false_positives/100, deleted_in_cuckoo/delete_count*100]
    
    x = range(len(metrics))
    
    plt.bar([i - width/2 for i in x], bloom_metrics, width, label='Bloom Filter')
    plt.bar([i + width/2 for i in x], cuckoo_metrics, width, label='Cuckoo Filter')
    
    plt.xlabel('Metric')
    plt.ylabel('Percentage')
    plt.title('Accuracy Comparison')
    plt.xticks(x, metrics)
    plt.grid(True, axis='y')
    plt.legend()
    
    plt.tight_layout()
    plt.savefig('cuckoo_vs_bloom.png')
    print(f"\nComparison plot saved as 'cuckoo_vs_bloom.png'")


def document_similarity_minhash():
    """
    Demonstrate MinHash for document similarity estimation.
    Shows how MinHash can efficiently estimate Jaccard similarity.
    """
    print("\n=== MinHash Document Similarity Estimation ===\n")
    
    # Sample documents (tokenized into word sets)
    documents = {
        "doc1": set("this is a document about ipfs content addressing and how it works".split()),
        "doc2": set("a document explaining how content addressing works in ipfs and its benefits".split()),
        "doc3": set("this tutorial covers distributed hash tables and peer discovery in libp2p".split()),
        "doc4": set("peer discovery mechanisms in libp2p include dht bootstrap and mdns".split()),
        "doc5": set("ipfs uses content addressing based on cryptographic hashes to identify data".split()),
        "doc6": set("completely different topic discussing programming languages and frameworks".split())
    }
    
    # Number of permutations to use
    perm_values = [16, 32, 64, 128, 256]
    
    # Compute true Jaccard similarities between all pairs of documents
    true_similarities = {}
    similarity_compute_time = time.time()
    
    for doc1 in documents:
        for doc2 in documents:
            if doc1 < doc2:  # To avoid computing both (a,b) and (b,a)
                intersection = len(documents[doc1].intersection(documents[doc2]))
                union = len(documents[doc1].union(documents[doc2]))
                jaccard = intersection / union
                true_similarities[(doc1, doc2)] = jaccard
    
    similarity_compute_time = time.time() - similarity_compute_time
    
    print(f"True Jaccard similarities (computed in {similarity_compute_time:.4f}s):")
    for pair, sim in true_similarities.items():
        print(f"  {pair}: {sim:.4f}")
    
    # Results to track for different permutation counts
    results = []
    
    # Test MinHash with different permutation counts
    for num_perms in perm_values:
        print(f"\nTesting MinHash with {num_perms} permutations:")
        
        # Create MinHash signatures for all documents
        signatures = {}
        minhash_compute_time = time.time()
        
        for doc_id, tokens in documents.items():
            minhash = MinHash(num_perm=num_perms)
            minhash.update(tokens)
            signatures[doc_id] = minhash
        
        minhash_compute_time = time.time() - minhash_compute_time
        
        # Compute MinHash similarity estimates
        minhash_similarities = {}
        minhash_similarity_time = time.time()
        
        for doc1 in signatures:
            for doc2 in signatures:
                if doc1 < doc2:  # To avoid computing both (a,b) and (b,a)
                    minhash_similarities[(doc1, doc2)] = signatures[doc1].jaccard(signatures[doc2])
        
        minhash_similarity_time = time.time() - minhash_similarity_time
        
        # Compare to true similarities
        errors = []
        for pair in true_similarities:
            true_sim = true_similarities[pair]
            minhash_sim = minhash_similarities[pair]
            error = abs(true_sim - minhash_sim)
            errors.append(error)
        
        avg_error = sum(errors) / len(errors)
        max_error = max(errors)
        
        # Memory usage
        memory_per_sig = signatures["doc1"].get_info()["memory_usage_bytes"] / 1024  # KB
        total_memory = sum(sys.getsizeof(sig.signature) for sig in signatures.values()) / 1024  # KB
        
        print(f"  Signature computation time: {minhash_compute_time:.4f}s")
        print(f"  Similarity computation time: {minhash_similarity_time:.4f}s")
        print(f"  Memory per signature: {memory_per_sig:.2f} KB")
        print(f"  Total memory usage: {total_memory:.2f} KB")
        print(f"  Average error: {avg_error:.4f}")
        print(f"  Maximum error: {max_error:.4f}")
        
        # Store results for plotting
        results.append({
            "num_perms": num_perms,
            "compute_time": minhash_compute_time,
            "similarity_time": minhash_similarity_time,
            "memory_per_sig": memory_per_sig,
            "total_memory": total_memory,
            "avg_error": avg_error,
            "max_error": max_error,
            "similarities": minhash_similarities
        })
    
    # Show detailed comparison for one specific case (128 perms)
    detailed = next(r for r in results if r["num_perms"] == 128)
    print("\nDetailed comparison (128 permutations):")
    for pair in sorted(true_similarities.keys()):
        true_sim = true_similarities[pair]
        minhash_sim = detailed["similarities"][pair]
        error = abs(true_sim - minhash_sim)
        print(f"  {pair}: True={true_sim:.4f}, MinHash={minhash_sim:.4f}, Error={error:.4f}")
    
    # Plot results
    plt.figure(figsize=(15, 10))
    
    # Plot 1: Accuracy vs Permutations
    plt.subplot(2, 2, 1)
    plt.plot([r["num_perms"] for r in results], [r["avg_error"] for r in results], 'o-', label='Average Error')
    plt.plot([r["num_perms"] for r in results], [r["max_error"] for r in results], 's-', label='Maximum Error')
    
    plt.xlabel('Number of Permutations')
    plt.ylabel('Absolute Error')
    plt.title('MinHash Error vs. Number of Permutations')
    plt.grid(True)
    plt.legend()
    
    # Plot 2: Memory vs Permutations
    plt.subplot(2, 2, 2)
    plt.plot([r["num_perms"] for r in results], [r["memory_per_sig"] for r in results], 'o-')
    
    plt.xlabel('Number of Permutations')
    plt.ylabel('Memory per Signature (KB)')
    plt.title('MinHash Memory Usage vs. Permutations')
    plt.grid(True)
    
    # Plot 3: Memory-Accuracy Tradeoff
    plt.subplot(2, 2, 3)
    plt.plot([r["memory_per_sig"] for r in results], [r["avg_error"] for r in results], 'o-')
    
    plt.xlabel('Memory per Signature (KB)')
    plt.ylabel('Average Error')
    plt.title('MinHash Memory-Accuracy Tradeoff')
    plt.grid(True)
    
    # Plot 4: Similarity Comparison
    plt.subplot(2, 2, 4)
    
    # Get all pairs
    pairs = sorted(true_similarities.keys())
    
    # Plot true similarities
    x = range(len(pairs))
    true_sims = [true_similarities[pair] for pair in pairs]
    plt.plot(x, true_sims, 'ko-', label='True Similarity')
    
    # Plot MinHash similarities for different permutation counts
    colors = ['r', 'g', 'b', 'c', 'm']
    for i, r in enumerate(results):
        minhash_sims = [r["similarities"][pair] for pair in pairs]
        plt.plot(x, minhash_sims, f'{colors[i]}o-', alpha=0.7, 
                label=f'MinHash ({r["num_perms"]} perms)')
    
    plt.xlabel('Document Pair')
    plt.ylabel('Jaccard Similarity')
    plt.title('MinHash Similarity Estimates')
    plt.xticks(x, [f"{p[0]}-{p[1]}" for p in pairs], rotation=45)
    plt.grid(True)
    plt.legend()
    
    plt.tight_layout()
    plt.savefig('minhash_evaluation.png')
    print(f"\nMinHash evaluation plot saved as 'minhash_evaluation.png'")


def heavy_hitters_topk():
    """
    Demonstrate Top-K with Count-Min Sketch for identifying frequent items.
    Shows how to track most frequent elements in a data stream with limited memory.
    """
    print("\n=== Top-K Heavy Hitters ===\n")
    
    # Generate data with a Zipfian distribution (some items are much more frequent)
    def generate_zipfian_data(n, zipf_param=1.1, unique_items=1000):
        # Generate ranks following Zipf distribution
        ranks = np.random.zipf(zipf_param, n)
        # Map to a smaller range of unique items
        return [f"item_{rank % unique_items}" for rank in ranks]
    
    # Parameters
    n_items = 1_000_000  # 1 million data points
    unique_items = 10_000  # Number of unique items
    k_values = [10, 50, 100, 500]  # Different k values to track
    
    # Generate data
    print(f"Generating Zipfian data ({n_items} items)...")
    data = generate_zipfian_data(n_items, zipf_param=1.3, unique_items=unique_items)
    
    # Compute exact frequencies (ground truth)
    print("Computing exact frequencies...")
    start_time = time.time()
    true_counts = Counter(data)
    exact_time = time.time() - start_time
    exact_memory = sys.getsizeof(true_counts) / (1024 * 1024)  # MB
    
    # Get true top-k items
    true_top_k = {k: dict(true_counts.most_common(k)) for k in k_values}
    
    print(f"\nExact counting with Counter:")
    print(f"  Time: {exact_time:.4f} seconds")
    print(f"  Memory: {exact_memory:.2f} MB")
    print(f"  Unique items: {len(true_counts)}")
    
    # Test TopK with different k values
    results = []
    
    for k in k_values:
        # Create TopK tracker
        topk = TopK(k=k, width=2000, depth=5)
        
        # Add all items
        start_time = time.time()
        for item in data:
            topk.add(item)
        add_time = time.time() - start_time
        
        # Get the top-k items
        start_time = time.time()
        estimated_top_k = dict(topk.get_top_k())
        query_time = time.time() - start_time
        
        # Memory usage
        memory_usage = topk.get_info()['memory_usage_bytes'] / (1024 * 1024)  # MB
        
        # Calculate accuracy metrics
        true_set = set(true_top_k[k].keys())
        estimated_set = set(estimated_top_k.keys())
        
        # Set-based metrics
        intersection = true_set.intersection(estimated_set)
        precision = len(intersection) / len(estimated_set) if estimated_set else 0
        recall = len(intersection) / len(true_set) if true_set else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        # Rank correlation
        # Get ranks in true top-k
        true_ranks = {item: i for i, item in enumerate(sorted(true_top_k[k].keys(), 
                                                             key=lambda x: true_top_k[k][x], 
                                                             reverse=True))}
        # Get ranks in estimated top-k
        est_ranks = {item: i for i, item in enumerate(sorted(estimated_top_k.keys(), 
                                                           key=lambda x: estimated_top_k[x], 
                                                           reverse=True))}
        
        # Calculate rank correlation for items in intersection
        rank_errors = [(est_ranks[item] - true_ranks[item]) for item in intersection]
        avg_rank_error = sum(abs(err) for err in rank_errors) / len(rank_errors) if rank_errors else float('inf')
        
        # Store results
        result = {
            "k": k,
            "add_time": add_time,
            "query_time": query_time,
            "memory_mb": memory_usage,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "avg_rank_error": avg_rank_error,
            "true_top_k": true_top_k[k],
            "estimated_top_k": estimated_top_k
        }
        results.append(result)
        
        print(f"\nTop-{k} Heavy Hitters:")
        print(f"  Add time: {add_time:.4f} seconds")
        print(f"  Query time: {query_time:.4f} seconds")
        print(f"  Memory: {memory_usage:.4f} MB")
        print(f"  Precision: {precision:.4f}")
        print(f"  Recall: {recall:.4f}")
        print(f"  F1 Score: {f1:.4f}")
        print(f"  Average Rank Error: {avg_rank_error:.2f}")
        
        # Show top 5 items comparison
        print("\n  Top 5 items comparison:")
        print("    True Top-5:")
        for i, (item, count) in enumerate(sorted(true_top_k[k].items(), key=lambda x: x[1], reverse=True)[:5]):
            print(f"      {i+1}. {item}: {count}")
        
        print("    Estimated Top-5:")
        for i, (item, count) in enumerate(sorted(estimated_top_k.items(), key=lambda x: x[1], reverse=True)[:5]):
            true_count = true_counts[item]
            error = (count - true_count) / true_count
            print(f"      {i+1}. {item}: {count} (true: {true_count}, error: {error:.2%})")
    
    # Plot results
    plt.figure(figsize=(15, 10))
    
    # Plot 1: Precision, Recall, F1 vs k
    plt.subplot(2, 2, 1)
    plt.plot([r["k"] for r in results], [r["precision"] for r in results], 'o-', label='Precision')
    plt.plot([r["k"] for r in results], [r["recall"] for r in results], 's-', label='Recall')
    plt.plot([r["k"] for r in results], [r["f1"] for r in results], '^-', label='F1 Score')
    
    plt.xlabel('k')
    plt.ylabel('Score')
    plt.title('Accuracy Metrics vs. k')
    plt.grid(True)
    plt.legend()
    
    # Plot 2: Memory vs k
    plt.subplot(2, 2, 2)
    plt.plot([r["k"] for r in results], [r["memory_mb"] for r in results], 'o-')
    plt.axhline(y=exact_memory, color='r', linestyle='--', label=f'Counter ({exact_memory:.2f} MB)')
    
    plt.xlabel('k')
    plt.ylabel('Memory (MB)')
    plt.title('Memory Usage vs. k')
    plt.grid(True)
    plt.legend()
    
    # Plot 3: Time vs k
    plt.subplot(2, 2, 3)
    plt.plot([r["k"] for r in results], [r["add_time"] for r in results], 'o-', label='Add Time')
    plt.plot([r["k"] for r in results], [r["query_time"] for r in results], 's-', label='Query Time')
    plt.axhline(y=exact_time, color='r', linestyle='--', label=f'Counter ({exact_time:.4f}s)')
    
    plt.xlabel('k')
    plt.ylabel('Time (seconds)')
    plt.title('Processing Time vs. k')
    plt.grid(True)
    plt.legend()
    
    # Plot 4: Average Rank Error vs k
    plt.subplot(2, 2, 4)
    plt.plot([r["k"] for r in results], [r["avg_rank_error"] for r in results], 'o-')
    
    plt.xlabel('k')
    plt.ylabel('Average Rank Error')
    plt.title('Ranking Accuracy vs. k')
    plt.grid(True)
    
    plt.tight_layout()
    plt.savefig('topk_evaluation.png')
    print(f"\nTop-K evaluation plot saved as 'topk_evaluation.png'")


def ipfs_use_case():
    """
    Demonstrate practical IPFS use cases for probabilistic data structures:
    1. Bloom filter for local content availability checking
    2. HyperLogLog for unique peer tracking
    3. Count-Min Sketch for content popularity monitoring
    4. MinHash for content similarity detection
    """
    print("\n=== IPFS Practical Use Cases ===\n")
    
    # Create the manager
    pds_manager = ProbabilisticDataStructureManager()
    
    # 1. Bloom filter for fast CID availability checks
    print("1. Bloom filter for fast local content availability checks")
    print("   Use case: Quickly determine if content is available locally without disk lookups")
    
    # Simulate 1 million content entries
    num_cids = 1_000_000
    
    # Create a bloom filter
    content_filter = pds_manager.create_bloom_filter(
        name="local_content",
        capacity=num_cids,
        false_positive_rate=0.01
    )
    
    # Simulate adding CIDs to the filter
    mock_cids = [f"QmHash{i}" for i in range(num_cids)]
    for cid in mock_cids:
        content_filter.add(cid)
    
    # Show memory usage
    content_filter_info = content_filter.get_info()
    print(f"   Memory usage: {content_filter_info['memory_usage_bytes'] / (1024*1024):.2f} MB")
    print(f"   Bit array size: {content_filter_info['size']} bits")
    print(f"   Hash functions: {content_filter_info['hash_count']}")
    print(f"   Estimated false positive rate: {content_filter_info['estimated_false_positive_rate']:.4%}")
    
    # Example usage: Check if content exists locally
    print("\n   Example queries:")
    for i in range(5):
        cid = f"QmHash{i}"
        print(f"     Contains {cid}? {cid in content_filter} (should be True)")
    
    for i in range(5):
        cid = f"QmUnknown{i}"
        print(f"     Contains {cid}? {cid in content_filter} (should be False)")
    
    # 2. HyperLogLog for unique peer tracking
    print("\n2. HyperLogLog for unique peers seen")
    print("   Use case: Track number of unique peers connected over time without storing all IDs")
    
    # Create a HyperLogLog estimator
    peer_counter = pds_manager.create_hyperloglog(
        name="unique_peers",
        precision=14  # ~0.8% error with ~20KB memory
    )
    
    # Simulate peers connecting (with some repeats)
    num_connections = 100_000
    unique_peers = 50_000  # Actually unique
    
    for i in range(num_connections):
        # Some peers connect multiple times
        peer_id = f"Peer{i % unique_peers}"
        peer_counter.add(peer_id)
    
    # Check results
    estimated_peers = peer_counter.count()
    error = abs(estimated_peers - unique_peers) / unique_peers * 100
    
    peer_counter_info = peer_counter.get_info()
    print(f"   Memory usage: {peer_counter_info['memory_usage_bytes'] / 1024:.2f} KB")
    print(f"   Precision parameter: {peer_counter_info['precision']}")
    print(f"   Standard error: {peer_counter_info['standard_error']*100:.2f}%")
    print(f"   True unique peers: {unique_peers}")
    print(f"   Estimated unique peers: {estimated_peers}")
    print(f"   Error: {error:.2f}%")
    
    # 3. Count-Min Sketch for content popularity tracking
    print("\n3. Count-Min Sketch for content popularity monitoring")
    print("   Use case: Identify popular content without storing counters for all content")
    
    # Create a Count-Min Sketch
    popularity_tracker = pds_manager.create_count_min_sketch(
        name="content_popularity",
        width=10000,
        depth=5
    )
    
    # Simulate content requests with Zipfian distribution
    num_requests = 1_000_000
    unique_contents = 100_000
    
    # Generate popularity ranks with Zipf distribution
    ranks = np.random.zipf(1.3, num_requests)
    
    # Map to CIDs and track frequencies
    true_counts = Counter()
    for rank in ranks:
        cid = f"QmContent{rank % unique_contents}"
        popularity_tracker.add(cid)
        true_counts[cid] += 1
    
    # Check most popular content
    print("\n   Top 5 most popular content:")
    most_common = true_counts.most_common(5)
    for i, (cid, true_count) in enumerate(most_common):
        est_count = popularity_tracker.estimate_count(cid)
        error = (est_count - true_count) / true_count * 100
        print(f"     {i+1}. {cid}: Estimated {est_count} vs True {true_count} (error: {error:.2f}%)")
    
    popularity_info = popularity_tracker.get_info()
    print(f"\n   Memory usage: {popularity_info['memory_usage_bytes'] / (1024*1024):.2f} MB")
    print(f"   Width: {popularity_info['width']}, Depth: {popularity_info['depth']}")
    print(f"   Error bound: ±{popularity_info['error_bound']:.1f} items with {(1-popularity_info['failure_probability'])*100:.1f}% confidence")
    
    # 4. MinHash for content similarity detection
    print("\n4. MinHash for content similarity detection")
    print("   Use case: Find similar content without full content comparison")
    
    # Create document representations (simulate file chunk patterns)
    documents = {
        "File1": set(f"chunk_{i}" for i in range(100)),
        "File2": set(f"chunk_{i}" for i in range(10, 110)),  # 90% overlap with File1
        "File3": set(f"chunk_{i}" for i in range(50, 150)),  # 50% overlap with File1, 60% with File2
        "File4": set(f"chunk_{i}" for i in range(200, 300)),  # No overlap
    }
    
    # Calculate true Jaccard similarities
    true_sims = {}
    for doc1 in documents:
        for doc2 in documents:
            if doc1 < doc2:
                intersection = len(documents[doc1].intersection(documents[doc2]))
                union = len(documents[doc1].union(documents[doc2]))
                true_sims[(doc1, doc2)] = intersection / union
    
    # Create MinHash signatures
    signatures = {}
    for doc_id, chunks in documents.items():
        minhash = pds_manager.create_minhash(
            name=f"minhash_{doc_id}",
            num_perm=128
        )
        minhash.update(chunks)
        signatures[doc_id] = minhash
    
    # Calculate MinHash similarity estimates
    print("\n   File similarity comparisons:")
    for doc1, doc2 in true_sims:
        true_sim = true_sims[(doc1, doc2)]
        est_sim = signatures[doc1].jaccard(signatures[doc2])
        error = abs(true_sim - est_sim)
        print(f"     {doc1} vs {doc2}: MinHash={est_sim:.4f}, True={true_sim:.4f}, Error={error:.4f}")
    
    signature_info = next(iter(signatures.values())).get_info()
    print(f"\n   Memory per signature: {signature_info['memory_usage_bytes'] / 1024:.2f} KB")
    print(f"   Permutations: {signature_info['num_permutations']}")
    print(f"   Standard error: {signature_info['standard_error']:.4f}")


def main():
    """Run all example functions."""
    print("=== Probabilistic Data Structures Examples ===")
    
    # Run individual examples based on user choice or arguments
    if len(sys.argv) > 1:
        # If functions are specified as arguments, run only those
        for arg in sys.argv[1:]:
            if arg == "bloom":
                compare_bloom_vs_set()
            elif arg == "hll":
                cardinality_estimation_hyperloglog()
            elif arg == "cms":
                frequency_estimation_count_min_sketch()
            elif arg == "cuckoo":
                compare_cuckoo_vs_bloom()
            elif arg == "minhash":
                document_similarity_minhash()
            elif arg == "topk":
                heavy_hitters_topk()
            elif arg == "ipfs":
                ipfs_use_case()
            else:
                print(f"Unknown example: {arg}")
    else:
        # No arguments, run everything
        print("\nRunning all examples. This may take a while...")
        compare_bloom_vs_set()
        cardinality_estimation_hyperloglog()
        frequency_estimation_count_min_sketch()
        compare_cuckoo_vs_bloom()
        document_similarity_minhash()
        heavy_hitters_topk()
        ipfs_use_case()
    
    print("\nAll examples completed. See generated plots for visualizations.")


if __name__ == "__main__":
    main()