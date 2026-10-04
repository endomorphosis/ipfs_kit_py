#!/bin/bash
# Progressive Fix Script for IPFS MCP Server
# This script will help diagnose and fix issues with the MCP server step by step

set -e  # Exit on error

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BLUE}[*] Starting progressive fix for IPFS MCP Server${NC}"

# Step 1: Ensure consistent port usage
echo -e "${BLUE}[*] Step 1: Verifying consistent port usage${NC}"
PORT=9998
grep -q "PORT = $PORT" final_mcp_server.py || {
    echo -e "${RED}[-] Port mismatch detected in final_mcp_server.py${NC}"
    sed -i "s/PORT = [0-9]\{4\}/PORT = $PORT/g" final_mcp_server.py
    echo -e "${GREEN}[+] Fixed port number to $PORT in final_mcp_server.py${NC}"
}

# Step 2: Fix broken imports and global function definitions
echo -e "${BLUE}[*] Step 2: Adding global function definitions in multi_backend_fs_integration.py${NC}"
if ! grep -q "mbfs_get_backend = None  # Will be set by register_tools" multi_backend_fs_integration.py; then
    # Add the global definitions
    sed -i '1,/import/!{/^import/{x;s/^/# Export key functions at module level for direct import\n# This ensures tools like mbfs_get_backend are available when imported directly\nmbfs_get_backend = None  # Will be set by register_tools\nmbfs_list_backends = None\nmbfs_store = None\nmbfs_retrieve = None\nmbfs_delete = None\nmbfs_register_backend = None\n\n/;x}}' multi_backend_fs_integration.py
    echo -e "${GREEN}[+] Added global function definitions in multi_backend_fs_integration.py${NC}"

    # Add global keyword to register_tools function
    sed -i 's/def register_tools(server) -> bool:/def register_tools(server) -> bool:\n    global mbfs_get_backend, mbfs_list_backends, mbfs_store, mbfs_retrieve, mbfs_delete, mbfs_register_backend/g' multi_backend_fs_integration.py
    echo -e "${GREEN}[+] Added global keywords to register_tools function${NC}"
fi

# Step 3: Fix the generic_handler reference in unified_ipfs_tools.py
echo -e "${BLUE}[*] Step 3: Fixing generic_handler reference in unified_ipfs_tools.py${NC}"
if grep -q "generic_handler" unified_ipfs_tools.py; then
    sed -i '/mcp_server.tool(name=tool_name, description=description)(generic_handler)/d' unified_ipfs_tools.py
    echo -e "${GREEN}[+] Removed redundant generic_handler reference in unified_ipfs_tools.py${NC}"
fi

# Step 4: Test server startup
echo -e "${BLUE}[*] Step 4: Testing server startup${NC}"
echo -e "${YELLOW}[!] Starting server in the background for 5 seconds...${NC}"
python3 final_mcp_server.py --debug > progressive_fix.log 2>&1 &
SERVER_PID=$!
sleep 5
if ps -p $SERVER_PID > /dev/null; then
    echo -e "${GREEN}[+] Server started successfully (PID: $SERVER_PID)${NC}"
    echo -e "${YELLOW}[!] Stopping server...${NC}"
    kill $SERVER_PID
    wait $SERVER_PID 2>/dev/null || true
    echo -e "${GREEN}[+] Server stopped${NC}"
else
    echo -e "${RED}[-] Server failed to start. Check progressive_fix.log for details${NC}"
    cat progressive_fix.log
    exit 1
fi

# Step 5: Run a basic health check
echo -e "${BLUE}[*] Step 5: Running final solution script with --start-only${NC}"
bash run_final_solution.sh --start-only

# Done
echo -e "${GREEN}[+] Progressive fix completed${NC}"
echo -e "${BLUE}[*] To run the full test, use: bash run_final_solution.sh${NC}"
