#!/usr/bin/env python3
"""
Fix subprocess.Popen call in direct_mcp_server_with_tools.py
"""

import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_subprocess_popen():
    """Fix the subprocess.Popen call missing closing parenthesis"""
    try:
        # Check if the file exists
        if not os.path.exists("direct_mcp_server_with_tools.py"):
            logger.error("direct_mcp_server_with_tools.py not found")
            return False
        
        # Read the file content
        with open("direct_mcp_server_with_tools.py", "r") as f:
            lines = f.readlines()
        
        # Look for the subprocess.Popen call and properly close it
        subprocess_start_index = None
        comment_line_index = None
        
        for i, line in enumerate(lines):
            if "subprocess.Popen(" in line:
                subprocess_start_index = i
            if subprocess_start_index is not None and "# Removed unmatched parenthesis" in line:
                comment_line_index = i
                # Replace the comment with a proper closing parenthesis
                lines[i] = "        )\n"
                logger.info(f"Fixed subprocess.Popen call at line {i+1}")
                break
        
        if comment_line_index is None and subprocess_start_index is not None:
            # If we found the subprocess.Popen but not the comment, look for the logger.info line
            for i in range(subprocess_start_index, len(lines)):
                if "logger.info" in lines[i] and "Started other instance" in lines[i]:
                    # Insert closing parenthesis before this line
                    lines.insert(i, "        )\n")
                    logger.info(f"Added closing parenthesis at line {i+1}")
                    break
        
        # Write the fixed content back to the file
        with open("direct_mcp_server_with_tools.py", "w") as f:
            f.writelines(lines)
        
        logger.info("✅ Fixed subprocess.Popen call")
        return True
    
    except Exception as e:
        logger.error(f"Error fixing subprocess.Popen call: {e}")
        return False

def main():
    """Main function"""
    logger.info("Starting to fix subprocess.Popen call in direct_mcp_server_with_tools.py...")
    
    # Fix subprocess.Popen call
    if not fix_subprocess_popen():
        logger.error("❌ Failed to fix subprocess.Popen call")
        return 1
    
    logger.info("\n✅ Successfully fixed subprocess.Popen call in direct_mcp_server_with_tools.py")
    logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
    return 0

if __name__ == "__main__":
    sys.exit(main())
