"""WebRTC Dashboard Controller AnyIO Module

This module provides AnyIO-compatible WebRTC dashboard controller functionality.
"""

import anyio
import logging
from typing import Dict, List, Optional, Union, Any

logger = logging.getLogger(__name__)


class WebRTCDashboardControllerAnyIO:
    """AnyIO-compatible controller for WebRTC dashboard operations."""
    
    def __init__(self, webrtc_model):
        """Initialize with a WebRTC model."""
        self.webrtc_model = webrtc_model
        self.logger = logging.getLogger(__name__)
    
    async def get_connections(self, request) -> Dict[str, Any]:
        """Get all active WebRTC connections."""
        self.logger.info("Getting WebRTC connections")
        try:
            connections = await self.webrtc_model.get_connections_async()
            return {
                "connections": connections,
                "count": len(connections),
                "success": True,
                "message": "Connections retrieved successfully"
            }
        except Exception as e:
            self.logger.error(f"Error getting connections: {str(e)}")
            return {
                "connections": [],
                "count": 0,
                "success": False,
                "message": f"Error getting connections: {str(e)}"
            }
    
    async def get_connection_stats(self, request) -> Dict[str, Any]:
        """Get statistics for a specific WebRTC connection."""
        connection_id = request.connection_id
        self.logger.info(f"Getting stats for connection: {connection_id}")
        try:
            stats = await self.webrtc_model.get_connection_stats_async(connection_id)
            return {
                "stats": stats,
                "success": True,
                "message": f"Stats retrieved for connection {connection_id}"
            }
        except Exception as e:
            self.logger.error(f"Error getting connection stats: {str(e)}")
            return {
                "stats": {},
                "success": False,
                "message": f"Error getting connection stats: {str(e)}"
            }
    
    async def close_connection(self, request) -> Dict[str, Any]:
        """Close a specific WebRTC connection."""
        connection_id = request.connection_id
        self.logger.info(f"Closing connection: {connection_id}")
        try:
            await self.webrtc_model.close_connection_async(connection_id)
            return {
                "success": True,
                "message": f"Connection {connection_id} closed successfully"
            }
        except Exception as e:
            self.logger.error(f"Error closing connection: {str(e)}")
            return {
                "success": False,
                "message": f"Error closing connection: {str(e)}"
            }
    
    async def get_system_stats(self, request) -> Dict[str, Any]:
        """Get system-wide WebRTC statistics."""
        self.logger.info("Getting system WebRTC stats")
        try:
            stats = await self.webrtc_model.get_system_stats_async()
            return {
                "stats": stats,
                "success": True,
                "message": "System stats retrieved successfully"
            }
        except Exception as e:
            self.logger.error(f"Error getting system stats: {str(e)}")
            return {
                "stats": {},
                "success": False,
                "message": f"Error getting system stats: {str(e)}"
            }