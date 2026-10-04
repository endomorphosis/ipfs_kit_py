"""
API Key Cache Management Router

This module provides API endpoints for managing the API key cache,
allowing administrators to view cache statistics, clear the cache,
and invalidate specific cache entries.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from .api_key_middleware import ApiKeyAdminEndpoints
from ..models.auth import User
from ..models.responses import StandardResponse, ErrorResponse

# Set up logging
logger = logging.getLogger(__name__)

def create_api_key_cache_router(
    key_admin: ApiKeyAdminEndpoints, 
    get_current_user_admin
) -> APIRouter:
    """
    Create a router for API key cache management.
    
    Args:
        key_admin: API key admin endpoints
        get_current_user_admin: Dependency for getting admin user
        
    Returns:
        Configured router
    """
    router = APIRouter(tags=["API Key Cache Management"])
    
    @router.get(
        "/stats",
        response_model=StandardResponse,
        summary="Get API Key Cache Stats",
        description="Get statistics about the API key cache performance."
    )
    async def get_cache_stats(
        current_user: User = Depends(get_current_user_admin)
    ) -> StandardResponse:
        """Get API key cache statistics."""
        try:
            stats = await key_admin.get_stats()
            
            return StandardResponse(
                success=True,
                message="API key cache statistics retrieved",
                data=stats.dict()
            )
        except Exception as e:
            logger.error(f"Error getting API key cache stats: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get cache statistics: {str(e)}"
            )
    
    @router.post(
        "/clear",
        response_model=StandardResponse,
        summary="Clear API Key Cache",
        description="Clear the entire API key cache. Use with caution as this will impact performance until the cache warms up again."
    )
    async def clear_cache(
        current_user: User = Depends(get_current_user_admin)
    ) -> StandardResponse:
        """Clear the API key cache."""
        try:
            result = await key_admin.clear_cache()
            
            return StandardResponse(
                success=True,
                message="API key cache cleared successfully",
                data=result
            )
        except Exception as e:
            logger.error(f"Error clearing API key cache: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to clear cache: {str(e)}"
            )
    
    @router.post(
        "/invalidate/user/{user_id}",
        response_model=StandardResponse,
        summary="Invalidate User API Keys",
        description="Invalidate all cached API keys for a specific user."
    )
    async def invalidate_user_keys(
        user_id: str,
        current_user: User = Depends(get_current_user_admin)
    ) -> StandardResponse:
        """Invalidate all API keys for a user."""
        try:
            result = await key_admin.invalidate_user_keys(user_id)
            
            return StandardResponse(
                success=True,
                message=f"API keys for user {user_id} invalidated",
                data=result
            )
        except Exception as e:
            logger.error(f"Error invalidating user API keys: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to invalidate user keys: {str(e)}"
            )
    
    @router.post(
        "/invalidate/key/{key_id}",
        response_model=StandardResponse,
        summary="Invalidate API Key",
        description="Invalidate a specific API key in the cache."
    )
    async def invalidate_key(
        key_id: str,
        current_user: User = Depends(get_current_user_admin)
    ) -> StandardResponse:
        """Invalidate a specific API key."""
        try:
            result = await key_admin.invalidate_key(key_id)
            
            return StandardResponse(
                success=True,
                message=f"API key {key_id} invalidated",
                data=result
            )
        except Exception as e:
            logger.error(f"Error invalidating API key: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to invalidate key: {str(e)}"
            )
    
    return router