#!/bin/bash

# Setup Multiple GitHub Actions Runners
# Creates multiple runner instances on the same machine

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}===================================================================="
echo "Setup Multiple GitHub Actions Runners"
echo -e "====================================================================${NC}\n"

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}Please do not run this script as root${NC}"
   exit 1
fi

# Detect architecture
ARCH=$(uname -m)
case $ARCH in
    x86_64)
        RUNNER_ARCH="x64"
        DEFAULT_LABELS="self-hosted,linux,x64,amd64"
        ;;
    aarch64|arm64)
        RUNNER_ARCH="arm64"
        DEFAULT_LABELS="self-hosted,linux,arm64"
        ;;
    *)
        echo -e "${RED}Unsupported architecture: $ARCH${NC}"
        exit 1
        ;;
esac

# Configuration
RUNNER_VERSION="${RUNNER_VERSION:-2.311.0}"
GITHUB_REPO="${GITHUB_REPO:-endomorphosis/ipfs_kit_py}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
BASE_DIR="$HOME/actions-runners"

# Get GitHub token
if [ -z "$GITHUB_TOKEN" ]; then
    echo -e "${YELLOW}Please enter your GitHub Personal Access Token:${NC}"
    read -rs GITHUB_TOKEN
    echo
fi

if [ -z "$GITHUB_TOKEN" ]; then
    echo -e "${RED}GitHub token is required${NC}"
    exit 1
fi

# Ask for number of runners
echo -e "${BLUE}How many runners do you want to create?${NC}"
read -p "Number of runners (1-5): " NUM_RUNNERS

if ! [[ "$NUM_RUNNERS" =~ ^[1-5]$ ]]; then
    echo -e "${RED}Invalid number. Must be between 1 and 5.${NC}"
    exit 1
fi

# Create base directory
mkdir -p "$BASE_DIR"

echo -e "\n${GREEN}Setting up $NUM_RUNNERS runner(s)...${NC}\n"

# Install dependencies once
echo -e "${GREEN}Installing system dependencies...${NC}"
sudo apt-get update -qq
sudo apt-get install -y curl jq libssl-dev libffi-dev

# Setup each runner
for i in $(seq 1 $NUM_RUNNERS); do
    RUNNER_DIR="$BASE_DIR/runner-$i"
    RUNNER_NAME="$(hostname)-$ARCH-runner-$i"
    
    echo -e "\n${BLUE}===================================================================="
    echo "Setting up Runner $i of $NUM_RUNNERS"
    echo -e "====================================================================${NC}"
    
    # Create runner directory
    mkdir -p "$RUNNER_DIR"
    cd "$RUNNER_DIR"
    
    # Download runner if not already present
    if [ ! -f "config.sh" ]; then
        echo "Downloading GitHub Actions runner..."
        RUNNER_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"
        curl -o actions-runner.tar.gz -L "$RUNNER_URL"
        tar xzf ./actions-runner.tar.gz
        rm actions-runner.tar.gz
    else
        echo "Runner already downloaded, skipping..."
    fi
    
    # Get registration token
    echo "Getting registration token..."
    REGISTRATION_TOKEN=$(curl -s -X POST \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3+json" \
        "https://api.github.com/repos/$GITHUB_REPO/actions/runners/registration-token" | jq -r .token)
    
    if [ -z "$REGISTRATION_TOKEN" ] || [ "$REGISTRATION_TOKEN" == "null" ]; then
        echo -e "${RED}Failed to get registration token for runner $i${NC}"
        continue
    fi
    
    # Configure runner
    echo "Configuring runner..."
    ./config.sh \
        --url "https://github.com/$GITHUB_REPO" \
        --token "$REGISTRATION_TOKEN" \
        --name "$RUNNER_NAME" \
        --labels "$DEFAULT_LABELS" \
        --unattended \
        --replace
    
    # Install as service
    echo "Installing as service..."
    sudo ./svc.sh install
    sudo ./svc.sh start
    
    echo -e "${GREEN}✅ Runner $i configured and started${NC}"
    sleep 2
done

echo -e "\n${GREEN}===================================================================="
echo "✅ All runners setup complete!"
echo -e "====================================================================${NC}"
echo "Base directory: $BASE_DIR"
echo "Runners created: $NUM_RUNNERS"
echo ""
echo "Verify at: https://github.com/$GITHUB_REPO/settings/actions/runners"
echo ""
echo "Management commands:"
echo "  List all: ls -la $BASE_DIR"
echo "  Status:   sudo $BASE_DIR/runner-1/svc.sh status"
echo "  Stop all: for i in {1..$NUM_RUNNERS}; do sudo $BASE_DIR/runner-\$i/svc.sh stop; done"
echo -e "${GREEN}====================================================================${NC}"
