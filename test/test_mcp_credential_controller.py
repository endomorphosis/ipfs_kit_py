"""
Test for the MCP Credentials Controller module.

This module tests the functionality of the Credentials Controller in the MCP server,
ensuring all credential management endpoints are properly exposed via HTTP endpoints.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ipfs_kit_py.mcp.controllers.credential_controller import CredentialController
from ipfs_kit_py.mcp.server import MCPServer


class TestMCPCredentialController(unittest.TestCase):
    """Test case for the MCP Credentials Controller."""

    def setUp(self):
        """Set up test environment."""
        # Create a mock IPFS model
        self.mock_ipfs_model = MagicMock()
        
        # Create a mock credential manager
        self.mock_credential_manager = MagicMock()
        
        # Create a Credentials controller with the mocks
        self.controller = CredentialController(self.mock_ipfs_model, credential_manager=self.mock_credential_manager)
        
        # Create a FastAPI app and test client
        self.app = FastAPI()
        router = self.app.router
        self.controller.register_routes(router)
        self.client = TestClient(self.app)
        
        # Print all registered routes for debugging
        print("\nRegistered routes:")
        for route in self.app.routes:
            print(f"  {route.methods} {route.path}")

    def test_list_credentials(self):
        """Test the list_credentials endpoint (GET /credentials)."""
        # Set up mock return value
        mock_credentials = [
            {
                "name": "default",
                "service": "ipfs",
                "created_at": "2025-04-09T12:34:56Z"
            },
            {
                "name": "test-s3",
                "service": "s3",
                "created_at": "2025-04-09T12:34:56Z"
            }
        ]
        self.mock_credential_manager.list_credentials.return_value = {
            "success": True,
            "credentials": mock_credentials,
            "count": len(mock_credentials)
        }
        
        # Make API request
        response = self.client.get("/credentials")
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 2)
        self.assertEqual(len(data["credentials"]), 2)
        
        # Verify credential manager method was called
        self.mock_credential_manager.list_credentials.assert_called_once()
        
        # Verify specific credentials are present
        services = [cred["service"] for cred in data["credentials"]]
        self.assertIn("ipfs", services)
        self.assertIn("s3", services)
        
    def test_list_credentials_filtered(self):
        """Test the list_credentials endpoint with service filter."""
        # Set up mock return value for filtered credentials
        mock_credentials = [
            {
                "name": "test-s3",
                "service": "s3",
                "created_at": "2025-04-09T12:34:56Z"
            }
        ]
        self.mock_credential_manager.list_credentials.return_value = {
            "success": True,
            "credentials": mock_credentials,
            "count": len(mock_credentials)
        }
        
        # Make API request with service filter
        response = self.client.get("/credentials?service=s3")
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 1)
        
        # Verify credential manager method was called with filter
        self.mock_credential_manager.list_credentials.assert_called_once_with(service="s3")
        
        # Verify only S3 credentials are returned
        self.assertEqual(data["credentials"][0]["service"], "s3")
    
    def test_add_generic_credential(self):
        """Test the add_generic_credential endpoint (POST /credentials)."""
        # Set up mock return value
        self.mock_credential_manager.add_credential.return_value = {
            "success": True,
            "service": "custom-service",
            "name": "custom-cred",
            "message": "Credential added successfully"
        }
        
        # Create payload for adding a generic credential
        payload = {
            "service": "custom-service",
            "name": "custom-cred",
            "values": {
                "api_key": "test-key",
                "api_secret": "test-secret"
            }
        }
        
        # Make API request
        response = self.client.post("/credentials", json=payload)
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["service"], "custom-service")
        self.assertEqual(data["name"], "custom-cred")
        
        # Verify credential manager method was called with correct parameters
        self.mock_credential_manager.add_credential.assert_called_once_with(
            "custom-service", 
            "custom-cred", 
            payload["values"]
        )
    
    def test_add_s3_credential(self):
        """Test the add_s3_credential endpoint (POST /credentials/s3)."""
        # Set up mock return value
        self.mock_credential_manager.add_credential.return_value = {
            "success": True,
            "service": "s3",
            "name": "test-s3",
            "message": "S3 credential added successfully"
        }
        
        # Create payload for S3 credentials
        payload = {
            "name": "test-s3",
            "aws_access_key_id": "test-access-key",
            "aws_secret_access_key": "test-secret-key",
            "region": "us-test-1"
        }
        
        # Make API request
        response = self.client.post("/credentials/s3", json=payload)
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["service"], "s3")
        self.assertEqual(data["name"], "test-s3")
        
        # Verify credential manager method was called with correct parameters
        self.mock_credential_manager.add_credential.assert_called_once()
        args = self.mock_credential_manager.add_credential.call_args
        self.assertEqual(args[0][0], "s3")  # First arg: service
        self.assertEqual(args[0][1], "test-s3")  # Second arg: name
        # Third arg should be the credentials dict
        self.assertEqual(args[0][2]["aws_access_key_id"], "test-access-key")
        self.assertEqual(args[0][2]["aws_secret_access_key"], "test-secret-key")
    
    def test_delete_credential(self):
        """Test the delete_credential endpoint (DELETE /credentials/{service}/{name})."""
        # Set up mock return value
        self.mock_credential_manager.remove_credential.return_value = {
            "success": True,
            "service": "s3",
            "name": "test-s3",
            "message": "Credential removed successfully"
        }
        
        # Make API request
        response = self.client.delete("/credentials/s3/test-s3")
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["service"], "s3")
        self.assertEqual(data["name"], "test-s3")
        
        # Verify credential manager method was called with correct parameters
        self.mock_credential_manager.remove_credential.assert_called_once_with("s3", "test-s3")
    
    def test_error_handling(self):
        """Test error handling in Credentials controller."""
        # Set up mock to raise an exception
        self.mock_credential_manager.list_credentials.side_effect = Exception("Test error")
        
        # Make API request
        response = self.client.get("/credentials")
        
        # Verify response is an error response
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("error", data)
        self.assertIn("Test error", data["error"])


if __name__ == "__main__":
    unittest.main()