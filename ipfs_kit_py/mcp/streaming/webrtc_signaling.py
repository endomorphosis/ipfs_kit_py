"""
WebRTC signaling implementation for MCP server.

This module implements the WebRTC signaling capabilities mentioned in the roadmap,
providing peer-to-peer connection establishment and room-based peer discovery.
"""

import os
import sys
import json
import time
import uuid
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Set, Any, Optional, Union, Callable

# Configure logger
logger = logging.getLogger(__name__)

@dataclass
class PeerConnection:
    """Information about a peer connection."""
    id: str
    room_id: str
    websocket: Any
    connected_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for client consumption."""
        return {
            "id": self.id,
            "room_id": self.room_id,
            "connected_at": self.connected_at,
            "metadata": self.metadata
        }

@dataclass
class Room:
    """WebRTC signaling room."""
    id: str
    peers: Dict[str, PeerConnection] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    
    def add_peer(self, peer: PeerConnection) -> bool:
        """
        Add a peer to the room.
        
        Args:
            peer: Peer connection to add
            
        Returns:
            True if peer was added successfully
        """
        if peer.id in self.peers:
            logger.warning(f"Peer {peer.id} already in room {self.id}")
            return False
        
        self.peers[peer.id] = peer
        return True
    
    def remove_peer(self, peer_id: str) -> bool:
        """
        Remove a peer from the room.
        
        Args:
            peer_id: ID of peer to remove
            
        Returns:
            True if peer was removed successfully
        """
        if peer_id not in self.peers:
            logger.warning(f"Peer {peer_id} not in room {self.id}")
            return False
        
        del self.peers[peer_id]
        return True
    
    def get_peer(self, peer_id: str) -> Optional[PeerConnection]:
        """
        Get a peer from the room.
        
        Args:
            peer_id: ID of peer to get
            
        Returns:
            Peer connection or None if not found
        """
        return self.peers.get(peer_id)
    
    def get_peer_ids(self) -> List[str]:
        """
        Get all peer IDs in the room.
        
        Returns:
            List of peer IDs
        """
        return list(self.peers.keys())
    
    def get_peers(self) -> List[Dict[str, Any]]:
        """
        Get all peers in the room for client consumption.
        
        Returns:
            List of peer dictionaries
        """
        return [peer.to_dict() for peer in self.peers.values()]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for client consumption."""
        return {
            "id": self.id,
            "peers": self.get_peers(),
            "created_at": self.created_at,
            "peer_count": len(self.peers)
        }


class SignalingServer:
    """
    WebRTC signaling server implementation.
    
    This class implements the WebRTC signaling capabilities mentioned
    in the roadmap, providing peer-to-peer connection establishment.
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton implementation."""
        if cls._instance is None:
            cls._instance = super(SignalingServer, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the signaling server."""
        # Skip initialization if already initialized
        if getattr(self, "_initialized", False):
            return
        
        self._rooms: Dict[str, Room] = {}
        self._initialized = True
        
        logger.info("WebRTC signaling server initialized")
    
    async def create_room(self, room_id: Optional[str] = None) -> Room:
        """
        Create a new room.
        
        Args:
            room_id: Optional room ID (generated if not provided)
            
        Returns:
            Created room
        """
        # Generate room ID if not provided
        if room_id is None:
            room_id = str(uuid.uuid4())
        elif room_id in self._rooms:
            # If room already exists, return it
            return self._rooms[room_id]
        
        # Create room
        room = Room(id=room_id)
        self._rooms[room_id] = room
        
        logger.info(f"Room {room_id} created")
        
        return room
    
    async def get_room(self, room_id: str) -> Optional[Room]:
        """
        Get a room by ID.
        
        Args:
            room_id: Room ID
            
        Returns:
            Room or None if not found
        """
        return self._rooms.get(room_id)
    
    async def delete_room(self, room_id: str) -> bool:
        """
        Delete a room.
        
        Args:
            room_id: Room ID
            
        Returns:
            True if room was deleted successfully
        """
        if room_id not in self._rooms:
            logger.warning(f"Room {room_id} not found for deletion")
            return False
        
        # Remove room
        del self._rooms[room_id]
        
        logger.info(f"Room {room_id} deleted")
        
        return True
    
    async def join_room(self, room_id: str, websocket: Any, 
                       peer_id: Optional[str] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> PeerConnection:
        """
        Join a room.
        
        Args:
            room_id: Room ID
            websocket: WebSocket connection
            peer_id: Optional peer ID (generated if not provided)
            metadata: Optional peer metadata
            
        Returns:
            Peer connection
        """
        # Get or create room
        room = await self.get_room(room_id)
        if room is None:
            room = await self.create_room(room_id)
        
        # Generate peer ID if not provided
        if peer_id is None:
            peer_id = str(uuid.uuid4())
        
        # Create peer connection
        peer = PeerConnection(
            id=peer_id,
            room_id=room_id,
            websocket=websocket,
            metadata=metadata or {}
        )
        
        # Add peer to room
        room.add_peer(peer)
        
        logger.info(f"Peer {peer_id} joined room {room_id}")
        
        # Notify other peers in the room
        await self.broadcast_to_room(
            room_id=room_id,
            message={
                "type": "peer_joined",
                "peer": peer.to_dict()
            },
            exclude_peer_id=peer_id
        )
        
        return peer
    
    async def leave_room(self, room_id: str, peer_id: str) -> bool:
        """
        Leave a room.
        
        Args:
            room_id: Room ID
            peer_id: Peer ID
            
        Returns:
            True if peer left the room successfully
        """
        # Get room
        room = await self.get_room(room_id)
        if room is None:
            logger.warning(f"Room {room_id} not found for peer {peer_id} to leave")
            return False
        
        # Remove peer from room
        if not room.remove_peer(peer_id):
            logger.warning(f"Peer {peer_id} not found in room {room_id}")
            return False
        
        logger.info(f"Peer {peer_id} left room {room_id}")
        
        # Notify other peers in the room
        await self.broadcast_to_room(
            room_id=room_id,
            message={
                "type": "peer_left",
                "peer_id": peer_id
            }
        )
        
        # Delete room if empty
        if len(room.peers) == 0:
            await self.delete_room(room_id)
            logger.info(f"Room {room_id} deleted (empty)")
        
        return True
    
    async def send_to_peer(self, room_id: str, peer_id: str, 
                          message: Dict[str, Any]) -> bool:
        """
        Send a message to a specific peer.
        
        Args:
            room_id: Room ID
            peer_id: Peer ID
            message: Message to send
            
        Returns:
            True if message was sent successfully
        """
        # Get room
        room = await self.get_room(room_id)
        if room is None:
            logger.warning(f"Room {room_id} not found for sending to peer {peer_id}")
            return False
        
        # Get peer
        peer = room.get_peer(peer_id)
        if peer is None:
            logger.warning(f"Peer {peer_id} not found in room {room_id}")
            return False
        
        try:
            # Send message
            await peer.websocket.send_text(json.dumps(message))
            
            # Update last activity
            peer.last_activity = time.time()
            
            return True
        except Exception as e:
            logger.error(f"Error sending message to peer {peer_id} in room {room_id}: {e}")
            return False
    
    async def broadcast_to_room(self, room_id: str, message: Dict[str, Any],
                              exclude_peer_id: Optional[str] = None) -> int:
        """
        Broadcast a message to all peers in a room.
        
        Args:
            room_id: Room ID
            message: Message to broadcast
            exclude_peer_id: Optional peer ID to exclude
            
        Returns:
            Number of peers the message was sent to
        """
        # Get room
        room = await self.get_room(room_id)
        if room is None:
            logger.warning(f"Room {room_id} not found for broadcasting")
            return 0
        
        # Broadcast to all peers except excluded
        sent_count = 0
        for peer_id, peer in room.peers.items():
            if exclude_peer_id is not None and peer_id == exclude_peer_id:
                continue
            
            try:
                await peer.websocket.send_text(json.dumps(message))
                peer.last_activity = time.time()
                sent_count += 1
            except Exception as e:
                logger.error(f"Error broadcasting to peer {peer_id} in room {room_id}: {e}")
        
        return sent_count
    
    async def relay_message(self, room_id: str, from_peer_id: str, 
                           to_peer_id: str, message: Dict[str, Any]) -> bool:
        """
        Relay a message from one peer to another.
        
        Args:
            room_id: Room ID
            from_peer_id: Source peer ID
            to_peer_id: Destination peer ID
            message: Message to relay
            
        Returns:
            True if message was relayed successfully
        """
        # Add sender ID to message
        relay_message = message.copy()
        relay_message["from"] = from_peer_id
        
        # Send to destination peer
        return await self.send_to_peer(room_id, to_peer_id, relay_message)
    
    async def handle_signal(self, room_id: str, from_peer_id: str,
                           message: Dict[str, Any]) -> bool:
        """
        Handle a WebRTC signaling message.
        
        Args:
            room_id: Room ID
            from_peer_id: Source peer ID
            message: Signaling message
            
        Returns:
            True if message was handled successfully
        """
        # Get message type
        message_type = message.get("type")
        
        if message_type == "offer" or message_type == "answer" or message_type == "candidate":
            # Get destination peer ID
            to_peer_id = message.get("to")
            if not to_peer_id:
                logger.warning(f"Missing destination peer ID in {message_type} message")
                return False
            
            # Relay message to destination peer
            return await self.relay_message(room_id, from_peer_id, to_peer_id, message)
        
        elif message_type == "peers":
            # Get room
            room = await self.get_room(room_id)
            if room is None:
                logger.warning(f"Room {room_id} not found for peers request")
                return False
            
            # Get room peers
            peers = room.get_peers()
            
            # Send peers list to requesting peer
            return await self.send_to_peer(
                room_id=room_id,
                peer_id=from_peer_id,
                message={
                    "type": "peers",
                    "peers": [p for p in peers if p["id"] != from_peer_id]
                }
            )
        
        else:
            logger.warning(f"Unknown signal message type: {message_type}")
            return False
    
    def get_room_info(self, room_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a room.
        
        Args:
            room_id: Room ID
            
        Returns:
            Dictionary with room information or None if not found
        """
        room = self._rooms.get(room_id)
        if room is None:
            return None
        
        return room.to_dict()
    
    def list_rooms(self) -> List[Dict[str, Any]]:
        """
        List all rooms.
        
        Returns:
            List of room information dictionaries
        """
        return [room.to_dict() for room in self._rooms.values()]
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get signaling server statistics.
        
        Returns:
            Dictionary with statistics
        """
        total_peers = sum(len(room.peers) for room in self._rooms.values())
        
        return {
            "room_count": len(self._rooms),
            "peer_count": total_peers,
            "rooms": {room_id: len(room.peers) for room_id, room in self._rooms.items()}
        }
    
    async def cleanup_inactive_rooms(self, inactive_timeout: int = 3600) -> int:
        """
        Clean up inactive rooms.
        
        Args:
            inactive_timeout: Timeout in seconds for inactivity
            
        Returns:
            Number of rooms cleaned up
        """
        now = time.time()
        inactive_room_ids = []
        
        # Find inactive rooms
        for room_id, room in self._rooms.items():
            # Room is inactive if all peers are inactive or if it's empty
            if len(room.peers) == 0:
                inactive_room_ids.append(room_id)
            else:
                # Check if all peers are inactive
                all_inactive = True
                for peer in room.peers.values():
                    if now - peer.last_activity <= inactive_timeout:
                        all_inactive = False
                        break
                
                if all_inactive:
                    inactive_room_ids.append(room_id)
        
        # Delete inactive rooms
        for room_id in inactive_room_ids:
            await self.delete_room(room_id)
        
        return len(inactive_room_ids)