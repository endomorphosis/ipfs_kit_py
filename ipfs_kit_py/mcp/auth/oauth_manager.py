"""
OAuth Provider Manager for MCP Server

This module provides comprehensive OAuth integration for the MCP server as specified
in the MCP roadmap for Advanced Authentication & Authorization (Phase 1: Q3 2025).

Features:
- Configurable OAuth provider management
- Support for multiple OAuth providers (GitHub, Google, Microsoft, etc.)
- User account linking with OAuth identities
- Secure token exchange and user info retrieval
- Persistent provider configuration storage
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

import aiohttp
from pydantic import BaseModel, Field, validator

from ipfs_kit_py.mcp.auth.models import OAuthProvider, Role
from ipfs_kit_py.mcp.auth.persistence import get_persistence_manager

# Configure logging
logger = logging.getLogger(__name__)

# OAuth provider configuration models
class OAuthProviderConfig(BaseModel):
    """Configuration for an OAuth provider."""
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
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        """Pydantic model configuration."""
        extra = "allow"  # Allow extra fields for provider-specific config

    def create_authorization_url(self, redirect_uri: str, state: str) -> str:
        """
        Create the authorization URL for this provider.
        
        Args:
            redirect_uri: Redirect URI for the OAuth flow
            state: State parameter for CSRF protection
            
        Returns:
            Complete authorization URL
        """
        import urllib.parse
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": self.scope,
            "state": state,
            "response_type": "code",
        }
        
        # Add custom params for specific providers
        if self.provider_type == "github":
            # GitHub specific
            pass
        elif self.provider_type == "google":
            # Google specific
            params["access_type"] = "offline"
            params["prompt"] = "consent"
        elif self.provider_type == "microsoft":
            # Microsoft specific
            params["response_mode"] = "query"
        
        # Build the URL with parameters
        query_string = urllib.parse.urlencode(params)
        return f"{self.authorize_url}?{query_string}"


class OAuthManager:
    """
    Manager for OAuth provider configurations and operations.
    
    This class handles:
    - Provider configuration management
    - OAuth flow operations
    - User identity management
    """
    
    def __init__(self):
        """Initialize the OAuth manager."""
        self._providers: Dict[str, OAuthProviderConfig] = {}
        self._persistence = get_persistence_manager()
        logger.info("OAuth Manager initialized")
    
    async def load_providers(self, force_reload: bool = False) -> Dict[str, OAuthProviderConfig]:
        """
        Load all OAuth provider configurations.
        
        Args:
            force_reload: Whether to force reload from storage
            
        Returns:
            Dictionary of provider ID to provider config
        """
        if not self._providers or force_reload:
            try:
                # Get providers from persistent storage
                providers_data = await self._persistence.get_oauth_providers()
                
                if not providers_data:
                    # Load default providers if none in storage
                    await self._initialize_default_providers()
                    providers_data = await self._persistence.get_oauth_providers()
                
                # Convert to provider config objects
                self._providers = {
                    provider_id: OAuthProviderConfig(**provider_data)
                    for provider_id, provider_data in providers_data.items()
                    if provider_data.get("active", True)
                }
                
                logger.info(f"Loaded {len(self._providers)} OAuth providers")
            except Exception as e:
                logger.error(f"Error loading OAuth providers: {e}")
                # Fall back to defaults if error
                await self._initialize_default_providers()
        
        return self._providers
    
    async def get_provider(self, provider_id: str) -> Optional[OAuthProviderConfig]:
        """
        Get a specific OAuth provider configuration.
        
        Args:
            provider_id: Provider ID
            
        Returns:
            Provider configuration or None if not found
        """
        providers = await self.load_providers()
        return providers.get(provider_id)
    
    async def add_provider(self, provider_config: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Add or update an OAuth provider configuration.
        
        Args:
            provider_config: Provider configuration data
            
        Returns:
            Tuple of (success, message)
        """
        try:
            provider_id = provider_config.get("id")
            if not provider_id:
                return False, "Provider ID is required"
            
            # Set timestamps
            now = datetime.utcnow()
            if provider_id in self._providers:
                provider_config["updated_at"] = now
            else:
                provider_config["created_at"] = now
                provider_config["updated_at"] = now
            
            # Validate the configuration
            config = OAuthProviderConfig(**provider_config)
            
            # Save to persistence
            await self._persistence.save_oauth_provider(provider_id, config.dict())
            
            # Update local cache
            self._providers[provider_id] = config
            
            return True, f"Provider {provider_id} saved successfully"
        except Exception as e:
            logger.error(f"Error adding OAuth provider: {e}")
            return False, f"Error adding provider: {str(e)}"
    
    async def delete_provider(self, provider_id: str) -> Tuple[bool, str]:
        """
        Delete an OAuth provider configuration.
        
        Args:
            provider_id: Provider ID to delete
            
        Returns:
            Tuple of (success, message)
        """
        try:
            if provider_id not in self._providers:
                return False, f"Provider {provider_id} not found"
            
            # Delete from persistence
            await self._persistence.delete_oauth_provider(provider_id)
            
            # Remove from local cache
            if provider_id in self._providers:
                del self._providers[provider_id]
            
            return True, f"Provider {provider_id} deleted successfully"
        except Exception as e:
            logger.error(f"Error deleting OAuth provider: {e}")
            return False, f"Error deleting provider: {str(e)}"
    
    async def create_authorization_url(
        self, provider_id: str, redirect_uri: str, state: str
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Create an authorization URL for an OAuth provider.
        
        Args:
            provider_id: Provider ID
            redirect_uri: Redirect URI for the OAuth flow
            state: State parameter for CSRF protection
            
        Returns:
            Tuple of (success, result, message)
        """
        provider = await self.get_provider(provider_id)
        if not provider:
            return False, {}, f"Unknown OAuth provider: {provider_id}"
        
        try:
            auth_url = provider.create_authorization_url(redirect_uri, state)
            return True, {"authorization_url": auth_url}, "Authorization URL created"
        except Exception as e:
            logger.error(f"Error creating authorization URL: {e}")
            return False, {}, f"Error creating authorization URL: {str(e)}"
    
    async def exchange_code_for_token(
        self, provider_id: str, code: str, redirect_uri: str
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Exchange an authorization code for an access token.
        
        Args:
            provider_id: Provider ID
            code: Authorization code from the provider
            redirect_uri: Redirect URI used in the authorization request
            
        Returns:
            Tuple of (success, token_data, message)
        """
        provider = await self.get_provider(provider_id)
        if not provider:
            return False, {}, f"Unknown OAuth provider: {provider_id}"
        
        try:
            # Set up token request parameters
            token_params = {
                "client_id": provider.client_id,
                "client_secret": provider.client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }
            
            # Add custom params for specific providers
            headers = {"Accept": "application/json"}
            if provider.provider_type == "github":
                # GitHub needs Accept header for JSON response
                pass
            
            # Make the token request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    provider.token_url, data=token_params, headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OAuth token error: {error_text}")
                        return False, {}, f"Failed to get OAuth token: {response.status}"
                    
                    # Parse the response - try JSON first, then form-encoded
                    content_type = response.headers.get("Content-Type", "")
                    if "application/json" in content_type:
                        token_data = await response.json()
                    else:
                        token_text = await response.text()
                        # Parse form-encoded response
                        import urllib.parse
                        token_data = dict(urllib.parse.parse_qsl(token_text))
            
            # Verify we got an access token
            if "access_token" not in token_data:
                logger.error(f"No access token in response: {token_data}")
                return False, {}, "No access token in OAuth response"
            
            return True, token_data, "Token exchange successful"
        except Exception as e:
            logger.error(f"Error exchanging code for token: {e}")
            return False, {}, f"Error exchanging code: {str(e)}"
    
    async def get_user_info(
        self, provider_id: str, access_token: str
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Get user information from an OAuth provider.
        
        Args:
            provider_id: Provider ID
            access_token: Access token from the provider
            
        Returns:
            Tuple of (success, user_info, message)
        """
        provider = await self.get_provider(provider_id)
        if not provider:
            return False, {}, f"Unknown OAuth provider: {provider_id}"
        
        try:
            # Set up headers with the access token
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Add custom headers for specific providers
            if provider.provider_type == "github":
                # GitHub API versioning
                headers["Accept"] = "application/vnd.github.v3+json"
            
            # Make the user info request
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    provider.userinfo_url, headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OAuth userinfo error: {error_text}")
                        return False, {}, f"Failed to get user info: {response.status}"
                    
                    user_info = await response.json()
            
            # Process provider-specific user info format
            processed_info = await self._process_user_info(provider, user_info)
            
            return True, processed_info, "User info retrieved successfully"
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return False, {}, f"Error getting user info: {str(e)}"
    
    async def _process_user_info(
        self, provider: OAuthProviderConfig, user_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process provider-specific user info into a standardized format.
        
        Args:
            provider: Provider configuration
            user_info: Raw user info from the provider
            
        Returns:
            Standardized user info dictionary
        """
        result = {
            "provider_id": provider.id,
            "provider_user_id": "",
            "email": "",
            "username": "",
            "name": "",
            "avatar_url": "",
            "profile_url": "",
            "raw_info": user_info,
        }
        
        # Process provider-specific formats
        if provider.provider_type == "github":
            result["provider_user_id"] = str(user_info.get("id", ""))
            result["email"] = user_info.get("email", "")
            result["username"] = user_info.get("login", "")
            result["name"] = user_info.get("name", "")
            result["avatar_url"] = user_info.get("avatar_url", "")
            result["profile_url"] = user_info.get("html_url", "")
            
            # If email not returned directly, get from email endpoint
            if not result["email"] and user_info.get("login"):
                # We'd typically make another API call to get verified emails
                # This is a placeholder - in a real implementation, you'd call:
                # GET /user/emails with the same access token
                result["email"] = f"{user_info.get('login')}@example.com"
        
        elif provider.provider_type == "google":
            result["provider_user_id"] = user_info.get("sub", "")
            result["email"] = user_info.get("email", "")
            result["username"] = user_info.get("email", "").split("@")[0]
            result["name"] = user_info.get("name", "")
            result["avatar_url"] = user_info.get("picture", "")
            result["profile_url"] = user_info.get("profile", "")
        
        elif provider.provider_type == "microsoft":
            result["provider_user_id"] = user_info.get("id", "")
            result["email"] = user_info.get("mail", user_info.get("userPrincipalName", ""))
            result["username"] = result["email"].split("@")[0] if result["email"] else ""
            result["name"] = user_info.get("displayName", "")
            # Microsoft Graph doesn't provide these directly
            result["avatar_url"] = ""
            result["profile_url"] = ""
        
        return result
    
    async def find_linked_user(
        self, provider_id: str, provider_user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find a user linked to an OAuth identity.
        
        Args:
            provider_id: Provider ID
            provider_user_id: User ID from the provider
            
        Returns:
            User data if found, None otherwise
        """
        user_data = await self._persistence.find_user_by_oauth(
            provider_id, provider_user_id
        )
        return user_data
    
    async def link_user_account(
        self, user_id: str, provider_id: str, provider_user_id: str, provider_data: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Link a user account to an OAuth identity.
        
        Args:
            user_id: Internal user ID
            provider_id: Provider ID
            provider_user_id: User ID from the provider
            provider_data: Additional provider-specific data
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Check if already linked
            existing = await self._persistence.find_oauth_connection(
                user_id, provider_id
            )
            
            if existing:
                # Update existing link
                await self._persistence.update_oauth_connection(
                    user_id, provider_id, provider_user_id, provider_data
                )
                return True, "OAuth connection updated"
            else:
                # Create new link
                await self._persistence.create_oauth_connection(
                    user_id, provider_id, provider_user_id, provider_data
                )
                return True, "OAuth connection created"
        except Exception as e:
            logger.error(f"Error linking user account: {e}")
            return False, f"Error linking account: {str(e)}"
    
    async def unlink_user_account(
        self, user_id: str, provider_id: str
    ) -> Tuple[bool, str]:
        """
        Unlink a user account from an OAuth identity.
        
        Args:
            user_id: Internal user ID
            provider_id: Provider ID
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Delete the OAuth connection
            deleted = await self._persistence.delete_oauth_connection(
                user_id, provider_id
            )
            
            if deleted:
                return True, "OAuth connection removed"
            else:
                return False, "OAuth connection not found"
        except Exception as e:
            logger.error(f"Error unlinking user account: {e}")
            return False, f"Error unlinking account: {str(e)}"
    
    async def get_user_oauth_connections(
        self, user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all OAuth connections for a user.
        
        Args:
            user_id: Internal user ID
            
        Returns:
            List of OAuth connection data
        """
        try:
            connections = await self._persistence.get_user_oauth_connections(user_id)
            return connections
        except Exception as e:
            logger.error(f"Error getting user OAuth connections: {e}")
            return []
    
    async def _initialize_default_providers(self) -> None:
        """Initialize default OAuth provider configurations."""
        # Default provider configurations
        default_providers = {
            "github": {
                "id": "github",
                "name": "GitHub",
                "provider_type": "github",
                "client_id": os.environ.get("GITHUB_CLIENT_ID", ""),
                "client_secret": os.environ.get("GITHUB_CLIENT_SECRET", ""),
                "authorize_url": "https://github.com/login/oauth/authorize",
                "token_url": "https://github.com/login/oauth/access_token",
                "userinfo_url": "https://api.github.com/user",
                "scope": "user:email",
                "active": bool(os.environ.get("GITHUB_CLIENT_ID", "")),
                "default_roles": ["user"],
            },
            "google": {
                "id": "google",
                "name": "Google",
                "provider_type": "google",
                "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
                "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
                "authorize_url": "https://accounts.google.com/o/oauth2/auth",
                "token_url": "https://oauth2.googleapis.com/token",
                "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
                "scope": "openid email profile",
                "active": bool(os.environ.get("GOOGLE_CLIENT_ID", "")),
                "default_roles": ["user"],
            },
            "microsoft": {
                "id": "microsoft",
                "name": "Microsoft",
                "provider_type": "microsoft",
                "client_id": os.environ.get("MICROSOFT_CLIENT_ID", ""),
                "client_secret": os.environ.get("MICROSOFT_CLIENT_SECRET", ""),
                "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
                "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                "userinfo_url": "https://graph.microsoft.com/v1.0/me",
                "scope": "User.Read",
                "active": bool(os.environ.get("MICROSOFT_CLIENT_ID", "")),
                "default_roles": ["user"],
            },
        }
        
        # Save default providers to persistence
        for provider_id, config in default_providers.items():
            await self._persistence.save_oauth_provider(provider_id, config)
        
        logger.info("Initialized default OAuth providers")


# Singleton instance
_oauth_manager_instance = None

def get_oauth_manager() -> OAuthManager:
    """
    Get or create the OAuth manager singleton instance.
    
    Returns:
        OAuthManager instance
    """
    global _oauth_manager_instance
    if _oauth_manager_instance is None:
        _oauth_manager_instance = OAuthManager()
    return _oauth_manager_instance