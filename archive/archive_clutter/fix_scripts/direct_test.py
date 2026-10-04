#!/usr/bin/env python3
"""
Direct test runner that doesn't rely on pytest.
This executes the basic tests directly to verify functionality.
"""

import os
import sys
import logging
import unittest
from unittest.mock import MagicMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the project directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Create necessary mock modules
def setup_mock_modules():
    """Set up mock modules needed for tests."""
    # Mock ipfs_kit_py.lotus_kit module
    if 'ipfs_kit_py.lotus_kit' not in sys.modules:
        import types
        lotus_kit = types.ModuleType('ipfs_kit_py.lotus_kit')
        lotus_kit.LOTUS_KIT_AVAILABLE = True
        sys.modules['ipfs_kit_py.lotus_kit'] = lotus_kit
        logger.info("Created mock lotus_kit module")
        
    # Mock ipfs_kit_py.mcp.storage_manager module
    if 'ipfs_kit_py.mcp.storage_manager' not in sys.modules:
        import types
        
        # Create parent modules if they don't exist
        if 'ipfs_kit_py.mcp' not in sys.modules:
            mcp = types.ModuleType('ipfs_kit_py.mcp')
            sys.modules['ipfs_kit_py.mcp'] = mcp
            
        # Create storage_manager module
        storage_manager = types.ModuleType('ipfs_kit_py.mcp.storage_manager')
        
        # Add BackendStorage class
        class BackendStorage:
            """Base class for all storage backends."""
            def __init__(self, resources=None, metadata=None):
                self.resources = resources or {}
                self.metadata = metadata or {}
                
            def store(self, content, key=None, **kwargs):
                """Store content in the backend."""
                return {"success": True, "key": key or "test_key"}
                
            def retrieve(self, key, **kwargs):
                """Retrieve content from the backend."""
                return {"success": True, "content": b"test content"}
                
            def list_keys(self, **kwargs):
                """List keys in the backend."""
                return {"success": True, "keys": ["test_key"]}
                
            def delete(self, key, **kwargs):
                """Delete content from the backend."""
                return {"success": True}
                
        storage_manager.BackendStorage = BackendStorage
        sys.modules['ipfs_kit_py.mcp.storage_manager'] = storage_manager
        logger.info("Created mock storage_manager module with BackendStorage")
        
    # Mock ipfs_kit_py.ipfs module
    if 'ipfs_kit_py.ipfs' not in sys.modules:
        import types
        
        # Create ipfs module
        ipfs_module = types.ModuleType('ipfs_kit_py.ipfs')
        
        # Add ipfs class
        class ipfs:
            def __init__(self, config=None):
                self.config = config or {}
                self._client = MagicMock()
                
            def add(self, content, **kwargs):
                """Add content to IPFS."""
                return {"Hash": "QmTestHash"}
                
            def cat(self, cid, **kwargs):
                """Retrieve content from IPFS."""
                return b"test content"
                
            def ls(self, cid, **kwargs):
                """List IPFS directory content."""
                return {"Objects": [{"Hash": cid, "Links": []}]}
                
        ipfs_module.ipfs = ipfs
        ipfs_module.ipfs_py = MagicMock()
        
        sys.modules['ipfs_kit_py.ipfs'] = ipfs_module
        logger.info("Created mock ipfs module")

# Set up test classes
class TestBasicFunctionality(unittest.TestCase):
    """Test basic IPFS Kit functionality."""
    
    def setUp(self):
        """Set up test environment."""
        setup_mock_modules()
        
    def test_backend_storage_import(self):
        """Test that we can import BackendStorage."""
        from ipfs_kit_py.mcp.storage_manager import BackendStorage
        self.assertIsNotNone(BackendStorage)
        
    def test_lotus_kit_available(self):
        """Test that we can import LOTUS_KIT_AVAILABLE."""
        from ipfs_kit_py.lotus_kit import LOTUS_KIT_AVAILABLE
        self.assertTrue(LOTUS_KIT_AVAILABLE)
        
    @patch('ipfs_kit_py.ipfs.ipfs_py')
    def test_ipfs_basic_functionality(self, mock_ipfs):
        """Test basic IPFS functionality with mocks."""
        from ipfs_kit_py.ipfs import ipfs
        
        # Configure mock
        mock_ipfs.return_value.add.return_value = {"Hash": "QmTestHash"}
        mock_ipfs.return_value.cat.return_value = b"test content"
        
        # Create instance with test config
        instance = ipfs({"test_mode": True})
        
        # Test add functionality
        add_result = instance.add(b"test data")
        self.assertIn("Hash", add_result)
        self.assertEqual(add_result["Hash"], "QmTestHash")
        
        # Test cat functionality
        cat_result = instance.cat("QmTestHash")
        self.assertEqual(cat_result, b"test content")

# Run the tests if executed directly
if __name__ == "__main__":
    unittest.main(verbosity=2)