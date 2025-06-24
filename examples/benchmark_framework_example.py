#!/usr/bin/env python
"""
Example usage of the ipfs_kit_py benchmark framework.

This script demonstrates how to use the benchmark framework to:
1. Run comprehensive benchmarks across different operations
2. Focus on specific performance aspects
3. Interpret and visualize results
4. Use the recommendations for optimization

Run this script with:
    python examples/benchmark_framework_example.py
"""

import os
import sys
import time
import json
import argparse
from datetime import datetime

# Ensure parent directory is in path for importing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ipfs_kit_py.ipfs_kit import IPFSKit
from ipfs_kit_py.benchmark_framework import BenchmarkSuite


def run_comprehensive_benchmark():
    """Run a comprehensive benchmark across all operations."""
    print("Running comprehensive benchmark suite...")
    benchmark_suite = BenchmarkSuite(
        output_dir="benchmark_results",
        file_sizes=[1024, 1024*1024, 10*1024*1024],  # 1KB, 1MB, 10MB
        iterations=3,
        cleanup=True
    )

    # Run all benchmarks
    results = benchmark_suite.run_all()

    # Display summary of results
    print("\nBenchmark Summary:")
    print("-" * 80)
    for category, tests in results["categories"].items():
        print(f"\n{category.upper()}:")
        for test_name, metrics in tests.items():
            if "mean" in metrics:
                print(f"  {test_name}: {metrics['mean']:.4f}s (±{metrics['std']:.4f}s)")

    # Display recommendations
    print("\nOptimization Recommendations:")
    print("-" * 80)
    for recommendation in results["recommendations"]:
        print(f"- {recommendation}")

    # Return results for further processing
    return results


def run_focused_benchmark(focus_area):
    """Run a focused benchmark on a specific area of interest."""
    valid_areas = ["add", "get", "cat", "pin", "cache", "api", "network"]
    if focus_area not in valid_areas:
        print(f"Invalid focus area. Choose from: {', '.join(valid_areas)}")
        return None

    print(f"Running focused benchmark on {focus_area} operations...")
    benchmark_suite = BenchmarkSuite(
        output_dir="benchmark_results",
        file_sizes=[1024*1024],  # 1MB
        iterations=5,
        cleanup=True
    )

    # Run focused benchmark
    if focus_area == "add":
        results = benchmark_suite.run_add_benchmarks()
    elif focus_area == "get":
        results = benchmark_suite.run_get_benchmarks()
    elif focus_area == "cat":
        results = benchmark_suite.run_cat_benchmarks()
    elif focus_area == "pin":
        results = benchmark_suite.run_pin_benchmarks()
    elif focus_area == "cache":
        results = benchmark_suite.run_cache_benchmarks()
    elif focus_area == "api":
        results = benchmark_suite.run_api_benchmarks()
    elif focus_area == "network":
        results = benchmark_suite.run_network_benchmarks()

    # Display detailed results
    print("\nDetailed Results:")
    print("-" * 80)
    for test_name, metrics in results.items():
        if "mean" in metrics:
            print(f"\n{test_name}:")
            print(f"  Mean execution time: {metrics['mean']:.4f}s")
            print(f"  Standard deviation: {metrics['std']:.4f}s")
            print(f"  Min: {metrics['min']:.4f}s")
            print(f"  Max: {metrics['max']:.4f}s")
            if "data_size" in metrics:
                size_mb = metrics["data_size"] / (1024 * 1024)
                throughput = size_mb / metrics["mean"]
                print(f"  Throughput: {throughput:.2f} MB/s")

    return results


def compare_cache_efficiency():
    """Compare cache efficiency across different access patterns."""
    print("Comparing cache efficiency across different access patterns...")
    benchmark_suite = BenchmarkSuite(
        output_dir="benchmark_results",
        file_sizes=[1024*1024],  # 1MB
        iterations=3,
        cleanup=True
    )

    # Run cache benchmarks
    results = benchmark_suite.run_cache_benchmarks()

    # Extract cache statistics
    sequential_stats = results.get("sequential_access", {})
    random_stats = results.get("random_access", {})
    repeated_stats = results.get("repeated_access", {})

    # Display comparison
    print("\nCache Efficiency Comparison:")
    print("-" * 80)
    print(f"Sequential Access:")
    print(f"  Mean execution time: {sequential_stats.get('mean', 0):.4f}s")
    print(f"  Cache hit rate: {sequential_stats.get('cache_hit_rate', 0):.2%}")

    print(f"\nRandom Access:")
    print(f"  Mean execution time: {random_stats.get('mean', 0):.4f}s")
    print(f"  Cache hit rate: {random_stats.get('cache_hit_rate', 0):.2%}")

    print(f"\nRepeated Access:")
    print(f"  Mean execution time: {repeated_stats.get('mean', 0):.4f}s")
    print(f"  Cache hit rate: {repeated_stats.get('cache_hit_rate', 0):.2%}")

    # Interpret results
    print("\nInterpretation:")
    patterns = [
        ("Sequential", sequential_stats.get('cache_hit_rate', 0)),
        ("Random", random_stats.get('cache_hit_rate', 0)),
        ("Repeated", repeated_stats.get('cache_hit_rate', 0))
    ]
    patterns.sort(key=lambda x: x[1], reverse=True)

    print(f"Best performing pattern: {patterns[0][0]} access ({patterns[0][1]:.2%} hit rate)")
    print(f"Worst performing pattern: {patterns[-1][0]} access ({patterns[-1][1]:.2%} hit rate)")

    if patterns[0][0] == "Repeated":
        print("The cache is optimized for repeated access to the same content.")
    elif patterns[0][0] == "Sequential":
        print("The cache is optimized for sequential access patterns.")
    else:
        print("The cache handles random access well, suggesting good distribution.")

    return results


def analyze_api_overhead():
    """Analyze overhead between high-level and low-level APIs."""
    print("Analyzing API overhead...")
    benchmark_suite = BenchmarkSuite(
        output_dir="benchmark_results",
        file_sizes=[1024*1024],  # 1MB
        iterations=5,
        cleanup=True
    )

    # Run API benchmarks
    results = benchmark_suite.run_api_benchmarks()

    # Calculate overhead ratios
    print("\nAPI Overhead Analysis:")
    print("-" * 80)

    operations = ["add", "get", "cat", "pin"]
    for op in operations:
        high_level_key = f"high_level_{op}"
        low_level_key = f"low_level_{op}"

        if high_level_key in results and low_level_key in results:
            high_level_time = results[high_level_key].get("mean", 0)
            low_level_time = results[low_level_key].get("mean", 0)

            if low_level_time > 0:
                overhead = (high_level_time - low_level_time) / low_level_time * 100
                print(f"{op.upper()} operation:")
                print(f"  High-level API: {high_level_time:.4f}s")
                print(f"  Low-level API: {low_level_time:.4f}s")
                print(f"  Overhead: {overhead:.2f}%")

                if overhead > 50:
                    print(f"  ⚠️ High overhead detected! Consider using low-level API for {op} operations in performance-critical code.")
                elif overhead < 10:
                    print(f"  ✅ Minimal overhead - high-level API is well-optimized for {op} operations.")
                print()

    return results


def analyze_file_size_impact():
    """Analyze the impact of file size on performance."""
    print("Analyzing impact of file size on performance...")
    file_sizes = [1024, 10*1024, 100*1024, 1024*1024, 10*1024*1024]  # 1KB to 10MB

    benchmark_suite = BenchmarkSuite(
        output_dir="benchmark_results",
        file_sizes=file_sizes,
        iterations=3,
        cleanup=True
    )

    # Run add and get benchmarks for different file sizes
    results = {}
    for size in file_sizes:
        benchmark_suite.file_sizes = [size]
        print(f"Testing with file size: {size/1024:.1f} KB")
        size_results = {}

        # Run add benchmark
        add_results = benchmark_suite.run_add_benchmarks()
        size_results["add"] = add_results.get("high_level_add", {}).get("mean", 0)

        # Run get benchmark
        get_results = benchmark_suite.run_get_benchmarks()
        size_results["get"] = get_results.get("high_level_get", {}).get("mean", 0)

        results[size] = size_results

    # Display results
    print("\nFile Size Impact Analysis:")
    print("-" * 80)
    print("File Size (KB) | Add Time (s) | Get Time (s) | Add Throughput (MB/s) | Get Throughput (MB/s)")
    print("-" * 95)

    for size, times in results.items():
        size_kb = size / 1024
        size_mb = size / (1024 * 1024)
        add_time = times.get("add", 0)
        get_time = times.get("get", 0)

        add_throughput = size_mb / add_time if add_time > 0 else 0
        get_throughput = size_mb / get_time if get_time > 0 else 0

        print(f"{size_kb:13.1f} | {add_time:11.4f} | {get_time:11.4f} | {add_throughput:19.2f} | {get_throughput:19.2f}")

    # Analyze scaling behavior
    print("\nScaling Behavior:")

    # Calculate growth ratios
    sizes = sorted(results.keys())
    if len(sizes) >= 2:
        max_size_ratio = sizes[-1] / sizes[0]
        max_add_ratio = results[sizes[-1]]["add"] / results[sizes[0]]["add"] if results[sizes[0]]["add"] > 0 else 0
        max_get_ratio = results[sizes[-1]]["get"] / results[sizes[0]]["get"] if results[sizes[0]]["get"] > 0 else 0

        print(f"File size increase factor: {max_size_ratio:.1f}x")
        print(f"Add time increase factor: {max_add_ratio:.1f}x")
        print(f"Get time increase factor: {max_get_ratio:.1f}x")

        if max_add_ratio < max_size_ratio:
            print("Add operations scale sublinearly with file size - good performance scaling!")
        elif max_add_ratio > max_size_ratio * 1.5:
            print("Add operations scale superlinearly with file size - potential performance bottleneck for large files.")
        else:
            print("Add operations scale approximately linearly with file size.")

        if max_get_ratio < max_size_ratio:
            print("Get operations scale sublinearly with file size - good performance scaling!")
        elif max_get_ratio > max_size_ratio * 1.5:
            print("Get operations scale superlinearly with file size - potential performance bottleneck for large files.")
        else:
            print("Get operations scale approximately linearly with file size.")

    return results


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="IPFS Kit Benchmark Framework Example")
    parser.add_argument("--mode", choices=["comprehensive", "focused", "cache", "api", "filesize"],
                      default="comprehensive", help="Benchmark mode to run")
    parser.add_argument("--focus", choices=["add", "get", "cat", "pin", "cache", "api", "network"],
                      default="add", help="Focus area for focused benchmark")
    parser.add_argument("--output", default="benchmark_results", help="Output directory for results")

    return parser.parse_args()


def main():
    """Main function to run benchmarks based on arguments."""
    args = parse_arguments()

    # Create output directory
    os.makedirs(args.output, exist_ok=True)

    start_time = time.time()
    print(f"Starting benchmarks at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {args.mode}")

    try:
        if args.mode == "comprehensive":
            results = run_comprehensive_benchmark()
        elif args.mode == "focused":
            results = run_focused_benchmark(args.focus)
        elif args.mode == "cache":
            results = compare_cache_efficiency()
        elif args.mode == "api":
            results = analyze_api_overhead()
        elif args.mode == "filesize":
            results = analyze_file_size_impact()

        # Save results to file
        if results:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_file = os.path.join(args.output, f"benchmark_{args.mode}_{timestamp}.json")
            with open(result_file, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\nResults saved to {result_file}")

    except Exception as e:
        print(f"Error running benchmarks: {str(e)}")
        raise

    total_time = time.time() - start_time
    print(f"\nBenchmarks completed in {total_time:.2f} seconds")


if __name__ == "__main__":
    main()
