#!/usr/bin/env python
"""
Performance profiling tool for ipfs_kit_py.

This script runs performance tests on key operations in ipfs_kit_py and generates
a detailed report of bottlenecks and optimization opportunities.
"""

import os
import sys
import time
import cProfile
import pstats
import io
import json
import numpy as np
import random
import argparse
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import ipfs_kit_py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from ipfs_kit_py import ipfs_kit
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
except ImportError as e:
    print(f"Error importing ipfs_kit_py: {e}")
    sys.exit(1)

class PerformanceProfiler:
    """Performance profiling tool for ipfs_kit_py."""
    
    def __init__(self, output_dir=None, iterations=10, file_sizes=None, include_metrics=True):
        """Initialize the performance profiler.
        
        Args:
            output_dir: Directory to store profiling results
            iterations: Number of iterations for each test
            file_sizes: List of file sizes to test (in bytes)
            include_metrics: Whether to include detailed metrics in results
        """
        self.iterations = iterations
        self.file_sizes = file_sizes or [1024, 10*1024, 100*1024, 1024*1024]  # 1KB to 1MB
        self.include_metrics = include_metrics
        
        # Create output directory
        self.output_dir = output_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            f"profile_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize results dictionary
        self.results = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "iterations": iterations,
                "file_sizes": self.file_sizes,
            },
            "tests": {}
        }
        
        # Initialize test files
        self.test_files = self._create_test_files()
        
        # Initialize IPFS Kit
        print("Initializing IPFS Kit...")
        self.kit = ipfs_kit()
        
        # Initialize high-level API
        print("Initializing high-level API...")
        self.api = IPFSSimpleAPI()
        
        # Get filesystem if available
        if hasattr(self.kit, 'get_filesystem'):
            self.fs = self.kit.get_filesystem()
        else:
            self.fs = None
            print("Warning: Filesystem interface not available")
            
        # Warmup IPFS daemon
        print("Warming up IPFS daemon...")
        self._warmup()
    
    def _create_test_files(self):
        """Create test files of various sizes.
        
        Returns:
            Dictionary mapping size to file path
        """
        test_files = {}
        for size in self.file_sizes:
            path = os.path.join(self.output_dir, f"test_file_{size}b.bin")
            with open(path, 'wb') as f:
                f.write(os.urandom(size))
            test_files[size] = path
        return test_files
    
    def _warmup(self):
        """Warm up IPFS daemon to ensure fair benchmarking."""
        try:
            # Add and retrieve a small file to warm up the daemon
            test_file = self.test_files[min(self.file_sizes)]
            result = self.kit.ipfs_add_file(test_file)
            if 'Hash' in result:
                self.kit.ipfs_cat(result['Hash'])
            time.sleep(2)  # Allow daemon to stabilize
        except Exception as e:
            print(f"Warning: Warmup failed: {e}")
    
    def _run_with_profile(self, func, *args, **kwargs):
        """Run a function with cProfile and return stats with timing.
        
        Args:
            func: Function to profile
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            Dictionary with timing results and profiling stats
        """
        # Run with cProfile
        pr = cProfile.Profile()
        pr.enable()
        
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            success = True
        except Exception as e:
            result = str(e)
            success = False
        finally:
            end_time = time.time()
            pr.disable()
        
        # Get profile stats
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
        ps.print_stats(20)  # Top 20 functions
        
        # Extract timing
        elapsed = end_time - start_time
        
        return {
            "elapsed": elapsed,
            "success": success,
            "result": result,
            "profile": s.getvalue() if self.include_metrics else "disabled"
        }
    
    def profile_add_operation(self):
        """Profile the add operation for different file sizes."""
        test_name = "add_operation"
        print(f"\nProfiling {test_name}...")
        
        results = {}
        for size, file_path in self.test_files.items():
            size_results = []
            
            print(f"  Testing file size: {size} bytes")
            for i in range(self.iterations):
                # Using low-level API
                low_level_result = self._run_with_profile(
                    self.kit.ipfs_add_file, file_path
                )
                
                # Using high-level API
                high_level_result = self._run_with_profile(
                    self.api.add_file, file_path
                )
                
                size_results.append({
                    "iteration": i,
                    "low_level_api": low_level_result,
                    "high_level_api": high_level_result
                })
            
            results[str(size)] = size_results
            
            # Calculate average times
            low_level_times = [r["low_level_api"]["elapsed"] for r in size_results 
                              if r["low_level_api"]["success"]]
            high_level_times = [r["high_level_api"]["elapsed"] for r in size_results 
                               if r["high_level_api"]["success"]]
            
            if low_level_times and high_level_times:
                print(f"    Average time (low-level): {np.mean(low_level_times):.4f}s")
                print(f"    Average time (high-level): {np.mean(high_level_times):.4f}s")
        
        self.results["tests"][test_name] = results
        return results
    
    def profile_cat_operation(self):
        """Profile the cat operation for different file sizes."""
        test_name = "cat_operation"
        print(f"\nProfiling {test_name}...")
        
        # First add all files to get their CIDs
        cids = {}
        for size, file_path in self.test_files.items():
            result = self.kit.ipfs_add_file(file_path)
            if 'Hash' in result:
                cids[size] = result['Hash']
            else:
                print(f"Warning: Failed to add file of size {size}")
        
        results = {}
        for size, cid in cids.items():
            size_results = []
            
            print(f"  Testing file size: {size} bytes (CID: {cid})")
            for i in range(self.iterations):
                # First run: uncached (potentially)
                if i == 0:
                    # Clear caches if filesystem is available
                    if self.fs and hasattr(self.fs, 'cache'):
                        try:
                            self.fs.cache.clear()
                            print("    Cleared cache for first run")
                        except Exception as e:
                            print(f"    Warning: Failed to clear cache: {e}")
                
                # Using low-level API
                low_level_result = self._run_with_profile(
                    self.kit.ipfs_cat, cid
                )
                
                # Using high-level API
                high_level_result = self._run_with_profile(
                    self.api.cat, cid
                )
                
                # Using filesystem API if available
                fs_result = None
                if self.fs:
                    fs_result = self._run_with_profile(
                        self.fs.cat, cid
                    )
                
                size_results.append({
                    "iteration": i,
                    "low_level_api": low_level_result,
                    "high_level_api": high_level_result,
                    "filesystem_api": fs_result
                })
            
            results[str(size)] = size_results
            
            # Calculate average times
            low_level_times = [r["low_level_api"]["elapsed"] for r in size_results 
                              if r["low_level_api"]["success"]]
            high_level_times = [r["high_level_api"]["elapsed"] for r in size_results 
                               if r["high_level_api"]["success"]]
            
            if low_level_times and high_level_times:
                print(f"    Average time (low-level): {np.mean(low_level_times):.4f}s")
                print(f"    Average time (high-level): {np.mean(high_level_times):.4f}s")
                
                # Print first vs. subsequent access times to show caching effect
                if len(low_level_times) > 1:
                    print(f"    First access (low-level): {low_level_times[0]:.4f}s")
                    print(f"    Subsequent access (low-level): {np.mean(low_level_times[1:]):.4f}s")
                
                if self.fs:
                    fs_times = [r["filesystem_api"]["elapsed"] for r in size_results 
                               if r["filesystem_api"] and r["filesystem_api"]["success"]]
                    if fs_times:
                        print(f"    Average time (filesystem): {np.mean(fs_times):.4f}s")
                        
                        if len(fs_times) > 1:
                            print(f"    First access (filesystem): {fs_times[0]:.4f}s")
                            print(f"    Subsequent access (filesystem): {np.mean(fs_times[1:]):.4f}s")
        
        self.results["tests"][test_name] = results
        return results
    
    def profile_tiered_cache(self):
        """Profile the tiered cache performance."""
        test_name = "tiered_cache"
        print(f"\nProfiling {test_name}...")
        
        # Skip if filesystem is not available
        if not self.fs or not hasattr(self.fs, 'cache'):
            print("  Skipping: Filesystem or cache not available")
            return None
        
        # Get reference to the cache
        cache = self.fs.cache
        
        # First add all files to get their CIDs
        cids = {}
        for size, file_path in self.test_files.items():
            result = self.kit.ipfs_add_file(file_path)
            if 'Hash' in result:
                cids[size] = result['Hash']
        
        results = {}
        
        # Test 1: Cache hit rates for sequential access
        print("  Testing sequential access cache patterns...")
        cache_test_results = []
        
        # Clear caches
        try:
            cache.clear()
        except Exception as e:
            print(f"  Warning: Failed to clear cache: {e}")
        
        # Access each CID once in sequence
        for size, cid in cids.items():
            start_time = time.time()
            content = self.fs.cat(cid)
            elapsed = time.time() - start_time
            
            if hasattr(cache, 'get_stats'):
                stats = cache.get_stats()
            else:
                stats = {"memory_hits": 0, "disk_hits": 0, "misses": 0}
            
            cache_test_results.append({
                "cid": cid,
                "size": size,
                "elapsed": elapsed,
                "stats": stats
            })
        
        results["sequential_access"] = cache_test_results
        
        # Test 2: Cache hit rates for random access
        print("  Testing random access cache patterns...")
        cache_test_results = []
        
        # Clear caches
        try:
            cache.clear()
        except Exception as e:
            print(f"  Warning: Failed to clear cache: {e}")
        
        # Access CIDs randomly
        cid_list = list(cids.values())
        size_list = list(cids.keys())
        for _ in range(len(cids) * 3):  # 3x more accesses than items
            idx = random.randint(0, len(cid_list) - 1)
            cid = cid_list[idx]
            size = size_list[idx]
            
            start_time = time.time()
            content = self.fs.cat(cid)
            elapsed = time.time() - start_time
            
            if hasattr(cache, 'get_stats'):
                stats = cache.get_stats()
            else:
                stats = {"memory_hits": 0, "disk_hits": 0, "misses": 0}
            
            cache_test_results.append({
                "cid": cid,
                "size": size,
                "elapsed": elapsed,
                "stats": stats
            })
        
        results["random_access"] = cache_test_results
        
        # Test 3: Cache hit rates for repeated access to subset
        print("  Testing repeated access cache patterns...")
        cache_test_results = []
        
        # Clear caches
        try:
            cache.clear()
        except Exception as e:
            print(f"  Warning: Failed to clear cache: {e}")
        
        # Access a small subset of CIDs repeatedly
        subset = list(cids.items())[:2]  # First two items
        for _ in range(10):  # Repeat 10 times
            for size, cid in subset:
                start_time = time.time()
                content = self.fs.cat(cid)
                elapsed = time.time() - start_time
                
                if hasattr(cache, 'get_stats'):
                    stats = cache.get_stats()
                else:
                    stats = {"memory_hits": 0, "disk_hits": 0, "misses": 0}
                
                cache_test_results.append({
                    "cid": cid,
                    "size": size,
                    "elapsed": elapsed,
                    "stats": stats
                })
        
        results["repeated_access"] = cache_test_results
        
        self.results["tests"][test_name] = results
        return results
    
    def profile_api_operations(self):
        """Profile common API operations."""
        test_name = "api_operations"
        print(f"\nProfiling {test_name}...")
        
        results = {}
        
        # Test 1: Node ID operation
        print("  Testing node ID operation...")
        id_results = []
        for i in range(self.iterations):
            # Using low-level API
            low_level_result = self._run_with_profile(
                self.kit.ipfs_id
            )
            
            # Using high-level API
            high_level_result = self._run_with_profile(
                self.api.get_node_id
            )
            
            id_results.append({
                "iteration": i,
                "low_level_api": low_level_result,
                "high_level_api": high_level_result
            })
        
        results["node_id"] = id_results
        
        # Test 2: Version operation
        print("  Testing version operation...")
        version_results = []
        for i in range(self.iterations):
            # Using low-level API
            low_level_result = self._run_with_profile(
                self.kit.ipfs_version
            )
            
            # Using high-level API
            high_level_result = self._run_with_profile(
                self.api.get_version
            )
            
            version_results.append({
                "iteration": i,
                "low_level_api": low_level_result,
                "high_level_api": high_level_result
            })
        
        results["version"] = version_results
        
        # Calculate average times
        low_level_id_times = [r["low_level_api"]["elapsed"] for r in id_results 
                            if r["low_level_api"]["success"]]
        high_level_id_times = [r["high_level_api"]["elapsed"] for r in id_results 
                             if r["high_level_api"]["success"]]
        
        if low_level_id_times and high_level_id_times:
            print(f"    Node ID (low-level): {np.mean(low_level_id_times):.4f}s")
            print(f"    Node ID (high-level): {np.mean(high_level_id_times):.4f}s")
        
        low_level_version_times = [r["low_level_api"]["elapsed"] for r in version_results 
                                 if r["low_level_api"]["success"]]
        high_level_version_times = [r["high_level_api"]["elapsed"] for r in version_results 
                                  if r["high_level_api"]["success"]]
        
        if low_level_version_times and high_level_version_times:
            print(f"    Version (low-level): {np.mean(low_level_version_times):.4f}s")
            print(f"    Version (high-level): {np.mean(high_level_version_times):.4f}s")
            
        self.results["tests"][test_name] = results
        return results
    
    def run_all_tests(self):
        """Run all profiling tests."""
        print("\n===== Starting Performance Profiling =====")
        
        # Run all profiling tests
        self.profile_add_operation()
        self.profile_cat_operation()
        self.profile_tiered_cache()
        self.profile_api_operations()
        
        # Save results
        self.save_results()
        
        print("\n===== Performance Profiling Complete =====")
        print(f"Results saved to: {self.output_dir}")
        
        # Generate summary
        self.generate_summary()
    
    def save_results(self):
        """Save profiling results to file."""
        results_path = os.path.join(self.output_dir, "profiling_results.json")
        with open(results_path, 'w') as f:
            json.dump(self.results, f, indent=2)
    
    def generate_summary(self):
        """Generate a summary of profiling results."""
        print("\n===== Performance Profiling Summary =====")
        
        # Process add operation results
        if "add_operation" in self.results["tests"]:
            add_results = self.results["tests"]["add_operation"]
            print("\nAdd Operation Performance:")
            
            for size, size_results in add_results.items():
                low_level_times = [r["low_level_api"]["elapsed"] for r in size_results 
                                  if r["low_level_api"]["success"]]
                high_level_times = [r["high_level_api"]["elapsed"] for r in size_results 
                                   if r["high_level_api"]["success"]]
                
                if low_level_times and high_level_times:
                    print(f"  Size {size} bytes:")
                    print(f"    Low-level API: {np.mean(low_level_times):.4f}s ± {np.std(low_level_times):.4f}s")
                    print(f"    High-level API: {np.mean(high_level_times):.4f}s ± {np.std(high_level_times):.4f}s")
                    print(f"    Overhead: {(np.mean(high_level_times) - np.mean(low_level_times)) / np.mean(low_level_times) * 100:.1f}%")
        
        # Process cat operation results
        if "cat_operation" in self.results["tests"]:
            cat_results = self.results["tests"]["cat_operation"]
            print("\nCat Operation Performance:")
            
            for size, size_results in cat_results.items():
                low_level_times = [r["low_level_api"]["elapsed"] for r in size_results 
                                  if r["low_level_api"]["success"]]
                high_level_times = [r["high_level_api"]["elapsed"] for r in size_results 
                                   if r["high_level_api"]["success"]]
                
                if low_level_times and high_level_times:
                    print(f"  Size {size} bytes:")
                    
                    # First access (uncached)
                    if len(low_level_times) > 1:
                        print(f"    First access (uncached):")
                        print(f"      Low-level API: {low_level_times[0]:.4f}s")
                        print(f"      High-level API: {high_level_times[0]:.4f}s")
                    
                    # Subsequent accesses (potentially cached)
                    if len(low_level_times) > 1:
                        print(f"    Subsequent accesses (potentially cached):")
                        print(f"      Low-level API: {np.mean(low_level_times[1:]):.4f}s ± {np.std(low_level_times[1:]):.4f}s")
                        print(f"      High-level API: {np.mean(high_level_times[1:]):.4f}s ± {np.std(high_level_times[1:]):.4f}s")
                        
                        # Calculate cache speedup
                        low_level_speedup = low_level_times[0] / np.mean(low_level_times[1:])
                        high_level_speedup = high_level_times[0] / np.mean(high_level_times[1:])
                        print(f"      Cache speedup (low-level): {low_level_speedup:.1f}x")
                        print(f"      Cache speedup (high-level): {high_level_speedup:.1f}x")
                
                # Check filesystem API results
                fs_times = [r["filesystem_api"]["elapsed"] for r in size_results 
                           if r["filesystem_api"] and r["filesystem_api"]["success"]]
                
                if fs_times:
                    print(f"    Filesystem API: {np.mean(fs_times):.4f}s ± {np.std(fs_times):.4f}s")
                    
                    if len(fs_times) > 1:
                        print(f"      First access: {fs_times[0]:.4f}s")
                        print(f"      Subsequent accesses: {np.mean(fs_times[1:]):.4f}s ± {np.std(fs_times[1:]):.4f}s")
                        fs_speedup = fs_times[0] / np.mean(fs_times[1:])
                        print(f"      Cache speedup: {fs_speedup:.1f}x")
        
        # Process cache test results
        if "tiered_cache" in self.results["tests"]:
            cache_results = self.results["tests"]["tiered_cache"]
            
            if cache_results:
                print("\nCache Performance:")
                
                # Analyze sequential access
                if "sequential_access" in cache_results:
                    seq_results = cache_results["sequential_access"]
                    seq_times = [r["elapsed"] for r in seq_results]
                    
                    print(f"  Sequential access:")
                    print(f"    Average access time: {np.mean(seq_times):.4f}s ± {np.std(seq_times):.4f}s")
                    
                    # Calculate hit rates if available
                    if seq_results and "stats" in seq_results[-1]:
                        last_stats = seq_results[-1]["stats"]
                        if "memory_hits" in last_stats and "disk_hits" in last_stats and "misses" in last_stats:
                            total = last_stats["memory_hits"] + last_stats["disk_hits"] + last_stats["misses"]
                            if total > 0:
                                memory_hit_rate = last_stats["memory_hits"] / total * 100
                                disk_hit_rate = last_stats["disk_hits"] / total * 100
                                miss_rate = last_stats["misses"] / total * 100
                                
                                print(f"    Memory hit rate: {memory_hit_rate:.1f}%")
                                print(f"    Disk hit rate: {disk_hit_rate:.1f}%")
                                print(f"    Miss rate: {miss_rate:.1f}%")
                
                # Analyze random access
                if "random_access" in cache_results:
                    rand_results = cache_results["random_access"]
                    rand_times = [r["elapsed"] for r in rand_results]
                    
                    print(f"  Random access:")
                    print(f"    Average access time: {np.mean(rand_times):.4f}s ± {np.std(rand_times):.4f}s")
                    
                    # Calculate hit rates if available
                    if rand_results and "stats" in rand_results[-1]:
                        last_stats = rand_results[-1]["stats"]
                        if "memory_hits" in last_stats and "disk_hits" in last_stats and "misses" in last_stats:
                            total = last_stats["memory_hits"] + last_stats["disk_hits"] + last_stats["misses"]
                            if total > 0:
                                memory_hit_rate = last_stats["memory_hits"] / total * 100
                                disk_hit_rate = last_stats["disk_hits"] / total * 100
                                miss_rate = last_stats["misses"] / total * 100
                                
                                print(f"    Memory hit rate: {memory_hit_rate:.1f}%")
                                print(f"    Disk hit rate: {disk_hit_rate:.1f}%")
                                print(f"    Miss rate: {miss_rate:.1f}%")
                
                # Analyze repeated access
                if "repeated_access" in cache_results:
                    rep_results = cache_results["repeated_access"]
                    rep_times = [r["elapsed"] for r in rep_results]
                    
                    print(f"  Repeated access:")
                    print(f"    Average access time: {np.mean(rep_times):.4f}s ± {np.std(rep_times):.4f}s")
                    
                    # Calculate hit rates if available
                    if rep_results and "stats" in rep_results[-1]:
                        last_stats = rep_results[-1]["stats"]
                        if "memory_hits" in last_stats and "disk_hits" in last_stats and "misses" in last_stats:
                            total = last_stats["memory_hits"] + last_stats["disk_hits"] + last_stats["misses"]
                            if total > 0:
                                memory_hit_rate = last_stats["memory_hits"] / total * 100
                                disk_hit_rate = last_stats["disk_hits"] / total * 100
                                miss_rate = last_stats["misses"] / total * 100
                                
                                print(f"    Memory hit rate: {memory_hit_rate:.1f}%")
                                print(f"    Disk hit rate: {disk_hit_rate:.1f}%")
                                print(f"    Miss rate: {miss_rate:.1f}%")
        
        # Process API operations results
        if "api_operations" in self.results["tests"]:
            api_results = self.results["tests"]["api_operations"]
            
            print("\nAPI Operations Performance:")
            
            # Node ID operation
            if "node_id" in api_results:
                id_results = api_results["node_id"]
                low_level_times = [r["low_level_api"]["elapsed"] for r in id_results 
                                  if r["low_level_api"]["success"]]
                high_level_times = [r["high_level_api"]["elapsed"] for r in id_results 
                                   if r["high_level_api"]["success"]]
                
                if low_level_times and high_level_times:
                    print(f"  Node ID operation:")
                    print(f"    Low-level API: {np.mean(low_level_times):.4f}s ± {np.std(low_level_times):.4f}s")
                    print(f"    High-level API: {np.mean(high_level_times):.4f}s ± {np.std(high_level_times):.4f}s")
                    print(f"    Overhead: {(np.mean(high_level_times) - np.mean(low_level_times)) / np.mean(low_level_times) * 100:.1f}%")
            
            # Version operation
            if "version" in api_results:
                version_results = api_results["version"]
                low_level_times = [r["low_level_api"]["elapsed"] for r in version_results 
                                  if r["low_level_api"]["success"]]
                high_level_times = [r["high_level_api"]["elapsed"] for r in version_results 
                                   if r["high_level_api"]["success"]]
                
                if low_level_times and high_level_times:
                    print(f"  Version operation:")
                    print(f"    Low-level API: {np.mean(low_level_times):.4f}s ± {np.std(low_level_times):.4f}s")
                    print(f"    High-level API: {np.mean(high_level_times):.4f}s ± {np.std(high_level_times):.4f}s")
                    print(f"    Overhead: {(np.mean(high_level_times) - np.mean(low_level_times)) / np.mean(low_level_times) * 100:.1f}%")
        
        # Recommendations based on results
        print("\nPerformance Optimization Recommendations:")
        
        # Check for high-level API overhead
        high_level_overhead = False
        if "api_operations" in self.results["tests"]:
            api_results = self.results["tests"]["api_operations"]
            
            if "node_id" in api_results:
                id_results = api_results["node_id"]
                low_level_times = [r["low_level_api"]["elapsed"] for r in id_results 
                                  if r["low_level_api"]["success"]]
                high_level_times = [r["high_level_api"]["elapsed"] for r in id_results 
                                   if r["high_level_api"]["success"]]
                
                if low_level_times and high_level_times:
                    overhead = (np.mean(high_level_times) - np.mean(low_level_times)) / np.mean(low_level_times) * 100
                    if overhead > 50:  # More than 50% overhead
                        high_level_overhead = True
        
        if high_level_overhead:
            print("  1. High-level API has significant overhead. Consider:")
            print("     - Reducing validation in high-level API methods")
            print("     - Adding caching for frequently called methods")
            print("     - Optimizing error handling paths")
        
        # Check for cache performance
        cache_recommendations = []
        if "tiered_cache" in self.results["tests"]:
            cache_results = self.results["tests"]["tiered_cache"]
            
            if cache_results and "repeated_access" in cache_results:
                rep_results = cache_results["repeated_access"]
                if rep_results and "stats" in rep_results[-1]:
                    last_stats = rep_results[-1]["stats"]
                    if "memory_hits" in last_stats and "disk_hits" in last_stats and "misses" in last_stats:
                        total = last_stats["memory_hits"] + last_stats["disk_hits"] + last_stats["misses"]
                        if total > 0:
                            memory_hit_rate = last_stats["memory_hits"] / total * 100
                            if memory_hit_rate < 70:  # Less than 70% memory hit rate for repeated access
                                cache_recommendations.append(
                                    "Increase memory cache size to improve hit rates"
                                )
        
        if cache_recommendations:
            print("  2. Cache performance can be improved:")
            for i, rec in enumerate(cache_recommendations, 1):
                print(f"     - {rec}")
        
        # Check for add operation performance
        add_recommendations = []
        if "add_operation" in self.results["tests"]:
            add_results = self.results["tests"]["add_operation"]
            
            for size, size_results in add_results.items():
                low_level_times = [r["low_level_api"]["elapsed"] for r in size_results 
                                  if r["low_level_api"]["success"]]
                
                if low_level_times and int(size) > 100000 and np.mean(low_level_times) > 1.0:
                    # Large files taking >1s
                    add_recommendations.append(
                        f"Implement chunked uploads for large files (>100KB)"
                    )
                    break
        
        if add_recommendations:
            print("  3. Content addition performance:")
            for i, rec in enumerate(add_recommendations, 1):
                print(f"     - {rec}")
        
        print("\nDetailed results saved to:", os.path.join(self.output_dir, "profiling_results.json"))


def main():
    """Main entry point for the profiling tool."""
    parser = argparse.ArgumentParser(description="Performance profiling for ipfs_kit_py")
    parser.add_argument(
        "--output-dir", 
        help="Directory to store results (default: examples/profile_results_TIMESTAMP)"
    )
    parser.add_argument(
        "--iterations", 
        type=int, 
        default=10, 
        help="Number of iterations for each test (default: 10)"
    )
    parser.add_argument(
        "--file-sizes", 
        type=str, 
        default="1024,10240,102400,1048576", 
        help="Comma-separated list of file sizes in bytes to test (default: 1024,10240,102400,1048576)"
    )
    parser.add_argument(
        "--no-metrics", 
        action="store_true", 
        help="Disable detailed metrics collection"
    )
    parser.add_argument(
        "--test", 
        choices=["all", "add", "cat", "cache", "api"], 
        default="all", 
        help="Specific test to run (default: all)"
    )
    
    args = parser.parse_args()
    
    # Convert file sizes string to list of integers
    try:
        file_sizes = [int(size) for size in args.file_sizes.split(",")]
    except ValueError:
        print("Error: file-sizes must be comma-separated integers")
        sys.exit(1)
    
    # Create profiler
    profiler = PerformanceProfiler(
        output_dir=args.output_dir,
        iterations=args.iterations,
        file_sizes=file_sizes,
        include_metrics=not args.no_metrics
    )
    
    # Run tests
    if args.test == "all":
        profiler.run_all_tests()
    elif args.test == "add":
        profiler.profile_add_operation()
        profiler.save_results()
        profiler.generate_summary()
    elif args.test == "cat":
        profiler.profile_cat_operation()
        profiler.save_results()
        profiler.generate_summary()
    elif args.test == "cache":
        profiler.profile_tiered_cache()
        profiler.save_results()
        profiler.generate_summary()
    elif args.test == "api":
        profiler.profile_api_operations()
        profiler.save_results()
        profiler.generate_summary()


if __name__ == "__main__":
    main()