#!/bin/bash
# Script to test the MCP server fixes

# Print a status-colored message
print_status() {
  if [ "$1" == "success" ]; then
    echo -e "\e[32m$2\e[0m"  # Green text
  elif [ "$1" == "error" ]; then
    echo -e "\e[31m$2\e[0m"  # Red text
  elif [ "$1" == "info" ]; then
    echo -e "\e[34m$2\e[0m"  # Blue text
  else
    echo "$2"
  fi
}

# Check if a command exists
check_command() {
  if ! command -v "$1" &> /dev/null; then
    print_status "error" "Required command '$1' not found. Please install it."
    exit 1
  fi
}

# Check for required commands
check_command uvicorn
check_command python

# Start the MCP server in the background
start_server() {
  print_status "info" "Starting MCP server on port 8001..."
  
  # Kill any existing uvicorn process on port 8001
  pkill -f "uvicorn.*:8001" 2>/dev/null
  
  # Start the server
  nohup uvicorn run_mcp_server:app --host 127.0.0.1 --port 8001 > mcp_server.log 2>&1 &
  
  # Save the PID
  SERVER_PID=$!
  echo $SERVER_PID > server.pid
  
  # Wait for server to start
  print_status "info" "Waiting for server to start..."
  sleep 5
  
  # Check if server is running
  if ! kill -0 $SERVER_PID 2>/dev/null; then
    print_status "error" "Failed to start MCP server. Check mcp_server.log for details."
    exit 1
  fi
  
  print_status "success" "MCP server started with PID $SERVER_PID"
}

# Stop the server
stop_server() {
  if [ -f server.pid ]; then
    SERVER_PID=$(cat server.pid)
    if kill -0 $SERVER_PID 2>/dev/null; then
      print_status "info" "Stopping MCP server (PID $SERVER_PID)..."
      kill $SERVER_PID
      # Remove PID file
      rm server.pid
      print_status "success" "MCP server stopped"
    fi
  fi
}

# Run tests
run_tests() {
  print_status "info" "Running MCP fixes test script..."
  python test_mcp_fixes.py
  
  if [ $? -eq 0 ]; then
    print_status "success" "Tests completed. Check mcp_fix_verification_results.json for details."
  else
    print_status "error" "Tests failed. Check the output above for details."
  fi
}

# Main function
main() {
  # Trap to ensure server is stopped
  trap stop_server EXIT
  
  # Start the server
  start_server
  
  # Run tests
  run_tests
}

# Run the main function
main