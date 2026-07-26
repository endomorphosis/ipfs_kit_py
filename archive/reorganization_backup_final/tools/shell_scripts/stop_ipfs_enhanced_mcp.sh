#!/bin/bash
# stop_ipfs_enhanced_mcp.sh
#
# Script to stop the IPFS-enhanced direct MCP server
#

# Check for the PID file
if [ -f "./direct_mcp_server_blue.pid" ]; then
    PID=$(cat ./direct_mcp_server_blue.pid)
    if ps -p $PID > /dev/null; then
        echo "🛑 Stopping IPFS-Enhanced MCP Server with PID $PID..."
        kill $PID
        echo "✅ Server stopped successfully"
    else
        echo "⚠️ Server is not running (PID $PID not found)"
        rm ./direct_mcp_server_blue.pid
        echo "✅ Removed stale PID file"
    fi
else
    echo "⚠️ No PID file found. Server may not be running or may be using a different name."
    
    # Try to find the server process
    SERVER_PIDS=$(pgrep -f "python direct_mcp_server.py")
    if [ -n "$SERVER_PIDS" ]; then
        echo "🔍 Found running MCP server processes: $SERVER_PIDS"
        echo "🛑 Stopping all MCP server processes..."
        
        for pid in $SERVER_PIDS; do
            echo "Stopping PID $pid..."
            kill $pid
        done
        
        echo "✅ All server processes stopped"
    else
        echo "❌ Could not find any running MCP server processes"
    fi
fi

# Clean up any temporary files
echo "🧹 Cleaning up temporary files..."
if [ -f "./direct_mcp_server_active.txt" ]; then
    rm ./direct_mcp_server_active.txt
    echo "✅ Removed active version file"
fi

echo "✅ Cleanup complete"
echo "🔄 You can restart the server with ./start_ipfs_enhanced_mcp.sh"
