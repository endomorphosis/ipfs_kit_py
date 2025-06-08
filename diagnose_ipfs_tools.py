#!/usr/bin/env python3
"""
IPFS MCP Tools Diagnostic Script

This script tests each IPFS tool individually with detailed logging to help diagnose issues.
"""

import os
import sys
import json
import time
import logging
import requests
import traceback
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("ipfs-mcp-diagnostic")

# MCP Server configuration
MCP_HOST = "localhost"
MCP_PORT = 9998
MCP_URL = f"http://{MCP_HOST}:{MCP_PORT}"
JSONRPC_URL = f"{MCP_URL}/jsonrpc"
HEALTH_URL = f"{MCP_URL}/health"
TIMEOUT = 10  # seconds

# Test data
TEST_CONTENT = "Hello IPFS MCP World - Diagnostic Test!"
TEST_FILE = "test_diagnostic_file.txt"
TEST_DIR = "test_diagnostic_dir"
TEST_MFS_PATH = "/test_diagnostic_path"

def jsonrpc_call(method: str, params: Optional[Dict] = None) -> Dict:
    """Make a JSON-RPC call to the MCP server with detailed logging"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": int(time.time() * 1000)
    }

    # Log the request
    logger.info(f"JSON-RPC request: {method} with params: {json.dumps(params)}")

    try:
        response = requests.post(
            JSONRPC_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT
        )

        logger.info(f"JSON-RPC response status code: {response.status_code}")
        
        try:
            result = response.json()
            logger.info(f"JSON-RPC response: {json.dumps(result)[:1000]}")
            
            if "error" in result:
                logger.error(f"JSON-RPC error: {result['error']}")
                return {"error": str(result["error"])}
            
            if "result" in result:
                return result["result"]
            
            return {"error": "Invalid JSON-RPC response"}
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON response: {response.text}")
            return {"error": f"Invalid JSON response: {response.text[:200]}..."}
    except Exception as e:
        logger.error(f"Exception during JSON-RPC call: {e}\n{traceback.format_exc()}")
        return {"error": str(e)}

def check_server_health():
    """Check if the MCP server is healthy"""
    try:
        response = requests.get(HEALTH_URL, timeout=TIMEOUT)
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Server health: {result}")
            return True
        else:
            logger.error(f"Server health check failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return False

def test_ping():
    """Test basic server connectivity"""
    logger.info("--- Testing ping ---")
    result = jsonrpc_call("ping")
    if "error" in result:
        logger.error(f"Ping failed: {result['error']}")
        return False
    logger.info(f"Ping successful: {result}")
    return True

def test_ipfs_add():
    """Test adding content to IPFS"""
    logger.info("--- Testing ipfs_add ---")
    
    # Try with different parameter formats
    test_variations = [
        {"content": TEST_CONTENT},
        {"content": TEST_CONTENT, "pin": True},
        {"data": TEST_CONTENT},
        {"text": TEST_CONTENT}
    ]
    
    for i, params in enumerate(test_variations):
        logger.info(f"Variation {i+1}: {params}")
        result = jsonrpc_call("ipfs_add", params)
        if "error" in result:
            logger.error(f"ipfs_add failed with params {params}: {result['error']}")
        else:
            logger.info(f"ipfs_add succeeded: {result}")
            return result.get("cid")
    
    return None

def test_ipfs_cat(cid):
    """Test retrieving content from IPFS"""
    logger.info(f"--- Testing ipfs_cat with CID {cid} ---")
    if not cid:
        logger.error("No CID provided for cat")
        return False
        
    result = jsonrpc_call("ipfs_cat", {"cid": cid})
    if "error" in result:
        logger.error(f"ipfs_cat failed: {result['error']}")
        return False
    
    logger.info(f"ipfs_cat result: {result}")
    if result == TEST_CONTENT:
        logger.info("Content matches expected value")
        return True
    else:
        logger.error(f"Content mismatch. Expected '{TEST_CONTENT}', got '{result}'")
        return False

def test_ipfs_pin(cid):
    """Test pinning content in IPFS"""
    logger.info(f"--- Testing ipfs_pin with CID {cid} ---")
    if not cid:
        logger.error("No CID provided for pin")
        return False
        
    # Pin the content
    result = jsonrpc_call("ipfs_pin_add", {"cid": cid})
    if "error" in result:
        logger.error(f"ipfs_pin_add failed: {result['error']}")
        return False
    
    logger.info(f"ipfs_pin_add result: {result}")
    
    # List pins
    result = jsonrpc_call("ipfs_pin_ls", {})
    if "error" in result:
        logger.error(f"ipfs_pin_ls failed: {result['error']}")
        return False
    
    logger.info(f"ipfs_pin_ls result: {result}")
    pins = result.get("pins", [])
    if cid in pins:
        logger.info(f"CID {cid} found in pins")
    else:
        logger.error(f"CID {cid} not found in pins: {pins}")
        return False
    
    # Remove pin
    result = jsonrpc_call("ipfs_pin_rm", {"cid": cid})
    if "error" in result:
        logger.error(f"ipfs_pin_rm failed: {result['error']}")
        return False
    
    logger.info(f"ipfs_pin_rm result: {result}")
    return True

def test_mfs_mkdir():
    """Test creating directories in MFS"""
    logger.info(f"--- Testing ipfs_files_mkdir with path {TEST_MFS_PATH} ---")
    
    # First try to remove if it exists
    result = jsonrpc_call("ipfs_files_rm", {"path": TEST_MFS_PATH, "recursive": True})
    logger.info(f"Cleanup result: {result}")
    
    # Create directory
    result = jsonrpc_call("ipfs_files_mkdir", {"path": TEST_MFS_PATH})
    if "error" in result:
        logger.error(f"ipfs_files_mkdir failed: {result['error']}")
        return False
    
    logger.info(f"ipfs_files_mkdir result: {result}")
    
    # List directories to verify
    result = jsonrpc_call("ipfs_files_ls", {"path": "/"})
    if "error" in result:
        logger.error(f"ipfs_files_ls failed: {result['error']}")
        return False
    
    logger.info(f"ipfs_files_ls result: {result}")
    return True

def test_mfs_write_read():
    """Test writing and reading files in MFS"""
    test_path = f"{TEST_MFS_PATH}/{TEST_FILE}"
    logger.info(f"--- Testing MFS write/read with path {test_path} ---")
    
    # Write file
    result = jsonrpc_call("ipfs_files_write", {
        "path": test_path,
        "content": TEST_CONTENT,
        "create": True,
        "truncate": True
    })
    if "error" in result:
        logger.error(f"ipfs_files_write failed: {result['error']}")
        return False
    
    logger.info(f"ipfs_files_write result: {result}")
    
    # Read file
    result = jsonrpc_call("ipfs_files_read", {"path": test_path})
    if "error" in result:
        logger.error(f"ipfs_files_read failed: {result['error']}")
        return False
    
    logger.info(f"ipfs_files_read result: {result}")
    if result == TEST_CONTENT:
        logger.info("Content matches expected value")
    else:
        logger.error(f"Content mismatch. Expected '{TEST_CONTENT}', got '{result}'")
        return False
    
    return True

def run_diagnostics():
    """Run all diagnostic tests"""
    logger.info("Starting IPFS MCP diagnostic tests")
    
    # Check server health
    if not check_server_health():
        logger.error("Server health check failed, aborting tests")
        return
    
    # Test basic connectivity
    if not test_ping():
        logger.error("Basic connectivity test failed, aborting tests")
        return
    
    # Test IPFS core functions
    cid = test_ipfs_add()
    if cid:
        test_ipfs_cat(cid)
        test_ipfs_pin(cid)
    
    # Test MFS functions
    test_mfs_mkdir()
    test_mfs_write_read()
    
    logger.info("Diagnostic tests completed")

if __name__ == "__main__":
    run_diagnostics()
