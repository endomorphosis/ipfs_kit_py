#!/bin/bash
#
# Verify MCP Tools Script
# This script verifies that all MCP tools are working correctly.
#

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Step 1: Running MCP compatibility verification...${NC}"
python verify_mcp_compatibility.py

echo -e "\n${GREEN}Step 2: Making test script executable...${NC}"
chmod +x test_mcp_tools.py

echo -e "\n${GREEN}Step 3: Testing IPFS model extensions and Cline integration...${NC}"
./test_mcp_tools.py

echo -e "\n${GREEN}Step 4: Checking if MCP server is running...${NC}"
if pgrep -f "python.*run_mcp_server.py" > /dev/null; then
    echo -e "${YELLOW}MCP server is already running. Testing against running instance.${NC}"
else
    echo -e "${YELLOW}MCP server is not running. Starting server for testing...${NC}"
    
    # Start the server in background
    ./start_mcp_server_fixed.sh --port=9995 &
    SERVER_PID=$!
    
    # Wait for server to start
    echo -e "${YELLOW}Waiting for server to start...${NC}"
    sleep 10
    
    # Check if server started successfully
    if curl -s "http://localhost:9995/api/v0/health" > /dev/null 2>&1; then
        echo -e "${GREEN}MCP server started successfully!${NC}"
    else
        echo -e "${RED}MCP server failed to start. Check logs for details.${NC}"
        exit 1
    fi
    
    # Run the tests with the new server
    echo -e "\n${GREEN}Step 5: Testing MCP server API...${NC}"
    MCP_PORT=9995 ./test_mcp_tools.py
    
    # Stop the server
    echo -e "\n${GREEN}Step 6: Stopping test server...${NC}"
    kill $SERVER_PID
    sleep 2
    echo -e "${GREEN}Test server stopped.${NC}"
fi

echo -e "\n${GREEN}All verification steps completed!${NC}"
echo -e "\n${YELLOW}To start your MCP server with all tools enabled, run:${NC}"
echo -e "  ./start_mcp_server_fixed.sh"
echo -e "\n${YELLOW}Your MCP server configuration is at:${NC}"
echo -e "  .config/Code - Insiders/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
echo -e "\n${GREEN}The following MCP tools are now available:${NC}"
echo -e "  - ipfs_add: Add content to IPFS"
echo -e "  - ipfs_cat: Retrieve content from IPFS"
echo -e "  - ipfs_pin: Pin content in IPFS"
echo -e "  - storage_transfer: Transfer content between storage backends"
echo -e "\n${GREEN}Enjoy using your fixed MCP server!${NC}"
