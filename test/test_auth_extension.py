#!/usr/bin/env python3
"""
Test script for the authentication extension.

This script tests the basic functionality of the authentication and authorization system.
"""

import os
import sys
import logging
import asyncio
import json
import uuid
import time
import random
from typing import Dict, Any
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the parent directory to the path to import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Try to import required modules
try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from jose import jwt
    from passlib.context import CryptContext
    HAS_REQUIREMENTS = True
except ImportError:
    logger.warning("Missing required packages. Please install: fastapi, python-jose, passlib")
    HAS_REQUIREMENTS = False

# Import the auth extension
try:
    from mcp_extensions.auth_extension import (
        create_auth_router,
        initialize,
        get_password_hash,
        get_user_by_username,
        users,
        roles,
        api_keys,
        create_api_key,
        Permission
    )
    HAS_AUTH_EXTENSION = True
except ImportError as e:
    logger.error(f"Failed to import auth extension: {e}")
    HAS_AUTH_EXTENSION = False

# Test variables
TEST_USERNAME = "test_user"
TEST_PASSWORD = "test_password123"
TEST_EMAIL = "test@example.com"
TEST_API_KEY_NAME = "test_api_key"

# Test functions
def test_user_creation():
    """Test user creation."""
    logger.info("Testing user creation")

    if not HAS_AUTH_EXTENSION:
        logger.error("Auth extension not available")
        return False

    try:
        # Clear any existing test user
        for user_id, user in list(users.items()):
            if user.get("username") == TEST_USERNAME:
                del users[user_id]

        # Check that test user doesn't exist
        existing_user = get_user_by_username(TEST_USERNAME)
        if existing_user:
            logger.error(f"Test user {TEST_USERNAME} already exists")
            return False

        # Create test user
        user_id = str(uuid.uuid4())
        hashed_password = get_password_hash(TEST_PASSWORD)

        new_user = {
            "id": user_id,
            "username": TEST_USERNAME,
            "email": TEST_EMAIL,
            "hashed_password": hashed_password,
            "full_name": "Test User",
            "disabled": False,
            "roles": ["user"],
            "created_at": time.time(),
            "updated_at": time.time()
        }

        users[user_id] = new_user

        # Verify user exists
        created_user = get_user_by_username(TEST_USERNAME)
        if not created_user:
            logger.error("Failed to create test user")
            return False

        logger.info(f"Successfully created test user {TEST_USERNAME}")
        return True
    except Exception as e:
        logger.error(f"Error testing user creation: {e}")
        return False

def test_api_key_creation():
    """Test API key creation."""
    logger.info("Testing API key creation")

    if not HAS_AUTH_EXTENSION:
        logger.error("Auth extension not available")
        return False

    try:
        # Get test user
        test_user = get_user_by_username(TEST_USERNAME)
        if not test_user:
            logger.error(f"Test user {TEST_USERNAME} not found")
            return False

        # Create API key data
        api_key_data = type('ApiKeyCreate', (), {
            "name": TEST_API_KEY_NAME,
            "description": "Test API key",
            "roles": ["api"],
            "expires_days": 30
        })

        # Create API key
        api_key_info = create_api_key(test_user["id"], api_key_data)

        # Verify API key was created
        if not api_key_info or "key" not in api_key_info:
            logger.error("Failed to create API key")
            return False

        logger.info(f"Successfully created API key: {api_key_info['key']}")
        return True
    except Exception as e:
        logger.error(f"Error testing API key creation: {e}")
        return False

def test_fastapi_integration():
    """Test FastAPI integration of auth router."""
    logger.info("Testing FastAPI integration")

    if not HAS_REQUIREMENTS or not HAS_AUTH_EXTENSION:
        logger.error("Required packages not available")
        return False

    try:
        # Create a test FastAPI app
        app = FastAPI()

        # Create and add an auth router
        auth_router = create_auth_router("/api/v0")
        app.include_router(auth_router)

        # Create a test client
        client = TestClient(app)

        # Test the token endpoint with test user
        response = client.post(
            "/api/v0/auth/token",
            data={"username": TEST_USERNAME, "password": TEST_PASSWORD}
        )

        if response.status_code != 200:
            logger.error(f"Token endpoint returned status code {response.status_code}")
            return False

        # Check the response JSON
        data = response.json()
        if "access_token" not in data:
            logger.error("Token endpoint didn't return access_token")
            return False

        # Use the token to access a protected endpoint
        access_token = data["access_token"]
        response = client.get(
            "/api/v0/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        if response.status_code != 200:
            logger.error(f"Me endpoint returned status code {response.status_code}")
            return False

        user_data = response.json()
        if user_data.get("username") != TEST_USERNAME:
            logger.error(f"Me endpoint returned wrong username: {user_data.get('username')}")
            return False

        logger.info("FastAPI integration working correctly")
        return True
    except Exception as e:
        logger.error(f"Error testing FastAPI integration: {e}")
        return False

def test_role_based_access():
    """Test role-based access control."""
    logger.info("Testing role-based access control")

    if not HAS_AUTH_EXTENSION:
        logger.error("Auth extension not available")
        return False

    try:
        # Get test user
        test_user = get_user_by_username(TEST_USERNAME)
        if not test_user:
            logger.error(f"Test user {TEST_USERNAME} not found")
            return False

        # Test permissions based on roles
        user_permissions = [
            Permission.READ,
            Permission.WRITE,
            Permission.IPFS_READ,
            Permission.IPFS_WRITE,
            Permission.IPFS_PIN
        ]

        for permission in user_permissions:
            if permission not in roles["user"]["permissions"]:
                logger.error(f"User role should have permission: {permission}")
                return False

        # Test admin permissions
        admin_permissions = ["*"]  # Wildcard
        if admin_permissions != roles["admin"]["permissions"]:
            logger.error(f"Admin role should have wildcard permission")
            return False

        logger.info("Role-based access control working correctly")
        return True
    except Exception as e:
        logger.error(f"Error testing role-based access control: {e}")
        return False

def run_all_tests():
    """Run all tests."""
    logger.info("Starting authentication extension tests")

    # Check requirements
    if not HAS_REQUIREMENTS:
        logger.error("Required packages are missing. Please install fastapi, python-jose, and passlib")
        return False

    if not HAS_AUTH_EXTENSION:
        logger.error("Auth extension not available or could not be imported")
        return False

    # Initialize the auth system
    initialize()

    # Run tests and collect results
    results = {
        "user_creation": test_user_creation(),
        "api_key_creation": test_api_key_creation(),
        "fastapi_integration": test_fastapi_integration(),
        "role_based_access": test_role_based_access()
    }

    # Check if all tests passed
    all_passed = all(results.values())

    if all_passed:
        logger.info("✅ All tests passed!")
    else:
        logger.error("❌ Some tests failed!")
        failed_tests = [test for test, result in results.items() if not result]
        logger.error(f"Failed tests: {failed_tests}")

    return all_passed

# Main entry point
if __name__ == "__main__":
    run_all_tests()
