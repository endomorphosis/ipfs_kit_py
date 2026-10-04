"""
Protected API endpoints for MCP server.

This controller demonstrates how to use the authentication and authorization
middleware to create protected API endpoints with different security requirements.
"""

import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, Request, HTTPException, status

from ..auth.auth_middleware import require_auth, require_permission, require_backend_access
from ..auth.backend_authorization import Operation

# Configure logging
logger = logging.getLogger(__name__)


class ProtectedAPIController:
    """
    Controller for protected API endpoints.
    """
    
    def __init__(self):
        """Initialize the controller."""
        self.router = APIRouter(tags=["protected"])
    
    def register_routes(self):
        """Register protected API routes."""
        
        @self.router.get("/user_info")
        async def get_user_info(user = Depends(require_auth)):
            """
            Get information about the authenticated user.
            Requires authentication.
            """
            return {"user": user}
        
        @self.router.get("/admin_info")
        async def get_admin_info(user = Depends(require_permission("admin:access"))):
            """
            Get administrative information.
            Requires admin:access permission.
            """
            return {
                "message": "You have admin access!",
                "user": user
            }
        
        @self.router.get("/backend_info/{backend_id}")
        async def get_backend_info(
            backend_id: str,
            user = Depends(require_backend_access("ipfs", Operation.RETRIEVE))
        ):
            """
            Get information about a specific backend.
            Requires access to the specified backend.
            """
            return {
                "message": f"You have access to the {backend_id} backend!",
                "user": user
            }
        
        # Return the router
        return self.router
