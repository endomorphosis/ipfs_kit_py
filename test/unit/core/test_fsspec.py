"""
Test FSSpec integration in high_level_api.py
"""

import os
import sys
import logging
import pytest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import mock_imports to enable mock fsspec functionality
try:
    import test.mock_imports
    logger.info("Successfully imported mock_imports")
except ImportError as e:
    logger.warning(f"Could not import mock_imports: {e}")

def test_fsspec_integration():
    """Test FSSpec integration with mock implementation."""
    try:
        # Import high_level_api
        from ipfs_kit_py.high_level_api import IPFSSimpleAPI

        # Initialize API
        api = IPFSSimpleAPI()

        # Try to get filesystem
        logger.info("Testing get_filesystem() method")
        fs = api.get_filesystem()

        # Assertions to verify functionality
        assert fs is not None, "Filesystem should not be None with our mock implementation"
        assert fs.protocol == "ipfs", "Protocol should be 'ipfs'"
        assert fs.role == "leecher", "Default role should be 'leecher'"

        # Test basic functionality
        ls_result = fs.ls("/ipfs/QmTest")
        assert isinstance(ls_result, list), "ls() should return a list"

        info_result = fs.info("/ipfs/QmTest")
        assert isinstance(info_result, dict), "info() should return a dict"

        logger.info(f"Successfully created filesystem: {type(fs).__name__}")
        logger.info(f"Protocol: {fs.protocol}")
        logger.info(f"Role: {fs.role}")
        logger.info("Test completed")

    except Exception as e:
        logger.error(f"Error during test: {type(e).__name__}: {e}")
        pytest.fail(f"Test failed: {e}")

if __name__ == "__main__":
    # Allow running as a standalone script as well
    test_fsspec_integration()
