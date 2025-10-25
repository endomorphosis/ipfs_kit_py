#!/bin/bash

# Add Runner for Another Repository
# Quick script to add runners for multiple repositories

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}===================================================================="
echo "Add Runner for Another Repository"
echo -e "====================================================================${NC}\n"

# Get repository name
echo -e "${BLUE}Enter the repository (format: owner/repo):${NC}"
read -p "Repository: " GITHUB_REPO

if [ -z "$GITHUB_REPO" ]; then
    echo "No repository specified. Exiting."
    exit 1
fi

# Validate format
if [[ ! "$GITHUB_REPO" =~ ^[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$ ]]; then
    echo -e "${YELLOW}Warning: Repository format looks unusual.${NC}"
    echo "Expected format: owner/repo (e.g., endomorphosis/ipfs_kit_py)"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

export GITHUB_REPO

echo -e "\n${GREEN}Setting up runner for: $GITHUB_REPO${NC}\n"
echo "You'll need a registration token or PAT for this repository."
echo ""
echo "Get a registration token at:"
echo "  https://github.com/$GITHUB_REPO/settings/actions/runners/new"
echo ""
read -p "Press Enter when ready..."

# Run the setup script
./scripts/setup-github-runner.sh
