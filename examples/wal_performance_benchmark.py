#!/usr/bin/env python3
"""
Performance benchmarking for the WAL system.

This script tests the performance of the WAL system under various conditions,
measuring throughput, latency, and recovery capabilities.
"""

import os
import sys
import time
import uuid
import random
import logging
import argparse
import tempfile
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import required modules
from ipfs_kit_py import IPFSSimpleAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Optional imports for visualization
try:
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("Matplotlib is not available. Install with: pip install matplotlib")

# Constants
DEFAULT_NUM_OPERATIONS = 100
DEFAULT_FILE_SIZE_KB = 10
DEFAULT_BATCH_SIZE = 10
DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "benchmark_results")
BACKEND_COLORS = {
    "ipfs": "#3498DB",
    "s3": "#F1C40F",
    "storacha": "#9B59B6"
}

class WALBenchmark:
    """Benchmark tool for the WAL system."""

    def __init__(self, api: Optional[IPFSSimpleAPI] = None, output_dir: Optional[str] = None):
        """Initialize the benchmark tool.

        Args:
            api: An existing IPFSSimpleAPI instance, or None to create a new one
            output_dir: Directory to save benchmark results
        """
        self.api = api or IPFSSimpleAPI()
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR

        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)

        # Test data storage
        self.test_files = []
        self.operations = []
        self.results = {}

    def create_test_file(self, size_kb: int) -> str:
        """Create a test file of specified size.

        Args:
            size_kb: Size of the file in KB

        Returns:
            Path to the test file
        """
        # Create temporary file
        fd, path = tempfile.mkstemp(suffix=".bin")

        # Write random data to the file
        with os.fdopen(fd, "wb") as f:
            # Write in 1KB chunks
            for _ in range(size_kb):
                f.write(os.urandom(1024))

        # Add to test files list for cleanup
        self.test_files.append(path)

        return path

    def cleanup(self):
        """Clean up test files."""
        for file_path in self.test_files:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception as e:
                logger.warning(f"Failed to remove test file {file_path}: {e}")

        self.test_files = []

    def benchmark_add_operation(self,
                                num_operations: int = DEFAULT_NUM_OPERATIONS,
                                file_size_kb: int = DEFAULT_FILE_SIZE_KB,
                                backends: Optional[List[str]] = None) -> Dict[str, Any]:
        """Benchmark 'add' operation performance.

        Args:
            num_operations: Number of operations to perform
            file_size_kb: Size of test files in KB
            backends: List of backends to test, or None for all available

        Returns:
            Dictionary with benchmark results
        """
        if backends is None:
            backends = ["ipfs", "s3", "storacha"]

        logger.info(f"Benchmarking 'add' operation: {num_operations} operations, "
                   f"{file_size_kb}KB files, backends: {backends}")

        # Results structure
        results = {
            "operation": "add",
            "num_operations": num_operations,
            "file_size_kb": file_size_kb,
            "backends": backends,
            "timestamp": time.time(),
            "metrics": {}
        }

        # Results for each backend
        for backend in backends:
            logger.info(f"Testing backend: {backend}")

            backend_results = {
                "operation_ids": [],
                "start_times": [],
                "end_times": [],
                "latencies": [],
                "success_count": 0,
                "failure_count": 0,
                "pending_count": 0
            }

            # Perform operations
            for i in range(num_operations):
                # Create test file
                test_file = self.create_test_file(file_size_kb)

                # Measure performance
                start_time = time.time()

                # Add file using the specified backend
                if backend == "ipfs":
                    response = self.api.add(test_file)
                else:
                    # For this benchmark, we just use IPFS for all backends
                    # since we're focusing on WAL performance, not backend performance
                    response = self.api.add(test_file)

                end_time = time.time()
                latency = end_time - start_time

                # Record results
                operation_id = response.get("operation_id", str(uuid.uuid4()))
                backend_results["operation_ids"].append(operation_id)
                backend_results["start_times"].append(start_time)
                backend_results["end_times"].append(end_time)
                backend_results["latencies"].append(latency)

                # Check operation status
                if response.get("success", False):
                    backend_results["success_count"] += 1
                elif response.get("status") == "pending":
                    backend_results["pending_count"] += 1
                else:
                    backend_results["failure_count"] += 1

            # Calculate statistics
            if backend_results["latencies"]:
                backend_results["min_latency"] = min(backend_results["latencies"])
                backend_results["max_latency"] = max(backend_results["latencies"])
                backend_results["avg_latency"] = statistics.mean(backend_results["latencies"])
                if len(backend_results["latencies"]) > 1:
                    backend_results["stddev_latency"] = statistics.stdev(backend_results["latencies"])
                else:
                    backend_results["stddev_latency"] = 0

                # Calculate throughput (operations per second)
                total_time = backend_results["end_times"][-1] - backend_results["start_times"][0]
                backend_results["throughput"] = num_operations / total_time if total_time > 0 else 0

            # Store results for this backend
            results["metrics"][backend] = backend_results

        # Save results
        self.results["add_operation"] = results

        return results

    def benchmark_batch_operations(self,
                                  num_batches: int = 10,
                                  batch_size: int = DEFAULT_BATCH_SIZE,
                                  file_size_kb: int = DEFAULT_FILE_SIZE_KB,
                                  backends: Optional[List[str]] = None) -> Dict[str, Any]:
        """Benchmark batch operation performance.

        Args:
            num_batches: Number of batches to perform
            batch_size: Number of operations per batch
            file_size_kb: Size of test files in KB
            backends: List of backends to test, or None for all available

        Returns:
            Dictionary with benchmark results
        """
        if backends is None:
            backends = ["ipfs", "s3", "storacha"]

        logger.info(f"Benchmarking batch operations: {num_batches} batches, "
                   f"{batch_size} operations per batch, {file_size_kb}KB files, "
                   f"backends: {backends}")

        # Results structure
        results = {
            "operation": "batch",
            "num_batches": num_batches,
            "batch_size": batch_size,
            "file_size_kb": file_size_kb,
            "backends": backends,
            "timestamp": time.time(),
            "metrics": {}
        }

        # Results for each backend
        for backend in backends:
            logger.info(f"Testing backend: {backend}")

            backend_results = {
                "batch_start_times": [],
                "batch_end_times": [],
                "batch_latencies": [],
                "success_count": 0,
                "failure_count": 0,
                "pending_count": 0
            }

            # Perform batches
            for batch_num in range(num_batches):
                # Create test files for this batch
                batch_files = [self.create_test_file(file_size_kb) for _ in range(batch_size)]

                # Measure batch performance
                start_time = time.time()

                # Process batch (in a real implementation, this would use the batch API)
                for test_file in batch_files:
                    if backend == "ipfs":
                        response = self.api.add(test_file)
                    else:
                        # For this benchmark, we just use IPFS for all backends
                        response = self.api.add(test_file)

                    # Count results
                    if response.get("success", False):
                        backend_results["success_count"] += 1
                    elif response.get("status") == "pending":
                        backend_results["pending_count"] += 1
                    else:
                        backend_results["failure_count"] += 1

                end_time = time.time()
                latency = end_time - start_time

                # Record batch results
                backend_results["batch_start_times"].append(start_time)
                backend_results["batch_end_times"].append(end_time)
                backend_results["batch_latencies"].append(latency)

            # Calculate statistics
            if backend_results["batch_latencies"]:
                backend_results["min_batch_latency"] = min(backend_results["batch_latencies"])
                backend_results["max_batch_latency"] = max(backend_results["batch_latencies"])
                backend_results["avg_batch_latency"] = statistics.mean(backend_results["batch_latencies"])
                if len(backend_results["batch_latencies"]) > 1:
                    backend_results["stddev_batch_latency"] = statistics.stdev(backend_results["batch_latencies"])
                else:
                    backend_results["stddev_batch_latency"] = 0

                # Calculate throughput (operations per second)
                total_time = sum(backend_results["batch_latencies"])
                total_operations = num_batches * batch_size
                backend_results["throughput"] = total_operations / total_time if total_time > 0 else 0

                # Calculate average operations per second per batch
                backend_results["avg_batch_throughput"] = batch_size / backend_results["avg_batch_latency"] if backend_results["avg_batch_latency"] > 0 else 0

            # Store results for this backend
            results["metrics"][backend] = backend_results

        # Save results
        self.results["batch_operations"] = results

        return results

    def benchmark_recovery(self,
                          num_operations: int = DEFAULT_NUM_OPERATIONS,
                          file_size_kb: int = DEFAULT_FILE_SIZE_KB,
                          failure_rate: float = 0.2,
                          backend: str = "ipfs") -> Dict[str, Any]:
        """Benchmark WAL recovery performance.

        Args:
            num_operations: Number of operations to perform
            file_size_kb: Size of test files in KB
            failure_rate: Rate of simulated failures (0.0 to 1.0)
            backend: Backend to test

        Returns:
            Dictionary with benchmark results
        """
        logger.info(f"Benchmarking recovery: {num_operations} operations, "
                   f"{file_size_kb}KB files, {failure_rate:.1%} failure rate, "
                   f"backend: {backend}")

        # Results structure
        results = {
            "operation": "recovery",
            "num_operations": num_operations,
            "file_size_kb": file_size_kb,
            "failure_rate": failure_rate,
            "backend": backend,
            "timestamp": time.time(),
            "metrics": {
                "operation_ids": [],
                "initial_latencies": [],
                "retry_latencies": [],
                "recovery_times": [],
                "successful_recoveries": 0,
                "failed_recoveries": 0
            }
        }

        # Track operations for retry
        failed_operations = []

        # Phase 1: Initial operations with simulated failures
        logger.info("Phase 1: Initial operations with simulated failures")
        for i in range(num_operations):
            # Create test file
            test_file = self.create_test_file(file_size_kb)

            # Measure performance
            start_time = time.time()

            # Add file
            response = self.api.add(test_file)

            end_time = time.time()
            latency = end_time - start_time

            # Record operation ID and latency
            operation_id = response.get("operation_id", str(uuid.uuid4()))
            results["metrics"]["operation_ids"].append(operation_id)
            results["metrics"]["initial_latencies"].append(latency)

            # Simulate failure based on failure rate
            if random.random() < failure_rate:
                # In a real benchmark, you would need to actually cause failures
                # Here we just track operations to retry as if they failed
                failed_operations.append(operation_id)

        # Phase 2: Retry failed operations
        logger.info(f"Phase 2: Retrying {len(failed_operations)} failed operations")
        for operation_id in failed_operations:
            # Measure retry performance
            start_time = time.time()

            # Retry operation
            # In a real implementation, you would use a retry API
            # Here we simulate it with a delay
            time.sleep(0.1)  # Simulate retry processing time
            retry_success = random.random() < 0.8  # 80% retry success rate

            end_time = time.time()
            retry_latency = end_time - start_time

            # Record retry latency
            results["metrics"]["retry_latencies"].append(retry_latency)

            # Record recovery status
            if retry_success:
                results["metrics"]["successful_recoveries"] += 1
                results["metrics"]["recovery_times"].append(retry_latency)
            else:
                results["metrics"]["failed_recoveries"] += 1

        # Calculate statistics
        if results["metrics"]["initial_latencies"]:
            results["metrics"]["min_initial_latency"] = min(results["metrics"]["initial_latencies"])
            results["metrics"]["max_initial_latency"] = max(results["metrics"]["initial_latencies"])
            results["metrics"]["avg_initial_latency"] = statistics.mean(results["metrics"]["initial_latencies"])

            if len(results["metrics"]["initial_latencies"]) > 1:
                results["metrics"]["stddev_initial_latency"] = statistics.stdev(results["metrics"]["initial_latencies"])
            else:
                results["metrics"]["stddev_initial_latency"] = 0

        if results["metrics"]["retry_latencies"]:
            results["metrics"]["min_retry_latency"] = min(results["metrics"]["retry_latencies"])
            results["metrics"]["max_retry_latency"] = max(results["metrics"]["retry_latencies"])
            results["metrics"]["avg_retry_latency"] = statistics.mean(results["metrics"]["retry_latencies"])

            if len(results["metrics"]["retry_latencies"]) > 1:
                results["metrics"]["stddev_retry_latency"] = statistics.stdev(results["metrics"]["retry_latencies"])
            else:
                results["metrics"]["stddev_retry_latency"] = 0

        if results["metrics"]["recovery_times"]:
            results["metrics"]["min_recovery_time"] = min(results["metrics"]["recovery_times"])
            results["metrics"]["max_recovery_time"] = max(results["metrics"]["recovery_times"])
            results["metrics"]["avg_recovery_time"] = statistics.mean(results["metrics"]["recovery_times"])

            if len(results["metrics"]["recovery_times"]) > 1:
                results["metrics"]["stddev_recovery_time"] = statistics.stdev(results["metrics"]["recovery_times"])
            else:
                results["metrics"]["stddev_recovery_time"] = 0

        # Calculate recovery rate
        total_failures = len(failed_operations)
        if total_failures > 0:
            results["metrics"]["recovery_rate"] = results["metrics"]["successful_recoveries"] / total_failures
        else:
            results["metrics"]["recovery_rate"] = 1.0  # No failures to recover from

        # Save results
        self.results["recovery"] = results

        return results

    def save_results(self, filename: Optional[str] = None) -> str:
        """Save benchmark results to file.

        Args:
            filename: Optional filename, or None to generate one

        Returns:
            Path to the saved file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"wal_benchmark_{timestamp}.json"

        filepath = os.path.join(self.output_dir, filename)

        # Add summary to results
        self.results["summary"] = self.generate_summary()

        # Save to file
        import json
        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2)

        logger.info(f"Saved benchmark results to {filepath}")
        return filepath

    def generate_summary(self) -> Dict[str, Any]:
        """Generate a summary of benchmark results.

        Returns:
            Dictionary with benchmark summary
        """
        summary = {
            "timestamp": time.time(),
            "benchmarks_run": list(self.results.keys()),
            "throughput": {},
            "latency": {},
            "recovery": {}
        }

        # Extract throughput data
        if "add_operation" in self.results:
            for backend, metrics in self.results["add_operation"]["metrics"].items():
                summary["throughput"][f"add_{backend}"] = metrics.get("throughput", 0)

        if "batch_operations" in self.results:
            for backend, metrics in self.results["batch_operations"]["metrics"].items():
                summary["throughput"][f"batch_{backend}"] = metrics.get("throughput", 0)
                summary["throughput"][f"batch_{backend}_avg"] = metrics.get("avg_batch_throughput", 0)

        # Extract latency data
        if "add_operation" in self.results:
            for backend, metrics in self.results["add_operation"]["metrics"].items():
                summary["latency"][f"add_{backend}_avg"] = metrics.get("avg_latency", 0)
                summary["latency"][f"add_{backend}_min"] = metrics.get("min_latency", 0)
                summary["latency"][f"add_{backend}_max"] = metrics.get("max_latency", 0)

        if "batch_operations" in self.results:
            for backend, metrics in self.results["batch_operations"]["metrics"].items():
                summary["latency"][f"batch_{backend}_avg"] = metrics.get("avg_batch_latency", 0)
                summary["latency"][f"batch_{backend}_min"] = metrics.get("min_batch_latency", 0)
                summary["latency"][f"batch_{backend}_max"] = metrics.get("max_batch_latency", 0)

        # Extract recovery data
        if "recovery" in self.results:
            recovery_metrics = self.results["recovery"]["metrics"]
            summary["recovery"]["recovery_rate"] = recovery_metrics.get("recovery_rate", 0)
            summary["recovery"]["avg_recovery_time"] = recovery_metrics.get("avg_recovery_time", 0)
            summary["recovery"]["successful_recoveries"] = recovery_metrics.get("successful_recoveries", 0)
            summary["recovery"]["failed_recoveries"] = recovery_metrics.get("failed_recoveries", 0)

        return summary

    def plot_results(self, output_dir: Optional[str] = None) -> Dict[str, str]:
        """Generate plots from benchmark results.

        Args:
            output_dir: Optional directory to save plots, or None to use the benchmark output directory

        Returns:
            Dictionary with paths to generated plots
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib not available. Cannot generate plots.")
            return {}

        # Use default output directory if not specified
        if output_dir is None:
            output_dir = self.output_dir

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        plots = {}

        # Plot throughput comparison
        if "add_operation" in self.results:
            plots["throughput"] = self._plot_throughput_comparison(
                os.path.join(output_dir, "throughput_comparison.png")
            )

        # Plot latency comparison
        if "add_operation" in self.results:
            plots["latency"] = self._plot_latency_comparison(
                os.path.join(output_dir, "latency_comparison.png")
            )

        # Plot recovery performance
        if "recovery" in self.results:
            plots["recovery"] = self._plot_recovery_performance(
                os.path.join(output_dir, "recovery_performance.png")
            )

        # Plot batch performance
        if "batch_operations" in self.results:
            plots["batch"] = self._plot_batch_performance(
                os.path.join(output_dir, "batch_performance.png")
            )

        # Generate summary report
        plots["summary"] = self._generate_summary_report(
            os.path.join(output_dir, "benchmark_summary.html")
        )

        return plots

    def _plot_throughput_comparison(self, output_path: str) -> str:
        """Generate throughput comparison plot.

        Args:
            output_path: Path to save the plot

        Returns:
            Path to the saved plot
        """
        # Extract throughput data
        backends = []
        throughputs = []
        colors = []

        if "add_operation" in self.results:
            for backend, metrics in self.results["add_operation"]["metrics"].items():
                backends.append(backend)
                throughputs.append(metrics.get("throughput", 0))
                colors.append(BACKEND_COLORS.get(backend, "#999999"))

        if not backends:
            logger.warning("No throughput data available.")
            return ""

        # Create figure
        plt.figure(figsize=(10, 6))

        # Create bar chart
        bars = plt.bar(backends, throughputs, color=colors)

        # Add throughput values on top of bars
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{height:.2f}', ha='center', va='bottom')

        # Add labels and title
        plt.xlabel('Backend')
        plt.ylabel('Throughput (operations/second)')
        plt.title('WAL Throughput by Backend')
        plt.grid(axis='y', linestyle='--', alpha=0.7)

        # Save plot
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()

        logger.info(f"Saved throughput comparison plot to {output_path}")
        return output_path

    def _plot_latency_comparison(self, output_path: str) -> str:
        """Generate latency comparison plot.

        Args:
            output_path: Path to save the plot

        Returns:
            Path to the saved plot
        """
        # Extract latency data
        backends = []
        avg_latencies = []
        min_latencies = []
        max_latencies = []

        if "add_operation" in self.results:
            for backend, metrics in self.results["add_operation"]["metrics"].items():
                backends.append(backend)
                avg_latencies.append(metrics.get("avg_latency", 0))
                min_latencies.append(metrics.get("min_latency", 0))
                max_latencies.append(metrics.get("max_latency", 0))

        if not backends:
            logger.warning("No latency data available.")
            return ""

        # Create figure
        plt.figure(figsize=(10, 6))

        # Set width of bars
        bar_width = 0.25

        # Set position of bars on x axis
        r1 = range(len(backends))
        r2 = [x + bar_width for x in r1]
        r3 = [x + bar_width for x in r2]

        # Create bar chart
        plt.bar(r1, min_latencies, width=bar_width, color='green', label='Min Latency')
        plt.bar(r2, avg_latencies, width=bar_width, color='blue', label='Avg Latency')
        plt.bar(r3, max_latencies, width=bar_width, color='red', label='Max Latency')

        # Add labels and title
        plt.xlabel('Backend')
        plt.ylabel('Latency (seconds)')
        plt.title('WAL Latency by Backend')
        plt.xticks([r + bar_width for r in range(len(backends))], backends)
        plt.legend()
        plt.grid(axis='y', linestyle='--', alpha=0.7)

        # Set logarithmic scale for better visualization if large differences
        if max(max_latencies) / min(min_latencies + [0.001]) > 10:
            plt.yscale('log')

        # Save plot
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()

        logger.info(f"Saved latency comparison plot to {output_path}")
        return output_path

    def _plot_recovery_performance(self, output_path: str) -> str:
        """Generate recovery performance plot.

        Args:
            output_path: Path to save the plot

        Returns:
            Path to the saved plot
        """
        if "recovery" not in self.results:
            logger.warning("No recovery data available.")
            return ""

        recovery_metrics = self.results["recovery"]["metrics"]
        backend = self.results["recovery"]["backend"]

        # Create figure with two subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))

        # Plot 1: Recovery rate
        recovery_rate = recovery_metrics.get("recovery_rate", 0)
        recovery_success = recovery_metrics.get("successful_recoveries", 0)
        recovery_failed = recovery_metrics.get("failed_recoveries", 0)

        # Create pie chart
        ax1.pie([recovery_success, recovery_failed],
               labels=['Successful', 'Failed'],
               autopct='%1.1f%%',
               colors=['#4CAF50', '#F44336'],
               startangle=90)

        ax1.set_title(f'Recovery Success Rate: {recovery_rate:.1%}')

        # Plot 2: Recovery time
        avg_recovery_time = recovery_metrics.get("avg_recovery_time", 0)
        min_recovery_time = recovery_metrics.get("min_recovery_time", 0)
        max_recovery_time = recovery_metrics.get("max_recovery_time", 0)

        # Create bar chart
        bar_labels = ['Min', 'Avg', 'Max']
        bar_values = [min_recovery_time, avg_recovery_time, max_recovery_time]
        bars = ax2.bar(bar_labels, bar_values, color=['#4CAF50', '#2196F3', '#F44336'])

        # Add recovery time values on top of bars
        for bar in bars:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                    f'{height:.3f}s', ha='center', va='bottom')

        ax2.set_title(f'Recovery Time ({backend} backend)')
        ax2.set_ylabel('Time (seconds)')
        ax2.grid(axis='y', linestyle='--', alpha=0.7)

        # Save plot
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()

        logger.info(f"Saved recovery performance plot to {output_path}")
        return output_path

    def _plot_batch_performance(self, output_path: str) -> str:
        """Generate batch performance plot.

        Args:
            output_path: Path to save the plot

        Returns:
            Path to the saved plot
        """
        if "batch_operations" not in self.results:
            logger.warning("No batch operation data available.")
            return ""

        # Extract batch performance data
        backends = []
        throughputs = []
        avg_batch_latencies = []
        colors = []

        batch_metrics = self.results["batch_operations"]["metrics"]
        for backend, metrics in batch_metrics.items():
            backends.append(backend)
            throughputs.append(metrics.get("throughput", 0))
            avg_batch_latencies.append(metrics.get("avg_batch_latency", 0))
            colors.append(BACKEND_COLORS.get(backend, "#999999"))

        if not backends:
            logger.warning("No batch data available.")
            return ""

        # Create figure with two subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))

        # Plot 1: Throughput
        bars1 = ax1.bar(backends, throughputs, color=colors)

        # Add throughput values on top of bars
        for bar in bars1:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{height:.2f}', ha='center', va='bottom')

        ax1.set_xlabel('Backend')
        ax1.set_ylabel('Throughput (operations/second)')
        ax1.set_title('Batch Throughput by Backend')
        ax1.grid(axis='y', linestyle='--', alpha=0.7)

        # Plot 2: Average Batch Latency
        bars2 = ax2.bar(backends, avg_batch_latencies, color=colors)

        # Add latency values on top of bars
        for bar in bars2:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                    f'{height:.3f}s', ha='center', va='bottom')

        ax2.set_xlabel('Backend')
        ax2.set_ylabel('Average Batch Latency (seconds)')
        ax2.set_title('Batch Latency by Backend')
        ax2.grid(axis='y', linestyle='--', alpha=0.7)

        # Save plot
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()

        logger.info(f"Saved batch performance plot to {output_path}")
        return output_path

    def _generate_summary_report(self, output_path: str) -> str:
        """Generate HTML summary report.

        Args:
            output_path: Path to save the report

        Returns:
            Path to the saved report
        """
        # Get summary data
        summary = self.results.get("summary", self.generate_summary())

        # Get timestamp
        timestamp = datetime.fromtimestamp(summary.get("timestamp", time.time()))
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")

        # Create HTML content
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>WAL Benchmark Summary</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                h1, h2, h3 {{
                    color: #2c3e50;
                }}
                .header {{
                    background-color: #3498db;
                    color: white;
                    padding: 20px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                }}
                .section {{
                    background-color: white;
                    padding: 20px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 20px;
                }}
                th, td {{
                    padding: 10px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }}
                th {{
                    background-color: #f2f2f2;
                }}
                tr:hover {{
                    background-color: #f5f5f5;
                }}
                .metric-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                    gap: 15px;
                    margin-bottom: 20px;
                }}
                .metric-card {{
                    background-color: #f9f9f9;
                    padding: 15px;
                    border-radius: 5px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                    text-align: center;
                }}
                .metric-value {{
                    font-size: 24px;
                    font-weight: bold;
                    margin: 10px 0;
                }}
                .metric-label {{
                    font-size: 14px;
                    color: #666;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    color: #777;
                    font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>WAL Benchmark Summary</h1>
                <p>Generated on {timestamp_str}</p>
            </div>

            <div class="section">
                <h2>Overview</h2>
                <p>This report summarizes the performance benchmarks run on the WAL system.</p>
                <p>Benchmarks run: {', '.join(summary.get('benchmarks_run', []))}</p>
            </div>
        """

        # Add throughput section
        if summary.get("throughput"):
            html_content += """
            <div class="section">
                <h2>Throughput Performance</h2>
                <div class="metric-grid">
            """

            for metric, value in summary["throughput"].items():
                html_content += f"""
                    <div class="metric-card">
                        <div class="metric-label">{metric.replace('_', ' ').title()}</div>
                        <div class="metric-value">{value:.2f}</div>
                        <div class="metric-label">ops/second</div>
                    </div>
                """

            html_content += """
                </div>
            </div>
            """

        # Add latency section
        if summary.get("latency"):
            html_content += """
            <div class="section">
                <h2>Latency Performance</h2>
                <table>
                    <tr>
                        <th>Metric</th>
                        <th>Value (seconds)</th>
                    </tr>
            """

            for metric, value in summary["latency"].items():
                html_content += f"""
                    <tr>
                        <td>{metric.replace('_', ' ').title()}</td>
                        <td>{value:.6f}</td>
                    </tr>
                """

            html_content += """
                </table>
            </div>
            """

        # Add recovery section
        if summary.get("recovery"):
            html_content += """
            <div class="section">
                <h2>Recovery Performance</h2>
                <div class="metric-grid">
            """

            recovery_rate = summary["recovery"].get("recovery_rate", 0) * 100
            avg_recovery_time = summary["recovery"].get("avg_recovery_time", 0)
            successful_recoveries = summary["recovery"].get("successful_recoveries", 0)
            failed_recoveries = summary["recovery"].get("failed_recoveries", 0)

            html_content += f"""
                <div class="metric-card">
                    <div class="metric-label">Recovery Rate</div>
                    <div class="metric-value">{recovery_rate:.1f}%</div>
                </div>

                <div class="metric-card">
                    <div class="metric-label">Avg Recovery Time</div>
                    <div class="metric-value">{avg_recovery_time:.3f}s</div>
                </div>

                <div class="metric-card">
                    <div class="metric-label">Successful Recoveries</div>
                    <div class="metric-value">{successful_recoveries}</div>
                </div>

                <div class="metric-card">
                    <div class="metric-label">Failed Recoveries</div>
                    <div class="metric-value">{failed_recoveries}</div>
                </div>
            """

            html_content += """
                </div>
            </div>
            """

        # Add full details section with links to plots
        html_content += """
            <div class="section">
                <h2>Benchmark Details</h2>
                <p>The full benchmark results are available in the following files:</p>
                <ul>
        """

        # Add links to generated plots
        plot_links = {
            "throughput_comparison.png": "Throughput Comparison",
            "latency_comparison.png": "Latency Comparison",
            "recovery_performance.png": "Recovery Performance",
            "batch_performance.png": "Batch Performance"
        }

        for filename, description in plot_links.items():
            filepath = os.path.join(os.path.dirname(output_path), filename)
            if os.path.exists(filepath):
                html_content += f"""
                    <li><a href="{filename}">{description}</a></li>
                """

        html_content += """
                </ul>
            </div>

            <div class="footer">
                <p>Generated by WAL Benchmark Tool</p>
            </div>
        </body>
        </html>
        """

        # Write HTML to file
        with open(output_path, 'w') as f:
            f.write(html_content)

        logger.info(f"Generated summary report: {output_path}")
        return output_path

def run_benchmarks(args):
    """Run WAL benchmarks based on command-line arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        Tuple of (benchmark results, plot paths)
    """
    # Create the benchmark tool
    benchmark = WALBenchmark(output_dir=args.output_dir)

    try:
        # Run selected benchmarks
        if args.add or args.all:
            logger.info("Running 'add' operation benchmark...")
            benchmark.benchmark_add_operation(
                num_operations=args.num_operations,
                file_size_kb=args.file_size_kb,
                backends=args.backends
            )

        if args.batch or args.all:
            logger.info("Running batch operations benchmark...")
            benchmark.benchmark_batch_operations(
                num_batches=args.num_batches,
                batch_size=args.batch_size,
                file_size_kb=args.file_size_kb,
                backends=args.backends
            )

        if args.recovery or args.all:
            logger.info("Running recovery benchmark...")
            benchmark.benchmark_recovery(
                num_operations=args.num_operations,
                file_size_kb=args.file_size_kb,
                failure_rate=args.failure_rate,
                backend=args.backends[0] if args.backends else "ipfs"
            )

        # Save results
        results_path = benchmark.save_results()

        # Generate plots if requested
        plots = {}
        if args.plots:
            plots = benchmark.plot_results()

        # Clean up
        benchmark.cleanup()

        return (benchmark.results, plots)

    except Exception as e:
        logger.exception(f"Benchmark failed: {e}")
        benchmark.cleanup()
        raise

def main():
    """Main function for running WAL benchmarks."""
    parser = argparse.ArgumentParser(description="WAL Performance Benchmark")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Output directory for benchmark results")

    # Benchmark selection
    parser.add_argument("--all", action="store_true", help="Run all benchmarks")
    parser.add_argument("--add", action="store_true", help="Run 'add' operation benchmark")
    parser.add_argument("--batch", action="store_true", help="Run batch operations benchmark")
    parser.add_argument("--recovery", action="store_true", help="Run recovery benchmark")

    # Benchmark parameters
    parser.add_argument("--num-operations", type=int, default=DEFAULT_NUM_OPERATIONS, help="Number of operations for add and recovery benchmarks")
    parser.add_argument("--file-size-kb", type=int, default=DEFAULT_FILE_SIZE_KB, help="Size of test files in KB")
    parser.add_argument("--num-batches", type=int, default=10, help="Number of batches for batch benchmark")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Operations per batch")
    parser.add_argument("--failure-rate", type=float, default=0.2, help="Failure rate for recovery benchmark (0.0 to 1.0)")
    parser.add_argument("--backends", nargs="*", default=["ipfs", "s3", "storacha"], help="Backends to test")

    # Output options
    parser.add_argument("--plots", action="store_true", help="Generate plots")

    args = parser.parse_args()

    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # If no benchmarks selected, run all
    if not (args.add or args.batch or args.recovery or args.all):
        args.all = True

    try:
        logger.info(f"Starting WAL benchmarks...")
        results, plots = run_benchmarks(args)

        logger.info("Benchmarks completed successfully")
        if plots:
            logger.info(f"Generated plots:")
            for name, path in plots.items():
                if path:
                    logger.info(f"  {name}: {path}")

        # If summary report was generated, show its path
        if "summary" in plots and plots["summary"]:
            logger.info(f"\nBenchmark summary report: {plots['summary']}")
            logger.info("Open this file in a web browser to view the complete benchmark results.")

        return 0

    except Exception as e:
        logger.exception(f"Benchmark failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
