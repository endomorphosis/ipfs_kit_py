#!/bin/bash
# Test IPFS MCP Integration
# This script tests the IPFS integration in the MCP server

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
LOG_FILE="final_ipfs_test.log"
PID_FILE="final_mcp_server.pid"
MAX_WAIT=60
CURL_TIMEOUT=10

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
    
    # Also check for any processes on the port
    PORT_PID=$(lsof -i :$PORT -t 2>/dev/null || true)
    if [ -n "$PORT_PID" ]; then
        log "WARNING" "Found process using port $PORT: $PORT_PID"
        kill "$PORT_PID" 2>/dev/null || true
        sleep 1
        if lsof -i :$PORT -t 2>/dev/null; then
            log "WARNING" "Process still using port, forcing with SIGKILL"
            kill -9 "$PORT_PID" 2>/dev/null || true
        fi
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
            cat "$LOG_FILE" | tail -n 50
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
            cat "$LOG_FILE" | tail -n 50
            return 1
        fi
        
        # Wait and retry
        sleep 1
    done
    
    return 0
}

# Call JSON-RPC method on server
call_jsonrpc() {
    local method="$1"
    local params="$2"
    
    log "INFO" "Calling JSON-RPC method: $method"
    
    # Create JSON-RPC request
    local request="{\"jsonrpc\":\"2.0\",\"id\":\"$(date +%s%N)\",\"method\":\"$method\",\"params\":$params}"
    
    # Make the request
    local response=$(curl -s -X POST -H "Content-Type: application/json" -d "$request" "http://$HOST:$PORT/jsonrpc" --connect-timeout $CURL_TIMEOUT)
    
    # Check for curl errors
    if [ $? -ne 0 ]; then
        log "ERROR" "Failed to connect to server"
        return 1
    fi
    
    echo "$response"
}

# Test IPFS tools registration
test_tools_registration() {
    log "INFO" "Testing tool registration"
    
    # Get all tools
    local result=$(call_jsonrpc "get_tools" "{}")
    
    # Check if any IPFS tools are registered
    if echo "$result" | grep -q "ipfs_add"; then
        log "SUCCESS" "IPFS tools are registered"
        
        # Print the list of IPFS tools
        echo "$result" | grep -o '"name":"ipfs_[^"]*"' | sed 's/"name":"//g' | sed 's/"//g' | sort | while read tool; do
            log "INFO" "Found tool: $tool"
        done
        
        return 0
    else
        log "ERROR" "No IPFS tools found in registered tools"
        return 1
    fi
}

# Test ipfs_add
test_ipfs_add() {
    log "INFO" "Testing ipfs_add"
    
    # Test with content parameter
    local result=$(call_jsonrpc "ipfs_add" "{\"content\":\"Hello IPFS World!\"}")
    
    # Check for success
    if echo "$result" | grep -q "\"cid\":"; then
        local cid=$(echo "$result" | grep -o '"cid":"[^"]*"' | sed 's/"cid":"//g' | sed 's/"//g')
        log "SUCCESS" "ipfs_add successful with content parameter. CID: $cid"
        echo "$cid"  # Return the CID for use in other tests
        return 0
    elif echo "$result" | grep -q "\"error\":"; then
        local error=$(echo "$result" | grep -o '"error":"[^"]*"' | sed 's/"error":"//g' | sed 's/"//g')
        log "ERROR" "ipfs_add failed: $error"
        return 1
    else
        log "ERROR" "Unexpected response from ipfs_add"
        echo "$result"
        return 1
    fi
}

# Test ipfs_cat
test_ipfs_cat() {
    local cid="$1"
    
    if [ -z "$cid" ]; then
        log "WARNING" "No CID provided, using default test CID"
        cid="QmPZ9gcCEpqKTo6aq61g2nXGUhM4iCL3ewB6LDXZCtioEB"
    fi
    
    log "INFO" "Testing ipfs_cat with CID: $cid"
    
    # Call ipfs_cat
    local result=$(call_jsonrpc "ipfs_cat" "{\"cid\":\"$cid\"}")
    
    # Check for success
    if echo "$result" | grep -q "\"content\":"; then
        log "SUCCESS" "ipfs_cat successful"
        return 0
    elif echo "$result" | grep -q "\"error\":"; then
        local error=$(echo "$result" | grep -o '"error":"[^"]*"' | sed 's/"error":"//g' | sed 's/"//g')
        log "ERROR" "ipfs_cat failed: $error"
        return 1
    else
        log "ERROR" "Unexpected response from ipfs_cat"
        echo "$result"
        return 1
    fi
}

# Test MFS operations
test_mfs_operations() {
    local test_path="/test_path_$(date +%s)"
    
    log "INFO" "Testing MFS operations with path: $test_path"
    
    # Create directory
    log "INFO" "Testing ipfs_files_mkdir"
    local mkdir_result=$(call_jsonrpc "ipfs_files_mkdir" "{\"path\":\"$test_path\"}")
    
    if ! echo "$mkdir_result" | grep -q "\"success\":true"; then
        if echo "$mkdir_result" | grep -q "\"error\":"; then
            local error=$(echo "$mkdir_result" | grep -o '"error":"[^"]*"' | sed 's/"error":"//g' | sed 's/"//g')
            log "ERROR" "ipfs_files_mkdir failed: $error"
        else
            log "ERROR" "Unexpected response from ipfs_files_mkdir"
            echo "$mkdir_result"
        fi
        return 1
    fi
    
    # Write file
    log "INFO" "Testing ipfs_files_write"
    local write_result=$(call_jsonrpc "ipfs_files_write" "{\"path\":\"$test_path/test.txt\",\"content\":\"Hello MFS World!\",\"create\":true}")
    
    if ! echo "$write_result" | grep -q "\"success\":true"; then
        if echo "$write_result" | grep -q "\"error\":"; then
            local error=$(echo "$write_result" | grep -o '"error":"[^"]*"' | sed 's/"error":"//g' | sed 's/"//g')
            log "ERROR" "ipfs_files_write failed: $error"
        else
            log "ERROR" "Unexpected response from ipfs_files_write"
            echo "$write_result"
        fi
        return 1
    fi
    
    # Read file
    log "INFO" "Testing ipfs_files_read"
    local read_result=$(call_jsonrpc "ipfs_files_read" "{\"path\":\"$test_path/test.txt\"}")
    
    if ! echo "$read_result" | grep -q "\"content\":"; then
        if echo "$read_result" | grep -q "\"error\":"; then
            local error=$(echo "$read_result" | grep -o '"error":"[^"]*"' | sed 's/"error":"//g' | sed 's/"//g')
            log "ERROR" "ipfs_files_read failed: $error"
        else
            log "ERROR" "Unexpected response from ipfs_files_read"
            echo "$read_result"
        fi
        return 1
    fi
    
    # List directory
    log "INFO" "Testing ipfs_files_ls"
    local ls_result=$(call_jsonrpc "ipfs_files_ls" "{\"path\":\"$test_path\"}")
    
    if ! echo "$ls_result" | grep -q "\"entries\":"; then
        if echo "$ls_result" | grep -q "\"error\":"; then
            local error=$(echo "$ls_result" | grep -o '"error":"[^"]*"' | sed 's/"error":"//g' | sed 's/"//g')
            log "ERROR" "ipfs_files_ls failed: $error"
        else
            log "ERROR" "Unexpected response from ipfs_files_ls"
            echo "$ls_result"
        fi
        return 1
    fi
    
    # Remove directory
    log "INFO" "Testing ipfs_files_rm"
    local rm_result=$(call_jsonrpc "ipfs_files_rm" "{\"path\":\"$test_path\",\"recursive\":true}")
    
    if ! echo "$rm_result" | grep -q "\"success\":true"; then
        if echo "$rm_result" | grep -q "\"error\":"; then
            local error=$(echo "$rm_result" | grep -o '"error":"[^"]*"' | sed 's/"error":"//g' | sed 's/"//g')
            log "ERROR" "ipfs_files_rm failed: $error"
        else
            log "ERROR" "Unexpected response from ipfs_files_rm"
            echo "$rm_result"
        fi
        return 1
    fi
    
    log "SUCCESS" "All MFS operations successful"
    return 0
}

# Test with alternative parameter names
test_parameter_variations() {
    log "INFO" "Testing parameter variations for ipfs_add"
    
    # Test with data parameter instead of content
    local result1=$(call_jsonrpc "ipfs_add" "{\"data\":\"Test with data parameter\"}")
    
    # Test with text parameter instead of content
    local result2=$(call_jsonrpc "ipfs_add" "{\"text\":\"Test with text parameter\"}")
    
    # Test with different filename parameter
    local result3=$(call_jsonrpc "ipfs_add" "{\"content\":\"Test with name parameter\",\"name\":\"test_file.txt\"}")
    
    # Check results
    local success=0
    
    if echo "$result1" | grep -q "\"cid\":"; then
        log "SUCCESS" "ipfs_add successful with data parameter"
    else
        log "ERROR" "ipfs_add failed with data parameter"
        echo "$result1"
        success=1
    fi
    
    if echo "$result2" | grep -q "\"cid\":"; then
        log "SUCCESS" "ipfs_add successful with text parameter"
    else
        log "ERROR" "ipfs_add failed with text parameter"
        echo "$result2"
        success=1
    fi
    
    if echo "$result3" | grep -q "\"cid\":"; then
        log "SUCCESS" "ipfs_add successful with name parameter"
    else
        log "ERROR" "ipfs_add failed with name parameter"
        echo "$result3"
        success=1
    fi
    
    return $success
}

# Run all tests
run_all_tests() {
    log "INFO" "Running all tests"
    
    # Test tool registration
    test_tools_registration
    if [ $? -ne 0 ]; then
        log "ERROR" "Tool registration test failed"
        return 1
    fi
    
    # Test ipfs_add
    local cid=$(test_ipfs_add)
    if [ $? -ne 0 ]; then
        log "ERROR" "ipfs_add test failed"
        return 1
    fi
    
    # Test ipfs_cat
    test_ipfs_cat "$cid"
    if [ $? -ne 0 ]; then
        log "ERROR" "ipfs_cat test failed"
        return 1
    fi
    
    # Test MFS operations
    test_mfs_operations
    if [ $? -ne 0 ]; then
        log "ERROR" "MFS operations test failed"
        return 1
    fi
    
    # Test parameter variations
    test_parameter_variations
    if [ $? -ne 0 ]; then
        log "ERROR" "Parameter variations test failed"
        return 1
    fi
    
    log "SUCCESS" "All tests passed!"
    return 0
}

# Main function
main() {
    log "INFO" "Starting IPFS MCP integration tests"
    
    # Kill any existing servers
    kill_existing_servers
    
    # Start the server
    start_server
    if [ $? -ne 0 ]; then
        log "ERROR" "Failed to start MCP server"
        return 1
    fi
    
    # Run all tests
    run_all_tests
    TEST_RESULT=$?
    
    # Cleanup
    log "INFO" "Cleaning up"
    kill_existing_servers
    
    # Final result
    if [ $TEST_RESULT -eq 0 ]; then
        log "SUCCESS" "🎉 IPFS MCP integration tests completed successfully"
        return 0
    else
        log "ERROR" "❌ IPFS MCP integration tests failed"
        return 1
    fi
}

# Run the main function
main
exit $?
