#!/usr/bin/env python3
"""
Fix missing and extra parentheses in list comprehensions in direct_mcp_server_with_tools.py
"""

import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_parentheses():
    """Fix the missing and extra parentheses in the list comprehensions"""
    try:
        # Check if the file exists
        if not os.path.exists("direct_mcp_server_with_tools.py"):
            logger.error("direct_mcp_server_with_tools.py not found")
            return False

        # Read the file content
        with open("direct_mcp_server_with_tools.py", "r") as f:
            lines = f.readlines()

        # Fix the missing parentheses in the first list comprehension
        for i, line in enumerate(lines):
            if "result[\"file_count\"] = len([i for i in contents if os.path.isfile(os.path.join(abs_path, i))]" in line:
                lines[i] = line.rstrip() + ")\n"
                logger.info(f"Fixed missing parenthesis in file_count line {i+1}")

            elif "result[\"dir_count\"] = len([i for i in contents if os.path.isdir(os.path.join(abs_path, i))]" in line:
                lines[i] = line.rstrip() + ")\n"
                logger.info(f"Fixed missing parenthesis in dir_count line {i+1}")

            elif "if len(contents) <= 100):" in line:
                lines[i] = line.replace("if len(contents) <= 100):", "if len(contents) <= 100:")
                logger.info(f"Removed extra parenthesis in if statement at line {i+1}")

        # Write the fixed content back to the file
        with open("direct_mcp_server_with_tools.py", "w") as f:
            f.writelines(lines)

        logger.info("✅ Fixed parentheses issues")
        return True

    except Exception as e:
        logger.error(f"Error fixing parentheses: {e}")
        return False

def main():
    """Main function"""
    logger.info("Starting to fix parentheses issues in direct_mcp_server_with_tools.py...")

    # Fix parentheses
    if not fix_parentheses():
        logger.error("❌ Failed to fix parentheses issues")
        return 1

    logger.info("\n✅ Successfully fixed parentheses issues in direct_mcp_server_with_tools.py")
    logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
    return 0

if __name__ == "__main__":
    sys.exit(main())
