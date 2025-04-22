#!/bin/bash
#
# MCP Server Stop Script
# This script stops the MCP server gracefully
#

# Default values
PID_FILE="/tmp/mcp_server.pid"
FORCE="false"

# Function to show usage
show_usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  --force          Force kill the server instead of graceful shutdown"
    echo "  --help           Show this help message"
    exit 1
}

# Parse command line options
for arg in "$@"; do
    case $arg in
        --force)
            FORCE="true"
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

# Check if PID file exists
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null; then
        echo "Found running MCP server with PID $PID"
        if [ "$FORCE" = "true" ]; then
            echo "Force killing MCP server..."
            kill -9 "$PID" 2>/dev/null
        else
            echo "Stopping MCP server gracefully..."
            kill "$PID" 2>/dev/null
            
            # Wait for server to stop
            MAX_WAIT=10
            for i in $(seq 1 $MAX_WAIT); do
                if ! ps -p "$PID" > /dev/null; then
                    break
                fi
                echo "Waiting for server to shut down... ($i/$MAX_WAIT)"
                sleep 1
            done
            
            # Check if it's still running and force kill if necessary
            if ps -p "$PID" > /dev/null; then
                echo "Server didn't shut down gracefully. Force killing..."
                kill -9 "$PID" 2>/dev/null
            fi
        fi
        
        # Wait for final confirmation
        sleep 1
        if ! ps -p "$PID" > /dev/null; then
            echo "MCP server has been stopped"
        else
            echo "Failed to stop MCP server"
            exit 1
        fi
    else
        echo "No running MCP server found with PID $PID"
    fi
    rm -f "$PID_FILE"
else
    echo "No PID file found at $PID_FILE"
    echo "Checking for running MCP server processes..."
    
    # Try to find running processes that match the server pattern
    PIDS=$(pgrep -f "python.*run_mcp_server.py" 2>/dev/null)
    if [ -n "$PIDS" ]; then
        echo "Found running MCP server processes: $PIDS"
        if [ "$FORCE" = "true" ]; then
            echo "Force killing all MCP server processes..."
            pkill -9 -f "python.*run_mcp_server.py" 2>/dev/null
        else
            echo "Stopping all MCP server processes gracefully..."
            pkill -f "python.*run_mcp_server.py" 2>/dev/null
            
            # Wait for processes to stop
            MAX_WAIT=10
            for i in $(seq 1 $MAX_WAIT); do
                if ! pgrep -f "python.*run_mcp_server.py" > /dev/null; then
                    break
                fi
                echo "Waiting for servers to shut down... ($i/$MAX_WAIT)"
                sleep 1
            done
            
            # Check if any are still running and force kill if necessary
            if pgrep -f "python.*run_mcp_server.py" > /dev/null; then
                echo "Some servers didn't shut down gracefully. Force killing..."
                pkill -9 -f "python.*run_mcp_server.py" 2>/dev/null
            fi
        fi
        
        # Wait for final confirmation
        sleep 1
        if ! pgrep -f "python.*run_mcp_server.py" > /dev/null; then
            echo "All MCP server processes have been stopped"
        else
            echo "Failed to stop some MCP server processes"
            exit 1
        fi
    else
        echo "No running MCP server processes found"
    fi
fi

# Check for any other mcp server processes
if pgrep -f "uvicorn.*run_mcp_server.*:app" > /dev/null; then
    echo "Found additional uvicorn processes for MCP server"
    if [ "$FORCE" = "true" ]; then
        echo "Force killing uvicorn processes..."
        pkill -9 -f "uvicorn.*run_mcp_server.*:app" 2>/dev/null
    else
        echo "Stopping uvicorn processes gracefully..."
        pkill -f "uvicorn.*run_mcp_server.*:app" 2>/dev/null
        
        # Wait for final confirmation
        sleep 2
        if pgrep -f "uvicorn.*run_mcp_server.*:app" > /dev/null; then
            echo "Some uvicorn processes didn't shut down gracefully. Force killing..."
            pkill -9 -f "uvicorn.*run_mcp_server.*:app" 2>/dev/null
        else
            echo "All uvicorn processes have been stopped"
        fi
    fi
fi

echo "MCP server shutdown complete"
