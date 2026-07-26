#!/bin/bash
# Make all IPFS MCP tools executable
# This script sets executable permissions for all IPFS tool scripts

echo "Setting executable permissions for IPFS MCP tools..."

# Shell scripts
chmod +x start_ipfs_mcp_with_tools.sh
chmod +x stop_ipfs_mcp.sh
if [ -f start_ipfs_mcp_with_fs.sh ]; then
    chmod +x start_ipfs_mcp_with_fs.sh
fi
if [ -f start_fixed_direct_mcp.sh ]; then
    chmod +x start_fixed_direct_mcp.sh
fi
if [ -f restart_mcp_server.sh ]; then
    chmod +x restart_mcp_server.sh
fi
if [ -f restart_and_verify_mcp_tools.sh ]; then
    chmod +x restart_and_verify_mcp_tools.sh
fi

# Python scripts
chmod +x verify_ipfs_tools.py
chmod +x patch_direct_mcp_server.py

echo "All tool scripts are now executable."
echo "You can start the MCP server with integrated IPFS tools by running:"
echo "  ./start_ipfs_mcp_with_tools.sh"
