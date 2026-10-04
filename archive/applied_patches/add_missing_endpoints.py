#!/usr/bin/env python3
"""
Add missing root and health endpoints to the MCP server.

This script adds basic endpoints required by the test suite:
- / (root endpoint)
- /health
- /api/v0/versions
"""

import os
import sys
import re
import logging

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
    backup_path = f"{server_path}.bak.{int(os.path.getmtime(server_path))}"
    with open(backup_path, "w") as f:
        f.write(content)
    logger.info(f"Created backup at {backup_path}")
    
    # Find where to add the endpoints
    init_router_pattern = r"(\s+)self\.router = APIRouter\(\)"
    match = re.search(init_router_pattern, content)
    
    if not match:
        logger.error("Could not find the router initialization")
        return False
    
    # Find the self._register_controller_routes() line
    register_routes_pattern = r"(\s+)self\._register_controller_routes\(\)"
    routes_match = re.search(register_routes_pattern, content)
    
    if not routes_match:
        logger.error("Could not find the controller routes registration")
        return False
    
    indent = routes_match.group(1)  # Extract the indentation level
    position = routes_match.start()
    
    # Create the new endpoints code
    new_endpoints = f"""
{indent}# Add basic routes to the router
{indent}
{indent}@self.router.get("/health",
{indent}        summary="Health check endpoint",
{indent}        description="Check if the server is running")
{indent}async def health():
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
{indent}
{indent}@self.router.get("/versions",
{indent}        summary="Get versions of components",
{indent}        description="Get versions of IPFS, server, and dependencies")
{indent}async def versions():
{indent}    \"\"\"Get component versions.\"\"\"
{indent}    import sys
{indent}    import anyio
{indent}    import fastapi
{indent}    
{indent}    versions = {{}}
{indent}    if hasattr(self.models["ipfs"], "get_version"):
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
{indent}
{indent}@self.router.get("",
{indent}        summary="Root MCP endpoint",
{indent}        description="MCP root showing general information")
{indent}async def mcp_root():
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
"""
    
    # Insert the new endpoints before the route registration
    modified_content = content[:position] + new_endpoints + content[position:]
    
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