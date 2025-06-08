"""
Authentication & Authorization Unit Tests

This module contains tests for the Advanced Authentication & Authorization system.
It tests core functionality like:
- User authentication
- Token validation
- Role-based access control
- API key validation
- Backend authorization

Run tests using: pytest -xvs test_auth.py
"""

import os
import time
import pytest
import json
import uuid
from typing import Dict, Any
from unittest.mock import MagicMock, patch, AsyncMock

# Import auth components
from ipfs_kit_py.mcp.auth.models import User, Role, Permission
from ipfs_kit_py.mcp.auth.rbac import RBACManager, ResourceType, ActionType
from ipfs_kit_py.mcp.auth.api_key_enhanced import APIKey, EnhancedAPIKeyManager
from ipfs_kit_py.mcp.auth.enhanced_backend_middleware import BackendAuthorizationMiddleware


# Test RBAC functionality
class TestRBAC:
    """Tests for the Role-Based Access Control system."""
    
    @pytest.fixture
    def rbac_manager(self, tmp_path):
        """Create a test RBAC manager."""
        # Create a temporary directory for test data
        store_path = str(tmp_path / "rbac")
        return RBACManager(store_path)
    
    def test_create_permission(self, rbac_manager):
        """Test creating a permission."""
        # Create a permission
        permission = rbac_manager.create_permission(
            name="test:permission",
            resource_type=ResourceType.STORAGE,
            actions={ActionType.READ},
            description="Test permission"
        )
        
        # Verify permission was created
        assert permission is not None
        assert permission.name == "test:permission"
        assert permission.resource_type == ResourceType.STORAGE
        assert ActionType.READ in permission.actions
        assert permission.description == "Test permission"
        
        # Verify permission can be retrieved
        retrieved = rbac_manager.get_permission(permission.id)
        assert retrieved is not None
        assert retrieved.name == permission.name
    
    def test_create_role(self, rbac_manager):
        """Test creating a role."""
        # Create a permission first
        permission = rbac_manager.create_permission(
            name="test:permission",
            resource_type=ResourceType.STORAGE,
            actions={ActionType.READ},
            description="Test permission"
        )
        
        # Create a role
        role = rbac_manager.create_role(
            id="test_role",
            name="Test Role",
            permissions=[permission.id],
            description="Test role"
        )
        
        # Verify role was created
        assert role is not None
        assert role.id == "test_role"
        assert role.name == "Test Role"
        assert permission.id in role.permissions
        assert role.description == "Test role"
        
        # Verify role can be retrieved
        retrieved = rbac_manager.get_role(role.id)
        assert retrieved is not None
        assert retrieved.name == role.name
    
    def test_role_permissions(self, rbac_manager):
        """Test getting permissions for a role."""
        # Create permissions
        read_permission = rbac_manager.create_permission(
            name="read:test",
            resource_type=ResourceType.STORAGE,
            actions={ActionType.READ},
            description="Read permission"
        )
        write_permission = rbac_manager.create_permission(
            name="write:test",
            resource_type=ResourceType.STORAGE,
            actions={ActionType.CREATE, ActionType.UPDATE},
            description="Write permission"
        )
        
        # Create parent role with read permission
        parent_role = rbac_manager.create_role(
            id="parent_role",
            name="Parent Role",
            permissions=[read_permission.id],
            description="Parent role"
        )
        
        # Create child role with write permission and parent role
        child_role = rbac_manager.create_role(
            id="child_role",
            name="Child Role",
            permissions=[write_permission.id],
            parent_roles=[parent_role.id],
            description="Child role"
        )
        
        # Get permissions for child role
        child_permissions = rbac_manager.get_role_permissions(child_role.id, include_parents=True)
        
        # Verify child role has both permissions
        assert read_permission.id in child_permissions
        assert write_permission.id in child_permissions
    
    def test_has_permission(self, rbac_manager):
        """Test checking if roles have permissions."""
        # Create permission
        permission = rbac_manager.create_permission(
            name="read:test",
            resource_type=ResourceType.STORAGE,
            actions={ActionType.READ},
            description="Read permission"
        )
        
        # Create role with permission
        role = rbac_manager.create_role(
            id="test_role",
            name="Test Role",
            permissions=[permission.id],
            description="Test role"
        )
        
        # Check has_permission
        assert rbac_manager.has_permission(
            role_ids=[role.id],
            resource_type=ResourceType.STORAGE,
            action=ActionType.READ
        ) is True
        
        # Check for action that should fail
        assert rbac_manager.has_permission(
            role_ids=[role.id],
            resource_type=ResourceType.STORAGE,
            action=ActionType.DELETE
        ) is False
        
        # Check for resource type that should fail
        assert rbac_manager.has_permission(
            role_ids=[role.id],
            resource_type=ResourceType.USER,
            action=ActionType.READ
        ) is False


# Test User model
class TestUserModel:
    """Tests for the User model."""
    
    def test_user_creation(self):
        """Test creating a user."""
        # Create a user
        user = User(
            username="testuser",
            email="test@example.com",
            role=Role.USER
        )
        
        # Set password
        user.set_password("password123")
        
        # Verify user attributes
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == Role.USER
        assert user.verify_password("password123") is True
        assert user.verify_password("wrong_password") is False
    
    def test_admin_user(self):
        """Test creating an admin user."""
        # Create an admin user
        admin = User(
            username="admin",
            email="admin@example.com",
            role=Role.ADMIN
        )
        
        # Verify admin role
        assert admin.role == Role.ADMIN
        assert admin.has_role(Role.ADMIN) is True
        assert admin.has_role(Role.USER) is False
    
    def test_user_to_dict(self):
        """Test converting user to dictionary."""
        # Create a user
        user = User(
            username="testuser",
            email="test@example.com",
            role=Role.USER
        )
        
        # Convert to dictionary
        user_dict = user.to_dict()
        
        # Verify dictionary
        assert user_dict["username"] == "testuser"
        assert user_dict["email"] == "test@example.com"
        assert user_dict["role"] == Role.USER
        
        # Password should not be included
        assert "password" not in user_dict
        assert "password_hash" not in user_dict


# Test API key functionality
class TestAPIKey:
    """Tests for the API key functionality."""
    
    def test_api_key_creation(self):
        """Test creating an API key."""
        # Create an API key
        api_key = APIKey(
            user_id="user123",
            name="Test Key",
            permissions=["read:ipfs", "read:search"],
            expires_at=time.time() + 3600,  # 1 hour from now
            rate_limit=100,
            backends=["ipfs", "filecoin"],
            ip_whitelist=["192.168.1.0/24"]
        )
        
        # Verify API key attributes
        assert api_key.user_id == "user123"
        assert api_key.name == "Test Key"
        assert "read:ipfs" in api_key.permissions
        assert "read:search" in api_key.permissions
        assert api_key.expires_at > time.time()
        assert api_key.rate_limit == 100
        assert "ipfs" in api_key.backends
        assert "filecoin" in api_key.backends
        assert "192.168.1.0/24" in api_key.ip_whitelist
        
        # Verify API key has a value
        assert api_key.key is not None
        assert api_key.key.startswith("mcp_")
        
        # Verify key hash
        assert api_key.key_hash is not None
        assert api_key.verify_key(api_key.key) is True
        assert api_key.verify_key("wrong_key") is False
    
    def test_api_key_expiration(self):
        """Test API key expiration."""
        # Create an expired API key
        expired_key = APIKey(
            user_id="user123",
            name="Expired Key",
            expires_at=time.time() - 3600  # 1 hour ago
        )
        
        # Create a valid API key
        valid_key = APIKey(
            user_id="user123",
            name="Valid Key",
            expires_at=time.time() + 3600  # 1 hour from now
        )
        
        # Verify expiration
        assert expired_key.is_expired() is True
        assert valid_key.is_expired() is False
    
    def test_api_key_backend_access(self):
        """Test API key backend access."""
        # Create API key with specific backends
        key_with_backends = APIKey(
            user_id="user123",
            name="Backend Key",
            backends=["ipfs", "filecoin"]
        )
        
        # Create API key without backend restrictions
        key_without_backends = APIKey(
            user_id="user123",
            name="Unrestricted Key"
        )
        
        # Verify backend access
        assert key_with_backends.can_access_backend("ipfs") is True
        assert key_with_backends.can_access_backend("filecoin") is True
        assert key_with_backends.can_access_backend("s3") is False
        
        # Key without backend restrictions should allow all backends
        assert key_without_backends.can_access_backend("ipfs") is True
        assert key_without_backends.can_access_backend("s3") is True
    
    def test_api_key_ip_whitelist(self):
        """Test API key IP whitelist."""
        # Create API key with IP whitelist
        key_with_ip = APIKey(
            user_id="user123",
            name="IP Key",
            ip_whitelist=["192.168.1.1", "10.0.0.0/24"]
        )
        
        # Create API key without IP restrictions
        key_without_ip = APIKey(
            user_id="user123",
            name="Unrestricted Key"
        )
        
        # Verify IP restrictions
        assert key_with_ip.is_ip_allowed("192.168.1.1") is True
        assert key_with_ip.is_ip_allowed("10.0.0.5") is True  # In the CIDR range
        assert key_with_ip.is_ip_allowed("172.16.0.1") is False
        
        # Key without IP restrictions should allow all IPs
        assert key_without_ip.is_ip_allowed("192.168.1.1") is True
        assert key_without_ip.is_ip_allowed("172.16.0.1") is True


# Test Backend Authorization Middleware
class TestBackendMiddleware:
    """Tests for the Backend Authorization Middleware."""
    
    @pytest.mark.asyncio
    async def test_identify_backend_operation(self):
        """Test identifying backend and operation from request."""
        # Create mock backend manager
        backend_manager = MagicMock()
        
        # Create middleware
        middleware = BackendAuthorizationMiddleware(
            rbac_manager=MagicMock(),
            backend_manager=backend_manager
        )
        
        # Create mock requests
        ipfs_version_request = MagicMock()
        ipfs_version_request.url.path = "/api/v0/ipfs/version"
        ipfs_version_request.method = "GET"
        
        ipfs_add_request = MagicMock()
        ipfs_add_request.url.path = "/api/v0/ipfs/add"
        ipfs_add_request.method = "POST"
        
        storage_get_request = MagicMock()
        storage_get_request.url.path = "/api/v0/storage/get/s3/some-file"
        storage_get_request.method = "GET"
        
        # Test backend identification
        backend, operation = middleware._identify_backend_operation(ipfs_version_request)
        assert backend == "ipfs"
        assert operation == "read"
        
        backend, operation = middleware._identify_backend_operation(ipfs_add_request)
        assert backend == "ipfs"
        assert operation == "write"
        
        backend, operation = middleware._identify_backend_operation(storage_get_request)
        assert backend == "s3"
        assert operation == "read"


# Integration test for authorization middleware with FastAPI
@pytest.mark.asyncio
async def test_auth_middleware_integration():
    """Test integration of authorization middleware with FastAPI."""
    # This is a more complex test that would typically use FastAPI's TestClient
    # We're mocking the key components here for simplicity
    from fastapi import FastAPI, Depends, HTTPException
    from starlette.requests import Request
    from starlette.responses import Response
    
    # Create mock components
    rbac_manager = MagicMock()
    backend_manager = MagicMock()
    audit_logger = MagicMock()
    
    # Mock the RBAC check permission method
    rbac_manager.check_permission.return_value = True
    
    # Create middleware
    middleware = BackendAuthorizationMiddleware(
        rbac_manager=rbac_manager,
        backend_manager=backend_manager,
        audit_logger=audit_logger
    )
    
    # Create a mock user
    user = User(
        id="user123",
        username="testuser",
        email="test@example.com",
        role=Role.USER
    )
    
    # Create a mock request
    request = MagicMock()
    request.url.path = "/api/v0/ipfs/add"
    request.method = "POST"
    request.state.user = user
    
    # Create a mock response
    response = Response("Success")
    
    # Create a mock call_next function
    async def call_next(request):
        return response
    
    # Execute middleware
    result = await middleware.authorize_backend_access(request, call_next)
    
    # Verify middleware passed the request through
    assert result == response
    
    # Verify RBAC manager was called to check permissions
    rbac_manager.check_permission.assert_called_once()
    
    # Verify audit logger was called
    if audit_logger:
        audit_logger.log.assert_called_once()


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])