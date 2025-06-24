"""
Tests for the anyio-based WAL WebSocket implementation.

These tests verify that the anyio implementation of the WAL WebSocket system
works correctly and maintains the same functionality as the asyncio version,
while providing the benefits of anyio's backend flexibility.
"""

import json
import time
from unittest.mock import MagicMock, patch
from typing import Dict, Any, List

import pytest
import anyio

# Import our mock WebSocket implementation instead of fastapi's
import sys
import os

# Add the parent directory to sys.path to make test/mock_fastapi.py importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from test.mock_fastapi import WebSocket, WebSocketDisconnect

from ipfs_kit_py.wal_websocket_anyio import (
    SubscriptionType,
    WALConnectionManager,
    WALWebSocketHandler,
    register_wal_websocket
)

# Mock FastAPI app
class MockFastAPI:
    def __init__(self):
        self.routes = []
        self.router = MockRouter()

    def websocket(self, path):
        def decorator(func):
            self.routes.append(MockRoute(path, func))
            return func
        return decorator

class MockRouter:
    def __init__(self):
        self.on_shutdown = []

    def add_event_handler(self, event, func):
        if event == "shutdown":
            self.on_shutdown.append(func)

class MockRoute:
    def __init__(self, path, endpoint):
        self.path = path
        self.endpoint = endpoint

# Mark all tests in this module as anyio tests
pytestmark = pytest.mark.anyio

class MockWebSocket:
    """Mock WebSocket for testing the WAL WebSocket system."""

    def __init__(self):
        self.client_state = "CONNECTED"
        self.sent_messages = []
        self.closed = False
        self.close_code = None
        self.close_reason = None

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
        """
        Mock receive_json that needs to be overridden in tests.
        By default, raises WebSocketDisconnect to simulate client disconnect.
        """
        raise WebSocketDisconnect()

class MockStorageWriteAheadLog:
    """Mock WAL for testing."""

    def __init__(self):
        self.operations = {}
        self.health_monitor = MockHealthMonitor()

    def get_operation(self, operation_id):
        """Get an operation by ID."""
        return self.operations.get(operation_id)

    def get_operations(self, limit=100):
        """Get all operations."""
        return list(self.operations.values())[:limit]

    def get_operations_by_status(self, status, limit=100):
        """Get operations by status."""
        return [op for op in self.operations.values()
                if op.get("status") == status][:limit]

    def get_statistics(self):
        """Get WAL statistics."""
        return {
            "operations_total": len(self.operations),
            "operations_by_status": {
                "pending": len([op for op in self.operations.values()
                               if op.get("status") == "pending"]),
                "processing": len([op for op in self.operations.values()
                                  if op.get("status") == "processing"]),
                "completed": len([op for op in self.operations.values()
                                 if op.get("status") == "completed"]),
                "failed": len([op for op in self.operations.values()
                              if op.get("status") == "failed"])
            },
            "timestamp": time.time()
        }

    def add_test_operation(self, operation_id, status="pending", backend="test",
                         operation_type="test"):
        """Add a test operation."""
        self.operations[operation_id] = {
            "operation_id": operation_id,
            "status": status,
            "backend": backend,
            "operation_type": operation_type,
            "created_at": time.time(),
            "updated_at": time.time()
        }
        return self.operations[operation_id]

class MockHealthMonitor:
    """Mock health monitor for testing."""

    def __init__(self):
        self.status = {}
        self.status_change_callback = None

    def get_status(self, backend=None):
        """Get backend status."""
        if backend:
            return {backend: self.status.get(backend, "unknown")}
        return self.status.copy()

    def set_status(self, backend, status):
        """Set backend status and trigger callback."""
        old_status = self.status.get(backend, "unknown")
        self.status[backend] = status

        if self.status_change_callback and old_status != status:
            self.status_change_callback(backend, old_status, status)

@pytest.fixture
async def connection_manager():
    """Create a connection manager for testing."""
    return WALConnectionManager()

@pytest.fixture
async def mock_websocket():
    """Create a mock WebSocket for testing."""
    return MockWebSocket()

@pytest.fixture
async def mock_wal():
    """Create a mock WAL for testing."""
    wal = MockStorageWriteAheadLog()

    # Add some test operations
    wal.add_test_operation("op1", status="pending")
    wal.add_test_operation("op2", status="processing")
    wal.add_test_operation("op3", status="completed")

    # Set up some test backend statuses
    wal.health_monitor.status = {
        "backend1": "healthy",
        "backend2": "degraded"
    }

    return wal

@pytest.fixture
async def websocket_handler(mock_wal):
    """Create a WebSocket handler for testing."""
    return WALWebSocketHandler(mock_wal)

@pytest.fixture
async def connected_websocket(connection_manager, mock_websocket):
    """Create a connected WebSocket for testing."""
    await connection_manager.connect(mock_websocket)
    return mock_websocket

@pytest.fixture
def fastapi_app():
    """Create a mock FastAPI app for testing."""
    return MockFastAPI()

async def test_connection_manager_connect(connection_manager, mock_websocket):
    """Test connecting a WebSocket."""
    # Connect the WebSocket
    result = await connection_manager.connect(mock_websocket)

    # Check connection was successful
    assert result is True
    assert mock_websocket in connection_manager.active_connections
    assert mock_websocket in connection_manager.connection_subscriptions

    # Check welcome message was sent
    assert len(mock_websocket.sent_messages) == 1
    assert mock_websocket.sent_messages[0]["type"] == "connection_established"

async def test_connection_manager_disconnect(connection_manager, mock_websocket):
    """Test disconnecting a WebSocket."""
    # Connect the WebSocket
    await connection_manager.connect(mock_websocket)

    # Subscribe to some topics
    connection_manager.subscribe(
        mock_websocket,
        SubscriptionType.ALL_OPERATIONS
    )
    connection_manager.subscribe(
        mock_websocket,
        SubscriptionType.BACKEND_HEALTH
    )

    # Disconnect the WebSocket
    connection_manager.disconnect(mock_websocket)

    # Check connection was removed
    assert mock_websocket not in connection_manager.active_connections
    assert mock_websocket not in connection_manager.connection_subscriptions
    assert mock_websocket not in connection_manager.all_operations_subscribers
    assert mock_websocket not in connection_manager.health_subscribers

async def test_connection_manager_subscribe(connection_manager, mock_websocket):
    """Test subscribing to notification types."""
    # Connect the WebSocket
    await connection_manager.connect(mock_websocket)

    # Subscribe to ALL_OPERATIONS
    subscription_id = connection_manager.subscribe(
        mock_websocket,
        SubscriptionType.ALL_OPERATIONS
    )

    # Check subscription was created
    assert subscription_id.startswith(SubscriptionType.ALL_OPERATIONS.value)
    assert subscription_id in connection_manager.connection_subscriptions[mock_websocket]
    assert mock_websocket in connection_manager.all_operations_subscribers

    # Subscribe to a specific operation
    subscription_id = connection_manager.subscribe(
        mock_websocket,
        SubscriptionType.SPECIFIC_OPERATION,
        {"operation_id": "test-op-1"}
    )

    # Check subscription was created
    assert subscription_id.startswith(SubscriptionType.SPECIFIC_OPERATION.value)
    assert "test-op-1" in connection_manager.operation_subscribers
    assert mock_websocket in connection_manager.operation_subscribers["test-op-1"]

    # Subscribe to a specific status
    subscription_id = connection_manager.subscribe(
        mock_websocket,
        SubscriptionType.OPERATIONS_BY_STATUS,
        {"status": "pending"}
    )

    # Check subscription was created
    assert subscription_id.startswith(SubscriptionType.OPERATIONS_BY_STATUS.value)
    assert "pending" in connection_manager.status_subscribers
    assert mock_websocket in connection_manager.status_subscribers["pending"]

async def test_connection_manager_unsubscribe(connection_manager, mock_websocket):
    """Test unsubscribing from notification types."""
    # Connect the WebSocket
    await connection_manager.connect(mock_websocket)

    # Subscribe to ALL_OPERATIONS
    subscription_id = connection_manager.subscribe(
        mock_websocket,
        SubscriptionType.ALL_OPERATIONS
    )

    # Unsubscribe
    success = connection_manager.unsubscribe(mock_websocket, subscription_id)

    # Check unsubscribe was successful
    assert success is True
    assert subscription_id not in connection_manager.connection_subscriptions[mock_websocket]
    assert mock_websocket not in connection_manager.all_operations_subscribers

    # Test unsubscribing from non-existent subscription
    success = connection_manager.unsubscribe(mock_websocket, "non-existent")
    assert success is False

async def test_connection_manager_send_message(connection_manager, mock_websocket):
    """Test sending a message to a WebSocket."""
    # Connect the WebSocket
    await connection_manager.connect(mock_websocket)

    # Send a message
    message = {"type": "test", "data": "test data"}
    result = await connection_manager.send_message(mock_websocket, message)

    # Check message was sent
    assert result is True
    assert len(mock_websocket.sent_messages) == 2  # Welcome message + test message
    assert mock_websocket.sent_messages[1] == message

    # Test sending to disconnected WebSocket
    mock_websocket.client_state = "DISCONNECTED"
    result = await connection_manager.send_message(mock_websocket, message)
    assert result is False

async def test_connection_manager_broadcast_operation_update(connection_manager, mock_websocket):
    """Test broadcasting an operation update."""
    # Connect the WebSocket
    await connection_manager.connect(mock_websocket)

    # Subscribe to ALL_OPERATIONS
    connection_manager.subscribe(
        mock_websocket,
        SubscriptionType.ALL_OPERATIONS
    )

    # Broadcast an operation update
    operation = {
        "operation_id": "test-op-1",
        "status": "pending",
        "backend": "test",
        "operation_type": "test"
    }

    await connection_manager.broadcast_operation_update(operation)

    # Check message was sent
    assert len(mock_websocket.sent_messages) >= 2  # Welcome message + operation update
    assert mock_websocket.sent_messages[-1]["type"] == "operation_update"
    assert mock_websocket.sent_messages[-1]["operation"] == operation

async def test_connection_manager_broadcast_health_update(connection_manager, mock_websocket):
    """Test broadcasting a health update."""
    # Connect the WebSocket
    await connection_manager.connect(mock_websocket)

    # Subscribe to BACKEND_HEALTH
    connection_manager.subscribe(
        mock_websocket,
        SubscriptionType.BACKEND_HEALTH
    )

    # Broadcast a health update
    health_data = {
        "backend1": "healthy",
        "backend2": "degraded"
    }

    await connection_manager.broadcast_health_update(health_data)

    # Check message was sent
    assert len(mock_websocket.sent_messages) >= 2  # Welcome message + health update
    assert mock_websocket.sent_messages[-1]["type"] == "health_update"
    assert mock_websocket.sent_messages[-1]["health_data"] == health_data

async def test_connection_manager_broadcast_metrics_update(connection_manager, mock_websocket):
    """Test broadcasting a metrics update."""
    # Connect the WebSocket
    await connection_manager.connect(mock_websocket)

    # Subscribe to METRICS
    connection_manager.subscribe(
        mock_websocket,
        SubscriptionType.METRICS
    )

    # Broadcast a metrics update
    metrics_data = {
        "operations_total": 10,
        "operations_by_status": {
            "pending": 2,
            "processing": 3,
            "completed": 4,
            "failed": 1
        }
    }

    await connection_manager.broadcast_metrics_update(metrics_data)

    # Check message was sent
    assert len(mock_websocket.sent_messages) >= 2  # Welcome message + metrics update
    assert mock_websocket.sent_messages[-1]["type"] == "metrics_update"
    assert mock_websocket.sent_messages[-1]["metrics_data"] == metrics_data

async def test_websocket_handler_init(mock_wal):
    """Test initializing the WebSocket handler."""
    handler = WALWebSocketHandler(mock_wal)

    # Check handler was initialized correctly
    assert handler.wal == mock_wal
    assert isinstance(handler.connection_manager, WALConnectionManager)
    assert handler.running is False
    assert handler.task_group is None

    # Check callback was set up
    assert mock_wal.health_monitor.status_change_callback == handler._on_backend_status_change

async def test_websocket_handler_handle_connection(websocket_handler, mock_websocket):
    """Test handling a WebSocket connection."""
    # Override receive_json to return a subscribe message and then disconnect
    async def receive_json():
        # Return a subscribe message
        return {
            "action": "subscribe",
            "subscription_type": "all_operations"
        }

    # Set up the mock WebSocket
    mock_websocket.receive_json = receive_json

    # Call handle_connection in a task to handle the message
    async with anyio.create_task_group() as tg:
        tg.start_soon(websocket_handler.handle_connection, mock_websocket)
        # Give it time to process the message
        await anyio.sleep(0.5)
        # Simulate disconnection
        mock_websocket.client_state = "DISCONNECTED"
        # Wait for the handler to detect the disconnection
        await anyio.sleep(0.5)

    # Check welcome and subscription confirmation messages were sent
    assert len(mock_websocket.sent_messages) >= 2
    assert mock_websocket.sent_messages[0]["type"] == "connection_established"
    subscription_message = None
    for msg in mock_websocket.sent_messages:
        if msg["type"] == "subscription_created":
            subscription_message = msg
            break
    assert subscription_message is not None
    assert subscription_message["subscription_type"] == "all_operations"

async def test_websocket_handler_handle_subscribe(websocket_handler, mock_websocket):
    """Test handling a subscribe request."""
    # Connect the WebSocket
    await websocket_handler.connection_manager.connect(mock_websocket)

    # Clear sent messages
    mock_websocket.sent_messages = []

    # Handle a subscribe message
    await websocket_handler.handle_subscribe(
        mock_websocket,
        {
            "subscription_type": "all_operations"
        }
    )

    # Check subscription confirmation was sent
    assert len(mock_websocket.sent_messages) == 2  # Confirmation + operations list
    assert mock_websocket.sent_messages[0]["type"] == "subscription_created"
    assert mock_websocket.sent_messages[0]["subscription_type"] == "all_operations"
    assert mock_websocket.sent_messages[1]["type"] == "operations_list"

    # Check WebSocket was added to subscribers
    assert mock_websocket in websocket_handler.connection_manager.all_operations_subscribers

async def test_websocket_handler_handle_unsubscribe(websocket_handler, mock_websocket):
    """Test handling an unsubscribe request."""
    # Connect the WebSocket
    await websocket_handler.connection_manager.connect(mock_websocket)

    # Subscribe to ALL_OPERATIONS
    subscription_id = websocket_handler.connection_manager.subscribe(
        mock_websocket,
        SubscriptionType.ALL_OPERATIONS
    )

    # Clear sent messages
    mock_websocket.sent_messages = []

    # Handle an unsubscribe message
    await websocket_handler.handle_unsubscribe(
        mock_websocket,
        {
            "subscription_id": subscription_id
        }
    )

    # Check unsubscribe confirmation was sent
    assert len(mock_websocket.sent_messages) == 1
    assert mock_websocket.sent_messages[0]["type"] == "unsubscribe_result"
    assert mock_websocket.sent_messages[0]["subscription_id"] == subscription_id
    assert mock_websocket.sent_messages[0]["success"] is True

    # Check WebSocket was removed from subscribers
    assert mock_websocket not in websocket_handler.connection_manager.all_operations_subscribers

async def test_websocket_handler_handle_get_operation(websocket_handler, mock_websocket):
    """Test handling a get_operation request."""
    # Connect the WebSocket
    await websocket_handler.connection_manager.connect(mock_websocket)

    # Clear sent messages
    mock_websocket.sent_messages = []

    # Handle a get_operation message
    await websocket_handler.handle_get_operation(
        mock_websocket,
        {
            "operation_id": "op1"
        }
    )

    # Check operation data was sent
    assert len(mock_websocket.sent_messages) == 1
    assert mock_websocket.sent_messages[0]["type"] == "operation_data"
    assert mock_websocket.sent_messages[0]["operation"]["operation_id"] == "op1"

    # Test with non-existent operation
    mock_websocket.sent_messages = []
    await websocket_handler.handle_get_operation(
        mock_websocket,
        {
            "operation_id": "non-existent"
        }
    )

    # Check error message was sent
    assert len(mock_websocket.sent_messages) == 1
    assert mock_websocket.sent_messages[0]["type"] == "error"

async def test_websocket_handler_handle_get_health(websocket_handler, mock_websocket):
    """Test handling a get_health request."""
    # Connect the WebSocket
    await websocket_handler.connection_manager.connect(mock_websocket)

    # Clear sent messages
    mock_websocket.sent_messages = []

    # Handle a get_health message
    await websocket_handler.handle_get_health(
        mock_websocket,
        {}
    )

    # Check health data was sent
    assert len(mock_websocket.sent_messages) == 1
    assert mock_websocket.sent_messages[0]["type"] == "health_data"
    assert "backend1" in mock_websocket.sent_messages[0]["health_data"]
    assert "backend2" in mock_websocket.sent_messages[0]["health_data"]

    # Test with specific backend
    mock_websocket.sent_messages = []
    await websocket_handler.handle_get_health(
        mock_websocket,
        {
            "backend": "backend1"
        }
    )

    # Check health data was sent
    assert len(mock_websocket.sent_messages) == 1
    assert mock_websocket.sent_messages[0]["type"] == "health_data"
    assert "backend1" in mock_websocket.sent_messages[0]["health_data"]

async def test_websocket_handler_handle_get_metrics(websocket_handler, mock_websocket):
    """Test handling a get_metrics request."""
    # Connect the WebSocket
    await websocket_handler.connection_manager.connect(mock_websocket)

    # Clear sent messages
    mock_websocket.sent_messages = []

    # Handle a get_metrics message
    await websocket_handler.handle_get_metrics(
        mock_websocket,
        {}
    )

    # Check metrics data was sent
    assert len(mock_websocket.sent_messages) == 1
    assert mock_websocket.sent_messages[0]["type"] == "metrics_data"
    assert "operations_total" in mock_websocket.sent_messages[0]["metrics_data"]
    assert "operations_by_status" in mock_websocket.sent_messages[0]["metrics_data"]

async def test_websocket_handler_on_backend_status_change(websocket_handler, mock_websocket):
    """Test handling a backend status change."""
    # Connect the WebSocket
    await websocket_handler.connection_manager.connect(mock_websocket)

    # Subscribe to BACKEND_HEALTH
    websocket_handler.connection_manager.subscribe(
        mock_websocket,
        SubscriptionType.BACKEND_HEALTH
    )

    # Change backend status
    with patch("anyio.from_thread.run") as mock_run:
        # Mock the anyio.from_thread.run function to just call the function directly
        mock_run.side_effect = lambda func, *args, **kwargs: anyio.run(func, *args)

        # Trigger status change
        websocket_handler._on_backend_status_change("backend1", "healthy", "degraded")

        # Wait for the message to be sent
        await anyio.sleep(0.5)

        # Check the function was called
        mock_run.assert_called_once()

async def test_websocket_handler_start_update_task(websocket_handler):
    """Test starting the update task."""
    # Start the update task
    await websocket_handler.start_update_task()

    # Check task was started
    assert websocket_handler.running is True
    assert websocket_handler.task_group is not None

    # Clean up
    await websocket_handler.stop()

async def test_websocket_handler_stop(websocket_handler):
    """Test stopping the WebSocket handler."""
    # Start the update task
    await websocket_handler.start_update_task()

    # Stop the handler
    await websocket_handler.stop()

    # Check handler was stopped
    assert websocket_handler.running is False
    assert websocket_handler.task_group is None

async def test_register_wal_websocket(fastapi_app, mock_wal):
    """Test registering the WAL WebSocket with FastAPI."""
    # Mock the WAL instance and get_wal_instance function
    with patch("ipfs_kit_py.wal_websocket_anyio.get_wal_instance", return_value=mock_wal):
        # Register the WebSocket
        success = register_wal_websocket(fastapi_app)

        # Check registration was successful
        assert success is True

        # Check the WebSocket endpoint was registered
        routes = [route.path for route in fastapi_app.routes]
        assert "/api/v0/wal/ws" in routes

        # Check the shutdown event handler was registered
        assert len(fastapi_app.router.on_shutdown) > 0

        # Create a test client
        client = TestClient(fastapi_app)

        # Test the WebSocket endpoint (just check it's registered, we can't test it directly)
        # In a real test we would use TestClient.websocket_connect but that's not available in test mode

if __name__ == "__main__":
    # Run tests with anyio backend (defaults to asyncio)
    import anyio
    anyio.run(pytest.main, ["-v", __file__])
