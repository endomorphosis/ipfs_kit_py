#!/usr/bin/env python3
"""
Simplified Test Script for IPFS MCP Tools

This script tests the basic functionality of the IPFS tools
registered with the MCP server.
"""

import os
import sys
import json
import requests
import time
import logging
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ipfs-mcp-basic-test")

# MCP Server configuration
MCP_HOST = "localhost"
MCP_PORT = 9998
MCP_URL = f"http://{MCP_HOST}:{MCP_PORT}"
JSONRPC_URL = f"{MCP_URL}/jsonrpc"
HEALTH_URL = f"{MCP_URL}/health"
TIMEOUT = 10  # seconds

def check_server_health():
    """Check if the MCP server is healthy and ready to accept requests"""
    try:
        logger.info(f"Checking server health at {HEALTH_URL}")
        response = requests.get(HEALTH_URL, timeout=TIMEOUT)
        
        if response.status_code != 200:
            logger.error(f"Server returned non-200 status: {response.status_code}")
            logger.error(f"Response content: {response.text}")
            return False
        
        # Check server health info
        try:
            health_data = response.json()
            logger.info(f"Server health: {health_data}")
            
            # Verify that server has tools
            tools_count = health_data.get("tools_count", 0)
            if tools_count == 0:
                logger.warning("Server has no tools registered")
                return False
            
            # Check if IPFS tools are registered
            tool_categories = health_data.get("registered_tool_categories", [])
            if "ipfs_tools" not in tool_categories:
                logger.warning(f"IPFS tools category not registered. Available categories: {tool_categories}")
                return False
            
            logger.info(f"Server is healthy with {tools_count} tools registered")
            logger.info(f"Available tool categories: {tool_categories}")
            return True
            
        except Exception as e:
            logger.error(f"Error parsing health data: {e}")
            return False
            
    except requests.RequestException as e:
        logger.error(f"Error connecting to server: {e}")
        return False

def get_tools():
    """Get the list of available tools from the server"""
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "get_tools",
            "params": {},
            "id": int(time.time() * 1000)
        }
        
        response = requests.post(
            JSONRPC_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT
        )
        
        if response.status_code != 200:
            logger.error(f"Server returned non-200 status: {response.status_code}")
            logger.error(f"Response content: {response.text}")
            return None
        
        # Parse response
        data = response.json()
        if "error" in data:
            logger.error(f"JSON-RPC error: {data['error']}")
            return None
        
        result = data.get("result")
        return result
    
    except Exception as e:
        logger.error(f"Error getting tools: {e}")
        return None

def jsonrpc_call(method, params=None):
    """Make a JSON-RPC call to the MCP server"""
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": int(time.time() * 1000)
        }
        
        logger.info(f"Calling method '{method}' with params: {params}")
        
        response = requests.post(
            JSONRPC_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT
        )
        
        if response.status_code != 200:
            logger.error(f"Server returned non-200 status: {response.status_code}")
            logger.error(f"Response content: {response.text}")
            return None
        
        # Parse response
        data = response.json()
        if "error" in data:
            logger.error(f"JSON-RPC error: {data['error']}")
            return None
        
        result = data.get("result")
        return result
    
    except Exception as e:
        logger.error(f"Error making JSON-RPC call: {e}")
        return None

def test_ping():
    """Test the ping method"""
    logger.info("Testing ping method")
    result = jsonrpc_call("ping")
    if result == "pong":
        logger.info("✅ Ping successful")
        return True
    else:
        logger.error(f"❌ Ping failed, got: {result}")
        return False

def test_ipfs_add_cat():
    """Test adding and retrieving content to/from IPFS"""
    logger.info("Testing ipfs_add and ipfs_cat methods")
    
    # Test content
    test_content = "Hello IPFS MCP World!"
    
    # Add content to IPFS
    logger.info(f"Adding content to IPFS: '{test_content}'")
    add_result = jsonrpc_call("ipfs_add", {"content": test_content})
    
    if not add_result or "cid" not in add_result:
        logger.error(f"❌ ipfs_add failed, result: {add_result}")
        return False
    
    cid = add_result["cid"]
    logger.info(f"Content added with CID: {cid}")
    
    # Retrieve content from IPFS
    logger.info(f"Retrieving content for CID: {cid}")
    cat_result = jsonrpc_call("ipfs_cat", {"cid": cid})
    
    if cat_result is None:
        logger.error("❌ ipfs_cat failed")
        return False
    
    # Compare retrieved content with original
    logger.info(f"Retrieved content: '{cat_result}'")
    if cat_result == test_content:
        logger.info("✅ Content matches original")
        return True
    else:
        logger.error(f"❌ Content doesn't match original")
        return False

def main():
    """Main test function"""
    success = True
    
    # Check server health
    logger.info("Starting IPFS MCP basic test")
    if not check_server_health():
        logger.error("Server health check failed")
        return False
    
    # Get available tools
    tools = get_tools()
    if not tools:
        logger.error("Failed to get tools")
        return False
    
    # Check for IPFS tools
    ipfs_tools = [t for t in tools if t["name"].startswith("ipfs_")]
    logger.info(f"Found {len(ipfs_tools)} IPFS tools:")
    for tool in ipfs_tools:
        logger.info(f"  - {tool['name']}: {tool['description']}")
    
    if not ipfs_tools:
        logger.error("No IPFS tools found")
        return False
    
    # Run ping test
    if not test_ping():
        logger.error("Ping test failed")
        success = False
    
    # Check if ipfs_add and ipfs_cat are available
    ipfs_add_available = any(t["name"] == "ipfs_add" for t in tools)
    ipfs_cat_available = any(t["name"] == "ipfs_cat" for t in tools)
    
    if ipfs_add_available and ipfs_cat_available:
        # Run IPFS add/cat test
        if not test_ipfs_add_cat():
            logger.error("IPFS add/cat test failed")
            success = False
    else:
        logger.warning("ipfs_add and/or ipfs_cat not available, skipping test")
    
    # Report overall status
    if success:
        logger.info("✅ All tests passed!")
    else:
        logger.error("❌ Some tests failed")
    
    return success

if __name__ == "__main__":
    try:
        if main():
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        traceback.print_exc()
        sys.exit(2)
