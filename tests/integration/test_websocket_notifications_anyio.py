"""
Tests for the anyio-based WebSocket notification system.

These tests verify the anyio implementation of the WebSocket notification system
works correctly and maintains the same functionality as the async-io version while 
providing the benefits of anyio's backend flexibility.
"""

import json
import time
from typing import Dict, Any, List

import pytest
import anyio
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect

from ipfs_kit_py.websocket_notifications_anyio import (
    NotificationType, 
    NotificationManager,
    handle_notification_websocket,
    register_notification_websocket,
    emit_event
)

# Mark all tests in this module as anyio tests
pytestmark = pytest.mark.anyio

# Mock WebSocket class for testing
class MockWebSocket:
    """Mock WebSocket for testing the notification system."""
    
    def __init__(self):
        self.client_state = "CONNECTED"
        self.sent_messages = []
        self.client = None
        self.closed = False
        self.close_code = None
        self.close_reason = None
        self._receive_queue = []
        
    async def accept(self):
        """Accept the connection."""
        return True
        
    async def send_json(self, data: Dict[str, Any]):
        """Send a JSON message."""
        self.sent_messages.append(data)
        return True
        
    async def close(self, code=1000, reason=""):
        """Close the connection."""
        self.closed = True
        self.close_code = code
        self.close_reason = reason
        self.client_state = "DISCONNECTED"
    
    async def receive_json(self):
        """Receive a JSON message."""
        if not self._receive_queue:
            raise WebSocketDisconnect()
        return self._receive_queue.pop(0)
    
    def add_receive_message(self, message: Dict[str, Any]):
        """Add a message to the receive queue."""
        self._receive_queue.append(message)
    
    def get_sent_message(self, message_type: str) -> Dict[str, Any]:
        """Get a sent message by type."""
        for message in self.sent_messages:
            if message.get("type") == message_type:
                return message
        return None


@pytest.fixture
async def notification_manager():
    """Create a notification manager instance for testing."""
    manager = NotificationManager()
    yield manager


@pytest.fixture
async def mock_websocket():
    """Create a mock WebSocket instance for testing."""
    websocket = MockWebSocket()
    yield websocket


@pytest.fixture
async def connected_websocket(notification_manager, mock_websocket):
    """Create a connected mock WebSocket instance for testing."""
    connection_id = f"test_conn_{int(time.time())}"
    success = await notification_manager.connect(mock_websocket, connection_id)
    assert success is True
    yield mock_websocket, connection_id


async def test_notification_manager_init(notification_manager):
    """Test initialization of the notification manager."""
    # Check that subscription maps are initialized for all notification types
    for notification_type in NotificationType:
        assert notification_type.value in notification_manager.subscriptions
        assert isinstance(notification_manager.subscriptions[notification_type.value], set)
    
    # Check that metrics are initialized correctly
    assert notification_manager.metrics["connections_total"] == 0
    assert notification_manager.metrics["active_connections"] == 0
    assert notification_manager.metrics["notifications_sent"] == 0
    assert len(notification_manager.metrics["subscriptions_by_type"]) == len(NotificationType)


async def test_connect_and_disconnect(notification_manager, mock_websocket):
    """Test connecting and disconnecting a WebSocket client."""
    # Connect
    connection_id = "test_connection"
    success = await notification_manager.connect(mock_websocket, connection_id)
    assert success is True
    assert connection_id in notification_manager.active_connections
    assert notification_manager.metrics["connections_total"] == 1
    assert notification_manager.metrics["active_connections"] == 1
    
    # Disconnect
    notification_manager.disconnect(connection_id)
    assert connection_id not in notification_manager.active_connections
    assert notification_manager.metrics["active_connections"] == 0


async def test_subscribe_and_unsubscribe(notification_manager, connected_websocket):
    """Test subscribing and unsubscribing to notification types."""
    mock_websocket, connection_id = connected_websocket
    
    # Subscribe to some notification types
    notification_types = [
        NotificationType.CONTENT_ADDED.value,
        NotificationType.SYSTEM_INFO.value
    ]
    
    result = await notification_manager.subscribe(connection_id, notification_types)
    assert result["success"] is True
    assert set(result["subscribed_types"]) == set(notification_types)
    
    # Check that the connection is in the subscription maps
    for notification_type in notification_types:
        assert connection_id in notification_manager.subscriptions[notification_type]
    
    # Verify confirmation was sent
    confirmation = mock_websocket.get_sent_message("subscription_confirmed")
    assert confirmation is not None
    assert set(confirmation["notification_types"]) == set(notification_types)
    
    # Unsubscribe from one type
    result = await notification_manager.unsubscribe(connection_id, [NotificationType.CONTENT_ADDED.value])
    assert result["success"] is True
    assert NotificationType.SYSTEM_INFO.value in result["remaining_subscriptions"]
    assert NotificationType.CONTENT_ADDED.value not in result["remaining_subscriptions"]
    
    # Check that subscription maps are updated correctly
    assert connection_id not in notification_manager.subscriptions[NotificationType.CONTENT_ADDED.value]
    assert connection_id in notification_manager.subscriptions[NotificationType.SYSTEM_INFO.value]
    
    # Verify confirmation was sent
    confirmation = mock_websocket.get_sent_message("unsubscription_confirmed")
    assert confirmation is not None
    assert NotificationType.SYSTEM_INFO.value in confirmation["notification_types"]
    assert NotificationType.CONTENT_ADDED.value not in confirmation["notification_types"]


async def test_subscribe_all_events(notification_manager, connected_websocket):
    """Test subscribing to ALL_EVENTS notification type."""
    mock_websocket, connection_id = connected_websocket
    
    # Subscribe to ALL_EVENTS
    notification_types = [NotificationType.ALL_EVENTS.value]
    
    result = await notification_manager.subscribe(connection_id, notification_types)
    assert result["success"] is True
    
    # Check that the connection is in all subscription maps
    for notification_type in NotificationType:
        if notification_type != NotificationType.ALL_EVENTS:
            assert connection_id in notification_manager.subscriptions[notification_type.value]


async def test_notify(notification_manager, connected_websocket):
    """Test sending notifications to subscribed clients."""
    mock_websocket, connection_id = connected_websocket
    
    # Subscribe to a notification type
    notification_type = NotificationType.CONTENT_ADDED.value
    await notification_manager.subscribe(connection_id, [notification_type])
    
    # Clear sent messages
    mock_websocket.sent_messages = []
    
    # Send a notification
    data = {"cid": "QmTest123", "size": 1024}
    source = "test_source"
    
    result = await notification_manager.notify(notification_type, data, source)
    assert result["success"] is True
    assert result["recipients_sent"] == 1
    assert result["notification_type"] == notification_type
    
    # Check that the notification was sent to the client
    assert len(mock_websocket.sent_messages) == 1
    notification = mock_websocket.sent_messages[0]
    assert notification["type"] == "notification"
    assert notification["notification_type"] == notification_type
    assert notification["data"] == data
    assert notification["source"] == source
    
    # Check that the metrics were updated
    assert notification_manager.metrics["notifications_sent"] == 1
    
    # Check that the notification was added to history
    assert len(notification_manager.event_history) == 1
    assert notification_manager.event_history[0]["notification_type"] == notification_type


async def test_notify_with_filters(notification_manager, connected_websocket):
    """Test that notifications respect filters."""
    mock_websocket, connection_id = connected_websocket
    
    # Subscribe to a notification type with a filter
    notification_type = NotificationType.CONTENT_ADDED.value
    filters = {"cid": "QmFilterMatch"}
    
    await notification_manager.subscribe(connection_id, [notification_type], filters)
    
    # Clear sent messages
    mock_websocket.sent_messages = []
    
    # Send a notification that matches the filter
    data_matching = {"cid": "QmFilterMatch", "size": 1024}
    result = await notification_manager.notify(notification_type, data_matching)
    assert result["success"] is True
    assert result["recipients_sent"] == 1
    
    # Send a notification that doesn't match the filter
    mock_websocket.sent_messages = []  # Clear messages again
    data_non_matching = {"cid": "QmFilterNoMatch", "size": 1024}
    result = await notification_manager.notify(notification_type, data_non_matching)
    assert result["success"] is True
    assert result["recipients_sent"] == 0  # Should not be sent due to filter


async def test_notify_all(notification_manager, connected_websocket):
    """Test sending notifications to all clients regardless of subscription."""
    mock_websocket, connection_id = connected_websocket
    
    # Don't subscribe to anything
    
    # Clear sent messages
    mock_websocket.sent_messages = []
    
    # Send a notification to all clients
    notification_type = NotificationType.SYSTEM_WARNING.value
    data = {"message": "System maintenance starting soon"}
    
    result = await notification_manager.notify_all(notification_type, data)
    assert result["success"] is True
    assert result["recipients_sent"] == 1
    
    # Check that the notification was sent to the client
    assert len(mock_websocket.sent_messages) == 1
    notification = mock_websocket.sent_messages[0]
    assert notification["type"] == "system_notification"
    assert notification["notification_type"] == notification_type
    assert notification["data"] == data


async def test_get_connection_info(notification_manager, connected_websocket):
    """Test getting information about a connection."""
    mock_websocket, connection_id = connected_websocket
    
    # Subscribe to some notification types
    notification_types = [NotificationType.CONTENT_ADDED.value]
    filters = {"size": 1024}
    await notification_manager.subscribe(connection_id, notification_types, filters)
    
    # Get connection info
    info = await notification_manager.get_connection_info(connection_id)
    assert info["success"] is True
    assert info["connection_id"] == connection_id
    assert NotificationType.CONTENT_ADDED.value in info["subscriptions"]
    assert info["filters"] == filters
    assert "connected_at" in info
    assert "last_activity" in info
    assert "duration" in info


async def test_get_metrics(notification_manager, connected_websocket):
    """Test getting notification system metrics."""
    mock_websocket, connection_id = connected_websocket
    
    # Subscribe to a notification type
    notification_type = NotificationType.CONTENT_ADDED.value
    await notification_manager.subscribe(connection_id, [notification_type])
    
    # Send a notification
    await notification_manager.notify(notification_type, {"cid": "QmTest123"})
    
    # Get metrics
    metrics = notification_manager.get_metrics()
    assert metrics["connections_total"] == 1
    assert metrics["active_connections"] == 1
    assert metrics["notifications_sent"] == 1
    assert metrics["subscriptions_by_type"][notification_type] == 1
    assert "timestamp" in metrics


async def test_passes_filters():
    """Test the _passes_filters method."""
    manager = NotificationManager()
    
    # Test with no filters
    notification = {"data": {"cid": "QmTest123", "size": 1024}}
    assert manager._passes_filters(notification, {}) is True
    
    # Test with matching filter
    filters = {"cid": "QmTest123"}
    assert manager._passes_filters(notification, filters) is True
    
    # Test with non-matching filter
    filters = {"cid": "QmNoMatch"}
    assert manager._passes_filters(notification, filters) is False
    
    # Test with nested key using dot notation
    notification = {"type": "notification", "data": {"file": {"name": "test.txt"}}}
    filters = {"data.file.name": "test.txt"}
    assert manager._passes_filters(notification, filters) is True
    
    # Test with nested key that doesn't exist
    filters = {"data.file.missing": "value"}
    assert manager._passes_filters(notification, filters) is False


async def test_handle_notification_websocket():
    """Test the handle_notification_websocket function."""
    websocket = MockWebSocket()
    
    # Setup messages to be received from the client
    websocket.add_receive_message({
        "action": "subscribe",
        "notification_types": [NotificationType.CONTENT_ADDED.value]
    })
    
    websocket.add_receive_message({
        "action": "ping"
    })
    
    # Create a handler task that runs concurrently
    async def run_handler():
        await handle_notification_websocket(websocket)
    
    # Start the handler in the background
    async with anyio.create_task_group() as tg:
        tg.start_soon(run_handler)
        
        # Give it time to process the welcome message
        await anyio.sleep(0.1)
        
        # Check welcome message
        welcome = websocket.get_sent_message("welcome")
        assert welcome is not None
        assert "connection_id" in welcome
        assert "available_notifications" in welcome
        
        # Give it time to process the subscription message
        await anyio.sleep(0.1)
        
        # Check subscription confirmation
        confirm = websocket.get_sent_message("subscription_confirmed")
        assert confirm is not None
        assert NotificationType.CONTENT_ADDED.value in confirm["notification_types"]
        
        # Give it time to process the ping message
        await anyio.sleep(0.1)
        
        # Check pong response
        pong = websocket.get_sent_message("pong")
        assert pong is not None
        
        # Send an event that should be received
        await emit_event(NotificationType.CONTENT_ADDED.value, {"cid": "QmTest123"})
        
        # Give it time to process the event
        await anyio.sleep(0.1)
        
        # Check notification was sent
        notification = None
        for msg in websocket.sent_messages:
            if msg.get("type") == "notification" and msg.get("notification_type") == NotificationType.CONTENT_ADDED.value:
                notification = msg
                break
        
        assert notification is not None
        assert notification["data"]["cid"] == "QmTest123"
        
        # Close the connection to end the handler
        websocket.client_state = "DISCONNECTED"
        
        # Allow task to finish
        await anyio.sleep(0.1)


async def test_emit_event():
    """Test the emit_event function."""
    manager = NotificationManager()
    websocket = MockWebSocket()
    connection_id = "test_connection"
    
    # Connect a client
    await manager.connect(websocket, connection_id)
    
    # Subscribe to a notification type
    notification_type = NotificationType.CONTENT_ADDED.value
    await manager.subscribe(connection_id, [notification_type])
    
    # Replace the global manager with our test manager
    from ipfs_kit_py.websocket_notifications_anyio import notification_manager as global_manager
    original_manager = global_manager
    import ipfs_kit_py.websocket_notifications_anyio
    ipfs_kit_py.websocket_notifications_anyio.notification_manager = manager
    
    try:
        # Clear sent messages
        websocket.sent_messages = []
        
        # Emit an event
        data = {"cid": "QmEmitTest", "size": 2048}
        result = await emit_event(notification_type, data, "test_source")
        
        # Check result
        assert result["success"] is True
        assert result["notification_type"] == notification_type
        assert result["recipients_sent"] == 1
        
        # Check that the notification was sent
        assert len(websocket.sent_messages) == 1
        notification = websocket.sent_messages[0]
        assert notification["type"] == "notification"
        assert notification["notification_type"] == notification_type
        assert notification["data"] == data
        assert notification["source"] == "test_source"
        
    finally:
        # Restore the original global manager
        ipfs_kit_py.websocket_notifications_anyio.notification_manager = original_manager


async def test_register_notification_websocket():
    """Test registering the notification WebSocket handler with FastAPI."""
    app = FastAPI()
    
    # Register the WebSocket handler
    success = register_notification_websocket(app, "/test/ws")
    assert success is True
    
    # Check that the endpoint was registered
    assert any(route.path == "/test/ws" for route in app.routes)
    
    # Check that the startup event was registered
    assert len(app.router.on_startup) > 0
    
    # Check that the shutdown event was registered
    assert len(app.router.on_shutdown) > 0


async def test_maintenance_tasks():
    """Test the background maintenance tasks."""
    manager = NotificationManager()
    websocket = MockWebSocket()
    connection_id = "test_connection"
    
    # Connect a client
    await manager.connect(websocket, connection_id)
    
    # Start maintenance tasks with short timeout
    await manager.start_maintenance(inactive_timeout=0.5, check_interval=0.2)
    
    try:
        # Check that tasks are running
        assert manager.task_group is not None
        
        # Wait for the inactive connection to be closed
        await anyio.sleep(1.0)
        
        # Check that the connection was closed
        assert connection_id not in manager.active_connections
        assert websocket.closed is True
        assert websocket.close_code == 1000
        assert websocket.close_reason == "Inactivity timeout"
        
    finally:
        # Stop maintenance tasks
        await manager.stop_maintenance()
        assert manager.task_group is None


if __name__ == "__main__":
    # Run tests with anyio backend (defaults to async-io)
    import anyio
    anyio.run(pytest.main, ["-v", __file__])