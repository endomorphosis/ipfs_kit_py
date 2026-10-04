#!/bin/bash
# Start the all-in-one MCP server with JSON-RPC support

# Kill any existing MCP servers
pkill -f "python.*mcp_server_fixed_all" 2>/dev/null || true

# Start the all-in-one MCP server with JSON-RPC support
echo "Starting all-in-one MCP server with JSON-RPC support..."
python3 mcp_server_fixed_all.py --port=9994 --debug --isolation --skip-daemon --jsonrpc > mcp_server.log 2>&1 &

# Wait for server to start
echo "Waiting for server to start..."
sleep 2

# Check if server is running
if curl -s http://localhost:9994/ > /dev/null; then
    echo "MCP server is running at http://localhost:9994/"
    
    # Update VS Code settings to use the correct JSON-RPC endpoint
    VSCODE_SETTINGS_FILE=~/.config/Code\ -\ Insiders/User/settings.json
    
    if [ -f "$VSCODE_SETTINGS_FILE" ]; then
        echo "Updating VS Code settings..."
        # Use jq to update the settings file if available, or fallback to sed
        if command -v jq > /dev/null; then
            cp "$VSCODE_SETTINGS_FILE" "$VSCODE_SETTINGS_FILE.bak"
            jq '.localStorageNetworkingTools.lspEndpoint.url = "http://localhost:9994/jsonrpc"' \
                "$VSCODE_SETTINGS_FILE" > "$VSCODE_SETTINGS_FILE.tmp" && \
                mv "$VSCODE_SETTINGS_FILE.tmp" "$VSCODE_SETTINGS_FILE"
        else
            cp "$VSCODE_SETTINGS_FILE" "$VSCODE_SETTINGS_FILE.bak"
            sed -i 's|"url": "http://localhost:[0-9]*/.*"|"url": "http://localhost:9994/jsonrpc"|g' "$VSCODE_SETTINGS_FILE"
        fi
        echo "VS Code settings updated."
    else
        echo "VS Code settings file not found at $VSCODE_SETTINGS_FILE"
    fi
    
    echo "MCP server is ready for use!"
else
    echo "Failed to start MCP server. Check the logs at mcp_server.log"
    exit 1
fi
