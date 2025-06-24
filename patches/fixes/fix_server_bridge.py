#!/usr/bin/env python3
"""
Fix the server_bridge.py file to correct the register_with_app method
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

# Find the problematic code
problematic_code = """        # Also add routes at root level (without controller prefix) for basic endpoints
        app.include_router(
            APIRouter()
                .get("/health", status_code=200)(
                    lambda: self.router.routes_by_name["health"].endpoint({})
                )
                .get("/version", status_code=200)(
                    lambda: self.router.routes_by_name["version"].endpoint({})
                ),
        )"""

# Define the fixed code
fixed_code = """        # Also add routes at root level (without controller prefix) for basic endpoints
        root_router = APIRouter()

        @root_router.get("/health", status_code=200)
        def get_health():
            return self.router.routes_by_name["health"].endpoint({})

        @root_router.get("/version", status_code=200)
        def get_version():
            return self.router.routes_by_name["version"].endpoint({})

        app.include_router(root_router)"""

# Replace the problematic code with the fixed code
if problematic_code in content:
    new_content = content.replace(problematic_code, fixed_code)

    # Write the fixed content back to the file
    with open(server_bridge_path, 'w') as f:
        f.write(new_content)

    print(f"✅ Successfully fixed the register_with_app method in {server_bridge_path}")
else:
    print(f"❌ Could not find the problematic code in {server_bridge_path}")
    print("The code might have been modified already or the file structure is different.")

print("\nNow try running the MCP server again with: python ./enhanced_mcp_server_fixed.py")
