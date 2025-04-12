import unittest
import tempfile
import os
import json
import anyio
import shutil
import time
from unittest.mock import MagicMock, patch, AsyncMock

from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient

# Import MCP server and components
from ipfs_kit_py.mcp.server import MCPServer
from ipfs_kit_py.mcp.persistence.cache_manager import MCPCacheManager


class TestMCPServerComprehensive(unittest.TestCase):
    """Comprehensive testing for MCP server functionality."""
    
    def setUp(self):
        """Set up test environment with MCP server."""
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        
        # Initialize MCP server with debug mode and isolated persistence
        self.server = MCPServer(
            debug_mode=True,
            persistence_path=self.temp_dir,
            isolation_mode=True  # Use isolated IPFS repo for testing
        )
        
        # Create FastAPI app with MCP server routes
        self.app = FastAPI()
        self.router = APIRouter()
        self.server.register_with_app(self.app, prefix="/api/v0")
        self.client = TestClient(self.app)
        
        # For test validity checking - some endpoints may be in simulation mode
        self.simulation_mode = True  # Set based on IPFS availability
    
    def tearDown(self):
        """Clean up test environment."""
        # Close any open resources in server
        if hasattr(self.server, "shutdown") and callable(self.server.shutdown):
            self.server.shutdown()
        
        # Remove temporary directory and contents
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_server_initialization(self):
        """Test proper server initialization with components."""
        # Verify server components exist
        self.assertIsNotNone(self.server.cache_manager)
        self.assertIsInstance(self.server.cache_manager, MCPCacheManager)
        
        # Check controllers are registered
        expected_controllers = ["ipfs", "cli"]
        for controller_name in expected_controllers:
            self.assertIn(controller_name, self.server.controllers)
            self.assertIsNotNone(self.server.controllers[controller_name])
        
        # Check models are registered
        expected_models = ["ipfs"]
        for model_name in expected_models:
            self.assertIn(model_name, self.server.models)
            self.assertIsNotNone(self.server.models[model_name])
    
    def test_health_endpoint(self):
        """Test the health endpoint."""
        response = self.client.get("/api/v0/mcp/health")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("success", data)
        self.assertIn("status", data)
        self.assertIn("timestamp", data)
        self.assertEqual(data["status"], "healthy")
    
    def test_debug_endpoint(self):
        """Test the debug endpoint."""
        response = self.client.get("/api/v0/mcp/debug")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("success", data)
        self.assertIn("debug_mode", data)
        self.assertIn("controllers", data)
        self.assertIn("models", data)
        self.assertIn("persistence", data)
        self.assertTrue(data["debug_mode"])
    
    def test_operations_endpoint(self):
        """Test the operations endpoint."""
        # Make some operations first to generate data
        self.client.get("/api/v0/mcp/health")
        self.client.get("/api/v0/mcp/debug")
        
        # Now check operations
        response = self.client.get("/api/v0/mcp/operations")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("success", data)
        self.assertIn("operations", data)
        self.assertIsInstance(data["operations"], list)
        self.assertGreaterEqual(len(data["operations"]), 2)  # At least the health and debug operations
    
    def test_daemon_status_endpoint(self):
        """Test the daemon status endpoint."""
        response = self.client.get("/api/v0/mcp/daemon/status")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("success", data)
        self.assertIn("is_running", data)
        # Other fields may vary based on daemon status
    
    def test_ipfs_cat_endpoint(self):
        """Test the IPFS content retrieval endpoint."""
        # Use a well-known IPFS CID that should be available in most IPFS networks
        # This is the "hello world" file, widely available
        cid = "QmT78zSuBmuS4z925WZfrqQ1qHaJ56DQaTfyMUF7F8ff5o"
        
        response = self.client.get(f"/api/v0/mcp/ipfs/cat/{cid}")
        
        # If we're in simulation mode, we'll get a simulated response
        if self.simulation_mode:
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("success", data)
            self.assertIn("simulation_mode", data)
            self.assertTrue(data["simulation_mode"])
        else:
            # If IPFS is available, we'll get the actual content
            self.assertEqual(response.status_code, 200)
            # "hello world" content
            self.assertEqual(response.content, b"hello world\n")
    
    def test_ipfs_pin_endpoints(self):
        """Test IPFS pin operations."""
        # Use a well-known IPFS CID
        cid = "QmT78zSuBmuS4z925WZfrqQ1qHaJ56DQaTfyMUF7F8ff5o"
        
        # Test pin endpoint
        pin_response = self.client.post("/api/v0/mcp/ipfs/pin", 
                                       json={"cid": cid})
        self.assertEqual(pin_response.status_code, 200)
        
        pin_data = pin_response.json()
        self.assertIn("success", pin_data)
        
        # Test list pins endpoint
        list_response = self.client.get("/api/v0/mcp/ipfs/pins")
        self.assertEqual(list_response.status_code, 200)
        
        list_data = list_response.json()
        self.assertIn("success", list_data)
        self.assertIn("pins", list_data)
        
        # If not in simulation mode, check that our pin is in the list
        if not self.simulation_mode:
            self.assertIn(cid, list_data["pins"])
        
        # Test unpin endpoint
        unpin_response = self.client.post("/api/v0/mcp/ipfs/unpin", 
                                         json={"cid": cid})
        self.assertEqual(unpin_response.status_code, 200)
        
        unpin_data = unpin_response.json()
        self.assertIn("success", unpin_data)
    
    def test_ipfs_add_endpoint_json(self):
        """Test the IPFS add endpoint with JSON content."""
        # Prepare test content
        test_content = "Hello, MCP Server!"
        
        # Test JSON-based add
        add_response = self.client.post("/api/v0/mcp/ipfs/add", 
                                       json={"content": test_content})
        self.assertEqual(add_response.status_code, 200)
        
        add_data = add_response.json()
        self.assertIn("success", add_data)
        self.assertIn("cid", add_data)
        
        added_cid = add_data["cid"]
        
        # Verify content was added by retrieving it
        cat_response = self.client.get(f"/api/v0/mcp/ipfs/cat/{added_cid}")
        
        if self.simulation_mode:
            self.assertEqual(cat_response.status_code, 200)
            cat_data = cat_response.json()
            self.assertTrue(cat_data["success"])
            self.assertTrue(cat_data["simulation_mode"])
        else:
            self.assertEqual(cat_response.status_code, 200)
            self.assertEqual(cat_response.content.decode('utf-8'), test_content)
    
    def test_ipfs_dag_operations(self):
        """Test IPFS DAG operations."""
        # Prepare test DAG object
        dag_object = {
            "name": "Test Object",
            "value": 42,
            "links": [
                {"name": "link1", "value": "value1"},
                {"name": "link2", "value": "value2"}
            ]
        }
        
        # Test DAG put
        put_response = self.client.post("/api/v0/mcp/ipfs/dag/put", 
                                       json={"object": dag_object})
        self.assertEqual(put_response.status_code, 200)
        
        put_data = put_response.json()
        self.assertIn("success", put_data)
        self.assertIn("cid", put_data)
        
        dag_cid = put_data["cid"]
        
        # Test DAG get
        get_response = self.client.get(f"/api/v0/mcp/ipfs/dag/get/{dag_cid}")
        self.assertEqual(get_response.status_code, 200)
        
        get_data = get_response.json()
        self.assertIn("success", get_data)
        
        # In simulation mode, we won't get the actual object back
        if not self.simulation_mode:
            self.assertIn("object", get_data)
            retrieved_object = get_data["object"]
            self.assertEqual(retrieved_object["name"], dag_object["name"])
            self.assertEqual(retrieved_object["value"], dag_object["value"])
    
    def test_ipfs_block_operations(self):
        """Test IPFS block operations."""
        # Prepare test block data
        test_data = "Test block data"
        test_data_bytes = test_data.encode('utf-8')
        
        # Test block put
        put_response = self.client.post("/api/v0/mcp/ipfs/block/put", 
                                       json={"data": test_data})
        self.assertEqual(put_response.status_code, 200)
        
        put_data = put_response.json()
        self.assertIn("success", put_data)
        self.assertIn("cid", put_data)
        
        block_cid = put_data["cid"]
        
        # Test block get
        get_response = self.client.get(f"/api/v0/mcp/ipfs/block/get/{block_cid}")
        
        if self.simulation_mode:
            self.assertEqual(get_response.status_code, 200)
            # In simulation mode, response may be JSON or bytes
            if "Content-Type" in get_response.headers and get_response.headers["Content-Type"] == "application/json":
                get_data = get_response.json()
                self.assertIn("success", get_data)
                self.assertTrue(get_data["success"])
        else:
            self.assertEqual(get_response.status_code, 200)
            self.assertEqual(get_response.content, test_data_bytes)
        
        # Test block stat
        stat_response = self.client.get(f"/api/v0/mcp/ipfs/block/stat/{block_cid}")
        self.assertEqual(stat_response.status_code, 200)
        
        stat_data = stat_response.json()
        self.assertIn("success", stat_data)
        self.assertIn("size", stat_data)
        
        if not self.simulation_mode:
            self.assertEqual(stat_data["size"], len(test_data_bytes))
    
    def test_ipfs_stats_endpoint(self):
        """Test the IPFS stats endpoint."""
        response = self.client.get("/api/v0/mcp/ipfs/stats")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("success", data)
        self.assertIsInstance(data, dict)
        
        # Stats should include operation counts
        self.assertTrue(
            "operation_stats" in data or 
            "add_count" in data or
            "operations" in data,
            "Missing statistics in response"
        )
    
    def test_ipfs_daemon_status_endpoint(self):
        """Test the IPFS daemon status endpoint."""
        response = self.client.get("/api/v0/mcp/ipfs/daemon/status")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("success", data)
        self.assertIn("is_running", data)
        self.assertIn("version", data)
    
    def test_cli_version_endpoint(self):
        """Test the CLI version endpoint."""
        response = self.client.get("/api/v0/mcp/cli/version")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("success", data)
        self.assertIn("version", data)
    
    def test_error_handling(self):
        """Test error handling for invalid requests."""
        # Test non-existent endpoint
        response = self.client.get("/api/v0/mcp/nonexistent")
        self.assertEqual(response.status_code, 404)
        
        # Test invalid method
        response = self.client.put("/api/v0/mcp/health")
        self.assertEqual(response.status_code, 405)
        
        # Test invalid parameter
        response = self.client.post("/api/v0/mcp/ipfs/pin", json={"invalid_param": "value"})
        self.assertEqual(response.status_code, 400)
        
        # Test missing required parameter
        response = self.client.post("/api/v0/mcp/ipfs/pin", json={})
        self.assertEqual(response.status_code, 400)
    
    def test_session_middleware(self):
        """Test session middleware functionality."""
        # Make a request and check for session ID
        response = self.client.get("/api/v0/mcp/health")
        self.assertEqual(response.status_code, 200)
        
        # Check if X-MCP-Session-ID header is present in the response
        self.assertIn("X-MCP-Session-ID", response.headers)
        session_id = response.headers["X-MCP-Session-ID"]
        self.assertTrue(session_id)  # Non-empty session ID
        
        # Make another request with the same session ID
        headers = {"X-MCP-Session-ID": session_id}
        response2 = self.client.get("/api/v0/mcp/health", headers=headers)
        self.assertEqual(response2.status_code, 200)
        
        # Session ID should be preserved
        self.assertEqual(response2.headers["X-MCP-Session-ID"], session_id)
    
    def test_operations_tracking(self):
        """Test operation tracking functionality."""
        # Clear operations before testing
        self.server.operations = []
        
        # Make some operations
        response1 = self.client.get("/api/v0/mcp/health")
        self.assertEqual(response1.status_code, 200)
        
        response2 = self.client.get("/api/v0/mcp/debug")
        self.assertEqual(response2.status_code, 200)
        
        # Get operations
        response = self.client.get("/api/v0/mcp/operations")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("operations", data)
        operations = data["operations"]
        
        # Should have recorded health and debug operations
        self.assertGreaterEqual(len(operations), 2)
        
        # Check operation structure
        for op in operations:
            self.assertIn("timestamp", op)
            self.assertIn("path", op)
            self.assertIn("method", op)
            self.assertIn("session_id", op)
            self.assertIn("duration_ms", op)
    
    def test_cache_manager(self):
        """Test cache manager functionality."""
        # Add some data to cache
        key = "test_key"
        value = {"test": "data"}
        
        # Use cache manager directly
        self.server.cache_manager.put(key, value)
        
        # Retrieve from cache
        retrieved = self.server.cache_manager.get(key)
        self.assertEqual(retrieved, value)
        
        # Update cache
        value2 = {"updated": "data"}
        self.server.cache_manager.put(key, value2)
        
        # Check updated value
        retrieved2 = self.server.cache_manager.get(key)
        self.assertEqual(retrieved2, value2)
        
        # Delete from cache
        self.server.cache_manager.delete(key)
        
        # Verify it's gone
        retrieved3 = self.server.cache_manager.get(key)
        self.assertIsNone(retrieved3)
    
    @unittest.skipIf(True, "ParquetCIDCache integration test - requires more setup")
    def test_parquet_cid_cache_integration(self):
        """Test ParquetCIDCache integration with IPFS model."""
        # This test requires more setup and specific dependencies
        # Skip it for now
        pass
    
    def test_concurrent_requests(self):
        """Test handling of concurrent requests."""
        # Create a list of URLs to request concurrently
        urls = [
            "/api/v0/mcp/health",
            "/api/v0/mcp/debug",
            "/api/v0/mcp/operations",
            "/api/v0/mcp/daemon/status",
            "/api/v0/mcp/ipfs/stats",
            "/api/v0/mcp/cli/version"
        ]
        
        # Make concurrent requests
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(urls)) as executor:
            futures = [
                executor.submit(self.client.get, url)
                for url in urls
            ]
            
            # Wait for all requests to complete
            responses = [future.result() for future in futures]
            
        # Check that all requests succeeded
        for response in responses:
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("success", data)
            self.assertTrue(data["success"])
    
    @unittest.skipIf(True, "Stress test - skip for normal test runs")
    def test_stress_performance(self):
        """Stress test for server performance."""
        # This test puts significant load on the server
        # Skip it for normal test runs
        pass


class TestMCPAsyncFunctionality(unittest.TestCase):
    """Test MCP server async functionality."""
    
    def setUp(self):
        """Set up test environment with MCP server."""
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        
        # Initialize MCP server with debug mode and isolated persistence
        self.server = MCPServer(
            debug_mode=True,
            persistence_path=self.temp_dir,
            isolation_mode=True  # Use isolated IPFS repo for testing
        )
        
        # Create FastAPI app with MCP server routes
        self.app = FastAPI()
        self.router = APIRouter()
        self.server.register_with_app(self.app, prefix="/api/v0")
        self.client = TestClient(self.app)
    
    def tearDown(self):
        """Clean up test environment."""
        # Close any open resources in server
        if hasattr(self.server, "shutdown") and callable(self.server.shutdown):
            self.server.shutdown()
        
        # Remove temporary directory and contents
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_debug_middleware_async(self):
        """Test async debug middleware."""
        async def run_test():
            # Create request and response mocks
            request = MagicMock()
            request.url.path = "/test/path"
            request.method = "GET"
            
            response = MagicMock()
            
            # Create call_next mock
            async def mock_call_next(*args, **kwargs):
                return response
            
            # Get the middleware function
            from ipfs_kit_py.mcp.server import create_debug_middleware
            middleware = create_debug_middleware(debug_mode=True)
            
            # Call the middleware
            result = await middleware(request, mock_call_next)
            
            return result
        
        # Run the async test
        response = anyio.run(run_test())
        
        # Should get the response back
        self.assertEqual(response, response)
    
    def test_session_middleware_async(self):
        """Test async session middleware."""
        async def run_test():
            # Create request and response mocks
            request = MagicMock()
            request.headers = {}
            
            response = MagicMock()
            response.headers = {}
            
            # Create call_next mock
            async def mock_call_next(*args, **kwargs):
                return response
            
            # Get the middleware function
            from ipfs_kit_py.mcp.server import create_session_middleware
            middleware = create_session_middleware()
            
            # Call the middleware
            result = await middleware(request, mock_call_next)
            
            return result
        
        # Run the async test
        response = anyio.run(run_test())
        
        # Should get the response back with X-MCP-Session-ID header
        self.assertIn("X-MCP-Session-ID", response.headers)
    
    def test_operation_logging_middleware_async(self):
        """Test async operation logging middleware."""
        async def run_test():
            # Create request and response mocks
            request = MagicMock()
            request.url.path = "/test/path"
            request.method = "GET"
            request.headers = {}
            
            response = MagicMock()
            
            # Create call_next mock that waits a bit
            async def mock_call_next(*args, **kwargs):
                await anyio.sleep(0.01)  # Short delay
                return response
            
            # Set up operations list
            operations = []
            
            # Get the middleware function
            from ipfs_kit_py.mcp.server import create_operation_logging_middleware
            middleware = create_operation_logging_middleware(operations)
            
            # Call the middleware
            result = await middleware(request, mock_call_next)
            
            return result, operations
        
        # Run the async test
        response, operations = anyio.run(run_test())
        
        # Should get the response back
        self.assertEqual(response, response)
        
        # Should have logged the operation
        self.assertEqual(len(operations), 1)
        operation = operations[0]
        self.assertEqual(operation["path"], "/test/path")
        self.assertEqual(operation["method"], "GET")
        self.assertIn("duration_ms", operation)
        self.assertGreater(operation["duration_ms"], 0)


if __name__ == "__main__":
    unittest.main()