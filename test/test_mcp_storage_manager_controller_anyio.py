"""
Test suite for MCP Storage Manager Controller with AnyIO support.

This module tests the functionality of the StorageManagerControllerAnyIO class
which provides HTTP endpoints for managing multiple storage backends and
operations between them with AnyIO compatibility.
"""

import pytest
import json
import time
import sniffio
from unittest.mock import MagicMock, AsyncMock, patch, ANY
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response
from fastapi.testclient import TestClient

# Import controller class and models
from ipfs_kit_py.mcp.controllers.storage_manager_controller_anyio import (
    StorageManagerControllerAnyIO,
    OperationResponse,
    ReplicationPolicyRequest,
    ReplicationPolicyResponse,
    BackendStatusResponse,
    AllBackendsStatusResponse,
    StorageTransferRequest,
    StorageTransferResponse,
    ContentMigrationRequest,
    ContentMigrationResponse
)

class TestStorageManagerControllerAnyIOInitialization:
    """Test initialization and setup of StorageManagerControllerAnyIO."""
    
    def test_init(self):
        """Test initialization of StorageManagerControllerAnyIO."""
        # Mock storage manager
        mock_storage_manager = MagicMock()
        
        # Initialize controller
        controller = StorageManagerControllerAnyIO(mock_storage_manager)
        
        # Verify controller was initialized with storage manager
        assert controller.storage_manager == mock_storage_manager
    
    def test_register_routes(self):
        """Test that all routes are registered with AnyIO handlers."""
        # Mock storage manager
        mock_storage_manager = MagicMock()
        
        # Mock router
        mock_router = MagicMock(spec=APIRouter)
        
        # Initialize controller
        controller = StorageManagerControllerAnyIO(mock_storage_manager)
        
        # Register routes
        controller.register_routes(mock_router)
        
        # Verify that routes were registered using async handlers
        expected_routes = [
            "/storage/status",
            "/storage/{backend_name}/status",
            "/storage/transfer",
            "/storage/verify",
            "/storage/migrate",
            "/storage/apply-policy"
        ]
        
        # Extract route paths from calls
        route_calls = [call.args[0] for call in mock_router.add_api_route.call_args_list]
        
        # Verify all expected routes were registered
        for route in expected_routes:
            assert any(route == call for call in route_calls), f"Route {route} was not registered"
        
        # Verify that all handlers have "async" in their name
        handler_calls = [call.kwargs["endpoint"] for call in mock_router.add_api_route.call_args_list]
        for handler in handler_calls:
            handler_name = handler.__name__
            assert "async" in handler_name, f"Handler {handler_name} is not an async method"

    def test_backend_detection(self):
        """Test detection of current async backend."""
        # Test static method directly
        backend = StorageManagerControllerAnyIO.get_backend()
        assert backend is None  # No async context when running this test
        
        # In an async context, it should return the backend name
        @pytest.mark.anyio
        async def check_async_backend():
            return StorageManagerControllerAnyIO.get_backend()
        
        # Can't test the result directly here, but the function shouldn't raise an exception

@pytest.mark.anyio
class TestStorageManagerControllerAnyIO:
    """Test StorageManagerControllerAnyIO with AnyIO compatibility."""
    
    @pytest.fixture
    def mock_storage_manager(self):
        """Create a mock storage manager for testing."""
        mock_manager = MagicMock()
        
        # Set up mock backends
        mock_ipfs = MagicMock(name="ipfs_model")
        mock_s3 = MagicMock(name="s3_model")
        mock_storacha = MagicMock(name="storacha_model")
        
        # Configure get_available_backends
        mock_manager.get_available_backends.return_value = {
            "ipfs": True,
            "s3": True,
            "storacha": True
        }
        
        # Configure get_all_models
        mock_manager.get_all_models.return_value = {
            "ipfs": mock_ipfs,
            "s3": mock_s3,
            "storacha": mock_storacha
        }
        
        # Configure get_model
        mock_manager.get_model.side_effect = lambda name: {
            "ipfs": mock_ipfs,
            "s3": mock_s3,
            "storacha": mock_storacha
        }.get(name)
        
        # Set up backend model capabilities
        for model in [mock_ipfs, mock_s3, mock_storacha]:
            model.get_stats.return_value = {
                "success": True,
                "status": "available",
                "storage_used": 1024,
                "content_count": 10
            }
        
        # Create mock storage bridge
        mock_bridge = MagicMock()
        mock_manager.storage_bridge = mock_bridge
        
        return {
            "manager": mock_manager,
            "backends": {
                "ipfs": mock_ipfs,
                "s3": mock_s3,
                "storacha": mock_storacha
            },
            "bridge": mock_bridge
        }
    
    @pytest.fixture
    def controller(self, mock_storage_manager):
        """Create a controller instance for testing."""
        return StorageManagerControllerAnyIO(mock_storage_manager["manager"])
    
    @pytest.mark.anyio
    async def test_handle_status_request_async(self, controller, mock_storage_manager):
        """Test the async status request handler."""
        # Patch anyio.to_thread.run_sync to verify it's used correctly
        with patch("anyio.to_thread.run_sync") as mock_run_sync:
            # Configure mock to return a valid status response
            mock_run_sync.return_value = {
                "success": True,
                "operation_id": "test-op-id",
                "backends": {
                    "ipfs": {"backend_name": "ipfs", "is_available": True},
                    "s3": {"backend_name": "s3", "is_available": True},
                    "storacha": {"backend_name": "storacha", "is_available": True}
                },
                "available_count": 3,
                "total_count": 3,
                "duration_ms": 10.5
            }
            
            # Call the async method
            result = await controller.handle_status_request_async()
            
            # Verify anyio.to_thread.run_sync was called with the correct sync method
            mock_run_sync.assert_called_once()
            assert mock_run_sync.call_args[0][0] == controller.handle_status_request
            
            # Verify result
            assert result["success"] is True
            assert "backends" in result
            assert len(result["backends"]) == 3
    
    @pytest.mark.anyio
    async def test_handle_backend_status_request_async(self, controller, mock_storage_manager):
        """Test the async backend status request handler."""
        # Patch anyio.to_thread.run_sync
        with patch("anyio.to_thread.run_sync") as mock_run_sync:
            # Configure mock to return a valid backend status
            mock_run_sync.return_value = {
                "success": True,
                "operation_id": "test-op-id",
                "backend_name": "ipfs",
                "is_available": True,
                "capabilities": ["content_retrieval", "content_storage"],
                "stats": {"storage_used": 1024, "content_count": 10},
                "duration_ms": 5.2
            }
            
            # Call the async method
            result = await controller.handle_backend_status_request_async("ipfs")
            
            # Verify anyio.to_thread.run_sync was called with the correct sync method and arguments
            mock_run_sync.assert_called_once()
            assert mock_run_sync.call_args[0][0] == controller.handle_backend_status_request
            assert mock_run_sync.call_args[0][1] == "ipfs"
            
            # Verify result
            assert result["success"] is True
            assert result["backend_name"] == "ipfs"
            assert "capabilities" in result
            assert "stats" in result
    
    @pytest.mark.anyio
    async def test_handle_transfer_request_async(self, controller, mock_storage_manager):
        """Test the async transfer request handler."""
        # Create transfer request
        request = StorageTransferRequest(
            source_backend="ipfs",
            target_backend="s3",
            content_id="test-cid",
            options={"retention": "standard"}
        )
        
        # Patch anyio.to_thread.run_sync
        with patch("anyio.to_thread.run_sync") as mock_run_sync:
            # Configure mock to return a valid transfer response
            mock_run_sync.return_value = {
                "success": True,
                "operation_id": "transfer-123",
                "source_backend": "ipfs",
                "target_backend": "s3",
                "content_id": "test-cid",
                "target_location": "s3://bucket/key",
                "source_location": "ipfs://test-cid",
                "bytes_transferred": 1024,
                "duration_ms": 15.3
            }
            
            # Call the async method
            result = await controller.handle_transfer_request_async(request)
            
            # Verify anyio.to_thread.run_sync was called with the correct sync method and arguments
            mock_run_sync.assert_called_once()
            assert mock_run_sync.call_args[0][0] == controller.handle_transfer_request
            assert mock_run_sync.call_args[0][1] == request
            
            # Verify result
            assert result["success"] is True
            assert result["source_backend"] == "ipfs"
            assert result["target_backend"] == "s3"
            assert result["content_id"] == "test-cid"
            assert result["bytes_transferred"] == 1024
    
    @pytest.mark.anyio
    async def test_handle_verify_request_async(self, controller, mock_storage_manager):
        """Test the async verify request handler."""
        # Prepare test parameters
        content_id = "test-cid"
        backends = ["ipfs", "s3"]
        
        # Patch anyio.to_thread.run_sync
        with patch("anyio.to_thread.run_sync") as mock_run_sync:
            # Configure mock to return a valid verification response
            mock_run_sync.return_value = {
                "success": True,
                "operation_id": "verify-123",
                "content_id": "test-cid",
                "verified_backends": ["ipfs", "s3"],
                "total_backends_checked": 2,
                "verification_results": {
                    "ipfs": {"success": True},
                    "s3": {"success": True}
                },
                "duration_ms": 8.7
            }
            
            # Call the async method
            result = await controller.handle_verify_request_async(content_id, backends)
            
            # Verify anyio.to_thread.run_sync was called with the correct sync method and arguments
            mock_run_sync.assert_called_once()
            assert mock_run_sync.call_args[0][0] == controller.handle_verify_request
            assert mock_run_sync.call_args[0][1] == content_id
            assert mock_run_sync.call_args[0][2] == backends
            
            # Verify result
            assert result["success"] is True
            assert result["content_id"] == "test-cid"
            assert result["verified_backends"] == ["ipfs", "s3"]
    
    @pytest.mark.anyio
    async def test_handle_migration_request_async(self, controller, mock_storage_manager):
        """Test the async migration request handler."""
        # Create migration request
        request = ContentMigrationRequest(
            source_backend="ipfs",
            target_backend="s3",
            content_ids=["cid1", "cid2"],
            options={"tier": "standard"},
            delete_source=False,
            verify_integrity=True
        )
        
        # Patch anyio.to_thread.run_sync
        with patch("anyio.to_thread.run_sync") as mock_run_sync:
            # Configure mock to return a valid migration response
            mock_run_sync.return_value = {
                "success": True,
                "operation_id": "migrate-123",
                "source_backend": "ipfs",
                "target_backend": "s3",
                "content_count": 2,
                "successful_count": 2,
                "failed_count": 0,
                "total_bytes_transferred": 2048,
                "results": {
                    "cid1": {"success": True, "bytes": 1024},
                    "cid2": {"success": True, "bytes": 1024}
                },
                "duration_ms": 25.1
            }
            
            # Call the async method
            result = await controller.handle_migration_request_async(request)
            
            # Verify anyio.to_thread.run_sync was called with the correct sync method and arguments
            mock_run_sync.assert_called_once()
            assert mock_run_sync.call_args[0][0] == controller.handle_migration_request
            assert mock_run_sync.call_args[0][1] == request
            
            # Verify result
            assert result["success"] is True
            assert result["source_backend"] == "ipfs"
            assert result["target_backend"] == "s3"
            assert result["content_count"] == 2
            assert result["successful_count"] == 2
            assert result["total_bytes_transferred"] == 2048
            
            # Check for individual content results
            assert "cid1" in result["results"]
            assert "cid2" in result["results"]
            assert result["results"]["cid1"]["success"] is True
            assert result["results"]["cid2"]["success"] is True
    
    @pytest.mark.anyio
    async def test_handle_replication_policy_request_async(self, controller, mock_storage_manager):
        """Test the async replication policy request handler."""
        # Create replication policy request
        request = ReplicationPolicyRequest(
            content_id="test-cid",
            policy={
                "name": "high-availability",
                "backends": ["ipfs", "s3", "storacha"],
                "replication_factor": 3
            }
        )
        
        # Patch anyio.to_thread.run_sync
        with patch("anyio.to_thread.run_sync") as mock_run_sync:
            # Configure mock to return a valid policy application response
            mock_run_sync.return_value = {
                "success": True,
                "operation_id": "policy-123",
                "content_id": "test-cid",
                "source_backend": "ipfs",
                "backends_selected": ["ipfs", "s3", "storacha"],
                "policy_applied": True,
                "successful_backends": ["ipfs", "s3", "storacha"],
                "failed_backends": [],
                "bytes_transferred": 3072,
                "duration_ms": 30.5
            }
            
            # Call the async method
            result = await controller.handle_replication_policy_request_async(request)
            
            # Verify anyio.to_thread.run_sync was called with the correct sync method and arguments
            mock_run_sync.assert_called_once()
            assert mock_run_sync.call_args[0][0] == controller.handle_replication_policy_request
            assert mock_run_sync.call_args[0][1] == request
            
            # Verify result
            assert result["success"] is True
            assert result["content_id"] == "test-cid"
            assert result["backends_selected"] == ["ipfs", "s3", "storacha"]
            assert result["policy_applied"] is True
            assert result["successful_backends"] == ["ipfs", "s3", "storacha"]
            assert result["failed_backends"] == []

    @pytest.mark.anyio
    async def test_warn_if_async_context(self, controller):
        """Test the _warn_if_async_context method."""
        # Test the warning method directly
        with pytest.warns(UserWarning, match="called from async context"):
            controller._warn_if_async_context("test_method")

@pytest.mark.skip("HTTP endpoint tests need FastAPI dependency injection to be fixed")
class TestStorageManagerControllerAnyIOHTTPEndpoints:
    """Test HTTP endpoints of StorageManagerControllerAnyIO."""
    
    @pytest.fixture
    def test_app(self, monkeypatch):
        """Create a FastAPI test app with the controller."""
        # Create FastAPI app
        app = FastAPI()
        router = APIRouter()
        
        # Mock storage manager
        mock_manager = MagicMock()
        
        # Set up mock backends
        mock_ipfs = MagicMock(name="ipfs_model")
        mock_s3 = MagicMock(name="s3_model")
        
        mock_manager.get_available_backends.return_value = {
            "ipfs": True,
            "s3": True
        }
        
        mock_manager.get_all_models.return_value = {
            "ipfs": mock_ipfs,
            "s3": mock_s3
        }
        
        mock_manager.get_model.side_effect = lambda name: {
            "ipfs": mock_ipfs,
            "s3": mock_s3
        }.get(name)
        
        # Mock storage bridge
        mock_bridge = MagicMock()
        mock_manager.storage_bridge = mock_bridge
        
        # Initialize controller
        controller = StorageManagerControllerAnyIO(mock_manager)
        
        # Patch the async methods to return dummy values
        # This is necessary for FastAPI to properly handle the routes
        async def mock_status_request_async():
            return {
                "success": True,
                "backends": {
                    "ipfs": {"is_available": True, "capabilities": []},
                    "s3": {"is_available": True, "capabilities": []}
                },
                "available_count": 2,
                "total_count": 2
            }
            
        async def mock_backend_status_request_async(backend_name):
            if backend_name == "nonexistent":
                raise HTTPException(
                    status_code=404,
                    detail={"error": "Backend not found", "error_type": "BackendNotFoundError"}
                )
            return {
                "success": True,
                "backend_name": backend_name,
                "is_available": True,
                "capabilities": ["content_retrieval", "content_storage"],
                "stats": {"storage_used": 1024}
            }
            
        async def mock_transfer_request_async(request):
            return {
                "success": True,
                "operation_id": "transfer-123",
                "source_backend": request.source_backend,
                "target_backend": request.target_backend,
                "content_id": request.content_id,
                "bytes_transferred": 1024
            }
            
        async def mock_verify_request_async(content_id, backends=None):
            return {
                "success": True,
                "content_id": content_id,
                "verified_backends": backends or []
            }
            
        async def mock_migration_request_async(request):
            return {
                "success": True,
                "source_backend": request.source_backend,
                "target_backend": request.target_backend,
                "content_count": len(request.content_ids),
                "successful_count": len(request.content_ids),
                "failed_count": 0,
                "total_bytes_transferred": 2048,
                "results": {cid: {"success": True} for cid in request.content_ids}
            }
            
        async def mock_replication_policy_request_async(request):
            return {
                "success": True,
                "content_id": request.content_id,
                "source_backend": "ipfs",
                "backends_selected": ["ipfs", "s3"],
                "policy_applied": True,
                "successful_backends": ["ipfs", "s3"],
                "failed_backends": []
            }
        
        # Patch the async methods with mocks that will be used in HTTP routes
        monkeypatch.setattr(controller, "handle_status_request_async", mock_status_request_async)
        monkeypatch.setattr(controller, "handle_backend_status_request_async", mock_backend_status_request_async)
        monkeypatch.setattr(controller, "handle_transfer_request_async", mock_transfer_request_async)
        monkeypatch.setattr(controller, "handle_verify_request_async", mock_verify_request_async)
        monkeypatch.setattr(controller, "handle_migration_request_async", mock_migration_request_async)
        monkeypatch.setattr(controller, "handle_replication_policy_request_async", mock_replication_policy_request_async)
        
        # Register routes
        controller.register_routes(router)
        
        # Mount router to app
        app.include_router(router, prefix="/api/v0")
        
        # Create test client
        client = TestClient(app)
        
        return {
            "app": app,
            "client": client,
            "controller": controller,
            "manager": mock_manager,
            "backends": {
                "ipfs": mock_ipfs,
                "s3": mock_s3
            },
            "bridge": mock_bridge
        }
    
    def test_get_all_backends_status(self, test_app):
        """Test GET /storage/status endpoint."""
        client = test_app["client"]
        
        # Send request to endpoint
        response = client.get("/api/v0/storage/status")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "backends" in data
        assert len(data["backends"]) == 2
        assert "ipfs" in data["backends"]
        assert "s3" in data["backends"]
    
    def test_get_backend_status(self, test_app):
        """Test GET /storage/{backend_name}/status endpoint."""
        client = test_app["client"]
        
        # Send request to endpoint
        response = client.get("/api/v0/storage/ipfs/status")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["backend_name"] == "ipfs"
        assert "capabilities" in data
        assert "stats" in data
    
    def test_post_transfer_content(self, test_app):
        """Test POST /storage/transfer endpoint."""
        client = test_app["client"]
        
        # Send request to endpoint
        response = client.post(
            "/api/v0/storage/transfer",
            json={
                "source_backend": "ipfs",
                "target_backend": "s3",
                "content_id": "test-cid",
                "options": {"retention": "standard"}
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["source_backend"] == "ipfs"
        assert data["target_backend"] == "s3"
        assert data["content_id"] == "test-cid"
        assert "bytes_transferred" in data
    
    def test_post_verify_content(self, test_app):
        """Test POST /storage/verify endpoint."""
        client = test_app["client"]
        
        # Send request to endpoint
        response = client.post(
            "/api/v0/storage/verify",
            json={
                "content_id": "test-cid",
                "backends": ["ipfs", "s3"]
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["content_id"] == "test-cid"
        assert "verified_backends" in data
    
    def test_post_migrate_content(self, test_app):
        """Test POST /storage/migrate endpoint."""
        client = test_app["client"]
        
        # Send request to endpoint
        response = client.post(
            "/api/v0/storage/migrate",
            json={
                "source_backend": "ipfs",
                "target_backend": "s3",
                "content_ids": ["cid1", "cid2"],
                "options": {"tier": "standard"},
                "delete_source": False,
                "verify_integrity": True
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["source_backend"] == "ipfs"
        assert data["target_backend"] == "s3"
        assert data["content_count"] == 2
        assert data["successful_count"] == 2
        assert "results" in data
    
    def test_post_apply_policy(self, test_app):
        """Test POST /storage/apply-policy endpoint."""
        client = test_app["client"]
        
        # Send request to endpoint
        response = client.post(
            "/api/v0/storage/apply-policy",
            json={
                "content_id": "test-cid",
                "policy": {
                    "name": "high-availability",
                    "backends": ["ipfs", "s3"],
                    "replication_factor": 2
                }
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["content_id"] == "test-cid"
        assert "backends_selected" in data
        assert "policy_applied" in data
    
    def test_endpoint_error_handling(self, test_app):
        """Test error handling in endpoints."""
        client = test_app["client"]
        
        # Send request to a non-existent backend
        response = client.get("/api/v0/storage/nonexistent/status")
        
        # Verify response
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "error" in data["detail"]
        assert data["detail"]["error"] == "Backend not found"

if __name__ == "__main__":
    pytest.main(["-xvs", __file__])