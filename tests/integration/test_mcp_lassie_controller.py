import unittest
from unittest.mock import MagicMock, patch
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
import tempfile
import os
import sys
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


class TestLassieController(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        # Create mock Lassie model
        self.mock_lassie_model = MagicMock()
        
        # Import the controller
        from ipfs_kit_py.mcp.controllers.storage.lassie_controller import LassieController
        
        # Create controller with mock model
        self.controller = LassieController(self.mock_lassie_model)
        
        # Set up FastAPI router and app
        self.router = APIRouter()
        self.controller.register_routes(self.router)
        self.app = FastAPI()
        self.app.include_router(self.router)
        self.client = TestClient(self.app)
        
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.test_output_path = os.path.join(self.temp_dir, "test_output.bin")
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test controller initialization."""
        self.assertEqual(self.controller.lassie_model, self.mock_lassie_model)
    
    def test_route_registration(self):
        """Test route registration."""
        route_paths = [route.path for route in self.router.routes]
        self.assertIn("/storage/lassie/fetch", route_paths)
        self.assertIn("/storage/lassie/fetch_car", route_paths)
        self.assertIn("/storage/lassie/status", route_paths)
    
    def test_handle_status_request(self):
        """Test handling status request."""
        # Configure mock response
        self.mock_lassie_model.get_status.return_value = {
            "success": True,
            "version": "0.6.0",
            "is_available": True,
            "concurrent_fetches": 5,
            "config": {
                "timeout_seconds": 300,
                "max_blocks": 10000,
                "max_providers": 50
            },
            "stats": {
                "total_fetches": 100,
                "successful_fetches": 95,
                "failed_fetches": 5,
                "avg_fetch_time_ms": 450.5
            }
        }
        
        # Send request
        response = self.client.get("/storage/lassie/status")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["version"], "0.6.0")
        self.assertTrue(response_data["is_available"])
        self.assertEqual(response_data["stats"]["successful_fetches"], 95)
        
        # Verify model was called
        self.mock_lassie_model.get_status.assert_called_once()
    
    def test_handle_fetch_request(self):
        """Test handling fetch request."""
        # Configure mock response
        self.mock_lassie_model.fetch.return_value = {
            "success": True,
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "output_path": self.test_output_path,
            "size_bytes": 1024,
            "duration_ms": 125.5,
            "blocks_fetched": 10,
            "providers_used": 2
        }
        
        # Create request
        request_data = {
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "output_path": self.test_output_path,
            "timeout_seconds": 300
        }
        
        # Send request
        response = self.client.post("/storage/lassie/fetch", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["cid"], "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi")
        self.assertEqual(response_data["output_path"], self.test_output_path)
        self.assertEqual(response_data["blocks_fetched"], 10)
        
        # Verify model was called with correct parameters
        self.mock_lassie_model.fetch.assert_called_once_with(
            cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            output_path=self.test_output_path,
            timeout_seconds=300
        )
    
    def test_handle_fetch_car_request(self):
        """Test handling fetch CAR request."""
        # Configure mock response
        car_path = os.path.join(self.temp_dir, "test.car")
        self.mock_lassie_model.fetch_car.return_value = {
            "success": True,
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "output_path": car_path,
            "size_bytes": 2048,
            "duration_ms": 250.5,
            "blocks_fetched": 20,
            "providers_used": 3,
            "is_car": True
        }
        
        # Create request
        request_data = {
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "output_path": car_path,
            "timeout_seconds": 600,
            "max_blocks": 1000
        }
        
        # Send request
        response = self.client.post("/storage/lassie/fetch_car", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["cid"], "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi")
        self.assertEqual(response_data["output_path"], car_path)
        self.assertEqual(response_data["blocks_fetched"], 20)
        self.assertTrue(response_data["is_car"])
        
        # Verify model was called with correct parameters
        self.mock_lassie_model.fetch_car.assert_called_once_with(
            cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            output_path=car_path,
            timeout_seconds=600,
            max_blocks=1000
        )
    
    def test_handle_verify_request(self):
        """Test handling verify request."""
        # Configure mock response
        self.mock_lassie_model.verify_data.return_value = {
            "success": True,
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "file_path": self.test_output_path,
            "is_valid": True,
            "size_bytes": 1024,
            "blocks_verified": 10,
            "verification_time_ms": 75.5
        }
        
        # Create request
        request_data = {
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "file_path": self.test_output_path
        }
        
        # Send request
        response = self.client.post("/storage/lassie/verify", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["cid"], "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi")
        self.assertEqual(response_data["file_path"], self.test_output_path)
        self.assertTrue(response_data["is_valid"])
        
        # Verify model was called with correct parameters
        self.mock_lassie_model.verify_data.assert_called_once_with(
            cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            file_path=self.test_output_path
        )
    
    def test_handle_find_providers_request(self):
        """Test handling find providers request."""
        # Configure mock response
        self.mock_lassie_model.find_providers.return_value = {
            "success": True,
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "providers": [
                {
                    "peer_id": "12D3KooWQYV9dGMFoRzNStwsrVfMEZn9YQ9HGtVDhgNCyqvj2oGT",
                    "multiaddrs": [
                        "/ip4/192.168.1.101/tcp/4001",
                        "/ip4/192.168.1.101/udp/4001/quic"
                    ],
                    "protocols": ["bitswap", "graphsync"],
                    "latency_ms": 25.5
                },
                {
                    "peer_id": "12D3KooWJHQxJGNGbvX7VujYZ8yfDq5hcAzVbX4zBDsBz9qRs1X7",
                    "multiaddrs": [
                        "/ip4/192.168.1.102/tcp/4001"
                    ],
                    "protocols": ["bitswap"],
                    "latency_ms": 50.2
                }
            ],
            "provider_count": 2,
            "search_duration_ms": 150.5
        }
        
        # Create request
        request_data = {
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "timeout_seconds": 30,
            "max_providers": 10
        }
        
        # Send request
        response = self.client.post("/storage/lassie/providers", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["cid"], "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi")
        self.assertEqual(len(response_data["providers"]), 2)
        self.assertEqual(response_data["providers"][0]["peer_id"], 
                         "12D3KooWQYV9dGMFoRzNStwsrVfMEZn9YQ9HGtVDhgNCyqvj2oGT")
        
        # Verify model was called with correct parameters
        self.mock_lassie_model.find_providers.assert_called_once_with(
            cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            timeout_seconds=30,
            max_providers=10
        )
    
    # Test error cases
    def test_handle_fetch_error(self):
        """Test handling fetch error."""
        # Configure mock to return error
        self.mock_lassie_model.fetch.return_value = {
            "success": False,
            "error": "Content not found",
            "error_type": "ContentNotFoundError",
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
        }
        
        # Create request
        request_data = {
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "output_path": self.test_output_path
        }
        
        # Send request
        response = self.client.post("/storage/lassie/fetch", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 500)
        response_data = response.json()
        self.assertEqual(response_data["detail"]["error"], "Content not found")
        self.assertEqual(response_data["detail"]["error_type"], "ContentNotFoundError")
    
    def test_handle_timeout_error(self):
        """Test handling timeout error."""
        # Configure mock to return error
        self.mock_lassie_model.fetch.return_value = {
            "success": False,
            "error": "Operation timed out",
            "error_type": "TimeoutError",
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "timeout_seconds": 30
        }
        
        # Create request
        request_data = {
            "cid": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "output_path": self.test_output_path,
            "timeout_seconds": 30
        }
        
        # Send request
        response = self.client.post("/storage/lassie/fetch", json=request_data)
        
        # Check response
        self.assertEqual(response.status_code, 500)
        response_data = response.json()
        self.assertEqual(response_data["detail"]["error"], "Operation timed out")
        self.assertEqual(response_data["detail"]["error_type"], "TimeoutError")
    
    def test_handle_validation_error(self):
        """Test handling validation error."""
        # Send request with missing required fields
        response = self.client.post("/storage/lassie/fetch", json={})
        
        # Check response
        self.assertEqual(response.status_code, 400)
        # Validation errors return detailed information about missing fields
        self.assertIn("detail", response.json())
    
    def test_unavailable_service(self):
        """Test behavior when Lassie service is unavailable."""
        # Set controller to indicate dependencies are not available
        self.controller._has_dependencies = False
        
        # Send request
        response = self.client.get("/storage/lassie/status")
        
        # Check response - should indicate service unavailable
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn("not available", response_data["detail"])