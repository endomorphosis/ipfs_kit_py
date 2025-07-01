"""
Extended tests for DHT operations in the MCP Server.

This module provides enhanced tests for the DHT operations (dht_findpeer, dht_findprovs)
including controller integration tests, performance tests, and enhanced error scenarios.
"""

import unittest
from unittest.mock import patch, MagicMock, call
import json
import time
import anyio
import os
import sys
import tempfile

# Try to import FastAPI
try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("FastAPI not available, skipping HTTP tests")

# Add the parent directory to the path so we can import the ipfs_kit_py module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import
from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController


@unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
class TestMCPDHTControllerIntegration(unittest.TestCase):
    """Test DHT operations with the IPFS Controller integration."""
    
    @classmethod
    def setUpClass(cls):
        """Set up the FastAPI application once for all tests."""
        if not FASTAPI_AVAILABLE:
            return
            
        # Create a FastAPI app for HTTP tests
        cls.app = FastAPI()
    
    def setUp(self):
        """Set up test environment."""
        if not FASTAPI_AVAILABLE:
            self.skipTest("FastAPI not available")
            
        # Create a temp directory for the MCP server
        self.temp_dir = tempfile.mkdtemp(prefix="mcp_dht_test_")
        
        # Create a mock IPFS Kit
        self.mock_ipfs_kit = MagicMock()
        
        # Set up mock cache manager instead of real one
        self.mock_cache_manager = MagicMock()
        
        # Create IPFS Model with mocks
        self.ipfs_model = IPFSModel(
            ipfs_kit_instance=self.mock_ipfs_kit,
            cache_manager=self.mock_cache_manager
        )
        
        # Create an IPFS controller for the tests
        self.ipfs_controller = IPFSController(self.ipfs_model)
        
        # Register the IPFS controller routes
        router = self.__class__.app.router
        self.ipfs_controller.register_routes(router)
        
        # Create a test client
        self.client = TestClient(self.__class__.app)
    
    def tearDown(self):
        """Clean up after tests."""
        if not FASTAPI_AVAILABLE:
            return
            
        # Clean up the temp directory if it exists
        if hasattr(self, 'temp_dir'):
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_dht_findpeer_endpoint(self):
        """Test the DHT findpeer endpoint."""
        # Set up mock response for dht_findpeer
        mock_response = {
            "success": True,
            "operation": "dht_findpeer",
            "operation_id": "test_op_123",
            "peer_id": "QmTestPeer",
            "responses": [
                {
                    "id": "QmFoundPeer",
                    "addrs": [
                        "/ip4/127.0.0.1/tcp/4001",
                        "/ip6/::1/tcp/4001"
                    ]
                }
            ],
            "peers_found": 1,
            "duration_ms": 123.45,
            "timestamp": time.time()
        }
        
        # Make our model return this response
        self.ipfs_model.dht_findpeer = MagicMock(return_value=mock_response)
        
        # Make a request to the endpoint
        response = self.client.post(
            "/ipfs/dht/findpeer",
            json={"peer_id": "QmTestPeer"}
        )
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["success"], True)
        self.assertEqual(data["operation"], "dht_findpeer")
        self.assertEqual(data["peer_id"], "QmTestPeer")
        self.assertEqual(data["peers_found"], 1)
        self.assertEqual(len(data["responses"]), 1)
        self.assertEqual(data["responses"][0]["id"], "QmFoundPeer")
        
        # Verify the model method was called correctly
        self.ipfs_model.dht_findpeer.assert_called_once_with("QmTestPeer")
    
    def test_dht_findprovs_endpoint(self):
        """Test the DHT findprovs endpoint."""
        # Set up mock response for dht_findprovs
        mock_response = {
            "success": True,
            "operation": "dht_findprovs",
            "operation_id": "test_op_456",
            "cid": "QmTestCID",
            "providers": [
                {
                    "id": "QmProvider1",
                    "addrs": [
                        "/ip4/192.168.1.1/tcp/4001",
                        "/ip6/2001:db8::1/tcp/4001"
                    ]
                },
                {
                    "id": "QmProvider2",
                    "addrs": [
                        "/ip4/192.168.1.2/tcp/4001"
                    ]
                }
            ],
            "count": 2,
            "num_providers": 10,
            "duration_ms": 234.56,
            "timestamp": time.time()
        }
        
        # Make our model return this response
        self.ipfs_model.dht_findprovs = MagicMock(return_value=mock_response)
        
        # Make a request to the endpoint
        response = self.client.post(
            "/ipfs/dht/findprovs",
            json={"cid": "QmTestCID", "num_providers": 10}
        )
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["success"], True)
        self.assertEqual(data["operation"], "dht_findprovs")
        self.assertEqual(data["cid"], "QmTestCID")
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["num_providers"], 10)
        self.assertEqual(len(data["providers"]), 2)
        self.assertEqual(data["providers"][0]["id"], "QmProvider1")
        self.assertEqual(data["providers"][1]["id"], "QmProvider2")
        
        # Verify the model method was called correctly
        self.ipfs_model.dht_findprovs.assert_called_once_with(
            "QmTestCID", num_providers=10
        )
    
    def test_dht_findpeer_validation_error(self):
        """Test validation errors in the DHT findpeer endpoint."""
        # Make a request with missing peer_id
        response = self.client.post(
            "/ipfs/dht/findpeer",
            json={}
        )
        
        # Verify validation error response
        self.assertEqual(response.status_code, 422)  # Unprocessable Entity
        data = response.json()
        self.assertIn("detail", data)
        
        # Ensure the validation error message mentions peer_id
        validation_errors = data["detail"]
        self.assertTrue(any("peer_id" in str(error) for error in validation_errors))
    
    def test_dht_findprovs_validation_error(self):
        """Test validation errors in the DHT findprovs endpoint."""
        # Make a request with missing cid
        response = self.client.post(
            "/ipfs/dht/findprovs",
            json={"num_providers": 5}
        )
        
        # Verify validation error response
        self.assertEqual(response.status_code, 422)  # Unprocessable Entity
        data = response.json()
        self.assertIn("detail", data)
        
        # Ensure the validation error message mentions cid
        validation_errors = data["detail"]
        self.assertTrue(any("cid" in str(error) for error in validation_errors))
    
    def test_dht_findpeer_server_error(self):
        """Test server error handling in the DHT findpeer endpoint."""
        # Make the model method raise an exception
        error_response = {
            "success": False,
            "operation": "dht_findpeer",
            "error": "Simulated server error",
            "error_type": "server_error",
            "timestamp": time.time()
        }
        self.ipfs_model.dht_findpeer = MagicMock(return_value=error_response)
        
        # Make a request to the endpoint
        response = self.client.post(
            "/ipfs/dht/findpeer",
            json={"peer_id": "QmTestPeer"}
        )
        
        # Verify error response
        # Non-200 status code varies by implementation (usually 400 or 500)
        self.assertNotEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["success"], False)
        self.assertEqual(data["operation"], "dht_findpeer")
        self.assertIn("error", data)
        self.assertEqual(data["error"], "Simulated server error")
    
    def test_dht_findpeer_invalid_peer_id(self):
        """Test handling of invalid peer ID format."""
        # Set up a response simulating validation error for invalid peer ID
        error_response = {
            "success": False,
            "operation": "dht_findpeer",
            "error": "Invalid peer ID format",
            "error_type": "validation_error",
            "timestamp": time.time()
        }
        self.ipfs_model.dht_findpeer = MagicMock(return_value=error_response)
        
        # Make a request with an invalid peer ID format
        response = self.client.post(
            "/ipfs/dht/findpeer",
            json={"peer_id": "invalid_peer_id_format"}
        )
        
        # Verify error response
        self.assertNotEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["success"], False)
        self.assertEqual(data["operation"], "dht_findpeer")
        self.assertIn("error", data)
        self.assertEqual(data["error"], "Invalid peer ID format")


class TestMCPDHTPerformance(unittest.TestCase):
    """Test DHT operation performance characteristics."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a mock IPFS Kit
        self.mock_ipfs_kit = MagicMock()
        
        # Create a mock cache manager
        self.mock_cache_manager = MagicMock()
        
        # Create an IPFS Model with the mocks
        self.ipfs_model = IPFSModel(
            ipfs_kit_instance=self.mock_ipfs_kit,
            cache_manager=self.mock_cache_manager
        )
    
    def test_dht_findpeer_duration_tracking(self):
        """Test that the DHT findpeer operation tracks duration."""
        # Simulate a delay in the IPFS Kit response
        def delayed_response(*args, **kwargs):
            """Simulate a delayed response from IPFS Kit."""
            time.sleep(0.1)  # 100ms delay
            return {
                "Responses": [
                    {
                        "ID": "QmFoundPeer",
                        "Addrs": ["/ip4/127.0.0.1/tcp/4001"]
                    }
                ]
            }
        
        # Set up the mock to use our delayed response
        self.mock_ipfs_kit.dht_findpeer.side_effect = delayed_response
        
        # Call the method
        result = self.ipfs_model.dht_findpeer("QmTestPeer")
        
        # Verify the result includes duration tracking
        self.assertTrue(result["success"])
        self.assertIn("duration_ms", result)
        # Duration should be at least our simulated delay
        self.assertTrue(result["duration_ms"] >= 100)
    
    def test_dht_findprovs_with_large_response(self):
        """Test handling of large response lists from dht_findprovs."""
        # Number of providers to simulate
        num_providers = 100
        
        # Generate a large response
        responses = []
        for i in range(num_providers):
            responses.append({
                "ID": f"QmProvider{i}",
                "Addrs": [f"/ip4/192.168.1.{i}/tcp/4001"]
            })
        
        # Set up the mock response
        self.mock_ipfs_kit.dht_findprovs.return_value = {
            "Responses": responses
        }
        
        # Call the method
        result = self.ipfs_model.dht_findprovs("QmTestCID")
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "dht_findprovs")
        self.assertEqual(result["count"], num_providers)
        self.assertEqual(len(result["providers"]), num_providers)
        
        # Verify some sample providers
        self.assertEqual(result["providers"][0]["id"], "QmProvider0")
        self.assertEqual(result["providers"][99]["id"], "QmProvider99")
    
    def test_dht_findpeer_multiple_calls(self):
        """Test performance of multiple consecutive DHT findpeer calls."""
        # Number of calls to make
        num_calls = 10
        
        # Simulate a response that gets faster with each call (simulating caching effect)
        call_count = [0]
        
        def timed_response(*args, **kwargs):
            """Simulate a response that gets faster over time."""
            call_num = call_count[0]
            call_count[0] += 1
            # First call takes 100ms, subsequent calls take less time
            delay = 0.1 * (0.5 ** call_num)
            time.sleep(delay)
            return {
                "Responses": [
                    {
                        "ID": "QmFoundPeer",
                        "Addrs": ["/ip4/127.0.0.1/tcp/4001"]
                    }
                ]
            }
        
        # Set up the mock to use our timed response
        self.mock_ipfs_kit.dht_findpeer.side_effect = timed_response
        
        # Make multiple calls
        results = []
        for _ in range(num_calls):
            result = self.ipfs_model.dht_findpeer("QmTestPeer")
            results.append(result)
        
        # Verify all calls succeeded
        self.assertTrue(all(result["success"] for result in results))
        
        # Get durations
        durations = [result["duration_ms"] for result in results]
        
        # First call should be slowest
        self.assertTrue(durations[0] > durations[-1], 
                       f"First call ({durations[0]}ms) should be slower than last call ({durations[-1]}ms)")
    
    def test_combined_operation_sequence(self):
        """Test a sequence of DHT operations to simulate typical usage patterns."""
        # Set up mocks for both operations
        self.mock_ipfs_kit.dht_findpeer.return_value = {
            "Responses": [
                {
                    "ID": "QmFoundPeer",
                    "Addrs": ["/ip4/127.0.0.1/tcp/4001"]
                }
            ]
        }
        
        self.mock_ipfs_kit.dht_findprovs.return_value = {
            "Responses": [
                {
                    "ID": "QmProvider",
                    "Addrs": ["/ip4/192.168.1.1/tcp/4001"]
                }
            ]
        }
        
        # Simulate a typical usage sequence:
        # 1. Find a peer
        # 2. Find providers for a CID
        # 3. Find another peer (potentially one of the providers)
        start_time = time.time()
        
        # 1. Find a peer
        peer_result = self.ipfs_model.dht_findpeer("QmPeer1")
        self.assertTrue(peer_result["success"])
        
        # 2. Find providers for a CID
        provs_result = self.ipfs_model.dht_findprovs("QmTestCID")
        self.assertTrue(provs_result["success"])
        
        # 3. Find another peer (the provider we just found)
        provider_id = provs_result["providers"][0]["id"]
        peer2_result = self.ipfs_model.dht_findpeer(provider_id)
        self.assertTrue(peer2_result["success"])
        
        # Calculate total sequence duration
        total_duration = time.time() - start_time
        
        # The sequence should complete in a reasonable time
        self.assertLess(total_duration, 1.0, 
                       f"Combined operation sequence took {total_duration:.2f}s, which is too long")
        
        # Verify the expected calls were made
        expected_calls = [
            call("QmPeer1"),
            call(provider_id)
        ]
        self.mock_ipfs_kit.dht_findpeer.assert_has_calls(expected_calls)
        self.mock_ipfs_kit.dht_findprovs.assert_called_once_with("QmTestCID")


class TestMCPDHTErrorScenarios(unittest.TestCase):
    """Test DHT operation error scenarios."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a mock IPFS Kit
        self.mock_ipfs_kit = MagicMock()
        
        # Create a mock cache manager
        self.mock_cache_manager = MagicMock()
        
        # Create an IPFS Model with the mocks
        self.ipfs_model = IPFSModel(
            ipfs_kit_instance=self.mock_ipfs_kit,
            cache_manager=self.mock_cache_manager
        )
    
    def test_dht_findpeer_invalid_response_format(self):
        """Test handling of invalid response format from IPFS Kit."""
        # Set up an invalid response format
        invalid_response = {
            "Invalid": "Response format"
        }
        
        # Make the mock return the invalid response
        self.mock_ipfs_kit.dht_findpeer.return_value = invalid_response
        
        # Call the method
        result = self.ipfs_model.dht_findpeer("QmTestPeer")
        
        # Check if the implementation handles the invalid format as an error
        # Some implementations might handle this by providing default values
        if not result["success"]:
            # If it's treated as an error, verify the error details
            self.assertEqual(result["operation"], "dht_findpeer")
            self.assertIn("error", result)
            self.assertIn("error_type", result)
        else:
            # If it's not treated as an error, verify that the response
            # at least has the expected fields
            self.assertEqual(result["operation"], "dht_findpeer")
            self.assertIn("peers_found", result)
            # Verify peers_found is 0 if no valid peers were in the response
            self.assertEqual(result["peers_found"], 0)
    
    def test_dht_findprovs_null_response(self):
        """Test handling of null response from IPFS Kit."""
        # Make the mock return None
        self.mock_ipfs_kit.dht_findprovs.return_value = None
        
        # Call the method
        result = self.ipfs_model.dht_findprovs("QmTestCID")
        
        # Verify the result indicates an error
        self.assertFalse(result["success"])
        self.assertEqual(result["operation"], "dht_findprovs")
        self.assertIn("error", result)
        # The exact error message might vary, but it should indicate a problem with None/null
        self.assertTrue(
            any(term in result["error"].lower() for term in ["none", "null", "nonetype"]),
            f"Error message '{result['error']}' doesn't mention null/None"
        )
    
    def test_dht_findpeer_unexpected_error_type(self):
        """Test handling of unexpected error types."""
        # Set up the mock to raise an unexpected error type
        class CustomError(Exception):
            """Custom error type for testing."""
            pass
            
        self.mock_ipfs_kit.dht_findpeer.side_effect = CustomError("Unexpected error type")
        
        # Call the method
        result = self.ipfs_model.dht_findpeer("QmTestPeer")
        
        # Verify the result indicates an error
        self.assertFalse(result["success"])
        self.assertEqual(result["operation"], "dht_findpeer")
        self.assertIn("error", result)
        
        # The exact error handling might vary, but it should indicate an unexpected error
        error_msg = result["error"].lower()
        self.assertTrue(
            any(term in error_msg for term in ["unexpected", "error", "exception", "unknown"]),
            f"Error message '{result['error']}' doesn't indicate an unexpected error"
        )
    
    def test_dht_findprovs_daemon_not_running(self):
        """Test behavior when the IPFS daemon is not running."""
        # Simulate a ConnectionError which might indicate daemon not running
        self.mock_ipfs_kit.dht_findprovs.side_effect = ConnectionError("Failed to connect to IPFS daemon")
        
        # Call the method
        result = self.ipfs_model.dht_findprovs("QmTestCID")
        
        # Verify the result indicates an error
        self.assertFalse(result["success"])
        self.assertEqual(result["operation"], "dht_findprovs")
        self.assertIn("error", result)
        
        # The error message should mention connectivity issues
        error_msg = result["error"].lower()
        self.assertTrue(
            any(term in error_msg for term in ["connect", "daemon", "connection", "failed"]),
            f"Error message '{result['error']}' doesn't indicate a connection issue"
        )
    
    def test_dht_findpeer_peer_id_validation(self):
        """Test validation of peer ID format."""
        # Define an invalid peer ID
        invalid_peer_id = "not a valid peer ID"
        
        # Call the method directly
        result = self.ipfs_model.dht_findpeer(invalid_peer_id)
        
        # Behavior depends on implementation:
        if not result["success"]:
            # Some implementations validate the peer ID format
            self.assertEqual(result["operation"], "dht_findpeer")
            self.assertIn("error", result)
            self.assertIn("peer id", result["error"].lower())
        else:
            # Some implementations pass validation to the IPFS daemon
            self.mock_ipfs_kit.dht_findpeer.assert_called_once_with(invalid_peer_id)


if __name__ == "__main__":
    unittest.main()