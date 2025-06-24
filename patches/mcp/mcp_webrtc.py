"""
WebRTC integration for MCP server.

This module provides WebRTC signaling server functionality to facilitate
peer-to-peer connections between clients, enabling direct data exchange
without the need for server-side proxying.
"""

import os
import json
import time
import uuid
import logging
import asyncio
from typing import Dict, Any, List, Set, Optional
from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger(__name__)

# Check for WebSocket module which we depend on
try:
    from mcp_websocket import get_websocket_service
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    logger.error("WebSocket module not available. WebRTC requires WebSocket support.")

# Models for WebRTC signaling
class RTCSessionDescription(BaseModel):
    """WebRTC Session Description Protocol message."""
    type: str  # "offer" or "answer"
    sdp: str

class RTCIceCandidate(BaseModel):
    """WebRTC ICE candidate."""
    candidate: str
    sdpMLineIndex: int
    sdpMid: str

class PeerInfo(BaseModel):
    """Information about a WebRTC peer."""
    peer_id: str
    room_id: str
    joined_at: float
    metadata: Optional[Dict[str, Any]] = None

# WebRTC signaling server
class WebRTCSignalingServer:
    """
    WebRTC signaling server.

    Provides a signaling mechanism for WebRTC peers to establish
    direct peer-to-peer connections.
    """

    def __init__(self):
        """Initialize the WebRTC signaling server."""
        # Rooms with connected peers (room_id -> set of peer_ids)
        self.rooms: Dict[str, Set[str]] = {}

        # Peer information (peer_id -> PeerInfo)
        self.peers: Dict[str, PeerInfo] = {}

        # Room metadata (room_id -> dict)
        self.room_metadata: Dict[str, Dict[str, Any]] = {}

        # Stats
        self.connections_count = 0
        self.rooms_count = 0
        self.messages_count = 0
        self.start_time = time.time()

    def create_room(self, room_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new room or get an existing one.

        Args:
            room_id: Optional room ID (generated if not provided)
            metadata: Optional room metadata

        Returns:
            The room ID
        """
        # Generate room ID if not provided
        if room_id is None:
            room_id = str(uuid.uuid4())

        # Create the room if it doesn't exist
        if room_id not in self.rooms:
            self.rooms[room_id] = set()
            self.room_metadata[room_id] = metadata or {}
            self.rooms_count += 1
        elif metadata:
            # Update metadata if provided
            self.room_metadata[room_id].update(metadata)

        return room_id

    def join_room(self, room_id: str, peer_id: str, metadata: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Add a peer to a room.

        Args:
            room_id: The room ID
            peer_id: The peer ID
            metadata: Optional peer metadata

        Returns:
            List of existing peers in the room
        """
        # Create the room if it doesn't exist
        self.create_room(room_id)

        # Get existing peers before adding the new one
        existing_peers = list(self.rooms[room_id])

        # Add the peer to the room
        self.rooms[room_id].add(peer_id)

        # Store peer information
        self.peers[peer_id] = PeerInfo(
            peer_id=peer_id,
            room_id=room_id,
            joined_at=time.time(),
            metadata=metadata or {}
        )

        self.connections_count += 1
        logger.info(f"Peer {peer_id} joined room {room_id}")

        return existing_peers

    def leave_room(self, peer_id: str) -> Optional[str]:
        """
        Remove a peer from its room.

        Args:
            peer_id: The peer ID

        Returns:
            The room ID the peer was in, or None if not found
        """
        # Check if the peer exists
        if peer_id not in self.peers:
            return None

        # Get the room
        room_id = self.peers[peer_id].room_id

        # Remove the peer from the room
        if room_id in self.rooms:
            self.rooms[room_id].discard(peer_id)

            # Clean up empty rooms
            if not self.rooms[room_id]:
                del self.rooms[room_id]
                del self.room_metadata[room_id]

        # Remove peer information
        del self.peers[peer_id]

        logger.info(f"Peer {peer_id} left room {room_id}")
        return room_id

    def get_peers_in_room(self, room_id: str) -> List[PeerInfo]:
        """
        Get all peers in a room.

        Args:
            room_id: The room ID

        Returns:
            List of peer information
        """
        if room_id not in self.rooms:
            return []

        return [
            self.peers[peer_id]
            for peer_id in self.rooms[room_id]
            if peer_id in self.peers
        ]

    def get_room_info(self, room_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a room.

        Args:
            room_id: The room ID

        Returns:
            Room information, or None if not found
        """
        if room_id not in self.rooms:
            return None

        return {
            "room_id": room_id,
            "peer_count": len(self.rooms[room_id]),
            "metadata": self.room_metadata.get(room_id, {}),
            "peers": [
                {
                    "peer_id": peer_id,
                    "joined_at": self.peers[peer_id].joined_at if peer_id in self.peers else None,
                    "metadata": self.peers[peer_id].metadata if peer_id in self.peers else {}
                }
                for peer_id in self.rooms[room_id]
            ]
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Get signaling server statistics.

        Returns:
            Dictionary with server stats
        """
        uptime = time.time() - self.start_time

        return {
            "active_rooms": len(self.rooms),
            "active_peers": len(self.peers),
            "total_connections": self.connections_count,
            "total_rooms": self.rooms_count,
            "messages_count": self.messages_count,
            "uptime": uptime,
            "msgs_per_second": self.messages_count / uptime if uptime > 0 else 0
        }

    async def handle_signaling(
        self,
        websocket: WebSocket,
        room_id: str,
        peer_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Handle WebRTC signaling for a peer.

        Args:
            websocket: The WebSocket connection
            room_id: The room ID to join
            peer_id: Optional peer ID (generated if not provided)
            metadata: Optional peer metadata
        """
        # Generate peer ID if not provided
        if peer_id is None:
            peer_id = str(uuid.uuid4())

        # Accept WebSocket connection
        await websocket.accept()

        try:
            # Join the room
            existing_peers = self.join_room(room_id, peer_id, metadata)

            # Send welcome message with peer ID and room information
            await websocket.send_json({
                "type": "welcome",
                "peer_id": peer_id,
                "room_id": room_id,
                "peers": [
                    {
                        "peer_id": existing_peer,
                        "metadata": self.peers[existing_peer].metadata if existing_peer in self.peers else {}
                    }
                    for existing_peer in existing_peers
                ],
                "timestamp": time.time()
            })

            # Notify other peers about the new peer
            if WEBSOCKET_AVAILABLE:
                websocket_service = get_websocket_service()
                await websocket_service.manager.broadcast(
                    {
                        "type": "peer_joined",
                        "peer_id": peer_id,
                        "room_id": room_id,
                        "metadata": metadata or {},
                        "timestamp": time.time()
                    },
                    f"webrtc:room:{room_id}"
                )

            # Handle messages
            while True:
                try:
                    # Receive message
                    message = await websocket.receive_text()
                    data = json.loads(message)
                    self.messages_count += 1

                    # Process message based on type
                    if "type" in data:
                        # Handle offer message
                        if data["type"] == "offer" and "target" in data:
                            target_peer_id = data["target"]
                            # Forward the offer to the target peer
                            await self._forward_message(room_id, peer_id, target_peer_id, data)

                        # Handle answer message
                        elif data["type"] == "answer" and "target" in data:
                            target_peer_id = data["target"]
                            # Forward the answer to the target peer
                            await self._forward_message(room_id, peer_id, target_peer_id, data)

                        # Handle ICE candidate message
                        elif data["type"] == "candidate" and "target" in data:
                            target_peer_id = data["target"]
                            # Forward the ICE candidate to the target peer
                            await self._forward_message(room_id, peer_id, target_peer_id, data)

                        # Handle room message (broadcast to all peers in the room)
                        elif data["type"] == "room_message":
                            # Broadcast to all peers in the room via WebSocket service
                            if WEBSOCKET_AVAILABLE:
                                websocket_service = get_websocket_service()
                                await websocket_service.manager.broadcast(
                                    {
                                        "type": "room_message",
                                        "from": peer_id,
                                        "room_id": room_id,
                                        "data": data.get("data", {}),
                                        "timestamp": time.time()
                                    },
                                    f"webrtc:room:{room_id}"
                                )

                        # Handle direct message to a specific peer
                        elif data["type"] == "peer_message" and "target" in data:
                            target_peer_id = data["target"]
                            # Forward the message to the target peer
                            await self._forward_message(room_id, peer_id, target_peer_id, {
                                "type": "peer_message",
                                "from": peer_id,
                                "data": data.get("data", {}),
                                "timestamp": time.time()
                            })

                        # Handle ping message
                        elif data["type"] == "ping":
                            await websocket.send_json({
                                "type": "pong",
                                "timestamp": time.time()
                            })

                        # Handle unknown message type
                        else:
                            await websocket.send_json({
                                "type": "error",
                                "error": "Unknown message type",
                                "timestamp": time.time()
                            })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "error": "Message missing type field",
                            "timestamp": time.time()
                        })

                except WebSocketDisconnect:
                    break
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "error": "Invalid JSON message",
                        "timestamp": time.time()
                    })
                except Exception as e:
                    logger.error(f"Error handling WebRTC signaling message: {e}")
                    try:
                        await websocket.send_json({
                            "type": "error",
                            "error": f"Server error: {str(e)}",
                            "timestamp": time.time()
                        })
                    except:
                        break

        finally:
            # Leave the room
            room_id = self.leave_room(peer_id)

            # Notify other peers about the peer leaving
            if room_id and WEBSOCKET_AVAILABLE:
                websocket_service = get_websocket_service()
                await websocket_service.manager.broadcast(
                    {
                        "type": "peer_left",
                        "peer_id": peer_id,
                        "room_id": room_id,
                        "timestamp": time.time()
                    },
                    f"webrtc:room:{room_id}"
                )

    async def _forward_message(self, room_id: str, from_peer_id: str, to_peer_id: str, message: Dict[str, Any]) -> bool:
        """
        Forward a message from one peer to another.

        Args:
            room_id: The room ID
            from_peer_id: The sender's peer ID
            to_peer_id: The recipient's peer ID
            message: The message to forward

        Returns:
            True if the message was forwarded successfully
        """
        # Make sure both peers are in the same room
        if (
            room_id not in self.rooms or
            from_peer_id not in self.rooms[room_id] or
            to_peer_id not in self.rooms[room_id]
        ):
            return False

        # Add the sender information
        message["from"] = from_peer_id

        # Use WebSocket service to forward the message
        if WEBSOCKET_AVAILABLE:
            websocket_service = get_websocket_service()
            await websocket_service.manager.broadcast(
                message,
                f"webrtc:peer:{to_peer_id}"
            )
            return True

        return False


# Create global signaling server instance
signaling_server = WebRTCSignalingServer()

# Create FastAPI router for WebRTC endpoints
def create_webrtc_router(api_prefix: str) -> APIRouter:
    """
    Create a FastAPI router for WebRTC endpoints.

    Args:
        api_prefix: The API prefix for the endpoints

    Returns:
        FastAPI router
    """
    router = APIRouter(prefix=f"{api_prefix}/webrtc")

    @router.get("/status")
    async def webrtc_status():
        """Get WebRTC signaling server status."""
        return {
            "success": True,
            "status": "available",
            "stats": signaling_server.get_stats()
        }

    @router.get("/rooms")
    async def list_rooms():
        """List all active WebRTC rooms."""
        return {
            "success": True,
            "rooms": [
                {
                    "room_id": room_id,
                    "peer_count": len(peers),
                    "metadata": signaling_server.room_metadata.get(room_id, {})
                }
                for room_id, peers in signaling_server.rooms.items()
            ]
        }

    @router.get("/rooms/{room_id}")
    async def get_room(room_id: str):
        """Get details about a specific WebRTC room."""
        room_info = signaling_server.get_room_info(room_id)

        if room_info:
            return {
                "success": True,
                "room": room_info
            }
        else:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": f"Room {room_id} not found"
                }
            )

    @router.post("/rooms")
    async def create_room(metadata: Optional[Dict[str, Any]] = None):
        """Create a new WebRTC room."""
        room_id = signaling_server.create_room(metadata=metadata)

        return {
            "success": True,
            "room_id": room_id,
            "metadata": signaling_server.room_metadata.get(room_id, {}),
            "created_at": time.time()
        }

    @router.websocket("/signal/{room_id}")
    async def webrtc_signaling(websocket: WebSocket, room_id: str, peer_id: Optional[str] = None):
        """WebRTC signaling WebSocket endpoint."""
        await signaling_server.handle_signaling(websocket, room_id, peer_id)

    @router.websocket("/signal/{room_id}/{peer_id}")
    async def webrtc_signaling_with_peer_id(websocket: WebSocket, room_id: str, peer_id: str):
        """WebRTC signaling WebSocket endpoint with explicit peer ID."""
        await signaling_server.handle_signaling(websocket, room_id, peer_id)

    return router


# Function to get the WebRTC signaling server instance
def get_signaling_server() -> WebRTCSignalingServer:
    """
    Get the WebRTC signaling server instance.

    Returns:
        The WebRTC signaling server instance
    """
    return signaling_server
