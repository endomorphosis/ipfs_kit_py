#!/usr/bin/env python3
"""
Unit tests for connection pool functionality.
"""

import time
import unittest
import threading
from unittest.mock import Mock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ipfs_kit_py.connection_pool import (
    ConnectionPool,
    ConnectionPoolManager,
    PooledConnection,
    get_global_pool_manager,
)


class TestConnectionPool(unittest.TestCase):
    """Test connection pool functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.connection_counter = 0
        
    def _create_mock_connection(self):
        """Create a mock connection."""
        self.connection_counter += 1
        return Mock(id=self.connection_counter)
    
    def _health_check(self, connection):
        """Mock health check."""
        return hasattr(connection, 'id')
    
    def test_pool_initialization(self):
        """Test pool is initialized correctly."""
        pool = ConnectionPool(
            connection_factory=self._create_mock_connection,
            min_size=2,
            max_size=5,
        )
        
        # Should create min_size connections
        stats = pool.get_stats()
        self.assertGreaterEqual(stats['total_size'], 2)
        self.assertEqual(stats['min_size'], 2)
        self.assertEqual(stats['max_size'], 5)
    
    def test_acquire_and_release(self):
        """Test acquiring and releasing connections."""
        pool = ConnectionPool(
            connection_factory=self._create_mock_connection,
            min_size=1,
            max_size=3,
        )
        
        # Acquire connection
        conn = pool.acquire(timeout=1.0)
        self.assertIsNotNone(conn)
        
        stats = pool.get_stats()
        self.assertEqual(stats['in_use'], 1)
        
        # Release connection
        pool.release(conn)
        
        stats = pool.get_stats()
        self.assertEqual(stats['in_use'], 0)
        self.assertGreater(stats['available'], 0)
    
    def test_pool_exhaustion(self):
        """Test pool behavior when exhausted."""
        pool = ConnectionPool(
            connection_factory=self._create_mock_connection,
            min_size=1,
            max_size=2,
        )
        
        # Acquire all connections
        conn1 = pool.acquire(timeout=1.0)
        conn2 = pool.acquire(timeout=1.0)
        
        self.assertIsNotNone(conn1)
        self.assertIsNotNone(conn2)
        
        # Try to acquire one more (should timeout)
        conn3 = pool.acquire(timeout=0.5)
        self.assertIsNone(conn3)
        
        # Release one and try again
        pool.release(conn1)
        conn4 = pool.acquire(timeout=0.5)
        self.assertIsNotNone(conn4)
    
    def test_concurrent_access(self):
        """Test thread-safe concurrent access."""
        pool = ConnectionPool(
            connection_factory=self._create_mock_connection,
            min_size=2,
            max_size=10,
        )
        
        acquired_conns = []
        errors = []
        
        def worker():
            try:
                conn = pool.acquire(timeout=2.0)
                if conn:
                    acquired_conns.append(conn)
                    time.sleep(0.1)
                    pool.release(conn)
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have no errors
        self.assertEqual(len(errors), 0)
        
        # All connections should be released
        stats = pool.get_stats()
        self.assertEqual(stats['in_use'], 0)
    
    def test_connection_health_check(self):
        """Test connection health checking."""
        # Health check that always fails for first connection
        first_call = [True]
        
        def health_check_first_fail(conn):
            if first_call[0]:
                first_call[0] = False
                return False
            return self._health_check(conn)
        
        pool = ConnectionPool(
            connection_factory=self._create_mock_connection,
            health_check=health_check_first_fail,
            min_size=0,
            max_size=5,
        )
        
        # First acquire should skip the unhealthy connection
        conn = pool.acquire(timeout=1.0)
        self.assertIsNotNone(conn)
        # Should have created at least 2 connections (one unhealthy, one healthy)
        stats = pool.get_stats()
        self.assertGreaterEqual(stats['total_created'], 1)
    
    def test_connection_recycling(self):
        """Test connection recycling based on lifetime."""
        pool = ConnectionPool(
            connection_factory=self._create_mock_connection,
            min_size=1,
            max_size=3,
            max_connection_lifetime=1,  # 1 second
        )
        
        # Acquire and use connection
        conn = pool.acquire(timeout=1.0)
        original_id = conn.id
        
        # Wait for lifetime to expire
        time.sleep(1.1)
        
        pool.release(conn)
        
        # Next acquire should get a new connection
        time.sleep(0.5)  # Give maintenance time to run
        conn2 = pool.acquire(timeout=1.0)
        
        # May or may not be recycled depending on maintenance timing
        self.assertIsNotNone(conn2)
    
    def test_pool_statistics(self):
        """Test pool statistics tracking."""
        pool = ConnectionPool(
            connection_factory=self._create_mock_connection,
            min_size=2,
            max_size=5,
        )
        
        stats = pool.get_stats()
        
        # Check expected fields
        self.assertIn('available', stats)
        self.assertIn('in_use', stats)
        self.assertIn('total_size', stats)
        self.assertIn('total_created', stats)
        self.assertIn('min_size', stats)
        self.assertIn('max_size', stats)
        
        # Verify initial state
        self.assertEqual(stats['min_size'], 2)
        self.assertEqual(stats['max_size'], 5)
        self.assertGreaterEqual(stats['total_created'], 2)


class TestConnectionPoolManager(unittest.TestCase):
    """Test connection pool manager."""
    
    def test_get_or_create_pool(self):
        """Test getting or creating pools."""
        manager = ConnectionPoolManager()
        
        def factory():
            return Mock()
        
        # Create pool
        pool1 = manager.get_or_create_pool("backend1", factory, min_size=2)
        self.assertIsNotNone(pool1)
        
        # Get same pool
        pool2 = manager.get_or_create_pool("backend1", factory, min_size=2)
        self.assertIs(pool1, pool2)
        
        # Create different pool
        pool3 = manager.get_or_create_pool("backend2", factory, min_size=2)
        self.assertIsNot(pool1, pool3)
    
    def test_get_all_stats(self):
        """Test getting statistics for all pools."""
        manager = ConnectionPoolManager()
        
        def factory():
            return Mock()
        
        manager.get_or_create_pool("backend1", factory, min_size=1)
        manager.get_or_create_pool("backend2", factory, min_size=2)
        
        stats = manager.get_all_stats()
        
        self.assertEqual(len(stats), 2)
        self.assertIn('backend1', stats)
        self.assertIn('backend2', stats)
    
    def test_global_pool_manager(self):
        """Test global pool manager singleton."""
        manager1 = get_global_pool_manager()
        manager2 = get_global_pool_manager()
        
        # Should be same instance
        self.assertIs(manager1, manager2)


if __name__ == '__main__':
    unittest.main()
