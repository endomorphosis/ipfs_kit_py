#!/usr/bin/env python3
"""
Fix the missing closing parenthesis for CORS middleware
"""

import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_cors_middleware():
    filename = "direct_mcp_server_with_tools.py"

    # Make sure the file exists
    if not os.path.exists(filename):
        logger.error(f"File {filename} not found!")
        return False

    # Read the current content
    with open(filename, 'r') as f:
        lines = f.readlines()

    # Find the CORS middleware section
    cors_start = -1
    remove_comment_line = -1
    fixed = False

    for i, line in enumerate(lines):
        if "app.add_middleware(CORSMiddleware," in line:
            cors_start = i
        if "# Removed unmatched parenthesis" in line and cors_start != -1:
            # Add closing parenthesis before this comment line
            prev_line_index = i - 1
            lines[prev_line_index] = lines[prev_line_index].rstrip() + "\n)\n"
            logger.info(f"Added closing parenthesis at line {prev_line_index+1}")
            fixed = True
            break

    if not fixed:
        logger.warning("Could not find CORS middleware section to fix")
        return False

    # Write the fixed content back to the file
    with open(filename, 'w') as f:
        f.writelines(lines)

    logger.info("✅ Successfully fixed CORS middleware closing parenthesis")
    return True

if __name__ == "__main__":
    logger.info("Starting to fix CORS middleware closing parenthesis...")

    if fix_cors_middleware():
        logger.info("✅ Successfully fixed CORS middleware")
        logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
        sys.exit(0)
    else:
        logger.warning("⚠️ Failed to fix CORS middleware")
        sys.exit(1)
