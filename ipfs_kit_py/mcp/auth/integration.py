"""
OAuth Integration Module for MCP Server.

This module integrates the enhanced OAuth security with the MCP authentication service.
It provides a cleaner API for OAuth operations and implements security best practices.
"""

import logging
import time
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
import json
import os

from .oauth_security import (
    OAuthSecurityManager,
    OAuthProviderConfig,
    OAuthStateData,
    build_oauth_callback_url
)

# Configure logging
logger = logging.getLogger(__name__)

class OAuthIntegrationManager:
    """
    Manages OAuth provider integration and authentication flows.
    
    This class provides a simplified API for OAuth operations and ensures
    that all security best practices are followed.
    """
    
    def __init__(self, auth_service, config_path: Optional[str] = None, redis_client=None):
        """
        Initialize the OAuth integration manager.
        
        Args:
            auth_service: Authentication service instance
            config_path: Path to OAuth provider configuration file
            redis_client: Optional Redis client for distributed state storage
        """
        self.auth_service = auth_service
        self.config_path = config_path or os.environ.get(
            "OAUTH_CONFIG_PATH", 
            str(Path.home() / ".ipfs_kit" / "oauth_providers.json")
        )
        
        # Initialize security manager
        self.security_manager = OAuthSecurityManager(redis_client=redis_client)
        
        # Provider configuration cache
        self.providers: Dict[str, OAuthProviderConfig] = {}
        
        # Tracking for initialization
        self.initialized = False
    
    async def initialize(self):
        """Initialize the OAuth integration manager."""
        if self.initialized:
            return
        
        logger.info("Initializing OAuth integration manager")
        
        # Load provider configurations
        await self._load_provider_configs()
        
        self.initialized = True
        logger.info(f"OAuth integration manager initialized with {len(self.providers)} providers")
    
    async def _load_provider_configs(self):
        """Load OAuth provider configurations."""
        try:
            # First check config file
            config_path = Path(self.config_path)
            if config_path.exists():
                with open(config_path, 'r') as f:
                    provider_data = json.load(f)
                    
                for provider_id, config in provider_data.items():
                    try:
                        # Create provider config object
                        provider = OAuthProviderConfig(**config)
                        if provider.active:
                            self.providers[provider_id] = provider
                            logger.info(f"Loaded OAuth provider: {provider_id}")
                    except Exception as e:
                        logger.error(f"Error loading OAuth provider {provider_id}: {e}")
            else:
                logger.warning(f"OAuth config file not found: {self.config_path}")
                
            # If no providers loaded from file, add default development providers
            if not self.providers and os.environ.get("ENVIRONMENT") in ["development", "testing"]:
                logger.info("Adding default development OAuth providers")
                self._add_development_providers()
                
        except Exception as e:
            logger.error(f"Error loading OAuth provider configurations: {e}")
    
    def _add_development_providers(self):
        """Add default providers for development/testing environments."""
        try:
            # GitHub example
            self.providers["github"] = OAuthProviderConfig(
                id="github",
                name="GitHub",
                provider_type="github",
                client_id=os.environ.get("GITHUB_CLIENT_ID", "github_development_client_id"),
                client_secret=os.environ.get("GITHUB_CLIENT_SECRET", "github_development_client_secret"),
                authorize_url="https://github.com/login/oauth/authorize",
                token_url="https://github.com/login/oauth/access_token",
                userinfo_url="https://api.github.com/user",
                scope="user:email",
                active=True,
                default_roles=["user"],
                domain_restrictions=None,
                allowed_redirect_domains=[".localhost", "127.0.0.1"]
            )
            
            # Google example
            self.providers["google"] = OAuthProviderConfig(
                id="google",
                name="Google",
                provider_type="openid_connect",
                client_id=os.environ.get("GOOGLE_CLIENT_ID", "google_development_client_id"),
                client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", "google_development_client_secret"),
                authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
                token_url="https://oauth2.googleapis.com/token",
                userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
                scope="openid email profile",
                active=True,
                default_roles=["user"],
                domain_restrictions=None,
                jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
                trusted_issuers=["https://accounts.google.com"],
                user_id_claim="sub",
                email_claim="email",
                name_claim="name",
                pkce_required=True,
                allowed_redirect_domains=[".localhost", "127.0.0.1"]
            )
            
            logger.info("Added development OAuth providers")
        except Exception as e:
            logger.error(f"Error adding development providers: {e}")
    
    async def get_provider(self, provider_id: str) -> Optional[OAuthProviderConfig]:
        """
        Get OAuth provider configuration.
        
        Args:
            provider_id: OAuth provider ID
            
        Returns:
            Provider configuration or None if not found
        """
        if not self.initialized:
            await self.initialize()
            
        return self.providers.get(provider_id)
    
    async def get_available_providers(self) -> List[Dict[str, Any]]:
        """
        Get list of available OAuth providers.
        
        Returns:
            List of provider info dicts (id, name, type)
        """
        if not self.initialized:
            await self.initialize()
            
        return [
            {
                "id": p.id,
                "name": p.name, 
                "type": p.provider_type
            } 
            for p in self.providers.values()
        ]
    
    async def create_authorization_url(
        self,
        provider_id: str,
        redirect_uri: str,
        additional_params: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Create an authorization URL for OAuth flow initiation.
        
        Args:
            provider_id: OAuth provider ID
            redirect_uri: Redirect URI after authorization
            additional_params: Additional URL parameters
            
        Returns:
            Tuple of (success, data, error_message)
        """
        try:
            if not self.initialized:
                await self.initialize()
                
            # Get provider configuration
            provider = await self.get_provider(provider_id)
            if not provider:
                return False, {}, f"Unknown OAuth provider: {provider_id}"
                
            # Determine if PKCE should be used
            use_pkce = provider.pkce_required or provider.provider_type == "openid_connect"
            
            # Create authorization URL
            auth_url, state = await self.security_manager.create_authorization_url(
                provider=provider,
                redirect_uri=redirect_uri,
                use_pkce=use_pkce,
                additional_params=additional_params
            )
            
            return True, {
                "authorization_url": auth_url,
                "state": state,
                "provider_id": provider_id,
                "provider_name": provider.name
            }, ""
            
        except ValueError as e:
            logger.warning(f"OAuth authorization URL error: {e}")
            return False, {}, str(e)
        except Exception as e:
            logger.error(f"Error creating OAuth authorization URL: {e}")
            return False, {}, f"Error creating authorization URL: {str(e)}"
    
    async def process_callback(
        self,
        provider_id: str,
        code: str,
        state: str,
        redirect_uri: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Process OAuth callback and authenticate user.
        
        Args:
            provider_id: OAuth provider ID
            code: Authorization code
            state: State parameter from callback
            redirect_uri: Redirect URI
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            Tuple of (success, auth_data, error_message)
        """
        try:
            if not self.initialized:
                await self.initialize()
                
            # Get provider configuration
            provider = await self.get_provider(provider_id)
            if not provider:
                return False, {}, f"Unknown OAuth provider: {provider_id}"
                
            # Validate state parameter
            valid, state_data, error = await self.security_manager.validate_callback(state)
            if not valid:
                return False, {}, error
                
            # Convert state data
            state_obj = OAuthStateData(**state_data)
            
            # Verify provider matches
            if state_obj.provider_id != provider_id:
                return False, {}, "Provider ID mismatch in state"
                
            # Use the original redirect URI from state if not provided
            if not redirect_uri:
                redirect_uri = state_obj.redirect_uri
                
            # Exchange code for token
            success, token_data, error = await self.security_manager.exchange_code_for_token(
                provider=provider,
                code=code,
                redirect_uri=redirect_uri,
                code_verifier=state_obj.pkce_code_verifier
            )
            
            if not success:
                return False, {}, error
                
            # Extract tokens
            access_token = token_data.get("access_token")
            id_token = token_data.get("id_token")
            
            # Verify id_token if present (for OpenID Connect)
            id_token_data = None
            if id_token and "openid" in provider.scope:
                valid, payload, error = await self.security_manager.verify_jwt_token(
                    token=id_token,
                    provider=provider,
                    expected_audience=provider.client_id,
                    expected_nonce=state_obj.nonce
                )
                
                if not valid:
                    logger.warning(f"ID token validation failed: {error}")
                    # Continue with user info endpoint as fallback
                else:
                    id_token_data = payload
            
            # Get user information
            success, userinfo, error = await self.security_manager.get_userinfo(
                provider=provider,
                access_token=access_token,
                id_token_data=id_token_data
            )
            
            if not success:
                return False, {}, error
                
            # Process authentication with the user data
            success, auth_result, message = await self._authenticate_oauth_user(
                provider=provider,
                userinfo=userinfo,
                ip_address=ip_address,
                user_agent=user_agent,
                token_data=token_data
            )
            
            return success, auth_result, message
            
        except Exception as e:
            logger.error(f"Error processing OAuth callback: {e}")
            return False, {}, f"OAuth callback error: {str(e)}"
    
    async def _authenticate_oauth_user(
        self,
        provider: OAuthProviderConfig,
        userinfo: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        token_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Authenticate a user based on OAuth user information.
        
        This handles user creation if needed and authentication token generation.
        
        Args:
            provider: OAuth provider configuration
            userinfo: User information from provider
            ip_address: Client IP address
            user_agent: Client user agent
            token_data: OAuth token data
            
        Returns:
            Tuple of (success, auth_data, message)
        """
        try:
            # Extract core user information
            user_id = userinfo.get("sub")
            email = userinfo.get("email")
            name = userinfo.get("name", "")
            
            if not user_id:
                return False, {}, "Missing user ID in OAuth response"
                
            # Create a unique identifier for this user from this provider
            oauth_unique_id = f"{provider.id}:{user_id}"
            
            # Get or create user
            user = None
            user_created = False
            
            # Search for existing user by OAuth ID in metadata
            users_by_oauth_id = await self.auth_service.user_store.find_by_metadata_field(
                field="oauth_id", 
                value=oauth_unique_id
            )
            if users_by_oauth_id:
                # User exists, get the first match
                user_dict = next(iter(users_by_oauth_id.values()))
                user = await self.auth_service.get_user(user_dict.get("id"))
            
            # If not found by OAuth ID, try email if available
            if not user and email:
                user = await self.auth_service.get_user_by_email(email)
                
            if user:
                # Existing user - update OAuth information
                user_dict = user.dict()
                
                # Update OAuth metadata
                metadata = user_dict.get("metadata", {}) or {}
                metadata["oauth_provider"] = provider.id
                metadata["oauth_id"] = oauth_unique_id
                metadata["last_oauth_login"] = time.time()
                
                # Add provider-specific metadata
                provider_key = f"oauth_{provider.id}"
                metadata[provider_key] = {
                    "id": user_id,
                    "email": email,
                    "name": name,
                    "last_login": time.time()
                }
                
                # If we have token data, store refresh token if available
                if token_data and token_data.get("refresh_token"):
                    if "oauth_tokens" not in metadata:
                        metadata["oauth_tokens"] = {}
                    metadata["oauth_tokens"][provider.id] = {
                        "refresh_token": token_data.get("refresh_token"),
                        "expires_at": time.time() + token_data.get("expires_in", 3600)
                    }
                    
                # Update user
                user_dict["metadata"] = metadata
                user_dict["last_login"] = time.time()
                
                # If name is missing, update it
                if not user.full_name and name:
                    user_dict["full_name"] = name
                    
                # Update user in database
                await self.auth_service.user_store.update(user.id, user_dict)
            else:
                # New user - create from OAuth data
                
                # Generate a username from email or provider ID with user ID
                username = None
                if email:
                    # Use part before @ in email
                    username = email.split("@")[0]
                else:
                    # Use provider prefix with user ID
                    username = f"{provider.id}_{user_id}"
                    
                # Ensure username is unique by appending numbers if needed
                base_username = username
                counter = 1
                while await self.auth_service.user_store.get_by_username(username):
                    username = f"{base_username}{counter}"
                    counter += 1
                
                # Create metadata with OAuth information
                metadata = {
                    "oauth_provider": provider.id,
                    "oauth_id": oauth_unique_id,
                    "oauth_created": time.time(),
                    "last_oauth_login": time.time(),
                    f"oauth_{provider.id}": {
                        "id": user_id,
                        "email": email,
                        "name": name,
                        "created_at": time.time(),
                        "last_login": time.time()
                    }
                }
                
                # If we have token data, store refresh token if available
                if token_data and token_data.get("refresh_token"):
                    metadata["oauth_tokens"] = {
                        provider.id: {
                            "refresh_token": token_data.get("refresh_token"),
                            "expires_at": time.time() + token_data.get("expires_in", 3600)
                        }
                    }
                
                # Get roles from provider config
                roles = set(provider.default_roles)
                
                # Create user with OAuth data
                from .models import User
                user = User(
                    username=username,
                    email=email,
                    full_name=name,
                    roles=roles,
                    metadata=metadata,
                    # No password for OAuth users
                    hashed_password=None
                )
                
                # Mark as created via OAuth
                user.oauth_created = True
                
                # Save user
                success = await self.auth_service.user_store.create(user.id, user.dict())
                if not success:
                    return False, {}, "Failed to create user from OAuth data"
                
                logger.info(f"Created new user from OAuth ({provider.id}): {user.username} ({user.id})")
                user_created = True
            
            # Create session
            session = await self.auth_service.create_session(user, ip_address, user_agent)
            
            # Create tokens
            access_token = await self.auth_service.create_access_token(user, session)
            refresh_token = await self.auth_service.create_refresh_token(user, session)
            
            return (
                True,
                {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                    "expires_in": self.auth_service.token_expire_minutes * 60,
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "full_name": user.full_name,
                        "roles": list(user.roles),
                        "oauth_provider": provider.id,
                    },
                    "is_new_user": user_created,
                    "provider": {
                        "id": provider.id,
                        "name": provider.name
                    }
                },
                "OAuth login successful",
            )
            
        except Exception as e:
            logger.error(f"Error authenticating OAuth user: {e}")
            return False, {}, f"Authentication error: {str(e)}"