#!/bin/bash
# Start MCP server with advanced Filecoin features

echo "Starting MCP server with advanced Filecoin features..."

# Stop any running server
pkill -f "enhanced_mcp_server.py" || echo "No server to stop"
sleep 2

# Ensure directories exist
mkdir -p logs
mkdir -p ~/.ipfs_kit/mock_filecoin/deals

# Set up environment
source .venv/bin/activate
export LOTUS_PATH="$HOME/.lotus-gateway"
export LOTUS_GATEWAY_MODE="true"
export PATH="$(pwd)/bin:$PATH"

# Start the server
python enhanced_mcp_server.py --port 9997 --debug > logs/mcp_server.log 2>&1 &
PID=$!

echo "MCP server started with PID: $PID"
echo "Waiting for server to start..."
sleep 5

# Check if server is running
if curl -s http://localhost:9997/api/v0/health > /dev/null; then
    echo "MCP server is running successfully"
    echo "To check server health: curl http://localhost:9997/api/v0/health"
    echo "To access advanced Filecoin features: curl http://localhost:9997/api/v0/filecoin/advanced/status"
    echo "Log file: $(pwd)/logs/mcp_server.log"
else
    echo "MCP server failed to start. Check logs: $(pwd)/logs/mcp_server.log"
    tail -20 logs/mcp_server.log
fi