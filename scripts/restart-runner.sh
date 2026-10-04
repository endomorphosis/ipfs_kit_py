#!/bin/bash

# Restart GitHub Actions Runner
# Safely restart the runner service

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

RUNNER_DIR="${RUNNER_DIR:-$HOME/actions-runner}"

echo -e "${GREEN}===================================================================="
echo "Restarting GitHub Actions Runner"
echo -e "====================================================================${NC}\n"

# Check if runner exists
if [ ! -d "$RUNNER_DIR" ]; then
    echo -e "${RED}Runner not found at: $RUNNER_DIR${NC}"
    exit 1
fi

cd "$RUNNER_DIR"

# Check if configured as service
if [ ! -f "svc.sh" ]; then
    echo -e "${RED}Runner is not configured as a service${NC}"
    echo "Run: sudo ./svc.sh install"
    exit 1
fi

echo "Stopping runner..."
sudo ./svc.sh stop || echo "Runner was not running"

sleep 2

echo "Starting runner..."
sudo ./svc.sh start

sleep 2

echo -e "\n${GREEN}Checking status...${NC}"
if sudo ./svc.sh status; then
    echo -e "\n${GREEN}✅ Runner restarted successfully!${NC}"
else
    echo -e "\n${RED}❌ Runner failed to start. Check logs:${NC}"
    echo "  journalctl -u actions.runner.* -n 50"
    exit 1
fi

echo -e "\n${GREEN}====================================================================${NC}"
