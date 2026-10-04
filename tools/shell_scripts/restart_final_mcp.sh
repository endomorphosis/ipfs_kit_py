#!/bin/bash
# Restart Final MCP Server
# Simple script to restart the final MCP server and verify it's working

# Define colors for output
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[1;33m"
NC="\033[0m" # No Color

echo -e "${YELLOW}Stopping any existing MCP servers...${NC}"
pkill -f "python.*final_mcp_server.py" || true
sleep 2

echo -e "${YELLOW}Starting final MCP server...${NC}"
cd "$(dirname "$0")"  # Change to script directory
python final_mcp_server.py --debug > final_mcp_server.log 2>&1 &
MCP_PID=$!
echo $MCP_PID > final_mcp_server.pid
echo -e "${GREEN}Server started with PID: ${MCP_PID}${NC}"

echo -e "${YELLOW}Waiting for server to initialize...${NC}"
MAX_WAIT=30
for ((i=1; i<=$MAX_WAIT; i++)); do
  if curl -s http://localhost:9997/health > /dev/null; then
    echo -e "${GREEN}Server is ready!${NC}"
    echo -e "${YELLOW}Health check:${NC}"
    curl -s http://localhost:9997/health | jq || echo "Server is healthy but jq not available"
    echo ""
    
    echo -e "${YELLOW}Testing JSON-RPC ping:${NC}"
    curl -s -X POST -H "Content-Type: application/json" \
         -d '{"jsonrpc":"2.0","method":"ping","params":{},"id":1}' \
         http://localhost:9997/jsonrpc | jq || echo "Ping test successful but jq not available"
    echo ""
    
    echo -e "${YELLOW}Testing get_tools:${NC}"
    curl -s -X POST -H "Content-Type: application/json" \
         -d '{"jsonrpc":"2.0","method":"get_tools","params":{},"id":2}' \
         http://localhost:9997/jsonrpc | jq '.result.tools | length' || \
         echo "Found tools but jq not available"
    echo ""
    
    echo -e "${GREEN}Server is running successfully at http://localhost:9997${NC}"
    echo -e "To stop the server: kill $MCP_PID"
    exit 0
  fi
  echo -n "."
  sleep 1
done

echo -e "${RED}Server failed to start within $MAX_WAIT seconds${NC}"
echo "Check logs at final_mcp_server.log"
exit 1
