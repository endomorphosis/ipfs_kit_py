"""
JSON-RPC Event Manager for MCP Server.

This module provides event management functionality via JSON-RPC calls,
replacing WebSocket-based real-time communication with polling-based
event retrieval while maintaining all existing functionality.
"""

import json
import time
import logging
import threading
import uuid
from enum import Enum
from typing import Dict, Any, List, Set, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque

# Configure logger
logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events that can be managed."""
    BACKEND_CHANGE = "backend_change"
    MIGRATION_EVENT = "migration_event"
    STREAM_PROGRESS = "stream_progress"
    SEARCH_EVENT = "search_event"
    SYSTEM_EVENT = "system_event"
    CLIENT_CONNECTION = "client_connection"
    SUBSCRIPTION_CHANGE = "subscription_change"


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
class Event:
    """Represents an event in the system."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: EventType = EventType.SYSTEM_EVENT
    category: str = "system"
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "category": self.category,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


@dataclass
class ClientSession:
    """Information about a client session."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subscriptions: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    last_poll: datetime = field(default_factory=datetime.now)
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()
    
    def update_poll(self) -> None:
        """Update last poll timestamp."""
        self.last_poll = datetime.now()
        self.update_activity()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "subscriptions": list(self.subscriptions),
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "last_poll": self.last_poll.isoformat(),
            "session_duration": (datetime.now() - self.created_at).total_seconds()
        }


class JSONRPCEventManager:
    """
    Event manager that provides WebSocket-like functionality via JSON-RPC polling.
    
    This class replaces WebSocket real-time communication with a polling-based
    approach while maintaining all the same functionality for subscriptions,
    events, and notifications.
    """
    
    def __init__(self, max_events_per_category: int = 1000, event_ttl_hours: int = 24):
        """
        Initialize the JSON-RPC event manager.
        
        Args:
            max_events_per_category: Maximum events to keep per category
            event_ttl_hours: Hours to keep events before expiring them
        """
        self.max_events_per_category = max_events_per_category
        self.event_ttl = timedelta(hours=event_ttl_hours)
        
        # Client sessions
        self.sessions: Dict[str, ClientSession] = {}
        
        # Event storage by category
        self.events_by_category: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_events_per_category))
        
        # Subscription management
        self.subscriptions: Dict[str, Set[str]] = defaultdict(set)  # category -> set of session_ids
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Event handlers
        self.event_handlers: Dict[str, Callable] = {}
        
        # Cleanup thread
        self.cleanup_running = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_expired_events, daemon=True)
        self.cleanup_thread.start()
    
    def create_session(self, session_id: Optional[str] = None) -> str:
        """
        Create a new client session.
        
        Args:
            session_id: Optional session ID (generated if not provided)
            
        Returns:
            Session ID
        """
        with self.lock:
            if session_id is None:
                session_id = str(uuid.uuid4())
            
            session = ClientSession(id=session_id)
            self.sessions[session_id] = session
            
            # Create session event
            self._add_event(Event(
                type=EventType.CLIENT_CONNECTION,
                category="system",
                data={
                    "action": "session_created",
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat()
                }
            ))
            
            logger.info(f"Created session: {session_id}")
            return session_id
    
    def destroy_session(self, session_id: str) -> bool:
        """
        Destroy a client session.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if session was destroyed
        """
        with self.lock:
            if session_id not in self.sessions:
                return False
            
            session = self.sessions[session_id]
            
            # Remove from all subscriptions
            for category in list(session.subscriptions):
                self._unsubscribe_session(session_id, category)
            
            # Remove session
            del self.sessions[session_id]
            
            # Create session destroyed event
            self._add_event(Event(
                type=EventType.CLIENT_CONNECTION,
                category="system",
                data={
                    "action": "session_destroyed",
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat()
                }
            ))
            
            logger.info(f"Destroyed session: {session_id}")
            return True
    
    def subscribe(self, session_id: str, categories: Union[str, List[str]]) -> Dict[str, Any]:
        """
        Subscribe a session to event categories.
        
        Args:
            session_id: Session ID
            categories: Category or list of categories to subscribe to
            
        Returns:
            Result dictionary
        """
        with self.lock:
            if session_id not in self.sessions:
                return {"success": False, "error": f"Session {session_id} not found"}
            
            if isinstance(categories, str):
                categories = [categories]
            
            session = self.sessions[session_id]
            subscribed = []
            
            for category in categories:
                # Handle special "all" category
                if category.lower() == EventCategory.ALL.value:
                    for cat in EventCategory:
                        if cat != EventCategory.ALL:
                            self._subscribe_session(session_id, cat.value)
                            subscribed.append(cat.value)
                else:
                    self._subscribe_session(session_id, category)
                    subscribed.append(category)
            
            # Create subscription event
            self._add_event(Event(
                type=EventType.SUBSCRIPTION_CHANGE,
                category="system",
                data={
                    "action": "subscribed",
                    "session_id": session_id,
                    "categories": subscribed,
                    "timestamp": datetime.now().isoformat()
                }
            ))
            
            session.update_activity()
            
            return {
                "success": True,
                "subscribed": subscribed,
                "total_subscriptions": len(session.subscriptions)
            }
    
    def unsubscribe(self, session_id: str, categories: Union[str, List[str]] = None) -> Dict[str, Any]:
        """
        Unsubscribe a session from event categories.
        
        Args:
            session_id: Session ID
            categories: Category or list of categories to unsubscribe from (all if None)
            
        Returns:
            Result dictionary
        """
        with self.lock:
            if session_id not in self.sessions:
                return {"success": False, "error": f"Session {session_id} not found"}
            
            session = self.sessions[session_id]
            
            if categories is None:
                # Unsubscribe from all
                categories = list(session.subscriptions)
            elif isinstance(categories, str):
                categories = [categories]
            
            unsubscribed = []
            
            for category in categories:
                # Handle special "all" category
                if category.lower() == EventCategory.ALL.value:
                    for cat in list(session.subscriptions):
                        self._unsubscribe_session(session_id, cat)
                        unsubscribed.append(cat)
                else:
                    if self._unsubscribe_session(session_id, category):
                        unsubscribed.append(category)
            
            # Create unsubscription event
            self._add_event(Event(
                type=EventType.SUBSCRIPTION_CHANGE,
                category="system",
                data={
                    "action": "unsubscribed",
                    "session_id": session_id,
                    "categories": unsubscribed,
                    "timestamp": datetime.now().isoformat()
                }
            ))
            
            session.update_activity()
            
            return {
                "success": True,
                "unsubscribed": unsubscribed,
                "total_subscriptions": len(session.subscriptions)
            }
    
    def poll_events(self, session_id: str, since: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """
        Poll for events that the session is subscribed to.
        
        Args:
            session_id: Session ID
            since: ISO timestamp to get events since (optional)
            limit: Maximum number of events to return
            
        Returns:
            Dictionary with events and metadata
        """
        with self.lock:
            if session_id not in self.sessions:
                return {"success": False, "error": f"Session {session_id} not found"}
            
            session = self.sessions[session_id]
            session.update_poll()
            
            # Parse since timestamp
            since_dt = None
            if since:
                try:
                    since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
                except ValueError:
                    return {"success": False, "error": "Invalid since timestamp format"}
            else:
                # Default to last poll time
                since_dt = session.last_poll
            
            # Collect events from subscribed categories
            events = []
            
            for category in session.subscriptions:
                if category in self.events_by_category:
                    category_events = self.events_by_category[category]
                    
                    for event in category_events:
                        if event.timestamp > since_dt:
                            events.append(event.to_dict())
                            
                            if len(events) >= limit:
                                break
                
                if len(events) >= limit:
                    break
            
            # Sort events by timestamp
            events.sort(key=lambda x: x['timestamp'])
            
            # Limit results
            events = events[:limit]
            
            return {
                "success": True,
                "events": events,
                "count": len(events),
                "session_id": session_id,
                "since": since,
                "timestamp": datetime.now().isoformat()
            }
    
    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get status of a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session status dictionary
        """
        with self.lock:
            if session_id not in self.sessions:
                return {"success": False, "error": f"Session {session_id} not found"}
            
            session = self.sessions[session_id]
            session.update_activity()
            
            return {
                "success": True,
                "session": session.to_dict(),
                "subscriptions_count": len(session.subscriptions),
                "server_stats": self.get_server_stats()
            }
    
    def get_server_stats(self) -> Dict[str, Any]:
        """
        Get server statistics.
        
        Returns:
            Server statistics dictionary
        """
        with self.lock:
            category_stats = {}
            total_events = 0
            
            for category, events in self.events_by_category.items():
                count = len(events)
                category_stats[category] = {
                    "event_count": count,
                    "subscribers": len(self.subscriptions.get(category, set()))
                }
                total_events += count
            
            return {
                "sessions": len(self.sessions),
                "total_events": total_events,
                "categories": category_stats,
                "timestamp": datetime.now().isoformat()
            }
    
    def _subscribe_session(self, session_id: str, category: str) -> bool:
        """
        Subscribe a session to a category.
        
        Args:
            session_id: Session ID
            category: Category to subscribe to
            
        Returns:
            True if successfully subscribed
        """
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        session.subscriptions.add(category)
        self.subscriptions[category].add(session_id)
        
        return True
    
    def _unsubscribe_session(self, session_id: str, category: str) -> bool:
        """
        Unsubscribe a session from a category.
        
        Args:
            session_id: Session ID
            category: Category to unsubscribe from
            
        Returns:
            True if successfully unsubscribed
        """
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        
        if category in session.subscriptions:
            session.subscriptions.remove(category)
        
        if category in self.subscriptions and session_id in self.subscriptions[category]:
            self.subscriptions[category].remove(session_id)
            
            # Clean up empty categories
            if not self.subscriptions[category]:
                del self.subscriptions[category]
        
        return True
    
    def _add_event(self, event: Event) -> None:
        """
        Add an event to the appropriate category.
        
        Args:
            event: Event to add
        """
        with self.lock:
            self.events_by_category[event.category].append(event)
            
            # Also add to 'all' category for subscribers to all events
            if event.category != 'all':
                self.events_by_category['all'].append(event)
    
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
        
        # Add to backend category
        self._add_event(Event(
            type=EventType.BACKEND_CHANGE,
            category=EventCategory.BACKEND.value,
            data=event_data
        ))
        
        # Also add to storage category for compatibility
        self._add_event(Event(
            type=EventType.BACKEND_CHANGE,
            category=EventCategory.STORAGE.value,
            data=event_data
        ))
    
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
        
        self._add_event(Event(
            type=EventType.MIGRATION_EVENT,
            category=EventCategory.MIGRATION.value,
            data=event_data
        ))
    
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
        
        self._add_event(Event(
            type=EventType.STREAM_PROGRESS,
            category=EventCategory.STREAMING.value,
            data=event_data
        ))
    
    def notify_search_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Notify subscribers of search events.
        
        Args:
            event_type: Type of search event
            data: Event data
        """
        event_data = {
            **data,
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
        }
        
        self._add_event(Event(
            type=EventType.SEARCH_EVENT,
            category=EventCategory.SEARCH.value,
            data=event_data
        ))
    
    def notify_system_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Notify subscribers of system events.
        
        Args:
            event_type: Type of system event
            data: Event data
        """
        event_data = {
            **data,
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
        }
        
        self._add_event(Event(
            type=EventType.SYSTEM_EVENT,
            category=EventCategory.SYSTEM.value,
            data=event_data
        ))
    
    def _cleanup_expired_events(self) -> None:
        """Clean up expired events periodically."""
        while self.cleanup_running:
            try:
                cutoff_time = datetime.now() - self.event_ttl
                
                with self.lock:
                    for category, events in self.events_by_category.items():
                        # Remove expired events
                        while events and events[0].timestamp < cutoff_time:
                            events.popleft()
                
                # Sleep for 1 hour before next cleanup
                time.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error in event cleanup: {e}")
                time.sleep(60)  # Sleep 1 minute on error
    
    def shutdown(self) -> None:
        """Shut down the event manager."""
        logger.info("Shutting down JSON-RPC event manager")
        self.cleanup_running = False
        
        if self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5.0)


# Global instance
_global_event_manager: Optional[JSONRPCEventManager] = None


def get_jsonrpc_event_manager() -> JSONRPCEventManager:
    """Get the global JSON-RPC event manager instance."""
    global _global_event_manager
    
    if _global_event_manager is None:
        _global_event_manager = JSONRPCEventManager()
    
    return _global_event_manager


def initialize_jsonrpc_event_manager(**kwargs) -> JSONRPCEventManager:
    """Initialize the global JSON-RPC event manager with custom settings."""
    global _global_event_manager
    
    _global_event_manager = JSONRPCEventManager(**kwargs)
    return _global_event_manager