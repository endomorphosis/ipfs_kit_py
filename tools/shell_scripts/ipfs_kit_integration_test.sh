#!/bin/bash
# Simplified script to test IPFS kit integration

# Set default variables
RESULTS_DIR="test_results"
PORT=9997
HEALTH_ENDPOINT="http://localhost:${PORT}/health"
JSONRPC_ENDPOINT="http://localhost:${PORT}/jsonrpc"
SSE_ENDPOINT="http://localhost:${PORT}/sse"
LOG_FILE="ipfs_kit_test_$(date +%Y%m%d_%H%M%S).log"
SERVER_PID_FILE="mcp_server.pid"
SERVER_FILE="enhanced_final_mcp_server.py"

# Make sure results directory exists
mkdir -p "$RESULTS_DIR"

# Basic logging function
log() {
  local level=$1
  local message=$2
  local component=${3:-"MAIN"}
  
  local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
  echo "[$timestamp] [$level] [$component] $message"
  echo "[$timestamp] [$level] [$component] $message" >> "$LOG_FILE"
}

# Source external test functions if available
if [ -f "ipfs_daemon_functions.sh" ]; then
  source ipfs_daemon_functions.sh
  log "INFO" "Loaded IPFS daemon functions" "SETUP"
else
  log "WARNING" "ipfs_daemon_functions.sh not found, functionality will be limited" "SETUP"
fi

if [ -f "ipfs_kit_test_functions.sh" ]; then
  source ipfs_kit_test_functions.sh
  log "INFO" "Loaded IPFS kit test functions" "SETUP"
else
  log "WARNING" "ipfs_kit_test_functions.sh not found, functionality will be limited" "SETUP"
fi

# Main function
main() {
  log "INFO" "Starting IPFS Kit Integration Tests" "MAIN"
  
  # Check if IPFS daemon is running
  if type ensure_ipfs_daemon_running &>/dev/null; then
    ensure_ipfs_daemon_running || {
      log "ERROR" "Failed to ensure IPFS daemon is running" "MAIN"
      exit 1
    }
  else
    log "WARNING" "ensure_ipfs_daemon_running function not available" "MAIN"
    # Try simple check
    if ! pgrep -x "ipfs" > /dev/null; then
      log "ERROR" "IPFS daemon doesn't appear to be running" "MAIN"
      exit 1
    fi
  fi
  
  # Check if MCP server is running
  log "INFO" "Checking if MCP server is running..." "MAIN"
  if [ -f "$SERVER_PID_FILE" ]; then
    local pid=$(cat "$SERVER_PID_FILE")
    if ps -p "$pid" > /dev/null; then
      log "INFO" "MCP server is running with PID: $pid" "MAIN"
    else
      log "ERROR" "Server PID file exists but process is not running" "MAIN"
      exit 1
    fi
  else
    log "ERROR" "MCP server is not running. Please start it first." "MAIN"
    exit 1
  fi
  
  # Run IPFS kit integration test
  if type test_ipfs_kit_integration &>/dev/null; then
    log "INFO" "Running IPFS kit integration test..." "MAIN"
    test_ipfs_kit_integration || {
      log "ERROR" "IPFS kit integration test failed" "MAIN"
      exit 1
    }
  else
    log "ERROR" "test_ipfs_kit_integration function not available" "MAIN"
    exit 1
  fi
  
  # Verify tool coverage
  if type verify_ipfs_kit_tool_coverage &>/dev/null; then
    log "INFO" "Verifying IPFS kit tool coverage..." "MAIN"
    verify_ipfs_kit_tool_coverage || {
      log "WARNING" "IPFS kit tool coverage below threshold" "MAIN"
    }
  else
    log "WARNING" "verify_ipfs_kit_tool_coverage function not available" "MAIN"
  fi
  
  log "SUCCESS" "IPFS Kit Integration Tests completed" "MAIN"
}

# Run main function
main "$@"
exit 0
