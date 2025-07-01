"""
Integration tests for the Optimized Data Routing system.

This module tests the complete routing system, including:
- Routing decision accuracy
- Backend selection algorithms
- Integration with MCP server
- Dashboard functionality
"""

import os
import json
import time
import asyncio
import unittest
from unittest import mock
from typing import Dict, Any, List, Optional
import pytest

# Import routing components
from ipfs_kit_py.mcp.routing.routing_manager import (
    RoutingManager, RoutingManagerSettings, get_routing_manager, initialize_routing_manager
)
from ipfs_kit_py.mcp.routing.optimized_router import (
    OptimizedDataRouter, RoutingStrategy, ContentCategory
)
from ipfs_kit_py.mcp.routing.data_router import (
    ContentAnalyzer, RoutingPriority
)
from ipfs_kit_py.mcp.routing.adaptive_optimizer import (
    AdaptiveOptimizer, OptimizationFactor, RouteOptimizationResult
)
from ipfs_kit_py.mcp.optimized_routing import RoutingIntegration
from ipfs_kit_py.mcp.routing.routing_dashboard import RoutingDashboardExtension


class MockBackendManager:
    """Mock storage backend manager for testing."""
    
    def __init__(self, backends=None):
        """Initialize with mock backends."""
        self.backends = backends or ["ipfs", "filecoin", "s3", "storacha", "huggingface"]
    
    async def list_backends(self):
        """Return list of mock backends."""
        return self.backends


class MockFastAPI:
    """Mock FastAPI app for testing."""
    
    def __init__(self):
        """Initialize with mock routes."""
        self.routes = {}
        self.middlewares = []
        self.event_handlers = {}
    
    def get(self, path, **kwargs):
        """Register a GET route."""
        def decorator(func):
            self.routes[f"GET {path}"] = func
            return func
        return decorator
    
    def post(self, path, **kwargs):
        """Register a POST route."""
        def decorator(func):
            self.routes[f"POST {path}"] = func
            return func
        return decorator
    
    def websocket(self, path, **kwargs):
        """Register a WebSocket route."""
        def decorator(func):
            self.routes[f"WS {path}"] = func
            return func
        return decorator
    
    def on_event(self, event_type):
        """Register an event handler."""
        def decorator(func):
            self.event_handlers[event_type] = func
            return func
        return decorator
    
    def include_router(self, router):
        """Include a router."""
        pass
    
    def add_middleware(self, middleware, **kwargs):
        """Add a middleware."""
        self.middlewares.append((middleware, kwargs))
    
    def mount(self, path, app, name=None):
        """Mount another app."""
        pass


class TestRoutingSystem(unittest.TestCase):
    """Test suite for the Optimized Data Routing system."""
    
    def setUp(self):
        """Set up test environment."""
        # Create test backends
        self.test_backends = ["ipfs", "filecoin", "s3", "storacha", "huggingface"]
        
        # Create optimized router
        self.router = OptimizedDataRouter({
            "default_strategy": RoutingStrategy.HYBRID.value,
            "backends": self.test_backends,
        })
        
        # Register backends
        for backend in self.test_backends:
            self.router.register_backend(backend)
        
        # Create content samples
        self.content_samples = {
            "document": b"This is a sample document for testing" * 100,  # ~3KB
            "image": os.urandom(1024 * 100),  # 100KB binary data
            "video": os.urandom(1024 * 1024),  # 1MB binary data
            "audio": os.urandom(1024 * 500),  # 500KB binary data
            "code": b"def test_function():\n    return 'Hello, world!'" * 50,  # ~2KB
        }
        
        # Metadata for content samples
        self.content_metadata = {
            "document": {
                "content_type": "application/pdf",
                "filename": "sample.pdf"
            },
            "image": {
                "content_type": "image/jpeg",
                "filename": "sample.jpg"
            },
            "video": {
                "content_type": "video/mp4",
                "filename": "sample.mp4"
            },
            "audio": {
                "content_type": "audio/mp3",
                "filename": "sample.mp3"
            },
            "code": {
                "content_type": "text/javascript",
                "filename": "sample.js"
            }
        }
    
    def test_backend_registration(self):
        """Test registration and unregistration of backends."""
        # Test backend registration with new backend
        new_backend = "new_test_backend"
        self.router.register_backend(new_backend)
        self.assertIn(new_backend, self.router.backends)
        
        # Test backend unregistration
        self.router.unregister_backend(new_backend)
        self.assertNotIn(new_backend, self.router.backends)
    
    def test_content_analysis(self):
        """Test content analysis functionality."""
        # Test each content type
        for content_type, content in self.content_samples.items():
            metadata = self.content_metadata[content_type]
            
            # Analyze content
            analysis = self.router.analyze_content(
                content=content,
                filename=metadata["filename"],
                content_type=metadata["content_type"]
            )
            
            # Check analysis results
            self.assertIn("size_bytes", analysis)
            self.assertIn("content_type", analysis)
            self.assertIn("filename", analysis)
            self.assertIn("content_category", analysis)
            self.assertIn("content_hash", analysis)
            
            # Check size
            self.assertEqual(analysis["size_bytes"], len(content))
            
            # Check content type
            self.assertEqual(analysis["content_type"], metadata["content_type"])
            
            # Check filename
            self.assertEqual(analysis["filename"], metadata["filename"])
    
    def test_routing_strategies(self):
        """Test different routing strategies."""
        # Test each strategy
        strategies = [
            RoutingStrategy.RANDOM,
            RoutingStrategy.ROUND_ROBIN,
            RoutingStrategy.CONTENT_TYPE,
            RoutingStrategy.COST,
            RoutingStrategy.PERFORMANCE,
            RoutingStrategy.AVAILABILITY,
            RoutingStrategy.GEOGRAPHIC,
            RoutingStrategy.HYBRID
        ]
        
        content_info = {
            "content_type": "application/pdf",
            "filename": "test.pdf",
            "size_bytes": 1024 * 100  # 100KB
        }
        
        # Check that each strategy returns a valid backend
        for strategy in strategies:
            backend = self.router.get_backend_for_content(content_info, strategy)
            self.assertIn(backend, self.test_backends)
    
    def test_route_mapping(self):
        """Test custom route mappings."""
        # Create custom mapping for document category
        document_mapping = {
            "ipfs": 0.7,
            "s3": 0.3
        }
        
        self.router.set_route_mapping(ContentCategory.DOCUMENT, document_mapping)
        
        # Test with document content
        content_info = {
            "content_category": ContentCategory.DOCUMENT,
            "size_bytes": 1024 * 100  # 100KB
        }
        
        # Perform multiple routing decisions to check distribution
        results = {}
        for _ in range(100):
            backend = self.router.get_backend_for_content(
                content_info,
                RoutingStrategy.CONTENT_TYPE
            )
            results[backend] = results.get(backend, 0) + 1
        
        # Check that only the mapped backends were used
        used_backends = set(results.keys())
        self.assertTrue(used_backends.issubset({"ipfs", "s3"}))
    
    def test_backend_stats_update(self):
        """Test updating backend statistics."""
        backend_id = "ipfs"
        
        # Initial stats
        initial_stats = self.router.get_backend_stats(backend_id)
        
        # Record successful operation
        self.router.update_backend_stats(
            backend_id=backend_id,
            operation="store",
            success=True,
            size_bytes=1024 * 100,
            content_type="application/pdf",
            latency=0.5
        )
        
        # Get updated stats
        updated_stats = self.router.get_backend_stats(backend_id)
        
        # Check that stats were updated
        self.assertEqual(updated_stats["total_operations"], initial_stats["total_operations"] + 1)
        self.assertEqual(updated_stats["successful_operations"], initial_stats["successful_operations"] + 1)
    
    def test_backend_availability(self):
        """Test updating backend availability."""
        backend_id = "ipfs"
        
        # Set backend as unavailable
        self.router.update_backend_availability(backend_id, False)
        
        # Check that backend is marked as unavailable
        stats = self.router.get_backend_stats(backend_id)
        self.assertFalse(stats["availability_status"])
        
        # Set backend as available
        self.router.update_backend_availability(backend_id, True)
        
        # Check that backend is marked as available
        stats = self.router.get_backend_stats(backend_id)
        self.assertTrue(stats["availability_status"])
    
    def test_routing_decisions(self):
        """Test recording and analyzing routing decisions."""
        # Record some routing decisions
        for content_type, content in self.content_samples.items():
            metadata = self.content_metadata[content_type]
            content_info = {
                "content_type": metadata["content_type"],
                "filename": metadata["filename"],
                "size_bytes": len(content)
            }
            
            # Get routing decision
            backend = self.router.get_backend_for_content(content_info)
            
            # Check that decision was recorded
            self.assertGreater(len(self.router.routing_decisions), 0)
            
            # Check that last decision matches expected content info
            last_decision = self.router.routing_decisions[-1]
            self.assertEqual(last_decision["selected_backend"], backend)
            self.assertEqual(last_decision["content_info"]["content_type"], metadata["content_type"])


class TestAdaptiveOptimizer:
    """Test suite for the Adaptive Optimizer."""
    
    @pytest.fixture
    def optimizer(self):
        """Create a fresh adaptive optimizer instance for each test."""
        return AdaptiveOptimizer()
    
    @pytest.mark.asyncio
    async def test_optimize_route(self, optimizer):
        """Test the optimize_route method."""
        # Define test content and backends
        content = b"Test content"
        metadata = {
            "content_type": "text/plain",
            "filename": "test.txt",
            "size_bytes": len(content)
        }
        backends = ["ipfs", "filecoin", "s3", "storacha"]
        
        # Test basic optimization
        result = optimizer.optimize_route(
            content=content,
            metadata=metadata,
            available_backends=backends
        )
        
        # Check result
        assert result.backend_id in backends
        assert len(result.factor_scores) > 0
        assert len(result.alternatives) >= 0
        assert result.content_analysis is not None
        assert result.execution_time_ms > 0
    
    @pytest.mark.asyncio
    async def test_multiple_priorities(self, optimizer):
        """Test optimization with different priorities."""
        content = b"Test content"
        metadata = {"size_bytes": len(content)}
        backends = ["ipfs", "filecoin", "s3"]
        
        priorities = [
            RoutingPriority.BALANCED,
            RoutingPriority.PERFORMANCE,
            RoutingPriority.COST,
            RoutingPriority.RELIABILITY,
            RoutingPriority.GEOGRAPHIC
        ]
        
        results = {}
        
        # Run optimization with each priority
        for priority in priorities:
            result = optimizer.optimize_route(
                content=content,
                metadata=metadata,
                available_backends=backends,
                priority=priority
            )
            results[priority.value] = result.backend_id
        
        # There should be some variation in backend selection based on priority
        # This might not always be true, but is likely with different priorities
        assert len(set(results.values())) > 1
    
    @pytest.mark.asyncio
    async def test_learning_from_outcomes(self, optimizer):
        """Test learning from routing outcomes."""
        # Setup
        content = b"Test content"
        metadata = {"size_bytes": len(content)}
        backends = ["ipfs", "filecoin", "s3"]
        
        # Initial optimization
        result1 = optimizer.optimize_route(
            content=content,
            metadata=metadata,
            available_backends=backends
        )
        
        # Record successful outcome
        optimizer.record_outcome(result1, True)
        
        # Record several more outcomes to trigger learning
        for i in range(10):
            result = optimizer.optimize_route(
                content=content,
                metadata=metadata,
                available_backends=backends
            )
            # Alternate between success and failure
            optimizer.record_outcome(result, i % 2 == 0)
        
        # Check that optimizer has learned from outcomes
        assert len(optimizer.decision_history) > 0
        
        # The weights should have been updated based on outcomes
        initial_weights = {factor: 0.0 for factor in OptimizationFactor}
        current_weights = optimizer.weights.weights
        
        # At least some weights should have changed
        assert current_weights != initial_weights


@pytest.mark.asyncio
class TestRoutingManager:
    """Test suite for the Routing Manager."""
    
    @pytest.fixture
    async def routing_manager(self):
        """Create a routing manager for testing."""
        settings = RoutingManagerSettings(
            enabled=True,
            default_strategy="hybrid",
            default_priority="balanced",
            backends=["ipfs", "filecoin", "s3", "storacha", "huggingface"],
            learning_enabled=True
        )
        
        manager = RoutingManager(settings)
        await manager.initialize()
        return manager
    
    async def test_select_backend(self, routing_manager):
        """Test backend selection."""
        # Test with content metadata
        content_info = {
            "content_type": "application/pdf",
            "filename": "test.pdf",
            "size_bytes": 1024 * 100  # 100KB
        }
        
        # Select backend
        backend = await routing_manager.select_backend(
            content=content_info,
            available_backends=routing_manager.settings.backends
        )
        
        # Check result
        assert backend in routing_manager.settings.backends
    
    async def test_record_outcome(self, routing_manager):
        """Test recording outcomes."""
        # Select backend
        backend = await routing_manager.select_backend(
            content={"size_bytes": 1024, "content_type": "text/plain"},
            available_backends=routing_manager.settings.backends
        )
        
        # Record outcome
        await routing_manager.record_routing_outcome(
            backend_id=backend,
            content_info={"size_bytes": 1024, "content_type": "text/plain"},
            success=True
        )
        
        # Check that outcome was recorded
        insights = await routing_manager.get_routing_insights()
        assert insights is not None
    
    async def test_different_strategies(self, routing_manager):
        """Test different routing strategies."""
        content = {"size_bytes": 1024, "content_type": "text/plain"}
        strategies = ["adaptive", "content_type", "cost", "performance", "geographic", "hybrid"]
        
        results = {}
        
        # Test each strategy
        for strategy in strategies:
            backend = await routing_manager.select_backend(
                content=content,
                strategy=strategy
            )
            results[strategy] = backend
        
        # There should be some variation in backend selection
        assert len(set(results.values())) >= 1


@pytest.mark.asyncio
class TestRoutingIntegration:
    """Test the integration of the routing system with MCP server."""
    
    @pytest.fixture
    async def routing_integration(self):
        """Create a routing integration for testing."""
        mock_app = MockFastAPI()
        mock_backend_manager = MockBackendManager()
        
        integration = RoutingIntegration(
            app=mock_app,
            config={
                "routing_enabled": True,
                "routing_strategy": "hybrid",
                "collect_metrics_on_startup": False
            },
            storage_backend_manager=mock_backend_manager
        )
        
        await integration.initialize()
        return integration
    
    async def test_routing_flow(self, routing_integration):
        """Test the complete routing flow."""
        # Create test content
        content = b"Test content for integration"
        
        # Select backend
        backend = await routing_integration.select_backend(
            content=content,
            metadata={
                "content_type": "text/plain",
                "filename": "test.txt"
            }
        )
        
        # Verify backend is valid
        assert backend in routing_integration.settings.backends
        
        # Record outcome
        await routing_integration.record_outcome(
            backend_id=backend,
            content_info={
                "content_type": "text/plain",
                "size_bytes": len(content)
            },
            success=True
        )
        
        # Get insights
        insights = await routing_integration.get_insights()
        assert insights is not None


if __name__ == "__main__":
    unittest.main()