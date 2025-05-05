#!/bin/bash
# MCP Server Starter with VFS Integration
# This script starts the MCP server with Virtual Filesystem integration and verifies that the tools are working.

echo "🚀 Starting MCP Server with VFS Integration"
echo "=========================================="

# Make sure script is executable
chmod +x verify_vfs_tools.py

# Stop any running MCP server instances
echo "Stopping any existing MCP server processes..."
pkill -f "python.*direct_mcp_server.py" || true
sleep 2

# Start the MCP server
echo "Starting MCP server with VFS integration..."
cd /home/barberb/ipfs_kit_py
python3 direct_mcp_server.py > mcp_server_vfs.log 2>&1 &
echo $! > mcp_server_vfs.pid
echo "Server started with PID $(cat mcp_server_vfs.pid)"

# Wait for server to initialize
echo "Waiting for server to initialize..."
sleep 5

# Check server status
echo "Verifying server is running..."
TRIES=0
MAX_TRIES=10
SERVER_UP=0

while [ $TRIES -lt $MAX_TRIES ] && [ $SERVER_UP -eq 0 ]; do
    TRIES=$((TRIES+1))
    curl -s http://localhost:3000/ > /dev/null
    if [ $? -eq 0 ]; then
        SERVER_UP=1
    else
        echo "Server not ready yet, waiting... (attempt $TRIES/$MAX_TRIES)"
        sleep 2
    fi
done

if [ $SERVER_UP -eq 0 ]; then
    echo "❌ Error: Could not connect to MCP server after multiple attempts"
    echo "Last 20 lines of server log:"
    tail -n 20 mcp_server_vfs.log
    exit 1
else
    echo "✅ MCP server is running!"
    SERVER_INFO=$(curl -s http://localhost:3000/)
    echo "Server info: $SERVER_INFO"
fi

# Verify VFS tool registration
echo "Verifying VFS tool registration..."
python3 verify_vfs_tools.py

if [ $? -eq 0 ]; then
    echo "✅ VFS integration successful!"
    echo "The MCP server is now running with Virtual Filesystem tools."
    echo "Server PID: $(cat mcp_server_vfs.pid)"
    echo "Server log: mcp_server_vfs.log"
else
    echo "❌ VFS integration verification failed"
    echo "Last 20 lines of server log:"
    tail -n 20 mcp_server_vfs.log
    exit 1
fi

# Create a test file to demonstrate VFS tools
TIMESTAMP=$(date +%s)
TEST_CONTENT="This is a test file created by the VFS integration test at $(date)"
TEST_FILE="vfs_test_$TIMESTAMP.txt"

echo "Creating a test file using the VFS tools..."
curl -s -X POST "http://localhost:3000/jsonrpc" \
  -H "Content-Type: application/json" \
  -d "{
    \"jsonrpc\": \"2.0\",
    \"id\": 2,
    \"method\": \"execute_tool\",
    \"params\": {
      \"name\": \"vfs_write_file\",
      \"arguments\": {
        \"path\": \"$TEST_FILE\",
        \"content\": \"$TEST_CONTENT\"
      }
    }
  }" | grep -q "\"success\":true" && echo "✅ Successfully created test file $TEST_FILE" || echo "❌ Failed to create test file"

# Check the contents of the test file
if [ -f "$TEST_FILE" ]; then
    echo "Test file contents:"
    cat "$TEST_FILE"
    echo ""
    echo "✅ VFS write operation confirmed"
else
    echo "❌ Test file was not created"
fi

echo ""
echo "⚠️  The MCP server is still running in the background. To stop it, run:"
echo "kill \$(cat mcp_server_vfs.pid)"
echo ""
echo "✅ VFS integration complete!"
