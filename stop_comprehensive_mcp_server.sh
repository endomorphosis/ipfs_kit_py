#!/bin/bash

echo "Stopping Comprehensive IPFS MCP Server..."

# Find and kill the MCP server process
pkill -f "python.*comprehensive_final_mcp_server.py" || true

echo "Comprehensive IPFS MCP Server stopped"
