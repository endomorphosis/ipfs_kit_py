"""
MCP WebRTC Module for peer-to-peer data transfer.

This module provides WebRTC signaling capabilities for the MCP server, enabling:
1. Peer-to-peer connection establishment
2. Room-based peer discovery
3. Direct data channel communication
4. Efficient binary data transfer
"""

import json
import time
import logging
import threading
import uuid
from enum import Enum
from typing import Dict, Any, List, Set, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field

# Configure logger
logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Types of WebRTC signaling messages."""
    JOIN = "join"
    LEAVE = "leave"
    OFFER = "offer"
    ANSWER = "answer"
    ICE_CANDIDATE = "ice_candidate"
    ROOM_INFO = "room_info"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


@dataclass
class Peer:
    """Information about a WebRTC peer."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    room_id: Optional[str] = None
    user_agent: Optional[str] = None
    remote_ip: Optional[str] = None
    joined_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()
    
    def to_dict(self, include_private: bool = False) -> Dict[str, Any]:
        """
        Convert to dictionary.
        
        Args:
            include_private: Whether to include private information
            
        Returns:
            Dictionary representation
        """
        result = {
            "id": self.id,
            "room_id": self.room_id,
            "joined_at": self.joined_at.isoformat(),
            "metadata": self.metadata
        }
        
        if include_private:
            result.update({
                "user_agent": self.user_agent,
                "remote_ip": self.remote_ip,
                "last_activity": self.last_activity.isoformat()
            })
        
        return result


@dataclass
class Room:
    """Information about a WebRTC signaling room."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    peers: Dict[str, Peer] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    password: Optional[str] = None
    max_peers: int = 20
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()
    
    def add_peer(self, peer: Peer) -> None:
        """
        Add a peer to the room.
        
        Args:
            peer: Peer to add
        """
        peer.room_id = self.id
        self.peers[peer.id] = peer
        self.update_activity()
    
    def remove_peer(self, peer_id: str) -> None:
        """
        Remove a peer from the room.
        
        Args:
            peer_id: ID of peer to remove
        """
        if peer_id in self.peers:
            del self.peers[peer_id]
            self.update_activity()
    
    def get_peer_ids(self) -> List[str]:
        """
        Get list of peer IDs in the room.
        
        Returns:
            List of peer IDs
        """
        return list(self.peers.keys())
    
    def get_peers_info(self, exclude_peer_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get information about peers in the room.
        
        Args:
            exclude_peer_id: Optional peer ID to exclude
            
        Returns:
            List of peer information dictionaries
        """
        return [
            peer.to_dict() for peer_id, peer in self.peers.items()
            if peer_id != exclude_peer_id
        ]
    
    def is_full(self) -> bool:
        """
        Check if the room is full.
        
        Returns:
            True if room is at or above max capacity
        """
        return len(self.peers) >= self.max_peers
    
    def is_empty(self) -> bool:
        """
        Check if the room is empty.
        
        Returns:
            True if room has no peers
        """
        return len(self.peers) == 0
    
    def to_dict(self, include_peers: bool = False) -> Dict[str, Any]:
        """
        Convert to dictionary.
        
        Args:
            include_peers: Whether to include peer information
            
        Returns:
            Dictionary representation
        """
        result = {
            "id": self.id,
            "peer_count": len(self.peers),
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "metadata": self.metadata,
            "has_password": self.password is not None,
            "max_peers": self.max_peers
        }
        
        if include_peers:
            result["peers"] = [peer.to_dict() for peer in self.peers.values()]
        
        return result


@dataclass
class SignalMessage:
    """WebRTC signaling message."""
    type: SignalType
    data: Dict[str, Any] = field(default_factory=dict)
    sender_id: Optional[str] = None
    target_id: Optional[str] = None
    room_id: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type.value,
            "data": self.data,
            "sender_id": self.sender_id,
            "target_id": self.target_id,
            "room_id": self.room_id,
            "id": self.id,
            "timestamp": self.timestamp.isoformat()
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> Optional['SignalMessage']:
        """Create message from JSON string."""
        try:
            data = json.loads(json_str)
            msg_type = data.get("type")
            if not msg_type:
                return None
            
            try:
                signal_type = SignalType(msg_type)
            except ValueError:
                return None
            
            return cls(
                type=signal_type,
                data=data.get("data", {}),
                sender_id=data.get("sender_id"),
                target_id=data.get("target_id"),
                room_id=data.get("room_id"),
                id=data.get("id", str(uuid.uuid4())),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat()))
            )
        except Exception as e:
            logger.error(f"Error parsing signaling message: {e}")
            return None


class WebRTCSignalingServer:
    """WebRTC signaling server for peer-to-peer connections."""
    
    def __init__(self, message_sender: Optional[Callable[[str, str], None]] = None):
        """
        Initialize WebRTC signaling server.
        
        Args:
            message_sender: Optional function to send messages to peers
        """
        self.rooms: Dict[str, Room] = {}
        self.peers: Dict[str, Peer] = {}
        self.message_sender = message_sender
        
        # Message handlers
        self.message_handlers = {
            SignalType.JOIN: self._handle_join,
            SignalType.LEAVE: self._handle_leave,
            SignalType.OFFER: self._handle_offer,
            SignalType.ANSWER: self._handle_answer,
            SignalType.ICE_CANDIDATE: self._handle_ice_candidate,
            SignalType.PING: self._handle_ping
        }
        
        # Lock for thread safety
        self.lock = threading.RLock()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True
        )
        self.cleanup_thread.start()
    
    def register_peer(self, peer_id: Optional[str] = None, 
                     user_agent: Optional[str] = None,
                     remote_ip: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> Peer:
        """
        Register a new peer.
        
        Args:
            peer_id: Optional peer ID (generated if not provided)
            user_agent: Optional user agent string
            remote_ip: Optional remote IP address
            metadata: Optional peer metadata
            
        Returns:
            Registered peer
        """
        with self.lock:
            peer = Peer(
                id=peer_id or str(uuid.uuid4()),
                user_agent=user_agent,
                remote_ip=remote_ip,
                metadata=metadata or {}
            )
            
            self.peers[peer.id] = peer
            
            return peer
    
    def unregister_peer(self, peer_id: str) -> None:
        """
        Unregister a peer.
        
        Args:
            peer_id: Peer ID
        """
        with self.lock:
            if peer_id in self.peers:
                peer = self.peers[peer_id]
                
                # Remove from room if in one
                if peer.room_id and peer.room_id in self.rooms:
                    self.rooms[peer.room_id].remove_peer(peer_id)
                
                # Remove peer
                del self.peers[peer_id]
    
    def create_room(self, room_id: Optional[str] = None,
                   password: Optional[str] = None,
                   max_peers: int = 20,
                   metadata: Optional[Dict[str, Any]] = None) -> Room:
        """
        Create a new room.
        
        Args:
            room_id: Optional room ID (generated if not provided)
            password: Optional password for the room
            max_peers: Maximum number of peers allowed
            metadata: Optional room metadata
            
        Returns:
            Created room
        """
        with self.lock:
            room = Room(
                id=room_id or str(uuid.uuid4()),
                password=password,
                max_peers=max_peers,
                metadata=metadata or {}
            )
            
            self.rooms[room.id] = room
            
            return room
    
    def handle_message(self, peer_id: str, message_json: str) -> Dict[str, Any]:
        """
        Handle an incoming signaling message.
        
        Args:
            peer_id: Peer ID
            message_json: Message as JSON string
            
        Returns:
            Result dictionary
        """
        if peer_id not in self.peers:
            return {
                "success": False,
                "error": f"Peer {peer_id} not registered"
            }
        
        # Update peer activity
        self.peers[peer_id].update_activity()
        
        # Parse message
        message = SignalMessage.from_json(message_json)
        if not message:
            return {
                "success": False,
                "error": "Invalid message format"
            }
        
        # Set sender ID
        message.sender_id = peer_id
        
        # Handle message based on type
        handler = self.message_handlers.get(message.type)
        if handler:
            return handler(message)
        else:
            return {
                "success": False,
                "error": f"Unsupported message type: {message.type.value}"
            }
    
    def _handle_join(self, message: SignalMessage) -> Dict[str, Any]:
        """
        Handle join message.
        
        Args:
            message: Signaling message
            
        Returns:
            Result dictionary
        """
        room_id = message.data.get("room_id") or message.room_id
        if not room_id:
            return {
                "success": False,
                "error": "No room ID specified"
            }
        
        # Check if room exists, create if not
        with self.lock:
            if room_id not in self.rooms:
                create_if_missing = message.data.get("create_if_missing", True)
                if create_if_missing:
                    # Create room with optional parameters
                    password = message.data.get("password")
                    max_peers = message.data.get("max_peers", 20)
                    metadata = message.data.get("room_metadata", {})
                    
                    room = self.create_room(
                        room_id=room_id,
                        password=password,
                        max_peers=max_peers,
                        metadata=metadata
                    )
                else:
                    return {
                        "success": False,
                        "error": f"Room {room_id} does not exist"
                    }
            else:
                room = self.rooms[room_id]
            
            # Check room password
            if room.password and message.data.get("password") != room.password:
                return {
                    "success": False,
                    "error": "Invalid room password"
                }
            
            # Check if room is full
            if room.is_full():
                return {
                    "success": False,
                    "error": f"Room {room_id} is full"
                }
            
            # Get peer
            peer = self.peers[message.sender_id]
            
            # Check if peer is already in a room
            if peer.room_id:
                # Leave current room
                if peer.room_id in self.rooms:
                    old_room = self.rooms[peer.room_id]
                    old_room.remove_peer(peer.id)
                    
                    # Notify other peers in the old room
                    self._broadcast_leave(peer.id, old_room.id)
            
            # Join new room
            room.add_peer(peer)
            
            # Send room information to the joining peer
            room_info = SignalMessage(
                type=SignalType.ROOM_INFO,
                data={
                    "room": room.to_dict(),
                    "peers": room.get_peers_info(exclude_peer_id=peer.id)
                },
                sender_id="server",
                target_id=peer.id,
                room_id=room.id
            )
            
            if self.message_sender:
                self.message_sender(peer.id, room_info.to_json())
            
            # Notify other peers in the room
            self._broadcast_join(peer.id, room.id)
            
            return {
                "success": True,
                "room_id": room.id,
                "peer_count": len(room.peers),
                "peer_id": peer.id
            }
    
    def _handle_leave(self, message: SignalMessage) -> Dict[str, Any]:
        """
        Handle leave message.
        
        Args:
            message: Signaling message
            
        Returns:
            Result dictionary
        """
        peer_id = message.sender_id
        
        with self.lock:
            peer = self.peers.get(peer_id)
            if not peer:
                return {
                    "success": False,
                    "error": f"Peer {peer_id} not found"
                }
            
            room_id = peer.room_id
            if not room_id or room_id not in self.rooms:
                return {
                    "success": False,
                    "error": f"Peer {peer_id} is not in a room"
                }
            
            room = self.rooms[room_id]
            
            # Remove peer from room
            room.remove_peer(peer_id)
            peer.room_id = None
            
            # Notify other peers in the room
            self._broadcast_leave(peer_id, room_id)
            
            # Check if room is now empty
            if room.is_empty():
                # Remove room if auto-cleanup is enabled
                auto_cleanup = message.data.get("auto_cleanup", True)
                if auto_cleanup:
                    del self.rooms[room_id]
            
            return {
                "success": True,
                "room_id": room_id,
                "peer_id": peer_id
            }
    
    def _handle_offer(self, message: SignalMessage) -> Dict[str, Any]:
        """
        Handle offer message.
        
        Args:
            message: Signaling message
            
        Returns:
            Result dictionary
        """
        # Forward offer to target peer
        return self._forward_message(message)
    
    def _handle_answer(self, message: SignalMessage) -> Dict[str, Any]:
        """
        Handle answer message.
        
        Args:
            message: Signaling message
            
        Returns:
            Result dictionary
        """
        # Forward answer to target peer
        return self._forward_message(message)
    
    def _handle_ice_candidate(self, message: SignalMessage) -> Dict[str, Any]:
        """
        Handle ICE candidate message.
        
        Args:
            message: Signaling message
            
        Returns:
            Result dictionary
        """
        # Forward ICE candidate to target peer
        return self._forward_message(message)
    
    def _handle_ping(self, message: SignalMessage) -> Dict[str, Any]:
        """
        Handle ping message.
        
        Args:
            message: Signaling message
            
        Returns:
            Result dictionary
        """
        # Reply with pong
        pong = SignalMessage(
            type=SignalType.PONG,
            data={
                "timestamp": datetime.now().isoformat(),
                "echo": message.data.get("data")
            },
            sender_id="server",
            target_id=message.sender_id
        )
        
        if self.message_sender:
            self.message_sender(message.sender_id, pong.to_json())
        
        return {
            "success": True,
            "ping_received": True
        }
    
    def _forward_message(self, message: SignalMessage) -> Dict[str, Any]:
        """
        Forward a message to its target peer.
        
        Args:
            message: Signaling message
            
        Returns:
            Result dictionary
        """
        if not message.target_id:
            return {
                "success": False,
                "error": "No target ID specified"
            }
        
        # Check if target peer exists
        if message.target_id not in self.peers:
            return {
                "success": False,
                "error": f"Target peer {message.target_id} not found"
            }
        
        # Check if sender and target are in the same room
        sender = self.peers.get(message.sender_id)
        target = self.peers.get(message.target_id)
        
        if not sender or not sender.room_id:
            return {
                "success": False,
                "error": f"Sender {message.sender_id} is not in a room"
            }
        
        if not target or not target.room_id:
            return {
                "success": False,
                "error": f"Target {message.target_id} is not in a room"
            }
        
        if sender.room_id != target.room_id:
            return {
                "success": False,
                "error": "Sender and target are not in the same room"
            }
        
        # Forward the message
        if self.message_sender:
            self.message_sender(message.target_id, message.to_json())
        
        return {
            "success": True,
            "forwarded": True,
            "target_id": message.target_id
        }
    
    def _broadcast_join(self, peer_id: str, room_id: str) -> None:
        """
        Broadcast join event to all peers in a room.
        
        Args:
            peer_id: ID of joining peer
            room_id: Room ID
        """
        with self.lock:
            if room_id not in self.rooms:
                return
            
            room = self.rooms[room_id]
            
            # Create join message
            join_message = SignalMessage(
                type=SignalType.JOIN,
                data={
                    "peer": self.peers[peer_id].to_dict()
                },
                sender_id=peer_id,
                room_id=room_id
            )
            
            # Send to all peers in the room except the joiner
            for pid in room.get_peer_ids():
                if pid != peer_id and self.message_sender:
                    self.message_sender(pid, join_message.to_json())
    
    def _broadcast_leave(self, peer_id: str, room_id: str) -> None:
        """
        Broadcast leave event to all peers in a room.
        
        Args:
            peer_id: ID of leaving peer
            room_id: Room ID
        """
        with self.lock:
            if room_id not in self.rooms:
                return
            
            room = self.rooms[room_id]
            
            # Create leave message
            leave_message = SignalMessage(
                type=SignalType.LEAVE,
                data={
                    "peer_id": peer_id
                },
                sender_id=peer_id,
                room_id=room_id
            )
            
            # Send to all peers in the room except the leaver
            for pid in room.get_peer_ids():
                if pid != peer_id and self.message_sender:
                    self.message_sender(pid, leave_message.to_json())
    
    def _cleanup_loop(self) -> None:
        """Periodically clean up inactive peers and rooms."""
        while True:
            try:
                time.sleep(60)  # Check every minute
                
                now = datetime.now()
                inactive_peers = []
                inactive_rooms = []
                
                with self.lock:
                    # Check for inactive peers (inactive for 5 minutes)
                    for peer_id, peer in self.peers.items():
                        if (now - peer.last_activity).total_seconds() > 300:  # 5 minutes
                            inactive_peers.append(peer_id)
                    
                    # Check for inactive rooms (inactive for 10 minutes)
                    for room_id, room in self.rooms.items():
                        if (now - room.last_activity).total_seconds() > 600:  # 10 minutes
                            inactive_rooms.append(room_id)
                    
                    # Clean up inactive peers
                    for peer_id in inactive_peers:
                        if peer_id in self.peers:
                            peer = self.peers[peer_id]
                            
                            # Remove from room if in one
                            if peer.room_id and peer.room_id in self.rooms:
                                room = self.rooms[peer.room_id]
                                room.remove_peer(peer_id)
                                
                                # Notify other peers in the room
                                self._broadcast_leave(peer_id, peer.room_id)
                            
                            # Remove peer
                            del self.peers[peer_id]
                    
                    # Clean up inactive and empty rooms
                    for room_id in inactive_rooms:
                        if room_id in self.rooms:
                            del self.rooms[room_id]
            
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    def get_room_info(self, room_id: str, include_peers: bool = True) -> Dict[str, Any]:
        """
        Get information about a room.
        
        Args:
            room_id: Room ID
            include_peers: Whether to include peer information
            
        Returns:
            Room information dictionary
        """
        with self.lock:
            if room_id not in self.rooms:
                return {
                    "success": False,
                    "error": f"Room {room_id} not found"
                }
            
            room = self.rooms[room_id]
            
            return {
                "success": True,
                "room": room.to_dict(include_peers=include_peers)
            }
    
    def list_rooms(self, include_peers: bool = False) -> Dict[str, Any]:
        """
        List all rooms.
        
        Args:
            include_peers: Whether to include peer information
            
        Returns:
            List of room information dictionaries
        """
        with self.lock:
            rooms_info = [
                room.to_dict(include_peers=include_peers)
                for room in self.rooms.values()
            ]
            
            return {
                "success": True,
                "rooms": rooms_info,
                "count": len(rooms_info)
            }
    
    def get_peer_info(self, peer_id: str) -> Dict[str, Any]:
        """
        Get information about a peer.
        
        Args:
            peer_id: Peer ID
            
        Returns:
            Peer information dictionary
        """
        with self.lock:
            if peer_id not in self.peers:
                return {
                    "success": False,
                    "error": f"Peer {peer_id} not found"
                }
            
            peer = self.peers[peer_id]
            
            return {
                "success": True,
                "peer": peer.to_dict(include_private=True)
            }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get server status.
        
        Returns:
            Status information dictionary
        """
        with self.lock:
            return {
                "success": True,
                "peer_count": len(self.peers),
                "room_count": len(self.rooms),
                "rooms": [
                    {
                        "id": room.id,
                        "peer_count": len(room.peers),
                        "created_at": room.created_at.isoformat()
                    }
                    for room in self.rooms.values()
                ],
                "timestamp": datetime.now().isoformat()
            }
    
    def send_to_peer(self, peer_id: str, message_type: SignalType, 
                    data: Dict[str, Any]) -> bool:
        """
        Send a message to a specific peer.
        
        Args:
            peer_id: Peer ID
            message_type: Type of message
            data: Message data
            
        Returns:
            True if message was sent
        """
        if peer_id not in self.peers:
            return False
        
        message = SignalMessage(
            type=message_type,
            data=data,
            sender_id="server",
            target_id=peer_id
        )
        
        if self.message_sender:
            self.message_sender(peer_id, message.to_json())
            return True
        
        return False
    
    def broadcast_to_room(self, room_id: str, message_type: SignalType,
                         data: Dict[str, Any],
                         exclude_peer_id: Optional[str] = None) -> bool:
        """
        Broadcast a message to all peers in a room.
        
        Args:
            room_id: Room ID
            message_type: Type of message
            data: Message data
            exclude_peer_id: Optional peer ID to exclude
            
        Returns:
            True if message was broadcast
        """
        with self.lock:
            if room_id not in self.rooms:
                return False
            
            room = self.rooms[room_id]
            
            message = SignalMessage(
                type=message_type,
                data=data,
                sender_id="server",
                room_id=room_id
            )
            
            message_json = message.to_json()
            
            for peer_id in room.get_peer_ids():
                if peer_id != exclude_peer_id and self.message_sender:
                    self.message_sender(peer_id, message_json)
            
            return True


class WebRTCSignalingHandler:
    """Handler for WebRTC signaling in MCP server."""
    
    def __init__(self, backend_registry: Optional[Dict[str, Any]] = None):
        """
        Initialize WebRTC signaling handler.
        
        Args:
            backend_registry: Optional dictionary mapping backend names to instances
        """
        self.backend_registry = backend_registry or {}
        
        # Create signaling server
        self.signaling_server = WebRTCSignalingServer(
            message_sender=self._send_signal
        )
        
        # Active connections (would be managed by web framework)
        self.connections = {}
    
    def _send_signal(self, peer_id: str, message: str) -> None:
        """
        Send a signaling message to a peer.
        
        Args:
            peer_id: Peer ID
            message: Message as JSON string
        """
        # This would be implemented by the web framework
        # For now, just log the message
        logger.debug(f"Would send signal to peer {peer_id}: {message}")
        
        # If we had an actual client connection, we would do something like:
        # self.connections[peer_id].send(message)
    
    def register_peer(self, peer_id: Optional[str] = None,
                     user_agent: Optional[str] = None,
                     remote_ip: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Register a new peer.
        
        Args:
            peer_id: Optional peer ID (generated if not provided)
            user_agent: Optional user agent string
            remote_ip: Optional remote IP address
            metadata: Optional peer metadata
            
        Returns:
            Registration result
        """
        peer = self.signaling_server.register_peer(
            peer_id=peer_id,
            user_agent=user_agent,
            remote_ip=remote_ip,
            metadata=metadata
        )
        
        return {
            "success": True,
            "peer_id": peer.id,
            "joined_at": peer.joined_at.isoformat()
        }
    
    def unregister_peer(self, peer_id: str) -> Dict[str, Any]:
        """
        Unregister a peer.
        
        Args:
            peer_id: Peer ID
            
        Returns:
            Unregistration result
        """
        self.signaling_server.unregister_peer(peer_id)
        
        return {
            "success": True,
            "peer_id": peer_id,
            "message": f"Peer {peer_id} unregistered"
        }
    
    def create_room(self, room_id: Optional[str] = None,
                   password: Optional[str] = None,
                   max_peers: int = 20,
                   metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new room.
        
        Args:
            room_id: Optional room ID (generated if not provided)
            password: Optional password for the room
            max_peers: Maximum number of peers allowed
            metadata: Optional room metadata
            
        Returns:
            Room creation result
        """
        room = self.signaling_server.create_room(
            room_id=room_id,
            password=password,
            max_peers=max_peers,
            metadata=metadata
        )
        
        return {
            "success": True,
            "room_id": room.id,
            "created_at": room.created_at.isoformat(),
            "has_password": room.password is not None,
            "max_peers": room.max_peers
        }
    
    def join_room(self, peer_id: str, room_id: str,
                 password: Optional[str] = None,
                 create_if_missing: bool = True) -> Dict[str, Any]:
        """
        Join a room.
        
        Args:
            peer_id: Peer ID
            room_id: Room ID
            password: Optional room password
            create_if_missing: Whether to create the room if it doesn't exist
            
        Returns:
            Join result
        """
        # Create join message
        join_message = SignalMessage(
            type=SignalType.JOIN,
            data={
                "room_id": room_id,
                "password": password,
                "create_if_missing": create_if_missing
            },
            sender_id=peer_id
        )
        
        # Handle message
        return self.signaling_server.handle_message(peer_id, join_message.to_json())
    
    def leave_room(self, peer_id: str) -> Dict[str, Any]:
        """
        Leave current room.
        
        Args:
            peer_id: Peer ID
            
        Returns:
            Leave result
        """
        # Create leave message
        leave_message = SignalMessage(
            type=SignalType.LEAVE,
            sender_id=peer_id
        )
        
        # Handle message
        return self.signaling_server.handle_message(peer_id, leave_message.to_json())
    
    def handle_signal(self, peer_id: str, message: str) -> Dict[str, Any]:
        """
        Handle a signaling message.
        
        Args:
            peer_id: Peer ID
            message: Message as JSON string
            
        Returns:
            Handling result
        """
        return self.signaling_server.handle_message(peer_id, message)
    
    def get_room_info(self, room_id: str, include_peers: bool = True) -> Dict[str, Any]:
        """
        Get information about a room.
        
        Args:
            room_id: Room ID
            include_peers: Whether to include peer information
            
        Returns:
            Room information
        """
        return self.signaling_server.get_room_info(room_id, include_peers)
    
    def list_rooms(self, include_peers: bool = False) -> Dict[str, Any]:
        """
        List all rooms.
        
        Args:
            include_peers: Whether to include peer information
            
        Returns:
            List of rooms
        """
        return self.signaling_server.list_rooms(include_peers)
    
    def get_peer_info(self, peer_id: str) -> Dict[str, Any]:
        """
        Get information about a peer.
        
        Args:
            peer_id: Peer ID
            
        Returns:
            Peer information
        """
        return self.signaling_server.get_peer_info(peer_id)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get server status.
        
        Returns:
            Server status
        """
        return self.signaling_server.get_status()