"""
Advanced Partitioning Strategies Example

This example demonstrates the usage of advanced partitioning strategies in ipfs_kit_py.
"""

import os
import time
import random
import uuid
import json
import pyarrow as pa
import pyarrow.parquet as pq
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from typing import Dict, List, Any

from ipfs_kit_py.cache.advanced_partitioning_strategies import (
    PartitioningStrategy,
    TimeBasedPartitionStrategy,
    SizeBasedPartitionStrategy,
    ContentTypePartitionStrategy,
    HashBasedPartitionStrategy,
    DynamicPartitionManager,
    AdvancedPartitionManager
)

# Create a temp directory for the example
TEMP_DIR = os.path.expanduser("~/ipfs_kit_tmp/partitioning_example")
os.makedirs(TEMP_DIR, exist_ok=True)

def create_test_data(num_records: int = 1000) -> List[Dict[str, Any]]:
    """Create test data with diverse characteristics."""
    records = []

    # Common MIME types for testing content-type partitioning
    mime_types = [
        "image/jpeg", "image/png", "application/pdf", "text/plain",
        "video/mp4", "audio/mpeg", "application/zip"
    ]

    # Generate sample records with varying characteristics
    for i in range(num_records):
        # Create record with a mix of characteristics to test different partitioning strategies
        record = {
            "cid": f"Qm{uuid.uuid4().hex[:38]}",  # Simulated CID
            "timestamp": time.time() - random.randint(0, 90 * 24 * 3600),  # Random time in last 90 days
            "mime_type": random.choice(mime_types),
            "size_bytes": random.randint(1024, 10 * 1024 * 1024),  # 1KB to 10MB
            "filename": f"file_{i}.dat",
            "metadata": {
                "title": f"Test Record {i}",
                "description": f"This is test record {i} for partitioning",
                "tags": random.sample(["test", "example", "data", "record", "partition"],
                                      k=random.randint(1, 3))
            }
        }

        records.append(record)

    return records

def example_time_based_partitioning():
    """Demonstrate time-based partitioning strategy."""
    print("\n=== Time-Based Partitioning Example ===")

    # Initialize time-based partitioning
    time_base_path = os.path.join(TEMP_DIR, "time_based")
    time_strategy = TimeBasedPartitionStrategy(
        timestamp_column="timestamp",
        period="daily",
        base_path=time_base_path
    )

    # Create test data with timestamps spanning multiple days
    records = create_test_data(100)

    # Sort records by timestamp to demonstrate time partitioning
    records.sort(key=lambda x: x["timestamp"])

    # Assign records to partitions
    partition_assignments = {}
    for record in records:
        partition_path = time_strategy.partition_record(record)
        if partition_path not in partition_assignments:
            partition_assignments[partition_path] = []
        partition_assignments[partition_path].append(record)

    # Print partition distribution
    print(f"Time-based partitioning created {len(partition_assignments)} partitions")
    for partition_path, partition_records in partition_assignments.items():
        # Convert first timestamp to readable date
        first_date = datetime.fromtimestamp(partition_records[0]["timestamp"]).strftime("%Y-%m-%d")
        print(f"  Partition {os.path.basename(partition_path)}: {len(partition_records)} records, date: {first_date}")

    # Write some records to actual partition files for demonstration
    selected_partition = next(iter(partition_assignments.keys()))
    records_to_write = partition_assignments[selected_partition][:10]

    # Create a PyArrow table and write to Parquet
    schema = pa.schema([
        pa.field("cid", pa.string()),
        pa.field("timestamp", pa.float64()),
        pa.field("mime_type", pa.string()),
        pa.field("size_bytes", pa.int64())
    ])

    # Convert records to columns
    cids = pa.array([r["cid"] for r in records_to_write], type=pa.string())
    timestamps = pa.array([r["timestamp"] for r in records_to_write], type=pa.float64())
    mime_types = pa.array([r["mime_type"] for r in records_to_write], type=pa.string())
    sizes = pa.array([r["size_bytes"] for r in records_to_write], type=pa.int64())

    # Create table
    table = pa.Table.from_arrays([cids, timestamps, mime_types, sizes],
                                schema=schema)

    # Ensure directory exists
    os.makedirs(os.path.dirname(selected_partition), exist_ok=True)

    # Write to Parquet file
    parquet_path = f"{selected_partition}/data.parquet"
    pq.write_table(table, parquet_path)

    print(f"Wrote sample data to {parquet_path}")

    # Visualize time distribution
    visualize_time_partitioning(records, time_strategy)

    return time_strategy

def visualize_time_partitioning(records, time_strategy):
    """Visualize the time-based partitioning."""
    try:
        # Import matplotlib only if available
        import matplotlib.pyplot as plt
        import numpy as np

        # Extract timestamps
        timestamps = [r["timestamp"] for r in records]
        dates = [datetime.fromtimestamp(ts) for ts in timestamps]

        # Count records per partition
        partition_counts = {}
        for record in records:
            partition_path = time_strategy.partition_record(record)
            partition_name = os.path.basename(partition_path)
            if partition_name not in partition_counts:
                partition_counts[partition_name] = 0
            partition_counts[partition_name] += 1

        # Sort partitions for nicer visualization
        sorted_partitions = sorted(partition_counts.keys())
        counts = [partition_counts[p] for p in sorted_partitions]

        # Create the figure with subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

        # Plot histogram of timestamps
        ax1.hist(dates, bins=20, alpha=0.7, color='skyblue')
        ax1.set_title('Distribution of Records by Date')
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Number of Records')

        # Plot bar chart of records per partition
        ax2.bar(sorted_partitions, counts, alpha=0.7, color='lightgreen')
        ax2.set_title('Records per Time Partition')
        ax2.set_xlabel('Partition')
        ax2.set_ylabel('Number of Records')
        ax2.tick_params(axis='x', rotation=45)

        plt.tight_layout()

        # Save the figure
        plt.savefig(os.path.join(TEMP_DIR, 'time_partitioning.png'))
        print(f"Visualization saved to {os.path.join(TEMP_DIR, 'time_partitioning.png')}")
        plt.close()

    except ImportError:
        print("Matplotlib not available, skipping visualization")

def example_size_based_partitioning():
    """Demonstrate size-based partitioning strategy."""
    print("\n=== Size-Based Partitioning Example ===")

    # Initialize size-based partitioning
    size_base_path = os.path.join(TEMP_DIR, "size_based")
    size_strategy = SizeBasedPartitionStrategy(
        target_size_mb=10,  # Small value for the example
        max_size_mb=20,
        base_path=size_base_path
    )

    # Create test data with various sizes
    records = create_test_data(200)

    # Track partition assignments and simulate adding records
    partition_assignments = {}
    current_partition_id = None

    for record in records:
        # Simulate the size-based partitioning process
        record_size = record["size_bytes"]

        # Check if we need a new partition
        if size_strategy.should_rotate_partition(record_size):
            current_partition_id = size_strategy.initialize_partition()

        # Get the partition path
        partition_path = size_strategy.get_partition_path()

        # Update size tracking
        size_strategy.add_record_size(record_size)

        # Track assignments
        if partition_path not in partition_assignments:
            partition_assignments[partition_path] = []
        partition_assignments[partition_path].append(record)

    # Print partition distribution
    print(f"Size-based partitioning created {len(partition_assignments)} partitions")
    for partition_path, partition_records in partition_assignments.items():
        total_size = sum(r["size_bytes"] for r in partition_records)
        print(f"  Partition {os.path.basename(partition_path)}: {len(partition_records)} records, "
              f"size: {total_size / (1024*1024):.2f} MB")

    # Visualize size distribution
    visualize_size_partitioning(records, partition_assignments)

    return size_strategy

def visualize_size_partitioning(records, partition_assignments):
    """Visualize the size-based partitioning."""
    try:
        # Import matplotlib only if available
        import matplotlib.pyplot as plt
        import numpy as np

        # Create the figure with subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

        # Plot histogram of record sizes
        sizes_mb = [r["size_bytes"] / (1024*1024) for r in records]
        ax1.hist(sizes_mb, bins=20, alpha=0.7, color='skyblue')
        ax1.set_title('Distribution of Record Sizes')
        ax1.set_xlabel('Size (MB)')
        ax1.set_ylabel('Number of Records')

        # Plot records and total size per partition
        partitions = list(partition_assignments.keys())
        record_counts = [len(partition_assignments[p]) for p in partitions]
        total_sizes = [sum(r["size_bytes"] for r in partition_assignments[p]) / (1024*1024)
                      for p in partitions]

        partition_names = [os.path.basename(p) for p in partitions]

        # Plot bar charts
        ax2.bar(partition_names, total_sizes, alpha=0.7, color='lightgreen')
        ax2.set_title('Total Size per Partition')
        ax2.set_xlabel('Partition')
        ax2.set_ylabel('Size (MB)')
        ax2.tick_params(axis='x', rotation=45)

        # Add record count as text on bars
        for i, count in enumerate(record_counts):
            ax2.text(i, total_sizes[i] + 0.5, f"{count} records",
                    ha='center', va='bottom', rotation=0)

        plt.tight_layout()

        # Save the figure
        plt.savefig(os.path.join(TEMP_DIR, 'size_partitioning.png'))
        print(f"Visualization saved to {os.path.join(TEMP_DIR, 'size_partitioning.png')}")
        plt.close()

    except ImportError:
        print("Matplotlib not available, skipping visualization")

def example_content_type_partitioning():
    """Demonstrate content-type partitioning strategy."""
    print("\n=== Content-Type Partitioning Example ===")

    # Initialize content-type partitioning
    content_base_path = os.path.join(TEMP_DIR, "content_based")
    content_strategy = ContentTypePartitionStrategy(
        content_type_column="mime_type",
        use_groups=True,
        base_path=content_base_path
    )

    # Create test data with various content types
    records = create_test_data(150)

    # Assign records to partitions
    partition_assignments = {}
    for record in records:
        partition_path = content_strategy.partition_record(record)
        if partition_path not in partition_assignments:
            partition_assignments[partition_path] = []
        partition_assignments[partition_path].append(record)

    # Print partition distribution
    print(f"Content-type partitioning created {len(partition_assignments)} partitions")
    for partition_path, partition_records in partition_assignments.items():
        # Get content types in this partition
        content_types = set(r["mime_type"] for r in partition_records)
        content_group = os.path.basename(partition_path)
        print(f"  Partition {content_group}: {len(partition_records)} records")
        print(f"    Content types: {', '.join(content_types)}")

    # Visualize content type distribution
    visualize_content_partitioning(records, partition_assignments)

    return content_strategy

def visualize_content_partitioning(records, partition_assignments):
    """Visualize the content-type partitioning."""
    try:
        # Import matplotlib only if available
        import matplotlib.pyplot as plt
        import numpy as np

        # Create the figure with subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

        # Count records per content type
        content_type_counts = {}
        for record in records:
            mime_type = record["mime_type"]
            if mime_type not in content_type_counts:
                content_type_counts[mime_type] = 0
            content_type_counts[mime_type] += 1

        # Plot bar chart of content types
        types = list(content_type_counts.keys())
        counts = [content_type_counts[t] for t in types]

        ax1.bar(types, counts, alpha=0.7, color='skyblue')
        ax1.set_title('Distribution of Content Types')
        ax1.set_xlabel('MIME Type')
        ax1.set_ylabel('Number of Records')
        ax1.tick_params(axis='x', rotation=45)

        # Plot records per partition group
        partitions = list(partition_assignments.keys())
        partition_names = [os.path.basename(p) for p in partitions]
        record_counts = [len(partition_assignments[p]) for p in partitions]

        ax2.bar(partition_names, record_counts, alpha=0.7, color='lightgreen')
        ax2.set_title('Records per Content Type Group')
        ax2.set_xlabel('Content Type Group')
        ax2.set_ylabel('Number of Records')

        plt.tight_layout()

        # Save the figure
        plt.savefig(os.path.join(TEMP_DIR, 'content_partitioning.png'))
        print(f"Visualization saved to {os.path.join(TEMP_DIR, 'content_partitioning.png')}")
        plt.close()

    except ImportError:
        print("Matplotlib not available, skipping visualization")

def example_hash_based_partitioning():
    """Demonstrate hash-based partitioning strategy."""
    print("\n=== Hash-Based Partitioning Example ===")

    # Initialize hash-based partitioning with different numbers of partitions
    hash_base_path = os.path.join(TEMP_DIR, "hash_based")
    hash_strategy_16 = HashBasedPartitionStrategy(
        key_column="cid",
        num_partitions=16,
        hash_algorithm="md5",
        base_path=os.path.join(hash_base_path, "16")
    )

    hash_strategy_4 = HashBasedPartitionStrategy(
        key_column="cid",
        num_partitions=4,
        hash_algorithm="md5",
        base_path=os.path.join(hash_base_path, "4")
    )

    # Create test data
    records = create_test_data(200)

    # Assign records to partitions (16 partitions)
    partition_assignments_16 = {}
    for record in records:
        partition_path = hash_strategy_16.partition_record(record)
        if partition_path not in partition_assignments_16:
            partition_assignments_16[partition_path] = []
        partition_assignments_16[partition_path].append(record)

    # Assign records to partitions (4 partitions)
    partition_assignments_4 = {}
    for record in records:
        partition_path = hash_strategy_4.partition_record(record)
        if partition_path not in partition_assignments_4:
            partition_assignments_4[partition_path] = []
        partition_assignments_4[partition_path].append(record)

    # Print partition distribution for 16 partitions
    print(f"Hash-based partitioning (16 partitions):")
    for partition_path, partition_records in partition_assignments_16.items():
        print(f"  Partition {os.path.basename(partition_path)}: {len(partition_records)} records")

    # Print partition distribution for 4 partitions
    print(f"\nHash-based partitioning (4 partitions):")
    for partition_path, partition_records in partition_assignments_4.items():
        print(f"  Partition {os.path.basename(partition_path)}: {len(partition_records)} records")

    # Visualize hash distribution
    visualize_hash_partitioning(partition_assignments_16, partition_assignments_4)

    return hash_strategy_16

def visualize_hash_partitioning(partition_assignments_16, partition_assignments_4):
    """Visualize the hash-based partitioning."""
    try:
        # Import matplotlib only if available
        import matplotlib.pyplot as plt
        import numpy as np

        # Create the figure with subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

        # Plot records per partition for 16 partitions
        partitions_16 = sorted(partition_assignments_16.keys())
        partition_names_16 = [os.path.basename(p) for p in partitions_16]
        record_counts_16 = [len(partition_assignments_16[p]) for p in partitions_16]

        ax1.bar(partition_names_16, record_counts_16, alpha=0.7, color='skyblue')
        ax1.set_title('Records per Partition (16 partitions)')
        ax1.set_xlabel('Partition')
        ax1.set_ylabel('Number of Records')
        ax1.tick_params(axis='x', rotation=45)

        # Calculate statistics for evenness
        mean_16 = np.mean(record_counts_16)
        std_16 = np.std(record_counts_16)
        cv_16 = std_16 / mean_16 if mean_16 > 0 else 0  # Coefficient of variation

        ax1.axhline(y=mean_16, color='r', linestyle='-', alpha=0.7)
        ax1.text(0, mean_16 + 2, f"Mean: {mean_16:.1f}, StdDev: {std_16:.1f}, CV: {cv_16:.3f}",
                 color='red')

        # Plot records per partition for 4 partitions
        partitions_4 = sorted(partition_assignments_4.keys())
        partition_names_4 = [os.path.basename(p) for p in partitions_4]
        record_counts_4 = [len(partition_assignments_4[p]) for p in partitions_4]

        ax2.bar(partition_names_4, record_counts_4, alpha=0.7, color='lightgreen')
        ax2.set_title('Records per Partition (4 partitions)')
        ax2.set_xlabel('Partition')
        ax2.set_ylabel('Number of Records')

        # Calculate statistics for evenness
        mean_4 = np.mean(record_counts_4)
        std_4 = np.std(record_counts_4)
        cv_4 = std_4 / mean_4 if mean_4 > 0 else 0  # Coefficient of variation

        ax2.axhline(y=mean_4, color='r', linestyle='-', alpha=0.7)
        ax2.text(0, mean_4 + 2, f"Mean: {mean_4:.1f}, StdDev: {std_4:.1f}, CV: {cv_4:.3f}",
                 color='red')

        plt.tight_layout()

        # Save the figure
        plt.savefig(os.path.join(TEMP_DIR, 'hash_partitioning.png'))
        print(f"Visualization saved to {os.path.join(TEMP_DIR, 'hash_partitioning.png')}")
        plt.close()

    except ImportError:
        print("Matplotlib not available, skipping visualization")

def example_dynamic_partitioning():
    """Demonstrate dynamic partitioning strategy."""
    print("\n=== Dynamic Partitioning Example ===")

    # Initialize dynamic partition manager
    dynamic_base_path = os.path.join(TEMP_DIR, "dynamic")
    dynamic_manager = DynamicPartitionManager(
        base_path=dynamic_base_path,
        default_strategy=PartitioningStrategy.HASH_BASED,
        auto_rebalance=True
    )

    # Create test data with varied characteristics
    records = create_test_data(300)

    # Set up some clear workload characteristics (for demonstration)
    # Time-based pattern
    for i in range(50):
        # Last day records
        timestamp = time.time() - random.randint(0, 24 * 3600)
        records.append({
            "cid": f"Qm{uuid.uuid4().hex[:38]}",
            "timestamp": timestamp,
            "mime_type": "text/plain",
            "size_bytes": random.randint(1024, 5 * 1024),
        })

    # Content-type pattern
    for i in range(50):
        # Image-focused content
        records.append({
            "cid": f"Qm{uuid.uuid4().hex[:38]}",
            "timestamp": time.time() - random.randint(0, 90 * 24 * 3600),
            "mime_type": random.choice(["image/jpeg", "image/png", "image/gif"]),
            "size_bytes": random.randint(100 * 1024, 5 * 1024 * 1024),
        })

    # Size-based pattern
    for i in range(50):
        # Very large files
        records.append({
            "cid": f"Qm{uuid.uuid4().hex[:38]}",
            "timestamp": time.time() - random.randint(0, 90 * 24 * 3600),
            "mime_type": random.choice(["video/mp4", "application/zip"]),
            "size_bytes": random.randint(50 * 1024 * 1024, 200 * 1024 * 1024),
        })

    # Simulate workload behavior
    for i, record in enumerate(records):
        # Register some synthetic access patterns to drive workload detection
        if "timestamp" in record and record["timestamp"] > time.time() - (2 * 24 * 3600):
            # Register recent timestamp accesses to boost temporal score
            for _ in range(3):  # Multiple accesses to this range
                dynamic_manager.update_workload_stats(
                    recent_access={
                        "key": record["cid"],
                        "timestamp": record["timestamp"],
                        "operation": "read"
                    }
                )

        if "mime_type" in record and record["mime_type"].startswith("image/"):
            # Register accesses to image content to boost content-type score
            dynamic_manager.update_workload_stats(
                recent_access={
                    "key": record["cid"],
                    "content_type": record["mime_type"],
                    "operation": "read"
                }
            )

        if "size_bytes" in record and record["size_bytes"] > 50 * 1024 * 1024:
            # Register accesses to large files to boost size variance score
            dynamic_manager.update_workload_stats(
                recent_access={
                    "key": record["cid"],
                    "size": record["size_bytes"],
                    "operation": "read"
                }
            )

    # Analyze access patterns
    dynamic_manager.analyze_access_patterns()
    dynamic_manager.check_rebalance_partitions()

    # Get partition for each record with current strategy weights
    partition_assignments = {}
    for record in records:
        partition_path = dynamic_manager.get_partition_for_record(record)
        if partition_path not in partition_assignments:
            partition_assignments[partition_path] = []
        partition_assignments[partition_path].append(record)

        # Register the partition
        if len(partition_assignments[partition_path]) == 1:
            strategy = dynamic_manager.get_strategy_for_record(record)
            dynamic_manager.register_partition(
                partition_path=partition_path,
                strategy=strategy,
                record_count=0,
                size_bytes=0,
                metadata={"first_record_cid": record["cid"]}
            )

        # Update partition stats after a few records
        if len(partition_assignments[partition_path]) % 10 == 0:
            partition_id = next(
                pid for pid, pinfo in dynamic_manager.partitions.items()
                if pinfo.path == partition_path
            )

            # Update the stats
            dynamic_manager.update_partition_stats(
                partition_id=partition_id,
                record_count=len(partition_assignments[partition_path]),
                size_bytes=sum(r.get("size_bytes", 0) for r in partition_assignments[partition_path])
            )

    # Print workload stats
    print("Workload Statistics:")
    print(f"  Temporal access score: {dynamic_manager.workload_stats['temporal_access_score']:.3f}")
    print(f"  Content type score: {dynamic_manager.workload_stats['content_type_score']:.3f}")
    print(f"  Size variance score: {dynamic_manager.workload_stats['size_variance_score']:.3f}")
    print(f"  Access distribution score: {dynamic_manager.workload_stats['access_distribution_score']:.3f}")

    # Print optimal strategy
    optimal_strategy = dynamic_manager.get_optimal_strategy()
    print(f"Optimal partitioning strategy: {optimal_strategy.value}")

    # Print partition distribution by strategy
    strategy_counts = {}
    for partition_info in dynamic_manager.partitions.values():
        strategy = partition_info.strategy
        if strategy not in strategy_counts:
            strategy_counts[strategy] = 0
        strategy_counts[strategy] += 1

    print("\nPartition Distribution by Strategy:")
    for strategy, count in strategy_counts.items():
        print(f"  {strategy.value}: {count} partitions")

    # Print some example partitions
    print("\nExample Partitions:")
    for i, partition_id in enumerate(dynamic_manager.partitions.keys()):
        if i >= 5:  # Only show first 5
            break

        partition = dynamic_manager.partitions[partition_id]
        print(f"  ID: {partition_id}")
        print(f"    Path: {partition.path}")
        print(f"    Strategy: {partition.strategy.value}")
        print(f"    Records: {partition.record_count}")
        if partition.size_bytes > 0:
            print(f"    Size: {partition.size_bytes / (1024*1024):.2f} MB")

    # Visualize dynamic partitioning
    visualize_dynamic_partitioning(dynamic_manager)

    return dynamic_manager

def visualize_dynamic_partitioning(dynamic_manager):
    """Visualize the dynamic partitioning strategy."""
    try:
        # Import matplotlib only if available
        import matplotlib.pyplot as plt
        import numpy as np

        # Create the figure with two subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10))

        # Plot workload scores
        scores = {
            "Temporal": dynamic_manager.workload_stats["temporal_access_score"],
            "Content Type": dynamic_manager.workload_stats["content_type_score"],
            "Size Variance": dynamic_manager.workload_stats["size_variance_score"],
            "Access Distribution": dynamic_manager.workload_stats["access_distribution_score"]
        }

        score_names = list(scores.keys())
        score_values = [scores[name] for name in score_names]

        ax1.bar(score_names, score_values, alpha=0.7, color='skyblue')
        ax1.set_title('Workload Characteristic Scores')
        ax1.set_xlabel('Workload Characteristic')
        ax1.set_ylabel('Score (0-1)')
        ax1.set_ylim(0, 1.1)  # Scores are from 0-1

        # Highlight the highest score
        max_score_idx = np.argmax(score_values)
        ax1.get_children()[max_score_idx].set_color('red')

        # Add text about optimal strategy
        optimal_strategy = dynamic_manager.get_optimal_strategy()
        ax1.text(
            0.5, 1.05,
            f"Optimal Strategy: {optimal_strategy.value}",
            horizontalalignment='center',
            transform=ax1.transAxes,
            fontsize=12,
            bbox=dict(facecolor='yellow', alpha=0.2)
        )

        # Plot partition strategy distribution
        strategy_counts = {}
        for partition_info in dynamic_manager.partitions.values():
            strategy = partition_info.strategy
            if strategy not in strategy_counts:
                strategy_counts[strategy] = 0
            strategy_counts[strategy] += 1

        strategy_names = [s.value for s in strategy_counts.keys()]
        strategy_values = list(strategy_counts.values())

        ax2.pie(
            strategy_values,
            labels=strategy_names,
            autopct='%1.1f%%',
            startangle=90,
            shadow=True,
            explode=[0.05] * len(strategy_values),
            colors=plt.cm.Paired(np.linspace(0, 1, len(strategy_values)))
        )
        ax2.set_title('Partition Distribution by Strategy')
        ax2.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle

        plt.tight_layout()

        # Save the figure
        plt.savefig(os.path.join(TEMP_DIR, 'dynamic_partitioning.png'))
        print(f"Visualization saved to {os.path.join(TEMP_DIR, 'dynamic_partitioning.png')}")
        plt.close()

    except ImportError:
        print("Matplotlib not available, skipping visualization")

def example_high_level_manager():
    """Demonstrate the high-level AdvancedPartitionManager."""
    print("\n=== High-Level Advanced Partition Manager Example ===")

    # Create a high-level manager with dynamic strategy
    manager_path = os.path.join(TEMP_DIR, "high_level")
    manager = AdvancedPartitionManager(
        base_path=manager_path,
        strategy="dynamic",
        config={
            "default_strategy": "hash_based",
            "auto_rebalance": True
        }
    )

    # Create test data
    records = create_test_data(100)

    # Process records and track partition assignments
    print("Processing records with high-level manager...")
    partition_assignments = {}

    for record in records:
        # Get partition path
        partition_path = manager.get_partition_path(record)

        # Track assignments
        if partition_path not in partition_assignments:
            partition_assignments[partition_path] = []
        partition_assignments[partition_path].append(record)

        # Register access for workload analysis
        manager.register_access(
            record=record,
            operation="read",
            size=record.get("size_bytes", 1024)
        )

    # Analyze workload
    manager.analyze_workload()

    # Get partition statistics
    stats = manager.get_partition_statistics()

    # Print statistics
    print("Partition Statistics:")
    print(f"  Strategy: {stats['strategy']}")
    print(f"  Base path: {stats['base_path']}")

    if "partition_counts" in stats:
        print("  Partition counts by strategy:")
        for strategy, count in stats["partition_counts"].items():
            print(f"    {strategy}: {count}")

    if "workload_stats" in stats:
        workload = stats["workload_stats"]
        print("  Workload characteristics:")
        print(f"    Temporal access score: {workload.get('temporal_access_score', 0):.3f}")
        print(f"    Content type score: {workload.get('content_type_score', 0):.3f}")
        print(f"    Size variance score: {workload.get('size_variance_score', 0):.3f}")
        print(f"    Access distribution score: {workload.get('access_distribution_score', 0):.3f}")

    if "optimal_strategy" in stats:
        print(f"  Optimal strategy: {stats['optimal_strategy']}")

    # Print partition distribution
    print(f"\nPartition distribution ({len(partition_assignments)} partitions):")
    for i, (partition_path, records) in enumerate(partition_assignments.items()):
        if i >= 5:  # Only show first 5
            print(f"  ... and {len(partition_assignments) - 5} more")
            break

        print(f"  {partition_path}: {len(records)} records")

    return manager

def run_benchmark():
    """Run a simple benchmark comparing the different partitioning strategies."""
    print("\n=== Partitioning Strategies Benchmark ===")

    # Create test data
    num_records = 10000
    print(f"Generating {num_records} test records...")
    records = create_test_data(num_records)

    # Define strategies to benchmark
    strategies = [
        ("Time-based", TimeBasedPartitionStrategy(base_path=os.path.join(TEMP_DIR, "bench_time"))),
        ("Size-based", SizeBasedPartitionStrategy(base_path=os.path.join(TEMP_DIR, "bench_size"))),
        ("Content-type", ContentTypePartitionStrategy(base_path=os.path.join(TEMP_DIR, "bench_content"))),
        ("Hash-based", HashBasedPartitionStrategy(base_path=os.path.join(TEMP_DIR, "bench_hash"))),
        ("Dynamic", DynamicPartitionManager(base_path=os.path.join(TEMP_DIR, "bench_dynamic")))
    ]

    # Results to track
    results = {}

    # Run benchmark for each strategy
    for name, strategy in strategies:
        print(f"Benchmarking {name} partitioning strategy...")
        start_time = time.time()

        # Process all records
        partition_counts = {}

        for record in records:
            if isinstance(strategy, DynamicPartitionManager):
                partition_path = strategy.get_partition_for_record(record)
            else:
                partition_path = strategy.partition_record(record)

            if partition_path not in partition_counts:
                partition_counts[partition_path] = 0
            partition_counts[partition_path] += 1

        # Record elapsed time and partition distribution
        elapsed_time = time.time() - start_time
        num_partitions = len(partition_counts)

        # Calculate partition distribution statistics
        counts = list(partition_counts.values())
        avg_count = sum(counts) / len(counts)
        max_count = max(counts)
        min_count = min(counts)

        # Calculate coefficient of variation (lower is more even)
        stddev = (sum((c - avg_count) ** 2 for c in counts) / len(counts)) ** 0.5
        cv = stddev / avg_count if avg_count > 0 else 0

        results[name] = {
            "time_ms": elapsed_time * 1000,
            "num_partitions": num_partitions,
            "avg_records": avg_count,
            "max_records": max_count,
            "min_records": min_count,
            "coefficient_of_variation": cv
        }

    # Print benchmark results
    print("\nBenchmark Results:")
    print(f"{'Strategy':<15} {'Time (ms)':<12} {'Partitions':<12} {'Avg Records':<15} {'CV (lower=better)':<18}")
    print("-" * 75)

    for name, data in results.items():
        print(f"{name:<15} {data['time_ms']:<12.2f} {data['num_partitions']:<12} {data['avg_records']:<15.2f} {data['coefficient_of_variation']:<18.4f}")

    # Visualize benchmark results
    visualize_benchmark(results)

    return results

def visualize_benchmark(results):
    """Visualize benchmark results."""
    try:
        # Import matplotlib only if available
        import matplotlib.pyplot as plt
        import numpy as np

        # Extract data for plotting
        strategies = list(results.keys())
        times = [results[s]["time_ms"] for s in strategies]
        partitions = [results[s]["num_partitions"] for s in strategies]
        cvs = [results[s]["coefficient_of_variation"] for s in strategies]

        # Create figure with subplots
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 12))

        # Plot processing time
        ax1.bar(strategies, times, alpha=0.7, color='skyblue')
        ax1.set_title('Processing Time (lower is better)')
        ax1.set_xlabel('Strategy')
        ax1.set_ylabel('Time (ms)')

        # Add value labels
        for i, v in enumerate(times):
            ax1.text(i, v + max(times) * 0.02, f"{v:.1f}", ha='center')

        # Plot number of partitions
        ax2.bar(strategies, partitions, alpha=0.7, color='lightgreen')
        ax2.set_title('Number of Partitions')
        ax2.set_xlabel('Strategy')
        ax2.set_ylabel('Partitions')

        # Add value labels
        for i, v in enumerate(partitions):
            ax2.text(i, v + max(partitions) * 0.02, str(v), ha='center')

        # Plot coefficient of variation (lower is better - more even distribution)
        ax3.bar(strategies, cvs, alpha=0.7, color='salmon')
        ax3.set_title('Partition Evenness (lower CV is better)')
        ax3.set_xlabel('Strategy')
        ax3.set_ylabel('Coefficient of Variation')

        # Add value labels
        for i, v in enumerate(cvs):
            ax3.text(i, v + max(cvs) * 0.02, f"{v:.4f}", ha='center')

        plt.tight_layout()

        # Save the figure
        plt.savefig(os.path.join(TEMP_DIR, 'benchmark_results.png'))
        print(f"Benchmark visualization saved to {os.path.join(TEMP_DIR, 'benchmark_results.png')}")
        plt.close()

    except ImportError:
        print("Matplotlib not available, skipping visualization")

def main():
    """Run all examples."""
    print("Advanced Partitioning Strategies Examples")
    print("=" * 50)
    print(f"Temporary directory: {TEMP_DIR}")

    # Run individual strategy examples
    time_strategy = example_time_based_partitioning()
    size_strategy = example_size_based_partitioning()
    content_strategy = example_content_type_partitioning()
    hash_strategy = example_hash_based_partitioning()

    # Run dynamic partitioning example
    dynamic_manager = example_dynamic_partitioning()

    # Run high-level manager example
    high_level_manager = example_high_level_manager()

    # Run benchmark
    benchmark_results = run_benchmark()

    print("\nAll examples completed successfully!")
    print(f"Results and visualizations saved to {TEMP_DIR}")

    # Clean up (comment out to keep files for inspection)
    # import shutil
    # shutil.rmtree(TEMP_DIR)
    # print(f"Cleaned up temporary directory: {TEMP_DIR}")

if __name__ == "__main__":
    main()
