#!/usr/bin/env python3
"""
Test MCP Tool Execution

This script tests if the MCP server can actually execute a tool.
It simulates how VS Code would call a tool on the MCP server.
"""

import json
import requests
import sys
from pprint import pprint

# The MCP server URL
SERVER_URL = "http://localhost:9998"

def test_tool_execution(tool_name, params=None):
    """Test executing a specific tool on the MCP server."""
    if params is None:
        params = {}
    
    print(f"Testing execution of tool: {tool_name}")
    print(f"Parameters: {json.dumps(params)}")
    
    # Create the JSON-RPC request
    jsonrpc_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "execute",
        "params": {
            "name": tool_name,
            "parameters": params
        }
    }
    
    # Send the request to the server
    try:
        response = requests.post(
            f"{SERVER_URL}/jsonrpc",
            json=jsonrpc_payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        
        # Parse the response
        result = response.json()
        print("\nResponse:")
        pprint(result)
        
        if "error" in result:
            print(f"\n❌ Tool execution failed: {result['error']['message']}")
            return False
        
        print("\n✅ Tool execution successful!")
        return True
    
    except Exception as e:
        print(f"\n❌ Error executing tool: {e}")
        return False

def main():
    # Test a simple tool first (one with no required parameters)
    test_tool_execution("ipfs_pin_ls")
    
    # Test a tool with parameters
    test_tool_execution("ipfs_cat", {"cid": "QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx"})

if __name__ == "__main__":
    main()
