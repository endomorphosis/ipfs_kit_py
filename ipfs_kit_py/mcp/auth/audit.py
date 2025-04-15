"""
Authentication Audit Logging System for MCP server.

This module implements comprehensive audit logging for authentication and authorization
events as specified in the MCP roadmap for Phase 1: Core Functionality Enhancements (Q3 2025).

Key features:
- Detailed audit logging for all authentication events
- Structured log format for easy querying and analysis
- Support for log forwarding to external systems
- Compliance-focused event capture
"""

import logging
import json
import time
import os
import asyncio
from typing import Dict, Any, Optional, List, Set, Union
from datetime import datetime
from enum import Enum

# Configure logging
logger = logging.getLogger(__name__)

# Define audit event types
class AuditEventType(str, Enum):
    """Types of audit events."""
    # Authentication events
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_REGISTER = "user_register"
    LOGIN_FAILURE = "login_failure"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET = "password_reset"
    
    # Session events
    SESSION_CREATE = "session_create"
    SESSION_EXPIRE = "session_expire"
    SESSION_REVOKE = "session_revoke"
    
    # Token events
    TOKEN_CREATE = "token_create"
    TOKEN_REFRESH = "token_refresh"
    TOKEN_REVOKE = "token_revoke"
    TOKEN_VERIFY = "token_verify"
    TOKEN_VERIFY_FAILURE = "token_verify_failure"
    
    # API key events
    API_KEY_CREATE = "api_key_create"
    API_KEY_REVOKE = "api_key_revoke"
    API_KEY_USE = "api_key_use"
    API_KEY_USE_FAILURE = "api_key_use_failure"
    
    # User management events
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    USER_LOCK = "user_lock"
    USER_UNLOCK = "user_unlock"
    
    # Role and permission events
    ROLE_CREATE = "role_create"
    ROLE_UPDATE = "role_update"
    ROLE_DELETE = "role_delete"
    PERMISSION_CREATE = "permission_create"
    PERMISSION_UPDATE = "permission_update"
    PERMISSION_DELETE = "permission_delete"
    
    # Access control events
    PERMISSION_CHECK = "permission_check"
    PERMISSION_DENIED = "permission_denied"
    PERMISSION_GRANTED = "permission_granted"
    
    # OAuth events
    OAUTH_LOGIN = "oauth_login"
    OAUTH_LINK = "oauth_link"
    OAUTH_FAILURE = "oauth_failure"
    
    # Backend authorization events
    BACKEND_ACCESS_ATTEMPT = "backend_access_attempt"
    BACKEND_ACCESS_DENIED = "backend_access_denied"
    BACKEND_ACCESS_GRANTED = "backend_access_granted"


class AuditLogEntry:
    """Structured audit log entry."""
    
    def __init__(
        self,
        event_type: AuditEventType,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
        status: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize an audit log entry.
        
        Args:
            event_type: Type of audit event
            user_id: ID of user performing the action
            username: Username of user performing the action
            ip_address: IP address of client
            user_agent: User agent of client
            resource_id: ID of resource being accessed
            resource_type: Type of resource being accessed
            action: Action being performed
            status: Status of the action (success, failure, etc.)
            details: Additional details about the event
        """
        self.event_type = event_type
        self.user_id = user_id
        self.username = username
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.resource_id = resource_id
        self.resource_type = resource_type
        self.action = action
        self.status = status
        self.details = details or {}
        self.timestamp = time.time()
        self.id = f"audit_{int(self.timestamp)}_{os.urandom(4).hex()}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "id": self.id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "user_id": self.user_id,
            "username": self.username,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "action": self.action,
            "status": self.status,
            "details": self.details,
        }
    
    def __str__(self) -> str:
        """String representation of the audit log entry."""
        return (
            f"[AUDIT] {self.event_type} | {datetime.fromtimestamp(self.timestamp).isoformat()} | "
            f"User: {self.username or self.user_id or 'anonymous'} | "
            f"Resource: {self.resource_type}/{self.resource_id} | "
            f"Action: {self.action} | Status: {self.status}"
        )


class AuditLogger:
    """
    Centralized audit logging service for authentication and authorization events.
    
    This class provides methods for logging various authentication and authorization
    events in a structured, consistent format.
    """
    
    def __init__(
        self,
        log_file: str = "auth_audit.log",
        console_logging: bool = True,
        file_logging: bool = True,
        json_logging: bool = True,
        external_handler: Optional[callable] = None,
    ):
        """
        Initialize the audit logger.
        
        Args:
            log_file: Path to audit log file
            console_logging: Whether to log to console
            file_logging: Whether to log to file
            json_logging: Whether to use JSON format for logs
            external_handler: Optional external logging handler for integration
        """
        self.log_file = log_file
        self.console_logging = console_logging
        self.file_logging = file_logging
        self.json_logging = json_logging
        self.external_handler = external_handler
        
        # Setup loggers
        self.setup_loggers()
        
        # Set up in-memory queue for async logging
        self.queue = asyncio.Queue()
        
        # In-memory log storage for recent entries (limited capacity)
        self.recent_logs: List[AuditLogEntry] = []
        self.max_recent_logs = 1000
        
        # Track event counts
        self.event_counts: Dict[str, int] = {}
        
        # Background task references
        self.log_processor_task = None
    
    def setup_loggers(self):
        """Set up console and file loggers."""
        # Create audit logger
        self.logger = logging.getLogger("mcp.auth.audit")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Add console handler if enabled
        if self.console_logging:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            if self.json_logging:
                formatter = logging.Formatter("%(message)s")
            else:
                formatter = logging.Formatter(
                    "[%(levelname)s] %(asctime)s - AUDIT - %(message)s"
                )
            
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        # Add file handler if enabled
        if self.file_logging:
            try:
                file_handler = logging.FileHandler(self.log_file)
                file_handler.setLevel(logging.INFO)
                
                if self.json_logging:
                    formatter = logging.Formatter("%(message)s")
                else:
                    formatter = logging.Formatter(
                        "[%(levelname)s] %(asctime)s - AUDIT - %(message)s"
                    )
                
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
            except Exception as e:
                logging.error(f"Failed to create audit log file handler: {e}")
    
    async def start(self):
        """Start the audit logger background tasks."""
        # Start log processor task
        if not self.log_processor_task:
            self.log_processor_task = asyncio.create_task(self._process_log_queue())
            logging.info("Started audit log processor")
    
    async def stop(self):
        """Stop the audit logger background tasks."""
        # Cancel log processor task
        if self.log_processor_task:
            self.log_processor_task.cancel()
            try:
                await self.log_processor_task
            except asyncio.CancelledError:
                pass
            self.log_processor_task = None
            logging.info("Stopped audit log processor")
    
    async def _process_log_queue(self):
        """Background task to process log entries from the queue."""
        while True:
            try:
                # Get entry from queue
                entry = await self.queue.get()
                
                # Log entry
                self._log_entry(entry)
                
                # Mark task as done
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error processing audit log entry: {e}")
    
    def _log_entry(self, entry: AuditLogEntry):
        """Log an audit entry to configured outputs."""
        try:
            # Log to file/console
            if self.json_logging:
                log_message = json.dumps(entry.to_dict())
            else:
                log_message = str(entry)
            
            self.logger.info(log_message)
            
            # Call external handler if configured
            if self.external_handler:
                try:
                    self.external_handler(entry)
                except Exception as e:
                    logging.error(f"Error in external audit handler: {e}")
            
            # Add to recent logs (with capacity limit)
            self.recent_logs.append(entry)
            if len(self.recent_logs) > self.max_recent_logs:
                self.recent_logs.pop(0)
            
            # Update event counts
            self.event_counts[entry.event_type] = self.event_counts.get(entry.event_type, 0) + 1
            
        except Exception as e:
            logging.error(f"Error logging audit entry: {e}")
    
    async def log(self, entry: AuditLogEntry):
        """
        Log an audit event.
        
        Args:
            entry: Audit log entry to record
        """
        # Add to queue for async processing
        await self.queue.put(entry)
    
    async def log_login(
        self,
        success: bool,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Log a user login event.
        
        Args:
            success: Whether login was successful
            user_id: User ID
            username: Username
            ip_address: Client IP address
            user_agent: Client user agent
            details: Additional details
        """
        event_type = AuditEventType.USER_LOGIN if success else AuditEventType.LOGIN_FAILURE
        status = "success" if success else "failure"
        
        entry = AuditLogEntry(
            event_type=event_type,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            action="login",
            status=status,
            details=details,
        )
        
        await self.log(entry)
    
    async def log_token_creation(
        self,
        token_type: str,
        user_id: str,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        expires_at: Optional[float] = None,
        session_id: Optional[str] = None,
    ):
        """
        Log token creation event.
        
        Args:
            token_type: Type of token (access, refresh)
            user_id: User ID
            username: Username
            ip_address: Client IP address
            user_agent: Client user agent
            expires_at: Token expiration timestamp
            session_id: Associated session ID
        """
        details = {
            "token_type": token_type,
            "expires_at": expires_at,
            "session_id": session_id,
        }
        
        entry = AuditLogEntry(
            event_type=AuditEventType.TOKEN_CREATE,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            resource_type="token",
            resource_id=session_id,
            action="create",
            status="success",
            details=details,
        )
        
        await self.log(entry)
    
    async def log_permission_check(
        self,
        user_id: str,
        permission: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        granted: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Log permission check event.
        
        Args:
            user_id: User ID
            permission: Permission being checked
            resource_type: Type of resource being accessed
            resource_id: ID of resource being accessed
            granted: Whether permission was granted
            details: Additional details
        """
        event_type = AuditEventType.PERMISSION_GRANTED if granted else AuditEventType.PERMISSION_DENIED
        status = "granted" if granted else "denied"
        
        entry = AuditLogEntry(
            event_type=event_type,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action="check_permission",
            status=status,
            details={
                "permission": permission,
                **(details or {}),
            },
        )
        
        await self.log(entry)
    
    async def log_api_key_use(
        self,
        success: bool,
        key_id: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Log API key usage event.
        
        Args:
            success: Whether API key use was successful
            key_id: API key ID
            user_id: User ID associated with the key
            ip_address: Client IP address
            user_agent: Client user agent
            details: Additional details
        """
        event_type = AuditEventType.API_KEY_USE if success else AuditEventType.API_KEY_USE_FAILURE
        status = "success" if success else "failure"
        
        entry = AuditLogEntry(
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            resource_type="api_key",
            resource_id=key_id,
            action="use",
            status=status,
            details=details,
        )
        
        await self.log(entry)
    
    async def log_backend_access(
        self,
        success: bool,
        backend_id: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Log backend access event.
        
        Args:
            success: Whether access was granted
            backend_id: Backend ID
            user_id: User ID
            username: Username
            ip_address: Client IP address
            action: Action being performed on the backend
            details: Additional details
        """
        event_type = (
            AuditEventType.BACKEND_ACCESS_GRANTED if success 
            else AuditEventType.BACKEND_ACCESS_DENIED
        )
        status = "granted" if success else "denied"
        
        entry = AuditLogEntry(
            event_type=event_type,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            resource_type="backend",
            resource_id=backend_id,
            action=action or "access",
            status=status,
            details=details,
        )
        
        await self.log(entry)
    
    async def log_oauth_login(
        self,
        success: bool,
        provider: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Log OAuth login event.
        
        Args:
            success: Whether OAuth login was successful
            provider: OAuth provider (github, google, etc.)
            user_id: User ID
            username: Username
            ip_address: Client IP address
            user_agent: Client user agent
            details: Additional details
        """
        event_type = AuditEventType.OAUTH_LOGIN if success else AuditEventType.OAUTH_FAILURE
        status = "success" if success else "failure"
        
        entry = AuditLogEntry(
            event_type=event_type,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            resource_type="oauth",
            resource_id=provider,
            action="login",
            status=status,
            details=details,
        )
        
        await self.log(entry)
    
    async def get_recent_logs(
        self,
        limit: int = 100,
        event_types: Optional[List[AuditEventType]] = None,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recent audit logs with filtering.
        
        Args:
            limit: Maximum number of logs to return
            event_types: Filter by event types
            user_id: Filter by user ID
            resource_type: Filter by resource type
            resource_id: Filter by resource ID
            start_time: Filter by start time (timestamp)
            end_time: Filter by end time (timestamp)
            
        Returns:
            List of audit log entries as dictionaries
        """
        # Make a copy of recent logs
        logs = self.recent_logs.copy()
        
        # Apply filters
        filtered_logs = []
        for log in reversed(logs):  # Most recent first
            # Apply event type filter
            if event_types and log.event_type not in event_types:
                continue
            
            # Apply user filter
            if user_id and log.user_id != user_id:
                continue
            
            # Apply resource type filter
            if resource_type and log.resource_type != resource_type:
                continue
            
            # Apply resource ID filter
            if resource_id and log.resource_id != resource_id:
                continue
            
            # Apply time filters
            if start_time and log.timestamp < start_time:
                continue
                
            if end_time and log.timestamp > end_time:
                continue
            
            # Add to filtered logs
            filtered_logs.append(log.to_dict())
            
            # Check limit
            if len(filtered_logs) >= limit:
                break
        
        return filtered_logs
    
    async def get_event_counts(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> Dict[str, int]:
        """
        Get counts of audit events, optionally filtered by time.
        
        Args:
            start_time: Filter by start time (timestamp)
            end_time: Filter by end time (timestamp)
            
        Returns:
            Dictionary of event types to counts
        """
        if start_time is None and end_time is None:
            # Return overall counts
            return self.event_counts.copy()
        
        # Filter by time
        counts = {}
        for log in self.recent_logs:
            if start_time and log.timestamp < start_time:
                continue
                
            if end_time and log.timestamp > end_time:
                continue
            
            # Count event
            counts[log.event_type] = counts.get(log.event_type, 0) + 1
        
        return counts


# Singleton instance
_instance = None

def get_instance(
    log_file: str = "auth_audit.log",
    console_logging: bool = True,
    file_logging: bool = True,
    json_logging: bool = True,
    external_handler: Optional[callable] = None,
) -> AuditLogger:
    """
    Get or create the singleton audit logger instance.
    
    Args:
        log_file: Path to audit log file
        console_logging: Whether to log to console
        file_logging: Whether to log to file
        json_logging: Whether to use JSON format for logs
        external_handler: Optional external logging handler
        
    Returns:
        AuditLogger instance
    """
    global _instance
    if _instance is None:
        _instance = AuditLogger(
            log_file=log_file,
            console_logging=console_logging,
            file_logging=file_logging,
            json_logging=json_logging,
            external_handler=external_handler,
        )
    return _instance