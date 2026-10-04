#!/bin/bash
# Start all MCP components

# Stop any existing processes
echo "Stopping any existing processes..."
pkill -f "python.*enhanced_mcp_server" || true
pkill -f "python.*simple_jsonrpc_server" || true
pkill -f "python.*minimal_health_endpoint" || true
sleep 2

# Start the enhanced MCP server
echo "Starting enhanced MCP server..."
python ./enhanced_mcp_server_fixed.py --port 9994 --api-prefix /api/v0 > mcp_server_output.log 2>&1 &
echo $! > mcp_server.pid
sleep 2

# Start the simple JSON-RPC server
echo "Starting simple JSON-RPC server..."
python ./simple_jsonrpc_server.py > jsonrpc_server.log 2>&1 &
echo $! > jsonrpc_server.pid
sleep 2

# Start the minimal health endpoint
echo "Starting minimal health endpoint..."
python ./minimal_health_endpoint.py --port 9996 > health_endpoint.log 2>&1 &
echo $! > health_endpoint.pid
sleep 2

# Update VS Code settings
echo "Updating VS Code settings..."
VSCODE_SETTINGS_FILE=~/.config/Code/User/settings.json
VSCODE_INSIDERS_SETTINGS_FILE=~/.config/Code\ -\ Insiders/User/settings.json

update_settings() {
    local settings_file=$1
    if [ -f "$settings_file" ]; then
        # Create a backup
        cp "$settings_file" "${settings_file}.bak"
        
        # Update settings using sed
        sed -i 's|"url": "http://localhost:[0-9]*/api/v0/sse"|"url": "http://localhost:9994/api/v0/sse"|g' "$settings_file"
        sed -i 's|"url": "http://localhost:[0-9]*/jsonrpc"|"url": "http://localhost:9995/jsonrpc"|g' "$settings_file"
        
        echo "  ✅ Updated $settings_file"
    else
        echo "  ❌ Settings file not found: $settings_file"
    fi
}

update_settings "$VSCODE_SETTINGS_FILE"
update_settings "$VSCODE_INSIDERS_SETTINGS_FILE"

# Check if all servers are running
echo -e "\nChecking server status..."

check_server() {
    local url=$1
    local name=$2
    
    if curl -s "$url" > /dev/null; then
        echo "  ✅ $name is running at $url"
    else
        echo "  ❌ $name is not running at $url"
    fi
}

check_server "http://localhost:9994/" "MCP server"
check_server "http://localhost:9995/" "JSON-RPC server"
check_server "http://localhost:9996/" "Health endpoint"

# Test key functionality
echo -e "\nTesting key endpoints..."

echo "MCP root endpoint:"
curl -s http://localhost:9994/ | python -m json.tool | head -10

echo -e "\nHealth endpoint:"
curl -s http://localhost:9996/api/v0/health | python -m json.tool | head -10

echo -e "\nJSON-RPC initialize request:"
curl -s -X POST -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"processId":123,"rootUri":null,"capabilities":{}}}' \
     http://localhost:9995/jsonrpc | python -m json.tool

echo -e "\n✅ All MCP components started successfully!"
echo "Use the following commands to check logs:"
echo "  tail -f mcp_server_output.log"
echo "  tail -f jsonrpc_server.log"
echo "  tail -f health_endpoint.log"
