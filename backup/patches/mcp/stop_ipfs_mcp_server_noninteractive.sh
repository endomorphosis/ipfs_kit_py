#!/bin/bash
# Stop IPFS MCP Server (Non-interactive version)
# This script stops the MCP server and optionally the IPFS daemon without user prompts

# Set up logging
LOG_FILE="ipfs_mcp_shutdown.log"
echo "Stopping IPFS MCP Server (Non-interactive)" > $LOG_FILE
echo "$(date)" >> $LOG_FILE

# Parse command line arguments
STOP_IPFS=false
if [ "$1" = "--stop-ipfs" ]; then
    STOP_IPFS=true
fi

# Check if MCP server is running
if [ -f "direct_mcp_server.pid" ]; then
    PID=$(cat direct_mcp_server.pid)
    
    if kill -0 $PID 2>/dev/null; then
        echo "Stopping MCP server with PID: $PID" | tee -a $LOG_FILE
        kill $PID
        sleep 2
        
        # Check if server was stopped
        if ! kill -0 $PID 2>/dev/null; then
            echo "MCP server stopped successfully" | tee -a $LOG_FILE
            rm direct_mcp_server.pid
        else
            echo "MCP server did not stop gracefully, forcing..." | tee -a $LOG_FILE
            kill -9 $PID
            sleep 1
            rm direct_mcp_server.pid
        fi
    else
        echo "MCP server is not running (stale PID file)" | tee -a $LOG_FILE
        rm direct_mcp_server.pid
    fi
else
    echo "MCP server is not running (no PID file found)" | tee -a $LOG_FILE
fi

# Stop IPFS daemon if requested
if $STOP_IPFS; then
    echo "Stopping IPFS daemon..." | tee -a $LOG_FILE
    
    # Check if IPFS daemon is running
    if pgrep -x "ipfs" > /dev/null; then
        # Get the PID of IPFS daemon
        IPFS_PID=$(pgrep -x "ipfs")
        
        # Stop IPFS daemon
        ipfs shutdown
        sleep 2
        
        # Check if IPFS daemon was stopped
        if ! kill -0 $IPFS_PID 2>/dev/null; then
            echo "IPFS daemon stopped successfully" | tee -a $LOG_FILE
        else
            echo "IPFS daemon did not stop gracefully, forcing..." | tee -a $LOG_FILE
            kill -9 $IPFS_PID
            sleep 1
        fi
    else
        echo "IPFS daemon is not running" | tee -a $LOG_FILE
    fi
else
    echo "IPFS daemon will continue running" | tee -a $LOG_FILE
fi

echo "=================================================" | tee -a $LOG_FILE
echo "Shutdown complete" | tee -a $LOG_FILE
echo "=================================================" | tee -a $LOG_FILE

exit 0
