"""
Tests for the resource management module.

This module tests the functionality of the resource management system
that optimizes thread and memory usage in resource-constrained environments.
"""

import os
import time
import threading
import unittest
from unittest.mock import patch, MagicMock

from ipfs_kit_py.resource_management import (
    ResourceMonitor,
    AdaptiveThreadPool,
    ResourceAdapter
)

class TestResourceMonitor(unittest.TestCase):
    """Tests for the ResourceMonitor class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a ResourceMonitor with background monitoring disabled
        self.monitor = ResourceMonitor({
            "background_monitoring": False,
            "log_resource_usage": False
        })
    
    def test_initialization(self):
        """Test initialization with default configuration."""
        # Verify initialization creates expected data structures
        self.assertIsNotNone(self.monitor.resources.get("cpu"))
        self.assertIsNotNone(self.monitor.resources.get("memory"))
        self.assertIsNotNone(self.monitor.resources.get("disk"))
        self.assertIsNotNone(self.monitor.resources.get("network"))
        
        # Verify system status is initialized
        self.assertIsNotNone(self.monitor.system_status.get("overall"))
        
        # Verify thread pool info is initialized
        self.assertIsNotNone(self.monitor.thread_pool_info.get("recommended_size"))
        
        # Verify cache info is initialized
        self.assertIsNotNone(self.monitor.cache_info.get("recommended_size_bytes"))
    
    def test_check_resources(self):
        """Test the resource checking functionality."""
        # Get resource status
        status = self.monitor.check_resources()
        
        # Verify the status contains expected fields
        self.assertIn("overall", status)
        self.assertIn("bottleneck", status)
        self.assertIn("cpu", status)
        self.assertIn("memory", status)
        self.assertIn("disk", status)
        self.assertIn("network", status)
        self.assertIn("recommendations", status)
        
        # Verify CPU info
        self.assertIn("status", status["cpu"])
        self.assertIn("usage_percent", status["cpu"])
        self.assertIn("cores", status["cpu"])
        
        # Verify memory info
        self.assertIn("status", status["memory"])
        self.assertIn("used_percent", status["memory"])
        self.assertIn("available_bytes", status["memory"])
        
        # Verify recommendations
        self.assertIn("thread_pool_size", status["recommendations"])
        self.assertIn("memory_cache_bytes", status["recommendations"])
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    def test_resource_status_changes(self, mock_virtual_memory, mock_cpu_percent):
        """Test that resource status changes based on measurements."""
        # Create a mock memory object
        mock_memory = MagicMock()
        mock_memory.total = 8 * 1024 * 1024 * 1024  # 8GB
        mock_memory.available = 6 * 1024 * 1024 * 1024  # 6GB available (25% used)
        mock_memory.percent = 25.0
        mock_virtual_memory.return_value = mock_memory
        
        # Mock CPU at 30% (low usage)
        mock_cpu_percent.return_value = 30.0
        
        # Check resources
        self.monitor.check_resources()
        
        # Verify status is reported as low
        self.assertEqual(self.monitor.resources["cpu"]["status"], "low")
        self.assertEqual(self.monitor.resources["memory"]["status"], "low")
        
        # Now simulate high CPU usage
        mock_cpu_percent.return_value = 85.0
        
        # Check resources again
        self.monitor.check_resources()
        
        # Verify CPU status is now high
        self.assertEqual(self.monitor.resources["cpu"]["status"], "high")
        
        # Simulate critical memory usage
        mock_memory.percent = 95.0
        mock_memory.available = 0.4 * 1024 * 1024 * 1024  # Only 400MB available
        
        # Check resources again
        self.monitor.check_resources()
        
        # Verify memory status is now critical
        self.assertEqual(self.monitor.resources["memory"]["status"], "critical")
        
        # Verify system status reflects the most critical component
        self.assertEqual(self.monitor.system_status["overall"], "critical")
        self.assertEqual(self.monitor.system_status["bottleneck"], "memory")
    
    def test_thread_allocation(self):
        """Test thread allocation recommendations based on resource state."""
        # Test with different worker types
        worker_types = ["prefetch", "io", "compute", "network"]
        
        # Force system status for testing
        self.monitor.system_status["overall"] = "low"
        
        # Each worker type should return a reasonable number of threads
        for worker_type in worker_types:
            threads = self.monitor.get_thread_allocation(worker_type)
            self.assertGreater(threads, 0)
            self.assertLessEqual(threads, self.monitor.thread_pool_info["recommended_size"] * 2)
        
        # Test with different system statuses
        statuses = ["critical", "high", "moderate", "low"]
        
        for status in statuses:
            self.monitor.system_status["overall"] = status
            # Thread count should generally decrease as resource pressure increases
            threads_prefetch = self.monitor.get_thread_allocation("prefetch")
            
            # Critical status should always return minimal threads
            if status == "critical":
                self.assertEqual(threads_prefetch, 1)
            
            # Low status should provide more threads
            if status == "low":
                self.assertGreater(threads_prefetch, 1)
    
    def test_prefetch_parameters(self):
        """Test prefetch parameters adapt to system resources."""
        # Test with different system statuses
        statuses = ["critical", "high", "moderate", "low"]
        
        for status in statuses:
            # Set system status
            self.monitor.system_status["overall"] = status
            
            # Get prefetch parameters
            params = self.monitor.get_prefetch_parameters()
            
            # Verify parameters exist
            self.assertIn("enabled", params)
            self.assertIn("max_items", params)
            self.assertIn("chunk_size", params)
            self.assertIn("max_concurrent", params)
            
            # Verify constraints based on status
            if status == "critical":
                self.assertFalse(params["enabled"])
                self.assertEqual(params["max_items"], 0)
            elif status == "low":
                self.assertTrue(params["enabled"])
                self.assertGreaterEqual(params["max_items"], 5)
                self.assertTrue(params["aggressive"])
    
    def test_memory_allocation(self):
        """Test memory allocation recommendations based on resource state."""
        # Test with different resource types
        resource_types = ["cache", "buffer", "heap"]
        
        # Force system status for testing
        self.monitor.system_status["overall"] = "low"
        
        # Each resource type should return a reasonable allocation
        for resource_type in resource_types:
            allocation = self.monitor.get_memory_allocation(resource_type)
            self.assertGreater(allocation, 0)
        
        # Test with different system statuses
        statuses = ["critical", "high", "moderate", "low"]
        
        for status in statuses:
            self.monitor.system_status["overall"] = status
            
            # Memory allocations should generally decrease as resource pressure increases
            buffer_size = self.monitor.get_memory_allocation("buffer")
            
            # Critical status should limit buffer size
            if status == "critical":
                self.assertLessEqual(buffer_size, self.monitor.get_memory_allocation("buffer", 10 * 1024 * 1024) // 5)
    
    def test_io_throttling(self):
        """Test I/O throttling parameters adapt to system resources."""
        # Test with different system statuses
        statuses = ["critical", "high", "moderate", "low"]
        
        for status in statuses:
            # Set system status
            self.monitor.system_status["overall"] = status
            self.monitor.system_status["bottleneck"] = "network"
            
            # Get I/O throttling parameters
            params = self.monitor.get_io_throttle_parameters()
            
            # Verify parameters exist
            self.assertIn("max_concurrent_io", params)
            self.assertIn("max_bandwidth_bps", params)
            self.assertIn("throttle_delay", params)
            
            # Verify constraints based on status
            if status == "critical":
                self.assertEqual(params["max_concurrent_io"], 1)
                self.assertGreater(params["throttle_delay"], 0)
            elif status == "low":
                self.assertGreater(params["max_concurrent_io"], 1)
                self.assertEqual(params["throttle_delay"], 0)


class TestAdaptiveThreadPool(unittest.TestCase):
    """Tests for the AdaptiveThreadPool class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a mock resource monitor
        self.resource_monitor = MagicMock()
        self.resource_monitor.get_thread_allocation.return_value = 4
        
        # Create an AdaptiveThreadPool with the mock monitor
        self.thread_pool = AdaptiveThreadPool(
            resource_monitor=self.resource_monitor,
            config={
                "initial_threads": 2,
                "min_threads": 1,
                "max_threads": 4,
                "dynamic_adjustment": False,  # Disable dynamic adjustment for easier testing
                "thread_idle_timeout": 0.5  # Short timeout for faster testing
            }
        )
    
    def tearDown(self):
        """Clean up after tests."""
        self.thread_pool.shutdown()
    
    def test_initialization(self):
        """Test pool initialization."""
        # Verify pool creates the specified number of workers
        self.assertEqual(len(self.thread_pool.workers), 2)
        
        # Verify stats are initialized
        self.assertEqual(self.thread_pool.stats["tasks_submitted"], 0)
        self.assertEqual(self.thread_pool.stats["tasks_completed"], 0)
        self.assertEqual(self.thread_pool.stats["tasks_failed"], 0)
    
    def test_submit_and_execute(self):
        """Test submitting and executing tasks."""
        # Create a task to execute
        result = []
        def test_task(x, y):
            time.sleep(0.1)  # Small delay to ensure task runs
            result.append(x + y)
            return x + y
        
        # Submit the task
        self.thread_pool.submit(test_task, 3, 4)
        
        # Wait for task to complete
        time.sleep(0.3)
        
        # Verify task was executed
        self.assertEqual(result, [7])
        
        # Verify stats were updated
        self.assertEqual(self.thread_pool.stats["tasks_submitted"], 1)
        self.assertEqual(self.thread_pool.stats["tasks_completed"], 1)
    
    def test_task_priorities(self):
        """Test tasks are executed in priority order."""
        # Create test tasks that add their priority to a result list
        result = []
        def priority_task(priority):
            time.sleep(0.05)  # Small delay
            result.append(priority)
        
        # Submit tasks with different priorities
        # Priority 0 is highest, 2 is lowest
        self.thread_pool.submit(priority_task, 2, priority=2)  # Lowest priority
        self.thread_pool.submit(priority_task, 1, priority=1)  # Medium priority
        self.thread_pool.submit(priority_task, 0, priority=0)  # Highest priority
        
        # Wait for tasks to complete
        time.sleep(0.5)
        
        # Verify tasks were executed in priority order (0, 1, 2)
        self.assertEqual(result, [0, 1, 2])
    
    def test_worker_idle_timeout(self):
        """Test that idle workers exit after timeout."""
        # Create a thread pool with only 1 initial thread
        pool = AdaptiveThreadPool(
            resource_monitor=self.resource_monitor,
            config={
                "initial_threads": 3,
                "min_threads": 1,
                "max_threads": 4,
                "dynamic_adjustment": False,
                "thread_idle_timeout": 0.2  # Very short timeout for testing
            }
        )
        
        # Verify initial thread count
        self.assertEqual(len(pool.workers), 3)
        
        # Wait for idle timeout
        time.sleep(0.5)
        
        # Verify thread count has decreased to min_threads
        self.assertEqual(len(pool.workers), 1)
        
        # Clean up
        pool.shutdown()


class TestResourceAdapter(unittest.TestCase):
    """Tests for the ResourceAdapter class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a mock resource monitor
        self.resource_monitor = MagicMock()
        self.resource_monitor.get_status.return_value = {
            "overall": "moderate",
            "bottleneck": "cpu",
            "cpu": {"status": "moderate", "usage_percent": 70},
            "memory": {"status": "low", "used_percent": 40},
            "recommendations": {
                "thread_pool_size": 4,
                "memory_cache_bytes": 512 * 1024 * 1024
            }
        }
        self.resource_monitor.get_prefetch_parameters.return_value = {
            "enabled": True,
            "max_items": 5,
            "chunk_size": 3,
            "max_concurrent": 3,
            "aggressive": False
        }
        self.resource_monitor.get_thread_allocation.return_value = 4
        self.resource_monitor.get_memory_allocation.return_value = 256 * 1024 * 1024
        self.resource_monitor.get_io_throttle_parameters.return_value = {
            "max_concurrent_io": 4,
            "max_bandwidth_bps": 1024 * 1024,
            "throttle_delay": 0.0
        }
        
        # Create a resource adapter
        self.adapter = ResourceAdapter(self.resource_monitor)
    
    def test_configure_prefetch_manager(self):
        """Test configuring a prefetch manager."""
        # Create a mock prefetch manager
        prefetch_manager = MagicMock()
        prefetch_manager.config = {
            "enabled": False,
            "max_prefetch_items": 10,
            "prefetch_threshold": 0.3
        }
        prefetch_manager.prefetch_thread_pool = MagicMock()
        
        # Configure the prefetch manager
        self.adapter.configure_prefetch_manager(prefetch_manager)
        
        # Verify configuration was applied
        self.assertEqual(prefetch_manager.config["enabled"], True)
        self.assertEqual(prefetch_manager.config["max_prefetch_items"], 5)
        self.assertEqual(prefetch_manager.config["prefetch_threshold"], 0.5)
        self.assertEqual(prefetch_manager.prefetch_thread_pool._max_workers, 3)
    
    def test_configure_thread_pool(self):
        """Test configuring a thread pool."""
        # Create a mock thread pool
        thread_pool = MagicMock()
        thread_pool._max_workers = 8
        
        # Configure the thread pool
        self.adapter.configure_thread_pool(thread_pool, "prefetch")
        
        # Verify configuration was applied
        self.assertEqual(thread_pool._max_workers, 4)
    
    def test_configure_cache(self):
        """Test configuring a cache manager."""
        # Create a mock cache manager
        cache_manager = MagicMock()
        cache_manager.config = {
            "memory_cache_size": 1024 * 1024 * 1024,
            "max_item_size": 100 * 1024 * 1024
        }
        
        # Configure the cache manager
        self.adapter.configure_cache(cache_manager)
        
        # Verify configuration was applied
        self.assertEqual(cache_manager.config["memory_cache_size"], 256 * 1024 * 1024)
    
    def test_apply_io_throttling(self):
        """Test applying I/O throttling."""
        # Create a mock I/O operation
        io_operation = MagicMock()
        io_operation.return_value = "success"
        
        # Apply I/O throttling
        result = self.adapter.apply_io_throttling(io_operation, "arg1", arg2="value")
        
        # Verify operation was called with correct arguments
        io_operation.assert_called_once_with("arg1", arg2="value")
        self.assertEqual(result, "success")
    
    def test_get_optimized_config(self):
        """Test getting optimized configurations."""
        # Get optimized configurations for different component types
        prefetch_config = self.adapter.get_optimized_config("prefetch")
        cache_config = self.adapter.get_optimized_config("cache")
        network_config = self.adapter.get_optimized_config("network")
        
        # Verify configurations have expected keys
        self.assertIn("enabled", prefetch_config)
        self.assertIn("max_prefetch_items", prefetch_config)
        
        self.assertIn("memory_cache_size", cache_config)
        self.assertIn("local_cache_size", cache_config)
        
        self.assertIn("max_concurrent_requests", network_config)
        self.assertIn("max_bandwidth_bps", network_config)


if __name__ == '__main__':
    unittest.main()