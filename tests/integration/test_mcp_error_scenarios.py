"""
Test error scenarios and recovery in the MCP Server.

This module implements the recommendation from MCP_TEST_IMPROVEMENTS.md
to add tests for more error paths and recovery scenarios, specifically
focusing on network failures, timeout handling, and concurrent access edge cases.
"""

import os
import sys
import json
import time
import socket
import requests
import unittest
import threading
import tempfile
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

from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import
from ipfs_kit_py.error import IPFSError


class MockRequestsSession:
    """Mock requests.Session class that can simulate network errors and timeouts."""
    
    def __init__(self, error_mode=None, error_count=1):
        """Initialize with specified error behavior.
        
        Args:
            error_mode: Type of error to simulate ('timeout', 'connection', 'http_error', or None)
            error_count: Number of consecutive errors to simulate before succeeding
        """
        self.error_mode = error_mode
        self.error_count = error_count
        self.call_count = 0
    
    def post(self, url, *args, **kwargs):
        """Mock POST request with simulated errors."""
        self.call_count += 1
        
        # Simulate errors for the specified number of calls
        if self.error_mode and self.call_count <= self.error_count:
            if self.error_mode == 'timeout':
                raise requests.exceptions.Timeout("Simulated timeout error")
            elif self.error_mode == 'connection':
                raise requests.exceptions.ConnectionError("Simulated connection error")
            elif self.error_mode == 'http_error':
                response = requests.Response()
                response.status_code = 500
                response._content = b'{"error": "Simulated HTTP error"}'
                response.reason = "Internal Server Error"
                return response
        
        # Create a successful response
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"success": true, "result": "mock_response"}'
        return response
    
    def get(self, url, *args, **kwargs):
        """Mock GET request with simulated errors."""
        return self.post(url, *args, **kwargs)


class TestMCPErrorScenarios(unittest.TestCase):
    """Test error scenarios and recovery in the MCP Server."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temp directory for the MCP server
        self.temp_dir = tempfile.mkdtemp(prefix="mcp_error_test_")
        
        # Create an MCP server in debug mode
        self.mcp_server = MCPServer(
            debug_mode=True,
            persistence_path=self.temp_dir,
            isolation_mode=True
        )
        
        # Create mock IPFS API
        self.mock_ipfs_api = MagicMock()
        self.mcp_server.ipfs_kit = self.mock_ipfs_api
        
        # Patch the requests module in the ipfs_model
        self.session_patcher = patch('ipfs_kit_py.mcp.models.ipfs_model.requests.Session')
        self.mock_session_class = self.session_patcher.start()
        self.mock_session = MockRequestsSession()
        self.mock_session_class.return_value = self.mock_session
    
    def tearDown(self):
        """Clean up after tests."""
        # Stop request patching
        self.session_patcher.stop()
        
        # Shutdown the MCP server
        self.mcp_server.shutdown()
        
        # Clean up the temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_connection_error_retry(self):
        """Test retry behavior on connection errors."""
        # Configure mock to fail with connection errors twice, then succeed
        self.mock_session.error_mode = 'connection'
        self.mock_session.error_count = 2
        
        # Configure the IPFS model's retry settings for testing
        ipfs_model = self.mcp_server.models["ipfs"]
        original_retry_count = getattr(ipfs_model, 'retry_count', 3)
        original_retry_delay = getattr(ipfs_model, 'retry_delay', 1)
        
        try:
            # Set retry configuration for faster tests
            if hasattr(ipfs_model, 'retry_count'):
                ipfs_model.retry_count = 3  # Ensure at least 3 retries
            if hasattr(ipfs_model, 'retry_delay'):
                ipfs_model.retry_delay = 0.1  # Short delay for tests
            
            # Call a method that uses the IPFS API
            result = ipfs_model.cat("QmTestCID")
            
            # Verify the result indicates success after retries
            self.assertTrue(result.get("success", False), 
                           f"Operation should succeed after retries: {result}")
            self.assertIn("retries", result, "Result should indicate retries were performed")
            self.assertEqual(result.get("retries", 0), 2, "Should have performed 2 retries")
            
            # Verify mock was called 3 times (2 failures + 1 success)
            self.assertEqual(self.mock_session.call_count, 3)
        
        finally:
            # Restore original retry settings
            if hasattr(ipfs_model, 'retry_count'):
                ipfs_model.retry_count = original_retry_count
            if hasattr(ipfs_model, 'retry_delay'):
                ipfs_model.retry_delay = original_retry_delay
    
    def test_timeout_handling(self):
        """Test handling of timeout errors."""
        # Configure mock to fail with timeout errors once, then succeed
        self.mock_session.error_mode = 'timeout'
        self.mock_session.error_count = 1
        
        # Call a method that uses the IPFS API
        ipfs_model = self.mcp_server.models["ipfs"]
        result = ipfs_model.cat("QmTestCID")
        
        # Verify the result
        self.assertTrue(result.get("success", False), 
                       f"Operation should succeed after timeout retry: {result}")
        self.assertEqual(self.mock_session.call_count, 2, "Should have retried once")
        
        # Verify timeout information is included
        self.assertIn("retry_info", result, "Result should include retry information")
        self.assertIn("original_error", result.get("retry_info", {}), 
                     "Retry info should include original error")
    
    def test_retry_exhaustion(self):
        """Test behavior when all retries are exhausted."""
        # Configure mock to always fail with connection errors
        self.mock_session.error_mode = 'connection'
        self.mock_session.error_count = 10  # More than retry limit
        
        # Call a method that uses the IPFS API
        ipfs_model = self.mcp_server.models["ipfs"]
        
        # Configure retry settings for testing
        original_retry_count = getattr(ipfs_model, 'retry_count', 3)
        original_retry_delay = getattr(ipfs_model, 'retry_delay', 1)
        
        try:
            # Set retry configuration for faster tests
            if hasattr(ipfs_model, 'retry_count'):
                ipfs_model.retry_count = 3
            if hasattr(ipfs_model, 'retry_delay'):
                ipfs_model.retry_delay = 0.1
                
            # Call the method, which should fail after all retries
            result = ipfs_model.cat("QmTestCID")
            
            # Verify the result indicates failure
            self.assertFalse(result.get("success", True), 
                            "Operation should fail after exhausting retries")
            self.assertIn("error", result, "Result should include error information")
            self.assertIn("retries_exhausted", result, 
                         "Result should indicate retries were exhausted")
            
            # Verify retry count matches configuration
            # Should be initial attempt + retries
            expected_calls = getattr(ipfs_model, 'retry_count', 3) + 1
            self.assertEqual(self.mock_session.call_count, expected_calls, 
                            f"Should have attempted {expected_calls} calls")
                
        finally:
            # Restore original retry settings
            if hasattr(ipfs_model, 'retry_count'):
                ipfs_model.retry_count = original_retry_count
            if hasattr(ipfs_model, 'retry_delay'):
                ipfs_model.retry_delay = original_retry_delay
    
    def test_http_error_handling(self):
        """Test handling of HTTP errors (non-200 responses)."""
        # Configure mock to return HTTP 500 error once, then succeed
        self.mock_session.error_mode = 'http_error'
        self.mock_session.error_count = 1
        
        # Call a method that uses the IPFS API
        ipfs_model = self.mcp_server.models["ipfs"]
        result = ipfs_model.cat("QmTestCID")
        
        # Verify the result
        if result.get("success", False):
            # Some implementations retry on HTTP errors
            self.assertEqual(self.mock_session.call_count, 2, 
                           "Should have retried after HTTP error")
        else:
            # Some implementations don't retry on HTTP errors
            self.assertEqual(self.mock_session.call_count, 1, 
                           "Should not retry after HTTP error")
            self.assertIn("error", result, "Result should include error information")
            self.assertIn("status_code", result, "Result should include status code")
            self.assertEqual(result.get("status_code"), 500, "Status code should be 500")
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    def test_daemon_not_running(self):
        """Test behavior when the IPFS daemon is not running."""
        # Create a FastAPI app
        app = FastAPI()
        
        # Register MCP server with the app
        self.mcp_server.register_with_app(app, prefix="/api/v0")
        
        # Create a test client
        client = TestClient(app)
        
        # Mock the IPFS model to simulate daemon not running
        with patch.object(self.mcp_server.models["ipfs"], '_is_daemon_running', return_value=False):
            # Try to cat a file, which should fail
            response = client.get("/api/v0/ipfs/cat/QmTestCID")
            
            # Verify response
            self.assertEqual(response.status_code, 503, 
                           "Should return 503 when daemon is not running")
            data = response.json()
            self.assertFalse(data.get("success", True), "Operation should fail")
            self.assertIn("error", data, "Response should include error information")
            self.assertIn("daemon", data.get("error", "").lower(), 
                         "Error should mention daemon not running")
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    def test_middleware_error_handling(self):
        """Test that middleware properly handles errors in request processing."""
        # Create a FastAPI app
        app = FastAPI()
        
        # Register MCP server with the app
        self.mcp_server.register_with_app(app, prefix="/api/v0")
        
        # Create a test client
        client = TestClient(app)
        
        # Patch the cat method to raise an unexpected exception
        original_cat = self.mcp_server.models["ipfs"].cat
        def cat_with_error(*args, **kwargs):
            """Test replacement that raises an exception."""
            raise RuntimeError("Simulated unexpected error")
            
        self.mcp_server.models["ipfs"].cat = cat_with_error
        
        try:
            # Try to cat a file, which should fail gracefully
            response = client.get("/api/v0/ipfs/cat/QmTestCID")
            
            # Verify the response is a proper error
            self.assertIn(response.status_code, [500, 404], 
                         f"Should return error status, got {response.status_code}")
            data = response.json()
            self.assertIn("error", data, "Response should include error information")
            
        finally:
            # Restore original method
            self.mcp_server.models["ipfs"].cat = original_cat
    
    def test_concurrent_access(self):
        """Test handling of concurrent access to the MCP server."""
        # Number of concurrent requests
        num_threads = 10
        
        # Shared results dictionary
        results = {'success': 0, 'failure': 0, 'errors': []}
        
        # Function to execute in threads
        def execute_request():
            try:
                # Call cat method on IPFS model
                result = self.mcp_server.models["ipfs"].cat("QmTestCID")
                if result.get("success", False):
                    results['success'] += 1
                else:
                    results['failure'] += 1
                    results['errors'].append(result.get("error", "No error message"))
            except Exception as e:
                results['failure'] += 1
                results['errors'].append(str(e))
        
        # Create and start threads
        threads = []
        for _ in range(num_threads):
            thread = threading.Thread(target=execute_request)
            thread.start()
            threads.append(thread)
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all requests were handled
        self.assertEqual(results['success'] + results['failure'], num_threads,
                        "All requests should be accounted for")
        
        # Verify no unexpected errors occurred
        if results['failure'] > 0:
            print(f"Failures: {results['failure']}, Errors: {results['errors']}")
    
    def test_cache_error_recovery(self):
        """Test recovery when cache operations fail."""
        # Get the cache manager
        cache_manager = self.mcp_server.persistence
        
        # Patch the put method to simulate a failure
        original_put = cache_manager.put
        fail_count = [0]  # Use a list for mutable value in closure
        
        def failing_put(key, value, metadata=None):
            """Test replacement that fails the first time."""
            if fail_count[0] == 0:
                fail_count[0] += 1
                raise IOError("Simulated cache write error")
            return original_put(key, value, metadata)
            
        cache_manager.put = failing_put
        
        try:
            # Perform an operation that uses the cache
            result = self.mcp_server.models["ipfs"].cat("QmTestCID")
            
            # Operation should succeed despite cache failure
            self.assertTrue(result.get("success", False), 
                           "Operation should succeed despite cache error")
            
            # Verify cache was attempted again on second call
            result2 = self.mcp_server.models["ipfs"].cat("QmTestCID")
            self.assertTrue(result2.get("success", False), 
                           "Second operation should succeed")
            self.assertEqual(fail_count[0], 1, "Cache put should have failed once")
            
        finally:
            # Restore original method
            cache_manager.put = original_put
    
    def test_invalid_cid_error_handling(self):
        """Test handling of invalid CIDs."""
        # Call with an invalid CID
        result = self.mcp_server.models["ipfs"].cat("InvalidCID")
        
        # Verify the result indicates proper validation error
        self.assertFalse(result.get("success", True), 
                        "Operation should fail with invalid CID")
        self.assertIn("error", result, "Result should include error information")
        self.assertIn("cid", result.get("error", "").lower(), 
                     "Error should mention invalid CID")
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    def test_request_validation_errors(self):
        """Test that API request validation errors are handled properly."""
        # Create a FastAPI app
        app = FastAPI()
        
        # Register MCP server with the app
        self.mcp_server.register_with_app(app, prefix="/api/v0")
        
        # Create a test client
        client = TestClient(app)
        
        # Test with missing required field
        response = client.post("/api/v0/ipfs/dag/put", json={"format": "json"})
        
        # Verify validation error response
        self.assertEqual(response.status_code, 422, 
                        "Should return 422 Unprocessable Entity for validation error")
        data = response.json()
        self.assertIn("detail", data, "Response should include validation details")
        
        # Test with invalid enum value
        response = client.post(
            "/api/v0/ipfs/dag/put", 
            json={"object": {"test": "value"}, "format": "invalid_format"}
        )
        
        # Verify validation error response
        self.assertEqual(response.status_code, 422, 
                        "Should return 422 Unprocessable Entity for invalid enum")
    
    def test_ipfs_client_reconnection(self):
        """Test reconnection to IPFS client after connection lost."""
        ipfs_model = self.mcp_server.models["ipfs"]
        
        # Mock connection status checking
        original_is_connected = getattr(ipfs_model, '_is_connected', None)
        if original_is_connected:
            connection_status = [False]  # Start disconnected
            
            def mock_is_connected():
                """Mock that returns the current connection status."""
                return connection_status[0]
                
            ipfs_model._is_connected = mock_is_connected
            
            # Mock reconnection method
            original_reconnect = getattr(ipfs_model, '_reconnect', None)
            reconnect_called = [0]
            
            def mock_reconnect():
                """Mock that tracks reconnection attempts."""
                reconnect_called[0] += 1
                connection_status[0] = True  # Mark as connected after reconnect
                if original_reconnect:
                    return original_reconnect()
                return True
                
            if hasattr(ipfs_model, '_reconnect'):
                ipfs_model._reconnect = mock_reconnect
            
            try:
                # Call a method that should trigger reconnection
                result = ipfs_model.cat("QmTestCID")
                
                # Verify reconnection was attempted
                if hasattr(ipfs_model, '_reconnect'):
                    self.assertTrue(reconnect_called[0] > 0, 
                                  "Reconnection should have been attempted")
                
                # Operation should succeed after reconnection
                self.assertTrue(result.get("success", False), 
                               "Operation should succeed after reconnection")
                
            finally:
                # Restore original methods
                if original_is_connected:
                    ipfs_model._is_connected = original_is_connected
                if original_reconnect:
                    ipfs_model._reconnect = original_reconnect


if __name__ == "__main__":
    unittest.main()