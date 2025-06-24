#!/bin/bash
# Start the final MCP server

# Kill any running instances
pkill -f "final_mcp_server.py" || echo "No running instances found"

# Wait for ports to be released
sleep 1

# Start the server
python3 final_mcp_server.py --debug --port 3000

# Exit with the same status as the server
exit $?
