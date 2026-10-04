#!/usr/bin/env python3
"""
Fix the health handler in the server_bridge.py file
"""

import os
import sys

# Define the path to the server_bridge.py file
mcp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ipfs_kit_py', 'mcp')
server_bridge_path = os.path.join(mcp_dir, 'server_bridge.py')

# Check if the file exists
if not os.path.exists(server_bridge_path):
    print(f"Error: Cannot find server_bridge.py at {server_bridge_path}")
    sys.exit(1)

# Read the current content of the file
with open(server_bridge_path, 'r') as f:
    content = f.read()

# Find the health handler method
health_method_start = content.find("def health")
if health_method_start == -1:
    print(f"Error: Could not find health method in {server_bridge_path}")
    sys.exit(1)

# Find the method body
method_body_start = content.find(":", health_method_start) + 1
# Find the next method (or end of file)
next_method = content.find("def ", method_body_start)
if next_method == -1:
    next_method = len(content)
health_method = content[health_method_start:next_method]

# Check for problematic model.isolation_mode references
if "model.isolation_mode" in health_method:
    # Replace the model.isolation_mode with a safer version using getattr
    fixed_health_method = health_method.replace(
        "model.isolation_mode",
        "getattr(model, 'isolation_mode', self.isolation_mode)"
    )

    # Update the content
    content = content.replace(health_method, fixed_health_method)

    # Write the modified content back to the file
    with open(server_bridge_path, 'w') as f:
        f.write(content)

    print(f"✅ Fixed health method in {server_bridge_path}")
else:
    print(f"✅ No issues found with health method in {server_bridge_path}")

print("\nNow try running the MCP server again with: python ./enhanced_mcp_server_fixed.py")
