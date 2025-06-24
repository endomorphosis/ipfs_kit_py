#!/usr/bin/env python3
"""
Fix unmatched parenthesis in direct_mcp_server_with_tools.py
"""

import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_unmatched_parenthesis():
    """Fix the unmatched parenthesis in the if statement"""
    try:
        # Check if the file exists
        if not os.path.exists("direct_mcp_server_with_tools.py"):
            logger.error("direct_mcp_server_with_tools.py not found")
            return False

        # Read the file content
        with open("direct_mcp_server_with_tools.py", "r") as f:
            lines = f.readlines()

        # Find the line with the unmatched parenthesis
        for i, line in enumerate(lines):
            if 'os.path.exists(abs_destination) and overwrite)' in line:
                # Remove the extra closing parenthesis
                lines[i] = line.replace('and overwrite)', 'and overwrite')
                logger.info(f"Fixed unmatched parenthesis at line {i+1}")
                break

        # Write the fixed content back to the file
        with open("direct_mcp_server_with_tools.py", "w") as f:
            f.writelines(lines)

        logger.info("✅ Fixed unmatched parenthesis")
        return True

    except Exception as e:
        logger.error(f"Error fixing unmatched parenthesis: {e}")
        return False

def main():
    """Main function"""
    logger.info("Starting to fix unmatched parenthesis in direct_mcp_server_with_tools.py...")

    # Fix unmatched parenthesis
    if not fix_unmatched_parenthesis():
        logger.error("❌ Failed to fix unmatched parenthesis")
        return 1

    logger.info("\n✅ Successfully fixed unmatched parenthesis in direct_mcp_server_with_tools.py")
    logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
    return 0

if __name__ == "__main__":
    sys.exit(main())
