import unittest
from unittest.mock import MagicMock, patch
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
import json


class TestAria2Controller(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        # Create mock Aria2 model
        self.mock_aria2_model = MagicMock()
        
        # Import the controller
        from ipfs_kit_py.mcp.controllers.aria2_controller import Aria2Controller
        
        # Create controller with mock
        self.controller = Aria2Controller(self.mock_aria2_model)
        
        # Set up FastAPI router and app
        self.router = APIRouter()
        self.controller.register_routes(self.router)
        self.app = FastAPI()
        self.app.include_router(self.router)
        self.client = TestClient(self.app)
    
    def test_initialization(self):
        """Test controller initialization."""
        self.assertEqual(self.controller.aria2_model, self.mock_aria2_model)
    
    def test_route_registration(self):
        """Test route registration."""
        route_paths = [route.path for route in self.router.routes]
        self.assertIn("/aria2/download", route_paths)
        self.assertIn("/aria2/status", route_paths)
        self.assertIn("/aria2/list", route_paths)
        self.assertIn("/aria2/cancel/{gid}", route_paths)
    
    def test_handle_status_request(self):
        """Test handling status request."""
        # Configure mock response
        self.mock_aria2_model.get_status.return_value = {
            "success": True,
            "is_running": True,
            "version": "1.36.0",
            "session_id": "s-123456",
            "active_downloads": 2,
            "waiting_downloads": 1,
            "stopped_downloads": 5,
            "global_stats": {
                "download_speed": 1024000,
                "upload_speed": 512000,
                "total_size": 104857600,
                "active_connections": 10
            }
        }
        
        # Send request
        response = self.client.get("/aria2/status")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertTrue(response_data["is_running"])
        self.assertEqual(response_data["version"], "1.36.0")
        self.assertEqual(response_data["active_downloads"], 2)
        
        # Verify model was called
        self.mock_aria2_model.get_status.assert_called_once()
    
    def test_handle_download_request(self):
        """Test handling download request."""
        # Configure mock response
        self.mock_aria2_model.add_uri.return_value = {
            "success": True,
            "gid": "2089b05ecca3d829",
            "uri": "https://example.com/file.zip",
            "status": "waiting",
            "total_length": 104857600,
            "added_time": 1693526400
        }
        
        # Create request
        request_data = {
            "uri": "https://example.com/file.zip",
            "out": "file.zip",
            "dir": "/downloads",
            "max_download_speed": "1M"
        }
        
        # Send request
        response = self.client.post("/aria2/download", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["gid"], "2089b05ecca3d829")
        self.assertEqual(response_data["uri"], "https://example.com/file.zip")
        self.assertEqual(response_data["status"], "waiting")
        
        # Verify model was called with correct parameters
        self.mock_aria2_model.add_uri.assert_called_once_with(
            uri="https://example.com/file.zip",
            out="file.zip",
            dir="/downloads",
            max_download_speed="1M"
        )
    
    def test_handle_list_request(self):
        """Test handling list request."""
        # Configure mock response
        self.mock_aria2_model.list_downloads.return_value = {
            "success": True,
            "downloads": [
                {
                    "gid": "2089b05ecca3d829",
                    "uri": "https://example.com/file1.zip",
                    "status": "active",
                    "completed_length": 52428800,
                    "total_length": 104857600,
                    "download_speed": 1024000,
                    "progress": 0.5,
                    "dir": "/downloads",
                    "files": [
                        {"path": "/downloads/file1.zip", "length": 104857600}
                    ]
                },
                {
                    "gid": "2089b05ecca3d830",
                    "uri": "https://example.com/file2.zip",
                    "status": "waiting",
                    "completed_length": 0,
                    "total_length": 52428800,
                    "download_speed": 0,
                    "progress": 0.0,
                    "dir": "/downloads",
                    "files": [
                        {"path": "/downloads/file2.zip", "length": 52428800}
                    ]
                }
            ],
            "count": 2
        }
        
        # Send request
        response = self.client.get("/aria2/list")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(len(response_data["downloads"]), 2)
        self.assertEqual(response_data["downloads"][0]["gid"], "2089b05ecca3d829")
        self.assertEqual(response_data["downloads"][0]["status"], "active")
        self.assertEqual(response_data["downloads"][1]["uri"], "https://example.com/file2.zip")
        
        # Verify model was called
        self.mock_aria2_model.list_downloads.assert_called_once()
    
    def test_handle_download_status_request(self):
        """Test handling download status request."""
        # Configure mock response
        self.mock_aria2_model.get_download_status.return_value = {
            "success": True,
            "gid": "2089b05ecca3d829",
            "uri": "https://example.com/file1.zip",
            "status": "active",
            "completed_length": 52428800,
            "total_length": 104857600,
            "download_speed": 1024000,
            "upload_speed": 0,
            "progress": 0.5,
            "connections": 5,
            "dir": "/downloads",
            "files": [
                {"path": "/downloads/file1.zip", "length": 104857600}
            ],
            "error_message": None
        }
        
        # Create request
        request_data = {
            "gid": "2089b05ecca3d829"
        }
        
        # Send request
        response = self.client.post("/aria2/status", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["gid"], "2089b05ecca3d829")
        self.assertEqual(response_data["status"], "active")
        self.assertEqual(response_data["progress"], 0.5)
        
        # Verify model was called with correct parameters
        self.mock_aria2_model.get_download_status.assert_called_once_with(
            gid="2089b05ecca3d829"
        )
    
    def test_handle_cancel_request(self):
        """Test handling cancel request."""
        # Configure mock response
        self.mock_aria2_model.cancel_download.return_value = {
            "success": True,
            "gid": "2089b05ecca3d829",
            "status": "removed",
            "was_active": True
        }
        
        # Send request
        response = self.client.delete("/aria2/cancel/2089b05ecca3d829")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["gid"], "2089b05ecca3d829")
        self.assertEqual(response_data["status"], "removed")
        
        # Verify model was called with correct parameters
        self.mock_aria2_model.cancel_download.assert_called_once_with(
            gid="2089b05ecca3d829"
        )
    
    def test_handle_pause_request(self):
        """Test handling pause request."""
        # Configure mock response
        self.mock_aria2_model.pause_download.return_value = {
            "success": True,
            "gid": "2089b05ecca3d829",
            "status": "paused",
            "was_active": True
        }
        
        # Create request
        request_data = {
            "gid": "2089b05ecca3d829"
        }
        
        # Send request
        response = self.client.post("/aria2/pause", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["gid"], "2089b05ecca3d829")
        self.assertEqual(response_data["status"], "paused")
        
        # Verify model was called with correct parameters
        self.mock_aria2_model.pause_download.assert_called_once_with(
            gid="2089b05ecca3d829"
        )
    
    def test_handle_resume_request(self):
        """Test handling resume request."""
        # Configure mock response
        self.mock_aria2_model.resume_download.return_value = {
            "success": True,
            "gid": "2089b05ecca3d829",
            "status": "active",
            "was_paused": True
        }
        
        # Create request
        request_data = {
            "gid": "2089b05ecca3d829"
        }
        
        # Send request
        response = self.client.post("/aria2/resume", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["gid"], "2089b05ecca3d829")
        self.assertEqual(response_data["status"], "active")
        
        # Verify model was called with correct parameters
        self.mock_aria2_model.resume_download.assert_called_once_with(
            gid="2089b05ecca3d829"
        )
    
    # Test error cases
    def test_handle_download_error(self):
        """Test handling download error."""
        # Configure mock to return error
        self.mock_aria2_model.add_uri.return_value = {
            "success": False,
            "error": "Failed to add download",
            "error_type": "Aria2Error",
            "uri": "https://example.com/file.zip"
        }
        
        # Create request
        request_data = {
            "uri": "https://example.com/file.zip",
            "out": "file.zip"
        }
        
        # Send request
        response = self.client.post("/aria2/download", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 500)
        response_data = response.json()
        self.assertEqual(response_data["detail"]["error"], "Failed to add download")
        self.assertEqual(response_data["detail"]["error_type"], "Aria2Error")
    
    def test_handle_status_error(self):
        """Test handling status error."""
        # Configure mock to return error
        self.mock_aria2_model.get_download_status.return_value = {
            "success": False,
            "error": "Download not found",
            "error_type": "DownloadNotFoundError",
            "gid": "invalid-gid"
        }
        
        # Create request
        request_data = {
            "gid": "invalid-gid"
        }
        
        # Send request
        response = self.client.post("/aria2/status", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 500)
        response_data = response.json()
        self.assertEqual(response_data["detail"]["error"], "Download not found")
        self.assertEqual(response_data["detail"]["error_type"], "DownloadNotFoundError")
    
    def test_handle_validation_error(self):
        """Test handling validation error."""
        # Send request with missing required fields
        response = self.client.post("/aria2/download", json={})
        
        # Check response
        self.assertEqual(response.status_code, 400)
        # Validation errors return detailed information about missing fields
        self.assertIn("detail", response.json())
    
    def test_unavailable_service(self):
        """Test behavior when Aria2 service is unavailable."""
        # Set controller to indicate dependencies are not available
        self.controller._has_dependencies = False
        
        # Send request
        response = self.client.get("/aria2/status")
        
        # Check response - should indicate service unavailable
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn("not available", response_data["detail"])