#!/usr/bin/env python3
"""
Fix IPFSModel initialization in server_bridge.py

This script modifies the server_bridge.py file to fix
the initialization of IPFSModel with the correct parameters.
"""

import os
import sys

# Path to the server bridge script
server_bridge_path = "./ipfs_kit_py/mcp/server_bridge.py"

# Read the file content
with open(server_bridge_path, 'r') as f:
    content = f.read()

# Find the problematic code block
old_init = '''            # Create config for IPFS model
            ipfs_config = {
                "debug": self.debug_mode,
                "isolation": self.isolation_mode,
                "log_level": self.log_level
            }

            # Correctly initialize the IPFS model with the config parameter
            ipfs_model = IPFSModel(
                ipfs_backend=None,  # Will be initialized later if needed
                debug_mode=self.debug_mode,
                log_level=self.log_level,'''

# New version with correct parameters
new_init = '''            # Create config for IPFS model
            ipfs_config = {
                "debug": self.debug_mode,
                "isolation": self.isolation_mode,
                "log_level": self.log_level
            }

            # Correctly initialize the IPFS model with the config parameter
            ipfs_model = IPFSModel(
                ipfs_kit_instance=None,  # Will be initialized later if needed
                config=ipfs_config,'''

# Replace the problematic code block
if old_init in content:
    modified_content = content.replace(old_init, new_init)

    # Write the modified content back to the file
    with open(server_bridge_path, 'w') as f:
        f.write(modified_content)

    print(f"✅ Successfully fixed IPFSModel initialization in {server_bridge_path}")
    print("   Changed parameters to match IPFSModel constructor.")
else:
    # Try a more direct approach with shorter patterns
    old_pattern = '''            ipfs_model = IPFSModel(
                ipfs_backend=None,  # Will be initialized later if needed
                debug_mode=self.debug_mode,
                log_level=self.log_level,'''

    new_pattern = '''            ipfs_model = IPFSModel(
                ipfs_kit_instance=None,  # Will be initialized later if needed
                config=ipfs_config,'''

    if old_pattern in content:
        modified_content = content.replace(old_pattern, new_pattern)

        # Write the modified content back to the file
        with open(server_bridge_path, 'w') as f:
            f.write(modified_content)

        print(f"✅ Successfully fixed IPFSModel initialization in {server_bridge_path}")
        print("   Changed parameters to match IPFSModel constructor.")
    else:
        print(f"❌ Could not find IPFSModel initialization pattern in {server_bridge_path}")
        print("   Please manually fix the IPFSModel initialization in the server_bridge.py file.")
        print("   Replace the parameters with ipfs_kit_instance=None and config=ipfs_config")
