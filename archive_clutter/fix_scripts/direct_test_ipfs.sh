#!/bin/bash
# Direct Test Runner for IPFS MCP
# This script runs the diagnostic tests with the fixed server

set -e

echo "===== Starting Direct IPFS MCP Test Runner ====="
echo "Current directory: $(pwd)"

# Stop any running server
if [ -f "./final_mcp_server.pid" ]; then
    SERVER_PID=$(cat ./final_mcp_server.pid)
    if ps -p $SERVER_PID > /dev/null; then
        echo "Stopping existing server with PID $SERVER_PID"
        kill $SERVER_PID || true
        sleep 2
    fi
    rm -f ./final_mcp_server.pid
fi

# Start server in the background
echo "Starting MCP server..."
python3 ./final_mcp_server.py --host 0.0.0.0 --port 9998 --debug > ./final_mcp_server.log 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > ./final_mcp_server.pid
echo "Started server with PID $SERVER_PID"

# Wait for server to start
echo "Waiting for server to start..."
for i in {1..30}; do
    if curl -s http://localhost:9998/health > /dev/null; then
        echo "✅ Server started successfully"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Failed to start server within 30 seconds"
        cat ./final_mcp_server.log
        exit 1
    fi
    echo "Attempt $i/30: Server not ready yet, waiting..."
    sleep 1
done

# Wait a bit for the server to fully initialize
echo "Giving the server a moment to fully initialize..."
sleep 2

# Create test file with content
echo "Creating test file..."
TEST_CONTENT="Hello IPFS MCP World - Test Content!"
echo "$TEST_CONTENT" > test_ipfs_file.txt

# Test ipfs_add with explicit content parameter
echo -e "\n===== Testing ipfs_add with explicit content parameter ====="
curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"ipfs_add","params":{"content":"'"$TEST_CONTENT"'"},"id":1}' http://localhost:9998/jsonrpc | python3 -m json.tool

# Test ipfs_add with file content loaded from file
echo -e "\n===== Testing ipfs_add with file content ====="
FILE_CONTENT=$(cat test_ipfs_file.txt)
curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"ipfs_add","params":{"content":"'"$FILE_CONTENT"'"},"id":2}' http://localhost:9998/jsonrpc | python3 -m json.tool

# Run diagnostic tests
echo -e "\n===== Running diagnostic tests ====="
python3 ./diagnose_ipfs_tools.py

# Check final server status
echo -e "\n===== Final server status ====="
curl -s http://localhost:9998/health | python3 -m json.tool

# Show recent server logs
echo -e "\n===== Server logs ====="
tail -50 ./final_mcp_server.log

# Don't stop the server to allow further testing
echo -e "\n===== Test run complete ====="
echo "Server is still running with PID $SERVER_PID"
echo "To stop it, run: kill $SERVER_PID"
