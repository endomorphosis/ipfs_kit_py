#!/bin/bash
# A simplified script to start the final MCP server with all tools integrated

echo "Starting the Final MCP Server with all tools integrated..."

# Set current directory
cd "$(dirname "$0")"

# Kill any existing processes
pkill -f "python3.*direct_mcp_server_with_tools.py" || echo "No direct_mcp_server_with_tools.py running"
pkill -f "python3.*final_mcp_server.py" || echo "No final_mcp_server.py running"
sleep 1

# Set up environment
export PYTHONPATH="$PYTHONPATH:$(pwd)"

# Start the server with full tool integration
echo "Starting direct_mcp_server_with_tools.py which has 53 tools integrated..."
python3 direct_mcp_server_with_tools.py --port 3000 --debug

# Exit with the same status
exit $?
