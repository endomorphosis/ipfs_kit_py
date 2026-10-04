#!/usr/bin/env python3
"""
Simple MCP Server Test
"""

import requests
import json

# Base URL for the MCP server
base_url = "http://localhost:9994"
api_url = f"{base_url}/api/v0"

def test_server_root():
    """Test the server root endpoint."""
    print("Testing server root...")
    response = requests.get(base_url)
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Server response: {json.dumps(data, indent=2)}")
        return True
    else:
        print(f"Failed to connect to server at {base_url}")
        return False

def test_jsonrpc():
    """Test the JSON-RPC endpoint."""
    print("\nTesting JSON-RPC endpoint...")
    jsonrpc_url = f"{base_url}/jsonrpc"
    
    initialize_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "processId": 12345,
            "rootUri": None,
            "capabilities": {}
        }
    }
    
    response = requests.post(jsonrpc_url, json=initialize_request)
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"JSON-RPC response: {json.dumps(data, indent=2)}")
        return True
    else:
        print(f"Failed to connect to JSON-RPC endpoint at {jsonrpc_url}")
        return False

def test_sse():
    """Test the SSE endpoint."""
    print("\nTesting SSE endpoint...")
    sse_url = f"{api_url}/sse"
    
    try:
        with requests.get(sse_url, stream=True, timeout=3) as response:
            print(f"Status code: {response.status_code}")
            if response.status_code == 200:
                # Get just the first event
                for line in response.iter_lines(decode_unicode=True):
                    if line and line.startswith("data: "):
                        print(f"SSE event: {line}")
                        return True
                    
                print("No SSE events received")
                return False
            else:
                print(f"Failed to connect to SSE endpoint at {sse_url}")
                return False
    except requests.RequestException as e:
        print(f"Error connecting to SSE endpoint: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("MCP Server Connection Test")
    print("=" * 60)
    
    server_ok = test_server_root()
    if server_ok:
        jsonrpc_ok = test_jsonrpc()
        sse_ok = test_sse()
        
        print("\nTest Summary:")
        print(f"Server root: {'✅ PASS' if server_ok else '❌ FAIL'}")
        print(f"JSON-RPC endpoint: {'✅ PASS' if jsonrpc_ok else '❌ FAIL'}")
        print(f"SSE endpoint: {'✅ PASS' if sse_ok else '❌ FAIL'}")
        
        if server_ok and jsonrpc_ok and sse_ok:
            print("\n✅ All tests passed! MCP server is operational.")
        else:
            print("\n❌ Some tests failed. Please check the server configuration.")
    else:
        print("\n❌ Server root test failed. Is the MCP server running?")
