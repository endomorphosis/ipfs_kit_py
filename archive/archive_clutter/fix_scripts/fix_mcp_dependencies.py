#!/usr/bin/env python3
"""
MCP Server Dependency Fixer

This script will modify the final_mcp_server.py to better handle missing dependencies,
particularly the issue with multihash.FuncReg not being found.
"""

import os
import sys
import re
import shutil
from datetime import datetime

# Configuration
SERVER_PATH = "/home/barberb/ipfs_kit_py/final_mcp_server.py"
BACKUP_PATH = f"/home/barberb/ipfs_kit_py/final_mcp_server.py.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"

# Create a backup of the original file
shutil.copy2(SERVER_PATH, BACKUP_PATH)
print(f"Created backup at {BACKUP_PATH}")

# Read the original file
with open(SERVER_PATH, 'r') as f:
    content = f.read()

# Modify the import section to catch and handle the multihash error
multihash_fix = """
# --- Handle multihash.FuncReg error ---
try:
    import multihash
    if not hasattr(multihash, 'FuncReg'):
        # Create a mock FuncReg object
        class MockFuncReg:
            @staticmethod
            def register(*args, **kwargs):
                pass
        multihash.FuncReg = MockFuncReg()
        logger.warning("Created mock multihash.FuncReg implementation")
except ImportError:
    logger.warning("multihash module not available, some IPFS features may be limited")
"""

# Find the end of the imports section
import_section_end = re.search(r'# --- Early Setup: Logging and Path ---', content)
if import_section_end:
    # Insert the fix just before this line
    content = content[:import_section_end.start()] + multihash_fix + content[import_section_end.start():]
    
    # Write the modified content back
    with open(SERVER_PATH, 'w') as f:
        f.write(content)
    
    print("Successfully added multihash.FuncReg fix to the server script")
else:
    print("Could not find a suitable place to insert the fix")
    sys.exit(1)

print("Done. Please restart the server to apply the changes.")
