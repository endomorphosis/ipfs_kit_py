"""
Test script for the Storacha connection manager.

This script verifies that the StorachaConnectionManager correctly handles connection
failures, implements proper retry logic, and provides robust endpoint failover.
"""

import os
import sys
import time
import json
import logging
import unittest
import requests
from unittest.mock import patch, MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add project root to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# Now import the necessary modules
try:
    from ipfs_kit_py.mcp.extensions.storacha_connection import StorachaConnectionManager, StorachaApiError
    logger.info("Successfully imported StorachaConnectionManager")
except ImportError as e:
    logger.error(f"Failed to import StorachaConnectionManager: {e}")
    sys.exit(1)

class MockResponse:
    """Mock Response class for testing."""
    
    def __init__(self, status_code=200, json_data=None, content=None, headers=None):
        self.status_code = status_code
        self._json_data = json_data
        self.content = content or b""
        self.headers = headers or {}
        self.text = content.decode('utf-8') if isinstance(content, bytes) else str(content or "")
        
    def json(self):
        return self._json_data
    
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP Error: {self.status_code}")

class TestStorachaConnection(unittest.TestCase):
    """Test cases for StorachaConnectionManager."""
    
    def setUp(self):
        """Set up test environment."""
        # Test API key and endpoints
        self.api_key = "test_api_key"
        self.test_endpoints = [
            "https://test-endpoint-1.example.com",
            "https://test-endpoint-2.example.com",
            "https://test-endpoint-3.example.com"
        ]
        
        # Configure connection manager for testing
        self.connection = StorachaConnectionManager(
            api_key=self.api_key,
            endpoints=self.test_endpoints,
            max_retries=2,
            timeout=5,
            validate_endpoints=False,  # Skip validation for tests
            circuit_breaker_threshold=3,
            circuit_breaker_reset_time=10  # Short reset time for testing
        )
        
        # Override session with mock
        self.connection.session = MagicMock()
        
    def test_initialization(self):
        """Test that the connection manager initializes properly."""
        self.assertEqual(self.connection.api_key, self.api_key)
        self.assertEqual(len(self.connection.endpoints), 3)
        self.assertEqual(self.connection.max_retries, 2)
        self.assertEqual(self.connection.timeout, 5)
        
        # Verify all endpoints are in the health tracking
        for endpoint in self.test_endpoints:
            self.assertIn(endpoint, self.connection.endpoint_health)
            
    def test_endpoint_selection(self):
        """Test endpoint selection logic."""
        # Set up health status for endpoints
        self.connection.endpoint_health[self.test_endpoints[0]]["healthy"] = True
        self.connection.endpoint_health[self.test_endpoints[0]]["success_rate"] = 95
        
        self.connection.endpoint_health[self.test_endpoints[1]]["healthy"] = True
        self.connection.endpoint_health[self.test_endpoints[1]]["success_rate"] = 98
        
        self.connection.endpoint_health[self.test_endpoints[2]]["healthy"] = False
        
        # Test endpoint selection
        selected_endpoint = self.connection._get_endpoint()
        
        # Should select the endpoint with highest success rate
        self.assertEqual(selected_endpoint, self.test_endpoints[1])
        
    @patch('requests.Session.get')
    def test_request_success(self, mock_get):
        """Test successful request handling."""
        # Mock a successful response
        mock_response = MockResponse(
            status_code=200,
            json_data={"success": True, "data": "test_data"},
            headers={"Content-Type": "application/json"}
        )
        mock_get.return_value = mock_response
        
        # Make a request
        response = self.connection.get("test/endpoint")
        
        # Verify the request was made with the correct parameters
        mock_get.assert_called_once()
        
        # Check that the endpoint health was updated
        endpoint = self.test_endpoints[0]  # First endpoint should be used
        self.assertTrue(self.connection.endpoint_health[endpoint]["healthy"])
        self.assertEqual(self.connection.endpoint_health[endpoint]["failures"], 0)
        self.assertEqual(self.connection.endpoint_health[endpoint]["requests_count"], 1)
        self.assertEqual(self.connection.endpoint_health[endpoint]["success_count"], 1)
        
    @patch('requests.Session.get')
    def test_request_failure_with_retry(self, mock_get):
        """Test request failure with retry logic."""
        # Mock a failed response followed by a successful one
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("Connection refused"),
            MockResponse(
                status_code=200,
                json_data={"success": True, "data": "test_data"},
                headers={"Content-Type": "application/json"}
            )
        ]
        
        # Make a request
        response = self.connection.get("test/endpoint")
        
        # Verify the request was made twice
        self.assertEqual(mock_get.call_count, 2)
        
        # Check that the first endpoint was marked as failed
        self.assertFalse(self.connection.endpoint_health[self.test_endpoints[0]]["healthy"])
        self.assertEqual(self.connection.endpoint_health[self.test_endpoints[0]]["failures"], 1)
        
        # Check that the second endpoint was marked as successful
        self.assertTrue(self.connection.endpoint_health[self.test_endpoints[1]]["healthy"])
        self.assertEqual(self.connection.endpoint_health[self.test_endpoints[1]]["success_count"], 1)
        
    @patch('requests.Session.get')
    def test_circuit_breaker(self, mock_get):
        """Test circuit breaker functionality."""
        # Mock multiple failures for the first endpoint
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        # Force failures on the first endpoint to trigger circuit breaker
        for _ in range(3):  # 3 failures needed to trigger circuit breaker
            try:
                self.connection.get("test/endpoint")
            except Exception:
                pass
            
            # Reset the mock to simulate new requests
            mock_get.reset_mock()
            mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        # Verify the circuit is open
        self.assertTrue(self.connection.endpoint_health[self.test_endpoints[0]]["circuit_open"])
        
        # First endpoint should be skipped, test if second endpoint is used
        mock_get.side_effect = [
            MockResponse(
                status_code=200,
                json_data={"success": True, "data": "test_data"},
                headers={"Content-Type": "application/json"}
            )
        ]
        
        # Make a request
        self.connection.get("test/endpoint")
        
        # Check if the request was made to the second endpoint
        mock_get.assert_called_once()
        # The URL should start with the second endpoint
        call_args = mock_get.call_args[0][0]
        self.assertTrue(call_args.startswith(self.test_endpoints[1]))
        
    @patch('requests.Session.get')
    def test_rate_limiting(self, mock_get):
        """Test rate limiting detection and handling."""
        # Mock a rate limited response
        mock_get.return_value = MockResponse(
            status_code=429,
            json_data={"error": "Too Many Requests"},
            headers={"X-RateLimit-Reset": str(int(time.time()) + 30)}
        )
        
        # Make a request that should detect rate limiting
        with self.assertRaises(StorachaApiError) as context:
            self.connection.get("test/endpoint")
        
        # Verify the error message
        self.assertIn("Rate limit", str(context.exception))
        
        # Check if rate limiting was applied
        self.assertTrue(self.connection.rate_limited_until > time.time())
        
    @patch('requests.Session.post')
    def test_upload_file(self, mock_post):
        """Test file upload functionality."""
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            temp.write(b"Test file content")
            temp_path = temp.name
        
        try:
            # Mock a successful upload response
            mock_post.return_value = MockResponse(
                status_code=200,
                json_data={"cid": "bafybeihgzjmdpx3a3n44m25h7b2jkj5yvqv7lvcksjj3dxhk2h35zykzuy"},
                headers={"Content-Type": "application/json"}
            )
            
            # Upload the file
            result = self.connection.upload_file(temp_path)
            
            # Verify the upload was successful
            self.assertEqual(result["cid"], "bafybeihgzjmdpx3a3n44m25h7b2jkj5yvqv7lvcksjj3dxhk2h35zykzuy")
            
            # Verify the request was made with the correct parameters
            mock_post.assert_called_once()
            
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    @patch('socket.gethostbyname')
    def test_dns_resolution(self, mock_gethostbyname):
        """Test DNS resolution checking."""
        # Test successful DNS resolution
        mock_gethostbyname.return_value = "192.168.1.1"
        self.assertTrue(self.connection._check_dns_resolution("example.com"))
        
        # Test failed DNS resolution
        mock_gethostbyname.side_effect = socket.gaierror("Name or service not known")
        self.assertFalse(self.connection._check_dns_resolution("nonexistent.example.com"))
        
    def test_get_status(self):
        """Test getting connection status information."""
        # Set up some metrics
        self.connection.total_requests = 10
        self.connection.successful_requests = 8
        self.connection.failed_requests = 2
        self.connection.working_endpoint = self.test_endpoints[0]
        self.connection.last_working_time = time.time()
        
        # Get status
        status = self.connection.get_status()
        
        # Verify status contains expected information
        self.assertEqual(status["working_endpoint"], self.test_endpoints[0])
        self.assertEqual(status["total_requests"], 10)
        self.assertEqual(status["successful_requests"], 8)
        self.assertEqual(status["failed_requests"], 2)
        self.assertEqual(status["success_rate"], 80.0)
        self.assertEqual(len(status["endpoints"]), 3)
        
    @patch('time.sleep', return_value=None)  # Don't actually sleep in tests
    @patch('requests.Session.get')
    def test_exponential_backoff(self, mock_get, mock_sleep):
        """Test exponential backoff behavior on retries."""
        # Mock failed responses
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("Connection refused"),
            requests.exceptions.ConnectionError("Connection refused"),
            requests.exceptions.ConnectionError("Connection refused")
        ]
        
        # Make a request that will fail all retries
        with self.assertRaises(Exception):
            self.connection.get("test/endpoint")
        
        # Verify sleep was called with increasing delays
        self.assertEqual(mock_sleep.call_count, 2)  # Should be called once per retry
        
        # First retry should have shorter delay than second retry
        first_delay = mock_sleep.call_args_list[0][0][0]
        second_delay = mock_sleep.call_args_list[1][0][0]
        self.assertLess(first_delay, second_delay)

if __name__ == "__main__":
    unittest.main()