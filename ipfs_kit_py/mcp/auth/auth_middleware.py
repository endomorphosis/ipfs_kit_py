"""
Authentication and Authorization Middleware for MCP server.

This middleware integrates the RBAC, backend authorization, and audit logging systems
with FastAPI to provide comprehensive authentication and authorization for MCP API requests.

Features:
- Authentication middleware for JWT, API key, and OAuth token validation
- Authorization middleware for RBAC and backend-specific permissions
- Automatic audit logging of all authentication and authorization events
- Configuration options for different authorization levels
"""

import logging
import time
import json
from typing import Dict, Any, Optional, List, Callable, Union
from enum import Enum

from fastapi import Request, Response, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# Import authorization components
from ..rbac import get_rbac_manager, get_current_user_role, has_permission, has_backend_permission
from .backend_authorization import get_instance as get_backend_auth, Operation
from .audit import get_instance as get_audit_logger, AuditEventType, AuditLogEntry

# Configure logging
logger = logging.getLogger(__name__)

# Security scheme for bearer token
security = HTTPBearer(auto_error=False)


class AuthLevel(str, Enum):
    """Authorization levels for API endpoints."""
    PUBLIC = "public"  # No authentication required
    AUTHENTICATED = "authenticated"  # Any authenticated user
    VERIFIED = "verified"  # Verified user (email verified, etc.)
    RBAC = "rbac"  # Role-based access control
    BACKEND = "backend"  # Backend-specific authorization


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware for authentication and authorization in MCP server.
    
    This middleware handles:
    1. JWT/API key validation
    2. Role-based access control
    3. Backend-specific authorization
    4. Audit logging
    """
    
    def __init__(
        self,
        app,
        auth_config: Dict[str, Any] = None,
        exclude_paths: List[str] = None,
        rbac_config_path: Optional[str] = None,
    ):
        """
        Initialize the authentication middleware.
        
        Args:
            app: The FastAPI application
            auth_config: Configuration for the authentication system
            exclude_paths: List of paths to exclude from authentication
            rbac_config_path: Path to RBAC configuration file
        """
        super().__init__(app)
        self.auth_config = auth_config or {}
        self.exclude_paths = exclude_paths or ["/docs", "/redoc", "/openapi.json", "/health", "/"]
        
        # Get components
        self.rbac_manager = get_rbac_manager()
        self.backend_auth = get_backend_auth()
        self.audit_logger = get_audit_logger()
        
        # Route-specific auth levels
        self.route_auth_levels: Dict[str, AuthLevel] = {}
        
        # Parse auth configuration
        self._parse_auth_config()
        
        logger.info("Authentication middleware initialized")
    
    def _parse_auth_config(self):
        """Parse authentication configuration."""
        # Get default auth level
        self.default_auth_level = AuthLevel(self.auth_config.get("default_level", AuthLevel.AUTHENTICATED))
        
        # Get route-specific auth levels
        route_levels = self.auth_config.get("route_levels", {})
        for route, level in route_levels.items():
            self.route_auth_levels[route] = AuthLevel(level)
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process incoming requests.
        
        Args:
            request: The incoming request
            call_next: The next middleware in the chain
            
        Returns:
            Response
        """
        # Skip authentication for excluded paths
        path = request.url.path
        if any(path.startswith(exclude) for exclude in self.exclude_paths):
            return await call_next(request)
        
        # Get auth level for this route
        auth_level = self._get_auth_level(path)
        
        # For public routes, no authentication needed
        if auth_level == AuthLevel.PUBLIC:
            return await call_next(request)
        
        # Start timing authentication
        auth_start_time = time.time()
        
        # Extract authentication credentials
        auth_result = await self._authenticate(request)
        authenticated = auth_result["authenticated"]
        user_data = auth_result["user"]
        auth_method = auth_result["method"]
        auth_error = auth_result.get("error")
        
        # Check if authentication is required but failed
        if auth_level != AuthLevel.PUBLIC and not authenticated:
            # Log authentication failure
            await self._log_auth_event(
                request=request,
                success=False,
                user_id=None,
                username=None,
                method=auth_method,
                error=auth_error,
            )
            
            # Return error response
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Not authenticated",
                    "error": auth_error or "Authentication required",
                },
            )
        
        # Set authentication in request state
        request.state.auth = {
            "authenticated": authenticated,
            "user": user_data,
            "method": auth_method,
        }
        
        # Log authentication success
        await self._log_auth_event(
            request=request,
            success=True,
            user_id=user_data.get("id") if user_data else None,
            username=user_data.get("username") if user_data else None,
            method=auth_method,
        )
        
        # For authenticated level, proceed if authenticated
        if auth_level == AuthLevel.AUTHENTICATED:
            return await call_next(request)
        
        # For verified level, check if user is verified
        if auth_level == AuthLevel.VERIFIED:
            if not user_data.get("verified", False):
                await self._log_auth_event(
                    request=request,
                    success=False,
                    user_id=user_data.get("id"),
                    username=user_data.get("username"),
                    method=auth_method,
                    error="User not verified",
                )
                
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Verified user required for this resource"},
                )
            
            return await call_next(request)
        
        # For RBAC level, check permissions
        if auth_level == AuthLevel.RBAC:
            permission = self._get_required_permission(path, request.method)
            if not permission:
                # No specific permission required, proceed
                return await call_next(request)
            
            # Get user role from request
            role = get_current_user_role(request)
            has_perm = has_permission(role, permission)
            
            # Log permission check
            await self._log_permission_check(
                request=request,
                permission=permission,
                granted=has_perm,
                user_id=user_data.get("id") if user_data else None,
            )
            
            if not has_perm:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "detail": f"Permission denied",
                        "required_permission": permission,
                    },
                )
            
            return await call_next(request)
        
        # For backend level, check backend permissions
        if auth_level == AuthLevel.BACKEND:
            backend_id = self._get_backend_id(path)
            operation = self._get_backend_operation(path, request.method)
            
            if not backend_id:
                # No specific backend, proceed
                return await call_next(request)
            
            # Get user role from request
            role = get_current_user_role(request)
            has_backend_perm = has_backend_permission(role, backend_id, operation)
            
            # Log backend access check
            await self._log_backend_access(
                request=request,
                backend_id=backend_id,
                operation=operation,
                granted=has_backend_perm,
                user_id=user_data.get("id") if user_data else None,
            )
            
            if not has_backend_perm:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "detail": f"Backend access denied",
                        "backend": backend_id,
                        "operation": operation,
                    },
                )
            
            return await call_next(request)
        
        # If no specific checks needed, proceed
        return await call_next(request)
    
    def _get_auth_level(self, path: str) -> AuthLevel:
        """
        Get the authentication level for a path.
        
        Args:
            path: The request path
            
        Returns:
            AuthLevel
        """
        # Find the most specific match in route_auth_levels
        matching_routes = []
        for route, level in self.route_auth_levels.items():
            if path.startswith(route):
                matching_routes.append((route, level))
        
        if matching_routes:
            # Sort by length of route prefix (longest first)
            matching_routes.sort(key=lambda x: len(x[0]), reverse=True)
            return matching_routes[0][1]
        
        # Fall back to default level
        return self.default_auth_level
    
    async def _authenticate(self, request: Request) -> Dict[str, Any]:
        """
        Authenticate a request.
        
        Args:
            request: The incoming request
            
        Returns:
            Dictionary with authentication result
        """
        # Check for Authorization header (Bearer token)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            return await self._validate_jwt(token)
        
        # Check for API key in header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return await self._validate_api_key(api_key)
        
        # Check for session cookie
        session_id = request.cookies.get("mcp_session")
        if session_id:
            return await self._validate_session(session_id)
        
        # No authentication provided
        return {
            "authenticated": False,
            "method": "none",
            "error": "No authentication credentials provided",
            "user": None,
        }
    
    async def _validate_jwt(self, token: str) -> Dict[str, Any]:
        """
        Validate a JWT token.
        
        Args:
            token: The JWT token
            
        Returns:
            Authentication result
        """
        # This would normally decode and validate the JWT
        # For now, stub implementation for compatibility
        # In a real system, this would use a proper JWT library
        try:
            # Placeholder for JWT validation
            # In a real implementation, decode and verify signature
            # For example, with PyJWT
            
            # Simplified check for testing
            if "." in token and len(token) > 40:
                # Mock successful validation
                return {
                    "authenticated": True,
                    "method": "jwt",
                    "user": {
                        "id": "user123",
                        "username": "test_user",
                        "roles": ["user"],
                        "verified": True,
                    }
                }
            
            return {
                "authenticated": False,
                "method": "jwt",
                "error": "Invalid JWT token",
                "user": None,
            }
            
        except Exception as e:
            logger.error(f"Error validating JWT: {e}")
            return {
                "authenticated": False,
                "method": "jwt",
                "error": str(e),
                "user": None,
            }
    
    async def _validate_api_key(self, api_key: str) -> Dict[str, Any]:
        """
        Validate an API key.
        
        Args:
            api_key: The API key
            
        Returns:
            Authentication result
        """
        # This would normally look up and validate the API key
        # For now, stub implementation for compatibility
        try:
            # Placeholder for API key validation
            # In a real implementation, query database
            
            # Simplified check for testing
            if len(api_key) >= 32:
                # Mock successful validation
                return {
                    "authenticated": True,
                    "method": "api_key",
                    "user": {
                        "id": "apiuser456",
                        "username": "api_user",
                        "roles": ["api_client"],
                        "verified": True,
                    }
                }
            
            return {
                "authenticated": False,
                "method": "api_key",
                "error": "Invalid API key",
                "user": None,
            }
            
        except Exception as e:
            logger.error(f"Error validating API key: {e}")
            return {
                "authenticated": False,
                "method": "api_key",
                "error": str(e),
                "user": None,
            }
    
    async def _validate_session(self, session_id: str) -> Dict[str, Any]:
        """
        Validate a session.
        
        Args:
            session_id: The session ID
            
        Returns:
            Authentication result
        """
        # This would normally validate the session using a session store
        # For now, stub implementation for compatibility
        try:
            # Placeholder for session validation
            # In a real implementation, query session store
            
            # Simplified check for testing
            if len(session_id) >= 16:
                # Mock successful validation
                return {
                    "authenticated": True,
                    "method": "session",
                    "user": {
                        "id": "sessionuser789",
                        "username": "session_user",
                        "roles": ["user"],
                        "verified": True,
                    }
                }
            
            return {
                "authenticated": False,
                "method": "session",
                "error": "Invalid session",
                "user": None,
            }
            
        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return {
                "authenticated": False,
                "method": "session",
                "error": str(e),
                "user": None,
            }
    
    def _get_required_permission(self, path: str, method: str) -> Optional[str]:
        """
        Get the required permission for a path and method.
        
        Args:
            path: The request path
            method: The HTTP method
            
        Returns:
            Required permission or None
        """
        # This would normally be loaded from a permission mapping
        # For now, simple path-based inference for compatibility
        
        # Extract resource type from path
        parts = path.strip("/").split("/")
        if len(parts) < 2:
            return None
        
        resource_type = parts[1]  # e.g., "ipfs", "filecoin"
        
        # Map HTTP method to operation
        operation_map = {
            "GET": "read",
            "HEAD": "read",
            "OPTIONS": "read",
            "POST": "write",
            "PUT": "write",
            "PATCH": "write",
            "DELETE": "delete",
        }
        
        operation = operation_map.get(method, "read")
        
        # Special case for advanced operations
        if len(parts) >= 3:
            action = parts[2]
            if action in ["pin", "unpin", "publish", "admin"]:
                return f"{action}:{resource_type}"
        
        # Default permission format
        return f"{operation}:{resource_type}"
    
    def _get_backend_id(self, path: str) -> Optional[str]:
        """
        Extract backend ID from path.
        
        Args:
            path: The request path
            
        Returns:
            Backend ID or None
        """
        # Extract from path like /api/v0/s3/... or /api/v0/ipfs/...
        parts = path.strip("/").split("/")
        if len(parts) < 2:
            return None
        
        # Handle API version prefix
        if parts[0] == "api" and parts[1].startswith("v"):
            if len(parts) < 3:
                return None
            return parts[2]
        
        return parts[1]
    
    def _get_backend_operation(self, path: str, method: str) -> str:
        """
        Get the backend operation for a path and method.
        
        Args:
            path: The request path
            method: The HTTP method
            
        Returns:
            Backend operation
        """
        # Map HTTP method to operation
        method_map = {
            "GET": Operation.RETRIEVE,
            "HEAD": Operation.RETRIEVE,
            "OPTIONS": Operation.RETRIEVE,
            "POST": Operation.STORE,
            "PUT": Operation.STORE,
            "PATCH": Operation.STORE,
            "DELETE": Operation.DELETE,
        }
        
        base_operation = method_map.get(method, Operation.RETRIEVE)
        
        # Special case for administrative operations
        parts = path.strip("/").split("/")
        if len(parts) >= 4:
            action = parts[3]
            if action in ["admin", "config", "maintenance"]:
                return Operation.ADMIN
            elif action in ["list", "ls", "find"]:
                return Operation.LIST
            elif action in ["query", "search"]:
                return Operation.QUERY
        
        return base_operation
    
    async def _log_auth_event(
        self,
        request: Request,
        success: bool,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        method: str = "unknown",
        error: Optional[str] = None,
    ):
        """
        Log an authentication event to the audit log.
        
        Args:
            request: The request being authenticated
            success: Whether authentication was successful
            user_id: User ID if available
            username: Username if available
            method: Authentication method
            error: Error message if authentication failed
        """
        if not self.audit_logger:
            return
        
        # Get client info
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent", "unknown")
        
        # Create details
        details = {
            "method": method,
            "path": str(request.url.path),
            "query": str(request.url.query),
            "http_method": request.method,
        }
        
        if error:
            details["error"] = error
        
        # Log to audit logger
        await self.audit_logger.log_login(
            success=success,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )
    
    async def _log_permission_check(
        self,
        request: Request,
        permission: str,
        granted: bool,
        user_id: Optional[str] = None,
    ):
        """
        Log a permission check to the audit log.
        
        Args:
            request: The request being checked
            permission: The permission being checked
            granted: Whether permission was granted
            user_id: User ID if available
        """
        if not self.audit_logger:
            return
        
        # Extract resource info from path
        path = request.url.path
        parts = path.strip("/").split("/")
        
        resource_type = parts[1] if len(parts) > 1 else None
        resource_id = parts[2] if len(parts) > 2 else None
        
        # Log to audit logger
        await self.audit_logger.log_permission_check(
            user_id=user_id,
            permission=permission,
            resource_type=resource_type,
            resource_id=resource_id,
            granted=granted,
            details={
                "path": str(path),
                "method": request.method,
            },
        )
    
    async def _log_backend_access(
        self,
        request: Request,
        backend_id: str,
        operation: str,
        granted: bool,
        user_id: Optional[str] = None,
    ):
        """
        Log a backend access check to the audit log.
        
        Args:
            request: The request being checked
            backend_id: The backend being accessed
            operation: The operation being performed
            granted: Whether access was granted
            user_id: User ID if available
        """
        if not self.audit_logger:
            return
        
        # Extract resource ID from path
        path = request.url.path
        parts = path.strip("/").split("/")
        
        resource_id = parts[3] if len(parts) > 3 else None
        
        # Log to audit logger
        await self.audit_logger.log_backend_access(
            success=granted,
            backend_id=backend_id,
            user_id=user_id,
            ip_address=request.client.host if request.client else None,
            action=operation,
            details={
                "path": str(path),
                "method": request.method,
                "resource_id": resource_id,
            },
        )


# Dependency for requiring authentication
async def require_auth(request: Request):
    """
    FastAPI dependency for requiring authentication.
    
    Args:
        request: The incoming request
        
    Returns:
        User data if authenticated
        
    Raises:
        HTTPException: If not authenticated
    """
    auth = getattr(request.state, "auth", None)
    if not auth or not auth.get("authenticated"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    
    return auth.get("user")


# Dependency for requiring verified user
async def require_verified(request: Request):
    """
    FastAPI dependency for requiring a verified user.
    
    Args:
        request: The incoming request
        
    Returns:
        User data if authenticated and verified
        
    Raises:
        HTTPException: If not authenticated or not verified
    """
    auth = getattr(request.state, "auth", None)
    if not auth or not auth.get("authenticated"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    
    user = auth.get("user")
    if not user or not user.get("verified", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verified user required",
        )
    
    return user


# Dependency for requiring specific permission
def require_permission(permission: str):
    """
    FastAPI dependency factory for requiring a specific permission.
    
    Args:
        permission: The required permission
        
    Returns:
        Dependency function
    """
    async def dependency(request: Request):
        auth = getattr(request.state, "auth", None)
        if not auth or not auth.get("authenticated"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        
        # Get user role
        role = get_current_user_role(request)
        
        # Check permission
        if not has_permission(role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission} required",
            )
        
        return auth.get("user")
    
    return dependency


# Dependency for requiring backend access
def require_backend_access(backend_id: str, operation: str = Operation.RETRIEVE):
    """
    FastAPI dependency factory for requiring backend access.
    
    Args:
        backend_id: The backend ID
        operation: The operation being performed
        
    Returns:
        Dependency function
    """
    async def dependency(request: Request):
        auth = getattr(request.state, "auth", None)
        if not auth or not auth.get("authenticated"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        
        # Get user role
        role = get_current_user_role(request)
        
        # Check backend permission
        if not has_backend_permission(role, backend_id, operation):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Backend access denied: {backend_id} {operation}",
            )
        
        return auth.get("user")
    
    return dependency