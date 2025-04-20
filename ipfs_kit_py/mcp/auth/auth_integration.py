"""
Authentication & Authorization Integration Module

This module provides comprehensive integration of all authentication and authorization
components with the MCP server. It serves as the main entry point for the auth system.

Features:
- Complete RBAC implementation
- Per-backend authorization
- API key management
- OAuth integration
- Comprehensive audit logging

This module satisfies the requirements outlined in the MCP Server Development Roadmap
under "Advanced Authentication & Authorization" (Phase 1, Q3 2025).
"""

import os
import time
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union, Callable

from fastapi import FastAPI, Request, Response, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# Import auth components
from ipfs_kit_py.mcp.auth.models import User, Role, Permission
from ipfs_kit_py.mcp.auth.service import AuthService
from ipfs_kit_py.mcp.auth.middleware import AuthMiddleware
from ipfs_kit_py.mcp.auth.backend_middleware import BackendAuthorizationMiddleware
from ipfs_kit_py.mcp.auth.rbac import RBACManager
from ipfs_kit_py.mcp.auth.oauth_integration import OAuthManager
from ipfs_kit_py.mcp.auth.apikey_router import APIKeyRouter
from ipfs_kit_py.mcp.auth.audit_logging import AuditLogger, AuditEventType, AuditSeverity

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_auth_integration")

class AuthSystem:
    """Main authentication system integration class."""
    
    def __init__(self):
        """Initialize the authentication system."""
        self.auth_service = None
        self.rbac_manager = None
        self.oauth_manager = None
        self.apikey_router = None
        self.audit_logger = None
        self.auth_middleware = None
        self.backend_middleware = None
        self.initialized = False
    
    async def initialize(
        self, 
        app: FastAPI, 
        backend_manager: Any = None,
        config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Initialize the authentication system.
        
        Args:
            app: FastAPI application
            backend_manager: Backend manager instance
            config: Optional configuration dictionary
            
        Returns:
            Success flag
        """
        try:
            logger.info("Initializing authentication system...")
            
            # Default configuration
            default_config = {
                "rbac_store_path": os.path.join(os.path.expanduser("~"), ".ipfs_kit", "rbac"),
                "token_secret": os.environ.get("JWT_SECRET_KEY", "your-secret-key-change-in-production"),
                "token_algorithm": os.environ.get("JWT_ALGORITHM", "HS256"),
                "token_expire_minutes": int(os.environ.get("JWT_EXPIRE_MINUTES", "1440")),
                "audit_log_path": os.path.join(os.path.expanduser("~"), ".ipfs_kit", "audit.log"),
                "oauth_providers": {
                    "github": {
                        "client_id": os.environ.get("GITHUB_CLIENT_ID", ""),
                        "client_secret": os.environ.get("GITHUB_CLIENT_SECRET", ""),
                        "redirect_uri": os.environ.get("GITHUB_REDIRECT_URI", "")
                    },
                    "google": {
                        "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
                        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
                        "redirect_uri": os.environ.get("GOOGLE_REDIRECT_URI", "")
                    }
                }
            }
            
            # Merge with provided config
            if config:
                for key, value in config.items():
                    if key == "oauth_providers" and key in default_config:
                        # Merge OAuth providers
                        for provider, settings in value.items():
                            default_config[key][provider] = settings
                    else:
                        default_config[key] = value
            
            # Initialize RBAC manager
            self.rbac_manager = RBACManager(default_config["rbac_store_path"])
            logger.info("RBAC manager initialized")
            
            # Initialize auth service
            self.auth_service = AuthService(
                rbac_manager=self.rbac_manager,
                token_secret=default_config["token_secret"],
                token_algorithm=default_config["token_algorithm"],
                token_expire_minutes=default_config["token_expire_minutes"]
            )
            logger.info("Auth service initialized")
            
            # Initialize OAuth manager
            self.oauth_manager = OAuthManager(
                auth_service=self.auth_service,
                providers=default_config["oauth_providers"]
            )
            logger.info("OAuth manager initialized")
            
            # Initialize API key router
            self.apikey_router = APIKeyRouter(
                auth_service=self.auth_service,
                rbac_manager=self.rbac_manager
            )
            logger.info("API key router initialized")
            
            # Initialize audit logger
            self.audit_logger = AuditLogger(
                log_path=default_config["audit_log_path"]
            )
            logger.info("Audit logger initialized")
            
            # Initialize auth middleware
            self.auth_middleware = AuthMiddleware(
                auth_service=self.auth_service,
                audit_logger=self.audit_logger
            )
            logger.info("Auth middleware initialized")
            
            # Initialize backend authorization middleware if backend_manager is provided
            if backend_manager:
                self.backend_middleware = BackendAuthorizationMiddleware(
                    rbac_manager=self.rbac_manager,
                    backend_manager=backend_manager,
                    audit_logger=self.audit_logger
                )
                logger.info("Backend authorization middleware initialized")
            
            # Set up middleware
            app.middleware("http")(self.auth_middleware.authenticate_request)
            if self.backend_middleware:
                app.middleware("http")(self.backend_middleware.authorize_backend_access)
            
            # Set up routers
            from ipfs_kit_py.mcp.auth.router import router as auth_router
            from ipfs_kit_py.mcp.auth.rbac_router import router as rbac_router
            
            app.include_router(auth_router, prefix="/api/v0/auth", tags=["Authentication"])
            app.include_router(rbac_router, prefix="/api/v0/rbac", tags=["RBAC"])
            app.include_router(self.apikey_router.router, prefix="/api/v0/auth", tags=["API Keys"])
            app.include_router(self.oauth_manager.router, prefix="/api/v0/auth/oauth", tags=["OAuth"])
            
            self.initialized = True
            logger.info("Authentication system initialized successfully")
            
            # Log initialization
            self.audit_logger.log(
                event_type=AuditEventType.SYSTEM,
                action="auth_system_initialized",
                severity=AuditSeverity.INFO,
                user_id="system",
                details={
                    "timestamp": time.time(),
                    "components": [
                        "rbac_manager",
                        "auth_service",
                        "oauth_manager",
                        "apikey_router",
                        "audit_logger",
                        "auth_middleware",
                        "backend_middleware" if self.backend_middleware else None
                    ]
                }
            )
            
            return True
        
        except Exception as e:
            logger.error(f"Error initializing authentication system: {e}")
            return False
    
    async def configure_roles(self, roles_config: List[Dict[str, Any]]) -> bool:
        """
        Configure custom roles.
        
        Args:
            roles_config: List of role configurations
            
        Returns:
            Success flag
        """
        if not self.initialized or not self.rbac_manager:
            logger.warning("Cannot configure roles: Auth system not initialized")
            return False
        
        try:
            logger.info(f"Configuring {len(roles_config)} custom roles...")
            
            for role_config in roles_config:
                role_id = role_config.get("id")
                name = role_config.get("name")
                permissions = role_config.get("permissions", [])
                parent_role = role_config.get("parent_role")
                description = role_config.get("description", f"Custom role: {name}")
                
                # Check if role already exists
                existing_role = None
                try:
                    existing_role = self.rbac_manager.get_role_by_name(name)
                except:
                    pass
                
                if existing_role:
                    logger.info(f"Role '{name}' already exists, updating...")
                    # Update existing role
                    self.rbac_manager.update_role(
                        role_id=existing_role.id,
                        name=name,
                        description=description,
                        permissions=permissions,
                        parent_roles=[parent_role] if parent_role else []
                    )
                else:
                    logger.info(f"Creating role '{name}'...")
                    # Create new role
                    self.rbac_manager.create_role(
                        id=role_id,
                        name=name,
                        description=description,
                        permissions=permissions,
                        parent_roles=[parent_role] if parent_role else []
                    )
            
            logger.info("Custom roles configured successfully")
            
            # Log role configuration
            self.audit_logger.log(
                event_type=AuditEventType.ROLE,
                action="custom_roles_configured",
                severity=AuditSeverity.INFO,
                user_id="system",
                details={
                    "timestamp": time.time(),
                    "roles_count": len(roles_config),
                    "role_names": [role.get("name") for role in roles_config]
                }
            )
            
            return True
        
        except Exception as e:
            logger.error(f"Error configuring roles: {e}")
            return False
    
    async def verify_auth_system(self) -> Dict[str, Any]:
        """
        Verify that all authentication system components are working.
        
        Returns:
            Verification result
        """
        if not self.initialized:
            return {
                "success": False,
                "error": "Auth system not initialized"
            }
        
        try:
            verification_result = {
                "success": True,
                "components": {},
                "timestamp": time.time()
            }
            
            # Check RBAC manager
            try:
                roles = self.rbac_manager.list_roles()
                permissions = self.rbac_manager.list_permissions()
                verification_result["components"]["rbac_manager"] = {
                    "status": "ok",
                    "roles_count": len(roles),
                    "permissions_count": len(permissions)
                }
            except Exception as e:
                verification_result["components"]["rbac_manager"] = {
                    "status": "error",
                    "error": str(e)
                }
                verification_result["success"] = False
            
            # Check auth service
            try:
                test_token = await self.auth_service.create_access_token(
                    data={"sub": "test_user", "role": "user"},
                    expires_delta=None
                )
                verification_result["components"]["auth_service"] = {
                    "status": "ok",
                    "token_generation": "successful"
                }
            except Exception as e:
                verification_result["components"]["auth_service"] = {
                    "status": "error",
                    "error": str(e)
                }
                verification_result["success"] = False
            
            # Check OAuth manager
            try:
                providers = self.oauth_manager.get_enabled_providers()
                verification_result["components"]["oauth_manager"] = {
                    "status": "ok",
                    "enabled_providers": providers
                }
            except Exception as e:
                verification_result["components"]["oauth_manager"] = {
                    "status": "error",
                    "error": str(e)
                }
                verification_result["success"] = False
            
            # Check audit logger
            try:
                self.audit_logger.log(
                    event_type=AuditEventType.SYSTEM,
                    action="verify_auth_system",
                    severity=AuditSeverity.INFO,
                    user_id="system",
                    details={"timestamp": time.time()}
                )
                verification_result["components"]["audit_logger"] = {
                    "status": "ok",
                    "logging": "successful"
                }
            except Exception as e:
                verification_result["components"]["audit_logger"] = {
                    "status": "error",
                    "error": str(e)
                }
                verification_result["success"] = False
            
            # Check API key router
            try:
                routes = [route.path for route in self.apikey_router.router.routes]
                verification_result["components"]["apikey_router"] = {
                    "status": "ok",
                    "routes": routes
                }
            except Exception as e:
                verification_result["components"]["apikey_router"] = {
                    "status": "error",
                    "error": str(e)
                }
                verification_result["success"] = False
            
            # Check backend middleware
            if self.backend_middleware:
                try:
                    verification_result["components"]["backend_middleware"] = {
                        "status": "ok",
                        "initialized": True
                    }
                except Exception as e:
                    verification_result["components"]["backend_middleware"] = {
                        "status": "error",
                        "error": str(e)
                    }
                    verification_result["success"] = False
            
            return verification_result
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": time.time()
            }


# Singleton instance
_instance = None

async def initialize_auth_system(
    app: FastAPI, 
    backend_manager: Any = None,
    config: Optional[Dict[str, Any]] = None
) -> AuthSystem:
    """
    Initialize the authentication system.
    
    Args:
        app: FastAPI application
        backend_manager: Backend manager instance
        config: Optional configuration dictionary
        
    Returns:
        Auth system instance
    """
    global _instance
    if _instance is None:
        _instance = AuthSystem()
    
    await _instance.initialize(app, backend_manager, config)
    return _instance

def get_auth_system() -> AuthSystem:
    """
    Get the auth system instance.
    
    Returns:
        Auth system instance
    """
    global _instance
    if _instance is None:
        _instance = AuthSystem()
    
    return _instance

# Audit logging convenience functions
def audit_login_attempt(
    user_id: str,
    success: bool,
    ip_address: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a login attempt.
    
    Args:
        user_id: User ID
        success: Success flag
        ip_address: Optional IP address
        details: Optional additional details
    """
    auth_system = get_auth_system()
    if not auth_system or not auth_system.audit_logger:
        logger.warning("Cannot log login attempt: Auth system not initialized")
        return
    
    event_details = {
        "timestamp": time.time(),
        "success": success,
        "ip_address": ip_address
    }
    
    if details:
        event_details.update(details)
    
    auth_system.audit_logger.log(
        event_type=AuditEventType.AUTH,
        action="login_attempt",
        severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
        user_id=user_id,
        details=event_details
    )

def audit_permission_check(
    user_id: str,
    permission: str,
    granted: bool,
    resource: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a permission check.
    
    Args:
        user_id: User ID
        permission: Permission checked
        granted: Whether permission was granted
        resource: Optional resource ID
        details: Optional additional details
    """
    auth_system = get_auth_system()
    if not auth_system or not auth_system.audit_logger:
        logger.warning("Cannot log permission check: Auth system not initialized")
        return
    
    event_details = {
        "timestamp": time.time(),
        "permission": permission,
        "granted": granted
    }
    
    if resource:
        event_details["resource"] = resource
    
    if details:
        event_details.update(details)
    
    auth_system.audit_logger.log(
        event_type=AuditEventType.PERMISSION,
        action="permission_check",
        severity=AuditSeverity.INFO if granted else AuditSeverity.WARNING,
        user_id=user_id,
        details=event_details
    )

def audit_backend_access(
    user_id: str,
    backend: str,
    operation: str,
    granted: bool,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a backend access attempt.
    
    Args:
        user_id: User ID
        backend: Backend name
        operation: Operation attempted
        granted: Whether access was granted
        details: Optional additional details
    """
    auth_system = get_auth_system()
    if not auth_system or not auth_system.audit_logger:
        logger.warning("Cannot log backend access: Auth system not initialized")
        return
    
    event_details = {
        "timestamp": time.time(),
        "backend": backend,
        "operation": operation,
        "granted": granted
    }
    
    if details:
        event_details.update(details)
    
    auth_system.audit_logger.log(
        event_type=AuditEventType.BACKEND,
        action="backend_access",
        severity=AuditSeverity.INFO if granted else AuditSeverity.WARNING,
        user_id=user_id,
        details=event_details
    )

def audit_user_change(
    admin_id: str,
    target_user_id: str,
    action: str,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a user account change.
    
    Args:
        admin_id: Admin user ID
        target_user_id: Target user ID
        action: Action performed
        details: Optional additional details
    """
    auth_system = get_auth_system()
    if not auth_system or not auth_system.audit_logger:
        logger.warning("Cannot log user change: Auth system not initialized")
        return
    
    event_details = {
        "timestamp": time.time(),
        "admin_id": admin_id,
        "target_user_id": target_user_id,
        "action": action
    }
    
    if details:
        event_details.update(details)
    
    auth_system.audit_logger.log(
        event_type=AuditEventType.USER,
        action=action,
        severity=AuditSeverity.INFO,
        user_id=admin_id,
        details=event_details
    )

def audit_system_event(
    event: str,
    severity: AuditSeverity = AuditSeverity.INFO,
    user_id: str = "system",
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a system event.
    
    Args:
        event: Event description
        severity: Event severity
        user_id: User ID (defaults to "system")
        details: Optional additional details
    """
    auth_system = get_auth_system()
    if not auth_system or not auth_system.audit_logger:
        logger.warning("Cannot log system event: Auth system not initialized")
        return
    
    event_details = {
        "timestamp": time.time(),
        "event": event
    }
    
    if details:
        event_details.update(details)
    
    auth_system.audit_logger.log(
        event_type=AuditEventType.SYSTEM,
        action=event,
        severity=severity,
        user_id=user_id,
        details=event_details
    )

def audit_data_event(
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a data operation event.
    
    Args:
        user_id: User ID
        action: Action performed
        resource_type: Resource type
        resource_id: Resource ID
        details: Optional additional details
    """
    auth_system = get_auth_system()
    if not auth_system or not auth_system.audit_logger:
        logger.warning("Cannot log data event: Auth system not initialized")
        return
    
    event_details = {
        "timestamp": time.time(),
        "resource_type": resource_type,
        "resource_id": resource_id
    }
    
    if details:
        event_details.update(details)
    
    auth_system.audit_logger.log(
        event_type=AuditEventType.DATA,
        action=action,
        severity=AuditSeverity.INFO,
        user_id=user_id,
        details=event_details
    )