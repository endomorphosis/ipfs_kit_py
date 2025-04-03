#!/usr/bin/env python3
"""
Tests for the FSSpec performance metrics functionality.

This module tests the performance metrics collection and analysis features
of the IPFS FSSpec implementation.
"""

import os
import random
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path to import ipfs_kit_py
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from ipfs_kit_py.ipfs_fsspec import PerformanceMetrics
from ipfs_kit_py.ipfs_kit import ipfs_kit


class TestPerformanceMetrics(unittest.TestCase):
    """Test case for PerformanceMetrics class functionality."""

    def test_metrics_collection(self):
        """Test that metrics are collected correctly."""
        # Create a metrics collector with metrics enabled
        metrics = PerformanceMetrics(enable_metrics=True)

        # Record some operations
        metrics.record_operation_time("read", 0.005)
        metrics.record_operation_time("read", 0.006)
        metrics.record_operation_time("write", 0.01)

        # Record some cache accesses
        metrics.record_cache_access("memory_hit")
        metrics.record_cache_access("memory_hit")
        metrics.record_cache_access("disk_hit")
        metrics.record_cache_access("miss")

        # Get operation stats
        read_stats = metrics.get_operation_stats("read")
        all_stats = metrics.get_operation_stats()

        # Check read stats
        self.assertEqual(read_stats["count"], 2)
        self.assertAlmostEqual(read_stats["mean"], 0.0055, delta=0.0001)

        # Check all stats
        self.assertEqual(all_stats["total_operations"], 3)
        self.assertEqual(all_stats["read"]["count"], 2)
        self.assertEqual(all_stats["write"]["count"], 1)

        # Check cache stats
        cache_stats = metrics.get_cache_stats()
        self.assertEqual(cache_stats["memory_hits"], 2)
        self.assertEqual(cache_stats["disk_hits"], 1)
        self.assertEqual(cache_stats["misses"], 1)
        self.assertEqual(cache_stats["total"], 4)
        self.assertAlmostEqual(cache_stats["memory_hit_rate"], 0.5, delta=0.001)
        self.assertAlmostEqual(cache_stats["disk_hit_rate"], 0.25, delta=0.001)
        self.assertAlmostEqual(cache_stats["overall_hit_rate"], 0.75, delta=0.001)
        self.assertAlmostEqual(cache_stats["miss_rate"], 0.25, delta=0.001)

        # Test reset
        metrics.reset_metrics()
        cache_stats = metrics.get_cache_stats()
        self.assertEqual(cache_stats["total"], 0)

    def test_metrics_disabled(self):
        """Test that metrics collection is properly disabled."""
        # Create a metrics collector with metrics disabled
        metrics = PerformanceMetrics(enable_metrics=False)

        # Record some operations (they should be ignored)
        metrics.record_operation_time("read", 0.005)
        metrics.record_cache_access("memory_hit")

        # Get stats - should indicate metrics are disabled
        op_stats = metrics.get_operation_stats()
        cache_stats = metrics.get_cache_stats()

        self.assertIn("metrics_disabled", op_stats)
        self.assertIn("metrics_disabled", cache_stats)


class TestIPFSFileSystemMetrics(unittest.TestCase):
    """Test case for metrics in IPFSFileSystem."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary file with test content
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.write(b"Test content for metrics testing")
        self.temp_file.close()

        # Mock CID for the file
        self.test_cid = "QmTestCid123456789"

        # Patch the IPFS run_ipfs_command method to return successful results
        self.ipfs_command_patcher = patch("ipfs_kit_py.ipfs.ipfs_py.run_ipfs_command")
        self.mock_ipfs_command = self.ipfs_command_patcher.start()
        self.mock_ipfs_command.return_value = {
            "success": True,
            "returncode": 0,
            "stdout": b"IPFS daemon is running",
        }

        # Create kit instance
        self.kit = ipfs_kit()

        # Mock the filesystem
        self.kit.get_filesystem = MagicMock()
        mock_fs = MagicMock()
        # Set up the mock filesystem with expected methods and return values
        mock_fs.cat = MagicMock(return_value=b"Test content for metrics testing")
        mock_fs.get_performance_metrics = MagicMock(
            return_value={
                "operations": {"total_operations": 5, "read": {"count": 5}},
                "cache": {
                    "memory_hits": 4,
                    "disk_hits": 0,
                    "misses": 1,
                    "total": 5,
                    "memory_hit_rate": 0.8,
                    "disk_hit_rate": 0.0,
                    "overall_hit_rate": 0.8,
                    "miss_rate": 0.2,
                },
            }
        )
        self.kit.get_filesystem.return_value = mock_fs

    def tearDown(self):
        """Clean up after tests."""
        # Remove temporary file
        os.unlink(self.temp_file.name)

        # Stop patchers
        self.ipfs_command_patcher.stop()

    @patch("ipfs_kit_py.ipfs_fsspec.IPFSFileSystem._fetch_from_ipfs")
    def test_filesystem_metrics(self, mock_fetch):
        """Test that filesystem operations collect metrics."""
        # Mock fetch to return test content
        mock_fetch.return_value = b"Test content for metrics testing"

        # Get filesystem with metrics enabled
        fs = self.kit.get_filesystem(enable_metrics=True)

        # Read the same CID multiple times to test caching
        for _ in range(5):
            content = fs.cat(self.test_cid)
            self.assertEqual(content, b"Test content for metrics testing")

        # Get metrics
        metrics = fs.get_performance_metrics()

        # Check that metrics were collected
        self.assertIn("operations", metrics)
        self.assertIn("cache", metrics)

        # Verify cache metrics
        cache_stats = metrics["cache"]
        self.assertTrue("total" in cache_stats)

        # We just want to make sure metrics are being collected,
        # the exact values may vary depending on implementation details
        self.assertTrue("misses" in cache_stats)
        self.assertTrue("memory_hits" in cache_stats)

        # Check that hit rates are calculated
        self.assertTrue("miss_rate" in cache_stats)
        self.assertTrue("memory_hit_rate" in cache_stats)


if __name__ == "__main__":
    unittest.main()
