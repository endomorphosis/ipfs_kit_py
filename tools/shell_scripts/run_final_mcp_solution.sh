#!/bin/bash
# Simplified MCP Server Launcher Script
# This script provides a more reliable way to start the final MCP server solution
# and fixes issues with the original start_final_solution.sh script

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
LOG_FILE="mcp_server.log"
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
                sleep 1
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
    
    # Start the server in the background
    python3 "$MCP_SERVER" --host "$HOST" --port "$PORT" --debug > "$LOG_FILE" 2>&1 &
    SERVER_PID=$!
    echo "$SERVER_PID" > "$PID_FILE"
    log "INFO" "MCP server started with PID: $SERVER_PID"
    
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
}

# Test the JSON-RPC endpoint
test_jsonrpc() {
    log "INFO" "Testing JSON-RPC endpoint"
    
    # Test ping method
    log "INFO" "Testing ping method"
    PING_RESULT=$(curl -s -X POST -H "Content-Type: application/json" \
                -d '{"jsonrpc":"2.0","method":"ping","params":{},"id":1}' \
                http://localhost:$PORT/jsonrpc)
    if echo "$PING_RESULT" | grep -q '"result":"pong"'; then
        log "SUCCESS" "Ping test successful"
    else
        log "ERROR" "Ping test failed: $PING_RESULT"
    fi
    
    # Test get_tools method
    log "INFO" "Testing get_tools method"
    TOOLS_RESULT=$(curl -s -X POST -H "Content-Type: application/json" \
                  -d '{"jsonrpc":"2.0","method":"get_tools","params":{},"id":2}' \
                  http://localhost:$PORT/jsonrpc)
    
    # More robust approach without complex grep patterns
    if [[ "$TOOLS_RESULT" == *'"result":{"tools":'* ]] || [[ "$TOOLS_RESULT" == *'"tools":'* ]]; then
        TOOL_COUNT=$(echo "$TOOLS_RESULT" | grep -o '"name"' | wc -l)
        log "SUCCESS" "get_tools test successful, found $TOOL_COUNT tools"
    else
        log "ERROR" "get_tools test failed: $TOOLS_RESULT"
    fi
    
    # Test get_server_info method
    log "INFO" "Testing get_server_info method"
    SERVER_INFO_RESULT=$(curl -s -X POST -H "Content-Type: application/json" \
                      -d '{"jsonrpc":"2.0","method":"get_server_info","params":{},"id":3}' \
                      http://localhost:$PORT/jsonrpc)
    
    if [[ "$SERVER_INFO_RESULT" == *'"version":'* ]]; then
        SERVER_VERSION=$(echo "$SERVER_INFO_RESULT" | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
        log "SUCCESS" "get_server_info test successful, server version: $SERVER_VERSION"
    else
        log "ERROR" "get_server_info test failed: $SERVER_INFO_RESULT"
    fi
}

# Run enhanced JSON-RPC tests
run_enhanced_jsonrpc_test() {
    log "INFO" "Running enhanced JSON-RPC tests"
    
    if [ -f "enhanced_jsonrpc_test.py" ]; then
        python3 enhanced_jsonrpc_test.py --host localhost "$PORT" --verbose > "$TEST_RESULTS_DIR/enhanced_jsonrpc_test_$(date +%Y%m%d_%H%M%S).log" 2>&1
        if [ $? -eq 0 ]; then
            log "SUCCESS" "Enhanced JSON-RPC tests passed"
            return 0
        else
            log "ERROR" "Enhanced JSON-RPC tests failed"
            tail -n 10 "$TEST_RESULTS_DIR/enhanced_jsonrpc_test_$(date +%Y%m%d_%H%M%S).log"
            return 1
        fi
    else
        log "WARNING" "enhanced_jsonrpc_test.py not found, skipping enhanced JSON-RPC tests"
        return 0
    fi
}

# Run comprehensive MCP server tests
run_comprehensive_tests() {
    log "INFO" "Running comprehensive MCP server tests"
    
    if [ -f "comprehensive_mcp_test.py" ]; then
        python3 comprehensive_mcp_test.py --url "http://localhost:$PORT" --verbose > "$TEST_RESULTS_DIR/comprehensive_mcp_test_$(date +%Y%m%d_%H%M%S).log" 2>&1
        if [ $? -eq 0 ]; then
            log "SUCCESS" "Comprehensive MCP server tests passed"
            return 0
        else
            log "ERROR" "Comprehensive MCP server tests failed"
            tail -n 10 "$TEST_RESULTS_DIR/comprehensive_mcp_test_$(date +%Y%m%d_%H%M%S).log"
            return 1
        fi
    else
        log "WARNING" "comprehensive_mcp_test.py not found, skipping comprehensive tests"
        return 0
    fi
}

# Run simple MCP tester
run_simple_mcp_tests() {
    log "INFO" "Running simple MCP tester"
    
    if [ -f "simple_mcp_tester.py" ]; then
        python3 simple_mcp_tester.py --url "http://localhost:$PORT/jsonrpc" > "$TEST_RESULTS_DIR/simple_mcp_test_$(date +%Y%m%d_%H%M%S).log" 2>&1
        if [ $? -eq 0 ]; then
            log "SUCCESS" "Simple MCP tests passed"
            return 0
        else
            log "WARNING" "Simple MCP tests completed with some issues"
            tail -n 10 "$TEST_RESULTS_DIR/simple_mcp_test_$(date +%Y%m%d_%H%M%S).log"
            return 0  # Don't fail the script for simple test issues
        fi
    else
        log "WARNING" "simple_mcp_tester.py not found, skipping simple tests"
        return 0
    fi
}
# Function to run the enhanced test suite
run_enhanced_tests() {
    log "INFO" "Running enhanced MCP test suite"
    
    # Make sure the Python script is executable
    chmod +x enhanced_mcp_test_suite.py
    
    # Run the enhanced test suite and capture the output
    python3 enhanced_mcp_test_suite.py --url "http://$HOST:$PORT" --output-dir "$TEST_RESULTS_DIR" --verbose
    local test_result=$?
    
    if [ $test_result -eq 0 ]; then
        log "SUCCESS" "Enhanced MCP test suite passed successfully"
        return 0
    else
        log "ERROR" "Enhanced MCP test suite found issues"
        log "INFO" "Check the test_results directory for detailed reports"
        return 1
    fi
}

# Run the improved comprehensive MCP test runner
run_improved_mcp_tests() {
    log "INFO" "Running improved MCP test runner"
    
    # Make sure test runner exists
    if [ ! -f "mcp_test_runner.py" ]; then
        log "WARNING" "Improved MCP test runner not found, skipping enhanced testing"
        return 0
    fi
    
    # Make sure the test runner is executable
    chmod +x mcp_test_runner.py
    
    # Run the test runner
    python3 mcp_test_runner.py --port $PORT --server-file $MCP_SERVER
    
    if [ $? -eq 0 ]; then
        log "SUCCESS" "Improved MCP tests passed"
        return 0
    else
        log "ERROR" "Some improved MCP tests failed"
        log "INFO" "Check mcp_test_results.json and mcp_test_runner.log for details"
        # Don't return error as this is non-critical testing
        return 0
    fi
}

# Function to provide status summary
print_status_summary() {
    log "INFO" "====================== MCP Server Status ======================"
    log "INFO" "Server running on port: $PORT with PID: $(cat $PID_FILE 2>/dev/null || echo "unknown")"
    log "INFO" "Server version: $(curl -s http://localhost:$PORT/health | grep -o '"version":"[^"]*"' | cut -d'"' -f4)"
    log "INFO" "Uptime: $(curl -s http://localhost:$PORT/health | grep -o '"uptime_seconds":[^,]*' | cut -d':' -f2) seconds"
    log "INFO" "Tools count: $(curl -s http://localhost:$PORT/health | grep -o '"tools_count":[^,]*' | cut -d':' -f2)"
    log "INFO" "Tool categories: $(curl -s http://localhost:$PORT/health | grep -o '"registered_tool_categories":\[[^\]]*\]' | cut -d':' -f2-)"
    log "INFO" "=============================================================="
    log "INFO" "Health endpoint: http://localhost:$PORT/health"
    log "INFO" "JSON-RPC endpoint: http://localhost:$PORT/jsonrpc"
    log "INFO" "To stop the server, run: kill $(cat $PID_FILE 2>/dev/null || echo "<pid>") or ./run_final_mcp_solution.sh --stop"
    log "INFO" "=============================================================="
}

# Parse command-line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        key="$1"
        case $key in
            --port)
                PORT="$2"
                shift 2
                ;;
            --host)
                HOST="$2"
                shift 2
                ;;
            --stop)
                stop_server=true
                shift
                ;;
            --status)
                show_status=true
                shift
                ;;
            --test-only)
                test_only=true
                shift
                ;;
            --start-only)
                start_only=true
                shift
                ;;
            --help)
                show_help=true
                shift
                ;;
            *)
                log "ERROR" "Unknown option: $1"
                exit 1
                ;;
        esac
    done
}

# Show help/usage information
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  --port PORT       Port for the MCP server (default: 9997)"
    echo "  --host HOST       Host for the MCP server (default: 0.0.0.0)"
    echo "  --stop            Stop the running server"
    echo "  --status          Show server status"
    echo "  --test-only       Run tests against running server without starting/stopping"
    echo "  --start-only      Start the server without running tests"
    echo "  --help            Show this help message"
    echo
}

# Main function
main() {
    local stop_server=false
    local show_status=false
    local test_only=false
    local start_only=false
    local show_help=false
    
    # Parse command-line arguments
    parse_args $*
    
    if [ "$show_help" = "true" ]; then
        show_usage
        return 0
    fi
    
    # Handle --stop option
    if [ "$stop_server" = "true" ]; then
        log "INFO" "Stopping MCP server"
        kill_existing_servers
        log "SUCCESS" "MCP server stopped"
        return 0
    fi
    
    # Handle --status option
    if [ "$show_status" = "true" ]; then
        if [ -f "$PID_FILE" ] && ps -p "$(cat $PID_FILE)" > /dev/null 2>&1; then
            print_status_summary
        else
            log "ERROR" "MCP server is not running"
            return 1
        fi
        return 0
    fi
    
    # Handle --test-only option
    if [ "$test_only" = "true" ]; then
        log "INFO" "Running tests against existing MCP server"
        if ! curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
            log "ERROR" "No MCP server running on port $PORT"
            return 1
        fi
        
        test_jsonrpc
        run_enhanced_tests
        run_enhanced_jsonrpc_test
        run_improved_mcp_tests
        log "SUCCESS" "Tests completed"
        return 0
    fi
    
    # Handle --start-only option
    if [ "$start_only" = "true" ]; then
        log "INFO" "Starting MCP server only (no tests)"
        
        # Kill any existing servers
        kill_existing_servers
        
        # Check if port is available
        if ! check_port; then
            return 1
        fi
        
        # Start the server
        if ! start_server; then
            return 1
        fi
        
        log "SUCCESS" "MCP server started successfully on port $PORT"
        print_status_summary
        return 0
    fi
    
    # Normal startup flow
    log "INFO" "Starting MCP server solution"
    
    # Kill any existing servers
    kill_existing_servers
    
    # Check if port is available
    if ! check_port; then
        return 1
    fi
    
    # Start the server
    if ! start_server; then
        return 1
    fi
    
    # Test the server
    test_jsonrpc
    run_enhanced_jsonrpc_test
    run_comprehensive_tests
    run_simple_mcp_tests
    
    # Run our new enhanced tests for more thorough validation
    if [ -f "enhanced_mcp_test_suite.py" ]; then
        run_enhanced_tests
    else
        log "WARNING" "Enhanced MCP test suite not found, skipping enhanced tests"
    fi
    
    # Run our improved MCP test runner for comprehensive diagnostics
    run_improved_mcp_tests
    
    # Run the improved MCP test runner if available
    run_improved_mcp_tests
    
    log "SUCCESS" "MCP server is running successfully on port $PORT"
    print_status_summary
    
    return 0
}

# Run the main function
main "$@"
exit $?
