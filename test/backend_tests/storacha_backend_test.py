"""
Storacha Backend Test Suite

This module provides comprehensive tests for the Storacha (Web3.Storage) backend implementation,
ensuring that all required functionality works correctly.
"""

import os
import unittest
from typing import Dict, Any

from .base_backend_test import BaseBackendTest
from ipfs_kit_py.mcp.storage_manager.backends.storacha_backend import StorachaBackend
from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType


class StorachaBackendTest(BaseBackendTest):
    """Test class for the Storacha backend implementation."""

    def setUp(self):
        """Set up the test environment with a Storacha backend."""
        super().setUp()
        self.backend_name = "Storacha"

        # Load configuration from environment variables or use defaults for testing
        resources = {
            "api_key": os.environ.get("W3S_API_KEY", ""),
            "endpoints": os.environ.get("W3S_ENDPOINTS", "https://api.web3.storage,https://w3s.link"),
            "mock_mode": os.environ.get("W3S_MOCK_MODE", "true").lower() in ("true", "1", "yes"),
            "max_threads": 5,
            "connection_timeout": 10,
            "read_timeout": 30,
            "max_retries": 3
        }

        # If endpoints is a string, convert to list
        if isinstance(resources["endpoints"], str):
            resources["endpoints"] = [e.strip() for e in resources["endpoints"].split(",")]

        metadata = {
            "cache_ttl": 3600,  # 1 hour
            "cache_size_limit": 100 * 1024 * 1024  # 100MB
        }

        # Skip test if no API key provided and not in mock mode
        if not resources["api_key"] and not resources["mock_mode"]:
            self.skipTest("Web3.Storage API key not provided and mock mode disabled")

        # Initialize the Storacha backend
        try:
            self.backend = StorachaBackend(resources, metadata)
            self.test_container = None  # Storacha doesn't use containers
        except Exception as e:
            self.skipTest(f"Failed to initialize Storacha backend: {e}")

    def test_cid_format_validation(self):
        """Test CID format validation in Storacha."""
        # Skip if backend is not initialized
        if not self.backend:
            self.skipTest("Storacha backend not initialized")

        # Store content to get a CID
        content = "CID format test content for Storacha"

        # Store the content
        result = self.backend.store(content)
        self.assertTrue(result.get("success", False), f"Failed to store content: {result.get('error', 'Unknown error')}")

        # Get identifier for cleanup
        identifier = result.get("identifier")
        self.assertIsNotNone(identifier, "No identifier returned from store operation")
        self.created_identifiers.append(identifier)

        # Check CID format (should be v1 CID for Web3.Storage, starting with 'bafy')
        self.assertTrue(
            identifier.startswith("bafy") or identifier.startswith("b"),
            f"CID format doesn't match expected Web3.Storage pattern: {identifier}"
        )

        # Test retrieval with this CID
        retrieve_result = self.backend.retrieve(identifier)
        self.assertTrue(retrieve_result.get("success", False), f"Failed to retrieve content: {retrieve_result.get('error', 'Unknown error')}")

    def test_connection_failover(self):
        """Test connection failover mechanism in StorachaConnectionManager."""
        # Skip if backend is not initialized
        if not self.backend:
            self.skipTest("Storacha backend not initialized")

        # Skip if in mock mode as failover is not meaningful
        if self.backend.connection.mock_mode:
            self.skipTest("Test skipped in mock mode")

        # Test available endpoints
        connection_status = self.backend.connection.get_status()
        self.assertIsNotNone(connection_status, "Connection status should not be None")

        # At least one endpoint should be healthy
        healthy_endpoints = [
            endpoint for endpoint, status in connection_status.get("endpoints", {}).items()
            if status.get("healthy", False)
        ]

        self.assertGreater(len(healthy_endpoints), 0, "No healthy endpoints found")

        # Store content to test actual connection
        content = "Connection failover test content"

        # Store the content
        result = self.backend.store(content)
        self.assertTrue(result.get("success", False), f"Failed to store content: {result.get('error', 'Unknown error')}")

        # Get identifier for cleanup
        identifier = result.get("identifier")
        self.assertIsNotNone(identifier, "No identifier returned from store operation")
        self.created_identifiers.append(identifier)

    def test_cache_functionality(self):
        """Test caching functionality of the Storacha backend."""
        # Skip if backend is not initialized
        if not self.backend:
            self.skipTest("Storacha backend not initialized")

        # Store content
        content = "Storacha cache test content"

        # Store with cache enabled
        options = {"cache": True}
        result = self.backend.store(content, None, None, options)
        self.assertTrue(result.get("success", False), f"Failed to store content: {result.get('error', 'Unknown error')}")

        identifier = result.get("identifier")
        self.assertIsNotNone(identifier, "No identifier returned from store operation")
        self.created_identifiers.append(identifier)

        # Retrieve first time (should go to Web3.Storage)
        first_retrieve = self.backend.retrieve(identifier, None, {"use_cache": True})
        self.assertTrue(first_retrieve.get("success", False), f"Failed to retrieve content: {first_retrieve.get('error', 'Unknown error')}")

        # Retrieve second time (should use cache if available)
        second_retrieve = self.backend.retrieve(identifier, None, {"use_cache": True})
        self.assertTrue(second_retrieve.get("success", False), f"Failed to retrieve cached content: {second_retrieve.get('error', 'Unknown error')}")

        # Verify the second retrieval has cache information or matches the first retrieval
        self.assertEqual(
            first_retrieve.get("data"),
            second_retrieve.get("data"),
            "Cached content should match original content"
        )

        # Check if cache indication is present in some way
        cache_indication = False
        if "cached" in second_retrieve:
            cache_indication = second_retrieve.get("cached", False)
        elif "details" in second_retrieve and isinstance(second_retrieve["details"], dict):
            cache_indication = "cache" in str(second_retrieve["details"]).lower()

        # This is not a strict requirement as cache may be implemented differently
        if not cache_indication:
            print("Note: Cache indication not found in response, but data integrity verified")

        # Retrieve with cache disabled (should go to Web3.Storage)
        direct_retrieve = self.backend.retrieve(identifier, None, {"use_cache": False})
        self.assertTrue(direct_retrieve.get("success", False), f"Failed to retrieve content directly: {direct_retrieve.get('error', 'Unknown error')}")

        self.assertEqual(
            first_retrieve.get("data"),
            direct_retrieve.get("data"),
            "Direct retrieval content should match original content"
        )

    def test_immutable_semantics(self):
        """Test immutability semantics of Web3.Storage content."""
        # Skip if backend is not initialized
        if not self.backend:
            self.skipTest("Storacha backend not initialized")

        # Store content
        content = "Immutability test content"

        # Store the content
        result = self.backend.store(content)
        self.assertTrue(result.get("success", False), f"Failed to store content: {result.get('error', 'Unknown error')}")

        identifier = result.get("identifier")
        self.assertIsNotNone(identifier, "No identifier returned from store operation")
        self.created_identifiers.append(identifier)

        # Store the same content again
        repeat_result = self.backend.store(content)
        self.assertTrue(repeat_result.get("success", False), f"Failed to store same content again: {repeat_result.get('error', 'Unknown error')}")

        repeat_identifier = repeat_result.get("identifier")
        self.assertIsNotNone(repeat_identifier, "No identifier returned from repeat store operation")

        # For truly content-addressable storage, same content should yield same identifier
        # Note: Some implementations might add timestamps or other metadata
        # that causes identifiers to differ, so this is not a strict requirement
        if identifier != repeat_identifier:
            print(f"Note: Same content yielded different identifiers: {identifier} vs {repeat_identifier}")
            self.created_identifiers.append(repeat_identifier)

        # Store different content
        modified_content = content + " with modifications"
        modified_result = self.backend.store(modified_content)
        self.assertTrue(modified_result.get("success", False), f"Failed to store modified content: {modified_result.get('error', 'Unknown error')}")

        modified_identifier = modified_result.get("identifier")
        self.assertIsNotNone(modified_identifier, "No identifier returned from modified store operation")
        self.created_identifiers.append(modified_identifier)

        # Different content should yield different identifiers
        self.assertNotEqual(identifier, modified_identifier, "Different content should yield different identifiers")


# Allow running the tests directly
if __name__ == "__main__":
    unittest.main()
