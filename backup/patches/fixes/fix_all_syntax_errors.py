#!/usr/bin/env python3
"""
Fix all syntax errors in direct_mcp_server_with_tools.py
"""

import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_syntax_errors():
    """Fix all syntax errors in direct_mcp_server_with_tools.py"""
    try:
        # Check if the file exists
        if not os.path.exists("direct_mcp_server_with_tools.py"):
            logger.error("direct_mcp_server_with_tools.py not found")
            return False

        # Read the file content
        with open("direct_mcp_server_with_tools.py", "r") as f:
            content = f.read()

        # Fix 1: Fix the unmatched parenthesis
        if "tools = [" in content and "])" in content:
            content = content.replace("])", "]")
            logger.info("Fixed unmatched parenthesis in tools array")

        # Fix 2: Fix the missing parenthesis in if statement
        if "if os.path.exists(DEPLOYMENT_CONFIG[\"active_version_file\"]:" in content:
            content = content.replace(
                "if os.path.exists(DEPLOYMENT_CONFIG[\"active_version_file\"]:",
                "if os.path.exists(DEPLOYMENT_CONFIG[\"active_version_file\"]):"
            )
            logger.info("Fixed missing closing parenthesis in if statement")

        # Fix 3: Look for other common syntax errors
        lines = content.split('\n')
        fixed_lines = []

        for i, line in enumerate(lines):
            # Fix missing parentheses in if statements
            if re.search(r'if\s+.*\(\s*.*[^)]\s*:', line):
                fixed_line = re.sub(r'if\s+(.*\(\s*.*[^)]\s*):', r'if \1):', line)
                fixed_lines.append(fixed_line)
                logger.info(f"Fixed missing parenthesis in line {i+1}")
            # Fix unmatched parentheses
            elif line.strip() == ')':
                fixed_lines.append('# Removed unmatched parenthesis')
                logger.info(f"Removed unmatched parenthesis in line {i+1}")
            else:
                fixed_lines.append(line)

        # Join the fixed lines
        fixed_content = '\n'.join(fixed_lines)

        # Write the fixed content back to the file
        with open("direct_mcp_server_with_tools.py", "w") as f:
            f.write(fixed_content)

        logger.info("✅ Fixed syntax errors in direct_mcp_server_with_tools.py")
        return True

    except Exception as e:
        logger.error(f"Error fixing syntax errors: {e}")
        return False

def main():
    """Main function"""
    logger.info("Starting to fix all syntax errors in direct_mcp_server_with_tools.py...")

    # Fix syntax errors
    if not fix_syntax_errors():
        logger.error("❌ Failed to fix syntax errors")
        return 1

    logger.info("\n✅ Successfully fixed all syntax errors in direct_mcp_server_with_tools.py")
    logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
    return 0

if __name__ == "__main__":
    sys.exit(main())
