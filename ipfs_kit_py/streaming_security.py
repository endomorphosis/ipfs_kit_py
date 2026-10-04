"""
Streaming Security module for IPFS Kit.

This module provides security mechanisms for WebRTC and WebSocket streaming, 
including authentication, authorization, encryption, and secure signaling.

Key features:
1. Authentication: User-based authentication for streaming connections
2. Authorization: Content-specific access control
3. Token-based Security: JWT-based authentication for streaming
4. Encryption: Content encryption for sensitive media
5. Secure Signaling: Protection for WebRTC signaling
6. Audit Logging: Comprehensive logging of streaming access
7. Rate Limiting: Prevention of abuse through rate limiting
8. SOP/CORS Protection: Security for browser-based clients
"""

import anyio
import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Awaitable, Union, Any

# For encryption
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    HAVE_CRYPTO = True
except ImportError:
    HAVE_CRYPTO = False

# For JWT
try:
    import jwt
    HAVE_JWT = True
except ImportError:
    HAVE_JWT = False

# For rate limiting
try:
    from fastapi import WebSocket, WebSocketDisconnect, Request, Response, HTTPException, Depends
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.status import HTTP_429_TOO_MANY_REQUESTS, HTTP_401_UNAUTHORIZED
    HAVE_FASTAPI = True
except ImportError:
    HAVE_FASTAPI = False

# Configure logging
logger = logging.getLogger(__name__)


class SecurityLevel(str, Enum):
    """Security levels for different types of content."""
    PUBLIC = "public"      # No authentication required
    PROTECTED = "protected"  # Authentication required, basic rate limiting
    PRIVATE = "private"    # Authentication + Authorization required
    ENCRYPTED = "encrypted"  # Authentication + Authorization + Encryption required


class AuthType(str, Enum):
    """Authentication types for streaming connections."""
    NONE = "none"         # No authentication
    JWT = "jwt"           # JWT token authentication
    API_KEY = "api_key"   # API key authentication
    HMAC = "hmac"         # HMAC signature authentication


class StreamingSecurityManager:
    """Central manager for all streaming security features."""
    
    def __init__(self, secret_key=None, token_expiry_seconds=3600,
                 allowed_origins=None, rate_limit_config=None):
        """
        Initialize the streaming security manager.
        
        Args:
            secret_key: Secret key for token generation and validation
            token_expiry_seconds: JWT token expiry time in seconds
            allowed_origins: List of allowed origins for CORS
            rate_limit_config: Configuration for rate limiting
        """
        self.secret_key = secret_key or str(uuid.uuid4())
        self.token_expiry_seconds = token_expiry_seconds
        self.allowed_origins = allowed_origins or ["*"]
        self.rate_limit_config = rate_limit_config or {
            "default": {"requests": 100, "window": 60},  # 100 requests per minute
            "streaming": {"requests": 5, "window": 60},  # 5 streaming connections per minute
            "signaling": {"requests": 20, "window": 60}  # 20 signaling messages per minute
        }
        
        # Client rate limiting trackers
        self.client_tracker = {}
        
        # Access token registry (for invalidation)
        self.token_registry = {}
        
        # Content access policies (CID -> allowed users/roles)
        self.content_policies = {}
        
        # For advanced use cases: encryption key management
        self.encryption_keys = {}
        
        # Flag whether we have crypto libraries
        self.have_crypto = HAVE_CRYPTO
        self.have_jwt = HAVE_JWT
        
        # Initialize security components
        self._initialize_components()
        
    def _initialize_components(self):
        """Initialize security components based on available libraries."""
        # Warn if missing critical components
        if not self.have_jwt:
            logger.warning("JWT library not available. Token authentication will not work.")
            
        if not self.have_crypto:
            logger.warning("Cryptography library not available. Content encryption will not work.")
    
    def create_token(self, user_id, user_role="user", permissions=None, cid_access=None):
        """
        Create a JWT token for streaming authentication.
        
        Args:
            user_id: User identifier
            user_role: User role ("user", "admin", etc.)
            permissions: Dict of permission flags
            cid_access: List of CIDs this token grants access to
            
        Returns:
            JWT token string
        """
        if not self.have_jwt:
            logger.error("JWT library not available. Cannot create token.")
            return None
            
        permissions = permissions or {}
        cid_access = cid_access or []
        
        # Standard claims
        now = datetime.utcnow()
        expiry = now + timedelta(seconds=self.token_expiry_seconds)
        
        claims = {
            "sub": str(user_id),
            "role": user_role,
            "permissions": permissions,
            "cid_access": cid_access,
            "iat": now,
            "exp": expiry,
            "jti": str(uuid.uuid4())  # JWT ID for token revocation
        }
        
        # Sign token
        token = jwt.encode(claims, self.secret_key, algorithm="HS256")
        
        # Register token for potential future revocation
        self.token_registry[claims["jti"]] = {
            "user_id": user_id,
            "expires_at": expiry.timestamp(),
            "revoked": False
        }
        
        return token
    
    def verify_token(self, token):
        """
        Verify a JWT token and return the claims.
        
        Args:
            token: JWT token string
            
        Returns:
            Dict with token claims or None if invalid
        """
        if not self.have_jwt:
            logger.error("JWT library not available. Cannot verify token.")
            return None
            
        try:
            # Decode and verify token
            claims = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            
            # Check if token has been revoked
            if claims.get("jti") in self.token_registry:
                if self.token_registry[claims["jti"]]["revoked"]:
                    logger.warning(f"Rejected revoked token for user {claims.get('sub')}")
                    return None
                    
            return claims
            
        except jwt.ExpiredSignatureError:
            logger.warning("Rejected expired token")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Rejected invalid token: {e}")
            return None
            
    def revoke_token(self, token_or_jti):
        """
        Revoke a token to prevent its future use.
        
        Args:
            token_or_jti: Either a JWT token string or a JWT ID
            
        Returns:
            Boolean indicating success
        """
        jti = token_or_jti
        
        # If a token was provided, extract the JTI
        if len(token_or_jti) > 36 and self.have_jwt:  # Likely a token, not a JTI
            try:
                claims = jwt.decode(token_or_jti, self.secret_key, algorithms=["HS256"])
                jti = claims.get("jti")
            except Exception as e:
                logger.error(f"Failed to extract JTI from token: {e}")
                return False
        
        # Mark token as revoked
        if jti in self.token_registry:
            self.token_registry[jti]["revoked"] = True
            self.token_registry[jti]["revoked_at"] = time.time()
            return True
            
        return False
    
    def revoke_all_user_tokens(self, user_id):
        """
        Revoke all tokens for a specific user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Number of tokens revoked
        """
        revoked_count = 0
        
        for jti, token_info in self.token_registry.items():
            if token_info["user_id"] == user_id and not token_info["revoked"]:
                self.token_registry[jti]["revoked"] = True
                self.token_registry[jti]["revoked_at"] = time.time()
                revoked_count += 1
                
        return revoked_count
    
    def set_content_policy(self, cid, allowed_users=None, allowed_roles=None, 
                          security_level=SecurityLevel.PROTECTED):
        """
        Set access policy for a specific content item.
        
        Args:
            cid: Content identifier
            allowed_users: List of user IDs allowed to access this content
            allowed_roles: List of roles allowed to access this content
            security_level: Security level for this content
            
        Returns:
            Dict with the applied policy
        """
        policy = {
            "cid": cid,
            "allowed_users": allowed_users or [],
            "allowed_roles": allowed_roles or [],
            "security_level": security_level,
            "created_at": time.time()
        }
        
        self.content_policies[cid] = policy
        return policy
    
    def check_content_access(self, cid, user_claims):
        """
        Check if a user has access to specific content.
        
        Args:
            cid: Content identifier
            user_claims: User claims from verified token
            
        Returns:
            Boolean indicating access permission
        """
        # If no policy exists, use default security level (protected)
        if cid not in self.content_policies:
            return SecurityLevel.PUBLIC
            
        policy = self.content_policies[cid]
        
        # Public content is accessible to all
        if policy["security_level"] == SecurityLevel.PUBLIC:
            return True
            
        # For protected content and above, require authentication
        if not user_claims:
            return False
            
        # Get user ID and role from claims
        user_id = user_claims.get("sub")
        user_role = user_claims.get("role", "user")
        
        # Check explicit CID access in token
        token_cid_access = user_claims.get("cid_access", [])
        if cid in token_cid_access:
            return True
            
        # For private and encrypted content, check user/role lists
        if policy["security_level"] in [SecurityLevel.PRIVATE, SecurityLevel.ENCRYPTED]:
            # Check if user is in allowed users list
            if user_id in policy["allowed_users"]:
                return True
                
            # Check if user's role is in allowed roles list
            if user_role in policy["allowed_roles"]:
                return True
                
            # If we get here, access is denied for private/encrypted content
            return False
            
        # For protected content, any authenticated user is allowed
        return True
    
    def check_rate_limit(self, client_id, action_type="default"):
        """
        Check if a client has exceeded rate limits.
        
        Args:
            client_id: Client identifier (IP, user ID, etc.)
            action_type: Type of action for specific rate limits
            
        Returns:
            Tuple of (allowed, current_count, limit, reset_seconds)
        """
        # Get rate limit configuration for this action type
        config = self.rate_limit_config.get(action_type, self.rate_limit_config["default"])
        limit = config["requests"]
        window = config["window"]
        
        # Initialize client tracking if needed
        if client_id not in self.client_tracker:
            self.client_tracker[client_id] = {}
            
        if action_type not in self.client_tracker[client_id]:
            self.client_tracker[client_id][action_type] = {
                "count": 0,
                "window_start": time.time()
            }
            
        # Get client's current tracking data
        tracking = self.client_tracker[client_id][action_type]
        
        # Check if window has expired
        current_time = time.time()
        if current_time - tracking["window_start"] > window:
            # Reset for new window
            tracking["count"] = 1
            tracking["window_start"] = current_time
            return (True, 1, limit, window)
        
        # Increment count
        tracking["count"] += 1
        
        # Check if limit exceeded
        if tracking["count"] > limit:
            # Calculate seconds until reset
            reset_seconds = window - (current_time - tracking["window_start"])
            return (False, tracking["count"], limit, reset_seconds)
            
        return (True, tracking["count"], limit, window)
    
    def generate_encryption_key(self, key_id=None, bits=256):
        """
        Generate a new encryption key for secure content.
        
        Args:
            key_id: Optional key identifier
            bits: Key size in bits (128, 192, or 256)
            
        Returns:
            Dict with key information
        """
        if not self.have_crypto:
            logger.error("Cryptography library not available. Cannot generate encryption key.")
            return None
            
        # Validate bit size
        if bits not in [128, 192, 256]:
            bits = 256
            
        # Generate key
        key_bytes = os.urandom(bits // 8)
        
        # Generate key ID if not provided
        key_id = key_id or str(uuid.uuid4())
        
        # Store key
        self.encryption_keys[key_id] = {
            "key": key_bytes,
            "bits": bits,
            "created_at": time.time()
        }
        
        # Return key information (without the key itself for security)
        return {
            "key_id": key_id,
            "bits": bits,
            "created_at": time.time()
        }
    
    def encrypt_content(self, content, key_id=None):
        """
        Encrypt content using AES-GCM.
        
        Args:
            content: Content bytes to encrypt
            key_id: Key identifier (uses newest key if not specified)
            
        Returns:
            Dict with encrypted content and metadata
        """
        if not self.have_crypto:
            logger.error("Cryptography library not available. Cannot encrypt content.")
            return None
            
        # Get key to use
        if not key_id:
            # Use newest key if not specified
            if not self.encryption_keys:
                # Generate a new key
                key_info = self.generate_encryption_key()
                key_id = key_info["key_id"]
            else:
                # Find newest key
                key_id = max(
                    self.encryption_keys.items(),
                    key=lambda x: x[1]["created_at"]
                )[0]
        
        if key_id not in self.encryption_keys:
            logger.error(f"Encryption key {key_id} not found")
            return None
            
        key = self.encryption_keys[key_id]["key"]
        
        # Generate nonce/IV
        nonce = os.urandom(12)  # 96 bits is recommended for AES-GCM
        
        # Encrypt with AES-GCM
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, content, None)
        
        # Return encrypted content with metadata
        return {
            "key_id": key_id,
            "nonce": base64.b64encode(nonce).decode('utf-8'),
            "ciphertext": base64.b64encode(ciphertext).decode('utf-8'),
            "encrypted_at": time.time()
        }
    
    def decrypt_content(self, encrypted_data):
        """
        Decrypt content using AES-GCM.
        
        Args:
            encrypted_data: Dict with encrypted content and metadata
            
        Returns:
            Decrypted content bytes
        """
        if not self.have_crypto:
            logger.error("Cryptography library not available. Cannot decrypt content.")
            return None
            
        # Extract parameters
        key_id = encrypted_data.get("key_id")
        nonce_b64 = encrypted_data.get("nonce")
        ciphertext_b64 = encrypted_data.get("ciphertext")
        
        if not all([key_id, nonce_b64, ciphertext_b64]):
            logger.error("Missing required decryption parameters")
            return None
            
        # Check if we have the key
        if key_id not in self.encryption_keys:
            logger.error(f"Decryption key {key_id} not found")
            return None
            
        key = self.encryption_keys[key_id]["key"]
        
        # Decode from base64
        nonce = base64.b64decode(nonce_b64)
        ciphertext = base64.b64decode(ciphertext_b64)
        
        # Decrypt with AES-GCM
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        
        return plaintext
    
    def create_hmac_signature(self, message, shared_secret=None):
        """
        Create HMAC signature for message authentication.
        
        Args:
            message: Message to sign
            shared_secret: Optional shared secret (uses instance secret if not provided)
            
        Returns:
            HMAC signature
        """
        # Use provided secret or instance secret
        secret = shared_secret or self.secret_key
        
        # Convert message to bytes if it's a string
        if isinstance(message, str):
            message = message.encode('utf-8')
            
        # Create HMAC signature
        signature = hmac.new(
            secret.encode('utf-8') if isinstance(secret, str) else secret,
            message,
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def verify_hmac_signature(self, message, signature, shared_secret=None):
        """
        Verify HMAC signature for message authentication.
        
        Args:
            message: Original message
            signature: HMAC signature to verify
            shared_secret: Optional shared secret (uses instance secret if not provided)
            
        Returns:
            Boolean indicating validity
        """
        # Calculate expected signature
        expected = self.create_hmac_signature(message, shared_secret)
        
        # Compare signatures using constant-time comparison to prevent timing attacks
        return hmac.compare_digest(signature, expected)
    
    def generate_content_key(self, cid, user_id=None, expiry_seconds=3600):
        """
        Generate a short-lived content key for specific content.
        
        Args:
            cid: Content identifier
            user_id: Optional user identifier
            expiry_seconds: Key expiry time in seconds
            
        Returns:
            Content key
        """
        # Create key data
        key_data = {
            "cid": cid,
            "user_id": user_id,
            "created_at": time.time(),
            "expires_at": time.time() + expiry_seconds
        }
        
        # Convert to string for signing
        data_str = json.dumps(key_data, sort_keys=True)
        
        # Sign the data
        signature = self.create_hmac_signature(data_str)
        
        # Combine data and signature
        content_key = f"{base64.urlsafe_b64encode(data_str.encode('utf-8')).decode('utf-8')}.{signature}"
        
        return content_key
    
    def verify_content_key(self, content_key, cid):
        """
        Verify a content key for a specific CID.
        
        Args:
            content_key: Content key to verify
            cid: Content identifier this key should work for
            
        Returns:
            Boolean indicating validity
        """
        try:
            # Split data and signature
            data_b64, signature = content_key.split('.')
            
            # Decode data
            data_str = base64.urlsafe_b64decode(data_b64).decode('utf-8')
            key_data = json.loads(data_str)
            
            # Check if key is for the correct CID
            if key_data["cid"] != cid:
                logger.warning(f"Content key CID mismatch: {key_data['cid']} != {cid}")
                return False
                
            # Check if key has expired
            if key_data["expires_at"] < time.time():
                logger.warning("Content key has expired")
                return False
                
            # Verify signature
            if not self.verify_hmac_signature(data_str, signature):
                logger.warning("Content key has invalid signature")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error verifying content key: {e}")
            return False
    
    def sanitize_origin(self, origin):
        """
        Sanitize and validate origin header for CORS protection.
        
        Args:
            origin: Origin header from request
            
        Returns:
            Validated origin or None if invalid
        """
        if not origin:
            return None
            
        # Check against allowed origins
        if "*" in self.allowed_origins:
            return origin
            
        if origin in self.allowed_origins:
            return origin
            
        # Check for wildcard domains
        for allowed in self.allowed_origins:
            if allowed.startswith("*."):
                domain_suffix = allowed[1:]  # Remove the *
                if origin.endswith(domain_suffix):
                    return origin
                    
        return None
    
    async def authenticate_websocket(self, websocket):
        """
        Authenticate a WebSocket connection.
        
        Args:
            websocket: WebSocket connection object
            
        Returns:
            Tuple of (authenticated, user_claims)
        """
        # Extract token from query parameters or cookies
        token = websocket.query_params.get("token")
        
        if not token and "authorization" in websocket.headers:
            auth_header = websocket.headers["authorization"]
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                
        if not token:
            # Check for session cookie
            session_token = websocket.cookies.get("session")
            if session_token:
                token = session_token
                
        if not token:
            return (False, None)
            
        # Verify token
        user_claims = self.verify_token(token)
        if not user_claims:
            return (False, None)
            
        return (True, user_claims)
    
    async def authenticate_webrtc_signaling(self, websocket):
        """
        Authenticate a WebRTC signaling connection with enhanced security.
        
        Args:
            websocket: WebSocket connection object
            
        Returns:
            Tuple of (authenticated, user_claims, security_context)
        """
        # First, do basic authentication
        authenticated, user_claims = await self.authenticate_websocket(websocket)
        
        if not authenticated:
            return (False, None, {})
            
        # Create enhanced security context
        security_context = {
            "client_id": websocket.client.host,
            "user_id": user_claims.get("sub"),
            "role": user_claims.get("role", "user"),
            "permissions": user_claims.get("permissions", {}),
            "session_id": str(uuid.uuid4()),
            "started_at": time.time()
        }
        
        # Check rate limits for signaling
        client_id = security_context["client_id"]
        allowed, count, limit, reset = self.check_rate_limit(client_id, "signaling")
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for WebRTC signaling: {client_id}")
            security_context["rate_limited"] = True
            security_context["rate_limit_info"] = {
                "limit": limit,
                "current": count,
                "reset_seconds": reset
            }
            return (False, user_claims, security_context)
            
        # Check CORS if origin is provided
        origin = websocket.headers.get("origin")
        if origin:
            valid_origin = self.sanitize_origin(origin)
            if not valid_origin:
                logger.warning(f"Invalid origin for WebRTC signaling: {origin}")
                security_context["invalid_origin"] = True
                return (False, user_claims, security_context)
                
        return (True, user_claims, security_context)
    
    async def log_streaming_access(self, cid, user_id, access_type, access_details=None):
        """
        Log streaming access for audit purposes.
        
        Args:
            cid: Content identifier
            user_id: User identifier
            access_type: Type of access (e.g., "webrtc", "websocket")
            access_details: Additional details about the access
            
        Returns:
            Dict with logged information
        """
        access_details = access_details or {}
        
        # Create log entry
        log_entry = {
            "cid": cid,
            "user_id": user_id,
            "access_type": access_type,
            "timestamp": time.time(),
            "ip_address": access_details.get("ip_address"),
            "user_agent": access_details.get("user_agent"),
            "session_id": access_details.get("session_id"),
            "stream_id": access_details.get("stream_id", str(uuid.uuid4())),
            "details": access_details
        }
        
        # Log the entry
        logger.info(f"Streaming access: {json.dumps(log_entry)}")
        
        # In a production implementation, this would likely write to a database or secure log service
        
        return log_entry


# WebSocket authentication middleware
async def secure_websocket_middleware(websocket, security_manager):
    """
    Middleware for securing WebSocket connections.
    
    Args:
        websocket: WebSocket connection
        security_manager: Security manager instance
        
    Returns:
        Tuple of (success, user_claims, security_context)
    """
    # Check rate limits
    client_id = websocket.client.host
    allowed, count, limit, reset = security_manager.check_rate_limit(client_id, "websocket")
    
    if not allowed:
        security_context = {
            "client_id": client_id,
            "rate_limited": True,
            "limit_info": {
                "limit": limit,
                "current": count,
                "reset_seconds": reset
            }
        }
        return (False, None, security_context)
        
    # Authenticate user
    authenticated, user_claims = await security_manager.authenticate_websocket(websocket)
    
    security_context = {
        "client_id": client_id,
        "authenticated": authenticated,
        "session_id": str(uuid.uuid4()),
        "started_at": time.time()
    }
    
    if authenticated:
        security_context["user_id"] = user_claims.get("sub")
        security_context["role"] = user_claims.get("role", "user")
        
    return (authenticated, user_claims, security_context)


# WebRTC content security
class WebRTCContentSecurity:
    """Security utilities for WebRTC content streaming."""
    
    def __init__(self, security_manager):
        """
        Initialize WebRTC content security.
        
        Args:
            security_manager: Security manager instance
        """
        self.security_manager = security_manager
    
    async def secure_streaming_offer(self, cid, user_claims, security_context):
        """
        Secure a WebRTC streaming offer request.
        
        Args:
            cid: Content identifier
            user_claims: User claims from token
            security_context: Security context
            
        Returns:
            Tuple of (allowed, reason, enhanced_context)
        """
        # Check content access
        access_allowed = self.security_manager.check_content_access(cid, user_claims)
        
        if not access_allowed:
            return (False, "Content access denied", security_context)
            
        # Enhance security context with content info
        enhanced_context = security_context.copy()
        enhanced_context["cid"] = cid
        
        # Get content policy
        if cid in self.security_manager.content_policies:
            policy = self.security_manager.content_policies[cid]
            enhanced_context["security_level"] = policy["security_level"]
        else:
            enhanced_context["security_level"] = SecurityLevel.PROTECTED
            
        # For encrypted content, add encryption info
        if enhanced_context["security_level"] == SecurityLevel.ENCRYPTED:
            # Generate content key
            user_id = user_claims.get("sub") if user_claims else None
            content_key = self.security_manager.generate_content_key(cid, user_id)
            enhanced_context["content_key"] = content_key
            
        # Log access attempt
        user_id = user_claims.get("sub") if user_claims else "anonymous"
        await self.security_manager.log_streaming_access(
            cid, 
            user_id,
            "webrtc",
            {
                "ip_address": security_context.get("client_id"),
                "session_id": security_context.get("session_id"),
                "user_agent": security_context.get("user_agent")
            }
        )
        
        return (True, "Access granted", enhanced_context)
    
    def secure_frame_data(self, frame_data, security_context):
        """
        Apply security measures to frame data if needed.
        
        Args:
            frame_data: Raw frame data
            security_context: Security context
            
        Returns:
            Processed frame data
        """
        # For encrypted content, encrypt the frame
        if security_context.get("security_level") == SecurityLevel.ENCRYPTED:
            if self.security_manager.have_crypto:
                # Encrypt frame data
                encrypted = self.security_manager.encrypt_content(frame_data)
                if encrypted:
                    return encrypted
                    
        # For non-encrypted content or if encryption failed, return raw data
        return frame_data


# HTTP middleware for FastAPI
if HAVE_FASTAPI:
    class SecurityMiddleware(BaseHTTPMiddleware):
        """FastAPI middleware for streaming security."""
        
        def __init__(self, app, security_manager):
            """Initialize with security manager."""
            super().__init__(app)
            self.security_manager = security_manager
        
        async def dispatch(self, request, call_next):
            """Process request and apply security measures."""
            # Check rate limits for the client
            client_id = request.client.host
            action_type = "streaming" if "stream" in request.url.path else "default"
            allowed, count, limit, reset = self.security_manager.check_rate_limit(client_id, action_type)
            
            if not allowed:
                # Rate limit exceeded
                headers = {
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(reset)),
                    "Retry-After": str(int(reset))
                }
                return Response(
                    content=json.dumps({
                        "error": "Rate limit exceeded",
                        "retry_after": int(reset)
                    }),
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                    headers=headers,
                    media_type="application/json"
                )
                
            # Check CORS for OPTIONS requests
            if request.method == "OPTIONS" and "origin" in request.headers:
                origin = request.headers["origin"]
                valid_origin = self.security_manager.sanitize_origin(origin)
                
                if not valid_origin:
                    return Response(
                        status_code=403,
                        content="Invalid origin"
                    )
                    
            # Process the request
            response = await call_next(request)
            
            # Add security headers
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Content-Security-Policy"] = "default-src 'self'"
            
            # Add CORS headers if origin is present
            if "origin" in request.headers:
                origin = request.headers["origin"]
                valid_origin = self.security_manager.sanitize_origin(origin)
                
                if valid_origin:
                    response.headers["Access-Control-Allow-Origin"] = valid_origin
                    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
                    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
                    response.headers["Access-Control-Max-Age"] = "3600"
            
            return response

    # FastAPI dependency for token authentication
    class TokenSecurity:
        """Token-based security for FastAPI endpoints."""
        
        def __init__(self, security_manager):
            """Initialize with security manager."""
            self.security_manager = security_manager
            self.scheme = HTTPBearer()
            
        async def __call__(self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
            """Validate token and return user claims."""
            if not credentials:
                raise HTTPException(
                    status_code=HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
                
            token = credentials.credentials
            user_claims = self.security_manager.verify_token(token)
            
            if not user_claims:
                raise HTTPException(
                    status_code=HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token"
                )
                
            return user_claims


# Example usage in FastAPI application
"""
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect

app = FastAPI()

# Initialize security manager
security_manager = StreamingSecurityManager(
    secret_key="your-secret-key",
    allowed_origins=["https://example.com"]
)

# Add security middleware
app.add_middleware(SecurityMiddleware, security_manager=security_manager)

# Create token security
token_security = TokenSecurity(security_manager)

# Create WebRTC security
webrtc_security = WebRTCContentSecurity(security_manager)

# Secure WebSocket endpoint
@app.websocket("/ws/stream/{cid}")
async def websocket_stream(websocket: WebSocket, cid: str):
    # Authenticate the connection
    authenticated, user_claims, security_context = await secure_websocket_middleware(
        websocket, security_manager
    )
    
    # Check rate limits
    if security_context.get("rate_limited"):
        await websocket.close(code=1008, reason="Rate limit exceeded")
        return
        
    # Authenticate
    if not authenticated:
        await websocket.close(code=1008, reason="Authentication required")
        return
        
    # Check content access
    access_allowed = security_manager.check_content_access(cid, user_claims)
    if not access_allowed:
        await websocket.close(code=1008, reason="Content access denied")
        return
        
    # Accept the connection
    await websocket.accept()
    
    # Log access
    user_id = user_claims.get("sub")
    await security_manager.log_streaming_access(
        cid, user_id, "websocket", 
        {"ip_address": websocket.client.host, "session_id": security_context["session_id"]}
    )
    
    # Proceed with normal streaming...

# Secure WebRTC signaling endpoint
@app.websocket("/ws/webrtc")
async def websocket_webrtc_signaling(websocket: WebSocket):
    # Authenticate with enhanced security
    authenticated, user_claims, security_context = await security_manager.authenticate_webrtc_signaling(
        websocket
    )
    
    # Check security issues
    if security_context.get("rate_limited"):
        await websocket.close(code=1008, reason="Rate limit exceeded")
        return
        
    if security_context.get("invalid_origin"):
        await websocket.close(code=1008, reason="Invalid origin")
        return
        
    # For WebRTC, we might allow anonymous connections for public content
    # but track the session for rate limiting purposes
    await websocket.accept()
    
    # Create WebRTC manager with security integration
    manager = WebRTCStreamingManager(ipfs_api)
    
    try:
        # Handle signaling messages securely
        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type")
            
            if msg_type == "offer_request":
                # Get CID and check access securely
                cid = message.get("cid")
                allowed, reason, enhanced_context = await webrtc_security.secure_streaming_offer(
                    cid, user_claims, security_context
                )
                
                if not allowed:
                    await websocket.send_json({
                        "type": "error",
                        "error": reason
                    })
                    continue
                
                # If access allowed, proceed with offer creation
                # ...
    except WebSocketDisconnect:
        pass
    finally:
        # Clean up resources
        pass

# Create a token for testing (typically in an API endpoint)
@app.post("/api/tokens")
async def create_token_endpoint(username: str, password: str):
    # In a real implementation, verify username/password
    if username == "testuser" and password == "testpass":
        token = security_manager.create_token(
            user_id=username,
            user_role="user",
            permissions={"streaming": True}
        )
        return {"token": token}
    return {"error": "Invalid credentials"}

# Secure API endpoint
@app.get("/api/secure-content/{cid}")
async def get_secure_content(cid: str, user_claims = Depends(token_security)):
    # Check content access
    access_allowed = security_manager.check_content_access(cid, user_claims)
    if not access_allowed:
        raise HTTPException(status_code=403, detail="Content access denied")
        
    # Proceed with content retrieval
    # ...
    return {"cid": cid, "access": "granted"}
"""