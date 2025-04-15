"""
Integrated Backend Authorization Module

This module integrates RBAC with backend-specific authorization, providing a unified
permission system that controls access to different storage backends based on user roles.

Part of the MCP Roadmap Phase 1: Advanced Authentication & Authorization.
"""

import os
import json
import logging
import time
from typing import Dict, List, Optional, Union, Any
from enum import Enum
import asyncio
from datetime import datetime, timedelta
import functools

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer

from ..auth.models import User, Role, Permission
from ..rbac import rbac_manager, has_permission, check_permission, require_permission

# Configure logging
logger = logging.getLogger("mcp.auth.backend_auth")

# Backend permission mapping
class BackendPermission(Enum):
    """Permission types for backend operations"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    LIST = "list"
    PIN = "pin"
    SYNC = "sync"

# Backend operation to permission mapping
OPERATION_PERMISSION_MAP = {
    # Generic operations
    "list": BackendPermission.LIST,
    "get": BackendPermission.READ,
    "add": BackendPermission.WRITE,
    "delete": BackendPermission.DELETE,
    "info": BackendPermission.READ,
    
    # IPFS specific
    "pin_add": BackendPermission.PIN,
    "pin_rm": BackendPermission.PIN,
    "pin_ls": BackendPermission.LIST,
    "cat": BackendPermission.READ,
    "get": BackendPermission.READ,
    "add": BackendPermission.WRITE,
    "dag_get": BackendPermission.READ,
    "dag_put": BackendPermission.WRITE,
    "files_cp": BackendPermission.WRITE,
    "files_ls": BackendPermission.LIST,
    "files_mkdir": BackendPermission.WRITE,
    "files_rm": BackendPermission.DELETE,
    "files_read": BackendPermission.READ,
    "files_write": BackendPermission.WRITE,
    "files_stat": BackendPermission.READ,
    "dht_findpeer": BackendPermission.READ,
    "dht_findprovs": BackendPermission.READ,
    "dht_put": BackendPermission.WRITE,
    "dht_get": BackendPermission.READ,
    
    # Filecoin specific
    "deal_create": BackendPermission.WRITE,
    "deal_list": BackendPermission.LIST,
    "deal_status": BackendPermission.READ,
    "deal_verify": BackendPermission.READ,
    "miner_list": BackendPermission.LIST,
    "miner_info": BackendPermission.READ,
    
    # S3 specific
    "bucket_create": BackendPermission.WRITE,
    "bucket_list": BackendPermission.LIST,
    "bucket_delete": BackendPermission.DELETE,
    "object_put": BackendPermission.WRITE,
    "object_get": BackendPermission.READ,
    "object_delete": BackendPermission.DELETE,
    "object_list": BackendPermission.LIST,
    
    # Storacha specific
    "upload": BackendPermission.WRITE,
    "download": BackendPermission.READ,
    "delete": BackendPermission.DELETE,
    "status": BackendPermission.READ,
    "list": BackendPermission.LIST,
    
    # HuggingFace specific
    "model_download": BackendPermission.READ,
    "model_push": BackendPermission.WRITE,
    "model_list": BackendPermission.LIST,
    "dataset_download": BackendPermission.READ,
    "dataset_push": BackendPermission.WRITE,
    "dataset_list": BackendPermission.LIST,
    
    # Lassie specific
    "fetch": BackendPermission.READ,
    "fetch_all": BackendPermission.READ,
    "fetch_range": BackendPermission.READ,
    "status": BackendPermission.READ,
}

class BackendAuthorization:
    """
    Backend Authorization Manager for controlling access to storage backends
    based on user roles and permissions.
    """
    
    def __init__(self):
        """Initialize the backend authorization manager."""
        # Mapping of backend names to custom permission sets
        self.backend_permissions: Dict[str, Dict[Role, List[BackendPermission]]] = {}
        
        # Cache of permission checks for performance
        self.permission_cache = {}
        
        # Audit logging for backend access
        self.access_log = []
        self.max_log_entries = 1000
        
        # Default authorization map for standard backends
        self._init_default_backend_permissions()
        
        # Load custom backend permissions if available
        self._load_custom_permissions()
    
    def _init_default_backend_permissions(self):
        """Initialize default backend permissions based on roles."""
        # Default backend permissions for different roles
        default_permissions = {
            Role.ADMIN: [
                BackendPermission.READ,
                BackendPermission.WRITE,
                BackendPermission.DELETE,
                BackendPermission.ADMIN,
                BackendPermission.LIST,
                BackendPermission.PIN,
                BackendPermission.SYNC
            ],
            Role.DEVELOPER: [
                BackendPermission.READ,
                BackendPermission.WRITE,
                BackendPermission.LIST,
                BackendPermission.PIN
            ],
            Role.USER: [
                BackendPermission.READ,
                BackendPermission.WRITE,
                BackendPermission.LIST
            ],
            Role.ANONYMOUS: [
                BackendPermission.READ,
                BackendPermission.LIST
            ]
        }
        
        # Standard backends
        standard_backends = ["ipfs", "filecoin", "storacha", "s3", "huggingface", "lassie"]
        
        # Initialize permissions for standard backends
        for backend in standard_backends:
            self.backend_permissions[backend] = default_permissions.copy()
    
    def _load_custom_permissions(self):
        """Load custom backend permissions from configuration file."""
        config_path = os.environ.get(
            "BACKEND_AUTH_CONFIG",
            os.path.join(os.path.expanduser("~"), ".ipfs_kit", "backend_auth.json")
        )
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                # Process backend permissions
                if "backend_permissions" in config:
                    for backend, roles_config in config["backend_permissions"].items():
                        if backend not in self.backend_permissions:
                            self.backend_permissions[backend] = {}
                        
                        for role_name, permissions in roles_config.items():
                            try:
                                role = Role(role_name)
                                backend_perms = [BackendPermission(p) for p in permissions]
                                self.backend_permissions[backend][role] = backend_perms
                            except ValueError:
                                logger.warning(f"Invalid role or permission in config: {role_name}, {permissions}")
                
                logger.info(f"Loaded custom backend permissions from {config_path}")
            except Exception as e:
                logger.error(f"Error loading backend permissions from {config_path}: {e}")
    
    def has_backend_permission(self, user: User, backend: str, 
                             permission: Union[BackendPermission, str],
                             log_access: bool = True) -> bool:
        """
        Check if a user has the required permission for a backend.
        
        Args:
            user: User object
            backend: Backend name
            permission: Required permission
            log_access: Whether to log this access check
            
        Returns:
            True if the user has permission, False otherwise
        """
        # Admin role always has access
        if user.role == Role.ADMIN or user.role == Role.SYSTEM:
            if log_access:
                self._log_access(user, backend, permission, True, "Admin/System role")
            return True
        
        # Convert string permission to enum if needed
        if isinstance(permission, str):
            try:
                permission = BackendPermission(permission)
            except ValueError:
                # Check if it's an operation that maps to a permission
                if permission in OPERATION_PERMISSION_MAP:
                    permission = OPERATION_PERMISSION_MAP[permission]
                else:
                    logger.warning(f"Unknown permission or operation: {permission}")
                    if log_access:
                        self._log_access(user, backend, permission, False, "Unknown permission")
                    return False
        
        # Check cache
        cache_key = f"{user.id}:{backend}:{permission.value}"
        if cache_key in self.permission_cache:
            cached_result = self.permission_cache[cache_key]
            # Check if cache is still valid (5 minutes)
            if cached_result["timestamp"] > datetime.now() - timedelta(minutes=5):
                if log_access:
                    self._log_access(user, backend, permission, cached_result["result"], "Cached result")
                return cached_result["result"]
        
        # Check if backend exists in permissions map
        if backend not in self.backend_permissions:
            # Default to false for unknown backends
            if log_access:
                self._log_access(user, backend, permission, False, "Unknown backend")
            return False
        
        # Check if role exists in backend permissions
        if user.role not in self.backend_permissions[backend]:
            # Default to false for undefined role permissions
            if log_access:
                self._log_access(user, backend, permission, False, "Role not defined for backend")
            return False
        
        # Check if permission is in allowed permissions for role
        allowed = permission in self.backend_permissions[backend][user.role]
        
        # Cache the result
        self.permission_cache[cache_key] = {
            "result": allowed,
            "timestamp": datetime.now()
        }
        
        if log_access:
            self._log_access(user, backend, permission, allowed, "Direct permission check")
        
        return allowed
    
    def set_backend_permissions(self, backend: str, role: Role, 
                              permissions: List[BackendPermission]) -> bool:
        """
        Set permissions for a role on a specific backend.
        
        Args:
            backend: Backend name
            role: User role
            permissions: List of allowed permissions
            
        Returns:
            True if permissions were set successfully
        """
        if backend not in self.backend_permissions:
            self.backend_permissions[backend] = {}
        
        self.backend_permissions[backend][role] = permissions
        
        # Clear cache entries for this backend and role
        cache_keys = [k for k in self.permission_cache if k.split(':')[1] == backend]
        for key in cache_keys:
            del self.permission_cache[key]
        
        logger.info(f"Set {len(permissions)} permissions for role {role.value} on backend {backend}")
        return True
    
    def get_backend_permissions(self, backend: str, role: Optional[Role] = None) -> Dict:
        """
        Get permissions for a backend.
        
        Args:
            backend: Backend name
            role: Optional role to filter by
            
        Returns:
            Dictionary of permissions by role (or for specific role)
        """
        if backend not in self.backend_permissions:
            return {}
        
        if role:
            if role not in self.backend_permissions[backend]:
                return {}
            
            return {
                "backend": backend,
                "role": role.value,
                "permissions": [p.value for p in self.backend_permissions[backend][role]]
            }
        
        # Return all roles for this backend
        result = {
            "backend": backend,
            "roles": {}
        }
        
        for r, perms in self.backend_permissions[backend].items():
            result["roles"][r.value] = [p.value for p in perms]
        
        return result
    
    def list_backends(self) -> List[str]:
        """
        Get list of backends with defined permissions.
        
        Returns:
            List of backend names
        """
        return list(self.backend_permissions.keys())
    
    def _log_access(self, user: User, backend: str, 
                   permission: Union[BackendPermission, str],
                   allowed: bool, reason: str):
        """
        Log an access check for audit purposes.
        
        Args:
            user: User object
            backend: Backend name
            permission: Requested permission
            allowed: Whether access was allowed
            reason: Reason for the decision
        """
        # Convert permission to string if it's an enum
        perm_str = permission.value if isinstance(permission, BackendPermission) else str(permission)
        
        # Create log entry
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user.id,
            "username": user.username,
            "role": user.role.value,
            "backend": backend,
            "permission": perm_str,
            "allowed": allowed,
            "reason": reason
        }
        
        # Add to log
        self.access_log.append(entry)
        
        # Trim log if needed
        if len(self.access_log) > self.max_log_entries:
            self.access_log = self.access_log[-self.max_log_entries:]
    
    def get_access_logs(self, limit: int = 100, 
                      filter_user: Optional[str] = None,
                      filter_backend: Optional[str] = None,
                      filter_allowed: Optional[bool] = None) -> List[Dict]:
        """
        Get backend access audit logs with optional filtering.
        
        Args:
            limit: Maximum number of log entries to return
            filter_user: Optional user ID to filter by
            filter_backend: Optional backend name to filter by
            filter_allowed: Optional filter by allowed/denied
            
        Returns:
            List of log entries
        """
        # Apply filters
        filtered_logs = self.access_log
        
        if filter_user:
            filtered_logs = [log for log in filtered_logs if log["user_id"] == filter_user]
        
        if filter_backend:
            filtered_logs = [log for log in filtered_logs if log["backend"] == filter_backend]
        
        if filter_allowed is not None:
            filtered_logs = [log for log in filtered_logs if log["allowed"] == filter_allowed]
        
        # Return the most recent entries up to limit
        return filtered_logs[-limit:]
    
    def clear_permission_cache(self):
        """Clear the permission cache."""
        self.permission_cache = {}
        logger.info("Backend permission cache cleared")


# Singleton instance
_backend_auth_instance = None

def get_backend_auth() -> BackendAuthorization:
    """Get the singleton backend authorization instance."""
    global _backend_auth_instance
    if _backend_auth_instance is None:
        _backend_auth_instance = BackendAuthorization()
    return _backend_auth_instance


# API Integration Helpers

def require_backend_permission(backend: str, permission: Union[BackendPermission, str]):
    """
    Decorator to require a specific backend permission.
    
    Args:
        backend: Backend name
        permission: Required permission
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Get user from request
            from ..auth.router import get_current_user
            try:
                user = await get_current_user(request)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated"
                )
            
            # Get backend auth
            backend_auth = get_backend_auth()
            
            # Check permission
            if not backend_auth.has_backend_permission(user, backend, permission):
                logger.warning(f"Backend permission denied: {backend}/{permission} for user {user.username}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission} required for {backend} backend"
                )
            
            # Permission granted
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


def check_backend_operation(backend: str, operation: str, user: User) -> bool:
    """
    Check if a user has permission for a specific backend operation.
    
    Args:
        backend: Backend name
        operation: Operation name
        user: User object
        
    Returns:
        True if the user has permission for the operation
    """
    # Map operation to permission
    if operation in OPERATION_PERMISSION_MAP:
        permission = OPERATION_PERMISSION_MAP[operation]
    else:
        logger.warning(f"Unknown operation: {operation}")
        return False
    
    # Check permission
    backend_auth = get_backend_auth()
    return backend_auth.has_backend_permission(user, backend, permission)


async def verify_backend_permissions(user_id: Optional[str] = None) -> Dict:
    """
    Verify backend permissions for testing and debugging.
    
    Args:
        user_id: Optional user ID to check (defaults to test users)
        
    Returns:
        Dictionary with verification results
    """
    from ..auth.service import get_user_by_id
    from ..auth.models import User, Role
    
    # Get backend auth
    backend_auth = get_backend_auth()
    
    # Get user
    user = None
    if user_id:
        user = await get_user_by_id(user_id)
    
    # If no user provided or found, create test users for each role
    if not user:
        test_users = {
            Role.ADMIN: User(id="test_admin", username="test_admin", role=Role.ADMIN),
            Role.DEVELOPER: User(id="test_developer", username="test_developer", role=Role.DEVELOPER),
            Role.USER: User(id="test_user", username="test_user", role=Role.USER),
            Role.ANONYMOUS: User(id="test_anon", username="test_anon", role=Role.ANONYMOUS)
        }
    else:
        # Just use the provided user
        test_users = {user.role: user}
    
    # Test permissions for all backends
    backends = backend_auth.list_backends()
    
    # Test all permission types
    permission_types = list(BackendPermission)
    
    # Results structure
    results = {
        "backends": {},
        "timestamp": datetime.now().isoformat()
    }
    
    # Test each backend
    for backend in backends:
        backend_results = {}
        
        # Test each user role
        for role, test_user in test_users.items():
            role_results = {}
            
            # Test each permission
            for permission in permission_types:
                allowed = backend_auth.has_backend_permission(
                    test_user, backend, permission, log_access=False)
                role_results[permission.value] = allowed
            
            backend_results[role.value] = role_results
        
        results["backends"][backend] = backend_results
    
    return results