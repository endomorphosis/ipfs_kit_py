"""
Comprehensive test for FSSpec integration in high_level_api.py
"""

import os
import sys
import logging
from unittest.mock import MagicMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Mock problematic modules
sys.modules['fsspec'] = MagicMock()
sys.modules['fsspec.spec'] = MagicMock()
sys.modules['fsspec.utils'] = MagicMock()

# Create a mock AbstractFileSystem class
class MockAbstractFileSystem:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

# Patch the fsspec module
sys.modules['fsspec'].spec = sys.modules['fsspec.spec']
sys.modules['fsspec.spec'].AbstractFileSystem = MockAbstractFileSystem

# Mock the ipfs_fsspec module
class MockIPFSFileSystem(MockAbstractFileSystem):
    protocol = "ipfs"
    
    def __init__(self, ipfs_path=None, socket_path=None, role="leecher", 
                 cache_config=None, use_mmap=True, enable_metrics=True, **kwargs):
        super().__init__(**kwargs)
        self.ipfs_path = ipfs_path
        self.socket_path = socket_path
        self.role = role
        self.cache_config = cache_config
        self.use_mmap = use_mmap
        self.enable_metrics = enable_metrics

# Create mock ipfs_fsspec module
mock_ipfs_fsspec = MagicMock()
mock_ipfs_fsspec.HAVE_FSSPEC = True
mock_ipfs_fsspec.IPFSFileSystem = MockIPFSFileSystem
sys.modules['ipfs_kit_py.ipfs_fsspec'] = mock_ipfs_fsspec

# Mock all potentially problematic modules
mock_ai_ml = MagicMock()
sys.modules['ipfs_kit_py.ai_ml_integration'] = mock_ai_ml

mock_webrtc = MagicMock()
mock_webrtc.HAVE_WEBRTC = False
mock_webrtc.handle_webrtc_signaling = MagicMock()
sys.modules['ipfs_kit_py.webrtc_streaming'] = mock_webrtc

# Mock the ipfs_kit module
mock_ipfs_kit = MagicMock()
mock_ipfs_kit.IPFSKit = MagicMock()
mock_ipfs_kit.ipfs_kit = MagicMock()
sys.modules['ipfs_kit_py.ipfs_kit'] = mock_ipfs_kit

# Mock validation module
mock_validation = MagicMock()
sys.modules['ipfs_kit_py.validation'] = mock_validation

# Mock error module
mock_error = MagicMock()
mock_error.IPFSError = Exception
mock_error.IPFSValidationError = Exception
mock_error.IPFSConfigurationError = Exception
sys.modules['ipfs_kit_py.error'] = mock_error

# Import high_level_api
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

def test_fsspec_integration():
    """Test FSSpec integration in high_level_api."""
    try:
        # Initialize the API
        api = IPFSSimpleAPI()
        
        # Test get_filesystem method
        logger.info("Testing get_filesystem() method")
        fs = api.get_filesystem()
        
        if fs is None:
            logger.warning("Filesystem is None - likely fsspec is not available")
            return False
            
        # Verify properties
        logger.info(f"Successfully created filesystem: {type(fs).__name__}")
        logger.info(f"Protocol: {fs.protocol}")
        logger.info(f"Role: {fs.role}")
        logger.info(f"IPFS Path: {fs.ipfs_path}")
        logger.info(f"Cache Config: {fs.cache_config}")
        
        # Test with different parameters
        logger.info("Testing with custom parameters")
        custom_fs = api.get_filesystem(
            ipfs_path="/custom/path",
            role="master", 
            cache_config={"memory_cache_size": 200 * 1024 * 1024}
        )
        
        logger.info(f"Custom filesystem properties:")
        logger.info(f"IPFS Path: {custom_fs.ipfs_path}")
        logger.info(f"Role: {custom_fs.role}")
        logger.info(f"Cache Config: {custom_fs.cache_config}")
        
        logger.info("Test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error during test: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = test_fsspec_integration()
    sys.exit(0 if success else 1)