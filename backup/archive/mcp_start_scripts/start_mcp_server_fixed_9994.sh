#!/bin/bash
# Start MCP server fixed - with consistent port 9994

# Check if the server is already running
PID_FILE="/tmp/mcp_server.pid"

echo "Checking for running MCP server instances..."
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null; then
        echo "MCP server is already running with PID $PID"
        echo "To stop it, run: ./stop_mcp_server.sh"
        exit 1
    else
        echo "Found stale PID file. Removing."
        rm "$PID_FILE"
    fi
else
    echo "No PID file found, checking for running processes..."
    RUNNING_SERVER=$(ps aux | grep "run_mcp_server" | grep -v grep)
    if [ -n "$RUNNING_SERVER" ]; then
        echo "Found running MCP server:"
        echo "$RUNNING_SERVER"
        echo "To stop it, run: ./stop_mcp_server.sh"
        exit 1
    else
        echo "No running MCP server found"
    fi
fi

# Run compatibility checks and fixes
echo "Running MCP compatibility checks and fixes..."
python mcp_compatibility.py

echo "Verifying ipfs_kit_py import path..."
echo "Running import test..."
echo "Python interpreter: $(which python)"
echo "Python version: $(python --version)"

# Run a simple import test
python -c "
print('Importing ipfs_kit_py.mcp.server_bridge...')
from ipfs_kit_py.mcp.server_bridge import MCPServer
print('Import successful, server classes available:', dir(MCPServer))
print('Creating MCPServer instance...')
server = MCPServer(debug_mode=True)
print('MCPServer instance created successfully')
print('Import test passed')
"

# Run MCP model initializer
echo "Running MCP model initializer..."
python -c "
try:
    from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
    from ipfs_kit_py.mcp.models.ipfs_model_fix import fix_ipfs_model
    model = IPFSModel()
    fix_ipfs_model(IPFSModel)
    model = IPFSModel()
    print('IPFSModel initialization and patching successful')
except Exception as e:
    import traceback
    print(f'Error: {e}')
    traceback.print_exc()
"

# Set the port to 9994 to match Cline MCP config
PORT=9994
LOG_FILE="mcp_server.log"
STDOUT_LOG="logs/mcp_server_stdout.log"

# Check for command line arguments
FOREGROUND=false
for arg in "$@"; do
    if [ "$arg" == "--foreground" ]; then
        FOREGROUND=true
    fi
    if [[ "$arg" == "--port="* ]]; then
        PORT="${arg#*=}"
    fi
    if [[ "$arg" == "--log-file="* ]]; then
        LOG_FILE="${arg#*=}"
    fi
done

# Create logs directory if it doesn't exist
mkdir -p logs

# Start the server
echo "Starting MCP server on port $PORT..."
CMD="python ./ipfs_kit_py/run_mcp_server_real_storage.py --port $PORT --api-prefix /api/v0 --log-file $LOG_FILE"

if [ "$FOREGROUND" = true ]; then
    echo "Running MCP server in foreground..."
    eval "$CMD"
else
    # Start in background and save PID
    nohup $CMD > "$STDOUT_LOG" 2>&1 &
    SERVER_PID=$!
    echo "$SERVER_PID" > "$PID_FILE"
    echo "MCP server started with PID $SERVER_PID"
    echo "Logs are being saved to: $LOG_FILE and $STDOUT_LOG"
    echo "To stop the server run: ./stop_mcp_server.sh"
    
    # Wait for a bit to ensure the server has started
    echo "Waiting for server to start..."
    sleep 5
    
    # Check if the server is still running
    if ! ps -p $SERVER_PID > /dev/null; then
        echo "ERROR: MCP server failed to start. Check the logs at: $LOG_FILE"
        exit 1
    fi
    
    # Test the health endpoint
    echo "MCP server is running. Testing health endpoint..."
    HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT/api/v0/health 2>/dev/null || echo "Error")
    
    if [ "$HEALTH_RESPONSE" == "200" ]; then
        echo "MCP server is healthy and responding to requests."
    else
        echo "MCP server did not respond to health check."
        echo "This might be normal if the server is still starting."
        echo "Check the logs at: $LOG_FILE"
    fi
fi

echo "MCP server startup complete"
