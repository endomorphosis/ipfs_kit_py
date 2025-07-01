"""
Authentication API router for MCP server.

This module provides REST API endpoints for authentication and authorization
as specified in the MCP roadmap.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from ..auth.middleware import get_current_user, require_permission
from ..auth.models import ApiKeyCreateRequest, LoginRequest, RegisterRequest
from ..auth.service import AuthenticationService

logger = logging.getLogger(__name__)


def create_auth_router(auth_service: AuthenticationService) -> APIRouter:
    """
    Create a FastAPI router for authentication endpoints.

    Args:
        auth_service: Authentication service instance

    Returns:
        FastAPI router
    """
    router = APIRouter(prefix="/api/v0/auth", tags=["auth"])

    @router.post("/register")
    async def register_user(request: RegisterRequest):
        """Register a new user."""
        try:
            success, user, message = await auth_service.register_user(request)

            if not success:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"success": False, "message": message},
                )

            return {
                "success": True
                "message": "User registered successfully",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                },
            }
        except Exception as e:
            logger.error(f"Error registering user: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False
                    "message": f"Internal server error: {str(e)}",
                },
            )

    @router.post("/login")
    async def login(request: Request, login_request: LoginRequest, response: Response):
        """Login a user and return tokens."""
        try:
            success, tokens, message = await auth_service.login(
                login_request,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )

            if not success:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"success": False, "message": message},
                )

            # Set access token as cookie if running in browser context
            if request.headers.get("accept", "").find("text/html") != -1:
                cookie_max_age = auth_service.token_expire_minutes * 60
                if login_request.remember_me:
                    cookie_max_age = auth_service.refresh_token_expire_days * 86400

                response.set_cookie(
                    key="access_token",
                    value=tokens["access_token"],
                    httponly=True,
                    max_age=cookie_max_age,
                    path="/",
                    secure=request.url.scheme == "https",
                    samesite="lax",
                )

            return {
                "success": True
                "message": "Login successful",
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "token_type": tokens["token_type"],
                "expires_in": tokens["expires_in"],
                "user": tokens["user"],
            }
        except Exception as e:
            logger.error(f"Error logging in: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False
                    "message": f"Internal server error: {str(e)}",
                },
            )

    @router.post("/token")
    async def refresh_token(refresh_token: str):
        """Refresh an access token using a refresh token."""
        try:
            success, access_token, message = await auth_service.refresh_access_token(refresh_token)

            if not success:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"success": False, "message": message},
                )

            return {
                "success": True
                "access_token": access_token
                "token_type": "bearer",
                "expires_in": auth_service.token_expire_minutes * 60,
            }
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False
                    "message": f"Internal server error: {str(e)}",
                },
            )

    @router.post("/logout")
    async def logout(
        request: Request
        response: Response
        user_id: str = Depends(get_current_user),
        access_token: Optional[str] = Cookie(None, alias="access_token"),
    ):
        """Logout a user by revoking their token."""
        try:
            # Extract token from request
            token = None

            # Check for token in Authorization header
            auth_header = request.headers.get("Authorization")
            if auth_header:
                parts = auth_header.split()
                if len(parts) == 2 and parts[0].lower() == "bearer":
                    token = parts[1]

            # Check for token in cookie
            if not token and access_token:
                token = access_token

            # Revoke token if found
            if token:
                await auth_service.revoke_token(token)

            # Clear cookie
            response.delete_cookie(
                key="access_token",
                path="/",
                secure=request.url.scheme == "https",
                httponly=True,
            )

            return {"success": True, "message": "Logout successful"}
        except Exception as e:
            logger.error(f"Error logging out: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False
                    "message": f"Internal server error: {str(e)}",
                },
            )

    @router.get("/user")
    async def get_user_info(user_id: str = Depends(get_current_user)):
        """Get information about the current user."""
        try:
            user = await auth_service.get_user(user_id)
            if not user:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"success": False, "message": "User not found"},
                )

            # Get user permissions
            permissions = await auth_service.get_user_permissions(user_id)

            return {
                "success": True
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "roles": list(user.roles),
                    "permissions": list(permissions),
                    "created_at": user.created_at,
                    "last_login": user.last_login,
                },
            }
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False
                    "message": f"Internal server error: {str(e)}",
                },
            )

    @router.post("/apikeys")
    async def create_api_key(
        request: ApiKeyCreateRequest, user_id: str = Depends(get_current_user)
    ):
        """Create a new API key."""
        try:
            success, api_key, message = await auth_service.create_api_key(user_id, request)

            if not success:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"success": False, "message": message},
                )

            return {
                "success": True
                "message": "API key created successfully",
                "api_key": api_key.dict(),
            }
        except Exception as e:
            logger.error(f"Error creating API key: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False
                    "message": f"Internal server error: {str(e)}",
                },
            )

    @router.get("/apikeys")
    async def list_api_keys(user_id: str = Depends(get_current_user)):
        """List all API keys for the current user."""
        try:
            api_keys = await auth_service.api_key_store.get_by_user(user_id)

            # Remove sensitive information
            sanitized_keys = []
            for key_id, key_data in api_keys.items():
                sanitized_key = {
                    k: v for k, v in key_data.items() if k not in ["hashed_key", "key"]
                }
                sanitized_key["id"] = key_id
                sanitized_keys.append(sanitized_key)

            return {"success": True, "api_keys": sanitized_keys}
        except Exception as e:
            logger.error(f"Error listing API keys: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False
                    "message": f"Internal server error: {str(e)}",
                },
            )

    @router.delete("/apikeys/{key_id}")
    async def revoke_api_key(key_id: str, user_id: str = Depends(get_current_user)):
        """Revoke an API key."""
        try:
            success, message = await auth_service.revoke_api_key(key_id, user_id)

            if not success:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"success": False, "message": message},
                )

            return {"success": True, "message": "API key revoked successfully"}
        except Exception as e:
            logger.error(f"Error revoking API key: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False
                    "message": f"Internal server error: {str(e)}",
                },
            )

    @router.get("/sessions")
    async def list_sessions(user_id: str = Depends(get_current_user)):
        """List all active sessions for the current user."""
        try:
            sessions = await auth_service.session_store.find_by_user(user_id)

            # Filter active sessions and add ID
            active_sessions = []
            for session_id, session_data in sessions.items():
                if (
                    session_data.get("active", False)
                    and session_data.get("expires_at", 0) > datetime.now().timestamp()
                ):
                    session_data["id"] = session_id
                    active_sessions.append(session_data)

            return {"success": True, "sessions": active_sessions}
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False
                    "message": f"Internal server error: {str(e)}",
                },
            )

    @router.delete("/sessions/{session_id}")
    async def revoke_session(session_id: str, user_id: str = Depends(get_current_user)):
        """Revoke a specific session."""
        try:
            # Get session
            session = await auth_service.session_store.get(session_id)
            if not session:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"success": False, "message": "Session not found"},
                )

            # Check if session belongs to user
            if session.get("user_id") != user_id:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "success": False
                        "message": "Session does not belong to this user",
                    },
                )

            # Revoke session
            session["active"] = False
            await auth_service.session_store.update(session_id, session)

            return {"success": True, "message": "Session revoked successfully"}
        except Exception as e:
            logger.error(f"Error revoking session: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False
                    "message": f"Internal server error: {str(e)}",
                },
            )

    @router.post("/sessions/revoke-all")
    async def revoke_all_sessions(user_id: str = Depends(get_current_user)):
        """Revoke all sessions for the current user."""
        try:
            count = await auth_service.revoke_all_user_tokens(user_id)

            return {
                "success": True
                "message": f"Revoked {count} sessions successfully",
            }
        except Exception as e:
            logger.error(f"Error revoking all sessions: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False
                    "message": f"Internal server error: {str(e)}",
                },
            )

    @router.get("/roles")
    async def list_roles(
        user_id: str = Depends(get_current_user),
        _: bool = Depends(require_permission("user:manage")),
    ):
        """List all roles (requires user:manage permission)."""
        try:
            roles = await auth_service.role_store.load_all()

            # Add IDs to role data
            role_list = []
            for role_id, role_data in roles.items():
                role_data["id"] = role_id
                role_list.append(role_data)

            return {"success": True, "roles": role_list}
        except Exception as e:
            logger.error(f"Error listing roles: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False
                    "message": f"Internal server error: {str(e)}",
                },
            )

    @router.get("/permissions")
    async def list_permissions(
        user_id: str = Depends(get_current_user),
        _: bool = Depends(require_permission("user:manage")),
    ):
        """List all permissions (requires user:manage permission)."""
        try:
            permissions = await auth_service.permission_store.load_all()

            # Add IDs to permission data
            perm_list = []
            for perm_id, perm_data in permissions.items():
                perm_data["id"] = perm_id
                perm_list.append(perm_data)

            return {"success": True, "permissions": perm_list}
        except Exception as e:
            logger.error(f"Error listing permissions: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False
                    "message": f"Internal server error: {str(e)}",
                },
            )

    @router.get("/users")
    async def list_users(
        user_id: str = Depends(get_current_user),
        _: bool = Depends(require_permission("user:manage")),
    ):
        """List all users (requires user:manage permission)."""
        try:
            users = await auth_service.user_store.load_all()

            # Sanitize user data
            user_list = []
            for user_id, user_data in users.items():
                sanitized_user = {
                    k: v for k, v in user_data.items() if k not in ["hashed_password"]
                }
                sanitized_user["id"] = user_id
                user_list.append(sanitized_user)

            return {"success": True, "users": user_list}
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False
                    "message": f"Internal server error: {str(e)}",
                },
            )

    @router.post("/check-permission")
    async def check_user_permission(permission: str, user_id: str = Depends(get_current_user)):
        """Check if the current user has a specific permission."""
        try:
            has_permission = await auth_service.check_permission(user_id, permission)

            return {"success": True, "has_permission": has_permission}
        except Exception as e:
            logger.error(f"Error checking permission: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False
                    "message": f"Internal server error: {str(e)}",
                },
            )

    @router.post("/check-role")
    async def check_user_role(role: str, user_id: str = Depends(get_current_user)):
        """Check if the current user has a specific role."""
        try:
            has_role = await auth_service.check_role(user_id, role)

            return {"success": True, "has_role": has_role}
        except Exception as e:
            logger.error(f"Error checking role: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False
                    "message": f"Internal server error: {str(e)}",
                },
            )

    return router
