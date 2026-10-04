#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Example usage of Parallel Query Execution module for high-performance queries.

This example demonstrates:
1. Setting up the parallel query manager
2. Creating different types of queries
3. Executing queries in parallel across partitions
4. Measuring performance improvements
5. Query caching and result reuse
"""

import time
import os
import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import matplotlib.pyplot as plt
from typing import List, Dict, Any, Tuple

# Import our parallel query execution module
from ipfs_kit_py.cache.parallel_query_execution import (
    ParallelQueryManager,
    Query,
    QueryType,
    QueryPredicate,
    QueryAggregation,
    ThreadPoolManager,
    QueryCacheManager
)

# Import advanced partitioning for test data generation
from ipfs_kit_py.cache.advanced_partitioning_strategies import (
    AdvancedPartitionManager,
    PartitioningStrategy
)

def create_test_dataset(base_dir: str, num_partitions: int = 10, rows_per_partition: int = 100000):
    """
    Create a test dataset with multiple partitions for demonstration purposes.
    
    Args:
        base_dir: Directory to store the partitions
        num_partitions: Number of partitions to create
        rows_per_partition: Number of rows in each partition
        
    Returns:
        List of partition paths
    """
    os.makedirs(base_dir, exist_ok=True)
    
    partition_paths = []
    
    # Generate data with some patterns for interesting queries
    for i in range(num_partitions):
        # Create a DataFrame with test data
        df = pd.DataFrame({
            'id': range(i * rows_per_partition, (i + 1) * rows_per_partition),
            'timestamp': pd.date_range(
                start=f'2023-01-01', 
                periods=rows_per_partition, 
                freq='1min'
            ),
            'category': np.random.choice(['A', 'B', 'C', 'D', 'E'], size=rows_per_partition),
            'numeric_value': np.random.normal(100, 25, size=rows_per_partition),
            'integer_value': np.random.randint(1, 1000, size=rows_per_partition),
            'boolean_flag': np.random.choice([True, False], size=rows_per_partition),
            'nested_data': [
                {
                    'attribute1': np.random.randint(1, 100),
                    'attribute2': np.random.choice(['X', 'Y', 'Z']),
                    'attribute3': np.random.random()
                } 
                for _ in range(rows_per_partition)
            ]
        })
        
        # Add some patterns for demonstration
        df.loc[df['id'] % 10 == 0, 'numeric_value'] = 500  # Outliers
        df.loc[df['category'] == 'A', 'integer_value'] *= 2  # Category-specific pattern
        
        # Save as parquet
        partition_path = os.path.join(base_dir, f'partition_{i:03d}.parquet')
        df.to_parquet(partition_path, index=False)
        partition_paths.append(partition_path)
        
        print(f"Created partition {i+1}/{num_partitions}")
    
    return partition_paths

def demonstrate_query_types(parallel_query_manager, partition_paths):
    """
    Demonstrate different types of queries and their execution.
    
    Args:
        parallel_query_manager: The ParallelQueryManager instance
        partition_paths: List of partition paths to query
    """
    print("\n=== Demonstrating Different Query Types ===\n")
    
    # Simple lookup query
    simple_query = Query(
        query_type=QueryType.SIMPLE_LOOKUP,
        predicates=[
            QueryPredicate("id", "==", 42)
        ],
        projections=["id", "category", "numeric_value"]
    )
    
    print("Executing simple lookup query...")
    simple_result = parallel_query_manager.execute_query(simple_query, partition_paths)
    print(f"Simple query result: {simple_result.to_pandas().head()}")
    print(f"Total records: {simple_result.num_rows}")
    
    # Range scan query
    range_query = Query(
        query_type=QueryType.RANGE_SCAN,
        predicates=[
            QueryPredicate("numeric_value", ">", 400),
            QueryPredicate("numeric_value", "<", 600)
        ],
        projections=["id", "category", "numeric_value"]
    )
    
    print("\nExecuting range scan query...")
    range_result = parallel_query_manager.execute_query(range_query, partition_paths)
    print(f"Range query result shape: {range_result.to_pandas().shape}")
    print(f"Range query sample: {range_result.to_pandas().head()}")
    
    # Aggregate query with grouping
    aggregate_query = Query(
        query_type=QueryType.AGGREGATE,
        predicates=[
            QueryPredicate("boolean_flag", "==", True)
        ],
        projections=["category"],
        group_by=["category"],
        aggregations=[
            QueryAggregation("numeric_value", "mean", "avg_value"),
            QueryAggregation("numeric_value", "min", "min_value"),
            QueryAggregation("numeric_value", "max", "max_value"),
            QueryAggregation("integer_value", "sum", "total_integer"),
            QueryAggregation("id", "count", "count")
        ]
    )
    
    print("\nExecuting aggregate query...")
    agg_result = parallel_query_manager.execute_query(aggregate_query, partition_paths)
    print(f"Aggregate query result:")
    print(agg_result.to_pandas())
    
    # Complex query with nested conditions
    complex_query = Query(
        query_type=QueryType.COMPLEX,
        predicates=[
            QueryPredicate("category", "in", ["A", "B"]),
            QueryPredicate("numeric_value", ">", 200),
            # Logical OR would be represented with a special notation in a real implementation
            # For simplicity, we'll just use nested conditions in this example
        ],
        projections=["id", "category", "numeric_value", "integer_value"],
        limit=100,
        sort_by="numeric_value",
        descending=True
    )
    
    print("\nExecuting complex query...")
    complex_result = parallel_query_manager.execute_query(complex_query, partition_paths)
    print(f"Complex query result shape: {complex_result.to_pandas().shape}")
    print(f"Complex query top results (sorted by numeric_value desc):")
    print(complex_result.to_pandas().head(10))

def benchmark_parallel_vs_sequential(parallel_query_manager, partition_paths):
    """
    Benchmark parallel query execution against sequential execution.
    
    Args:
        parallel_query_manager: The ParallelQueryManager instance
        partition_paths: List of partition paths to query
    """
    print("\n=== Benchmarking Parallel vs Sequential Execution ===\n")
    
    # Define a query that requires significant processing
    benchmark_query = Query(
        query_type=QueryType.AGGREGATE,
        predicates=[
            QueryPredicate("numeric_value", ">", 50)
        ],
        projections=["category", "boolean_flag"],
        group_by=["category", "boolean_flag"],
        aggregations=[
            QueryAggregation("numeric_value", "mean", "avg_value"),
            QueryAggregation("numeric_value", "stddev", "stddev_value"),
            QueryAggregation("integer_value", "sum", "total_integer"),
            QueryAggregation("id", "count", "count")
        ]
    )
    
    # Run with different thread counts to see scaling
    thread_counts = [1, 2, 4, 8, 16]  # Adjust based on your machine's capabilities
    execution_times = []
    
    for threads in thread_counts:
        parallel_query_manager.thread_pool_manager.set_max_workers(threads)
        
        start_time = time.time()
        _ = parallel_query_manager.execute_query(benchmark_query, partition_paths)
        execution_time = time.time() - start_time
        
        execution_times.append(execution_time)
        print(f"Execution with {threads} threads took {execution_time:.4f} seconds")
    
    # Plot the results
    plt.figure(figsize=(10, 6))
    plt.plot(thread_counts, execution_times, marker='o')
    plt.xlabel('Number of Threads')
    plt.ylabel('Execution Time (seconds)')
    plt.title('Query Execution Time vs Number of Threads')
    plt.grid(True)
    
    # Calculate and display speedup
    speedup = [execution_times[0] / t for t in execution_times]
    for i, threads in enumerate(thread_counts):
        plt.annotate(f"{speedup[i]:.2f}x", 
                    (thread_counts[i], execution_times[i]),
                    textcoords="offset points",
                    xytext=(0, 10),
                    ha='center')
    
    plt.savefig('parallel_query_scaling.png')
    print(f"Scaling graph saved as 'parallel_query_scaling.png'")
    
    # Show ideal scaling line for comparison
    plt.plot(thread_counts, [execution_times[0] / t for t in thread_counts], 
             linestyle='--', label='Ideal Scaling')
    plt.legend()
    plt.savefig('parallel_query_scaling_with_ideal.png')
    print(f"Scaling graph with ideal comparison saved as 'parallel_query_scaling_with_ideal.png'")

def demonstrate_query_caching(parallel_query_manager, partition_paths):
    """
    Demonstrate query caching and result reuse.
    
    Args:
        parallel_query_manager: The ParallelQueryManager instance
        partition_paths: List of partition paths to query
    """
    print("\n=== Demonstrating Query Caching ===\n")
    
    # Enable caching
    parallel_query_manager.enable_caching(max_cache_entries=100)
    
    # Define a query
    cache_query = Query(
        query_type=QueryType.RANGE_SCAN,
        predicates=[
            QueryPredicate("numeric_value", ">", 300),
            QueryPredicate("numeric_value", "<", 400)
        ],
        projections=["id", "category", "numeric_value"]
    )
    
    # First execution (cold cache)
    print("First execution (cold cache)...")
    start_time = time.time()
    result1 = parallel_query_manager.execute_query(cache_query, partition_paths)
    cold_time = time.time() - start_time
    print(f"Cold execution took {cold_time:.4f} seconds")
    print(f"Result record count: {result1.num_rows}")
    
    # Second execution (warm cache)
    print("\nSecond execution (warm cache, same query)...")
    start_time = time.time()
    result2 = parallel_query_manager.execute_query(cache_query, partition_paths)
    warm_time = time.time() - start_time
    print(f"Warm execution took {warm_time:.4f} seconds")
    print(f"Result record count: {result2.num_rows}")
    
    # Calculate speedup
    speedup = cold_time / warm_time
    print(f"\nCache speedup: {speedup:.2f}x faster with caching")
    
    # Show query statistics
    cache_stats = parallel_query_manager.query_cache_manager.get_statistics()
    print(f"\nCache statistics:")
    print(f"Cache hits: {cache_stats.get('hits', 0)}")
    print(f"Cache misses: {cache_stats.get('misses', 0)}")
    print(f"Cache size: {cache_stats.get('current_size', 0)} entries")
    print(f"Memory usage: {cache_stats.get('memory_usage', 0) / (1024*1024):.2f} MB")

def demonstrate_query_planner(parallel_query_manager, partition_paths):
    """
    Demonstrate the query planner's optimization capabilities.
    
    Args:
        parallel_query_manager: The ParallelQueryManager instance
        partition_paths: List of partition paths to query
    """
    print("\n=== Demonstrating Query Planner Optimizations ===\n")
    
    # Enable verbose query planning
    parallel_query_manager.enable_verbose_planning(True)
    
    # Define a query that can benefit from optimization
    complex_query = Query(
        query_type=QueryType.COMPLEX,
        predicates=[
            QueryPredicate("category", "in", ["A", "C"]),
            QueryPredicate("numeric_value", ">", 200),
            QueryPredicate("boolean_flag", "==", True)
        ],
        projections=["id", "category", "numeric_value", "timestamp"],
        limit=10,
        sort_by="numeric_value",
        descending=True
    )
    
    print("Executing optimized query...")
    start_time = time.time()
    optimized_result = parallel_query_manager.execute_query(complex_query, partition_paths)
    optimized_time = time.time() - start_time
    
    # Get query plan information
    query_plan = parallel_query_manager.get_last_query_plan()
    print(f"\nQuery plan details:")
    print(f"Predicate push-down applied: {query_plan.get('predicate_pushdown', False)}")
    print(f"Partition pruning: {query_plan.get('partitions_pruned', 0)} partitions skipped")
    print(f"Projection pruning: {query_plan.get('columns_pruned', 0)} columns pruned")
    print(f"Parallelization strategy: {query_plan.get('parallelization_strategy', 'unknown')}")
    print(f"Thread allocation: {query_plan.get('thread_allocation', {})}")
    
    # Now execute without optimizations for comparison
    parallel_query_manager.enable_optimizations(False)
    
    print("\nExecuting unoptimized query...")
    start_time = time.time()
    unoptimized_result = parallel_query_manager.execute_query(complex_query, partition_paths)
    unoptimized_time = time.time() - start_time
    
    # Re-enable optimizations
    parallel_query_manager.enable_optimizations(True)
    
    # Compare results and performance
    speedup = unoptimized_time / optimized_time
    print(f"\nPerformance comparison:")
    print(f"Optimized query time: {optimized_time:.4f} seconds")
    print(f"Unoptimized query time: {unoptimized_time:.4f} seconds")
    print(f"Optimization speedup: {speedup:.2f}x faster with optimizations")
    
    # Verify results are equivalent
    optimized_df = optimized_result.to_pandas().sort_values('id').reset_index(drop=True)
    unoptimized_df = unoptimized_result.to_pandas().sort_values('id').reset_index(drop=True)
    results_match = optimized_df.equals(unoptimized_df)
    
    print(f"\nResults are {'equivalent' if results_match else 'DIFFERENT'}")
    if not results_match:
        print("WARNING: Optimization changed results - this should not happen!")
    
    print(f"\nOptimized query result sample:")
    print(optimized_result.to_pandas().head())

def main():
    """Main function to run the example."""
    print("=== Parallel Query Execution Example ===\n")
    
    # Create temporary directory for test data
    data_dir = "/tmp/parallel_query_example"
    
    # Check if data already exists
    if not os.path.exists(data_dir) or len([f for f in os.listdir(data_dir) if f.endswith('.parquet')]) < 5:
        print("Creating test dataset (this may take a moment)...")
        partition_paths = create_test_dataset(data_dir, num_partitions=8, rows_per_partition=50000)
    else:
        print("Using existing test dataset...")
        partition_paths = [os.path.join(data_dir, f) for f in os.listdir(data_dir) 
                          if f.endswith('.parquet')]
    
    # Initialize the parallel query manager
    parallel_query_manager = ParallelQueryManager(
        thread_pool_manager=ThreadPoolManager(max_workers=4),
        query_cache_manager=QueryCacheManager(max_cache_entries=20)
    )
    
    # Run the demonstrations
    demonstrate_query_types(parallel_query_manager, partition_paths)
    
    benchmark_parallel_vs_sequential(parallel_query_manager, partition_paths)
    
    demonstrate_query_caching(parallel_query_manager, partition_paths)
    
    demonstrate_query_planner(parallel_query_manager, partition_paths)
    
    print("\n=== Example Complete ===")

if __name__ == "__main__":
    main()