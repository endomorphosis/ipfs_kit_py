"""
MCP Server SSE and CORS Fix

This module patches the MCP server to properly handle SSE (Server-Sent Events)
and CORS (Cross-Origin Resource Sharing) issues.
"""

import logging
from typing import Any, Dict, List, Optional, Union
import importlib

# Configure logger
logger = logging.getLogger(__name__)

def patch_fastapi_app(app=None):
    """
    Patch a FastAPI app to handle SSE and CORS correctly.
    
    Args:
        app: The FastAPI app instance to patch
        
    Returns:
        bool: True if patching was successful, False otherwise
    """
    try:
        import fastapi
        from fastapi.middleware.cors import CORSMiddleware
        from starlette.responses import StreamingResponse
        
        if app is None:
            # Try to find the app in the imported modules
            try:
                app_module = importlib.import_module("ipfs_kit_py.run_mcp_server_real_storage")
                app = getattr(app_module, "app", None)
            except ImportError:
                try:
                    app_module = importlib.import_module("ipfs_kit_py.mcp.run_mcp_server_real_storage")
                    app = getattr(app_module, "app", None)
                except ImportError:
                    logger.error("Could not import run_mcp_server_real_storage module")
                    return False
        
        if app is None:
            logger.error("Could not find app instance")
            return False
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Allow all origins for testing
            allow_credentials=True,
            allow_methods=["*"],  # Allow all methods
            allow_headers=["*"],  # Allow all headers
            expose_headers=["Content-Type", "Content-Length", "Cache-Control", 
                          "X-MCP-Server", "X-MCP-Version", "X-Accel-Buffering"],
        )
        
        # Patch the app to handle SSE correctly
        original_route = app.router.add_api_route
        
        def patched_route(path, endpoint, *args, **kwargs):
            """Patched route that adds SSE headers for streaming endpoints."""
            async def wrapped_endpoint(*endpoint_args, **endpoint_kwargs):
                response = await endpoint(*endpoint_args, **endpoint_kwargs)
                
                # Check if this is a streaming response
                if isinstance(response, StreamingResponse):
                    # Add necessary SSE headers
                    response.headers["Content-Type"] = "text/event-stream"
                    response.headers["Cache-Control"] = "no-cache"
                    response.headers["Connection"] = "keep-alive"
                    response.headers["X-Accel-Buffering"] = "no"
                
                return response
            
            # Use the original route function with our wrapped endpoint
            return original_route(path, wrapped_endpoint, *args, **kwargs)
        
        # Replace the original route function with our patched version
        app.router.add_api_route = patched_route
        
        logger.info("Successfully patched FastAPI app for SSE and CORS")
        return True
    
    except Exception as e:
        logger.error(f"Error patching FastAPI app: {e}")
        return False

def add_sse_endpoint(app=None):
    """
    Add a test SSE endpoint to the FastAPI app.
    
    Args:
        app: The FastAPI app instance to add the endpoint to
        
    Returns:
        bool: True if adding the endpoint was successful, False otherwise
    """
    try:
        import fastapi
        from fastapi import APIRouter
        from starlette.responses import StreamingResponse
        import asyncio
        
        if app is None:
            # Try to find the app in the imported modules
            try:
                app_module = importlib.import_module("ipfs_kit_py.run_mcp_server_real_storage")
                app = getattr(app_module, "app", None)
            except ImportError:
                try:
                    app_module = importlib.import_module("ipfs_kit_py.mcp.run_mcp_server_real_storage")
                    app = getattr(app_module, "app", None)
                except ImportError:
                    logger.error("Could not import run_mcp_server_real_storage module")
                    return False
        
        if app is None:
            logger.error("Could not find app instance")
            return False
        
        # Create a test SSE endpoint
        async def sse_endpoint():
            """Test SSE endpoint that sends a message every second."""
            async def event_generator():
                """Generate SSE events."""
                for i in range(10):
                    # This is the SSE format
                    yield f"data: {{'message': 'SSE test message {i}'}}\n\n"
                    await asyncio.sleep(1)
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        
        # Add the endpoint
        app.add_api_route("/api/v0/test/sse", sse_endpoint, methods=["GET"])
        
        logger.info("Successfully added test SSE endpoint")
        return True
    
    except Exception as e:
        logger.error(f"Error adding SSE endpoint: {e}")
        return False

def patch_mcp_server_for_sse():
    """
    Patch the MCP server to handle SSE correctly.
    
    Returns:
        bool: True if patching was successful, False otherwise
    """
    success = True
    
    # Patch the FastAPI app
    if not patch_fastapi_app():
        logger.warning("Failed to patch FastAPI app for SSE and CORS")
        success = False
    
    # Add a test SSE endpoint
    if not add_sse_endpoint():
        logger.warning("Failed to add test SSE endpoint")
        success = False
    
    return success

# If this module is imported, apply the patches automatically
if __name__ != "__main__":
    patch_mcp_server_for_sse()
