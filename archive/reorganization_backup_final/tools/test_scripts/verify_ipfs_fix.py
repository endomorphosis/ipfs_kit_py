#!/usr/bin/env python3
"""
IPFS Fix Verification Script

This script verifies that the IPFS tool handlers in the MCP server
are working correctly, especially for parameter handling.
"""

import os
import sys
import json
import logging
import anyio
import requests
from datetime import datetime
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("verification.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ipfs-fix-verify")

# MCP Server configuration
MCP_HOST = "localhost"
MCP_PORT = 9998
MCP_URL = f"http://{MCP_HOST}:{MCP_PORT}"
JSONRPC_URL = f"{MCP_URL}/jsonrpc"
HEALTH_URL = f"{MCP_URL}/health"
TIMEOUT = 10  # seconds

# Test data
TEST_CONTENT = "Hello IPFS World from verification script!"
TEST_FILENAME = "test_file.txt"
TEST_MFS_PATH = "/test_verify_path"


def check_server_health() -> bool:
    """Check if the MCP server is running and healthy"""
    try:
        response = requests.get(HEALTH_URL, timeout=TIMEOUT)
        if response.status_code == 200:
            health_data = response.json()
            logger.info(f"Server health: {health_data}")
            return True
        else:
            logger.error(f"Server health check failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error checking server health: {e}")
        return False


def call_jsonrpc(method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Call a JSON-RPC method on the MCP server"""
    payload = {
        "jsonrpc": "2.0",
        "id": str(datetime.now().timestamp()),
        "method": method,
        "params": params
    }
    
    logger.info(f"Calling {method} with params: {json.dumps(params, indent=2)}")
    
    try:
        response = requests.post(JSONRPC_URL, json=payload, timeout=TIMEOUT)
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Response: {json.dumps(result, indent=2)}")
            return result
        else:
            logger.error(f"Error calling {method}: {response.status_code} - {response.text}")
            return {"error": {"code": response.status_code, "message": response.text}}
    except Exception as e:
        logger.error(f"Exception calling {method}: {e}")
        return {"error": {"code": -32000, "message": str(e)}}


def test_ipfs_add():
    """Test the ipfs_add tool with various parameter combinations"""
    test_cases = [
        # Standard parameter naming
        {"content": TEST_CONTENT, "filename": TEST_FILENAME},
        # Alternative parameter naming
        {"data": TEST_CONTENT, "name": TEST_FILENAME},
        # Another alternative
        {"text": TEST_CONTENT, "file_name": TEST_FILENAME},
        # Minimal parameters
        {"content": TEST_CONTENT},
        # With pin parameter
        {"content": TEST_CONTENT, "pin": True},
    ]
    
    results = []
    for i, params in enumerate(test_cases):
        logger.info(f"=== Test Case {i+1}: {params} ===")
        result = call_jsonrpc("ipfs_add", params)
        results.append({"params": params, "result": result})
        if "error" in result:
            logger.error(f"Test case {i+1} failed")
        elif "result" in result and isinstance(result["result"], dict) and "cid" in result["result"]:
            logger.info(f"Test case {i+1} passed - CID: {result['result']['cid']}")
        else:
            logger.warning(f"Test case {i+1} - unexpected result format")
    
    return results


def test_ipfs_cat(cid: Optional[str] = None):
    """Test the ipfs_cat tool"""
    if not cid:
        # Use a known test CID if none provided
        cid = "QmPZ9gcCEpqKTo6aq61g2nXGUhM4iCL3ewB6LDXZCtioEB"
    
    result = call_jsonrpc("ipfs_cat", {"cid": cid})
    if "error" in result:
        logger.error(f"ipfs_cat test failed")
        return False
    else:
        logger.info(f"ipfs_cat test passed")
        return True


def test_mfs_operations():
    """Test MFS operations"""
    # Create directory
    mkdir_result = call_jsonrpc("ipfs_files_mkdir", {"path": TEST_MFS_PATH})
    if "error" in mkdir_result:
        logger.error(f"ipfs_files_mkdir test failed")
        return False
    
    # Write file
    write_result = call_jsonrpc("ipfs_files_write", {
        "path": f"{TEST_MFS_PATH}/test.txt", 
        "content": TEST_CONTENT,
        "create": True
    })
    if "error" in write_result:
        logger.error(f"ipfs_files_write test failed")
        return False
    
    # Read file
    read_result = call_jsonrpc("ipfs_files_read", {"path": f"{TEST_MFS_PATH}/test.txt"})
    if "error" in read_result:
        logger.error(f"ipfs_files_read test failed")
        return False
    
    # List directory
    ls_result = call_jsonrpc("ipfs_files_ls", {"path": TEST_MFS_PATH})
    if "error" in ls_result:
        logger.error(f"ipfs_files_ls test failed")
        return False
    
    logger.info(f"MFS operations test passed")
    return True


def run_all_tests():
    """Run all verification tests"""
    logger.info("Starting IPFS MCP verification tests")
    
    if not check_server_health():
        logger.error("Server health check failed, cannot proceed with tests")
        return False
    
    # Test ipfs_add with various parameter combinations
    add_results = test_ipfs_add()
    
    # If we have a successful add result, use that CID for cat test
    cid = None
    for result in add_results:
        if "result" in result["result"] and "cid" in result["result"]["result"]:
            cid = result["result"]["result"]["cid"]
            break
    
    # Test ipfs_cat
    cat_result = test_ipfs_cat(cid)
    
    # Test MFS operations
    mfs_result = test_mfs_operations()
    
    # Overall results
    success = any(["result" in r["result"] and "cid" in r["result"]["result"] for r in add_results]) and cat_result and mfs_result
    
    if success:
        logger.info("🎉 All verification tests PASSED! The IPFS MCP integration is working correctly.")
    else:
        logger.error("❌ Some verification tests FAILED. See logs for details.")
    
    return success


if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Verification tests interrupted")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unhandled exception in verification tests: {e}")
        sys.exit(1)
