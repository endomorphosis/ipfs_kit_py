"""
API Key Management System

This module provides a comprehensive API key management system that allows users
to create, manage, and revoke API keys with specific permissions for programmatic access.

Part of the MCP Roadmap Phase 1: Advanced Authentication & Authorization.
"""

import os
import json
import time
import logging
import secrets
import hashlib
import base64
from typing import Dict, List, Optional, Union, Any
from enum import Enum
from datetime import datetime, timedelta
import re
import asyncio
import sqlite3
from pathlib import Path

from fastapi import Depends, HTTPException, status, Request, Response, Header, APIRouter
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer

from ..auth.models import User, Role, Permission
from ..rbac import rbac_manager, has_permission, check_permission
from .backend_authorization_integration import BackendPermission, get_backend_auth

# Configure logging
logger = logging.getLogger("mcp.auth.apikey")

# API Key header
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


class ApiKeyScope(str, Enum):
    """Scope of an API key"""
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    FULL_ACCESS = "full_access"
    CUSTOM = "custom"


class ApiKeyStatus(str, Enum):
    """Status of an API key"""
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    DISABLED = "disabled"


class ApiKeyManager:
    """
    API Key Management System for the MCP server.
    
    Features:
    - Key generation with customizable permissions
    - Scoped access for specific backends
    - Per-key usage statistics
    - Rate limiting
    - Automatic expiration
    - Audit logging
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the API key manager.
        
        Args:
            db_path: Path to SQLite database for key storage
        """
        # Set database path
        if db_path:
            self.db_path = db_path
        else:
            data_dir = os.environ.get(
                "MCP_DATA_DIR", 
                os.path.join(os.path.expanduser("~"), ".ipfs_kit")
            )
            Path(data_dir).mkdir(exist_ok=True)
            self.db_path = os.path.join(data_dir, "apikeys.db")
        
        # Cache for API key lookups
        self.key_cache: Dict[str, Dict[str, Any]] = {}
        self.key_cache_ttl = 300  # 5 minutes
        
        # Initialize database
        self._init_db()
        
        # Load settings
        self.settings = {
            "default_key_expiry_days": 90,
            "max_keys_per_user": 10,
            "key_rate_limit": 1000,  # requests per hour
            "enable_rate_limiting": False
        }
        
        # Rate limiting counters
        self.rate_counters: Dict[str, Dict[str, Any]] = {}
        
        # Usage statistics
        self.usage_stats: Dict[str, Dict[str, int]] = {}
        
        logger.info(f"API Key Manager initialized with database at {self.db_path}")
    
    def _init_db(self):
        """Initialize the SQLite database for API key storage."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create API keys table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    key_hash TEXT UNIQUE,
                    name TEXT,
                    user_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    last_used_at TIMESTAMP,
                    scope TEXT,
                    status TEXT,
                    usage_count INTEGER DEFAULT 0,
                    metadata TEXT
                )
                ''')
                
                # Create API key permissions table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS api_key_permissions (
                    key_id TEXT,
                    permission TEXT,
                    backend TEXT,
                    FOREIGN KEY (key_id) REFERENCES api_keys(id),
                    PRIMARY KEY (key_id, permission, backend)
                )
                ''')
                
                # Create API key usage log table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS api_key_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_id TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    endpoint TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    status_code INTEGER,
                    FOREIGN KEY (key_id) REFERENCES api_keys(id)
                )
                ''')
                
                conn.commit()
                logger.info("API key database initialized")
                
        except Exception as e:
            logger.error(f"Error initializing API key database: {e}")
            raise
    
    def _hash_key(self, api_key: str) -> str:
        """
        Hash an API key for secure storage.
        
        Args:
            api_key: Raw API key
            
        Returns:
            Hashed key
        """
        # Use SHA-256 for key hashing
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    def _generate_key(self) -> str:
        """
        Generate a cryptographically secure API key.
        
        Returns:
            Generated API key
        """
        # Generate a 32-byte random token
        token = secrets.token_bytes(32)
        
        # Encode as URL-safe base64
        key = base64.urlsafe_b64encode(token).decode().rstrip('=')
        
        # Add a prefix for easy identification
        return f"mcp_{key}"
    
    def _key_from_cache(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Get API key info from cache.
        
        Args:
            api_key: API key to look up
            
        Returns:
            API key data dict if found and valid, None otherwise
        """
        # Check if key is in cache
        key_hash = self._hash_key(api_key)
        
        if key_hash in self.key_cache:
            cache_entry = self.key_cache[key_hash]
            
            # Check if cache entry is still valid
            if time.time() - cache_entry['cache_time'] < self.key_cache_ttl:
                return cache_entry['data']
            
            # Cache entry expired, remove it
            del self.key_cache[key_hash]
        
        return None
    
    def _store_key_in_cache(self, api_key: str, key_data: Dict[str, Any]):
        """
        Store API key info in cache.
        
        Args:
            api_key: API key
            key_data: API key data to cache
        """
        key_hash = self._hash_key(api_key)
        
        self.key_cache[key_hash] = {
            'data': key_data,
            'cache_time': time.time()
        }
    
    async def create_key(self, user_id: str, name: str, 
                        permissions: Optional[List[str]] = None,
                        backend_permissions: Optional[Dict[str, List[str]]] = None,
                        scope: ApiKeyScope = ApiKeyScope.READ_ONLY,
                        expires_in_days: Optional[int] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new API key.
        
        Args:
            user_id: User ID who owns this key
            name: Name/description of the key
            permissions: List of permission strings (if scope is CUSTOM)
            backend_permissions: Dict of backend names to permission lists
            scope: API key scope
            expires_in_days: Days until key expires (default from settings)
            metadata: Additional metadata for the key
            
        Returns:
            Dict with key information including the raw key (displayed only once)
        """
        # Check if user has reached maximum key limit
        keys = await self.list_keys(user_id)
        if len(keys) >= self.settings["max_keys_per_user"]:
            raise ValueError(f"User has reached maximum API key limit ({self.settings['max_keys_per_user']})")
        
        # Generate key and ID
        api_key = self._generate_key()
        key_id = base64.urlsafe_b64encode(os.urandom(16)).decode().rstrip('=')
        key_hash = self._hash_key(api_key)
        
        # Set expiration if provided, otherwise use default
        if expires_in_days is None:
            expires_in_days = self.settings["default_key_expiry_days"]
        
        expires_at = (datetime.now() + timedelta(days=expires_in_days)).isoformat() if expires_in_days else None
        
        # Serialize metadata
        metadata_json = json.dumps(metadata) if metadata else None
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Add key to database
                cursor.execute('''
                INSERT INTO api_keys 
                (id, key_hash, name, user_id, expires_at, scope, status, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    key_id, key_hash, name, user_id, expires_at, 
                    scope.value, ApiKeyStatus.ACTIVE.value, metadata_json
                ))
                
                # Add permissions if scope is CUSTOM
                if scope == ApiKeyScope.CUSTOM and permissions:
                    for permission in permissions:
                        cursor.execute('''
                        INSERT INTO api_key_permissions
                        (key_id, permission, backend)
                        VALUES (?, ?, 'global')
                        ''', (key_id, permission))
                
                # Add backend-specific permissions
                if backend_permissions:
                    for backend, perms in backend_permissions.items():
                        for permission in perms:
                            cursor.execute('''
                            INSERT INTO api_key_permissions
                            (key_id, permission, backend)
                            VALUES (?, ?, ?)
                            ''', (key_id, permission, backend))
                
                conn.commit()
                
                # Get the created key
                cursor.execute('''
                SELECT * FROM api_keys WHERE id = ?
                ''', (key_id,))
                
                key_data = dict(cursor.fetchone())
                
                # Fetch permissions
                cursor.execute('''
                SELECT permission, backend FROM api_key_permissions
                WHERE key_id = ?
                ''', (key_id,))
                
                perms = cursor.fetchall()
                key_permissions = {}
                
                for perm in perms:
                    backend = perm['backend']
                    if backend not in key_permissions:
                        key_permissions[backend] = []
                    key_permissions[backend].append(perm['permission'])
                
                key_data['permissions'] = key_permissions
                
                # Add the raw key to the result (only time it's available in plaintext)
                key_data['key'] = api_key
                
                logger.info(f"Created API key '{name}' for user {user_id} with scope {scope.value}")
                
                return key_data
                
        except Exception as e:
            logger.error(f"Error creating API key: {e}")
            raise
    
    async def get_key_info(self, api_key: str, check_valid: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get information about an API key.
        
        Args:
            api_key: API key
            check_valid: Whether to check if key is valid (not revoked/expired)
            
        Returns:
            API key data or None if not found
        """
        # Check cache first
        key_data = self._key_from_cache(api_key)
        if key_data:
            # Perform validation check if required
            if check_valid:
                if key_data['status'] != ApiKeyStatus.ACTIVE.value:
                    return None
                
                # Check expiration
                if key_data.get('expires_at'):
                    expires_at = datetime.fromisoformat(key_data['expires_at'])
                    if expires_at < datetime.now():
                        # Update status to EXPIRED
                        await self.update_key_status(key_data['id'], ApiKeyStatus.EXPIRED)
                        return None
            
            return key_data
        
        # Look up key in database
        key_hash = self._hash_key(api_key)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT * FROM api_keys WHERE key_hash = ?
                ''', (key_hash,))
                
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                key_data = dict(row)
                
                # Fetch permissions
                cursor.execute('''
                SELECT permission, backend FROM api_key_permissions
                WHERE key_id = ?
                ''', (key_data['id'],))
                
                perms = cursor.fetchall()
                key_permissions = {}
                
                for perm in perms:
                    backend = perm['backend']
                    if backend not in key_permissions:
                        key_permissions[backend] = []
                    key_permissions[backend].append(perm['permission'])
                
                key_data['permissions'] = key_permissions
                
                # Validate key if requested
                if check_valid:
                    if key_data['status'] != ApiKeyStatus.ACTIVE.value:
                        return None
                    
                    # Check expiration
                    if key_data.get('expires_at'):
                        expires_at = datetime.fromisoformat(key_data['expires_at'])
                        if expires_at < datetime.now():
                            # Update status to EXPIRED
                            await self.update_key_status(key_data['id'], ApiKeyStatus.EXPIRED)
                            return None
                
                # Store in cache for future lookups
                self._store_key_in_cache(api_key, key_data)
                
                return key_data
                
        except Exception as e:
            logger.error(f"Error getting API key info: {e}")
            return None
    
    async def validate_key(self, api_key: str, required_permission: Optional[str] = None,
                        backend: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate an API key and check permissions.
        
        Args:
            api_key: API key to validate
            required_permission: Optional permission to check
            backend: Optional backend name for backend-specific permission
            
        Returns:
            Dict with validation results
        """
        if not api_key:
            return {
                "valid": False,
                "reason": "No API key provided"
            }
        
        # Get key info
        key_info = await self.get_key_info(api_key)
        
        if not key_info:
            return {
                "valid": False,
                "reason": "Invalid, expired, or revoked API key"
            }
        
        # Check rate limiting if enabled
        if self.settings["enable_rate_limiting"]:
            rate_limited = self._check_rate_limit(key_info['id'])
            if rate_limited:
                return {
                    "valid": False,
                    "reason": "Rate limit exceeded",
                    "key_id": key_info['id'],
                    "user_id": key_info['user_id']
                }
        
        # If no permission check needed, key is valid
        if not required_permission:
            return {
                "valid": True,
                "key_id": key_info['id'],
                "user_id": key_info['user_id'],
                "scope": key_info['scope']
            }
        
        # Check permission based on scope
        has_perm = False
        
        # Full access always has permission
        if key_info['scope'] == ApiKeyScope.FULL_ACCESS.value:
            has_perm = True
        
        # Read-only scope can only perform read operations
        elif key_info['scope'] == ApiKeyScope.READ_ONLY.value:
            has_perm = required_permission.startswith('read:') or required_permission == 'read'
        
        # Read-write scope can perform read and write operations
        elif key_info['scope'] == ApiKeyScope.READ_WRITE.value:
            has_perm = required_permission.startswith('read:') or required_permission == 'read' or \
                      required_permission.startswith('write:') or required_permission == 'write'
        
        # Custom scope checks specific permissions
        elif key_info['scope'] == ApiKeyScope.CUSTOM.value:
            perms = key_info.get('permissions', {})
            
            # Check backend-specific permission first
            if backend and backend in perms and required_permission in perms[backend]:
                has_perm = True
            # Then check global permissions
            elif 'global' in perms and required_permission in perms['global']:
                has_perm = True
        
        # Update usage stats
        await self._update_key_usage(key_info['id'])
        
        if has_perm:
            return {
                "valid": True,
                "key_id": key_info['id'],
                "user_id": key_info['user_id'],
                "scope": key_info['scope']
            }
        else:
            return {
                "valid": False,
                "reason": f"Missing required permission: {required_permission}",
                "key_id": key_info['id'],
                "user_id": key_info['user_id']
            }
    
    def _check_rate_limit(self, key_id: str) -> bool:
        """
        Check if an API key has exceeded its rate limit.
        
        Args:
            key_id: API key ID
            
        Returns:
            True if rate limited, False otherwise
        """
        # Get current hour timestamp (floor to hour)
        current_hour = int(time.time()) // 3600 * 3600
        
        # Initialize counter if needed
        if key_id not in self.rate_counters or self.rate_counters[key_id]['hour'] != current_hour:
            self.rate_counters[key_id] = {
                'hour': current_hour,
                'count': 0
            }
        
        # Check limit
        if self.rate_counters[key_id]['count'] >= self.settings["key_rate_limit"]:
            return True
        
        # Increment counter
        self.rate_counters[key_id]['count'] += 1
        return False
    
    async def _update_key_usage(self, key_id: str):
        """
        Update usage statistics for an API key.
        
        Args:
            key_id: API key ID
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Update last used timestamp and increment usage count
                cursor.execute('''
                UPDATE api_keys
                SET last_used_at = CURRENT_TIMESTAMP,
                    usage_count = usage_count + 1
                WHERE id = ?
                ''', (key_id,))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error updating API key usage: {e}")
    
    async def log_key_usage(self, key_id: str, endpoint: str, ip_address: str, 
                          user_agent: str, status_code: int):
        """
        Log API key usage for audit purposes.
        
        Args:
            key_id: API key ID
            endpoint: API endpoint accessed
            ip_address: Client IP address
            user_agent: Client User-Agent string
            status_code: HTTP status code of response
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                INSERT INTO api_key_usage
                (key_id, endpoint, ip_address, user_agent, status_code)
                VALUES (?, ?, ?, ?, ?)
                ''', (key_id, endpoint, ip_address, user_agent, status_code))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error logging API key usage: {e}")
    
    async def list_keys(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List API keys, optionally filtered by user.
        
        Args:
            user_id: Optional user ID to filter by
            
        Returns:
            List of API key data dictionaries
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if user_id:
                    cursor.execute('''
                    SELECT * FROM api_keys WHERE user_id = ?
                    ORDER BY created_at DESC
                    ''', (user_id,))
                else:
                    cursor.execute('''
                    SELECT * FROM api_keys
                    ORDER BY created_at DESC
                    ''')
                
                rows = cursor.fetchall()
                result = []
                
                for row in rows:
                    key_data = dict(row)
                    
                    # Fetch permissions
                    cursor.execute('''
                    SELECT permission, backend FROM api_key_permissions
                    WHERE key_id = ?
                    ''', (key_data['id'],))
                    
                    perms = cursor.fetchall()
                    key_permissions = {}
                    
                    for perm in perms:
                        backend = perm['backend']
                        if backend not in key_permissions:
                            key_permissions[backend] = []
                        key_permissions[backend].append(perm['permission'])
                    
                    key_data['permissions'] = key_permissions
                    
                    # Parse metadata if present
                    if key_data.get('metadata'):
                        try:
                            key_data['metadata'] = json.loads(key_data['metadata'])
                        except:
                            key_data['metadata'] = {}
                    
                    result.append(key_data)
                
                return result
                
        except Exception as e:
            logger.error(f"Error listing API keys: {e}")
            return []
    
    async def update_key_status(self, key_id: str, status: ApiKeyStatus) -> bool:
        """
        Update an API key's status.
        
        Args:
            key_id: API key ID
            status: New status
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                UPDATE api_keys
                SET status = ?
                WHERE id = ?
                ''', (status.value, key_id))
                
                conn.commit()
                
                # Clear cache entries for this key
                for k in list(self.key_cache.keys()):
                    if self.key_cache[k]['data'].get('id') == key_id:
                        del self.key_cache[k]
                
                logger.info(f"Updated API key {key_id} status to {status.value}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating API key status: {e}")
            return False
    
    async def revoke_key(self, key_id: str) -> bool:
        """
        Revoke an API key.
        
        Args:
            key_id: API key ID
            
        Returns:
            True if successful, False otherwise
        """
        return await self.update_key_status(key_id, ApiKeyStatus.REVOKED)
    
    async def delete_key(self, key_id: str) -> bool:
        """
        Permanently delete an API key.
        
        Args:
            key_id: API key ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete permissions
                cursor.execute('''
                DELETE FROM api_key_permissions
                WHERE key_id = ?
                ''', (key_id,))
                
                # Delete usage logs
                cursor.execute('''
                DELETE FROM api_key_usage
                WHERE key_id = ?
                ''', (key_id,))
                
                # Delete key
                cursor.execute('''
                DELETE FROM api_keys
                WHERE id = ?
                ''', (key_id,))
                
                conn.commit()
                
                # Clear cache entries for this key
                for k in list(self.key_cache.keys()):
                    if self.key_cache[k]['data'].get('id') == key_id:
                        del self.key_cache[k]
                
                logger.info(f"Deleted API key {key_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting API key: {e}")
            return False
    
    async def update_key_permissions(self, key_id: str, 
                                  permissions: Optional[List[str]] = None,
                                  backend_permissions: Optional[Dict[str, List[str]]] = None) -> bool:
        """
        Update permissions for an API key.
        
        Args:
            key_id: API key ID
            permissions: List of global permissions
            backend_permissions: Dict of backend-specific permissions
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete existing permissions
                cursor.execute('''
                DELETE FROM api_key_permissions
                WHERE key_id = ?
                ''', (key_id,))
                
                # Add global permissions
                if permissions:
                    for permission in permissions:
                        cursor.execute('''
                        INSERT INTO api_key_permissions
                        (key_id, permission, backend)
                        VALUES (?, ?, 'global')
                        ''', (key_id, permission))
                
                # Add backend permissions
                if backend_permissions:
                    for backend, perms in backend_permissions.items():
                        for permission in perms:
                            cursor.execute('''
                            INSERT INTO api_key_permissions
                            (key_id, permission, backend)
                            VALUES (?, ?, ?)
                            ''', (key_id, permission, backend))
                
                # Update key scope to CUSTOM if permissions are specified
                if permissions or backend_permissions:
                    cursor.execute('''
                    UPDATE api_keys
                    SET scope = ?
                    WHERE id = ?
                    ''', (ApiKeyScope.CUSTOM.value, key_id))
                
                conn.commit()
                
                # Clear cache entries for this key
                for k in list(self.key_cache.keys()):
                    if self.key_cache[k]['data'].get('id') == key_id:
                        del self.key_cache[k]
                
                logger.info(f"Updated permissions for API key {key_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating API key permissions: {e}")
            return False
    
    async def get_key_usage_logs(self, key_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get usage logs for an API key.
        
        Args:
            key_id: API key ID
            limit: Maximum number of logs to return
            
        Returns:
            List of usage log entries
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT * FROM api_key_usage
                WHERE key_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                ''', (key_id, limit))
                
                rows = cursor.fetchall()
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting API key usage logs: {e}")
            return []
    
    async def get_user_from_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Get user information from an API key.
        
        Args:
            api_key: API key
            
        Returns:
            User information or None if key is invalid
        """
        key_info = await self.get_key_info(api_key)
        
        if not key_info:
            return None
        
        from ..auth.service import get_user_by_id
        user = await get_user_by_id(key_info['user_id'])
        
        if not user:
            return None
        
        # Return user info along with key scope
        return {
            "user": user,
            "key_id": key_info['id'],
            "scope": key_info['scope'],
            "permissions": key_info.get('permissions', {})
        }


# Singleton instance
_api_key_manager_instance = None

def get_api_key_manager() -> ApiKeyManager:
    """Get the singleton API key manager instance."""
    global _api_key_manager_instance
    if _api_key_manager_instance is None:
        _api_key_manager_instance = ApiKeyManager()
    return _api_key_manager_instance


# API Key Authentication

async def get_api_key_user(
    api_key: str = Depends(api_key_header),
    require_auth: bool = True
) -> Optional[User]:
    """
    Get a user from an API key.
    
    Args:
        api_key: API key from header
        require_auth: Whether to raise an exception if authentication fails
        
    Returns:
        User object if authenticated, None otherwise
        
    Raises:
        HTTPException: If authentication fails and require_auth is True
    """
    if not api_key:
        if require_auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required"
            )
        return None
    
    # Get API key manager
    api_key_manager = get_api_key_manager()
    
    # Get user from key
    user_info = await api_key_manager.get_user_from_key(api_key)
    
    if not user_info:
        if require_auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        return None
    
    # Enhance user object with API key information
    user = user_info["user"]
    
    # Add API key context to the user object
    user.api_key_context = {
        "key_id": user_info["key_id"],
        "scope": user_info["scope"],
        "permissions": user_info["permissions"]
    }
    
    return user


# API Key middleware
async def api_key_middleware(request: Request, call_next):
    """
    Middleware to handle API key authentication.
    
    This middleware checks for API keys in the request header and validates them.
    If a valid API key is found, the user is authenticated without needing
    a JWT token or other authentication method.
    
    Args:
        request: Request object
        call_next: Next middleware or endpoint handler
        
    Returns:
        Response from next middleware or endpoint
    """
    # Check if this is a route that should be protected
    path = request.url.path
    
    # Skip authentication for certain paths
    skip_paths = [
        "/health",
        "/api/v0/status",
        "/api/v0/auth/login",
        "/api/v0/auth/register",
        "/api/v0/auth/refresh",
        "/docs",
        "/redoc",
        "/openapi.json"
    ]
    
    # Extract API key from header
    api_key = request.headers.get(API_KEY_NAME)
    
    # If no API key and path doesn't need auth, just continue
    if not api_key and any(path.startswith(p) for p in skip_paths):
        return await call_next(request)
    
    # If there's an API key, validate it
    if api_key:
        # Get API key manager
        api_key_manager = get_api_key_manager()
        
        # Validate key (without checking specific permissions here)
        validation = await api_key_manager.validate_key(api_key)
        
        if validation["valid"]:
            # Get user information from key
            user_info = await api_key_manager.get_user_from_key(api_key)
            
            if user_info:
                # Store user and key info in request state for endpoints to access
                request.state.api_key_user = user_info["user"]
                request.state.api_key = {
                    "key_id": user_info["key_id"],
                    "scope": user_info["scope"],
                    "permissions": user_info["permissions"]
                }
                
                # Get client information for logging
                client_host = request.client.host if request.client else "unknown"
                user_agent = request.headers.get("User-Agent", "unknown")
                
                # Record key usage asynchronously (don't wait for it)
                asyncio.create_task(
                    api_key_manager.log_key_usage(
                        user_info["key_id"],
                        path,
                        client_host,
                        user_agent,
                        200  # This will be updated after the response if possible
                    )
                )
    
    # Continue processing the request
    response = await call_next(request)
    
    # Update status code in key usage if API key was used
    if api_key and hasattr(request.state, "api_key") and request.state.api_key:
        api_key_manager = get_api_key_manager()
        key_id = request.state.api_key["key_id"]
        
        # Update status code in the last log entry
        client_host = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("User-Agent", "unknown")
        
        asyncio.create_task(
            api_key_manager.log_key_usage(
                key_id,
                path,
                client_host,
                user_agent,
                response.status_code
            )
        )
    
    return response


# Create API router
def create_api_key_router(get_current_admin_user=None) -> APIRouter:
    """
    Create an API router for API key management.
    
    Args:
        get_current_admin_user: Function to get the current admin user
        
    Returns:
        Configured APIRouter
    """
    router = APIRouter(prefix="/api/v0/auth/apikeys", tags=["API Keys"])
    
    # Get API key manager
    api_key_manager = get_api_key_manager()
    
    from ..auth.router import get_current_user
    
    @router.post("/create")
    async def create_api_key(
        name: str,
        scope: ApiKeyScope = ApiKeyScope.READ_ONLY,
        expires_in_days: Optional[int] = None,
        permissions: Optional[List[str]] = None,
        backend_permissions: Optional[Dict[str, List[str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        current_user: User = Depends(get_current_user)
    ):
        """Create a new API key."""
        try:
            # Only allow CUSTOM scope if permissions are provided
            if scope == ApiKeyScope.CUSTOM and not (permissions or backend_permissions):
                return {
                    "success": False,
                    "message": "Custom scope requires permissions"
                }
            
            # Create key
            key_data = await api_key_manager.create_key(
                user_id=current_user.id,
                name=name,
                permissions=permissions,
                backend_permissions=backend_permissions,
                scope=scope,
                expires_in_days=expires_in_days,
                metadata=metadata
            )
            
            return {
                "success": True,
                "message": "API key created",
                "data": key_data
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error creating API key: {str(e)}"
            }
    
    @router.get("/list")
    async def list_api_keys(
        current_user: User = Depends(get_current_user)
    ):
        """List API keys for the current user."""
        # Admins can list all keys with a query parameter
        all_keys = False
        if current_user.role in [Role.ADMIN, Role.SYSTEM]:
            all_keys = True
        
        try:
            if all_keys:
                keys = await api_key_manager.list_keys()
            else:
                keys = await api_key_manager.list_keys(current_user.id)
            
            # Remove sensitive data
            for key in keys:
                if 'key_hash' in key:
                    del key['key_hash']
            
            return {
                "success": True,
                "message": "API keys retrieved",
                "data": keys
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error listing API keys: {str(e)}"
            }
    
    @router.delete("/{key_id}")
    async def revoke_api_key(
        key_id: str,
        current_user: User = Depends(get_current_user)
    ):
        """Revoke an API key."""
        try:
            # Check if the key belongs to the user unless admin
            if current_user.role not in [Role.ADMIN, Role.SYSTEM]:
                keys = await api_key_manager.list_keys(current_user.id)
                if not any(k['id'] == key_id for k in keys):
                    return {
                        "success": False,
                        "message": "API key not found or doesn't belong to you"
                    }
            
            # Revoke key
            success = await api_key_manager.revoke_key(key_id)
            
            if success:
                return {
                    "success": True,
                    "message": "API key revoked"
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to revoke API key"
                }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error revoking API key: {str(e)}"
            }
    
    @router.put("/{key_id}/permissions")
    async def update_api_key_permissions(
        key_id: str,
        permissions: Optional[List[str]] = None,
        backend_permissions: Optional[Dict[str, List[str]]] = None,
        current_user: User = Depends(get_current_user)
    ):
        """Update permissions for an API key."""
        try:
            # Check if the key belongs to the user unless admin
            if current_user.role not in [Role.ADMIN, Role.SYSTEM]:
                keys = await api_key_manager.list_keys(current_user.id)
                if not any(k['id'] == key_id for k in keys):
                    return {
                        "success": False,
                        "message": "API key not found or doesn't belong to you"
                    }
            
            # Update permissions
            success = await api_key_manager.update_key_permissions(
                key_id=key_id,
                permissions=permissions,
                backend_permissions=backend_permissions
            )
            
            if success:
                return {
                    "success": True,
                    "message": "API key permissions updated"
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to update API key permissions"
                }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error updating API key permissions: {str(e)}"
            }
    
    @router.get("/{key_id}/usage")
    async def get_api_key_usage(
        key_id: str,
        limit: int = 100,
        current_user: User = Depends(get_current_user)
    ):
        """Get usage logs for an API key."""
        try:
            # Check if the key belongs to the user unless admin
            if current_user.role not in [Role.ADMIN, Role.SYSTEM]:
                keys = await api_key_manager.list_keys(current_user.id)
                if not any(k['id'] == key_id for k in keys):
                    return {
                        "success": False,
                        "message": "API key not found or doesn't belong to you"
                    }
            
            # Get usage logs
            logs = await api_key_manager.get_key_usage_logs(key_id, limit)
            
            return {
                "success": True,
                "message": "API key usage logs retrieved",
                "data": logs
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error getting API key usage logs: {str(e)}"
            }
    
    @router.delete("/{key_id}/delete")
    async def delete_api_key(
        key_id: str,
        current_user: User = Depends(get_current_admin_user or get_current_user)
    ):
        """Permanently delete an API key (admin only)."""
        # Only admins can permanently delete keys
        if not get_current_admin_user and current_user.role not in [Role.ADMIN, Role.SYSTEM]:
            return {
                "success": False,
                "message": "Admin permission required"
            }
        
        try:
            # Delete key
            success = await api_key_manager.delete_key(key_id)
            
            if success:
                return {
                    "success": True,
                    "message": "API key deleted"
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to delete API key"
                }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error deleting API key: {str(e)}"
            }
    
    return router


# Setup function for FastAPI app
def setup_api_key_authentication(app):
    """
    Set up API key authentication for a FastAPI app.
    
    Args:
        app: FastAPI application
    """
    # Add API key middleware
    app.middleware("http")(api_key_middleware)
    
    # Create and include API key router
    from ..auth.router import get_admin_user
    api_key_router = create_api_key_router(get_admin_user)
    app.include_router(api_key_router)
    
    logger.info("API Key authentication system initialized")