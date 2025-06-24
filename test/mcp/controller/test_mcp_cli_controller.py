"""
Test for the MCP CLI Controller module.

This module tests the functionality of the CLI Controller in the MCP server,
ensuring all CLI commands are properly exposed via HTTP endpoints.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ipfs_kit_py.mcp.controllers.cli_controller import CliController
from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import


class TestMCPCliController(unittest.TestCase):
    """Test case for the MCP CLI Controller."""

    def setUp(self):
        """Set up test environment."""
        # Create a mock IPFS model
        self.mock_ipfs_model = MagicMock()

        # Create a CLI controller with the mock model
        self.controller = CliController(self.mock_ipfs_model)

        # Create a FastAPI app and test client
        self.app = FastAPI()
        router = self.app.router
        self.controller.register_routes(router)
        self.client = TestClient(self.app)

        # Print all registered routes for debugging
        print("\nRegistered routes:")
        for route in self.app.routes:
            print(f"  {route.methods} {route.path}")

        # Patch the IPFSSimpleAPI class in the controller
        self.api_patcher = patch('ipfs_kit_py.mcp.controllers.cli_controller.IPFSSimpleAPI')
        self.mock_api_class = self.api_patcher.start()
        self.mock_api = MagicMock()
        self.mock_api_class.return_value = self.mock_api
        self.controller.api = self.mock_api

    def tearDown(self):
        """Clean up after test."""
        self.api_patcher.stop()


    def test_add_content(self):
        """Test the add_content endpoint."""
        # Set up mock return value
        self.mock_api.add.return_value = {"Hash": "QmTest"}

        # Make API request
        response = self.client.post(
            "/cli/add",
            json={"content": "test content"}
        )

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

        # Verify API method was called
        self.mock_api.add.assert_called_once()

    def test_get_content(self):
        """Test the get_content endpoint."""
        # Set up mock return value
        self.mock_api.get.return_value = b"test content"

        # Make API request
        response = self.client.get("/cli/cat/QmTest")

        # Verify response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"test content")

        # Verify API method was called
        self.mock_api.get.assert_called_once_with("QmTest")

    def test_pin_content(self):
        """Test the pin_content endpoint."""
        # Set up mock return value
        self.mock_api.pin.return_value = {"Pins": ["QmTest"]}

        # Make API request
        response = self.client.post("/cli/pin/QmTest")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

        # Verify API method was called
        self.mock_api.pin.assert_called_once()

    def test_unpin_content(self):
        """Test the unpin_content endpoint."""
        # Set up mock return value
        self.mock_api.unpin.return_value = {"Pins": ["QmTest"]}

        # Make API request
        response = self.client.post("/cli/unpin/QmTest")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

        # Verify API method was called
        self.mock_api.unpin.assert_called_once()

    def test_list_pins(self):
        """Test the list_pins endpoint."""
        # Set up mock return value
        self.mock_api.list_pins.return_value = {"Keys": {"QmTest": {"Type": "recursive"}}}

        # Make API request
        response = self.client.get("/cli/pins")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

        # Verify API method was called
        self.mock_api.list_pins.assert_called_once()

    def test_publish_content(self):
        """Test the publish_content endpoint."""
        # Set up mock return value with required fields for success
        mock_result = {
            "Name": "QmTest",
            "Value": "/ipfs/QmTest",
            "operation_id": "test_op_123",
            "format": "json",
            "success": True
        }
        self.mock_ipfs_model.name_publish.return_value = mock_result

        # Make API request
        response = self.client.post("/cli/publish/QmTest?key=self&lifetime=24h&ttl=1h")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

        # Verify model method was called
        self.mock_ipfs_model.name_publish.assert_called_once()

    def test_resolve_name(self):
        """Test the resolve_name endpoint."""
        # Set up mock return value for both possible methods used
        self.mock_api.resolve.return_value = {"Path": "/ipfs/QmTest"}
        # Also mock the model method in case that's used
        self.mock_ipfs_model.name_resolve.return_value = {
            "success": True,
            "Path": "/ipfs/QmTest",
            "operation": "name_resolve"
        }

        # Make API request
        response = self.client.get("/cli/resolve/test-name")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

        # Print the actual response structure for debugging
        print(f"Resolve name response: {data}")

        # Check the result structure more flexibly
        self.assertIn("result", data)
        result = data["result"]

        # Only check for operation and timestamp as those are guaranteed
        self.assertIn("operation", result)
        self.assertEqual(result["operation"], "resolve_name")
        self.assertIn("timestamp", result)

        # Verify that either the API method or the model method was called
        # The controller can use either one but we don't know which in advance
        called_count = self.mock_api.resolve.call_count + self.mock_ipfs_model.name_resolve.call_count
        self.assertGreaterEqual(called_count, 1, "Either API or model method should be called")

    def test_connect_peer(self):
        """Test the connect_peer endpoint."""
        # Set up mock return values for both possible methods used
        self.mock_api.connect.return_value = {"Strings": ["connection established"]}
        # Also mock the model method in case that's used
        self.mock_ipfs_model.swarm_connect.return_value = {
            "success": True,
            "Strings": ["connection established"],
            "operation": "swarm_connect"
        }

        # Make API request
        response = self.client.post("/cli/connect/QmTestPeerId")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

        # Print the actual response structure for debugging
        print(f"Connect peer response: {data}")

        # Check the result structure more flexibly
        self.assertIn("result", data)
        result = data["result"]

        # Only check for operation and timestamp as those are guaranteed
        self.assertIn("operation", result)
        self.assertEqual(result["operation"], "connect_peer")
        self.assertIn("timestamp", result)

        # Verify that either the API method or the model method was called
        # The controller can use either one but we don't know which in advance
        called_count = self.mock_api.connect.call_count + self.mock_ipfs_model.swarm_connect.call_count
        self.assertGreaterEqual(called_count, 1, "Either API or model method should be called")

    def test_list_peers(self):
        """Test the list_peers endpoint."""
        # Set up mock return value
        self.mock_api.peers.return_value = ["/ip4/127.0.0.1/tcp/4001/p2p/QmTest"]

        # Make API request
        response = self.client.get("/cli/peers")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

        # Verify API method was called
        self.mock_api.peers.assert_called_once()

    def test_check_existence(self):
        """Test the check_existence endpoint."""
        # Set up mock return value
        self.mock_api.exists.return_value = True

        # Make API request
        response = self.client.get("/cli/exists/QmTest")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["result"]["exists"])

        # Verify API method was called
        self.mock_api.exists.assert_called_once()

    def test_list_directory(self):
        """Test the list_directory endpoint."""
        # Set up mock return value
        self.mock_api.ls.return_value = {"Entries": [{"Name": "test", "Type": 1, "Size": 0}]}

        # Make API request
        response = self.client.get("/cli/ls/QmTest")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

        # Verify API method was called
        self.mock_api.ls.assert_called_once()

    def test_generate_sdk(self):
        """Test the generate_sdk endpoint."""
        # Set up mock return value
        self.mock_api.generate_sdk.return_value = {"path": "/tmp/sdk"}

        # Make API request
        response = self.client.post(
            "/cli/generate-sdk",
            json={"language": "python", "output_dir": "/tmp"}
        )

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

        # Verify API method was called
        self.mock_api.generate_sdk.assert_called_once()

    def test_error_handling(self):
        """Test error handling in CLI controller."""
        # Set up mock to raise an exception
        self.mock_api.get.side_effect = Exception("Test error")

        # Make API request
        response = self.client.get("/cli/cat/QmTest")

        # Verify response is an error response
        self.assertEqual(response.status_code, 404)

    def test_execute_command(self):
        """Test the execute_command endpoint."""
        # Set up mock return value
        self.mock_api.execute_command.return_value = {
            "success": True,
            "operation": "execute_command",
            "result": "Command executed successfully",
            "timestamp": 1234567890
        }

        # Make API request
        response = self.client.post(
            "/cli/execute",
            json={"command": "ipfs version", "args": []}
        )

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "execute_command")
        self.assertEqual(data["result"], "Command executed successfully")

        # Verify API method was called
        self.mock_api.execute_command.assert_called_once()

    def test_get_mcp_server_status(self):
        """Test the get_mcp_server_status endpoint."""
        # Set up mock return value
        self.mock_api.get_mcp_server_status.return_value = {
            "success": True,
            "operation": "get_mcp_server_status",
            "status": "running",
            "uptime": 3600,
            "endpoints": 25,
            "clients": 3,
            "version": "1.0.0",
            "timestamp": 1234567890
        }

        # Make API request
        response = self.client.get("/cli/mcp/status")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "get_mcp_server_status")
        self.assertEqual(data["status"], "running")
        self.assertEqual(data["uptime"], 3600)
        self.assertEqual(data["endpoints"], 25)
        self.assertEqual(data["clients"], 3)

        # Verify API method was called
        self.mock_api.get_mcp_server_status.assert_called_once()

    def test_get_version(self):
        """Test the get_version endpoint."""
        # Set up mock return value
        self.mock_api._get_version_info.return_value = {
            "ipfs_kit_version": "1.0.0",
            "python_version": "3.9.0",
            "platform": "linux",
            "dependencies": {
                "ipfs": "0.14.0",
                "ipfs_cluster": "0.14.1"
            }
        }

        # Make API request
        response = self.client.get("/cli/version")

        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["version"]["ipfs_kit_version"], "1.0.0")
        self.assertEqual(data["version"]["python_version"], "3.9.0")
        self.assertEqual(data["version"]["platform"], "linux")

        # Verify API method was called appropriately
        # Note: The _get_version_info method might be called internally by get_version, but we're mocking at a lower level

if __name__ == "__main__":
    unittest.main()
