#!/bin/bash
# Start MCP IPFS Integration Server
# This script starts the MCP proxy server with IPFS integration

# Color configuration
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${GREEN}MCP IPFS Integration Server${NC}"
echo -e "${BLUE}================================${NC}"

# Check if IPFS is running
check_ipfs() {
    echo -e "${YELLOW}Checking IPFS daemon...${NC}"
    if curl -s http://localhost:5001/api/v0/version > /dev/null; then
        echo -e "${GREEN}✓ IPFS daemon is running${NC}"
        return 0
    else
        echo -e "${RED}✗ IPFS daemon is not running${NC}"
        return 1
    fi
}

# Start IPFS if it's not running
start_ipfs() {
    if ! check_ipfs; then
        echo -e "${YELLOW}Attempting to start IPFS daemon...${NC}"
        ipfs daemon --enable-pubsub-experiment > ipfs_daemon.log 2>&1 &
        IPFS_PID=$!
        echo $IPFS_PID > ipfs_daemon.pid
        # Wait for IPFS to start
        sleep 5
        if check_ipfs; then
            echo -e "${GREEN}Successfully started IPFS daemon (PID: $IPFS_PID)${NC}"
            return 0
        else
            echo -e "${RED}Failed to start IPFS daemon${NC}"
            echo -e "${YELLOW}You can try starting it manually with 'ipfs daemon --enable-pubsub-experiment'${NC}"
            return 1
        fi
    fi
}

# Check dependencies
check_dependencies() {
    echo -e "${YELLOW}Checking dependencies...${NC}"
    
    # Check Python version
    python_version=$(python3 --version 2>&1 | awk '{print $2}')
    echo -e "Python version: ${GREEN}$python_version${NC}"
    
    # Check required Python packages
    required_packages=("fastapi" "uvicorn" "aiohttp" "pydantic")
    for package in "${required_packages[@]}"; do
        if python3 -c "import $package" 2>/dev/null; then
            echo -e "✓ $package: ${GREEN}Installed${NC}"
        else
            echo -e "✗ $package: ${RED}Missing${NC}"
            echo -e "${YELLOW}You can install it with: pip install $package${NC}"
            missing_deps=true
        fi
    done
    
    if [ "$missing_deps" = true ]; then
        echo -e "${RED}Missing dependencies detected. Please install them and try again.${NC}"
        return 1
    fi
    
    echo -e "${GREEN}All dependencies installed${NC}"
    return 0
}

# Start MCP IPFS proxy server
start_mcp_proxy() {
    echo -e "${YELLOW}Starting MCP IPFS proxy server...${NC}"
    
    # Kill any existing proxy server
    if [ -f mcp_proxy.pid ]; then
        old_pid=$(cat mcp_proxy.pid)
        if ps -p $old_pid > /dev/null; then
            echo -e "${YELLOW}Killing existing proxy server (PID: $old_pid)${NC}"
            kill $old_pid
            sleep 1
        fi
    fi
    
    # Start SSE-enabled MCP server
    ./mcp_server_with_sse.py > mcp_proxy.log 2>&1 &
    PROXY_PID=$!
    echo $PROXY_PID > mcp_proxy.pid
    echo -e "${GREEN}Started MCP IPFS proxy server (PID: $PROXY_PID)${NC}"
    
    # Wait for server to start
    sleep 2
    if curl -s http://localhost:8000/health > /dev/null; then
        echo -e "${GREEN}✓ MCP IPFS proxy server is running${NC}"
        echo -e "${BLUE}Server URL: http://localhost:8000${NC}"
        echo -e "${BLUE}Health endpoint: http://localhost:8000/health${NC}"
        echo -e "${BLUE}Initialize endpoint: http://localhost:8000/initialize${NC}"
        return 0
    else
        echo -e "${RED}✗ MCP IPFS proxy server failed to start${NC}"
        cat mcp_proxy.log
        return 1
    fi
}

# Make the integration script executable
make_scripts_executable() {
    echo -e "${YELLOW}Making scripts executable...${NC}"
    chmod +x ipfs_mcp_proxy_server.py ipfs_mcp_fs_integration.py mcp_server_with_sse.py
    echo -e "${GREEN}✓ Made scripts executable${NC}"
}

# Main execution flow
main() {
    echo -e "${YELLOW}Starting MCP IPFS integration...${NC}"
    
    # Check dependencies
    if ! check_dependencies; then
        echo -e "${RED}Dependency check failed. Exiting.${NC}"
        exit 1
    fi
    
    # Make scripts executable
    make_scripts_executable
    
    # Start IPFS daemon if not running
    start_ipfs
    
    # Start MCP proxy server
    if ! start_mcp_proxy; then
        echo -e "${RED}Failed to start MCP proxy server. Exiting.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}=============================${NC}"
    echo -e "${GREEN}    Services are running!    ${NC}"
    echo -e "${GREEN}=============================${NC}"
    echo -e "${YELLOW}* To test the MCP server: ${NC}./test_mcp_tools.py"
    echo -e "${YELLOW}* To stop all services: ${NC}./stop_mcp_ipfs_integration.sh"
    echo -e "${YELLOW}* View logs: ${NC}tail -f mcp_proxy.log"
    echo -e "${GREEN}=============================${NC}"
}

# Run the main function
main
