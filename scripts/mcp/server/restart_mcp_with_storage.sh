#!/bin/bash
# Restart MCP server with storage backends enabled

# Kill existing MCP server processes
pkill -f "run_mcp_server"
sleep 2

# Start the updated server
python run_mcp_server_with_storage.py > mcp_storage_server.log 2>&1 &
echo $! > mcp_storage_server.pid

echo "MCP Server started with storage backends enabled (PID: $(cat mcp_storage_server.pid))"
