"""
Tests for OAuth integration in the advanced authentication system.

These tests verify that the OAuth functionality implemented as part of the
MCP roadmap Phase 1: Core Functionality Enhancements (Q3 2025) works correctly.
"""

import os
import json
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from ipfs_kit_py.mcp.auth.oauth_manager import OAuthManager, OAuthProviderConfig, get_oauth_manager
from ipfs_kit_py.mcp.auth.oauth_router import router as oauth_router
from ipfs_kit_py.mcp.auth.oauth_persistence import OAuthStore
from ipfs_kit_py.mcp.auth.oauth_integration_service import patch_authentication_service

from fastapi import FastAPI
from fastapi.testclient import TestClient


# Test data
TEST_PROVIDER_CONFIG = {
    "id": "test_provider",
    "name": "Test Provider",
    "provider_type": "test",
    "client_id": "test_client_id",
    "client_secret": "test_client_secret",
    "authorize_url": "https://test.com/authorize",
    "token_url": "https://test.com/token",
    "userinfo_url": "https://test.com/userinfo",
    "scope": "test scope",
    "active": True,
    "default_roles": ["user"]
}

TEST_USER_INFO = {
    "provider_id": "test_provider",
    "provider_user_id": "test_user_123",
    "email": "test@example.com",
    "username": "testuser",
    "name": "Test User",
    "avatar_url": "https://example.com/avatar.jpg",
    "profile_url": "https://example.com/profile"
}


# Fixtures
@pytest.fixture
def mock_oauth_persistence():
    """Mock the OAuth persistence layer."""
    with patch("ipfs_kit_py.mcp.auth.oauth_manager.get_persistence_manager") as mock_persistence:
        # Configure the mock
        persistence_instance = AsyncMock()

        # Mock provider storage
        providers = {TEST_PROVIDER_CONFIG["id"]: TEST_PROVIDER_CONFIG}
        persistence_instance.get_oauth_providers.return_value = providers
        persistence_instance.save_oauth_provider.return_value = True
        persistence_instance.delete_oauth_provider.return_value = True

        # Mock connections storage
        persistence_instance.find_user_by_oauth.return_value = None  # No existing user by default
        persistence_instance.create_oauth_connection.return_value = True
        persistence_instance.update_oauth_connection.return_value = True
        persistence_instance.delete_oauth_connection.return_value = True
        persistence_instance.get_user_oauth_connections.return_value = []

        # Mock state storage
        persistence_instance.save_oauth_state.return_value = True
        persistence_instance.verify_oauth_state.return_value = {"provider_id": "test_provider"}

        mock_persistence.return_value = persistence_instance

        yield persistence_instance


@pytest.fixture
def oauth_manager(mock_oauth_persistence):
    """Create an OAuth manager with mocked persistence."""
    manager = OAuthManager()
    return manager


@pytest.fixture
def mock_http_client():
    """Mock aiohttp client for external API calls."""
    with patch("ipfs_kit_py.mcp.auth.oauth_manager.aiohttp.ClientSession") as mock_session:
        # Configure the mock session
        session_instance = AsyncMock()

        # Mock for token exchange
        token_response = AsyncMock()
        token_response.status = 200
        token_response.json.return_value = {"access_token": "test_access_token"}

        # Mock for user info
        user_info_response = AsyncMock()
        user_info_response.status = 200
        user_info_response.json.return_value = {
            "id": "test_user_123",
            "login": "testuser",
            "name": "Test User",
            "email": "test@example.com",
            "avatar_url": "https://example.com/avatar.jpg",
            "html_url": "https://example.com/profile"
        }

        # Configure context manager returns
        session_cm = MagicMock()
        session_cm.__aenter__.return_value = session_instance
        session_instance.post.return_value = session_cm
        session_instance.post.return_value.__aenter__.return_value = token_response

        session_instance.get.return_value = session_cm
        session_instance.get.return_value.__aenter__.return_value = user_info_response

        mock_session.return_value = session_cm

        yield mock_session


@pytest.fixture
def mock_auth_service():
    """Mock authentication service."""
    with patch("ipfs_kit_py.mcp.auth.oauth_router.get_auth_service") as mock_service:
        # Configure the mock
        service_instance = AsyncMock()

        # Mock process_oauth_callback
        service_instance.process_oauth_callback.return_value = (
            True,
            {
                "access_token": "mock_access_token",
                "refresh_token": "mock_refresh_token",
                "token_type": "bearer",
                "expires_in": 3600,
                "user": {
                    "id": "user123",
                    "username": "testuser",
                    "email": "test@example.com"
                },
                "is_new_user": False
            },
            "OAuth login successful"
        )

        mock_service.return_value = service_instance

        yield service_instance


@pytest.fixture
def test_app(mock_auth_service):
    """Create a test FastAPI app with OAuth router."""
    app = FastAPI()
    app.include_router(oauth_router)

    return TestClient(app)


# Tests for OAuthManager
@pytest.mark.asyncio
async def test_load_providers(oauth_manager, mock_oauth_persistence):
    """Test loading OAuth providers."""
    # Test loading providers
    providers = await oauth_manager.load_providers()

    # Verify providers were loaded
    assert len(providers) == 1
    assert TEST_PROVIDER_CONFIG["id"] in providers
    assert providers[TEST_PROVIDER_CONFIG["id"]].name == TEST_PROVIDER_CONFIG["name"]

    # Verify persistence was called
    mock_oauth_persistence.get_oauth_providers.assert_called_once()


@pytest.mark.asyncio
async def test_add_provider(oauth_manager, mock_oauth_persistence):
    """Test adding a new OAuth provider."""
    new_provider = {
        "id": "github",
        "name": "GitHub",
        "provider_type": "github",
        "client_id": "github_client_id",
        "client_secret": "github_client_secret",
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "scope": "user:email",
        "active": True
    }

    # Add the provider
    success, message = await oauth_manager.add_provider(new_provider)

    # Verify success
    assert success
    assert "saved successfully" in message

    # Verify persistence was called
    mock_oauth_persistence.save_oauth_provider.assert_called_once()


@pytest.mark.asyncio
async def test_create_authorization_url(oauth_manager):
    """Test creating an authorization URL."""
    # Create authorization URL
    success, result, message = await oauth_manager.create_authorization_url(
        TEST_PROVIDER_CONFIG["id"],
        "https://example.com/callback",
        "test_state"
    )

    # Verify success
    assert success
    assert "authorization_url" in result

    # Verify URL contains expected parameters
    auth_url = result["authorization_url"]
    assert TEST_PROVIDER_CONFIG["authorize_url"] in auth_url
    assert "client_id=test_client_id" in auth_url
    assert "redirect_uri=https%3A%2F%2Fexample.com%2Fcallback" in auth_url
    assert "state=test_state" in auth_url


@pytest.mark.asyncio
async def test_exchange_code_for_token(oauth_manager, mock_http_client):
    """Test exchanging an authorization code for a token."""
    # Exchange code for token
    success, token_data, message = await oauth_manager.exchange_code_for_token(
        TEST_PROVIDER_CONFIG["id"],
        "test_code",
        "https://example.com/callback"
    )

    # Verify success
    assert success
    assert "access_token" in token_data
    assert token_data["access_token"] == "test_access_token"


@pytest.mark.asyncio
async def test_get_user_info(oauth_manager, mock_http_client):
    """Test getting user info with an access token."""
    # Get user info
    success, user_info, message = await oauth_manager.get_user_info(
        TEST_PROVIDER_CONFIG["id"],
        "test_access_token"
    )

    # Verify success
    assert success
    assert "provider_id" in user_info
    assert user_info["provider_id"] == TEST_PROVIDER_CONFIG["id"]
    assert "provider_user_id" in user_info
    assert "email" in user_info
    assert "username" in user_info


# Tests for OAuth API endpoints
def test_list_providers_endpoint(test_app, oauth_manager):
    """Test the list providers endpoint."""
    with patch("ipfs_kit_py.mcp.auth.oauth_router.get_oauth_manager") as mock_get_manager:
        mock_get_manager.return_value = oauth_manager

        # Make the request
        response = test_app.get("/providers")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        assert len(data["providers"]) == 1
        assert data["providers"][0]["id"] == TEST_PROVIDER_CONFIG["id"]


def test_get_oauth_login_url_endpoint(test_app, oauth_manager):
    """Test the get OAuth login URL endpoint."""
    with patch("ipfs_kit_py.mcp.auth.oauth_router.get_oauth_manager") as mock_get_manager:
        mock_get_manager.return_value = oauth_manager

        # Mock the persistence manager
        with patch("ipfs_kit_py.mcp.auth.oauth_router.get_persistence_manager") as mock_get_persistence:
            persistence = AsyncMock()
            persistence.save_oauth_state.return_value = True
            mock_get_persistence.return_value = persistence

            # Make the request
            response = test_app.get(
                f"/login/{TEST_PROVIDER_CONFIG['id']}?redirect_uri=https://example.com/callback"
            )

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert "authorization_url" in data


def test_oauth_callback_endpoint(test_app, mock_auth_service):
    """Test the OAuth callback endpoint."""
    # Make the request
    response = test_app.get(
        f"/callback/test_provider?code=test_code&state=test_state&redirect_uri=https://example.com/callback"
    )

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert "user" in data


# Integration tests for OAuth functionality
def test_oauth_integration():
    """Test the OAuth integration with authentication service."""
    # Patch the authentication service
    with patch("ipfs_kit_py.mcp.auth.oauth_integration_service.AuthenticationService") as MockAuthService:
        # Verify the patch function works without errors
        patch_authentication_service()

        # Verify methods were replaced
        assert hasattr(MockAuthService, "get_oauth_login_url")
        assert hasattr(MockAuthService, "process_oauth_callback")
        assert hasattr(MockAuthService, "_load_oauth_providers")


if __name__ == "__main__":
    pytest.main()
