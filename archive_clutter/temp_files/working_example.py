#!/usr/bin/env python3
"""
Working IPFS MCP Example

This script demonstrates how to use the existing IPFS operations
through the MCP server.
"""

import requests
import json
import base64
import time

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
print(f"Server health: {json.dumps(health, indent=2)}")

# Get capabilities
init = mcp_request("initialize")
capabilities = {}
tools = []
if init:
    capabilities = init.get('capabilities', {})
    tools = capabilities.get('tools', [])
print(f"Available tools: {json.dumps(tools, indent=2)}")

# Example 1: Add content to IPFS
print("\nExample 1: Adding content to IPFS")
content = "Hello, IPFS from Python!"
add_data = {
    "name": "ipfs_add",
    "server": "ipfs-kit-mcp",
    "args": {
        "content": content,
        "filename": "hello.txt",
        "pin": True
    }
}
add_result = mcp_request("mcp/tools", method="POST", data=add_data)
print(f"Add result: {json.dumps(add_result, indent=2)}")

# If the add was successful, retrieve the CID for later use
if add_result and add_result.get("success"):
    content_cid = add_result.get("cid")
    print(f"Content was added with CID: {content_cid}")
else:
    # Use a default CID for demonstration if the add failed
    content_cid = "QmPChd2hVbrJ6bfo3WBcTW4iZnpHm8TEzWkLHmLpXhF68A"
    print(f"Using demo CID: {content_cid}")

# Example 2: Retrieve content from IPFS
print("\nExample 2: Retrieving content from IPFS")
cat_data = {
    "name": "ipfs_cat",
    "server": "ipfs-kit-mcp",
    "args": {
        "cid": content_cid
    }
}
cat_result = mcp_request("mcp/tools", method="POST", data=cat_data)

if cat_result and cat_result.get("success"):
    content = cat_result.get("content", "")
    if cat_result.get("content_encoding") == "base64":
        try:
            content = base64.b64decode(content).decode("utf-8")
        except:
            pass
    print(f"Retrieved content: {content}")
else:
    print(f"Cat error: {cat_result}")

# Example 3: Pin content to local node
print("\nExample 3: Pinning content to local node")
pin_data = {
    "name": "ipfs_pin",
    "server": "ipfs-kit-mcp",
    "args": {
        "cid": content_cid
    }
}
pin_result = mcp_request("mcp/tools", method="POST", data=pin_data)
print(f"Pin result: {json.dumps(pin_result, indent=2)}")

# Example 4: List files in directory using the standard list_files tool
print("\nExample 4: Listing files in current directory")
list_data = {
    "name": "list_files",
    "server": "ipfs-kit-mcp",
    "args": {
        "directory": ".",
        "recursive": False,
        "include_hidden": False
    }
}
list_result = mcp_request("mcp/tools", method="POST", data=list_data)
print(f"Directory listing result: {json.dumps(list_result, indent=2)}")

# Example 5: Write a file using the standard write_file tool
print("\nExample 5: Writing a file to local filesystem")
write_data = {
    "name": "write_file",
    "server": "ipfs-kit-mcp",
    "args": {
        "path": "ipfs_example_file.txt",
        "content": f"This file contains IPFS content with CID: {content_cid}\nTimestamp: {time.time()}"
    }
}
write_result = mcp_request("mcp/tools", method="POST", data=write_data)
print(f"Write file result: {json.dumps(write_result, indent=2)}")

# Example 6: Read the file we just wrote using read_file tool
print("\nExample 6: Reading the file we just created")
read_data = {
    "name": "read_file",
    "server": "ipfs-kit-mcp",
    "args": {
        "path": "ipfs_example_file.txt"
    }
}
read_result = mcp_request("mcp/tools", method="POST", data=read_data)
if read_result and read_result.get("success"):
    content = read_result.get("content", "")
    print(f"File content:\n{content}")
else:
    print(f"Read error: {read_result}")

print("\nCompleted IPFS test with existing tools!")
print("Note: The virtual filesystem (MFS) tools were not accessible in this run.")
print("To use those features, further updates to the MCP server are needed.")
