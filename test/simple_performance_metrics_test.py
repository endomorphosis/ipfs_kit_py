"""
Simple unittest-based tests for the performance_metrics.py module.

This file uses unittest directly instead of pytest to avoid conftest.py issues.
"""

import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from collections import deque
from unittest.mock import MagicMock, patch

# Import the module to test
from ipfs_kit_py.performance_metrics import PerformanceMetrics, ProfilingContext, profile


class TestPerformanceMetrics(unittest.TestCase):
    """Test cases for PerformanceMetrics class."""

    def setUp(self):
        """Set up test fixtures before each test."""
        # Create a metrics instance without background collection
        self.metrics = PerformanceMetrics(
            max_history=100, enable_logging=False, track_system_resources=False
        )

    def test_initialization(self):
        """Test PerformanceMetrics initialization."""
        self.assertEqual(self.metrics.max_history, 100)
        self.assertFalse(self.metrics.enable_logging)
        self.assertFalse(self.metrics.track_system_resources)
        self.assertIsNone(self.metrics.metrics_dir)
        self.assertIsNone(self.metrics.correlation_id)

        # Check if data structures are initialized
        self.assertIsInstance(self.metrics.latency, dict)
        self.assertIsInstance(self.metrics.bandwidth, dict)
        self.assertIsInstance(self.metrics.cache, dict)
        self.assertIsInstance(self.metrics.operations, dict)
        self.assertIsInstance(self.metrics.system_metrics, dict)
        self.assertIsInstance(self.metrics.errors, dict)
        self.assertIsInstance(self.metrics.throughput, dict)
        self.assertIsInstance(self.metrics.active_operations, set)

    def test_reset(self):
        """Test reset method."""
        # Add some test data first
        self.metrics.latency["test_op"] = deque([0.1, 0.2, 0.3])
        self.metrics.operations["test_op"] = 3
        self.metrics.cache["hits"] = 10

        # Reset
        self.metrics.reset()

        # Verify reset state
        self.assertEqual(len(self.metrics.latency["test_op"]), 0)
        self.assertEqual(self.metrics.operations["test_op"], 0)
        self.assertEqual(self.metrics.cache["hits"], 0)

    def test_record_operation_time(self):
        """Test recording operation time."""
        self.metrics.record_operation_time("test_operation", 0.5)

        # Check if data is recorded
        self.assertIn("test_operation", self.metrics.latency)
        self.assertEqual(len(self.metrics.latency["test_operation"]), 1)
        self.assertEqual(self.metrics.latency["test_operation"][0], 0.5)
        self.assertEqual(self.metrics.operations["test_operation"], 1)

    def test_record_operation_time_with_correlation(self):
        """Test recording operation time with correlation ID."""
        self.metrics.record_operation_time("test_operation", 0.5, correlation_id="corr123")

        # Check if correlation is recorded
        self.assertIn("corr123", self.metrics.correlated_operations)
        self.assertEqual(len(self.metrics.correlated_operations["corr123"]), 1)
        self.assertEqual(
            self.metrics.correlated_operations["corr123"][0]["operation"], "test_operation"
        )
        self.assertEqual(self.metrics.correlated_operations["corr123"][0]["elapsed"], 0.5)

    def test_record_bandwidth_usage(self):
        """Test recording bandwidth usage."""
        self.metrics.record_bandwidth_usage("inbound", 1024, source="http")

        # Check if data is recorded
        self.assertEqual(len(self.metrics.bandwidth["inbound"]), 1)
        self.assertEqual(self.metrics.bandwidth["inbound"][0]["size"], 1024)
        self.assertEqual(self.metrics.bandwidth["inbound"][0]["source"], "http")

        # Test with invalid direction
        with self.assertRaises(ValueError):
            self.metrics.record_bandwidth_usage("invalid", 1024)

    def test_record_cache_access(self):
        """Test recording cache access."""
        # Test hit
        self.metrics.record_cache_access("hit", tier="memory")
        self.assertEqual(self.metrics.cache["hits"], 1)
        self.assertEqual(self.metrics.cache["misses"], 0)
        self.assertEqual(self.metrics.cache["tiers"]["memory"]["hits"], 1)

        # Test miss
        self.metrics.record_cache_access("miss", tier="disk")
        self.assertEqual(self.metrics.cache["hits"], 1)
        self.assertEqual(self.metrics.cache["misses"], 1)
        self.assertEqual(self.metrics.cache["tiers"]["disk"]["misses"], 1)

        # Check hit rate calculation
        self.assertEqual(self.metrics.cache["hit_rate"], 0.5)  # 1 hit, 1 miss

    def test_record_error(self):
        """Test recording an error."""
        try:
            raise ValueError("Test error")
        except ValueError as e:
            self.metrics.record_error("test_operation", e)

        # Check if error is recorded
        self.assertEqual(self.metrics.errors["count"], 1)
        self.assertEqual(self.metrics.errors["by_type"]["ValueError"], 1)
        self.assertEqual(len(self.metrics.errors["recent"]), 1)
        self.assertEqual(self.metrics.errors["recent"][0]["error_type"], "ValueError")
        self.assertEqual(self.metrics.errors["recent"][0]["message"], "Test error")

    def test_track_operation_context_manager(self):
        """Test track_operation context manager."""
        # Test successful operation
        with self.metrics.track_operation("test_operation") as tracking:
            self.assertIn("test_operation", self.metrics.active_operations)
            self.assertEqual(tracking["operation"], "test_operation")
            self.assertGreater(tracking["start_time"], 0)
            time.sleep(0.01)  # Small delay for measurable duration

        # Check if operation was tracked
        self.assertNotIn("test_operation", self.metrics.active_operations)
        self.assertEqual(len(self.metrics.latency["test_operation"]), 1)
        self.assertGreater(self.metrics.latency["test_operation"][0], 0)

        # Test operation with error
        try:
            with self.metrics.track_operation("error_operation"):
                time.sleep(0.01)
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Check if error and operation time were recorded
        self.assertEqual(self.metrics.errors["count"], 1)
        self.assertEqual(len(self.metrics.latency["error_operation"]), 1)

    def test_get_operation_stats(self):
        """Test getting operation statistics."""
        # Add some test data
        self.metrics.record_operation_time("test_op", 0.1)
        self.metrics.record_operation_time("test_op", 0.2)
        self.metrics.record_operation_time("test_op", 0.3)

        # Get stats for specific operation
        stats = self.metrics.get_operation_stats("test_op")
        self.assertEqual(stats["count"], 3)
        self.assertEqual(stats["min"], 0.1)
        self.assertEqual(stats["max"], 0.3)
        self.assertAlmostEqual(stats["avg"], 0.2, delta=0.01)

        # Get stats for all operations
        all_stats = self.metrics.get_operation_stats()
        self.assertIn("operations", all_stats)
        self.assertIn("test_op", all_stats["operations"])

    def test_get_correlated_operations(self):
        """Test getting correlated operations."""
        # Add correlated operations
        self.metrics.record_operation_time("op1", 0.1, correlation_id="corr123")
        self.metrics.record_operation_time("op2", 0.2, correlation_id="corr123")

        # Get correlated operations
        corr_ops = self.metrics.get_correlated_operations("corr123")
        self.assertEqual(len(corr_ops), 2)
        self.assertEqual(corr_ops[0]["operation"], "op1")
        self.assertEqual(corr_ops[1]["operation"], "op2")

        # Test with non-existent correlation ID
        self.assertEqual(self.metrics.get_correlated_operations("nonexistent"), [])

    def test_get_current_throughput(self):
        """Test getting current throughput."""
        # By default, throughput should be zero
        throughput = self.metrics.get_current_throughput()
        self.assertEqual(throughput["operations_per_second"], 0)
        self.assertEqual(throughput["bytes_per_second"], 0)

    def test_get_system_utilization(self):
        """Test getting system utilization."""
        # Without system tracking enabled
        util = self.metrics.get_system_utilization()
        self.assertFalse(util["enabled"])

    def test_analyze_metrics(self):
        """Test analyzing metrics."""
        # Add some test data
        self.metrics.record_operation_time("fast_op", 0.1)
        self.metrics.record_operation_time("slow_op", 1.5)
        self.metrics.record_cache_access("hit", tier="memory")
        self.metrics.record_cache_access("miss", tier="disk")

        # Get analysis
        analysis = self.metrics.analyze_metrics()

        # Check basic structure
        self.assertIn("timestamp", analysis)
        self.assertIn("session_duration", analysis)
        self.assertIn("summary", analysis)
        self.assertIn("recommendations", analysis)

        # Check specific analysis results
        self.assertIn("latency_avg", analysis)
        self.assertIn("slow_op", analysis["latency_avg"])
        self.assertIn("fast_op", analysis["latency_avg"])
        self.assertIn("cache_hit_rate", analysis)
        self.assertAlmostEqual(analysis["cache_hit_rate"], 0.5, delta=0.01)

    def test_percentile_calculation(self):
        """Test percentile calculation."""
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        # Test various percentiles
        self.assertEqual(self.metrics._percentile(data, 50), 5.5)  # Median
        self.assertEqual(self.metrics._percentile(data, 0), 1)  # Min
        self.assertEqual(self.metrics._percentile(data, 100), 10)  # Max
        self.assertEqual(self.metrics._percentile(data, 25), 3.25)  # First quartile
        self.assertEqual(self.metrics._percentile(data, 75), 7.75)  # Third quartile

        # Test with empty data
        self.assertEqual(self.metrics._percentile([], 50), 0)

    def test_format_size(self):
        """Test size formatting."""
        self.assertEqual(self.metrics._format_size(500), "500.00 B")
        self.assertEqual(self.metrics._format_size(1024), "1.00 KB")
        self.assertEqual(self.metrics._format_size(1024 * 1024), "1.00 MB")
        self.assertEqual(self.metrics._format_size(1024 * 1024 * 1024), "1.00 GB")
        self.assertEqual(self.metrics._format_size(1024 * 1024 * 1024 * 1024), "1.00 TB")

    def test_format_duration(self):
        """Test duration formatting."""
        self.assertEqual(self.metrics._format_duration(30), "30.00 seconds")
        self.assertEqual(self.metrics._format_duration(90), "1.50 minutes")
        self.assertEqual(self.metrics._format_duration(3600), "1.00 hours")

    @patch("psutil.cpu_percent")
    @patch("psutil.virtual_memory")
    @patch("psutil.disk_usage")
    @patch("psutil.net_io_counters")
    def test_collect_system_metrics(self, mock_net, mock_disk, mock_mem, mock_cpu):
        """Test collecting system metrics."""
        # Create metrics with system tracking enabled
        metrics = PerformanceMetrics(track_system_resources=True, enable_logging=False)

        # Mock system metrics
        mock_cpu.return_value = 50.0
        mock_mem.return_value = MagicMock(total=16000000000, available=8000000000, percent=50.0)
        mock_disk.return_value = MagicMock(
            total=500000000000, used=250000000000, free=250000000000, percent=50.0
        )
        mock_net.return_value = MagicMock(
            bytes_sent=1000000, bytes_recv=2000000, packets_sent=1000, packets_recv=2000
        )

        # Call the method
        metrics._collect_system_metrics()

        # Check if metrics were collected
        self.assertEqual(len(metrics.system_metrics["cpu"]), 1)
        self.assertEqual(metrics.system_metrics["cpu"][0]["percent"], 50.0)

        self.assertEqual(len(metrics.system_metrics["memory"]), 1)
        self.assertEqual(metrics.system_metrics["memory"][0]["percent"], 50.0)

        self.assertEqual(len(metrics.system_metrics["disk"]), 1)
        self.assertEqual(metrics.system_metrics["disk"][0]["percent"], 50.0)

        self.assertEqual(len(metrics.system_metrics["network"]), 1)
        self.assertEqual(metrics.system_metrics["network"][0]["bytes_sent"], 1000000)


class TestProfilingContext(unittest.TestCase):
    """Test cases for ProfilingContext class."""

    def setUp(self):
        """Set up test fixtures before each test."""
        self.metrics = PerformanceMetrics(enable_logging=False)

    def test_successful_profiling(self):
        """Test successful profiling context."""
        with ProfilingContext(self.metrics, "test_profiling") as profile:
            self.assertIsNotNone(profile.start_time)
            time.sleep(0.01)  # Small delay for measurable duration

        # Check if profiling recorded the operation
        self.assertIsNotNone(profile.end_time)
        self.assertGreater(profile.end_time, profile.start_time)
        self.assertEqual(len(self.metrics.latency["test_profiling"]), 1)

    def test_profiling_with_error(self):
        """Test profiling context with error."""
        try:
            with ProfilingContext(self.metrics, "error_profiling"):
                time.sleep(0.01)
                raise ValueError("Test error")
        except ValueError:
            pass

        # Check if error was recorded
        self.assertEqual(self.metrics.errors["count"], 1)
        self.assertEqual(self.metrics.errors["by_type"]["ValueError"], 1)
        self.assertEqual(len(self.metrics.latency["error_profiling"]), 1)


class TestProfileDecorator(unittest.TestCase):
    """Test cases for profile decorator."""

    def setUp(self):
        """Set up test fixtures before each test."""
        self.metrics = PerformanceMetrics(enable_logging=False)

    def test_decorated_function(self):
        """Test decorating a function with @profile."""

        @profile(self.metrics, name="decorated_test")
        def test_function():
            time.sleep(0.01)
            return "test result"

        # Call the decorated function
        result = test_function()

        # Check if profiling worked
        self.assertEqual(result, "test result")
        self.assertEqual(len(self.metrics.latency["decorated_test"]), 1)
        self.assertGreater(self.metrics.latency["decorated_test"][0], 0)

    def test_decorated_function_with_error(self):
        """Test decorating a function that raises an error."""

        @profile(self.metrics)
        def error_function():
            time.sleep(0.01)
            raise ValueError("Test error")

        # Call the decorated function
        try:
            error_function()
        except ValueError:
            pass

        # Check if error was recorded
        self.assertEqual(self.metrics.errors["count"], 1)
        self.assertEqual(self.metrics.errors["by_type"]["ValueError"], 1)
        self.assertEqual(len(self.metrics.latency["error_function"]), 1)


class TestMetricsLoggerWithTempDir(unittest.TestCase):
    """Test cases for metrics logging with a temporary directory."""

    def setUp(self):
        """Set up test fixtures before each test."""
        # Create a temporary directory for metrics
        self.metrics_dir = tempfile.mkdtemp()

        # Create metrics with logging enabled
        self.metrics = PerformanceMetrics(
            max_history=100,
            metrics_dir=self.metrics_dir,
            enable_logging=False,  # Don't start background thread
            collection_interval=1,
            retention_days=1,
        )

    def tearDown(self):
        """Clean up after each test."""
        if hasattr(self, "metrics_dir") and os.path.exists(self.metrics_dir):
            shutil.rmtree(self.metrics_dir)

    def test_write_metrics_to_log(self):
        """Test writing metrics to log file."""
        # Add some test data
        self.metrics.record_operation_time("test_op", 0.1)
        self.metrics.record_cache_access("hit", tier="memory")

        # Manually write metrics to log
        self.metrics._write_metrics_to_log()

        # Check if log file was created
        date_str = time.strftime("%Y-%m-%d", time.localtime(time.time()))
        date_dir = os.path.join(self.metrics_dir, date_str)
        self.assertTrue(os.path.exists(date_dir))

        # Should have one file in the directory
        files = os.listdir(date_dir)
        self.assertEqual(len(files), 1)

        # Check if file contains valid JSON
        with open(os.path.join(date_dir, files[0]), "r") as f:
            data = json.load(f)
            self.assertIn("timestamp", data)
            self.assertIn("latency", data)
            self.assertIn("cache", data)

    def test_create_metrics_snapshot(self):
        """Test creating a metrics snapshot."""
        # Add some test data
        self.metrics.record_operation_time("test_op", 0.1)
        self.metrics.record_cache_access("hit", tier="memory")

        # Create snapshot
        snapshot = self.metrics._create_metrics_snapshot()

        # Check snapshot structure
        self.assertIn("timestamp", snapshot)
        self.assertIn("session_duration", snapshot)
        self.assertIn("cache", snapshot)
        self.assertIn("operations", snapshot)
        self.assertIn("latency", snapshot)
        self.assertIn("bandwidth", snapshot)
        self.assertIn("errors", snapshot)
        self.assertIn("throughput", snapshot)

    def test_cleanup_old_logs(self):
        """Test cleaning up old logs."""
        # Create a directory structure with an "old" date directory
        old_date = "2000-01-01"  # Very old date
        old_date_dir = os.path.join(self.metrics_dir, old_date)
        os.makedirs(old_date_dir, exist_ok=True)

        # Create a test file in the old directory
        with open(os.path.join(old_date_dir, "test_metrics.json"), "w") as f:
            f.write('{"test": "data"}')

        # Set the directory's modification time to be old
        old_time = time.time() - (self.metrics.retention_days + 1) * 24 * 3600
        os.utime(old_date_dir, (old_time, old_time))

        # Run cleanup
        self.metrics._cleanup_old_logs()

        # Check if the old directory was removed
        self.assertFalse(os.path.exists(old_date_dir))

        # Test with invalid directory name (should be skipped)
        invalid_dir = os.path.join(self.metrics_dir, "not-a-date-dir")
        os.makedirs(invalid_dir, exist_ok=True)

        # Run cleanup again
        self.metrics._cleanup_old_logs()

        # Invalid directory should still exist
        self.assertTrue(os.path.exists(invalid_dir))

    def test_generate_report_json(self):
        """Test report generation in JSON format."""
        # Add some test data
        self.metrics.record_operation_time("test_op", 0.1)
        self.metrics.record_cache_access("hit", tier="memory")

        # Generate JSON report
        report = self.metrics.generate_report(output_format="json")

        # Verify it's valid JSON
        data = json.loads(report)
        self.assertIn("timestamp", data)
        self.assertIn("session_duration", data)
        self.assertIn("latency_avg", data)

    def test_generate_report_markdown(self):
        """Test report generation in Markdown format."""
        # Add some test data
        self.metrics.record_operation_time("test_op", 0.1)
        self.metrics.record_cache_access("hit", tier="memory")

        # Generate Markdown report
        report = self.metrics.generate_report(output_format="markdown")

        # Check report structure
        self.assertIn("# IPFS Performance Report", report)
        self.assertIn("## Performance Summary", report)
        self.assertIn("## Latency Statistics", report)
        self.assertIn("| Operation | Count | Avg (s) | Min (s) | Max (s) | P95 (s) |", report)

    def test_generate_report_text(self):
        """Test report generation in text format."""
        # Add some test data
        self.metrics.record_operation_time("test_op", 0.1)
        self.metrics.record_cache_access("hit", tier="memory")

        # Generate text report
        report = self.metrics.generate_report(output_format="text")

        # Check report structure
        self.assertIn("IPFS PERFORMANCE REPORT", report)
        self.assertIn("PERFORMANCE SUMMARY:", report)
        self.assertIn("LATENCY STATISTICS:", report)

    @patch("threading.Thread")
    def test_metrics_collection_thread(self, mock_thread):
        """Test metrics collection thread initialization."""
        # Create metrics with logging and collection enabled
        metrics = PerformanceMetrics(
            max_history=100,
            metrics_dir=self.metrics_dir,
            enable_logging=True,
            collection_interval=1,
        )

        # Check if thread was started
        mock_thread.assert_called_once()
        self.assertTrue(hasattr(metrics, "collection_thread"))
        self.assertTrue(hasattr(metrics, "stop_collection"))
        self.assertFalse(metrics.stop_collection.is_set())

        # Clean up
        metrics.shutdown()
        self.assertTrue(metrics.stop_collection.is_set())

    @patch("time.sleep", return_value=None)  # Don't actually sleep
    def test_collection_loop(self, mock_sleep):
        """Test the collection loop function."""
        # Create a mock for _collect_metrics and _write_metrics_to_log
        self.metrics._collect_metrics = MagicMock()
        self.metrics._write_metrics_to_log = MagicMock()
        self.metrics._cleanup_old_logs = MagicMock()

        # Set up the stop event
        self.metrics.stop_collection = threading.Event()

        # Run the collection loop for one iteration
        def set_stop_after_one_iteration(*args, **kwargs):
            self.metrics.stop_collection.set()

        # Set stop after first iteration
        mock_sleep.side_effect = set_stop_after_one_iteration

        # Run the loop
        self.metrics._collection_loop()

        # Verify methods were called
        self.metrics._collect_metrics.assert_called_once()
        self.metrics._write_metrics_to_log.assert_called_once()
        self.metrics._cleanup_old_logs.assert_called_once()

    def test_calculate_throughput(self):
        """Test throughput calculation."""
        # Directly modify the latency data structure to simulate recent operations
        # This is needed because the implementation looks at timestamp values in the
        # latency deque, which we need to control for the test
        now = time.time()
        window = self.metrics.throughput["window_size"]  # Default 60 seconds

        # Create test data with controlled timestamps
        # Add operations within time window by directly manipulating the internal structures
        # (Since we're testing internal implementation, we need to match the expected format)
        self.metrics.latency["test_op"] = deque(maxlen=self.metrics.max_history)
        for i in range(5):
            # Add operation time directly
            self.metrics.latency["test_op"].append(0.1)
            # Increment operation count
            self.metrics.operations["test_op"] += 1

        # Add bandwidth data within window
        self.metrics.bandwidth["inbound"].append(
            {
                "timestamp": now - 10,  # 10 seconds ago, within the window
                "size": 1024,
                "source": "http",
            }
        )
        self.metrics.bandwidth["outbound"].append(
            {"timestamp": now - 10, "size": 2048, "source": "http"}
        )

        # Patch time.time to return a fixed value during calculation
        with patch("time.time", return_value=now):
            # Run throughput calculation
            self.metrics._calculate_throughput()

        # Check results
        self.assertEqual(len(self.metrics.throughput["operations_per_second"]), 1)
        self.assertEqual(len(self.metrics.throughput["bytes_per_second"]), 1)

        ops_entry = self.metrics.throughput["operations_per_second"][0]
        bytes_entry = self.metrics.throughput["bytes_per_second"][0]

        # Instead of checking exact values which depend on implementation details,
        # verify the structure and reasonable outputs
        self.assertIn("timestamp", ops_entry)
        self.assertIn("value", ops_entry)

        # Check bytes calculations which are more predictable
        self.assertAlmostEqual(bytes_entry["inbound"], 1024 / window, delta=0.1)
        self.assertAlmostEqual(bytes_entry["outbound"], 2048 / window, delta=0.1)
        self.assertAlmostEqual(bytes_entry["total"], 3072 / window, delta=0.1)

    @patch("psutil.cpu_percent")
    @patch("psutil.virtual_memory")
    @patch("psutil.disk_usage")
    @patch("psutil.net_io_counters")
    def test_get_system_utilization_with_data(self, mock_net, mock_disk, mock_mem, mock_cpu):
        """Test getting system utilization with metrics enabled."""
        # Create a metrics instance with system tracking
        metrics = PerformanceMetrics(enable_logging=False, track_system_resources=True)

        # Mock system metrics
        mock_cpu.return_value = 50.0
        mock_mem.return_value = MagicMock(total=16000000000, available=8000000000, percent=50.0)
        mock_disk.return_value = MagicMock(
            total=500000000000, used=250000000000, free=250000000000, percent=50.0
        )
        mock_net.return_value = MagicMock(
            bytes_sent=1000000, bytes_recv=2000000, packets_sent=1000, packets_recv=2000
        )

        # Collect system metrics
        metrics._collect_system_metrics()

        # Get system utilization
        util = metrics.get_system_utilization()

        # Check structure and data
        self.assertTrue(util["enabled"])
        self.assertIn("cpu", util)
        self.assertIn("memory", util)
        self.assertIn("disk", util)
        self.assertIn("network", util)

        self.assertEqual(util["cpu"]["percent"], 50.0)
        self.assertEqual(util["memory"]["percent"], 50.0)
        self.assertEqual(util["disk"]["percent"], 50.0)

    def test_find_correlation_patterns(self):
        """Test finding correlation patterns."""
        # Add some correlated operations
        self.metrics.correlated_operations["corr1"] = [
            {"operation": "op1", "elapsed": 0.1, "timestamp": time.time()},
            {"operation": "op2", "elapsed": 0.2, "timestamp": time.time()},
        ]
        self.metrics.correlated_operations["corr2"] = [
            {"operation": "op1", "elapsed": 0.1, "timestamp": time.time()},
            {"operation": "op3", "elapsed": 0.3, "timestamp": time.time()},
        ]

        # Get correlation patterns
        patterns = self.metrics.find_correlation_patterns()

        # Verify structure
        self.assertIn("operation_correlations", patterns)
        self.assertIn("latency_vs_cache", patterns)
        self.assertIn("system_impact", patterns)

        # Check operation correlations
        self.assertGreater(len(patterns["operation_correlations"]), 0)

    @patch("threading.Thread")
    def test_shutdown(self, mock_thread):
        """Test metrics shutdown functionality."""
        # Create metrics with mocked thread
        metrics = PerformanceMetrics(
            max_history=100, metrics_dir=self.metrics_dir, enable_logging=True
        )

        # Mock thread join
        metrics.collection_thread.join = MagicMock()

        # Mock _write_metrics_to_log
        metrics._write_metrics_to_log = MagicMock()

        # Shutdown
        metrics.shutdown()

        # Verify stop event was set
        self.assertTrue(metrics.stop_collection.is_set())

        # Verify thread was joined
        metrics.collection_thread.join.assert_called_once()

        # Verify final metrics were written
        metrics._write_metrics_to_log.assert_called_once()


if __name__ == "__main__":
    unittest.main()
