#!/usr/bin/env python3
"""
Test Script for Comprehensive IPFS MCP Server

This script tests the functionality of the comprehensive MCP server,
verifying various components and tool registrations.
"""

import sys
import json
import time
import logging
import requests
import unittest
import subprocess
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp-tester")

# Server config
SERVER_URL = "http://localhost:3000"
JSONRPC_ENDPOINT = f"{SERVER_URL}/jsonrpc"
HEALTH_ENDPOINT = f"{SERVER_URL}/health"
API_ENDPOINT = f"{SERVER_URL}/api"

class ComprehensiveMCPServerTest(unittest.TestCase):
    """Test suite for the Comprehensive MCP Server."""
    
    @classmethod
    def setUpClass(cls):
        """Start the server before running tests."""
        logger.info("Setting up test environment...")
        try:
            # Check if server is already running
            response = requests.get(HEALTH_ENDPOINT, timeout=1)
            if response.status_code == 200:
                logger.info("Server is already running")
                return
        except requests.RequestException:
            # Server is not running, start it
            logger.info("Starting MCP server...")
            try:
                subprocess.Popen(["./start_comprehensive_mcp_server.sh"], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE)
                # Give it time to start
                time.sleep(3)
            except Exception as e:
                logger.error(f"Error starting server: {e}")
                raise
    
    @classmethod
    def tearDownClass(cls):
        """Stop the server after tests complete."""
        logger.info("Cleaning up test environment...")
        try:
            subprocess.Popen(["./stop_comprehensive_mcp_server.sh"], 
                           stdout=subprocess.PIPE, 
                           stderr=subprocess.PIPE)
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error stopping server: {e}")
    
    def test_01_server_health(self):
        """Test server health endpoint."""
        logger.info("Testing server health...")
        try:
            response = requests.get(HEALTH_ENDPOINT, timeout=5)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "healthy")
            logger.info("Server health check passed")
        except requests.RequestException as e:
            self.fail(f"Server health check failed: {e}")
    
    def test_02_system_info(self):
        """Test system info tool."""
        logger.info("Testing system info tool...")
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "execute_tool",
                "params": {
                    "tool_name": "system_info",
                    "args": {}
                },
                "id": 1
            }
            response = requests.post(JSONRPC_ENDPOINT, json=payload, timeout=5)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("result", data)
            result = data["result"]
            self.assertIn("status", result)
            self.assertEqual(result["status"], "success")
            self.assertIn("result", result)
            info = result["result"]
            self.assertIn("version", info)
            self.assertIn("tool_count", info)
            self.assertIn("tool_categories", info)
            logger.info(f"System info: {json.dumps(info, indent=2)}")
        except requests.RequestException as e:
            self.fail(f"System info test failed: {e}")
    
    def test_03_echo_tool(self):
        """Test the echo tool."""
        logger.info("Testing echo tool...")
        test_message = "Hello, Comprehensive MCP Server!"
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "execute_tool",
                "params": {
                    "tool_name": "echo",
                    "args": {"message": test_message}
                },
                "id": 1
            }
            response = requests.post(JSONRPC_ENDPOINT, json=payload, timeout=5)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("result", data)
            result = data["result"]
            self.assertIn("status", result)
            self.assertEqual(result["status"], "success")
            self.assertIn("result", result)
            echo_result = result["result"]
            self.assertIn("message", echo_result)
            self.assertEqual(echo_result["message"], test_message)
            logger.info(f"Echo test passed: {echo_result}")
        except requests.RequestException as e:
            self.fail(f"Echo tool test failed: {e}")
    
    def test_04_check_tool_categories(self):
        """Test the availability of tool categories."""
        logger.info("Testing tool categories...")
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "execute_tool",
                "params": {
                    "tool_name": "system_info",
                    "args": {}
                },
                "id": 1
            }
            response = requests.post(JSONRPC_ENDPOINT, json=payload, timeout=5)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("result", data)
            result = data["result"]
            self.assertIn("result", result)
            info = result["result"]
            self.assertIn("tool_categories", info)
            
            # Check that we have at least some of the expected categories
            expected_categories = ["System", "Utility", "IPFS", "FileSystem", "Network", "Storage"]
            categories = info["tool_categories"]
            for category in expected_categories:
                self.assertIn(category, categories)
                logger.info(f"Category '{category}' has {categories[category]} tools")
        except requests.RequestException as e:
            self.fail(f"Tool categories test failed: {e}")

if __name__ == "__main__":
    unittest.main(verbosity=2)
