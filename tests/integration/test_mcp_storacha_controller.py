import unittest
from unittest.mock import MagicMock, patch
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
import tempfile
import os
import json


class TestStorachaController(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        # Create mock Storacha model
        self.mock_storacha_model = MagicMock()
        
        # Import the controller
        from ipfs_kit_py.mcp.controllers.storage.storacha_controller import StorachaController
        
        # Create controller with mock
        self.controller = StorachaController(self.mock_storacha_model)
        
        # Set up FastAPI router and app
        self.router = APIRouter()
        self.controller.register_routes(self.router)
        self.app = FastAPI()
        self.app.include_router(self.router)
        self.client = TestClient(self.app)
        
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.test_file_path = os.path.join(self.temp_dir, "test_file.txt")
        with open(self.test_file_path, "w") as f:
            f.write("Test content for Storacha upload")
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test controller initialization."""
        self.assertEqual(self.controller.storacha_model, self.mock_storacha_model)
    
    def test_route_registration(self):
        """Test route registration."""
        route_paths = [route.path for route in self.router.routes]
        self.assertIn("/storage/storacha/upload", route_paths)
        self.assertIn("/storage/storacha/retrieve", route_paths)
        self.assertIn("/storage/storacha/status", route_paths)
    
    def test_handle_status_request(self):
        """Test handling status request."""
        # Configure mock response
        self.mock_storacha_model.get_status.return_value = {
            "success": True,
            "is_connected": True,
            "space_did": "did:web:example.storacha.web",
            "account": "test@example.com",
            "used_storage": 1024,
            "uploads_count": 10
        }
        
        # Send request
        response = self.client.get("/storage/storacha/status")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertTrue(response_data["is_connected"])
        self.assertEqual(response_data["space_did"], "did:web:example.storacha.web")
        
        # Verify model was called
        self.mock_storacha_model.get_status.assert_called_once()
    
    def test_handle_upload_request(self):
        """Test handling upload request."""
        # Configure mock response
        self.mock_storacha_model.upload_file.return_value = {
            "success": True,
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "file_path": self.test_file_path,
            "size_bytes": 100,
            "duration_ms": 50.5
        }
        
        # Create request
        request_data = {
            "file_path": self.test_file_path,
        }
        
        # Send request
        response = self.client.post("/storage/storacha/upload", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["cid"], "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi")
        self.assertEqual(response_data["file_path"], self.test_file_path)
        
        # Verify model was called with correct parameters
        self.mock_storacha_model.upload_file.assert_called_once_with(file_path=self.test_file_path)
    
    def test_handle_retrieve_request(self):
        """Test handling retrieve request."""
        # Configure mock response
        self.mock_storacha_model.retrieve_file.return_value = {
            "success": True,
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "output_path": "/tmp/output.txt",
            "size_bytes": 100,
            "duration_ms": 50.5
        }
        
        # Create request
        request_data = {
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "output_path": "/tmp/output.txt"
        }
        
        # Send request
        response = self.client.post("/storage/storacha/retrieve", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["cid"], "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi")
        self.assertEqual(response_data["output_path"], "/tmp/output.txt")
        
        # Verify model was called with correct parameters
        self.mock_storacha_model.retrieve_file.assert_called_once_with(
            cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            output_path="/tmp/output.txt"
        )
    
    def test_handle_list_request(self):
        """Test handling list request."""
        # Configure mock response
        self.mock_storacha_model.list_files.return_value = {
            "success": True,
            "files": [
                {
                    "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
                    "name": "test1.txt",
                    "size": 100,
                    "uploaded_at": "2023-01-01T00:00:00Z"
                },
                {
                    "cid": "bafybeihykxewafc5hwz2fz6fkzd5a2rxl5avcktcbvvuo6qnni7v3tsvni",
                    "name": "test2.txt",
                    "size": 200,
                    "uploaded_at": "2023-01-02T00:00:00Z"
                }
            ],
            "count": 2,
            "space_did": "did:web:example.storacha.web"
        }
        
        # Send request
        response = self.client.get("/storage/storacha/list")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(len(response_data["files"]), 2)
        self.assertEqual(response_data["files"][0]["cid"], 
                         "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi")
        
        # Verify model was called
        self.mock_storacha_model.list_files.assert_called_once()
    
    def test_handle_upload_car_request(self):
        """Test handling CAR file upload request."""
        # Configure mock response
        self.mock_storacha_model.upload_car.return_value = {
            "success": True,
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "car_path": "/tmp/test.car",
            "size_bytes": 1024,
            "duration_ms": 100.5
        }
        
        # Create request
        request_data = {
            "car_path": "/tmp/test.car"
        }
        
        # Send request
        response = self.client.post("/storage/storacha/upload_car", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["cid"], "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi")
        self.assertEqual(response_data["car_path"], "/tmp/test.car")
        
        # Verify model was called with correct parameters
        self.mock_storacha_model.upload_car.assert_called_once_with(car_path="/tmp/test.car")
    
    # Test error cases
    def test_handle_upload_error(self):
        """Test handling upload error."""
        # Configure mock to return error
        self.mock_storacha_model.upload_file.return_value = {
            "success": False,
            "error": "Upload failed",
            "error_type": "StorachaError"
        }
        
        # Create request
        request_data = {
            "file_path": self.test_file_path,
        }
        
        # Send request
        response = self.client.post("/storage/storacha/upload", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 500)
        response_data = response.json()
        self.assertEqual(response_data["detail"]["error"], "Upload failed")
        self.assertEqual(response_data["detail"]["error_type"], "StorachaError")
    
    def test_handle_retrieve_error(self):
        """Test handling retrieve error."""
        # Configure mock to return error
        self.mock_storacha_model.retrieve_file.return_value = {
            "success": False,
            "error": "Content not found",
            "error_type": "StorachaContentNotFoundError"
        }
        
        # Create request
        request_data = {
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "output_path": "/tmp/output.txt"
        }
        
        # Send request
        response = self.client.post("/storage/storacha/retrieve", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 500)
        response_data = response.json()
        self.assertEqual(response_data["detail"]["error"], "Content not found")
        self.assertEqual(response_data["detail"]["error_type"], "StorachaContentNotFoundError")
    
    def test_handle_validation_error(self):
        """Test handling validation error."""
        # Send request with missing required fields
        response = self.client.post("/storage/storacha/upload", json={})
        
        # Check response
        self.assertEqual(response.status_code, 400)
        # Validation errors return detailed information about missing fields
        self.assertIn("detail", response.json())
    
    def test_unavailable_service(self):
        """Test behavior when Storacha service is unavailable."""
        # Set controller to indicate dependencies are not available
        self.controller._has_dependencies = False
        
        # Send request
        response = self.client.get("/storage/storacha/status")
        
        # Check response - should indicate service unavailable
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn("not available", response_data["detail"])