#!/usr/bin/env python3
"""
VS Code MCP Verification Script

This script verifies that the MCP server is returning tools in a format
that VS Code expects. It simulates how VS Code would interact with the server.
"""

import sys
import json
import requests
import argparse
from typing import List, Dict, Any
import time

def verify_tools_endpoint(url: str) -> bool:
    """Verify that the /tools endpoint returns a flat array."""
    try:
        # Request the tools endpoint
        response = requests.get(f"{url}/tools", timeout=5)
        response.raise_for_status()
        
        # Parse the response
        data = response.json()
        
        # Check that it's a list (array)
        if not isinstance(data, list):
            print(f"❌ The /tools endpoint returned {type(data).__name__}, expected list")
            print(f"Response: {json.dumps(data)[:200]}...")
            return False
        
        # Check that it has tools
        if len(data) == 0:
            print(f"⚠️ The /tools endpoint returned an empty list")
            return False
        
        # Check that the tools have the expected fields
        first_tool = data[0]
        expected_fields = ["name", "description"]
        for field in expected_fields:
            if field not in first_tool:
                print(f"❌ The tool object is missing the required field: {field}")
                print(f"Tool: {json.dumps(first_tool)}")
                return False
        
        # Print success message
        print(f"✅ The /tools endpoint returned {len(data)} tools in the correct format")
        print(f"Example tool: {json.dumps(first_tool)}")
        return True
    
    except Exception as e:
        print(f"❌ Error accessing the /tools endpoint: {e}")
        return False

def verify_health_endpoint(url: str) -> bool:
    """Verify that the /health endpoint returns the expected data."""
    try:
        # Request the health endpoint
        response = requests.get(f"{url}/health", timeout=5)
        response.raise_for_status()
        
        # Parse the response
        data = response.json()
        
        # Check required fields
        expected_fields = ["status", "version", "tools_count"]
        for field in expected_fields:
            if field not in data:
                print(f"❌ The health endpoint is missing the required field: {field}")
                print(f"Response: {json.dumps(data)}")
                return False
        
        # Check tool count
        if data["tools_count"] == 0:
            print(f"⚠️ The health endpoint reports 0 tools")
            return False
        
        # Print success message
        print(f"✅ The /health endpoint reports {data['tools_count']} tools")
        print(f"Health status: {data['status']}")
        return True
    
    except Exception as e:
        print(f"❌ Error accessing the /health endpoint: {e}")
        return False

def verify_jsonrpc_endpoint(url: str) -> bool:
    """Verify that the /jsonrpc endpoint works with the get_tools method."""
    try:
        # Request the jsonrpc endpoint with the get_tools method
        payload = {
            "jsonrpc": "2.0",
            "method": "get_tools",
            "params": [],
            "id": 1
        }
        response = requests.post(
            f"{url}/jsonrpc", 
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        response.raise_for_status()
        
        # Parse the response
        data = response.json()
        
        # Check required fields
        if "result" not in data:
            print(f"❌ The JSON-RPC response is missing the result field")
            print(f"Response: {json.dumps(data)}")
            return False
        
        # Check that the result is a list
        if not isinstance(data["result"], list):
            print(f"❌ The JSON-RPC result is {type(data['result']).__name__}, expected list")
            print(f"Result: {json.dumps(data['result'])[:200]}...")
            return False
        
        # Check that it has tools
        if len(data["result"]) == 0:
            print(f"⚠️ The JSON-RPC result returned an empty list")
            return False
        
        # Print success message
        print(f"✅ The /jsonrpc endpoint returned {len(data['result'])} tools via the get_tools method")
        print(f"Example tool: {json.dumps(data['result'][0])}")
        return True
    
    except Exception as e:
        print(f"❌ Error accessing the /jsonrpc endpoint: {e}")
        return False

def main():
    """Main function to parse arguments and run verification."""
    parser = argparse.ArgumentParser(description="VS Code MCP Verification")
    parser.add_argument("--url", default="http://localhost:9998", help="MCP server URL")
    args = parser.parse_args()
    
    print(f"Verifying MCP server at {args.url}...")
    
    # Verify the tools endpoint
    tools_ok = verify_tools_endpoint(args.url)
    
    # Verify the health endpoint
    health_ok = verify_health_endpoint(args.url)
    
    # Verify the jsonrpc endpoint
    jsonrpc_ok = verify_jsonrpc_endpoint(args.url)
    
    # Print summary
    print("\n=== Verification Summary ===")
    print(f"Tools Endpoint: {'✅ PASS' if tools_ok else '❌ FAIL'}")
    print(f"Health Endpoint: {'✅ PASS' if health_ok else '❌ FAIL'}")
    print(f"JSON-RPC Endpoint: {'✅ PASS' if jsonrpc_ok else '❌ FAIL'}")
    
    # Return exit code
    if tools_ok and health_ok and jsonrpc_ok:
        print("\n✅ All verification checks passed! Your MCP server is VS Code compatible.")
        return 0
    else:
        print("\n❌ Some verification checks failed. Your MCP server may not work correctly with VS Code.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
