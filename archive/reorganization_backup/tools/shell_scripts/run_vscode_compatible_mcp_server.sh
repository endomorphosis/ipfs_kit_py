#!/bin/bash
# Run the VS Code compatible MCP server

# Kill all existing Python servers
echo "Stopping all existing MCP servers..."
pkill -9 -f "python.*mcp.*server" || echo "No MCP server processes to kill"
pkill -9 -f "python.*minimal_mcp_server" || echo "No minimal MCP server processes to kill"
pkill -9 -f "python.*simple_mcp_server" || echo "No simple MCP server processes to kill"
pkill -9 -f "python.*final_mcp_server" || echo "No final MCP server processes to kill"
sleep 2

echo "Starting the VS Code compatible MCP server..."
cd /home/barberb/ipfs_kit_py

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "Activated virtual environment"
elif [ -d "venv" ]; then
    source venv/bin/activate
    echo "Activated virtual environment"
fi

# Install required packages
pip install starlette uvicorn

# Start the server
echo "Launching server on port 9996..."
python3 vscode_compatible_mcp_server.py --port 9996 > vscode_compatible_mcp_server.log 2>&1 &
SERVER_PID=$!

# Write PID to file for future reference
echo $SERVER_PID > vscode_compatible_mcp_server.pid
echo "Server started with PID: $SERVER_PID"

# Wait for server to initialize
echo "Waiting for server to initialize..."
sleep 5

# Check if server is running
if ps -p $SERVER_PID > /dev/null; then
    echo "Server is running successfully with PID: $SERVER_PID"
    echo "Testing health endpoint..."
    curl -s http://localhost:9996/health
    
    echo -e "\nTesting initialize endpoint..."
    TOOL_COUNT=$(curl -s -X POST http://localhost:9996/initialize | jq -r '.capabilities.tools | length' 2>/dev/null || curl -s -X POST http://localhost:9996/initialize | grep -o '"tools":\[[^]]*\]' | wc -l)
    echo "Server initialized with $TOOL_COUNT tools"
    
    echo -e "\nTesting JSON-RPC endpoint..."
    curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"health_check","params":{},"id":1}' http://localhost:9996/jsonrpc
    
    echo -e "\n\nServer is ready! VS Code should now be able to discover all the IPFS tools."
    echo "You may need to restart VS Code to see the changes."
    
    # Create a marker file for VS Code to find
    echo "Writing marker file for VS Code integration..."
    echo "VS Code compatible MCP server is running on port 9996" > /home/barberb/ipfs_kit_py/vscode_compatible_mcp_server_active.txt
else
    echo "Server failed to start. Check the log file: vscode_compatible_mcp_server.log"
    cat vscode_compatible_mcp_server.log
fi
