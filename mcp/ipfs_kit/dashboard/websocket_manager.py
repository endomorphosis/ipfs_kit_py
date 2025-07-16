"""
WebSocket manager for dashboard.
"""

import json
import asyncio
from typing import Set
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections for dashboard."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """Connect a new WebSocket."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Disconnect a WebSocket."""
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        if self.active_connections:
            message_str = json.dumps(message)
            for websocket in self.active_connections.copy():
                try:
                    await websocket.send_text(message_str)
                except:
                    # Remove disconnected websockets
                    self.active_connections.discard(websocket)
