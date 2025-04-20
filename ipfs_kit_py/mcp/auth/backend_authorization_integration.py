"""
Backend Authorization Integration

This module provides a comprehensive backend authorization system that integrates with RBAC,
allowing fine-grained control over which users and API keys can access different storage backends.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
import asyncio
from typing import Dict, List, Set, Optional, Any, Union
from dataclasses import dataclass, field

from ipfs_kit_py.mcp.auth.rbac import PermissionEffect, RBACManager
from ipfs_kit_py.mcp.auth.models import User
from ipfs_kit_py.mcp.auth.api_key_enhanced import ApiKey

logger = logging.getLogger(__name__)


@dataclass
class BackendPermission:
    """Permission configuration for a specific backend."""
    backend_id: str
    allowed_users: Set[str] = field(default_factory=set)
    allowed_roles: Set[str] = field(default_factory=set)
    denied_users: Set[str] = field(default_factory=set)
    denied_roles: Set[str] = field(default_factory=set)
    # Operation-specific permissions
    read_only_users: Set[str] = field(default_factory=set)
    read_only_roles: Set[str] = field(default_factory=set)
    admin_users: Set[str] = field(default_factory=set)
    admin_roles: Set[str] = field(default_factory=set)
    # Default policy
    default_allow: bool = False


class BackendAuthorizationManager:
    """
    Backend Authorization Manager for MCP server.
    
    This class manages permissions for different storage backends, integrating with the RBAC system
    to provide fine-grained control over who can access which backend and what operations they can perform.
    """
    
    def __init__(
        self,
        rbac_manager: RBACManager,
        storage_backend_manager = None,  # Type hint omitted for circular import avoidance
        default_allow: bool = False
    ):
        """
        Initialize the Backend Authorization Manager.
        
        Args:
            rbac_manager: Role-Based Access Control manager
            storage_backend_manager: Storage Backend Manager instance
            default_allow: Whether to allow access by default if no specific permission is found
        """
        self.rbac_manager = rbac_manager
        self.storage_backend_manager = storage_backend_manager
        self.default_allow = default_allow
        
        # Backend permissions dictionary (backend_id -> BackendPermission)
        self._backend_permissions: Dict[str, BackendPermission] = {}
        
        # Initialization state
        self._initialized = False
        
        logger.info("Backend Authorization Manager initialized")
    
    async def initialize(self):
        """
        Initialize the Backend Authorization Manager.
        
        This method initializes default permissions for all backends and sets up
        the necessary RBAC permissions.
        """
        if self._initialized:
            return
        
        logger.info("Initializing backend authorization system")
        
        # Get all available backends
        if self.storage_backend_manager:
            backend_ids = await self.storage_backend_manager.list_backends()
            
            # Create default permissions for each backend
            for backend_id in backend_ids:
                self._backend_permissions[backend_id] = BackendPermission(
                    backend_id=backend_id,
                    default_allow=self.default_allow
                )
                logger.debug(f"Created default permissions for backend: {backend_id}")
        
        # Create RBAC permissions for backend access
        await self._create_rbac_permissions()
        
        self._initialized = True
        logger.info("Backend authorization system initialized")
    
    async def _create_rbac_permissions(self):
        """Create RBAC permissions for backend access."""
        # Create basic backend permissions
        for backend_id, perm in self._backend_permissions.items():
            # Create backend access permission
            access_perm_id = f"backend:{backend_id}:access"
            if not self.rbac_manager.get_permission(access_perm_id):
                self.rbac_manager.create_permission({
                    "id": access_perm_id,
                    "name": f"Access {backend_id} Backend",
                    "description": f"Permission to access the {backend_id} backend",
                    "resource_type": "backend",
                    "actions": ["access"],
                    "effect": PermissionEffect.ALLOW,
                    "backend_id": backend_id
                })
            
            # Create backend read permission
            read_perm_id = f"backend:{backend_id}:read"
            if not self.rbac_manager.get_permission(read_perm_id):
                self.rbac_manager.create_permission({
                    "id": read_perm_id,
                    "name": f"Read from {backend_id} Backend",
                    "description": f"Permission to read from the {backend_id} backend",
                    "resource_type": "backend",
                    "actions": ["read"],
                    "effect": PermissionEffect.ALLOW,
                    "backend_id": backend_id
                })
            
            # Create backend write permission
            write_perm_id = f"backend:{backend_id}:write"
            if not self.rbac_manager.get_permission(write_perm_id):
                self.rbac_manager.create_permission({
                    "id": write_perm_id,
                    "name": f"Write to {backend_id} Backend",
                    "description": f"Permission to write to the {backend_id} backend",
                    "resource_type": "backend",
                    "actions": ["write"],
                    "effect": PermissionEffect.ALLOW,
                    "backend_id": backend_id
                })
            
            # Create backend admin permission
            admin_perm_id = f"backend:{backend_id}:admin"
            if not self.rbac_manager.get_permission(admin_perm_id):
                self.rbac_manager.create_permission({
                    "id": admin_perm_id,
                    "name": f"Administer {backend_id} Backend",
                    "description": f"Permission to administer the {backend_id} backend",
                    "resource_type": "backend",
                    "actions": ["admin"],
                    "effect": PermissionEffect.ALLOW,
                    "backend_id": backend_id
                })
        
        logger.info("Created RBAC permissions for backend access")
    
    async def check_backend_access(
        self,
        user: Optional[User],
        backend_id: str,
        operation: str = "access",
        api_key: Optional[ApiKey] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if a user or API key has permission to access a backend.
        
        Args:
            user: User attempting access (or None if using API key only)
            backend_id: ID of the backend to check
            operation: Operation to perform (e.g., "access", "read", "write", "admin")
            api_key: Optional API key being used for access
            context: Optional additional context for condition evaluation
            
        Returns:
            True if access is allowed, False otherwise
        """
        # Ensure initialization
        if not self._initialized:
            await self.initialize()
        
        # If backend doesn't exist, deny access
        if backend_id not in self._backend_permissions:
            logger.warning(f"Backend {backend_id} not found in permissions")
            return False
        
        backend_perm = self._backend_permissions[backend_id]
        user_id = user.id if user else None
        
        # Check API key permissions first if provided
        if api_key:
            # Check if the API key has explicit backend permissions
            if hasattr(api_key, "permissions") and hasattr(api_key.permissions, "allowed_backends"):
                # If allowed backends is specified and this backend is not in it, deny access
                if (api_key.permissions.allowed_backends is not None and 
                    backend_id not in api_key.permissions.allowed_backends):
                    return False
                
                # If this backend is explicitly denied, deny access
                if backend_id in getattr(api_key.permissions, "denied_backends", []):
                    return False
            
            # Check RBAC permissions for the API key if it has roles or permission IDs
            if hasattr(api_key, "permissions"):
                # Check direct permissions
                if hasattr(api_key.permissions, "permission_ids"):
                    permission_id = f"backend:{backend_id}:{operation}"
                    if permission_id in api_key.permissions.permission_ids:
                        return True
                
                # Check role-based permissions
                if hasattr(api_key.permissions, "role_ids") and self.rbac_manager:
                    for role_id in api_key.permissions.role_ids:
                        if self.rbac_manager.check_permission(
                            user_id=user_id or api_key.user_id,
                            action=operation,
                            resource_type="backend",
                            resource_id=backend_id,
                            backend_id=backend_id,
                            context=context
                        ):
                            return True
        
        # If no user is provided and API key check failed, deny access
        if not user:
            return False
        
        # Check user-specific permissions
        if user_id in backend_perm.denied_users:
            return False
        
        if operation != "access" and operation != "read" and user_id in backend_perm.read_only_users:
            return False
        
        if operation == "admin" and user_id not in backend_perm.admin_users:
            # Check admin roles
            if not any(role in backend_perm.admin_roles for role in user.roles):
                return False
        
        if user_id in backend_perm.allowed_users:
            return True
        
        # Check role-based permissions
        for role in user.roles:
            if role in backend_perm.denied_roles:
                return False
            
            if operation != "access" and operation != "read" and role in backend_perm.read_only_roles:
                return False
            
            if role in backend_perm.allowed_roles:
                return True
        
        # Check RBAC permissions
        if self.rbac_manager:
            if self.rbac_manager.check_permission(
                user_id=user_id,
                action=operation,
                resource_type="backend",
                resource_id=backend_id,
                backend_id=backend_id,
                group_ids=[role for role in user.roles],
                context=context
            ):
                return True
        
        # No explicit permission found, use default
        return backend_perm.default_allow
    
    async def set_backend_permission(
        self,
        backend_id: str,
        permission_type: str,
        entity_id: str,
        entity_type: str = "user",
        add: bool = True
    ) -> bool:
        """
        Set a permission for a backend.
        
        Args:
            backend_id: ID of the backend
            permission_type: Type of permission (allowed, denied, read_only, admin)
            entity_id: ID of the user or role
            entity_type: Type of entity (user or role)
            add: True to add the permission, False to remove it
            
        Returns:
            True if the permission was set successfully, False otherwise
        """
        # Ensure initialization
        if not self._initialized:
            await self.initialize()
        
        # Create backend permission if it doesn't exist
        if backend_id not in self._backend_permissions:
            self._backend_permissions[backend_id] = BackendPermission(
                backend_id=backend_id,
                default_allow=self.default_allow
            )
        
        backend_perm = self._backend_permissions[backend_id]
        
        # Determine which permission set to modify
        if entity_type == "user":
            if permission_type == "allowed":
                permission_set = backend_perm.allowed_users
            elif permission_type == "denied":
                permission_set = backend_perm.denied_users
            elif permission_type == "read_only":
                permission_set = backend_perm.read_only_users
            elif permission_type == "admin":
                permission_set = backend_perm.admin_users
            else:
                logger.error(f"Invalid permission type: {permission_type}")
                return False
        elif entity_type == "role":
            if permission_type == "allowed":
                permission_set = backend_perm.allowed_roles
            elif permission_type == "denied":
                permission_set = backend_perm.denied_roles
            elif permission_type == "read_only":
                permission_set = backend_perm.read_only_roles
            elif permission_type == "admin":
                permission_set = backend_perm.admin_roles
            else:
                logger.error(f"Invalid permission type: {permission_type}")
                return False
        else:
            logger.error(f"Invalid entity type: {entity_type}")
            return False
        
        # Add or remove the permission
        if add:
            permission_set.add(entity_id)
        else:
            if entity_id in permission_set:
                permission_set.remove(entity_id)
        
        logger.info(
            f"{'Added' if add else 'Removed'} {permission_type} permission for "
            f"{entity_type} {entity_id} on backend {backend_id}"
        )
        
        return True
    
    async def get_backend_permissions(self, backend_id: str) -> Optional[BackendPermission]:
        """
        Get permissions for a backend.
        
        Args:
            backend_id: ID of the backend
            
        Returns:
            BackendPermission object or None if not found
        """
        # Ensure initialization
        if not self._initialized:
            await self.initialize()
        
        return self._backend_permissions.get(backend_id)
    
    async def list_accessible_backends(
        self,
        user: Optional[User],
        operation: str = "access",
        api_key: Optional[ApiKey] = None
    ) -> List[str]:
        """
        List all backends that a user or API key has permission to access.
        
        Args:
            user: User to check
            operation: Operation to check permission for
            api_key: Optional API key to check
            
        Returns:
            List of backend IDs the user has permission to access
        """
        # Ensure initialization
        if not self._initialized:
            await self.initialize()
        
        # Check permissions for each backend
        accessible_backends = []
        for backend_id in self._backend_permissions:
            has_access = await self.check_backend_access(
                user=user,
                backend_id=backend_id,
                operation=operation,
                api_key=api_key
            )
            
            if has_access:
                accessible_backends.append(backend_id)
        
        return accessible_backends
    
    async def set_default_policy(self, backend_id: str, allow: bool) -> bool:
        """
        Set the default access policy for a backend.
        
        Args:
            backend_id: ID of the backend
            allow: Whether to allow access by default
            
        Returns:
            True if the policy was set successfully, False otherwise
        """
        # Ensure initialization
        if not self._initialized:
            await self.initialize()
        
        # Create backend permission if it doesn't exist
        if backend_id not in self._backend_permissions:
            self._backend_permissions[backend_id] = BackendPermission(
                backend_id=backend_id,
                default_allow=allow
            )
            return True
        
        # Update existing permission
        self._backend_permissions[backend_id].default_allow = allow
        logger.info(f"Set default policy for backend {backend_id} to {'allow' if allow else 'deny'}")
        
        return True


# Singleton instance
_backend_auth_manager = None


def get_backend_auth_manager() -> BackendAuthorizationManager:
    """
    Get the singleton backend authorization manager instance.
    
    Returns:
        BackendAuthorizationManager instance
    """
    global _backend_auth_manager
    return _backend_auth_manager


async def initialize_backend_auth_manager(
    rbac_manager: RBACManager,
    storage_backend_manager = None,
    default_allow: bool = False
) -> BackendAuthorizationManager:
    """
    Initialize the backend authorization manager.
    
    Args:
        rbac_manager: Role-Based Access Control manager
        storage_backend_manager: Storage Backend Manager instance
        default_allow: Whether to allow access by default if no specific permission is found
        
    Returns:
        Initialized BackendAuthorizationManager instance
    """
    global _backend_auth_manager
    
    if _backend_auth_manager is None:
        _backend_auth_manager = BackendAuthorizationManager(
            rbac_manager=rbac_manager,
            storage_backend_manager=storage_backend_manager,
            default_allow=default_allow
        )
    
    # Initialize the manager
    await _backend_auth_manager.initialize()
    
    return _backend_auth_manager


async def setup_backend_authorization(storage_backend_manager, rbac_manager=None) -> BackendAuthorizationManager:
    """
    Set up backend authorization.
    
    This is a convenience function that initializes the backend authorization manager
    and returns it for use.
    
    Args:
        storage_backend_manager: Storage Backend Manager instance
        rbac_manager: Optional Role-Based Access Control manager (will use global if None)
        
    Returns:
        Initialized BackendAuthorizationManager instance
    """
    # Get RBAC manager if not provided
    if rbac_manager is None:
        from ipfs_kit_py.mcp.auth.rbac import rbac_manager as global_rbac_manager
        rbac_manager = global_rbac_manager
    
    # Initialize backend authorization manager
    manager = await initialize_backend_auth_manager(
        rbac_manager=rbac_manager,
        storage_backend_manager=storage_backend_manager,
        default_allow=False  # Default to deny for security
    )
    
    logger.info("Backend authorization set up complete")
    
    return manager