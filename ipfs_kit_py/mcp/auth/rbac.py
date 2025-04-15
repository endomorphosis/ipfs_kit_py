"""
Role-Based Access Control (RBAC) for MCP Server.

This module provides a comprehensive role-based access control system for the MCP server,
enabling fine-grained permission management based on user roles.

Key features:
1. Role hierarchy with inheritance
2. Permission-based access control
3. Resource-specific access rules
4. Backend-specific permissions
5. Flexible policy enforcement

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
import json
import os
import time
import threading
from enum import Enum
from typing import Dict, List, Set, Optional, Any, Union, Tuple
from dataclasses import dataclass, field, asdict

# Configure logger
logger = logging.getLogger(__name__)

# Default roles and permissions
DEFAULT_ROLES_FILE = "config/rbac_roles.json"
DEFAULT_PERMISSIONS_FILE = "config/rbac_permissions.json"


class PermissionEffect(str, Enum):
    """Effect of a permission (allow or deny)."""
    ALLOW = "allow"
    DENY = "deny"


@dataclass
class Permission:
    """
    Permission definition for accessing resources.
    
    A Permission defines what actions can be performed on which resources.
    """
    # Required fields
    id: str
    name: str
    description: str
    resource_type: str  # e.g., "file", "storage", "backend", "admin"
    actions: List[str]  # e.g., ["read", "write", "delete", "list"]
    effect: PermissionEffect = PermissionEffect.ALLOW
    
    # Optional fields
    resource_prefix: Optional[str] = None  # Prefix for resource IDs this permission applies to
    backend_id: Optional[str] = None  # Specific backend this permission applies to
    conditions: Dict[str, Any] = field(default_factory=dict)  # Additional conditions


@dataclass
class Role:
    """
    Role definition combining multiple permissions.
    
    A Role is a collection of permissions that can be assigned to users.
    """
    # Required fields
    id: str
    name: str
    description: str
    
    # Optional fields
    permissions: List[str] = field(default_factory=list)  # List of permission IDs
    parent_roles: List[str] = field(default_factory=list)  # Parent roles (for inheritance)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessPolicy:
    """
    Access policy defining role assignments and additional rules.
    
    An AccessPolicy links users to roles and defines additional access rules.
    """
    # Required fields
    id: str
    name: str
    description: str
    
    # Core policy elements
    role_assignments: Dict[str, List[str]] = field(default_factory=dict)  # user_id -> role_ids
    group_role_assignments: Dict[str, List[str]] = field(default_factory=dict)  # group_id -> role_ids
    
    # Additional policy settings
    default_roles: List[str] = field(default_factory=list)  # Default roles for new users
    deny_by_default: bool = True  # Deny access by default if no matching permission
    
    # Policy metadata
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    version: int = 1


class RBACManager:
    """
    Role-Based Access Control Manager for MCP server.
    
    This class is responsible for managing roles, permissions, and access policies,
    and enforcing access control rules based on user roles and permissions.
    """
    
    def __init__(
        self,
        roles_file: Optional[str] = None,
        permissions_file: Optional[str] = None,
        policy_file: Optional[str] = None,
        auto_save: bool = True,
        refresh_interval: Optional[int] = 300,  # 5 minutes
    ):
        """
        Initialize the RBAC Manager.
        
        Args:
            roles_file: Path to JSON file with role definitions
            permissions_file: Path to JSON file with permission definitions
            policy_file: Path to JSON file with access policy
            auto_save: Whether to automatically save changes to files
            refresh_interval: Interval in seconds to refresh from files (None to disable)
        """
        self._roles_file = roles_file or DEFAULT_ROLES_FILE
        self._permissions_file = permissions_file or DEFAULT_PERMISSIONS_FILE
        self._policy_file = policy_file
        self._auto_save = auto_save
        
        # State storage
        self._roles: Dict[str, Role] = {}
        self._permissions: Dict[str, Permission] = {}
        self._access_policy: Optional[AccessPolicy] = None
        
        # Role hierarchy cache (role_id -> all permission IDs including inherited)
        self._role_permissions_cache: Dict[str, Set[str]] = {}
        
        # For thread safety
        self._lock = threading.RLock()
        
        # Load initial data
        self._load_permissions()
        self._load_roles()
        if policy_file:
            self._load_policy()
        else:
            # Create default policy if none exists
            self._access_policy = AccessPolicy(
                id="default",
                name="Default Policy",
                description="Default access policy"
            )
        
        # Rebuild role permissions cache
        self._rebuild_role_cache()
        
        # Set up background refresh if needed
        self._refresh_interval = refresh_interval
        self._shutdown_event = threading.Event()
        
        if refresh_interval:
            self._refresh_thread = threading.Thread(
                target=self._refresh_background,
                daemon=True,
                name="rbac-refresh"
            )
            self._refresh_thread.start()
            logger.debug(f"Started RBAC refresh thread (interval: {refresh_interval}s)")
    
    def _load_roles(self) -> bool:
        """
        Load roles from file.
        
        Returns:
            True if roles were loaded successfully, False otherwise
        """
        if not os.path.exists(self._roles_file):
            logger.warning(f"Roles file not found: {self._roles_file}")
            return False
        
        try:
            with open(self._roles_file, 'r') as f:
                roles_data = json.load(f)
            
            # Reset roles dictionary
            self._roles = {}
            
            # Parse roles
            for role_data in roles_data:
                role = Role(**role_data)
                self._roles[role.id] = role
            
            logger.info(f"Loaded {len(self._roles)} roles from {self._roles_file}")
            return True
        except Exception as e:
            logger.error(f"Error loading roles from {self._roles_file}: {e}")
            return False
    
    def _load_permissions(self) -> bool:
        """
        Load permissions from file.
        
        Returns:
            True if permissions were loaded successfully, False otherwise
        """
        if not os.path.exists(self._permissions_file):
            logger.warning(f"Permissions file not found: {self._permissions_file}")
            return False
        
        try:
            with open(self._permissions_file, 'r') as f:
                permissions_data = json.load(f)
            
            # Reset permissions dictionary
            self._permissions = {}
            
            # Parse permissions
            for perm_data in permissions_data:
                # Convert effect string to enum if needed
                if "effect" in perm_data and isinstance(perm_data["effect"], str):
                    perm_data["effect"] = PermissionEffect(perm_data["effect"])
                
                permission = Permission(**perm_data)
                self._permissions[permission.id] = permission
            
            logger.info(f"Loaded {len(self._permissions)} permissions from {self._permissions_file}")
            return True
        except Exception as e:
            logger.error(f"Error loading permissions from {self._permissions_file}: {e}")
            return False
    
    def _load_policy(self) -> bool:
        """
        Load access policy from file.
        
        Returns:
            True if policy was loaded successfully, False otherwise
        """
        if not self._policy_file or not os.path.exists(self._policy_file):
            logger.warning(f"Policy file not found: {self._policy_file}")
            return False
        
        try:
            with open(self._policy_file, 'r') as f:
                policy_data = json.load(f)
            
            self._access_policy = AccessPolicy(**policy_data)
            logger.info(f"Loaded access policy from {self._policy_file}")
            return True
        except Exception as e:
            logger.error(f"Error loading policy from {self._policy_file}: {e}")
            return False
    
    def _save_roles(self) -> bool:
        """
        Save roles to file.
        
        Returns:
            True if roles were saved successfully, False otherwise
        """
        if not self._auto_save:
            return False
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self._roles_file), exist_ok=True)
            
            # Convert roles to serializable format
            roles_data = [asdict(role) for role in self._roles.values()]
            
            with open(self._roles_file, 'w') as f:
                json.dump(roles_data, f, indent=2)
            
            logger.info(f"Saved {len(self._roles)} roles to {self._roles_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving roles to {self._roles_file}: {e}")
            return False
    
    def _save_permissions(self) -> bool:
        """
        Save permissions to file.
        
        Returns:
            True if permissions were saved successfully, False otherwise
        """
        if not self._auto_save:
            return False
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self._permissions_file), exist_ok=True)
            
            # Convert permissions to serializable format
            permissions_data = []
            for permission in self._permissions.values():
                perm_dict = asdict(permission)
                
                # Convert enum to string
                if "effect" in perm_dict and isinstance(perm_dict["effect"], PermissionEffect):
                    perm_dict["effect"] = perm_dict["effect"].value
                
                permissions_data.append(perm_dict)
            
            with open(self._permissions_file, 'w') as f:
                json.dump(permissions_data, f, indent=2)
            
            logger.info(f"Saved {len(self._permissions)} permissions to {self._permissions_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving permissions to {self._permissions_file}: {e}")
            return False
    
    def _save_policy(self) -> bool:
        """
        Save access policy to file.
        
        Returns:
            True if policy was saved successfully, False otherwise
        """
        if not self._auto_save or not self._policy_file or not self._access_policy:
            return False
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self._policy_file), exist_ok=True)
            
            with open(self._policy_file, 'w') as f:
                json.dump(asdict(self._access_policy), f, indent=2)
            
            logger.info(f"Saved access policy to {self._policy_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving policy to {self._policy_file}: {e}")
            return False
    
    def _refresh_background(self) -> None:
        """Background thread for refreshing RBAC data from files."""
        while not self._shutdown_event.is_set():
            # Wait for interval or shutdown
            if self._shutdown_event.wait(self._refresh_interval):
                break
            
            # Refresh data
            with self._lock:
                self._load_permissions()
                self._load_roles()
                if self._policy_file:
                    self._load_policy()
                
                # Rebuild cache
                self._rebuild_role_cache()
            
            logger.debug("Refreshed RBAC data from files")
    
    def _rebuild_role_cache(self) -> None:
        """Rebuild the role permissions cache."""
        # Reset cache
        self._role_permissions_cache = {}
        
        # Process each role
        for role_id in self._roles:
            self._get_role_permissions(role_id)
    
    def _get_role_permissions(self, role_id: str) -> Set[str]:
        """
        Get all permission IDs for a role, including those from parent roles.
        
        Args:
            role_id: ID of the role
            
        Returns:
            Set of permission IDs
        """
        # Check cache first
        if role_id in self._role_permissions_cache:
            return self._role_permissions_cache[role_id]
        
        # Get role
        role = self._roles.get(role_id)
        if not role:
            logger.warning(f"Role not found: {role_id}")
            return set()
        
        # Start with this role's permissions
        permissions = set(role.permissions)
        
        # Add permissions from parent roles
        for parent_id in role.parent_roles:
            # Skip if this would cause a circular reference
            if parent_id == role_id:
                logger.warning(f"Circular reference detected in role {role_id}")
                continue
            
            # Get parent permissions (recursive)
            parent_permissions = self._get_role_permissions(parent_id)
            permissions.update(parent_permissions)
        
        # Cache the result
        self._role_permissions_cache[role_id] = permissions
        
        return permissions
    
    def _get_user_permissions(self, user_id: str, group_ids: Optional[List[str]] = None) -> Set[str]:
        """
        Get all permission IDs for a user based on their roles.
        
        Args:
            user_id: ID of the user
            group_ids: Optional list of group IDs the user belongs to
            
        Returns:
            Set of permission IDs
        """
        if not self._access_policy:
            return set()
        
        # Get roles assigned to the user
        user_roles = set(self._access_policy.role_assignments.get(user_id, []))
        
        # Add default roles if user has no specific roles
        if not user_roles:
            user_roles.update(self._access_policy.default_roles)
        
        # Add roles from groups
        if group_ids:
            for group_id in group_ids:
                group_roles = self._access_policy.group_role_assignments.get(group_id, [])
                user_roles.update(group_roles)
        
        # Get permissions for all roles
        all_permissions = set()
        for role_id in user_roles:
            role_permissions = self._get_role_permissions(role_id)
            all_permissions.update(role_permissions)
        
        return all_permissions
    
    def check_permission(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        backend_id: Optional[str] = None,
        group_ids: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Check if a user has permission to perform an action on a resource.
        
        Args:
            user_id: ID of the user
            action: Action to perform (e.g., "read", "write", "delete")
            resource_type: Type of resource (e.g., "file", "storage", "backend")
            resource_id: Optional ID of the specific resource
            backend_id: Optional ID of the backend
            group_ids: Optional list of group IDs the user belongs to
            context: Optional additional context for condition evaluation
            
        Returns:
            True if the user has permission, False otherwise
        """
        if not self._access_policy:
            # No policy defined, use default behavior
            return not self._access_policy.deny_by_default
        
        with self._lock:
            # Get user permissions
            permission_ids = self._get_user_permissions(user_id, group_ids)
            
            # No permissions assigned
            if not permission_ids:
                # Use default behavior from policy
                return not self._access_policy.deny_by_default
            
            # Keep track of the most specific match
            best_match = None
            best_match_specificity = -1
            
            # Check each permission
            for perm_id in permission_ids:
                permission = self._permissions.get(perm_id)
                if not permission:
                    continue
                
                # Check resource type
                if permission.resource_type != resource_type:
                    continue
                
                # Check action
                if action not in permission.actions:
                    continue
                
                # Check backend (if applicable)
                if permission.backend_id and backend_id and permission.backend_id != backend_id:
                    continue
                
                # Check resource ID prefix (if applicable)
                if permission.resource_prefix and resource_id:
                    if not resource_id.startswith(permission.resource_prefix):
                        continue
                
                # Evaluate conditions (if applicable)
                if permission.conditions and not self._evaluate_conditions(permission.conditions, context):
                    continue
                
                # Calculate specificity score for this match
                specificity = 0
                if permission.backend_id:
                    specificity += 10
                if permission.resource_prefix:
                    specificity += len(permission.resource_prefix)
                if permission.conditions:
                    specificity += len(permission.conditions) * 5
                
                # Keep track of the most specific match
                if specificity > best_match_specificity:
                    best_match = permission
                    best_match_specificity = specificity
            
            # No matching permission found
            if best_match is None:
                # Use default behavior from policy
                return not self._access_policy.deny_by_default
            
            # Check effect of the most specific permission
            return best_match.effect == PermissionEffect.ALLOW
    
    def _evaluate_conditions(self, conditions: Dict[str, Any], context: Optional[Dict[str, Any]]) -> bool:
        """
        Evaluate conditions against context.
        
        This is a simplified condition evaluation. In a real implementation,
        this would be more sophisticated with support for complex conditions.
        
        Args:
            conditions: Dictionary of conditions to evaluate
            context: Context to evaluate against
            
        Returns:
            True if all conditions are met, False otherwise
        """
        if not context:
            return False
        
        for key, expected_value in conditions.items():
            if key not in context:
                return False
            
            actual_value = context[key]
            
            # Simple equality check for now
            if actual_value != expected_value:
                return False
        
        return True
    
    # Role management
    
    def create_role(self, role: Role) -> bool:
        """
        Create a new role.
        
        Args:
            role: Role to create
            
        Returns:
            True if the role was created successfully, False if it already exists
        """
        with self._lock:
            if role.id in self._roles:
                logger.warning(f"Role already exists: {role.id}")
                return False
            
            self._roles[role.id] = role
            self._role_permissions_cache[role.id] = set(role.permissions)
            
            # Save to file if auto-save is enabled
            self._save_roles()
            
            return True
    
    def update_role(self, role: Role) -> bool:
        """
        Update an existing role.
        
        Args:
            role: Role to update
            
        Returns:
            True if the role was updated successfully, False if it doesn't exist
        """
        with self._lock:
            if role.id not in self._roles:
                logger.warning(f"Role not found: {role.id}")
                return False
            
            self._roles[role.id] = role
            
            # Reset cache for this role and all roles that inherit from it
            del self._role_permissions_cache[role.id]
            for other_role in self._roles.values():
                if role.id in other_role.parent_roles:
                    if other_role.id in self._role_permissions_cache:
                        del self._role_permissions_cache[other_role.id]
            
            # Rebuild this role's cache entry
            self._get_role_permissions(role.id)
            
            # Save to file if auto-save is enabled
            self._save_roles()
            
            return True
    
    def delete_role(self, role_id: str) -> bool:
        """
        Delete a role.
        
        Args:
            role_id: ID of the role to delete
            
        Returns:
            True if the role was deleted successfully, False if it doesn't exist
        """
        with self._lock:
            if role_id not in self._roles:
                logger.warning(f"Role not found: {role_id}")
                return False
            
            # Check if other roles inherit from this one
            for other_role in self._roles.values():
                if role_id in other_role.parent_roles:
                    logger.warning(f"Cannot delete role {role_id}: other roles inherit from it")
                    return False
            
            # Remove from cache
            if role_id in self._role_permissions_cache:
                del self._role_permissions_cache[role_id]
            
            # Remove from roles dictionary
            del self._roles[role_id]
            
            # Save to file if auto-save is enabled
            self._save_roles()
            
            return True
    
    def add_permission_to_role(self, role_id: str, permission_id: str) -> bool:
        """
        Add a permission to a role.
        
        Args:
            role_id: ID of the role
            permission_id: ID of the permission to add
            
        Returns:
            True if the permission was added successfully, False otherwise
        """
        with self._lock:
            if role_id not in self._roles:
                logger.warning(f"Role not found: {role_id}")
                return False
            
            if permission_id not in self._permissions:
                logger.warning(f"Permission not found: {permission_id}")
                return False
            
            # Add permission if not already present
            if permission_id not in self._roles[role_id].permissions:
                self._roles[role_id].permissions.append(permission_id)
                
                # Reset cache for this role and all roles that inherit from it
                if role_id in self._role_permissions_cache:
                    del self._role_permissions_cache[role_id]
                
                # Rebuild this role's cache entry
                self._get_role_permissions(role_id)
                
                # Save to file if auto-save is enabled
                self._save_roles()
            
            return True
    
    def remove_permission_from_role(self, role_id: str, permission_id: str) -> bool:
        """
        Remove a permission from a role.
        
        Args:
            role_id: ID of the role
            permission_id: ID of the permission to remove
            
        Returns:
            True if the permission was removed successfully, False otherwise
        """
        with self._lock:
            if role_id not in self._roles:
                logger.warning(f"Role not found: {role_id}")
                return False
            
            # Remove permission if present
            if permission_id in self._roles[role_id].permissions:
                self._roles[role_id].permissions.remove(permission_id)
                
                # Reset cache for this role and all roles that inherit from it
                if role_id in self._role_permissions_cache:
                    del self._role_permissions_cache[role_id]
                
                # Rebuild this role's cache entry
                self._get_role_permissions(role_id)
                
                # Save to file if auto-save is enabled
                self._save_roles()
            
            return True
    
    # Permission management
    
    def create_permission(self, permission: Permission) -> bool:
        """
        Create a new permission.
        
        Args:
            permission: Permission to create
            
        Returns:
            True if the permission was created successfully, False if it already exists
        """
        with self._lock:
            if permission.id in self._permissions:
                logger.warning(f"Permission already exists: {permission.id}")
                return False
            
            self._permissions[permission.id] = permission
            
            # Reset cache for all roles (since this might affect permission resolution)
            self._role_permissions_cache = {}
            
            # Save to file if auto-save is enabled
            self._save_permissions()
            
            return True
    
    def update_permission(self, permission: Permission) -> bool:
        """
        Update an existing permission.
        
        Args:
            permission: Permission to update
            
        Returns:
            True if the permission was updated successfully, False if it doesn't exist
        """
        with self._lock:
            if permission.id not in self._permissions:
                logger.warning(f"Permission not found: {permission.id}")
                return False
            
            self._permissions[permission.id] = permission
            
            # Reset cache for all roles (since this might affect permission resolution)
            self._role_permissions_cache = {}
            
            # Save to file if auto-save is enabled
            self._save_permissions()
            
            return True
    
    def delete_permission(self, permission_id: str) -> bool:
        """
        Delete a permission.
        
        Args:
            permission_id: ID of the permission to delete
            
        Returns:
            True if the permission was deleted successfully, False if it doesn't exist
        """
        with self._lock:
            if permission_id not in self._permissions:
                logger.warning(f"Permission not found: {permission_id}")
                return False
            
            # Check if any roles use this permission
            for role in self._roles.values():
                if permission_id in role.permissions:
                    logger.warning(f"Cannot delete permission {permission_id}: it is used by role {role.id}")
                    return False
            
            # Remove from permissions dictionary
            del self._permissions[permission_id]
            
            # Save to file if auto-save is enabled
            self._save_permissions()
            
            return True
    
    # Policy management
    
    def create_access_policy(self, policy: AccessPolicy) -> bool:
        """
        Create a new access policy.
        
        Args:
            policy: Access policy to create
            
        Returns:
            True if the policy was created successfully, False if one already exists
        """
        with self._lock:
            if self._access_policy:
                logger.warning("Access policy already exists")
                return False
            
            self._access_policy = policy
            
            # Save to file if auto-save is enabled
            self._save_policy()
            
            return True
    
    def update_access_policy(self, policy: AccessPolicy) -> bool:
        """
        Update the access policy.
        
        Args:
            policy: Access policy to update
            
        Returns:
            True if the policy was updated successfully, False if none exists
        """
        with self._lock:
            if not self._access_policy:
                logger.warning("No access policy exists")
                return False
            
            # Update version and timestamp
            policy.version = self._access_policy.version + 1
            policy.updated_at = time.time()
            
            self._access_policy = policy
            
            # Save to file if auto-save is enabled
            self._save_policy()
            
            return True
    
    def assign_role_to_user(self, user_id: str, role_id: str) -> bool:
        """
        Assign a role to a user.
        
        Args:
            user_id: ID of the user
            role_id: ID of the role to assign
            
        Returns:
            True if the role was assigned successfully, False otherwise
        """
        with self._lock:
            if not self._access_policy:
                logger.warning("No access policy exists")
                return False
            
            if role_id not in self._roles:
                logger.warning(f"Role not found: {role_id}")
                return False
            
            # Initialize user's roles list if not present
            if user_id not in self._access_policy.role_assignments:
                self._access_policy.role_assignments[user_id] = []
            
            # Add role if not already assigned
            if role_id not in self._access_policy.role_assignments[user_id]:
                self._access_policy.role_assignments[user_id].append(role_id)
                
                # Update policy timestamp
                self._access_policy.updated_at = time.time()
                
                # Save to file if auto-save is enabled
                self._save_policy()
            
            return True
    
    def unassign_role_from_user(self, user_id: str, role_id: str) -> bool:
        """
        Unassign a role from a user.
        
        Args:
            user_id: ID of the user
            role_id: ID of the role to unassign
            
        Returns:
            True if the role was unassigned successfully, False otherwise
        """
        with self._lock:
            if not self._access_policy:
                logger.warning("No access policy exists")
                return False
            
            if user_id not in self._access_policy.role_assignments:
                logger.warning(f"User has no role assignments: {user_id}")
                return False
            
            # Remove role if assigned
            if role_id in self._access_policy.role_assignments[user_id]:
                self._access_policy.role_assignments[user_id].remove(role_id)
                
                # Update policy timestamp
                self._access_policy.updated_at = time.time()
                
                # Save to file if auto-save is enabled
                self._save_policy()
            
            return True
    
    def assign_role_to_group(self, group_id: str, role_id: str) -> bool:
        """
        Assign a role to a group.
        
        Args:
            group_id: ID of the group
            role_id: ID of the role to assign
            
        Returns:
            True if the role was assigned successfully, False otherwise
        """
        with self._lock:
            if not self._access_policy:
                logger.warning("No access policy exists")
                return False
            
            if role_id not in self._roles:
                logger.warning(f"Role not found: {role_id}")
                return False
            
            # Initialize group's roles list if not present
            if group_id not in self._access_policy.group_role_assignments:
                self._access_policy.group_role_assignments[group_id] = []
            
            # Add role if not already assigned
            if role_id not in self._access_policy.group_role_assignments[group_id]:
                self._access_policy.group_role_assignments[group_id].append(role_id)
                
                # Update policy timestamp
                self._access_policy.updated_at = time.time()
                
                # Save to file if auto-save is enabled
                self._save_policy()
            
            return True
    
    def unassign_role_from_group(self, group_id: str, role_id: str) -> bool:
        """
        Unassign a role from a group.
        
        Args:
            group_id: ID of the group
            role_id: ID of the role to unassign
            
        Returns:
            True if the role was unassigned successfully, False otherwise
        """
        with self._lock:
            if not self._access_policy:
                logger.warning("No access policy exists")
                return False
            
            if group_id not in self._access_policy.group_role_assignments:
                logger.warning(f"Group has no role assignments: {group_id}")
                return False
            
            # Remove role if assigned
            if role_id in self._access_policy.group_role_assignments[group_id]:
                self._access_policy.group_role_assignments[group_id].remove(role_id)
                
                # Update policy timestamp
                self._access_policy.updated_at = time.time()
                
                # Save to file if auto-save is enabled
                self._save_policy()
            
            return True
    
    def get_user_roles(self, user_id: str, include_default_roles: bool = True) -> List[str]:
        """
        Get all roles assigned to a user.
        
        Args:
            user_id: ID of the user
            include_default_roles: Whether to include default roles
            
        Returns:
            List of role IDs assigned to the user
        """
        if not self._access_policy:
            return []
        
        # Get directly assigned roles
        roles = list(self._access_policy.role_assignments.get(user_id, []))
        
        # Add default roles if requested
        if include_default_roles and not roles:
            roles.extend(self._access_policy.default_roles)
        
        return roles
    
    def get_group_roles(self, group_id: str) -> List[str]:
        """
        Get all roles assigned to a group.
        
        Args:
            group_id: ID of the group
            
        Returns:
            List of role IDs assigned to the group
        """
        if not self._access_policy:
            return []
        
        return list(self._access_policy.group_role_assignments.get(group_id, []))
    
    def get_all_permissions(self) -> Dict[str, Permission]:
        """
        Get all permissions.
        
        Returns:
            Dictionary of permission ID to Permission object
        """
        with self._lock:
            return self._permissions.copy()
    
    def get_all_roles(self) -> Dict[str, Role]:
        """
        Get all roles.
        
        Returns:
            Dictionary of role ID to Role object
        """
        with self._lock:
            return self._roles.copy()
    
    def get_permission(self, permission_id: str) -> Optional[Permission]:
        """
        Get a permission by ID.
        
        Args:
            permission_id: ID of the permission
            
        Returns:
            Permission object or None if not found
        """
        with self._lock:
            return self._permissions.get(permission_id)
    
    def get_role(self, role_id: str) -> Optional[Role]:
        """
        Get a role by ID.
        
        Args:
            role_id: ID of the role
            
        Returns:
            Role object or None if not found
        """
        with self._lock:
            return self._roles.get(role_id)
    
    def get_access_policy(self) -> Optional[AccessPolicy]:
        """
        Get the current access policy.
        
        Returns:
            Current access policy or None if none exists
        """
        with self._lock:
            return self._access_policy
    
    def shutdown(self) -> None:
        """
        Shutdown the RBAC manager.
        
        This stops the background refresh thread and saves any pending changes.
        """
        logger.info("Shutting down RBAC manager")
        
        # Stop background refresh
        if hasattr(self, "_refresh_thread") and self._refresh_thread.is_alive():
            self._shutdown_event.set()
            self._refresh_thread.join(timeout=5.0)
            if self._refresh_thread.is_alive():
                logger.warning("Background refresh thread did not terminate in time")
        
        # Save changes
        with self._lock:
            self._save_roles()
            self._save_permissions()
            self._save_policy()
