"""
A simple test for the benchmark_framework.py without using conftest.py fixtures.
"""

import json
import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, mock_open, patch

from ipfs_kit_py.benchmark_framework import BenchmarkContext, BenchmarkSuite


class TestBenchmarkFramework(unittest.TestCase):
    """Tests for the benchmark_framework.py module."""

    def test_benchmark_context(self):
        """Test BenchmarkContext."""
        # Test initialization
        ctx = BenchmarkContext("test_benchmark")
        self.assertEqual(ctx.operation_name, "test_benchmark")
        self.assertIsNone(ctx.start_time)
        self.assertIsNone(ctx.end_time)

        # Test context manager functionality
        with BenchmarkContext("test_benchmark") as ctx:
            self.assertIsNotNone(ctx.start_time)
            self.assertIsNone(ctx.end_time)
            time.sleep(0.01)  # Small delay

        self.assertIsNotNone(ctx.end_time)
        self.assertTrue(ctx.end_time - ctx.start_time > 0)

    @patch("os.makedirs")
    def test_benchmark_suite(self, mock_makedirs):
        """Test BenchmarkSuite basics."""
        # Test initialization with default parameters
        suite = BenchmarkSuite()
        self.assertIsNotNone(suite)

        # Normally we would test more methods of BenchmarkSuite,
        # but this is just a simple test to verify it can be imported and instantiated


if __name__ == "__main__":
    unittest.main()
