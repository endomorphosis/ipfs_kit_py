#!/bin/bash
# Start MCP server with all tools integrated (53 models)
set -e

# Set current directory
cd "$(dirname "$0")"

# Kill any existing processes
echo "Stopping any running MCP servers..."
pkill -f "python.*direct_mcp_server_with_tools.py" || echo "No direct_mcp_server_with_tools.py running"
pkill -f "python.*final_mcp_server.py" || echo "No final_mcp_server.py running"

# Clean up PID files
rm -f direct_mcp_server.pid final_mcp_server.pid

echo "Starting MCP server with 53 models integrated..."

# Set environment variables
export PYTHONPATH="$PYTHONPATH:$(pwd):$(pwd)/docs/mcp-python-sdk/src"
export PORT=3000

# Start server in the background
nohup python3 -u direct_mcp_server_with_tools.py --port $PORT > direct_mcp_server.log 2>&1 &

# Store PID
echo $! > direct_mcp_server.pid
echo "Server started with PID $(cat direct_mcp_server.pid)"

# Wait a moment
echo "Waiting for server to start..."
sleep 3

# Check if running
if ps -p $(cat direct_mcp_server.pid) > /dev/null; then
    echo "✅ Server started successfully on port $PORT!"
    echo "Server status: http://localhost:$PORT/"
    echo "To stop: kill $(cat direct_mcp_server.pid)"
    
    # Verify tool count
    echo -e "\nChecking available tools..."
    curl -s -X POST http://localhost:$PORT/jsonrpc -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"get_tools","id":1}' | python3 -c "import sys, json; data = json.load(sys.stdin); tools = data.get('result', {}).get('tools', []); print(f'Number of available tools: {len(tools)}')"
    
    echo -e "\nServer is ready for use!"
else
    echo "❌ Failed to start server! Check direct_mcp_server.log for details."
    exit 1
fi
