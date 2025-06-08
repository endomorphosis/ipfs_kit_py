#!/bin/bash
# Launch the comprehensive MCP server solution

# Kill all existing Python servers
echo "Stopping all existing MCP servers..."
pkill -9 -f "python.*mcp.*server" || echo "No MCP server processes to kill"
pkill -9 -f "python.*minimal_mcp_server" || echo "No minimal MCP server processes to kill"
pkill -9 -f "python.*simple_mcp_server" || echo "No simple MCP server processes to kill"
pkill -9 -f "python.*final_mcp_server" || echo "No final MCP server processes to kill"
sleep 2

echo "Starting the comprehensive MCP server solution..."
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
pip install starlette uvicorn python-multipart aiofiles

# Start the server
echo "Launching server on port 9996..."
python3 direct_mcp_server_with_tools.py --port 9996 --host 0.0.0.0 > comprehensive_mcp_server.log 2>&1 &
SERVER_PID=$!

# Write PID to file for future reference
echo $SERVER_PID > comprehensive_mcp_server.pid
echo "Server started with PID: $SERVER_PID"

# Wait for server to initialize
echo "Waiting for server to initialize..."
sleep 5

# Check if server is running
if ps -p $SERVER_PID > /dev/null; then
    echo "Server is running successfully"
    echo "Testing health endpoint..."
    curl -s http://localhost:9996/health
    
    echo -e "\nTesting initialize endpoint..."
    echo "Available tools:"
    curl -s -X POST http://localhost:9996/initialize | grep -o '"tools":\[[^]]*\]' | sed 's/"tools":\[//g' | sed 's/\]//g' | tr ',' '\n' | sed 's/"//g' | sort
    
    echo -e "\nTesting JSON-RPC endpoint..."
    curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"health_check","params":{},"id":1}' http://localhost:9996/jsonrpc
    
    echo -e "\n\nServer is ready! VS Code should now be able to discover all the IPFS tools."
    echo "You may need to restart VS Code to see the changes."
    
    # Create a marker file for VS Code to find
    echo "Writing marker file for VS Code integration..."
    echo "Direct MCP server is running on port 9996" > /home/barberb/ipfs_kit_py/direct_mcp_server_active.txt
else
    echo "Server failed to start. Check the log file: comprehensive_mcp_server.log"
    tail -n 50 comprehensive_mcp_server.log
fi
