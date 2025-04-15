"""
Authentication and Authorization middleware for MCP server.

This module provides FastAPI middleware for implementing authentication
and authorization as specified in the MCP roadmap.
"""

import logging
import re
from typing import List, Callable
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.security import HTTPBearer
from fastapi.security.api_key import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from .service import AuthenticationService

# Configure logging
logger = logging.getLogger(__name__)

# Security schemes
oauth2_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware for handling authentication and authorization.

    This middleware checks for authentication tokens in requests and
    verifies permissions for protected routes.
    """
    def __init__(
        self,
        app: FastAPI,
        auth_service: AuthenticationService,
        exclude_paths: List[str] = None,
        require_auth: bool = False,
    ):
        """
        Initialize the auth middleware.

        Args:
            app: FastAPI application
            auth_service: Authentication service
            exclude_paths: List of path patterns to exclude from authentication
            require_auth: Whether to require authentication for all routes by default
        """
        super().__init__(app)
        self.auth_service = auth_service
        self.require_auth = require_auth

        # Path patterns to exclude from authentication
        self.exclude_paths = exclude_paths or [
            r"^/docs($|/)",
            r"^/redoc($|/)",
            r"^/openapi.json$",
            r"^/api/v0/auth/login$",
            r"^/api/v0/auth/register$",
            r"^/api/v0/auth/token$",
            r"^/api/v0/status$",
            r"^/ping$",
            r"^/health$",
            r"^/metrics$",
        ]

        # Compile exclude path patterns
        self.exclude_patterns = [re.compile(pattern) for pattern in self.exclude_paths]

        # Route permissions registry
        self.route_permissions = {}
        self.route_roles = {}

    def register_route_permission(self, path: str, method: str, required_permission: str) -> None:
        """
        Register a permission requirement for a route.

        Args:
            path: Route path
            method: HTTP method
            required_permission: Required permission
        """
        key = f"{method.upper()}:{path}"
        self.route_permissions[key] = required_permission
        logger.debug(f"Registered permission {required_permission} for {key}")

    def register_route_role(self, path: str, method: str, required_role: str) -> None:
        """
        Register a role requirement for a route.

        Args:
            path: Route path
            method: HTTP method
            required_role: Required role
        """
        key = f"{method.upper()}:{path}"
        self.route_roles[key] = required_role
        logger.debug(f"Registered role {required_role} for {key}")

    def exclude_path(self, path: str) -> None:
        """
        Add a path pattern to exclude from authentication.

        Args:
            path: Path pattern
        """
        self.exclude_paths.append(path)
        self.exclude_patterns.append(re.compile(path))
        logger.debug(f"Added {path} to authentication exclusion list")

    def _is_path_excluded(self, path: str) -> bool:
        """
        Check if a path is excluded from authentication.

        Args:
            path: Request path

        Returns:
            True if path is excluded
        """
        for pattern in self.exclude_patterns:
            if pattern.match(path):
                return True
        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process a request through the middleware.

        Args:
            request: Incoming request
            call_next: Next middleware

        Returns:
            Response
        """
        # Check if path is excluded from authentication
        if self._is_path_excluded(request.url.path):
            return await call_next(request)

        # Extract token from request
        token = None
        token_type = None

        # Check for token in Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]
                token_type = "bearer"

        # Check for API key in X-API-Key header
        api_key = request.headers.get("X-API-Key")
        if not token and api_key:
            token = api_key
            token_type = "api_key"

        # Check for token in cookie
        if not token:
            token = request.cookies.get("access_token")
            if token:
                token_type = "cookie"

        # Create auth context to pass to route handlers
        auth_context = {
            "authenticated": False,
            "user_id": None,
            "roles": [],
            "permissions": [],
            "token_type": None,
            "token_data": None,
        }

        # Verify token if present
        if token:
            if token_type == "api_key":
                # Verify API key
                valid, api_key_obj, error = await self.auth_service.verify_api_key(
                    token, ip_address=request.client.host if request.client else None
                )

                if valid and api_key_obj:
                    # Generate JWT token from API key
                    jwt_token = await self.auth_service.create_access_token_from_api_key(
                        api_key_obj
                    )

                    # Verify the JWT token
                    valid, token_data, _ = await self.auth_service.verify_token(jwt_token)

                    if valid and token_data:
                        # Set auth context
                        auth_context["authenticated"] = True
                        auth_context["user_id"] = token_data.sub
                        auth_context["roles"] = token_data.roles
                        auth_context["permissions"] = token_data.permissions
                        auth_context["token_type"] = "api_key"
                        auth_context["token_data"] = token_data
            else:
                # Verify JWT token
                valid, token_data, error = await self.auth_service.verify_token(token)

                if valid and token_data:
                    # Set auth context
                    auth_context["authenticated"] = True
                    auth_context["user_id"] = token_data.sub
                    auth_context["roles"] = token_data.roles
                    auth_context["permissions"] = token_data.permissions
                    auth_context["token_type"] = token_type
                    auth_context["token_data"] = token_data

        # Check if authentication is required for this path
        route_key = f"{request.method}:{request.url.path}"
        requires_permission = route_key in self.route_permissions
        requires_role = route_key in self.route_roles

        if (self.require_auth or requires_permission or requires_role) and not auth_context[
            "authenticated"
        ]:
            # Authentication required but not provided or invalid
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Not authenticated"},
            )

        # Check permissions if required
        if requires_permission:
            required_permission = self.route_permissions[route_key]
            if required_permission not in auth_context["permissions"]:
                # Check for wildcard permissions
                permission_parts = required_permission.split(":")
                if len(permission_parts) > 1:
                    resource = permission_parts[0]
                    wildcard_perm = f"{resource}:*"
                    admin_perm = "admin:*"

                    if (
                        wildcard_perm not in auth_context["permissions"]
                        and admin_perm not in auth_context["permissions"]
                    ):
                        return JSONResponse(
                            status_code=status.HTTP_403_FORBIDDEN,
                            content={
                                "detail": f"Permission denied: {required_permission} required"
                            },
                        )
                else:
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": f"Permission denied: {required_permission} required"},
                    )

        # Check roles if required
        if requires_role:
            required_role = self.route_roles[route_key]
            if required_role not in auth_context["roles"] and "admin" not in auth_context["roles"]:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": f"Role denied: {required_role} required"},
                )

        # Add auth context to request state
        request.state.auth = auth_context

        # Process the request
        response = await call_next(request)

        return response


def get_current_user(request: Request):
    """
    FastAPI dependency to get the current authenticated user.

    Args:
        request: Request object

    Returns:
        User ID or raises HTTPException if not authenticated
    """
    auth = getattr(request.state, "auth", None)
    if not auth or not auth.get("authenticated"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    return auth.get("user_id")


def get_current_user_optional(request: Request):
    """
    FastAPI dependency to get the current user if authenticated.

    Args:
        request: Request object

    Returns:
        User ID or None if not authenticated
    """
    auth = getattr(request.state, "auth", None)
    if not auth or not auth.get("authenticated"):
        return None

    return auth.get("user_id")


def require_permission(permission: str):
    """
    FastAPI dependency to require a specific permission.

    Args:
        permission: Required permission

    Returns:
        Dependency function
    """
    def _require_permission(request: Request):
        auth = getattr(request.state, "auth", None)
        if not auth or not auth.get("authenticated"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
            )

        permissions = auth.get("permissions", [])

        # Check for admin permission
        if "admin:*" in permissions:
            return True

        # Check for exact permission
        if permission in permissions:
            return True

        # Check for wildcard permissions
        permission_parts = permission.split(":")
        if len(permission_parts) > 1:
            resource = permission_parts[0]
            wildcard_perm = f"{resource}:*"

            if wildcard_perm in permissions:
                return True

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {permission} required",
        )

    return _require_permission


def require_role(role: str):
    """
    FastAPI dependency to require a specific role.

    Args:
        role: Required role

    Returns:
        Dependency function
    """
    def _require_role(request: Request):
        auth = getattr(request.state, "auth", None)
        if not auth or not auth.get("authenticated"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
            )

        roles = auth.get("roles", [])

        # Check for admin role
        if "admin" in roles:
            return True

        # Check for specific role
        if role in roles:
            return True

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role denied: {role} required",
        )

    return _require_role


def get_auth_context(request: Request):
    """
    FastAPI dependency to get the complete auth context.

    Args:
        request: Request object

    Returns:
        Auth context or raises HTTPException if not authenticated
    """
    auth = getattr(request.state, "auth", None)
    if not auth or not auth.get("authenticated"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    return auth
