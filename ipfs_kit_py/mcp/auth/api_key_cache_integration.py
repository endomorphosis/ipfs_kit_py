"""
API Key Cache Integration for MCP Server.

This module provides integration between the enhanced API key cache and
the MCP server's authentication system. It implements the high-performance
API key validation improvements mentioned in the MCP roadmap.
"""

import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from functools import wraps
import ipaddress

# Configure logger
logger = logging.getLogger(__name__)

# Import enhanced cache
from ipfs_kit_py.mcp.auth.enhanced_api_key_cache import EnhancedApiKeyCache, CachePolicy

class ApiKeyCacheService:
    """
    Service for high-performance API key validation with caching.
    
    This service integrates the enhanced API key cache with the MCP
    authentication service, providing improved performance for API key
    validation while maintaining compatibility with existing code.
    
    Key features:
    1. High-performance validation with multi-level caching
    2. Automatic cache invalidation on key changes
    3. Support for IP restrictions and scopes/permissions
    4. Metrics and telemetry for API key usage
    5. Rate limiting and abuse detection
    """
    
    def __init__(
        self,
        auth_service: Any,
        cache_size: int = 1000,
        ttl_seconds: int = 3600,
        negative_ttl: int = 300,
        redis_client: Optional[Any] = None,
        memcached_client: Optional[Any] = None,
        policy: str = CachePolicy.ADAPTIVE,
        enable_metrics: bool = True,
        enable_rate_limiting: bool = True,
        max_requests_per_minute: int = 120,
        shards: int = 4,
    ):
        """
        Initialize the API key cache service.
        
        Args:
            auth_service: Authentication service instance
            cache_size: Maximum size of the validation cache
            ttl_seconds: TTL for cached API keys in seconds
            negative_ttl: TTL for negative cache entries in seconds
            redis_client: Optional Redis client for distributed caching
            memcached_client: Optional Memcached client for distributed caching
            policy: Cache eviction policy
            enable_metrics: Whether to collect and report detailed metrics
            enable_rate_limiting: Whether to enable rate limiting
            max_requests_per_minute: Maximum requests per minute for rate limiting
            shards: Number of cache shards for better concurrency
        """
        self.auth_service = auth_service
        self.enable_rate_limiting = enable_rate_limiting
        self.max_requests_per_minute = max_requests_per_minute
        
        # Initialize the enhanced cache
        self.cache = EnhancedApiKeyCache(
            cache_size=cache_size,
            ttl_seconds=ttl_seconds,
            negative_ttl=negative_ttl,
            prefix="mcp:apikey:",
            redis_client=redis_client,
            memcached_client=memcached_client,
            policy=policy,
            enable_metrics=enable_metrics,
            enable_cache_warming=True,
            shards=shards,
        )
        
        # Rate limiting data (if enabled)
        if enable_rate_limiting:
            self._rate_limits = {}
            self._rate_limit_lock = asyncio.Lock()
        
        # Register hooks with auth service (if available)
        if hasattr(auth_service, 'register_key_invalidation_hook'):
            auth_service.register_key_invalidation_hook(self._invalidation_hook)
    
    async def validate_api_key(
        self,
        api_key: str,
        ip_address: Optional[str] = None,
        required_scopes: Optional[List[str]] = None,
        required_permissions: Optional[List[str]] = None,
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Validate an API key with efficient caching.
        
        Args:
            api_key: API key to validate
            ip_address: Optional client IP address for IP restrictions
            required_scopes: Optional list of required scopes
            required_permissions: Optional list of required permissions
        
        Returns:
            Tuple of (valid, key_data, error_message)
        """
        if not api_key:
            return False, None, "API key is required"
        
        # Create a unique hash for this key
        key_hash = self.cache.hash_token(api_key)
        
        # Check rate limits if enabled
        if self.enable_rate_limiting:
            if await self._check_rate_limit(key_hash):
                return False, None, "Rate limit exceeded"
        
        # Check cache first
        cache_hit, key_data = self.cache.get(key_hash)
        
        if cache_hit and key_data:
            # Update usage metrics in the background to avoid blocking the request
            # without blocking the current request
            if hasattr(self.auth_service, 'update_api_key_last_used'):
                # Don't await - fire and forget to update last_used
                asyncio.create_task(
                    self.auth_service.update_api_key_last_used(key_data.get("id"))
                )
            
            # Validate the cached key
            valid, error = self._validate_cached_key(key_data, ip_address, required_scopes, required_permissions)
            
            if valid:
                return True, key_data, None
            return False, None, error
        
        # Not in cache, do full validation
        valid, key_obj, error = await self.auth_service.verify_api_key(api_key, ip_address)
        
        if not valid:
            # Cache negative result to avoid repeated DB lookups for invalid keys
            self.cache.set_negative(key_hash)
            return False, None, error
        
        # Convert key_obj to dict if needed
        if hasattr(key_obj, "dict"):
            # Handle Pydantic models
            key_data = key_obj.dict()
        elif hasattr(key_obj, "__dict__"):
            # Handle regular objects
            key_data = {k: v for k, v in key_obj.__dict__.items() if not k.startswith('_')}
        else:
            # Already a dict or other type
            key_data = key_obj
        
        # Cache for future use
        self.cache.set(key_hash, key_data)
        
        return True, key_data, None
    
    def _validate_cached_key(
        self,
        key_data: Dict[str, Any],
        ip_address: Optional[str] = None,
        required_scopes: Optional[List[str]] = None,
        required_permissions: Optional[List[str]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a cached API key.
        
        Args:
            key_data: Cached API key data
            ip_address: Optional client IP address for IP restrictions
            required_scopes: Optional list of required scopes
            required_permissions: Optional list of required permissions
        
        Returns:
            Tuple of (valid, error_message)
        """
        # Check if key is active
        if not key_data.get("active", True):
            return False, "API key is inactive"
        
        # Check expiration
        expiration = key_data.get("expires_at")
        if expiration and time.time() > expiration:
            return False, "API key has expired"
        
        # Check IP restrictions
        if ip_address and "allowed_ips" in key_data and key_data["allowed_ips"]:
            if not self._check_ip_allowed(ip_address, key_data["allowed_ips"]):
                return False, "Client IP not allowed"
        
        # Check scopes if required
        if required_scopes and "scopes" in key_data:
            key_scopes = key_data["scopes"]
            if not all(scope in key_scopes for scope in required_scopes):
                return False, "Insufficient API key scopes"
        
        # Check permissions if required
        if required_permissions and "permissions" in key_data:
            key_permissions = key_data["permissions"]
            if not all(perm in key_permissions for perm in required_permissions):
                return False, "Insufficient API key permissions"
        
        return True, None
    
    def _check_ip_allowed(self, ip_address: str, allowed_ips: List[str]) -> bool:
        """
        Check if an IP address is allowed based on IP restrictions.
        
        Args:
            ip_address: Client IP address to check
            allowed_ips: List of allowed IP addresses or ranges
        
        Returns:
            True if IP is allowed, False otherwise
        """
        if not allowed_ips:
            return True
        
        # Try handling as IP address/network first
        try:
            client_ip = ipaddress.ip_address(ip_address)
            
            for allowed in allowed_ips:
                if '/' in allowed:  # CIDR notation
                    network = ipaddress.ip_network(allowed, strict=False)
                    if client_ip in network:
                        return True
                else:  # Single IP
                    if ip_address == allowed:
                        return True
            
            return False
        except ValueError:
            # Fall back to simple string matching if ipaddress module can't parse
            return ip_address in allowed_ips
    
    async def _check_rate_limit(self, key_hash: str) -> bool:
        """
        Check if a key has exceeded its rate limit.
        
        Args:
            key_hash: Hashed API key
        
        Returns:
            True if rate limit exceeded, False otherwise
        """
        if not self.enable_rate_limiting:
            return False
        
        # Simple in-memory rate limiting
        current_minute = int(time.time() / 60)  # Current minute timestamp
        
        async with self._rate_limit_lock:
            # Clean up old entries
            keys_to_remove = []
            for k, (minute, count) in self._rate_limits.items():
                if minute < current_minute:
                    keys_to_remove.append(k)
            
            for k in keys_to_remove:
                del self._rate_limits[k]
            
            # Check/update current key's rate limit
            if key_hash in self._rate_limits:
                minute, count = self._rate_limits[key_hash]
                
                if minute == current_minute:
                    # Same minute, increment counter
                    if count >= self.max_requests_per_minute:
                        return True  # Rate limit exceeded
                    
                    self._rate_limits[key_hash] = (minute, count + 1)
                else:
                    # New minute, reset counter
                    self._rate_limits[key_hash] = (current_minute, 1)
            else:
                # First request for this key
                self._rate_limits[key_hash] = (current_minute, 1)
        
        return False
    
    def invalidate_key(self, api_key: str) -> None:
        """
        Invalidate a cached API key.
        
        Args:
            api_key: API key to invalidate
        """
        key_hash = self.cache.hash_token(api_key)
        self.cache.invalidate(key_hash)
    
    def invalidate_by_id(self, key_id: str) -> None:
        """
        Invalidate a cached API key by its ID.
        
        Args:
            key_id: API key ID
        """
        self.cache.invalidate_by_id(key_id)
    
    def invalidate_all(self) -> None:
        """Invalidate all cached API keys."""
        self.cache.invalidate_all()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        stats = self.cache.get_stats()
        
        # Add rate limiting stats if enabled
        if self.enable_rate_limiting:
            stats["rate_limiting"] = {
                "enabled": True,
                "max_requests_per_minute": self.max_requests_per_minute,
                "active_keys": len(self._rate_limits),
            }
        
        return stats
    
    def _invalidation_hook(self, key_id: str) -> None:
        """
        Handle cache invalidation events from the auth service.
        
        Args:
            key_id: ID of the API key that was modified or deleted
        """
        self.invalidate_by_id(key_id)

# Decorator for API key validation
def require_api_key(
    cache_service: ApiKeyCacheService,
    required_scopes: Optional[List[str]] = None,
    required_permissions: Optional[List[str]] = None,
):
    """
    Decorator for API key validation with caching.
    
    Args:
        cache_service: ApiKeyCacheService instance
        required_scopes: Optional list of required scopes
        required_permissions: Optional list of required permissions
    
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(request, *args, **kwargs):
            # Get API key from header
            api_key = request.headers.get("X-API-Key")
            if not api_key:
                return {"error": "API key required", "status": "unauthorized"}, 401
            
            # Get client IP if available
            ip_address = request.client.host if hasattr(request, "client") else None
            
            # Validate API key
            valid, key_data, error = await cache_service.validate_api_key(
                api_key,
                ip_address=ip_address,
                required_scopes=required_scopes,
                required_permissions=required_permissions,
            )
            
            if not valid:
                return {"error": error or "Invalid API key", "status": "unauthorized"}, 401
            
            # Add key data to request state
            if hasattr(request, "state"):
                request.state.api_key_data = key_data
            
            # Call original function
            return await func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator

# Factory function for creating a shared instance
_default_cache_service = None

def get_api_key_cache_service(
    auth_service: Any = None,
    cache_size: int = 1000,
    ttl_seconds: int = 3600,
    redis_client: Optional[Any] = None,
    policy: str = CachePolicy.ADAPTIVE,
    enable_metrics: bool = True,
    enable_rate_limiting: bool = True,
) -> ApiKeyCacheService:
    """
    Get or create a shared API key cache service.
    
    Args:
        auth_service: Authentication service instance (required on first call)
        cache_size: Maximum size of the validation cache
        ttl_seconds: TTL for cached API keys in seconds
        redis_client: Optional Redis client for distributed caching
        policy: Cache eviction policy
        enable_metrics: Whether to collect and report metrics
        enable_rate_limiting: Whether to enable rate limiting
    
    Returns:
        ApiKeyCacheService instance
    """
    global _default_cache_service
    
    if _default_cache_service is None:
        if auth_service is None:
            raise ValueError("auth_service is required for initial creation")
        
        _default_cache_service = ApiKeyCacheService(
            auth_service=auth_service,
            cache_size=cache_size,
            ttl_seconds=ttl_seconds,
            redis_client=redis_client,
            policy=policy,
            enable_metrics=enable_metrics,
            enable_rate_limiting=enable_rate_limiting,
        )
    
    return _default_cache_service

# FastAPI middleware for API key validation
def create_api_key_validation_middleware(cache_service: ApiKeyCacheService):
    """
    Create FastAPI middleware for API key validation.
    
    Args:
        cache_service: ApiKeyCacheService instance
    
    Returns:
        FastAPI middleware function
    """
    @asyncio.coroutine
    async def api_key_middleware(request, call_next):
        # Skip validation for certain paths
        path = request.url.path
        
        # Skip validation for public endpoints
        if (
            path.startswith("/docs") or
            path.startswith("/redoc") or
            path.startswith("/openapi.json") or
            path == "/"
        ):
            return await call_next(request)
        
        # Check for API key in header
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            # No API key provided, let the endpoint handler decide if it's required
            return await call_next(request)
        
        # Get client IP if available
        ip_address = request.client.host if hasattr(request, "client") else None
        
        # Validate API key
        valid, key_data, error = await cache_service.validate_api_key(
            api_key,
            ip_address=ip_address,
        )
        
        if valid:
            # Store key data in request state
            request.state.api_key_data = key_data
            # Call the next middleware/endpoint
            return await call_next(request)
        else:
            # Return error response for invalid API key
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"error": error or "Invalid API key", "status": "unauthorized"},
            )
    
    return api_key_middleware

def patch_auth_service(auth_service: Any):
    """
    Patch the authentication service to use the enhanced API key cache.
    
    This function modifies the authentication service to use the enhanced
    API key cache for validation, providing a seamless upgrade path.
    
    Args:
        auth_service: Authentication service instance to patch
    """
    # Create cache service
    cache_service = get_api_key_cache_service(auth_service=auth_service)
    
    # Store original verify_api_key method
    original_verify_api_key = auth_service.verify_api_key
    
    # Define new method that uses the cache
    async def cached_verify_api_key(api_key, ip_address=None):
        valid, key_data, error = await cache_service.validate_api_key(api_key, ip_address)
        return valid, key_data if valid else None, error
    
    # Patch the method
    auth_service.verify_api_key = cached_verify_api_key
    
    # Store reference to original method
    auth_service._original_verify_api_key = original_verify_api_key
    
    # Add reference to cache service
    auth_service.api_key_cache = cache_service
    
    logger.info("Authentication service patched to use enhanced API key cache")
    
    return auth_service
