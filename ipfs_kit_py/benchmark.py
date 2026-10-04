#!/usr/bin/env python3
"""
IPFS Kit Performance Benchmarking Tool

This module provides comprehensive benchmarking capabilities for the ipfs_kit_py
library, enabling detailed performance analysis of various operations and components.
"""

import argparse
import json
import logging
import multiprocessing
import os
import sys
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional, Union

# Add the parent directory to sys.path if running as standalone script
script_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(script_dir) == "ipfs_kit_py":
    sys.path.insert(0, os.path.dirname(script_dir))

from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.performance_metrics import PerformanceMetrics, ProfilingContext

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class IPFSKitBenchmark:
    """
    Comprehensive benchmark tool for IPFS Kit operations.

    This class provides methods to thoroughly benchmark different aspects of
    the IPFS Kit library, including:

    1. Basic operations (add, cat, pin, etc.)
    2. Tiered caching system performance
    3. FSSpec integration performance
    4. Networking and P2P operations
    5. Cluster operations and coordination
    6. Advanced features like AI/ML integration
    """

    def __init__(
        self,
        metrics_dir=None,
        role="leecher",
        daemon_port=None,
        parallelism=1,
        iterations=5,
        warmup=1,
    ):
        """
        Initialize the benchmark tool.

        Args:
            metrics_dir: Directory to store performance metrics
            role: IPFS node role to use for benchmarking ('master', 'worker', 'leecher')
            daemon_port: IPFS daemon port, if None uses default 5001
            parallelism: Number of parallel operations to run
            iterations: Number of iterations for each benchmark
            warmup: Number of warmup iterations before timing
        """
        self.metrics_dir = metrics_dir or os.path.join(os.path.expanduser("~"), ".ipfs_benchmark")
        self.role = role
        self.daemon_port = daemon_port
        self.parallelism = parallelism
        self.iterations = iterations
        self.warmup = warmup
        self.correlation_id = str(uuid.uuid4())

        # Create metrics directory if it doesn't exist
        os.makedirs(self.metrics_dir, exist_ok=True)

        # Initialize performance metrics
        self.metrics = PerformanceMetrics(
            metrics_dir=os.path.join(self.metrics_dir, "raw_metrics"),
            enable_logging=True,
            track_system_resources=True,
            collection_interval=60,
        )

        # Initialize IPFS Kit instance
        daemon_config = {}
        if daemon_port:
            daemon_config["port"] = daemon_port

        self.kit = ipfs_kit(role=self.role, daemon_config=daemon_config)

        # Get filesystem with metrics enabled
        self.fs = self.kit.get_filesystem(enable_metrics=True)

        # Benchmark results
        self.results = {
            "timestamp": time.time(),
            "config": {
                "role": self.role,
                "parallelism": self.parallelism,
                "iterations": self.iterations,
                "warmup": self.warmup,
            },
            "benchmarks": {},
        }

    def _create_test_files(self, sizes=None):
        """
        Create temporary test files of various sizes.

        Args:
            sizes: Dictionary mapping names to sizes in bytes, e.g.,
                  {'small': 1024, 'medium': 1024*1024, 'large': 10*1024*1024}

        Returns:
            Dictionary mapping names to (path, content) tuples
        """
        if sizes is None:
            sizes = {
                "tiny": 1024,  # 1KB
                "small": 10 * 1024,  # 10KB
                "medium": 1024 * 1024,  # 1MB
                "large": 10 * 1024 * 1024,  # 10MB
            }

        files = {}
        for name, size in sizes.items():
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{name}.dat") as f:
                # Generate semi-random content with some patterns for compression tests
                if size <= 1024 * 1024:  # For files up to 1MB, use semi-random data
                    pattern = os.urandom(min(10240, size // 10))  # Create a random pattern
                    repeats = size // len(pattern) + 1
                    content = pattern * repeats
                    content = content[:size]  # Truncate to exact size
                else:
                    # For larger files, use blocks of repeating and random data
                    content = b""
                    block_size = 1024 * 64  # 64KB blocks
                    while len(content) < size:
                        if len(content) % (block_size * 2) < block_size:
                            # Add a block of repeating data
                            pattern = os.urandom(1024)  # 1KB random pattern
                            block = pattern * (block_size // 1024)
                        else:
                            # Add a block of random data
                            block = os.urandom(block_size)

                        content += block
                        if len(content) >= size:
                            content = content[:size]  # Truncate to exact size
                            break

                f.write(content)
                files[name] = (f.name, content)

        return files

    def _cleanup_test_files(self, files):
        """
        Clean up temporary test files.

        Args:
            files: Dictionary of test files from _create_test_files
        """
        for name, (path, _) in files.items():
            try:
                os.unlink(path)
            except Exception as e:
                logger.warning(f"Error removing test file {path}: {e}")

    def benchmark_core_operations(self):
        """
        Benchmark core IPFS operations: add, cat, pin, etc.

        Returns:
            Dictionary with benchmark results
        """
        logger.info("Starting core operations benchmark...")

        # Create test files
        files = self._create_test_files()
        results = {}

        try:
            # Test 1: Add operation benchmark
            add_results = {}
            for name, (path, content) in files.items():
                add_timings = []

                # Warmup iterations
                for _ in range(self.warmup):
                    self.kit.ipfs_add_file(path)

                # Timed iterations
                for i in range(self.iterations):
                    with ProfilingContext(
                        self.metrics, f"add_{name}", self.correlation_id
                    ) as profile:
                        add_result = self.kit.ipfs_add_file(path)
                        if add_result and "Hash" in add_result:
                            cid = add_result["Hash"]
                        else:
                            logger.warning(f"Failed to add file {name} (iteration {i})")
                            continue

                        # Record the CID for later use
                        if i == 0:  # Only need to save one CID per file size
                            add_results[name] = {"cid": cid, "size": len(content)}

                # Get statistics from metrics
                stats = self.metrics.get_operation_stats(f"add_{name}")
                add_results[name].update(stats)

                # Calculate throughput
                if stats.get("avg", 0) > 0:
                    throughput = len(content) / stats["avg"]
                    add_results[name]["throughput_bytes_per_second"] = throughput

            results["add"] = add_results

            # Test 2: Cat operation benchmark
            cat_results = {}
            for name, info in add_results.items():
                cid = info["cid"]

                # Warmup iterations
                for _ in range(self.warmup):
                    self.kit.ipfs_cat(cid)

                # Timed iterations
                for i in range(self.iterations):
                    with ProfilingContext(
                        self.metrics, f"cat_{name}", self.correlation_id
                    ) as profile:
                        content = self.kit.ipfs_cat(cid)
                        if not content:
                            logger.warning(f"Failed to cat file {name} (iteration {i})")

                # Get statistics from metrics
                stats = self.metrics.get_operation_stats(f"cat_{name}")
                cat_results[name] = {"cid": cid, "size": info["size"]}
                cat_results[name].update(stats)

                # Calculate throughput
                if stats.get("avg", 0) > 0:
                    throughput = info["size"] / stats["avg"]
                    cat_results[name]["throughput_bytes_per_second"] = throughput

            results["cat"] = cat_results

            # Test 3: Pin operation benchmark
            pin_results = {}
            for name, info in add_results.items():
                cid = info["cid"]

                # First unpin to make sure we're testing pinning, not checking existing pins
                try:
                    self.kit.ipfs_unpin(cid)
                except Exception:
                    pass

                # Warmup iterations
                for _ in range(self.warmup):
                    self.kit.ipfs_pin_add(cid)
                    self.kit.ipfs_unpin(cid)

                # Pin timing
                for i in range(self.iterations):
                    # Unpin first so we're actually pinning
                    self.kit.ipfs_unpin(cid)

                    with ProfilingContext(
                        self.metrics, f"pin_{name}", self.correlation_id
                    ) as profile:
                        pin_result = self.kit.ipfs_pin_add(cid)
                        if not pin_result or not pin_result.get("success", False):
                            logger.warning(f"Failed to pin file {name} (iteration {i})")

                # Get statistics from metrics
                stats = self.metrics.get_operation_stats(f"pin_{name}")
                pin_results[name] = {"cid": cid, "size": info["size"]}
                pin_results[name].update(stats)

            results["pin"] = pin_results

            # Test 4: Unpin operation benchmark
            unpin_results = {}
            for name, info in add_results.items():
                cid = info["cid"]

                # Make sure it's pinned first
                try:
                    self.kit.ipfs_pin_add(cid)
                except Exception:
                    pass

                # Warmup iterations
                for _ in range(self.warmup):
                    self.kit.ipfs_unpin(cid)
                    self.kit.ipfs_pin_add(cid)

                # Unpin timing
                for i in range(self.iterations):
                    # Pin first so we're actually unpinning
                    self.kit.ipfs_pin_add(cid)

                    with ProfilingContext(
                        self.metrics, f"unpin_{name}", self.correlation_id
                    ) as profile:
                        unpin_result = self.kit.ipfs_unpin(cid)
                        if not unpin_result or not unpin_result.get("success", False):
                            logger.warning(f"Failed to unpin file {name} (iteration {i})")

                # Get statistics from metrics
                stats = self.metrics.get_operation_stats(f"unpin_{name}")
                unpin_results[name] = {"cid": cid, "size": info["size"]}
                unpin_results[name].update(stats)

            results["unpin"] = unpin_results

            # Test 5: Batch add operation benchmark
            batch_files = {}
            batch_sizes = {}
            for name, size in {
                "batch_small": 10 * 1024,  # 10KB x 10
                "batch_medium": 100 * 1024,  # 100KB x 10
            }.items():
                batch = []
                total_size = 0
                for i in range(10):  # Create 10 files for each batch
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{name}_{i}.dat") as f:
                        content = os.urandom(size)
                        f.write(content)
                        batch.append(f.name)
                        total_size += len(content)
                batch_files[name] = batch
                batch_sizes[name] = total_size

            batch_results = {}
            for name, batch in batch_files.items():
                # Warmup iterations
                for _ in range(self.warmup):
                    self.kit.ipfs_add_batch(batch)

                # Timed iterations
                for i in range(self.iterations):
                    with ProfilingContext(
                        self.metrics, f"batch_add_{name}", self.correlation_id
                    ) as profile:
                        batch_result = self.kit.ipfs_add_batch(batch)
                        if not batch_result:
                            logger.warning(f"Failed to add batch {name} (iteration {i})")

                # Get statistics from metrics
                stats = self.metrics.get_operation_stats(f"batch_add_{name}")
                batch_results[name] = {"file_count": len(batch), "total_size": batch_sizes[name]}
                batch_results[name].update(stats)

                # Calculate throughput
                if stats.get("avg", 0) > 0:
                    throughput = batch_sizes[name] / stats["avg"]
                    batch_results[name]["throughput_bytes_per_second"] = throughput
                    files_per_sec = len(batch) / stats["avg"]
                    batch_results[name]["throughput_files_per_second"] = files_per_sec

                # Clean up batch files
                for path in batch:
                    try:
                        os.unlink(path)
                    except Exception:
                        pass

            results["batch_add"] = batch_results

        finally:
            # Clean up test files
            self._cleanup_test_files(files)

        # Add to overall results
        self.results["benchmarks"]["core_operations"] = results

        # Return results for this benchmark
        return results

    def benchmark_caching(self):
        """
        Benchmark tiered caching performance.

        Tests cache hit rates, promotion/demotion, and performance
        across different access patterns.

        Returns:
            Dictionary with benchmark results
        """
        logger.info("Starting cache performance benchmark...")

        # Create test files
        files = self._create_test_files()
        results = {}

        try:
            # Setup - add files to IPFS and get their CIDs
            cids = {}
            for name, (path, content) in files.items():
                result = self.kit.ipfs_add_file(path)
                if result and "Hash" in result:
                    cids[name] = {"cid": result["Hash"], "size": len(content)}

            # Clear caches to start with a clean slate
            self.fs.clear_cache()

            # Test 1: Sequential access pattern
            sequential_results = self._run_cache_access_pattern(cids, "sequential", iterations=5)
            results["sequential"] = sequential_results

            # Test 2: Random access pattern
            random_results = self._run_cache_access_pattern(cids, "random", iterations=5)
            results["random"] = random_results

            # Test 3: Repeated access to a small set (hot spot)
            repeated_results = self._run_cache_access_pattern(cids, "repeated", iterations=5)
            results["repeated"] = repeated_results

            # Test 4: Cache tier promotion
            # Clear caches first
            self.fs.clear_cache()

            promotion_results = {}
            for name, info in cids.items():
                cid = info["cid"]

                # First access - should be a cache miss
                with ProfilingContext(
                    self.metrics, f"promotion_first_{name}", self.correlation_id
                ) as profile:
                    content = self.kit.ipfs_cat(cid)

                # Get heat score after first access
                heat_score_1 = self.fs.cache.get_heat_score(cid)

                # Access multiple times to increase heat score
                for _ in range(5):
                    self.kit.ipfs_cat(cid)

                # Get heat score after multiple accesses
                heat_score_n = self.fs.cache.get_heat_score(cid)

                promotion_results[name] = {
                    "initial_heat_score": heat_score_1,
                    "final_heat_score": heat_score_n,
                    "heat_increase": heat_score_n - heat_score_1,
                }

            results["promotion"] = promotion_results

        finally:
            # Clean up test files
            self._cleanup_test_files(files)

        # Add to overall results
        self.results["benchmarks"]["caching"] = results

        # Return results for this benchmark
        return results

    def _run_cache_access_pattern(self, cids, pattern, iterations=5):
        """
        Run a cache access pattern benchmark.

        Args:
            cids: Dictionary of CIDs to access
            pattern: Access pattern ('sequential', 'random', or 'repeated')
            iterations: Number of access iterations

        Returns:
            Dictionary with benchmark results
        """
        import random

        fs = self.fs
        results = {"pattern": pattern, "access_sequence": [], "cache_stats": {}}

        # Reset cache statistics
        start_hits = fs.performance_metrics.cache["hits"]
        start_misses = fs.performance_metrics.cache["misses"]

        # Create access sequence based on pattern
        access_sequence = []
        cid_list = list(cids.keys())

        if pattern == "sequential":
            # Access each CID once in order, repeated for iterations
            for _ in range(iterations):
                access_sequence.extend(cid_list)

        elif pattern == "random":
            # Random access pattern
            for _ in range(iterations):
                random_order = cid_list.copy()
                random.shuffle(random_order)
                access_sequence.extend(random_order)

        elif pattern == "repeated":
            # Repeatedly access a small set of CIDs (hot spot)
            hot_cids = random.sample(cid_list, min(2, len(cid_list)))
            for _ in range(iterations * len(cid_list) // len(hot_cids)):
                access_sequence.extend(hot_cids)

        # Run the access pattern
        timings = {}
        for i, name in enumerate(access_sequence):
            # Record the access for analysis
            results["access_sequence"].append(name)

            cid = cids[name]["cid"]

            # Access the content
            with ProfilingContext(
                self.metrics, f"cache_{pattern}_{name}", self.correlation_id
            ) as profile:
                content = fs.cat(cid)

                if not content:
                    logger.warning(f"Failed to access content for {name} in {pattern} pattern")

            # Get operations stats so far
            if name not in timings:
                timings[name] = []

            # Only record timing after we've accessed this CID at least once
            # (to separate the cold and warm cache timings)
            stats = self.metrics.get_operation_stats(f"cache_{pattern}_{name}")
            if stats.get("count", 0) > 0:
                timings[name].append({"position": i, "latency": stats.get("avg", 0)})

        # Calculate cache statistics
        end_hits = fs.performance_metrics.cache["hits"]
        end_misses = fs.performance_metrics.cache["misses"]

        total_hits = end_hits - start_hits
        total_misses = end_misses - start_misses
        total = total_hits + total_misses

        if total > 0:
            hit_rate = total_hits / total
        else:
            hit_rate = 0

        results["cache_stats"] = {
            "hits": total_hits,
            "misses": total_misses,
            "total": total,
            "hit_rate": hit_rate,
        }

        # Process timings - calculate average latency for each CID
        # Split into first access (cold cache) and subsequent accesses (warm cache)
        latency_data = {}
        for name, data in timings.items():
            # Skip if no timing data
            if not data:
                continue

            cold_latencies = [item["latency"] for item in data[:1]]
            warm_latencies = [item["latency"] for item in data[1:]]

            latency_data[name] = {
                "cold_cache": {
                    "count": len(cold_latencies),
                    "avg": sum(cold_latencies) / len(cold_latencies) if cold_latencies else 0,
                },
                "warm_cache": {
                    "count": len(warm_latencies),
                    "avg": sum(warm_latencies) / len(warm_latencies) if warm_latencies else 0,
                },
            }

            # Calculate speedup
            if cold_latencies and warm_latencies:
                cold_avg = sum(cold_latencies) / len(cold_latencies)
                warm_avg = sum(warm_latencies) / len(warm_latencies)

                if warm_avg > 0:
                    speedup = cold_avg / warm_avg
                    latency_data[name]["speedup"] = speedup

        results["latency"] = latency_data

        return results

    def benchmark_fsspec_operations(self):
        """
        Benchmark FSSpec operations.

        Tests the FSSpec integration with various file operations and access patterns.

        Returns:
            Dictionary with benchmark results
        """
        logger.info("Starting FSSpec operations benchmark...")

        # Create test files
        files = self._create_test_files(
            {
                "small": 10 * 1024,  # 10KB
                "medium": 100 * 1024,  # 100KB
            }
        )
        results = {}

        try:
            # Setup - add files to IPFS and get their CIDs
            cids = {}
            for name, (path, content) in files.items():
                result = self.kit.ipfs_add_file(path)
                if result and "Hash" in result:
                    cids[name] = {"cid": result["Hash"], "size": len(content)}

            # Clear caches to start with a clean slate
            self.fs.clear_cache()

            # Test 1: Standard filesystem operations
            fs_ops_results = {}

            # Test open and read
            for name, info in cids.items():
                cid = info["cid"]
                path = f"ipfs://{cid}"

                # Warmup
                with self.fs.open(path, "rb") as f:
                    f.read()

                # Open operation
                open_timings = []
                for i in range(self.iterations):
                    with ProfilingContext(
                        self.metrics, f"fsspec_open_{name}", self.correlation_id
                    ) as profile:
                        f = self.fs.open(path, "rb")

                    # Don't forget to close the file
                    f.close()

                # Read operation - small reads
                small_read_timings = []
                with self.fs.open(path, "rb") as f:
                    for i in range(self.iterations):
                        # Reset to beginning
                        f.seek(0)

                        with ProfilingContext(
                            self.metrics, f"fsspec_read_small_{name}", self.correlation_id
                        ) as profile:
                            # Read in small chunks
                            chunk_size = 1024  # 1KB chunks
                            while True:
                                chunk = f.read(chunk_size)
                                if not chunk:
                                    break

                # Read operation - full file read
                full_read_timings = []
                for i in range(self.iterations):
                    with self.fs.open(path, "rb") as f:
                        with ProfilingContext(
                            self.metrics, f"fsspec_read_full_{name}", self.correlation_id
                        ) as profile:
                            content = f.read()

                # Seek operation
                seek_timings = []
                with self.fs.open(path, "rb") as f:
                    for i in range(self.iterations):
                        # Seek to random positions
                        positions = [
                            0,  # Start
                            info["size"] // 2,  # Middle
                            info["size"] - 100,  # Near end
                            info["size"] // 4,  # Quarter
                            info["size"] * 3 // 4,  # Three-quarters
                        ]

                        for pos in positions:
                            with ProfilingContext(
                                self.metrics, f"fsspec_seek_{name}", self.correlation_id
                            ) as profile:
                                f.seek(pos)
                                # Read a small amount to verify seek worked
                                data = f.read(10)

                # Get statistics
                fs_ops_results[name] = {
                    "open": self.metrics.get_operation_stats(f"fsspec_open_{name}"),
                    "read_small": self.metrics.get_operation_stats(f"fsspec_read_small_{name}"),
                    "read_full": self.metrics.get_operation_stats(f"fsspec_read_full_{name}"),
                    "seek": self.metrics.get_operation_stats(f"fsspec_seek_{name}"),
                }

                # Calculate read throughput
                if fs_ops_results[name]["read_full"].get("avg", 0) > 0:
                    throughput = info["size"] / fs_ops_results[name]["read_full"]["avg"]
                    fs_ops_results[name]["read_throughput"] = throughput

            results["fs_operations"] = fs_ops_results

            # Test 2: Directory operations
            # Create a test directory structure
            dir_structure = {}
            with tempfile.TemporaryDirectory() as tmpdir:
                # Create some folders
                os.makedirs(os.path.join(tmpdir, "dir1/subdir1"), exist_ok=True)
                os.makedirs(os.path.join(tmpdir, "dir1/subdir2"), exist_ok=True)
                os.makedirs(os.path.join(tmpdir, "dir2"), exist_ok=True)

                # Create some files
                for i in range(5):
                    with open(os.path.join(tmpdir, f"file{i}.txt"), "w") as f:
                        f.write(f"Test file {i}" * 100)

                    with open(os.path.join(tmpdir, f"dir1/file{i}.txt"), "w") as f:
                        f.write(f"Test file in dir1 {i}" * 100)

                    with open(os.path.join(tmpdir, f"dir1/subdir1/file{i}.txt"), "w") as f:
                        f.write(f"Test file in subdir1 {i}" * 100)

                    with open(os.path.join(tmpdir, f"dir2/file{i}.txt"), "w") as f:
                        f.write(f"Test file in dir2 {i}" * 100)

                # Add directory to IPFS
                result = self.kit.ipfs_add_path(tmpdir)
                if result and "Hash" in result:
                    dir_cid = result["Hash"]
                    path = f"ipfs://{dir_cid}"

                    # Test ls operation
                    with ProfilingContext(
                        self.metrics, "fsspec_ls_root", self.correlation_id
                    ) as profile:
                        root_listing = self.fs.ls(path)

                    # Test ls on subdirectory
                    with ProfilingContext(
                        self.metrics, "fsspec_ls_subdir", self.correlation_id
                    ) as profile:
                        subdir_listing = self.fs.ls(f"{path}/dir1")

                    # Test glob operation
                    with ProfilingContext(
                        self.metrics, "fsspec_glob", self.correlation_id
                    ) as profile:
                        glob_result = self.fs.glob(f"{path}/**/*.txt")

                    # Test find operation
                    with ProfilingContext(
                        self.metrics, "fsspec_find", self.correlation_id
                    ) as profile:
                        find_result = self.fs.find(path)

                    # Get statistics
                    dir_ops_results = {
                        "ls_root": self.metrics.get_operation_stats("fsspec_ls_root"),
                        "ls_subdir": self.metrics.get_operation_stats("fsspec_ls_subdir"),
                        "glob": self.metrics.get_operation_stats("fsspec_glob"),
                        "find": self.metrics.get_operation_stats("fsspec_find"),
                        "dir_size": len(root_listing) if root_listing else 0,
                        "glob_matches": len(glob_result) if glob_result else 0,
                        "find_matches": len(find_result) if find_result else 0,
                    }

                    results["directory_operations"] = dir_ops_results

        finally:
            # Clean up test files
            self._cleanup_test_files(files)

        # Add to overall results
        self.results["benchmarks"]["fsspec_operations"] = results

        # Return results for this benchmark
        return results

    def benchmark_parallel_operations(self):
        """
        Benchmark parallel operations performance.

        Tests how well the IPFS Kit scales with parallel operations.

        Returns:
            Dictionary with benchmark results
        """
        logger.info("Starting parallel operations benchmark...")

        # Create test files - smaller ones for parallel testing
        files = self._create_test_files(
            {
                "tiny": 1024,  # 1KB
                "small": 10 * 1024,  # 10KB
                "medium": 100 * 1024,  # 100KB
            }
        )
        results = {}

        try:
            # Setup - add files to IPFS and get their CIDs
            cids = {}
            for name, (path, content) in files.items():
                result = self.kit.ipfs_add_file(path)
                if result and "Hash" in result:
                    cids[name] = {"cid": result["Hash"], "size": len(content)}

            # Test parallel add operations with different parallelism levels
            parallel_add_results = {}
            for parallelism in [1, 2, 4, 8]:
                if parallelism > multiprocessing.cpu_count():
                    # Skip if parallelism exceeds CPU count
                    continue

                # Create multiple test files for parallel add
                parallel_files = {}
                for i in range(parallelism * 5):  # 5 files per worker
                    name = f"parallel_{i}"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{name}.dat") as f:
                        # Create files with varying sizes for realistic testing
                        size = random.randint(1024, 100 * 1024)
                        content = os.urandom(size)
                        f.write(content)
                        parallel_files[name] = (f.name, size)

                # Run parallel add test
                with ProfilingContext(
                    self.metrics, f"parallel_add_{parallelism}", self.correlation_id
                ) as profile:
                    # Use ThreadPoolExecutor to run parallel operations
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor(max_workers=parallelism) as executor:
                        # Submit add operations
                        futures = {}
                        for name, (path, _) in parallel_files.items():
                            future = executor.submit(self.kit.ipfs_add_file, path)
                            futures[future] = name

                        # Collect results
                        results_count = 0
                        for future in concurrent.futures.as_completed(futures):
                            name = futures[future]
                            try:
                                result = future.result()
                                if result and "Hash" in result:
                                    results_count += 1
                            except Exception as e:
                                logger.warning(f"Error in parallel add {name}: {e}")

                # Get statistics
                stats = self.metrics.get_operation_stats(f"parallel_add_{parallelism}")
                parallel_add_results[parallelism] = {
                    "workers": parallelism,
                    "files": len(parallel_files),
                    "successful": results_count,
                }
                parallel_add_results[parallelism].update(stats)

                # Calculate files per second
                if stats.get("avg", 0) > 0:
                    files_per_sec = results_count / stats["avg"]
                    parallel_add_results[parallelism]["files_per_second"] = files_per_sec

                # Clean up parallel files
                for name, (path, _) in parallel_files.items():
                    try:
                        os.unlink(path)
                    except Exception:
                        pass

            results["parallel_add"] = parallel_add_results

            # Test parallel retrieve operations with different parallelism levels
            parallel_cat_results = {}
            for parallelism in [1, 2, 4, 8]:
                if parallelism > multiprocessing.cpu_count():
                    # Skip if parallelism exceeds CPU count
                    continue

                # Use the CIDs we already have, but repeat them to have enough
                parallel_cids = []
                for name, info in cids.items():
                    # Add each CID multiple times to have enough for the test
                    for _ in range(parallelism * 2):
                        parallel_cids.append((name, info["cid"]))

                # Run parallel cat test
                with ProfilingContext(
                    self.metrics, f"parallel_cat_{parallelism}", self.correlation_id
                ) as profile:
                    # Use ThreadPoolExecutor to run parallel operations
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor(max_workers=parallelism) as executor:
                        # Submit cat operations
                        futures = {}
                        for i, (name, cid) in enumerate(parallel_cids):
                            future = executor.submit(self.kit.ipfs_cat, cid)
                            futures[future] = name

                        # Collect results
                        results_count = 0
                        for future in concurrent.futures.as_completed(futures):
                            name = futures[future]
                            try:
                                content = future.result()
                                if content:
                                    results_count += 1
                            except Exception as e:
                                logger.warning(f"Error in parallel cat {name}: {e}")

                # Get statistics
                stats = self.metrics.get_operation_stats(f"parallel_cat_{parallelism}")
                parallel_cat_results[parallelism] = {
                    "workers": parallelism,
                    "requests": len(parallel_cids),
                    "successful": results_count,
                }
                parallel_cat_results[parallelism].update(stats)

                # Calculate requests per second
                if stats.get("avg", 0) > 0:
                    reqs_per_sec = results_count / stats["avg"]
                    parallel_cat_results[parallelism]["requests_per_second"] = reqs_per_sec

            results["parallel_cat"] = parallel_cat_results

        finally:
            # Clean up test files
            self._cleanup_test_files(files)

        # Add to overall results
        self.results["benchmarks"]["parallel_operations"] = results

        # Return results for this benchmark
        return results

    def run_all_benchmarks(self):
        """
        Run all benchmarks.

        Returns:
            Dictionary with all benchmark results
        """
        # Record start time
        start_time = time.time()

        # Set a correlation ID for this full benchmark run
        self.correlation_id = str(uuid.uuid4())
        self.metrics.set_correlation_id(self.correlation_id)

        # Run individual benchmarks
        logger.info("Starting comprehensive benchmark suite...")

        # Core operations
        self.benchmark_core_operations()

        # Caching performance
        self.benchmark_caching()

        # FSSpec operations
        self.benchmark_fsspec_operations()

        # Parallel operations
        self.benchmark_parallel_operations()

        # Record end time and duration
        end_time = time.time()
        duration = end_time - start_time

        # Add summary metrics
        self.results["duration"] = duration
        self.results["correlation_id"] = self.correlation_id

        # Add system information
        import platform

        import psutil

        self.results["system"] = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "ipfs_version": self.kit.ipfs_version(),
        }

        # Generate metrics report
        metrics_analysis = self.metrics.analyze_metrics()
        self.results["metrics_analysis"] = metrics_analysis

        # Generate report
        report = self.metrics.generate_report(output_format="markdown")

        # Save results
        results_path = os.path.join(self.metrics_dir, f"benchmark_results_{int(start_time)}.json")
        with open(results_path, "w") as f:
            json.dump(self.results, f, indent=2)

        report_path = os.path.join(self.metrics_dir, f"benchmark_report_{int(start_time)}.md")
        with open(report_path, "w") as f:
            f.write(report)

        logger.info(f"Benchmark complete. Results saved to {results_path}")
        logger.info(f"Performance report saved to {report_path}")

        return self.results

    def save_results(self, path=None):
        """
        Save benchmark results to a file.

        Args:
            path: Path to save results to (default: metrics_dir/benchmark_results_<timestamp>.json)

        Returns:
            Path to saved results file
        """
        if not path:
            path = os.path.join(self.metrics_dir, f"benchmark_results_{int(time.time())}.json")

        with open(path, "w") as f:
            json.dump(self.results, f, indent=2)

        logger.info(f"Benchmark results saved to {path}")

        return path


def main():
    """Main function for running the benchmark script."""
    parser = argparse.ArgumentParser(description="IPFS Kit Benchmark Tool")
    parser.add_argument("--metrics-dir", help="Directory to store metrics and results")
    parser.add_argument(
        "--role",
        default="leecher",
        choices=["master", "worker", "leecher"],
        help="IPFS node role to use",
    )
    parser.add_argument("--daemon-port", type=int, help="IPFS daemon API port")
    parser.add_argument(
        "--parallelism", type=int, default=2, help="Number of parallel operations to run"
    )
    parser.add_argument(
        "--iterations", type=int, default=5, help="Number of iterations for each benchmark"
    )
    parser.add_argument(
        "--warmup", type=int, default=1, help="Number of warmup iterations before timing"
    )
    parser.add_argument(
        "--benchmark",
        choices=["all", "core", "caching", "fsspec", "parallel"],
        default="all",
        help="Which benchmark to run",
    )

    args = parser.parse_args()

    # Create benchmark instance
    benchmark = IPFSKitBenchmark(
        metrics_dir=args.metrics_dir,
        role=args.role,
        daemon_port=args.daemon_port,
        parallelism=args.parallelism,
        iterations=args.iterations,
        warmup=args.warmup,
    )

    # Run requested benchmark
    if args.benchmark == "all":
        results = benchmark.run_all_benchmarks()
    elif args.benchmark == "core":
        results = benchmark.benchmark_core_operations()
    elif args.benchmark == "caching":
        results = benchmark.benchmark_caching()
    elif args.benchmark == "fsspec":
        results = benchmark.benchmark_fsspec_operations()
    elif args.benchmark == "parallel":
        results = benchmark.benchmark_parallel_operations()

    # Save results
    benchmark.save_results()

    # Shutdown metrics handler
    benchmark.metrics.shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
