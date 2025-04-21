"""WebRTC Controller AnyIO Module

This module provides AnyIO-compatible WebRTC controller functionality.
"""

import anyio
import logging
from typing import Dict, List, Optional, Union, Any, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ResourceStatsResponse(BaseModel):
    """Response model for resource statistics."""
    cpu_percent: float = Field(0.0, description="CPU usage percentage")
    memory_percent: float = Field(0.0, description="Memory usage percentage")
    disk_usage: Dict[str, float] = Field(default_factory=dict, description="Disk usage by path")
    network_io: Dict[str, int] = Field(default_factory=dict, description="Network IO statistics")
    connection_count: int = Field(0, description="Number of active connections")
    uptime_seconds: int = Field(0, description="System uptime in seconds")
    timestamp: float = Field(..., description="Timestamp of the statistics collection")


class WebRTCResponse:
    """Base response model for WebRTC operations."""
    
    def __init__(self, success: bool, message: str = "", data: Optional[Dict[str, Any]] = None):
        self.success = success
        self.message = message
        self.data = data or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data
        }


class WebRTCControllerAnyIO:
    """AnyIO-compatible controller for WebRTC operations."""
    
    def __init__(self, webrtc_model):
        """Initialize with a WebRTC model."""
        self.webrtc_model = webrtc_model
        self.logger = logging.getLogger(__name__)
    
    async def create_offer(self, request) -> WebRTCResponse:
        """Create a WebRTC offer."""
        self.logger.info("Creating WebRTC offer")
        try:
            offer = await self.webrtc_model.create_offer_async()
            return WebRTCResponse(
                success=True,
                message="Offer created successfully",
                data={"offer": offer}
            )
        except Exception as e:
            self.logger.error(f"Error creating offer: {str(e)}")
            return WebRTCResponse(
                success=False,
                message=f"Error creating offer: {str(e)}"
            )
    
    async def create_answer(self, request) -> WebRTCResponse:
        """Create a WebRTC answer in response to an offer."""
        self.logger.info("Creating WebRTC answer")
        try:
            offer = request.data.get("offer", {})
            if not offer:
                return WebRTCResponse(
                    success=False,
                    message="Missing offer in request"
                )
            
            answer = await self.webrtc_model.create_answer_async(offer)
            return WebRTCResponse(
                success=True,
                message="Answer created successfully",
                data={"answer": answer}
            )
        except Exception as e:
            self.logger.error(f"Error creating answer: {str(e)}")
            return WebRTCResponse(
                success=False,
                message=f"Error creating answer: {str(e)}"
            )
    
    async def add_ice_candidate(self, request) -> WebRTCResponse:
        """Add an ICE candidate to the WebRTC connection."""
        self.logger.info("Adding ICE candidate")
        try:
            candidate = request.data.get("candidate", {})
            if not candidate:
                return WebRTCResponse(
                    success=False,
                    message="Missing candidate in request"
                )
            
            await self.webrtc_model.add_ice_candidate_async(candidate)
            return WebRTCResponse(
                success=True,
                message="ICE candidate added successfully"
            )
        except Exception as e:
            self.logger.error(f"Error adding ICE candidate: {str(e)}")
            return WebRTCResponse(
                success=False,
                message=f"Error adding ICE candidate: {str(e)}"
            )
    
    async def close_connection(self, request) -> WebRTCResponse:
        """Close the WebRTC connection."""
        self.logger.info("Closing WebRTC connection")
        try:
            connection_id = request.data.get("connection_id")
            if not connection_id:
                return WebRTCResponse(
                    success=False,
                    message="Missing connection_id in request"
                )
            
            await self.webrtc_model.close_connection_async(connection_id)
            return WebRTCResponse(
                success=True,
                message="Connection closed successfully"
            )
        except Exception as e:
            self.logger.error(f"Error closing connection: {str(e)}")
            return WebRTCResponse(
                success=False,
                message=f"Error closing connection: {str(e)}"
            )
            
    async def get_resource_stats(self, request) -> WebRTCResponse:
        """Get system resource statistics."""
        self.logger.info("Getting resource statistics")
        try:
            stats = await self.webrtc_model.get_resource_stats_async()
            
            # Convert to ResourceStatsResponse model
            response_data = ResourceStatsResponse(
                cpu_percent=stats.get("cpu_percent", 0.0),
                memory_percent=stats.get("memory_percent", 0.0),
                disk_usage=stats.get("disk_usage", {}),
                network_io=stats.get("network_io", {}),
                connection_count=stats.get("connection_count", 0),
                uptime_seconds=stats.get("uptime_seconds", 0),
                timestamp=stats.get("timestamp", 0.0)
            )
            
            return WebRTCResponse(
                success=True,
                message="Resource statistics retrieved successfully",
                data={"stats": response_data.dict()}
            )
        except Exception as e:
            self.logger.error(f"Error getting resource statistics: {str(e)}")
            return WebRTCResponse(
                success=False,
                message=f"Error getting resource statistics: {str(e)}"
            )