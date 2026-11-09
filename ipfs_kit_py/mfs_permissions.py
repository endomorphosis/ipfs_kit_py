#!/usr/bin/env python3
"""
Permissions management for IPFS MFS operations.

This module provides a permission management system for controlling access
to files and directories in the IPFS Mutable File System (MFS). It implements
UNIX-like permissions with users, groups, and access control lists (ACLs).
"""

import json
import os
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Any, Union

# Setup logging
logger = logging.getLogger(__name__)


class Permission(Enum):
    """Basic UNIX-style permissions."""
    READ = "r"
    WRITE = "w"
    EXECUTE = "x"


class FileType(Enum):
    """MFS file types."""
    FILE = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"


@dataclass
class UserPermission:
    """Permission for a specific user."""
    user_id: str
    permissions: Set[Permission] = field(default_factory=set)
    
    def can_read(self) -> bool:
        """Check if user has read permission."""
        return Permission.READ in self.permissions
    
    def can_write(self) -> bool:
        """Check if user has write permission."""
        return Permission.WRITE in self.permissions
    
    def can_execute(self) -> bool:
        """Check if user has execute permission."""
        return Permission.EXECUTE in self.permissions
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "user_id": self.user_id,
            "permissions": [p.value for p in self.permissions]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserPermission":
        """Create from dictionary."""
        return cls(
            user_id=data["user_id"],
            permissions={Permission(p) for p in data.get("permissions", [])}
        )


@dataclass
class GroupPermission:
    """Permission for a specific group."""
    group_id: str
    permissions: Set[Permission] = field(default_factory=set)
    
    def can_read(self) -> bool:
        """Check if group has read permission."""
        return Permission.READ in self.permissions
    
    def can_write(self) -> bool:
        """Check if group has write permission."""
        return Permission.WRITE in self.permissions
    
    def can_execute(self) -> bool:
        """Check if group has execute permission."""
        return Permission.EXECUTE in self.permissions
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "group_id": self.group_id,
            "permissions": [p.value for p in self.permissions]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GroupPermission":
        """Create from dictionary."""
        return cls(
            group_id=data["group_id"],
            permissions={Permission(p) for p in data.get("permissions", [])}
        )


@dataclass
class ACLEntry:
    """Access Control List entry for granular permissions."""
    target_id: str  # User or group ID
    target_type: str  # "user" or "group"
    permissions: Set[Permission] = field(default_factory=set)
    
    def can_read(self) -> bool:
        """Check if entry allows read permission."""
        return Permission.READ in self.permissions
    
    def can_write(self) -> bool:
        """Check if entry allows write permission."""
        return Permission.WRITE in self.permissions
    
    def can_execute(self) -> bool:
        """Check if entry allows execute permission."""
        return Permission.EXECUTE in self.permissions
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "target_id": self.target_id,
            "target_type": self.target_type,
            "permissions": [p.value for p in self.permissions]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ACLEntry":
        """Create from dictionary."""
        return cls(
            target_id=data["target_id"],
            target_type=data["target_type"],
            permissions={Permission(p) for p in data.get("permissions", [])}
        )


@dataclass
class FilePermissions:
    """Complete permissions for a file or directory."""
    path: str
    file_type: FileType = FileType.FILE
    owner_id: str = ""
    group_id: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    # Basic UNIX-style permissions
    owner_permissions: Set[Permission] = field(default_factory=lambda: {Permission.READ, Permission.WRITE})
    group_permissions: Set[Permission] = field(default_factory=lambda: {Permission.READ})
    other_permissions: Set[Permission] = field(default_factory=lambda: {Permission.READ})
    
    # Extended ACLs for finer-grained control
    acl: List[ACLEntry] = field(default_factory=list)
    
    def user_can_access(self, user_id: str, permission: Permission, user_groups: List[str] = None) -> bool:
        """
        Check if a user has specific access to the file.
        
        Args:
            user_id: ID of the user to check
            permission: Permission to check (READ, WRITE, EXECUTE)
            user_groups: List of groups the user belongs to
            
        Returns:
            bool: Whether the user has the requested permission
        """
        user_groups = user_groups or []
        
        print(f"*** FilePermissions.user_can_access: user_id={user_id}, permission={permission.value}")
        print(f"*** File owner: {self.owner_id}, Current user is owner: {user_id == self.owner_id}")
        print(f"*** Owner permissions: {[p.value for p in self.owner_permissions]}")
        print(f"*** Requested permission in owner_permissions: {permission in self.owner_permissions}")
        
        # Owner permissions
        if user_id == self.owner_id:
            if permission in self.owner_permissions:
                print(f"*** [ALLOW] User is owner and has {permission.value} permission")
                return True
            else:
                print(f"*** [DENY] User is owner but lacks {permission.value} permission")
        
        # Group permissions
        print(f"*** File group: {self.group_id}, User groups: {user_groups}")
        print(f"*** Group overlap: {self.group_id in user_groups}")
        print(f"*** Group permissions: {[p.value for p in self.group_permissions]}")
        print(f"*** Requested permission in group_permissions: {permission in self.group_permissions}")
        if self.group_id in user_groups:
            if permission in self.group_permissions:
                print(f"*** [ALLOW] User is in file's group and has {permission.value} permission")
                return True
            else:
                print(f"*** User is in file's group but lacks {permission.value} permission")
        
        # Check ACLs for specific user
        print(f"*** ACLs: {len(self.acl)} entries")
        for entry in self.acl:
            print(f"*** ACL entry: type={entry.target_type}, id={entry.target_id}, perms={[p.value for p in entry.permissions]}")
            if entry.target_type == "user" and entry.target_id == user_id:
                if permission in entry.permissions:
                    print(f"*** [ALLOW] User has {permission.value} permission via ACL entry")
                    return True
                else:
                    print(f"*** User has ACL entry but lacks {permission.value} permission")
            elif entry.target_type == "group" and entry.target_id in user_groups:
                if permission in entry.permissions:
                    print(f"*** [ALLOW] User's group has {permission.value} permission via ACL entry")
                    return True
                else:
                    print(f"*** User's group has ACL entry but lacks {permission.value} permission")
        
        # Other permissions (public access)
        print(f"*** Other permissions: {[p.value for p in self.other_permissions]}")
        print(f"*** Requested permission in other_permissions: {permission in self.other_permissions}")
        if permission in self.other_permissions:
            print(f"*** [ALLOW] Public access includes {permission.value} permission")
            return True
        
        print(f"*** [DENY] No permission granted via any channel")
        return False
    
    def add_acl_entry(self, entry: ACLEntry) -> None:
        """Add an ACL entry for a user or group."""
        # Check if entry already exists
        for i, existing in enumerate(self.acl):
            if (existing.target_id == entry.target_id and 
                existing.target_type == entry.target_type):
                # Update existing entry
                self.acl[i] = entry
                self.updated_at = time.time()
                return
        
        # Add new entry
        self.acl.append(entry)
        self.updated_at = time.time()
    
    def remove_acl_entry(self, target_id: str, target_type: str) -> bool:
        """Remove an ACL entry for a user or group."""
        for i, entry in enumerate(self.acl):
            if entry.target_id == target_id and entry.target_type == target_type:
                del self.acl[i]
                self.updated_at = time.time()
                return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "path": self.path,
            "file_type": self.file_type.value,
            "owner_id": self.owner_id,
            "group_id": self.group_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "owner_permissions": [p.value for p in self.owner_permissions],
            "group_permissions": [p.value for p in self.group_permissions],
            "other_permissions": [p.value for p in self.other_permissions],
            "acl": [entry.to_dict() for entry in self.acl]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FilePermissions":
        """Create from dictionary."""
        result = cls(
            path=data["path"],
            file_type=FileType(data["file_type"]),
            owner_id=data["owner_id"],
            group_id=data["group_id"],
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            owner_permissions={Permission(p) for p in data.get("owner_permissions", [])},
            group_permissions={Permission(p) for p in data.get("group_permissions", [])},
            other_permissions={Permission(p) for p in data.get("other_permissions", [])}
        )
        
        # Add ACL entries
        for entry_data in data.get("acl", []):
            result.acl.append(ACLEntry.from_dict(entry_data))
        
        return result


class PermissionManager:
    """
    Manages file and directory permissions for MFS.
    
    Provides UNIX-like permissions with users, groups, and ACLs for
    files and directories in the IPFS Mutable File System.
    """
    
    def __init__(self, 
                 permissions_dir: Optional[str] = None,
                 current_user_id: Optional[str] = None,
                 default_permissions: Optional[Dict[str, Any]] = None):
        """
        Initialize permission manager.
        
        Args:
            permissions_dir: Directory to store permission information
            current_user_id: ID of the current user
            default_permissions: Default permissions for new files and directories
        """
        self.permissions_dir = permissions_dir or os.path.expanduser("~/.ipfs_kit/permissions")
        os.makedirs(self.permissions_dir, exist_ok=True)
        
        self.current_user_id = current_user_id or "default_user"
        self.user_groups = {}  # user_id -> list of group_ids
        self.file_permissions = {}  # path -> FilePermissions
        
        # Set default permissions
        self.default_file_permissions = {
            "owner": {Permission.READ, Permission.WRITE},
            "group": {Permission.READ},
            "other": {Permission.READ}
        }
        self.default_dir_permissions = {
            "owner": {Permission.READ, Permission.WRITE, Permission.EXECUTE},
            "group": {Permission.READ, Permission.EXECUTE},
            "other": {Permission.READ, Permission.EXECUTE}
        }
        
        if default_permissions:
            # Override defaults if provided
            if "file" in default_permissions:
                file_perms = default_permissions["file"]
                self.default_file_permissions = {
                    "owner": {Permission(p) for p in file_perms.get("owner", ["r", "w"])},
                    "group": {Permission(p) for p in file_perms.get("group", ["r"])},
                    "other": {Permission(p) for p in file_perms.get("other", ["r"])}
                }
            
            if "directory" in default_permissions:
                dir_perms = default_permissions["directory"]
                self.default_dir_permissions = {
                    "owner": {Permission(p) for p in dir_perms.get("owner", ["r", "w", "x"])},
                    "group": {Permission(p) for p in dir_perms.get("group", ["r", "x"])},
                    "other": {Permission(p) for p in dir_perms.get("other", ["r", "x"])}
                }
        
        # Load existing user groups
        self._load_user_groups()
    
    def _get_permissions_path(self, file_path: str) -> str:
        """Get path to permissions file for a given MFS path."""
        # Convert path to safe filename
        safe_path = file_path.replace("/", "_").strip("_")
        if not safe_path:
            safe_path = "root"
        return os.path.join(self.permissions_dir, f"{safe_path}.json")
    
    def _get_groups_path(self) -> str:
        """Get path to the user groups file."""
        return os.path.join(self.permissions_dir, "user_groups.json")
    
    def _load_user_groups(self) -> None:
        """Load user group memberships from file."""
        groups_path = self._get_groups_path()
        if os.path.exists(groups_path):
            try:
                with open(groups_path, "r") as f:
                    self.user_groups = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading user groups: {e}")
                self.user_groups = {}
    
    def _save_user_groups(self) -> None:
        """Save user group memberships to file."""
        groups_path = self._get_groups_path()
        try:
            with open(groups_path, "w") as f:
                json.dump(self.user_groups, f)
        except IOError as e:
            logger.error(f"Error saving user groups: {e}")
    
    def add_user_to_group(self, user_id: str, group_id: str) -> None:
        """
        Add a user to a group.
        
        Args:
            user_id: ID of the user
            group_id: ID of the group
        """
        if user_id not in self.user_groups:
            self.user_groups[user_id] = []
        
        if group_id not in self.user_groups[user_id]:
            self.user_groups[user_id].append(group_id)
            self._save_user_groups()
    
    def remove_user_from_group(self, user_id: str, group_id: str) -> bool:
        """
        Remove a user from a group.
        
        Args:
            user_id: ID of the user
            group_id: ID of the group
            
        Returns:
            bool: Whether the user was removed from the group
        """
        if user_id in self.user_groups and group_id in self.user_groups[user_id]:
            self.user_groups[user_id].remove(group_id)
            self._save_user_groups()
            return True
        return False
    
    def get_user_groups(self, user_id: str) -> List[str]:
        """
        Get the groups a user belongs to.
        
        Args:
            user_id: ID of the user
            
        Returns:
            List[str]: List of group IDs the user belongs to
        """
        return self.user_groups.get(user_id, [])
    
    async def load_permissions(self, file_path: str) -> Optional[FilePermissions]:
        """
        Load permissions for a file from disk.
        
        Args:
            file_path: Path to the file in MFS
            
        Returns:
            FilePermissions: Permissions for the file, or None if not found
        """
        logger.debug(f"Loading permissions for path: {file_path}")
        
        # Check in-memory cache first
        if file_path in self.file_permissions:
            logger.debug(f"Cache hit: Found permissions in memory cache for {file_path}")
            cache_perms = self.file_permissions[file_path]
            logger.debug(f"Cache permissions for {file_path}: owner_id={cache_perms.owner_id}, "
                         f"owner_permissions={[p.value for p in cache_perms.owner_permissions]}")
            return self.file_permissions[file_path]
        
        logger.debug(f"Cache miss: Permissions not in memory cache, loading from disk")
        
        # Try to load from disk
        permissions_path = self._get_permissions_path(file_path)
        logger.debug(f"Permission file path: {permissions_path}")
        
        if os.path.exists(permissions_path):
            logger.debug(f"Permission file exists on disk")
            try:
                with open(permissions_path, "r") as f:
                    data = json.load(f)
                    
                logger.debug(f"Raw permission data from disk: owner_permissions={data.get('owner_permissions', [])}")
                
                permissions = FilePermissions.from_dict(data)
                logger.debug(f"Parsed permissions from disk: owner_id={permissions.owner_id}, "
                            f"owner_permissions={[p.value for p in permissions.owner_permissions]}")
                
                logger.debug(f"Adding permissions to memory cache")
                self.file_permissions[file_path] = permissions
                return permissions
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Error loading permissions file {permissions_path}: {e}")
        else:
            logger.debug(f"Permission file does not exist on disk")
        
        logger.debug(f"No permissions found for {file_path}")
        return None
    
    async def save_permissions(self, permissions: FilePermissions) -> None:
        """
        Save permissions for a file to disk.
        
        Args:
            permissions: Permissions to save
        """
        # Update in-memory cache
        self.file_permissions[permissions.path] = permissions
        
        # Save to disk
        permissions_path = self._get_permissions_path(permissions.path)
        try:
            # Ensure the path is updated
            permissions.updated_at = time.time()
            
            with open(permissions_path, "w") as f:
                json.dump(permissions.to_dict(), f)
                
            logger.debug(f"Saved permissions for path: {permissions.path}, "
                       f"owner_perms: {[p.value for p in permissions.owner_permissions]}")
        except IOError as e:
            logger.error(f"Error saving permissions to {permissions_path}: {e}")
            
    async def clear_cache(self, file_path: Optional[str] = None) -> None:
        """
        Clear the in-memory permissions cache.
        
        Args:
            file_path: Specific file path to clear from cache, or None to clear all
        """
        if file_path:
            if file_path in self.file_permissions:
                logger.debug(f"Clearing cache for path: {file_path}")
                del self.file_permissions[file_path]
        else:
            logger.debug("Clearing entire permissions cache")
            self.file_permissions = {}
    
    async def delete_permissions(self, file_path: str) -> bool:
        """
        Delete permissions for a file.
        
        Args:
            file_path: Path to the file in MFS
            
        Returns:
            bool: Whether permissions were deleted
        """
        if file_path in self.file_permissions:
            del self.file_permissions[file_path]
        
        permissions_path = self._get_permissions_path(file_path)
        if os.path.exists(permissions_path):
            try:
                os.remove(permissions_path)
                return True
            except IOError as e:
                logger.error(f"Error deleting permissions file {permissions_path}: {e}")
        
        return False
    
    def create_default_permissions(self, 
                                 file_path: str, 
                                 file_type: FileType,
                                 owner_id: Optional[str] = None,
                                 group_id: Optional[str] = None) -> FilePermissions:
        """
        Create default permissions for a new file or directory.
        
        Args:
            file_path: Path to the file in MFS
            file_type: Type of file (FILE, DIRECTORY, SYMLINK)
            owner_id: ID of the owner (defaults to current user)
            group_id: ID of the group (defaults to user's primary group)
            
        Returns:
            FilePermissions: Default permissions for the file
        """
        owner_id = owner_id or self.current_user_id
        group_id = group_id or "users"  # Default group
        
        if file_type == FileType.DIRECTORY:
            permissions = FilePermissions(
                path=file_path,
                file_type=FileType.DIRECTORY,
                owner_id=owner_id,
                group_id=group_id,
                owner_permissions=self.default_dir_permissions["owner"],
                group_permissions=self.default_dir_permissions["group"],
                other_permissions=self.default_dir_permissions["other"]
            )
        else:
            permissions = FilePermissions(
                path=file_path,
                file_type=file_type,
                owner_id=owner_id,
                group_id=group_id,
                owner_permissions=self.default_file_permissions["owner"],
                group_permissions=self.default_file_permissions["group"],
                other_permissions=self.default_file_permissions["other"]
            )
        
        return permissions
    
    async def ensure_permissions(self, 
                              file_path: str, 
                              file_type: FileType,
                              ipfs_client=None) -> FilePermissions:
        """
        Ensure permissions exist for a file, creating them if needed.
        
        Args:
            file_path: Path to the file in MFS
            file_type: Type of file (FILE, DIRECTORY, SYMLINK)
            ipfs_client: Optional IPFS client for checking file existence
            
        Returns:
            FilePermissions: Permissions for the file
        """
        permissions = await self.load_permissions(file_path)
        if permissions:
            return permissions
        
        # Create default permissions
        permissions = self.create_default_permissions(file_path, file_type)
        await self.save_permissions(permissions)
        return permissions
    
    async def check_permission(self, 
                             file_path: str, 
                             permission: Permission,
                             user_id: Optional[str] = None) -> bool:
        """
        Check if a user has a specific permission for a file.
        
        Args:
            file_path: Path to the file in MFS
            permission: Permission to check (READ, WRITE, EXECUTE)
            user_id: ID of the user (defaults to current user)
            
        Returns:
            bool: Whether the user has the requested permission
        """
        user_id = user_id or self.current_user_id
        
        logger.debug(f"Checking permission: path={file_path}, permission={permission.value}, user={user_id}")
        
        # Super user has all permissions
        if user_id == "root":
            logger.debug(f"Root user has all permissions")
            return True
        
        # Load permissions
        permissions = await self.load_permissions(file_path)
        
        if not permissions:
            # No permissions defined, use default access rules
            # For safety, restrict access when permissions are missing
            logger.debug(f"No permissions defined for path: {file_path}")
            return False
        
        # Get user's groups
        user_groups = self.get_user_groups(user_id)
        
        # Check if user has permission
        result = permissions.user_can_access(user_id, permission, user_groups)
        
        if result:
            logger.debug(f"Permission granted for user {user_id} on {file_path} for {permission.value}")
        else:
            logger.debug(f"Permission denied for user {user_id} on {file_path} for {permission.value}")
            
        return result
    
    async def set_owner(self, 
                      file_path: str, 
                      owner_id: str,
                      group_id: Optional[str] = None) -> bool:
        """
        Set the owner and optionally group of a file.
        
        Args:
            file_path: Path to the file in MFS
            owner_id: New owner ID
            group_id: New group ID (if None, group is not changed)
            
        Returns:
            bool: Whether the owner was successfully changed
        """
        permissions = await self.load_permissions(file_path)
        if not permissions:
            # Create default permissions with the specified owner
            file_type = FileType.DIRECTORY if file_path.endswith("/") else FileType.FILE
            permissions = self.create_default_permissions(file_path, file_type, owner_id, group_id)
        else:
            # Update owner
            permissions.owner_id = owner_id
            if group_id is not None:
                permissions.group_id = group_id
            permissions.updated_at = time.time()
        
        await self.save_permissions(permissions)
        return True
    
    async def set_permissions(self,
                           file_path: str,
                           owner_perms: Optional[Set[Permission]] = None,
                           group_perms: Optional[Set[Permission]] = None,
                           other_perms: Optional[Set[Permission]] = None) -> bool:
        """
        Set permissions for a file.
        
        Args:
            file_path: Path to the file in MFS
            owner_perms: New owner permissions
            group_perms: New group permissions
            other_perms: New public permissions
            
        Returns:
            bool: Whether permissions were successfully changed
        """
        permissions = await self.load_permissions(file_path)
        if not permissions:
            # Create default permissions first
            file_type = FileType.DIRECTORY if file_path.endswith("/") else FileType.FILE
            permissions = self.create_default_permissions(file_path, file_type)
        
        # Update permissions that were specified
        if owner_perms is not None:
            permissions.owner_permissions = owner_perms
        if group_perms is not None:
            permissions.group_permissions = group_perms
        if other_perms is not None:
            permissions.other_permissions = other_perms
        
        permissions.updated_at = time.time()
        await self.save_permissions(permissions)
        return True
    
    async def add_acl_entry(self,
                         file_path: str,
                         target_id: str,
                         target_type: str,
                         permissions_list: List[str]) -> bool:
        """
        Add an ACL entry for a user or group.
        
        Args:
            file_path: Path to the file in MFS
            target_id: ID of the user or group
            target_type: "user" or "group"
            permissions_list: List of permission strings ("r", "w", "x")
            
        Returns:
            bool: Whether the ACL entry was added successfully
        """
        if target_type not in ("user", "group"):
            raise ValueError("Target type must be 'user' or 'group'")
        
        # Convert permission strings to Permission enum
        perms = {Permission(p) for p in permissions_list if p in ("r", "w", "x")}
        entry = ACLEntry(target_id=target_id, target_type=target_type, permissions=perms)
        
        file_perms = await self.load_permissions(file_path)
        if not file_perms:
            # Create default permissions first
            file_type = FileType.DIRECTORY if file_path.endswith("/") else FileType.FILE
            file_perms = self.create_default_permissions(file_path, file_type)
        
        # Add ACL entry
        file_perms.add_acl_entry(entry)
        await self.save_permissions(file_perms)
        return True
    
    async def remove_acl_entry(self,
                            file_path: str,
                            target_id: str,
                            target_type: str) -> bool:
        """
        Remove an ACL entry for a user or group.
        
        Args:
            file_path: Path to the file in MFS
            target_id: ID of the user or group
            target_type: "user" or "group"
            
        Returns:
            bool: Whether the ACL entry was removed successfully
        """
        file_perms = await self.load_permissions(file_path)
        if not file_perms:
            return False
        
        # Remove ACL entry
        result = file_perms.remove_acl_entry(target_id, target_type)
        if result:
            await self.save_permissions(file_perms)
        return result
    
    async def inherit_permissions(self,
                               file_path: str,
                               parent_path: str,
                               inherit_acls: bool = True) -> bool:
        """
        Inherit permissions from a parent directory.
        
        Args:
            file_path: Path to the file in MFS
            parent_path: Path to the parent directory
            inherit_acls: Whether to inherit ACLs
            
        Returns:
            bool: Whether permissions were inherited successfully
        """
        parent_perms = await self.load_permissions(parent_path)
        if not parent_perms:
            return False
        
        # Load or create permissions for the file
        file_perms = await self.load_permissions(file_path)
        if not file_perms:
            file_type = FileType.DIRECTORY if file_path.endswith("/") else FileType.FILE
            file_perms = self.create_default_permissions(file_path, file_type)
        
        # Inherit basic permissions
        file_perms.group_id = parent_perms.group_id
        file_perms.group_permissions = parent_perms.group_permissions.copy()
        file_perms.other_permissions = parent_perms.other_permissions.copy()
        
        # Inherit ACLs if requested
        if inherit_acls:
            file_perms.acl = [ACLEntry(
                target_id=entry.target_id,
                target_type=entry.target_type,
                permissions=entry.permissions.copy()
            ) for entry in parent_perms.acl]
        
        file_perms.updated_at = time.time()
        await self.save_permissions(file_perms)
        return True


class AccessDeniedException(Exception):
    """Exception raised when a user does not have permission for an operation."""
    
    def __init__(self, path: str, permission: Permission, user_id: str):
        self.path = path
        self.permission = permission
        self.user_id = user_id
        message = f"Access denied for user {user_id} on {path}: lacks {permission.value} permission"
        super().__init__(message)