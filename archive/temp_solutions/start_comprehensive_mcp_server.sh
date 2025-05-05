#!/bin/bash
# Comprehensive IPFS MCP Server Start Script
# This script starts the comprehensive MCP server with all IPFS and VFS functionality

# Default settings
PORT=3000
HOST="0.0.0.0"
DEBUG=false
LOG_FILE="comprehensive_mcp_server.log"
PID_FILE="comprehensive_mcp_server.pid"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --port=*)
      PORT="${1#*=}"
      shift
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --host=*)
      HOST="${1#*=}"
      shift
      ;;
    --host)
      HOST="$2"
      shift 2
      ;;
    --debug)
      DEBUG=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--port=PORT] [--host=HOST] [--debug]"
      exit 1
      ;;
  esac
done

# Check if server is already running
if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  if ps -p $PID > /dev/null; then
    echo "Comprehensive MCP server is already running with PID $PID"
    echo "Use stop_comprehensive_mcp_server.sh to stop it first"
    exit 1
  else
    echo "Removing stale PID file"
    rm "$PID_FILE"
  fi
fi

# Set debug mode
if [ "$DEBUG" = true ]; then
  DEBUG_ARG="--debug"
  LOG_LEVEL="debug"
else
  DEBUG_ARG=""
  LOG_LEVEL="info"
fi

echo "Starting Comprehensive IPFS MCP Server..."
echo "Host: $HOST"
echo "Port: $PORT"
echo "Debug: $DEBUG"
echo "Log file: $LOG_FILE"

# Run the server
nohup python comprehensive_final_mcp_server.py \
  --host "$HOST" \
  --port "$PORT" \
  --log-level "$LOG_LEVEL" \
  $DEBUG_ARG > "$LOG_FILE" 2>&1 &

# Save the PID
echo $! > "$PID_FILE"

echo "Server started with PID $(cat $PID_FILE)"
echo "Logs available at $LOG_FILE"
echo "To stop the server, run: ./stop_comprehensive_mcp_server.sh"
