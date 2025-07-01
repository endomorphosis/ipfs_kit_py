#!/usr/bin/env python3
"""
Add missing root and health endpoints to the MCP server.

This script adds basic endpoints required by the test suite:
- / (root endpoint)
- /versions
- /api/v0/versions
"""

import os
import sys
import re
import logging
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("add-missing-endpoints")

def add_endpoints_to_server(server_path):
    """Add missing endpoints to the MCP server."""
    logger.info(f"Adding missing endpoints to {server_path}")
    
    # Check if file exists
    if not os.path.exists(server_path):
        logger.error(f"Server file not found: {server_path}")
        return False
    
    # Read the file content
    with open(server_path, "r") as f:
        content = f.read()
    
    # Make a backup
    backup_path = f"{server_path}.bak.modified_{int(time.time())}"
    with open(backup_path, "w") as f:
        f.write(content)
    logger.info(f"Created backup at {backup_path}")
    
    # Check if the endpoints already exist
    if "async def versions(" in content and "@self.router.get(\"\"" in content:
        logger.info("Root and versions endpoints already exist")
        return True
    
    # Find the core_endpoints list declaration
    core_endpoints_pattern = r"(\s+)core_endpoints\s*=\s*\[(.*?)\]"
    match = re.search(core_endpoints_pattern, content, re.DOTALL)
    
    if not match:
        logger.error("Could not find core_endpoints list")
        return False
    
    indent = match.group(1)  # Extract the indentation level
    endpoints_list = match.group(0)
    endpoints_end = match.end()
    
    # Check if health endpoint already exists
    health_exists = '"/health"' in endpoints_list
    
    # Create new endpoints to add
    new_endpoints = [
        f',\n{indent}    ("", self.mcp_root, ["GET"])',
        f',\n{indent}    ("/versions", self.versions_endpoint, ["GET"])'
    ]
    
    if not health_exists:
        new_endpoints.append(f',\n{indent}    ("/health", self.health_check, ["GET"])')
    
    # Add the endpoints to the list
    modified_content = content[:endpoints_end - 1]
    for endpoint in new_endpoints:
        modified_content += endpoint
    modified_content += content[endpoints_end - 1:]
    
    # Now add the endpoint methods to the class
    
    # Find a good place to add the methods - before the last method or at the end of the class
    method_definition = re.search(r"(\s+)def\s+\w+\([^)]*\):\s*\n\s+\"\"\"[^\"]*\"\"\"\s*\n", content)
    if method_definition:
        indent = method_definition.group(1)
        method_pos = content.rfind(f"{indent}def ")
        if method_pos == -1:
            method_pos = content.rfind("class ")
            if method_pos == -1:
                method_pos = len(content)
            else:
                # Find end of class
                method_pos = content.find("\n\n", method_pos)
                if method_pos == -1:
                    method_pos = len(content)
    else:
        method_pos = len(content)
        indent = "    "
    
    # Define the new methods
    new_methods = f"""
{indent}async def mcp_root(self):
{indent}    \"\"\"MCP root endpoint.\"\"\"
{indent}    return {{
{indent}        "message": "MCP Server is running",
{indent}        "version": getattr(self, 'version', '0.1.0'),
{indent}        "controllers": list(self.controllers.keys()),
{indent}        "endpoints": {{
{indent}            "health": "/health",
{indent}            "versions": "/versions"
{indent}        }}
{indent}    }}

{indent}async def versions_endpoint(self):
{indent}    \"\"\"Get component versions.\"\"\"
{indent}    import sys
{indent}    import anyio
{indent}    import fastapi
{indent}    
{indent}    versions = {{}}
{indent}    if "ipfs" in self.models and hasattr(self.models["ipfs"], "get_version"):
{indent}        try:
{indent}            ipfs_version = await anyio.to_thread.run_sync(self.models["ipfs"].get_version)
{indent}            versions["ipfs"] = ipfs_version
{indent}        except Exception as e:
{indent}            versions["ipfs"] = {{"success": False, "error": str(e)}}
{indent}    else:
{indent}        versions["ipfs"] = {{"success": False, "version": "unknown"}}
{indent}    
{indent}    return {{
{indent}        "success": True,
{indent}        "server": getattr(self, 'version', '0.1.0'),
{indent}        "ipfs": versions.get("ipfs", {{}}).get("version", "unknown"),
{indent}        "python": sys.version,
{indent}        "dependencies": {{
{indent}            "ipfs_kit_py": getattr(self, 'version', '0.1.0'),
{indent}            "fastapi": getattr(fastapi, "__version__", "unknown"),
{indent}            "anyio": getattr(anyio, "__version__", "unknown")
{indent}        }}
{indent}    }}
"""
    
    # Only add health_check method if it doesn't exist
    if "async def health_check" not in content:
        new_methods += f"""
{indent}async def health_check(self):
{indent}    \"\"\"Health check endpoint.\"\"\"
{indent}    return {{
{indent}        "success": True,
{indent}        "status": "ok",
{indent}        "timestamp": time.time(),
{indent}        "server_id": self.server_id,
{indent}        "debug_mode": self.debug_mode,
{indent}        "isolation_mode": self.isolation_mode,
{indent}        "ipfs_daemon_running": self.ipfs_daemon_running,
{indent}        "auto_start_daemons_enabled": self.auto_start_daemons,
{indent}        "controllers": {{key: True for key in self.controllers.keys()}}
{indent}    }}
"""
    
    # Insert the new methods
    modified_content = modified_content[:method_pos] + new_methods + modified_content[method_pos:]
    
    # Write the modified content back to the file
    with open(server_path, "w") as f:
        f.write(modified_content)
    
    logger.info("Successfully added missing endpoints to the server")
    return True

if __name__ == "__main__":
    server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                              "ipfs_kit_py", "mcp", "server.py")
    
    if len(sys.argv) > 1:
        server_path = sys.argv[1]
    
    success = add_endpoints_to_server(server_path)
    sys.exit(0 if success else 1)