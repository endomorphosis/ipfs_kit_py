#!/usr/bin/env python3
"""
Verify that all IPFS tools are registered properly with the MCP server.
This script checks the following:
1. That all tools are listed in the MCP server's registered tools
2. Tests a few sample tools to ensure they respond correctly
"""

import os
import sys
import json
import time
import logging
import requests
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# MCP server details
MCP_SERVER_URL = "http://127.0.0.1:3000"
MCP_SERVER_NAME = "direct-ipfs-kit-mcp"

def get_registered_tools() -> List[str]:
    """Get a list of all tools registered with the MCP server"""
    try:
        # Make a request to the MCP server to get the list of tools
        response = requests.get(f"{MCP_SERVER_URL}/mcpserver/tools")
        response.raise_for_status()
        
        tools_data = response.json()
        tools = [tool["name"] for tool in tools_data]
        
        return tools
    except Exception as e:
        logger.error(f"Error getting registered tools: {e}")
        return []

def get_expected_tools() -> List[str]:
    """Get a list of all tools that should be registered"""
    try:
        # Import the tools registry
        sys.path.append(os.getcwd())
        from ipfs_tools_registry import get_ipfs_tools
        
        tools = get_ipfs_tools()
        tool_names = [tool["name"] for tool in tools]
        
        return tool_names
    except Exception as e:
        logger.error(f"Error getting expected tools: {e}")
        return []

def test_tool(tool_name: str, params: Dict[str, Any] = {}) -> bool:
    """Test a specific tool to ensure it works correctly"""
    try:
        # Make sure we don't modify the original default dictionary
        params = params.copy()
            
        # Make a request to the MCP server to use the tool
        response = requests.post(
            f"{MCP_SERVER_URL}/mcpserver/use-tool",
            json={
                "server_name": MCP_SERVER_NAME,
                "tool_name": tool_name,
                "arguments": params
            }
        )
        response.raise_for_status()
        
        result = response.json()
        logger.info(f"Tool {tool_name} response: {json.dumps(result, indent=2)}")
        
        return True
    except Exception as e:
        logger.error(f"Error testing tool {tool_name}: {e}")
        return False

def main():
    """Main function"""
    # Get the list of all registered tools
    registered_tools = get_registered_tools()
    logger.info(f"Found {len(registered_tools)} registered tools")
    
    # Get the list of all expected tools
    expected_tools = get_expected_tools()
    logger.info(f"Found {len(expected_tools)} expected tools")
    
    # Check if all expected tools are registered
    missing_tools = []
    for tool in expected_tools:
        if tool not in registered_tools:
            missing_tools.append(tool)
    
    if missing_tools:
        logger.warning(f"Missing {len(missing_tools)} tools: {', '.join(missing_tools)}")
    else:
        logger.info("✅ All expected tools are registered")
        
    # Test a few sample tools
    test_tools = [
        # Original IPFS MFS tool
        ("ipfs_files_ls", {"path": "/"}),
        
        # FS Journal tool
        ("fs_journal_get_history", {"path": "/"}),
        
        # IPFS Bridge tool
        ("ipfs_fs_bridge_status", {"detailed": True}),
        
        # S3 Storage tool
        ("s3_store_file", {"local_path": "test_file.txt", "bucket": "test-bucket", "key": "test-key"}),
        
        # Filecoin Storage tool
        ("filecoin_store_file", {"local_path": "test_file.txt"}),
        
        # WebRTC tool
        ("webrtc_peer_connect", {"peer_id": "test-peer-id"}),
        
        # Credential Management tool
        ("credential_store", {"service": "test-service", "credential_data": {"api_key": "test-key"}})
    ]
    
    successful_tests = 0
    for tool_name, params in test_tools:
        if tool_name in registered_tools:
            if test_tool(tool_name, params):
                successful_tests += 1
    
    logger.info(f"✅ Successfully tested {successful_tests}/{len(test_tools)} tools")
    
    # Create a test file if it doesn't exist
    if not os.path.exists("test_file.txt"):
        with open("test_file.txt", "w") as f:
            f.write("This is a test file for IPFS tools.\n")
        logger.info("Created test_file.txt for testing")
    
    logger.info("Tool verification complete")

if __name__ == "__main__":
    main()
