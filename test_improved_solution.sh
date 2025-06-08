#!/bin/bash
# Improved test script for final MCP solution

set -e  # Exit on error

# Define colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
PORT=9998
HOST="0.0.0.0"
LOG_FILE="test_mcp_server.log"
PID_FILE="test_mcp_server.pid"

# Logging function
log() {
    local level="$1"
    local message="$2"
    local color="$NC"
    
    case "$level" in
        "INFO") color="$BLUE";;
        "SUCCESS") color="$GREEN";;
        "ERROR") color="$RED";;
        "WARNING") color="$YELLOW";;
    esac
    
    echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message${NC}" | tee -a "$LOG_FILE"
}

# Clean up any existing processes
cleanup() {
    log "INFO" "Cleaning up..."
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE" 2>/dev/null || echo "")
        if [ -n "$PID" ] && ps -p "$PID" > /dev/null 2>&1; then
            log "INFO" "Stopping server with PID $PID"
            kill "$PID" 2>/dev/null || true
            sleep 2
            if ps -p "$PID" > /dev/null 2>&1; then
                log "WARNING" "Force killing server"
                kill -9 "$PID" 2>/dev/null || true
            fi
        fi
        rm -f "$PID_FILE"
    fi
    
    # Kill any remaining Python processes
    pkill -f "final_mcp_server" 2>/dev/null || true
    pkill -f "simple_mcp_server_test" 2>/dev/null || true
}

# Test basic Python functionality
test_python() {
    log "INFO" "Testing basic Python functionality..."
    
    # Test basic execution
    if python3 -c "print('Python test successful')" 2>&1 | tee -a "$LOG_FILE"; then
        log "SUCCESS" "Basic Python execution works"
    else
        log "ERROR" "Basic Python execution failed"
        return 1
    fi
    
    # Test import capabilities
    if python3 -c "import sys, os, json; print('Python imports successful')" 2>&1 | tee -a "$LOG_FILE"; then
        log "SUCCESS" "Basic Python imports work"
    else
        log "ERROR" "Basic Python imports failed"
        return 1
    fi
    
    return 0
}

# Test FastAPI/uvicorn availability
test_dependencies() {
    log "INFO" "Testing dependencies..."
    
    if python3 -c "import fastapi, uvicorn, jsonrpcserver; print('All dependencies available')" 2>&1 | tee -a "$LOG_FILE"; then
        log "SUCCESS" "All required dependencies are available"
        return 0
    else
        log "ERROR" "Some dependencies are missing"
        return 1
    fi
}

# Test unified_ipfs_tools import
test_unified_ipfs_tools() {
    log "INFO" "Testing unified_ipfs_tools import..."
    
    if timeout 10 python3 -c "import unified_ipfs_tools; print('unified_ipfs_tools imported successfully')" 2>&1 | tee -a "$LOG_FILE"; then
        log "SUCCESS" "unified_ipfs_tools imports successfully"
        return 0
    else
        log "ERROR" "unified_ipfs_tools import failed or timed out"
        return 1
    fi
}

# Start simple test server
start_test_server() {
    log "INFO" "Starting simple test server..."
    
    # Clear log file
    > "$LOG_FILE"
    
    # Start the simple server
    python3 simple_mcp_server_test.py --host "$HOST" --port "$PORT" --debug >> "$LOG_FILE" 2>&1 &
    SERVER_PID=$!
    echo "$SERVER_PID" > "$PID_FILE"
    
    log "INFO" "Test server started with PID: $SERVER_PID"
    
    # Wait for server to start
    for i in {1..30}; do
        if ! ps -p "$SERVER_PID" > /dev/null 2>&1; then
            log "ERROR" "Server process died. Check log file: $LOG_FILE"
            return 1
        fi
        
        # Check if server is responding
        if curl -s --max-time 2 http://localhost:$PORT/health > /dev/null 2>&1; then
            log "SUCCESS" "Test server is responding"
            return 0
        fi
        
        if [ $((i % 5)) -eq 0 ]; then
            log "INFO" "Waiting for server to start ($i/30 seconds)..."
        fi
        sleep 1
    done
    
    log "ERROR" "Server failed to start within 30 seconds"
    return 1
}

# Test server functionality
test_server() {
    log "INFO" "Testing server functionality..."
    
    # Test health endpoint
    if HEALTH_RESPONSE=$(curl -s --max-time 5 http://localhost:$PORT/health 2>/dev/null); then
        log "SUCCESS" "Health endpoint responded: $HEALTH_RESPONSE"
    else
        log "ERROR" "Health endpoint failed"
        return 1
    fi
    
    # Test JSON-RPC ping
    if PING_RESPONSE=$(curl -s --max-time 5 -X POST -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","method":"ping","params":{},"id":1}' \
        http://localhost:$PORT/jsonrpc 2>/dev/null); then
        log "SUCCESS" "JSON-RPC ping responded: $PING_RESPONSE"
    else
        log "ERROR" "JSON-RPC ping failed"
        return 1
    fi
    
    return 0
}

# Main test execution
main() {
    log "INFO" "Starting improved MCP server tests..."
    
    # Cleanup any existing processes
    cleanup
    
    # Run tests in sequence
    local tests=(
        "test_python"
        "test_dependencies" 
        "test_unified_ipfs_tools"
        "start_test_server"
        "test_server"
    )
    
    for test in "${tests[@]}"; do
        log "INFO" "Running $test..."
        if $test; then
            log "SUCCESS" "$test passed"
        else
            log "ERROR" "$test failed - stopping tests"
            cleanup
            exit 1
        fi
    done
    
    log "SUCCESS" "All tests passed!"
    cleanup
    exit 0
}

# Trap cleanup on exit
trap cleanup EXIT

# Run main function
main "$@"
