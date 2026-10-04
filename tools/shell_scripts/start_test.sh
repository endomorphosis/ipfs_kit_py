#!/bin/bash
# Comprehensive MCP Server Testing Framework
# This script runs a series of tests to validate the MCP server implementation
# with specific focus on IPFS and VFS integration.

set -e

# Source IPFS daemon functions
if [ -f "ipfs_daemon_functions.sh" ]; then
  source ipfs_daemon_functions.sh
  log "INFO" "Loaded IPFS daemon functions" "SETUP"
else
  log "WARNING" "ipfs_daemon_functions.sh not found, some functionality may be limited" "SETUP"
fi

# Constants
SERVER_FILE="enhanced_final_mcp_server.py"
PORT=9997
LOG_FILE="mcp_test_$(date +%Y%m%d_%H%M%S).log"
RESULTS_DIR="test_results"
SERVER_PID_FILE="mcp_server.pid"
COVERAGE_FILE="${RESULTS_DIR}/coverage_$(date +%Y%m%d_%H%M%S).json"
SUMMARY_FILE="${RESULTS_DIR}/summary_$(date +%Y%m%d_%H%M%S).md"
DETAILED_TEST_REPORT="${RESULTS_DIR}/report_$(date +%Y%m%d_%H%M%S).md"
TEST_DATA_DIR="${RESULTS_DIR}/test_data"
HEALTH_ENDPOINT="http://localhost:${PORT}/health"
JSONRPC_ENDPOINT="http://localhost:${PORT}/jsonrpc"
SSE_ENDPOINT="http://localhost:${PORT}/sse"
TEST_TIMEOUT=30
MAX_START_RETRIES=5
IPFS_MAPPING_FILE="${RESULTS_DIR}/ipfs_to_mcp_mapping_$(date +%Y%m%d_%H%M%S).json"
IPFS_LOG_FILE="${RESULTS_DIR}/ipfs_daemon_$(date +%Y%m%d_%H%M%S).log"
DEPENDENCY_MAP_FILE="${RESULTS_DIR}/dependency_map_$(date +%Y%m%d_%H%M%S).json"
MCP_SERVER_VERSIONS=("enhanced_final_mcp_server.py" "direct_mcp_server_with_tools.py" "comprehensive_mcp_server.py")
CROSS_COMPATIBILITY_REPORT="${RESULTS_DIR}/cross_compatibility_$(date +%Y%m%d_%H%M%S).md"

# Colors for better readability
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Create results directory
mkdir -p "$RESULTS_DIR"

# Log function with optional sub-component and detailed levels
log() {
  local level=$1
  local message=$2
  local component=${3:-"MAIN"}
  local color=$NC
  local bold=""
  
  case $level in
    "INFO")
      color=$BLUE
      ;;
    "SUCCESS")
      color=$GREEN
      ;;
    "ERROR")
      color=$RED
      bold=$BOLD
      ;;
    "WARNING")
      color=$YELLOW
      ;;
    "DEBUG")
      color=$CYAN
      ;;
    "CRITICAL")
      color=$RED
      bold=$BOLD
      ;;
  esac
  
  local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
  echo -e "${bold}${color}[$timestamp] [$level] [$component] $message${NC}"
  echo "[$timestamp] [$level] [$component] $message" >> "$LOG_FILE"
}

# Function to check if a command exists
check_command() {
  local cmd=$1
  if ! command -v "$cmd" &> /dev/null; then
    log "ERROR" "Command $cmd not found. Please install it and try again."
    exit 1
  fi
}

# Function to check if required Python packages are installed
check_python_packages() {
  log "INFO" "Checking required Python packages..." "SETUP"
  
  local packages=("requests" "sseclient" "pytest" "aiohttp")
  local missing_packages=()
  
  for package in "${packages[@]}"; do
    if ! python3 -c "import $package" &> /dev/null; then
      missing_packages+=("$package")
    fi
  done
  
  if [ ${#missing_packages[@]} -gt 0 ]; then
    log "WARNING" "Missing Python packages: ${missing_packages[*]}" "SETUP"
    log "INFO" "Installing missing packages..." "SETUP"
    pip install "${missing_packages[@]}" || {
      log "ERROR" "Failed to install required packages" "SETUP"
      return 1
    }
  else
    log "SUCCESS" "All required Python packages are installed" "SETUP"
  fi
  
  return 0
}

# Function to check if the server is running
check_server_running() {
  if [ -f "$SERVER_PID_FILE" ]; then
    local pid=$(cat "$SERVER_PID_FILE")
    if ps -p "$pid" > /dev/null; then
      log "INFO" "MCP server is running with PID: $pid" "SERVER"
      # Check if it's responsive
      if curl -s "http://localhost:${PORT}/health" &>/dev/null; then
        log "SUCCESS" "MCP server is responsive" "SERVER" 
        return 0
      else
        log "WARNING" "MCP server process exists but is not responding to health checks" "SERVER"
        return 2
      fi
    else
      log "WARNING" "PID file exists but process is not running" "SERVER"
      return 1
    fi
  else
    log "WARNING" "MCP server is not running" "SERVER"
    return 1
  fi
}

# Function to start the server
start_server() {
  local max_retries=$MAX_SERVER_START_RETRIES
  local retry_count=0
  local started=false
  
  if check_server_running; then
    log "INFO" "Server is already running" "SERVER"
    return 0
  fi
  
  log "INFO" "Starting MCP server using $SERVER_FILE on port $PORT..." "SERVER"
  
  # Make sure log directories exist
  mkdir -p "$(dirname "final_mcp_server.log")"
  mkdir -p "$RESULTS_DIR"
  
  while [ $retry_count -lt $max_retries ] && [ "$started" = "false" ]; do
    # Start the server with debug logging
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local server_log="$RESULTS_DIR/mcp_server_${timestamp}.log"
    
    # Check if IPFS daemon is running - try to start it if not
    if ! pgrep -x "ipfs" > /dev/null; then
      log "WARNING" "IPFS daemon doesn't appear to be running, attempting to start it" "SERVER"
      ipfs daemon --init &
      sleep 5
    fi
    
    # Start the server with full output capture
    log "INFO" "Starting MCP server (attempt ${retry_count}/${max_retries})" "SERVER"
    python3 "$SERVER_FILE" --port "$PORT" --debug > "$server_log" 2>&1 &
    
    # Save the PID
    echo $! > "$SERVER_PID_FILE"
    log "INFO" "MCP server started with PID: $(cat $SERVER_PID_FILE)" "SERVER"
    
    # Wait for server to initialize
    log "INFO" "Waiting for server to initialize..." "SERVER"
    
    # More sophisticated wait approach with timeout
    local timeout=$TEST_TIMEOUT
    local elapsed=0
    local interval=1
    local health_ok=false
    local jsonrpc_ok=false
    
    # First wait for health endpoint
    while [ $elapsed -lt $timeout ] && [ "$health_ok" = "false" ]; do
      if curl -s "$SERVER_HEALTH_ENDPOINT" &>/dev/null; then
        health_ok=true
        log "INFO" "Health endpoint is responsive" "SERVER"
      else
        sleep $interval
        elapsed=$((elapsed + interval))
        if [ $((elapsed % 5)) -eq 0 ]; then
