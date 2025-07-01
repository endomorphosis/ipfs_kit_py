#!/usr/bin/env python3
"""Patch the MCP server to include FS Journal integration"""

import os
import sys
import re

def patch_mcp_server():
    """Add FS Journal integration to the MCP server"""
    file_path = "direct_mcp_server.py"

    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found!")
        return False

    with open(file_path, "r") as f:
        content = f.read()

    # Check if already patched
    if "ipfs_mcp_fs_integration" in content:
        print("MCP server already patched with FS Journal integration")
        return True

    # Add the import
    import_line = "# FS Journal and IPFS Bridge integration\nimport ipfs_mcp_fs_integration"
    last_import_match = list(re.finditer(r"^(?:import|from)\s+.*$", content, re.MULTILINE))[-1]
    if last_import_match:
        content = content[:last_import_match.end()] + "\n" + import_line + content[last_import_match.end():]

    # Find the server initialization line
    server_init_match = re.search(r"server\s*=\s*FastMCP", content)
    if server_init_match:
        # Add the integration call after server initialization
        next_line_match = re.search(r"\n\s*\S", content[server_init_match.end():])
        if next_line_match:
            pos = server_init_match.end() + next_line_match.start()
            integration_call = "\n# Register FS Journal tools\nipfs_mcp_fs_integration.register_with_mcp_server(server)\n"
            content = content[:pos] + integration_call + content[pos:]

    # Write the patched content back
    with open(file_path, "w") as f:
        f.write(content)

    print(f"Successfully patched {file_path} with FS Journal integration")
    return True

if __name__ == "__main__":
    patch_mcp_server()
