#!/usr/bin/env python3
"""
IPFS MCP Server Test Diagnostics

This script runs tests against the IPFS MCP server and provides detailed diagnostics.
It's helpful for diagnosing and fixing server issues.
"""

import os
import sys
import json
import logging
import requests
import traceback
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp-test-diagnostics")

# Constants
DEFAULT_PORT = 9998
DEFAULT_HOST = "localhost"
DEFAULT_TIMEOUT = 10  # seconds
JSON_INDENT = 2

def setup_test_env():
    """Set up the test environment variables."""
    test_env = {
        "host": os.environ.get("MCP_HOST", DEFAULT_HOST),
        "port": int(os.environ.get("MCP_PORT", DEFAULT_PORT)),
        "timeout": int(os.environ.get("MCP_TIMEOUT", DEFAULT_TIMEOUT)),
    }
    
    test_env["url"] = f"http://{test_env['host']}:{test_env['port']}"
    test_env["health_url"] = f"{test_env['url']}/health"
    test_env["jsonrpc_url"] = f"{test_env['url']}/jsonrpc"
    
    return test_env

def check_server_health(env):
    """Check if the server is healthy."""
    logger.info(f"Checking server health at {env['health_url']}")
    
    try:
        response = requests.get(env["health_url"], timeout=env["timeout"])
        
        if response.status_code == 200:
            health_data = response.json()
            logger.info("Server is healthy:")
            logger.info(f"  Status: {health_data.get('status')}")
            logger.info(f"  Version: {health_data.get('version')}")
            logger.info(f"  Uptime: {health_data.get('uptime_seconds'):.2f} seconds")
            logger.info(f"  Tools Count: {health_data.get('tools_count', 0)}")
            categories = health_data.get('registered_tool_categories', [])
            logger.info(f"  Tool Categories: {', '.join(categories) if categories else 'None'}")
            return True, health_data
        else:
            logger.error(f"Server health check failed with status code {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False, None
            
    except Exception as e:
        logger.error(f"Error checking server health: {str(e)}")
        logger.error(traceback.format_exc())
        return False, None

def jsonrpc_call(env, method, params=None):
    """Make a JSON-RPC call to the server."""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": int(datetime.now().timestamp() * 1000)
    }
    
    logger.info(f"Calling method: {method}")
    if params:
        logger.info(f"Parameters: {json.dumps(params, indent=JSON_INDENT)}")
    
    try:
        response = requests.post(
            env["jsonrpc_url"],
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=env["timeout"]
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if "error" in data:
                logger.error(f"JSON-RPC error: {json.dumps(data['error'], indent=JSON_INDENT)}")
                return False, data
            
            return True, data.get("result")
        else:
            logger.error(f"HTTP error: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False, {"error": f"HTTP error: {response.status_code}"}
            
    except Exception as e:
        logger.error(f"Exception during JSON-RPC call: {str(e)}")
        logger.error(traceback.format_exc())
        return False, {"error": str(e)}

def get_tools(env):
    """Get the list of available tools from the server."""
    logger.info("Getting available tools")
    
    success, result = jsonrpc_call(env, "get_tools")
    
    if success and "tools" in result:
        tools = result["tools"]
        logger.info(f"Found {len(tools)} tools")
        
        # Group tools by category
        categories = {}
        for tool in tools:
            name = tool["name"]
            if "_" in name:
                category = name.split("_")[0]
                if category not in categories:
                    categories[category] = []
                categories[category].append(name)
            else:
                if "misc" not in categories:
                    categories["misc"] = []
                categories["misc"].append(name)
        
        # Print tools by category
        for category, tool_names in categories.items():
            logger.info(f"Category {category} ({len(tool_names)} tools):")
            for name in sorted(tool_names):
                logger.info(f"  - {name}")
        
        return True, tools
    else:
        logger.error("Failed to get tools")
        return False, None

def test_ipfs_add(env):
    """Test adding content to IPFS."""
    logger.info("Testing ipfs_add")
    
    content = "Hello IPFS MCP World! Test at " + datetime.now().isoformat()
    success, result = jsonrpc_call(env, "ipfs_add", {"content": content})
    
    if success and "cid" in result:
        cid = result["cid"]
        logger.info(f"Successfully added content to IPFS with CID: {cid}")
        
        # Test retrieving the content
        logger.info("Testing ipfs_cat to retrieve the content")
        success, result = jsonrpc_call(env, "ipfs_cat", {"cid": cid})
        
        if success and "content" in result:
            retrieved_content = result["content"]
            if retrieved_content == content:
                logger.info("Content retrieved successfully and matches original")
                return True, cid
            else:
                logger.error("Retrieved content does not match original")
                logger.error(f"Original: {content}")
                logger.error(f"Retrieved: {retrieved_content}")
                return False, None
        else:
            logger.error("Failed to retrieve content")
            return False, None
    else:
        logger.error("Failed to add content to IPFS")
        return False, None

def test_mfs_operations(env):
    """Test MFS (Mutable File System) operations."""
    logger.info("Testing MFS operations")
    
    # Create a test directory
    test_dir = f"/test_dir_{int(datetime.now().timestamp())}"
    success, result = jsonrpc_call(env, "ipfs_files_mkdir", {"path": test_dir})
    
    if not success:
        logger.error(f"Failed to create directory {test_dir}")
        return False
    
    logger.info(f"Successfully created directory {test_dir}")
    
    # Write to a test file
    test_file = f"{test_dir}/test.txt"
    content = "Hello MFS World! Test at " + datetime.now().isoformat()
    success, result = jsonrpc_call(
        env, 
        "ipfs_files_write", 
        {"path": test_file, "content": content, "create": True}
    )
    
    if not success:
        logger.error(f"Failed to write to {test_file}")
        return False
    
    logger.info(f"Successfully wrote to {test_file}")
    
    # Read the test file
    success, result = jsonrpc_call(env, "ipfs_files_read", {"path": test_file})
    
    if not success or "content" not in result:
        logger.error(f"Failed to read {test_file}")
        return False
    
    retrieved_content = result["content"]
    if retrieved_content != content:
        logger.error("Retrieved content does not match original")
        logger.error(f"Original: {content}")
        logger.error(f"Retrieved: {retrieved_content}")
        return False
    
    logger.info("Successfully read content from file")
    
    # List directory contents
    success, result = jsonrpc_call(env, "ipfs_files_ls", {"path": test_dir})
    
    if not success or "entries" not in result:
        logger.error(f"Failed to list directory {test_dir}")
        return False
    
    entries = result["entries"]
    if not any(e["name"] == "test.txt" for e in entries):
        logger.error("test.txt not found in directory listing")
        return False
    
    logger.info("Successfully listed directory contents")
    
    # Clean up
    success, result = jsonrpc_call(env, "ipfs_files_rm", {"path": test_dir, "recursive": True})
    
    if not success:
        logger.warning(f"Failed to remove directory {test_dir}")
    else:
        logger.info(f"Successfully removed directory {test_dir}")
    
    return True

def run_all_tests(env):
    """Run all tests and return overall success."""
    tests = [
        ("Server Health", lambda: check_server_health(env)[0]),
        ("Get Tools", lambda: get_tools(env)[0]),
        ("IPFS Add", lambda: test_ipfs_add(env)[0]),
        ("MFS Operations", lambda: test_mfs_operations(env))
    ]
    
    success_count = 0
    failure_count = 0
    
    logger.info("=== Running MCP Server Tests ===")
    
    for name, test_func in tests:
        logger.info(f"\n=== Test: {name} ===")
        try:
            if test_func():
                logger.info(f"✅ {name} - PASSED")
                success_count += 1
            else:
                logger.error(f"❌ {name} - FAILED")
                failure_count += 1
        except Exception as e:
            logger.error(f"❌ {name} - ERROR: {str(e)}")
            logger.error(traceback.format_exc())
            failure_count += 1
    
    logger.info("\n=== Test Summary ===")
    logger.info(f"Tests passed: {success_count}")
    logger.info(f"Tests failed: {failure_count}")
    logger.info("=====================")
    
    return failure_count == 0

def parse_arguments():
    """Parse command line arguments."""
    import argparse
    
    parser = argparse.ArgumentParser(description="IPFS MCP Server Test Diagnostics")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"MCP server host (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"MCP server port (default: {DEFAULT_PORT})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Set environment variables for the test environment
    os.environ["MCP_HOST"] = args.host
    os.environ["MCP_PORT"] = str(args.port)
    os.environ["MCP_TIMEOUT"] = str(args.timeout)
    
    # Configure logging level
    if args.verbose:
        logging.getLogger("mcp-test-diagnostics").setLevel(logging.DEBUG)
    
    return args

def main():
    """Main function."""
    args = parse_arguments()
    env = setup_test_env()
    
    logger.info(f"MCP Server URL: {env['url']}")
    
    # Run all tests
    success = run_all_tests(env)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
