#!/bin/bash
# Start the minimal MCP server

# Kill any running instances
pkill -f "minimal_mcp_server.py" || echo "No running instances found"

# Wait for ports to be released
sleep 1

# Start the server
python3 minimal_mcp_server.py --debug --port 3001

# Exit with the same status as the server
exit $?
