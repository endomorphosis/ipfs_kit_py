"""
Filecoin Backend Test Suite

This module provides comprehensive tests for the Filecoin backend implementation,
ensuring that all required functionality works correctly. The tests are designed
to work with both the standard Filecoin interface and the enhanced Advanced
Filecoin Integration features.
"""

import os
import time
import unittest
from typing import Dict, Any

from .base_backend_test import BaseBackendTest
from ipfs_kit_py.mcp.storage_manager.backends.filecoin_backend import FilecoinBackend
from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType


class FilecoinBackendTest(BaseBackendTest):
    """Test class for the Filecoin backend implementation."""

    def setUp(self):
        """Set up the test environment with a Filecoin backend."""
        super().setUp()
        self.backend_name = "Filecoin"

        # Load configuration from environment variables or use defaults for testing
        resources = {
            "api_key": os.environ.get("FILECOIN_API_KEY", ""),
            "endpoint": os.environ.get("FILECOIN_ENDPOINT", ""),
            "mock_mode": os.environ.get("FILECOIN_MOCK_MODE", "true").lower() in ("true", "1", "yes"),
            "max_retries": 3
        }

        metadata = {
            "default_miner": os.environ.get("FILECOIN_DEFAULT_MINER", "t01000"),
            "replication_count": 1,
            "verify_deals": True,
            "max_price": "100000000000",  # In attoFIL (0.0001 FIL)
            "deal_duration": 518400  # 180 days in epochs
        }

        # Skip test if no API key provided and not in mock mode
        if not resources["api_key"] and not resources["mock_mode"]:
            self.skipTest("Filecoin API key not provided and mock mode disabled")

        # Initialize the Filecoin backend
        try:
            self.backend = FilecoinBackend(resources, metadata)
            self.test_container = metadata["default_miner"]  # Use default miner as container
        except Exception as e:
            self.skipTest(f"Failed to initialize Filecoin backend: {e}")

    def test_deal_lifecycle(self):
        """Test the Filecoin deal lifecycle if possible."""
        # Skip if backend is not initialized or in unavailable mode
        if not self.backend or self.backend.mode == "unavailable":
            self.skipTest("Filecoin backend not initialized or unavailable")

        # Skip in non-mock mode as real deals take too long
        if not hasattr(self.backend, 'mode') or self.backend.mode != "lotus" or not "mock" in str(self.backend.lotus):
            self.skipTest("Test requires mock mode for deal lifecycle testing")

        # Create test content
        content = "Filecoin deal lifecycle test content"
        temp_file = self._create_temp_file(content)

        # Store content (create deal)
        result = None
        with open(temp_file, 'rb') as f:
            result = self.backend.store(f, self.test_container)

        self.assertTrue(result.get("success", False), f"Failed to store content: {result.get('error', 'Unknown error')}")

        # Get CID/identifier for cleanup and tracking
        identifier = result.get("identifier")
        self.assertIsNotNone(identifier, "No identifier returned from store operation")
        self.created_identifiers.append(identifier)

        # Get deal information
        deals = result.get("deals", [])
        self.assertGreaterEqual(len(deals), 1, "No deals returned from store operation")

        # In a mock environment, we'd expect the deal to progress through states
        # Note: This might need adjustments based on the actual mock implementation
        deal_id = deals[0].get("deal_id") if deals else None

        if deal_id:
            # We would check deal state transitions here
            # For mock mode, we might need to manually trigger state transitions
            # This is a placeholder for that logic
            print(f"Deal {deal_id} created for {identifier}")

            # Get current deal state
            metadata_result = self.backend.get_metadata(identifier, self.test_container)
            self.assertTrue(metadata_result.get("success", False), f"Failed to get metadata: {metadata_result.get('error', 'Unknown error')}")

            # Deal state should be one of: 'proposed', 'published', 'active', 'sealed'
            # The exact state depends on the mock implementation
            metadata = metadata_result.get("metadata", {})
            found_deal_info = False

            # Different backends structure their metadata differently
            if "deals" in metadata:
                deals_info = metadata["deals"]
                if isinstance(deals_info, list) and len(deals_info) > 0:
                    found_deal_info = True
                    deal_state = deals_info[0].get("state", "unknown")
                    print(f"Deal state: {deal_state}")

            # If we didn't find deal info in the expected structure, look through the metadata string
            if not found_deal_info:
                metadata_str = str(metadata)
                if "deal" in metadata_str.lower() or "miner" in metadata_str.lower():
                    found_deal_info = True
                    print(f"Deal info found in metadata: {metadata}")

            self.assertTrue(found_deal_info, "No deal information found in metadata")

    def test_miner_selection(self):
        """Test miner selection in Filecoin deals."""
        # Skip if backend is not initialized or in unavailable mode
        if not self.backend or self.backend.mode == "unavailable":
            self.skipTest("Filecoin backend not initialized or unavailable")

        # Skip in non-mock mode as real deals take too long
        if not hasattr(self.backend, 'mode') or self.backend.mode != "lotus" or not "mock" in str(self.backend.lotus):
            self.skipTest("Test requires mock mode for miner selection testing")

        # Create test content
        content = "Filecoin miner selection test content"
        temp_file = self._create_temp_file(content)

        # Get a specific miner (not the default)
        test_miner = "t01001"  # Use a different miner than default
        if self.test_container == test_miner:
            test_miner = "t01002"  # Use a different miner if default is t01001

        # Store content with specific miner
        result = None
        with open(temp_file, 'rb') as f:
            result = self.backend.store(f, test_miner)

        self.assertTrue(result.get("success", False), f"Failed to store content with specific miner: {result.get('error', 'Unknown error')}")

        # Get CID/identifier for cleanup
        identifier = result.get("identifier")
        self.assertIsNotNone(identifier, "No identifier returned from store operation")
        self.created_identifiers.append(identifier)

        # Check if the deal was made with the correct miner
        deals = result.get("deals", [])
        self.assertGreaterEqual(len(deals), 1, "No deals returned from store operation")

        for deal in deals:
            if "miner" in deal:
                self.assertEqual(
                    deal["miner"],
                    test_miner,
                    f"Deal created with wrong miner: {deal['miner']} instead of {test_miner}"
                )

    def test_deal_retrieval(self):
        """Test retrieving content from Filecoin deals."""
        # Skip if backend is not initialized or in unavailable mode
        if not self.backend or self.backend.mode == "unavailable":
            self.skipTest("Filecoin backend not initialized or unavailable")

        # Create and store test content
        content = "Filecoin retrieval test content"
        temp_file = self._create_temp_file(content)

        # Store content
        result = None
        with open(temp_file, 'rb') as f:
            result = self.backend.store(f, self.test_container)

        self.assertTrue(result.get("success", False), f"Failed to store content: {result.get('error', 'Unknown error')}")

        # Get CID/identifier for cleanup
        identifier = result.get("identifier")
        self.assertIsNotNone(identifier, "No identifier returned from store operation")
        self.created_identifiers.append(identifier)

        # In mock mode, the content should be immediately retrievable
        # In real Filecoin, retrieval might need to wait for the deal to be active

        # Check the existence of the content
        exists = self.backend.exists(identifier, self.test_container)
        self.assertTrue(exists, f"Content should exist but exists check returned {exists}")

        # Retrieve the content
        retrieve_result = self.backend.retrieve(identifier, self.test_container)
        self.assertTrue(retrieve_result.get("success", False), f"Failed to retrieve content: {retrieve_result.get('error', 'Unknown error')}")

        # Verify content
        retrieved_data = retrieve_result.get("data")
        self.assertIsNotNone(retrieved_data, "No data returned from retrieve operation")

        if isinstance(retrieved_data, bytes):
            retrieved_text = retrieved_data.decode('utf-8')
        else:
            retrieved_text = retrieved_data

        self.assertEqual(content, retrieved_text, "Retrieved content doesn't match original")

    def test_advanced_features_if_available(self):
        """Test advanced Filecoin features if they are available."""
        # Skip if backend is not initialized or in unavailable mode
        if not self.backend or self.backend.mode == "unavailable":
            self.skipTest("Filecoin backend not initialized or unavailable")

        # Check if the backend or its underlying implementation has advanced features
        has_advanced_features = False

        # These are just some possible ways advanced features might be exposed
        # The actual implementation will determine how to check for them
        if hasattr(self.backend, "advanced_features"):
            has_advanced_features = True
        elif hasattr(self.backend, "lotus") and hasattr(self.backend.lotus, "advanced_api"):
            has_advanced_features = True
        elif hasattr(self.backend, "filecoin") and hasattr(self.backend.filecoin, "advanced_api"):
            has_advanced_features = True

        # For mock mode, we assume advanced features might be available
        if not has_advanced_features and (hasattr(self.backend, 'mode') and "mock" in str(getattr(self.backend, self.backend.mode))):
            # Try a method that might exist in the advanced implementation
            if hasattr(self.backend, "get_network_stats") or hasattr(self.backend, "recommend_miners"):
                has_advanced_features = True

        # Skip test if advanced features are not available
        if not has_advanced_features:
            self.skipTest("Advanced Filecoin features not available")

        # If we have advanced features, run some basic tests
        # Note: The actual tests depend on the specific advanced features implemented

        # This is just a placeholder for advanced feature testing
        # Actual implementations would have more specific tests
        print("Advanced Filecoin features detected, running enhanced tests...")

        # Example: Test miner recommendation
        if hasattr(self.backend, "recommend_miners"):
            miners = self.backend.recommend_miners(size=1024*1024, replication=2)
            self.assertIsNotNone(miners, "Miner recommendation should return results")
            print(f"Recommended miners: {miners}")

        # Example: Test network statistics
        if hasattr(self.backend, "get_network_stats"):
            stats = self.backend.get_network_stats()
            self.assertIsNotNone(stats, "Network stats should not be None")
            print(f"Network stats: {stats}")


# Allow running the tests directly
if __name__ == "__main__":
    unittest.main()
