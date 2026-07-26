#!/bin/bash
# Improved test script to diagnose and fix issues with the MCP server

set -e  # Exit on any error

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Kill any existing servers
echo -e "${BLUE}Stopping any existing MCP servers...${NC}"
./run_final_solution.sh --stop || true

# Start the server with enhanced debugging
echo -e "${BLUE}Starting the MCP server with debug mode...${NC}"
python3 final_mcp_server.py --host 0.0.0.0 --port 9998 --debug > final_mcp_server.log 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > final_mcp_server.pid

# Wait for server to start
echo -e "${BLUE}Waiting for server to initialize...${NC}"
sleep 5

# Check if server is running
if ! ps -p $SERVER_PID > /dev/null; then
    echo -e "${RED}Server failed to start! Check logs:${NC}"
    cat final_mcp_server.log
    exit 1
fi

# Check if the health endpoint is responding
echo -e "${BLUE}Testing health endpoint...${NC}"
HEALTH_RESPONSE=$(curl -s http://localhost:9998/health)
if [ $? -ne 0 ] || [ -z "$HEALTH_RESPONSE" ]; then
    echo -e "${RED}Health endpoint not responding! Server logs:${NC}"
    cat final_mcp_server.log
    kill $SERVER_PID
    exit 1
else
    echo -e "${GREEN}Health endpoint responding: $HEALTH_RESPONSE${NC}"
fi

# Test a simple JSON-RPC call
echo -e "${BLUE}Testing JSON-RPC ping...${NC}"
PING_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc": "2.0", "method": "ping", "params": {}, "id": 1}' http://localhost:9998/jsonrpc)
if [ $? -ne 0 ] || [ -z "$PING_RESPONSE" ]; then
    echo -e "${RED}JSON-RPC endpoint not responding! Server logs:${NC}"
    cat final_mcp_server.log
    kill $SERVER_PID
    exit 1
else
    echo -e "${GREEN}JSON-RPC ping response: $PING_RESPONSE${NC}"
fi

# Run the test suite
echo -e "${BLUE}Running test suite...${NC}"
python3 test_ipfs_mcp_tools.py --host localhost --port 9998 --verbose
TEST_RESULT=$?

# Stop the server
echo -e "${BLUE}Stopping the server...${NC}"
kill $SERVER_PID

# Show results
if [ $TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}All tests passed successfully!${NC}"
else
    echo -e "${RED}Some tests failed. Check the output above for details.${NC}"
    echo -e "${YELLOW}Logs from the server:${NC}"
    cat final_mcp_server.log
fi

exit $TEST_RESULT
