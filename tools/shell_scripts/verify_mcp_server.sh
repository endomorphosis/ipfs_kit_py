#!/bin/bash
# Comprehensive MCP Server Test and Verification
# This script provides comprehensive testing for the final MCP server implementation

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
LOG_FILE="mcp_verification_$(date +%Y%m%d_%H%M%S).log"

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
    
    echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message${NC}" | tee -a "$LOG_FILE"
}

# Check if enhanced scripts exist
check_scripts() {
    log "INFO" "Checking for required test scripts..."
    
    if [ ! -f "enhanced_mcp_test.py" ]; then
        log "ERROR" "Enhanced MCP test script not found: enhanced_mcp_test.py"
        return 1
    fi
    
    if [ ! -f "enhanced_ipfs_mcp_test.py" ]; then
        log "ERROR" "Enhanced IPFS MCP test script not found: enhanced_ipfs_mcp_test.py"
        return 1
    fi
    
    if [ ! -f "final_mcp_server.py" ]; then
        log "ERROR" "MCP server script not found: final_mcp_server.py"
        return 1
    fi
    
    log "SUCCESS" "All required scripts found"
    return 0
}

# Run port consistency check
check_port_consistency() {
    log "INFO" "Checking port consistency across configuration files..."
    ./enhanced_mcp_test.py --fix --verbose >> "$LOG_FILE" 2>&1
    
    if [ $? -eq 0 ]; then
        log "SUCCESS" "Port consistency check passed"
        return 0
    else
        log "ERROR" "Port consistency check failed"
        return 1
    fi
}

# Start or verify MCP server
ensure_server_running() {
    log "INFO" "Ensuring MCP server is running..."
    
    # Check if server is already running
    if curl -s "http://$HOST:$PORT/health" > /dev/null 2>&1; then
        log "SUCCESS" "MCP server is already running"
        return 0
    fi
    
    # Try to start the server
    log "INFO" "Starting MCP server..."
    ./enhanced_ipfs_mcp_test.py --verbose 2>&1 | grep "MCP server" >> "$LOG_FILE"
    
    # Check if server is now running
    if curl -s "http://$HOST:$PORT/health" > /dev/null 2>&1; then
        log "SUCCESS" "MCP server started successfully"
        return 0
    else
        log "ERROR" "Failed to start MCP server"
        return 1
    fi
}

# Run basic tests
run_basic_tests() {
    log "INFO" "Running basic server tests..."
    
    ./enhanced_ipfs_mcp_test.py --verbose --basic-only >> "$LOG_FILE" 2>&1
    
    if [ $? -eq 0 ]; then
        log "SUCCESS" "Basic server tests passed"
        return 0
    else
        log "ERROR" "Basic server tests failed"
        return 1
    fi
}

# Get server info
get_server_info() {
    log "INFO" "Retrieving server information..."
    
    response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","method":"get_server_info","params":{},"id":1}' \
        http://$HOST:$PORT/jsonrpc)
        
    if [ $? -eq 0 ]; then
        echo $response | jq . >> "$LOG_FILE" 2>/dev/null
        version=$(echo $response | jq -r '.result.version' 2>/dev/null)
        tools=$(echo $response | jq -r '.result.registered_tools' 2>/dev/null)
        uptime=$(echo $response | jq -r '.result.uptime_seconds' 2>/dev/null)
        categories=$(echo $response | jq -r '.result.registered_tool_categories' 2>/dev/null)
        
        log "SUCCESS" "Server information retrieved:"
        log "INFO" "  Version: $version"
        log "INFO" "  Registered Tools: $tools"
        log "INFO" "  Uptime: $uptime seconds"
        log "INFO" "  Tool Categories: $categories"
        return 0
    else
        log "ERROR" "Failed to retrieve server information"
        return 1
    fi
}

# Main function
main() {
    echo -e "${BOLD}MCP Server Verification Suite${NC}"
    echo "Starting comprehensive verification at $(date)"
    echo "Log file: $LOG_FILE"
    echo
    
    # Check for scripts
    check_scripts || exit 1
    
    # Make scripts executable if not already
    chmod +x enhanced_mcp_test.py enhanced_ipfs_mcp_test.py
    
    # Run port consistency check
    check_port_consistency || exit 1
    
    # Ensure server is running
    ensure_server_running || exit 1
    
    # Get server info
    get_server_info || exit 1
    
    # Run basic tests
    run_basic_tests || exit 1
    
    log "SUCCESS" "All verification steps completed successfully"
    echo
    echo "For detailed test results, check the log file: $LOG_FILE"
    return 0
}

# Run main function
main
