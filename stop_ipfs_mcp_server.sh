#!/bin/bash
# Stop the IPFS MCP server

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Stopping IPFS MCP Server${NC}"

# Check if the PID file exists
if [ -f "direct_mcp_server_active.txt" ]; then
    # Read the PID from the file
    SERVER_PID=$(cat direct_mcp_server_active.txt)
    
    # Check if the process is still running
    if ps -p $SERVER_PID > /dev/null; then
        echo -e "${YELLOW}Stopping MCP server with PID $SERVER_PID...${NC}"
        
        # Try to stop the server gracefully first
        kill -15 $SERVER_PID
        
        # Give it a moment to stop
        sleep 2
        
        # Check if it's still running
        if ps -p $SERVER_PID > /dev/null; then
            echo -e "${YELLOW}Server didn't stop gracefully, forcing termination...${NC}"
            kill -9 $SERVER_PID
            sleep 1
        fi
        
        # Check one more time
        if ps -p $SERVER_PID > /dev/null; then
            echo -e "${RED}Failed to stop server with PID $SERVER_PID${NC}"
            exit 1
        else
            echo -e "${GREEN}Server stopped successfully${NC}"
            rm direct_mcp_server_active.txt
        fi
    else
        echo -e "${YELLOW}Server with PID $SERVER_PID is not running${NC}"
        rm direct_mcp_server_active.txt
    fi
else
    echo -e "${YELLOW}No active server PID file found${NC}"
    
    # Check if there are any direct_mcp_server.py processes running
    SERVER_PID=$(ps aux | grep "python3 direct_mcp_server.py" | grep -v grep | awk '{print $2}')
    
    if [ ! -z "$SERVER_PID" ]; then
        echo -e "${YELLOW}Found running server process with PID $SERVER_PID${NC}"
        
        # Try to stop the server
        echo -e "${YELLOW}Stopping MCP server with PID $SERVER_PID...${NC}"
        kill -15 $SERVER_PID
        
        # Give it a moment to stop
        sleep 2
        
        # Check if it's still running
        if ps -p $SERVER_PID > /dev/null; then
            echo -e "${YELLOW}Server didn't stop gracefully, forcing termination...${NC}"
            kill -9 $SERVER_PID
            sleep 1
        fi
        
        # Check one more time
        if ps -p $SERVER_PID > /dev/null; then
            echo -e "${RED}Failed to stop server with PID $SERVER_PID${NC}"
            exit 1
        else
            echo -e "${GREEN}Server stopped successfully${NC}"
        fi
    else
        echo -e "${YELLOW}No running MCP server process found${NC}"
    fi
fi

echo -e "${GREEN}IPFS MCP server has been stopped${NC}"
exit 0
