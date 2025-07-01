#\!/usr/bin/env python3

"""Script to fix API path prefix conflicts in MCP server."""

import re

def fix_api_path_prefix():
    """Fix API path prefix conflicts in MCP server_anyio.py."""
    file_path = "ipfs_kit_py/mcp/server_anyio.py"
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the register_with_app method
    register_pattern = re.compile(r'def register_with_app.*?app\.include_router\(self\.router, prefix=prefix\)', re.DOTALL)
    match = register_pattern.search(content)
    
    if not match:
        print("Could not find register_with_app method with include_router call")
        return False
    
    old_code = match.group(0)
    
    # New code with path prefix normalization
    new_code = '''def register_with_app(self, app: FastAPI, prefix: str = "/mcp"):
        """
        Register MCP server with a FastAPI application.
        
        Args:
            app: FastAPI application instance
            prefix: URL prefix for MCP endpoints
        """
        # Track registration success
        registration_success = True
        errors = []
        
        # Normalize prefix to ensure it starts with / but doesn't end with /
        if not prefix:
            prefix = "/mcp"  # Default prefix
        
        if not prefix.startswith('/'):
            prefix = '/' + prefix
        
        if prefix.endswith('/'):
            prefix = prefix[:-1]
            
        logger.info(f"Using normalized API prefix: {prefix}")
        
        # Mount the router
        try:
            app.include_router(self.router, prefix=prefix)'''
    
    # Replace the code
    updated_content = content.replace(old_code, new_code)
    
    # Add test endpoint for health checks
    health_endpoint_pattern = re.compile(r'# Create the router.*?self\.router = APIRouter\(\)', re.DOTALL)
    match = health_endpoint_pattern.search(content)
    
    if match:
        old_router_init = match.group(0)
        new_router_init = old_router_init + '''
        
        # Add basic health check endpoint that doesn't conflict with other routes
        @self.router.get("/internal-health")
        async def health_check():
            """Basic health check endpoint."""
            return {
                "status": "ok",
                "timestamp": time.time(),
                "server_type": "mcp_anyio",
                "controllers": list(self.controllers.keys())
            }'''
        
        updated_content = updated_content.replace(old_router_init, new_router_init)
        print("Added internal health check endpoint")
    
    with open(file_path, 'w') as f:
        f.write(updated_content)
    
    print("Successfully fixed API path prefix in MCP server_anyio.py")
    return True

if __name__ == "__main__":
    fix_api_path_prefix()
