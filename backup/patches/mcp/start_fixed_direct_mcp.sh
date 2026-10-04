#!/bin/bash
# start_fixed_direct_mcp.sh
#
# This script applies all the fixes to the direct MCP server
# and then starts it with optimal settings.
#

set -e  # Exit on any error

echo "📋 Starting IPFS Direct MCP Server with fixes..."

# Directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Apply server.py fixes
echo "🔧 Applying server.py fixes..."
if [ -f "./complete_server_fix.py" ]; then
    chmod +x ./complete_server_fix.py
    ./complete_server_fix.py
else
    echo "❌ complete_server_fix.py not found. Please ensure it exists in the current directory."
    exit 1
fi

# Check if direct_mcp_server.py exists
if [ ! -f "./direct_mcp_server.py" ]; then
    echo "❌ direct_mcp_server.py not found. Please ensure it exists in the current directory."
    exit 1
fi

# Default port and host
PORT=3000
HOST="127.0.0.1"
LOG_LEVEL="INFO"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --port)
        PORT="$2"
        shift
        shift
        ;;
        --host)
        HOST="$2"
        shift
        shift
        ;;
        --log-level)
        LOG_LEVEL="$2"
        shift
        shift
        ;;
        *)
        echo "Unknown option: $1"
        echo "Usage: $0 [--port PORT] [--host HOST] [--log-level LEVEL]"
        exit 1
        ;;
    esac
done

# Check for existing server
if [ -f "./direct_mcp_server_blue.pid" ]; then
    PID=$(cat ./direct_mcp_server_blue.pid)
    if ps -p $PID > /dev/null; then
        echo "⚠️ Direct MCP Server is already running with PID $PID"
        echo "   Use stop_mcp_server.sh to stop it, or use a different port."
        echo "   Continuing with a new instance..."
    fi
fi

# Start the server
echo "🚀 Starting Direct MCP Server on $HOST:$PORT..."
python direct_mcp_server.py --host "$HOST" --port "$PORT" --log-level "$LOG_LEVEL"

# Note: The server will keep running in the foreground
# Press Ctrl+C to stop it
