#!/usr/bin/env python3
"""
Check MCP Tools

This script checks the tools registered on an MCP server and provides
detailed information about the server status.
"""

import sys
import json
import requests
import argparse
from urllib.parse import urljoin

def check_server(url="http://localhost:9998"):
    """Check the status of an MCP server and list its tools."""
    print(f"Checking MCP server at: {url}")
    
    # Try the health endpoint
    try:
        health_url = urljoin(url, "/health")
        print(f"Checking health endpoint: {health_url}")
        health_response = requests.get(health_url, timeout=5)
        
        if health_response.status_code == 200:
            health_data = health_response.json()
            print("\n=== Server Health ===")
            print(f"Status: {health_data.get('status', 'unknown')}")
            print(f"Version: {health_data.get('version', 'unknown')}")
            print(f"Uptime: {health_data.get('uptime_seconds', 0):.2f} seconds")
            print(f"Tools Count: {health_data.get('tools_count', 0)}")
            
            if 'registered_tool_categories' in health_data:
                print(f"Tool Categories: {', '.join(health_data['registered_tool_categories'])}")
        else:
            print(f"Health check failed with status code: {health_response.status_code}")
            print(f"Response: {health_response.text}")
    except requests.RequestException as e:
        print(f"Error accessing health endpoint: {e}")
    
    # Try the tools endpoint
    try:
        tools_url = urljoin(url, "/tools")
        print(f"\nChecking tools endpoint: {tools_url}")
        tools_response = requests.get(tools_url, timeout=5)
        
        if tools_response.status_code == 200:
            try:
                tools_data = tools_response.json()
                print("\n=== Registered Tools ===")
                
                if isinstance(tools_data, list):
                    if len(tools_data) > 0:
                        for tool in tools_data:
                            print(f"- {tool.get('name', 'Unknown')}: {tool.get('description', 'No description')}")
                    else:
                        print("No tools registered on the server.")
                else:
                    print(f"Unexpected response format: {tools_data}")
            except json.JSONDecodeError:
                print(f"Failed to parse tools response as JSON: {tools_response.text[:100]}...")
        else:
            print(f"Tools check failed with status code: {tools_response.status_code}")
            print(f"Response: {tools_response.text}")
    except requests.RequestException as e:
        print(f"Error accessing tools endpoint: {e}")
    
    # Try the SSE endpoint (this might be used by VSCode)
    try:
        sse_url = urljoin(url, "/sse")
        print(f"\nChecking SSE endpoint: {sse_url}")
        # Just check if the endpoint exists, don't try to read the stream
        sse_response = requests.get(sse_url, stream=True, timeout=2)
        print(f"SSE endpoint status: {sse_response.status_code}")
        # Close the connection immediately
        sse_response.close()
    except requests.RequestException as e:
        print(f"Error accessing SSE endpoint: {e}")
    
    # Try the jsonrpc endpoint (might be used by some tools)
    try:
        jsonrpc_url = urljoin(url, "/jsonrpc")
        print(f"\nChecking JSONRPC endpoint: {jsonrpc_url}")
        # Just check if the endpoint exists
        headers = {'Content-Type': 'application/json'}
        data = {
            "jsonrpc": "2.0",
            "method": "system.listMethods",
            "params": [],
            "id": 1
        }
        jsonrpc_response = requests.post(jsonrpc_url, headers=headers, json=data, timeout=5)
        print(f"JSONRPC endpoint status: {jsonrpc_response.status_code}")
        
        if jsonrpc_response.status_code == 200:
            try:
                jsonrpc_data = jsonrpc_response.json()
                if 'result' in jsonrpc_data and isinstance(jsonrpc_data['result'], list):
                    print(f"Available JSONRPC methods: {len(jsonrpc_data['result'])}")
                    if len(jsonrpc_data['result']) > 0:
                        for method in jsonrpc_data['result'][:10]:  # Show first 10
                            print(f"- {method}")
                        if len(jsonrpc_data['result']) > 10:
                            print(f"... and {len(jsonrpc_data['result']) - 10} more")
            except json.JSONDecodeError:
                print(f"Failed to parse JSONRPC response as JSON")
    except requests.RequestException as e:
        print(f"Error accessing JSONRPC endpoint: {e}")

def main():
    parser = argparse.ArgumentParser(description="Check MCP server status and tools")
    parser.add_argument("--url", default="http://localhost:9998", help="MCP server URL")
    args = parser.parse_args()
    
    check_server(args.url)

if __name__ == "__main__":
    main()
