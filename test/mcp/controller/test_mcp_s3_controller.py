"""
Test module for S3Controller in MCP server.

This module tests the S3Controller class that handles HTTP endpoints for S3 operations.
"""

import os
import tempfile
import json
import unittest
from unittest.mock import MagicMock, patch
from io import BytesIO

import pytest
from fastapi import APIRouter, UploadFile
from fastapi.testclient import TestClient

from ipfs_kit_py.mcp.controllers.storage.s3_controller import (
    S3Controller, S3UploadRequest, S3DownloadRequest,
    S3ListRequest, S3DeleteRequest, IPFSS3Request, S3IPFSRequest
)


class TestS3Controller(unittest.TestCase):
    """Test cases for S3Controller."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock S3 model
        self.mock_s3_model = MagicMock()

        # Create S3Controller with mock model
        self.controller = S3Controller(self.mock_s3_model)

        # Create FastAPI router and register routes
        self.router = APIRouter()
        self.controller.register_routes(self.router)

        # Create test app with router
        from fastapi import FastAPI
        self.app = FastAPI()
        self.app.include_router(self.router)

        # Create test client
        self.client = TestClient(self.app)

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
        """Test S3Controller initialization."""
        # Check that model is properly stored
        self.assertEqual(self.controller.s3_model, self.mock_s3_model)

    def test_route_registration(self):
        """Test that routes are registered correctly."""
        # Check that routes are registered
        route_paths = [route.path for route in self.router.routes]

        # Check core routes
        self.assertIn("/storage/s3/upload", route_paths)
        self.assertIn("/storage/s3/download", route_paths)
        self.assertIn("/storage/s3/list/{bucket}", route_paths)
        self.assertIn("/storage/s3/delete", route_paths)
        self.assertIn("/storage/s3/from_ipfs", route_paths)
        self.assertIn("/storage/s3/to_ipfs", route_paths)
        self.assertIn("/storage/s3/status", route_paths)
        self.assertIn("/storage/s3/buckets", route_paths)

        # Check backward compatibility routes
        self.assertIn("/s3/status", route_paths)

    def test_handle_upload_request_json(self):
        """Test handling upload request with JSON body."""
        # Configure mock response
        self.mock_s3_model.upload_file.return_value = {
            "success": True,
            "bucket": "test-bucket",
            "key": "test-key",
            "etag": "test-etag",
            "size_bytes": 100,
            "duration_ms": 50.5
        }

        # Create request
        request_data = {
            "file_path": self.test_file_path,
            "bucket": "test-bucket",
            "key": "test-key",
            "metadata": {"test-key": "test-value"}
        }

        # Send request
        response = self.client.post("/storage/s3/upload", json=request_data)

        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["bucket"], "test-bucket")
        self.assertEqual(response_data["key"], "test-key")
        self.assertEqual(response_data["etag"], "test-etag")
        self.assertEqual(response_data["size_bytes"], 100)

        # Check that model was called with correct parameters
        self.mock_s3_model.upload_file.assert_called_once_with(
            file_path=self.test_file_path,
            bucket="test-bucket",
            key="test-key",
            metadata={"test-key": "test-value"}
        )

    def test_handle_upload_request_form(self):
        """Test handling upload request with form data."""
        # Configure mock response
        self.mock_s3_model.upload_file.return_value = {
            "success": True,
            "bucket": "test-bucket",
            "key": "test-file.txt",
            "etag": "test-etag",
            "size_bytes": 100,
            "duration_ms": 50.5
        }

        # Create form data
        with open(self.test_file_path, "rb") as f:
            file_content = f.read()

        files = {
            "file": ("test-file.txt", file_content, "text/plain")
        }
        form_data = {
            "bucket": "test-bucket",
            "metadata": json.dumps({"test-key": "test-value"})
        }

        # Setup patching for temp file handling
        with patch("tempfile.NamedTemporaryFile") as mock_temp_file, \
             patch("os.unlink") as mock_unlink:

            # Configure mock temporary file
            mock_file = MagicMock()
            mock_file.name = "/tmp/test-temp-file"
            mock_temp_file.return_value.__enter__.return_value = mock_file

            # Send request
            response = self.client.post(
                "/storage/s3/upload",
                files=files,
                data=form_data
            )

            # Check that temp file was created and removed
            mock_temp_file.assert_called_once()
            mock_unlink.assert_called_once_with("/tmp/test-temp-file")

        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["bucket"], "test-bucket")

        # Check that model was called (can't check exact parameters due to temp file)
        self.mock_s3_model.upload_file.assert_called_once()

    def test_handle_upload_request_error(self):
        """Test handling upload request with error response."""
        # Configure mock to return error
        self.mock_s3_model.upload_file.return_value = {
            "success": False,
            "error": "S3 upload failed",
            "error_type": "S3Error"
        }

        # Create request
        request_data = {
            "file_path": self.test_file_path,
            "bucket": "test-bucket",
            "key": "test-key"
        }

        # Send request
        response = self.client.post("/storage/s3/upload", json=request_data)

        # Check response
        self.assertEqual(response.status_code, 500)
        response_data = response.json()
        self.assertEqual(response_data["detail"]["error"], "S3 upload failed")
        self.assertEqual(response_data["detail"]["error_type"], "S3Error")

    def test_handle_download_request(self):
        """Test handling download request."""
        # Configure mock response
        self.mock_s3_model.download_file.return_value = {
            "success": True,
            "bucket": "test-bucket",
            "key": "test-key",
            "destination": "/tmp/test-download.txt",
            "size_bytes": 100,
            "duration_ms": 50.5
        }

        # Create request
        request_data = {
            "bucket": "test-bucket",
            "key": "test-key",
            "destination": "/tmp/test-download.txt"
        }

        # Send request
        response = self.client.post("/storage/s3/download", json=request_data)

        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["bucket"], "test-bucket")
        self.assertEqual(response_data["key"], "test-key")
        self.assertEqual(response_data["destination"], "/tmp/test-download.txt")

        # Check that model was called with correct parameters
        self.mock_s3_model.download_file.assert_called_once_with(
            bucket="test-bucket",
            key="test-key",
            destination="/tmp/test-download.txt"
        )

    def test_handle_list_request(self):
        """Test handling list request."""
        # Configure mock response
        mock_objects = [
            {
                "key": "test-key-1",
                "e_tag": "test-etag-1",
                "last_modified": "2022-01-01T00:00:00Z",
                "size": 100
            },
            {
                "key": "test-key-2",
                "e_tag": "test-etag-2",
                "last_modified": "2022-01-02T00:00:00Z",
                "size": 200
            }
        ]
        self.mock_s3_model.list_objects.return_value = {
            "success": True,
            "bucket": "test-bucket",
            "prefix": "test-prefix",
            "objects": mock_objects,
            "count": 2,
            "duration_ms": 50.5
        }

        # Send request
        response = self.client.get("/storage/s3/list/test-bucket?prefix=test-prefix")

        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["bucket"], "test-bucket")
        self.assertEqual(response_data["prefix"], "test-prefix")
        self.assertEqual(response_data["count"], 2)
        self.assertEqual(len(response_data["objects"]), 2)

        # Check that model was called with correct parameters
        self.mock_s3_model.list_objects.assert_called_once_with(
            bucket="test-bucket",
            prefix="test-prefix"
        )

    def test_handle_delete_request(self):
        """Test handling delete request."""
        # Configure mock response
        self.mock_s3_model.delete_object.return_value = {
            "success": True,
            "bucket": "test-bucket",
            "key": "test-key",
            "duration_ms": 50.5
        }

        # Create request
        request_data = {
            "bucket": "test-bucket",
            "key": "test-key"
        }

        # Send request
        response = self.client.post("/storage/s3/delete", json=request_data)

        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["bucket"], "test-bucket")
        self.assertEqual(response_data["key"], "test-key")

        # Check that model was called with correct parameters
        self.mock_s3_model.delete_object.assert_called_once_with(
            bucket="test-bucket",
            key="test-key"
        )

    def test_handle_ipfs_to_s3_request(self):
        """Test handling IPFS to S3 request."""
        # Configure mock response
        self.mock_s3_model.ipfs_to_s3.return_value = {
            "success": True,
            "ipfs_cid": "test-cid",
            "bucket": "test-bucket",
            "key": "test-key",
            "etag": "test-etag",
            "size_bytes": 100,
            "duration_ms": 50.5
        }

        # Create request
        request_data = {
            "cid": "test-cid",
            "bucket": "test-bucket",
            "key": "test-key",
            "pin": True
        }

        # Send request
        response = self.client.post("/storage/s3/from_ipfs", json=request_data)

        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["ipfs_cid"], "test-cid")
        self.assertEqual(response_data["bucket"], "test-bucket")
        self.assertEqual(response_data["key"], "test-key")

        # Check that model was called with correct parameters
        self.mock_s3_model.ipfs_to_s3.assert_called_once_with(
            cid="test-cid",
            bucket="test-bucket",
            key="test-key",
            pin=True
        )

    def test_handle_s3_to_ipfs_request(self):
        """Test handling S3 to IPFS request."""
        # Configure mock response
        self.mock_s3_model.s3_to_ipfs.return_value = {
            "success": True,
            "bucket": "test-bucket",
            "key": "test-key",
            "ipfs_cid": "test-cid",
            "size_bytes": 100,
            "duration_ms": 50.5
        }

        # Create request
        request_data = {
            "bucket": "test-bucket",
            "key": "test-key",
            "pin": True
        }

        # Send request
        response = self.client.post("/storage/s3/to_ipfs", json=request_data)

        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["bucket"], "test-bucket")
        self.assertEqual(response_data["key"], "test-key")
        self.assertEqual(response_data["ipfs_cid"], "test-cid")

        # Check that model was called with correct parameters
        self.mock_s3_model.s3_to_ipfs.assert_called_once_with(
            bucket="test-bucket",
            key="test-key",
            pin=True
        )

    def test_handle_status_request(self):
        """Test handling status request."""
        # Configure mock response
        self.mock_s3_model.get_stats.return_value = {
            "backend_name": "S3",
            "operation_stats": {
                "upload_count": 10,
                "download_count": 5,
                "list_count": 2,
                "delete_count": 1,
                "success_count": 18,
                "failure_count": 0,
                "bytes_uploaded": 1000,
                "bytes_downloaded": 500,
                "start_time": 1672531200.0,
                "last_operation_time": 1672531500.0
            },
            "timestamp": 1672531600.0,
            "uptime_seconds": 400.0
        }

        # Send request
        response = self.client.get("/storage/s3/status")

        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["backend"], "s3")
        self.assertTrue(response_data["is_available"])
        self.assertIn("stats", response_data)

        # Check that model was called
        self.mock_s3_model.get_stats.assert_called_once()

    def test_handle_list_buckets_request(self):
        """Test handling list buckets request."""
        # Configure mock response
        self.mock_s3_model.list_buckets.return_value = {
            "success": True,
            "buckets": ["bucket1", "bucket2", "bucket3"],
            "count": 3,
            "duration_ms": 50.5
        }

        # Send request
        response = self.client.get("/storage/s3/buckets")

        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["buckets"], ["bucket1", "bucket2", "bucket3"])
        self.assertEqual(response_data["count"], 3)

        # Check that model was called
        self.mock_s3_model.list_buckets.assert_called_once()

    def test_handle_upload_request_validation_error(self):
        """Test handling upload request with validation error."""
        # Send request without required fields
        response = self.client.post("/storage/s3/upload", json={})

        # Check response
        self.assertEqual(response.status_code, 400)

    def test_handle_backward_compatibility_routes(self):
        """Test that backward compatibility routes work correctly."""
        # Configure mock response
        self.mock_s3_model.get_stats.return_value = {
            "backend_name": "S3",
            "operation_stats": {
                "upload_count": 10,
                "download_count": 5
            },
            "timestamp": 1672531600.0
        }

        # Send request to old status endpoint
        response = self.client.get("/s3/status")

        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])

        # Check that model was called
        self.mock_s3_model.get_stats.assert_called_once()


if __name__ == "__main__":
    unittest.main()
