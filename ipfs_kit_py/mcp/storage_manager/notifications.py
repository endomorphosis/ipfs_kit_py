"""
WebSocket notifications for the Unified Storage Manager.

This module provides real-time notifications for storage operations through WebSockets,
allowing clients to receive updates about operations without polling.
"""

import logging
import time
import threading
import uuid
import asyncio
from enum import Enum
from typing import Dict, List, Any, Optional, Callable, Awaitable

# Configure logger
logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Types of storage notifications."""
    STORAGE_OPERATION = "storage_operation"
    MIGRATION = "migration"
    BACKEND_STATUS = "backend_status"
    CONTENT_STATUS = "content_status"
    SYSTEM = "system"


class NotificationPriority(Enum):
    """Priority levels for notifications."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class StorageNotification:
    """Represents a notification about a storage operation."""
    def __init__(self
        self
        notification_type: NotificationType
        subject: str
        message: str
        data: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
    ):
        """
        Initialize a storage notification.

        Args:
            notification_type: Type of notification
            subject: Subject of the notification
            message: Human-readable message
            data: Additional data for the notification
            priority: Priority level
        """
        self.id = str(uuid.uuid4())
        self.type = notification_type
        self.subject = subject
        self.message = message
        self.data = data or {}
        self.priority = priority
        self.timestamp = time.time()

    def to_dict(selfself) -> Dict[str, Any]:
        """Convert notification to dictionary format."""
        return {
            "id": self.id,
            "type": self.type.value,
            "subject": self.subject,
            "message": self.message,
            "data": self.data,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(selfcls, data: Dict[str, Any]) -> "StorageNotification": ,
        """Create notification from dictionary format."""
        notification = cls(
            notification_type=NotificationType(data["type"]),
            subject=data["subject"],
            message=data["message"],
            data=data.get("data", {}),
            priority=NotificationPriority(data["priority"]),
        )
        notification.id = data["id"]
        notification.timestamp = data["timestamp"]
        return notification


class NotificationSubscription:
    """Represents a client subscription to notifications."""
    def __init___v2(self
        self
        client_id: str
        notification_types: Optional[List[NotificationType]] = None,
        subjects: Optional[List[str]] = None,
        min_priority: NotificationPriority = NotificationPriority.NORMAL,
        callback: Optional[Callable[[StorageNotification], Awaitable[None]]] = None,
    ):
        """
        Initialize a notification subscription.

        Args:
            client_id: Unique client identifier
            notification_types: Types of notifications to receive (all if None)
            subjects: Specific subjects to receive (all if None)
            min_priority: Minimum priority to receive
            callback: Async function to call when notification is delivered
        """
        self.id = str(uuid.uuid4())
        self.client_id = client_id
        self.notification_types = set(notification_types) if notification_types else None
        self.subjects = set(subjects) if subjects else None
        self.min_priority = min_priority
        self.callback = callback
        self.created_at = time.time()
        self.last_notification = None

    def matches(selfself, notification: StorageNotification) -> bool:
        """
        Check if notification matches this subscription.

        Args:
            notification: Notification to check

        Returns:
            True if subscription matches notification
        """
        # Check notification type
        if self.notification_types is not None:
            if notification.type not in self.notification_types:
                return False

        # Check subject
        if self.subjects is not None:
            if notification.subject not in self.subjects:
                return False

        # Check priority
        priority_values = {
            NotificationPriority.LOW: 0
            NotificationPriority.NORMAL: 1
            NotificationPriority.HIGH: 2
            NotificationPriority.CRITICAL: 3
        }

        if priority_values.get(notification.priority, 0) < priority_values.get(
            self.min_priority, 0
        ):
            return False

        return True

    async def deliver(selfself, notification: StorageNotification) -> bool:
        """
        Deliver notification to this subscription.

        Args:
            notification: Notification to deliver

        Returns:
            True if notification was successfully delivered
        """
        try:
            if self.callback:
                await self.callback(notification)
                self.last_notification = time.time()
                return True
            return False
        except Exception as e:
            logger.error(f"Error delivering notification to {self.client_id}: {e}")
            return False


class NotificationManager:
    """
    Manager for storage operation notifications.

    This class handles the creation, distribution, and subscription to notifications
    for storage operations.
    """
    # DISABLED REDEFINITION
        """
        Initialize notification manager.

        Args:
            max_history: Maximum number of notifications to keep in history
        """
        self.max_history = max_history
        self.subscriptions: Dict[str, NotificationSubscription] = {}
        self.history: List[StorageNotification] = []
        self.lock = threading.RLock()
        self.delivery_tasks = set()

    def create_notification(self
        self
        notification_type: NotificationType
        subject: str
        message: str
        data: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
    ) -> StorageNotification:
        """
        Create a new notification.

        Args:
            notification_type: Type of notification
            subject: Subject of the notification
            message: Human-readable message
            data: Additional data for the notification
            priority: Priority level

        Returns:
            Created notification
        """
        notification = StorageNotification(
            notification_type=notification_type,
            subject=subject,
            message=message,
            data=data,
            priority=priority,
        )

        # Store notification in history
        with self.lock:
            self.history.append(notification)

            # Trim history if needed
            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history :]

        # Deliver notification to subscribers
        asyncio.create_task(self._deliver_notification(notification))

        return notification

    def subscribe(self
        self
        client_id: str
        notification_types: Optional[List[NotificationType]] = None,
        subjects: Optional[List[str]] = None,
        min_priority: NotificationPriority = NotificationPriority.NORMAL,
        callback: Optional[Callable[[StorageNotification], Awaitable[None]]] = None,
    ) -> str:
        """
        Subscribe to notifications.

        Args:
            client_id: Unique client identifier
            notification_types: Types of notifications to receive (all if None)
            subjects: Specific subjects to receive (all if None)
            min_priority: Minimum priority to receive
            callback: Async function to call when notification is delivered

        Returns:
            Subscription ID
        """
        subscription = NotificationSubscription(
            client_id=client_id,
            notification_types=notification_types,
            subjects=subjects,
            min_priority=min_priority,
            callback=callback,
        )

        with self.lock:
            self.subscriptions[subscription.id] = subscription

        return subscription.id

    def unsubscribe(selfself, subscription_id: str) -> bool:
        """
        Unsubscribe from notifications.

        Args:
            subscription_id: Subscription ID to unsubscribe

        Returns:
            True if successfully unsubscribed
        """
        with self.lock:
            if subscription_id in self.subscriptions:
                del self.subscriptions[subscription_id]
                return True
            return False

    def get_subscription(selfself, subscription_id: str) -> Optional[NotificationSubscription]:
        """
        Get a subscription by ID.

        Args:
            subscription_id: Subscription ID

        Returns:
            Subscription or None if not found
        """
        with self.lock:
            return self.subscriptions.get(subscription_id)

    def get_client_subscriptions(selfself, client_id: str) -> List[NotificationSubscription]:
        """
        Get all subscriptions for a client.

        Args:
            client_id: Client ID to get subscriptions for

        Returns:
            List of subscriptions
        """
        with self.lock:
            return [s for s in self.subscriptions.values() if s.client_id == client_id]

    def get_history(self
        self
        limit: int = 100,
        notification_types: Optional[List[NotificationType]] = None,
        subjects: Optional[List[str]] = None,
        min_priority: Optional[NotificationPriority] = None,
    ) -> List[StorageNotification]:
        """
        Get notification history with optional filtering.

        Args:
            limit: Maximum number of notifications to return
            notification_types: Filter by notification types
            subjects: Filter by subjects
            min_priority: Filter by minimum priority

        Returns:
            List of notifications
        """
        with self.lock:
            filtered = self.history.copy()

            # Apply filters
            if notification_types:
                filtered = [n for n in filtered if n.type in notification_types]

            if subjects:
                filtered = [n for n in filtered if n.subject in subjects]

            if min_priority:
                priority_values = {
                    NotificationPriority.LOW: 0
                    NotificationPriority.NORMAL: 1
                    NotificationPriority.HIGH: 2
                    NotificationPriority.CRITICAL: 3
                }
                min_value = priority_values.get(min_priority, 0)
                filtered = [n for n in filtered if priority_values.get(n.priority, 0) >= min_value]

            # Return most recent notifications first, limited by count
            return sorted(filtered, key=lambda n: n.timestamp, reverse=True)[:limit]

    async def _deliver_notification(selfself, notification: StorageNotification) -> None:
        """
        Deliver notification to all matching subscriptions.

        Args:
            notification: Notification to deliver
        """
        # Get all matching subscriptions
        matching_subscriptions = []
        with self.lock:
            for subscription in self.subscriptions.values():
                if subscription.matches(notification):
                    matching_subscriptions.append(subscription)

        # Deliver to each subscription
        for subscription in matching_subscriptions:
            try:
                await subscription.deliver(notification)
            except Exception as e:
                logger.error(
                    f"Error delivering notification to subscription {subscription.id}: {e}"
                )


class WebSocketStorageNotifier:
    """
    WebSocket notification handler for storage operations.

    This class provides a WebSocket interface for clients to subscribe to
    storage operation notifications.
    """
    # DISABLED REDEFINITION
        """
        Initialize WebSocket notifier.

        Args:
            notification_manager: Notification manager to use
        """
        self.notification_manager = notification_manager
        self.active_connections: Dict[str, Any] = {}
        self.connection_subscriptions: Dict[str, List[str]] = {}

    async def on_connect(selfself, websocket, client_id: Optional[str] = None) -> str:
        """
        Handle WebSocket connection.

        Args:
            websocket: WebSocket connection object
            client_id: Optional client ID (generated if None)

        Returns:
            Assigned client ID
        """
        # Generate client ID if not provided
        if client_id is None:
            client_id = f"ws-client-{str(uuid.uuid4())}"

        # Store connection
        self.active_connections[client_id] = websocket
        self.connection_subscriptions[client_id] = []

        # Send welcome message
        await websocket.send_json(
            {
                "type": "system",
                "event": "connected",
                "client_id": client_id,
                "timestamp": time.time(),
            }
        )

        logger.info(f"WebSocket client connected: {client_id}")
        return client_id

    async def on_disconnect(selfself, client_id: str) -> None:
        """
        Handle WebSocket disconnection.

        Args:
            client_id: Client ID
        """
        # Remove connection
        if client_id in self.active_connections:
            del self.active_connections[client_id]

        # Unsubscribe from all subscriptions
        if client_id in self.connection_subscriptions:
            for subscription_id in self.connection_subscriptions[client_id]:
                self.notification_manager.unsubscribe(subscription_id)
            del self.connection_subscriptions[client_id]

        logger.info(f"WebSocket client disconnected: {client_id}")

    async def on_message(selfself, websocket, client_id: str, message: Dict[str, Any]) -> None:
        """
        Handle WebSocket message.

        Args:
            websocket: WebSocket connection object
            client_id: Client ID
            message: Message data
        """
        try:
            message_type = message.get("type")

            if message_type == "subscribe":
                await self._handle_subscribe(websocket, client_id, message)
            elif message_type == "unsubscribe":
                await self._handle_unsubscribe(websocket, client_id, message)
            elif message_type == "get_history":
                await self._handle_get_history(websocket, client_id, message)
            elif message_type == "ping":
                await websocket.send_json({"type": "pong", "timestamp": time.time()})
            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "error": f"Unknown message type: {message_type}",
                        "timestamp": time.time(),
                    }
                )
        except Exception as e:
            logger.error(f"Error handling WebSocket message from {client_id}: {e}")
            try:
                await websocket.send_json(
                    {
                        "type": "error",
                        "error": f"Error processing message: {str(e)}",
                        "timestamp": time.time(),
                    }
                )
            except Exception:
                pass

    async def _handle_subscribe(selfself, websocket, client_id: str, message: Dict[str, Any]) -> None:
        """
        Handle subscription request.

        Args:
            websocket: WebSocket connection object
            client_id: Client ID
            message: Message data
        """
        try:
            # Parse subscription parameters
            notification_types = message.get("notification_types")
            if notification_types:
                notification_types = [NotificationType(t) for t in notification_types]

            subjects = message.get("subjects")

            min_priority = message.get("min_priority")
            if min_priority:
                min_priority = NotificationPriority(min_priority)
            else:
                min_priority = NotificationPriority.NORMAL

            # Create callback function to deliver notifications
            async def notification_callback(self, notification: StorageNotification) -> None:
                try:
                    await websocket.send_json(
                        {"type": "notification", "notification": notification.to_dict()}
                    )
                except Exception as e:
                    logger.error(f"Error sending notification to {client_id}: {e}")

            # Subscribe to notifications
            subscription_id = self.notification_manager.subscribe(
                client_id=client_id,
                notification_types=notification_types,
                subjects=subjects,
                min_priority=min_priority,
                callback=notification_callback,
            )

            # Store subscription ID
            if client_id in self.connection_subscriptions:
                self.connection_subscriptions[client_id].append(subscription_id)

            # Send confirmation
            await websocket.send_json(
                {
                    "type": "subscription_confirmed",
                    "subscription_id": subscription_id,
                    "notification_types": (,
                        [t.value for t in notification_types] if notification_types else None
                    ),
                    "subjects": subjects,
                    "min_priority": min_priority.value,
                    "timestamp": time.time(),
                }
            )

        except Exception as e:
            logger.error(f"Error creating subscription for {client_id}: {e}")
            await websocket.send_json(
                {
                    "type": "error",
                    "error": f"Error creating subscription: {str(e)}",
                    "timestamp": time.time(),
                }
            )

    async def _handle_unsubscribe(selfself, websocket, client_id: str, message: Dict[str, Any]) -> None:
        """
        Handle unsubscribe request.

        Args:
            websocket: WebSocket connection object
            client_id: Client ID
            message: Message data
        """
        subscription_id = message.get("subscription_id")

        if not subscription_id:
            await websocket.send_json(
                {
                    "type": "error",
                    "error": "Missing subscription_id",
                    "timestamp": time.time(),
                }
            )
            return

        # Verify subscription belongs to this client
        if client_id in self.connection_subscriptions:
            if subscription_id not in self.connection_subscriptions[client_id]:
                await websocket.send_json(
                    {
                        "type": "error",
                        "error": "Subscription does not belong to this client",
                        "timestamp": time.time(),
                    }
                )
                return

        # Unsubscribe
        success = self.notification_manager.unsubscribe(subscription_id)

        # Remove from client subscriptions
        if success and client_id in self.connection_subscriptions:
            if subscription_id in self.connection_subscriptions[client_id]:
                self.connection_subscriptions[client_id].remove(subscription_id)

        # Send confirmation
        await websocket.send_json(
            {
                "type": "unsubscribe_confirmed",
                "subscription_id": subscription_id,
                "success": success,
                "timestamp": time.time(),
            }
        )

    async def _handle_get_history(selfself, websocket, client_id: str, message: Dict[str, Any]) -> None:
        """
        Handle history request.

        Args:
            websocket: WebSocket connection object
            client_id: Client ID
            message: Message data
        """
        try:
            # Parse history parameters
            limit = message.get("limit", 100)

            notification_types = message.get("notification_types")
            if notification_types:
                notification_types = [NotificationType(t) for t in notification_types]

            subjects = message.get("subjects")

            min_priority = message.get("min_priority")
            if min_priority:
                min_priority = NotificationPriority(min_priority)

            # Get history
            notifications = self.notification_manager.get_history(
                limit=limit,
                notification_types=notification_types,
                subjects=subjects,
                min_priority=min_priority,
            )

            # Send history
            await websocket.send_json(
                {
                    "type": "history",
                    "notifications": [n.to_dict() for n in notifications],
                    "timestamp": time.time(),
                }
            )

        except Exception as e:
            logger.error(f"Error getting history for {client_id}: {e}")
            await websocket.send_json(
                {
                    "type": "error",
                    "error": f"Error getting history: {str(e)}",
                    "timestamp": time.time(),
                }
            )


class StorageNotificationService:
    """
    Service for generating storage-related notifications.

    This class integrates with the Storage Manager and Migration Controller to
    generate notifications for storage operations and migrations.
    """
    # DISABLED REDEFINITION
        """
        Initialize storage notification service.

        Args:
            notification_manager: Notification manager to use
        """
        self.notification_manager = notification_manager

    def notify_storage_operation(self
        self
        operation: str
        backend: str
        content_id: Optional[str] = None,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
    ) -> StorageNotification:
        """
        Create notification for a storage operation.

        Args:
            operation: Operation type (store, retrieve, delete, etc.)
            backend: Backend name
            content_id: Content ID (if applicable)
            success: Whether operation was successful
            details: Additional operation details
            priority: Notification priority

        Returns:
            Created notification
        """
        details = details or {}

        # Determine notification subject
        if content_id:
            subject = f"{backend}:{content_id}"
        else:
            subject = backend

        # Create message
        if success:
            message = f"Successfully {operation}d content"
            if content_id:
                message += f" {content_id}"
            message += f" on {backend} backend"
        else:
            message = f"Failed to {operation} content"
            if content_id:
                message += f" {content_id}"
            message += f" on {backend} backend"

            if "error" in details:
                message += f": {details['error']}"

        # Create notification data
        data = {
            "operation": operation,
            "backend": backend,
            "success": success,
            **details,
        }

        if content_id:
            data["content_id"] = content_id

        # Create and return notification
        return self.notification_manager.create_notification(
            notification_type=NotificationType.STORAGE_OPERATION,
            subject=subject,
            message=message,
            data=data,
            priority=priority,
        )

    def notify_migration_status(self
        self
        migration_id: str
        status: str
        source_backend: str
        target_backend: str
        content_id: Optional[str] = None,
        progress: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
    ) -> StorageNotification:
        """
        Create notification for a migration status update.

        Args:
            migration_id: Migration ID
            status: Migration status
            source_backend: Source backend name
            target_backend: Target backend name
            content_id: Content ID (if applicable)
            progress: Migration progress (0-1)
            details: Additional migration details
            priority: Notification priority

        Returns:
            Created notification
        """
        details = details or {}

        # Determine notification subject
        subject = f"migration:{migration_id}"

        # Create message
        message = f"Migration {status}: {source_backend} -> {target_backend}"
        if content_id:
            message += f" for content {content_id}"

        if progress is not None:
            message += f" ({int(progress * 100)}%)"

        # Create notification data
        data = {
            "migration_id": migration_id,
            "status": status,
            "source_backend": source_backend,
            "target_backend": target_backend,
            **details,
        }

        if content_id:
            data["content_id"] = content_id

        if progress is not None:
            data["progress"] = progress

        # Create and return notification
        return self.notification_manager.create_notification(
            notification_type=NotificationType.MIGRATION,
            subject=subject,
            message=message,
            data=data,
            priority=priority,
        )

    def notify_backend_status(self
        self
        backend: str
        status: str
        available: bool
        details: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.HIGH,
    ) -> StorageNotification:
        """
        Create notification for a backend status update.

        Args:
            backend: Backend name
            status: Status description
            available: Whether backend is available
            details: Additional status details
            priority: Notification priority

        Returns:
            Created notification
        """
        details = details or {}

        # Determine notification subject
        subject = f"backend:{backend}"

        # Create message
        message = f"Backend {backend} {status}"
        if not available:
            message += " (unavailable)"

        # Create notification data
        data = {"backend": backend, "status": status, "available": available, **details}

        # Create and return notification
        return self.notification_manager.create_notification(
            notification_type=NotificationType.BACKEND_STATUS,
            subject=subject,
            message=message,
            data=data,
            priority=priority,
        )

    def notify_content_status(self
        self
        content_id: str
        status: str
        backends: List[str]
        details: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
    ) -> StorageNotification:
        """
        Create notification for a content status update.

        Args:
            content_id: Content ID
            status: Content status
            backends: List of backends where content is available
            details: Additional status details
            priority: Notification priority

        Returns:
            Created notification
        """
        details = details or {}

        # Determine notification subject
        subject = f"content:{content_id}"

        # Create message
        message = f"Content {content_id} {status}"
        if backends:
            message += f" on backends: {', '.join(backends)}"

        # Create notification data
        data = {
            "content_id": content_id,
            "status": status,
            "backends": backends,
            **details,
        }

        # Create and return notification
        return self.notification_manager.create_notification(
            notification_type=NotificationType.CONTENT_STATUS,
            subject=subject,
            message=message,
            data=data,
            priority=priority,
        )

    def notify_system_event(self
        self
        event: str
        message: str
        details: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
    ) -> StorageNotification:
        """
        Create notification for a system event.

        Args:
            event: Event type
            message: Event message
            details: Additional event details
            priority: Notification priority

        Returns:
            Created notification
        """
        details = details or {}

        # Determine notification subject
        subject = f"system:{event}"

        # Create notification data
        data = {"event": event, **details}

        # Create and return notification
        return self.notification_manager.create_notification(
            notification_type=NotificationType.SYSTEM,
            subject=subject,
            message=message,
            data=data,
            priority=priority,
        )
