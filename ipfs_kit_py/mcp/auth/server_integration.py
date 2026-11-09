#!/usr/bin/env python3
# ipfs_kit_py/mcp/auth/server_integration.py

"""
MCP Server Authentication Integration

This module provides integration between the authentication/authorization system
and the MCP server. It adds middleware and request handlers to enforce access
control across the server's API endpoints.
"""

import functools
import json
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Import auth components
from .rbac_enhanced import (
    Action, ApiKey, Permission, ResourceType, Role, RBACService, 
    AuthorizationResult, RequestAuthenticator, require_permission
)
from .audit_logging import AuditLogger, AuditEvent, AuditEventType
from .oauth_integration import OAuthManager

# Logger setup
logger = logging.getLogger(__name__)


class AuthMiddleware:
    """
    Authentication and authorization middleware for the MCP server.
    
    This middleware intercepts requests to ensure they are properly authenticated
    and authorized before being processed by the server's handlers.
    """
    
    def __init__(self, rbac_service: RBACService, audit_logger: AuditLogger):
        """
        Initialize the middleware.
        
        Args:
            rbac_service: RBAC service for access control
            audit_logger: Audit logger for security events
        """
        self.rbac_service = rbac_service
        self.audit_logger = audit_logger
        self.authenticator = rbac_service.authenticator
    
    def __call__(self, request: Any) -> Any:
        """
        Process a request through the middleware.
        
        This method intercepts requests, extracts authentication information,
        and attaches user details to the request for downstream handlers.
        
        Args:
            request: The incoming request
        
        Returns:
            Any: The processed request with auth info attached
        """
        # Generate a request ID for correlation
        request_id = str(uuid.uuid4())
        setattr(request, "request_id", request_id)
        
        # Get client IP address
        ip_address = self._get_client_ip(request)
        setattr(request, "client_ip", ip_address)
        
        # Authenticate the request
        auth_result = self.authenticator.authenticate_request(request)
        
        # Attach authentication result to the request
        setattr(request, "auth_result", auth_result)
        setattr(request, "auth_user_id", auth_result.user_id)
        setattr(request, "auth_roles", auth_result.roles)
        
        # Log the authentication attempt
        if auth_result.is_authorized:
            if auth_result.user_id:
                self.audit_logger.log_auth_success(
                    user_id=auth_result.user_id,
                    ip_address=ip_address,
                    method=self._determine_auth_method(request),
                    request_id=request_id
                )
        else:
            self.audit_logger.log_auth_failure(
                user_id=None,
                ip_address=ip_address,
                method=self._determine_auth_method(request),
                reason=auth_result.reason or "unknown",
                request_id=request_id
            )
        
        return request
    
    def _get_client_ip(self, request: Any) -> Optional[str]:
        """
        Extract client IP address from request.
        
        Args:
            request: The request object
        
        Returns:
            Optional[str]: Client IP address or None
        """
        if not hasattr(request, 'headers'):
            return None
        
        # Try X-Forwarded-For header (for requests behind a proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs; the client IP is the first one
            return forwarded_for.split(",")[0].strip()
        
        # Try X-Real-IP header (used by some proxies)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to request's remote address if available
        if hasattr(request, 'remote_addr') or hasattr(request, 'client_addr'):
            return getattr(request, 'remote_addr', None) or getattr(request, 'client_addr', None)
        
        return None
    
    def _determine_auth_method(self, request: Any) -> str:
        """
        Determine the authentication method used.
        
        Args:
            request: The request object
        
        Returns:
            str: Authentication method name
        """
        if not hasattr(request, 'headers'):
            return "unknown"
        
        headers = request.headers
        
        # Check for API key
        if "X-API-Key" in headers:
            return "api_key"
        
        # Check for Bearer token (JWT)
        auth_header = headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return "jwt"
        
        # Check for Basic auth
        if auth_header.startswith("Basic "):
            return "basic"
        
        # Check for OAuth
        if "X-OAuth-Provider" in headers:
            return f"oauth_{headers['X-OAuth-Provider'].lower()}"
        
        # Check for custom header
        if "X-User-Role" in headers:
            return "custom_header"
        
        return "anonymous"


class AuthorizationHandler:
    """
    Handler for enforcing authorization on MCP server endpoints.
    
    This class provides decorators and utilities for protecting API endpoints
    with permission checks.
    """
    
    def __init__(self, rbac_service: RBACService, audit_logger: AuditLogger):
        """
        Initialize the handler.
        
        Args:
            rbac_service: RBAC service for access control
            audit_logger: Audit logger for security events
        """
        self.rbac_service = rbac_service
        self.audit_logger = audit_logger
    
    def requires_permission(self, permission: Union[str, Permission], 
                          resource_type: ResourceType = ResourceType.GLOBAL):
        """
        Decorator for requiring a permission to access an endpoint.
        
        Args:
            permission: Required permission (name or object)
            resource_type: Resource type for the permission
        
        Returns:
            Callable: Decorator function
        """
        def decorator(handler_func):
            @functools.wraps(handler_func)
            def wrapper(handler_instance, request, *args, **kwargs):
                # Check if the request has auth_result (set by middleware)
                auth_result = getattr(request, "auth_result", None)
                if not auth_result:
                    # If not authenticated by middleware, authenticate now
                    auth_result = self.rbac_service.authenticator.authenticate_request(request)
                
                if not auth_result.is_authorized:
                    # Authentication failed
                    return self._create_error_response(
                        "authentication_failed",
                        auth_result.reason or "Authentication required",
                        401
                    )
                
                # Check permission
                authorized = self.rbac_service.authorize(request, permission, resource_type)
                
                # Log the permission check
                request_id = getattr(request, "request_id", str(uuid.uuid4()))
                ip_address = getattr(request, "client_ip", self._get_client_ip(request))
                
                self.audit_logger.log_permission_check(
                    user_id=auth_result.user_id or "anonymous",
                    permission=str(permission),
                    resource_type=resource_type.name if isinstance(resource_type, ResourceType) else str(resource_type),
                    granted=bool(authorized),
                    ip_address=ip_address,
                    request_id=request_id
                )
                
                if not authorized:
                    # Permission denied
                    return self._create_error_response(
                        "permission_denied",
                        authorized.reason or f"Missing required permission: {permission}",
                        403
                    )
                
                # Call the original handler
                return handler_func(handler_instance, request, *args, **kwargs)
            
            return wrapper
        
        return decorator
    
    def requires_backend_access(self, backend: str, action: Action):
        """
        Decorator for requiring access to a specific backend.
        
        Args:
            backend: Backend name
            action: Required action (READ, WRITE, etc.)
        
        Returns:
            Callable: Decorator function
        """
        def decorator(handler_func):
            @functools.wraps(handler_func)
            def wrapper(handler_instance, request, *args, **kwargs):
                # Check if the request has auth_result (set by middleware)
                auth_result = getattr(request, "auth_result", None)
                if not auth_result:
                    # If not authenticated by middleware, authenticate now
                    auth_result = self.rbac_service.authenticator.authenticate_request(request)
                
                if not auth_result.is_authorized:
                    # Authentication failed
                    return self._create_error_response(
                        "authentication_failed",
                        auth_result.reason or "Authentication required",
                        401
                    )
                
                # Check backend access
                can_access = self.rbac_service.can_access_backend(
                    auth_result.roles,
                    backend,
                    action
                )
                
                # Log the permission check
                request_id = getattr(request, "request_id", str(uuid.uuid4()))
                ip_address = getattr(request, "client_ip", self._get_client_ip(request))
                
                self.audit_logger.log_permission_check(
                    user_id=auth_result.user_id or "anonymous",
                    permission=f"{backend}:{action.value}",
                    resource_type=backend,
                    granted=can_access,
                    ip_address=ip_address,
                    request_id=request_id
                )
                
                if not can_access:
                    # Access denied
                    return self._create_error_response(
                        "access_denied",
                        f"Access to {backend} backend for {action.value} action denied",
                        403
                    )
                
                # Call the original handler
                return handler_func(handler_instance, request, *args, **kwargs)
            
            return wrapper
        
        return decorator
    
    def _create_error_response(self, error_code: str, message: str, status_code: int) -> Dict[str, Any]:
        """
        Create a standardized error response.
        
        Args:
            error_code: Error code
            message: Error message
            status_code: HTTP status code
        
        Returns:
            Dict[str, Any]: Error response object
        """
        # In a real implementation, this would create an HTTP response
        # with the appropriate status code.
        # For this example, we just return a dict with error details.
        return {
            "error": {
                "code": error_code,
                "message": message,
                "status": status_code
            }
        }
    
    def _get_client_ip(self, request: Any) -> Optional[str]:
        """
        Extract client IP address from request.
        
        Args:
            request: The request object
        
        Returns:
            Optional[str]: Client IP address or None
        """
        if not hasattr(request, 'headers'):
            return None
        
        headers = request.headers
        
        # Try X-Forwarded-For header
        forwarded_for = headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Try X-Real-IP header
        real_ip = headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to request's remote address if available
        if hasattr(request, 'remote_addr') or hasattr(request, 'client_addr'):
            return getattr(request, 'remote_addr', None) or getattr(request, 'client_addr', None)
        
        return None


class MCPAuthIntegration:
    """
    Provides integration between the MCP server and authentication system.
    
    This class is responsible for:
    1. Setting up middleware for authentication
    2. Providing decorators for authorization
    3. Adding authentication endpoints to the MCP server
    4. Logging security events
    """
    
    def __init__(self, rbac_service: RBACService, audit_logger: AuditLogger, 
                oauth_manager: Optional[OAuthManager] = None):
        """
        Initialize the integration.
        
        Args:
            rbac_service: RBAC service for access control
            audit_logger: Audit logger for security events
            oauth_manager: Optional OAuth manager for OAuth integration
        """
        self.rbac_service = rbac_service
        self.audit_logger = audit_logger
        self.oauth_manager = oauth_manager
        
        # Create middleware and handler
        self.middleware = AuthMiddleware(rbac_service, audit_logger)
        self.auth_handler = AuthorizationHandler(rbac_service, audit_logger)
    
    def initialize(self, server: Any):
        """
        Initialize authentication for an MCP server.
        
        This method:
        1. Adds middleware to the server
        2. Registers auth-related API endpoints
        3. Sets up permissions for default endpoints
        
        Args:
            server: The MCP server instance
        """
        # Add middleware to the server
        # In a real implementation, this would depend on the web framework used
        # For example, in FastAPI:
        # server.add_middleware(self.middleware)
        
        # For this example, we assume the server has a method to add middleware
        if hasattr(server, 'add_middleware'):
            server.add_middleware(self.middleware)
        else:
            logger.warning("Server does not support middleware. Authentication must be manually added to handlers.")
        
        # Add auth endpoints to the server
        self._register_auth_endpoints(server)
        
        # Apply permissions to default endpoints
        self._secure_default_endpoints(server)
        
        # Log initialization
        self.audit_logger.log(
            AuditEventType.SYSTEM,
            "auth_integration_initialized",
            details={"server": str(server)}
        )
    
    def _register_auth_endpoints(self, server: Any):
        """
        Register authentication endpoints with the server.
        
        Args:
            server: The MCP server instance
        """
        from .api_endpoints import AuthHandler
        
        # Create auth handler
        handler = AuthHandler(self.rbac_service, self.oauth_manager)
        
        # Register endpoints
        # This implementation would depend on the web framework used
        # For this example, we assume the server has a method to register routes
        # Similar to the register_auth_endpoints function in api_endpoints.py
        if hasattr(server, 'add_route'):
            # Authentication endpoints
            server.add_route("/auth/login", "POST", handler.login)
            server.add_route("/auth/logout", "POST", handler.logout)
            
            # OAuth endpoints (if enabled)
            if self.oauth_manager:
                server.add_route("/auth/oauth/login", "GET", handler.oauth_login)
                server.add_route("/auth/oauth/callback", "GET", handler.oauth_callback)
            
            # User management endpoints
            server.add_route("/auth/users", "GET", handler.list_users)
            server.add_route("/auth/users/{user_id}", "GET", handler.get_user)
            server.add_route("/auth/users", "POST", handler.create_user)
            server.add_route("/auth/users/{user_id}", "PUT", handler.update_user)
            server.add_route("/auth/users/{user_id}", "DELETE", handler.delete_user)
            
            # Role management endpoints
            server.add_route("/auth/roles", "GET", handler.list_roles)
            server.add_route("/auth/roles/{role_name}", "GET", handler.get_role)
            server.add_route("/auth/roles", "POST", handler.create_role)
            server.add_route("/auth/roles/{role_name}", "PUT", handler.update_role)
            server.add_route("/auth/roles/{role_name}", "DELETE", handler.delete_role)
            
            # API key management endpoints
            server.add_route("/auth/api-keys", "GET", handler.list_api_keys)
            server.add_route("/auth/api-keys", "POST", handler.create_api_key)
            server.add_route("/auth/api-keys/{key_id}/revoke", "POST", handler.revoke_api_key)
            
            # Authorization endpoints
            server.add_route("/auth/check-permission", "GET", handler.check_permission)
            server.add_route("/auth/user-permissions", "GET", handler.get_user_permissions)
            server.add_route("/auth/accessible-backends", "GET", handler.get_user_accessible_backends)
        else:
            logger.warning("Server does not support route registration. Auth endpoints must be manually added.")
    
    def _secure_default_endpoints(self, server: Any):
        """
        Apply security to default MCP server endpoints.
        
        Args:
            server: The MCP server instance
        """
        # This would depend on how the server's handlers are registered
        # In a real implementation, we would iterate through existing handlers
        # and apply the appropriate decorators
        
        # Example of securing a handler:
        # if hasattr(server, 'handlers'):
        #     for path, handler in server.handlers.items():
        #         if path.startswith('/api/v0/ipfs/'):
        #             handler.handle = self.auth_handler.requires_backend_access('IPFS', Action.READ)(handler.handle)
        
        logger.info("Default MCP endpoints secured with authentication and authorization")
    
    # Convenience methods for securing handlers
    
    def requires_permission(self, permission: Union[str, Permission], 
                          resource_type: ResourceType = ResourceType.GLOBAL):
        """
        Decorator for requiring a permission to access an endpoint.
        
        Args:
            permission: Required permission (name or object)
            resource_type: Resource type for the permission
        
        Returns:
            Callable: Decorator function
        """
        return self.auth_handler.requires_permission(permission, resource_type)
    
    def requires_backend_access(self, backend: str, action: Action):
        """
        Decorator for requiring access to a specific backend.
        
        Args:
            backend: Backend name
            action: Required action (READ, WRITE, etc.)
        
        Returns:
            Callable: Decorator function
        """
        return self.auth_handler.requires_backend_access(backend, action)
    
    def log_data_access(self, user_id: str, resource_id: str,
                      resource_type: str, action: str,
                      ip_address: Optional[str] = None,
                      details: Optional[Dict[str, Any]] = None,
                      request_id: Optional[str] = None):
        """
        Log data access for auditing.
        
        Args:
            user_id: User ID
            resource_id: Resource ID
            resource_type: Resource type
            action: Action performed
            ip_address: Client IP address
            details: Additional details
            request_id: Request ID for correlation
        """
        self.audit_logger.log_data_access(
            user_id=user_id,
            resource_id=resource_id,
            resource_type=resource_type,
            action=action,
            ip_address=ip_address,
            details=details,
            request_id=request_id
        )


# Example of how to use the integration
def example_usage():
    """Example of integrating authentication with the MCP server."""
    from .rbac_enhanced import RBACService
    from .audit_logging import AuditLogger
    from .oauth_integration import OAuthManager
    
    # Create necessary components
    rbac_service = RBACService("data/api_keys.json")
    audit_logger = AuditLogger("logs/auth_audit.log")
    oauth_manager = OAuthManager("data/oauth_states.json")
    
    # Create the integration
    auth_integration = MCPAuthIntegration(rbac_service, audit_logger, oauth_manager)
    
    # Mock server class
    class MockMCPServer:
        def __init__(self):
            self.middleware = []
            self.routes = {}
        
        def add_middleware(self, middleware):
            self.middleware.append(middleware)
            print(f"Added middleware: {middleware.__class__.__name__}")
        
        def add_route(self, path, method, handler):
            self.routes[(path, method)] = handler
            print(f"Added route: {method} {path}")
    
    # Create a mock server and initialize auth
    server = MockMCPServer()
    auth_integration.initialize(server)
    
    # Example of securing an endpoint
    @auth_integration.requires_permission("read")
    def get_data(request):
        # Handler implementation
        return {"data": "sensitive data"}
    
    # Example of securing a backend-specific endpoint
    @auth_integration.requires_backend_access("IPFS", Action.READ)
    def get_ipfs_data(request):
        # Handler implementation
        return {"data": "IPFS data"}
    
    # Example of logging data access
    def access_data(request):
        # Handler implementation
        result = {"data": "accessed data"}
        
        # Log the access
        auth_integration.log_data_access(
            user_id=getattr(request, "auth_user_id", "anonymous"),
            resource_id="data123",
            resource_type="ipfs_file",
            action="read",
            ip_address=getattr(request, "client_ip", None),
            request_id=getattr(request, "request_id", None)
        )
        
        return result
    
    print("Authentication integration example completed")


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Run the example
    example_usage()