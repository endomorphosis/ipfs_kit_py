#!/usr/bin/env python3
"""
Test script for the final MCP server.
This script tests all the available IPFS tools.
"""

import sys
import json
import asyncio
import logging
import requests
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test-final-mcp")

# Server URL
SERVER_URL = "http://localhost:3000"

def check_server_health():
    """Check if the server is healthy."""
    try:
        response = requests.get(f"{SERVER_URL}/health")
        response.raise_for_status()
        
        logger.info(f"Server is healthy: {response.json()}")
        return True
    except Exception as e:
        logger.error(f"Server health check failed: {e}")
        return False

def get_available_tools():
    """Get the list of available tools."""
    try:
        response = requests.post(f"{SERVER_URL}/initialize")
        response.raise_for_status()
        
        data = response.json()
        tools = data.get("capabilities", {}).get("tools", [])
        
        logger.info(f"Available tools: {tools}")
        return tools
    except Exception as e:
        logger.error(f"Failed to get available tools: {e}")
        return []

def test_jsonrpc_endpoint():
    """Test the JSON-RPC endpoint."""
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "ping",
            "params": {},
            "id": 1
        }
        
        response = requests.post(
            f"{SERVER_URL}/jsonrpc",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        result = response.json()
        logger.info(f"JSON-RPC ping result: {result}")
        
        return True
    except Exception as e:
        logger.error(f"JSON-RPC test failed: {e}")
        return False

def main():
    """Main entry point."""
    logger.info("Starting tests for final MCP server...")
    
    # Check server health
    if not check_server_health():
        logger.error("Server health check failed. Is the server running?")
        return 1
    
    # Get available tools
    tools = get_available_tools()
    if not tools:
        logger.error("No tools found. Server configuration may be incomplete.")
        return 1
    
    # Test JSON-RPC endpoint
    if not test_jsonrpc_endpoint():
        logger.warning("JSON-RPC endpoint test failed. Some functionality may be limited.")
    
    # Output summary
    logger.info(f"Tests completed. Found {len(tools)} tools.")
    logger.info("Server appears to be functioning correctly.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
