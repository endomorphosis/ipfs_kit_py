#!/bin/bash
# Script to start the enhanced MCP server with JSON-RPC support

# Kill any running MCP server processes
echo "Stopping any running MCP server processes..."
pkill -f "python.*enhanced_mcp_server_fixed" 2>/dev/null || true
pkill -f "python.*mcp_jsonrpc_proxy" 2>/dev/null || true
sleep 2

# Start the enhanced MCP server
echo "Starting enhanced MCP server..."
python ./enhanced_mcp_server_fixed.py --port 9994 --api-prefix /api/v0 --log-file mcp_server.log > /dev/null 2>&1 &
sleep 3

# Check if server is running
if curl -s http://localhost:9994/ > /dev/null; then
    echo "MCP server is running at http://localhost:9994/"
    
    # Update VS Code settings
    VSCODE_SETTINGS_FILE=~/.config/Code\ -\ Insiders/User/settings.json
    
    if [ -f "$VSCODE_SETTINGS_FILE" ]; then
        echo "Updating VS Code settings..."
        # Make a backup
        cp "$VSCODE_SETTINGS_FILE" "$VSCODE_SETTINGS_FILE.bak"
        
        # Update the settings with new endpoints
        if command -v jq > /dev/null; then
            # Use jq if available
            jq '.mcp.servers["my-mcp-server-3e65fd06"].url = "http://localhost:9994/api/v0/sse" | .localStorageNetworkingTools.lspEndpoint.url = "http://localhost:9994/jsonrpc"' \
                "$VSCODE_SETTINGS_FILE" > "$VSCODE_SETTINGS_FILE.tmp" && \
                mv "$VSCODE_SETTINGS_FILE.tmp" "$VSCODE_SETTINGS_FILE"
        else
            # Fall back to sed
            sed -i 's|"url": "http://localhost:[0-9]*/api/v0/sse"|"url": "http://localhost:9994/api/v0/sse"|g' "$VSCODE_SETTINGS_FILE"
            sed -i 's|"url": "http://localhost:[0-9]*/jsonrpc"|"url": "http://localhost:9994/jsonrpc"|g' "$VSCODE_SETTINGS_FILE"
        fi
        
        echo "VS Code settings updated successfully."
    else
        echo "VS Code settings file not found at: $VSCODE_SETTINGS_FILE"
    fi
    
    echo "Testing the SSE endpoint..."
    curl -s -N http://localhost:9994/api/v0/sse | head -n 2
    
    echo
    echo "Testing the JSON-RPC endpoint..."
    curl -s -X POST -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"processId":123,"rootUri":null,"capabilities":{}}}' \
        http://localhost:9994/jsonrpc | head -n 10
    
    echo
    echo "MCP server configuration completed successfully!"
else
    echo "Failed to start MCP server. Check the logs at mcp_server.log"
    exit 1
fi
