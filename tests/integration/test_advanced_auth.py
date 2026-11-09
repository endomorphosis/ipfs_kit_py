#!/usr/bin/env python3
"""
Test Advanced Authentication & Authorization Features

This module tests the advanced authentication and authorization features
implemented as part of Phase 1: Core Functionality Enhancements (Q3 2025)
from the MCP roadmap.
"""

import os
import sys
import time
import anyio
import pytest
from typing import Dict, Any, Optional, List

# Add parent directory to path for importing
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from ipfs_kit_py.mcp.auth.models import User, Role, Permission, APIKey, BackendPermission
from ipfs_kit_py.mcp.auth.service import AuthenticationService
from ipfs_kit_py.mcp.auth.audit import AuditLogger, AuditEventType
from ipfs_kit_py.mcp.auth.backend_authorization import BackendAuthorizationManager, Operation


@pytest.mark.anyio
class TestAdvancedAuthentication:
    """Test cases for advanced authentication features."""

    @pytest.fixture(autouse=True)
    async def setup_auth(self):
        """Set up test environment."""
        # Create authentication service with test secret key
        self.auth_service = AuthenticationService(
            secret_key="test_secret_key_for_authentication",
            token_expire_minutes=60,
            refresh_token_expire_days=7,
            password_reset_expire_hours=24,
            api_key_prefix="ipfk_test_"
        )

        # Initialize authentication service
        await self.auth_service.initialize()

        # Create audit logger for testing (with console logging disabled)
        self.audit_logger = AuditLogger(
            log_file="test_audit.log",
            console_logging=False,
            file_logging=False,
            json_logging=True
        )

        # Start audit logger
        await self.audit_logger.start()

        # Create backend authorization manager
        self.backend_auth = BackendAuthorizationManager()

        # Initialize backend authorization manager
        await self.backend_auth.initialize()

        # Create test user data
        self.test_user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "TestPassword123",
            "full_name": "Test User"
        }

        # Create test admin data
        self.test_admin_data = {
            "username": "testadmin",
            "email": "admin@example.com",
            "password": "AdminPassword123",
            "full_name": "Test Admin"
        }

        yield

        # Clean up after tests.
        # Stop audit logger
        await self.audit_logger.stop()

        # Remove test files
        if os.path.exists("test_audit.log"):
            os.remove("test_audit.log")

    async def create_test_user(self) -> User:
        """Create a test user for use in tests."""
        # Register test user
        success, user, message = await self.auth_service.register_user(
            self.auth_service.user_store._create_register_request(self.test_user_data)
        )

        assert success, f"Failed to create test user: {message}"
        assert user is not None

        return user

    async def create_test_admin(self) -> User:
        """Create a test admin for use in tests."""
        # Register test admin
        success, admin, message = await self.auth_service.register_user(
            self.auth_service.user_store._create_register_request(self.test_admin_data)
        )

        assert success, f"Failed to create test admin: {message}"
        assert admin is not None

        # Add admin role to user
        admin.roles.add("admin")
        await self.auth_service.user_store.update(admin.id, admin.dict())

        return admin

    async def test_user_registration_and_authentication(self):
        """Test user registration and authentication."""
        # Create test user
        user = await self.create_test_user()

        # Verify user data
        assert user.username == self.test_user_data["username"]
        assert user.email == self.test_user_data["email"]
        assert user.full_name == self.test_user_data["full_name"]
        assert user.active
        assert "user" in user.roles

        # Test authentication with correct password
        authenticated_user = await self.auth_service.authenticate_user(
            username=self.test_user_data["username"],
            password=self.test_user_data["password"]
        )

        assert authenticated_user is not None
        assert authenticated_user.id == user.id

        # Test authentication with wrong password
        authenticated_user = await self.auth_service.authenticate_user(
            username=self.test_user_data["username"],
            password="WrongPassword123"
        )

        assert authenticated_user is None

        # Test authentication with email
        authenticated_user = await self.auth_service.authenticate_user(
            username=self.test_user_data["email"],
            password=self.test_user_data["password"]
        )

        assert authenticated_user is not None
        assert authenticated_user.id == user.id

    async def test_token_creation_and_verification(self):
        """Test token creation and verification."""
        # Create test user
        user = await self.create_test_user()

        # Create session for user
        session = await self.auth_service.create_session(
            user=user,
            ip_address="127.0.0.1",
            user_agent="Test Client"
        )

        # Create access token
        access_token = await self.auth_service.create_access_token(user, session)
        assert access_token is not None

        # Create refresh token
        refresh_token = await self.auth_service.create_refresh_token(user, session)
        assert refresh_token is not None

        # Verify access token
        valid, token_data, error = await self.auth_service.verify_token(access_token)
        assert valid
        assert token_data is not None
        assert token_data.sub == user.id
        assert token_data.scope == "access"

        # Verify refresh token
        valid, token_data, error = await self.auth_service.verify_token(refresh_token)
        assert valid
        assert token_data is not None
        assert token_data.sub == user.id
        assert token_data.scope == "refresh"

        # Test refresh token to get new access token
        success, new_access_token, error = await self.auth_service.refresh_access_token(refresh_token)
        assert success
        assert new_access_token is not None

        # Verify new access token
        valid, token_data, error = await self.auth_service.verify_token(new_access_token)
        assert valid
        assert token_data is not None
        assert token_data.sub == user.id
        assert token_data.scope == "access"

        # Test token revocation
        success = await self.auth_service.revoke_token(access_token)
        assert success

        # Verify revoked token
        valid, token_data, error = await self.auth_service.verify_token(access_token)
        assert not valid

    async def test_api_key_creation_and_verification(self):
        """Test API key creation and verification."""
        # Create test user
        user = await self.create_test_user()

        # Create API key request
        api_key_request = APIKey(
            name="Test API Key",
            user_id=user.id,
            roles={"api"},
            direct_permissions={"storage:read", "storage:list"},
            expires_at=time.time() + 86400  # 1 day expiration
        )

        # Create API key
        success, api_key_response, message = await self.auth_service.create_api_key(
            user_id=user.id,
            request=self.auth_service.api_key_store._create_api_key_request(api_key_request)
        )

        assert success, f"Failed to create API key: {message}"
        assert api_key_response is not None
        assert api_key_response.name == "Test API Key"
        assert api_key_response.user_id == user.id
        assert api_key_response.key.startswith(self.auth_service.api_key_prefix)

        # Verify API key
        valid, api_key_obj, error = await self.auth_service.verify_api_key(
            api_key=api_key_response.key,
            ip_address="127.0.0.1"
        )

        assert valid
        assert api_key_obj is not None
        assert api_key_obj.user_id == user.id
        assert api_key_obj.name == "Test API Key"

        # Create access token from API key
        token = await self.auth_service.create_access_token_from_api_key(api_key_obj)
        assert token is not None

        # Verify token created from API key
        valid, token_data, error = await self.auth_service.verify_token(token)
        assert valid
        assert token_data is not None
        assert token_data.sub == user.id
        assert token_data.is_api_key

        # Test API key revocation
        success, message = await self.auth_service.revoke_api_key(
            key_id=api_key_obj.id,
            user_id=user.id
        )

        assert success, f"Failed to revoke API key: {message}"

        # Try to verify revoked API key
        valid, api_key_obj, error = await self.auth_service.verify_api_key(
            api_key=api_key_response.key,
            ip_address="127.0.0.1"
        )

        assert not valid

    async def test_role_based_access_control(self):
        """Test role-based access control."""
        # Create test user and admin
        user = await self.create_test_user()
        admin = await self.create_test_admin()

        # Check user permissions
        user_permissions = await self.auth_service.get_user_permissions(user.id)
        assert "storage:read" in user_permissions
        assert "storage:list" in user_permissions
        assert "admin:*" not in user_permissions

        # Check admin permissions
        admin_permissions = await self.auth_service.get_user_permissions(admin.id)
        assert "admin:*" in admin_permissions

        # Test permission checking
        has_permission = await self.auth_service.check_permission(
            user_id=user.id,
            required_permission="storage:read"
        )
        assert has_permission

        has_permission = await self.auth_service.check_permission(
            user_id=user.id,
            required_permission="storage:write"
        )
        assert not has_permission

        has_permission = await self.auth_service.check_permission(
            user_id=admin.id,
            required_permission="storage:write"
        )
        assert has_permission

        # Test role checking
        has_role = await self.auth_service.check_role(
            user_id=user.id,
            required_role="user"
        )
        assert has_role

        has_role = await self.auth_service.check_role(
            user_id=user.id,
            required_role="admin"
        )
        assert not has_role

        has_role = await self.auth_service.check_role(
            user_id=admin.id,
            required_role="admin"
        )
        assert has_role

    async def test_audit_logging(self):
        """Test audit logging functionality."""
        # Create test entries
        await self.audit_logger.log_login(
            success=True,
            user_id="test_user_123",
            username="testuser",
            ip_address="127.0.0.1",
            user_agent="Test Browser"
        )

        await self.audit_logger.log_permission_check(
            user_id="test_user_123",
            permission="storage:read",
            resource_type="file",
            resource_id="test_file_123",
            granted=True
        )

        await self.audit_logger.log_backend_access(
            success=True,
            backend_id="ipfs",
            user_id="test_user_123",
            username="testuser",
            ip_address="127.0.0.1",
            action="store"
        )

        # Wait for logs to be processed
        await anyio.sleep(0.1)

        # Get recent logs
        logs = await self.audit_logger.get_recent_logs(limit=10)

        # Check if logs were created
        assert len(logs) >= 3

        # Check event counts
        counts = await self.audit_logger.get_event_counts()
        assert AuditEventType.USER_LOGIN in counts
        assert AuditEventType.PERMISSION_GRANTED in counts
        assert AuditEventType.BACKEND_ACCESS_GRANTED in counts

    async def test_backend_authorization(self):
        """Test backend authorization functionality."""
        # Create test user and admin
        user = await self.create_test_user()
        admin = await self.create_test_admin()

        # Check basic access to IPFS backend
        allowed, reason = await self.backend_auth.check_backend_access(
            backend_id="ipfs",
            user=user,
            operation=Operation.RETRIEVE
        )
        assert allowed, f"Expected access to be allowed, got: {reason}"

        # Check write access to IPFS backend
        allowed, reason = await self.backend_auth.check_backend_access(
            backend_id="ipfs",
            user=user,
            operation=Operation.STORE
        )
        assert allowed, f"Expected access to be allowed, got: {reason}"

        # Check access to Filecoin backend (admin only)
        allowed, reason = await self.backend_auth.check_backend_access(
            backend_id="filecoin",
            user=user,
            operation=Operation.RETRIEVE
        )
        assert not allowed, f"Expected access to be denied, got: {reason}"

        # Admin should have access to Filecoin backend
        allowed, reason = await self.backend_auth.check_backend_access(
            backend_id="filecoin",
            user=admin,
            operation=Operation.RETRIEVE
        )
        assert allowed, f"Expected admin access to be allowed, got: {reason}"

        # Set S3 backend to read-only
        await self.backend_auth.set_backend_read_only("s3", True)

        # Check read access to S3 backend
        allowed, reason = await self.backend_auth.check_backend_access(
            backend_id="s3",
            user=admin,
            operation=Operation.RETRIEVE
        )
        assert allowed, f"Expected read access to be allowed, got: {reason}"

        # Check write access to S3 backend (should be denied due to read-only)
        allowed, reason = await self.backend_auth.check_backend_access(
            backend_id="s3",
            user=admin,
            operation=Operation.STORE
        )
        assert not allowed, f"Expected write access to be denied due to read-only, got: {reason}"

        # Get accessible backends for user
        backends = self.backend_auth.get_accessible_backends(user)
        assert "ipfs" in backends
        assert "filecoin" not in backends

        # Get accessible backends for admin
        backends = self.backend_auth.get_accessible_backends(admin)
        assert "ipfs" in backends
        assert "filecoin" in backends
        assert "s3" in backends
        assert "huggingface" in backends
