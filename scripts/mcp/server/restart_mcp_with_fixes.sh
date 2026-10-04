#!/bin/bash
# Script to restart the MCP server with fixed backend controllers

# Stop any running MCP servers (adjust PIDs as needed)
pkill -f "run_mcp_server"
pkill -f "uvicorn run_mcp_server"

# Wait a moment for shutdown
sleep 2

# Start the server again
cd "$(dirname "$0")"
nohup python run_mcp_server_fixed.py > mcp_server_restarted.log 2>&1 &

echo "MCP server restarted with fixed backend controllers"
