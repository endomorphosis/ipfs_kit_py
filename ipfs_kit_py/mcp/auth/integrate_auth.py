#!/usr/bin/env python3
"""
Integrate Authentication & Authorization with MCP Server.

This script adds the advanced authentication and authorization middleware
to the MCP server as specified in the MCP roadmap for Phase 1 (Q3 2025).

Features added:
- Authentication middleware for JWT, API key, and session validation
- Role-based access control (RBAC) for API endpoints
- Per-backend authorization checks
- Comprehensive audit logging
"""

import os
import sys
import logging
import json
import asyncio
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("integrate_auth")

# Define paths
MCP_DIR = Path("/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp")
SERVER_PATH = MCP_DIR / "server.py"
AUTH_CONFIG_PATH = MCP_DIR / "auth" / "config" / "auth_config.json"


async def create_auth_config():
    """Create default authentication configuration."""
    # Ensure directory exists
    os.makedirs(os.path.dirname(AUTH_CONFIG_PATH), exist_ok=True)
    
    # Default authorization configuration
    config = {
        "default_level": "authenticated",
        "route_levels": {
            "/api/v0/ipfs/cat": "public",
            "/api/v0/ipfs/get": "public",
            "/api/v0/ipfs/ls": "public",
            "/docs": "public",
            "/redoc": "public",
            "/openapi.json": "public",
            "/health": "public",
            "/": "public",
            "/api/v0/auth": "public",
            "/api/v0/ipfs": "rbac",
            "/api/v0/filecoin": "rbac",
            "/api/v0/s3": "rbac",
            "/api/v0/storacha": "rbac",
            "/api/v0/huggingface": "rbac",
            "/api/v0/lassie": "rbac",
            "/api/v0/admin": "rbac",
            "/api/v0/storage/backends": "backend"
        },
        "rbac": {
            "config_path": str(MCP_DIR / "auth" / "config" / "rbac.json")
        },
        "audit": {
            "log_file": "auth_audit.log",
            "console_logging": True,
            "file_logging": True,
            "json_logging": True
        }
    }
    
    # Write to file
    with open(AUTH_CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)
    
    logger.info(f"Created default auth configuration at {AUTH_CONFIG_PATH}")
    
    return config


async def update_server_file():
    """Update the MCP server file to include the auth middleware."""
    logger.info(f"Updating MCP server file: {SERVER_PATH}")
    
    # Read server file
    with open(SERVER_PATH, 'r') as f:
        content = f.read()
    
    # Check if middleware is already added
    if "auth_middleware" in content:
        logger.info("Auth middleware already added to server.py")
        return
    
    # Find import section
    import_section_end = content.find("\n\n", content.find("import "))
    
    # Add imports
    new_imports = """
from .auth.auth_middleware import AuthMiddleware, require_auth, require_permission, require_backend_access
from .auth.audit import get_instance as get_audit_logger
"""
    
    # Find FastAPI initialization
    app_init = "app = FastAPI("
    app_init_pos = content.find(app_init)
    if app_init_pos == -1:
        logger.error("Could not find FastAPI initialization in server.py")
        return
    
    # Find register_with_app method
    register_method = "def register_with_app(self, app: FastAPI, prefix: str = \"/api/v0\"):"
    register_pos = content.find(register_method)
    if register_pos == -1:
        logger.error("Could not find register_with_app method in server.py")
        return
    
    # Find the body of the register_with_app method
    register_end = content.find("\n\n", register_pos)
    if register_end == -1:
        register_end = len(content)
    
    # Add method to initialize auth components - fixed the docstring syntax
    add_init_auth = """
    async def initialize_auth(self):
        # Initialize authentication and authorization components
        # Create auth config if it doesn't exist
        auth_config_path = os.path.join(os.path.dirname(__file__), "auth", "config", "auth_config.json")
        if not os.path.exists(auth_config_path):
            # Create default config
            auth_config = {
                "default_level": "authenticated",
                "route_levels": {
                    "/api/v0/ipfs/cat": "public",
                    "/api/v0/ipfs/get": "public",
                    "/api/v0/ipfs/ls": "public",
                    "/docs": "public",
                    "/redoc": "public",
                    "/openapi.json": "public",
                    "/health": "public",
                    "/": "public",
                    "/api/v0/auth": "public",
                    "/api/v0/ipfs": "rbac",
                    "/api/v0/filecoin": "rbac",
                    "/api/v0/s3": "rbac",
                    "/api/v0/storacha": "rbac",
                    "/api/v0/huggingface": "rbac",
                    "/api/v0/lassie": "rbac",
                    "/api/v0/admin": "rbac",
                    "/api/v0/storage/backends": "backend"
                }
            }
            
            # Write to file
            os.makedirs(os.path.dirname(auth_config_path), exist_ok=True)
            with open(auth_config_path, 'w') as f:
                json.dump(auth_config, f, indent=2)
            
            logger.info(f"Created default auth configuration at {auth_config_path}")
        else:
            # Load existing config
            with open(auth_config_path, 'r') as f:
                auth_config = json.load(f)
        
        # Initialize audit logger
        from .auth.audit import get_instance as get_audit_logger
        audit_logger = get_audit_logger()
        await audit_logger.start()
        
        # Initialize backend authorization
        from .auth.backend_authorization import get_instance as get_backend_auth
        backend_auth = get_backend_auth()
        await backend_auth.initialize()
        
        logger.info("Authentication components initialized")
        return auth_config
"""
    
    # Add middleware registration to register_with_app method
    add_middleware = """
        # Initialize auth components and add middleware
        auth_config = await self.initialize_auth()
        
        # Add authentication middleware
        app.add_middleware(
            AuthMiddleware,
            auth_config=auth_config,
            exclude_paths=["/docs", "/redoc", "/openapi.json", "/health", "/"],
        )
        
        logger.info("Added authentication middleware to FastAPI app")
"""
    
    # Modify start method to run initialize_auth
    start_method = "async def start(self"
    start_pos = content.find(start_method)
    if start_pos == -1:
        logger.error("Could not find start method in server.py")
        return
    
    # Find the body of the start method
    start_body_start = content.find(":", start_pos)
    start_body_start = content.find("\n", start_body_start) + 1
    
    # Update content
    modified_content = (
        content[:import_section_end] + new_imports + content[import_section_end:register_end] + 
        add_init_auth + content[register_end:register_end] + 
        content[register_end:register_pos + len(register_method)]
    )
    
    # Find the position to add middleware registration
    route_reg_pos = modified_content.find("# Register routes", register_pos)
    if route_reg_pos == -1:
        # Try another pattern
        route_reg_pos = modified_content.find("self.register_controllers(app, prefix)", register_pos)
    
    if route_reg_pos == -1:
        logger.error("Could not find position to add middleware registration")
        return
    
    # Add middleware registration before route registration
    modified_content = (
        modified_content[:route_reg_pos] + add_middleware + 
        modified_content[route_reg_pos:]
    )
    
    # Add initialize_auth call to start method
    start_updated = modified_content[:start_body_start] + "        # Initialize auth components\n        await self.initialize_auth()\n" + modified_content[start_body_start:]
    
    # Write back to file
    with open(SERVER_PATH, 'w') as f:
        f.write(start_updated)
    
    logger.info("Updated MCP server with auth middleware integration")


async def create_protected_api_endpoint():
    """Create an example controller with protected API endpoints."""
    protected_api_path = MCP_DIR / "controllers" / "protected_api_controller.py"
    
    # Check if file already exists
    if protected_api_path.exists():
        logger.info(f"Protected API controller already exists at {protected_api_path}")
        return
    
    content = """\"\"\"
Protected API endpoints for MCP server.

This controller demonstrates how to use the authentication and authorization
middleware to create protected API endpoints with different security requirements.
\"\"\"

import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, Request, HTTPException, status

from ..auth.auth_middleware import require_auth, require_permission, require_backend_access
from ..auth.backend_authorization import Operation

# Configure logging
logger = logging.getLogger(__name__)


class ProtectedAPIController:
    \"\"\"
    Controller for protected API endpoints.
    \"\"\"
    
    def __init__(self):
        \"\"\"Initialize the controller.\"\"\"
        self.router = APIRouter(tags=["protected"])
    
    def register_routes(self):
        \"\"\"Register protected API routes.\"\"\"
        
        @self.router.get("/user_info")
        async def get_user_info(user = Depends(require_auth)):
            \"\"\"
            Get information about the authenticated user.
            Requires authentication.
            \"\"\"
            return {"user": user}
        
        @self.router.get("/admin_info")
        async def get_admin_info(user = Depends(require_permission("admin:access"))):
            \"\"\"
            Get administrative information.
            Requires admin:access permission.
            \"\"\"
            return {
                "message": "You have admin access!",
                "user": user
            }
        
        @self.router.get("/backend_info/{backend_id}")
        async def get_backend_info(
            backend_id: str,
            user = Depends(require_backend_access("ipfs", Operation.RETRIEVE))
        ):
            \"\"\"
            Get information about a specific backend.
            Requires access to the specified backend.
            \"\"\"
            return {
                "message": f"You have access to the {backend_id} backend!",
                "user": user
            }
        
        # Return the router
        return self.router
"""
    
    # Create file
    with open(protected_api_path, 'w') as f:
        f.write(content)
    
    logger.info(f"Created protected API controller at {protected_api_path}")


async def update_controller_registry():
    """Update the controller registry to include protected_api_controller."""
    controllers_init_path = MCP_DIR / "controllers" / "__init__.py"
    
    # Read file
    with open(controllers_init_path, 'r') as f:
        content = f.read()
    
    # Check if protected_api_controller is already imported
    if "protected_api_controller" in content:
        logger.info("Protected API controller already registered")
        return
    
    # Add import
    import_pos = content.rfind("from .")
    if import_pos == -1:
        logger.error("Could not find import section in controllers/__init__.py")
        return
    
    import_line = "\nfrom .protected_api_controller import ProtectedAPIController"
    
    # Add register function
    register_fn = "\ndef register_protected_api_controller(app, prefix: str):"
    register_fn += "\n    controller = ProtectedAPIController()"
    register_fn += "\n    app.include_router(controller.register_routes(), prefix=prefix + \"/protected\")"
    register_fn += "\n    return controller"
    
    # Add to register_all_controllers function
    register_all_pos = content.find("def register_all_controllers")
    if register_all_pos == -1:
        logger.error("Could not find register_all_controllers in controllers/__init__.py")
        return
    
    register_all_body_end = content.find("return", register_all_pos)
    if register_all_body_end == -1:
        logger.error("Could not find return statement in register_all_controllers")
        return
    
    # Add protected_api_controller registration
    add_registration = "    protected_api = register_protected_api_controller(app, prefix)\n"
    
    # Combine changes
    updated_content = (
        content[:import_pos] + import_pos + import_line + 
        content[import_pos:] + "\n" + register_fn
    )
    
    # Add registration to register_all_controllers
    updated_content = (
        updated_content[:register_all_body_end] + add_registration + 
        updated_content[register_all_body_end:]
    )
    
    # Write back to file
    with open(controllers_init_path, 'w') as f:
        f.write(updated_content)
    
    logger.info("Updated controller registry with protected API controller")


async def main():
    """Main function to integrate auth components with MCP server."""
    logger.info("Starting auth integration with MCP server")
    
    try:
        # Create auth config
        await create_auth_config()
        
        # Update MCP server
        await update_server_file()
        
        # Create protected API endpoints
        await create_protected_api_endpoint()
        
        # Update controller registry
        await update_controller_registry()
        
        logger.info("✅ Successfully integrated auth components with MCP server")
        return 0
    except Exception as e:
        logger.error(f"Error integrating auth components: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        sys.exit(1)