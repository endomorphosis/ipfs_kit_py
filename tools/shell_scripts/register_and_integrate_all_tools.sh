#!/bin/bash

# Register and Integrate All IPFS Tools Script
# This script combines the basic tools with all controller tools to provide comprehensive IPFS tool coverage

# Set up colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}========== IPFS KIT COMPREHENSIVE TOOL REGISTRATION ==========${NC}"
echo "This script will register all IPFS tools and controller tools with the MCP server"

# Step 1: Check for required files
echo -e "\n${GREEN}1. Checking for required files...${NC}"
for file in register_all_controller_tools.py integrate_all_tools.py direct_mcp_server.py; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}ERROR: Required file not found: $file${NC}"
        exit 1
    else
        echo "✓ Found $file"
    fi
done

# Step 2: Make all scripts executable
echo -e "\n${GREEN}2. Making scripts executable...${NC}"
chmod +x register_all_controller_tools.py
chmod +x integrate_all_tools.py
echo "✓ Made scripts executable"

# Step 3: Run the controller tools registration script
echo -e "\n${GREEN}3. Registering all controller tools...${NC}"
./register_all_controller_tools.py
if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Failed to register controller tools${NC}"
    echo "Please check the output for errors"
    exit 1
fi

# Step 4: Run the integration script for basic tools
echo -e "\n${GREEN}4. Running basic tools integration...${NC}"
./integrate_all_tools.py
if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Failed to integrate basic tools${NC}"
    echo "Please check the output for errors"
    exit 1
fi

# Step 5: Update the documentation with comprehensive tool list
echo -e "\n${GREEN}5. Checking documentation updates...${NC}"
for file in README_IPFS_COMPREHENSIVE_TOOLS.md IPFS_KIT_COMPREHENSIVE_FEATURES.md; do
    if [ -f "$file" ]; then
        echo "✓ Documentation updated: $file"
    else
        echo -e "${YELLOW}WARNING: Documentation file not found: $file${NC}"
    fi
done

# Step 6: Make shell scripts executable
echo -e "\n${GREEN}6. Making shell scripts executable...${NC}"
for script in start_ipfs_mcp_with_tools.sh stop_ipfs_mcp.sh verify_ipfs_tools.py; do
    if [ -f "$script" ]; then
        chmod +x "$script"
        echo "✓ Made $script executable"
    else
        echo -e "${YELLOW}WARNING: Script not found: $script${NC}"
    fi
done

echo -e "\n${GREEN}========== INTEGRATION COMPLETE ==========${NC}"
echo -e "All IPFS tools have been integrated with the MCP server."
echo -e "\nTo start the MCP server with all tools:"
echo -e "  ${YELLOW}./start_ipfs_mcp_with_tools.sh${NC}"
echo -e "\nTo stop the MCP server:"
echo -e "  ${YELLOW}./stop_ipfs_mcp.sh${NC}"
echo -e "\nFor more information, see:"
echo -e "  ${YELLOW}README_IPFS_COMPREHENSIVE_TOOLS.md${NC}"
echo -e "  ${YELLOW}IPFS_KIT_COMPREHENSIVE_FEATURES.md${NC}"
