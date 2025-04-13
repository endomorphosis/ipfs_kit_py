#!/bin/bash
# Stop the MCP AnyIO server by PID

# Check if PID file exists
if [ ! -f "mcp_anyio_server.pid" ]; then
  echo "PID file not found. Server may not be running or was started differently."
  exit 1
fi

# Read PID from file
PID=$(cat mcp_anyio_server.pid)

# Check if process is running
if ! kill -0 $PID 2>/dev/null; then
  echo "Process with PID $PID is not running."
  rm mcp_anyio_server.pid
  exit 1
fi

# Try graceful shutdown first
echo "Sending SIGTERM to process $PID..."
kill $PID

# Wait for process to terminate
for i in {1..10}; do
  if ! kill -0 $PID 2>/dev/null; then
    echo "Process terminated successfully."
    rm mcp_anyio_server.pid
    exit 0
  fi
  echo "Waiting for process to terminate... ($i/10)"
  sleep 1
done

# Force kill if still running
echo "Process did not terminate gracefully. Sending SIGKILL..."
kill -9 $PID

# Final check
if ! kill -0 $PID 2>/dev/null; then
  echo "Process forcefully terminated."
  rm mcp_anyio_server.pid
  exit 0
else
  echo "Failed to terminate process. Please check manually."
  exit 1
fi