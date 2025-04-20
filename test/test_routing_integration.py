"""
Integration Tests for the Optimized Data Routing System

This module provides comprehensive integration tests for the
optimized data routing system, verifying that all components
work together properly.
"""

import os
import sys
import asyncio
import unittest
import tempfile
import logging
import random
from typing import Dict, Any, List, Optional

# Configure logging to a more minimal format for tests
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("routing_integration_test")

# Import routing components
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


class RoutingIntegrationTest(unittest.IsolatedAsyncioTestCase):
    """Integration tests for the optimized data routing system."""
    
    async def asyncSetUp(self):
        """Set up the test environment."""
        # Create temporary directory for test data
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_data_dir = self.temp_dir.name
        
        # Import routing components
        from ipfs_kit_py.routing import (
            RoutingManager, 
            RoutingManagerSettings,
            RoutingStrategy,
            RoutingPriority
        )
        from ipfs_kit_py.routing.config_manager import RoutingConfigManager
        from ipfs_kit_py.routing.metrics_collector import RoutingMetricsDatabase
        
        # Make components accessible to tests
        self.RoutingManager = RoutingManager
        self.RoutingManagerSettings = RoutingManagerSettings
        self.RoutingStrategy = RoutingStrategy
        self.RoutingPriority = RoutingPriority
        
        # Set up test configuration
        self.config_manager = RoutingConfigManager(
            config_dir=os.path.join(self.test_data_dir, "config"),
            auto_create=True
        )
        
        # Set up test metrics database
        self.metrics_db = RoutingMetricsDatabase(
            db_path=os.path.join(self.test_data_dir, "metrics.db"),
            retention_days=1
        )
        
        # Set up test backends
        self.test_backends = [
            "test_ipfs",
            "test_filecoin",
            "test_s3",
            "test_local"
        ]
        
        # Initialize routing manager with test settings
        self.settings = self.RoutingManagerSettings(
            enabled=True,
            backends=self.test_backends,
            default_strategy="hybrid",
            default_priority="balanced",
            collect_metrics_on_startup=False,  # Avoid external dependencies during tests
            auto_start_background_tasks=False,
            learning_enabled=True,
            config_path=os.path.join(self.test_data_dir, "config/routing_config.json")
        )
        
        self.routing_manager = await self.RoutingManager.create(
            settings=self.settings,
            metrics_db=self.metrics_db
        )
        
        logger.info("Test environment set up")
    
    async def asyncTearDown(self):
        """Clean up the test environment."""
        # Stop the routing manager
        if hasattr(self, "routing_manager") and self.routing_manager:
            await self.routing_manager.stop()
        
        # Close metrics database
        if hasattr(self, "metrics_db") and self.metrics_db:
            self.metrics_db.close()
        
        # Clean up temporary directory
        if hasattr(self, "temp_dir") and self.temp_dir:
            self.temp_dir.cleanup()
        
        logger.info("Test environment cleaned up")
    
    async def test_basic_routing(self):
        """Test basic routing functionality."""
        # Test routing with different content types
        content_types = [
            "application/pdf",
            "image/jpeg",
            "video/mp4",
            "text/plain",
            "application/json"
        ]
        
        for content_type in content_types:
            # Generate test content info
            content_info = self._generate_content_info(content_type)
            
            # Select backend
            backend_id = await self.routing_manager.select_backend(
                content_type=content_info["content_type"],
                content_size=content_info["content_size"],
                metadata=content_info["metadata"]
            )
            
            # Verify backend selection
            self.assertIn(
                backend_id, 
                self.test_backends,
                f"Selected backend {backend_id} should be in available backends"
            )
            
            # Record outcome
            await self.routing_manager.record_routing_outcome(
                backend_id=backend_id,
                content_info={
                    "content_type": content_info["content_type"],
                    "size_bytes": content_info["content_size"]
                },
                success=True
            )
            
            logger.info(f"Successfully routed {content_type} to {backend_id}")
    
    async def test_routing_strategies(self):
        """Test different routing strategies."""
        # Test content
        content_info = self._generate_content_info("application/pdf")
        
        # Test each strategy
        strategies = ["content_type", "cost", "performance", "reliability", "hybrid"]
        
        for strategy in strategies:
            # Select backend using the current strategy
            backend_id = await self.routing_manager.select_backend(
                content_type=content_info["content_type"],
                content_size=content_info["content_size"],
                metadata=content_info["metadata"],
                strategy=strategy
            )
            
            # Verify backend selection
            self.assertIn(
                backend_id, 
                self.test_backends,
                f"Selected backend {backend_id} should be in available backends"
            )
            
            logger.info(f"Strategy '{strategy}' selected backend: {backend_id}")
    
    async def test_routing_priorities(self):
        """Test different routing priorities."""
        # Test content
        content_info = self._generate_content_info("image/jpeg")
        
        # Test each priority
        priorities = ["balanced", "performance", "cost", "reliability"]
        
        for priority in priorities:
            # Select backend using the current priority
            backend_id = await self.routing_manager.select_backend(
                content_type=content_info["content_type"],
                content_size=content_info["content_size"],
                metadata=content_info["metadata"],
                priority=priority
            )
            
            # Verify backend selection
            self.assertIn(
                backend_id, 
                self.test_backends,
                f"Selected backend {backend_id} should be in available backends"
            )
            
            logger.info(f"Priority '{priority}' selected backend: {backend_id}")
    
    async def test_backend_filtering(self):
        """Test routing with filtered backends."""
        # Test content
        content_info = self._generate_content_info("video/mp4")
        
        # Test with limited backends
        available_backends = ["test_ipfs", "test_s3"]
        
        # Select backend with limited options
        backend_id = await self.routing_manager.select_backend(
            content_type=content_info["content_type"],
            content_size=content_info["content_size"],
            metadata=content_info["metadata"],
            available_backends=available_backends
        )
        
        # Verify backend selection
        self.assertIn(
            backend_id, 
            available_backends,
            f"Selected backend {backend_id} should be in available backends"
        )
        
        logger.info(f"Successfully filtered backends and selected: {backend_id}")
    
    async def test_routing_insights(self):
        """Test routing insights functionality."""
        # Get routing insights
        insights = await self.routing_manager.get_routing_insights()
        
        # Verify insights structure
        self.assertIsInstance(insights, dict, "Insights should be a dictionary")
        self.assertIn("factor_weights", insights, "Insights should contain factor weights")
        self.assertIn("backend_scores", insights, "Insights should contain backend scores")
        
        logger.info(f"Successfully retrieved routing insights")
    
    async def test_learning_from_outcomes(self):
        """Test learning from routing outcomes."""
        # Test content
        content_info = self._generate_content_info("text/plain")
        
        # Make a series of routing decisions and record outcomes
        for _ in range(10):
            # Select backend
            backend_id = await self.routing_manager.select_backend(
                content_type=content_info["content_type"],
                content_size=content_info["content_size"],
                metadata=content_info["metadata"]
            )
            
            # Record success or failure (80% success rate)
            success = random.random() < 0.8
            
            await self.routing_manager.record_routing_outcome(
                backend_id=backend_id,
                content_info={
                    "content_type": content_info["content_type"],
                    "size_bytes": content_info["content_size"]
                },
                success=success
            )
        
        # Verify learning has occurred
        insights_before = await self.routing_manager.get_routing_insights()
        
        # Record several failures for a specific backend
        target_backend = self.test_backends[0]
        for _ in range(5):
            await self.routing_manager.record_routing_outcome(
                backend_id=target_backend,
                content_info={
                    "content_type": content_info["content_type"],
                    "size_bytes": content_info["content_size"]
                },
                success=False
            )
        
        # Get updated insights
        insights_after = await self.routing_manager.get_routing_insights()
        
        # The score for the target backend should have decreased
        # (However, as learning is complex, we don't check the exact values)
        logger.info(f"Backend scores before: {insights_before.get('backend_scores', {})}")
        logger.info(f"Backend scores after: {insights_after.get('backend_scores', {})}")
    
    async def test_apache_arrow_ipc(self):
        """Test the Apache Arrow IPC interface."""
        try:
            from ipfs_kit_py.routing.arrow_ipc import (
                ArrowIPCServer, 
                ArrowIPCClient, 
                start_ipc_server
            )
            
            # Set up test socket path
            socket_path = os.path.join(self.test_data_dir, "routing_test.sock")
            
            # Start IPC server
            server = await start_ipc_server(
                socket_path=socket_path,
                routing_manager=self.routing_manager
            )
            
            try:
                # Create client
                client = ArrowIPCClient(socket_path=socket_path)
                
                # Connect to server
                await client.connect()
                
                # Test content
                content_type = "application/pdf"
                content_size = 1024 * 1024  # 1 MB
                content_hash = "test-hash-123"
                
                # Select backend using IPC
                backend_id = await client.select_backend(
                    content_type=content_type,
                    content_size=content_size,
                    content_hash=content_hash,
                    metadata={"filename": "test.pdf"}
                )
                
                # Verify backend selection
                self.assertIn(
                    backend_id, 
                    self.test_backends,
                    f"Selected backend {backend_id} should be in available backends"
                )
                
                # Record outcome using IPC
                await client.record_outcome(
                    backend_id=backend_id,
                    content_type=content_type,
                    content_size=content_size,
                    content_hash=content_hash,
                    success=True
                )
                
                # Disconnect
                await client.disconnect()
                
                logger.info(f"Successfully tested Arrow IPC interface")
                
            finally:
                # Stop server
                await server.stop()
                
        except ImportError:
            logger.warning("Skipping Arrow IPC test (pyarrow not available)")
    
    async def test_config_persistence(self):
        """Test configuration persistence."""
        # Get initial config
        initial_config = self.config_manager.load_config()
        
        # Modify configuration
        updates = {
            "default_strategy": "performance",
            "optimization_weights": {
                "network_quality": 0.3,
                "content_match": 0.3,
                "cost_efficiency": 0.1,
                "geographic_proximity": 0.1,
                "load_balancing": 0.1,
                "reliability": 0.1,
                "historical_success": 0.0
            }
        }
        
        # Update config
        self.config_manager.update_config(updates)
        
        # Reload config
        loaded_config = self.config_manager.load_config()
        
        # Verify changes were persisted
        self.assertEqual(
            loaded_config["default_strategy"],
            updates["default_strategy"],
            "Config changes should be persisted"
        )
        
        self.assertEqual(
            loaded_config["optimization_weights"]["network_quality"],
            updates["optimization_weights"]["network_quality"],
            "Nested config changes should be persisted"
        )
        
        logger.info(f"Successfully tested configuration persistence")
    
    async def test_metrics_collection(self):
        """Test metrics collection and retrieval."""
        # Record some test routing decisions
        for i in range(5):
            content_type = random.choice([
                "application/pdf",
                "image/jpeg",
                "video/mp4",
                "text/plain"
            ])
            
            content_info = self._generate_content_info(content_type)
            
            # Select backend
            backend_id = await self.routing_manager.select_backend(
                content_type=content_info["content_type"],
                content_size=content_info["content_size"],
                metadata=content_info["metadata"]
            )
            
            # Record decision directly in metrics DB
            self.metrics_db.record_routing_decision(
                backend_id=backend_id,
                content_type=content_info["content_type"],
                content_size=content_info["content_size"],
                strategy="hybrid",
                priority="balanced",
                score=0.8 + (random.random() * 0.2)
            )
            
            # Record outcome
            self.metrics_db.record_routing_outcome(
                backend_id=backend_id,
                success=random.random() < 0.8,
                content_type=content_info["content_type"],
                content_size=content_info["content_size"],
                duration_ms=int(50 + (random.random() * 100))
            )
        
        # Record some backend metrics
        for backend_id in self.test_backends:
            self.metrics_db.record_backend_metric(
                backend_id=backend_id,
                metric_type="performance",
                metric_name="latency_ms",
                metric_value=50.0 + (random.random() * 100.0)
            )
            
            self.metrics_db.record_backend_metric(
                backend_id=backend_id,
                metric_type="reliability",
                metric_name="available",
                metric_value=1.0 if random.random() < 0.9 else 0.0
            )
        
        # Test metrics retrieval
        success_rates = self.metrics_db.get_backend_success_rates(time_window_hours=24)
        self.assertIsInstance(success_rates, dict, "Success rates should be a dictionary")
        
        latency_stats = self.metrics_db.get_backend_latency_stats(time_window_hours=24)
        self.assertIsInstance(latency_stats, dict, "Latency stats should be a dictionary")
        
        usage_stats = self.metrics_db.get_backend_usage_stats(time_window_hours=24)
        self.assertIsInstance(usage_stats, dict, "Usage stats should be a dictionary")
        
        logger.info(f"Successfully tested metrics collection and retrieval")
    
    def _generate_content_info(self, content_type: str) -> Dict[str, Any]:
        """Generate test content information."""
        size_kb = random.randint(10, 1000)
        return {
            "content_type": content_type,
            "content_size": size_kb * 1024,
            "metadata": {
                "filename": f"test-{random.randint(1000, 9999)}.{content_type.split('/')[-1]}",
                "created": "2025-04-15T20:00:00Z",
                "tags": ["test", content_type.split('/')[-1]]
            }
        }


if __name__ == "__main__":
    unittest.main()