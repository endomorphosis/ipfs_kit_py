#!/usr/bin/env python3
"""
Fix the missing except block for the try statement in handle_jsonrpc
"""

import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_missing_except():
    """Add the missing except block for the try in handle_jsonrpc"""
    try:
        filename = "direct_mcp_server_with_tools.py"
        # Check if the file exists
        if not os.path.exists(filename):
            logger.error(f"{filename} not found")
            return False

        # Read the file content
        with open(filename, "r") as f:
            lines = f.readlines()

        # The comment '# Removed unmatched parenthesis' is right before PORT = args.port
        # We need to add except block before this point
        for i, line in enumerate(lines):
            if "# Removed unmatched parenthesis" in line and i < len(lines) - 1:
                # Insert the except block after this line
                except_block = "    except Exception as e:\n        logger.error(f\"JSON-RPC request handling error: {e}\")\n        return JSONResponse({\n            'jsonrpc': '2.0',\n            'error': {'code': -32603, 'message': f'Internal error: {str(e)}'},\n            'id': req_id if 'req_id' in locals() else None\n        })\n\n"
                lines.insert(i + 1, except_block)
                logger.info(f"Added missing except block at line {i+1}")
                break
        else:
            logger.error("Could not find insertion point for except block")
            return False

        # Write the fixed content back to the file
        with open(filename, "w") as f:
            f.writelines(lines)

        logger.info("Successfully added missing except block")
        return True

    except Exception as e:
        logger.error(f"Error fixing missing except block: {e}")
        return False

def main():
    """Main function"""
    logger.info("Starting to fix missing except block...")

    # Fix the missing except block
    if not fix_missing_except():
        logger.error("❌ Failed to fix missing except block")
        return 1

    logger.info("\n✅ Successfully fixed missing except block")
    logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
    return 0

if __name__ == "__main__":
    sys.exit(main())
