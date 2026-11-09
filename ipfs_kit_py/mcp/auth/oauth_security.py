"""
OAuth Security Enhancements for MCP Authentication Service.

This module implements enhanced security measures for OAuth integration
as specified in the MCP roadmap for Advanced Authentication & Authorization.
"""

import logging
import time
import secrets
import hashlib
import json
import urllib.parse
from typing import Dict, Any, Optional, Tuple, List
import aiohttp
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger(__name__)

class OAuthStateData(BaseModel):
    """Data stored in the state parameter for CSRF protection."""
    nonce: str
    redirect_uri: str
    created_at: float
    provider_id: str
    pkce_code_verifier: Optional[str] = None
    additional_params: Dict[str, Any] = {}

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
    token_endpoint_auth_method: str = "client_secret_post"
    jwks_uri: Optional[str] = None
    supported_algorithms: List[str] = ["HS256", "RS256"]
    additional_authorize_params: Dict[str, str] = {}
    additional_token_params: Dict[str, str] = {}
    user_id_claim: str = "sub"
    email_claim: str = "email"
    name_claim: str = "name"
    trusted_issuers: Optional[List[str]] = None
    pkce_required: bool = False
    allowed_redirect_domains: List[str] = []


class OAuthSecurityManager:
    """Manages security aspects of OAuth integration."""
    
    def __init__(self, state_timeout_seconds: int = 600, redis_client=None):
        """
        Initialize the OAuth security manager.
        
        Args:
            state_timeout_seconds: Timeout for state tokens in seconds
            redis_client: Optional Redis client for distributed state storage
        """
        self.state_timeout_seconds = state_timeout_seconds
        self.redis_client = redis_client
        # In-memory state store as fallback
        self._state_store = {}
        
    async def create_authorization_url(
        self, 
        provider: OAuthProviderConfig, 
        redirect_uri: str,
        use_pkce: bool = False,
        additional_params: Dict[str, Any] = None
    ) -> Tuple[str, str]:
        """
        Create an authorization URL with security enhancements.
        
        Args:
            provider: OAuth provider configuration
            redirect_uri: Redirect URI for the OAuth flow
            use_pkce: Whether to use PKCE
            additional_params: Additional parameters to include
            
        Returns:
            Tuple of (authorization_url, state)
        """
        # Validate redirect URI
        self._validate_redirect_uri(provider, redirect_uri)
        
        # Create a random state for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Create state data object
        state_data = OAuthStateData(
            nonce=secrets.token_urlsafe(16),
            redirect_uri=redirect_uri,
            created_at=time.time(),
            provider_id=provider.id,
            additional_params=additional_params or {}
        )
        
        # Handle PKCE if enabled
        code_verifier = None
        code_challenge = None
        code_challenge_method = None
        
        if use_pkce or provider.pkce_required:
            # Generate code verifier and challenge
            code_verifier = secrets.token_urlsafe(64)
            code_challenge = self._create_code_challenge(code_verifier)
            code_challenge_method = "S256"
            
            # Store code verifier in state data
            state_data.pkce_code_verifier = code_verifier
        
        # Store state data
        await self._store_state(state, state_data.dict())
        
        # Build authorization URL
        params = {
            "client_id": provider.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": provider.scope,
            "state": state,
        }
        
        # Add nonce as OpenID parameter if applicable
        if "openid" in provider.scope:
            params["nonce"] = state_data.nonce
            
        # Add PKCE parameters if enabled
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = code_challenge_method
            
        # Add provider-specific parameters
        params.update(provider.additional_authorize_params)
        
        # Add any additional parameters
        if additional_params:
            params.update(additional_params)
            
        # Construct full URL
        auth_url = f"{provider.authorize_url}?{urllib.parse.urlencode(params)}"
        
        return auth_url, state
    
    async def validate_callback(
        self, 
        state: str, 
        redirect_uri: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Validate the callback from an OAuth provider.
        
        Args:
            state: State parameter from the callback
            redirect_uri: Redirect URI for validation
            
        Returns:
            Tuple of (valid, state_data, error_message)
        """
        # Retrieve state data
        state_data = await self._get_state(state)
        
        if not state_data:
            return False, None, "Invalid or expired state parameter"
            
        # Convert to OAuthStateData object
        try:
            state_obj = OAuthStateData(**state_data)
        except Exception as e:
            logger.error(f"Error parsing state data: {e}")
            return False, None, "Invalid state data format"
            
        # Check state expiration
        if time.time() - state_obj.created_at > self.state_timeout_seconds:
            await self._delete_state(state)
            return False, None, "State parameter has expired"
            
        # Validate redirect URI if provided
        if redirect_uri and redirect_uri != state_obj.redirect_uri:
            logger.warning(f"Redirect URI mismatch: expected {state_obj.redirect_uri}, got {redirect_uri}")
            return False, None, "Redirect URI mismatch"
            
        # Delete state after successful validation (single use)
        await self._delete_state(state)
        
        return True, state_data, ""
        
    async def exchange_code_for_token(
        self,
        provider: OAuthProviderConfig,
        code: str,
        redirect_uri: str,
        code_verifier: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Exchange authorization code for token with security enhancements.
        
        Args:
            provider: OAuth provider configuration
            code: Authorization code
            redirect_uri: Redirect URI
            code_verifier: PKCE code verifier if used
            
        Returns:
            Tuple of (success, token_data, error_message)
        """
        # Build token request parameters
        token_params = {
            "client_id": provider.client_id,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }
        
        # Add client authentication
        if provider.token_endpoint_auth_method == "client_secret_post":
            token_params["client_secret"] = provider.client_secret
        
        # Add PKCE code verifier if provided
        if code_verifier:
            token_params["code_verifier"] = code_verifier
            
        # Add provider-specific parameters
        token_params.update(provider.additional_token_params)
        
        headers = {
            "Accept": "application/json",
            "User-Agent": "IPFS-Kit-MCP/1.0",
        }
        
        # Add client authentication in header if using basic auth
        if provider.token_endpoint_auth_method == "client_secret_basic":
            import base64
            auth_str = f"{provider.client_id}:{provider.client_secret}"
            encoded = base64.b64encode(auth_str.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
        
        try:
            async with aiohttp.ClientSession() as session:
                # Exchange code for token with proper error handling
                async with session.post(
                    provider.token_url, 
                    data=token_params, 
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OAuth token error ({response.status}): {error_text}")
                        return False, {}, f"Failed to exchange code: {response.status}"
                    
                    # Parse token response
                    content_type = response.headers.get("Content-Type", "")
                    if "application/json" in content_type:
                        token_data = await response.json()
                    elif "application/x-www-form-urlencoded" in content_type:
                        token_text = await response.text()
                        token_data = dict(urllib.parse.parse_qsl(token_text))
                    else:
                        # Try JSON first, then form-encoded
                        try:
                            token_data = await response.json()
                        except:
                            token_text = await response.text()
                            token_data = dict(urllib.parse.parse_qsl(token_text))
                    
                    # Validate token response
                    if "error" in token_data:
                        error_desc = token_data.get("error_description", token_data["error"])
                        logger.error(f"OAuth error response: {error_desc}")
                        return False, {}, f"OAuth error: {error_desc}"
                    
                    if "access_token" not in token_data:
                        return False, {}, "Missing access token in response"
                    
                    return True, token_data, ""
                    
        except Exception as e:
            logger.error(f"Error exchanging code for token: {e}")
            return False, {}, f"Token exchange error: {str(e)}"
    
    async def verify_jwt_token(
        self,
        token: str,
        provider: OAuthProviderConfig,
        expected_audience: Optional[str] = None,
        expected_nonce: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Verify a JWT token from an OpenID provider.
        
        Args:
            token: ID token to verify
            provider: OAuth provider configuration
            expected_audience: Expected audience value
            expected_nonce: Expected nonce value
            
        Returns:
            Tuple of (valid, payload, error_message)
        """
        try:
            import jwt
            
            # Determine key to use for verification
            if provider.jwks_uri:
                # Fetch JWKs from provider
                keys = await self._get_jwks(provider.jwks_uri)
                
                # Extract key ID from token header
                header = jwt.get_unverified_header(token)
                kid = header.get("kid")
                
                if not kid:
                    return False, {}, "Missing key ID in token header"
                
                # Find matching key
                key_data = next((k for k in keys.get("keys", []) if k.get("kid") == kid), None)
                if not key_data:
                    return False, {}, f"No matching key found for kid: {kid}"
                
                # Convert JWK to PEM
                key = self._jwk_to_key(key_data)
            else:
                # Use client secret as key
                key = provider.client_secret
                
            # Get algorithm from token header or config
            header = jwt.get_unverified_header(token)
            alg = header.get("alg", "RS256")
            
            # Verify token has an acceptable algorithm
            if alg not in provider.supported_algorithms:
                return False, {}, f"Unsupported algorithm: {alg}"
                
            # Set verification options
            options = {
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "verify_aud": bool(expected_audience),
                "verify_iss": bool(provider.trusted_issuers),
                "require_exp": True,
                "require_iat": True,
            }
            
            # Set claims for verification
            verify_claims = {}
            if expected_audience:
                verify_claims["aud"] = expected_audience
            if provider.trusted_issuers:
                verify_claims["iss"] = provider.trusted_issuers
                
            # Decode and verify token
            payload = jwt.decode(
                token,
                key,
                algorithms=[alg],
                options=options,
                audience=expected_audience if expected_audience else None,
                issuer=provider.trusted_issuers[0] if provider.trusted_issuers else None
            )
            
            # Verify nonce if provided
            if expected_nonce and payload.get("nonce") != expected_nonce:
                return False, {}, "Nonce mismatch"
                
            return True, payload, ""
            
        except jwt.ExpiredSignatureError:
            return False, {}, "Token has expired"
        except jwt.InvalidAudienceError:
            return False, {}, "Invalid audience"
        except jwt.InvalidIssuerError:
            return False, {}, "Invalid issuer"
        except jwt.InvalidSignatureError:
            return False, {}, "Invalid signature"
        except jwt.DecodeError as e:
            return False, {}, f"Token decode error: {str(e)}"
        except Exception as e:
            logger.error(f"Error verifying JWT token: {e}")
            return False, {}, f"Token verification error: {str(e)}"
    
    async def get_userinfo(
        self,
        provider: OAuthProviderConfig,
        access_token: str,
        id_token_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Get user information from the userinfo endpoint.
        
        Args:
            provider: OAuth provider configuration
            access_token: Access token
            id_token_data: Optional ID token payload
            
        Returns:
            Tuple of (success, userinfo, error_message)
        """
        # If we already have user info from ID token, use that
        if id_token_data:
            # Extract relevant claims based on provider configuration
            userinfo = {
                "sub": id_token_data.get(provider.user_id_claim),
                "email": id_token_data.get(provider.email_claim),
                "name": id_token_data.get(provider.name_claim),
                # Include all claims for reference
                "raw_claims": id_token_data
            }
            
            # Ensure critical fields are present
            if not userinfo["sub"]:
                return False, {}, f"Missing user ID claim: {provider.user_id_claim}"
                
            return True, userinfo, ""
            
        # Fetch from userinfo endpoint if needed
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "User-Agent": "IPFS-Kit-MCP/1.0",
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(provider.userinfo_url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Userinfo error ({response.status}): {error_text}")
                        return False, {}, f"Failed to get user info: {response.status}"
                    
                    # Parse userinfo response
                    userinfo = await response.json()
                    
                    # Extract standard claims
                    result = {
                        "sub": userinfo.get(provider.user_id_claim),
                        "email": userinfo.get(provider.email_claim),
                        "name": userinfo.get(provider.name_claim),
                        # Include all userinfo for reference
                        "raw_userinfo": userinfo
                    }
                    
                    # Ensure critical fields are present
                    if not result["sub"]:
                        return False, {}, f"Missing user ID claim: {provider.user_id_claim}"
                        
                    return True, result, ""
                    
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return False, {}, f"User info error: {str(e)}"
    
    def _validate_redirect_uri(self, provider: OAuthProviderConfig, redirect_uri: str) -> bool:
        """
        Validate that a redirect URI is allowed for the provider.
        
        Args:
            provider: OAuth provider configuration
            redirect_uri: Redirect URI to validate
            
        Returns:
            True if valid, raises ValueError if invalid
        """
        if not redirect_uri:
            raise ValueError("Redirect URI is required")
            
        # Parse the redirect URI
        try:
            parsed = urllib.parse.urlparse(redirect_uri)
            
            # Check for localhost (development)
            if parsed.netloc == "localhost" or parsed.netloc.startswith("localhost:"):
                return True
                
            # Check domain against allowed domains
            domain = parsed.netloc.lower()
            if provider.allowed_redirect_domains:
                for allowed_domain in provider.allowed_redirect_domains:
                    # Check exact match
                    if domain == allowed_domain.lower():
                        return True
                    # Check subdomain match (if allowed domain starts with '.')
                    if allowed_domain.startswith(".") and domain.endswith(allowed_domain.lower()):
                        return True
                
                # No match found
                raise ValueError(f"Redirect domain not allowed: {domain}")
            
            # No domain restrictions
            return True
            
        except Exception as e:
            logger.error(f"Error validating redirect URI: {e}")
            raise ValueError(f"Invalid redirect URI: {str(e)}")
    
    async def _store_state(self, state: str, data: Dict[str, Any]) -> bool:
        """
        Store state data with TTL.
        
        Args:
            state: State string
            data: State data
            
        Returns:
            True if stored successfully
        """
        try:
            # Use Redis if available
            if self.redis_client:
                json_data = json.dumps(data)
                await self.redis_client.setex(
                    f"oauth:state:{state}", 
                    self.state_timeout_seconds,
                    json_data
                )
            else:
                # Use in-memory store with expiration
                self._state_store[state] = {
                    "data": data,
                    "expires": time.time() + self.state_timeout_seconds
                }
                
            return True
        except Exception as e:
            logger.error(f"Error storing state: {e}")
            return False
    
    async def _get_state(self, state: str) -> Optional[Dict[str, Any]]:
        """
        Get state data if it exists and isn't expired.
        
        Args:
            state: State string
            
        Returns:
            State data or None if not found/expired
        """
        try:
            # Use Redis if available
            if self.redis_client:
                json_data = await self.redis_client.get(f"oauth:state:{state}")
                if not json_data:
                    return None
                return json.loads(json_data)
            else:
                # Use in-memory store
                state_entry = self._state_store.get(state)
                if not state_entry:
                    return None
                    
                # Check expiration
                if time.time() > state_entry["expires"]:
                    del self._state_store[state]
                    return None
                    
                return state_entry["data"]
        except Exception as e:
            logger.error(f"Error getting state: {e}")
            return None
    
    async def _delete_state(self, state: str) -> bool:
        """
        Delete state after use.
        
        Args:
            state: State string
            
        Returns:
            True if deleted successfully
        """
        try:
            # Use Redis if available
            if self.redis_client:
                await self.redis_client.delete(f"oauth:state:{state}")
            else:
                # Use in-memory store
                if state in self._state_store:
                    del self._state_store[state]
                    
            return True
        except Exception as e:
            logger.error(f"Error deleting state: {e}")
            return False
    
    async def _get_jwks(self, jwks_uri: str) -> Dict[str, Any]:
        """
        Get JWKs from provider.
        
        Args:
            jwks_uri: URI for JWKS
            
        Returns:
            JWKs data
        """
        # Implement JWKs caching to avoid frequent requests
        cache_key = f"jwks:{jwks_uri}"
        
        # Try to get from cache
        cached_jwks = getattr(self, "_jwks_cache", {}).get(cache_key)
        if cached_jwks and cached_jwks["expires"] > time.time():
            return cached_jwks["data"]
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(jwks_uri) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"JWKS error ({response.status}): {error_text}")
                        raise ValueError(f"Failed to get JWKS: {response.status}")
                    
                    jwks = await response.json()
                    
                    # Cache with expiration (1 hour)
                    if not hasattr(self, "_jwks_cache"):
                        self._jwks_cache = {}
                        
                    self._jwks_cache[cache_key] = {
                        "data": jwks,
                        "expires": time.time() + 3600
                    }
                    
                    return jwks
        except Exception as e:
            logger.error(f"Error getting JWKS: {e}")
            raise
            
    def _jwk_to_key(self, jwk: Dict[str, Any]):
        """
        Convert JWK to cryptographic key.
        
        Args:
            jwk: JWK data
            
        Returns:
            Cryptographic key object
        """
        try:
            from jwt.algorithms import RSAAlgorithm
            
            # Handle RSA keys
            if jwk.get("kty") == "RSA":
                return RSAAlgorithm.from_jwk(jwk)
            else:
                raise ValueError(f"Unsupported key type: {jwk.get('kty')}")
        except Exception as e:
            logger.error(f"Error converting JWK to key: {e}")
            raise
            
    def _create_code_challenge(self, code_verifier: str) -> str:
        """
        Create a PKCE code challenge from a verifier.
        
        Args:
            code_verifier: PKCE code verifier
            
        Returns:
            Code challenge
        """
        import base64
        
        # Hash the verifier
        sha256_digest = hashlib.sha256(code_verifier.encode()).digest()
        
        # Base64 encode the hash
        encoded = base64.urlsafe_b64encode(sha256_digest).decode()
        
        # Remove padding
        return encoded.rstrip("=")


# Helper function to create callback URL
def build_oauth_callback_url(base_url: str, provider_id: str) -> str:
    """
    Build a standardized OAuth callback URL.
    
    Args:
        base_url: Base URL of the application
        provider_id: OAuth provider ID
        
    Returns:
        Callback URL
    """
    # Ensure base URL doesn't have trailing slash
    if base_url.endswith("/"):
        base_url = base_url[:-1]
        
    return f"{base_url}/api/v0/auth/oauth/callback/{provider_id}"