#!/bin/bash
# Script to start the MCP server

# Default port
PORT=8000
# Default host
HOST="127.0.0.1"
# Default prefix
PREFIX="/api/v0/mcp"
# Default debug mode
DEBUG=true
# Default isolation mode
ISOLATION=true

# Help message
show_help() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -p, --port PORT      Port to run the server on (default: 8000)"
    echo "  -h, --host HOST      Host to bind to (default: 127.0.0.1)"
    echo "  --prefix PREFIX      Prefix for API endpoints (default: /api/v0/mcp)"
    echo "  --no-debug           Disable debug mode"
    echo "  --no-isolation       Disable isolation mode"
    echo "  --help               Show this help message"
}

# Parse command-line arguments
while [ $# -gt 0 ]; do
    case "$1" in
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -h|--host)
            HOST="$2"
            shift 2
            ;;
        --prefix)
            PREFIX="$2"
            shift 2
            ;;
        --no-debug)
            DEBUG=false
            shift
            ;;
        --no-isolation)
            ISOLATION=false
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Build the command
if [ "$DEBUG" = true ]; then
    DEBUG_FLAG="--debug"
else
    DEBUG_FLAG=""
fi

if [ "$ISOLATION" = true ]; then
    ISOLATION_FLAG="--isolation"
else
    ISOLATION_FLAG=""
fi

# Use run_mcp_with_storage.py instead of uvicorn directly
CMD="python run_mcp_with_storage.py --host $HOST --port $PORT --api-prefix $PREFIX $DEBUG_FLAG $ISOLATION_FLAG --simulation-mode"

# Print startup message
echo "Starting MCP server with the following configuration:"
echo "  Host: $HOST"
echo "  Port: $PORT"
echo "  API Prefix: $PREFIX"
echo "  Debug Mode: $DEBUG"
echo "  Isolation Mode: $ISOLATION"
echo ""
echo "MCP server includes the following components:"
echo "  - IPFS Controller: Basic IPFS operations"
echo "  - CLI Controller: Access to all CLI tool functionality"
echo "  - Cache Manager: Efficient content caching"
echo ""
echo "To view CLI endpoints, visit: http://$HOST:$PORT${PREFIX}/docs"
echo ""

# Export environment variables
export MCP_API_PREFIX="$PREFIX"
export MCP_DEBUG_MODE="$DEBUG"
export MCP_ISOLATION_MODE="$ISOLATION"

# Run the server
echo "Running command: $CMD"
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server
$CMD