#!/bin/bash
# IPFS-Kit MCP Service Management Script
# This script provides easy management of the IPFS-Kit MCP systemd service

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="ipfs-kit-mcp.service"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 {start|stop|restart|status|enable|disable|logs}"
    echo ""
    echo "Commands:"
    echo "  start    - Start the IPFS-Kit MCP service"
    echo "  stop     - Stop the IPFS-Kit MCP service"
    echo "  restart  - Restart the IPFS-Kit MCP service"
    echo "  status   - Show service status"
    echo "  enable   - Enable service to start on boot"
    echo "  disable  - Disable service auto-start"
    echo "  logs     - Show service logs"
    echo "  mcp      - Use the native MCP CLI (pass additional args)"
    echo ""
    echo "Examples:"
    echo "  $0 start"
    echo "  $0 status"
    echo "  $0 mcp status"
    echo "  $0 logs -f"
}

check_service_exists() {
    if ! systemctl list-unit-files | grep -q "$SERVICE_NAME"; then
        echo -e "${RED}Error: Service $SERVICE_NAME not found!${NC}"
        echo "Please run the installation script first."
        exit 1
    fi
}

case "${1:-}" in
    start)
        check_service_exists
        echo -e "${BLUE}Starting IPFS-Kit MCP service...${NC}"
        sudo systemctl start "$SERVICE_NAME"
        echo -e "${GREEN}✓ Service started${NC}"
        sleep 2
        systemctl status "$SERVICE_NAME" --no-pager
        ;;
    stop)
        check_service_exists
        echo -e "${BLUE}Stopping IPFS-Kit MCP service...${NC}"
        sudo systemctl stop "$SERVICE_NAME"
        echo -e "${GREEN}✓ Service stopped${NC}"
        ;;
    restart)
        check_service_exists
        echo -e "${BLUE}Restarting IPFS-Kit MCP service...${NC}"
        sudo systemctl restart "$SERVICE_NAME"
        echo -e "${GREEN}✓ Service restarted${NC}"
        sleep 2
        systemctl status "$SERVICE_NAME" --no-pager
        ;;
    status)
        check_service_exists
        systemctl status "$SERVICE_NAME" --no-pager
        echo ""
        echo -e "${BLUE}MCP CLI Status:${NC}"
        cd "$SCRIPT_DIR" && python ipfs_kit_cli.py mcp status
        ;;
    enable)
        check_service_exists
        echo -e "${BLUE}Enabling IPFS-Kit MCP service for auto-start...${NC}"
        sudo systemctl enable "$SERVICE_NAME"
        echo -e "${GREEN}✓ Service enabled for auto-start on boot${NC}"
        ;;
    disable)
        check_service_exists
        echo -e "${BLUE}Disabling IPFS-Kit MCP service auto-start...${NC}"
        sudo systemctl disable "$SERVICE_NAME"
        echo -e "${YELLOW}⚠ Service disabled - will not start on boot${NC}"
        ;;
    logs)
        check_service_exists
        shift # Remove 'logs' from arguments
        echo -e "${BLUE}Showing IPFS-Kit MCP service logs...${NC}"
        sudo journalctl -u "$SERVICE_NAME" "$@"
        ;;
    mcp)
        shift # Remove 'mcp' from arguments
        echo -e "${BLUE}Running MCP CLI command...${NC}"
        cd "$SCRIPT_DIR" && python ipfs_kit_cli.py mcp "$@"
        ;;
    "")
        usage
        exit 1
        ;;
    *)
        echo -e "${RED}Error: Unknown command '$1'${NC}"
        echo ""
        usage
        exit 1
        ;;
esac