#!/bin/bash
# Stop the enhanced MCP server

# Set up colors for better visibility
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m" # No Color

if [ -f "direct_mcp_server_active.txt" ]; then
  PID=$(cat direct_mcp_server_active.txt)
  if [ -n "$PID" ] && ps -p $PID > /dev/null; then
    echo -e "${YELLOW}Stopping MCP server (PID: $PID)...${NC}"
    kill $PID
    sleep 1
    if ! ps -p $PID > /dev/null; then
      echo -e "${GREEN}✅ MCP server stopped successfully${NC}"
      rm -f direct_mcp_server_active.txt
    else
      echo -e "${RED}Failed to stop MCP server gracefully, forcing shutdown...${NC}"
      kill -9 $PID
      sleep 1
      if ! ps -p $PID > /dev/null; then
        echo -e "${GREEN}✅ MCP server stopped successfully (forced)${NC}"
        rm -f direct_mcp_server_active.txt
      else
        echo -e "${RED}❌ Failed to stop MCP server${NC}"
      fi
    fi
  else
    echo -e "${YELLOW}No running MCP server found with PID: $PID${NC}"
    rm -f direct_mcp_server_active.txt
  fi
else
  echo -e "${YELLOW}No MCP server appears to be running${NC}"
fi
