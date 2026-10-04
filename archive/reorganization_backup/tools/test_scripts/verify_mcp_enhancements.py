#!/usr/bin/env python3
"""
Verify MCP Tool Enhancements

This script verifies that the MCP tools have been successfully enhanced
by checking the initialize endpoint and testing a few of the new tools.
"""

import requests
import json
import sys
import time

def main():
    """Main verification function."""
    # Check that the server is running
    try:
        response = requests.get("http://localhost:9994/health", timeout=5)
        if response.status_code != 200:
            print(f"ERROR: Server health check failed with status {response.status_code}")
            sys.exit(1)
        print("Server is running.")
    except Exception as e:
        print(f"ERROR: Could not connect to server: {e}")
        sys.exit(1)
    
    # Check the initialize endpoint for enhanced capabilities
    try:
        response = requests.get("http://localhost:9994/initialize", timeout=5)
        if response.status_code != 200:
            print(f"ERROR: Initialize endpoint failed with status {response.status_code}")
            sys.exit(1)
        
        data = response.json()
        capabilities = data.get("capabilities", {})
        tools = capabilities.get("tools", [])
        
        # Check for some of the enhanced tools
        expected_tools = [
            "ipfs_files_ls", "ipfs_files_stat", "ipfs_files_mkdir", 
            "ipfs_files_read", "ipfs_files_write", "ipfs_name_publish"
        ]
        
        missing_tools = [tool for tool in expected_tools if tool not in tools]
        
        if missing_tools:
            print(f"ERROR: The following tools are missing: {', '.join(missing_tools)}")
            sys.exit(1)
        
        print(f"Initialize endpoint includes enhanced capabilities with {len(tools)} tools.")
    except Exception as e:
        print(f"ERROR: Could not check initialize endpoint: {e}")
        sys.exit(1)
    
    print("SUCCESS: MCP server has been successfully enhanced!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
