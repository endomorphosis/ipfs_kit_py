#!/bin/bash
# Enhanced MCP Stack Starter
# This script starts all necessary components with enhanced settings

# Define colors for better output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Print header
echo -e "${YELLOW}====================================${NC}"
echo -e "${YELLOW}Enhanced MCP Server Stack${NC}"
echo -e "${YELLOW}====================================${NC}"

# Define ports
MCP_PORT=9994
JSONRPC_PORT=9995

# Kill any existing processes
echo -e "${YELLOW}Stopping any existing processes...${NC}"
pkill -f "python.*enhanced_mcp_server" 2>/dev/null || true
pkill -f "python.*simple_jsonrpc_server" 2>/dev/null || true
pkill -f "python.*vscode_enhanced_jsonrpc_server" 2>/dev/null || true
sleep 2

# Start the MCP server
echo -e "${YELLOW}Starting enhanced MCP server...${NC}"
python ./enhanced_mcp_server_fixed.py --port ${MCP_PORT} --api-prefix /api/v0 > mcp_server_output.log 2>&1 &
MCP_PID=$!
echo "MCP server started with PID: ${MCP_PID}"
echo ${MCP_PID} > mcp_server.pid

# Start the enhanced JSON-RPC server (new version)
echo -e "${YELLOW}Starting enhanced VS Code JSON-RPC server...${NC}"
python ./vscode_enhanced_jsonrpc_server.py --port ${JSONRPC_PORT} > vscode_jsonrpc_server.log 2>&1 &
JSONRPC_PID=$!
echo "VS Code JSON-RPC server started with PID: ${JSONRPC_PID}"
echo ${JSONRPC_PID} > jsonrpc_server.pid

# Function to check if a server is responding
check_server() {
    local url=$1
    local name=$2
    local max_attempts=$3
    local attempt=1

    echo -e "${YELLOW}Checking ${name} status...${NC}"
    while [ ${attempt} -le ${max_attempts} ]; do
        if curl -s ${url} > /dev/null; then
            echo -e "${GREEN}✓${NC} ${name} is running at ${url} (attempt ${attempt})"
            return 0
        else
            echo "Attempt ${attempt}: ${name} not responding yet..."
            attempt=$((attempt + 1))
            sleep 1
        fi
    done

    echo -e "${RED}✗${NC} ${name} failed to respond after ${max_attempts} attempts"
    return 1
}

# Check if servers are running
MCP_SERVER_OK=false
JSONRPC_SERVER_OK=false

if check_server "http://localhost:${MCP_PORT}/" "MCP server" 5; then
    MCP_SERVER_OK=true
fi

if check_server "http://localhost:${JSONRPC_PORT}/" "JSON-RPC server" 5; then
    JSONRPC_SERVER_OK=true
fi

# Update VS Code settings if both servers are running
if [ "${MCP_SERVER_OK}" = true ] && [ "${JSONRPC_SERVER_OK}" = true ]; then
    echo -e "${GREEN}Both servers are running!${NC}"
    
    # Update VS Code settings
    echo -e "${YELLOW}Updating VS Code settings...${NC}"
    
    # Try to find VS Code settings
    VSCODE_SETTINGS_FILES=(
        "$HOME/.config/Code/User/settings.json"
        "$HOME/.config/Code - Insiders/User/settings.json"
    )
    
    for settings_file in "${VSCODE_SETTINGS_FILES[@]}"; do
        if [ -f "${settings_file}" ]; then
            # Create backup
            cp "${settings_file}" "${settings_file}.bak.$(date +%s)"
            
            # Update settings (naive approach, consider using jq for more reliability)
            # Update MCP SSE endpoint
            if grep -q '"mcp"' "${settings_file}"; then
                sed -i -E 's|"url": "http://localhost:[0-9]+/api/v0/sse"|"url": "http://localhost:'${MCP_PORT}'/api/v0/sse"|g' "${settings_file}"
            else
                # If mcp section doesn't exist, add it at the end before the last '}'
                sed -i '$ s/}/,\n  "mcp": {\n    "servers": {\n      "my-mcp-server": {\n        "url": "http:\/\/localhost:'${MCP_PORT}'\/api\/v0\/sse"\n      }\n    }\n  }\n}/' "${settings_file}"
            fi
            
            # Update JSON-RPC endpoint
            if grep -q '"localStorageNetworkingTools"' "${settings_file}"; then
                sed -i -E 's|"url": "http://localhost:[0-9]+/jsonrpc"|"url": "http://localhost:'${JSONRPC_PORT}'/jsonrpc"|g' "${settings_file}"
            else
                # If localStorageNetworkingTools section doesn't exist, add it at the end before the last '}'
                sed -i '$ s/}/,\n  "localStorageNetworkingTools": {\n    "lspEndpoint": {\n      "url": "http:\/\/localhost:'${JSONRPC_PORT}'\/jsonrpc"\n    }\n  }\n}/' "${settings_file}"
            fi
            
            echo -e "${GREEN}VS Code settings updated successfully${NC}"
        fi
    done
    
    # Test key endpoints
    echo -e "\n${YELLOW}Testing key endpoints...${NC}"
    
    # Test MCP server root
    echo -e "\n${YELLOW}MCP server root:${NC}"
    curl -s http://localhost:${MCP_PORT}/ | python -m json.tool | head -10
    
    # Test MCP server SSE endpoint
    echo -e "\n${YELLOW}MCP server SSE endpoint:${NC}"
    curl -s -N http://localhost:${MCP_PORT}/api/v0/sse | head -1
    
    # Test JSON-RPC initialize request
    echo -e "\n${YELLOW}JSON-RPC initialize request:${NC}"
    curl -s -X POST -H "Content-Type: application/json" \
         -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"processId":123,"rootUri":null,"capabilities":{}}}' \
         http://localhost:${JSONRPC_PORT}/jsonrpc | python -m json.tool
    
    echo -e "\n${GREEN}MCP server setup completed successfully!${NC}"
    echo "Server logs:"
    echo "  - MCP server log: mcp_server_output.log"
    echo "  - JSON-RPC server log: vscode_jsonrpc_server.log"
    
    echo -e "\n${YELLOW}Next Steps:${NC}"
    echo "1. Reload VS Code window (F1 -> Reload Window)"
    echo "2. If you still have issues, see TROUBLESHOOT_VSCODE_MCP.md"
else
    echo -e "${RED}One or both servers failed to start!${NC}"
    
    # Check server logs for errors
    echo -e "\n${YELLOW}MCP server log:${NC}"
    tail -10 mcp_server_output.log
    
    echo -e "\n${YELLOW}JSON-RPC server log:${NC}"
    tail -10 vscode_jsonrpc_server.log
    
    echo -e "\n${RED}Please check the logs for errors and try again.${NC}"
fi
