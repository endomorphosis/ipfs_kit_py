#!/bin/bash
# Make all scripts executable

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Making IPFS MCP scripts executable...${NC}"

# Main scripts
SCRIPTS=(
    "add_comprehensive_ipfs_tools.py"
    "register_ipfs_tools_with_mcp.py"
    "verify_ipfs_tools.py"
    "start_ipfs_mcp_server.sh"
    "stop_ipfs_mcp_server.sh"
)

# Make each script executable
for script in "${SCRIPTS[@]}"; do
    if [ -f "$script" ]; then
        echo -e "${YELLOW}Making $script executable...${NC}"
        chmod +x "$script"
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ $script is now executable${NC}"
        else
            echo -e "${RED}✗ Failed to make $script executable${NC}"
        fi
    else
        echo -e "${YELLOW}! Script $script not found${NC}"
    fi
done

echo -e "${GREEN}Done!${NC}"
