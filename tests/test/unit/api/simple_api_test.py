"""
DEPRECATED: Simple unittest-based tests for the FastAPI server in api.py.

This file is now DEPRECATED in favor of test_api.py and test_simple_api.py, which use pytest.
These tests are kept for reference but are not expected to pass as they conflict
with the FastAPI implementation. DO NOT RUN these tests.
"""

# Import unittest and immediately mark all tests as skipped
import unittest

unittest.skip("Deprecated test file")

import anyio
import base64
import json
import unittest
from unittest.mock import MagicMock, patch

# We need to patch FastAPI imports before importing the module
with patch("ipfs_kit_py.api.FastAPI"), patch("ipfs_kit_py.api.uvicorn"), patch(
    "ipfs_kit_py.api.HTTPException"
), patch("ipfs_kit_py.api.CORSMiddleware"), patch("ipfs_kit_py.api.IPFSSimpleAPI"):
    # Only now import the module to test
    from ipfs_kit_py.api import (
        APIRequest,
        api_method,
        app,
        download_file,
        get_config,
        health_check,
        list_methods,
        upload_file,
    )


class AsyncTestCase(unittest.TestCase):
    """Base test case that supports running async tests with unittest."""

    def run_async(self, coro):
        """Run a coroutine and return its result."""
        return anyio.run(coro)


@unittest.skip("Deprecated test class")
class TestAPIEndpoints(AsyncTestCase):
    """DEPRECATED: Test cases for API endpoints."""

    def setUp(self):
        """Set up test fixtures before each test."""
        # Create a mock IPFS API
        self.mock_ipfs_api = MagicMock()

        # Mock results for different method calls
        self.mock_ipfs_api.return_value = {"success": True, "data": "mock_data"}

        # Mock get method to return bytes
        self.mock_ipfs_api.get.return_value = b"mock file content"

        # Mock add method
        self.mock_ipfs_api.add.return_value = {"success": True, "cid": "QmTestCid"}

        # Patch the IPFS API in the module
        patcher = patch("ipfs_kit_py.api.ipfs_api", self.mock_ipfs_api)
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_health_check(self):
        """Test health check endpoint."""
        response = self.run_async(health_check())
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["version"], "0.1.0")

    def test_api_method_success(self):
        """Test API method call with success."""
        # Create API request
        request = APIRequest(args=["arg1", "arg2"], kwargs={"key1": "value1"})

        # Call API method
        response = self.run_async(api_method("test_method", request))

        # Verify API method was called with correct arguments
        self.mock_ipfs_api.assert_called_once_with("test_method", "arg1", "arg2", key1="value1")

        # Verify response
        self.assertEqual(response["success"], True)
        self.assertEqual(response["data"], "mock_data")

    def test_api_method_bytes_response(self):
        """Test API method call with bytes response."""
        # Set up mock to return bytes
        self.mock_ipfs_api.return_value = b"binary data"

        # Create API request
        request = APIRequest()

        # Call API method
        response = self.run_async(api_method("binary_method", request))

        # Verify response encoding
        self.assertEqual(response["success"], True)
        self.assertEqual(response["encoding"], "base64")
        self.assertEqual(base64.b64decode(response["data"]), b"binary data")

    def test_api_method_ipfs_error(self):
        """Test API method call with IPFS error."""
        # Set up mock to raise IPFS error
        from ipfs_kit_py.error import IPFSError

        self.mock_ipfs_api.side_effect = IPFSError("Test IPFS error")

        # Create API request
        request = APIRequest()

        # Call API method
        response = self.run_async(api_method("error_method", request))

        # Verify error response
        self.assertEqual(response["success"], False)
        self.assertEqual(response["error"], "Test IPFS error")
        self.assertEqual(response["error_type"], "IPFSError")
        self.assertEqual(response["status_code"], 400)

    def test_api_method_unexpected_error(self):
        """Test API method call with unexpected error."""
        # Set up mock to raise unexpected error
        self.mock_ipfs_api.side_effect = ValueError("Unexpected error")

        # Create API request
        request = APIRequest()

        # Call API method
        response = self.run_async(api_method("error_method", request))

        # Verify error response
        self.assertEqual(response["success"], False)
        self.assertEqual(response["error"], "Unexpected error")
        self.assertEqual(response["error_type"], "ValueError")
        self.assertEqual(response["status_code"], 500)

    def test_upload_file(self):
        """Test file upload endpoint."""
        # Create mock request
        mock_request = MagicMock()
        mock_file = MagicMock()

        # Use an async function for read
        async def mock_read():
            return b"file content"

        mock_file.read = mock_read

        mock_form = MagicMock()
        mock_form.get = MagicMock(
            side_effect=lambda key, default=None: {
                "file": mock_file,
                "pin": "true",
                "wrap_with_directory": "false",
            }.get(key, default)
        )

        # Use an async function for form
        async def mock_form_async():
            return mock_form

        mock_request.form = mock_form_async

        # Call upload endpoint
        response = self.run_async(upload_file(mock_request))

        # Verify API method was called with correct arguments
        self.mock_ipfs_api.add.assert_called_once_with(
            b"file content", pin=True, wrap_with_directory=False
        )

        # Verify response
        self.assertEqual(response["success"], True)
        self.assertEqual(response["cid"], "QmTestCid")

    def test_upload_file_no_file(self):
        """Test file upload endpoint with no file."""
        # Create mock request with no file
        mock_request = MagicMock()
        mock_form = MagicMock()
        mock_form.get = MagicMock(return_value=None)

        # Use an async function for form
        async def mock_form_async():
            return mock_form

        mock_request.form = mock_form_async

        # Call upload endpoint
        response = self.run_async(upload_file(mock_request))

        # Verify error response
        self.assertEqual(response["success"], False)
        self.assertEqual(response["error_type"], "ValueError")
        self.assertEqual(response["status_code"], 500)

    def test_download_file(self):
        """Test file download endpoint."""
        # Call download endpoint
        response = self.run_async(download_file("QmTestCid"))

        # Verify API method was called with correct arguments
        self.mock_ipfs_api.get.assert_called_once_with("QmTestCid")

        # Verify response
        self.assertEqual(response.body, b"mock file content")
        self.assertEqual(response.media_type, "application/octet-stream")
        self.assertEqual(
            response.headers["Content-Disposition"], 'attachment; filename="QmTestCid"'
        )

    def test_download_file_with_filename(self):
        """Test file download endpoint with filename."""
        # Call download endpoint with filename
        response = self.run_async(download_file("QmTestCid", filename="test.txt"))

        # Verify response headers
        self.assertEqual(response.headers["Content-Disposition"], 'attachment; filename="test.txt"')

    def test_download_file_error(self):
        """Test file download endpoint with error."""
        # Set up mock to raise error
        self.mock_ipfs_api.get.side_effect = ValueError("Download error")

        # Call download endpoint
        response = self.run_async(download_file("QmTestCid"))

        # Verify error response
        self.assertEqual(response["success"], False)
        self.assertEqual(response["error"], "Download error")
        self.assertEqual(response["error_type"], "ValueError")
        self.assertEqual(response["status_code"], 500)

    def test_get_config(self):
        """Test config endpoint."""
        # Set up mock config
        self.mock_ipfs_api.config = {"role": "master", "timeouts": {"gateway": 30, "api": 60}}

        # Call config endpoint
        response = self.run_async(get_config())

        # Verify response
        self.assertEqual(response["role"], "master")
        self.assertEqual(response["version"], "0.1.0")
        self.assertEqual(response["features"]["cluster"], True)
        self.assertEqual(response["timeouts"], {"gateway": 30, "api": 60})

    def test_list_methods(self):
        """Test list methods endpoint."""
        # Set up mock methods
        self.mock_ipfs_api.add.__doc__ = "Add content to IPFS"
        self.mock_ipfs_api.get.__doc__ = "Get content from IPFS"
        self.mock_ipfs_api.pin.__doc__ = "Pin content in IPFS"

        # Set up mock extensions
        self.mock_ipfs_api.extensions = {"custom_extension": MagicMock(__doc__="Custom extension")}

        # Call list methods endpoint
        response = self.run_async(list_methods())

        # Verify response contains methods
        methods = response["methods"]
        self.assertGreaterEqual(len(methods), 3)  # At least the 3 methods we set up

        # Check if our methods are in the list
        method_names = [m["name"] for m in methods]
        self.assertIn("add", method_names)
        self.assertIn("get", method_names)
        self.assertIn("pin", method_names)
        self.assertIn("custom_extension", method_names)

        # Check if extension is marked correctly
        for method in methods:
            if method["name"] == "custom_extension":
                self.assertEqual(method["type"], "extension")


if __name__ == "__main__":
    unittest.main()
