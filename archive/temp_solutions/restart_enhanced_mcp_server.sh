#!/bin/bash
# 
# Restart Enhanced MCP Server
#
# This script restarts the consolidated final MCP server with IPFS and VFS tools.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Log functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Stop any running MCP server instances
log_info "Stopping any running MCP server instances..."
if [ -f "stop_ipfs_mcp_server.sh" ]; then
    bash stop_ipfs_mcp_server.sh || true
fi

# Kill any stray Python processes running final_mcp_server.py
pkill -f "python.*final_mcp_server.py" 2>/dev/null || true
pkill -f "python.*fixed_final_mcp_server.py" 2>/dev/null || true
sleep 1

# Check if the final_mcp_server.py file exists
if [ ! -f "final_mcp_server.py" ]; then
    log_error "final_mcp_server.py not found. Please make sure it exists in the current directory."
    exit 1
fi

# Make backup of original file
log_info "Creating backup of original server file..."
cp -f final_mcp_server.py final_mcp_server.py.bak.$(date "+%Y%m%d%H%M%S") || true

# Run pre-start verification tests
log_info "Verifying IPFS tool coverage..."
python3 test_ipfs_mcp_tools.py --dry-run --output test_coverage.json

# Start the MCP server
log_info "Starting final MCP server..."

# Set up environment variables
export MCP_PORT=3000
export MCP_HOST="0.0.0.0"
export MCP_DEBUG=false

# Start the server
python3 final_mcp_server.py --port $MCP_PORT --host $MCP_HOST &
SERVER_PID=$!

# Wait a moment for the server to start
sleep 2

# Check if the server is running
if ps -p $SERVER_PID > /dev/null; then
    log_success "Final MCP server started successfully with PID $SERVER_PID"
    # Save PID to file for later reference
    echo $SERVER_PID > final_mcp_server.pid
    
    log_info "Running tool verification test..."
    python3 test_ipfs_mcp_tools.py --output tool_verification.json
    
    if [ $? -eq 0 ]; then
        log_success "Tool verification successful!"
    else
        log_warning "Tool verification completed with errors. Check tool_verification.json for details."
    fi
    
    log_info "To stop the server, run: kill $SERVER_PID or ./stop_ipfs_mcp_server.sh"
else
    log_error "Failed to start the MCP server"
    exit 1
fi

# Print server information
log_success "======================================="
log_success "Final MCP Server is now running"
log_success "URL: http://localhost:$MCP_PORT"
log_success "Tools available at: http://localhost:$MCP_PORT/jsonrpc"
log_success "Health endpoint: http://localhost:$MCP_PORT/health"
log_success "======================================="
