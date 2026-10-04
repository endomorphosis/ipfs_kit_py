#!/usr/bin/env python3
# ipfs_kit_py/mcp/auth/__init__.py

"""
Authentication and Authorization module for IPFS Kit MCP Server.

This module provides a comprehensive authentication and authorization system
for the MCP server, including:
- Role-based access control (RBAC)
- Per-backend authorization
- API key management
- OAuth integration
- Audit logging
"""

import logging
import os
from typing import Optional

# Import core RBAC components
from .rbac_enhanced import (
    RBACService, Permission, Role, ResourceType, Action,
    ApiKey, ApiKeyManager, BackendAuthorization, RequestAuthenticator,
    require_permission, AuthorizationResult
)

# Import OAuth integration
from .oauth_integration import (
    OAuthManager, OAuthProvider, OAuthConfig, OAuthToken,
    OAuthUserInfo, OAuthUserManager
)

# Import API endpoints
from .api_endpoints import AuthHandler

# Import audit logging
from .audit_logging import AuditLogger, AuditEvent, AuditEventType

# Create a global logger
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    "audit_log_path": "logs/auth_audit.log",
    "api_keys_path": "data/api_keys.json",
    "oauth_state_path": "data/oauth_states.json",
    "enable_oauth": False,
    "oauth_providers": {},
}

# Global instances
rbac_service: Optional[RBACService] = None
oauth_manager: Optional[OAuthManager] = None
audit_logger: Optional[AuditLogger] = None
auth_handler: Optional[AuthHandler] = None


def initialize(config=None):
    """
    Initialize the authentication and authorization system.
    
    Args:
        config: Configuration dictionary
    """
    global rbac_service, oauth_manager, audit_logger, auth_handler
    
    # Merge with default config
    if config is None:
        config = {}
    
    merged_config = DEFAULT_CONFIG.copy()
    merged_config.update(config)
    
    # Ensure directories exist
    for path_key in ["audit_log_path", "api_keys_path", "oauth_state_path"]:
        path = merged_config[path_key]
        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)
    
    # Initialize audit logger
    audit_logger = AuditLogger(merged_config["audit_log_path"])
    
    # Initialize RBAC service
    rbac_service = RBACService(merged_config["api_keys_path"])
    
    # Initialize OAuth manager if enabled
    if merged_config["enable_oauth"]:
        oauth_manager = OAuthManager(merged_config["oauth_state_path"])
        
        # Register OAuth providers
        for provider_name, provider_config in merged_config["oauth_providers"].items():
            oauth_config = OAuthConfig(**provider_config)
            oauth_manager.register_provider(oauth_config)
    
    # Initialize auth handler
    auth_handler = AuthHandler(rbac_service, oauth_manager)
    
    logger.info("Authentication and authorization system initialized")
    audit_logger.log(
        AuditEventType.SYSTEM, 
        "auth_system_initialized",
        details={"config": {k: v for k, v in merged_config.items() if "secret" not in k}}
    )
    
    return {
        "rbac_service": rbac_service,
        "oauth_manager": oauth_manager,
        "audit_logger": audit_logger,
        "auth_handler": auth_handler
    }


def get_rbac_service():
    """Get the global RBAC service instance."""
    if rbac_service is None:
        raise RuntimeError("Authentication system not initialized. Call initialize() first.")
    return rbac_service


def get_oauth_manager():
    """Get the global OAuth manager instance."""
    if oauth_manager is None:
        raise RuntimeError("OAuth manager not initialized or disabled. Check configuration.")
    return oauth_manager


def get_audit_logger():
    """Get the global audit logger instance."""
    if audit_logger is None:
        raise RuntimeError("Audit logger not initialized. Call initialize() first.")
    return audit_logger


def get_auth_handler():
    """Get the global auth handler instance."""
    if auth_handler is None:
        raise RuntimeError("Auth handler not initialized. Call initialize() first.")
    return auth_handler


# Convenience exports
__all__ = [
    # Core RBAC components
    "RBACService", "Permission", "Role", "ResourceType", "Action",
    "ApiKey", "ApiKeyManager", "BackendAuthorization", "RequestAuthenticator",
    "require_permission", "AuthorizationResult",
    
    # OAuth integration
    "OAuthManager", "OAuthProvider", "OAuthConfig", "OAuthToken",
    "OAuthUserInfo", "OAuthUserManager",
    
    # API endpoints
    "AuthHandler",
    
    # Audit logging
    "AuditLogger", "AuditEvent", "AuditEventType",
    
    # Module functions
    "initialize", "get_rbac_service", "get_oauth_manager", 
    "get_audit_logger", "get_auth_handler"
]