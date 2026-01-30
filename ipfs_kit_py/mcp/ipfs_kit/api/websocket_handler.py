"""
WebSocket handler for API routes.
"""

import json
import logging
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """WebSocket connection handler."""
    
    def __init__(self, websocket_manager=None):
        self.websocket_manager = websocket_manager
        self.active_connections: Set[WebSocket] = set()
    
    async def handle_websocket(self, websocket: WebSocket):
        """Handle WebSocket connections."""
        await websocket.accept()
        self.active_connections.add(websocket)
        
        try:
            while True:
                # Wait for messages from client
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle different message types
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif message.get("type") == "subscribe":
                    # Handle subscription requests
                    await self._handle_subscription(websocket, message)
                
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
        finally:
            self.active_connections.discard(websocket)
    
    async def _handle_subscription(self, websocket: WebSocket, message: dict):
        """Handle subscription messages."""
        subscription_type = message.get("subscription")
        
        if subscription_type == "backend_updates":
            # Send current backend status
            await websocket.send_text(json.dumps({
                "type": "backend_update",
                "data": {"message": "Backend monitoring active"}
            }))
        elif subscription_type == "system_updates":
            # Send system status
            await websocket.send_text(json.dumps({
                "type": "system_update",
                "data": {"message": "System monitoring active"}
            }))
    
    async def broadcast_to_all(self, message: dict):
        """Broadcast message to all connected clients."""
        if self.active_connections:
            message_str = json.dumps(message)
            for websocket in self.active_connections.copy():
                try:
                    await websocket.send_text(message_str)
                except:
                    # Remove disconnected websockets
                    self.active_connections.discard(websocket)
