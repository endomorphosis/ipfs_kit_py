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
                    content={"success": False, "message": message}
                )

            return {
                "success": True,
                "message": "User registered successfully",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name
                }
            }
        except Exception as e:
            logger.error(f"Error registering user: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "message": f"Internal server error: {str(e)}"
                }
            )

    @router.post("/login")
    async def login(request: Request, login_request: LoginRequest, response: Response):
        """Login a user and return tokens."""
        try:
            success, tokens, message = await auth_service.login(
                login_request,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent")
            )

            if not success:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"success": False, "message": message}
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
                    samesite="lax"
                )

            return {
                "success": True,
                "message": "Login successful",
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "token_type": tokens["token_type"],
                "expires_in": tokens["expires_in"],
                "user": tokens["user"]
            }
        except Exception as e:
            logger.error(f"Error logging in: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "message": f"Internal server error: {str(e)}"
                }
            )

    @router.post("/token")
    async def refresh_token(refresh_token: str):
        """Refresh an access token using a refresh token."""
        try:
            success, access_token, message = await auth_service.refresh_access_token(refresh_token)

            if not success:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"success": False, "message": message}
                )

            return {
                "success": True,
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": auth_service.token_expire_minutes * 60
            }
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "message": f"Internal server error: {str(e)}"
                }
            )

    @router.post("/logout")
    async def logout(
        request: Request,
        response: Response,
        user_id: str = Depends(get_current_user),
        access_token: Optional[str] = Cookie(None, alias="access_token")
    ):
        """Logout a user."""
        try:
            success, message = await auth_service.logout(user_id, access_token)

            # Clear the cookie regardless of success
            if access_token:
                response.delete_cookie(key="access_token", path="/")

            if not success:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"success": False, "message": message}
                )

            return {"success": True, "message": "Logged out successfully"}
        except Exception as e:
            logger.error(f"Error logging out: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "message": f"Internal server error: {str(e)}"
                }
            )

    return router
