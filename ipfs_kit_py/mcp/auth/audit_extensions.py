"""
Enhanced Audit Logging for Advanced Authentication Features

This module extends the AuditLogger with methods specifically for the
OAuth and API key features implemented as part of the MCP roadmap.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
from typing import Dict, Any, Optional, List

from ipfs_kit_py.mcp.auth.audit import AuditLogger, AuditLogEntry, AuditEventType, get_instance

logger = logging.getLogger(__name__)


# Extend AuditLogger with additional OAuth-specific methods
async def log_oauth_login(
    self,
    user_id: str,
    provider_id: str,
    provider_user_id: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    is_new_user: bool = False,
    details: Optional[Dict[str, Any]] = None,
):
    """
    Log an OAuth login event.
    
    Args:
        user_id: Internal user ID
        provider_id: OAuth provider ID
        provider_user_id: User ID from the provider
        ip_address: Client IP address
        user_agent: Client user agent
        is_new_user: Whether this is a new user created via OAuth
        details: Additional details
    """
    event_details = {
        "provider_id": provider_id,
        "provider_user_id": provider_user_id,
        "is_new_user": is_new_user,
        **(details or {}),
    }
    
    entry = AuditLogEntry(
        event_type=AuditEventType.OAUTH_LOGIN,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        resource_type="oauth",
        resource_id=provider_id,
        action="login",
        status="success",
        details=event_details,
    )
    
    await self.log(entry)


async def log_oauth_link(
    self,
    user_id: str,
    provider_id: str,
    provider_user_id: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
):
    """
    Log an OAuth account linking event.
    
    Args:
        user_id: Internal user ID
        provider_id: OAuth provider ID
        provider_user_id: User ID from the provider
        ip_address: Client IP address
        user_agent: Client user agent
        details: Additional details
    """
    event_details = {
        "provider_id": provider_id,
        "provider_user_id": provider_user_id,
        **(details or {}),
    }
    
    entry = AuditLogEntry(
        event_type=AuditEventType.OAUTH_LINK,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        resource_type="oauth",
        resource_id=provider_id,
        action="link",
        status="success",
        details=event_details,
    )
    
    await self.log(entry)


async def log_oauth_failure(
    self,
    provider_id: str,
    error: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
):
    """
    Log an OAuth failure event.
    
    Args:
        provider_id: OAuth provider ID
        error: Error message
        ip_address: Client IP address
        user_agent: Client user agent
        details: Additional details
    """
    event_details = {
        "provider_id": provider_id,
        "error": error,
        **(details or {}),
    }
    
    entry = AuditLogEntry(
        event_type=AuditEventType.OAUTH_FAILURE,
        ip_address=ip_address,
        user_agent=user_agent,
        resource_type="oauth",
        resource_id=provider_id,
        action="login",
        status="failure",
        details=event_details,
    )
    
    await self.log(entry)


# Add enhanced API key audit methods
async def log_api_key_creation(
    self,
    user_id: str,
    key_id: str,
    key_name: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
):
    """
    Log an API key creation event.
    
    Args:
        user_id: User ID
        key_id: API key ID
        key_name: API key name
        ip_address: Client IP address
        user_agent: Client user agent
        details: Additional details
    """
    event_details = {
        "key_name": key_name,
        **(details or {}),
    }
    
    entry = AuditLogEntry(
        event_type=AuditEventType.API_KEY_CREATE,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        resource_type="api_key",
        resource_id=key_id,
        action="create",
        status="success",
        details=event_details,
    )
    
    await self.log(entry)


async def log_api_key_update(
    self,
    user_id: str,
    key_id: str,
    update_type: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
):
    """
    Log an API key update event.
    
    Args:
        user_id: User ID
        key_id: API key ID
        update_type: Type of update (permissions, roles, restrictions)
        ip_address: Client IP address
        user_agent: Client user agent
        details: Additional details
    """
    event_details = {
        "update_type": update_type,
        **(details or {}),
    }
    
    entry = AuditLogEntry(
        event_type="api_key_update",  # Not defined in AuditEventType, using string
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        resource_type="api_key",
        resource_id=key_id,
        action="update",
        status="success",
        details=event_details,
    )
    
    await self.log(entry)


# Add general user action logging
async def log_user_action(
    self,
    user_id: str,
    action: str,
    resource_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
):
    """
    Log a general user action.
    
    Args:
        user_id: User ID
        action: Action name
        resource_id: Resource ID
        resource_type: Resource type
        ip_address: Client IP address
        user_agent: Client user agent
        details: Additional details
    """
    entry = AuditLogEntry(
        event_type=f"user_{action}",  # Dynamic event type
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        status="success",
        details=details or {},
    )
    
    await self.log(entry)


async def log_admin_action(
    self,
    user_id: str,
    action: str,
    resource_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
):
    """
    Log an admin action.
    
    Args:
        user_id: Admin user ID
        action: Action name
        resource_id: Resource ID
        resource_type: Resource type
        ip_address: Client IP address
        user_agent: Client user agent
        details: Additional details
    """
    entry = AuditLogEntry(
        event_type=f"admin_{action}",  # Dynamic event type
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        status="success",
        details=details or {},
    )
    
    await self.log(entry)


def extend_audit_logger():
    """
    Extend the AuditLogger class with additional methods.
    
    This function adds the enhanced audit methods to the AuditLogger class.
    """
    # Add OAuth methods
    AuditLogger.log_oauth_login = log_oauth_login
    AuditLogger.log_oauth_link = log_oauth_link
    AuditLogger.log_oauth_failure = log_oauth_failure
    
    # Add API key methods
    AuditLogger.log_api_key_creation = log_api_key_creation
    AuditLogger.log_api_key_update = log_api_key_update
    
    # Add general action methods
    AuditLogger.log_user_action = log_user_action
    AuditLogger.log_admin_action = log_admin_action
    
    logger.info("Extended AuditLogger with additional methods")


# Helper function to get the audit logger
def get_audit_logger() -> AuditLogger:
    """
    Get the configured audit logger.
    
    Returns:
        AuditLogger instance
    """
    # Make sure extensions are applied
    extend_audit_logger()
    
    # Get the singleton instance
    return get_instance()