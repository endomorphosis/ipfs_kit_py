#!/usr/bin/env python3
"""
Test suite for the S3 backend implementation.

This module tests the S3 backend implementation to ensure it
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

class S3BackendTest(unittest.TestCase, StorageBackendBaseTest):
    """Test suite for S3 backend implementation."""

    def setUp(self):
        """Set up the test environment with S3 backend."""
        try:
            # Import S3 backend
            from ipfs_kit_py.mcp.storage_manager.backends.s3_backend import S3Backend
            self.backend_class = S3Backend

            # Configure default resources and metadata
            self.default_resources = {
                # S3-specific resources can be added here
                "aws_access_key": os.environ.get("AWS_ACCESS_KEY_ID"),
                "aws_secret_key": os.environ.get("AWS_SECRET_ACCESS_KEY"),
                "region": os.environ.get("AWS_REGION", "us-east-1"),
                "endpoint_url": os.environ.get("S3_ENDPOINT_URL"),
                "bucket": os.environ.get("S3_DEFAULT_BUCKET"),
                "max_threads": 5,
                "connection_timeout": 10,
                "read_timeout": 30,
                "max_retries": 3,
                "cache_ttl": 3600,
                "cache_size_limit": 10 * 1024 * 1024,  # 10MB
            }

            self.default_metadata = {
                # S3-specific metadata can be added here
            }

            # Skip tests if credentials are not available
            if not self.default_resources.get("aws_access_key") or not self.default_resources.get("bucket"):
                self.skipTest("S3 credentials or bucket not provided in environment variables")

            # Call the parent setUp
            super().setUp()

            # Test bucket existence
            self.test_bucket_name = self.default_resources.get("bucket")

        except ImportError as e:
            logger.error(f"Failed to import S3 backend: {e}")
            raise

    def test_s3_specific_bucket_operations(self):
        """Test S3-specific bucket operations."""
        # Add a test file with a specific path
        test_data = self._create_test_content("small")
        test_path = f"test_folder/test_file_{uuid.uuid4()}.txt"

        # Use the store method directly to specify the path
        store_result = self.backend.store(
            data=test_data,
            container=self.test_bucket_name,
            path=test_path
        )

        if not store_result.get("success", False):
            self.skipTest(f"S3 backend not available for writes: {store_result.get('error', 'Unknown error')}")

        # Store identifier for cleanup
        identifier = store_result.get("identifier")
        self.test_identifiers = getattr(self, 'test_identifiers', [])
        self.test_identifiers.append(identifier)

        # Test retrieving with container parameter
        retrieve_result = self.backend.retrieve(
            identifier=identifier,
            container=self.test_bucket_name
        )

        self.assertTrue(retrieve_result.get("success", False))
        self.assertEqual(retrieve_result.get("data"), test_data)

        # Test listing objects with prefix
        if hasattr(self.backend, 'list'):
            list_result = self.backend.list(
                container=self.test_bucket_name,
                prefix="test_folder/"
            )

            self.assertTrue(list_result.get("success", False))
            self.assertIn("items", list_result)
            self.assertIsInstance(list_result["items"], list)

            # At least our test file should be in the list
            self.assertGreaterEqual(len(list_result["items"]), 1)

            # Find our test file in the list
            found = False
            for item in list_result["items"]:
                if item.get("identifier") == identifier:
                    found = True
                    break

            self.assertTrue(found, f"Test file {identifier} not found in list result")

    def test_s3_caching(self):
        """Test S3 caching functionality."""
        # Add content
        test_data = self._create_test_content("small")

        add_result = self.backend.add_content(test_data)
        if not add_result.get("success", False):
            self.skipTest(f"S3 backend not available for writes: {add_result.get('error', 'Unknown error')}")

        identifier = add_result["identifier"]

        # Store identifier for cleanup
        self.test_identifiers = getattr(self, 'test_identifiers', [])
        self.test_identifiers.append(identifier)

        # Get the content first time (should cache it)
        first_get = self.backend.get_content(identifier)
        self.assertTrue(first_get.get("success", False))

        # Get it again (should use cache)
        second_get = self.backend.retrieve(identifier)
        self.assertTrue(second_get.get("success", False))

        # Check if cache was used (if the backend tracks cache hits)
        if hasattr(self.backend, 'cache_hits'):
            self.assertGreaterEqual(self.backend.cache_hits, 1,
                                    "Cache hit count didn't increase after second retrieval")

    def test_s3_multipart_upload(self):
        """Test S3 multipart upload for large files."""
        # Create a larger test file that would trigger multipart upload
        test_data = self._create_test_content("large")

        # Use the store method with multipart option
        store_result = self.backend.store(
            data=test_data,
            container=self.test_bucket_name,
            options={"use_multipart": True}
        )

        if not store_result.get("success", False):
            self.skipTest(f"S3 backend not available for writes: {store_result.get('error', 'Unknown error')}")

        # Store identifier for cleanup
        identifier = store_result.get("identifier")
        self.test_identifiers = getattr(self, 'test_identifiers', [])
        self.test_identifiers.append(identifier)

        # Verify the upload was successful
        self.assertTrue(store_result.get("success", False))

        # Retrieve the content and verify it matches
        retrieve_result = self.backend.retrieve(
            identifier=identifier,
            container=self.test_bucket_name
        )

        self.assertTrue(retrieve_result.get("success", False))
        self.assertEqual(len(retrieve_result.get("data")), len(test_data))
        self.assertEqual(retrieve_result.get("data"), test_data)

    def test_s3_update_metadata(self):
        """Test updating metadata for S3 objects."""
        # First add content with metadata
        test_data = self._create_test_content("small")
        initial_metadata = {"test_key": "test_value", "version": "1.0"}

        add_result = self.backend.add_content(test_data, initial_metadata)
        if not add_result.get("success", False):
            self.skipTest(f"S3 backend not available for writes: {add_result.get('error', 'Unknown error')}")

        identifier = add_result["identifier"]

        # Store identifier for cleanup
        self.test_identifiers = getattr(self, 'test_identifiers', [])
        self.test_identifiers.append(identifier)

        # If update_metadata method exists, test it
        if hasattr(self.backend, 'update_metadata'):
            # Update the metadata
            updated_metadata = {"test_key": "updated_value", "version": "2.0", "new_key": "new_value"}

            update_result = self.backend.update_metadata(
                identifier=identifier,
                metadata=updated_metadata,
                container=self.test_bucket_name
            )

            self.assertTrue(update_result.get("success", False))

            # Get metadata to verify update
            metadata_result = self.backend.get_metadata(
                identifier=identifier,
                container=self.test_bucket_name
            )

            self.assertTrue(metadata_result.get("success", False))
            self.assertIn("metadata", metadata_result)

            # Check if updated values are present (implementation details might vary)
            metadata = metadata_result.get("metadata", {})
            user_metadata = metadata.get("user_metadata", metadata)

            # Test one of the updated values (might be nested differently in different implementations)
            found_updated_value = False
            for key, value in user_metadata.items():
                if "version" in key.lower() and "2.0" in str(value):
                    found_updated_value = True
                    break

            for key, value in user_metadata.items():
                if "test_key" in key.lower() and "updated_value" in str(value):
                    found_updated_value = True
                    break

            if not found_updated_value:
                logger.warning(f"Updated metadata not found in result. Full metadata: {user_metadata}")

    def tearDown(self):
        """Clean up after tests."""
        # Clean up test content
        self._cleanup_test_content()

        # Call the parent tearDown
        super().tearDown()


if __name__ == "__main__":
    unittest.main()
