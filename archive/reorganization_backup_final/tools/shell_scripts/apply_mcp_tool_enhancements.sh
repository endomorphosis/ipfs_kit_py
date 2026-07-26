#!/bin/bash
# Apply MCP Tool Enhancements
# 
# This script applies the enhanced tools to the MCP server.
# It first checks if the server is running, then applies the enhancements,
# and finally verifies that the tools are available.

set -e  # Exit on error

echo "=== Starting MCP Tool Enhancement Process ==="
echo "$(date): Beginning enhancement process" 

# Check if the MCP server is running
echo "Checking if MCP server is running..."
if ! pgrep -f "unified_mcp_server.py" > /dev/null; then
    echo "MCP server is not running. Starting it..."
    
    # Try to start the server
    if [ -f "start_unified_mcp_server.sh" ]; then
        chmod +x start_unified_mcp_server.sh
        ./start_unified_mcp_server.sh &
        sleep 3  # Give it time to start
    elif [ -f "start_mcp_server.sh" ]; then
        chmod +x start_mcp_server.sh
        ./start_mcp_server.sh &
        sleep 3  # Give it time to start
    else
        echo "ERROR: Could not find server start script. Please start the MCP server first."
        exit 1
    fi
fi

# Now, apply the enhancements
echo "Applying MCP tool enhancements..."
python3 enhance_mcp_tools.py --apply --debug

# Wait for the enhancements to take effect
sleep 2

# Verify the enhancements
echo "Verifying MCP tool enhancements..."

# Create a test verification script
cat > verify_mcp_enhancements.py << 'EOF'
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
EOF

chmod +x verify_mcp_enhancements.py
python3 verify_mcp_enhancements.py

# Check the result
if [ $? -eq 0 ]; then
    echo "=== MCP Tool Enhancement Process Completed Successfully ==="
    echo "All enhanced tools are now available through the MCP protocol."
    echo "You can now access these tools through the MCP integration."
else
    echo "=== MCP Tool Enhancement Process Failed ==="
    echo "Please check the error messages above for details."
fi

echo "$(date): Enhancement process completed"
