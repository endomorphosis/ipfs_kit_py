#!/usr/bin/env python3
"""
Simplified MCP Server Verification Script

This script tests the essential MCP server components without trying to
test streaming endpoints like SSE that are difficult to test in scripts.
"""

import sys
import os
import requests
import json
import subprocess
import time

def check_endpoint(url, description, expected_status=200):
    """Check if an endpoint is accessible."""
    print(f"Testing {description}...")
    try:
        response = requests.head(url, timeout=2)
        if response.status_code == expected_status:
            print(f"✅ {description} is accessible (status: {response.status_code})")
            return True
        else:
            print(f"❌ {description} returned unexpected status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to connect to {description}: {e}")
        return False

def test_mcp_server():
    """Test if the MCP server is running."""
    try:
        response = requests.get("http://localhost:9994/", timeout=2)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ MCP server is running: {data.get('message')}")
            return True
        else:
            print(f"❌ MCP server returned status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to connect to MCP server: {e}")
        return False

def test_jsonrpc_server():
    """Test if the JSON-RPC server is running."""
    try:
        response = requests.get("http://localhost:9995/", timeout=2)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ JSON-RPC server is running: {data.get('message')}")
            return True
        else:
            print(f"❌ JSON-RPC server returned status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to connect to JSON-RPC server: {e}")
        return False

def test_jsonrpc_initialize():
    """Test if the JSON-RPC server responds to initialize requests."""
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "processId": 123,
                "rootUri": None,
                "capabilities": {}
            }
        }
        
        response = requests.post(
            "http://localhost:9995/jsonrpc",
            json=payload,
            timeout=2
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("result") and data.get("result").get("capabilities"):
                print(f"✅ JSON-RPC initialize request successful")
                return True
            else:
                print(f"❌ JSON-RPC initialize request returned invalid response")
                return False
        else:
            print(f"❌ JSON-RPC initialize request returned status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to send JSON-RPC initialize request: {e}")
        return False

def check_vs_code_settings():
    """Check VS Code settings."""
    try:
        with open(os.path.expanduser("~/.config/Code - Insiders/User/settings.json"), "r") as f:
            settings = json.load(f)
            
        mcp_sse_url = settings.get("mcp", {}).get("servers", {}).get("my-mcp-server-3e65fd06", {}).get("url")
        jsonrpc_url = settings.get("localStorageNetworkingTools", {}).get("lspEndpoint", {}).get("url")
        
        if mcp_sse_url == "http://localhost:9994/api/v0/sse" and jsonrpc_url == "http://localhost:9995/jsonrpc":
            print(f"✅ VS Code settings are correct")
            return True
        else:
            print(f"❌ VS Code settings are incorrect:")
            print(f"  - MCP SSE URL: {mcp_sse_url} (should be http://localhost:9994/api/v0/sse)")
            print(f"  - JSON-RPC URL: {jsonrpc_url} (should be http://localhost:9995/jsonrpc)")
            return False
    except Exception as e:
        print(f"❌ Failed to check VS Code settings: {e}")
        return False

def main():
    """Run all verification checks."""
    print("=" * 60)
    print("Simple MCP Server Verification")
    print("=" * 60)
    
    # List of all tests
    tests = [
        test_mcp_server,
        test_jsonrpc_server,
        test_jsonrpc_initialize,
    ]
    
    # List of critical endpoints to check
    endpoints = [
        ("http://localhost:9994/api/v0/health", "MCP health endpoint"),
        ("http://localhost:9994/api/v0/ipfs/version", "IPFS version endpoint"),
        ("http://localhost:9994/api/v0/sse", "SSE endpoint", 200),  # Just check if it exists
        ("http://localhost:9995/jsonrpc", "JSON-RPC endpoint", 405),  # 405 Method Not Allowed is OK for HEAD
    ]
    
    # Run tests
    success_count = 0
    failure_count = 0
    
    for test in tests:
        if test():
            success_count += 1
        else:
            failure_count += 1
    
    print("\nChecking critical endpoints...")
    for url, description, *args in endpoints:
        expected_status = args[0] if args else 200
        if check_endpoint(url, description, expected_status):
            success_count += 1
        else:
            failure_count += 1
    
    # Try to check VS Code settings if possible
    import os
    if os.path.exists(os.path.expanduser("~/.config/Code - Insiders/User/settings.json")):
        if check_vs_code_settings():
            success_count += 1
        else:
            failure_count += 1
    
    # Print summary
    print("\n" + "=" * 60)
    print(f"Test Results: {success_count} passed, {failure_count} failed")
    print("=" * 60)
    
    if failure_count == 0:
        print("\n✅ All tests passed! Your MCP server setup is working correctly.")
        print("VS Code should now be able to connect to your MCP server.")
        return 0
    else:
        print("\n❌ Some tests failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
