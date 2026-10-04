"""
Authentication and Authorization for gRPC Routing Service

This module provides authentication and authorization capabilities for the
gRPC routing service, including:
- JWT-based authentication
- Role-based access control
- API key authentication
- Token validation middleware

These security features ensure that only authorized users and services
can access the routing functionality via gRPC.
"""

import os
import re
import jwt
import time
import json
import logging
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable, Tuple
from pathlib import Path

try:
    import grpc
    import grpc.experimental.aio as grpc_aio
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False
    # Create placeholder for type hints
    class grpc:
        class AuthMetadataContext: pass
        class AuthMetadataPluginCallback: pass
        class ServerInterceptor: pass
    class grpc_aio:
        class ServerInterceptor: pass

# Configure logging
logger = logging.getLogger(__name__)

# Define roles and permissions
ROLES = {
    "admin": {
        "description": "Administrator with full access",
        "permissions": [
            "routing:read",
            "routing:write",
            "routing:admin"
        ]
    },
    "user": {
        "description": "Regular user with basic access",
        "permissions": [
            "routing:read"
        ]
    },
    "service": {
        "description": "Service account for backend integration",
        "permissions": [
            "routing:read",
            "routing:write"
        ]
    }
}

# Map operations to required permissions
OPERATION_PERMISSIONS = {
    "/ipfs_kit_py.routing.RoutingService/SelectBackend": "routing:read",
    "/ipfs_kit_py.routing.RoutingService/RecordOutcome": "routing:write",
    "/ipfs_kit_py.routing.RoutingService/GetInsights": "routing:read",
    "/ipfs_kit_py.routing.RoutingService/StreamMetrics": "routing:read"
}


class User:
    """User representation for authentication and authorization."""
    
    def __init__(
        self,
        username: str,
        role: str,
        api_key: Optional[str] = None,
        hashed_password: Optional[str] = None
    ):
        """
        Initialize a user.
        
        Args:
            username: Username
            role: User role (admin, user, service)
            api_key: Optional API key
            hashed_password: Optional hashed password
        """
        self.username = username
        self.role = role
        self.api_key = api_key
        self.hashed_password = hashed_password
        
        # Get permissions from role
        self.permissions = ROLES.get(role, {}).get("permissions", [])
    
    def has_permission(self, permission: str) -> bool:
        """
        Check if user has a specific permission.
        
        Args:
            permission: Permission to check
            
        Returns:
            True if user has permission, False otherwise
        """
        return permission in self.permissions
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert user to dictionary.
        
        Returns:
            User as dictionary
        """
        return {
            "username": self.username,
            "role": self.role,
            "permissions": self.permissions
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        """
        Create user from dictionary.
        
        Args:
            data: User data
            
        Returns:
            User instance
        """
        return cls(
            username=data.get("username"),
            role=data.get("role", "user"),
            api_key=data.get("api_key"),
            hashed_password=data.get("hashed_password")
        )


class AuthenticationManager:
    """
    Authentication and authorization manager for gRPC routing service.
    
    This class handles user authentication, token validation, and
    permission checking for the gRPC routing service.
    """
    
    def __init__(
        self,
        jwt_secret: Optional[str] = None,
        token_expiry_minutes: int = 60,
        users_file: Optional[str] = None
    ):
        """
        Initialize the authentication manager.
        
        Args:
            jwt_secret: Secret for JWT signing (generated if not provided)
            token_expiry_minutes: Token expiry time in minutes
            users_file: Path to users configuration file
        """
        # Set JWT secret
        self.jwt_secret = jwt_secret or secrets.token_hex(32)
        self.token_expiry_minutes = token_expiry_minutes
        
        # Set users file
        self.users_file = users_file
        
        # Initialize users dictionary
        self.users: Dict[str, User] = {}
        
        # Load users if file is provided
        if users_file:
            self.load_users()
    
    def load_users(self) -> None:
        """Load users from configuration file."""
        if not self.users_file or not os.path.exists(self.users_file):
            logger.warning(f"Users file not found: {self.users_file}")
            return
        
        try:
            with open(self.users_file, "r") as f:
                users_data = json.load(f)
            
            for username, user_data in users_data.items():
                self.users[username] = User.from_dict({
                    "username": username,
                    **user_data
                })
            
            logger.info(f"Loaded {len(self.users)} users from {self.users_file}")
            
        except Exception as e:
            logger.error(f"Error loading users: {e}", exc_info=True)
    
    def save_users(self) -> None:
        """Save users to configuration file."""
        if not self.users_file:
            logger.warning("No users file specified")
            return
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.users_file), exist_ok=True)
            
            # Convert users to dictionaries
            users_data = {}
            for username, user in self.users.items():
                user_dict = {
                    "role": user.role
                }
                if user.api_key:
                    user_dict["api_key"] = user.api_key
                if user.hashed_password:
                    user_dict["hashed_password"] = user.hashed_password
                
                users_data[username] = user_dict
            
            # Write to file
            with open(self.users_file, "w") as f:
                json.dump(users_data, f, indent=2)
            
            logger.info(f"Saved {len(self.users)} users to {self.users_file}")
            
        except Exception as e:
            logger.error(f"Error saving users: {e}", exc_info=True)
    
    def add_user(
        self,
        username: str,
        role: str,
        password: Optional[str] = None,
        generate_api_key: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Add a new user.
        
        Args:
            username: Username
            role: User role
            password: Optional password
            generate_api_key: Whether to generate an API key
            
        Returns:
            Dictionary with user credentials or None if failed
        """
        # Validate role
        if role not in ROLES:
            logger.error(f"Invalid role: {role}")
            return None
        
        # Create user data
        user_data = {
            "username": username,
            "role": role
        }
        
        # Hash password if provided
        if password:
            user_data["hashed_password"] = self._hash_password(password)
        
        # Generate API key if requested
        if generate_api_key:
            api_key = secrets.token_hex(16)
            user_data["api_key"] = api_key
        
        # Create and add user
        user = User.from_dict(user_data)
        self.users[username] = user
        
        # Save users
        self.save_users()
        
        # Return user credentials
        credentials = {
            "username": username,
            "role": role
        }
        if generate_api_key:
            credentials["api_key"] = api_key
        if password:
            credentials["password"] = password
        
        return credentials
    
    def remove_user(self, username: str) -> bool:
        """
        Remove a user.
        
        Args:
            username: Username
            
        Returns:
            True if user was removed, False otherwise
        """
        if username in self.users:
            del self.users[username]
            self.save_users()
            return True
        return False
    
    def _hash_password(self, password: str) -> str:
        """
        Hash a password using SHA-256.
        
        Args:
            password: Password to hash
            
        Returns:
            Hashed password
        """
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, username: str, password: str) -> bool:
        """
        Verify a password for a user.
        
        Args:
            username: Username
            password: Password to verify
            
        Returns:
            True if password is correct, False otherwise
        """
        user = self.users.get(username)
        if not user or not user.hashed_password:
            return False
        
        hashed = self._hash_password(password)
        return hashed == user.hashed_password
    
    def verify_api_key(self, api_key: str) -> Optional[User]:
        """
        Verify an API key.
        
        Args:
            api_key: API key to verify
            
        Returns:
            User if API key is valid, None otherwise
        """
        for user in self.users.values():
            if user.api_key and user.api_key == api_key:
                return user
        return None
    
    def generate_jwt(self, username: str) -> str:
        """
        Generate a JWT token for a user.
        
        Args:
            username: Username
            
        Returns:
            JWT token
        """
        user = self.users.get(username)
        if not user:
            raise ValueError(f"User not found: {username}")
        
        # Create token payload
        now = datetime.utcnow()
        payload = {
            "sub": username,
            "role": user.role,
            "permissions": user.permissions,
            "iat": now,
            "exp": now + timedelta(minutes=self.token_expiry_minutes)
        }
        
        # Sign token
        token = jwt.encode(payload, self.jwt_secret, algorithm="HS256")
        
        return token
    
    def verify_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify a JWT token.
        
        Args:
            token: JWT token
            
        Returns:
            Token payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
    
    def authenticate(
        self,
        metadata: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """
        Authenticate a request from metadata.
        
        This method extracts authentication information from request metadata
        and returns the authenticated user.
        
        Args:
            metadata: Request metadata
            
        Returns:
            User information if authenticated, None otherwise
        """
        # Check for JWT token
        auth_header = metadata.get("authorization", "")
        match = re.match(r"^Bearer\s+(.+)$", auth_header)
        if match:
            token = match.group(1)
            payload = self.verify_jwt(token)
            if payload:
                return payload
        
        # Check for API key
        api_key = metadata.get("x-api-key", "")
        if api_key:
            user = self.verify_api_key(api_key)
            if user:
                return user.to_dict()
        
        # Check for basic auth
        basic_auth = metadata.get("authorization", "")
        match = re.match(r"^Basic\s+(.+)$", basic_auth)
        if match:
            try:
                import base64
                decoded = base64.b64decode(match.group(1)).decode("utf-8")
                username, password = decoded.split(":", 1)
                
                if self.verify_password(username, password):
                    user = self.users.get(username)
                    if user:
                        return user.to_dict()
            except Exception as e:
                logger.warning(f"Error decoding basic auth: {e}")
        
        return None
    
    def has_permission(
        self,
        metadata: Dict[str, str],
        permission: str
    ) -> bool:
        """
        Check if the user has a specific permission.
        
        Args:
            metadata: Request metadata
            permission: Permission to check
            
        Returns:
            True if user has permission, False otherwise
        """
        user_info = self.authenticate(metadata)
        if not user_info:
            return False
        
        # Check permissions
        permissions = user_info.get("permissions", [])
        return permission in permissions


class AuthInterceptor(grpc.ServerInterceptor):
    """
    Server interceptor for authentication and authorization.
    
    This interceptor checks each incoming request for valid authentication
    and ensures the user has the required permissions for the operation.
    """
    
    def __init__(self, auth_manager: AuthenticationManager):
        """
        Initialize the interceptor.
        
        Args:
            auth_manager: Authentication manager
        """
        self.auth_manager = auth_manager
        self._authorized_metadata_plugins = {}
    
    def intercept_service(
        self,
        continuation, 
        handler_call_details
    ):
        """
        Intercept an incoming request.
        
        This method is called for each incoming request and checks
        if the user is authenticated and authorized.
        
        Args:
            continuation: Function to continue processing the request
            handler_call_details: Details about the request
            
        Returns:
            RPC handler or None if not authorized
        """
        # Extract metadata as a dictionary
        metadata = {}
        for key, value in handler_call_details.invocation_metadata:
            metadata[key] = value
        
        # Get required permission for this operation
        method_name = handler_call_details.method
        required_permission = OPERATION_PERMISSIONS.get(method_name)
        
        # If no permission is defined, allow the operation
        if not required_permission:
            return continuation(handler_call_details)
        
        # Check if user has permission
        if self.auth_manager.has_permission(metadata, required_permission):
            return continuation(handler_call_details)
        
        # Reject unauthorized requests
        return None


class AsyncAuthInterceptor(grpc_aio.ServerInterceptor):
    """
    Async server interceptor for authentication and authorization.
    
    This is the async version of AuthInterceptor for use with the
    asynchronous gRPC server.
    """
    
    def __init__(self, auth_manager: AuthenticationManager):
        """
        Initialize the interceptor.
        
        Args:
            auth_manager: Authentication manager
        """
        self.auth_manager = auth_manager
    
    async def intercept_service(
        self,
        continuation, 
        handler_call_details
    ):
        """
        Intercept an incoming request.
        
        This method is called for each incoming request and checks
        if the user is authenticated and authorized.
        
        Args:
            continuation: Function to continue processing the request
            handler_call_details: Details about the request
            
        Returns:
            RPC handler or None if not authorized
        """
        # Extract metadata as a dictionary
        metadata = {}
        for key, value in handler_call_details.invocation_metadata:
            metadata[key] = value
        
        # Get required permission for this operation
        method_name = handler_call_details.method
        required_permission = OPERATION_PERMISSIONS.get(method_name)
        
        # If no permission is defined, allow the operation
        if not required_permission:
            return await continuation(handler_call_details)
        
        # Check if user has permission
        if self.auth_manager.has_permission(metadata, required_permission):
            return await continuation(handler_call_details)
        
        # Reject unauthorized requests
        return None


class JWTAuthMetadataPlugin:
    """
    Client-side plugin to add JWT authentication to requests.
    
    This plugin automatically adds authentication metadata to each request.
    """
    
    def __init__(self, token: str):
        """
        Initialize the plugin.
        
        Args:
            token: JWT token
        """
        self.token = token
    
    def __call__(
        self,
        context: grpc.AuthMetadataContext,
        callback: grpc.AuthMetadataPluginCallback
    ):
        """
        Add authentication metadata to a request.
        
        Args:
            context: Auth metadata context
            callback: Callback to add metadata
        """
        callback((("authorization", f"Bearer {self.token}"),), None)


class APIKeyAuthMetadataPlugin:
    """
    Client-side plugin to add API key authentication to requests.
    
    This plugin automatically adds an API key to each request.
    """
    
    def __init__(self, api_key: str):
        """
        Initialize the plugin.
        
        Args:
            api_key: API key
        """
        self.api_key = api_key
    
    def __call__(
        self,
        context: grpc.AuthMetadataContext,
        callback: grpc.AuthMetadataPluginCallback
    ):
        """
        Add API key to a request.
        
        Args:
            context: Auth metadata context
            callback: Callback to add metadata
        """
        callback((("x-api-key", self.api_key),), None)


class BasicAuthMetadataPlugin:
    """
    Client-side plugin to add Basic authentication to requests.
    
    This plugin automatically adds Basic authentication to each request.
    """
    
    def __init__(self, username: str, password: str):
        """
        Initialize the plugin.
        
        Args:
            username: Username
            password: Password
        """
        self.username = username
        self.password = password
    
    def __call__(
        self,
        context: grpc.AuthMetadataContext,
        callback: grpc.AuthMetadataPluginCallback
    ):
        """
        Add Basic authentication to a request.
        
        Args:
            context: Auth metadata context
            callback: Callback to add metadata
        """
        import base64
        auth_string = f"{self.username}:{self.password}"
        encoded = base64.b64encode(auth_string.encode()).decode()
        callback((("authorization", f"Basic {encoded}"),), None)


def create_jwt_auth_interceptor(
    token: str
) -> grpc.UnaryUnaryClientInterceptor:
    """
    Create a client interceptor for JWT authentication.
    
    Args:
        token: JWT token
        
    Returns:
        Client interceptor
    """
    plugin = JWTAuthMetadataPlugin(token)
    return grpc.metadata_call_credentials(plugin)


def create_api_key_auth_interceptor(
    api_key: str
) -> grpc.UnaryUnaryClientInterceptor:
    """
    Create a client interceptor for API key authentication.
    
    Args:
        api_key: API key
        
    Returns:
        Client interceptor
    """
    plugin = APIKeyAuthMetadataPlugin(api_key)
    return grpc.metadata_call_credentials(plugin)


def create_basic_auth_interceptor(
    username: str,
    password: str
) -> grpc.UnaryUnaryClientInterceptor:
    """
    Create a client interceptor for Basic authentication.
    
    Args:
        username: Username
        password: Password
        
    Returns:
        Client interceptor
    """
    plugin = BasicAuthMetadataPlugin(username, password)
    return grpc.metadata_call_credentials(plugin)


def secure_channel_credentials(
    jwt_token: Optional[str] = None,
    api_key: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    ssl_credentials: Optional[grpc.ChannelCredentials] = None
) -> grpc.ChannelCredentials:
    """
    Create secure channel credentials with authentication.
    
    Args:
        jwt_token: Optional JWT token
        api_key: Optional API key
        username: Optional username for Basic auth
        password: Optional password for Basic auth
        ssl_credentials: Optional SSL credentials
        
    Returns:
        Secure channel credentials
    """
    # Create list of call credentials
    call_credentials_list = []
    
    if jwt_token:
        call_credentials_list.append(create_jwt_auth_interceptor(jwt_token))
    
    if api_key:
        call_credentials_list.append(create_api_key_auth_interceptor(api_key))
    
    if username and password:
        call_credentials_list.append(create_basic_auth_interceptor(username, password))
    
    # Combine call credentials
    if call_credentials_list:
        call_credentials = call_credentials_list[0]
        for creds in call_credentials_list[1:]:
            call_credentials = grpc.composite_call_credentials(call_credentials, creds)
    else:
        return ssl_credentials or grpc.local_channel_credentials()
    
    # Combine with SSL credentials
    if ssl_credentials:
        return grpc.composite_channel_credentials(ssl_credentials, call_credentials)
    
    # Use local credentials if no SSL
    return grpc.composite_channel_credentials(
        grpc.local_channel_credentials(),
        call_credentials
    )