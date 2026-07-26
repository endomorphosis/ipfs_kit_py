#!/bin/bash
# Start the enhanced MCP server with all IPFS Kit features

# Set up colors for better visibility
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
BLUE="\033[0;34m"
NC="\033[0m" # No Color

echo -e "${BLUE}Starting Enhanced MCP Server with IPFS Kit Integration${NC}"

# Stop any running server
if [ -f "direct_mcp_server_active.txt" ]; then
  PID=$(cat direct_mcp_server_active.txt)
  if [ -n "$PID" ] && ps -p $PID > /dev/null; then
    echo -e "${YELLOW}Stopping running MCP server (PID: $PID)...${NC}"
    kill $PID
    sleep 1
  fi
  rm -f direct_mcp_server_active.txt
fi

# Start the server in the background
python direct_mcp_server.py > mcp_server.log 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > direct_mcp_server_active.txt

# Wait for server to start
echo -e "${YELLOW}Waiting for server to start...${NC}"
sleep 2

# Check if server is running
if ps -p $SERVER_PID > /dev/null; then
  echo -e "${GREEN}✅ MCP server started successfully${NC}"
  echo -e "${GREEN}ℹ️ Server is running at http://127.0.0.1:3000${NC}"
  echo ""
  echo -e "${BLUE}Available Features:${NC}"
  echo -e "  ${GREEN}✓${NC} IPFS Core Operations"
  echo -e "  ${GREEN}✓${NC} IPFS MFS (Mutable File System)"
  echo -e "  ${GREEN}✓${NC} FS Journal for tracking filesystem operations"
  echo -e "  ${GREEN}✓${NC} IPFS-FS Bridge for mapping between IPFS and local filesystem"
  echo -e "  ${GREEN}✓${NC} Multi-Backend Storage (IPFS, HuggingFace, S3, Filecoin, etc.)"
  echo -e "  ${GREEN}✓${NC} Content prefetching and search capabilities"
  echo -e "  ${GREEN}✓${NC} Data format conversion and transformation"
  echo ""
  echo -e "${BLUE}Available Tools:${NC}"
  echo -e "  Run ${YELLOW}python verify_tools.py${NC} to view all available tools"
  echo ""
  echo -e "${BLUE}To stop the server:${NC}"
  echo -e "  Run ${YELLOW}bash stop_enhanced_mcp_server.sh${NC}"
else
  echo -e "${RED}❌ Failed to start MCP server. Check mcp_server.log for details.${NC}"
  exit 1
fi
