#!/bin/bash

# Comprehensive MCP Dashboard Startup Script
# This script starts the comprehensive dashboard with all features enabled

set -e

# Configuration
DASHBOARD_HOST="${DASHBOARD_HOST:-127.0.0.1}"
DASHBOARD_PORT="${DASHBOARD_PORT:-8085}"
MCP_SERVER_URL="${MCP_SERVER_URL:-http://127.0.0.1:8004}"
DATA_DIR="${DATA_DIR:-~/.ipfs_kit}"
DEBUG="${DEBUG:-false}"
UPDATE_INTERVAL="${UPDATE_INTERVAL:-5}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Comprehensive MCP Dashboard${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${YELLOW}Configuration:${NC}"
echo "  • Host: $DASHBOARD_HOST"
echo "  • Port: $DASHBOARD_PORT"
echo "  • MCP Server URL: $MCP_SERVER_URL"
echo "  • Data Directory: $DATA_DIR"
echo "  • Debug Mode: $DEBUG"
echo "  • Update Interval: ${UPDATE_INTERVAL}s"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: Python 3 is required but not installed${NC}"
    exit 1
fi

# Check if the dashboard file exists
DASHBOARD_FILE="ipfs_kit_py/dashboard/comprehensive_mcp_dashboard.py"
if [ ! -f "$DASHBOARD_FILE" ]; then
    echo -e "${RED}❌ Error: Dashboard file not found: $DASHBOARD_FILE${NC}"
    exit 1
fi

# Create data directory if it doesn't exist
mkdir -p "$(eval echo $DATA_DIR)"

# Start the dashboard
echo -e "${GREEN}🔄 Starting dashboard server...${NC}"

# Build command arguments
ARGS="--host $DASHBOARD_HOST --port $DASHBOARD_PORT --mcp-server-url $MCP_SERVER_URL --data-dir $DATA_DIR --update-interval $UPDATE_INTERVAL"
if [ "$DEBUG" = "true" ]; then
    ARGS="$ARGS --debug"
fi

# Run the dashboard
python3 "$DASHBOARD_FILE" $ARGS

echo -e "${GREEN}✅ Dashboard stopped${NC}"
