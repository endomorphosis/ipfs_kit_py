"""
Test for the MCP CLI Controller module using AnyIO.

This module tests the functionality of the CLI Controller in the MCP server,
ensuring all CLI commands are properly exposed via HTTP endpoints using AnyIO primitives.
"""

import json
import unittest
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# Import anyio for async testing
import anyio

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
        
        # Add test routes manually for missing endpoints
        # Resolve endpoint
        @self.app.get("/cli/resolve/{name}")
        async def resolve_name(name: str):
            self.mock_api.resolve.return_value = {"Path": "/ipfs/QmTest"}
            return {"success": True, "result": self.mock_api.resolve()}
        
        # Connect endpoint
        @self.app.post("/cli/connect/{peer}")
        async def connect_peer(peer: str):
            self.mock_api.connect.return_value = {"Strings": ["connection established"]}
            return {"success": True, "result": self.mock_api.connect()}
        
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
        # TODO: Implement resolve_name endpoint in cli_controller.py first
        # This endpoint is not yet fully implemented in the MCP server
        self.skipTest("resolve_name endpoint not yet implemented in MCP server")

    def test_connect_peer(self):
        """Test the connect_peer endpoint."""
        # TODO: Implement connect_peer endpoint in cli_controller.py first
        # This endpoint is not yet fully implemented in the MCP server
        self.skipTest("connect_peer endpoint not yet implemented in MCP server")

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


# AnyIO-compatible test class
@pytest.mark.anyio
class TestMCPCliControllerAnyIO:
    """Test case for the MCP CLI Controller using AnyIO."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Set up test environment."""
        # Create a mock IPFS model
        self.mock_ipfs_model = MagicMock()
        
        # Add async method mocks for AnyIO compatibility
        self.mock_ipfs_model.name_publish_async = AsyncMock(return_value={
            "Name": "QmTest", 
            "Value": "/ipfs/QmTest",
            "operation_id": "test_op_123",
            "format": "json",
            "success": True
        })
        
        # Create a CLI controller with the mock model
        self.controller = CliController(self.mock_ipfs_model)
        
        # Create a FastAPI app and test client
        self.app = FastAPI()
        router = self.app.router
        self.controller.register_routes(router)
        self.client = TestClient(self.app)
        
        # Add test routes manually for missing endpoints
        # Resolve endpoint
        @self.app.get("/cli/resolve/{name}")
        async def resolve_name(name: str):
            return {"success": True, "result": {"Path": "/ipfs/QmTest"}}
        
        # Connect endpoint
        @self.app.post("/cli/connect/{peer}")
        async def connect_peer(peer: str):
            return {"success": True, "result": {"Strings": ["connection established"]}}
        
        # Patch the IPFSSimpleAPI class in the controller
        self.api_patcher = patch('ipfs_kit_py.mcp.controllers.cli_controller.IPFSSimpleAPI')
        self.mock_api_class = self.api_patcher.start()
        self.mock_api = MagicMock()
        
        # Add async method mocks for AnyIO compatibility
        self.mock_api.add_async = AsyncMock(return_value={"Hash": "QmTest"})
        self.mock_api.get_async = AsyncMock(return_value=b"test content")
        self.mock_api.pin_async = AsyncMock(return_value={"Pins": ["QmTest"]})
        self.mock_api.unpin_async = AsyncMock(return_value={"Pins": ["QmTest"]})
        self.mock_api.list_pins_async = AsyncMock(return_value={"Keys": {"QmTest": {"Type": "recursive"}}})
        self.mock_api.peers_async = AsyncMock(return_value=["/ip4/127.0.0.1/tcp/4001/p2p/QmTest"])
        self.mock_api.exists_async = AsyncMock(return_value=True)
        self.mock_api.ls_async = AsyncMock(return_value={"Entries": [{"Name": "test", "Type": 1, "Size": 0}]})
        self.mock_api.generate_sdk_async = AsyncMock(return_value={"path": "/tmp/sdk"})
        
        self.mock_api_class.return_value = self.mock_api
        self.controller.api = self.mock_api
        
        yield
        
        # Cleanup
        self.api_patcher.stop()

    @pytest.mark.anyio
    async def test_add_content_async(self):
        """Test the add_content endpoint with AnyIO."""
        # Make API request with async client
        response = self.client.post(
            "/cli/add",
            json={"content": "test content"}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # In a real async test, we'd use something like:
        # async with AsyncClient(app=self.app) as ac:
        #     response = await ac.post("/cli/add", json={"content": "test content"})

    @pytest.mark.anyio
    async def test_get_content_async(self):
        """Test the get_content endpoint with AnyIO."""
        # Make API request
        response = self.client.get("/cli/cat/QmTest")
        
        # Verify response
        assert response.status_code == 200
        assert response.content == b"test content"

    @pytest.mark.anyio
    async def test_pin_content_async(self):
        """Test the pin_content endpoint with AnyIO."""
        # Make API request
        response = self.client.post("/cli/pin/QmTest")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.anyio
    async def test_unpin_content_async(self):
        """Test the unpin_content endpoint with AnyIO."""
        # Make API request
        response = self.client.post("/cli/unpin/QmTest")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.anyio
    async def test_list_pins_async(self):
        """Test the list_pins endpoint with AnyIO."""
        # Make API request
        response = self.client.get("/cli/pins")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.anyio
    async def test_publish_content_async(self):
        """Test the publish_content endpoint with AnyIO."""
        # Make API request
        response = self.client.post("/cli/publish/QmTest?key=self&lifetime=24h&ttl=1h")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.anyio
    async def test_list_peers_async(self):
        """Test the list_peers endpoint with AnyIO."""
        # Make API request
        response = self.client.get("/cli/peers")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.anyio
    async def test_check_existence_async(self):
        """Test the check_existence endpoint with AnyIO."""
        # Make API request
        response = self.client.get("/cli/exists/QmTest")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["result"]["exists"] is True

    @pytest.mark.anyio
    async def test_list_directory_async(self):
        """Test the list_directory endpoint with AnyIO."""
        # Make API request
        response = self.client.get("/cli/ls/QmTest")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.anyio
    async def test_generate_sdk_async(self):
        """Test the generate_sdk endpoint with AnyIO."""
        # Make API request
        response = self.client.post(
            "/cli/generate-sdk",
            json={"language": "python", "output_dir": "/tmp"}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.anyio
    async def test_error_handling_async(self):
        """Test error handling in CLI controller with AnyIO."""
        # Set up mock to raise an exception
        self.mock_api.get.side_effect = Exception("Test error")
        
        # Make API request
        response = self.client.get("/cli/cat/QmTest")
        
        # Verify response is an error response
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_anyio_sleep_integration(self):
        """Test the integration with anyio.sleep."""
        # Create a method that uses sleep to simulate network delay
        async def add_with_delay_async(content, delay=0.1):
            # Simulate network or processing delay
            await anyio.sleep(delay)
            
            # Mock result after delay
            return {
                "success": True,
                "Hash": "QmTest",
                "Size": len(content)
            }
        
        # Set up the mock implementation
        self.mock_api.add_async = AsyncMock(side_effect=add_with_delay_async)
        
        # Call the method with a delay
        start_time = time.time()
        result = await self.mock_api.add_async("test content", delay=0.1)
        end_time = time.time()
        
        # Verify the result
        assert result["success"] is True
        assert result["Hash"] == "QmTest"
        
        # Verify the delay
        elapsed = end_time - start_time
        assert elapsed >= 0.1, f"Expected delay of at least 0.1s, but got {elapsed}s"


if __name__ == "__main__":
    unittest.main()