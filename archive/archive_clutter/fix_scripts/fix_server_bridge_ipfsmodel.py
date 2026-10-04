#!/usr/bin/env python3
"""
Fix IPFSModel initialization in server_bridge.py

This script modifies the server_bridge.py file to fix
the initialization of IPFSModel by removing the ipfs_backend argument.
"""

import os
import sys

# Path to the server bridge script
server_bridge_path = "./ipfs_kit_py/mcp/server_bridge.py"

# Read the file content
with open(server_bridge_path, 'r') as f:
    content = f.read()

# Find the problematic line
old_init = '''            ipfs_model = IPFSModel(
                ipfs_backend=None,  # Will be initialized later if needed
                debug_mode=self.debug_mode,
                log_level=self.log_level,'''

# New version without ipfs_backend
new_init = '''            ipfs_model = IPFSModel(
                debug_mode=self.debug_mode,
                log_level=self.log_level,'''

# Replace the problematic line
if old_init in content:
    modified_content = content.replace(old_init, new_init)
    
    # Write the modified content back to the file
    with open(server_bridge_path, 'w') as f:
        f.write(modified_content)
    
    print(f"✅ Successfully fixed IPFSModel initialization in {server_bridge_path}")
    print("   Removed 'ipfs_backend' argument that was causing the error.")
else:
    print(f"❌ Could not find IPFSModel initialization pattern in {server_bridge_path}")
    print("   Please manually fix the IPFSModel initialization in the server_bridge.py file.")
    print("   Remove the 'ipfs_backend' argument from IPFSModel initialization.")
