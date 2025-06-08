#!/bin/bash
# Run Fixed Final MCP Solution
# This script runs the fixed version of the MCP server

# Source the original script for common functions
source run_final_solution.sh

# Override main function
main() {
    local stop_server=false
    local show_status=false
    local test_only=false
    local start_only=false
    local show_help=false
    local verbose=""
    
    # Parse command-line arguments
    parse_args "$@"
    
    if [ "$show_help" = "true" ]; then
        show_usage
        return 0
    fi
    
    # Handle --stop option
    if [ "$stop_server" = "true" ]; then
        log "INFO" "Stopping MCP server"
        kill_existing_servers
        log "SUCCESS" "MCP server stopped"
        return 0
    fi
    
    # Handle --status option
    if [ "$show_status" = "true" ]; then
        if [ -f "$PID_FILE" ] && ps -p "$(cat $PID_FILE)" > /dev/null 2>&1; then
            print_status_summary
        else
            log "ERROR" "MCP server is not running"
            return 1
        fi
        return 0
    fi
    
    # Handle --test-only option
    if [ "$test_only" = "true" ]; then
        log "INFO" "Running tests against existing MCP server"
        if ! curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
            log "ERROR" "No MCP server running on port $PORT"
            return 1
        fi
        
        python3 test_mcp_basic.py
        log "SUCCESS" "Basic tests completed"
        return 0
    fi
    
    # Normal startup flow
    log "INFO" "Starting fixed MCP server solution"
    
    # Create fixed server file with IPFS tools fix
    log "INFO" "Creating fixed MCP server with tools fix..."
    cat > fixed_final_mcp_server.py << 'EOL'
#!/usr/bin/env python3
"""
Fixed MCP Server Implementation

This is a fixed version of the final MCP server that ensures all tools
are properly registered as JSON-RPC methods.
"""

import os
import sys
import importlib.util
from pathlib import Path

# First, import the original server
from final_mcp_server import MCPServer, app, setup_imports, setup_jsonrpc, setup_ipfs_tools

# Then, import our tools fix
ipfs_tools_fix_path = os.path.join(os.path.dirname(__file__), "ipfs_tools_fix.py")
spec = importlib.util.spec_from_file_location("ipfs_tools_fix", ipfs_tools_fix_path)
ipfs_tools_fix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ipfs_tools_fix)

# Create a wrapper around the server creation to apply our fix
def create_and_fix_server():
    # Create the original server instance
    server = MCPServer()
    
    # Set up imports
    setup_imports()
    
    # Set up JSONRPC
    setup_jsonrpc()
    
    # Set up IPFS tools
    if setup_ipfs_tools(server):
        # Apply our fix to register tools as direct JSON-RPC methods
        fix_result = ipfs_tools_fix.fix_mcp_tools(server)
        print(f"Tools fix applied: {fix_result}")
    
    return server

# Create and fix the server instance
server_instance = create_and_fix_server()

# Add the server instance to the app's state
app.state.server = server_instance

# Ensure app imports the new server instance
from final_mcp_server import *

# Run the server if executed directly
if __name__ == "__main__":
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser(description="Run the Fixed Final MCP Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=9997, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    print(f"Starting server on {args.host}:{args.port}, debug={args.debug}, PID: {os.getpid()}")
    
    uvicorn.run(app, host=args.host, port=args.port, log_level="debug" if args.debug else "info")
EOL
    
    chmod +x fixed_final_mcp_server.py
    
    # Kill any existing servers
    kill_existing_servers
    
    # Check if port is available
    if ! check_port; then
        return 1
    fi
    
    # Start the fixed server
    log "INFO" "Starting fixed MCP server on $HOST:$PORT"
    python3 fixed_final_mcp_server.py --host "$HOST" --port "$PORT" --debug > "fixed_final_mcp_server.log" 2>&1 &
    SERVER_PID=$!
    echo "$SERVER_PID" > "$PID_FILE"
    log "INFO" "Fixed MCP server started with PID: $SERVER_PID"
    
    # Wait for the server to start
    log "INFO" "Waiting for server to initialize"
    
    for ((i=1; i<=$MAX_WAIT; i++)); do
        sleep 1
        if ! ps -p "$SERVER_PID" > /dev/null; then
            log "ERROR" "Server process died unexpectedly. Check fixed_final_mcp_server.log for details."
            tail -n 20 "fixed_final_mcp_server.log"
            return 1
        fi
        
        # Check if server is accepting connections
        if curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT/health 2>/dev/null | grep -q 200; then
            log "SUCCESS" "Server is up and responding to health checks"
            break
        fi
        
        # Show progress
        if (( i % 5 == 0 )); then
            log "INFO" "Still waiting for server to start ($i/$MAX_WAIT seconds)"
            tail -n 5 "fixed_final_mcp_server.log"
        fi
        
        if [ $i -eq $MAX_WAIT ]; then
            log "ERROR" "Server failed to start within $MAX_WAIT seconds. Check fixed_final_mcp_server.log for details."
            tail -n 20 "fixed_final_mcp_server.log"
            kill "$SERVER_PID" 2>/dev/null || true
            return 1
        fi
    done
    
    # Run a basic test
    log "INFO" "Running basic test to verify server functionality"
    python3 test_mcp_basic.py
    
    log "SUCCESS" "Fixed MCP server is running successfully on port $PORT"
    print_status_summary
    
    return 0
}

# Run the main function
main "$@"
exit $?
