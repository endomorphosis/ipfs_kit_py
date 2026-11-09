#!/usr/bin/env python3
"""
WebRTC Monitor for the MCP Server.

This module provides monitoring capabilities for WebRTC connections,
helping to debug issues and track the status of connections.
"""

import os
import re
import time
import json
import logging
# import anyio # Replaced by anyio
import threading
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class WebRTCConnectionStats:
    """Statistics for a WebRTC connection."""
    connection_id: str
    created_at: float
    updated_at: float
    ice_state: str = "new"
    connection_state: str = "new"
    signaling_state: str = "stable"
    gathering_state: str = "new"
    tracks: List[str] = field(default_factory=list)
    data_channels: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    async_tasks: Set[str] = field(default_factory=set)
    lifecycle_events: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_event(self, event_type: str, details: Optional[Dict[str, Any]] = None):
        """Add a lifecycle event with timestamp."""
        event = {
            "type": event_type,
            "timestamp": time.time(),
            "details": details or {}
        }
        self.lifecycle_events.append(event)
        self.updated_at = time.time()
    
    def add_error(self, error: str):
        """Add an error with timestamp."""
        self.errors.append(error)
        self.add_event("error", {"error": error})
    
    def update_state(self, state_type: str, state_value: str):
        """Update a state field."""
        if state_type == "ice":
            self.ice_state = state_value
        elif state_type == "connection":
            self.connection_state = state_value
        elif state_type == "signaling":
            self.signaling_state = state_value
        elif state_type == "gathering":
            self.gathering_state = state_value
        
        self.add_event(f"{state_type}_state_change", {"state": state_value})
    
    def add_track(self, track_id: str):
        """Add a track."""
        if track_id not in self.tracks:
            self.tracks.append(track_id)
            self.add_event("track_added", {"track_id": track_id})
    
    def remove_track(self, track_id: str):
        """Remove a track."""
        if track_id in self.tracks:
            self.tracks.remove(track_id)
            self.add_event("track_removed", {"track_id": track_id})
    
    def add_data_channel(self, channel_id: str):
        """Add a data channel."""
        if channel_id not in self.data_channels:
            self.data_channels.append(channel_id)
            self.add_event("data_channel_added", {"channel_id": channel_id})
    
    def remove_data_channel(self, channel_id: str):
        """Remove a data channel."""
        if channel_id in self.data_channels:
            self.data_channels.remove(channel_id)
            self.add_event("data_channel_removed", {"channel_id": channel_id})
    
    def add_async_task(self, task_id: str):
        """Add an async task."""
        self.async_tasks.add(task_id)
        self.add_event("async_task_added", {"task_id": task_id})
    
    def remove_async_task(self, task_id: str):
        """Remove an async task."""
        if task_id in self.async_tasks:
            self.async_tasks.remove(task_id)
            self.add_event("async_task_removed", {"task_id": task_id})
    
    def to_dict(self):
        """Convert to dictionary."""
        return asdict(self)
    
    def to_json(self):
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @property
    def is_connected(self):
        """Check if the connection is established."""
        return self.connection_state == "connected" and self.ice_state == "connected"
    
    @property
    def is_closed(self):
        """Check if the connection is closed."""
        return self.connection_state == "closed" or self.ice_state == "closed"
    
    @property
    def age_seconds(self):
        """Get the age of the connection in seconds."""
        return time.time() - self.created_at
    
    @property
    def idle_seconds(self):
        """Get the idle time of the connection in seconds."""
        return time.time() - self.updated_at
    
    @property
    def has_pending_tasks(self):
        """Check if there are pending async tasks."""
        return len(self.async_tasks) > 0

class WebRTCMonitor:
    """
    Monitor and track WebRTC connections and operations.
    
    This class provides utilities to monitor WebRTC connections,
    track async tasks, and help with debugging WebRTC-related issues.
    """
    
    def __init__(self, 
                log_dir: Optional[str] = None,
                debug_mode: bool = False):
        """
        Initialize the WebRTC monitor.
        
        Args:
            log_dir: Directory for storing logs (if None, logging is disabled)
            debug_mode: Enable detailed debug logging
        """
        self.connections = {}  # connection_id -> WebRTCConnectionStats
        self.log_dir = log_dir
        self.debug_mode = debug_mode
        self.start_time = time.time()
        self.operations = {}  # operation_id -> operation_details
        self.event_log = []
        self.lock = threading.RLock()  # For thread safety
        
        # Create log directory if specified
        if self.log_dir:
            os.makedirs(self.log_dir, exist_ok=True)
            
        logger.info(f"WebRTC monitor initialized (debug_mode={debug_mode})")
    
    def track_connection(self, connection_id: str) -> WebRTCConnectionStats:
        """
        Start tracking a WebRTC connection.
        
        Args:
            connection_id: ID of the connection to track
            
        Returns:
            Connection statistics object
        """
        with self.lock:
            # Create connection stats if it doesn't exist
            if connection_id not in self.connections:
                now = time.time()
                self.connections[connection_id] = WebRTCConnectionStats(
                    connection_id=connection_id,
                    created_at=now,
                    updated_at=now
                )
                self._log_event("connection_created", {"connection_id": connection_id})
                logger.info(f"Started tracking WebRTC connection: {connection_id}")
            
            return self.connections[connection_id]
    
    def untrack_connection(self, connection_id: str):
        """
        Stop tracking a WebRTC connection.
        
        Args:
            connection_id: ID of the connection to stop tracking
        """
        with self.lock:
            if connection_id in self.connections:
                # Get final stats and remove from tracking
                stats = self.connections.pop(connection_id)
                
                # Log the event
                self._log_event("connection_removed", {
                    "connection_id": connection_id,
                    "age_seconds": stats.age_seconds,
                    "final_state": stats.connection_state
                })
                
                # Save final stats to log file if logging is enabled
                if self.log_dir:
                    self._write_connection_log(stats)
                
                logger.info(f"Stopped tracking WebRTC connection: {connection_id}")
                return True
                
            return False
    
    def update_connection_state(self, connection_id: str, state_type: str, state_value: str):
        """
        Update the state of a WebRTC connection.
        
        Args:
            connection_id: ID of the connection
            state_type: Type of state ("ice", "connection", "signaling", "gathering")
            state_value: New state value
        """
        with self.lock:
            stats = self.track_connection(connection_id)
            stats.update_state(state_type, state_value)
            
            self._log_event(f"connection_state_update", {
                "connection_id": connection_id,
                "state_type": state_type,
                "state_value": state_value
            })
            
            logger.debug(f"Updated {state_type} state for {connection_id}: {state_value}")
    
    def add_async_task(self, connection_id: str, task_id: str):
        """
        Track an async task for a WebRTC connection.
        
        Args:
            connection_id: ID of the connection
            task_id: ID of the async task
        """
        with self.lock:
            stats = self.track_connection(connection_id)
            stats.add_async_task(task_id)
            
            self._log_event("async_task_added", {
                "connection_id": connection_id,
                "task_id": task_id
            })
            
            logger.debug(f"Added async task {task_id} for {connection_id}")
    
    def remove_async_task(self, connection_id: str, task_id: str):
        """
        Remove an async task for a WebRTC connection.
        
        Args:
            connection_id: ID of the connection
            task_id: ID of the async task
        """
        with self.lock:
            if connection_id in self.connections:
                stats = self.connections[connection_id]
                stats.remove_async_task(task_id)
                
                self._log_event("async_task_removed", {
                    "connection_id": connection_id,
                    "task_id": task_id
                })
                
                logger.debug(f"Removed async task {task_id} for {connection_id}")
    
    def add_operation(self, operation_id: str, operation_type: str, details: Dict[str, Any] = None):
        """
        Track a WebRTC operation.
        
        Args:
            operation_id: ID of the operation
            operation_type: Type of operation
            details: Additional details about the operation
        """
        with self.lock:
            self.operations[operation_id] = {
                "operation_id": operation_id,
                "operation_type": operation_type,
                "start_time": time.time(),
                "details": details or {},
                "status": "started"
            }
            
            self._log_event("operation_started", {
                "operation_id": operation_id,
                "operation_type": operation_type,
                "details": details
            })
            
            logger.debug(f"Started WebRTC operation: {operation_type} ({operation_id})")
    
    def update_operation(self, operation_id: str, status: str, result: Dict[str, Any] = None):
        """
        Update a WebRTC operation.
        
        Args:
            operation_id: ID of the operation
            status: New status ("completed", "failed", "canceled")
            result: Operation result
        """
        with self.lock:
            if operation_id in self.operations:
                operation = self.operations[operation_id]
                operation["status"] = status
                operation["end_time"] = time.time()
                operation["duration"] = operation["end_time"] - operation["start_time"]
                
                if result:
                    operation["result"] = result
                
                self._log_event("operation_updated", {
                    "operation_id": operation_id,
                    "status": status,
                    "duration": operation["duration"],
                    "result": result
                })
                
                logger.debug(f"Updated WebRTC operation: {operation_id} ({status})")
                
                # If logging is enabled, write operation log
                if self.log_dir and status in ("completed", "failed", "canceled"):
                    self._write_operation_log(operation)
    
    def get_connection_stats(self, connection_id: str = None):
        """
        Get statistics for WebRTC connections.
        
        Args:
            connection_id: ID of the specific connection to get stats for
                          If None, returns stats for all connections
        
        Returns:
            Dictionary with connection statistics
        """
        with self.lock:
            if connection_id:
                # Get stats for a specific connection
                if connection_id in self.connections:
                    return {
                        "connection": self.connections[connection_id].to_dict(),
                        "timestamp": time.time()
                    }
                return {"error": "Connection not found", "timestamp": time.time()}
            
            # Get stats for all connections
            return {
                "connections": {conn_id: stats.to_dict() for conn_id, stats in self.connections.items()},
                "count": len(self.connections),
                "timestamp": time.time()
            }
    
    def get_active_operations(self):
        """
        Get active WebRTC operations.
        
        Returns:
            Dictionary with active operations
        """
        with self.lock:
            active_operations = {}
            for op_id, operation in self.operations.items():
                if operation["status"] == "started":
                    active_operations[op_id] = operation
            
            return {
                "operations": active_operations,
                "count": len(active_operations),
                "timestamp": time.time()
            }
    
    def get_pending_tasks(self):
        """
        Get all pending async tasks.
        
        Returns:
            Dictionary with pending tasks by connection
        """
        with self.lock:
            pending_tasks = {}
            for conn_id, stats in self.connections.items():
                if stats.has_pending_tasks:
                    pending_tasks[conn_id] = list(stats.async_tasks)
            
            return {
                "tasks": pending_tasks,
                "count": sum(len(tasks) for tasks in pending_tasks.values()),
                "timestamp": time.time()
            }
    
    def get_summary(self):
        """
        Get a summary of WebRTC monitoring.
        
        Returns:
            Dictionary with monitoring summary
        """
        with self.lock:
            # Count connections by state
            connection_states = {
                "total": len(self.connections),
                "connected": 0,
                "disconnected": 0,
                "new": 0,
                "connecting": 0,
                "closed": 0,
                "failed": 0
            }
            
            for stats in self.connections.values():
                if stats.is_connected:
                    connection_states["connected"] += 1
                elif stats.is_closed:
                    connection_states["closed"] += 1
                elif stats.connection_state == "failed":
                    connection_states["failed"] += 1
                elif stats.connection_state == "connecting":
                    connection_states["connecting"] += 1
                elif stats.connection_state == "disconnected":
                    connection_states["disconnected"] += 1
                else:
                    connection_states["new"] += 1
            
            # Count operations by status
            operation_stats = {
                "total": len(self.operations),
                "started": 0,
                "completed": 0,
                "failed": 0,
                "canceled": 0
            }
            
            for operation in self.operations.values():
                status = operation["status"]
                if status in operation_stats:
                    operation_stats[status] += 1
            
            # Get pending tasks count
            pending_tasks = self.get_pending_tasks()
            
            return {
                "uptime_seconds": time.time() - self.start_time,
                "connection_states": connection_states,
                "operation_stats": operation_stats,
                "pending_tasks": pending_tasks["count"],
                "event_count": len(self.event_log),
                "timestamp": time.time(),
                "debug_mode": self.debug_mode,
                "logging_enabled": self.log_dir is not None
            }
    
    def _log_event(self, event_type: str, details: Dict[str, Any] = None):
        """Log an event to the internal event log."""
        event = {
            "type": event_type,
            "timestamp": time.time(),
            "details": details or {}
        }
        
        self.event_log.append(event)
        
        # If debug mode is enabled, log to logger
        if self.debug_mode:
            logger.debug(f"WebRTC event: {event_type} - {details}")
    
    def _write_connection_log(self, stats: WebRTCConnectionStats):
        """Write connection statistics to a log file."""
        if not self.log_dir:
            return
        
        try:
            # Create connections directory if it doesn't exist
            connections_dir = os.path.join(self.log_dir, "connections")
            os.makedirs(connections_dir, exist_ok=True)
            
            # Create log filename with timestamp and connection ID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{stats.connection_id}.json"
            log_path = os.path.join(connections_dir, filename)
            
            # Write the log file
            with open(log_path, "w") as f:
                json.dump(stats.to_dict(), f, indent=2)
                
            logger.debug(f"Wrote connection log: {log_path}")
            
        except Exception as e:
            logger.error(f"Error writing connection log: {e}")
    
    def _write_operation_log(self, operation: Dict[str, Any]):
        """Write operation details to a log file."""
        if not self.log_dir:
            return
        
        try:
            # Create operations directory if it doesn't exist
            operations_dir = os.path.join(self.log_dir, "operations")
            os.makedirs(operations_dir, exist_ok=True)
            
            # Create log filename with timestamp and operation ID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            op_type = re.sub(r'[^a-zA-Z0-9]', '_', operation["operation_type"])
            filename = f"{timestamp}_{op_type}_{operation['operation_id']}.json"
            log_path = os.path.join(operations_dir, filename)
            
            # Write the log file
            with open(log_path, "w") as f:
                json.dump(operation, f, indent=2)
                
            logger.debug(f"Wrote operation log: {log_path}")
            
        except Exception as e:
            logger.error(f"Error writing operation log: {e}")

class AsyncTaskTracker:
    """
    Utility for tracking and managing async tasks in WebRTC operations.
    
    This class helps to ensure that async tasks are properly tracked and
    cleaned up, even if exceptions occur, preventing memory leaks and
    resource exhaustion.
    """
    
    def __init__(self, monitor: WebRTCMonitor):
        """
        Initialize the async task tracker.
        
        Args:
            monitor: WebRTC monitor instance
        """
        self.monitor = monitor
    
    async def track_task(self, connection_id: str, coro, task_name: str = None):
        """
        Track an async task for a WebRTC connection.
        
        This method ensures that the task is properly tracked and removed
        from tracking when it completes, even if an exception occurs.
        
        Args:
            connection_id: ID of the WebRTC connection
            coro: Coroutine to run as a task
            task_name: Optional name for the task (for debugging)
            
        Returns:
            Result of the coroutine
        """
        # Generate a task ID if not provided
        task_id = task_name or f"task_{id(coro)}"
        task_id = f"{task_id}_{int(time.time() * 1000)}"
        
        # Track the task
        self.monitor.add_async_task(connection_id, task_id)
        
        try:
            # Run the coroutine
            return await coro
            
        finally:
            # Always remove the task from tracking when it completes
            self.monitor.remove_async_task(connection_id, task_id)
    
    async def batch_track_tasks(self, connection_id: str, coros, task_prefix: str = None):
        """
        Track multiple async tasks for a WebRTC connection.
        
        Args:
            connection_id: ID of the WebRTC connection
            coros: List of coroutines to run as tasks
            task_prefix: Optional prefix for task names
            
        Returns:
            List of results from the coroutines
        """
        tasks = []
        
        for i, coro in enumerate(coros):
            task_name = f"{task_prefix or 'batch'}_{i}"
            task = anyio.create_task(self.track_task(connection_id, coro, task_name))
            tasks.append(task)
        
        return await anyio.gather(*tasks, return_exceptions=True)

# Helper functions for using the monitor with the WebRTC AnyIO fix

def wrap_webrtc_method(func, monitor: WebRTCMonitor, connection_id: str = None):
    """
    Wrap a WebRTC method to track its execution and monitor connections.
    
    Args:
        func: The WebRTC method to wrap
        monitor: WebRTC monitor instance
        connection_id: Optional connection ID to track (if None, extracted from arguments)
        
    Returns:
        Wrapped function
    """
    def wrapper(*args, **kwargs):
        # Extract connection ID if not provided
        conn_id = connection_id
        if conn_id is None and len(args) > 1:
            # Assuming connection_id is the first argument after self
            conn_id = args[1]
        
        # Generate operation ID
        operation_id = f"{func.__name__}_{int(time.time() * 1000)}"
        
        # Track the operation
        monitor.add_operation(operation_id, func.__name__, {
            "connection_id": conn_id,
            "args": str(args[1:]),  # Skip self
            "kwargs": str(kwargs)
        })
        
        try:
            # Run the wrapped function
            result = func(*args, **kwargs)
            
            # Update operation status
            is_successful = isinstance(result, dict) and result.get("success", False)
            status = "completed" if is_successful else "failed"
            monitor.update_operation(operation_id, status, result)
            
            # Update connection tracking if needed
            if conn_id and is_successful:
                if "close" in func.__name__:
                    monitor.untrack_connection(conn_id)
            
            return result
            
        except Exception as e:
            # Update operation status
            monitor.update_operation(operation_id, "failed", {
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise
    
    return wrapper

def wrap_async_webrtc_method(func, monitor: WebRTCMonitor, connection_id: str = None):
    """
    Wrap an async WebRTC method to track its execution and monitor connections.
    
    Args:
        func: The async WebRTC method to wrap
        monitor: WebRTC monitor instance
        connection_id: Optional connection ID to track (if None, extracted from arguments)
        
    Returns:
        Wrapped async function
    """
    async def wrapper(*args, **kwargs):
        # Extract connection ID if not provided
        conn_id = connection_id
        if conn_id is None and len(args) > 1:
            # Assuming connection_id is the first argument after self
            conn_id = args[1]
        
        # Generate operation ID
        operation_id = f"{func.__name__}_{int(time.time() * 1000)}"
        
        # Track the operation
        monitor.add_operation(operation_id, func.__name__, {
            "connection_id": conn_id,
            "args": str(args[1:]),  # Skip self
            "kwargs": str(kwargs)
        })
        
        try:
            # Run the wrapped function
            result = await func(*args, **kwargs)
            
            # Update operation status
            is_successful = isinstance(result, dict) and result.get("success", False)
            status = "completed" if is_successful else "failed"
            monitor.update_operation(operation_id, status, result)
            
            # Update connection tracking if needed
            if conn_id and is_successful:
                if "close" in func.__name__:
                    monitor.untrack_connection(conn_id)
            
            return result
            
        except Exception as e:
            # Update operation status
            monitor.update_operation(operation_id, "failed", {
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise
    
    return wrapper

def apply_webrtc_monitoring(ipfs_model, log_dir: str = None, debug_mode: bool = False):
    """
    Apply WebRTC monitoring to an IPFS model.
    
    Args:
        ipfs_model: IPFS model instance
        log_dir: Directory to store logs
        debug_mode: Enable debug mode
        
    Returns:
        WebRTC monitor instance
    """
    # Create monitor
    monitor = WebRTCMonitor(log_dir=log_dir, debug_mode=debug_mode)
    
    # Attach monitor to model
    ipfs_model.webrtc_monitor = monitor
    
    # Wrap WebRTC methods with monitoring
    if hasattr(ipfs_model, "stop_webrtc_streaming"):
        ipfs_model.stop_webrtc_streaming = wrap_webrtc_method(
            ipfs_model.stop_webrtc_streaming, monitor
        )
    if hasattr(ipfs_model, "close_webrtc_connection"):
        ipfs_model.close_webrtc_connection = wrap_webrtc_method(
            ipfs_model.close_webrtc_connection, monitor
        )
    if hasattr(ipfs_model, "close_all_webrtc_connections"):
        ipfs_model.close_all_webrtc_connections = wrap_webrtc_method(
            ipfs_model.close_all_webrtc_connections, monitor
        )
    
    # Wrap async WebRTC methods if they exist
    if hasattr(ipfs_model, "async_stop_webrtc_streaming"):
        ipfs_model.async_stop_webrtc_streaming = wrap_async_webrtc_method(
            ipfs_model.async_stop_webrtc_streaming, monitor
        )
    if hasattr(ipfs_model, "async_close_webrtc_connection"):
        ipfs_model.async_close_webrtc_connection = wrap_async_webrtc_method(
            ipfs_model.async_close_webrtc_connection, monitor
        )
    if hasattr(ipfs_model, "async_close_all_webrtc_connections"):
        ipfs_model.async_close_all_webrtc_connections = wrap_async_webrtc_method(
            ipfs_model.async_close_all_webrtc_connections, monitor
        )
    
    logger.info(f"Applied WebRTC monitoring to IPFS model")
    return monitor

if __name__ == "__main__":
    # Example usage
    monitor = WebRTCMonitor(debug_mode=True)
    
    # Track some connections
    monitor.track_connection("conn-1")
    monitor.track_connection("conn-2")
    
    # Update connection states
    monitor.update_connection_state("conn-1", "ice", "connected")
    monitor.update_connection_state("conn-1", "connection", "connected")
    
    # Add some operations
    monitor.add_operation("op-1", "close_connection", {"connection_id": "conn-1"})
    monitor.update_operation("op-1", "completed", {"success": True})
    
    # Print summary
    print(json.dumps(monitor.get_summary(), indent=2))
