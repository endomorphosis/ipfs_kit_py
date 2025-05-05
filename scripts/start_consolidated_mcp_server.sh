#!/bin/bash
# Start script for the Consolidated MCP Server
# This script starts the IPFS daemon if not already running
# and then launches the consolidated MCP server

echo "Starting Consolidated IPFS-VFS MCP Server..."

# Check if IPFS daemon is running
if ! pgrep -x "ipfs" > /dev/null; then
    echo "IPFS daemon not detected. Starting IPFS daemon..."
    ipfs daemon --routing=dhtclient > /dev/null 2>&1 &
    IPFS_PID=$!
    echo "IPFS daemon started with PID: $IPFS_PID"

    # Give IPFS daemon a moment to fully initialize
    sleep 3
    echo "IPFS daemon initialized"
else
    echo "IPFS daemon is already running"
fi

# Start the MCP server
echo "Starting Consolidated MCP Server..."
python3 consolidated_final_mcp_server.py --host 127.0.0.1 --port 3000 "$@"
