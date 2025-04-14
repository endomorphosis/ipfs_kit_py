"""
Authentication and Authorization models for MCP server.

This module defines the data models for the authentication and authorization system
as specified in the MCP roadmap for Phase 1: Core Functionality Enhancements (Q3 2025).
"""

from pydantic import BaseModel, Field, EmailStr, SecretStr, validator
from typing import Dict, List, Any, Optional, Union, Set
from datetime import datetime
import uuid
import re

class Role(BaseModel):
    """Role definition for RBAC system."""
    id: str = Field(default_factory=lambda: f"role_{uuid.uuid4().hex[:8]}")
    name: str = Field(..., description="Name of the role")
    description: Optional[str] = Field(None, description="Description of the role")
    permissions: Set[str] = Field(default_factory=set, description="Permissions assigned to the role")
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    
    @validator('name')
    def name_must_be_valid(cls, v):
        if not re.match(r'^[a-zA-Z0-9_-]{3,50}$', v):
            raise ValueError('Role name must be 3-50 characters and contain only alphanumeric characters, underscores, and hyphens')
        return v

class Permission(BaseModel):
    """Permission definition."""
    id: str = Field(default_factory=lambda: f"perm_{uuid.uuid4().hex[:8]}")
    name: str = Field(..., description="Name of the permission")
    description: Optional[str] = Field(None, description="Description of the permission")
    resource_type: str = Field(..., description="Type of resource this permission applies to")
    actions: Set[str] = Field(..., description="Actions allowed by this permission")
    conditions: Optional[Dict[str, Any]] = Field(None, description="Conditional expressions for permission")
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    
    @validator('name')
    def name_must_be_valid(cls, v):
        if not re.match(r'^[a-zA-Z0-9_:.-]{3,100}$', v):
            raise ValueError('Permission name must be 3-100 characters and contain only alphanumeric characters, underscores, colons, periods, and hyphens')
        return v
    
    @validator('actions')
    def actions_must_be_valid(cls, v):
        valid_actions = {'create', 'read', 'update', 'delete', 'list', 'execute', '*'}
        for action in v:
            if action not in valid_actions and not action.endswith(':*'):
                raise ValueError(f'Invalid action: {action}. Valid actions are {valid_actions} or custom actions with wildcard (e.g., "custom:*")')
        return v

class User(BaseModel):
    """User account definition."""
    id: str = Field(default_factory=lambda: f"user_{uuid.uuid4().hex[:8]}")
    username: str = Field(..., description="Username for login")
    email: Optional[EmailStr] = Field(None, description="User email address")
    full_name: Optional[str] = Field(None, description="User's full name")
    hashed_password: Optional[str] = Field(None, description="Hashed password")
    active: bool = Field(True, description="Whether the user account is active")
    roles: Set[str] = Field(default_factory=set, description="Roles assigned to the user")
    direct_permissions: Set[str] = Field(default_factory=set, description="Permissions directly assigned to the user")
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    last_login: Optional[float] = Field(None, description="Timestamp of last login")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional user metadata")
    
    @validator('username')
    def username_must_be_valid(cls, v):
        if not re.match(r'^[a-zA-Z0-9_.-]{3,50}$', v):
            raise ValueError('Username must be 3-50 characters and contain only alphanumeric characters, underscores, periods, and hyphens')
        return v

class ApiKey(BaseModel):
    """API key definition."""
    id: str = Field(default_factory=lambda: f"key_{uuid.uuid4().hex}")
    name: str = Field(..., description="Name of the API key")
    key: str = Field(default_factory=lambda: f"ipfk_{uuid.uuid4().hex}")
    user_id: str = Field(..., description="User ID this API key belongs to")
    hashed_key: Optional[str] = Field(None, description="Hashed API key for verification")
    active: bool = Field(True, description="Whether the API key is active")
    roles: Set[str] = Field(default_factory=set, description="Roles assigned to this API key")
    direct_permissions: Set[str] = Field(default_factory=set, description="Permissions directly assigned to this API key")
    expires_at: Optional[float] = Field(None, description="Expiration timestamp")
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    last_used: Optional[float] = Field(None, description="Timestamp of last usage")
    allowed_ips: Optional[List[str]] = Field(None, description="IP addresses allowed to use this key")
    backend_restrictions: Optional[List[str]] = Field(None, description="Backends this key is restricted to")
    
    @validator('name')
    def name_must_be_valid(cls, v):
        if not re.match(r'^[a-zA-Z0-9_\s.-]{3,100}$', v):
            raise ValueError('API key name must be 3-100 characters and contain only alphanumeric characters, underscores, spaces, periods, and hyphens')
        return v

class OAuthProvider(BaseModel):
    """OAuth provider configuration."""
    id: str = Field(default_factory=lambda: f"oauth_{uuid.uuid4().hex[:8]}")
    name: str = Field(..., description="Name of the OAuth provider")
    provider_type: str = Field(..., description="Type of OAuth provider (github, google, etc.)")
    client_id: str = Field(..., description="OAuth client ID")
    client_secret: SecretStr = Field(..., description="OAuth client secret")
    authorize_url: str = Field(..., description="Authorization URL")
    token_url: str = Field(..., description="Token URL")
    userinfo_url: str = Field(..., description="User info URL")
    scope: str = Field(..., description="OAuth scope")
    active: bool = Field(True, description="Whether the provider is active")
    default_roles: Set[str] = Field(default_factory=set, description="Default roles for users authenticated with this provider")
    domain_restrictions: Optional[List[str]] = Field(None, description="Domain restrictions for email addresses")
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = Field(default_factory=lambda: datetime.now().timestamp())

class BackendPermission(BaseModel):
    """Permission settings for a specific backend."""
    backend_id: str = Field(..., description="Backend identifier")
    allowed_roles: Set[str] = Field(default_factory=set, description="Roles allowed to access this backend")
    allowed_permissions: Set[str] = Field(default_factory=set, description="Permissions required to access this backend")
    public: bool = Field(False, description="Whether the backend is publicly accessible")
    read_only: bool = Field(False, description="Whether the backend is read-only for normal users")
    admin_only: bool = Field(False, description="Whether the backend is admin-only")
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = Field(default_factory=lambda: datetime.now().timestamp())

class AccessPolicy(BaseModel):
    """Access policy for fine-grained control."""
    id: str = Field(default_factory=lambda: f"policy_{uuid.uuid4().hex[:8]}")
    name: str = Field(..., description="Name of the policy")
    description: Optional[str] = Field(None, description="Description of the policy")
    resources: List[str] = Field(..., description="Resources this policy applies to")
    actions: List[str] = Field(..., description="Actions this policy applies to")
    effect: str = Field(..., description="Effect of the policy (allow or deny)")
    conditions: Optional[Dict[str, Any]] = Field(None, description="Conditions for the policy")
    principals: List[str] = Field(..., description="Principals (users/roles) this policy applies to")
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    
    @validator('effect')
    def effect_must_be_valid(cls, v):
        if v not in ['allow', 'deny']:
            raise ValueError('Effect must be either "allow" or "deny"')
        return v

class Session(BaseModel):
    """User session information."""
    id: str = Field(default_factory=lambda: f"sess_{uuid.uuid4().hex}")
    user_id: str = Field(..., description="User ID for this session")
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    expires_at: float = Field(..., description="Expiration timestamp")
    ip_address: Optional[str] = Field(None, description="IP address for this session")
    user_agent: Optional[str] = Field(None, description="User agent for this session")
    active: bool = Field(True, description="Whether the session is active")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional session metadata")
    last_activity: float = Field(default_factory=lambda: datetime.now().timestamp())

class TokenData(BaseModel):
    """Data stored in authentication tokens."""
    sub: str = Field(..., description="Subject (user ID)")
    exp: float = Field(..., description="Expiration timestamp")
    iat: float = Field(..., description="Issued at timestamp")
    scope: str = Field("access", description="Token scope")
    type: str = Field("bearer", description="Token type")
    roles: List[str] = Field(default_factory=list, description="User roles")
    permissions: List[str] = Field(default_factory=list, description="User permissions")
    is_api_key: bool = Field(False, description="Whether this token is for an API key")
    session_id: Optional[str] = Field(None, description="Session ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional token metadata")

class LoginRequest(BaseModel):
    """Login request data."""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")
    remember_me: bool = Field(False, description="Whether to create a long-lived session")

class RegisterRequest(BaseModel):
    """User registration request data."""
    username: str = Field(..., description="Username")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., description="Password")
    full_name: Optional[str] = Field(None, description="Full name")
    
    @validator('password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one number')
        return v

class ApiKeyCreateRequest(BaseModel):
    """API key creation request data."""
    name: str = Field(..., description="Name for the API key")
    expires_in_days: Optional[int] = Field(None, description="Days until expiration")
    roles: Optional[List[str]] = Field(None, description="Roles to assign")
    permissions: Optional[List[str]] = Field(None, description="Direct permissions to assign")
    backend_restrictions: Optional[List[str]] = Field(None, description="Backends to restrict this key to")
    allowed_ips: Optional[List[str]] = Field(None, description="IP addresses allowed to use this key")

class ApiKeyResponse(BaseModel):
    """API key response after creation."""
    id: str = Field(..., description="API key ID")
    name: str = Field(..., description="API key name")
    key: str = Field(..., description="The actual API key value (only shown once)")
    expires_at: Optional[float] = Field(None, description="Expiration timestamp")
    user_id: str = Field(..., description="User ID this key belongs to")
    created_at: float = Field(..., description="Creation timestamp")
    roles: List[str] = Field(default_factory=list, description="Assigned roles")
    permissions: List[str] = Field(default_factory=list, description="Assigned permissions")
    backend_restrictions: Optional[List[str]] = Field(None, description="Backend restrictions")