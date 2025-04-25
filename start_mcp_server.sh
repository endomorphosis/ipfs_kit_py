#!/bin/bash
#
# MCP Server Start Script
# This script starts the MCP server with configurable options
#

# Default values
PORT=9994
DEBUG="true"
ISOLATION="true"
SKIP_DAEMON="true"
API_PREFIX="/api/v0"
LOG_FILE="mcp_server.log"
BACKGROUND="true"

# Function to show usage
show_usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  --port=NUMBER         Port number to use (default: 9994)"
    echo "  --no-debug            Disable debug mode"
    echo "  --no-isolation        Disable isolation mode"
    echo "  --no-skip-daemon      Don't skip daemon initialization"
    echo "  --api-prefix=PATH     Set the API prefix (default: /api/v0)"
    echo "  --log-file=FILE       Log file to use (default: mcp_server.log)"
    echo "  --foreground          Run in foreground (don't detach)"
    echo "  --help                Show this help message"
    exit 1
}

# Parse command line options
for arg in "$@"; do
    case $arg in
        --port=*)
            PORT="${arg#*=}"
            ;;
        --no-debug)
            DEBUG="false"
            ;;
        --no-isolation)
            ISOLATION="false"
            ;;
        --no-skip-daemon)
            SKIP_DAEMON="false"
            ;;
        --api-prefix=*)
            API_PREFIX="${arg#*=}"
            ;;
        --log-file=*)
            LOG_FILE="${arg#*=}"
            ;;
        --foreground)
            BACKGROUND="false"
            ;;
        --help)
            show_usage
            ;;
        *)
            echo "Unknown option: $arg"
            show_usage
            ;;
    esac
done

# Create logs directory if it doesn't exist
mkdir -p logs

# Stop any running instances
echo "Checking for running MCP server instances..."
PID_FILE="/tmp/mcp_server.pid"
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null; then
        echo "Found running MCP server with PID $PID. Stopping it..."
        kill "$PID" 2>/dev/null || true
        sleep 2
    else
        echo "No running MCP server found with PID $PID"
    fi
    rm -f "$PID_FILE"
else
    echo "No PID file found, checking for running processes..."
    pkill -f "python.*(run_mcp_server|enhanced_mcp_server).*py" 2>/dev/null || echo "No running MCP server found"
    sleep 2
fi

# Ensure the log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Build the command with all options - using only arguments that the enhanced script accepts
CMD="./ipfs_kit_py/enhanced_mcp_server_real.py --port $PORT"
[ "$DEBUG" = "true" ] && CMD="$CMD --debug"
# Note: Other arguments (api-prefix, isolation, skip-daemon) are not used by the enhanced script

# Start the server
echo "Starting MCP server..."
if [ "$BACKGROUND" = "true" ]; then
    # Start in background
    nohup python $CMD > "logs/mcp_server_stdout.log" 2>&1 &
    PID=$!
    echo $PID > "$PID_FILE"
    echo "MCP server started with PID $PID"
    echo "Logs are being saved to: $LOG_FILE and logs/mcp_server_stdout.log"
    echo "To stop the server, run: ./stop_mcp_server.sh"
else
    # Start in foreground
    echo "Running MCP server in foreground..."
    python $CMD
fi

# Check if server started successfully
if [ "$BACKGROUND" = "true" ]; then
    echo "Waiting for server to start..."
    sleep 3
    if ps -p "$PID" > /dev/null; then
        echo "MCP server is running. Testing health endpoint..."
        if curl -s "http://localhost:$PORT/api/v0/health" > /dev/null 2>&1 || curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
            echo "MCP server is healthy"
            echo "You can access the API at: http://localhost:$PORT$API_PREFIX"
            echo "API documentation available at: http://localhost:$PORT/docs"
        else
            echo "MCP server did not respond to health check."
            echo "Check the logs at: $LOG_FILE"
        fi
    else
        echo "MCP server failed to start. Check the logs at: $LOG_FILE"
        exit 1
    fi
fi
