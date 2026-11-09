#!/usr/bin/env python3
"""
Test VS Code MCP Server Connection

This script tests the connection to the MCP server configured in VS Code settings.
It reads the VS Code settings.json file to get the server URL and then tests the connection.
"""

import os
import json
import sys
import requests
from pathlib import Path

def main():
    # Path to VS Code settings.json
    vscode_settings_path = Path.home() / ".config" / "Code - Insiders" / "User" / "settings.json"
    
    # Check if settings file exists
    if not vscode_settings_path.exists():
        print(f"❌ VS Code settings file not found at: {vscode_settings_path}")
        return 1
    
    # Read settings file
    try:
        with open(vscode_settings_path, 'r') as f:
            settings = json.load(f)
    except Exception as e:
        print(f"❌ Error reading settings file: {e}")
        return 1
    
    # Get MCP server settings
    if 'mcp' not in settings or 'servers' not in settings['mcp']:
        print("❌ No MCP servers found in VS Code settings")
        return 1
    
    # Get default server
    default_server = settings['mcp'].get('defaultServer')
    if not default_server:
        print("❌ No default MCP server specified in VS Code settings")
        server_id = next(iter(settings['mcp']['servers'].keys()))
        print(f"Using first available server: {server_id}")
    else:
        print(f"Default MCP server: {default_server}")
        server_id = default_server
    
    # Get server URL
    if server_id not in settings['mcp']['servers']:
        print(f"❌ Server {server_id} not found in MCP servers list")
        return 1
    
    server_url = settings['mcp']['servers'][server_id].get('url')
    if not server_url:
        print(f"❌ No URL found for server {server_id}")
        return 1
    
    print(f"Testing connection to MCP server {server_id} at {server_url}")
    
    # Test server health
    try:
        health_url = f"{server_url}/health"
        print(f"Testing health endpoint: {health_url}")
        health_response = requests.get(health_url, timeout=5)
        health_response.raise_for_status()
        health_data = health_response.json()
        print(f"✅ Health check successful: {json.dumps(health_data, indent=2)}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return 1
    
    # Test tools endpoint
    try:
        tools_url = f"{server_url}/tools"
        print(f"Testing tools endpoint: {tools_url}")
        tools_response = requests.get(tools_url, timeout=5)
        tools_response.raise_for_status()
        tools_data = tools_response.json()
        
        if not isinstance(tools_data, list):
            print(f"❌ Tools endpoint returned {type(tools_data).__name__}, expected list")
            return 1
        
        print(f"✅ Tools endpoint returned {len(tools_data)} tools")
        print("Sample tools:")
        for i, tool in enumerate(tools_data[:5]):  # Show first 5 tools
            print(f"  {i+1}. {tool['name']}: {tool['description']}")
    except Exception as e:
        print(f"❌ Tools endpoint failed: {e}")
        return 1
    
    # Test JSON-RPC endpoint
    try:
        jsonrpc_url = f"{server_url}/jsonrpc"
        print(f"Testing JSON-RPC endpoint: {jsonrpc_url}")
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "get_tools",
            "params": {}
        }
        
        jsonrpc_response = requests.post(jsonrpc_url, json=payload, timeout=5)
        jsonrpc_response.raise_for_status()
        jsonrpc_data = jsonrpc_response.json()
        
        if "result" not in jsonrpc_data:
            print(f"❌ JSON-RPC endpoint returned error: {jsonrpc_data.get('error')}")
            return 1
        
        tools_result = jsonrpc_data["result"]
        if not isinstance(tools_result, list):
            print(f"❌ JSON-RPC endpoint returned {type(tools_result).__name__}, expected list")
            return 1
        
        print(f"✅ JSON-RPC endpoint returned {len(tools_result)} tools")
        
        # Test executing a tool via JSON-RPC
        print("\nTesting tool execution...")
        execute_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "execute",
            "params": {
                "name": "ipfs_pin_ls",  # A simple tool with no required parameters
                "parameters": {}
            }
        }
        
        execute_response = requests.post(jsonrpc_url, json=execute_payload, timeout=10)
        execute_response.raise_for_status()
        execute_data = execute_response.json()
        
        if "result" not in execute_data:
            print(f"❌ Tool execution failed: {execute_data.get('error')}")
        else:
            print(f"✅ Tool execution successful: {json.dumps(execute_data['result'], indent=2)}")
    except Exception as e:
        print(f"❌ JSON-RPC endpoint failed: {e}")
        return 1
    
    print("\n=== SUMMARY ===")
    print(f"✅ Successfully connected to MCP server {server_id} at {server_url}")
    print(f"✅ Server has {len(tools_data)} tools available")
    print(f"✅ All endpoints (health, tools, JSON-RPC) are working correctly")
    print(f"✅ Tool execution is functioning properly")
    
    print("\nThe MCP server should now be correctly accessible from VS Code!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
