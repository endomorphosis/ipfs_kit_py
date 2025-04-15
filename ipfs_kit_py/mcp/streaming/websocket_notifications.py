"""
WebSocket notifications implementation for MCP server.

This module implements the WebSocket integration mentioned in the roadmap,
providing real-time event notifications to clients.
"""

import os
import sys
import json
import time
import uuid
import logging
import asyncio
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Union, Callable
from dataclasses import dataclass

# Configure logger
logger = logging.getLogger(__name__)

class EventType(Enum):
    """Types of events for WebSocket notifications."""
    # Content events
    CONTENT_ADDED = "content.added"
    CONTENT_RETRIEVED = "content.retrieved"
    CONTENT_REMOVED = "content.removed"
    CONTENT_UPDATED = "content.updated"
    
    # Pinning events
    PIN_ADDED = "pin.added"
    PIN_REMOVED = "pin.removed"
    PIN_STATUS_CHANGED = "pin.status_changed"
    
    # Storage events
    STORAGE_BACKEND_ADDED = "storage.backend_added"
    STORAGE_BACKEND_REMOVED = "storage.backend_removed"
    STORAGE_BACKEND_STATUS_CHANGED = "storage.backend_status_changed"
    
    # System events
    SYSTEM_STATUS = "system.status"
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"
    
    # Migration events
    MIGRATION_STARTED = "migration.started"
    MIGRATION_PROGRESS = "migration.progress"
    MIGRATION_COMPLETED = "migration.completed"
    MIGRATION_FAILED = "migration.failed"
    
    # Transfer events
    TRANSFER_STARTED = "transfer.started"
    TRANSFER_PROGRESS = "transfer.progress"
    TRANSFER_COMPLETED = "transfer.completed"
    TRANSFER_FAILED = "transfer.failed"
    
    # Search events
    SEARCH_INDEXING_STARTED = "search.indexing_started"
    SEARCH_INDEXING_PROGRESS = "search.indexing_progress"
    SEARCH_INDEXING_COMPLETED = "search.indexing_completed"
    SEARCH_INDEXING_FAILED = "search.indexing_failed"

@dataclass
class WebSocketClient:
    """Represents a connected WebSocket client."""
    id: str
    websocket: Any
    channels: Set[str]
    connected_at: float
    last_activity: float

class WebSocketManager:
    """
    Manager for WebSocket connections and notifications.
    
    This class implements WebSocket notification system mentioned
    in the roadmap, providing real-time event notifications.
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton implementation."""
        if cls._instance is None:
            cls._instance = super(WebSocketManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the WebSocket manager."""
        # Skip initialization if already initialized
        if getattr(self, "_initialized", False):
            return
        
        self._clients: Dict[str, WebSocketClient] = {}
        self._channels: Dict[str, Set[str]] = {}
        self._stats = {
            "total_connections": 0,
            "total_messages_sent": 0,
            "total_broadcasts": 0
        }
        self._initialized = True
        
        logger.info("WebSocket manager initialized")
    
    async def register_client(self, websocket: Any) -> str:
        """
        Register a new WebSocket client.
        
        Args:
            websocket: WebSocket connection object
            
        Returns:
            Client ID
        """
        # Generate client ID
        client_id = str(uuid.uuid4())
        
        # Add client
        now = time.time()
        self._clients[client_id] = WebSocketClient(
            id=client_id,
            websocket=websocket,
            channels=set(),
            connected_at=now,
            last_activity=now
        )
        
        # Update stats
        self._stats["total_connections"] += 1
        
        logger.info(f"Client {client_id} connected")
        
        return client_id
    
    async def unregister_client(self, client_id: str):
        """
        Unregister a WebSocket client.
        
        Args:
            client_id: Client ID
        """
        if client_id in self._clients:
            # Get client channels
            channels = self._clients[client_id].channels.copy()
            
            # Remove client from channels
            for channel in channels:
                await self.unsubscribe(client_id, channel)
            
            # Remove client
            del self._clients[client_id]
            
            logger.info(f"Client {client_id} disconnected")
    
    async def subscribe(self, client_id: str, channel: str) -> bool:
        """
        Subscribe a client to a channel.
        
        Args:
            client_id: Client ID
            channel: Channel name
            
        Returns:
            True if subscription was successful
        """
        if client_id not in self._clients:
            logger.warning(f"Cannot subscribe unknown client {client_id}")
            return False
        
        # Add channel to client
        self._clients[client_id].channels.add(channel)
        
        # Add client to channel
        if channel not in self._channels:
            self._channels[channel] = set()
        self._channels[channel].add(client_id)
        
        # Update last activity
        self._clients[client_id].last_activity = time.time()
        
        logger.debug(f"Client {client_id} subscribed to channel {channel}")
        return True
    
    async def unsubscribe(self, client_id: str, channel: str) -> bool:
        """
        Unsubscribe a client from a channel.
        
        Args:
            client_id: Client ID
            channel: Channel name
            
        Returns:
            True if unsubscription was successful
        """
        if client_id not in self._clients:
            logger.warning(f"Cannot unsubscribe unknown client {client_id}")
            return False
        
        # Remove channel from client
        if channel in self._clients[client_id].channels:
            self._clients[client_id].channels.remove(channel)
        
        # Remove client from channel
        if channel in self._channels and client_id in self._channels[channel]:
            self._channels[channel].remove(client_id)
            
            # Remove channel if empty
            if not self._channels[channel]:
                del self._channels[channel]
        
        # Update last activity
        self._clients[client_id].last_activity = time.time()
        
        logger.debug(f"Client {client_id} unsubscribed from channel {channel}")
        return True
    
    async def send(self, client_id: str, message: Union[str, Dict[str, Any]]) -> bool:
        """
        Send a message to a specific client.
        
        Args:
            client_id: Client ID
            message: Message to send
            
        Returns:
            True if message was sent successfully
        """
        if client_id not in self._clients:
            logger.warning(f"Cannot send to unknown client {client_id}")
            return False
        
        client = self._clients[client_id]
        
        try:
            # Convert message to string if needed
            if isinstance(message, dict):
                message_str = json.dumps(message)
            else:
                message_str = str(message)
            
            # Send message
            await client.websocket.send_text(message_str)
            
            # Update stats
            self._stats["total_messages_sent"] += 1
            
            # Update last activity
            client.last_activity = time.time()
            
            return True
        except Exception as e:
            logger.error(f"Error sending message to client {client_id}: {e}")
            return False
    
    async def broadcast(self, message: Union[str, Dict[str, Any]], channel: str = None) -> int:
        """
        Broadcast a message to multiple clients.
        
        Args:
            message: Message to send
            channel: Optional channel name (if None, broadcast to all clients)
            
        Returns:
            Number of clients the message was sent to
        """
        # Convert message to string if needed
        if isinstance(message, dict):
            message_str = json.dumps(message)
        else:
            message_str = str(message)
        
        # Get target clients
        if channel is not None:
            # Broadcast to channel subscribers
            if channel not in self._channels:
                return 0
            
            target_client_ids = self._channels[channel]
        else:
            # Broadcast to all clients
            target_client_ids = self._clients.keys()
        
        # Send message to all targets
        sent_count = 0
        for client_id in list(target_client_ids):
            try:
                if await self.send(client_id, message_str):
                    sent_count += 1
            except Exception as e:
                logger.error(f"Error broadcasting to client {client_id}: {e}")
        
        # Update stats
        self._stats["total_broadcasts"] += 1
        
        return sent_count
    
    def notify(self, channel: str, data: Dict[str, Any]) -> bool:
        """
        Send a notification to a channel.
        
        This is a synchronous wrapper around broadcast for easier use
        from non-async code. It schedules the broadcast in the event loop.
        
        Args:
            channel: Channel name
            data: Notification data
            
        Returns:
            True if notification was scheduled successfully
        """
        try:
            # Create notification message
            message = {
                "type": "notification",
                "channel": channel,
                "timestamp": time.time(),
                "data": data
            }
            
            # Schedule broadcast in event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule in running loop
                asyncio.create_task(self.broadcast(message, channel))
            else:
                # Create new loop (this should rarely happen)
                async def _broadcast():
                    await self.broadcast(message, channel)
                
                asyncio.run(_broadcast())
            
            return True
        except Exception as e:
            logger.error(f"Error scheduling notification for channel {channel}: {e}")
            return False
    
    def get_client_info(self, client_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a client.
        
        Args:
            client_id: Client ID
            
        Returns:
            Dictionary with client information or None if not found
        """
        if client_id not in self._clients:
            return None
        
        client = self._clients[client_id]
        
        return {
            "id": client.id,
            "channels": list(client.channels),
            "connected_at": client.connected_at,
            "last_activity": client.last_activity,
            "connection_time": time.time() - client.connected_at
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get WebSocket manager statistics.
        
        Returns:
            Dictionary with statistics
        """
        stats = self._stats.copy()
        stats["active_connections"] = len(self._clients)
        stats["active_channels"] = len(self._channels)
        
        # Channel subscription counts
        channel_stats = {}
        for channel, clients in self._channels.items():
            channel_stats[channel] = len(clients)
        
        stats["channels"] = channel_stats
        
        return stats
    
    async def cleanup_inactive_clients(self, inactive_timeout: int = 300) -> int:
        """
        Clean up inactive clients.
        
        Args:
            inactive_timeout: Timeout in seconds for inactivity
            
        Returns:
            Number of clients cleaned up
        """
        now = time.time()
        inactive_client_ids = []
        
        # Find inactive clients
        for client_id, client in self._clients.items():
            if now - client.last_activity > inactive_timeout:
                inactive_client_ids.append(client_id)
        
        # Unregister inactive clients
        for client_id in inactive_client_ids:
            await self.unregister_client(client_id)
        
        return len(inactive_client_ids)


def get_ws_manager() -> WebSocketManager:
    """
    Get the WebSocket manager singleton instance.
    
    Returns:
        WebSocket manager instance
    """
    return WebSocketManager()