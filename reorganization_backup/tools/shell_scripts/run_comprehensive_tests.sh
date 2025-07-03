#!/bin/bash

# Comprehensive test runner for IPFS MCP tools
# This script ensures all required tools are registered before running tests

# Setup colors and logging
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BLUE='\033[0;34m'
CYAN='\033[0;36m'

log() {
  local level=$1
  local message=$2
  local color=$GREEN
  
  case $level in
    "INFO") color=$BLUE ;;
    "WARNING") color=$YELLOW ;;
    "ERROR") color=$RED ;;
    "SUCCESS") color=$GREEN ;;
    *) color=$CYAN ;;
  esac
  
  echo -e "${color}[$level]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $message"
}

cleanup() {
  log "INFO" "Cleaning up processes..."
  
  # Kill any running MCP server
  if [ -f "direct_mcp_server.pid" ]; then
    PID=$(cat direct_mcp_server.pid)
    log "INFO" "Stopping MCP server (PID: $PID)..."
    kill -15 $PID 2>/dev/null || true
    rm -f direct_mcp_server.pid
  fi
}

# Set up trap to clean up on exit
trap cleanup EXIT

# Start the MCP server
start_mcp_server() {
  log "INFO" "Starting MCP server..."
  nohup python3 direct_mcp_server.py --port 9998 > direct_mcp_server.log 2>&1 &
  
  # Save PID for later cleanup
  echo $! > direct_mcp_server.pid
  
  # Wait for server to start
  log "INFO" "Waiting for MCP server to be ready..."
  max_attempts=30
  attempt=0
  
  while [ $attempt -lt $max_attempts ]; do
    attempt=$((attempt + 1))
    
    # Check if server is up by checking health endpoint
    if curl -s http://localhost:9998/health > /dev/null; then
      log "SUCCESS" "MCP server is ready (attempts: $attempt)"
      return 0
    fi
    
    log "INFO" "Waiting for server... (attempt $attempt/$max_attempts)"
    sleep 1
  done
  
  log "ERROR" "MCP server did not start in time"
  return 1
}

# Run diagnostics to check tool availability
run_diagnostics() {
  log "INFO" "Running diagnostics to identify missing tools..."
  python3 diagnose_mcp_tools.py
  
  if [ $? -ne 0 ]; then
    log "WARNING" "Diagnostics identified issues with MCP tools"
  else
    log "SUCCESS" "Diagnostics completed successfully"
  fi
}

# Register missing tools
register_missing_tools() {
  log "INFO" "Registering any missing IPFS tools..."
  python3 register_ipfs_tools_directly.py
  
  if [ $? -ne 0 ]; then
    log "WARNING" "Failed to register all missing tools"
    log "INFO" "Trying alternative registration method..."
    python3 quick_fix_tool_registration.py
  else
    log "SUCCESS" "Successfully registered missing tools"
  fi
}

# Run the tests
run_tests() {
  log "INFO" "Running MCP IPFS tools tests..."
  python3 -m pytest test_ipfs_mcp_tools.py -v
  
  TEST_EXIT_CODE=$?
  
  if [ $TEST_EXIT_CODE -eq 0 ]; then
    log "SUCCESS" "All tests passed successfully"
  else
    log "ERROR" "Tests failed with exit code $TEST_EXIT_CODE"
  fi
  
  return $TEST_EXIT_CODE
}

# Main execution flow
main() {
  log "INFO" "Starting comprehensive test suite for IPFS MCP tools"
  
  # Start the MCP server
  start_mcp_server || { log "ERROR" "Failed to start MCP server"; exit 1; }
  
  # Give server a bit more time to initialize
  sleep 2
  
  # Run diagnostics
  run_diagnostics
  
  # Register missing tools
  register_missing_tools
  
  # Run the tests
  run_tests
  test_result=$?
  
  log "INFO" "Test execution completed"
  return $test_result
}

# Run main function
main
exit $?
