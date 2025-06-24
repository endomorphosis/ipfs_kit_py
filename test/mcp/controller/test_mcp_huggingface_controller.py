"""
Test module for HuggingFaceController in MCP server.

This module tests the HuggingFaceController class that handles HTTP endpoints for Hugging Face Hub operations.
"""

import os
import tempfile
import json
import unittest
from unittest.mock import MagicMock, patch

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient


class TestHuggingFaceController(unittest.TestCase):
    """Test cases for HuggingFaceController."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock the HuggingFaceController class
        self.controller_patcher = patch('ipfs_kit_py.mcp.controllers.storage.huggingface_controller.HuggingFaceController')
        self.mock_controller_class = self.controller_patcher.start()

        # Create an instance of the mocked controller
        self.mock_controller = MagicMock()
        self.mock_controller_class.return_value = self.mock_controller

        # Mock the route registration method
        self.mock_controller.register_routes = MagicMock()

        # Mock the handler methods
        self.mock_controller.handle_auth_request = MagicMock()
        self.mock_controller.handle_repo_creation_request = MagicMock()
        self.mock_controller.handle_upload_request = MagicMock()
        self.mock_controller.handle_download_request = MagicMock()
        self.mock_controller.handle_list_models_request = MagicMock()
        self.mock_controller.handle_ipfs_to_huggingface_request = MagicMock()
        self.mock_controller.handle_huggingface_to_ipfs_request = MagicMock()
        self.mock_controller.handle_status_request = MagicMock()

        # Create mock HuggingFace model
        self.mock_hf_model = MagicMock()

        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()

        # Create a test file
        self.test_file_path = os.path.join(self.temp_dir, "test_file.txt")
        with open(self.test_file_path, "w") as f:
            f.write("Test content for Hugging Face upload")

    def tearDown(self):
        """Clean up test fixtures."""
        # Stop the patcher
        self.controller_patcher.stop()

        # Remove temporary directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_controller_initialization(self):
        """Test HuggingFaceController initialization."""
        # Import the controller here to avoid import errors during collection
        from ipfs_kit_py.mcp.controllers.storage.huggingface_controller import HuggingFaceController

        # Create the controller with mock model
        controller = HuggingFaceController(self.mock_hf_model)

        # Check that model is properly stored
        self.assertEqual(controller.huggingface_model, self.mock_hf_model)

    def test_route_registration(self):
        """Test that routes are registered correctly."""
        # Import the controller here to avoid import errors during collection
        from ipfs_kit_py.mcp.controllers.storage.huggingface_controller import HuggingFaceController

        # Create controller
        controller = HuggingFaceController(self.mock_hf_model)

        # Create router
        router = APIRouter()

        # Register routes
        controller.register_routes(router)

        # Check that routes were registered
        route_paths = [route.path for route in router.routes]
        expected_paths = [
            "/huggingface/auth",
            "/huggingface/repo/create",
            "/huggingface/upload",
            "/huggingface/download",
            "/huggingface/models",
            "/huggingface/from_ipfs",
            "/huggingface/to_ipfs",
            "/storage/huggingface/status"
        ]

        for path in expected_paths:
            self.assertIn(path, route_paths)

    def test_auth_success_flow(self):
        """Test successful authentication flow."""
        # Import the controller here to avoid import errors during collection
        from ipfs_kit_py.mcp.controllers.storage.huggingface_controller import HuggingFaceController

        # Configure mock model response
        self.mock_hf_model.authenticate.return_value = {
            "success": True,
            "authenticated": True,
            "user_info": {
                "name": "Test User",
                "email": "test@example.com"
            },
            "duration_ms": 50.5
        }

        # Create controller and test app
        controller = HuggingFaceController(self.mock_hf_model)
        app = FastAPI()
        router = APIRouter()
        controller.register_routes(router)
        app.include_router(router)
        client = TestClient(app)

        # Create request
        request_data = {
            "token": "test-token"
        }

        # Send request
        response = client.post("/huggingface/auth", json=request_data)

        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertTrue(response_data["authenticated"])
        self.assertEqual(response_data["user_info"]["name"], "Test User")

        # Check that model was called with correct parameters
        self.mock_hf_model.authenticate.assert_called_once_with(token="test-token")

    def test_auth_error_flow(self):
        """Test authentication error flow."""
        # Import the controller here to avoid import errors during collection
        from ipfs_kit_py.mcp.controllers.storage.huggingface_controller import HuggingFaceController

        # Configure mock model response
        self.mock_hf_model.authenticate.return_value = {
            "success": False,
            "error": "Authentication failed",
            "error_type": "AuthenticationError"
        }

        # Create controller and test app
        controller = HuggingFaceController(self.mock_hf_model)
        app = FastAPI()
        router = APIRouter()
        controller.register_routes(router)
        app.include_router(router)
        client = TestClient(app)

        # Create request
        request_data = {
            "token": "invalid-token"
        }

        # Send request
        response = client.post("/huggingface/auth", json=request_data)

        # Check response
        self.assertEqual(response.status_code, 401)
        response_data = response.json()
        self.assertEqual(response_data["detail"]["error"], "Authentication failed")
        self.assertEqual(response_data["detail"]["error_type"], "AuthenticationError")

    def test_status_endpoint(self):
        """Test status endpoint."""
        # Import the controller here to avoid import errors during collection
        from ipfs_kit_py.mcp.controllers.storage.huggingface_controller import HuggingFaceController

        # Configure mock model response
        self.mock_hf_model.get_stats.return_value = {
            "backend_name": "HuggingFace",
            "operation_stats": {
                "upload_count": 10,
                "download_count": 5,
                "auth_count": 2,
                "repo_creation_count": 3
            },
            "timestamp": 1672531600.0
        }

        # Create controller and test app
        controller = HuggingFaceController(self.mock_hf_model)
        app = FastAPI()
        router = APIRouter()
        controller.register_routes(router)
        app.include_router(router)
        client = TestClient(app)

        # Send request
        response = client.get("/storage/huggingface/status")

        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["backend"], "huggingface")
        self.assertTrue(response_data["is_available"])
        self.assertIn("stats", response_data)

        # Check that model was called
        self.mock_hf_model.get_stats.assert_called_once()


if __name__ == "__main__":
    unittest.main()
