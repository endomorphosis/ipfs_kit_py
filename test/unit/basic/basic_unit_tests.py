#!/usr/bin/env python3
"""
Basic unit tests for ipfs_kit_py using unittest instead of pytest.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import logging

# Add the project root to sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestBackendStorageImport(unittest.TestCase):
    """Test importing and using BackendStorage class."""

    def test_backend_storage_import(self):
        """Test that BackendStorage can be imported."""
        from ipfs_kit_py.mcp.storage_manager import BackendStorage
        self.assertIsNotNone(BackendStorage)

class TestLotusKitAvailable(unittest.TestCase):
    """Test importing and using LOTUS_KIT_AVAILABLE."""

    def test_lotus_kit_available(self):
        """Test that LOTUS_KIT_AVAILABLE is properly defined."""
        from ipfs_kit_py.lotus_kit import LOTUS_KIT_AVAILABLE
        self.assertTrue(LOTUS_KIT_AVAILABLE)

@patch('ipfs_kit_py.ipfs_kit.ipfs_py')
class TestIPFSBasicFunctionality(unittest.TestCase):
    """Test basic IPFS functionality with mocks."""

    def test_ipfs_add(self, mock_ipfs):
        """Test adding content to IPFS."""
        from ipfs_kit_py.ipfs_kit import ipfs_kit

        # Configure mock
        mock_ipfs.return_value.add.return_value = {"Hash": "QmTestHash"}

        # Create instance with test config
        instance = ipfs_kit({"test_mode": True})

        # Test add functionality
        add_result = instance.add(b"test data")
        self.assertIn("Hash", add_result)
        self.assertEqual(add_result["Hash"], "QmTestHash")

    def test_ipfs_cat(self, mock_ipfs):
        """Test retrieving content from IPFS."""
        from ipfs_kit_py.ipfs_kit import ipfs_kit

        # Configure mock
        mock_ipfs.return_value.cat.return_value = b"test content"

        # Create instance with test config
        instance = ipfs_kit({"test_mode": True})

        # Test cat functionality
        cat_result = instance.cat("QmTestHash")
        self.assertEqual(cat_result, b"test content")

if __name__ == "__main__":
    unittest.main()
