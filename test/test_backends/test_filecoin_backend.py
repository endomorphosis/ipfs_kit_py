"""
Tests for the Filecoin backend implementation.

This module tests the Filecoin backend to ensure it properly implements
the required BackendStorage interface.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import io

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from ipfs_kit_py.mcp.storage_manager.backends.filecoin_backend import FilecoinBackend
from ipfs_kit_py.mcp.storage_manager.backend_base import BackendStorage
from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType


class TestFilecoinBackend(unittest.TestCase):
    """Test case for Filecoin backend."""

    @patch('ipfs_kit_py.mcp.storage_manager.backends.filecoin_backend.FilecoinBackend._setup_client', return_value=None)
    def setUp(self, mock_setup):
        """Set up the test environment."""
        # Mock the lotus and filecoin implementations
        self.mock_lotus = MagicMock()
        self.mock_filecoin = MagicMock()

        # Create mock resources and metadata
        self.resources = {
            "lotus_api": "http://localhost:1234/rpc/v0",
            "lotus_token": "mock-token"
        }
        self.metadata = {
            "default_miner": "t01000",
            "replication_count": 2
        }

        # Create patchers
        self.lotus_patch = patch('ipfs_kit_py.lotus_kit.lotus_kit', return_value=self.mock_lotus)
        self.filecoin_patch = patch('ipfs_kit_py.filecoin_storage.filecoin_storage',
                                    return_value=self.mock_filecoin)

        # Start patchers
        self.mock_lotus_kit = self.lotus_patch.start()
        self.mock_filecoin_storage = self.filecoin_patch.start()

        # Create backend
        self.backend = FilecoinBackend(self.resources, self.metadata)
        self.backend.mode = "lotus"  # Force lotus mode for testing

    def tearDown(self):
        """Clean up after tests."""
        # Stop patchers
        self.lotus_patch.stop()
        self.filecoin_patch.stop()

    def test_inheritance(self):
        """Test that FilecoinBackend inherits from BackendStorage."""
        self.assertIsInstance(self.backend, BackendStorage)

    def test_backend_type(self):
        """Test that the backend has the correct type."""
        self.assertEqual(self.backend.backend_type, StorageBackendType.FILECOIN)

    def test_get_name(self):
        """Test the get_name method."""
        self.assertEqual(self.backend.get_name(), "filecoin")

    def test_add_content(self):
        """Test the add_content method."""
        # Configure the mock
        self.mock_lotus.lotus_client_deal.return_value = {
            "success": True,
            "cid": "test-cid",
            "deals": ["deal1", "deal2"]
        }

        # Call add_content
        content = b"test content"
        result = self.backend.add_content(content, {"miner": "t01000"})

        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["identifier"], "test-cid")

        # Verify the underlying method was called
        self.assertTrue(self.mock_lotus.lotus_client_deal.called or
                       self.mock_lotus.lotus_client_deal_auto.called)

    def test_get_content(self):
        """Test the get_content method."""
        # Configure the mock
        self.mock_lotus.lotus_client_retrieve.return_value = {
            "success": True,
            "output_path": "/tmp/test-output"
        }

        # Mock the open function to return test data
        with patch("builtins.open", mock_open := MagicMock()):
            # Configure the mock to return a file-like object with test data
            mock_file = MagicMock()
            mock_file.read.return_value = b"test content data"
            mock_open.return_value.__enter__.return_value = mock_file

            # Call get_content
            result = self.backend.get_content("test-cid")

            # Verify the result
            self.assertTrue(result["success"])
            self.assertEqual(result["data"], b"test content data")

            # Verify the underlying method was called
            self.assertTrue(self.mock_lotus.lotus_client_retrieve.called)

    def test_remove_content(self):
        """Test the remove_content method."""
        # Configure the mock
        self.mock_lotus.lotus_client_cancel_pending_deals.return_value = {
            "success": True,
            "cancelled_deals": ["deal1"]
        }

        # Call remove_content
        result = self.backend.remove_content("test-cid")

        # Verify the result
        self.assertTrue(result["success"])

        # Verify the underlying method was called
        self.assertTrue(self.mock_lotus.lotus_client_cancel_pending_deals.called)

    def test_get_metadata(self):
        """Test the get_metadata method."""
        # Configure the mock
        self.mock_lotus.lotus_client_find_deal.return_value = {
            "success": True,
            "deals": [
                {
                    "deal_id": "deal1",
                    "state": "active",
                    "miner": "t01000",
                    "size": 1024
                }
            ],
            "active_deals": 1
        }

        self.mock_lotus.lotus_get_metadata.return_value = {
            "success": True,
            "metadata": {
                "custom_field": "custom_value"
            }
        }

        # Call get_metadata
        result = self.backend.get_metadata("test-cid")

        # Verify the result
        self.assertTrue(result["success"])
        self.assertIn("metadata", result)
        self.assertEqual(result["metadata"]["active_deals"], 1)
        self.assertEqual(result["metadata"]["custom_field"], "custom_value")

        # Verify the underlying methods were called
        self.assertTrue(self.mock_lotus.lotus_client_find_deal.called)
        self.assertTrue(self.mock_lotus.lotus_get_metadata.called)

if __name__ == "__main__":
    unittest.main()
