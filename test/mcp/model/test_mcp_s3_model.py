"""
Test module for S3Model in MCP server.

This module tests the S3Model class that provides business logic for S3 operations.
"""

import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

import pytest

from ipfs_kit_py.mcp.models.storage.s3_model import S3Model


class TestS3Model(unittest.TestCase):
    """Test cases for S3Model."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock dependencies
        self.mock_s3_kit = MagicMock()
        self.mock_ipfs_model = MagicMock()
        self.mock_cache_manager = MagicMock()
        self.mock_credential_manager = MagicMock()

        # Configure credential manager to return test credentials
        self.mock_credential_manager.get_credentials.return_value = {
            "accessKey": "test-access-key",
            "secretKey": "test-secret-key",
            "endpoint": "https://test-endpoint.example.com"
        }

        # Create S3Model instance with mock dependencies
        self.s3_model = S3Model(
            s3_kit_instance=self.mock_s3_kit,
            ipfs_model=self.mock_ipfs_model,
            cache_manager=self.mock_cache_manager,
            credential_manager=self.mock_credential_manager
        )

        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()

        # Create a test file
        self.test_file_path = os.path.join(self.temp_dir, "test_file.txt")
        with open(self.test_file_path, "w") as f:
            f.write("Test content for S3 upload")

    def tearDown(self):
        """Clean up test fixtures."""
        # Remove temporary directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        """Test S3Model initialization."""
        # Check that dependencies are properly stored
        self.assertEqual(self.s3_model.kit, self.mock_s3_kit)
        self.assertEqual(self.s3_model.ipfs_model, self.mock_ipfs_model)
        self.assertEqual(self.s3_model.cache_manager, self.mock_cache_manager)
        self.assertEqual(self.s3_model.credential_manager, self.mock_credential_manager)

        # Check that backend name is correct
        self.assertEqual(self.s3_model.backend_name, "S3")

        # Check that operation_stats is initialized
        self.assertIsNotNone(self.s3_model.operation_stats)
        self.assertEqual(self.s3_model.operation_stats["upload_count"], 0)
        self.assertEqual(self.s3_model.operation_stats["download_count"], 0)
        self.assertEqual(self.s3_model.operation_stats["list_count"], 0)
        self.assertEqual(self.s3_model.operation_stats["delete_count"], 0)

    def test_upload_file_success(self):
        """Test successful file upload to S3."""
        # Configure mock response
        self.mock_s3_kit.s3_ul_file.return_value = {
            "success": True,
            "key": "test-key",
            "e_tag": "test-etag",
            "last_modified": time.time(),
            "size": 100
        }

        # Upload file
        result = self.s3_model.upload_file(
            file_path=self.test_file_path,
            bucket="test-bucket",
            key="test-key"
        )

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["bucket"], "test-bucket")
        self.assertEqual(result["key"], "test-key")
        self.assertIn("duration_ms", result)

        # Check that s3_kit was called with correct parameters
        self.mock_s3_kit.s3_ul_file.assert_called_once_with(
            self.test_file_path, "test-bucket", "test-key", None
        )

        # Check that operation stats were updated
        self.assertEqual(self.s3_model.operation_stats["upload_count"], 1)
        self.assertEqual(self.s3_model.operation_stats["success_count"], 1)

    def test_upload_file_failure_invalid_params(self):
        """Test file upload with invalid parameters."""
        # Test with non-existent file
        result = self.s3_model.upload_file(
            file_path="/non/existent/file.txt",
            bucket="test-bucket",
            key="test-key"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "FileNotFoundError")

        # Test with empty bucket
        result = self.s3_model.upload_file(
            file_path=self.test_file_path,
            bucket="",
            key="test-key"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "ValidationError")

        # Test with empty key
        result = self.s3_model.upload_file(
            file_path=self.test_file_path,
            bucket="test-bucket",
            key=""
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "ValidationError")

    def test_upload_file_kit_error(self):
        """Test file upload with S3 kit error."""
        # Configure mock to return error
        self.mock_s3_kit.s3_ul_file.return_value = {
            "success": False,
            "error": "S3 upload failed",
            "error_type": "S3Error"
        }

        # Upload file
        result = self.s3_model.upload_file(
            file_path=self.test_file_path,
            bucket="test-bucket",
            key="test-key"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "S3Error")

        # Check that operation stats were updated correctly
        self.assertEqual(self.s3_model.operation_stats["upload_count"], 1)
        self.assertEqual(self.s3_model.operation_stats["failure_count"], 1)

    def test_download_file_success(self):
        """Test successful file download from S3."""
        # Create destination path
        dest_path = os.path.join(self.temp_dir, "downloaded.txt")

        # Configure mock response
        self.mock_s3_kit.s3_dl_file.return_value = {
            "success": True,
            "key": "test-key",
            "e_tag": "test-etag",
            "last_modified": time.time(),
            "size": 100,
            "local_path": dest_path
        }

        # Download file
        result = self.s3_model.download_file(
            bucket="test-bucket",
            key="test-key",
            destination=dest_path
        )

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["bucket"], "test-bucket")
        self.assertEqual(result["key"], "test-key")
        self.assertEqual(result["destination"], dest_path)
        self.assertIn("duration_ms", result)

        # Check that s3_kit was called with correct parameters
        self.mock_s3_kit.s3_dl_file.assert_called_once_with(
            "test-bucket", "test-key", dest_path
        )

        # Check that operation stats were updated
        self.assertEqual(self.s3_model.operation_stats["download_count"], 1)
        self.assertEqual(self.s3_model.operation_stats["success_count"], 1)

    def test_download_file_failure(self):
        """Test file download with S3 kit error."""
        # Create destination path
        dest_path = os.path.join(self.temp_dir, "downloaded.txt")

        # Configure mock to return error
        self.mock_s3_kit.s3_dl_file.return_value = {
            "success": False,
            "error": "S3 download failed",
            "error_type": "S3Error"
        }

        # Download file
        result = self.s3_model.download_file(
            bucket="test-bucket",
            key="test-key",
            destination=dest_path
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "S3Error")

        # Check that operation stats were updated correctly
        self.assertEqual(self.s3_model.operation_stats["download_count"], 1)
        self.assertEqual(self.s3_model.operation_stats["failure_count"], 1)

    def test_list_objects_success(self):
        """Test successful listing of objects in S3 bucket."""
        # Configure mock response
        mock_objects = [
            {
                "key": "test-key-1",
                "last_modified": time.time(),
                "size": 100,
                "e_tag": "test-etag-1"
            },
            {
                "key": "test-key-2",
                "last_modified": time.time(),
                "size": 200,
                "e_tag": "test-etag-2"
            }
        ]
        self.mock_s3_kit.s3_ls_dir.return_value = mock_objects

        # List objects
        result = self.s3_model.list_objects(
            bucket="test-bucket",
            prefix="test-prefix"
        )

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["bucket"], "test-bucket")
        self.assertEqual(result["prefix"], "test-prefix")
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["objects"]), 2)
        self.assertIn("duration_ms", result)

        # Check that s3_kit was called with correct parameters
        self.mock_s3_kit.s3_ls_dir.assert_called_once_with(
            "test-prefix", "test-bucket"
        )

        # Check that operation stats were updated
        self.assertEqual(self.s3_model.operation_stats["list_count"], 1)
        self.assertEqual(self.s3_model.operation_stats["success_count"], 1)

    def test_list_objects_empty_response(self):
        """Test listing objects with empty response."""
        # Configure mock response
        self.mock_s3_kit.s3_ls_dir.return_value = []

        # List objects
        result = self.s3_model.list_objects(
            bucket="test-bucket"
        )

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(len(result["objects"]), 0)

        # Check that s3_kit was called with correct parameters (empty prefix)
        self.mock_s3_kit.s3_ls_dir.assert_called_once_with(
            "", "test-bucket"
        )

    def test_list_objects_error(self):
        """Test listing objects with S3 kit error."""
        # Configure mock to return error
        self.mock_s3_kit.s3_ls_dir.return_value = {
            "success": False,
            "error": "S3 list failed",
            "error_type": "S3Error"
        }

        # List objects
        result = self.s3_model.list_objects(
            bucket="test-bucket"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "S3Error")

        # Check that operation stats were updated correctly
        self.assertEqual(self.s3_model.operation_stats["list_count"], 1)
        self.assertEqual(self.s3_model.operation_stats["failure_count"], 1)

    def test_delete_object_success(self):
        """Test successful deletion of object from S3."""
        # Configure mock response
        self.mock_s3_kit.s3_rm_file.return_value = {
            "key": "test-key",
            "e_tag": "test-etag",
            "last_modified": time.time(),
            "size": 100
        }

        # Delete object
        result = self.s3_model.delete_object(
            bucket="test-bucket",
            key="test-key"
        )

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["bucket"], "test-bucket")
        self.assertEqual(result["key"], "test-key")
        self.assertIn("etag", result)
        self.assertIn("duration_ms", result)

        # Check that s3_kit was called with correct parameters
        self.mock_s3_kit.s3_rm_file.assert_called_once_with(
            "test-key", "test-bucket"
        )

        # Check that operation stats were updated
        self.assertEqual(self.s3_model.operation_stats["delete_count"], 1)
        self.assertEqual(self.s3_model.operation_stats["success_count"], 1)

    def test_delete_object_error(self):
        """Test deletion of object with S3 kit error."""
        # Configure mock to return error
        self.mock_s3_kit.s3_rm_file.return_value = {
            "success": False,
            "error": "S3 delete failed",
            "error_type": "S3Error"
        }

        # Delete object
        result = self.s3_model.delete_object(
            bucket="test-bucket",
            key="test-key"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "S3Error")

        # Check that operation stats were updated correctly
        self.assertEqual(self.s3_model.operation_stats["delete_count"], 1)
        self.assertEqual(self.s3_model.operation_stats["failure_count"], 1)

    @patch("tempfile.NamedTemporaryFile")
    @patch("os.unlink")
    def test_ipfs_to_s3_success(self, mock_unlink, mock_named_temp_file):
        """Test successful transfer from IPFS to S3."""
        # Configure mock temporary file
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/test-temp-file"
        mock_named_temp_file.return_value.__enter__.return_value = mock_temp_file

        # Configure mock IPFS model
        self.mock_ipfs_model.get_content.return_value = {
            "success": True,
            "data": b"Test content from IPFS",
            "cid": "test-cid"
        }
        self.mock_ipfs_model.pin_content.return_value = {
            "success": True,
            "cid": "test-cid"
        }

        # Mock the upload_file method to return success
        with patch.object(self.s3_model, "upload_file") as mock_upload:
            mock_upload.return_value = {
                "success": True,
                "bucket": "test-bucket",
                "key": "test-key",
                "etag": "test-etag",
                "size_bytes": 100
            }

            # Transfer from IPFS to S3
            result = self.s3_model.ipfs_to_s3(
                cid="test-cid",
                bucket="test-bucket",
                key="test-key",
                pin=True
            )

            # Check result
            self.assertTrue(result["success"])
            self.assertEqual(result["ipfs_cid"], "test-cid")
            self.assertEqual(result["bucket"], "test-bucket")
            self.assertEqual(result["key"], "test-key")
            self.assertIn("duration_ms", result)

            # Check that IPFS model was called
            self.mock_ipfs_model.get_content.assert_called_once_with("test-cid")
            self.mock_ipfs_model.pin_content.assert_called_once_with("test-cid")

            # Check that upload_file was called with correct parameters
            mock_upload.assert_called_once_with(
                mock_temp_file.name,
                "test-bucket",
                "test-key",
                metadata={"ipfs_cid": "test-cid"}
            )

            # Check that temporary file was cleaned up
            mock_unlink.assert_called_once_with(mock_temp_file.name)

            # Check that operation stats were updated
            # Note: operation_stats are updated by _handle_operation_result which we're not testing directly

    @patch("tempfile.NamedTemporaryFile")
    @patch("os.unlink")
    def test_ipfs_to_s3_ipfs_error(self, mock_unlink, mock_named_temp_file):
        """Test IPFS to S3 transfer with IPFS error."""
        # Configure mock temporary file
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/test-temp-file"
        mock_named_temp_file.return_value.__enter__.return_value = mock_temp_file

        # Configure mock IPFS model to return error
        self.mock_ipfs_model.get_content.return_value = {
            "success": False,
            "error": "IPFS get failed",
            "error_type": "IPFSError"
        }

        # Transfer from IPFS to S3
        result = self.s3_model.ipfs_to_s3(
            cid="test-cid",
            bucket="test-bucket",
            key="test-key"
        )

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "IPFSError")
        self.assertIn("ipfs_result", result)

        # Check that temporary file was cleaned up
        mock_unlink.assert_called_once_with(mock_temp_file.name)

    @patch("tempfile.NamedTemporaryFile")
    @patch("os.unlink")
    def test_s3_to_ipfs_success(self, mock_unlink, mock_named_temp_file):
        """Test successful transfer from S3 to IPFS."""
        # Configure mock temporary file
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/test-temp-file"
        mock_named_temp_file.return_value.__enter__.return_value = mock_temp_file

        # Mock the download_file method to return success
        with patch.object(self.s3_model, "download_file") as mock_download:
            mock_download.return_value = {
                "success": True,
                "bucket": "test-bucket",
                "key": "test-key",
                "destination": mock_temp_file.name,
                "size_bytes": 100
            }

            # Mock file open and read
            mock_file_content = b"Test content from S3"
            mock_file = MagicMock()
            mock_file.__enter__.return_value.read.return_value = mock_file_content
            mock_open = MagicMock(return_value=mock_file)

            # Mock IPFS add content
            self.mock_ipfs_model.add_content.return_value = {
                "success": True,
                "cid": "test-cid"
            }

            # Mock IPFS pin content
            self.mock_ipfs_model.pin_content.return_value = {
                "success": True,
                "cid": "test-cid"
            }

            with patch("builtins.open", mock_open):
                # Transfer from S3 to IPFS
                result = self.s3_model.s3_to_ipfs(
                    bucket="test-bucket",
                    key="test-key",
                    pin=True
                )

                # Check result
                self.assertTrue(result["success"])
                self.assertEqual(result["bucket"], "test-bucket")
                self.assertEqual(result["key"], "test-key")
                self.assertEqual(result["ipfs_cid"], "test-cid")
                self.assertIn("duration_ms", result)

                # Check that download_file was called with correct parameters
                mock_download.assert_called_once_with(
                    "test-bucket", "test-key", mock_temp_file.name
                )

                # Check that IPFS model methods were called correctly
                self.mock_ipfs_model.add_content.assert_called_once()
                self.mock_ipfs_model.pin_content.assert_called_once_with("test-cid")

                # Check that temporary file was cleaned up
                mock_unlink.assert_called_once_with(mock_temp_file.name)

    def test_list_buckets_success(self):
        """Test successful listing of S3 buckets."""
        # Configure mock response
        self.mock_s3_kit.s3_list_buckets.return_value = {
            "success": True,
            "buckets": ["bucket1", "bucket2", "bucket3"]
        }

        # List buckets
        result = self.s3_model.list_buckets()

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 3)
        self.assertEqual(len(result["buckets"]), 3)
        self.assertIn("duration_ms", result)

        # Check that s3_kit was called
        self.mock_s3_kit.s3_list_buckets.assert_called_once()

        # Check that operation stats were updated
        self.assertEqual(self.s3_model.operation_stats["list_count"], 1)
        self.assertEqual(self.s3_model.operation_stats["success_count"], 1)

    def test_list_buckets_fallback(self):
        """Test bucket listing with fallback implementation."""
        # Remove s3_list_buckets from the mock
        del self.mock_s3_kit.s3_list_buckets

        # List buckets
        result = self.s3_model.list_buckets()

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        self.assertIn("warning", result)

        # Check that operation stats were updated
        self.assertEqual(self.s3_model.operation_stats["list_count"], 1)
        self.assertEqual(self.s3_model.operation_stats["success_count"], 1)

    def test_get_stats(self):
        """Test getting operation statistics."""
        # Perform some operations to update stats
        self.s3_model.operation_stats["upload_count"] = 5
        self.s3_model.operation_stats["download_count"] = 10
        self.s3_model.operation_stats["list_count"] = 3
        self.s3_model.operation_stats["delete_count"] = 2
        self.s3_model.operation_stats["success_count"] = 18
        self.s3_model.operation_stats["failure_count"] = 2
        self.s3_model.operation_stats["bytes_uploaded"] = 1000
        self.s3_model.operation_stats["bytes_downloaded"] = 2000

        # Get stats
        stats = self.s3_model.get_stats()

        # Check stats
        self.assertEqual(stats["backend_name"], "S3")
        self.assertEqual(stats["operation_stats"]["upload_count"], 5)
        self.assertEqual(stats["operation_stats"]["download_count"], 10)
        self.assertEqual(stats["operation_stats"]["list_count"], 3)
        self.assertEqual(stats["operation_stats"]["delete_count"], 2)
        self.assertEqual(stats["operation_stats"]["success_count"], 18)
        self.assertEqual(stats["operation_stats"]["failure_count"], 2)
        self.assertEqual(stats["operation_stats"]["bytes_uploaded"], 1000)
        self.assertEqual(stats["operation_stats"]["bytes_downloaded"], 2000)
        self.assertIn("timestamp", stats)
        self.assertIn("uptime_seconds", stats)

    def test_reset_stats(self):
        """Test resetting operation statistics."""
        # Perform some operations to update stats
        self.s3_model.operation_stats["upload_count"] = 5
        self.s3_model.operation_stats["download_count"] = 10
        self.s3_model.operation_stats["list_count"] = 3
        self.s3_model.operation_stats["delete_count"] = 2

        # Reset stats
        result = self.s3_model.reset()

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "reset_stats")
        self.assertEqual(result["backend_name"], "S3")

        # Check that previous stats are included
        self.assertEqual(result["previous_stats"]["upload_count"], 5)
        self.assertEqual(result["previous_stats"]["download_count"], 10)
        self.assertEqual(result["previous_stats"]["list_count"], 3)
        self.assertEqual(result["previous_stats"]["delete_count"], 2)

        # Check that stats were reset
        self.assertEqual(self.s3_model.operation_stats["upload_count"], 0)
        self.assertEqual(self.s3_model.operation_stats["download_count"], 0)
        self.assertEqual(self.s3_model.operation_stats["list_count"], 0)
        self.assertEqual(self.s3_model.operation_stats["delete_count"], 0)

    def test_health_check(self):
        """Test health check functionality."""
        # Run health check
        result = self.s3_model.health_check()

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "health_check")
        self.assertEqual(result["backend_name"], "S3")
        self.assertTrue(result["kit_available"])
        self.assertTrue(result["cache_available"])
        self.assertTrue(result["credential_available"])
        self.assertIn("duration_ms", result)

    def test_health_check_no_dependencies(self):
        """Test health check with missing dependencies."""
        # Create model with no dependencies
        model = S3Model()

        # Run health check
        result = model.health_check()

        # Check result
        self.assertFalse(result["success"])
        self.assertEqual(result["operation"], "health_check")
        self.assertEqual(result["backend_name"], "S3")
        self.assertFalse(result["kit_available"])
        self.assertFalse(result["cache_available"])
        self.assertFalse(result["credential_available"])


if __name__ == "__main__":
    unittest.main()
