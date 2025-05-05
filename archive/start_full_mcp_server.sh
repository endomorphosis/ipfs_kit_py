#!/bin/bash
# Start Full MCP Server with All Tools
set -e

echo "Starting Full MCP Server with all tools..."

# Change to script directory
cd "$(dirname "$0")"

# Clean up any existing servers
pkill -f "python.*direct_mcp_server" || echo "No running servers"
echo "Cleared previous logs..." > direct_mcp_server.log

# Check if IPFS daemon is running
echo "Checking IPFS daemon status..."
if ! pgrep -x "ipfs" > /dev/null; then
    echo "IPFS daemon not running, starting it..."
    ipfs daemon --init &
    # Wait a bit for IPFS to start
    sleep 3
else
    echo "IPFS daemon is already running."
fi

echo "Cleaning up any existing MCP server processes..."
if [ -f direct_mcp_server.pid ]; then
    pid=$(cat direct_mcp_server.pid 2>/dev/null || echo "")
    if [ -n "$pid" ] && ps -p $pid > /dev/null 2>&1; then
        kill $pid
        sleep 2
    fi
fi

# Set environment variables
echo "Setting up Python environment..."
export PYTHONPATH="$PYTHONPATH:$(pwd):$(pwd)/docs/mcp-python-sdk/src"

# Start the server
echo "Starting direct_mcp_server_with_tools.py..."
python3 direct_mcp_server_with_tools.py --port 3000 > direct_mcp_server.log 2>&1 &
echo $! > direct_mcp_server.pid
echo "Server started with PID: $(cat direct_mcp_server.pid)"

# Wait a moment for server to initialize
echo "Waiting for server initialization..."
sleep 5

# Check if running
if ps -p $(cat direct_mcp_server.pid) > /dev/null; then
    echo "✅ Server started successfully!"
    
    echo -e "\nServer is running at http://localhost:3000/"
    echo "Health check: http://localhost:3000/health"
    echo "To stop: kill $(cat direct_mcp_server.pid)"
else
    echo "❌ Server process stopped unexpectedly."
    echo "Last 20 lines of output:"
    tail -20 direct_mcp_server.log
    exit 1
fi
