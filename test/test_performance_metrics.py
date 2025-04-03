"""
Tests for the performance_metrics.py module.
"""

import json
import os
import shutil
import statistics
import tempfile
import threading
import time
from collections import deque
from unittest.mock import MagicMock, mock_open, patch

import pytest

from ipfs_kit_py.performance_metrics import PerformanceMetrics, ProfilingContext, profile


class TestPerformanceMetrics:
    """Tests for the PerformanceMetrics class."""

    def test_init_default(self):
        """Test basic initialization with default parameters."""
        metrics = PerformanceMetrics()
        assert metrics.max_history == 1000
        assert metrics.metrics_dir is None
        assert metrics.collection_interval == 300
        assert metrics.enable_logging is True
        assert metrics.track_system_resources is True
        assert metrics.retention_days == 7
        assert metrics.correlation_id is None

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            metrics = PerformanceMetrics(
                max_history=500,
                metrics_dir=temp_dir,
                collection_interval=60,
                enable_logging=False,
                track_system_resources=False,
                retention_days=14,
            )
            assert metrics.max_history == 500
            assert metrics.metrics_dir == temp_dir
            assert metrics.collection_interval == 60
            assert metrics.enable_logging is False
            assert metrics.track_system_resources is False
            assert metrics.retention_days == 14

    def test_reset(self):
        """Test resetting all metrics."""
        metrics = PerformanceMetrics()

        # Add some data
        metrics.latency["test_op"].append(0.1)
        metrics.bandwidth["inbound"].append(
            {"timestamp": time.time(), "size": 1024, "source": "test"}
        )
        metrics.cache["hits"] = 10
        metrics.operations["test_op"] = 5

        # Reset
        metrics.reset()

        # Verify everything is reset
        assert len(metrics.latency["test_op"]) == 0
        assert len(metrics.bandwidth["inbound"]) == 0
        assert metrics.cache["hits"] == 0
        assert metrics.operations["test_op"] == 0

    def test_track_operation(self):
        """Test track_operation context manager."""
        metrics = PerformanceMetrics()

        # Test successful operation
        with metrics.track_operation("test_operation") as tracking:
            assert "test_operation" in metrics.active_operations
            assert tracking["operation"] == "test_operation"
            assert tracking["start_time"] > 0
            time.sleep(0.01)  # Small delay for measurable duration

        assert "test_operation" not in metrics.active_operations
        assert len(metrics.latency["test_operation"]) == 1
        assert metrics.latency["test_operation"][0] > 0

        # Test operation with error
        try:
            with metrics.track_operation("error_operation"):
                raise ValueError("Test error")
        except ValueError:
            pass

        assert "error_operation" not in metrics.active_operations
        assert len(metrics.latency["error_operation"]) == 1
        assert metrics.errors["count"] == 1
        assert metrics.errors["by_type"]["ValueError"] == 1

    def test_set_correlation_id(self):
        """Test setting correlation ID."""
        metrics = PerformanceMetrics()
        assert metrics.correlation_id is None

        metrics.set_correlation_id("test-correlation-id")
        assert metrics.correlation_id == "test-correlation-id"

        # Test correlation tracking in operations
        with metrics.track_operation("correlated_op"):
            time.sleep(0.01)

        assert "test-correlation-id" in metrics.correlated_operations
        assert len(metrics.correlated_operations["test-correlation-id"]) == 1
        assert (
            metrics.correlated_operations["test-correlation-id"][0]["operation"] == "correlated_op"
        )

    @patch("psutil.cpu_percent", return_value=50.0)
    @patch("psutil.cpu_count", return_value=4)
    @patch("psutil.virtual_memory")
    @patch("psutil.disk_usage")
    @patch("psutil.net_io_counters")
    def test_collect_system_metrics(
        self, mock_net_io, mock_disk, mock_memory, mock_cpu_count, mock_cpu_percent
    ):
        """Test collection of system metrics."""
        # Setup mocks
        mock_memory.return_value = MagicMock(
            total=16 * 1024 * 1024 * 1024, available=8 * 1024 * 1024 * 1024, percent=50.0
        )
        mock_disk.return_value = MagicMock(
            total=100 * 1024 * 1024 * 1024,
            used=40 * 1024 * 1024 * 1024,
            free=60 * 1024 * 1024 * 1024,
            percent=40.0,
        )
        mock_net_io.return_value = MagicMock(
            bytes_sent=1024, bytes_recv=2048, packets_sent=10, packets_recv=20
        )

        # Test system metrics collection
        metrics = PerformanceMetrics()
        metrics._collect_system_metrics()

        # Check results
        assert len(metrics.system_metrics["cpu"]) == 1
        cpu_data = metrics.system_metrics["cpu"][0]
        assert cpu_data["percent"] == 50.0
        assert cpu_data["count"] == 4

        assert len(metrics.system_metrics["memory"]) == 1
        memory_data = metrics.system_metrics["memory"][0]
        assert memory_data["percent"] == 50.0
        assert memory_data["total"] == 16 * 1024 * 1024 * 1024

        assert len(metrics.system_metrics["disk"]) == 1
        disk_data = metrics.system_metrics["disk"][0]
        assert disk_data["percent"] == 40.0
        assert disk_data["free"] == 60 * 1024 * 1024 * 1024

        assert len(metrics.system_metrics["network"]) == 1
        network_data = metrics.system_metrics["network"][0]
        assert network_data["bytes_sent"] == 1024
        assert network_data["bytes_recv"] == 2048

    def test_calculate_throughput(self):
        """Test throughput calculation."""
        metrics = PerformanceMetrics()

        # Add operation data
        now = time.time()
        metrics.latency["op1"].append(0.1)
        metrics.latency["op1"].append(0.2)
        metrics.latency["op2"].append(0.3)

        # Add bandwidth data
        metrics.bandwidth["inbound"].append({"timestamp": now, "size": 1024, "source": "test"})
        metrics.bandwidth["outbound"].append({"timestamp": now, "size": 2048, "source": "test"})

        # Calculate throughput
        metrics.throughput["window_size"] = 10  # Use small window for test
        metrics._calculate_throughput()

        # Check results
        assert len(metrics.throughput["operations_per_second"]) == 1
        ops_data = metrics.throughput["operations_per_second"][0]
        assert ops_data["value"] >= 0  # Should have some operations per second

        assert len(metrics.throughput["bytes_per_second"]) == 1
        bytes_data = metrics.throughput["bytes_per_second"][0]
        assert bytes_data["inbound"] >= 0
        assert bytes_data["outbound"] >= 0
        assert bytes_data["total"] == bytes_data["inbound"] + bytes_data["outbound"]

    @patch("os.makedirs")
    @patch("json.dump")
    def test_write_metrics_to_log(self, mock_json_dump, mock_makedirs):
        """Test writing metrics to log file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            metrics = PerformanceMetrics(metrics_dir=temp_dir)

            # Add some test data
            metrics.latency["test_op"].append(0.1)
            metrics.bandwidth["inbound"].append(
                {"timestamp": time.time(), "size": 1024, "source": "test"}
            )
            metrics.cache["hits"] = 10

            # Use patch to mock 'open' contextually
            with patch("builtins.open", mock_open()) as mock_file:
                # Write metrics to log
                metrics._write_metrics_to_log()

                # Check that directories were created
                mock_makedirs.assert_called()

                # Check that file was opened
                mock_file.assert_called()

                # Check that json.dump was called with a dict containing our metrics
                mock_json_dump.assert_called_once()
                # Get the first positional argument to json.dump
                snapshot = mock_json_dump.call_args[0][0]
                assert "timestamp" in snapshot
                assert "latency" in snapshot
                assert "test_op" in snapshot["latency"]
                assert "cache" in snapshot
                assert snapshot["cache"]["hits"] == 10

    def test_create_metrics_snapshot(self):
        """Test creating a metrics snapshot."""
        metrics = PerformanceMetrics()

        # Add some test data
        metrics.latency["test_op"].append(0.1)
        metrics.latency["test_op"].append(0.2)
        metrics.bandwidth["inbound"].append(
            {"timestamp": time.time(), "size": 1024, "source": "test"}
        )
        metrics.cache["hits"] = 10
        metrics.cache["misses"] = 5
        metrics.operations["test_op"] = 2

        # Create snapshot
        snapshot = metrics._create_metrics_snapshot()

        # Check snapshot contents
        assert "timestamp" in snapshot
        assert "session_duration" in snapshot
        assert "cache" in snapshot
        assert snapshot["cache"]["hits"] == 10
        assert snapshot["cache"]["misses"] == 5
        assert snapshot["cache"]["hit_rate"] == (10 / (10 + 5))
        assert "operations" in snapshot
        assert snapshot["operations"]["test_op"] == 2
        assert "latency" in snapshot
        assert "test_op" in snapshot["latency"]
        assert snapshot["latency"]["test_op"]["min"] == 0.1
        assert snapshot["latency"]["test_op"]["max"] == 0.2
        # Use approximately equal for floating point comparison
        assert abs(snapshot["latency"]["test_op"]["mean"] - 0.15) < 0.0001
        assert "bandwidth" in snapshot
        assert snapshot["bandwidth"]["inbound_total"] == 1024

    @patch("os.path.getmtime")
    @patch("os.rmdir")
    @patch("os.remove")
    def test_cleanup_old_logs(self, mock_remove, mock_rmdir, mock_getmtime):
        """Test cleaning up old log files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            metrics = PerformanceMetrics(metrics_dir=temp_dir, retention_days=1)

            # Create test directories and files
            date_dir = os.path.join(temp_dir, "2022-01-01")
            os.makedirs(date_dir, exist_ok=True)
            test_file = os.path.join(date_dir, "test.json")
            with open(test_file, "w") as f:
                f.write("{}")

            # Set up our mocks
            mock_getmtime.return_value = time.time() - (2 * 24 * 3600)  # 2 days old

            # Call the cleanup method
            metrics._cleanup_old_logs()

            # Check that the right methods were called
            mock_remove.assert_called_with(test_file)
            mock_rmdir.assert_called_with(date_dir)

    def test_record_operation_time(self):
        """Test recording operation time."""
        metrics = PerformanceMetrics()

        # Record operation time
        metrics.record_operation_time("test_op", 0.5)

        # Check results
        assert len(metrics.latency["test_op"]) == 1
        assert metrics.latency["test_op"][0] == 0.5
        assert metrics.operations["test_op"] == 1

        # Test with correlation ID
        metrics.record_operation_time("correlated_op", 0.7, correlation_id="test-corr-id")
        assert "test-corr-id" in metrics.correlated_operations
        assert len(metrics.correlated_operations["test-corr-id"]) == 1
        assert metrics.correlated_operations["test-corr-id"][0]["operation"] == "correlated_op"
        assert metrics.correlated_operations["test-corr-id"][0]["elapsed"] == 0.7

    def test_record_bandwidth_usage(self):
        """Test recording bandwidth usage."""
        metrics = PerformanceMetrics()

        # Test inbound bandwidth
        metrics.record_bandwidth_usage("inbound", 1024, source="http")
        assert len(metrics.bandwidth["inbound"]) == 1
        assert metrics.bandwidth["inbound"][0]["size"] == 1024
        assert metrics.bandwidth["inbound"][0]["source"] == "http"

        # Test outbound bandwidth
        metrics.record_bandwidth_usage(
            "outbound", 2048, source="p2p", correlation_id="test-corr-id"
        )
        assert len(metrics.bandwidth["outbound"]) == 1
        assert metrics.bandwidth["outbound"][0]["size"] == 2048
        assert metrics.bandwidth["outbound"][0]["source"] == "p2p"

        # Check correlation
        assert "test-corr-id" in metrics.correlated_operations
        assert len(metrics.correlated_operations["test-corr-id"]) == 1
        assert metrics.correlated_operations["test-corr-id"][0]["operation"] == "bandwidth_outbound"

        # Test invalid direction
        with pytest.raises(ValueError):
            metrics.record_bandwidth_usage("invalid", 1024)

    def test_record_cache_access(self):
        """Test recording cache access."""
        metrics = PerformanceMetrics()

        # Test cache hit
        metrics.record_cache_access("hit", tier="memory")
        assert metrics.cache["hits"] == 1
        assert metrics.cache["misses"] == 0
        assert metrics.cache["tiers"]["memory"]["hits"] == 1
        assert metrics.cache["hit_rate"] == 1.0

        # Test cache miss
        metrics.record_cache_access("miss", tier="disk", correlation_id="test-corr-id")
        assert metrics.cache["hits"] == 1
        assert metrics.cache["misses"] == 1
        assert metrics.cache["tiers"]["disk"]["misses"] == 1
        assert metrics.cache["hit_rate"] == 0.5

        # Check operation recorded
        assert len(metrics.cache["operations"]) == 2

        # Check correlation
        assert "test-corr-id" in metrics.correlated_operations
        assert len(metrics.correlated_operations["test-corr-id"]) == 1
        assert metrics.correlated_operations["test-corr-id"][0]["operation"] == "cache_access"

    def test_record_error(self):
        """Test recording errors."""
        metrics = PerformanceMetrics()

        # Record an error
        error = ValueError("Test error")
        metrics.record_error("test_op", error, details={"extra": "info"})

        # Check error counts
        assert metrics.errors["count"] == 1
        assert metrics.errors["by_type"]["ValueError"] == 1

        # Check error details
        assert len(metrics.errors["recent"]) == 1
        error_record = metrics.errors["recent"][0]
        assert error_record["operation"] == "test_op"
        assert error_record["error_type"] == "ValueError"
        assert error_record["message"] == "Test error"
        assert error_record["details"] == {"extra": "info"}

        # Test with correlation ID
        metrics.record_error("corr_op", error, correlation_id="test-corr-id")
        assert "test-corr-id" in metrics.correlated_operations
        assert len(metrics.correlated_operations["test-corr-id"]) == 1
        assert metrics.correlated_operations["test-corr-id"][0]["operation"] == "error_corr_op"

    def test_get_operation_stats(self):
        """Test getting operation statistics."""
        metrics = PerformanceMetrics()

        # Add operation data
        metrics.latency["test_op"].append(0.1)
        metrics.latency["test_op"].append(0.2)
        metrics.latency["test_op"].append(0.3)

        # Get stats for specific operation
        stats = metrics.get_operation_stats("test_op")
        assert stats["count"] == 3
        assert stats["avg"] == 0.2
        assert stats["min"] == 0.1
        assert stats["max"] == 0.3
        assert stats["median"] == 0.2

        # Get stats for all operations
        all_stats = metrics.get_operation_stats()
        assert "operations" in all_stats
        assert "test_op" in all_stats["operations"]

        # Test with non-existent operation
        no_stats = metrics.get_operation_stats("non_existent")
        assert no_stats["count"] == 0

    def test_get_correlated_operations(self):
        """Test getting correlated operations."""
        metrics = PerformanceMetrics()

        # Add correlated operations
        metrics.correlated_operations["test-corr-id"] = [
            {"operation": "op1", "elapsed": 0.1, "timestamp": time.time()},
            {"operation": "op2", "elapsed": 0.2, "timestamp": time.time()},
        ]

        # Get correlated operations
        ops = metrics.get_correlated_operations("test-corr-id")
        assert len(ops) == 2
        assert ops[0]["operation"] == "op1"
        assert ops[1]["operation"] == "op2"

        # Test with non-existent correlation ID
        no_ops = metrics.get_correlated_operations("non-existent")
        assert no_ops == []

    def test_get_current_throughput(self):
        """Test getting current throughput metrics."""
        metrics = PerformanceMetrics()

        # Add throughput data
        metrics.throughput["operations_per_second"].append({"timestamp": time.time(), "value": 100})
        metrics.throughput["bytes_per_second"].append(
            {"timestamp": time.time(), "inbound": 1024, "outbound": 2048, "total": 3072}
        )

        # Get throughput
        throughput = metrics.get_current_throughput()
        assert throughput["operations_per_second"] == 100
        assert throughput["bytes_per_second"] == 3072

    @patch("psutil.cpu_percent", return_value=50.0)
    @patch("psutil.cpu_count", return_value=4)
    @patch("psutil.virtual_memory")
    @patch("psutil.disk_usage")
    @patch("psutil.net_io_counters")
    def test_get_system_utilization(
        self, mock_net_io, mock_disk, mock_memory, mock_cpu_count, mock_cpu_percent
    ):
        """Test getting system utilization metrics."""
        # Setup mocks
        mock_memory.return_value = MagicMock(
            total=16 * 1024 * 1024 * 1024, available=8 * 1024 * 1024 * 1024, percent=50.0
        )
        mock_disk.return_value = MagicMock(
            total=100 * 1024 * 1024 * 1024,
            used=40 * 1024 * 1024 * 1024,
            free=60 * 1024 * 1024 * 1024,
            percent=40.0,
        )
        mock_net_io.return_value = MagicMock(
            bytes_sent=1024, bytes_recv=2048, packets_sent=10, packets_recv=20
        )

        # Test with tracking enabled
        metrics = PerformanceMetrics(track_system_resources=True)
        metrics._collect_system_metrics()

        util = metrics.get_system_utilization()
        assert util["enabled"] is True
        assert "cpu" in util
        assert "memory" in util
        assert "disk" in util

        # Test with tracking disabled
        metrics_disabled = PerformanceMetrics(track_system_resources=False)
        util_disabled = metrics_disabled.get_system_utilization()
        assert util_disabled["enabled"] is False

    def test_get_error_stats(self):
        """Test getting error statistics."""
        metrics = PerformanceMetrics()

        # Add error data
        metrics.errors["count"] = 5
        metrics.errors["by_type"]["ValueError"] = 3
        metrics.errors["by_type"]["KeyError"] = 2
        metrics.errors["recent"].append({"operation": "op1", "error_type": "ValueError"})

        # Get error stats
        error_stats = metrics.get_error_stats()
        assert error_stats["count"] == 5
        assert error_stats["by_type"]["ValueError"] == 3
        assert error_stats["by_type"]["KeyError"] == 2
        assert error_stats["recent_count"] == 1

    def test_percentile(self):
        """Test percentile calculation."""
        metrics = PerformanceMetrics()

        # Test with simple data
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        # 50th percentile (median)
        p50 = metrics._percentile(data, 50)
        assert p50 == 5.5  # Median of 1-10

        # 90th percentile
        p90 = metrics._percentile(data, 90)
        assert p90 == 9.1  # 90% of values are ≤ 9.1

        # Test with empty data
        assert metrics._percentile([], 50) == 0

    def test_track_latency(self):
        """Test track_latency method (alias for record_operation_time)."""
        metrics = PerformanceMetrics()

        metrics.track_latency("test_op", 0.5)
        assert len(metrics.latency["test_op"]) == 1
        assert metrics.latency["test_op"][0] == 0.5

    def test_track_bandwidth(self):
        """Test track_bandwidth method (alias for record_bandwidth_usage)."""
        metrics = PerformanceMetrics()

        metrics.track_bandwidth("inbound", 1024, endpoint="test")
        assert len(metrics.bandwidth["inbound"]) == 1
        assert metrics.bandwidth["inbound"][0]["size"] == 1024
        assert metrics.bandwidth["inbound"][0]["source"] == "test"

    def test_track_cache_access(self):
        """Test track_cache_access method."""
        metrics = PerformanceMetrics()

        # Test hit
        metrics.track_cache_access(True, tier="memory")
        assert metrics.cache["hits"] == 1
        assert metrics.cache["misses"] == 0

        # Test miss
        metrics.track_cache_access(False, tier="disk")
        assert metrics.cache["hits"] == 1
        assert metrics.cache["misses"] == 1

    def test_analyze_metrics(self):
        """Test metrics analysis."""
        metrics = PerformanceMetrics()

        # Add data for analysis
        metrics.latency["fast_op"].append(0.1)
        metrics.latency["slow_op"].append(1.0)

        metrics.bandwidth["inbound"].append(
            {"timestamp": time.time(), "size": 1024, "source": "test"}
        )
        metrics.bandwidth["outbound"].append(
            {"timestamp": time.time(), "size": 2048, "source": "test"}
        )

        metrics.cache["hits"] = 7
        metrics.cache["misses"] = 3
        metrics.cache["tiers"]["memory"] = {"hits": 5, "misses": 1}
        metrics.cache["tiers"]["disk"] = {"hits": 2, "misses": 2}

        metrics.operations["fast_op"] = 1
        metrics.operations["slow_op"] = 1

        # Run analysis
        analysis = metrics.analyze_metrics()

        # Check analysis results
        assert "timestamp" in analysis
        assert "summary" in analysis
        assert "slowest_operation" in analysis["summary"]
        assert analysis["summary"]["slowest_operation"]["operation"] == "slow_op"

        assert "latency_avg" in analysis
        assert "bandwidth_total" in analysis
        assert "cache_hit_rate" in analysis
        assert analysis["cache_hit_rate"] == 0.7  # 7 hits out of 10 total

        assert "tier_hit_rates" in analysis
        assert analysis["tier_hit_rates"]["memory"] == 0.8333333333333334  # 5 hits out of 6 total
        assert analysis["tier_hit_rates"]["disk"] == 0.5  # 2 hits out of 4 total

        assert "recommendations" in analysis

    def test_generate_report_json(self):
        """Test generating a JSON report."""
        metrics = PerformanceMetrics()

        # Add some test data
        metrics.latency["test_op"].append(0.1)

        # Generate JSON report
        report = metrics.generate_report(output_format="json")

        # Verify it's valid JSON
        report_data = json.loads(report)
        assert "timestamp" in report_data
        assert "latency_avg" in report_data

    def test_generate_report_markdown(self):
        """Test generating a Markdown report."""
        metrics = PerformanceMetrics()

        # Add some test data
        metrics.latency["test_op"].append(0.1)
        metrics.cache["hits"] = 7
        metrics.cache["misses"] = 3

        # Generate Markdown report
        report = metrics.generate_report(output_format="markdown")

        # Check report format
        assert "# IPFS Performance Report" in report
        assert "## Performance Summary" in report
        assert "## Latency Statistics" in report
        assert "| Operation" in report

    def test_generate_report_text(self):
        """Test generating a text report."""
        metrics = PerformanceMetrics()

        # Add some test data
        metrics.latency["test_op"].append(0.1)
        metrics.cache["hits"] = 7
        metrics.cache["misses"] = 3

        # Generate text report
        report = metrics.generate_report(output_format="text")

        # Check report format
        assert "IPFS PERFORMANCE REPORT" in report
        assert "PERFORMANCE SUMMARY:" in report
        assert "LATENCY STATISTICS:" in report
        assert "CACHE PERFORMANCE:" in report

    def test_format_size(self):
        """Test size formatting."""
        metrics = PerformanceMetrics()

        assert metrics._format_size(500) == "500.00 B"
        assert metrics._format_size(1500) == "1.46 KB"
        assert metrics._format_size(1500000) == "1.43 MB"
        assert metrics._format_size(1500000000) == "1.43 GB"
        assert metrics._format_size(1500000000000) == "1.36 TB"

    def test_format_duration(self):
        """Test duration formatting."""
        metrics = PerformanceMetrics()

        assert metrics._format_duration(30) == "30.00 seconds"
        assert metrics._format_duration(90) == "1.50 minutes"
        assert metrics._format_duration(3600) == "1.00 hours"

    def test_find_correlation_patterns(self):
        """Test finding correlation patterns."""
        metrics = PerformanceMetrics()

        # Add correlated operations
        metrics.correlated_operations["id1"] = [
            {"operation": "op1", "timestamp": time.time()},
            {"operation": "op2", "timestamp": time.time()},
        ]
        metrics.correlated_operations["id2"] = [
            {"operation": "op1", "timestamp": time.time()},
            {"operation": "op2", "timestamp": time.time()},
        ]

        # Find patterns
        patterns = metrics.find_correlation_patterns()

        assert "operation_correlations" in patterns
        assert len(patterns["operation_correlations"]) > 0

    @patch("threading.Thread")
    def test_shutdown(self, mock_thread):
        """Test metrics handler shutdown."""
        # Mock thread
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        # Setup metrics with collection thread
        with tempfile.TemporaryDirectory() as temp_dir:
            metrics = PerformanceMetrics(metrics_dir=temp_dir, enable_logging=True)

            # Force thread setup manually (since we mocked threading.Thread)
            metrics.stop_collection = threading.Event()
            metrics.collection_thread = mock_thread_instance

            # Shutdown metrics
            with patch.object(metrics, "_write_metrics_to_log") as mock_write:
                metrics.shutdown()

                # Verify thread was joined
                mock_thread_instance.join.assert_called_once()

                # Verify final metrics were written
                mock_write.assert_called_once()


class TestProfilingContext:
    """Tests for the ProfilingContext class."""

    def test_init(self):
        """Test initialization."""
        metrics = PerformanceMetrics()
        ctx = ProfilingContext(metrics, "test_context")

        assert ctx.metrics == metrics
        assert ctx.name == "test_context"
        assert ctx.correlation_id is None
        assert ctx.start_time is None
        assert ctx.end_time is None

    def test_context_manager(self):
        """Test context manager behavior."""
        metrics = PerformanceMetrics()

        # Test successful operation
        with ProfilingContext(metrics, "test_context") as ctx:
            assert ctx.start_time is not None
            time.sleep(0.01)

        assert ctx.end_time is not None
        assert len(metrics.latency["test_context"]) == 1

        # Test operation with error
        try:
            with ProfilingContext(metrics, "error_context"):
                raise ValueError("Test error")
        except ValueError:
            pass

        assert len(metrics.latency["error_context"]) == 1
        assert metrics.errors["count"] == 1


def test_profile_decorator():
    """Test the profile decorator."""
    metrics = PerformanceMetrics()

    # Define a function to profile
    @profile(metrics, "custom_name")
    def test_function():
        time.sleep(0.01)
        return "result"

    # Call the function
    result = test_function()

    # Check results
    assert result == "result"
    assert len(metrics.latency["custom_name"]) == 1

    # Test with default name
    @profile(metrics)
    def another_function():
        time.sleep(0.01)
        return "another result"

    another_result = another_function()

    assert another_result == "another result"
    assert len(metrics.latency["another_function"]) == 1

    # Test with error
    @profile(metrics)
    def error_function():
        raise ValueError("Test error")

    try:
        error_function()
    except ValueError:
        pass

    assert len(metrics.latency["error_function"]) == 1
    assert metrics.errors["count"] == 1
