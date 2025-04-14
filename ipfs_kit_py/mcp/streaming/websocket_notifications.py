"""
WebSocket integration for real-time event notifications in MCP server.

This module implements WebSocket support for the MCP server, addressing the
WebSocket Integration requirements in the Streaming Operations section of the MCP roadmap.
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, Set, Callable, Awaitable, List, Union
import uuid
import threading
from enum import Enum

# Configure logger
logger = logging.getLogger(__name__)

# Define event types for WebSocket notifications
class EventType(str, Enum):
    """Event types for WebSocket notifications."""
    CONTENT_ADDED = "content.added"
    CONTENT_RETRIEVED = "content.retrieved"
    CONTENT_REMOVED = "content.removed"
    PIN_ADDED = "pin.added"
    PIN_REMOVED = "pin.removed"
    METADATA_UPDATED = "metadata.updated"
    BACKEND_STATUS = "backend.status"
    OPERATION_STARTED = "operation.started"
    OPERATION_PROGRESS = "operation.progress"
    OPERATION_COMPLETED = "operation.completed"
    OPERATION_FAILED = "operation.failed"
    ERROR = "error"
    CONNECTION = "connection"
    SYSTEM = "system"


class WebSocketNotificationManager:
    """
    Manages WebSocket connections and notifications for MCP server events.
    
    This class implements the WebSocket integration features required
    in the Streaming Operations section of the MCP roadmap.
    """
    
    def __init__(self):
        """Initialize the WebSocket notification manager."""
        self.connections: Dict[str, Any] = {}
        self.channels: Dict[str, Set[str]] = {}  # channel -> set of connection_ids
        self.connection_channels: Dict[str, Set[str]] = {}  # connection_id -> set of channels
        self.running = False
        self.lock = threading.RLock()
        self.message_handlers: Dict[str, Callable[[str, Dict[str, Any]], Awaitable[None]]] = {}
        self.reconnect_interval = 5  # seconds
        
        # Initialize default channels
        self.channels = {
            "content": set(),
            "pinning": set(),
            "metadata": set(),
            "system": set(),
            "operations": set(),
            "all": set()
        }
    
    def start(self):
        """Start the WebSocket notification manager."""
        if not self.running:
            logger.info("Starting WebSocket notification manager")
            self.running = True
            
            # Start a background thread for handling reconnections
            thread = threading.Thread(target=self._reconnect_handler, daemon=True)
            thread.start()
            
            logger.info("WebSocket notification manager started")
    
    def stop(self):
        """Stop the WebSocket notification manager."""
        if self.running:
            logger.info("Stopping WebSocket notification manager")
            self.running = False
            
            # Close all connections
            with self.lock:
                for conn_id in list(self.connections.keys()):
                    self._close_connection(conn_id)
            
            logger.info("WebSocket notification manager stopped")
    
    def register_connection(self, connection: Any) -> str:
        """
        Register a new WebSocket connection.
        
        Args:
            connection: The WebSocket connection object
            
        Returns:
            Unique connection ID
        """
        conn_id = str(uuid.uuid4())
        
        with self.lock:
            self.connections[conn_id] = {
                "connection": connection,
                "connected_at": time.time(),
                "last_ping": time.time(),
                "messages_sent": 0,
                "is_active": True
            }
            self.connection_channels[conn_id] = set()
            
            # Add to system channel by default
            self.subscribe(conn_id, "system")
            
            # Notify about new connection
            self.notify("system", {
                "type": EventType.CONNECTION,
                "action": "connected",
                "connection_id": conn_id,
                "timestamp": time.time()
            })
        
        logger.info(f"New WebSocket connection registered: {conn_id}")
        return conn_id
    
    def unregister_connection(self, conn_id: str):
        """
        Unregister a WebSocket connection.
        
        Args:
            conn_id: The connection ID to unregister
        """
        if not conn_id:
            return
            
        with self.lock:
            if conn_id in self.connections:
                # Unsubscribe from all channels
                if conn_id in self.connection_channels:
                    for channel in list(self.connection_channels[conn_id]):
                        self.unsubscribe(conn_id, channel)
                
                # Close and remove the connection
                self._close_connection(conn_id)
                
                # Notify about disconnection
                self.notify("system", {
                    "type": EventType.CONNECTION,
                    "action": "disconnected",
                    "connection_id": conn_id,
                    "timestamp": time.time()
                })
                
                logger.info(f"WebSocket connection unregistered: {conn_id}")
    
    def _close_connection(self, conn_id: str):
        """
        Close a WebSocket connection and clean up resources.
        
        Args:
            conn_id: The connection ID to close
        """
        if conn_id not in self.connections:
            return
            
        # Mark as inactive
        self.connections[conn_id]["is_active"] = False
        
        # Clean up resources
        if conn_id in self.connection_channels:
            del self.connection_channels[conn_id]
        
        # Remove from channels
        for channel, connections in self.channels.items():
            if conn_id in connections:
                connections.remove(conn_id)
        
        # Remove the connection itself
        del self.connections[conn_id]
    
    def subscribe(self, conn_id: str, channel: str) -> bool:
        """
        Subscribe a connection to a notification channel.
        
        Args:
            conn_id: Connection ID
            channel: Channel name to subscribe to
            
        Returns:
            True if subscription was successful, False otherwise
        """
        if not conn_id or conn_id not in self.connections:
            return False
            
        with self.lock:
            # Create channel if it doesn't exist
            if channel not in self.channels:
                self.channels[channel] = set()
            
            # Add connection to channel
            self.channels[channel].add(conn_id)
            
            # Add channel to connection's subscriptions
            if conn_id not in self.connection_channels:
                self.connection_channels[conn_id] = set()
            self.connection_channels[conn_id].add(channel)
            
            # Notify about subscription
            self.send_to_connection(conn_id, {
                "type": "subscription",
                "action": "subscribed",
                "channel": channel,
                "timestamp": time.time()
            })
            
            logger.debug(f"Connection {conn_id} subscribed to channel {channel}")
            return True
    
    def unsubscribe(self, conn_id: str, channel: str) -> bool:
        """
        Unsubscribe a connection from a notification channel.
        
        Args:
            conn_id: Connection ID
            channel: Channel to unsubscribe from
            
        Returns:
            True if unsubscription was successful, False otherwise
        """
        if not conn_id or conn_id not in self.connections:
            return False
            
        with self.lock:
            success = False
            
            # Remove connection from channel
            if channel in self.channels and conn_id in self.channels[channel]:
                self.channels[channel].remove(conn_id)
                success = True
            
            # Remove channel from connection's subscriptions
            if conn_id in self.connection_channels and channel in self.connection_channels[conn_id]:
                self.connection_channels[conn_id].remove(channel)
                success = True
            
            if success:
                # Notify about unsubscription
                self.send_to_connection(conn_id, {
                    "type": "subscription",
                    "action": "unsubscribed",
                    "channel": channel,
                    "timestamp": time.time()
                })
                
                logger.debug(f"Connection {conn_id} unsubscribed from channel {channel}")
            
            return success
    
    def notify(self, channel: str, event: Dict[str, Any]) -> int:
        """
        Send a notification to all connections subscribed to a channel.
        
        Args:
            channel: Channel to send notification to
            event: Event data to send
            
        Returns:
            Number of connections notified
        """
        if not channel or not event:
            return 0
        
        # Add timestamp if not present
        if "timestamp" not in event:
            event["timestamp"] = time.time()
        
        # Add channel to event data
        event["channel"] = channel
        
        count = 0
        with self.lock:
            # Connections directly subscribed to this channel
            connections = set(self.channels.get(channel, set()))
            
            # Also include connections subscribed to 'all' channel
            connections.update(self.channels.get("all", set()))
            
            # Send to all connections
            for conn_id in connections:
                if self.send_to_connection(conn_id, event):
                    count += 1
        
        if count > 0:
            logger.debug(f"Sent notification to {count} connections on channel {channel}")
        
        return count
    
    def send_to_connection(self, conn_id: str, data: Dict[str, Any]) -> bool:
        """
        Send data to a specific connection.
        
        Args:
            conn_id: Connection ID to send to
            data: Data to send
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not conn_id or conn_id not in self.connections:
            return False
        
        conn_info = self.connections.get(conn_id)
        if not conn_info or not conn_info.get("is_active"):
            return False
        
        connection = conn_info.get("connection")
        if not connection:
            return False
        
        try:
            # Convert data to JSON string
            message = json.dumps(data)
            
            # Send the message using the appropriate method for this connection
            # This will depend on your WebSocket implementation
            if hasattr(connection, "send"):
                # For synchronous WebSocket implementations
                connection.send(message)
            elif hasattr(connection, "send_text"):
                # For asynchronous WebSocket implementations (like FastAPI)
                asyncio.create_task(connection.send_text(message))
            elif hasattr(connection, "write_message"):
                # For Tornado WebSocket implementation
                connection.write_message(message)
            else:
                # Fallback
                logger.error(f"Unable to send message to connection {conn_id}: Unsupported connection type")
                return False
            
            # Update connection stats
            conn_info["messages_sent"] += 1
            
            return True
        except Exception as e:
            logger.error(f"Error sending message to connection {conn_id}: {str(e)}")
            return False
    
    def broadcast(self, data: Dict[str, Any]) -> int:
        """
        Broadcast data to all active connections.
        
        Args:
            data: Data to broadcast
            
        Returns:
            Number of connections messaged
        """
        count = 0
        with self.lock:
            for conn_id in list(self.connections.keys()):
                if self.send_to_connection(conn_id, data):
                    count += 1
        
        if count > 0:
            logger.debug(f"Broadcast message to {count} connections")
        
        return count
    
    def register_message_handler(self, message_type: str, handler: Callable[[str, Dict[str, Any]], Awaitable[None]]):
        """
        Register a handler for a specific message type.
        
        Args:
            message_type: Type of message to handle
            handler: Async function to handle messages of this type
        """
        self.message_handlers[message_type] = handler
        logger.debug(f"Registered message handler for type: {message_type}")
    
    async def handle_message(self, conn_id: str, message: str) -> bool:
        """
        Handle an incoming message from a WebSocket connection.
        
        Args:
            conn_id: Connection ID that sent the message
            message: Raw message string
            
        Returns:
            True if message was handled successfully, False otherwise
        """
        if not conn_id or not message:
            return False
        
        try:
            # Parse the message as JSON
            data = json.loads(message)
            
            # Check if this is a subscription request
            if data.get("action") == "subscribe" and "channel" in data:
                channel = data.get("channel")
                self.subscribe(conn_id, channel)
                return True
            
            # Check if this is an unsubscription request
            elif data.get("action") == "unsubscribe" and "channel" in data:
                channel = data.get("channel")
                self.unsubscribe(conn_id, channel)
                return True
            
            # Check if this is a ping message
            elif data.get("action") == "ping":
                self.send_to_connection(conn_id, {
                    "action": "pong",
                    "timestamp": time.time()
                })
                # Update last ping time
                if conn_id in self.connections:
                    self.connections[conn_id]["last_ping"] = time.time()
                return True
            
            # Handle other message types using registered handlers
            message_type = data.get("type")
            if message_type and message_type in self.message_handlers:
                await self.message_handlers[message_type](conn_id, data)
                return True
            
            # Unhandled message
            logger.warning(f"Unhandled WebSocket message from {conn_id}: {message}")
            return False
            
        except json.JSONDecodeError:
            logger.warning(f"Received invalid JSON from connection {conn_id}")
            return False
        except Exception as e:
            logger.error(f"Error handling message from {conn_id}: {str(e)}")
            return False
    
    def _reconnect_handler(self):
        """Background task to handle reconnections and connection health checks."""
        while self.running:
            try:
                with self.lock:
                    now = time.time()
                    for conn_id in list(self.connections.keys()):
                        conn_info = self.connections[conn_id]
                        
                        # Check if connection is still active
                        if conn_info["is_active"]:
                            # Check if it's been too long since the last ping
                            last_ping = conn_info.get("last_ping", 0)
                            if now - last_ping > 60:  # 60 seconds without a ping
                                logger.warning(f"Connection {conn_id} has not sent a ping in 60 seconds, marking as inactive")
                                conn_info["is_active"] = False
                        
                        # Attempt to reconnect inactive connections (implementation specific)
                        # This would typically be handled at a higher level in your WebSocket server
            
            except Exception as e:
                logger.error(f"Error in reconnect handler: {str(e)}")
            
            # Sleep before next check
            time.sleep(self.reconnect_interval)
            
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the WebSocket manager.
        
        Returns:
            Dict with statistics
        """
        with self.lock:
            active_connections = sum(1 for info in self.connections.values() if info.get("is_active", False))
            total_messages = sum(info.get("messages_sent", 0) for info in self.connections.values())
            
            channel_stats = {
                channel: len(connections)
                for channel, connections in self.channels.items()
            }
            
            return {
                "active_connections": active_connections,
                "total_connections": len(self.connections),
                "total_messages_sent": total_messages,
                "channels": channel_stats,
                "uptime": time.time() - (min([info.get("connected_at", time.time()) for info in self.connections.values()]) if self.connections else time.time())
            }


# Helper function to map event types to channels
def get_channel_for_event(event_type: Union[EventType, str]) -> str:
    """
    Get the appropriate channel for an event type.
    
    Args:
        event_type: Event type or string
        
    Returns:
        Channel name
    """
    if isinstance(event_type, str):
        event_type = EventType(event_type)
    
    channel_mapping = {
        EventType.CONTENT_ADDED: "content",
        EventType.CONTENT_RETRIEVED: "content",
        EventType.CONTENT_REMOVED: "content",
        EventType.PIN_ADDED: "pinning",
        EventType.PIN_REMOVED: "pinning",
        EventType.METADATA_UPDATED: "metadata",
        EventType.BACKEND_STATUS: "system",
        EventType.OPERATION_STARTED: "operations",
        EventType.OPERATION_PROGRESS: "operations",
        EventType.OPERATION_COMPLETED: "operations",
        EventType.OPERATION_FAILED: "operations",
        EventType.ERROR: "system",
        EventType.CONNECTION: "system",
        EventType.SYSTEM: "system",
    }
    
    return channel_mapping.get(event_type, "system")


# Singleton instance
_ws_manager = None

def get_ws_manager() -> WebSocketNotificationManager:
    """
    Get the global WebSocket notification manager instance.
    
    Returns:
        WebSocket notification manager instance
    """
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketNotificationManager()
    return _ws_manager
