#!/usr/bin/env python3
"""
Test MCP Tools Script

This script tests each tool in the MCP proxy server to verify functionality.
"""

import os
import sys
import json
import logging
import asyncio
import requests
import tempfile
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MCP Proxy Server settings
MCP_SERVER_URL = "http://localhost:8000"
MCP_TOOLS_ENDPOINT = f"{MCP_SERVER_URL}/mcp/tools"
MCP_HEALTH_ENDPOINT = f"{MCP_SERVER_URL}/health"
MCP_INITIALIZE_ENDPOINT = f"{MCP_SERVER_URL}/initialize"

# Test data
TEST_DIR = "test_mcp_data"
TEST_FILE = os.path.join(TEST_DIR, "test_file.txt")
TEST_CONTENT = "This is a test file created by test_mcp_tools.py"
TEST_IPFS_CID = "QmTestCid"

def health_check():
    """Check the health of the MCP server."""
    try:
        response = requests.get(MCP_HEALTH_ENDPOINT)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Server health: {json.dumps(data, indent=2)}")
            return data
        else:
            logger.error(f"Health check failed with status code {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return None

def get_available_tools():
    """Get available tools from the server."""
    try:
        response = requests.get(MCP_INITIALIZE_ENDPOINT)
        if response.status_code == 200:
            data = response.json()
            if "capabilities" in data and "tools" in data["capabilities"]:
                tools = data["capabilities"]["tools"]
                logger.info(f"Available tools: {json.dumps(tools, indent=2)}")
                return tools
            else:
                logger.error("No tools found in capabilities")
                return []
        else:
            logger.error(f"Initialize request failed with status code {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Initialize request error: {e}")
        return []

def call_tool(tool_name, args=None):
    """Call a tool on the MCP server."""
    if args is None:
        args = {}

    try:
        data = {
            "name": tool_name,
            "args": args
        }

        response = requests.post(MCP_TOOLS_ENDPOINT, json=data)

        if response.status_code == 200:
            result = response.json()
            return True, result
        else:
            error = f"Tool call failed with status code {response.status_code}"
            try:
                error_data = response.json()
                error += f": {error_data.get('error', '')}"
            except:
                pass

            logger.error(error)
            return False, {"error": error}

    except Exception as e:
        error = f"Error calling tool {tool_name}: {e}"
        logger.error(error)
        return False, {"error": error}

def test_list_files():
    """Test the list_files tool."""
    logger.info("Testing list_files tool...")

    success, result = call_tool("list_files", {"directory": "."})

    if success:
        logger.info(f"list_files succeeded with {len(result.get('items', []))} items")
        return True
    else:
        logger.error(f"list_files failed: {result.get('error')}")
        return False

def test_write_file():
    """Test the write_file tool."""
    logger.info("Testing write_file tool...")

    # Ensure the test directory exists
    os.makedirs(TEST_DIR, exist_ok=True)

    success, result = call_tool("write_file", {
        "path": TEST_FILE,
        "content": TEST_CONTENT
    })

    if success:
        logger.info(f"write_file succeeded: {result}")
        return True
    else:
        logger.error(f"write_file failed: {result.get('error')}")
        return False

def test_read_file():
    """Test the read_file tool."""
    logger.info("Testing read_file tool...")

    success, result = call_tool("read_file", {
        "path": TEST_FILE
    })

    if success:
        content = result.get("content", "")
        if content == TEST_CONTENT:
            logger.info("read_file succeeded with correct content")
            return True
        else:
            logger.error(f"read_file returned incorrect content: {content}")
            return False
    else:
        logger.error(f"read_file failed: {result.get('error')}")
        return False

def test_ipfs_add():
    """Test the ipfs_add tool."""
    logger.info("Testing ipfs_add tool...")

    success, result = call_tool("ipfs_add", {
        "content": "Hello IPFS from test script",
        "filename": "test.txt",
        "pin": True
    })

    if success:
        logger.info(f"ipfs_add succeeded: {result}")
        return True, result.get("cid")
    else:
        logger.error(f"ipfs_add failed: {result.get('error')}")
        return False, None

def test_ipfs_cat(cid):
    """Test the ipfs_cat tool."""
    logger.info(f"Testing ipfs_cat tool with CID {cid}...")

    success, result = call_tool("ipfs_cat", {
        "cid": cid
    })

    if success:
        logger.info(f"ipfs_cat succeeded: {result}")
        return True
    else:
        logger.error(f"ipfs_cat failed: {result.get('error')}")
        return False

def test_ipfs_pin(cid):
    """Test the ipfs_pin tool."""
    logger.info(f"Testing ipfs_pin tool with CID {cid}...")

    success, result = call_tool("ipfs_pin", {
        "cid": cid,
        "recursive": True
    })

    if success:
        logger.info(f"ipfs_pin succeeded: {result}")
        return True
    else:
        logger.error(f"ipfs_pin failed: {result.get('error')}")
        return False

def run_tests():
    """Run all tests."""
    logger.info("Starting MCP tool tests...")

    # First check if the server is running
    health = health_check()
    if not health:
        logger.error("MCP server is not running or health check failed")
        return

    # Get available tools
    tools = get_available_tools()
    if not tools:
        logger.error("Failed to get available tools")
        return

    # Track test results
    results = {}

    # Test basic file tools
    if "list_files" in tools:
        results["list_files"] = test_list_files()

    if "write_file" in tools:
        results["write_file"] = test_write_file()

    if "read_file" in tools:
        results["read_file"] = test_read_file()

    # Test IPFS tools
    if "ipfs_add" in tools:
        success, cid = test_ipfs_add()
        results["ipfs_add"] = success

        if success and cid and "ipfs_cat" in tools:
            results["ipfs_cat"] = test_ipfs_cat(cid)

        if success and cid and "ipfs_pin" in tools:
            results["ipfs_pin"] = test_ipfs_pin(cid)

    # Clean up
    try:
        if os.path.exists(TEST_FILE):
            os.unlink(TEST_FILE)
        if os.path.exists(TEST_DIR) and not os.listdir(TEST_DIR):
            os.rmdir(TEST_DIR)
    except Exception as e:
        logger.warning(f"Cleanup error: {e}")

    # Print summary
    logger.info("\n=== Test Results ===")
    for tool, success in results.items():
        status = "PASSED" if success else "FAILED"
        logger.info(f"{tool}: {status}")

    # Overall result
    if all(results.values()):
        logger.info("All tests passed!")
    else:
        logger.error(f"{list(results.values()).count(False)} tests failed")

if __name__ == "__main__":
    run_tests()
