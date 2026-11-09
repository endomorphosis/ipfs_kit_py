"""
Authentication and Authorization Extension for MCP Server

This extension integrates authentication and authorization features with the MCP server,
providing user management, API key generation, and role-based access control.
"""

import os
import sys
import time
import logging
import importlib.util
from typing import Dict, Any, Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Form,
    Query)
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.security.api_key import APIKeyHeader, APIKeyQuery



# Configure logging
logger = logging.getLogger(__name__)

# Import our auth manager
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from mcp_auth import AuthManager, AuthError

    AUTH_MANAGER_AVAILABLE = True
    logger.info("Auth Manager successfully imported")
except ImportError as e:
    AUTH_MANAGER_AVAILABLE = False
    logger.error(f"Error importing Auth Manager: {e}")

# Optional dependencies for OAuth
# Check if httpx is available without importing it globally


OAUTH_AVAILABLE = importlib.util.find_spec("httpx") is not None
if not OAUTH_AVAILABLE:
    logger.warning("OAuth dependencies not available. Install with: pip install httpx")
else:
    logger.info("OAuth dependencies available")
    # Note: The original code had a logic error here, setting OAUTH_AVAILABLE to False
    # after logging it was available. Correcting this.

# Initialize auth manager
auth_manager = None
if AUTH_MANAGER_AVAILABLE:
    try:
        # Get environment variables for config
        jwt_secret = os.environ.get("MCP_JWT_SECRET")
        default_admin_password = os.environ.get("MCP_DEFAULT_ADMIN_PASSWORD")

        # Configure auth manager
        auth_config = {
            "auth_enabled": True,
            "jwt_secret": jwt_secret,
            "default_admin_password": default_admin_password,
            "allow_anonymous_access": True,
            "anon_allowed_paths": [
                "/api/v0/health",
                "/api/v0/metrics/status",
                "/api/v0/ipfs/version",
            ],
        }

        auth_manager = AuthManager(auth_config)
        logger.info("Auth Manager initialized")
    except Exception as e:
        logger.error(f"Error initializing Auth Manager: {e}")

# Security schemes
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v0/auth/token", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)


# Dependency for authentication
async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    api_key_header_value: Optional[str] = Depends(api_key_header),
    api_key_query_value: Optional[str] = Depends(api_key_query),
):
    """
    Dependency to get the current authenticated user.

    Args:
        request: FastAPI request object
        token: Optional JWT token from Authorization header
        api_key_header_value: Optional API key from X-API-Key header
        api_key_query_value: Optional API key from api_key query parameter

    Returns:
        User information dict

    Raises:
        HTTPException: If authentication fails
    """
    if not AUTH_MANAGER_AVAILABLE or auth_manager is None:
        return None

    # Get request info for logging
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    # Check if path requires authentication
    path = request.url.path

    # Try API key authentication first
    api_key = api_key_header_value or api_key_query_value
    if api_key:
        try:
            user_info = auth_manager.authenticate_api_key(
                api_key, ip_address=ip_address, user_agent=user_agent
            )
            return user_info
        except AuthError as e:
            # If path allows anonymous access, return None
            if auth_manager.config["allow_anonymous_access"]:
                for allowed_path in auth_manager.config["anon_allowed_paths"]:
                    if path.startswith(allowed_path):
                        return None

            raise HTTPException(status_code=401, detail=str(e))

    # Try JWT token authentication
    if token:
        try:
            # Validate token
            payload = auth_manager.validate_token(token)

            # Get user ID from token
            user_id = payload.get("sub")
            if not user_id:
                raise AuthError("Invalid token")

            # Get user info
            user_info = auth_manager.get_user_info(int(user_id))

            # Add token to user info for convenience
            user_info["access_token"] = token

            return user_info
        except AuthError as e:
            # If path allows anonymous access, return None
            if auth_manager.config["allow_anonymous_access"]:
                for allowed_path in auth_manager.config["anon_allowed_paths"]:
                    if path.startswith(allowed_path):
                        return None

            raise HTTPException(status_code=401, detail=str(e))

    # If no authentication provided but path allows anonymous access
    if auth_manager.config["allow_anonymous_access"]:
        for allowed_path in auth_manager.config["anon_allowed_paths"]:
            if path.startswith(allowed_path):
                return None

    # Otherwise, require authentication
    raise HTTPException(
        status_code=401,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


# Dependency for requiring authenticated user
async def require_auth(user: Optional[Dict[str, Any]] = Depends(get_current_user)):
    """
    Dependency to require authentication.

    Args:
        user: User information from get_current_user

    Returns:
        User information dict

    Raises:
        HTTPException: If not authenticated
    """
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# Dependency for requiring admin role
async def require_admin(user: Dict[str, Any] = Depends(require_auth)):
    """
    Dependency to require admin role.

    Args:
        user: User information from require_auth

    Returns:
        User information dict

    Raises:
        HTTPException: If not an admin
    """
    if not AUTH_MANAGER_AVAILABLE or auth_manager is None:
        raise HTTPException(status_code=501, detail="Authentication system not available")

    if not auth_manager.has_permission(user["id"], "auth:admin"):
        raise HTTPException(status_code=403, detail="Admin permission required")

    return user


# Dependency for checking permission
def require_permission(permission: str):
    """
    Factory for dependency to require specific permission.

    Args:
        permission: Required permission

    Returns:
        Dependency function
    """
    async def check_permission(user: Dict[str, Any] = Depends(require_auth)):
        if not AUTH_MANAGER_AVAILABLE or auth_manager is None:
            raise HTTPException(status_code=501, detail="Authentication system not available")

        if not auth_manager.has_permission(user["id"], permission):
            raise HTTPException(status_code=403, detail=f"Permission '{permission}' required")

        return user

    return check_permission


def create_auth_router(api_prefix: str) -> APIRouter:
    """
    Create a FastAPI router with authentication endpoints.

    Args:
        api_prefix: The API prefix for the endpoints

    Returns:
        FastAPI router
    """
    router = APIRouter(prefix=f"{api_prefix}/auth")

    @router.get("/status")
    async def auth_status(user: Optional[Dict[str, Any]] = Depends(get_current_user)):
        """Get authentication system status."""
        if not AUTH_MANAGER_AVAILABLE or auth_manager is None:
            return {
                "success": False,
                "status": "unavailable",
                "error": "Authentication system is not available",
            }

        return {
            "success": True,
            "status": "available",
            "authenticated": user is not None,
            "user": user["username"] if user else None,
            "allow_anonymous_access": auth_manager.config["allow_anonymous_access"],
        }

    @router.post("/token")
    async def login_for_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
        """
        OAuth2 compatible token endpoint.

        Args:
            request: FastAPI request
            form_data: OAuth2 form data
        """
        if not AUTH_MANAGER_AVAILABLE or auth_manager is None:
            raise HTTPException(status_code=501, detail="Authentication system not available")

        try:
            # Get request info for logging
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("User-Agent")

            # Authenticate user
            user_info = auth_manager.authenticate_user(
                form_data.username,
                form_data.password,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            return {
                "access_token": user_info["access_token"],
                "refresh_token": user_info["refresh_token"],
                "token_type": user_info["token_type"],
                "expires_in": user_info["expires_in"],
            }
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e))

    @router.post("/refresh")
    async def refresh_token(
        request: Request,
        refresh_token: str = Form(...),
    ):
        """
        Refresh an access token.

        Args:
            request: FastAPI request
            refresh_token: Refresh token
        """
        if not AUTH_MANAGER_AVAILABLE or auth_manager is None:
            raise HTTPException(status_code=501, detail="Authentication system not available")

        try:
            # Get request info for logging
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("User-Agent")

            # Refresh token
            token_info = auth_manager.refresh_token(
                refresh_token, ip_address=ip_address, user_agent=user_agent
            )

            return token_info
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e))

    @router.get("/me")
    async def get_user_me(user: Dict[str, Any] = Depends(require_auth)):
        """Get current authenticated user information."""
        return {"success": True, "user": user}

    @router.post("/apikey")
    async def create_api_key(
        name: str = Form(...),
        expires_in_days: Optional[int] = Form(365),
        user: Dict[str, Any] = Depends(require_auth),
    ):
        """
        Create a new API key for the current user.

        Args:
            name: API key name
            expires_in_days: Days until expiration (None for no expiration)
            user: Current user
        """
        if not AUTH_MANAGER_AVAILABLE or auth_manager is None:
            raise HTTPException(status_code=501, detail="Authentication system not available")

        try:
            # Create API key
            api_key_info = auth_manager.create_api_key(
                user["id"], name, expires_in_days=expires_in_days
            )

            return {"success": True, "api_key": api_key_info}
        except AuthError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/apikeys")
    async def list_api_keys(user: Dict[str, Any] = Depends(require_auth)):
        """List API keys for the current user."""
        if not AUTH_MANAGER_AVAILABLE or auth_manager is None:
            raise HTTPException(status_code=501, detail="Authentication system not available")

        api_keys = auth_manager.list_api_keys(user["id"])

        return {"success": True, "api_keys": api_keys}

    @router.post("/apikey/revoke")
    async def revoke_api_key(key_id: int = Form(...), user: Dict[str, Any] = Depends(require_auth)):
        """
        Revoke an API key.

        Args:
            key_id: API key ID
            user: Current user
        """
        if not AUTH_MANAGER_AVAILABLE or auth_manager is None:
            raise HTTPException(status_code=501, detail="Authentication system not available")

        try:
            # Revoke API key
            result = auth_manager.revoke_api_key(key_id, user["id"])

            return result
        except AuthError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/password")
    async def change_password(
        old_password: str = Form(...),
        new_password: str = Form(...),
        user: Dict[str, Any] = Depends(require_auth),
    ):
        """
        Change user password.

        Args:
            old_password: Current password
            new_password: New password
            user: Current user
        """
        if not AUTH_MANAGER_AVAILABLE or auth_manager is None:
            raise HTTPException(status_code=501, detail="Authentication system not available")

        try:
            # Change password
            result = auth_manager.change_password(user["id"], old_password, new_password)

            return result
        except AuthError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Admin endpoints

    @router.post("/users", dependencies=[Depends(require_admin)])
    async def create_user(
        username: str = Form(...),
        password: str = Form(...),
        full_name: Optional[str] = Form(None),
        email: Optional[str] = Form(None),
        role_name: str = Form("user"),
    ):
        """
        Create a new user (admin only).

        Args:
            username: Username
            password: Password
            full_name: User's full name
            email: User's email
            role_name: Role name to assign
        """
        if not AUTH_MANAGER_AVAILABLE or auth_manager is None:
            raise HTTPException(status_code=501, detail="Authentication system not available")

        try:
            # Create user
            user_info = auth_manager.create_user(
                username,
                password,
                full_name=full_name,
                email=email,
                role_name=role_name,
            )

            return {"success": True, "user": user_info}
        except AuthError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/users", dependencies=[Depends(require_admin)])
    async def list_users(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        role: Optional[str] = Query(None),
    ):
        """
        List users with pagination (admin only).

        Args:
            page: Page number
            page_size: Number of users per page
            role: Optional role filter
        """
        if not AUTH_MANAGER_AVAILABLE or auth_manager is None:
            raise HTTPException(status_code=501, detail="Authentication system not available")

        users_result = auth_manager.list_users(page=page, page_size=page_size, role_filter=role)

        return {"success": True, **users_result}

    @router.get("/users/{user_id}", dependencies=[Depends(require_admin)])
    async def get_user(user_id: int):
        """
        Get user information (admin only).

        Args:
            user_id: User ID
        """
        if not AUTH_MANAGER_AVAILABLE or auth_manager is None:
            raise HTTPException(status_code=501, detail="Authentication system not available")

        try:
            user_info = auth_manager.get_user_info(user_id)

            return {"success": True, "user": user_info}
        except AuthError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @router.post("/users/{user_id}", dependencies=[Depends(require_admin)])
    async def update_user(
        user_id: int,
        full_name: Optional[str] = Form(None),
        email: Optional[str] = Form(None),
        role_name: Optional[str] = Form(None),
        active: Optional[bool] = Form(None),
    ):
        """
        Update user information (admin only).

        Args:
            user_id: User ID
            full_name: Optional new full name
            email: Optional new email
            role_name: Optional new role name
            active: Optional new active status
        """
        if not AUTH_MANAGER_AVAILABLE or auth_manager is None:
            raise HTTPException(status_code=501, detail="Authentication system not available")

        try:
            user_info = auth_manager.update_user(
                user_id,
                full_name=full_name,
                email=email,
                role_name=role_name,
                active=active,
            )

            return {"success": True, "user": user_info}
        except AuthError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/users/{user_id}/reset-password", dependencies=[Depends(require_admin)])
    async def reset_password(
        user_id: int,
        new_password: str = Form(...),
        admin_user: Dict[str, Any] = Depends(require_admin),
    ):
        """
        Reset a user's password (admin only).

        Args:
            user_id: User ID
            new_password: New password
            admin_user: Admin user
        """
        if not AUTH_MANAGER_AVAILABLE or auth_manager is None:
            raise HTTPException(status_code=501, detail="Authentication system not available")

        try:
            result = auth_manager.reset_password(user_id, new_password, admin_user["id"])

            return result
        except AuthError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/roles", dependencies=[Depends(require_admin)])
    async def list_roles():
        """List all roles with their permissions (admin only)."""
        if not AUTH_MANAGER_AVAILABLE or auth_manager is None:
            raise HTTPException(status_code=501, detail="Authentication system not available")

        roles = auth_manager.list_roles()

        return {"success": True, "roles": roles}

    @router.post("/roles", dependencies=[Depends(require_admin)])
    async def create_role(
        name: str = Form(...),
        description: str = Form(...),
        permissions: str = Form(...),  # Comma-separated list
    ):
        """
        Create a new role (admin only).

        Args:
            name: Role name
            description: Role description
            permissions: Comma-separated list of permissions
        """
        if not AUTH_MANAGER_AVAILABLE or auth_manager is None:
            raise HTTPException(status_code=501, detail="Authentication system not available")

        try:
            # Parse permissions
            permissions_list = [p.strip() for p in permissions.split(",") if p.strip()]

            role_info = auth_manager.create_role(name, description, permissions_list)

            return {"success": True, "role": role_info}
        except AuthError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/roles/{role_id}/permissions", dependencies=[Depends(require_admin)])
    async def update_role_permissions(
        role_id: int,
        permissions: str = Form(...),  # Comma-separated list
    ):
        """
        Update a role's permissions (admin only).

        Args:
            role_id: Role ID
            permissions: Comma-separated list of permissions
        """
        if not AUTH_MANAGER_AVAILABLE or auth_manager is None:
            raise HTTPException(status_code=501, detail="Authentication system not available")

        try:
            # Parse permissions
            permissions_list = [p.strip() for p in permissions.split(",") if p.strip()]

            result = auth_manager.update_role_permissions(role_id, permissions_list)

            return result
        except AuthError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/permissions", dependencies=[Depends(require_admin)])
    async def list_permissions():
        """List all available permissions (admin only)."""
        if not AUTH_MANAGER_AVAILABLE or auth_manager is None:
            raise HTTPException(status_code=501, detail="Authentication system not available")

        return auth_manager.list_permissions()

    @router.get("/logs", dependencies=[Depends(require_admin)])
    async def get_auth_logs(
        user_id: Optional[int] = Query(None),
        username: Optional[str] = Query(None),
        action: Optional[str] = Query(None),
        status: Optional[str] = Query(None),
        days: int = Query(7, ge=1, le=30),
        limit: int = Query(100, ge=1, le=500),
    ):
        """
        Get authentication logs (admin only).

        Args:
            user_id: Optional user ID filter
            username: Optional username filter
            action: Optional action filter
            status: Optional status filter
            days: Number of days to look back
            limit: Maximum number of logs to return
        """
        if not AUTH_MANAGER_AVAILABLE or auth_manager is None:
            raise HTTPException(status_code=501, detail="Authentication system not available")

        # Calculate start time
        start_time = time.time() - (days * 86400)

        logs = auth_manager.get_auth_logs(
            user_id=user_id,
            username=username,
            action=action,
            status=status,
            start_time=start_time,
            limit=limit,
        )

        return {"success": True, "logs": logs, "count": len(logs)}

    return router


def update_auth_status(storage_backends: Dict[str, Any]) -> None:
    """
    Update storage_backends with auth manager status.

    Args:
        storage_backends: Dictionary of storage backends to update
    """
    # Add auth as a component
    storage_backends["auth"] = {
        "available": AUTH_MANAGER_AVAILABLE and auth_manager is not None,
        "simulation": False,
        "features": (
            {
                "user_management": True,
                "api_keys": True,
                "role_based_access": True,
                "oauth": OAUTH_AVAILABLE,
            }
            if AUTH_MANAGER_AVAILABLE and auth_manager is not None
            else {}
        ),
    }

    logger.debug("Updated auth status in storage backends")
