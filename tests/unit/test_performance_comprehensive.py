"""
Comprehensive Tests for Performance Optimization (Phase 9)

Tests all components of the performance optimization system:
- Cache Manager (LRU/LFU, multi-tier, invalidation)
- Batch Operations (parallel, sequential, transactions)
- Performance Monitor (timing, resources, bottlenecks)
- MCP tools integration
- CLI integration
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil
import time
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from ipfs_kit_py.cache_manager import (
    CacheManager, CacheEntry, LRUCache, LFUCache, DiskCache
)
from ipfs_kit_py.batch_operations import (
    BatchProcessor, TransactionBatch, Operation, OperationStatus, BatchResult
)
from ipfs_kit_py.performance_monitor import (
    PerformanceMonitor, OperationMetrics, ResourceSnapshot, Bottleneck
)


class TestCacheEntry(unittest.TestCase):
    """Test cache entry functionality"""
    
    def test_cache_entry_creation(self):
        """Test creating a cache entry"""
        entry = CacheEntry('key1', 'value1', ttl=60)
        self.assertEqual(entry.key, 'key1')
        self.assertEqual(entry.value, 'value1')
        self.assertIsNotNone(entry.created_at)
        self.assertIsNotNone(entry.expires_at)
    
    def test_cache_entry_no_ttl(self):
        """Test cache entry without TTL"""
        entry = CacheEntry('key1', 'value1')
        self.assertIsNone(entry.expires_at)
        self.assertFalse(entry.is_expired())
    
    def test_cache_entry_expiration(self):
        """Test cache entry expiration"""
        entry = CacheEntry('key1', 'value1', ttl=0.1)
        self.assertFalse(entry.is_expired())
        time.sleep(0.2)
        self.assertTrue(entry.is_expired())
    
    def test_cache_entry_touch(self):
        """Test cache entry touch updates access metadata"""
        entry = CacheEntry('key1', 'value1')
        initial_count = entry.access_count
        initial_time = entry.accessed_at
        
        time.sleep(0.01)
        entry.touch()
        
        self.assertEqual(entry.access_count, initial_count + 1)
        self.assertGreater(entry.accessed_at, initial_time)


class TestLRUCache(unittest.TestCase):
    """Test LRU cache implementation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.cache = LRUCache(max_size=3)
    
    def test_lru_set_and_get(self):
        """Test setting and getting from LRU cache"""
        entry = CacheEntry('key1', 'value1')
        self.cache.set('key1', entry)
        
        retrieved = self.cache.get('key1')
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.value, 'value1')
    
    def test_lru_eviction(self):
        """Test LRU eviction on capacity"""
        # Fill cache
        self.cache.set('key1', CacheEntry('key1', 'value1'))
        self.cache.set('key2', CacheEntry('key2', 'value2'))
        self.cache.set('key3', CacheEntry('key3', 'value3'))
        
        # Add one more (should evict key1)
        self.cache.set('key4', CacheEntry('key4', 'value4'))
        
        self.assertIsNone(self.cache.get('key1'))
        self.assertIsNotNone(self.cache.get('key2'))
        self.assertIsNotNone(self.cache.get('key4'))
    
    def test_lru_move_to_end(self):
        """Test that access moves item to end"""
        self.cache.set('key1', CacheEntry('key1', 'value1'))
        self.cache.set('key2', CacheEntry('key2', 'value2'))
        self.cache.set('key3', CacheEntry('key3', 'value3'))
        
        # Access key1 (moves to end)
        self.cache.get('key1')
        
        # Add key4 (should evict key2, not key1)
        self.cache.set('key4', CacheEntry('key4', 'value4'))
        
        self.assertIsNotNone(self.cache.get('key1'))
        self.assertIsNone(self.cache.get('key2'))
    
    def test_lru_delete(self):
        """Test deleting from LRU cache"""
        self.cache.set('key1', CacheEntry('key1', 'value1'))
        self.assertTrue(self.cache.delete('key1'))
        self.assertIsNone(self.cache.get('key1'))
        self.assertFalse(self.cache.delete('key1'))
    
    def test_lru_clear(self):
        """Test clearing LRU cache"""
        self.cache.set('key1', CacheEntry('key1', 'value1'))
        self.cache.set('key2', CacheEntry('key2', 'value2'))
        
        self.cache.clear()
        self.assertEqual(self.cache.size(), 0)


class TestLFUCache(unittest.TestCase):
    """Test LFU cache implementation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.cache = LFUCache(max_size=3)
    
    def test_lfu_eviction_by_frequency(self):
        """Test LFU evicts least frequently used"""
        # Add items
        self.cache.set('key1', CacheEntry('key1', 'value1'))
        self.cache.set('key2', CacheEntry('key2', 'value2'))
        self.cache.set('key3', CacheEntry('key3', 'value3'))
        
        # Access key1 and key2 multiple times
        self.cache.get('key1')
        self.cache.get('key1')
        self.cache.get('key2')
        
        # Add key4 (should evict key3 - least accessed)
        self.cache.set('key4', CacheEntry('key4', 'value4'))
        
        self.assertIsNotNone(self.cache.get('key1'))
        self.assertIsNotNone(self.cache.get('key2'))
        self.assertIsNone(self.cache.get('key3'))
        self.assertIsNotNone(self.cache.get('key4'))


class TestDiskCache(unittest.TestCase):
    """Test disk cache implementation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cache = DiskCache(self.temp_dir, max_size_mb=1)
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_disk_cache_set_and_get(self):
        """Test setting and getting from disk cache"""
        entry = CacheEntry('key1', 'value1')
        self.cache.set('key1', entry)
        
        retrieved = self.cache.get('key1')
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.value, 'value1')
    
    def test_disk_cache_persistence(self):
        """Test disk cache persists across instances"""
        entry = CacheEntry('key1', 'value1')
        self.cache.set('key1', entry)
        
        # Create new cache instance with same directory
        cache2 = DiskCache(self.temp_dir, max_size_mb=1)
        retrieved = cache2.get('key1')
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.value, 'value1')
    
    def test_disk_cache_delete(self):
        """Test deleting from disk cache"""
        self.cache.set('key1', CacheEntry('key1', 'value1'))
        self.assertTrue(self.cache.delete('key1'))
        self.assertIsNone(self.cache.get('key1'))


class TestCacheManager(unittest.TestCase):
    """Test cache manager with multi-tier caching"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cache = CacheManager(
            memory_policy='lru',
            memory_size=10,
            disk_size_mb=1,
            cache_dir=self.temp_dir,
            enable_disk=True
        )
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_cache_manager_set_and_get(self):
        """Test basic set and get"""
        self.cache.set('key1', 'value1')
        self.assertEqual(self.cache.get('key1'), 'value1')
    
    def test_cache_manager_ttl(self):
        """Test TTL expiration"""
        self.cache.set('key1', 'value1', ttl=0.1)
        self.assertEqual(self.cache.get('key1'), 'value1')
        
        time.sleep(0.2)
        self.assertIsNone(self.cache.get('key1'))
    
    def test_cache_manager_tier_promotion(self):
        """Test disk to memory promotion"""
        # Set memory only
        self.cache.set('key1', 'value1', memory_only=True)
        
        # Clear memory cache
        self.cache.clear('memory')
        
        # Should be gone (was memory only)
        self.assertIsNone(self.cache.get('key1'))
        
        # Set in both tiers
        self.cache.set('key2', 'value2', memory_only=False)
        
        # Clear memory
        self.cache.clear('memory')
        
        # Should still be available from disk
        self.assertEqual(self.cache.get('key2'), 'value2')
    
    def test_cache_manager_delete(self):
        """Test deleting from both tiers"""
        self.cache.set('key1', 'value1')
        self.assertTrue(self.cache.delete('key1'))
        self.assertIsNone(self.cache.get('key1'))
    
    def test_cache_manager_invalidate_pattern(self):
        """Test pattern-based invalidation"""
        self.cache.set('user:1', 'data1')
        self.cache.set('user:2', 'data2')
        self.cache.set('post:1', 'post1')
        
        self.cache.invalidate_pattern('user:*')
        
        self.assertIsNone(self.cache.get('user:1'))
        self.assertIsNone(self.cache.get('user:2'))
        self.assertIsNotNone(self.cache.get('post:1'))
    
    def test_cache_manager_statistics(self):
        """Test statistics tracking"""
        self.cache.set('key1', 'value1')
        self.cache.get('key1')  # Hit
        self.cache.get('key2')  # Miss
        
        stats = self.cache.get_statistics()
        
        self.assertEqual(stats['hits'], 1)
        self.assertEqual(stats['misses'], 1)
        self.assertEqual(stats['sets'], 1)
        self.assertGreater(stats['hit_rate_percent'], 0)


class TestBatchProcessor(unittest.TestCase):
    """Test batch operations processor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.processor = BatchProcessor(max_batch_size=10, max_workers=2)
    
    def test_batch_add_operation(self):
        """Test adding operations to batch"""
        op_id = self.processor.add_operation(lambda x: x * 2, 5)
        self.assertIsNotNone(op_id)
        self.assertEqual(len(self.processor.operations), 1)
    
    def test_batch_execute_sequential(self):
        """Test sequential batch execution"""
        self.processor.add_operation(lambda x: x * 2, 5)
        self.processor.add_operation(lambda x: x + 10, 3)
        
        result = self.processor.execute_batch(parallel=False)
        
        self.assertEqual(result.total_operations, 2)
        self.assertEqual(result.successful, 2)
        self.assertEqual(result.failed, 0)
    
    def test_batch_execute_parallel(self):
        """Test parallel batch execution"""
        self.processor.add_operation(lambda x: x * 2, 5)
        self.processor.add_operation(lambda x: x + 10, 3)
        
        result = self.processor.execute_batch(parallel=True)
        
        self.assertEqual(result.total_operations, 2)
        self.assertEqual(result.successful, 2)
    
    def test_batch_error_handling(self):
        """Test error handling in batch"""
        self.processor.add_operation(lambda: 1/0)  # Will raise error
        self.processor.add_operation(lambda: 42)
        
        result = self.processor.execute_batch(parallel=False)
        
        self.assertEqual(result.failed, 1)
        self.assertEqual(result.successful, 1)
    
    def test_batch_get_results(self):
        """Test getting results from batch"""
        self.processor.add_operation(lambda x: x * 2, 5)
        self.processor.add_operation(lambda x: x + 10, 3)
        
        self.processor.execute_batch(parallel=False)
        results = self.processor.get_results()
        
        self.assertEqual(len(results), 2)
        self.assertIn(10, results)  # 5 * 2
        self.assertIn(13, results)  # 3 + 10
    
    def test_batch_statistics(self):
        """Test batch statistics"""
        self.processor.add_operation(lambda: 42)
        stats = self.processor.get_statistics()
        
        self.assertEqual(stats['total_operations'], 1)
        self.assertEqual(stats['pending'], 1)


class TestTransactionBatch(unittest.TestCase):
    """Test transaction batch with rollback"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.batch = TransactionBatch(max_batch_size=10)
        self.rollback_called = []
    
    def test_transaction_success(self):
        """Test successful transaction"""
        self.batch.add_operation(lambda: 42, rollback_func=None)
        self.batch.add_operation(lambda: 100, rollback_func=None)
        
        result = self.batch.execute_batch(parallel=False)
        
        self.assertEqual(result.successful, 2)
        self.assertEqual(result.failed, 0)
    
    def test_transaction_rollback(self):
        """Test transaction rollback on failure"""
        def rollback1():
            self.rollback_called.append(1)
        
        def rollback2():
            self.rollback_called.append(2)
        
        self.batch.add_operation(lambda: 42, rollback_func=rollback1)
        self.batch.add_operation(lambda: 1/0, rollback_func=rollback2)  # Fails
        
        result = self.batch.execute_batch(parallel=False)
        
        # First operation should be rolled back
        self.assertIn(1, self.rollback_called)


class TestPerformanceMonitor(unittest.TestCase):
    """Test performance monitor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.monitor = PerformanceMonitor(history_size=100)
    
    def test_monitor_start_operation(self):
        """Test starting operation tracking"""
        op_id = self.monitor.start_operation('test_op')
        self.assertIsNotNone(op_id)
        self.assertIn(op_id, self.monitor.active_operations)
    
    def test_monitor_end_operation(self):
        """Test ending operation tracking"""
        op_id = self.monitor.start_operation('test_op')
        time.sleep(0.01)
        self.monitor.end_operation(op_id, success=True)
        
        self.assertNotIn(op_id, self.monitor.active_operations)
        self.assertEqual(len(self.monitor.operation_history), 1)
    
    def test_monitor_get_metrics(self):
        """Test getting metrics"""
        op_id = self.monitor.start_operation('test_op')
        time.sleep(0.01)
        self.monitor.end_operation(op_id, success=True)
        
        metrics = self.monitor.get_metrics('test_op', timeframe='1h')
        
        self.assertEqual(metrics['count'], 1)
        self.assertEqual(metrics['successful'], 1)
        self.assertGreater(metrics['avg_duration'], 0)
    
    def test_monitor_detect_bottlenecks(self):
        """Test bottleneck detection"""
        # Mock resource samples with high CPU
        mock_snapshot = Mock()
        mock_snapshot.cpu_percent = 95.0
        mock_snapshot.memory_percent = 50.0
        
        self.monitor.resource_samples.append(mock_snapshot)
        
        bottlenecks = self.monitor.detect_bottlenecks(cpu_threshold=80.0)
        
        # Should detect CPU bottleneck
        cpu_bottlenecks = [b for b in bottlenecks if b.bottleneck_type == 'cpu']
        self.assertGreater(len(cpu_bottlenecks), 0)
    
    def test_monitor_set_baseline(self):
        """Test setting performance baseline"""
        # Add enough operations
        for i in range(15):
            op_id = self.monitor.start_operation('test_op')
            time.sleep(0.001)
            self.monitor.end_operation(op_id, success=True)
        
        self.monitor.set_baseline('test_op')
        self.assertIn('test_op', self.monitor.baselines)


class TestMCPToolsIntegration(unittest.TestCase):
    """Test MCP tools integration"""
    
    def test_performance_tools_import(self):
        """Test that performance MCP tools can be imported"""
        try:
            from ipfs_kit_py.mcp.servers import performance_mcp_tools
            self.assertIsNotNone(performance_mcp_tools)
        except ImportError as e:
            self.fail(f"Could not import performance MCP tools: {e}")
    
    def test_performance_tools_available(self):
        """Test that all expected tools are available"""
        from ipfs_kit_py.mcp.servers import performance_mcp_tools
        
        expected_tools = [
            'performance_get_cache_stats',
            'performance_clear_cache',
            'performance_invalidate_cache',
            'performance_get_metrics',
            'performance_get_bottlenecks',
            'performance_get_resource_usage',
            'performance_set_baseline',
            'performance_start_operation',
            'performance_end_operation',
            'performance_get_monitor_stats',
            'performance_get_batch_stats',
            'performance_reset_cache_stats',
            'performance_get_summary',
        ]
        
        for tool_name in expected_tools:
            self.assertTrue(
                hasattr(performance_mcp_tools, tool_name),
                f"Tool {tool_name} not found"
            )


class TestCLIIntegration(unittest.TestCase):
    """Test CLI integration"""
    
    def test_performance_cli_import(self):
        """Test that performance CLI module can be imported"""
        try:
            from ipfs_kit_py import performance_cli
            self.assertIsNotNone(performance_cli)
        except ImportError as e:
            self.fail(f"Could not import performance CLI: {e}")
    
    def test_performance_cli_parser(self):
        """Test CLI parser creation"""
        from ipfs_kit_py.performance_cli import create_parser
        
        parser = create_parser()
        self.assertIsNotNone(parser)


if __name__ == '__main__':
    unittest.main()
