#!/bin/bash
# Simple MCP Server Startup Script

# Set up colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}==================================================${NC}"
echo -e "${BLUE}${BOLD}          SIMPLE MCP SERVER SOLUTION             ${NC}"
echo -e "${BLUE}${BOLD}==================================================${NC}"

# Step 1: Stop running servers
echo -e "\n${GREEN}${BOLD}[1/4] Stopping any running MCP server instances...${NC}"
pkill -f "final_mcp_server.py" || echo "No final MCP server instances found"
pkill -f "minimal_mcp_server.py" || echo "No minimal MCP server instances found"
pkill -f "simple_mcp_server.py" || echo "No simple MCP server instances found"

# Wait for ports to be released
sleep 2
echo "✅ Stopped any running MCP server instances"

# Step 2: Make script executable
echo -e "\n${GREEN}${BOLD}[2/4] Making script executable...${NC}"
chmod +x simple_mcp_server.py
echo "✅ Made script executable"

# Step 3: Start the server
echo -e "\n${GREEN}${BOLD}[3/4] Starting Simple MCP Server...${NC}"
echo -e "${YELLOW}Server will start in the background. Check simple_mcp_server.log for output.${NC}"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "✅ Activated virtual environment"
fi

nohup python3 simple_mcp_server.py --port 3000 > simple_mcp_server.log 2>&1 &
SERVER_PID=$!

# Wait for server to start
echo "Waiting for server to start..."
sleep 3

# Check if server is running
if kill -0 $SERVER_PID 2>/dev/null; then
    echo -e "${GREEN}✅ Simple MCP Server started successfully with PID $SERVER_PID${NC}"
else
    echo -e "${RED}❌ Failed to start Simple MCP Server${NC}"
    echo "Check simple_mcp_server.log for details"
    exit 1
fi

# Step 4: Test the server
echo -e "\n${GREEN}${BOLD}[4/4] Testing server health...${NC}"
if curl -s http://localhost:3000/health > /dev/null; then
    echo -e "${GREEN}✅ Server is healthy and responding to requests${NC}"
    echo -e "\n${GREEN}${BOLD}SERVER SUCCESSFULLY STARTED${NC}"
    echo -e "${BLUE}Available at:${NC} http://localhost:3000/"
    echo -e "${BLUE}Log file:${NC} $(pwd)/simple_mcp_server.log"
    echo -e "${BLUE}Server PID:${NC} $SERVER_PID"
    
    # Get tool information
    TOOLS=$(curl -s -X POST http://localhost:3000/initialize | grep -o '"tools":\[[^]]*\]' | sed 's/"tools":\[//g' | sed 's/\]//g' | tr ',' '\n' | sed 's/"//g' | sort)
    TOOL_COUNT=$(echo "$TOOLS" | wc -l)
    
    echo -e "\n${GREEN}${BOLD}AVAILABLE TOOLS ($TOOL_COUNT):${NC}"
    echo "$TOOLS" | sort | column
    
    echo -e "\n${BLUE}${BOLD}HOW TO USE:${NC}"
    echo "1. The server is now running at http://localhost:3000"
    echo "2. You can test the server with: curl http://localhost:3000/health"
    echo "3. Use Ctrl+C to stop this script"
    echo "4. To stop the server: pkill -f 'simple_mcp_server.py'"
    echo -e "\n${GREEN}${BOLD}Ready to use!${NC}"
else
    echo -e "${RED}❌ Server is not responding to health checks${NC}"
    echo "Check simple_mcp_server.log for details"
    exit 1
fi

# Keep script running to see logs
echo -e "\n${YELLOW}Showing server logs (Ctrl+C to exit, server will continue running)...${NC}"
tail -f simple_mcp_server.log
