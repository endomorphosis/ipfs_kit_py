#!/bin/bash

# GitHub Actions Runner Removal Script
# Safely removes a GitHub Actions self-hosted runner

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}===================================================================="
echo "GitHub Actions Runner Removal"
echo -e "====================================================================${NC}"

# Configuration
RUNNER_DIR="${RUNNER_DIR:-$HOME/actions-runner}"
GITHUB_REPO="${GITHUB_REPO:-endomorphosis/ipfs_kit_py}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

# Check if runner directory exists
if [ ! -d "$RUNNER_DIR" ]; then
    echo -e "${RED}Runner directory not found: $RUNNER_DIR${NC}"
    echo "No runner to remove."
    exit 0
fi

cd "$RUNNER_DIR"

echo -e "${YELLOW}Runner directory: $RUNNER_DIR${NC}"

# Check if runner is configured
if [ ! -f ".runner" ]; then
    echo -e "${YELLOW}Runner is not configured.${NC}"
    read -p "Delete runner directory anyway? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cd ..
        rm -rf "$RUNNER_DIR"
        echo -e "${GREEN}Runner directory removed.${NC}"
    fi
    exit 0
fi

# Stop the service if running
echo -e "\n${GREEN}Step 1: Stopping runner service...${NC}"
if [ -f "svc.sh" ]; then
    sudo ./svc.sh stop || echo "Service was not running"
    sudo ./svc.sh uninstall || echo "Service was not installed"
else
    echo "Service script not found, skipping..."
fi

# Get removal token if token provided
if [ -z "$GITHUB_TOKEN" ]; then
    echo -e "\n${YELLOW}Step 2: Removing runner from GitHub...${NC}"
    echo -e "${YELLOW}No GitHub token provided. You'll need to remove manually.${NC}"
    echo "Remove the runner at: https://github.com/$GITHUB_REPO/settings/actions/runners"
    read -p "Press Enter once you've removed it from GitHub..."
else
    echo -e "\n${GREEN}Step 2: Getting removal token from GitHub...${NC}"
    REMOVAL_TOKEN=$(curl -s -X POST \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3+json" \
        "https://api.github.com/repos/$GITHUB_REPO/actions/runners/remove-token" | jq -r .token)
    
    if [ -z "$REMOVAL_TOKEN" ] || [ "$REMOVAL_TOKEN" == "null" ]; then
        echo -e "${RED}Failed to get removal token. You may need to remove manually.${NC}"
        echo "Remove at: https://github.com/$GITHUB_REPO/settings/actions/runners"
    else
        echo -e "${GREEN}Step 3: Removing runner from GitHub...${NC}"
        ./config.sh remove --token "$REMOVAL_TOKEN" || echo "Runner may have already been removed"
    fi
fi

# Remove directory
echo -e "\n${GREEN}Step 4: Removing runner directory...${NC}"
cd ..
rm -rf "$RUNNER_DIR"

echo -e "\n${GREEN}===================================================================="
echo "✅ Runner removed successfully!"
echo -e "====================================================================${NC}"
echo "Verify removal at: https://github.com/$GITHUB_REPO/settings/actions/runners"
