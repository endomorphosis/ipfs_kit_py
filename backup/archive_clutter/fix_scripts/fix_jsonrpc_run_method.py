#!/usr/bin/env python3
"""
Focused fix for the JSON-RPC handler in direct_mcp_server.py
This script specifically targets the method call, changing tool.use() to tool.run()
"""

import sys
import re
import logging
import shutil
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def backup_file(filepath):
    """Create a backup of the file"""
    backup_path = f"{filepath}.bak.run_method"
    shutil.copy2(filepath, backup_path)
    logger.info(f"Created backup at {backup_path}")
    return backup_path

def fix_use_tool_method():
    """Fix the use_tool method in direct_mcp_server.py"""
    filepath = Path("direct_mcp_server.py")

    # Create backup
    backup_file(filepath)

    with open(filepath, 'r') as f:
        content = f.read()

    # Find and replace the specific line that calls tool.use()
    use_tool_pattern = r'(result = await )tool\.use\((arguments)\)'

    if not re.search(use_tool_pattern, content):
        logger.error("Could not find 'tool.use(arguments)' in the file. The pattern might be different.")
        return False

    # Replace tool.use with tool.run
    modified_content = re.sub(use_tool_pattern, r'\1tool.run(\2)', content)

    # Write the modified content back
    with open(filepath, 'w') as f:
        f.write(modified_content)

    logger.info("✅ Successfully replaced tool.use() with tool.run()")
    return True

def find_get_tools_function():
    """Find and report the get_tools function to help diagnose schema issues"""
    filepath = Path("direct_mcp_server.py")

    with open(filepath, 'r') as f:
        content = f.read()

    # Look for the get_tools function or related code
    get_tools_pattern = r'(tools = \[\{.*?schema.*?for tool in.*?\])'

    match = re.search(get_tools_pattern, content, re.DOTALL)
    if match:
        logger.info(f"Found get_tools implementation: {match.group(1)[:100]}...")
        return True
    else:
        logger.warning("Could not find the get_tools implementation. May need manual inspection.")
        return False

def main():
    """Main function"""
    logger.info("Starting focused fix for JSON-RPC handler (tool.use -> tool.run)...")

    success = fix_use_tool_method()
    find_get_tools_function()

    if success:
        logger.info("\n✅ Fix successfully applied")
        logger.info("The server should now be able to use tools through JSON-RPC")
        logger.info("Restart the MCP server to apply the changes:")
        logger.info("  1. Stop the current server")
        logger.info("  2. Start the server again with './restart_mcp_server.sh' or similar")
        return 0
    else:
        logger.error("❌ Failed to apply the fix")
        logger.info("You may need to manually edit direct_mcp_server.py:")
        logger.info("  1. Find the line with 'tool.use(arguments)'")
        logger.info("  2. Change it to 'tool.run(arguments)'")
        logger.info("  3. Save the file and restart the server")
        return 1

if __name__ == "__main__":
    sys.exit(main())
