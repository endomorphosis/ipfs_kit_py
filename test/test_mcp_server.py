#!/usr/bin/env python3
"""
Tests for the MCP (Model-Controller-Persistence) server implementation.

These tests verify that:
1. The MCP server initializes correctly
2. Models properly encapsulate business logic
3. Controllers correctly handle HTTP requests
4. The persistence layer properly caches data
5. Debug and isolation modes work as expected
6. Integration with FastAPI works correctly
"""

import os
import sys
import json
import time
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Ensure ipfs_kit_py is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Try to import FastAPI
try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("FastAPI not available, skipping HTTP tests")

# Import MCP server and components
try:
    from ipfs_kit_py.mcp import MCPServer
    from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
    from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
    from ipfs_kit_py.mcp.persistence.cache_manager import CacheManager
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("MCP server not available, skipping tests")

@unittest.skipIf(not MCP_AVAILABLE, "MCP server not available")
class TestMCPServer(unittest.TestCase):
    """Tests for the MCP server implementation."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a temp directory for the cache
        self.temp_dir = tempfile.mkdtemp(prefix="ipfs_mcp_test_")
        
        # Mock the IPFS API
        self.mock_ipfs_api = MagicMock(spec=IPFSSimpleAPI)
        
        # Setup mock responses
        self.mock_ipfs_api.add.return_value = {
            "success": True,
            "cid": "QmTest123",
            "size": 123
        }
        self.mock_ipfs_api.cat.return_value = b"Test content"
        self.mock_ipfs_api.pin.return_value = {"success": True}
        self.mock_ipfs_api.unpin.return_value = {"success": True}
        self.mock_ipfs_api.list_pins.return_value = {
            "success": True,
            "pins": ["QmTest123", "QmTest456"]
        }
        
        # Initialize the MCP server
        self.mcp_server = MCPServer(
            debug_mode=True,
            isolation_mode=True,
            ipfs_api=self.mock_ipfs_api,
            cache_dir=self.temp_dir,
            memory_cache_size=10 * 1024 * 1024,  # 10MB
            disk_cache_size=50 * 1024 * 1024,  # 50MB
        )
    
    def tearDown(self):
        """Clean up after each test."""
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_mcp_server_initialization(self):
        """Test that the MCP server initializes correctly."""
        # Verify that all components are initialized
        self.assertTrue(hasattr(self.mcp_server, "models"))
        self.assertTrue(hasattr(self.mcp_server, "controllers"))
        self.assertTrue(hasattr(self.mcp_server, "persistence"))
        
        # Verify that the IPFS model is initialized
        self.assertIn("ipfs", self.mcp_server.models)
        self.assertIsInstance(self.mcp_server.models["ipfs"], IPFSModel)
        
        # Verify that debug mode is enabled
        self.assertTrue(self.mcp_server.debug_mode)
        
        # Verify that isolation mode is enabled
        self.assertTrue(self.mcp_server.isolation_mode)
    
    def test_ipfs_model(self):
        """Test the IPFS model operations."""
        ipfs_model = self.mcp_server.models["ipfs"]
        
        # Test adding content
        content = b"Test content"
        result = ipfs_model.add_content(content)
        self.assertTrue(result["success"])
        self.assertEqual(result["cid"], "QmTest123")
        
        # Test getting content
        content_result = ipfs_model.get_content("QmTest123")
        self.assertEqual(content_result, b"Test content")
        
        # Test pinning content
        pin_result = ipfs_model.pin_content("QmTest123")
        self.assertTrue(pin_result["success"])
        
        # Test unpinning content
        unpin_result = ipfs_model.unpin_content("QmTest123")
        self.assertTrue(unpin_result["success"])
        
        # Test listing pins
        pins_result = ipfs_model.list_pins()
        self.assertTrue(pins_result["success"])
        self.assertIn("QmTest123", pins_result["pins"])
        
        # Test getting stats
        stats = ipfs_model.get_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn("operations", stats)
        self.assertIn("success_count", stats)
        self.assertIn("error_count", stats)
    
    def test_cache_manager(self):
        """Test the cache manager operations."""
        cache_manager = self.mcp_server.persistence
        
        # Test putting content in the cache
        cache_manager.put("test_key", b"Test value", metadata={"size": 10})
        
        # Test getting content from the cache
        value = cache_manager.get("test_key")
        self.assertEqual(value, b"Test value")
        
        # Test cache info
        cache_info = cache_manager.get_cache_info()
        self.assertIsInstance(cache_info, dict)
        self.assertIn("memory_cache", cache_info)
        self.assertIn("disk_cache", cache_info)
        
        # Test cache stats
        self.assertIn("items", cache_info["memory_cache"])
        self.assertIn("size", cache_info["memory_cache"])
        self.assertIn("hit_count", cache_info["memory_cache"])
        self.assertIn("miss_count", cache_info["memory_cache"])
        
        # Test deleting from cache
        cache_manager.delete("test_key")
        self.assertIsNone(cache_manager.get("test_key"))
    
    def test_debug_operations(self):
        """Test the debug operations."""
        # Perform some operations to generate debug info
        ipfs_model = self.mcp_server.models["ipfs"]
        ipfs_model.add_content(b"Debug test content")
        ipfs_model.get_content("QmTest123")
        
        # Get operation log
        operations = self.mcp_server.get_operation_log()
        self.assertIsInstance(operations, list)
        self.assertGreaterEqual(len(operations), 2)  # At least 2 operations
        
        # Check operation log format
        op = operations[0]
        self.assertIn("timestamp", op)
        self.assertIn("operation", op)
        self.assertIn("success", op)
        
        # Get debug state
        debug_state = self.mcp_server.get_debug_state()
        self.assertIsInstance(debug_state, dict)
        self.assertIn("server_info", debug_state)
        self.assertIn("models", debug_state)
        self.assertIn("persistence", debug_state)
        
        # Check cache info in debug state
        self.assertIn("cache_info", debug_state["persistence"])

@unittest.skipIf(not MCP_AVAILABLE or not FASTAPI_AVAILABLE, "MCP server or FastAPI not available")
class TestMCPServerHTTP(unittest.TestCase):
    """Tests for the MCP server HTTP integration with FastAPI."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a temp directory for the cache
        self.temp_dir = tempfile.mkdtemp(prefix="ipfs_mcp_http_test_")
        
        # Mock the IPFS API
        self.mock_ipfs_api = MagicMock(spec=IPFSSimpleAPI)
        
        # Setup mock responses
        self.mock_ipfs_api.add.return_value = {
            "success": True,
            "cid": "QmTest123",
            "size": 123
        }
        self.mock_ipfs_api.cat.return_value = b"Test content"
        self.mock_ipfs_api.pin.return_value = {"success": True}
        self.mock_ipfs_api.unpin.return_value = {"success": True}
        self.mock_ipfs_api.list_pins.return_value = {
            "success": True,
            "pins": ["QmTest123", "QmTest456"]
        }
        
        # Create a FastAPI app
        self.app = FastAPI()
        
        # Initialize the MCP server
        self.mcp_server = MCPServer(
            debug_mode=True,
            isolation_mode=True,
            ipfs_api=self.mock_ipfs_api,
            cache_dir=self.temp_dir,
            memory_cache_size=10 * 1024 * 1024,  # 10MB
            disk_cache_size=50 * 1024 * 1024,  # 50MB
        )
        
        # Register the MCP server with the FastAPI app
        self.mcp_server.register_with_app(self.app, prefix="/api/v0/mcp")
        
        # Create a test client
        self.client = TestClient(self.app)
    
    def tearDown(self):
        """Clean up after each test."""
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_health_endpoint(self):
        """Test the health endpoint."""
        response = self.client.get("/api/v0/mcp/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("status", data)
        self.assertEqual(data["status"], "ok")
    
    def test_debug_endpoint(self):
        """Test the debug endpoint."""
        response = self.client.get("/api/v0/mcp/debug")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("server_info", data)
        self.assertIn("models", data)
        self.assertIn("persistence", data)
    
    def test_operations_endpoint(self):
        """Test the operations endpoint."""
        response = self.client.get("/api/v0/mcp/operations")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("operations", data)
        self.assertIsInstance(data["operations"], list)
    
    def test_ipfs_add_endpoint(self):
        """Test the IPFS add endpoint."""
        # Create a test file
        files = {"file": ("test.txt", b"Test content")}
        response = self.client.post("/api/v0/mcp/ipfs/add", files=files)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["cid"], "QmTest123")
    
    def test_ipfs_get_endpoint(self):
        """Test the IPFS get endpoint."""
        response = self.client.get("/api/v0/mcp/ipfs/get/QmTest123")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"Test content")
    
    def test_ipfs_pin_endpoint(self):
        """Test the IPFS pin endpoint."""
        response = self.client.post("/api/v0/mcp/ipfs/pin/QmTest123")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
    
    def test_ipfs_unpin_endpoint(self):
        """Test the IPFS unpin endpoint."""
        response = self.client.delete("/api/v0/mcp/ipfs/unpin/QmTest123")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
    
    def test_ipfs_pins_endpoint(self):
        """Test the IPFS pins endpoint."""
        response = self.client.get("/api/v0/mcp/ipfs/pins")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("pins", data)
        self.assertIsInstance(data["pins"], list)

if __name__ == "__main__":
    unittest.main()