#!/bin/bash
# Run MCP Tests
# Enhanced script for running MCP server tests with proper diagnostics and error handling

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Test configuration
PORT=9998
HOST="localhost"
RESULTS_DIR="test_results"

# Function for logging
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
    
    echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message${NC}" | tee -a "${LOG_FILE}"
}

# Create results directory if it doesn't exist
mkdir -p "$RESULTS_DIR"

# Generate timestamp for logs
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$RESULTS_DIR/mcp_test_$TIMESTAMP.log"
echo "Starting MCP test with enhanced diagnostics at $(date)" > "${LOG_FILE}"

# Parse command-line options
VERBOSE=""
FULL_TESTS=false
CLEAN_ENV=true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --verbose|-v)
            VERBOSE="--verbose"
            shift
            ;;
        --all|-a)
            FULL_TESTS=true
            shift
            ;;
        --no-clean)
            CLEAN_ENV=false
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --verbose, -v    Run tests with verbose output"
            echo "  --all, -a        Run all tests, not just basic ones"
            echo "  --no-clean       Skip environment cleanup"
            echo "  --help, -h       Show this help message"
            exit 0
            ;;
        *)
            log "ERROR" "Unknown option: $1"
            exit 1
            ;;
    esac
done

log "INFO" "Starting MCP test suite"

# Clean up any existing processes if requested
if [ "$CLEAN_ENV" = true ]; then
    log "INFO" "Cleaning up environment before testing"
    ./cleanup_mcp_server.sh --full >> "$LOG_FILE" 2>&1
    if [ $? -ne 0 ]; then
        log "WARNING" "Cleanup reported issues. See $LOG_FILE for details."
    fi
    
    # Check if port is available after cleanup
    if command -v lsof >/dev/null 2>&1; then
        PORT_PROCESS=$(lsof -i :$PORT -t 2>/dev/null)
        if [ -n "$PORT_PROCESS" ]; then
            log "ERROR" "Port $PORT is still in use after cleanup. Try again or use a different port."
            exit 1
        else
            log "SUCCESS" "Port $PORT is available for testing"
        fi
    else
        log "WARNING" "lsof command not found, can't verify port availability"
    fi
else
    log "INFO" "Skipping environment cleanup as requested"
fi

# Run the enhanced tests
log "INFO" "Starting enhanced MCP tests on $HOST:$PORT"
if [ "$FULL_TESTS" = true ]; then
    log "INFO" "Running all tests"
    python3 enhanced_ipfs_mcp_test.py --host "$HOST" --port "$PORT" $VERBOSE 2>&1 | tee -a "$LOG_FILE"
else
    log "INFO" "Running basic tests only"
    python3 enhanced_ipfs_mcp_test.py --host "$HOST" --port "$PORT" $VERBOSE --basic-only 2>&1 | tee -a "$LOG_FILE"
fi
TEST_RESULT=${PIPESTATUS[0]}

# Check the test result
if [ $TEST_RESULT -eq 0 ]; then
    log "SUCCESS" "All tests passed successfully!"
else
    log "ERROR" "Some tests failed or encountered errors"
    
    # Extract errors from the log file for quick reference
    log "INFO" "Extracting relevant error information from logs..."
    {
        echo "=== ERROR SUMMARY ==="
        echo ""
        grep -E "ERROR|FAIL|Exception|Error:|Failed" "$LOG_FILE" | sort | uniq
        echo ""
        echo "=== TEST FAILURE DETAILS ==="
        echo ""
        grep -A 5 -B 1 -E "FAIL:|ERROR:" "$LOG_FILE"
    } > "$RESULTS_DIR/error_summary_$TIMESTAMP.txt"
    
    log "INFO" "Error summary saved to $RESULTS_DIR/error_summary_$TIMESTAMP.txt"
fi

# Check the MCP server log file for any issues
if [ -f "final_mcp_server.log" ]; then
    log "INFO" "Checking MCP server log for issues"
    
    if grep -E "ERROR|Exception|Error:|Failed|Traceback" "final_mcp_server.log" > /dev/null; then
        log "WARNING" "Found potential issues in MCP server log"
        grep -E "ERROR|Exception|Error:|Failed|Traceback" "final_mcp_server.log" | \
            head -20 > "$RESULTS_DIR/server_errors_$TIMESTAMP.txt"
        log "INFO" "Server error summary saved to $RESULTS_DIR/server_errors_$TIMESTAMP.txt"
    else
        log "SUCCESS" "No obvious errors found in server log"
    fi
    
    # Save the full server log for reference
    cp "final_mcp_server.log" "$RESULTS_DIR/server_log_$TIMESTAMP.log"
    log "INFO" "Full server log saved to $RESULTS_DIR/server_log_$TIMESTAMP.log"
fi

# Clean up after tests if requested
if [ "$CLEAN_ENV" = true ]; then
    log "INFO" "Cleaning up environment after testing"
    ./cleanup_mcp_server.sh >> "$LOG_FILE" 2>&1
else
    log "INFO" "Skipping post-test cleanup as requested"
    log "INFO" "Server is still running. To stop it manually, use: ./cleanup_mcp_server.sh"
fi

log "INFO" "Test run complete. Full log available at $LOG_FILE"

# Return the test result
exit $TEST_RESULT
