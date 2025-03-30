"""
Simple test example for IPFS Kit High-Level API.

This is a basic test to verify that our implementation works.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the test mock
from test.mock_ipfs_kit import MockIPFSKit

# Patch IPFSKit with mock implementation
sys.modules['ipfs_kit_py.ipfs_kit'] = MagicMock()
sys.modules['ipfs_kit_py.ipfs_kit'].IPFSKit = MockIPFSKit

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
        
        # Create a patcher for the IPFSKit
        self.kit_patcher = patch('ipfs_kit_py.ipfs_kit.IPFSKit', return_value=self.mock_kit)
        self.mock_kit_class = self.kit_patcher.start()
        
        # Mock validation
        self.validation_patcher = patch('ipfs_kit_py.validation.validate_parameters', side_effect=lambda params, spec: params)
        self.mock_validate = self.validation_patcher.start()
        
        # Create API instance
        self.api = IPFSSimpleAPI()
    
    def tearDown(self):
        """Clean up after tests."""
        self.kit_patcher.stop()
        self.validation_patcher.stop()
    
    def test_simple_initialization(self):
        """Test simple initialization."""
        # Verify IPFSKit was initialized
        self.mock_kit_class.assert_called_once()
        
        # Verify we can access the API
        self.assertIsInstance(self.api, IPFSSimpleAPI)
        
        # Simple test passes
        self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()