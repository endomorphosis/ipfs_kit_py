#!/bin/bash
# Very simple MCP server starter

# Kill any existing servers
pkill -f "python.*final_mcp_server.py" || echo "No existing servers to kill"
sleep 2

# Start the server
cd "$(dirname "$0")"
python final_mcp_server.py --debug > final_mcp_server.log 2>&1 &
PID=$!
echo $PID > final_mcp_server.pid
echo "MCP server started with PID: $PID"

# Wait for server to start
echo "Waiting for server to initialize..."
for i in {1..30}; do
  if curl -s http://localhost:9997/health > /dev/null; then
    echo "Server is up and running!"
    echo "Health check: $(curl -s http://localhost:9997/health | grep status)"
    echo "JSON-RPC endpoint: http://localhost:9997/jsonrpc"
    exit 0
  fi
  echo -n "."
  sleep 1
done

echo "Warning: Server may not have started properly. Check logs in final_mcp_server.log"
