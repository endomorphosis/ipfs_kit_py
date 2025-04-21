"""
Test IPNS operations in the MCP server.

This test file focuses on testing the IPNS functionality of the MCP server,
including publishing and resolving IPNS names.
"""

import unittest
import json
import time
from unittest.mock import patch, MagicMock

from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import

class TestMCPIPNSOperations(unittest.TestCase):
    """Test IPNS operations in the MCP server."""
    
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
    
    def test_ipfs_name_publish_with_string_response(self):
        """Test that ipfs_name_publish correctly handles string response."""
        # Mock the run_ipfs_command method to return a string response
        cmd_result = {
            "success": True,
            "stdout": "Published to k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8: /ipfs/QmTestCID"
        }
        self.mock_ipfs_kit.run_ipfs_command.return_value = cmd_result
        
        # Call the method
        result = self.ipfs_model.ipfs_name_publish("QmTestCID")
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "ipfs_name_publish")
        self.assertEqual(result["cid"], "QmTestCID")
        self.assertEqual(result["name"], "k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8")
        self.assertEqual(result["value"], "/ipfs/QmTestCID")
        
        # Verify command parameters
        self.mock_ipfs_kit.run_ipfs_command.assert_called_once()
        args, _ = self.mock_ipfs_kit.run_ipfs_command.call_args
        cmd = args[0]
        self.assertEqual(cmd[0:3], ["ipfs", "name", "publish"])
        self.assertEqual(cmd[-1], "/ipfs/QmTestCID")
    
    def test_ipfs_name_publish_with_json_response(self):
        """Test that ipfs_name_publish correctly handles JSON response."""
        # Mock the run_ipfs_command method to return a JSON response
        json_str = json.dumps({
            "Name": "k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8",
            "Value": "/ipfs/QmTestCID"
        })
        cmd_result = {
            "success": True,
            "stdout": json_str.encode('utf-8')
        }
        self.mock_ipfs_kit.run_ipfs_command.return_value = cmd_result
        
        # Call the method
        result = self.ipfs_model.ipfs_name_publish("QmTestCID")
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "ipfs_name_publish")
        self.assertEqual(result["cid"], "QmTestCID")
        self.assertEqual(result["name"], "k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8")
        self.assertEqual(result["value"], "/ipfs/QmTestCID")
    
    def test_ipfs_name_publish_with_key(self):
        """Test that ipfs_name_publish correctly handles the key parameter."""
        # Mock the run_ipfs_command method
        cmd_result = {
            "success": True,
            "stdout": "Published to k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8: /ipfs/QmTestCID"
        }
        self.mock_ipfs_kit.run_ipfs_command.return_value = cmd_result
        
        # Call the method with a key
        result = self.ipfs_model.ipfs_name_publish("QmTestCID", key="test-key")
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["key"], "test-key")
        
        # Verify command parameters
        self.mock_ipfs_kit.run_ipfs_command.assert_called_once()
        args, _ = self.mock_ipfs_kit.run_ipfs_command.call_args
        cmd = args[0]
        self.assertIn("--key", cmd)
        key_index = cmd.index("--key")
        self.assertEqual(cmd[key_index + 1], "test-key")
    
    def test_ipfs_name_publish_failure(self):
        """Test that ipfs_name_publish correctly handles failure."""
        # Mock the run_ipfs_command method to return a failure
        cmd_result = {
            "success": False,
            "stderr": b"Error: failed to publish entry: publisher not online"
        }
        self.mock_ipfs_kit.run_ipfs_command.return_value = cmd_result
        
        # Call the method
        result = self.ipfs_model.ipfs_name_publish("QmTestCID")
        
        # Verify the result
        self.assertFalse(result["success"])
        self.assertEqual(result["operation"], "ipfs_name_publish")
        self.assertEqual(result["cid"], "QmTestCID")
        self.assertEqual(result["error_type"], "command_error")
        self.assertIn("publisher not online", result["error"])
    
    def test_ipfs_name_resolve_with_string_response(self):
        """Test that ipfs_name_resolve correctly handles string response."""
        # Mock the run_ipfs_command method to return a string response
        cmd_result = {
            "success": True,
            "stdout": b"/ipfs/QmResolvedTestCID"
        }
        self.mock_ipfs_kit.run_ipfs_command.return_value = cmd_result
        
        # Call the method
        result = self.ipfs_model.ipfs_name_resolve("test-name")
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "ipfs_name_resolve")
        self.assertEqual(result["name"], "test-name")
        self.assertEqual(result["path"], "/ipfs/QmResolvedTestCID")
        
        # Verify command parameters
        self.mock_ipfs_kit.run_ipfs_command.assert_called_once()
        args, _ = self.mock_ipfs_kit.run_ipfs_command.call_args
        cmd = args[0]
        self.assertEqual(cmd[0:3], ["ipfs", "name", "resolve"])
        self.assertTrue(cmd[-1].endswith("test-name"))
    
    def test_ipfs_name_resolve_with_ipns_prefix_handling(self):
        """Test that ipfs_name_resolve correctly handles IPNS prefix."""
        # Mock the run_ipfs_command method
        cmd_result = {
            "success": True,
            "stdout": b"/ipfs/QmResolvedTestCID"
        }
        self.mock_ipfs_kit.run_ipfs_command.return_value = cmd_result
        
        # Call the method with already prefixed name
        result = self.ipfs_model.ipfs_name_resolve("/ipns/test-name")
        
        # Verify command parameters - shouldn't add another /ipns/ prefix
        self.mock_ipfs_kit.run_ipfs_command.assert_called_once()
        args, _ = self.mock_ipfs_kit.run_ipfs_command.call_args
        cmd = args[0]
        self.assertEqual(cmd[-1], "/ipns/test-name")
        self.assertEqual(result["name"], "/ipns/test-name")
    
    def test_ipfs_name_resolve_with_recursive_parameter(self):
        """Test that ipfs_name_resolve correctly handles the recursive parameter."""
        # Mock the run_ipfs_command method
        cmd_result = {
            "success": True,
            "stdout": b"/ipfs/QmResolvedTestCID"
        }
        self.mock_ipfs_kit.run_ipfs_command.return_value = cmd_result
        
        # Call the method with recursive=False
        result = self.ipfs_model.ipfs_name_resolve("test-name", recursive=False)
        
        # Verify command parameters
        self.mock_ipfs_kit.run_ipfs_command.assert_called_once()
        args, _ = self.mock_ipfs_kit.run_ipfs_command.call_args
        cmd = args[0]
        self.assertIn("--recursive=false", cmd)
    
    def test_ipfs_name_resolve_with_nocache_parameter(self):
        """Test that ipfs_name_resolve correctly handles the nocache parameter."""
        # Mock the run_ipfs_command method
        cmd_result = {
            "success": True,
            "stdout": b"/ipfs/QmResolvedTestCID"
        }
        self.mock_ipfs_kit.run_ipfs_command.return_value = cmd_result
        
        # Call the method with nocache=True
        result = self.ipfs_model.ipfs_name_resolve("test-name", nocache=True)
        
        # Verify command parameters
        self.mock_ipfs_kit.run_ipfs_command.assert_called_once()
        args, _ = self.mock_ipfs_kit.run_ipfs_command.call_args
        cmd = args[0]
        self.assertIn("--nocache", cmd)
    
    def test_ipfs_name_resolve_failure(self):
        """Test that ipfs_name_resolve correctly handles failure."""
        # Mock the run_ipfs_command method to return a failure
        cmd_result = {
            "success": False,
            "stderr": b"Error: could not resolve name"
        }
        self.mock_ipfs_kit.run_ipfs_command.return_value = cmd_result
        
        # Call the method
        result = self.ipfs_model.ipfs_name_resolve("test-name")
        
        # Verify the result
        self.assertFalse(result["success"])
        self.assertEqual(result["operation"], "ipfs_name_resolve")
        self.assertEqual(result["name"], "test-name")
        self.assertEqual(result["error_type"], "command_error")
        self.assertIn("could not resolve name", result["error"])
    
    def test_ipfs_name_resolve_with_timeout_parameter(self):
        """Test that ipfs_name_resolve correctly handles the timeout parameter."""
        # Mock the run_ipfs_command method
        cmd_result = {
            "success": True,
            "stdout": b"/ipfs/QmResolvedTestCID"
        }
        self.mock_ipfs_kit.run_ipfs_command.return_value = cmd_result
        
        # Call the method with timeout=30
        result = self.ipfs_model.ipfs_name_resolve("test-name", timeout=30)
        
        # Verify command parameters
        self.mock_ipfs_kit.run_ipfs_command.assert_called_once()
        args, _ = self.mock_ipfs_kit.run_ipfs_command.call_args
        cmd = args[0]
        self.assertIn("--timeout", cmd)
        timeout_index = cmd.index("--timeout")
        self.assertEqual(cmd[timeout_index + 1], "30s")
    
    def test_ipfs_controller_name_publish_endpoint(self):
        """Test that the IPFSController correctly handles name publish requests."""
        # Create a mock FastAPI Request object
        mock_request = MagicMock()
        
        # Mock the model's ipfs_name_publish method
        model_result = {
            "success": True,
            "operation": "ipfs_name_publish",
            "cid": "QmTestCID",
            "name": "k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8",
            "value": "/ipfs/QmTestCID"
        }
        self.ipfs_model.ipfs_name_publish = MagicMock(return_value=model_result)
        
        # Call the controller method with a request body
        result = self.ipfs_controller.ipfs_name_publish(mock_request, "QmTestCID")
        
        # Verify the result
        self.assertEqual(result, model_result)
        self.ipfs_model.ipfs_name_publish.assert_called_once_with("QmTestCID", key=None, lifetime=None, ttl=None)
    
    def test_ipfs_controller_name_resolve_endpoint(self):
        """Test that the IPFSController correctly handles name resolve requests."""
        # Create a mock FastAPI Request object
        mock_request = MagicMock()
        
        # Mock the model's ipfs_name_resolve method
        model_result = {
            "success": True,
            "operation": "ipfs_name_resolve",
            "name": "test-name",
            "path": "/ipfs/QmResolvedTestCID"
        }
        self.ipfs_model.ipfs_name_resolve = MagicMock(return_value=model_result)
        
        # Call the controller method
        result = self.ipfs_controller.ipfs_name_resolve(mock_request, "test-name")
        
        # Verify the result
        self.assertEqual(result, model_result)
        self.ipfs_model.ipfs_name_resolve.assert_called_once_with("test-name", recursive=True, nocache=False, timeout=None)
    
    def test_ipfs_key_gen_functionality(self):
        """Test the IPFS key generation functionality."""
        # Mock the run_ipfs_command method
        cmd_result = {
            "success": True,
            "stdout": b'{"Name":"test-key","Id":"k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8"}'
        }
        self.mock_ipfs_kit.run_ipfs_command.return_value = cmd_result
        
        # Call the method
        result = self.ipfs_model.ipfs_key_gen("test-key")
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "ipfs_key_gen")
        self.assertEqual(result["key_name"], "test-key")
        self.assertEqual(result["key_id"], "k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8")
        
        # Verify command parameters
        self.mock_ipfs_kit.run_ipfs_command.assert_called_once()
        args, _ = self.mock_ipfs_kit.run_ipfs_command.call_args
        cmd = args[0]
        self.assertEqual(cmd[0:3], ["ipfs", "key", "gen"])
        self.assertEqual(cmd[-1], "test-key")
    
    def test_ipfs_key_gen_with_type_and_size(self):
        """Test that ipfs_key_gen correctly handles type and size parameters."""
        # Mock the run_ipfs_command method
        cmd_result = {
            "success": True,
            "stdout": b'{"Name":"test-key","Id":"k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8"}'
        }
        self.mock_ipfs_kit.run_ipfs_command.return_value = cmd_result
        
        # Call the method with type and size
        result = self.ipfs_model.ipfs_key_gen("test-key", key_type="rsa", size=2048)
        
        # Verify command parameters
        self.mock_ipfs_kit.run_ipfs_command.assert_called_once()
        args, _ = self.mock_ipfs_kit.run_ipfs_command.call_args
        cmd = args[0]
        self.assertIn("--type=rsa", cmd)
        self.assertIn("--size=2048", cmd)
    
    def test_ipfs_key_list_functionality(self):
        """Test the IPFS key listing functionality."""
        # Mock the run_ipfs_command method
        cmd_result = {
            "success": True,
            "stdout": b'[{"Name":"self","Id":"12D3KooWR5Vc5wRTuW8HZoZWTd5hRJ2pS6SUy8jMtzs3Ji4Dpk9f"},{"Name":"test-key","Id":"k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8"}]'
        }
        self.mock_ipfs_kit.run_ipfs_command.return_value = cmd_result
        
        # Call the method
        result = self.ipfs_model.ipfs_key_list()
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "ipfs_key_list")
        self.assertEqual(len(result["keys"]), 2)
        self.assertEqual(result["keys"][0]["Name"], "self")
        self.assertEqual(result["keys"][1]["Name"], "test-key")
        
        # Verify command parameters
        self.mock_ipfs_kit.run_ipfs_command.assert_called_once()
        args, _ = self.mock_ipfs_kit.run_ipfs_command.call_args
        cmd = args[0]
        self.assertEqual(cmd[0:3], ["ipfs", "key", "list"])
        self.assertIn("--format=json", cmd)
    
    def test_ipfs_controller_key_gen_endpoint(self):
        """Test that the IPFSController correctly handles key generation requests."""
        # Create a mock FastAPI Request object
        mock_request = MagicMock()
        
        # Mock the model's ipfs_key_gen method
        model_result = {
            "success": True,
            "operation": "ipfs_key_gen",
            "key_name": "test-key",
            "key_id": "k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8"
        }
        self.ipfs_model.ipfs_key_gen = MagicMock(return_value=model_result)
        
        # Call the controller method
        result = self.ipfs_controller.ipfs_key_gen(mock_request, "test-key")
        
        # Verify the result
        self.assertEqual(result, model_result)
        self.ipfs_model.ipfs_key_gen.assert_called_once_with("test-key", key_type=None, size=None)
    
    def test_ipfs_controller_key_list_endpoint(self):
        """Test that the IPFSController correctly handles key listing requests."""
        # Create a mock FastAPI Request object
        mock_request = MagicMock()
        
        # Mock the model's ipfs_key_list method
        model_result = {
            "success": True,
            "operation": "ipfs_key_list",
            "keys": [
                {"Name": "self", "Id": "12D3KooWR5Vc5wRTuW8HZoZWTd5hRJ2pS6SUy8jMtzs3Ji4Dpk9f"},
                {"Name": "test-key", "Id": "k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8"}
            ]
        }
        self.ipfs_model.ipfs_key_list = MagicMock(return_value=model_result)
        
        # Call the controller method
        result = self.ipfs_controller.ipfs_key_list(mock_request)
        
        # Verify the result
        self.assertEqual(result, model_result)
        self.ipfs_model.ipfs_key_list.assert_called_once()
    
    def test_integration_mcp_server_ipns_endpoints(self):
        """Test the integration of IPNS endpoints in the MCP server."""
        # Create a mock server with required components
        mock_server = MagicMock()
        mock_server.cache_manager = MagicMock()
        mock_server.ipfs_kit = self.mock_ipfs_kit
        mock_server.models = {"ipfs": self.ipfs_model}
        mock_server.controllers = {"ipfs": self.ipfs_controller}
        
        # Mock the router and app for registration
        mock_router = MagicMock()
        mock_app = MagicMock()
        mock_app.include_router.return_value = None
        
        # Get the router from the server
        self.ipfs_controller.register_routes(mock_router)
        
        # Verify the routes are registered - make sure IPNS endpoints are included
        calls = mock_router.add_api_route.call_args_list
        
        # Extract endpoint paths from calls
        endpoints = [call[0][0] for call in calls]
        
        # Verify IPNS endpoints are registered
        self.assertIn("/name/publish", endpoints)
        self.assertIn("/name/resolve", endpoints)
        self.assertIn("/key/gen", endpoints)
        self.assertIn("/key/list", endpoints)


if __name__ == "__main__":
    unittest.main()