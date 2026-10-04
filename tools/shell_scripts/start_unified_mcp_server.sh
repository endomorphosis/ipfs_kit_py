#!/bin/bash
# Unified MCP Server Launcher
# This script manages the Unified MCP Server, providing a single entrypoint
# for starting, stopping, and checking the status of the server.
# It combines functionality from all existing MCP starter scripts.

# Default configurations
PORT=9994
API_PREFIX="/api/v0"
HOST="0.0.0.0"
LOG_FILE="mcp_server.log"
PID_FILE="unified_mcp_server.pid"
JSONRPC_PORT=9995
JSONRPC_LOG="jsonrpc_server.log"
JSONRPC_PID_FILE="jsonrpc_server.pid"
FORCE="false"
SEPARATE_JSONRPC="false"
USE_LEGACY="false"

# Process colors for better output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Parse command line options
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            PORT="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --api-prefix)
            API_PREFIX="$2"
            shift 2
            ;;
        --log-file)
            LOG_FILE="$2"
            shift 2
            ;;
        --force)
            FORCE="true"
            shift
            ;;
        --separate-jsonrpc)
            SEPARATE_JSONRPC="true"
            shift
            ;;
        --legacy)
            USE_LEGACY="true"
            shift
            ;;
        --help)
            echo -e "${CYAN}${BOLD}Unified MCP Server Launcher${NC}"
            echo "Usage: $0 [options] [command]"
            echo
            echo "Commands:"
            echo "  start       Start the MCP server (default)"
            echo "  stop        Stop the MCP server"
            echo "  restart     Restart the MCP server"
            echo "  status      Check the status of the MCP server"
            echo "  test        Test the MCP server endpoints"
            echo "  update-settings  Update VS Code settings"
            echo
            echo "Options:"
            echo "  --port PORT             Set the MCP server port (default: 9994)"
            echo "  --host HOST             Set the bind host (default: 0.0.0.0)"
            echo "  --api-prefix PREFIX     Set the API prefix (default: /api/v0)"
            echo "  --log-file FILE         Set the log file (default: mcp_server.log)"
            echo "  --force                 Force kill server processes"
            echo "  --separate-jsonrpc      Start a separate JSON-RPC server"
            echo "  --legacy                Use legacy scripts (enhanced_mcp_server_fixed.py)"
            echo "  --help                  Show this help message"
            exit 0
            ;;
        start|stop|restart|status|test|update-settings)
            COMMAND="$1"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information."
            exit 1
            ;;
    esac
done

# If no command specified, default to start
if [ -z "$COMMAND" ]; then
    COMMAND="start"
fi

# Display banner
echo -e "${BLUE}${BOLD}"
echo "====================================================================="
echo "                   UNIFIED MCP SERVER LAUNCHER                       "
echo "====================================================================="
echo -e "${NC}"

# Determine server script to use
SERVER_SCRIPT="unified_mcp_server.py"
if [ "$USE_LEGACY" = "true" ]; then
    SERVER_SCRIPT="enhanced_mcp_server_fixed.py"
    echo -e "${YELLOW}Using legacy server script: ${SERVER_SCRIPT}${NC}"
fi

# Check if the server script exists
if [ ! -f "$SERVER_SCRIPT" ]; then
    echo -e "${RED}Error: $SERVER_SCRIPT not found!${NC}"
    echo "Make sure you are in the correct directory."
    exit 1
fi

# Make the server script executable
chmod +x "$SERVER_SCRIPT"

# If using separate JSON-RPC server, check if it exists
JSONRPC_SCRIPT="vscode_enhanced_jsonrpc_server.py"
if [ "$SEPARATE_JSONRPC" = "true" ]; then
    if [ -f "$JSONRPC_SCRIPT" ]; then
        chmod +x "$JSONRPC_SCRIPT"
    elif [ -f "simple_jsonrpc_server.py" ]; then
        JSONRPC_SCRIPT="simple_jsonrpc_server.py"
        chmod +x "$JSONRPC_SCRIPT"
    else
        echo -e "${YELLOW}Warning: JSON-RPC server script not found. Using unified server only.${NC}"
        SEPARATE_JSONRPC="false"
    fi
fi

# Function to check if a server is running
check_running() {
    local url=$1
    local name=$2
    local max_attempts=${3:-3}
    local attempt=1

    echo -e "${YELLOW}Checking ${name} status...${NC}"
    while [ ${attempt} -le ${max_attempts} ]; do
        if curl -s ${url} > /dev/null; then
            echo -e "${GREEN}✓${NC} ${name} is running at ${url} (attempt ${attempt})"
            return 0
        else
            echo "Attempt ${attempt}: ${name} not responding yet..."
            attempt=$((attempt + 1))
            sleep 1
        fi
    done

    echo -e "${RED}✗${NC} ${name} failed to respond after ${max_attempts} attempts"
    return 1
}

# Function to stop any running MCP server processes
stop_server() {
    echo -e "${YELLOW}Stopping MCP server processes...${NC}"
    
    local stop_count=0
    local success=true
    
    # Find and kill the unified server process if it's running
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null; then
            echo "Stopping process $PID from PID file..."
            if [ "$FORCE" = "true" ]; then
                kill -9 "$PID" 2>/dev/null
                sleep 1
            else
                kill "$PID" 2>/dev/null
                
                # Wait for process to end
                MAX_WAIT=5
                for i in $(seq 1 $MAX_WAIT); do
                    if ! ps -p "$PID" > /dev/null; then
                        break
                    fi
                    echo "Waiting for server to shut down... ($i/$MAX_WAIT)"
                    sleep 1
                done
                
                # Force kill if still running
                if ps -p "$PID" > /dev/null; then
                    echo "Process still running, force killing..."
                    kill -9 "$PID" 2>/dev/null
                    sleep 1
                fi
            fi
            
            if ! ps -p "$PID" > /dev/null; then
                echo "Process stopped."
                stop_count=$((stop_count + 1))
            else
                echo "Failed to stop process."
                success=false
            fi
        else
            echo "Process in PID file not running."
        fi
        rm -f "$PID_FILE"
    fi
    
    # Check for JSON-RPC server if using separate process
    if [ "$SEPARATE_JSONRPC" = "true" ] && [ -f "$JSONRPC_PID_FILE" ]; then
        PID=$(cat "$JSONRPC_PID_FILE")
        if ps -p "$PID" > /dev/null; then
            echo "Stopping JSON-RPC process $PID from PID file..."
            if [ "$FORCE" = "true" ]; then
                kill -9 "$PID" 2>/dev/null
                sleep 1
            else
                kill "$PID" 2>/dev/null
                sleep 2
                if ps -p "$PID" > /dev/null; then
                    echo "JSON-RPC process still running, force killing..."
                    kill -9 "$PID" 2>/dev/null
                    sleep 1
                fi
            fi
            
            if ! ps -p "$PID" > /dev/null; then
                echo "JSON-RPC process stopped."
                stop_count=$((stop_count + 1))
            else
                echo "Failed to stop JSON-RPC process."
                success=false
            fi
        else
            echo "JSON-RPC process in PID file not running."
        fi
        rm -f "$JSONRPC_PID_FILE"
    fi
    
    # Kill any other potentially running MCP processes
    local other_pids=$(pgrep -f "python.*(unified_mcp_server|enhanced_mcp_server|mcp_server_fixed|run_mcp_server)" 2>/dev/null || true)
    if [ -n "$other_pids" ]; then
        echo "Found other MCP server processes: $other_pids"
        if [ "$FORCE" = "true" ]; then
            echo "Force killing all MCP server processes..."
            pkill -9 -f "python.*(unified_mcp_server|enhanced_mcp_server|mcp_server_fixed|run_mcp_server)" 2>/dev/null || true
        else
            echo "Stopping all MCP server processes gracefully..."
            pkill -f "python.*(unified_mcp_server|enhanced_mcp_server|mcp_server_fixed|run_mcp_server)" 2>/dev/null || true
            
            # Wait and then force kill if needed
            sleep 2
            if pgrep -f "python.*(unified_mcp_server|enhanced_mcp_server|mcp_server_fixed|run_mcp_server)" > /dev/null; then
                echo "Some processes still running, force killing..."
                pkill -9 -f "python.*(unified_mcp_server|enhanced_mcp_server|mcp_server_fixed|run_mcp_server)" 2>/dev/null || true
            fi
        fi
        
        # Check if all processes were killed
        if ! pgrep -f "python.*(unified_mcp_server|enhanced_mcp_server|mcp_server_fixed|run_mcp_server)" > /dev/null; then
            echo "Additional MCP processes stopped."
            stop_count=$((stop_count + 1))
        else
            echo "Failed to stop some MCP processes."
            success=false
        fi
    fi
    
    # Kill any running JSON-RPC proxies
    if pgrep -f "python.*(simple_jsonrpc_server|mcp_jsonrpc_proxy|vscode_enhanced_jsonrpc_server)" > /dev/null; then
        echo "Stopping JSON-RPC server processes..."
        pkill -f "python.*(simple_jsonrpc_server|mcp_jsonrpc_proxy|vscode_enhanced_jsonrpc_server)" 2>/dev/null || true
        sleep 1
        if pgrep -f "python.*(simple_jsonrpc_server|mcp_jsonrpc_proxy|vscode_enhanced_jsonrpc_server)" > /dev/null; then
            echo "JSON-RPC processes still running, force killing..."
            pkill -9 -f "python.*(simple_jsonrpc_server|mcp_jsonrpc_proxy|vscode_enhanced_jsonrpc_server)" 2>/dev/null || true
        fi
        stop_count=$((stop_count + 1))
    fi
    
    # Check for any uvicorn processes
    if pgrep -f "uvicorn.*(unified_mcp_server|enhanced_mcp_server|mcp_server|jsonrpc)" > /dev/null; then
        echo "Stopping uvicorn processes..."
        pkill -f "uvicorn.*(unified_mcp_server|enhanced_mcp_server|mcp_server|jsonrpc)" 2>/dev/null || true
        sleep 1
        if pgrep -f "uvicorn.*(unified_mcp_server|enhanced_mcp_server|mcp_server|jsonrpc)" > /dev/null; then
            echo "Uvicorn processes still running, force killing..."
            pkill -9 -f "uvicorn.*(unified_mcp_server|enhanced_mcp_server|mcp_server|jsonrpc)" 2>/dev/null || true
        fi
        stop_count=$((stop_count + 1))
    fi
    
    if [ "$stop_count" -gt 0 ]; then
        echo -e "${GREEN}MCP server processes stopped successfully.${NC}"
    elif [ "$success" = "true" ]; then
        echo -e "${YELLOW}No running MCP server processes found.${NC}"
    else
        echo -e "${RED}Failed to stop some MCP server processes.${NC}"
        return 1
    fi
    
    return 0
}

# Function to start the server
start_server() {
    echo -e "${YELLOW}Starting Unified MCP server...${NC}"
    
    # First, make sure no other instance is running
    stop_server
    
    # Start the server in the background
    if [ "$USE_LEGACY" = "true" ]; then
        echo "Using legacy server: $SERVER_SCRIPT"
        python "$SERVER_SCRIPT" --port "$PORT" --host "$HOST" --api-prefix "$API_PREFIX" --log-file "$LOG_FILE" > /dev/null 2>&1 &
    else
        echo "Using unified server: $SERVER_SCRIPT"
        python "$SERVER_SCRIPT" --port "$PORT" --host "$HOST" --api-prefix "$API_PREFIX" --log-file "$LOG_FILE" > /dev/null 2>&1 &
    fi
    
    echo $! > "$PID_FILE"
    echo "Started MCP server with PID $(cat $PID_FILE)"
    
    # Start separate JSON-RPC server if requested
    if [ "$SEPARATE_JSONRPC" = "true" ]; then
        echo -e "${YELLOW}Starting separate JSON-RPC server on port $JSONRPC_PORT...${NC}"
        python "$JSONRPC_SCRIPT" --port "$JSONRPC_PORT" > "$JSONRPC_LOG" 2>&1 &
        echo $! > "$JSONRPC_PID_FILE"
        echo "Started JSON-RPC server with PID $(cat $JSONRPC_PID_FILE)"
    fi
    
    # Wait for the server to start
    sleep 3
    
    # Check if MCP server is running
    MCP_SERVER_OK=false
    JSONRPC_SERVER_OK=true # Default to true, will be set to false if needed
    
    if check_running "http://${HOST}:${PORT}/" "MCP server" 5; then
        MCP_SERVER_OK=true
    fi
    
    # Check JSON-RPC server if separate
    if [ "$SEPARATE_JSONRPC" = "true" ]; then
        JSONRPC_SERVER_OK=false
        if check_running "http://localhost:${JSONRPC_PORT}/" "JSON-RPC server" 3; then
            JSONRPC_SERVER_OK=true
        fi
    fi
    
    # Proceed if at least MCP server is running
    if [ "$MCP_SERVER_OK" = "true" ]; then
        echo -e "${GREEN}MCP server is running at http://${HOST}:${PORT}/${NC}"
        
        # Update VS Code settings
        update_vscode_settings
        
        # Test the endpoints
        test_endpoints
        
        echo -e "${GREEN}Unified MCP server started successfully!${NC}"
        
        # Display a helpful message
        echo -e "\n${BLUE}Server Information:${NC}"
        echo " - Main URL: http://${HOST}:${PORT}/"
        echo " - SSE Endpoint: http://${HOST}:${PORT}${API_PREFIX}/sse"
        if [ "$SEPARATE_JSONRPC" = "true" ] && [ "$JSONRPC_SERVER_OK" = "true" ]; then
            echo " - JSON-RPC Endpoint: http://localhost:${JSONRPC_PORT}/jsonrpc"
        else
            echo " - JSON-RPC Endpoint: http://${HOST}:${PORT}/jsonrpc"
        fi
        echo " - Health Endpoint: http://${HOST}:${PORT}${API_PREFIX}/health"
        echo " - Log File: $LOG_FILE"
        
        echo -e "\n${BLUE}Commands:${NC}"
        echo " - Stop server: $0 stop"
        echo " - View logs: tail -f $LOG_FILE"
        echo " - Status: $0 status"
        
        # Show warning if JSON-RPC server failed to start
        if [ "$SEPARATE_JSONRPC" = "true" ] && [ "$JSONRPC_SERVER_OK" = "false" ]; then
            echo -e "\n${RED}Warning: JSON-RPC server failed to start.${NC}"
            echo "MCP server is running, but VS Code integration may be limited."
            echo "Check the JSON-RPC log: $JSONRPC_LOG"
        fi
        
        return 0
    else
        echo -e "${RED}Failed to start MCP server. Check the logs at $LOG_FILE${NC}"
        tail -20 "$LOG_FILE"
        return 1
    fi
}

# Function to update VS Code settings
update_vscode_settings() {
    echo -e "${YELLOW}Updating VS Code settings...${NC}"
    
    # Find the Claude settings files - try both regular and Insiders
    CLAUDE_SETTINGS_FILES=(
        "$HOME/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
        "$HOME/.config/Code - Insiders/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
    )
    
    # Try to update the Claude MCP settings
    local updated=false
    for settings_file in "${CLAUDE_SETTINGS_FILES[@]}"; do
        if [ -f "$settings_file" ]; then
            echo "Found Claude settings at: $settings_file"
            
            # Make a backup
            cp "$settings_file" "$settings_file.bak"
            echo "Created backup at $settings_file.bak"
            
            # Determine JSON-RPC URL
            local jsonrpc_url
            if [ "$SEPARATE_JSONRPC" = "true" ]; then
                jsonrpc_url="http://localhost:${JSONRPC_PORT}/jsonrpc"
            else
                jsonrpc_url="http://${HOST}:${PORT}/jsonrpc"
            fi
            
            # Update the settings - replace only the URLs
            if command -v jq > /dev/null; then
                # Use jq for a cleaner update if available
                SERVER_NAME=$(jq -r '.mcpServers | keys[0]' "$settings_file" 2>/dev/null)
                
                if [ -n "$SERVER_NAME" ] && [ "$SERVER_NAME" != "null" ]; then
                    echo "Updating settings for server: $SERVER_NAME"
                    jq --arg server "$SERVER_NAME" \
                       --arg sse "http://${HOST}:${PORT}${API_PREFIX}/sse" \
                       --arg jsonrpc "$jsonrpc_url" \
                       '.mcpServers[$server].url = $sse | .mcpServers[$server].jsonRpcUrl = $jsonrpc' \
                       "$settings_file" > "$settings_file.tmp" && \
                       mv "$settings_file.tmp" "$settings_file"
                else
                    echo "Couldn't find server name in settings, using default replacement"
                    # Fall back to sed if jq parsing fails
                    sed -i 's|"url": "http://[^"]*"|"url": "http://'"${HOST}:${PORT}${API_PREFIX}"'/sse"|g' "$settings_file"
                    sed -i 's|"jsonRpcUrl": "http://[^"]*"|"jsonRpcUrl": "'"$jsonrpc_url"'"|g' "$settings_file"
                fi
            else
                # Fall back to sed if jq is not available
                sed -i 's|"url": "http://[^"]*"|"url": "http://'"${HOST}:${PORT}${API_PREFIX}"'/sse"|g' "$settings_file"
                sed -i 's|"jsonRpcUrl": "http://[^"]*"|"jsonRpcUrl": "'"$jsonrpc_url"'"|g' "$settings_file"
            fi
            
            updated=true
            echo -e "${GREEN}VS Code settings updated successfully in $settings_file.${NC}"
        fi
    done
    
    # Try to update regular VS Code settings if needed
    VSCODE_SETTINGS_FILES=(
        "$HOME/.config/Code/User/settings.json"
        "$HOME/.config/Code - Insiders/User/settings.json"
    )
    
    for settings_file in "${VSCODE_SETTINGS_FILES[@]}"; do
        if [ -f "$settings_file" ]; then
            echo "Found VS Code settings at: $settings_file"
            
            # Create backup
            cp "$settings_file" "$settings_file.bak.$(date +%s)"
            
            # Determine JSON-RPC URL
            local jsonrpc_url
            if [ "$SEPARATE_JSONRPC" = "true" ]; then
                jsonrpc_url="http://localhost:${JSONRPC_PORT}/jsonrpc"
            else
                jsonrpc_url="http://${HOST}:${PORT}/jsonrpc"
            fi
            
            # Update MCP-related settings
            if grep -q '"mcp"' "$settings_file"; then
                sed -i 's|"url": "http://localhost:[0-9]*/api/v0/sse"|"url": "http://'"${HOST}:${PORT}${API_PREFIX}"'/sse"|g' "$settings_file"
            fi
            
            # Update JSON-RPC settings
            if grep -q '"localStorageNetworkingTools"' "$settings_file"; then
                sed -i 's|"url": "http://localhost:[0-9]*/jsonrpc"|"url": "'"$jsonrpc_url"'"|g' "$settings_file"
            fi
            
            updated=true
            echo -e "${GREEN}VS Code settings updated in $settings_file.${NC}"
        fi
    done
    
    if [ "$updated" = "false" ]; then
        echo -e "${YELLOW}No VS Code settings files found.${NC}"
        echo "If you're using VS Code, you'll need to manually configure the MCP settings."
    else
        echo "Please reload VS Code windows to apply the new settings."
    fi
}

# Function to test the endpoints
test_endpoints() {
    echo -e "${YELLOW}Testing the SSE endpoint...${NC}"
    curl -s -N "http://${HOST}:${PORT}${API_PREFIX}/sse" | head -n 2
    
    # Determine JSON-RPC URL
    local jsonrpc_url
    if [ "$SEPARATE_JSONRPC" = "true" ]; then
        jsonrpc_url="http://localhost:${JSONRPC_PORT}/jsonrpc"
    else
        jsonrpc_url="http://${HOST}:${PORT}/jsonrpc"
    fi
    
    echo -e "\n${YELLOW}Testing the JSON-RPC endpoint...${NC}"
    curl -s -X POST -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"processId":123,"rootUri":null,"capabilities":{}}}' \
        "$jsonrpc_url" | head -n 10
        
    echo -e "\n${YELLOW}Testing the health endpoint...${NC}"
    curl -s "http://${HOST}:${PORT}${API_PREFIX}/health" | head -n 10
    
    echo
}

# Function to check server status
check_status() {
    local mcp_running=false
    local jsonrpc_running=false
    local pid=""
    
    # Check for MCP server
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null; then
            echo -e "${GREEN}MCP server is running with PID $pid${NC}"
            mcp_running=true
            
            # Check if it's responding to requests
            if curl -s "http://${HOST}:${PORT}/" > /dev/null; then
                echo -e "${GREEN}MCP server is responding to requests.${NC}"
                
                # Show basic info from the server
                SERVER_INFO=$(curl -s "http://${HOST}:${PORT}/")
                
                # Extract uptime if available
                UPTIME=$(echo "$SERVER_INFO" | grep -o '"uptime":[^,}]*' | sed 's/"uptime"://g')
                if [ -n "$UPTIME" ]; then
                    # Calculate uptime in more readable format if it's a number
                    if [[ "$UPTIME" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
                        UPTIME_SEC=$(echo "$UPTIME" | awk '{printf "%.0f", $1}')
                        UPTIME_MIN=$(($UPTIME_SEC / 60))
                        UPTIME_HOURS=$(($UPTIME_MIN / 60))
                        UPTIME_DAYS=$(($UPTIME_HOURS / 24))
                        
                        UPTIME_HOURS=$(($UPTIME_HOURS % 24))
                        UPTIME_MIN=$(($UPTIME_MIN % 60))
                        
                        echo -e "${BLUE}Server uptime: ${UPTIME_DAYS}d ${UPTIME_HOURS}h ${UPTIME_MIN}m${NC}"
                    else
                        echo -e "${BLUE}Server uptime: $UPTIME${NC}"
                    fi
                fi
            else
                echo -e "${RED}MCP server process is running but not responding to HTTP requests.${NC}"
                echo "This might indicate the server is still starting up or is in an error state."
                echo -e "${YELLOW}Check the logs: tail -f $LOG_FILE${NC}"
            fi
        else
            echo -e "${RED}MCP server is not running (stale PID file found)${NC}"
            rm -f "$PID_FILE"
        fi
    else
        echo -e "${RED}MCP server is not running (no PID file found)${NC}"
        
        # Check if there's a process running anyway
        if pgrep -f "python.*(unified_mcp_server|enhanced_mcp_server)" > /dev/null; then
            echo -e "${YELLOW}However, an MCP server process was found running.${NC}"
            echo "This might indicate the PID file was lost or the server was started manually."
        fi
    fi
    
    # Check for JSON-RPC server
    if [ "$SEPARATE_JSONRPC" = "true" ] && [ -f "$JSONRPC_PID_FILE" ]; then
        pid=$(cat "$JSONRPC_PID_FILE")
        if ps -p "$pid" > /dev/null; then
            echo -e "${GREEN}JSON-RPC server is running with PID $pid${NC}"
            jsonrpc_running=true
            
            # Check if it's responding
            if curl -s "http://localhost:${JSONRPC_PORT}/" > /dev/null; then
                echo -e "${GREEN}JSON-RPC server is responding to requests.${NC}"
            else
                echo -e "${RED}JSON-RPC server process is running but not responding to HTTP requests.${NC}"
                echo "This might indicate the server is in an error state."
                echo -e "${YELLOW}Check the logs: tail -f $JSONRPC_LOG${NC}"
            fi
        else
            echo -e "${RED}JSON-RPC server is not running (stale PID file found)${NC}"
            rm -f "$JSONRPC_PID_FILE"
        fi
    elif [ "$SEPARATE_JSONRPC" = "true" ]; then
        echo -e "${RED}JSON-RPC server is not running (no PID file found)${NC}"
        
        # Check if there's a process running anyway
        if pgrep -f "python.*(simple_jsonrpc_server|vscode_enhanced_jsonrpc_server)" > /dev/null; then
            echo -e "${YELLOW}However, a JSON-RPC server process was found running.${NC}"
            echo "This might indicate the PID file was lost or the server was started manually."
        fi
    fi
    
    # Show instructions based on status
    if [ "$mcp_running" = "false" ]; then
        echo -e "${YELLOW}To start the MCP server, run: $0 start${NC}"
    else
        echo -e "${YELLOW}To view detailed server info: curl http://${HOST}:${PORT}/${NC}"
        echo -e "${YELLOW}To stop the server: $0 stop${NC}"
    fi
}

# Process command line arguments
case "$COMMAND" in
    stop)
        stop_server
        ;;
    status)
        check_status
        ;;
    start)
        start_server
        ;;
    restart)
        stop_server
        start_server
        ;;
    update-settings)
        update_vscode_settings
        ;;
    test)
        test_endpoints
        ;;
    *)
        # Default is to start the server
        start_server
        ;;
esac

exit 0
