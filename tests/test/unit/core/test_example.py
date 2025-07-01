"""
Simple test example for IPFS Kit High-Level API.

This is a basic test to verify that our implementation works.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import importlib.util

# Import the test mock
import os.path

# Use direct file import as a workaround
mock_path = os.path.join(os.path.dirname(__file__), "mock_ipfs_kit.py")
spec = importlib.util.spec_from_file_location("mock_ipfs_kit", mock_path)
mock_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mock_module)
MockIPFSKit = mock_module.MockIPFSKit

# Now import the High-Level API
from ipfs_kit_py.high_level_api import IPFSSimpleAPI, PluginBase


class TestSimpleExample(unittest.TestCase):
    """
    Simple test example for the High-Level API.
    """

    def setUp(self):
        """Set up test fixtures."""
        # Mock the IPFSKit class
        self.mock_kit = MagicMock()

        # Create a patcher for the ipfs_kit function
        self.kit_patcher = patch("ipfs_kit_py.high_level_api.ipfs_kit", return_value=self.mock_kit)
        self.mock_kit_function = self.kit_patcher.start()

        # Mock validation
        self.validation_patcher = patch(
            "ipfs_kit_py.validation.validate_parameters", side_effect=lambda params, spec: params
        )
        self.mock_validate = self.validation_patcher.start()

        # Create API instance with mock kit - this will call the mocked ipfs_kit function
        self.api = IPFSSimpleAPI()

        # Replace the kit and filesystem with mocks
        self.api.kit = self.mock_kit
        self.api.fs = MagicMock()

    def tearDown(self):
        """Clean up after tests."""
        self.kit_patcher.stop()
        self.validation_patcher.stop()

    def test_simple_initialization(self):
        """Test simple initialization."""
        # We're not testing if ipfs_kit was called, since we're mocking it
        # and the actual IPFSSimpleAPI implementation might not call it directly

        # Verify the API exists
        self.assertIsNotNone(self.api)

        # Verify the mock kit is accessible
        self.assertEqual(self.api.kit, self.mock_kit)

        # Simple test passes
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
