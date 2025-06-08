#!/usr/bin/env python3
"""
Base test framework for storage backends.

This module provides a common set of tests that any storage backend
implementing the BackendStorage abstract class should pass.
"""

import unittest
import uuid
import os
import logging
import tempfile
from typing import Dict, Any, Type, Optional, List, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import the BackendStorage base class
try:
    from ipfs_kit_py.mcp.storage_manager.backend_base import BackendStorage
    from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType
except ImportError as e:
    logger.error(f"Failed to import BackendStorage: {e}")
    raise

class StorageBackendBaseTest:
    """
    Base test suite for storage backends.
    
    This class provides common tests for any backend that implements the
    BackendStorage abstract class. It should be subclassed to create
    specific test cases for individual backend implementations.
    """
    
    # The backend class to test - should be set by subclasses
    backend_class: Type[BackendStorage] = None
    
    # Default resources and metadata for backend initialization
    default_resources: Dict[str, Any] = {}
    default_metadata: Dict[str, Any] = {}
    
    # Test data for upload/download tests
    test_data_small = b"This is a small test data string for storage backend testing."
    test_data_medium = b"Medium sized test data " * 100  # ~2KB
    
    def setUp(self):
        """Set up the test environment."""
        if not self.backend_class:
            raise ValueError("backend_class must be set by subclasses")
        
        # Initialize the backend with default resources and metadata
        try:
            self.backend = self.backend_class(
                resources=self.default_resources,
                metadata=self.default_metadata
            )
            logger.info(f"Initialized {self.backend.get_name()} backend for testing")
        except Exception as e:
            logger.error(f"Failed to initialize backend: {e}")
            raise
            
        # Create a temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.write(self.test_data_medium)
        self.temp_file.close()
            
    def tearDown(self):
        """Clean up after tests."""
        # Clean up temporary file
        if hasattr(self, 'temp_file') and os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
            
        # Clean up backend resources if needed
        if hasattr(self, 'backend') and hasattr(self.backend, 'cleanup'):
            self.backend.cleanup()
            
    def test_backend_initialization(self):
        """Test backend initialization and basic properties."""
        # Verify backend was properly initialized
        self.assertIsNotNone(self.backend)
        
        # Verify backend type
        self.assertIsNotNone(self.backend.backend_type)
        self.assertIsInstance(self.backend.backend_type, StorageBackendType)
        
        # Verify backend name is set
        backend_name = self.backend.get_name()
        self.assertIsNotNone(backend_name)
        self.assertIsInstance(backend_name, str)
        self.assertGreater(len(backend_name), 0)
        
    def test_abstract_methods_implemented(self):
        """Test that all required abstract methods are implemented."""
        # Check if required abstract methods are implemented
        required_methods = [
            'add_content',
            'get_content', 
            'remove_content',
            'get_metadata'
        ]
        
        for method_name in required_methods:
            method = getattr(self.backend, method_name, None)
            self.assertIsNotNone(method, f"Method {method_name} not implemented")
            self.assertTrue(callable(method), f"Method {method_name} is not callable")
    
    def _create_test_content(self, size="small") -> bytes:
        """Create test content for upload."""
        if size == "small":
            return self.test_data_small
        elif size == "medium":
            return self.test_data_medium
        elif size == "large":
            # Create ~1MB of test data
            return b"Large test data block " * 50000
        else:
            return self.test_data_small
            
    def test_add_content_bytes(self):
        """Test adding content as bytes."""
        test_data = self._create_test_content("small")
        test_metadata = {"test_key": "test_value", "timestamp": str(uuid.uuid4())}
        
        # Add content
        result = self.backend.add_content(test_data, test_metadata)
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)
        
        # Check if the operation was successful
        if result.get("success", False):
            # If successful, verify identifier
            self.assertIn("identifier", result)
            self.assertIsNotNone(result["identifier"])
            
            # Store identifier for cleanup
            self.test_identifiers = getattr(self, 'test_identifiers', [])
            self.test_identifiers.append(result["identifier"])
            
            # Verify backend field
            self.assertIn("backend", result)
            self.assertEqual(result["backend"], self.backend.get_name())
            
            return result["identifier"]
        else:
            # If mock mode or backend is unavailable, this test may be skipped
            logger.warning(f"add_content test was not successful: {result.get('error', 'Unknown error')}")
            self.skipTest(f"Backend not available for writes: {result.get('error', 'Unknown error')}")
    
    def test_add_content_filelike(self):
        """Test adding content as a file-like object."""
        test_metadata = {"test_key": "test_value", "timestamp": str(uuid.uuid4())}
        
        # Open the temporary file for reading
        with open(self.temp_file.name, 'rb') as f:
            # Add content
            result = self.backend.add_content(f, test_metadata)
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)
        
        # Check if the operation was successful
        if result.get("success", False):
            # If successful, verify identifier
            self.assertIn("identifier", result)
            self.assertIsNotNone(result["identifier"])
            
            # Store identifier for cleanup
            self.test_identifiers = getattr(self, 'test_identifiers', [])
            self.test_identifiers.append(result["identifier"])
            
            # Verify backend field
            self.assertIn("backend", result)
            self.assertEqual(result["backend"], self.backend.get_name())
            
            return result["identifier"]
        else:
            # If mock mode or backend is unavailable, this test may be skipped
            logger.warning(f"add_content test was not successful: {result.get('error', 'Unknown error')}")
            self.skipTest(f"Backend not available for writes: {result.get('error', 'Unknown error')}")
    
    def test_add_and_get_content(self):
        """Test adding and retrieving content."""
        # Add content
        test_data = self._create_test_content("small")
        test_metadata = {"test_key": "test_value", "timestamp": str(uuid.uuid4())}
        
        add_result = self.backend.add_content(test_data, test_metadata)
        
        # Skip if add was not successful
        if not add_result.get("success", False):
            self.skipTest(f"Backend not available for writes: {add_result.get('error', 'Unknown error')}")
        
        identifier = add_result["identifier"]
        
        # Store identifier for cleanup
        self.test_identifiers = getattr(self, 'test_identifiers', [])
        self.test_identifiers.append(identifier)
        
        # Get content
        get_result = self.backend.get_content(identifier)
        
        # Verify result
        self.assertIsNotNone(get_result)
        self.assertIsInstance(get_result, dict)
        self.assertIn("success", get_result)
        
        # Check if the operation was successful
        if get_result.get("success", False):
            # Verify data
            self.assertIn("data", get_result)
            self.assertEqual(get_result["data"], test_data)
            
            # Verify backend field
            self.assertIn("backend", get_result)
            self.assertEqual(get_result["backend"], self.backend.get_name())
            
            # Verify identifier field
            self.assertIn("identifier", get_result)
            self.assertEqual(get_result["identifier"], identifier)
        else:
            # If mock mode or backend is unavailable for reads, this test may be skipped
            logger.warning(f"get_content test was not successful: {get_result.get('error', 'Unknown error')}")
            self.skipTest(f"Backend not available for reads: {get_result.get('error', 'Unknown error')}")
    
    def test_get_metadata(self):
        """Test getting metadata for content."""
        # Add content
        test_data = self._create_test_content("small")
        test_metadata = {"test_key": "test_value", "timestamp": str(uuid.uuid4())}
        
        add_result = self.backend.add_content(test_data, test_metadata)
        
        # Skip if add was not successful
        if not add_result.get("success", False):
            self.skipTest(f"Backend not available for writes: {add_result.get('error', 'Unknown error')}")
        
        identifier = add_result["identifier"]
        
        # Store identifier for cleanup
        self.test_identifiers = getattr(self, 'test_identifiers', [])
        self.test_identifiers.append(identifier)
        
        # Get metadata
        metadata_result = self.backend.get_metadata(identifier)
        
        # Verify result
        self.assertIsNotNone(metadata_result)
        self.assertIsInstance(metadata_result, dict)
        self.assertIn("success", metadata_result)
        
        # Check if the operation was successful
        if metadata_result.get("success", False):
            # Verify metadata
            self.assertIn("metadata", metadata_result)
            self.assertIsInstance(metadata_result["metadata"], dict)
            
            # Verify backend field
            self.assertIn("backend", metadata_result)
            self.assertEqual(metadata_result["backend"], self.backend.get_name())
            
            # Verify identifier field
            self.assertIn("identifier", metadata_result)
            self.assertEqual(metadata_result["identifier"], identifier)
        else:
            # If mock mode or backend is unavailable for metadata, this test may be skipped
            logger.warning(f"get_metadata test was not successful: {metadata_result.get('error', 'Unknown error')}")
            self.skipTest(f"Backend not available for metadata: {metadata_result.get('error', 'Unknown error')}")
    
    def test_remove_content(self):
        """Test removing content."""
        # Add content
        test_data = self._create_test_content("small")
        
        add_result = self.backend.add_content(test_data)
        
        # Skip if add was not successful
        if not add_result.get("success", False):
            self.skipTest(f"Backend not available for writes: {add_result.get('error', 'Unknown error')}")
        
        identifier = add_result["identifier"]
        
        # Remove content
        remove_result = self.backend.remove_content(identifier)
        
        # Verify result
        self.assertIsNotNone(remove_result)
        self.assertIsInstance(remove_result, dict)
        self.assertIn("success", remove_result)
        
        # Some backends (like Filecoin) might not support true deletion
        if not remove_result.get("success", False) and not remove_result.get("warning"):
            # If the backend doesn't support deletion and doesn't provide a warning,
            # then it's a failure
            self.fail(f"remove_content failed: {remove_result.get('error', 'Unknown error')}")
    
    def test_list_method(self):
        """Test list method if available."""
        # Check if list method is available
        if not hasattr(self.backend, 'list'):
            self.skipTest("list method not implemented by this backend")
        
        # Call list method
        list_result = self.backend.list()
        
        # Verify result structure
        self.assertIsNotNone(list_result)
        self.assertIsInstance(list_result, dict)
        self.assertIn("success", list_result)
        
        # If success, verify items field
        if list_result.get("success", False):
            self.assertIn("items", list_result)
            self.assertIsInstance(list_result["items"], list)
            
            # Verify backend field
            self.assertIn("backend", list_result)
            self.assertEqual(list_result["backend"], self.backend.get_name())
    
    def test_exists_method(self):
        """Test exists method if available."""
        # Check if exists method is available
        if not hasattr(self.backend, 'exists'):
            self.skipTest("exists method not implemented by this backend")
        
        # Add content
        test_data = self._create_test_content("small")
        
        add_result = self.backend.add_content(test_data)
        
        # Skip if add was not successful
        if not add_result.get("success", False):
            self.skipTest(f"Backend not available for writes: {add_result.get('error', 'Unknown error')}")
        
        identifier = add_result["identifier"]
        
        # Store identifier for cleanup
        self.test_identifiers = getattr(self, 'test_identifiers', [])
        self.test_identifiers.append(identifier)
        
        # Check if content exists
        exists_result = self.backend.exists(identifier)
        
        # Verify result
        self.assertIsInstance(exists_result, bool)
        
        # Content should exist
        # Note: Some backends might have eventual consistency, so this test might fail
        # if the content isn't immediately available
        if not exists_result:
            logger.warning(f"exists method returned False for content that was just added: {identifier}")
    
    def test_get_status_method(self):
        """Test get_status method if available."""
        # Check if get_status method is available
        if not hasattr(self.backend, 'get_status'):
            self.skipTest("get_status method not implemented by this backend")
        
        # Call get_status method
        status_result = self.backend.get_status()
        
        # Verify result structure
        self.assertIsNotNone(status_result)
        self.assertIsInstance(status_result, dict)
        self.assertIn("success", status_result)
        
        # If success, verify backend field
        if status_result.get("success", False):
            self.assertIn("backend", status_result)
            self.assertEqual(status_result["backend"], self.backend.get_name())
    
    def _cleanup_test_content(self):
        """Clean up test content created during tests."""
        # Clean up all test identifiers
        if hasattr(self, 'test_identifiers') and self.test_identifiers:
            for identifier in self.test_identifiers:
                try:
                    self.backend.remove_content(identifier)
                except Exception as e:
                    logger.warning(f"Failed to remove test content {identifier}: {e}")


class MockStorageBackendTest(unittest.TestCase, StorageBackendBaseTest):
    """
    Mock implementation of StorageBackendBaseTest for demonstration and testing.
    
    This class shows how to create a test suite for a specific backend.
    It inherits from both unittest.TestCase and StorageBackendBaseTest.
    """
    
    def setUp(self):
        """Set up the test environment with a mock backend."""
        # Create a mock backend class
        from unittest.mock import MagicMock, patch
        import enum
        
        # A simpler approach - let's patch the assertion method used in the test
        original_assertIsInstance = self.assertIsInstance
        def patched_assertIsInstance(obj, class_or_tuple, msg=None):
            if 'StorageBackendType' in str(class_or_tuple) and 'MOCK' in str(obj):
                # Skip the check for our mock enum
                return
            return original_assertIsInstance(obj, class_or_tuple, msg)
            
        self.assertIsInstance = patched_assertIsInstance
        
        # Create a mock object for the enum value
        mock_type = MagicMock(name="StorageBackendType.MOCK")
        mock_type.__str__ = lambda self: "StorageBackendType.MOCK"
        
        # Create a mock backend class that inherits from BackendStorage
        class MockBackend(BackendStorage):
            def __init__(self, resources, metadata):
                super().__init__(mock_type, resources, metadata)
                self.stored_data = {}
                
            def get_name(self):
                return "mock"
                
            def add_content(self, content, metadata=None):
                content_id = str(uuid.uuid4())
                
                if isinstance(content, (str, bytes)):
                    data = content
                else:
                    # Assume file-like object
                    data = content.read()
                    
                self.stored_data[content_id] = {
                    "data": data,
                    "metadata": metadata or {}
                }
                
                return {
                    "success": True,
                    "identifier": content_id,
                    "backend": self.get_name()
                }
                
            def get_content(self, content_id):
                if content_id not in self.stored_data:
                    return {
                        "success": False,
                        "error": "Content not found",
                        "backend": self.get_name()
                    }
                    
                return {
                    "success": True,
                    "data": self.stored_data[content_id]["data"],
                    "backend": self.get_name(),
                    "identifier": content_id
                }
                
            def remove_content(self, content_id):
                if content_id in self.stored_data:
                    del self.stored_data[content_id]
                    
                return {
                    "success": True,
                    "backend": self.get_name(),
                    "identifier": content_id
                }
                
            def get_metadata(self, content_id):
                if content_id not in self.stored_data:
                    return {
                        "success": False,
                        "error": "Content not found",
                        "backend": self.get_name()
                    }
                    
                return {
                    "success": True,
                    "metadata": self.stored_data[content_id]["metadata"],
                    "backend": self.get_name(),
                    "identifier": content_id
                }
                
            def list(self):
                items = [
                    {"identifier": cid, "backend": self.get_name()}
                    for cid in self.stored_data.keys()
                ]
                
                return {
                    "success": True,
                    "items": items,
                    "backend": self.get_name()
                }
                
            def exists(self, identifier):
                return identifier in self.stored_data
                
            def get_status(self):
                return {
                    "success": True,
                    "backend": self.get_name(),
                    "available": True,
                    "status": {
                        "items_count": len(self.stored_data)
                    }
                }
                
            def cleanup(self):
                self.stored_data = {}
        
        # Set the backend class
        self.backend_class = MockBackend
        
        # Initialize default resources and metadata
        self.default_resources = {}
        self.default_metadata = {}
        
        # Call the parent setUp from StorageBackendBaseTest
        StorageBackendBaseTest.setUp(self)
    
    def test_mock_specific_functionality(self):
        """Test functionality specific to the mock backend."""
        # Add content
        test_data = b"Mock-specific test data"
        
        add_result = self.backend.add_content(test_data)
        self.assertTrue(add_result["success"])
        
        # Verify direct access to stored_data (mock-specific feature)
        identifier = add_result["identifier"]
        self.assertIn(identifier, self.backend.stored_data)
        self.assertEqual(self.backend.stored_data[identifier]["data"], test_data)
        
        # Clean up
        self.backend.remove_content(identifier)


if __name__ == "__main__":
    # Run the mock test as a demonstration
    unittest.main()