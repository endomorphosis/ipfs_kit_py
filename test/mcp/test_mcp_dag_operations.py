"""
Test DAG operations in the MCP server.

This test file focuses on testing the IPLD DAG functionality of the MCP server,
including putting, getting, and resolving DAG nodes.
"""

import unittest
import json
import time
from unittest.mock import patch, MagicMock

from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
from ipfs_kit_py.mcp.server import MCPServer

class TestMCPDAGOperations(unittest.TestCase):
    """Test DAG operations in the MCP server."""
    
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
    
    def test_dag_put_json_object(self):
        """Test that dag_put correctly handles a JSON object."""
        # Test object to store
        test_obj = {
            "name": "test-node",
            "value": 123,
            "links": [
                {"name": "link1", "cid": "QmLinkCid1"},
                {"name": "link2", "cid": "QmLinkCid2"}
            ]
        }
        
        # Mock the dag_put method to return a CID
        expected_cid = "QmTestDAGCID"
        self.mock_ipfs_kit.dag_put.return_value = expected_cid
        
        # Call the method
        result = self.ipfs_model.dag_put(test_obj)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "dag_put")
        self.assertEqual(result["cid"], expected_cid)
        
        # Verify method parameters
        self.mock_ipfs_kit.dag_put.assert_called_once()
    
    def test_dag_put_with_format_parameter(self):
        """Test that dag_put correctly handles the format parameter."""
        # Test object to store
        test_obj = {"name": "test-node", "value": 123}
        
        # Mock the dag_put method
        expected_cid = "QmTestDAGCID"
        self.mock_ipfs_kit.dag_put.return_value = expected_cid
        
        # Call the method with format parameter
        result = self.ipfs_model.dag_put(test_obj, format="cbor")
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["format"], "cbor")
        
        # Verify method parameters
        self.mock_ipfs_kit.dag_put.assert_called_once()
        args, kwargs = self.mock_ipfs_kit.dag_put.call_args
        self.assertEqual(kwargs.get("format"), "cbor")
    
    def test_dag_put_with_pin_parameter(self):
        """Test that dag_put correctly handles the pin parameter."""
        # Test object to store
        test_obj = {"name": "test-node", "value": 123}
        
        # Mock the dag_put method
        expected_cid = "QmTestDAGCID"
        self.mock_ipfs_kit.dag_put.return_value = expected_cid
        
        # Call the method with pin parameter
        result = self.ipfs_model.dag_put(test_obj, pin=False)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["pin"], False)
        
        # Verify method parameters
        self.mock_ipfs_kit.dag_put.assert_called_once()
        args, kwargs = self.mock_ipfs_kit.dag_put.call_args
        self.assertEqual(kwargs.get("pin"), False)
    
    def test_dag_put_failure(self):
        """Test that dag_put correctly handles failure."""
        # Test object to store
        test_obj = {"name": "test-node", "value": 123}
        
        # Mock the dag_put method to raise an exception
        error_msg = "Failed to put DAG node"
        self.mock_ipfs_kit.dag_put.side_effect = Exception(error_msg)
        
        # Call the method
        result = self.ipfs_model.dag_put(test_obj)
        
        # Verify the result
        self.assertFalse(result["success"])
        self.assertEqual(result["operation"], "dag_put")
        self.assertIn(error_msg, result["error"])
    
    def test_dag_get_success(self):
        """Test that dag_get correctly retrieves a DAG node."""
        # Test CID to get
        test_cid = "QmTestDAGCID"
        
        # Test object to return
        expected_obj = {
            "name": "test-node",
            "value": 123,
            "links": [
                {"name": "link1", "cid": "QmLinkCid1"},
                {"name": "link2", "cid": "QmLinkCid2"}
            ]
        }
        
        # Mock the dag_get method
        self.mock_ipfs_kit.dag_get.return_value = expected_obj
        
        # Call the method
        result = self.ipfs_model.dag_get(test_cid)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "dag_get")
        self.assertEqual(result["cid"], test_cid)
        self.assertEqual(result["object"], expected_obj)
        
        # Verify method parameters
        self.mock_ipfs_kit.dag_get.assert_called_once_with(test_cid)
    
    def test_dag_get_with_path_parameter(self):
        """Test that dag_get correctly handles the path parameter."""
        # Test CID and path
        test_cid = "QmTestDAGCID"
        test_path = "links/0/name"
        
        # Expected result from following the path
        expected_value = "link1"
        
        # Mock the dag_get method
        self.mock_ipfs_kit.dag_get.return_value = expected_value
        
        # Call the method with path parameter
        result = self.ipfs_model.dag_get(test_cid, path=test_path)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["path"], test_path)
        self.assertEqual(result["object"], expected_value)
        
        # Verify method parameters
        self.mock_ipfs_kit.dag_get.assert_called_once()
        args, kwargs = self.mock_ipfs_kit.dag_get.call_args
        self.assertEqual(args[0], f"{test_cid}/{test_path}")
    
    def test_dag_get_failure(self):
        """Test that dag_get correctly handles failure."""
        # Test CID to get
        test_cid = "QmTestDAGCID"
        
        # Mock the dag_get method to raise an exception
        error_msg = "Failed to get DAG node"
        self.mock_ipfs_kit.dag_get.side_effect = Exception(error_msg)
        
        # Call the method
        result = self.ipfs_model.dag_get(test_cid)
        
        # Verify the result
        self.assertFalse(result["success"])
        self.assertEqual(result["operation"], "dag_get")
        self.assertEqual(result["cid"], test_cid)
        self.assertIn(error_msg, result["error"])
    
    def test_dag_resolve_success(self):
        """Test that dag_resolve correctly resolves a DAG path."""
        # Test CID and path
        test_cid = "QmTestDAGCID"
        test_path = "links/0/cid"
        
        # Mock the dag_resolve method
        expected_result = {
            "Cid": {"/"  : "QmLinkCid1"},
            "RemPath": ""
        }
        self.mock_ipfs_kit.dag_resolve.return_value = expected_result
        
        # Call the method
        result = self.ipfs_model.dag_resolve(f"{test_cid}/{test_path}")
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "dag_resolve")
        self.assertEqual(result["path"], f"{test_cid}/{test_path}")
        self.assertEqual(result["cid"], "QmLinkCid1")
        self.assertEqual(result["remainder_path"], "")
        
        # Verify method parameters
        self.mock_ipfs_kit.dag_resolve.assert_called_once_with(f"{test_cid}/{test_path}")
    
    def test_dag_resolve_with_remainder_path(self):
        """Test that dag_resolve correctly handles a remainder path."""
        # Test path with a remainder
        test_path = "QmTestDAGCID/links/0"
        
        # Mock the dag_resolve method with a remainder path
        expected_result = {
            "Cid": {"/"  : "QmLinkListCID"},
            "RemPath": "0"
        }
        self.mock_ipfs_kit.dag_resolve.return_value = expected_result
        
        # Call the method
        result = self.ipfs_model.dag_resolve(test_path)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["cid"], "QmLinkListCID")
        self.assertEqual(result["remainder_path"], "0")
    
    def test_dag_resolve_failure(self):
        """Test that dag_resolve correctly handles failure."""
        # Test path
        test_path = "QmTestDAGCID/nonexistent/path"
        
        # Mock the dag_resolve method to raise an exception
        error_msg = "Failed to resolve DAG path"
        self.mock_ipfs_kit.dag_resolve.side_effect = Exception(error_msg)
        
        # Call the method
        result = self.ipfs_model.dag_resolve(test_path)
        
        # Verify the result
        self.assertFalse(result["success"])
        self.assertEqual(result["operation"], "dag_resolve")
        self.assertEqual(result["path"], test_path)
        self.assertIn(error_msg, result["error"])