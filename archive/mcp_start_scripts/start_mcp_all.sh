#!/bin/bash
# Start the all-in-one MCP server
# This script ensures proper startup and PID management

# Stop any running MCP servers
if [ -f /tmp/mcp_server.pid ]; then
    echo "Stopping existing MCP server..."
    PID=$(cat /tmp/mcp_server.pid)
    if ps -p $PID > /dev/null; then
        kill $PID
        sleep 1
    fi
    rm /tmp/mcp_server.pid
fi

if [ -f /tmp/mcp_jsonrpc_proxy.pid ]; then
    echo "Stopping existing JSON-RPC proxy..."
    PID=$(cat /tmp/mcp_jsonrpc_proxy.pid)
    if ps -p $PID > /dev/null; then
        kill $PID
        sleep 1
    fi
    rm /tmp/mcp_jsonrpc_proxy.pid
fi

# Determine if we should use background mode
USE_BACKGROUND=false
if [ "$1" == "--background" ]; then
    USE_BACKGROUND=true
    shift
fi

# Set default port if not provided
MCP_PORT="${1:-9994}"

# Start the all-in-one MCP server
echo "Starting all-in-one MCP server on port $MCP_PORT..."
if [ "$USE_BACKGROUND" = true ]; then
    python mcp_server_fixed_all.py --port $MCP_PORT --debug &
    # Save PID
    echo $! > /tmp/mcp_server.pid
    echo "MCP server started in background with PID $(cat /tmp/mcp_server.pid)"
else
    # Run in foreground
    python mcp_server_fixed_all.py --port $MCP_PORT --debug
fi

# Success message
echo "MCP server startup completed"
echo "API is available at: http://localhost:$MCP_PORT/api/v0"
echo "JSON-RPC is available at: http://localhost:$MCP_PORT/jsonrpc"
echo "Documentation is available at: http://localhost:$MCP_PORT/docs"
