"""
Temporary test runner for content-aware prefetch tests.

This script directly imports the required modules without going through
the package's __init__.py file, allowing us to test our new functionality
without fixing all indentation issues in the codebase.
"""

import os
import sys
import unittest
import tempfile
import time
import json
import shutil
from unittest.mock import MagicMock, patch

# Add the parent directory to sys.path so we can import directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the classes directly from the module file
from ipfs_kit_py.content_aware_prefetch import ContentTypeAnalyzer, ContentAwarePrefetchManager

# Create mock TieredCacheManager for testing
class MockTieredCacheManager:
    """Mock implementation of TieredCacheManager for testing."""

    def __init__(self, config=None):
        self.config = config or {}
        self.memory_cache = MockMemoryCache()
        self.disk_cache = MockDiskCache()
        self.parquet_cache = None
        self.access_stats = {}

    def prefetch(self, key):
        """Mock prefetch method."""
        return {
            "success": True,
            "operation": "prefetch",
            "cid": key,
            "tier": "disk",
            "size": 1000,
            "promoted_to_memory": True
        }

    def get(self, key):
        """Mock get method."""
        return b"Test content"

    def contains(self, key):
        """Mock contains method."""
        return key in self.memory_cache

    def _update_stats(self, key, access_type, metadata=None):
        """Mock update stats method."""
        if key not in self.access_stats:
            self.access_stats[key] = {
                "access_count": 0,
                "last_access": time.time(),
                "access_times": []
            }

        stats = self.access_stats[key]
        stats["access_count"] += 1
        stats["last_access"] = time.time()
        stats["access_times"].append(time.time())

        if access_type == "prefetch" and metadata:
            stats["prefetched"] = True
            stats["prefetch_metadata"] = metadata

class MockMemoryCache:
    """Mock memory cache for testing."""

    def __init__(self):
        self.data = {}

    def get(self, key):
        """Get item from cache."""
        return self.data.get(key)

    def put(self, key, value):
        """Put item in cache."""
        self.data[key] = value
        return True

    def contains(self, key):
        """Check if key is in cache."""
        return key in self.data

    def __contains__(self, key):
        """Magic method for 'in' operator."""
        return self.contains(key)

class MockDiskCache:
    """Mock disk cache for testing."""

    def __init__(self):
        self.data = {}

    def get(self, key):
        """Get item from cache."""
        return self.data.get(key)

    def put(self, key, value):
        """Put item in cache."""
        self.data[key] = value
        return True


# Test classes copied from test_content_aware_prefetch.py
class TestContentTypeAnalyzer(unittest.TestCase):
    """Test the ContentTypeAnalyzer class."""

    def setUp(self):
        """Set up a test analyzer."""
        self.analyzer = ContentTypeAnalyzer(enable_magic_detection=False)

    def test_detect_content_type_by_extension(self):
        """Test content type detection based on file extensions."""
        # Test various file extensions
        test_cases = [
            # Video files
            ({"filename": "test.mp4"}, "video"),
            ({"filename": "test.avi"}, "video"),
            ({"filename": "test.mkv"}, "video"),

            # Audio files
            ({"filename": "test.mp3"}, "audio"),
            ({"filename": "test.wav"}, "audio"),
            ({"filename": "test.flac"}, "audio"),

            # Image files
            ({"filename": "test.jpg"}, "image"),
            ({"filename": "test.png"}, "image"),
            ({"filename": "test.gif"}, "image"),

            # Documents
            ({"filename": "test.pdf"}, "document"),
            ({"filename": "test.docx"}, "document"),
            ({"filename": "test.txt"}, "document"),

            # Datasets
            ({"filename": "test.csv"}, "dataset"),
            ({"filename": "test.parquet"}, "dataset"),
            ({"filename": "test.json"}, "dataset"),

            # Code
            ({"filename": "test.py"}, "code"),
            ({"filename": "test.js"}, "code"),
            ({"filename": "test.cpp"}, "code"),

            # Models
            ({"filename": "test.pth"}, "model"),
            ({"filename": "test.h5"}, "model"),
            ({"filename": "test.onnx"}, "model"),

            # Archives
            ({"filename": "test.zip"}, "archive"),
            ({"filename": "test.tar.gz"}, "archive"),

            # Web
            ({"filename": "test.html"}, "web"),
            ({"filename": "test.css"}, "web"),

            # Unknown extension
            ({"filename": "test.unknown"}, "generic")
        ]

        for metadata, expected_type in test_cases:
            detected_type = self.analyzer.detect_content_type(metadata)
            self.assertEqual(detected_type, expected_type,
                           f"Failed to detect {expected_type} for {metadata}")

    def test_detect_content_type_by_mimetype(self):
        """Test content type detection based on mimetype."""
        test_cases = [
            # Video mimetype
            ({"mimetype": "video/mp4"}, "video"),
            ({"mimetype": "video/x-msvideo"}, "video"),

            # Audio mimetype
            ({"mimetype": "audio/mpeg"}, "audio"),
            ({"mimetype": "audio/wav"}, "audio"),

            # Image mimetype
            ({"mimetype": "image/jpeg"}, "image"),
            ({"mimetype": "image/png"}, "image"),

            # Document mimetype
            ({"mimetype": "application/pdf"}, "document"),
            ({"mimetype": "text/plain"}, "document"),

            # Dataset mimetype
            ({"mimetype": "text/csv"}, "dataset"),
            ({"mimetype": "application/json"}, "dataset"),

            # Unknown mimetype
            ({"mimetype": "application/x-unknown"}, "generic")
        ]

        for metadata, expected_type in test_cases:
            detected_type = self.analyzer.detect_content_type(metadata)
            self.assertEqual(detected_type, expected_type,
                           f"Failed to detect {expected_type} for {metadata}")

    def test_detect_content_type_by_content(self):
        """Test content type detection based on content samples."""
        # Create test content samples
        test_cases = [
            # JSON dataset
            ({"filename": "unknown.bin"}, b'{"name": "test", "value": 123}', "dataset"),

            # HTML content
            ({"filename": "unknown.bin"}, b'<!DOCTYPE html><html><body><h1>Test</h1></body></html>', "web"),

            # CSV content
            ({"filename": "unknown.bin"}, b'name,age,city\nJohn,30,New York\nJane,25,Boston', "dataset"),

            # Parquet header
            ({"filename": "unknown.bin"}, b'PAR1' + b'x' * 100, "dataset"),

            # Unknown binary data
            ({"filename": "unknown.bin"}, b'\x00\x01\x02\x03\x04', "generic")
        ]

        for metadata, content, expected_type in test_cases:
            detected_type = self.analyzer.detect_content_type(metadata, content)
            self.assertEqual(detected_type, expected_type,
                           f"Failed to detect {expected_type} for content sample")


class TestContentAwarePrefetchManager(unittest.TestCase):
    """Test the ContentAwarePrefetchManager class."""

    def setUp(self):
        """Set up a test prefetch manager with a mock cache manager."""
        self.mock_cache = MagicMock()
        self.mock_cache.get = MagicMock(return_value=b"test content")
        self.mock_cache.prefetch = MagicMock(return_value={"success": True, "size": 1000})
        self.mock_cache.contains = MagicMock(return_value=False)

        self.prefetch_manager = ContentAwarePrefetchManager(
            tiered_cache_manager=self.mock_cache,
            config={
                "enabled": True,
                "max_prefetch_items": 5,
                "max_concurrent_prefetch": 2,
                "enable_magic_detection": False,
                "enable_logging": False
            }
        )

    def tearDown(self):
        """Clean up resources."""
        self.prefetch_manager.stop()

    def test_record_content_access(self):
        """Test recording content access and detecting content type."""
        # Test with video file
        metadata = {
            "filename": "test.mp4",
            "size": 1_000_000,
            "cached": False
        }

        result = self.prefetch_manager.record_content_access("video1", metadata)

        # Check result contains expected information
        self.assertEqual(result["content_type"], "video")
        self.assertTrue(result["prefetch_scheduled"])
        self.assertIn("prefetch_strategy", result)

        # Check content type was stored
        self.assertEqual(self.prefetch_manager.content_types["video1"], "video")

    def test_prefetch_operation(self):
        """Test actual prefetch operation."""
        # Perform a prefetch operation
        result = self.prefetch_manager._prefetch_item(
            "prefetch_test", "video", {"prefetch_strategy": "sliding_window"}
        )

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["content_type"], "video")
        self.assertEqual(result["cid"], "prefetch_test")
        self.assertIn("elapsed", result)

        # Verify call to cache manager
        self.mock_cache.prefetch.assert_called_with("prefetch_test")

    def test_integration_with_mock_tiered_cache(self):
        """Test integration with a mock TieredCacheManager."""
        # Create a mock TieredCacheManager
        cache_manager = MockTieredCacheManager()

        # Add test content to disk cache
        test_cid = "test_integration_cid"
        test_content = b"Test content for integration" * 100
        cache_manager.disk_cache.put(test_cid, test_content)

        # Create prefetch manager with mock cache
        prefetch_manager = ContentAwarePrefetchManager(
            tiered_cache_manager=cache_manager,
            config={
                "enabled": True,
                "max_prefetch_items": 5,
                "max_concurrent_prefetch": 2,
                "enable_magic_detection": False,
                "enable_logging": False
            }
        )

        # Test content access and prefetching
        metadata = {
            "filename": "video.mp4",
            "size": len(test_content)
        }

        # Record content access to analyze content type
        result = prefetch_manager.record_content_access(test_cid, metadata)
        self.assertEqual(result["content_type"], "video")

        # Test prefetch operation
        prefetch_result = prefetch_manager._prefetch_item(
            test_cid, "video", {"prefetch_strategy": "sliding_window"}
        )

        # Verify operation success
        self.assertTrue(prefetch_result["success"])
        self.assertEqual(prefetch_result["cid"], test_cid)

        # Clean up
        prefetch_manager.stop()


if __name__ == "__main__":
    unittest.main()
