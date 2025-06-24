"""
S3 Backend Test Suite

This module provides comprehensive tests for the S3 backend implementation,
ensuring that all required functionality works correctly.
"""

import os
import uuid
import unittest
from typing import Dict, Any

from .base_backend_test import BaseBackendTest
from ipfs_kit_py.mcp.storage_manager.backends.s3_backend import S3Backend
from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType


class S3BackendTest(BaseBackendTest):
    """Test class for the S3 backend implementation."""

    def setUp(self):
        """Set up the test environment with an S3 backend."""
        super().setUp()
        self.backend_name = "S3"

        # Generate a unique test bucket name for isolation
        test_bucket_suffix = uuid.uuid4().hex[:8]
        self.test_bucket_name = f"mcp-test-{test_bucket_suffix}"

        # Load configuration from environment variables or use defaults for testing
        resources = {
            "aws_access_key": os.environ.get("AWS_ACCESS_KEY_ID", ""),
            "aws_secret_key": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
            "region": os.environ.get("AWS_REGION", "us-east-1"),
            "endpoint_url": os.environ.get("S3_ENDPOINT_URL", ""),
            "bucket": self.test_bucket_name,
            "mock_mode": os.environ.get("S3_MOCK_MODE", "true").lower() in ("true", "1", "yes"),
            "max_threads": 5,
            "connection_timeout": 10,
            "read_timeout": 30,
            "max_retries": 3
        }

        metadata = {
            "cache_ttl": 3600,  # 1 hour
            "cache_size_limit": 100 * 1024 * 1024  # 100MB
        }

        # Skip test if no credentials provided and not in mock mode
        if not resources["aws_access_key"] and not resources["mock_mode"]:
            self.skipTest("AWS credentials not provided and mock mode disabled")

        # Initialize the S3 backend
        try:
            self.backend = S3Backend(resources, metadata)
            self.test_container = self.test_bucket_name

            # Create test bucket if it doesn't exist
            self._ensure_test_bucket()
        except Exception as e:
            self.skipTest(f"Failed to initialize S3 backend: {e}")

    def tearDown(self):
        """Clean up after tests, including removing the test bucket."""
        # Clean up created test objects
        super().tearDown()

        # Clean up test bucket
        if hasattr(self, "backend") and self.backend and not self.backend.connection.mock_mode:
            try:
                self._cleanup_test_bucket()
            except Exception as e:
                print(f"Warning: Failed to clean up test bucket: {e}")

    def _ensure_test_bucket(self):
        """Ensure the test bucket exists."""
        # Skip if in mock mode
        if self.backend.connection.mock_mode:
            return

        try:
            # Check if bucket exists
            self.backend.connection.s3_client.head_bucket(Bucket=self.test_bucket_name)
        except Exception:
            # Bucket doesn't exist, create it
            try:
                self.backend.connection.s3_client.create_bucket(Bucket=self.test_bucket_name)
                print(f"Created test bucket: {self.test_bucket_name}")
            except Exception as e:
                raise Exception(f"Failed to create test bucket: {e}")

    def _cleanup_test_bucket(self):
        """Clean up the test bucket by deleting all objects and the bucket itself."""
        # Skip if in mock mode
        if self.backend.connection.mock_mode:
            return

        try:
            # Delete all objects in the bucket
            paginator = self.backend.connection.s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=self.test_bucket_name):
                if 'Contents' in page:
                    delete_keys = {'Objects': [{'Key': obj['Key']} for obj in page['Contents']]}
                    self.backend.connection.s3_client.delete_objects(
                        Bucket=self.test_bucket_name, Delete=delete_keys
                    )

            # Delete the bucket
            self.backend.connection.s3_client.delete_bucket(Bucket=self.test_bucket_name)
            print(f"Deleted test bucket: {self.test_bucket_name}")
        except Exception as e:
            print(f"Warning: Error cleaning up test bucket: {e}")

    def test_s3_specific_path_handling(self):
        """Test S3-specific path handling with keys and prefixes."""
        # Skip if backend is not initialized
        if not self.backend:
            self.skipTest("S3 backend not initialized")

        # Store content with a path containing folders
        content = "S3 path test content"
        path = "folder1/folder2/test.txt"

        # Store the content
        result = self.backend.store(content, self.test_container, path)
        self.assertTrue(result.get("success", False), f"Failed to store content with path: {result.get('error', 'Unknown error')}")

        # Get identifier for cleanup
        identifier = result.get("identifier")
        self.assertIsNotNone(identifier, "No identifier returned from store operation")
        self.created_identifiers.append(identifier)

        # Test prefix listing
        list_result = self.backend.list(self.test_container, "folder1/")
        self.assertTrue(list_result.get("success", False), f"Failed to list by prefix: {list_result.get('error', 'Unknown error')}")

        items = list_result.get("items", [])
        self.assertGreaterEqual(len(items), 1, "List should return at least one item")

        # Check if our item is in the list
        found = False
        for item in items:
            if item.get("identifier") == identifier:
                found = True
                break

        self.assertTrue(found, "Created item not found in prefix listing")

    def test_cache_functionality(self):
        """Test caching functionality of the S3 backend."""
        # Skip if backend is not initialized
        if not self.backend:
            self.skipTest("S3 backend not initialized")

        # Store content
        content = "S3 cache test content"
        path = "cache-test.txt"

        # Store with cache enabled
        options = {"cache": True}
        result = self.backend.store(content, self.test_container, path, options)
        self.assertTrue(result.get("success", False), f"Failed to store content: {result.get('error', 'Unknown error')}")

        identifier = result.get("identifier")
        self.assertIsNotNone(identifier, "No identifier returned from store operation")
        self.created_identifiers.append(identifier)

        # Retrieve first time (should go to S3)
        first_retrieve = self.backend.retrieve(identifier, self.test_container, {"use_cache": True})
        self.assertTrue(first_retrieve.get("success", False), f"Failed to retrieve content: {first_retrieve.get('error', 'Unknown error')}")

        # Retrieve second time (should use cache if available)
        second_retrieve = self.backend.retrieve(identifier, self.test_container, {"use_cache": True})
        self.assertTrue(second_retrieve.get("success", False), f"Failed to retrieve cached content: {second_retrieve.get('error', 'Unknown error')}")

        # Verify the second retrieval has cache information or matches the first retrieval
        self.assertEqual(
            first_retrieve.get("data"),
            second_retrieve.get("data"),
            "Cached content should match original content"
        )

        # Retrieve with cache disabled (should go to S3)
        direct_retrieve = self.backend.retrieve(identifier, self.test_container, {"use_cache": False})
        self.assertTrue(direct_retrieve.get("success", False), f"Failed to retrieve content directly: {direct_retrieve.get('error', 'Unknown error')}")

        self.assertEqual(
            first_retrieve.get("data"),
            direct_retrieve.get("data"),
            "Direct retrieval content should match original content"
        )

    def test_multipart_upload_simulation(self):
        """Test multipart upload functionality (simulated for testing)."""
        # Skip if backend is not initialized
        if not self.backend:
            self.skipTest("S3 backend not initialized")

        # Create a moderate-sized content to simulate multipart upload
        # Note: We're not using a truly large file to keep tests fast
        content = b"S3 multipart test content " * 1000  # ~25KB
        path = "multipart-test.bin"

        # Store with multipart option
        options = {"use_multipart": True}
        result = self.backend.store(content, self.test_container, path, options)
        self.assertTrue(result.get("success", False), f"Failed to store content: {result.get('error', 'Unknown error')}")

        identifier = result.get("identifier")
        self.assertIsNotNone(identifier, "No identifier returned from store operation")
        self.created_identifiers.append(identifier)

        # Retrieve the content
        retrieve_result = self.backend.retrieve(identifier, self.test_container)
        self.assertTrue(retrieve_result.get("success", False), f"Failed to retrieve content: {retrieve_result.get('error', 'Unknown error')}")

        # Verify content
        retrieved_data = retrieve_result.get("data")
        self.assertIsNotNone(retrieved_data, "No data returned from retrieve operation")
        self.assertEqual(content, retrieved_data, "Retrieved content doesn't match original")


# Allow running the tests directly
if __name__ == "__main__":
    unittest.main()
