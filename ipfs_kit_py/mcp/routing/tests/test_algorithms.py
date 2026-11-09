#!/usr/bin/env python3
# ipfs_kit_py/mcp/routing/tests/test_algorithms.py

"""
Unit tests for the routing algorithms.

This module tests the various routing strategy implementations used for
intelligent backend selection.
"""

import unittest
from unittest.mock import MagicMock, patch

from ipfs_kit_py.mcp.routing.router import (
    Backend, ContentType, OperationType,
    RouteMetrics, RoutingContext, RoutingDecision
)
from ipfs_kit_py.mcp.routing.algorithms.content_aware import ContentAwareRouter
from ipfs_kit_py.mcp.routing.algorithms.cost_based import CostBasedRouter
from ipfs_kit_py.mcp.routing.algorithms.geographic import GeographicRouter
from ipfs_kit_py.mcp.routing.algorithms.performance import PerformanceRouter
from ipfs_kit_py.mcp.routing.algorithms.composite import CompositeRouter


class TestContentAwareRouter(unittest.TestCase):
    """Test cases for the ContentAwareRouter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_analyzer = MagicMock()
        self.mock_analyzer.analyze_content_type.return_value = ContentType.IMAGE
        self.mock_analyzer.calculate_backend_score.return_value = 0.8
        
        self.router = ContentAwareRouter(content_analyzer=self.mock_analyzer)
        
        # Available backends
        self.backends = ["IPFS", "S3", "FILECOIN"]
        
        # Mock metrics
        self.metrics = {
            "IPFS": RouteMetrics(content_type=ContentType.IMAGE),
            "S3": RouteMetrics(content_type=ContentType.IMAGE),
            "FILECOIN": RouteMetrics(content_type=ContentType.IMAGE)
        }
    
    def test_select_backend_with_content_type(self):
        """Test selecting a backend with a specified content type."""
        context = RoutingContext(
            operation=OperationType.READ,
            content_type=ContentType.IMAGE,
            content_size_bytes=1024 * 1024  # 1 MB
        )
        
        decision = self.router.select_backend(context, self.backends, self.metrics)
        
        # Check that a decision was made
        self.assertIsNotNone(decision)
        self.assertIn(decision.backend, self.backends)
        self.assertGreater(decision.score, 0)
        self.assertTrue("based on content type" in decision.reason.lower())
    
    def test_select_backend_with_analyzer(self):
        """Test selecting a backend using the content analyzer."""
        context = RoutingContext(
            operation=OperationType.READ,
            content_size_bytes=1024 * 1024,  # 1 MB
            metadata={"content": "some_content"}
        )
        
        decision = self.router.select_backend(context, self.backends, self.metrics)
        
        # Check that the analyzer was called
        self.mock_analyzer.analyze_content_type.assert_called_once()
        
        # Check that a decision was made
        self.assertIsNotNone(decision)
        self.assertIn(decision.backend, self.backends)
        self.assertGreater(decision.score, 0)
    
    def test_select_backend_with_size(self):
        """Test selecting a backend based on content size."""
        # Test with small file
        context_small = RoutingContext(
            operation=OperationType.WRITE,
            content_type=ContentType.IMAGE,
            content_size_bytes=500 * 1024  # 500 KB
        )
        
        decision_small = self.router.select_backend(context_small, self.backends, self.metrics)
        
        # Test with large file
        context_large = RoutingContext(
            operation=OperationType.WRITE,
            content_type=ContentType.IMAGE,
            content_size_bytes=5 * 1024 * 1024 * 1024  # 5 GB
        )
        
        decision_large = self.router.select_backend(context_large, self.backends, self.metrics)
        
        # Decisions should be valid
        self.assertIsNotNone(decision_small)
        self.assertIsNotNone(decision_large)
        
        # Large files often route to different backends than small files
        # but this depends on the implementation, so we just check for valid decisions
        self.assertIn(decision_small.backend, self.backends)
        self.assertIn(decision_large.backend, self.backends)
    
    def test_no_available_backends(self):
        """Test behavior when no backends are available."""
        context = RoutingContext(
            operation=OperationType.READ,
            content_type=ContentType.IMAGE
        )
        
        with self.assertRaises(ValueError):
            self.router.select_backend(context, [], {})


class TestCostBasedRouter(unittest.TestCase):
    """Test cases for the CostBasedRouter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_calculator = MagicMock()
        
        # Configure mock to return different costs for backends
        def collect_metrics_side_effect(backend):
            costs = {
                "IPFS": {"storage_cost": 0.02, "retrieval_cost": 0.01, "operation_cost": 0.0001},
                "S3": {"storage_cost": 0.023, "retrieval_cost": 0.09, "operation_cost": 0.0005},
                "FILECOIN": {"storage_cost": 0.005, "retrieval_cost": 0.02, "operation_cost": 0.001}
            }
            return costs.get(backend, {})
        
        self.mock_calculator.collect_metrics.side_effect = collect_metrics_side_effect
        
        self.router = CostBasedRouter(cost_calculator=self.mock_calculator)
        
        # Available backends
        self.backends = ["IPFS", "S3", "FILECOIN"]
        
        # Mock metrics
        self.metrics = {
            "IPFS": RouteMetrics(
                storage_cost=0.02,
                retrieval_cost=0.01,
                operation_cost=0.0001
            ),
            "S3": RouteMetrics(
                storage_cost=0.023,
                retrieval_cost=0.09,
                operation_cost=0.0005
            ),
            "FILECOIN": RouteMetrics(
                storage_cost=0.005,
                retrieval_cost=0.02,
                operation_cost=0.001
            )
        }
    
    def test_select_backend_for_read(self):
        """Test selecting a backend for a read operation."""
        context = RoutingContext(
            operation=OperationType.READ,
            content_size_bytes=1024 * 1024 * 1024  # 1 GB
        )
        
        decision = self.router.select_backend(context, self.backends, self.metrics)
        
        # For reads, IPFS should be preferred (lowest retrieval cost)
        self.assertEqual(decision.backend, "IPFS")
        self.assertTrue("cost optimization" in decision.reason.lower())
    
    def test_select_backend_for_write(self):
        """Test selecting a backend for a write operation."""
        context = RoutingContext(
            operation=OperationType.WRITE,
            content_size_bytes=1024 * 1024 * 1024  # 1 GB
        )
        
        decision = self.router.select_backend(context, self.backends, self.metrics)
        
        # For writes, FILECOIN should be preferred (lowest storage cost)
        self.assertEqual(decision.backend, "FILECOIN")
        self.assertTrue("cost optimization" in decision.reason.lower())
    
    def test_select_backend_with_missing_metrics(self):
        """Test behavior with missing metrics."""
        context = RoutingContext(
            operation=OperationType.READ,
            content_size_bytes=1024 * 1024  # 1 MB
        )
        
        # Remove metrics for IPFS
        metrics = {
            "S3": self.metrics["S3"],
            "FILECOIN": self.metrics["FILECOIN"]
        }
        
        decision = self.router.select_backend(context, self.backends, metrics)
        
        # Should still make a valid decision
        self.assertIsNotNone(decision)
        self.assertIn(decision.backend, self.backends)
        
        # IPFS should be assigned a high cost and not selected
        self.assertNotEqual(decision.backend, "IPFS")
    
    def test_no_available_backends(self):
        """Test behavior when no backends are available."""
        context = RoutingContext(
            operation=OperationType.READ
        )
        
        with self.assertRaises(ValueError):
            self.router.select_backend(context, [], {})


class TestGeographicRouter(unittest.TestCase):
    """Test cases for the GeographicRouter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_optimizer = MagicMock()
        
        # Configure mock to return different regions for IPs
        def get_region_for_ip_side_effect(ip):
            regions = {
                "192.168.1.1": "us-east",
                "192.168.1.2": "eu-west",
                "192.168.1.3": "ap-northeast"
            }
            return regions.get(ip, "us-east")
        
        self.mock_optimizer.get_region_for_ip.side_effect = get_region_for_ip_side_effect
        
        # Configure mock to calculate proximity scores
        def calculate_proximity_score_side_effect(backend, region):
            # Simulate different proximity scores based on backend and region
            scores = {
                ("IPFS", "us-east"): 0.9,
                ("IPFS", "eu-west"): 0.6,
                ("IPFS", "ap-northeast"): 0.3,
                ("S3", "us-east"): 0.8,
                ("S3", "eu-west"): 0.7,
                ("S3", "ap-northeast"): 0.6,
                ("FILECOIN", "us-east"): 0.7,
                ("FILECOIN", "eu-west"): 0.8,
                ("FILECOIN", "ap-northeast"): 0.5
            }
            return scores.get((backend, region), 0.5)
        
        # Mock method isn't directly in GeographicOptimizer, so patching here
        with patch.object(GeographicRouter, '_calculate_proximity_score') as mock_calc:
            mock_calc.side_effect = calculate_proximity_score_side_effect
            self.router = GeographicRouter(geo_optimizer=self.mock_optimizer)
            self.router._calculate_proximity_score = mock_calc
        
        # Available backends
        self.backends = ["IPFS", "S3", "FILECOIN"]
        
        # Mock metrics
        self.metrics = {
            "IPFS": RouteMetrics(region="us-east"),
            "S3": RouteMetrics(region="us-east"),
            "FILECOIN": RouteMetrics(region="eu-west")
        }
    
    def test_select_backend_with_region(self):
        """Test selecting a backend with a specified region."""
        context = RoutingContext(
            operation=OperationType.READ,
            region="us-east"
        )
        
        decision = self.router.select_backend(context, self.backends, self.metrics)
        
        # IPFS should be preferred for us-east
        self.assertEqual(decision.backend, "IPFS")
        self.assertTrue("geographic proximity" in decision.reason.lower())
    
    def test_select_backend_with_client_ip(self):
        """Test selecting a backend based on client IP."""
        context = RoutingContext(
            operation=OperationType.READ,
            metadata={"client_ip": "192.168.1.2"}  # eu-west region
        )
        
        decision = self.router.select_backend(context, self.backends, self.metrics)
        
        # Should use region from client IP
        self.mock_optimizer.get_region_for_ip.assert_called_with("192.168.1.2")
        
        # FILECOIN should be preferred for eu-west
        self.assertEqual(decision.backend, "FILECOIN")
    
    def test_select_backend_with_residency_requirements(self):
        """Test selecting a backend with data residency requirements."""
        context = RoutingContext(
            operation=OperationType.WRITE,
            region="us-east",
            metadata={"residency_zone": "EU"}
        )
        
        decision = self.router.select_backend(context, self.backends, self.metrics)
        
        # Should mention residency requirements in reason
        self.assertTrue("residency" in decision.reason.lower())
    
    def test_no_available_backends(self):
        """Test behavior when no backends are available."""
        context = RoutingContext(
            operation=OperationType.READ,
            region="us-east"
        )
        
        with self.assertRaises(ValueError):
            self.router.select_backend(context, [], {})


class TestPerformanceRouter(unittest.TestCase):
    """Test cases for the PerformanceRouter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_perf_metrics = MagicMock()
        
        # Configure mock to return different performance metrics for backends
        def collect_metrics_side_effect(backend):
            metrics = {
                "IPFS": {
                    "throughput_mbps": 100.0,
                    "latency_ms": 50.0,
                    "success_rate": 0.99,
                    "availability": 0.995,
                    "performance_score": 0.9
                },
                "S3": {
                    "throughput_mbps": 80.0,
                    "latency_ms": 70.0,
                    "success_rate": 0.999,
                    "availability": 0.9999,
                    "performance_score": 0.85
                },
                "FILECOIN": {
                    "throughput_mbps": 50.0,
                    "latency_ms": 200.0,
                    "success_rate": 0.95,
                    "availability": 0.98,
                    "performance_score": 0.7
                }
            }
            return metrics.get(backend, {})
        
        self.mock_perf_metrics.collect_metrics.side_effect = collect_metrics_side_effect
        
        self.router = PerformanceRouter(performance_metrics=self.mock_perf_metrics)
        
        # Available backends
        self.backends = ["IPFS", "S3", "FILECOIN"]
        
        # Mock metrics
        self.metrics = {
            "IPFS": RouteMetrics(
                latency_ms=50.0,
                throughput_mbps=100.0,
                success_rate=0.99,
                availability=0.995
            ),
            "S3": RouteMetrics(
                latency_ms=70.0,
                throughput_mbps=80.0,
                success_rate=0.999,
                availability=0.9999
            ),
            "FILECOIN": RouteMetrics(
                latency_ms=200.0,
                throughput_mbps=50.0,
                success_rate=0.95,
                availability=0.98
            )
        }
    
    def test_select_backend_for_read(self):
        """Test selecting a backend for a read operation."""
        context = RoutingContext(
            operation=OperationType.READ
        )
        
        decision = self.router.select_backend(context, self.backends, self.metrics)
        
        # IPFS should be preferred for reads (lowest latency, highest throughput)
        self.assertEqual(decision.backend, "IPFS")
        self.assertTrue("performance" in decision.reason.lower())
    
    def test_select_backend_for_write(self):
        """Test selecting a backend for a write operation."""
        context = RoutingContext(
            operation=OperationType.WRITE
        )
        
        decision = self.router.select_backend(context, self.backends, self.metrics)
        
        # Still IPFS should be preferred for writes based on our test metrics
        self.assertEqual(decision.backend, "IPFS")
    
    def test_select_backend_with_missing_metrics(self):
        """Test behavior with missing metrics."""
        context = RoutingContext(
            operation=OperationType.READ
        )
        
        # Provide metrics for only one backend
        metrics = {
            "S3": self.metrics["S3"]
        }
        
        decision = self.router.select_backend(context, self.backends, metrics)
        
        # Should still make a valid decision
        self.assertIsNotNone(decision)
        self.assertIn(decision.backend, self.backends)
    
    def test_no_available_backends(self):
        """Test behavior when no backends are available."""
        context = RoutingContext(
            operation=OperationType.READ
        )
        
        with self.assertRaises(ValueError):
            self.router.select_backend(context, [], {})


class TestCompositeRouter(unittest.TestCase):
    """Test cases for the CompositeRouter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock strategies
        self.mock_content = MagicMock()
        self.mock_cost = MagicMock()
        self.mock_geo = MagicMock()
        self.mock_perf = MagicMock()
        
        # Configure mocks to return decisions
        def make_decision(backend, score, context):
            return RoutingDecision(
                backend=backend,
                score=score,
                reason=f"Mock decision for {backend}",
                metrics=RouteMetrics(),
                alternatives=[
                    (b, score - 0.1) for b in ["IPFS", "S3", "FILECOIN"]
                    if b != backend
                ],
                context=context
            )
        
        self.mock_content.select_backend.side_effect = lambda c, b, m: make_decision("IPFS", 0.9, c)
        self.mock_cost.select_backend.side_effect = lambda c, b, m: make_decision("S3", 0.8, c)
        self.mock_geo.select_backend.side_effect = lambda c, b, m: make_decision("FILECOIN", 0.7, c)
        self.mock_perf.select_backend.side_effect = lambda c, b, m: make_decision("IPFS", 0.85, c)
        
        # Create composite router with weighted strategies
        self.router = CompositeRouter({
            "content": (self.mock_content, 0.4),
            "cost": (self.mock_cost, 0.3),
            "geo": (self.mock_geo, 0.2),
            "perf": (self.mock_perf, 0.1)
        })
        
        # Available backends and mock metrics
        self.backends = ["IPFS", "S3", "FILECOIN"]
        self.metrics = {
            "IPFS": RouteMetrics(),
            "S3": RouteMetrics(),
            "FILECOIN": RouteMetrics()
        }
    
    def test_select_backend(self):
        """Test selecting a backend using the composite router."""
        context = RoutingContext(
            operation=OperationType.READ
        )
        
        decision = self.router.select_backend(context, self.backends, self.metrics)
        
        # All strategies should be called
        self.mock_content.select_backend.assert_called_once()
        self.mock_cost.select_backend.assert_called_once()
        self.mock_geo.select_backend.assert_called_once()
        self.mock_perf.select_backend.assert_called_once()
        
        # IPFS should win due to highest weighted score
        self.assertEqual(decision.backend, "IPFS")
        
        # Score should be a weighted combination
        # 0.9*0.4 (content) + 0.7*0.3 (S3 alternative from cost) + 0.6*0.2 (IPFS alternative from geo) + 0.85*0.1 (perf)
        # = 0.36 + 0.21 + 0.12 + 0.085 = 0.775
        self.assertAlmostEqual(decision.score, 0.775, places=2)
    
    def test_add_strategy(self):
        """Test adding a strategy to the composite router."""
        # Create a new mock strategy
        mock_new = MagicMock()
        mock_new.select_backend.side_effect = lambda c, b, m: RoutingDecision(
            backend="NEW",
            score=1.0,
            reason="New strategy decision",
            metrics=RouteMetrics(),
            alternatives=[],
            context=c
        )
        
        # Add the strategy
        self.router.add_strategy("new", mock_new, 0.5)
        
        # Check weights are normalized
        self.assertEqual(sum(weight for _, weight in self.router.strategies.values()), 1.0)
        
        # Select a backend with the new strategy
        context = RoutingContext(operation=OperationType.READ)
        decision = self.router.select_backend(context, self.backends, self.metrics)
        
        # New strategy should be called
        mock_new.select_backend.assert_called_once()
        
        # Decision should consider the new strategy
        self.assertIsNotNone(decision)
    
    def test_remove_strategy(self):
        """Test removing a strategy from the composite router."""
        # Remove the content strategy
        self.router.remove_strategy("content")
        
        # Check it was removed
        self.assertNotIn("content", self.router.strategies)
        
        # Check weights are normalized
        self.assertEqual(sum(weight for _, weight in self.router.strategies.values()), 1.0)
        
        # Select a backend without the content strategy
        context = RoutingContext(operation=OperationType.READ)
        decision = self.router.select_backend(context, self.backends, self.metrics)
        
        # Content strategy should not be called
        self.mock_content.select_backend.assert_not_called()
        
        # Decision should still be valid
        self.assertIsNotNone(decision)
    
    def test_adjust_weight(self):
        """Test adjusting the weight of a strategy."""
        # Adjust the weight of the content strategy
        self.router.adjust_weight("content", 0.8)
        
        # Check weights are normalized
        self.assertEqual(sum(weight for _, weight in self.router.strategies.values()), 1.0)
        
        # Get the weights
        weights = self.router.get_weights()
        
        # Content weight should be higher than before
        self.assertGreater(weights["content"], weights["cost"])
        self.assertGreater(weights["content"], weights["geo"])
        self.assertGreater(weights["content"], weights["perf"])
    
    def test_strategy_error_handling(self):
        """Test error handling when a strategy fails."""
        # Make the content strategy raise an exception
        self.mock_content.select_backend.side_effect = Exception("Strategy failed")
        
        # Select a backend
        context = RoutingContext(operation=OperationType.READ)
        decision = self.router.select_backend(context, self.backends, self.metrics)
        
        # Should still get a valid decision despite the error
        self.assertIsNotNone(decision)
        
        # Other strategies should still be called
        self.mock_cost.select_backend.assert_called_once()
        self.mock_geo.select_backend.assert_called_once()
        self.mock_perf.select_backend.assert_called_once()


if __name__ == "__main__":
    unittest.main()