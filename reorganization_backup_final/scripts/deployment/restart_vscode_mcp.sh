#!/bin/bash
# VS Code MCP Server Restart Script
# =================================

echo "🔄 Restarting VS Code for MCP Server Integration"
echo "================================================"

# Kill any existing VS Code processes
echo "Stopping VS Code..."
pkill -f "code" 2>/dev/null || echo "VS Code not running"

# Kill any lingering MCP servers
echo "Stopping any running MCP servers..."
pkill -f "mcp_stdio_server.py" 2>/dev/null || echo "No MCP servers running"

# Wait a moment for processes to clean up
sleep 2

# Verify our MCP server is working
echo "Verifying MCP server functionality..."
cd /home/barberb/ipfs_kit_py
python3 mcp_status_check.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ MCP server verified successfully!"
    echo ""
    echo "🚀 Starting VS Code..."
    
    # Start VS Code in the background
    nohup code /home/barberb/ipfs_kit_py > /dev/null 2>&1 &
    
    echo ""
    echo "VS Code started with updated MCP server configuration:"
    echo "  - Server: ipfs-kit-mcp"
    echo "  - Protocol: stdio"
    echo "  - Path: /home/barberb/ipfs_kit_py/mcp_stdio_server.py"
    echo ""
    echo "Available IPFS Kit MCP Tools:"
    echo "  • ipfs_add - Add content to IPFS"
    echo "  • ipfs_get - Retrieve content from IPFS"
    echo "  • ipfs_pin - Pin content in IPFS"
    echo "  • filesystem_health - Check filesystem health"
    echo "  • system_health - Get system health status"
    echo "  • ipfs_cluster_status - Get IPFS cluster status"
    echo ""
    echo "✅ Ready to use IPFS Kit MCP tools in VS Code!"
else
    echo "❌ MCP server verification failed. Please check the server implementation."
    exit 1
fi
