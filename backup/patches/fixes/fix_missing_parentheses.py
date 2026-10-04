#!/usr/bin/env python3
"""
Fix the missing closing parentheses in Route definitions
"""

import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_missing_parentheses():
    """Add the missing closing parentheses in Route definitions"""
    try:
        filename = "direct_mcp_server_with_tools.py"
        # Check if the file exists
        if not os.path.exists(filename):
            logger.error(f"{filename} not found")
            return False

        # Read the file content
        with open(filename, "r") as f:
            lines = f.readlines()

        # Find lines with Route definitions that are missing closing parentheses
        fixed_count = 0
        for i, line in enumerate(lines):
            if 'app.routes.append(Route(' in line and not line.strip().endswith('))'):
                # If the line ends with "[POST]" or similar but without the closing parenthesis
                if re.search(r'methods=\[".+"\]$', line.strip()):
                    lines[i] = line.rstrip() + '))\n'
                    logger.info(f"Fixed missing closing parenthesis at line {i+1}")
                    fixed_count += 1

        if fixed_count == 0:
            logger.warning("No missing parentheses found in Route definitions")
            return False

        # Write the fixed content back to the file
        with open(filename, "w") as f:
            f.writelines(lines)

        logger.info(f"Successfully fixed {fixed_count} missing parentheses")
        return True

    except Exception as e:
        logger.error(f"Error fixing missing parentheses: {e}")
        return False

def main():
    """Main function"""
    logger.info("Starting to fix missing parentheses in Route definitions...")

    # Fix the missing parentheses
    if not fix_missing_parentheses():
        logger.error("❌ Failed to fix missing parentheses or none found")
        return 1

    logger.info("\n✅ Successfully fixed missing parentheses")
    logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
    return 0

if __name__ == "__main__":
    sys.exit(main())
