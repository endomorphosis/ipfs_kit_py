#!/usr/bin/env python3
# ipfs_kit_py/mcp/auth/oauth_integration.py

"""
OAuth Integration for IPFS Kit MCP Server.

This module provides OAuth 2.0 integration for authentication, allowing users to
authenticate using various OAuth providers (Google, GitHub, etc.).
"""

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable

import requests

# Set up logging
logger = logging.getLogger(__name__)


class OAuthProvider(Enum):
    """Supported OAuth providers."""
    GOOGLE = "google"
    GITHUB = "github"
    MICROSOFT = "microsoft"
    GITLAB = "gitlab"
    CUSTOM = "custom"


@dataclass
class OAuthConfig:
    """Configuration for an OAuth provider."""
    provider: OAuthProvider
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    user_info_url: str
    scope: str
    redirect_uri: str
    user_id_field: str = "id"
    user_name_field: str = "name"
    user_email_field: str = "email"
    extra_params: Dict[str, str] = field(default_factory=dict)
    

@dataclass
class OAuthToken:
    """OAuth token information."""
    access_token: str
    refresh_token: Optional[str]
    token_type: str
    expires_at: Optional[float]
    scope: Optional[str] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if the token has expired."""
        if self.expires_at is None:
            return False
        # Add a small buffer (30 seconds) to account for network latency
        return time.time() > (self.expires_at - 30)


@dataclass
class OAuthUserInfo:
    """User information from an OAuth provider."""
    provider: OAuthProvider
    provider_user_id: str
    username: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    profile_url: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


class OAuthStateManager:
    """Manages OAuth state for CSRF protection."""
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize the OAuth state manager.
        
        Args:
            storage_path: Optional path to store state information
        """
        self.states: Dict[str, Dict[str, Any]] = {}
        self.storage_path = storage_path
        
        # Load states from storage if available
        if storage_path and os.path.exists(storage_path):
            try:
                with open(storage_path, 'r') as f:
                    self.states = json.load(f)
                # Clean up expired states
                self._cleanup_expired()
            except Exception as e:
                logger.error(f"Error loading OAuth states: {e}")
    
    def _save_states(self):
        """Save states to storage."""
        if not self.storage_path:
            return
        
        try:
            # Remove expired states before saving
            self._cleanup_expired()
            
            with open(self.storage_path, 'w') as f:
                json.dump(self.states, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving OAuth states: {e}")
    
    def _cleanup_expired(self):
        """Clean up expired states."""
        now = time.time()
        expired_states = [
            state for state, data in self.states.items() 
            if data.get('expires_at', 0) < now
        ]
        
        for state in expired_states:
            del self.states[state]
    
    def create_state(self, extra_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new state string.
        
        Args:
            extra_data: Optional extra data to associate with the state
        
        Returns:
            str: State string
        """
        state = str(uuid.uuid4())
        
        # Store state with expiration (10 minutes)
        self.states[state] = {
            'created_at': time.time(),
            'expires_at': time.time() + 600,  # 10 minutes
            'extra_data': extra_data or {}
        }
        
        # Save to storage
        self._save_states()
        
        return state
    
    def validate_state(self, state: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Validate a state string.
        
        Args:
            state: State string to validate
        
        Returns:
            Tuple[bool, Optional[Dict[str, Any]]]: 
                (is_valid, extra_data) tuple
        """
        if state not in self.states:
            return False, None
        
        state_data = self.states[state]
        
        # Check if state has expired
        if state_data.get('expires_at', 0) < time.time():
            del self.states[state]
            self._save_states()
            return False, None
        
        # Remove used state
        extra_data = state_data.get('extra_data', {})
        del self.states[state]
        self._save_states()
        
        return True, extra_data


class OAuthManager:
    """
    Manages OAuth integrations.
    
    This class handles OAuth flow, token management, and user information
    retrieval from various OAuth providers.
    """
    
    def __init__(self, state_storage_path: Optional[str] = None):
        """
        Initialize the OAuth manager.
        
        Args:
            state_storage_path: Optional path to store OAuth states
        """
        self.providers: Dict[str, OAuthConfig] = {}
        self.state_manager = OAuthStateManager(state_storage_path)
        self.token_cache: Dict[str, OAuthToken] = {}
        
        # Load predefined providers
        self._load_predefined_providers()
    
    def _load_predefined_providers(self):
        """Load configurations for predefined OAuth providers."""
        # This would typically come from a configuration file
        # Here's an example for GitHub
        github_config = OAuthConfig(
            provider=OAuthProvider.GITHUB,
            client_id=os.environ.get("GITHUB_CLIENT_ID", ""),
            client_secret=os.environ.get("GITHUB_CLIENT_SECRET", ""),
            authorize_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            user_info_url="https://api.github.com/user",
            scope="read:user user:email",
            redirect_uri=os.environ.get("OAUTH_REDIRECT_URI", "http://localhost:8000/auth/callback"),
            user_id_field="id",
            user_name_field="login",
            user_email_field="email"
        )
        
        # Only add the provider if both client ID and secret are set
        if github_config.client_id and github_config.client_secret:
            self.register_provider(github_config)
    
    def register_provider(self, config: OAuthConfig):
        """
        Register an OAuth provider.
        
        Args:
            config: OAuth provider configuration
        """
        self.providers[config.provider.value] = config
    
    def get_provider_config(self, provider: Union[str, OAuthProvider]) -> Optional[OAuthConfig]:
        """
        Get configuration for a provider.
        
        Args:
            provider: Provider name or enum
        
        Returns:
            Optional[OAuthConfig]: Provider configuration or None if not found
        """
        if isinstance(provider, OAuthProvider):
            provider_name = provider.value
        else:
            provider_name = provider
        
        return self.providers.get(provider_name)
    
    def get_authorization_url(self, provider: Union[str, OAuthProvider], 
                             extra_params: Optional[Dict[str, str]] = None,
                             state_data: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """
        Get the authorization URL for an OAuth provider.
        
        Args:
            provider: Provider name or enum
            extra_params: Additional parameters to include in the authorization URL
            state_data: Optional data to associate with the state
        
        Returns:
            Tuple[str, str]: (authorization_url, state) tuple
        
        Raises:
            ValueError: If the provider is not registered
        """
        config = self.get_provider_config(provider)
        if not config:
            raise ValueError(f"OAuth provider '{provider}' not registered")
        
        # Create a state parameter for CSRF protection
        state = self.state_manager.create_state(state_data)
        
        # Build query parameters
        params = {
            'client_id': config.client_id,
            'redirect_uri': config.redirect_uri,
            'scope': config.scope,
            'state': state,
            'response_type': 'code'
        }
        
        # Add provider-specific extra parameters
        if config.extra_params:
            params.update(config.extra_params)
        
        # Add caller-specified extra parameters
        if extra_params:
            params.update(extra_params)
        
        # Build the authorization URL
        url = f"{config.authorize_url}"
        query = "&".join([f"{k}={requests.utils.quote(str(v))}" for k, v in params.items()])
        if "?" in url:
            url = f"{url}&{query}"
        else:
            url = f"{url}?{query}"
        
        return url, state
    
    def exchange_code_for_token(self, provider: Union[str, OAuthProvider], code: str, 
                               state: Optional[str] = None, 
                               expected_state: Optional[str] = None) -> Tuple[bool, Optional[OAuthToken], Optional[Dict[str, Any]]]:
        """
        Exchange an authorization code for an access token.
        
        Args:
            provider: Provider name or enum
            code: Authorization code from the OAuth provider
            state: State parameter from the callback
            expected_state: Expected state parameter (if not using state manager)
        
        Returns:
            Tuple[bool, Optional[OAuthToken], Optional[Dict[str, Any]]]: 
                (success, token, state_data) tuple
        """
        config = self.get_provider_config(provider)
        if not config:
            logger.error(f"OAuth provider '{provider}' not registered")
            return False, None, None
        
        # Validate state if provided
        state_data = None
        if state:
            if expected_state:
                # Manual state validation
                if state != expected_state:
                    logger.error("OAuth state mismatch")
                    return False, None, None
            else:
                # Use state manager
                is_valid, state_data = self.state_manager.validate_state(state)
                if not is_valid:
                    logger.error("Invalid or expired OAuth state")
                    return False, None, None
        
        # Prepare token request
        token_params = {
            'client_id': config.client_id,
            'client_secret': config.client_secret,
            'code': code,
            'redirect_uri': config.redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        headers = {'Accept': 'application/json'}
        
        try:
            # Request access token
            response = requests.post(
                config.token_url,
                data=token_params,
                headers=headers
            )
            response.raise_for_status()
            
            # Parse response
            if 'application/json' in response.headers.get('Content-Type', ''):
                token_data = response.json()
            else:
                # Handle form-encoded response (some providers use this)
                from urllib.parse import parse_qs
                token_data = parse_qs(response.text)
                # Convert lists to single values
                token_data = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in token_data.items()}
            
            # Extract token information
            access_token = token_data.get('access_token')
            if not access_token:
                logger.error("No access token in OAuth response")
                return False, None, state_data
            
            # Calculate token expiration
            expires_in = token_data.get('expires_in')
            expires_at = None
            if expires_in and isinstance(expires_in, (int, str)):
                try:
                    expires_at = time.time() + int(expires_in)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid expires_in value: {expires_in}")
            
            # Create token object
            token = OAuthToken(
                access_token=access_token,
                refresh_token=token_data.get('refresh_token'),
                token_type=token_data.get('token_type', 'Bearer'),
                expires_at=expires_at,
                scope=token_data.get('scope')
            )
            
            # Cache the token if we have a user ID in state_data
            if state_data and 'user_id' in state_data:
                user_id = state_data['user_id']
                provider_key = config.provider.value
                self.token_cache[f"{user_id}:{provider_key}"] = token
            
            return True, token, state_data
            
        except requests.RequestException as e:
            logger.error(f"Error exchanging OAuth code for token: {e}")
            return False, None, state_data
    
    def get_user_info(self, provider: Union[str, OAuthProvider], 
                     token: OAuthToken) -> Optional[OAuthUserInfo]:
        """
        Get user information from an OAuth provider.
        
        Args:
            provider: Provider name or enum
            token: OAuth token
        
        Returns:
            Optional[OAuthUserInfo]: User information or None if failed
        """
        config = self.get_provider_config(provider)
        if not config:
            logger.error(f"OAuth provider '{provider}' not registered")
            return None
        
        # Check if token is expired
        if token.is_expired:
            logger.error("OAuth token is expired")
            return None
        
        # Prepare request
        headers = {
            'Authorization': f"{token.token_type} {token.access_token}",
            'Accept': 'application/json'
        }
        
        try:
            # Request user information
            response = requests.get(
                config.user_info_url,
                headers=headers
            )
            response.raise_for_status()
            
            # Parse response
            user_data = response.json()
            
            # Extract user information
            user_id = str(user_data.get(config.user_id_field, ''))
            if not user_id:
                logger.error(f"No user ID field '{config.user_id_field}' in OAuth response")
                return None
            
            username = user_data.get(config.user_name_field, '')
            email = user_data.get(config.user_email_field)
            
            # Some providers (like GitHub) may not include email in the user info
            # In that case, we might need to make additional requests
            if not email and config.provider == OAuthProvider.GITHUB:
                # GitHub requires a separate request for email
                email_response = requests.get(
                    'https://api.github.com/user/emails',
                    headers=headers
                )
                if email_response.status_code == 200:
                    emails = email_response.json()
                    primary_emails = [e['email'] for e in emails if e.get('primary')]
                    if primary_emails:
                        email = primary_emails[0]
            
            # Create user info object
            user_info = OAuthUserInfo(
                provider=config.provider if isinstance(config.provider, OAuthProvider) 
                         else OAuthProvider(config.provider),
                provider_user_id=user_id,
                username=username,
                email=email,
                display_name=user_data.get('name'),
                avatar_url=user_data.get('avatar_url'),
                profile_url=user_data.get('html_url'),
                raw_data=user_data
            )
            
            return user_info
            
        except requests.RequestException as e:
            logger.error(f"Error getting OAuth user info: {e}")
            return None
    
    def refresh_token(self, provider: Union[str, OAuthProvider], 
                     refresh_token: str) -> Optional[OAuthToken]:
        """
        Refresh an OAuth token.
        
        Args:
            provider: Provider name or enum
            refresh_token: Refresh token
        
        Returns:
            Optional[OAuthToken]: New token or None if failed
        """
        config = self.get_provider_config(provider)
        if not config:
            logger.error(f"OAuth provider '{provider}' not registered")
            return None
        
        # Prepare refresh request
        refresh_params = {
            'client_id': config.client_id,
            'client_secret': config.client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
        
        headers = {'Accept': 'application/json'}
        
        try:
            # Request new token
            response = requests.post(
                config.token_url,
                data=refresh_params,
                headers=headers
            )
            response.raise_for_status()
            
            # Parse response
            if 'application/json' in response.headers.get('Content-Type', ''):
                token_data = response.json()
            else:
                # Handle form-encoded response
                from urllib.parse import parse_qs
                token_data = parse_qs(response.text)
                token_data = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in token_data.items()}
            
            # Extract token information
            access_token = token_data.get('access_token')
            if not access_token:
                logger.error("No access token in OAuth refresh response")
                return None
            
            # Get new refresh token or keep the old one
            new_refresh_token = token_data.get('refresh_token', refresh_token)
            
            # Calculate token expiration
            expires_in = token_data.get('expires_in')
            expires_at = None
            if expires_in and isinstance(expires_in, (int, str)):
                try:
                    expires_at = time.time() + int(expires_in)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid expires_in value: {expires_in}")
            
            # Create token object
            token = OAuthToken(
                access_token=access_token,
                refresh_token=new_refresh_token,
                token_type=token_data.get('token_type', 'Bearer'),
                expires_at=expires_at,
                scope=token_data.get('scope')
            )
            
            return token
            
        except requests.RequestException as e:
            logger.error(f"Error refreshing OAuth token: {e}")
            return None


class OAuthUserManager:
    """
    Manages users authenticated through OAuth.
    
    This class handles mapping between OAuth user information and
    internal system users.
    """
    
    def __init__(self, oauth_manager: OAuthManager, default_roles: List[str] = None):
        """
        Initialize the OAuth user manager.
        
        Args:
            oauth_manager: OAuth manager instance
            default_roles: Default roles to assign to new users
        """
        self.oauth_manager = oauth_manager
        self.default_roles = default_roles or ["user"]
        self.user_mappings: Dict[str, Dict[str, Any]] = {}
        
        # Load user mappings from storage (in a real implementation)
        # self._load_user_mappings()
    
    def get_mapping_key(self, provider: OAuthProvider, provider_user_id: str) -> str:
        """
        Get a mapping key for an OAuth user.
        
        Args:
            provider: OAuth provider
            provider_user_id: User ID from the provider
        
        Returns:
            str: Mapping key
        """
        return f"{provider.value}:{provider_user_id}"
    
    def get_user_for_oauth(self, user_info: OAuthUserInfo) -> Dict[str, Any]:
        """
        Get or create a user for an OAuth user.
        
        Args:
            user_info: OAuth user information
        
        Returns:
            Dict[str, Any]: User information
        """
        mapping_key = self.get_mapping_key(user_info.provider, user_info.provider_user_id)
        
        # Check if user already exists
        if mapping_key in self.user_mappings:
            user_data = self.user_mappings[mapping_key]
            
            # Update user data with latest information
            user_data['last_login'] = time.time()
            user_data['oauth_info'] = {
                'provider': user_info.provider.value,
                'provider_user_id': user_info.provider_user_id,
                'username': user_info.username,
                'email': user_info.email,
                'display_name': user_info.display_name,
                'avatar_url': user_info.avatar_url,
                'profile_url': user_info.profile_url
            }
            
            return user_data
        
        # Create a new user
        user_id = str(uuid.uuid4())
        user_data = {
            'user_id': user_id,
            'username': user_info.username,
            'email': user_info.email,
            'display_name': user_info.display_name or user_info.username,
            'roles': self.default_roles,
            'created_at': time.time(),
            'last_login': time.time(),
            'oauth_info': {
                'provider': user_info.provider.value,
                'provider_user_id': user_info.provider_user_id,
                'username': user_info.username,
                'email': user_info.email,
                'display_name': user_info.display_name,
                'avatar_url': user_info.avatar_url,
                'profile_url': user_info.profile_url
            }
        }
        
        # Store the mapping
        self.user_mappings[mapping_key] = user_data
        
        # Save user mappings (in a real implementation)
        # self._save_user_mappings()
        
        return user_data


# Create global instances for convenience (for simple cases)
oauth_manager = OAuthManager()
oauth_user_manager = OAuthUserManager(oauth_manager)


def example_oauth_flow():
    """Example of the OAuth flow."""
    # Register OAuth providers (in a real application, this would come from configuration)
    # Here we'll just use the predefined GitHub provider from _load_predefined_providers
    
    # Step 1: Get the authorization URL
    try:
        auth_url, state = oauth_manager.get_authorization_url(
            OAuthProvider.GITHUB,
            state_data={'redirect_after_login': '/dashboard'}
        )
        print(f"1. Authorization URL: {auth_url}")
        print(f"   State: {state}")
        
        # In a real application, redirect the user to auth_url
        
        # Step 2: Handle the callback (after user authorizes)
        # The callback would receive 'code' and 'state' parameters
        # Here we'll just simulate it with dummy values
        code = "dummy_code"  # In a real app, this comes from the OAuth callback
        
        # Step 3: Exchange the code for an access token
        success, token, state_data = oauth_manager.exchange_code_for_token(
            OAuthProvider.GITHUB,
            code,
            state=state
        )
        
        if success and token:
            print(f"2. Got access token: {token.access_token[:10]}...")
            print(f"   Token expires at: {token.expires_at}")
            print(f"   State data: {state_data}")
            
            # Step 4: Get user information
            user_info = oauth_manager.get_user_info(OAuthProvider.GITHUB, token)
            if user_info:
                print(f"3. User info:")
                print(f"   Provider: {user_info.provider.value}")
                print(f"   Provider user ID: {user_info.provider_user_id}")
                print(f"   Username: {user_info.username}")
                print(f"   Email: {user_info.email}")
                
                # Step 5: Get or create a user
                user = oauth_user_manager.get_user_for_oauth(user_info)
                print(f"4. System user:")
                print(f"   User ID: {user['user_id']}")
                print(f"   Username: {user['username']}")
                print(f"   Roles: {user['roles']}")
                
                # Step 6: In a real application, create a session or JWT token
                print(f"5. User authenticated successfully!")
                print(f"   Redirect to: {state_data.get('redirect_after_login', '/')}")
            else:
                print("3. Failed to get user information")
        else:
            print("2. Failed to exchange code for token")
            
    except ValueError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Run the example if environment variables are set
    if os.environ.get("GITHUB_CLIENT_ID") and os.environ.get("GITHUB_CLIENT_SECRET"):
        example_oauth_flow()
    else:
        print("Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET environment variables to run the example.")
        print("Also set OAUTH_REDIRECT_URI if needed (defaults to http://localhost:8000/auth/callback).")