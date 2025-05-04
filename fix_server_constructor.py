#!/usr/bin/env python3
"""
Fix FastMCP server constructor missing comma in direct_mcp_server_with_tools.py
"""

import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_server_constructor():
    """Fix the FastMCP server constructor missing comma"""
    try:
        # Check if the file exists
        if not os.path.exists("direct_mcp_server_with_tools.py"):
            logger.error("direct_mcp_server_with_tools.py not found")
            return False
        
        # Read the file content
        with open("direct_mcp_server_with_tools.py", "r") as f:
            content = f.read()
        
        # Find the server constructor pattern
        server_constructor_pattern = r'server\s*=\s*FastMCP\(\s*\n\s*name=f"[^"]*"\s*,\s*\n\s*instructions="[^"]*"\s*\n\s*\)'
        
        if re.search(server_constructor_pattern, content):
            # Fix the server constructor by adding a comma after the instructions parameter
            fixed_content = re.sub(
                r'(server\s*=\s*FastMCP\(\s*\n\s*name=f"[^"]*"\s*,\s*\n\s*instructions="[^"]*")(\s*\n\s*\))',
                r'\1,\2',
                content
            )
            
            # Write the fixed content back to the file
            with open("direct_mcp_server_with_tools.py", "w") as f:
                f.write(fixed_content)
            
            logger.info("✅ Fixed FastMCP server constructor by adding missing comma")
            return True
        else:
            # If the regex pattern doesn't match, try a more direct approach
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'instructions=' in line and not line.strip().endswith(','):
                    # Add comma at the end of the line
                    lines[i] = line + ','
                    logger.info(f"Added missing comma at line {i+1}")
                    
                    # Write the fixed content back to the file
                    with open("direct_mcp_server_with_tools.py", "w") as f:
                        f.write('\n'.join(lines))
                    
                    return True
            
            logger.error("Could not find the server constructor to fix")
            return False
    
    except Exception as e:
        logger.error(f"Error fixing server constructor: {e}")
        return False

def main():
    """Main function"""
    logger.info("Starting to fix server constructor in direct_mcp_server_with_tools.py...")
    
    # Fix server constructor
    if not fix_server_constructor():
        logger.error("❌ Failed to fix server constructor")
        return 1
    
    logger.info("\n✅ Successfully fixed server constructor in direct_mcp_server_with_tools.py")
    logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
    return 0

if __name__ == "__main__":
    sys.exit(main())
