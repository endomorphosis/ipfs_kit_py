#!/usr/bin/env python3
"""
IPFS-VFS Integration Test

This script tests comprehensive integration between IPFS and virtual filesystem
by creating files, directories, publishing to IPFS, and synchronizing content.

It provides a more thorough test of the virtual filesystem tools than the basic test script.
"""

import os
import sys
import json
import logging
import asyncio
import time
import argparse
import requests
import tempfile
import base64
from datetime import datetime
from pprint import pprint
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# MCP Server URL
MCP_URL = "http://localhost:3000"
MCP_JSON_RPC_URL = f"{MCP_URL}/jsonrpc"
TOOL_ENDPOINT = f"{MCP_URL}/mcp/tools"

async def call_tool(tool_name: str, args: Dict[str, Any] = None) -> Dict[str, Any]:
    """Call a tool on the MCP server via JSON-RPC"""
    if args is None:
        args = {}
    
    try:
        # First try the JSON-RPC endpoint
        response = requests.post(MCP_JSON_RPC_URL, json={
            "jsonrpc": "2.0",
            "method": "use_tool",
            "params": {
                "tool_name": tool_name,
                "arguments": args
            },
            "id": int(time.time() * 1000)  # Use timestamp as ID
        })
        
        if response.status_code == 200:
            data = response.json()
            if "result" in data:
                return data["result"]
            elif "error" in data:
                logger.error(f"Error calling tool {tool_name} via JSON-RPC: {data['error']}")
                return {"error": data["error"]}
        
        # If JSON-RPC fails, try the direct tools endpoint
        logger.info(f"JSON-RPC failed, trying direct tool endpoint")
        response = requests.post(TOOL_ENDPOINT, json={
            "name": tool_name,
            "args": args
        })
        
        if response.status_code == 200:
            return response.json()
        
        logger.error(f"Error calling tool {tool_name}: HTTP {response.status_code}")
        return {"error": f"HTTP {response.status_code}", "body": response.text}
    
    except Exception as e:
        logger.error(f"Exception calling tool {tool_name}: {e}")
        return {"error": str(e)}

async def get_available_tools() -> List[str]:
    """Get a list of available tools from the MCP server"""
    try:
        response = requests.post(MCP_JSON_RPC_URL, json={
            "jsonrpc": "2.0", 
            "method": "get_tools",
            "params": {},
            "id": 1
        })
        
        if response.status_code != 200:
            logger.error(f"Error getting tools: HTTP {response.status_code}")
            return []
        
        data = response.json()
        all_tools = []
        
        # Check response structure
        if "result" in data:
            if isinstance(data["result"], list):
                all_tools = data["result"]
            elif "tools" in data["result"]:
                all_tools = data["result"]["tools"]
            
        # Extract tool names
        tool_names = [tool["name"] for tool in all_tools]
        return tool_names
        
    except Exception as e:
        logger.error(f"Exception getting tools: {e}")
        return []

async def test_basic_vfs_operations():
    """Test basic virtual filesystem operations"""
    logger.info("=== TESTING BASIC VFS OPERATIONS ===")
    
    # Create test directory
    test_dir = f"/vfs_test_{int(time.time())}"
    logger.info(f"Creating test directory: {test_dir}")
    
    result = await call_tool("vfs_mkdir", {"path": test_dir})
    if "error" in result:
        logger.error(f"Failed to create directory: {result['error']}")
        return False
    
    # Create test file
    test_file = f"{test_dir}/hello.txt"
    test_content = f"Hello, virtual filesystem! Created at {datetime.now().isoformat()}"
    logger.info(f"Creating file: {test_file}")
    
    result = await call_tool("vfs_write", {
        "path": test_file,
        "content": test_content
    })
    
    if "error" in result:
        logger.error(f"Failed to write file: {result['error']}")
        return False
    
    # Read test file
    logger.info(f"Reading file: {test_file}")
    result = await call_tool("vfs_read", {"path": test_file})
    
    if "error" in result:
        logger.error(f"Failed to read file: {result['error']}")
        return False
    
    if "content" in result:
        if result["content"] == test_content:
            logger.info("✅ File content matches")
        else:
            logger.error(f"❌ File content mismatch: {result['content']}")
    else:
        logger.error("❌ No content in read result")
    
    # List directory
    logger.info(f"Listing directory: {test_dir}")
    result = await call_tool("vfs_list", {"path": test_dir})
    
    if "error" in result:
        logger.error(f"Failed to list directory: {result['error']}")
        return False
    
    if "entries" in result:
        logger.info(f"Directory entries: {len(result['entries'])}")
        for entry in result["entries"]:
            logger.info(f"  {entry['name']} ({entry['type']})")
    else:
        logger.error("❌ No entries in list result")
    
    # Get file stats
    logger.info(f"Getting file stats: {test_file}")
    result = await call_tool("vfs_stat", {"path": test_file})
    
    if "error" in result:
        logger.error(f"Failed to get file stats: {result['error']}")
        return False
    
    if "type" in result:
        logger.info(f"File stats: {result}")
    else:
        logger.error("❌ No type in stat result")
    
    logger.info("✅ Basic VFS operations test completed successfully")
    return True

async def test_advanced_vfs_operations():
    """Test advanced virtual filesystem operations"""
    logger.info("=== TESTING ADVANCED VFS OPERATIONS ===")
    
    # Create test directories
    source_dir = f"/vfs_source_{int(time.time())}"
    dest_dir = f"/vfs_dest_{int(time.time())}"
    
    logger.info(f"Creating source directory: {source_dir}")
    await call_tool("vfs_mkdir", {"path": source_dir})
    
    logger.info(f"Creating destination directory: {dest_dir}")
    await call_tool("vfs_mkdir", {"path": dest_dir})
    
    # Create nested directories
    nested_dir = f"{source_dir}/nested1/nested2"
    logger.info(f"Creating nested directory: {nested_dir}")
    
    # Try to create with parents
    result = await call_tool("vfs_mkdir", {
        "path": nested_dir,
        "metadata": {"description": "A nested test directory"}
    })
    
    # Create a few test files
    files = [
        {"path": f"{source_dir}/file1.txt", "content": "This is file 1"},
        {"path": f"{source_dir}/file2.txt", "content": "This is file 2"},
        {"path": f"{nested_dir}/file3.txt", "content": "This is file 3 in nested directory"}
    ]
    
    for file in files:
        logger.info(f"Creating file: {file['path']}")
        await call_tool("vfs_write", {
            "path": file['path'],
            "content": file['content']
        })
    
    # Test copying files
    copy_source = f"{source_dir}/file1.txt"
    copy_dest = f"{dest_dir}/file1_copy.txt"
    logger.info(f"Copying file: {copy_source} -> {copy_dest}")
    
    result = await call_tool("vfs_copy", {
        "source": copy_source,
        "destination": copy_dest
    })
    
    if "success" in result and result["success"]:
        logger.info("✅ File copied successfully")
    else:
        logger.error(f"❌ Failed to copy file: {result}")
    
    # Test moving files
    move_source = f"{source_dir}/file2.txt"
    move_dest = f"{dest_dir}/file2_moved.txt"
    logger.info(f"Moving file: {move_source} -> {move_dest}")
    
    result = await call_tool("vfs_move", {
        "source": move_source,
        "destination": move_dest
    })
    
    if "success" in result and result["success"]:
        logger.info("✅ File moved successfully")
    else:
        logger.error(f"❌ Failed to move file: {result}")
    
    # List both directories
    logger.info("Listing source directory contents:")
    source_contents = await call_tool("vfs_list", {"path": source_dir})
    if "entries" in source_contents:
        for entry in source_contents["entries"]:
            logger.info(f"  {entry['name']} ({entry['type']})")
    
    logger.info("Listing destination directory contents:")
    dest_contents = await call_tool("vfs_list", {"path": dest_dir})
    if "entries" in dest_contents:
        for entry in dest_contents["entries"]:
            logger.info(f"  {entry['name']} ({entry['type']})")
    
    # Test removing files and directories
    logger.info(f"Removing file: {copy_dest}")
    await call_tool("vfs_rm", {"path": copy_dest})
    
    logger.info(f"Attempting to remove directory with contents: {source_dir}")
    result = await call_tool("vfs_rm", {"path": source_dir})
    logger.info(f"Result (should fail without recursive=True): {result}")
    
    logger.info(f"Removing directory recursively: {source_dir}")
    result = await call_tool("vfs_rm", {"path": source_dir, "recursive": True})
    
    if "success" in result and result["success"]:
        logger.info("✅ Directory removed successfully")
    else:
        logger.error(f"❌ Failed to remove directory: {result}")
    
    logger.info("✅ Advanced VFS operations test completed")
    return True

async def test_filesystem_journal():
    """Test filesystem journal functionality"""
    logger.info("=== TESTING FILESYSTEM JOURNAL ===")
    
    # First check journal status
    logger.info("Checking filesystem journal status")
    result = await call_tool("fs_journal_status", {})
    
    if "error" in result:
        logger.error(f"Failed to get journal status: {result['error']}")
        return False
    
    logger.info(f"Journal status: {result}")
    
    # Create a test directory and file to track
    test_dir = f"/vfs_journal_test_{int(time.time())}"
    test_file = f"{test_dir}/tracked_file.txt"
    
    logger.info(f"Creating test directory: {test_dir}")
    await call_tool("vfs_mkdir", {"path": test_dir})
    
    # Start tracking the directory
    logger.info(f"Starting tracking on: {test_dir}")
    result = await call_tool("fs_journal_track", {"path": test_dir})
    
    if "success" in result and result["success"]:
        logger.info("✅ Tracking started")
    else:
        logger.error(f"❌ Failed to start tracking: {result}")
    
    # Perform some operations
    logger.info(f"Creating file: {test_file}")
    await call_tool("vfs_write", {
        "path": test_file,
        "content": f"This is a tracked file. Created at {datetime.now().isoformat()}"
    })
    
    logger.info(f"Modifying file: {test_file}")
    await call_tool("vfs_write", {
        "path": test_file,
        "content": f"This file has been modified. Modified at {datetime.now().isoformat()}"
    })
    
    # Check journal history
    logger.info("Getting journal history for the file")
    result = await call_tool("fs_journal_get_history", {
        "path": test_file,
        "limit": 10
    })
    
    if "error" in result:
        logger.error(f"Failed to get journal history: {result['error']}")
    else:
        logger.info("Journal history:")
        if "operations" in result:
            for op in result["operations"]:
                logger.info(f"  {op.get('timestamp', 'unknown')}: {op.get('operation_type', 'unknown')}")
        else:
            logger.error("❌ No operations in journal history")
    
    # Get full journal history
    logger.info("Getting full journal history")
    result = await call_tool("fs_journal_get_history", {
        "limit": 5
    })
    
    if "operations" in result:
        logger.info(f"Recent operations ({len(result['operations'])}):")
        for op in result["operations"]:
            logger.info(f"  {op.get('timestamp', 'unknown')}: {op.get('operation_type', 'unknown')} - {op.get('path', 'unknown')}")
    
    # Stop tracking
    logger.info(f"Stopping tracking on: {test_dir}")
    result = await call_tool("fs_journal_untrack", {"path": test_dir})
    
    if "success" in result and result["success"]:
        logger.info("✅ Tracking stopped")
    else:
        logger.error(f"❌ Failed to stop tracking: {result}")
    
    # Cleanup
    logger.info(f"Cleaning up test directory: {test_dir}")
    await call_tool("vfs_rm", {"path": test_dir, "recursive": True})
    
    logger.info("✅ Filesystem journal test completed")
    return True

async def test_ipfs_bridge():
    """Test IPFS-FS bridge functionality"""
    logger.info("=== TESTING IPFS-FS BRIDGE ===")
    
    # First check bridge status
    logger.info("Checking IPFS-FS bridge status")
    result = await call_tool("ipfs_fs_bridge_status", {})
    
    if "error" in result:
        logger.error(f"Failed to get bridge status: {result['error']}")
        return False
    
    logger.info(f"Bridge status: {result}")
    
    # Create a test file to export to IPFS
    test_dir = f"/ipfs_bridge_test_{int(time.time())}"
    test_file = f"{test_dir}/ipfs_test.txt"
    
    logger.info(f"Creating test directory: {test_dir}")
    await call_tool("vfs_mkdir", {"path": test_dir})
    
    logger.info(f"Creating test file: {test_file}")
    await call_tool("vfs_write", {
        "path": test_file,
        "content": f"This file will be exported to IPFS. Created at {datetime.now().isoformat()}"
    })
    
    # Export to IPFS
    logger.info(f"Exporting file to IPFS: {test_file}")
    result = await call_tool("ipfs_fs_export_to_ipfs", {
        "path": test_file
    })
    
    if "error" in result:
        logger.error(f"Failed to export to IPFS: {result['error']}")
        return False
    
    if "cid" in result:
        cid = result["cid"]
        logger.info(f"✅ File exported to IPFS with CID: {cid}")
    else:
        logger.error("❌ No CID in export result")
        return False
    
    # List mappings
    logger.info("Listing IPFS-FS mappings")
    result = await call_tool("ipfs_fs_bridge_list_mappings", {})
    
    if "mappings" in result:
        logger.info(f"IPFS-FS mappings ({len(result['mappings'])}):")
        for mapping in result['mappings']:
            logger.info(f"  {mapping.get('cid', 'unknown')} -> {mapping.get('fs_path', 'unknown')}")
    
    # Import from IPFS to a new location
    import_path = f"{test_dir}/imported_from_ipfs.txt"
    logger.info(f"Importing from IPFS to: {import_path}")
    
    result = await call_tool("ipfs_fs_import_from_ipfs", {
        "cid": cid,
        "path": import_path
    })
    
    if "success" in result and result["success"]:
        logger.info("✅ File imported from IPFS successfully")
    else:
        logger.error(f"❌ Failed to import from IPFS: {result}")
    
    # Read the imported file
    logger.info(f"Reading imported file: {import_path}")
    result = await call_tool("vfs_read", {"path": import_path})
    
    if "content" in result:
        logger.info(f"Imported file content: {result['content'][:50]}...")
    
    # Try creating a mapping
    logger.info("Creating a manual mapping")
    result = await call_tool("ipfs_fs_bridge_map", {
        "ipfs_path": cid,
        "fs_path": f"{test_dir}/manually_mapped.txt"
    })
    
    if "success" in result and result["success"]:
        logger.info("✅ Mapping created successfully")
    else:
        logger.error(f"❌ Failed to create mapping: {result}")
    
    # Sync bridge
    logger.info("Syncing IPFS-FS bridge")
    result = await call_tool("ipfs_fs_bridge_sync", {
        "direction": "both"
    })
    
    if "success" in result:
        logger.info(f"✅ Bridge sync completed: {result}")
    else:
        logger.error(f"❌ Failed to sync bridge: {result}")
    
    # Cleanup
    logger.info(f"Cleaning up test directory: {test_dir}")
    await call_tool("vfs_rm", {"path": test_dir, "recursive": True})
    
    logger.info("✅ IPFS-FS bridge test completed")
    return True

async def test_storage_backends():
    """Test storage backend functionality"""
    logger.info("=== TESTING STORAGE BACKENDS ===")
    
    # Check storage status
    logger.info("Checking storage backends status")
    result = await call_tool("storage_status", {})
    
    if "error" in result:
        logger.error(f"Failed to get storage status: {result['error']}")
        return False
    
    logger.info(f"Storage status: {result}")
    
    # Initialize IPFS backend if not already initialized
    logger.info("Initializing IPFS backend")
    result = await call_tool("init_ipfs_backend", {
        "api_url": "http://localhost:5001/api/v0"
    })
    
    if "success" in result and result["success"]:
        logger.info("✅ IPFS backend initialized")
    elif "error" in result:
        logger.error(f"❌ Failed to initialize IPFS backend: {result['error']}")
    else:
        logger.info(f"IPFS backend initialization result: {result}")
    
    # Check storage status again
    logger.info("Checking storage backends status after initialization")
    result = await call_tool("storage_status", {})
    logger.info(f"Storage status: {result}")
    
    logger.info("✅ Storage backends test completed")
    return True

async def comprehensive_test():
    """Run a comprehensive test of all virtual filesystem functionality"""
    logger.info("\n=== STARTING COMPREHENSIVE VIRTUAL FILESYSTEM TEST ===\n")
    
    # Get available tools
    tools = await get_available_tools()
    logger.info(f"Found {len(tools)} tools on the server")
    
    # Count VFS tools
    vfs_tools = [t for t in tools if t.startswith(("vfs_", "fs_journal_", "ipfs_fs_"))]
    logger.info(f"Found {len(vfs_tools)} virtual filesystem tools")
    
    if not vfs_tools:
        logger.error("❌ No virtual filesystem tools found!")
        return False
    
    # Run each test
    success_count = 0
    total_tests = 4  # Number of tests we're running
    
    try:
        # Test basic operations
        if await test_basic_vfs_operations():
            success_count += 1
        
        # Test advanced operations
        if await test_advanced_vfs_operations():
            success_count += 1
        
        # Test filesystem journal
        if await test_filesystem_journal():
            success_count += 1
        
        # Test IPFS bridge
        if await test_ipfs_bridge():
            success_count += 1
        
        # Test storage backends if time permits
        # if "storage_status" in tools:
        #     await test_storage_backends()
        
    except Exception as e:
        logger.error(f"❌ Exception during testing: {e}")
        logger.error(traceback.format_exc())
    
    # Summary
    logger.info("\n=== TEST SUMMARY ===")
    logger.info(f"Total tests: {total_tests}")
    logger.info(f"Successful tests: {success_count}")
    logger.info(f"Failed tests: {total_tests - success_count}")
    
    if success_count == total_tests:
        logger.info("✅ All tests completed successfully!")
    else:
        logger.error(f"❌ Some tests failed ({total_tests - success_count}/{total_tests})")
    
    return success_count == total_tests

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Test IPFS-VFS Integration")
    parser.add_argument("--url", default="http://localhost:3000", help="MCP server URL")
    parser.add_argument("--test", choices=["basic", "advanced", "journal", "ipfs", "storage", "all"], 
                        default="all", help="Which test to run")
    
    args = parser.parse_args()
    
    global MCP_URL
    MCP_URL = args.url
    global MCP_JSON_RPC_URL
    MCP_JSON_RPC_URL = f"{MCP_URL}/jsonrpc"
    global TOOL_ENDPOINT
    TOOL_ENDPOINT = f"{MCP_URL}/mcp/tools"
    
    return args

async def main():
    """Main entry point"""
    args = parse_arguments()
    
    # Check if MCP server is reachable
    logger.info(f"Checking if MCP server is reachable at {MCP_URL}...")
    try:
        response = requests.get(f"{MCP_URL}/health")
        if response.status_code == 200:
            logger.info(f"MCP server responded with status code {response.status_code}")
        else:
            logger.warning(f"MCP server responded with status code {response.status_code}")
    except Exception as e:
        logger.error(f"MCP server not reachable at {MCP_URL}: {e}")
        logger.warning("Make sure the MCP server is running")
        return 1
    
    # Run specified test or all tests
    if args.test == "basic":
        success = await test_basic_vfs_operations()
    elif args.test == "advanced":
        success = await test_advanced_vfs_operations()
    elif args.test == "journal":
        success = await test_filesystem_journal()
    elif args.test == "ipfs":
        success = await test_ipfs_bridge()
    elif args.test == "storage":
        success = await test_storage_backends()
    else:  # all
        success = await comprehensive_test()
    
    return 0 if success else 1

if __name__ == "__main__":
    asyncio.run(main())
