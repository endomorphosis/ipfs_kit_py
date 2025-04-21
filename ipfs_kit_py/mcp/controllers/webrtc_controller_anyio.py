"""
WebRTC Controller AnyIO Module

This module provides AnyIO-compatible WebRTC controller functionality.
"""

import anyio
import logging
import sys
import os
from typing import Dict, List, Optional, Union, Any, Tuple
from pydantic import BaseModel, Field

# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import mcp_error_handling

logger = logging.getLogger(__name__)


class ResourceStatsResponse(BaseModel):
    """Response model for resource statistics."""
    cpu_percent: float = Field(0.0, description="CPU usage percentage")
    memory_percent: float = Field(0.0, description="Memory usage percentage")
    disk_usage: Dict[str, float] = Field(default_factory=dict, description="Disk usage by path")
    network_io: Dict[str, int] = Field(default_factory=dict, description="Network IO statistics")
    connection_count: int = Field(0, description="Number of active connections")


class StreamRequest(BaseModel):
    """Request model for WebRTC streaming operations."""
    stream_id: str = Field(..., description="Unique identifier for the stream")
    stream_type: str = Field("video", description="Type of stream (video, audio, data)")
    quality: Optional[str] = Field("medium", description="Stream quality (low, medium, high)")
    max_bitrate: Optional[int] = Field(None, description="Maximum bitrate in kbps")
    encryption: Optional[bool] = Field(True, description="Whether to use encryption")
    peer_id: Optional[str] = Field(None, description="Target peer ID for direct connections")


class StreamResponse(BaseModel):
    """Response model for WebRTC streaming operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    stream_id: str = Field(..., description="Unique identifier for the stream")
    peer_connection_id: Optional[str] = Field(None, description="ID of the peer connection")
    ice_candidates: Optional[List[Dict[str, Any]]] = Field(None, description="ICE candidates")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class WebRTCConnectionRequest(BaseModel):
    """Request model for WebRTC connection operations."""
    peer_id: str = Field(..., description="ID of the peer to connect to")
    connection_type: str = Field("p2p", description="Type of connection (p2p, relay)")
    offer_sdp: Optional[str] = Field(None, description="SDP offer for the connection")
    ice_candidates: Optional[List[Dict[str, Any]]] = Field(None, description="ICE candidates")


class WebRTCConnectionResponse(BaseModel):
    """Response model for WebRTC connection operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    connection_id: Optional[str] = Field(None, description="ID of the established connection")
    answer_sdp: Optional[str] = Field(None, description="SDP answer for the connection")
    ice_candidates: Optional[List[Dict[str, Any]]] = Field(None, description="ICE candidates")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class WebRTCStatsRequest(BaseModel):
    """Request model for WebRTC statistics."""
    connection_id: str = Field(..., description="ID of the connection to get stats for")
    stats_type: str = Field("all", description="Type of stats to get (all, inbound, outbound)")


class WebRTCStatsResponse(BaseModel):
    """Response model for WebRTC statistics."""
    success: bool = Field(..., description="Whether the operation was successful")
    connection_id: str = Field(..., description="ID of the connection")
    timestamp: int = Field(..., description="Timestamp of the stats")
    inbound_stats: Optional[Dict[str, Any]] = Field(None, description="Inbound stream statistics")
    outbound_stats: Optional[Dict[str, Any]] = Field(None, description="Outbound stream statistics")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class WebRTCControllerAnyIO:
    """WebRTC controller with AnyIO support."""

    def __init__(self, webrtc_model):
        """
        Initialize the WebRTC controller.

        Args:
            webrtc_model: WebRTC model for handling WebRTC operations
        """
        self.webrtc_model = webrtc_model
        logger.info("WebRTC Controller (AnyIO) initialized")

    def register_routes(self, router):
        """
        Register routes with a FastAPI router.

        Args:
            router: FastAPI router to register routes with
        """
        # Create a WebRTC stream
        router.add_api_route(
            "/stream/create",
            self.create_stream,
            methods=["POST"],
            response_model=StreamResponse,
            summary="Create WebRTC stream",
            description="Create a new WebRTC stream for video, audio, or data"
        )

        # Close a WebRTC stream
        router.add_api_route(
            "/stream/close/{stream_id}",
            self.close_stream,
            methods=["DELETE"],
            response_model=StreamResponse,
            summary="Close WebRTC stream",
            description="Close an existing WebRTC stream"
        )

        # Establish a WebRTC connection
        router.add_api_route(
            "/connection/establish",
            self.establish_connection,
            methods=["POST"],
            response_model=WebRTCConnectionResponse,
            summary="Establish WebRTC connection",
            description="Establish a WebRTC connection with a peer"
        )

        # Close a WebRTC connection
        router.add_api_route(
            "/connection/close/{connection_id}",
            self.close_connection,
            methods=["DELETE"],
            response_model=WebRTCConnectionResponse,
            summary="Close WebRTC connection",
            description="Close an existing WebRTC connection"
        )

        # Get WebRTC connection statistics
        router.add_api_route(
            "/stats",
            self.get_stats,
            methods=["POST"],
            response_model=WebRTCStatsResponse,
            summary="Get WebRTC statistics",
            description="Get statistics for a WebRTC connection"
        )

        # Get WebRTC resource usage
        router.add_api_route(
            "/resources",
            self.get_resource_usage,
            methods=["GET"],
            response_model=ResourceStatsResponse,
            summary="Get WebRTC resource usage",
            description="Get resource usage statistics for WebRTC operations"
        )

        logger.info("WebRTC Controller (AnyIO) routes registered")

    async def create_stream(self, request: StreamRequest) -> Dict[str, Any]:
        """
        Create a WebRTC stream.

        Args:
            request: Stream creation request

        Returns:
            Dictionary with operation results
        """
        try:
            logger.info(f"Creating WebRTC stream of type {request.stream_type}")
            
            # Call the model's create_stream method
            result = await self.webrtc_model.create_stream(
                stream_id=request.stream_id,
                stream_type=request.stream_type,
                quality=request.quality,
                max_bitrate=request.max_bitrate,
                encryption=request.encryption,
                peer_id=request.peer_id
            )
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error creating WebRTC stream: {error_msg}")
                return {
                    "success": False,
                    "stream_id": request.stream_id,
                    "error": error_msg
                }
            
            return {
                "success": True,
                "stream_id": request.stream_id,
                "peer_connection_id": result.get("peer_connection_id"),
                "ice_candidates": result.get("ice_candidates")
            }
            
        except Exception as e:
            logger.error(f"Error creating WebRTC stream: {e}")
            return {
                "success": False,
                "stream_id": request.stream_id,
                "error": str(e)
            }

    async def close_stream(self, stream_id: str) -> Dict[str, Any]:
        """
        Close a WebRTC stream.

        Args:
            stream_id: ID of the stream to close

        Returns:
            Dictionary with operation results
        """
        try:
            logger.info(f"Closing WebRTC stream: {stream_id}")
            
            # Call the model's close_stream method
            result = await self.webrtc_model.close_stream(stream_id)
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error closing WebRTC stream: {error_msg}")
                return {
                    "success": False,
                    "stream_id": stream_id,
                    "error": error_msg
                }
            
            return {
                "success": True,
                "stream_id": stream_id
            }
            
        except Exception as e:
            logger.error(f"Error closing WebRTC stream: {e}")
            return {
                "success": False,
                "stream_id": stream_id,
                "error": str(e)
            }

    async def establish_connection(self, request: WebRTCConnectionRequest) -> Dict[str, Any]:
        """
        Establish a WebRTC connection.

        Args:
            request: Connection establishment request

        Returns:
            Dictionary with operation results
        """
        try:
            logger.info(f"Establishing WebRTC connection with peer: {request.peer_id}")
            
            # Call the model's establish_connection method
            result = await self.webrtc_model.establish_connection(
                peer_id=request.peer_id,
                connection_type=request.connection_type,
                offer_sdp=request.offer_sdp,
                ice_candidates=request.ice_candidates
            )
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error establishing WebRTC connection: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
            
            return {
                "success": True,
                "connection_id": result.get("connection_id"),
                "answer_sdp": result.get("answer_sdp"),
                "ice_candidates": result.get("ice_candidates")
            }
            
        except Exception as e:
            logger.error(f"Error establishing WebRTC connection: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def close_connection(self, connection_id: str) -> Dict[str, Any]:
        """
        Close a WebRTC connection.

        Args:
            connection_id: ID of the connection to close

        Returns:
            Dictionary with operation results
        """
        try:
            logger.info(f"Closing WebRTC connection: {connection_id}")
            
            # Call the model's close_connection method
            result = await self.webrtc_model.close_connection(connection_id)
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error closing WebRTC connection: {error_msg}")
                return {
                    "success": False,
                    "connection_id": connection_id,
                    "error": error_msg
                }
            
            return {
                "success": True,
                "connection_id": connection_id
            }
            
        except Exception as e:
            logger.error(f"Error closing WebRTC connection: {e}")
            return {
                "success": False,
                "connection_id": connection_id,
                "error": str(e)
            }

    async def get_stats(self, request: WebRTCStatsRequest) -> Dict[str, Any]:
        """
        Get WebRTC connection statistics.

        Args:
            request: Statistics request

        Returns:
            Dictionary with operation results
        """
        try:
            logger.info(f"Getting WebRTC stats for connection: {request.connection_id}")
            
            # Call the model's get_stats method
            result = await self.webrtc_model.get_stats(
                connection_id=request.connection_id,
                stats_type=request.stats_type
            )
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error getting WebRTC stats: {error_msg}")
                return {
                    "success": False,
                    "connection_id": request.connection_id,
                    "error": error_msg
                }
            
            return {
                "success": True,
                "connection_id": request.connection_id,
                "timestamp": result.get("timestamp"),
                "inbound_stats": result.get("inbound_stats"),
                "outbound_stats": result.get("outbound_stats")
            }
            
        except Exception as e:
            logger.error(f"Error getting WebRTC stats: {e}")
            return {
                "success": False,
                "connection_id": request.connection_id,
                "error": str(e)
            }

    async def get_resource_usage(self) -> Dict[str, Any]:
        """
        Get WebRTC resource usage.

        Returns:
            Dictionary with resource usage statistics
        """
        try:
            logger.info("Getting WebRTC resource usage")
            
            # Call the model's get_resource_usage method
            result = await self.webrtc_model.get_resource_usage()
            
            return {
                "cpu_percent": result.get("cpu_percent", 0.0),
                "memory_percent": result.get("memory_percent", 0.0),
                "disk_usage": result.get("disk_usage", {}),
                "network_io": result.get("network_io", {}),
                "connection_count": result.get("connection_count", 0)
            }
            
        except Exception as e:
            logger.error(f"Error getting WebRTC resource usage: {e}")
            return {
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "disk_usage": {},
                "network_io": {},
                "connection_count": 0
            }
