#!/usr/bin/env bash
# Enhanced MCP Server Restart Script
# This script provides a more robust way to restart the MCP server with 
# additional diagnostic information and error recovery options

# Define colors for output
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
BOLD="\033[1m"
NC="\033[0m" # No Color

# Configuration
MCP_SERVER="final_mcp_server.py"
PORT=9998  # Updated to match PORT defined in final_mcp_server.py
HOST="0.0.0.0"
LOG_FILE="enhanced_mcp_server.log"
PID_FILE="enhanced_mcp_server.pid" 
DEBUG_MODE="--debug"
MAX_RETRY=3
WAIT_TIME=30

# Print with color
print_color() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Log message with timestamp
log() {
    local level=$1
    local message=$2
    local color=$NC
    
    case "$level" in
        "INFO") color=$BLUE ;;
        "SUCCESS") color=$GREEN ;;
        "ERROR") color=$RED ;;
        "WARNING") color=$YELLOW ;;
    esac
    
    echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] [${level}] ${message}${NC}"
}

# Function to check dependencies
check_dependencies() {
    log "INFO" "Checking Python dependencies..."
    
    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        log "ERROR" "Python 3 is not available. Please install it."
        return 1
    fi
    
    # Check essential packages
    python3 -c "
import sys
missing = []
for pkg in ['fastapi', 'uvicorn', 'requests']:
    try:
        __import__(pkg)
    except ImportError:
        missing.append(pkg)
if missing:
    print(f'Missing packages: {missing}')
    sys.exit(1)
"
    
    if [ $? -ne 0 ]; then
        log "WARNING" "Missing essential packages. Would you like to install them? (y/n)"
        read -r answer
        if [[ $answer == "y" ]]; then
            python3 -m pip install fastapi uvicorn requests
        else
            log "ERROR" "Required packages are missing. Cannot continue."
            return 1
        fi
    fi
    
    log "SUCCESS" "All essential dependencies are satisfied"
    return 0
}

# Function to stop any running MCP server
stop_server() {
    log "INFO" "Stopping any running MCP server processes..."
    
    # Check if PID file exists
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null; then
            log "INFO" "Stopping MCP server with PID $pid"
            kill "$pid" 2>/dev/null
            
            # Wait for process to terminate
            local count=0
            while ps -p "$pid" > /dev/null && [ $count -lt 5 ]; do
                sleep 1
                count=$((count + 1))
            done
            
            # Force kill if still running
            if ps -p "$pid" > /dev/null; then
                log "WARNING" "MCP server did not stop gracefully, force killing"
                kill -9 "$pid" 2>/dev/null
            else
                log "SUCCESS" "MCP server stopped successfully"
            fi
        else
            log "WARNING" "No running MCP server found with PID $pid"
        fi
    else
        log "INFO" "No PID file found for MCP server"
    fi
    
    # Kill any other MCP server processes
    pkill -f "python3.*$MCP_SERVER" > /dev/null 2>&1 || true
    rm -f "$PID_FILE" > /dev/null 2>&1 || true
    
    # Give processes time to fully terminate
    sleep 2
}

# Function to check if port is available
check_port() {
    log "INFO" "Checking if port $PORT is available..."
    
    if command -v nc &> /dev/null; then
        if nc -z localhost "$PORT" 2>/dev/null; then
            log "ERROR" "Port $PORT is already in use"
            return 1
        fi
    elif command -v lsof &> /dev/null; then
        if lsof -i:"$PORT" > /dev/null 2>&1; then
            log "ERROR" "Port $PORT is already in use"
            return 1
        fi
    else
        log "WARNING" "Neither nc nor lsof available, skipping port check"
    fi
    
    log "SUCCESS" "Port $PORT is available"
    return 0
}

# Function to check server health
check_server_health() {
    log "INFO" "Checking server health..."
    
    local retry=0
    while [ $retry -lt 5 ]; do
        if curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
            local health
            health=$(curl -s "http://localhost:$PORT/health")
            log "SUCCESS" "Server is healthy"
            log "INFO" "Health information: $health"
            return 0
        fi
        log "INFO" "Waiting for server to become available... ($(($retry + 1))/5)"
        sleep 2
        retry=$((retry + 1))
    done
    
    log "ERROR" "Server health check failed"
    return 1
}

# Function to start the MCP server
start_server() {
    log "INFO" "Starting MCP server on $HOST:$PORT..."
    
    # Create a clean log file
    > "$LOG_FILE"
    
    # Start the server
    python3 "$MCP_SERVER" --host "$HOST" --port "$PORT" $DEBUG_MODE > "$LOG_FILE" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"
    
    log "INFO" "MCP server started with PID $pid"
    
    # Wait for server to initialize
    log "INFO" "Waiting for server to initialize..."
    local count=0
    while [ $count -lt $WAIT_TIME ]; do
        sleep 1
        
        # Check if process is still running
        if ! ps -p "$pid" > /dev/null; then
            log "ERROR" "Server process died during startup. Check $LOG_FILE for details."
            tail -n 20 "$LOG_FILE"
            return 1
        fi
        
        # Check if server is responding to health checks
        if curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
            log "SUCCESS" "Server initialized successfully"
            return 0
        fi
        
        count=$((count + 1))
        
        # Show progress every 5 seconds
        if ((count % 5 == 0)); then
            log "INFO" "Still waiting for server to initialize... ($count/$WAIT_TIME seconds)"
            tail -n 5 "$LOG_FILE"
        fi
    done
    
    log "ERROR" "Server failed to initialize within $WAIT_TIME seconds"
    tail -n 20 "$LOG_FILE"
    return 1
}

# Function to display server status
show_status() {
    log "INFO" "Checking MCP server status..."
    
    # Check if PID file exists
    if [ ! -f "$PID_FILE" ]; then
        log "ERROR" "No PID file found, server may not be running"
        return 1
    fi
    
    local pid
    pid=$(cat "$PID_FILE")
    
    # Check if process is running
    if ! ps -p "$pid" > /dev/null; then
        log "ERROR" "Process with PID $pid not found, server may have crashed"
        return 1
    fi
    
    # Check if server is responding to health requests
    if ! curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
        log "ERROR" "Server is running but not responding to health requests"
        return 1
    fi
    
    # Display health info
    local health
    health=$(curl -s "http://localhost:$PORT/health")
    
    log "SUCCESS" "MCP server is running and healthy"
    log "INFO" "PID: $pid"
    log "INFO" "Health: $health"
    log "INFO" "Log file: $LOG_FILE"
    
    return 0
}

# Function to test the server's functionality
test_server() {
    log "INFO" "Running basic server functionality tests..."
    
    # Test health endpoint
    local health_response
    health_response=$(curl -s "http://localhost:$PORT/health")
    if [ $? -ne 0 ] || [ -z "$health_response" ]; then
        log "ERROR" "Health endpoint test failed"
        return 1
    fi
    log "SUCCESS" "Health endpoint test passed"
    
    # Test JSON-RPC ping
    local ping_response
    ping_response=$(curl -s -X POST "http://localhost:$PORT/jsonrpc" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc": "2.0", "method": "ping", "id": 1}')
    
    if [ $? -ne 0 ] || [ -z "$ping_response" ] || ! echo "$ping_response" | grep -q "pong"; then
        log "ERROR" "JSON-RPC ping test failed"
        log "ERROR" "Response: $ping_response"
        return 1
    fi
    log "SUCCESS" "JSON-RPC ping test passed"
    
    # Test get_tools method
    local tools_response
    tools_response=$(curl -s -X POST "http://localhost:$PORT/jsonrpc" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc": "2.0", "method": "get_tools", "id": 2}')
    
    if [ $? -ne 0 ] || [ -z "$tools_response" ] || ! echo "$tools_response" | grep -q "tools"; then
        log "ERROR" "get_tools test failed"
        log "ERROR" "Response: $tools_response"
        return 1
    fi
    log "SUCCESS" "get_tools test passed"
    
    log "SUCCESS" "All basic tests passed"
    return 0
}

# Function to fix common issues
fix_common_issues() {
    log "INFO" "Checking for common issues..."
    
    # Fix permissions
    if [ ! -x "$MCP_SERVER" ]; then
        log "WARNING" "MCP server script is not executable"
        chmod +x "$MCP_SERVER"
        log "INFO" "Made $MCP_SERVER executable"
    fi
    
    # Check for log file size
    if [ -f "$LOG_FILE" ] && [ "$(stat -c %s "$LOG_FILE" 2>/dev/null || echo 0)" -gt 10485760 ]; then
        log "WARNING" "Log file is very large (>10MB), rotating"
        mv "$LOG_FILE" "${LOG_FILE}.old"
        log "INFO" "Rotated log file"
    fi
    
    return 0
}

# Main function
main() {
    log "INFO" "=== Enhanced MCP Server Restart ==="
    
    # Parse command-line arguments
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
            --no-debug)
                DEBUG_MODE=""
                shift
                ;;
            --status)
                show_status
                exit $?
                ;;
            --fix)
                fix_common_issues
                exit $?
                ;;
            --test)
                check_server_health && test_server
                exit $?
                ;;
            --stop)
                stop_server
                exit $?
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --port PORT      Set server port (default: 9997)"
                echo "  --host HOST      Set server host (default: 0.0.0.0)"
                echo "  --no-debug       Disable debug mode"
                echo "  --status         Show server status"
                echo "  --fix            Fix common issues"
                echo "  --test           Test server functionality"
                echo "  --stop           Stop the server without restarting"
                echo "  --help           Show this help message"
                exit 0
                ;;
            *)
                log "ERROR" "Unknown option: $1"
                echo "Use --help to see available options"
                exit 1
                ;;
        esac
    done
    
    # Check dependencies
    check_dependencies || exit 1
    
    # Fix common issues
    fix_common_issues
    
    # Stop any running instances
    stop_server
    
    # Check if port is available
    check_port || exit 1
    
    # Start the server
    for ((i=1; i<=MAX_RETRY; i++)); do
        log "INFO" "Starting server (attempt $i/$MAX_RETRY)..."
        if start_server; then
            break
        else
            if [ $i -eq $MAX_RETRY ]; then
                log "ERROR" "Failed to start server after $MAX_RETRY attempts"
                exit 1
            fi
            log "WARNING" "Retrying in 5 seconds..."
            sleep 5
        fi
    done
    
    # Check server health
    check_server_health || exit 1
    
    # Test server functionality
    test_server
    
    log "SUCCESS" "MCP server restarted successfully"
    return 0
}

# Run the main function
main "$@"