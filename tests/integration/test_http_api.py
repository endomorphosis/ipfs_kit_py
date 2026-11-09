"""
Comprehensive test suite for HTTP API endpoints.

This module contains tests for the FastAPI-based HTTP API that exposes
IPFS Kit functionality.
"""

import os
import sys
import pytest
import logging
import json
from unittest.mock import MagicMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Skip if FastAPI is not available
pytest.importorskip("fastapi", reason="FastAPI is not installed")

# Try to import necessary modules
try:
    from fastapi.testclient import TestClient
    from ipfs_kit_py.api.server import app, router
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
except ImportError as e:
    logger.error(f"Error importing API modules: {e}")
    # Create mock versions
    from fastapi import FastAPI
    app = FastAPI()
    router = MagicMock()
    app.include_router(router)
    
    from fastapi.testclient import TestClient
    
    class IPFSSimpleAPI:
        def __init__(self, config=None):
            self.config = config or {}
        
        def add(self, content):
            return {"Hash": "QmTestHash"}
        
        def get(self, cid):
            return b"test content"

@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    # Mock the IPFSSimpleAPI
    with patch('ipfs_kit_py.api.server.IPFSSimpleAPI') as mock_api_class:
        mock_api = MagicMock()
        mock_api.add.return_value = {"Hash": "QmTestHash"}
        mock_api.get.return_value = b"test content"
        mock_api_class.return_value = mock_api
        
        # Create the test client
        client = TestClient(app)
        yield client

# Test API Endpoints
class TestAPIEndpoints:
    
    def test_health_endpoint(self, test_client):
        """Test the health endpoint."""
        response = test_client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"
    
    def test_add_endpoint(self, test_client):
        """Test the add endpoint."""
        # Test with string content
        response = test_client.post(
            "/api/v0/add",
            json={"content": "test content"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "Hash" in data
        assert data["Hash"] == "QmTestHash"
    
    def test_get_endpoint(self, test_client):
        """Test the get endpoint."""
        response = test_client.get("/api/v0/get/QmTestHash")
        assert response.status_code == 200
        assert response.content == b"test content"
    
    def test_add_file_endpoint(self, test_client):
        """Test the add file endpoint."""
        # Create a test file
        file_content = b"test file content"
        files = {"file": ("test.txt", file_content, "text/plain")}
        
        response = test_client.post(
            "/api/v0/add/file",
            files=files
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "Hash" in data
        assert data["Hash"] == "QmTestHash"
    
    def test_pin_endpoint(self, test_client):
        """Test the pin endpoint."""
        with patch('ipfs_kit_py.api.server.get_api') as mock_get_api:
            mock_api = MagicMock()
            mock_api.pin_add.return_value = {"Pins": ["QmTestHash"]}
            mock_get_api.return_value = mock_api
            
            response = test_client.post(
                "/api/v0/pin/add",
                json={"cid": "QmTestHash"}
            )
            assert response.status_code == 200
            
            data = response.json()
            assert "Pins" in data
            assert "QmTestHash" in data["Pins"]
    
    def test_error_handling(self, test_client):
        """Test error handling."""
        with patch('ipfs_kit_py.api.server.get_api') as mock_get_api:
            mock_api = MagicMock()
            mock_api.get.side_effect = Exception("Test error")
            mock_get_api.return_value = mock_api
            
            response = test_client.get("/api/v0/get/QmInvalidHash")
            assert response.status_code == 500
            
            data = response.json()
            assert "detail" in data
            assert "error" in data["detail"].lower()

# Test API Initialization
class TestAPIInitialization:
    
    def test_app_initialization(self):
        """Test app initialization."""
        assert app is not None
        
        # Verify routes are registered
        routes = [route.path for route in app.routes]
        assert "/health" in routes
        assert "/api/v0/add" in routes or "/api/v0/add/" in routes
        assert any(route.startswith("/api/v0/get/") for route in routes)
    
    def test_api_config(self):
        """Test API configuration."""
        with patch('ipfs_kit_py.api.server.load_config') as mock_load_config:
            mock_load_config.return_value = {"api": {"host": "localhost", "port": 8000}}
            
            from ipfs_kit_py.api.server import get_config
            config = get_config()
            
            assert config is not None
            assert "api" in config
            assert config["api"]["host"] == "localhost"
            assert config["api"]["port"] == 8000

if __name__ == "__main__":
    pytest.main(["-v", __file__])
