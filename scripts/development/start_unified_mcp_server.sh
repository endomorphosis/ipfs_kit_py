#!/bin/bash

# Unified MCP Server Startup Script with Virtual Environment
# This script activates the virtual environment and starts the unified server

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Project directory
PROJECT_DIR="/home/barberb/ipfs_kit_py"
VENV_DIR="$PROJECT_DIR/.venv"
SERVER_SCRIPT="$PROJECT_DIR/unified_observability_mcp_server.py"

echo -e "${BLUE}🚀 Starting Unified IPFS Kit MCP Server with Full Observability${NC}"
echo -e "${BLUE}================================================================${NC}"

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${RED}❌ Virtual environment not found at $VENV_DIR${NC}"
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    cd "$PROJECT_DIR"
    python3 -m venv .venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
echo -e "${BLUE}📦 Activating virtual environment...${NC}"
source "$VENV_DIR/bin/activate"

# Check if we're in the virtual environment
if [ "$VIRTUAL_ENV" = "" ]; then
    echo -e "${RED}❌ Failed to activate virtual environment${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Virtual environment activated: $VIRTUAL_ENV${NC}"

# Change to project directory
cd "$PROJECT_DIR"

# Install/update dependencies if needed
echo -e "${BLUE}📚 Checking dependencies...${NC}"
pip install -q --upgrade pip

# Install the project in development mode if not already installed
if ! pip show ipfs_kit_py > /dev/null 2>&1; then
    echo -e "${YELLOW}Installing ipfs_kit_py in development mode...${NC}"
    pip install -e .
fi

# Install additional dependencies for MCP and dashboard
echo -e "${YELLOW}Installing additional dependencies...${NC}"
pip install -q fastapi uvicorn websockets mcp jinja2 prometheus_client

echo -e "${GREEN}✓ Dependencies ready${NC}"

# Set environment variables for better observability
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
export IPFS_KIT_LOG_LEVEL="INFO"
export MCP_SERVER_HOST="${MCP_SERVER_HOST:-127.0.0.1}"
export MCP_SERVER_PORT="${MCP_SERVER_PORT:-8765}"

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"

echo -e "${BLUE}🌐 Server Configuration:${NC}"
echo -e "   Host: $MCP_SERVER_HOST"
echo -e "   Port: $MCP_SERVER_PORT"
echo -e "   Dashboard: http://$MCP_SERVER_HOST:$MCP_SERVER_PORT/"
echo -e "   MCP Endpoint: http://$MCP_SERVER_HOST:$MCP_SERVER_PORT/mcp"
echo -e "   WebSocket: ws://$MCP_SERVER_HOST:$MCP_SERVER_PORT/mcp/ws"
echo -e "   API Docs: http://$MCP_SERVER_HOST:$MCP_SERVER_PORT/docs"

echo -e "${BLUE}📊 Component Status Check:${NC}"

# Quick component availability check
python3 -c "
import sys
sys.path.insert(0, '$PROJECT_DIR')

components = {}

try:
    from mcp import ClientSession
    components['MCP Core'] = '✓'
except ImportError:
    components['MCP Core'] = '✗'

try:
    from fastapi import FastAPI
    components['FastAPI'] = '✓'
except ImportError:
    components['FastAPI'] = '✗'

try:
    from dashboard.config import DashboardConfig
    components['Dashboard'] = '✓'
except ImportError:
    components['Dashboard'] = '✗'

try:
    from ipfs_kit_py import IPFSKit
    components['IPFS Kit'] = '✓'
except ImportError:
    components['IPFS Kit'] = '✗'

for name, status in components.items():
    print(f'   {name}: {status}')
"

echo -e "${BLUE}🚀 Starting server...${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""

# Start the server with proper error handling
trap 'echo -e "\n${YELLOW}🛑 Shutting down server...${NC}"; exit 0' INT TERM

python3 "$SERVER_SCRIPT" --host "$MCP_SERVER_HOST" --port "$MCP_SERVER_PORT" "$@"
