#!/usr/bin/env python3
"""
Fix asyncio.sleep call in direct_mcp_server_with_tools.py
"""

import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_asyncio_sleep():
    """Fix the asyncio.sleep call missing closing parenthesis"""
    try:
        # Check if the file exists
        if not os.path.exists("direct_mcp_server_with_tools.py"):
            logger.error("direct_mcp_server_with_tools.py not found")
            return False
        
        # Read the file content
        with open("direct_mcp_server_with_tools.py", "r") as f:
            lines = f.readlines()
        
        # Find the line with the asyncio.sleep call
        for i, line in enumerate(lines):
            if 'await asyncio.sleep(DEPLOYMENT_CONFIG["health_check_interval"]' in line:
                # Add closing parenthesis
                lines[i] = line.rstrip() + ")\n"
                logger.info(f"Fixed asyncio.sleep call at line {i+1}")
                break
        
        # Write the fixed content back to the file
        with open("direct_mcp_server_with_tools.py", "w") as f:
            f.writelines(lines)
        
        logger.info("✅ Fixed asyncio.sleep call")
        return True
    
    except Exception as e:
        logger.error(f"Error fixing asyncio.sleep call: {e}")
        return False

def main():
    """Main function"""
    logger.info("Starting to fix asyncio.sleep call in direct_mcp_server_with_tools.py...")
    
    # Fix asyncio.sleep call
    if not fix_asyncio_sleep():
        logger.error("❌ Failed to fix asyncio.sleep call")
        return 1
    
    logger.info("\n✅ Successfully fixed asyncio.sleep call in direct_mcp_server_with_tools.py")
    logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
    return 0

if __name__ == "__main__":
    sys.exit(main())
