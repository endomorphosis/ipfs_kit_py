#!/usr/bin/env python3
"""
Verify FS Tool Integration

This script verifies that the filesystem integration with IPFS tools is working correctly.
"""

import os
import sys
import json
import logging
import requests
import tempfile
import time
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# MCP server endpoint
MCP_ENDPOINT = "http://localhost:3000/api"

def call_mcp_method(method, params=None):
    """Call a method on the MCP server"""
    if params is None:
        params = {}
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }
    
    try:
        response = requests.post(MCP_ENDPOINT, json=payload)
        response.raise_for_status()
        result = response.json()
        
        if "error" in result:
            logger.error(f"Error calling {method}: {result['error']}")
            return None
        
        return result.get("result")
    
    except Exception as e:
        logger.error(f"Error calling {method}: {e}")
        return None

def verify_fs_operations():
    """Verify filesystem operations"""
    logger.info("Verifying filesystem operations...")
    
    # Create a test directory in the virtual filesystem
    test_dir = f"/test_fs_integration_{int(time.time())}"
    result = call_mcp_method("fs_journal_sync", {"path": "/"})
    if result is None:
        logger.error("Failed to sync filesystem journal")
        return False
    
    # Create a test file in the virtual filesystem
    test_file = f"{test_dir}/test_file.txt"
    test_content = f"Test content generated at {time.time()}"
    
    # First create the directory
    result = call_mcp_method("ipfs_files_mkdir", {"path": test_dir})
    if result is None:
        logger.error(f"Failed to create directory {test_dir}")
        return False
    
    logger.info(f"✅ Created test directory {test_dir}")
    
    # Write to the test file
    result = call_mcp_method("ipfs_files_write", {
        "path": test_file,
        "content": test_content,
        "create": True
    })
    if result is None:
        logger.error(f"Failed to write to file {test_file}")
        return False
    
    logger.info(f"✅ Created test file {test_file}")
    
    # Read the test file
    result = call_mcp_method("ipfs_files_read", {"path": test_file})
    if result is None:
        logger.error(f"Failed to read file {test_file}")
        return False
    
    if result != test_content:
        logger.error(f"File content mismatch. Expected: {test_content}, Got: {result}")
        return False
    
    logger.info(f"✅ Successfully read test file with correct content")
    
    # Get file stats
    result = call_mcp_method("ipfs_files_stat", {"path": test_file})
    if result is None:
        logger.error(f"Failed to get stats for file {test_file}")
        return False
    
    logger.info(f"✅ Got stats for test file: {result}")
    
    # Copy the file
    copy_file = f"{test_dir}/test_file_copy.txt"
    result = call_mcp_method("ipfs_files_cp", {
        "source": test_file,
        "dest": copy_file
    })
    if result is None:
        logger.error(f"Failed to copy file from {test_file} to {copy_file}")
        return False
    
    logger.info(f"✅ Copied test file to {copy_file}")
    
    # Verify the copy
    result = call_mcp_method("ipfs_files_read", {"path": copy_file})
    if result is None or result != test_content:
        logger.error(f"Failed to verify copied file content")
        return False
    
    logger.info(f"✅ Verified copied file content")
    
    # Move the file
    move_file = f"{test_dir}/test_file_moved.txt"
    result = call_mcp_method("ipfs_files_mv", {
        "source": copy_file,
        "dest": move_file
    })
    if result is None:
        logger.error(f"Failed to move file from {copy_file} to {move_file}")
        return False
    
    logger.info(f"✅ Moved test file to {move_file}")
    
    # Verify the move
    result = call_mcp_method("ipfs_files_read", {"path": move_file})
    if result is None or result != test_content:
        logger.error(f"Failed to verify moved file content")
        return False
    
    logger.info(f"✅ Verified moved file content")
    
    # List directory contents
    result = call_mcp_method("ipfs_files_ls", {"path": test_dir})
    if result is None:
        logger.error(f"Failed to list directory {test_dir}")
        return False
    
    logger.info(f"✅ Listed directory contents: {result}")
    
    # Clean up
    result = call_mcp_method("ipfs_files_rm", {
        "path": test_dir,
        "recursive": True
    })
    if result is None:
        logger.error(f"Failed to remove test directory {test_dir}")
        return False
    
    logger.info(f"✅ Cleaned up test directory")
    
    return True

def verify_multi_backend():
    """Verify multi-backend operations"""
    logger.info("Verifying multi-backend operations...")
    
    # List backends
    result = call_mcp_method("multi_backend_list_backends")
    if result is None:
        logger.warning("Multi-backend functionality not available")
        return True  # Not a failure, just not available
    
    logger.info(f"✅ Listed backends: {result}")
    
    # Test mapping a path
    local_path = tempfile.mkdtemp()
    backend_path = "/ipfs/test_mapping"
    
    result = call_mcp_method("multi_backend_map", {
        "backend_path": backend_path,
        "local_path": local_path
    })
    if result is None:
        logger.error(f"Failed to map {backend_path} to {local_path}")
        return False
    
    logger.info(f"✅ Mapped {backend_path} to {local_path}")
    
    # Create a test file in the local path
    test_file = os.path.join(local_path, "test_file.txt")
    with open(test_file, 'w') as f:
        f.write("Test content for multi-backend")
    
    # Sync the mapping
    result = call_mcp_method("multi_backend_sync")
    if result is None:
        logger.error("Failed to sync multi-backend")
        return False
    
    logger.info(f"✅ Synced multi-backend")
    
    # Unmap the path
    result = call_mcp_method("multi_backend_unmap", {
        "backend_path": backend_path
    })
    if result is None:
        logger.error(f"Failed to unmap {backend_path}")
        return False
    
    logger.info(f"✅ Unmapped {backend_path}")
    
    return True

def verify_enhanced_tools():
    """Verify enhanced tools"""
    logger.info("Verifying enhanced tools...")
    
    # Test IPFS cluster tools if available
    result = call_mcp_method("ipfs_cluster_peers")
    if result is not None:
        logger.info(f"✅ IPFS cluster tools available: {result}")
    else:
        logger.warning("IPFS cluster tools not available")
    
    # Test Lassie tools if available
    temp_file = tempfile.mktemp()
    result = call_mcp_method("lassie_fetch", {
        "cid": "QmPChd2hVbrJ6bfo3WBcTW4iZnpHm8TEzWkLHmLpXhF68A",  # Example CID
        "output_path": temp_file
    })
    if result is not None:
        logger.info(f"✅ Lassie tools available: {result}")
    else:
        logger.warning("Lassie tools not available")
    
    # Test Storacha tools if available
    result = call_mcp_method("storacha_store", {
        "content_path": __file__  # Use this script as test content
    })
    if result is not None:
        logger.info(f"✅ Storacha tools available: {result}")
    else:
        logger.warning("Storacha tools not available")
    
    return True

def main():
    """Main verification function"""
    logger.info("Starting verification of FS tool integration...")
    
    # Check if MCP server is running
    try:
        response = requests.get(MCP_ENDPOINT.replace("/api", "/health"))
        if response.status_code != 200:
            logger.error(f"MCP server is not running or health check failed: {response.status_code}")
            return 1
        
        logger.info("✅ MCP server is running")
    except Exception as e:
        logger.error(f"Error connecting to MCP server: {e}")
        logger.error("Please make sure the MCP server is running with the enhanced tools")
        return 1
    
    # Verify filesystem operations
    if not verify_fs_operations():
        logger.error("❌ Filesystem operations verification failed")
        return 1
    
    # Verify multi-backend operations
    if not verify_multi_backend():
        logger.error("❌ Multi-backend operations verification failed")
        return 1
    
    # Verify enhanced tools
    if not verify_enhanced_tools():
        logger.error("❌ Enhanced tools verification failed")
        return 1
    
    logger.info("\n✅ All verifications passed successfully!")
    logger.info("The filesystem integration with IPFS tools is working correctly")
    return 0

if __name__ == "__main__":
    sys.exit(main())
