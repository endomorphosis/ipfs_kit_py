"""
Tests for the HuggingFaceControllerAnyIO class.

This module tests the anyio-compatible MCP controller for Hugging Face Hub operations.
"""

import json
import time
import uuid
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from fastapi import APIRouter, HTTPException

# Import HuggingFaceControllerAnyIO and related models
from ipfs_kit_py.mcp.controllers.storage.huggingface_controller_anyio import (
    HuggingFaceControllerAnyIO,
    HuggingFaceAuthRequest,
    HuggingFaceRepoCreationRequest,
    HuggingFaceUploadRequest,
    HuggingFaceDownloadRequest,
    HuggingFaceListModelsRequest,
    IPFSHuggingFaceRequest,
    HuggingFaceIPFSRequest,
    HuggingFaceAuthResponse,
    HuggingFaceRepoCreationResponse,
    HuggingFaceUploadResponse,
    HuggingFaceDownloadResponse,
    HuggingFaceListModelsResponse,
    IPFSHuggingFaceResponse,
    HuggingFaceIPFSResponse,
    OperationResponse
)


class MockHuggingFaceModelAnyIO:
    """Mock class for HuggingFace model."""
    
    def __init__(self):
        """Initialize with mock responses."""
        # Pre-configured responses for model methods
        self.authenticate_return = {
            "success": True,
            "operation_id": "auth-123",
            "timestamp": time.time(),
            "authenticated": True,
            "username": "test-user"
        }
        
        self.create_repository_return = {
            "success": True,
            "operation_id": "repo-123",
            "timestamp": time.time(),
            "repo_id": "test-user/test-repo",
            "repo_type": "model",
            "repo_url": "https://huggingface.co/test-user/test-repo"
        }
        
        self.upload_file_return = {
            "success": True,
            "operation_id": "upload-123",
            "timestamp": time.time(),
            "repo_id": "test-user/test-repo",
            "path_in_repo": "model.bin",
            "commit_info": {
                "commit_url": "https://huggingface.co/test-user/test-repo/commit/abc123",
                "commit_id": "abc123"
            }
        }
        
        self.download_file_return = {
            "success": True,
            "operation_id": "download-123",
            "timestamp": time.time(),
            "repo_id": "test-user/test-repo",
            "filename": "model.bin",
            "destination": "/tmp/model.bin",
            "file_size": 12345
        }
        
        self.list_models_return = {
            "success": True,
            "operation_id": "list-123",
            "timestamp": time.time(),
            "models": [
                {
                    "id": "test-user/model1",
                    "last_modified": "2023-01-01T00:00:00.000Z",
                    "private": False
                },
                {
                    "id": "test-user/model2",
                    "last_modified": "2023-01-02T00:00:00.000Z",
                    "private": True
                }
            ],
            "count": 2
        }
        
        self.ipfs_to_huggingface_return = {
            "success": True,
            "operation_id": "ipfs2hf-123",
            "timestamp": time.time(),
            "cid": "QmTest123",
            "repo_id": "test-user/test-repo",
            "path_in_repo": "model.bin",
            "commit_info": {
                "commit_url": "https://huggingface.co/test-user/test-repo/commit/abc123",
                "commit_id": "abc123"
            }
        }
        
        self.huggingface_to_ipfs_return = {
            "success": True,
            "operation_id": "hf2ipfs-123",
            "timestamp": time.time(),
            "repo_id": "test-user/test-repo",
            "filename": "model.bin",
            "cid": "QmTest123"
        }
        
        self.get_stats_return = {
            "uploads": 10,
            "downloads": 5,
            "repositories": 3
        }
    
    def authenticate(self, token):
        """Mock authenticate method."""
        return self.authenticate_return
    
    def create_repository(self, repo_id, repo_type="model", private=False):
        """Mock create_repository method."""
        return self.create_repository_return
    
    def upload_file(self, file_path, repo_id, path_in_repo, commit_message=None, repo_type="model"):
        """Mock upload_file method."""
        return self.upload_file_return
    
    def download_file(self, repo_id, filename, destination=None, revision=None, repo_type="model"):
        """Mock download_file method."""
        return self.download_file_return
    
    def list_models(self, author=None, search=None, limit=50):
        """Mock list_models method."""
        return self.list_models_return
    
    def ipfs_to_huggingface(self, cid, repo_id, path_in_repo, commit_message=None, repo_type="model", pin=True):
        """Mock ipfs_to_huggingface method."""
        return self.ipfs_to_huggingface_return
    
    def huggingface_to_ipfs(self, repo_id, filename, pin=True, revision=None, repo_type="model"):
        """Mock huggingface_to_ipfs method."""
        return self.huggingface_to_ipfs_return
    
    def get_stats(self):
        """Mock get_stats method."""
        return self.get_stats_return


class TestHuggingFaceControllerAnyIOInitialization:
    """Test initialization and route registration for HuggingFaceControllerAnyIO."""
    
    def setup_method(self):
        """Set up each test."""
        self.mock_huggingface_model = MagicMock()
    
    def test_initialization(self):
        """Test controller initialization."""
        controller = HuggingFaceControllerAnyIO(self.mock_huggingface_model)
        
        assert controller.huggingface_model == self.mock_huggingface_model
    
    def test_route_registration(self):
        """Test route registration with FastAPI router."""
        controller = HuggingFaceControllerAnyIO(self.mock_huggingface_model)
        router = APIRouter()
        
        # Call the method to register routes
        controller.register_routes(router)
        
        # Since we can't easily inspect the router's routes, we'll just ensure
        # the method runs without errors


@pytest.mark.anyio
class TestHuggingFaceControllerAnyIO:
    """Test the HuggingFaceControllerAnyIO class functionality."""
    
    @pytest.fixture
    async def controller(self):
        """Create a controller for testing."""
        mock_huggingface_model = MockHuggingFaceModelAnyIO()
        controller = HuggingFaceControllerAnyIO(mock_huggingface_model)
        yield controller
    
    @pytest.fixture
    def mock_huggingface_model(self):
        """Create a mock HuggingFace model."""
        return MockHuggingFaceModelAnyIO()
    
    async def test_handle_auth_request_async(self, controller, mock_huggingface_model):
        """Test handle_auth_request_async method."""
        # Create a request
        request = HuggingFaceAuthRequest(token="test-token")
        
        # Test the method with mocked anyio.to_thread.run_sync
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = mock_huggingface_model.authenticate_return
            
            # Call the method
            result = await controller.handle_auth_request_async(request)
            
            # Verify that to_thread.run_sync was called
            mock_run_sync.assert_awaited_once()
            
            # Verify result
            assert result["success"] is True
            assert result["authenticated"] is True
            assert "username" in result
    
    async def test_handle_repo_creation_request_async(self, controller, mock_huggingface_model):
        """Test handle_repo_creation_request_async method."""
        # Create a request
        request = HuggingFaceRepoCreationRequest(
            repo_id="test-user/test-repo",
            repo_type="model",
            private=False
        )
        
        # Test with successful response
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = mock_huggingface_model.create_repository_return
            
            # Call the method
            result = await controller.handle_repo_creation_request_async(request)
            
            # Verify that to_thread.run_sync was called
            mock_run_sync.assert_awaited_once()
            
            # Verify result
            assert result["success"] is True
            assert result["repo_id"] == "test-user/test-repo"
            assert "repo_url" in result
        
        # Test with error response
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": False,
                "error": "Failed to create repository",
                "error_type": "RepositoryCreationError"
            }
            
            # Call the method and verify it raises an HTTPException
            with pytest.raises(HTTPException) as excinfo:
                await controller.handle_repo_creation_request_async(request)
            
            # Verify exception details
            assert excinfo.value.status_code == 500
            assert "Failed to create repository" in str(excinfo.value.detail)
    
    async def test_handle_upload_request_async(self, controller, mock_huggingface_model):
        """Test handle_upload_request_async method."""
        # Create a request
        request = HuggingFaceUploadRequest(
            file_path="/tmp/model.bin",
            repo_id="test-user/test-repo",
            path_in_repo="model.bin",
            commit_message="Upload model",
            repo_type="model"
        )
        
        # Test with successful response
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = mock_huggingface_model.upload_file_return
            
            # Call the method
            result = await controller.handle_upload_request_async(request)
            
            # Verify that to_thread.run_sync was called
            mock_run_sync.assert_awaited_once()
            
            # Verify result
            assert result["success"] is True
            assert result["repo_id"] == "test-user/test-repo"
            assert result["path_in_repo"] == "model.bin"
            assert "commit_info" in result
        
        # Test with error response
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": False,
                "error": "Failed to upload file",
                "error_type": "UploadError"
            }
            
            # Call the method and verify it raises an HTTPException
            with pytest.raises(HTTPException) as excinfo:
                await controller.handle_upload_request_async(request)
            
            # Verify exception details
            assert excinfo.value.status_code == 500
            assert "Failed to upload file" in str(excinfo.value.detail)
    
    async def test_handle_download_request_async(self, controller, mock_huggingface_model):
        """Test handle_download_request_async method."""
        # Create a request
        request = HuggingFaceDownloadRequest(
            repo_id="test-user/test-repo",
            filename="model.bin",
            destination="/tmp/model.bin",
            revision="main",
            repo_type="model"
        )
        
        # Test with successful response
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = mock_huggingface_model.download_file_return
            
            # Call the method
            result = await controller.handle_download_request_async(request)
            
            # Verify that to_thread.run_sync was called
            mock_run_sync.assert_awaited_once()
            
            # Verify result
            assert result["success"] is True
            assert result["repo_id"] == "test-user/test-repo"
            assert result["filename"] == "model.bin"
            assert result["destination"] == "/tmp/model.bin"
        
        # Test with error response
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": False,
                "error": "Failed to download file",
                "error_type": "DownloadError"
            }
            
            # Call the method and verify it raises an HTTPException
            with pytest.raises(HTTPException) as excinfo:
                await controller.handle_download_request_async(request)
            
            # Verify exception details
            assert excinfo.value.status_code == 500
            assert "Failed to download file" in str(excinfo.value.detail)
    
    async def test_handle_list_models_request_async(self, controller, mock_huggingface_model):
        """Test handle_list_models_request_async method."""
        # Test with successful response
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = mock_huggingface_model.list_models_return
            
            # Call the method
            result = await controller.handle_list_models_request_async(
                author="test-user",
                search="model",
                limit=10
            )
            
            # Verify that to_thread.run_sync was called
            mock_run_sync.assert_awaited_once()
            
            # Verify result
            assert result["success"] is True
            assert "models" in result
            assert result["count"] == 2
        
        # Test with error response
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": False,
                "error": "Failed to list models",
                "error_type": "ListModelsError"
            }
            
            # Call the method and verify it raises an HTTPException
            with pytest.raises(HTTPException) as excinfo:
                await controller.handle_list_models_request_async()
            
            # Verify exception details
            assert excinfo.value.status_code == 500
            assert "Failed to list models" in str(excinfo.value.detail)
    
    async def test_handle_ipfs_to_huggingface_request_async(self, controller, mock_huggingface_model):
        """Test handle_ipfs_to_huggingface_request_async method."""
        # Create a request
        request = IPFSHuggingFaceRequest(
            cid="QmTest123",
            repo_id="test-user/test-repo",
            path_in_repo="model.bin",
            commit_message="Transfer from IPFS",
            repo_type="model",
            pin=True
        )
        
        # Test with successful response
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = mock_huggingface_model.ipfs_to_huggingface_return
            
            # Call the method
            result = await controller.handle_ipfs_to_huggingface_request_async(request)
            
            # Verify that to_thread.run_sync was called
            mock_run_sync.assert_awaited_once()
            
            # Verify result
            assert result["success"] is True
            assert result["cid"] == "QmTest123"
            assert result["repo_id"] == "test-user/test-repo"
            assert result["path_in_repo"] == "model.bin"
            assert "commit_info" in result
        
        # Test with error response
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": False,
                "error": "Failed to transfer content from IPFS to Hugging Face Hub",
                "error_type": "IPFSToHuggingFaceError"
            }
            
            # Call the method and verify it raises an HTTPException
            with pytest.raises(HTTPException) as excinfo:
                await controller.handle_ipfs_to_huggingface_request_async(request)
            
            # Verify exception details
            assert excinfo.value.status_code == 500
            assert "Failed to transfer content from IPFS" in str(excinfo.value.detail)
    
    async def test_handle_huggingface_to_ipfs_request_async(self, controller, mock_huggingface_model):
        """Test handle_huggingface_to_ipfs_request_async method."""
        # Create a request
        request = HuggingFaceIPFSRequest(
            repo_id="test-user/test-repo",
            filename="model.bin",
            pin=True,
            revision="main",
            repo_type="model"
        )
        
        # Test with successful response
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = mock_huggingface_model.huggingface_to_ipfs_return
            
            # Call the method
            result = await controller.handle_huggingface_to_ipfs_request_async(request)
            
            # Verify that to_thread.run_sync was called
            mock_run_sync.assert_awaited_once()
            
            # Verify result
            assert result["success"] is True
            assert result["repo_id"] == "test-user/test-repo"
            assert result["filename"] == "model.bin"
            assert result["cid"] == "QmTest123"
        
        # Test with error response
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = {
                "success": False,
                "error": "Failed to transfer content from Hugging Face Hub to IPFS",
                "error_type": "HuggingFaceToIPFSError"
            }
            
            # Call the method and verify it raises an HTTPException
            with pytest.raises(HTTPException) as excinfo:
                await controller.handle_huggingface_to_ipfs_request_async(request)
            
            # Verify exception details
            assert excinfo.value.status_code == 500
            assert "Failed to transfer content" in str(excinfo.value.detail)
    
    async def test_handle_status_request_async(self, controller, mock_huggingface_model):
        """Test handle_status_request_async method."""
        # Test with successful response
        with patch('anyio.to_thread.run_sync', new_callable=AsyncMock) as mock_run_sync:
            mock_run_sync.return_value = mock_huggingface_model.get_stats_return
            
            # Call the method
            result = await controller.handle_status_request_async()
            
            # Verify that to_thread.run_sync was called
            mock_run_sync.assert_awaited_once()
            
            # Verify result
            assert result["success"] is True
            assert result["is_available"] is True
            assert result["backend"] == "huggingface"
            assert "stats" in result
            assert result["stats"]["uploads"] == 10
            assert result["stats"]["downloads"] == 5
    
    async def test_warn_if_async_context(self, controller):
        """Test _warn_if_async_context method."""
        # Mock sniffio to return a backend
        with patch('sniffio.current_async_library', return_value="anyio"):
            # Mock warnings.warn
            with patch('warnings.warn') as mock_warn:
                # Call the method
                controller._warn_if_async_context("test_method")
                
                # Verify that warnings.warn was called
                mock_warn.assert_called_once()
                assert "Synchronous method test_method called from async context" in mock_warn.call_args[0][0]
        
        # Mock sniffio to raise exception
        with patch('sniffio.current_async_library', side_effect=Exception("No async library found")):
            # Mock warnings.warn
            with patch('warnings.warn') as mock_warn:
                # Call the method
                controller._warn_if_async_context("test_method")
                
                # Verify that warnings.warn was not called
                mock_warn.assert_not_called()
    
    def test_get_backend(self):
        """Test get_backend static method."""
        # Mock sniffio to return a backend
        with patch('sniffio.current_async_library', return_value="anyio"):
            backend = HuggingFaceControllerAnyIO.get_backend()
            assert backend == "anyio"
        
        # Mock sniffio to raise exception
        with patch('sniffio.current_async_library', side_effect=Exception("No async library found")):
            backend = HuggingFaceControllerAnyIO.get_backend()
            assert backend is None


# @pytest.mark.skip(reason="HTTP endpoint tests require running FastAPI server") - removed by fix_all_tests.py
class TestHuggingFaceControllerAnyIOHTTPEndpoints:
    """Test HTTP endpoints for HuggingFaceControllerAnyIO."""
    
    @pytest.fixture
    def client(self):
        """Create a test client with the controller endpoints registered."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        
        app = FastAPI()
        mock_huggingface_model = MockHuggingFaceModelAnyIO()
        controller = HuggingFaceControllerAnyIO(mock_huggingface_model)
        controller.register_routes(app.router)
        
        return TestClient(app)
    
    def test_auth_endpoint(self, client):
        """Test /huggingface/auth endpoint."""
        response = client.post("/huggingface/auth", json={"token": "test-token"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["authenticated"] is True
        assert "username" in data
    
    def test_create_repo_endpoint(self, client):
        """Test /huggingface/repo/create endpoint."""
        response = client.post("/huggingface/repo/create", json={
            "repo_id": "test-user/test-repo",
            "repo_type": "model",
            "private": False
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["repo_id"] == "test-user/test-repo"
        assert "repo_url" in data
    
    def test_upload_endpoint(self, client):
        """Test /huggingface/upload endpoint."""
        response = client.post("/huggingface/upload", json={
            "file_path": "/tmp/model.bin",
            "repo_id": "test-user/test-repo",
            "path_in_repo": "model.bin",
            "commit_message": "Upload model",
            "repo_type": "model"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["repo_id"] == "test-user/test-repo"
        assert data["path_in_repo"] == "model.bin"
        assert "commit_info" in data
    
    def test_download_endpoint(self, client):
        """Test /huggingface/download endpoint."""
        response = client.post("/huggingface/download", json={
            "repo_id": "test-user/test-repo",
            "filename": "model.bin",
            "destination": "/tmp/model.bin",
            "revision": "main",
            "repo_type": "model"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["repo_id"] == "test-user/test-repo"
        assert data["filename"] == "model.bin"
        assert data["destination"] == "/tmp/model.bin"
    
    def test_list_models_endpoint(self, client):
        """Test /huggingface/models endpoint."""
        response = client.get("/huggingface/models?author=test-user&search=model&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "models" in data
        assert data["count"] == 2
    
    def test_ipfs_to_huggingface_endpoint(self, client):
        """Test /huggingface/from_ipfs endpoint."""
        response = client.post("/huggingface/from_ipfs", json={
            "cid": "QmTest123",
            "repo_id": "test-user/test-repo",
            "path_in_repo": "model.bin",
            "commit_message": "Transfer from IPFS",
            "repo_type": "model",
            "pin": True
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cid"] == "QmTest123"
        assert data["repo_id"] == "test-user/test-repo"
        assert data["path_in_repo"] == "model.bin"
        assert "commit_info" in data
    
    def test_huggingface_to_ipfs_endpoint(self, client):
        """Test /huggingface/to_ipfs endpoint."""
        response = client.post("/huggingface/to_ipfs", json={
            "repo_id": "test-user/test-repo",
            "filename": "model.bin",
            "pin": True,
            "revision": "main",
            "repo_type": "model"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["repo_id"] == "test-user/test-repo"
        assert data["filename"] == "model.bin"
        assert data["cid"] == "QmTest123"
    
    def test_status_endpoint(self, client):
        """Test /storage/huggingface/status endpoint."""
        response = client.get("/storage/huggingface/status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["is_available"] is True
        assert data["backend"] == "huggingface"
        assert "stats" in data
        assert data["stats"]["uploads"] == 10
        assert data["stats"]["downloads"] == 5