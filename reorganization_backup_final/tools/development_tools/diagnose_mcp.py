#!/usr/bin/env python3
"""
IPFS MCP Diagnostic Tool

This tool performs targeted tests on the MCP server to diagnose specific issues.
"""

import requests
import json
import sys
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ipfs-mcp-diagnostics")

# MCP Server configuration
HOST = "localhost"
PORT = 9998
URL = f"http://{HOST}:{PORT}"
JSONRPC_URL = f"{URL}/jsonrpc"
HEALTH_URL = f"{URL}/health"
TIMEOUT = 10  # seconds

def test_health():
    """Test the health endpoint"""
    try:
        logger.info(f"Testing health endpoint at {HEALTH_URL}")
        response = requests.get(HEALTH_URL, timeout=TIMEOUT)
        logger.info(f"Health response status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Health data: {json.dumps(data, indent=2)}")
            return True
        else:
            logger.error(f"Health check failed with status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return False

def jsonrpc_call(method, params=None):
    """Make a JSON-RPC call to the MCP server"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": int(time.time() * 1000)
    }
    
    try:
        logger.info(f"Making JSON-RPC call: {method}")
        response = requests.post(
            JSONRPC_URL, 
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT
        )
        
        logger.info(f"JSON-RPC response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"JSON-RPC HTTP error: {response.status_code}, {response.text}")
            return None
        
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Response text: {response.text}")
            return None
        
        if "error" in data:
            logger.error(f"JSON-RPC error: {data['error']}")
            return None
        
        if "result" not in data:
            logger.error("JSON-RPC response missing 'result' field")
            logger.error(f"Full response: {data}")
            return None
        
        return data["result"]
    except Exception as e:
        logger.error(f"JSON-RPC call error: {e}")
        return None

def test_ping():
    """Test basic ping functionality"""
    result = jsonrpc_call("ping")
    if result == "pong":
        logger.info("Ping test passed")
        return True
    else:
        logger.error(f"Ping test failed, got: {result}")
        return False

def test_get_tools():
    """Test getting the list of available tools"""
    result = jsonrpc_call("get_tools")
    if result and isinstance(result, list):
        logger.info(f"Found {len(result)} tools:")
        for tool in result:
            logger.info(f"  - {tool}")
        return True
    else:
        logger.error("Failed to get tools list")
        return False

def test_get_server_info():
    """Test getting server info"""
    result = jsonrpc_call("get_server_info")
    if result and isinstance(result, dict):
        logger.info(f"Server info: {json.dumps(result, indent=2)}")
        return True
    else:
        logger.error("Failed to get server info")
        return False

def test_ipfs_add():
    """Test adding content to IPFS"""
    result = jsonrpc_call("ipfs_add", {"content": "Hello IPFS MCP diagnostic tool!"})
    if result and "cid" in result:
        logger.info(f"Successfully added content to IPFS. CID: {result['cid']}")
        
        # Now try to retrieve it
        cat_result = jsonrpc_call("ipfs_cat", {"cid": result["cid"]})
        if cat_result and isinstance(cat_result, str):
            logger.info(f"Successfully retrieved content: {cat_result}")
            return True
        else:
            logger.error(f"Failed to retrieve content with CID: {result['cid']}")
            return False
    else:
        logger.error("Failed to add content to IPFS")
        return False

def main():
    """Run diagnostic tests"""
    logger.info("Starting IPFS MCP diagnostic tests")
    
    tests = [
        ("Health endpoint", test_health),
        ("Ping", test_ping),
        ("Get tools list", test_get_tools),
        ("Get server info", test_get_server_info),
        ("IPFS add/cat", test_ipfs_add)
    ]
    
    results = []
    for name, func in tests:
        logger.info(f"Running test: {name}")
        try:
            result = func()
            results.append((name, result))
            logger.info(f"Test {name}: {'PASSED' if result else 'FAILED'}")
        except Exception as e:
            logger.error(f"Test {name} raised exception: {e}")
            results.append((name, False))
    
    # Print summary
    logger.info("\n=== Test Results Summary ===")
    passed = 0
    for name, result in results:
        status = "PASSED" if result else "FAILED"
        logger.info(f"{name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"Passed {passed} of {len(results)} tests")
    
    return 0 if passed == len(results) else 1

if __name__ == "__main__":
    sys.exit(main())
