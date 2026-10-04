"""
JSON-RPC Methods for MCP Server.

This module provides JSON-RPC method implementations that replace
WebSocket functionality, including event management, subscriptions,
and WebRTC signaling.
"""

import json
import time
import logging
import uuid
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

from .jsonrpc_event_manager import get_jsonrpc_event_manager, EventCategory

# Configure logger
logger = logging.getLogger(__name__)


class JSONRPCEventMethods:
    """JSON-RPC methods for event management (replacing WebSocket /ws endpoint)."""
    
    def __init__(self):
        self.event_manager = get_jsonrpc_event_manager()
    
    async def create_session(self, session_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Create a new event session.
        
        Replaces WebSocket connection establishment.
        
        Args:
            session_id: Optional session ID
            
        Returns:
            Session creation result
        """
        try:
            session_id = self.event_manager.create_session(session_id)
            
            return {
                "success": True,
                "session_id": session_id,
                "message": "Session created successfully",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def destroy_session(self, session_id: str, **kwargs) -> Dict[str, Any]:
        """
        Destroy an event session.
        
        Replaces WebSocket disconnection.
        
        Args:
            session_id: Session ID to destroy
            
        Returns:
            Session destruction result
        """
        try:
            success = self.event_manager.destroy_session(session_id)
            
            return {
                "success": success,
                "message": f"Session {'destroyed' if success else 'not found'}",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error destroying session: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def subscribe(self, session_id: str, categories: Union[str, List[str]], **kwargs) -> Dict[str, Any]:
        """
        Subscribe to event categories.
        
        Replaces WebSocket subscription messages.
        
        Args:
            session_id: Session ID
            categories: Category or list of categories to subscribe to
            
        Returns:
            Subscription result
        """
        try:
            result = self.event_manager.subscribe(session_id, categories)
            result["timestamp"] = datetime.now().isoformat()
            return result
        except Exception as e:
            logger.error(f"Error subscribing: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def unsubscribe(self, session_id: str, categories: Optional[Union[str, List[str]]] = None, **kwargs) -> Dict[str, Any]:
        """
        Unsubscribe from event categories.
        
        Replaces WebSocket unsubscription messages.
        
        Args:
            session_id: Session ID
            categories: Category or list of categories to unsubscribe from (all if None)
            
        Returns:
            Unsubscription result
        """
        try:
            result = self.event_manager.unsubscribe(session_id, categories)
            result["timestamp"] = datetime.now().isoformat()
            return result
        except Exception as e:
            logger.error(f"Error unsubscribing: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def poll_events(self, session_id: str, since: Optional[str] = None, limit: int = 100, **kwargs) -> Dict[str, Any]:
        """
        Poll for events.
        
        Replaces WebSocket real-time event delivery with polling.
        
        Args:
            session_id: Session ID
            since: ISO timestamp to get events since
            limit: Maximum number of events to return
            
        Returns:
            Events and metadata
        """
        try:
            return self.event_manager.poll_events(session_id, since, limit)
        except Exception as e:
            logger.error(f"Error polling events: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def get_session_status(self, session_id: str, **kwargs) -> Dict[str, Any]:
        """
        Get session status and statistics.
        
        Replaces WebSocket status messages.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session status
        """
        try:
            return self.event_manager.get_session_status(session_id)
        except Exception as e:
            logger.error(f"Error getting session status: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def ping(self, session_id: Optional[str] = None, data: Any = None, **kwargs) -> Dict[str, Any]:
        """
        Ping method for connection health check.
        
        Replaces WebSocket ping/pong mechanism.
        
        Args:
            session_id: Optional session ID
            data: Optional data to echo back
            
        Returns:
            Pong response
        """
        try:
            result = {
                "success": True,
                "type": "pong",
                "timestamp": datetime.now().isoformat(),
                "server": "mcp-jsonrpc"
            }
            
            if session_id:
                result["session_id"] = session_id
                # Update session activity if session exists
                if session_id in self.event_manager.sessions:
                    self.event_manager.sessions[session_id].update_activity()
            
            if data is not None:
                result["echo"] = data
            
            return result
        except Exception as e:
            logger.error(f"Error in ping: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def get_server_stats(self, **kwargs) -> Dict[str, Any]:
        """
        Get server statistics.
        
        Args:
            
        Returns:
            Server statistics
        """
        try:
            stats = self.event_manager.get_server_stats()
            return {
                "success": True,
                "stats": stats,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting server stats: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


class JSONRPCWebRTCMethods:
    """JSON-RPC methods for WebRTC signaling (replacing WebSocket /webrtc/signal endpoint)."""
    
    def __init__(self):
        self.rooms: Dict[str, Dict[str, Any]] = {}  # room_id -> room_data
        self.peers: Dict[str, Dict[str, Any]] = {}  # peer_id -> peer_data
        self.room_peers: Dict[str, List[str]] = {}  # room_id -> list of peer_ids
    
    async def join_room(self, room_id: str, peer_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """
        Join a WebRTC signaling room.
        
        Replaces WebSocket room joining.
        
        Args:
            room_id: Room identifier
            peer_id: Optional peer identifier (generated if not provided)
            metadata: Optional peer metadata
            
        Returns:
            Join result with peer information
        """
        try:
            if peer_id is None:
                peer_id = str(uuid.uuid4())
            
            # Create room if it doesn't exist
            if room_id not in self.rooms:
                self.rooms[room_id] = {
                    "id": room_id,
                    "created_at": datetime.now().isoformat(),
                    "peer_count": 0
                }
                self.room_peers[room_id] = []
            
            # Create peer data
            peer_data = {
                "id": peer_id,
                "room_id": room_id,
                "joined_at": datetime.now().isoformat(),
                "metadata": metadata or {},
                "last_activity": datetime.now().isoformat()
            }
            
            # Add peer to room
            self.peers[peer_id] = peer_data
            if peer_id not in self.room_peers[room_id]:
                self.room_peers[room_id].append(peer_id)
                self.rooms[room_id]["peer_count"] = len(self.room_peers[room_id])
            
            # Get other peers in room
            other_peers = []
            for p_id in self.room_peers[room_id]:
                if p_id != peer_id and p_id in self.peers:
                    other_peers.append({
                        "id": p_id,
                        "metadata": self.peers[p_id].get("metadata", {}),
                        "joined_at": self.peers[p_id].get("joined_at")
                    })
            
            return {
                "success": True,
                "peer_id": peer_id,
                "room_id": room_id,
                "other_peers": other_peers,
                "room_info": self.rooms[room_id],
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error joining room: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def leave_room(self, room_id: str, peer_id: str, **kwargs) -> Dict[str, Any]:
        """
        Leave a WebRTC signaling room.
        
        Args:
            room_id: Room identifier
            peer_id: Peer identifier
            
        Returns:
            Leave result
        """
        try:
            success = False
            
            # Remove peer from room
            if peer_id in self.peers and self.peers[peer_id]["room_id"] == room_id:
                del self.peers[peer_id]
                success = True
            
            if room_id in self.room_peers and peer_id in self.room_peers[room_id]:
                self.room_peers[room_id].remove(peer_id)
                success = True
                
                # Update room peer count
                if room_id in self.rooms:
                    self.rooms[room_id]["peer_count"] = len(self.room_peers[room_id])
                    
                    # Clean up empty room
                    if not self.room_peers[room_id]:
                        del self.rooms[room_id]
                        del self.room_peers[room_id]
            
            return {
                "success": success,
                "peer_id": peer_id,
                "room_id": room_id,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error leaving room: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def send_signal(self, room_id: str, peer_id: str, target_peer_id: str, signal_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Send a WebRTC signal to another peer.
        
        Args:
            room_id: Room identifier
            peer_id: Sender peer identifier
            target_peer_id: Target peer identifier
            signal_data: Signal data to send
            
        Returns:
            Send result
        """
        try:
            # Validate peer and room
            if peer_id not in self.peers or self.peers[peer_id]["room_id"] != room_id:
                return {
                    "success": False,
                    "error": "Peer not in room",
                    "timestamp": datetime.now().isoformat()
                }
            
            if target_peer_id not in self.peers or self.peers[target_peer_id]["room_id"] != room_id:
                return {
                    "success": False,
                    "error": "Target peer not in room",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Update last activity
            self.peers[peer_id]["last_activity"] = datetime.now().isoformat()
            
            # In a real implementation, this would queue the signal for the target peer
            # For now, we'll just store it in a simple message queue
            if not hasattr(self, 'message_queue'):
                self.message_queue = {}
            
            if target_peer_id not in self.message_queue:
                self.message_queue[target_peer_id] = []
            
            message = {
                "from_peer_id": peer_id,
                "signal_data": signal_data,
                "timestamp": datetime.now().isoformat(),
                "room_id": room_id
            }
            
            self.message_queue[target_peer_id].append(message)
            
            return {
                "success": True,
                "peer_id": peer_id,
                "target_peer_id": target_peer_id,
                "room_id": room_id,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error sending signal: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def poll_signals(self, peer_id: str, **kwargs) -> Dict[str, Any]:
        """
        Poll for incoming WebRTC signals.
        
        Args:
            peer_id: Peer identifier
            
        Returns:
            Incoming signals
        """
        try:
            if not hasattr(self, 'message_queue'):
                self.message_queue = {}
            
            messages = self.message_queue.get(peer_id, [])
            
            # Clear the queue after reading
            if peer_id in self.message_queue:
                self.message_queue[peer_id] = []
            
            # Update last activity if peer exists
            if peer_id in self.peers:
                self.peers[peer_id]["last_activity"] = datetime.now().isoformat()
            
            return {
                "success": True,
                "peer_id": peer_id,
                "signals": messages,
                "count": len(messages),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error polling signals: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def get_room_peers(self, room_id: str, **kwargs) -> Dict[str, Any]:
        """
        Get peers in a room.
        
        Args:
            room_id: Room identifier
            
        Returns:
            Room peers information
        """
        try:
            if room_id not in self.rooms:
                return {
                    "success": False,
                    "error": "Room not found",
                    "timestamp": datetime.now().isoformat()
                }
            
            peers = []
            for peer_id in self.room_peers.get(room_id, []):
                if peer_id in self.peers:
                    peer_data = self.peers[peer_id]
                    peers.append({
                        "id": peer_id,
                        "metadata": peer_data.get("metadata", {}),
                        "joined_at": peer_data.get("joined_at"),
                        "last_activity": peer_data.get("last_activity")
                    })
            
            return {
                "success": True,
                "room_id": room_id,
                "room_info": self.rooms[room_id],
                "peers": peers,
                "peer_count": len(peers),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting room peers: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def get_webrtc_stats(self, **kwargs) -> Dict[str, Any]:
        """
        Get WebRTC statistics.
        
        Returns:
            WebRTC statistics
        """
        try:
            return {
                "success": True,
                "stats": {
                    "rooms": len(self.rooms),
                    "total_peers": len(self.peers),
                    "active_rooms": {room_id: len(peers) for room_id, peers in self.room_peers.items()},
                    "message_queue_size": sum(len(queue) for queue in getattr(self, 'message_queue', {}).values())
                },
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting WebRTC stats: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# Global instances
_event_methods: Optional[JSONRPCEventMethods] = None
_webrtc_methods: Optional[JSONRPCWebRTCMethods] = None


def get_jsonrpc_event_methods() -> JSONRPCEventMethods:
    """Get the global JSON-RPC event methods instance."""
    global _event_methods
    
    if _event_methods is None:
        _event_methods = JSONRPCEventMethods()
    
    return _event_methods


def get_jsonrpc_webrtc_methods() -> JSONRPCWebRTCMethods:
    """Get the global JSON-RPC WebRTC methods instance."""
    global _webrtc_methods
    
    if _webrtc_methods is None:
        _webrtc_methods = JSONRPCWebRTCMethods()
    
    return _webrtc_methods


def register_jsonrpc_methods(dispatcher):
    """
    Register all JSON-RPC methods with a dispatcher.
    
    Args:
        dispatcher: JSON-RPC dispatcher to register methods with
    """
    event_methods = get_jsonrpc_event_methods()
    webrtc_methods = get_jsonrpc_webrtc_methods()
    
    # Event management methods (replacing WebSocket /ws)
    dispatcher.add_method(event_methods.create_session, "events.create_session")
    dispatcher.add_method(event_methods.destroy_session, "events.destroy_session")
    dispatcher.add_method(event_methods.subscribe, "events.subscribe")
    dispatcher.add_method(event_methods.unsubscribe, "events.unsubscribe")
    dispatcher.add_method(event_methods.poll_events, "events.poll")
    dispatcher.add_method(event_methods.get_session_status, "events.get_session_status")
    dispatcher.add_method(event_methods.ping, "events.ping")
    dispatcher.add_method(event_methods.get_server_stats, "events.get_server_stats")
    
    # WebRTC signaling methods (replacing WebSocket /webrtc/signal)
    dispatcher.add_method(webrtc_methods.join_room, "webrtc.join_room")
    dispatcher.add_method(webrtc_methods.leave_room, "webrtc.leave_room")
    dispatcher.add_method(webrtc_methods.send_signal, "webrtc.send_signal")
    dispatcher.add_method(webrtc_methods.poll_signals, "webrtc.poll_signals")
    dispatcher.add_method(webrtc_methods.get_room_peers, "webrtc.get_room_peers")
    dispatcher.add_method(webrtc_methods.get_webrtc_stats, "webrtc.get_stats")
    
    logger.info("Registered JSON-RPC methods for event management and WebRTC signaling")