#!/usr/bin/env python3
"""
Fix run_pytest call in direct_mcp_server_with_tools.py
"""

import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_pytest_call():
    """Fix the run_pytest call missing closing parenthesis"""
    try:
        # Check if the file exists
        if not os.path.exists("direct_mcp_server_with_tools.py"):
            logger.error("direct_mcp_server_with_tools.py not found")
            return False

        # Read the file content
        with open("direct_mcp_server_with_tools.py", "r") as f:
            lines = f.readlines()

        # Find the line with the run_pytest call
        for i, line in enumerate(lines):
            if "run_pytest(DEPLOYMENT_CONFIG[\"test_suite\"]" in line:
                # Add closing parenthesis
                lines[i] = line.rstrip() + ")\n"
                logger.info(f"Fixed run_pytest call at line {i+1}")
                break

        # Write the fixed content back to the file
        with open("direct_mcp_server_with_tools.py", "w") as f:
            f.writelines(lines)

        logger.info("✅ Fixed run_pytest call")
        return True

    except Exception as e:
        logger.error(f"Error fixing run_pytest call: {e}")
        return False

def main():
    """Main function"""
    logger.info("Starting to fix run_pytest call in direct_mcp_server_with_tools.py...")

    # Fix run_pytest call
    if not fix_pytest_call():
        logger.error("❌ Failed to fix run_pytest call")
        return 1

    logger.info("\n✅ Successfully fixed run_pytest call in direct_mcp_server_with_tools.py")
    logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
    return 0

if __name__ == "__main__":
    sys.exit(main())
