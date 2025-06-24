"""
WebSocket streaming integration for MCP server.

This module implements real-time WebSocket connections for streaming
notifications, events, and content updates to clients.
"""

import os
import json
import time
import asyncio
import logging
import uuid
from typing import Dict, Any, List, Set, Optional, Callable, Union, Awaitable
from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, Depends, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import aiofiles

# Configure logging
logger = logging.getLogger(__name__)

# WebSocket connection manager for handling multiple connections
class ConnectionManager:
    """
    WebSocket connection manager.

    Manages active WebSocket connections, event subscriptions, and broadcasting messages.
    """

    def __init__(self):
        """Initialize the connection manager."""
        # Active connections
        self.active_connections: Dict[str, WebSocket] = {}

        # Subscription channels (channel_name -> set of connection IDs)
        self.subscriptions: Dict[str, Set[str]] = {}

        # Stats
        self.connection_count = 0
        self.message_count = 0
        self.start_time = time.time()

    async def connect(self, websocket: WebSocket, connection_id: Optional[str] = None) -> str:
        """
        Connect a WebSocket client.

        Args:
            websocket: The WebSocket connection
            connection_id: Optional connection ID (generated if not provided)

        Returns:
            The connection ID
        """
        await websocket.accept()

        # Generate connection ID if not provided
        if connection_id is None:
            connection_id = str(uuid.uuid4())

        # Store the connection
        self.active_connections[connection_id] = websocket
        self.connection_count += 1

        logger.info(f"WebSocket connected: {connection_id}")
        return connection_id

    def disconnect(self, connection_id: str) -> None:
        """
        Disconnect a WebSocket client.

        Args:
            connection_id: The connection ID to disconnect
        """
        # Remove from active connections
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            logger.info(f"WebSocket disconnected: {connection_id}")

        # Remove from all subscriptions
        for channel, subscribers in self.subscriptions.items():
            if connection_id in subscribers:
                subscribers.remove(connection_id)

    def subscribe(self, connection_id: str, channel: str) -> None:
        """
        Subscribe a connection to a channel.

        Args:
            connection_id: The connection ID to subscribe
            channel: The channel to subscribe to
        """
        if channel not in self.subscriptions:
            self.subscriptions[channel] = set()

        self.subscriptions[channel].add(connection_id)
        logger.debug(f"Connection {connection_id} subscribed to {channel}")

    def unsubscribe(self, connection_id: str, channel: str) -> None:
        """
        Unsubscribe a connection from a channel.

        Args:
            connection_id: The connection ID to unsubscribe
            channel: The channel to unsubscribe from
        """
        if channel in self.subscriptions and connection_id in self.subscriptions[channel]:
            self.subscriptions[channel].remove(connection_id)
            logger.debug(f"Connection {connection_id} unsubscribed from {channel}")

            # Clean up empty channels
            if not self.subscriptions[channel]:
                del self.subscriptions[channel]

    def unsubscribe_all(self, connection_id: str) -> List[str]:
        """
        Unsubscribe a connection from all channels.

        Args:
            connection_id: The connection ID to unsubscribe

        Returns:
            List of channels that were unsubscribed
        """
        unsubscribed = []

        for channel in list(self.subscriptions.keys()):
            if connection_id in self.subscriptions[channel]:
                self.subscriptions[channel].remove(connection_id)
                unsubscribed.append(channel)

                # Clean up empty channels
                if not self.subscriptions[channel]:
                    del self.subscriptions[channel]

        return unsubscribed

    async def broadcast(self, message: Any, channel: Optional[str] = None) -> int:
        """
        Broadcast a message to subscribers.

        Args:
            message: The message to broadcast
            channel: The channel to broadcast to (None for all connections)

        Returns:
            Number of clients the message was sent to
        """
        # Convert message to JSON if it's not already a string
        if not isinstance(message, str):
            message = json.dumps(message)

        sent_count = 0
        failed = []

        # If channel is specified, only send to subscribers
        if channel:
            if channel in self.subscriptions:
                for connection_id in self.subscriptions[channel]:
                    if connection_id in self.active_connections:
                        try:
                            await self.active_connections[connection_id].send_text(message)
                            sent_count += 1
                        except Exception as e:
                            logger.error(f"Error sending to {connection_id}: {e}")
                            failed.append(connection_id)
        # Otherwise send to all connections
        else:
            for connection_id, websocket in self.active_connections.items():
                try:
                    await websocket.send_text(message)
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Error sending to {connection_id}: {e}")
                    failed.append(connection_id)

        # Remove failed connections
        for connection_id in failed:
            self.disconnect(connection_id)

        self.message_count += 1
        return sent_count

    async def send_personal(self, connection_id: str, message: Any) -> bool:
        """
        Send a message to a specific client.

        Args:
            connection_id: The connection ID to send to
            message: The message to send

        Returns:
            True if the message was sent successfully
        """
        # Check if the connection exists
        if connection_id not in self.active_connections:
            return False

        # Convert message to JSON if it's not already a string
        if not isinstance(message, str):
            message = json.dumps(message)

        # Send the message
        try:
            await self.active_connections[connection_id].send_text(message)
            self.message_count += 1
            return True
        except Exception as e:
            logger.error(f"Error sending to {connection_id}: {e}")
            self.disconnect(connection_id)
            return False

    async def send_binary(self, connection_id: str, data: bytes) -> bool:
        """
        Send binary data to a specific client.

        Args:
            connection_id: The connection ID to send to
            data: The binary data to send

        Returns:
            True if the data was sent successfully
        """
        # Check if the connection exists
        if connection_id not in self.active_connections:
            return False

        # Send the data
        try:
            await self.active_connections[connection_id].send_bytes(data)
            self.message_count += 1
            return True
        except Exception as e:
            logger.error(f"Error sending binary to {connection_id}: {e}")
            self.disconnect(connection_id)
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get connection statistics.

        Returns:
            Dictionary with connection stats
        """
        uptime = time.time() - self.start_time

        return {
            "active_connections": len(self.active_connections),
            "total_connections": self.connection_count,
            "active_channels": len(self.subscriptions),
            "messages_sent": self.message_count,
            "uptime": uptime,
            "msg_per_second": self.message_count / uptime if uptime > 0 else 0
        }

    def get_channels(self) -> Dict[str, int]:
        """
        Get active channels and subscriber counts.

        Returns:
            Dictionary of channel names to subscriber counts
        """
        return {
            channel: len(subscribers)
            for channel, subscribers in self.subscriptions.items()
        }

# Event models
class EventData(BaseModel):
    """Base model for event data."""
    timestamp: float = None
    event_id: str = None

    def __init__(self, **data):
        """Initialize with default timestamp and event ID if not provided."""
        if 'timestamp' not in data:
            data['timestamp'] = time.time()
        if 'event_id' not in data:
            data['event_id'] = str(uuid.uuid4())
        super().__init__(**data)

class IPFSEvent(EventData):
    """IPFS-related event."""
    event_type: str
    cid: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class StorageEvent(EventData):
    """Storage backend event."""
    backend: str
    operation: str
    cid: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class WebSocketEvent(EventData):
    """WebSocket-related event."""
    type: str
    connection_id: str
    channel: Optional[str] = None
    data: Optional[Any] = None

# WebSocket service class
class WebSocketService:
    """
    WebSocket service for real-time communication.

    Manages WebSocket connections and provides methods for broadcasting events.
    """

    def __init__(self):
        """Initialize the WebSocket service."""
        self.manager = ConnectionManager()
        self.event_handlers: Dict[str, List[Callable[[Any], Awaitable[None]]]] = {}

    def register_event_handler(self, event_type: str, handler: Callable[[Any], Awaitable[None]]) -> None:
        """
        Register a handler for a specific event type.

        Args:
            event_type: The event type to handle
            handler: The handler function
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []

        self.event_handlers[event_type].append(handler)
        logger.debug(f"Registered handler for event type: {event_type}")

    async def handle_event(self, event_type: str, event_data: Any) -> None:
        """
        Handle an event by calling all registered handlers.

        Args:
            event_type: The event type
            event_data: The event data
        """
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    await handler(event_data)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}")

    async def broadcast_ipfs_event(self, event_type: str, cid: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Broadcast an IPFS-related event.

        Args:
            event_type: The IPFS event type
            cid: Optional content identifier
            details: Optional event details
        """
        event = IPFSEvent(
            event_type=event_type,
            cid=cid,
            details=details
        )

        # Broadcast to the specific event channel
        await self.manager.broadcast(event.dict(), f"ipfs:{event_type}")

        # Also broadcast to the general IPFS channel
        await self.manager.broadcast(event.dict(), "ipfs:all")

        # Call event handlers
        await self.handle_event(f"ipfs:{event_type}", event)

    async def broadcast_storage_event(self, backend: str, operation: str, cid: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Broadcast a storage backend event.

        Args:
            backend: The storage backend (e.g., 's3', 'filecoin')
            operation: The operation performed
            cid: Optional content identifier
            details: Optional event details
        """
        event = StorageEvent(
            backend=backend,
            operation=operation,
            cid=cid,
            details=details
        )

        # Broadcast to the specific backend channel
        await self.manager.broadcast(event.dict(), f"storage:{backend}")

        # Also broadcast to the general storage channel
        await self.manager.broadcast(event.dict(), "storage:all")

        # Call event handlers
        await self.handle_event(f"storage:{backend}:{operation}", event)

    async def broadcast_websocket_event(self, event_type: str, connection_id: str, channel: Optional[str] = None, data: Optional[Any] = None) -> None:
        """
        Broadcast a WebSocket-related event.

        Args:
            event_type: The WebSocket event type
            connection_id: The connection ID
            channel: Optional channel name
            data: Optional event data
        """
        event = WebSocketEvent(
            type=event_type,
            connection_id=connection_id,
            channel=channel,
            data=data
        )

        # Broadcast to admin channel only
        await self.manager.broadcast(event.dict(), "admin:websocket")

        # Call event handlers
        await self.handle_event(f"websocket:{event_type}", event)

    async def handle_connection(self, websocket: WebSocket) -> None:
        """
        Handle a WebSocket connection.

        Args:
            websocket: The WebSocket connection
        """
        connection_id = await self.manager.connect(websocket)

        try:
            # Send welcome message
            await self.manager.send_personal(connection_id, {
                "type": "welcome",
                "connection_id": connection_id,
                "timestamp": time.time()
            })

            # Notify admins
            await self.broadcast_websocket_event("connect", connection_id)

            # Handle messages
            while True:
                try:
                    # Wait for a message
                    message = await websocket.receive_text()

                    # Parse the message
                    try:
                        data = json.loads(message)

                        # Handle commands
                        if isinstance(data, dict) and "command" in data:
                            command = data["command"]

                            # Subscribe command
                            if command == "subscribe" and "channel" in data:
                                channel = data["channel"]
                                self.manager.subscribe(connection_id, channel)
                                await self.manager.send_personal(connection_id, {
                                    "type": "subscribed",
                                    "channel": channel,
                                    "timestamp": time.time()
                                })
                                await self.broadcast_websocket_event("subscribe", connection_id, channel=channel)

                            # Unsubscribe command
                            elif command == "unsubscribe" and "channel" in data:
                                channel = data["channel"]
                                self.manager.unsubscribe(connection_id, channel)
                                await self.manager.send_personal(connection_id, {
                                    "type": "unsubscribed",
                                    "channel": channel,
                                    "timestamp": time.time()
                                })
                                await self.broadcast_websocket_event("unsubscribe", connection_id, channel=channel)

                            # Unsubscribe all command
                            elif command == "unsubscribe_all":
                                channels = self.manager.unsubscribe_all(connection_id)
                                await self.manager.send_personal(connection_id, {
                                    "type": "unsubscribed_all",
                                    "channels": channels,
                                    "timestamp": time.time()
                                })
                                await self.broadcast_websocket_event("unsubscribe_all", connection_id)

                            # Echo command
                            elif command == "echo" and "data" in data:
                                echo_data = data["data"]
                                await self.manager.send_personal(connection_id, {
                                    "type": "echo",
                                    "data": echo_data,
                                    "timestamp": time.time()
                                })

                            # Ping command
                            elif command == "ping":
                                await self.manager.send_personal(connection_id, {
                                    "type": "pong",
                                    "timestamp": time.time()
                                })

                            # Unknown command
                            else:
                                await self.manager.send_personal(connection_id, {
                                    "type": "error",
                                    "error": "Unknown command",
                                    "command": command,
                                    "timestamp": time.time()
                                })
                        else:
                            await self.manager.send_personal(connection_id, {
                                "type": "error",
                                "error": "Invalid message format",
                                "timestamp": time.time()
                            })

                    except json.JSONDecodeError:
                        await self.manager.send_personal(connection_id, {
                            "type": "error",
                            "error": "Invalid JSON",
                            "timestamp": time.time()
                        })

                except WebSocketDisconnect:
                    break

        except Exception as e:
            logger.error(f"Error handling WebSocket connection {connection_id}: {e}")

        finally:
            # Clean up
            self.manager.disconnect(connection_id)
            await self.broadcast_websocket_event("disconnect", connection_id)

# Global WebSocket service instance
websocket_service = WebSocketService()

# Create FastAPI router for WebSocket endpoints
def create_websocket_router(api_prefix: str) -> APIRouter:
    """
    Create a FastAPI router for WebSocket endpoints.

    Args:
        api_prefix: API prefix for REST endpoints

    Returns:
        FastAPI router
    """
    router = APIRouter()

    # WebSocket connection endpoint
    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket connection endpoint."""
        await websocket_service.handle_connection(websocket)

    # Channel-specific WebSocket endpoint
    @router.websocket("/ws/{channel}")
    async def channel_websocket_endpoint(websocket: WebSocket, channel: str):
        """Channel-specific WebSocket endpoint."""
        connection_id = await websocket_service.manager.connect(websocket)

        try:
            # Subscribe to the specified channel
            websocket_service.manager.subscribe(connection_id, channel)

            # Send welcome message
            await websocket_service.manager.send_personal(connection_id, {
                "type": "welcome",
                "connection_id": connection_id,
                "channel": channel,
                "timestamp": time.time()
            })

            # Notify admins
            await websocket_service.broadcast_websocket_event("connect", connection_id, channel=channel)

            # Handle messages
            while True:
                try:
                    # Wait for a message
                    message = await websocket.receive_text()

                    # Parse the message
                    try:
                        data = json.loads(message)

                        # Handle commands
                        if isinstance(data, dict) and "command" in data:
                            command = data["command"]

                            # Echo command
                            if command == "echo" and "data" in data:
                                echo_data = data["data"]
                                await websocket_service.manager.send_personal(connection_id, {
                                    "type": "echo",
                                    "data": echo_data,
                                    "timestamp": time.time()
                                })

                            # Ping command
                            elif command == "ping":
                                await websocket_service.manager.send_personal(connection_id, {
                                    "type": "pong",
                                    "timestamp": time.time()
                                })

                            # Unknown command
                            else:
                                await websocket_service.manager.send_personal(connection_id, {
                                    "type": "error",
                                    "error": "Unknown command",
                                    "command": command,
                                    "timestamp": time.time()
                                })
                        else:
                            await websocket_service.manager.send_personal(connection_id, {
                                "type": "error",
                                "error": "Invalid message format",
                                "timestamp": time.time()
                            })

                    except json.JSONDecodeError:
                        await websocket_service.manager.send_personal(connection_id, {
                            "type": "error",
                            "error": "Invalid JSON",
                            "timestamp": time.time()
                        })

                except WebSocketDisconnect:
                    break

        except Exception as e:
            logger.error(f"Error handling WebSocket connection {connection_id} on channel {channel}: {e}")

        finally:
            # Clean up
            websocket_service.manager.disconnect(connection_id)
            await websocket_service.broadcast_websocket_event("disconnect", connection_id, channel=channel)

    # REST endpoints
    rest_router = APIRouter(prefix=f"{api_prefix}/realtime")

    @rest_router.get("/status")
    async def websocket_status():
        """Get WebSocket service status."""
        return {
            "success": True,
            "status": "available",
            "stats": websocket_service.manager.get_stats(),
            "channels": websocket_service.manager.get_channels()
        }

    @rest_router.post("/broadcast")
    async def broadcast_message(
        channel: str,
        message: Dict[str, Any],
        admin_key: Optional[str] = Header(None)
    ):
        """
        Broadcast a message to a channel.

        Args:
            channel: The channel to broadcast to
            message: The message to broadcast
            admin_key: Optional admin key for authentication
        """
        # TODO: Implement proper authentication
        if admin_key != "test_admin_key":
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Unauthorized"}
            )

        recipients = await websocket_service.manager.broadcast(message, channel)

        return {
            "success": True,
            "channel": channel,
            "recipients": recipients,
            "message_id": str(uuid.uuid4()),
            "timestamp": time.time()
        }

    @rest_router.post("/ipfs/event")
    async def trigger_ipfs_event(
        event_type: str,
        cid: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        admin_key: Optional[str] = Header(None)
    ):
        """
        Trigger an IPFS event.

        Args:
            event_type: The IPFS event type
            cid: Optional content identifier
            details: Optional event details
            admin_key: Optional admin key for authentication
        """
        # TODO: Implement proper authentication
        if admin_key != "test_admin_key":
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Unauthorized"}
            )

        await websocket_service.broadcast_ipfs_event(event_type, cid, details)

        return {
            "success": True,
            "event_type": event_type,
            "cid": cid,
            "timestamp": time.time()
        }

    @rest_router.post("/storage/event")
    async def trigger_storage_event(
        backend: str,
        operation: str,
        cid: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        admin_key: Optional[str] = Header(None)
    ):
        """
        Trigger a storage event.

        Args:
            backend: The storage backend
            operation: The operation performed
            cid: Optional content identifier
            details: Optional event details
            admin_key: Optional admin key for authentication
        """
        # TODO: Implement proper authentication
        if admin_key != "test_admin_key":
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Unauthorized"}
            )

        await websocket_service.broadcast_storage_event(backend, operation, cid, details)

        return {
            "success": True,
            "backend": backend,
            "operation": operation,
            "cid": cid,
            "timestamp": time.time()
        }

    return router, rest_router

# Function to get the WebSocket service instance
def get_websocket_service() -> WebSocketService:
    """
    Get the WebSocket service instance.

    Returns:
        The WebSocket service instance
    """
    return websocket_service
