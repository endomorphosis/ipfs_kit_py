"""
Tests for the Storacha backend implementation.

This module tests the Storacha backend to ensure it properly implements
the required BackendStorage interface.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import io
import json

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from ipfs_kit_py.mcp.storage_manager.backends.storacha_backend import StorachaBackend
from ipfs_kit_py.mcp.storage_manager.backend_base import BackendStorage
from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType


class MockResponse:
    """Mock response for requests library."""
    def __init__(self, status_code, json_data=None, content=None, headers=None):
        self.status_code = status_code
        self._json_data = json_data
        self._content = content or b""
        self.headers = headers or {}
        self.text = str(content or "") if not isinstance(content, bytes) else content.decode('utf-8', errors='ignore')
        
    def json(self):
        return self._json_data
        
    @property
    def content(self):
        return self._content


class TestStorachaBackend(unittest.TestCase):
    """Test case for Storacha backend."""

    def setUp(self):
        """Set up the test environment."""
        # Create patchers
        self.connection_mgr_patcher = patch('ipfs_kit_py.mcp.storage_manager.backends.storacha_backend.StorachaConnectionManager')
        self.executor_patcher = patch('ipfs_kit_py.mcp.storage_manager.backends.storacha_backend.ThreadPoolExecutor')
        
        # Start patchers
        self.mock_connection_mgr = self.connection_mgr_patcher.start()
        self.mock_executor = self.executor_patcher.start()
        
        # Configure mock connection manager
        self.connection_instance = MagicMock()
        self.mock_connection_mgr.return_value = self.connection_instance
        
        # Create resources and metadata
        self.resources = {
            "api_key": "test-api-key",
            "endpoints": ["https://test-endpoint.example.com"],
            "mock_mode": True
        }
        
        self.metadata = {
            "cache_ttl": 3600,
            "cache_size_limit": 10485760  # 10MB
        }
        
        # Create backend
        self.backend = StorachaBackend(self.resources, self.metadata)
        
    def tearDown(self):
        """Clean up after tests."""
        # Stop patchers
        self.connection_mgr_patcher.stop()
        self.executor_patcher.stop()

    def test_inheritance(self):
        """Test that StorachaBackend inherits from BackendStorage."""
        self.assertIsInstance(self.backend, BackendStorage)
        
    def test_backend_type(self):
        """Test that the backend has the correct type."""
        self.assertEqual(self.backend.backend_type, StorageBackendType.STORACHA)
        
    def test_get_name(self):
        """Test the get_name method."""
        self.assertEqual(self.backend.get_name(), "storacha")

    def test_add_content(self):
        """Test the add_content method calls store with correct arguments."""
        # Set up response for successful upload
        self.connection_instance.post.return_value = MockResponse(
            200, json_data={"cid": "test-cid-123"}
        )
        
        # Test with string content
        content = "test content"
        metadata = {"test_key": "test_value"}
        
        result = self.backend.add_content(content, metadata)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["identifier"], "test-cid-123")
        
        # Verify the connection manager was called
        self.connection_instance.post.assert_called_once()
        call_args = self.connection_instance.post.call_args[0]
        self.assertEqual(call_args[0], "upload")  # Endpoint
        
    def test_get_content(self):
        """Test the get_content method calls retrieve with correct arguments."""
        # Set up responses for content retrieval
        self.connection_instance.get.side_effect = [
            # First call to get content
            MockResponse(
                200, 
                content=b"test content data", 
                headers={"Content-Type": "text/plain"}
            ),
            # Second call to get metadata
            MockResponse(
                200,
                json_data={"metadata": {"test_key": "test_value"}}
            )
        ]
        
        # Test retrieving content
        result = self.backend.get_content("test-cid-123")
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["data"], b"test content data")
        
        # Verify the connection manager was called
        self.assertEqual(self.connection_instance.get.call_count, 2)
        call_args = self.connection_instance.get.call_args_list[0][0]
        self.assertEqual(call_args[0], "content/cid/test-cid-123")  # Endpoint
        
    def test_remove_content(self):
        """Test the remove_content method calls delete with correct arguments."""
        # Mock cache paths to test cleanup
        self.backend._cache_path = MagicMock(return_value="/fake/cache/path")
        
        # Set up file system mocks for cache cleanup
        with patch('os.path.exists', return_value=True), \
             patch('os.remove') as mock_remove, \
             patch('os.path.getsize', return_value=1024):
            
            result = self.backend.remove_content("test-cid-123")
            
            # Verify the result
            self.assertTrue(result["success"])
            
            # Verify cache was cleaned up
            self.assertEqual(mock_remove.call_count, 2)  # Two calls - one for file, one for metadata
    
    def test_get_metadata(self):
        """Test the get_metadata method."""
        # Set up responses for status and metadata
        self.connection_instance.get.side_effect = [
            # First call for status
            MockResponse(
                200,
                json_data={"pin": {"status": "pinned"}}
            ),
            # Second call for metadata
            MockResponse(
                200,
                json_data={"metadata": {"test_key": "test_value"}}
            )
        ]
        
        # Test getting metadata
        result = self.backend.get_metadata("test-cid-123")
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["metadata"], {"test_key": "test_value"})
        
        # Verify the connection manager was called
        self.assertEqual(self.connection_instance.get.call_count, 2)
        call_args = self.connection_instance.get.call_args_list[0][0]
        self.assertEqual(call_args[0], "status/cid/test-cid-123")  # Endpoint
        
    def test_update_metadata(self):
        """Test the update_metadata method."""
        # Set up response for metadata update
        self.connection_instance.put.return_value = MockResponse(
            200,
            json_data={"success": True}
        )
        
        # Add test metadata to cache for update
        self.backend._metadata_cache = {"test-cid-123": {"metadata": {"existing": "value"}}}
        
        # Test updating metadata
        new_metadata = {"new_key": "new_value"}
        result = self.backend.update_metadata("test-cid-123", new_metadata)
        
        # Verify the result
        self.assertTrue(result["success"])
        
        # Verify the connection manager was called
        self.connection_instance.put.assert_called_once()
        call_args = self.connection_instance.put.call_args[0]
        self.assertEqual(call_args[0], "metadata/cid/test-cid-123")  # Endpoint
        
        # Verify cache was updated
        updated_metadata = self.backend._metadata_cache["test-cid-123"]["metadata"]
        self.assertEqual(updated_metadata["new_key"], "new_value")
        self.assertEqual(updated_metadata["existing"], "value")  # Original value preserved
        
if __name__ == "__main__":
    unittest.main()