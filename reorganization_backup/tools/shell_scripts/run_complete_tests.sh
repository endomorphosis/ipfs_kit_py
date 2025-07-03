#!/usr/bin/env bash
#
# Clean environment and run tests

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Cleaning up any existing MCP server processes...${NC}"
ps aux | grep python3 | grep "_mcp_server.py" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true

echo -e "${BLUE}Removing any stale PID files...${NC}"
rm -f .mcp_server.pid direct_mcp_server.pid final_mcp_server.pid

echo -e "${BLUE}Running complete MCP server test suite...${NC}"
./start_final_solution.sh --verbose

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}All tests completed successfully!${NC}"
    echo -e "${GREEN}The MCP server is now ready with full IPFS and VFS support.${NC}"
else
    echo -e "${RED}Some tests failed. Please check the logs for details.${NC}"
fi

echo -e "${BLUE}See README_MCP_IPFS_VFS.md for documentation on the MCP server.${NC}"
echo -e "${BLUE}See MCP_IPFS_VFS_FIX_REPORT.md for details on the fixes applied.${NC}"

exit $EXIT_CODE
