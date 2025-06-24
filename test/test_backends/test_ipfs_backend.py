#!/usr/bin/env python3
"""
Test suite for the IPFS backend implementation.

This module tests the IPFS backend implementation to ensure it
correctly implements the BackendStorage abstract class.
"""

import unittest
import os
import logging
import tempfile
import uuid
from typing import Dict, Any, Optional

# Import the base test framework
from test_storage_backend_base import StorageBackendBaseTest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IPFSBackendTest(unittest.TestCase, StorageBackendBaseTest):
    """Test suite for IPFS backend implementation."""

    def setUp(self):
        """Set up the test environment with IPFS backend."""
        try:
            # Import IPFS backend
            from ipfs_kit_py.mcp.storage_manager.backends.ipfs_backend import IPFSBackend
            self.backend_class = IPFSBackend

            # Configure default resources and metadata
            self.default_resources = {
                # IPFS-specific resources can be added here
                "node_url": os.environ.get("IPFS_NODE_URL", "http://localhost:5001"),
                "timeout": 30,
            }

            self.default_metadata = {
                # IPFS-specific metadata can be added here
                "mock_mode": os.environ.get("IPFS_MOCK_MODE", "true").lower() == "true"
            }

            # Call the parent setUp
            super().setUp()

            # Check if backend initialized in mock mode
            mock_implementation = hasattr(self.backend.ipfs, "_mock_implementation") and self.backend.ipfs._mock_implementation
            if mock_implementation:
                logger.warning("IPFS backend initialized in mock mode - some tests may be skipped")
                self.mock_mode = True
            else:
                self.mock_mode = False

        except ImportError as e:
            logger.error(f"Failed to import IPFS backend: {e}")
            raise

    def test_ipfs_specific_pin_methods(self):
        """Test IPFS-specific pin methods."""
        # Skip if backend is in mock mode
        if getattr(self, 'mock_mode', True):
            self.skipTest("IPFS backend is in mock mode")

        # First add some content
        test_data = self._create_test_content("small")

        add_result = self.backend.add_content(test_data)
        if not add_result.get("success", False):
            self.skipTest(f"Backend not available for writes: {add_result.get('error', 'Unknown error')}")

        identifier = add_result["identifier"]

        # Store identifier for cleanup
        self.test_identifiers = getattr(self, 'test_identifiers', [])
        self.test_identifiers.append(identifier)

        # Test pin_add method
        if hasattr(self.backend, 'pin_add'):
            pin_result = self.backend.pin_add(identifier)
            self.assertIsNotNone(pin_result)
            self.assertIsInstance(pin_result, dict)

            # Test pin_ls method
            if hasattr(self.backend, 'pin_ls'):
                ls_result = self.backend.pin_ls()
                self.assertIsNotNone(ls_result)
                self.assertIsInstance(ls_result, dict)

                # Test pin_rm method
                if hasattr(self.backend, 'pin_rm'):
                    rm_result = self.backend.pin_rm(identifier)
                    self.assertIsNotNone(rm_result)
                    self.assertIsInstance(rm_result, dict)

    def test_ipfs_daemon_status(self):
        """Test getting IPFS daemon status if available."""
        # Skip if backend is in mock mode
        if getattr(self, 'mock_mode', True):
            self.skipTest("IPFS backend is in mock mode")

        # Test if ipfs binary is available
        if hasattr(self.backend.ipfs, 'test_ipfs'):
            result = self.backend.ipfs.test_ipfs()
            self.assertIsNotNone(result)
            self.assertIsInstance(result, dict)
            self.assertIn("success", result)
            self.assertTrue(result["success"])

            # If IPFS is available, try getting node ID
            if result.get("available", False) and hasattr(self.backend.ipfs, 'ipfs_id'):
                id_result = self.backend.ipfs.ipfs_id()
                self.assertIsNotNone(id_result)
                self.assertIsInstance(id_result, dict)

    def tearDown(self):
        """Clean up after tests."""
        # Clean up test content
        self._cleanup_test_content()

        # Call the parent tearDown
        super().tearDown()


if __name__ == "__main__":
    unittest.main()
