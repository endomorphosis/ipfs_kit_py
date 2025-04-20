"""
MCP Authentication & Authorization Integration Module

This module provides a simple API for integrating the Advanced Authentication & Authorization
system with the MCP server. It handles setting up all components of the auth system:

1. User authentication (username/password, tokens)
2. Role-based access control (RBAC)
3. API key management
4. OAuth integration
5. Backend-specific authorization
6. Audit logging

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.
"""

import os
import json
import time
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union, Callable

from fastapi import FastAPI, Request, Response, Depends, HTTPException, status

# Import auth components
try:
    # Core Auth Components
    from ipfs_kit_py.mcp.auth.auth_integration import initialize_auth_system, get_auth_system
    from ipfs_kit_py.mcp.auth.models import User, Role, Permission
    from ipfs_kit_py.mcp.auth.router import get_current_user, get_admin_user
    
    # Enhanced Components
    from ipfs_kit_py.mcp.auth.enhanced_backend_middleware import BackendAuthorizationMiddleware
    from ipfs_kit_py.mcp.auth.api_key_enhanced import EnhancedAPIKeyManager
    from ipfs_kit_py.mcp.auth.oauth_integration_enhanced import OAuthEnhancedManager
    from ipfs_kit_py.mcp.auth.rbac import RBACManager

    AUTH_IMPORTS_SUCCESSFUL = True
except ImportError as e:
    logging.error(f"Error importing auth components: {e}")
    AUTH_IMPORTS_SUCCESSFUL = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_auth_integration")

class MCPAuthIntegrator:
    """
    Helper class for integrating Advanced Authentication & Authorization with MCP server.
    """
    
    def __init__(self):
        """Initialize auth integrator."""
        self.initialized = False
        self.auth_system = None
        self.rbac_manager = None
        self.api_key_manager = None
        self.oauth_manager = None
        self.backend_middleware = None
    
    async def initialize(
        self, 
        app: FastAPI, 
        backend_manager: Any = None,
        config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Initialize and integrate the auth system.
        
        Args:
            app: FastAPI application
            backend_manager: Backend manager instance
            config: Optional configuration dictionary
            
        Returns:
            Success flag
        """
        if not AUTH_IMPORTS_SUCCESSFUL:
            logger.error("Auth component imports failed - cannot initialize")
            return False
        
        try:
            logger.info("Initializing MCP Auth System...")
            
            # Default configuration
            default_config = {
                "data_dir": os.path.join(os.path.expanduser("~"), ".ipfs_kit", "auth"),
                "token_secret": os.environ.get("MCP_JWT_SECRET", "change-this-in-production"),
                "token_algorithm": "HS256",
                "token_expire_minutes": 1440,  # 24 hours
                "admin_username": os.environ.get("MCP_ADMIN_USERNAME", "admin"),
                "admin_password": os.environ.get("MCP_ADMIN_PASSWORD", "change-this-in-production"),
                "oauth_providers": {},
                "default_roles": ["admin", "user", "readonly", "backend_manager"],
                "custom_roles": []
            }
            
            # Merge with provided config
            if config:
                # Deep merge for nested dictionaries like oauth_providers
                for key, value in config.items():
                    if key == "oauth_providers" and key in default_config:
                        default_config[key].update(value)
                    elif key == "custom_roles" and key in default_config:
                        default_config[key].extend(value)
                    else:
                        default_config[key] = value
            
            # Ensure data directories exist
            os.makedirs(default_config["data_dir"], exist_ok=True)
            rbac_dir = os.path.join(default_config["data_dir"], "rbac")
            os.makedirs(rbac_dir, exist_ok=True)
            api_keys_dir = os.path.join(default_config["data_dir"], "api_keys")
            os.makedirs(api_keys_dir, exist_ok=True)
            audit_dir = os.path.join(default_config["data_dir"], "audit")
            os.makedirs(audit_dir, exist_ok=True)
            
            # Initialize core auth system
            self.auth_system = await initialize_auth_system(
                app=app,
                backend_manager=backend_manager,
                config={
                    "rbac_store_path": rbac_dir,
                    "token_secret": default_config["token_secret"],
                    "token_algorithm": default_config["token_algorithm"],
                    "token_expire_minutes": default_config["token_expire_minutes"],
                    "audit_log_path": os.path.join(audit_dir, "audit.log"),
                    "oauth_providers": default_config["oauth_providers"]
                }
            )
            
            # Get core managers
            self.rbac_manager = self.auth_system.rbac_manager
            self.api_key_manager = self.auth_system.apikey_manager
            self.oauth_manager = self.auth_system.oauth_manager
            self.backend_middleware = self.auth_system.backend_middleware
            
            # Configure default admin account
            await self._ensure_admin_account(
                username=default_config["admin_username"],
                password=default_config["admin_password"]
            )
            
            # Configure custom roles
            if default_config["custom_roles"]:
                await self.auth_system.configure_roles(default_config["custom_roles"])
            
            self.initialized = True
            logger.info("MCP Auth System initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing auth system: {e}")
            return False
    
    async def _ensure_admin_account(self, username: str, password: str) -> bool:
        """
        Ensure admin account exists.
        
        Args:
            username: Admin username
            password: Admin password
            
        Returns:
            Success flag
        """
        try:
            # Check if user exists
            existing_user = await self.auth_system.auth_service.get_user_by_username(username)
            
            if not existing_user:
                # Create admin user
                admin_user = User(
                    username=username,
                    email=f"{username}@localhost",
                    role=Role.ADMIN
                )
                # Set password
                admin_user.set_password(password)
                
                # Save user
                await self.auth_system.auth_service.create_user(admin_user)
                logger.info(f"Created admin account: {username}")
            else:
                logger.info(f"Admin account already exists: {username}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error ensuring admin account: {e}")
            return False
    
    async def configure_backend_permissions(
        self, 
        backend_permissions: Dict[str, List[str]]
    ) -> bool:
        """
        Configure backend-specific permissions.
        
        Args:
            backend_permissions: Dictionary mapping backend names to permission lists
            
        Returns:
            Success flag
        """
        if not self.initialized or not self.rbac_manager:
            logger.error("Auth system not initialized")
            return False
        
        try:
            # Create backend-specific permissions for each role
            for backend_name, permissions in backend_permissions.items():
                for permission in permissions:
                    # Check if permission already exists
                    perm_name = f"{permission}:{backend_name}"
                    existing_perm = self.rbac_manager.get_permission_by_name(perm_name)
                    
                    if not existing_perm:
                        # Create permission
                        self.rbac_manager.create_permission(
                            name=perm_name,
                            resource_type="BACKEND",
                            actions=[permission],
                            description=f"{permission.capitalize()} access to {backend_name} backend",
                            resource_id=backend_name
                        )
                        logger.info(f"Created backend permission: {perm_name}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error configuring backend permissions: {e}")
            return False
    
    async def create_role_if_not_exists(
        self,
        role_id: str,
        name: str,
        permissions: List[str],
        parent_role: Optional[str] = None,
        description: Optional[str] = None
    ) -> bool:
        """
        Create a role if it doesn't exist.
        
        Args:
            role_id: Role ID
            name: Role name
            permissions: List of permissions
            parent_role: Optional parent role
            description: Optional description
            
        Returns:
            Success flag
        """
        if not self.initialized or not self.rbac_manager:
            logger.error("Auth system not initialized")
            return False
        
        try:
            # Check if role exists
            existing_role = self.rbac_manager.get_role_by_name(name)
            
            if not existing_role:
                # Create role
                self.rbac_manager.create_role(
                    id=role_id,
                    name=name,
                    permissions=permissions,
                    parent_roles=[parent_role] if parent_role else None,
                    description=description or f"Role: {name}"
                )
                logger.info(f"Created role: {name}")
                return True
            else:
                logger.info(f"Role already exists: {name}")
                return True
        
        except Exception as e:
            logger.error(f"Error creating role: {e}")
            return False


# Singleton instance
_instance = None

async def setup_mcp_auth(
    app: FastAPI, 
    backend_manager: Any = None,
    config: Optional[Dict[str, Any]] = None
) -> MCPAuthIntegrator:
    """
    Set up the MCP authentication system.
    
    Args:
        app: FastAPI application
        backend_manager: Backend manager instance
        config: Optional configuration
        
    Returns:
        Auth integrator instance
    """
    global _instance
    if _instance is None:
        _instance = MCPAuthIntegrator()
    
    success = await _instance.initialize(app, backend_manager, config)
    if not success:
        logger.error("Failed to initialize MCP auth system")
    
    return _instance

def get_mcp_auth() -> MCPAuthIntegrator:
    """
    Get the MCP auth integrator instance.
    
    Returns:
        Auth integrator instance
    """
    global _instance
    if _instance is None:
        _instance = MCPAuthIntegrator()
    
    return _instance

# Export key components for convenience
if AUTH_IMPORTS_SUCCESSFUL:
    # Re-export key functions and classes
    from ipfs_kit_py.mcp.auth.auth_integration import (
        audit_login_attempt, audit_permission_check, audit_backend_access,
        audit_user_change, audit_system_event, audit_data_event
    )
    from ipfs_kit_py.mcp.auth.router import get_current_user, get_admin_user