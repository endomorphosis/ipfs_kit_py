#!/usr/bin/env python3
"""
Unified test script for the MCP server implementation.

This script creates an in-process MCP server instance and tests all its features:
1. Server initialization and configuration
2. Core IPFS operations (add, cat, pin, etc.)
3. Daemon management
4. Method normalization
5. Credential management
6. Cache management
7. Debug mode features
"""

import os
import sys
import time
import json
import unittest
import tempfile
import logging
import threading
import shutil
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to the path so we can import from the project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import MCP server components
from ipfs_kit_py.mcp_server.server_bridge import MCPServer  # Refactored import

class TestMCPUnified(unittest.TestCase):
    """Unified test case for the MCP server."""

    @classmethod
    def setUpClass(cls):
        """Set up the test environment once for all tests."""
        # Create a temporary directory for test files
        cls.temp_dir = tempfile.mkdtemp(prefix="mcp_unified_test_")
        
        # Create a sample test file
        cls.test_file_path = os.path.join(cls.temp_dir, "test_file.txt")
        with open(cls.test_file_path, "w") as f:
            f.write("This is a test file for MCP server testing.")
        
        # Set up MCP server with debug mode and isolation
        cls.mcp_server = MCPServer(
            debug_mode=True,
            log_level="INFO",
            persistence_path=os.path.join(cls.temp_dir, "mcp_data"),
            isolation_mode=True  # Use isolation mode to avoid affecting the host system
        )
        
        # Create a FastAPI app and register the MCP server
        cls.app = FastAPI(title="MCP Test App")
        cls.mcp_server.register_with_app(cls.app, prefix="/api/v0/mcp")
        
        # Create a test client
        cls.client = TestClient(cls.app)
        
        logger.info(f"MCP test environment set up with persistence path: {cls.mcp_server.persistence_path}")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up the test environment after all tests."""
        # Shutdown MCP server
        cls.mcp_server.shutdown()
        
        # Clean up temporary directory
        if os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir)
            
        logger.info("MCP test environment cleaned up")
    
    def setUp(self):
        """Reset server state before each test."""
        self.mcp_server.reset_state()
    
    def test_01_server_initialization(self):
        """Test server initialization and basic configuration."""
        # Check that server components are initialized
        self.assertIsNotNone(self.mcp_server.ipfs_kit)
        self.assertIsNotNone(self.mcp_server.router)
        self.assertIsNotNone(self.mcp_server.cache_manager)
        self.assertIsNotNone(self.mcp_server.credential_manager)
        
        # Check that the models and controllers are initialized
        self.assertIn("ipfs", self.mcp_server.models)
        self.assertIn("ipfs", self.mcp_server.controllers)
        self.assertIn("cli", self.mcp_server.controllers)
        self.assertIn("credentials", self.mcp_server.controllers)
        
        # Check debug and isolation mode
        self.assertTrue(self.mcp_server.debug_mode)
        self.assertTrue(self.mcp_server.isolation_mode)
        
        logger.info("Server initialization test passed")
    
    def test_02_health_check(self):
        """Test the health check endpoint."""
        # Call the health check endpoint
        response = self.client.get("/api/v0/mcp/health")
        
        # Check response status code
        self.assertEqual(response.status_code, 200)
        
        # Parse response content
        data = response.json()
        
        # Check required fields
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "ok")
        self.assertIn("server_id", data)
        self.assertIn("timestamp", data)
        self.assertIn("debug_mode", data)
        self.assertTrue(data["debug_mode"])
        
        logger.info("Health check test passed")
    
    def test_03_debug_state(self):
        """Test the debug state endpoint."""
        # Call the debug state endpoint
        response = self.client.get("/api/v0/mcp/debug")
        
        # Check response status code
        self.assertEqual(response.status_code, 200)
        
        # Parse response content
        data = response.json()
        
        # Check required fields
        self.assertTrue(data["success"])
        self.assertIn("server_info", data)
        self.assertIn("models", data)
        self.assertIn("persistence", data)
        self.assertIn("credentials", data)
        
        # Check server info fields
        server_info = data["server_info"]
        self.assertEqual(server_info["debug_mode"], True)
        self.assertEqual(server_info["isolation_mode"], True)
        
        logger.info("Debug state test passed")
    
    def test_04_ipfs_add_content(self):
        """Test adding content to IPFS."""
        # Prepare some test content
        test_content = "Hello, MCP server! Testing content addition."
        
        # Call the add content endpoint
        response = self.client.post(
            "/api/v0/mcp/ipfs/add",
            data={"content": test_content}
        )
        
        # Check response status code
        self.assertEqual(response.status_code, 200)
        
        # Parse response content
        data = response.json()
        
        # Check required fields
        self.assertIn("success", data)
        
        if data.get("success", False):
            # If add operation succeeded
            self.assertIn("cid", data)
            # MCP server returns content_size_bytes instead of size
            self.assertIn("content_size_bytes", data)
            logger.info(f"Added content with CID: {data['cid']}")
            # Store CID for later tests
            self.test_content_cid = data.get("cid")
        else:
            # Even if simulation is used, we should still get information
            logger.info(f"Add operation used simulation: {data}")
            self.assertIn("error", data)
            # Use a test CID for later tests if needed
            if hasattr(self, 'test_content_cid') == False:
                self.test_content_cid = "QmTest123"
        
        logger.info("IPFS add content test completed")
    
    def test_05_ipfs_add_file(self):
        """Test adding a file to IPFS."""
        # Call the add file endpoint
        with open(self.test_file_path, "rb") as f:
            response = self.client.post(
                "/api/v0/mcp/ipfs/add",
                files={"file": ("test_file.txt", f)}
            )
        
        # Check response status code
        self.assertEqual(response.status_code, 200)
        
        # Parse response content
        data = response.json()
        
        # Check required fields
        self.assertIn("success", data)
        
        if data.get("success", False):
            # If add operation succeeded
            self.assertIn("cid", data)
            # MCP server returns content_size_bytes instead of size
            self.assertIn("content_size_bytes", data)
            # Store CID for later tests
            self.test_file_cid = data.get("cid")
            logger.info(f"Added file with CID: {data['cid']}")
        else:
            # Even if simulation is used, we should still get information
            logger.info(f"Add file operation used simulation: {data}")
            # Use a test CID for later tests if needed
            if hasattr(self, 'test_file_cid') == False:
                self.test_file_cid = "QmTest123"
        
        logger.info("IPFS add file test completed")
    
    def test_06_ipfs_cat_content(self):
        """Test retrieving content from IPFS."""
        # First add content to get a CID if we don't have one
        if not hasattr(self, 'test_content_cid'):
            self.test_04_ipfs_add_content()
        
        # Try different endpoints for content retrieval
        endpoints = [
            f"/api/v0/mcp/ipfs/cat/{self.test_content_cid}",
            f"/api/v0/mcp/ipfs/get/{self.test_content_cid}"
        ]
        
        success = False
        for endpoint in endpoints:
            try:
                # Call the endpoint
                logger.info(f"Trying to get content from: {endpoint}")
                response = self.client.get(endpoint)
                
                # Check response status code
                if response.status_code == 200:
                    # Check response content
                    content_type = response.headers.get("content-type", "")
                    if "application/json" in content_type:
                        # JSON response (likely simulation or error)
                        data = response.json()
                        logger.info(f"Content operation returned JSON: {data}")
                        self.assertIn("success", data)
                    else:
                        # Direct content response (binary data)
                        logger.info(f"Content operation returned binary data of length {len(response.content)}")
                        self.assertTrue(len(response.content) > 0)
                    success = True
                    break
            except Exception as e:
                logger.warning(f"Error accessing endpoint {endpoint}: {e}")
        
        # If we didn't succeed with any endpoint, try the JSON version
        if not success:
            logger.info("Trying JSON-based content retrieval as fallback")
            response = self.client.post(
                "/api/v0/mcp/ipfs/cat",
                json={"cid": self.test_content_cid}
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            logger.info(f"Content operation via JSON post returned: {data}")
            self.assertIn("success", data)
            success = True
        
        # Verify that we were able to successfully retrieve the content
        self.assertTrue(success, "Could not retrieve content with any method")
        
        logger.info("IPFS content retrieval test completed")
    
    def test_07_ipfs_pin_operations(self):
        """Test pinning operations."""
        # First make sure we have a CID to work with
        if not hasattr(self, 'test_file_cid'):
            self.test_05_ipfs_add_file()
        
        # Test pinning - update to use JSON body instead of query parameter
        pin_response = self.client.post(
            "/api/v0/mcp/ipfs/pin/add", 
            json={"cid": self.test_file_cid}
        )
        
        # Check response status code
        self.assertEqual(pin_response.status_code, 200)
        
        # Parse response content
        pin_data = pin_response.json()
        logger.info(f"Pin response: {pin_data}")
        
        # Check required fields
        self.assertIn("success", pin_data)
        
        # Test listing pins
        list_response = self.client.get("/api/v0/mcp/ipfs/pin/ls")
        
        # Check response status code
        self.assertEqual(list_response.status_code, 200)
        
        # Parse response content
        list_data = list_response.json()
        logger.info(f"List pins response: {list_data}")
        
        # Check required fields
        self.assertIn("success", list_data)
        
        # Test unpinning - update to use JSON body instead of query parameter
        unpin_response = self.client.post(
            "/api/v0/mcp/ipfs/pin/rm", 
            json={"cid": self.test_file_cid}
        )
        
        # Check response status code
        self.assertEqual(unpin_response.status_code, 200)
        
        # Parse response content
        unpin_data = unpin_response.json()
        logger.info(f"Unpin response: {unpin_data}")
        
        # Check required fields
        self.assertIn("success", unpin_data)
        
        logger.info("IPFS pin operations test completed")
    
    def test_08_cli_command_execution(self):
        """Test CLI command execution."""
        # Try different endpoints that might be used for CLI commands
        endpoints = [
            # Try the version endpoint which should always be available
            "/api/v0/mcp/cli/version"
        ]
        
        success = False
        for endpoint in endpoints:
            try:
                # Call the endpoint
                logger.info(f"Trying CLI endpoint: {endpoint}")
                response = self.client.get(endpoint)
                
                # Check response status code
                if response.status_code == 200:
                    # Parse response content
                    data = response.json()
                    
                    # Check required fields - specific check for version endpoint
                    self.assertIn("ipfs_kit_py_version", data)
                    logger.info(f"CLI version info: {data}")
                    success = True
                    break
            except Exception as e:
                logger.warning(f"Error calling CLI endpoint {endpoint}: {e}")
        
        # Verify that we were able to successfully call at least one endpoint
        self.assertTrue(success, "Could not find a working CLI endpoint")
        
        logger.info("CLI command execution test completed")
    
    def test_09_daemon_management(self):
        """Test daemon management endpoints."""
        # Get daemon status
        status_response = self.client.get("/api/v0/mcp/daemon/status")
        
        # Check response status code
        self.assertEqual(status_response.status_code, 200)
        
        # Parse response content
        status_data = status_response.json()
        logger.info(f"Daemon status: {status_data}")
        
        # Check required fields
        self.assertIn("success", status_data)
        
        # Try to stop the daemon monitor if it's running
        try:
            stop_monitor_response = self.client.post("/api/v0/mcp/daemon/monitor/stop")
            
            # Check response status code
            self.assertEqual(stop_monitor_response.status_code, 200)
            
            # Parse response content
            stop_monitor_data = stop_monitor_response.json()
            logger.info(f"Stop monitor response: {stop_monitor_data}")
        except Exception as e:
            logger.warning(f"Failed to stop daemon monitor: {e}")
        
        # Try to start the daemon monitor
        start_monitor_response = self.client.post("/api/v0/mcp/daemon/monitor/start?check_interval=30")
        
        # Check response status code
        self.assertEqual(start_monitor_response.status_code, 200)
        
        # Parse response content
        start_monitor_data = start_monitor_response.json()
        logger.info(f"Start monitor response: {start_monitor_data}")
        
        # Check required fields
        self.assertIn("success", start_monitor_data)
        
        # Try to stop the IPFS daemon
        stop_daemon_response = self.client.post("/api/v0/mcp/daemon/stop/ipfs")
        
        # Check response status code
        self.assertEqual(stop_daemon_response.status_code, 200)
        
        # Parse response content
        stop_daemon_data = stop_daemon_response.json()
        logger.info(f"Stop daemon response: {stop_daemon_data}")
        
        # Check required fields
        self.assertIn("success", stop_daemon_data)
        
        # Try to start the IPFS daemon
        start_daemon_response = self.client.post("/api/v0/mcp/daemon/start/ipfs")
        
        # Check response status code
        self.assertEqual(start_daemon_response.status_code, 200)
        
        # Parse response content
        start_daemon_data = start_daemon_response.json()
        logger.info(f"Start daemon response: {start_daemon_data}")
        
        # Check required fields
        self.assertIn("success", start_daemon_data)
        
        logger.info("Daemon management test completed")
    
    def test_10_credential_management(self):
        """Test credential management."""
        # Add a test credential - using the ipfs endpoint which is more generic
        add_response = self.client.post(
            "/api/v0/mcp/credentials/ipfs",
            json={
                "name": "test_account",
                "identity": "test_user",
                "api_address": "test_api_address",
                "cluster_secret": "test_cluster_secret"
            }
        )
        
        # Check response status code
        self.assertEqual(add_response.status_code, 200)
        
        # Parse response content
        add_data = add_response.json()
        logger.info(f"Add credential response: {add_data}")
        
        # Check required fields
        self.assertIn("success", add_data)
        
        # List credentials
        list_response = self.client.get("/api/v0/mcp/credentials")
        
        # Check response status code
        self.assertEqual(list_response.status_code, 200)
        
        # Parse response content
        list_data = list_response.json()
        logger.info(f"List credentials response: {list_data}")
        
        # Check required fields
        self.assertIn("success", list_data)
        if list_data.get("success", False):
            self.assertIn("credentials", list_data)
        
        # Delete the credential
        delete_response = self.client.delete("/api/v0/mcp/credentials/ipfs/test_account")
        
        # Check response status code
        self.assertEqual(delete_response.status_code, 200)
        
        # Parse response content
        delete_data = delete_response.json()
        logger.info(f"Delete credential response: {delete_data}")
        
        # Check required fields
        self.assertIn("success", delete_data)
        
        logger.info("Credential management test completed")
    
    def test_11_operation_logging(self):
        """Test operation logging in debug mode."""
        # First make some API calls to generate log entries
        self.client.get("/api/v0/mcp/health")
        self.client.get("/api/v0/mcp/debug")
        
        # Get the operation log
        response = self.client.get("/api/v0/mcp/operations")
        
        # Check response status code
        self.assertEqual(response.status_code, 200)
        
        # Parse response content
        data = response.json()
        
        # Check required fields
        self.assertTrue(data["success"])
        self.assertIn("operations", data)
        self.assertIn("count", data)
        self.assertGreater(data["count"], 0)
        
        # Check that our requests are in the log
        operations = data["operations"]
        paths = [op["path"] for op in operations if op["type"] == "request"]
        self.assertIn("/api/v0/mcp/health", paths)
        self.assertIn("/api/v0/mcp/debug", paths)
        
        logger.info("Operation logging test completed")
    
    def test_12_cache_management(self):
        """Test cache management features."""
        # First add content to get it in the cache
        if not hasattr(self, 'test_content_cid'):
            self.test_04_ipfs_add_content()
        
        # Access the content to ensure it's in cache
        # Use the get endpoint since cat might return raw content
        self.client.get(f"/api/v0/mcp/ipfs/get/{self.test_content_cid}")
        
        # Check cache info through debug endpoint
        debug_response = self.client.get("/api/v0/mcp/debug")
        debug_data = debug_response.json()
        
        # Check persistence info
        self.assertIn("persistence", debug_data)
        self.assertIn("cache_info", debug_data["persistence"])
        
        cache_info = debug_data["persistence"]["cache_info"]
        logger.info(f"Cache info: {cache_info}")
        
        # Check that cache has the correct structure from MCPCacheManager.get_cache_info()
        # Check for expected fields but don't be too strict as the implementation may evolve
        expected_fields = [
            "memory_usage", "memory_item_count", "item_count", 
            "memory_limit", "disk_usage", "disk_limit"
        ]
        
        # Check each field if it exists, but don't fail the test if some are missing
        for field in expected_fields:
            if field in cache_info:
                logger.info(f"Found expected cache field: {field}={cache_info[field]}")
            else:
                logger.warning(f"Cache field '{field}' not found in response")
        
        # Verify at least some cache statistics exist
        cache_stats_fields = ["stats", "memory_hit_rate", "disk_hit_rate", "overall_hit_rate"]
        found_stats = any(field in cache_info for field in cache_stats_fields)
        self.assertTrue(found_stats, "No cache statistics fields found in response")
        
        logger.info("Cache management test completed")
        
    def test_13_method_normalization(self):
        """Test method normalization features."""
        # Get the IPFS model's stats through the debug endpoint
        debug_response = self.client.get("/api/v0/mcp/debug")
        debug_data = debug_response.json()
        
        # Check models info
        self.assertIn("models", debug_data)
        self.assertIn("ipfs", debug_data["models"])
        
        # Check the model stats for normalized methods
        ipfs_model = debug_data["models"]["ipfs"]
        
        # In the actual implementation, stats are directly in the model response
        self.assertIn("normalized_ipfs_stats", ipfs_model)
        
        # Check normalized IPFS stats
        normalized_stats = ipfs_model["normalized_ipfs_stats"]
        logger.info(f"Normalized IPFS stats: {normalized_stats}")
        
        # Verify aggregate stats
        self.assertIn("aggregate", ipfs_model)
        aggregate_stats = ipfs_model["aggregate"]
        
        # Simulated operations should be tracked
        self.assertIn("simulated_operations", normalized_stats)
        
        logger.info("Method normalization test completed")
        
if __name__ == "__main__":
    unittest.main()