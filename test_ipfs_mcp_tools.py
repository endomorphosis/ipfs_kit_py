#!/usr/bin/env python3
"""
Comprehensive Test Suite for IPFS and VFS Tools in MCP Server

This test script verifies that all IPFS and VFS tools are properly registered with the MCP server
and checks their basic functionality. It serves as both a verification tool and documentation
of the expected behavior of each tool.
"""

import os
import sys
import json
import logging
import requests
import argparse
import traceback
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("test_ipfs_mcp_tools.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("test-ipfs-mcp")

# Constants
SERVER_URL = "http://localhost:3000"  # Default MCP server URL
JSONRPC_URL = f"{SERVER_URL}/jsonrpc"

# Tool categories for classification and testing
TOOL_CATEGORIES = {
    "ipfs_core": [
        "ipfs_add", "ipfs_cat", "ipfs_pin_add", "ipfs_pin_rm", "ipfs_pin_ls",
        "ipfs_version", "ipfs_add_file", "ipfs_get", "ipfs_object_stat", "ipfs_ls",
        "ipfs_status", "ipfs_swarm_peers", "ipfs_swarm_connect"
    ],
    "ipfs_mfs": [
        "ipfs_files_ls", "ipfs_files_mkdir", "ipfs_files_write", "ipfs_files_read",
        "ipfs_files_rm", "ipfs_files_stat", "ipfs_files_cp", "ipfs_files_mv", "ipfs_files_flush"
    ],
    "ipfs_ipns": [
        "ipfs_name_publish", "ipfs_name_resolve", "ipfs_name_list"
    ],
    "ipfs_dag": [
        "ipfs_dag_put", "ipfs_dag_get"
    ],
    "fs_journal": [
        "fs_journal_get_history", "fs_journal_sync", "fs_journal_track", "fs_journal_untrack"
    ],
    "ipfs_fs_bridge": [
        "ipfs_fs_bridge_status", "ipfs_fs_bridge_map", "ipfs_fs_bridge_unmap",
        "ipfs_fs_bridge_list_mappings", "ipfs_fs_bridge_sync"
    ],
    "multi_backend": [
        "multi_backend_status", "multi_backend_map", "multi_backend_unmap",
        "multi_backend_list_mappings", "multi_backend_sync", "multi_backend_search"
    ],
    "storage": [
        "s3_store_file", "s3_retrieve_file", "filecoin_store_file", "filecoin_retrieve_deal",
        "storacha_store", "storacha_retrieve"
    ],
    "other": [
        "health_check"
    ]
}

# Mapping of tool names to example parameters for testing
TOOL_TEST_PARAMS = {
    # IPFS Core tools
    "ipfs_add": {"content": "test content"},
    "ipfs_cat": {"cid": "QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx"},  # Will be replaced with actual CID
    "ipfs_pin_add": {"cid": "QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx"},  # Will be replaced with actual CID
    "ipfs_pin_rm": {"cid": "QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx"},  # Will be replaced with actual CID
    "ipfs_pin_ls": {},
    "ipfs_version": {},
    
    # MFS tools
    "ipfs_files_mkdir": {"path": "/test_dir"},
    "ipfs_files_write": {"path": "/test_file.txt", "content": "test content"},
    "ipfs_files_read": {"path": "/test_file.txt"},
    "ipfs_files_ls": {"path": "/"},
    "ipfs_files_stat": {"path": "/test_file.txt"},
    "ipfs_files_rm": {"path": "/test_file.txt"},
    
    # IPNS tools
    "ipfs_name_publish": {"path": "/ipfs/QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx"},  # Will be replaced with actual CID
    "ipfs_name_resolve": {"name": "/ipns/QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx"},  # Will be replaced with actual name
    
    # FS Journal tools
    "fs_journal_get_history": {"ctx": "test", "path": "/test"},
    "fs_journal_sync": {"ctx": "test"},
    
    # Bridge tools
    "ipfs_fs_bridge_status": {"ctx": "test"},
    "ipfs_fs_bridge_map": {"ctx": "test", "ipfs_path": "/ipfs/QmTest", "fs_path": "/tmp/test"},
    
    # Multi-backend tools
    "multi_backend_status": {"ctx": "test"},
    "multi_backend_list_mappings": {"ctx": "test"},
    
    # General tools
    "health_check": {}
}

def check_server_health() -> bool:
    """Check if the MCP server is healthy."""
    try:
        response = requests.get(f"{SERVER_URL}/health")
        response.raise_for_status()
        
        result = response.json()
        logger.info(f"Server is healthy: {result}")
        
        if "status" in result and result["status"] == "healthy":
            logger.info(f"Server uptime: {result.get('uptime_seconds', 'unknown')} seconds")
            return True
        else:
            logger.warning("Server returned a response but may not be healthy")
            return False
    except Exception as e:
        logger.error(f"Server health check failed: {e}")
        return False

def get_available_tools() -> List[str]:
    """Get a list of all available tools from the MCP server."""
    try:
        response = requests.get(SERVER_URL)
        response.raise_for_status()
        
        data = response.json()
        tools = data.get("registered_tools", [])
        tool_count = data.get("registered_tools_count", 0)
        
        logger.info(f"Found {tool_count} registered tools")
        return tools
    except Exception as e:
        logger.error(f"Failed to get available tools: {e}")
        return []

def categorize_tools(all_tools: List[str]) -> Dict[str, List[str]]:
    """Categorize tools based on their prefix."""
    categorized = {category: [] for category in TOOL_CATEGORIES.keys()}
    categorized["unknown"] = []  # For tools that don't match known categories
    
    # Assign tools to categories
    for tool in all_tools:
        assigned = False
        for category, tool_list in TOOL_CATEGORIES.items():
            if tool in tool_list:
                categorized[category].append(tool)
                assigned = True
                break
        
        if not assigned:
            # Try to categorize by prefix
            if tool.startswith("ipfs_files_"):
                categorized["ipfs_mfs"].append(tool)
            elif tool.startswith("ipfs_"):
                categorized["ipfs_core"].append(tool)
            elif tool.startswith("fs_journal_"):
                categorized["fs_journal"].append(tool)
            elif tool.startswith("ipfs_fs_bridge_"):
                categorized["ipfs_fs_bridge"].append(tool)
            elif tool.startswith("multi_backend_"):
                categorized["multi_backend"].append(tool)
            elif tool.startswith("s3_") or tool.startswith("filecoin_") or tool.startswith("storacha_"):
                categorized["storage"].append(tool)
            else:
                categorized["unknown"].append(tool)
    
    # Filter out empty categories
    return {k: v for k, v in categorized.items() if v}

async def test_tool(tool_name: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Test a specific tool using JSON-RPC."""
    if params is None:
        params = TOOL_TEST_PARAMS.get(tool_name, {})
    
    try:
        # Prepare JSON-RPC request
        request_data = {
            "jsonrpc": "2.0",
            "method": "execute_tool",
            "params": {
                "tool_name": tool_name,
                "params": params
            },
            "id": int(time.time() * 1000)  # Use timestamp as ID
        }
        
        # Send request
        logger.debug(f"Testing tool {tool_name} with params: {params}")
        response = requests.post(JSONRPC_URL, json=request_data)
        response.raise_for_status()
        
        # Process response
        result = response.json()
        if "result" in result:
            logger.info(f"Tool {tool_name} succeeded: {result['result']}")
            return {
                "success": True,
                "tool_name": tool_name,
                "params": params,
                "result": result["result"]
            }
        elif "error" in result:
            logger.warning(f"Tool {tool_name} returned error: {result['error']}")
            return {
                "success": False,
                "tool_name": tool_name,
                "params": params,
                "error": result["error"]
            }
        else:
            logger.warning(f"Tool {tool_name} returned unexpected response: {result}")
            return {
                "success": False,
                "tool_name": tool_name,
                "params": params,
                "unexpected_response": result
            }
    except Exception as e:
        logger.error(f"Error testing tool {tool_name}: {e}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "tool_name": tool_name,
            "params": params,
            "exception": str(e)
        }

def test_tool_sync(tool_name: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Synchronous version of test_tool for use in scenarios where asyncio isn't set up."""
    # This function calls the JSON-RPC endpoint directly without using asyncio
    if params is None:
        params = TOOL_TEST_PARAMS.get(tool_name, {})
    
    try:
        # Special case for health_check which has a dedicated endpoint
        if tool_name == "health_check":
            response = requests.get(f"{SERVER_URL}/health")
            response.raise_for_status()
            result = response.json()
            return {
                "success": True,
                "tool_name": tool_name,
                "result": result
            }
        
        # Prepare JSON-RPC request
        request_data = {
            "jsonrpc": "2.0",
            "method": "execute_tool",
            "params": {
                "tool_name": tool_name,
                "params": params
            },
            "id": int(time.time() * 1000)  # Use timestamp as ID
        }
        
        # Send request
        logger.debug(f"Testing tool {tool_name} with params: {params}")
        response = requests.post(JSONRPC_URL, json=request_data)
        
        # For HTTP errors, we'll still try to parse the response
        try:
            result = response.json()
        except ValueError:
            return {
                "success": False,
                "tool_name": tool_name,
                "params": params,
                "http_status": response.status_code,
                "response": response.text
            }
        
        if "result" in result:
            logger.info(f"Tool {tool_name} succeeded")
            return {
                "success": True,
                "tool_name": tool_name,
                "params": params,
                "result": result["result"]
            }
        elif "error" in result:
            logger.warning(f"Tool {tool_name} returned error: {result['error']}")
            return {
                "success": False,
                "tool_name": tool_name,
                "params": params,
                "error": result["error"]
            }
        else:
            logger.warning(f"Tool {tool_name} returned unexpected response: {result}")
            return {
                "success": False,
                "tool_name": tool_name,
                "params": params,
                "unexpected_response": result
            }
    except Exception as e:
        logger.error(f"Error testing tool {tool_name}: {e}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "tool_name": tool_name,
            "params": params,
            "exception": str(e)
        }

def run_comprehensive_tests() -> Dict[str, Any]:
    """Run comprehensive tests on all available tools."""
    # Start with a health check
    if not check_server_health():
        return {
            "overall_success": False,
            "error": "Server health check failed",
            "message": "The MCP server is not healthy or not running."
        }
    
    # Get all available tools
    all_tools = get_available_tools()
    if not all_tools:
        return {
            "overall_success": False,
            "error": "No tools found",
            "message": "The MCP server did not return any registered tools."
        }
    
    # Categorize tools
    categorized_tools = categorize_tools(all_tools)
    
    # Test results will be stored here
    test_results = {
        "timestamp": datetime.now().isoformat(),
        "server_url": SERVER_URL,
        "total_tools": len(all_tools),
        "categories": {category: len(tools) for category, tools in categorized_tools.items()},
        "results": {}
    }
    
    # Start with adding some test content to get a CID for later tests
    logger.info("Adding test content to IPFS to get a CID for subsequent tests")
    if "ipfs_add" in all_tools:
        add_result = test_tool_sync("ipfs_add", {"content": "This is test content for the IPFS MCP tools test suite."})
        test_results["results"]["ipfs_add"] = add_result
        
        if add_result["success"] and "result" in add_result and "cid" in add_result["result"]:
            test_cid = add_result["result"]["cid"]
            logger.info(f"Got test CID: {test_cid}")
            
            # Update test params with the actual CID
            for tool_name in ["ipfs_cat", "ipfs_pin_add", "ipfs_pin_rm"]:
                if tool_name in TOOL_TEST_PARAMS:
                    TOOL_TEST_PARAMS[tool_name]["cid"] = test_cid
            
            if "ipfs_name_publish" in TOOL_TEST_PARAMS:
                TOOL_TEST_PARAMS["ipfs_name_publish"]["path"] = f"/ipfs/{test_cid}"
    
    # Run tests for each tool
    for tool_name in all_tools:
        logger.info(f"Testing tool: {tool_name}")
        # Skip ipfs_add as we already tested it
        if tool_name != "ipfs_add":
            result = test_tool_sync(tool_name)
            test_results["results"][tool_name] = result
    
    # Calculate success rates
    total_tests = len(test_results["results"])
    successful_tests = sum(1 for result in test_results["results"].values() if result.get("success", False))
    
    test_results["overall_success"] = successful_tests == total_tests
    test_results["success_rate"] = successful_tests / total_tests if total_tests > 0 else 0
    test_results["summary"] = f"Successfully tested {successful_tests} out of {total_tests} tools"
    
    return test_results

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Comprehensive Test Suite for IPFS and VFS Tools in MCP Server")
    parser.add_argument("--host", type=str, default="localhost", help="MCP server hostname (default: localhost)")
    parser.add_argument("--port", type=int, default=3000, help="MCP server port (default: 3000)")
    parser.add_argument("--output", type=str, help="Output file for test results (default: no file output)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode - don't perform actual tests")
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Set server URL
    global SERVER_URL, JSONRPC_URL
    SERVER_URL = f"http://{args.host}:{args.port}"
    JSONRPC_URL = f"{SERVER_URL}/jsonrpc"
    
    logger.info(f"Testing IPFS MCP tools on server {SERVER_URL}")
    
    # If dry run, just return success without performing tests
    if args.dry_run:
        logger.info("Dry run mode - skipping actual tests")
        print("\nDry Run Mode - No tests performed")
        print("To run actual tests, remove the --dry-run flag")
        return 0
    
    # Run comprehensive tests
    test_results = run_comprehensive_tests()
    
    # Output results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(test_results, f, indent=2)
        logger.info(f"Test results written to {args.output}")
    
    # Print summary
    logger.info(f"Test Summary: {test_results['summary']}")
    print("\nTest Results Summary:")
    print("=====================")
    print(f"Server: {SERVER_URL}")
    print(f"Total tools tested: {test_results['total_tools']}")
    
    # Print categories
    print("\nTool Categories:")
    for category, count in test_results['categories'].items():
        print(f"  - {category}: {count} tools")
    
    # Print success rate
    success_rate_pct = test_results['success_rate'] * 100
    print(f"\nSuccess rate: {success_rate_pct:.1f}% ({test_results['summary']})")
    
    # Return 0 for success, 1 for failure
    return 0 if test_results["overall_success"] else 1

if __name__ == "__main__":
    sys.exit(main())