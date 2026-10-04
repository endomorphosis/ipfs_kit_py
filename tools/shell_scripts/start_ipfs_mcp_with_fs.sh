#!/bin/bash
# Start IPFS MCP Server with Comprehensive Filesystem Tools
# This script sets up and starts an IPFS MCP server with all virtual filesystem tools enabled

set -e  # Exit on error

echo "==== Starting IPFS MCP Server with Virtual Filesystem Integration ===="

# Check if IPFS is running
if ! pgrep -x "ipfs" > /dev/null; then
    echo "Starting IPFS daemon..."
    ipfs daemon --enable-pubsub-experiment &
    IPFS_PID=$!
    # Give IPFS time to start
    sleep 5
    echo "IPFS daemon started with PID $IPFS_PID"
else
    echo "IPFS daemon is already running"
fi

# Python environment check
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3 and try again."
    exit 1
fi

echo "Python 3 found: $(python3 --version)"

# Check for required Python modules
echo "Checking for required Python modules..."
python3 -c "import asyncio, aiohttp, fastapi, uvicorn" 2>/dev/null || {
    echo "Installing required Python modules..."
    pip install asyncio aiohttp fastapi uvicorn
}

# Verify all IPFS tools are available
echo "Verifying IPFS tools..."
python3 verify_ipfs_tools.py

# Check if verification was successful
if [ $? -ne 0 ]; then
    echo "Tool verification failed. Please check the errors above."
    exit 1
fi

# Create required directories
mkdir -p logs data

# Start the MCP server
echo "Starting MCP server with IPFS integration..."
python3 -c "
import os
import sys
import asyncio

# Add current directory to path
sys.path.append(os.getcwd())

# Import necessary modules
import ipfs_mcp_tools
from direct_mcp_server import DirectMCPServer

# Create and initialize MCP server
async def start_server():
    print('Initializing MCP server...')
    server = DirectMCPServer()
    print('Registering IPFS tools with MCP server...')
    success = ipfs_mcp_tools.register_tools(server)
    
    if not success:
        print('Failed to register IPFS tools. Exiting.')
        return
    
    print('Starting server...')
    await server.start(host='0.0.0.0', port=8000)
    print('Server started!')

# Run the server
asyncio.run(start_server())
" > logs/mcp_server.log 2>&1 &

MCP_PID=$!
echo "MCP server started with PID $MCP_PID"

# Save PIDs for cleanup
echo "$IPFS_PID" > ./ipfs_pid.txt
echo "$MCP_PID" > ./mcp_pid.txt

echo "==== IPFS MCP Server with Filesystem Integration is now running ===="
echo "The server is available at: http://localhost:8000"
echo "To stop the server, run: ./stop_ipfs_mcp.sh"
