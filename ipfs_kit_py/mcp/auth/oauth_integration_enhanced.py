"""
Enhanced OAuth Integration Module

This module provides comprehensive OAuth 2.0 integration for the MCP server.
It supports multiple OAuth providers (GitHub, Google, etc.) and handles the
authentication flow, token exchange, and user profile retrieval.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements - "Advanced Authentication & Authorization".
"""

import os
import json
import time
import logging
import secrets
import httpx
from typing import Dict, List, Any, Optional, Union, Callable
from urllib.parse import urlencode

from fastapi import APIRouter, Request, Response, Depends, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse

from ipfs_kit_py.mcp.auth.models import User, Role, Permission
from ipfs_kit_py.mcp.auth.service import AuthService
from ipfs_kit_py.mcp.auth.audit_logging import AuditLogger, AuditEventType, AuditSeverity

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("oauth_enhanced")

# OAuth provider definitions
OAUTH_PROVIDERS = {
    "github": {
        "name": "GitHub",
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "user_info_url": "https://api.github.com/user",
        "user_email_url": "https://api.github.com/user/emails",
        "scope": "user:email",
        "id_field": "id",
        "username_field": "login",
        "email_field": "email",
        "name_field": "name",
        "avatar_field": "avatar_url"
    },
    "google": {
        "name": "Google",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "user_info_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "scope": "openid email profile",
        "id_field": "sub",
        "username_field": "email",
        "email_field": "email",
        "name_field": "name",
        "avatar_field": "picture"
    },
    "microsoft": {
        "name": "Microsoft",
        "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "user_info_url": "https://graph.microsoft.com/v1.0/me",
        "scope": "openid email profile User.Read",
        "id_field": "id",
        "username_field": "userPrincipalName",
        "email_field": "mail",
        "name_field": "displayName",
        "avatar_field": null
    },
    "gitlab": {
        "name": "GitLab",
        "auth_url": "https://gitlab.com/oauth/authorize",
        "token_url": "https://gitlab.com/oauth/token",
        "user_info_url": "https://gitlab.com/api/v4/user",
        "scope": "read_user",
        "id_field": "id",
        "username_field": "username",
        "email_field": "email",
        "name_field": "name",
        "avatar_field": "avatar_url"
    }
}

class OAuthEnhancedManager:
    """Enhanced OAuth Manager for handling multiple providers."""
    
    def __init__(
        self,
        auth_service: AuthService,
        providers: Dict[str, Dict[str, Any]],
        audit_logger: Optional[AuditLogger] = None
    ):
        """
        Initialize OAuth manager.
        
        Args:
            auth_service: Auth service instance
            providers: Dictionary of provider configurations
            audit_logger: Optional audit logger instance
        """
        self.auth_service = auth_service
        self.providers_config = providers
        self.audit_logger = audit_logger
        
        # Configure providers
        self.providers = {}
        for provider_id, config in providers.items():
            if provider_id in OAUTH_PROVIDERS and config.get("client_id") and config.get("client_secret"):
                provider_def = OAUTH_PROVIDERS[provider_id].copy()
                provider_def.update({
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"],
                    "redirect_uri": config.get("redirect_uri", "")
                })
                self.providers[provider_id] = provider_def
        
        # Create router
        self.router = APIRouter()
        
        # Set up routes
        self.setup_routes()
        
        logger.info(f"OAuth manager initialized with providers: {', '.join(self.providers.keys())}")
    
    def setup_routes(self):
        """Set up router endpoints."""
        
        @self.router.get("/providers")
        async def list_providers():
            """List available OAuth providers."""
            return {
                "success": True,
                "providers": [
                    {
                        "id": provider_id,
                        "name": provider["name"]
                    }
                    for provider_id, provider in self.providers.items()
                ]
            }
        
        @self.router.get("/{provider_id}/login")
        async def oauth_login(request: Request, provider_id: str):
            """
            Get OAuth login URL for a provider.
            
            Args:
                request: FastAPI request
                provider_id: OAuth provider ID
            """
            if provider_id not in self.providers:
                raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")
            
            provider = self.providers[provider_id]
            
            # Generate state for CSRF protection
            state = secrets.token_urlsafe(32)
            
            # Store state in session (would be cookie/Redis in production)
            # For now, we'll use a simple cookie
            response = JSONResponse({
                "success": True,
                "login_url": self.get_authorization_url(provider_id, state)
            })
            response.set_cookie(
                key=f"oauth_state_{provider_id}",
                value=state,
                httponly=True,
                max_age=600,  # 10 minutes
                secure=False,  # Set to True in production with HTTPS
                samesite="lax"
            )
            
            return response
        
        @self.router.get("/{provider_id}/callback")
        async def oauth_callback(
            request: Request,
            provider_id: str,
            code: Optional[str] = None,
            state: Optional[str] = None,
            error: Optional[str] = None,
            error_description: Optional[str] = None
        ):
            """
            Handle OAuth callback from provider.
            
            Args:
                request: FastAPI request
                provider_id: OAuth provider ID
                code: Authorization code
                state: State for CSRF protection
                error: Optional error code
                error_description: Optional error description
            """
            if provider_id not in self.providers:
                raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")
            
            # Check for errors
            if error:
                error_msg = error_description or f"OAuth error: {error}"
                
                # Log failed authentication
                if self.audit_logger:
                    self.audit_logger.log(
                        event_type=AuditEventType.AUTH,
                        action="oauth_callback_error",
                        severity=AuditSeverity.WARNING,
                        user_id="anonymous",
                        details={
                            "provider": provider_id,
                            "error": error,
                            "error_description": error_description,
                            "ip": request.client.host if request.client else None
                        }
                    )
                
                return JSONResponse({
                    "success": False,
                    "error": error_msg
                })
            
            # Verify state
            stored_state = request.cookies.get(f"oauth_state_{provider_id}")
            if not stored_state or stored_state != state:
                
                # Log suspicious activity - potential CSRF attack
                if self.audit_logger:
                    self.audit_logger.log(
                        event_type=AuditEventType.SECURITY,
                        action="oauth_csrf_attempt",
                        severity=AuditSeverity.WARNING,
                        user_id="anonymous",
                        details={
                            "provider": provider_id,
                            "expected_state": stored_state,
                            "received_state": state,
                            "ip": request.client.host if request.client else None
                        }
                    )
                
                raise HTTPException(
                    status_code=400,
                    detail="Invalid state parameter (potential CSRF attack)"
                )
            
            # Exchange code for tokens
            try:
                # Get tokens
                token_result = await self.exchange_code_for_token(provider_id, code)
                access_token = token_result.get("access_token")
                
                if not access_token:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to get access token: {token_result.get('error', 'Unknown error')}"
                    )
                
                # Get user profile
                user_profile = await self.get_user_profile(provider_id, access_token)
                
                if not user_profile:
                    raise HTTPException(
                        status_code=400,
                        detail="Failed to get user profile"
                    )
                
                # Create or get user
                user = await self.get_or_create_user(provider_id, user_profile)
                
                # Generate tokens
                tokens = await self.auth_service.create_tokens_for_user(user)
                
                # Clear state cookie and set tokens
                response = JSONResponse({
                    "success": True,
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "role": user.role,
                        "profile": user.profile
                    },
                    "access_token": tokens["access_token"],
                    "refresh_token": tokens["refresh_token"],
                    "token_type": "bearer"
                })
                
                # Clear state cookie
                response.delete_cookie(key=f"oauth_state_{provider_id}")
                
                # Log successful authentication
                if self.audit_logger:
                    self.audit_logger.log(
                        event_type=AuditEventType.AUTH,
                        action="oauth_login_success",
                        severity=AuditSeverity.INFO,
                        user_id=user.id,
                        details={
                            "provider": provider_id,
                            "username": user.username,
                            "ip": request.client.host if request.client else None
                        }
                    )
                
                return response
                
            except Exception as e:
                logger.error(f"OAuth callback error: {str(e)}")
                
                # Log error
                if self.audit_logger:
                    self.audit_logger.log(
                        event_type=AuditEventType.AUTH,
                        action="oauth_callback_exception",
                        severity=AuditSeverity.ERROR,
                        user_id="anonymous",
                        details={
                            "provider": provider_id,
                            "error": str(e),
                            "ip": request.client.host if request.client else None
                        }
                    )
                
                raise HTTPException(
                    status_code=500,
                    detail=f"OAuth callback error: {str(e)}"
                )
    
    def get_authorization_url(self, provider_id: str, state: str) -> str:
        """
        Get authorization URL for a provider.
        
        Args:
            provider_id: Provider ID
            state: State for CSRF protection
            
        Returns:
            Authorization URL
        """
        if provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")
        
        provider = self.providers[provider_id]
        
        params = {
            "client_id": provider["client_id"],
            "response_type": "code",
            "redirect_uri": provider["redirect_uri"],
            "state": state,
            "scope": provider["scope"]
        }
        
        return f"{provider['auth_url']}?{urlencode(params)}"
    
    async def exchange_code_for_token(self, provider_id: str, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Args:
            provider_id: Provider ID
            code: Authorization code
            
        Returns:
            Token response
        """
        if provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")
        
        provider = self.providers[provider_id]
        
        data = {
            "client_id": provider["client_id"],
            "client_secret": provider["client_secret"],
            "code": code,
            "redirect_uri": provider["redirect_uri"],
            "grant_type": "authorization_code"
        }
        
        headers = {
            "Accept": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                provider["token_url"],
                data=data,
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"Token exchange error: {response.text}")
                return {"error": f"HTTP {response.status_code}: {response.text}"}
            
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"error": "Invalid JSON response"}
    
    async def get_user_profile(self, provider_id: str, access_token: str) -> Optional[Dict[str, Any]]:
        """
        Get user profile from provider.
        
        Args:
            provider_id: Provider ID
            access_token: Access token
            
        Returns:
            User profile or None if failed
        """
        if provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")
        
        provider = self.providers[provider_id]
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    provider["user_info_url"],
                    headers=headers
                )
                
                if response.status_code != 200:
                    logger.error(f"User info error: {response.text}")
                    return None
                
                user_data = response.json()
                
                # For GitHub, email might be private and require a separate call
                if provider_id == "github" and not user_data.get("email"):
                    # Get emails from GitHub API
                    emails_response = await client.get(
                        provider["user_email_url"],
                        headers=headers
                    )
                    
                    if emails_response.status_code == 200:
                        emails = emails_response.json()
                        # Find the primary email
                        for email in emails:
                            if email.get("primary", False):
                                user_data["email"] = email["email"]
                                break
                
                return user_data
                
        except Exception as e:
            logger.error(f"Error getting user profile: {str(e)}")
            return None
    
    async def get_or_create_user(self, provider_id: str, profile: Dict[str, Any]) -> User:
        """
        Get existing user or create a new one based on OAuth profile.
        
        Args:
            provider_id: Provider ID
            profile: User profile from OAuth provider
            
        Returns:
            User object
        """
        if provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")
        
        provider = self.providers[provider_id]
        
        # Extract user data from profile
        provider_user_id = str(profile.get(provider["id_field"], ""))
        username = profile.get(provider["username_field"], "")
        email = profile.get(provider["email_field"], "")
        name = profile.get(provider["name_field"], "")
        avatar = profile.get(provider["avatar_field"], "")
        
        if not provider_user_id or not username:
            raise ValueError("Provider profile missing required fields")
        
        # Create a unique user ID for this provider
        external_user_id = f"{provider_id}:{provider_user_id}"
        
        # Try to find existing user
        existing_user = await self.auth_service.get_user_by_external_id(external_user_id)
        
        if existing_user:
            # Update user data if needed
            updated = False
            
            if email and existing_user.email != email:
                existing_user.email = email
                updated = True
            
            if name and existing_user.profile.get("name") != name:
                existing_user.profile["name"] = name
                updated = True
            
            if avatar and existing_user.profile.get("avatar") != avatar:
                existing_user.profile["avatar"] = avatar
                updated = True
            
            if updated:
                await self.auth_service.update_user(existing_user)
            
            return existing_user
        
        # Create new user
        new_user = User(
            username=username,
            email=email,
            role=Role.USER,  # Default role for OAuth users
            external_id=external_user_id,
            profile={
                "name": name,
                "avatar": avatar,
                "provider": provider_id
            }
        )
        
        # Store user
        created_user = await self.auth_service.create_user(new_user)
        
        # Log user creation
        if self.audit_logger:
            self.audit_logger.log(
                event_type=AuditEventType.USER,
                action="user_created_oauth",
                severity=AuditSeverity.INFO,
                user_id=created_user.id,
                details={
                    "provider": provider_id,
                    "username": username,
                    "email": email
                }
            )
        
        return created_user
    
    def get_enabled_providers(self) -> List[Dict[str, str]]:
        """
        Get list of enabled OAuth providers.
        
        Returns:
            List of provider information dictionaries
        """
        return [
            {
                "id": provider_id,
                "name": provider["name"]
            }
            for provider_id, provider in self.providers.items()
        ]