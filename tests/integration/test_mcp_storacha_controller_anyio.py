"""
Test module for StorachaControllerAnyIO in MCP server.

This module tests the AnyIO version of StorachaController which provides
async/await support for both async-io and trio backends.
"""

import pytest
import tempfile
import os
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
import anyio
import time


@pytest.fixture
def mock_storacha_model():
    """Create a mock storacha model with async methods."""
    model = MagicMock()
    
    # Configure the get_stats method (used directly)
    model.get_stats = MagicMock()
    
    # Configure sync methods that will be used with anyio.to_thread.run_sync
    model.create_space = MagicMock()
    model.list_spaces = MagicMock()
    model.set_current_space = MagicMock()
    model.upload_file = MagicMock()
    model.upload_car = MagicMock()
    model.list_uploads = MagicMock()
    model.delete_upload = MagicMock()
    model.ipfs_to_storacha = MagicMock()
    model.storacha_to_ipfs = MagicMock()
    
    # These methods were added for compatibility but they shouldn't be used
    # in the AnyIO controller - keep them to prevent AttributeError
    model.create_space_async = MagicMock()
    model.list_spaces_async = MagicMock()
    model.set_current_space_async = MagicMock()
    model.upload_file_async = MagicMock()
    model.upload_car_async = MagicMock()
    model.list_uploads_async = MagicMock()
    model.delete_upload_async = MagicMock()
    model.ipfs_to_storacha_async = MagicMock()
    model.storacha_to_ipfs_async = MagicMock()
    
    return model


@pytest.fixture
def controller(mock_storacha_model):
    """Create StorachaControllerAnyIO instance with mock model."""
    from ipfs_kit_py.mcp.controllers.storage.storacha_controller_anyio import StorachaControllerAnyIO
    return StorachaControllerAnyIO(mock_storacha_model)


@pytest.fixture
def app(controller):
    """Create FastAPI app with controller routes."""
    app = FastAPI()
    router = APIRouter()
    controller.register_routes(router)
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def temp_test_file():
    """Create a temporary file for testing uploads."""
    temp_dir = tempfile.mkdtemp()
    test_file_path = os.path.join(temp_dir, "test_file.txt")
    with open(test_file_path, "w") as f:
        f.write("Test content for Storacha upload")
    
    yield test_file_path
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestStorachaControllerAnyIO:
    """Test cases for StorachaControllerAnyIO."""
    
    def test_initialization(self, controller, mock_storacha_model):
        """Test StorachaControllerAnyIO initialization."""
        assert controller.storacha_model == mock_storacha_model
    
    def test_route_registration(self, controller):
        """Test that routes are registered correctly."""
        router = APIRouter()
        controller.register_routes(router)
        
        # Extract route paths
        route_paths = [route.path for route in router.routes]
        
        # Check core endpoints
        assert "/storacha/space/create" in route_paths
        assert "/storacha/space/list" in route_paths
        assert "/storacha/space/set" in route_paths
        assert "/storacha/upload" in route_paths
        assert "/storacha/upload/car" in route_paths
        assert "/storacha/uploads" in route_paths
        assert "/storacha/delete" in route_paths
        assert "/storacha/from_ipfs" in route_paths
        assert "/storacha/to_ipfs" in route_paths
        assert "/storage/storacha/status" in route_paths
    
    @pytest.mark.anyio
    async def test_handle_status_request(self, client, mock_storacha_model):
        """Test handling status request."""
        # Configure mock response
        mock_storacha_model.get_stats.return_value = {
            "spaces_count": 2,
            "current_space": "did:web:example.storacha.web",
            "uploads_count": 10,
            "storage_used": 1024 * 1024
        }
        
        # Mock anyio.to_thread.run_sync to return the mock result
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # Configure the mock to return the value from our mocked method
            mock_run_sync.return_value = mock_storacha_model.get_stats.return_value
            
            # Send request
            response = client.get("/storage/storacha/status")
            
            # Check response - only check fields that we know are definitely in the response
            assert response.status_code == 200
            response_data = response.json()
            
            # Just check basic success flag and operation_id - these fields we know are present
            assert response_data["success"] is True
            assert "operation_id" in response_data
            assert "duration_ms" in response_data
            
            # Verify anyio.to_thread.run_sync was called with the right method
            mock_run_sync.assert_awaited_once_with(mock_storacha_model.get_stats)
    
    @pytest.mark.anyio
    async def test_handle_space_creation_request(self, client, mock_storacha_model):
        """Test handling space creation request."""
        # Configure mock response for the sync method that will be used with anyio.to_thread.run_sync
        mock_storacha_model.create_space.return_value = {
            "success": True,
            "space_did": "did:web:example.storacha.web",
            "name": "Test Space",
            "email": "test@example.com",
            "type": "personal",
            "space_info": {"key": "value"},
            "duration_ms": 50.5
        }
        
        # Create request
        request_data = {
            "name": "Test Space"
        }
        
        # Mock anyio.to_thread.run_sync to return the mock result
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # Configure the mock to return the value from our mocked method
            mock_run_sync.return_value = mock_storacha_model.create_space.return_value
            
            # Send request
            response = client.post("/storacha/space/create", json=request_data)
            
            # Check response
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert response_data["space_did"] == "did:web:example.storacha.web"
            assert response_data["name"] == "Test Space"
            assert response_data["email"] == "test@example.com"
            
            # Verify anyio.to_thread.run_sync was called with the right method and parameters
            mock_run_sync.assert_awaited_once()
            args, kwargs = mock_run_sync.call_args
            assert args[0] == mock_storacha_model.create_space
            assert kwargs.get("name") == "Test Space" or args[1] == "Test Space"
    
    @pytest.mark.anyio
    async def test_handle_list_spaces_request(self, client, mock_storacha_model):
        """Test handling list spaces request."""
        # Configure mock response for the sync method
        mock_spaces = [
            {
                "did": "did:web:example.storacha.web",
                "name": "Space 1",
                "current": True
            },
            {
                "did": "did:web:another.storacha.web",
                "name": "Space 2",
                "current": False
            }
        ]
        mock_storacha_model.list_spaces.return_value = {
            "success": True,
            "spaces": mock_spaces,
            "count": 2,
            "duration_ms": 50.5
        }
        
        # Mock anyio.to_thread.run_sync to return the mock result
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # Configure the mock to return the value from our mocked method
            mock_run_sync.return_value = mock_storacha_model.list_spaces.return_value
            
            # Send request
            response = client.get("/storacha/space/list")
            
            # Check response
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert response_data["count"] == 2
            assert len(response_data["spaces"]) == 2
            assert response_data["spaces"][0]["did"] == "did:web:example.storacha.web"
            
            # Verify anyio.to_thread.run_sync was called with the right method
            mock_run_sync.assert_awaited_once_with(mock_storacha_model.list_spaces)
    
    @pytest.mark.anyio
    async def test_handle_set_space_request(self, client, mock_storacha_model):
        """Test handling set space request."""
        # Configure mock response
        mock_storacha_model.set_current_space.return_value = {
            "success": True,
            "space_did": "did:web:example.storacha.web",
            "space_info": {"name": "Test Space", "email": "test@example.com"},
            "duration_ms": 50.5
        }
        
        # Create request
        request_data = {
            "space_did": "did:web:example.storacha.web"
        }
        
        # Mock anyio.to_thread.run_sync to return the mock result
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # Configure the mock to return the value from our mocked method
            mock_run_sync.return_value = mock_storacha_model.set_current_space.return_value
            
            # Send request
            response = client.post("/storacha/space/set", json=request_data)
            
            # Check response
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert response_data["space_did"] == "did:web:example.storacha.web"
            assert response_data["space_info"]["name"] == "Test Space"
            
            # Verify anyio.to_thread.run_sync was called with the right method and parameters
            mock_run_sync.assert_awaited_once()
            args, kwargs = mock_run_sync.call_args
            assert args[0] == mock_storacha_model.set_current_space
            assert kwargs.get("space_did") == "did:web:example.storacha.web" or args[1] == "did:web:example.storacha.web"
    
    @pytest.mark.anyio
    async def test_handle_upload_request(self, client, mock_storacha_model, temp_test_file):
        """Test handling upload request."""
        # Configure mock response
        mock_storacha_model.upload_file.return_value = {
            "success": True,
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "size_bytes": 100,
            "root_cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "shard_size": 100,
            "upload_id": "12345",
            "space_did": "did:web:example.storacha.web",
            "duration_ms": 50.5
        }
        
        # Create request
        request_data = {
            "file_path": temp_test_file,
            "space_did": "did:web:example.storacha.web"
        }
        
        # Mock anyio.to_thread.run_sync to return the mock result
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # Configure the mock to return the value from our mocked method
            mock_run_sync.return_value = mock_storacha_model.upload_file.return_value
            
            # Send request
            response = client.post("/storacha/upload", json=request_data)
            
            # Check response
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert response_data["cid"] == "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            assert response_data["size_bytes"] == 100
            assert response_data["space_did"] == "did:web:example.storacha.web"
            
            # Verify anyio.to_thread.run_sync was called with the right method and parameters
            mock_run_sync.assert_awaited_once()
            args, kwargs = mock_run_sync.call_args
            assert args[0] == mock_storacha_model.upload_file
            assert kwargs.get("file_path") == temp_test_file
            assert kwargs.get("space_did") == "did:web:example.storacha.web"
    
    @pytest.mark.anyio
    async def test_handle_upload_car_request(self, client, mock_storacha_model):
        """Test handling CAR upload request."""
        # Configure mock response
        mock_storacha_model.upload_car.return_value = {
            "success": True,
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "car_cid": "bafybeihykxewafc5hwz2fz6fkzd5a2rxl5avcktcbvvuo6qnni7v3tsvni",
            "size_bytes": 1024,
            "root_cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "shard_size": 1024,
            "upload_id": "12345",
            "space_did": "did:web:example.storacha.web",
            "duration_ms": 50.5
        }
        
        # Create request
        request_data = {
            "car_path": "/tmp/test.car",
            "space_did": "did:web:example.storacha.web"
        }
        
        # Mock anyio.to_thread.run_sync to return the mock result
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # Configure the mock to return the value from our mocked method
            mock_run_sync.return_value = mock_storacha_model.upload_car.return_value
            
            # Send request
            response = client.post("/storacha/upload/car", json=request_data)
            
            # Check response
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert response_data["cid"] == "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            assert response_data["car_cid"] == "bafybeihykxewafc5hwz2fz6fkzd5a2rxl5avcktcbvvuo6qnni7v3tsvni"
            assert response_data["size_bytes"] == 1024
            
            # Verify anyio.to_thread.run_sync was called with the right method and parameters
            mock_run_sync.assert_awaited_once()
            args, kwargs = mock_run_sync.call_args
            assert args[0] == mock_storacha_model.upload_car
            assert kwargs.get("car_path") == "/tmp/test.car"
            assert kwargs.get("space_did") == "did:web:example.storacha.web"
    
    @pytest.mark.anyio
    async def test_handle_list_uploads_request(self, client, mock_storacha_model):
        """Test handling list uploads request."""
        # Configure mock response
        mock_uploads = [
            {
                "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
                "name": "file1.txt",
                "size": 100,
                "created": "2023-01-01T00:00:00Z"
            },
            {
                "cid": "bafybeihykxewafc5hwz2fz6fkzd5a2rxl5avcktcbvvuo6qnni7v3tsvni",
                "name": "file2.txt",
                "size": 200,
                "created": "2023-01-02T00:00:00Z"
            }
        ]
        mock_storacha_model.list_uploads.return_value = {
            "success": True,
            "uploads": mock_uploads,
            "count": 2,
            "space_did": "did:web:example.storacha.web",
            "duration_ms": 50.5
        }
        
        # Mock anyio.to_thread.run_sync to return the mock result
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # Configure the mock to return the value from our mocked method
            mock_run_sync.return_value = mock_storacha_model.list_uploads.return_value
            
            # Send request with space_did parameter
            response = client.get("/storacha/uploads?space_did=did:web:example.storacha.web")
            
            # Check response
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert response_data["count"] == 2
            assert len(response_data["uploads"]) == 2
            assert response_data["uploads"][0]["cid"] == "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            assert response_data["space_did"] == "did:web:example.storacha.web"
            
            # Verify anyio.to_thread.run_sync was called with the right method and parameters
            mock_run_sync.assert_awaited_once()
            args, kwargs = mock_run_sync.call_args
            assert args[0] == mock_storacha_model.list_uploads
            assert kwargs.get("space_did") == "did:web:example.storacha.web"
    
    @pytest.mark.anyio
    async def test_handle_delete_request(self, client, mock_storacha_model):
        """Test handling delete request."""
        # Configure mock response
        mock_storacha_model.delete_upload.return_value = {
            "success": True,
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "space_did": "did:web:example.storacha.web",
            "duration_ms": 50.5
        }
        
        # Create request
        request_data = {
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "space_did": "did:web:example.storacha.web"
        }
        
        # Mock anyio.to_thread.run_sync to return the mock result
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # Configure the mock to return the value from our mocked method
            mock_run_sync.return_value = mock_storacha_model.delete_upload.return_value
            
            # Send request
            response = client.post("/storacha/delete", json=request_data)
            
            # Check response
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert response_data["cid"] == "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            assert response_data["space_did"] == "did:web:example.storacha.web"
            
            # Verify anyio.to_thread.run_sync was called with the right method and parameters
            mock_run_sync.assert_awaited_once()
            args, kwargs = mock_run_sync.call_args
            assert args[0] == mock_storacha_model.delete_upload
            assert kwargs.get("cid") == "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            assert kwargs.get("space_did") == "did:web:example.storacha.web"
    
    @pytest.mark.anyio
    async def test_handle_ipfs_to_storacha_request(self, client, mock_storacha_model):
        """Test handling IPFS to Storacha transfer request."""
        # Configure mock response
        mock_storacha_model.ipfs_to_storacha.return_value = {
            "success": True,
            "ipfs_cid": "QmTestCid",
            "storacha_cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "size_bytes": 100,
            "root_cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "upload_id": "12345",
            "space_did": "did:web:example.storacha.web",
            "duration_ms": 50.5
        }
        
        # Create request
        request_data = {
            "cid": "QmTestCid",
            "space_did": "did:web:example.storacha.web",
            "pin": True
        }
        
        # Mock anyio.to_thread.run_sync to return the mock result
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # Configure the mock to return the value from our mocked method
            mock_run_sync.return_value = mock_storacha_model.ipfs_to_storacha.return_value
            
            # Send request
            response = client.post("/storacha/from_ipfs", json=request_data)
            
            # Check response
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert response_data["ipfs_cid"] == "QmTestCid"
            assert response_data["storacha_cid"] == "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            assert response_data["size_bytes"] == 100
            assert response_data["space_did"] == "did:web:example.storacha.web"
            
            # Verify anyio.to_thread.run_sync was called with the right method and parameters
            mock_run_sync.assert_awaited_once()
            args, kwargs = mock_run_sync.call_args
            assert args[0] == mock_storacha_model.ipfs_to_storacha
            assert kwargs.get("cid") == "QmTestCid"
            assert kwargs.get("space_did") == "did:web:example.storacha.web"
            assert kwargs.get("pin") is True
    
    @pytest.mark.anyio
    async def test_handle_storacha_to_ipfs_request(self, client, mock_storacha_model):
        """Test handling Storacha to IPFS transfer request."""
        # Configure mock response
        mock_storacha_model.storacha_to_ipfs.return_value = {
            "success": True,
            "storacha_cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "ipfs_cid": "QmNewTestCid",
            "size_bytes": 100,
            "space_did": "did:web:example.storacha.web",
            "duration_ms": 50.5
        }
        
        # Create request
        request_data = {
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "space_did": "did:web:example.storacha.web",
            "pin": True
        }
        
        # Mock anyio.to_thread.run_sync to return the mock result
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # Configure the mock to return the value from our mocked method
            mock_run_sync.return_value = mock_storacha_model.storacha_to_ipfs.return_value
            
            # Send request
            response = client.post("/storacha/to_ipfs", json=request_data)
            
            # Check response
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["success"] is True
            assert response_data["storacha_cid"] == "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            assert response_data["ipfs_cid"] == "QmNewTestCid"
            assert response_data["size_bytes"] == 100
            assert response_data["space_did"] == "did:web:example.storacha.web"
            
            # Verify anyio.to_thread.run_sync was called with the right method and parameters
            mock_run_sync.assert_awaited_once()
            args, kwargs = mock_run_sync.call_args
            assert args[0] == mock_storacha_model.storacha_to_ipfs
            assert kwargs.get("cid") == "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
            assert kwargs.get("space_did") == "did:web:example.storacha.web"
            assert kwargs.get("pin") is True
    
    @pytest.mark.anyio
    async def test_handle_request_with_error(self, client, mock_storacha_model):
        """Test handling a request that results in an error response."""
        # Configure mock to return error
        mock_storacha_model.upload_file.return_value = {
            "success": False,
            "error": "Failed to upload file",
            "error_type": "UploadError"
        }
        
        # Create request
        request_data = {
            "file_path": "/nonexistent/path/file.txt",
            "space_did": "did:web:example.storacha.web"
        }
        
        # Mock anyio.to_thread.run_sync to return the mock result
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            # Configure the mock to return the value from our mocked method
            mock_run_sync.return_value = mock_storacha_model.upload_file.return_value
            
            # Send request
            response = client.post("/storacha/upload", json=request_data)
            
            # Check response
            assert response.status_code == 500
            response_data = response.json()
            assert response_data["detail"]["error"] == "Failed to upload file"
            assert response_data["detail"]["error_type"] == "UploadError"
            
            # Verify anyio.to_thread.run_sync was called with the right method
            mock_run_sync.assert_awaited_once()
            args, kwargs = mock_run_sync.call_args
            assert args[0] == mock_storacha_model.upload_file


if __name__ == "__main__":
    pytest.main(["-v", __file__])