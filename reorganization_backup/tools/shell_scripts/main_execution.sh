#!/bin/bash
# Main function used to execute the testing framework
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
  ensure_ipfs_daemon_running || {
    log "ERROR" "Failed to ensure IPFS daemon is running" "MAIN"
    exit 1
  }
  
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
