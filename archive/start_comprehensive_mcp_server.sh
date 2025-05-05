#!/bin/bash
# Start script for the Comprehensive IPFS MCP Server
# This script starts the server with appropriate parameters

# Set default values
PORT=3000
HOST="0.0.0.0"
DEBUG=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --port)
      PORT="$2"
      shift 2
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
      echo "Usage: $0 [--port PORT] [--host HOST] [--debug]"
      exit 1
      ;;
  esac
done

# Function to check if a process is running
is_running() {
  if [ -f "comprehensive_mcp_server.pid" ]; then
    PID=$(cat comprehensive_mcp_server.pid)
    if ps -p $PID > /dev/null; then
      return 0  # Process is running
    fi
  fi
  return 1  # Process is not running
}

# Check if server is already running
if is_running; then
  echo "Comprehensive MCP Server is already running with PID $(cat comprehensive_mcp_server.pid)"
  echo "To stop it, use: ./stop_comprehensive_mcp_server.sh"
  exit 0
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install required packages if needed
echo "Installing required packages..."
pip install -q uvicorn starlette python-multipart psutil

# Construct the command
CMD="python3 comprehensive_final_mcp_server.py --port $PORT --host $HOST"
if [ "$DEBUG" = true ]; then
  CMD="$CMD --debug"
fi

# Start the server
echo "Starting Comprehensive IPFS MCP Server on $HOST:$PORT..."
echo "Debug mode: $DEBUG"
echo "Command: $CMD"

# Run the server
if [ "$DEBUG" = true ]; then
  # Run in foreground with full output if debug mode is enabled
  eval $CMD
else
  # Run in background and redirect output to log file
  eval "$CMD > comprehensive_mcp_server_output.log 2>&1 &"
  echo $! > comprehensive_mcp_server.pid
  echo "Server started with PID $(cat comprehensive_mcp_server.pid)"
  echo "Output is being logged to comprehensive_mcp_server_output.log"
  echo "To stop the server, use: ./stop_comprehensive_mcp_server.sh"
fi
