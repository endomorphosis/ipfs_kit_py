"""
Test script to verify the FSSpec integration in high_level_api.py.
This script creates a mock environment to test the get_filesystem method.

Run this from the project root with:
python -m tools.test_utils.test_fsspec_integration
"""

import os
import sys
import logging
import unittest
from unittest.mock import patch, MagicMock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the parent directory to path if needed
if not os.getcwd() in sys.path:
    sys.path.insert(0, os.getcwd())

# Import our MockIPFSFileSystem
from tools.test_utils.test_fsspec_simple import MockIPFSFileSystem

class TestFSSpecIntegration(unittest.TestCase):
    """Test FSSpec integration in high_level_api."""

    @patch('ipfs_kit_py.high_level_api.HAVE_FSSPEC', True)
    def test_get_filesystem_success(self):
        """Test successful initialization of filesystem."""
        # Create a mock instance to be returned
        mock_instance = MockIPFSFileSystem(
            role="leecher",
            use_mmap=True,
            cache_config={"memory_cache_size": 100 * 1024 * 1024},
            enable_metrics=True
        )

        # First patch our import from ipfs_fsspec with our MockIPFSFileSystem
        with patch('ipfs_kit_py.high_level_api.IPFSFileSystem',
                  return_value=mock_instance) as mock_factory:

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
            mock_factory.assert_called_once()

            # Extract kwargs from call
            call_kwargs = mock_factory.call_args[1]

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
    def test_get_filesystem_exception(self):
        """Test handling of exceptions during filesystem initialization."""
        # Define a test exception class and object
        class TestException(Exception):
            pass

        # Mock the IPFSFileSystem factory to raise an exception
        with patch('ipfs_kit_py.high_level_api.IPFSFileSystem') as mock_fs_class:
            # Configure the mock to raise an exception when called
            mock_fs_class.side_effect = TestException("Test error")

            # Import after patching
            from ipfs_kit_py.high_level_api import IPFSSimpleAPI

            # Create API instance with minimal config
            api = IPFSSimpleAPI()
            api.config = {"role": "leecher"}

            # Get filesystem - should return None
            fs = api.get_filesystem()

            # Ensure the function returns None when an exception occurs
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
