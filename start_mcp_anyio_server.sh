#!/bin/bash
# Start the MCP AnyIO server in the background with proper error handling

# Define default parameters
PORT=9993
DEBUG="--debug"
ISOLATION="--isolation"
SKIP_DAEMON="--skip-daemon"
API_PREFIX="/api/v0"
LOG_FILE="mcp_anyio_server.log"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --port=*)
      PORT="${1#*=}"
      shift
      ;;
    --no-debug)
      DEBUG=""
      shift
      ;;
    --no-isolation)
      ISOLATION=""
      shift
      ;;
    --no-skip-daemon)
      SKIP_DAEMON=""
      shift
      ;;
    --api-prefix=*)
      API_PREFIX="${1#*=}"
      shift
      ;;
    --log-file=*)
      LOG_FILE="${1#*=}"
      shift
      ;;
    --help)
      echo "Usage: $0 [options]"
      echo "  --port=NUMBER       Port number to use (default: 9993)"
      echo "  --no-debug          Disable debug mode"
      echo "  --no-isolation      Disable isolation mode"
      echo "  --no-skip-daemon    Don't skip daemon initialization"
      echo "  --api-prefix=PATH   Set the API prefix (default: /api/v0)"
      echo "  --log-file=FILE     Log file to use (default: mcp_anyio_server.log)"
      echo "  --help              Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# Build the command
CMD="python run_mcp_server_anyio_fixed.py --port $PORT"
if [ -n "$DEBUG" ]; then
  CMD="$CMD $DEBUG"
fi
if [ -n "$ISOLATION" ]; then
  CMD="$CMD $ISOLATION"
fi
if [ -n "$SKIP_DAEMON" ]; then
  CMD="$CMD $SKIP_DAEMON"
fi
CMD="$CMD --api-prefix=$API_PREFIX"

# Print startup message
echo "Starting MCP AnyIO server..."
echo "Command: $CMD"
echo "Server URL: http://localhost:$PORT"
echo "Logs: $LOG_FILE"

# Start server in background
nohup $CMD > "$LOG_FILE" 2>&1 &
PID=$!

# Save PID to file for later reference
echo $PID > mcp_anyio_server.pid

# Wait briefly to check if process is still running
sleep 2
if kill -0 $PID 2>/dev/null; then
  echo "Server started successfully with PID $PID"
  echo "Run the following to stop the server:"
  echo "  kill \$(cat mcp_anyio_server.pid)"
  echo "Run the following to test the server:"
  echo "  python test_mcp_api_anyio.py --url http://localhost:$PORT"
else
  echo "Server failed to start. Check $LOG_FILE for details."
  exit 1
fi