#!/usr/bin/env python3
# ipfs_kit_py/mcp/auth/audit_logging.py

"""
Audit Logging for IPFS Kit MCP Server.

This module provides comprehensive audit logging capabilities for tracking
authentication, authorization, and other security-related events in the system.
Features include:
- Structured logging of security events
- Event categorization
- User action tracking
- Compliance-oriented logging format
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class AuditSeverity(Enum):
    """Severity levels for audit events."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditEventType(Enum):
    """Types of audit events."""
    AUTHENTICATION = "authentication"  # Login/logout events
    AUTHORIZATION = "authorization"    # Permission checks
    USER = "user"                      # User management actions
    ROLE = "role"                      # Role management actions
    API_KEY = "api_key"                # API key management
    OAUTH = "oauth"                    # OAuth events
    DATA = "data"                      # Data access/modification
    SYSTEM = "system"                  # System configuration changes
    BACKEND = "backend"                # Storage backend operations
    ADMIN = "admin"                    # Administrative actions


@dataclass
class AuditEvent:
    """Represents an audit event in the system."""
    event_type: AuditEventType
    action: str
    timestamp: float = field(default_factory=time.time)
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    resource_id: Optional[str] = None
    resource_type: Optional[str] = None
    status: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    request_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the event to a dictionary for serialization."""
        return {
            "event_type": self.event_type.value if isinstance(self.event_type, AuditEventType) else self.event_type,
            "action": self.action,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "status": self.status,
            "details": self.details,
            "request_id": self.request_id
        }
    
    def to_json(self) -> str:
        """Convert the event to a JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditEvent':
        """Create an event from a dictionary."""
        event_type = data.get("event_type")
        if isinstance(event_type, str):
            try:
                event_type = AuditEventType(event_type)
            except ValueError:
                # Use the string value if it's not a valid enum value
                pass
        
        return cls(
            event_type=event_type,
            action=data.get("action"),
            timestamp=data.get("timestamp", time.time()),
            user_id=data.get("user_id"),
            ip_address=data.get("ip_address"),
            resource_id=data.get("resource_id"),
            resource_type=data.get("resource_type"),
            status=data.get("status"),
            details=data.get("details", {}),
            request_id=data.get("request_id")
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AuditEvent':
        """Create an event from a JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


class AuditLogger:
    """
    Handles audit logging for the system.
    
    This class provides methods for logging various types of audit events
    and ensures they are properly formatted and stored.
    """
    
    def __init__(self, log_file: Optional[str] = None, log_level: int = logging.INFO):
        """
        Initialize the audit logger.
        
        Args:
            log_file: Path to the audit log file. If None, logs will only go to the console.
            log_level: Logging level (default: INFO)
        """
        # Create a dedicated logger for audit events
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(log_level)
        
        # Create formatter for audit logs
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Add file handler if log_file is provided
        if log_file:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        
        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Keep an in-memory cache of recent events for quick access
        self.recent_events: List[AuditEvent] = []
        self.max_cached_events = 1000  # Limit to avoid memory issues
    
    def log(self, event_type: Union[AuditEventType, str], action: str, 
            user_id: Optional[str] = None, ip_address: Optional[str] = None,
            resource_id: Optional[str] = None, resource_type: Optional[str] = None,
            status: Optional[str] = None, details: Optional[Dict[str, Any]] = None,
            request_id: Optional[str] = None) -> AuditEvent:
        """
        Log an audit event.
        
        Args:
            event_type: Type of the event
            action: Action being performed
            user_id: ID of the user performing the action
            ip_address: IP address of the user
            resource_id: ID of the resource being accessed
            resource_type: Type of the resource being accessed
            status: Status of the action (success, failure, etc.)
            details: Additional details about the event
            request_id: ID of the request for correlation
            
        Returns:
            AuditEvent: The created audit event
        """
        # Convert string event type to enum if needed
        if isinstance(event_type, str):
            try:
                event_type = AuditEventType(event_type)
            except ValueError:
                # Use the string value if it's not a valid enum value
                pass
        
        # Create the audit event
        event = AuditEvent(
            event_type=event_type,
            action=action,
            timestamp=time.time(),
            user_id=user_id,
            ip_address=ip_address,
            resource_id=resource_id,
            resource_type=resource_type,
            status=status,
            details=details or {},
            request_id=request_id
        )
        
        # Log the event
        self.logger.info(event.to_json())
        
        # Add to recent events cache
        self.recent_events.append(event)
        if len(self.recent_events) > self.max_cached_events:
            self.recent_events.pop(0)  # Remove oldest event
        
        return event
    
    def log_auth_success(self, user_id: str, ip_address: Optional[str] = None,
                       method: str = "password", details: Optional[Dict[str, Any]] = None,
                       request_id: Optional[str] = None) -> AuditEvent:
        """
        Log a successful authentication.
        
        Args:
            user_id: ID of the authenticated user
            ip_address: IP address of the user
            method: Authentication method used
            details: Additional details
            request_id: ID of the request
            
        Returns:
            AuditEvent: The created audit event
        """
        return self.log(
            event_type=AuditEventType.AUTHENTICATION,
            action="login",
            user_id=user_id,
            ip_address=ip_address,
            status="success",
            details={"method": method, **(details or {})},
            request_id=request_id
        )
    
    def log_auth_failure(self, user_id: Optional[str], ip_address: Optional[str] = None,
                       method: str = "password", reason: str = "invalid_credentials",
                       details: Optional[Dict[str, Any]] = None,
                       request_id: Optional[str] = None) -> AuditEvent:
        """
        Log a failed authentication attempt.
        
        Args:
            user_id: ID of the user (if known)
            ip_address: IP address of the user
            method: Authentication method used
            reason: Reason for failure
            details: Additional details
            request_id: ID of the request
            
        Returns:
            AuditEvent: The created audit event
        """
        return self.log(
            event_type=AuditEventType.AUTHENTICATION,
            action="login",
            user_id=user_id,
            ip_address=ip_address,
            status="failure",
            details={"method": method, "reason": reason, **(details or {})},
            request_id=request_id
        )
    
    def log_logout(self, user_id: str, ip_address: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None,
                 request_id: Optional[str] = None) -> AuditEvent:
        """
        Log a user logout.
        
        Args:
            user_id: ID of the user
            ip_address: IP address of the user
            details: Additional details
            request_id: ID of the request
            
        Returns:
            AuditEvent: The created audit event
        """
        return self.log(
            event_type=AuditEventType.AUTHENTICATION,
            action="logout",
            user_id=user_id,
            ip_address=ip_address,
            status="success",
            details=details or {},
            request_id=request_id
        )
    
    def log_permission_check(self, user_id: str, permission: str, 
                           resource_id: Optional[str] = None, 
                           resource_type: Optional[str] = None,
                           granted: bool = True, ip_address: Optional[str] = None,
                           details: Optional[Dict[str, Any]] = None,
                           request_id: Optional[str] = None) -> AuditEvent:
        """
        Log a permission check.
        
        Args:
            user_id: ID of the user
            permission: Permission being checked
            resource_id: ID of the resource
            resource_type: Type of the resource
            granted: Whether the permission was granted
            ip_address: IP address of the user
            details: Additional details
            request_id: ID of the request
            
        Returns:
            AuditEvent: The created audit event
        """
        return self.log(
            event_type=AuditEventType.AUTHORIZATION,
            action="check_permission",
            user_id=user_id,
            ip_address=ip_address,
            resource_id=resource_id,
            resource_type=resource_type,
            status="granted" if granted else "denied",
            details={"permission": permission, **(details or {})},
            request_id=request_id
        )
    
    def log_user_creation(self, admin_user_id: str, created_user_id: str,
                        ip_address: Optional[str] = None,
                        details: Optional[Dict[str, Any]] = None,
                        request_id: Optional[str] = None) -> AuditEvent:
        """
        Log user creation.
        
        Args:
            admin_user_id: ID of the admin creating the user
            created_user_id: ID of the created user
            ip_address: IP address of the admin
            details: Additional details
            request_id: ID of the request
            
        Returns:
            AuditEvent: The created audit event
        """
        return self.log(
            event_type=AuditEventType.USER,
            action="create",
            user_id=admin_user_id,
            ip_address=ip_address,
            resource_id=created_user_id,
            resource_type="user",
            status="success",
            details=details or {},
            request_id=request_id
        )
    
    def log_user_modification(self, admin_user_id: str, modified_user_id: str,
                            ip_address: Optional[str] = None,
                            details: Optional[Dict[str, Any]] = None,
                            request_id: Optional[str] = None) -> AuditEvent:
        """
        Log user modification.
        
        Args:
            admin_user_id: ID of the admin modifying the user
            modified_user_id: ID of the modified user
            ip_address: IP address of the admin
            details: Additional details
            request_id: ID of the request
            
        Returns:
            AuditEvent: The created audit event
        """
        return self.log(
            event_type=AuditEventType.USER,
            action="modify",
            user_id=admin_user_id,
            ip_address=ip_address,
            resource_id=modified_user_id,
            resource_type="user",
            status="success",
            details=details or {},
            request_id=request_id
        )
    
    def log_user_deletion(self, admin_user_id: str, deleted_user_id: str,
                        ip_address: Optional[str] = None,
                        details: Optional[Dict[str, Any]] = None,
                        request_id: Optional[str] = None) -> AuditEvent:
        """
        Log user deletion.
        
        Args:
            admin_user_id: ID of the admin deleting the user
            deleted_user_id: ID of the deleted user
            ip_address: IP address of the admin
            details: Additional details
            request_id: ID of the request
            
        Returns:
            AuditEvent: The created audit event
        """
        return self.log(
            event_type=AuditEventType.USER,
            action="delete",
            user_id=admin_user_id,
            ip_address=ip_address,
            resource_id=deleted_user_id,
            resource_type="user",
            status="success",
            details=details or {},
            request_id=request_id
        )
    
    def log_role_creation(self, admin_user_id: str, role_name: str,
                        ip_address: Optional[str] = None,
                        details: Optional[Dict[str, Any]] = None,
                        request_id: Optional[str] = None) -> AuditEvent:
        """
        Log role creation.
        
        Args:
            admin_user_id: ID of the admin creating the role
            role_name: Name of the created role
            ip_address: IP address of the admin
            details: Additional details
            request_id: ID of the request
            
        Returns:
            AuditEvent: The created audit event
        """
        return self.log(
            event_type=AuditEventType.ROLE,
            action="create",
            user_id=admin_user_id,
            ip_address=ip_address,
            resource_id=role_name,
            resource_type="role",
            status="success",
            details=details or {},
            request_id=request_id
        )
    
    def log_role_modification(self, admin_user_id: str, role_name: str,
                            ip_address: Optional[str] = None,
                            details: Optional[Dict[str, Any]] = None,
                            request_id: Optional[str] = None) -> AuditEvent:
        """
        Log role modification.
        
        Args:
            admin_user_id: ID of the admin modifying the role
            role_name: Name of the modified role
            ip_address: IP address of the admin
            details: Additional details
            request_id: ID of the request
            
        Returns:
            AuditEvent: The created audit event
        """
        return self.log(
            event_type=AuditEventType.ROLE,
            action="modify",
            user_id=admin_user_id,
            ip_address=ip_address,
            resource_id=role_name,
            resource_type="role",
            status="success",
            details=details or {},
            request_id=request_id
        )
    
    def log_role_deletion(self, admin_user_id: str, role_name: str,
                        ip_address: Optional[str] = None,
                        details: Optional[Dict[str, Any]] = None,
                        request_id: Optional[str] = None) -> AuditEvent:
        """
        Log role deletion.
        
        Args:
            admin_user_id: ID of the admin deleting the role
            role_name: Name of the deleted role
            ip_address: IP address of the admin
            details: Additional details
            request_id: ID of the request
            
        Returns:
            AuditEvent: The created audit event
        """
        return self.log(
            event_type=AuditEventType.ROLE,
            action="delete",
            user_id=admin_user_id,
            ip_address=ip_address,
            resource_id=role_name,
            resource_type="role",
            status="success",
            details=details or {},
            request_id=request_id
        )
    
    def log_api_key_creation(self, admin_user_id: str, key_id: str,
                           user_id: str, ip_address: Optional[str] = None,
                           details: Optional[Dict[str, Any]] = None,
                           request_id: Optional[str] = None) -> AuditEvent:
        """
        Log API key creation.
        
        Args:
            admin_user_id: ID of the admin creating the key
            key_id: ID of the created key
            user_id: ID of the user the key belongs to
            ip_address: IP address of the admin
            details: Additional details
            request_id: ID of the request
            
        Returns:
            AuditEvent: The created audit event
        """
        return self.log(
            event_type=AuditEventType.API_KEY,
            action="create",
            user_id=admin_user_id,
            ip_address=ip_address,
            resource_id=key_id,
            resource_type="api_key",
            status="success",
            details={"for_user_id": user_id, **(details or {})},
            request_id=request_id
        )
    
    def log_api_key_revocation(self, admin_user_id: str, key_id: str,
                             ip_address: Optional[str] = None,
                             details: Optional[Dict[str, Any]] = None,
                             request_id: Optional[str] = None) -> AuditEvent:
        """
        Log API key revocation.
        
        Args:
            admin_user_id: ID of the admin revoking the key
            key_id: ID of the revoked key
            ip_address: IP address of the admin
            details: Additional details
            request_id: ID of the request
            
        Returns:
            AuditEvent: The created audit event
        """
        return self.log(
            event_type=AuditEventType.API_KEY,
            action="revoke",
            user_id=admin_user_id,
            ip_address=ip_address,
            resource_id=key_id,
            resource_type="api_key",
            status="success",
            details=details or {},
            request_id=request_id
        )
    
    def log_oauth_login(self, user_id: Optional[str], provider: str,
                      ip_address: Optional[str] = None, status: str = "success",
                      details: Optional[Dict[str, Any]] = None,
                      request_id: Optional[str] = None) -> AuditEvent:
        """
        Log OAuth login.
        
        Args:
            user_id: ID of the user (if known)
            provider: OAuth provider (e.g., "google", "github")
            ip_address: IP address of the user
            status: Status of the login
            details: Additional details
            request_id: ID of the request
            
        Returns:
            AuditEvent: The created audit event
        """
        return self.log(
            event_type=AuditEventType.OAUTH,
            action="login",
            user_id=user_id,
            ip_address=ip_address,
            status=status,
            details={"provider": provider, **(details or {})},
            request_id=request_id
        )
    
    def log_data_access(self, user_id: str, resource_id: str,
                      resource_type: str, action: str,
                      ip_address: Optional[str] = None,
                      details: Optional[Dict[str, Any]] = None,
                      request_id: Optional[str] = None) -> AuditEvent:
        """
        Log data access.
        
        Args:
            user_id: ID of the user accessing the data
            resource_id: ID of the accessed resource
            resource_type: Type of the accessed resource
            action: Action performed (read, write, delete)
            ip_address: IP address of the user
            details: Additional details
            request_id: ID of the request
            
        Returns:
            AuditEvent: The created audit event
        """
        return self.log(
            event_type=AuditEventType.DATA,
            action=action,
            user_id=user_id,
            ip_address=ip_address,
            resource_id=resource_id,
            resource_type=resource_type,
            status="success",
            details=details or {},
            request_id=request_id
        )
    
    def log_system_config_change(self, user_id: str, config_key: str,
                               ip_address: Optional[str] = None,
                               details: Optional[Dict[str, Any]] = None,
                               request_id: Optional[str] = None) -> AuditEvent:
        """
        Log system configuration change.
        
        Args:
            user_id: ID of the user making the change
            config_key: Configuration key being changed
            ip_address: IP address of the user
            details: Additional details
            request_id: ID of the request
            
        Returns:
            AuditEvent: The created audit event
        """
        return self.log(
            event_type=AuditEventType.SYSTEM,
            action="config_change",
            user_id=user_id,
            ip_address=ip_address,
            resource_id=config_key,
            resource_type="config",
            status="success",
            details=details or {},
            request_id=request_id
        )
    
    def log_backend_operation(self, user_id: str, backend: str,
                            operation: str, resource_id: Optional[str] = None,
                            ip_address: Optional[str] = None, status: str = "success",
                            details: Optional[Dict[str, Any]] = None,
                            request_id: Optional[str] = None) -> AuditEvent:
        """
        Log storage backend operation.
        
        Args:
            user_id: ID of the user performing the operation
            backend: Storage backend (e.g., "IPFS", "S3")
            operation: Operation performed
            resource_id: ID of the affected resource
            ip_address: IP address of the user
            status: Status of the operation
            details: Additional details
            request_id: ID of the request
            
        Returns:
            AuditEvent: The created audit event
        """
        return self.log(
            event_type=AuditEventType.BACKEND,
            action=operation,
            user_id=user_id,
            ip_address=ip_address,
            resource_id=resource_id,
            resource_type=backend,
            status=status,
            details=details or {},
            request_id=request_id
        )
    
    def log_admin_action(self, user_id: str, action: str,
                       resource_id: Optional[str] = None,
                       resource_type: Optional[str] = None,
                       ip_address: Optional[str] = None,
                       details: Optional[Dict[str, Any]] = None,
                       request_id: Optional[str] = None) -> AuditEvent:
        """
        Log administrative action.
        
        Args:
            user_id: ID of the admin performing the action
            action: Action performed
            resource_id: ID of the affected resource
            resource_type: Type of the affected resource
            ip_address: IP address of the admin
            details: Additional details
            request_id: ID of the request
            
        Returns:
            AuditEvent: The created audit event
        """
        return self.log(
            event_type=AuditEventType.ADMIN,
            action=action,
            user_id=user_id,
            ip_address=ip_address,
            resource_id=resource_id,
            resource_type=resource_type,
            status="success",
            details=details or {},
            request_id=request_id
        )
    
    def get_recent_events(self, limit: Optional[int] = None,
                        event_type: Optional[Union[AuditEventType, str]] = None,
                        user_id: Optional[str] = None) -> List[AuditEvent]:
        """
        Get recent audit events from the in-memory cache.
        
        Args:
            limit: Maximum number of events to return
            event_type: Filter by event type
            user_id: Filter by user ID
            
        Returns:
            List[AuditEvent]: List of recent audit events
        """
        # Convert string event type to enum if needed
        if isinstance(event_type, str):
            try:
                event_type = AuditEventType(event_type)
            except ValueError:
                # Use the string value if it's not a valid enum value
                pass
        
        # Filter events
        filtered_events = self.recent_events
        if event_type is not None:
            filtered_events = [e for e in filtered_events 
                             if e.event_type == event_type or 
                             (isinstance(e.event_type, str) and e.event_type == event_type.value)]
        
        if user_id is not None:
            filtered_events = [e for e in filtered_events if e.user_id == user_id]
        
        # Apply limit
        if limit is not None:
            filtered_events = filtered_events[-limit:]
        
        return filtered_events
    
    def clear_cache(self):
        """Clear the in-memory event cache."""
        self.recent_events = []