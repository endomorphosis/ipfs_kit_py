#!/bin/bash

# Monitor GitHub Actions Runner
# Real-time monitoring of runner status, logs, and system resources

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

RUNNER_DIR="${RUNNER_DIR:-$HOME/actions-runner}"

clear
echo -e "${GREEN}===================================================================="
echo "GitHub Actions Runner Monitor"
echo -e "====================================================================${NC}\n"

# Check if runner exists
if [ ! -d "$RUNNER_DIR" ]; then
    echo -e "${RED}Runner not found at: $RUNNER_DIR${NC}"
    exit 1
fi

# Function to display runner info
show_runner_info() {
    echo -e "${BLUE}Runner Information:${NC}"
    if [ -f "$RUNNER_DIR/.runner" ]; then
        RUNNER_NAME=$(grep -Po '"agentName":\s*"\K[^"]*' "$RUNNER_DIR/.runner" 2>/dev/null || echo "unknown")
        RUNNER_ID=$(grep -Po '"agentId":\s*\K[^,]*' "$RUNNER_DIR/.runner" 2>/dev/null || echo "unknown")
        echo "  Name: $RUNNER_NAME"
        echo "  ID: $RUNNER_ID"
    fi
    echo ""
}

# Function to display service status
show_service_status() {
    echo -e "${BLUE}Service Status:${NC}"
    if [ -f "$RUNNER_DIR/svc.sh" ]; then
        if sudo "$RUNNER_DIR/svc.sh" status > /dev/null 2>&1; then
            echo -e "  Status: ${GREEN}Running ✓${NC}"
        else
            echo -e "  Status: ${RED}Stopped ✗${NC}"
        fi
    else
        echo -e "  Status: ${YELLOW}Not configured as service${NC}"
    fi
    echo ""
}

# Function to display system resources
show_system_resources() {
    echo -e "${BLUE}System Resources:${NC}"
    
    # CPU usage
    CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
    echo "  CPU Usage: ${CPU_USAGE}%"
    
    # Memory usage
    MEM_INFO=$(free -h | awk '/^Mem:/ {print $3 "/" $2}')
    echo "  Memory: $MEM_INFO"
    
    # Disk usage
    DISK_USAGE=$(df -h "$RUNNER_DIR" | awk 'NR==2 {print $3 "/" $2 " (" $5 " used)"}')
    echo "  Disk: $DISK_USAGE"
    
    echo ""
}

# Function to display recent logs
show_recent_logs() {
    echo -e "${BLUE}Recent Logs (last 10 lines):${NC}"
    if systemctl --user list-units --all | grep -q "actions.runner" 2>/dev/null; then
        journalctl --user -u actions.runner.* -n 10 --no-pager 2>/dev/null || echo "  No logs available"
    elif systemctl list-units --all | grep -q "actions.runner" 2>/dev/null; then
        sudo journalctl -u actions.runner.* -n 10 --no-pager 2>/dev/null || echo "  No logs available"
    else
        echo "  Service logs not available. Check $RUNNER_DIR/_diag/ for log files."
    fi
    echo ""
}

# Function to display workflow runs
show_workflow_status() {
    echo -e "${BLUE}Workflow Run Status:${NC}"
    if [ -d "$RUNNER_DIR/_work" ]; then
        WORK_DIRS=$(find "$RUNNER_DIR/_work" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
        if [ "$WORK_DIRS" -gt 0 ]; then
            echo -e "  Active/Recent jobs: $WORK_DIRS"
            find "$RUNNER_DIR/_work" -mindepth 1 -maxdepth 1 -type d -printf "    - %f\n" 2>/dev/null | head -5
        else
            echo "  No active jobs"
        fi
    else
        echo "  No work directory found"
    fi
    echo ""
}

# Display mode selection
echo "Select monitoring mode:"
echo "  1) One-time status check"
echo "  2) Live log monitoring"
echo "  3) Continuous monitoring (refresh every 5s)"
echo ""
read -p "Enter choice (1-3): " CHOICE

case $CHOICE in
    1)
        # One-time check
        show_runner_info
        show_service_status
        show_system_resources
        show_workflow_status
        show_recent_logs
        ;;
    2)
        # Live logs
        echo -e "\n${GREEN}Starting live log monitoring (Ctrl+C to exit)...${NC}\n"
        if systemctl --user list-units --all | grep -q "actions.runner" 2>/dev/null; then
            journalctl --user -u actions.runner.* -f
        elif systemctl list-units --all | grep -q "actions.runner" 2>/dev/null; then
            sudo journalctl -u actions.runner.* -f
        else
            echo -e "${YELLOW}Service logs not available. Tailing log file...${NC}"
            if [ -f "$RUNNER_DIR/_diag/Runner_*.log" ]; then
                tail -f "$RUNNER_DIR/_diag/Runner_"*.log
            else
                echo -e "${RED}No log files found${NC}"
            fi
        fi
        ;;
    3)
        # Continuous monitoring
        echo -e "\n${GREEN}Starting continuous monitoring (Ctrl+C to exit)...${NC}\n"
        while true; do
            clear
            echo -e "${GREEN}===================================================================="
            echo "GitHub Actions Runner Monitor - $(date)"
            echo -e "====================================================================${NC}\n"
            
            show_runner_info
            show_service_status
            show_system_resources
            show_workflow_status
            show_recent_logs
            
            echo -e "${YELLOW}Refreshing in 5 seconds... (Ctrl+C to exit)${NC}"
            sleep 5
        done
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac
