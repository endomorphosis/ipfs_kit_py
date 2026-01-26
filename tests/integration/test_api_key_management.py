"""
Tests for API Key Management in the advanced authentication system.

These tests verify that the API key functionality implemented as part of the 
MCP roadmap Phase 1: Core Functionality Enhancements (Q3 2025) works correctly.
"""

import os
import json
import pytest
import time
from unittest.mock import patch, MagicMock, AsyncMock

from ipfs_kit_py.mcp.auth.models import User, Role, Permission, ApiKey
from ipfs_kit_py.mcp.auth.apikey_router import router as apikey_router
from ipfs_kit_py.mcp.auth.service import AuthenticationService
from ipfs_kit_py.mcp.auth.persistence import ApiKeyStore

from fastapi import FastAPI
from fastapi.testclient import TestClient


# Test data
TEST_USER = User(
    id="user123",
    username="testuser",
    email="test@example.com",
    full_name="Test User",
    hashed_password="hashed_password",
    roles={"user"},
    active=True
)

TEST_API_KEY_CREATE_REQUEST = {
    "name": "Test API Key",
    "expires_in_days": 30,
    "permissions": ["read:ipfs", "write:ipfs"],
    "roles": ["user"],
    "allowed_ips": ["127.0.0.1", "192.168.1.0/24"],
    "backend_restrictions": ["ipfs"]
}

TEST_API_KEY_RESPONSE = {
    "id": "apikey123",
    "name": "Test API Key",
    "key": "ipfk_testapikey123456789",
    "user_id": "user123",
    "created_at": time.time(),
    "expires_at": time.time() + (30 * 86400),
    "active": True,
    "roles": ["user"],
    "permissions": ["read:ipfs", "write:ipfs"],
    "allowed_ips": ["127.0.0.1", "192.168.1.0/24"],
    "backend_restrictions": ["ipfs"]
}


# Fixtures
@pytest.fixture
def mock_api_key_store():
    """Mock the API key store."""
    with patch("ipfs_kit_py.mcp.auth.service.ApiKeyStore") as MockApiKeyStore:
        # Configure the mock
        store_instance = AsyncMock()
        
        # Mock API key storage
        api_keys = {TEST_API_KEY_RESPONSE["id"]: TEST_API_KEY_RESPONSE}
        store_instance.load_all.return_value = api_keys
        store_instance.get.side_effect = lambda key_id: api_keys.get(key_id)
        store_instance.create.return_value = True
        store_instance.update.return_value = True
        store_instance.delete.return_value = True
        
        MockApiKeyStore.return_value = store_instance
        
        yield store_instance


@pytest.fixture
def mock_auth_service(mock_api_key_store):
    """Mock authentication service."""
    with patch("ipfs_kit_py.mcp.auth.apikey_router.get_auth_service") as mock_service:
        # Configure the mock
        service_instance = AsyncMock()
        
        # Mock API key methods
        service_instance.create_api_key.return_value = (
            True,
            TEST_API_KEY_RESPONSE,
            "API key created successfully"
        )
        
        service_instance.get_user_api_keys.return_value = [
            ApiKey(**TEST_API_KEY_RESPONSE)
        ]
        
        service_instance.get_api_key.return_value = ApiKey(**TEST_API_KEY_RESPONSE)
        
        service_instance.revoke_api_key.return_value = (
            True,
            "API key revoked successfully"
        )
        
        service_instance.update_api_key_permissions.return_value = (
            True,
            "API key permissions updated"
        )
        
        service_instance.update_api_key_roles.return_value = (
            True,
            "API key roles updated"
        )
        
        service_instance.update_api_key_restrictions.return_value = (
            True,
            "API key restrictions updated"
        )
        
        mock_service.return_value = service_instance
        
        yield service_instance


@pytest.fixture
def mock_audit_logger():
    """Mock audit logger."""
    with patch("ipfs_kit_py.mcp.auth.apikey_router.get_audit_logger") as mock_logger:
        # Configure the mock
        logger_instance = AsyncMock()
        
        # Mock logging methods
        logger_instance.log_user_action.return_value = None
        
        mock_logger.return_value = logger_instance
        
        yield logger_instance


@pytest.fixture
def current_user():
    """Return a mock current user dependency."""
    return TEST_USER


@pytest.fixture
def test_app(mock_auth_service, mock_audit_logger):
    """Create a test FastAPI app with API key router."""
    app = FastAPI()
    
    # Override authentication dependency
    @app.dependency_overrides[apikey_router.get_current_user]
    def override_get_current_user():
        return TEST_USER
    
    app.include_router(apikey_router)
    
    return TestClient(app)


# Tests for API Key Management endpoints
def test_create_api_key_endpoint(test_app, mock_auth_service):
    """Test creating an API key."""
    # Make the request
    response = test_app.post(
        "",
        json=TEST_API_KEY_CREATE_REQUEST
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "key" in data
    assert data["name"] == TEST_API_KEY_CREATE_REQUEST["name"]
    
    # Verify service was called
    mock_auth_service.create_api_key.assert_called_once()


def test_list_api_keys_endpoint(test_app, mock_auth_service):
    """Test listing API keys."""
    # Make the request
    response = test_app.get("")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "keys" in data
    assert "total" in data
    assert len(data["keys"]) == 1
    assert data["keys"][0]["id"] == TEST_API_KEY_RESPONSE["id"]
    assert "key" not in data["keys"][0]  # Key should not be included in list
    
    # Verify service was called
    mock_auth_service.get_user_api_keys.assert_called_once()


def test_get_api_key_endpoint(test_app, mock_auth_service):
    """Test getting a specific API key."""
    # Make the request
    response = test_app.get(f"/{TEST_API_KEY_RESPONSE['id']}")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == TEST_API_KEY_RESPONSE["id"]
    assert data["name"] == TEST_API_KEY_RESPONSE["name"]
    assert "key" not in data  # Key should not be included in response
    
    # Verify service was called
    mock_auth_service.get_api_key.assert_called_once()


def test_revoke_api_key_endpoint(test_app, mock_auth_service):
    """Test revoking an API key."""
    # Make the request
    response = test_app.delete(f"/{TEST_API_KEY_RESPONSE['id']}")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "revoked" in data["message"]
    
    # Verify service was called
    mock_auth_service.revoke_api_key.assert_called_once_with(
        TEST_API_KEY_RESPONSE["id"],
        TEST_USER.id
    )


def test_update_api_key_permissions_endpoint(test_app, mock_auth_service):
    """Test updating API key permissions."""
    new_permissions = ["read:ipfs", "read:filecoin"]
    
    # Make the request
    response = test_app.put(
        f"/{TEST_API_KEY_RESPONSE['id']}/permissions",
        json=new_permissions
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "permissions" in data
    assert set(data["permissions"]) == set(new_permissions)
    
    # Verify service was called
    mock_auth_service.update_api_key_permissions.assert_called_once()


def test_update_api_key_roles_endpoint(test_app, mock_auth_service):
    """Test updating API key roles."""
    new_roles = ["user", "developer"]
    
    # Make the request
    response = test_app.put(
        f"/{TEST_API_KEY_RESPONSE['id']}/roles",
        json=new_roles
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "roles" in data
    assert set(data["roles"]) == set(new_roles)
    
    # Verify service was called
    mock_auth_service.update_api_key_roles.assert_called_once()


def test_update_api_key_restrictions_endpoint(test_app, mock_auth_service):
    """Test updating API key restrictions."""
    new_restrictions = {
        "allowed_ips": ["10.0.0.0/8", "192.168.0.0/16"],
        "backend_restrictions": ["ipfs", "filecoin"]
    }
    
    # Make the request
    response = test_app.put(
        f"/{TEST_API_KEY_RESPONSE['id']}/restrictions",
        json=new_restrictions
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "allowed_ips" in data
    assert "backend_restrictions" in data
    assert set(data["allowed_ips"]) == set(new_restrictions["allowed_ips"])
    assert set(data["backend_restrictions"]) == set(new_restrictions["backend_restrictions"])
    
    # Verify service was called
    mock_auth_service.update_api_key_restrictions.assert_called_once()


# Tests for API key validation
@pytest.mark.anyio
async def test_verify_api_key():
    """Test verifying an API key."""
    with patch("ipfs_kit_py.mcp.auth.service.AuthenticationService._verify_api_key") as mock_verify:
        # Set up the mock
        mock_verify.return_value = True
        
        auth_service = AuthenticationService(secret_key="test_secret")
        
        # Mock ApiKeyStore
        auth_service.api_key_store = AsyncMock()
        
        # Test valid key
        api_key = ApiKey(**TEST_API_KEY_RESPONSE)
        
        # Create a mock for the key lookup result
        mock_key_data = TEST_API_KEY_RESPONSE.copy()
        mock_key_data["hashed_key"] = "hashed_key_value"
        
        # Configure the mock ApiKeyStore to return our test key
        auth_service.api_key_store.load_all.return_value = {api_key.id: mock_key_data}
        
        # Call the method
        valid, result, message = await auth_service.verify_api_key(
            "ipfk_testapikey123456789",
            ip_address="127.0.0.1"
        )
        
        # Verify the result
        assert valid
        assert result is not None


@pytest.mark.anyio
async def test_verify_api_key_with_ip_restriction():
    """Test verifying an API key with IP restriction."""
    # This test would verify that IP restrictions are properly enforced
    # For simplicity, just a stub implementation here
    pass


@pytest.mark.anyio
async def test_create_access_token_from_api_key():
    """Test creating an access token from an API key."""
    # This test would verify that access tokens can be created from API keys
    # For simplicity, just a stub implementation here
    pass


if __name__ == "__main__":
    pytest.main()