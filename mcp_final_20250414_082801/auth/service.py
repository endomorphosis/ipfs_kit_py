"""
Authentication Service for MCP server.

This module implements the core authentication functionality
as specified in the MCP roadmap for Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
import time
import asyncio
import jwt
import hashlib
import secrets
import ipaddress
from typing import Dict, Any, Optional, Set, Tuple
from .models import (
from .persistence import (

User,
    Role,
    Permission,
    ApiKey,
    Session,
    TokenData,
    LoginRequest,
    RegisterRequest,
    ApiKeyCreateRequest,
    ApiKeyResponse)

    UserStore,
    RoleStore,
    PermissionStore,
    ApiKeyStore,
    SessionStore,
)

# Configure logging
logger = logging.getLogger(__name__)


class AuthenticationService:
    """
    Service providing authentication and user management functionality.

    This service implements the Advanced Authentication & Authorization requirement
    from the MCP roadmap.
    """
    def __init__(
    self,
    secret_key: str
        token_expire_minutes: int = 60,
        refresh_token_expire_days: int = 7,
        password_reset_expire_hours: int = 24,
        api_key_prefix: str = "ipfk_",
    ):
        """
        Initialize the authentication service.

        Args:
            secret_key: Secret key for JWT token signing
            token_expire_minutes: Access token expiration in minutes
            refresh_token_expire_days: Refresh token expiration in days
            password_reset_expire_hours: Password reset token expiration in hours
            api_key_prefix: Prefix for API keys
        """
        self.secret_key = secret_key
        self.token_expire_minutes = token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
        self.password_reset_expire_hours = password_reset_expire_hours
        self.api_key_prefix = api_key_prefix

        # Initialize stores
        self.user_store = UserStore()
        self.role_store = RoleStore()
        self.permission_store = PermissionStore()
        self.api_key_store = ApiKeyStore()
        self.session_store = SessionStore()

        # Active tokens blacklist for immediate revocation
        self.revoked_tokens = set()

        # Cache for frequently accessed data
        self.user_cache = {}
        self.role_cache = {}
        self.permission_cache = {}

        # Rate limiting
        self.login_attempts = {}

        # Boolean to track initialization state
        self.initialized = False

    async def initialize(self):
        """Initialize the authentication service."""
        if self.initialized:
            return

        logger.info("Initializing authentication service")

        # Initialize stores
        await self.user_store.initialize()
        await self.role_store.initialize()
        await self.permission_store.initialize()
        await self.api_key_store.initialize()
        await self.session_store.initialize()

        # Create default roles and permissions if not exist
        await self._create_default_roles()
        await self._create_default_permissions()

        # Start background tasks
        asyncio.create_task(self._cleanup_expired_sessions())
        asyncio.create_task(self._cleanup_cache())

        self.initialized = True
        logger.info("Authentication service initialized")

    async def _create_default_roles(self):
        """Create default roles if they don't exist."""
        default_roles = [
            {
                "name": "admin",
                "description": "Administrator with full access",
                "permissions": {"admin:*"},
            },
            {
                "name": "user",
                "description": "Standard user",
                "permissions": {"storage:read", "storage:list"},
            },
            {"name": "api", "description": "API access", "permissions": {"api:*"}},
            {
                "name": "readonly",
                "description": "Read-only access",
                "permissions": {"storage:read", "storage:list"},
            },
        ]

        for role_data in default_roles:
            # Check if role exists
            existing_role = await self.role_store.get_by_name(role_data["name"])
            if not existing_role:
                # Create role
                role = Role(
                    name=role_data["name"],
                    description=role_data["description"],
                    permissions=role_data["permissions"],
                )
                await self.role_store.create(role.id, role.dict())
                logger.info(f"Created default role: {role.name}")

    async def _create_default_permissions(self):
        """Create default permissions if they don't exist."""
        default_permissions = [
            {
                "name": "admin:*",
                "description": "Full administrative access",
                "resource_type": "all",
                "actions": {"*"},
            },
            {
                "name": "storage:read",
                "description": "Read access to storage",
                "resource_type": "storage",
                "actions": {"read"},
            },
            {
                "name": "storage:write",
                "description": "Write access to storage",
                "resource_type": "storage",
                "actions": {"create", "update", "delete"},
            },
            {
                "name": "storage:list",
                "description": "List storage contents",
                "resource_type": "storage",
                "actions": {"list"},
            },
            {
                "name": "api:*",
                "description": "Full API access",
                "resource_type": "api",
                "actions": {"*"},
            },
            {
                "name": "user:manage",
                "description": "Manage users",
                "resource_type": "user",
                "actions": {"create", "read", "update", "delete", "list"},
            },
        ]

        for perm_data in default_permissions:
            # Check if permission exists
            existing_perm = await self.permission_store.get_by_name(perm_data["name"])
            if not existing_perm:
                # Create permission
                perm = Permission(
                    name=perm_data["name"],
                    description=perm_data["description"],
                    resource_type=perm_data["resource_type"],
                    actions=perm_data["actions"],
                )
                await self.permission_store.create(perm.id, perm.dict())
                logger.info(f"Created default permission: {perm.name}")

    async def _cleanup_expired_sessions(self):
        """Background task to clean up expired sessions."""
        while True:
            try:
                now = time.time()

                # Get all sessions
                sessions = await self.session_store.load_all()

                # Find expired sessions
                expired_count = 0
                for session_id, session in sessions.items():
                    if session.get("expires_at", 0) < now:
                        # Delete expired session
                        await self.session_store.delete(session_id)
                        expired_count += 1

                if expired_count > 0:
                    logger.info(f"Cleaned up {expired_count} expired sessions")
            except Exception as e:
                logger.error(f"Error cleaning up expired sessions: {e}")

            # Sleep for 1 hour before checking again
            await asyncio.sleep(3600)

    async def _cleanup_cache(self):
        """Background task to clean up memory caches."""
        while True:
            try:
                # Clear caches periodically to prevent memory leaks
                self.user_cache.clear()
                self.role_cache.clear()
                self.permission_cache.clear()

                logger.debug("Cleared authentication caches")
            except Exception as e:
                logger.error(f"Error cleaning up caches: {e}")

            # Sleep for 6 hours before clearing again
            await asyncio.sleep(21600)

    def _get_password_hash(self, password: str) -> str:
        """
        Hash a password.

        Args:
            password: Plain password

        Returns:
            Hashed password
        """
        # Use a secure hash algorithm with salt
        salt = secrets.token_hex(8)
        hashed = hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
        return f"{salt}${hashed}"

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against a hash.

        Args:
            plain_password: Plain password
            hashed_password: Hashed password

        Returns:
            True if password is correct
        """
        if not hashed_password or not plain_password:
            return False

        try:
            # Extract salt from hashed password
            salt, stored_hash = hashed_password.split("$", 1)

            # Hash the provided password with the same salt
            computed_hash = hashlib.sha256(f"{plain_password}{salt}".encode()).hexdigest()

            # Compare hashes
            return secrets.compare_digest(computed_hash, stored_hash)
        except Exception as e:
            logger.error(f"Error verifying password: {e}")
            return False

    def _get_api_key_hash(self, api_key: str) -> str:
        """
        Hash an API key.

        Args:
            api_key: Plain API key

        Returns:
            Hashed API key
        """
        # Use a secure hash algorithm with salt
        salt = secrets.token_hex(8)
        hashed = hashlib.sha256(f"{api_key}{salt}".encode()).hexdigest()
        return f"{salt}${hashed}"

    def _verify_api_key(self, plain_key: str, hashed_key: str) -> bool:
        """
        Verify an API key against a hash.

        Args:
            plain_key: Plain API key
            hashed_key: Hashed API key

        Returns:
            True if API key is correct
        """
        if not hashed_key or not plain_key:
            return False

        try:
            # Extract salt from hashed key
            salt, stored_hash = hashed_key.split("$", 1)

            # Hash the provided key with the same salt
            computed_hash = hashlib.sha256(f"{plain_key}{salt}".encode()).hexdigest()

            # Compare hashes
            return secrets.compare_digest(computed_hash, stored_hash)
        except Exception as e:
            logger.error(f"Error verifying API key: {e}")
            return False

    async def register_user(self, request: RegisterRequest) -> Tuple[bool, Optional[User], str]:
        """
        Register a new user.

        Args:
            request: Registration request data

        Returns:
            Tuple of (success, user, message)
        """
        # Check if username exists
        existing_user = await self.user_store.get_by_username(request.username)
        if existing_user:
            return False, None, "Username already taken"

        # Check if email exists
        existing_email = await self.user_store.get_by_email(request.email)
        if existing_email:
            return False, None, "Email already registered"

        # Create user
        user = User(
            username=request.username,
            email=request.email,
            full_name=request.full_name,
            hashed_password=self._get_password_hash(request.password),
            roles={"user"},  # Assign default user role
        )

        # Save user
        success = await self.user_store.create(user.id, user.dict())
        if not success:
            return False, None, "Failed to create user"

        logger.info(f"Registered new user: {user.username} ({user.id})")
        return True, user, "User registered successfully"

    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate a user with username/password.

        Args:
            username: Username or email
            password: Password

        Returns:
            User object if authentication successful, None otherwise
        """
        # Check login attempts for rate limiting
        ip_key = f"login_{username}"
        if ip_key in self.login_attempts:
            attempts, last_attempt = self.login_attempts[ip_key]
            if attempts >= 5 and (time.time() - last_attempt) < 300:
                logger.warning(f"Rate limited login attempt for {username}")
                return None

        # Try to find user by username
        user_dict = await self.user_store.get_by_username(username)

        # If not found, try by email
        if not user_dict and "@" in username:
            user_dict = await self.user_store.get_by_email(username)

        # If still not found, authentication fails
        if not user_dict:
            # Record failed attempt
            if ip_key in self.login_attempts:
                attempts, _ = self.login_attempts[ip_key]
                self.login_attempts[ip_key] = (attempts + 1, time.time())
            else:
                self.login_attempts[ip_key] = (1, time.time())

            logger.warning(f"Authentication failed: user not found {username}")
            return None

        # Verify password
        user = User(**user_dict)
        if not self._verify_password(password, user.hashed_password):
            # Record failed attempt
            if ip_key in self.login_attempts:
                attempts, _ = self.login_attempts[ip_key]
                self.login_attempts[ip_key] = (attempts + 1, time.time())
            else:
                self.login_attempts[ip_key] = (1, time.time())

            logger.warning(f"Authentication failed: incorrect password for {username}")
            return None

        # Check if user is active
        if not user.active:
            logger.warning(f"Authentication failed: user {username} is inactive")
            return None

        # Authentication successful, reset login attempts
        if ip_key in self.login_attempts:
            del self.login_attempts[ip_key]

        # Update last login
        user.last_login = time.time()
        user_dict.update({"last_login": user.last_login})
        await self.user_store.update(user.id, user_dict)

        logger.info(f"User authenticated: {user.username} ({user.id})")
        return user

    async def create_session(
    self,
    user: User
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Session:
        """
        Create a new session for a user.

        Args:
            user: User object
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Session object
        """
        # Create session with expiration
        expires_at = time.time() + (self.token_expire_minutes * 60)

        session = Session(
            user_id=user.id,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Save session
        await self.session_store.create(session.id, session.dict())

        logger.info(f"Created session {session.id} for user {user.username}")
        return session

    async def create_access_token(self, user: User, session: Session) -> str:
        """
        Create a JWT access token.

        Args:
            user: User object
            session: Session object

        Returns:
            JWT token
        """
        # Get user permissions (direct + from roles)
        permissions = await self.get_user_permissions(user.id)

        # Create token data
        token_data = TokenData(
            sub=user.id,
            exp=time.time() + (self.token_expire_minutes * 60),
            iat=time.time(),
            scope="access",
            roles=list(user.roles),
            permissions=list(permissions),
            session_id=session.id,
        )

        # Create JWT token
        token = jwt.encode(token_data.dict(), self.secret_key, algorithm="HS256")

        return token

    async def create_refresh_token(self, user: User, session: Session) -> str:
        """
        Create a JWT refresh token.

        Args:
            user: User object
            session: Session object

        Returns:
            JWT refresh token
        """
        # Create token data
        token_data = TokenData(
            sub=user.id,
            exp=time.time() + (self.refresh_token_expire_days * 86400),
            iat=time.time(),
            scope="refresh",
            roles=list(user.roles),
            session_id=session.id,
        )

        # Create JWT token
        token = jwt.encode(token_data.dict(), self.secret_key, algorithm="HS256")

        return token

    async def verify_token(self, token: str) -> Tuple[bool, Optional[TokenData], str]:
        """
        Verify a JWT token.

        Args:
            token: JWT token

        Returns:
            Tuple of (valid, token_data, error_message)
        """
        try:
            # Check if token is revoked
            if token in self.revoked_tokens:
                return False, None, "Token has been revoked"

            # Decode token
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            token_data = TokenData(**payload)

            # Check if token is expired
            if token_data.exp < time.time():
                return False, None, "Token has expired"

            # If token has a session, check if session is valid
            if token_data.session_id:
                session = await self.session_store.get(token_data.session_id)
                if not session:
                    return False, None, "Session not found"

                # Check if session is expired or inactive
                if session.get("expires_at", 0) < time.time() or not session.get("active", False):
                    return False, None, "Session expired or inactive"

                # Update session last activity
                session["last_activity"] = time.time()
                await self.session_store.update(token_data.session_id, session)

            # For access tokens, verify that the user still has the roles/permissions
            if token_data.scope == "access":
                user = await self.get_user(token_data.sub)
                if not user:
                    return False, None, "User not found"

                if not user.active:
                    return False, None, "User is inactive"

                # Check if roles have changed
                if set(token_data.roles) != set(user.roles):
                    return False, None, "User roles have changed"

            return True, token_data, ""
        except jwt.PyJWTError as e:
            logger.warning(f"JWT token verification failed: {e}")
            return False, None, f"Invalid token: {str(e)}"
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            return False, None, f"Token verification error: {str(e)}"

    async def refresh_access_token(self, refresh_token: str) -> Tuple[bool, Optional[str], str]:
        """
        Refresh an access token using a refresh token.

        Args:
            refresh_token: JWT refresh token

        Returns:
            Tuple of (success, new_access_token, error_message)
        """
        # Verify refresh token
        valid, token_data, error = await self.verify_token(refresh_token)
        if not valid:
            return False, None, error

        # Check if token is a refresh token
        if token_data.scope != "refresh":
            return False, None, "Token is not a refresh token"

        # Get user
        user_dict = await self.user_store.get(token_data.sub)
        if not user_dict:
            return False, None, "User not found"

        user = User(**user_dict)

        # Get session
        session_dict = await self.session_store.get(token_data.session_id)
        if not session_dict:
            return False, None, "Session not found"

        session = Session(**session_dict)

        # Create new access token
        new_token = await self.create_access_token(user, session)

        logger.info(f"Refreshed access token for user {user.username}")
        return True, new_token, ""

    async def revoke_token(self, token: str) -> bool:
        """
        Revoke a token.

        Args:
            token: JWT token

        Returns:
            True if token was revoked
        """
        try:
            # Add to revoked tokens set
            self.revoked_tokens.add(token)

            # Verify token to get data
            valid, token_data, _ = await self.verify_token(token)
            if valid and token_data and token_data.session_id:
                # Invalidate session
                session = await self.session_store.get(token_data.session_id)
                if session:
                    session["active"] = False
                    await self.session_store.update(token_data.session_id, session)
                    logger.info(f"Revoked session {token_data.session_id}")

            return True
        except Exception as e:
            logger.error(f"Error revoking token: {e}")
            return False

    async def revoke_all_user_tokens(self, user_id: str) -> int:
        """
        Revoke all tokens for a user.

        Args:
            user_id: User ID

        Returns:
            Number of sessions revoked
        """
        try:
            # Find all sessions for user
            sessions = await self.session_store.find_by_user(user_id)

            # Invalidate all sessions
            count = 0
            for session_id, session in sessions.items():
                session["active"] = False
                await self.session_store.update(session_id, session)
                count += 1

            logger.info(f"Revoked {count} sessions for user {user_id}")
            return count
        except Exception as e:
            logger.error(f"Error revoking all user tokens: {e}")
            return 0

    async def get_user(self, user_id: str) -> Optional[User]:
        """
        Get a user by ID.

        Args:
            user_id: User ID

        Returns:
            User object or None if not found
        """
        # Check cache first
        if user_id in self.user_cache:
            return self.user_cache[user_id]

        # Get from store
        user_dict = await self.user_store.get(user_id)
        if not user_dict:
            return None

        # Create user object
        user = User(**user_dict)

        # Add to cache
        self.user_cache[user_id] = user

        return user

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Get a user by username.

        Args:
            username: Username

        Returns:
            User object or None if not found
        """
        # Get from store
        user_dict = await self.user_store.get_by_username(username)
        if not user_dict:
            return None

        # Create user object
        user = User(**user_dict)

        # Add to cache
        self.user_cache[user.id] = user

        return user

    async def create_api_key(
        self, user_id: str, request: ApiKeyCreateRequest
    ) -> Tuple[bool, Optional[ApiKeyResponse], str]:
        """
        Create a new API key for a user.

        Args:
            user_id: User ID
            request: API key creation request

        Returns:
            Tuple of (success, api_key, error_message)
        """
        # Get user
        user = await self.get_user(user_id)
        if not user:
            return False, None, "User not found"

        # Calculate expiration timestamp
        expires_at = None
        if request.expires_in_days:
            expires_at = time.time() + (request.expires_in_days * 86400)

        # Generate API key
        key_value = f"{self.api_key_prefix}{secrets.token_hex(16)}"

        # Create API key
        api_key = ApiKey(
            name=request.name,
            key=key_value,
            user_id=user_id,
            hashed_key=self._get_api_key_hash(key_value),
            roles=set(request.roles) if request.roles else set(),
            direct_permissions=set(request.permissions) if request.permissions else set(),
            expires_at=expires_at,
            allowed_ips=request.allowed_ips,
            backend_restrictions=request.backend_restrictions,
        )

        # Save API key
        success = await self.api_key_store.create(api_key.id, api_key.dict())
        if not success:
            return False, None, "Failed to create API key"

        # Create response object with the key (will only be shown once)
        response = ApiKeyResponse(
            id=api_key.id,
            name=api_key.name,
            key=api_key.key,
            expires_at=api_key.expires_at,
            user_id=api_key.user_id,
            created_at=api_key.created_at,
            roles=list(api_key.roles),
            permissions=list(api_key.direct_permissions),
            backend_restrictions=api_key.backend_restrictions,
        )

        logger.info(f"Created API key {api_key.id} for user {user.username}")
        return True, response, "API key created successfully"

    async def verify_api_key(
        self, api_key: str, ip_address: Optional[str] = None
    ) -> Tuple[bool, Optional[ApiKey], str]:
        """
        Verify an API key.

        Args:
            api_key: API key
            ip_address: Client IP address for IP restriction check

        Returns:
            Tuple of (valid, api_key_object, error_message)
        """
        try:
            # Check prefix
            if not api_key.startswith(self.api_key_prefix):
                return False, None, "Invalid API key format"

            # Find API key by prefix
            api_keys = await self.api_key_store.load_all()
            found_key = None

            for key_id, key_data in api_keys.items():
                # Check if key matches
                if self._verify_api_key(api_key, key_data.get("hashed_key", "")):
                    found_key = key_data
                    break

            if not found_key:
                return False, None, "API key not found"

            # Create API key object
            key_obj = ApiKey(**found_key)

            # Check if key is active
            if not key_obj.active:
                return False, None, "API key is inactive"

            # Check if key has expired
            if key_obj.expires_at and key_obj.expires_at < time.time():
                return False, None, "API key has expired"

            # Check IP restrictions
            if key_obj.allowed_ips and ip_address:
                ip_allowed = False
                client_ip = ipaddress.ip_address(ip_address)

                for allowed_ip in key_obj.allowed_ips:
                    if "/" in allowed_ip:
                        # CIDR notation
                        network = ipaddress.ip_network(allowed_ip, strict=False)
                        if client_ip in network:
                            ip_allowed = True
                            break
                    else:
                        # Single IP
                        if ip_address == allowed_ip:
                            ip_allowed = True
                            break

                if not ip_allowed:
                    return False, None, "IP address not allowed for this API key"

            # Update last used timestamp
            found_key["last_used"] = time.time()
            await self.api_key_store.update(key_obj.id, found_key)

            return True, key_obj, ""
        except Exception as e:
            logger.error(f"Error verifying API key: {e}")
            return False, None, f"API key verification error: {str(e)}"

    async def create_access_token_from_api_key(self, api_key: ApiKey) -> str:
        """
        Create a JWT access token from an API key.

        Args:
            api_key: API key object

        Returns:
            JWT token
        """
        # Get user
        await self.get_user(api_key.user_id)

        # Get permissions (direct + from roles)
        permissions = list(api_key.direct_permissions)

        # Add permissions from roles
        for role_name in api_key.roles:
            role = await self.role_store.get_by_name(role_name)
            if role:
                permissions.extend(role.get("permissions", []))

        # Create token data
        token_data = TokenData(
            sub=api_key.user_id,
            exp=time.time() + (self.token_expire_minutes * 60),
            iat=time.time(),
            scope="access",
            roles=list(api_key.roles),
            permissions=permissions,
            is_api_key=True,
            metadata={"api_key_id": api_key.id},
        )

        # Create JWT token
        token = jwt.encode(token_data.dict(), self.secret_key, algorithm="HS256")

        return token

    async def revoke_api_key(self, key_id: str, user_id: str) -> Tuple[bool, str]:
        """
        Revoke an API key.

        Args:
            key_id: API key ID
            user_id: User ID (for authorization check)

        Returns:
            Tuple of (success, message)
        """
        # Get API key
        api_key_dict = await self.api_key_store.get(key_id)
        if not api_key_dict:
            return False, "API key not found"

        # Check if key belongs to user
        if api_key_dict.get("user_id") != user_id:
            return False, "API key does not belong to this user"

        # Deactivate key
        api_key_dict["active"] = False

        # Save changes
        success = await self.api_key_store.update(key_id, api_key_dict)
        if not success:
            return False, "Failed to update API key"

        logger.info(f"Revoked API key {key_id} for user {user_id}")
        return True, "API key revoked successfully"

    async def get_user_permissions(self, user_id: str) -> Set[str]:
        """
        Get all permissions for a user.

        Args:
            user_id: User ID

        Returns:
            Set of permission names
        """
        # Get user
        user = await self.get_user(user_id)
        if not user:
            return set()

        # Start with direct permissions
        permissions = set(user.direct_permissions)

        # Add permissions from roles
        for role_name in user.roles:
            role = await self.role_store.get_by_name(role_name)
            if role:
                permissions.update(role.get("permissions", []))

        return permissions

    async def check_permission(self, user_id: str, required_permission: str) -> bool:
        """
        Check if a user has a specific permission.

        Args:
            user_id: User ID
            required_permission: Permission to check

        Returns:
            True if user has the permission
        """
        # Get user permissions
        permissions = await self.get_user_permissions(user_id)

        # Check for admin permission (wildcard)
        if "admin:*" in permissions:
            return True

        # Check for exact permission
        if required_permission in permissions:
            return True

        # Check for wildcard permissions
        permission_parts = required_permission.split(":")
        if len(permission_parts) > 1:
            resource = permission_parts[0]
            wildcard_perm = f"{resource}:*"
            if wildcard_perm in permissions:
                return True

        return False

    async def check_role(self, user_id: str, required_role: str) -> bool:
        """
        Check if a user has a specific role.

        Args:
            user_id: User ID
            required_role: Role to check

        Returns:
            True if user has the role
        """
        # Get user
        user = await self.get_user(user_id)
        if not user:
            return False

        # Check for admin role
        if "admin" in user.roles:
            return True

        # Check for specific role
        return required_role in user.roles

    async def login(
    self,
    request: LoginRequest
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Login a user and create tokens.

        Args:
            request: Login request
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Tuple of (success, tokens, message)
        """
        # Authenticate user
        user = await self.authenticate_user(request.username, request.password)
        if not user:
            return False, {}, "Invalid username or password"

        # Create session
        session = await self.create_session(user, ip_address, user_agent)

        # Create tokens
        access_token = await self.create_access_token(user, session)
        refresh_token = await self.create_refresh_token(user, session)

        return (
            True,
            {
                "access_token": access_token
                "refresh_token": refresh_token
                "token_type": "bearer",
                "expires_in": self.token_expire_minutes * 60,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "roles": list(user.roles),
                },
            },
            "Login successful",
        )
