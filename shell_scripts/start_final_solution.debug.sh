set -e
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
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color
mkdir -p "$RESULTS_DIR"
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
check_command() {
  local cmd=$1
  if ! command -v "$cmd" &> /dev/null; then
    log "ERROR" "Command $cmd not found. Please install it and try again."
    exit 1
  fi
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
          log "INFO" "Still waiting for health endpoint... (${elapsed}s)" "SERVER"
        fi
      fi
    done
    
    if [ "$health_ok" = "true" ]; then
      # Then check if JSON-RPC is working
      elapsed=0
      while [ $elapsed -lt $timeout ] && [ "$jsonrpc_ok" = "false" ]; do
        # Try a simple ping call
        local response=$(curl -s -X POST "$SERVER_JSONRPC_ENDPOINT" \
          -H "Content-Type: application/json" \
          -d '{"jsonrpc":"2.0","method":"ping","params":{},"id":1}')
        
        if [ $? -eq 0 ] && [[ $response == *"pong"* ]]; then
          jsonrpc_ok=true
          log "INFO" "JSON-RPC endpoint is responsive" "SERVER"
          started=true
          break
        else
          sleep $interval
          elapsed=$((elapsed + interval))
          if [ $((elapsed % 5)) -eq 0 ]; then
            log "INFO" "Still waiting for JSON-RPC endpoint... (${elapsed}s)" "SERVER"
          fi
        fi
      done
      
      if [ "$jsonrpc_ok" = "true" ]; then
        # Check available tools
        local tools_response=$(curl -s -X POST "$SERVER_JSONRPC_ENDPOINT" \
          -H "Content-Type: application/json" \
          -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}')
        
        if [ $? -eq 0 ] && [[ $tools_response == *"tools"* ]]; then
          # Extract tool count if possible
          local tool_count=$(echo $tools_response | grep -o '"tools":\[[^]]*\]' | grep -o ',' | wc -l)
          tool_count=$((tool_count + 1))
          log "SUCCESS" "MCP server is fully responsive with approximately $tool_count tools!" "SERVER"
          # Wait a bit more to ensure all routes are registered
          sleep 2
          break
        else
          log "WARNING" "Server is responding but list_tools failed" "SERVER"
          # Still consider the server started, but with a warning
          started=true
          break
        fi
      else
        log "WARNING" "Health endpoint is responsive, but JSON-RPC is not" "SERVER"
      fi
    fi
    
    if [ "$started" = "false" ]; then
      retry_count=$((retry_count + 1))
      log "WARNING" "Attempt $retry_count: Server not fully responsive after ${timeout}s" "SERVER"
      
      # Show the last few lines of the log for debugging
      log "INFO" "Last 10 lines of server log:" "SERVER"
      tail -n 10 "$server_log" | while read -r line; do
        log "DEBUG" "$line" "SERVER_LOG"
      done
      
      stop_server
      sleep 3
    fi
  done
  
  # Final check if the server is actually running
  if ! check_server_running; then
    log "ERROR" "Failed to start MCP server after $max_retries attempts" "SERVER"
    log "ERROR" "See logs in $RESULTS_DIR for details" "SERVER"
    exit 1
  fi
  
  # Run a quick tool count diagnostic
  log "INFO" "Checking available MCP tools..." "SERVER"
  local tools_response=$(curl -s -X POST "$SERVER_JSONRPC_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}')
  
  # Count IPFS and VFS tools
  local ipfs_tools=$(echo $tools_response | grep -o '"ipfs_[^"]*"' | wc -l)
  local vfs_tools=$(echo $tools_response | grep -o '"vfs_[^"]*"' | wc -l)
  
  log "INFO" "Detected approximately $ipfs_tools IPFS tools and $vfs_tools VFS tools" "SERVER"
stop_server() {
  if [ -f "$SERVER_PID_FILE" ]; then
    local pid=$(cat "$SERVER_PID_FILE")
    log "INFO" "Stopping MCP server with PID: $pid" "SERVER"
    
    # First try SIGTERM for graceful shutdown
    kill -15 "$pid" 2> /dev/null || true
    
    # Wait up to 5 seconds for graceful shutdown
    local timeout=5
    local elapsed=0
    
    while [ $elapsed -lt $timeout ]; do
      if ! ps -p "$pid" > /dev/null 2>&1; then
        log "SUCCESS" "Server stopped gracefully" "SERVER"
        rm -f "$SERVER_PID_FILE"
        return 0
      fi
      sleep 1
      elapsed=$((elapsed + 1))
    done
    
    # If still running after timeout, force kill
    if ps -p "$pid" > /dev/null 2>&1; then
      log "WARNING" "Server still running after ${timeout}s, force killing..." "SERVER"
      kill -9 "$pid" 2> /dev/null || true
      sleep 1
    fi
    
    # Verify it's actually stopped
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
check_test_files() {
  log "INFO" "Checking for required test files..." "SETUP"
  local missing_files=0
  
  # Check for server file
  if [ ! -f "$SERVER_FILE" ]; then
    log "ERROR" "MCP server file '$SERVER_FILE' not found" "SETUP"
    missing_files=$((missing_files + 1))
  fi
  
  # Create test data directory if it doesn't exist
  mkdir -p "$TEST_DATA_DIR"
  
  # Create test runner if it doesn't exist or needs to be updated
  if [ ! -f "mcp_test_runner.py" ] || [ "$1" == "--force-update" ]; then
    log "INFO" "Creating/Updating comprehensive MCP test runner..." "SETUP"
    
    cat > "mcp_test_runner.py" << 'EOF'
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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('mcp_test_runner.log')
    ]
)
logger = logging.getLogger("mcp-test-runner")
try:
    import requests
    from requests.exceptions import RequestException
except ImportError:
    logger.info("Installing required dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests
    from requests.exceptions import RequestException
try:
    from sseclient import SSEClient
except ImportError:
    logger.info("Installing SSE client dependency...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "sseclient-py"])
    from sseclient import SSEClient
DEFAULT_PORT = 9996
DEFAULT_SERVER_FILE = "enhanced_final_mcp_server.py"
DEFAULT_TIMEOUT = 30  # seconds
DEFAULT_TEST_DATA_DIR = "diagnostic_results/test_data"
DEFAULT_RESULTS_FILE = "mcp_test_results.json"
TEST_RESULTS = {
    "timestamp": datetime.now().isoformat(),
    "server_file": DEFAULT_SERVER_FILE,
    "tests": {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0
    },
    "categories": {},
    "tool_tests": [],
    "failed_tools": [],
    "success_rate": 0.0
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
        
        # Create test data directory if it doesn't exist
        os.makedirs(self.test_data_dir, exist_ok=True)
        
        # Set logging level based on debug flag
        if debug:
            logger.setLevel(logging.DEBUG)
        
        logger.info(f"MCP Test Runner initialized: Server on port {port}, debug={debug}")
    
    def call_jsonrpc(self, method, params=None, timeout=DEFAULT_TIMEOUT):
        """Make a JSON-RPC call to the MCP server"""
        if params is None:
            params = {}
        
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": int(time.time() * 1000)
        }
        
        try:
            logger.debug(f"Calling {method} with params: {params}")
            response = requests.post(self.jsonrpc_url, json=payload, timeout=timeout)
            return response.json()
        except Exception as e:
            logger.error(f"Error calling {method}: {e}")
            return {"error": {"message": str(e)}}
    
    def test_server_health(self):
        """Test the server health endpoint"""
        try:
            logger.info("Testing server health endpoint...")
            response = requests.get(self.health_url, timeout=DEFAULT_TIMEOUT)
            if response.status_code == 200:
                logger.info("Health endpoint check passed")
                return True
            else:
                logger.error(f"Health endpoint check failed: status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Health endpoint check error: {e}")
            return False
    
    def get_all_tools(self):
        """Get a list of all tools registered with the MCP server"""
        result = self.call_jsonrpc("list_tools")
        if "result" in result and "tools" in result["result"]:
            tools = result["result"]["tools"]
            logger.info(f"Found {len(tools)} tools registered with the server")
            return tools
        else:
            error = result.get("error", {}).get("message", "Unknown error")
            logger.error(f"Failed to get tool list: {error}")
            return []
    
    def categorize_tools(self, tools):
        """Categorize tools by their type based on naming convention"""
        categories = {
            "core": [],
            "ipfs": [],
            "vfs": [],
            "other": [],
        }
        
        for tool in tools:
            name = tool if isinstance(tool, str) else tool.get("name", "")
            
            if name in ["ping", "health", "list_tools"]:
                categories["core"].append(name)
            elif name.startswith("ipfs_"):
                categories["ipfs"].append(name)
            elif name.startswith("vfs_"):
                categories["vfs"].append(name)
            else:
                categories["other"].append(name)
        
        # Log category counts
        for category, tools_list in categories.items():
            logger.info(f"Found {len(tools_list)} {category.upper()} tools")
        
        return categories
    
    def generate_test_data(self):
        """Generate random test data for IPFS and VFS operations"""
        test_file_content = ''.join(random.choices(
            string.ascii_letters + string.digits, k=1024))
        test_file_path = os.path.join(self.test_data_dir, "test_file.txt")
        
        with open(test_file_path, 'w') as f:
            f.write(test_file_content)
        
        logger.info(f"Generated test file at {test_file_path}")
        return {
            "file_path": test_file_path,
            "content": test_file_content,
            "directory": self.test_data_dir
        }
    
    def test_core_tools(self):
        """Test core MCP tools (ping, health, list_tools)"""
        logger.info("Testing core MCP tools...")
        results = {"passed": 0, "failed": 0, "total": 3}
        
        # Test ping
        ping_result = self.call_jsonrpc("ping")
        if "result" in ping_result and ping_result["result"] == "pong":
            logger.info("PASS: ping tool returned 'pong'")
            results["passed"] += 1
        else:
            error = ping_result.get("error", {}).get("message", "Unknown error")
            logger.error(f"FAIL: ping tool failed: {error}")
            results["failed"] += 1
            TEST_RESULTS["failed_tools"].append({"name": "ping", "category": "core"})
        
        # Test health
        health_result = self.call_jsonrpc("health")
        if "result" in health_result and health_result["result"].get("status") == "ok":
            logger.info("PASS: health tool returned status 'ok'")
            results["passed"] += 1
        else:
            error = health_result.get("error", {}).get("message", "Unknown error")
            logger.error(f"FAIL: health tool failed: {error}")
            results["failed"] += 1
            TEST_RESULTS["failed_tools"].append({"name": "health", "category": "core"})
        
        # Test list_tools 
        list_result = self.call_jsonrpc("list_tools")
        if "result" in list_result and "tools" in list_result["result"]:
            logger.info(f"PASS: list_tools returned {len(list_result['result']['tools'])} tools")
            results["passed"] += 1
        else:
            error = list_result.get("error", {}).get("message", "Unknown error")
            logger.error(f"FAIL: list_tools failed: {error}")
            results["failed"] += 1
            TEST_RESULTS["failed_tools"].append({"name": "list_tools", "category": "core"})
        
        # Update global test results
        TEST_RESULTS["tests"]["total"] += results["total"]
        TEST_RESULTS["tests"]["passed"] += results["passed"]
        TEST_RESULTS["tests"]["failed"] += results["failed"]
        
        success_rate = (results["passed"] / results["total"]) * 100
        logger.info(f"Core tools test complete: {results['passed']}/{results['total']} passed ({success_rate:.2f}%)")
        return results
    
    def test_ipfs_basic_tools(self):
        """Test basic IPFS tools for functionality"""
        logger.info("Testing basic IPFS tools...")
        results = {"passed": 0, "failed": 0, "total": 0}
        
        # Test ipfs_version
        results["total"] += 1
        version_result = self.call_jsonrpc("ipfs_version")
        if "result" in version_result:
            logger.info(f"PASS: ipfs_version returned: {version_result['result']}")
            results["passed"] += 1
        else:
            error = version_result.get("error", {}).get("message", "Unknown error")
            logger.error(f"FAIL: ipfs_version failed: {error}")
            results["failed"] += 1
            TEST_RESULTS["failed_tools"].append({"name": "ipfs_version", "category": "ipfs"})
        
        # Test ipfs_add and ipfs_cat
        test_content = "Hello IPFS from MCP test runner!"
        
        results["total"] += 1
        add_result = self.call_jsonrpc("ipfs_add", {"content": test_content})
        if "result" in add_result:
            # Check for either "Hash" or "cid" field for compatibility
            if "Hash" in add_result["result"]:
                cid = add_result["result"]["Hash"]
            elif "cid" in add_result["result"]:
                cid = add_result["result"]["cid"]
            else:
                cid = None
                
            if cid:
                logger.info(f"PASS: ipfs_add returned CID: {cid}")
                results["passed"] += 1
                
                # Now test ipfs_cat with the CID
                results["total"] += 1
                cat_result = self.call_jsonrpc("ipfs_cat", {"cid": cid})
                
                if "result" in cat_result:
                    retrieved = cat_result["result"]
                    if isinstance(retrieved, dict) and "content" in retrieved:
                        retrieved = retrieved["content"]
                    
                    if retrieved == test_content:
                        logger.info("PASS: ipfs_cat retrieved correct content")
                        results["passed"] += 1
                    else:
                        logger.error(f"FAIL: ipfs_cat retrieved incorrect content: {retrieved}")
                        results["failed"] += 1
                        TEST_RESULTS["failed_tools"].append({"name": "ipfs_cat", "category": "ipfs"})
                else:
                    error = cat_result.get("error", {}).get("message", "Unknown error")
                    logger.error(f"FAIL: ipfs_cat failed: {error}")
                    results["failed"] += 1
                    TEST_RESULTS["failed_tools"].append({"name": "ipfs_cat", "category": "ipfs"})
            else:
                logger.error("FAIL: ipfs_add did not return a valid CID")
                results["failed"] += 1
                TEST_RESULTS["failed_tools"].append({"name": "ipfs_add", "category": "ipfs"})
        else:
            error = add_result.get("error", {}).get("message", "Unknown error")
            logger.error(f"FAIL: ipfs_add failed: {error}")
            results["failed"] += 1
            TEST_RESULTS["failed_tools"].append({"name": "ipfs_add", "category": "ipfs"})
        
        # Update global test results
        TEST_RESULTS["tests"]["total"] += results["total"]
        TEST_RESULTS["tests"]["passed"] += results["passed"]
        TEST_RESULTS["tests"]["failed"] += results["failed"]
        
        if results["total"] > 0:
            success_rate = (results["passed"] / results["total"]) * 100
            logger.info(f"Basic IPFS tools test complete: {results['passed']}/{results['total']} passed ({success_rate:.2f}%)")
        
        return results
    
    def test_vfs_basic_tools(self):
        """Test basic VFS tools for functionality"""
        logger.info("Testing basic VFS tools...")
        results = {"passed": 0, "failed": 0, "total": 0}
        
        # Generate a unique test directory path
        test_dir = f"/vfs-test-{int(time.time())}"
        test_file = f"{test_dir}/test.txt"
        test_content = "Hello VFS from MCP test runner!"
        
        # Test vfs_mkdir
        results["total"] += 1
        mkdir_result = self.call_jsonrpc("vfs_mkdir", {"path": test_dir})
        if "result" in mkdir_result:
            logger.info(f"PASS: vfs_mkdir created directory {test_dir}")
            results["passed"] += 1
            
            # Test vfs_write
            results["total"] += 1
            write_result = self.call_jsonrpc("vfs_write", {"path": test_file, "content": test_content})
            if "result" in write_result:
                logger.info(f"PASS: vfs_write wrote to {test_file}")
                    results["passed"] += 1
                else:
                    logger.error("FAIL: Did not receive server_info event from SSE")
                    results["failed"] += 1
                
                # Additional check for tool events
                results["total"] += 1
                if tool_update_received:
                    logger.info("PASS: Received tool update event from SSE")
                    results["passed"] += 1
                else:
                    logger.error("FAIL: Did not receive tool update event from SSE")
                    results["failed"] += 1
            else:
                        logger.error(f"FAIL: vfs_read retrieved incorrect content: {content}")
                        results["failed"] += 1
                        TEST_RESULTS["failed_tools"].append({"name": "vfs_read", "category": "vfs"})
                else:
                    error = read_result.get("error", {}).get("message", "Unknown error")
                    logger.error(f"FAIL: vfs_read failed: {error}")
                    results["failed"] += 1
                    TEST_RESULTS["failed_tools"].append({"name": "vfs_read", "category": "vfs"})
                
                # Test vfs_ls
                results["total"] += 1
                ls_result = self.call_jsonrpc("vfs_ls", {"path": test_dir})
                if "result" in ls_result:
                    entries = ls_result["result"]
                    if isinstance(entries, dict) and "entries" in entries:
                        entries = entries["entries"]
                    
                    if isinstance(entries, list) and any(entry.get("name") == "test.txt" for entry in entries):
                        logger.info("PASS: vfs_ls found the test file")
                        results["passed"] += 1
                    else:
                        logger.error(f"FAIL: vfs_ls did not find expected file: {entries}")
                        results["failed"] += 1
                        TEST_RESULTS["failed_tools"].append({"name": "vfs_ls", "category": "vfs"})
                else:
                    error = ls_result.get("error", {}).get("message", "Unknown error")
                    logger.error(f"FAIL: vfs_ls failed: {error}")
                    results["failed"] += 1
                    TEST_RESULTS["failed_tools"].append({"name": "vfs_ls", "category": "vfs"})
                
                # Test vfs_rm
                results["total"] += 1
                rm_result = self.call_jsonrpc("vfs_rm", {"path": test_file})
                if "result" in rm_result:
                    logger.info(f"PASS: vfs_rm removed file {test_file}")
                    results["passed"] += 1
                else:
                    error = rm_result.get("error", {}).get("message", "Unknown error")
                    logger.error(f"FAIL: vfs_rm failed: {error}")
                    results["failed"] += 1
                    TEST_RESULTS["failed_tools"].append({"name": "vfs_rm", "category": "vfs"})
            else:
                error = write_result.get("error", {}).get("message", "Unknown error")
                logger.error(f"FAIL: vfs_write failed: {error}")
                results["failed"] += 1
                TEST_RESULTS["failed_tools"].append({"name": "vfs_write", "category": "vfs"})
            
            # Test vfs_rmdir
            results["total"] += 1
            rmdir_result = self.call_jsonrpc("vfs_rmdir", {"path": test_dir})
            if "result" in rmdir_result:
                logger.info(f"PASS: vfs_rmdir removed directory {test_dir}")
                results["passed"] += 1
            else:
                error = rmdir_result.get("error", {}).get("message", "Unknown error")
                logger.error(f"FAIL: vfs_rmdir failed: {error}")
                results["failed"] += 1
                TEST_RESULTS["failed_tools"].append({"name": "vfs_rmdir", "category": "vfs"})
        else:
            error = mkdir_result.get("error", {}).get("message", "Unknown error")
            logger.error(f"FAIL: vfs_mkdir failed: {error}")
            results["failed"] += 1
            TEST_RESULTS["failed_tools"].append({"name": "vfs_mkdir", "category": "vfs"})
        
        # Update global test results
        TEST_RESULTS["tests"]["total"] += results["total"]
        TEST_RESULTS["tests"]["passed"] += results["passed"]
        TEST_RESULTS["tests"]["failed"] += results["failed"]
        
        if results["total"] > 0:
            success_rate = (results["passed"] / results["total"]) * 100
            logger.info(f"Basic VFS tools test complete: {results['passed']}/{results['total']} passed ({success_rate:.2f}%)")
        
        return results
    def test_ipfs_vfs_integration(self):
        """Test the integration between IPFS and VFS functionality"""
        logger.info("Testing IPFS-VFS integration...")
        results = {"passed": 0, "failed": 0, "total": 0}
        
        # Create a test file with random content
        test_content = ''.join(random.choices(string.ascii_letters + string.digits, k=1024))
        vfs_test_dir = f"/ipfs-vfs-test-{int(time.time())}"
        vfs_test_file = f"{vfs_test_dir}/integration-test.txt"
        
        # Step 1: Create VFS directory
        results["total"] += 1
        mkdir_result = self.call_jsonrpc("vfs_mkdir", {"path": vfs_test_dir})
        if "result" not in mkdir_result:
            logger.error(f"FAIL: Could not create VFS test directory: {mkdir_result.get('error')}")
            results["failed"] += 1
            return results
        results["passed"] += 1
        
        # Step 2: Write content to VFS file
        results["total"] += 1
        write_result = self.call_jsonrpc("vfs_write", {"path": vfs_test_file, "content": test_content})
        if "result" not in write_result:
            logger.error(f"FAIL: Could not write to VFS test file: {write_result.get('error')}")
            results["failed"] += 1
            # Clean up
            self.call_jsonrpc("vfs_rmdir", {"path": vfs_test_dir})
            return results
        results["passed"] += 1
        
        # Step 3: Get IPFS hash of the file through VFS
        results["total"] += 1
        hash_result = self.call_jsonrpc("vfs_stat", {"path": vfs_test_file})
        if "result" not in hash_result or not isinstance(hash_result["result"], dict):
            logger.error(f"FAIL: Could not get VFS stat: {hash_result.get('error')}")
            results["failed"] += 1
            # Clean up
            self.call_jsonrpc("vfs_rm", {"path": vfs_test_file})
            self.call_jsonrpc("vfs_rmdir", {"path": vfs_test_dir})
            return results
        
        # Extract CID from stats
        cid = None
        if "cid" in hash_result["result"]:
            cid = hash_result["result"]["cid"]
        elif "hash" in hash_result["result"]:
            cid = hash_result["result"]["hash"]
        
        if not cid:
            logger.error("FAIL: Could not extract CID from VFS stat")
            results["failed"] += 1
            # Clean up
            self.call_jsonrpc("vfs_rm", {"path": vfs_test_file})
            self.call_jsonrpc("vfs_rmdir", {"path": vfs_test_dir})
            return results
        
        logger.info(f"Got CID from VFS file: {cid}")
        results["passed"] += 1
        
        # Step 4: Access the content via IPFS using the CID
        results["total"] += 1
        cat_result = self.call_jsonrpc("ipfs_cat", {"cid": cid})
        if "result" not in cat_result:
            logger.error(f"FAIL: Could not access content via IPFS: {cat_result.get('error')}")
            results["failed"] += 1
            # Clean up
            self.call_jsonrpc("vfs_rm", {"path": vfs_test_file})
            self.call_jsonrpc("vfs_rmdir", {"path": vfs_test_dir})
            return results
        
        ipfs_content = cat_result["result"]
        if isinstance(ipfs_content, dict) and "content" in ipfs_content:
            ipfs_content = ipfs_content["content"]
        
        if ipfs_content == test_content:
            logger.info("PASS: Successfully accessed VFS file content through IPFS")
            results["passed"] += 1
        else:
            logger.error("FAIL: Content retrieved through IPFS doesn't match original content")
            results["failed"] += 1
        
        # Step 5: Create a new VFS file from IPFS content
        new_test_file = f"{vfs_test_dir}/from-ipfs.txt"
        results["total"] += 1
        import_result = self.call_jsonrpc("vfs_import", {"path": new_test_file, "cid": cid})
        if "result" not in import_result:
            logger.error(f"FAIL: Could not import IPFS content to VFS: {import_result.get('error')}")
            results["failed"] += 1
        else:
            logger.info("PASS: Successfully imported IPFS content to VFS")
            results["passed"] += 1
            
            # Verify the imported content
            results["total"] += 1
            read_result = self.call_jsonrpc("vfs_read", {"path": new_test_file})
            if "result" in read_result:
                imported_content = read_result["result"]
                if isinstance(imported_content, dict) and "content" in imported_content:
                    imported_content = imported_content["content"]
                
                if imported_content == test_content:
                    logger.info("PASS: Content imported from IPFS to VFS matches original")
                    results["passed"] += 1
                else:
                    logger.error("FAIL: Content imported from IPFS to VFS doesn't match original")
                    results["failed"] += 1
            else:
                logger.error(f"FAIL: Could not read imported VFS file: {read_result.get('error')}")
                results["failed"] += 1
        
        # Clean up
        self.call_jsonrpc("vfs_rm", {"path": vfs_test_file})
        self.call_jsonrpc("vfs_rm", {"path": new_test_file})
        self.call_jsonrpc("vfs_rmdir", {"path": vfs_test_dir})
        
        # Update global test results
        TEST_RESULTS["tests"]["total"] += results["total"]
        TEST_RESULTS["tests"]["passed"] += results["passed"]
        TEST_RESULTS["tests"]["failed"] += results["failed"]
        
        if results["total"] > 0:
            success_rate = (results["passed"] / results["total"]) * 100
            logger.info(f"IPFS-VFS integration test complete: {results['passed']}/{results['total']} passed ({success_rate:.2f}%)")
        
        return results
    
    def test_sse_endpoint(self):
        """Test the SSE endpoint for real-time updates"""
        logger.info("Testing SSE endpoint...")
        results = {"passed": 0, "failed": 0, "total": 1}
        
        try {
            # Connect to SSE endpoint with a short timeout
            messages = SSEClient(self.sse_url, timeout=5)
            logger.info("Successfully connected to SSE endpoint")
            
            # Trigger an event by calling a tool
            trigger_time = time.time()
            self.call_jsonrpc("ping")
            
            # Check for events
            event_received = False
            server_info_received = False
            tool_update_received = False
            
            # Listen for a short time
            timeout = time.time() + 10
            
            for msg in messages:
                if time.time() > timeout:
                    break
                    
                if not msg or not msg.data:
                    continue
                    
                try:
                    data = json.loads(msg.data)
                    event_type = data.get('type')
                    logger.info(f"Received SSE event: {event_type}")
                    
                    event_received = True
                    
                    if event_type == 'server_info':
                        server_info_received = True
                        if 'tools' in data and isinstance(data['tools'], list):
                            logger.info(f"Server info event contains {len(data['tools'])} tools")
                            
                    if event_type in ['tool_call', 'tool_result']:
                        tool_update_received = True
                        
                except json.JSONDecodeError:
                    logger.error("Received invalid JSON data from SSE")
            
            # Check success criteria
            if event_received:
                if server_info_received:
                    logger.info("PASS: Received server_info event from SSE")
                    results["passed"] += 1
                else:
                    logger.error("FAIL: Did not receive server_info event from SSE")
                    results["failed"] += 1
                
                # Additional check for tool events
                    if tool_update_received:
                        logger.info("PASS: Received tool update event from SSE")
                        results["passed"] += 1
                    else:
                        logger.error("FAIL: Did not receive tool update event from SSE")
                        results["failed"] += 1
                else:
                    logger.error("FAIL: Did not receive any events from SSE")
                    results["failed"] += 1
            return results
        
        except Exception as e:
            logger.error(f"Error testing SSE endpoint: {e}")
            return {"passed": 0, "failed": 1, "total": 1}
        TEST_RESULTS["tests"]["passed"] += results["passed"]
        TEST_RESULTS["tests"]["failed"] += results["failed"]
        
        if results["total"] > 0:
            success_rate = (results["passed"] / results["total"]) * 100
            logger.info(f"SSE endpoint test complete: {results['passed']}/{results['total']} passed ({success_rate:.2f}%)")
        
        return results
    
    def analyze_tool_coverage(self):
        """Analyze and report on tool coverage of IPFS and VFS functionality"""
        logger.info("Analyzing tool coverage...")
        
        # Get all available tools
        all_tools = self.get_all_tools()
        categories = self.categorize_tools(all_tools)
        
        # Store categories in results
        TEST_RESULTS["categories"] = categories
        
        # Determine coverage
        # This part would normally scan the actual ipfs_kit.py and vfs implementations
        # to determine what percentage of methods are exposed as tools
        
        # For now, check if we have at least some essential tools
        essential_ipfs_tools = ["ipfs_add", "ipfs_cat", "ipfs_version"]
        essential_vfs_tools = ["vfs_read", "vfs_write", "vfs_ls", "vfs_mkdir"]
        
        ipfs_tools = categories.get("ipfs", [])
        vfs_tools = categories.get("vfs", [])
        
        missing_essentials = []
        for tool in essential_ipfs_tools:
            if tool not in ipfs_tools:
                missing_essentials.append(tool)
                
        for tool in essential_vfs_tools:
            if tool not in vfs_tools:
                missing_essentials.append(tool)
        
        if missing_essentials:
            logger.error(f"Missing essential tools: {', '.join(missing_essentials)}")
        else:
            logger.info("All essential tools are implemented")
        
        # Calculate overall coverage metrics
        ipfs_count = len(ipfs_tools)
        vfs_count = len(vfs_tools)
        
        logger.info(f"IPFS tools count: {ipfs_count}")
        logger.info(f"VFS tools count: {vfs_count}")
        
        return {
            "ipfs_tool_count": ipfs_count,
            "vfs_tool_count": vfs_count,
            "missing_essentials": missing_essentials
        }
    
    def run_all_tests(self):
        """Run all tests and return consolidated results"""
        logger.info("Starting comprehensive MCP server tests...")
        
        # Check server health first
        if not self.test_server_health():
            logger.error("Server health check failed. Tests cannot proceed.")
            TEST_RESULTS["tests"]["failed"] += 1
            TEST_RESULTS["tests"]["total"] += 1
            return False
        
        # Run all test suites
        self.test_core_tools()
        self.test_ipfs_basic_tools()
        self.test_vfs_basic_tools()
        self.test_ipfs_vfs_integration()
        self.test_sse_endpoint()
        
        # Analyze tool coverage
        coverage = self.analyze_tool_coverage()
        TEST_RESULTS["coverage"] = coverage
        
        # Calculate final success rate
        total_tests = TEST_RESULTS["tests"]["total"]
        if total_tests > 0:
            TEST_RESULTS["success_rate"] = (TEST_RESULTS["tests"]["passed"] / total_tests) * 100
        
        # Generate a report
        self.generate_report()
        
        # Return overall success status
        return TEST_RESULTS["tests"]["failed"] == 0
    def generate_report(self):
        """Generate a comprehensive test report"""
        logger.info("Generating test report...")
        
        # Save results to JSON file
        with open(DEFAULT_RESULTS_FILE, 'w') as f:
            # Convert sets to lists for JSON serialization
            json_results = TEST_RESULTS.copy()
            json.dump(json_results, f, indent=2)
        
        logger.info(f"Test results saved to {DEFAULT_RESULTS_FILE}")
        
        # Print summary
        total = TEST_RESULTS["tests"]["total"]
        passed = TEST_RESULTS["tests"]["passed"]
        failed = TEST_RESULTS["tests"]["failed"]
        success_rate = TEST_RESULTS["success_rate"]
        
        print("\n" + "="*80)
        print("                     MCP TEST RESULTS SUMMARY                       ")
        print("="*80)
        print(f"Total tests:    {total}")
        print(f"Passed:         {passed}")
        print(f"Failed:         {failed}")
        print(f"Success rate:   {success_rate:.2f}%")
        print("="*80)
        
        if total == 0:
            print("No tests were run!")
        elif failed == 0:
            print("ALL TESTS PASSED! The MCP server implementation is complete and working.")
        else:
            print(f"SOME TESTS FAILED. See {DEFAULT_RESULTS_FILE} for details.")
            
        print("\nTool counts by category:")
        for category, tools in TEST_RESULTS["categories"].items():
            print(f"- {category.upper()}: {len(tools)}")
        
        if TEST_RESULTS.get("coverage", {}).get("missing_essentials"):
            print("\nWARNING: Missing essential tools:")
            for tool in TEST_RESULTS["coverage"]["missing_essentials"]:
                print(f"- {tool}")
                
        print("="*80 + "\n")
def test_ipfs_vfs_integration():
    """Standalone function to test IPFS-VFS integration"""
    runner = MCPTestRunner()
    results = runner.test_ipfs_vfs_integration()
    return results["failed"] == 0
def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(description="MCP Server Test Runner")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port the MCP server is running on")
    parser.add_argument("--server-file", type=str, default=DEFAULT_SERVER_FILE, help="MCP server file")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--integration-test", action="store_true", help="Run only the IPFS-VFS integration test")
    parser.add_argument("--vscode-test", action="store_true", help="Run only the VSCode integration test")
    parser.add_argument("--sse-test", action="store_true", help="Run only the SSE endpoint test")
    parser.add_argument("--results-file", type=str, default=DEFAULT_RESULTS_FILE, help="Results output file")
    
    args = parser.parse_args()
    
    # Configure result file
    global DEFAULT_RESULTS_FILE
    DEFAULT_RESULTS_FILE = args.results_file
    
    # Update server file in results
    TEST_RESULTS["server_file"] = args.server_file
    
    # Create test runner
    runner = MCPTestRunner(port=args.port, server_file=args.server_file, debug=args.debug)
    
    # Run requested test(s)
    success = False
    
    if args.integration_test:
        results = runner.test_ipfs_vfs_integration()
        success = results["failed"] == 0
    elif args.sse_test:
        results = runner.test_sse_endpoint()
        success = results["failed"] == 0
    elif args.vscode_test:
        # Not yet implemented
        print("VSCode integration test not yet implemented")
        success = False
    else:
        # Run all tests
        success = runner.run_all_tests()
    
    # Exit with appropriate status
    sys.exit(0 if success else 1)
if __name__ == "__main__":
    main()
check_ipfs_dependency() {
  log "INFO" "Checking IPFS dependency..." "IPFS"
  
  # Check if IPFS is installed
  if ! command -v ipfs &> /dev/null; then
    log "ERROR" "IPFS is not installed. Please install it and try again." "IPFS"
    log "INFO" "You can install IPFS from https://docs.ipfs.tech/install/command-line/" "IPFS"
    return 1
  else
    local ipfs_version=$(ipfs --version)
    log "INFO" "IPFS is installed: $ipfs_version" "IPFS"
  fi
  
  # Check if IPFS daemon is running
  if ! pgrep -x "ipfs" > /dev/null; then
    log "WARNING" "IPFS daemon is not running. Attempting to start it..." "IPFS"
    
    # Start IPFS daemon in background and redirect output to log file
    mkdir -p "$(dirname "$IPFS_LOG_FILE")"
    ipfs daemon --init &> "$IPFS_LOG_FILE" &
    
    # Save IPFS daemon PID
    local ipfs_pid=$!
    log "INFO" "Started IPFS daemon with PID: $ipfs_pid" "IPFS"
    
    # Wait for IPFS daemon to initialize
    log "INFO" "Waiting for IPFS daemon to initialize..." "IPFS"
    local timeout=30
    local elapsed=0
    local interval=1
    
    while [ $elapsed -lt $timeout ]; do
      # Check if daemon is responsive
      if ipfs swarm peers &> /dev/null; then
        log "SUCCESS" "IPFS daemon is running and responsive" "IPFS"
        return 0
      fi
      
      # Check if daemon is still running
      if ! kill -0 $ipfs_pid 2> /dev/null; then
        log "ERROR" "IPFS daemon process terminated unexpectedly" "IPFS"
        log "ERROR" "Check the log file for details: $IPFS_LOG_FILE" "IPFS"
        return 1
      fi
      
      sleep $interval
      elapsed=$((elapsed + interval))
      
      if [ $((elapsed % 5)) -eq 0 ]; then
        log "INFO" "Still waiting for IPFS daemon to initialize... (${elapsed}s)" "IPFS"
      fi
    done
    
    # If we get here, the timeout was reached
    log "ERROR" "Timeout waiting for IPFS daemon to initialize" "IPFS"
    log "ERROR" "Check the log file for details: $IPFS_LOG_FILE" "IPFS"
    return 1
  else
    # Daemon is already running
    log "SUCCESS" "IPFS daemon is already running" "IPFS"
    
    # Check if daemon is responsive
    if ipfs swarm peers &> /dev/null; then
      log "INFO" "IPFS daemon is responsive" "IPFS"
    else
      log "WARNING" "IPFS daemon appears to be running but is not responsive" "IPFS"
    fi
  fi
  
  return 0
analyze_dependencies() {
  log "INFO" "Analyzing dependencies between MCP tools and IPFS/VFS..." "DEPENDENCIES"
  
  # Create or clear the dependency map file
  echo "{}" > "$DEPENDENCY_MAP_FILE"
  
  # Get list of available tools
  local tools_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}')
  
  # Check if the response contains tools
  if [ $? -ne 0 ] || [[ ! $tools_response == *"tools"* ]]; then
    log "ERROR" "Failed to get list of tools from the server" "DEPENDENCIES"
    return 1
  fi
  
  # Extract the tool list and create a Python script to analyze dependencies
  log "INFO" "Creating dependency analysis script..." "DEPENDENCIES"
  
  # Create a temporary Python script to analyze the dependencies
  local temp_script="dependency_analyzer_$(date +%s).py"
  
  cat > "$temp_script" << 'EOF'
"""
Dependency Analyzer for MCP Tools
This script analyzes the dependencies between MCP tools and IPFS/VFS functionality.
"""
import sys
import json
import os
import requests
import re
from datetime import datetime
jsonrpc_endpoint = os.environ.get("JSONRPC_ENDPOINT")
dependency_map_file = os.environ.get("DEPENDENCY_MAP_FILE")
server_file = os.environ.get("SERVER_FILE")
if not all([jsonrpc_endpoint, dependency_map_file, server_file]):
    print("Error: Missing required environment variables")
    sys.exit(1)
dependency_map = {
    "timestamp": datetime.now().isoformat(),
    "server_file": server_file,
    "tools": {},
    "dependencies": {
        "ipfs": [],
        "vfs": [],
        "other": []
    },
    "coverage": {
        "ipfs_tools_count": 0,
        "vfs_tools_count": 0,
        "other_tools_count": 0,
        "total_tools_count": 0
    }
def get_tools():
    try:
        response = requests.post(
            jsonrpc_endpoint,
            json={"jsonrpc": "2.0", "method": "list_tools", "params": {}, "id": 1}
        )
        if response.status_code == 200:
            return response.json().get("result", {}).get("tools", [])
        else:
            print(f"Error: Failed to fetch tools. Status code: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error fetching tools: {e}")
        return []
tools = get_tools()
print(f"Found {len(tools)} tools")
ipfs_tools = [t for t in tools if t.startswith("ipfs_")]
vfs_tools = [t for t in tools if t.startswith("vfs_")]
other_tools = [t for t in tools if not (t.startswith("ipfs_") or t.startswith("vfs_"))]
dependency_map["coverage"]["ipfs_tools_count"] = len(ipfs_tools)
dependency_map["coverage"]["vfs_tools_count"] = len(vfs_tools)
dependency_map["coverage"]["other_tools_count"] = len(other_tools)
dependency_map["coverage"]["total_tools_count"] = len(tools)
if os.path.exists(server_file):
    with open(server_file, 'r') as f:
        content = f.read()
        
    # Look for IPFS imports and usages
    ipfs_imports = re.findall(r'import\s+.*ipfs.*', content, re.IGNORECASE) or []
    ipfs_usages = re.findall(r'ipfs\.[a-zA-Z_]+', content) or []
    
    # Look for VFS imports and usages
    vfs_imports = re.findall(r'import\s+.*vfs.*', content, re.IGNORECASE) or []
    vfs_usages = re.findall(r'vfs\.[a-zA-Z_]+', content) or []
    
    # Add to dependency map
    dependency_map["dependencies"]["ipfs"] = list(set([u.split('.')[-1] for u in ipfs_usages]))
    dependency_map["dependencies"]["vfs"] = list(set([u.split('.')[-1] for u in vfs_usages]))
    
    # Analyze tools
    for tool in tools:
        # Look for tool implementation in content
        tool_implementations = re.findall(rf'def\s+{tool}\s*\(', content)
        if tool_implementations:
            # Tool is defined in the file
            # Find the function definition and analyze its content
            dependency_map["tools"][tool] = {
                "defined_in": server_file,
                "uses_ipfs": any(ipfs_usage in content for ipfs_usage in ipfs_usages),
                "uses_vfs": any(vfs_usage in content for vfs_usage in vfs_usages)
            }
with open(dependency_map_file, 'w') as f:
    json.dump(dependency_map, f, indent=2)
print(f"Dependency map written to {dependency_map_file}")
print(f"IPFS tools: {dependency_map['coverage']['ipfs_tools_count']}")
print(f"VFS tools: {dependency_map['coverage']['vfs_tools_count']}")
print(f"Other tools: {dependency_map['coverage']['other_tools_count']}")
print(f"Total tools: {dependency_map['coverage']['total_tools_count']}")
report_file = dependency_map_file.replace('.json', '.md')
with open(report_file, 'w') as f:
    f.write("# MCP Tool Dependency Analysis\n\n")
    f.write(f"**Server File:** `{server_file}`  \n")
    f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n\n")
    
    f.write("## Tool Coverage\n\n")
    f.write("| Category | Count |\n")
    f.write("|----------|------:|\n")
    f.write(f"| IPFS Tools | {dependency_map['coverage']['ipfs_tools_count']} |\n")
    f.write(f"| VFS Tools | {dependency_map['coverage']['vfs_tools_count']} |\n")
    f.write(f"| Other Tools | {dependency_map['coverage']['other_tools_count']} |\n")
    f.write(f"| **Total Tools** | **{dependency_map['coverage']['total_tools_count']}** |\n\n")
    
    f.write("## IPFS Dependencies\n\n")
    if dependency_map['dependencies']['ipfs']:
        f.write("| IPFS Function |\n")
        f.write("|---------------|\n")
        for func in sorted(dependency_map['dependencies']['ipfs']):
            f.write(f"| `{func}` |\n")
    else:
        f.write("No IPFS dependencies detected.\n")
    f.write("\n")
    
    f.write("## VFS Dependencies\n\n")
    if dependency_map['dependencies']['vfs']:
        f.write("| VFS Function |\n")
        f.write("|-------------|\n")
        for func in sorted(dependency_map['dependencies']['vfs']):
            f.write(f"| `{func}` |\n")
    else:
        f.write("No VFS dependencies detected.\n")
print(f"Markdown report written to {report_file}")
EOF
  
  # Make the script executable
  chmod +x "$temp_script"
  
  # Run the dependency analyzer
  log "INFO" "Running dependency analysis..." "DEPENDENCIES"
  export JSONRPC_ENDPOINT="$JSONRPC_ENDPOINT"
  export DEPENDENCY_MAP_FILE="$DEPENDENCY_MAP_FILE"
  export SERVER_FILE="$SERVER_FILE"
  
  if python3 "$temp_script"; then
    log "SUCCESS" "Dependency analysis completed successfully" "DEPENDENCIES"
    # Clean up temp script
    rm -f "$temp_script"
    log "INFO" "Dependency map written to: $DEPENDENCY_MAP_FILE" "DEPENDENCIES"
    log "INFO" "Dependency analysis report written to: ${DEPENDENCY_MAP_FILE/.json/.md}" "DEPENDENCIES"
    return 0
  else
    log "ERROR" "Dependency analysis failed" "DEPENDENCIES"
    # Clean up temp script
    rm -f "$temp_script"
    return 1
test_cross_version_compatibility() {
  log "INFO" "Testing cross-version compatibility between MCP server implementations..." "COMPATIBILITY"
  
  # Create a temporary directory for test results
  local temp_dir="${RESULTS_DIR}/cross_compat_$(date +%s)"
  mkdir -p "$temp_dir"
  log "INFO" "Created temporary directory for test results: $temp_dir" "COMPATIBILITY"
  
  # Define common test cases
  local test_content="Hello from cross-version compatibility test!"
  local test_cases=(
    '{"jsonrpc":"2.0","method":"ping","params":{},"id":1}'
    '{"jsonrpc":"2.0","method":"ipfs_add","params":{"content":"'"$test_content"'"},"id":2}'
    '{"jsonrpc":"2.0","method":"vfs_mkdir","params":{"path":"/test-compat"},"id":3}'
    '{"jsonrpc":"2.0","method":"vfs_write","params":{"path":"/test-compat/file.txt","content":"'"$test_content"'"},"id":4}'
    '{"jsonrpc":"2.0","method":"vfs_read","params":{"path":"/test-compat/file.txt"},"id":5}'
    '{"jsonrpc":"2.0","method":"vfs_ls","params":{"path":"/test-compat"},"id":6}'
  )
  
  # Initialize results structure
  local results=()
  
  # Initialize the compatibility report
  cat > "$CROSS_COMPATIBILITY_REPORT" << EOF
Generated: $(date "+%Y-%m-%d %H:%M:%S")
This report compares the behavior of different MCP server implementations
to ensure consistent API behavior across versions.
EOF
  
  # Test each server implementation
  for server_file in "${MCP_SERVER_VERSIONS[@]}"; do
    # Check if the server file exists
    if [ ! -f "$server_file" ]; then
      log "WARNING" "Server file not found: $server_file. Skipping." "COMPATIBILITY"
      continue
    fi
    
    log "INFO" "Testing server implementation: $server_file" "COMPATIBILITY"
    
    # Create a unique log file for this server
    local server_log="$temp_dir/$(basename "$server_file").log"
    local server_result_file="$temp_dir/$(basename "$server_file").json"
    local server_port=$((PORT + 100 + RANDOM % 1000))
    
    # Stop any existing server instance
    stop_server
    
    # Start this server implementation on a different port
    log "INFO" "Starting server on port $server_port..." "COMPATIBILITY"
    python3 "$server_file" --port "$server_port" --debug > "$server_log" 2>&1 &
    
    # Save the PID
    local server_pid=$!
    echo $server_pid > "$SERVER_PID_FILE"
    
    # Wait for server to initialize
    log "INFO" "Waiting for server to initialize..." "COMPATIBILITY"
    local timeout=30
    local elapsed=0
    local interval=1
    local server_ready=false
    
    # Custom endpoint URLs for this server instance
    local server_health_endpoint="http://localhost:${server_port}/health"
    local server_jsonrpc_endpoint="http://localhost:${server_port}/jsonrpc"
    
    while [ $elapsed -lt $timeout ]; do
      if curl -s "$server_health_endpoint" &>/dev/null; then
        # Try a simple ping to ensure JSON-RPC is working
        local ping_response=$(curl -s -X POST "$server_jsonrpc_endpoint" \
          -H "Content-Type: application/json" \
          -d '{"jsonrpc":"2.0","method":"ping","params":{},"id":1}')
        
        if [ $? -eq 0 ] && [[ $ping_response == *"pong"* ]]; then
          server_ready=true
          log "SUCCESS" "Server $server_file is ready on port $server_port" "COMPATIBILITY"
          break
        fi
      fi
      
      sleep $interval
      elapsed=$((elapsed + interval))
      
      if [ $((elapsed % 5)) -eq 0 ]; then
        log "INFO" "Still waiting for server to initialize... (${elapsed}s)" "COMPATIBILITY"
      fi
    done
    
    # If server failed to start, log and continue to next server
    if [ "$server_ready" = "false" ]; then
      log "ERROR" "Server $server_file failed to start properly" "COMPATIBILITY"
      # Show the last few lines of the log
      log "INFO" "Last 10 lines of server log:" "COMPATIBILITY"
      tail -n 10 "$server_log" | while read -r line; do
        log "DEBUG" "$line" "SERVER_LOG"
      done
      
      # Cleanup
      kill -9 $server_pid 2>/dev/null || true
      rm -f "$SERVER_PID_FILE"
      continue
    fi
    
    # Run the test cases
    log "INFO" "Running test cases..." "COMPATIBILITY"
    local server_results=()
    
    # Get available tools
    local tools_response=$(curl -s -X POST "$server_jsonrpc_endpoint" \
      -H "Content-Type: application/json" \
      -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}')
    
    # Save available tools for this server
    echo "$tools_response" > "$server_result_file.tools"
    
    # Run each test case
    for ((i=0; i<${#test_cases[@]}; i++)); do
      local test_case="${test_cases[i]}"
      local test_method=$(echo "$test_case" | grep -o '"method":"[^"]*"' | cut -d':' -f2 | tr -d '"')
      local test_id=$(echo "$test_case" | grep -o '"id":[0-9]*' | cut -d':' -f2)
      
      log "INFO" "Running test case: $test_method (id: $test_id)" "COMPATIBILITY"
      
      local start_time=$(date +%s.%N)
      local response=$(curl -s -X POST "$server_jsonrpc_endpoint" \
        -H "Content-Type: application/json" \
        -d "$test_case")
      local end_time=$(date +%s.%N)
      local elapsed_time=$(echo "$end_time - $start_time" | bc)
      
      # Save response to file
      echo "$response" > "$server_result_file.$test_id"
      
      # Check response validity
      if [[ "$response" == *"result"* ]]; then
        log "SUCCESS" "Test case $test_method succeeded (${elapsed_time}s)" "COMPATIBILITY"
        server_results+=("✓ $test_method")
      elif [[ "$response" == *"error"* ]]; then
        local error_message=$(echo "$response" | grep -o '"message":"[^"]*"' | cut -d':' -f2- | tr -d '"')
        log "WARNING" "Test case $test_method failed: $error_message" "COMPATIBILITY"
        server_results+=("✗ $test_method: $error_message")
      else
        log "ERROR" "Invalid response for test case $test_method" "COMPATIBILITY"
        server_results+=("? $test_method: Invalid response")
      fi
      
      # Add a small delay between requests
      sleep 0.5
    done
    
    # Add results for this server
    results+=("$server_file:${server_results[*]}")
    
    # Add results to the report
    cat >> "$CROSS_COMPATIBILITY_REPORT" << EOF
| Method | Status | Notes |
|--------|--------|-------|
EOF
    
    for result in "${server_results[@]}"; do
      if [[ "$result" == "✓"* ]]; then
        local method=$(echo "$result" | cut -d' ' -f2)
        cat >> "$CROSS_COMPATIBILITY_REPORT" << EOF
| $method | ✅ Pass | |
EOF
      elif [[ "$result" == "✗"* ]]; then
        local method=$(echo "$result" | cut -d' ' -f2 | cut -d':' -f1)
        local error=$(echo "$result" | cut -d':' -f2-)
        cat >> "$CROSS_COMPATIBILITY_REPORT" << EOF
| $method | ❌ Fail | $error |
EOF
      else
        local method=$(echo "$result" | cut -d' ' -f2 | cut -d':' -f1)
        local error=$(echo "$result" | cut -d':' -f2-)
        cat >> "$CROSS_COMPATIBILITY_REPORT" << EOF
| $method | ⚠️ Unknown | $error |
EOF
      fi
    done
    
    cat >> "$CROSS_COMPATIBILITY_REPORT" << EOF
EOF
    
    # Stop the server for this test
    log "INFO" "Stopping server..." "COMPATIBILITY"
    kill -15 "$server_pid" 2>/dev/null || true
    sleep 1
    kill -9 "$server_pid" 2>/dev/null || true
    rm -f "$SERVER_PID_FILE"
  done
  
  # Optionally restart the main server
  if [ "$1" != "--no-restart" ]; then
    log "INFO" "Restarting main MCP server..." "COMPATIBILITY"
    start_server
  fi
  
  log "INFO" "Cross-compatibility report generated: $CROSS_COMPATIBILITY_REPORT" "COMPATIBILITY"
  return 0
generate_ipfs_mapping() {
  log "INFO" "Generating mapping between IPFS Kit tools and MCP API..." "IPFS"
  
  # Create mapping file structure
  cat > "$IPFS_MAPPING_FILE" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "mapping": []
EOF
  
  # Get all available tools from the MCP server
  log "INFO" "Fetching available tools from MCP server..." "IPFS"
  local tools_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}')
  
  # Check if the response contains tools
  if [ $? -ne 0 ] || [[ ! $tools_response == *"tools"* ]]; then
    log "ERROR" "Failed to get list of tools from the server" "IPFS"
    return 1
  fi
  
  # Create a Python script to analyze IPFS tools and generate mapping
  log "INFO" "Creating IPFS mapping analysis script..." "IPFS"
  local temp_script="ipfs_mapping_analyzer_$(date +%s).py"
  
  cat > "$temp_script" << 'EOF'
"""
IPFS Kit to MCP API Mapping Generator
This script analyzes MCP tools that use IPFS and maps them to their
corresponding IPFS functionality.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime
jsonrpc_endpoint = os.environ.get("JSONRPC_ENDPOINT")
mapping_file = os.environ.get("IPFS_MAPPING_FILE")
server_file = os.environ.get("SERVER_FILE")
if not all([jsonrpc_endpoint, mapping_file, server_file]):
    print("Error: Missing required environment variables")
    sys.exit(1)
print("Getting IPFS commands from CLI...")
ipfs_commands = []
try:
    result = subprocess.run(["ipfs", "commands"], capture_output=True, text=True, check=True)
    ipfs_commands = [cmd.strip() for cmd in result.stdout.split("\n") if cmd.strip()]
    print(f"Found {len(ipfs_commands)} IPFS commands from CLI")
except Exception as e:
    print(f"Could not get IPFS commands from CLI: {e}")
print("Getting tools from MCP server...")
import requests
try:
    response = requests.post(
        jsonrpc_endpoint,
        json={"jsonrpc": "2.0", "method": "list_tools", "params": {}, "id": 1}
    )
    if response.status_code != 200:
        print(f"Error: Server returned status {response.status_code}")
        sys.exit(1)
        
    tools_data = response.json()
    if "result" not in tools_data or "tools" not in tools_data["result"]:
        print("Error: Unexpected response format")
        sys.exit(1)
        
    all_tools = tools_data["result"]["tools"]
    # Check if tools is a list of strings or a list of objects
    if all_tools and isinstance(all_tools[0], dict):
        all_tools = [t.get("name", "") for t in all_tools]
        
    ipfs_tools = [t for t in all_tools if t.startswith("ipfs_")]
    print(f"Found {len(ipfs_tools)} IPFS tools in MCP server")
    
except Exception as e:
    print(f"Error getting tools from server: {e}")
    sys.exit(1)
try:
    with open(mapping_file, 'r') as f:
        mapping_data = json.load(f)
except Exception:
    mapping_data = {"timestamp": datetime.now().isoformat(), "mapping": []}
if os.path.exists(server_file):
    print(f"Analyzing server file: {server_file}")
    with open(server_file, 'r') as f:
        content = f.read()
    
    # Build mapping between MCP tools and IPFS commands
    mapping = []
    
    for tool in ipfs_tools:
        # Find the function definition for this tool
        tool_pattern = rf"def\s+{tool}\s*\([^)]*\):(?:\s*[\"\'](?:[^\"\'])*[\"\'])?((?:.|\n)*?)(?:def\s+|$)"
        matches = re.findall(tool_pattern, content)
        
        if matches:
            tool_impl = matches[0]
            # Look for IPFS calls within the implementation
            ipfs_calls = re.findall(r'ipfs\.([a-zA-Z_]+)', tool_impl)
            ipfs_shell_calls = re.findall(r'subprocess\.(?:run|call|Popen).*?\["ipfs",\s*"([^"]+)"', tool_impl)
            
            # Find parameters
            param_match = re.search(rf"def\s+{tool}\s*\(([^)]*)\)", content)
            params = []
            if param_match:
                param_str = param_match.group(1)
                # Remove 'self' parameter if present
                param_str = re.sub(r'self,?\s*', '', param_str)
                # Extract parameter names
                params = [p.strip().split('=')[0].strip() for p in param_str.split(',') if p.strip()]
            
            # Find docstring
            docstring = ""
            docstring_match = re.search(rf'def\s+{tool}\s*\([^)]*\):\s*[\"\']([^\"\']*)[\"\']', content)
            if docstring_match:
                docstring = docstring_match.group(1).strip()
            
            # Create mapping entry
            ipfs_method = ""
            if ipfs_calls:
                ipfs_method = ipfs_calls[0]
            elif ipfs_shell_calls:
                ipfs_method = ipfs_shell_calls[0]
            
            # Match with CLI command if possible
            cli_command = ""
            if ipfs_method:
                for cmd in ipfs_commands:
                    if cmd.endswith(ipfs_method) or ipfs_method.endswith(cmd):
                        cli_command = cmd
                        break
            
            mapping.append({
                "mcp_tool": tool,
                "ipfs_method": ipfs_method,
                "ipfs_cli_command": cli_command,
                "parameters": params,
                "description": docstring
            })
        else:
            # If no implementation found, add a placeholder
            mapping.append({
                "mcp_tool": tool,
                "ipfs_method": "",
                "ipfs_cli_command": "",
                "parameters": [],
                "description": "Implementation not found"
            })
    
    # Update the mapping data
    mapping_data["mapping"] = mapping
    mapping_data["timestamp"] = datetime.now().isoformat()
    
    # Write updated mapping to file
    with open(mapping_file, 'w') as f:
        json.dump(mapping_data, f, indent=2)
    
    print(f"Updated mapping file: {mapping_file}")
    
    # Generate markdown report
    md_file = mapping_file.replace(".json", ".md")
    with open(md_file, 'w') as f:
        f.write("# IPFS Kit to MCP API Mapping\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("This document maps MCP API tools to their corresponding IPFS functionality.\n\n")
        
        f.write("## MCP Tools to IPFS Methods\n\n")
        f.write("| MCP Tool | IPFS Method | IPFS CLI Command | Parameters | Description |\n")
        f.write("|----------|------------|-----------------|------------|-------------|\n")
        
        for entry in mapping:
            # Format parameters as comma-separated list
            params = ", ".join(entry["parameters"]) if entry["parameters"] else "-"
            
            f.write(f"| `{entry['mcp_tool']}` | `{entry['ipfs_method'] or '-'}` | " +
                    f"`{entry['ipfs_cli_command'] or '-'}` | {params} | " +
                    f"{entry['description'] or '-'} |\n")
        
        # Add coverage section
        total_ipfs_commands = len(ipfs_commands) if ipfs_commands else "unknown"
        covered_count = sum(1 for entry in mapping if entry["ipfs_method"])
        
        f.write("\n## Coverage Analysis\n\n")
        f.write(f"- **Total IPFS commands available:** {total_ipfs_commands}\n")
        f.write(f"- **MCP tools implementing IPFS functionality:** {len(mapping)}\n")
        f.write(f"- **MCP tools with identified IPFS methods:** {covered_count}\n")
        
        if ipfs_commands:
            coverage_pct = (covered_count / len(ipfs_commands)) * 100 if ipfs_commands else 0
            f.write(f"- **Approximate IPFS coverage:** {coverage_pct:.1f}%\n\n")
            
            # List uncovered IPFS commands
            covered_commands = [entry["ipfs_cli_command"] for entry in mapping if entry["ipfs_cli_command"]]
            uncovered = [cmd for cmd in ipfs_commands if cmd not in covered_commands]
            
            if uncovered:
                f.write("\n### Uncovered IPFS Commands\n\n")
                for cmd in sorted(uncovered):
                    f.write(f"- `{cmd}`\n")
    
    print(f"Generated markdown report: {md_file}")
else:
    print(f"Server file not found: {server_file}")
    sys.exit(1)
EOF
  
  # Make the script executable
  chmod +x "$temp_script"
  
  # Run the IPFS mapping generator
  log "INFO" "Running IPFS mapping analysis..." "IPFS"
  export JSONRPC_ENDPOINT="$JSONRPC_ENDPOINT"
  export IPFS_MAPPING_FILE="$IPFS_MAPPING_FILE"
  export SERVER_FILE="$SERVER_FILE"
  
  if python3 "$temp_script"; then
    log "SUCCESS" "IPFS mapping analysis completed successfully" "IPFS"
    # Clean up temp script
    rm -f "$temp_script"
    log "INFO" "IPFS mapping written to: $IPFS_MAPPING_FILE" "IPFS"
    log "INFO" "IPFS mapping report written to: ${IPFS_MAPPING_FILE/.json/.md}" "IPFS"
    return 0
  else
    log "ERROR" "IPFS mapping analysis failed" "IPFS"
    # Clean up temp script
    rm -f "$temp_script"
    return 1
  fi
check_mcp_tools_coverage() {
  log "INFO" "Checking MCP tools coverage..." "COVERAGE"
  
  # Create coverage report file
  local coverage_report="${COVERAGE_FILE/.json/.md}"
  
  # Get list of available tools
  log "INFO" "Fetching available tools from MCP server..." "COVERAGE"
  local tools_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}')
  
  # Check if the response contains tools
  if [ $? -ne 0 ] || [[ ! $tools_response == *"tools"* ]]; then
    log "ERROR" "Failed to get list of tools from the server" "COVERAGE"
    return 1
  fi
  
  # Create a Python script to analyze tool coverage
  log "INFO" "Creating tool coverage analysis script..." "COVERAGE"
  local temp_script="tools_coverage_analyzer_$(date +%s).py"
  
  cat > "$temp_script" << 'EOF'
"""
MCP Tools Coverage Analyzer
This script analyzes the coverage of MCP tools against expected functionality.
"""
import json
import os
import re
import sys
from datetime import datetime
EXPECTED_CATEGORIES = {
    "core": ["ping", "health", "list_tools"],
    "ipfs": [
        "ipfs_version", "ipfs_add", "ipfs_cat", "ipfs_get", 
        "ipfs_ls", "ipfs_pin_add", "ipfs_pin_ls", "ipfs_pin_rm"
    ],
    "vfs": [
        "vfs_read", "vfs_write", "vfs_ls", "vfs_mkdir", 
        "vfs_rm", "vfs_rmdir", "vfs_stat", "vfs_import", "vfs_export"
    ]
jsonrpc_endpoint = os.environ.get("JSONRPC_ENDPOINT")
coverage_file = os.environ.get("COVERAGE_FILE")
tools_response = os.environ.get("TOOLS_RESPONSE")
if not all([jsonrpc_endpoint, coverage_file]):
    print("Error: Missing required environment variables")
    sys.exit(1)
import requests
all_tools = []
if tools_response:
    try:
        tools_data = json.loads(tools_response)
        if "result" in tools_data and "tools" in tools_data["result"]:
            all_tools = tools_data["result"]["tools"]
    except Exception as e:
        print(f"Error parsing tools response: {e}")
if not all_tools:
    try:
        response = requests.post(
            jsonrpc_endpoint,
            json={"jsonrpc": "2.0", "method": "list_tools", "params": {}, "id": 1}
        )
        if response.status_code == 200:
            tools_data = response.json()
            if "result" in tools_data and "tools" in tools_data["result"]:
                all_tools = tools_data["result"]["tools"]
        else:
            print(f"Error: Server returned status {response.status_code}")
    except Exception as e:
        print(f"Error fetching tools from server: {e}")
normalized_tools = []
for tool in all_tools:
    if isinstance(tool, dict) and "name" in tool:
        normalized_tools.append(tool["name"])
    elif isinstance(tool, str):
        normalized_tools.append(tool)
all_tools = normalized_tools
print(f"Found {len(all_tools)} tools")
categorized_tools = {
    "core": [],
    "ipfs": [],
    "vfs": [],
    "other": []
for tool in all_tools:
    if tool in EXPECTED_CATEGORIES["core"]:
        categorized_tools["core"].append(tool)
    elif tool.startswith("ipfs_"):
        categorized_tools["ipfs"].append(tool)
    elif tool.startswith("vfs_"):
        categorized_tools["vfs"].append(tool)
    else:
        categorized_tools["other"].append(tool)
coverage_metrics = {}
for category, expected in EXPECTED_CATEGORIES.items():
    available = categorized_tools.get(category, [])
    
    # Find missing essential tools
    missing = [tool for tool in expected if tool not in available]
    
    # Calculate coverage percentage
    if expected:
        found = sum(1 for tool in expected if tool in available)
        coverage_pct = (found / len(expected)) * 100
    else:
        coverage_pct = 0
    
    # Store metrics
    coverage_metrics[category] = {
        "expected": len(expected),
        "available": len(available),
        "essential_found": len(expected) - len(missing),
        "coverage_percent": coverage_pct,
        "missing": missing
    }
coverage_data = {
    "timestamp": datetime.now().isoformat(),
    "total_tools": len(all_tools),
    "categories": {
        "core": len(categorized_tools["core"]),
        "ipfs": len(categorized_tools["ipfs"]),
        "vfs": len(categorized_tools["vfs"]),
        "other": len(categorized_tools["other"])
    },
    "metrics": coverage_metrics,
    "tools_by_category": categorized_tools
with open(coverage_file, 'w') as f:
    json.dump(coverage_data, f, indent=2)
print(f"Coverage data written to: {coverage_file}")
md_file = coverage_file.replace(".json", ".md")
with open(md_file, 'w') as f:
    f.write("# MCP Tools Coverage Report\n\n")
    f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    
    f.write("## Overview\n\n")
    f.write(f"- **Total tools available:** {len(all_tools)}\n")
    
    # Tool counts by category
    f.write("\n## Tool Distribution\n\n")
    f.write("| Category | Count | Percentage |\n")
    f.write("|----------|------:|-----------:|\n")
    
    for category, tools in categorized_tools.items():
        percentage = (len(tools) / len(all_tools)) * 100 if all_tools else 0
        f.write(f"| {category.upper()} | {len(tools)} | {percentage:.1f}% |\n")
    
    # Coverage metrics
    f.write("\n## Essential Coverage\n\n")
    f.write("| Category | Essential Tools | Found | Coverage |\n")
    f.write("|----------|-----------------:|------:|---------:|\n")
    
    for category, metrics in coverage_metrics.items():
        f.write(f"| {category.upper()} | {metrics['expected']} | {metrics['essential_found']} | {metrics['coverage_percent']:.1f}% |\n")
    
    # Missing essential tools
    f.write("\n## Missing Essential Tools\n\n")
    missing_any = False
    
    for category, metrics in coverage_metrics.items():
        if metrics['missing']:
            missing_any = True
            f.write(f"### {category.upper()}\n\n")
            for tool in metrics['missing']:
                f.write(f"- `{tool}`\n")
            f.write("\n")
    
    if not missing_any:
        f.write("All essential tools are implemented! 🎉\n")
    
    # Full tool lists by category
    f.write("\n## Available Tools by Category\n\n")
    
    for category, tools in categorized_tools.items():
        if tools:
            f.write(f"### {category.upper()}\n\n")
            for tool in sorted(tools):
                f.write(f"- `{tool}`\n")
            f.write("\n")
print(f"Coverage report written to: {md_file}")
EOF
  
  # Make the script executable
  chmod +x "$temp_script"
  
  # Run the coverage analyzer
  log "INFO" "Running tools coverage analysis..." "COVERAGE"
  export JSONRPC_ENDPOINT="$JSONRPC_ENDPOINT"
  export COVERAGE_FILE="$COVERAGE_FILE"
  export TOOLS_RESPONSE="$tools_response"
  
  if python3 "$temp_script"; then
    log "SUCCESS" "Tools coverage analysis completed successfully" "COVERAGE"
    # Clean up temp script
    rm -f "$temp_script"
    log "INFO" "Coverage data written to: $COVERAGE_FILE" "COVERAGE"
    log "INFO" "Coverage report written to: ${COVERAGE_FILE/.json/.md}" "COVERAGE"
    return 0
  else
    log "ERROR" "Tools coverage analysis failed" "COVERAGE"
    # Clean up temp script
    rm -f "$temp_script"
    return 1
  fi
run_comprehensive_test_suite() {
  log "INFO" "Running comprehensive MCP test suite..." "TEST"
  
  # Create directory for test results
  mkdir -p "$RESULTS_DIR"
  
  # Create summary file
  cat > "$SUMMARY_FILE" << EOF
**Generated:** $(date "+%Y-%m-%d %H:%M:%S")
- Server: $SERVER_FILE
- Port: $PORT
EOF
  
  # Run MCP test runner if available
  log "INFO" "Checking for MCP test runner..." "TEST"
  
  if [ -f "mcp_test_runner.py" ]; then
    log "INFO" "Running comprehensive MCP tests with test runner..." "TEST"
    
    # Execute the test runner and capture the output
    local test_results_file="${RESULTS_DIR}/test_runner_$(date +%Y%m%d_%H%M%S).json"
    local test_runner_output="${RESULTS_DIR}/test_runner_$(date +%Y%m%d_%H%M%S).log"
    
    log "INFO" "Executing test runner..." "TEST"
    python3 mcp_test_runner.py --port "$PORT" --server-file "$SERVER_FILE" --results-file "$test_results_file" > "$test_runner_output" 2>&1
    local test_runner_status=$?
    
    if [ $test_runner_status -eq 0 ]; then
      log "SUCCESS" "Test runner completed successfully" "TEST"
      cat >> "$SUMMARY_FILE" << EOF
✅ **PASSED**
See detailed results in:
- $test_results_file
- $test_runner_output
EOF
    else
      log "ERROR" "Test runner reported failures" "TEST"
      cat >> "$SUMMARY_FILE" << EOF
❌ **FAILED**
See error details in:
- $test_runner_output
EOF
    fi
  else
    log "INFO" "MCP test runner not found, running basic tests instead" "TEST"
    
    # Run basic tests manually
    log "INFO" "Running basic JSONRPC tests..." "TEST"
    
    # Ping test
    local ping_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
      -H "Content-Type: application/json" \
      -d '{"jsonrpc":"2.0","method":"ping","params":{},"id":1}')
    
    if [[ "$ping_response" == *"pong"* ]]; then
      log "SUCCESS" "Ping test passed" "TEST"
      local ping_status="✅ PASSED"
    else
      log "ERROR" "Ping test failed: $ping_response" "TEST"
      local ping_status="❌ FAILED"
    fi
    
    # Tool list test
    local tools_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
      -H "Content-Type: application/json" \
      -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}')
    
    if [[ "$tools_response" == *"tools"* ]]; then
      log "SUCCESS" "Tool list test passed" "TEST"
      local tools_status="✅ PASSED"
    else
      log "ERROR" "Tool list test failed: $tools_response" "TEST"
      local tools_status="❌ FAILED"
    fi
    
    # IPFS test
    local ipfs_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
      -H "Content-Type: application/json" \
      -d '{"jsonrpc":"2.0","method":"ipfs_version","params":{},"id":1}')
    
    if [[ "$ipfs_response" == *"result"* ]]; then
      log "SUCCESS" "IPFS test passed" "TEST"
      local ipfs_status="✅ PASSED"
    else
      log "ERROR" "IPFS test failed: $ipfs_response" "TEST"
      local ipfs_status="❌ FAILED"
    fi
    
    # VFS test
    local vfs_response=$(curl -s -X POST "$JSONRPC_ENDPOINT" \
      -H "Content-Type: application/json" \
      -d '{"jsonrpc":"2.0","method":"vfs_mkdir","params":{"path":"/test-dir"},"id":1}')
    
    if [[ "$vfs_response" == *"result"* ]]; then
      log "SUCCESS" "VFS test passed" "TEST"
      local vfs_status="✅ PASSED"
    else
      log "ERROR" "VFS test failed: $vfs_response" "TEST"
      local vfs_status="❌ FAILED"
    fi
    
    # Add results to summary
    cat >> "$SUMMARY_FILE" << EOF
- Ping: $ping_status
- Tool List: $tools_status
- IPFS Version: $ipfs_status
- VFS Directory Creation: $vfs_status
EOF
  fi
  
  # Run dependency analysis
  log "INFO" "Running dependency analysis..." "TEST"
  if analyze_dependencies; then
    log "SUCCESS" "Dependency analysis completed" "TEST"
    cat >> "$SUMMARY_FILE" << EOF
✅ **COMPLETED**
See detailed results in:
- $DEPENDENCY_MAP_FILE
- ${DEPENDENCY_MAP_FILE/.json/.md}
EOF
  else
    log "ERROR" "Dependency analysis failed" "TEST"
    cat >> "$SUMMARY_FILE" << EOF
❌ **FAILED**
EOF
  fi
  
  # Run IPFS mapping
  log "INFO" "Running IPFS mapping generation..." "TEST"
  if generate_ipfs_mapping; then
    log "SUCCESS" "IPFS mapping generation completed" "TEST"
    cat >> "$SUMMARY_FILE" << EOF
✅ **COMPLETED**
See detailed results in:
- $IPFS_MAPPING_FILE
- ${IPFS_MAPPING_FILE/.json/.md}
EOF
  else
    log "ERROR" "IPFS mapping generation failed" "TEST"
    cat >> "$SUMMARY_FILE" << EOF
❌ **FAILED**
EOF
  fi
  
  # Run tools coverage analysis
  log "INFO" "Running tools coverage analysis..." "TEST"
  if check_mcp_tools_coverage; then
    log "SUCCESS" "Tools coverage analysis completed" "TEST"
    cat >> "$SUMMARY_FILE" << EOF
✅ **COMPLETED**
See detailed results in:
- $COVERAGE_FILE
- ${COVERAGE_FILE/.json/.md}
EOF
  else
    log "ERROR" "Tools coverage analysis failed" "TEST"
    cat >> "$SUMMARY_FILE" << EOF
❌ **FAILED**
EOF
  fi
  
  # Run cross-version compatibility test if multiple server versions are available
  local available_versions=0
  for server_file in "${MCP_SERVER_VERSIONS[@]}"; do
    if [ -f "$server_file" ]; then
      available_versions=$((available_versions + 1))
    fi
  done
  
  if [ $available_versions -gt 1 ]; then
    log "INFO" "Running cross-version compatibility tests..." "TEST"
    if test_cross_version_compatibility; then
      log "SUCCESS" "Cross-version compatibility tests completed" "TEST"
      cat >> "$SUMMARY_FILE" << EOF
✅ **COMPLETED**
See detailed results in:
- $CROSS_COMPATIBILITY_REPORT
EOF
    else
      log "ERROR" "Cross-version compatibility tests failed" "TEST"
      cat >> "$SUMMARY_FILE" << EOF
❌ **FAILED**
EOF
    fi
  else
    log "INFO" "Skipping cross-version compatibility tests (need at least 2 server versions)" "TEST"
    cat >> "$SUMMARY_FILE" << EOF
⚠️ **SKIPPED** (need at least 2 server versions)
EOF
  fi
  
  # Add timestamp to summary
  cat >> "$SUMMARY_FILE" << EOF
- Tests completed: $(date "+%Y-%m-%d %H:%M:%S")
- Log file: $LOG_FILE
EOF
  
  log "SUCCESS" "Comprehensive test suite completed" "TEST"
  log "INFO" "Summary report written to: $SUMMARY_FILE" "TEST"
  
  return 0
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
Generated: $(date "+%Y-%m-%d %H:%M:%S")
| Component | Status | 
|-----------|--------|
| IPFS Tools | $(if $ipfs_tools_working; then echo "✅ WORKING"; else echo "❌ FAILURE"; fi) |
| VFS Tools | $(if $vfs_tools_working; then echo "✅ WORKING"; else echo "❌ FAILURE"; fi) |
| Integration | $(if $integration_working; then echo "✅ WORKING"; else echo "❌ FAILURE"; fi) |
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
Generated: $(date "+%Y-%m-%d %H:%M:%S")
| Category | Available | Expected | Coverage |
|----------|-----------|----------|----------|
| IPFS Tools | $ipfs_found | ${#expected_ipfs_functions[@]} | $ipfs_coverage% |
| VFS Tools | $vfs_found | ${#expected_vfs_functions[@]} | $vfs_coverage% |
| **Total** | $((ipfs_found + vfs_found)) | $((${#expected_ipfs_functions[@]} + ${#expected_vfs_functions[@]})) | $total_coverage% |
EOF
  if [ ${#missing_ipfs[@]} -eq 0 ]; then
    echo "- *None - All expected IPFS functions are implemented*" >> "$report_file"
  else
    for func in "${missing_ipfs[@]}"; do
      echo "- \`$func\`" >> "$report_file"
    done
  fi
  
  cat >> "$report_file" << EOF
EOF
  if [ ${#missing_vfs[@]} -eq 0 ]; then
    echo "- *None - All expected VFS functions are implemented*" >> "$report_file"
  else
    for func in "${missing_vfs[@]}"; do
      echo "- \`$func\`" >> "$report_file"
    done
  fi
  
  cat >> "$report_file" << EOF
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
main "$@"
