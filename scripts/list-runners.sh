#!/bin/bash

# List GitHub Actions Runners
# Shows all runners registered for the repository

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

GITHUB_REPO="${GITHUB_REPO:-endomorphosis/ipfs_kit_py}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

echo -e "${GREEN}===================================================================="
echo "GitHub Actions Runners for: $GITHUB_REPO"
echo -e "====================================================================${NC}\n"

# Check for local runners (multiple repositories supported)
RUNNERS_BASE="$HOME/actions-runners"
LEGACY_RUNNER="$HOME/actions-runner"

echo -e "${BLUE}Local Runners:${NC}\n"

FOUND_RUNNERS=0

# Check new multi-repo structure
if [ -d "$RUNNERS_BASE" ]; then
    for runner_dir in "$RUNNERS_BASE"/*; do
        if [ -d "$runner_dir" ] && [ -f "$runner_dir/.runner" ]; then
            FOUND_RUNNERS=$((FOUND_RUNNERS + 1))
            RUNNER_NAME=$(grep -Po '"agentName":\s*"\K[^"]*' "$runner_dir/.runner" 2>/dev/null || echo "unknown")
            REPO_NAME=$(basename "$runner_dir" | sed 's/-/\//1')
            
            echo -e "${GREEN}Runner #$FOUND_RUNNERS${NC}"
            echo "  Repository: $REPO_NAME"
            echo "  Name: $RUNNER_NAME"
            echo "  Directory: $runner_dir"
            
            # Check service status
            if [ -f "$runner_dir/svc.sh" ]; then
                echo -n "  Status: "
                if sudo "$runner_dir/svc.sh" status > /dev/null 2>&1; then
                    echo -e "${GREEN}Running ✓${NC}"
                else
                    echo -e "${RED}Stopped ✗${NC}"
                fi
                
                # Get systemd service name
                SERVICE_NAME=$(systemctl list-units --type=service --all | grep -o "actions.runner[^[:space:]]*" | grep "$(basename "$runner_dir")" | head -1 || echo "")
                if [ -n "$SERVICE_NAME" ]; then
                    echo "  Service: $SERVICE_NAME"
                fi
            fi
            echo ""
        fi
    done
fi

# Check legacy single runner location
if [ -d "$LEGACY_RUNNER" ] && [ -f "$LEGACY_RUNNER/.runner" ]; then
    FOUND_RUNNERS=$((FOUND_RUNNERS + 1))
    RUNNER_NAME=$(grep -Po '"agentName":\s*"\K[^"]*' "$LEGACY_RUNNER/.runner" 2>/dev/null || echo "unknown")
    
    echo -e "${YELLOW}Legacy Runner${NC}"
    echo "  Name: $RUNNER_NAME"
    echo "  Directory: $LEGACY_RUNNER"
    
    # Check service status
    if [ -f "$LEGACY_RUNNER/svc.sh" ]; then
        echo -n "  Status: "
        if sudo "$LEGACY_RUNNER/svc.sh" status > /dev/null 2>&1; then
            echo -e "${GREEN}Running ✓${NC}"
        else
            echo -e "${RED}Stopped ✗${NC}"
        fi
    fi
    echo ""
fi

if [ $FOUND_RUNNERS -eq 0 ]; then
    echo -e "${YELLOW}No local runners found${NC}\n"
fi

# Show all systemd services
echo -e "${BLUE}Systemd Services:${NC}\n"
SERVICES=$(systemctl list-units --type=service --all | grep "actions.runner" | awk '{print $1}' || echo "")
if [ -n "$SERVICES" ]; then
    echo "$SERVICES" | while read -r service; do
        STATUS=$(systemctl is-active "$service" 2>/dev/null || echo "inactive")
        if [ "$STATUS" = "active" ]; then
            echo -e "  ${GREEN}●${NC} $service - ${GREEN}$STATUS${NC}"
        else
            echo -e "  ${RED}●${NC} $service - ${RED}$STATUS${NC}"
        fi
    done
    echo ""
else
    echo -e "  ${YELLOW}No runner services found${NC}\n"
fi

# Fetch from GitHub API if token provided
if [ -n "$GITHUB_TOKEN" ]; then
    echo -e "${BLUE}Fetching runners from GitHub API...${NC}\n"
    
    RESPONSE=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3+json" \
        "https://api.github.com/repos/$GITHUB_REPO/actions/runners")
    
    TOTAL=$(echo "$RESPONSE" | jq -r '.total_count // 0')
    
    if [ "$TOTAL" -eq 0 ]; then
        echo -e "${YELLOW}No runners registered in GitHub.${NC}"
    else
        echo -e "${GREEN}Total runners registered: $TOTAL${NC}\n"
        
        echo "$RESPONSE" | jq -r '.runners[] | 
            "Name: \(.name)\n" +
            "  ID: \(.id)\n" +
            "  OS: \(.os)\n" +
            "  Status: \(.status)\n" +
            "  Busy: \(.busy)\n" +
            "  Labels: \([.labels[].name] | join(", "))\n"'
    fi
else
    echo -e "${YELLOW}GitHub token not provided. Set GITHUB_TOKEN to see runners from API.${NC}"
    echo -e "Or view at: ${BLUE}https://github.com/$GITHUB_REPO/settings/actions/runners${NC}"
fi

echo -e "\n${GREEN}====================================================================${NC}"
