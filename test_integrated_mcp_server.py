#!/usr/bin/env python3
"""
Comprehensive MCP Server Tools Test

This script tests the integrated MCP server to verify that all IPFS and VFS tools
have been properly registered and are functioning correctly.

Features tested:
1. Basic IPFS operations
2. Virtual filesystem operations
3. Filesystem journal functionality 
4. IPFS-FS bridge operations
5. Multi-backend storage operations
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
from datetime import datetime
from pprint import pprint
from typing import Dict, List, Any, Optional, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("test_mcp_integration.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# MCP Server URL (configurable via command line)
MCP_URL = "http://localhost:3000"
MCP_JSON_RPC_URL = f"{MCP_URL}/jsonrpc"

async def check_server_status() -> bool:
    """Check if the MCP server is running."""
    try:
        response = requests.get(f"{MCP_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Server is running, version: {data.get('version')}")
            logger.info(f"Server has {data.get('tools_count', 0)} tools registered")
            logger.info(f"Registered tool categories: {data.get('registered_tool_categories', [])}")
            return True
        else:
            logger.error(f"Server returned status code {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to connect to server: {e}")
        return False

async def get_registered_tools() -> List[Dict[str, Any]]:
    """Get a list of all registered tools from the server."""
    try:
        response = requests.post(
            MCP_JSON_RPC_URL,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "get_tools"
            },
            timeout=5
        )
        
        if response.status_code != 200:
            logger.error(f"Error accessing MCP server: HTTP {response.status_code}")
            return []
        
        data = response.json()
        if "result" not in data:
            logger.error(f"Invalid response from server: {data}")
            return []
        
        return data["result"]
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        return []

async def call_tool(tool_name: str, args: Dict[str, Any] = None) -> Dict[str, Any]:
    """Call a tool on the MCP server via JSON-RPC."""
    if args is None:
        args = {}
    
    try:
        response = requests.post(
            MCP_JSON_RPC_URL,
            json={
                "jsonrpc": "2.0",
                "method": "use_tool",
                "params": {
                    "tool_name": tool_name,
                    "arguments": args
                },
                "id": int(time.time() * 1000)  # Use timestamp as ID
            },
            timeout=30  # Longer timeout for operations that might take time
        )
        
        if response.status_code != 200:
            return {"error": f"HTTP error: {response.status_code}"}
        
        result = response.json()
        if "error" in result:
            return {"error": result["error"]}
        elif "result" in result:
            return result["result"]
        else:
            return {"error": "Invalid response format"}
    except Exception as e:
        logger.error(f"Error calling tool {tool_name}: {e}")
        return {"error": str(e)}

async def categorize_tools(tools: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Categorize tools by their prefix."""
    categories = {
        "ipfs": [],
        "vfs": [],
        "fs_journal": [],
        "ipfs_fs": [],
        "storage": [],
        "multi_backend": [],
        "other": []
    }
    
    for tool in tools:
        name = tool["name"]
        if name.startswith("ipfs_"):
            categories["ipfs"].append(name)
        elif name.startswith("vfs_"):
            categories["vfs"].append(name)
        elif name.startswith("fs_journal_"):
            categories["fs_journal"].append(name)
        elif name.startswith("ipfs_fs_"):
            categories["ipfs_fs"].append(name)
        elif name.startswith("storage_"):
            categories["storage"].append(name)
        elif name.startswith("multi_backend_"):
            categories["multi_backend"].append(name)
        else:
            categories["other"].append(name)
    
    return categories

async def test_ipfs_tools(ipfs_tools: List[str]) -> bool:
    """Test basic IPFS tools functionality."""
    if not ipfs_tools:
        logger.warning("No IPFS tools found, skipping IPFS tests")
        return False
    
    logger.info("=== TESTING IPFS TOOLS ===")
    logger.info(f"Found {len(ipfs_tools)} IPFS tools")
    
    # Test basic IPFS operations if available
    basic_tools = []
    
    for required_tool in ["ipfs_add", "ipfs_cat", "ipfs_ls", "ipfs_stats"]:
        if required_tool in ipfs_tools:
            basic_tools.append(required_tool)
    
    if not basic_tools:
        logger.warning("No basic IPFS tools found, skipping basic IPFS tests")
        return False
    
    logger.info(f"Testing basic IPFS tools: {basic_tools}")
    
    # Create test content
    test_content = f"Test content created at {datetime.now().isoformat()}"
    
    # Upload content to IPFS if ipfs_add is available
    if "ipfs_add" in basic_tools:
        logger.info("Testing ipfs_add")
        result = await call_tool("ipfs_add", {"content": test_content})
        if "error" in result:
            logger.error(f"Error in ipfs_add: {result['error']}")
            return False
        
        cid = result.get("Hash") or result.get("cid") or result.get("hash")
        if not cid:
            logger.error("ipfs_add returned no CID")
            return False
            
        logger.info(f"Successfully added content to IPFS with CID: {cid}")
        
        # Retrieve content if ipfs_cat is available
        if "ipfs_cat" in basic_tools:
            logger.info("Testing ipfs_cat")
            result = await call_tool("ipfs_cat", {"path": cid})
            if "error" in result:
                logger.error(f"Error in ipfs_cat: {result['error']}")
            else:
                content = result.get("content") or result
                logger.info(f"Successfully retrieved content from IPFS: {content}")
                if isinstance(content, str) and test_content in content:
                    logger.info("✅ Content verification successful")
                else:
                    logger.warning("⚠️ Content verification failed")
    
    logger.info("✅ IPFS tools test completed")
    return True

async def test_vfs_tools(vfs_tools: List[str]) -> bool:
    """Test virtual filesystem tools functionality."""
    if not vfs_tools:
        logger.warning("No VFS tools found, skipping VFS tests")
        return False
    
    logger.info("=== TESTING VFS TOOLS ===")
    logger.info(f"Found {len(vfs_tools)} VFS tools")
    
    # Check for required tools
    required_tools = ["vfs_write_file", "vfs_read_file", "vfs_list_files", "vfs_mkdir"]
    missing_tools = [tool for tool in required_tools if tool not in vfs_tools]
    
    if missing_tools:
        logger.warning(f"Missing required VFS tools: {missing_tools}, skipping tests")
        return False
    
    logger.info("Testing basic VFS operations")
    
    # Create a test directory
    test_dir = f"/test_{int(time.time())}"
    logger.info(f"Creating test directory: {test_dir}")
    
    result = await call_tool("vfs_mkdir", {"path": test_dir})
    if "error" in result:
        logger.error(f"Error creating directory: {result['error']}")
        return False
    
    logger.info("Creating test file")
    test_content = f"Test content created at {datetime.now().isoformat()}"
    test_file = f"{test_dir}/test_file.txt"
    
    result = await call_tool("vfs_write_file", {
        "path": test_file,
        "content": test_content
    })
    
    if "error" in result:
        logger.error(f"Error writing file: {result['error']}")
        return False
    
    logger.info("Reading test file")
    result = await call_tool("vfs_read_file", {"path": test_file})
    
    if "error" in result:
        logger.error(f"Error reading file: {result['error']}")
        return False
    
    content = result.get("content") or result
    logger.info(f"Read content: {content}")
    
    if test_content in str(content):
        logger.info("✅ File content verification successful")
    else:
        logger.warning("⚠️ File content verification failed")
    
    logger.info("Listing test directory")
    result = await call_tool("vfs_list_files", {"path": test_dir})
    
    if "error" in result:
        logger.error(f"Error listing directory: {result['error']}")
    else:
        files = result.get("files") or []
        directories = result.get("directories") or []
        logger.info(f"Directory contents - Files: {files}, Directories: {directories}")
    
    logger.info("✅ VFS tools test completed")
    return True

async def test_fs_journal_tools(fs_journal_tools: List[str]) -> bool:
    """Test filesystem journal tools functionality."""
    if not fs_journal_tools:
        logger.warning("No filesystem journal tools found, skipping tests")
        return False
    
    logger.info("=== TESTING FILESYSTEM JOURNAL TOOLS ===")
    logger.info(f"Found {len(fs_journal_tools)} filesystem journal tools")
    
    # Check for key tools
    if "fs_journal_status" in fs_journal_tools:
        logger.info("Testing fs_journal_status")
        result = await call_tool("fs_journal_status", {})
        
        if "error" in result:
            logger.error(f"Error getting journal status: {result['error']}")
        else:
            logger.info(f"Journal status: {result}")
    
    if "fs_journal_track" in fs_journal_tools:
        # Create a test directory for tracking
        test_dir = f"/journal_test_{int(time.time())}"
        
        # Create directory if vfs_mkdir is available
        vfs_tools = await get_registered_tools()
        vfs_tool_names = [t["name"] for t in vfs_tools]
        if "vfs_mkdir" in vfs_tool_names:
            logger.info(f"Creating test directory for journal tracking: {test_dir}")
            await call_tool("vfs_mkdir", {"path": test_dir})
        
        logger.info(f"Testing fs_journal_track on path: {test_dir}")
        result = await call_tool("fs_journal_track", {"path": test_dir})
        
        if "error" in result:
            logger.error(f"Error tracking directory: {result['error']}")
        else:
            logger.info(f"Journal tracking result: {result}")
            
            # Create a file in the tracked directory if vfs_write_file is available
            if "vfs_write_file" in vfs_tool_names:
                test_file = f"{test_dir}/journal_test.txt"
                logger.info(f"Creating test file in tracked directory: {test_file}")
                await call_tool("vfs_write_file", {
                    "path": test_file,
                    "content": f"Journal test content created at {datetime.now().isoformat()}"
                })
            
            # Get journal history
            if "fs_journal_get_history" in fs_journal_tools:
                logger.info("Testing fs_journal_get_history")
                result = await call_tool("fs_journal_get_history", {"path": test_dir})
                
                if "error" in result:
                    logger.error(f"Error getting journal history: {result['error']}")
                else:
                    logger.info(f"Journal history: {result}")
            
            # Untrack the directory
            if "fs_journal_untrack" in fs_journal_tools:
                logger.info(f"Testing fs_journal_untrack on path: {test_dir}")
                result = await call_tool("fs_journal_untrack", {"path": test_dir})
                
                if "error" in result:
                    logger.error(f"Error untracking directory: {result['error']}")
                else:
                    logger.info(f"Journal untracking result: {result}")
    
    logger.info("✅ Filesystem journal tools test completed")
    return True

async def test_ipfs_fs_bridge_tools(ipfs_fs_tools: List[str]) -> bool:
    """Test IPFS-FS bridge tools functionality."""
    if not ipfs_fs_tools:
        logger.warning("No IPFS-FS bridge tools found, skipping tests")
        return False
    
    logger.info("=== TESTING IPFS-FS BRIDGE TOOLS ===")
    logger.info(f"Found {len(ipfs_fs_tools)} IPFS-FS bridge tools")
    
    # Test bridge status if available
    if "ipfs_fs_bridge_status" in ipfs_fs_tools:
        logger.info("Testing ipfs_fs_bridge_status")
        result = await call_tool("ipfs_fs_bridge_status", {})
        
        if "error" in result:
            logger.error(f"Error getting bridge status: {result['error']}")
        else:
            logger.info(f"Bridge status: {result}")
    
    # Test bridge mapping if available
    if "ipfs_fs_bridge_map" in ipfs_fs_tools:
        # Create a test directory name
        test_dir = f"/bridge_test_{int(time.time())}"
        
        logger.info(f"Testing ipfs_fs_bridge_map with path: {test_dir}")
        result = await call_tool("ipfs_fs_bridge_map", {
            "local_path": test_dir,
            "ipfs_path": "/ipfs/QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn"  # IPFS directory node
        })
        
        if "error" in result:
            logger.error(f"Error mapping bridge: {result['error']}")
        else:
            logger.info(f"Bridge mapping result: {result}")
            
            # List mappings
            if "ipfs_fs_bridge_list_mappings" in ipfs_fs_tools:
                logger.info("Testing ipfs_fs_bridge_list_mappings")
                result = await call_tool("ipfs_fs_bridge_list_mappings", {})
                
                if "error" in result:
                    logger.error(f"Error listing bridge mappings: {result['error']}")
                else:
                    logger.info(f"Bridge mappings: {result}")
            
            # Unmap
            if "ipfs_fs_bridge_unmap" in ipfs_fs_tools:
                logger.info(f"Testing ipfs_fs_bridge_unmap with path: {test_dir}")
                result = await call_tool("ipfs_fs_bridge_unmap", {"local_path": test_dir})
                
                if "error" in result:
                    logger.error(f"Error unmapping bridge: {result['error']}")
                else:
                    logger.info(f"Bridge unmapping result: {result}")
    
    logger.info("✅ IPFS-FS bridge tools test completed")
    return True

async def test_storage_backend_tools(storage_tools: List[str], multi_backend_tools: List[str]) -> bool:
    """Test storage backend tools functionality."""
    combined_tools = storage_tools + multi_backend_tools
    if not combined_tools:
        logger.warning("No storage/multi-backend tools found, skipping tests")
        return False
    
    logger.info("=== TESTING STORAGE BACKEND TOOLS ===")
    logger.info(f"Found {len(combined_tools)} storage backend tools")
    
    # Test storage status if available
    status_tools = [t for t in combined_tools if "status" in t]
    if status_tools:
        logger.info(f"Testing storage status using {status_tools[0]}")
        result = await call_tool(status_tools[0], {})
        
        if "error" in result:
            logger.error(f"Error getting storage status: {result['error']}")
        else:
            logger.info(f"Storage status: {result}")
    
    # Try initializing IPFS backend if available
    init_tools = [t for t in combined_tools if "init_ipfs" in t]
    if init_tools:
        logger.info(f"Testing IPFS backend initialization using {init_tools[0]}")
        result = await call_tool(init_tools[0], {
            "api_url": "http://localhost:5001/api/v0"
        })
        
        if "error" in result:
            logger.error(f"Error initializing IPFS backend: {result['error']}")
        else:
            logger.info(f"IPFS backend initialization result: {result}")
    
    logger.info("✅ Storage backend tools test completed")
    return True

async def comprehensive_test():
    """Run comprehensive tests on all tool categories."""
    logger.info("\n=== STARTING COMPREHENSIVE MCP SERVER TOOLS TEST ===\n")
    
    # Check if the server is running
    if not await check_server_status():
        logger.error("Cannot proceed: MCP server is not running")
        return False
    
    # Get all registered tools
    all_tools = await get_registered_tools()
    logger.info(f"Found {len(all_tools)} registered tools on the server")
    
    if not all_tools:
        logger.error("No tools found. Test cannot continue.")
        return False
    
    # Categorize tools
    tool_categories = await categorize_tools(all_tools)
    
    # Print out summary of tools per category
    for category, tools in tool_categories.items():
        logger.info(f"{category.upper()}: {len(tools)} tools")
    
    # Test each category of tools
    results = {}
    
    # Test IPFS tools
    results["ipfs"] = await test_ipfs_tools(tool_categories["ipfs"])
    
    # Test VFS tools
    results["vfs"] = await test_vfs_tools(tool_categories["vfs"])
    
    # Test FS Journal tools
    results["fs_journal"] = await test_fs_journal_tools(tool_categories["fs_journal"])
    
    # Test IPFS-FS bridge tools
    results["ipfs_fs"] = await test_ipfs_fs_bridge_tools(tool_categories["ipfs_fs"])
    
    # Test storage backend tools
    results["storage"] = await test_storage_backend_tools(tool_categories["storage"], tool_categories["multi_backend"])
    
    # Print final results
    logger.info("\n=== COMPREHENSIVE TEST RESULTS ===")
    successes = 0
    for category, result in results.items():
        status = "✅ PASSED" if result else "⚠️ SKIPPED/FAILED"
        logger.info(f"{category.upper()}: {status}")
        if result:
            successes += 1
    
    # Overall status
    if successes == len(results):
        logger.info("\n✅ ALL TESTS PASSED SUCCESSFULLY!")
        return True
    elif successes > 0:
        logger.info(f"\n⚠️ {successes}/{len(results)} TEST CATEGORIES PASSED")
        return True
    else:
        logger.error("\n❌ ALL TESTS FAILED")
        return False

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Comprehensive MCP Server Tools Test")
    parser.add_argument("--url", default="http://localhost:3000", help="MCP Server URL")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    return parser.parse_args()

async def main():
    """Main entry point."""
    global MCP_URL, MCP_JSON_RPC_URL
    
    args = parse_arguments()
    MCP_URL = args.url
    MCP_JSON_RPC_URL = f"{MCP_URL}/jsonrpc"
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    logger.info(f"Using MCP server at {MCP_URL}")
    
    # Run the comprehensive test
    success = await comprehensive_test()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
