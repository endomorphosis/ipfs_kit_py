"""
Mock imports for testing dependencies.

This module provides mock implementations of various dependencies
that may not be installed, allowing tests to run successfully.
"""

import sys
import logging
import importlib.abc
import types
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Dictionary to store our mock modules
MOCK_MODULES = {}

class MockFinder(importlib.abc.MetaPathFinder):
    """
    Custom module finder for mocking dependencies.
    """
    
    def find_spec(self, fullname, path, target=None):
        if fullname in MOCK_MODULES:
            logger.info(f"Using mock implementation for {fullname}")
            return importlib.machinery.ModuleSpec(
                fullname, 
                MockLoader(fullname),
                is_package=fullname.split('.')[-1] == "__init__"
            )
        return None

class MockLoader(importlib.abc.Loader):
    """
    Custom module loader for mock implementations.
    """
    
    def __init__(self, fullname):
        self.fullname = fullname
    
    def create_module(self, spec):
        if self.fullname in MOCK_MODULES:
            return MOCK_MODULES[self.fullname]
        return None
    
    def exec_module(self, module):
        # The module is already initialized in create_module
        pass

# Create a mock fsspec module
fsspec_module = types.ModuleType("fsspec")
fsspec_module.__version__ = "2023.4.0"

# Create mock registry module
registry_module = types.ModuleType("fsspec.registry")
registry_module.known_implementations = {}
registry_module.register_implementation = lambda protocol, cls, clobber=False: None
registry_module.get_filesystem_class = lambda protocol: None

# Create mock spec module
spec_module = types.ModuleType("fsspec.spec")

# Create abstract filesystem class
class AbstractFileSystem:
    protocol = "abstract"
    
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
    
    def ls(self, path, detail=True, **kwargs):
        return []
    
    def info(self, path, **kwargs):
        return {"name": path, "size": 0, "type": "file"}
    
    def open(self, path, mode="rb", **kwargs):
        return None

# Add class to spec module
spec_module.AbstractFileSystem = AbstractFileSystem

# Register modules in our mock dictionary
MOCK_MODULES["fsspec"] = fsspec_module
MOCK_MODULES["fsspec.registry"] = registry_module
MOCK_MODULES["fsspec.spec"] = spec_module

# Add our finder to the meta path
sys.meta_path.insert(0, MockFinder())

# Apply patch to fix import error in high_level_api.py
def apply_import_patches():
    """
    Apply patches to fix import issues in various modules.
    """
    try:
        # Import the module we need to patch
        from ipfs_kit_py import high_level_api
        
        # Check if _FSSPEC_AVAILABLE is imported
        if hasattr(high_level_api, "_FSSPEC_AVAILABLE"):
            # Force _FSSPEC_AVAILABLE to True
            high_level_api._FSSPEC_AVAILABLE = True
            logger.info("Successfully patched high_level_api._FSSPEC_AVAILABLE")
        
        # Check IPFSSimpleAPI class
        if hasattr(high_level_api, "IPFSSimpleAPI"):
            # Get the class object
            api_class = high_level_api.IPFSSimpleAPI
            
            # Check if we need to modify the get_filesystem method
            if hasattr(api_class, "get_filesystem"):
                original_get_filesystem = api_class.get_filesystem
                
                # Create a patched version
                def patched_get_filesystem(self, **kwargs):
                    # Import our mock filesystem
                    from ipfs_kit_py.ipfs_fsspec import IPFSFileSystem
                    logger.info("Using mock IPFSFileSystem implementation")
                    return IPFSFileSystem(**kwargs)
                
                # Replace the method
                api_class.get_filesystem = patched_get_filesystem
                logger.info("Successfully patched IPFSSimpleAPI.get_filesystem method")
        
        return True
    except Exception as e:
        logger.error(f"Error applying patches: {e}")
        return False

# Apply our patches
apply_import_patches()