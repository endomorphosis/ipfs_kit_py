#!/bin/bash
#
# Comprehensive MCP Testing Framework
#
# This script runs comprehensive tests on the MCP server implementation.
# It starts the server, runs basic and integration tests, then stops the server.
#
# Usage:
#   ./run_all_mcp_tests.sh [--no-restart] [--tests-only] [--coverage]
#
# Options:
#   --no-restart   Don't restart the MCP server
#   --tests-only   Only run tests without starting/stopping the server
#   --coverage     Also run IPFS kit coverage analysis

set -e

# Configuration
SERVER_FILE="final_mcp_server.py"
PORT=9996
SERVER_PID_FILE="final_mcp_server.pid"
SERVER_LOG_FILE="final_mcp_server.log"
TEST_RUNNER="mcp_test_runner.py"
COVERAGE_ANALYZER="ipfs_kit_coverage_analyzer.py"
VSCODE_TEST=true
INTEGRATION_TEST=true
RESTART_SERVER=true
TESTS_ONLY=false
RUN_COVERAGE=false
DEFAULT_TIMEOUT=30

# Process command line arguments
for arg in "$@"; do
  case $arg in
    --no-restart)
      RESTART_SERVER=false
      ;;
    --tests-only)
      TESTS_ONLY=true
      ;;
    --coverage)
      RUN_COVERAGE=true
      ;;
    *)
      echo "Unknown argument: $arg"
      echo "Usage: $0 [--no-restart] [--tests-only] [--coverage]"
      exit 1
      ;;
  esac
done

# Function to display a timestamp
timestamp() {
  date +"%Y-%m-%d %H:%M:%S"
}

# Function to check if server is running
is_server_running() {
  if [ -f "$SERVER_PID_FILE" ]; then
    PID=$(cat "$SERVER_PID_FILE")
    if ps -p "$PID" > /dev/null; then
      return 0  # Server is running
    fi
  fi
  return 1  # Server is not running
}

# Function to start the MCP server
start_mcp_server() {
  echo "[$(timestamp)] Starting MCP server using $SERVER_FILE on port $PORT..."
  python3 "$SERVER_FILE" --port "$PORT" > "$SERVER_LOG_FILE" 2>&1 &
  echo $! > "$SERVER_PID_FILE"
  echo "[$(timestamp)] MCP server started with PID: $(cat "$SERVER_PID_FILE")"
  
  # Wait for server to initialize
  echo "[$(timestamp)] Waiting for server to initialize..."
  for i in $(seq 1 $DEFAULT_TIMEOUT); do
    if curl -s "http://localhost:$PORT/health" > /dev/null; then
      echo "[$(timestamp)] MCP server is ready!"
      return 0
    fi
    sleep 1
  done
  
  echo "[$(timestamp)] ERROR: MCP server failed to start within $DEFAULT_TIMEOUT seconds" >&2
  return 1
}

# Function to stop the MCP server
stop_mcp_server() {
  echo "[$(timestamp)] Stopping MCP server if running..."
  if [ -f "$SERVER_PID_FILE" ]; then
    PID=$(cat "$SERVER_PID_FILE")
    if ps -p "$PID" > /dev/null; then
      echo "[$(timestamp)] Stopping MCP server process $PID..."
      kill "$PID"
      sleep 2
      
      # Make sure it's really stopped
      if ps -p "$PID" > /dev/null; then
        echo "[$(timestamp)] Server did not stop gracefully, forcing termination..."
        kill -9 "$PID" > /dev/null 2>&1 || true
      fi
    else
      echo "[$(timestamp)] PID file exists but process is not running"
    fi
    rm -f "$SERVER_PID_FILE"
  else
    echo "[$(timestamp)] No PID file found, server is not running"
  fi
}

# Function to run comprehensive tests
run_comprehensive_tests() {
  echo "[$(timestamp)] Running comprehensive MCP tests..."
  echo "[$(timestamp)] Running test runner..."
  
  TEST_ARGS=""
  if [ "$INTEGRATION_TEST" = true ]; then
    TEST_ARGS="$TEST_ARGS --integration-test"
  fi
  if [ "$VSCODE_TEST" = true ]; then
    TEST_ARGS="$TEST_ARGS --vscode-test"
  fi
  
  python3 "$TEST_RUNNER" --server-file "$SERVER_FILE" --port "$PORT" $TEST_ARGS
  TEST_RESULT=$?
  
  if [ "$TEST_RESULT" -eq 0 ]; then
    echo "[$(timestamp)] All tests passed successfully!"
  else
    echo "[$(timestamp)] Some tests failed. See detailed output above."
  fi
  
  return $TEST_RESULT
}

# Function to run coverage analysis
run_coverage_analysis() {
  if [ "$RUN_COVERAGE" = true ]; then
    echo "[$(timestamp)] Running IPFS kit coverage analysis..."
    python3 "$COVERAGE_ANALYZER" --server-file "$SERVER_FILE" --port "$PORT"
    return $?
  fi
  return 0
}

# Main execution
cleanup() {
  echo "[$(timestamp)] Cleanup started..."
  stop_mcp_server
  sleep 2
  echo "[$(timestamp)] Cleanup complete."
}

# Register cleanup function to run on exit
trap cleanup EXIT

# Main script logic
RESULT=0

if [ "$TESTS_ONLY" = false ]; then
  # Start server if needed or requested
  if [ "$RESTART_SERVER" = true ] || ! is_server_running; then
    is_server_running && stop_mcp_server
    start_mcp_server || exit 1
  fi
else
  echo "[$(timestamp)] Server File: $SERVER_FILE"
  echo "[$(timestamp)] Port: $PORT"
  echo "[$(timestamp)] Test Runner: $TEST_RUNNER"
fi

# Check if server is actually running before proceeding
if ! curl -s "http://localhost:$PORT/health" > /dev/null; then
  echo "[$(timestamp)] MCP server is not running. Starting it for the requested operations..."
  start_mcp_server || exit 1
fi

# Run tests and coverage analysis
run_comprehensive_tests || RESULT=1
[ "$RUN_COVERAGE" = true ] && run_coverage_analysis || true

exit $RESULT
