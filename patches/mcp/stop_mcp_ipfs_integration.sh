#!/bin/bash
# Stop MCP IPFS Integration Server
# This script stops all MCP and IPFS services started by start_mcp_ipfs_integration.sh

# Color configuration
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Process force kill flag (default: false)
FORCE_KILL=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --force|-f)
            FORCE_KILL=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo "OPTIONS:"
            echo "  --force, -f    Force kill processes (SIGKILL) if they don't respond to SIGTERM"
            echo "  --help, -h     Display this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help to see available options"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}================================${NC}"
echo -e "${RED}Stopping MCP IPFS Integration${NC}"
echo -e "${BLUE}================================${NC}"

stop_process() {
    local pid_file=$1
    local process_name=$2
    
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null; then
            echo -e "${YELLOW}Stopping $process_name (PID: $pid)...${NC}"
            kill $pid
            sleep 1
            
            # Check if process is still running
            if ps -p $pid > /dev/null; then
                if [ "$FORCE_KILL" = true ]; then
                    echo -e "${RED}Process still running. Sending SIGKILL...${NC}"
                    kill -9 $pid
                    sleep 1
                else
                    echo -e "${YELLOW}Process still running. Waiting a bit longer...${NC}"
                    sleep 2
                    if ps -p $pid > /dev/null; then
                        echo -e "${RED}Process still not responding. Sending SIGKILL...${NC}"
                        kill -9 $pid
                        sleep 1
                    fi
                fi
            fi
            
            # Final check
            if ! ps -p $pid > /dev/null; then
                echo -e "${GREEN}✓ $process_name stopped successfully${NC}"
            else
                echo -e "${RED}✗ Failed to stop $process_name${NC}"
            fi
        else
            echo -e "${YELLOW}$process_name (PID: $pid) is not running${NC}"
        fi
        rm -f "$pid_file"
    else
        echo -e "${YELLOW}No PID file found for $process_name${NC}"
    fi
}

# Find and stop processes by name pattern
stop_processes_by_pattern() {
    local pattern=$1
    local process_name=$2
    
    echo -e "${YELLOW}Looking for running $process_name processes...${NC}"
    pids=$(pgrep -f "$pattern" | grep -v $$)
    
    if [ -n "$pids" ]; then
        echo -e "${YELLOW}Found $process_name processes: $pids${NC}"
        for pid in $pids; do
            echo -e "${YELLOW}Stopping $process_name (PID: $pid)...${NC}"
            kill $pid
            sleep 1
            
            # Check if process is still running
            if ps -p $pid > /dev/null; then
                if [ "$FORCE_KILL" = true ]; then
                    echo -e "${RED}Process still running. Sending SIGKILL...${NC}"
                    kill -9 $pid
                    sleep 1
                else
                    echo -e "${YELLOW}Process still running. Waiting a bit longer...${NC}"
                    sleep 2
                    if ps -p $pid > /dev/null; then
                        echo -e "${RED}Process still not responding. Sending SIGKILL...${NC}"
                        kill -9 $pid
                        sleep 1
                    fi
                fi
            fi
            
            # Final check
            if ! ps -p $pid > /dev/null; then
                echo -e "${GREEN}✓ $process_name (PID: $pid) stopped successfully${NC}"
            else
                echo -e "${RED}✗ Failed to stop $process_name (PID: $pid)${NC}"
            fi
        done
    else
        echo -e "${YELLOW}No running $process_name processes found${NC}"
    fi
}

# Stop all known PID files
stop_all_pid_files() {
    echo -e "${YELLOW}Stopping all services with PID files...${NC}"
    
    # List of PID files to check
    pid_files=(
        "mcp_proxy.pid:MCP IPFS proxy server"
        "ipfs_daemon.pid:IPFS daemon"
        "jsonrpc_server.pid:JSON-RPC server"
        "mcp_server.pid:MCP server"
        "direct_mcp_server_blue.pid:Direct MCP server"
        "enhanced_mcp_server_real.pid:Enhanced MCP server"
    )
    
    for entry in "${pid_files[@]}"; do
        IFS=':' read -r file name <<< "$entry"
        if [ -f "$file" ]; then
            stop_process "$file" "$name"
        fi
    done
}

# Stop MCP proxy server
stop_mcp_proxy() {
    echo -e "${YELLOW}Stopping MCP IPFS proxy server...${NC}"
    stop_process "mcp_proxy.pid" "MCP IPFS proxy server"
    # Also try to find by pattern in case PID file is missing
    stop_processes_by_pattern "ipfs_mcp_proxy_server.py" "MCP IPFS proxy server"
}

# Stop JSON-RPC server
stop_jsonrpc_server() {
    echo -e "${YELLOW}Stopping MCP JSON-RPC proxy server...${NC}"
    stop_process "jsonrpc_server.pid" "JSON-RPC server"
    # Also try to find by pattern in case PID file is missing
    stop_processes_by_pattern "mcp_jsonrpc_" "JSON-RPC proxy"
}

# Stop MCP server instances
stop_mcp_servers() {
    echo -e "${YELLOW}Stopping any running MCP server instances...${NC}"
    # Try known patterns for MCP servers
    stop_processes_by_pattern "run_mcp_server" "MCP server"
    stop_processes_by_pattern "direct_mcp_server.py" "Direct MCP server"
    stop_processes_by_pattern "unified_mcp_server.py" "Unified MCP server"
    stop_processes_by_pattern "enhanced_mcp_server" "Enhanced MCP server"
}

# Stop IPFS daemon (if started by our script)
stop_ipfs() {
    echo -e "${YELLOW}Checking IPFS daemon...${NC}"
    if [ -f "ipfs_daemon.pid" ]; then
        echo -e "${YELLOW}IPFS daemon was started by our script. Stopping it...${NC}"
        stop_process "ipfs_daemon.pid" "IPFS daemon"
    else
        echo -e "${YELLOW}IPFS daemon was not started by our script.${NC}"
        read -p "Do you want to stop the IPFS daemon anyway? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${YELLOW}Attempting to stop IPFS daemon...${NC}"
            ipfs shutdown
            sleep 2
            if ! curl -s http://localhost:5001/api/v0/version > /dev/null; then
                echo -e "${GREEN}✓ IPFS daemon stopped successfully${NC}"
            else
                echo -e "${RED}✗ Failed to stop IPFS daemon${NC}"
            fi
        else
            echo -e "${YELLOW}Skipping IPFS daemon. You can stop it manually with 'ipfs shutdown'${NC}"
        fi
    fi
}

# Clean up any temporary files
cleanup() {
    echo -e "${YELLOW}Cleaning up temporary files...${NC}"
    # List of temporary files to clean
    temp_files=(
        "ipfs_mcp_fs.log" 
        "test_mcp_data"
        "mcp_proxy.log"
        "ipfs_daemon.log"
        "jsonrpc_proxy.log"
        "mcp_enhanced_tools.log"
        "auth_audit.log"
        "direct_mcp_server.log"
        "jsonrpc_server.log"
        "mcp_direct_server.log"
        "flask_health.log"
        "health_debug.log"
    )
    
    for file in "${temp_files[@]}"; do
        if [ -e "$file" ]; then
            echo -e "${YELLOW}Removing $file...${NC}"
            rm -rf "$file"
        fi
    done
    
    # Check for any remaining PID files
    remaining_pid_files=$(find . -name "*.pid" -type f)
    if [ -n "$remaining_pid_files" ]; then
        echo -e "${YELLOW}Found remaining PID files:${NC}"
        echo "$remaining_pid_files"
        read -p "Do you want to remove these PID files? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            find . -name "*.pid" -type f -delete
            echo -e "${GREEN}✓ Removed remaining PID files${NC}"
        fi
    fi
    
    echo -e "${GREEN}✓ Cleanup complete${NC}"
}

# Main function
main() {
    echo -e "${YELLOW}Starting shutdown sequence...${NC}"
    
    # Stop services in reverse order of dependency
    stop_mcp_proxy
    stop_jsonrpc_server
    stop_mcp_servers
    
    # Stop all remaining services with PID files
    stop_all_pid_files
    
    # Finally stop IPFS daemon
    stop_ipfs
    
    # Cleanup temp files (optional)
    read -p "Do you want to clean up temporary files? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cleanup
    fi
    
    echo -e "${GREEN}=============================${NC}"
    echo -e "${GREEN}  Shutdown complete!        ${NC}"
    echo -e "${GREEN}=============================${NC}"
}

# Run the main function
main
