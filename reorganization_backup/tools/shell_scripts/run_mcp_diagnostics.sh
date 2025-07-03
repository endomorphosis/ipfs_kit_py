#!/bin/bash
# Run the complete MCP diagnostic suite

set -e

# Colors for better readability
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}${BOLD}═════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}${BOLD}                MCP COMPREHENSIVE DIAGNOSTIC SUITE                    ${NC}"
echo -e "${BLUE}${BOLD}═════════════════════════════════════════════════════════════════════${NC}"
echo

# Step 1: Run the basic MCP tests
echo -e "${BOLD}[Step 1] Running basic MCP tests...${NC}"
./start_final_solution.sh

# Step 2: Check IPFS kit coverage
echo
echo -e "${BOLD}[Step 2] Running IPFS kit coverage analysis...${NC}"
python3 minimal_coverage_analyzer.py

# Step 3: Compare server implementations if available
echo
echo -e "${BOLD}[Step 3] Running cross-version comparison...${NC}"
# Check if direct_mcp_server.py and enhanced_mcp_server.py exist
if [ -f "direct_mcp_server.py" ] && [ -f "enhanced_mcp_server.py" ]; then
    # Run the comparison
    ./compare_mcp_servers.sh
else
    echo -e "${YELLOW}Warning: Some server implementations are missing. Skipping cross-version comparison.${NC}"
    echo "Looking for direct_mcp_server.py and enhanced_mcp_server.py"
fi

echo
echo -e "${GREEN}${BOLD}═════════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}                DIAGNOSTIC SUITE COMPLETED                           ${NC}"
echo -e "${GREEN}${BOLD}═════════════════════════════════════════════════════════════════════${NC}"
echo
echo -e "Results can be found in:"
echo -e "  - diagnostic_results/ (Basic test results)"
echo -e "  - cross_version_results/ (Cross-version comparison results)"
echo -e "  - minimal_ipfs_coverage_report.json (IPFS coverage report)"
echo
