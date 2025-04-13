"""
Test the credential management functionality of the MCP server.

This test file verifies that the MCP server can properly manage credentials
for various backends including IPFS, S3, Storacha, and Filecoin.
"""

import os
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from fastapi import FastAPI

from ipfs_kit_py.mcp.server import MCPServer
from ipfs_kit_py.credential_manager import CredentialManager

class TestMCPCredentialManagement(unittest.TestCase):
    """Test the credential management functionality of the MCP server."""
    
    def setUp(self):
        """Set up a test environment with a temporary directory for credentials."""
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.credential_file_path = os.path.join(self.test_dir, "credentials.json")
        
        # Create an app for testing
        self.app = FastAPI()
        
        # Create MCP server with temporary directory
        self.mcp_server = MCPServer(
            debug_mode=True,
            persistence_path=self.test_dir,
            isolation_mode=True
        )
        
        # Register the MCP server with the app
        self.mcp_server.register_with_app(self.app, prefix="/api/v0")
        
        # Create test client
        self.client = TestClient(self.app)
        
    def tearDown(self):
        """Clean up after tests."""
        # Shut down MCP server
        self.mcp_server.shutdown()
        
        # Remove temporary directory
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_credential_endpoints_exist(self):
        """Test that credential endpoints are registered properly."""
        # Check that the health endpoint works
        response = self.client.get("/api/v0/health")
        self.assertEqual(response.status_code, 200)
        
        # Check that debug information includes credentials
        response = self.client.get("/api/v0/debug")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify credentials section exists and is properly initialized
        self.assertIn("credentials", data)
        self.assertTrue(data["credentials"]["enabled"])
        self.assertIn("services", data["credentials"])
        
        # Verify credential endpoints are registered by checking list endpoint
        response = self.client.get("/api/v0/credentials")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("credentials", data)
        self.assertIn("count", data)
    
    def test_add_s3_credentials(self):
        """Test adding S3 credentials."""
        # Create test credentials
        credentials = {
            "name": "test-s3",
            "aws_access_key_id": "test-access-key",
            "aws_secret_access_key": "test-secret-key",
            "endpoint_url": "https://test-s3.example.com",
            "region": "us-test-1"
        }
        
        # Add credentials
        response = self.client.post("/api/v0/credentials/s3", json=credentials)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["name"], "test-s3")
        self.assertEqual(data["service"], "s3")
        
        # List credentials and verify the new one is there
        response = self.client.get("/api/v0/credentials")
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 1)
        
        # Verify credential file exists
        self.assertTrue(os.path.exists(self.credential_file_path))
        
        # Verify credential was stored correctly
        with open(self.credential_file_path, "r") as f:
            stored_credentials = json.load(f)
        
        self.assertIn("s3_test-s3", stored_credentials)
        self.assertEqual(stored_credentials["s3_test-s3"]["credentials"]["aws_access_key_id"], "test-access-key")
        self.assertEqual(stored_credentials["s3_test-s3"]["credentials"]["aws_secret_access_key"], "test-secret-key")
    
    def test_add_storacha_credentials(self):
        """Test adding Storacha credentials."""
        # Create test credentials
        credentials = {
            "name": "test-storacha",
            "api_token": "test-token-12345",
            "space_did": "did:key:test123456789"
        }
        
        # Add credentials
        response = self.client.post("/api/v0/credentials/storacha", json=credentials)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        
        # List credentials and verify the new one is there
        response = self.client.get("/api/v0/credentials")
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 1)
        
        # Verify credential is the one we added
        found = False
        for cred in data["credentials"]:
            if cred["service"] == "storacha" and cred["name"] == "test-storacha":
                found = True
                break
                
        self.assertTrue(found, "Storacha credential not found in list")
    
    def test_add_filecoin_credentials(self):
        """Test adding Filecoin credentials."""
        # Create test credentials
        credentials = {
            "name": "test-filecoin",
            "api_key": "test-filecoin-key",
            "api_secret": "test-filecoin-secret",
            "wallet_address": "f12345test",
            "provider": "estuary"
        }
        
        # Add credentials
        response = self.client.post("/api/v0/credentials/filecoin", json=credentials)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        
        # List credentials and verify the new one is there
        response = self.client.get("/api/v0/credentials")
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 1)
    
    def test_add_ipfs_credentials(self):
        """Test adding IPFS credentials."""
        # Create test credentials
        credentials = {
            "name": "test-ipfs",
            "identity": "test-identity-data",
            "api_address": "/ip4/127.0.0.1/tcp/5001",
            "cluster_secret": "test-cluster-secret"
        }
        
        # Add credentials
        response = self.client.post("/api/v0/credentials/ipfs", json=credentials)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        
        # List credentials and verify the new one is there
        response = self.client.get("/api/v0/credentials")
        data = response.json()
        self.assertTrue(data["success"])
        
        # Since adding IPFS credentials with cluster_secret adds two credential entries
        # (one for ipfs and one for ipfs_cluster), there should be 2 credentials
        self.assertEqual(data["count"], 2)
    
    def test_delete_credential(self):
        """Test deleting a credential."""
        # First add a credential
        credentials = {
            "name": "test-delete",
            "aws_access_key_id": "delete-key",
            "aws_secret_access_key": "delete-secret"
        }
        
        # Add S3 credentials
        response = self.client.post("/api/v0/credentials/s3", json=credentials)
        self.assertEqual(response.status_code, 200)
        
        # Verify it exists
        response = self.client.get("/api/v0/credentials")
        data = response.json()
        self.assertEqual(data["count"], 1)
        
        # Delete the credential
        response = self.client.delete("/api/v0/credentials/s3/test-delete")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        
        # Verify it's gone
        response = self.client.get("/api/v0/credentials")
        data = response.json()
        self.assertEqual(data["count"], 0)
    
    def test_credentials_used_for_operations(self):
        """Test that credentials are used for operations when available."""
        # Mock the credential manager to return predictable credentials
        mock_creds = {
            "type": "s3",
            "aws_access_key_id": "mock-access-key",
            "aws_secret_access_key": "mock-secret-key",
            "endpoint_url": "https://mock-s3.example.com",
            "region": "us-mock-1"
        }
        
        with patch.object(CredentialManager, 'get_credential', return_value=mock_creds):
            # Mock the IPFSModel._get_credentials method to verify it's called during operations
            original_get_credentials = self.mcp_server.models["ipfs"]._get_credentials
            
            calls = []
            def mock_get_credentials(service, name="default"):
                calls.append((service, name))
                return original_get_credentials(service, name)
                
            with patch.object(self.mcp_server.models["ipfs"], '_get_credentials', side_effect=mock_get_credentials):
                # Test that connection test tries to use credentials
                self.mcp_server.models["ipfs"]._test_connection()
                
                # Verify that _get_credentials was called for IPFS
                self.assertTrue(any(call[0] == "ipfs" for call in calls))
                
                # Reset calls for next test
                calls.clear()
                
                # Test other operations as needed...
                
                # Test debug state includes credentials
                response = self.client.get("/api/v0/debug")
                data = response.json()
                
                # Verify credentials section exists
                self.assertIn("credentials", data)
                self.assertTrue(data["credentials"]["enabled"])

if __name__ == "__main__":
    unittest.main()