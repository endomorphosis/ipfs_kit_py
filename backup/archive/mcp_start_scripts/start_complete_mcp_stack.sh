#!/bin/bash
# Comprehensive MCP + JSON-RPC server startup script

# Kill any running MCP servers
echo "Stopping any running MCP and JSON-RPC servers..."
pkill -f "python.*enhanced_mcp_server_fixed" 2>/dev/null || true
pkill -f "python.*standalone_jsonrpc" 2>/dev/null || true
sleep 2

# Clean up log files
echo "Cleaning up log files..."
rm -f mcp_server.log standalone_jsonrpc.log

# Start the MCP server in background
echo "Starting enhanced MCP server..."
python ./enhanced_mcp_server_fixed.py --port 9994 --api-prefix /api/v0 --log-file mcp_server.log > /dev/null 2>&1 &
sleep 2

# Start the standalone JSON-RPC server in background
echo "Starting standalone JSON-RPC server..."
python ./standalone_jsonrpc.py --port 9995 --debug > /dev/null 2>&1 &
sleep 2

# Check if servers are running
echo "Checking if servers are running..."
MCP_RUNNING=false
JSONRPC_RUNNING=false

if curl -s http://localhost:9994/ > /dev/null; then
    echo "✓ MCP server is running at http://localhost:9994/"
    MCP_RUNNING=true
else
    echo "✗ MCP server failed to start"
fi

if curl -s http://localhost:9995/ > /dev/null; then
    echo "✓ JSON-RPC server is running at http://localhost:9995/"
    JSONRPC_RUNNING=true
else
    echo "✗ JSON-RPC server failed to start"
fi

# Update VS Code settings if both servers are running
if $MCP_RUNNING && $JSONRPC_RUNNING; then
    VSCODE_SETTINGS_FILE=~/.config/Code\ -\ Insiders/User/settings.json
    
    if [ -f "$VSCODE_SETTINGS_FILE" ]; then
        echo "Updating VS Code settings..."
        # Make a backup
        cp "$VSCODE_SETTINGS_FILE" "$VSCODE_SETTINGS_FILE.bak"
        
        # Update the settings with new endpoints
        if command -v jq > /dev/null; then
            # Use jq if available
            jq '.mcp.servers["my-mcp-server-3e65fd06"].url = "http://localhost:9994/api/v0/sse" | .localStorageNetworkingTools.lspEndpoint.url = "http://localhost:9995/jsonrpc"' \
                "$VSCODE_SETTINGS_FILE" > "$VSCODE_SETTINGS_FILE.tmp" && \
                mv "$VSCODE_SETTINGS_FILE.tmp" "$VSCODE_SETTINGS_FILE"
        else
            # Fall back to sed
            sed -i 's|"url": "http://localhost:[0-9]*/api/v0/sse"|"url": "http://localhost:9994/api/v0/sse"|g' "$VSCODE_SETTINGS_FILE"
            sed -i 's|"url": "http://localhost:[0-9]*/jsonrpc"|"url": "http://localhost:9995/jsonrpc"|g' "$VSCODE_SETTINGS_FILE"
        fi
        
        echo "VS Code settings updated successfully."
    else
        echo "VS Code settings file not found at: $VSCODE_SETTINGS_FILE"
    fi
    
    # Test the MCP server endpoints
    echo "Testing MCP server endpoints..."
    echo "Root endpoint:"
    curl -s http://localhost:9994/ | head -1
    echo
    
    echo "SSE endpoint (will show first event):"
    curl -s -N http://localhost:9994/api/v0/sse | head -1
    echo
    
    # Test the JSON-RPC server
    echo "Testing JSON-RPC server..."
    echo "Root endpoint:"
    curl -s http://localhost:9995/ | head -1
    echo
    
    echo "JSON-RPC initialize request:"
    curl -s -X POST -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"processId":123,"rootUri":null,"capabilities":{}}}' \
        http://localhost:9995/jsonrpc | head -1
    echo
    
    echo "Setup complete! Servers are running and VS Code settings have been updated."
    echo "The MCP server log is available at: mcp_server.log"
    echo "The JSON-RPC server log is available at: standalone_jsonrpc.log"
else
    echo "One or both servers failed to start. Please check the logs."
    exit 1
fi
