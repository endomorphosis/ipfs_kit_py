#!/usr/bin/env python3
"""
Fix missing closing parenthesis in logger.info statement in direct_mcp_server_with_tools.py
"""

import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_logger_info():
    """Fix the missing closing parenthesis in logger.info statement"""
    try:
        # Check if the file exists
        if not os.path.exists("direct_mcp_server_with_tools.py"):
            logger.error("direct_mcp_server_with_tools.py not found")
            return False

        # Read the file content
        with open("direct_mcp_server_with_tools.py", "r") as f:
            lines = f.readlines()

        # Find the line with the logger.info statement
        for i, line in enumerate(lines):
            if "logger.info(\"Successfully listed files in %s with %s files\", directory, result['statistics']['total_files']" in line:
                # Add closing parenthesis
                lines[i] = line.rstrip() + ")\n"
                logger.info(f"Fixed logger.info statement at line {i+1}")
                break

        # Write the fixed content back to the file
        with open("direct_mcp_server_with_tools.py", "w") as f:
            f.writelines(lines)

        logger.info("✅ Fixed logger.info statement")
        return True

    except Exception as e:
        logger.error(f"Error fixing logger.info statement: {e}")
        return False

def main():
    """Main function"""
    logger.info("Starting to fix logger.info statement in direct_mcp_server_with_tools.py...")

    # Fix logger.info statement
    if not fix_logger_info():
        logger.error("❌ Failed to fix logger.info statement")
        return 1

    logger.info("\n✅ Successfully fixed logger.info statement in direct_mcp_server_with_tools.py")
    logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
    return 0

if __name__ == "__main__":
    sys.exit(main())
