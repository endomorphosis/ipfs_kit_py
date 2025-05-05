#!/bin/bash
# Integrated MCP Server Solution Startup Script
# This script combines the robustness of start_final_solution.sh with VFS integration

# Set up colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}==================================================${NC}"
echo -e "${BLUE}${BOLD}  FINAL MCP SERVER WITH IPFS/VFS INTEGRATION  ${NC}"
echo -e "${BLUE}${BOLD}==================================================${NC}"

# Step 1: Check and kill any existing MCP server instances
echo -e "\n${GREEN}${BOLD}[1/7] Stopping any running MCP server instances...${NC}"
pkill -f "final_mcp_server.py" || echo "No final MCP server instances found"
pkill -f "direct_mcp_server.py" || echo "No direct MCP server instances found"
pkill -f "enhanced_mcp_server" || echo "No enhanced MCP server instances found"

# Wait for ports to be released
sleep 2
echo "✅ Stopped any running MCP server instances"

# Step 2: Set up environment
echo -e "\n${GREEN}${BOLD}[2/7] Setting up environment...${NC}"
# Set Python paths
export PYTHONPATH=$PYTHONPATH:$(pwd):$(pwd)/ipfs_kit_py
echo "✅ Python paths set"

# Create backup of the current final_mcp_server.py if it doesn't exist
if [ ! -f "final_mcp_server.py.bak.vfs" ]; then
    cp final_mcp_server.py final_mcp_server.py.bak.vfs
    echo "✅ Created backup of final_mcp_server.py as final_mcp_server.py.bak.vfs"
else
    echo "✅ Backup of final_mcp_server.py already exists"
fi

# Step 3: Run the integration scripts
echo -e "\n${GREEN}${BOLD}[3/7] Running integration scripts...${NC}"
python3 final_integration.py
INTEGRATION_STATUS=$?

if [ $INTEGRATION_STATUS -ne 0 ]; then
    echo -e "${RED}Integration script failed. Attempting to continue anyway...${NC}"
else
    echo -e "✅ Integration completed successfully"
fi

# Run the VFS to final MCP integration specifically
echo "Running VFS integration script..."
if [ -f "integrate_vfs_to_final_mcp.py" ]; then
    python3 integrate_vfs_to_final_mcp.py
    VFS_INTEGRATION_STATUS=$?
    
    if [ $VFS_INTEGRATION_STATUS -ne 0 ]; then
        echo -e "${YELLOW}⚠️ VFS integration script returned non-zero status. Continuing anyway...${NC}"
    else
        echo -e "✅ VFS integration completed successfully"
    fi
else
    echo -e "${YELLOW}⚠️ VFS integration script not found. VFS functionality may be limited.${NC}"
fi

# Step 4: Check dependencies
echo -e "\n${GREEN}${BOLD}[4/7] Checking system dependencies...${NC}"
MISSING_DEPS=0

check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}❌ $1 is not installed.${NC}"
        MISSING_DEPS=$((MISSING_DEPS+1))
    else
        echo "✅ $1 is installed"
    fi
}

check_python_module() {
    if ! python3 -c "import $1" &> /dev/null; then
        echo -e "${YELLOW}⚠️ Python module $1 is not installed.${NC}"
        MISSING_DEPS=$((MISSING_DEPS+1))
    else
        echo "✅ Python module $1 is installed"
    fi
}

check_command python3
check_command pip3
check_command curl

check_python_module uvicorn
check_python_module starlette
check_python_module jsonrpc

# Check if ipfs is running
if ! pgrep -x "ipfs" > /dev/null; then
    echo -e "${YELLOW}⚠️ IPFS daemon is not running. Some functionality may be limited.${NC}"

    # Try to start IPFS
    if command -v ipfs &> /dev/null; then
        echo "Attempting to start IPFS daemon..."
        nohup ipfs daemon --routing=dhtclient > ipfs.log 2>&1 &
        sleep 3
        if pgrep -x "ipfs" > /dev/null; then
            echo -e "${GREEN}✅ Successfully started IPFS daemon${NC}"
        else
            echo -e "${RED}❌ Failed to start IPFS daemon${NC}"
            MISSING_DEPS=$((MISSING_DEPS+1))
        fi
    else
        echo -e "${RED}❌ IPFS is not installed${NC}"
        MISSING_DEPS=$((MISSING_DEPS+1))
    fi
else
    echo "✅ IPFS daemon is running"
fi

if [ $MISSING_DEPS -gt 0 ]; then
    echo -e "${YELLOW}⚠️ Some dependencies are missing. Continuing with limited functionality.${NC}"
fi

# Step 5: Ensure all required files are present
echo -e "\n${GREEN}${BOLD}[5/7] Checking for required files...${NC}"
MISSING_FILES=0

check_file() {
    if [ ! -f "$1" ]; then
        echo -e "${RED}❌ $1 is missing${NC}"
        MISSING_FILES=$((MISSING_FILES+1))
    else
        echo "✅ $1 is present"
    fi
}

check_file "final_mcp_server.py"
check_file "unified_ipfs_tools.py"
check_file "ipfs_tools_registry.py"
check_file "enhance_vfs_mcp_integration.py"

if [ $MISSING_FILES -gt 0 ]; then
    echo -e "${RED}❌ Some required files are missing. Cannot continue.${NC}"
    exit 1
fi

# Step 6: Make scripts executable
echo -e "\n${GREEN}${BOLD}[6/7] Making scripts executable...${NC}"
chmod +x final_mcp_server.py
chmod +x unified_ipfs_tools.py
chmod +x integrate_vfs_to_final_mcp.py
chmod +x test_final_mcp_server.py
echo "✅ Made scripts executable"

# Step 7: Start the MCP Server
echo -e "\n${GREEN}${BOLD}[7/7] Starting Final MCP Server with VFS Integration...${NC}"
echo -e "${YELLOW}Server will start in the background. Check final_mcp_server.log for output.${NC}"
nohup python3 final_mcp_server.py --port 3000 > final_mcp_server.log 2>&1 &
SERVER_PID=$!

# Wait for server to start
echo "Waiting for server to start..."
sleep 5

# Check if server is running
if kill -0 $SERVER_PID 2>/dev/null; then
    echo -e "${GREEN}✅ Final MCP Server started successfully with PID $SERVER_PID${NC}"
else
    echo -e "${RED}❌ Failed to start Final MCP Server${NC}"
    echo "Check final_mcp_server.log for details"
    exit 1
fi

# Test server health
echo "Testing server health..."
if curl -s http://localhost:3000/health > /dev/null; then
    echo -e "${GREEN}✅ Server is healthy and responding to requests${NC}"
    
    # Get available tools
    TOOLS=$(curl -s -X POST http://localhost:3000/initialize | grep -o '"tools":\[[^]]*\]' | sed 's/"tools":\[//g' | sed 's/\]//g' | tr ',' '\n' | sed 's/"//g' | sort)
    TOOL_COUNT=$(echo "$TOOLS" | grep -v "^$" | wc -l)

    echo -e "\n${GREEN}${BOLD}SERVER SUCCESSFULLY STARTED WITH $TOOL_COUNT TOOLS${NC}"
    echo -e "${BLUE}Available at:${NC} http://localhost:3000/"
    echo -e "${BLUE}Log file:${NC} $(pwd)/final_mcp_server.log"
    echo -e "${BLUE}Server PID:${NC} $SERVER_PID"

    echo -e "\n${GREEN}${BOLD}AVAILABLE TOOLS:${NC}"
    if [ $TOOL_COUNT -gt 0 ]; then
        echo "$TOOLS" | grep -v "^$" | sort | column
    else
        echo -e "${YELLOW}⚠️ No tools registered. Check the server logs for issues.${NC}"
    fi

    echo -e "\n${BLUE}${BOLD}HOW TO USE:${NC}"
    echo "1. The server is now running at http://localhost:3000"
    echo "2. You can test the server with: python3 test_final_mcp_server.py"
    echo "3. Use Ctrl+C to stop this script"
    echo "4. To stop the server: pkill -f 'final_mcp_server.py'"
    echo -e "\n${GREEN}${BOLD}Ready to use!${NC}"
else
    echo -e "${RED}❌ Server is not responding to health checks${NC}"
    echo "Check final_mcp_server.log for details"
    exit 1
fi

# Keep script running to see logs
echo -e "\n${YELLOW}Showing server logs (Ctrl+C to exit, server will continue running)...${NC}"
tail -f final_mcp_server.log
