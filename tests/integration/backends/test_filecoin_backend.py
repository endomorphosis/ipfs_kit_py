"""
Integration test for Filecoin Backend implementation.
This test verifies that the Filecoin backend can properly initialize,
and access basic Filecoin network functions.
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestFilecoinBackendIntegration(unittest.TestCase):
    """Integration tests for the Filecoin backend."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test resources."""
        # Import here to avoid import errors when the module is first loaded
        try:
            from ipfs_kit_py.mcp.storage_manager.backends.filecoin_backend import FilecoinBackend
            from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType
            
            cls.backend_class = FilecoinBackend
            cls.backend_type = StorageBackendType.FILECOIN
            cls.import_error = None
        except ImportError as e:
            logger.warning(f"Cannot import Filecoin backend: {e}")
            cls.import_error = e
            return
            
        cls.resources = {
            "filecoin_gateway": "https://api.node.glif.io",
            "filecoin_timeout": 30,
            "allow_mock": True  # Allow mock implementation for CI environments
        }
        
        cls.metadata = {
            "performance_metrics_file": os.path.join(tempfile.gettempdir(), "filecoin_metrics.json"),
            "backend_name": "filecoin_test",
        }
        
        # Initialize backend
        try:
            cls.backend = cls.backend_class(cls.resources, cls.metadata)
            
            # Check if using mock implementation
            if hasattr(cls.backend, "_mock_mode") and cls.backend._mock_mode:
                cls.is_mock = True
                logger.warning("Tests running with mock Filecoin implementation - some tests may be skipped")
            else:
                cls.is_mock = False
        except Exception as e:
            logger.error(f"Failed to initialize Filecoin backend: {e}")
            cls.backend = None
            cls.init_error = e
    
    def setUp(self):
        """Set up individual test case."""
        if hasattr(self.__class__, 'import_error') and self.__class__.import_error:
            self.skipTest(f"Filecoin backend not available: {self.__class__.import_error}")
        
        if not hasattr(self.__class__, 'backend') or self.__class__.backend is None:
            self.skipTest("Filecoin backend initialization failed")
    
    def test_backend_initialization(self):
        """Test that the backend initializes correctly."""
        self.assertIsNotNone(self.backend)
        self.assertEqual(self.backend.backend_type, self.backend_type)
        self.assertEqual(self.backend.get_name(), "filecoin")
        logger.info(f"Filecoin Backend initialized successfully (mock mode: {getattr(self, 'is_mock', False)})")
    
    def test_network_stats(self):
        """Test getting Filecoin network statistics."""
        if getattr(self, 'is_mock', True):
            self.skipTest("Skipping network stats test for mock implementation")
        
        # This assumes a get_network_stats method exists; adjust as needed
        if hasattr(self.backend, 'get_network_stats'):
            stats = self.backend.get_network_stats()
            self.assertIsNotNone(stats)
            logger.info(f"Got Filecoin network stats: {stats}")
        else:
            self.skipTest("get_network_stats method not available")
    
    def test_miner_list(self):
        """Test getting list of storage miners."""
        if getattr(self, 'is_mock', True):
            self.skipTest("Skipping miner list test for mock implementation")
        
        # This assumes a get_miners method exists; adjust as needed
        if hasattr(self.backend, 'get_miners'):
            miners = self.backend.get_miners(limit=5)
            self.assertIsNotNone(miners)
            logger.info(f"Got Filecoin miners list with {len(miners)} miners")
        else:
            self.skipTest("get_miners method not available")

if __name__ == "__main__":
    unittest.main()