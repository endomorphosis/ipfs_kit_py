"""
Backend Authorization Middleware

This module implements middleware for enforcing per-backend authorization policies.
It intercepts requests to storage backends and verifies that the authenticated user
has the required permissions for the requested operation.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements - "Advanced Authentication & Authorization".
"""

import logging
import json
import re
from typing import Dict, Any, Callable, Optional, List, Set, Union

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ipfs_kit_py.mcp.auth.models import User, Role
from ipfs_kit_py.mcp.auth.rbac import RBACManager
from ipfs_kit_py.mcp.auth.audit_logging import AuditLogger, AuditEventType, AuditSeverity

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("backend_authorization")

class BackendAuthorizationMiddleware:
    """Middleware for enforcing per-backend authorization policies."""
    
    def __init__(
        self,
        rbac_manager: RBACManager,
        backend_manager: Any,
        audit_logger: Optional[AuditLogger] = None
    ):
        """
        Initialize backend authorization middleware.
        
        Args:
            rbac_manager: RBAC manager instance
            backend_manager: Backend manager instance
            audit_logger: Optional audit logger instance
        """
        self.rbac_manager = rbac_manager
        self.backend_manager = backend_manager
        self.audit_logger = audit_logger
        
        # Compile backend operation patterns
        self.backend_patterns = [
            # IPFS backend
            (re.compile(r'^/api/v0/ipfs/(.*)$'), 'ipfs'),
            # Generic storage backend
            (re.compile(r'^/api/v0/storage/get/([^/]+)/.*$'), None),
            (re.compile(r'^/api/v0/storage/add$'), None),
            # Stream operations
            (re.compile(r'^/api/v0/stream/download/([^/]+)/.*$'), None),
            (re.compile(r'^/api/v0/stream/upload/finalize$'), None),
            # Migration
            (re.compile(r'^/api/v0/migration/.*$'), 'migration'),
            # Search
            (re.compile(r'^/api/v0/search/.*$'), 'search'),
            # DAG operations
            (re.compile(r'^/api/v0/dag/.*$'), 'dag'),
            # DHT operations
            (re.compile(r'^/api/v0/dht/.*$'), 'dht'),
            # IPNS operations
            (re.compile(r'^/api/v0/name/.*$'), 'ipns'),
        ]
        
        # Map HTTP methods to operations
        self.method_operations = {
            'GET': 'read',
            'HEAD': 'read',
            'OPTIONS': 'read',
            'POST': 'write',
            'PUT': 'write',
            'DELETE': 'delete',
            'PATCH': 'write'
        }
        
        logger.info("Backend authorization middleware initialized")
    
    async def authorize_backend_access(self, request: Request, call_next: Callable) -> Response:
        """
        Authorize backend access for a request.
        
        Args:
            request: FastAPI request
            call_next: Next middleware function
            
        Returns:
            Response from the next middleware or 403 if unauthorized
        """
        # Skip OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Get the path and method
        path = request.url.path
        method = request.method
        
        # Get the backend and operation
        backend, operation_type = self._identify_backend_operation(request)
        
        # If no backend or operation identified, pass through
        if not backend or not operation_type:
            return await call_next(request)
        
        # Get the user from request state
        user = getattr(request.state, 'user', None)
        if not user:
            # No authenticated user, let auth middleware handle it
            return await call_next(request)
        
        # Skip authorization for admin and system users
        if user.role == Role.ADMIN or user.role == Role.SYSTEM:
            return await call_next(request)
        
        # Check if user has the required permission
        permission = f"{operation_type}:{backend}"
        has_permission = self.rbac_manager.check_permission(
            user_id=user.id,
            permission=permission
        )
        
        # Log authorization attempt
        if self.audit_logger:
            self.audit_logger.log(
                event_type=AuditEventType.BACKEND,
                action="backend_access",
                severity=AuditSeverity.INFO if has_permission else AuditSeverity.WARNING,
                user_id=user.id,
                details={
                    "backend": backend,
                    "operation": operation_type,
                    "method": method,
                    "path": path,
                    "granted": has_permission
                }
            )
        
        if not has_permission:
            # Create JSON response for unauthorized access
            error_message = {
                "success": False,
                "error": "Permission denied",
                "detail": f"You do not have permission to {operation_type} on {backend} backend",
                "required_permission": permission
            }
            return Response(
                content=json.dumps(error_message),
                status_code=403,
                media_type="application/json"
            )
        
        # User has permission, continue
        return await call_next(request)
    
    def _identify_backend_operation(self, request: Request) -> tuple[Optional[str], Optional[str]]:
        """
        Identify the backend and operation type from a request.
        
        Args:
            request: FastAPI request
            
        Returns:
            Tuple of (backend_name, operation_type) or (None, None) if not identified
        """
        path = request.url.path
        method = request.method
        
        # Get operation type from method
        operation_type = self.method_operations.get(method, 'read')
        
        # Extract backend from path
        backend = None
        
        # Check URL patterns
        for pattern, default_backend in self.backend_patterns:
            match = pattern.match(path)
            if match:
                # If pattern has a capture group, use it as backend name
                if match.groups() and not default_backend:
                    backend = match.group(1)
                else:
                    backend = default_backend
                break
        
        # If no backend identified but path starts with /api/v0/
        if not backend and path.startswith('/api/v0/'):
            # Extract first component after /api/v0/
            parts = path.split('/')
            if len(parts) > 3:
                backend = parts[3]
        
        # Handle special case for storage endpoint with backend in form
        if path == '/api/v0/storage/add' and request.method == 'POST':
            # We'll need to get the backend from form data in a real implementation
            # For now, default to 'ipfs'
            backend = 'ipfs'
        
        # Handle special case for storage upload finalize
        if path == '/api/v0/stream/upload/finalize' and request.method == 'POST':
            # Would need to get backend from form data
            backend = 'ipfs'
        
        return backend, operation_type
    
    def get_backend_permissions(self, user_id: str) -> Dict[str, List[str]]:
        """
        Get per-backend permissions for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary mapping backend names to allowed operations
        """
        return self.rbac_manager.get_backend_permissions(user_id)


def check_backend_permission(backend: str, operation: Optional[str] = None, write_access: bool = False) -> bool:
    """
    Check if current user has permission for a backend operation.
    
    Args:
        backend: Backend name
        operation: Optional specific operation
        write_access: Whether to check for write access
        
    Returns:
        True if permission granted
    """
    # This is a placeholder - in production, this would use request.state.user
    # For now, we'll allow all operations
    return True


def require_backend_permission(backend: str, operation: Optional[str] = None, write_access: bool = False):
    """
    Dependency to require backend permission.
    
    Args:
        backend: Backend name
        operation: Optional specific operation
        write_access: Whether to require write access
        
    Returns:
        Dependency function
    """
    async def dependency(request: Request):
        user = getattr(request.state, 'user', None)
        if not user:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )
        
        # Skip authorization for admin and system users
        if user.role == Role.ADMIN or user.role == Role.SYSTEM:
            return True
        
        # Determine operation to check
        op = operation or ('write' if write_access else 'read')
        permission = f"{op}:{backend}"
        
        # Get RBAC manager and check permission
        from ipfs_kit_py.mcp.auth.auth_integration import get_auth_system
        auth_system = get_auth_system()
        
        if not auth_system or not auth_system.rbac_manager:
            # If auth system not initialized, deny access
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authorization system not initialized"
            )
        
        has_permission = auth_system.rbac_manager.check_permission(
            user_id=user.id,
            permission=permission
        )
        
        if not has_permission:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: You do not have {op} access to the {backend} backend"
            )
        
        return True
    
    return dependency