#!/bin/bash
# Set executable permissions on all scripts
# This script sets the executable bit on all the necessary scripts

# Set up logging
echo "Setting executable permissions on scripts"
echo "$(date)"

# Make start and stop scripts executable
chmod +x start_ipfs_mcp_server.sh
chmod +x stop_ipfs_mcp_server.sh
chmod +x register_ipfs_tools_with_mcp.py
chmod +x add_comprehensive_ipfs_tools.py

echo "Made the following scripts executable:"
echo "- start_ipfs_mcp_server.sh"
echo "- stop_ipfs_mcp_server.sh" 
echo "- register_ipfs_tools_with_mcp.py"
echo "- add_comprehensive_ipfs_tools.py"

echo "Done!"
