#!/bin/bash
# Start MCP Server with JSON-RPC support 
# This script starts all necessary components and verifies they are working

set -e

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting MCP Server with JSON-RPC support${NC}"
echo "================================================="

# Kill any existing processes
echo -e "${YELLOW}Stopping any existing processes...${NC}"
# Kill any running MCP server and JSON-RPC servers (simple or proxy)
pkill -f "enhanced_mcp_server_fixed.py" 2>/dev/null || true
pkill -f "simple_jsonrpc_server.py" 2>/dev/null || true
pkill -f "mcp_jsonrpc_proxy.py" 2>/dev/null || true
sleep 2

# Start the enhanced MCP server
echo -e "${YELLOW}Starting enhanced MCP server...${NC}"
python ./enhanced_mcp_server_fixed.py --port 9994 --api-prefix /api/v0 > mcp_server.log 2>&1 &
MCP_PID=$!
echo $MCP_PID > mcp_server.pid
echo -e "${GREEN}MCP server started with PID: $MCP_PID${NC}"
sleep 3

# No separate JSON-RPC proxy: enhanced MCP server handles JSON-RPC on /api/v0/jsonrpc
echo -e "${YELLOW}Using MCP server's built-in JSON-RPC endpoint at port 9994${NC}"

# Check if servers are running
MCP_RUNNING=false
JSONRPC_RUNNING=false

# Function to check server status
check_server() {
    local url=$1
    local name=$2
    local max_attempts=${3:-5}
    local attempt=1
    
    echo -e "${YELLOW}Checking $name status...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null; then
            echo -e "${GREEN}✓ $name is running at $url (attempt $attempt)${NC}"
            return 0
        else
            echo -e "${YELLOW}Attempt $attempt: $name not responding yet...${NC}"
            sleep 2
            attempt=$((attempt+1))
        fi
    done
    
    echo -e "${RED}✗ $name failed to start after $max_attempts attempts${NC}"
    return 1
}

# Check both servers
if check_server "http://localhost:9994/" "MCP server"; then
    MCP_RUNNING=true
fi

if check_server "http://localhost:9994/api/v0/jsonrpc" "JSON-RPC endpoint"; then
    JSONRPC_RUNNING=true
fi

# Only continue if both servers are running
if [ "$MCP_RUNNING" = true ] && [ "$JSONRPC_RUNNING" = true ]; then
    echo -e "${GREEN}Both servers are running!${NC}"
    
    # Update VS Code settings for both stable and Insiders
    echo -e "${YELLOW}Updating VS Code settings...${NC}"
    SETTINGS_PATHS=("$HOME/.config/Code/User/settings.json" "$HOME/.config/Code - Insiders/User/settings.json")
    for VSCODE_SETTINGS_FILE in "${SETTINGS_PATHS[@]}"; do
        if [ -f "$VSCODE_SETTINGS_FILE" ]; then
            cp "$VSCODE_SETTINGS_FILE" "$VSCODE_SETTINGS_FILE.bak"
            sed -i 's|"url": "http://localhost:[0-9]*/api/v0/sse"|"url": "http://localhost:9994/api/v0/sse"|g' "$VSCODE_SETTINGS_FILE"
            sed -i 's|"url": "http://localhost:[0-9]*/api/v0/jsonrpc"|"url": "http://localhost:9994/api/v0/jsonrpc"|g' "$VSCODE_SETTINGS_FILE"
            sed -i 's|"url": "http://localhost:[0-9]*/jsonrpc"|"url": "http://localhost:9994/jsonrpc"|g' "$VSCODE_SETTINGS_FILE"
            echo -e "${GREEN}VS Code settings updated at $VSCODE_SETTINGS_FILE${NC}"
        fi
    done
    
    # Test endpoints
    echo -e "\n${YELLOW}Testing key endpoints...${NC}"
    
    echo -e "\nMCP server root:"
    curl -s http://localhost:9994/ | python -m json.tool | head -10
    
    echo -e "\nMCP server SSE endpoint:"
    curl -s -N http://localhost:9994/api/v0/sse | head -1
    
    echo -e "\nJSON-RPC initialize request:"
    curl -s -X POST -H "Content-Type: application/json" \
         -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"processId":123,"rootUri":null,"capabilities":{}}}' \
         http://localhost:9994/jsonrpc | python -m json.tool
    
    echo -e "\n${GREEN}MCP server setup completed successfully!${NC}"
    echo -e "${YELLOW}Server logs:${NC}"
    echo "  - MCP server log: mcp_server.log"
else
    echo -e "${RED}Server setup failed. Please check the logs:${NC}"
    echo "  - MCP server log: mcp_server.log"
    
    # Show the logs
    echo -e "\n${YELLOW}Last 10 lines of MCP server log:${NC}"
    tail -10 mcp_server.log
    
    exit 1
fi
