"""
WebSocket extension for MCP server.

This extension integrates WebSocket functionality for real-time event streaming
and notifications into the MCP server.
"""

import logging
import os
import sys
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, FastAPI

# Configure logging
logger = logging.getLogger(__name__)

# Import the WebSocket module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from mcp_websocket import create_websocket_router, get_websocket_service

    WEBSOCKET_AVAILABLE = True
    logger.info("WebSocket module successfully imported")
except ImportError as e:
    WEBSOCKET_AVAILABLE = False
    logger.error(f"Error importing WebSocket module: {e}")


def create_websocket_extension_router(
    api_prefix: str,
) -> Tuple[Optional[APIRouter], Optional[APIRouter]]:
    """
    Create a FastAPI router for WebSocket endpoints.

    Args:
        api_prefix: The API prefix for the endpoints

    Returns:
        Tuple of WebSocket router and REST router, or None if not available
    """
    if not WEBSOCKET_AVAILABLE:
        logger.error("WebSocket module not available, cannot create router")
        # Return empty routers if WebSocket is not available
        return None, None

    try:
        # Create the WebSocket router
        websocket_router, rest_router = create_websocket_router(api_prefix)
        logger.info("Successfully created WebSocket routers")
        return websocket_router, rest_router
    except Exception as e:
        logger.error(f"Error creating WebSocket router: {e}")
        return None, None


def update_websocket_status(storage_backends: Dict[str, Any]) -> None:
    """
    Update storage_backends with WebSocket status.

    Args:
        storage_backends: Dictionary of storage backends to update
    """
    # Add WebSocket as a component
    storage_backends["realtime"] = {
        "available": WEBSOCKET_AVAILABLE,
        "simulation": False,
        "features": {
            "websocket": True,
            "events": True,
            "broadcast": True,
            "subscriptions": True,
        },
    }
    logger.debug("Updated WebSocket status in storage backends")


def register_app_websocket_routes(app: FastAPI, api_prefix: str) -> bool:
    """
    Register WebSocket routes directly with the FastAPI app.

    This is necessary because WebSocket endpoints can't be added via APIRouter.include_router()

    Args:
        app: The FastAPI application
        api_prefix: The API prefix for REST endpoints

    Returns:
        True if routes were registered successfully
    """
    if not WEBSOCKET_AVAILABLE:
        return False

    try:
        # Create the WebSocket router (but don't use it directly)
        websocket_router, rest_router = create_websocket_router(api_prefix)

        # Register the WebSocket routes directly with the app
        for route in websocket_router.routes:
            app.routes.append(route)

        # Return the REST router for normal inclusion
        return True
    except Exception as e:
        logger.error(f"Error registering WebSocket routes: {e}")
        return False


def setup_mcp_event_hooks() -> bool:
    """
    Set up event hooks for MCP server operations.

    Returns:
        True if hooks were set up successfully
    """
    if not WEBSOCKET_AVAILABLE:
        return False

    try:
        # Get the WebSocket service
        get_websocket_service()

        # TODO: Register event handlers for various MCP operations
        # This will be implemented when we hook up the events system

        return True
    except Exception as e:
        logger.error(f"Error setting up MCP event hooks: {e}")
        return False
