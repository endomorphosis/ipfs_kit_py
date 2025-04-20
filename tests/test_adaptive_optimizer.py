"""
Test suite for the Adaptive Routing Optimizer.

This module contains tests for the adaptive optimization system used in MCP routing.
"""

import os
import json
import unittest
import pytest
from unittest.mock import patch, MagicMock, Mock
import tempfile
import asyncio
import logging
from typing import Dict, List, Any, Optional

from ipfs_kit_py.mcp.routing.adaptive_optimizer import (
    AdaptiveOptimizer, create_adaptive_optimizer, RouteOptimizationResult,
    OptimizationFactor, AdaptiveWeights, AccessPattern, UsagePattern
)
from ipfs_kit_py.mcp.routing.data_router import ContentCategory, RoutingPriority, RoutingStrategy
from ipfs_kit_py.mcp.routing.bandwidth_aware_router import (
    NetworkQualityLevel, NetworkMetricType, NetworkAnalyzer, 
    MetricSample, BackendNetworkMetrics
)


class TestAdaptiveWeights(unittest.TestCase):
    """Tests for the AdaptiveWeights class."""
    
    def test_initialization(self):
        """Test that weights initialize correctly."""
        weights = AdaptiveWeights()
        
        # Check that all factors have weights
        for factor in OptimizationFactor:
            self.assertIn(factor, weights.weights)
            
        # Check that weights sum to 1.0
        self.assertAlmostEqual(sum(weights.weights.values()), 1.0, places=5)
    
    def test_get_weight(self):
        """Test getting weights for factors."""
        weights = AdaptiveWeights()
        
        # Check each factor
        for factor in OptimizationFactor:
            weight = weights.get_weight(factor)
            self.assertGreaterEqual(weight, 0.0)
            self.assertLessEqual(weight, 1.0)
    
    def test_update_weights(self):
        """Test updating weights based on outcomes."""
        weights = AdaptiveWeights()
        
        # Save initial weights
        initial_weights = weights.weights.copy()
        
        # Update weights with success for some factors
        success_factors = {
            OptimizationFactor.NETWORK_QUALITY: True,
            OptimizationFactor.CONTENT_MATCH: False,
            OptimizationFactor.COST_EFFICIENCY: True
        }
        
        # Make the same update multiple times to have enough data
        for _ in range(20):
            weights.update_weights(success_factors)
        
        # Verify weights still sum to 1.0
        self.assertAlmostEqual(sum(weights.weights.values()), 1.0, places=5)
        
        # Success factors should have higher weights than initially
        self.assertGreater(
            weights.weights[OptimizationFactor.NETWORK_QUALITY], 
            initial_weights[OptimizationFactor.NETWORK_QUALITY]
        )
        
        # Failure factors should have lower weights than initially
        self.assertLess(
            weights.weights[OptimizationFactor.CONTENT_MATCH], 
            initial_weights[OptimizationFactor.CONTENT_MATCH]
        )
    
    def test_adjust_for_priority(self):
        """Test adjusting weights based on priorities."""
        # Test each priority
        for priority in RoutingPriority:
            weights = AdaptiveWeights()
            initial_weights = weights.weights.copy()
            
            # Adjust weights for this priority
            weights.adjust_for_priority(priority)
            
            # Check weights still sum to 1.0
            self.assertAlmostEqual(sum(weights.weights.values()), 1.0, places=5)
            
            # Check that weights changed
            self.assertNotEqual(weights.weights, initial_weights)
            
            # Check specific changes based on priority
            if priority == RoutingPriority.PERFORMANCE:
                self.assertGreater(
                    weights.weights[OptimizationFactor.NETWORK_QUALITY],
                    initial_weights[OptimizationFactor.NETWORK_QUALITY]
                )
            elif priority == RoutingPriority.COST:
                self.assertGreater(
                    weights.weights[OptimizationFactor.COST_EFFICIENCY],
                    initial_weights[OptimizationFactor.COST_EFFICIENCY]
                )


class TestAccessPattern(unittest.TestCase):
    """Tests for the AccessPattern class."""
    
    def test_record_access(self):
        """Test recording content access."""
        patterns = AccessPattern()
        
        # Record successful access
        patterns.record_access(
            content_category=ContentCategory.SMALL_FILE,
            size_bytes=1024,
            backend_id="ipfs",
            success=True
        )
        
        # Check that access was recorded
        self.assertEqual(patterns.content_type_access[ContentCategory.SMALL_FILE], 1)
        self.assertEqual(patterns.backend_success["ipfs"][ContentCategory.SMALL_FILE], 1)
        self.assertEqual(patterns.backend_failure["ipfs"][ContentCategory.SMALL_FILE], 0)
        
        # Record failed access
        patterns.record_access(
            content_category=ContentCategory.SMALL_FILE,
            size_bytes=2048,
            backend_id="ipfs",
            success=False
        )
        
        # Check updated counts
        self.assertEqual(patterns.content_type_access[ContentCategory.SMALL_FILE], 2)
        self.assertEqual(patterns.backend_success["ipfs"][ContentCategory.SMALL_FILE], 1)
        self.assertEqual(patterns.backend_failure["ipfs"][ContentCategory.SMALL_FILE], 1)
    
    def test_get_success_rate(self):
        """Test getting success rate."""
        patterns = AccessPattern()
        
        # Record accesses with different success
        for i in range(10):
            patterns.record_access(
                content_category=ContentCategory.MEDIA,
                size_bytes=1024 * 1024,
                backend_id="s3",
                success=i < 7  # 7 successes, 3 failures
            )
        
        # Check success rate
        self.assertAlmostEqual(
            patterns.get_success_rate("s3", ContentCategory.MEDIA),
            0.7,  # 7/10 = 0.7
            places=5
        )
        
        # Check success rate for unknown combo
        self.assertEqual(
            patterns.get_success_rate("unknown", ContentCategory.MEDIA),
            0.5  # Default when no data
        )
    
    def test_get_preferred_backends(self):
        """Test getting preferred backends."""
        patterns = AccessPattern()
        
        # Record accesses for multiple backends
        backends = ["ipfs", "s3", "filecoin"]
        success_rates = [0.9, 0.6, 0.3]  # 90%, 60%, 30% success
        
        for i, backend_id in enumerate(backends):
            success_count = int(10 * success_rates[i])
            
            # Add successes
            for _ in range(success_count):
                patterns.record_access(
                    content_category=ContentCategory.DOCUMENT,
                    size_bytes=5000,
                    backend_id=backend_id,
                    success=True
                )
            
            # Add failures
            for _ in range(10 - success_count):
                patterns.record_access(
                    content_category=ContentCategory.DOCUMENT,
                    size_bytes=5000,
                    backend_id=backend_id,
                    success=False
                )
        
        # Get preferred backends with min success rate 0.8
        preferred = patterns.get_preferred_backends(
            ContentCategory.DOCUMENT,
            min_success_rate=0.8
        )
        
        # Should only include ipfs (90% success)
        self.assertEqual(len(preferred), 1)
        self.assertIn("ipfs", preferred)
        
        # Get preferred backends with min success rate 0.5
        preferred = patterns.get_preferred_backends(
            ContentCategory.DOCUMENT,
            min_success_rate=0.5
        )
        
        # Should include ipfs and s3 (90% and 60% success)
        self.assertEqual(len(preferred), 2)
        self.assertIn("ipfs", preferred)
        self.assertIn("s3", preferred)
    
    def test_is_size_appropriate(self):
        """Test size appropriateness check."""
        patterns = AccessPattern()
        
        # Record accesses for a backend with consistent size
        for _ in range(10):
            patterns.record_access(
                content_category=ContentCategory.SMALL_FILE,
                size_bytes=1000,  # Consistently small files
                backend_id="ipfs",
                success=True
            )
        
        # Check if similar size is appropriate
        self.assertTrue(patterns.is_size_appropriate("ipfs", 1100))
        
        # Check if very different size is not appropriate
        self.assertFalse(patterns.is_size_appropriate("ipfs", 50000))
        
        # Check if new backend is always appropriate
        self.assertTrue(patterns.is_size_appropriate("new_backend", 50000))


class TestUsagePattern(unittest.TestCase):
    """Tests for the UsagePattern class."""
    
    def test_record_usage(self):
        """Test recording backend usage."""
        usage = UsagePattern(time_window_minutes=5)
        
        # Record usage for multiple backends
        usage.record_usage("ipfs", 1000)
        usage.record_usage("ipfs", 2000)
        usage.record_usage("s3", 5000)
        
        # Check usage stats
        ipfs_usage = usage.get_usage("ipfs")
        s3_usage = usage.get_usage("s3")
        
        self.assertEqual(ipfs_usage[0], 3000)  # 1000 + 2000
        self.assertEqual(ipfs_usage[1], 2)     # 2 requests
        
        self.assertEqual(s3_usage[0], 5000)    # 5000
        self.assertEqual(s3_usage[1], 1)       # 1 request
    
    def test_get_load_distribution(self):
        """Test getting load distribution."""
        usage = UsagePattern(time_window_minutes=5)
        
        # Record usage for multiple backends
        usage.record_usage("ipfs", 1000)    # 1000 bytes
        usage.record_usage("s3", 3000)      # 3000 bytes
        usage.record_usage("filecoin", 6000)  # 6000 bytes
        
        # Total: 10000 bytes
        
        # Get load distribution
        load_dist = usage.get_load_distribution()
        
        # Check distribution
        self.assertAlmostEqual(load_dist["ipfs"], 0.1, places=5)      # 1000/10000 = 0.1
        self.assertAlmostEqual(load_dist["s3"], 0.3, places=5)        # 3000/10000 = 0.3
        self.assertAlmostEqual(load_dist["filecoin"], 0.6, places=5)  # 6000/10000 = 0.6


@pytest.mark.asyncio
class TestAdaptiveOptimizer:
    """Tests for the AdaptiveOptimizer class."""
    
    @pytest.fixture
    def optimizer(self):
        """Create an optimizer for testing."""
        # Create mock NetworkAnalyzer
        network_analyzer = MagicMock(spec=NetworkAnalyzer)
        
        # Create mock metrics
        mock_metrics = MagicMock(spec=BackendNetworkMetrics)
        mock_metrics.get_performance_score.return_value = 0.8
        mock_metrics.get_overall_quality.return_value = NetworkQualityLevel.GOOD
        
        # Make NetworkAnalyzer.get_metrics return the mock metrics
        network_analyzer.get_metrics.return_value = mock_metrics
        
        # Create optimizer with mock analyzer
        optimizer = AdaptiveOptimizer(network_analyzer=network_analyzer)
        
        return optimizer
    
    async def test_optimize_route(self, optimizer):
        """Test optimizing route for content."""
        # Create sample content
        content = b"Test content"
        metadata = {
            "content_type": "text/plain",
            "filename": "test.txt"
        }
        
        # Get routing decision
        result = optimizer.optimize_route(
            content=content,
            metadata=metadata,
            available_backends=["ipfs", "filecoin", "s3"]
        )
        
        # Check result
        assert result.backend_id in ["ipfs", "filecoin", "s3"]
        assert result.overall_score > 0.0
        assert len(result.factor_scores) > 0
        assert "category" in result.content_analysis
        assert "size_bytes" in result.content_analysis
    
    async def test_record_outcome(self, optimizer):
        """Test recording outcome of routing decision."""
        # Create sample result
        result = RouteOptimizationResult("ipfs")
        result.content_analysis = {
            "category": ContentCategory.SMALL_FILE.value,
            "size_bytes": 1024
        }
        result.factor_scores = {
            OptimizationFactor.NETWORK_QUALITY: 0.9,
            OptimizationFactor.CONTENT_MATCH: 0.8,
            OptimizationFactor.COST_EFFICIENCY: 0.7
        }
        
        # Record successful outcome
        initial_weights = optimizer.weights.weights.copy()
        optimizer.record_outcome(result, True)
        
        # Check that access was recorded
        assert optimizer.access_patterns.content_type_access[ContentCategory.SMALL_FILE] == 1
        
        # Record multiple outcomes to trigger weight update
        for _ in range(20):
            optimizer.record_outcome(result, True)
        
        # Check that weights were updated
        assert optimizer.weights.weights != initial_weights
    
    async def test_generate_insights(self, optimizer):
        """Test generating insights."""
        # Record some data first
        result = RouteOptimizationResult("ipfs")
        result.content_analysis = {
            "category": ContentCategory.SMALL_FILE.value,
            "size_bytes": 1024
        }
        optimizer.record_outcome(result, True)
        
        result = RouteOptimizationResult("s3")
        result.content_analysis = {
            "category": ContentCategory.MEDIA.value,
            "size_bytes": 1024 * 1024
        }
        optimizer.record_outcome(result, True)
        
        # Generate insights
        insights = optimizer.generate_insights()
        
        # Check insights structure
        assert "optimal_backends_by_content" in insights
        assert "network_quality_ranking" in insights
        assert "load_distribution" in insights
        assert "optimization_weights" in insights


if __name__ == "__main__":
    unittest.main()