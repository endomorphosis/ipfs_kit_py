#!/bin/bash
# Run the Minimal MCP Server

# Set up colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}==================================================${NC}"
echo -e "${BLUE}${BOLD}    RUNNING MINIMAL MCP SERVER ON PORT 9996      ${NC}"
echo -e "${BLUE}${BOLD}==================================================${NC}"

# Step 1: Stop any running MCP servers
echo -e "\n${GREEN}${BOLD}[1/4] Stopping any running MCP server instances...${NC}"
pkill -f "final_mcp_server.py" || echo "No final MCP server instances found"
pkill -f "minimal_mcp_server.py" || echo "No minimal MCP server instances found"
pkill -f "simple_mcp_server.py" || echo "No simple MCP server instances found"

# Wait for ports to be released
sleep 2
echo "✅ Stopped any running MCP server instances"

# Step 2: Check dependencies
echo -e "\n${GREEN}${BOLD}[2/4] Checking virtual environment...${NC}"
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "✅ Activated virtual environment"
else
    echo -e "${YELLOW}⚠️ No virtual environment found at .venv, using system Python${NC}"
fi

echo -e "\n${GREEN}${BOLD}[3/4] Starting Minimal MCP Server...${NC}"
echo -e "${YELLOW}Server will start in the background on port 9996. Check minimal_mcp_server.log for output.${NC}"

# Make scripts executable
chmod +x minimal_mcp_server.py

# Run the server in the background
nohup python3 minimal_mcp_server.py --port 9996 > minimal_mcp_server.log 2>&1 &
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

# Step 4: Test server health
echo -e "\n${GREEN}${BOLD}[4/4] Testing server health...${NC}"
if curl -s http://localhost:9996/health > /dev/null; then
    echo -e "${GREEN}✅ Server is healthy and responding to requests${NC}"
    echo -e "\n${GREEN}${BOLD}SERVER SUCCESSFULLY STARTED${NC}"
    echo -e "${BLUE}Available at:${NC} http://localhost:9996/"
    echo -e "${BLUE}Log file:${NC} $(pwd)/minimal_mcp_server.log"
    echo -e "${BLUE}Server PID:${NC} $SERVER_PID"
    
    # Get tool information
    TOOL_INFO=$(curl -s http://localhost:9996/initialize || echo "{}")
    TOOLS=$(echo "$TOOL_INFO" | grep -o '"tools":\[[^]]*\]' | sed 's/"tools":\[//g' | sed 's/\]//g' | tr ',' '\n' | sed 's/"//g' | sort || echo "None")
    TOOL_COUNT=$(echo "$TOOLS" | wc -l)
    
    echo -e "\n${GREEN}${BOLD}AVAILABLE TOOLS ($TOOL_COUNT):${NC}"
    echo "$TOOLS" | sort | column
    
    echo -e "\n${BLUE}${BOLD}HOW TO USE:${NC}"
    echo "1. The server is now running at http://localhost:9996"
    echo "2. You can test the server with: curl http://localhost:9996/health"
    echo "3. Use Ctrl+C to stop this script"
    echo "4. To stop the server: pkill -f 'minimal_mcp_server.py'"
    echo -e "\n${GREEN}${BOLD}Ready to use!${NC}"
else
    echo -e "${RED}❌ Server is not responding to health checks${NC}"
    echo "Check minimal_mcp_server.log for details"
    cat minimal_mcp_server.log
    exit 1
fi

# Keep script running to see logs
echo -e "\n${YELLOW}Showing server logs (Ctrl+C to exit, server will continue running)...${NC}"
tail -f minimal_mcp_server.log
