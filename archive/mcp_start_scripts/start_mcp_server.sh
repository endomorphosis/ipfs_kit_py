#!/bin/bash
# MCP Server Startup Script
# This script starts both the MCP server and JSON-RPC server
# and ensures they are running correctly.

# Define paths and ports
MCP_SERVER_PORT=9994
JSONRPC_PORT=9995
MCP_API_PREFIX="/api/v0"
MCP_SERVER_LOG="mcp_server.log"
JSONRPC_LOG="simple_jsonrpc_server.log"
MCP_PID_FILE="mcp_server.pid"
JSONRPC_PID_FILE="jsonrpc_server.pid"

# Function to check if a server is running
check_running() {
    local url=$1
    local name=$2
    
    if curl -s "$url" > /dev/null; then
        echo "✅ $name is running at $url"
        return 0
    else
        echo "❌ $name is not running at $url"
        return 1
    fi
}

# Function to start the MCP server
start_mcp_server() {
    echo "Starting MCP server on port $MCP_SERVER_PORT..."
    
    # Stop any existing MCP server
    if [ -f "$MCP_PID_FILE" ]; then
        pid=$(cat "$MCP_PID_FILE")
        if ps -p "$pid" > /dev/null; then
            echo "Stopping existing MCP server (PID: $pid)..."
            kill "$pid" 2>/dev/null || true
            sleep 2
        fi
        rm "$MCP_PID_FILE" 2>/dev/null || true
    fi
    
    # Start the MCP server
    nohup python3 ./enhanced_mcp_server_fixed.py --port "$MCP_SERVER_PORT" --api-prefix "$MCP_API_PREFIX" --log-file "$MCP_SERVER_LOG" > /dev/null 2>&1 &
    echo $! > "$MCP_PID_FILE"
    
    # Wait for server to start
    echo "Waiting for MCP server to start..."
    for i in {1..10}; do
        if check_running "http://localhost:$MCP_SERVER_PORT/" "MCP server"; then
            return 0
        fi
        sleep 1
    done
    
    echo "Failed to start MCP server within 10 seconds"
    return 1
}

# Function to start the JSON-RPC server
start_jsonrpc_server() {
    echo "Starting JSON-RPC server on port $JSONRPC_PORT..."
    
    # Stop any existing JSON-RPC server
    if [ -f "$JSONRPC_PID_FILE" ]; then
        pid=$(cat "$JSONRPC_PID_FILE")
        if ps -p "$pid" > /dev/null; then
            echo "Stopping existing JSON-RPC server (PID: $pid)..."
            kill "$pid" 2>/dev/null || true
            sleep 2
        fi
        rm "$JSONRPC_PID_FILE" 2>/dev/null || true
    fi
    
    # Start the JSON-RPC server
    nohup python3 ./simple_jsonrpc_server.py > "$JSONRPC_LOG" 2>&1 &
    echo $! > "$JSONRPC_PID_FILE"
    
    # Wait for server to start
    echo "Waiting for JSON-RPC server to start..."
    for i in {1..10}; do
        if check_running "http://localhost:$JSONRPC_PORT/" "JSON-RPC server"; then
            return 0
        fi
        sleep 1
    done
    
    echo "Failed to start JSON-RPC server within 10 seconds"
    return 1
}

# Function to update VS Code settings
update_vscode_settings() {
    echo "Updating VS Code settings..."
    
    VSCODE_SETTINGS_FILE=~/.config/Code\ -\ Insiders/User/settings.json
    
    if [ -f "$VSCODE_SETTINGS_FILE" ]; then
        # Make a backup
        cp "$VSCODE_SETTINGS_FILE" "$VSCODE_SETTINGS_FILE.bak"
        
        # Update settings using sed
        sed -i 's|"url": "http://localhost:[0-9]*/api/v0/sse"|"url": "http://localhost:'$MCP_SERVER_PORT'/api/v0/sse"|g' "$VSCODE_SETTINGS_FILE"
        sed -i 's|"url": "http://localhost:[0-9]*/jsonrpc"|"url": "http://localhost:'$JSONRPC_PORT'/jsonrpc"|g' "$VSCODE_SETTINGS_FILE"
        
        echo "✅ VS Code settings updated successfully."
    else
        echo "❌ VS Code settings file not found at: $VSCODE_SETTINGS_FILE"
    fi
}

# Main function
main() {
    echo "=================================="
    echo "MCP Server Startup Script"
    echo "=================================="
    
    # Stop any existing servers
    echo "Stopping any existing servers..."
    pkill -f "python.*enhanced_mcp_server" 2>/dev/null || true
    pkill -f "python.*simple_jsonrpc_server" 2>/dev/null || true
    sleep 2
    
    # Start servers
    start_mcp_server
    mcp_result=$?
    
    start_jsonrpc_server
    jsonrpc_result=$?
    
    # Update VS Code settings if both servers started successfully
    if [ $mcp_result -eq 0 ] && [ $jsonrpc_result -eq 0 ]; then
        update_vscode_settings
        
        # Run verification
        echo "Running full verification..."
        ./verify_mcp_setup.py
        
        if [ $? -eq 0 ]; then
            echo "✅ MCP server setup completed successfully!"
            echo "MCP server running on http://localhost:$MCP_SERVER_PORT/"
            echo "JSON-RPC server running on http://localhost:$JSONRPC_PORT/"
            echo "Log files:"
            echo "  - MCP server: $MCP_SERVER_LOG"
            echo "  - JSON-RPC server: $JSONRPC_LOG"
        else
            echo "❌ Verification failed. Please check the logs."
        fi
    else
        echo "❌ Failed to start one or both servers."
        exit 1
    fi
}

# Run the main function
main
