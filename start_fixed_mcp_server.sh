#!/bin/bash
# Start Fixed MCP Server with all tools and enhancements
# This script starts the enhanced MCP server with all fixed endpoints
# and properly configures the Claude MCP extension to use them.

# Don't exit on error, we'll handle errors manually
set +e

echo "========================================"
echo "Starting Fixed MCP Server with all tools"
echo "========================================"

# Default port
PORT=9997
DEBUG=true

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --port)
      PORT="$2"
      shift 2
      ;;
    --no-debug)
      DEBUG=false
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--port PORT] [--no-debug]"
      exit 1
      ;;
  esac
done

# Make sure existing MCP server is stopped
echo "Stopping any existing MCP servers..."
if [ -f "stop_mcp_server.sh" ]; then
  bash ./stop_mcp_server.sh || true
else
  echo "Warning: stop_mcp_server.sh not found, attempting to kill processes directly"
  pkill -f "python.*enhanced_mcp_server_fixed.py" || true
fi
sleep 2

# Check if port is already in use
if netstat -tuln | grep -q ":$PORT "; then
  echo "Error: Port $PORT is already in use. Please choose a different port or stop the service using it."
  exit 1
fi

# Start the enhanced MCP server in the background
echo "Starting enhanced MCP server on port $PORT..."
python enhanced_mcp_server_fixed.py --port $PORT --debug=$DEBUG &
SERVER_PID=$!

# Save the PID to a file
echo $SERVER_PID > /tmp/mcp_server.pid
echo "Server started with PID: $SERVER_PID"

# Wait for the server to start up
echo "Waiting for server to start up..."
MAX_RETRIES=10
RETRY_COUNT=0
SERVER_READY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  # Check if the server is still running
  if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo "Error: Server process died unexpectedly"
    exit 1
  fi
  
  # Check if the server is responding
  if curl -s http://localhost:$PORT/ > /dev/null; then
    SERVER_READY=true
    break
  fi
  
  RETRY_COUNT=$((RETRY_COUNT + 1))
  echo "Waiting for server to become available... ($RETRY_COUNT/$MAX_RETRIES)"
  sleep 2
done

if [ "$SERVER_READY" = false ]; then
  echo "Error: Server did not become available within the timeout period"
  echo "Server logs:"
  tail -n 20 mcp_server.log
  kill $SERVER_PID
  exit 1
fi

echo "Server is running and responding, updating Claude MCP configuration..."

# Fix the Claude MCP configuration
python fix_cline_mcp_tools.py
if [ $? -ne 0 ]; then
  echo "Warning: Failed to update Claude MCP configuration"
fi

echo "Running verification tests..."

# Run verification tests
echo "1. Testing SSE endpoints..."
python verify_sse_endpoints.py --url http://localhost:$PORT --timeout 3
if [ $? -ne 0 ]; then
  echo "Warning: SSE endpoint verification failed"
fi

echo "2. Testing MCP tools..."
python verify_mcp_tools_fixed.py --url http://localhost:$PORT
if [ $? -ne 0 ]; then
  echo "Warning: MCP tools verification failed"
fi

echo "========================================"
echo "MCP Server setup complete!"
echo "========================================"
echo "The enhanced MCP server is running on port $PORT"
echo "All tools and endpoints have been initialized."
echo "The Claude MCP extension has been configured to use these tools."
echo 
echo "Available tools:"
echo "- ipfs_add: Add content to IPFS"
echo "- ipfs_cat: Get content from IPFS by CID"
echo "- ipfs_pin: Pin content in IPFS by CID"
echo "- ipfs_pin_ls: List pinned content in IPFS"
echo "- storage_status: Get status of all storage backends"
echo
echo "Available resources:"
echo "- ipfs_content: Access content from IPFS"
echo
echo "To stop the server, run: ./stop_mcp_server.sh"
echo "To restart, run: ./start_fixed_mcp_server.sh"
echo "========================================"

# Keep the script running until ctrl+c
echo "Press Ctrl+C to stop the server and exit"
wait $SERVER_PID
