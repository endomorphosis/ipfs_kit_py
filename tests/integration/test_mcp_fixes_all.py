#!/usr/bin/env python3
"""
Comprehensive test for MCP server fixes.

This test focuses on the fixes made to handle raw bytes responses from IPFS methods:
1. get_content
2. pin_content
3. unpin_content
4. list_pins
5. add_content
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import json
import time

# Add the parent directory to the path to enable importing ipfs_kit_py
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController

class TestMCPFixes(unittest.TestCase):
    """Test the MCP server fixes."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock IPFS instance that returns bytes for cat method
        self.mock_ipfs = MagicMock()
        
        # Mock cache manager
        self.mock_cache_manager = MagicMock()
        self.mock_cache_manager.get.return_value = None
        
        # Mock ipfs_kit
        self.mock_ipfs_kit = MagicMock()
        
        # Create IPFSModel with mocked dependencies
        self.ipfs_model = IPFSModel(self.mock_ipfs, self.mock_cache_manager)
        self.ipfs_model.ipfs_kit = self.mock_ipfs_kit
        
        # Patch normalize_response so it doesn't interfere with tests
        self.normalize_patch = patch('ipfs_kit_py.mcp.models.ipfs_model.normalize_response', 
                                    side_effect=lambda x, *args, **kwargs: x)
        self.mock_normalize = self.normalize_patch.start()
        
    def tearDown(self):
        """Tear down test fixtures."""
        self.normalize_patch.stop()

    def test_get_content_bytes_response(self):
        """Test get_content method with bytes response."""
        # Setup the mock to return bytes
        test_bytes = b"test content data"
        self.mock_ipfs.cat.return_value = test_bytes
        
        # Call the method
        result = self.ipfs_model.get_content("test-cid")
        
        # Verify result
        self.assertTrue(result.get("success", False))
        self.assertEqual(result.get("operation"), "get_content")
        self.assertEqual(result.get("data"), test_bytes)

    def test_pin_content_bytes_response(self):
        """Test pin_content method with bytes response."""
        # Setup the mock to return bytes
        test_bytes = b"pin response data"
        self.mock_ipfs.pin.return_value = test_bytes
        
        # Call the method
        result = self.ipfs_model.pin_content("test-cid")
        
        # Verify result
        self.assertTrue(result.get("success", False))
        self.assertEqual(result.get("operation"), "pin_content")
        self.assertEqual(result.get("data"), test_bytes)

    def test_unpin_content_bytes_response(self):
        """Test unpin_content method with bytes response."""
        # Setup the mock to return bytes
        test_bytes = b"unpin response data"
        self.mock_ipfs.unpin.return_value = test_bytes
        
        # Call the method
        result = self.ipfs_model.unpin_content("test-cid")
        
        # Verify result
        self.assertTrue(result.get("success", False))
        self.assertEqual(result.get("operation"), "unpin_content")
        self.assertEqual(result.get("data"), test_bytes)

    def test_list_pins_bytes_response(self):
        """Test list_pins method with bytes response."""
        # Setup the mock to return bytes
        test_bytes = b"list pins response data"
        self.mock_ipfs.list_pins.return_value = test_bytes
        
        # Call the method
        result = self.ipfs_model.list_pins()
        
        # Verify result
        self.assertTrue(result.get("success", False))
        self.assertEqual(result.get("operation"), "list_pins")
        self.assertEqual(result.get("data"), test_bytes)
        self.assertIn("Keys", result)
        self.assertIn("pins", result)

    def test_add_content_bytes_response(self):
        """Test add_content method with bytes response."""
        # Setup the mock to return bytes
        test_bytes = b"add response data"
        self.mock_ipfs.add_file.return_value = test_bytes
        
        # Need to patch os.unlink to avoid actual file deletion
        with patch('os.unlink'):
            # Call the method with string content
            result = self.ipfs_model.add_content("test content")
            
            # Verify result
            self.assertTrue(result.get("success", False))
            self.assertEqual(result.get("operation"), "add_content")
            self.assertEqual(result.get("data"), test_bytes)

    def test_model_api_directly(self):
        """Test that the controller can work with the model API directly."""
        # Since the controller methods are async and we want to keep this test simple,
        # we'll directly test that the model API methods return the correct format
        # when the controller would use them.
        
        # Test that get_content returns appropriate structure
        self.mock_ipfs.cat.return_value = b"controller test content"
        result = self.ipfs_model.get_content("test-cid")
        
        # This is what the controller would check for
        self.assertTrue(result.get("success", False))
        self.assertEqual(result.get("operation"), "get_content")
        
        # Test that pin_content returns appropriate structure
        self.mock_ipfs.pin.return_value = b"pin response"
        result = self.ipfs_model.pin_content("test-cid")
        
        self.assertTrue(result.get("success", False))
        self.assertEqual(result.get("operation"), "pin_content")
        
        # Test that unpin_content returns appropriate structure
        self.mock_ipfs.unpin.return_value = b"unpin response"
        result = self.ipfs_model.unpin_content("test-cid")
        
        self.assertTrue(result.get("success", False))
        self.assertEqual(result.get("operation"), "unpin_content")

if __name__ == "__main__":
    unittest.main()