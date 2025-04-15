"""
OAuth Security Enhancements for MCP Server

This module provides security enhancements for OAuth authentication in the MCP server:
1. Token blacklist system to immediately revoke compromised tokens
2. Secure token processing with signing and verification
3. Security configuration for OAuth endpoints

These components strengthen the OAuth integration and help prevent common 
security vulnerabilities such as token replay, CSRF attacks, and token leakage.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
import time
import json
import os
from typing import Dict, List, Optional, Set, Union, Any
from datetime import datetime, timedelta
import hashlib
import hmac
from collections import defaultdict
import threading
import sqlite3
import tempfile
import uuid

# Optional JWT support
try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False
    
logger = logging.getLogger(__name__)

class TokenBlacklist:
    """
    Token blacklist system for invalidating tokens before their expiration.
    
    This class provides:
    - Fast in-memory blacklist for immediate token validation
    - Persistent storage of blacklisted tokens with cleaning
    - Token fingerprinting for storage efficiency
    - Time-based automatic cleanup
    """
    
    def __init__(self, db_path: Optional[str] = None, cleanup_interval: int = 3600):
        """
        Initialize the token blacklist.
        
        Args:
            db_path: Path to SQLite database for persistence (None for in-memory)
            cleanup_interval: Interval in seconds for cleaning expired tokens (default 1 hour)
        """
        self._blacklist: Dict[str, datetime] = {}
        self._lock = threading.RLock()
        
        # Set up database path
        self._db_path = db_path
        if not self._db_path:
            temp_dir = tempfile.gettempdir()
            self._db_path = os.path.join(temp_dir, "mcp_token_blacklist.db")
            
        # Initialize database
        self._init_db()
        
        # Load existing blacklist
        self._load_from_db()
        
        # Start cleanup thread
        self._cleanup_interval = cleanup_interval
        self._stop_cleanup = threading.Event()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="token-blacklist-cleanup"
        )
        self._cleanup_thread.start()
        
        logger.info(f"Token blacklist initialized with persistence at {self._db_path}")
        
    def _init_db(self) -> None:
        """Initialize the SQLite database for token storage."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS blacklisted_tokens (
                token_hash TEXT PRIMARY KEY,
                expires_at TEXT NOT NULL
            )
            """)
            conn.commit()
        finally:
            conn.close()
    
    def _load_from_db(self) -> None:
        """Load blacklisted tokens from the database into memory."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT token_hash, expires_at FROM blacklisted_tokens")
            now = datetime.utcnow()
            
            with self._lock:
                for token_hash, expires_at in cursor.fetchall():
                    expires = datetime.fromisoformat(expires_at)
                    # Only load non-expired tokens
                    if expires > now:
                        self._blacklist[token_hash] = expires
                        
            # Clean up expired tokens from database
            cursor.execute(
                "DELETE FROM blacklisted_tokens WHERE expires_at < ?",
                (now.isoformat(),)
            )
            conn.commit()
            
            logger.debug(f"Loaded {len(self._blacklist)} active blacklisted tokens")
        except Exception as e:
            logger.error(f"Error loading blacklist from database: {e}")
        finally:
            conn.close()
    
    def _save_to_db(self, token_hash: str, expires_at: datetime) -> None:
        """
        Save a blacklisted token to the database.
        
        Args:
            token_hash: Hash of the token
            expires_at: Expiration datetime
        """
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO blacklisted_tokens VALUES (?, ?)",
                (token_hash, expires_at.isoformat())
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Error saving token to blacklist database: {e}")
        finally:
            conn.close()
    
    def _fingerprint_token(self, token: str) -> str:
        """
        Create a fingerprint hash of a token for storage.
        
        Args:
            token: The token to fingerprint
            
        Returns:
            A SHA-256 hash of the token
        """
        return hashlib.sha256(token.encode()).hexdigest()
    
    def blacklist_token(self, token: str, expires_at: datetime) -> None:
        """
        Add a token to the blacklist.
        
        Args:
            token: The token to blacklist
            expires_at: When the token would have expired
        """
        token_hash = self._fingerprint_token(token)
        
        with self._lock:
            self._blacklist[token_hash] = expires_at
            
        # Persist to database
        self._save_to_db(token_hash, expires_at)
        
        logger.info(f"Token blacklisted until {expires_at.isoformat()}")
    
    def is_blacklisted(self, token: str) -> bool:
        """
        Check if a token is blacklisted.
        
        Args:
            token: The token to check
            
        Returns:
            True if the token is blacklisted, False otherwise
        """
        token_hash = self._fingerprint_token(token)
        
        with self._lock:
            if token_hash in self._blacklist:
                expires_at = self._blacklist[token_hash]
                now = datetime.utcnow()
                
                # If token is expired, remove from blacklist and return False
                if expires_at <= now:
                    del self._blacklist[token_hash]
                    return False
                
                return True
                
        return False
    
    def _cleanup_expired(self) -> None:
        """Clean up expired tokens from memory and database."""
        now = datetime.utcnow()
        to_remove = []
        
        # Find expired tokens in memory
        with self._lock:
            for token_hash, expires_at in self._blacklist.items():
                if expires_at <= now:
                    to_remove.append(token_hash)
            
            # Remove from memory
            for token_hash in to_remove:
                del self._blacklist[token_hash]
        
        # Clean database
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM blacklisted_tokens WHERE expires_at < ?",
                (now.isoformat(),)
            )
            conn.commit()
            
            if to_remove:
                logger.debug(f"Cleaned up {len(to_remove)} expired tokens from blacklist")
        except Exception as e:
            logger.error(f"Error cleaning expired tokens from database: {e}")
        finally:
            conn.close()
    
    def _cleanup_loop(self) -> None:
        """Periodic cleanup of expired tokens."""
        while not self._stop_cleanup.is_set():
            # Sleep first to allow initial setup
            self._stop_cleanup.wait(self._cleanup_interval)
            if not self._stop_cleanup.is_set():
                try:
                    self._cleanup_expired()
                except Exception as e:
                    logger.error(f"Error in token blacklist cleanup: {e}")
    
    def shutdown(self) -> None:
        """Shutdown the blacklist system cleanly."""
        logger.info("Shutting down token blacklist")
        self._stop_cleanup.set()
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5.0)


class SecureTokenProcessor:
    """
    Secure token processor with signing and verification capabilities.
    
    This class provides:
    - Token signing with HMAC-SHA-256
    - Token expiration and validity checking
    - Optional JWT integration for structured tokens
    - Protection against common token-based attacks
    """
    
    def __init__(self, secret_key: str, issuer: str = "mcp", 
                algorithm: str = "HS256", token_lifetime: int = 3600):
        """
        Initialize the secure token processor.
        
        Args:
            secret_key: Secret key used for signing tokens
            issuer: Name of the issuing system
            algorithm: Signing algorithm (when using JWT)
            token_lifetime: Default token lifetime in seconds
        """
        self._secret_key = secret_key
        self._issuer = issuer
        self._algorithm = algorithm
        self._token_lifetime = token_lifetime
        self._jwt_supported = HAS_JWT
        
        if not HAS_JWT:
            logger.warning("JWT library not available, using built-in token processor")
            
        logger.info(f"SecureTokenProcessor initialized with {'JWT' if HAS_JWT else 'built-in'} token handling")
    
    def create_token(self, data: Dict[str, Any], 
                    expires_in: Optional[int] = None) -> Dict[str, Any]:
        """
        Create a secure token with the given data.
        
        Args:
            data: Data to include in the token
            expires_in: Token lifetime in seconds (None for default)
            
        Returns:
            Dict with token, expires_at, and other metadata
        """
        # Determine expiration
        if expires_in is None:
            expires_in = self._token_lifetime
            
        issued_at = datetime.utcnow()
        expires_at = issued_at + timedelta(seconds=expires_in)
        
        # Add standard claims
        token_data = data.copy()
        token_data.update({
            "iss": self._issuer,
            "iat": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": str(uuid.uuid4())
        })
        
        # Create token
        if self._jwt_supported:
            token = jwt.encode(
                token_data,
                self._secret_key,
                algorithm=self._algorithm
            )
            # Handle PyJWT v1.x vs v2.x behavior
            if isinstance(token, bytes):
                token = token.decode('utf-8')
        else:
            # Simple custom token format if JWT not available
            token_json = json.dumps(token_data)
            token_bytes = token_json.encode('utf-8')
            signature = hmac.new(
                self._secret_key.encode('utf-8'),
                token_bytes,
                digestmod=hashlib.sha256
            ).hexdigest()
            token = f"{self._encode_base64(token_bytes)}.{signature}"
        
        return {
            "token": token,
            "token_type": "bearer",
            "expires_in": expires_in,
            "expires_at": expires_at.isoformat(),
            "issued_at": issued_at.isoformat(),
            "jti": token_data["jti"]
        }
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify a token and extract its data.
        
        Args:
            token: The token to verify
            
        Returns:
            Dict with the token data
            
        Raises:
            ValueError: If token is invalid or expired
        """
        if self._jwt_supported:
            try:
                # Verify and decode the token
                payload = jwt.decode(
                    token,
                    self._secret_key,
                    algorithms=[self._algorithm],
                    options={"verify_signature": True}
                )
                # Check issuer
                if payload.get("iss") != self._issuer:
                    raise ValueError(f"Invalid token issuer: {payload.get('iss')}")
                
                return payload
            except jwt.ExpiredSignatureError:
                raise ValueError("Token has expired")
            except jwt.InvalidTokenError as e:
                raise ValueError(f"Invalid token: {str(e)}")
        else:
            # Custom token verification if JWT not available
            try:
                parts = token.split(".")
                if len(parts) != 2:
                    raise ValueError("Invalid token format")
                
                token_data_b64, signature = parts
                token_data_bytes = self._decode_base64(token_data_b64)
                expected_signature = hmac.new(
                    self._secret_key.encode('utf-8'),
                    token_data_bytes,
                    digestmod=hashlib.sha256
                ).hexdigest()
                
                if not hmac.compare_digest(signature, expected_signature):
                    raise ValueError("Invalid token signature")
                
                payload = json.loads(token_data_bytes.decode('utf-8'))
                
                # Check expiration
                now = datetime.utcnow()
                if payload.get("exp", 0) < now.timestamp():
                    raise ValueError("Token has expired")
                
                # Check issuer
                if payload.get("iss") != self._issuer:
                    raise ValueError(f"Invalid token issuer: {payload.get('iss')}")
                
                return payload
            except Exception as e:
                raise ValueError(f"Invalid token: {str(e)}")
    
    def get_token_expiry(self, token: str) -> datetime:
        """
        Extract the expiration time from a token.
        
        Args:
            token: The token to check
            
        Returns:
            Datetime when the token expires
            
        Raises:
            ValueError: If token is invalid
        """
        payload = self.verify_token(token)
        exp_timestamp = payload.get("exp", 0)
        return datetime.fromtimestamp(exp_timestamp)
    
    def _encode_base64(self, data: bytes) -> str:
        """
        Encode bytes to URL-safe base64.
        
        Args:
            data: Bytes to encode
            
        Returns:
            Base64 encoded string
        """
        import base64
        encoded = base64.urlsafe_b64encode(data).decode('utf-8')
        return encoded.rstrip("=")
    
    def _decode_base64(self, data: str) -> bytes:
        """
        Decode URL-safe base64 to bytes.
        
        Args:
            data: Base64 string to decode
            
        Returns:
            Decoded bytes
        """
        import base64
        # Add padding if needed
        padding = 4 - (len(data) % 4)
        if padding < 4:
            data += "=" * padding
        return base64.urlsafe_b64decode(data)


class OAuthSecurityConfig:
    """
    Configuration for OAuth security settings.
    
    This class provides:
    - CORS configuration for OAuth endpoints
    - HTTPS enforcement options
    - Allowed callback domain management
    - Token security parameters
    """
    
    def __init__(self):
        """Initialize OAuth security configuration with default values."""
        # CORS and domain settings
        self.allowed_callback_domains: List[str] = [
            "https://localhost:3000",
            "https://127.0.0.1:3000",
            "https://localhost:8080",
            "https://127.0.0.1:8080"
        ]
        
        # Add any configured domains from environment
        env_domains = os.environ.get("MCP_OAUTH_ALLOWED_DOMAINS", "")
        if env_domains:
            self.allowed_callback_domains.extend(env_domains.split(","))
        
        # Security settings
        self.enforce_https: bool = os.environ.get("MCP_OAUTH_ENFORCE_HTTPS", "true").lower() == "true"
        self.use_secure_cookies: bool = self.enforce_https
        self.csrf_protection: bool = True
        self.same_site_policy: str = "lax"  # Options: None, Lax, Strict
        
        # Token settings
        self.access_token_lifetime: int = int(os.environ.get("MCP_OAUTH_ACCESS_TOKEN_LIFETIME", "3600"))
        self.refresh_token_lifetime: int = int(os.environ.get("MCP_OAUTH_REFRESH_TOKEN_LIFETIME", "604800"))  # 7 days
        self.minimum_key_length: int = 32
        
        # Rate limiting
        self.enable_rate_limiting: bool = True
        self.max_login_attempts: int = 5
        self.lockout_period: int = 300  # 5 minutes
        
        logger.info("OAuth security configuration initialized")
    
    def add_allowed_domain(self, domain: str) -> None:
        """
        Add a domain to the allowed callback domains list.
        
        Args:
            domain: Domain to add (must start with http:// or https://)
        """
        if not domain.startswith(("http://", "https://")):
            domain = f"https://{domain}"
            
        if self.enforce_https and domain.startswith("http://"):
            logger.warning(f"Adding non-HTTPS domain {domain} while HTTPS is enforced")
            
        if domain not in self.allowed_callback_domains:
            self.allowed_callback_domains.append(domain)
            logger.info(f"Added {domain} to allowed OAuth callback domains")
    
    def remove_allowed_domain(self, domain: str) -> bool:
        """
        Remove a domain from the allowed callback domains list.
        
        Args:
            domain: Domain to remove
            
        Returns:
            True if domain was removed, False if not found
        """
        if domain in self.allowed_callback_domains:
            self.allowed_callback_domains.remove(domain)
            logger.info(f"Removed {domain} from allowed OAuth callback domains")
            return True
            
        # Also try with https:// prefix
        if not domain.startswith(("http://", "https://")):
            https_domain = f"https://{domain}"
            if https_domain in self.allowed_callback_domains:
                self.allowed_callback_domains.remove(https_domain)
                logger.info(f"Removed {https_domain} from allowed OAuth callback domains")
                return True
                
        return False
    
    def is_allowed_domain(self, domain: str) -> bool:
        """
        Check if a domain is in the allowed callback domains list.
        
        Args:
            domain: Domain to check
            
        Returns:
            True if domain is allowed, False otherwise
        """
        return domain in self.allowed_callback_domains
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.
        
        Returns:
            Dict representation of configuration (sensitive values redacted)
        """
        return {
            "allowed_callback_domains": self.allowed_callback_domains,
            "enforce_https": self.enforce_https,
            "use_secure_cookies": self.use_secure_cookies,
            "csrf_protection": self.csrf_protection,
            "same_site_policy": self.same_site_policy,
            "access_token_lifetime": self.access_token_lifetime,
            "refresh_token_lifetime": self.refresh_token_lifetime,
            "enable_rate_limiting": self.enable_rate_limiting,
            "max_login_attempts": self.max_login_attempts,
            "lockout_period": self.lockout_period
        }


class RateLimiter:
    """
    Rate limiter for authentication endpoints.
    
    Prevents brute force attacks by limiting the number of attempts
    per IP address or username within a time period.
    """
    
    def __init__(self, max_attempts: int = 5, reset_period: int = 300):
        """
        Initialize the rate limiter.
        
        Args:
            max_attempts: Maximum number of attempts allowed
            reset_period: Period in seconds before counter resets
        """
        self._max_attempts = max_attempts
        self._reset_period = reset_period
        self._attempts: Dict[str, List[datetime]] = defaultdict(list)
        self._lock = threading.RLock()
        
        # Start cleanup thread
        self._stop_cleanup = threading.Event()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="rate-limiter-cleanup"
        )
        self._cleanup_thread.start()
        
        logger.info(f"Rate limiter initialized: {max_attempts} attempts per {reset_period}s")
    
    def record_attempt(self, key: str) -> None:
        """
        Record an authentication attempt.
        
        Args:
            key: Identifier for the attempt (IP, username, etc.)
        """
        now = datetime.utcnow()
        
        with self._lock:
            self._attempts[key].append(now)
    
    def is_rate_limited(self, key: str) -> bool:
        """
        Check if a key is currently rate limited.
        
        Args:
            key: Identifier to check
            
        Returns:
            True if rate limited, False otherwise
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self._reset_period)
        
        with self._lock:
            # Filter attempts to only include those within the window
            recent_attempts = [
                attempt for attempt in self._attempts.get(key, [])
                if attempt > cutoff
            ]
            
            # Update the list with filtered attempts
            self._attempts[key] = recent_attempts
            
            # Check if limit exceeded
            return len(recent_attempts) >= self._max_attempts
    
    def get_remaining_attempts(self, key: str) -> int:
        """
        Get the number of remaining attempts before rate limiting.
        
        Args:
            key: Identifier to check
            
        Returns:
            Number of remaining attempts
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self._reset_period)
        
        with self._lock:
            # Filter attempts to only include those within the window
            recent_attempts = [
                attempt for attempt in self._attempts.get(key, [])
                if attempt > cutoff
            ]
            
            return max(0, self._max_attempts - len(recent_attempts))
    
    def reset(self, key: str) -> None:
        """
        Reset the attempt counter for a key.
        
        Args:
            key: Identifier to reset
        """
        with self._lock:
            if key in self._attempts:
                del self._attempts[key]
    
    def _cleanup_loop(self) -> None:
        """Periodic cleanup of expired attempt records."""
        while not self._stop_cleanup.is_set():
            # Sleep for half the reset period
            self._stop_cleanup.wait(self._reset_period / 2)
            if not self._stop_cleanup.is_set():
                try:
                    self._cleanup_expired()
                except Exception as e:
                    logger.error(f"Error in rate limiter cleanup: {e}")
    
    def _cleanup_expired(self) -> None:
        """Clean up expired attempt records."""
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self._reset_period)
        keys_to_remove = []
        
        with self._lock:
            for key, attempts in self._attempts.items():
                # Filter out expired attempts
                recent_attempts = [attempt for attempt in attempts if attempt > cutoff]
                
                if not recent_attempts:
                    # If no recent attempts, mark for removal
                    keys_to_remove.append(key)
                else:
                    # Otherwise update with filtered list
                    self._attempts[key] = recent_attempts
            
            # Remove empty keys
            for key in keys_to_remove:
                del self._attempts[key]
    
    def shutdown(self) -> None:
        """Shutdown the rate limiter cleanly."""
        logger.info("Shutting down rate limiter")
        self._stop_cleanup.set()
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5.0)


class CSRFProtection:
    """
    Cross-Site Request Forgery (CSRF) protection.
    
    This class provides:
    - CSRF token generation and validation
    - Double-submit cookie pattern
    - Timing attack resistant comparisons
    """
    
    def __init__(self, secret_key: str, token_name: str = "csrf_token",
                cookie_name: str = "X-CSRF-Token", header_name: str = "X-CSRF-Token"):
        """
        Initialize CSRF protection.
        
        Args:
            secret_key: Secret key for token generation
            token_name: Name of the CSRF token in forms
            cookie_name: Name of the CSRF cookie
            header_name: Name of the CSRF header
        """
        self._secret_key = secret_key
        self._token_name = token_name
        self._cookie_name = cookie_name
        self._header_name = header_name
        
        logger.info("CSRF protection initialized")
    
    def generate_token(self, user_id: str) -> str:
        """
        Generate a new CSRF token.
        
        Args:
            user_id: User identifier to associate with token
            
        Returns:
            Generated CSRF token
        """
        # Create a random component
        random_component = os.urandom(16).hex()
        
        # Create a timestamp
        timestamp = int(time.time())
        
        # Combine user ID, timestamp, and random component
        message = f"{user_id}:{timestamp}:{random_component}"
        
        # Sign the message
        signature = hmac.new(
            self._secret_key.encode('utf-8'),
            message.encode('utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        # Create token
        token = f"{message}:{signature}"
        
        return token
    
    def validate_token(self, token: str, user_id: str, max_age: int = 3600) -> bool:
        """
        Validate a CSRF token.
        
        Args:
            token: CSRF token to validate
            user_id: User identifier to validate against
            max_age: Maximum age of token in seconds
            
        Returns:
            True if token is valid, False otherwise
        """
        try:
            # Split the token
            parts = token.split(":")
            if len(parts) != 4:
                return False
                
            token_user_id, timestamp_str, random_component, token_signature = parts
            
            # Verify user ID
            if token_user_id != user_id:
                return False
                
            # Verify token age
            try:
                timestamp = int(timestamp_str)
                current_time = int(time.time())
                if current_time - timestamp > max_age:
                    return False
            except ValueError:
                return False
                
            # Verify signature
            message = f"{token_user_id}:{timestamp_str}:{random_component}"
            expected_signature = hmac.new(
                self._secret_key.encode('utf-8'),
                message.encode('utf-8'),
                digestmod=hashlib.sha256
            ).hexdigest()
            
            # Use constant-time comparison to prevent timing attacks
            return hmac.compare_digest(token_signature, expected_signature)
        except Exception:
            return False
    
    @property
    def token_name(self) -> str:
        """Get the CSRF token name for forms."""
        return self._token_name
    
    @property
    def cookie_name(self) -> str:
        """Get the CSRF cookie name."""
        return self._cookie_name
    
    @property
    def header_name(self) -> str:
        """Get the CSRF header name."""
        return self._header_name
"""