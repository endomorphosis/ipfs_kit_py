"""
Test module for S3ControllerAnyIO in MCP server.

This module tests the S3ControllerAnyIO class that handles HTTP endpoints for S3 operations
with AnyIO support for asyncio and trio backends.
"""

import os
import tempfile
import json
from unittest.mock import MagicMock, patch
from io import BytesIO

import pytest
import pytest_asyncio
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.testclient import TestClient

from ipfs_kit_py.mcp.controllers.storage.s3_controller import (
    S3UploadRequest, S3DownloadRequest, S3DeleteRequest,
    IPFSS3Request, S3IPFSRequest
)
from ipfs_kit_py.mcp.controllers.storage.s3_controller_anyio import S3ControllerAnyIO


@pytest.fixture
def mock_s3_model():
    """Create a mock S3 model with async methods."""
    model = MagicMock()
    
    # Configure async method mocks
    model.upload_file_async = MagicMock()
    model.download_file_async = MagicMock()
    model.list_objects_async = MagicMock()
    model.delete_object_async = MagicMock()
    model.ipfs_to_s3_async = MagicMock()
    model.s3_to_ipfs_async = MagicMock()
    model.get_stats_async = MagicMock()
    model.list_buckets_async = MagicMock()
    
    # Configure sync method mocks (should not be called in async context)
    model.upload_file = MagicMock()
    model.download_file = MagicMock()
    model.list_objects = MagicMock()
    model.delete_object = MagicMock()
    model.ipfs_to_s3 = MagicMock()
    model.s3_to_ipfs = MagicMock()
    model.get_stats = MagicMock()
    model.list_buckets = MagicMock()
    
    return model


@pytest.fixture
def s3_controller_anyio(mock_s3_model):
    """Create an S3ControllerAnyIO instance with a mock model."""
    controller = S3ControllerAnyIO(mock_s3_model)
    return controller


@pytest.fixture
def router():
    """Create a FastAPI router for testing."""
    return APIRouter()


@pytest.fixture
def test_app(s3_controller_anyio, router):
    """Create a FastAPI test app with the controller routes."""
    from fastapi import FastAPI
    
    app = FastAPI()
    s3_controller_anyio.register_routes(router)
    app.include_router(router)
    
    return app


@pytest.fixture
def test_client(test_app):
    """Create a test client for the FastAPI app."""
    return TestClient(test_app)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    dir_path = tempfile.mkdtemp()
    yield dir_path
    import shutil
    shutil.rmtree(dir_path, ignore_errors=True)


@pytest.fixture
def test_file(temp_dir):
    """Create a test file for upload tests."""
    file_path = os.path.join(temp_dir, "test_file.txt")
    with open(file_path, "w") as f:
        f.write("Test content for S3 upload")
    
    return file_path


@pytest.mark.anyio
async def test_initialization(mock_s3_model):
    """Test S3ControllerAnyIO initialization."""
    controller = S3ControllerAnyIO(mock_s3_model)
    assert controller.s3_model == mock_s3_model


def test_route_registration(s3_controller_anyio, router):
    """Test that routes are registered correctly."""
    # Register routes
    s3_controller_anyio.register_routes(router)
    
    # Get registered route paths
    route_paths = [route.path for route in router.routes]
    
    # Check core routes
    assert "/storage/s3/upload" in route_paths
    assert "/storage/s3/download" in route_paths
    assert "/storage/s3/list/{bucket}" in route_paths
    assert "/storage/s3/delete" in route_paths
    assert "/storage/s3/from_ipfs" in route_paths
    assert "/storage/s3/to_ipfs" in route_paths
    assert "/storage/s3/status" in route_paths
    assert "/storage/s3/buckets" in route_paths
    
    # Check backward compatibility routes
    assert "/s3/status" in route_paths


@pytest.mark.anyio
async def test_handle_upload_request_json(test_client, mock_s3_model, test_file):
    """Test handling JSON upload request."""
    # Configure mock response
    mock_s3_model.upload_file_async.return_value = {
        "success": True,
        "bucket": "test-bucket",
        "key": "test-key",
        "etag": "test-etag",
        "size_bytes": 100,
        "duration_ms": 50.5
    }
    
    # Create request data
    request_data = {
        "file_path": test_file,
        "bucket": "test-bucket",
        "key": "test-key",
        "metadata": {"test-key": "test-value"}
    }
    
    # Send request
    response = test_client.post("/storage/s3/upload", json=request_data)
    
    # Check response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["bucket"] == "test-bucket"
    assert response_data["key"] == "test-key"
    assert response_data["etag"] == "test-etag"
    assert response_data["size_bytes"] == 100
    
    # Check that the async model method was called with correct parameters
    mock_s3_model.upload_file_async.assert_called_once()
    args, kwargs = mock_s3_model.upload_file_async.call_args
    assert kwargs["file_path"] == test_file
    assert kwargs["bucket"] == "test-bucket"
    assert kwargs["key"] == "test-key"
    assert kwargs["metadata"] == {"test-key": "test-value"}
    
    # Verify that sync method was not called
    mock_s3_model.upload_file.assert_not_called()


@pytest.mark.anyio
async def test_handle_upload_request_form(test_client, mock_s3_model, test_file):
    """Test handling form-based upload request."""
    # Configure mock response
    mock_s3_model.upload_file_async.return_value = {
        "success": True,
        "bucket": "test-bucket",
        "key": "test-file.txt",
        "etag": "test-etag",
        "size_bytes": 100,
        "duration_ms": 50.5
    }
    
    # Create form data
    with open(test_file, "rb") as f:
        file_content = f.read()
    
    files = {
        "file": ("test-file.txt", file_content, "text/plain")
    }
    form_data = {
        "bucket": "test-bucket",
        "metadata": json.dumps({"test-key": "test-value"})
    }
    
    # Send request
    response = test_client.post(
        "/storage/s3/upload",
        files=files,
        data=form_data
    )
    
    # Check response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["bucket"] == "test-bucket"
    assert response_data["key"] == "test-file.txt"
    
    # Check that the async model method was called
    mock_s3_model.upload_file_async.assert_called_once()
    
    # Verify that sync method was not called
    mock_s3_model.upload_file.assert_not_called()


@pytest.mark.anyio
async def test_handle_upload_request_error(test_client, mock_s3_model, test_file):
    """Test handling upload request with error response."""
    # Configure mock to return error
    mock_s3_model.upload_file_async.return_value = {
        "success": False,
        "error": "S3 upload failed",
        "error_type": "S3Error"
    }
    
    # Create request data
    request_data = {
        "file_path": test_file,
        "bucket": "test-bucket",
        "key": "test-key"
    }
    
    # Send request
    response = test_client.post("/storage/s3/upload", json=request_data)
    
    # Check response
    assert response.status_code == 500
    response_data = response.json()
    assert response_data["detail"]["error"] == "S3 upload failed"
    assert response_data["detail"]["error_type"] == "S3Error"
    
    # Verify that sync method was not called
    mock_s3_model.upload_file.assert_not_called()


@pytest.mark.anyio
async def test_handle_download_request(test_client, mock_s3_model):
    """Test handling download request."""
    # Configure mock response
    mock_s3_model.download_file_async.return_value = {
        "success": True,
        "bucket": "test-bucket",
        "key": "test-key",
        "destination": "/tmp/test-download.txt",
        "size_bytes": 100,
        "duration_ms": 50.5
    }
    
    # Create request data
    request_data = {
        "bucket": "test-bucket",
        "key": "test-key",
        "destination": "/tmp/test-download.txt"
    }
    
    # Send request
    response = test_client.post("/storage/s3/download", json=request_data)
    
    # Check response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["bucket"] == "test-bucket"
    assert response_data["key"] == "test-key"
    assert response_data["destination"] == "/tmp/test-download.txt"
    
    # Check that the async model method was called with correct parameters
    mock_s3_model.download_file_async.assert_called_once_with(
        bucket="test-bucket",
        key="test-key",
        destination="/tmp/test-download.txt"
    )
    
    # Verify that sync method was not called
    mock_s3_model.download_file.assert_not_called()


@pytest.mark.anyio
async def test_handle_list_request(test_client, mock_s3_model):
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
    mock_s3_model.list_objects_async.return_value = {
        "success": True,
        "bucket": "test-bucket",
        "prefix": "test-prefix",
        "objects": mock_objects,
        "count": 2,
        "duration_ms": 50.5
    }
    
    # Send request
    response = test_client.get("/storage/s3/list/test-bucket?prefix=test-prefix")
    
    # Check response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["bucket"] == "test-bucket"
    assert response_data["prefix"] == "test-prefix"
    assert response_data["count"] == 2
    assert len(response_data["objects"]) == 2
    
    # Check that the async model method was called with correct parameters
    mock_s3_model.list_objects_async.assert_called_once_with(
        bucket="test-bucket",
        prefix="test-prefix"
    )
    
    # Verify that sync method was not called
    mock_s3_model.list_objects.assert_not_called()


@pytest.mark.anyio
async def test_handle_delete_request(test_client, mock_s3_model):
    """Test handling delete request."""
    # Configure mock response
    mock_s3_model.delete_object_async.return_value = {
        "success": True,
        "bucket": "test-bucket",
        "key": "test-key",
        "duration_ms": 50.5
    }
    
    # Create request data
    request_data = {
        "bucket": "test-bucket",
        "key": "test-key"
    }
    
    # Send request
    response = test_client.post("/storage/s3/delete", json=request_data)
    
    # Check response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["bucket"] == "test-bucket"
    assert response_data["key"] == "test-key"
    
    # Check that the async model method was called with correct parameters
    mock_s3_model.delete_object_async.assert_called_once_with(
        bucket="test-bucket",
        key="test-key"
    )
    
    # Verify that sync method was not called
    mock_s3_model.delete_object.assert_not_called()


@pytest.mark.anyio
async def test_handle_ipfs_to_s3_request(test_client, mock_s3_model):
    """Test handling IPFS to S3 request."""
    # Configure mock response
    mock_s3_model.ipfs_to_s3_async.return_value = {
        "success": True,
        "ipfs_cid": "test-cid",
        "bucket": "test-bucket",
        "key": "test-key",
        "etag": "test-etag",
        "size_bytes": 100,
        "duration_ms": 50.5
    }
    
    # Create request data
    request_data = {
        "cid": "test-cid",
        "bucket": "test-bucket",
        "key": "test-key",
        "pin": True
    }
    
    # Send request
    response = test_client.post("/storage/s3/from_ipfs", json=request_data)
    
    # Check response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["ipfs_cid"] == "test-cid"
    assert response_data["bucket"] == "test-bucket"
    assert response_data["key"] == "test-key"
    
    # Check that the async model method was called with correct parameters
    mock_s3_model.ipfs_to_s3_async.assert_called_once_with(
        cid="test-cid",
        bucket="test-bucket",
        key="test-key",
        pin=True
    )
    
    # Verify that sync method was not called
    mock_s3_model.ipfs_to_s3.assert_not_called()


@pytest.mark.anyio
async def test_handle_s3_to_ipfs_request(test_client, mock_s3_model):
    """Test handling S3 to IPFS request."""
    # Configure mock response
    mock_s3_model.s3_to_ipfs_async.return_value = {
        "success": True,
        "bucket": "test-bucket",
        "key": "test-key",
        "ipfs_cid": "test-cid",
        "size_bytes": 100,
        "duration_ms": 50.5
    }
    
    # Create request data
    request_data = {
        "bucket": "test-bucket",
        "key": "test-key",
        "pin": True
    }
    
    # Send request
    response = test_client.post("/storage/s3/to_ipfs", json=request_data)
    
    # Check response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["bucket"] == "test-bucket"
    assert response_data["key"] == "test-key"
    assert response_data["ipfs_cid"] == "test-cid"
    
    # Check that the async model method was called with correct parameters
    mock_s3_model.s3_to_ipfs_async.assert_called_once_with(
        bucket="test-bucket",
        key="test-key",
        pin=True
    )
    
    # Verify that sync method was not called
    mock_s3_model.s3_to_ipfs.assert_not_called()


@pytest.mark.anyio
async def test_handle_status_request(test_client, mock_s3_model):
    """Test handling status request."""
    # Configure mock response
    mock_s3_model.get_stats_async.return_value = {
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
    response = test_client.get("/storage/s3/status")
    
    # Check response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["backend"] == "s3"
    assert response_data["is_available"] is True
    assert "stats" in response_data
    
    # Check that the async model method was called
    mock_s3_model.get_stats_async.assert_called_once()
    
    # Verify that sync method was not called
    mock_s3_model.get_stats.assert_not_called()


@pytest.mark.anyio
async def test_handle_list_buckets_request(test_client, mock_s3_model):
    """Test handling list buckets request."""
    # Configure mock response
    mock_s3_model.list_buckets_async.return_value = {
        "success": True,
        "buckets": ["bucket1", "bucket2", "bucket3"],
        "count": 3,
        "duration_ms": 50.5
    }
    
    # Send request
    response = test_client.get("/storage/s3/buckets")
    
    # Check response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    assert response_data["buckets"] == ["bucket1", "bucket2", "bucket3"]
    assert response_data["count"] == 3
    
    # Check that the async model method was called
    mock_s3_model.list_buckets_async.assert_called_once()
    
    # Verify that sync method was not called
    mock_s3_model.list_buckets.assert_not_called()


@pytest.mark.anyio
async def test_handle_upload_request_validation_error(test_client):
    """Test handling upload request with validation error."""
    # Send request without required fields
    response = test_client.post("/storage/s3/upload", json={})
    
    # Check response
    assert response.status_code == 400
    assert "error" in response.json()["detail"]


@pytest.mark.anyio
async def test_handle_download_request_error(test_client, mock_s3_model):
    """Test handling download request with error response."""
    # Configure mock to return error
    mock_s3_model.download_file_async.return_value = {
        "success": False,
        "error": "S3 download failed",
        "error_type": "S3Error"
    }
    
    # Create request data
    request_data = {
        "bucket": "test-bucket",
        "key": "test-key",
        "destination": "/tmp/test-download.txt"
    }
    
    # Send request
    response = test_client.post("/storage/s3/download", json=request_data)
    
    # Check response
    assert response.status_code == 500
    response_data = response.json()
    assert response_data["detail"]["error"] == "S3 download failed"
    assert response_data["detail"]["error_type"] == "S3Error"


@pytest.mark.anyio
async def test_handle_list_request_error(test_client, mock_s3_model):
    """Test handling list request with error response."""
    # Configure mock to return error
    mock_s3_model.list_objects_async.return_value = {
        "success": False,
        "error": "S3 list failed",
        "error_type": "S3Error"
    }
    
    # Send request
    response = test_client.get("/storage/s3/list/test-bucket")
    
    # Check response
    assert response.status_code == 500
    response_data = response.json()
    assert response_data["detail"]["error"] == "S3 list failed"
    assert response_data["detail"]["error_type"] == "S3Error"


@pytest.mark.anyio
async def test_handle_delete_request_error(test_client, mock_s3_model):
    """Test handling delete request with error response."""
    # Configure mock to return error
    mock_s3_model.delete_object_async.return_value = {
        "success": False,
        "error": "S3 delete failed",
        "error_type": "S3Error"
    }
    
    # Create request data
    request_data = {
        "bucket": "test-bucket",
        "key": "test-key"
    }
    
    # Send request
    response = test_client.post("/storage/s3/delete", json=request_data)
    
    # Check response
    assert response.status_code == 500
    response_data = response.json()
    assert response_data["detail"]["error"] == "S3 delete failed"
    assert response_data["detail"]["error_type"] == "S3Error"


@pytest.mark.anyio
async def test_handle_ipfs_to_s3_request_error(test_client, mock_s3_model):
    """Test handling IPFS to S3 request with error response."""
    # Configure mock to return error
    mock_s3_model.ipfs_to_s3_async.return_value = {
        "success": False,
        "error": "IPFS to S3 transfer failed",
        "error_type": "TransferError"
    }
    
    # Create request data
    request_data = {
        "cid": "test-cid",
        "bucket": "test-bucket",
        "key": "test-key",
        "pin": True
    }
    
    # Send request
    response = test_client.post("/storage/s3/from_ipfs", json=request_data)
    
    # Check response
    assert response.status_code == 500
    response_data = response.json()
    assert response_data["detail"]["error"] == "IPFS to S3 transfer failed"
    assert response_data["detail"]["error_type"] == "TransferError"


@pytest.mark.anyio
async def test_handle_s3_to_ipfs_request_error(test_client, mock_s3_model):
    """Test handling S3 to IPFS request with error response."""
    # Configure mock to return error
    mock_s3_model.s3_to_ipfs_async.return_value = {
        "success": False,
        "error": "S3 to IPFS transfer failed",
        "error_type": "TransferError"
    }
    
    # Create request data
    request_data = {
        "bucket": "test-bucket",
        "key": "test-key",
        "pin": True
    }
    
    # Send request
    response = test_client.post("/storage/s3/to_ipfs", json=request_data)
    
    # Check response
    assert response.status_code == 500
    response_data = response.json()
    assert response_data["detail"]["error"] == "S3 to IPFS transfer failed"
    assert response_data["detail"]["error_type"] == "TransferError"


@pytest.mark.anyio
async def test_handle_backward_compatibility_routes(test_client, mock_s3_model):
    """Test that backward compatibility routes work correctly."""
    # Configure mock response
    mock_s3_model.get_stats_async.return_value = {
        "backend_name": "S3",
        "operation_stats": {
            "upload_count": 10,
            "download_count": 5
        },
        "timestamp": 1672531600.0
    }
    
    # Send request to old status endpoint
    response = test_client.get("/s3/status")
    
    # Check response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["success"] is True
    
    # Check that the async model method was called
    mock_s3_model.get_stats_async.assert_called_once()
    
    # Verify that sync method was not called
    mock_s3_model.get_stats.assert_not_called()