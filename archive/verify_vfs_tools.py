#!/usr/bin/env python3
"""
VFS Tools Verification Script

This script verifies that the VFS tools have been properly registered with the MCP server.
"""

import os
import sys
import json
import requests
import logging
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# MCP server URL
MCP_SERVER_URL = "http://localhost:3000"

def check_server_status() -> bool:
    """Check if the MCP server is running"""
    try:
        response = requests.get(f"{MCP_SERVER_URL}/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"MCP server is running: {data.get('message')}")
            logger.info(f"Registered tools count: {data.get('registered_tools_count', 0)}")
            return True
        else:
            logger.error(f"Error accessing MCP server: HTTP {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        logger.error("Could not connect to MCP server. Is it running?")
        return False
    except Exception as e:
        logger.error(f"Error checking server status: {e}")
        return False

def get_registered_tools() -> List[Dict[str, Any]]:
    """Get the list of registered tools from the MCP server"""
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "get_tools",
                "params": {}
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
    except requests.exceptions.ConnectionError:
        logger.error("Could not connect to MCP server. Is it running?")
        return []
    except Exception as e:
        logger.error(f"Error getting registered tools: {e}")
        return []

def find_vfs_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Find VFS tools in the list of registered tools"""
    vfs_prefixes = ["vfs_", "fs_", "virtual_", "filesystem_", "ipfs_fs_"]
    return [tool for tool in tools if any(tool["name"].startswith(prefix) for prefix in vfs_prefixes)]

def main():
    """Main function"""
    print("🚀 Virtual Filesystem MCP Tools Verification")
    print("============================================")
    
    # Check if the server is running
    if not check_server_status():
        print("❌ Virtual filesystem tools integration verification failed")
        sys.exit(1)
    
    # Get the list of registered tools
    print("🔍 Checking MCP server for virtual filesystem tools...")
    tools = get_registered_tools()
    
    # Find VFS tools
    vfs_tools = find_vfs_tools(tools)
    
    if not vfs_tools:
        print("❌ No virtual filesystem tools found")
        print("\n❌ Virtual filesystem tools integration verification failed")
        sys.exit(1)
    
    print(f"✅ Found {len(vfs_tools)} virtual filesystem tools:")
    for tool in vfs_tools:
        print(f"  - {tool['name']}: {tool['description']}")
    
    print("\n✅ Virtual filesystem tools integration verified successfully!")
    sys.exit(0)

if __name__ == "__main__":
    main()
