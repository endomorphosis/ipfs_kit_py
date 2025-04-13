"""
Tests for metadata replication integration with MCP server.

These tests verify that the MCP server correctly handles the metadata replication
functionality and enforces the minimum replication factor of 3.
"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import pytest
import requests

# Import MCP components
from ipfs_kit_py.mcp.server import MCPServer
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


if __name__ == "__main__":
    unittest.main()