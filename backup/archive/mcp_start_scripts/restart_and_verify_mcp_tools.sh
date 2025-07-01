#!/bin/bash
# Comprehensive script to restart and verify all MCP server tools are working

set -e

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== MCP Server Tools Verification Script ===${NC}"
echo -e "${BLUE}================================================${NC}"

echo -e "\n${YELLOW}Step 1: Stopping any existing MCP processes...${NC}"
pkill -f "enhanced_mcp_server_fixed.py" 2>/dev/null || true
pkill -f "simple_jsonrpc_server.py" 2>/dev/null || true
pkill -f "mcp_jsonrpc_proxy.py" 2>/dev/null || true
sleep 2
echo -e "${GREEN}All previous processes stopped.${NC}"

echo -e "\n${YELLOW}Step 2: Starting enhanced MCP server...${NC}"
python ./enhanced_mcp_server_fixed.py --port 9994 --api-prefix /api/v0 > mcp_server.log 2>&1 &
MCP_PID=$!
echo $MCP_PID > mcp_server.pid
echo -e "${GREEN}MCP server started with PID: ${MCP_PID}${NC}"
sleep 5

# Function to check server status
check_endpoint() {
    local url=$1
    local name=$2
    local max_attempts=${3:-5}
    local attempt=1
    
    echo -e "\n${YELLOW}Checking ${name}...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null; then
            echo -e "${GREEN}✓ ${name} is available at ${url} (attempt ${attempt})${NC}"
            return 0
        else
            echo -e "${YELLOW}Attempt ${attempt}: ${name} not responding yet...${NC}"
            sleep 2
            attempt=$((attempt+1))
        fi
    done
    
    echo -e "${RED}✗ ${name} failed to start after ${max_attempts} attempts${NC}"
    return 1
}

# Verify key endpoints
ROOT_ENDPOINT="http://localhost:9994/"
HEALTH_ENDPOINT="http://localhost:9994/api/v0/health"
JSONRPC_ENDPOINT="http://localhost:9994/api/v0/jsonrpc"
SSE_ENDPOINT="http://localhost:9994/api/v0/sse"
TOOLS_ENDPOINT="http://localhost:9994/api/v0/tools"

# Check all important endpoints
check_endpoint "$ROOT_ENDPOINT" "MCP server root" || { echo -e "${RED}MCP server root not available. Check mcp_server.log for errors.${NC}"; exit 1; }
check_endpoint "$HEALTH_ENDPOINT" "Health endpoint" || { echo -e "${RED}Health endpoint not available. Check mcp_server.log for errors.${NC}"; exit 1; }
check_endpoint "$TOOLS_ENDPOINT" "Tools listing endpoint" || { echo -e "${YELLOW}Warning: Tools listing endpoint not available.${NC}"; }

echo -e "\n${YELLOW}Step 3: Verifying JSON-RPC initialize request...${NC}"
INITIALIZE_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"processId":123,"rootUri":null,"capabilities":{}}}' \
     $JSONRPC_ENDPOINT)

if echo "$INITIALIZE_RESPONSE" | grep -q "capabilities"; then
    echo -e "${GREEN}✓ JSON-RPC initialize response contains capabilities${NC}"
    echo -e "${BLUE}Response preview:${NC}"
    echo "$INITIALIZE_RESPONSE" | python -m json.tool | head -10
else
    echo -e "${RED}✗ JSON-RPC initialize response does not contain capabilities${NC}"
    echo -e "${RED}Response: ${NC}"
    echo "$INITIALIZE_RESPONSE" | python -m json.tool
    exit 1
fi

echo -e "\n${YELLOW}Step 4: Verifying SSE connection...${NC}"
SSE_RESPONSE=$(curl -s -N "$SSE_ENDPOINT" --max-time 3)
if echo "$SSE_RESPONSE" | grep -q "connection"; then
    echo -e "${GREEN}✓ SSE endpoint is streaming events${NC}"
    echo -e "${BLUE}First event received:${NC}"
    echo "$SSE_RESPONSE" | head -1
else
    echo -e "${RED}✗ SSE endpoint is not streaming events${NC}"
    echo -e "${RED}Response: ${NC}"
    echo "$SSE_RESPONSE"
    exit 1
fi

echo -e "\n${YELLOW}Step 5: Running debug_vscode_connection.py to verify VS Code compatibility...${NC}"
python debug_vscode_connection.py

echo -e "\n${YELLOW}Step 6: Checking available MCP tools...${NC}"
TOOLS_RESPONSE=$(curl -s "$TOOLS_ENDPOINT")
echo -e "${BLUE}Available tools:${NC}"
echo "$TOOLS_RESPONSE" | python -m json.tool

echo -e "\n${GREEN}============================================${NC}"
echo -e "${GREEN}✓ MCP server tools verification complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo -e "${BLUE}The server is running at:${NC} http://localhost:9994/"
echo -e "${BLUE}JSON-RPC endpoint:${NC} $JSONRPC_ENDPOINT"
echo -e "${BLUE}SSE endpoint:${NC} $SSE_ENDPOINT"
echo -e "${BLUE}Tools endpoint:${NC} $TOOLS_ENDPOINT" 
echo -e "${BLUE}Log file:${NC} mcp_server.log"
echo -e "${BLUE}Process ID:${NC} $MCP_PID"
echo -e "${GREEN}============================================${NC}"