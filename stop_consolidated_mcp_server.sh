#!/bin/bash
# Stop script for the Consolidated MCP Server
# This script stops the MCP server process

echo "Stopping Consolidated IPFS-VFS MCP Server..."

# First, try to find the process running on port 3000 (default MCP server port)
PORT_PID=$(lsof -i :3000 -t 2>/dev/null)

if [ -n "$PORT_PID" ]; then
    echo "Found MCP server process on port 3000 with PID: $PORT_PID"
    echo "Sending SIGTERM to process..."
    kill -15 $PORT_PID
    
    # Give it a moment to terminate gracefully
    sleep 2
    
    # Check if it's still running
    if ps -p $PORT_PID > /dev/null; then
        echo "Process still running, sending SIGKILL..."
        kill -9 $PORT_PID
    fi
    
    echo "MCP server stopped."
else
    echo "No MCP server process found running on port 3000."
    
    # Try to find by process name as a fallback
    PY_PIDS=$(pgrep -f "python3.*consolidated_final_mcp_server.py" 2>/dev/null)
    
    if [ -n "$PY_PIDS" ]; then
        echo "Found MCP server processes by name:"
        for pid in $PY_PIDS; do
            echo "Stopping process with PID: $pid"
            kill -15 $pid
        done
        
        # Give them a moment to terminate gracefully
        sleep 2
        
        # Check if any are still running
        REMAINING_PIDS=$(pgrep -f "python3.*consolidated_final_mcp_server.py" 2>/dev/null)
        if [ -n "$REMAINING_PIDS" ]; then
            echo "Some processes still running, sending SIGKILL..."
            for pid in $REMAINING_PIDS; do
                kill -9 $pid
            done
        fi
        
        echo "MCP server processes stopped."
    else
        echo "No MCP server processes found."
    fi
fi

echo "Done."
