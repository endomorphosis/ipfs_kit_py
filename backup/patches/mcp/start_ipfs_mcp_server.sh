#!/bin/bash
# Start IPFS MCP Server
# This script starts the IPFS daemon (if needed) and the MCP server with all IPFS tools

# Set up logging
LOG_FILE="ipfs_mcp_startup.log"
echo "Starting IPFS MCP Server" > $LOG_FILE
echo "$(date)" >> $LOG_FILE

# Check if IPFS daemon is running
if ! pgrep -x "ipfs" > /dev/null; then
    echo "IPFS daemon is not running, starting it now..." | tee -a $LOG_FILE
    
    # Check if the IPFS daemon is installed
    if ! command -v ipfs &> /dev/null; then
        echo "ERROR: IPFS daemon is not installed. Please install it before continuing." | tee -a $LOG_FILE
        exit 1
    fi
    
    # Start the IPFS daemon in the background
    ipfs daemon --routing=dhtclient &
    IPFS_PID=$!
    
    # Wait for daemon to start
    echo "Waiting for IPFS daemon to start..." | tee -a $LOG_FILE
    sleep 5
    
    # Check if daemon started successfully
    if ! pgrep -x "ipfs" > /dev/null; then
        echo "ERROR: Failed to start IPFS daemon." | tee -a $LOG_FILE
        exit 1
    fi
    
    echo "IPFS daemon started successfully!" | tee -a $LOG_FILE
else
    echo "IPFS daemon is already running" | tee -a $LOG_FILE
fi

# Find an available port
PORT=3000
while netstat -tuln | grep ":$PORT " > /dev/null 2>&1; do
    echo "Port $PORT is already in use, trying the next port..." | tee -a $LOG_FILE
    PORT=$((PORT + 1))
    if [ $PORT -gt 3010 ]; then
        echo "ERROR: Could not find an available port in range 3000-3010" | tee -a $LOG_FILE
        exit 1
    fi
done

echo "Using port $PORT for MCP server" | tee -a $LOG_FILE

# Check if the direct MCP server is already running
if [ -f "direct_mcp_server.pid" ]; then
    PID=$(cat direct_mcp_server.pid)
    if kill -0 $PID 2>/dev/null; then
        echo "MCP server is already running with PID: $PID" | tee -a $LOG_FILE
        echo "Stopping the existing server before starting a new one..." | tee -a $LOG_FILE
        
        # Stop the server
        ./stop_ipfs_mcp_server_noninteractive.sh
        sleep 2
    else
        echo "Found stale PID file, cleaning up..." | tee -a $LOG_FILE
        rm direct_mcp_server.pid
    fi
fi

# Register tools with MCP
echo "Registering IPFS tools with MCP..." | tee -a $LOG_FILE
if [ -f "add_comprehensive_ipfs_tools.py" ] && [ -f "register_ipfs_tools_with_mcp.py" ]; then
    python3 register_ipfs_tools_with_mcp.py
    
    # Check if registration was successful
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to register IPFS tools with MCP" | tee -a $LOG_FILE
        exit 1
    fi
    
    echo "IPFS tools registered successfully!" | tee -a $LOG_FILE
else
    echo "ERROR: Tool registration scripts not found." | tee -a $LOG_FILE
    echo "Please ensure add_comprehensive_ipfs_tools.py and register_ipfs_tools_with_mcp.py exist." | tee -a $LOG_FILE
    exit 1
fi

# Start the MCP server
echo "Starting MCP server on port $PORT..." | tee -a $LOG_FILE
python3 direct_mcp_server.py --port $PORT --log-level INFO &

MCP_PID=$!
sleep 2

# Check if server started successfully
if ! kill -0 $MCP_PID 2>/dev/null; then
    echo "ERROR: Failed to start MCP server" | tee -a $LOG_FILE
    exit 1
fi

# Save PID to file
echo $MCP_PID > direct_mcp_server.pid
echo "MCP server started successfully with PID: $MCP_PID" | tee -a $LOG_FILE

# Verify the tools are registered
echo "Verifying IPFS tools registration..." | tee -a $LOG_FILE
if [ -f "verify_ipfs_tools.py" ]; then
    python3 verify_ipfs_tools.py
fi

echo "=================================================" | tee -a $LOG_FILE
echo "IPFS MCP Server Startup Complete" | tee -a $LOG_FILE
echo "MCP server is running on port: $PORT" | tee -a $LOG_FILE
echo "=================================================" | tee -a $LOG_FILE

exit 0
