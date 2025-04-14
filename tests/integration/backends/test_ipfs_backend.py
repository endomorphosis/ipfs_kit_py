"""
Integration test for IPFS Backend implementation.
This test verifies that the IPFS backend can properly initialize, store, retrieve, 
and manage content after the dependency issue fix.
"""

import os
import sys
import unittest
import logging
import tempfile
import time
import uuid

# Add the parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from ipfs_kit_py.mcp.storage_manager.backends.ipfs_backend import IPFSBackend
from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestIPFSBackendIntegration(unittest.TestCase):
    """Integration tests for the IPFS backend."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test resources."""
        cls.resources = {
            "ipfs_host": "127.0.0.1",
            "ipfs_port": 5001,
            "ipfs_timeout": 30,
            "pin_mode": "recursive",
            "allow_mock": True,  # Allow mock implementation for CI environments without IPFS
        }
        
        cls.metadata = {
            "performance_metrics_file": os.path.join(tempfile.gettempdir(), "ipfs_metrics.json"),
            "backend_name": "ipfs_test",
        }
        
        # Initialize backend
        cls.backend = IPFSBackend(cls.resources, cls.metadata)
        
        # Check if using mock implementation
        cls.is_mock = hasattr(cls.backend.ipfs, "_mock_implementation") and cls.backend.ipfs._mock_implementation
        if cls.is_mock:
            logger.warning("Tests running with mock IPFS implementation - some tests may be skipped")
    
    def setUp(self):
        """Set up individual test case."""
        self.test_content = f"Test content {uuid.uuid4()}".encode()
        self.test_metadata = {
            "test_key": "test_value",
            "timestamp": time.time(),
        }
    
    def test_backend_initialization(self):
        """Test that the backend initializes correctly."""
        # Verify the backend was created
        self.assertIsNotNone(self.backend)
        
        # Verify backend type
        self.assertEqual(self.backend.backend_type, StorageBackendType.IPFS)
        
        # Verify backend name
        self.assertEqual(self.backend.get_name(), "ipfs")
        
        # Log whether we're using mock implementation
        logger.info(f"IPFS Backend using mock implementation: {self.is_mock}")
    
    def test_add_content(self):
        """Test adding content to IPFS."""
        if self.is_mock and not self.backend.resources.get("allow_mock_operations"):
            self.skipTest("Skipping add_content test for mock implementation")
        
        # Add content
        result = self.backend.add_content(self.test_content, self.test_metadata)
        
        # If mock implementation, verify we get the expected error
        if self.is_mock:
            self.assertFalse(result.get("success", False))
            self.assertIn("Mock IPFS implementation", result.get("error", ""))
        else:
            # If real implementation, verify success and identifier
            self.assertTrue(result.get("success", False))
            self.assertIsNotNone(result.get("identifier"))
            
            # Store CID for subsequent tests
            self.__class__.test_cid = result.get("identifier")
            logger.info(f"Added content with CID: {self.__class__.test_cid}")
    
    def test_get_content(self):
        """Test retrieving content from IPFS."""
        if self.is_mock or not hasattr(self.__class__, "test_cid"):
            self.skipTest("Skipping get_content test - no valid CID or using mock")
        
        # Retrieve content
        result = self.backend.get_content(self.__class__.test_cid)
        
        # Verify success and content
        self.assertTrue(result.get("success", False))
        self.assertEqual(result.get("data"), self.test_content)
    
    def test_get_metadata(self):
        """Test retrieving metadata for content in IPFS."""
        if self.is_mock or not hasattr(self.__class__, "test_cid"):
            self.skipTest("Skipping get_metadata test - no valid CID or using mock")
        
        # Get metadata
        result = self.backend.get_metadata(self.__class__.test_cid)
        
        # Verify success and basic metadata structure
        self.assertTrue(result.get("success", False))
        self.assertIsNotNone(result.get("metadata"))
        self.assertIn("size", result.get("metadata", {}))
    
    def test_pin_operations(self):
        """Test pinning operations."""
        if self.is_mock or not hasattr(self.__class__, "test_cid"):
            self.skipTest("Skipping pin operations test - no valid CID or using mock")
        
        # List pins
        pins_result = self.backend.pin_ls()
        self.assertTrue(pins_result.get("success", False))
        
        # Pin content (should already be pinned from add, but testing the method)
        pin_result = self.backend.pin_add(self.__class__.test_cid)
        self.assertTrue(pin_result.get("success", False))
        
        # Verify content is in pin list
        pins_filtered_result = self.backend.pin_ls(self.__class__.test_cid)
        self.assertTrue(pins_filtered_result.get("success", False))
        # Either the pins dict contains our CID as a key, or it's in the Pins list
        self.assertTrue(
            self.__class__.test_cid in pins_filtered_result.get("pins", {}) or
            self.__class__.test_cid in pins_filtered_result.get("Pins", [])
        )
    
    def test_performance_metrics(self):
        """Test performance monitoring."""
        metrics = self.backend.get_performance_metrics()
        
        # Verify metrics structure
        self.assertIsNotNone(metrics)
        self.assertIn("operations", metrics)
    
    def test_exists(self):
        """Test exists method."""
        if self.is_mock or not hasattr(self.__class__, "test_cid"):
            self.skipTest("Skipping exists test - no valid CID or using mock")
        
        # Check if content exists
        exists = self.backend.exists(self.__class__.test_cid)
        self.assertTrue(exists)
    
    def test_list(self):
        """Test list method."""
        if self.is_mock:
            self.skipTest("Skipping list test for mock implementation")
        
        # List all items
        result = self.backend.list()
        
        # Verify success and structure
        self.assertTrue(result.get("success", False))
        self.assertIsNotNone(result.get("items"))
        self.assertIsInstance(result.get("items"), list)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up resources."""
        # Remove test content if available
        if hasattr(cls, "test_cid") and not cls.is_mock:
            try:
                cls.backend.remove_content(cls.test_cid)
                logger.info(f"Removed test content with CID: {cls.test_cid}")
            except Exception as e:
                logger.warning(f"Error removing test content: {e}")

if __name__ == "__main__":
    unittest.main()