#!/usr/bin/env python3
"""
Fix the IPFS tools registry file by replacing JSON boolean values with Python boolean values
"""

import os
import re
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

REGISTRY_PATH = "ipfs_tools_registry.py"

def fix_tools_registry():
    """Fix the IPFS tools registry by replacing JSON booleans with Python booleans"""
    if not os.path.exists(REGISTRY_PATH):
        logger.error(f"❌ File not found: {REGISTRY_PATH}")
        return False

    try:
        # Read the file
        with open(REGISTRY_PATH, 'r') as f:
            content = f.read()

        # Replace JSON booleans with Python booleans
        # This handles 'false' -> 'False' and 'true' -> 'True'
        content_fixed = re.sub(r':\s*false\b', ': False', content)
        content_fixed = re.sub(r':\s*true\b', ': True', content_fixed)

        # Write the fixed content back to the file
        with open(REGISTRY_PATH, 'w') as f:
            f.write(content_fixed)

        logger.info(f"✅ Successfully fixed {REGISTRY_PATH} JSON boolean syntax")
        return True
    except Exception as e:
        logger.error(f"❌ Error fixing tools registry: {e}")
        return False

if __name__ == "__main__":
    fix_tools_registry()
