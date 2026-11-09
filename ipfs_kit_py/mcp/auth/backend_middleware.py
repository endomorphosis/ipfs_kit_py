"""
Backend Authorization Middleware

This middleware enforces permissions for access to different storage backends,
integrating with the backend authorization system to control access based on
user roles and API keys.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
import re
import json
from typing import List, Dict, Optional, Any, Callable, Set, Pattern
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.status import HTTP_403_FORBIDDEN

from ipfs_kit_py.mcp.auth.backend_authorization_integration import get_backend_auth_manager
from ipfs_kit_py.mcp.auth.models import User
from ipfs_kit_py.mcp.auth.api_key_enhanced import ApiKey
from ipfs_kit_py.mcp.auth.audit import get_instance as get_audit_logger

logger = logging.getLogger(__name__)


class BackendAuthorizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for enforcing backend authorization policies.
    
    This middleware intercepts requests to backend-specific endpoints and checks
    whether the authenticated user has permission to access the requested backend.
    """
    
    def __init__(
        self,
        app,
        backend_manager=None,
        exclude_paths: List[str] = None,
    ):
        """
        Initialize the backend authorization middleware.
        
        Args:
            app: ASGI application
            backend_manager: Storage backend manager
            exclude_paths: List of path prefixes to exclude from authorization checks
        """
        super().__init__(app)
        self.backend_manager = backend_manager
        self.exclude_paths = exclude_paths or []
        
        # Compiled regex patterns for matching backend paths
        self._backend_patterns: Dict[str, Pattern] = {}
        
        # Cache of path -> backend_id mappings for faster lookups
        self._path_backend_cache: Dict[str, Optional[str]] = {}
        
        # Initialize backend patterns if backend manager is available
        if self.backend_manager:
            self._initialize_backend_patterns()
        
        logger.info("Backend authorization middleware initialized")
    
    def _initialize_backend_patterns(self):
        """Initialize regex patterns for matching backend-specific paths."""
        # Pattern for backend-specific endpoints in the form /api/v0/storage/{backend_id}/...
        self._backend_patterns["storage"] = re.compile(r"^/api/v0/storage/([^/]+)")
        
        # Pattern for backend-specific operations in the form /api/v0/backends/{backend_id}/...
        self._backend_patterns["backends"] = re.compile(r"^/api/v0/backends/([^/]+)")
        
        # Pattern for migration endpoints referencing source/target backends
        self._backend_patterns["migration"] = re.compile(r"^/api/v0/migration/([^/]+)/to/([^/]+)")
        
        # Pattern for backend-specific metadata endpoints
        self._backend_patterns["metadata"] = re.compile(r"^/api/v0/metadata/([^/]+)")
        
        logger.debug(f"Initialized {len(self._backend_patterns)} backend path patterns")
    
    def _extract_backend_id(self, path: str) -> Optional[str]:
        """
        Extract backend ID from a request path.
        
        Args:
            path: Request path
            
        Returns:
            Backend ID if found, None otherwise
        """
        # Check cache first
        if path in self._path_backend_cache:
            return self._path_backend_cache[path]
        
        # Check each pattern
        for pattern_name, pattern in self._backend_patterns.items():
            match = pattern.match(path)
            if match:
                # Special handling for migration endpoints (source backend)
                if pattern_name == "migration" and len(match.groups()) >= 2:
                    backend_id = match.group(1)  # Source backend
                else:
                    backend_id = match.group(1)
                
                # Update cache
                self._path_backend_cache[path] = backend_id
                return backend_id
        
        # No match found
        self._path_backend_cache[path] = None
        return None
    
    def _extract_operation(self, method: str, path: str) -> str:
        """
        Extract the operation type from the request method and path.
        
        Args:
            method: HTTP method
            path: Request path
            
        Returns:
            Operation type (access, read, write, admin)
        """
        # Default operation is access
        operation = "access"
        
        # Map HTTP methods to operations
        if method in ["GET", "HEAD"]:
            operation = "read"
        elif method in ["POST", "PUT", "PATCH"]:
            operation = "write"
        elif method == "DELETE":
            operation = "write"  # Delete is considered a write operation
        
        # Check for admin operations in the path
        if "/admin/" in path or "/manage/" in path or path.endswith("/admin"):
            operation = "admin"
        
        return operation
    
    async def _get_user_from_request(self, request: Request) -> Optional[User]:
        """
        Get the authenticated user from the request state.
        
        Args:
            request: Request object
            
        Returns:
            User object if authenticated, None otherwise
        """
        # Try to get user from request state
        return getattr(request.state, "user", None)
    
    async def _get_api_key_from_request(self, request: Request) -> Optional[ApiKey]:
        """
        Get the API key from the request state.
        
        Args:
            request: Request object
            
        Returns:
            ApiKey object if present, None otherwise
        """
        # Try to get API key from request state
        return getattr(request.state, "api_key", None)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and enforce backend authorization.
        
        Args:
            request: Request object
            call_next: Next middleware in the chain
            
        Returns:
            Response from the next middleware or 403 if access is denied
        """
        # Check if path should be excluded
        path = request.url.path
        for exclude_prefix in self.exclude_paths:
            if path.startswith(exclude_prefix):
                return await call_next(request)
        
        # Extract backend ID from path
        backend_id = self._extract_backend_id(path)
        
        # If no backend ID found, allow the request
        if not backend_id:
            return await call_next(request)
        
        # Get user and API key from request
        user = await self._get_user_from_request(request)
        api_key = await self._get_api_key_from_request(request)
        
        # If no user or API key, deny access
        if not user and not api_key:
            logger.warning(f"Access denied to backend {backend_id}: No authenticated user or API key")
            return self._create_access_denied_response("Authentication required to access backend")
        
        # Determine operation type
        operation = self._extract_operation(request.method, path)
        
        # Get backend authorization manager
        backend_auth_manager = get_backend_auth_manager()
        if not backend_auth_manager:
            logger.error("Backend authorization manager not initialized")
            return self._create_access_denied_response("Backend authorization system not available")
        
        # Check if access is allowed
        has_access = await backend_auth_manager.check_backend_access(
            user=user,
            backend_id=backend_id,
            operation=operation,
            api_key=api_key,
            context={"path": path, "method": request.method}
        )
        
        if not has_access:
            # Log the denied access
            audit_logger = get_audit_logger()
            if audit_logger:
                user_id = user.id if user else (api_key.user_id if api_key else None)
                username = user.username if user else None
                
                await audit_logger.log_event(
                    action="backend_access_denied",
                    user_id=user_id,
                    username=username,
                    target=f"backend:{backend_id}",
                    status="failure",
                    details={
                        "operation": operation,
                        "path": path,
                        "method": request.method,
                        "api_key_id": api_key.id if api_key else None,
                    },
                    priority="high"
                )
            
            logger.warning(
                f"Access denied to backend {backend_id}: "
                f"User={user.id if user else None}, "
                f"Operation={operation}, "
                f"Path={path}"
            )
            
            return self._create_access_denied_response(
                f"You do not have permission to {operation} the {backend_id} backend"
            )
        
        # Access allowed, proceed with the request
        response = await call_next(request)
        
        # Log successful access if it's an API key
        if api_key:
            audit_logger = get_audit_logger()
            if audit_logger:
                await audit_logger.log_event(
                    action="backend_access",
                    user_id=api_key.user_id,
                    username=None,
                    target=f"backend:{backend_id}",
                    status="success",
                    details={
                        "operation": operation,
                        "path": path,
                        "method": request.method,
                        "api_key_id": api_key.id,
                    },
                    priority="low"
                )
        
        return response
    
    def _create_access_denied_response(self, message: str) -> JSONResponse:
        """
        Create a JSON response for access denied.
        
        Args:
            message: Error message
            
        Returns:
            JSONResponse with 403 status code
        """
        return JSONResponse(
            status_code=HTTP_403_FORBIDDEN,
            content={
                "error": "forbidden",
                "message": message,
                "code": "backend_access_denied"
            }
        )