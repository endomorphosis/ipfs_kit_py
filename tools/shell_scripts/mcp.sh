#!/bin/bash
# MCP Server Manager
# A simple wrapper script to manage the MCP server

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Print header
echo -e "${BOLD}MCP Server Manager${NC}"
echo "A simple tool to manage the Model Context Protocol server"
echo "Current date: $(date)"
echo

# Show help message
show_help() {
    echo "Usage: $0 [COMMAND]"
    echo
    echo "Commands:"
    echo "  start       Start the MCP server"
    echo "  stop        Stop the MCP server"
    echo "  restart     Restart the MCP server"
    echo "  status      Show server status"
    echo "  info        Show detailed server information"
    echo "  test        Run tests against the server"
    echo "  tools       List all registered tools"
    echo "  cleanup     Stop server and clean up temporary files"
    echo "  help        Show this help message"
    echo
}

# Check if Python and required scripts exist
check_requirements() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Error: python3 is required but not installed${NC}"
        exit 1
    fi
    
    if [ ! -f "check_server.py" ]; then
        echo -e "${RED}Error: check_server.py not found in current directory${NC}"
        exit 1
    fi
    
    if [ ! -f "final_mcp_server.py" ]; then
        echo -e "${RED}Error: final_mcp_server.py not found in current directory${NC}"
        exit 1
    fi
    
    # Make sure check_server.py is executable
    chmod +x check_server.py &> /dev/null
}

# Execute chosen command
if [ $# -eq 0 ]; then
    show_help
    exit 0
fi

check_requirements

case "$1" in
    start)
        echo -e "${BLUE}Starting MCP server...${NC}"
        ./check_server.py --start
        ;;
    stop)
        echo -e "${BLUE}Stopping MCP server...${NC}"
        ./check_server.py --stop
        ;;
    restart)
        echo -e "${BLUE}Restarting MCP server...${NC}"
        ./check_server.py --restart
        ;;
    status)
        echo -e "${BLUE}Checking MCP server status...${NC}"
        ./check_server.py
        ;;
    info)
        echo -e "${BLUE}Getting server information...${NC}"
        ./check_server.py --info
        ;;
    test)
        echo -e "${BLUE}Running tests against the MCP server...${NC}"
        ./run_enhanced_solution.sh --test-only
        ;;
    tools)
        echo -e "${BLUE}Listing registered tools...${NC}"
        ./check_server.py --list-tools
        ;;
    cleanup)
        echo -e "${BLUE}Cleaning up MCP server...${NC}"
        ./cleanup_mcp_server.sh
        ;;
    help)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo
        show_help
        exit 1
        ;;
esac

exit $?
