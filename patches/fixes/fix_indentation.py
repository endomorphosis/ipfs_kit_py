#!/usr/bin/env python3
"""
Fix indentation issue around line 1024 in direct_mcp_server_with_tools.py
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_indentation():
    """Fix the indentation issue around line 1024"""
    try:
        # Check if the file exists
        if not os.path.exists("direct_mcp_server_with_tools.py"):
            logger.error("direct_mcp_server_with_tools.py not found")
            return False

        # Read the file content
        with open("direct_mcp_server_with_tools.py", "r") as f:
            lines = f.readlines()

        # The issue starts at line 1024
        # We need to indent the lines from 1024 to the end of the tools array
        start_line = 1023  # 0-indexed line number

        # Adding indentation to the tools definition and list
        if "# Enhanced IPFS tools registered" in lines[start_line]:
            lines[start_line] = "            # Enhanced IPFS tools registered\n"

            # Add indentation to the tools array
            if "tools = [" in lines[start_line + 1]:
                lines[start_line + 1] = "            tools = [\n"

                # Scan ahead to find all the lines that need to be indented in the tools array
                i = start_line + 2
                indentation_level = 4  # Additional spaces needed

                while i < len(lines):
                    if "]" in lines[i] and lines[i].strip() == "]":
                        # This is the end of the tools array
                        lines[i] = "            ]\n"
                        break
                    else:
                        # Add 4 more spaces to existing indentation
                        lines[i] = "    " + lines[i]
                    i += 1

                logger.info(f"Fixed indentation from lines {start_line+1} to {i+1}")

        # Write the fixed content back to the file
        with open("direct_mcp_server_with_tools.py", "w") as f:
            f.writelines(lines)

        return True

    except Exception as e:
        logger.error(f"Error fixing indentation: {e}")
        return False

def main():
    """Main function"""
    logger.info("Starting to fix indentation issue in direct_mcp_server_with_tools.py...")

    # Fix indentation
    if not fix_indentation():
        logger.error("❌ Failed to fix indentation issue")
        return 1

    logger.info("\n✅ Successfully fixed indentation issue in direct_mcp_server_with_tools.py")
    logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
    return 0

if __name__ == "__main__":
    sys.exit(main())
