#!/bin/bash
#
# IPFS Kit MCP Server Startup Script
# This script restarts the enhanced MCP server with fixed features.
#

# Log file
LOG_FILE="mcp_server.log"

# Helper function for logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Create log file with header
echo "=================================" > "$LOG_FILE"
echo "MCP Server Startup Log - $(date)" >> "$LOG_FILE"
echo "=================================" >> "$LOG_FILE"

# Check if there's a fixed server version available
if [ -f "fixed_final_mcp_server.py" ]; then
    SERVER_SCRIPT="fixed_final_mcp_server.py"
    log "Using fixed server implementation: $SERVER_SCRIPT"
else
    # If not, look for other server implementations
    if [ -f "final_mcp_server.py" ]; then
        SERVER_SCRIPT="final_mcp_server.py"
        log "Using final server implementation: $SERVER_SCRIPT"
    elif [ -f "direct_mcp_server.py" ]; then
        SERVER_SCRIPT="direct_mcp_server.py"
        log "Using direct server implementation: $SERVER_SCRIPT"
    else
        log "ERROR: No server implementation found!"
        exit 1
    fi
    
    # Create fixed server if needed
    log "Generating fixed server implementation..."
    python integrate_features.py --base "$SERVER_SCRIPT"
    
    if [ -f "fixed_$SERVER_SCRIPT" ]; then
        SERVER_SCRIPT="fixed_$SERVER_SCRIPT"
        log "Created fixed server: $SERVER_SCRIPT"
    else
        log "WARNING: Failed to create fixed server, using original: $SERVER_SCRIPT"
    fi
fi

# Apply module patches
log "Applying compatibility patches..."
python mcp_module_patch.py --file "$SERVER_SCRIPT"
if [ $? -ne 0 ]; then
    log "WARNING: Patching process encountered errors, but proceeding"
fi

# Make script executable
chmod +x "$SERVER_SCRIPT"

# Stop any existing servers
log "Stopping existing MCP servers..."
pkill -f "python.*mcp_server" || true
sleep 2

# Start the server
log "Starting MCP server..."
python "$SERVER_SCRIPT" >> "$LOG_FILE" 2>&1 &
SERVER_PID=$!

# Wait for server to initialize
sleep 5

# Check if server is running
if ps -p $SERVER_PID > /dev/null; then
    log "MCP server started successfully (PID: $SERVER_PID)"
    log "Running server verification..."
    
    # Run verification
    python verify_fixed_mcp_tools.py
    
    if [ $? -eq 0 ]; then
        log "Verification successful! Server is running with all required functionality."
        echo "Server is running in the background with PID: $SERVER_PID"
        echo "To stop the server, run: kill $SERVER_PID"
    else
        log "Verification reported issues. Check verification.log for details."
        echo "Server is running, but verification reported issues."
        echo "Server PID: $SERVER_PID"
        echo "Check verification.log for details."
    fi
else
    log "ERROR: Server failed to start!"
    tail -n 20 "$LOG_FILE"
    exit 1
fi

log "Startup process completed."
