#!/bin/bash

# GitHub Actions Self-Hosted Runner Setup Script for AMD64
# Repository: endomorphosis/ipfs_kit_py

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}===================================================================="
echo "GitHub Actions Self-Hosted Runner Setup"
echo "Repository: endomorphosis/ipfs_kit_py"
echo -e "====================================================================${NC}"

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
        DEFAULT_LABELS="self-hosted,linux,arm64,dgx"
        ;;
    armv7l)
        RUNNER_ARCH="arm"
        DEFAULT_LABELS="self-hosted,linux,arm"
        ;;
    *)
        echo -e "${RED}Unsupported architecture: $ARCH${NC}"
        exit 1
        ;;
esac

echo -e "${GREEN}Detected architecture: $ARCH (GitHub: $RUNNER_ARCH)${NC}"

# Configuration
RUNNER_VERSION="${RUNNER_VERSION:-2.311.0}"
GITHUB_REPO="${GITHUB_REPO:-endomorphosis/ipfs_kit_py}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

# Support multiple repositories - create unique directory per repo
REPO_SAFE_NAME=$(echo "$GITHUB_REPO" | sed 's/\//-/g')
RUNNER_DIR="${RUNNER_DIR:-$HOME/actions-runners/$REPO_SAFE_NAME}"
RUNNER_NAME="${RUNNER_NAME:-$(hostname)-$ARCH-$REPO_SAFE_NAME}"
RUNNER_LABELS="${RUNNER_LABELS:-$DEFAULT_LABELS}"

# Get registration token - support both methods
REGISTRATION_TOKEN="${REGISTRATION_TOKEN:-}"

if [ -z "$REGISTRATION_TOKEN" ]; then
    echo -e "\n${YELLOW}Choose token method:${NC}"
    echo "1) Paste registration token from GitHub (easiest)"
    echo "2) Use Personal Access Token (PAT) - for automation"
    echo ""
    read -p "Choice (1 or 2): " TOKEN_METHOD
    
    if [ "$TOKEN_METHOD" = "1" ]; then
        echo -e "\n${GREEN}Get your registration token:${NC}"
        echo "1. Go to: https://github.com/$GITHUB_REPO/settings/actions/runners/new"
        echo "2. Scroll down to 'Configure' section"
        echo "3. Copy the token from the './config.sh' command"
        echo "   (It looks like: AAZ7LEUVCMVXDGJFY3FH3JDI6WQ6W)"
        echo ""
        echo "Paste the registration token:"
        read -r REGISTRATION_TOKEN
    else
        echo -e "\n${YELLOW}Enter your GitHub Personal Access Token:${NC}"
        echo -e "${YELLOW}(Token needs 'repo' and 'workflow' scopes)${NC}"
        echo -e "${BLUE}Create one at: https://github.com/settings/tokens${NC}"
        read -rs GITHUB_TOKEN
        echo
        
        if [ -z "$GITHUB_TOKEN" ]; then
            echo -e "${RED}Error: GitHub token is required${NC}"
            exit 1
        fi
    fi
fi

# Show configuration
echo -e "\n${BLUE}Configuration:${NC}"
echo -e "  Repository: ${GREEN}$GITHUB_REPO${NC}"
echo -e "  Runner Name: ${GREEN}$RUNNER_NAME${NC}"
echo -e "  Runner Labels: ${GREEN}$RUNNER_LABELS${NC}"
echo -e "  Install Directory: ${GREEN}$RUNNER_DIR${NC}"
echo ""

# Check if runner already exists for this repo
if [ -d "$RUNNER_DIR" ]; then
    echo -e "${YELLOW}⚠️  A runner already exists for this repository at:${NC}"
    echo "   $RUNNER_DIR"
    echo ""
    read -p "Replace it? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled. Existing runner preserved."
        exit 0
    fi
    # Stop and remove existing service if present
    if [ -f "$RUNNER_DIR/svc.sh" ]; then
        echo "Stopping existing service..."
        sudo "$RUNNER_DIR/svc.sh" stop 2>/dev/null || true
        sudo "$RUNNER_DIR/svc.sh" uninstall 2>/dev/null || true
    fi
fi

read -p "Continue with these settings? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled."
    exit 1
fi

# Install dependencies
echo -e "\n${GREEN}Step 1: Installing system dependencies...${NC}"

# Check if dependencies are already installed
MISSING_DEPS=()
command -v curl >/dev/null 2>&1 || MISSING_DEPS+=("curl")
command -v jq >/dev/null 2>&1 || MISSING_DEPS+=("jq")
dpkg -l | grep -q libssl-dev || MISSING_DEPS+=("libssl-dev")
dpkg -l | grep -q libffi-dev || MISSING_DEPS+=("libffi-dev")

if [ ${#MISSING_DEPS[@]} -eq 0 ]; then
    echo "✓ All dependencies already installed"
else
    echo "Installing missing packages: ${MISSING_DEPS[*]}"
    sudo apt-get update -qq 2>&1 | grep -v "^W:" | grep -v "^E:" || true
    sudo apt-get install -y "${MISSING_DEPS[@]}" 2>&1 | grep -v "^W:" || true
    echo "✓ Dependencies installed"
fi

# Create runner directory
echo -e "\n${GREEN}Step 2: Creating runner directory...${NC}"
mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

# Download runner package
echo -e "\n${GREEN}Step 3: Downloading GitHub Actions runner...${NC}"
RUNNER_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"
echo "Downloading from: $RUNNER_URL"
curl -o actions-runner.tar.gz -L "$RUNNER_URL"

# Extract
echo -e "\n${GREEN}Step 4: Extracting runner package...${NC}"
tar xzf ./actions-runner.tar.gz
rm actions-runner.tar.gz

# Get registration token (if not already provided)
echo -e "\n${GREEN}Step 5: Getting registration token...${NC}"

if [ -z "$REGISTRATION_TOKEN" ] && [ -n "$GITHUB_TOKEN" ]; then
    echo "Fetching token from GitHub API..."
    REGISTRATION_TOKEN=$(curl -s -X POST \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3+json" \
        "https://api.github.com/repos/$GITHUB_REPO/actions/runners/registration-token" | jq -r .token)
    
    if [ -z "$REGISTRATION_TOKEN" ] || [ "$REGISTRATION_TOKEN" == "null" ]; then
        echo -e "${RED}Failed to get registration token. Please check your token permissions.${NC}"
        exit 1
    fi
elif [ -n "$REGISTRATION_TOKEN" ]; then
    echo "Using provided registration token..."
else
    echo -e "${RED}Error: No registration token available${NC}"
    exit 1
fi

# Configure runner
echo -e "\n${GREEN}Step 6: Configuring the runner...${NC}"
./config.sh \
    --url "https://github.com/$GITHUB_REPO" \
    --token "$REGISTRATION_TOKEN" \
    --name "$RUNNER_NAME" \
    --labels "$RUNNER_LABELS" \
    --unattended \
    --replace

# Install as service with proper user context
echo -e "\n${GREEN}Step 7: Installing runner as a systemd service...${NC}"
echo "Installing service for user: $USER"
sudo ./svc.sh install "$USER"

echo -e "\n${GREEN}Step 8: Starting the runner service...${NC}"
sudo ./svc.sh start

# Wait a moment for service to start
sleep 2

# Check status
echo -e "\n${GREEN}Step 9: Verifying runner service status...${NC}"
if sudo ./svc.sh status; then
    echo -e "${GREEN}✓ Service is running${NC}"
else
    echo -e "${YELLOW}⚠️  Service may be starting up. Check with: sudo systemctl status actions.runner.*${NC}"
fi

# Show systemctl unit name
SERVICE_NAME=$(systemctl list-units --type=service --all | grep -o "actions.runner[^[:space:]]*" | grep "$REPO_SAFE_NAME" | head -1 || echo "actions.runner.*")
if [ -n "$SERVICE_NAME" ] && [ "$SERVICE_NAME" != "actions.runner.*" ]; then
    echo -e "\n${BLUE}Systemd service name: ${GREEN}$SERVICE_NAME${NC}"
    echo "Manage with systemctl commands:"
    echo "  sudo systemctl status $SERVICE_NAME"
    echo "  sudo systemctl restart $SERVICE_NAME"
    echo "  sudo journalctl -u $SERVICE_NAME -f"
fi

echo -e "\n${GREEN}===================================================================="
echo "✅ GitHub Actions Runner Setup Complete!"
echo "===================================================================="
echo "Runner Name: $RUNNER_NAME"
echo "Labels: $RUNNER_LABELS"
echo "Repository: $GITHUB_REPO"
echo "Runner Directory: $RUNNER_DIR"
echo ""
echo "Verify runner at:"
echo "  https://github.com/$GITHUB_REPO/settings/actions/runners"
echo ""
echo "Systemctl commands:"
if [ -n "$SERVICE_NAME" ] && [ "$SERVICE_NAME" != "actions.runner.*" ]; then
    echo "  sudo systemctl status $SERVICE_NAME"
    echo "  sudo systemctl restart $SERVICE_NAME"
    echo "  sudo systemctl stop $SERVICE_NAME"
    echo "  sudo systemctl start $SERVICE_NAME"
    echo "  sudo journalctl -u $SERVICE_NAME -f"
else
    echo "  sudo systemctl status actions.runner.*"
    echo "  sudo systemctl restart actions.runner.*"
    echo "  sudo journalctl -u actions.runner.* -f"
fi
echo ""
echo "Runner script commands:"
echo "  Check status:    sudo $RUNNER_DIR/svc.sh status"
echo "  Stop runner:     sudo $RUNNER_DIR/svc.sh stop"
echo "  Start runner:    sudo $RUNNER_DIR/svc.sh start"
echo ""
echo "Management scripts:"
echo "  List all runners:    ./scripts/list-runners.sh"
echo "  Monitor runner:      RUNNER_DIR=$RUNNER_DIR ./scripts/monitor-runner.sh"
echo "  Restart runner:      RUNNER_DIR=$RUNNER_DIR ./scripts/restart-runner.sh"
echo "  Remove runner:       RUNNER_DIR=$RUNNER_DIR ./scripts/remove-runner.sh"
echo ""
echo "To add another repository:"
echo "  GITHUB_REPO=owner/repo ./scripts/setup-github-runner.sh"
echo -e "====================================================================${NC}"
