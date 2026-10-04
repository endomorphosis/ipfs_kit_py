"""
Streaming extension for MCP server.

This extension integrates the streaming functionality from mcp_streaming.py
into the MCP server, providing optimized file streaming capabilities.
"""

import logging
import os
import sys
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, FastAPI

# Configure logging
logger = logging.getLogger(__name__)

# Import the error handling module
try:
    import mcp_error_handling
except ImportError:
    logger.warning("mcp_error_handling module not available, using local error handling")
    mcp_error_handling = None

# Import the streaming module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from mcp_streaming import create_streaming_router, StreamingOperations
    STREAMING_AVAILABLE = True
    logger.info("Streaming module successfully imported")
except ImportError as e:
    STREAMING_AVAILABLE = False
    logger.error(f"Error importing streaming module: {e}")

# Initialize streaming operations
_streaming_ops = None

def get_streaming_ops():
    """Get or initialize the streaming operations."""
    global _streaming_ops
    if _streaming_ops is None and STREAMING_AVAILABLE:
        try:
            _streaming_ops = StreamingOperations()
            logger.info("Streaming operations initialized")
        except Exception as e:
            logger.error(f"Error initializing streaming operations: {e}")
    return _streaming_ops

def create_streaming_router_wrapper(api_prefix: str) -> APIRouter:
    """
    Create a FastAPI router for streaming endpoints.

    Args:
        api_prefix: The API prefix for the endpoints

    Returns:
        FastAPI router
    """
    if not STREAMING_AVAILABLE:
        logger.error("Streaming module not available, cannot create router")
        # Return an empty router if streaming is not available
        router = APIRouter(prefix=f"{api_prefix}/stream")

        @router.get("/status")
        async def streaming_status_unavailable():
            """Return status when streaming is unavailable."""
            return {
                "success": False,
                "status": "unavailable",
                "error": "Streaming functionality is not available",
                "message": "Ensure IPFS daemon is running and accessible"
            }

        return router

    try:
        # Initialize streaming operations
        get_streaming_ops()
        
        # Create the streaming router
        router = create_streaming_router(api_prefix)
        logger.info(f"Successfully created streaming router with prefix: {router.prefix}")
        
        # Add additional status endpoint
        
        @router.get("/status")
        async def streaming_status(streaming_ops=get_streaming_ops()):
            """Return status of streaming functionality."""
            if not streaming_ops:
                error_message = "Streaming service not available"
                if mcp_error_handling:
                    return mcp_error_handling.create_error_response(
                        code="EXTENSION_NOT_AVAILABLE",
                        message_override=error_message,
                        doc_category="streaming"
                    )
                return {"success": False, "error": error_message}
            
            try:
                # Check if IPFS daemon is running
                import subprocess
                import json
                
                process = subprocess.run(
                    ["ipfs", "id", "--format=json"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if process.returncode != 0:
                    return {
                        "success": False,
                        "status": "daemon_error",
                        "error": "IPFS daemon is not running or not accessible",
                        "details": process.stderr.strip()
                    }
                
                # Parse IPFS ID info
                id_info = json.loads(process.stdout.strip())
                
                return {
                    "success": True,
                    "status": "available",
                    "ipfs_node": {
                        "id": id_info.get("ID"),
                        "addresses": id_info.get("Addresses", []),
                        "agent_version": id_info.get("AgentVersion")
                    },
                    "features": {
                        "streaming_upload": True,
                        "streaming_download": True,
                        "background_pinning": True,
                        "dag_import_export": True,
                        "progress_tracking": True
                    },
                    "chunk_size": streaming_ops.chunk_size
                }
            except Exception as e:
                logger.error(f"Error checking streaming status: {e}")
                if mcp_error_handling:
                    return mcp_error_handling.handle_exception(
                        e, code="INTERNAL_ERROR", endpoint="/stream/status", doc_category="streaming"
                    )
                return {"success": False, "error": str(e)}
                
        return router
    except Exception as e:
        logger.error(f"Error creating streaming router: {e}")
        # Return an empty router if there's an error
        router = APIRouter(prefix=f"{api_prefix}/stream")

        @router.get("/status")
        async def streaming_status_error():
            error_message = f"Error initializing streaming: {str(e)}"
            if mcp_error_handling:
                return mcp_error_handling.create_error_response(
                    code="EXTENSION_ERROR",
                    message_override=error_message,
                    doc_category="streaming"
                )
            return {"success": False, "status": "error", "error": error_message}

        return router


def update_streaming_status(storage_backends: Dict[str, Any]) -> None:
    """
    Update storage_backends with streaming status.

    Args:
        storage_backends: Dictionary of storage backends to update
    """
    # Add streaming as a component
    storage_backends["streaming"] = {
        "available": STREAMING_AVAILABLE,
        "simulation": False,
        "features": {
            "streaming_upload": True,
            "streaming_download": True,
            "background_pinning": True,
            "dag_import_export": True,
            "progress_tracking": True
        },
        "version": "1.0.0",
        "endpoints": [
            "/stream/status",
            "/stream/add",
            "/stream/cat/{cid}",
            "/stream/download",
            "/stream/pin",
            "/stream/unpin",
            "/stream/dag/export/{cid}",
            "/stream/dag/import"
        ]
    }
    logger.info("Updated streaming status in storage backends")


def on_startup(app: Optional[FastAPI] = None) -> None:
    """
    Initialize the streaming extension on server startup.
    
    Args:
        app: The FastAPI application instance
    """
    logger.info("Initializing streaming extension")
    
    # Initialize streaming operations in background
    get_streaming_ops()


def on_shutdown(app: Optional[FastAPI] = None) -> None:
    """
    Clean up the streaming extension on server shutdown.
    
    Args:
        app: The FastAPI application instance
    """
    logger.info("Shutting down streaming extension")
    
    # No specific cleanup required for streaming operations
    global _streaming_ops
    _streaming_ops = None