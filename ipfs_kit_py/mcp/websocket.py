"""
MCP WebSocket Module for real-time communication.

This module provides WebSocket-like capabilities for the MCP server via JSON-RPC polling,
enabling:
1. Event notifications
2. Subscription-based updates
3. Bidirectional communication
4. Automatic connection recovery

Note: This module has been refactored to use JSON-RPC instead of WebSocket connections.
"""

import json
import time
import logging
import anyio
import threading
import uuid
import queue
from enum import Enum
from typing import Dict, Any, List, Set, Optional, Callable, Union
from datetime import datetime
from dataclasses import dataclass, field

try:
    import anyio
    ANYIO_AVAILABLE = True
except ImportError:
    ANYIO_AVAILABLE = False

# Import the JSON-RPC event manager
from .jsonrpc_event_manager import get_jsonrpc_event_manager, EventCategory

# Configure logger
logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of WebSocket messages (maintained for compatibility)."""
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


class WebSocketManager:
    """
    WebSocket-compatible manager that uses JSON-RPC event system.
    
    This class maintains the same interface as the original WebSocket manager
    but delegates to the JSON-RPC event manager for actual functionality.
    """
    
    def __init__(self, event_handlers: Optional[Dict[str, Callable]] = None):
        """
        Initialize WebSocket manager.
        
        Args:
            event_handlers: Optional dictionary mapping event types to handler functions
        """
        self.event_handlers = event_handlers or {}
        self.jsonrpc_event_manager = get_jsonrpc_event_manager()
        
        logger.info("WebSocket manager initialized with JSON-RPC backend")
    
    def register_client(self, client_id: Optional[str] = None, 
                       user_agent: Optional[str] = None,
                       remote_ip: Optional[str] = None) -> 'WSClient':
        """
        Register a new WebSocket client.
        
        Args:
            client_id: Optional client ID (generated if not provided)
            user_agent: Optional user agent string
            remote_ip: Optional remote IP address
            
        Returns:
            WSClient instance
        """
        session_id = self.jsonrpc_event_manager.create_session(client_id)
        
        # Create a WSClient-compatible object
        client = WSClient(
            id=session_id,
            user_agent=user_agent,
            remote_ip=remote_ip
        )
        
        return client
    
    def unregister_client(self, client_id: str) -> None:
        """
        Unregister a WebSocket client.
        
        Args:
            client_id: Client ID
        """
        self.jsonrpc_event_manager.destroy_session(client_id)
    
    def handle_message(self, client_id: str, message_json: str) -> None:
        """
        Handle an incoming WebSocket message.
        
        Args:
            client_id: Client ID
            message_json: Message as JSON string
        """
        try:
            data = json.loads(message_json)
            msg_type = data.get("type")
            
            if msg_type == "subscribe":
                categories = data.get("categories", data.get("category", []))
                self.jsonrpc_event_manager.subscribe(client_id, categories)
            
            elif msg_type == "unsubscribe":
                categories = data.get("categories", data.get("category"))
                self.jsonrpc_event_manager.unsubscribe(client_id, categories)
            
            elif msg_type == "ping":
                # Handle ping - could trigger activity update
                if client_id in self.jsonrpc_event_manager.sessions:
                    self.jsonrpc_event_manager.sessions[client_id].update_activity()
            
        except Exception as e:
            logger.error(f"Error handling message from {client_id}: {e}")
    
    def send_event(self, category: str, event_type: str, data: Dict[str, Any]) -> None:
        """
        Send an event to all subscribed clients.
        
        Args:
            category: Event category
            event_type: Type of event
            data: Event data
        """
        # Add event via JSON-RPC event manager
        if category == EventCategory.BACKEND.value:
            self.jsonrpc_event_manager.notify_backend_change(
                backend_name=data.get("backend", "unknown"),
                operation=data.get("operation", event_type),
                content_id=data.get("content_id"),
                details=data
            )
        elif category == EventCategory.MIGRATION.value:
            self.jsonrpc_event_manager.notify_migration_event(
                migration_id=data.get("migration_id", "unknown"),
                status=data.get("status", event_type),
                source_backend=data.get("source_backend", "unknown"),
                target_backend=data.get("target_backend", "unknown"),
                details=data
            )
        elif category == EventCategory.STREAMING.value:
            self.jsonrpc_event_manager.notify_stream_progress(
                operation_id=data.get("operation_id", "unknown"),
                progress=data
            )
        elif category == EventCategory.SEARCH.value:
            self.jsonrpc_event_manager.notify_search_event(event_type, data)
        else:
            self.jsonrpc_event_manager.notify_system_event(event_type, data)
    
    def broadcast(self, message_type: MessageType, data: Dict[str, Any]) -> None:
        """
        Broadcast a message to all connected clients.
        
        Args:
            message_type: Type of message
            data: Message data
        """
        # Convert to system event
        self.jsonrpc_event_manager.notify_system_event(message_type.value, data)
    
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
        # In JSON-RPC mode, we can't send directly to a client
        # But we can add an event that they'll get when they poll
        self.jsonrpc_event_manager.notify_system_event(
            f"client_message_{message_type.value}",
            {**data, "target_client": client_id}
        )
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
        self.jsonrpc_event_manager.notify_backend_change(backend_name, operation, content_id, details)
    
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
        self.jsonrpc_event_manager.notify_migration_event(migration_id, status, source_backend, target_backend, details)
    
    def notify_stream_progress(self, operation_id: str, progress: Dict[str, Any]) -> None:
        """
        Notify subscribers of streaming progress.
        
        Args:
            operation_id: Streaming operation identifier
            progress: Progress information
        """
        self.jsonrpc_event_manager.notify_stream_progress(operation_id, progress)
    
    def notify_search_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Notify subscribers of search events.
        
        Args:
            event_type: Type of search event
            data: Event data
        """
        self.jsonrpc_event_manager.notify_search_event(event_type, data)
    
    def notify_system_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Notify subscribers of system events.
        
        Args:
            event_type: Type of system event
            data: Event data
        """
        self.jsonrpc_event_manager.notify_system_event(event_type, data)
    
    def get_client_count(self) -> int:
        """
        Get the number of connected clients.
        
        Returns:
            Number of clients
        """
        return len(self.jsonrpc_event_manager.sessions)
    
    def get_subscription_stats(self) -> Dict[str, int]:
        """
        Get subscription statistics.
        
        Returns:
            Dictionary mapping categories to subscriber counts
        """
        stats = self.jsonrpc_event_manager.get_server_stats()
        return stats.get("categories", {})
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get WebSocket manager statistics.
        
        Returns:
            Statistics dictionary
        """
        return self.jsonrpc_event_manager.get_server_stats()
    
    def shutdown(self) -> None:
        """Shut down the WebSocket manager."""
        logger.info("Shutting down WebSocket manager (JSON-RPC backend)")
        # The JSON-RPC event manager handles its own cleanup


@dataclass
class WSClient:
    """Information about a connected WebSocket client (compatibility class)."""
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
    """WebSocket message (compatibility class)."""
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


class WebSocketServer:
    """WebSocket server for MCP integration (now using JSON-RPC backend)."""
    
    def __init__(self, backend_registry: Optional[Dict[str, Any]] = None):
        """
        Initialize the WebSocket server.
        
        Args:
            backend_registry: Optional dictionary mapping backend names to instances
        """
        self.backend_registry = backend_registry or {}
        
        # Create WebSocket manager (which now uses JSON-RPC)
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
        # In JSON-RPC mode, this is handled by the event polling mechanism
        logger.debug(f"Would send to client {client_id}: {message}")
    
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