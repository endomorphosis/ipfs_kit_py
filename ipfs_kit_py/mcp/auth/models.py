"""
Authentication and Authorization Models for MCP Server

Defines core authentication and authorization models:
- Permission/scope definitions
- User and role models
- Token models

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.
"""

import os
import enum
import time
import secrets
from typing import Dict, List, Optional, Set, Union, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, validator, root_validator


class Permission(str, enum.Enum):
    """
    Available permission scopes in the MCP system.
    
    Permissions follow a resource:action pattern.
    """
    # READ permissions
    READ_BASIC = "read:basic"
    READ_IPFS = "read:ipfs"
    READ_FILECOIN = "read:filecoin"
    READ_STORACHA = "read:storacha"
    READ_S3 = "read:s3"
    READ_LASSIE = "read:lassie"
    READ_HUGGINGFACE = "read:huggingface"
    READ_ADMIN = "read:admin"
    
    # WRITE permissions
    WRITE_BASIC = "write:basic"
    WRITE_IPFS = "write:ipfs"
    WRITE_FILECOIN = "write:filecoin"
    WRITE_STORACHA = "write:storacha"
    WRITE_S3 = "write:s3"
    WRITE_LASSIE = "write:lassie" 
    WRITE_HUGGINGFACE = "write:huggingface"
    WRITE_ADMIN = "write:admin"
    
    # ADMIN permissions
    ADMIN_USERS = "admin:users"
    ADMIN_ROLES = "admin:roles"
    ADMIN_SYSTEM = "admin:system"
    ADMIN_AUDIT = "admin:audit"


class Role(str, enum.Enum):
    """
    User roles in the MCP system.
    
    Each role includes a set of permissions.
    """
    ANONYMOUS = "anonymous"  # Unauthenticated users
    USER = "user"            # Basic authenticated users
    DEVELOPER = "developer"  # Developers with advanced permissions
    ADMIN = "admin"          # System administrators
    SYSTEM = "system"        # For system services/automation


# Define permissions for each role
ROLE_PERMISSIONS = {
    Role.ANONYMOUS: [
        Permission.READ_BASIC,
    ],
    
    Role.USER: [
        Permission.READ_BASIC,
        Permission.READ_IPFS,
        Permission.READ_FILECOIN,
        Permission.READ_STORACHA,
        Permission.READ_S3,
        Permission.READ_LASSIE,
        Permission.READ_HUGGINGFACE,
        Permission.WRITE_BASIC,
        Permission.WRITE_IPFS,
    ],
    
    Role.DEVELOPER: [
        Permission.READ_BASIC,
        Permission.READ_IPFS,
        Permission.READ_FILECOIN,
        Permission.READ_STORACHA,
        Permission.READ_S3,
        Permission.READ_LASSIE,
        Permission.READ_HUGGINGFACE,
        Permission.READ_ADMIN,
        Permission.WRITE_BASIC,
        Permission.WRITE_IPFS,
        Permission.WRITE_FILECOIN,
        Permission.WRITE_STORACHA,
        Permission.WRITE_S3,
        Permission.WRITE_LASSIE,
        Permission.WRITE_HUGGINGFACE,
    ],
    
    Role.ADMIN: [
        Permission.READ_BASIC,
        Permission.READ_IPFS,
        Permission.READ_FILECOIN,
        Permission.READ_STORACHA,
        Permission.READ_S3,
        Permission.READ_LASSIE,
        Permission.READ_HUGGINGFACE,
        Permission.READ_ADMIN,
        Permission.WRITE_BASIC,
        Permission.WRITE_IPFS,
        Permission.WRITE_FILECOIN,
        Permission.WRITE_STORACHA,
        Permission.WRITE_S3,
        Permission.WRITE_LASSIE,
        Permission.WRITE_HUGGINGFACE,
        Permission.WRITE_ADMIN,
        Permission.ADMIN_USERS,
        Permission.ADMIN_ROLES,
        Permission.ADMIN_AUDIT,
    ],
    
    Role.SYSTEM: [
        # System role has all permissions
        *list(Permission),
    ]
}


def has_permission(role: Role, permission: Permission) -> bool:
    """Check if a role has a specific permission."""
    return permission in ROLE_PERMISSIONS.get(role, [])


def get_role_permissions(role: Role) -> List[Permission]:
    """Get all permissions for a role."""
    return ROLE_PERMISSIONS.get(role, [])


# Backend-specific permission mapping
BACKEND_PERMISSIONS = {
    "ipfs": [Permission.READ_IPFS, Permission.WRITE_IPFS],
    "filecoin": [Permission.READ_FILECOIN, Permission.WRITE_FILECOIN],
    "storacha": [Permission.READ_STORACHA, Permission.WRITE_STORACHA],
    "s3": [Permission.READ_S3, Permission.WRITE_S3],
    "lassie": [Permission.READ_LASSIE, Permission.WRITE_LASSIE],
    "huggingface": [Permission.READ_HUGGINGFACE, Permission.WRITE_HUGGINGFACE],
}


def has_backend_permission(role: Role, backend: str, write_access: bool = False) -> bool:
    """
    Check if a role has permission to access a specific backend.
    
    Args:
        role: User role
        backend: Storage backend name
        write_access: Whether write access is required
    
    Returns:
        True if the role has permission to access the backend
    """
    # Admin and system roles have access to all backends
    if role in (Role.ADMIN, Role.SYSTEM):
        return True
    
    # Get permissions for this backend
    backend_perms = BACKEND_PERMISSIONS.get(backend.lower(), [])
    if not backend_perms:
        return False
    
    # Check for required permission (read or write)
    required_perm = backend_perms[1] if write_access and len(backend_perms) > 1 else backend_perms[0]
    return has_permission(role, required_perm)


# Pydantic models for auth

class UserBase(BaseModel):
    """Base model for user data."""
    username: str
    email: Optional[str] = None
    role: Role = Role.USER
    is_active: bool = True


class UserCreate(UserBase):
    """Model for creating a new user."""
    password: str
    
    @validator('password')
    def password_strength(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        # Add more password strength rules as needed
        return v


class UserUpdate(BaseModel):
    """Model for updating a user."""
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[Role] = None
    is_active: Optional[bool] = None
    custom_permissions: Optional[List[Permission]] = None


class User(UserBase):
    """Complete user model."""
    id: str
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    custom_permissions: List[Permission] = []

    class Config:
        orm_mode = True


class TokenData(BaseModel):
    """Data contained in authentication tokens."""
    user_id: str
    username: str
    role: Role
    permissions: List[Permission]
    exp: Optional[int] = None  # Expiration timestamp


class TokenResponse(BaseModel):
    """Response model for token generation."""
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: Optional[str] = None


class APIKeyBase(BaseModel):
    """Base model for API keys."""
    name: str
    permissions: List[Permission] = []
    expires_at: Optional[datetime] = None


class APIKeyCreate(APIKeyBase):
    """Model for creating a new API key."""
    user_id: str
    
    
class APIKey(APIKeyBase):
    """Complete API key model."""
    id: str
    key: str  # The actual API key value (hashed in storage)
    user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    is_active: bool = True
    backend_restrictions: Optional[Dict[str, bool]] = None

    class Config:
        orm_mode = True


class Session(BaseModel):
    """Session model for user authentication."""
    id: str = Field(default_factory=lambda: secrets.token_hex(16))
    user_id: str
    expires_at: float
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    active: bool = True
    created_at: float = Field(default_factory=time.time)
    last_activity: float = Field(default_factory=time.time)

    class Config:
        orm_mode = True


class LoginRequest(BaseModel):
    """Request model for user login."""
    username: str
    password: str


class RegisterRequest(BaseModel):
    """Request model for user registration."""
    username: str
    email: str
    password: str
    full_name: Optional[str] = None

    @validator('password')
    def password_strength(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        # Add more password strength rules as needed
        return v


class RefreshTokenRequest(BaseModel):
    """Request model for refreshing an access token."""
    refresh_token: str


class APIKeyResponse(BaseModel):
    """Response model for API key creation."""
    id: str
    name: str
    key: str  # Only returned once when created
    user_id: str
    created_at: float
    expires_at: Optional[float] = None
    roles: List[str] = []
    permissions: List[str] = []
    backend_restrictions: Optional[Dict[str, bool]] = None


class OAuthProvider(str, enum.Enum):
    """Supported OAuth providers."""
    GITHUB = "github"
    GOOGLE = "google"
    FACEBOOK = "facebook"
    TWITTER = "twitter"
    MICROSOFT = "microsoft"


class BackendPermission(BaseModel):
    """
    Backend-specific permission model.
    
    Controls access to specific storage backends for users or API keys.
    """
    backend_id: str
    read_access: bool = True
    write_access: bool = False
    extra_permissions: Dict[str, bool] = {}
    
    class Config:
        orm_mode = True


class PermissionModel(BaseModel):
    """Permission model for storing permission data."""
    id: str = Field(default_factory=lambda: secrets.token_hex(16))
    name: str
    description: str
    resource_type: str
    actions: Set[str] = set()
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    class Config:
        orm_mode = True


class RoleModel(BaseModel):
    """Role model for storing role data."""
    id: str = Field(default_factory=lambda: secrets.token_hex(16))
    name: str
    description: str
    permissions: Set[str] = set()
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    class Config:
        orm_mode = True


class OAuthConnection(BaseModel):
    """OAuth connection model."""
    id: str
    user_id: str
    provider: OAuthProvider
    provider_user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
