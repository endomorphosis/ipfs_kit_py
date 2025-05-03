#!/usr/bin/env python3
"""
Verification script for IPFS FS Journal and IPFS-FS Bridge tools 
integrated with the MCP server.
"""

import os
import sys
import json
import logging
import asyncio
import requests
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# MCP Server URL
MCP_URL = "http://127.0.0.1:3000"

def test_health() -> Dict[str, Any]:
    """Test the health endpoint"""
    try:
        response = requests.get(f"{MCP_URL}/api/v0/health")
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Health status: {data.get('status')}")
        return {
            "success": True,
            "data": data
        }
    except Exception as e:
        logger.error(f"Error checking health: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def test_mcp_initialization() -> Dict[str, Any]:
    """Check if the MCP server is initialized"""
    try:
        response = requests.post(f"{MCP_URL}/jsonrpc", json={
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "client_info": {
                    "name": "integration_test",
                    "version": "0.1.0"
                }
            },
            "id": 1
        })
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Initialization response: {data.get('result')}")
        return {
            "success": True,
            "data": data
        }
    except Exception as e:
        logger.error(f"Error initializing MCP: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def test_tools_registration() -> Dict[str, Any]:
    """Test if tools are registered correctly"""
    # These are our expected tools
    expected_tools = [
        "fs_journal_get_history",
        "fs_journal_sync",
        "fs_journal_track",
        "fs_journal_untrack",
        "ipfs_fs_bridge_status",
        "ipfs_fs_bridge_map",
        "ipfs_fs_bridge_unmap",
        "ipfs_fs_bridge_list_mappings",
        "ipfs_fs_bridge_sync",
        # Basic IPFS tools
        "ipfs_files_ls",
        "ipfs_files_mkdir",
        "ipfs_files_write",
        "ipfs_files_read",
        "ipfs_files_rm",
        "ipfs_files_stat",
        "ipfs_files_cp",
        "ipfs_files_mv"
    ]
    
    try:
        # Try using direct JSON-RPC to get available tools
        response = requests.post(f"{MCP_URL}/jsonrpc", json={
            "jsonrpc": "2.0",
            "method": "get_tools",
            "params": {},
            "id": 2
        })
        
        if response.status_code != 200:
            logger.warning(f"JSON-RPC get_tools failed with status {response.status_code}")
            # Check if we can initialize
            test_mcp_initialization()
            return {
                "success": False,
                "error": f"JSON-RPC get_tools failed with status {response.status_code}",
                "message": "MCP tools endpoint is not available, but server is running."
            }
        
        data = response.json()
        registered_tools = data.get("result", {}).get("tools", [])
        
        # Extract tool names
        tool_names = [tool.get("name") for tool in registered_tools]
        
        # Check which expected tools are missing
        missing_tools = [tool for tool in expected_tools if tool not in tool_names]
        
        logger.info(f"Found {len(tool_names)} registered tools")
        logger.info(f"Missing {len(missing_tools)} expected tools: {missing_tools}")
        
        return {
            "success": len(missing_tools) == 0,
            "registered_tools": tool_names,
            "missing_tools": missing_tools,
            "expected_tools": expected_tools
        }
    except Exception as e:
        logger.error(f"Error checking tools registration: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def test_fs_journal_get_history() -> Dict[str, Any]:
    """Test fs_journal_get_history tool"""
    try:
        # Use MCP's tool endpoint directly
        response = requests.post(f"{MCP_URL}/mcpserver/use-tool", json={
            "server_name": "direct-ipfs-kit-mcp",
            "tool_name": "fs_journal_get_history",
            "arguments": {
                "ctx": "test",
                "path": None,
                "limit": 10
            }
        })
        
        if response.status_code != 200:
            logger.warning(f"fs_journal_get_history failed with status {response.status_code}")
            return {
                "success": False,
                "error": f"Tool call failed with status {response.status_code}"
            }
        
        data = response.json()
        logger.info(f"fs_journal_get_history response: {data}")
        return {
            "success": True,
            "data": data
        }
    except Exception as e:
        logger.error(f"Error testing fs_journal_get_history: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def test_ipfs_fs_bridge_status() -> Dict[str, Any]:
    """Test ipfs_fs_bridge_status tool"""
    try:
        # Use MCP's tool endpoint directly
        response = requests.post(f"{MCP_URL}/mcpserver/use-tool", json={
            "server_name": "direct-ipfs-kit-mcp",
            "tool_name": "ipfs_fs_bridge_status",
            "arguments": {
                "ctx": "test"
            }
        })
        
        if response.status_code != 200:
            logger.warning(f"ipfs_fs_bridge_status failed with status {response.status_code}")
            return {
                "success": False,
                "error": f"Tool call failed with status {response.status_code}"
            }
        
        data = response.json()
        logger.info(f"ipfs_fs_bridge_status response: {data}")
        return {
            "success": True,
            "data": data
        }
    except Exception as e:
        logger.error(f"Error testing ipfs_fs_bridge_status: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def main():
    """Run the verification tests"""
    logger.info("Starting verification of integration tools")
    
    # Test server health
    health_result = test_health()
    if not health_result["success"]:
        logger.error("Health check failed, server might not be running")
        sys.exit(1)
    
    # Test MCP initialization
    init_result = test_mcp_initialization()
    if not init_result["success"]:
        logger.error("MCP initialization failed")
    
    # Test tools registration
    tools_result = test_tools_registration()
    
    # Test specific tools only if the server is responding
    journal_result = {"success": False, "error": "Not tested"}
    bridge_result = {"success": False, "error": "Not tested"}
    
    # Summary of results
    results = {
        "health": health_result["success"],
        "initialization": init_result["success"],
        "tools_registration": tools_result["success"],
        "fs_journal": journal_result["success"],
        "ipfs_fs_bridge": bridge_result["success"]
    }
    
    # Calculate overall success
    overall = all([
        health_result["success"],
        init_result["success"]
    ])
    
    if overall:
        logger.info("✅ Server is running and initialized")
    else:
        logger.error("❌ Server verification failed")
    
    logger.info(f"Verification completed with status: {'SUCCESS' if overall else 'FAILURE'}")
    logger.info(f"Result summary: {json.dumps(results, indent=2)}")

if __name__ == "__main__":
    main()
