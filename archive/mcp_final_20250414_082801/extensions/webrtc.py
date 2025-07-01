"""
WebRTC extension for the MCP server.

This extension provides WebRTC functionality for streaming media content.
"""

import logging
from typing import Optional

from fastapi import APIRouter, FastAPI, WebSocket  # Added FastAPI import

# Configure logger
logger = logging.getLogger(__name__)

# Import the WebRTC streaming module if available
try:
    from ipfs_kit_py.webrtc_streaming import (
        HAVE_AIORTC,
        HAVE_CV2,
        HAVE_NUMPY,
        HAVE_WEBRTC,
        check_webrtc_dependencies,
    )

    WEBRTC_AVAILABLE = HAVE_WEBRTC and HAVE_CV2 and HAVE_NUMPY and HAVE_AIORTC
except ImportError:
    WEBRTC_AVAILABLE = False
    HAVE_WEBRTC = False
    HAVE_CV2 = False
    HAVE_NUMPY = False
    HAVE_AIORTC = False

    def check_webrtc_dependencies():
        """Check if WebRTC dependencies are available."""
        return {
            "webrtc_available": False
            "missing_dependencies": ["aiortc", "opencv-python", "numpy"],
            "message": "WebRTC streaming not available - dependencies not installed",
        }


# Create router function
def create_webrtc_router(api_prefix: str) -> Optional[APIRouter]:
    """Create a router for WebRTC endpoints."""
    try:
        router = APIRouter(prefix=api_prefix)
        # Here would be route registrations
        return router
    except Exception as e:
        logger.error(f"Error creating WebRTC router: {e}")
        return None


def create_webrtc_extension_router(api_prefix: str) -> Optional[APIRouter]:
    """
    Create a FastAPI router for WebRTC endpoints.

    Args:
        api_prefix: The API prefix to use for the router

    Returns:
        The created router or None if an error occurred
    """
    logger.info("Creating WebRTC extension router")

    if not WEBRTC_AVAILABLE:
        logger.warning("WebRTC not available, extension will be limited")

    try:
        # Create the WebRTC router
        router = create_webrtc_router(api_prefix)
        logger.info(f"Successfully created WebRTC router with prefix: {router.prefix}")
        return router
    except Exception as e:
        logger.error(f"Error creating WebRTC router: {e}")
        return None


# Removed mock FastAPI class definition as the real one is now imported


def register_app_webrtc_routes(app: FastAPI, api_prefix: str) -> bool:
    """
    Register WebRTC WebSocket routes directly with the FastAPI app.

    Args:
        app: The FastAPI app
        api_prefix: The API prefix to use for routes

    Returns:
        True if registration succeeded, False otherwise
    """
    logger.info(f"Registering WebRTC routes directly with app using prefix: {api_prefix}")

    if not WEBRTC_AVAILABLE:
        logger.warning("WebRTC not available, no routes will be registered")
        return False

    try:
        # Create the WebRTC router (but don't use it directly)
        router = create_webrtc_router(api_prefix)

        # Register the WebSocket routes directly with the app
        websocket_routes = [route for route in router.routes if isinstance(route, WebSocket)]
        for route in websocket_routes:
            app.routes.append(route)

        logger.info(f"Successfully registered {len(websocket_routes)} WebRTC routes with app")
        return True
    except Exception as e:
        logger.error(f"Error registering WebRTC routes: {e}")
        return False
