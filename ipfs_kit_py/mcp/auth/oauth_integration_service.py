"""
Authentication Service OAuth Integration

This module updates the AuthenticationService class to use the OAuth manager
for improved OAuth provider handling as specified in the MCP roadmap.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
from typing import Dict, Any, Optional, Tuple

from ipfs_kit_py.mcp.auth.service import AuthenticationService
from ipfs_kit_py.mcp.auth.oauth_manager import get_oauth_manager

logger = logging.getLogger(__name__)


async def get_oauth_login_url(
    self, provider_id: str, redirect_uri: str, state: Optional[str] = None
) -> Tuple[bool, Dict[str, Any], str]:
    """
    Get an OAuth login URL for a provider.
    
    This method uses the OAuth manager for improved provider handling.
    
    Args:
        provider_id: OAuth provider ID
        redirect_uri: Redirect URI for the OAuth flow
        state: Optional state parameter for CSRF protection
        
    Returns:
        Tuple of (success, result, message)
    """
    try:
        # Get OAuth manager
        oauth_manager = get_oauth_manager()
        
        # Create authorization URL
        success, result, message = await oauth_manager.create_authorization_url(
            provider_id, redirect_uri, state
        )
        
        return success, result, message
    except Exception as e:
        logger.error(f"Error getting OAuth login URL: {e}")
        return False, {}, f"Error getting OAuth login URL: {str(e)}"


async def process_oauth_callback_improved(
    self,
    provider_id: str,
    code: str,
    redirect_uri: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Tuple[bool, Dict[str, Any], str]:
    """
    Process an OAuth callback and authenticate the user.
    
    This implementation uses the OAuth manager for improved provider handling
    and user account linking.
    
    Args:
        provider_id: OAuth provider ID
        code: Authorization code from provider
        redirect_uri: Redirect URI used in the authorization request
        ip_address: Client IP address
        user_agent: Client user agent
        
    Returns:
        Tuple of (success, tokens, message)
    """
    try:
        from ipfs_kit_py.mcp.auth.audit import get_audit_logger
        
        # Get OAuth manager
        oauth_manager = get_oauth_manager()
        
        # Exchange code for token
        success, token_data, message = await oauth_manager.exchange_code_for_token(
            provider_id, code, redirect_uri
        )
        
        if not success:
            return False, {}, message
        
        # Get access token
        access_token = token_data.get("access_token")
        if not access_token:
            return False, {}, "No access token in OAuth response"
        
        # Get user info
        success, user_info, message = await oauth_manager.get_user_info(
            provider_id, access_token
        )
        
        if not success:
            return False, {}, message
        
        # Check email and provider user ID
        email = user_info.get("email", "")
        provider_user_id = user_info.get("provider_user_id", "")
        
        if not email:
            return False, {}, "Email not provided by OAuth provider"
        
        if not provider_user_id:
            return False, {}, "User ID not provided by OAuth provider"
        
        # Get provider details
        provider = await oauth_manager.get_provider(provider_id)
        if not provider:
            return False, {}, f"Provider {provider_id} not found"
        
        # Check domain restrictions if configured
        if provider.domain_restrictions:
            domain = email.split("@")[1] if "@" in email else ""
            if domain not in provider.domain_restrictions:
                return False, {}, f"Email domain not allowed: {domain}"
        
        # Try to find existing OAuth link
        existing_user = await oauth_manager.find_linked_user(provider_id, provider_user_id)
        
        # If user exists, use that account
        if existing_user:
            user_dict = existing_user
            is_new_user = False
            
            # Get user from the user store for complete data
            user = await self.get_user(existing_user.get("id"))
            
            # Update last login
            user.last_login = time.time()
            
            # Update user metadata
            metadata = user.metadata.copy() if user.metadata else {}
            metadata["last_oauth_login"] = time.time()
            
            # Update user in store
            user_dict = user.dict()
            user_dict.update({"last_login": user.last_login, "metadata": metadata})
            await self.user_store.update(user.id, user_dict)
            
            # Log OAuth login
            audit_logger = get_audit_logger()
            await audit_logger.log_oauth_login(
                user_id=user.id,
                provider_id=provider_id,
                provider_user_id=provider_user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
        else:
            # Try to find user by email
            user = await self.get_user_by_email(email)
            
            if user:
                # User exists but not linked - link the accounts
                success, message = await oauth_manager.link_user_account(
                    user.id, provider_id, provider_user_id, user_info
                )
                
                if not success:
                    return False, {}, f"Failed to link account: {message}"
                
                is_new_user = False
                
                # Update last login
                user.last_login = time.time()
                
                # Update user metadata
                metadata = user.metadata.copy() if user.metadata else {}
                metadata["oauth_provider"] = provider_id
                metadata["oauth_id"] = provider_user_id
                metadata["last_oauth_login"] = time.time()
                
                # Update user in store
                user_dict = user.dict()
                user_dict.update({"last_login": user.last_login, "metadata": metadata})
                await self.user_store.update(user.id, user_dict)
                
                # Log OAuth link
                audit_logger = get_audit_logger()
                await audit_logger.log_oauth_link(
                    user_id=user.id,
                    provider_id=provider_id,
                    provider_user_id=provider_user_id,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
            else:
                # Create new user from OAuth data
                username = email.split("@")[0]
                
                # Ensure username is unique by appending numbers if needed
                base_username = username
                counter = 1
                while await self.user_store.get_by_username(username):
                    username = f"{base_username}{counter}"
                    counter += 1
                
                # Create user with OAuth metadata
                user = User(
                    username=username,
                    email=email,
                    full_name=user_info.get("name", ""),
                    roles=set(provider.default_roles),
                    metadata={
                        "oauth_provider": provider_id,
                        "oauth_id": provider_user_id,
                        "oauth_created": time.time(),
                        "last_oauth_login": time.time(),
                    }
                )
                
                # Save user
                success = await self.user_store.create(user.id, user.dict())
                if not success:
                    return False, {}, "Failed to create user from OAuth data"
                
                # Link the OAuth account to the new user
                success, message = await oauth_manager.link_user_account(
                    user.id, provider_id, provider_user_id, user_info
                )
                
                if not success:
                    # This shouldn't happen but log it just in case
                    logger.warning(f"Failed to link new user account: {message}")
                
                logger.info(f"Created new user from OAuth: {user.username} ({user.id})")
                is_new_user = True
                user_dict = user.dict()
                
                # Log OAuth registration
                audit_logger = get_audit_logger()
                await audit_logger.log_oauth_login(
                    user_id=user.id,
                    provider_id=provider_id,
                    provider_user_id=provider_user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    is_new_user=True
                )
        
        # Create session
        session = await self.create_session(user, ip_address, user_agent)
        
        # Create tokens
        access_token = await self.create_access_token(user, session)
        refresh_token = await self.create_refresh_token(user, session)
        
        return (
            True,
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": self.token_expire_minutes * 60,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "roles": list(user.roles),
                    "oauth_provider": provider_id,
                },
                "is_new_user": is_new_user,
                "user_info": user_info,
            },
            "OAuth login successful",
        )
    except Exception as e:
        logger.error(f"OAuth error: {str(e)}")
        return False, {}, f"OAuth processing error: {str(e)}"


async def _load_oauth_providers_improved(self) -> Dict[str, Dict]:
    """
    Load all OAuth provider configurations using the OAuth manager.
    
    Returns:
        Dictionary of provider ID to provider config
    """
    try:
        # Get OAuth manager
        oauth_manager = get_oauth_manager()
        
        # Load providers
        providers = await oauth_manager.load_providers()
        
        # Convert to dictionary format
        result = {
            provider_id: provider.dict()
            for provider_id, provider in providers.items()
        }
        
        return result
    except Exception as e:
        logger.error(f"Error loading OAuth providers: {e}")
        return {}


def patch_authentication_service():
    """
    Patch the AuthenticationService with improved OAuth methods.
    
    This function replaces the placeholder OAuth methods in the AuthenticationService
    with the improved implementations that use the OAuth manager.
    """
    # Import necessary modules
    import time
    from ipfs_kit_py.mcp.auth.models import User
    
    # Add required imports to the module
    globals()["time"] = time
    globals()["User"] = User
    
    # Replace methods
    AuthenticationService.get_oauth_login_url = get_oauth_login_url
    AuthenticationService.process_oauth_callback = process_oauth_callback_improved
    AuthenticationService._load_oauth_providers = _load_oauth_providers_improved
    
    logger.info("Patched AuthenticationService with improved OAuth methods")