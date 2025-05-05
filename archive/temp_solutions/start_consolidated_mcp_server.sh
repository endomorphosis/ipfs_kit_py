#!/bin/bash
#
# start_consolidated_mcp_server.sh
#
# Script to start the Consolidated MCP Server with various options
# This server integrates all IPFS and Virtual Filesystem (VFS) tools into a single server

# Define colors for output
GREEN="\033[92m"
RED="\033[91m"
YELLOW="\033[93m"
BLUE="\033[94m"
BOLD="\033[1m"
RESET="\033[0m"

# Default values
PORT=3000
HOST="127.0.0.1"
DEBUG=false
RELOAD=false
SHOW_HELP=false

# Parse command-line arguments
for arg in "$@"; do
    case $arg in
        --port=*)
            PORT="${arg#*=}"
            ;;
        --host=*)
            HOST="${arg#*=}"
            ;;
        --debug)
            DEBUG=true
            ;;
        --reload)
            RELOAD=true
            ;;
        --help)
            SHOW_HELP=true
            ;;
        *)
            echo -e "${RED}Unknown argument: $arg${RESET}"
            SHOW_HELP=true
            ;;
    esac
done

# Display help if requested
if [ "$SHOW_HELP" = true ]; then
    echo -e "${BOLD}Consolidated MCP Server Startup Script${RESET}"
    echo -e "Usage: ./start_consolidated_mcp_server.sh [options]"
    echo -e ""
    echo -e "Options:"
    echo -e "  --port=PORT      Set server port (default: 3000)"
    echo -e "  --host=HOST      Set server host (default: 127.0.0.1)"
    echo -e "  --debug          Enable debug mode"
    echo -e "  --reload         Enable auto-reload on code changes"
    echo -e "  --help           Display this help message"
    echo -e ""
    echo -e "Example:"
    echo -e "  ./start_consolidated_mcp_server.sh --port=8000 --host=0.0.0.0 --debug"
    exit 0
fi

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not found.${RESET}"
    exit 1
fi

# Check if consolidated_final_mcp_server.py exists
if [ ! -f "consolidated_final_mcp_server.py" ]; then
    echo -e "${RED}Error: consolidated_final_mcp_server.py not found in the current directory.${RESET}"
    exit 1
fi

# Construct command based on options
CMD="python3 consolidated_final_mcp_server.py --port $PORT --host $HOST"

if [ "$DEBUG" = true ]; then
    CMD="$CMD --debug"
fi

if [ "$RELOAD" = true ]; then
    CMD="$CMD --reload"
fi

# Print server startup information
echo -e "${BOLD}${BLUE}Starting Consolidated MCP Server${RESET}"
echo -e "${BLUE}----------------------------------------${RESET}"
echo -e "${BOLD}Host:${RESET} $HOST"
echo -e "${BOLD}Port:${RESET} $PORT"
echo -e "${BOLD}Debug:${RESET} $DEBUG"
echo -e "${BOLD}Reload:${RESET} $RELOAD"
echo -e "${BLUE}----------------------------------------${RESET}"
echo -e "${GREEN}Server will be available at:${RESET} http://$HOST:$PORT"
echo -e "${YELLOW}Health check at:${RESET} http://$HOST:$PORT/health"
echo -e "${YELLOW}Tools list at:${RESET} http://$HOST:$PORT/tools"
echo -e "${YELLOW}JSON-RPC endpoint at:${RESET} http://$HOST:$PORT/jsonrpc"
echo -e "${YELLOW}Initialize endpoint at:${RESET} http://$HOST:$PORT/initialize"
echo -e "${BLUE}----------------------------------------${RESET}"
echo -e "${GREEN}Press Ctrl+C to stop the server${RESET}"
echo -e ""

# Execute the command
echo -e "${BOLD}Executing:${RESET} $CMD"
echo -e ""
eval $CMD
