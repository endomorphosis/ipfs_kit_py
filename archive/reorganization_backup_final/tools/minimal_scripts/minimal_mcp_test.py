#!/usr/bin/env python3
"""
Minimal MCP Test Script

This script tests the basic functionality of an MCP server without relying on complex dependencies.
"""

import json
import sys
import requests
from datetime import datetime

ENDPOINT = "http://localhost:9997/jsonrpc"
TEST_ENDPOINT = "http://localhost:9997/health"

def test_health():
    """Test the health endpoint of the MCP server."""
    print(f"Testing health endpoint: {TEST_ENDPOINT}")
    try:
        response = requests.get(TEST_ENDPOINT, timeout=10)
        print(f"Status code: {response.status_code}")
        if response.status_code == 200:
            print("Health endpoint is working!")
            print(f"Response: {response.json()}")
            return True
        else:
            print(f"Health endpoint returned error: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to health endpoint: {e}")
        return False

def call_jsonrpc(method, params=None):
    """Make a JSON-RPC call to the MCP server."""
    if params is None:
        params = {}
    
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": int(datetime.now().timestamp() * 1000)
    }
    
    print(f"Calling method: {method} with params: {params}")
    try:
        response = requests.post(ENDPOINT, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            print(f"Success! Response: {json.dumps(result, indent=2)}")
            return result
        else:
            print(f"Error: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None

def main():
    """Run basic MCP tests."""
    print(f"Testing MCP server at {ENDPOINT}")
    
    # First test the health endpoint
    if not test_health():
        print("WARNING: Health endpoint test failed, but continuing with RPC tests...")
    
    # Test the ping method
    print("\nTesting ping method")
    ping_result = call_jsonrpc("ping")
    if ping_result and "result" in ping_result and ping_result["result"] == "pong":
        print("Ping test PASSED!")
    else:
        print("Ping test FAILED!")
    
    # Test the list_tools method
    print("\nTesting list_tools method")
    tools_result = call_jsonrpc("list_tools")
    if tools_result and "result" in tools_result and "tools" in tools_result["result"]:
        tool_count = len(tools_result["result"]["tools"])
        print(f"Server has {tool_count} tools available")
    else:
        print("list_tools test FAILED!")
    
    # Done!
    print("\nBasic MCP tests complete")

if __name__ == "__main__":
    main()
