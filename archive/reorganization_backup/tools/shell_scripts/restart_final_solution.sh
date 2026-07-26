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
        if ps -p "$PID" > /dev/null; then
            log "WARNING" "Found running MCP server with PID $PID, stopping it"
            kill "$PID" 2>/dev/null || true
            sleep 2
            if ps -p "$PID" > /dev/null; then
                log "WARNING" "MCP server did not stop gracefully, force killing"
                kill -9 "$PID" 2>/dev/null || true
            fi
        fi
        rm -f "$PID_FILE"
    fi
    
    # Kill any other MCP server processes that might be running
    pkill -f "python.*final_mcp_server\.py" > /dev/null 2>&1 || true
    sleep 1
}

# Check if the port is already in use
check_port() {
    log "INFO" "Checking if port $PORT is available"
    if nc -z "$HOST" "$PORT" 2>/dev/null; then
        log "ERROR" "Port $PORT is already in use. Please use a different port or stop the existing server."
        return 1
    fi
    log "SUCCESS" "Port $PORT is available"
    return 0
}

# Start the MCP server
start_server() {
    log "INFO" "Starting MCP server on $HOST:$PORT"
    
    # Clear the log file
    > "$LOG_FILE"
    
    # Start the server with debug flag for better diagnostics
    echo "Starting server with command: python3 $MCP_SERVER --host $HOST --port $PORT --debug"
    python3 "$MCP_SERVER" --host "$HOST" --port "$PORT" --debug &
    SERVER_PID=$!
    
    # Save PID for later reference
    echo "$SERVER_PID" > "$PID_FILE"
    
    log "INFO" "MCP server started with PID $SERVER_PID"
    
    # Wait for the server to start up
    log "INFO" "Waiting for server to be ready (max $MAX_WAIT seconds)"
    for i in $(seq 1 $MAX_WAIT); do
        if curl -s "http://$HOST:$PORT/health" > /dev/null; then
            log "SUCCESS" "Server is up and responding to health checks after $i seconds"
            return 0
        fi
        sleep 1
    done
    
    log "ERROR" "Server failed to start within $MAX_WAIT seconds"
    return 1
}

# Wait for server to be healthy
wait_for_server_health() {
    local max_wait="$1"
    [ -z "$max_wait" ] && max_wait=30
    
    log "INFO" "Checking if server is healthy (max $max_wait seconds)"
    
    for i in $(seq 1 $max_wait); do
        response=$(curl -s "http://$HOST:$PORT/health" 2>/dev/null)
        if [ $? -eq 0 ] && [ -n "$response" ]; then
            log "SUCCESS" "Server is healthy after $i seconds"
            
            # Add an extra delay after the server is detected as healthy
            log "INFO" "Adding a 5-second delay to ensure full initialization."
            sleep 5

            # Verify if the server is fully operational by testing a simple jsonrpc call
            PING_RESULT=$(curl -s -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"ping","params":{},"id":123}' http://localhost:$PORT/jsonrpc)
            log "INFO" "Ping test result: $PING_RESULT"
            
            if [[ "$PING_RESULT" == *"pong"* ]]; then
                log "SUCCESS" "JSON-RPC endpoint is operational"
            else
                log "WARNING" "JSON-RPC endpoint may not be fully operational. Response: $PING_RESULT"
            fi

            return 0
        fi
        sleep 1
    done
    
    log "ERROR" "Server did not become healthy within $max_wait seconds"
    return 1
}

# Run the IPFS MCP tools test suite
run_ipfs_mcp_tests() {
    log "INFO" "Running IPFS MCP tools test suite"
    
    # First run a basic connectivity test
    log "INFO" "Running basic connectivity test"
    python3 -c "import requests; print(requests.get('http://$HOST:$PORT/health').text)"
    
    # Set up timestamp for test results
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    TEST_OUTPUT_FILE="$TEST_RESULTS_DIR/test_output_$TIMESTAMP.log"
    ERROR_SUMMARY_FILE="$TEST_RESULTS_DIR/error_summary_$TIMESTAMP.txt"
    
    # Run the comprehensive test suite
    log "INFO" "Running comprehensive test suite"
    python3 test_ipfs_mcp_tools.py --host "$HOST" --port "$PORT" --verbose 2>&1 | tee "$TEST_OUTPUT_FILE"
    TEST_EXIT_CODE=${PIPESTATUS[0]}
    
    # Generate error summary if tests failed
    if [ $TEST_EXIT_CODE -ne 0 ]; then
        log "ERROR" "Tests failed with exit code $TEST_EXIT_CODE"
        
        # Extract error information
        echo "=== TEST FAILURE SUMMARY ===" > "$ERROR_SUMMARY_FILE"
        echo "" >> "$ERROR_SUMMARY_FILE"
        
        # Extract errors from test output
        grep -A 2 "ERROR:" "$TEST_OUTPUT_FILE" >> "$ERROR_SUMMARY_FILE"
        grep -A 2 "FAIL:" "$TEST_OUTPUT_FILE" >> "$ERROR_SUMMARY_FILE"
        grep -A 2 "AssertionError" "$TEST_OUTPUT_FILE" >> "$ERROR_SUMMARY_FILE"
        grep -A 2 "Exception" "$TEST_OUTPUT_FILE" >> "$ERROR_SUMMARY_FILE"
        
        echo "" >> "$ERROR_SUMMARY_FILE"
        echo "=== TEST FAILURE DETAILS ===" >> "$ERROR_SUMMARY_FILE"
        echo "" >> "$ERROR_SUMMARY_FILE"
        
        # Extract the full traceback sections
        grep -A 20 "Traceback" "$TEST_OUTPUT_FILE" >> "$ERROR_SUMMARY_FILE"
        
        log "INFO" "Error summary saved to $ERROR_SUMMARY_FILE"
    else
        log "SUCCESS" "All tests passed!"
    fi
    
    return $TEST_EXIT_CODE
}

# Main function that orchestrates the entire process
main() {
    log "INFO" "Starting IPFS MCP test process"
    
    # Kill any existing servers
    kill_existing_servers
    
    # Check if port is available
    check_port || return 1
    
    # Start the server
    start_server || return 1
    
    # Wait for server to be healthy
    wait_for_server_health 30 || return 1
    
    # Run the tests
    run_ipfs_mcp_tests
    test_exit_code=$? # Capture test result

    # Stop the server after tests
    log "INFO" "Tests finished, stopping MCP server."
    kill_existing_servers

    # Return the test result
    return $test_exit_code
}

# Run the main function
main "$@"
exit $?
