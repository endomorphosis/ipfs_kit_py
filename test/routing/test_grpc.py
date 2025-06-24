"""
Integration Tests for gRPC Routing Service

This module provides comprehensive tests for the gRPC implementation of the
optimized data routing system, covering both client and server functionality.
"""

import os
import sys
import time
import json
import uuid
import asyncio
import unittest
import tempfile
import logging
from typing import Dict, Any, List, Optional, Tuple
from unittest import mock

# Configure logging to a more minimal format for tests
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_grpc_routing")

# Add module path to system path if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    # Check if grpc is available
    import grpc
    import grpc.experimental.aio as grpc_aio
    import google.protobuf.struct_pb2 as struct_pb2
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False

# Try to import generated gRPC code
try:
    from ipfs_kit_py.routing.grpc.routing_pb2 import (
        SelectBackendRequest, SelectBackendResponse,
        RecordOutcomeRequest, RecordOutcomeResponse,
        GetInsightsRequest, GetInsightsResponse,
        StreamMetricsRequest, MetricsUpdate
    )
    from ipfs_kit_py.routing.grpc.routing_pb2_grpc import (
        RoutingServiceServicer, RoutingServiceStub,
        add_RoutingServiceServicer_to_server
    )
    GRPC_GENERATED_CODE_AVAILABLE = True
except ImportError:
    GRPC_GENERATED_CODE_AVAILABLE = False


@unittest.skipUnless(
    GRPC_AVAILABLE and GRPC_GENERATED_CODE_AVAILABLE,
    "gRPC or generated code not available. Run bin/generate_grpc_code.py first and install grpcio."
)
class TestGRPCRouting(unittest.IsolatedAsyncioTestCase):
    """Integration tests for the gRPC routing implementation."""

    async def asyncSetUp(self):
        """Set up the test environment."""
        # Create temporary directory for test data
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_data_dir = self.temp_dir.name

        # Import routing components
        from ipfs_kit_py.routing import (
            RoutingManager,
            RoutingManagerSettings
        )
        from ipfs_kit_py.routing.grpc_server import (
            RoutingServicer, run_server
        )
        from ipfs_kit_py.routing.grpc_client import (
            RoutingClient, create_client
        )

        # Store class references
        self.RoutingManager = RoutingManager
        self.RoutingManagerSettings = RoutingManagerSettings
        self.RoutingServicer = RoutingServicer
        self.run_server = run_server
        self.RoutingClient = RoutingClient
        self.create_client = create_client

        # Initialize routing manager with test settings
        self.settings = self.RoutingManagerSettings(
            enabled=True,
            backends=["test_ipfs", "test_filecoin", "test_s3", "test_local"],
            default_strategy="hybrid",
            default_priority="balanced",
            collect_metrics_on_startup=False,  # Avoid external dependencies during tests
            auto_start_background_tasks=False,
            learning_enabled=True,
            config_path=os.path.join(self.test_data_dir, "config/routing_config.json")
        )

        self.routing_manager = await self.RoutingManager.create(settings=self.settings)

        # Start the gRPC server for testing
        self.server_host = "localhost"
        self.server_port = 50099  # Use a different port than the default for tests

        # Start the server
        self.server = await self.run_server(
            host=self.server_host,
            port=self.server_port,
            routing_manager=self.routing_manager,
            max_workers=2  # Use fewer workers for tests
        )

        # Create a client
        self.client = await self.create_client(
            host=self.server_host,
            port=self.server_port,
            timeout=5.0  # Shorter timeout for tests
        )

        logger.info("Test environment set up")

    async def asyncTearDown(self):
        """Clean up the test environment."""
        # Disconnect client
        if hasattr(self, "client") and self.client:
            await self.client.disconnect()

        # Stop the server
        if hasattr(self, "server") and self.server:
            await self.server.stop()

        # Stop the routing manager
        if hasattr(self, "routing_manager") and self.routing_manager:
            await self.routing_manager.stop()

        # Clean up temporary directory
        if hasattr(self, "temp_dir") and self.temp_dir:
            self.temp_dir.cleanup()

        logger.info("Test environment cleaned up")

    def _generate_content_info(self, content_type: str = "application/pdf") -> Dict[str, Any]:
        """Generate test content information."""
        size_kb = 100
        return {
            "content_type": content_type,
            "content_size": size_kb * 1024,
            "content_hash": f"test-hash-{uuid.uuid4()}",
            "metadata": {
                "filename": f"test-{uuid.uuid4()}.{content_type.split('/')[-1]}",
                "created": "2025-04-15T20:00:00Z",
                "tags": ["test", content_type.split('/')[-1]]
            }
        }

    async def test_select_backend_basic(self):
        """Test basic backend selection via gRPC."""
        # Generate test content info
        content_info = self._generate_content_info()

        # Select backend with default settings
        result = await self.client.select_backend(
            content_type=content_info["content_type"],
            content_size=content_info["content_size"],
            content_hash=content_info["content_hash"],
            metadata=content_info["metadata"]
        )

        # Verify result structure
        self.assertIn("backend_id", result)
        self.assertIn("score", result)
        self.assertIn("factor_scores", result)
        self.assertIn("alternatives", result)
        self.assertIn("request_id", result)
        self.assertIn("timestamp", result)

        # Verify backend ID is in expected list
        self.assertIn(
            result["backend_id"],
            self.settings.backends,
            f"Selected backend {result['backend_id']} should be in available backends"
        )

        # Verify score is a float between 0 and 1
        self.assertIsInstance(result["score"], float)
        self.assertGreaterEqual(result["score"], 0.0)
        self.assertLessEqual(result["score"], 1.0)

        # Verify factor scores
        self.assertIsInstance(result["factor_scores"], dict)

        # Verify alternatives
        self.assertIsInstance(result["alternatives"], list)

        logger.info(f"Successfully selected backend: {result['backend_id']}")

    async def test_select_backend_strategies(self):
        """Test different routing strategies via gRPC."""
        # Generate test content info
        content_info = self._generate_content_info()

        # Test each strategy
        strategies = ["content_type", "cost", "performance", "reliability", "hybrid"]

        for strategy in strategies:
            # Select backend using the current strategy
            result = await self.client.select_backend(
                content_type=content_info["content_type"],
                content_size=content_info["content_size"],
                content_hash=content_info["content_hash"],
                metadata=content_info["metadata"],
                strategy=strategy
            )

            # Verify backend ID is in expected list
            self.assertIn(
                result["backend_id"],
                self.settings.backends,
                f"Selected backend {result['backend_id']} should be in available backends"
            )

            logger.info(f"Strategy '{strategy}' selected backend: {result['backend_id']}")

    async def test_select_backend_priorities(self):
        """Test different routing priorities via gRPC."""
        # Generate test content info
        content_info = self._generate_content_info()

        # Test each priority
        priorities = ["balanced", "performance", "cost", "reliability", "geographic"]

        for priority in priorities:
            # Select backend using the current priority
            result = await self.client.select_backend(
                content_type=content_info["content_type"],
                content_size=content_info["content_size"],
                content_hash=content_info["content_hash"],
                metadata=content_info["metadata"],
                priority=priority
            )

            # Verify backend ID is in expected list
            self.assertIn(
                result["backend_id"],
                self.settings.backends,
                f"Selected backend {result['backend_id']} should be in available backends"
            )

            logger.info(f"Priority '{priority}' selected backend: {result['backend_id']}")

    async def test_select_backend_filtered(self):
        """Test backend selection with filtered backends via gRPC."""
        # Generate test content info
        content_info = self._generate_content_info()

        # Use a subset of backends
        available_backends = self.settings.backends[:2]

        # Select backend with limited backend options
        result = await self.client.select_backend(
            content_type=content_info["content_type"],
            content_size=content_info["content_size"],
            content_hash=content_info["content_hash"],
            metadata=content_info["metadata"],
            available_backends=available_backends
        )

        # Verify backend ID is in filtered list
        self.assertIn(
            result["backend_id"],
            available_backends,
            f"Selected backend {result['backend_id']} should be in filtered backends"
        )

        logger.info(f"Successfully selected backend from filtered list: {result['backend_id']}")

    async def test_record_outcome(self):
        """Test recording a routing outcome via gRPC."""
        # Generate test content info
        content_info = self._generate_content_info()

        # Select a backend
        select_result = await self.client.select_backend(
            content_type=content_info["content_type"],
            content_size=content_info["content_size"]
        )

        backend_id = select_result["backend_id"]

        # Record success outcome
        success_result = await self.client.record_outcome(
            backend_id=backend_id,
            success=True,
            content_type=content_info["content_type"],
            content_size=content_info["content_size"],
            content_hash=content_info["content_hash"]
        )

        # Verify success result
        self.assertIn("success", success_result)
        self.assertIn("message", success_result)
        self.assertIn("timestamp", success_result)
        self.assertTrue(success_result["success"])

        # Record failure outcome
        failure_result = await self.client.record_outcome(
            backend_id=backend_id,
            success=False,
            content_type=content_info["content_type"],
            content_size=content_info["content_size"],
            content_hash=content_info["content_hash"],
            error="Test error message"
        )

        # Verify failure result
        self.assertIn("success", failure_result)
        self.assertIn("message", failure_result)
        self.assertIn("timestamp", failure_result)
        self.assertTrue(failure_result["success"])  # The operation succeeded, even though the outcome was a failure

        logger.info("Successfully recorded routing outcomes")

    async def test_get_insights(self):
        """Test getting routing insights via gRPC."""
        # Get insights
        result = await self.client.get_insights()

        # Verify result structure
        self.assertIn("factor_weights", result)
        self.assertIn("backend_scores", result)
        self.assertIn("backend_success_rates", result)
        self.assertIn("content_type_distribution", result)
        self.assertIn("backend_usage_stats", result)
        self.assertIn("latency_stats", result)
        self.assertIn("timestamp", result)

        # Verify factor weights
        self.assertIsInstance(result["factor_weights"], dict)

        # Verify backend scores
        self.assertIsInstance(result["backend_scores"], dict)

        logger.info("Successfully retrieved routing insights")

    async def test_metrics_streaming(self):
        """Test metrics streaming via gRPC."""
        # Set up metrics callback
        metrics_received = []

        def metrics_callback(update):
            metrics_received.append(update)

        # Start metrics streaming
        await self.client.start_metrics_streaming(
            callback=metrics_callback,
            update_interval_seconds=1
        )

        # Wait for a few updates
        await asyncio.sleep(3)

        # Stop metrics streaming
        await self.client.stop_metrics_streaming()

        # Verify metrics were received
        self.assertGreater(len(metrics_received), 0)

        # Verify structure of first update
        first_update = metrics_received[0]
        self.assertIn("metrics", first_update)
        self.assertIn("status", first_update)
        self.assertIn("timestamp", first_update)

        logger.info(f"Successfully received {len(metrics_received)} metrics updates")

    async def test_error_handling(self):
        """Test error handling in gRPC client and server."""
        # Test with invalid strategy
        with self.assertRaises(Exception):
            await self.client.select_backend(
                content_type="application/pdf",
                content_size=1024,
                strategy="invalid_strategy"
            )

        # Test with invalid backend ID
        with self.assertRaises(Exception):
            await self.client.record_outcome(
                backend_id="invalid_backend",
                success=True,
                content_type="application/pdf",
                content_size=1024
            )

        logger.info("Successfully verified error handling")

    async def test_connection_management(self):
        """Test connection management in the gRPC client."""
        # Disconnect client
        await self.client.disconnect()

        # Reconnect automatically on method call
        result = await self.client.select_backend(
            content_type="application/pdf",
            content_size=1024
        )

        # Verify result
        self.assertIn("backend_id", result)

        logger.info("Successfully verified automatic reconnection")

    async def test_server_restart(self):
        """Test client behavior when server restarts."""
        # Stop the server
        await self.server.stop()

        # Start a new server
        self.server = await self.run_server(
            host=self.server_host,
            port=self.server_port,
            routing_manager=self.routing_manager
        )

        # Wait a short time for server to start
        await asyncio.sleep(1)

        # Test client connection
        result = await self.client.select_backend(
            content_type="application/pdf",
            content_size=1024
        )

        # Verify result
        self.assertIn("backend_id", result)

        logger.info("Successfully reconnected after server restart")

    async def test_concurrent_requests(self):
        """Test concurrent requests to the gRPC server."""
        # Generate test content info
        content_info = self._generate_content_info()

        # Create concurrent tasks
        num_tasks = 10
        tasks = []

        for i in range(num_tasks):
            task = asyncio.create_task(
                self.client.select_backend(
                    content_type=content_info["content_type"],
                    content_size=content_info["content_size"]
                )
            )
            tasks.append(task)

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks)

        # Verify all results
        for result in results:
            self.assertIn("backend_id", result)
            self.assertIn(result["backend_id"], self.settings.backends)

        logger.info(f"Successfully completed {num_tasks} concurrent requests")

    async def test_performance(self):
        """Test performance of the gRPC implementation."""
        # Generate test content info
        content_info = self._generate_content_info()

        # Measure time to perform multiple requests
        num_requests = 50
        start_time = time.time()

        for i in range(num_requests):
            await self.client.select_backend(
                content_type=content_info["content_type"],
                content_size=content_info["content_size"]
            )

        elapsed_time = time.time() - start_time
        average_time = elapsed_time / num_requests

        logger.info(f"Performance test: {num_requests} requests in {elapsed_time:.2f}s (avg: {average_time*1000:.2f}ms)")

        # No strict assertion, but log the performance metrics
        self.assertLess(average_time, 0.1, "Average request time should be less than 100ms")


if __name__ == "__main__":
    unittest.main()
