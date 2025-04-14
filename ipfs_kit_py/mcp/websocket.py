"""
MCP WebSocket Module for real-time communication.

This module provides WebSocket capabilities for the MCP server, enabling:
1. Real-time event notifications
2. Subscription-based updates
3. Bidirectional communication
4. Automatic connection recovery
"""

import json
import time
import logging
import asyncio
import threading
import uuid
import queue
from enum import Enum
from typing import Dict, Any, List, Set, Optional, Callable, Union
from datetime import datetime
from dataclasses import dataclass, field

# Configure logger
logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of WebSocket messages."""
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    EVENT = "event"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"
    STATUS = "status"
    OPERATION = "operation"


class EventCategory(Enum):
    """Categories of events to subscribe to."""
    BACKEND = "backend"
    STORAGE = "storage"
    MIGRATION = "migration"
    STREAMING = "streaming"
    SEARCH = "search"
    SYSTEM = "system"
    ALL = "all"


@dataclass
class WSClient:
    """Information about a connected WebSocket client."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subscriptions: Set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    user_agent: Optional[str] = None
    remote_ip: Optional[str] = None
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "subscriptions": list(self.subscriptions),
            "connected_at": self.connected_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "user_agent": self.user_agent,
            "remote_ip": self.remote_ip,
            "connected_for": (datetime.now() - self.connected_at).total_seconds()
        }


@dataclass
class WSMessage:
    """WebSocket message."""
    type: MessageType
    data: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type.value,
            "data": self.data,
            "id": self.id,
            "timestamp": self.timestamp.isoformat()
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> Optional['WSMessage']:
        """Create message from JSON string."""
        try:
            data = json.loads(json_str)
            msg_type = data.get("type")
            if not msg_type:
                return None
            
            try:
                message_type = MessageType(msg_type)
            except ValueError:
                return None
            
            msg_data = data.get("data", {})
            msg_id = data.get("id", str(uuid.uuid4()))
            
            try:
                msg_timestamp = datetime.fromisoformat(data.get("timestamp", ""))
            except ValueError:
                msg_timestamp = datetime.now()
            
            return cls(
                type=message_type,
                data=msg_data,
                id=msg_id,
                timestamp=msg_timestamp
            )
        except Exception as e:
            logger.error(f"Error parsing WebSocket message: {e}")
            return None


class WebSocketManager:
    """Manager for WebSocket connections and messaging."""
    
    def __init__(self, event_handlers: Optional[Dict[str, Callable]] = None):
        """
        Initialize WebSocket manager.
        
        Args:
            event_handlers: Optional dictionary mapping event types to handler functions
        """
        self.clients: Dict[str, WSClient] = {}
        self.event_handlers = event_handlers or {}
        self.message_queue = queue.Queue()
        self.shutdown_flag = threading.Event()
        
        # Map of category to clients subscribed to it
        self.subscriptions: Dict[str, Set[str]] = {}
        
        # Message handlers dispatch table
        self.message_handlers = {
            MessageType.CONNECT: self._handle_connect,
            MessageType.DISCONNECT: self._handle_disconnect,
            MessageType.SUBSCRIBE: self._handle_subscribe,
            MessageType.UNSUBSCRIBE: self._handle_unsubscribe,
            MessageType.PING: self._handle_ping,
            MessageType.STATUS: self._handle_status
        }
        
        # Start message processor thread
        self.processor_thread = threading.Thread(
            target=self._process_messages, 
            daemon=True
        )
        self.processor_thread.start()
    
    def register_client(self, client_id: Optional[str] = None, 
                       user_agent: Optional[str] = None,
                       remote_ip: Optional[str] = None) -> WSClient:
        """
        Register a new WebSocket client.
        
        Args:
            client_id: Optional client ID (generated if not provided)
            user_agent: Optional user agent string
            remote_ip: Optional remote IP address
            
        Returns:
            WSClient instance
        """
        client = WSClient(
            id=client_id or str(uuid.uuid4()),
            user_agent=user_agent,
            remote_ip=remote_ip
        )
        
        self.clients[client.id] = client
        
        # Send welcome message
        welcome_message = WSMessage(
            type=MessageType.CONNECT,
            data={
                "client_id": client.id,
                "message": "Welcome to MCP WebSocket Server",
                "connected_at": client.connected_at.isoformat()
            }
        )
        
        self.message_queue.put((client.id, welcome_message))
        
        return client
    
    def unregister_client(self, client_id: str) -> None:
        """
        Unregister a WebSocket client.
        
        Args:
            client_id: Client ID
        """
        if client_id in self.clients:
            client = self.clients[client_id]
            
            # Remove from subscriptions
            for category in list(client.subscriptions):
                self._unsubscribe_client(client_id, category)
            
            # Remove from clients dictionary
            del self.clients[client_id]
    
    def handle_message(self, client_id: str, message_json: str) -> None:
        """
        Handle an incoming WebSocket message.
        
        Args:
            client_id: Client ID
            message_json: Message as JSON string
        """
        if client_id not in self.clients:
            logger.warning(f"Message received for unknown client: {client_id}")
            return
        
        # Update client activity
        self.clients[client_id].update_activity()
        
        # Parse message
        message = WSMessage.from_json(message_json)
        if not message:
            error_message = WSMessage(
                type=MessageType.ERROR,
                data={"error": "Invalid message format", "original": message_json}
            )
            self.message_queue.put((client_id, error_message))
            return
        
        # Handle message based on type
        handler = self.message_handlers.get(message.type)
        if handler:
            handler(client_id, message)
        else:
            # Unknown message type
            error_message = WSMessage(
                type=MessageType.ERROR,
                data={"error": f"Unsupported message type: {message.type.value}", "original": message.to_dict()}
            )
            self.message_queue.put((client_id, error_message))
    
    def _handle_connect(self, client_id: str, message: WSMessage) -> None:
        """
        Handle connect message.
        
        Args:
            client_id: Client ID
            message: WebSocket message
        """
        # Client is already connected, just acknowledge
        response = WSMessage(
            type=MessageType.CONNECT,
            data={
                "client_id": client_id,
                "status": "connected", 
                "message": "Already connected",
                "timestamp": datetime.now().isoformat()
            }
        )
        self.message_queue.put((client_id, response))
    
    def _handle_disconnect(self, client_id: str, message: WSMessage) -> None:
        """
        Handle disconnect message.
        
        Args:
            client_id: Client ID
            message: WebSocket message
        """
        # Acknowledge disconnect request
        response = WSMessage(
            type=MessageType.DISCONNECT,
            data={
                "client_id": client_id,
                "status": "disconnected",
                "message": "Disconnected by client request",
                "timestamp": datetime.now().isoformat()
            }
        )
        self.message_queue.put((client_id, response))
        
        # Unregister client
        self.unregister_client(client_id)
    
    def _handle_subscribe(self, client_id: str, message: WSMessage) -> None:
        """
        Handle subscribe message.
        
        Args:
            client_id: Client ID
            message: WebSocket message
        """
        categories = message.data.get("categories", [])
        if not categories:
            # Try singular category
            category = message.data.get("category")
            if category:
                categories = [category]
        
        if not categories:
            # No categories specified
            error_message = WSMessage(
                type=MessageType.ERROR,
                data={"error": "No categories specified for subscription", "original": message.to_dict()}
            )
            self.message_queue.put((client_id, error_message))
            return
        
        # Subscribe to each category
        subscribed = []
        for category in categories:
            result = self._subscribe_client(client_id, category)
            if result:
                subscribed.append(category)
        
        # Send response
        response = WSMessage(
            type=MessageType.SUBSCRIBE,
            data={
                "subscribed": subscribed,
                "timestamp": datetime.now().isoformat()
            }
        )
        self.message_queue.put((client_id, response))
    
    def _handle_unsubscribe(self, client_id: str, message: WSMessage) -> None:
        """
        Handle unsubscribe message.
        
        Args:
            client_id: Client ID
            message: WebSocket message
        """
        categories = message.data.get("categories", [])
        if not categories:
            # Try singular category
            category = message.data.get("category")
            if category:
                categories = [category]
        
        if not categories:
            # Unsubscribe from all
            categories = list(self.clients[client_id].subscriptions)
        
        # Unsubscribe from each category
        unsubscribed = []
        for category in categories:
            result = self._unsubscribe_client(client_id, category)
            if result:
                unsubscribed.append(category)
        
        # Send response
        response = WSMessage(
            type=MessageType.UNSUBSCRIBE,
            data={
                "unsubscribed": unsubscribed,
                "timestamp": datetime.now().isoformat()
            }
        )
        self.message_queue.put((client_id, response))
    
    def _handle_ping(self, client_id: str, message: WSMessage) -> None:
        """
        Handle ping message.
        
        Args:
            client_id: Client ID
            message: WebSocket message
        """
        # Send pong response
        response = WSMessage(
            type=MessageType.PONG,
            data={
                "timestamp": datetime.now().isoformat(),
                "echo": message.data.get("data")
            }
        )
        self.message_queue.put((client_id, response))
    
    def _handle_status(self, client_id: str, message: WSMessage) -> None:
        """
        Handle status message.
        
        Args:
            client_id: Client ID
            message: WebSocket message
        """
        # Send server status
        client = self.clients[client_id]
        
        response = WSMessage(
            type=MessageType.STATUS,
            data={
                "client": client.to_dict(),
                "server": {
                    "clients": len(self.clients),
                    "subscriptions": {category: len(clients) for category, clients in self.subscriptions.items()},
                    "uptime": time.time(),  # Would be more meaningful with server start time
                    "timestamp": datetime.now().isoformat()
                }
            }
        )
        self.message_queue.put((client_id, response))
    
    def _subscribe_client(self, client_id: str, category: str) -> bool:
        """
        Subscribe a client to a category.
        
        Args:
            client_id: Client ID
            category: Event category to subscribe to
            
        Returns:
            True if successfully subscribed
        """
        if client_id not in self.clients:
            return False
        
        client = self.clients[client_id]
        
        # Handle special "all" category
        if category.lower() == EventCategory.ALL.value:
            for cat in EventCategory:
                if cat != EventCategory.ALL:
                    self._subscribe_client(client_id, cat.value)
            return True
        
        # Add to client's subscriptions
        client.subscriptions.add(category)
        
        # Add to subscriptions map
        if category not in self.subscriptions:
            self.subscriptions[category] = set()
        
        self.subscriptions[category].add(client_id)
        
        return True
    
    def _unsubscribe_client(self, client_id: str, category: str) -> bool:
        """
        Unsubscribe a client from a category.
        
        Args:
            client_id: Client ID
            category: Event category to unsubscribe from
            
        Returns:
            True if successfully unsubscribed
        """
        if client_id not in self.clients:
            return False
        
        client = self.clients[client_id]
        
        # Handle special "all" category
        if category.lower() == EventCategory.ALL.value:
            for cat in list(client.subscriptions):
                self._unsubscribe_client(client_id, cat)
            return True
        
        # Remove from client's subscriptions
        if category in client.subscriptions:
            client.subscriptions.remove(category)
        
        # Remove from subscriptions map
        if category in self.subscriptions and client_id in self.subscriptions[category]:
            self.subscriptions[category].remove(client_id)
            
            # Clean up empty category
            if not self.subscriptions[category]:
                del self.subscriptions[category]
        
        return True
    
    def send_event(self, category: str, event_type: str, data: Dict[str, Any]) -> None:
        """
        Send an event to all subscribed clients.
        
        Args:
            category: Event category
            event_type: Type of event
            data: Event data
        """
        if category not in self.subscriptions:
            # No subscribers
            return
        
        # Create event message
        event_message = WSMessage(
            type=MessageType.EVENT,
            data={
                "category": category,
                "event": event_type,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        # Queue message for all subscribed clients
        for client_id in self.subscriptions[category]:
            if client_id in self.clients:
                self.message_queue.put((client_id, event_message))
    
    def broadcast(self, message_type: MessageType, data: Dict[str, Any]) -> None:
        """
        Broadcast a message to all connected clients.
        
        Args:
            message_type: Type of message
            data: Message data
        """
        # Create broadcast message
        broadcast_message = WSMessage(
            type=message_type,
            data=data
        )
        
        # Queue message for all clients
        for client_id in self.clients:
            self.message_queue.put((client_id, broadcast_message))
    
    def send_to_client(self, client_id: str, message_type: MessageType, data: Dict[str, Any]) -> bool:
        """
        Send a message to a specific client.
        
        Args:
            client_id: Client ID
            message_type: Type of message
            data: Message data
            
        Returns:
            True if message was queued
        """
        if client_id not in self.clients:
            return False
        
        # Create message
        message = WSMessage(
            type=message_type,
            data=data
        )
        
        # Queue message
        self.message_queue.put((client_id, message))
        
        return True
    
    def notify_backend_change(self, backend_name: str, operation: str, 
                            content_id: Optional[str] = None, 
                            details: Optional[Dict[str, Any]] = None) -> None:
        """
        Notify subscribers of backend changes.
        
        Args:
            backend_name: Name of the backend
            operation: Operation performed (add, update, delete, etc.)
            content_id: Optional content identifier
            details: Optional additional details
        """
        event_data = {
            "backend": backend_name,
            "operation": operation,
            "timestamp": datetime.now().isoformat(),
        }
        
        if content_id:
            event_data["content_id"] = content_id
            
        if details:
            event_data["details"] = details
        
        self.send_event(EventCategory.BACKEND.value, f"{backend_name}_{operation}", event_data)
        
        # Also send to storage category for compatibility
        self.send_event(EventCategory.STORAGE.value, f"{backend_name}_{operation}", event_data)
    
    def notify_migration_event(self, migration_id: str, status: str, 
                             source_backend: str, target_backend: str,
                             details: Optional[Dict[str, Any]] = None) -> None:
        """
        Notify subscribers of migration events.
        
        Args:
            migration_id: Migration identifier
            status: Migration status
            source_backend: Source backend name
            target_backend: Target backend name
            details: Optional additional details
        """
        event_data = {
            "migration_id": migration_id,
            "status": status,
            "source_backend": source_backend,
            "target_backend": target_backend,
            "timestamp": datetime.now().isoformat(),
        }
        
        if details:
            event_data["details"] = details
        
        self.send_event(EventCategory.MIGRATION.value, f"migration_{status}", event_data)
    
    def notify_stream_progress(self, operation_id: str, progress: Dict[str, Any]) -> None:
        """
        Notify subscribers of streaming progress.
        
        Args:
            operation_id: Streaming operation identifier
            progress: Progress information
        """
        event_data = {
            "operation_id": operation_id,
            "progress": progress,
            "timestamp": datetime.now().isoformat(),
        }
        
        self.send_event(EventCategory.STREAMING.value, "stream_progress", event_data)
    
    def notify_search_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Notify subscribers of search events.
        
        Args:
            event_type: Type of search event
            data: Event data
        """
        event_data = {
            **data,
            "timestamp": datetime.now().isoformat(),
        }
        
        self.send_event(EventCategory.SEARCH.value, f"search_{event_type}", event_data)
    
    def notify_system_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Notify subscribers of system events.
        
        Args:
            event_type: Type of system event
            data: Event data
        """
        event_data = {
            **data,
            "timestamp": datetime.now().isoformat(),
        }
        
        self.send_event(EventCategory.SYSTEM.value, f"system_{event_type}", event_data)
    
    def _process_messages(self) -> None:
        """Process outgoing messages from the queue."""
        while not self.shutdown_flag.is_set():
            try:
                # Get message with timeout to check shutdown flag periodically
                client_id, message = self.message_queue.get(timeout=0.5)
                
                # Check if we have a handler for this client
                handler = self.event_handlers.get("send_message")
                if handler and client_id in self.clients:
                    try:
                        # Use the handler to send the message
                        handler(client_id, message.to_json())
                    except Exception as e:
                        logger.error(f"Error sending message to client {client_id}: {e}")
                
                # Mark task as done
                self.message_queue.task_done()
                
            except queue.Empty:
                # Queue is empty, check shutdown flag again
                pass
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
    
    def get_client_count(self) -> int:
        """
        Get the number of connected clients.
        
        Returns:
            Number of clients
        """
        return len(self.clients)
    
    def get_subscription_stats(self) -> Dict[str, int]:
        """
        Get subscription statistics.
        
        Returns:
            Dictionary mapping categories to subscriber counts
        """
        return {category: len(clients) for category, clients in self.subscriptions.items()}
    
    def shutdown(self) -> None:
        """Shut down the WebSocket manager."""
        logger.info("Shutting down WebSocket manager")
        self.shutdown_flag.set()
        
        # Wait for message processor to finish
        if self.processor_thread.is_alive():
            self.processor_thread.join(timeout=5.0)


class WebSocketServer:
    """WebSocket server for MCP integration."""
    
    def __init__(self, backend_registry: Optional[Dict[str, Any]] = None):
        """
        Initialize the WebSocket server.
        
        Args:
            backend_registry: Optional dictionary mapping backend names to instances
        """
        self.backend_registry = backend_registry or {}
        
        # Create WebSocket manager
        self.ws_manager = WebSocketManager({
            "send_message": self._send_ws_message
        })
        
        # Client message handlers
        self.clients = {}
        
        # Register event handlers for backend operations
        for backend_name, backend in self.backend_registry.items():
            if hasattr(backend, "register_event_handler"):
                backend.register_event_handler(self._backend_event_handler)
    
    def _send_ws_message(self, client_id: str, message: str) -> None:
        """
        Send a WebSocket message to a client.
        
        Args:
            client_id: Client ID
            message: Message as JSON string
        """
        # This would be implemented by the web framework
        # For now, just log the message
        logger.debug(f"Would send to client {client_id}: {message}")
        
        # If we had an actual client connection, we would do something like:
        # self.clients[client_id].send(message)
    
    def _backend_event_handler(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Handle backend events.
        
        Args:
            event_type: Type of event
            event_data: Event data
        """
        # Parse event type to determine category and operation
        # Expected format: backend_name.operation (e.g., ipfs.add, s3.delete)
        if '.' in event_type:
            backend_name, operation = event_type.split('.', 1)
            
            # Get content ID if available
            content_id = event_data.get("content_id") or event_data.get("identifier")
            
            # Notify subscribers
            self.ws_manager.notify_backend_change(
                backend_name=backend_name,
                operation=operation,
                content_id=content_id,
                details=event_data
            )
    
    def register_client(self, client_id: Optional[str] = None, 
                       user_agent: Optional[str] = None,
                       remote_ip: Optional[str] = None) -> Dict[str, Any]:
        """
        Register a new WebSocket client.
        
        Args:
            client_id: Optional client ID (generated if not provided)
            user_agent: Optional user agent string
            remote_ip: Optional remote IP address
            
        Returns:
            Dictionary with client information
        """
        client = self.ws_manager.register_client(client_id, user_agent, remote_ip)
        return {"client_id": client.id, "connected_at": client.connected_at.isoformat()}
    
    def unregister_client(self, client_id: str) -> Dict[str, Any]:
        """
        Unregister a WebSocket client.
        
        Args:
            client_id: Client ID
            
        Returns:
            Dictionary with result
        """
        if client_id in self.ws_manager.clients:
            self.ws_manager.unregister_client(client_id)
            return {"success": True, "message": f"Client {client_id} unregistered"}
        else:
            return {"success": False, "error": f"Client {client_id} not found"}
    
    def handle_message(self, client_id: str, message: str) -> Dict[str, Any]:
        """
        Handle an incoming WebSocket message.
        
        Args:
            client_id: Client ID
            message: Message as JSON string
            
        Returns:
            Dictionary with result
        """
        if client_id not in self.ws_manager.clients:
            return {"success": False, "error": f"Client {client_id} not registered"}
        
        try:
            self.ws_manager.handle_message(client_id, message)
            return {"success": True}
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            return {"success": False, "error": str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get server status.
        
        Returns:
            Dictionary with status information
        """
        return {
            "clients": self.ws_manager.get_client_count(),
            "subscriptions": self.ws_manager.get_subscription_stats(),
            "timestamp": datetime.now().isoformat()
        }
    
    def notify_backend_change(self, backend_name: str, operation: str, 
                            content_id: Optional[str] = None, 
                            details: Optional[Dict[str, Any]] = None) -> None:
        """
        Notify subscribers of backend changes.
        
        Args:
            backend_name: Name of the backend
            operation: Operation performed (add, update, delete, etc.)
            content_id: Optional content identifier
            details: Optional additional details
        """
        self.ws_manager.notify_backend_change(backend_name, operation, content_id, details)
    
    def notify_migration_event(self, migration_id: str, status: str, 
                             source_backend: str, target_backend: str,
                             details: Optional[Dict[str, Any]] = None) -> None:
        """
        Notify subscribers of migration events.
        
        Args:
            migration_id: Migration identifier
            status: Migration status
            source_backend: Source backend name
            target_backend: Target backend name
            details: Optional additional details
        """
        self.ws_manager.notify_migration_event(migration_id, status, source_backend, target_backend, details)
    
    def notify_stream_progress(self, operation_id: str, progress: Dict[str, Any]) -> None:
        """
        Notify subscribers of streaming progress.
        
        Args:
            operation_id: Streaming operation identifier
            progress: Progress information
        """
        self.ws_manager.notify_stream_progress(operation_id, progress)
    
    def shutdown(self) -> None:
        """Shut down the WebSocket server."""
        self.ws_manager.shutdown()