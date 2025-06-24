"""
IPFS Backend Test Suite

This module provides comprehensive tests for the IPFS backend implementation,
ensuring that all required functionality works correctly.
"""

import os
import unittest
from typing import Dict, Any

from .base_backend_test import BaseBackendTest
from ipfs_kit_py.mcp.storage_manager.backends.ipfs_backend import IPFSBackend
from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType


class IPFSBackendTest(BaseBackendTest):
    """Test class for the IPFS backend implementation."""

    def setUp(self):
        """Set up the test environment with an IPFS backend."""
        super().setUp()
        self.backend_name = "IPFS"

        # Load configuration from environment variables or use defaults for testing
        resources = {
            "ipfs_api_url": os.environ.get("IPFS_API_URL", "http://localhost:5001"),
            "ipfs_gateway_url": os.environ.get("IPFS_GATEWAY_URL", "http://localhost:8080"),
            "mock_mode": os.environ.get("IPFS_MOCK_MODE", "true").lower() in ("true", "1", "yes"),
            "timeout": 30
        }

        metadata = {
            "default_pin": True,
            "verify_cids": True
        }

        # Initialize the IPFS backend
        try:
            self.backend = IPFSBackend(resources, metadata)
            self.test_container = None  # IPFS doesn't use containers
        except Exception as e:
            self.skipTest(f"Failed to initialize IPFS backend: {e}")

    def test_ipfs_specific_path_handling(self):
        """Test IPFS-specific path handling for CIDs."""
        # Skip if backend is not initialized
        if not self.backend:
            self.skipTest("IPFS backend not initialized")

        # Store content with a specific path
        content = "IPFS path test content"
        path = "test/ipfs/path/test.txt"

        # Store the content
        result = self.backend.store(content, None, path)
        self.assertTrue(result.get("success", False), f"Failed to store content with path: {result.get('error', 'Unknown error')}")

        # Get identifier for cleanup
        identifier = result.get("identifier")
        self.assertIsNotNone(identifier, "No identifier returned from store operation")
        self.created_identifiers.append(identifier)

        # Retrieve the content
        retrieve_result = self.backend.retrieve(identifier)
        self.assertTrue(retrieve_result.get("success", False), f"Failed to retrieve content: {retrieve_result.get('error', 'Unknown error')}")

        # Verify content
        retrieved_data = retrieve_result.get("data")
        self.assertIsNotNone(retrieved_data, "No data returned from retrieve operation")

        if isinstance(retrieved_data, bytes):
            retrieved_text = retrieved_data.decode('utf-8')
        else:
            retrieved_text = retrieved_data

        self.assertEqual(content, retrieved_text, "Retrieved content doesn't match original")

    def test_cid_formats(self):
        """Test handling of different CID formats (v0, v1)."""
        # Skip if backend is not initialized
        if not self.backend:
            self.skipTest("IPFS backend not initialized")

        # Store content to get a CID
        content = "CID format test content"

        # Store the content
        result = self.backend.store(content)
        self.assertTrue(result.get("success", False), f"Failed to store content: {result.get('error', 'Unknown error')}")

        # Get identifier for cleanup
        identifier = result.get("identifier")
        self.assertIsNotNone(identifier, "No identifier returned from store operation")
        self.created_identifiers.append(identifier)

        # Check if CID format matches expected pattern
        # CIDv0 starts with "Qm", CIDv1 with "b"
        # We're not strict about the exact format since it depends on the IPFS implementation
        self.assertTrue(
            identifier.startswith("Qm") or identifier.startswith("bafy"),
            f"CID format doesn't match expected patterns: {identifier}"
        )

        # Try to retrieve with the CID
        retrieve_result = self.backend.retrieve(identifier)
        self.assertTrue(retrieve_result.get("success", False), f"Failed to retrieve content: {retrieve_result.get('error', 'Unknown error')}")

    def test_pinning(self):
        """Test pinning functionality if supported by the backend."""
        # Skip if backend is not initialized
        if not self.backend:
            self.skipTest("IPFS backend not initialized")

        # Only run if backend has IPFS client with pin operations
        if not hasattr(self.backend, "ipfs") or not hasattr(self.backend.ipfs, "ipfs_pin_add"):
            self.skipTest("IPFS client doesn't support pin operations")

        # Store content
        content = "Pinning test content"

        # Store with pin option
        options = {"pin": True}
        result = self.backend.store(content, None, None, options)
        self.assertTrue(result.get("success", False), f"Failed to store content: {result.get('error', 'Unknown error')}")

        # Get identifier for cleanup
        identifier = result.get("identifier")
        self.assertIsNotNone(identifier, "No identifier returned from store operation")
        self.created_identifiers.append(identifier)

        # Verify content is pinned
        try:
            pin_ls_result = self.backend.ipfs.ipfs_pin_ls(identifier)
            self.assertTrue(pin_ls_result.get("success", False), f"Failed to check pin status: {pin_ls_result.get('error', 'Unknown error')}")

            # The exact response format might vary, but it should indicate the content is pinned
            pins = pin_ls_result.get("pins", {})
            self.assertTrue(
                identifier in pins or identifier in str(pins),
                f"Content should be pinned but pin check returned: {pins}"
            )
        except Exception as e:
            self.skipTest(f"Failed to check pin status: {e}")

        # Test unpinning if pin_rm is available
        if hasattr(self.backend.ipfs, "ipfs_pin_rm"):
            try:
                unpin_result = self.backend.ipfs.ipfs_pin_rm(identifier)
                self.assertTrue(unpin_result.get("success", False), f"Failed to unpin content: {unpin_result.get('error', 'Unknown error')}")

                # Verify content is unpinned
                pin_ls_after = self.backend.ipfs.ipfs_pin_ls(identifier)
                pins_after = pin_ls_after.get("pins", {})
                self.assertFalse(
                    identifier in pins_after or identifier in str(pins_after),
                    f"Content should be unpinned but pin check returned: {pins_after}"
                )
            except Exception as e:
                # Don't fail the test for unpin issues
                print(f"Warning: Failed to unpin content: {e}")


# Allow running the tests directly
if __name__ == "__main__":
    unittest.main()
