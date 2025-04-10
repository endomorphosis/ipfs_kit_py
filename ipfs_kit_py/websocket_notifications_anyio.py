"""
WebSocket Notifications for IPFS Kit using anyio.

This module provides a real-time notification system for IPFS Kit using WebSockets,
implemented with anyio for backend-agnostic async operations. It enables clients to 
subscribe to various event types and receive notifications when those events occur,
providing real-time visibility into IPFS operations.

Key features:
1. Event Subscriptions: Subscribe to specific event types
2. Filtered Notifications: Receive only events matching specific criteria
3. Multiple Channels: Different notification categories (content, peers, pins, etc.)
4. Lightweight Protocol: Simple JSON-based messaging protocol
5. Persistent Connections: Long-lived WebSocket connections for real-time updates
6. Broadcast Support: Send notifications to multiple clients
7. System Metrics: Real-time performance and health metrics
8. Backend Agnostic: Works with asyncio, trio, or any other anyio-compatible backend
"""

import json
import logging
import time
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Callable, Awaitable, Union

# Import anyio instead of asyncio
import anyio
from anyio.abc import TaskGroup

# WebSocket imports - wrapped in try/except for graceful fallback
from fastapi import WebSocket, WebSocketDisconnect, FastAPI
# Handle WebSocketState import based on FastAPI/Starlette version
# In FastAPI < 0.100, WebSocketState was in fastapi module
# In FastAPI >= 0.100, WebSocketState moved to starlette.websockets
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
        
        # Task group for background tasks
        self.task_group = None
    
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
            # Accept the connection with timeout
            try:
                with anyio.fail_after(5.0):  # 5-second timeout
                    await websocket.accept()
            except anyio.TimeoutError:
                logger.error(f"Timeout accepting WebSocket connection: {connection_id}")
                return False
            
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
            # Send confirmation with timeout
            with anyio.fail_after(5.0):  # 5-second timeout
                await websocket.send_json(confirmation)
        except anyio.TimeoutError:
            logger.error(f"Timeout sending subscription confirmation to {connection_id}")
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
            # Send confirmation with timeout
            with anyio.fail_after(5.0):  # 5-second timeout
                await websocket.send_json(confirmation)
        except anyio.TimeoutError:
            logger.error(f"Timeout sending unsubscription confirmation to {connection_id}")
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
        
        # Create a list of send tasks
        send_tasks = []
        for conn_id in recipients:
            if conn_id in self.active_connections:
                connection = self.active_connections[conn_id]
                websocket = connection["websocket"]
                
                # Check if this notification passes the connection's filters
                if not self._passes_filters(notification, connection["filters"]):
                    continue
                
                # Check if WebSocket is still connected
                if websocket.client_state == WebSocketState.DISCONNECTED:
                    continue
                
                # Add send task
                send_tasks.append((conn_id, websocket, notification.copy()))
        
        # Use memory streams to collect results
        send_stream, receive_stream = anyio.create_memory_object_stream(len(send_tasks))
        
        # Function to send notification and report result
        async def send_notification(conn_id: str, websocket: WebSocket, notification: Dict[str, Any]):
            try:
                # Send with timeout
                with anyio.fail_after(5.0):  # 5-second timeout
                    await websocket.send_json(notification)
                
                # Update last activity timestamp
                if conn_id in self.active_connections:
                    self.active_connections[conn_id]["last_activity"] = time.time()
                
                # Report success
                await send_stream.send((conn_id, True, None))
            except Exception as e:
                # Report error
                await send_stream.send((conn_id, False, str(e)))
        
        # Send notifications concurrently
        async with anyio.create_task_group() as tg:
            # Start all send tasks
            for conn_id, websocket, notification in send_tasks:
                tg.start_soon(send_notification, conn_id, websocket, notification)
            
            # Close send stream when all tasks are done
            tg.start_soon(send_stream.aclose)
        
        # Collect results
        async with receive_stream:
            async for conn_id, success, error in receive_stream:
                if success:
                    sent_count += 1
                    
                    # Update metrics
                    self.metrics["notifications_sent"] += 1
                else:
                    errors.append({
                        "connection_id": conn_id,
                        "error": error
                    })
                    logger.error(f"Error sending notification to {conn_id}: {error}")
        
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
        
        # Use memory streams to collect results
        send_stream, receive_stream = anyio.create_memory_object_stream(len(self.active_connections))
        
        # Function to send notification and report result
        async def send_notification(conn_id: str, websocket: WebSocket, notification: Dict[str, Any]):
            try:
                # Check if WebSocket is still connected
                if websocket.client_state == WebSocketState.DISCONNECTED:
                    await send_stream.send((conn_id, False, "WebSocket disconnected"))
                    return
                
                # Send with timeout
                with anyio.fail_after(5.0):  # 5-second timeout
                    await websocket.send_json(notification)
                
                # Update last activity timestamp
                if conn_id in self.active_connections:
                    self.active_connections[conn_id]["last_activity"] = time.time()
                
                # Report success
                await send_stream.send((conn_id, True, None))
            except Exception as e:
                # Report error
                await send_stream.send((conn_id, False, str(e)))
        
        # Send notifications concurrently
        async with anyio.create_task_group() as tg:
            # Start all send tasks
            for conn_id, connection in self.active_connections.items():
                websocket = connection["websocket"]
                tg.start_soon(send_notification, conn_id, websocket, notification.copy())
            
            # Close send stream when all tasks are done
            tg.start_soon(send_stream.aclose)
        
        # Collect results
        sent_count = 0
        errors = []
        
        async with receive_stream:
            async for conn_id, success, error in receive_stream:
                if success:
                    sent_count += 1
                    
                    # Update metrics
                    self.metrics["notifications_sent"] += 1
                else:
                    errors.append({
                        "connection_id": conn_id,
                        "error": error
                    })
                    logger.error(f"Error sending system notification to {conn_id}: {error}")
        
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
    
    async def start_maintenance(self, inactive_timeout: float = 300.0, check_interval: float = 60.0):
        """
        Start background maintenance tasks.
        
        Args:
            inactive_timeout: Time in seconds after which inactive connections are closed
            check_interval: How often to check for inactive connections
        """
        self.task_group = anyio.create_task_group()
        
        # Define the maintenance task
        async def maintenance_task():
            while True:
                try:
                    # Check for inactive connections
                    now = time.time()
                    inactive_connections = []
                    
                    for conn_id, connection in self.active_connections.items():
                        inactive_time = now - connection["last_activity"]
                        if inactive_time > inactive_timeout:
                            inactive_connections.append(conn_id)
                    
                    # Close inactive connections
                    for conn_id in inactive_connections:
                        if conn_id in self.active_connections:
                            # Get the WebSocket
                            websocket = self.active_connections[conn_id]["websocket"]
                            
                            # Try to close it properly
                            try:
                                with anyio.fail_after(5.0):  # 5-second timeout
                                    await websocket.close(code=1000, reason="Inactivity timeout")
                            except Exception as e:
                                logger.error(f"Error closing inactive connection {conn_id}: {e}")
                            
                            # Disconnect it from the manager
                            self.disconnect(conn_id)
                            logger.info(f"Closed inactive connection: {conn_id}")
                    
                    # Wait until next check
                    await anyio.sleep(check_interval)
                    
                except anyio.get_cancelled_exc_class():
                    logger.debug("Maintenance task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in maintenance task: {e}")
                    # Wait a bit before retrying
                    await anyio.sleep(check_interval)
        
        # Start the maintenance task
        await self.task_group.__aenter__()
        self.task_group.start_soon(maintenance_task)
        logger.info("Started notification system maintenance tasks")
    
    async def stop_maintenance(self):
        """Stop background maintenance tasks."""
        if self.task_group:
            # Cancel and cleanup the task group
            try:
                await self.task_group.__aexit__(None, None, None)
                self.task_group = None
                logger.info("Stopped notification system maintenance tasks")
            except Exception as e:
                logger.error(f"Error stopping maintenance tasks: {e}")


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
        # Register connection with timeout handling
        try:
            with anyio.fail_after(5.0):  # 5-second timeout
                success = await notification_manager.connect(websocket, connection_id)
            
            # Return early if connection failed
            if not success:
                logger.error(f"Failed to register connection: {connection_id}")
                return
        except anyio.TimeoutError:
            logger.error(f"Timeout registering connection: {connection_id}")
            return
        
        # Send welcome message with timeout handling
        try:
            with anyio.fail_after(5.0):  # 5-second timeout
                await websocket.send_json({
                    "type": "welcome",
                    "message": "Connected to IPFS notification service",
                    "connection_id": connection_id,
                    "available_notifications": [t.value for t in NotificationType],
                    "timestamp": time.time()
                })
        except anyio.TimeoutError:
            logger.error(f"Timeout sending welcome message to: {connection_id}")
            notification_manager.disconnect(connection_id)
            return
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")
            notification_manager.disconnect(connection_id)
            return
        
        # Main connection management loop
        connection_active = True
        last_activity_time = time.time()
        ping_interval = 30  # Send ping every 30 seconds of inactivity
        
        while connection_active:
            try:
                # Calculate time until next ping
                time_since_activity = time.time() - last_activity_time
                timeout = max(1.0, ping_interval - time_since_activity)
                
                # Wait for message with timeout
                with anyio.fail_after(timeout):
                    # Receive JSON message with proper error handling
                    try:
                        message = await websocket.receive_json()
                        
                        # Update activity time
                        last_activity_time = time.time()
                        
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
                            
                            # Send history with timeout
                            with anyio.fail_after(10.0):  # 10-second timeout for potentially large response
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
                        logger.info(f"WebSocket disconnect during receive: {connection_id}")
                        connection_active = False
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON from client: {connection_id}")
                        await websocket.send_json({
                            "type": "error",
                            "error": "Invalid JSON message",
                            "timestamp": time.time()
                        })
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        # Only close on serious errors
                        if "connection" in str(e).lower() or "closed" in str(e).lower():
                            connection_active = False
            
            except anyio.TimeoutError:
                # No message received within timeout - send a ping
                time_since_activity = time.time() - last_activity_time
                
                if time_since_activity >= ping_interval:
                    try:
                        # Check if the connection is still active
                        if websocket.client_state == WebSocketState.DISCONNECTED:
                            logger.debug(f"WebSocket no longer connected: {connection_id}")
                            connection_active = False
                            break
                        
                        # Send ping with timeout
                        with anyio.fail_after(5.0):  # 5-second ping timeout
                            await websocket.send_json({
                                "type": "heartbeat",
                                "timestamp": time.time()
                            })
                            # Update activity time after successful ping
                            last_activity_time = time.time()
                    except Exception as e:
                        # Any error during ping means the connection is probably dead
                        logger.info(f"Error sending ping, closing connection {connection_id}: {e}")
                        connection_active = False
            
            except Exception as e:
                logger.error(f"Unexpected error in WebSocket handler: {e}")
                connection_active = False
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected normally: {connection_id}")
    except Exception as e:
        logger.error(f"Error in notification WebSocket: {e}")
    finally:
        # Always clean up the connection
        notification_manager.disconnect(connection_id)
        
        # Ensure socket is closed
        try:
            if (hasattr(websocket, 'client_state') and 
                websocket.client_state != WebSocketState.DISCONNECTED):
                with anyio.fail_after(2.0):  # 2-second close timeout
                    await websocket.close(code=1000, reason="Connection complete")
        except Exception as e:
            logger.debug(f"Error during WebSocket cleanup: {e}")


# Function to emit events from IPFS operations to WebSocket subscribers
async def emit_event(notification_type: str, data: Dict[str, Any], 
                   source: Optional[str] = None) -> Dict[str, Any]:
    """
    Emit an event to all subscribed WebSocket clients.
    
    This function should be called from various parts of the IPFS Kit
    when events occur that clients might be interested in.
    
    Args:
        notification_type: Type of notification (use NotificationType enum)
        data: Event data to include in the notification
        source: Optional source of the event
        
    Returns:
        Dict with notification results
    """
    try:
        return await notification_manager.notify(notification_type, data, source)
    except Exception as e:
        logger.error(f"Error emitting event: {e}")
        return {
            "success": False,
            "error": str(e),
            "notification_type": notification_type
        }


# Function to integrate with FastAPI
def register_notification_websocket(app: FastAPI, path: str = "/api/v0/notifications/ws"):
    """
    Register notification WebSocket endpoint with FastAPI.
    
    Args:
        app: FastAPI application
        path: WebSocket endpoint path
        
    Returns:
        True if registration was successful
    """
    try:
        # Define WebSocket endpoint
        @app.websocket(path)
        async def notifications_websocket(websocket: WebSocket):
            await handle_notification_websocket(websocket)
        
        # Add startup event to start maintenance tasks
        @app.on_event("startup")
        async def start_notification_maintenance():
            await notification_manager.start_maintenance()
        
        # Add shutdown event to stop maintenance tasks
        @app.on_event("shutdown")
        async def stop_notification_maintenance():
            await notification_manager.stop_maintenance()
        
        logger.info(f"Registered notification WebSocket endpoint at {path}")
        return True
    except Exception as e:
        logger.error(f"Failed to register notification WebSocket: {e}")
        return False


# Example client-side code for documentation
WEBSOCKET_CLIENT_EXAMPLE = """
// Example client-side JavaScript for WebSocket notifications

class NotificationClient {
  constructor(url = "ws://localhost:8000/api/v0/notifications/ws") {
    this.url = url;
    this.socket = null;
    this.connected = false;
    this.handlers = {};
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
  }

  connect() {
    return new Promise((resolve, reject) => {
      try {
        this.socket = new WebSocket(this.url);

        this.socket.onopen = () => {
          console.log("WebSocket connected");
          this.connected = true;
          this.reconnectAttempts = 0;
          resolve();
        };

        this.socket.onmessage = (event) => {
          const message = JSON.parse(event.data);
          this.handleMessage(message);
        };

        this.socket.onerror = (error) => {
          console.error("WebSocket error:", error);
          reject(error);
        };

        this.socket.onclose = (event) => {
          console.log(`WebSocket closed: ${event.code} - ${event.reason}`);
          this.connected = false;
          
          // Try to reconnect
          if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.pow(2, this.reconnectAttempts) * 1000; // Exponential backoff
            console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
            
            setTimeout(() => {
              this.connect().catch(err => console.error("Reconnect failed:", err));
            }, delay);
          }
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  handleMessage(message) {
    const { type } = message;

    switch (type) {
      case "welcome":
        console.log(`Connected to notification service: ${message.connection_id}`);
        // Subscribe to desired notification types
        this.subscribe(["content_added", "system_info"]);
        break;

      case "notification":
        const { notification_type, data } = message;
        // Call handler for this notification type if registered
        if (this.handlers[notification_type]) {
          this.handlers[notification_type](data);
        }
        // Call generic notification handler if registered
        if (this.handlers["all"]) {
          this.handlers["all"](notification_type, data);
        }
        break;

      case "subscription_confirmed":
        console.log(`Subscribed to: ${message.notification_types.join(", ")}`);
        break;

      case "heartbeat":
        // Send ping response
        this.ping();
        break;

      case "error":
        console.error(`Server error: ${message.error}`);
        break;
    }
  }

  subscribe(notificationTypes, filters = {}) {
    if (!this.connected) return;

    this.socket.send(JSON.stringify({
      action: "subscribe",
      notification_types: notificationTypes,
      filters: filters,
      timestamp: Date.now() / 1000
    }));
  }

  unsubscribe(notificationTypes) {
    if (!this.connected) return;

    this.socket.send(JSON.stringify({
      action: "unsubscribe",
      notification_types: notificationTypes,
      timestamp: Date.now() / 1000
    }));
  }

  ping() {
    if (!this.connected) return;

    this.socket.send(JSON.stringify({
      action: "ping",
      timestamp: Date.now() / 1000
    }));
  }

  getHistory(limit = 100, notificationType = null) {
    if (!this.connected) return;

    this.socket.send(JSON.stringify({
      action: "get_history",
      limit: limit,
      notification_type: notificationType,
      timestamp: Date.now() / 1000
    }));
  }

  getMetrics() {
    if (!this.connected) return;

    this.socket.send(JSON.stringify({
      action: "get_metrics",
      timestamp: Date.now() / 1000
    }));
  }

  disconnect() {
    if (this.socket) {
      this.socket.close();
      this.connected = false;
    }
  }

  // Register a handler for a specific notification type
  on(notificationType, handler) {
    this.handlers[notificationType] = handler;
  }

  // Remove a handler
  off(notificationType) {
    delete this.handlers[notificationType];
  }
}

// Usage example:
// const client = new NotificationClient();
//
// client.on("content_added", (data) => {
//   console.log(`New content added: ${data.cid}`);
// });
//
// client.on("all", (type, data) => {
//   console.log(`Received notification type: ${type}`);
// });
//
// client.connect().then(() => {
//   console.log("Connected to notification service");
// });
"""

# Utility function to run a simple example
async def run_example():
    """Run a simple example of the notification WebSocket system."""
    print("Running notification WebSocket example...")
    
    # Mock WebSocket for local testing
    class MockWebSocket:
        def __init__(self):
            self.client_state = WebSocketState.CONNECTED
            self.sent_messages = []
            self.client = None
            
        async def accept(self):
            print("WebSocket connection accepted")
            
        async def send_json(self, data):
            self.sent_messages.append(data)
            print(f"Sent: {data['type']}")
            
        async def close(self, code=1000, reason=""):
            self.client_state = WebSocketState.DISCONNECTED
            print(f"WebSocket closed: {code} - {reason}")
    
    # Create mock WebSocket
    websocket = MockWebSocket()
    
    # Handle WebSocket connection
    connection_task = handle_notification_websocket(websocket)
    
    # Wait a bit
    await anyio.sleep(1)
    
    # Simulate receiving a subscription message
    websocket.receive_json = lambda: {
        "action": "subscribe",
        "notification_types": [
            NotificationType.CONTENT_ADDED.value,
            NotificationType.SYSTEM_INFO.value
        ]
    }
    
    # Wait for processing
    await anyio.sleep(1)
    
    # Emit a test event
    await emit_event(
        NotificationType.CONTENT_ADDED.value,
        {"cid": "QmTest123", "size": 1024},
        "test_source"
    )
    
    # Wait for notification to be processed
    await anyio.sleep(1)
    
    # Print received messages
    print("\nReceived messages:")
    for i, msg in enumerate(websocket.sent_messages):
        print(f"{i+1}. {msg['type']}")
    
    # Clean up
    websocket.client_state = WebSocketState.DISCONNECTED
    
    print("Example completed")


if __name__ == "__main__":
    anyio.run(run_example)