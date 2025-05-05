#!/bin/bash
# Start the minimal MCP server
# This script uses our simplified implementation that doesn't rely on FastMCP

# Set up color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Starting Minimal MCP Server ===${NC}"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed or not in PATH${NC}"
    exit 1
fi

# Kill any running MCP servers
echo -e "${YELLOW}Stopping any running MCP servers...${NC}"
pkill -f "final_mcp_server.py" || echo "No final_mcp_server.py instances found"
pkill -f "fixed_final_mcp_server.py" || echo "No fixed_final_mcp_server.py instances found"
pkill -f "minimal_mcp_server.py" || echo "No minimal_mcp_server.py instances found"
pkill -f "enhanced_mcp_server_fixed.py" || echo "No enhanced_mcp_server_fixed.py instances found"
pkill -f "vfs_mcp_server.py" || echo "No vfs_mcp_server.py instances found"

# Check for port conflicts
PORT=3000
if lsof -Pi :$PORT -sTCP:LISTEN -t &> /dev/null ; then
    echo -e "${RED}Warning: Port $PORT is already in use. Attempting to free it...${NC}"
    lsof -ti :$PORT | xargs kill -9 || echo "Could not free port $PORT"
fi

# Wait for ports to be released
echo -e "${YELLOW}Waiting for ports to be released...${NC}"
sleep 2

# Check if our server file exists
if [ ! -f "./minimal_mcp_server.py" ]; then
    echo -e "${RED}Error: minimal_mcp_server.py not found${NC}"
    exit 1
fi

# Make sure the script is executable
chmod +x ./minimal_mcp_server.py

# Create log directory if it doesn't exist
mkdir -p logs

# Set up Python paths
SCRIPT_DIR="$(pwd)"
export PYTHONPATH="$SCRIPT_DIR:$SCRIPT_DIR/ipfs_kit_py:$SCRIPT_DIR/ipfs_kit_py/mcp:$SCRIPT_DIR/ipfs_kit_py/ipfs_kit_py:$SCRIPT_DIR/docs/mcp-python-sdk/src:$PYTHONPATH"
echo -e "${YELLOW}Setting Python path to: $PYTHONPATH${NC}"

# Start the server with output logged to file
echo -e "${GREEN}Starting Minimal MCP Server on port $PORT...${NC}"
echo -e "${BLUE}Logs will be saved to logs/minimal_mcp_server.log${NC}"
echo -e "${BLUE}Press Ctrl+C to stop the server${NC}"

# Start the server and capture the PID
PYTHONPATH=$PYTHONPATH python3 ./minimal_mcp_server.py --debug --port $PORT 2>&1 | tee logs/minimal_mcp_server.log &
SERVER_PID=$!

# Write PID to file for later reference
echo $SERVER_PID > minimal_mcp_server.pid
echo -e "${GREEN}Server started with PID $SERVER_PID${NC}"

# Wait for server to initialize (adjust timeout as needed)
echo -e "${YELLOW}Waiting for server to initialize...${NC}"
TIMEOUT=10
COUNT=0
while [ $COUNT -lt $TIMEOUT ]; do
    # Check if server is still running
    if ! kill -0 $SERVER_PID 2>/dev/null; then
        echo -e "${RED}Server process terminated unexpectedly${NC}"
        cat logs/minimal_mcp_server.log
        exit 1
    fi
    
    # Check if server is responding to health checks
    if curl -s http://localhost:$PORT/health > /dev/null; then
        echo -e "${GREEN}Server is responding to health checks!${NC}"
        break
    fi
    
    COUNT=$((COUNT+1))
    sleep 1
    echo -n "."
done

if [ $COUNT -eq $TIMEOUT ]; then
    echo -e "${RED}Server failed to initialize within $TIMEOUT seconds${NC}"
    echo -e "${YELLOW}Check logs/minimal_mcp_server.log for details${NC}"
    exit 1
fi

# Display server health information
echo -e "${BLUE}Server Health Information:${NC}"
curl -s http://localhost:$PORT/health | python3 -m json.tool

# Display registered tools
echo -e "${BLUE}Registered Tools:${NC}"
curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"get_tools","id":1}' http://localhost:$PORT/jsonrpc | python3 -m json.tool

echo -e "${GREEN}Server is running. Press Ctrl+C to stop.${NC}"

# Uncomment if you want the script to wait until the server exits
# wait $SERVER_PID

# Otherwise, just exit successfully
exit 0
