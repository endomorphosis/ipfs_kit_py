#!/bin/bash
# Start IPFS MCP server with comprehensive tools

# Log file for the server
LOG_FILE="ipfs_mcp_server.log"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting IPFS MCP Server with Comprehensive Tools${NC}"
echo "$(date) - Starting server" > $LOG_FILE

# First, ensure we have the comprehensive IPFS tools
if [ ! -f "add_comprehensive_ipfs_tools.py" ]; then
    echo -e "${RED}Error: add_comprehensive_ipfs_tools.py not found${NC}"
    echo "Please ensure you have created the comprehensive IPFS tools file"
    exit 1
fi

# Register the IPFS tools with the MCP server
echo -e "${YELLOW}Registering IPFS tools with MCP server...${NC}"
python3 register_ipfs_tools_with_mcp.py >> $LOG_FILE 2>&1
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to register IPFS tools${NC}"
    echo "Check $LOG_FILE for details"
    exit 1
fi

# Check if we need to run the direct MCP server
if [ -f "direct_mcp_server.py" ]; then
    echo -e "${YELLOW}Using direct_mcp_server.py...${NC}"
    
    # Run the server in the background
    python3 direct_mcp_server.py "$@" >> $LOG_FILE 2>&1 &
    SERVER_PID=$!
    
    # Wait a moment for server to start
    sleep 2
    
    # Check if server is running
    if ps -p $SERVER_PID > /dev/null; then
        echo -e "${GREEN}MCP server started successfully with PID $SERVER_PID${NC}"
        echo $SERVER_PID > direct_mcp_server_active.txt
    else
        echo -e "${RED}Error: MCP server failed to start${NC}"
        echo "Check $LOG_FILE for details"
        exit 1
    fi
    
    # Verify the IPFS tools
    echo -e "${YELLOW}Verifying IPFS tools...${NC}"
    python3 verify_ipfs_tools.py
    
    echo -e "${GREEN}Server is running! Log file: $LOG_FILE${NC}"
    echo "To stop the server, run: ./stop_ipfs_mcp_server.sh"
    
else
    echo -e "${RED}Error: direct_mcp_server.py not found${NC}"
    echo "Please ensure you have the MCP server implementation"
    exit 1
fi
