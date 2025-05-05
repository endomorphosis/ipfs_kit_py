#!/bin/bash
#
# Enhanced MCP Server Startup Script
#
# This script starts the MCP server with all fixes and features,
# ensuring support for 53+ models.

set -e

# Default configuration
HOST="0.0.0.0"
PORT=3000
INTEGRATION=true
VERIFY=true
BACKUP=true
WAIT_TIME=5
LOGS_DIR="logs"
DEBUG=false

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Create logs directory if it doesn't exist
mkdir -p "$LOGS_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOGS_DIR/mcp_server_$TIMESTAMP.log"

# Show usage information
show_usage() {
    echo -e "${CYAN}Enhanced MCP Server Startup Script${NC}"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --host HOST            Host address to bind to (default: 0.0.0.0)"
    echo "  --port PORT            Port to listen on (default: 3000)"
    echo "  --no-integration       Skip feature integration"
    echo "  --no-verify            Skip server verification"
    echo "  --no-backup            Skip backup creation"
    echo "  --wait SECONDS         Seconds to wait for server startup (default: 5)"
    echo "  --debug                Enable debug mode"
    echo "  --help                 Show this help message"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --no-integration)
            INTEGRATION=false
            shift
            ;;
        --no-verify)
            VERIFY=false
            shift
            ;;
        --no-backup)
            BACKUP=false
            shift
            ;;
        --wait)
            WAIT_TIME="$2"
            shift 2
            ;;
        --debug)
            DEBUG=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_usage
            exit 1
            ;;
    esac
done

# Log function
log() {
    local level=$1
    local message=$2
    local color=$NC
    
    case $level in
        INFO)
            color=$GREEN
            ;;
        WARN)
            color=$YELLOW
            ;;
        ERROR)
            color=$RED
            ;;
        DEBUG)
            color=$BLUE
            if [[ "$DEBUG" != "true" ]]; then
                return
            fi
            ;;
    esac
    
    echo -e "${color}[$level] $(date '+%Y-%m-%d %H:%M:%S') - $message${NC}" | tee -a "$LOG_FILE"
}

# Check if required tools are available
check_dependencies() {
    log "INFO" "Checking dependencies..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log "ERROR" "Python 3 is required but not found"
        exit 1
    fi
    
    # Check Python version
    PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if [[ $(echo "$PY_VERSION < 3.6" | bc) -eq 1 ]]; then
        log "ERROR" "Python 3.6+ is required, found $PY_VERSION"
        exit 1
    fi
    
    log "INFO" "Using Python $PY_VERSION"
    
    # Check if required Python modules are available
    REQUIRED_MODULES=("jsonrpc" "asyncio" "aiohttp" "starlette" "fastapi" "uvicorn")
    MISSING_MODULES=()
    
    for module in "${REQUIRED_MODULES[@]}"; do
        if ! python3 -c "import $module" &> /dev/null; then
            MISSING_MODULES+=("$module")
        fi
    done
    
    if [[ ${#MISSING_MODULES[@]} -gt 0 ]]; then
        log "WARN" "Some required Python modules are missing: ${MISSING_MODULES[*]}"
        log "INFO" "Attempting to install missing modules..."
        
        for module in "${MISSING_MODULES[@]}"; do
            log "DEBUG" "Installing $module..."
            if ! pip3 install "$module"; then
                log "ERROR" "Failed to install $module"
                exit 1
            fi
        done
    fi
    
    log "INFO" "All dependencies satisfied"
}

# Stop any running MCP server
stop_running_server() {
    log "INFO" "Checking for running MCP server..."
    
    # Find PID of running MCP server process
    MCP_PID=$(ps aux | grep "[p]ython.*mcp.*server" | awk '{print $2}')
    
    if [[ -n "$MCP_PID" ]]; then
        log "INFO" "Found running MCP server (PID: $MCP_PID), stopping..."
        
        # Try graceful termination first
        kill -15 "$MCP_PID" 2>/dev/null || true
        
        # Wait a bit for the process to terminate
        sleep 2
        
        # Check if process is still running
        if ps -p "$MCP_PID" > /dev/null; then
            log "WARN" "Process did not terminate gracefully, forcing..."
            kill -9 "$MCP_PID" 2>/dev/null || true
        fi
        
        # Verify the process is gone
        if ! ps -p "$MCP_PID" > /dev/null; then
            log "INFO" "MCP server stopped successfully"
        else
            log "ERROR" "Failed to stop MCP server"
            exit 1
        fi
    else
        log "INFO" "No running MCP server found"
    fi
}

# Create backup of important files
create_backup() {
    if [[ "$BACKUP" != "true" ]]; then
        log "INFO" "Skipping backup creation"
        return
    fi
    
    log "INFO" "Creating backup of important files..."
    
    BACKUP_DIR="backup_files"
    mkdir -p "$BACKUP_DIR"
    
    FILES_TO_BACKUP=(
        "final_mcp_server.py"
        "direct_mcp_server.py"
        "start_final_mcp_server.sh"
    )
    
    for file in "${FILES_TO_BACKUP[@]}"; do
        if [[ -f "$file" ]]; then
            cp "$file" "$BACKUP_DIR/${file}.bak.$TIMESTAMP"
            log "DEBUG" "Backed up $file to $BACKUP_DIR/${file}.bak.$TIMESTAMP"
        fi
    done
    
    log "INFO" "Backup completed"
}

# Run feature integration
run_integration() {
    if [[ "$INTEGRATION" != "true" ]]; then
        log "INFO" "Skipping feature integration"
        return
    fi
    
    log "INFO" "Running feature integration..."
    
    if [[ ! -f "integrate_features.py" ]]; then
        log "ERROR" "integrate_features.py not found"
        exit 1
    fi
    
    chmod +x integrate_features.py
    
    if ! ./integrate_features.py; then
        log "ERROR" "Feature integration failed"
        exit 1
    fi
    
    log "INFO" "Feature integration completed successfully"
}

# Apply module patches
apply_patches() {
    log "INFO" "Applying module patches..."
    
    if [[ ! -f "mcp_module_patch.py" ]]; then
        log "ERROR" "mcp_module_patch.py not found"
        exit 1
    fi
    
    chmod +x mcp_module_patch.py
    
    if ! python3 mcp_module_patch.py; then
        log "ERROR" "Module patching failed"
        exit 1
    fi
    
    log "INFO" "Module patches applied successfully"
}

# Start the server
start_server() {
    log "INFO" "Starting MCP server on $HOST:$PORT..."
    
    # Check for server script files
    SERVER_SCRIPT=""
    if [[ -f "fixed_final_mcp_server.py" ]]; then
        SERVER_SCRIPT="fixed_final_mcp_server.py"
    elif [[ -f "final_mcp_server.py" ]]; then
        SERVER_SCRIPT="final_mcp_server.py"
    elif [[ -f "direct_mcp_server.py" ]]; then
        SERVER_SCRIPT="direct_mcp_server.py"
    else
        log "ERROR" "No server script found"
        exit 1
    fi
    
    log "INFO" "Using server script: $SERVER_SCRIPT"
    
    # Create launcher script if not exists
    if [[ ! -f "start_final_mcp.py" ]]; then
        log "INFO" "Creating launcher script..."
        cat > start_final_mcp.py << EOL
#!/usr/bin/env python3
"""
MCP Server Launcher

This script launches the MCP server with proper error handling
and environment setup.
"""

import os
import sys
import argparse
import subprocess
import logging
import importlib.util
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("server_launcher.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("server-launcher")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Launch MCP server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=3000, help='Port to listen on')
    parser.add_argument('--script', help='Server script to run')
    return parser.parse_args()

def apply_path_fixes():
    """Apply fixes to Python path to ensure proper module imports."""
    current_dir = os.getcwd()
    
    # Add current directory
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    # Add potential module directories
    module_dirs = [
        os.path.join(current_dir, "ipfs_kit_py"),
        os.path.join(current_dir, "vfs"),
    ]
    
    for module_dir in module_dirs:
        if os.path.isdir(module_dir) and module_dir not in sys.path:
            sys.path.insert(0, module_dir)
            logger.info(f"Added module directory to Python path: {module_dir}")

def find_best_server_script(specified_script=None):
    """Find the best server script to use."""
    if specified_script and os.path.isfile(specified_script):
        return specified_script
    
    preferred_scripts = [
        "fixed_final_mcp_server.py",
        "final_mcp_server.py",
        "direct_mcp_server.py"
    ]
    
    for script in preferred_scripts:
        if os.path.isfile(script):
            return script
    
    return None

def apply_patches():
    """Apply any necessary patches."""
    try:
        # Try to import the patch module
        if os.path.isfile("mcp_module_patch.py"):
            spec = importlib.util.spec_from_file_location("mcp_module_patch", "mcp_module_patch.py")
            patch_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(patch_module)
            
            # Apply all patches
            patch_module.apply_all_patches()
            logger.info("Applied patches from mcp_module_patch.py")
    except Exception as e:
        logger.warning(f"Error applying patches: {e}")

def main():
    """Main entry point."""
    args = parse_args()
    
    # Apply path fixes
    apply_path_fixes()
    
    # Apply patches
    apply_patches()
    
    # Find server script
    server_script = find_best_server_script(args.script)
    if not server_script:
        logger.error("No server script found")
        return 1
    
    logger.info(f"Using server script: {server_script}")
    
    try:
        # Start server as module
        logger.info(f"Starting server on {args.host}:{args.port}")
        
        cmd = [
            sys.executable,
            server_script,
            "--host", args.host,
            "--port", str(args.port)
        ]
        
        # Use subprocess to start the server
        process = subprocess.Popen(cmd)
        
        # Return the process exit code or 0 if it's still running
        return process.poll() or 0
    
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
EOL
        chmod +x start_final_mcp.py
        log "DEBUG" "Created launcher script: start_final_mcp.py"
    fi
    
    # Start the server
    nohup python3 start_final_mcp.py --host "$HOST" --port "$PORT" --script "$SERVER_SCRIPT" > "$LOGS_DIR/server_$TIMESTAMP.log" 2>&1 &
    SERVER_PID=$!
    
    log "INFO" "Server started with PID: $SERVER_PID"
    
    # Wait for server to start
    log "INFO" "Waiting $WAIT_TIME seconds for server to start..."
    sleep "$WAIT_TIME"
    
    # Check if server is still running
    if ! ps -p "$SERVER_PID" > /dev/null; then
        log "ERROR" "Server failed to start"
        cat "$LOGS_DIR/server_$TIMESTAMP.log"
        exit 1
    fi
    
    log "INFO" "Server is running on $HOST:$PORT"
}

# Verify server is working
verify_server() {
    if [[ "$VERIFY" != "true" ]]; then
        log "INFO" "Skipping server verification"
        return
    fi
    
    log "INFO" "Verifying server functionality..."
    
    if [[ ! -f "verify_fixed_mcp_tools.py" ]]; then
        log "ERROR" "verify_fixed_mcp_tools.py not found"
        exit 1
    fi
    
    chmod +x verify_fixed_mcp_tools.py
    
    VERIFICATION_OUTPUT="$LOGS_DIR/verification_$TIMESTAMP.json"
    
    if ! ./verify_fixed_mcp_tools.py --host "$HOST" --port "$PORT" --output "$VERIFICATION_OUTPUT" --wait 2; then
        log "ERROR" "Server verification failed"
        exit 1
    fi
    
    log "INFO" "Server verification completed successfully"
    log "INFO" "Verification report saved to: $VERIFICATION_OUTPUT"
}

# Main function
main() {
    log "INFO" "Starting enhanced MCP server setup..."
    
    check_dependencies
    stop_running_server
    create_backup
    run_integration
    apply_patches
    start_server
    verify_server
    
    log "INFO" "MCP server is now running on $HOST:$PORT"
    log "INFO" "Server logs: $LOGS_DIR/server_$TIMESTAMP.log"
    log "INFO" "Setup logs: $LOG_FILE"
    
    echo -e "\n${GREEN}=============================================${NC}"
    echo -e "${GREEN}MCP Server with 53+ model support is now running${NC}"
    echo -e "${GREEN}=============================================${NC}"
    echo -e "Server: ${CYAN}http://$HOST:$PORT${NC}"
    echo -e "To stop the server: ${YELLOW}./stop_ipfs_mcp_server.sh${NC}"
    echo -e "To verify the server: ${YELLOW}./verify_fixed_mcp_tools.py${NC}"
}

# Run the main function
main
