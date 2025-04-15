"""
OAuth Router for MCP Server.

This module provides API endpoints for OAuth authentication with enhanced security.
It implements the improved OAuth flow described in the MCP roadmap.
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel, Field

from .integration import OAuthIntegrationManager
from ..models.auth import User, TokenData
from ..models.responses import StandardResponse, ErrorResponse

# Configure logging
logger = logging.getLogger(__name__)

# Models for request/response
class OAuthAuthorizeRequest(BaseModel):
    """Request model for OAuth authorization."""
    provider_id: str = Field(..., description="OAuth provider ID")
    redirect_uri: str = Field(..., description="Redirect URI after authorization")
    state: Optional[str] = Field(None, description="Optional client state parameter")

class OAuthProviderInfo(BaseModel):
    """Information about an OAuth provider."""
    id: str = Field(..., description="Provider ID")
    name: str = Field(..., description="Display name")
    type: str = Field(..., description="Provider type")

class OAuthAuthorizeResponse(StandardResponse):
    """Response model for OAuth authorization."""
    data: Dict[str, Any] = Field(..., description="Authorization data")

class OAuthCallbackRequest(BaseModel):
    """Request model for OAuth callback."""
    code: str = Field(..., description="Authorization code")
    state: str = Field(..., description="State parameter")
    
class OAuthProvidersResponse(StandardResponse):
    """Response model for available OAuth providers."""
    data: List[OAuthProviderInfo] = Field(..., description="List of available providers")

class OAuthTokenResponse(StandardResponse):
    """Response model for OAuth token data."""
    data: Dict[str, Any] = Field(..., description="Token data")


def create_oauth_router(
    oauth_manager: OAuthIntegrationManager,
    get_current_user=None,
) -> APIRouter:
    """
    Create and configure the OAuth router.
    
    Args:
        oauth_manager: OAuth integration manager
        get_current_user: Optional dependency for protected endpoints
        
    Returns:
        Configured router
    """
    router = APIRouter(tags=["OAuth Authentication"])

    @router.get(
        "/providers",
        response_model=OAuthProvidersResponse,
        summary="Get OAuth Providers",
        description="Get a list of available OAuth providers."
    )
    async def get_oauth_providers():
        """Get available OAuth providers."""
        try:
            providers = await oauth_manager.get_available_providers()
            return OAuthProvidersResponse(
                success=True,
                message="OAuth providers retrieved successfully",
                data=providers
            )
        except Exception as e:
            logger.error(f"Error getting OAuth providers: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get OAuth providers: {str(e)}"
            )

    @router.post(
        "/authorize",
        response_model=OAuthAuthorizeResponse,
        summary="Start OAuth Flow",
        description="Start the OAuth authorization flow with a provider."
    )
    async def oauth_authorize(request: OAuthAuthorizeRequest):
        """Start OAuth authorization flow."""
        try:
            additional_params = {}
            if request.state:
                additional_params["state"] = request.state

            success, data, error = await oauth_manager.create_authorization_url(
                provider_id=request.provider_id,
                redirect_uri=request.redirect_uri,
                additional_params=additional_params
            )
            
            if not success:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content=ErrorResponse(
                        success=False,
                        message=error,
                        error_code="oauth_authorize_failed",
                        error_details={"provider_id": request.provider_id}
                    ).dict()
                )
                
            return OAuthAuthorizeResponse(
                success=True,
                message="OAuth authorization URL created",
                data=data
            )
        except Exception as e:
            logger.error(f"Error creating OAuth authorization URL: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create authorization URL: {str(e)}"
            )

    @router.get(
        "/callback/{provider_id}",
        summary="OAuth Callback",
        description="Handle OAuth callback from provider."
    )
    async def oauth_callback(
        provider_id: str,
        code: str,
        state: str,
        request: Request,
        error: Optional[str] = None,
        error_description: Optional[str] = None
    ):
        """Handle OAuth callback."""
        try:
            # Check for errors from OAuth provider
            if error:
                error_msg = error_description or error
                logger.warning(f"OAuth error from provider {provider_id}: {error_msg}")
                
                # Redirect to error page or return error response
                frontend_url = request.headers.get("Referer", "/")
                return RedirectResponse(
                    url=f"{frontend_url}?error={error_msg}&auth_failed=true",
                    status_code=status.HTTP_302_FOUND
                )
                
            # Get client IP and user agent
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("User-Agent")
                
            # Process the callback
            success, auth_data, error = await oauth_manager.process_callback(
                provider_id=provider_id,
                code=code,
                state=state,
                ip_address=ip_address,
                user_agent=user_agent
            )
                
            if not success:
                logger.warning(f"OAuth callback processing failed: {error}")
                
                # Redirect to error page or return error response
                frontend_url = request.headers.get("Referer", "/")
                return RedirectResponse(
                    url=f"{frontend_url}?error={error}&auth_failed=true",
                    status_code=status.HTTP_302_FOUND
                )
                
            # For standard API clients, return token directly as JSON
            if "application/json" in request.headers.get("Accept", ""):
                return OAuthTokenResponse(
                    success=True,
                    message="OAuth authentication successful",
                    data=auth_data
                )
                
            # Otherwise, handle as browser flow - redirect to frontend with token
            # This allows browser-based apps to complete the flow
            
            # Extract token data for URL parameters
            access_token = auth_data.get("access_token", "")
            refresh_token = auth_data.get("refresh_token", "")
            user_info = auth_data.get("user", {})
            is_new_user = auth_data.get("is_new_user", False)
            
            # Determine redirect URL (use a configurable default)
            frontend_url = request.headers.get("Referer", "/")
            redirect_to = f"{frontend_url}?access_token={access_token}&refresh_token={refresh_token}&user_id={user_info.get('id', '')}&is_new_user={is_new_user}"
            
            return RedirectResponse(
                url=redirect_to,
                status_code=status.HTTP_302_FOUND
            )
                
        except Exception as e:
            logger.error(f"Error processing OAuth callback: {e}")
            
            # For API clients, return error as JSON
            if "application/json" in request.headers.get("Accept", ""):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"OAuth callback error: {str(e)}"
                )
                
            # For browser clients, redirect to error page
            frontend_url = request.headers.get("Referer", "/")
            return RedirectResponse(
                url=f"{frontend_url}?error=Server+error&auth_failed=true",
                status_code=status.HTTP_302_FOUND
            )

    @router.post(
        "/exchange",
        response_model=OAuthTokenResponse,
        summary="Exchange OAuth Code",
        description="Programmatically exchange an OAuth code for tokens."
    )
    async def exchange_oauth_code(
        request: OAuthCallbackRequest,
        provider_id: str,
        redirect_uri: str,
        client_request: Request
    ):
        """Exchange OAuth code for tokens."""
        try:
            # Get client IP and user agent
            ip_address = client_request.client.host if client_request.client else None
            user_agent = client_request.headers.get("User-Agent")
                
            # Process the code exchange
            success, auth_data, error = await oauth_manager.process_callback(
                provider_id=provider_id,
                code=request.code,
                state=request.state,
                redirect_uri=redirect_uri,
                ip_address=ip_address,
                user_agent=user_agent
            )
                
            if not success:
                logger.warning(f"OAuth token exchange failed: {error}")
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content=ErrorResponse(
                        success=False,
                        message=error,
                        error_code="oauth_exchange_failed",
                        error_details={"provider_id": provider_id}
                    ).dict()
                )
                
            return OAuthTokenResponse(
                success=True,
                message="OAuth authentication successful",
                data=auth_data
            )
                
        except Exception as e:
            logger.error(f"Error exchanging OAuth code: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"OAuth exchange error: {str(e)}"
            )

    return router