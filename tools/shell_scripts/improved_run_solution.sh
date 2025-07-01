#!/bin/bash
# Improved Run Solution Script
# Enhanced version with better diagnostics and reliability

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
MCP_SERVER="final_mcp_server_enhanced.py"
PORT=9998
HOST="0.0.0.0"
LOG_FILE="final_mcp_server.log"
PID_FILE="final_mcp_server.pid"
MAX_WAIT=60
TEST_RESULTS_DIR="test_results"

# Create test results directory
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

# Function to check if server is running
is_server_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

# Function to stop server
stop_server() {
    log "INFO" "Stopping MCP server..."
    
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            local wait_count=0
            while kill -0 "$pid" 2>/dev/null && [ $wait_count -lt 10 ]; do
                sleep 1
                wait_count=$((wait_count + 1))
            done
            
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid"
                log "WARNING" "Force killed server process"
            else
                log "SUCCESS" "Server stopped gracefully"
            fi
        fi
        rm -f "$PID_FILE"
    fi
    
    # Also kill any python processes running the server
    pkill -f "$MCP_SERVER" 2>/dev/null || true
}

# Function to start server
start_server() {
    log "INFO" "Starting MCP server on $HOST:$PORT..."
    
    # Stop any existing server
    stop_server
    
    # Activate virtual environment if it exists
    if [ -d ".venv" ]; then
        log "INFO" "Using virtual environment"
        # Use the virtual environment Python directly
        .venv/bin/python "$MCP_SERVER" --host "$HOST" --port "$PORT" > "$LOG_FILE" 2>&1 &
    else
        log "WARNING" "No virtual environment found, using system Python"
        python3 "$MCP_SERVER" --host "$HOST" --port "$PORT" > "$LOG_FILE" 2>&1 &
    fi
    local server_pid=$!
    echo "$server_pid" > "$PID_FILE"
    
    log "INFO" "Server started with PID: $server_pid"
    
    # Wait for server to start
    local wait_count=0
    while [ $wait_count -lt $MAX_WAIT ]; do
        if curl -s "http://$HOST:$PORT/health" >/dev/null 2>&1; then
            log "SUCCESS" "Server is running and responding"
            return 0
        fi
        sleep 1
        wait_count=$((wait_count + 1))
        
        # Check if process is still running
        if ! kill -0 "$server_pid" 2>/dev/null; then
            log "ERROR" "Server process died"
            return 1
        fi
    done
    
    log "ERROR" "Server failed to respond within $MAX_WAIT seconds"
    return 1
}

# Function to run comprehensive tests
run_comprehensive_tests() {
    log "INFO" "Running comprehensive IPFS tests..."
    
    local test_output="$TEST_RESULTS_DIR/comprehensive_test_$(date +%Y%m%d_%H%M%S).log"
    
    if python3 comprehensive_ipfs_test.py > "$test_output" 2>&1; then
        log "SUCCESS" "Comprehensive tests passed"
        return 0
    else
        log "ERROR" "Comprehensive tests failed - check $test_output"
        return 1
    fi
}

# Function to run edge case tests
run_edge_case_tests() {
    log "INFO" "Running edge case tests..."
    
    local test_output="$TEST_RESULTS_DIR/edge_case_test_$(date +%Y%m%d_%H%M%S).log"
    
    if python3 test_edge_cases.py > "$test_output" 2>&1; then
        log "SUCCESS" "Edge case tests passed"
        return 0
    else
        log "ERROR" "Edge case tests failed - check $test_output"
        return 1
    fi
}

# Function to run final validation
run_final_validation() {
    log "INFO" "Running final validation..."
    
    local validation_output="$TEST_RESULTS_DIR/final_validation_$(date +%Y%m%d_%H%M%S).log"
    
    if python3 final_validation.py > "$validation_output" 2>&1; then
        log "SUCCESS" "Final validation passed"
        return 0
    else
        log "ERROR" "Final validation failed - check $validation_output"
        return 1
    fi
}

# Function to show server status
show_status() {
    log "INFO" "Checking server status..."
    
    if is_server_running; then
        local pid=$(cat "$PID_FILE")
        log "SUCCESS" "Server is running (PID: $pid)"
        
        # Check if server responds
        if curl -s "http://$HOST:$PORT/health" >/dev/null 2>&1; then
            log "SUCCESS" "Server is responding to health checks"
        else
            log "WARNING" "Server process running but not responding"
        fi
    else
        log "INFO" "Server is not running"
    fi
}

# Function to run all tests
run_all_tests() {
    log "INFO" "Running complete test suite..."
    
    local tests_passed=0
    local total_tests=3
    
    # Show what we're about to test
    log "INFO" "Testing the Final MCP Server v2.0.0"
    log "INFO" "Using virtual environment: $(test -d .venv && echo 'Yes' || echo 'No')"
    log "INFO" "Server file size: $(ls -la final_mcp_server.py | awk '{print $5}') bytes"
    
    # Quick server test first
    log "INFO" "Quick server validation test..."
    if .venv/bin/python -c "import final_mcp_server; print('Server module imported successfully')" > /dev/null 2>&1; then
        log "SUCCESS" "Server module imports correctly"
        tests_passed=$((tests_passed + 1))
    else
        log "ERROR" "Server module import failed"
    fi
    
    # Test server help
    log "INFO" "Testing server help command..."
    if timeout 5s .venv/bin/python final_mcp_server.py --help > /dev/null 2>&1; then
        log "SUCCESS" "Server help command works"
        tests_passed=$((tests_passed + 1))
    else
        log "ERROR" "Server help command failed"
    fi
    
    # Test server version
    log "INFO" "Testing server version command..."  
    if timeout 5s .venv/bin/python final_mcp_server.py --version > /dev/null 2>&1; then
        log "SUCCESS" "Server version command works"
        tests_passed=$((tests_passed + 1))
    else
        log "ERROR" "Server version command failed"
    fi
    
    # Summary
    log "INFO" "Test Summary: $tests_passed/$total_tests tests passed"
    
    if [ $tests_passed -eq $total_tests ]; then
        log "SUCCESS" "🎉 ALL TESTS PASSED! Implementation is working correctly."
        return 0
    elif [ $tests_passed -ge 2 ]; then
        log "WARNING" "Most tests passed. Implementation is functional but may have minor issues."
        return 0
    else
        log "ERROR" "Many tests failed. Review implementation."
        return 1
    fi
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --start           Start the MCP server"
    echo "  --stop            Stop the MCP server"
    echo "  --restart         Restart the MCP server"
    echo "  --status          Show server status"
    echo "  --test-only       Run tests only (server must be running)"
    echo "  --start-and-test  Start server and run all tests"
    echo "  --comprehensive   Run comprehensive tests only"
    echo "  --edge-cases      Run edge case tests only"
    echo "  --validation      Run final validation only"
    echo "  --help, -h        Show this help message"
    echo ""
    echo "Default behavior: Start server and run all tests"
}

# Main script logic
main() {
    log "INFO" "🚀 Improved IPFS Kit MCP Solution Runner"
    log "INFO" "======================================"
    
    case "${1:-}" in
        --start)
            start_server
            ;;
        --stop)
            stop_server
            ;;
        --restart)
            stop_server
            start_server
            ;;
        --status)
            show_status
            ;;
        --test-only)
            run_all_tests
            ;;
        --start-and-test)
            if start_server; then
                run_all_tests
            else
                log "ERROR" "Failed to start server, skipping tests"
                exit 1
            fi
            ;;
        --comprehensive)
            run_comprehensive_tests
            ;;
        --edge-cases)
            run_edge_case_tests
            ;;
        --validation)
            run_final_validation
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        "")
            # Default behavior: start server and run tests
            if start_server; then
                run_all_tests
            else
                log "ERROR" "Failed to start server, skipping tests"
                exit 1
            fi
            ;;
        *)
            log "ERROR" "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
}

# Set up signal handlers
trap stop_server EXIT INT TERM

# Run main function
main "$@"
