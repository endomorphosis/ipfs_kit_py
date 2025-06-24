#!/usr/bin/env python3
"""
Fix line 881 in direct_mcp_server_with_tools.py by directly replacing the problematic line
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_line_881():
    """Directly replace line 881 with the corrected version"""
    try:
        # Check if the file exists
        if not os.path.exists("direct_mcp_server_with_tools.py"):
            logger.error("direct_mcp_server_with_tools.py not found")
            return False

        # Read the file content
        with open("direct_mcp_server_with_tools.py", "r") as f:
            lines = f.readlines()

        # Get line 881 (index 880)
        line_to_replace = 880
        original_line = lines[line_to_replace]

        # Replace with corrected line
        lines[line_to_replace] = "        if os.path.exists(abs_destination) and not overwrite:\n"

        # Write the fixed content back to the file
        with open("direct_mcp_server_with_tools.py", "w") as f:
            f.writelines(lines)

        logger.info(f"Line 881 replaced:")
        logger.info(f"  Original: {original_line.strip()}")
        logger.info(f"  Fixed:    {lines[line_to_replace].strip()}")

        return True

    except Exception as e:
        logger.error(f"Error fixing line 881: {e}")
        return False

def main():
    """Main function"""
    logger.info("Starting to fix line 881 in direct_mcp_server_with_tools.py...")

    # Fix line 881
    if not fix_line_881():
        logger.error("❌ Failed to fix line 881")
        return 1

    logger.info("\n✅ Successfully fixed line 881 in direct_mcp_server_with_tools.py")
    logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
    return 0

if __name__ == "__main__":
    sys.exit(main())
