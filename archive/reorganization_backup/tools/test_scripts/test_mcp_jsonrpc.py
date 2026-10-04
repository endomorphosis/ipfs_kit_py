#!/usr/bin/env python3
"""
Test MCP FastMCP Tools via JSON-RPC

This script tests if the FastMCP tools are accessible via JSON-RPC protocol.
"""

import json
import urllib.request
import urllib.parse

def test_jsonrpc_call(method, params=None):
    """Make a JSON-RPC call to the MCP server"""
    url = "http://localhost:3001/jsonrpc"
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {}
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result
    except Exception as e:
        return {"error": str(e)}

def main():
    """Test MCP tools"""
    print("=== Testing MCP JSON-RPC Tools ===")
    
    # Test tools/list
    print("\n1. Testing tools/list...")
    result = test_jsonrpc_call("tools/list")
    print(f"Result: {json.dumps(result, indent=2)}")
    
    # Test initialize (if needed)
    print("\n2. Testing initialize...")
    init_params = {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {
            "name": "test-client",
            "version": "1.0.0"
        }
    }
    result = test_jsonrpc_call("initialize", init_params)
    print(f"Result: {json.dumps(result, indent=2)}")
    
    # Test calling a specific tool
    print("\n3. Testing tools/call with ipfs_id...")
    tool_params = {
        "name": "ipfs_id",
        "arguments": {}
    }
    result = test_jsonrpc_call("tools/call", tool_params)
    print(f"Result: {json.dumps(result, indent=2)}")

if __name__ == "__main__":
    main()
