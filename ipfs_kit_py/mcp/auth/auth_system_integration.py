"""
Advanced Authentication & Authorization System Integration

This module provides a comprehensive integration of all authentication and
authorization components for the MCP server, fulfilling the requirements in the
MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).

Features:
- Role-based access control
- Per-backend authorization
- API key management
- OAuth integration
- Comprehensive audit logging
"""

import os
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from fastapi import FastAPI, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Core auth components
from ipfs_kit_py.mcp.auth.service import AuthenticationService, get_auth_service
from ipfs_kit_py.mcp.auth.router import router as auth_router
from ipfs_kit_py.mcp.auth.models import User, Role, Permission

# RBAC components
from ipfs_kit_py.mcp.rbac import rbac_manager, get_current_user_role, check_permission, check_backend_permission
from ipfs_kit_py.mcp.auth.rbac_router import router as rbac_router

# API Key components
from ipfs_kit_py.mcp.auth.api_key_middleware import APIKeyMiddleware
from ipfs_kit_py.mcp.auth.api_key_cache import APIKeyCache
from ipfs_kit_py.mcp.auth.api_key_cache_integration import setup_api_key_cache
from ipfs_kit_py.mcp.auth.apikey_router import router as apikey_router

# OAuth components
from ipfs_kit_py.mcp.auth.oauth_integration import setup_oauth
from ipfs_kit_py.mcp.auth.oauth_integration_service import patch_authentication_service
from ipfs_kit_py.mcp.auth.oauth_router import router as oauth_router

# Backend authorization
from ipfs_kit_py.mcp.auth.backend_middleware import BackendAuthorizationMiddleware
from ipfs_kit_py.mcp.auth.backend_authorization import setup_backend_authorization

# Audit components
from ipfs_kit_py.mcp.auth.audit import AuditLogger, get_instance as get_audit_logger
from ipfs_kit_py.mcp.auth.audit_extensions import extend_audit_logger
from ipfs_kit_py.mcp.auth.security_dashboard import router as security_dashboard_router

# Configure logging
logger = logging.getLogger(__name__)

class AuthSystem:
    """
    Comprehensive authentication and authorization system for MCP.
    
    This class manages all aspects of the auth system and provides
    a central point for configuration and operations.
    """
    
    def __init__(self, 
                app: FastAPI, 
                storage_backend_manager=None,
                config_path: Optional[str] = None):
        """
        Initialize the auth system.
        
        Args:
            app: FastAPI application
            storage_backend_manager: Storage backend manager instance
            config_path: Optional path to auth config directory
        """
        self.app = app
        self.backend_manager = storage_backend_manager
        self.config_path = config_path or os.environ.get(
            "MCP_AUTH_CONFIG_PATH", 
            str(Path.home() / ".ipfs_kit" / "auth")
        )
        
        # Create config directory if it doesn't exist
        os.makedirs(self.config_path, exist_ok=True)
        
        # Core components
        self.auth_service = None
        self.api_key_cache = None
        self.audit_logger = None
        
        # Initialization state
        self.initialized = False
    
    async def initialize(self):
        """Initialize all auth system components."""
        if self.initialized:
            return
        
        logger.info("Initializing advanced authentication & authorization system")
        
        # Initialize audit logger
        self.audit_logger = get_audit_logger()
        extend_audit_logger()
        await self.audit_logger.start()
        logger.info("Audit logging initialized")
        
        # Get auth service instance 
        self.auth_service = get_auth_service()
        
        # Patch authentication service with OAuth integration
        patch_authentication_service()
        logger.info("Authentication service patched with OAuth integration")
        
        # Initialize API key cache
        self.api_key_cache = await setup_api_key_cache()
        logger.info("API key cache initialized")
        
        # Set up middlewares
        self._setup_middlewares()
        
        # Set up routes
        self._setup_routes()
        
        # Set up backend authorization if backend manager is available
        if self.backend_manager:
            await setup_backend_authorization(self.backend_manager)
            logger.info("Backend authorization initialized")
        
        # Set up OAuth
        setup_oauth(self.app)
        logger.info("OAuth integration initialized")
        
        self.initialized = True
        logger.info("Advanced Authentication & Authorization system initialized")
    
    def _setup_middlewares(self):
        """Set up all auth-related middlewares."""
        # API Key middleware (handled first for API client access)
        self.app.add_middleware(
            APIKeyMiddleware,
            api_key_cache=self.api_key_cache,
            exclude_paths=["/api/v0/auth/login", "/health", "/api/v0/status"]
        )
        
        # Backend authorization middleware (for storage operations)
        if self.backend_manager:
            self.app.add_middleware(
                BackendAuthorizationMiddleware,
                backend_manager=self.backend_manager,
                exclude_paths=["/api/v0/auth/", "/health", "/api/v0/status"]
            )
        
        logger.info("Auth middlewares configured")
    
    def _setup_routes(self):
        """Set up all auth-related API routes."""
        # Core authentication routes
        self.app.include_router(auth_router)
        
        # RBAC management routes
        self.app.include_router(rbac_router)
        
        # API key management routes
        self.app.include_router(apikey_router)
        
        # OAuth routes
        self.app.include_router(oauth_router)
        
        # Security dashboard routes
        self.app.include_router(security_dashboard_router)
        
        logger.info("Auth routes configured")
    
    async def configure_roles(self, custom_roles: Optional[List[Dict[str, Any]]] = None):
        """
        Configure RBAC roles with custom roles if provided.
        
        Args:
            custom_roles: Optional list of custom role configurations
        """
        # Make sure the system is initialized
        if not self.initialized:
            await self.initialize()
        
        # Add custom roles if provided
        if custom_roles:
            for role_config in custom_roles:
                role_id = role_config.get("id")
                name = role_config.get("name")
                permissions = role_config.get("permissions", [])
                parent_role = role_config.get("parent_role")
                
                logger.info(f"Creating custom role: {name} ({role_id})")
                rbac_manager.create_custom_role(
                    role_id=role_id,
                    name=name,
                    permissions=permissions,
                    parent_role=parent_role
                )
        
        logger.info("RBAC roles configured")
    
    def get_user_dependency(self, require_auth: bool = True, admin_only: bool = False):
        """
        Get a dependency for FastAPI that provides the current user.
        
        Args:
            require_auth: Whether authentication is required (returns 401 if not authenticated)
            admin_only: Whether admin access is required (returns 403 if not admin)
            
        Returns:
            Dependency function for FastAPI
        """
        # Return appropriate dependency
        if admin_only:
            from ipfs_kit_py.mcp.auth.router import get_admin_user
            return get_admin_user
        elif require_auth:
            from ipfs_kit_py.mcp.auth.router import get_current_user
            return get_current_user
        else:
            from ipfs_kit_py.mcp.auth.router import get_optional_user
            return get_optional_user
    
    async def close(self):
        """Close and clean up auth system components."""
        if self.audit_logger:
            await self.audit_logger.stop()
            logger.info("Audit logger stopped")
        
        logger.info("Authentication system shutdown complete")


# Singleton instance
_auth_system = None


def get_auth_system() -> AuthSystem:
    """
    Get the singleton auth system instance.
    
    Returns:
        AuthSystem instance
    """
    global _auth_system
    return _auth_system


async def initialize_auth_system(app: FastAPI, backend_manager=None, config_path: Optional[str] = None) -> AuthSystem:
    """
    Initialize the authentication and authorization system.
    
    This function creates and initializes the auth system and all its components.
    It should be called during server startup.
    
    Args:
        app: FastAPI application
        backend_manager: Optional storage backend manager
        config_path: Optional auth config path
        
    Returns:
        Initialized AuthSystem instance
    """
    global _auth_system
    
    if _auth_system is None:
        _auth_system = AuthSystem(
            app=app,
            storage_backend_manager=backend_manager,
            config_path=config_path
        )
    
    # Initialize the system
    await _auth_system.initialize()
    
    return _auth_system