"""
WebRTC extension for the MCP server.

This extension provides WebRTC functionality for peer-to-peer communication, including:
- Signaling for WebRTC peer connection establishment
- Room-based peer discovery
- Direct data channel communication
- Efficient binary data transfer
"""

import logging
import os
import sys
import json
import uuid
from typing import Dict, Any, List, Optional, Set, Callable

from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException
from fastapi.responses import JSONResponse

# Configure logger
logger = logging.getLogger(__name__)

# Import the error handling module if available
try:
    import mcp_error_handling
except ImportError:
    logger.warning("mcp_error_handling module not available, using local error handling")
    mcp_error_handling = None

# Import the WebRTC dependencies
try:
    from ipfs_kit_py.webrtc_streaming import (
        HAVE_AIORTC,
        HAVE_CV2,
        HAVE_NUMPY,
        check_webrtc_dependencies,
    )
    
    HAVE_WEBRTC = True
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
            "webrtc_available": False,
            "missing_dependencies": ["aiortc", "opencv-python", "numpy"],
            "message": "WebRTC streaming not available - dependencies not installed",
        }

# Signaling server components
class WebRTCSignalingManager:
    """
    Manager for WebRTC signaling operations.
    
    Handles:
    - Room management for peer discovery
    - Signaling message exchange
    - Connection tracking
    """
    
    def __init__(self):
        """Initialize the WebRTC signaling manager."""
        # Room management
        self.rooms: Dict[str, Set[WebSocket]] = {}
        # Connection tracking
        self.active_connections: Dict[str, Dict[str, Any]] = {}
        # Client information mapping (client_id -> info)
        self.client_info: Dict[str, Dict[str, Any]] = {}
        
        logger.info("WebRTC signaling manager initialized")
    
    async def connect(self, websocket: WebSocket, room_id: str, client_id: Optional[str] = None) -> str:
        """
        Connect a WebSocket client to a room.
        
        Args:
            websocket: The WebSocket connection
            room_id: The ID of the room to join
            client_id: Optional client ID (generates one if not provided)
            
        Returns:
            The client ID
        """
        # Generate client ID if not provided
        if not client_id:
            client_id = str(uuid.uuid4())
        
        # Accept the WebSocket connection
        await websocket.accept()
        
        # Create room if it doesn't exist
        if room_id not in self.rooms:
            self.rooms[room_id] = set()
            logger.info(f"Created new WebRTC signaling room: {room_id}")
        
        # Add client to room
        self.rooms[room_id].add(websocket)
        
        # Track the connection
        self.active_connections[client_id] = {
            "websocket": websocket,
            "room_id": room_id,
            "connected_at": self._get_timestamp(),
            "last_activity": self._get_timestamp(),
        }
        
        # Store client info
        self.client_info[client_id] = {
            "client_id": client_id,
            "room_id": room_id,
            "connected_at": self._get_timestamp(),
        }
        
        # Notify everyone in the room about the new peer
        await self.broadcast_to_room(
            room_id,
            {
                "type": "peer_joined",
                "client_id": client_id,
                "room_id": room_id,
                "timestamp": self._get_timestamp(),
                "peers_count": len(self.rooms[room_id]),
            },
            exclude=websocket,
        )
        
        logger.info(f"Client {client_id} connected to WebRTC signaling room {room_id}")
        return client_id
    
    async def disconnect(self, websocket: WebSocket):
        """
        Disconnect a WebSocket client.
        
        Args:
            websocket: The WebSocket connection to disconnect
        """
        # Find the client ID for this WebSocket
        client_id = self._get_client_id_for_websocket(websocket)
        if not client_id:
            logger.warning("Attempted to disconnect unknown WebSocket")
            return
        
        # Get the room ID for this client
        room_id = self.active_connections[client_id]["room_id"]
        
        # Remove from room
        if room_id in self.rooms and websocket in self.rooms[room_id]:
            self.rooms[room_id].remove(websocket)
            
            # Remove room if empty
            if not self.rooms[room_id]:
                del self.rooms[room_id]
                logger.info(f"Removed empty WebRTC signaling room: {room_id}")
        
        # Remove from active connections
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        
        # Notify others in the room about the peer leaving
        if room_id in self.rooms:
            await self.broadcast_to_room(
                room_id,
                {
                    "type": "peer_left",
                    "client_id": client_id,
                    "room_id": room_id,
                    "timestamp": self._get_timestamp(),
                    "peers_count": len(self.rooms.get(room_id, set())),
                },
            )
        
        logger.info(f"Client {client_id} disconnected from WebRTC signaling room {room_id}")
    
    async def handle_signaling_message(self, websocket: WebSocket, message: Dict[str, Any]):
        """
        Handle a signaling message from a client.
        
        Args:
            websocket: The WebSocket connection
            message: The signaling message
        """
        # Get the client ID for this WebSocket
        client_id = self._get_client_id_for_websocket(websocket)
        if not client_id:
            logger.warning("Received message from unknown WebSocket")
            await websocket.send_json({
                "type": "error",
                "error": "Unknown client",
                "message": "Your connection is not registered",
            })
            return
        
        # Update last activity
        self.active_connections[client_id]["last_activity"] = self._get_timestamp()
        
        # Process message based on type
        message_type = message.get("type", "unknown")
        
        if message_type == "offer":
            # Handle WebRTC offer
            await self._handle_offer(client_id, message)
        elif message_type == "answer":
            # Handle WebRTC answer
            await self._handle_answer(client_id, message)
        elif message_type == "ice_candidate":
            # Handle ICE candidate
            await self._handle_ice_candidate(client_id, message)
        elif message_type == "get_peers":
            # Handle peer list request
            await self._handle_get_peers(client_id, websocket)
        else:
            # Unknown message type
            logger.warning(f"Received unknown message type from client {client_id}: {message_type}")
            await websocket.send_json({
                "type": "error",
                "error": "Unknown message type",
                "message": f"Message type '{message_type}' is not supported",
            })
    
    async def _handle_offer(self, client_id: str, message: Dict[str, Any]):
        """
        Handle a WebRTC offer.
        
        Args:
            client_id: The client ID
            message: The offer message
        """
        # Get the target peer ID
        target_id = message.get("target_id")
        if not target_id:
            logger.warning(f"Received offer from {client_id} without target_id")
            return
        
        # Check if target is connected
        if target_id not in self.active_connections:
            logger.warning(f"Target {target_id} for offer from {client_id} is not connected")
            await self._send_to_client(client_id, {
                "type": "error",
                "error": "Target not found",
                "message": f"Peer {target_id} is not connected",
                "target_id": target_id,
            })
            return
        
        # Forward the offer to the target
        offer_message = {
            "type": "offer",
            "sdp": message.get("sdp"),
            "sender_id": client_id,
            "timestamp": self._get_timestamp(),
        }
        
        await self._send_to_client(target_id, offer_message)
        logger.debug(f"Forwarded offer from {client_id} to {target_id}")
    
    async def _handle_answer(self, client_id: str, message: Dict[str, Any]):
        """
        Handle a WebRTC answer.
        
        Args:
            client_id: The client ID
            message: The answer message
        """
        # Get the target peer ID
        target_id = message.get("target_id")
        if not target_id:
            logger.warning(f"Received answer from {client_id} without target_id")
            return
        
        # Check if target is connected
        if target_id not in self.active_connections:
            logger.warning(f"Target {target_id} for answer from {client_id} is not connected")
            await self._send_to_client(client_id, {
                "type": "error",
                "error": "Target not found",
                "message": f"Peer {target_id} is not connected",
                "target_id": target_id,
            })
            return
        
        # Forward the answer to the target
        answer_message = {
            "type": "answer",
            "sdp": message.get("sdp"),
            "sender_id": client_id,
            "timestamp": self._get_timestamp(),
        }
        
        await self._send_to_client(target_id, answer_message)
        logger.debug(f"Forwarded answer from {client_id} to {target_id}")
    
    async def _handle_ice_candidate(self, client_id: str, message: Dict[str, Any]):
        """
        Handle an ICE candidate.
        
        Args:
            client_id: The client ID
            message: The ICE candidate message
        """
        # Get the target peer ID
        target_id = message.get("target_id")
        if not target_id:
            logger.warning(f"Received ICE candidate from {client_id} without target_id")
            return
        
        # Check if target is connected
        if target_id not in self.active_connections:
            logger.warning(f"Target {target_id} for ICE candidate from {client_id} is not connected")
            await self._send_to_client(client_id, {
                "type": "error",
                "error": "Target not found",
                "message": f"Peer {target_id} is not connected",
                "target_id": target_id,
            })
            return
        
        # Forward the ICE candidate to the target
        candidate_message = {
            "type": "ice_candidate",
            "candidate": message.get("candidate"),
            "sender_id": client_id,
            "timestamp": self._get_timestamp(),
        }
        
        await self._send_to_client(target_id, candidate_message)
        logger.debug(f"Forwarded ICE candidate from {client_id} to {target_id}")
    
    async def _handle_get_peers(self, client_id: str, websocket: WebSocket):
        """
        Handle a request for peer list.
        
        Args:
            client_id: The client ID
            websocket: The WebSocket connection
        """
        # Get the room ID for this client
        room_id = self.active_connections[client_id]["room_id"]
        
        # Get list of peers in the room excluding the requester
        peers = []
        for peer_id, info in self.active_connections.items():
            if peer_id != client_id and info["room_id"] == room_id:
                peers.append({
                    "client_id": peer_id,
                    "connected_at": info["connected_at"],
                })
        
        # Send the peer list
        await websocket.send_json({
            "type": "peers_list",
            "peers": peers,
            "room_id": room_id,
            "count": len(peers),
            "timestamp": self._get_timestamp(),
        })
        
        logger.debug(f"Sent peer list to {client_id} in room {room_id}: {len(peers)} peers")
    
    async def broadcast_to_room(self, room_id: str, message: Dict[str, Any], exclude: Optional[WebSocket] = None):
        """
        Broadcast a message to all clients in a room.
        
        Args:
            room_id: The room ID
            message: The message to broadcast
            exclude: Optional WebSocket to exclude from broadcast
        """
        if room_id not in self.rooms:
            logger.warning(f"Attempted to broadcast to non-existent room: {room_id}")
            return
        
        # Send to all clients in the room except the excluded one
        for websocket in self.rooms[room_id]:
            if websocket != exclude:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to client in room {room_id}: {e}")
    
    async def _send_to_client(self, client_id: str, message: Dict[str, Any]):
        """
        Send a message to a specific client.
        
        Args:
            client_id: The client ID
            message: The message to send
        """
        if client_id not in self.active_connections:
            logger.warning(f"Attempted to send message to disconnected client: {client_id}")
            return
        
        try:
            await self.active_connections[client_id]["websocket"].send_json(message)
        except Exception as e:
            logger.error(f"Error sending message to client {client_id}: {e}")
    
    def _get_client_id_for_websocket(self, websocket: WebSocket) -> Optional[str]:
        """
        Get the client ID for a WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            
        Returns:
            The client ID or None if not found
        """
        for client_id, info in self.active_connections.items():
            if info["websocket"] == websocket:
                return client_id
        return None
    
    def _get_timestamp(self) -> int:
        """
        Get the current timestamp in milliseconds.
        
        Returns:
            The current timestamp
        """
        import time
        return int(time.time() * 1000)
    
    def get_room_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the rooms and connections.
        
        Returns:
            Dictionary with room statistics
        """
        return {
            "room_count": len(self.rooms),
            "client_count": len(self.active_connections),
            "rooms": {
                room_id: len(clients)
                for room_id, clients in self.rooms.items()
            }
        }

# Global instance of the WebRTC signaling manager
_signaling_manager = None

def get_signaling_manager() -> WebRTCSignalingManager:
    """
    Get or create the WebRTC signaling manager.
    
    Returns:
        The WebRTC signaling manager
    """
    global _signaling_manager
    if _signaling_manager is None:
        _signaling_manager = WebRTCSignalingManager()
    return _signaling_manager

# Router creation function
def create_webrtc_router(api_prefix: str) -> APIRouter:
    """
    Create a FastAPI router for WebRTC endpoints.
    
    Args:
        api_prefix: The API prefix to use for the router
        
    Returns:
        The created router
    """
    router = APIRouter(prefix=f"{api_prefix}/webrtc")
    signaling_manager = get_signaling_manager()
    
    # --- Status endpoint ---
    @router.get("/status", summary="WebRTC Status")
    async def webrtc_status():
        """Get status of WebRTC functionality."""
        deps = check_webrtc_dependencies()
        
        # Add room statistics if available
        stats = {}
        if signaling_manager:
            stats = signaling_manager.get_room_stats()
        
        return {
            "success": WEBRTC_AVAILABLE,
            "available": WEBRTC_AVAILABLE,
            "dependencies": deps,
            "features": {
                "signaling": True,
                "video_streaming": HAVE_CV2 and HAVE_NUMPY,
                "data_channels": True,
                "peer_to_peer": True,
            },
            "stats": stats
        }
    
    # --- Room list endpoint ---
    @router.get("/rooms", summary="List WebRTC Rooms")
    async def list_rooms():
        """List all active WebRTC signaling rooms."""
        if not signaling_manager:
            if mcp_error_handling:
                return mcp_error_handling.create_error_response(
                    code="EXTENSION_NOT_AVAILABLE",
                    message_override="WebRTC signaling manager not available",
                    doc_category="webrtc"
                )
            return {"success": False, "error": "WebRTC signaling manager not available"}
        
        stats = signaling_manager.get_room_stats()
        rooms = [
            {
                "id": room_id,
                "clients": count,
            }
            for room_id, count in stats["rooms"].items()
        ]
        
        return {
            "success": True,
            "count": len(rooms),
            "rooms": rooms
        }
    
    # --- WebRTC signaling endpoint ---
    @router.websocket("/signal/{room_id}")
    async def webrtc_signaling(websocket: WebSocket, room_id: str, client_id: Optional[str] = None):
        """
        WebRTC signaling endpoint for peer connection establishment.
        
        This WebSocket endpoint allows clients to:
        - Connect to a signaling room
        - Exchange WebRTC connection offers/answers
        - Share ICE candidates
        - Discover other peers in the room
        
        The signaling server facilitates WebRTC peer-to-peer connections
        but does not access the actual data exchanged between peers.
        """
        if not WEBRTC_AVAILABLE:
            await websocket.close(code=1003, reason="WebRTC not available on server")
            return
        
        try:
            # Connect to the signaling room
            client_id = await signaling_manager.connect(websocket, room_id, client_id)
            
            # Send welcome message
            await websocket.send_json({
                "type": "welcome",
                "client_id": client_id,
                "room_id": room_id,
                "timestamp": signaling_manager._get_timestamp(),
            })
            
            # Message handling loop
            while True:
                # Receive message
                message = await websocket.receive_json()
                await signaling_manager.handle_signaling_message(websocket, message)
        
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected from room {room_id}")
        except Exception as e:
            logger.error(f"Error in WebRTC signaling for room {room_id}: {e}")
        finally:
            # Clean up when the WebSocket disconnects
            await signaling_manager.disconnect(websocket)
    
    return router

def create_webrtc_extension_router(api_prefix: str) -> Optional[APIRouter]:
    """
    Create a FastAPI router for WebRTC extension endpoints.
    
    Args:
        api_prefix: The API prefix to use for the router
        
    Returns:
        The created router or None if an error occurred
    """
    logger.info("Creating WebRTC extension router")
    
    if not HAVE_WEBRTC:
        logger.warning("WebRTC not available, extension will be limited")
    
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
    # Add WebRTC as a component
    storage_backends["webrtc"] = {
        "available": WEBRTC_AVAILABLE,
        "simulation": False,
        "features": {
            "signaling": True,
            "video_streaming": HAVE_CV2 and HAVE_NUMPY,
            "data_channels": True,
            "peer_to_peer": True,
        },
        "version": "1.0.0",
        "endpoints": [
            "/webrtc/status",
            "/webrtc/rooms",
            "/webrtc/signal/{room_id}",
        ],
        "missing_dependencies": [] if WEBRTC_AVAILABLE else [
            dep for dep, available in {
                "aiortc": HAVE_AIORTC,
                "opencv-python": HAVE_CV2,
                "numpy": HAVE_NUMPY,
            }.items() if not available
        ]
    }
    logger.info("Updated WebRTC status in storage backends")

def on_startup(app: Optional[FastAPI] = None) -> None:
    """
    Initialize the WebRTC extension on server startup.
    
    Args:
        app: The FastAPI application
    """
    logger.info("Initializing WebRTC extension")
    
    # Initialize signaling manager
    get_signaling_manager()

def on_shutdown(app: Optional[FastAPI] = None) -> None:
    """
    Clean up the WebRTC extension on server shutdown.
    
    Args:
        app: The FastAPI application
    """
    logger.info("Shutting down WebRTC extension")
    
    # Clean up signaling manager
    global _signaling_manager
    _signaling_manager = None