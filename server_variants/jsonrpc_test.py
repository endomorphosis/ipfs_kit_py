#!/usr/bin/env python3
"""
JSON-RPC Test for MCP Server

This script tests the JSON-RPC endpoint with basic ping requests to verify it's working properly.
"""

import requests
import json
import sys

def test_jsonrpc(port=9997):
    """Test the JSON-RPC endpoint with a ping request"""
    jsonrpc_url = f"http://localhost:{port}/jsonrpc"
    
    print(f"Testing JSON-RPC endpoint: {jsonrpc_url}")
    
    # Create a ping request
    payload = {
        "jsonrpc": "2.0",
        "method": "ping",
        "params": {},
        "id": 1
    }
    
    try:
        print("Sending ping request...")
        response = requests.post(jsonrpc_url, json=payload, timeout=5)
        print(f"Response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error: Non-200 status code: {response.status_code}")
            print(f"Response text: {response.text}")
            return False
            
        try:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            
            if "result" in data and data["result"] == "pong":
                print("✅ Success: Got 'pong' response!")
                return True
            else:
                print("❌ Error: Did not get 'pong' response")
                if "error" in data:
                    print(f"Error message: {data['error'].get('message', 'Unknown error')}")
                return False
                
        except json.JSONDecodeError:
            print(f"❌ Error: Invalid JSON response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error connecting to JSON-RPC endpoint: {e}")
        return False

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9997
    success = test_jsonrpc(port)
    sys.exit(0 if success else 1)
