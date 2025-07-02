"""
Test suite for MCP Storage Manager Controller.

This module tests the functionality of the StorageManagerController class
which provides HTTP endpoints for managing multiple storage backends and
operations between them.
"""

import pytest
import json
import time
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response
from fastapi.testclient import TestClient
from pydantic import BaseModel

# Import the controller class
try:
    from ipfs_kit_py.mcp.controllers.storage_manager_controller import (
        StorageManagerController,
        StorageTransferRequest,
        ContentMigrationRequest,
        ReplicationPolicyRequest
    )
except ImportError:
    # If AnyIO migration has occurred, import from the AnyIO version
    from ipfs_kit_py.mcp.controllers.storage_manager_controller_anyio import (
        StorageManagerController,
        StorageTransferRequest,
        ContentMigrationRequest,
        ReplicationPolicyRequest
    )


class TestStorageManagerControllerInitialization:
    """Test initialization and route registration of StorageManagerController."""

    def test_init_with_multiple_backends(self):
        """Test controller initialization with multiple storage backends."""
        # Mock storage backends
        mock_ipfs = MagicMock(name="ipfs_model")
        mock_s3 = MagicMock(name="s3_model")
        mock_storacha = MagicMock(name="storacha_model")
        
        # Mock storage manager with backends
        mock_storage_manager = MagicMock()
        mock_storage_manager.get_backends.return_value = {
            "ipfs": mock_ipfs,
            "s3": mock_s3,
            "storacha": mock_storacha
        }
        
        # Initialize controller
        controller = StorageManagerController(mock_storage_manager)
        
        # Verify the controller is initialized with the storage manager
        assert controller.storage_manager == mock_storage_manager
        
        # Verify backend capabilities are detected
        assert hasattr(controller, "_backend_capabilities")
        
        # Verify storage bridge is initialized if available
        if hasattr(mock_storage_manager, "storage_bridge"):
            assert hasattr(controller, "storage_bridge")
    
    def test_init_without_storage_bridge(self):
        """Test controller initialization without storage bridge."""
        # Mock storage backends
        mock_ipfs = MagicMock(name="ipfs_model")
        
        # Mock storage manager without storage bridge
        mock_storage_manager = MagicMock()
        mock_storage_manager.get_backends.return_value = {"ipfs": mock_ipfs}
        mock_storage_manager.storage_bridge = None
        
        # Initialize controller
        controller = StorageManagerController(mock_storage_manager)
        
        # Verify the controller is initialized with the storage manager
        assert controller.storage_manager == mock_storage_manager
        
        # Verify storage bridge is not available
        assert not hasattr(controller, "storage_bridge")
    
    def test_route_registration(self):
        """Test that all routes are registered correctly."""
        # Mock storage manager
        mock_storage_manager = MagicMock()
        mock_storage_manager.get_backends.return_value = {"ipfs": MagicMock()}
        
        # Mock router
        mock_router = MagicMock(spec=APIRouter)
        
        # Initialize controller and register routes
        controller = StorageManagerController(mock_storage_manager)
        controller.register_routes(mock_router)
        
        # Verify that add_api_route was called for each endpoint
        expected_routes = [
            # Status routes
            "/storage/status",
            "/storage/{backend_name}/status",
            
            # Operation routes
            "/storage/transfer",
            "/storage/verify",
            "/storage/migrate",
            "/storage/apply-policy"
        ]
        
        route_calls = [call.args[0] for call in mock_router.add_api_route.call_args_list]
        
        # Verify expected route registrations
        for route in expected_routes:
            assert any(route in call for call in route_calls), f"Route {route} was not registered"


class TestStorageManagerController:
    """Test storage operations for StorageManagerController."""
    
    @pytest.fixture
    def controller_with_app(self):
        """Create a controller with a FastAPI app for testing HTTP endpoints."""
        # Create FastAPI app and router
        app = FastAPI()
        router = APIRouter()
        
        # Mock storage backends
        mock_ipfs = MagicMock(name="ipfs_model")
        mock_s3 = MagicMock(name="s3_model")
        mock_storacha = MagicMock(name="storacha_model")
        
        # Set up mock backend capabilities
        mock_ipfs.get.return_value = {"success": True, "data": b"test content"}
        mock_ipfs.put = MagicMock()
        mock_s3.get_object = MagicMock()
        mock_s3.put_object = MagicMock()
        mock_storacha.get = MagicMock()
        mock_storacha.put = MagicMock()
        
        # Mock storage manager
        mock_storage_manager = MagicMock()
        mock_storage_manager.get_backends.return_value = {
            "ipfs": mock_ipfs,
            "s3": mock_s3,
            "storacha": mock_storacha
        }
        
        # Mock storage bridge
        mock_bridge = MagicMock()
        mock_storage_manager.storage_bridge = mock_bridge
        
        # Set up mock status responses
        mock_ipfs.get_status.return_value = {
            "success": True,
            "status": "online",
            "version": "0.18.0",
            "peer_id": "QmTest",
            "storage_used": 1024,
            "content_count": 10
        }
        
        mock_s3.get_status.return_value = {
            "success": True,
            "status": "online",
            "buckets": ["test-bucket"],
            "region": "us-east-1",
            "storage_used": 2048
        }
        
        mock_storacha.get_status.return_value = {
            "success": True,
            "status": "online",
            "space_did": "did:web:example.com",
            "storage_used": 512
        }
        
        # Initialize controller with mock storage manager
        controller = StorageManagerController(mock_storage_manager)
        controller.register_routes(router)
        
        # Mount router to app
        app.include_router(router, prefix="/api/v0")
        
        # Create test client
        client = TestClient(app)
        
        return {
            "app": app,
            "client": client,
            "controller": controller,
            "storage_manager": mock_storage_manager,
            "backends": {
                "ipfs": mock_ipfs,
                "s3": mock_s3,
                "storacha": mock_storacha
            },
            "bridge": mock_bridge
        }
    
    def test_get_all_backends_status(self, controller_with_app):
        """Test getting status of all storage backends."""
        client = controller_with_app["client"]
        
        # Test getting all backends status
        response = client.get("/api/v0/storage/status")
        assert response.status_code == 200
        
        # Verify response format
        data = response.json()
        assert data["success"] is True
        assert "backends" in data
        assert len(data["backends"]) == 3
        assert "ipfs" in data["backends"]
        assert "s3" in data["backends"]
        assert "storacha" in data["backends"]
        
        # Verify each backend has appropriate information
        for backend_name, backend_info in data["backends"].items():
            assert "status" in backend_info
            assert "capabilities" in backend_info
    
    def test_get_backend_status(self, controller_with_app):
        """Test getting status of a specific storage backend."""
        client = controller_with_app["client"]
        
        # Test getting IPFS backend status
        response = client.get("/api/v0/storage/ipfs/status")
        assert response.status_code == 200
        
        # Verify response format
        data = response.json()
        assert data["success"] is True
        assert data["backend_name"] == "ipfs"
        assert "status" in data["backend_info"]
        assert "version" in data["backend_info"]
        assert "peer_id" in data["backend_info"]
        
        # Test getting S3 backend status
        response = client.get("/api/v0/storage/s3/status")
        assert response.status_code == 200
        data = response.json()
        assert data["backend_name"] == "s3"
        assert "buckets" in data["backend_info"]
        
        # Test getting non-existent backend status
        response = client.get("/api/v0/storage/nonexistent/status")
        assert response.status_code == 404
        assert "Backend not found" in response.json()["detail"]
    
    def test_transfer_content_with_bridge(self, controller_with_app):
        """Test transferring content between backends using bridge."""
        client = controller_with_app["client"]
        bridge = controller_with_app["bridge"]
        
        # Set up mock bridge response
        bridge.transfer_content.return_value = {
            "success": True,
            "operation": "transfer_content",
            "source_backend": "ipfs",
            "target_backend": "s3",
            "content_id": "test-cid",
            "target_id": "s3-key"
        }
        
        # Test transfer request
        response = client.post(
            "/api/v0/storage/transfer", 
            json={
                "source_backend": "ipfs",
                "target_backend": "s3",
                "content_id": "test-cid",
                "target_id": "s3-key"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["source_backend"] == "ipfs"
        assert data["target_backend"] == "s3"
        assert data["content_id"] == "test-cid"
        
        # Verify bridge method was called
        bridge.transfer_content.assert_called_once_with(
            source_backend="ipfs",
            target_backend="s3",
            content_id="test-cid",
            target_id="s3-key"
        )
    
    def test_transfer_content_without_bridge(self, controller_with_app):
        """Test transferring content between backends without bridge."""
        client = controller_with_app["client"]
        controller = controller_with_app["controller"]
        backends = controller_with_app["backends"]
        
        # Mock direct transfer methods
        backends["ipfs"].get.return_value = {
            "success": True,
            "data": b"test content",
            "cid": "test-cid"
        }
        
        backends["s3"].put_object.return_value = {
            "success": True,
            "key": "s3-key"
        }
        
        # Remove bridge to force direct transfer
        controller.storage_bridge = None
        
        # Test transfer request
        response = client.post(
            "/api/v0/storage/transfer", 
            json={
                "source_backend": "ipfs",
                "target_backend": "s3",
                "content_id": "test-cid",
                "target_id": "s3-key"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["source_backend"] == "ipfs"
        assert data["target_backend"] == "s3"
        assert data["content_id"] == "test-cid"
        
        # Verify direct backend methods were called
        backends["ipfs"].get.assert_called_once_with("test-cid")
        backends["s3"].put_object.assert_called_once()
    
    def test_transfer_nonexistent_backend(self, controller_with_app):
        """Test transferring content with non-existent backend."""
        client = controller_with_app["client"]
        
        # Test transfer with non-existent source backend
        response = client.post(
            "/api/v0/storage/transfer", 
            json={
                "source_backend": "nonexistent",
                "target_backend": "s3",
                "content_id": "test-cid"
            }
        )
        
        assert response.status_code == 404
        assert "Backend not found" in response.json()["detail"]
        
        # Test transfer with non-existent target backend
        response = client.post(
            "/api/v0/storage/transfer", 
            json={
                "source_backend": "ipfs",
                "target_backend": "nonexistent",
                "content_id": "test-cid"
            }
        )
        
        assert response.status_code == 404
        assert "Backend not found" in response.json()["detail"]
    
    def test_transfer_missing_capabilities(self, controller_with_app):
        """Test transferring content with missing backend capabilities."""
        client = controller_with_app["client"]
        backends = controller_with_app["backends"]
        controller = controller_with_app["controller"]
        
        # Remove bridge to force direct transfer
        controller.storage_bridge = None
        
        # Remove get method from ipfs backend
        del backends["ipfs"].get
        
        # Test transfer with missing source capability
        response = client.post(
            "/api/v0/storage/transfer", 
            json={
                "source_backend": "ipfs",
                "target_backend": "s3",
                "content_id": "test-cid"
            }
        )
        
        assert response.status_code == 400
        assert "missing required capability" in response.json()["detail"]
        
        # Restore get method and remove put method from s3 backend
        backends["ipfs"].get = MagicMock(return_value={"success": True, "data": b"test"})
        del backends["s3"].put_object
        
        # Test transfer with missing target capability
        response = client.post(
            "/api/v0/storage/transfer", 
            json={
                "source_backend": "ipfs",
                "target_backend": "s3",
                "content_id": "test-cid"
            }
        )
        
        assert response.status_code == 400
        assert "missing required capability" in response.json()["detail"]
    
    def test_verify_content_with_bridge(self, controller_with_app):
        """Test verifying content across backends using bridge."""
        client = controller_with_app["client"]
        bridge = controller_with_app["bridge"]
        
        # Set up mock bridge response
        bridge.verify_content.return_value = {
            "success": True,
            "operation": "verify_content",
            "content_id": "test-cid",
            "backends": ["ipfs", "s3"],
            "identical": True,
            "verification_details": {
                "ipfs": {"status": "verified", "hash": "test-hash"},
                "s3": {"status": "verified", "hash": "test-hash"}
            }
        }
        
        # Test verify request
        response = client.post(
            "/api/v0/storage/verify", 
            json={
                "content_id": "test-cid",
                "backends": ["ipfs", "s3"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["content_id"] == "test-cid"
        assert "identical" in data
        assert data["identical"] is True
        
        # Verify bridge method was called
        bridge.verify_content.assert_called_once_with(
            content_id="test-cid",
            backends=["ipfs", "s3"]
        )
    
    def test_migrate_content_with_bridge(self, controller_with_app):
        """Test migrating content between backends using bridge."""
        client = controller_with_app["client"]
        bridge = controller_with_app["bridge"]
        
        # Set up mock bridge response
        bridge.migrate_content.return_value = {
            "success": True,
            "operation": "migrate_content",
            "source_backend": "ipfs",
            "target_backend": "s3",
            "content_ids": ["cid1", "cid2"],
            "results": {
                "cid1": {"success": True, "target_id": "key1"},
                "cid2": {"success": True, "target_id": "key2"}
            },
            "migration_summary": {
                "total": 2,
                "successful": 2,
                "failed": 0
            }
        }
        
        # Test migrate request
        response = client.post(
            "/api/v0/storage/migrate", 
            json={
                "source_backend": "ipfs",
                "target_backend": "s3",
                "content_ids": ["cid1", "cid2"],
                "verify": True,
                "delete_source": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["source_backend"] == "ipfs"
        assert data["target_backend"] == "s3"
        assert len(data["content_ids"]) == 2
        assert "migration_summary" in data
        
        # Verify bridge method was called
        bridge.migrate_content.assert_called_once_with(
            source_backend="ipfs",
            target_backend="s3",
            content_ids=["cid1", "cid2"],
            verify=True,
            delete_source=False
        )
    
    def test_apply_replication_policy_with_bridge(self, controller_with_app):
        """Test applying replication policy using bridge."""
        client = controller_with_app["client"]
        bridge = controller_with_app["bridge"]
        
        # Set up mock bridge response
        bridge.apply_replication_policy.return_value = {
            "success": True,
            "operation": "apply_replication_policy",
            "content_id": "test-cid",
            "policy_name": "test-policy",
            "backends": ["ipfs", "s3"],
            "replication_results": {
                "ipfs": {"success": True},
                "s3": {"success": True}
            }
        }
        
        # Test apply policy request
        response = client.post(
            "/api/v0/storage/apply-policy", 
            json={
                "content_id": "test-cid",
                "policy_name": "test-policy",
                "policy_rules": {
                    "file_size_threshold": 1024,
                    "high_availability": True,
                    "preferred_backends": ["ipfs", "s3"]
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["content_id"] == "test-cid"
        assert data["policy_name"] == "test-policy"
        
        # Verify bridge method was called
        bridge.apply_replication_policy.assert_called_once()
    
    def test_apply_replication_policy_without_bridge(self, controller_with_app):
        """Test applying replication policy without bridge."""
        client = controller_with_app["client"]
        controller = controller_with_app["controller"]
        
        # Remove bridge to test error handling
        controller.storage_bridge = None
        
        # Test apply policy request
        response = client.post(
            "/api/v0/storage/apply-policy", 
            json={
                "content_id": "test-cid",
                "policy_name": "test-policy",
                "policy_rules": {
                    "file_size_threshold": 1024,
                    "high_availability": True,
                    "preferred_backends": ["ipfs", "s3"]
                }
            }
        )
        
        # Should fail as replication policy requires the bridge
        assert response.status_code == 400
        assert "StorageBridge is not available" in response.json()["detail"]


@pytest.mark.skip("Pending implementation fixes")
class TestEnhancedStorageManagerController:
    """Test suite for enhanced functionality of the StorageManagerController."""
    
    @pytest.fixture
    def controller_with_app(self):
        """Create a controller with a FastAPI app for testing HTTP endpoints."""
        # Create FastAPI app and router
        app = FastAPI()
        router = APIRouter()
        
        # Mock backend models with additional capabilities
        mock_ipfs = MagicMock(name="ipfs_model")
        mock_s3 = MagicMock(name="s3_model")
        mock_filecoin = MagicMock(name="filecoin_model")
        mock_storacha = MagicMock(name="storacha_model")
        mock_huggingface = MagicMock(name="huggingface_model")
        
        # Set up mock verification capabilities
        mock_ipfs.verify_content = MagicMock(return_value={
            "success": True,
            "verification_status": "verified",
            "content_hash": "test-hash",
            "verification_time": time.time()
        })
        
        mock_s3.verify_content = MagicMock(return_value={
            "success": True,
            "verification_status": "verified", 
            "content_hash": "test-hash",
            "verification_time": time.time()
        })
        
        mock_filecoin.verify_content = MagicMock(return_value={
            "success": True,
            "verification_status": "verified",
            "content_hash": "test-hash",
            "deal_status": "active",
            "verification_time": time.time()
        })
        
        # Set up mock migration capabilities
        mock_ipfs.get_content = MagicMock(return_value={
            "success": True,
            "content": b"test content",
            "size": 12
        })
        
        mock_s3.put_content = MagicMock(return_value={
            "success": True,
            "location": "s3://bucket/key"
        })
        
        mock_filecoin.put_content = MagicMock(return_value={
            "success": True,
            "deal_id": "deal123"
        })
        
        mock_storacha.put_content = MagicMock(return_value={
            "success": True, 
            "car_cid": "storacha-cid"
        })
        
        # Mock backend capabilities detection
        for backend in [mock_ipfs, mock_s3, mock_filecoin, mock_storacha, mock_huggingface]:
            backend.get_stats = MagicMock(return_value={
                "success": True,
                "storage_used": 1024,
                "content_count": 10
            })
            
            # Add delete capability to test migration with deletion
            backend.delete_object = MagicMock(return_value={
                "success": True,
                "deleted": True
            })
        
        # Mock storage manager
        mock_storage_manager = MagicMock()
        mock_storage_manager.get_available_backends = MagicMock(return_value={
            "ipfs": True,
            "s3": True,
            "filecoin": True,
            "storacha": True,
            "huggingface": True
        })
        
        mock_storage_manager.get_all_models = MagicMock(return_value={
            "ipfs": mock_ipfs,
            "s3": mock_s3,
            "filecoin": mock_filecoin,
            "storacha": mock_storacha,
            "huggingface": mock_huggingface
        })
        
        mock_storage_manager.get_model = MagicMock(side_effect=lambda name: {
            "ipfs": mock_ipfs,
            "s3": mock_s3,
            "filecoin": mock_filecoin,
            "storacha": mock_storacha,
            "huggingface": mock_huggingface
        }.get(name))
        
        # Mock storage bridge
        mock_bridge = MagicMock()
        mock_storage_manager.storage_bridge = mock_bridge
        
        # Configure bridge methods
        mock_bridge.verify_content = MagicMock(return_value={
            "success": True,
            "content_id": "test-cid",
            "verification_results": {
                "ipfs": {"status": "verified", "hash": "test-hash"},
                "s3": {"status": "verified", "hash": "test-hash"},
                "filecoin": {"status": "verified", "hash": "test-hash"}
            },
            "identical": True
        })
        
        mock_bridge.transfer_content = MagicMock(return_value={
            "success": True,
            "source_backend": "ipfs",
            "target_backend": "filecoin",
            "content_id": "test-cid",
            "target_location": "deal123",
            "source_location": "Qm1234",
            "bytes_transferred": 1024
        })
        
        mock_bridge.apply_replication_policy = MagicMock(return_value={
            "success": True,
            "content_id": "test-cid",
            "source_backend": "ipfs",
            "backends_selected": ["s3", "filecoin"],
            "policy_applied": True,
            "successful_backends": ["s3", "filecoin"],
            "failed_backends": [],
            "bytes_transferred": 2048
        })
        
        # Initialize controller with mock storage manager
        controller = StorageManagerController(mock_storage_manager)
        controller.register_routes(router)
        
        # Mount router to app
        app.include_router(router, prefix="/api/v0")
        
        # Create test client
        client = TestClient(app)
        
        return {
            "app": app,
            "client": client,
            "controller": controller,
            "storage_manager": mock_storage_manager,
            "backends": {
                "ipfs": mock_ipfs,
                "s3": mock_s3,
                "filecoin": mock_filecoin,
                "storacha": mock_storacha,
                "huggingface": mock_huggingface
            },
            "bridge": mock_bridge
        }
    
    def test_verify_content_without_bridge(self, controller_with_app):
        """Test direct verification without using storage bridge."""
        client = controller_with_app["client"]
        controller = controller_with_app["controller"]
        
        # Remove bridge to test direct verification path
        controller.storage_manager.storage_bridge = None
        
        # Test verification with specified backends
        response = client.post(
            "/api/v0/storage/verify",
            json={
                "content_id": "test-cid",
                "backends": ["ipfs", "s3", "filecoin"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["content_id"] == "test-cid"
        assert "verified_backends" in data
        assert len(data["verified_backends"]) == 3
        assert "ipfs" in data["verified_backends"]
        assert "s3" in data["verified_backends"]
        assert "filecoin" in data["verified_backends"]
        
        # Verify each backend's verification method was called
        backends = controller_with_app["backends"]
        backends["ipfs"].verify_content.assert_called_once_with("test-cid")
        backends["s3"].verify_content.assert_called_once_with("test-cid")
        backends["filecoin"].verify_content.assert_called_once_with("test-cid")
    
    def test_verify_content_with_nonexistent_backend(self, controller_with_app):
        """Test verification with a nonexistent backend."""
        client = controller_with_app["client"]
        controller = controller_with_app["controller"]
        
        # Remove bridge to test direct verification path
        controller.storage_manager.storage_bridge = None
        
        # Test verification with a nonexistent backend
        response = client.post(
            "/api/v0/storage/verify",
            json={
                "content_id": "test-cid",
                "backends": ["ipfs", "nonexistent"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True  # Still succeeds with partial verification
        assert "verification_results" in data
        assert "nonexistent" in data["verification_results"]
        assert data["verification_results"]["nonexistent"]["success"] is False
        assert "Backend 'nonexistent' not found" in data["verification_results"]["nonexistent"]["error"]
    
    def test_verify_content_without_verify_method(self, controller_with_app):
        """Test verification with backend that doesn't support verification."""
        client = controller_with_app["client"]
        controller = controller_with_app["controller"]
        backends = controller_with_app["backends"]
        
        # Remove bridge to test direct verification path
        controller.storage_manager.storage_bridge = None
        
        # Remove verify_content method from huggingface backend
        delattr(backends["huggingface"], "verify_content")
        
        # Test verification with backend missing verify_content
        response = client.post(
            "/api/v0/storage/verify",
            json={
                "content_id": "test-cid",
                "backends": ["ipfs", "huggingface"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "verification_results" in data
        assert "huggingface" in data["verification_results"]
        
        # Should fall back to get_content if verify_content is not available
        backends["huggingface"].get_content.assert_called_once_with("test-cid")
    
    def test_migrate_content_direct_implementation(self, controller_with_app):
        """Test content migration using direct implementation (without bridge)."""
        client = controller_with_app["client"]
        controller = controller_with_app["controller"]
        backends = controller_with_app["backends"]
        
        # Remove bridge to test direct migration
        controller.storage_manager.storage_bridge = None
        
        # Test migration request
        response = client.post(
            "/api/v0/storage/migrate",
            json={
                "source_backend": "ipfs",
                "target_backend": "filecoin",
                "content_ids": ["cid1", "cid2", "cid3"],
                "options": {"retention": "permanent"},
                "delete_source": True,
                "verify_integrity": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["source_backend"] == "ipfs"
        assert data["target_backend"] == "filecoin"
        assert data["content_count"] == 3
        assert data["successful_count"] > 0
        assert "results" in data
        assert len(data["results"]) == 3
        
        # Verify source backend get_content was called for each CID
        assert backends["ipfs"].get_content.call_count == 3
        
        # Verify target backend put_content was called for each CID
        assert backends["filecoin"].put_content.call_count == 3
        
        # Verify deletion from source backend if delete_source is True
        assert backends["ipfs"].delete_object.call_count == 3
    
    def test_migrate_content_partial_failure(self, controller_with_app):
        """Test content migration with partial failures."""
        client = controller_with_app["client"]
        controller = controller_with_app["controller"]
        backends = controller_with_app["backends"]
        
        # Remove bridge to test direct migration
        controller.storage_manager.storage_bridge = None
        
        # Configure one failure in get_content
        original_get_content = backends["ipfs"].get_content
        call_count = 0
        
        def mock_get_content_with_failure(cid):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Fail on the second call
                return {
                    "success": False,
                    "error": "Content not found",
                    "error_type": "ContentNotFoundError"
                }
            return original_get_content(cid)
            
        backends["ipfs"].get_content = MagicMock(side_effect=mock_get_content_with_failure)
        
        # Test migration request
        response = client.post(
            "/api/v0/storage/migrate",
            json={
                "source_backend": "ipfs",
                "target_backend": "filecoin",
                "content_ids": ["cid1", "cid2", "cid3"],
                "delete_source": False,
                "verify_integrity": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False  # Overall failure due to partial failure
        assert data["content_count"] == 3
        assert data["successful_count"] == 2
        assert data["failed_count"] == 1
        
        # Check individual results
        assert "cid2" in data["results"]
        assert data["results"]["cid2"]["success"] is False
        assert "Content not found" in data["results"]["cid2"]["error"]
    
    def test_migration_with_verification_failure(self, controller_with_app):
        """Test migration with integrity verification failure."""
        client = controller_with_app["client"]
        controller = controller_with_app["controller"]
        backends = controller_with_app["backends"]
        
        # Set up bridge for verification but with a failure
        bridge = controller_with_app["bridge"]
        bridge.verify_content = MagicMock(return_value={
            "success": False,
            "error": "Content hash mismatch",
            "error_type": "VerificationError"
        })
        
        # Test migration with verification that will fail
        response = client.post(
            "/api/v0/storage/migrate",
            json={
                "source_backend": "ipfs",
                "target_backend": "filecoin",
                "content_ids": ["test-cid"],
                "delete_source": True,
                "verify_integrity": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that verification failed and marked the transfer as failed
        assert data["successful_count"] == 0
        assert data["failed_count"] == 1
        assert "results" in data
        assert "test-cid" in data["results"]
        assert data["results"]["test-cid"]["success"] is False
        
        # Verify content should not be deleted from source after verification failure
        backends["ipfs"].delete_object.assert_not_called()
    
    def test_apply_replication_policy(self, controller_with_app):
        """Test applying replication policy to content."""
        client = controller_with_app["client"]
        bridge = controller_with_app["bridge"]
        
        # Complex policy with multiple rules
        policy = {
            "name": "comprehensive-policy",
            "rules": {
                "size_threshold": 1024 * 1024,  # 1MB
                "importance_level": "high",
                "target_backends": {
                    "hot_storage": ["ipfs"],
                    "warm_storage": ["s3"],
                    "cold_storage": ["filecoin"]
                },
                "replication_factor": {
                    "hot": 3,
                    "warm": 2,
                    "cold": 1
                },
                "retention_period": {
                    "hot": "30d",
                    "warm": "180d",
                    "cold": "permanent"
                }
            }
        }
        
        # Test policy application
        response = client.post(
            "/api/v0/storage/apply-policy",
            json={
                "content_id": "test-cid",
                "policy": policy
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["content_id"] == "test-cid"
        assert "backends_selected" in data
        assert "policy_applied" in data
        assert data["policy_applied"] is True
        
        # Verify bridge method was called with correct parameters
        bridge.apply_replication_policy.assert_called_once_with(
            "test-cid",
            policy
        )
    
    def test_apply_policy_without_bridge(self, controller_with_app):
        """Test applying policy without bridge (should fail)."""
        client = controller_with_app["client"]
        controller = controller_with_app["controller"]
        
        # Remove bridge
        controller.storage_manager.storage_bridge = None
        
        # Test policy application
        response = client.post(
            "/api/v0/storage/apply-policy",
            json={
                "content_id": "test-cid",
                "policy": {"name": "test-policy"}
            }
        )
        
        # Should fail with appropriate error
        assert response.status_code == 400
        assert "Storage bridge not available" in response.json()["detail"]["error"]
    
    def test_backend_capabilities(self, controller_with_app):
        """Test accurate detection of backend capabilities."""
        client = controller_with_app["client"]
        
        # Get all backends status
        response = client.get("/api/v0/storage/status")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that each backend's capabilities are correctly reported
        assert "ipfs" in data["backends"]
        assert "capabilities" in data["backends"]["ipfs"]
        assert "content_retrieval" in data["backends"]["ipfs"]["capabilities"]
        
        assert "filecoin" in data["backends"]
        assert "capabilities" in data["backends"]["filecoin"]
        assert "deal_making" in data["backends"]["filecoin"]["capabilities"]
        
        assert "huggingface" in data["backends"]
        assert "capabilities" in data["backends"]["huggingface"]
        assert "model_registry" in data["backends"]["huggingface"]["capabilities"]


@pytest.mark.skip("Pending implementation fixes for AnyIO compatibility")
@pytest.mark.anyio
class TestStorageManagerControllerAnyIO:
    """Test suite for the AnyIO version of the StorageManagerController."""
    
    @pytest.fixture
    async def async_controller(self):
        """Create a controller with async model for AnyIO testing."""
        # Mock storage backends
        mock_ipfs = AsyncMock(name="ipfs_model")
        mock_s3 = AsyncMock(name="s3_model")
        mock_filecoin = AsyncMock(name="filecoin_model")
        
        # Set up mock backend capabilities
        mock_ipfs.get_status.return_value = {
            "success": True,
            "status": "online"
        }
        
        mock_s3.get_status.return_value = {
            "success": True,
            "status": "online"
        }
        
        mock_filecoin.get_status.return_value = {
            "success": True,
            "status": "online",
            "deal_count": 5
        }
        
        # Mock async storage manager
        mock_storage_manager = AsyncMock()
        mock_storage_manager.get_available_backends.return_value = {
            "ipfs": True,
            "s3": True,
            "filecoin": True
        }
        
        mock_storage_manager.get_all_models.return_value = {
            "ipfs": mock_ipfs,
            "s3": mock_s3,
            "filecoin": mock_filecoin
        }
        
        mock_storage_manager.get_model = AsyncMock(side_effect=lambda name: {
            "ipfs": mock_ipfs,
            "s3": mock_s3,
            "filecoin": mock_filecoin
        }.get(name))
        
        # Mock async storage bridge
        mock_bridge = AsyncMock()
        mock_storage_manager.storage_bridge = mock_bridge
        
        # Set up mock bridge responses
        mock_bridge.transfer_content.return_value = {
            "success": True,
            "operation": "transfer_content",
            "source_backend": "ipfs",
            "target_backend": "s3",
            "content_id": "test-cid",
            "bytes_transferred": 1024
        }
        
        mock_bridge.verify_content.return_value = {
            "success": True,
            "content_id": "test-cid",
            "identical": True
        }
        
        mock_bridge.apply_replication_policy.return_value = {
            "success": True,
            "content_id": "test-cid",
            "backends_selected": ["ipfs", "s3", "filecoin"],
            "policy_applied": True
        }
        
        # Initialize controller
        controller = StorageManagerController(mock_storage_manager)
        
        return {
            "controller": controller,
            "storage_manager": mock_storage_manager,
            "backends": {
                "ipfs": mock_ipfs,
                "s3": mock_s3,
                "filecoin": mock_filecoin
            },
            "bridge": mock_bridge
        }
    
    @pytest.mark.anyio
    async def test_async_handle_status_request(self, async_controller):
        """Test async version of handle_status_request method."""
        controller = async_controller["controller"]
        
        # Call the async method directly
        result = await controller.handle_status_request()
        
        # Verify result structure
        assert result["success"] is True
        assert "backends" in result
        assert len(result["backends"]) == 3
        assert "ipfs" in result["backends"]
        assert "s3" in result["backends"]
        assert "filecoin" in result["backends"]
    
    @pytest.mark.anyio
    async def test_async_handle_backend_status_request(self, async_controller):
        """Test async version of handle_backend_status_request method."""
        controller = async_controller["controller"]
        
        # Call the async method directly
        result = await controller.handle_backend_status_request(backend_name="ipfs")
        
        # Verify result structure
        assert result["success"] is True
        assert result["backend_name"] == "ipfs"
        assert "backend_info" in result
        
        # Test with non-existent backend
        with pytest.raises(HTTPException) as excinfo:
            await controller.handle_backend_status_request(backend_name="nonexistent")
        
        assert excinfo.value.status_code == 404
        assert "Backend not found" in excinfo.value.detail
    
    @pytest.mark.anyio
    async def test_async_handle_transfer_request(self, async_controller):
        """Test async version of handle_transfer_request method."""
        controller = async_controller["controller"]
        bridge = async_controller["bridge"]
        
        # Create transfer request
        request = StorageTransferRequest(
            source_backend="ipfs",
            target_backend="s3",
            content_id="test-cid",
            options={"retention": "standard"}
        )
        
        # Call the async method directly
        result = await controller.handle_transfer_request(request)
        
        # Verify result structure
        assert result["success"] is True
        assert result["source_backend"] == "ipfs"
        assert result["target_backend"] == "s3"
        assert result["content_id"] == "test-cid"
        
        # Verify bridge method was called
        bridge.transfer_content.assert_called_once()
    
    @pytest.mark.anyio
    async def test_async_handle_verify_request(self, async_controller):
        """Test async version of handle_verify_request method."""
        controller = async_controller["controller"]
        bridge = async_controller["bridge"]
        
        # Call verify method directly
        result = await controller.handle_verify_request(
            content_id="test-cid", 
            backends=["ipfs", "s3", "filecoin"]
        )
        
        # Verify result structure
        assert result["success"] is True
        assert result["content_id"] == "test-cid"
        
        # Verify bridge method was called
        bridge.verify_content.assert_called_once_with(
            content_id="test-cid",
            backends=["ipfs", "s3", "filecoin"],
            reference_backend=None
        )
    
    @pytest.mark.anyio
    async def test_async_handle_migration_request(self, async_controller):
        """Test async version of handle_migration_request method."""
        controller = async_controller["controller"]
        bridge = async_controller["bridge"]
        
        # Create migration request
        request = ContentMigrationRequest(
            source_backend="ipfs",
            target_backend="filecoin",
            content_ids=["cid1", "cid2"],
            options={"deal_duration": 540},
            delete_source=False,
            verify_integrity=True
        )
        
        # Configure bridge response
        bridge.transfer_content.return_value = {
            "success": True,
            "content_id": "cid1",
            "source_backend": "ipfs",
            "target_backend": "filecoin",
            "bytes_transferred": 1024
        }
        
        # Call migration method directly
        result = await controller.handle_migration_request(request)
        
        # Verify result structure
        assert result["success"] is True
        assert result["source_backend"] == "ipfs"
        assert result["target_backend"] == "filecoin"
        assert result["content_count"] == 2
        assert "results" in result
        
        # Bridge transfer_content should be called for each content ID
        assert bridge.transfer_content.call_count == 2
        
        # Verify verification was called since verify_integrity is True
        assert bridge.verify_content.call_count == 2
    
    @pytest.mark.anyio
    async def test_async_handle_replication_policy_request(self, async_controller):
        """Test async version of handle_replication_policy_request method."""
        controller = async_controller["controller"]
        bridge = async_controller["bridge"]
        
        # Create policy request
        request = ReplicationPolicyRequest(
            content_id="test-cid",
            policy={
                "name": "default-policy",
                "rules": {
                    "target_backends": ["ipfs", "s3", "filecoin"],
                    "replication_factor": 2
                }
            }
        )
        
        # Call replication policy method directly
        result = await controller.handle_replication_policy_request(request)
        
        # Verify result structure
        assert result["success"] is True
        assert result["content_id"] == "test-cid"
        assert "backends_selected" in result
        assert "policy_applied" in result
        
        # Verify bridge method was called with correct parameters
        bridge.apply_replication_policy.assert_called_once_with(
            "test-cid",
            request.policy
        )
    
    @pytest.mark.anyio
    async def test_async_error_handling(self, async_controller):
        """Test error handling in async methods."""
        controller = async_controller["controller"]
        bridge = async_controller["bridge"]
        
        # Configure bridge to raise an exception
        bridge.transfer_content.side_effect = Exception("Network error during transfer")
        
        # Create transfer request
        request = StorageTransferRequest(
            source_backend="ipfs",
            target_backend="s3",
            content_id="test-cid"
        )
        
        # Expect exception to be raised
        with pytest.raises(HTTPException) as excinfo:
            await controller.handle_transfer_request(request)
        
        assert excinfo.value.status_code == 500
        assert "Network error" in excinfo.value.detail["error"]
        assert excinfo.value.detail["error_type"] == "Exception"


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])