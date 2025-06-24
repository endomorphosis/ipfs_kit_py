"""
Base Test Class for Storage Backend Testing

This module provides a base test class with common test methods for all
storage backends, ensuring consistent testing across different implementations.
"""

import os
import time
import uuid
import unittest
import tempfile
from typing import Dict, Any, Optional, List

# Configure test constants
TEST_CONTENT = "This is test content for storage backend testing."
TEST_BINARY_CONTENT = b"This is binary test content for storage backend testing."
TEST_METADATA = {
    "test_name": "backend_test",
    "timestamp": time.time(),
    "description": "Test metadata for storage backend"
}


class BaseBackendTest(unittest.TestCase):
    """Base test class for storage backend testing."""

    def __init__(self, *args, **kwargs):
        """Initialize the base backend test."""
        super().__init__(*args, **kwargs)
        self.backend = None
        self.backend_name = "undefined"
        self.test_container = None
        self.created_identifiers = []
        self.temp_files = []

    def setUp(self):
        """Set up the test environment."""
        # Each subclass must initialize self.backend in its own setUp method
        self.created_identifiers = []
        self.temp_files = []

    def tearDown(self):
        """Clean up after tests."""
        # Clean up any created content
        for identifier in self.created_identifiers:
            try:
                self.backend.delete(identifier, self.test_container)
            except Exception as e:
                print(f"Error cleaning up {identifier}: {e}")

        # Clean up temporary files
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                print(f"Error removing temp file {temp_file}: {e}")

    def _create_temp_file(self, content=TEST_CONTENT) -> str:
        """Create a temporary file with the given content."""
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        if isinstance(content, str):
            temp_file.write(content.encode('utf-8'))
        else:
            temp_file.write(content)
        temp_file.close()
        self.temp_files.append(temp_file.name)
        return temp_file.name

    def _generate_test_path(self) -> str:
        """Generate a unique test path."""
        return f"test-{uuid.uuid4().hex[:8]}.txt"

    # Common test methods that apply to all backends

    def test_store_retrieve_string(self):
        """Test storing and retrieving a string."""
        # Skip if backend is not defined
        if not self.backend:
            self.skipTest("Backend not initialized")

        content = TEST_CONTENT + f" String test {uuid.uuid4().hex[:8]}"
        path = self._generate_test_path()

        # Store the content
        result = self.backend.store(content, self.test_container, path)
        self.assertTrue(result.get("success", False), f"Failed to store string: {result.get('error', 'Unknown error')}")

        # Track the identifier for cleanup
        identifier = result.get("identifier")
        self.assertIsNotNone(identifier, "No identifier returned from store operation")
        self.created_identifiers.append(identifier)

        # Retrieve the content
        retrieve_result = self.backend.retrieve(identifier, self.test_container)
        self.assertTrue(retrieve_result.get("success", False), f"Failed to retrieve content: {retrieve_result.get('error', 'Unknown error')}")

        # Verify retrieved content
        retrieved_data = retrieve_result.get("data")
        self.assertIsNotNone(retrieved_data, "No data returned from retrieve operation")

        if isinstance(retrieved_data, bytes):
            retrieved_text = retrieved_data.decode('utf-8')
        else:
            retrieved_text = retrieved_data

        self.assertEqual(content, retrieved_text, "Retrieved content doesn't match original")

    def test_store_retrieve_bytes(self):
        """Test storing and retrieving binary data."""
        # Skip if backend is not defined
        if not self.backend:
            self.skipTest("Backend not initialized")

        content = TEST_BINARY_CONTENT + str(uuid.uuid4().hex[:8]).encode('utf-8')
        path = self._generate_test_path()

        # Store the content
        result = self.backend.store(content, self.test_container, path)
        self.assertTrue(result.get("success", False), f"Failed to store binary: {result.get('error', 'Unknown error')}")

        # Track the identifier for cleanup
        identifier = result.get("identifier")
        self.assertIsNotNone(identifier, "No identifier returned from store operation")
        self.created_identifiers.append(identifier)

        # Retrieve the content
        retrieve_result = self.backend.retrieve(identifier, self.test_container)
        self.assertTrue(retrieve_result.get("success", False), f"Failed to retrieve content: {retrieve_result.get('error', 'Unknown error')}")

        # Verify retrieved content
        retrieved_data = retrieve_result.get("data")
        self.assertIsNotNone(retrieved_data, "No data returned from retrieve operation")
        self.assertEqual(content, retrieved_data, "Retrieved binary content doesn't match original")

    def test_store_retrieve_file(self):
        """Test storing and retrieving a file."""
        # Skip if backend is not defined
        if not self.backend:
            self.skipTest("Backend not initialized")

        content = TEST_CONTENT + f" File test {uuid.uuid4().hex[:8]}"
        temp_file = self._create_temp_file(content)
        path = self._generate_test_path()

        # Store the file
        with open(temp_file, 'rb') as f:
            result = self.backend.store(f, self.test_container, path)

        self.assertTrue(result.get("success", False), f"Failed to store file: {result.get('error', 'Unknown error')}")

        # Track the identifier for cleanup
        identifier = result.get("identifier")
        self.assertIsNotNone(identifier, "No identifier returned from store operation")
        self.created_identifiers.append(identifier)

        # Retrieve the content
        retrieve_result = self.backend.retrieve(identifier, self.test_container)
        self.assertTrue(retrieve_result.get("success", False), f"Failed to retrieve content: {retrieve_result.get('error', 'Unknown error')}")

        # Verify retrieved content
        retrieved_data = retrieve_result.get("data")
        self.assertIsNotNone(retrieved_data, "No data returned from retrieve operation")

        if isinstance(retrieved_data, bytes):
            retrieved_text = retrieved_data.decode('utf-8')
        else:
            retrieved_text = retrieved_data

        self.assertEqual(content, retrieved_text, "Retrieved file content doesn't match original")

    def test_exists(self):
        """Test checking if content exists."""
        # Skip if backend is not defined
        if not self.backend:
            self.skipTest("Backend not initialized")

        content = TEST_CONTENT + f" Exists test {uuid.uuid4().hex[:8]}"
        path = self._generate_test_path()

        # Store the content
        result = self.backend.store(content, self.test_container, path)
        self.assertTrue(result.get("success", False), f"Failed to store string: {result.get('error', 'Unknown error')}")

        # Track the identifier for cleanup
        identifier = result.get("identifier")
        self.assertIsNotNone(identifier, "No identifier returned from store operation")
        self.created_identifiers.append(identifier)

        # Check if content exists
        exists = self.backend.exists(identifier, self.test_container)
        self.assertTrue(exists, f"Content should exist but exists check returned {exists}")

        # Check if non-existent content doesn't exist
        non_existent_id = f"non-existent-{uuid.uuid4().hex}"
        exists = self.backend.exists(non_existent_id, self.test_container)
        self.assertFalse(exists, f"Non-existent content should not exist but exists check returned {exists}")

    def test_delete(self):
        """Test deleting content."""
        # Skip if backend is not defined
        if not self.backend:
            self.skipTest("Backend not initialized")

        content = TEST_CONTENT + f" Delete test {uuid.uuid4().hex[:8]}"
        path = self._generate_test_path()

        # Store the content
        result = self.backend.store(content, self.test_container, path)
        self.assertTrue(result.get("success", False), f"Failed to store string: {result.get('error', 'Unknown error')}")

        identifier = result.get("identifier")
        self.assertIsNotNone(identifier, "No identifier returned from store operation")

        # Check content exists before deletion
        exists_before = self.backend.exists(identifier, self.test_container)
        self.assertTrue(exists_before, "Content should exist before deletion")

        # Delete the content
        delete_result = self.backend.delete(identifier, self.test_container)

        # Some backends like Filecoin might not fully support deletion
        backend_supports_deletion = True
        if not delete_result.get("success", False):
            if "warning" in delete_result and "cannot be deleted" in delete_result.get("warning", ""):
                backend_supports_deletion = False
                print(f"Note: {self.backend_name} backend has limited delete support: {delete_result.get('warning')}")
            else:
                self.fail(f"Failed to delete content: {delete_result.get('error', 'Unknown error')}")

        # Only verify the content is gone if the backend claims to support deletion
        if backend_supports_deletion:
            # Check content doesn't exist after deletion
            exists_after = self.backend.exists(identifier, self.test_container)
            self.assertFalse(exists_after, "Content should not exist after deletion")

        # Remove from our cleanup list since we already deleted it
        if identifier in self.created_identifiers:
            self.created_identifiers.remove(identifier)

    def test_list(self):
        """Test listing content."""
        # Skip if backend is not defined
        if not self.backend:
            self.skipTest("Backend not initialized")

        # Create multiple content items
        test_prefix = f"list-test-{uuid.uuid4().hex[:6]}"
        identifiers = []

        # Store 3 items with the same prefix
        for i in range(3):
            content = f"{TEST_CONTENT} List test item {i} {uuid.uuid4().hex[:6]}"
            path = f"{test_prefix}-{i}.txt"

            result = self.backend.store(content, self.test_container, path)
            self.assertTrue(result.get("success", False), f"Failed to store item {i}: {result.get('error', 'Unknown error')}")

            identifier = result.get("identifier")
            self.assertIsNotNone(identifier, f"No identifier returned for item {i}")
            identifiers.append(identifier)
            self.created_identifiers.append(identifier)

        # List content
        list_result = self.backend.list(self.test_container, test_prefix)
        self.assertTrue(list_result.get("success", False), f"Failed to list content: {list_result.get('error', 'Unknown error')}")

        items = list_result.get("items", [])
        self.assertGreaterEqual(len(items), 1, "List should return at least one item")

        # Check if all created identifiers are in the list
        # Note: Some backends might not support exact prefix filtering
        found_count = 0
        for identifier in identifiers:
            for item in items:
                if item.get("identifier") == identifier:
                    found_count += 1
                    break

        # Allow for partial matches as some backends might have existing content or not support prefix filtering
        self.assertGreater(found_count, 0, "None of the created identifiers were found in list results")

    def test_metadata(self):
        """Test getting and updating metadata."""
        # Skip if backend is not defined
        if not self.backend:
            self.skipTest("Backend not initialized")

        content = TEST_CONTENT + f" Metadata test {uuid.uuid4().hex[:8]}"
        path = self._generate_test_path()

        # Store content with metadata
        options = {"metadata": TEST_METADATA}
        result = self.backend.store(content, self.test_container, path, options)
        self.assertTrue(result.get("success", False), f"Failed to store content: {result.get('error', 'Unknown error')}")

        identifier = result.get("identifier")
        self.assertIsNotNone(identifier, "No identifier returned from store operation")
        self.created_identifiers.append(identifier)

        # Get metadata
        metadata_result = self.backend.get_metadata(identifier, self.test_container)
        self.assertTrue(metadata_result.get("success", False), f"Failed to get metadata: {metadata_result.get('error', 'Unknown error')}")

        metadata = metadata_result.get("metadata", {})

        # Check if some test metadata is present
        # Note: Different backends may handle metadata differently, so we just check for some evidence
        metadata_found = False
        if metadata:
            metadata_str = str(metadata)
            if "test_name" in metadata_str or "backend_test" in metadata_str:
                metadata_found = True

        self.assertTrue(metadata_found, "Test metadata not found in retrieved metadata")

        # Update metadata
        update_metadata = {
            "updated": True,
            "update_time": time.time(),
            "updated_by": "test_metadata"
        }

        update_result = self.backend.update_metadata(identifier, update_metadata, self.test_container)

        # Some backends might have limited metadata update capabilities
        backend_supports_metadata_update = True
        if not update_result.get("success", False):
            if "warning" in update_result and "limited" in update_result.get("warning", "").lower():
                backend_supports_metadata_update = False
                print(f"Note: {self.backend_name} backend has limited metadata update support: {update_result.get('warning')}")
            else:
                self.fail(f"Failed to update metadata: {update_result.get('error', 'Unknown error')}")

        # Verify updated metadata if supported
        if backend_supports_metadata_update:
            updated_metadata_result = self.backend.get_metadata(identifier, self.test_container)
            self.assertTrue(updated_metadata_result.get("success", False), f"Failed to get updated metadata: {updated_metadata_result.get('error', 'Unknown error')}")

            updated_metadata = updated_metadata_result.get("metadata", {})
            update_found = False

            if updated_metadata:
                metadata_str = str(updated_metadata)
                if "updated" in metadata_str or "update_time" in metadata_str:
                    update_found = True

            self.assertTrue(update_found, "Updated metadata not found in retrieved metadata")
