"""
Backend Authorization Middleware

Implements middleware for enforcing backend-specific permissions on storage operations.
This middleware integrates with the RBAC system to provide fine-grained
access control for different storage backends.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
import json
from typing import Callable, Dict, Optional, Union
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ipfs_kit_py.mcp.rbac import rbac_manager, check_backend_permission

# Configure logging
logger = logging.getLogger(__name__)

class BackendAuthorizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for enforcing backend-specific permissions.
    
    This middleware checks if the authenticated user has the required
    permissions to access or modify data in specific storage backends.
    """
    
    def __init__(self, app, backend_manager=None):
        """
        Initialize the backend authorization middleware.
        
        Args:
            app: The FastAPI application
            backend_manager: Optional BackendManager instance
        """
        super().__init__(app)
        self.backend_manager = backend_manager
        
        # Define API path patterns that require backend authorization
        # Format: (method, path_pattern, backend_param_name, write_access)
        self.backend_endpoints = [
            # IPFS backend specific endpoints
            ("GET", "/api/v0/ipfs/cat/{cid}", "ipfs", False),
            ("GET", "/api/v0/ipfs/get/{cid}", "ipfs", False),
            ("POST", "/api/v0/ipfs/add", "ipfs", True),
            ("POST", "/api/v0/ipfs/pin/add", "ipfs", True),
            ("POST", "/api/v0/ipfs/pin/rm", "ipfs", True),
            ("GET", "/api/v0/ipfs/pin/ls", "ipfs", False),
            
            # Multi-backend endpoints
            ("GET", "/api/v0/storage/get/{backend}/{cid}", None, False),
            ("POST", "/api/v0/storage/add", "backend", True),
            
            # Migration endpoints
            ("POST", "/api/v0/migration/policy", None, True),
            ("POST", "/api/v0/migration/execute/{policy_name}", None, True),
            
            # Streaming endpoints
            ("POST", "/api/v0/stream/upload/finalize", "backend", True),
            ("GET", "/api/v0/stream/download/{backend}/{cid}", None, False),
        ]
        
        logger.info("Backend Authorization Middleware initialized")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and enforce backend authorization.
        
        Args:
            request: The incoming request
            call_next: The next middleware in the chain
            
        Returns:
            The response from the next middleware
        """
        # Check if this request requires backend authorization
        path = request.url.path
        method = request.method
        
        # Skip authorization check for non-backend endpoints
        requires_auth = False
        backend_name = None
        write_access = False
        
        for req_method, path_pattern, backend_param, is_write in self.backend_endpoints:
            # Convert path pattern to a simple matching pattern by replacing path parameters
            # with wildcards for basic matching
            simplified_pattern = path_pattern.replace("{", "").replace("}", "")
            parts = simplified_pattern.split("/")
            request_parts = path.split("/")
            
            if method == req_method and len(parts) == len(request_parts):
                matches = True
                backend_param_value = None
                
                for i, (pattern_part, request_part) in enumerate(zip(parts, request_parts)):
                    if pattern_part == backend_param:
                        # This part of the path is the backend parameter
                        backend_param_value = request_part
                        continue
                    elif pattern_part != request_part and pattern_part not in simplified_pattern:
                        # If the parts don't match and it's not a path parameter, this is not a match
                        matches = False
                        break
                
                if matches:
                    requires_auth = True
                    write_access = is_write
                    
                    # Extract backend name
                    if backend_param:
                        # Backend is a form parameter
                        if backend_param_value:
                            backend_name = backend_param_value
                        else:
                            # Try to extract from form data or query parameters
                            # This is a simplification - in a real implementation you would 
                            # need to handle different body types and content types
                            if request.query_params.get(backend_param):
                                backend_name = request.query_params.get(backend_param)
                    elif "{backend}" in path_pattern:
                        # Backend is in the path
                        backend_index = parts.index("backend")
                        if backend_index < len(request_parts):
                            backend_name = request_parts[backend_index]
                    
                    # Only need to match one endpoint
                    break
        
        # If this doesn't require backend authorization, proceed
        if not requires_auth:
            return await call_next(request)
        
        # Get backend name from request body for POST requests if not already determined
        if method == "POST" and not backend_name:
            # Try to get from form data
            try:
                form_data = await request.form()
                if "backend" in form_data:
                    backend_name = form_data["backend"]
            except:
                # Not a form request
                pass
            
            # Try to get from JSON body if still not found
            if not backend_name:
                try:
                    body = await request.json()
                    if isinstance(body, dict) and "backend" in body:
                        backend_name = body["backend"]
                except:
                    # Not a JSON request or couldn't parse
                    pass
        
        # If backend name is still not determined and we have a default backend
        # in the endpoint definition, use that
        if not backend_name:
            for req_method, path_pattern, backend_param, is_write in self.backend_endpoints:
                if method == req_method and path_pattern in path:
                    if backend_param and backend_param != "backend":
                        backend_name = backend_param
                    break
        
        # If we still don't have a backend name, default to "ipfs"
        # This is a fallback for endpoints that don't explicitly specify a backend
        if not backend_name:
            backend_name = "ipfs"
        
        # Check if user has permission for this backend operation
        has_permission = check_backend_permission(request, backend_name, write_access)
        
        if not has_permission:
            operation = "write to" if write_access else "read from"
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": f"Permission denied: You don't have permission to {operation} the {backend_name} backend"
                }
            )
        
        # User has permission, proceed with the request
        return await call_next(request)


# Helper function to register the middleware with FastAPI
def register_backend_authorization_middleware(app, backend_manager=None):
    """
    Register the backend authorization middleware with a FastAPI application.
    
    Args:
        app: The FastAPI application
        backend_manager: Optional BackendManager instance
    """
    app.add_middleware(BackendAuthorizationMiddleware, backend_manager=backend_manager)
    logger.info("Registered Backend Authorization Middleware")