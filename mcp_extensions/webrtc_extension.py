"""
WebRTC extension for MCP server.

This extension integrates WebRTC signaling functionality for peer-to-peer 
communication into the MCP server.
"""

import os
import sys
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, WebSocket, FastAPI

# Configure logging
logger = logging.getLogger(__name__)

# Import the WebRTC module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from mcp_webrtc import create_webrtc_router, get_signaling_server
    WEBRTC_AVAILABLE = True
    logger.info("WebRTC module successfully imported")
except ImportError as e:
    WEBRTC_AVAILABLE = False
    logger.error(f"Error importing WebRTC module: {e}")

def create_webrtc_extension_router(api_prefix: str) -> Optional[APIRouter]:
    """
    Create a FastAPI router for WebRTC endpoints.
    
    Args:
        api_prefix: The API prefix for the endpoints
        
    Returns:
        FastAPI router or None if not available
    """
    if not WEBRTC_AVAILABLE:
        logger.error("WebRTC module not available, cannot create router")
        return None
    
    try:
        # Create the WebRTC router
        router = create_webrtc_router(api_prefix)
        logger.info(f"Successfully created WebRTC router with prefix: {router.prefix}")
        return router
    except Exception as e:
        logger.error(f"Error creating WebRTC router: {e}")
        return None

def update_webrtc_status(storage_backends: Dict[str, Any]) -> None:
    """
    Update storage_backends with WebRTC status.
    
    Args:
        storage_backends: Dictionary of storage backends to update
    """
    # Add WebRTC as a component (or update existing realtime component)
    if "realtime" in storage_backends:
        storage_backends["realtime"]["webrtc"] = WEBRTC_AVAILABLE
        if "features" in storage_backends["realtime"]:
            storage_backends["realtime"]["features"]["webrtc"] = WEBRTC_AVAILABLE
    else:
        storage_backends["realtime"] = {
            "available": WEBRTC_AVAILABLE,
            "simulation": False,
            "features": {
                "webrtc": True,
                "signaling": True,
                "p2p": True
            }
        }
    logger.debug("Updated WebRTC status in storage backends")

def register_app_webrtc_routes(app: FastAPI, api_prefix: str) -> bool:
    """
    Register WebRTC WebSocket routes directly with the FastAPI app.
    
    This is necessary because WebSocket endpoints can't be added via APIRouter.include_router()
    
    Args:
        app: The FastAPI application
        api_prefix: The API prefix for REST endpoints
        
    Returns:
        True if routes were registered successfully
    """
    if not WEBRTC_AVAILABLE:
        return False
    
    try:
        # Create the WebRTC router (but don't use it directly)
        router = create_webrtc_router(api_prefix)
        
        # Register the WebSocket routes directly with the app
        websocket_routes = [route for route in router.routes if isinstance(route, WebSocket)]
        for route in websocket_routes:
            app.routes.append(route)
        
        # Return the REST router for normal inclusion
        return True
    except Exception as e:
        logger.error(f"Error registering WebRTC routes: {e}")
        return False