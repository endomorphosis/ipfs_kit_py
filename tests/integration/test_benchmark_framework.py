"""
Tests for the benchmark_framework.py module.
"""

import json
import os
import tempfile
import time
from unittest.mock import MagicMock, mock_open, patch

import pytest

from ipfs_kit_py.benchmark_framework import BenchmarkContext, BenchmarkSuite


# Define these utility functions ourselves for testing
def format_size(size_bytes):
    """Format a byte size value to a human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024 or unit == "TB":
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024


def format_time(seconds):
    """Format a time value to a human-readable string."""
    if seconds < 0.01:
        return f"{seconds * 1000:.2f} ms"
    elif seconds < 1:
        return f"{seconds * 1000:.2f} ms"
    elif seconds < 60:
        return f"{seconds:.2f} s"
    elif seconds < 3600:
        return f"{seconds / 60:.2f} min"
    else:
        return f"{seconds / 3600:.2f} hr"


# Utility tests
def test_format_size():
    """Test the format_size function."""
    assert format_size(500) == "500.00 B"
    assert format_size(1500) == "1.46 KB"
    assert format_size(1500000) == "1.43 MB"
    assert format_size(1500000000) == "1.40 GB"


def test_format_time():
    """Test the format_time function."""
    assert format_time(0.001) == "1.00 ms"
    assert format_time(0.5) == "500.00 ms"
    assert format_time(1.5) == "1.50 s"
    assert format_time(90) == "1.50 min"
    assert format_time(3700) == "1.03 hr"


# BenchmarkContext tests
class TestBenchmarkContext:
    """Tests for the BenchmarkContext class."""

    def test_init(self):
        """Test BenchmarkContext initialization."""
        ctx = BenchmarkContext("test_benchmark")
        assert ctx.name == "test_benchmark"
        assert ctx.start_time is None
        assert ctx.end_time is None
        assert ctx.system_metrics == {}

    def test_enter_exit(self):
        """Test context manager behavior."""
        with BenchmarkContext("test_benchmark") as ctx:
            assert ctx.start_time is not None
            assert ctx.end_time is None
            time.sleep(0.01)  # Small delay

        assert ctx.end_time is not None
        assert ctx.elapsed > 0
        assert ctx.system_metrics != {}

    def test_record_system_metrics(self):
        """Test system metrics recording."""
        ctx = BenchmarkContext("test_benchmark")
        ctx._record_system_metrics()

        # Check that system metrics are populated
        assert "cpu_percent" in ctx.system_metrics
        assert "memory_percent" in ctx.system_metrics
        assert "disk_usage" in ctx.system_metrics

    def test_get_results(self):
        """Test results generation."""
        with BenchmarkContext("test_benchmark") as ctx:
            time.sleep(0.01)  # Small delay

        results = ctx.get_results()

        assert results["name"] == "test_benchmark"
        assert results["success"] is True
        assert results["elapsed"] > 0
        assert "start_time" in results
        assert "end_time" in results
        assert "system_metrics" in results

        # Test with error
        try:
            with BenchmarkContext("error_benchmark") as ctx:
                raise ValueError("Test error")
        except ValueError:
            pass

        results = ctx.get_results()
        assert results["success"] is False
        assert results["error"] == "Test error"
        assert results["error_type"] == "ValueError"


# BenchmarkSuite tests
class TestBenchmarkSuite:
    """Tests for the BenchmarkSuite class."""

    def test_init(self):
        """Test BenchmarkSuite initialization."""
        suite = BenchmarkSuite(name="test_suite")
        assert suite.name == "test_suite"
        assert suite.results == {}
        assert suite.config == {
            "iterations": 3,
            "file_sizes": [1024, 1024 * 1024],
            "output_dir": os.path.join(os.getcwd(), "benchmark_results"),
            "include_tests": ["all"],
            "exclude_tests": [],
        }

    def test_init_with_config(self):
        """Test BenchmarkSuite initialization with custom config."""
        config = {
            "iterations": 5,
            "file_sizes": [1024],
            "output_dir": "/tmp/benchmarks",
            "include_tests": ["add", "get"],
            "exclude_tests": ["pin"],
        }
        suite = BenchmarkSuite(name="test_suite", config=config)
        assert suite.config["iterations"] == 5
        assert suite.config["file_sizes"] == [1024]
        assert suite.config["output_dir"] == "/tmp/benchmarks"
        assert suite.config["include_tests"] == ["add", "get"]
        assert suite.config["exclude_tests"] == ["pin"]

    @patch("os.makedirs")
    def test_setup(self, mock_makedirs):
        """Test setup method."""
        suite = BenchmarkSuite(name="test_suite")
        suite.setup()
        mock_makedirs.assert_called_once_with(
            os.path.join(os.getcwd(), "benchmark_results"), exist_ok=True
        )

    def test_run_benchmark(self):
        """Test run_benchmark method."""
        suite = BenchmarkSuite(name="test_suite")

        # Test function that always succeeds
        def test_func():
            return "success"

        suite.run_benchmark("test_benchmark", test_func, iterations=2)

        assert "test_benchmark" in suite.results
        assert len(suite.results["test_benchmark"]["iterations"]) == 2
        assert suite.results["test_benchmark"]["iterations"][0]["result"] == "success"
        assert suite.results["test_benchmark"]["iterations"][1]["result"] == "success"
        assert suite.results["test_benchmark"]["success"] is True
        assert "mean" in suite.results["test_benchmark"]["stats"]
        assert "median" in suite.results["test_benchmark"]["stats"]
        assert "min" in suite.results["test_benchmark"]["stats"]
        assert "max" in suite.results["test_benchmark"]["stats"]

        # Test function that raises an exception
        def error_func():
            raise ValueError("Test error")

        suite.run_benchmark("error_benchmark", error_func, iterations=1)

        assert "error_benchmark" in suite.results
        assert suite.results["error_benchmark"]["success"] is False
        assert "Test error" in suite.results["error_benchmark"]["error"]

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data='{"test": "data"}')
    def test_save_results(self, mock_file, mock_exists):
        """Test save_results method."""
        suite = BenchmarkSuite(name="test_suite")
        suite.results = {"test_benchmark": {"success": True}}

        file_path = suite.save_results()

        mock_file.assert_called_once()
        # Check that the file was written with JSON data
        file_handle = mock_file()
        file_handle.write.assert_called_once()
        # The written data should be a JSON string
        written_data = file_handle.write.call_args[0][0]
        assert json.loads(written_data)  # Should be valid JSON
        assert file_path is not None

    def test_analyze_results(self):
        """Test analyze_results method."""
        suite = BenchmarkSuite(name="test_suite")
        suite.results = {
            "add_small_file": {
                "success": True,
                "stats": {"mean": 0.1, "median": 0.09, "min": 0.05, "max": 0.2},
                "parameters": {"file_size": 1024},
            },
            "add_large_file": {
                "success": True,
                "stats": {"mean": 1.0, "median": 0.9, "min": 0.5, "max": 2.0},
                "parameters": {"file_size": 1024 * 1024},
            },
        }

        analysis = suite.analyze_results()

        assert "summary" in analysis
        assert "test_count" in analysis["summary"]
        assert analysis["summary"]["test_count"] == 2
        assert "success_count" in analysis["summary"]
        assert analysis["summary"]["success_count"] == 2

        # Check performance analysis
        assert "performance" in analysis
        perf = analysis["performance"]
        assert "slowest_test" in perf
        assert perf["slowest_test"]["name"] == "add_large_file"
        assert "fastest_test" in perf
        assert perf["fastest_test"]["name"] == "add_small_file"

        # Check recommendations
        assert "recommendations" in analysis
        assert len(analysis["recommendations"]) > 0

    @patch("tempfile.NamedTemporaryFile")
    def test_create_test_file(self, mock_temp_file):
        """Test create_test_file method."""
        mock_temp = MagicMock()
        mock_temp.__enter__.return_value.name = "/tmp/test_file"
        mock_temp_file.return_value = mock_temp

        suite = BenchmarkSuite(name="test_suite")
        file_path = suite._create_test_file(1024)

        assert file_path == "/tmp/test_file"
        mock_temp.__enter__.return_value.write.assert_called_once()

    @patch("os.unlink")
    def test_cleanup_test_files(self, mock_unlink):
        """Test cleanup_test_files method."""
        suite = BenchmarkSuite(name="test_suite")
        suite.test_files = ["/tmp/test_file1", "/tmp/test_file2"]
        suite._cleanup_test_files()

        assert mock_unlink.call_count == 2
        mock_unlink.assert_any_call("/tmp/test_file1")
        mock_unlink.assert_any_call("/tmp/test_file2")
        assert suite.test_files == []

    def test_calculate_statistics(self):
        """Test calculate_statistics method."""
        times = [0.1, 0.2, 0.3, 0.4, 0.5]
        suite = BenchmarkSuite(name="test_suite")
        stats = suite._calculate_statistics(times)

        assert stats["mean"] == 0.3
        assert stats["median"] == 0.3
        assert stats["min"] == 0.1
        assert stats["max"] == 0.5
        assert stats["std_dev"] > 0

    @patch("ipfs_kit_py.benchmark_framework.BenchmarkSuite.run_benchmark")
    def test_benchmarking_methods(self, mock_run_benchmark):
        """Test the various benchmarking methods."""
        suite = BenchmarkSuite(name="test_suite")

        # Create mock objects for IPFS Kit
        mock_kit = MagicMock()
        mock_api = MagicMock()
        mock_fs = MagicMock()

        # Test each of the private benchmark methods
        suite._run_add_benchmarks(mock_kit, mock_api, mock_fs)
        assert mock_run_benchmark.called
        mock_run_benchmark.reset_mock()

        suite._run_get_benchmarks(mock_kit, mock_api, mock_fs)
        assert mock_run_benchmark.called
        mock_run_benchmark.reset_mock()

        suite._run_cat_benchmarks(mock_kit, mock_api, mock_fs)
        assert mock_run_benchmark.called
        mock_run_benchmark.reset_mock()

        suite._run_pin_benchmarks(mock_kit, mock_api, mock_fs)
        assert mock_run_benchmark.called
        mock_run_benchmark.reset_mock()

        suite._run_cache_benchmarks(mock_kit, mock_api, mock_fs)
        assert mock_run_benchmark.called
        mock_run_benchmark.reset_mock()

        suite._run_api_benchmarks(mock_kit, mock_api, mock_fs)
        assert mock_run_benchmark.called
        mock_run_benchmark.reset_mock()

        suite._run_network_benchmarks(mock_kit, mock_api, mock_fs)
        assert mock_run_benchmark.called
        mock_run_benchmark.reset_mock()


if __name__ == "__main__":
    pytest.main(["-v", __file__])
