#!/usr/bin/env bash
# Enhanced IPFS MCP Test Runner
# This script runs the diagnostic tests and verifies that parameter handling works correctly

set -e

echo "===== Starting Enhanced IPFS MCP Test Runner ====="
echo "Current directory: $(pwd)"

# Function to check if the server is running
check_server() {
    echo "Checking if MCP server is running..."
    if curl -s http://localhost:9998/health > /dev/null; then
        echo "✅ MCP server is running"
        return 0
    else
        echo "❌ MCP server is not running"
        return 1
    fi
}

# Function to start the server
start_server() {
    echo "Starting MCP server..."
    if [ -f "./final_mcp_server.pid" ]; then
        echo "PID file exists, checking if server is already running"
        SERVER_PID=$(cat ./final_mcp_server.pid)
        if ps -p $SERVER_PID > /dev/null; then
            echo "Server is already running with PID $SERVER_PID"
            return 0
        else
            echo "Server PID file exists but process is not running. Removing stale PID file."
            rm ./final_mcp_server.pid
        fi
    fi

    # Start server in the background
    python3 ./final_mcp_server.py --host 0.0.0.0 --port 9998 --debug > ./final_mcp_server.log 2>&1 &
    SERVER_PID=$!
    echo $SERVER_PID > ./final_mcp_server.pid
    echo "Started server with PID $SERVER_PID"
    
    # Wait for server to start
    echo "Waiting for server to start..."
    for i in {1..30}; do
        if curl -s http://localhost:9998/health > /dev/null; then
            echo "✅ Server started successfully"
            return 0
        fi
        echo "Attempt $i/30: Server not ready yet, waiting..."
        sleep 1
    done
    
    echo "❌ Failed to start server within 30 seconds"
    if [ -f "./final_mcp_server.log" ]; then
        echo "===== Server Log ====="
        tail -50 ./final_mcp_server.log
        echo "======================"
    fi
    return 1
}

# Function to stop the server
stop_server() {
    if [ -f "./final_mcp_server.pid" ]; then
        SERVER_PID=$(cat ./final_mcp_server.pid)
        echo "Stopping server with PID $SERVER_PID..."
        if ps -p $SERVER_PID > /dev/null; then
            kill $SERVER_PID
            echo "Sent SIGTERM to server"
            # Wait for server to stop
            for i in {1..10}; do
                if ! ps -p $SERVER_PID > /dev/null; then
                    echo "✅ Server stopped"
                    rm ./final_mcp_server.pid
                    return 0
                fi
                echo "Waiting for server to stop..."
                sleep 1
            done
            echo "Server did not stop gracefully, sending SIGKILL"
            kill -9 $SERVER_PID
            rm ./final_mcp_server.pid
        else
            echo "Server process not found"
            rm ./final_mcp_server.pid
        fi
    else
        echo "No PID file found, server is not running"
    fi
}

# Apply the parameter handling fixes
echo "===== Applying parameter handling fixes ====="
python3 ./fix_ipfs_parameter_handling.py

# Restart the server to apply the fixes
echo "===== Restarting the server ====="
if check_server; then
    stop_server
fi

# Start the server
start_server

# Wait a bit for the server to fully initialize
echo "Giving the server a moment to fully initialize..."
sleep 3

# Run the diagnostic tests
echo "===== Running diagnostic tests ====="
python3 ./diagnose_ipfs_tools.py

# Run the comprehensive MCP tests
echo "===== Running comprehensive MCP tests ====="
python3 ./enhanced_ipfs_mcp_test.py --basic-only

echo "===== Test run complete ====="

# Check final server status
echo "Final server status:"
curl -s http://localhost:9998/health | python3 -m json.tool

echo "===== Enhanced IPFS MCP Test Runner Completed ====="
