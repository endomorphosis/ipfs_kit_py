"""
Unit tests for the Read-Ahead Prefetching functionality in tiered_cache.py.

This module tests the advanced prefetching capabilities of the TieredCacheManager
and PredictiveCacheManager classes, including pattern detection, streaming prefetch,
and intelligent content prediction.
"""

import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch, call
import threading
import queue
import concurrent.futures

sys.path.insert(0, "/home/barberb/ipfs_kit_py")

from ipfs_kit_py.tiered_cache import TieredCacheManager, PredictiveCacheManager

try:
    import asyncio
    HAS_ASYNCIO = True
except ImportError:
    HAS_ASYNCIO = False


class TestReadAheadPrefetching(unittest.TestCase):
    """Test the read-ahead prefetching functionality in TieredCacheManager."""

    def setUp(self):
        """Set up a test cache with a temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            "memory_cache_size": 10000,  # 10KB
            "local_cache_size": 100000,  # 100KB
            "local_cache_path": self.temp_dir,
            "max_item_size": 5000,  # 5KB
            "min_access_count": 2,
            "enable_memory_mapping": True,
            "prefetch_enabled": True,
            "max_prefetch_threads": 2,
            "predictive_prefetch": True, 
            "async_prefetch_enabled": True,
        }
        
        # Create cache with prefetching enabled
        self.cache = TieredCacheManager(config=self.config)
        
        # Mock the _identify_prefetch_candidates method to control predictions
        self.original_identify_candidates = self.cache._identify_prefetch_candidates
        self.cache._identify_prefetch_candidates = MagicMock(return_value=["prefetch1", "prefetch2"])
        
        # Mock the _trigger_prefetch method to track calls
        self.original_trigger_prefetch = self.cache._trigger_prefetch
        self.cache._trigger_prefetch = MagicMock()

    def tearDown(self):
        """Clean up the temporary directory and restore original methods."""
        # Restore original methods
        if hasattr(self, 'cache') and hasattr(self, 'original_identify_candidates'):
            self.cache._identify_prefetch_candidates = self.original_identify_candidates
        
        if hasattr(self, 'cache') and hasattr(self, 'original_trigger_prefetch'):
            self.cache._trigger_prefetch = self.original_trigger_prefetch
        
        # Clean up prefetch threads if any
        if hasattr(self, 'cache'):
            self.cache._clean_prefetch_threads()
        
        # Remove temp directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_prefetch_enabled_in_get(self):
        """Test that prefetching is triggered when enabled and an item is accessed."""
        # Add test content
        self.cache.put("test_key", b"test_value")
        
        # Get the content with prefetching enabled
        self.cache.get("test_key", prefetch=True)
        
        # Verify that trigger_prefetch was called with the expected key
        self.cache._trigger_prefetch.assert_called_once_with("test_key", "memory")

    def test_prefetch_disabled_in_get(self):
        """Test that prefetching is not triggered when disabled."""
        # Add test content
        self.cache.put("test_key", b"test_value")
        
        # Get the content with prefetching disabled
        self.cache.get("test_key", prefetch=False)
        
        # Verify that trigger_prefetch was not called
        self.cache._trigger_prefetch.assert_not_called()

    def test_trigger_prefetch(self):
        """Test that the _trigger_prefetch method properly initiates prefetching."""
        # Restore the original method for this test
        self.cache._trigger_prefetch = self.original_trigger_prefetch
        
        # Create a threading event to track when prefetch is complete
        prefetch_completed = threading.Event()
        
        # Mock the _execute_prefetch method to set the event when called
        original_execute_prefetch = self.cache._execute_prefetch
        
        def mock_execute_prefetch(key, source_tier):
            prefetch_completed.set()
            return original_execute_prefetch(key, source_tier)
        
        self.cache._execute_prefetch = mock_execute_prefetch
        
        # Add test content
        self.cache.put("trigger_test", b"test_value")
        
        # Trigger prefetch
        self.cache._trigger_prefetch("trigger_test", "memory")
        
        # Wait for prefetch to complete (max 5 seconds)
        prefetch_completed.wait(5)
        
        # Check that prefetch thread was created and tracked
        self.assertTrue(len(self.cache.prefetch_threads) > 0)
        
        # Restore original method
        self.cache._execute_prefetch = original_execute_prefetch

    @patch('threading.Thread')
    def test_prefetch_thread_management(self, mock_thread):
        """Test proper creation and cleaning of prefetch threads."""
        # Restore the original method
        self.cache._trigger_prefetch = self.original_trigger_prefetch
        
        # Set up mock thread
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance
        
        # Trigger prefetch
        self.cache._trigger_prefetch("thread_test", "memory")
        
        # Verify thread was created with correct arguments
        mock_thread.assert_called_with(
            target=self.cache._execute_prefetch,
            args=("thread_test", "memory"),
            daemon=True
        )
        
        # Verify thread was started
        mock_thread_instance.start.assert_called_once()
        
        # Verify thread was added to the prefetch_threads list
        self.assertIn(mock_thread_instance, self.cache.prefetch_threads)
        
        # Test cleaning of threads
        # Set is_alive to return False to simulate completed thread
        mock_thread_instance.is_alive.return_value = False
        
        # Clean threads
        self.cache._clean_prefetch_threads()
        
        # Prefetch_threads should be empty after cleaning
        self.assertEqual(len(self.cache.prefetch_threads), 0)

    def test_execute_prefetch(self):
        """Test that _execute_prefetch properly prefetches predicted content."""
        # Restore original methods
        self.cache._trigger_prefetch = self.original_trigger_prefetch
        self.cache._identify_prefetch_candidates = self.original_identify_candidates
        
        # Mock the get method to track calls without side effects
        original_get = self.cache.get
        self.cache.get = MagicMock()
        
        # Create a simple implementation of _identify_prefetch_candidates
        def mock_identify_candidates(key, max_items=3):
            # Simple pattern - for item "key1", predict ["key2", "key3"]
            if key == "key1":
                return ["key2", "key3"]
            return []
            
        self.cache._identify_prefetch_candidates = mock_identify_candidates
        
        # Add test content
        self.cache.put("key1", b"value1")
        self.cache.put("key2", b"value2")
        self.cache.put("key3", b"value3")
        
        # Execute prefetch
        self.cache._execute_prefetch("key1", "memory")
        
        # Verify that get was called for the predicted keys
        expected_calls = [call("key2"), call("key3")]
        self.cache.get.assert_has_calls(expected_calls, any_order=True)
        
        # Restore original method
        self.cache.get = original_get

    def test_prefetch_candidates_sequential(self):
        """Test identification of prefetch candidates with sequential access patterns."""
        # Restore original method
        self.cache._identify_prefetch_candidates = self.original_identify_candidates
        
        # Add sequentially named content
        for i in range(10):
            self.cache.put(f"seq{i}", f"value{i}".encode())
        
        # Access in sequential order to establish pattern
        for i in range(5):  # Access first 5 items in sequence
            self.cache.get(f"seq{i}")
        
        # Now get prefetch candidates for seq4
        candidates = self.cache._identify_prefetch_candidates("seq4", max_items=3)
        
        # Should predict next sequential items
        self.assertIn("seq5", candidates)
        
        # Check that only up to max_items are returned
        self.assertLessEqual(len(candidates), 3)

    def test_record_prefetch_metrics(self):
        """Test that prefetch metrics are properly recorded."""
        # Execute prefetch with specific metrics
        metrics = {
            "predicted": ["key1", "key2"],
            "prefetched": ["key1"],
            "already_cached": ["key2"],
            "time_taken": 0.1,
        }
        
        # Record metrics
        self.cache._record_prefetch_metrics("test_key", metrics)
        
        # Verify metrics were recorded
        self.assertIn("test_key", self.cache.prefetch_metrics)
        self.assertEqual(self.cache.prefetch_metrics["test_key"]["prefetched"], ["key1"])
        
        # Verify global metrics were updated
        self.assertEqual(self.cache.prefetch_stats["prefetch_operations"], 1)
        self.assertEqual(self.cache.prefetch_stats["items_prefetched"], 1)


class TestPredictiveCacheManager(unittest.TestCase):
    """Test the PredictiveCacheManager class for advanced prefetching capabilities."""

    def setUp(self):
        """Set up a test predictive cache manager with a TieredCacheManager."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            "memory_cache_size": 10000,  # 10KB
            "local_cache_size": 100000,  # 100KB
            "local_cache_path": self.temp_dir,
            "max_item_size": 5000,  # 5KB
        }
        
        # Create cache
        self.tiered_cache = TieredCacheManager(config=self.config)
        
        # Create predictive manager with test configuration
        predictive_config = {
            "pattern_tracking_enabled": True,
            "relationship_tracking_enabled": True,
            "prefetching_enabled": True,
            "max_prefetch_items": 3,
            "thread_pool_size": 2,
        }
        self.predictive_cache = PredictiveCacheManager(self.tiered_cache, predictive_config)

    def tearDown(self):
        """Clean up resources."""
        # Shutdown the predictive cache
        if hasattr(self, 'predictive_cache'):
            self.predictive_cache.shutdown()
        
        # Remove temp directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_access(self):
        """Test recording access for pattern analysis."""
        # Record a sequence of accesses
        self.predictive_cache.record_access("cid1")
        self.predictive_cache.record_access("cid2")
        self.predictive_cache.record_access("cid3")
        
        # Verify access history is populated
        self.assertEqual(len(self.predictive_cache.access_history), 3)
        
        # Check transition probabilities were updated
        self.assertIn("cid1", self.predictive_cache.transition_probabilities)
        self.assertIn("cid2", self.predictive_cache.transition_probabilities)
        
        # Verify cid1 -> cid2 transition was recorded
        self.assertEqual(self.predictive_cache.transition_probabilities["cid1"]["cid2"], 1)

    def test_predict_next_access(self):
        """Test prediction of next content access based on patterns."""
        # Create access pattern: cid1 -> cid2 -> cid3 (repeated)
        for _ in range(3):  # Repeat to strengthen pattern
            self.predictive_cache.record_access("cid1")
            self.predictive_cache.record_access("cid2")
            self.predictive_cache.record_access("cid3")
        
        # Predict next access after cid2
        predictions = self.predictive_cache.predict_next_access("cid2")
        
        # Should predict cid3 with high probability
        self.assertTrue(any(pred[0] == "cid3" for pred in predictions))
        
        # First prediction should be cid3 with high probability
        self.assertEqual(predictions[0][0], "cid3")
        self.assertGreater(predictions[0][1], 0.9)  # High probability

    def test_record_related_content(self):
        """Test recording relationships between content items."""
        # Record relationships
        related_items = [("related1", 0.9), ("related2", 0.7), ("related3", 0.5)]
        self.predictive_cache.record_related_content("base_cid", related_items)
        
        # Verify relationships were recorded
        self.assertIn("base_cid", self.predictive_cache.relationship_graph)
        self.assertEqual(len(self.predictive_cache.relationship_graph["base_cid"]), 3)
        
        # Check specific relationship values
        self.assertEqual(self.predictive_cache.relationship_graph["base_cid"]["related1"], 0.9)
        
        # Check reverse relationships
        self.assertIn("related1", self.predictive_cache.relationship_graph)
        self.assertIn("base_cid", self.predictive_cache.relationship_graph["related1"])

    @patch('threading.Thread')
    def test_prefetch_content(self, mock_thread):
        """Test prefetching content based on predictions."""
        # Set up deterministic predictions
        self.predictive_cache.predict_next_access = MagicMock(
            return_value=[("pred1", 0.9), ("pred2", 0.8), ("pred3", 0.6)]
        )
        
        # Call prefetch_content
        self.predictive_cache._prefetch_content("test_cid")
        
        # Verify thread pool was used correctly
        self.predictive_cache.thread_pool.submit.assert_called_once()
        args, kwargs = self.predictive_cache.thread_pool.submit.call_args
        
        # First arg should be the _perform_prefetch method
        self.assertEqual(args[0], self.predictive_cache._perform_prefetch)
        
        # Second arg should be the list of predicted CIDs
        self.assertEqual(set(args[1]), {"pred1", "pred2", "pred3"})

    @unittest.skipIf(not HAS_ASYNCIO, "asyncio not available")
    def test_ensure_event_loop(self):
        """Test that _ensure_event_loop properly sets up an asyncio event loop."""
        # Call the method
        loop = self.predictive_cache._ensure_event_loop()
        
        # Verify we got a valid event loop
        self.assertIsNotNone(loop)
        self.assertIsInstance(loop, asyncio.AbstractEventLoop)

    @unittest.skipIf(not HAS_ASYNCIO, "asyncio not available")
    def test_async_stream_prefetch(self):
        """Test async streaming prefetch functionality."""
        # Create a custom event loop for testing
        test_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(test_loop)
        
        try:
            # Setup read-ahead configuration
            self.predictive_cache.setup_read_ahead_prefetching({
                "enabled": True,
                "streaming_threshold": 100,
                "streaming_buffer_size": 50,
                "max_parallel_prefetch": 2
            })
            
            # Run the async prefetch method
            future = test_loop.create_task(
                self.predictive_cache._async_perform_stream_prefetch("test_cid", 500, 100, 5)
            )
            test_loop.run_until_complete(future)
            
            # Verify metrics were updated
            self.assertGreater(self.predictive_cache.read_ahead_metrics["prefetch_bytes_total"], 0)
            
        finally:
            # Clean up
            test_loop.close()

    def test_workload_detection(self):
        """Test detection of different workload patterns."""
        # Simulate sequential access pattern
        for i in range(15):
            self.predictive_cache.record_access(f"seq{i}")
        
        # Update workload based on this pattern
        self.predictive_cache._update_workload_detection()
        
        # Should detect sequential scan workload
        self.assertEqual(self.predictive_cache.current_workload, "sequential_scan")
        
        # Now simulate clustered access (same items repeated)
        for _ in range(20):
            self.predictive_cache.record_access("cluster1")
            self.predictive_cache.record_access("cluster2")
            self.predictive_cache.record_access("cluster3")
        
        # Setup relationships for these items
        self.predictive_cache.record_related_content("cluster1", [("cluster2", 0.9), ("cluster3", 0.8)])
        
        # Update workload
        self.predictive_cache._update_workload_detection()
        
        # Should now detect clustering workload
        self.assertEqual(self.predictive_cache.current_workload, "clustering")


if __name__ == "__main__":
    unittest.main()