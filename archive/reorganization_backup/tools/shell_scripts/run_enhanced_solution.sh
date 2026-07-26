#!/bin/bash
# Enhanced Run Final MCP Solution Script
# This script combines the original run_final_solution.sh with improved diagnostics and tests

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
ENHANCED_RUNNER="run_enhanced_mcp_server.py"
MCP_SERVER="final_mcp_server.py"
PORT=9998
HOST="0.0.0.0"
LOG_FILE="enhanced_mcp_server.log"
PID_FILE="enhanced_mcp_server.pid"
MAX_WAIT=60
TEST_RESULTS_DIR="test_results"
DIAGNOSTICS_TOOL="enhanced_diagnostics.py"
PARAM_HANDLER="fixed_ipfs_param_handling.py"

# Make sure test results directory exists
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

# Parse command line arguments
start_only=false
test_only=false
verbose=false
skip_tests=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --start-only)
            start_only=true
            shift
            ;;
        --test-only)
            test_only=true
            shift
            ;;
        --verbose|-v)
            verbose=true
            shift
            ;;
        --skip-tests)
            skip_tests=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --start-only     Start the MCP server without running tests"
            echo "  --test-only      Run tests against an existing MCP server"
            echo "  --verbose, -v    Enable verbose output"
            echo "  --skip-tests     Skip running tests after starting server"
            echo "  --help, -h       Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help to see available options"
            exit 1
            ;;
    esac
done

# Check if our check_server.py script exists
if [ -f "check_server.py" ]; then
    log "INFO" "Using check_server.py for server management"
    USE_CHECK_SCRIPT=true
else
    log "WARNING" "check_server.py not found, falling back to built-in methods"
    USE_CHECK_SCRIPT=false
fi

# Check if enhanced test scripts exist
if [ -f "enhanced_ipfs_mcp_test.py" ]; then
    log "INFO" "Using enhanced test scripts"
    USE_ENHANCED_TESTS=true
else
    log "WARNING" "Enhanced test scripts not found, falling back to original tests"
    USE_ENHANCED_TESTS=false
fi

# Start the MCP server using check_server.py if available
start_mcp_server() {
    log "INFO" "Starting MCP server on $HOST:$PORT"
    
    if [ "$USE_CHECK_SCRIPT" = true ]; then
        log "INFO" "Starting server with check_server.py"
        python3 check_server.py --start --port $PORT
        if [ $? -ne 0 ]; then
            log "ERROR" "Failed to start MCP server"
            return 1
        fi
        return 0
    else
        # Use enhanced server runner with parameter handling fixes
        log "INFO" "Starting server with enhanced runner and parameter handling fixes"
        
        # Clear the log file
        > "$LOG_FILE"
        
        # Start the enhanced server in the background
        python3 "$ENHANCED_RUNNER" --module final_mcp_server --host "$HOST" --port "$PORT" --debug > "$LOG_FILE" 2>&1 &
        SERVER_PID=$!
        echo "$SERVER_PID" > "$PID_FILE"
        log "INFO" "Enhanced MCP server started with PID: $SERVER_PID"
        
        # Wait for the server to start
        log "INFO" "Waiting for server to initialize"
        
        for ((i=1; i<=$MAX_WAIT; i++)); do
            sleep 1
            if ! ps -p "$SERVER_PID" > /dev/null; then
                log "ERROR" "Server process died unexpectedly. Check $LOG_FILE for details."
                tail -n 20 "$LOG_FILE"
                return 1
            fi
            
            # Check if server is accepting connections
            if curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT/health 2>/dev/null | grep -q 200; then
                log "SUCCESS" "Server is up and responding to health checks"
                break
            fi
            
            # Show progress
            if (( i % 5 == 0 )); then
                log "INFO" "Still waiting for server to start ($i/$MAX_WAIT seconds)"
                tail -n 5 "$LOG_FILE"
            fi
            
            if [ $i -eq $MAX_WAIT ]; then
                log "ERROR" "Server failed to start within $MAX_WAIT seconds. Check $LOG_FILE for details."
                tail -n 20 "$LOG_FILE"
                kill "$SERVER_PID" 2>/dev/null || true
                return 1
            fi
        done
        
        return 0
    fi
}

# Run tests using enhanced test scripts if available
run_tests() {
    log "INFO" "Running tests against MCP server on port $PORT"
    
    if [ "$USE_ENHANCED_TESTS" = true ]; then
        # Use enhanced tests
        log "INFO" "Running enhanced tests"
        TEST_LOG="$TEST_RESULTS_DIR/enhanced_ipfs_mcp_test_$(date +%Y%m%d_%H%M%S).log"
        
        python3 enhanced_ipfs_mcp_test.py --verbose --port $PORT > "$TEST_LOG" 2>&1
        local test_result=$?
        
        if [ $test_result -eq 0 ]; then
            log "SUCCESS" "Enhanced tests passed successfully"
            return 0
        else
            log "ERROR" "Enhanced tests failed with exit code $test_result"
            log "INFO" "Test log: $TEST_LOG"
            tail -n 20 "$TEST_LOG"
            return 1
        fi
    else
        # Use enhanced tests and diagnostics
        log "INFO" "Running enhanced tests and diagnostics"
        TEST_LOG="$TEST_RESULTS_DIR/ipfs_mcp_test_$(date +%Y%m%d_%H%M%S).log"
        DIAG_LOG="$TEST_RESULTS_DIR/ipfs_mcp_diag_$(date +%Y%m%d_%H%M%S).log"
        
        # First run our enhanced diagnostics
        log "INFO" "Running enhanced diagnostics..."
        python3 "$DIAGNOSTICS_TOOL" > "$DIAG_LOG" 2>&1
        local diag_result=$?
        
        if [ $diag_result -eq 0 ]; then
            log "SUCCESS" "Enhanced diagnostics passed successfully"
        else
            log "WARNING" "Enhanced diagnostics found issues, check $DIAG_LOG for details"
            # Still continue with tests
        fi
        
        # Now run the comprehensive IPFS tools tests
        log "INFO" "Running comprehensive IPFS tools tests..."
        python3 mcp_test_suite.py --host localhost --port $PORT > "$TEST_LOG" 2>&1
        local test_result=$?
        
        # Also run the original tests for backwards compatibility
        log "INFO" "Running original tests for backwards compatibility..."
        python3 test_ipfs_mcp_tools.py --host localhost --port $PORT >> "$TEST_LOG" 2>&1
        local orig_test_result=$?
        
        if [ $test_result -eq 0 ] && [ $orig_test_result -eq 0 ]; then
            log "SUCCESS" "All tests passed successfully"
            return 0
        else
            log "ERROR" "Tests failed: enhanced=$test_result, original=$orig_test_result"
            log "INFO" "Test log: $TEST_LOG"
            tail -n 20 "$TEST_LOG"
            return 1
        fi
    fi
}

# Check server health using check_server.py if available
check_server_health() {
    log "INFO" "Checking server health"
    
    if [ "$USE_CHECK_SCRIPT" = true ]; then
        # Use check_server.py
        python3 check_server.py --info
        if [ $? -ne 0 ]; then
            log "ERROR" "Server health check failed"
            return 1
        fi
        return 0
    else
        # Use curl directly
        local response=$(curl -s http://localhost:$PORT/health 2>/dev/null)
        if [ $? -ne 0 ] || [ -z "$response" ]; then
            log "ERROR" "Server health check failed: could not connect to server"
            return 1
        fi
        
        log "SUCCESS" "Server health check passed: $response"
        return 0
    fi
}

# Check if enhanced components are available
check_enhanced_components() {
    log "INFO" "Checking for enhanced components..."
    
    # Check for enhanced runner
    if [ -f "$ENHANCED_RUNNER" ]; then
        log "SUCCESS" "Enhanced runner found: $ENHANCED_RUNNER"
    else
        log "ERROR" "Enhanced runner not found: $ENHANCED_RUNNER"
        return 1
    fi
    
    # Check for parameter handler
    if [ -f "$PARAM_HANDLER" ]; then
        log "SUCCESS" "Parameter handler found: $PARAM_HANDLER"
    else
        log "ERROR" "Parameter handler not found: $PARAM_HANDLER"
        return 1
    fi
    
    # Check for diagnostics tool
    if [ -f "$DIAGNOSTICS_TOOL" ]; then
        log "SUCCESS" "Diagnostics tool found: $DIAGNOSTICS_TOOL"
    else
        log "ERROR" "Diagnostics tool not found: $DIAGNOSTICS_TOOL"
        return 1
    fi
    
    return 0
}

# Main function
main() {
    # Display header
    echo -e "${BOLD}Enhanced MCP Server Run Script${NC}"
    echo "Starting at $(date)"
    echo
    
    # Verify that enhanced components are available
    if ! check_enhanced_components; then
        log "ERROR" "Required enhanced components are missing"
        return 1
    fi
    
    # Handle --test-only option
    if [ "$test_only" = "true" ]; then
        log "INFO" "Running tests against existing MCP server"
        
        # Check server health before running tests
        if ! check_server_health; then
            log "ERROR" "No MCP server running on port $PORT"
            return 1
        fi
        
        # Run tests
        run_tests
        log "SUCCESS" "Tests completed"
        return $?
    fi
    
    # Handle --start-only option
    if [ "$start_only" = "true" ]; then
        log "INFO" "Starting MCP server only (no tests)"
        
        # Start server
        if ! start_mcp_server; then
            return 1
        fi
        
        # Final verification
        check_server_health
        return $?
    fi
    
    # Normal execution (start server and run tests)
    log "INFO" "Starting MCP server and running tests"
    
    # Start server
    if ! start_mcp_server; then
        return 1
    fi
    
    # Verify server is running
    if ! check_server_health; then
        log "ERROR" "Server health check failed after startup"
        return 1
    fi
    
    # Run tests if not skipped
    if [ "$skip_tests" = "true" ]; then
        log "INFO" "Tests skipped as requested"
        return 0
    else
        run_tests
        return $?
    fi
}

# Run main function
main
exit $?
