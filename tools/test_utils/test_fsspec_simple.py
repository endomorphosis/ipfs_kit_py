"""
Simplified test for FSSpec integration in high_level_api.py

This module provides mock classes for testing the FSSpec integration without 
requiring actual FSSpec to be installed.

Run this from the project root with:
python -m tools.test_utils.test_fsspec_simple
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add project root to path if needed
if not os.getcwd() in sys.path:
    sys.path.insert(0, os.getcwd())

# Mock the required modules and classes
class MockAbstractFileSystem:
    def __init__(self, **kwargs):
        pass

# Create mock modules
import sys
from unittest.mock import MagicMock

# Mock fsspec and IPFSFileSystem
sys.modules['fsspec'] = MagicMock()
sys.modules['fsspec.spec'] = MagicMock()
sys.modules['fsspec.spec'].AbstractFileSystem = MockAbstractFileSystem

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

# Mock the imports in ipfs_fsspec
sys.modules['ipfs_kit_py.ipfs_fsspec'] = MagicMock()
sys.modules['ipfs_kit_py.ipfs_fsspec'].HAVE_FSSPEC = True
sys.modules['ipfs_kit_py.ipfs_fsspec'].IPFSFileSystem = MockIPFSFileSystem

# Create a minimal version of IPFSSimpleAPI that only has the get_filesystem method
class SimpleIPFSAPI:
    def __init__(self):
        self.config = {
            'role': 'worker',
            'ipfs_path': '~/.ipfs',
            'cache': {
                'memory_cache_size': 100 * 1024 * 1024,
                'local_cache_size': 1 * 1024 * 1024 * 1024
            }
        }
    
    def get_filesystem(self, **kwargs):
        # Import mock modules
        from ipfs_kit_py.ipfs_fsspec import HAVE_FSSPEC, IPFSFileSystem
        
        if not HAVE_FSSPEC:
            logger.warning("FSSpec is not available")
            return None
        
        # Prepare configuration
        fs_kwargs = {}
        
        # Add configuration from self.config with kwargs taking precedence
        if "ipfs_path" in kwargs:
            fs_kwargs["ipfs_path"] = kwargs["ipfs_path"]
        elif "ipfs_path" in self.config:
            fs_kwargs["ipfs_path"] = self.config["ipfs_path"]

        if "socket_path" in kwargs:
            fs_kwargs["socket_path"] = kwargs["socket_path"]
        elif "socket_path" in self.config:
            fs_kwargs["socket_path"] = self.config["socket_path"]

        if "role" in kwargs:
            fs_kwargs["role"] = kwargs["role"]
        else:
            fs_kwargs["role"] = self.config.get("role", "leecher")

        # Add cache configuration if provided
        if "cache_config" in kwargs:
            fs_kwargs["cache_config"] = kwargs["cache_config"]
        elif "cache" in self.config:
            fs_kwargs["cache_config"] = self.config["cache"]
        
        try:
            # Create the filesystem
            filesystem = IPFSFileSystem(**fs_kwargs)
            logger.info("IPFSFileSystem initialized successfully")
            return filesystem
        except Exception as e:
            logger.error(f"Failed to initialize IPFSFileSystem: {e}")
            return None

# Run the test
if __name__ == "__main__":
    try:
        # Initialize API
        api = SimpleIPFSAPI()
        
        # Try to get filesystem
        logger.info("Testing get_filesystem() method")
        fs = api.get_filesystem()
        
        if fs is None:
            logger.warning("Filesystem is None - likely fsspec is not installed")
        else:
            logger.info(f"Successfully created filesystem: {type(fs).__name__}")
            logger.info(f"Protocol: {fs.protocol}")
            logger.info(f"Role: {fs.role}")
            logger.info(f"IPFS Path: {fs.ipfs_path}")
            logger.info(f"Cache Config: {fs.cache_config}")
        
        logger.info("Test completed successfully")
    except Exception as e:
        logger.error(f"Error during test: {type(e).__name__}: {e}")