#!/usr/bin/env python3
# ipfs_kit_py/mcp/routing/tests/test_router.py

"""
Unit tests for the core router components.

This module tests the basic functionality of the DataRouter class and related
components from the Optimized Data Routing system.
"""

import unittest
from unittest.mock import MagicMock, patch
import time

from ipfs_kit_py.mcp.routing.router import (
    Backend, ContentType, OperationType,
    RouteMetrics, RoutingContext, RoutingDecision, 
    RoutingStrategy, DataRouter
)


class TestRouteMetrics(unittest.TestCase):
    """Test cases for the RouteMetrics class."""
    
    def test_get_set_metric(self):
        """Test getting and setting metrics."""
        metrics = RouteMetrics()
        
        # Test setting standard metrics
        metrics.latency_ms = 100.0
        self.assertEqual(metrics.latency_ms, 100.0)
        self.assertEqual(metrics.get_metric('latency_ms'), 100.0)
        
        # Test getting non-existent metrics
        self.assertIsNone(metrics.get_metric('non_existent'))
        self.assertEqual(metrics.get_metric('non_existent', 'default'), 'default')
        
        # Test setting custom metrics
        metrics.set_metric('custom_latency', 50.0)
        self.assertEqual(metrics.get_metric('custom_latency'), 50.0)
        
        # Test overriding standard metrics with set_metric
        metrics.set_metric('latency_ms', 200.0)
        self.assertEqual(metrics.latency_ms, 200.0)
        
        # Test as_dict method
        metrics_dict = metrics.as_dict()
        self.assertEqual(metrics_dict['latency_ms'], 200.0)
        self.assertEqual(metrics_dict['custom_latency'], 50.0)


class TestRoutingContext(unittest.TestCase):
    """Test cases for the RoutingContext class."""
    
    def test_initialization(self):
        """Test initialization with various parameters."""
        # Test with minimal parameters
        context = RoutingContext(operation=OperationType.READ)
        self.assertEqual(context.operation, OperationType.READ)
        self.assertIsNone(context.content_type)
        self.assertIsNone(context.content_size_bytes)
        self.assertIsNone(context.user_id)
        self.assertIsNone(context.region)
        
        # Test with all parameters
        context = RoutingContext(
            operation=OperationType.WRITE,
            content_type=ContentType.IMAGE,
            content_size_bytes=1024,
            user_id="user123",
            region="us-east",
            priority=5,
            metadata={"key": "value"}
        )
        self.assertEqual(context.operation, OperationType.WRITE)
        self.assertEqual(context.content_type, ContentType.IMAGE)
        self.assertEqual(context.content_size_bytes, 1024)
        self.assertEqual(context.user_id, "user123")
        self.assertEqual(context.region, "us-east")
        self.assertEqual(context.priority, 5)
        self.assertEqual(context.metadata, {"key": "value"})
        
        # Test timestamp is automatically set
        self.assertIsNotNone(context.timestamp)
        self.assertLessEqual(context.timestamp, time.time())
    
    def test_metadata_methods(self):
        """Test getting and setting metadata."""
        context = RoutingContext(operation=OperationType.READ)
        
        # Test get_metadata
        self.assertIsNone(context.get_metadata("key"))
        self.assertEqual(context.get_metadata("key", "default"), "default")
        
        # Test set_metadata
        context.set_metadata("key", "value")
        self.assertEqual(context.get_metadata("key"), "value")
        
        # Test overriding metadata
        context.set_metadata("key", "new_value")
        self.assertEqual(context.get_metadata("key"), "new_value")


class TestRoutingDecision(unittest.TestCase):
    """Test cases for the RoutingDecision class."""
    
    def test_initialization(self):
        """Test initialization with various parameters."""
        metrics = RouteMetrics(latency_ms=100.0)
        context = RoutingContext(operation=OperationType.READ)
        
        # Test with minimal parameters
        decision = RoutingDecision(
            backend="IPFS",
            score=0.8,
            reason="Test reason",
            metrics=metrics
        )
        self.assertEqual(decision.backend, "IPFS")
        self.assertEqual(decision.score, 0.8)
        self.assertEqual(decision.reason, "Test reason")
        self.assertEqual(decision.metrics, metrics)
        self.assertEqual(decision.alternatives, [])
        self.assertIsNone(decision.context)
        
        # Test with all parameters
        decision = RoutingDecision(
            backend="IPFS",
            score=0.8,
            reason="Test reason",
            metrics=metrics,
            alternatives=[("S3", 0.7), ("FILECOIN", 0.6)],
            context=context
        )
        self.assertEqual(decision.backend, "IPFS")
        self.assertEqual(decision.score, 0.8)
        self.assertEqual(decision.reason, "Test reason")
        self.assertEqual(decision.metrics, metrics)
        self.assertEqual(decision.alternatives, [("S3", 0.7), ("FILECOIN", 0.6)])
        self.assertEqual(decision.context, context)
    
    def test_has_alternatives(self):
        """Test has_alternatives property."""
        metrics = RouteMetrics()
        
        # Test with no alternatives
        decision = RoutingDecision(
            backend="IPFS",
            score=0.8,
            reason="Test reason",
            metrics=metrics
        )
        self.assertFalse(decision.has_alternatives)
        
        # Test with alternatives
        decision = RoutingDecision(
            backend="IPFS",
            score=0.8,
            reason="Test reason",
            metrics=metrics,
            alternatives=[("S3", 0.7)]
        )
        self.assertTrue(decision.has_alternatives)
    
    def test_get_best_alternative(self):
        """Test get_best_alternative method."""
        metrics = RouteMetrics()
        
        # Test with no alternatives
        decision = RoutingDecision(
            backend="IPFS",
            score=0.8,
            reason="Test reason",
            metrics=metrics
        )
        self.assertIsNone(decision.get_best_alternative())
        
        # Test with alternatives
        decision = RoutingDecision(
            backend="IPFS",
            score=0.8,
            reason="Test reason",
            metrics=metrics,
            alternatives=[("S3", 0.7), ("FILECOIN", 0.6)]
        )
        best_alt = decision.get_best_alternative()
        self.assertEqual(best_alt, ("S3", 0.7))
        
        # Test with highest score not first
        decision = RoutingDecision(
            backend="IPFS",
            score=0.8,
            reason="Test reason",
            metrics=metrics,
            alternatives=[("FILECOIN", 0.6), ("S3", 0.9)]
        )
        best_alt = decision.get_best_alternative()
        self.assertEqual(best_alt, ("S3", 0.9))


class MockStrategy(RoutingStrategy):
    """Mock routing strategy for testing."""
    
    def __init__(self, backend_to_select=None, score=1.0):
        self.backend_to_select = backend_to_select
        self.score = score
        self.call_count = 0
    
    def select_backend(self, context, available_backends, metrics):
        """Mock implementation that returns a predefined backend."""
        self.call_count += 1
        
        # Use first available backend if none specified
        backend = self.backend_to_select or available_backends[0]
        
        return RoutingDecision(
            backend=backend,
            score=self.score,
            reason=f"Mock decision for {backend}",
            metrics=RouteMetrics(),
            alternatives=[(b, 0.5) for b in available_backends if b != backend],
            context=context
        )


class TestDataRouter(unittest.TestCase):
    """Test cases for the DataRouter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.router = DataRouter()
        
        # Register some backends
        self.router.register_backend("IPFS", {"type": "ipfs"})
        self.router.register_backend("S3", {"type": "s3"})
        self.router.register_backend("FILECOIN", {"type": "filecoin"})
        
        # Register a mock strategy
        self.mock_strategy = MockStrategy(backend_to_select="IPFS")
        self.router.add_strategy("mock", self.mock_strategy)
        self.router.set_primary_strategy(self.mock_strategy)
        
        # Register a mock metrics collector
        self.mock_collector = MagicMock()
        self.mock_collector.collect_metrics.return_value = {"metric": 1.0}
        self.router.register_metrics_collector("mock", self.mock_collector)
    
    def test_register_unregister_backend(self):
        """Test registering and unregistering backends."""
        # Test registering a new backend
        self.router.register_backend("NEW", {"type": "new"})
        self.assertIn("NEW", self.router.available_backends)
        self.assertEqual(self.router.backend_info["NEW"], {"type": "new"})
        
        # Test unregistering a backend
        self.router.unregister_backend("NEW")
        self.assertNotIn("NEW", self.router.available_backends)
        self.assertNotIn("NEW", self.router.backend_info)
    
    def test_add_remove_strategy(self):
        """Test adding and removing strategies."""
        # Test adding a new strategy
        new_strategy = MockStrategy(backend_to_select="S3")
        self.router.add_strategy("new", new_strategy)
        self.assertIn("new", self.router.strategies)
        self.assertEqual(self.router.strategies["new"], new_strategy)
        
        # Test removing a strategy
        self.router.remove_strategy("new")
        self.assertNotIn("new", self.router.strategies)
    
    def test_set_primary_strategy(self):
        """Test setting the primary strategy."""
        # Test setting a new primary strategy
        new_strategy = MockStrategy(backend_to_select="S3")
        self.router.set_primary_strategy(new_strategy)
        self.assertEqual(self.router.primary_strategy, new_strategy)
    
    def test_register_unregister_metrics_collector(self):
        """Test registering and unregistering metrics collectors."""
        # Test registering a new collector
        new_collector = MagicMock()
        self.router.register_metrics_collector("new", new_collector)
        self.assertIn("new", self.router.metrics_collectors)
        self.assertEqual(self.router.metrics_collectors["new"], new_collector)
        
        # Test unregistering a collector
        self.router.unregister_metrics_collector("new")
        self.assertNotIn("new", self.router.metrics_collectors)
    
    def test_collect_metrics(self):
        """Test collecting metrics for backends."""
        # Test collecting metrics for all backends
        metrics = self.router.collect_metrics()
        self.assertIn("IPFS", metrics)
        self.assertIn("S3", metrics)
        self.assertIn("FILECOIN", metrics)
        
        # Check mock collector was called for each backend
        self.assertEqual(self.mock_collector.collect_metrics.call_count, 3)
        
        # Test collecting metrics for specific backends
        metrics = self.router.collect_metrics(["IPFS", "S3"])
        self.assertIn("IPFS", metrics)
        self.assertIn("S3", metrics)
        self.assertNotIn("FILECOIN", metrics)
    
    def test_select_backend(self):
        """Test selecting a backend for a context."""
        # Create a context
        context = RoutingContext(operation=OperationType.READ)
        
        # Select a backend
        decision = self.router.select_backend(context)
        
        # Check the decision
        self.assertEqual(decision.backend, "IPFS")
        self.assertEqual(decision.score, 1.0)
        self.assertEqual(self.mock_strategy.call_count, 1)
        
        # Check the decision was recorded in history
        self.assertEqual(len(self.router.routing_history), 1)
        self.assertEqual(self.router.routing_history[0].backend, "IPFS")
    
    def test_select_backend_with_strategy(self):
        """Test selecting a backend with a specific strategy."""
        # Create a context
        context = RoutingContext(operation=OperationType.READ)
        
        # Add a strategy that selects a different backend
        diff_strategy = MockStrategy(backend_to_select="S3", score=0.9)
        self.router.add_strategy("diff", diff_strategy)
        
        # Select a backend with the different strategy
        decision = self.router.select_backend(context, strategy_name="diff")
        
        # Check the decision
        self.assertEqual(decision.backend, "S3")
        self.assertEqual(decision.score, 0.9)
        self.assertEqual(diff_strategy.call_count, 1)
        self.assertEqual(self.mock_strategy.call_count, 0)  # Primary not called
    
    def test_select_backend_no_backends(self):
        """Test selecting a backend when none are available."""
        # Remove all backends
        for backend in list(self.router.available_backends):
            self.router.unregister_backend(backend)
        
        # Create a context
        context = RoutingContext(operation=OperationType.READ)
        
        # Try to select a backend
        with self.assertRaises(ValueError):
            self.router.select_backend(context)
    
    def test_select_backend_no_strategy(self):
        """Test selecting a backend when no strategy is set."""
        # Remove primary strategy
        self.router.primary_strategy = None
        
        # Create a context
        context = RoutingContext(operation=OperationType.READ)
        
        # Try to select a backend
        with self.assertRaises(ValueError):
            self.router.select_backend(context)
    
    def test_get_backend_info(self):
        """Test getting backend information."""
        # Test getting info for an existing backend
        info = self.router.get_backend_info("IPFS")
        self.assertEqual(info, {"type": "ipfs"})
        
        # Test getting info for a non-existent backend
        with self.assertRaises(KeyError):
            self.router.get_backend_info("NON_EXISTENT")
    
    def test_get_routing_history(self):
        """Test getting routing history."""
        # Create some decisions
        context1 = RoutingContext(operation=OperationType.READ)
        context2 = RoutingContext(operation=OperationType.WRITE)
        
        decision1 = self.router.select_backend(context1)
        decision2 = self.router.select_backend(context2)
        
        # Get all history
        history = self.router.get_routing_history()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].backend, "IPFS")
        self.assertEqual(history[1].backend, "IPFS")
        
        # Get limited history
        history = self.router.get_routing_history(limit=1)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].backend, "IPFS")
        
        # Check history is returned in correct order (oldest first)
        self.assertEqual(history[0].context.operation, OperationType.WRITE)


if __name__ == "__main__":
    unittest.main()