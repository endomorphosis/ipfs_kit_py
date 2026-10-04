"""
Authentication API Routes

Implements FastAPI routes for authentication and authorization:
- User management endpoints
- Login and token endpoints
- API key management
- Permission validation
- OAuth integration

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.
"""

from fastapi import APIRouter, Depends, HTTPException, Security, status, Body, Path, Query, Header
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, APIKeyHeader
from typing import List, Optional, Dict, Any, Union

from ipfs_kit_py.mcp.auth.models import (
    User, UserCreate, UserUpdate, TokenResponse, APIKey, APIKeyCreate,
    Role, Permission, LoginRequest, RefreshTokenRequest, OAuthProvider
)
from ipfs_kit_py.mcp.auth.service import get_instance as get_auth_service


# Create API router
router = APIRouter(prefix="/api/v0/auth", tags=["auth"])

# Setup security schemes
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v0/auth/login/token")
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


# --- Dependency functions ---

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    api_key: Optional[str] = Depends(api_key_scheme)
) -> User:
    """
    Get the current authenticated user from JWT token or API key.
    
    First tries to validate JWT token, then falls back to API key.
    Returns the authenticated user or raises HTTPException.
    """
    auth_service = get_auth_service()
    
    # First try JWT token
    if token:
        success, token_data_or_error = auth_service.verify_jwt(token)
        if success:
            token_data = token_data_or_error
            user_success, user_or_error = auth_service.get_user(token_data.user_id)
            if user_success:
                return user_or_error
    
    # Then try API key
    if api_key:
        success, token_data_or_error = auth_service.verify_api_key(api_key)
        if success:
            token_data = token_data_or_error
            user_success, user_or_error = auth_service.get_user(token_data.user_id)
            if user_success:
                return user_or_error
    
    # Authentication failed
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Get the current user and verify they have admin role.
    Raises HTTPException if user is not an admin.
    """
    if current_user.role != Role.ADMIN and current_user.role != Role.SYSTEM:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    return current_user


async def check_permission(
    permission: Permission,
    current_user: User = Depends(get_current_user)
) -> bool:
    """
    Check if the current user has the specified permission.
    Raises HTTPException if user doesn't have the permission.
    """
    auth_service = get_auth_service()
    
    if not auth_service.check_permission(current_user.id, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission '{permission.value}' required"
        )
    return True


async def check_backend_access(
    backend: str,
    write_access: bool = False,
    current_user: User = Depends(get_current_user)
) -> bool:
    """
    Check if the current user has access to the specified backend.
    Raises HTTPException if user doesn't have access.
    """
    auth_service = get_auth_service()
    
    if not auth_service.check_backend_access(current_user.id, backend, write_access):
        access_type = "write" if write_access else "read"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{access_type.capitalize()} access to backend '{backend}' required"
        )
    return True


# --- Authentication endpoints ---

@router.post("/login", response_model=TokenResponse, summary="Login with username and password")
async def login(login_data: LoginRequest):
    """
    Authenticate a user with username and password.
    
    Returns JWT access token and refresh token on successful authentication.
    """
    auth_service = get_auth_service()
    
    success, result = auth_service.authenticate_user(
        login_data.username,
        login_data.password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result,
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return result


@router.post("/login/token", response_model=TokenResponse, summary="OAuth2 password flow endpoint")
async def login_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate a user using OAuth2 password flow.
    
    This endpoint is used by the OAuth2 password flow and returns JWT access token.
    """
    auth_service = get_auth_service()
    
    success, result = auth_service.authenticate_user(
        form_data.username,
        form_data.password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result,
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return result


@router.post("/refresh", response_model=TokenResponse, summary="Refresh access token")
async def refresh_token(refresh_data: RefreshTokenRequest):
    """
    Refresh an access token using a refresh token.
    
    Returns a new JWT access token and refresh token.
    """
    auth_service = get_auth_service()
    
    success, result = auth_service.refresh_access_token(refresh_data.refresh_token)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result,
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return result


@router.post("/logout", summary="Revoke the current token")
async def logout(token: str = Depends(oauth2_scheme)):
    """
    Logout by revoking the current JWT token.
    
    The token will be added to a blacklist and will no longer be valid.
    """
    auth_service = get_auth_service()
    
    success, message = auth_service.revoke_jwt(token)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return {"message": "Successfully logged out"}


# --- OAuth endpoints ---

@router.get("/oauth/{provider}/login", summary="Get OAuth login URL")
async def get_oauth_login_url(
    provider: OAuthProvider,
    redirect_uri: str = Query(..., description="Redirect URI after authentication"),
    state: Optional[str] = Query(None, description="Optional state parameter for security")
):
    """
    Get the login URL for an OAuth provider.
    
    Returns the URL to redirect the user to for OAuth authentication.
    """
    auth_service = get_auth_service()
    
    success, result = auth_service.get_oauth_login_url(provider, redirect_uri, state)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result
        )
    
    return result


@router.get("/oauth/{provider}/callback", response_model=TokenResponse, summary="Handle OAuth callback")
async def oauth_callback(
    provider: OAuthProvider,
    code: str = Query(..., description="Authorization code from provider"),
    redirect_uri: str = Query(..., description="Redirect URI used in the initial request")
):
    """
    Handle OAuth callback and exchange code for tokens.
    
    Returns JWT access token and refresh token on successful authentication.
    """
    auth_service = get_auth_service()
    
    success, result = auth_service.handle_oauth_callback(provider, code, redirect_uri)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result
        )
    
    return result


# --- User management endpoints ---

@router.post("/users", response_model=User, summary="Create a new user", dependencies=[Depends(get_admin_user)])
async def create_user(user_data: UserCreate):
    """
    Create a new user.
    
    Requires admin privileges.
    """
    auth_service = get_auth_service()
    
    success, result = auth_service.create_user(user_data)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result
        )
    
    return result


@router.get("/users", response_model=List[User], summary="List all users", dependencies=[Depends(get_admin_user)])
async def list_users(
    skip: int = Query(0, description="Number of users to skip"),
    limit: int = Query(100, description="Maximum number of users to return")
):
    """
    List all users with pagination.
    
    Requires admin privileges.
    """
    auth_service = get_auth_service()
    
    users = auth_service.list_users(skip, limit)
    return users


@router.get("/users/me", response_model=User, summary="Get current user information")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get information about the currently authenticated user.
    """
    return current_user


@router.get("/users/{user_id}", response_model=User, summary="Get user by ID")
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get a user by ID.
    
    Regular users can only view their own information.
    Admins can view any user's information.
    """
    # Check if user is trying to access their own info or is an admin
    if current_user.id != user_id and current_user.role != Role.ADMIN and current_user.role != Role.SYSTEM:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this user's information"
        )
    
    auth_service = get_auth_service()
    
    success, result = auth_service.get_user(user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result
        )
    
    return result


@router.put("/users/{user_id}", response_model=User, summary="Update user")
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update a user's information.
    
    Regular users can only update their own information and cannot change their role.
    Admins can update any user's information, including changing roles.
    """
    auth_service = get_auth_service()
    
    # Check permissions
    is_admin = current_user.role == Role.ADMIN or current_user.role == Role.SYSTEM
    is_self = current_user.id == user_id
    
    if not is_admin and not is_self:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user's information"
        )
    
    # Regular users cannot change their own role or custom permissions
    if is_self and not is_admin:
        if user_data.role is not None or user_data.custom_permissions is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Regular users cannot change their role or permissions"
            )
    
    success, result = auth_service.update_user(user_id, user_data)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result
        )
    
    return result


@router.delete("/users/{user_id}", summary="Delete user", dependencies=[Depends(get_admin_user)])
async def delete_user(user_id: str):
    """
    Delete a user.
    
    Requires admin privileges.
    """
    auth_service = get_auth_service()
    
    success, message = auth_service.delete_user(user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return {"message": message}


# --- API Key management endpoints ---

@router.post("/apikeys", response_model=APIKey, summary="Create a new API key")
async def create_api_key(
    api_key_data: APIKeyCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new API key.
    
    Regular users can only create API keys for themselves.
    Admins can create API keys for any user.
    """
    auth_service = get_auth_service()
    
    # Check if user is trying to create an API key for themselves or is an admin
    if current_user.id != api_key_data.user_id and current_user.role != Role.ADMIN and current_user.role != Role.SYSTEM:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create API keys for other users"
        )
    
    success, result = auth_service.create_api_key(api_key_data)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result
        )
    
    return result


@router.get("/apikeys", response_model=List[APIKey], summary="List API keys")
async def list_api_keys(
    user_id: Optional[str] = Query(None, description="User ID to list keys for"),
    current_user: User = Depends(get_current_user)
):
    """
    List API keys for a user.
    
    Regular users can only list their own API keys.
    Admins can list any user's API keys.
    """
    auth_service = get_auth_service()
    
    # If user_id not provided, use current user's ID
    if user_id is None:
        user_id = current_user.id
    
    # Check if user is trying to list their own API keys or is an admin
    if current_user.id != user_id and current_user.role != Role.ADMIN and current_user.role != Role.SYSTEM:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to list API keys for other users"
        )
    
    success, result = auth_service.list_api_keys(user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result
        )
    
    return result


@router.delete("/apikeys/{key_id}", summary="Revoke an API key")
async def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Revoke an API key.
    
    Regular users can only revoke their own API keys.
    Admins can revoke any API key.
    """
    auth_service = get_auth_service()
    
    # Admins can revoke any API key, regular users can only revoke their own
    user_id = None if current_user.role in [Role.ADMIN, Role.SYSTEM] else current_user.id
    
    success, message = auth_service.revoke_api_key(key_id, user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    return {"message": message}


# --- Audit log endpoints ---

@router.get("/logs", summary="Get audit logs", dependencies=[Depends(get_admin_user)])
async def get_audit_logs(
    user_id: Optional[str] = Query(None, description="Filter logs by user ID"),
    event_type: Optional[str] = Query(None, description="Filter logs by event type"),
    from_time: Optional[int] = Query(None, description="Filter logs from timestamp"),
    to_time: Optional[int] = Query(None, description="Filter logs to timestamp"),
    success: Optional[bool] = Query(None, description="Filter logs by success status"),
    limit: int = Query(100, description="Maximum number of logs to return"),
    offset: int = Query(0, description="Number of logs to skip")
):
    """
    Get audit logs with filtering and pagination.
    
    Requires admin privileges.
    """
    auth_service = get_auth_service()
    
    # Build filters
    filters = {}
    if user_id:
        filters["user_id"] = user_id
    if event_type:
        filters["event_type"] = event_type
    if from_time:
        filters["from_time"] = from_time
    if to_time:
        filters["to_time"] = to_time
    if success is not None:
        filters["success"] = success
    
    success, result = auth_service.get_audit_logs(filters, limit, offset)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result
        )
    
    return result


# --- Permission utility endpoints ---

@router.get("/permissions", summary="Get all permissions")
async def get_all_permissions(current_user: User = Depends(get_current_user)):
    """
    Get a list of all available permissions in the system.
    """
    return [p.value for p in Permission]


@router.get("/roles", summary="Get all roles")
async def get_all_roles(current_user: User = Depends(get_current_user)):
    """
    Get a list of all available roles in the system.
    """
    return [r.value for r in Role]


@router.get("/roles/{role}/permissions", summary="Get permissions for a role")
async def get_role_permissions(role: Role, current_user: User = Depends(get_current_user)):
    """
    Get the permissions associated with a specific role.
    """
    from ipfs_kit_py.mcp.auth.models import get_role_permissions
    
    permissions = get_role_permissions(role)
    return {"role": role.value, "permissions": [p.value for p in permissions]}


def register_auth_middleware(app):
    """
    Register authentication middleware with the FastAPI app.
    
    This middleware will process the JWT token and API key for every request.
    """
    from fastapi import Request
    from starlette.middleware.base import BaseHTTPMiddleware
    
    class AuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            # Extract JWT token from Authorization header
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "")
                request.state.token = token
            
            # Extract API key from X-API-Key header
            api_key = request.headers.get("X-API-Key")
            if api_key:
                request.state.api_key = api_key
            
            # Process the request
            response = await call_next(request)
            return response
    
    app.add_middleware(AuthMiddleware)