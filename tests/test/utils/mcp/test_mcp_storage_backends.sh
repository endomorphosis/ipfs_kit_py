#!/bin/bash
# Test MCP server storage backends
# This script runs the MCP server with all storage backends enabled and then tests each backend

set -e  # Exit on error

# Configure output coloring
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Default variables
MCP_HOST="127.0.0.1"
MCP_PORT="10000"
API_PREFIX="/api/v0/mcp"
API_URL_PREFIX=""  # Will be set based on API_PREFIX
BACKEND_LIST="s3 storacha filecoin lassie huggingface"
MCP_TIMEOUT=120  # Seconds to wait for MCP server to start (increased from 30 to 120)

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --port)
      MCP_PORT="$2"
      shift 2
      ;;
    --host)
      MCP_HOST="$2"
      shift 2
      ;;
    --backend)
      BACKEND_LIST="$2"
      shift 2
      ;;
    --help)
      echo "Usage: $0 [options]"
      echo ""
      echo "Options:"
      echo "  --port PORT       Port for MCP server (default: 10000)"
      echo "  --host HOST       Host for MCP server (default: 127.0.0.1)"
      echo "  --backend LIST    Space-separated list of backends to test (default: all)"
      echo "  --help            Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Create temporary directory for logs
LOG_DIR=$(mktemp -d -t mcp-test-XXXXXX)
MCP_LOG="$LOG_DIR/mcp_server.log"
TEST_LOG="$LOG_DIR/backend_test.log"

echo -e "${YELLOW}Starting MCP server with storage backends...${NC}"
echo -e "${YELLOW}Logs will be saved to $LOG_DIR${NC}"

# Start MCP server in background with simulation mode
python run_mcp_with_storage.py --host "$MCP_HOST" --port "$MCP_PORT" --debug --isolation --api-prefix "$API_PREFIX" --simulation-mode > "$MCP_LOG" 2>&1 &
MCP_PID=$!

# Function to clean up on exit
cleanup() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"
    if ps -p $MCP_PID > /dev/null; then
        echo "Stopping MCP server (PID: $MCP_PID)"
        kill $MCP_PID
    fi
    echo -e "${YELLOW}Logs saved to:${NC}"
    echo "  MCP Server: $MCP_LOG"
    echo "  Backend Tests: $TEST_LOG"
}

# Register cleanup function to run on script exit
trap cleanup EXIT

# Wait for MCP server to start
echo -e "${YELLOW}Waiting for MCP server to start (timeout: ${MCP_TIMEOUT}s)...${NC}"
MCP_URL="http://${MCP_HOST}:${MCP_PORT}${API_PREFIX}/health"
echo -e "${YELLOW}Checking health endpoint: ${MCP_URL}${NC}"
START_TIME=$(date +%s)

while true; do
    ELAPSED=$(($(date +%s) - START_TIME))
    if [ $ELAPSED -gt $MCP_TIMEOUT ]; then
        echo -e "${RED}Timeout waiting for MCP server to start${NC}"
        echo -e "${YELLOW}Last 15 lines of MCP server log:${NC}"
        tail -n 15 "$MCP_LOG"
        exit 1
    fi
    
    # Check if server is responding
    if curl -s -f "$MCP_URL" > /dev/null 2>&1; then
        echo -e "${GREEN}MCP server started successfully${NC}"
        break
    fi
    
    # Check if server process is still running
    if ! ps -p $MCP_PID > /dev/null; then
        echo -e "${RED}MCP server process died${NC}"
        echo -e "${YELLOW}Last 15 lines of MCP server log:${NC}"
        tail -n 15 "$MCP_LOG"
        exit 1
    fi
    
    echo -n "."
    sleep 1
done

# Run backend tests
echo -e "\n${YELLOW}Running storage backend tests...${NC}"
BACKENDS_ARG=""
if [ "$BACKEND_LIST" != "all" ]; then
    BACKENDS_ARG="--backends $BACKEND_LIST"
fi

# Create results directory if it doesn't exist
RESULTS_DIR="./test-results"
mkdir -p "$RESULTS_DIR"

# Generate timestamp for result file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RESULTS_FILE="$RESULTS_DIR/mcp_backends_test_${TIMESTAMP}.json"

# Set URL for the test script based on API_PREFIX
if [[ "$API_PREFIX" == *"/mcp" ]]; then
    # If API_PREFIX ends with /mcp, we need to strip it for our test script
    API_URL_PREFIX=$(echo "$API_PREFIX" | sed 's/\/mcp$//')
elif [[ "$API_PREFIX" == "/mcp" ]]; then
    # If API_PREFIX is just /mcp, use empty prefix
    API_URL_PREFIX=""
else
    # Otherwise, use API_PREFIX as is
    API_URL_PREFIX="$API_PREFIX"
fi

URL="http://${MCP_HOST}:${MCP_PORT}${API_URL_PREFIX}"
echo -e "${YELLOW}Using API URL: ${URL}${NC}"
python test_mcp_storage_backends.py --url "$URL" $BACKENDS_ARG --output "$RESULTS_FILE" 2>&1 | tee "$TEST_LOG"
TEST_EXIT_CODE=${PIPESTATUS[0]}

# Copy logs to results directory
cp "$MCP_LOG" "$RESULTS_DIR/mcp_server_${TIMESTAMP}.log"
cp "$TEST_LOG" "$RESULTS_DIR/backend_test_${TIMESTAMP}.log"

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}All backend tests completed successfully!${NC}"
    echo -e "${GREEN}Results saved to: ${RESULTS_FILE}${NC}"
    exit 0
else
    echo -e "\n${RED}Some backend tests failed. Check the logs for details.${NC}"
    echo -e "${YELLOW}Results saved to: ${RESULTS_FILE}${NC}"
    exit 1
fi