#!/bin/bash
# Verification and Testing Script
# This script runs the final MCP server and verifies the IPFS integration fix

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
MCP_SERVER="final_mcp_server.py"
PORT=9998
HOST="0.0.0.0"
LOG_FILE="final_mcp_server.log"
PID_FILE="final_mcp_server.pid"
MAX_WAIT=60

# Function for logging messages
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
    
    echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message${NC}"
}

# Kill any existing MCP server processes
kill_existing_servers() {
    log "INFO" "Checking for existing MCP server processes"
    
    # Check for PID file
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null; then
            log "WARNING" "Found running MCP server with PID $PID, stopping it"
            kill "$PID" 2>/dev/null || true
            sleep 2
            if ps -p "$PID" > /dev/null; then
                log "WARNING" "Server didn't stop, forcing with SIGKILL"
                kill -9 "$PID" 2>/dev/null || true
            fi
        fi
        rm -f "$PID_FILE"
    fi
    
    # Check for any other Python processes running the server script
    OTHER_PIDS=$(pgrep -f "python.*$MCP_SERVER" || true)
    if [ -n "$OTHER_PIDS" ]; then
        log "WARNING" "Found other MCP server processes: $OTHER_PIDS"
        for PID in $OTHER_PIDS; do
            log "INFO" "Stopping process $PID"
            kill "$PID" 2>/dev/null || true
            sleep 1
            if ps -p "$PID" > /dev/null; then
                log "WARNING" "Process $PID didn't stop, forcing with SIGKILL"
                kill -9 "$PID" 2>/dev/null || true
            fi
        done
    fi
}

# Start the MCP server
start_server() {
    log "INFO" "Starting MCP server at $HOST:$PORT"
    python3 "$MCP_SERVER" --host "$HOST" --port "$PORT" > "$LOG_FILE" 2>&1 &
    SERVER_PID=$!
    echo "$SERVER_PID" > "$PID_FILE"
    log "INFO" "MCP server started with PID $SERVER_PID"
    
    # Wait for server to be ready
    log "INFO" "Waiting for server to be ready (max $MAX_WAIT seconds)"
    start_time=$(date +%s)
    while true; do
        # Check if process is still running
        if ! ps -p "$SERVER_PID" > /dev/null; then
            log "ERROR" "Server process died unexpectedly"
            cat "$LOG_FILE"
            return 1
        fi
        
        # Check if server is responding
        if curl -s "http://$HOST:$PORT/health" > /dev/null; then
            log "SUCCESS" "Server is ready"
            break
        fi
        
        # Check timeout
        current_time=$(date +%s)
        elapsed=$((current_time - start_time))
        if [ $elapsed -ge $MAX_WAIT ]; then
            log "ERROR" "Timeout waiting for server to be ready"
            kill "$SERVER_PID" 2>/dev/null || true
            cat "$LOG_FILE"
            return 1
        fi
        
        # Wait and retry
        sleep 1
    done
    
    return 0
}

# Run verification script
run_verification() {
    log "INFO" "Running verification script"
    python3 verify_ipfs_fix.py
    
    if [ $? -eq 0 ]; then
        log "SUCCESS" "Verification completed successfully"
        return 0
    else
        log "ERROR" "Verification failed"
        return 1
    fi
}

# Run comprehensive test suite if available
run_comprehensive_tests() {
    if [ -f "test_ipfs_mcp_tools.py" ]; then
        log "INFO" "Running comprehensive test suite"
        python3 test_ipfs_mcp_tools.py
        
        if [ $? -eq 0 ]; then
            log "SUCCESS" "Comprehensive tests completed successfully"
            return 0
        else
            log "ERROR" "Comprehensive tests failed"
            return 1
        fi
    else
        log "INFO" "Comprehensive test suite not found, skipping"
        return 0
    fi
}

# Clean up and exit
cleanup() {
    log "INFO" "Cleaning up"
    kill_existing_servers
    log "INFO" "Done"
}

# Main execution
main() {
    log "INFO" "Starting verification process"
    
    # Clean up any existing servers
    kill_existing_servers
    
    # Start the MCP server
    start_server
    if [ $? -ne 0 ]; then
        log "ERROR" "Failed to start MCP server"
        return 1
    fi
    
    # Run verification
    run_verification
    VERIFY_RESULT=$?
    
    # Run comprehensive tests
    run_comprehensive_tests
    TEST_RESULT=$?
    
    # Clean up
    cleanup
    
    # Report results
    if [ $VERIFY_RESULT -eq 0 ] && [ $TEST_RESULT -eq 0 ]; then
        log "SUCCESS" "All tests passed! The IPFS MCP integration is working correctly."
        return 0
    else
        log "ERROR" "Some tests failed. See logs for details."
        return 1
    fi
}

# Run main function
main
exit $?
