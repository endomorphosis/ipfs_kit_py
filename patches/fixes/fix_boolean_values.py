#!/usr/bin/env python3
"""
Fix the JavaScript-style boolean values (true/false) to Python-style (True/False)
"""

import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_boolean_values(filename):
    if not os.path.exists(filename):
        logger.error(f"File {filename} not found!")
        return False
    
    # Read the current content
    with open(filename, 'r') as f:
        content = f.read()
    
    # Count occurrences before replacement
    false_count = content.count('"default": false') + content.count('"required": false')
    true_count = content.count('"default": true') + content.count('"required": true')
    
    # Replace JavaScript-style boolean values with Python-style
    fixed_content = content.replace('"default": false', '"default": False')
    fixed_content = fixed_content.replace('"required": false', '"required": False')
    fixed_content = fixed_content.replace('"default": true', '"default": True')
    fixed_content = fixed_content.replace('"required": true', '"required": True')
    
    # Also check for other uses of true/false without quotes
    other_false = len(re.findall(r'(?<!")\bfalse\b(?!")', content))
    other_true = len(re.findall(r'(?<!")\btrue\b(?!")', content))
    
    if other_false > 0 or other_true > 0:
        fixed_content = re.sub(r'(?<!")\bfalse\b(?!")', 'False', fixed_content)
        fixed_content = re.sub(r'(?<!")\btrue\b(?!")', 'True', fixed_content)
        logger.info(f"Found {other_false} other instances of 'false' and {other_true} other instances of 'true'")
    
    # Write the fixed content back to the file
    with open(filename, 'w') as f:
        f.write(fixed_content)
    
    logger.info(f"✅ Fixed {false_count + true_count + other_false + other_true} JavaScript-style boolean values in {filename}")
    return True

if __name__ == "__main__":
    logger.info("Starting to fix JavaScript-style boolean values...")
    
    files_to_fix = ["ipfs_tools_registry.py"]
    success = True
    
    for filename in files_to_fix:
        if not fix_boolean_values(filename):
            success = False
    
    if success:
        logger.info("✅ Successfully fixed all JavaScript-style boolean values")
        logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
        sys.exit(0)
    else:
        logger.warning("⚠️ Failed to fix some JavaScript-style boolean values")
        sys.exit(1)
