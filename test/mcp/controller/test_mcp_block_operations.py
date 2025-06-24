"""
Test Block operations in the MCP server.

This test file focuses on testing the IPLD Block functionality of the MCP server,
including putting, getting, and retrieving stats for IPLD blocks.
"""

import unittest
import json
import time
from unittest.mock import patch, MagicMock

from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import

class TestMCPBlockOperations(unittest.TestCase):
    """Test Block operations in the MCP server."""

    def setUp(self):
        """Set up test environment."""
        # Create a mock IPFS kit instance
        self.mock_ipfs_kit = MagicMock()

        # Create model instance with mock IPFS kit
        self.ipfs_model = IPFSModel(ipfs_kit_instance=self.mock_ipfs_kit)

        # Create controller instance
        self.ipfs_controller = IPFSController(self.ipfs_model)

        # Reset operation stats
        self.ipfs_model.operation_stats = {
            "total_operations": 0,
            "success_count": 0,
            "failure_count": 0,
        }

    def test_block_put_success(self):
        """Test that block_put correctly handles input data."""
        # Test data to store
        test_data = b"Hello IPFS Block World!"

        # Mock the block_put method to return a CID
        expected_cid = "QmTestBlockCID"
        self.mock_ipfs_kit.block_put.return_value = expected_cid

        # Call the method
        result = self.ipfs_model.block_put(test_data)

        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "block_put")
        self.assertEqual(result["cid"], expected_cid)

        # Verify method parameters
        self.mock_ipfs_kit.block_put.assert_called_once()

    def test_block_put_with_format_parameter(self):
        """Test that block_put correctly handles the format parameter."""
        # Test data to store
        test_data = b"Hello IPFS Block World!"

        # Mock the block_put method
        expected_cid = "QmTestBlockCID"
        self.mock_ipfs_kit.block_put.return_value = expected_cid

        # Call the method with format parameter
        result = self.ipfs_model.block_put(test_data, format="raw")

        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["format"], "raw")

        # Verify method parameters
        self.mock_ipfs_kit.block_put.assert_called_once()

    def test_block_put_failure(self):
        """Test that block_put correctly handles failure."""
        # Test data to store
        test_data = b"Hello IPFS Block World!"

        # Mock the block_put method to raise an exception
        error_msg = "Failed to put block"
        self.mock_ipfs_kit.block_put.side_effect = Exception(error_msg)

        # Call the method
        result = self.ipfs_model.block_put(test_data)

        # Verify the result
        self.assertFalse(result["success"])
        self.assertEqual(result["operation"], "block_put")
        self.assertIn(error_msg, result["error"])

    def test_block_get_success(self):
        """Test that block_get correctly retrieves a block."""
        # Test CID to get
        test_cid = "QmTestBlockCID"

        # Test data to return
        expected_data = b"Hello IPFS Block World!"

        # Mock the block_get method
        self.mock_ipfs_kit.block_get.return_value = expected_data

        # Call the method
        result = self.ipfs_model.block_get(test_cid)

        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "block_get")
        self.assertEqual(result["cid"], test_cid)
        self.assertEqual(result["data"], expected_data)

        # Verify method parameters
        self.mock_ipfs_kit.block_get.assert_called_once_with(test_cid)

    def test_block_get_failure(self):
        """Test that block_get correctly handles failure."""
        # Test CID to get
        test_cid = "QmTestBlockCID"

        # Mock the block_get method to raise an exception
        error_msg = "Failed to get block"
        self.mock_ipfs_kit.block_get.side_effect = Exception(error_msg)

        # Call the method
        result = self.ipfs_model.block_get(test_cid)

        # Verify the result
        self.assertFalse(result["success"])
        self.assertEqual(result["operation"], "block_get")
        self.assertEqual(result["cid"], test_cid)
        self.assertIn(error_msg, result["error"])

    def test_block_stat_success(self):
        """Test that block_stat correctly retrieves block stats."""
        # Test CID for stats
        test_cid = "QmTestBlockCID"

        # Test stats to return
        expected_stats = {
            "Key": test_cid,
            "Size": 22
        }

        # Mock the block_stat method
        self.mock_ipfs_kit.block_stat.return_value = expected_stats

        # Call the method
        result = self.ipfs_model.block_stat(test_cid)

        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "block_stat")
        self.assertEqual(result["cid"], test_cid)
        self.assertEqual(result["size"], 22)

        # Verify method parameters
        self.mock_ipfs_kit.block_stat.assert_called_once_with(test_cid)

    def test_block_stat_with_different_response_format(self):
        """Test that block_stat correctly handles different response formats."""
        # Test CID for stats
        test_cid = "QmTestBlockCID"

        # Test stats to return in a different format
        expected_stats = {
            "cid": test_cid,
            "size": 22
        }

        # Mock the block_stat method
        self.mock_ipfs_kit.block_stat.return_value = expected_stats

        # Call the method
        result = self.ipfs_model.block_stat(test_cid)

        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "block_stat")
        self.assertEqual(result["cid"], test_cid)
        self.assertEqual(result["size"], 22)

    def test_block_stat_failure(self):
        """Test that block_stat correctly handles failure."""
        # Test CID for stats
        test_cid = "QmTestBlockCID"

        # Mock the block_stat method to raise an exception
        error_msg = "Failed to get block stats"
        self.mock_ipfs_kit.block_stat.side_effect = Exception(error_msg)

        # Call the method
        result = self.ipfs_model.block_stat(test_cid)

        # Verify the result
        self.assertFalse(result["success"])
        self.assertEqual(result["operation"], "block_stat")
        self.assertEqual(result["cid"], test_cid)
        self.assertIn(error_msg, result["error"])
