#!/usr/bin/env python3
"""
Simple test to verify our fixes are working.
"""

import unittest
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

class SimpleTest(unittest.TestCase):
    """Basic test to verify imports are working."""
    
    def test_backend_storage_import(self):
        """Test that we can import BackendStorage."""
        from ipfs_kit_py.mcp.storage_manager import BackendStorage
        self.assertIsNotNone(BackendStorage)
        
    def test_lotus_kit_available(self):
        """Test that we can import LOTUS_KIT_AVAILABLE."""
        from ipfs_kit_py.lotus_kit import LOTUS_KIT_AVAILABLE
        self.assertTrue(LOTUS_KIT_AVAILABLE)
        
if __name__ == "__main__":
    unittest.main()