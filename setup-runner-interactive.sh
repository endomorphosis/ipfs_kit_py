#!/bin/bash

# Interactive GitHub Actions Runner Setup
# Guides you through getting a token and setting up the runner

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

clear
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗"
echo "║        GitHub Actions Runner - Interactive Setup               ║"
echo "║        Repository: endomorphosis/ipfs_kit_py                   ║"
echo -e "╚══════════════════════════════════════════════════════════════════╝${NC}\n"

# Check if already setup
if [ -d "$HOME/actions-runner" ] && [ -f "$HOME/actions-runner/.runner" ]; then
    echo -e "${YELLOW}⚠️  A runner is already installed!${NC}\n"
    echo "Runner directory: $HOME/actions-runner"
    
    if [ -f "$HOME/actions-runner/svc.sh" ]; then
        echo -n "Status: "
        if sudo "$HOME/actions-runner/svc.sh" status > /dev/null 2>&1; then
            echo -e "${GREEN}Running ✓${NC}"
        else
            echo -e "${RED}Stopped ✗${NC}"
        fi
    fi
    
    echo ""
    echo "Options:"
    echo "  1) View runner status (./scripts/list-runners.sh)"
    echo "  2) Monitor runner (./scripts/monitor-runner.sh)"
    echo "  3) Remove existing runner and setup new one"
    echo "  4) Exit"
    echo ""
    read -p "Choose (1-4): " CHOICE
    
    case $CHOICE in
        1)
            ./scripts/list-runners.sh
            exit 0
            ;;
        2)
            ./scripts/monitor-runner.sh
            exit 0
            ;;
        3)
            echo -e "\n${YELLOW}Removing existing runner...${NC}"
            ./scripts/remove-runner.sh
            echo -e "${GREEN}Existing runner removed. Continuing with setup...${NC}\n"
            sleep 2
            ;;
        *)
            exit 0
            ;;
    esac
fi

# Step 1: Explain what we're doing
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}📋 What This Will Do:${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
echo "This script will:"
echo "  ✓ Set up a self-hosted GitHub Actions runner on this machine"
echo "  ✓ Configure it for the ipfs_kit_py repository"
echo "  ✓ Install it as a service (auto-starts on reboot)"
echo "  ✓ Enable your AMD64 CI/CD workflows to run"
echo ""
echo "Workflows that will start working:"
echo "  • amd64-ci.yml (AMD64 CI/CD Pipeline)"
echo "  • multi-arch-ci.yml (AMD64 native tests)"
echo ""
read -p "Press Enter to continue..."
clear

# Step 2: Get GitHub Token
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}🔑 Step 1: GitHub Personal Access Token${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo "You need a token from GitHub to register the runner."
echo ""
echo -e "${CYAN}━━━━ EASIEST METHOD (Recommended) ━━━━${NC}"
echo ""
echo -e "${GREEN}Option 1: Use Registration Token (from GitHub UI)${NC}"
echo ""
echo "  1. Open this URL in your browser:"
echo -e "     ${GREEN}https://github.com/endomorphosis/ipfs_kit_py/settings/actions/runners/new${NC}"
echo ""
echo "  2. Scroll down to the 'Configure' section"
echo ""
echo "  3. Find the line that says './config.sh --url...' "
echo ""
echo "  4. Copy JUST the token part after '--token'"
echo "     (Looks like: AAZ7LEUVCMVXDGJFY3FH3JDI6WQ6W)"
echo ""
echo -e "${CYAN}━━━━ ALTERNATIVE (For Automation) ━━━━${NC}"
echo ""
echo -e "${YELLOW}Option 2: Create a Personal Access Token (PAT)${NC}"
echo ""
echo "  1. Go to: https://github.com/settings/tokens"
echo "  2. Generate new token with 'repo' + 'workflow' scopes"
echo ""

# Check for existing tokens
REGISTRATION_TOKEN="${REGISTRATION_TOKEN:-}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

if [ -n "$REGISTRATION_TOKEN" ]; then
    echo -e "${GREEN}✓ Registration token found in environment${NC}"
    echo ""
elif [ -n "$GITHUB_TOKEN" ]; then
    echo -e "${GREEN}✓ Personal Access Token found in environment${NC}"
    echo ""
    read -p "Use this token? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        GITHUB_TOKEN=""
    fi
fi

# Get token from user if not set
if [ -z "$REGISTRATION_TOKEN" ] && [ -z "$GITHUB_TOKEN" ]; then
    echo -e "${YELLOW}Which token type do you have?${NC}"
    echo "  1) Registration token (from GitHub UI)"
    echo "  2) Personal Access Token (PAT)"
    echo ""
    read -p "Choice (1 or 2): " TOKEN_CHOICE
    echo ""
    
    if [ "$TOKEN_CHOICE" = "1" ]; then
        echo "Paste your registration token (visible):"
        read -r REGISTRATION_TOKEN
        
        if [ -z "$REGISTRATION_TOKEN" ]; then
            echo -e "${RED}Error: No token provided${NC}"
            exit 1
        fi
        
        export REGISTRATION_TOKEN
    else
        echo "Paste your Personal Access Token (hidden):"
        read -rs GITHUB_TOKEN
        echo ""
        
        if [ -z "$GITHUB_TOKEN" ]; then
            echo -e "${RED}Error: No token provided${NC}"
            exit 1
        fi
        
        # Basic validation
        if [[ ! $GITHUB_TOKEN =~ ^gh[ps]_ ]]; then
            echo -e "${YELLOW}⚠️  Warning: Token doesn't look like a GitHub PAT (should start with 'ghp_')${NC}"
            read -p "Continue anyway? (y/n) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
        
        export GITHUB_TOKEN
    fi
fi

echo -e "${GREEN}✓ Token received${NC}\n"
sleep 1
clear

# Step 3: Show configuration
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}⚙️  Step 2: Configuration${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

ARCH=$(uname -m)
RUNNER_NAME="$(hostname)-$ARCH-runner"
echo "The runner will be configured with:"
echo ""
echo "  Repository:  endomorphosis/ipfs_kit_py"
echo "  Runner Name: $RUNNER_NAME"
echo "  Labels:      self-hosted, linux, x64, amd64"
echo "  Directory:   $HOME/actions-runner"
echo ""
read -p "Looks good? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled."
    exit 1
fi

clear

# Step 4: Run the setup
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}🚀 Step 3: Installing Runner${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo "Running setup script..."
echo ""

# Run the actual setup script
if ./scripts/setup-github-runner.sh; then
    clear
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗"
    echo "║                   🎉 SUCCESS! 🎉                                ║"
    echo "║        GitHub Actions Runner Setup Complete!                   ║"
    echo -e "╚══════════════════════════════════════════════════════════════════╝${NC}\n"
    
    echo -e "${CYAN}✅ Your runner is now active!${NC}\n"
    
    echo "Verify it's working:"
    echo "  • GitHub: https://github.com/endomorphosis/ipfs_kit_py/settings/actions/runners"
    echo "  • Local:  ./scripts/list-runners.sh"
    echo ""
    
    echo "Next steps:"
    echo "  1. Push a commit or manually trigger a workflow"
    echo "  2. Watch it run on your machine!"
    echo ""
    
    echo "Management commands:"
    echo "  • Monitor:  ./scripts/monitor-runner.sh"
    echo "  • Restart:  ./scripts/restart-runner.sh"
    echo "  • Remove:   ./scripts/remove-runner.sh"
    echo ""
    
    read -p "Would you like to monitor the runner now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ./scripts/monitor-runner.sh
    fi
else
    echo -e "\n${RED}╔══════════════════════════════════════════════════════════════════╗"
    echo "║                     Setup Failed                               ║"
    echo -e "╚══════════════════════════════════════════════════════════════════╝${NC}\n"
    
    echo "Common issues:"
    echo "  • Invalid or expired GitHub token"
    echo "  • Insufficient token permissions (needs 'repo' and 'workflow')"
    echo "  • Network connectivity issues"
    echo ""
    echo "Try again or check the logs above for details."
    exit 1
fi
