#!/bin/bash
# Start MCP server with logger fixes applied

# Set to exit on error
set -e

# Log function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Check if MCP server is already running and stop it
stop_mcp_server() {
    log "Stopping any running MCP servers..."
    if [ -f "direct_mcp_server.pid" ]; then
        PID=$(cat direct_mcp_server.pid)
        if ps -p $PID > /dev/null; then
            log "Stopping MCP server with PID $PID"
            kill $PID || true
            sleep 2
        fi
        rm direct_mcp_server.pid || true
    fi
    
    # Also check for background processes with direct_mcp_server.py
    PIDS=$(ps aux | grep "direct_mcp_server.py" | grep -v grep | awk '{print $2}')
    if [ ! -z "$PIDS" ]; then
        log "Found additional MCP server processes: $PIDS"
        for PID in $PIDS; do
            log "Stopping process $PID"
            kill $PID || true
        done
        sleep 2
    fi
    log "MCP server stopped"
}

# Apply logger fixes
apply_logger_fixes() {
    log "Applying logger fixes..."
    # Run the direct fix script if it hasn't been run yet
    if [ ! -f "ensure_mcp_loggers.py" ]; then
        log "Running direct_fix_resource_handlers.py..."
        ./direct_fix_resource_handlers.py
    fi
    
    # Run the ensure_mcp_loggers.py script to patch modules at runtime
    log "Running ensure_mcp_loggers.py..."
    ./ensure_mcp_loggers.py
    log "Logger fixes applied"
}

# Start MCP server with fixed configuration
start_mcp_server() {
    log "Starting MCP server with logger fixes..."
    # Export PYTHONPATH to ensure modules can be found
    export PYTHONPATH="$PWD:$PYTHONPATH"
    
    # Start the server with increased verbosity for debugging
    python direct_mcp_server.py --port 3000 --log-level INFO &
    
    # Save PID
    echo $! > direct_mcp_server.pid
    log "MCP server started with PID $!"
    
    # Wait for server to initialize
    log "Waiting for server to initialize..."
    sleep 5
    
    # Check if server is running
    if [ -f "direct_mcp_server.pid" ]; then
        PID=$(cat direct_mcp_server.pid)
        if ps -p $PID > /dev/null; then
            log "MCP server is running with PID $PID"
        else
            log "ERROR: MCP server failed to start!"
            exit 1
        fi
    else
        log "ERROR: MCP server PID file not found!"
        exit 1
    fi
}

# Verify server is responding
verify_server() {
    log "Verifying server is responding..."
    # Try to connect to the server
    for i in {1..5}; do
        if curl -s "http://localhost:3000/" > /dev/null; then
            log "Server is responding at http://localhost:3000/"
            return 0
        else
            log "Waiting for server to respond (attempt $i/5)..."
            sleep 2
        fi
    done
    
    log "ERROR: Server is not responding!"
    return 1
}

# Main execution
log "==== Starting MCP server with logger fixes ===="

# Stop any running MCP server
stop_mcp_server

# Apply logger fixes
apply_logger_fixes

# Start the server
start_mcp_server

# Verify server is responding
if verify_server; then
    log "MCP server is running and responding with logger fixes applied"
    log "Access the server at http://localhost:3000/"
    log "To stop the server, run: kill $(cat direct_mcp_server.pid)"
else
    log "Failed to verify MCP server is running"
    stop_mcp_server
    exit 1
fi
