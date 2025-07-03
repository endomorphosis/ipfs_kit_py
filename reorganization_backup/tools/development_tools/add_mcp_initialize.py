#!/usr/bin/env python3
"""
Add initialization endpoint to MCP server to support VS Code extension
"""

import os
import sys

# Path to the enhanced MCP server script
mcp_server_path = "./enhanced_mcp_server_fixed.py"

# Initialize endpoint code to add
init_endpoint_code = """
# Add initialization endpoint for VS Code extension
@app.post("/api/v0/initialize")
async def vs_code_initialize():
    # Handle initialization requests from VS Code extension
    logger.info("Received initialization request from VS Code extension")
    return {
        "capabilities": {
            "eventStream": True,
            "tools": ["ipfs_add", "ipfs_cat", "ipfs_pin", "storage_transfer"],
            "resources": ["ipfs://info", "storage://backends"]
        },
        "serverInfo": {
            "name": "Enhanced MCP Server",
            "version": "0.3.0"
        }
    }
"""

# Read the file content
with open(mcp_server_path, 'r') as f:
    content = f.readlines()

# Find where to insert the endpoint (after app creation)
for i, line in enumerate(content):
    if line.strip().startswith("app = FastAPI("):
        # Look for the end of the FastAPI initialization
        j = i
        while j < len(content) and not content[j].strip().endswith(')'):
            j += 1
        
        if j < len(content):
            # Insert after FastAPI initialization
            content.insert(j + 1, init_endpoint_code)
            break

# Write the modified content back to the file
with open(mcp_server_path, 'w') as f:
    f.writelines(content)

print(f"✅ Successfully added initialization endpoint to {mcp_server_path}")
