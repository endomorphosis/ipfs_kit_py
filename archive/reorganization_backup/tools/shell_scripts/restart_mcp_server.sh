#!/bin/bash

echo "Restarting MCP server with JSON-RPC fixes..."

# Check if stop script exists
if [ -f "./stop_enhanced_mcp_server.sh" ]; then
    echo "Stopping server using stop_enhanced_mcp_server.sh..."
    bash ./stop_enhanced_mcp_server.sh
elif [ -f "./stop_mcp_server.sh" ]; then
    echo "Stopping server using stop_mcp_server.sh..."
    bash ./stop_mcp_server.sh
else
    echo "No stop script found. Trying to kill running processes..."
    pkill -f "python.*direct_mcp_server.py" || true
    sleep 2
fi

# Verify server stopped
if pgrep -f "python.*direct_mcp_server.py" > /dev/null; then
    echo "Warning: MCP server processes still running. Forcefully killing..."
    pkill -9 -f "python.*direct_mcp_server.py" || true
    sleep 2
fi

# Check if start script exists
if [ -f "./start_ipfs_mcp_with_fs.sh" ]; then
    echo "Starting server using start_ipfs_mcp_with_fs.sh..."
    bash ./start_ipfs_mcp_with_fs.sh
elif [ -f "./start_enhanced_mcp_server.sh" ]; then
    echo "Starting server using start_enhanced_mcp_server.sh..."
    bash ./start_enhanced_mcp_server.sh
elif [ -f "./start_mcp_server.sh" ]; then
    echo "Starting server using start_mcp_server.sh..."
    bash ./start_mcp_server.sh
else
    echo "No start script found. Starting server directly..."
    python direct_mcp_server.py &
    echo "MCP server started with PID $!"
fi

# Wait for server to start
echo "Waiting for server to start..."
sleep 3

# Test the JSON-RPC endpoint
echo "Testing JSON-RPC endpoint..."
curl -s -X POST http://127.0.0.1:3000/jsonrpc -H "Content-Type: application/json" -d '{"jsonrpc": "2.0", "method": "get_tools", "params": {}, "id": 1}'
echo -e "\n"

echo "MCP server restart complete."
