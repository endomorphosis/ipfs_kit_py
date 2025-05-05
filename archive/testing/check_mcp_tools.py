#!/usr/bin/env python3
"""
Check Tools in MCP Server

This script checks what tools are registered in the MCP server.
"""

import requests
import json
import sys

def main():
    """Check tools in the MCP server."""
    url = "http://localhost:3000/jsonrpc"
    payload = {
        "jsonrpc": "2.0",
        "method": "get_tools",
        "id": 1
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        result = response.json()
        tools = result.get("result", [])
        
        print(f"Found {len(tools)} tools registered:")
        for i, tool in enumerate(tools, 1):
            print(f"{i}. {tool.get('name')}: {tool.get('description', '')}")
            
        # Check specific tools
        tool_names = [tool.get("name") for tool in tools]
        
        # Check for IPFS tools
        ipfs_tools = [name for name in tool_names if name.startswith("ipfs_")]
        print(f"\nIPFS Tools: {len(ipfs_tools)}")
        for tool in ipfs_tools:
            print(f"  - {tool}")
            
        # Check for VFS tools
        vfs_tools = [name for name in tool_names if name.startswith("vfs_")]
        print(f"\nVFS Tools: {len(vfs_tools)}")
        for tool in vfs_tools:
            print(f"  - {tool}")
            
        # Check for FS Journal tools
        fs_journal_tools = [name for name in tool_names if name.startswith("fs_journal_")]
        print(f"\nFS Journal Tools: {len(fs_journal_tools)}")
        for tool in fs_journal_tools:
            print(f"  - {tool}")
            
        # Check for Multi-Backend tools
        multi_backend_tools = [name for name in tool_names if name.startswith("storage_")]
        print(f"\nMulti-Backend Tools: {len(multi_backend_tools)}")
        for tool in multi_backend_tools:
            print(f"  - {tool}")
            
        return 0
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to MCP server: {e}")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
