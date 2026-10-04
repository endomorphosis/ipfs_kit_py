#!/usr/bin/env python3
"""
Fix async-io sleep call in direct_mcp_server_with_tools.py
"""

import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_async_io_sleep():
    """Fix the async-io sleep call missing closing parenthesis"""
    try:
        # Check if the file exists
        if not os.path.exists("direct_mcp_server_with_tools.py"):
            logger.error("direct_mcp_server_with_tools.py not found")
            return False

        # Read the file content
        with open("direct_mcp_server_with_tools.py", "r") as f:
            lines = f.readlines()

        # Find the line with the async-io sleep call
        for i, line in enumerate(lines):
            if 'await async_io.sleep(DEPLOYMENT_CONFIG["health_check_interval"]' in line:
                # Add closing parenthesis
                lines[i] = line.rstrip() + ")\n"
                logger.info(f"Fixed async-io sleep call at line {i+1}")
                break

        # Write the fixed content back to the file
        with open("direct_mcp_server_with_tools.py", "w") as f:
            f.writelines(lines)

        logger.info("✅ Fixed async-io sleep call")
        return True

    except Exception as e:
        logger.error(f"Error fixing async-io sleep call: {e}")
        return False

def main():
    """Main function"""
    logger.info("Starting to fix async-io sleep call in direct_mcp_server_with_tools.py...")

    # Fix async-io sleep call
    if not fix_async_io_sleep():
        logger.error("❌ Failed to fix async-io sleep call")
        return 1

    logger.info("\n✅ Successfully fixed async-io sleep call in direct_mcp_server_with_tools.py")
    logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
    return 0

if __name__ == "__main__":
    sys.exit(main())
