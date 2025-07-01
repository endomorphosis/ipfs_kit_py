"""
Search extension for MCP server.

This extension integrates the search functionality from mcp_search.py
into the MCP server, providing content indexing, metadata search, and
vector search capabilities.
"""

import logging
import os
import sys
from typing import Any, Dict

from fastapi import APIRouter

# Configure logging
logger = logging.getLogger(__name__)

# Import the search module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from mcp_search import create_search_router

    SEARCH_AVAILABLE = True
    logger.info("Search module successfully imported")
except ImportError as e:
    SEARCH_AVAILABLE = False
    logger.error(f"Error importing search module: {e}")

# Optional dependencies check
try:
    #     from sentence_transformers import SentenceTransformer
    # Unused import commented out

    SENTENCE_TRANSFORMERS_AVAILABLE = True
    logger.info("Sentence Transformers available for vector embeddings")
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning(
        "Sentence Transformers not available. Install with: pip install sentence-transformers"
    )

try:
    #     import faiss
    # Unused import commented out

    FAISS_AVAILABLE = True
    logger.info("FAISS available for vector search")
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("FAISS not available. Install with: pip install faiss-cpu")


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
            return {
                "success": False
                "status": "unavailable",
                "error": "Search functionality is not available",
            }

        return router

    try:
        # Create the search router
        router = create_search_router(api_prefix)
        logger.info(f"Successfully created search router with prefix: {router.prefix}")
        return router
    except Exception as e:
        logger.error(f"Error creating search router: {e}")
        # Return an empty router if there's an error
        router = APIRouter(prefix=f"{api_prefix}/search")

        @router.get("/status")
        async def search_status_error(e=Exception("Search functionality not available")):
            return {"success": False, "status": "error", "error": str(e)}

        return router


def update_search_status(storage_backends: Dict[str, Any]) -> None:
    """
    Update storage_backends with search status.

    Args:
        storage_backends: Dictionary of storage backends to update
    """
    # Add search as a component
    storage_backends["search"] = {
        "available": SEARCH_AVAILABLE
        "simulation": False
        "features": {
            "text_search": True
            "vector_search": SENTENCE_TRANSFORMERS_AVAILABLE and FAISS_AVAILABLE,
            "hybrid_search": SENTENCE_TRANSFORMERS_AVAILABLE and FAISS_AVAILABLE,
            "content_extraction": True
            "metadata_filtering": True
        },
    }
    logger.debug("Updated search status in storage backends")
