"""
Role-Based Access Control (RBAC) Module for MCP Server

This module implements comprehensive role-based access control for the MCP server:
- Role and permission management
- Resource-based access controls
- Backend-specific authorization
- Policy enforcement

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.
"""

import os
import time
import json
import logging
import uuid
import hashlib
from enum import Enum
from typing import Dict, List, Set, Optional, Union, Any, Callable, Tuple
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_rbac")

class PermissionEffect(Enum):
    """Effect of a permission evaluation."""
    ALLOW = "allow"
    DENY = "deny"
    NEUTRAL = "neutral"

class ResourceType(Enum):
    """Resource types that can be protected with access controls."""
    STORAGE = "storage"                # Storage operations
    API = "api"                        # API endpoints
    BACKEND = "backend"                # Storage backends
    SYSTEM = "system"                  # System operations
    CONFIG = "config"                  # Configuration management
    USER = "user"                      # User management
    ROLE = "role"                      # Role management
    PERMISSION = "permission"          # Permission management
    MONITORING = "monitoring"          # Monitoring capabilities
    ANALYTICS = "analytics"            # Analytics capabilities

class ActionType(Enum):
    """Action types that can be performed on resources."""
    CREATE = "create"                  # Create a resource
    READ = "read"                      # Read/view a resource
    UPDATE = "update"                  # Update/modify a resource
    DELETE = "delete"                  # Delete a resource
    LIST = "list"                      # List resources
    MANAGE = "manage"                  # Manage resource settings
    EXECUTE = "execute"                # Execute an operation
    ALL = "*"                          # All actions

class Permission:
    """Permission definition for role-based access control."""
    
    def __init__(
        self,
        name: str,
        resource_type: Union[ResourceType, str],
        actions: Set[Union[ActionType, str]],
        description: Optional[str] = None,
        resource_id: Optional[str] = None,
        conditions: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize permission.
        
        Args:
            name: Permission name
            resource_type: Resource type
            actions: Allowed actions
            description: Optional description
            resource_id: Optional specific resource ID (None for all)
            conditions: Optional conditions for permission
        """
        self.id = str(uuid.uuid4())
        self.name = name
        
        # Convert resource_type to enum if string
        if isinstance(resource_type, str):
            try:
                self.resource_type = ResourceType(resource_type)
            except ValueError:
                raise ValueError(f"Invalid resource type: {resource_type}")
        else:
            self.resource_type = resource_type
        
        # Convert actions to enum set
        self.actions = set()
        for action in actions:
            if isinstance(action, str):
                try:
                    self.actions.add(ActionType(action))
                except ValueError:
                    raise ValueError(f"Invalid action type: {action}")
            else:
                self.actions.add(action)
        
        self.description = description or ""
        self.resource_id = resource_id
        self.conditions = conditions or {}
        
        # Timestamp for creation and update tracking
        self.created_at = time.time()
        self.updated_at = self.created_at
    
    def matches(self, resource_type: Union[ResourceType, str], 
               action: Union[ActionType, str], 
               resource_id: Optional[str] = None,
               context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check if this permission matches a given access request.
        
        Args:
            resource_type: Resource type to check
            action: Action to check
            resource_id: Optional specific resource ID
            context: Optional request context for condition evaluation
            
        Returns:
            True if permission matches
        """
        # Convert resource_type to enum if string
        if isinstance(resource_type, str):
            try:
                resource_type = ResourceType(resource_type)
            except ValueError:
                return False
        
        # Convert action to enum if string
        if isinstance(action, str):
            try:
                action = ActionType(action)
            except ValueError:
                return False
        
        # Check resource type
        if self.resource_type != resource_type:
            return False
        
        # Check resource ID
        if self.resource_id is not None and resource_id is not None and self.resource_id != resource_id:
            return False
        
        # Check actions
        if ActionType.ALL not in self.actions and action not in self.actions:
            return False
        
        # Check conditions
        if self.conditions and context:
            if not self._evaluate_conditions(self.conditions, context):
                return False
        
        return True
    
    def _evaluate_conditions(self, conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        Evaluate conditions against context.
        
        Args:
            conditions: Condition definitions
            context: Request context
            
        Returns:
            True if conditions are satisfied
        """
        for key, condition in conditions.items():
            # Skip if key doesn't exist in context
            if key not in context:
                return False
            
            context_value = context[key]
            
            # Exact value match
            if isinstance(condition, (str, int, float, bool)):
                if context_value != condition:
                    return False
            
            # List contains
            elif isinstance(condition, list):
                if not isinstance(context_value, list):
                    # Single value - check if it's in condition list
                    if context_value not in condition:
                        return False
                else:
                    # List value - check if any value is in condition list
                    if not any(v in condition for v in context_value):
                        return False
            
            # Dictionary with operators
            elif isinstance(condition, dict):
                for op, value in condition.items():
                    if op == "eq" and context_value != value:
                        return False
                    elif op == "ne" and context_value == value:
                        return False
                    elif op == "gt" and not (isinstance(context_value, (int, float)) and context_value > value):
                        return False
                    elif op == "lt" and not (isinstance(context_value, (int, float)) and context_value < value):
                        return False
                    elif op == "gte" and not (isinstance(context_value, (int, float)) and context_value >= value):
                        return False
                    elif op == "lte" and not (isinstance(context_value, (int, float)) and context_value <= value):
                        return False
                    elif op == "contains" and not (isinstance(context_value, str) and value in context_value):
                        return False
                    elif op == "in" and context_value not in value:
                        return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary representation.
        
        Returns:
            Dictionary with permission fields
        """
        return {
            "id": self.id,
            "name": self.name,
            "resource_type": self.resource_type.value,
            "actions": [action.value for action in self.actions],
            "description": self.description,
            "resource_id": self.resource_id,
            "conditions": self.conditions,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Permission':
        """
        Create from dictionary representation.
        
        Args:
            data: Dictionary with permission fields
            
        Returns:
            Permission instance
        """
        # Create instance
        permission = cls(
            name=data["name"],
            resource_type=data["resource_type"],
            actions=set(data["actions"]),
            description=data.get("description"),
            resource_id=data.get("resource_id"),
            conditions=data.get("conditions")
        )
        
        # Set fields that aren't in constructor
        permission.id = data.get("id", permission.id)
        permission.created_at = data.get("created_at", permission.created_at)
        permission.updated_at = data.get("updated_at", permission.updated_at)
        
        return permission

class Role:
    """Role definition for role-based access control."""
    
    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        permissions: Optional[List[Union[str, Permission]]] = None,
        parent_roles: Optional[List[str]] = None
    ):
        """
        Initialize role.
        
        Args:
            name: Role name
            description: Optional description
            permissions: Optional list of permissions (IDs or objects)
            parent_roles: Optional parent role IDs for inheritance
        """
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description or ""
        
        # Store permission IDs
        self.permissions = set()
        if permissions:
            for perm in permissions:
                if isinstance(perm, Permission):
                    self.permissions.add(perm.id)
                else:
                    self.permissions.add(perm)
        
        self.parent_roles = set(parent_roles) if parent_roles else set()
        
        # Timestamp for creation and update tracking
        self.created_at = time.time()
        self.updated_at = self.created_at
    
    def add_permission(self, permission: Union[str, Permission]) -> None:
        """
        Add a permission to this role.
        
        Args:
            permission: Permission ID or object
        """
        if isinstance(permission, Permission):
            self.permissions.add(permission.id)
        else:
            self.permissions.add(permission)
        
        self.updated_at = time.time()
    
    def remove_permission(self, permission_id: str) -> None:
        """
        Remove a permission from this role.
        
        Args:
            permission_id: Permission ID
        """
        if permission_id in self.permissions:
            self.permissions.remove(permission_id)
            self.updated_at = time.time()
    
    def add_parent_role(self, role_id: str) -> None:
        """
        Add a parent role for inheritance.
        
        Args:
            role_id: Parent role ID
        """
        self.parent_roles.add(role_id)
        self.updated_at = time.time()
    
    def remove_parent_role(self, role_id: str) -> None:
        """
        Remove a parent role.
        
        Args:
            role_id: Parent role ID
        """
        if role_id in self.parent_roles:
            self.parent_roles.remove(role_id)
            self.updated_at = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary representation.
        
        Returns:
            Dictionary with role fields
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "permissions": list(self.permissions),
            "parent_roles": list(self.parent_roles),
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Role':
        """
        Create from dictionary representation.
        
        Args:
            data: Dictionary with role fields
            
        Returns:
            Role instance
        """
        # Create instance
        role = cls(
            name=data["name"],
            description=data.get("description"),
            permissions=data.get("permissions"),
            parent_roles=data.get("parent_roles")
        )
        
        # Set fields that aren't in constructor
        role.id = data.get("id", role.id)
        role.created_at = data.get("created_at", role.created_at)
        role.updated_at = data.get("updated_at", role.updated_at)
        
        return role

class RBACStore:
    """Storage backend for RBAC data."""
    
    def __init__(self, store_path: str):
        """
        Initialize RBAC data store.
        
        Args:
            store_path: Path to store RBAC data
        """
        self.store_path = store_path
        
        # Create store directories
        self.permissions_dir = os.path.join(store_path, "permissions")
        self.roles_dir = os.path.join(store_path, "roles")
        
        os.makedirs(self.permissions_dir, exist_ok=True)
        os.makedirs(self.roles_dir, exist_ok=True)
        
        # Caches for in-memory access
        self._permission_cache = {}  # id -> Permission
        self._role_cache = {}        # id -> Role
        self._role_name_cache = {}   # name -> id
    
    def save_permission(self, permission: Permission) -> bool:
        """
        Save a permission to the store.
        
        Args:
            permission: Permission to save
            
        Returns:
            Success flag
        """
        try:
            # Convert to dict
            perm_dict = permission.to_dict()
            
            # Save to file
            file_path = os.path.join(self.permissions_dir, f"{permission.id}.json")
            with open(file_path, 'w') as f:
                json.dump(perm_dict, f, indent=2)
            
            # Update cache
            self._permission_cache[permission.id] = permission
            
            return True
        except Exception as e:
            logger.error(f"Error saving permission {permission.id}: {e}")
            return False
    
    def get_permission(self, permission_id: str) -> Optional[Permission]:
        """
        Get a permission by ID.
        
        Args:
            permission_id: Permission ID
            
        Returns:
            Permission or None if not found
        """
        # Check cache
        if permission_id in self._permission_cache:
            return self._permission_cache[permission_id]
        
        # Try to load from file
        try:
            file_path = os.path.join(self.permissions_dir, f"{permission_id}.json")
            if not os.path.exists(file_path):
                return None
            
            with open(file_path, 'r') as f:
                perm_dict = json.load(f)
            
            # Create permission
            permission = Permission.from_dict(perm_dict)
            
            # Update cache
            self._permission_cache[permission_id] = permission
            
            return permission
        except Exception as e:
            logger.error(f"Error loading permission {permission_id}: {e}")
            return None
    
    def list_permissions(self) -> List[Permission]:
        """
        List all permissions.
        
        Returns:
            List of all permissions
        """
        permissions = []
        
        # Get all permission files
        for filename in os.listdir(self.permissions_dir):
            if filename.endswith(".json"):
                permission_id = filename[:-5]  # Remove .json extension
                permission = self.get_permission(permission_id)
                if permission:
                    permissions.append(permission)
        
        return permissions
    
    def delete_permission(self, permission_id: str) -> bool:
        """
        Delete a permission.
        
        Args:
            permission_id: Permission ID
            
        Returns:
            Success flag
        """
        try:
            # Remove from cache
            if permission_id in self._permission_cache:
                del self._permission_cache[permission_id]
            
            # Remove file
            file_path = os.path.join(self.permissions_dir, f"{permission_id}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return True
        except Exception as e:
            logger.error(f"Error deleting permission {permission_id}: {e}")
            return False
    
    def save_role(self, role: Role) -> bool:
        """
        Save a role to the store.
        
        Args:
            role: Role to save
            
        Returns:
            Success flag
        """
        try:
            # Convert to dict
            role_dict = role.to_dict()
            
            # Save to file
            file_path = os.path.join(self.roles_dir, f"{role.id}.json")
            with open(file_path, 'w') as f:
                json.dump(role_dict, f, indent=2)
            
            # Update caches
            self._role_cache[role.id] = role
            self._role_name_cache[role.name] = role.id
            
            return True
        except Exception as e:
            logger.error(f"Error saving role {role.id}: {e}")
            return False
    
    def get_role(self, role_id: str) -> Optional[Role]:
        """
        Get a role by ID.
        
        Args:
            role_id: Role ID
            
        Returns:
            Role or None if not found
        """
        # Check cache
        if role_id in self._role_cache:
            return self._role_cache[role_id]
        
        # Try to load from file
        try:
            file_path = os.path.join(self.roles_dir, f"{role_id}.json")
            if not os.path.exists(file_path):
                return None
            
            with open(file_path, 'r') as f:
                role_dict = json.load(f)
            
            # Create role
            role = Role.from_dict(role_dict)
            
            # Update caches
            self._role_cache[role_id] = role
            self._role_name_cache[role.name] = role.id
            
            return role
        except Exception as e:
            logger.error(f"Error loading role {role_id}: {e}")
            return None
    
    def get_role_by_name(self, role_name: str) -> Optional[Role]:
        """
        Get a role by name.
        
        Args:
            role_name: Role name
            
        Returns:
            Role or None if not found
        """
        # Check name cache
        if role_name in self._role_name_cache:
            role_id = self._role_name_cache[role_name]
            return self.get_role(role_id)
        
        # Scan roles
        for role_id in self._find_role_ids():
            role = self.get_role(role_id)
            if role and role.name == role_name:
                self._role_name_cache[role_name] = role_id
                return role
        
        return None
    
    def list_roles(self) -> List[Role]:
        """
        List all roles.
        
        Returns:
            List of all roles
        """
        roles = []
        
        # Get all role files
        for role_id in self._find_role_ids():
            role = self.get_role(role_id)
            if role:
                roles.append(role)
        
        return roles
    
    def delete_role(self, role_id: str) -> bool:
        """
        Delete a role.
        
        Args:
            role_id: Role ID
            
        Returns:
            Success flag
        """
        try:
            # Get role first to remove from name cache
            role = self.get_role(role_id)
            if role:
                if role.name in self._role_name_cache:
                    del self._role_name_cache[role.name]
            
            # Remove from ID cache
            if role_id in self._role_cache:
                del self._role_cache[role_id]
            
            # Remove file
            file_path = os.path.join(self.roles_dir, f"{role_id}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return True
        except Exception as e:
            logger.error(f"Error deleting role {role_id}: {e}")
            return False
    
    def _find_role_ids(self) -> List[str]:
        """
        Find all role IDs.
        
        Returns:
            List of role IDs
        """
        roles = []
        
        # Get all role files
        for filename in os.listdir(self.roles_dir):
            if filename.endswith(".json"):
                role_id = filename[:-5]  # Remove .json extension
                roles.append(role_id)
        
        return roles

class RBACManager:
    """
    Role-Based Access Control Manager.
    
    This class manages permissions, roles, and access control policies.
    """
    
    def __init__(self, store_path: str):
        """
        Initialize RBAC manager.
        
        Args:
            store_path: Path to store RBAC data
        """
        self.store = RBACStore(store_path)
        
        # Initialize with default permissions and roles
        self._ensure_default_permissions()
        self._ensure_default_roles()
        
        logger.info("RBAC Manager initialized")
    
    def _ensure_default_permissions(self) -> None:
        """Create default permissions if they don't exist."""
        # System-wide permissions
        self._ensure_permission(
            name="system:admin",
            resource_type=ResourceType.SYSTEM,
            actions={ActionType.ALL},
            description="Full system administration"
        )
        
        # Storage permissions
        self._ensure_permission(
            name="storage:read",
            resource_type=ResourceType.STORAGE,
            actions={ActionType.READ},
            description="Read storage content"
        )
        self._ensure_permission(
            name="storage:write",
            resource_type=ResourceType.STORAGE,
            actions={ActionType.CREATE, ActionType.UPDATE},
            description="Write to storage"
        )
        self._ensure_permission(
            name="storage:delete",
            resource_type=ResourceType.STORAGE,
            actions={ActionType.DELETE},
            description="Delete storage content"
        )
        self._ensure_permission(
            name="storage:list",
            resource_type=ResourceType.STORAGE,
            actions={ActionType.LIST},
            description="List storage contents"
        )
        
        # Backend permissions
        self._ensure_permission(
            name="backend:manage",
            resource_type=ResourceType.BACKEND,
            actions={ActionType.MANAGE},
            description="Manage storage backends"
        )
        self._ensure_permission(
            name="backend:read",
            resource_type=ResourceType.BACKEND,
            actions={ActionType.READ},
            description="View backend information"
        )
        
        # API permissions
        self._ensure_permission(
            name="api:access",
            resource_type=ResourceType.API,
            actions={ActionType.EXECUTE},
            description="Access API endpoints"
        )
        
        # User management permissions
        self._ensure_permission(
            name="user:manage",
            resource_type=ResourceType.USER,
            actions={ActionType.CREATE, ActionType.READ, ActionType.UPDATE, ActionType.DELETE, ActionType.LIST},
            description="Manage users"
        )
        self._ensure_permission(
            name="user:read",
            resource_type=ResourceType.USER,
            actions={ActionType.READ, ActionType.LIST},
            description="View user information"
        )
        
        # Role management permissions
        self._ensure_permission(
            name="role:manage",
            resource_type=ResourceType.ROLE,
            actions={ActionType.CREATE, ActionType.READ, ActionType.UPDATE, ActionType.DELETE, ActionType.LIST},
            description="Manage roles"
        )
        self._ensure_permission(
            name="role:read",
            resource_type=ResourceType.ROLE,
            actions={ActionType.READ, ActionType.LIST},
            description="View role information"
        )
        
        # Configuration permissions
        self._ensure_permission(
            name="config:manage",
            resource_type=ResourceType.CONFIG,
            actions={ActionType.CREATE, ActionType.READ, ActionType.UPDATE, ActionType.DELETE},
            description="Manage system configuration"
        )
        self._ensure_permission(
            name="config:read",
            resource_type=ResourceType.CONFIG,
            actions={ActionType.READ},
            description="View system configuration"
        )
        
        # Monitoring permissions
        self._ensure_permission(
            name="monitoring:view",
            resource_type=ResourceType.MONITORING,
            actions={ActionType.READ},
            description="View monitoring data"
        )
        self._ensure_permission(
            name="monitoring:manage",
            resource_type=ResourceType.MONITORING,
            actions={ActionType.MANAGE},
            description="Manage monitoring settings"
        )
        
        # Analytics permissions
        self._ensure_permission(
            name="analytics:view",
            resource_type=ResourceType.ANALYTICS,
            actions={ActionType.READ},
            description="View analytics data"
        )
        self._ensure_permission(
            name="analytics:manage",
            resource_type=ResourceType.ANALYTICS,
            actions={ActionType.MANAGE},
            description="Manage analytics settings"
        )
    
    def _ensure_permission(
        self,
        name: str,
        resource_type: ResourceType,
        actions: Set[ActionType],
        description: Optional[str] = None,
        resource_id: Optional[str] = None,
        conditions: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Create permission if it doesn't exist.
        
        Args:
            name: Permission name
            resource_type: Resource type
            actions: Allowed actions
            description: Optional description
            resource_id: Optional specific resource ID
            conditions: Optional conditions
        """
        # Check if permission exists by name
        existing_permissions = self.list_permissions()
        for perm in existing_permissions:
            if perm.name == name:
                return
        
        # Create permission
        permission = Permission(
            name=name,
            resource_type=resource_type,
            actions=actions,
            description=description,
            resource_id=resource_id,
            conditions=conditions
        )
        
        # Save permission
        self.store.save_permission(permission)
        logger.info(f"Created default permission: {name}")
    
    def _ensure_default_roles(self) -> None:
        """Create default roles if they don't exist."""
        # Get permission IDs by name
        permission_map = {}
        for perm in self.list_permissions():
            permission_map[perm.name] = perm.id
        
        # Admin role
        admin_permissions = [
            permission_map.get("system:admin")
        ]
        self._ensure_role(
            name="admin",
            description="Administrator with full access",
            permissions=[p for p in admin_permissions if p is not None]
        )
        
        # User role
        user_permissions = [
            permission_map.get("storage:read"),
            permission_map.get("storage:list"),
            permission_map.get("api:access"),
            permission_map.get("backend:read")
        ]
        self._ensure_role(
            name="user",
            description="Standard user",
            permissions=[p for p in user_permissions if p is not None]
        )
        
        # Backend manager role
        backend_permissions = [
            permission_map.get("backend:manage"),
            permission_map.get("backend:read"),
            permission_map.get("storage:read"),
            permission_map.get("storage:list"),
            permission_map.get("api:access")
        ]
        self._ensure_role(
            name="backend_manager",
            description="Backend manager",
            permissions=[p for p in backend_permissions if p is not None]
        )
        
        # Monitoring role
        monitoring_permissions = [
            permission_map.get("monitoring:view"),
            permission_map.get("analytics:view"),
            permission_map.get("api:access")
        ]
        self._ensure_role(
            name="monitoring",
            description="Monitoring access",
            permissions=[p for p in monitoring_permissions if p is not None]
        )
        
        # Read-only role
        readonly_permissions = [
            permission_map.get("storage:read"),
            permission_map.get("storage:list"),
            permission_map.get("backend:read"),
            permission_map.get("user:read"),
            permission_map.get("role:read"),
            permission_map.get("config:read"),
            permission_map.get("monitoring:view"),
            permission_map.get("analytics:view"),
            permission_map.get("api:access")
        ]
        self._ensure_role(
            name="readonly",
            description="Read-only access",
            permissions=[p for p in readonly_permissions if p is not None]
        )
    
    def _ensure_role(
        self,
        name: str,
        description: Optional[str] = None,
        permissions: Optional[List[str]] = None,
        parent_roles: Optional[List[str]] = None
    ) -> None:
        """
        Create role if it doesn't exist.
        
        Args:
            name: Role name
            description: Optional description
            permissions: Optional permission IDs
            parent_roles: Optional parent role IDs
        """
        # Check if role exists
        existing_role = self.get_role_by_name(name)
        if existing_role:
            return
        
        # Create role
        role = Role(
            name=name,
            description=description,
            permissions=permissions,
            parent_roles=parent_roles
        )
        
        # Save role
        self.store.save_role(role)
        logger.info(f"Created default role: {name}")
    
    def create_permission(
        self,
        name: str,
        resource_type: Union[ResourceType, str],
        actions: Set[Union[ActionType, str]],
        description: Optional[str] = None,
        resource_id: Optional[str] = None,
        conditions: Optional[Dict[str, Any]] = None
    ) -> Permission:
        """
        Create a new permission.
        
        Args:
            name: Permission name
            resource_type: Resource type
            actions: Allowed actions
            description: Optional description
            resource_id: Optional specific resource ID
            conditions: Optional conditions
            
        Returns:
            Created permission
        """
        # Create permission
        permission = Permission(
            name=name,
            resource_type=resource_type,
            actions=actions,
            description=description,
            resource_id=resource_id,
            conditions=conditions
        )
        
        # Save permission
        self.store.save_permission(permission)
        logger.info(f"Created permission: {name}")
        
        return permission
    
    def get_permission(self, permission_id: str) -> Optional[Permission]:
        """
        Get a permission by ID.
        
        Args:
            permission_id: Permission ID
            
        Returns:
            Permission or None if not found
        """
        return self.store.get_permission(permission_id)
    
    def get_permission_by_name(self, name: str) -> Optional[Permission]:
        """
        Get a permission by name.
        
        Args:
            name: Permission name
            
        Returns:
            Permission or None if not found
        """
        for permission in self.list_permissions():
            if permission.name == name:
                return permission
        return None
    
    def list_permissions(self) -> List[Permission]:
        """
        List all permissions.
        
        Returns:
            List of all permissions
        """
        return self.store.list_permissions()
    
    def update_permission(self, permission_id: str, **kwargs) -> Optional[Permission]:
        """
        Update a permission.
        
        Args:
            permission_id: Permission ID
            **kwargs: Fields to update
            
        Returns:
            Updated permission or None if not found
        """
        permission = self.get_permission(permission_id)
        if not permission:
            logger.warning(f"Permission {permission_id} not found")
            return None
        
        # Update fields
        for key, value in kwargs.items():
            if key == "name":
                permission.name = value
            elif key == "description":
                permission.description = value
            elif key == "resource_type":
                if isinstance(value, str):
                    permission.resource_type = ResourceType(value)
                else:
                    permission.resource_type = value
            elif key == "actions":
                # Convert string actions to enum
                actions = set()
                for action in value:
                    if isinstance(action, str):
                        actions.add(ActionType(action))
                    else:
                        actions.add(action)
                permission.actions = actions
            elif key == "resource_id":
                permission.resource_id = value
            elif key == "conditions":
                permission.conditions = value
        
        # Update timestamp
        permission.updated_at = time.time()
        
        # Save permission
        self.store.save_permission(permission)
        logger.info(f"Updated permission: {permission.name}")
        
        return permission
    
    def delete_permission(self, permission_id: str) -> bool:
        """
        Delete a permission.
        
        Args:
            permission_id: Permission ID
            
        Returns:
            Success flag
        """
        # First check if any roles reference this permission
        for role in self.list_roles():
            if permission_id in role.permissions:
                logger.warning(f"Cannot delete permission {permission_id}: referenced by role {role.name}")
                return False
        
        # Delete permission
        success = self.store.delete_permission(permission_id)
        if success:
            logger.info(f"Deleted permission {permission_id}")
        
        return success
    
    def create_role(
        self,
        name: str,
        description: Optional[str] = None,
        permissions: Optional[List[Union[str, Permission]]] = None,
        parent_roles: Optional[List[str]] = None
    ) -> Role:
        """
        Create a new role.
        
        Args:
            name: Role name
            description: Optional description
            permissions: Optional list of permissions (IDs or objects)
            parent_roles: Optional parent role IDs
            
        Returns:
            Created role
        """
        # Check if role with this name already exists
        existing_role = self.get_role_by_name(name)
        if existing_role:
            raise ValueError(f"Role with name {name} already exists")
        
        # Create role
        role = Role(
            name=name,
            description=description,
            permissions=permissions,
            parent_roles=parent_roles
        )
        
        # Save role
        self.store.save_role(role)
        logger.info(f"Created role: {name}")
        
        return role
    
    def get_role(self, role_id: str) -> Optional[Role]:
        """
        Get a role by ID.
        
        Args:
            role_id: Role ID
            
        Returns:
            Role or None if not found
        """
        return self.store.get_role(role_id)
    
    def get_role_by_name(self, name: str) -> Optional[Role]:
        """
        Get a role by name.
        
        Args:
            name: Role name
            
        Returns:
            Role or None if not found
        """
        return self.store.get_role_by_name(name)
    
    def list_roles(self) -> List[Role]:
        """
        List all roles.
        
        Returns:
            List of all roles
        """
        return self.store.list_roles()
    
    def update_role(self, role_id: str, **kwargs) -> Optional[Role]:
        """
        Update a role.
        
        Args:
            role_id: Role ID
            **kwargs: Fields to update
            
        Returns:
            Updated role or None if not found
        """
        role = self.get_role(role_id)
        if not role:
            logger.warning(f"Role {role_id} not found")
            return None
        
        # Update fields
        for key, value in kwargs.items():
            if key == "name":
                role.name = value
            elif key == "description":
                role.description = value
            elif key == "permissions":
                # Convert Permission objects to IDs
                permissions = set()
                for perm in value:
                    if isinstance(perm, Permission):
                        permissions.add(perm.id)
                    else:
                        permissions.add(perm)
                role.permissions = permissions
            elif key == "parent_roles":
                role.parent_roles = set(value)
        
        # Update timestamp
        role.updated_at = time.time()
        
        # Save role
        self.store.save_role(role)
        logger.info(f"Updated role: {role.name}")
        
        return role
    
    def delete_role(self, role_id: str) -> bool:
        """
        Delete a role.
        
        Args:
            role_id: Role ID
            
        Returns:
            Success flag
        """
        # First check if any roles reference this role as parent
        for role in self.list_roles():
            if role_id != role.id and role_id in role.parent_roles:
                logger.warning(f"Cannot delete role {role_id}: referenced as parent by role {role.name}")
                return False
        
        # Delete role
        success = self.store.delete_role(role_id)
        if success:
            logger.info(f"Deleted role {role_id}")
        
        return success
    
    def get_role_permissions(self, role_id: str, include_parents: bool = True) -> Set[str]:
        """
        Get all permission IDs granted to a role.
        
        Args:
            role_id: Role ID
            include_parents: Whether to include permissions from parent roles
            
        Returns:
            Set of permission IDs
        """
        role = self.get_role(role_id)
        if not role:
            return set()
        
        # Start with direct permissions
        permissions = set(role.permissions)
        
        # Add parent permissions if requested
        if include_parents and role.parent_roles:
            for parent_id in role.parent_roles:
                parent_permissions = self.get_role_permissions(parent_id, include_parents=True)
                permissions.update(parent_permissions)
        
        return permissions
    
    def has_permission(
        self,
        role_ids: List[str],
        resource_type: Union[ResourceType, str],
        action: Union[ActionType, str],
        resource_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if roles have permission for an action.
        
        Args:
            role_ids: List of role IDs
            resource_type: Resource type
            action: Action to check
            resource_id: Optional specific resource ID
            context: Optional request context for condition evaluation
            
        Returns:
            True if permission granted
        """
        # For each role, get all permissions (including from parents)
        all_permission_ids = set()
        for role_id in role_ids:
            role_permissions = self.get_role_permissions(role_id, include_parents=True)
            all_permission_ids.update(role_permissions)
        
        # Check each permission
        for permission_id in all_permission_ids:
            permission = self.get_permission(permission_id)
            if not permission:
                continue
            
            # Check if permission matches request
            if permission.matches(resource_type, action, resource_id, context):
                return True
        
        return False
    
    def get_backend_permissions(self, role_ids: List[str]) -> Dict[str, Set[str]]:
        """
        Get backend-specific permissions for roles.
        
        Args:
            role_ids: List of role IDs
            
        Returns:
            Dictionary mapping backend IDs to allowed actions
        """
        # Get all permissions for these roles
        all_permission_ids = set()
        for role_id in role_ids:
            role_permissions = self.get_role_permissions(role_id, include_parents=True)
            all_permission_ids.update(role_permissions)
        
        # Filter for backend permissions with specific resource IDs
        backend_permissions = defaultdict(set)
        for permission_id in all_permission_ids:
            permission = self.get_permission(permission_id)
            if not permission:
                continue
            
            if permission.resource_type == ResourceType.BACKEND and permission.resource_id:
                # Add actions for this backend
                backend_id = permission.resource_id
                for action in permission.actions:
                    backend_permissions[backend_id].add(action.value)
        
        return dict(backend_permissions)
    
    def user_has_permission(
        self,
        user_roles: List[str],
        permission_name: str,
        resource_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Higher-level method to check if a user has a specific permission.
        
        Args:
            user_roles: List of role names or IDs for the user
            permission_name: Name of the permission to check
            resource_id: Optional specific resource ID
            context: Optional request context for condition evaluation
            
        Returns:
            True if permission granted
        """
        # Get permission
        permission = self.get_permission_by_name(permission_name)
        if not permission:
            logger.warning(f"Permission {permission_name} not found")
            return False
        
        # Convert role names to IDs if needed
        role_ids = []
        for role in user_roles:
            if ":" in role or "-" in role:  # Assume UUID format
                role_ids.append(role)
            else:
                role_obj = self.get_role_by_name(role)
                if role_obj:
                    role_ids.append(role_obj.id)
        
        # Check permission
        return self.has_permission(
            role_ids=role_ids,
            resource_type=permission.resource_type,
            action=next(iter(permission.actions)) if permission.actions else ActionType.READ,
            resource_id=resource_id,
            context=context
        )


# Singleton instance
_instance = None

def get_instance(store_path=None):
    """Get or create a singleton instance of the RBAC manager."""
    global _instance
    if _instance is None:
        # Default store path
        if store_path is None:
            store_path = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "rbac")
        
        _instance = RBACManager(store_path)
    
    return _instance