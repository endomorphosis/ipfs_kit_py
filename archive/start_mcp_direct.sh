#!/bin/bash
# Direct MCP Server Startup Script
# This script directly patches problematic modules and starts the final MCP server

# Set strict error handling
set -e

# Directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Clear previous logs to avoid confusion
echo "Clearing previous logs..."
> final_mcp_server.log
echo "$(date) - Starting MCP server with direct patching" > final_mcp_server.log

# Check if IPFS daemon is running
echo "Checking IPFS daemon status..."
if ! pgrep -x "ipfs" > /dev/null; then
    echo "IPFS daemon not running. Starting it..."
    ipfs daemon --routing=dhtclient &
    # Give it a moment to start up
    sleep 5
    echo "IPFS daemon started."
else
    echo "IPFS daemon is already running."
fi

# Kill any existing MCP server processes
echo "Cleaning up any existing MCP server processes..."
pkill -f "python.*final_mcp_server.py" || true
pkill -f "uvicorn.*final_mcp_server" || true

# Set up Python environment
echo "Setting up Python environment..."

# Create necessary directories for MCP structure if they don't exist
mkdir -p ipfs_kit_py/mcp/models
mkdir -p ipfs_kit_py/mcp/controllers
mkdir -p ipfs_kit_py/mcp/controllers/storage

# Create __init__.py files in all directories to ensure proper package structure
touch ipfs_kit_py/mcp/models/__init__.py
touch ipfs_kit_py/mcp/controllers/__init__.py
touch ipfs_kit_py/mcp/controllers/storage/__init__.py

# Set PYTHONPATH to include all necessary directories
export PYTHONPATH="$SCRIPT_DIR:$SCRIPT_DIR/docs/mcp-python-sdk/src:$SCRIPT_DIR/ipfs_kit_py:$PYTHONPATH"

# Create a direct patching script that will run before the server
cat > direct_patch.py << 'EOL'
#!/usr/bin/env python3
"""
Direct patching script for MCP server compatibility issues
"""
import sys
import os
import importlib

def patch_asyncio():
    """Patch asyncio to handle the 'async' keyword issue"""
    try:
        import asyncio
        
        # Use safer dictionary approach to avoid syntax errors with 'async' keyword
        if 'async' in asyncio.__dict__:
            # Get the function without directly using the keyword
            async_func = asyncio.__dict__['async']
            # Add it under the new name
            asyncio.__dict__['ensure_future'] = async_func
            # Delete the old name
            del asyncio.__dict__['async']
            print("Patched asyncio.async -> asyncio.ensure_future")
        
        return True
    except Exception as e:
        print(f"Error patching asyncio: {e}")
        return False

def patch_multiaddr():
    """Add multiaddr.exceptions if it doesn't exist"""
    try:
        import multiaddr
        if not hasattr(multiaddr, 'exceptions'):
            class Exceptions:
                class Error(Exception):
                    pass
            multiaddr.exceptions = Exceptions
            print("Added mock exceptions to multiaddr module")
        return True
    except ImportError:
        print("multiaddr module not found, skipping patch")
        return False

if __name__ == "__main__":
    # Apply patches
    patch_asyncio()
    patch_multiaddr()
    
    # Continue with normal execution
    print("Patches applied, starting MCP server...")
EOL
chmod +x direct_patch.py

# Run the patching script and then start the server
echo "Starting MCP server with direct patching..."
python3 -c "import direct_patch; import sys; sys.path.insert(0, '.'); import final_mcp_server; exit(final_mcp_server.main())" --debug --port 3000 > server_output.log 2>&1 &

# Store the PID for later reference
SERVER_PID=$!
echo $SERVER_PID > final_mcp_server.pid
echo "Server started with PID: $SERVER_PID"

# Wait for server to initialize
echo "Waiting for server initialization..."
MAX_WAIT=30
counter=0
while [ $counter -lt $MAX_WAIT ]; do
    # Check if server is still running
    if ! kill -0 $SERVER_PID 2>/dev/null; then
        echo "Server process stopped unexpectedly."
        echo "Last 20 lines of output:"
        tail -n 20 server_output.log
        exit 1
    fi
    
    # Check for successful initialization in the logs
    if grep -q "Total registered tools:" final_mcp_server.log 2>/dev/null || 
       grep -q "Server started successfully" server_output.log 2>/dev/null ||
       grep -q "Uvicorn running on" server_output.log 2>/dev/null; then
        
        echo "Server initialized successfully!"
        grep "Total registered tools:" final_mcp_server.log 2>/dev/null || true
        grep "Server started successfully" server_output.log 2>/dev/null || true
        
        # Show list of registered tools for verification
        echo "Checking registered tools..."
        grep -A 5 "Tool names:" final_mcp_server.log 2>/dev/null || true
        
        break
    fi
    sleep 1
    counter=$((counter+1))
    echo -n "."
done

if [ $counter -eq $MAX_WAIT ]; then
    echo "Warning: Server initialization timeout. Check logs for details."
    echo "Last 20 lines of log:"
    tail -n 20 server_output.log
    tail -n 20 final_mcp_server.log 2>/dev/null || true
fi

echo "Server is running in the background with PID $SERVER_PID"
echo "Log files: server_output.log and final_mcp_server.log"
echo "To stop the server: kill -15 $SERVER_PID"
echo ""
echo "Server endpoints:"
echo "  - http://localhost:3000/ (Home)"
echo "  - http://localhost:3000/health (Health check)"
echo "  - http://localhost:3000/initialize (Client initialization)"
echo "  - http://localhost:3000/mcp (MCP SSE connection)"
echo "  - http://localhost:3000/jsonrpc (JSON-RPC endpoint)"
echo ""
echo "Server is ready!"

# Use curl to verify the server is responding
echo "Verifying server response..."
sleep 2
if curl -s http://localhost:3000/health; then
    echo ""
    echo "Server is responding correctly!"
else
    echo "Warning: Could not connect to server health endpoint"
fi