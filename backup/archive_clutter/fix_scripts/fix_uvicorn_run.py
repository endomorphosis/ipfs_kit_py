#!/usr/bin/env python3
"""
Fix the unmatched parenthesis in the uvicorn.run() call in direct_mcp_server_with_tools.py
"""

import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_uvicorn_run(filename):
    if not os.path.exists(filename):
        logger.error(f"File {filename} not found!")
        return False

    # Read the current content
    with open(filename, 'r') as f:
        content = f.read()

    # Find the uvicorn.run pattern and ensure it has matching parentheses
    # This pattern looks for uvicorn.run( followed by content until a line with a single )
    uvicorn_pattern = r'uvicorn\.run\(\s*app,\s*host=args\.host,\s*port=args\.port,\s*log_level="debug" if args\.debug else "info"\s*\)\s*\n# Removed unmatched parenthesis'

    fixed_content = re.sub(uvicorn_pattern,
                          'uvicorn.run(\n        app,\n        host=args.host,\n        port=args.port,\n        log_level="debug" if args.debug else "info"\n    )',
                          content)

    # Write the fixed content back to the file
    with open(filename, 'w') as f:
        f.write(fixed_content)

    logger.info(f"✅ Fixed unmatched parenthesis in uvicorn.run() call in {filename}")
    return True

if __name__ == "__main__":
    logger.info("Starting to fix unmatched parenthesis in uvicorn.run()...")

    filename = "direct_mcp_server_with_tools.py"
    if fix_uvicorn_run(filename):
        logger.info("✅ Successfully fixed the uvicorn.run() call")
        logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
        sys.exit(0)
    else:
        logger.warning("⚠️ Failed to fix the uvicorn.run() call")
        sys.exit(1)
