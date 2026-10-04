#!/bin/bash
# Test script for the final MCP server

echo "=== Testing Final MCP Server ==="
echo "Current directory: $(pwd)"
echo "Virtual environment: $(.venv/bin/python --version)"

echo ""
echo "=== Starting Server Test ==="

# Test server help
echo "Testing server help..."
.venv/bin/python final_mcp_server.py --help > help_output.txt 2>&1
echo "Help command exit code: $?"

# Try to start server on test port
echo "Starting server on port 9999..."
.venv/bin/python final_mcp_server.py --port 9999 --debug > server_output.txt 2>&1 &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"

# Wait a bit and test health endpoint
echo "Waiting for server startup..."
sleep 3

# Test health endpoint
echo "Testing health endpoint..."
curl -s http://localhost:9999/health > health_output.txt 2>&1
HEALTH_EXIT_CODE=$?
echo "Health check exit code: $HEALTH_EXIT_CODE"

# Show outputs
echo ""
echo "=== Help Output ==="
cat help_output.txt

echo ""
echo "=== Server Output ==="
head -20 server_output.txt

echo ""
echo "=== Health Output ==="
cat health_output.txt

# Cleanup
echo ""
echo "=== Cleanup ==="
kill $SERVER_PID 2>/dev/null
echo "Test completed"
