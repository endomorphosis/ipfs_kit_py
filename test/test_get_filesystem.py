"""
Test get_filesystem method in high_level_api.py
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

class TestGetFilesystem(unittest.TestCase):
    """
    Test cases for the get_filesystem method.
    
    These tests ensure that the get_filesystem method properly handles:
    1. Missing fsspec dependency
    2. Import errors when importing IPFSFileSystem
    3. Filesystem object caching
    """

    def setUp(self):
        """Set up common mocks for all tests."""
        # Create patches
        self.fsspec_patcher = patch("ipfs_kit_py.high_level_api.HAVE_FSSPEC")
        self.ipfs_kit_patcher = patch("ipfs_kit_py.high_level_api.ipfs_kit")
        self.logger_patcher = patch("ipfs_kit_py.high_level_api.logger")
        
        # Start patches
        self.mock_have_fsspec = self.fsspec_patcher.start()
        self.mock_ipfs_kit = self.ipfs_kit_patcher.start()
        self.mock_logger = self.logger_patcher.start()
        
        # Set default values
        self.mock_have_fsspec.return_value = True
        self.mock_ipfs_kit.return_value = MagicMock()
        
    def tearDown(self):
        """Clean up after tests."""
        self.fsspec_patcher.stop()
        self.ipfs_kit_patcher.stop()
        self.logger_patcher.stop()

    def test_fsspec_not_available(self):
        """Test that get_filesystem returns None when FSSpec is not available."""
        # Simulate FSSpec not available
        self.mock_have_fsspec = False
        
        # Import after patching
        from ipfs_kit_py.high_level_api import IPFSSimpleAPI
        
        # Create instance and reset mocks to clear initialization logs
        api = IPFSSimpleAPI()
        self.mock_logger.reset_mock()
        
        # Test get_filesystem
        result = api.get_filesystem()
        
        # Verify result is None and warning was logged
        self.assertIsNone(result)
        self.mock_logger.warning.assert_called()
            
if __name__ == "__main__":
    unittest.main()