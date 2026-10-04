#!/bin/bash
##
# Update and Restart IPFS-Kit MCP Systemd Service
#
# This script:
# 1. Copies the updated service file to systemd
# 2. Reloads systemd configuration
# 3. Restarts the service
# 4. Shows the status
##

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="ipfs-kit-mcp.service"
SERVICE_FILE="${SCRIPT_DIR}/${SERVICE_NAME}"
SYSTEMD_DIR="/etc/systemd/system"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}IPFS-Kit MCP Service Update & Restart${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check if service file exists
if [ ! -f "$SERVICE_FILE" ]; then
    echo -e "${RED}Error: Service file not found: $SERVICE_FILE${NC}"
    exit 1
fi

echo -e "${BLUE}1. Checking current service status...${NC}"
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo -e "${GREEN}   ✓ Service is currently running${NC}"
    SHOULD_RESTART=true
else
    echo -e "${YELLOW}   ⚠ Service is not running${NC}"
    SHOULD_RESTART=false
fi
echo ""

echo -e "${BLUE}2. Copying updated service file to systemd...${NC}"
if sudo cp "$SERVICE_FILE" "$SYSTEMD_DIR/$SERVICE_NAME"; then
    echo -e "${GREEN}   ✓ Service file copied to $SYSTEMD_DIR/$SERVICE_NAME${NC}"
else
    echo -e "${RED}   ✗ Failed to copy service file${NC}"
    exit 1
fi
echo ""

echo -e "${BLUE}3. Reloading systemd daemon...${NC}"
if sudo systemctl daemon-reload; then
    echo -e "${GREEN}   ✓ Systemd daemon reloaded${NC}"
else
    echo -e "${RED}   ✗ Failed to reload systemd daemon${NC}"
    exit 1
fi
echo ""

if [ "$SHOULD_RESTART" = true ]; then
    echo -e "${BLUE}4. Restarting service...${NC}"
    if sudo systemctl restart "$SERVICE_NAME"; then
        echo -e "${GREEN}   ✓ Service restarted successfully${NC}"
    else
        echo -e "${RED}   ✗ Failed to restart service${NC}"
        exit 1
    fi
else
    echo -e "${BLUE}4. Starting service...${NC}"
    if sudo systemctl start "$SERVICE_NAME"; then
        echo -e "${GREEN}   ✓ Service started successfully${NC}"
    else
        echo -e "${RED}   ✗ Failed to start service${NC}"
        exit 1
    fi
fi
echo ""

echo -e "${BLUE}5. Waiting for service to stabilize...${NC}"
sleep 3
echo ""

echo -e "${BLUE}6. Service Status:${NC}"
echo -e "${BLUE}============================================${NC}"
systemctl status "$SERVICE_NAME" --no-pager || true
echo ""

echo -e "${BLUE}7. Recent logs:${NC}"
echo -e "${BLUE}============================================${NC}"
sudo journalctl -u "$SERVICE_NAME" --no-pager -n 20 --since "30 seconds ago" || true
echo ""

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}✓ Service update complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "To view live logs: ${YELLOW}sudo journalctl -u $SERVICE_NAME -f${NC}"
echo -e "To check status:   ${YELLOW}systemctl status $SERVICE_NAME${NC}"
echo -e "To stop service:   ${YELLOW}sudo systemctl stop $SERVICE_NAME${NC}"
echo ""
