#!/usr/bin/env python3
"""
Fix the server registration ordering in direct_mcp_server.py
"""

import os
import re
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MCP_SERVER_PATH = "direct_mcp_server.py"

def fix_server_registration():
    """Fix the ordering of server registration in direct_mcp_server.py"""
    if not os.path.exists(MCP_SERVER_PATH):
        logger.error(f"❌ File not found: {MCP_SERVER_PATH}")
        return False

    try:
        # Read the file
        with open(MCP_SERVER_PATH, 'r') as f:
            content = f.read()

        # Remove the incorrectly placed registration call
        content = re.sub(r"# Register IPFS tools\s+register_ipfs_tools\(server\)\s+", "", content)

        # Find the FastMCP server creation
        server_pattern = r"server\s*=\s*FastMCP\([^)]*\)"
        server_match = re.search(server_pattern, content)

        if not server_match:
            logger.error("❌ Could not find server creation in the file")
            return False

        # Insert the registration call AFTER the server creation
        pos = server_match.end()

        # Add a newline and the registration call
        register_call = "\n\n# Register IPFS tools\nregister_ipfs_tools(server)"
        content = content[:pos] + register_call + content[pos:]

        # Write the updated content back to the file
        with open(MCP_SERVER_PATH, 'w') as f:
            f.write(content)

        logger.info(f"✅ Successfully fixed server registration ordering in {MCP_SERVER_PATH}")
        return True
    except Exception as e:
        logger.error(f"❌ Error fixing server registration: {e}")
        return False

if __name__ == "__main__":
    fix_server_registration()
