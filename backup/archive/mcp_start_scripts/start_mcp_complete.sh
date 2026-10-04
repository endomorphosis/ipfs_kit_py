#!/bin/bash
# Complete MCP + JSON-RPC startup script

# Stop any running servers
echo "Stopping any running servers..."
pkill -f "python.*enhanced_mcp_server" 2>/dev/null || true
pkill -f "python.*simple_jsonrpc_server" 2>/dev/null || true
pkill -f "python.*mcp_jsonrpc" 2>/dev/null || true
sleep 2

# Clear log files
echo "Clearing log files..."
echo "" > mcp_server.log
echo "" > simple_jsonrpc_server.log

# Start the MCP server
echo "Starting enhanced MCP server..."
nohup python3 ./enhanced_mcp_server_fixed.py --port 9994 --api-prefix /api/v0 --log-file mcp_server.log > /dev/null 2>&1 &
sleep 2

# Start the simple JSON-RPC server
echo "Starting simple JSON-RPC server..."
nohup python3 ./simple_jsonrpc_server.py > simple_jsonrpc_server.log 2>&1 &
sleep 2

# Check if servers are running
MCP_RUNNING=false
JSONRPC_RUNNING=false

echo "Checking server status..."
if curl -s http://localhost:9994/ > /dev/null; then
    echo "✅ MCP server is running at http://localhost:9994/"
    MCP_RUNNING=true
else
    echo "❌ MCP server failed to start. Check mcp_server.log for details."
fi

if curl -s http://localhost:9995/ > /dev/null; then
    echo "✅ JSON-RPC server is running at http://localhost:9995/"
    JSONRPC_RUNNING=true
else
    echo "❌ JSON-RPC server failed to start. Check simple_jsonrpc_server.log for details."
fi

# Update VS Code settings
if [ "$MCP_RUNNING" = true ] && [ "$JSONRPC_RUNNING" = true ]; then
    VSCODE_SETTINGS_FILE=~/.config/Code\ -\ Insiders/User/settings.json
    
    if [ -f "$VSCODE_SETTINGS_FILE" ]; then
        echo "Updating VS Code settings..."
        # Make a backup
        cp "$VSCODE_SETTINGS_FILE" "$VSCODE_SETTINGS_FILE.bak"
        
        # Update settings using sed
        sed -i 's|"url": "http://localhost:[0-9]*/api/v0/sse"|"url": "http://localhost:9994/api/v0/sse"|g' "$VSCODE_SETTINGS_FILE"
        sed -i 's|"url": "http://localhost:[0-9]*/jsonrpc"|"url": "http://localhost:9995/jsonrpc"|g' "$VSCODE_SETTINGS_FILE"
        
        echo "✅ VS Code settings updated successfully."
    else
        echo "❌ VS Code settings file not found at: $VSCODE_SETTINGS_FILE"
    fi
    
    # Test server connections
    echo -e "\nTesting MCP server:"
    curl -s http://localhost:9994/ | head -10
    
    echo -e "\nTesting JSON-RPC server:"
    curl -s http://localhost:9995/
    
    echo -e "\nTesting JSON-RPC initialize request:"
    curl -s -X POST -H "Content-Type: application/json" \
         -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"processId":123,"rootUri":null,"capabilities":{}}}' \
         http://localhost:9995/jsonrpc
    
    echo -e "\n✅ Setup complete! Your servers are running and VS Code settings have been updated."
    echo "MCP server log: mcp_server.log"
    echo "JSON-RPC server log: simple_jsonrpc_server.log"
    
    # Save PIDs for future reference
    pgrep -f "python.*enhanced_mcp_server" > mcp_server.pid
    pgrep -f "python.*simple_jsonrpc_server" > jsonrpc_server.pid
    
    echo "To restart the servers later, run this script again."
else
    echo "❌ One or both servers failed to start. Please check the logs."
    exit 1
fi
