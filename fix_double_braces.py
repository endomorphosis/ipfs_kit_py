#!/usr/bin/env python3
"""
Fix the double braces syntax error in ipfs_tools_registry.py
"""

import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_double_braces():
    filename = "ipfs_tools_registry.py"

    # Make sure the file exists
    if not os.path.exists(filename):
        logger.error(f"File {filename} not found!")
        return False

    # Read the current content
    with open(filename, 'r') as f:
        content = f.read()

    # Count the occurrences before replacement
    double_open_count = content.count('{{')
    double_close_count = content.count('}}')

    # Replace double braces with single braces
    fixed_content = content.replace('{{', '{').replace('}}', '}')

    # Write the fixed content back to the file
    with open(filename, 'w') as f:
        f.write(fixed_content)

    logger.info(f"✅ Replaced {double_open_count} occurrences of '{{{{' with '{{' and {double_close_count} occurrences of '}}}}' with '}}'")
    return True

if __name__ == "__main__":
    logger.info("Starting to fix double braces syntax error...")

    if fix_double_braces():
        logger.info("✅ Successfully fixed double braces syntax error")
        logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
        sys.exit(0)
    else:
        logger.warning("⚠️ Failed to fix double braces syntax error")
        sys.exit(1)
