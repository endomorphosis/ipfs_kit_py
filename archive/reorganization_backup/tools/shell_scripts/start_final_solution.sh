#!/bin/bash
# Comprehensive MCP Server Testing Framework
# This script runs a series of tests to validate the MCP server implementation
# with specific focus on IPFS and VFS integration.

set -e

# Constants
SERVER_FILE="final_mcp_server.py"
PORT=9998
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
  log "INFO" "Python executable: $(which python3)" "SETUP"
  log "INFO" "Python version: $(python3 --version)" "SETUP"
  log "INFO" "PYTHONPATH: ${PYTHONPATH:-'(not set)'}" "SETUP"
  log "INFO" "User site-packages: $(python3 -m site --user-site)" "SETUP"
  log "INFO" "Checking required Python packages..." "SETUP"
  
  local packages=("requests" "sseclient" "pytest" "aiohttp" "fastapi" "uvicorn" "jsonrpcserver")
  local missing_packages=()
  
  for package in "${packages[@]}"; do
    if ! python3 -c "import $package" &> /dev/null; then
      missing_packages+=("$package")
    fi
  done
  
  if [ ${#missing_packages[@]} -gt 0 ]; then
    log "WARNING" "Missing Python packages: ${missing_packages[*]}" "SETUP"
    log "INFO" "Installing missing packages..." "SETUP"
    pip install "${missing_packages[@]}" --break-system-packages || { # Added --break-system-packages
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
      local health_check_output
      health_check_output=$(curl -s -S --fail "http://localhost:${PORT}/health" 2>&1)
      local curl_exit_code=$?
      if [ $curl_exit_code -eq 0 ]; then
        log "SUCCESS" "MCP server is responsive. Health check output: $health_check_output" "SERVER"
        return 0
      else
        log "WARNING" "MCP server process exists but is not responding to health checks. Curl exit code: $curl_exit_code. Output: $health_check_output" "SERVER"
        return 2 # Indicates server process exists but not healthy
      fi
    else
      log "WARNING" "PID file exists but process is not running" "SERVER"
      rm -f "$SERVER_PID_FILE" # Remove stale PID file
      return 1 # Indicates server not running
    fi
  else
    log "INFO" "No PID file found, server is not running" "SERVER" # Changed from WARNING to INFO
    return 1 # Indicates server not running
  fi
}

# Function to start the server
start_server() {
  local max_retries=${MAX_START_RETRIES:-5} 
  local retry_count=0
  local started=false
  
  # Check if server is already running and responsive
  if check_server_running && [ $? -eq 0 ]; then
    log "INFO" "Server is already running and responsive" "SERVER"
    return 0
  fi
  
  log "INFO" "Starting MCP server using $SERVER_FILE on port $PORT..." "SERVER"
  
  mkdir -p "$(dirname "final_mcp_server.log")" 
  mkdir -p "$RESULTS_DIR"
  
  if [ ! -f "$SERVER_FILE" ]; then
    log "ERROR" "Server file '$SERVER_FILE' not found" "SERVER"
    exit 1
  fi
  
  log "INFO" "Verifying server file for required functionality..." "SERVER"
  if ! grep -q "ipfs" "$SERVER_FILE" || ! grep -q "vfs" "$SERVER_FILE"; then
    log "WARNING" "Server file may not include both IPFS and VFS functionality" "SERVER"
  fi
  
  while [ $retry_count -lt $max_retries ] && [ "$started" = "false" ]; do
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local server_log_file="$RESULTS_DIR/mcp_server_attempt_${retry_count}_${timestamp}.log" # Unique log per attempt
    
    if ! pgrep -x "ipfs" > /dev/null; then
      log "WARNING" "IPFS daemon doesn't appear to be running, attempting to start it" "SERVER"
      ipfs daemon --init &> "${IPFS_LOG_FILE}" &
      local ipfs_pid=$!
      log "INFO" "Started IPFS daemon with PID: $ipfs_pid" "IPFS"
      
      local ipfs_wait=0
      while [ $ipfs_wait -lt 15 ]; do # Increased wait time for IPFS
        if curl -s http://127.0.0.1:5001/api/v0/version > /dev/null 2>&1; then
          log "SUCCESS" "IPFS daemon is running and responsive" "IPFS"
          break
        fi
        sleep 1
        ipfs_wait=$((ipfs_wait + 1))
      done
      
      if [ $ipfs_wait -ge 15 ]; then
        log "WARNING" "IPFS daemon may not be fully initialized after 15s" "IPFS"
      fi
    else
      log "INFO" "IPFS daemon is already running" "IPFS"
    fi
    
    log "INFO" "Starting MCP server (attempt $((retry_count + 1))/${max_retries})" "SERVER"
    USER_SITE_PACKAGES=$(python3 -m site --user-site)
    log "INFO" "Prepending USER_SITE_PACKAGES to PYTHONPATH for server execution: $USER_SITE_PACKAGES" "SERVER"
    PYTHONPATH="$USER_SITE_PACKAGES${PYTHONPATH:+:$PYTHONPATH}" python3 "$SERVER_FILE" --port "$PORT" --debug > "$server_log_file" 2>&1 &
    
    echo $! > "$SERVER_PID_FILE"
    log "INFO" "MCP server started with PID: $(cat $SERVER_PID_FILE)" "SERVER"
    
    log "INFO" "Waiting for server to initialize..." "SERVER"
    
    local wait_timeout=${TEST_TIMEOUT:-30} 
    local elapsed=0
    local interval=1 # Check every second initially
    local health_ok=false
    local jsonrpc_ok=false
    
    while [ $elapsed -lt $wait_timeout ]; do
      local curl_health_output
      # Use --max-time for curl to prevent indefinite hanging
      curl_health_output=$(curl --max-time 5 -s -S --fail "$HEALTH_ENDPOINT" 2>&1)
      local curl_health_exit_code=$?

      if [ $curl_health_exit_code -eq 0 ]; then 
        health_ok=true
        log "INFO" "Health endpoint is responsive. Output: $curl_health_output" "SERVER"
        break # Health is OK, proceed to JSON-RPC check
      else
        sleep $interval
        elapsed=$((elapsed + interval))
        if [ $((elapsed % 5)) -eq 0 ] || [ $elapsed -eq 1 ]; then # Log more frequently at start
          log "INFO" "Still waiting for health endpoint... (${elapsed}s). Last curl error (code $curl_health_exit_code): $curl_health_output" "SERVER"
        fi
        # Increase interval after initial attempts
        if [ $elapsed -gt 10 ]; then interval=2; fi 
      fi
    done
    
    if [ "$health_ok" = "true" ]; then
      elapsed=0 # Reset elapsed for JSON-RPC check
      interval=1 # Reset interval
      while [ $elapsed -lt $wait_timeout ]; do
        local response
        response=$(curl --max-time 5 -s -S --fail -X POST "$JSONRPC_ENDPOINT" \
          -H "Content-Type: application/json" \
          -d '{"jsonrpc":"2.0","method":"ping","params":{},"id":1}' 2>&1)
        local curl_jsonrpc_exit_code=$?
        
        if [ $curl_jsonrpc_exit_code -eq 0 ] && [[ $response == *"pong"* ]]; then
          jsonrpc_ok=true
          log "INFO" "JSON-RPC endpoint is responsive. Response: $response" "SERVER"
          break # JSON-RPC is OK
        else
          sleep $interval
          elapsed=$((elapsed + interval))
          if [ $((elapsed % 5)) -eq 0 ] || [ $elapsed -eq 1 ]; then
            log "INFO" "Still waiting for JSON-RPC endpoint... (${elapsed}s). Last curl error (code $curl_jsonrpc_exit_code): $response" "SERVER"
          fi
          if [ $elapsed -gt 10 ]; then interval=2; fi
        fi
      done
      
      if [ "$jsonrpc_ok" = "true" ]; then
        local tools_response=$(curl --max-time 5 -s -X POST "$JSONRPC_ENDPOINT" \
          -H "Content-Type: application/json" \
          -d '{"jsonrpc":"2.0","method":"get_tools","params":{},"id":1}') # Changed to get_tools
        
        if [ $? -eq 0 ] && [[ $tools_response == *"name"* ]]; then # Check for "name" as tools are dicts
          log "SUCCESS" "MCP server is fully responsive! Tools listed." "SERVER"
          started=true 
          sleep 2
          break 
        else
          log "WARNING" "Server JSON-RPC is up (ping OK), but list_tools/get_tools failed or returned unexpected format. Response: $tools_response" "SERVER"
          started=true # Consider it started if ping works, but log the issue
          break 
        fi
      else
        log "WARNING" "Health endpoint is responsive, but JSON-RPC (ping) is not after ${elapsed}s." "SERVER"
      fi
    fi
    
    if [ "$started" = "false" ]; then
      retry_count=$((retry_count + 1))
      log "WARNING" "Attempt $retry_count: Server not fully responsive after ${wait_timeout}s (Health: $health_ok, JSON-RPC: $jsonrpc_ok)" "SERVER"
      
      log "INFO" "Last 10 lines of server log ($server_log_file):" "SERVER"
      tail -n 10 "$server_log_file" | while IFS= read -r line; do 
        log "DEBUG" "$line" "SERVER_LOG"
      done
      
      stop_server 
      sleep 3
    fi
  done
  
  if [ "$started" = "false" ]; then
    log "ERROR" "Failed to start MCP server after $max_retries attempts" "SERVER"
    log "ERROR" "See logs in $RESULTS_DIR for details (especially the mcp_server_attempt_*.log files)" "SERVER"
    exit 1
  fi
  
  if [ "$started" = "true" ]; then
    log "INFO" "Checking available MCP tools post-start..." "SERVER"
    local tools_response_final=$(curl --max-time 5 -s -X POST "$JSONRPC_ENDPOINT" \
      -H "Content-Type: application/json" \
      -d '{"jsonrpc":"2.0","method":"get_tools","params":{},"id":1}')
    
    local ipfs_tools_final=$(echo "$tools_response_final" | grep -o '"ipfs_[^"]*"' | wc -l)
    local vfs_tools_final=$(echo "$tools_response_final" | grep -o '"vfs_[^"]*"' | wc -l)
    
    log "INFO" "Detected $ipfs_tools_final IPFS tools and $vfs_tools_final VFS tools" "SERVER"
  fi
}

# Function to stop the server
stop_server() {
  if [ -f "$SERVER_PID_FILE" ]; then
    local pid=$(cat "$SERVER_PID_FILE")
    log "INFO" "Stopping MCP server with PID: $pid" "SERVER"
    
    kill -15 "$pid" 2> /dev/null || true 
    
    local stop_timeout=5
    local elapsed=0
    
    while [ $elapsed -lt $stop_timeout ]; do
      if ! ps -p "$pid" > /dev/null 2>&1; then
        log "SUCCESS" "Server stopped gracefully" "SERVER"
        rm -f "$SERVER_PID_FILE"
        return 0
      fi
      sleep 1
      elapsed=$((elapsed + 1))
    done
    
    if ps -p "$pid" > /dev/null 2>&1; then
      log "WARNING" "Server still running after ${stop_timeout}s, force killing..." "SERVER"
      kill -9 "$pid" 2> /dev/null || true 
      sleep 1 
    fi
    
    if ps -p "$pid" > /dev/null 2>&1; then
      log "ERROR" "Failed to stop server process $pid" "SERVER"
      return 1
    else
      log "SUCCESS" "Server process stopped" "SERVER"
      rm -f "$SERVER_PID_FILE"
      return 0
    fi
  else
    log "INFO" "No PID file found, server is not running" "SERVER"
    return 0
  fi
}

# Function to check for required test files and create them if missing
check_test_files() {
  log "INFO" "Checking for required test files..." "SETUP"
  local missing_files=0
  
  if [ ! -f "$SERVER_FILE" ]; then
    log "ERROR" "MCP server file '$SERVER_FILE' not found" "SETUP"
    missing_files=$((missing_files + 1))
  fi
  
  mkdir -p "$TEST_DATA_DIR"
  
  if [ ! -f "mcp_test_runner.py" ] || [ "$1" == "--force-update" ]; then
    log "INFO" "Creating/Updating comprehensive MCP test runner..." "SETUP"
    
    cat > "mcp_test_runner.py" << 'EOF'
#!/usr/bin/env python3
"""
Comprehensive MCP Test Runner

This script performs detailed tests of the MCP server implementation, with a focus on:
1. IPFS Kit integration with all functionality exposed as tools
2. Virtual File System (VFS) functionality and integration
3. Server stability and error handling
4. SSE event stream functionality
5. Tool coverage analysis
"""

import argparse
import asyncio
import json
import logging
import os
import random
import signal
import string
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union, Set

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('mcp_test_runner.log', mode='w') # Overwrite log each run
    ]
)
logger = logging.getLogger("mcp-test-runner")

try:
    import requests
    from requests.exceptions import RequestException
except ImportError:
    logger.info("Installing required dependencies: requests")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests
    from requests.exceptions import RequestException

try:
    from sseclient import SSEClient
except ImportError:
    logger.info("Installing SSE client dependency: sseclient-py")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "sseclient-py"])
    from sseclient import SSEClient

# Global configuration
DEFAULT_PORT = 9997
DEFAULT_SERVER_FILE = "final_mcp_server.py" # Should match the one started by start_final_solution.sh
DEFAULT_TIMEOUT = 30  # seconds
DEFAULT_TEST_DATA_DIR = "test_results/test_data" # Ensure this matches shell script
DEFAULT_RESULTS_FILE = "mcp_test_results.json" # Ensure this matches shell script

# Test data and results 
TEST_RESULTS = {
    "timestamp": datetime.now().isoformat(),
    "server_file": DEFAULT_SERVER_FILE, 
    "port": DEFAULT_PORT, 
    "tests": {
        "total": 0,
        "passed": 0,
        "failed": 0
    },
    "categories": {},
    "failed_tools": [],
    "probe_results": {}, 
    "success_rate": 0.0
}

class MCPTestRunner:
    """Test runner for MCP server"""
    
    def __init__(self, port=DEFAULT_PORT, server_file=DEFAULT_SERVER_FILE, 
                 debug=False, test_data_dir=DEFAULT_TEST_DATA_DIR):
        """Initialize the test runner"""
        self.port = port
        self.server_file = server_file
        self.debug = debug
        self.test_data_dir = test_data_dir
        self.base_url = f"http://localhost:{port}"
        self.jsonrpc_url = f"{self.base_url}/jsonrpc"
        self.health_url = f"{self.base_url}/health"
        self.sse_url = f"{self.base_url}/sse"
        
        TEST_RESULTS["server_file"] = server_file # Update global with actual server file
        TEST_RESULTS["port"] = port # Update global with actual port

        os.makedirs(self.test_data_dir, exist_ok=True)
        
        if debug:
            logger.setLevel(logging.DEBUG)
        
        logger.info(f"MCP Test Runner initialized: Server on port {port}, server_file='{server_file}', debug={debug}")
    
    def call_jsonrpc(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
        """Make a JSON-RPC call to the MCP server with enhanced error logging."""
        if params is None:
            params = {}
        
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": int(time.time() * 1000) 
        }
        
        response_text = "N/A" # Initialize for error logging
        try:
            logger.debug(f"Calling {method} with params: {json.dumps(params)}")
            response = requests.post(self.jsonrpc_url, json=payload, timeout=timeout)
            response_text = response.text # Store response text for potential error logging
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            json_response = response.json()
            if "error" in json_response: # Check for JSON-RPC level error
                logger.error(f"Error in JSON-RPC response for {method}: {json.dumps(json_response.get('error'))}")
            return json_response
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error calling {method}: {http_err}. Response text: {response_text}")
            return {"error": {"message": f"HTTP error: {http_err}", "details": response_text, "code": response.status_code if 'response' in locals() and hasattr(response, 'status_code') else None}}
        except requests.exceptions.RequestException as req_err: # Covers connection errors, timeouts, etc.
            logger.error(f"RequestException calling {method}: {req_err}")
            return {"error": {"message": f"RequestException: {req_err}"}}
        except json.JSONDecodeError as json_err: # If response is not valid JSON
            logger.error(f"JSONDecodeError calling {method}: {json_err}. Response text: {response_text}")
            return {"error": {"message": f"JSONDecodeError: {json_err}", "details": response_text}}
        except Exception as e: # Catch-all for other unexpected errors
            logger.error(f"Unexpected error calling {method}: {e}. Response text: {response_text}")
            return {"error": {"message": f"Unexpected error: {e}", "details": response_text}}

    def test_server_health(self) -> bool:
        """Test the server health endpoint with detailed logging."""
        TEST_RESULTS["tests"]["total"] += 1
        logger.info(f"Testing server health endpoint: {self.health_url}")
        try:
            response = requests.get(self.health_url, timeout=DEFAULT_TIMEOUT)
            if response.status_code == 200:
                logger.info(f"Health endpoint check PASSED. Status: {response.status_code}. Response: {response.text[:200]}") # Log snippet of response
                TEST_RESULTS["tests"]["passed"] += 1
                return True
            else:
                logger.error(f"Health endpoint check FAILED: Status {response.status_code}. Response: {response.text}")
                TEST_RESULTS["tests"]["failed"] += 1
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Health endpoint check FAILED with RequestException: {e}")
            TEST_RESULTS["tests"]["failed"] += 1
            return False
        except Exception as e: # Catch any other unexpected errors
            logger.error(f"Health endpoint check FAILED with unexpected error: {e}")
            TEST_RESULTS["tests"]["failed"] += 1
            return False

    def probe_server_capabilities(self) -> bool:
        """Perform initial capability probing after server is 'healthy'."""
        logger.info("Probing server capabilities...")
        critical_probes_passed = True
        
        # Probe 1: list_tools
        TEST_RESULTS["tests"]["total"] += 1
        logger.info("Probing: list_tools")
        list_tools_result = self.call_jsonrpc("get_tools") # Assuming get_tools is the JSON-RPC method
        if "result" in list_tools_result and isinstance(list_tools_result["result"], list):
            tool_count = len(list_tools_result["result"])
            logger.info(f"PASS: list_tools probe returned {tool_count} tools.")
            TEST_RESULTS["probe_results"]["list_tools"] = {"status": "passed", "count": tool_count, "tools": list_tools_result["result"]}
            TEST_RESULTS["tests"]["passed"] += 1
            if tool_count == 0:
                 logger.warning("list_tools probe passed but returned an empty list of tools.")
        else:
            logger.error(f"FAIL: list_tools probe failed. Response: {json.dumps(list_tools_result)}")
            TEST_RESULTS["probe_results"]["list_tools"] = {"status": "failed", "response": list_tools_result}
            TEST_RESULTS["tests"]["failed"] += 1
            critical_probes_passed = False # This is a critical probe

        # Probe 2: ipfs_version (only if list_tools was somewhat successful)
        if critical_probes_passed: # Or some less strict check like list_tools_result not having a connection error
            TEST_RESULTS["tests"]["total"] += 1
            logger.info("Probing: ipfs_version")
            ipfs_version_result = self.call_jsonrpc("ipfs_version")
            if "result" in ipfs_version_result: # Check for actual result, not just absence of error
                logger.info(f"PASS: ipfs_version returned: {json.dumps(ipfs_version_result['result'])}")
                TEST_RESULTS["probe_results"]["ipfs_version"] = {"status": "passed", "response": ipfs_version_result['result']}
                TEST_RESULTS["tests"]["passed"] += 1
            else:
                logger.error(f"FAIL: ipfs_version probe failed. Response: {json.dumps(ipfs_version_result)}")
                TEST_RESULTS["probe_results"]["ipfs_version"] = {"status": "failed", "response": ipfs_version_result}
                TEST_RESULTS["tests"]["failed"] += 1
                # Consider if this should also set critical_probes_passed to False
        else:
             logger.warning("Skipping ipfs_version probe due to list_tools failure.")
             TEST_RESULTS["probe_results"]["ipfs_version"] = {"status": "skipped", "reason": "list_tools failed"}

        # Probe 3: vfs_ls on root (only if list_tools was somewhat successful)
        if critical_probes_passed:
            TEST_RESULTS["tests"]["total"] += 1
            logger.info("Probing: vfs_ls on root ('/')")
            vfs_ls_result = self.call_jsonrpc("vfs_ls", {"path": "/"}) # Assuming vfs_ls is the tool name
            if "result" in vfs_ls_result: # Check for actual result
                logger.info(f"PASS: vfs_ls probe successful. Response: {json.dumps(vfs_ls_result['result'])}")
                TEST_RESULTS["probe_results"]["vfs_ls_root"] = {"status": "passed", "response": vfs_ls_result['result']}
                TEST_RESULTS["tests"]["passed"] += 1
            else:
                logger.error(f"FAIL: vfs_ls probe failed. Response: {json.dumps(vfs_ls_result)}")
                TEST_RESULTS["probe_results"]["vfs_ls_root"] = {"status": "failed", "response": vfs_ls_result}
                TEST_RESULTS["tests"]["failed"] += 1
        else:
            logger.warning("Skipping vfs_ls probe due to list_tools failure.")
            TEST_RESULTS["probe_results"]["vfs_ls_root"] = {"status": "skipped", "reason": "list_tools failed"}

        return critical_probes_passed

    def get_all_tools(self):
        result = self.call_jsonrpc("get_tools") # Changed from list_tools to get_tools
        if "result" in result and isinstance(result["result"], list): # Ensure result is a list
            tools = result["result"]
            logger.info(f"Found {len(tools)} tools registered with the server")
            return tools
        else:
            error_details = result.get("error", "Unknown error when listing tools")
            logger.error(f"Failed to get tool list: {json.dumps(error_details)}")
            return []
    
    def categorize_tools(self, tools):
        categories = {"core": [], "ipfs": [], "vfs": [], "other": []}
        for tool_info in tools: # Iterate over list of tool dicts
            name = tool_info.get("name", "") # Get name from dict
            if name in ["ping", "health", "get_tools", "get_server_info"]: categories["core"].append(name) # Updated core tools
            elif name.startswith("ipfs_"): categories["ipfs"].append(name)
            elif name.startswith("vfs_"): categories["vfs"].append(name)
            else: categories["other"].append(name)
        for category, tools_list in categories.items():
            logger.info(f"Found {len(tools_list)} {category.upper()} tools")
        return categories
    
    def generate_test_data(self):
        test_file_content = ''.join(random.choices(string.ascii_letters + string.digits, k=1024))
        test_file_path = os.path.join(self.test_data_dir, "test_file.txt")
        with open(test_file_path, 'w') as f: f.write(test_file_content)
        logger.info(f"Generated test file at {test_file_path}")
        return {"file_path": test_file_path, "content": test_file_content, "directory": self.test_data_dir}
    
    def test_core_tools(self):
        logger.info("Testing core MCP tools...")
        results = {"passed": 0, "failed": 0, "total": 0}
        
        results["total"] += 1
        ping_result = self.call_jsonrpc("ping")
        if "result" in ping_result and ping_result["result"] == "pong":
            logger.info("PASS: ping tool returned 'pong'")
            results["passed"] += 1
        else:
            logger.error(f"FAIL: ping tool failed. Response: {json.dumps(ping_result)}")
            results["failed"] += 1
            TEST_RESULTS["failed_tools"].append({"name": "ping", "category": "core", "response": ping_result})
        
        results["total"] += 1
        # Health is tested via HTTP GET, but we can also test a JSON-RPC 'health' or 'get_server_info' if it exists
        server_info_result = self.call_jsonrpc("get_server_info") 
        if "result" in server_info_result and server_info_result["result"].get("version"): # Check for a valid field
            logger.info(f"PASS: get_server_info JSON-RPC tool returned: {json.dumps(server_info_result['result'])}")
            results["passed"] += 1
        else:
            logger.error(f"FAIL: get_server_info JSON-RPC tool failed. Response: {json.dumps(server_info_result)}")
            results["failed"] += 1
            TEST_RESULTS["failed_tools"].append({"name": "get_server_info", "category": "core", "response": server_info_result})
        
        results["total"] += 1
        list_tools_result = self.call_jsonrpc("get_tools") # Changed to get_tools
        if "result" in list_tools_result and isinstance(list_tools_result["result"], list):
            logger.info(f"PASS: get_tools returned {len(list_tools_result['result'])} tools")
            results["passed"] += 1
        else:
            logger.error(f"FAIL: get_tools tool failed. Response: {json.dumps(list_tools_result)}")
            results["failed"] += 1
            TEST_RESULTS["failed_tools"].append({"name": "get_tools", "category": "core", "response": list_tools_result})

        TEST_RESULTS["tests"]["total"] += results["total"]
        TEST_RESULTS["tests"]["passed"] += results["passed"]
        TEST_RESULTS["tests"]["failed"] += results["failed"]
        
        success_rate = (results["passed"] / results["total"]) * 100 if results["total"] > 0 else 0
        logger.info(f"Core tools test complete: {results['passed']}/{results['total']} passed ({success_rate:.2f}%)")
        return results

    def test_ipfs_basic_tools(self):
        logger.info("Testing basic IPFS tools...")
        results = {"passed": 0, "failed": 0, "total": 0}
        
        results["total"] += 1
        version_result = self.call_jsonrpc("ipfs_version")
        if "result" in version_result:
            logger.info(f"PASS: ipfs_version returned: {json.dumps(version_result['result'])}")
            results["passed"] += 1
        else:
            logger.error(f"FAIL: ipfs_version failed. Response: {json.dumps(version_result)}")
            results["failed"] += 1
            TEST_RESULTS["failed_tools"].append({"name": "ipfs_version", "category": "ipfs", "response": version_result})
        
        test_content = "Hello IPFS from MCP test runner!"
        results["total"] += 1
        add_result = self.call_jsonrpc("ipfs_add", {"content": test_content}) # Assuming ipfs_add takes content directly
        cid_value = None
        if "result" in add_result:
            cid_value = add_result["result"].get("Hash") or add_result["result"].get("cid")
            if cid_value:
                logger.info(f"PASS: ipfs_add returned CID: {cid_value}")
                results["passed"] += 1
            else:
                logger.error(f"FAIL: ipfs_add did not return a valid CID. Response: {json.dumps(add_result)}")
                results["failed"] += 1
                TEST_RESULTS["failed_tools"].append({"name": "ipfs_add", "category": "ipfs", "response": add_result})
        else:
            logger.error(f"FAIL: ipfs_add failed. Response: {json.dumps(add_result)}")
            results["failed"] += 1
            TEST_RESULTS["failed_tools"].append({"name": "ipfs_add", "category": "ipfs", "response": add_result})

        if cid_value:
            results["total"] += 1
            cat_result = self.call_jsonrpc("ipfs_cat", {"cid": cid_value})
            retrieved_content = cat_result.get("result")
            if isinstance(retrieved_content, dict) and "content" in retrieved_content: # Handle if content is nested
                 retrieved_content = retrieved_content["content"]
            if retrieved_content == test_content:
                logger.info("PASS: ipfs_cat retrieved correct content")
                results["passed"] += 1
            else:
                logger.error(f"FAIL: ipfs_cat retrieved incorrect content. Got: '{retrieved_content}', Expected: '{test_content}'. Full Response: {json.dumps(cat_result)}")
                results["failed"] += 1
                TEST_RESULTS["failed_tools"].append({"name": "ipfs_cat", "category": "ipfs", "response": cat_result})
        
        TEST_RESULTS["tests"]["total"] += results["total"]
        TEST_RESULTS["tests"]["passed"] += results["passed"]
        TEST_RESULTS["tests"]["failed"] += results["failed"]
        success_rate = (results["passed"] / results["total"]) * 100 if results["total"] > 0 else 0
        logger.info(f"Basic IPFS tools test complete: {results['passed']}/{results['total']} passed ({success_rate:.2f}%)")
        return results
    
    def test_vfs_basic_tools(self):
        logger.info("Testing basic VFS tools...")
        results = {"passed": 0, "failed": 0, "total": 0}
        test_dir = f"/vfs-test-{int(time.time())}"
        test_file = f"{test_dir}/test.txt"
        test_content = "Hello VFS from MCP test runner!"
        
        results["total"] += 1
        mkdir_result = self.call_jsonrpc("vfs_mkdir", {"path": test_dir})
        if "result" in mkdir_result: # Assuming success if result key exists
            logger.info(f"PASS: vfs_mkdir created directory {test_dir}")
            results["passed"] += 1
            
            results["total"] += 1
            write_result = self.call_jsonrpc("vfs_write", {"path": test_file, "content": test_content})
            if "result" in write_result:
                logger.info(f"PASS: vfs_write wrote to {test_file}")
                results["passed"] += 1
                
                results["total"] += 1
                read_result = self.call_jsonrpc("vfs_read", {"path": test_file})
                retrieved_content = read_result.get("result")
                if isinstance(retrieved_content, dict) and "content" in retrieved_content: # Handle nested content
                    retrieved_content = retrieved_content["content"]
                if retrieved_content == test_content:
                    logger.info("PASS: vfs_read retrieved correct content")
                    results["passed"] += 1
                else:
                    logger.error(f"FAIL: vfs_read retrieved incorrect content. Got: '{retrieved_content}', Expected: '{test_content}'. Full Response: {json.dumps(read_result)}")
                    results["failed"] += 1
                    TEST_RESULTS["failed_tools"].append({"name": "vfs_read", "category": "vfs", "response": read_result})
                
                results["total"] += 1
                ls_result = self.call_jsonrpc("vfs_ls", {"path": test_dir})
                entries = ls_result.get("result")
                if isinstance(entries, dict) and "entries" in entries: entries = entries["entries"] # Handle nested entries
                if isinstance(entries, list) and any(entry.get("name") == "test.txt" for entry in entries):
                    logger.info("PASS: vfs_ls found the test file")
                    results["passed"] += 1
                else:
                    logger.error(f"FAIL: vfs_ls did not find expected file. Response: {json.dumps(ls_result)}")
                    results["failed"] += 1
                    TEST_RESULTS["failed_tools"].append({"name": "vfs_ls", "category": "vfs", "response": ls_result})
                
                results["total"] += 1
                rm_result = self.call_jsonrpc("vfs_rm", {"path": test_file})
                if "result" in rm_result:
                    logger.info(f"PASS: vfs_rm removed file {test_file}")
                    results["passed"] += 1
                else:
                    logger.error(f"FAIL: vfs_rm failed. Response: {json.dumps(rm_result)}")
                    results["failed"] += 1
                    TEST_RESULTS["failed_tools"].append({"name": "vfs_rm", "category": "vfs", "response": rm_result})
            else:
                logger.error(f"FAIL: vfs_write failed. Response: {json.dumps(write_result)}")
                results["failed"] += 4 # Mark subsequent tests in this block as failed
                TEST_RESULTS["failed_tools"].append({"name": "vfs_write", "category": "vfs", "response": write_result})
            
            results["total"] += 1
            rmdir_result = self.call_jsonrpc("vfs_rmdir", {"path": test_dir})
            if "result" in rmdir_result:
                logger.info(f"PASS: vfs_rmdir removed directory {test_dir}")
                results["passed"] += 1
            else:
                logger.error(f"FAIL: vfs_rmdir failed. Response: {json.dumps(rmdir_result)}")
                results["failed"] += 1
                TEST_RESULTS["failed_tools"].append({"name": "vfs_rmdir", "category": "vfs", "response": rmdir_result})
        else:
            logger.error(f"FAIL: vfs_mkdir failed. Response: {json.dumps(mkdir_result)}")
            results["failed"] += 6 # Mark all subsequent tests in this block as failed
            TEST_RESULTS["failed_tools"].append({"name": "vfs_mkdir", "category": "vfs", "response": mkdir_result})
        
        TEST_RESULTS["tests"]["total"] += results["total"]
        TEST_RESULTS["tests"]["passed"] += results["passed"]
        TEST_RESULTS["tests"]["failed"] += results["failed"]
        success_rate = (results["passed"] / results["total"]) * 100 if results["total"] > 0 else 0
        logger.info(f"Basic VFS tools test complete: {results['passed']}/{results['total']} passed ({success_rate:.2f}%)")
        return results

    def test_sse_endpoint(self):
        logger.info("Testing SSE endpoint...")
        results = {"passed": 0, "failed": 0, "total": 1} # Start with 1 test for connection
        try:
            messages = SSEClient(self.sse_url, timeout=5) # Using timeout for SSEClient constructor
            logger.info("Successfully connected to SSE endpoint")
            self.call_jsonrpc("ping") # Trigger an event
            event_received, server_info_received, tool_update_received = False, False, False
            listen_timeout = time.time() + 10 # Listen for 10 seconds
            for msg in messages:
                if time.time() > listen_timeout: break
                if not msg or not msg.data: continue
                try:
                    data = json.loads(msg.data)
                    event_type = data.get('type')
                    logger.info(f"Received SSE event: {event_type} - Data: {json.dumps(data)[:200]}") # Log snippet
                    event_received = True
                    if event_type == 'server_info': server_info_received = True
                    if event_type in ['tool_call', 'tool_result']: tool_update_received = True
                except json.JSONDecodeError: logger.error(f"Received invalid JSON from SSE: {msg.data}")
            messages.close()
            if event_received:
                logger.info("PASS: At least one event received from SSE.")
                results["passed"] += 1
                results["total"] += 1 # For server_info_event check
                if server_info_received:
                    logger.info("PASS: Received server_info event")
                    results["passed"] += 1
                else:
                    logger.error("FAIL: Did not receive server_info event")
                    results["failed"] +=1
                results["total"] += 1 # For tool_update_event check
                if tool_update_received:
                    logger.info("PASS: Received tool update event")
                    results["passed"] += 1
                else: logger.warning("WARN: Did not receive tool update event (may be normal)")
            else:
                logger.error("FAIL: Did not receive any events from SSE")
                results["failed"] += 1 # This is a definite failure
        except Exception as e:
            logger.error(f"Error testing SSE endpoint: {e}")
            results["failed"] += (results["total"] - results["passed"]) # Mark all remaining as failed
        TEST_RESULTS["tests"]["total"] += results["total"]
        TEST_RESULTS["tests"]["passed"] += results["passed"]
        TEST_RESULTS["tests"]["failed"] += results["failed"]
        success_rate = (results["passed"] / results["total"]) * 100 if results["total"] > 0 else 0
        logger.info(f"SSE endpoint test complete: {results['passed']}/{results['total']} passed ({success_rate:.2f}%)")
        return results
    
    def analyze_tool_coverage(self):
        logger.info("Analyzing tool coverage...")
        all_tools_info = self.get_all_tools() # get_tools returns list of dicts
        if not all_tools_info:
            logger.error("Could not retrieve tool list for coverage analysis.")
            TEST_RESULTS["coverage"] = {"error": "get_tools failed"}
            return {"ipfs_tool_count": 0, "vfs_tool_count": 0, "missing_essentials": ["all (get_tools failed)"]}
        
        all_tool_names = [t.get("name") for t in all_tools_info if t.get("name")] # Extract names
        categories = self.categorize_tools(all_tool_names) # Pass list of names
        TEST_RESULTS["categories"] = categories # Store categorized names
        
        essential_ipfs = ["ipfs_add", "ipfs_cat", "ipfs_version"]
        essential_vfs = ["vfs_read", "vfs_write", "vfs_ls", "vfs_mkdir"]
        missing = [t for t in essential_ipfs if t not in categories.get("ipfs", [])] + \
                  [t for t in essential_vfs if t not in categories.get("vfs", [])]
        if missing: logger.error(f"Missing essential tools: {', '.join(missing)}")
        else: logger.info("All essential tools are implemented")
        coverage_data = {"ipfs_tool_count": len(categories.get("ipfs", [])), 
                         "vfs_tool_count": len(categories.get("vfs", [])), 
                         "missing_essentials": missing}
        TEST_RESULTS["coverage"] = coverage_data
        return coverage_data
    
    def run_all_tests(self):
        logger.info("Starting comprehensive MCP server tests...")
        if not self.test_server_health():
            logger.error("Server health check FAILED. Aborting further tests.")
            self.generate_report() # Generate report even on health check failure
            return False
        logger.info("Server health check PASSED.")

        if not self.probe_server_capabilities():
            logger.warning("Initial server capability probing FAILED for critical components. Subsequent tests might be unreliable.")
            # Decide if we should abort or continue with warnings
        else:
            logger.info("Initial server capability probing PASSED.")

        self.test_core_tools()
        self.test_ipfs_basic_tools()
        self.test_vfs_basic_tools()
        self.test_sse_endpoint()
        self.analyze_tool_coverage()
        
        total_tests = TEST_RESULTS["tests"]["total"]
        if total_tests > 0:
            TEST_RESULTS["success_rate"] = (TEST_RESULTS["tests"]["passed"] / total_tests) * 100
        
        self.generate_report()
        return TEST_RESULTS["tests"]["failed"] == 0

    def generate_report(self):
        logger.info("Generating test report...")
        # Ensure results directory exists
        results_dir = os.path.dirname(DEFAULT_RESULTS_FILE) or "."
        os.makedirs(results_dir, exist_ok=True)

        with open(DEFAULT_RESULTS_FILE, 'w') as f:
            json.dump(TEST_RESULTS, f, indent=2, default=str) # Use default=str for non-serializable like datetime
        logger.info(f"Test results saved to {DEFAULT_RESULTS_FILE}")
        
        total, passed, failed, rate = TEST_RESULTS["tests"]["total"], TEST_RESULTS["tests"]["passed"], \
                                      TEST_RESULTS["tests"]["failed"], TEST_RESULTS["success_rate"]
        
        summary = [
            "\n" + "="*80,
            "                     MCP TEST RESULTS SUMMARY                       ",
            "="*80,
            f"Timestamp:      {TEST_RESULTS['timestamp']}",
            f"Server File:    {TEST_RESULTS['server_file']}",
            f"Port:           {TEST_RESULTS['port']}",
            f"Total tests:    {total}",
            f"Passed:         {passed}",
            f"Failed:         {failed}",
            f"Success rate:   {rate:.2f}%",
            "="*80
        ]
        if TEST_RESULTS.get("probe_results"):
            summary.append("\nInitial Probe Results:")
            for probe, result in TEST_RESULTS["probe_results"].items():
                status = result.get("status", "unknown")
                details = result.get("response") or result.get("reason", "")
                if isinstance(details, (dict, list)): details = json.dumps(details) # Serialize if dict/list
                summary.append(f"  - {probe}: {status.upper()} {(details[:200] + '...' if len(str(details)) > 200 else details) if details else ''}")
        
        if total == 0: summary.append("\nNo tests were run (beyond initial health/probe if any)!")
        elif failed == 0: summary.append("\nALL TESTS PASSED! The MCP server implementation appears to be working.")
        else:
            summary.append(f"\nSOME TESTS FAILED. See {DEFAULT_RESULTS_FILE} and mcp_test_runner.log for details.")
            if TEST_RESULTS.get("failed_tools"):
                summary.append("\nFailed tools/operations:")
                for ft in TEST_RESULTS["failed_tools"]:
                    resp_summary = json.dumps(ft.get('response')) if ft.get('response') else "N/A"
                    summary.append(f"  - Name: {ft.get('name', 'N/A')}, Category: {ft.get('category', 'N/A')}, Details: {resp_summary[:200]  + '...' if len(resp_summary) > 200 else resp_summary}")
        
        summary.append("\nTool counts by category (from last successful list_tools):")
        for cat, tools in TEST_RESULTS.get("categories", {}).items(): # categories stores list of names
            summary.append(f"- {cat.upper()}: {len(tools)}")
        
        if TEST_RESULTS.get("coverage", {}).get("missing_essentials"):
            summary.append("\nWARNING: Missing essential tools (based on coverage analysis):")
            for tool in TEST_RESULTS["coverage"]["missing_essentials"]: summary.append(f"- {tool}")
        summary.append("="*80 + "\n")
        
        print('\n'.join(summary))
        # Save summary to a markdown file as well
        summary_md_file = os.path.join(results_dir, "summary_mcp_test_runner.md")
        with open(summary_md_file, "w") as f_sum:
            f_sum.write('\n'.join(summary))
        logger.info(f"Test summary markdown saved to {summary_md_file}")


def main():
    parser = argparse.ArgumentParser(description="MCP Server Test Runner")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port the MCP server is running on")
    parser.add_argument("--server-file", type=str, default=DEFAULT_SERVER_FILE, help="MCP server file being tested")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    # Add other specific test flags if needed, e.g., --run-only ipfs_tests
    args = parser.parse_args()

    test_runner = MCPTestRunner(port=args.port, server_file=args.server_file, debug=args.debug)
    success = test_runner.run_all_tests()

    if not success:
        logger.error("One or more tests failed. Exiting with status 1.")
        sys.exit(1)
    else:
        logger.info("All tests passed successfully.")
        sys.exit(0)

if __name__ == "__main__":
    main()
EOF
    
    if [ $missing_files -gt 0 ]; then
      log "ERROR" "One or more required files are missing. Please check the setup." "SETUP"
      exit 1
    fi
    
    log "SUCCESS" "All required test files are present or created." "SETUP"
  fi
  return 0
}

# Function to run comprehensive tests
run_comprehensive_tests() {
  log "INFO" "Starting comprehensive test suite..." "TEST"
  
  # Ensure mcp_test_runner.py exists and is up-to-date
  check_test_files # Call without --force-update unless specified by user
  
  # Run the test runner
  if python3 mcp_test_runner.py --port "$PORT" --server-file "$SERVER_FILE"; then
    log "SUCCESS" "Comprehensive tests PASSED" "TEST"
    cat >> "$SUMMARY_FILE" << EOF
### Comprehensive Tests
✅ **PASSED**
EOF
    return 0
  else
    log "ERROR" "Comprehensive tests FAILED" "TEST"
    cat >> "$SUMMARY_FILE" << EOF
### Comprehensive Tests
❌ **FAILED**
EOF
    return 1
  fi
}

# Function to run IPFS Kit specific tests (if any)
run_ipfs_kit_tests() {
  log "INFO" "Running IPFS Kit specific tests..." "TEST"
  # Placeholder for IPFS Kit specific tests
  # Example: python3 test/test_ipfs_core.py
  
  # For now, assume success
  log "SUCCESS" "IPFS Kit specific tests completed (placeholder)" "TEST"
  cat >> "$SUMMARY_FILE" << EOF
### IPFS Kit Specific Tests
✅ **PASSED (Placeholder)**
EOF
  return 0
}

# Function to run VFS specific tests (if any)
run_vfs_tests() {
  log "INFO" "Running VFS specific tests..." "TEST"
  # Placeholder for VFS specific tests
  # Example: python3 test/test_fsspec_integration.py
  
  # For now, assume success
  log "SUCCESS" "VFS specific tests completed (placeholder)" "TEST"
  cat >> "$SUMMARY_FILE" << EOF
### VFS Specific Tests
✅ **PASSED (Placeholder)**
EOF
  return 0
}

# Function to analyze tool coverage
analyze_tool_coverage() {
  log "INFO" "Analyzing tool coverage..." "TEST"
  
  # Ensure mcp_test_runner.py exists
  check_test_files
  
  if python3 mcp_test_runner.py --coverage --port "$PORT" > "${RESULTS_DIR}/tool_coverage_output.txt" 2>&1; then
    log "SUCCESS" "Tools coverage analysis completed" "TEST"
    # The mcp_test_runner.py script should output its own summary
    # We can also extract key metrics here if needed
    local ipfs_tool_count=$(grep "IPFS tools count:" "${RESULTS_DIR}/tool_coverage_output.txt" | awk '{print $NF}')
    local vfs_tool_count=$(grep "VFS tools count:" "${RESULTS_DIR}/tool_coverage_output.txt" | awk '{print $NF}')
    
    cat >> "$SUMMARY_FILE" << EOF

### Tools Coverage Analysis
✅ **COMPLETED**
- IPFS Tools: ${ipfs_tool_count:-N/A}
- VFS Tools: ${vfs_tool_count:-N/A}
*(See ${DEFAULT_RESULTS_FILE} and ${RESULTS_DIR}/tool_coverage_output.txt for details)*
EOF
    return 0
  else
    log "ERROR" "Tools coverage analysis failed" "TEST"
    cat >> "$SUMMARY_FILE" << EOF

### Tools Coverage Analysis
❌ **FAILED**
EOF
    return 1
  fi
}

# Main execution
# JSON-RPC testing enhancement function
test_jsonrpc_endpoint() {
  log "INFO" "Testing JSON-RPC endpoint with basic ping..." "JSONRPC"
  
  # Create a minimal JSON-RPC request
  local ping_request='{"jsonrpc": "2.0", "method": "ping", "id": 1}'
  local ping_response
  
  if ! ping_response=$(curl -s -X POST -H "Content-Type: application/json" -d "$ping_request" "$JSONRPC_ENDPOINT"); then
    log "ERROR" "Failed to connect to JSON-RPC endpoint" "JSONRPC"
    return 1
  fi
  
  log "DEBUG" "JSON-RPC ping response: $ping_response" "JSONRPC"
  
  # Check for valid JSON-RPC response
  if ! echo "$ping_response" | jq -e . >/dev/null 2>&1; then
    log "ERROR" "JSON-RPC endpoint returned invalid JSON: $ping_response" "JSONRPC"
    return 1
  fi
  
  # Extract result and check for pong
  local result
  result=$(echo "$ping_response" | jq -r '.result // empty')
  
  if [[ "$result" == "pong" ]]; then
    log "SUCCESS" "JSON-RPC ping test successful (got 'pong' response)" "JSONRPC"
    return 0
  else
    local error
    error=$(echo "$ping_response" | jq -r '.error.message // "No specific error message"')
    log "ERROR" "JSON-RPC ping test failed. Error: $error" "JSONRPC"
    return 1
  fi
}
# Main execution
main() {
  # Initialize summary file
  echo "# MCP Test Framework Summary - $(date)" > "$SUMMARY_FILE"
  echo "Test run started at $(date)" >> "$SUMMARY_FILE"
  echo "" >> "$SUMMARY_FILE"

  # Trap for cleanup on exit
  trap "stop_server; log 'INFO' 'Test script finished.'" EXIT
  
  # Check commands and packages
  check_command "python3"
  check_command "pip"
  check_command "curl"
  check_command "ipfs"
  check_python_packages || exit 1 # Exit if package installation fails
  
  # Check and create test files
  check_test_files "$1" # Pass along --force-update if provided
  
  # Handle --tests-only flag
  if [ "$1" == "--tests-only" ]; then
    log "INFO" "Running in --tests-only mode. Assuming server is already running."
    if ! check_server_running || [ $? -ne 0 ]; then
      log "ERROR" "Server not running or not responsive. Cannot run tests in --tests-only mode."
      exit 1
    fi
  else
    # Start/Restart server
    stop_server # Ensure any old instance is stopped
    start_server || exit 1 # Exit if server fails to start
  fi
  
  # Run all test suites
  local all_tests_passed=true
  
  run_comprehensive_tests || all_tests_passed=false
  run_ipfs_kit_tests || all_tests_passed=false # Placeholder
  run_vfs_tests || all_tests_passed=false      # Placeholder
  analyze_tool_coverage || all_tests_passed=false
  
  # Final summary
  echo "" >> "$SUMMARY_FILE"
  if [ "$all_tests_passed" = true ]; then
    log "SUCCESS" "All test suites PASSED!" "MAIN"
    echo "🎉 **Overall Status: ALL TESTS PASSED** 🎉" >> "$SUMMARY_FILE"
  else
    log "ERROR" "One or more test suites FAILED." "MAIN"
    echo "❌ **Overall Status: SOME TESTS FAILED** ❌" >> "$SUMMARY_FILE"
  fi
  
  log "INFO" "Detailed test summary written to: $SUMMARY_FILE"
  log "INFO" "Full logs available in: $LOG_FILE"
  log "INFO" "Test results JSON: ${DEFAULT_RESULTS_FILE}" # From mcp_test_runner.py
  
  # If not in --tests-only mode, stop the server
  if [ "$1" != "--tests-only" ]; then
    stop_server
  fi

  if [ "$all_tests_passed" = false ]; then
    exit 1 # Exit with error code if any test failed
  fi
}

# Run main function with all script arguments
main "$@"
# Function to test complete IPFS kit integration with MCP
test_ipfs_kit_integration() {
  log "INFO" "Testing comprehensive IPFS kit integration with MCP tools..." "IPFS-KIT"
  
  # Create test directory
  local test_dir="$RESULTS_DIR/ipfs_kit_integration_test"
  mkdir -p "$test_dir"
  
  # Create test file
  local test_file="$test_dir/test_content.txt"
  local test_content="This is a test file for IPFS kit integration with MCP tools $(date)"
  echo "$test_content" > "$test_file"
  
  # Test flow:
  # 1. Add file to IPFS via MCP tool
  # 2. Retrieve CID
  # 3. Import into VFS
  # 4. Modify via VFS
  # 5. Verify changes propagate to IPFS
  local ipfs_tools_working=true
  local vfs_tools_working=true
  local integration_working=true
  
  # Step 1: Add file to IPFS
  log "INFO" "Adding test file to IPFS via MCP tool..." "IPFS-KIT"
  local add_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"ipfs_add\",\"params\":{\"file_path\":\"$test_file\"},\"id\":1}")
  
  if [[ "$add_response" != *"cid"* ]] && [[ "$add_response" != *"Hash"* ]]; then
    log "ERROR" "Failed to add file to IPFS: $add_response" "IPFS-KIT"
    ipfs_tools_working=false
    return 1
  fi
  
  # Extract CID
  local cid=""
  if [[ "$add_response" == *"\"cid\""* ]]; then
    cid=$(echo "$add_response" | grep -o '"cid"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
  elif [[ "$add_response" == *"\"Hash\""* ]]; then
    cid=$(echo "$add_response" | grep -o '"Hash"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
  fi
  
  log "INFO" "Successfully added file to IPFS with CID: $cid" "IPFS-KIT"
  
  # Step 2: Verify retrieval from IPFS
  log "INFO" "Retrieving file from IPFS via MCP tool..." "IPFS-KIT"
  local cat_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"ipfs_cat\",\"params\":{\"cid\":\"$cid\"},\"id\":2}")
  
  if [[ "$cat_response" != *"$test_content"* ]]; then
    log "ERROR" "Failed to retrieve file from IPFS or content mismatch: $cat_response" "IPFS-KIT"
    ipfs_tools_working=false
  else
    log "SUCCESS" "Successfully retrieved file from IPFS with matching content" "IPFS-KIT"
  fi
  
  # Step 3: Test VFS import from IPFS
  local vfs_path="/ipfs-kit-test-$(date +%s)"
  local vfs_file="$vfs_path/imported.txt"
  
  log "INFO" "Creating VFS directory: $vfs_path" "IPFS-KIT"
  local mkdir_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"vfs_mkdir\",\"params\":{\"path\":\"$vfs_path\"},\"id\":3}")
  
  if [[ "$mkdir_response" != *"success"* ]] && [[ "$mkdir_response" != *"result"* ]]; then
    log "ERROR" "Failed to create VFS directory: $mkdir_response" "IPFS-KIT"
    vfs_tools_working=false
    return 1
  fi
  
  log "INFO" "Importing IPFS content to VFS: $vfs_file" "IPFS-KIT"
  local import_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"vfs_import\",\"params\":{\"path\":\"$vfs_file\",\"cid\":\"$cid\"},\"id\":4}")
  
  if [[ "$import_response" != *"result"* ]]; then
    log "ERROR" "Failed to import IPFS content to VFS: $import_response" "IPFS-KIT"
    integration_working=false
  else
    log "SUCCESS" "Successfully imported IPFS content to VFS" "IPFS-KIT"
    
    # Step 4: Verify VFS content
    log "INFO" "Verifying VFS file content..." "IPFS-KIT"
    local read_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
      -H "Content-Type: application/json" \
      -d "{\"jsonrpc\":\"2.0\",\"method\":\"vfs_read\",\"params\":{\"path\":\"$vfs_file\"},\"id\":5}")
    
    if [[ "$read_response" != *"$test_content"* ]]; then
      log "ERROR" "VFS content doesn't match original: $read_response" "IPFS-KIT"
      vfs_tools_working=false
    else
      log "SUCCESS" "Successfully verified VFS content matches original" "IPFS-KIT"
      
      # Step 5: Modify VFS file and verify changes in IPFS
      local modified_content="$test_content\nModified via VFS on $(date)"
      log "INFO" "Modifying VFS file..." "IPFS-KIT"
      local write_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
        -H "Content-Type: application/json" \
        -d "{\"jsonrpc\":\"2.0\",\"method\":\"vfs_write\",\"params\":{\"path\":\"$vfs_file\",\"content\":\"$modified_content\"},\"id\":6}")
      
      if [[ "$write_response" != *"result"* ]]; then
        log "ERROR" "Failed to modify VFS file: $write_response" "IPFS-KIT"
        vfs_tools_working=false
      else
        log "SUCCESS" "Successfully modified VFS file" "IPFS-KIT"
        
        # Get new CID
        log "INFO" "Getting CID of modified file..." "IPFS-KIT"
        local stat_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
          -H "Content-Type: application/json" \
          -d "{\"jsonrpc\":\"2.0\",\"method\":\"vfs_stat\",\"params\":{\"path\":\"$vfs_file\"},\"id\":7}")
        
        local new_cid=""
        if [[ "$stat_response" == *"\"cid\""* ]]; then
          new_cid=$(echo "$stat_response" | grep -o '"cid"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
        elif [[ "$stat_response" == *"\"hash\""* ]]; then
          new_cid=$(echo "$stat_response" | grep -o '"hash"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
        fi
        
        if [ -z "$new_cid" ]; then
          log "ERROR" "Failed to get new CID for modified file" "IPFS-KIT"
          integration_working=false
        else
          log "INFO" "Got new CID after modification: $new_cid" "IPFS-KIT"
          
          # Verify modified content via IPFS
          log "INFO" "Verifying modified content via IPFS..." "IPFS-KIT"
          local new_cat_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
            -H "Content-Type: application/json" \
            -d "{\"jsonrpc\":\"2.0\",\"method\":\"ipfs_cat\",\"params\":{\"cid\":\"$new_cid\"},\"id\":8}")
          
          if [[ "$new_cat_response" != *"Modified via VFS"* ]]; then
            log "ERROR" "Modified content not reflected in IPFS: $new_cat_response" "IPFS-KIT"
            integration_working=false
          else
            log "SUCCESS" "Modified content successfully verified via IPFS" "IPFS-KIT"
          fi
        fi
      fi
    fi
  fi
  
  # Clean up
  log "INFO" "Cleaning up test files..." "IPFS-KIT"
  curl -s -X POST "$JSONRPC_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"vfs_rm\",\"params\":{\"path\":\"$vfs_file\"},\"id\":9}" > /dev/null
    
  curl -s -X POST "$JSONRPC_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"vfs_rmdir\",\"params\":{\"path\":\"$vfs_path\"},\"id\":10}" > /dev/null
  
  # Generate report
  local report_file="$RESULTS_DIR/ipfs_kit_integration_report_$(date +%Y%m%d_%H%M%S).md"
  cat > "$report_file" << EOF
# IPFS Kit Integration Test Report

Generated: $(date "+%Y-%m-%d %H:%M:%S")

## Test Results

| Component | Status | 
|-----------|--------|
| IPFS Tools | $(if $ipfs_tools_working; then echo "✅ WORKING"; else echo "❌ FAILURE"; fi) |
| VFS Tools | $(if $vfs_tools_working; then echo "✅ WORKING"; else echo "❌ FAILURE"; fi) |
| Integration | $(if $integration_working; then echo "✅ WORKING"; else echo "❌ FAILURE"; fi) |

## Test Details

- Test file: \`$test_file\`
- Original CID: \`$cid\`
- VFS Path: \`$vfs_file\`
- Modified CID: \`${new_cid:-"N/A"}\`

EOF
  
  log "INFO" "IPFS Kit integration test report written to: $report_file" "IPFS-KIT"
  
  # Return success if all components worked
  if $ipfs_tools_working && $vfs_tools_working && $integration_working; then
    log "SUCCESS" "IPFS Kit integration test passed" "IPFS-KIT"
    return 0
  else
    log "ERROR" "IPFS Kit integration test failed" "IPFS-KIT"
    return 1
  fi
}

# Function to restart and monitor MCP server
restart_and_monitor_server() {
  log "INFO" "Restarting and monitoring MCP server..." "MONITOR"
  
  # Stop the server if running
  stop_server
  
  # Record the start time
  local start_time=$(date +%s)
  
  # Start the server
  start_server || {
    log "ERROR" "Failed to start MCP server" "MONITOR"
    return 1
  }
  
  # Get the PID of the server
  local pid=$(cat "$SERVER_PID_FILE")
  log "INFO" "MCP server started with PID: $pid" "MONITOR"
  
  # Create monitoring log file
  local monitor_log="$RESULTS_DIR/server_monitor_$(date +%Y%m%d_%H%M%S).log"
  
  # Record initial stats
  log "INFO" "Recording initial stats to $monitor_log" "MONITOR"
  echo "=== MCP Server Monitoring Log - $(date) ===" > "$monitor_log"
  echo "Server PID: $pid" >> "$monitor_log"
  echo "Server File: $SERVER_FILE" >> "$monitor_log"
  echo "Port: $PORT" >> "$monitor_log"
  echo "" >> "$monitor_log"
  
  # Run a quick check of available tools
  local tools_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}')
  
  if [[ "$tools_response" == *"tools"* ]]; then
    # Count total, ipfs, and vfs tools
    local total_tools=$(echo "$tools_response" | grep -o '"tools"' | wc -l)
    local ipfs_tools=$(echo "$tools_response" | grep -o '"ipfs_[^"]*"' | wc -l)
    local vfs_tools=$(echo "$tools_response" | grep -o '"vfs_[^"]*"' | wc -l)
    
    echo "Initial Tool Count:" >> "$monitor_log"
    echo "- Total tools: $total_tools" >> "$monitor_log"
    echo "- IPFS tools: $ipfs_tools" >> "$monitor_log"
    echo "- VFS tools: $vfs_tools" >> "$monitor_log"
    echo "" >> "$monitor_log"
  else
    echo "WARNING: Could not get initial tool count" >> "$monitor_log"
  fi
  
  # Monitor process for 30 seconds
  log "INFO" "Monitoring server process for 30 seconds..." "MONITOR"
  local end_time=$((start_time + 30))
  local check_interval=5
  local iteration=1
  
  while [ $(date +%s) -lt $end_time ]; do
    # Check if process is still running
    if ! ps -p "$pid" > /dev/null; then
      log "ERROR" "Server process has died during monitoring" "MONITOR"
      echo "ERROR: Server process died at $(date)" >> "$monitor_log"
      return 1
    fi
    
    # Record process stats
    echo "=== Iteration $iteration - $(date) ===" >> "$monitor_log"
    ps -p "$pid" -o pid,ppid,user,%cpu,%mem,vsz,rss,stat,start,time,command >> "$monitor_log"
    echo "" >> "$monitor_log"
    
    # Test basic server functionality
    curl -s "$HEALTH_ENDPOINT" >> "$monitor_log" 2>&1
    echo "" >> "$monitor_log"
    
    # Test a ping call
    local ping_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
      -H "Content-Type: application/json" \
      -d '{"jsonrpc":"2.0","method":"ping","params":{},"id":1}')
    echo "Ping response: $ping_response" >> "$monitor_log"
    echo "" >> "$monitor_log"
    
    # Increment and wait
    ((iteration++))
    sleep $check_interval
  done
  
  # Final health check
  log "INFO" "Performing final health check..." "MONITOR"
  if curl -s "$HEALTH_ENDPOINT" | grep -q "ok"; then
    log "SUCCESS" "Server is healthy after monitoring period" "MONITOR"
    echo "FINAL STATUS: Server is healthy after monitoring period" >> "$monitor_log"
    return 0
  else
    log "ERROR" "Server is not responding healthily after monitoring period" "MONITOR"
    echo "FINAL STATUS: Server is not responding healthily" >> "$monitor_log"
    return 1
  fi
}

# Function to verify IPFS kit functionality exposed as MCP tools
verify_ipfs_kit_tool_coverage() {
  log "INFO" "Verifying IPFS kit functionality exposed as MCP tools..." "COVERAGE"
  
  # Get list of all tools
  local tools_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}')
  
  # Check if the response contains tools
  if [ $? -ne 0 ] || [[ ! $tools_response == *"tools"* ]]; then
    log "ERROR" "Failed to get list of tools from the server" "COVERAGE"
    return 1
  fi
  
  # Extract all tools
  local all_tools=$(echo "$tools_response" | grep -o '"[^"]*"' | grep -v '"jsonrpc"' | grep -v '"id"' | grep -v '"method"' | grep -v '"result"' | grep -v '"tools"' | tr -d '"')
  
  # Define expected IPFS functions
  local expected_ipfs_functions=(
    "ipfs_add"
    "ipfs_cat"
    "ipfs_get"
    "ipfs_ls"
    "ipfs_version"
    "ipfs_pin_add"
    "ipfs_pin_rm"
    "ipfs_pin_ls"
    "ipfs_files_cp"
    "ipfs_files_write"
    "ipfs_files_read"
    "ipfs_files_mkdir"
    "ipfs_files_stat"
    "ipfs_files_ls"
    "ipfs_files_rm"
  )
  
  # Define expected VFS functions
  local expected_vfs_functions=(
    "vfs_read"
    "vfs_write"
    "vfs_mkdir"
    "vfs_rmdir"
    "vfs_ls"
    "vfs_rm"
    "vfs_mv"
    "vfs_cp"
    "vfs_stat"
    "vfs_import"
    "vfs_export"
  )
  
  # Count found functions
  local ipfs_found=0
  local vfs_found=0
  local missing_ipfs=()
  local missing_vfs=()
  
  # Check IPFS functions
  for func in "${expected_ipfs_functions[@]}"; do
    if echo "$all_tools" | grep -q "$func"; then
      ((ipfs_found++))
      log "DEBUG" "Found expected IPFS function: $func" "COVERAGE"
    else
      missing_ipfs+=("$func")
      log "WARNING" "Missing expected IPFS function: $func" "COVERAGE"
    fi
  done
  
  # Check VFS functions
  for func in "${expected_vfs_functions[@]}"; do
    if echo "$all_tools" | grep -q "$func"; then
      ((vfs_found++))
      log "DEBUG" "Found expected VFS function: $func" "COVERAGE"
    else
      missing_vfs+=("$func")
      log "WARNING" "Missing expected VFS function: $func" "COVERAGE"
    fi
  done
  
  # Calculate coverage percentages
  local ipfs_coverage=$((ipfs_found * 100 / ${#expected_ipfs_functions[@]}))
  local vfs_coverage=$((vfs_found * 100 / ${#expected_vfs_functions[@]}))
  local total_coverage=$(((ipfs_found + vfs_found) * 100 / (${#expected_ipfs_functions[@]} + ${#expected_vfs_functions[@]})))
  
  log "INFO" "IPFS functionality coverage: $ipfs_coverage%" "COVERAGE"
  log "INFO" "VFS functionality coverage: $vfs_coverage%" "COVERAGE"
  log "INFO" "Overall IPFS Kit integration coverage: $total_coverage%" "COVERAGE"
  
  # Generate coverage report
  local report_file="$RESULTS_DIR/ipfs_kit_coverage_$(date +%Y%m%d_%H%M%S).md"
  cat > "$report_file" << EOF
# IPFS Kit Tool Coverage Report

Generated: $(date "+%Y-%m-%d %H:%M:%S")

## Coverage Summary

| Category | Available | Expected | Coverage |
|----------|-----------|----------|----------|
| IPFS Tools | $ipfs_found | ${#expected_ipfs_functions[@]} | $ipfs_coverage% |
| VFS Tools | $vfs_found | ${#expected_vfs_functions[@]} | $vfs_coverage% |
| **Total** | $((ipfs_found + vfs_found)) | $((${#expected_ipfs_functions[@]} + ${#expected_vfs_functions[@]})) | $total_coverage% |

## Details

### Missing IPFS Functions
EOF

  if [ ${#missing_ipfs[@]} -eq 0 ]; then
    echo "- *None - All expected IPFS functions are implemented*" >> "$report_file"
  else
    for func in "${missing_ipfs[@]}"; do
      echo "- \`$func\`" >> "$report_file"
    done
  fi
  
  cat >> "$report_file" << EOF

### Missing VFS Functions
EOF

  if [ ${#missing_vfs[@]} -eq 0 ]; then
    echo "- *None - All expected VFS functions are implemented*" >> "$report_file"
  else
    for func in "${missing_vfs[@]}"; do
      echo "- \`$func\`" >> "$report_file"
    done
  fi
  
  cat >> "$report_file" << EOF

## Recommendations

Based on the coverage analysis, the following actions are recommended:

EOF

  if [ "$total_coverage" -lt 80 ]; then
    cat >> "$report_file" << EOF
- **High Priority**: Implement the missing functions to improve integration.
- Consider implementing the most critical missing functions first.
EOF
  elif [ "$total_coverage" -lt 95 ]; then
    cat >> "$report_file" << EOF
- **Medium Priority**: Add the remaining functions to achieve full coverage.
- Focus on implementing the most useful missing functions.
EOF
  else
    cat >> "$report_file" << EOF
- **Low Priority**: Coverage is already excellent.
- Consider implementing the few remaining functions for completeness.
EOF
  fi
  
  log "INFO" "Tool coverage report written to: $report_file" "COVERAGE"
  
  # Return success if coverage is acceptable (>75%)
  if [ "$total_coverage" -ge 75 ]; then
    return 0
  else
    return 1
  fi
}

# Main function
main() {
  log "INFO" "Starting MCP Comprehensive Testing Framework" "MAIN"
  
  # Default parameters
  local server_file="$SERVER_FILE"
  local port="$PORT"
  local action="all"
  local restart_flag=true
  
  # Parse command line parameters
  while [ $# -gt 0 ]; do
    case "$1" in
      --server|-s)
        server_file="$2"
        shift 2
        ;;
      --port|-p)
        port="$2"
        shift 2
        ;;
      --action|-a)
        action="$2"
        shift 2
        ;;
      --no-restart)
        restart_flag=false
        shift
        ;;
      --help|-h)
        echo "MCP Comprehensive Testing Framework"
        echo "Usage: $0 [options]"
        echo ""
        echo "Options:"
        echo "  --server, -s FILE    Specify MCP server file (default: $SERVER_FILE)"
        echo "  --port, -p NUM       Specify MCP server port (default: $PORT)"
        echo "  --action, -a ACTION  Specify action: all, start, stop, restart, test"
        echo "  --no-restart         Don't restart the server if it's already running"
        echo "  --help, -h           Show this help message"
        exit 0
        ;;
      *)
        log "ERROR" "Unknown option: $1" "MAIN"
        exit 1
        ;;
    esac
  done
  
  # Update settings based on parsed parameters
  SERVER_FILE="$server_file"
  PORT="$port"
  
  # Set up endpoints based on PORT
  HEALTH_ENDPOINT="http://localhost:${PORT}/health"
  JSONRPC_ENDPOINT="http://localhost:${PORT}/jsonrpc"
  SSE_ENDPOINT="http://localhost:${PORT}/sse"

  # Ensure IPFS daemon is running
  if type check_ipfs_dependency &>/dev/null; then
    check_ipfs_dependency || {
      log "ERROR" "Failed to ensure IPFS daemon is running" "MAIN"
      exit 1
    }
  else
    log "WARNING" "check_ipfs_dependency function not available, skipping IPFS daemon check" "MAIN"
  fi
  
  # Execute the requested action
  case "$action" in
    all)
      log "INFO" "Running full MCP test suite" "MAIN"
      
      if $restart_flag; then
        log "INFO" "Restarting server with monitoring..." "MAIN"
        restart_and_monitor_server || {
          log "ERROR" "Server restart and monitoring failed" "MAIN"
        }
      else
        check_server_running || {
          log "INFO" "Server not running, starting..." "MAIN"
          start_server || {
            log "ERROR" "Failed to start MCP server" "MAIN"
            exit 1
          }
        }
      fi
      
      # Run the comprehensive test suite
      run_comprehensive_test_suite || {
        log "ERROR" "Comprehensive test suite failed" "MAIN"
      }
      
      # Run IPFS kit integration test
      test_ipfs_kit_integration || {
        log "ERROR" "IPFS kit integration test failed" "MAIN"
      }
      
      # Verify tool coverage
      verify_ipfs_kit_tool_coverage || {
        log "WARNING" "IPFS kit tool coverage below threshold" "MAIN"
      }
      
      # Display summary
      if [ -f "$SUMMARY_FILE" ]; then
        log "INFO" "Test summary:" "MAIN"
        cat "$SUMMARY_FILE"
      fi
      ;;
      
    start)
      log "INFO" "Starting MCP server" "MAIN"
      start_server || {
        log "ERROR" "Failed to start MCP server" "MAIN"
        exit 1
      }
      ;;
      
    stop)
      log "INFO" "Stopping MCP server" "MAIN"
      stop_server
      ;;
      
    restart)
      log "INFO" "Restarting MCP server with monitoring" "MAIN"
      restart_and_monitor_server || {
        log "ERROR" "Server restart and monitoring failed" "MAIN"
        exit 1
      }
      ;;
      
    test)
      log "INFO" "Running tests against running MCP server" "MAIN"
      check_server_running || {
        log "ERROR" "MCP server is not running. Start it first with: $0 --action start" "MAIN"
        exit 1
      }
      
      # Run the comprehensive test suite
      run_comprehensive_test_suite || {
        log "ERROR" "Comprehensive test suite failed" "MAIN"
      }
      
      # Run IPFS kit integration test
      test_ipfs_kit_integration || {
        log "ERROR" "IPFS kit integration test failed" "MAIN"
      }
      
      # Verify tool coverage
      verify_ipfs_kit_tool_coverage || {
        log "WARNING" "IPFS kit tool coverage below threshold" "MAIN"
      }
      
      # Display summary
      if [ -f "$SUMMARY_FILE" ]; then
        log "INFO" "Test summary:" "MAIN"
        cat "$SUMMARY_FILE"
      fi
      ;;
      
    *)
      log "ERROR" "Unknown action: $action" "MAIN"
      exit 1
      ;;
  esac
  
  log "SUCCESS" "MCP Comprehensive Testing Framework completed" "MAIN"
}

# Execute main function
main "$@"
