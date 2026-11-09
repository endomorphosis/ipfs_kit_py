"""
Enhanced API Key Management System

This module provides a comprehensive API key management system for the MCP server.
It supports features such as:
- Scoped API keys with specific permissions
- Auto-expiring keys
- Per-backend authorization
- Rate limiting
- Usage tracking and auditing

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements - "Advanced Authentication & Authorization".
"""

import os
import time
import json
import uuid
import hmac
import base64
import hashlib
import secrets
import logging
from typing import Dict, List, Any, Optional, Union, Set, Tuple
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Response, Depends, HTTPException, status, Form, Query
from fastapi.security import APIKeyHeader

from ipfs_kit_py.mcp.auth.models import User, Role, Permission
from ipfs_kit_py.mcp.auth.service import AuthService
from ipfs_kit_py.mcp.auth.rbac import RBACManager
from ipfs_kit_py.mcp.auth.audit_logging import AuditLogger, AuditEventType, AuditSeverity

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("api_key_enhanced")

# API key header name
API_KEY_HEADER = "X-API-Key"

# API key header security
api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)

class APIKey:
    """API key class with enhanced features."""
    
    def __init__(
        self,
        user_id: str,
        name: str,
        permissions: Optional[List[str]] = None,
        expires_at: Optional[float] = None,
        rate_limit: Optional[int] = None,
        backends: Optional[List[str]] = None,
        ip_whitelist: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize API key.
        
        Args:
            user_id: User ID
            name: Key name
            permissions: Optional list of permission IDs
            expires_at: Optional expiration timestamp
            rate_limit: Optional rate limit (requests per minute)
            backends: Optional list of allowed backend IDs
            ip_whitelist: Optional list of allowed IP addresses
            metadata: Optional metadata
        """
        self.id = str(uuid.uuid4())
        self.user_id = user_id
        self.name = name
        self.key = self._generate_key()
        self.key_hash = self._hash_key(self.key)
        self.permissions = set(permissions) if permissions else set()
        self.expires_at = expires_at
        self.rate_limit = rate_limit
        self.backends = set(backends) if backends else set()
        self.ip_whitelist = set(ip_whitelist) if ip_whitelist else set()
        self.metadata = metadata or {}
        self.created_at = time.time()
        self.last_used_at = None
        self.use_count = 0
    
    def _generate_key(self) -> str:
        """
        Generate a secure API key.
        
        Returns:
            API key string
        """
        # Generate a secure random key
        random_bytes = secrets.token_bytes(32)
        
        # Convert to a URL-safe base64 string
        encoded = base64.urlsafe_b64encode(random_bytes).decode().rstrip('=')
        
        # Add a prefix for easy identification
        return f"mcp_{encoded}"
    
    def _hash_key(self, key: str) -> str:
        """
        Hash an API key for storage.
        
        Args:
            key: API key string
            
        Returns:
            Hashed key
        """
        # Use SHA-256 for hashing
        return hashlib.sha256(key.encode()).hexdigest()
    
    def verify_key(self, key: str) -> bool:
        """
        Verify an API key against the stored hash.
        
        Args:
            key: API key string
            
        Returns:
            True if key is valid
        """
        return hmac.compare_digest(self._hash_key(key), self.key_hash)
    
    def is_expired(self) -> bool:
        """
        Check if the API key is expired.
        
        Returns:
            True if expired
        """
        return self.expires_at is not None and time.time() > self.expires_at
    
    def can_access_backend(self, backend_id: str) -> bool:
        """
        Check if the API key can access a backend.
        
        Args:
            backend_id: Backend ID
            
        Returns:
            True if access allowed
        """
        # If no backends specified, allow all
        if not self.backends:
            return True
        
        return backend_id in self.backends
    
    def is_ip_allowed(self, ip_address: str) -> bool:
        """
        Check if an IP address is allowed to use this API key.
        
        Args:
            ip_address: IP address
            
        Returns:
            True if allowed
        """
        # If no IP whitelist, allow all
        if not self.ip_whitelist:
            return True
        
        # Check exact match
        if ip_address in self.ip_whitelist:
            return True
        
        # Check CIDR ranges (simplified - in production would use ipaddress module)
        for allowed_ip in self.ip_whitelist:
            if '/' in allowed_ip:
                # This is a CIDR range
                if ip_address.startswith(allowed_ip.split('/')[0].rsplit('.', 1)[0]):
                    return True
        
        return False
    
    def record_usage(self) -> None:
        """Record API key usage."""
        self.last_used_at = time.time()
        self.use_count += 1
    
    def to_dict(self, include_key: bool = False) -> Dict[str, Any]:
        """
        Convert to dictionary representation.
        
        Args:
            include_key: Whether to include the API key
            
        Returns:
            Dictionary with API key fields
        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "key": self.key if include_key else None,
            "permissions": list(self.permissions),
            "expires_at": self.expires_at,
            "rate_limit": self.rate_limit,
            "backends": list(self.backends),
            "ip_whitelist": list(self.ip_whitelist),
            "metadata": self.metadata,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "use_count": self.use_count,
            "is_expired": self.is_expired()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'APIKey':
        """
        Create from dictionary representation.
        
        Args:
            data: Dictionary with API key fields
            
        Returns:
            API key instance
        """
        # Create instance
        api_key = cls(
            user_id=data["user_id"],
            name=data["name"],
            permissions=data.get("permissions"),
            expires_at=data.get("expires_at"),
            rate_limit=data.get("rate_limit"),
            backends=data.get("backends"),
            ip_whitelist=data.get("ip_whitelist"),
            metadata=data.get("metadata")
        )
        
        # Set fields that aren't in constructor
        api_key.id = data.get("id", api_key.id)
        api_key.key = data.get("key", api_key.key)
        api_key.key_hash = data.get("key_hash", api_key.key_hash)
        api_key.created_at = data.get("created_at", api_key.created_at)
        api_key.last_used_at = data.get("last_used_at")
        api_key.use_count = data.get("use_count", 0)
        
        return api_key


class APIKeyStore:
    """Storage backend for API keys."""
    
    def __init__(self, store_path: str):
        """
        Initialize API key store.
        
        Args:
            store_path: Path to store API keys
        """
        self.store_path = store_path
        
        # Create store directory
        os.makedirs(store_path, exist_ok=True)
        
        # Cache for in-memory access
        self._key_cache = {}  # id -> APIKey
        self._key_hash_map = {}  # key_hash -> id
    
    def save_key(self, api_key: APIKey) -> bool:
        """
        Save an API key to the store.
        
        Args:
            api_key: API key to save
            
        Returns:
            Success flag
        """
        try:
            # Convert to dict
            key_dict = api_key.to_dict(include_key=False)
            key_dict["key_hash"] = api_key.key_hash
            
            # Save to file
            file_path = os.path.join(self.store_path, f"{api_key.id}.json")
            with open(file_path, 'w') as f:
                json.dump(key_dict, f, indent=2)
            
            # Update caches
            self._key_cache[api_key.id] = api_key
            self._key_hash_map[api_key.key_hash] = api_key.id
            
            return True
        except Exception as e:
            logger.error(f"Error saving API key {api_key.id}: {e}")
            return False
    
    def get_key(self, key_id: str) -> Optional[APIKey]:
        """
        Get an API key by ID.
        
        Args:
            key_id: API key ID
            
        Returns:
            API key or None if not found
        """
        # Check cache
        if key_id in self._key_cache:
            return self._key_cache[key_id]
        
        # Try to load from file
        try:
            file_path = os.path.join(self.store_path, f"{key_id}.json")
            if not os.path.exists(file_path):
                return None
            
            with open(file_path, 'r') as f:
                key_dict = json.load(f)
            
            # Create API key
            api_key = APIKey.from_dict(key_dict)
            
            # Update caches
            self._key_cache[key_id] = api_key
            self._key_hash_map[api_key.key_hash] = key_id
            
            return api_key
        except Exception as e:
            logger.error(f"Error loading API key {key_id}: {e}")
            return None
    
    def get_key_by_hash(self, key_hash: str) -> Optional[APIKey]:
        """
        Get an API key by hash.
        
        Args:
            key_hash: API key hash
            
        Returns:
            API key or None if not found
        """
        # Check hash map
        if key_hash in self._key_hash_map:
            key_id = self._key_hash_map[key_hash]
            return self.get_key(key_id)
        
        # Scan all keys
        for filename in os.listdir(self.store_path):
            if filename.endswith(".json"):
                key_id = filename[:-5]  # Remove .json extension
                api_key = self.get_key(key_id)
                if api_key and api_key.key_hash == key_hash:
                    # Update hash map
                    self._key_hash_map[key_hash] = key_id
                    return api_key
        
        return None
    
    def get_keys_for_user(self, user_id: str) -> List[APIKey]:
        """
        Get all API keys for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of API keys
        """
        keys = []
        
        # Get all key files
        for filename in os.listdir(self.store_path):
            if filename.endswith(".json"):
                key_id = filename[:-5]  # Remove .json extension
                api_key = self.get_key(key_id)
                if api_key and api_key.user_id == user_id:
                    keys.append(api_key)
        
        return keys
    
    def delete_key(self, key_id: str) -> bool:
        """
        Delete an API key.
        
        Args:
            key_id: API key ID
            
        Returns:
            Success flag
        """
        try:
            # Get key for cache cleanup
            api_key = self.get_key(key_id)
            
            # Remove from caches
            if api_key:
                if key_id in self._key_cache:
                    del self._key_cache[key_id]
                
                if api_key.key_hash in self._key_hash_map:
                    del self._key_hash_map[api_key.key_hash]
            
            # Remove file
            file_path = os.path.join(self.store_path, f"{key_id}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return True
        except Exception as e:
            logger.error(f"Error deleting API key {key_id}: {e}")
            return False
    
    def find_key_by_actual_key(self, key: str) -> Optional[APIKey]:
        """
        Find an API key by the actual key string.
        
        Args:
            key: API key string
            
        Returns:
            API key or None if not found
        """
        # Hash the key
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        
        # Find by hash
        return self.get_key_by_hash(key_hash)


class RateLimiter:
    """Rate limiter for API keys."""
    
    def __init__(self):
        """Initialize rate limiter."""
        self.usage = {}  # key_id -> [(timestamp, count)]
        self.clean_interval = 60  # Seconds between cleanup
        self.last_cleanup = time.time()
    
    def check_rate_limit(self, key_id: str, limit: int) -> bool:
        """
        Check if an API key has exceeded its rate limit.
        
        Args:
            key_id: API key ID
            limit: Rate limit (requests per minute)
            
        Returns:
            True if within limit
        """
        now = time.time()
        
        # Clean old usage data periodically
        if now - self.last_cleanup > self.clean_interval:
            self._cleanup_old_data(now)
            self.last_cleanup = now
        
        # Get usage for this key
        if key_id not in self.usage:
            self.usage[key_id] = []
        
        # Filter to last minute
        minute_ago = now - 60
        recent_usage = [u for u in self.usage[key_id] if u[0] > minute_ago]
        
        # Calculate total requests in last minute
        total_requests = sum(u[1] for u in recent_usage)
        
        # Check limit
        if total_requests >= limit:
            return False
        
        # Record usage
        if recent_usage and recent_usage[-1][0] > now - 1:
            # Increment last entry if less than a second ago
            recent_usage[-1] = (recent_usage[-1][0], recent_usage[-1][1] + 1)
        else:
            # Add new entry
            recent_usage.append((now, 1))
        
        # Update usage
        self.usage[key_id] = recent_usage
        
        return True
    
    def _cleanup_old_data(self, now: float) -> None:
        """
        Clean up old usage data.
        
        Args:
            now: Current timestamp
        """
        minute_ago = now - 60
        
        for key_id in list(self.usage.keys()):
            # Keep only last minute of data
            self.usage[key_id] = [u for u in self.usage[key_id] if u[0] > minute_ago]
            
            # Remove empty entries
            if not self.usage[key_id]:
                del self.usage[key_id]


class EnhancedAPIKeyManager:
    """Enhanced API key manager with advanced features."""
    
    def __init__(
        self,
        store_path: str,
        auth_service: AuthService,
        rbac_manager: RBACManager,
        audit_logger: Optional[AuditLogger] = None
    ):
        """
        Initialize API key manager.
        
        Args:
            store_path: Path to store API keys
            auth_service: Auth service instance
            rbac_manager: RBAC manager instance
            audit_logger: Optional audit logger instance
        """
        self.store = APIKeyStore(store_path)
        self.auth_service = auth_service
        self.rbac_manager = rbac_manager
        self.audit_logger = audit_logger
        self.rate_limiter = RateLimiter()
        
        # Create router
        self.router = APIRouter()
        
        # Set up routes
        self.setup_routes()
        
        logger.info("Enhanced API key manager initialized")
    
    def setup_routes(self):
        """Set up router endpoints."""
        
        @self.router.post("/apikeys")
        async def create_api_key(
            request: Request,
            name: str = Form(...),
            permissions: Optional[str] = Form(None),
            expiry_days: Optional[int] = Form(None),
            rate_limit: Optional[int] = Form(None),
            backends: Optional[str] = Form(None),
            ip_whitelist: Optional[str] = Form(None),
            metadata: Optional[str] = Form(None),
            current_user: User = Depends(self.auth_service.get_current_user)
        ):
            """
            Create a new API key.
            
            Args:
                request: FastAPI request
                name: Key name
                permissions: Optional comma-separated list of permissions
                expiry_days: Optional expiry in days
                rate_limit: Optional rate limit (requests per minute)
                backends: Optional comma-separated list of allowed backends
                ip_whitelist: Optional comma-separated list of allowed IP addresses
                metadata: Optional JSON metadata
                current_user: Current authenticated user
            """
            try:
                # Parse form data
                permissions_list = permissions.split(',') if permissions else None
                backends_list = backends.split(',') if backends else None
                ip_whitelist_list = ip_whitelist.split(',') if ip_whitelist else None
                metadata_dict = json.loads(metadata) if metadata else None
                
                # Calculate expiry timestamp
                expires_at = None
                if expiry_days:
                    expires_at = time.time() + (expiry_days * 24 * 60 * 60)
                
                # Create API key
                api_key = await self.create_key(
                    user_id=current_user.id,
                    name=name,
                    permissions=permissions_list,
                    expires_at=expires_at,
                    rate_limit=rate_limit,
                    backends=backends_list,
                    ip_whitelist=ip_whitelist_list,
                    metadata=metadata_dict
                )
                
                if not api_key:
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to create API key"
                    )
                
                # Log key creation
                if self.audit_logger:
                    self.audit_logger.log(
                        event_type=AuditEventType.API_KEY,
                        action="api_key_created",
                        severity=AuditSeverity.INFO,
                        user_id=current_user.id,
                        details={
                            "key_id": api_key.id,
                            "name": name,
                            "ip": request.client.host if request.client else None
                        }
                    )
                
                # Return API key
                return {
                    "success": True,
                    "api_key": api_key.to_dict(include_key=True)
                }
                
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid metadata JSON"
                )
            except Exception as e:
                logger.error(f"Error creating API key: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error creating API key: {str(e)}"
                )
        
        @self.router.get("/apikeys")
        async def list_api_keys(
            current_user: User = Depends(self.auth_service.get_current_user)
        ):
            """
            List API keys for current user.
            
            Args:
                current_user: Current authenticated user
            """
            try:
                # Get keys for user
                keys = await self.get_keys_for_user(current_user.id)
                
                # Return keys
                return {
                    "success": True,
                    "api_keys": [key.to_dict() for key in keys]
                }
                
            except Exception as e:
                logger.error(f"Error listing API keys: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error listing API keys: {str(e)}"
                )
        
        @self.router.delete("/apikeys/{key_id}")
        async def revoke_api_key(
            request: Request,
            key_id: str,
            current_user: User = Depends(self.auth_service.get_current_user)
        ):
            """
            Revoke an API key.
            
            Args:
                request: FastAPI request
                key_id: API key ID
                current_user: Current authenticated user
            """
            try:
                # Get key
                api_key = self.store.get_key(key_id)
                
                if not api_key:
                    raise HTTPException(
                        status_code=404,
                        detail=f"API key {key_id} not found"
                    )
                
                # Check ownership
                if api_key.user_id != current_user.id and not current_user.role in [Role.ADMIN, Role.SYSTEM]:
                    raise HTTPException(
                        status_code=403,
                        detail="You do not own this API key"
                    )
                
                # Revoke key
                success = await self.revoke_key(key_id)
                
                if not success:
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to revoke API key"
                    )
                
                # Log key revocation
                if self.audit_logger:
                    self.audit_logger.log(
                        event_type=AuditEventType.API_KEY,
                        action="api_key_revoked",
                        severity=AuditSeverity.INFO,
                        user_id=current_user.id,
                        details={
                            "key_id": key_id,
                            "ip": request.client.host if request.client else None
                        }
                    )
                
                return {
                    "success": True,
                    "message": f"API key {key_id} revoked"
                }
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error revoking API key: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error revoking API key: {str(e)}"
                )
    
    async def create_key(
        self,
        user_id: str,
        name: str,
        permissions: Optional[List[str]] = None,
        expires_at: Optional[float] = None,
        rate_limit: Optional[int] = None,
        backends: Optional[List[str]] = None,
        ip_whitelist: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[APIKey]:
        """
        Create a new API key.
        
        Args:
            user_id: User ID
            name: Key name
            permissions: Optional list of permission IDs
            expires_at: Optional expiration timestamp
            rate_limit: Optional rate limit (requests per minute)
            backends: Optional list of allowed backend IDs
            ip_whitelist: Optional list of allowed IP addresses
            metadata: Optional metadata
            
        Returns:
            Created API key or None if failed
        """
        try:
            # Create API key
            api_key = APIKey(
                user_id=user_id,
                name=name,
                permissions=permissions,
                expires_at=expires_at,
                rate_limit=rate_limit,
                backends=backends,
                ip_whitelist=ip_whitelist,
                metadata=metadata
            )
            
            # Save to store
            if not self.store.save_key(api_key):
                logger.error(f"Failed to save API key {api_key.id}")
                return None
            
            return api_key
        except Exception as e:
            logger.error(f"Error creating API key: {e}")
            return None
    
    async def get_keys_for_user(self, user_id: str) -> List[APIKey]:
        """
        Get all API keys for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of API keys
        """
        return self.store.get_keys_for_user(user_id)
    
    async def revoke_key(self, key_id: str) -> bool:
        """
        Revoke an API key.
        
        Args:
            key_id: API key ID
            
        Returns:
            Success flag
        """
        return self.store.delete_key(key_id)
    
    async def verify_api_key(
        self,
        key: str,
        ip_address: Optional[str] = None,
        required_permissions: Optional[Set[str]] = None,
        required_backend: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Verify an API key.
        
        Args:
            key: API key string
            ip_address: Optional IP address
            required_permissions: Optional set of required permissions
            required_backend: Optional required backend
            
        Returns:
            Tuple of (success, user_id, error_details)
        """
        # Find API key
        api_key = self.store.find_key_by_actual_key(key)
        
        if not api_key:
            return False, None, {"error": "Invalid API key"}
        
        # Check if expired
        if api_key.is_expired():
            return False, None, {"error": "API key expired"}
        
        # Check IP whitelist
        if ip_address and not api_key.is_ip_allowed(ip_address):
            return False, None, {"error": "IP address not allowed"}
        
        # Check rate limit
        if api_key.rate_limit and not self.rate_limiter.check_rate_limit(api_key.id, api_key.rate_limit):
            return False, None, {"error": "Rate limit exceeded"}
        
        # Check backend access
        if required_backend and not api_key.can_access_backend(required_backend):
            return False, None, {"error": f"No access to backend: {required_backend}"}
        
        # Check permissions
        if required_permissions:
            # Get user role and permissions
            user = await self.auth_service.get_user(api_key.user_id)
            if not user:
                return False, None, {"error": "API key user not found"}
            
            # Check each required permission
            for permission in required_permissions:
                has_permission = self.rbac_manager.check_permission(
                    user_id=user.id,
                    permission=permission
                )
                
                # Also check API key specific permissions
                if not has_permission and api_key.permissions:
                    has_permission = permission in api_key.permissions
                
                if not has_permission:
                    return False, None, {"error": f"Missing permission: {permission}"}
        
        # Record usage
        api_key.record_usage()
        self.store.save_key(api_key)
        
        return True, api_key.user_id, None
    
    async def get_user_from_api_key(self, api_key_header: str) -> Optional[User]:
        """
        Get user from API key.
        
        Args:
            api_key_header: API key header value
            
        Returns:
            User object or None if invalid
        """
        if not api_key_header:
            return None
        
        # Verify API key
        success, user_id, error = await self.verify_api_key(api_key_header)
        
        if not success or not user_id:
            return None
        
        # Get user
        return await self.auth_service.get_user(user_id)


# Create dependency for current user from API key or token
async def get_current_user_from_api_key_or_token(
    request: Request,
    api_key_header: str = Depends(api_key_header),
    auth_service: Optional[AuthService] = None,
    api_key_manager: Optional[EnhancedAPIKeyManager] = None
) -> Optional[User]:
    """
    Get current user from API key or token.
    
    Args:
        request: FastAPI request
        api_key_header: API key header value
        auth_service: Optional auth service instance
        api_key_manager: Optional API key manager instance
        
    Returns:
        User object or None if not authenticated
    """
    # Try API key first
    if api_key_header and api_key_manager:
        user = await api_key_manager.get_user_from_api_key(api_key_header)
        if user:
            # Store in request state
            request.state.user = user
            request.state.auth_method = "api_key"
            return user
    
    # Try token
    if auth_service:
        user = await auth_service.get_current_user(request)
        if user:
            # Already stored in request state by auth service
            request.state.auth_method = "token"
            return user
    
    # Not authenticated
    return None

# Add alias for backward compatibility 
ApiKey = APIKey