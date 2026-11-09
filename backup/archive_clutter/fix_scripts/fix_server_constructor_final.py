#!/usr/bin/env python3
"""
Fix FastMCP server constructor in direct_mcp_server_with_tools.py
"""

import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_server_constructor():
    """Fix the FastMCP server constructor"""
    try:
        # Check if the file exists
        if not os.path.exists("direct_mcp_server_with_tools.py"):
            logger.error("direct_mcp_server_with_tools.py not found")
            return False

        # Read the file content
        with open("direct_mcp_server_with_tools.py", "r") as f:
            lines = f.readlines()

        # Look for the server constructor and properly close it
        server_start_index = None
        found_comment = False

        for i, line in enumerate(lines):
            if "server = FastMCP(" in line:
                server_start_index = i
            if server_start_index is not None and "# Removed unmatched parenthesis" in line:
                found_comment = True
                # Replace the comment with a proper closing parenthesis
                lines[i] = ")\n\n"
                logger.info(f"Fixed server constructor at line {i+1}")
                break

        if not found_comment and server_start_index is not None:
            # If we found the server constructor but not the comment, look for where it should be closed
            for i in range(server_start_index, len(lines)):
                if "logger.info" in lines[i] and "Registering all IPFS" in lines[i]:
                    # Insert closing parenthesis before this line
                    lines.insert(i, ")\n\n")
                    logger.info(f"Added closing parenthesis at line {i+1}")
                    break

        # Write the fixed content back to the file
        with open("direct_mcp_server_with_tools.py", "w") as f:
            f.writelines(lines)

        logger.info("✅ Fixed FastMCP server constructor")
        return True

    except Exception as e:
        logger.error(f"Error fixing server constructor: {e}")
        return False

def main():
    """Main function"""
    logger.info("Starting to fix server constructor in direct_mcp_server_with_tools.py...")

    # Fix server constructor
    if not fix_server_constructor():
        logger.error("❌ Failed to fix server constructor")
        return 1

    logger.info("\n✅ Successfully fixed server constructor in direct_mcp_server_with_tools.py")
    logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
    return 0

if __name__ == "__main__":
    sys.exit(main())
