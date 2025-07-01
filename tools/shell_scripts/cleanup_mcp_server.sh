#!/bin/bash
# MCP Server Cleanup Script
# This script stops the MCP server and cleans up temporary files

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
PORT=9998
PID_FILE="final_mcp_server.pid"
LOG_FILE="final_mcp_server.log"

# Function for logging messages
log() {
    local level="$1"
    local message="$2"
    local color="$NC"
    
    case "$level" in
        "INFO") color="$BLUE";;
        "SUCCESS") color="$GREEN";;
        "ERROR") color="$RED";;
        "WARNING") color="$YELLOW";;
    esac
    
    echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message${NC}"
}

# Try graceful shutdown first using check_server.py
log "INFO" "Attempting graceful server shutdown"
python3 check_server.py --stop

# Double-check for any MCP server processes
log "INFO" "Checking for any remaining MCP server processes"
MCP_PIDS=$(ps -ef | grep "python.*final_mcp_server\.py" | grep -v grep | awk '{print $2}')

if [ -n "$MCP_PIDS" ]; then
    log "WARNING" "Found additional MCP server processes: $MCP_PIDS"
    
    for PID in $MCP_PIDS; do
        log "WARNING" "Force killing process with PID $PID"
        kill -9 "$PID" 2>/dev/null
    done
    
    log "SUCCESS" "Killed all remaining MCP server processes"
fi

# Check if PID file still exists and remove it
if [ -f "$PID_FILE" ]; then
    log "WARNING" "PID file still exists, removing it"
    rm -f "$PID_FILE"
fi

# Check if port is still in use
if command -v lsof >/dev/null 2>&1; then
    PORT_PROCESS=$(lsof -i :$PORT -t 2>/dev/null)
    if [ -n "$PORT_PROCESS" ]; then
        log "WARNING" "Port $PORT is still in use by process(es): $PORT_PROCESS"
        log "WARNING" "Attempting to free up port $PORT"
        
        for PID in $PORT_PROCESS; do
            log "WARNING" "Killing process with PID $PID"
            kill -9 "$PID" 2>/dev/null
        done
        
        sleep 1
        PORT_PROCESS=$(lsof -i :$PORT -t 2>/dev/null)
        if [ -n "$PORT_PROCESS" ]; then
            log "ERROR" "Failed to free up port $PORT"
        else
            log "SUCCESS" "Port $PORT is now free"
        fi
    else
        log "SUCCESS" "Port $PORT is free"
    fi
else
    log "WARNING" "lsof command not found, can't verify port availability"
fi

# Clean up temporary files
log "INFO" "Cleaning up temporary files"
rm -f test_file.txt
[ -d "test_dir" ] && rm -rf test_dir

# Clean up log file if requested
if [ "$1" == "--full" ]; then
    log "INFO" "Performing full cleanup including logs"
    rm -f "$LOG_FILE"
fi

# List test result files
log "INFO" "Test result files are available in test_results directory"
ls -la test_results/ 2>/dev/null || echo "No test results found"

log "SUCCESS" "Cleanup complete"
