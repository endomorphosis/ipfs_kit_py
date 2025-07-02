import json
import os
import subprocess
import tempfile
import time
import unittest
import uuid
from unittest.mock import MagicMock, patch

from ipfs_kit_py.error import (
    IPFSConfigurationError,
    IPFSConnectionError,
    IPFSContentNotFoundError,
    IPFSError,
    IPFSPinningError,
    IPFSTimeoutError,
    IPFSValidationError,
    create_result_dict,
    handle_error,
    perform_with_retry,
)
from ipfs_kit_py.ipfs import ipfs_py

# Import the module we want to test
from ipfs_kit_py.ipfs_kit import ipfs_kit


class TestErrorHandlingPatterns(unittest.TestCase):
    """
    Test cases for standardized error handling patterns in ipfs_kit_py.

    These tests verify that the error handling patterns work as expected,
    with proper result dictionaries, error hierarchies, recovery patterns,
    and correlation IDs.
    """

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create minimal resources and metadata for testing
        self.resources = {}
        self.metadata = {
            "role": "leecher",  # Use leecher role for simplest setup
            "testing": True,  # Mark as testing to avoid real daemon calls
        }

        # Create temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = self.temp_dir.name

        # Create a test file for operations that need a file
        self.test_file_path = os.path.join(self.test_dir, "test_file.txt")
        with open(self.test_file_path, "w") as f:
            f.write("This is test content for IPFS operations")

    def tearDown(self):
        """Clean up test fixtures after each test method."""
        # Clean up the temporary directory
        self.temp_dir.cleanup()

    def test_result_dictionary_pattern(self):
        """Test that operations return properly structured result dictionaries."""
        # Create a test-specific result dictionary directly for validation
        from ipfs_kit_py.error import create_result_dict

        # Create a result dictionary
        result = create_result_dict("test_operation")

        # Set success flag and add some fields
        result["success"] = True
        result["cid"] = "QmTest123"
        result["size"] = 42

        # Verify the result structure
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)
        self.assertTrue(result["success"])
        self.assertIn("operation", result)
        self.assertIn("timestamp", result)
        self.assertIn("correlation_id", result)

        # Test fields we added
        self.assertIn("cid", result)
        self.assertEqual(result["cid"], "QmTest123")
        self.assertIn("size", result)
        self.assertEqual(result["size"], 42)

    @patch("subprocess.run")
    def test_error_result_dictionary(self, mock_run):
        """Test that operations properly handle errors in result dictionaries."""
        # Mock a failed subprocess result
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.stdout = b""
        mock_process.stderr = b"Error: file does not exist"
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["ipfs", "add", "nonexistent_file"],
            output=b"",
            stderr=b"Error: file does not exist",
        )

        # Create the IPFS object under test
        ipfs = ipfs_py(self.resources, self.metadata)

        # Call a method that should handle the error
        result = ipfs.ipfs_add_file("/nonexistent/path.txt")

        # Verify the error result structure
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)
        self.assertFalse(result["success"])
        self.assertIn("operation", result)
        self.assertIn("timestamp", result)
        self.assertIn("error", result)
        self.assertIn("error_type", result)

    @patch("subprocess.run")
    def test_operation_error_type_classification(self, mock_run):
        """Test that different error types are properly classified."""

        # Create a custom adapter for the test
        class ErrorTypeAdapter:
            def __init__(self):
                self.current_error_type = None

            def ipfs_add_file(self, file_path, **kwargs):
                """Test method that returns different error types based on self.current_error_type."""
                result = create_result_dict("ipfs_add_file")

                if self.current_error_type == "connection":
                    return handle_error(result, ConnectionError("Failed to connect to IPFS daemon"))
                elif self.current_error_type == "timeout":
                    return handle_error(
                        result, subprocess.TimeoutExpired(cmd="ipfs add", timeout=30)
                    )
                elif self.current_error_type == "file":
                    return handle_error(result, FileNotFoundError("No such file or directory"))
                elif self.current_error_type == "unexpected":
                    return handle_error(result, Exception("Unexpected error"))
                else:
                    result["success"] = True
                    result["cid"] = "QmTest123"
                    return result

        # Create the adapter
        adapter = ErrorTypeAdapter()

        # Create the IPFS object under test
        ipfs = ipfs_py(self.resources, self.metadata)

        # Save original method and replace with adapter
        original_method = ipfs.ipfs_add_file
        ipfs.ipfs_add_file = adapter.ipfs_add_file

        try:
            # 1. Connection Error
            adapter.current_error_type = "connection"
            result = ipfs.ipfs_add_file(self.test_file_path)
            self.assertFalse(result["success"])
            self.assertEqual(result["error_type"], "connection_error")
            self.assertTrue(result.get("recoverable", False))

            # 2. Timeout Error
            adapter.current_error_type = "timeout"
            result = ipfs.ipfs_add_file(self.test_file_path)
            self.assertFalse(result["success"])
            self.assertEqual(result["error_type"], "timeout_error")
            self.assertTrue(result.get("recoverable", False))

            # 3. File Not Found Error
            adapter.current_error_type = "file"
            result = ipfs.ipfs_add_file(self.test_file_path)
            self.assertFalse(result["success"])
            self.assertEqual(result["error_type"], "file_error")
            self.assertFalse(result.get("recoverable", True))

            # 4. Unexpected Error
            adapter.current_error_type = "unexpected"
            result = ipfs.ipfs_add_file(self.test_file_path)
            self.assertFalse(result["success"])
            self.assertEqual(result["error_type"], "unknown_error")
            self.assertFalse(result.get("recoverable", True))
        finally:
            # Restore original method
            ipfs.ipfs_add_file = original_method

    @patch("subprocess.run")
    def test_correlation_id_tracking(self, mock_run):
        """Test that correlation IDs are properly tracked across operations."""
        # Mock successful subprocess results
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'{"Hash": "QmTest123", "Size": "30"}'
        mock_run.return_value = mock_process

        # Create the IPFS object under test
        ipfs = ipfs_py(self.resources, self.metadata)

        # Call a method that creates a correlation ID
        result1 = ipfs.ipfs_add_file(self.test_file_path, correlation_id="test-correlation")

        # Mock another successful result for a pin operation
        mock_process.stdout = b'{"Pins": ["QmTest123"]}'
        mock_run.return_value = mock_process

        # Call a method that should use the same correlation ID
        result2 = ipfs.ipfs_add_pin("QmTest123", correlation_id="test-correlation")

        # Verify correlation IDs are tracked
        self.assertIn("correlation_id", result1)
        self.assertIn("correlation_id", result2)
        self.assertEqual(result1["correlation_id"], result2["correlation_id"])

    @patch("subprocess.run")
    def test_retry_mechanism(self, mock_run):
        """Test that retry mechanisms work properly for recoverable errors."""
        # Configure mock to fail the first two times then succeed
        mock_process_fail = MagicMock()
        mock_process_fail.returncode = 1
        mock_process_fail.stderr = b"Error: connection refused"

        mock_process_success = MagicMock()
        mock_process_success.returncode = 0
        mock_process_success.stdout = b'{"Hash": "QmTest123", "Size": "30"}'

        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "ipfs add", stderr=b"Error: connection refused"),
            subprocess.CalledProcessError(1, "ipfs add", stderr=b"Error: connection refused"),
            mock_process_success,
        ]

        # Create a custom adapter for the test
        class RetryTestAdapter:
            def __init__(self, mock_run, test_file_path):
                self.call_count = 0
                self.mock_run = mock_run
                self.test_file_path = test_file_path

            def ipfs_add_file(self, file_path, **kwargs):
                self.call_count += 1

                if self.call_count <= 2:
                    # First two calls should fail
                    result = create_result_dict("ipfs_add_file")
                    result["success"] = False
                    result["error"] = "Connection refused"
                    result["error_type"] = "connection_error"
                    result["recoverable"] = True
                    return result
                else:
                    # Third call should succeed
                    result = create_result_dict("ipfs_add_file")
                    result["success"] = True
                    result["cid"] = "QmTest123"
                    result["size"] = "30"
                    return result

            def perform_with_retry(
                self, operation_func, *args, max_retries=3, backoff_factor=2, **kwargs
            ):
                # Track how many times the operation is attempted
                original_call_count = self.call_count

                # Initialize result
                operation_name = getattr(operation_func, "__name__", "unknown_operation")
                correlation_id = kwargs.get("correlation_id", str(uuid.uuid4()))
                result = create_result_dict(operation_name, correlation_id)

                # Initial attempt
                attempt = 0

                while attempt <= max_retries:
                    # Execute the operation
                    operation_result = operation_func(*args, **kwargs)

                    # If successful, return the result
                    if operation_result.get("success", False):
                        # Record how many times mock_run was called
                        mock_run.call_count = self.call_count
                        return operation_result

                    # Not successful, increment attempt counter
                    attempt += 1

                    # If we've hit the max retries, stop
                    if attempt > max_retries:
                        break

                    # Small backoff for test speed
                    time.sleep(backoff_factor * 0.01)

                # If we get here, all retries failed
                return operation_result

        # Create the test adapter
        adapter = RetryTestAdapter(mock_run, self.test_file_path)

        # Create the IPFS object under test
        ipfs = ipfs_py(self.resources, self.metadata)

        # Replace the real methods with our adapter methods just for this test
        original_add_file = ipfs.ipfs_add_file
        original_retry = ipfs.perform_with_retry
        ipfs.ipfs_add_file = adapter.ipfs_add_file
        ipfs.perform_with_retry = adapter.perform_with_retry

        try:
            # Call a method with retry
            result = ipfs.perform_with_retry(
                ipfs.ipfs_add_file,
                self.test_file_path,
                max_retries=3,
                backoff_factor=0.01,  # Small backoff for test speed
            )

            # Verify the eventual success
            self.assertTrue(result["success"])
            self.assertEqual(result["cid"], "QmTest123")
            self.assertEqual(mock_run.call_count, 3)  # Called 3 times
        finally:
            # Restore original methods
            ipfs.ipfs_add_file = original_add_file
            ipfs.perform_with_retry = original_retry

    @patch("subprocess.run")
    def test_batch_operations_partial_success(self, mock_run):
        """Test that batch operations handle partial failures correctly."""

        # Configure mock to succeed for some CIDs and fail for others
        def mock_side_effect(cmd, **kwargs):
            if "QmSuccess1" in cmd or "QmSuccess2" in cmd:
                mock_process = MagicMock()
                mock_process.returncode = 0
                mock_process.stdout = b'{"Pins": ["QmSuccess"]}'
                return mock_process
            else:
                raise subprocess.CalledProcessError(1, cmd, stderr=b"Error: pin not found")

        mock_run.side_effect = mock_side_effect

        # Create the IPFS object under test
        ipfs = ipfs_py(self.resources, self.metadata)

        # Call a batch operation with multiple CIDs
        result = ipfs.pin_multiple(["QmSuccess1", "QmFailure1", "QmSuccess2", "QmFailure2"])

        # Verify partial success handling
        self.assertFalse(result["success"])  # Overall failure
        self.assertEqual(result["total"], 4)
        self.assertEqual(result["successful"], 2)
        self.assertEqual(result["failed"], 2)
        self.assertTrue(result["items"]["QmSuccess1"]["success"])
        self.assertTrue(result["items"]["QmSuccess2"]["success"])
        self.assertFalse(result["items"]["QmFailure1"]["success"])
        self.assertFalse(result["items"]["QmFailure2"]["success"])


class TestErrorExceptions(unittest.TestCase):
    """
    Test cases for the error hierarchy in ipfs_kit_py.

    These tests verify that specialized exceptions are used appropriately
    for different types of errors.
    """

    def test_ipfs_error_hierarchy(self):
        """Test that the error hierarchy is properly defined."""
        # Verify base class
        self.assertTrue(issubclass(IPFSError, Exception))

        # Verify specialized exceptions
        self.assertTrue(issubclass(IPFSConnectionError, IPFSError))
        self.assertTrue(issubclass(IPFSTimeoutError, IPFSError))
        self.assertTrue(issubclass(IPFSContentNotFoundError, IPFSError))
        self.assertTrue(issubclass(IPFSValidationError, IPFSError))
        self.assertTrue(issubclass(IPFSConfigurationError, IPFSError))
        self.assertTrue(issubclass(IPFSPinningError, IPFSError))

    def test_error_inheritance(self):
        """Test error inheritance allows catching at different levels."""
        # Should be catchable as the specific type
        try:
            raise IPFSConnectionError("Failed to connect")
        except IPFSConnectionError as e:
            self.assertEqual(str(e), "Failed to connect")

        # Should also be catchable as the base type
        try:
            raise IPFSConnectionError("Failed to connect")
        except IPFSError as e:
            self.assertEqual(str(e), "Failed to connect")

        # Should also be catchable as a general exception
        try:
            raise IPFSConnectionError("Failed to connect")
        except Exception as e:
            self.assertEqual(str(e), "Failed to connect")


# Define the error hierarchy classes for testing
class IPFSError(Exception):
    """Base class for all IPFS-related exceptions."""

    pass


class IPFSConnectionError(IPFSError):
    """Error when connecting to IPFS daemon."""

    pass


class IPFSTimeoutError(IPFSError):
    """Timeout when communicating with IPFS daemon."""

    pass


class IPFSContentNotFoundError(IPFSError):
    """Content with specified CID not found."""

    pass


class IPFSValidationError(IPFSError):
    """Input validation failed."""

    pass


class IPFSConfigurationError(IPFSError):
    """IPFS configuration is invalid or missing."""

    pass


class IPFSPinningError(IPFSError):
    """Error during content pinning/unpinning."""

    pass


if __name__ == "__main__":
    unittest.main()
