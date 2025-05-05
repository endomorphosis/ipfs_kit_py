#!/usr/bin/env python3
"""
Fix for JSON-RPC dispatcher issue in final_mcp_server.py
"""

import sys
import os
import re
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('jsonrpc-fix')

def fix_jsonrpc_dispatcher():
    """Fix the JSON-RPC dispatcher in final_mcp_server.py."""
    file_path = 'final_mcp_server.py'

    # Check if file exists
    if not os.path.exists(file_path):
        logger.error(f"❌ File {file_path} not found")
        return False

    # Read file content
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        # Make backup of original file
        backup_path = f"{file_path}.bak.jsonrpc_fix"
        with open(backup_path, 'w') as f:
            f.write(content)
        logger.info(f"✅ Created backup at {backup_path}")

        # Fix the handle method
        original_line = "response = await jsonrpc_dispatcher.handle(request_json)"
        fixed_line = "response = await jsonrpc_dispatcher.call(request_json)"

        if original_line in content:
            content = content.replace(original_line, fixed_line)
            logger.info("✅ Fixed handle method reference")
        else:
            # Try a more flexible search with regex
            pattern = r"response\s*=\s*await\s*jsonrpc_dispatcher\.handle\(request_json\)"
            if re.search(pattern, content):
                content = re.sub(pattern, "response = await jsonrpc_dispatcher.call(request_json)", content)
                logger.info("✅ Fixed handle method reference (using regex)")
            else:
                logger.warning("⚠️ Could not find handle method reference")

        # Write updated content back to file
        with open(file_path, 'w') as f:
            f.write(content)

        logger.info(f"✅ Updated {file_path} with JSON-RPC dispatcher fix")
        return True

    except Exception as e:
        logger.error(f"❌ Error fixing JSON-RPC dispatcher: {e}")
        return False

def main():
    """Main function."""
    logger.info("Starting JSON-RPC dispatcher fix")

    if fix_jsonrpc_dispatcher():
        logger.info("✅ Successfully fixed JSON-RPC dispatcher")
        logger.info("Restart the MCP server to apply the fix")
        return 0
    else:
        logger.error("❌ Failed to fix JSON-RPC dispatcher")
        return 1

if __name__ == "__main__":
    sys.exit(main())
