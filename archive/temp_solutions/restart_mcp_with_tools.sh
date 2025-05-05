#!/bin/bash
# Restart MCP server with the enhanced IPFS tools

echo "Stopping any running MCP servers..."
pkill -f "python.*direct_mcp_server" || true
sleep 2

echo "Starting MCP server with enhanced tools..."
python direct_mcp_server_with_tools.py --host=127.0.0.1 --port=3001 &
SERVER_PID=$!
echo "MCP server started with PID $SERVER_PID"
echo "Waiting for server to initialize..."
sleep 3

echo "✅ MCP server is now running with enhanced IPFS tools"
echo "You can use the new tools through the JSON-RPC interface at http://127.0.0.1:3001/jsonrpc"
echo "To test, try using a tool with the MCP interface"
