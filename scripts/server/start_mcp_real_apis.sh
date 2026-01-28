#!/bin/bash
# Start MCP server with real API implementations

# Kill existing MCP server processes
pkill -f "run_mcp_server"
sleep 2

# Start the server with real APIs
python run_mcp_server_real_apis.py > mcp_real_apis.log 2>&1 &
echo $! > mcp_real_apis.pid

echo "MCP Server started with real API implementations (PID: $(cat mcp_real_apis.pid))"
echo "Log file: mcp_real_apis.log"
