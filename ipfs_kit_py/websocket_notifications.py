"""
WebSocket Notifications for IPFS Kit.

This module provides a real-time notification system for IPFS Kit using WebSockets.
It enables clients to subscribe to various event types and receive notifications
when those events occur, providing real-time visibility into IPFS operations.

Key features:
1. Event Subscriptions: Subscribe to specific event types
2. Filtered Notifications: Receive only events matching specific criteria
3. Multiple Channels: Different notification categories (content, peers, pins, etc.)
4. Lightweight Protocol: Simple JSON-based messaging protocol
5. Persistent Connections: Long-lived WebSocket connections for real-time updates
6. Broadcast Support: Send notifications to multiple clients
7. System Metrics: Real-time performance and health metrics
"""

import anyio
import json
import logging
import time
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Callable, Awaitable, Union

from fastapi import WebSocket, WebSocketDisconnect
# Handle WebSocketState import based on FastAPI/Starlette version
# In FastAPI < 0.100, WebSocketState was in fastapi module
# In FastAPI >= 0.100, WebSocketState moved to starlette.websockets
# See: https://github.com/tiangolo/fastapi/pull/9281
try:
    from fastapi import WebSocketState
except ImportError:
    try:
        # In newer FastAPI versions, WebSocketState is in starlette
        from starlette.websockets import WebSocketState
    except ImportError:
        # Fallback for when WebSocketState is not available
        # Create an enum to match the expected behavior
        from enum import Enum
        class WebSocketState(str, Enum):
            CONNECTING = "CONNECTING"
            CONNECTED = "CONNECTED"
            DISCONNECTED = "DISCONNECTED"

# Configure logging
logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Types of notifications that can be sent or subscribed to."""
    
    # Content-related events
    CONTENT_ADDED = "content_added"
    CONTENT_RETRIEVED = "content_retrieved"
    CONTENT_REMOVED = "content_removed"
    
    # Pin-related events
    PIN_ADDED = "pin_added"
    PIN_REMOVED = "pin_removed"
    PIN_PROGRESS = "pin_progress"
    PIN_STATUS_CHANGED = "pin_status_changed"
    
    # Peer-related events
    PEER_CONNECTED = "peer_connected"
    PEER_DISCONNECTED = "peer_disconnected"
    SWARM_CHANGED = "swarm_changed"
    
    # Cluster-related events
    CLUSTER_PEER_JOINED = "cluster_peer_joined"
    CLUSTER_PEER_LEFT = "cluster_peer_left"
    CLUSTER_STATE_CHANGED = "cluster_state_changed"
    CLUSTER_PIN_ADDED = "cluster_pin_added"
    CLUSTER_PIN_REMOVED = "cluster_pin_removed"
    
    # WebRTC streaming events
    WEBRTC_CONNECTION_CREATED = "webrtc_connection_created"
    WEBRTC_CONNECTION_ESTABLISHED = "webrtc_connection_established"
    WEBRTC_CONNECTION_CLOSED = "webrtc_connection_closed"
    WEBRTC_STREAM_STARTED = "webrtc_stream_started"
    WEBRTC_STREAM_ENDED = "webrtc_stream_ended"
    WEBRTC_QUALITY_CHANGED = "webrtc_quality_changed"
    WEBRTC_ERROR = "webrtc_error"
    
    # System events
    SYSTEM_METRICS = "system_metrics"
    SYSTEM_WARNING = "system_warning"
    SYSTEM_ERROR = "system_error"
    SYSTEM_INFO = "system_info"
    
    # Generic events
    CUSTOM_EVENT = "custom_event"
    ALL_EVENTS = "all_events"  # Special type to subscribe to all events


class NotificationManager:
    """Manages WebSocket subscriptions and notifications."""
    
    def __init__(self):
        """Initialize the notification manager."""
        # Maps connection ID to WebSocket and subscriptions
        self.active_connections: Dict[str, Dict[str, Any]] = {}
        
        # Maps notification types to sets of connection IDs
        self.subscriptions: Dict[str, Set[str]] = {}
        
        # Initialize subscription maps for all notification types
        for notification_type in NotificationType:
            self.subscriptions[notification_type.value] = set()
            
        # Event history for persistent notifications
        self.event_history: List[Dict[str, Any]] = []
        self.max_history_size = 1000
        
        # Metrics collection
        self.metrics = {
            "connections_total": 0,
            "active_connections": 0,
            "notifications_sent": 0,
            "subscriptions_by_type": {t.value: 0 for t in NotificationType}
        }
    
    async def connect(self, websocket: WebSocket, connection_id: str) -> bool:
        """
        Register a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            connection_id: Unique identifier for this connection
            
        Returns:
            bool: True if connection was successful
        """
        try:
            # Accept the connection
            await websocket.accept()
            
            # Register the connection
            self.active_connections[connection_id] = {
                "websocket": websocket,
                "subscriptions": set(),
                "filters": {},
                "connected_at": time.time(),
                "last_activity": time.time()
            }
            
            # Update metrics
            self.metrics["connections_total"] += 1
            self.metrics["active_connections"] = len(self.active_connections)
            
            logger.info(f"WebSocket client connected: {connection_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error accepting WebSocket connection: {e}")
            return False
    
    def disconnect(self, connection_id: str) -> None:
        """
        Unregister a WebSocket connection.
        
        Args:
            connection_id: ID of the connection to remove
        """
        if connection_id in self.active_connections:
            # Get current subscriptions
            current_subs = self.active_connections[connection_id]["subscriptions"]
            
            # Remove from subscription maps
            for sub_type in current_subs:
                if sub_type in self.subscriptions:
                    self.subscriptions[sub_type].discard(connection_id)
                    self.metrics["subscriptions_by_type"][sub_type] -= 1
            
            # Remove connection
            del self.active_connections[connection_id]
            
            # Update metrics
            self.metrics["active_connections"] = len(self.active_connections)
            
            logger.info(f"WebSocket client disconnected: {connection_id}")
    
    async def subscribe(self, connection_id: str, notification_types: List[str], 
                      filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Subscribe a connection to specific notification types.
        
        Args:
            connection_id: ID of the connection
            notification_types: List of notification types to subscribe to
            filters: Optional filters to apply to notifications
            
        Returns:
            Dict with subscription results
        """
        if connection_id not in self.active_connections:
            return {
                "success": False,
                "error": "Connection not registered",
                "subscribed_types": []
            }
        
        # Validate notification types
        valid_types = []
        invalid_types = []
        
        for n_type in notification_types:
            if n_type in [t.value for t in NotificationType]:
                valid_types.append(n_type)
            else:
                invalid_types.append(n_type)
        
        # Update connection's subscriptions
        connection = self.active_connections[connection_id]
        old_subs = connection["subscriptions"].copy()
        
        # Add new subscriptions
        for n_type in valid_types:
            if n_type not in connection["subscriptions"]:
                connection["subscriptions"].add(n_type)
                self.subscriptions[n_type].add(connection_id)
                self.metrics["subscriptions_by_type"][n_type] += 1
        
        # Special case: if ALL_EVENTS is subscribed, add all types
        if NotificationType.ALL_EVENTS.value in valid_types:
            for n_type in [t.value for t in NotificationType]:
                if n_type != NotificationType.ALL_EVENTS.value and n_type not in connection["subscriptions"]:
                    connection["subscriptions"].add(n_type)
                    self.subscriptions[n_type].add(connection_id)
                    self.metrics["subscriptions_by_type"][n_type] += 1
        
        # Update filters if provided
        if filters:
            connection["filters"] = filters
        
        # Update last activity timestamp
        connection["last_activity"] = time.time()
        
        # Send confirmation
        websocket = connection["websocket"]
        confirmation = {
            "type": "subscription_confirmed",
            "notification_types": list(connection["subscriptions"]),
            "filters": connection["filters"],
            "invalid_types": invalid_types,
            "timestamp": time.time()
        }
        
        try:
            await websocket.send_json(confirmation)
        except Exception as e:
            logger.error(f"Error sending subscription confirmation: {e}")
        
        return {
            "success": True,
            "subscribed_types": list(connection["subscriptions"]),
            "new_types": list(set(connection["subscriptions"]) - set(old_subs)),
            "invalid_types": invalid_types
        }
    
    async def unsubscribe(self, connection_id: str, notification_types: List[str]) -> Dict[str, Any]:
        """
        Unsubscribe a connection from specific notification types.
        
        Args:
            connection_id: ID of the connection
            notification_types: List of notification types to unsubscribe from
            
        Returns:
            Dict with unsubscription results
        """
        if connection_id not in self.active_connections:
            return {
                "success": False,
                "error": "Connection not registered"
            }
        
        # Update connection's subscriptions
        connection = self.active_connections[connection_id]
        
        # Remove specified subscriptions
        for n_type in notification_types:
            if n_type in connection["subscriptions"]:
                connection["subscriptions"].discard(n_type)
                if n_type in self.subscriptions:
                    self.subscriptions[n_type].discard(connection_id)
                    self.metrics["subscriptions_by_type"][n_type] -= 1
        
        # Special case: if ALL_EVENTS is unsubscribed, remove all types
        if NotificationType.ALL_EVENTS.value in notification_types:
            for n_type in list(connection["subscriptions"]):
                connection["subscriptions"].discard(n_type)
                if n_type in self.subscriptions:
                    self.subscriptions[n_type].discard(connection_id)
                    self.metrics["subscriptions_by_type"][n_type] -= 1
        
        # Update last activity timestamp
        connection["last_activity"] = time.time()
        
        # Send confirmation
        websocket = connection["websocket"]
        confirmation = {
            "type": "unsubscription_confirmed",
            "notification_types": list(connection["subscriptions"]),
            "timestamp": time.time()
        }
        
        try:
            await websocket.send_json(confirmation)
        except Exception as e:
            logger.error(f"Error sending unsubscription confirmation: {e}")
        
        return {
            "success": True,
            "remaining_subscriptions": list(connection["subscriptions"])
        }
    
    async def notify(self, notification_type: str, data: Dict[str, Any], 
                   source: Optional[str] = None) -> Dict[str, Any]:
        """
        Send a notification to all subscribed connections.
        
        Args:
            notification_type: Type of notification to send
            data: Notification data
            source: Optional source of the notification
            
        Returns:
            Dict with notification results
        """
        if notification_type not in self.subscriptions:
            return {
                "success": False,
                "error": f"Invalid notification type: {notification_type}",
                "recipients": 0
            }
        
        # Create notification message
        notification = {
            "type": "notification",
            "notification_type": notification_type,
            "data": data,
            "timestamp": time.time()
        }
        
        if source:
            notification["source"] = source
        
        # Add to history
        self.event_history.append(notification)
        if len(self.event_history) > self.max_history_size:
            self.event_history = self.event_history[-self.max_history_size:]
        
        # Get subscribed connections
        recipients = self.subscriptions[notification_type]
        sent_count = 0
        errors = []
        
        # Send to all subscribed connections
        for conn_id in recipients:
            if conn_id in self.active_connections:
                connection = self.active_connections[conn_id]
                websocket = connection["websocket"]
                
                # Check if this notification passes the connection's filters
                if not self._passes_filters(notification, connection["filters"]):
                    continue
                
                try:
                    # Check if WebSocket is still connected
                    if websocket.client_state != WebSocketState.DISCONNECTED:
                        await websocket.send_json(notification)
                        sent_count += 1
                        
                        # Update metrics
                        self.metrics["notifications_sent"] += 1
                        
                        # Update last activity timestamp
                        connection["last_activity"] = time.time()
                except Exception as e:
                    errors.append({
                        "connection_id": conn_id,
                        "error": str(e)
                    })
                    logger.error(f"Error sending notification to {conn_id}: {e}")
        
        return {
            "success": True,
            "notification_type": notification_type,
            "recipients_total": len(recipients),
            "recipients_sent": sent_count,
            "errors": errors
        }
    
    async def notify_all(self, notification_type: str, data: Dict[str, Any], 
                       source: Optional[str] = None) -> Dict[str, Any]:
        """
        Send a notification to all connected clients, regardless of subscription.
        
        Args:
            notification_type: Type of notification to send
            data: Notification data
            source: Optional source of the notification
            
        Returns:
            Dict with notification results
        """
        # Create notification message
        notification = {
            "type": "system_notification",  # Special type for system-wide notifications
            "notification_type": notification_type,
            "data": data,
            "timestamp": time.time()
        }
        
        if source:
            notification["source"] = source
        
        # Add to history
        self.event_history.append(notification)
        if len(self.event_history) > self.max_history_size:
            self.event_history = self.event_history[-self.max_history_size:]
        
        # Send to all connections
        sent_count = 0
        errors = []
        
        for conn_id, connection in self.active_connections.items():
            websocket = connection["websocket"]
            
            try:
                # Check if WebSocket is still connected
                if websocket.client_state != WebSocketState.DISCONNECTED:
                    await websocket.send_json(notification)
                    sent_count += 1
                    
                    # Update metrics
                    self.metrics["notifications_sent"] += 1
                    
                    # Update last activity timestamp
                    connection["last_activity"] = time.time()
            except Exception as e:
                errors.append({
                    "connection_id": conn_id,
                    "error": str(e)
                })
                logger.error(f"Error sending system notification to {conn_id}: {e}")
        
        return {
            "success": True,
            "notification_type": notification_type,
            "connections_total": len(self.active_connections),
            "recipients_sent": sent_count,
            "errors": errors
        }
    
    async def get_connection_info(self, connection_id: str) -> Dict[str, Any]:
        """
        Get information about a specific connection.
        
        Args:
            connection_id: ID of the connection
            
        Returns:
            Dict with connection information
        """
        if connection_id not in self.active_connections:
            return {
                "success": False,
                "error": "Connection not found"
            }
        
        connection = self.active_connections[connection_id]
        
        return {
            "success": True,
            "connection_id": connection_id,
            "subscriptions": list(connection["subscriptions"]),
            "filters": connection["filters"],
            "connected_at": connection["connected_at"],
            "last_activity": connection["last_activity"],
            "duration": time.time() - connection["connected_at"]
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current notification metrics.
        
        Returns:
            Dict with notification metrics
        """
        # Update active connections count
        self.metrics["active_connections"] = len(self.active_connections)
        
        # Add timestamp
        metrics = self.metrics.copy()
        metrics["timestamp"] = time.time()
        
        return metrics
    
    def _passes_filters(self, notification: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """
        Check if a notification passes the specified filters.
        
        Args:
            notification: The notification to check
            filters: The filters to apply
            
        Returns:
            True if the notification passes the filters, False otherwise
        """
        # If no filters, always pass
        if not filters:
            return True
        
        # Check each filter
        data = notification.get("data", {})
        
        for key, value in filters.items():
            # Handle nested keys with dot notation (e.g., "data.cid")
            if "." in key:
                parts = key.split(".")
                current = notification
                for part in parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        return False  # Key path doesn't exist
                
                # Compare the value
                if current != value:
                    return False
            
            # Direct key in data
            elif key in data and data[key] != value:
                return False
        
        # All filters passed
        return True


# Global notification manager instance
notification_manager = NotificationManager()


async def handle_notification_websocket(websocket: WebSocket, ipfs_api=None):
    """
    Handle a WebSocket connection for notifications.
    
    Args:
        websocket: The WebSocket connection
        ipfs_api: IPFS API instance (optional)
    """
    # Generate a unique connection ID
    connection_id = f"conn_{int(time.time() * 1000)}_{id(websocket)}"
    
    try:
        # Register connection
        success = await notification_manager.connect(websocket, connection_id)
        if not success:
            return
        
        # Send welcome message
        await websocket.send_json({
            "type": "welcome",
            "message": "Connected to IPFS notification service",
            "connection_id": connection_id,
            "available_notifications": [t.value for t in NotificationType],
            "timestamp": time.time()
        })
        
        # Process messages
        while True:
            message = await websocket.receive_json()
            
            # Process the message
            if "action" not in message:
                await websocket.send_json({
                    "type": "error",
                    "error": "Missing 'action' field",
                    "timestamp": time.time()
                })
                continue
            
            action = message["action"]
            
            if action == "subscribe":
                # Subscribe to notification types
                notification_types = message.get("notification_types", [])
                filters = message.get("filters")
                
                result = await notification_manager.subscribe(
                    connection_id, notification_types, filters
                )
                
                # Log subscriptions for debugging
                if result["success"]:
                    logger.debug(f"Client {connection_id} subscribed to: {result['subscribed_types']}")
            
            elif action == "unsubscribe":
                # Unsubscribe from notification types
                notification_types = message.get("notification_types", [])
                
                result = await notification_manager.unsubscribe(
                    connection_id, notification_types
                )
                
                # Log remaining subscriptions
                if result["success"]:
                    logger.debug(f"Client {connection_id} remaining subscriptions: {result['remaining_subscriptions']}")
            
            elif action == "get_history":
                # Get event history
                limit = message.get("limit", 100)
                notification_type = message.get("notification_type")
                
                # Filter history based on type if specified
                if notification_type:
                    history = [
                        event for event in notification_manager.event_history
                        if event.get("notification_type") == notification_type
                    ]
                else:
                    history = notification_manager.event_history
                
                # Apply limit
                history = history[-limit:]
                
                await websocket.send_json({
                    "type": "history",
                    "events": history,
                    "count": len(history),
                    "timestamp": time.time()
                })
            
            elif action == "ping":
                # Simple ping-pong for connection testing
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": time.time()
                })
            
            elif action == "get_metrics":
                # Get notification system metrics
                metrics = notification_manager.get_metrics()
                
                await websocket.send_json({
                    "type": "metrics",
                    "metrics": metrics,
                    "timestamp": time.time()
                })
            
            elif action == "get_info":
                # Get connection info
                info = await notification_manager.get_connection_info(connection_id)
                
                await websocket.send_json({
                    "type": "connection_info",
                    "info": info,
                    "timestamp": time.time()
                })
            
            else:
                # Unknown action
                await websocket.send_json({
                    "type": "error",
                    "error": f"Unknown action: {action}",
                    "timestamp": time.time()
                })
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"Error in notification WebSocket: {e}")
    finally:
        # Unregister connection
        notification_manager.disconnect(connection_id)


# Function to emit events from IPFS operations to WebSocket subscribers
async def emit_event(notification_type: str, data: Dict[str, Any], 
                   source: Optional[str] = None) -> None:
    """
    Emit an event to all subscribed WebSocket clients.
    
    This function should be called from various parts of the IPFS Kit
    when events occur that clients might be interested in.
    
    Args:
        notification_type: Type of notification (use NotificationType enum)
        data: Event data to include in the notification
        source: Optional source of the event
    """
    try:
        await notification_manager.notify(notification_type, data, source)
    except Exception as e:
        logger.error(f"Error emitting event: {e}")