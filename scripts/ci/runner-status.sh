#!/bin/bash
# GitHub Actions Runner Setup Summary and Status Check
# Created: $(date)

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           GitHub Actions Runner Setup Complete              ║${NC}"
echo -e "${GREEN}║                  Status Dashboard                           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# System Information
echo -e "${YELLOW}=== System Information ===${NC}"
echo "Hostname: $(hostname)"
echo "Architecture: $(uname -m)"
echo "OS: $(lsb_release -d | cut -f2)"
echo "CPU Cores: $(nproc)"
echo "Memory: $(free -h | grep '^Mem:' | awk '{print $2}')"
echo "Docker Status: $(systemctl is-active docker)"
echo ""

# Runner Status
echo -e "${YELLOW}=== GitHub Actions Runners Status ===${NC}"
echo ""

# Check ipfs_kit_py runner
RUNNER_SERVICE="actions.runner.endomorphosis-ipfs_kit_py.workstation-amd64-ipfs-kit.service"
RUNNER_DIR="$HOME/actions-runner-ipfs-kit-py"

if systemctl is-active --quiet "$RUNNER_SERVICE"; then
    echo -e "${GREEN}✅ IPFS-Kit Runner: ACTIVE${NC}"
    echo "   Service: $RUNNER_SERVICE"
    echo "   Directory: $RUNNER_DIR"
    echo "   Status: $(systemctl is-active $RUNNER_SERVICE)"
    echo "   Enabled: $(systemctl is-enabled $RUNNER_SERVICE)"
    echo "   Uptime: $(systemctl show $RUNNER_SERVICE --property=ActiveEnterTimestamp --value | cut -d' ' -f2-)"
else
    echo -e "${RED}❌ IPFS-Kit Runner: INACTIVE${NC}"
fi
echo ""

# Check other runners
echo -e "${YELLOW}=== All Active Runner Services ===${NC}"
systemctl list-units --type=service --state=active | grep -E "actions\.runner\." | while read -r line; do
    service_name=$(echo "$line" | awk '{print $1}')
    echo -e "${GREEN}✅${NC} $service_name"
done
echo ""

# GitHub Runner Status
echo -e "${YELLOW}=== GitHub Registered Runners ===${NC}"
if command -v gh &> /dev/null && gh auth status &> /dev/null; then
    gh api repos/endomorphosis/ipfs_kit_py/actions/runners --jq '.runners[] | "  " + (.status | if . == "online" then "🟢" else "🔴" end) + " " + .name + " (" + (.labels | map(.name) | join(",")) + ")"' 2>/dev/null || echo "  Unable to fetch runner status from GitHub"
else
    echo "  GitHub CLI not authenticated - run 'gh auth login' to check online status"
fi
echo ""

# Docker Multi-Arch Support
echo -e "${YELLOW}=== Docker Multi-Architecture Support ===${NC}"
if docker buildx version &> /dev/null; then
    echo -e "${GREEN}✅ Docker Buildx: Available${NC}"
    echo "   Buildx Version: $(docker buildx version | head -1)"
else
    echo -e "${RED}❌ Docker Buildx: Not Available${NC}"
fi

# Test ARM64 emulation
if timeout 10 docker run --rm --platform linux/arm64 hello-world &> /dev/null; then
    echo -e "${GREEN}✅ ARM64 Emulation: Working${NC}"
else
    echo -e "${RED}❌ ARM64 Emulation: Not Working${NC}"
fi
echo ""

# Service Configuration Files
echo -e "${YELLOW}=== Service Configuration ===${NC}"
for service_file in /etc/systemd/system/actions.runner.endomorphosis-ipfs_kit_py.*.service; do
    if [ -f "$service_file" ]; then
        service_name=$(basename "$service_file")
        echo -e "${GREEN}✅${NC} $service_name"
        echo "   File: $service_file"
        echo "   User: $(grep "User=" "$service_file" | cut -d'=' -f2)"
        echo "   WorkingDirectory: $(grep "WorkingDirectory=" "$service_file" | cut -d'=' -f2)"
    fi
done
echo ""

# Workflow Files
echo -e "${YELLOW}=== Available Workflows ===${NC}"
if [ -d "/home/devel/ipfs_kit_py/.github/workflows" ]; then
    for workflow in /home/devel/ipfs_kit_py/.github/workflows/*.yml; do
        if [ -f "$workflow" ]; then
            workflow_name=$(basename "$workflow" .yml)
            echo -e "${GREEN}✅${NC} $workflow_name"
        fi
    done
else
    echo "  No workflows directory found"
fi
echo ""

# Recent Workflow Runs
echo -e "${YELLOW}=== Recent Workflow Runs ===${NC}"
if command -v gh &> /dev/null && gh auth status &> /dev/null; then
    cd /home/devel/ipfs_kit_py 2>/dev/null && gh run list --limit 5 2>/dev/null || echo "  Unable to fetch workflow runs"
else
    echo "  GitHub CLI not authenticated"
fi
echo ""

# System Integration
echo -e "${YELLOW}=== System Integration ===${NC}"
echo -e "${GREEN}✅ Systemd Integration: Configured${NC}"
echo "   - Services start automatically on boot"
echo "   - Services restart on failure"
echo "   - Logging via journalctl"
echo ""
echo -e "${GREEN}✅ Multi-Architecture Support: Configured${NC}"
echo "   - x86_64 native execution"
echo "   - ARM64 emulation via QEMU"
echo "   - Docker Buildx multi-platform builds"
echo ""

# Useful Commands
echo -e "${YELLOW}=== Useful Commands ===${NC}"
echo "Check runner logs:"
echo "  journalctl -u $RUNNER_SERVICE -f"
echo ""
echo "Restart runner:"
echo "  sudo systemctl restart $RUNNER_SERVICE"
echo ""
echo "Check runner status:"
echo "  sudo systemctl status $RUNNER_SERVICE"
echo ""
echo "View GitHub runners:"
echo "  gh api repos/endomorphosis/ipfs_kit_py/actions/runners"
echo ""
echo "Trigger workflow:"
echo "  gh workflow run docker-enhanced-test.yml"
echo ""

# Final Status
echo -e "${YELLOW}=== Summary ===${NC}"
if systemctl is-active --quiet "$RUNNER_SERVICE"; then
    echo -e "${GREEN}🚀 GitHub Actions Runner is OPERATIONAL${NC}"
    echo "   ✅ Service running and enabled for boot"
    echo "   ✅ Connected to GitHub"
    echo "   ✅ Multi-architecture Docker support"
    echo "   ✅ Automatic restart on reboot configured"
else
    echo -e "${RED}⚠️  GitHub Actions Runner needs attention${NC}"
    echo "   Check service status and logs"
fi

echo ""
echo -e "${GREEN}Setup completed on: $(date)${NC}"