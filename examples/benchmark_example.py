#!/usr/bin/env python3
"""
IPFS Kit Benchmarking Example

This example demonstrates how to use the benchmarking capabilities in the
ipfs_kit_py library to profile and optimize your IPFS operations.
"""

import os
import sys
import json
import logging
import matplotlib.pyplot as plt
from datetime import datetime

# Add the parent directory to the path to import ipfs_kit_py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.benchmark import IPFSKitBenchmark

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_basic_benchmark():
    """Run a basic benchmark of core operations."""
    logger.info("Starting basic benchmark example")

    # Create a benchmark instance with default settings
    benchmark = IPFSKitBenchmark(
        metrics_dir="benchmark_results",
        iterations=3,  # Use fewer iterations for quick example
        warmup=1
    )

    # Run core operations benchmark
    results = benchmark.benchmark_core_operations()

    # Print key results
    logger.info("Benchmark Complete. Results:")
    for operation, op_results in results.items():
        logger.info(f"\n{operation.upper()} OPERATION:")
        for size, size_results in op_results.items():
            if isinstance(size_results, dict) and "count" in size_results:
                logger.info(f"  Size: {size}")
                logger.info(f"    Average time: {size_results.get('avg', 0):.4f}s")
                if "throughput_bytes_per_second" in size_results:
                    throughput = size_results["throughput_bytes_per_second"]
                    logger.info(f"    Throughput: {throughput/1024/1024:.2f} MB/s")

    # Save results
    results_file = benchmark.save_results("basic_benchmark_results.json")
    logger.info(f"Results saved to {results_file}")

    return results

def run_caching_benchmark():
    """Run a benchmark focused on cache performance."""
    logger.info("Starting cache performance benchmark")

    # Create a benchmark instance
    benchmark = IPFSKitBenchmark(
        metrics_dir="benchmark_results",
        iterations=3,
        warmup=1
    )

    # Run caching benchmark
    results = benchmark.benchmark_caching()

    # Print key results
    logger.info("Cache Benchmark Complete. Results:")
    for pattern, pattern_results in results.items():
        if pattern == "promotion" or not isinstance(pattern_results, dict):
            continue

        cache_stats = pattern_results.get("cache_stats", {})
        logger.info(f"\n{pattern.upper()} ACCESS PATTERN:")
        logger.info(f"  Total accesses: {cache_stats.get('total', 0)}")
        logger.info(f"  Hit rate: {cache_stats.get('hit_rate', 0):.2%}")

        # Print latency comparison between cold and warm cache
        if "latency" in pattern_results:
            logger.info(f"  Latency comparison:")
            for name, latency in pattern_results["latency"].items():
                cold = latency.get("cold_cache", {}).get("avg", 0)
                warm = latency.get("warm_cache", {}).get("avg", 0)
                speedup = latency.get("speedup", 0)
                logger.info(f"    {name}: Cold: {cold:.4f}s, Warm: {warm:.4f}s, Speedup: {speedup:.1f}x")

    # Save results
    results_file = benchmark.save_results("cache_benchmark_results.json")
    logger.info(f"Results saved to {results_file}")

    return results

def run_parallel_benchmark():
    """Run a benchmark to evaluate parallel performance scaling."""
    logger.info("Starting parallel operations benchmark")

    # Create a benchmark instance
    benchmark = IPFSKitBenchmark(
        metrics_dir="benchmark_results",
        iterations=2,
        warmup=1,
        parallelism=4  # Set maximum parallelism
    )

    # Run parallel operations benchmark
    results = benchmark.benchmark_parallel_operations()

    # Print key results
    logger.info("Parallel Benchmark Complete. Results:")

    # Analyze parallel add results
    logger.info("\nPARALLEL ADD RESULTS:")
    if "parallel_add" in results:
        for workers, worker_results in results["parallel_add"].items():
            logger.info(f"  Workers: {workers}")
            ops_per_sec = worker_results.get("files_per_second", 0)
            avg_time = worker_results.get("avg", 0)
            logger.info(f"    Files per second: {ops_per_sec:.2f}")
            logger.info(f"    Average time: {avg_time:.4f}s")

    # Analyze parallel cat results
    logger.info("\nPARALLEL CAT RESULTS:")
    if "parallel_cat" in results:
        for workers, worker_results in results["parallel_cat"].items():
            logger.info(f"  Workers: {workers}")
            ops_per_sec = worker_results.get("requests_per_second", 0)
            avg_time = worker_results.get("avg", 0)
            logger.info(f"    Requests per second: {ops_per_sec:.2f}")
            logger.info(f"    Average time: {avg_time:.4f}s")

    # Save results
    results_file = benchmark.save_results("parallel_benchmark_results.json")
    logger.info(f"Results saved to {results_file}")

    # Create visualization if matplotlib is available
    try:
        visualize_parallel_scaling(results)
    except Exception as e:
        logger.warning(f"Could not create visualization: {str(e)}")

    return results

def visualize_parallel_scaling(results):
    """Create a visualization of parallel scaling performance."""
    plt.figure(figsize=(10, 6))

    # Plot parallel add performance
    if "parallel_add" in results:
        workers = []
        throughput = []

        for worker_count, data in results["parallel_add"].items():
            workers.append(worker_count)
            throughput.append(data.get("files_per_second", 0))

        plt.subplot(1, 2, 1)
        plt.plot(workers, throughput, 'o-', label='Add Operations')
        plt.xlabel('Number of Workers')
        plt.ylabel('Files per Second')
        plt.title('Add Operation Scaling')
        plt.grid(True)

    # Plot parallel cat performance
    if "parallel_cat" in results:
        workers = []
        throughput = []

        for worker_count, data in results["parallel_cat"].items():
            workers.append(worker_count)
            throughput.append(data.get("requests_per_second", 0))

        plt.subplot(1, 2, 2)
        plt.plot(workers, throughput, 'o-', label='Cat Operations')
        plt.xlabel('Number of Workers')
        plt.ylabel('Requests per Second')
        plt.title('Cat Operation Scaling')
        plt.grid(True)

    plt.tight_layout()
    plt.savefig("parallel_scaling.png")
    logger.info("Parallel scaling visualization saved to parallel_scaling.png")

def run_comprehensive_benchmark():
    """Run a comprehensive benchmark of all systems."""
    logger.info("Starting comprehensive benchmark")

    # Create benchmark instance
    benchmark = IPFSKitBenchmark(
        metrics_dir="benchmark_results",
        iterations=2,  # Lower for example
        warmup=1
    )

    # Run all benchmarks
    results = benchmark.run_all_benchmarks()

    logger.info(f"Comprehensive benchmark complete")
    logger.info(f"Total duration: {results['duration']:.2f} seconds")
    logger.info(f"Results saved to {benchmark.metrics_dir}")

    # Generate a report
    if "metrics_analysis" in results:
        analysis = results["metrics_analysis"]

        if "recommendations" in analysis:
            logger.info("\nPERFORMANCE RECOMMENDATIONS:")
            for rec in analysis["recommendations"]:
                logger.info(f"  - {rec['severity'].upper()}: {rec['message']}")

        if "summary" in analysis:
            logger.info("\nPERFORMANCE SUMMARY:")
            for key, value in analysis["summary"].items():
                if isinstance(value, dict):
                    logger.info(f"  - {key}: {value}")
                else:
                    logger.info(f"  - {key}: {value}")

    return results

def main():
    """Main function demonstrating different benchmark options."""
    if len(sys.argv) > 1:
        benchmark_type = sys.argv[1]
    else:
        benchmark_type = "basic"

    try:
        if benchmark_type == "basic":
            run_basic_benchmark()
        elif benchmark_type == "cache":
            run_caching_benchmark()
        elif benchmark_type == "parallel":
            run_parallel_benchmark()
        elif benchmark_type == "all":
            run_comprehensive_benchmark()
        else:
            logger.error(f"Unknown benchmark type: {benchmark_type}")
            logger.info("Available options: basic, cache, parallel, all")
            return 1

        return 0
    except Exception as e:
        logger.error(f"Benchmark failed: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
