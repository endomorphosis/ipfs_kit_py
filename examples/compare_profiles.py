#!/usr/bin/env python
"""
Compare performance profiling results to measure optimization impact.

This script compares before/after profiling results to quantify improvements
from performance optimizations.
"""

import os
import sys
import json
import argparse
from pathlib import Path
import numpy as np
import tabulate

def load_profile(profile_path):
    """Load profiling results from JSON file."""
    try:
        with open(profile_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading profile {profile_path}: {e}")
        sys.exit(1)

def extract_metrics(profile):
    """Extract key metrics from profile results."""
    metrics = {
        "add_operation": {},
        "cat_operation": {},
        "tiered_cache": {},
        "api_operations": {}
    }
    
    # Extract add operation metrics
    if "tests" in profile and "add_operation" in profile["tests"]:
        add_results = profile["tests"]["add_operation"]
        for size, size_results in add_results.items():
            # Calculate average times for low-level and high-level API
            low_level_times = [r["low_level_api"]["elapsed"] for r in size_results 
                              if r["low_level_api"]["success"]]
            high_level_times = [r["high_level_api"]["elapsed"] for r in size_results 
                               if r["high_level_api"]["success"]]
            
            if low_level_times and high_level_times:
                metrics["add_operation"][size] = {
                    "low_level_avg": np.mean(low_level_times),
                    "high_level_avg": np.mean(high_level_times),
                    "overhead_pct": (np.mean(high_level_times) - np.mean(low_level_times)) / np.mean(low_level_times) * 100
                }
    
    # Extract cat operation metrics
    if "tests" in profile and "cat_operation" in profile["tests"]:
        cat_results = profile["tests"]["cat_operation"]
        for size, size_results in cat_results.items():
            # Calculate times for first (uncached) and subsequent (cached) accesses
            low_level_times = [r["low_level_api"]["elapsed"] for r in size_results 
                              if r["low_level_api"]["success"]]
            high_level_times = [r["high_level_api"]["elapsed"] for r in size_results 
                               if r["high_level_api"]["success"]]
            
            if low_level_times and len(low_level_times) > 1:
                # First access (usually uncached)
                first_low = low_level_times[0]
                subsequent_low = np.mean(low_level_times[1:])
                low_speedup = first_low / subsequent_low if subsequent_low > 0 else 0
                
                # Extract filesystem API times if available
                fs_times = []
                for r in size_results:
                    if r.get("filesystem_api") and r["filesystem_api"].get("success"):
                        fs_times.append(r["filesystem_api"]["elapsed"])
                
                metrics["cat_operation"][size] = {
                    "first_access_low": first_low,
                    "subsequent_access_low": subsequent_low,
                    "low_level_speedup": low_speedup
                }
                
                if high_level_times and len(high_level_times) > 1:
                    first_high = high_level_times[0]
                    subsequent_high = np.mean(high_level_times[1:])
                    high_speedup = first_high / subsequent_high if subsequent_high > 0 else 0
                    
                    metrics["cat_operation"][size].update({
                        "first_access_high": first_high,
                        "subsequent_access_high": subsequent_high,
                        "high_level_speedup": high_speedup
                    })
                
                if fs_times and len(fs_times) > 1:
                    first_fs = fs_times[0]
                    subsequent_fs = np.mean(fs_times[1:])
                    fs_speedup = first_fs / subsequent_fs if subsequent_fs > 0 else 0
                    
                    metrics["cat_operation"][size].update({
                        "first_access_fs": first_fs,
                        "subsequent_access_fs": subsequent_fs,
                        "fs_speedup": fs_speedup
                    })
    
    # Extract cache metrics
    if "tests" in profile and "tiered_cache" in profile["tests"]:
        cache_results = profile["tests"]["tiered_cache"]
        
        for access_pattern in ["sequential_access", "random_access", "repeated_access"]:
            if access_pattern in cache_results:
                pattern_results = cache_results[access_pattern]
                access_times = [r["elapsed"] for r in pattern_results]
                
                metrics["tiered_cache"][access_pattern] = {
                    "avg_access_time": np.mean(access_times) if access_times else 0
                }
                
                # Extract hit rates if available
                if pattern_results and "stats" in pattern_results[-1]:
                    last_stats = pattern_results[-1]["stats"]
                    if "memory_hits" in last_stats and "disk_hits" in last_stats and "misses" in last_stats:
                        total = last_stats["memory_hits"] + last_stats["disk_hits"] + last_stats["misses"]
                        if total > 0:
                            memory_hit_rate = last_stats["memory_hits"] / total * 100
                            disk_hit_rate = last_stats["disk_hits"] / total * 100
                            miss_rate = last_stats["misses"] / total * 100
                            
                            metrics["tiered_cache"][access_pattern].update({
                                "memory_hit_rate": memory_hit_rate,
                                "disk_hit_rate": disk_hit_rate,
                                "miss_rate": miss_rate
                            })
    
    # Extract API operation metrics
    if "tests" in profile and "api_operations" in profile["tests"]:
        api_results = profile["tests"]["api_operations"]
        
        for op_name in ["node_id", "version"]:
            if op_name in api_results:
                op_results = api_results[op_name]
                low_level_times = [r["low_level_api"]["elapsed"] for r in op_results 
                                  if r["low_level_api"]["success"]]
                high_level_times = [r["high_level_api"]["elapsed"] for r in op_results 
                                   if r["high_level_api"]["success"]]
                
                if low_level_times and high_level_times:
                    overhead = (np.mean(high_level_times) - np.mean(low_level_times)) / np.mean(low_level_times) * 100
                    
                    metrics["api_operations"][op_name] = {
                        "low_level_avg": np.mean(low_level_times),
                        "high_level_avg": np.mean(high_level_times),
                        "overhead_pct": overhead
                    }
    
    return metrics

def compare_metrics(before_metrics, after_metrics):
    """Compare before and after metrics and calculate improvements."""
    comparison = {
        "add_operation": {},
        "cat_operation": {},
        "tiered_cache": {},
        "api_operations": {}
    }
    
    # Compare add operation metrics
    for size in set(before_metrics["add_operation"].keys()) & set(after_metrics["add_operation"].keys()):
        before = before_metrics["add_operation"][size]
        after = after_metrics["add_operation"][size]
        
        comparison["add_operation"][size] = {
            "low_level_improvement": (before["low_level_avg"] - after["low_level_avg"]) / before["low_level_avg"] * 100 if before["low_level_avg"] > 0 else 0,
            "high_level_improvement": (before["high_level_avg"] - after["high_level_avg"]) / before["high_level_avg"] * 100 if before["high_level_avg"] > 0 else 0,
            "overhead_reduction": before["overhead_pct"] - after["overhead_pct"],
            "before_low_level_avg": before["low_level_avg"],
            "after_low_level_avg": after["low_level_avg"],
            "before_high_level_avg": before["high_level_avg"],
            "after_high_level_avg": after["high_level_avg"]
        }
    
    # Compare cat operation metrics
    for size in set(before_metrics["cat_operation"].keys()) & set(after_metrics["cat_operation"].keys()):
        before = before_metrics["cat_operation"][size]
        after = after_metrics["cat_operation"][size]
        
        comparison["cat_operation"][size] = {}
        
        # Compare low-level metrics
        if "first_access_low" in before and "first_access_low" in after:
            comparison["cat_operation"][size]["first_access_low_improvement"] = (
                (before["first_access_low"] - after["first_access_low"]) / 
                before["first_access_low"] * 100
            ) if before["first_access_low"] > 0 else 0
        
        if "subsequent_access_low" in before and "subsequent_access_low" in after:
            comparison["cat_operation"][size]["subsequent_access_low_improvement"] = (
                (before["subsequent_access_low"] - after["subsequent_access_low"]) / 
                before["subsequent_access_low"] * 100
            ) if before["subsequent_access_low"] > 0 else 0
        
        # Compare speedup improvement
        if "low_level_speedup" in before and "low_level_speedup" in after:
            comparison["cat_operation"][size]["speedup_improvement"] = after["low_level_speedup"] - before["low_level_speedup"]
        
        # Add original values for reference
        for key in ["first_access_low", "subsequent_access_low", "low_level_speedup"]:
            if key in before:
                comparison["cat_operation"][size][f"before_{key}"] = before[key]
            if key in after:
                comparison["cat_operation"][size][f"after_{key}"] = after[key]
    
    # Compare cache metrics
    for pattern in set(before_metrics["tiered_cache"].keys()) & set(after_metrics["tiered_cache"].keys()):
        before = before_metrics["tiered_cache"][pattern]
        after = after_metrics["tiered_cache"][pattern]
        
        comparison["tiered_cache"][pattern] = {}
        
        # Compare access time improvement
        if "avg_access_time" in before and "avg_access_time" in after:
            comparison["tiered_cache"][pattern]["access_time_improvement"] = (
                (before["avg_access_time"] - after["avg_access_time"]) / 
                before["avg_access_time"] * 100
            ) if before["avg_access_time"] > 0 else 0
        
        # Compare hit rate improvements
        for rate_type in ["memory_hit_rate", "disk_hit_rate", "miss_rate"]:
            if rate_type in before and rate_type in after:
                improvement_key = f"{rate_type}_improvement"
                if rate_type == "miss_rate":
                    # For miss rate, a decrease is an improvement
                    comparison["tiered_cache"][pattern][improvement_key] = before[rate_type] - after[rate_type]
                else:
                    # For hit rates, an increase is an improvement
                    comparison["tiered_cache"][pattern][improvement_key] = after[rate_type] - before[rate_type]
        
        # Add original values for reference
        for key in ["avg_access_time", "memory_hit_rate", "disk_hit_rate", "miss_rate"]:
            if key in before:
                comparison["tiered_cache"][pattern][f"before_{key}"] = before[key]
            if key in after:
                comparison["tiered_cache"][pattern][f"after_{key}"] = after[key]
    
    # Compare API operation metrics
    for op_name in set(before_metrics["api_operations"].keys()) & set(after_metrics["api_operations"].keys()):
        before = before_metrics["api_operations"][op_name]
        after = after_metrics["api_operations"][op_name]
        
        comparison["api_operations"][op_name] = {
            "low_level_improvement": (before["low_level_avg"] - after["low_level_avg"]) / before["low_level_avg"] * 100 if before["low_level_avg"] > 0 else 0,
            "high_level_improvement": (before["high_level_avg"] - after["high_level_avg"]) / before["high_level_avg"] * 100 if before["high_level_avg"] > 0 else 0,
            "overhead_reduction": before["overhead_pct"] - after["overhead_pct"],
            "before_low_level_avg": before["low_level_avg"],
            "after_low_level_avg": after["low_level_avg"],
            "before_high_level_avg": before["high_level_avg"],
            "after_high_level_avg": after["high_level_avg"]
        }
    
    return comparison

def format_comparison(comparison):
    """Format comparison results for display."""
    tables = []
    
    # Format add operation comparison
    if comparison["add_operation"]:
        add_table = []
        add_headers = ["Size (bytes)", "Before Low-level (s)", "After Low-level (s)", "Improvement (%)", 
                      "Before High-level (s)", "After High-level (s)", "Improvement (%)", "Overhead Reduction (%)"]
        
        for size, metrics in sorted(comparison["add_operation"].items(), key=lambda x: int(x[0])):
            add_table.append([
                size,
                f"{metrics['before_low_level_avg']:.4f}",
                f"{metrics['after_low_level_avg']:.4f}",
                f"{metrics['low_level_improvement']:.1f}%",
                f"{metrics['before_high_level_avg']:.4f}",
                f"{metrics['after_high_level_avg']:.4f}",
                f"{metrics['high_level_improvement']:.1f}%",
                f"{metrics['overhead_reduction']:.1f}%"
            ])
        
        tables.append(("Add Operation Performance", add_headers, add_table))
    
    # Format cat operation comparison
    if comparison["cat_operation"]:
        cat_table = []
        cat_headers = ["Size (bytes)", "Before First (s)", "After First (s)", "Improvement (%)",
                      "Before Cached (s)", "After Cached (s)", "Improvement (%)",
                      "Before Speedup", "After Speedup", "Speedup Improvement"]
        
        for size, metrics in sorted(comparison["cat_operation"].items(), key=lambda x: int(x[0])):
            cat_table.append([
                size,
                f"{metrics.get('before_first_access_low', 'N/A') if isinstance(metrics.get('before_first_access_low'), str) else f'{metrics.get('before_first_access_low', 0):.4f}'}",
                f"{metrics.get('after_first_access_low', 'N/A') if isinstance(metrics.get('after_first_access_low'), str) else f'{metrics.get('after_first_access_low', 0):.4f}'}",
                f"{metrics.get('first_access_low_improvement', 'N/A') if isinstance(metrics.get('first_access_low_improvement'), str) else f'{metrics.get('first_access_low_improvement', 0):.1f}%'}",
                f"{metrics.get('before_subsequent_access_low', 'N/A') if isinstance(metrics.get('before_subsequent_access_low'), str) else f'{metrics.get('before_subsequent_access_low', 0):.4f}'}",
                f"{metrics.get('after_subsequent_access_low', 'N/A') if isinstance(metrics.get('after_subsequent_access_low'), str) else f'{metrics.get('after_subsequent_access_low', 0):.4f}'}",
                f"{metrics.get('subsequent_access_low_improvement', 'N/A') if isinstance(metrics.get('subsequent_access_low_improvement'), str) else f'{metrics.get('subsequent_access_low_improvement', 0):.1f}%'}",
                f"{metrics.get('before_low_level_speedup', 'N/A') if isinstance(metrics.get('before_low_level_speedup'), str) else f'{metrics.get('before_low_level_speedup', 0):.1f}x'}",
                f"{metrics.get('after_low_level_speedup', 'N/A') if isinstance(metrics.get('after_low_level_speedup'), str) else f'{metrics.get('after_low_level_speedup', 0):.1f}x'}",
                f"{metrics.get('speedup_improvement', 'N/A') if isinstance(metrics.get('speedup_improvement'), str) else f'{metrics.get('speedup_improvement', 0):.1f}x'}"
            ])
        
        tables.append(("Content Retrieval Performance", cat_headers, cat_table))
    
    # Format cache comparison
    if comparison["tiered_cache"]:
        cache_table = []
        cache_headers = ["Access Pattern", "Before Access Time (s)", "After Access Time (s)", "Improvement (%)",
                        "Before Mem Hit (%)", "After Mem Hit (%)", "Improvement (%)",
                        "Before Miss (%)", "After Miss (%)", "Reduction (%)"]
        
        for pattern, metrics in comparison["tiered_cache"].items():
            cache_table.append([
                pattern.replace("_", " ").title(),
                f"{metrics.get('before_avg_access_time', 0):.4f}",
                f"{metrics.get('after_avg_access_time', 0):.4f}",
                f"{metrics.get('access_time_improvement', 0):.1f}%",
                f"{metrics.get('before_memory_hit_rate', 0):.1f}%",
                f"{metrics.get('after_memory_hit_rate', 0):.1f}%",
                f"{metrics.get('memory_hit_rate_improvement', 0):.1f}%",
                f"{metrics.get('before_miss_rate', 0):.1f}%",
                f"{metrics.get('after_miss_rate', 0):.1f}%",
                f"{metrics.get('miss_rate_improvement', 0):.1f}%"
            ])
        
        tables.append(("Cache Performance", cache_headers, cache_table))
    
    # Format API operations comparison
    if comparison["api_operations"]:
        api_table = []
        api_headers = ["Operation", "Before Low-level (s)", "After Low-level (s)", "Improvement (%)",
                      "Before High-level (s)", "After High-level (s)", "Improvement (%)",
                      "Before Overhead (%)", "After Overhead (%)", "Reduction (%)"]
        
        for op_name, metrics in comparison["api_operations"].items():
            api_table.append([
                op_name,
                f"{metrics['before_low_level_avg']:.4f}",
                f"{metrics['after_low_level_avg']:.4f}",
                f"{metrics['low_level_improvement']:.1f}%",
                f"{metrics['before_high_level_avg']:.4f}",
                f"{metrics['after_high_level_avg']:.4f}",
                f"{metrics['high_level_improvement']:.1f}%",
                f"{metrics['before_overhead_pct']:.1f}%",
                f"{metrics['after_overhead_pct']:.1f}%",
                f"{metrics['overhead_reduction']:.1f}%"
            ])
        
        tables.append(("API Operations Performance", api_headers, api_table))
    
    return tables

def print_comparison(tables):
    """Print formatted comparison tables."""
    for title, headers, table in tables:
        print(f"\n{title}")
        print(tabulate.tabulate(table, headers=headers, tablefmt="grid"))

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Compare performance profiling results")
    parser.add_argument("--before", required=True, help="Path to before profiling results JSON")
    parser.add_argument("--after", required=True, help="Path to after profiling results JSON")
    parser.add_argument("--output", help="Save comparison results to JSON file")
    
    args = parser.parse_args()
    
    # Load profiles
    before_profile = load_profile(args.before)
    after_profile = load_profile(args.after)
    
    # Extract metrics
    before_metrics = extract_metrics(before_profile)
    after_metrics = extract_metrics(after_profile)
    
    # Compare metrics
    comparison = compare_metrics(before_metrics, after_metrics)
    
    # Format and print comparison
    tables = format_comparison(comparison)
    print_comparison(tables)
    
    # Save comparison if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(comparison, f, indent=2)
        print(f"\nComparison saved to {args.output}")
    
    # Calculate overall improvement
    overall_improvements = []
    
    # Add operation improvement
    add_improvements = [metrics["high_level_improvement"] for metrics in comparison["add_operation"].values()]
    if add_improvements:
        overall_improvements.append(("Content Addition", np.mean(add_improvements)))
    
    # Cat operation improvement
    cat_improvements = [metrics.get("subsequent_access_low_improvement", 0) for metrics in comparison["cat_operation"].values()]
    if cat_improvements:
        overall_improvements.append(("Content Retrieval", np.mean(cat_improvements)))
    
    # Cache improvement
    cache_improvements = [metrics.get("access_time_improvement", 0) for metrics in comparison["tiered_cache"].values()]
    if cache_improvements:
        overall_improvements.append(("Cache Performance", np.mean(cache_improvements)))
    
    # API operation improvement
    api_improvements = [metrics["high_level_improvement"] for metrics in comparison["api_operations"].values()]
    if api_improvements:
        overall_improvements.append(("API Operations", np.mean(api_improvements)))
    
    # Print overall improvement
    if overall_improvements:
        total_improvement = np.mean([imp for _, imp in overall_improvements])
        print("\nOverall Performance Improvement")
        print("============================")
        for category, improvement in overall_improvements:
            print(f"{category}: {improvement:.1f}% faster")
        print(f"Average Improvement: {total_improvement:.1f}% faster")
    

if __name__ == "__main__":
    main()