#!/usr/bin/env python3
# ipfs_kit_py/mcp/auth/rbac_enhanced.py

"""
Enhanced Role-Based Access Control (RBAC) for IPFS Kit MCP Server.

This module provides comprehensive RBAC capabilities for the MCP server, including:
- Fine-grained permission management
- Per-backend authorization
- Role hierarchy
- Permission inheritance
- Dynamic permission checks
- Integration with authentication mechanisms
"""

import functools
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

# Set up logging
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# Permission and Role Classes
# -------------------------------------------------------------------------

class ResourceType(Enum):
    """Enum representing different resource types in the system."""
    GLOBAL = auto()
    STORAGE_BACKEND = auto()
    IPFS = auto()
    FILECOIN = auto()
    S3 = auto()
    STORACHA = auto()
    HUGGINGFACE = auto()
    LASSIE = auto()
    SEARCH = auto()
    USER = auto()
    API_KEY = auto()
    SYSTEM_CONFIG = auto()
    MONITORING = auto()


@dataclass
class Permission:
    """Represents a permission in the system."""
    name: str
    description: str
    resource_type: ResourceType
    
    def __hash__(self):
        return hash((self.name, self.resource_type))
    
    def __eq__(self, other):
        if not isinstance(other, Permission):
            return False
        return self.name == other.name and self.resource_type == other.resource_type


class Action(Enum):
    """Standard actions that can be performed on resources."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"
    LIST = "list"


# Standard global permissions
GLOBAL_PERMISSIONS = {
    Action.READ.value: Permission(Action.READ.value, "Read any resource", ResourceType.GLOBAL),
    Action.WRITE.value: Permission(Action.WRITE.value, "Write to any resource", ResourceType.GLOBAL),
    Action.DELETE.value: Permission(Action.DELETE.value, "Delete any resource", ResourceType.GLOBAL),
    Action.ADMIN.value: Permission(Action.ADMIN.value, "Full administrative access", ResourceType.GLOBAL),
    Action.LIST.value: Permission(Action.LIST.value, "List resources", ResourceType.GLOBAL),
}

# Backend-specific permissions
def get_backend_permission(backend: str, action: Action) -> Permission:
    """Generate a permission for a specific backend and action."""
    return Permission(
        f"{backend.lower()}:{action.value}",
        f"{action.value.capitalize()} access to {backend}",
        getattr(ResourceType, backend.upper(), ResourceType.STORAGE_BACKEND)
    )


@dataclass
class Role:
    """Represents a role with a set of permissions."""
    name: str
    description: str
    permissions: Set[Permission] = field(default_factory=set)
    parent_roles: Set[str] = field(default_factory=set)
    
    def add_permission(self, permission: Permission):
        """Add a permission to this role."""
        self.permissions.add(permission)
    
    def remove_permission(self, permission: Permission):
        """Remove a permission from this role."""
        if permission in self.permissions:
            self.permissions.remove(permission)
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if the role has a specific permission."""
        return permission in self.permissions
    
    def add_parent_role(self, role_name: str):
        """Add a parent role to inherit permissions from."""
        self.parent_roles.add(role_name)
    
    def remove_parent_role(self, role_name: str):
        """Remove a parent role."""
        if role_name in self.parent_roles:
            self.parent_roles.remove(role_name)


# -------------------------------------------------------------------------
# Role Manager
# -------------------------------------------------------------------------

class RoleManager:
    """Manages roles and their permissions."""
    
    def __init__(self):
        """Initialize the role manager with default roles."""
        self.roles: Dict[str, Role] = {}
        self._initialize_default_roles()
    
    def _initialize_default_roles(self):
        """Create default roles with standard permissions."""
        # Admin role - has all permissions
        admin_role = Role("admin", "Administrator with full access")
        for perm in GLOBAL_PERMISSIONS.values():
            admin_role.add_permission(perm)
        
        # Add admin permissions for each backend type
        for backend in ["IPFS", "FILECOIN", "S3", "STORACHA", "HUGGINGFACE", "LASSIE"]:
            for action in Action:
                admin_role.add_permission(get_backend_permission(backend, action))
        
        # User role - has limited permissions
        user_role = Role("user", "Standard user with basic access")
        user_role.add_permission(GLOBAL_PERMISSIONS[Action.READ.value])
        user_role.add_permission(GLOBAL_PERMISSIONS[Action.LIST.value])
        
        # Add read/write permissions for common backends
        for backend in ["IPFS", "FILECOIN"]:
            user_role.add_permission(get_backend_permission(backend, Action.READ))
            user_role.add_permission(get_backend_permission(backend, Action.WRITE))
        
        # Read-only role
        readonly_role = Role("read_only", "User with read-only access")
        readonly_role.add_permission(GLOBAL_PERMISSIONS[Action.READ.value])
        readonly_role.add_permission(GLOBAL_PERMISSIONS[Action.LIST.value])
        
        # Guest role - minimal permissions
        guest_role = Role("guest", "Unauthenticated user with minimal access")
        
        # Add all roles to the manager
        self.roles = {
            "admin": admin_role,
            "user": user_role,
            "read_only": readonly_role,
            "guest": guest_role
        }
    
    def get_role(self, role_name: str) -> Optional[Role]:
        """Get a role by name."""
        return self.roles.get(role_name)
    
    def create_role(self, name: str, description: str, parent_roles: Optional[List[str]] = None) -> Role:
        """Create a new role."""
        if name in self.roles:
            raise ValueError(f"Role {name} already exists")
        
        role = Role(name, description)
        if parent_roles:
            for parent in parent_roles:
                if parent in self.roles:
                    role.add_parent_role(parent)
                else:
                    logger.warning(f"Parent role {parent} does not exist")
        
        self.roles[name] = role
        return role
    
    def delete_role(self, name: str) -> bool:
        """Delete a role by name."""
        if name in self.roles:
            # Check if any other roles inherit from this one
            for role in self.roles.values():
                if name in role.parent_roles:
                    role.remove_parent_role(name)
            
            del self.roles[name]
            return True
        return False
    
    def add_permission_to_role(self, role_name: str, permission: Permission) -> bool:
        """Add a permission to a role."""
        role = self.get_role(role_name)
        if role:
            role.add_permission(permission)
            return True
        return False
    
    def remove_permission_from_role(self, role_name: str, permission: Permission) -> bool:
        """Remove a permission from a role."""
        role = self.get_role(role_name)
        if role:
            role.remove_permission(permission)
            return True
        return False
    
    def user_has_permission(self, user_roles: List[str], permission: Permission) -> bool:
        """Check if a user with given roles has a specific permission."""
        # Check direct permissions
        for role_name in user_roles:
            role = self.get_role(role_name)
            if role and self._role_has_permission(role, permission, set()):
                return True
        return False
    
    def _role_has_permission(self, role: Role, permission: Permission, checked_roles: Set[str]) -> bool:
        """
        Recursively check if a role has a permission, including inherited permissions.
        
        Args:
            role: The role to check
            permission: The permission to check for
            checked_roles: Set of role names already checked to prevent infinite recursion
        
        Returns:
            bool: True if the role has the permission, False otherwise
        """
        # Prevent infinite recursion with circular role inheritance
        if role.name in checked_roles:
            return False
        
        # Check if the role directly has the permission
        if role.has_permission(permission):
            return True
        
        # Check parent roles (inheritance)
        new_checked = checked_roles.copy()
        new_checked.add(role.name)
        
        for parent_role_name in role.parent_roles:
            parent_role = self.get_role(parent_role_name)
            if parent_role and self._role_has_permission(parent_role, permission, new_checked):
                return True
        
        return False
    
    def get_all_permissions_for_user(self, user_roles: List[str]) -> Set[Permission]:
        """Get all permissions for a user with the given roles."""
        all_permissions: Set[Permission] = set()
        checked_roles: Set[str] = set()
        
        for role_name in user_roles:
            role = self.get_role(role_name)
            if role:
                self._collect_role_permissions(role, all_permissions, checked_roles)
        
        return all_permissions
    
    def _collect_role_permissions(self, role: Role, all_permissions: Set[Permission], checked_roles: Set[str]):
        """
        Recursively collect all permissions from a role and its parents.
        
        Args:
            role: The role to collect permissions from
            all_permissions: Set to collect permissions into
            checked_roles: Set of role names already checked to prevent infinite recursion
        """
        if role.name in checked_roles:
            return
        
        # Add direct permissions
        all_permissions.update(role.permissions)
        
        # Add parent role permissions
        new_checked = checked_roles.copy()
        new_checked.add(role.name)
        
        for parent_role_name in role.parent_roles:
            parent_role = self.get_role(parent_role_name)
            if parent_role:
                self._collect_role_permissions(parent_role, all_permissions, new_checked)


# -------------------------------------------------------------------------
# Per-Backend Authorization
# -------------------------------------------------------------------------

class BackendAuthorization:
    """
    Handles per-backend authorization for storage backends.
    
    This class provides methods to check if a user has permissions
    to perform operations on specific backends.
    """
    
    def __init__(self, role_manager: RoleManager):
        """Initialize with a role manager."""
        self.role_manager = role_manager
    
    def can_access_backend(self, user_roles: List[str], backend: str, action: Action) -> bool:
        """
        Check if a user can access a specific backend.
        
        Args:
            user_roles: List of role names the user has
            backend: Backend name (e.g., "IPFS", "S3")
            action: The action to perform (e.g., READ, WRITE)
        
        Returns:
            bool: True if access is allowed, False otherwise
        """
        # Check if user has global permission for this action
        if self.role_manager.user_has_permission(user_roles, GLOBAL_PERMISSIONS[action.value]):
            return True
        
        # Check backend-specific permission
        return self.role_manager.user_has_permission(
            user_roles, 
            get_backend_permission(backend, action)
        )
    
    def get_accessible_backends(self, user_roles: List[str], action: Action) -> List[str]:
        """
        Get a list of backends a user can access for a specific action.
        
        Args:
            user_roles: List of role names the user has
            action: The action to check for (e.g., READ, WRITE)
        
        Returns:
            List[str]: List of backend names the user can access
        """
        permissions = self.role_manager.get_all_permissions_for_user(user_roles)
        accessible_backends = []
        
        # Check if user has global permission
        if GLOBAL_PERMISSIONS[action.value] in permissions:
            # If user has global permission, they can access all backends
            return [m.name for m in ResourceType if m != ResourceType.GLOBAL]
        
        # Check backend-specific permissions
        for backend in [r.name for r in ResourceType if r != ResourceType.GLOBAL]:
            backend_perm = get_backend_permission(backend, action)
            if backend_perm in permissions:
                accessible_backends.append(backend)
        
        return accessible_backends


# -------------------------------------------------------------------------
# API Key Management
# -------------------------------------------------------------------------

@dataclass
class ApiKey:
    """Represents an API key for authentication."""
    key_id: str
    key_hash: str  # Hashed API key for security
    user_id: str
    roles: List[str]
    description: str
    created_at: float
    expires_at: Optional[float] = None
    last_used: Optional[float] = None
    is_active: bool = True
    
    @classmethod
    def create(cls, user_id: str, roles: List[str], description: str, expires_in_days: Optional[int] = None) -> Tuple['ApiKey', str]:
        """
        Create a new API key.
        
        Args:
            user_id: ID of the user the key belongs to
            roles: List of roles to assign to the key
            description: Human-readable description of the key's purpose
            expires_in_days: Optional expiration in days from creation
        
        Returns:
            Tuple[ApiKey, str]: The API key object and the raw key value
        """
        import hashlib
        
        # Generate a random key
        key_value = str(uuid.uuid4())
        key_id = str(uuid.uuid4())
        
        # Hash the key for storage
        key_hash = hashlib.sha256(key_value.encode()).hexdigest()
        
        now = time.time()
        expires_at = None
        if expires_in_days:
            expires_at = now + (expires_in_days * 86400)  # Convert days to seconds
        
        api_key = cls(
            key_id=key_id,
            key_hash=key_hash,
            user_id=user_id,
            roles=roles,
            description=description,
            created_at=now,
            expires_at=expires_at,
            is_active=True
        )
        
        return api_key, key_value
    
    def is_expired(self) -> bool:
        """Check if the API key has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if the API key is valid (active and not expired)."""
        return self.is_active and not self.is_expired()
    
    def update_last_used(self):
        """Update the last used timestamp to the current time."""
        self.last_used = time.time()


class ApiKeyManager:
    """Manages API keys for authentication."""
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize the API key manager.
        
        Args:
            storage_path: Optional path to store API keys. If None, keys are only kept in memory.
        """
        self.api_keys: Dict[str, ApiKey] = {}  # key_id -> ApiKey
        self.key_hash_to_id: Dict[str, str] = {}  # key_hash -> key_id for lookups
        self.storage_path = storage_path
        
        # Load keys from storage if available
        if storage_path:
            self._load_keys()
    
    def _load_keys(self):
        """Load API keys from storage."""
        import os
        if not self.storage_path or not os.path.exists(self.storage_path):
            return
        
        try:
            with open(self.storage_path, 'r') as f:
                keys_data = json.load(f)
                
            for key_data in keys_data:
                api_key = ApiKey(**key_data)
                self.api_keys[api_key.key_id] = api_key
                self.key_hash_to_id[api_key.key_hash] = api_key.key_id
                
            logger.info(f"Loaded {len(self.api_keys)} API keys from storage")
        except Exception as e:
            logger.error(f"Error loading API keys: {e}")
    
    def _save_keys(self):
        """Save API keys to storage."""
        if not self.storage_path:
            return
        
        try:
            # Convert API keys to dictionaries
            keys_data = [vars(key) for key in self.api_keys.values()]
            
            with open(self.storage_path, 'w') as f:
                json.dump(keys_data, f, indent=2)
                
            logger.info(f"Saved {len(self.api_keys)} API keys to storage")
        except Exception as e:
            logger.error(f"Error saving API keys: {e}")
    
    def create_api_key(self, user_id: str, roles: List[str], description: str, expires_in_days: Optional[int] = None) -> Tuple[ApiKey, str]:
        """
        Create a new API key.
        
        Args:
            user_id: ID of the user the key belongs to
            roles: List of roles to assign to the key
            description: Human-readable description of the key's purpose
            expires_in_days: Optional expiration in days from creation
        
        Returns:
            Tuple[ApiKey, str]: The API key object and the raw key value
        """
        api_key, key_value = ApiKey.create(user_id, roles, description, expires_in_days)
        
        # Store the key
        self.api_keys[api_key.key_id] = api_key
        self.key_hash_to_id[api_key.key_hash] = api_key.key_id
        
        # Save to storage if configured
        if self.storage_path:
            self._save_keys()
        
        return api_key, key_value
    
    def validate_api_key(self, key_value: str) -> Optional[ApiKey]:
        """
        Validate an API key and return the associated ApiKey object if valid.
        
        Args:
            key_value: The API key to validate
        
        Returns:
            Optional[ApiKey]: The API key object if valid, None otherwise
        """
        import hashlib
        
        # Hash the key for lookup
        key_hash = hashlib.sha256(key_value.encode()).hexdigest()
        
        # Look up the key ID
        key_id = self.key_hash_to_id.get(key_hash)
        if not key_id:
            return None
        
        # Get the API key object
        api_key = self.api_keys.get(key_id)
        if not api_key:
            return None
        
        # Check if the key is valid
        if not api_key.is_valid():
            return None
        
        # Update last used timestamp
        api_key.update_last_used()
        if self.storage_path:
            self._save_keys()
        
        return api_key
    
    def revoke_api_key(self, key_id: str) -> bool:
        """
        Revoke an API key.
        
        Args:
            key_id: ID of the API key to revoke
        
        Returns:
            bool: True if the key was found and revoked, False otherwise
        """
        if key_id not in self.api_keys:
            return False
        
        # Set the key to inactive
        self.api_keys[key_id].is_active = False
        
        # Save to storage if configured
        if self.storage_path:
            self._save_keys()
        
        return True
    
    def get_user_api_keys(self, user_id: str) -> List[ApiKey]:
        """
        Get all API keys for a user.
        
        Args:
            user_id: ID of the user
        
        Returns:
            List[ApiKey]: List of API keys for the user
        """
        return [key for key in self.api_keys.values() if key.user_id == user_id]
    
    def cleanup_expired_keys(self) -> int:
        """
        Clean up expired API keys.
        
        Returns:
            int: Number of keys removed
        """
        expired_count = 0
        for key_id in list(self.api_keys.keys()):
            api_key = self.api_keys[key_id]
            if api_key.is_expired():
                # Remove the key
                del self.api_keys[key_id]
                del self.key_hash_to_id[api_key.key_hash]
                expired_count += 1
        
        # Save to storage if configured and keys were removed
        if expired_count > 0 and self.storage_path:
            self._save_keys()
        
        return expired_count


# -------------------------------------------------------------------------
# User Authentication
# -------------------------------------------------------------------------

class AuthenticationMethod(Enum):
    """Supported authentication methods."""
    API_KEY = "api_key"
    JWT = "jwt"
    BASIC = "basic"
    OAUTH = "oauth"
    SESSION = "session"


@dataclass
class User:
    """Represents a user in the system."""
    user_id: str
    username: str
    roles: List[str]
    is_active: bool = True
    display_name: Optional[str] = None
    email: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    last_login: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# -------------------------------------------------------------------------
# Request Authentication and Authorization
# -------------------------------------------------------------------------

class AuthorizationResult:
    """Represents the result of an authorization check."""
    
    def __init__(self, is_authorized: bool, user_id: Optional[str] = None, 
                 roles: Optional[List[str]] = None, reason: Optional[str] = None):
        self.is_authorized = is_authorized
        self.user_id = user_id
        self.roles = roles or []
        self.reason = reason
    
    def __bool__(self):
        return self.is_authorized


class RequestAuthenticator:
    """
    Authenticates requests and extracts user information.
    
    This class handles different authentication methods and provides
    a unified interface for checking permissions.
    """
    
    def __init__(self, role_manager: RoleManager, api_key_manager: Optional[ApiKeyManager] = None):
        """
        Initialize the authenticator.
        
        Args:
            role_manager: Role manager to check permissions
            api_key_manager: API key manager for API key authentication
        """
        self.role_manager = role_manager
        self.api_key_manager = api_key_manager
        self.audit_logger = logging.getLogger("auth_audit")
        
        # Set up audit logger with separate handler if not already configured
        if not self.audit_logger.handlers:
            handler = logging.FileHandler("auth_audit.log")
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.audit_logger.addHandler(handler)
            self.audit_logger.setLevel(logging.INFO)
    
    def authenticate_request(self, request: Any) -> AuthorizationResult:
        """
        Authenticate a request and extract user information.
        
        This method tries different authentication methods based on available
        headers and returns the result of authentication.
        
        Args:
            request: The request object, expected to have headers
        
        Returns:
            AuthorizationResult: Result of authentication
        """
        if not hasattr(request, 'headers'):
            return AuthorizationResult(False, reason="Request has no headers")
        
        # Try API key authentication
        api_key = request.headers.get("X-API-Key")
        if api_key and self.api_key_manager:
            api_key_obj = self.api_key_manager.validate_api_key(api_key)
            if api_key_obj:
                # Log successful API key authentication
                self.audit_logger.info(
                    f"API key authentication succeeded for user {api_key_obj.user_id}"
                )
                return AuthorizationResult(
                    True, 
                    user_id=api_key_obj.user_id, 
                    roles=api_key_obj.roles
                )
        
        # Try JWT authentication (just framework, actual implementation would be more complex)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            # In a real implementation, we would validate the JWT token here
            # For now, we just assume a successful authentication with default role
            self.audit_logger.info("JWT authentication used (mocked)")
            return AuthorizationResult(True, user_id="mock_user", roles=["user"])
        
        # Try basic authentication
        if auth_header.startswith("Basic "):
            # In a real implementation, we would decode and validate credentials
            # For now, we just assume a successful authentication with default role
            self.audit_logger.info("Basic authentication used (mocked)")
            return AuthorizationResult(True, user_id="mock_user", roles=["user"])
        
        # Try custom header for testing
        role = request.headers.get("X-User-Role")
        if role:
            if role in self.role_manager.roles:
                self.audit_logger.info(f"Custom header authentication with role {role}")
                return AuthorizationResult(True, user_id="test_user", roles=[role])
        
        # No authentication provided, use guest role
        self.audit_logger.info("No authentication provided, using guest role")
        return AuthorizationResult(True, roles=["guest"])
    
    def authorize(self, request: Any, required_permission: Union[Permission, str], 
                  resource_type: ResourceType = ResourceType.GLOBAL) -> AuthorizationResult:
        """
        Authorize a request for a specific permission.
        
        Args:
            request: The request object
            required_permission: The required permission or permission name
            resource_type: The resource type for the permission
        
        Returns:
            AuthorizationResult: Result of authorization
        """
        # Authenticate the request
        auth_result = self.authenticate_request(request)
        if not auth_result:
            return auth_result
        
        # Convert string permission to Permission object if needed
        if isinstance(required_permission, str):
            if required_permission in GLOBAL_PERMISSIONS:
                permission = GLOBAL_PERMISSIONS[required_permission]
            else:
                # Assume it's a backend-specific permission format: "backend:action"
                parts = required_permission.split(":")
                if len(parts) == 2:
                    backend, action = parts
                    try:
                        permission = get_backend_permission(
                            backend, Action(action)
                        )
                    except (ValueError, KeyError):
                        return AuthorizationResult(
                            False, 
                            user_id=auth_result.user_id,
                            roles=auth_result.roles,
                            reason=f"Invalid permission string: {required_permission}"
                        )
                else:
                    return AuthorizationResult(
                        False, 
                        user_id=auth_result.user_id,
                        roles=auth_result.roles,
                        reason=f"Invalid permission string: {required_permission}"
                    )
        else:
            permission = required_permission
        
        # Check if user has the required permission
        has_permission = self.role_manager.user_has_permission(auth_result.roles, permission)
        
        if has_permission:
            self.audit_logger.info(
                f"Authorization succeeded for user {auth_result.user_id or 'anonymous'} "
                f"with roles {auth_result.roles} for permission {permission.name}"
            )
            return auth_result
        else:
            self.audit_logger.warning(
                f"Authorization failed for user {auth_result.user_id or 'anonymous'} "
                f"with roles {auth_result.roles} for permission {permission.name}"
            )
            return AuthorizationResult(
                False, 
                user_id=auth_result.user_id,
                roles=auth_result.roles,
                reason=f"Insufficient permissions: {permission.name}"
            )


# -------------------------------------------------------------------------
# Decorators for Permission Checking
# -------------------------------------------------------------------------

def require_permission(permission: Union[str, Permission], 
                       resource_type: ResourceType = ResourceType.GLOBAL):
    """
    Decorator to require a permission for a function.
    
    This decorator can be used to protect functions that handle requests.
    It expects the first argument of the function to be the request object.
    
    Args:
        permission: The required permission string or Permission object
        resource_type: The resource type for the permission
    
    Returns:
        Callable: Decorator function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, request, *args, **kwargs):
            # Check if the handler class has an authenticator
            if not hasattr(self, 'authenticator') or not isinstance(self.authenticator, RequestAuthenticator):
                logger.error("Handler class does not have a RequestAuthenticator instance")
                raise RuntimeError("Authorization system not properly configured")
            
            # Authorize the request
            auth_result = self.authenticator.authorize(request, permission, resource_type)
            if not auth_result:
                # Handle unauthorized access
                # In a web framework, you might return a proper HTTP response here
                error_message = f"Access denied: {auth_result.reason or 'Insufficient permissions'}"
                logger.warning(error_message)
                return {"error": "access_denied", "message": error_message}
            
            # Add auth info to request for the handler to use
            setattr(request, "auth_user_id", auth_result.user_id)
            setattr(request, "auth_roles", auth_result.roles)
            
            # Call the original function
            return func(self, request, *args, **kwargs)
        
        return wrapper
    
    return decorator


# -------------------------------------------------------------------------
# Main RBAC Service Class
# -------------------------------------------------------------------------

class RBACService:
    """
    Main service class for Role-Based Access Control.
    
    This class combines the various components of the RBAC system and
    provides a unified interface for authentication and authorization.
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize the RBAC service.
        
        Args:
            storage_path: Optional path to store API keys
        """
        self.role_manager = RoleManager()
        self.api_key_manager = ApiKeyManager(storage_path)
        self.authenticator = RequestAuthenticator(self.role_manager, self.api_key_manager)
        self.backend_auth = BackendAuthorization(self.role_manager)
    
    def authenticate_request(self, request: Any) -> AuthorizationResult:
        """
        Authenticate a request.
        
        Args:
            request: The request object
        
        Returns:
            AuthorizationResult: Result of authentication
        """
        return self.authenticator.authenticate_request(request)
    
    def authorize(self, request: Any, required_permission: Union[str, Permission],
                 resource_type: ResourceType = ResourceType.GLOBAL) -> AuthorizationResult:
        """
        Authorize a request for a specific permission.
        
        Args:
            request: The request object
            required_permission: The required permission or permission name
            resource_type: The resource type for the permission
        
        Returns:
            AuthorizationResult: Result of authorization
        """
        return self.authenticator.authorize(request, required_permission, resource_type)
    
    def can_access_backend(self, user_roles: List[str], backend: str, action: Action) -> bool:
        """
        Check if a user can access a specific backend.
        
        Args:
            user_roles: List of role names the user has
            backend: Backend name (e.g., "IPFS", "S3")
            action: The action to perform (e.g., READ, WRITE)
        
        Returns:
            bool: True if access is allowed, False otherwise
        """
        return self.backend_auth.can_access_backend(user_roles, backend, action)
    
    def get_accessible_backends(self, user_roles: List[str], action: Action) -> List[str]:
        """
        Get a list of backends a user can access for a specific action.
        
        Args:
            user_roles: List of role names the user has
            action: The action to check for (e.g., READ, WRITE)
        
        Returns:
            List[str]: List of backend names the user can access
        """
        return self.backend_auth.get_accessible_backends(user_roles, action)
    
    def create_api_key(self, user_id: str, roles: List[str], description: str,
                      expires_in_days: Optional[int] = None) -> Tuple[ApiKey, str]:
        """
        Create a new API key.
        
        Args:
            user_id: ID of the user the key belongs to
            roles: List of roles to assign to the key
            description: Human-readable description of the key's purpose
            expires_in_days: Optional expiration in days from creation
        
        Returns:
            Tuple[ApiKey, str]: The API key object and the raw key value
        """
        return self.api_key_manager.create_api_key(user_id, roles, description, expires_in_days)
    
    def validate_api_key(self, key_value: str) -> Optional[ApiKey]:
        """
        Validate an API key.
        
        Args:
            key_value: The API key to validate
        
        Returns:
            Optional[ApiKey]: The API key object if valid, None otherwise
        """
        return self.api_key_manager.validate_api_key(key_value)
    
    def revoke_api_key(self, key_id: str) -> bool:
        """
        Revoke an API key.
        
        Args:
            key_id: ID of the API key to revoke
        
        Returns:
            bool: True if the key was found and revoked, False otherwise
        """
        return self.api_key_manager.revoke_api_key(key_id)
    
    def get_user_api_keys(self, user_id: str) -> List[ApiKey]:
        """
        Get all API keys for a user.
        
        Args:
            user_id: ID of the user
        
        Returns:
            List[ApiKey]: List of API keys for the user
        """
        return self.api_key_manager.get_user_api_keys(user_id)
    
    def create_role(self, name: str, description: str, 
                   parent_roles: Optional[List[str]] = None) -> Role:
        """
        Create a new role.
        
        Args:
            name: Role name
            description: Role description
            parent_roles: Optional list of parent roles
        
        Returns:
            Role: The created role
        """
        return self.role_manager.create_role(name, description, parent_roles)
    
    def get_role(self, role_name: str) -> Optional[Role]:
        """
        Get a role by name.
        
        Args:
            role_name: Name of the role
        
        Returns:
            Optional[Role]: The role if found, None otherwise
        """
        return self.role_manager.get_role(role_name)
    
    def add_permission_to_role(self, role_name: str, permission: Permission) -> bool:
        """
        Add a permission to a role.
        
        Args:
            role_name: Name of the role
            permission: Permission to add
        
        Returns:
            bool: True if successful, False otherwise
        """
        return self.role_manager.add_permission_to_role(role_name, permission)


# Create a global instance for convenience
rbac_service = RBACService()


# -------------------------------------------------------------------------
# Example Usage
# -------------------------------------------------------------------------

def example_usage():
    """Example usage of the RBAC system."""
    # Create a mock request with headers
    class MockRequest:
        def __init__(self, headers):
            self.headers = headers
    
    # Initialize the RBAC service
    rbac = RBACService()
    
    # Create a new API key for a user
    api_key_obj, key_value = rbac.create_api_key(
        user_id="user123",
        roles=["user"],
        description="Test API key",
        expires_in_days=30
    )
    print(f"Created API key: {key_value}")
    
    # Test authentication with the API key
    req_with_key = MockRequest({"X-API-Key": key_value})
    auth_result = rbac.authenticate_request(req_with_key)
    print(f"Authentication result with API key: {auth_result.is_authorized}")
    print(f"User ID: {auth_result.user_id}")
    print(f"Roles: {auth_result.roles}")
    
    # Test authorization for a permission
    auth_result = rbac.authorize(req_with_key, "read")
    print(f"Authorization result for 'read': {auth_result.is_authorized}")
    
    # Test backend access
    user_roles = ["user"]
    can_access_ipfs = rbac.can_access_backend(user_roles, "IPFS", Action.READ)
    print(f"User can access IPFS for READ: {can_access_ipfs}")
    
    # Get accessible backends
    accessible = rbac.get_accessible_backends(user_roles, Action.READ)
    print(f"Accessible backends for READ: {accessible}")
    
    # Test with different roles
    req_admin = MockRequest({"X-User-Role": "admin"})
    auth_result = rbac.authorize(req_admin, "admin")
    print(f"Admin authorization for 'admin': {auth_result.is_authorized}")
    
    # Test with insufficient permissions
    req_guest = MockRequest({})  # No auth headers, defaults to guest
    auth_result = rbac.authorize(req_guest, "write")
    print(f"Guest authorization for 'write': {auth_result.is_authorized}")
    print(f"Reason: {auth_result.reason}")


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Run the example
    example_usage()