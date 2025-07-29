#!/bin/bash
# Enhanced MCP Server Startup Script

set -e

echo "🚀 Starting Enhanced Unified MCP Server"
echo "========================================"

# Check if we're in the right directory
if [ ! -f "enhanced_unified_mcp_server.py" ]; then
    echo "❌ Error: Please run this script from the IPFS Kit project root directory"
    exit 1
fi

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "📦 Activating virtual environment..."
    source .venv/bin/activate
fi

# Install required dependencies if needed
echo "📋 Checking dependencies..."
python -c "import fastapi, uvicorn, psutil, aiohttp" 2>/dev/null || {
    echo "📦 Installing missing dependencies..."
    pip install fastapi uvicorn psutil aiohttp jinja2
}

# Parse command line arguments
HOST="127.0.0.1"
PORT="8765"
DEBUG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --host=*)
            HOST="${1#*=}"
            shift
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --port=*)
            PORT="${1#*=}"
            shift
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --debug)
            DEBUG="--debug"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --host=HOST       Host to bind to (default: 127.0.0.1)"
            echo "  --port=PORT       Port to bind to (default: 8765)"
            echo "  --debug           Enable debug logging"
            echo "  -h, --help        Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Start on default host:port"
            echo "  $0 --port=9000       # Start on port 9000"
            echo "  $0 --debug           # Start with debug logging"
            exit 0
            ;;
        *)
            echo "❌ Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "🌐 Starting server on http://$HOST:$PORT"
echo "📊 Dashboard will be available at http://$HOST:$PORT"
echo ""

# Start the enhanced MCP server
python enhanced_unified_mcp_server.py --host="$HOST" --port="$PORT" $DEBUG
