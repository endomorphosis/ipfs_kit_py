"""
OAuth API Router for MCP Server

This module provides REST API endpoints for OAuth operations:
- Provider management
- OAuth login flows
- User account connections

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
import secrets
import urllib.parse
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from ipfs_kit_py.mcp.auth.models import User, OAuthProvider, Role, TokenResponse
from ipfs_kit_py.mcp.auth.router import get_current_user, get_admin_user
from ipfs_kit_py.mcp.auth.oauth_manager import get_oauth_manager
from ipfs_kit_py.mcp.auth.audit import get_audit_logger

# Configure logging
logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/api/v0/oauth", tags=["oauth"])


# --- Pydantic models ---

class OAuthProviderInfo(BaseModel):
    """OAuth provider information."""
    id: str
    name: str
    provider_type: str
    authorize_url: str
    token_url: str
    scope: str
    active: bool


class OAuthProviderConfig(BaseModel):
    """OAuth provider configuration."""
    id: str
    name: str
    provider_type: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scope: str
    active: bool = True
    default_roles: List[str] = ["user"]
    domain_restrictions: Optional[List[str]] = None


class OAuthConnectionInfo(BaseModel):
    """OAuth connection information."""
    provider_id: str
    provider_name: str
    provider_user_id: str
    email: Optional[str] = None
    username: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    connected_at: str
    last_used: Optional[str] = None


class OAuthAuthUrlResponse(BaseModel):
    """Response model for OAuth authorization URL."""
    authorization_url: str


class OAuthCallbackResponse(TokenResponse):
    """Response model for OAuth callback."""
    is_new_user: bool = False
    user_info: Dict[str, Any] = Field(default_factory=dict)


# --- Provider management endpoints ---

@router.get("/providers", summary="List available OAuth providers")
async def list_providers(current_user: User = Depends(get_current_user)):
    """
    List all available OAuth providers.
    
    Returns public information about the providers, excluding secrets.
    """
    oauth_manager = get_oauth_manager()
    
    # Load all providers
    providers = await oauth_manager.load_providers()
    
    # Convert to public info model
    provider_info = [
        OAuthProviderInfo(
            id=provider.id,
            name=provider.name,
            provider_type=provider.provider_type,
            authorize_url=provider.authorize_url,
            token_url=provider.token_url,
            scope=provider.scope,
            active=provider.active
        )
        for provider in providers.values()
        if provider.active
    ]
    
    return {"providers": provider_info}


@router.get("/providers/{provider_id}", summary="Get OAuth provider details")
async def get_provider_details(
    provider_id: str,
    current_user: User = Depends(get_admin_user)
):
    """
    Get details for a specific OAuth provider.
    
    This includes sensitive information and requires admin privileges.
    """
    oauth_manager = get_oauth_manager()
    
    # Get the provider
    provider = await oauth_manager.get_provider(provider_id)
    if not provider:
        raise HTTPException(
            status_code=404,
            detail=f"Provider {provider_id} not found"
        )
    
    # Return complete provider config
    return provider


@router.post("/providers", summary="Add or update OAuth provider")
async def add_provider(
    provider_config: OAuthProviderConfig,
    current_user: User = Depends(get_admin_user)
):
    """
    Add or update an OAuth provider configuration.
    
    Requires admin privileges.
    """
    oauth_manager = get_oauth_manager()
    
    # Add or update the provider
    success, message = await oauth_manager.add_provider(provider_config.dict())
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail=message
        )
    
    # Log the action
    audit_logger = get_audit_logger()
    await audit_logger.log_admin_action(
        user_id=current_user.id,
        action="provider_update",
        resource_id=provider_config.id,
        resource_type="oauth_provider",
        details={"provider_type": provider_config.provider_type}
    )
    
    return {"message": message, "provider_id": provider_config.id}


@router.delete("/providers/{provider_id}", summary="Delete OAuth provider")
async def delete_provider(
    provider_id: str,
    current_user: User = Depends(get_admin_user)
):
    """
    Delete an OAuth provider configuration.
    
    Requires admin privileges.
    """
    oauth_manager = get_oauth_manager()
    
    # Delete the provider
    success, message = await oauth_manager.delete_provider(provider_id)
    
    if not success:
        raise HTTPException(
            status_code=404 if "not found" in message else 400,
            detail=message
        )
    
    # Log the action
    audit_logger = get_audit_logger()
    await audit_logger.log_admin_action(
        user_id=current_user.id,
        action="provider_delete",
        resource_id=provider_id,
        resource_type="oauth_provider"
    )
    
    return {"message": message}


# --- OAuth login flow endpoints ---

@router.get("/login/{provider_id}", response_model=OAuthAuthUrlResponse, summary="Get OAuth login URL")
async def get_oauth_login_url(
    provider_id: str,
    redirect_uri: str = Query(..., description="URI to redirect to after authorization"),
    state: Optional[str] = Query(None, description="Optional state parameter")
):
    """
    Get an authorization URL for an OAuth provider.
    
    This is the first step in the OAuth flow.
    """
    oauth_manager = get_oauth_manager()
    
    # Generate state if not provided
    state_value = state or secrets.token_urlsafe(32)
    
    # Create authorization URL
    success, result, message = await oauth_manager.create_authorization_url(
        provider_id, redirect_uri, state_value
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail=message
        )
    
    # Save state for validation
    from ipfs_kit_py.mcp.auth.persistence import get_persistence_manager
    persistence = get_persistence_manager()
    await persistence.save_oauth_state(
        state_value,
        {"provider_id": provider_id, "redirect_uri": redirect_uri}
    )
    
    return result


@router.get("/callback/{provider_id}", response_model=OAuthCallbackResponse, summary="Handle OAuth callback")
async def oauth_callback(
    request: Request,
    provider_id: str,
    code: str = Query(..., description="Authorization code from provider"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    redirect_uri: str = Query(..., description="Redirect URI used in authorization")
):
    """
    Handle the OAuth callback from the provider.
    
    This is the second step in the OAuth flow, after the user has authorized the application.
    """
    from ipfs_kit_py.mcp.auth.service import get_instance as get_auth_service
    
    # Get client info for audit
    client_host = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    
    # Process the OAuth callback
    auth_service = get_auth_service()
    success, result, message = await auth_service.process_oauth_callback(
        provider_id, code, redirect_uri, client_host, user_agent
    )
    
    if not success:
        # Log failed OAuth attempt
        audit_logger = get_audit_logger()
        await audit_logger.log_oauth_failure(
            provider_id=provider_id,
            error=message,
            ip_address=client_host,
            user_agent=user_agent
        )
        
        raise HTTPException(
            status_code=400,
            detail=message
        )
    
    return result


# --- User OAuth connections endpoints ---

@router.get("/connections", summary="List user OAuth connections")
async def list_user_connections(current_user: User = Depends(get_current_user)):
    """
    List all OAuth connections for the current user.
    
    Shows which OAuth providers the user has connected to their account.
    """
    oauth_manager = get_oauth_manager()
    
    # Get connections for the current user
    connections = await oauth_manager.get_user_oauth_connections(current_user.id)
    
    # Load provider info to get names
    providers = await oauth_manager.load_providers()
    
    # Format connection info
    connection_info = []
    for conn in connections:
        provider = providers.get(conn.get("provider_id", ""))
        provider_name = provider.name if provider else conn.get("provider_id", "Unknown")
        
        connection_info.append(
            OAuthConnectionInfo(
                provider_id=conn.get("provider_id", ""),
                provider_name=provider_name,
                provider_user_id=conn.get("provider_user_id", ""),
                email=conn.get("email"),
                username=conn.get("username"),
                name=conn.get("name"),
                avatar_url=conn.get("avatar_url"),
                connected_at=conn.get("created_at", ""),
                last_used=conn.get("last_used")
            )
        )
    
    return {"connections": connection_info}


@router.delete("/connections/{provider_id}", summary="Unlink OAuth connection")
async def unlink_connection(
    provider_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Unlink an OAuth provider from the current user's account.
    """
    oauth_manager = get_oauth_manager()
    
    # Unlink the connection
    success, message = await oauth_manager.unlink_user_account(
        current_user.id, provider_id
    )
    
    if not success:
        raise HTTPException(
            status_code=404 if "not found" in message else 400,
            detail=message
        )
    
    # Log the action
    audit_logger = get_audit_logger()
    await audit_logger.log_user_action(
        user_id=current_user.id,
        action="oauth_unlink",
        resource_id=provider_id,
        resource_type="oauth_connection"
    )
    
    return {"message": message}


@router.get("/connect/{provider_id}", response_model=OAuthAuthUrlResponse, summary="Connect OAuth provider")
async def connect_provider(
    provider_id: str,
    current_user: User = Depends(get_current_user),
    redirect_uri: str = Query(..., description="URI to redirect to after connection")
):
    """
    Start the flow to connect an OAuth provider to the current user's account.
    
    Returns an authorization URL to redirect the user to.
    """
    oauth_manager = get_oauth_manager()
    
    # Generate state with user ID for the callback
    state_value = secrets.token_urlsafe(32)
    
    # Create authorization URL
    success, result, message = await oauth_manager.create_authorization_url(
        provider_id, redirect_uri, state_value
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail=message
        )
    
    # Save state with user ID for connection
    from ipfs_kit_py.mcp.auth.persistence import get_persistence_manager
    persistence = get_persistence_manager()
    await persistence.save_oauth_state(
        state_value,
        {
            "provider_id": provider_id,
            "redirect_uri": redirect_uri,
            "user_id": current_user.id,
            "mode": "connect"
        }
    )
    
    return result


@router.get("/connect/callback/{provider_id}", summary="Handle OAuth connection callback")
async def connect_callback(
    request: Request,
    provider_id: str,
    code: str = Query(..., description="Authorization code from provider"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    redirect_uri: str = Query(..., description="Redirect URI used in authorization")
):
    """
    Handle the callback when connecting an OAuth provider to an existing account.
    """
    from ipfs_kit_py.mcp.auth.persistence import get_persistence_manager
    
    # Get client info for audit
    client_host = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    
    # Verify state and get associated data
    persistence = get_persistence_manager()
    state_data = await persistence.verify_oauth_state(state)
    
    if not state_data or state_data.get("mode") != "connect":
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired state parameter"
        )
    
    user_id = state_data.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="No user ID in state data"
        )
    
    # Process the OAuth connection
    oauth_manager = get_oauth_manager()
    
    # Exchange code for token
    success, token_data, message = await oauth_manager.exchange_code_for_token(
        provider_id, code, redirect_uri
    )
    
    if not success:
        # Log failure
        audit_logger = get_audit_logger()
        await audit_logger.log_oauth_failure(
            provider_id=provider_id,
            error=message,
            ip_address=client_host,
            user_agent=user_agent
        )
        
        raise HTTPException(
            status_code=400,
            detail=message
        )
    
    # Get user info
    access_token = token_data.get("access_token")
    success, user_info, message = await oauth_manager.get_user_info(
        provider_id, access_token
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail=message
        )
    
    # Check if this OAuth identity is already linked to another account
    existing_user = await oauth_manager.find_linked_user(
        provider_id, user_info.get("provider_user_id")
    )
    
    if existing_user and existing_user.get("id") != user_id:
        raise HTTPException(
            status_code=400,
            detail="This OAuth account is already linked to another user"
        )
    
    # Link the OAuth account to the user
    provider_user_id = user_info.get("provider_user_id")
    success, message = await oauth_manager.link_user_account(
        user_id, provider_id, provider_user_id, user_info
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail=message
        )
    
    # Log successful connection
    audit_logger = get_audit_logger()
    await audit_logger.log_oauth_link(
        user_id=user_id,
        provider_id=provider_id,
        provider_user_id=provider_user_id,
        ip_address=client_host,
        user_agent=user_agent
    )
    
    # Return success
    return {
        "message": "OAuth account connected successfully",
        "provider_id": provider_id,
        "provider_user_id": provider_user_id
    }