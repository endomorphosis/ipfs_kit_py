#!/bin/bash
# Restart the MCP server with fixed tool registration

echo "Stopping existing MCP server instances..."
pkill -f "minimal_mcp_server.py" || echo "No minimal MCP server instances found"

echo "Waiting for ports to be released..."
sleep 2

echo "Starting MCP server with fixed tool registration..."
cd /home/barberb/ipfs_kit_py
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "Activated virtual environment"
fi

python3 minimal_mcp_server.py --port 9996 > minimal_mcp_server_fixed.log 2>&1 &
SERVER_PID=$!

echo "Server started with PID: $SERVER_PID"
echo "Waiting for server to initialize..."
sleep 3

if kill -0 $SERVER_PID 2>/dev/null; then
    echo "Server is running. Testing health endpoint..."
    curl -s http://localhost:9996/health
    echo -e "\n\nAvailable tools (this may take a moment):"
    curl -s -X POST http://localhost:9996/initialize | grep -o '"tools":\[[^]]*\]' | sed 's/"tools":\[//g' | sed 's/\]//g' | tr ',' '\n' | sed 's/"//g' | sort
    echo -e "\n\nServer log tail:"
    tail -n 20 minimal_mcp_server_fixed.log
else
    echo "Server failed to start. Check the log file:"
    cat minimal_mcp_server_fixed.log
fi
