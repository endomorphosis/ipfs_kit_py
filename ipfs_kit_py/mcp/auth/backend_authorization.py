"""
Backend Authorization module for MCP server.

This module implements per-backend authorization capabilities
as specified in the MCP roadmap for Phase 1: Core Functionality Enhancements (Q3 2025).

Key features:
- Role-based access control for backends
- Per-backend authorization policies
- Fine-grained permission checking for storage operations
- Integration with audit logging system
"""

import logging
import time
import asyncio
from typing import Dict, Any, Optional, List, Set, Tuple
from enum import Enum

from .models import BackendPermission, Role, User, APIKey
from .audit import AuditEventType, get_instance as get_audit_logger

# Configure logging
logger = logging.getLogger(__name__)


class Operation(str, Enum):
    """Storage operation types."""
    STORE = "store"
    RETRIEVE = "retrieve"
    DELETE = "delete"
    LIST = "list"
    QUERY = "query"
    ADMIN = "admin"


class BackendAuthorizationManager:
    """
    Manager for backend-specific authorization rules.
    
    This class handles authorization decisions for storage backends
    based on user roles, permissions, and backend-specific policies.
    """
    
    def __init__(self):
        """Initialize the backend authorization manager."""
        # Backend permissions configuration
        self.backend_permissions: Dict[str, BackendPermission] = {}
        
        # Cache of permission decisions for performance
        self.decision_cache: Dict[str, Tuple[bool, float]] = {}
        self.cache_ttl = 300  # 5 minutes cache TTL
        
        # Audit logger
        self.audit_logger = get_audit_logger()
    
    async def initialize(self):
        """Initialize the backend authorization manager."""
        logger.info("Initializing backend authorization manager")
        
        # Start cache cleanup task
        asyncio.create_task(self._cleanup_cache())
        
        # Create default backend permissions
        await self._create_default_backend_permissions()
        
        logger.info("Backend authorization manager initialized")
    
    async def _cleanup_cache(self):
        """Background task to clean up expired cache entries."""
        while True:
            try:
                now = time.time()
                expired_keys = []
                
                # Find expired entries
                for key, (_, timestamp) in self.decision_cache.items():
                    if now - timestamp > self.cache_ttl:
                        expired_keys.append(key)
                
                # Remove expired entries
                for key in expired_keys:
                    del self.decision_cache[key]
                
                if expired_keys:
                    logger.debug(f"Cleaned up {len(expired_keys)} expired authorization cache entries")
            except Exception as e:
                logger.error(f"Error cleaning up authorization cache: {e}")
            
            # Sleep for 5 minutes
            await asyncio.sleep(300)
    
    async def _create_default_backend_permissions(self):
        """Create default backend permissions configurations."""
        # Note: This would typically load from a database
        # For now, we'll just set up some defaults in memory
        
        # Default permissions for IPFS backend
        self.set_backend_permission(
            backend_id="ipfs",
            permission=BackendPermission(
                backend_id="ipfs",
                allowed_roles={"admin", "user", "storage_manager"},
                allowed_permissions={"storage:read", "storage:write", "storage:list"},
                public=False,
                read_only=False,
                admin_only=False,
            )
        )
        
        # Default permissions for S3 backend
        self.set_backend_permission(
            backend_id="s3",
            permission=BackendPermission(
                backend_id="s3",
                allowed_roles={"admin", "storage_manager"},
                allowed_permissions={"storage:read", "storage:write", "storage:list", "s3:access"},
                public=False,
                read_only=False,
                admin_only=False,
            )
        )
        
        # Default permissions for Filecoin backend
        self.set_backend_permission(
            backend_id="filecoin",
            permission=BackendPermission(
                backend_id="filecoin",
                allowed_roles={"admin", "storage_manager"},
                allowed_permissions={"storage:read", "storage:write", "storage:list", "filecoin:access"},
                public=False,
                read_only=False,
                admin_only=True,  # Only admins can use Filecoin by default
            )
        )
        
        # Default permissions for HuggingFace backend
        self.set_backend_permission(
            backend_id="huggingface",
            permission=BackendPermission(
                backend_id="huggingface",
                allowed_roles={"admin", "ai_manager"},
                allowed_permissions={"storage:read", "storage:list", "ai:model_access"},
                public=False,
                read_only=True,  # Read-only by default
                admin_only=False,
            )
        )
        
        logger.info("Created default backend permissions")
    
    def set_backend_permission(self, backend_id: str, permission: BackendPermission) -> None:
        """
        Set permissions for a specific backend.
        
        Args:
            backend_id: Identifier for the backend
            permission: Backend permission configuration
        """
        self.backend_permissions[backend_id] = permission
        logger.info(f"Set permissions for backend {backend_id}")
        
        # Clear any cached decisions for this backend
        cache_keys_to_remove = []
        for key in self.decision_cache:
            if key.startswith(f"{backend_id}:"):
                cache_keys_to_remove.append(key)
        
        for key in cache_keys_to_remove:
            del self.decision_cache[key]
    
    def get_backend_permission(self, backend_id: str) -> Optional[BackendPermission]:
        """
        Get permissions for a specific backend.
        
        Args:
            backend_id: Identifier for the backend
            
        Returns:
            Backend permission configuration or None if not found
        """
        return self.backend_permissions.get(backend_id)
    
    async def check_backend_access(
        self,
        backend_id: str,
        user: Optional[User] = None,
        api_key: Optional[APIKey] = None,
        operation: Operation = Operation.RETRIEVE,
        resource_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Check if a user or API key has access to a backend for a specific operation.
        
        Args:
            backend_id: Identifier for the backend
            user: User making the request
            api_key: API key used for the request
            operation: Operation being performed
            resource_id: Optional identifier for the specific resource
            
        Returns:
            Tuple of (allowed, reason)
        """
        # Get the backend permission configuration
        backend_perm = self.get_backend_permission(backend_id)
        if not backend_perm:
            # No specific permission config, use conservative default
            logger.warning(f"No permission configuration found for backend {backend_id}")
            return False, f"No permission configuration for backend {backend_id}"
        
        # Check cache for decision
        cache_key = None
        if user:
            cache_key = f"{backend_id}:{operation}:{user.id}"
        elif api_key:
            cache_key = f"{backend_id}:{operation}:{api_key.id}:api_key"
        
        if cache_key and cache_key in self.decision_cache:
            decision, _ = self.decision_cache[cache_key]
            return decision, "Cached decision"
        
        # Check if backend is public
        if backend_perm.public and operation == Operation.RETRIEVE:
            # Public backends allow retrieval without authentication
            return True, "Public backend"
        
        # User or API key must be provided for non-public backends
        if not user and not api_key:
            return False, "Authentication required"
        
        # Check for backend restrictions on API key
        if api_key and api_key.backend_restrictions:
            if backend_id not in api_key.backend_restrictions:
                return False, f"API key not authorized for backend {backend_id}"
        
        # Check if backend is admin-only
        if backend_perm.admin_only:
            # For API keys
            if api_key:
                if "admin" not in api_key.roles:
                    return False, "Admin role required for this backend"
            # For users
            elif user:
                if "admin" not in user.roles:
                    return False, "Admin role required for this backend"
        
        # Check if backend is read-only and operation is not read-compatible
        if backend_perm.read_only and operation not in [Operation.RETRIEVE, Operation.LIST, Operation.QUERY]:
            return False, f"Backend {backend_id} is read-only"
        
        # Check role-based access
        allowed_by_role = False
        if api_key:
            # Check if API key has any of the allowed roles
            if any(role in api_key.roles for role in backend_perm.allowed_roles):
                allowed_by_role = True
        elif user:
            # Check if user has any of the allowed roles
            if any(role in user.roles for role in backend_perm.allowed_roles):
                allowed_by_role = True
        
        # Check permission-based access
        allowed_by_permission = False
        if api_key:
            # For API keys, check direct permissions
            if any(perm in api_key.direct_permissions for perm in backend_perm.allowed_permissions):
                allowed_by_permission = True
        elif user:
            # For users, normally we would check permissions
            # This would involve getting all permissions from user's roles
            # For simplicity, we'll assume role check is sufficient
            allowed_by_permission = True
        
        # Make final decision
        allowed = allowed_by_role or allowed_by_permission
        
        # Record in cache
        if cache_key:
            self.decision_cache[cache_key] = (allowed, time.time())
        
        # Log the decision to audit log if available
        if self.audit_logger:
            user_id = user.id if user else (api_key.user_id if api_key else None)
            username = user.username if user else None
            
            # Create backend details
            details = {
                "operation": operation,
                "resource_id": resource_id,
                "allowed_by_role": allowed_by_role,
                "allowed_by_permission": allowed_by_permission,
                "api_key_used": bool(api_key),
            }
            
            # Log to audit logger
            await self.audit_logger.log_backend_access(
                success=allowed,
                backend_id=backend_id,
                user_id=user_id,
                username=username,
                action=operation,
                details=details,
            )
        
        if allowed:
            return True, "Access granted based on roles/permissions"
        else:
            return False, "Insufficient permissions for this backend"
    
    def get_accessible_backends(
        self,
        user: User,
        operation: Operation = Operation.RETRIEVE,
    ) -> List[str]:
        """
        Get a list of backends that a user can access for a specific operation.
        
        Args:
            user: User to check
            operation: Operation to check
            
        Returns:
            List of backend IDs that the user can access
        """
        accessible_backends = []
        
        for backend_id, perm in self.backend_permissions.items():
            # Check if backend is public for retrieval
            if perm.public and operation == Operation.RETRIEVE:
                accessible_backends.append(backend_id)
                continue
                
            # Check if backend is read-only and operation is not read-compatible
            if perm.read_only and operation not in [Operation.RETRIEVE, Operation.LIST, Operation.QUERY]:
                continue
                
            # Check if backend is admin-only
            if perm.admin_only and "admin" not in user.roles:
                continue
                
            # Check role-based access
            if any(role in user.roles for role in perm.allowed_roles):
                accessible_backends.append(backend_id)
                continue
        
        return accessible_backends

    async def add_backend_role(
        self,
        backend_id: str,
        role: str,
    ) -> bool:
        """
        Add a role to a backend's allowed roles.
        
        Args:
            backend_id: Identifier for the backend
            role: Role to add
            
        Returns:
            True if successful
        """
        backend_perm = self.get_backend_permission(backend_id)
        if not backend_perm:
            # Create new permission config
            backend_perm = BackendPermission(
                backend_id=backend_id,
                allowed_roles={role},
                allowed_permissions=set(),
                public=False,
                read_only=False,
                admin_only=False,
            )
            self.set_backend_permission(backend_id, backend_perm)
            return True
        
        # Add role to existing config
        if role not in backend_perm.allowed_roles:
            backend_perm.allowed_roles.add(role)
            backend_perm.updated_at = time.time()
            self.set_backend_permission(backend_id, backend_perm)
        
        return True

    async def remove_backend_role(
        self,
        backend_id: str,
        role: str,
    ) -> bool:
        """
        Remove a role from a backend's allowed roles.
        
        Args:
            backend_id: Identifier for the backend
            role: Role to remove
            
        Returns:
            True if successful
        """
        backend_perm = self.get_backend_permission(backend_id)
        if not backend_perm:
            return False
        
        # Remove role if it exists
        if role in backend_perm.allowed_roles:
            backend_perm.allowed_roles.remove(role)
            backend_perm.updated_at = time.time()
            self.set_backend_permission(backend_id, backend_perm)
        
        return True

    async def add_backend_permission(
        self,
        backend_id: str,
        permission: str,
    ) -> bool:
        """
        Add a permission to a backend's allowed permissions.
        
        Args:
            backend_id: Identifier for the backend
            permission: Permission to add
            
        Returns:
            True if successful
        """
        backend_perm = self.get_backend_permission(backend_id)
        if not backend_perm:
            # Create new permission config
            backend_perm = BackendPermission(
                backend_id=backend_id,
                allowed_roles=set(),
                allowed_permissions={permission},
                public=False,
                read_only=False,
                admin_only=False,
            )
            self.set_backend_permission(backend_id, backend_perm)
            return True
        
        # Add permission to existing config
        if permission not in backend_perm.allowed_permissions:
            backend_perm.allowed_permissions.add(permission)
            backend_perm.updated_at = time.time()
            self.set_backend_permission(backend_id, backend_perm)
        
        return True

    async def remove_backend_permission(
        self,
        backend_id: str,
        permission: str,
    ) -> bool:
        """
        Remove a permission from a backend's allowed permissions.
        
        Args:
            backend_id: Identifier for the backend
            permission: Permission to remove
            
        Returns:
            True if successful
        """
        backend_perm = self.get_backend_permission(backend_id)
        if not backend_perm:
            return False
        
        # Remove permission if it exists
        if permission in backend_perm.allowed_permissions:
            backend_perm.allowed_permissions.remove(permission)
            backend_perm.updated_at = time.time()
            self.set_backend_permission(backend_id, backend_perm)
        
        return True

    async def set_backend_public(
        self,
        backend_id: str,
        public: bool,
    ) -> bool:
        """
        Set whether a backend is publicly accessible.
        
        Args:
            backend_id: Identifier for the backend
            public: Whether backend is public
            
        Returns:
            True if successful
        """
        backend_perm = self.get_backend_permission(backend_id)
        if not backend_perm:
            # Create new permission config
            backend_perm = BackendPermission(
                backend_id=backend_id,
                allowed_roles=set(),
                allowed_permissions=set(),
                public=public,
                read_only=False,
                admin_only=False,
            )
            self.set_backend_permission(backend_id, backend_perm)
            return True
        
        # Update existing config
        backend_perm.public = public
        backend_perm.updated_at = time.time()
        self.set_backend_permission(backend_id, backend_perm)
        
        return True

    async def set_backend_read_only(
        self,
        backend_id: str,
        read_only: bool,
    ) -> bool:
        """
        Set whether a backend is read-only.
        
        Args:
            backend_id: Identifier for the backend
            read_only: Whether backend is read-only
            
        Returns:
            True if successful
        """
        backend_perm = self.get_backend_permission(backend_id)
        if not backend_perm:
            # Create new permission config
            backend_perm = BackendPermission(
                backend_id=backend_id,
                allowed_roles=set(),
                allowed_permissions=set(),
                public=False,
                read_only=read_only,
                admin_only=False,
            )
            self.set_backend_permission(backend_id, backend_perm)
            return True
        
        # Update existing config
        backend_perm.read_only = read_only
        backend_perm.updated_at = time.time()
        self.set_backend_permission(backend_id, backend_perm)
        
        return True

    async def set_backend_admin_only(
        self,
        backend_id: str,
        admin_only: bool,
    ) -> bool:
        """
        Set whether a backend is admin-only.
        
        Args:
            backend_id: Identifier for the backend
            admin_only: Whether backend is admin-only
            
        Returns:
            True if successful
        """
        backend_perm = self.get_backend_permission(backend_id)
        if not backend_perm:
            # Create new permission config
            backend_perm = BackendPermission(
                backend_id=backend_id,
                allowed_roles=set(),
                allowed_permissions=set(),
                public=False,
                read_only=False,
                admin_only=admin_only,
            )
            self.set_backend_permission(backend_id, backend_perm)
            return True
        
        # Update existing config
        backend_perm.admin_only = admin_only
        backend_perm.updated_at = time.time()
        self.set_backend_permission(backend_id, backend_perm)
        
        return True


# Singleton instance
_instance = None

def get_instance() -> BackendAuthorizationManager:
    """
    Get or create the singleton backend authorization manager instance.
    
    Returns:
        BackendAuthorizationManager instance
    """
    global _instance
    if _instance is None:
        _instance = BackendAuthorizationManager()
    return _instance
