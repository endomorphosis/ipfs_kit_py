#!/bin/bash
# Start Fixed Final MCP Server
# This script starts the fixed final MCP server with proper environment setup and logging

# Default port
PORT=3002
# Default host
HOST="0.0.0.0"
# Log file
LOG_FILE="mcp_server.log"

# Show usage information
function show_usage {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  --port PORT     Port to run the server on (default: 3001)"
    echo "  --host HOST     Host to bind the server to (default: 0.0.0.0)"
    echo "  --log LOG_FILE  Log file to write output to (default: mcp_server.log)"
    echo "  --help          Show this help message"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)
            PORT="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --log)
            LOG_FILE="$2"
            shift 2
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

echo "== Starting Fixed Final MCP Server ==="
echo "Clearing previous logs..."
> $LOG_FILE

# Check if IPFS daemon is running
echo "Checking IPFS daemon status..."
if pgrep -x "ipfs" > /dev/null; then
    echo "IPFS daemon is already running."
else
    echo "Starting IPFS daemon..."
    ipfs daemon --init &
    sleep 2
    echo "IPFS daemon started."
fi

# Kill any existing MCP server processes
echo "Cleaning up any existing MCP server processes..."
pkill -f "python.*fixed_final_mcp_server.py" || true
sleep 1

# Set up Python environment
echo "Setting up Python environment..."
export PYTHONPATH="$PWD:$PWD/docs/mcp-python-sdk/src:$PWD/ipfs_kit_py:"
echo "PYTHONPATH: $PYTHONPATH"

# Start the server
echo "Starting fixed final MCP server with compatibility fixes..."
python3 fixed_final_mcp_server.py --port $PORT --host $HOST > $LOG_FILE 2>&1 &
SERVER_PID=$!

echo "Server started with PID: $SERVER_PID"

# Wait for server to initialize
echo "Waiting for server initialization..."
for i in {1..10}; do
    if grep -q "Server started successfully" $LOG_FILE; then
        echo "Server initialized successfully!"
        echo ""
        echo "The following MCP tools are available:"
        grep "Total registered tools:" $LOG_FILE | tail -1
        grep "Tool names:" $LOG_FILE | tail -1
        echo ""
        echo "Server is running on http://$HOST:$PORT"
        echo "JSON-RPC endpoint: http://$HOST:$PORT/jsonrpc"
        echo "Health endpoint: http://$HOST:$PORT/health"
        echo ""
        echo "To stop the server: kill $SERVER_PID"
        exit 0
    fi
    
    # Check if the server process is still running
    if ! ps -p $SERVER_PID > /dev/null; then
        echo "Server process stopped unexpectedly."
        echo "Last 20 lines of output:"
        tail -n 20 $LOG_FILE
        exit 1
    fi
    
    echo -n "."
    sleep 1
done

echo "Timed out waiting for server to initialize."
echo "Last 20 lines of output:"
tail -n 20 $LOG_FILE
exit 1
