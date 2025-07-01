#!/usr/bin/env python3
"""
Fix the syntax error in Route definitions - missing closing parentheses
"""

import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_routes_in_file():
    filename = "direct_mcp_server_with_tools.py"
    
    # Make sure the file exists
    if not os.path.exists(filename):
        logger.error(f"File {filename} not found!")
        return False
    
    # Read the current content
    with open(filename, 'r') as f:
        lines = f.readlines()
    
    # Pattern to find Route definitions with missing closing parenthesis
    pattern1 = r'app\.routes\.append\(Route\(.*methods=\["[A-Z]+"\]\s*$'
    pattern2 = r'app\.routes\.append\(Route\(.*endpoint=\w+\s*$'
    
    # Fix each line
    fixed_count = 0
    for i, line in enumerate(lines):
        if re.search(pattern1, line.strip()) or re.search(pattern2, line.strip()):
            # Add the missing parenthesis
            lines[i] = line.rstrip() + '))\n'
            fixed_count += 1
            logger.info(f"Fixed line {i+1}: Added missing closing parenthesis")
    
    # Write the fixed content back to the file
    if fixed_count > 0:
        with open(filename, 'w') as f:
            f.writelines(lines)
        logger.info(f"✅ Fixed {fixed_count} Route definition(s) with missing parentheses")
        return True
    else:
        logger.info("No issues found with Route definitions")
        return False

if __name__ == "__main__":
    logger.info("Starting to fix Route definitions with missing parentheses...")
    
    if fix_routes_in_file():
        logger.info("✅ Successfully fixed Route definitions")
        logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
        sys.exit(0)
    else:
        logger.warning("⚠️ No Route definitions were fixed")
        sys.exit(1)
