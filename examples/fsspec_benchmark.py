#!/usr/bin/env python3
"""
IPFS FSSpec Performance Benchmark

This example demonstrates the new performance metrics capabilities in the
IPFS FSSpec integration, allowing you to analyze cache efficiency and
operation latency.
"""

import os
import sys
import json
import time
import random
import logging
import tempfile
import matplotlib.pyplot as plt
from io import BytesIO

# Add the parent directory to the path to import ipfs_kit_py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ipfs_kit_py.ipfs_kit import ipfs_kit

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_files(count=5, min_size=1024, max_size=1024*1024):
    """Create test files with random content for benchmarking.

    Args:
        count: Number of test files to create
        min_size: Minimum file size in bytes
        max_size: Maximum file size in bytes

    Returns:
        List of file paths
    """
    file_paths = []
    for i in range(count):
        size = random.randint(min_size, max_size)
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'_test_{i}.dat') as temp:
            # Generate random content
            content = os.urandom(size)
            temp.write(content)
            file_paths.append(temp.name)

    return file_paths

def add_files_to_ipfs(kit, file_paths):
    """Add test files to IPFS.

    Args:
        kit: IPFS Kit instance
        file_paths: List of file paths to add

    Returns:
        Dictionary mapping file paths to CIDs
    """
    file_cids = {}
    for path in file_paths:
        add_result = kit.ipfs_add_file(path)
        if add_result and 'Hash' in add_result:
            file_cids[path] = add_result['Hash']
            logger.info(f"Added file {path} with CID {add_result['Hash']}")
        else:
            logger.error(f"Failed to add file {path} to IPFS")

    return file_cids

def run_access_pattern_benchmark(fs, cids, access_pattern="sequential", iterations=10):
    """Run a benchmark with different access patterns.

    Args:
        fs: IPFSFileSystem instance
        cids: List of CIDs to access
        access_pattern: "sequential", "random", or "repeated"
        iterations: Number of iterations to run

    Returns:
        Metrics from the benchmark
    """
    # Reset metrics
    fs.reset_metrics()

    # Choose access sequence based on pattern
    if access_pattern == "sequential":
        # Access each CID once in order
        access_sequence = cids * iterations
    elif access_pattern == "random":
        # Random access pattern
        access_sequence = []
        for _ in range(iterations):
            access_sequence.extend(random.sample(cids, len(cids)))
    elif access_pattern == "repeated":
        # Repeatedly access a small set of CIDs
        hot_cids = random.sample(cids, min(3, len(cids)))
        access_sequence = hot_cids * (iterations * len(cids) // len(hot_cids))
    else:
        raise ValueError(f"Unknown access pattern: {access_pattern}")

    # Run the benchmark
    for cid in access_sequence:
        fs.cat(cid)

    # Get metrics
    metrics = fs.get_performance_metrics()

    return metrics

def plot_metrics(metrics_dict):
    """Generate plots from benchmark metrics.

    Args:
        metrics_dict: Dictionary with metrics from different benchmarks

    Returns:
        BytesIO object containing the plot image
    """
    try:
        # Create a figure with multiple subplots
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle('IPFS FSSpec Performance Metrics', fontsize=16)

        # Plot 1: Cache hit rates for different access patterns
        ax1 = axes[0, 0]
        patterns = list(metrics_dict.keys())
        memory_hit_rates = [metrics_dict[p]['cache'].get('memory_hit_rate', 0) for p in patterns]
        disk_hit_rates = [metrics_dict[p]['cache'].get('disk_hit_rate', 0) for p in patterns]
        miss_rates = [metrics_dict[p]['cache'].get('miss_rate', 0) for p in patterns]

        x = range(len(patterns))
        width = 0.25
        ax1.bar([i - width for i in x], memory_hit_rates, width, label='Memory Cache')
        ax1.bar(x, disk_hit_rates, width, label='Disk Cache')
        ax1.bar([i + width for i in x], miss_rates, width, label='Miss')
        ax1.set_ylabel('Rate')
        ax1.set_title('Cache Hit Rates by Access Pattern')
        ax1.set_xticks(x)
        ax1.set_xticklabels(patterns)
        ax1.legend()

        # Plot 2: Access latency by tier
        ax2 = axes[0, 1]
        operations = []
        latencies = []
        labels = []

        # Collect latency data
        for pattern, data in metrics_dict.items():
            ops = data['operations']
            if 'cache_memory_get' in ops and not isinstance(ops['cache_memory_get'], dict):
                continue

            if 'cache_memory_get' in ops and 'mean' in ops['cache_memory_get']:
                operations.append('memory')
                latencies.append(ops['cache_memory_get']['mean'] * 1000)  # Convert to ms
                labels.append(f"{pattern} - memory")

            if 'cache_disk_get' in ops and 'mean' in ops['cache_disk_get']:
                operations.append('disk')
                latencies.append(ops['cache_disk_get']['mean'] * 1000)  # Convert to ms
                labels.append(f"{pattern} - disk")

            if 'ipfs_fetch' in ops and 'mean' in ops['ipfs_fetch']:
                operations.append('network')
                latencies.append(ops['ipfs_fetch']['mean'] * 1000)  # Convert to ms
                labels.append(f"{pattern} - network")

        # Create boxplot for latencies
        ax2.bar(labels, latencies)
        ax2.set_ylabel('Latency (ms)')
        ax2.set_title('Access Latency by Cache Tier')
        plt.setp(ax2.get_xticklabels(), rotation=45, ha='right')

        # Plot 3: Operation counts
        ax3 = axes[1, 0]
        for i, (pattern, data) in enumerate(metrics_dict.items()):
            ops = data['operations']
            if isinstance(ops, dict) and 'total_operations' in ops:
                del ops['total_operations']

            labels = []
            counts = []
            for op_name, op_data in ops.items():
                if isinstance(op_data, dict) and 'count' in op_data:
                    labels.append(op_name)
                    counts.append(op_data['count'])

            ax3.bar([f"{label} ({pattern})" for label in labels], counts)

        ax3.set_ylabel('Count')
        ax3.set_title('Operation Counts')
        plt.setp(ax3.get_xticklabels(), rotation=45, ha='right')

        # Plot 4: Summary metrics
        ax4 = axes[1, 1]
        # Create a text summary
        summary_text = "Performance Summary:\n\n"

        for pattern, data in metrics_dict.items():
            cache = data['cache']
            if 'overall_hit_rate' in cache:
                summary_text += f"{pattern} Access Pattern:\n"
                summary_text += f"  Overall Hit Rate: {cache['overall_hit_rate']:.2%}\n"
                summary_text += f"  Memory Hit Rate: {cache['memory_hit_rate']:.2%}\n"
                summary_text += f"  Disk Hit Rate: {cache['disk_hit_rate']:.2%}\n"
                summary_text += f"  Miss Rate: {cache['miss_rate']:.2%}\n\n"

        ax4.text(0.1, 0.1, summary_text, fontsize=10, va='top', ha='left')
        ax4.axis('off')

        # Adjust layout and save
        plt.tight_layout(rect=[0, 0, 1, 0.95])

        # Save plot to a BytesIO object
        img_data = BytesIO()
        plt.savefig(img_data, format='png')
        img_data.seek(0)
        plt.close()

        return img_data

    except Exception as e:
        logger.error(f"Failed to create plots: {str(e)}")
        return None

def main():
    """Main benchmark function."""
    # Create an IPFS Kit instance
    kit = ipfs_kit()

    # Check if IPFS daemon is running
    try:
        # This will raise an exception if daemon is not running
        kit.ipfs.run_ipfs_command(["ipfs", "id"])
    except Exception as e:
        logger.error(f"IPFS daemon is not running. Please start it with 'ipfs daemon'. Error: {str(e)}")
        return

    try:
        # Create test files
        logger.info("Creating test files...")
        file_paths = create_test_files(count=5, min_size=10*1024, max_size=100*1024)

        # Add files to IPFS
        logger.info("Adding files to IPFS...")
        file_cids = add_files_to_ipfs(kit, file_paths)
        cids = list(file_cids.values())

        if not cids:
            logger.error("No files were added to IPFS. Exiting.")
            return

        # Get a filesystem interface with metrics enabled
        fs = kit.get_filesystem(enable_metrics=True)

        # Run benchmarks with different access patterns
        logger.info("Running sequential access benchmark...")
        sequential_metrics = run_access_pattern_benchmark(fs, cids, "sequential", iterations=5)

        logger.info("Running random access benchmark...")
        random_metrics = run_access_pattern_benchmark(fs, cids, "random", iterations=5)

        logger.info("Running repeated access benchmark...")
        repeated_metrics = run_access_pattern_benchmark(fs, cids, "repeated", iterations=5)

        # Collect all metrics
        all_metrics = {
            "sequential": sequential_metrics,
            "random": random_metrics,
            "repeated": repeated_metrics
        }

        # Print summary
        logger.info("\n=== Benchmark Results ===")

        for pattern, metrics in all_metrics.items():
            cache_stats = metrics["cache"]
            logger.info(f"\n{pattern.upper()} ACCESS PATTERN:")

            if cache_stats["total"] > 0:
                logger.info(f"  Total accesses: {cache_stats['total']}")
                logger.info(f"  Memory hits: {cache_stats['memory_hits']} ({cache_stats['memory_hit_rate']:.2%})")
                logger.info(f"  Disk hits: {cache_stats['disk_hits']} ({cache_stats['disk_hit_rate']:.2%})")
                logger.info(f"  Misses: {cache_stats['misses']} ({cache_stats['miss_rate']:.2%})")
                logger.info(f"  Overall hit rate: {cache_stats['overall_hit_rate']:.2%}")

        # Save metrics to JSON
        with open("benchmark_results.json", "w") as f:
            json.dump(all_metrics, f, indent=2)
        logger.info(f"Saved metrics to benchmark_results.json")

        # Generate and save plots if matplotlib is available
        try:
            img_data = plot_metrics(all_metrics)
            if img_data:
                with open("benchmark_results.png", "wb") as f:
                    f.write(img_data.getvalue())
                logger.info(f"Saved plots to benchmark_results.png")
        except ImportError:
            logger.info("Matplotlib not available. Skipping plot generation.")

    finally:
        # Clean up test files
        for path in file_paths:
            try:
                os.unlink(path)
            except Exception:
                pass

if __name__ == "__main__":
    main()
