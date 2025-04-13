"""
Test the metrics collection and monitoring functionality of the MCP Server.

This module implements the recommendation from MCP_TEST_IMPROVEMENTS.md
to add specific tests for the metrics collection and reporting functionality.
"""

import os
import sys
import json
import time
import tempfile
import unittest
from unittest.mock import MagicMock, patch, call

# Try to import FastAPI
try:
    from fastapi import FastAPI, Request, Response, APIRouter
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("FastAPI not available, skipping HTTP tests")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ipfs_kit_py.mcp_server.server_bridge import MCPServer  # Refactored import


@unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
class TestMCPMonitoring(unittest.TestCase):
    """Test the metrics collection and monitoring functionality of the MCP Server."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temp directory for the MCP server
        self.temp_dir = tempfile.mkdtemp(prefix="mcp_monitoring_test_")
        
        # Create an MCP server in debug mode for better metrics
        self.mcp_server = MCPServer(
            debug_mode=True,
            persistence_path=self.temp_dir,
            isolation_mode=True
        )
        
        # Create a FastAPI app
        self.app = FastAPI()
        
        # Register MCP server with the app
        self.mcp_server.register_with_app(self.app, prefix="/api/v0")
        
        # Create a test client
        self.client = TestClient(self.app)
    
    def tearDown(self):
        """Clean up after tests."""
        # Shutdown the MCP server
        self.mcp_server.shutdown()
        
        # Clean up the temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_debug_endpoint_includes_metrics(self):
        """Test that the debug endpoint includes metrics data."""
        # Make requests to generate some metrics
        self.client.get("/api/v0/health")
        self.client.get("/api/v0/debug")
        
        # Get debug info
        response = self.client.get("/api/v0/debug")
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify metrics are included
        self.assertIn("metrics", data)
        metrics = data["metrics"]
        
        # Verify metrics structure
        self.assertIn("uptime_seconds", metrics)
        self.assertIn("request_count", metrics)
        self.assertIn("average_request_time_ms", metrics)
        self.assertIn("endpoints", metrics)
        
        # Verify endpoint metrics exist for the paths we accessed
        endpoints = metrics["endpoints"]
        self.assertIn("/api/v0/health", endpoints)
        self.assertIn("/api/v0/debug", endpoints)
        
        # Verify each endpoint has request metrics
        health_metrics = endpoints["/api/v0/health"]
        self.assertIn("count", health_metrics)
        self.assertIn("avg_time_ms", health_metrics)
        self.assertTrue(health_metrics["count"] >= 1)
    
    def test_request_metrics_are_updated(self):
        """Test that request metrics are updated with each request."""
        # Get initial metrics
        response = self.client.get("/api/v0/debug")
        initial_data = response.json()
        initial_request_count = initial_data["metrics"]["request_count"]
        
        # Make some more requests
        num_requests = 5
        for _ in range(num_requests):
            self.client.get("/api/v0/health")
        
        # Get updated metrics
        response = self.client.get("/api/v0/debug")
        updated_data = response.json()
        updated_request_count = updated_data["metrics"]["request_count"]
        
        # Verify the request count increased by the expected amount (num_requests + 1 for the debug request)
        self.assertEqual(updated_request_count, initial_request_count + num_requests + 1)
        
        # Verify the health endpoint metrics reflect our requests
        health_metrics = updated_data["metrics"]["endpoints"].get("/api/v0/health", {})
        # The count should be at least num_requests higher than before
        self.assertTrue(health_metrics.get("count", 0) >= num_requests)
    
    def test_controller_operation_metrics(self):
        """Test that controller operation metrics are properly tracked."""
        # Generate some controller operations
        self.client.get("/api/v0/ipfs/dag/get/QmTest1234")
        self.client.post("/api/v0/ipfs/dag/put", json={"object": {"test": "value"}, "format": "json"})
        self.client.get("/api/v0/ipfs/block/stat/QmTest5678")
        
        # Get debug info
        response = self.client.get("/api/v0/debug")
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify controller metrics are included
        self.assertIn("controllers", data)
        controllers = data["controllers"]
        self.assertIn("ipfs", controllers)
        
        # Verify operation metrics are tracked
        ipfs_controller = controllers["ipfs"]
        self.assertIn("operation_count", ipfs_controller)
        self.assertIn("operations", ipfs_controller)
        
        # Operations section might be an object or an array depending on implementation
        operations = ipfs_controller["operations"]
        
        # For object implementation
        if isinstance(operations, dict):
            # At least one of our operations should be recorded
            operation_keys = ["dag_get", "dag_put", "block_stat"]
            self.assertTrue(any(op in operations for op in operation_keys))
        # For array implementation
        elif isinstance(operations, list):
            operation_names = [op.get("name") for op in operations if "name" in op]
            # At least one of our operations should be recorded
            self.assertTrue(any(name in ["dag_get", "dag_put", "block_stat"] for name in operation_names))
        
        # Get controller stats directly
        ipfs_controller_obj = self.mcp_server.controllers["ipfs"]
        controller_stats = ipfs_controller_obj.get_stats()
        
        # Verify stats include operations
        self.assertIsInstance(controller_stats, dict)
        self.assertIn("operation_count", controller_stats)
        # Controller should have recorded our operations
        self.assertTrue(controller_stats["operation_count"] >= 3)
    
    def test_model_operation_metrics(self):
        """Test that model operation metrics are properly tracked."""
        # Generate some model operations
        self.client.get("/api/v0/ipfs/cat/QmTest1234")
        self.client.post("/api/v0/ipfs/add", files={"file": ("test.txt", b"test content")})
        
        # Get debug info
        response = self.client.get("/api/v0/debug")
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify models section exists
        self.assertIn("models", data)
        models = data["models"]
        self.assertIn("ipfs", models)
        
        # Verify model metrics are tracked
        ipfs_model = models["ipfs"]
        self.assertIn("operation_count", ipfs_model)
        
        # Operations might be tracked in different ways depending on implementation
        if "operations" in ipfs_model:
            operations = ipfs_model["operations"]
            # For object implementation
            if isinstance(operations, dict):
                operation_keys = ["cat", "add"]
                self.assertTrue(any(op in operations for op in operation_keys))
            # For array implementation
            elif isinstance(operations, list):
                operation_names = [op.get("name") for op in operations if "name" in op]
                self.assertTrue(any(name in ["cat", "add"] for name in operation_names))
        
        # Get model stats directly
        ipfs_model_obj = self.mcp_server.models["ipfs"]
        model_stats = ipfs_model_obj.get_stats()
        
        # Verify stats exist
        self.assertIsInstance(model_stats, dict)
        
        # The structure might vary, so we check for common patterns
        if "operation_count" in model_stats:
            # Should have recorded at least our operations
            self.assertTrue(model_stats["operation_count"] >= 2)
        elif "operations" in model_stats:
            operations = model_stats["operations"]
            # Should have some operation tracking
            self.assertTrue(len(operations) > 0)
    
    def test_persistence_metrics(self):
        """Test that cache/persistence metrics are properly tracked."""
        # Generate some operations that will use the cache
        self.client.get("/api/v0/ipfs/cat/QmTest1234")  # First access is a miss
        self.client.get("/api/v0/ipfs/cat/QmTest1234")  # Second access might be a hit
        
        # Get debug info
        response = self.client.get("/api/v0/debug")
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify persistence metrics are included
        self.assertIn("persistence", data)
        persistence = data["persistence"]
        
        # Verify cache metrics
        self.assertIn("cache_hits", persistence)
        self.assertIn("cache_misses", persistence)
        self.assertIn("cache_size", persistence)
        
        # The hit/miss rates depend on implementation, but both should be tracked
        self.assertIsInstance(persistence["cache_hits"], int)
        self.assertIsInstance(persistence["cache_misses"], int)
        
        # Get direct stats from the cache manager
        cache_manager = self.mcp_server.persistence
        cache_stats = cache_manager.get_stats()
        
        # Verify stats structure
        self.assertIsInstance(cache_stats, dict)
        self.assertIn("hits", cache_stats)
        self.assertIn("misses", cache_stats)
        
        # Total operations should match our requests
        # Note: exact numbers depend on implementation details
        total_operations = cache_stats["hits"] + cache_stats["misses"]
        self.assertTrue(total_operations >= 1)
    
    def test_event_tracking(self):
        """Test that server-level events are properly tracked."""
        # Get debug info with initial events
        response = self.client.get("/api/v0/debug")
        initial_data = response.json()
        
        # Trigger a server event if the reset API is available
        try:
            self.client.post("/api/v0/reset")
            event_triggered = True
        except:
            # Reset endpoint might not exist, try an alternative
            try:
                # Try to use the IPFSModel directly
                self.mcp_server.models["ipfs"].reset()
                event_triggered = True
            except:
                # If we can't trigger a specific event, skip the detailed checks
                event_triggered = False
                pass
        
        # Get updated debug info
        response = self.client.get("/api/v0/debug")
        updated_data = response.json()
        
        # Verify server metrics include event tracking
        self.assertIn("server", updated_data)
        server_metrics = updated_data["server"]
        
        # Events section might be tracked in different ways
        if "events" in server_metrics:
            self.assertIsInstance(server_metrics["events"], (list, dict))
        
        # Skip detailed event checks if we couldn't trigger a specific event
        if not event_triggered:
            return
            
        # If events are tracked as a list
        if isinstance(server_metrics.get("events", []), list):
            # There should be more events in the updated data
            initial_event_count = len(initial_data.get("server", {}).get("events", []))
            updated_event_count = len(updated_data.get("server", {}).get("events", []))
            self.assertTrue(updated_event_count >= initial_event_count)
            
        # If events are tracked as counters
        elif "event_count" in server_metrics:
            initial_count = initial_data.get("server", {}).get("event_count", 0)
            updated_count = updated_data.get("server", {}).get("event_count", 0)
            self.assertTrue(updated_count >= initial_count)
    
    def test_debug_mode_impact(self):
        """Test that debug mode enables additional metrics collection."""
        # Create a non-debug server for comparison
        non_debug_server = MCPServer(
            debug_mode=False,
            persistence_path=self.temp_dir,
            isolation_mode=True
        )
        
        # Create a FastAPI app for the non-debug server
        non_debug_app = FastAPI()
        non_debug_server.register_with_app(non_debug_app, prefix="/api/v0")
        non_debug_client = TestClient(non_debug_app)
        
        try:
            # Generate some metrics on both servers
            self.client.get("/api/v0/health")  # Debug mode server
            non_debug_client.get("/api/v0/health")  # Non-debug mode server
            
            # Get debug info from both servers
            debug_response = self.client.get("/api/v0/debug")
            non_debug_response = non_debug_client.get("/api/v0/debug")
            
            # Both should succeed
            self.assertEqual(debug_response.status_code, 200)
            self.assertEqual(non_debug_response.status_code, 200)
            
            debug_data = debug_response.json()
            non_debug_data = non_debug_response.json()
            
            # Debug mode should include more metrics
            self.assertTrue(len(json.dumps(debug_data)) >= len(json.dumps(non_debug_data)))
            
            # Check for specific debug-only metrics
            # Some metrics may only exist in debug mode
            debug_only_metrics = [
                ("metrics", "endpoint_timing_breakdown"),
                ("metrics", "detailed_statistics"),
                ("persistence", "cache_hit_rate_over_time"),
                ("controllers", "ipfs", "method_execution_times")
            ]
            
            # Check if at least one debug-only metric exists
            found_debug_metric = False
            for path in debug_only_metrics:
                # Navigate through the nested structure
                debug_value = debug_data
                non_debug_value = non_debug_data
                
                for key in path:
                    if key in debug_value:
                        debug_value = debug_value[key]
                    else:
                        debug_value = None
                        break
                        
                    if key in non_debug_value:
                        non_debug_value = non_debug_value[key]
                    else:
                        non_debug_value = None
                        break
                
                # If this metric exists in debug but not in non-debug, mark as found
                if debug_value is not None and non_debug_value is None:
                    found_debug_metric = True
                    break
            
            # If no specific debug-only metric was found, verify debug mode has more data
            if not found_debug_metric:
                # Debug response should at least have more information
                self.assertGreater(
                    len(json.dumps(debug_data, sort_keys=True)), 
                    len(json.dumps(non_debug_data, sort_keys=True))
                )
                
        finally:
            # Clean up the non-debug server
            non_debug_server.shutdown()


if __name__ == "__main__":
    unittest.main()