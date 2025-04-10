#!/bin/bash
#
# Script to run the MCP server tests with the fixed test server
#

# Kill any existing test servers
pkill -f "test_mcp_server" || true
pkill -f "fixed_test_mcp_server.py" || true

# Start the fixed test server
echo "Starting fixed MCP test server..."
python fixed_test_mcp_server.py &
SERVER_PID=$!

# Give it a moment to start
sleep 2

# Run the tests
echo "Running MCP API tests..."
python test_mcp_api.py

# Capture test result
TEST_RESULT=$?

# Kill the server
kill $SERVER_PID

# Report success or failure
if [ $TEST_RESULT -eq 0 ]; then
    echo -e "\n\033[32mALL TESTS PASSED!\033[0m"
else
    echo -e "\n\033[31mTESTS FAILED!\033[0m"
fi

exit $TEST_RESULT