"""
WebRTC Dashboard Controller AnyIO Module

This module provides AnyIO-compatible WebRTC dashboard controller functionality.
"""

import anyio
import logging
import sys
import os
import time
from typing import Dict, List, Optional, Union, Any, Callable
from pydantic import BaseModel, Field

# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import mcp_error_handling

logger = logging.getLogger(__name__)


class DashboardStatsResponse(BaseModel):
    """Response model for dashboard statistics."""
    success: bool = Field(..., description="Whether the operation was successful")
    timestamp: int = Field(..., description="Timestamp of the statistics")
    active_streams: int = Field(0, description="Number of active streams")
    active_connections: int = Field(0, description="Number of active connections")
    bandwidth_usage: Dict[str, float] = Field(default_factory=dict, description="Bandwidth usage statistics")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class StreamListResponse(BaseModel):
    """Response model for stream listings."""
    success: bool = Field(..., description="Whether the operation was successful")
    streams: List[Dict[str, Any]] = Field(default_factory=list, description="List of active streams")
    count: int = Field(0, description="Number of active streams")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class WebRTCDashboardControllerAnyIO:
    """AnyIO-compatible controller for WebRTC dashboard operations."""

    def __init__(self, webrtc_model):
        """
        Initialize with a WebRTC model.
        
        Args:
            webrtc_model: WebRTC model to use for dashboard operations
        """
        self.webrtc_model = webrtc_model
        self.logger = logging.getLogger(__name__)
        logger.info("WebRTC Dashboard Controller (AnyIO) initialized")

    def register_routes(self, router):
        """
        Register routes with a FastAPI router.
        
        Args:
            router: FastAPI router to register routes with
        """
        # Get dashboard statistics
        router.add_api_route(
            "/stats",
            self.get_dashboard_stats,
            methods=["GET"],
            response_model=DashboardStatsResponse,
            summary="Get dashboard statistics",
            description="Get statistics about WebRTC usage"
        )
        
        # List active streams
        router.add_api_route(
            "/streams",
            self.list_streams,
            methods=["GET"],
            response_model=StreamListResponse,
            summary="List active streams",
            description="List all active WebRTC streams"
        )
        
        # Serve dashboard UI
        router.add_api_route(
            "/",
            self.serve_dashboard,
            methods=["GET"],
            summary="Serve dashboard UI",
            description="Serve the WebRTC dashboard UI"
        )
        
        logger.info("WebRTC Dashboard Controller (AnyIO) routes registered")
    
    async def get_dashboard_stats(self) -> Dict[str, Any]:
        """
        Get dashboard statistics.
        
        Returns:
            Dictionary with dashboard statistics
        """
        try:
            logger.info("Getting WebRTC dashboard statistics")
            
            # Call the model's get_dashboard_stats method
            result = await self.webrtc_model.get_dashboard_stats()
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error getting dashboard statistics: {error_msg}")
                return {
                    "success": False,
                    "timestamp": int(time.time()),
                    "error": error_msg
                }
            
            return {
                "success": True,
                "timestamp": result.get("timestamp", int(time.time())),
                "active_streams": result.get("active_streams", 0),
                "active_connections": result.get("active_connections", 0),
                "bandwidth_usage": result.get("bandwidth_usage", {})
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboard statistics: {e}")
            return {
                "success": False,
                "timestamp": int(time.time()),
                "error": str(e)
            }
    
    async def list_streams(self) -> Dict[str, Any]:
        """
        List active streams.
        
        Returns:
            Dictionary with list of active streams
        """
        try:
            logger.info("Listing active WebRTC streams")
            
            # Call the model's list_streams method
            result = await self.webrtc_model.list_streams()
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error listing streams: {error_msg}")
                return {
                    "success": False,
                    "streams": [],
                    "count": 0,
                    "error": error_msg
                }
            
            streams = result.get("streams", [])
            return {
                "success": True,
                "streams": streams,
                "count": len(streams)
            }
            
        except Exception as e:
            logger.error(f"Error listing streams: {e}")
            return {
                "success": False,
                "streams": [],
                "count": 0,
                "error": str(e)
            }
    
    async def serve_dashboard(self):
        """
        Serve the WebRTC dashboard UI.
        
        Returns:
            HTML content for the dashboard
        """
        try:
            logger.info("Serving WebRTC dashboard UI")
            
            # Call the model's get_dashboard_html method
            result = await self.webrtc_model.get_dashboard_html()
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error serving dashboard UI: {error_msg}")
                return {"error": error_msg}
            
            return result.get("html", "<html><body><h1>WebRTC Dashboard</h1><p>No data available</p></body></html>")
            
        except Exception as e:
            logger.error(f"Error serving dashboard UI: {e}")
            return {"error": str(e)}


def create_webrtc_dashboard_router_anyio(webrtc_model) -> Any:
    """
    Create a FastAPI router for WebRTC dashboard operations.
    
    Args:
        webrtc_model: WebRTC model to use for dashboard operations
        
    Returns:
        FastAPI router with WebRTC dashboard routes registered
    """
    try:
        from fastapi import APIRouter
        
        controller = WebRTCDashboardControllerAnyIO(webrtc_model)
        router = APIRouter(prefix="/dashboard", tags=["webrtc-dashboard"])
        controller.register_routes(router)
        
        return router
    except ImportError as e:
        logger.error(f"Error creating WebRTC dashboard router: {e}")
        return None


# Add aliases for backward compatibility
create_webrtc_dashboard_controller_anyio = WebRTCDashboardControllerAnyIO
