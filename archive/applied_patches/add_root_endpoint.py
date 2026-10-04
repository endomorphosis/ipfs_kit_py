#!/usr/bin/env python3
"""
Add the root endpoint to the FastAPI app.

This script adds a root (/) endpoint to the FastAPI app to pass the tests.
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
logger = logging.getLogger("add-root-endpoint")

def add_root_endpoint(server_path):
    """Add a root endpoint to the FastAPI app."""
    logger.info(f"Adding root endpoint to {server_path}")
    
    # Check if file exists
    if not os.path.exists(server_path):
        logger.error(f"Server file not found: {server_path}")
        return False
    
    # Read the file content
    with open(server_path, "r") as f:
        content = f.read()
    
    # Make a backup
    backup_path = f"{server_path}.bak.root.{int(os.path.getmtime(server_path))}"
    with open(backup_path, "w") as f:
        f.write(content)
    logger.info(f"Created backup at {backup_path}")
    
    # Find the FastAPI app creation
    app_pattern = r"(\s+)app = FastAPI\("
    match = re.search(app_pattern, content)
    
    if not match:
        logger.error("Could not find the FastAPI app creation")
        return False
    
    # Find the place to add the root endpoint
    run_app_pattern = r"(\s+)# Run the server"
    run_match = re.search(run_app_pattern, content)
    
    if not run_match:
        logger.error("Could not find the 'Run the server' comment")
        return False
    
    indent = run_match.group(1)  # Extract the indentation level
    position = run_match.start()
    
    # Create the new endpoints code
    new_endpoints = f"""
{indent}# Add basic application-level endpoints
{indent}@app.get("/",
{indent}        summary="Root endpoint",
{indent}        description="Server root endpoint")
{indent}async def root():
{indent}    \"\"\"Server root endpoint.\"\"\"
{indent}    return {{
{indent}        "message": "MCP Server is running",
{indent}        "api_prefix": args.api_prefix,
{indent}        "example_endpoints": {{
{indent}            "health": f"{{args.api_prefix}}/health",
{indent}            "ipfs_version": f"{{args.api_prefix}}/ipfs/version",
{indent}        }}
{indent}    }}
{indent}
{indent}@app.get("/health",
{indent}        summary="Health check endpoint",
{indent}        description="Server health check")
{indent}async def server_health():
{indent}    \"\"\"Server health check endpoint.\"\"\"
{indent}    return {{
{indent}        "status": "ok",
{indent}        "server": "IPFS MCP Server",
{indent}        "version": "0.1.0"
{indent}    }}

"""
    
    # Insert the new endpoints before the 'Run the server' comment
    modified_content = content[:position] + new_endpoints + content[position:]
    
    # Write the modified content back to the file
    with open(server_path, "w") as f:
        f.write(modified_content)
    
    logger.info("Successfully added root endpoint to the server")
    return True

if __name__ == "__main__":
    server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                              "run_mcp_server.py")
    
    if len(sys.argv) > 1:
        server_path = sys.argv[1]
    
    success = add_root_endpoint(server_path)
    sys.exit(0 if success else 1)