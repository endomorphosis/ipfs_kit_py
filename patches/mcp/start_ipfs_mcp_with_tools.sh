#!/bin/bash
# Start MCP server with IPFS tools
# This script starts the MCP server with IPFS and filesystem tools

# Check if IPFS daemon is running
if ! ipfs id > /dev/null 2>&1; then
    echo "Warning: IPFS daemon not running. Starting IPFS daemon..."
    ipfs daemon &
    # Wait for daemon to start
    sleep 5
fi

# Start MCP server
echo "Starting MCP server with IPFS tools..."
python3 direct_mcp_server.py
