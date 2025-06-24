"""
Schema and Column Optimization Example.

This example demonstrates how to use the Schema and Column Optimization
features in ipfs_kit_py to optimize Parquet data storage based on
access patterns and workload characteristics.

Key features demonstrated:
1. Analyzing schema and column usage patterns
2. Creating optimized schemas based on workload type
3. Column pruning for unused fields
4. Creating specialized indexes for frequently queried columns
5. Schema evolution with backward compatibility
6. Measuring storage and performance improvements
"""

import os
import time
import logging
import tempfile
import random
import json
from typing import Dict, List, Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.compute as pc
from pyarrow.dataset import dataset
import matplotlib.pyplot as plt

from ipfs_kit_py.cache.schema_column_optimization import (
    WorkloadType,
    SchemaProfiler,
    SchemaOptimizer,
    SchemaEvolutionManager,
    ParquetCIDCache,
    SchemaColumnOptimizationManager,
    create_example_data
)

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_example_dataset(base_path: str, num_records: int = 5000) -> str:
    """
    Set up an example dataset for demonstration.

    Args:
        base_path: Base directory for storing data
        num_records: Number of records to generate

    Returns:
        Path to the created dataset
    """
    logger.info(f"Setting up example dataset with {num_records} records")

    # Create directories
    os.makedirs(base_path, exist_ok=True)
    dataset_path = os.path.join(base_path, "example_dataset")
    os.makedirs(dataset_path, exist_ok=True)

    # Generate example data
    table = create_example_data(num_records)

    # Split into multiple files to simulate a real dataset
    num_partitions = 5
    partition_size = num_records // num_partitions

    for i in range(num_partitions):
        start_idx = i * partition_size
        end_idx = min((i + 1) * partition_size, num_records)

        partition_table = table.slice(start_idx, end_idx - start_idx)
        file_path = os.path.join(dataset_path, f"part-{i:03d}.parquet")

        pq.write_table(partition_table, file_path)
        logger.info(f"Created partition file: {file_path} with {end_idx - start_idx} records")

    return dataset_path

def simulate_query_workload(profiler: SchemaProfiler, workload_type: WorkloadType, num_queries: int = 1000):
    """
    Simulate a specific query workload to train the profiler.

    Args:
        profiler: SchemaProfiler instance to train
        workload_type: Type of workload to simulate
        num_queries: Number of queries to simulate
    """
    logger.info(f"Simulating {num_queries} queries for {workload_type.value} workload")

    all_columns = [
        "cid", "size_bytes", "pinned", "content_type", "added_timestamp",
        "last_accessed", "access_count", "heat_score",
        "storage_backend", "replication_factor"
    ]

    # Define workload-specific query patterns
    if workload_type == WorkloadType.READ_HEAVY:
        # Read-heavy: Mostly simple retrievals with few filters
        for _ in range(num_queries):
            # Simple get by CID (70% of queries)
            if random.random() < 0.7:
                profiler.track_query({
                    "operation": "read",
                    "columns": ["cid", "size_bytes", "content_type"],
                    "filters": ["cid"],
                    "projections": ["cid", "size_bytes", "content_type"],
                    "timestamp": time.time()
                })
            else:
                # Some filtering by type or size (30% of queries)
                profiler.track_query({
                    "operation": "read",
                    "columns": ["cid", "size_bytes", "content_type", "pinned"],
                    "filters": ["content_type", "pinned"],
                    "projections": ["cid", "size_bytes"],
                    "timestamp": time.time()
                })

    elif workload_type == WorkloadType.WRITE_HEAVY:
        # Write-heavy: Mostly inserts and updates
        for _ in range(num_queries):
            if random.random() < 0.8:
                # Insert new record (80% of queries)
                profiler.track_query({
                    "operation": "write",
                    "columns": all_columns,
                    "timestamp": time.time()
                })
            else:
                # Update existing record (20% of queries)
                profiler.track_query({
                    "operation": "write",
                    "columns": ["cid", "last_accessed", "access_count", "heat_score"],
                    "filters": ["cid"],
                    "timestamp": time.time()
                })

    elif workload_type == WorkloadType.ANALYTICAL:
        # Analytical: Grouping, sorting, and complex filtering
        for _ in range(num_queries):
            # Choose a random analytical query pattern
            query_type = random.randint(1, 4)

            if query_type == 1:
                # Grouping by content type with aggregation
                profiler.track_query({
                    "operation": "read",
                    "columns": ["content_type", "size_bytes", "access_count"],
                    "projections": ["content_type", "size_bytes", "access_count"],
                    "group_by": ["content_type"],
                    "timestamp": time.time()
                })
            elif query_type == 2:
                # Filtering by multiple conditions
                profiler.track_query({
                    "operation": "read",
                    "columns": ["cid", "size_bytes", "content_type", "access_count", "pinned"],
                    "filters": ["size_bytes", "content_type", "pinned"],
                    "projections": ["cid", "size_bytes", "access_count"],
                    "order_by": ["access_count"],
                    "timestamp": time.time()
                })
            elif query_type == 3:
                # Time-based analysis
                profiler.track_query({
                    "operation": "read",
                    "columns": ["cid", "added_timestamp", "last_accessed", "access_count"],
                    "filters": ["added_timestamp"],
                    "order_by": ["added_timestamp"],
                    "timestamp": time.time()
                })
            else:
                # Complex aggregation
                profiler.track_query({
                    "operation": "read",
                    "columns": ["storage_backend", "replication_factor", "size_bytes"],
                    "group_by": ["storage_backend", "replication_factor"],
                    "projections": ["storage_backend", "replication_factor", "size_bytes"],
                    "timestamp": time.time()
                })

    elif workload_type == WorkloadType.CID_FOCUSED:
        # CID-focused: Operations centered on CID lookups
        for _ in range(num_queries):
            # Almost all operations involve CID lookups
            profiler.track_query({
                "operation": "read" if random.random() < 0.8 else "write",
                "columns": ["cid"] + random.sample(all_columns[1:], 3),  # CID plus some random columns
                "filters": ["cid"],
                "timestamp": time.time()
            })

    else:  # Mixed workload
        # Mix of different query types
        for _ in range(num_queries):
            query_type = random.randint(1, 3)

            if query_type == 1:
                # Simple read
                profiler.track_query({
                    "operation": "read",
                    "columns": ["cid", "content_type", "size_bytes"],
                    "filters": ["cid"],
                    "timestamp": time.time()
                })
            elif query_type == 2:
                # Write operation
                profiler.track_query({
                    "operation": "write",
                    "columns": random.sample(all_columns, 5),  # Random subset of columns
                    "timestamp": time.time()
                })
            else:
                # Analytical query
                profiler.track_query({
                    "operation": "read",
                    "columns": ["content_type", "storage_backend", "size_bytes"],
                    "group_by": ["content_type", "storage_backend"],
                    "timestamp": time.time()
                })

    logger.info(f"Completed workload simulation for {workload_type.value}")

def run_optimization_demo(dataset_path: str, workload_type: WorkloadType) -> Dict[str, Any]:
    """
    Run a complete optimization demo for a specific workload type.

    Args:
        dataset_path: Path to the dataset to optimize
        workload_type: Type of workload to optimize for

    Returns:
        Dictionary with optimization results
    """
    logger.info(f"Running optimization demo for {workload_type.value} workload")

    # Create optimization manager
    manager = SchemaColumnOptimizationManager(dataset_path)

    # Simulate workload
    simulate_query_workload(manager.profiler, workload_type, num_queries=1000)

    # Set workload type explicitly for demo purposes
    manager.profiler.workload_type = workload_type

    # Get schema info before optimization
    before_info = manager.get_schema_info()
    logger.info(f"Schema before optimization: {json.dumps(before_info, indent=2)}")

    # Run optimization
    start_time = time.time()
    result = manager.optimize_schema()
    optimization_time = time.time() - start_time

    # Get schema info after optimization
    after_info = manager.get_schema_info()

    # Combine results
    optimization_results = {
        "workload_type": workload_type.value,
        "optimization_time_seconds": optimization_time,
        "before": before_info,
        "after": after_info,
        "results": result
    }

    logger.info(f"Optimization completed in {optimization_time:.2f} seconds")
    logger.info(f"Results: {json.dumps(result, indent=2)}")

    return optimization_results

def compare_query_performance(dataset_path: str, optimizer: SchemaOptimizer) -> Dict[str, Any]:
    """
    Compare query performance before and after schema optimization.

    Args:
        dataset_path: Path to the dataset
        optimizer: SchemaOptimizer instance with optimized schema

    Returns:
        Dictionary with performance comparison results
    """
    logger.info("Comparing query performance before and after optimization")

    # Load dataset with original schema
    ds_original = dataset(dataset_path, format="parquet")
    original_schema = ds_original.schema

    # Get optimized schema
    optimized_schema = optimizer.optimize_schema(original_schema)

    # Define test queries
    test_queries = [
        {
            "name": "Simple filter by CID",
            "filter_expr": pc.equal(pc.field("cid"), pa.scalar("Qm123")),  # Dummy CID, won't match
            "columns": ["cid", "size_bytes", "content_type"]
        },
        {
            "name": "Filter by content type",
            "filter_expr": pc.equal(pc.field("content_type"), pa.scalar("image")),
            "columns": ["cid", "content_type", "size_bytes"]
        },
        {
            "name": "Complex filter with multiple conditions",
            "filter_expr": pc.and_(
                pc.greater(pc.field("size_bytes"), pa.scalar(1000)),
                pc.equal(pc.field("pinned"), pa.scalar(True))
            ),
            "columns": ["cid", "size_bytes", "pinned"]
        },
        {
            "name": "Select all columns",
            "filter_expr": None,
            "columns": None  # All columns
        }
    ]

    # Run queries and measure time
    results = []

    for query in test_queries:
        # Test with original schema
        start_time = time.time()
        _ = ds_original.to_table(
            filter=query["filter_expr"],
            columns=query["columns"]
        )
        original_time = time.time() - start_time

        # Test with pruned schema (simulated - just measure time to scan with fewer columns)
        # In a real implementation, you would apply the optimized schema to the dataset
        pruned_columns = set(optimized_schema.names)
        query_columns = set(query["columns"] if query["columns"] else original_schema.names)
        columns_to_read = list(pruned_columns.intersection(query_columns))

        start_time = time.time()
        _ = ds_original.to_table(
            filter=query["filter_expr"],
            columns=columns_to_read if columns_to_read else None
        )
        optimized_time = time.time() - start_time

        # Calculate speedup
        speedup = original_time / optimized_time if optimized_time > 0 else float('inf')

        results.append({
            "query": query["name"],
            "original_time_ms": original_time * 1000,
            "optimized_time_ms": optimized_time * 1000,
            "speedup": speedup
        })

        logger.info(f"Query: {query['name']}")
        logger.info(f"  Original: {original_time*1000:.2f}ms, Optimized: {optimized_time*1000:.2f}ms")
        logger.info(f"  Speedup: {speedup:.2f}x")

    return {
        "query_results": results,
        "average_speedup": sum(r["speedup"] for r in results) / len(results)
    }

def plot_optimization_results(results: Dict[str, Any], output_path: str = None):
    """
    Create visualizations of the optimization results.

    Args:
        results: Dictionary with optimization results
        output_path: Optional path to save the visualization
    """
    # Create a figure with subplots
    fig, axs = plt.subplots(2, 2, figsize=(15, 10))

    # Plot 1: Column access frequency
    access_freq = results["before"].get("most_accessed_columns", [])
    if access_freq:
        columns, frequencies = zip(*access_freq)
        axs[0, 0].bar(columns, frequencies)
        axs[0, 0].set_title("Column Access Frequency")
        axs[0, 0].set_ylabel("Access Frequency")
        axs[0, 0].tick_params(axis='x', rotation=45)

    # Plot 2: Storage savings
    if "results" in results and "estimated_bytes_saved" in results["results"]:
        axs[0, 1].bar(["Before", "After"],
                     [100, 100 - (results["results"]["estimated_bytes_saved"] / 100)])
        axs[0, 1].set_title("Estimated Storage Reduction")
        axs[0, 1].set_ylabel("Relative Size (%)")

    # Plot 3: Query speedup
    if "query_results" in results:
        query_names = [r["query"] for r in results["query_results"]]
        speedups = [r["speedup"] for r in results["query_results"]]

        axs[1, 0].bar(query_names, speedups)
        axs[1, 0].set_title("Query Performance Improvement")
        axs[1, 0].set_ylabel("Speedup Factor (x)")
        axs[1, 0].tick_params(axis='x', rotation=45)

    # Plot 4: Workload analysis
    axs[1, 1].text(0.5, 0.5,
                  f"Workload Type: {results['workload_type']}\n\n"
                  f"Optimization Time: {results['optimization_time_seconds']:.2f}s\n\n"
                  f"Avg Query Speedup: {results.get('average_speedup', 'N/A')}x\n\n"
                  f"Unused Columns: {len(results['results'].get('unused_columns', []))}\n\n"
                  f"Created Indexes: {len(results['results'].get('created_indexes', []))}",
                  horizontalalignment='center',
                  verticalalignment='center',
                  transform=axs[1, 1].transAxes,
                  fontsize=12)
    axs[1, 1].set_title("Optimization Summary")
    axs[1, 1].axis('off')

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path)
        logger.info(f"Saved visualization to {output_path}")
    else:
        plt.show()

def demonstrate_schema_evolution() -> None:
    """
    Demonstrate schema evolution features for backward compatibility.
    """
    logger.info("Demonstrating schema evolution...")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create evolution manager
        evolution_manager = SchemaEvolutionManager(temp_dir)

        # Create initial schema (version 1)
        initial_schema = pa.schema([
            pa.field("cid", pa.string()),
            pa.field("size_bytes", pa.int64()),
            pa.field("content_type", pa.string()),
            pa.field("added_timestamp", pa.float64())
        ])

        # Register initial schema
        v1 = evolution_manager.register_schema(
            initial_schema,
            "Initial schema with basic fields"
        )
        logger.info(f"Registered initial schema as version {v1}")

        # Evolve schema - add new fields (version 2)
        evolved_schema1 = pa.schema([
            pa.field("cid", pa.string()),
            pa.field("size_bytes", pa.int64()),
            pa.field("content_type", pa.string()),
            pa.field("added_timestamp", pa.float64()),
            pa.field("pinned", pa.bool_()),  # New field
            pa.field("replication_factor", pa.int8())  # New field
        ])

        # Register evolved schema
        v2 = evolution_manager.register_schema(
            evolved_schema1,
            "Added pinning and replication fields"
        )
        logger.info(f"Registered evolved schema as version {v2}")

        # Evolve schema further - change field type and remove field (version 3)
        evolved_schema2 = pa.schema([
            pa.field("cid", pa.string()),
            pa.field("size_bytes", pa.int64()),
            pa.field("content_type", pa.string()),
            # added_timestamp removed
            pa.field("pinned", pa.bool_()),
            pa.field("replication_factor", pa.int32()),  # Type changed from int8 to int32
            pa.field("last_accessed", pa.timestamp("ms"))  # New field with timestamp type
        ])

        # Register further evolved schema
        v3 = evolution_manager.register_schema(
            evolved_schema2,
            "Changed types and added timestamp"
        )
        logger.info(f"Registered further evolved schema as version {v3}")

        # Create compatibility view between versions
        compatibility_v1_v3 = evolution_manager.create_compatibility_view(
            initial_schema, v3
        )

        logger.info("Compatibility v1 -> v3:")
        logger.info(f"  Fully compatible: {compatibility_v1_v3['fully_compatible']}")
        logger.info(f"  Added fields: {compatibility_v1_v3['added_fields']}")
        logger.info(f"  Removed fields: {compatibility_v1_v3['removed_fields']}")
        logger.info(f"  Modified fields: {compatibility_v1_v3['modified_fields']}")
        logger.info(f"  Transformations: {len(compatibility_v1_v3['transformations'])}")

        # Demonstrate applying transformations
        # Create v1 data
        v1_data = pa.Table.from_arrays([
            pa.array(["Qm123", "Qm456"]),  # cid
            pa.array([1000, 2000]),        # size_bytes
            pa.array(["text", "image"]),   # content_type
            pa.array([time.time(), time.time()])  # added_timestamp
        ], schema=initial_schema)

        logger.info(f"V1 data schema: {v1_data.schema}")

        # Apply transformations to get v3-compatible data
        transformed_data = evolution_manager.apply_compatibility_transformations(
            v1_data, compatibility_v1_v3
        )

        logger.info(f"Transformed data schema: {transformed_data.schema}")
        logger.info("Transformation successful, data now compatible with schema v3")

def main():
    """Run the complete schema and column optimization example."""
    logger.info("Starting Schema and Column Optimization Example")

    try:
        # Create temporary directory for example data
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup test dataset
            dataset_path = setup_example_dataset(temp_dir)

            # Initialize optimizer components
            optimizer = SchemaOptimizer(SchemaProfiler())

            # Run optimization for a specific workload type
            workload_type = WorkloadType.ANALYTICAL  # Change to test different workloads
            optimization_results = run_optimization_demo(dataset_path, workload_type)

            # Compare query performance
            performance_results = compare_query_performance(dataset_path, optimizer)

            # Combine results
            combined_results = {**optimization_results, **performance_results}

            # Visualize results
            plot_filepath = os.path.join(temp_dir, "optimization_results.png")
            plot_optimization_results(combined_results, plot_filepath)

            # Demonstrate schema evolution
            demonstrate_schema_evolution()

            logger.info("Schema and Column Optimization Example completed successfully")

    except Exception as e:
        logger.error(f"Error running example: {e}", exc_info=True)

if __name__ == "__main__":
    main()
