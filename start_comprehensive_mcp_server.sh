#!/bin/bash

echo "Starting Comprehensive IPFS MCP Server..."

# Kill any existing server processes
pkill -f "python.*comprehensive_final_mcp_server.py" || true

# Start the MCP server
python comprehensive_final_mcp_server.py --port 3000

echo "Comprehensive IPFS MCP Server started on port 3000"
