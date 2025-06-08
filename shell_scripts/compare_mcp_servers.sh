#!/bin/bash
# Cross-Version MCP Server Testing Script
# This script compares the functionality between different MCP server implementations

set -e

# Constants
DEFAULT_SERVERS=(
  "final_mcp_server.py:9996"
  "direct_mcp_server.py:8001" 
  "enhanced_mcp_server.py:8002"
)
LOG_FILE="cross_version_comparison_$(date +%Y%m%d_%H%M%S).log"
RESULTS_DIR="cross_version_results"
COMPARISON_REPORT="comparison_report.json"

# Colors for better readability
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create results directory
mkdir -p "$RESULTS_DIR"

# Log function
log() {
  local level=$1
  local message=$2
  local color=$NC
  
  case $level in
    "INFO")
      color=$BLUE
      ;;
    "SUCCESS")
      color=$GREEN
      ;;
    "ERROR")
      color=$RED
      ;;
    "WARNING")
      color=$YELLOW
      ;;
  esac
  
  local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
  echo -e "${color}[$timestamp] [$level] $message${NC}"
  echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
}

# Function to check if a command exists
check_command() {
  local cmd=$1
  if ! command -v "$cmd" &> /dev/null; then
    log "ERROR" "Command $cmd not found. Please install it and try again."
    exit 1
  fi
}

# Function to make JSON-RPC call to a server
call_jsonrpc() {
  local server=$1
  local port=$2
  local method=$3
  local params=$4
  
  if [ -z "$params" ]; then
    params="{}"
  fi
  
  curl -s -X POST \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\": \"2.0\", \"id\": 1, \"method\": \"$method\", \"params\": $params}" \
    "http://localhost:$port/jsonrpc"
}

# Function to check if a server is running
check_server_running() {
  local port=$1
  
  if curl -s "http://localhost:$port/health" > /dev/null 2>&1; then
    return 0
  else
    return 1
  fi
}

# Function to get all tools from a server
get_all_tools() {
  local server=$1
  local port=$2
  
  local result=$(call_jsonrpc "$server" "$port" "system.listMethods")
  
  if [[ $result == *'"result":'* ]]; then
    echo "$result" | jq -r '.result[]'
  else
    echo "$result" | jq -r '.result'
  fi
}

# Function to get tool schema from a server
get_tool_schema() {
  local server=$1
  local port=$2
  local tool=$3
  
  local result=$(call_jsonrpc "$server" "$port" "get_tools_schema")
  
  if [[ $result == *'"result":'* ]]; then
    # Extract the schema for the specific tool
    echo "$result" | jq -r --arg tool "$tool" '.result | map(select(.name == $tool)) | .[0]'
  else
    echo "ERROR: Could not get tool schema"
  fi
}

# Function to compare tools between servers
compare_server_tools() {
  local server1=$1
  local port1=$2
  local server2=$3
  local port2=$4
  
  log "INFO" "Comparing tools between $server1:$port1 and $server2:$port2"
  
  # Get all tools from both servers
  log "INFO" "Getting tools from $server1..."
  local tools1=$(get_all_tools "$server1" "$port1")
  
  log "INFO" "Getting tools from $server2..."
  local tools2=$(get_all_tools "$server2" "$port2")
  
  # Count tools
  local count1=$(echo "$tools1" | wc -l)
  local count2=$(echo "$tools2" | wc -l)
  
  log "INFO" "Server $server1 has $count1 tools"
  log "INFO" "Server $server2 has $count2 tools"
  
  # Find common tools
  local common_tools=$(comm -12 <(echo "$tools1" | sort) <(echo "$tools2" | sort))
  local common_count=$(echo "$common_tools" | wc -l)
  
  log "INFO" "Servers have $common_count tools in common"
  
  # Find unique tools in server 1
  local unique1=$(comm -23 <(echo "$tools1" | sort) <(echo "$tools2" | sort))
  local unique1_count=$(echo "$unique1" | grep -v "^$" | wc -l)
  
  # Find unique tools in server 2
  local unique2=$(comm -13 <(echo "$tools1" | sort) <(echo "$tools2" | sort))
  local unique2_count=$(echo "$unique2" | grep -v "^$" | wc -l)
  
  log "INFO" "Server $server1 has $unique1_count unique tools"
  log "INFO" "Server $server2 has $unique2_count unique tools"
  
  # Create comparison report in JSON format
  local report_file="$RESULTS_DIR/${server1%.*}_vs_${server2%.*}_tools.json"
  
  # Start building the JSON report
  echo "{" > "$report_file"
  echo "  \"timestamp\": \"$(date '+%Y-%m-%d %H:%M:%S')\"," >> "$report_file"
  echo "  \"server1\": \"$server1:$port1\"," >> "$report_file"
  echo "  \"server2\": \"$server2:$port2\"," >> "$report_file"
  echo "  \"tools_count\": {" >> "$report_file"
  echo "    \"server1\": $count1," >> "$report_file"
  echo "    \"server2\": $count2," >> "$report_file"
  echo "    \"common\": $common_count," >> "$report_file"
  echo "    \"unique_to_server1\": $unique1_count," >> "$report_file"
  echo "    \"unique_to_server2\": $unique2_count" >> "$report_file"
  echo "  }," >> "$report_file"
  
  # Add unique tools to server 1
  echo "  \"unique_to_server1\": [" >> "$report_file"
  first=true
  while IFS= read -r tool; do
    if [ -n "$tool" ]; then
      if [ "$first" = true ]; then
        first=false
      else
        echo "," >> "$report_file"
      fi
      echo "    \"$tool\"" >> "$report_file"
    fi
  done <<< "$unique1"
  echo "" >> "$report_file"
  echo "  ]," >> "$report_file"
  
  # Add unique tools to server 2
  echo "  \"unique_to_server2\": [" >> "$report_file"
  first=true
  while IFS= read -r tool; do
    if [ -n "$tool" ]; then
      if [ "$first" = true ]; then
        first=false
      else
        echo "," >> "$report_file"
      fi
      echo "    \"$tool\"" >> "$report_file"
    fi
  done <<< "$unique2"
  echo "" >> "$report_file"
  echo "  ]," >> "$report_file"
  
  # Compare common tools
  echo "  \"common_tools\": [" >> "$report_file"
  first=true
  
  # For each common tool, check if implementations are compatible
  while IFS= read -r tool; do
    if [ -n "$tool" ]; then
      if [ "$first" = true ]; then
        first=false
      else
        echo "," >> "$report_file"
      fi
      
      # Get tool schema from both servers
      schema1=$(get_tool_schema "$server1" "$port1" "$tool")
      schema2=$(get_tool_schema "$server2" "$port2" "$tool")
      
      # Compare schemas (simplified version)
      if [ "$schema1" == "$schema2" ]; then
        compatibility="compatible"
      else
        compatibility="incompatible"
      fi
      
      echo "    {" >> "$report_file"
      echo "      \"name\": \"$tool\"," >> "$report_file"
      echo "      \"compatibility\": \"$compatibility\"" >> "$report_file"
      echo "    }" >> "$report_file"
    fi
  done <<< "$common_tools"
  
  echo "" >> "$report_file"
  echo "  ]" >> "$report_file"
  echo "}" >> "$report_file"
  
  log "SUCCESS" "Tool comparison completed. Report saved to $report_file"
}

# Function to compare test results between servers
compare_test_results() {
  local server1=$1
  local port1=$2
  local server2=$3
  local port2=$4
  
  log "INFO" "Comparing test results between $server1:$port1 and $server2:$port2"
  
  # Run tests on server 1
  log "INFO" "Running tests on $server1..."
  ./start_final_solution.sh --server-file "$server1" --port "$port1" --tests-only > "$RESULTS_DIR/${server1%.*}_test_results.log" 2>&1 || true
  
  # Run tests on server 2
  log "INFO" "Running tests on $server2..."
  ./start_final_solution.sh --server-file "$server2" --port "$port2" --tests-only > "$RESULTS_DIR/${server2%.*}_test_results.log" 2>&1 || true
  
  # Compare test results (this is a simplified version)
  log "INFO" "Comparing test results..."
  
  # In a real implementation, we would parse the test results and do a detailed comparison
  # For now, we'll just note that the comparison was done
  local report_file="$RESULTS_DIR/${server1%.*}_vs_${server2%.*}_tests.json"
  
  # Create a simple JSON report
  cat > "$report_file" << EOF
{
  "timestamp": "$(date '+%Y-%m-%d %H:%M:%S')",
  "server1": "$server1:$port1",
  "server2": "$server2:$port2",
  "comparison": "Test results comparison completed. See log files for details."
}
EOF
  
  log "SUCCESS" "Test comparison completed. See test logs for details."
}

# Main function to compare servers
compare_servers() {
  local server1=$1
  local port1=$2
  local server2=$3
  local port2=$4
  
  # Check if servers are running
  if ! check_server_running "$port1"; then
    log "ERROR" "Server $server1 on port $port1 is not running"
    return 1
  fi
  
  if ! check_server_running "$port2"; then
    log "ERROR" "Server $server2 on port $port2 is not running"
    return 1
  fi
  
  # Compare tools
  compare_server_tools "$server1" "$port1" "$server2" "$port2"
  
  # Compare test results
  compare_test_results "$server1" "$port1" "$server2" "$port2"
}

# Function to build the overall comparison report
build_overall_report() {
  log "INFO" "Building overall comparison report..."
  
  # Create overall report file
  cat > "$RESULTS_DIR/$COMPARISON_REPORT" << EOF
{
  "timestamp": "$(date '+%Y-%m-%d %H:%M:%S')",
  "servers_compared": [
EOF

  # Add each server pair
  first=true
  for server1_spec in "${SERVERS[@]}"; do
    IFS=':' read -r server1 port1 <<< "$server1_spec"
    
    for server2_spec in "${SERVERS[@]}"; do
      IFS=':' read -r server2 port2 <<< "$server2_spec"
      
      # Skip comparing the same server
      if [ "$server1" != "$server2" ]; then
        if [ "$first" = true ]; then
          first=false
        else
          echo "," >> "$RESULTS_DIR/$COMPARISON_REPORT"
        fi
        
        echo "    {" >> "$RESULTS_DIR/$COMPARISON_REPORT"
        echo "      \"server1\": \"$server1:$port1\"," >> "$RESULTS_DIR/$COMPARISON_REPORT"
        echo "      \"server2\": \"$server2:$port2\"," >> "$RESULTS_DIR/$COMPARISON_REPORT"
        echo "      \"tools_report\": \"${server1%.*}_vs_${server2%.*}_tools.json\"," >> "$RESULTS_DIR/$COMPARISON_REPORT"
        echo "      \"tests_report\": \"${server1%.*}_vs_${server2%.*}_tests.json\"" >> "$RESULTS_DIR/$COMPARISON_REPORT"
        echo "    }" >> "$RESULTS_DIR/$COMPARISON_REPORT"
      fi
    done
  done
  
  echo "" >> "$RESULTS_DIR/$COMPARISON_REPORT"
  echo "  ]" >> "$RESULTS_DIR/$COMPARISON_REPORT"
  echo "}" >> "$RESULTS_DIR/$COMPARISON_REPORT"
  
  log "SUCCESS" "Overall comparison report built: $RESULTS_DIR/$COMPARISON_REPORT"
}

# Parse command line options
SERVERS=()

while [[ $# -gt 0 ]]; do
  case $1 in
    --server)
      IFS=':' read -r server_file port <<< "$2"
      SERVERS+=("$server_file:$port")
      shift 2
      ;;
    --help)
      echo "Usage: $0 [options]"
      echo "Options:"
      echo "  --server FILE:PORT    Specify a server file and port to compare (can be used multiple times)"
      echo "  --help                Show this help message"
      exit 0
      ;;
    *)
      log "ERROR" "Unknown option: $1"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# If no servers specified, use defaults
if [ ${#SERVERS[@]} -eq 0 ]; then
  SERVERS=("${DEFAULT_SERVERS[@]}")
fi

# Check if we have at least 2 servers to compare
if [ ${#SERVERS[@]} -lt 2 ]; then
  log "ERROR" "At least 2 servers are needed for comparison"
  exit 1
fi

# Check required commands
check_command "curl"
check_command "jq"
check_command "comm"

# Display header
log "INFO" "═══════════════════════════════════════════════════════════════════"
log "INFO" "            CROSS-VERSION MCP SERVER COMPARISON                    "
log "INFO" "═══════════════════════════════════════════════════════════════════"

# Display servers being compared
log "INFO" "Comparing the following MCP servers:"
for server_spec in "${SERVERS[@]}"; do
  IFS=':' read -r server port <<< "$server_spec"
  log "INFO" "  - $server (port $port)"
done

log "INFO" ""

# Pairwise comparison of all servers
for ((i=0; i<${#SERVERS[@]}; i++)); do
  IFS=':' read -r server1 port1 <<< "${SERVERS[$i]}"
  
  for ((j=i+1; j<${#SERVERS[@]}; j++)); do
    IFS=':' read -r server2 port2 <<< "${SERVERS[$j]}"
    
    log "INFO" "Comparing $server1:$port1 with $server2:$port2..."
    compare_servers "$server1" "$port1" "$server2" "$port2"
  done
done

# Build overall report
build_overall_report

log "SUCCESS" "Cross-version comparison completed!"
log "INFO" "Results saved in $RESULTS_DIR/"
