"""
Test script to verify the FSSpec integration in high_level_api.py.
This script creates a mock environment to test the get_filesystem method.
"""

import os
import sys
import logging
import unittest
from unittest.mock import patch, MagicMock

logging.basicConfig(level=logging.INFO)

# Add the project directory to path
sys.path.insert(0, os.path.abspath('.'))

class TestFSSpecIntegration(unittest.TestCase):
    """Test FSSpec integration in high_level_api."""

    @patch('ipfs_kit_py.high_level_api.HAVE_FSSPEC', True)
    @patch('ipfs_kit_py.high_level_api.IPFSFileSystem')
    def test_get_filesystem_success(self, mock_filesystem):
        """Test successful initialization of filesystem."""
        # Mock the IPFSFileSystem
        mock_instance = MagicMock()
        mock_filesystem.return_value = mock_instance

        # Import after patching
        from ipfs_kit_py.high_level_api import IPFSSimpleAPI

        # Create API instance with minimal config
        api = IPFSSimpleAPI()
        api.config = {
            "role": "leecher",
            "cache": {"memory_cache_size": 100 * 1024 * 1024}
        }

        # Get filesystem
        fs = api.get_filesystem()

        # Check that filesystem was initialized with correct parameters
        self.assertIsNotNone(fs)
        mock_filesystem.assert_called_once()
        
        # Extract kwargs from call
        call_kwargs = mock_filesystem.call_args[1]
        
        # Verify key parameters
        self.assertEqual(call_kwargs["role"], "leecher")
        self.assertEqual(call_kwargs["use_mmap"], True)
        self.assertEqual(call_kwargs["enable_metrics"], True)
        
        # Verify that cache config was passed correctly
        self.assertIn("cache_config", call_kwargs)
        self.assertEqual(call_kwargs["cache_config"]["memory_cache_size"], 100 * 1024 * 1024)
        
        print("get_filesystem successfully returns a properly configured filesystem")

    @patch('ipfs_kit_py.high_level_api.HAVE_FSSPEC', False)
    def test_get_filesystem_missing_fsspec(self):
        """Test behavior when fsspec is not available."""
        # Import after patching
        from ipfs_kit_py.high_level_api import IPFSSimpleAPI

        # Create API instance with minimal config
        api = IPFSSimpleAPI()
        api.config = {"role": "leecher"}

        # Get filesystem - should return None
        fs = api.get_filesystem()
        self.assertIsNone(fs)
        
        print("get_filesystem correctly returns None when fsspec is not available")

    @patch('ipfs_kit_py.high_level_api.HAVE_FSSPEC', True)
    @patch('ipfs_kit_py.high_level_api.IPFSFileSystem')
    def test_get_filesystem_exception(self, mock_filesystem):
        """Test handling of exceptions during filesystem initialization."""
        # Mock the IPFSFileSystem to raise an exception
        mock_filesystem.side_effect = Exception("Test error")

        # Import after patching
        from ipfs_kit_py.high_level_api import IPFSSimpleAPI

        # Create API instance with minimal config
        api = IPFSSimpleAPI()
        api.config = {"role": "leecher"}

        # Get filesystem - should return None
        fs = api.get_filesystem()
        self.assertIsNone(fs)
        
        print("get_filesystem correctly handles exceptions during initialization")

if __name__ == "__main__":
    # Run tests
    test_runner = unittest.TextTestRunner()
    test_suite = unittest.TestLoader().loadTestsFromTestCase(TestFSSpecIntegration)
    test_result = test_runner.run(test_suite)
    
    # Output summary
    print("\nTest Summary:")
    print(f"Tests run: {test_result.testsRun}")
    print(f"Errors: {len(test_result.errors)}")
    print(f"Failures: {len(test_result.failures)}")
    print(f"Skipped: {len(test_result.skipped)}")
    
    # Exit with status code
    sys.exit(not test_result.wasSuccessful())