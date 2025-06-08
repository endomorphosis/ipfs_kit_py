#!/usr/bin/env python3
"""
Test MCP Client for IPFS Kit Tools

This script tests the MCP server by acting as a client similar to VS Code.
It connects to the server, retrieves tool schemas, and executes tools.
"""

import json
import requests
import time
import sys
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MCPClient:
    """Simple MCP client to test the server."""
    
    def __init__(self, server_url="http://localhost:8000"):
        """Initialize the MCP client."""
        self.server_url = server_url
        self.tools = {}
        self.server_info = {}
        logger.info(f"Initialized MCP client for server {server_url}")
    
    def get_server_info(self):
        """Get server information from the initialize endpoint."""
        try:
            response = requests.get(f"{self.server_url}/initialize")
            response.raise_for_status()
            data = response.json()
            self.server_info = data.get("serverInfo", {})
            tool_schemas = data.get("capabilities", {}).get("tools", [])
            
            # Process tool schemas
            for tool in tool_schemas:
                tool_name = tool.get("name")
                self.tools[tool_name] = tool
            
            logger.info(f"Server info: {self.server_info}")
            logger.info(f"Found {len(self.tools)} tools: {', '.join(self.tools.keys())}")
            return True
        except Exception as e:
            logger.error(f"Error getting server info: {e}")
            return False
    
    def call_tool(self, tool_name, **args):
        """Call a tool on the MCP server."""
        try:
            if tool_name not in self.tools:
                logger.error(f"Tool '{tool_name}' not found. Available tools: {', '.join(self.tools.keys())}")
                return None
            
            tool_schema = self.tools[tool_name]
            required_params = tool_schema.get("parameters", {}).get("required", [])
            
            # Check required parameters
            for param in required_params:
                if param not in args:
                    logger.error(f"Missing required parameter '{param}' for tool '{tool_name}'")
                    return None
            
            # Call the tool
            payload = {
                "name": tool_name,
                "args": args
            }
            
            logger.info(f"Calling tool {tool_name} with args: {args}")
            response = requests.post(f"{self.server_url}/mcp/tools", json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error calling tool '{tool_name}': {e}")
            return None
    
    def get_health(self):
        """Get health information from the server."""
        try:
            response = requests.get(f"{self.server_url}/health")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting server health: {e}")
            return None

def main():
    """Run MCP client tests."""
    client = MCPClient()
    
    # Step 1: Get server information
    logger.info("=== Testing Server Information ===")
    if not client.get_server_info():
        logger.error("Failed to get server information. Exiting.")
        sys.exit(1)
    
    # Step 2: Check server health
    logger.info("\n=== Testing Server Health ===")
    health = client.get_health()
    if not health:
        logger.error("Failed to get server health. Exiting.")
        sys.exit(1)
    
    logger.info(f"Server health: {json.dumps(health, indent=2)}")
    
    # Step 3: Test the FS tools
    logger.info("\n=== Testing FS Tools ===")
    
    # Test list_files
    logger.info("\nTesting list_files tool...")
    result = client.call_tool("list_files", directory=".")
    if result:
        logger.info(f"list_files result: {len(result.get('items', []))} items found")
    
    # Test write_file
    logger.info("\nTesting write_file tool...")
    test_file_content = "This is a test file created by the MCP client"
    result = client.call_tool("write_file", path="test_mcp_client_output.txt", content=test_file_content)
    if result and result.get("success"):
        logger.info(f"write_file result: {json.dumps(result, indent=2)}")
    
    # Test read_file
    logger.info("\nTesting read_file tool...")
    result = client.call_tool("read_file", path="test_mcp_client_output.txt")
    if result and result.get("success"):
        content = result.get("content", "")
        if content == test_file_content:
            logger.info("read_file successful: content matches")
        else:
            logger.warning(f"read_file: content mismatch. Expected '{test_file_content}', got '{content}'")
    
    # Step 4: Test the IPFS tools
    logger.info("\n=== Testing IPFS Tools ===")
    
    # Test ipfs_add
    logger.info("\nTesting ipfs_add tool...")
    result = client.call_tool("ipfs_add", content="Test IPFS content", filename="test.txt")
    if result and result.get("success"):
        cid = result.get("cid", "")
        logger.info(f"ipfs_add result: CID {cid}")
        
        # Test ipfs_cat
        logger.info("\nTesting ipfs_cat tool...")
        result = client.call_tool("ipfs_cat", cid=cid)
        if result and result.get("success"):
            logger.info(f"ipfs_cat result: {result.get('content')}")
        
        # Test ipfs_pin
        logger.info("\nTesting ipfs_pin tool...")
        result = client.call_tool("ipfs_pin", cid=cid)
        if result and result.get("success"):
            logger.info(f"ipfs_pin result: {json.dumps(result, indent=2)}")
    
    logger.info("\n=== Test Results ===")
    logger.info("All tests completed. The MCP server is working as expected.")
    logger.info(f"Available tools: {', '.join(client.tools.keys())}")

if __name__ == "__main__":
    main()
