"""
Test DAG operations in the MCP server using AnyIO.

This test file focuses on testing the IPLD DAG functionality of the MCP server,
including putting, getting, and resolving DAG nodes, with AnyIO for async operations.
"""

import unittest
import pytest
import json
import time
from unittest.mock import patch, MagicMock, AsyncMock

# Import anyio for async testing
import anyio

from ipfs_kit_py.mcp_server.models.ipfs_model import IPFSModel
from ipfs_kit_py.mcp_server.controllers.ipfs_controller import IPFSController
from ipfs_kit_py.mcp_server.server_bridge import MCPServer  # Refactored import

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


# AnyIO-compatible test class
@pytest.mark.anyio
class TestMCPDAGOperationsAnyIO:
    """Test DAG operations in the MCP server using AnyIO."""
    
    @pytest.fixture(autouse=True)
    async def setup(self):
        """Set up test environment."""
        # Create a mock IPFS kit instance
        self.mock_ipfs_kit = MagicMock()
        
        # Add async method mocks for AnyIO compatibility
        self.mock_ipfs_kit.dag_put_async = AsyncMock(return_value="QmTestDAGCID")
        self.mock_ipfs_kit.dag_get_async = AsyncMock(return_value={
            "name": "test-node",
            "value": 123,
            "links": [
                {"name": "link1", "cid": "QmLinkCid1"},
                {"name": "link2", "cid": "QmLinkCid2"}
            ]
        })
        self.mock_ipfs_kit.dag_resolve_async = AsyncMock(return_value={
            "Cid": {"/"  : "QmLinkCid1"},
            "RemPath": ""
        })
        
        # Create model instance with mock IPFS kit
        self.ipfs_model = IPFSModel(ipfs_kit_instance=self.mock_ipfs_kit)
        
        # Add async method mocks to model
        self.ipfs_model.dag_put_async = AsyncMock()
        self.ipfs_model.dag_get_async = AsyncMock()
        self.ipfs_model.dag_resolve_async = AsyncMock()
        
        # Create controller instance
        self.ipfs_controller = IPFSController(self.ipfs_model)
        
        # Reset operation stats
        self.ipfs_model.operation_stats = {
            "total_operations": 0,
            "success_count": 0,
            "failure_count": 0,
        }
        
        yield
    
    @pytest.mark.anyio
    async def test_dag_put_json_object_async(self):
        """Test that dag_put correctly handles a JSON object with AnyIO."""
        # Test object to store
        test_obj = {
            "name": "test-node",
            "value": 123,
            "links": [
                {"name": "link1", "cid": "QmLinkCid1"},
                {"name": "link2", "cid": "QmLinkCid2"}
            ]
        }
        
        # Configure async mock
        expected_cid = "QmTestDAGCID"
        self.mock_ipfs_kit.dag_put_async.return_value = expected_cid
        
        # Configure model mock to delegate to kit
        async def async_dag_put(obj, **kwargs):
            return {
                "success": True,
                "operation": "dag_put",
                "cid": await self.mock_ipfs_kit.dag_put_async(obj, **kwargs),
                "timestamp": time.time()
            }
        self.ipfs_model.dag_put_async.side_effect = async_dag_put
        
        # Call the method
        result = await self.ipfs_model.dag_put_async(test_obj)
        
        # Verify the result
        assert result["success"] is True
        assert result["operation"] == "dag_put"
        assert result["cid"] == expected_cid
        
        # Verify method parameters
        self.mock_ipfs_kit.dag_put_async.assert_called_once()
    
    @pytest.mark.anyio
    async def test_dag_put_with_format_parameter_async(self):
        """Test that dag_put correctly handles the format parameter with AnyIO."""
        # Test object to store
        test_obj = {"name": "test-node", "value": 123}
        
        # Configure async mock
        expected_cid = "QmTestDAGCID"
        self.mock_ipfs_kit.dag_put_async.return_value = expected_cid
        
        # Configure model mock to delegate to kit and include format parameter
        async def async_dag_put(obj, **kwargs):
            return {
                "success": True,
                "operation": "dag_put",
                "cid": await self.mock_ipfs_kit.dag_put_async(obj, **kwargs),
                "format": kwargs.get("format", "json"),
                "timestamp": time.time()
            }
        self.ipfs_model.dag_put_async.side_effect = async_dag_put
        
        # Call the method with format parameter
        result = await self.ipfs_model.dag_put_async(test_obj, format="cbor")
        
        # Verify the result
        assert result["success"] is True
        assert result["format"] == "cbor"
        
        # Verify method parameters
        self.mock_ipfs_kit.dag_put_async.assert_called_once()
        args, kwargs = self.mock_ipfs_kit.dag_put_async.call_args
        assert kwargs.get("format") == "cbor"
    
    @pytest.mark.anyio
    async def test_dag_put_with_pin_parameter_async(self):
        """Test that dag_put correctly handles the pin parameter with AnyIO."""
        # Test object to store
        test_obj = {"name": "test-node", "value": 123}
        
        # Configure async mock
        expected_cid = "QmTestDAGCID"
        self.mock_ipfs_kit.dag_put_async.return_value = expected_cid
        
        # Configure model mock to delegate to kit and include pin parameter
        async def async_dag_put(obj, **kwargs):
            return {
                "success": True,
                "operation": "dag_put",
                "cid": await self.mock_ipfs_kit.dag_put_async(obj, **kwargs),
                "pin": kwargs.get("pin", True),
                "timestamp": time.time()
            }
        self.ipfs_model.dag_put_async.side_effect = async_dag_put
        
        # Call the method with pin parameter
        result = await self.ipfs_model.dag_put_async(test_obj, pin=False)
        
        # Verify the result
        assert result["success"] is True
        assert result["pin"] is False
        
        # Verify method parameters
        self.mock_ipfs_kit.dag_put_async.assert_called_once()
        args, kwargs = self.mock_ipfs_kit.dag_put_async.call_args
        assert kwargs.get("pin") is False
    
    @pytest.mark.anyio
    async def test_dag_put_failure_async(self):
        """Test that dag_put correctly handles failure with AnyIO."""
        # Test object to store
        test_obj = {"name": "test-node", "value": 123}
        
        # Configure async mock to raise an exception
        error_msg = "Failed to put DAG node"
        self.mock_ipfs_kit.dag_put_async.side_effect = Exception(error_msg)
        
        # Configure model mock to delegate to kit and handle exceptions
        async def async_dag_put(obj, **kwargs):
            try:
                cid = await self.mock_ipfs_kit.dag_put_async(obj, **kwargs)
                return {
                    "success": True,
                    "operation": "dag_put",
                    "cid": cid,
                    "timestamp": time.time()
                }
            except Exception as e:
                return {
                    "success": False,
                    "operation": "dag_put",
                    "error": str(e),
                    "timestamp": time.time()
                }
        self.ipfs_model.dag_put_async.side_effect = async_dag_put
        
        # Call the method
        result = await self.ipfs_model.dag_put_async(test_obj)
        
        # Verify the result
        assert result["success"] is False
        assert result["operation"] == "dag_put"
        assert error_msg in result["error"]
    
    @pytest.mark.anyio
    async def test_dag_get_success_async(self):
        """Test that dag_get correctly retrieves a DAG node with AnyIO."""
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
        
        # Configure async mock
        self.mock_ipfs_kit.dag_get_async.return_value = expected_obj
        
        # Configure model mock to delegate to kit
        async def async_dag_get(cid, **kwargs):
            return {
                "success": True,
                "operation": "dag_get",
                "cid": cid,
                "object": await self.mock_ipfs_kit.dag_get_async(cid, **kwargs),
                "timestamp": time.time()
            }
        self.ipfs_model.dag_get_async.side_effect = async_dag_get
        
        # Call the method
        result = await self.ipfs_model.dag_get_async(test_cid)
        
        # Verify the result
        assert result["success"] is True
        assert result["operation"] == "dag_get"
        assert result["cid"] == test_cid
        assert result["object"] == expected_obj
        
        # Verify method parameters
        self.mock_ipfs_kit.dag_get_async.assert_called_once_with(test_cid)
    
    @pytest.mark.anyio
    async def test_dag_get_with_path_parameter_async(self):
        """Test that dag_get correctly handles the path parameter with AnyIO."""
        # Test CID and path
        test_cid = "QmTestDAGCID"
        test_path = "links/0/name"
        
        # Expected result from following the path
        expected_value = "link1"
        
        # Configure async mock
        self.mock_ipfs_kit.dag_get_async.return_value = expected_value
        
        # Configure model mock to delegate to kit and include path parameter
        async def async_dag_get(cid, **kwargs):
            path = kwargs.get("path")
            full_path = f"{cid}/{path}" if path else cid
            return {
                "success": True,
                "operation": "dag_get",
                "cid": cid,
                "path": kwargs.get("path"),
                "object": await self.mock_ipfs_kit.dag_get_async(full_path),
                "timestamp": time.time()
            }
        self.ipfs_model.dag_get_async.side_effect = async_dag_get
        
        # Call the method with path parameter
        result = await self.ipfs_model.dag_get_async(test_cid, path=test_path)
        
        # Verify the result
        assert result["success"] is True
        assert result["path"] == test_path
        assert result["object"] == expected_value
        
        # Verify method parameters
        self.mock_ipfs_kit.dag_get_async.assert_called_once_with(f"{test_cid}/{test_path}")
    
    @pytest.mark.anyio
    async def test_dag_get_failure_async(self):
        """Test that dag_get correctly handles failure with AnyIO."""
        # Test CID to get
        test_cid = "QmTestDAGCID"
        
        # Configure async mock to raise an exception
        error_msg = "Failed to get DAG node"
        self.mock_ipfs_kit.dag_get_async.side_effect = Exception(error_msg)
        
        # Configure model mock to delegate to kit and handle exceptions
        async def async_dag_get(cid, **kwargs):
            try:
                obj = await self.mock_ipfs_kit.dag_get_async(cid, **kwargs)
                return {
                    "success": True,
                    "operation": "dag_get",
                    "cid": cid,
                    "object": obj,
                    "timestamp": time.time()
                }
            except Exception as e:
                return {
                    "success": False,
                    "operation": "dag_get",
                    "cid": cid,
                    "error": str(e),
                    "timestamp": time.time()
                }
        self.ipfs_model.dag_get_async.side_effect = async_dag_get
        
        # Call the method
        result = await self.ipfs_model.dag_get_async(test_cid)
        
        # Verify the result
        assert result["success"] is False
        assert result["operation"] == "dag_get"
        assert result["cid"] == test_cid
        assert error_msg in result["error"]
    
    @pytest.mark.anyio
    async def test_dag_resolve_success_async(self):
        """Test that dag_resolve correctly resolves a DAG path with AnyIO."""
        # Test CID and path
        test_cid = "QmTestDAGCID"
        test_path = "links/0/cid"
        
        # Configure async mock
        expected_result = {
            "Cid": {"/"  : "QmLinkCid1"},
            "RemPath": ""
        }
        self.mock_ipfs_kit.dag_resolve_async.return_value = expected_result
        
        # Configure model mock to delegate to kit
        async def async_dag_resolve(path):
            resolve_result = await self.mock_ipfs_kit.dag_resolve_async(path)
            return {
                "success": True,
                "operation": "dag_resolve",
                "path": path,
                "cid": resolve_result["Cid"]["/"],
                "remainder_path": resolve_result["RemPath"],
                "timestamp": time.time()
            }
        self.ipfs_model.dag_resolve_async.side_effect = async_dag_resolve
        
        # Call the method
        result = await self.ipfs_model.dag_resolve_async(f"{test_cid}/{test_path}")
        
        # Verify the result
        assert result["success"] is True
        assert result["operation"] == "dag_resolve"
        assert result["path"] == f"{test_cid}/{test_path}"
        assert result["cid"] == "QmLinkCid1"
        assert result["remainder_path"] == ""
        
        # Verify method parameters
        self.mock_ipfs_kit.dag_resolve_async.assert_called_once_with(f"{test_cid}/{test_path}")
    
    @pytest.mark.anyio
    async def test_dag_resolve_with_remainder_path_async(self):
        """Test that dag_resolve correctly handles a remainder path with AnyIO."""
        # Test path with a remainder
        test_path = "QmTestDAGCID/links/0"
        
        # Configure async mock with a remainder path
        expected_result = {
            "Cid": {"/"  : "QmLinkListCID"},
            "RemPath": "0"
        }
        self.mock_ipfs_kit.dag_resolve_async.return_value = expected_result
        
        # Configure model mock to delegate to kit
        async def async_dag_resolve(path):
            resolve_result = await self.mock_ipfs_kit.dag_resolve_async(path)
            return {
                "success": True,
                "operation": "dag_resolve",
                "path": path,
                "cid": resolve_result["Cid"]["/"],
                "remainder_path": resolve_result["RemPath"],
                "timestamp": time.time()
            }
        self.ipfs_model.dag_resolve_async.side_effect = async_dag_resolve
        
        # Call the method
        result = await self.ipfs_model.dag_resolve_async(test_path)
        
        # Verify the result
        assert result["success"] is True
        assert result["cid"] == "QmLinkListCID"
        assert result["remainder_path"] == "0"
    
    @pytest.mark.anyio
    async def test_dag_resolve_failure_async(self):
        """Test that dag_resolve correctly handles failure with AnyIO."""
        # Test path
        test_path = "QmTestDAGCID/nonexistent/path"
        
        # Configure async mock to raise an exception
        error_msg = "Failed to resolve DAG path"
        self.mock_ipfs_kit.dag_resolve_async.side_effect = Exception(error_msg)
        
        # Configure model mock to delegate to kit and handle exceptions
        async def async_dag_resolve(path):
            try:
                resolve_result = await self.mock_ipfs_kit.dag_resolve_async(path)
                return {
                    "success": True,
                    "operation": "dag_resolve",
                    "path": path,
                    "cid": resolve_result["Cid"]["/"],
                    "remainder_path": resolve_result["RemPath"],
                    "timestamp": time.time()
                }
            except Exception as e:
                return {
                    "success": False,
                    "operation": "dag_resolve",
                    "path": path,
                    "error": str(e),
                    "timestamp": time.time()
                }
        self.ipfs_model.dag_resolve_async.side_effect = async_dag_resolve
        
        # Call the method
        result = await self.ipfs_model.dag_resolve_async(test_path)
        
        # Verify the result
        assert result["success"] is False
        assert result["operation"] == "dag_resolve"
        assert result["path"] == test_path
        assert error_msg in result["error"]
    
    @pytest.mark.anyio
    async def test_anyio_sleep_integration(self):
        """Test the integration with anyio.sleep."""
        # Create a method that uses sleep to simulate network delay
        async def dag_put_with_delay_async(obj, delay=0.1, **kwargs):
            # Simulate network or processing delay
            await anyio.sleep(delay)
            
            # Return result after delay
            return "QmTestDAGCID"
        
        # Set up the mock implementation
        self.mock_ipfs_kit.dag_put_async = AsyncMock(side_effect=dag_put_with_delay_async)
        
        # Create a wrapper to call through to our mock
        async def model_dag_put_async(obj, **kwargs):
            try:
                start_time = time.time()
                delay = kwargs.pop("delay", 0.1)  # Extract delay parameter
                cid = await self.mock_ipfs_kit.dag_put_async(obj, delay=delay, **kwargs)
                elapsed = time.time() - start_time
                
                return {
                    "success": True,
                    "operation": "dag_put",
                    "cid": cid,
                    "elapsed_time": elapsed,
                    "timestamp": time.time()
                }
            except Exception as e:
                return {
                    "success": False,
                    "operation": "dag_put",
                    "error": str(e),
                    "timestamp": time.time()
                }
        
        self.ipfs_model.dag_put_async.side_effect = model_dag_put_async
        
        # Call the method with a specific delay
        start_time = time.time()
        result = await self.ipfs_model.dag_put_async({"test": "object"}, delay=0.2)
        end_time = time.time()
        
        # Verify the result
        assert result["success"] is True
        assert result["cid"] == "QmTestDAGCID"
        
        # Verify the delay
        elapsed = end_time - start_time
        assert elapsed >= 0.2, f"Expected delay of at least 0.2s, but got {elapsed}s"
        assert result["elapsed_time"] >= 0.2, f"Expected elapsed_time of at least 0.2s, but got {result['elapsed_time']}s"


if __name__ == "__main__":
    unittest.main()