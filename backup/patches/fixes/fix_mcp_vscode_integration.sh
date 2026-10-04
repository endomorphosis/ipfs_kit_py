#!/usr/bin/env bash
# All-in-one script to fix MCP server VS Code integration

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== MCP Server VS Code Integration Fix ===${NC}"
echo "This script will fix the integration between MCP server and VS Code"

# Step 1: Kill any existing processes
echo -e "\n${YELLOW}Stopping any existing processes...${NC}"
pkill -f "python.*enhanced_mcp_server" 2>/dev/null || true
pkill -f "python.*mcp_vscode_proxy" 2>/dev/null || true
pkill -f "python.*simple_jsonrpc_server" 2>/dev/null || true
pkill -f "python.*vscode_enhanced_jsonrpc_server" 2>/dev/null || true
sleep 2

# Step 2: Start the MCP server
echo -e "\n${YELLOW}Starting enhanced MCP server...${NC}"
python ./enhanced_mcp_server_fixed.py --port 9994 --api-prefix /api/v0 > mcp_server_output.log 2>&1 &
MCP_PID=$!
echo "MCP server started with PID: ${MCP_PID}"
echo ${MCP_PID} > mcp_server.pid

# Step 3: Start the JSON-RPC server
echo -e "\n${YELLOW}Starting VS Code JSON-RPC server...${NC}"
python ./vscode_enhanced_jsonrpc_server.py --port 9995 > vscode_jsonrpc_server.log 2>&1 &
JSONRPC_PID=$!
echo "VS Code JSON-RPC server started with PID: ${JSONRPC_PID}"
echo ${JSONRPC_PID} > jsonrpc_server.pid

# Step 4: Wait for servers to start
echo -e "\n${YELLOW}Waiting for servers to start...${NC}"
sleep 5

# Step 5: Update VS Code settings to use the proxy
echo -e "\n${YELLOW}Updating VS Code settings...${NC}"
python ./update_vscode_settings_for_proxy.py

# Step 6: Start the MCP VS Code proxy
echo -e "\n${YELLOW}Starting MCP VS Code proxy...${NC}"
python ./mcp_vscode_proxy.py > mcp_vscode_proxy.log 2>&1 &
PROXY_PID=$!
echo "MCP VS Code proxy started with PID: ${PROXY_PID}"
echo ${PROXY_PID} > mcp_vscode_proxy.pid

# Step 7: Verify everything is working
echo -e "\n${YELLOW}Verifying setup...${NC}"
sleep 2

# Check MCP server
if curl -s http://localhost:9994/ > /dev/null; then
  echo -e "${GREEN}✓${NC} MCP server is running at http://localhost:9994/"
else
  echo -e "${RED}✗${NC} MCP server is not running"
fi

# Check JSON-RPC server
if curl -s http://localhost:9995/ > /dev/null; then
  echo -e "${GREEN}✓${NC} JSON-RPC server is running at http://localhost:9995/"
else
  echo -e "${RED}✗${NC} JSON-RPC server is not running"
fi

# Check MCP proxy
if curl -s http://localhost:9996/ > /dev/null; then
  echo -e "${GREEN}✓${NC} MCP proxy is running at http://localhost:9996/"
else
  echo -e "${RED}✗${NC} MCP proxy is not running"
fi

# Step 8: Display next steps
echo -e "\n${GREEN}Setup completed!${NC}"
echo "Next steps:"
echo "1. Reload VS Code window (F1 -> Reload Window)"
echo "2. If VS Code still doesn't connect, check mcp_vscode_proxy.log for errors"
echo "3. If needed, run debug_vscode_connection.py to diagnose connection issues"

echo -e "\n${YELLOW}Server logs:${NC}"
echo "- MCP server log: mcp_server_output.log"
echo "- JSON-RPC server log: vscode_jsonrpc_server.log"
echo "- MCP proxy log: mcp_vscode_proxy.log"
