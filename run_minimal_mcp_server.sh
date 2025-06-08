#!/bin/bash
# Minimal MCP Server Startup Script

# Set up colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}==================================================${NC}"
echo -e "${BLUE}${BOLD}    MINIMAL MCP SERVER WITH IPFS INTEGRATION      ${NC}"
echo -e "${BLUE}${BOLD}==================================================${NC}"

# Step 1: Check and kill any existing MCP server instances
echo -e "\n${GREEN}${BOLD}[1/5] Stopping any running MCP server instances...${NC}"
pkill -f "final_mcp_server.py" || echo "No final MCP server instances found"
pkill -f "minimal_mcp_server.py" || echo "No minimal MCP server instances found"

# Wait for ports to be released
sleep 2
echo "✅ Stopped any running MCP server instances"

# Step 2: Check dependencies
echo -e "\n${GREEN}${BOLD}[2/5] Checking system dependencies...${NC}"

check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}❌ $1 is not installed.${NC}"
    else
        echo "✅ $1 is installed"
    fi
}

check_command python3
check_command pip3
check_command curl

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "✅ Found virtual environment, activating..."
    source .venv/bin/activate
fi

# Step 3: Make scripts executable
echo -e "\n${GREEN}${BOLD}[3/5] Making scripts executable...${NC}"
chmod +x minimal_mcp_server.py
chmod +x unified_ipfs_tools.py
echo "✅ Made scripts executable"

# Step 4: Start the MCP Server
echo -e "\n${GREEN}${BOLD}[4/5] Starting Minimal MCP Server...${NC}"
echo -e "${YELLOW}Server will start in the background. Check minimal_mcp_server.log for output.${NC}"
nohup python3 minimal_mcp_server.py --port 3000 > minimal_mcp_server.log 2>&1 &
SERVER_PID=$!

# Wait for server to start
echo "Waiting for server to start..."
sleep 3

# Check if server is running
if kill -0 $SERVER_PID 2>/dev/null; then
    echo -e "${GREEN}✅ Minimal MCP Server started successfully with PID $SERVER_PID${NC}"
else
    echo -e "${RED}❌ Failed to start Minimal MCP Server${NC}"
    echo "Check minimal_mcp_server.log for details"
    exit 1
fi

# Step 5: Test server health
echo -e "\n${GREEN}${BOLD}[5/5] Testing server health...${NC}"
if curl -s http://localhost:3000/health > /dev/null; then
    echo -e "${GREEN}✅ Server is healthy and responding to requests${NC}"
    
    # Get available tools
    TOOLS=$(curl -s -X POST http://localhost:3000/initialize | grep -o '"tools":\[[^]]*\]' | sed 's/"tools":\[//g' | sed 's/\]//g' | tr ',' '\n' | sed 's/"//g' | sort)
    TOOL_COUNT=$(echo "$TOOLS" | wc -l)
    
    echo -e "\n${GREEN}${BOLD}SERVER SUCCESSFULLY STARTED WITH $TOOL_COUNT TOOLS${NC}"
    echo -e "${BLUE}Available at:${NC} http://localhost:3000/"
    echo -e "${BLUE}Log file:${NC} $(pwd)/minimal_mcp_server.log"
    echo -e "${BLUE}Server PID:${NC} $SERVER_PID"
    
    echo -e "\n${GREEN}${BOLD}AVAILABLE TOOLS:${NC}"
    echo "$TOOLS" | sort | column
    
    echo -e "\n${BLUE}${BOLD}HOW TO USE:${NC}"
    echo "1. The server is now running at http://localhost:3000"
    echo "2. You can test the server with a curl command: curl http://localhost:3000/health"
    echo "3. Use Ctrl+C to stop this script"
    echo "4. To stop the server: pkill -f 'minimal_mcp_server.py'"
    echo -e "\n${GREEN}${BOLD}Ready to use!${NC}"
else
    echo -e "${RED}❌ Server is not responding to health checks${NC}"
    echo "Check minimal_mcp_server.log for details"
    exit 1
fi

# Keep script running to see logs
echo -e "\n${YELLOW}Showing server logs (Ctrl+C to exit, server will continue running)...${NC}"
tail -f minimal_mcp_server.log
