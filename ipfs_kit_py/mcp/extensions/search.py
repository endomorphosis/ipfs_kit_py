"""
Search extension for MCP server.

This extension integrates the search functionality from mcp_search.py
into the MCP server, providing content indexing, metadata search, and
vector search capabilities.
"""

import logging
import os
import sys
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

# Configure logging
logger = logging.getLogger(__name__)

# Import the error handling module
try:
    import mcp_error_handling
except ImportError:
    logger.warning("mcp_error_handling module not available, using local error handling")
    mcp_error_handling = None

# Import the search module
try:
    from ipfs_kit_py.mcp.search.search import (
        create_search_router,
        ContentSearchService,
        SENTENCE_TRANSFORMERS_AVAILABLE,
        FAISS_AVAILABLE
    )
    SEARCH_AVAILABLE = True
    logger.info("Search module successfully imported from ipfs_kit_py.mcp.search.search")
except ImportError as e:
    SEARCH_AVAILABLE = False
    logger.error(f"Error importing search module from ipfs_kit_py.mcp.search.search: {e}")
    logger.info("Please ensure ipfs_kit_py is installed correctly and search dependencies are met.")

# Initialize search service
_search_service = None

def get_search_service():
    """Get or initialize the search service."""
    global _search_service
    if _search_service is None and SEARCH_AVAILABLE:
        try:
            _search_service = ContentSearchService()
            logger.info("Search service initialized")
        except Exception as e:
            logger.error(f"Error initializing search service: {e}")
    return _search_service

def create_search_router_wrapper(api_prefix: str) -> APIRouter:
    """
    Create a FastAPI router for search endpoints.

    Args:
        api_prefix: The API prefix for the endpoints

    Returns:
        FastAPI router
    """
    if not SEARCH_AVAILABLE:
        logger.error("Search module not available, cannot create router")
        # Return an empty router if search is not available
        router = APIRouter(prefix=f"{api_prefix}/search")

        @router.get("/status")
        async def search_status_unavailable():
            """Return status when search is unavailable."""
            return {
                "success": False,
                "status": "unavailable",
                "error": "Search functionality is not available",
                "message": "Install required dependencies: pip install ipfs_kit_py[search]"
            }

        return router

    try:
        # Initialize search service
        get_search_service()
        
        # Create the search router
        router = create_search_router(api_prefix)
        logger.info(f"Successfully created search router with prefix: {router.prefix}")
        
        # Add enhanced endpoints to the router
        
        @router.get("/tags", summary="Get Popular Tags")
        async def get_popular_tags(
            limit: int = Query(50, description="Maximum number of tags to return"),
            min_count: int = Query(1, description="Minimum count for tags to return"),
            search_service=Depends(get_search_service)
        ):
            """
            Get the most popular tags from indexed content.
            
            Returns a list of tags sorted by frequency.
            """
            if not search_service:
                error_message = "Search service not available"
                if mcp_error_handling:
                    return mcp_error_handling.create_error_response(
                        code="EXTENSION_NOT_AVAILABLE",
                        message_override=error_message,
                        doc_category="search"
                    )
                return {"success": False, "error": error_message}
            
            try:
                stats = await search_service.get_stats()
                if not stats["success"]:
                    return stats
                
                tags = stats["stats"].get("tags", {})
                
                # Filter by min_count and sort by count
                filtered_tags = [
                    {"tag": tag, "count": count} 
                    for tag, count in tags.items() 
                    if count >= min_count
                ]
                filtered_tags.sort(key=lambda x: x["count"], reverse=True)
                
                # Limit the number of results
                filtered_tags = filtered_tags[:limit]
                
                return {
                    "success": True,
                    "count": len(filtered_tags),
                    "tags": filtered_tags
                }
            except Exception as e:
                logger.error(f"Error getting popular tags: {e}")
                if mcp_error_handling:
                    return mcp_error_handling.handle_exception(
                        e, code="INTERNAL_ERROR", endpoint="/search/tags", doc_category="search"
                    )
                return {"success": False, "error": str(e)}
        
        @router.get("/content-types", summary="Get Content Types")
        async def get_content_types(
            search_service=Depends(get_search_service)
        ):
            """
            Get the content types from indexed content.
            
            Returns a list of content types sorted by frequency.
            """
            if not search_service:
                error_message = "Search service not available"
                if mcp_error_handling:
                    return mcp_error_handling.create_error_response(
                        code="EXTENSION_NOT_AVAILABLE",
                        message_override=error_message,
                        doc_category="search"
                    )
                return {"success": False, "error": error_message}
            
            try:
                stats = await search_service.get_stats()
                if not stats["success"]:
                    return stats
                
                content_types = stats["stats"].get("content_types", {})
                
                # Format as list sorted by count
                content_type_list = [
                    {"type": content_type, "count": count} 
                    for content_type, count in content_types.items()
                ]
                content_type_list.sort(key=lambda x: x["count"], reverse=True)
                
                return {
                    "success": True,
                    "count": len(content_type_list),
                    "content_types": content_type_list
                }
            except Exception as e:
                logger.error(f"Error getting content types: {e}")
                if mcp_error_handling:
                    return mcp_error_handling.handle_exception(
                        e, code="INTERNAL_ERROR", endpoint="/search/content-types", doc_category="search"
                    )
                return {"success": False, "error": str(e)}
                
        return router
    except Exception as e:
        logger.error(f"Error creating search router: {e}")
        # Return an empty router if there's an error
        router = APIRouter(prefix=f"{api_prefix}/search")

        @router.get("/status")
        async def search_status_error():
            error_message = f"Error initializing search: {str(e)}"
            if mcp_error_handling:
                return mcp_error_handling.create_error_response(
                    code="EXTENSION_ERROR",
                    message_override=error_message,
                    doc_category="search"
                )
            return {"success": False, "status": "error", "error": error_message}

        return router


def update_search_status(storage_backends: Dict[str, Any]) -> None:
    """
    Update storage_backends with search status.

    Args:
        storage_backends: Dictionary of storage backends to update
    """
    # Add search as a component
    storage_backends["search"] = {
        "available": SEARCH_AVAILABLE,
        "simulation": False,
        "features": {
            "text_search": True,
            "vector_search": SENTENCE_TRANSFORMERS_AVAILABLE and FAISS_AVAILABLE,
            "hybrid_search": SENTENCE_TRANSFORMERS_AVAILABLE and FAISS_AVAILABLE,
            "content_extraction": True,
            "metadata_filtering": True,
        },
        "version": "1.0.0",
        "endpoints": [
            "/search/status",
            "/search/index",
            "/search/query",
            "/search/metadata/{cid}",
            "/search/remove/{cid}",
            "/search/vector",
            "/search/hybrid",
            "/search/tags",
            "/search/content-types"
        ]
    }
    logger.info("Updated search status in storage backends")


def on_startup(app: Any = None) -> None:
    """
    Initialize the search extension on server startup.
    
    Args:
        app: The FastAPI application instance
    """
    logger.info("Initializing search extension")
    
    # Initialize search service in background
    get_search_service()


def on_shutdown(app: Any = None) -> None:
    """
    Clean up the search extension on server shutdown.
    
    Args:
        app: The FastAPI application instance
    """
    logger.info("Shutting down search extension")
    
    # Save any pending changes
    global _search_service
    if _search_service is not None and hasattr(_search_service, "_save_vector_index"):
        try:
            _search_service._save_vector_index()
            logger.info("Saved vector index on shutdown")
        except Exception as e:
            logger.error(f"Error saving vector index on shutdown: {e}")
