#!/bin/bash
# Script to start the MCP server with WebRTC support enabled

# Set environment variables to force WebRTC availability
export IPFS_KIT_FORCE_WEBRTC=1
export FORCE_WEBRTC_TESTS=1
export IPFS_KIT_RUN_ALL_TESTS=1

# Default values
HOST="127.0.0.1"
PORT=9999
DEBUG=0
PERSISTENCE_PATH=""

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --debug)
            DEBUG=1
            shift
            ;;
        --persistence-path)
            PERSISTENCE_PATH="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [--host HOST] [--port PORT] [--debug] [--persistence-path PATH]"
            echo "  --host HOST             Host to bind to (default: 127.0.0.1)"
            echo "  --port PORT             Port to run the server on (default: 9999)"
            echo "  --debug                 Enable debug mode"
            echo "  --persistence-path PATH Path for persistence files"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Print status information
echo "Starting MCP server with WebRTC support enabled"
echo "IPFS_KIT_FORCE_WEBRTC=${IPFS_KIT_FORCE_WEBRTC}"
echo "FORCE_WEBRTC_TESTS=${FORCE_WEBRTC_TESTS}"

# Kill any existing MCP server processes
pids=$(ps aux | grep "uvicorn.*run_mcp_with_webrtc:app" | grep -v grep | awk '{print $2}')
if [ -n "$pids" ]; then
    echo "Stopping existing MCP server processes: $pids"
    kill -9 $pids
fi

# Build command with arguments
CMD="python run_mcp_with_webrtc.py --host $HOST --port $PORT"

if [ $DEBUG -eq 1 ]; then
    CMD="$CMD --debug"
fi

if [ -n "$PERSISTENCE_PATH" ]; then
    CMD="$CMD --persistence-path $PERSISTENCE_PATH"
fi

# Print the command being executed
echo "Executing: $CMD"

# Start the MCP server with WebRTC support
$CMD

# Check if the server started successfully
if [ $? -ne 0 ]; then
    echo "Error: MCP server failed to start"
    exit 1
fi