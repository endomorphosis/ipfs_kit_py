#!/usr/bin/env python3
"""
Example IPFS Virtual Filesystem Usage

This script demonstrates how to use the IPFS virtual filesystem
features exposed through the MCP server.
"""

import requests
import json
import base64

MCP_SERVER = "http://localhost:9994"

def mcp_request(endpoint, method="GET", data=None):
    """Make a request to the MCP server."""
    url = f"{MCP_SERVER}/{endpoint}"
    if method == "GET":
        response = requests.get(url)
    else:
        response = requests.post(url, json=data)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        return None
    
    return response.json()

# Check server health
health = mcp_request("health")
print(f"Server health: {health}")

# Get capabilities
init = mcp_request("initialize")
print(f"Available tools: {init.get('capabilities', {}).get('tools', [])}")

# Example 1: Create a directory in MFS
print("\nExample 1: Creating a directory in MFS")
mkdir_data = {
    "name": "ipfs_files_mkdir",
    "server": "ipfs-kit-mcp",
    "args": {
        "path": "/test_dir",
        "parents": True
    }
}
mkdir_result = mcp_request("mcp/tools", method="POST", data=mkdir_data)
print(f"Mkdir result: {mkdir_result}")

# Example 2: Write a file to MFS
print("\nExample 2: Writing a file to MFS")
content = "Hello, IPFS Virtual Filesystem!"
write_data = {
    "name": "ipfs_files_write",
    "server": "ipfs-kit-mcp",
    "args": {
        "path": "/test_dir/hello.txt",
        "content": content,
        "create": True,
        "truncate": True
    }
}
write_result = mcp_request("mcp/tools", method="POST", data=write_data)
print(f"Write result: {write_result}")

# Example 3: List files in directory
print("\nExample 3: Listing files in directory")
ls_data = {
    "name": "ipfs_files_ls",
    "server": "ipfs-kit-mcp",
    "args": {
        "path": "/test_dir",
        "long": True
    }
}
ls_result = mcp_request("mcp/tools", method="POST", data=ls_data)
print(f"List result: {ls_result}")

# Example 4: Read file content
print("\nExample 4: Reading file content")
read_data = {
    "name": "ipfs_files_read",
    "server": "ipfs-kit-mcp",
    "args": {
        "path": "/test_dir/hello.txt"
    }
}
read_result = mcp_request("mcp/tools", method="POST", data=read_data)
if read_result and read_result.get("content"):
    content = read_result.get("content")
    if read_result.get("content_encoding") == "base64":
        content = base64.b64decode(content).decode("utf-8")
    print(f"File content: {content}")
else:
    print(f"Read error: {read_result}")

print("\nCompleted IPFS virtual filesystem test!")
