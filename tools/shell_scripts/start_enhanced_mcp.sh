#!/bin/bash
# Start the enhanced MCP server with IPFS tools and FS integration

echo "Stopping any running MCP servers..."
pkill -f "python.*direct_mcp_server" || true
sleep 2

echo "Starting enhanced MCP server with IPFS tool coverage..."
python start_enhanced_mcp_server.py --host=127.0.0.1 --port=3001 &
SERVER_PID=$!
echo "Enhanced MCP server started with PID $SERVER_PID"
echo "Waiting for server to initialize..."
sleep 5

echo "✅ Enhanced MCP server is now running at http://127.0.0.1:3001"
echo "JSON-RPC endpoint is available at http://127.0.0.1:3001/jsonrpc"
echo "To test, try using the IPFS tools with the MCP interface"
