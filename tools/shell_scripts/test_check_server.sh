#!/bin/bash
# Test script for check_server.py enhancements

echo "===== MCP Server Check Tool Test ====="
echo ""

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Function for running tests
run_test() {
    local test_name="$1"
    local command="$2"
    
    echo -e "${BLUE}Running test:${NC} ${BOLD}$test_name${NC}"
    echo -e "${YELLOW}Command:${NC} $command"
    echo -e "${YELLOW}Output:${NC}"
    
    if eval "$command"; then
        echo -e "\n${GREEN}Test passed!${NC}"
        return 0
    else
        echo -e "\n${RED}Test failed!${NC}"
        return 1
    fi
    
    echo ""
}

# Test 1: Check if server is running
run_test "Check Server Status" "./check_server.py" || true

# Test 2: Start server if not running
run_test "Start Server" "./check_server.py --start" || true

# Test 3: Get server info
run_test "Get Server Info" "./check_server.py --info" || true

# Test 4: List tools
run_test "List Tools" "./check_server.py --list-tools" || true

# Test 5: Restart server
run_test "Restart Server" "./check_server.py --restart" || true

# Test 6: Stop server
run_test "Stop Server" "./check_server.py --stop" || true

echo -e "\n${BOLD}All tests completed!${NC}"
