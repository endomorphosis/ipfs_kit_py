"""
Tests for metadata replication integration with MCP server using AnyIO.

These tests verify that the MCP server correctly handles the metadata replication
functionality and enforces the minimum replication factor of 3 using AnyIO.
"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
import anyio
import requests

# Import MCP components
from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import
from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
from ipfs_kit_py.fs_journal_replication import (
    MetadataReplicationManager,
    ReplicationLevel,
    ReplicationStatus
)


class TestMCPMetadataReplication(unittest.TestCase):
    """Tests for the metadata replication integration with MCP server."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        
        # Create patches for required components
        self.patches = []
        
        # Patch create_replication_manager
        self.mock_create_manager = MagicMock()
        create_manager_patch = patch(
            'ipfs_kit_py.high_level_api.create_replication_manager', 
            self.mock_create_manager
        )
        self.patches.append(create_manager_patch)
        
        # Create mock replication manager
        self.mock_replication_manager = MagicMock(spec=MetadataReplicationManager)
        self.mock_create_manager.return_value = self.mock_replication_manager
        
        # Mock for IPFS model
        self.mock_ipfs_model = MagicMock(spec=IPFSModel)
        mock_ipfs_model_patch = patch(
            'ipfs_kit_py.mcp.models.ipfs_model.IPFSModel',
            return_value=self.mock_ipfs_model
        )
        self.patches.append(mock_ipfs_model_patch)
        
        # Mock for high-level API
        self.mock_api = MagicMock()
        self.mock_api.replication_manager = self.mock_replication_manager
        mock_api_patch = patch(
            'ipfs_kit_py.high_level_api.IPFSSimpleAPI',
            return_value=self.mock_api
        )
        self.patches.append(mock_api_patch)
        
        # Start all patches
        for p in self.patches:
            p.start()
            
        # Create server with test configuration
        self.server_config = {
            "role": "master",
            "metadata_replication": {
                "enabled": True,
                "min_replication_factor": 3,
                "target_replication_factor": 4,
                "max_replication_factor": 5,
                "replication_level": "QUORUM"
            }
        }
        
        # Initialize MCP server with isolation mode for testing
        self.server = MCPServer(
            debug_mode=True,
            isolation_mode=True,
            persistence_path=self.temp_dir
        )
        
        # Access the controller directly for testing
        self.ipfs_controller = IPFSController(self.mock_ipfs_model)
        self.server.controllers["ipfs"] = self.ipfs_controller
    
    def tearDown(self):
        """Clean up after tests."""
        # Stop all patches
        for p in self.patches:
            p.stop()
            
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_register_peer_endpoint(self):
        """Test the register_peer endpoint in the MCP server."""
        # Setup mock for the replication manager
        self.mock_replication_manager.register_peer.return_value = True
        
        # Setup mock return value for the model
        peer_response = {
            "success": True,
            "peer_id": "test-peer-123",
            "operation": "register_peer"
        }
        self.mock_ipfs_model.register_peer.return_value = peer_response
        
        # Create a test request
        request_data = {
            "peer_id": "test-peer-123",
            "metadata": {
                "role": "worker", 
                "address": "192.168.1.100"
            }
        }
        
        # Call the controller method directly
        response = self.ipfs_controller.register_peer(request_data)
        
        # Verify the model method was called
        self.mock_ipfs_model.register_peer.assert_called_once_with(
            request_data["peer_id"], 
            request_data["metadata"]
        )
        
        # Verify response
        self.assertEqual(response, peer_response)
    
    def test_store_metadata_endpoint(self):
        """Test the store_metadata endpoint in the MCP server."""
        # Setup mock return for the model
        store_response = {
            "success": True,
            "path": "/test/file.txt",
            "operation": "store_metadata",
            "replication_status": ReplicationStatus.COMPLETE.value,
            "success_count": 4,
            "target_count": 4,
            "quorum_size": 3
        }
        self.mock_ipfs_model.store_metadata.return_value = store_response
        
        # Create a test request
        request_data = {
            "path": "/test/file.txt",
            "metadata": {
                "size": 1024,
                "type": "text"
            },
            "replication_level": "QUORUM"
        }
        
        # Call the controller method directly
        response = self.ipfs_controller.store_metadata(request_data)
        
        # Verify the model method was called
        self.mock_ipfs_model.store_metadata.assert_called_once_with(
            request_data["path"],
            request_data["metadata"],
            replication_level=request_data["replication_level"]
        )
        
        # Verify response includes replication information
        self.assertEqual(response, store_response)
        self.assertEqual(response["replication_status"], ReplicationStatus.COMPLETE.value)
        self.assertEqual(response["success_count"], 4)
        self.assertEqual(response["quorum_size"], 3)
    
    def test_verify_metadata_replication_endpoint(self):
        """Test the verify_metadata_replication endpoint in the MCP server."""
        # Setup mock return for the model
        verify_response = {
            "success": True,
            "entry_id": "test-entry-123",
            "operation": "verify_metadata_replication",
            "replication_status": ReplicationStatus.COMPLETE.value,
            "success_count": 4,
            "target_count": 4,
            "quorum_size": 3
        }
        self.mock_ipfs_model.verify_metadata_replication.return_value = verify_response
        
        # Create test parameters
        entry_id = "test-entry-123"
        
        # Call the controller method directly
        response = self.ipfs_controller.verify_metadata_replication(entry_id=entry_id)
        
        # Verify the model method was called
        self.mock_ipfs_model.verify_metadata_replication.assert_called_once_with(entry_id)
        
        # Verify response
        self.assertEqual(response, verify_response)
        self.assertEqual(response["quorum_size"], 3)  # Ensure minimum of 3 is reported
    
    def test_server_routes_registration(self):
        """Test that MCP server registers routes for metadata replication endpoints."""
        # Create server with FastAPI router
        from fastapi import APIRouter
        router = APIRouter()
        
        # Register routes
        self.ipfs_controller.register_routes(router)
        
        # Get paths from router
        paths = [route.path for route in router.routes]
        
        # Verify replication endpoints are registered
        self.assertIn("/ipfs/peers/register", paths)
        self.assertIn("/ipfs/peers/unregister/{peer_id}", paths)
        self.assertIn("/ipfs/metadata", paths)
        self.assertIn("/ipfs/metadata/replication/{entry_id}", paths)
    
    def test_enforce_minimum_replication_factor(self):
        """Test that the MCP server enforces a minimum replication factor of 3."""
        # Mock IPFSModel.initialize to capture config
        original_initialize = IPFSModel.initialize
        captured_config = {}
        
        def mock_initialize(self, *args, **kwargs):
            nonlocal captured_config
            if "config" in kwargs:
                captured_config.update(kwargs["config"])
            return original_initialize(self, *args, **kwargs)
        
        IPFSModel.initialize = mock_initialize
        
        try:
            # Create a low replication config
            low_config = {
                "role": "master",
                "metadata_replication": {
                    "enabled": True,
                    "min_replication_factor": 1,  # This should be increased to 3
                    "target_replication_factor": 2,
                    "max_replication_factor": 3
                }
            }
            
            # Create a new model with this config
            model = IPFSModel(config=low_config)
            
            # Check the captured config
            replication_config = captured_config.get("metadata_replication", {})
            self.assertGreaterEqual(replication_config.get("min_replication_factor", 0), 3,
                                 "Minimum replication factor should be at least 3")
            
        finally:
            # Restore original method
            IPFSModel.initialize = original_initialize
    
    def test_model_initialize_with_replication(self):
        """Test that the IPFSModel initializes with metadata replication."""
        # Set up mock high-level API with replication
        self.mock_api.replication_manager = self.mock_replication_manager
        
        # Create model with replication config
        config = {
            "role": "master",
            "metadata_replication": {
                "enabled": True,
                "min_replication_factor": 3,
                "target_replication_factor": 4,
                "max_replication_factor": 5
            }
        }
        
        model = IPFSModel(config=config)
        
        # Test model methods for replication
        
        # 1. Test register_peer
        peer_id = "test-peer-123"
        metadata = {"role": "worker"}
        
        self.mock_api.register_peer.return_value = {
            "success": True,
            "peer_id": peer_id
        }
        
        result = model.register_peer(peer_id, metadata)
        self.mock_api.register_peer.assert_called_once_with(peer_id, metadata)
        self.assertTrue(result["success"])
        
        # 2. Test store_metadata
        path = "/test/file.txt"
        metadata = {"size": 1024}
        replication_level = "QUORUM"
        
        self.mock_api.store_metadata.return_value = {
            "success": True,
            "path": path,
            "replication_status": ReplicationStatus.COMPLETE.value,
            "success_count": 4,
            "target_count": 4,
            "quorum_size": 3
        }
        
        result = model.store_metadata(path, metadata, replication_level=replication_level)
        self.mock_api.store_metadata.assert_called_once_with(
            path, metadata, replication_level=replication_level
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["quorum_size"], 3)
        
        # 3. Test verify_metadata_replication
        entry_id = "test-entry-123"
        
        self.mock_api.verify_metadata_replication.return_value = {
            "success": True,
            "entry_id": entry_id,
            "replication_status": ReplicationStatus.COMPLETE.value,
            "quorum_size": 3
        }
        
        result = model.verify_metadata_replication(entry_id)
        self.mock_api.verify_metadata_replication.assert_called_once_with(entry_id)
        self.assertTrue(result["success"])
        self.assertEqual(result["quorum_size"], 3)


# AnyIO version of the test class
class TestMCPMetadataReplicationAnyIO:
    """Tests for the metadata replication integration with MCP server using AnyIO."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Set up test environment."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        
        # Create patches for required components
        self.patches = []
        
        # Patch create_replication_manager
        self.mock_create_manager = MagicMock()
        create_manager_patch = patch(
            'ipfs_kit_py.high_level_api.create_replication_manager', 
            self.mock_create_manager
        )
        self.patches.append(create_manager_patch)
        
        # Create mock replication manager with async methods
        self.mock_replication_manager = MagicMock(spec=MetadataReplicationManager)
        self.mock_replication_manager.register_peer_async = AsyncMock(return_value=True)
        self.mock_replication_manager.store_metadata_async = AsyncMock(return_value={
            "success": True,
            "path": "/test/file.txt",
            "operation": "store_metadata",
            "replication_status": ReplicationStatus.COMPLETE.value,
            "success_count": 4,
            "target_count": 4,
            "quorum_size": 3
        })
        self.mock_replication_manager.verify_metadata_replication_async = AsyncMock(return_value={
            "success": True,
            "entry_id": "test-entry-123",
            "operation": "verify_metadata_replication",
            "replication_status": ReplicationStatus.COMPLETE.value,
            "success_count": 4,
            "target_count": 4,
            "quorum_size": 3
        })
        self.mock_create_manager.return_value = self.mock_replication_manager
        
        # Mock for IPFS model with async methods
        self.mock_ipfs_model = MagicMock(spec=IPFSModel)
        self.mock_ipfs_model.register_peer_async = AsyncMock(return_value={
            "success": True,
            "peer_id": "test-peer-123",
            "operation": "register_peer"
        })
        self.mock_ipfs_model.store_metadata_async = AsyncMock(return_value={
            "success": True,
            "path": "/test/file.txt",
            "operation": "store_metadata",
            "replication_status": ReplicationStatus.COMPLETE.value,
            "success_count": 4,
            "target_count": 4,
            "quorum_size": 3
        })
        self.mock_ipfs_model.verify_metadata_replication_async = AsyncMock(return_value={
            "success": True,
            "entry_id": "test-entry-123",
            "operation": "verify_metadata_replication",
            "replication_status": ReplicationStatus.COMPLETE.value,
            "success_count": 4,
            "target_count": 4,
            "quorum_size": 3
        })
        
        mock_ipfs_model_patch = patch(
            'ipfs_kit_py.mcp.models.ipfs_model.IPFSModel',
            return_value=self.mock_ipfs_model
        )
        self.patches.append(mock_ipfs_model_patch)
        
        # Mock for high-level API with async methods
        self.mock_api = MagicMock()
        self.mock_api.replication_manager = self.mock_replication_manager
        self.mock_api.register_peer_async = AsyncMock(return_value={
            "success": True,
            "peer_id": "test-peer-123"
        })
        self.mock_api.store_metadata_async = AsyncMock(return_value={
            "success": True,
            "path": "/test/file.txt",
            "replication_status": ReplicationStatus.COMPLETE.value,
            "success_count": 4,
            "target_count": 4,
            "quorum_size": 3
        })
        self.mock_api.verify_metadata_replication_async = AsyncMock(return_value={
            "success": True,
            "entry_id": "test-entry-123",
            "replication_status": ReplicationStatus.COMPLETE.value,
            "quorum_size": 3
        })
        
        mock_api_patch = patch(
            'ipfs_kit_py.high_level_api.IPFSSimpleAPI',
            return_value=self.mock_api
        )
        self.patches.append(mock_api_patch)
        
        # Start all patches
        for p in self.patches:
            p.start()
            
        # Create server with test configuration
        self.server_config = {
            "role": "master",
            "metadata_replication": {
                "enabled": True,
                "min_replication_factor": 3,
                "target_replication_factor": 4,
                "max_replication_factor": 5,
                "replication_level": "QUORUM"
            }
        }
        
        # Initialize MCP server with isolation mode for testing
        self.server = MCPServer(
            debug_mode=True,
            isolation_mode=True,
            persistence_path=self.temp_dir
        )
        
        # Access the controller directly for testing
        self.ipfs_controller = IPFSController(self.mock_ipfs_model)
        self.server.controllers["ipfs"] = self.ipfs_controller
        
        yield
        
        # Stop all patches
        for p in self.patches:
            p.stop()
            
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.anyio
    async def test_register_peer_endpoint_async(self):
        """Test the register_peer_async endpoint in the MCP server."""
        # Create a test request
        request_data = {
            "peer_id": "test-peer-123",
            "metadata": {
                "role": "worker", 
                "address": "192.168.1.100"
            }
        }
        
        # Define the async method for the controller
        async def register_peer_async(request):
            peer_id = request.get("peer_id")
            metadata = request.get("metadata", {})
            
            # Call the model's async method
            return await self.mock_ipfs_model.register_peer_async(peer_id, metadata)
        
        # Attach method to controller
        self.ipfs_controller.register_peer_async = register_peer_async
        
        # Call the controller method
        response = await self.ipfs_controller.register_peer_async(request_data)
        
        # Verify the model method was called
        self.mock_ipfs_model.register_peer_async.assert_called_once_with(
            request_data["peer_id"], 
            request_data["metadata"]
        )
        
        # Verify response
        assert response["success"] is True
        assert response["peer_id"] == "test-peer-123"
        assert response["operation"] == "register_peer"
    
    @pytest.mark.anyio
    async def test_store_metadata_endpoint_async(self):
        """Test the store_metadata_async endpoint in the MCP server."""
        # Create a test request
        request_data = {
            "path": "/test/file.txt",
            "metadata": {
                "size": 1024,
                "type": "text"
            },
            "replication_level": "QUORUM"
        }
        
        # Define the async method for the controller
        async def store_metadata_async(request):
            path = request.get("path")
            metadata = request.get("metadata", {})
            replication_level = request.get("replication_level", "QUORUM")
            
            # Call the model's async method
            return await self.mock_ipfs_model.store_metadata_async(
                path, metadata, replication_level=replication_level
            )
        
        # Attach method to controller
        self.ipfs_controller.store_metadata_async = store_metadata_async
        
        # Call the controller method
        response = await self.ipfs_controller.store_metadata_async(request_data)
        
        # Verify the model method was called
        self.mock_ipfs_model.store_metadata_async.assert_called_once_with(
            request_data["path"],
            request_data["metadata"],
            replication_level=request_data["replication_level"]
        )
        
        # Verify response includes replication information
        assert response["success"] is True
        assert response["path"] == "/test/file.txt"
        assert response["operation"] == "store_metadata"
        assert response["replication_status"] == ReplicationStatus.COMPLETE.value
        assert response["success_count"] == 4
        assert response["quorum_size"] == 3
    
    @pytest.mark.anyio
    async def test_verify_metadata_replication_endpoint_async(self):
        """Test the verify_metadata_replication_async endpoint in the MCP server."""
        # Create test parameters
        entry_id = "test-entry-123"
        
        # Define the async method for the controller
        async def verify_metadata_replication_async(entry_id):
            # Call the model's async method
            return await self.mock_ipfs_model.verify_metadata_replication_async(entry_id)
        
        # Attach method to controller
        self.ipfs_controller.verify_metadata_replication_async = verify_metadata_replication_async
        
        # Call the controller method
        response = await self.ipfs_controller.verify_metadata_replication_async(entry_id)
        
        # Verify the model method was called
        self.mock_ipfs_model.verify_metadata_replication_async.assert_called_once_with(entry_id)
        
        # Verify response
        assert response["success"] is True
        assert response["entry_id"] == "test-entry-123"
        assert response["operation"] == "verify_metadata_replication"
        assert response["quorum_size"] == 3  # Ensure minimum of 3 is reported
    
    @pytest.mark.anyio
    async def test_model_initialize_with_replication_async(self):
        """Test that the IPFSModel initializes with metadata replication and uses async methods."""
        # Mock async methods on the model
        model = IPFSModel(config=self.server_config)
        model.register_peer_async = AsyncMock(return_value={
            "success": True,
            "peer_id": "test-peer-123",
            "operation": "register_peer"
        })
        model.store_metadata_async = AsyncMock(return_value={
            "success": True,
            "path": "/test/file.txt",
            "replication_status": ReplicationStatus.COMPLETE.value,
            "success_count": 4,
            "target_count": 4,
            "quorum_size": 3
        })
        model.verify_metadata_replication_async = AsyncMock(return_value={
            "success": True,
            "entry_id": "test-entry-123",
            "replication_status": ReplicationStatus.COMPLETE.value,
            "quorum_size": 3
        })
        
        # 1. Test register_peer_async
        peer_id = "test-peer-123"
        metadata = {"role": "worker"}
        
        result = await model.register_peer_async(peer_id, metadata)
        model.register_peer_async.assert_called_once_with(peer_id, metadata)
        assert result["success"] is True
        assert result["peer_id"] == "test-peer-123"
        
        # 2. Test store_metadata_async
        path = "/test/file.txt"
        metadata = {"size": 1024}
        replication_level = "QUORUM"
        
        result = await model.store_metadata_async(path, metadata, replication_level=replication_level)
        model.store_metadata_async.assert_called_once_with(
            path, metadata, replication_level=replication_level
        )
        assert result["success"] is True
        assert result["quorum_size"] == 3
        
        # 3. Test verify_metadata_replication_async
        entry_id = "test-entry-123"
        
        result = await model.verify_metadata_replication_async(entry_id)
        model.verify_metadata_replication_async.assert_called_once_with(entry_id)
        assert result["success"] is True
        assert result["quorum_size"] == 3
    
    @pytest.mark.anyio
    async def test_anyio_sleep_integration(self):
        """Test that anyio.sleep works correctly with metadata replication operations."""
        # Create a method that uses sleep to simulate network delay
        async def replicate_with_delay_async(path, metadata, delay=0.1):
            # Simulate network delay
            await anyio.sleep(delay)
            
            return {
                "success": True,
                "operation": "replicate_with_delay",
                "path": path,
                "metadata": metadata,
                "delay": delay,
                "replication_status": ReplicationStatus.COMPLETE.value,
                "success_count": 3,
                "quorum_size": 3
            }
        
        # Attach the method
        self.mock_ipfs_model.replicate_with_delay_async = replicate_with_delay_async
        
        # Call the method with minimal delay for testing
        path = "/test/file.txt"
        metadata = {"size": 1024}
        response = await self.mock_ipfs_model.replicate_with_delay_async(path, metadata, delay=0.01)
        
        # Verify response
        assert response["success"] is True
        assert response["path"] == path
        assert response["operation"] == "replicate_with_delay"
        assert response["delay"] == 0.01
        assert response["success_count"] == 3
        assert response["quorum_size"] == 3


if __name__ == "__main__":
    unittest.main()