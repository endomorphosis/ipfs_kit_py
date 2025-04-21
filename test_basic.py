"""
Basic test module for ipfs_kit_py.

This module contains simple tests that should pass with our fixes.
"""

import os
import sys
import pytest
import logging
from unittest.mock import MagicMock, patch

# Import our test patching module
import ipfs_test_patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_backend_storage_import():
    """Test that we can import BackendStorage."""
    from ipfs_kit_py.mcp.storage_manager import BackendStorage
    assert BackendStorage is not None

def test_lotus_kit_available():
    """Test that we can import LOTUS_KIT_AVAILABLE."""
    from ipfs_kit_py.lotus_kit import LOTUS_KIT_AVAILABLE
    assert LOTUS_KIT_AVAILABLE is True

@patch('ipfs_kit_py.ipfs.ipfs_py')
def test_ipfs_basic_functionality(mock_ipfs):
    """Test basic IPFS functionality with mocks."""
    from ipfs_kit_py.ipfs import ipfs
    
    # Configure mock
    mock_ipfs.return_value.add.return_value = {"Hash": "QmTestHash"}
    mock_ipfs.return_value.cat.return_value = b"test content"
    
    # Create instance with test config
    instance = ipfs({"test_mode": True})
    
    # Test add functionality
    add_result = instance.add(b"test data")
    assert "Hash" in add_result
    assert add_result["Hash"] == "QmTestHash"
    
    # Test cat functionality
    cat_result = instance.cat("QmTestHash")
    assert cat_result == b"test content"

if __name__ == "__main__":
    # Run tests directly if file is executed
    pytest.main(["-xvs", __file__])