"""
Audit logging module for the MCP auth system.

This module provides utilities for audit logging operations in the auth system,
tracking authentication and authorization events for security purposes.
"""

import logging
import time
import json
import os
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional, Union, List, Counter
import enum
import aiofiles

# Create a dedicated logger for audit events
_audit_logger = logging.getLogger("ipfs_kit_py.mcp.auth.audit")


def get_audit_logger() -> logging.Logger:
    """
    Get the audit logger instance.
    
    Returns:
        logging.Logger: The configured audit logger.
    """
    return _audit_logger


def log_auth_event(
    event_type: str,
    user_id: Optional[str] = None,
    api_key_id: Optional[str] = None,
    resource: Optional[str] = None,
    action: Optional[str] = None,
    status: str = "success",
    details: Optional[Dict[str, Any]] = None,
    source_ip: Optional[str] = None,
    timestamp: Optional[float] = None,
) -> None:
    """
    Log an authentication or authorization event.
    
    Args:
        event_type: Type of event (login, logout, access, etc.)
        user_id: ID of the user associated with the event
        api_key_id: ID of the API key used (if applicable)
        resource: Resource being accessed
        action: Action being performed on the resource
        status: Outcome of the event (success, failure, etc.)
        details: Additional details about the event
        source_ip: Source IP address of the request
        timestamp: Event timestamp (if None, current time is used)
    """
    if timestamp is None:
        timestamp = time.time()
        
    event_data = {
        "event_type": event_type,
        "timestamp": timestamp,
        "datetime": datetime.fromtimestamp(timestamp).isoformat(),
        "status": status,
    }
    
    if user_id:
        event_data["user_id"] = user_id
    if api_key_id:
        event_data["api_key_id"] = api_key_id
    if resource:
        event_data["resource"] = resource
    if action:
        event_data["action"] = action
    if source_ip:
        event_data["source_ip"] = source_ip
    if details:
        event_data["details"] = details
        
    logger = get_audit_logger()
    
    if status == "failure":
        logger.warning(f"Auth event: {event_type}", extra={"audit": event_data})
    else:
        logger.info(f"Auth event: {event_type}", extra={"audit": event_data})


def configure_audit_logger(
    log_file: Optional[str] = None,
    log_level: int = logging.INFO,
    format_string: Optional[str] = None,
) -> None:
    """
    Configure the audit logger with specific settings.
    
    Args:
        log_file: Path to the audit log file
        log_level: Logging level
        format_string: Custom format string for log entries
    """
    logger = get_audit_logger()
    logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicate logging
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    if format_string is None:
        format_string = "%(asctime)s [%(levelname)8s] %(message)s - %(audit)s"
        
    formatter = logging.Formatter(format_string)
    
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Always add a stream handler for console output
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)


class AuditEventType(enum.Enum):
    """Enum defining the types of audit events that can be logged."""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    PERMISSION_CHECK = "permission_check"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    BACKEND_ACCESS_ATTEMPT = "backend_access_attempt"
    BACKEND_ACCESS_GRANTED = "backend_access_granted"
    BACKEND_ACCESS_DENIED = "backend_access_denied"
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    API_KEY_USED = "api_key_used"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    LOGIN = "login"
    LOGOUT = "logout"
    ACCESS = "access"
    ERROR = "error"


class AuditLogEntry:
    """Class representing a single audit log entry."""
    def __init__(self, event_type, user_id=None, resource_type=None, resource_id=None, timestamp=None, details=None):
        self.event_type = event_type
        self.user_id = user_id
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.timestamp = timestamp or time.time()
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the audit log entry to a dictionary representation."""
        return {
            "event_type": self.event_type,
            "user_id": self.user_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "details": self.details
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditLogEntry':
        """Create an AuditLogEntry object from a dictionary."""
        return cls(
            event_type=data.get("event_type"),
            user_id=data.get("user_id"),
            resource_type=data.get("resource_type"),
            resource_id=data.get("resource_id"),
            timestamp=data.get("timestamp"),
            details=data.get("details", {})
        )


class AuditLogger:
    """
    Advanced audit logging system for tracking authentication and authorization events.
    
    This class provides methods for logging various security events and querying
    the audit log history.
    """
    
    def __init__(self, log_file=None, console_logging=True, file_logging=True, json_logging=False):
        """
        Initialize the audit logger.
        
        Args:
            log_file: Path to the audit log file
            console_logging: Whether to log to console
            file_logging: Whether to log to file
            json_logging: Whether to use JSON format for the log file
        """
        self.log_file = log_file or "audit.log"
        self.console_logging = console_logging
        self.file_logging = file_logging
        self.json_logging = json_logging
        self.in_memory_logs = []
        self.running = False
        self.log_queue = asyncio.Queue()
        self._worker_task = None
    
    async def start(self):
        """Start the audit logger worker."""
        if self.running:
            return
        
        self.running = True
        
        # Configure the standard logger
        level = logging.INFO
        format_string = "%(asctime)s [%(levelname)8s] %(message)s"
        
        logger = get_audit_logger()
        logger.setLevel(level)
        
        # Remove existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        formatter = logging.Formatter(format_string)
        
        if self.console_logging:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        if self.file_logging and not self.json_logging:
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        # Start the worker task for JSON logging
        if self.json_logging:
            self._worker_task = asyncio.create_task(self._log_worker())
    
    async def stop(self):
        """Stop the audit logger worker."""
        if not self.running:
            return
        
        self.running = False
        
        if self._worker_task:
            # Give time for the worker to process remaining logs
            await asyncio.sleep(0.2)
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
    
    async def _log_worker(self):
        """Worker task for processing log entries asynchronously."""
        while self.running:
            try:
                entry = await self.log_queue.get()
                
                # Add to in-memory logs
                self.in_memory_logs.append(entry)
                while len(self.in_memory_logs) > 1000:  # Limit in-memory logs
                    self.in_memory_logs.pop(0)
                
                # Write to JSON log file if enabled
                if self.file_logging and self.json_logging:
                    try:
                        log_dir = os.path.dirname(self.log_file)
                        if log_dir and not os.path.exists(log_dir):
                            os.makedirs(log_dir)
                        
                        async with aiofiles.open(self.log_file, "a") as f:
                            await f.write(json.dumps(entry.to_dict()) + "\n")
                    except Exception as e:
                        print(f"Error writing to audit log file: {e}")
                
                self.log_queue.task_done()
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in audit log worker: {e}")
                await asyncio.sleep(1)  # Avoid tight loop on error
    
    async def log_event(self, entry: AuditLogEntry):
        """
        Log an audit event.
        
        Args:
            entry: The audit log entry to record
        """
        await self.log_queue.put(entry)
        
        # Also log using the standard logger
        log_auth_event(
            event_type=entry.event_type,
            user_id=entry.user_id,
            resource=entry.resource_type,
            action=entry.resource_id,
            details=entry.details
        )
    
    async def log_login(self, success, user_id, username, ip_address, user_agent):
        """
        Log a user login event.
        
        Args:
            success: Whether the login was successful
            user_id: ID of the user
            username: Username of the user
            ip_address: IP address of the client
            user_agent: User agent of the client
        """
        event_type = AuditEventType.USER_LOGIN
        details = {
            "success": success,
            "username": username,
            "ip_address": ip_address,
            "user_agent": user_agent
        }
        
        entry = AuditLogEntry(
            event_type=event_type.value,
            user_id=user_id,
            resource_type="auth",
            resource_id="login",
            details=details
        )
        
        await self.log_event(entry)
    
    async def log_permission_check(self, user_id, permission, resource_type, resource_id, granted):
        """
        Log a permission check event.
        
        Args:
            user_id: ID of the user
            permission: Permission being checked
            resource_type: Type of resource being accessed
            resource_id: ID of the resource being accessed
            granted: Whether permission was granted
        """
        event_type = AuditEventType.PERMISSION_GRANTED if granted else AuditEventType.PERMISSION_DENIED
        details = {
            "permission": permission,
            "granted": granted
        }
        
        entry = AuditLogEntry(
            event_type=event_type.value,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details
        )
        
        await self.log_event(entry)
    
    async def log_backend_access(self, success, backend_id, user_id, username, ip_address, action):
        """
        Log a backend access event.
        
        Args:
            success: Whether access was granted
            backend_id: ID of the backend
            user_id: ID of the user
            username: Username of the user
            ip_address: IP address of the client
            action: Action being performed
        """
        event_type = AuditEventType.BACKEND_ACCESS_GRANTED if success else AuditEventType.BACKEND_ACCESS_DENIED
        details = {
            "success": success,
            "username": username,
            "ip_address": ip_address,
            "action": action
        }
        
        entry = AuditLogEntry(
            event_type=event_type.value,
            user_id=user_id,
            resource_type="backend",
            resource_id=backend_id,
            details=details
        )
        
        await self.log_event(entry)
    
    async def get_recent_logs(self, limit=100, event_type=None, user_id=None):
        """
        Get recent audit log entries.
        
        Args:
            limit: Maximum number of logs to return
            event_type: Filter by event type
            user_id: Filter by user ID
        
        Returns:
            List of matching audit log entries
        """
        logs = self.in_memory_logs.copy()
        
        # Apply filters
        if event_type:
            logs = [log for log in logs if log.event_type == event_type.value]
        
        if user_id:
            logs = [log for log in logs if log.user_id == user_id]
        
        # Sort by timestamp (newest first)
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Apply limit
        return logs[:limit]
    
    async def get_event_counts(self):
        """
        Get counts of different event types.
        
        Returns:
            Counter object with event type counts
        """
        counts = Counter()
        for log in self.in_memory_logs:
            event_type = log.event_type
            
            # Convert string event types to enum
            for enum_type in AuditEventType:
                if enum_type.value == event_type:
                    counts[enum_type] += 1
                    break
        
        return counts


def get_instance():
    """
    Get a singleton instance of the audit logger.
    
    Returns:
        Instance of the audit logger
    """
    # This is a stub for the singleton pattern
    return get_audit_logger()
