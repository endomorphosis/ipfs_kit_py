#!/usr/bin/env python3
"""
Patch to fix import path issues in the IPFS Kit high level API.

This patch resolves import path problems that emerged after refactoring
test files into their proper directories. The main issues are:

1. Ensures high_level_api.py can be imported correctly
2. Fixes path resolution for relative imports after the refactoring
"""

import os
import sys
import logging
import shutil
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def patch_api_imports():
    """
    Fix API import mechanisms to work with the refactored directory structure.
    """
    try:
        # Path to the main API file we need to patch
        api_file = os.path.join("ipfs_kit_py", "api.py")
        
        # Check if file exists
        if not os.path.isfile(api_file):
            logger.error(f"File not found: {api_file}")
            return False
        
        # Read the file
        with open(api_file, 'r') as f:
            content = f.read()
        
        # Update the import mechanism to handle both package and direct imports
        # The issue happens when trying to import IPFSSimpleAPI
        original_import = """try:
    # First try relative imports (when used as a package)
    from .error import IPFSError
    from .high_level_api import IPFSSimpleAPI
    
    # Import WebSocket notifications"""
        
        fixed_import = """try:
    # First try relative imports (when used as a package)
    from .error import IPFSError
    
    # Import high_level_api more carefully to avoid path issues
    try:
        from .high_level_api import IPFSSimpleAPI
    except ImportError:
        # If that fails, try with the full module path
        from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    
    # Import WebSocket notifications"""
        
        # Replace the import mechanism in the API file
        new_content = content.replace(original_import, fixed_import)
        
        # Also fix the absolute import path in the except block
        original_fallback = """    # Add parent directory to path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from ipfs_kit_py.error import IPFSError
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI"""
        
        fixed_fallback = """    # Add parent directory to path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from ipfs_kit_py.error import IPFSError
    
    # Try different import paths for high_level_api
    try:
        from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    except ImportError:
        # Last resort - direct import by path manipulation
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "high_level_api", 
            os.path.join(os.path.dirname(__file__), "high_level_api.py")
        )
        high_level_api = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(high_level_api)
        IPFSSimpleAPI = high_level_api.IPFSSimpleAPI"""
        
        # Replace the fallback mechanism
        new_content = new_content.replace(original_fallback, fixed_fallback)
        
        # Write the patched content back to the file
        with open(api_file, 'w') as f:
            f.write(new_content)
        
        logger.info(f"Successfully patched {api_file}")
        
        # Create a symlink to high_level_api.py in the expected directory
        # This ensures imports can find it regardless of the path mechanism used
        try:
            source_file = os.path.abspath(os.path.join("ipfs_kit_py", "high_level_api.py"))
            if not os.path.exists(source_file):
                logger.error(f"Source file not found: {source_file}")
                return False
                
            # Create a proper Python module for high_level_api in the package root if needed
            package_path = os.path.join("ipfs_kit_py", "high_level_api", "__init__.py")
            
            # Ensure the directory exists
            os.makedirs(os.path.dirname(package_path), exist_ok=True)
            
            # Create an __init__.py that imports from the main module
            init_content = """\"\"\"
Proxy module to ensure high_level_api can be imported from various paths.
This resolves import issues after the codebase refactoring.
\"\"\"

import os
import sys
import importlib.util

# Import from the main high_level_api.py file
high_level_api_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "high_level_api.py")
spec = importlib.util.spec_from_file_location("high_level_api", high_level_api_path)
high_level_api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(high_level_api)

# Import all attributes to make them available when importing this module
from high_level_api import *

# Important classes and functions that need to be explicitly available
IPFSSimpleAPI = high_level_api.IPFSSimpleAPI
"""
            
            # Write the proxy module
            with open(package_path, 'w') as f:
                f.write(init_content)
                
            logger.info(f"Created proxy module at {package_path}")
        except Exception as e:
            logger.warning(f"Error creating proxy module: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error applying patch: {e}")
        return False

def patch_init_file():
    """
    Update the __init__.py file to manage imports for moved test files.
    """
    try:
        # Path to the init file
        init_file = os.path.join("ipfs_kit_py", "__init__.py")
        
        # Check if file exists
        if not os.path.isfile(init_file):
            logger.error(f"File not found: {init_file}")
            return False
        
        # Read the file
        with open(init_file, 'r') as f:
            content = f.read()
        
        # Update the test_fio import to handle both locations
        original_import = """    from .test_fio import test_fio"""
        
        fixed_import = """    try:
        # First try the compatibility shim
        from .test_fio import test_fio
    except ImportError:
        # If that fails, try importing from tests directory
        from .tests.test_fio import test_fio"""
        
        # Replace the import mechanism
        new_content = content.replace(original_import, fixed_import)
        
        # Write the patched content back to the file
        with open(init_file, 'w') as f:
            f.write(new_content)
        
        logger.info(f"Successfully patched {init_file}")
        return True
        
    except Exception as e:
        logger.error(f"Error patching __init__.py: {e}")
        return False

if __name__ == "__main__":
    logger.info("Applying patches to fix import path issues...")
    
    # Fix API imports
    api_success = patch_api_imports()
    if api_success:
        logger.info("Successfully patched API imports")
    else:
        logger.error("Failed to patch API imports")
    
    # Fix init file
    init_success = patch_init_file()
    if init_success:
        logger.info("Successfully patched __init__.py file")
    else:
        logger.error("Failed to patch __init__.py file")
    
    # Overall success
    if api_success and init_success:
        logger.info("All patches applied successfully")
        sys.exit(0)
    else:
        logger.error("Some patches failed to apply")
        sys.exit(1)