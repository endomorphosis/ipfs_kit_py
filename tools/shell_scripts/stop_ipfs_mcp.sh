#!/bin/bash
# Stop MCP server and optionally IPFS daemon
# This script stops the MCP server and optionally the IPFS daemon

# Stop MCP server
echo "Stopping MCP server..."
pkill -f "python3 direct_mcp_server.py"

# Ask if IPFS daemon should be stopped
read -p "Do you want to stop the IPFS daemon too? (y/n): " stop_ipfs

if [[ $stop_ipfs == "y" || $stop_ipfs == "Y" ]]; then
    echo "Stopping IPFS daemon..."
    ipfs shutdown
fi

echo "Done."
