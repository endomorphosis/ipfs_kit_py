"""
Unit tests for the Tiered Cache implementation.

This module tests the functionality of ARCache, DiskCache, and TieredCacheManager classes
to ensure proper caching behavior and tier management.
"""

import os
import shutil
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import MagicMock, patch

sys.path.insert(0, "/home/barberb/ipfs_kit_py")

# Import from new module locations directly for testing
from ipfs_kit_py.arc_cache import ARCache
from ipfs_kit_py.disk_cache import DiskCache
from ipfs_kit_py.tiered_cache_manager import TieredCacheManager


class TestARCache(unittest.TestCase):
    """Test the Adaptive Replacement Cache implementation."""

    def setUp(self):
        """Set up a test cache with a small size limit."""
        self.cache = ARCache(maxsize=1000)  # 1000 bytes for testing

    def test_init(self):
        """Test that the cache initializes correctly."""
        self.assertEqual(self.cache.maxsize, 1000)
        self.assertEqual(self.cache.current_size, 0)
        self.assertEqual(len(self.cache.T1), 0)
        self.assertEqual(len(self.cache.T2), 0)
        self.assertEqual(len(self.cache.B1), 0)
        self.assertEqual(len(self.cache.B2), 0)

    def test_put_and_get(self):
        """Test putting and getting items from the cache."""
        # Put an item
        self.cache.put("key1", b"value1")

        # Check it was stored
        self.assertEqual(len(self.cache), 1)
        self.assertTrue("key1" in self.cache)

        # Get the item
        value = self.cache.get("key1")
        self.assertEqual(value, b"value1")

        # Check that getting moves from T1 to T2
        self.assertNotIn("key1", self.cache.T1)
        self.assertIn("key1", self.cache.T2)

    def test_eviction(self):
        """Test that items are evicted when cache is full."""
        # Fill the cache beyond capacity
        for i in range(20):  # Use more items to ensure eviction
            key = f"key{i}"
            # Each item is ~100 bytes
            value = bytes([i] * 100)
            self.cache.put(key, value)

        # Cache should have evicted items to stay under maxsize
        self.assertLess(
            self.cache.current_size, self.cache.maxsize + 100
        )  # Allow for slight overage during eviction

        # Some earlier items should be evicted
        self.assertLessEqual(len(self.cache), 10)  # Should be 10 or fewer items

    def test_heat_scoring(self):
        """Test that heat scoring works correctly."""
        # Add two items
        self.cache.put("cold", b"cold_value")
        self.cache.put("hot", b"hot_value")

        # Access "hot" multiple times to increase its heat score
        for _ in range(5):
            self.cache.get("hot")
            time.sleep(0.01)  # Small delay to differentiate access times

        # Fill the cache to trigger eviction
        for i in range(10):
            self.cache.put(f"filler{i}", bytes([i] * 100))

        # "hot" should still be in cache, "cold" should be evicted
        self.assertIn("hot", self.cache)
        self.assertNotIn("cold", self.cache)

    def test_clear(self):
        """Test clearing the cache."""
        # Add some items
        self.cache.put("key1", b"value1")
        self.cache.put("key2", b"value2")

        # Clear the cache
        self.cache.clear()

        # Cache should be empty
        self.assertEqual(len(self.cache), 0)
        self.assertEqual(self.cache.current_size, 0)

    def test_stats(self):
        """Test getting cache statistics."""
        # Add some items
        self.cache.put("key1", b"value1")
        self.cache.get("key1")  # Move to T2
        self.cache.put("key2", b"value2")

        # Get stats
        stats = self.cache.get_stats()

        # Check basic stats
        self.assertEqual(stats["maxsize"], 1000)
        self.assertGreater(stats["current_size"], 0)
        self.assertEqual(stats["item_count"], 2)
        self.assertEqual(stats["T1"]["count"], 1)
        self.assertEqual(stats["T2"]["count"], 1)


class TestDiskCache(unittest.TestCase):
    """Test the disk-based cache implementation."""

    def setUp(self):
        """Set up a test cache with a temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache = DiskCache(directory=self.temp_dir, size_limit=10000)

    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init(self):
        """Test that the cache initializes correctly."""
        self.assertEqual(self.cache.size_limit, 10000)
        self.assertEqual(self.cache.current_size, 0)
        self.assertEqual(len(self.cache.index), 0)

    def test_put_and_get(self):
        """Test putting and getting items from the cache."""
        # Put an item
        self.cache.put("key1", b"value1")

        # Check index was updated
        self.assertEqual(len(self.cache.index), 1)
        self.assertIn("key1", self.cache.index)

        # Get the item
        value = self.cache.get("key1")
        self.assertEqual(value, b"value1")

        # Check file exists
        filename = self.cache.index["key1"]["filename"]
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, filename)))

    def test_eviction(self):
        """Test that items are evicted when cache is full."""
        # Fill the cache beyond capacity
        for i in range(200):  # Use more items to ensure eviction
            key = f"key{i}"
            # Each item is ~100 bytes
            value = bytes([i] * 100)
            self.cache.put(key, value)

        # Cache should have evicted items to stay under size limit
        self.assertLess(
            self.cache.current_size, self.cache.size_limit + 100
        )  # Allow for slight overage during eviction

        # Some earlier items should be evicted
        self.assertLessEqual(len(self.cache.index), 100)

    def test_metadata(self):
        """Test storing and retrieving metadata with cached items."""
        metadata = {"mimetype": "text/plain", "source": "test", "created_at": time.time()}

        # Put item with metadata
        self.cache.put("key_with_metadata", b"value", metadata)

        # Check metadata was stored
        self.assertEqual(
            self.cache.index["key_with_metadata"]["metadata"]["mimetype"], "text/plain"
        )

        # Get the item (doesn't return metadata directly)
        value = self.cache.get("key_with_metadata")
        self.assertEqual(value, b"value")

    def test_clear(self):
        """Test clearing the cache."""
        # Add some items
        self.cache.put("key1", b"value1")
        self.cache.put("key2", b"value2")

        # Clear the cache
        self.cache.clear()

        # Cache should be empty
        self.assertEqual(len(self.cache.index), 0)
        self.assertEqual(self.cache.current_size, 0)

        # Files should be deleted
        file_count = len(os.listdir(self.temp_dir))
        # The cache_index.json file and metadata directory should remain
        self.assertLessEqual(file_count, 2)

    def test_stats(self):
        """Test getting cache statistics."""
        # Add some items with different metadata
        self.cache.put("key1", b"value1", {"mimetype": "text/plain"})
        self.cache.put("key2", b"value2", {"mimetype": "application/json"})

        # Get stats
        stats = self.cache.get_stats()

        # Check basic stats
        self.assertEqual(stats["size_limit"], 10000)
        self.assertGreater(stats["current_size"], 0)
        self.assertEqual(stats["entry_count"], 2)
        self.assertEqual(stats["by_type"]["text/plain"], 1)
        self.assertEqual(stats["by_type"]["application/json"], 1)


class TestTieredCacheManager(unittest.TestCase):
    """Test the tiered cache manager implementation."""

    def setUp(self):
        """Set up a test cache with a temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            "memory_cache_size": 1000,  # 1KB
            "local_cache_size": 10000,  # 10KB
            "local_cache_path": self.temp_dir,
            "max_item_size": 500,  # 500 bytes
            "min_access_count": 2,
            "enable_memory_mapping": True,
        }
        self.cache = TieredCacheManager(config=self.config)

    def tearDown(self):
        """Clean up the temporary directory and any memory-mapped files."""
        # Close any memory-mapped files
        if hasattr(self.cache, 'mmap_store'):
            for key, (file_obj, mmap_obj, temp_path) in list(self.cache.mmap_store.items()):
                try:
                    if mmap_obj and not mmap_obj.closed:
                        mmap_obj.close()
                    if file_obj and not file_obj.closed:
                        file_obj.close()
                    if temp_path and os.path.exists(temp_path):
                        os.unlink(temp_path)
                except Exception as e:
                    print(f"Error cleaning up mmap for {key}: {e}")
                
            # Clear the store
            self.cache.mmap_store.clear()
            
        # Remove temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init(self):
        """Test that the cache manager initializes correctly."""
        self.assertEqual(self.cache.memory_cache.maxsize, 1000)
        self.assertEqual(self.cache.disk_cache.size_limit, 10000)
        self.assertEqual(self.cache.disk_cache.directory, self.temp_dir)

    def test_put_and_get_small_item(self):
        """Test putting and getting small items (should be in both tiers)."""
        # Put a small item (should go to both memory and disk)
        self.cache.put("small_key", b"small_value")

        # Check it's in memory cache
        self.assertIn("small_key", self.cache.memory_cache)

        # Check it's in disk cache
        self.assertIn("small_key", self.cache.disk_cache.index)

        # Get the item (should come from memory)
        value = self.cache.get("small_key")
        self.assertEqual(value, b"small_value")

        # Check hit counters
        self.assertEqual(self.cache.access_stats["small_key"]["tier_hits"]["memory"], 1)

    def test_put_and_get_large_item(self):
        """Test putting and getting large items (should only be in disk tier)."""
        # Create a large item (larger than max_item_size)
        large_value = bytes([0] * 600)  # 600 bytes

        # Put the large item (should only go to disk)
        self.cache.put("large_key", large_value)

        # Check it's not in memory cache (too big)
        self.assertNotIn("large_key", self.cache.memory_cache)

        # Check it's in disk cache
        self.assertIn("large_key", self.cache.disk_cache.index)

        # Get the item (should come from disk)
        value = self.cache.get("large_key")
        self.assertEqual(value, large_value)

        # Check hit counters
        self.assertEqual(self.cache.access_stats["large_key"]["tier_hits"]["disk"], 1)

    def test_promotion(self):
        """Test that items get promoted from disk to memory on access."""
        # Create a value small enough to fit in memory but we'll only put it on disk
        value = b"promotable_value"

        # Manually add to disk cache only
        self.cache.disk_cache.put("promote_key", value)

        # Verify it's not in memory yet
        self.assertNotIn("promote_key", self.cache.memory_cache)

        # Access it - should get promoted to memory
        retrieved_value = self.cache.get("promote_key")
        self.assertEqual(retrieved_value, value)

        # Now it should be in memory
        self.assertIn("promote_key", self.cache.memory_cache)

    def test_tiered_eviction(self):
        """Test eviction from memory tier while keeping in disk tier."""
        # Fill memory cache
        for i in range(20):
            key = f"mem_key{i}"
            # Each item is ~100 bytes
            value = bytes([i] * 100)
            self.cache.put(key, value)

        # Memory cache should be near capacity, some items evicted
        self.assertLess(
            self.cache.memory_cache.current_size, self.config["memory_cache_size"] + 100
        )

        # But disk cache should have all items
        self.assertEqual(len(self.cache.disk_cache.index), 20)

        # We should be able to retrieve all items (some from disk)
        for i in range(20):
            key = f"mem_key{i}"
            value = self.cache.get(key)
            self.assertEqual(value[0], i)

    def test_mmap_access(self):
        """Test memory-mapped access for large files."""
        # Create a large item
        large_value = bytes([42] * 1000)

        # Add it to cache
        self.cache.put("mmap_key", large_value)

        # Get via mmap
        mmap_obj = self.cache.get_mmap("mmap_key")

        # Check it's a valid mmap object
        self.assertIsNotNone(mmap_obj)

        # Read the first 10 bytes from the mmap
        mmap_obj.seek(0)
        mmap_data = mmap_obj.read(10)
        self.assertEqual(mmap_data, bytes([42] * 10))

        # Check that it's tracked in mmap_store
        self.assertIn("mmap_key", self.cache.mmap_store)

    def test_metadata_and_stats(self):
        """Test metadata handling and statistics collection."""
        # Add items with metadata
        self.cache.put("key1", b"value1", {"mimetype": "text/plain"})
        self.cache.put("key2", b"value2", {"mimetype": "application/json"})

        # Access items to generate stats
        self.cache.get("key1")
        self.cache.get("key1")  # Access twice to increase heat
        self.cache.get("key2")

        # Get stats
        stats = self.cache.get_stats()

        # Check stats include both tiers
        self.assertTrue("memory_cache" in stats)
        self.assertTrue("disk_cache" in stats)

        # Verify hit counts (actual counts may vary by implementation)
        self.assertIn("memory", stats["hits"])
        self.assertIn("disk", stats["hits"])
        self.assertGreater(sum(stats["hits"].values()), 0)

        # Verify hit rate is reasonable
        self.assertGreaterEqual(stats["hit_rate"], 0.0)
        self.assertLessEqual(stats["hit_rate"], 1.0)

    def test_clear_specific_tiers(self):
        """Test clearing specific cache tiers."""
        # Add some items
        self.cache.put("key1", b"value1")
        self.cache.put("key2", b"value2")

        # First verify items are in both tiers
        self.assertIn("key1", self.cache.memory_cache)
        self.assertIn("key1", self.cache.disk_cache.index)

        # Clear only memory tier
        self.cache.clear(tiers=["memory"])

        # Memory should be empty, disk should still have items
        self.assertEqual(len(self.cache.memory_cache), 0)
        self.assertGreater(len(self.cache.disk_cache.index), 0)

        # Items should still be retrievable (from disk)
        value = self.cache.get("key1")
        self.assertEqual(value, b"value1")

        # The retrieval would have promoted the item back to memory,
        # so clear memory again
        self.cache.clear(tiers=["memory"])

        # Clear disk tier
        self.cache.clear(tiers=["disk"])

        # Disk should be empty
        self.assertEqual(len(self.cache.disk_cache.index), 0)

        # Verify both tiers are clear of our test keys
        self.assertNotIn("key1", self.cache.memory_cache)
        self.assertNotIn("key1", self.cache.disk_cache.index)


if __name__ == "__main__":
    unittest.main()
