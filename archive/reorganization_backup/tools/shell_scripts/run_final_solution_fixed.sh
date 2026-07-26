#!/bin/bash
# Run Final MCP Solution
# This script runs the final MCP server and tests the solution

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
MCP_SERVER="final_mcp_server.py"
PORT=9998  # Updated to match the port defined in final_mcp_server.py
HOST="0.0.0.0"
LOG_FILE="final_mcp_server.log"
PID_FILE="final_mcp_server.pid"
MAX_WAIT=60
TEST_RESULTS_DIR="test_results"

# Create test results directory if it doesn't exist
mkdir -p "$TEST_RESULTS_DIR"

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
        if ps -p "$PID" > /dev/null 2>&1; then
            log "WARNING" "Found running MCP server with PID $PID, stopping it"
            kill "$PID" 2>/dev/null || true
            sleep 2
            if ps -p "$PID" > /dev/null 2>&1; then
                log "WARNING" "MCP server did not stop gracefully, force killing"
                kill -9 "$PID" 2>/dev/null || true
            fi
        fi
        rm -f "$PID_FILE"
    fi
    
    # Look for any processes that might be the MCP server
    for PID in $(ps aux | grep -E "python.*$MCP_SERVER" | grep -v grep | awk '{print $2}'); do
        log "WARNING" "Found orphaned MCP server process with PID $PID, stopping it"
        kill "$PID" 2>/dev/null || true
        sleep 2
        if ps -p "$PID" > /dev/null 2>&1; then
            log "WARNING" "Process did not stop gracefully, force killing"
            kill -9 "$PID" 2>/dev/null || true
        fi
    done
}

# Check if port is available
check_port() {
    log "INFO" "Checking if port $PORT is available"
    if netstat -tuln | grep ":$PORT " > /dev/null 2>&1; then
        log "ERROR" "Port $PORT is already in use"
        return 1
    else
        log "SUCCESS" "Port $PORT is available"
        return 0
    fi
}

# Start the MCP server
start_server() {
    log "INFO" "Starting MCP server on $HOST:$PORT"
    
    # Clear the log file
    > "$LOG_FILE"
    
    # Start the server in the background with improved parameters
    python3 "$MCP_SERVER" --host "$HOST" --port "$PORT" --debug > "$LOG_FILE" 2>&1 &
    SERVER_PID=$!
    echo "$SERVER_PID" > "$PID_FILE"
    log "INFO" "MCP server started with PID: $SERVER_PID"
    
    # Wait for the server to start
    log "INFO" "Waiting for server to initialize"
    
    for ((i=1; i<=$MAX_WAIT; i++)); do
        sleep 1
        if ! ps -p "$SERVER_PID" > /dev/null 2>&1; then
            log "ERROR" "Server process died unexpectedly. Check $LOG_FILE for details."
            log "ERROR" "Last 20 lines from the log file:"
            tail -n 20 "$LOG_FILE"
            return 1
        fi
        
        # Check if server is accepting connections
        STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/health" 2>/dev/null || echo "000")
        if [ "$STATUS_CODE" = "200" ]; then
            log "SUCCESS" "Server is up and responding to health checks"
            HEALTH_JSON=$(curl -s "http://localhost:$PORT/health" 2>/dev/null)
            log "INFO" "Health endpoint response: $HEALTH_JSON"
            break
        else
            if (( i % 5 == 0 )); then
                log "INFO" "Health check status code: $STATUS_CODE (waiting for 200)"
            fi
        fi

        # Show progress
        if (( i % 5 == 0 )); then
            log "INFO" "Still waiting for server to start ($i/$MAX_WAIT seconds)"
            log "INFO" "Recent log entries:"
            tail -n 10 "$LOG_FILE"
        fi

        if [ $i -eq $MAX_WAIT ]; then
            log "ERROR" "Server failed to start within $MAX_WAIT seconds. Check $LOG_FILE for details."
            log "ERROR" "Last 20 lines from the log file:"
            tail -n 20 "$LOG_FILE"
            kill "$SERVER_PID" 2>/dev/null || true
            sleep 2
            if ps -p "$SERVER_PID" > /dev/null 2>&1; then
                log "WARNING" "Process did not stop gracefully, force killing"
                kill -9 "$SERVER_PID" 2>/dev/null || true
            fi
            return 1
        fi
    done

    # Add an extra delay after the server is detected as healthy
    log "INFO" "Adding a 5-second delay to ensure full initialization."
    sleep 5

    # Verify if the server is fully operational by testing a simple jsonrpc call
    PING_RESULT=$(curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"ping","params":{},"id":123}' "http://localhost:$PORT/jsonrpc" 2>/dev/null || echo '{"error":"Connection failed"}')
    log "INFO" "Ping test result: $PING_RESULT"
    
    if [[ "$PING_RESULT" == *"pong"* ]]; then
        log "SUCCESS" "JSON-RPC endpoint is operational"
    else
        log "WARNING" "JSON-RPC endpoint may not be fully operational. Response: $PING_RESULT"
    fi

    return 0
}

# Function to run the IPFS MCP tools test suite
run_ipfs_mcp_tests() {
    log "INFO" "Running IPFS MCP tools test suite"
    
    # First run a basic connectivity test
    log "INFO" "Running basic connectivity test"
    HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/health" 2>/dev/null || echo "000")
    log "INFO" "Health check status: $HEALTH_STATUS"
    
    if [ "$HEALTH_STATUS" != "200" ]; then
        log "ERROR" "Health check failed with status $HEALTH_STATUS"
        return 1
    fi
    
    HEALTH_RESPONSE=$(curl -s "http://localhost:$PORT/health" 2>/dev/null)
    log "INFO" "Health response: $HEALTH_RESPONSE"
    
    # Test JSON-RPC endpoint with ping
    PING_STATUS=$(curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"ping","params":{},"id":123}' -o /dev/null -w "%{http_code}" "http://localhost:$PORT/jsonrpc" 2>/dev/null || echo "000")
    log "INFO" "Ping status: $PING_STATUS"
    
    if [ "$PING_STATUS" != "200" ]; then
        log "ERROR" "JSON-RPC ping failed with status $PING_STATUS"
        return 1
    fi
    
    PING_RESPONSE=$(curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"ping","params":{},"id":123}' "http://localhost:$PORT/jsonrpc" 2>/dev/null)
    log "INFO" "Ping response: $PING_RESPONSE"
    
    # Run the diagnostics first
    log "INFO" "Running IPFS tool diagnostics"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    DIAG_LOG="$TEST_RESULTS_DIR/ipfs_diagnostic_$TIMESTAMP.log"
    
    python3 diagnose_ipfs_tools.py 2>&1 | tee "$DIAG_LOG"
    log "INFO" "Diagnostic results saved to $DIAG_LOG"
    
    # Run the enhanced test suite
    log "INFO" "Running enhanced test suite"
    TEST_LOG="$TEST_RESULTS_DIR/ipfs_mcp_test_$TIMESTAMP.log"
    
    # Check if we have an enhanced test script
    if [ -f "enhanced_ipfs_mcp_test.py" ]; then
        log "INFO" "Using enhanced test script"
        TEST_SCRIPT="enhanced_ipfs_mcp_test.py"
    else
        log "INFO" "Using standard test script"
        TEST_SCRIPT="test_ipfs_mcp_tools.py"
    fi
    
    # Run the test with detailed output
    if python3 "$TEST_SCRIPT" 2>&1 | tee "$TEST_LOG"; then
        log "SUCCESS" "IPFS MCP tools test suite completed successfully"
        return 0
    else
        log "ERROR" "IPFS MCP tools test suite found issues"
        log "INFO" "Check $TEST_LOG for detailed report"
        return 1
    fi
}

# Main function
main() {
    log "INFO" "Starting MCP server solution"
    
    # Kill any existing servers
    kill_existing_servers
    
    # Check if port is available
    if ! check_port; then
        log "ERROR" "Cannot start server due to port conflict"
        return 1
    fi
    
    # Start server
    if ! start_server; then
        log "ERROR" "Failed to start MCP server"
        return 1
    fi
    
    # Run the test suite
    if ! run_ipfs_mcp_tests; then
        log "WARNING" "Test suite reported issues. Check the logs for details."
    fi
    
    # Clean up
    log "INFO" "Tests finished, stopping MCP server."
    kill_existing_servers
    
    return 0
}

# Run the main function
main
exit $?
