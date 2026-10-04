"""
Performance Benchmarking Tool for IPFS Prefetching.

This module provides tools for benchmarking and analyzing the performance
of different prefetching strategies in the ipfs_kit_py library.
"""

import time
import json
import os
import logging
import random
import argparse
import tempfile
import concurrent.futures
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
import csv

try:
    import matplotlib.pyplot as plt
    import numpy as np
    HAS_VISUALIZATION = True
except ImportError:
    HAS_VISUALIZATION = False

from ipfs_kit_py.tiered_cache_manager import TieredCacheManager
from ipfs_kit_py.predictive_cache_manager import PredictiveCacheManager
from ipfs_kit_py.predictive_prefetching import create_prefetching_engine

# Initialize logger
logger = logging.getLogger(__name__)


class PrefetchBenchmark:
    """Benchmarking tool for prefetching strategies.
    
    This class provides methods for measuring the performance of different
    prefetching strategies under various access patterns.
    """
    
    def __init__(self, 
                cache_config: Optional[Dict[str, Any]] = None,
                prefetch_config: Optional[Dict[str, Any]] = None,
                output_dir: Optional[str] = None):
        """Initialize the benchmark tool.
        
        Args:
            cache_config: Configuration for TieredCacheManager
            prefetch_config: Configuration for predictive prefetching
            output_dir: Directory for benchmark results
        """
        # Create temporary directory for cache if not specified
        self.temp_dir = tempfile.mkdtemp()
        
        # Default cache configuration
        default_cache_config = {
            "memory_cache_size": 10 * 1024 * 1024,  # 10MB
            "local_cache_size": 100 * 1024 * 1024,  # 100MB
            "local_cache_path": self.temp_dir,
            "max_item_size": 1 * 1024 * 1024,       # 1MB
            "prefetch_enabled": True,
            "max_prefetch_threads": 4,
        }
        
        # Merge with provided config
        self.cache_config = default_cache_config.copy()
        if cache_config:
            self.cache_config.update(cache_config)
        
        # Default prefetch configuration
        default_prefetch_config = {
            "markov_enabled": True,
            "graph_enabled": True,
            "content_type_enabled": True,
            "max_prefetch_items": 5,
            "prefetch_threshold": 0.3,
            "model_storage_path": os.path.join(self.temp_dir, "models"),
        }
        
        # Merge with provided config
        self.prefetch_config = default_prefetch_config.copy()
        if prefetch_config:
            self.prefetch_config.update(prefetch_config)
        
        # Set up output directory
        self.output_dir = output_dir or os.path.join(self.temp_dir, "benchmark_results")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize caches with different strategies
        self.caches = {
            "no_prefetch": TieredCacheManager({**self.cache_config, "prefetch_enabled": False}),
            "basic_prefetch": TieredCacheManager(self.cache_config),
            "predictive_prefetch": self._create_predictive_cache()
        }
        
        # Metrics
        self.metrics = defaultdict(dict)
        
        # Test content
        self.test_content = {}
    
    def _create_predictive_cache(self) -> TieredCacheManager:
        """Create cache with predictive prefetching."""
        # Create base cache
        cache = TieredCacheManager(self.cache_config)
        
        # Create predictive manager
        predictive_manager = create_prefetching_engine(self.prefetch_config)
        
        # Connect to cache
        cache.predictive_manager = predictive_manager
        
        # Override _identify_prefetch_candidates method to use predictive engine
        original_identify_candidates = cache._identify_prefetch_candidates
        
        def enhanced_identify_candidates(key, max_items=5):
            # First try with the predictive engine
            metadata = cache.get_metadata(key)
            candidates = predictive_manager.get_prefetch_candidates(key, metadata, max_items)
            
            # If no predictions, fall back to original method
            if not candidates:
                candidates = original_identify_candidates(key, max_items)
            
            return candidates
        
        # Replace method
        cache._identify_prefetch_candidates = enhanced_identify_candidates
        
        return cache
    
    def generate_test_content(self, 
                            num_items: int = 100, 
                            size_min: int = 1024,
                            size_max: int = 1024 * 1024,
                            content_types: Optional[List[str]] = None) -> None:
        """Generate test content for benchmarking.
        
        Args:
            num_items: Number of content items to generate
            size_min: Minimum content size in bytes
            size_max: Maximum content size in bytes
            content_types: List of content types to generate
        """
        if content_types is None:
            content_types = ["document", "image", "video", "dataset"]
        
        logger.info(f"Generating {num_items} test content items...")
        
        for i in range(num_items):
            # Generate a unique content ID
            content_id = f"cid_{i:06d}"
            
            # Random content size
            size = random.randint(size_min, size_max)
            
            # Random content type
            content_type = random.choice(content_types)
            
            # Generate content based on type
            if content_type == "document":
                # Text-like content
                content = os.urandom(size)
                metadata = {
                    "filename": f"document_{i}.txt",
                    "mimetype": "text/plain",
                    "content_type": "document",
                }
            elif content_type == "image":
                # Binary image-like content
                content = os.urandom(size)
                metadata = {
                    "filename": f"image_{i}.jpg",
                    "mimetype": "image/jpeg",
                    "content_type": "image",
                }
            elif content_type == "video":
                # Binary video-like content
                content = os.urandom(size)
                metadata = {
                    "filename": f"video_{i}.mp4",
                    "mimetype": "video/mp4",
                    "content_type": "video",
                }
            elif content_type == "dataset":
                # Data-like content
                content = os.urandom(size)
                metadata = {
                    "filename": f"dataset_{i}.csv",
                    "mimetype": "text/csv",
                    "content_type": "dataset",
                }
            else:
                # Generic content
                content = os.urandom(size)
                metadata = {
                    "filename": f"generic_{i}.bin",
                    "mimetype": "application/octet-stream",
                    "content_type": "generic",
                }
            
            # Add to test content
            self.test_content[content_id] = {
                "content": content,
                "metadata": metadata,
                "size": size,
            }
        
        logger.info(f"Generated {len(self.test_content)} test content items")
        
        # Load content into caches
        for cache_name, cache in self.caches.items():
            for content_id, content_data in self.test_content.items():
                cache.put(content_id, content_data["content"], content_data["metadata"])
            
            # Clear cache to start with empty state
            cache.clear(tiers=["memory", "disk"])
            
            logger.info(f"Initialized cache '{cache_name}'")
    
    def benchmark_access_pattern(self, 
                                pattern_name: str,
                                access_sequence: List[str],
                                warmup: int = 0) -> Dict[str, Any]:
        """Benchmark cache performance for a specific access pattern.
        
        Args:
            pattern_name: Name of the access pattern
            access_sequence: List of content IDs to access in sequence
            warmup: Number of accesses to perform before starting measurements
            
        Returns:
            Dictionary with benchmark results
        """
        logger.info(f"Benchmarking access pattern: {pattern_name}")
        
        # Results for this pattern
        pattern_results = {
            "pattern_name": pattern_name,
            "total_accesses": len(access_sequence) - warmup,
            "cache_results": {}
        }
        
        # Benchmark each cache strategy
        for cache_name, cache in self.caches.items():
            logger.info(f"Testing cache strategy: {cache_name}")
            
            # Clear cache before starting
            cache.clear(tiers=["memory", "disk"])
            
            # Reset metrics
            if hasattr(cache, "prefetch_stats"):
                cache.prefetch_stats = {
                    "prefetch_operations": 0,
                    "items_prefetched": 0,
                    "prefetch_hits": 0,
                    "prefetch_misses": 0,
                }
            
            # Warmup phase (not measured)
            for i in range(min(warmup, len(access_sequence))):
                content_id = access_sequence[i]
                if content_id in self.test_content:
                    cache.get(content_id)
            
            # Measurement phase
            cache_metrics = {
                "access_times": [],
                "hit_count": 0,
                "miss_count": 0,
                "hit_rate": 0.0,
                "prefetch_hits": 0,
                "total_time": 0.0,
                "mean_access_time": 0.0,
                "memory_hits": 0,
                "disk_hits": 0,
            }
            
            start_time = time.time()
            
            for i in range(warmup, len(access_sequence)):
                content_id = access_sequence[i]
                if content_id in self.test_content:
                    # Measure access time
                    access_start = time.time()
                    content = cache.get(content_id)
                    access_time = time.time() - access_start
                    
                    # Record metrics
                    cache_metrics["access_times"].append(access_time)
                    
                    # Check if it was a hit
                    if content is not None:
                        cache_metrics["hit_count"] += 1
                        
                        # Track hit tier
                        stats = cache.access_stats.get(content_id, {})
                        tier_hits = stats.get("tier_hits", {})
                        if tier_hits.get("memory", 0) > 0:
                            cache_metrics["memory_hits"] += 1
                        elif tier_hits.get("disk", 0) > 0:
                            cache_metrics["disk_hits"] += 1
                    else:
                        cache_metrics["miss_count"] += 1
            
            total_time = time.time() - start_time
            
            # Calculate aggregate metrics
            cache_metrics["total_time"] = total_time
            cache_metrics["mean_access_time"] = (
                sum(cache_metrics["access_times"]) / len(cache_metrics["access_times"])
                if cache_metrics["access_times"] else 0
            )
            cache_metrics["hit_rate"] = (
                cache_metrics["hit_count"] / (cache_metrics["hit_count"] + cache_metrics["miss_count"])
                if (cache_metrics["hit_count"] + cache_metrics["miss_count"]) > 0 else 0
            )
            
            # Get prefetch metrics if available
            if hasattr(cache, "prefetch_stats"):
                cache_metrics["prefetch_operations"] = cache.prefetch_stats.get("prefetch_operations", 0)
                cache_metrics["items_prefetched"] = cache.prefetch_stats.get("items_prefetched", 0)
                cache_metrics["prefetch_hits"] = cache.prefetch_stats.get("prefetch_hits", 0)
                cache_metrics["prefetch_hit_rate"] = (
                    cache.prefetch_stats.get("prefetch_hits", 0) / 
                    max(1, cache.prefetch_stats.get("items_prefetched", 0))
                )
            
            # Save results for this cache
            pattern_results["cache_results"][cache_name] = cache_metrics
            
            logger.info(f"  Hit rate: {cache_metrics['hit_rate']:.2%}")
            logger.info(f"  Mean access time: {cache_metrics['mean_access_time']*1000:.2f}ms")
        
        # Add results to metrics
        self.metrics[pattern_name] = pattern_results
        
        return pattern_results
    
    def benchmark_sequential_access(self, 
                                  num_accesses: int = 100,
                                  warmup: int = 10) -> Dict[str, Any]:
        """Benchmark sequential access pattern.
        
        Args:
            num_accesses: Number of accesses to perform
            warmup: Number of warmup accesses
            
        Returns:
            Benchmark results
        """
        # Build sequential access pattern
        if not self.test_content:
            self.generate_test_content()
        
        # Sort content IDs to ensure sequential access
        content_ids = sorted(self.test_content.keys())
        
        # Create sequential access sequence
        if len(content_ids) >= num_accesses:
            access_sequence = content_ids[:num_accesses + warmup]
        else:
            # Repeat if needed
            access_sequence = []
            while len(access_sequence) < num_accesses + warmup:
                access_sequence.extend(content_ids)
            access_sequence = access_sequence[:num_accesses + warmup]
        
        # Run benchmark
        return self.benchmark_access_pattern("sequential", access_sequence, warmup)
    
    def benchmark_random_access(self, 
                             num_accesses: int = 100,
                             warmup: int = 10) -> Dict[str, Any]:
        """Benchmark random access pattern.
        
        Args:
            num_accesses: Number of accesses to perform
            warmup: Number of warmup accesses
            
        Returns:
            Benchmark results
        """
        # Build random access pattern
        if not self.test_content:
            self.generate_test_content()
        
        content_ids = list(self.test_content.keys())
        
        # Create random access sequence
        access_sequence = [random.choice(content_ids) for _ in range(num_accesses + warmup)]
        
        # Run benchmark
        return self.benchmark_access_pattern("random", access_sequence, warmup)
    
    def benchmark_zipf_access(self, 
                            num_accesses: int = 100,
                            alpha: float = 1.0,
                            warmup: int = 10) -> Dict[str, Any]:
        """Benchmark Zipf-distributed access pattern (some items accessed more frequently).
        
        Args:
            num_accesses: Number of accesses to perform
            alpha: Zipf distribution parameter (higher means more skewed)
            warmup: Number of warmup accesses
            
        Returns:
            Benchmark results
        """
        # Build Zipf access pattern
        if not self.test_content:
            self.generate_test_content()
        
        content_ids = list(self.test_content.keys())
        n = len(content_ids)
        
        # Create Zipf distribution
        if HAS_VISUALIZATION:
            # Use numpy for Zipf distribution
            zipf_probs = np.power(np.arange(1, n + 1, dtype=float), -alpha)
            zipf_probs /= zipf_probs.sum()
            
            # Create access sequence based on Zipf distribution
            access_sequence = np.random.choice(
                content_ids, size=num_accesses + warmup, replace=True, p=zipf_probs
            ).tolist()
        else:
            # Approximate Zipf without numpy
            ranks = list(range(1, n + 1))
            probs = [1.0 / (r ** alpha) for r in ranks]
            total = sum(probs)
            probs = [p / total for p in probs]
            
            # Create cumulative probabilities
            cum_probs = [sum(probs[:i+1]) for i in range(len(probs))]
            
            # Generate access sequence
            access_sequence = []
            for _ in range(num_accesses + warmup):
                r = random.random()
                for i, cp in enumerate(cum_probs):
                    if r <= cp:
                        access_sequence.append(content_ids[i])
                        break
        
        # Run benchmark
        return self.benchmark_access_pattern(f"zipf_alpha{alpha}", access_sequence, warmup)
    
    def benchmark_clustered_access(self, 
                                 num_accesses: int = 100,
                                 cluster_size: int = 5,
                                 num_clusters: int = 5,
                                 warmup: int = 10) -> Dict[str, Any]:
        """Benchmark clustered access pattern (accessing related items together).
        
        Args:
            num_accesses: Number of accesses to perform
            cluster_size: Number of items in each cluster
            num_clusters: Number of clusters
            warmup: Number of warmup accesses
            
        Returns:
            Benchmark results
        """
        # Build clustered access pattern
        if not self.test_content:
            self.generate_test_content()
        
        content_ids = list(self.test_content.keys())
        
        # Create clusters
        clusters = []
        for i in range(min(num_clusters, len(content_ids) // cluster_size)):
            start = i * cluster_size
            end = start + cluster_size
            if end <= len(content_ids):
                clusters.append(content_ids[start:end])
        
        # Create access sequence by choosing clusters
        access_sequence = []
        while len(access_sequence) < num_accesses + warmup:
            # Choose a random cluster
            cluster = random.choice(clusters)
            # Add all items in the cluster
            access_sequence.extend(cluster)
        
        # Run benchmark
        return self.benchmark_access_pattern("clustered", access_sequence[:num_accesses + warmup], warmup)
    
    def benchmark_typespecific_access(self, 
                                    num_accesses: int = 100,
                                    content_type: str = "video",
                                    warmup: int = 10) -> Dict[str, Any]:
        """Benchmark type-specific access pattern (e.g., sequential for video).
        
        Args:
            num_accesses: Number of accesses to perform
            content_type: Content type to benchmark
            warmup: Number of warmup accesses
            
        Returns:
            Benchmark results
        """
        # Build type-specific access pattern
        if not self.test_content:
            self.generate_test_content()
        
        # Filter content by type
        type_content = [
            cid for cid, data in self.test_content.items()
            if data["metadata"].get("content_type") == content_type
        ]
        
        if not type_content:
            logger.warning(f"No content items of type '{content_type}' found")
            return {}
        
        # Create access sequence based on content type
        if content_type in ["video", "audio", "document"]:
            # Sequential access for streaming media
            access_sequence = []
            while len(access_sequence) < num_accesses + warmup:
                # Pick a random starting point
                start_idx = random.randint(0, len(type_content) - 1)
                # Access sequentially from that point
                for i in range(min(len(type_content) - start_idx, 10)):
                    access_sequence.append(type_content[start_idx + i])
        else:
            # Random access for other types
            access_sequence = [random.choice(type_content) for _ in range(num_accesses + warmup)]
        
        # Run benchmark
        return self.benchmark_access_pattern(f"type_{content_type}", access_sequence[:num_accesses + warmup], warmup)
    
    def run_all_benchmarks(self, 
                          num_accesses: int = 100,
                          warmup: int = 10) -> Dict[str, Dict[str, Any]]:
        """Run all benchmark patterns.
        
        Args:
            num_accesses: Number of accesses per benchmark
            warmup: Number of warmup accesses
            
        Returns:
            Dictionary of benchmark results
        """
        # Generate test content if not already done
        if not self.test_content:
            self.generate_test_content()
        
        # Run all benchmark patterns
        self.benchmark_sequential_access(num_accesses, warmup)
        self.benchmark_random_access(num_accesses, warmup)
        self.benchmark_zipf_access(num_accesses, 1.0, warmup)
        self.benchmark_clustered_access(num_accesses, 5, 5, warmup)
        
        # Run type-specific benchmarks
        for content_type in ["video", "image", "document", "dataset"]:
            self.benchmark_typespecific_access(num_accesses, content_type, warmup)
        
        return self.metrics
    
    def generate_report(self, output_format: str = "text") -> str:
        """Generate a report of benchmark results.
        
        Args:
            output_format: Format for the report ('text', 'json', or 'csv')
            
        Returns:
            Report as a string in the specified format
        """
        if output_format == "json":
            # JSON report
            return json.dumps(self.metrics, indent=2)
        
        elif output_format == "csv":
            # CSV report
            csv_data = []
            header = ["Pattern", "Cache Strategy", "Hit Rate", "Mean Access Time (ms)",
                     "Prefetch Hit Rate", "Memory Hits", "Disk Hits"]
            csv_data.append(header)
            
            for pattern_name, pattern_results in self.metrics.items():
                for cache_name, cache_metrics in pattern_results["cache_results"].items():
                    row = [
                        pattern_name,
                        cache_name,
                        f"{cache_metrics.get('hit_rate', 0):.4f}",
                        f"{cache_metrics.get('mean_access_time', 0) * 1000:.4f}",
                        f"{cache_metrics.get('prefetch_hit_rate', 0):.4f}",
                        str(cache_metrics.get('memory_hits', 0)),
                        str(cache_metrics.get('disk_hits', 0))
                    ]
                    csv_data.append(row)
            
            # Convert to CSV string
            csv_output = ""
            for row in csv_data:
                csv_output += ",".join(row) + "\n"
            
            return csv_output
        
        else:  # default text format
            # Text report
            report = "IPFS Prefetching Benchmark Results\n"
            report += "================================\n\n"
            
            for pattern_name, pattern_results in self.metrics.items():
                report += f"Access Pattern: {pattern_name}\n"
                report += f"Total Accesses: {pattern_results['total_accesses']}\n"
                report += "Cache Strategy Results:\n"
                
                # Table header
                report += "  {:<20} {:<10} {:<20} {:<20} {:<15}\n".format(
                    "Strategy", "Hit Rate", "Mean Access Time", "Prefetch Hit Rate", "Memory/Disk Hits"
                )
                report += "  {:<20} {:<10} {:<20} {:<20} {:<15}\n".format(
                    "-" * 20, "-" * 10, "-" * 20, "-" * 20, "-" * 15
                )
                
                # Table rows
                for cache_name, cache_metrics in pattern_results["cache_results"].items():
                    report += "  {:<20} {:<10.2%} {:<20.2f}ms {:<20.2%} {:<15}\n".format(
                        cache_name,
                        cache_metrics.get("hit_rate", 0),
                        cache_metrics.get("mean_access_time", 0) * 1000,  # to ms
                        cache_metrics.get("prefetch_hit_rate", 0),
                        f"{cache_metrics.get('memory_hits', 0)}/{cache_metrics.get('disk_hits', 0)}"
                    )
                
                report += "\n"
            
            return report
    
    def save_report(self, output_format: str = "all") -> List[str]:
        """Save benchmark report to file(s).
        
        Args:
            output_format: Format(s) to save ('text', 'json', 'csv', or 'all')
            
        Returns:
            List of paths to saved files
        """
        saved_files = []
        
        formats = ["text", "json", "csv"] if output_format == "all" else [output_format]
        
        for fmt in formats:
            report = self.generate_report(fmt)
            
            # Set file extension based on format
            extension = {"text": "txt", "json": "json", "csv": "csv"}[fmt]
            
            # Create filename
            filename = f"prefetch_benchmark_results.{extension}"
            file_path = os.path.join(self.output_dir, filename)
            
            # Save to file
            with open(file_path, "w") as f:
                f.write(report)
            
            saved_files.append(file_path)
            logger.info(f"Saved {fmt} report to {file_path}")
        
        return saved_files
    
    def visualize_results(self, save_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Visualize benchmark results if matplotlib is available.
        
        Args:
            save_path: Optional path to save visualization images
            
        Returns:
            Dictionary of figure objects or None if visualization not available
        """
        if not HAS_VISUALIZATION:
            logger.warning("Visualization requires matplotlib and numpy. Skipping visualization.")
            return None
        
        if not self.metrics:
            logger.warning("No benchmark results to visualize. Run benchmarks first.")
            return None
        
        figures = {}
        
        # Prepare data
        patterns = list(self.metrics.keys())
        strategies = ["no_prefetch", "basic_prefetch", "predictive_prefetch"]
        
        # Create figure directory if needed
        if save_path:
            os.makedirs(save_path, exist_ok=True)
        
        # Figure 1: Hit rate comparison
        fig1, ax1 = plt.subplots(figsize=(12, 8))
        x = np.arange(len(patterns))
        width = 0.25
        
        for i, strategy in enumerate(strategies):
            hit_rates = [
                self.metrics[pattern]["cache_results"][strategy].get("hit_rate", 0) 
                for pattern in patterns
            ]
            ax1.bar(x + (i - 1) * width, hit_rates, width, label=strategy)
        
        ax1.set_ylabel('Hit Rate')
        ax1.set_title('Cache Hit Rate by Access Pattern')
        ax1.set_xticks(x)
        ax1.set_xticklabels(patterns, rotation=45, ha="right")
        ax1.legend()
        ax1.grid(axis='y', linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        figures["hit_rate"] = fig1
        
        if save_path:
            fig1.savefig(os.path.join(save_path, "hit_rate_comparison.png"))
        
        # Figure 2: Access time comparison
        fig2, ax2 = plt.subplots(figsize=(12, 8))
        
        for i, strategy in enumerate(strategies):
            access_times = [
                self.metrics[pattern]["cache_results"][strategy].get("mean_access_time", 0) * 1000  # to ms
                for pattern in patterns
            ]
            ax2.bar(x + (i - 1) * width, access_times, width, label=strategy)
        
        ax2.set_ylabel('Mean Access Time (ms)')
        ax2.set_title('Mean Access Time by Access Pattern')
        ax2.set_xticks(x)
        ax2.set_xticklabels(patterns, rotation=45, ha="right")
        ax2.legend()
        ax2.grid(axis='y', linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        figures["access_time"] = fig2
        
        if save_path:
            fig2.savefig(os.path.join(save_path, "access_time_comparison.png"))
        
        # Figure 3: Prefetch hit rate (only for strategies with prefetching)
        fig3, ax3 = plt.subplots(figsize=(12, 8))
        
        prefetch_strategies = ["basic_prefetch", "predictive_prefetch"]
        
        for i, strategy in enumerate(prefetch_strategies):
            prefetch_hit_rates = [
                self.metrics[pattern]["cache_results"][strategy].get("prefetch_hit_rate", 0) 
                for pattern in patterns
            ]
            ax3.bar(x + (i - 0.5) * width, prefetch_hit_rates, width, label=strategy)
        
        ax3.set_ylabel('Prefetch Hit Rate')
        ax3.set_title('Prefetch Hit Rate by Access Pattern')
        ax3.set_xticks(x)
        ax3.set_xticklabels(patterns, rotation=45, ha="right")
        ax3.legend()
        ax3.grid(axis='y', linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        figures["prefetch_hit_rate"] = fig3
        
        if save_path:
            fig3.savefig(os.path.join(save_path, "prefetch_hit_rate_comparison.png"))
        
        return figures
    
    def cleanup(self) -> None:
        """Clean up temporary files and resources."""
        try:
            # Shut down predictive cache manager
            for cache_name, cache in self.caches.items():
                if hasattr(cache, "predictive_manager"):
                    cache.predictive_manager.shutdown()
            
            # Clean up temp directory
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            
            logger.info("Cleaned up benchmark resources")
        except Exception as e:
            logger.error(f"Error cleaning up resources: {e}")


def run_benchmark(output_dir: str = None, 
                 num_accesses: int = 100,
                 visualize: bool = True) -> None:
    """Run a complete prefetching benchmark.
    
    Args:
        output_dir: Directory to save results
        num_accesses: Number of accesses per benchmark
        visualize: Whether to generate visualizations
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create benchmark instance
    benchmark = PrefetchBenchmark(output_dir=output_dir)
    
    try:
        # Generate test content
        benchmark.generate_test_content(num_items=200)
        
        # Run all benchmarks
        benchmark.run_all_benchmarks(num_accesses=num_accesses)
        
        # Save reports
        benchmark.save_report(output_format="all")
        
        # Generate visualizations if enabled
        if visualize:
            if output_dir:
                viz_path = os.path.join(output_dir, "visualizations")
            else:
                viz_path = os.path.join(benchmark.output_dir, "visualizations")
                
            benchmark.visualize_results(save_path=viz_path)
        
        logger.info("Benchmark completed successfully")
        
    finally:
        # Clean up resources
        benchmark.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IPFS Prefetching Benchmark Tool")
    parser.add_argument("--output", "-o", type=str, help="Output directory for benchmark results")
    parser.add_argument("--accesses", "-a", type=int, default=100, help="Number of accesses per benchmark")
    parser.add_argument("--no-viz", action="store_true", help="Disable visualization")
    
    args = parser.parse_args()
    
    run_benchmark(
        output_dir=args.output,
        num_accesses=args.accesses,
        visualize=not args.no_viz
    )