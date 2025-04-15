"""
API Key Authentication Middleware with Caching

This module provides FastAPI middleware for efficient API key authentication
using the optimized caching system. It addresses the performance issue
mentioned in the MCP roadmap regarding API key validation caching.
"""

import time
import logging
from typing import Optional, Dict, Any, Callable, List, Union
from fastapi import Request, Response, HTTPException, status, Depends
from fastapi.security import APIKeyHeader, APIKeyQuery
from pydantic import BaseModel

from .api_key_cache import ApiKeyValidator
from ..models.auth import TokenData

# Set up logging
logger = logging.getLogger(__name__)

class ApiKeyMiddleware:
    """
    FastAPI middleware for API key authentication with caching support.
    
    This middleware efficiently validates API keys using the caching system
    to reduce database load and improve performance.
    """
    
    def __init__(
        self,
        auth_service,
        api_header_name: str = "X-API-Key",
        api_query_param: Optional[str] = "api_key",
        protected_path_prefixes: List[str] = ["/api/"],
        excluded_paths: List[str] = ["/api/v0/auth/", "/docs", "/redoc", "/openapi.json"],
        redis_client = None,
        cache_size: int = 1000,
        cache_ttl: int = 300
    ):
        """
        Initialize API key middleware.
        
        Args:
            auth_service: Authentication service instance
            api_header_name: HTTP header name for API key
            api_query_param: Query parameter name for API key (None to disable)
            protected_path_prefixes: Path prefixes that require authentication
            excluded_paths: Paths excluded from authentication
            redis_client: Optional Redis client for distributed caching
            cache_size: Size of API key cache
            cache_ttl: TTL for cache entries in seconds
        """
        self.auth_service = auth_service
        self.api_header_name = api_header_name
        self.api_query_param = api_query_param
        self.protected_path_prefixes = protected_path_prefixes
        self.excluded_paths = excluded_paths
        
        # Initialize API key validator with caching
        self.key_validator = ApiKeyValidator(
            auth_service=auth_service,
            cache_size=cache_size,
            cache_ttl=cache_ttl,
            redis_client=redis_client
        )
        
        # Set up API key security schemes
        self.api_key_header = APIKeyHeader(name=api_header_name, auto_error=False)
        self.api_key_query = APIKeyQuery(name=api_query_param, auto_error=False) if api_query_param else None
        
        logger.info(f"API Key Middleware initialized with cache_size={cache_size}, ttl={cache_ttl}s")
    
    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """
        Process a request through the middleware.
        
        Args:
            request: FastAPI request
            call_next: Next middleware function
            
        Returns:
            Response
        """
        # Skip authentication for excluded paths
        path = request.url.path
        
        # Skip if path is in excluded paths
        for excluded in self.excluded_paths:
            if path.startswith(excluded):
                return await call_next(request)
        
        # Check if path should be protected
        should_protect = False
        for prefix in self.protected_path_prefixes:
            if path.startswith(prefix):
                should_protect = True
                break
                
        if not should_protect:
            return await call_next(request)
        
        # Measure authentication time
        start_time = time.time()
        
        # Get API key from header or query parameter
        api_key = None
        
        # Try header first
        api_key = request.headers.get(self.api_header_name)
        
        # Try query param if header not found
        if not api_key and self.api_query_param:
            query_params = request.query_params
            api_key = query_params.get(self.api_query_param)
        
        # If no API key found, proceed to next middleware
        # (JWT authentication might handle it)
        if not api_key:
            return await call_next(request)
        
        # Get client IP address for IP restrictions
        client_ip = request.client.host if request.client else None
        
        # Validate API key using cache
        valid, key_data, error = await self.key_validator.validate_key(api_key, client_ip)
        
        if not valid:
            auth_time = time.time() - start_time
            logger.warning(f"API key validation failed: {error} (took {auth_time:.4f}s)")
            
            # Continue to next middleware to allow JWT auth to work
            # Set attribute on request to indicate API key auth failed
            request.state.api_key_auth_failed = True
            request.state.api_key_auth_error = error
            return await call_next(request)
        
        # API key validation successful
        auth_time = time.time() - start_time
        
        # Set authenticated user on request state
        request.state.authenticated = True
        request.state.user_id = key_data.get("user_id")
        request.state.api_key = True
        request.state.api_key_id = key_data.get("id")
        
        # Set roles and permissions
        request.state.roles = key_data.get("roles", [])
        request.state.permissions = key_data.get("direct_permissions", [])
        
        # Create token data for dependency compatibility
        token_data = TokenData(
            sub=key_data.get("user_id"),
            exp=time.time() + 3600,  # Doesn't really matter for API keys
            iat=time.time(),
            scope="access",
            roles=list(key_data.get("roles", [])),
            permissions=list(key_data.get("direct_permissions", [])),
            is_api_key=True,
            metadata={"api_key_id": key_data.get("id")}
        )
        request.state.token_data = token_data
        
        # Include backend restrictions if available
        if "backend_restrictions" in key_data:
            request.state.backend_restrictions = key_data.get("backend_restrictions")
        
        # Log successful authentication
        logger.debug(f"API key auth succeeded for key {key_data.get('id')} (took {auth_time:.4f}s)")
        
        # Continue with request
        return await call_next(request)

# FastAPI dependencies for API key authentication

async def get_api_key(
    request: Request,
    api_key_header: str = Depends(APIKeyHeader(name="X-API-Key", auto_error=False)),
    api_key_query: Optional[str] = Depends(APIKeyQuery(name="api_key", auto_error=False))
) -> str:
    """
    Get API key from request.
    
    Args:
        request: FastAPI request
        api_key_header: API key from header
        api_key_query: API key from query parameter
        
    Returns:
        API key or raises HTTPException
    """
    # Check if API key auth already failed
    if hasattr(request.state, "api_key_auth_failed") and request.state.api_key_auth_failed:
        error = getattr(request.state, "api_key_auth_error", "Invalid API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error,
            headers={"WWW-Authenticate": "APIKey"}
        )
    
    # If already authenticated with API key, return the key ID
    if (hasattr(request.state, "authenticated") and request.state.authenticated and
        hasattr(request.state, "api_key") and request.state.api_key):
        return getattr(request.state, "api_key_id", "unknown")
    
    # Try to get API key from header or query
    api_key = api_key_header or api_key_query
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "APIKey"}
        )
    
    return api_key
    
async def api_key_security(api_key: str = Depends(get_api_key)) -> TokenData:
    """
    Validate API key and get token data.
    
    This dependency assumes the middleware has already validated the key.
    
    Args:
        api_key: API key from request
        
    Returns:
        TokenData from validated API key
    """
    # This dependency is mainly for documentation purposes
    # The actual validation is done in the middleware
    return TokenData(
        sub="api_key_user",
        exp=time.time() + 3600, 
        iat=time.time(),
        scope="access",
        roles=[],
        permissions=[],
        is_api_key=True,
        metadata={"api_key_id": api_key}
    )

class ApiKeyStats(BaseModel):
    """API key cache statistics model."""
    cache_size: int
    max_cache_size: int 
    hit_ratio: float
    hits: int
    misses: int
    total_requests: int
    
class ApiKeyAdminEndpoints:
    """Admin endpoints for API key cache management."""
    
    def __init__(self, key_validator: ApiKeyValidator):
        """
        Initialize admin endpoints.
        
        Args:
            key_validator: API key validator instance
        """
        self.key_validator = key_validator
    
    async def get_stats(self) -> ApiKeyStats:
        """
        Get API key cache statistics.
        
        Returns:
            Cache statistics
        """
        stats = self.key_validator.get_stats()
        
        return ApiKeyStats(
            cache_size=stats.get("size", 0),
            max_cache_size=stats.get("max_size", 0),
            hit_ratio=stats.get("hit_ratio", 0),
            hits=stats.get("hits", 0),
            misses=stats.get("misses", 0),
            total_requests=stats.get("hits", 0) + stats.get("misses", 0)
        )
    
    async def clear_cache(self) -> Dict[str, Any]:
        """
        Clear the API key cache.
        
        Returns:
            Success message
        """
        self.key_validator.clear_cache()
        return {"success": True, "message": "API key cache cleared"}
    
    async def invalidate_user_keys(self, user_id: str) -> Dict[str, Any]:
        """
        Invalidate all API keys for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Success message with count
        """
        count = self.key_validator.invalidate_user_keys(user_id)
        return {
            "success": True,
            "message": f"Invalidated {count} API keys for user {user_id}"
        }
    
    async def invalidate_key(self, key_id: str) -> Dict[str, Any]:
        """
        Invalidate an API key by ID.
        
        Args:
            key_id: API key ID
            
        Returns:
            Success message
        """
        self.key_validator.invalidate_key_by_id(key_id)
        return {
            "success": True,
            "message": f"Invalidated API key {key_id}"
        }