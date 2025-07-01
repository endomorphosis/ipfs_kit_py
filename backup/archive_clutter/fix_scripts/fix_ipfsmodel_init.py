#!/usr/bin/env python3
"""
Fix IPFSModel initialization in enhanced_mcp_server_fixed.py

This script modifies the enhanced_mcp_server_fixed.py file to fix
the initialization of IPFSModel by removing the ipfs_backend argument.
"""

import os
import sys
import re

# Path to the enhanced MCP server script
mcp_server_path = "./enhanced_mcp_server_fixed.py"

# Read the file content
with open(mcp_server_path, 'r') as f:
    content = f.read()

# Find the IPFSModel initialization in initialize_mcp_components function
pattern = r'(\s+ipfs_model = IPFSModel\()([^)]+)(\))'
match = re.search(pattern, content)

if match:
    init_start, init_args, init_end = match.groups()

    # Parse the arguments
    args = [arg.strip() for arg in init_args.split(',')]

    # Remove 'ipfs_backend=ipfs_backend' argument
    args = [arg for arg in args if not arg.startswith('ipfs_backend=')]

    # Join the remaining arguments
    new_args = ',\n                '.join(args)

    # Replace the old initialization
    new_init = f"{init_start}{new_args}{init_end}"
    modified_content = content.replace(match.group(0), new_init)

    # Write the modified content back to the file
    with open(mcp_server_path, 'w') as f:
        f.write(modified_content)

    print(f"✅ Successfully fixed IPFSModel initialization in {mcp_server_path}")
    print("   Removed 'ipfs_backend' argument that was causing the error.")
else:
    # If we can't find the pattern, let's try a more direct approach
    # Look for the MCPServer initialization
    pattern = r'(\s+mcp_server = MCPServer\()([^)]+)(\))'
    match = re.search(pattern, content)

    if match:
        # Add a fallback ipfs_model initialization after the MCPServer instantiation
        server_init = match.group(0)
        fallback_code = server_init + "\n\n        # Use safe IPFSModel initialization\n        try:\n            from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel\n            ipfs_model = IPFSModel()\n            mcp_server.models['ipfs'] = ipfs_model\n        except Exception as e:\n            logger.warning(f\"Could not initialize IPFSModel: {e}\")\n"
        modified_content = content.replace(server_init, fallback_code)

        # Write the modified content back to the file
        with open(mcp_server_path, 'w') as f:
            f.write(modified_content)

        print(f"✅ Successfully added safe IPFSModel initialization fallback in {mcp_server_path}")
    else:
        print(f"❌ Could not find IPFSModel initialization pattern in {mcp_server_path}")
        print("   Please manually fix the IPFSModel initialization in the enhanced_mcp_server_fixed.py file.")
        print("   Remove the 'ipfs_backend' argument from IPFSModel initialization.")
