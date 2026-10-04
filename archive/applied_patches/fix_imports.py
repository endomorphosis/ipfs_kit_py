"""
Module import fixer for MCP to MCP_SERVER transition.

This script directly copies the necessary modules from mcp_server to mcp,
ensuring all imports work properly without relying on symbolic links.
"""

import os
import sys
import shutil
import importlib
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger('import_fixer')

# Path to the project root
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

# Define source and destination paths
MCP_SERVER_PATH = os.path.join(PROJECT_ROOT, 'ipfs_kit_py', 'mcp_server')
MCP_PATH = os.path.join(PROJECT_ROOT, 'ipfs_kit_py', 'mcp')

# Remove any existing symbolic links
def remove_symlinks(path):
    """Remove all symbolic links in the given path."""
    count = 0
    if os.path.exists(path):
        for root, dirs, files in os.walk(path):
            for filename in files:
                filepath = os.path.join(root, filename)
                if os.path.islink(filepath):
                    os.unlink(filepath)
                    count += 1
                    logger.info(f"Removed symbolic link: {filepath}")
    return count

# Create module bridges
def create_module_bridge(source_module, target_module):
    """Create a module bridge that imports from source and re-exports."""
    source_path = f"ipfs_kit_py.{source_module}"
    code = f'''"""
Auto-generated bridge module from {source_module} to {target_module}.
This file was created by the import_fixer.py script.
"""

import sys
import logging
import importlib

# Configure logging
logger = logging.getLogger(__name__)

# Import from the real module location
try:
    # Import the real module
    _real_module = importlib.import_module("{source_path}")
    
    # Get the exported symbols
    if hasattr(_real_module, "__all__"):
        __all__ = _real_module.__all__
    else:
        __all__ = [name for name in dir(_real_module) if not name.startswith("_")]
    
    # Import everything into this namespace
    for name in __all__:
        try:
            globals()[name] = getattr(_real_module, name)
            logger.debug(f"Imported {{name}} from {source_path}")
        except AttributeError:
            logger.warning(f"Failed to import {{name}} from {source_path}")
    
    logger.debug(f"Successfully imported from {source_path}")
except ImportError as e:
    logger.error(f"Failed to import from {source_path}: {{e}}")
    # No fallbacks provided here, will just raise the ImportError
    raise
'''
    return code

# Copy directory structure
def copy_directory_structure(source_dir, target_dir):
    """Copy the directory structure without copying files."""
    for root, dirs, files in os.walk(source_dir):
        # Get relative path from source_dir
        rel_path = os.path.relpath(root, source_dir)
        # Create corresponding directory in target_dir
        if rel_path == '.':
            continue  # Skip root dir
        target_path = os.path.join(target_dir, rel_path)
        os.makedirs(target_path, exist_ok=True)
        logger.info(f"Created directory: {target_path}")

# Create bridge modules for all Python files
def create_bridge_modules(source_dir, target_dir):
    """Create bridge modules for all Python files in source_dir."""
    count = 0
    for root, dirs, files in os.walk(source_dir):
        # Get relative path from source_dir
        rel_path = os.path.relpath(root, source_dir)
        # Skip the root directory for the relative path calculation
        module_prefix = '' if rel_path == '.' else f"{rel_path.replace('/', '.')}."
        
        for filename in files:
            if filename.endswith('.py') and not filename.startswith('__'):
                # Get the module name without .py extension
                module_name = os.path.splitext(filename)[0]
                # Construct full module paths
                source_module = f"mcp_server.{module_prefix}{module_name}"
                target_module = f"mcp.{module_prefix}{module_name}"
                
                # Create the bridge module code
                bridge_code = create_module_bridge(source_module, target_module)
                
                # Write the bridge module to the target path
                target_file = os.path.join(target_dir, rel_path, filename)
                os.makedirs(os.path.dirname(target_file), exist_ok=True)
                
                with open(target_file, 'w') as f:
                    f.write(bridge_code)
                    
                count += 1
                logger.info(f"Created bridge module: {target_file}")
    
    return count

# Create __init__.py files in all directories
def create_init_files(target_dir):
    """Create __init__.py files in all directories."""
    count = 0
    for root, dirs, files in os.walk(target_dir):
        init_file = os.path.join(root, '__init__.py')
        if not os.path.exists(init_file):
            # For mcp/__init__.py, create a special bridge
            if root == target_dir:
                with open(init_file, 'w') as f:
                    f.write('''"""
MCP package that redirects imports to mcp_server.
This file was created by the import_fixer.py script.
"""

import logging
import importlib

# Configure logging
logger = logging.getLogger(__name__)

# Try to import common components from mcp_server
try:
    from ipfs_kit_py.mcp_server.server_bridge import MCPServer, AsyncMCPServer, MCPCacheManager
    logger.info("Successfully imported core MCP components from mcp_server")
    __all__ = ["MCPServer", "AsyncMCPServer", "MCPCacheManager"]
except ImportError as e:
    logger.error(f"Failed to import from mcp_server: {e}")
    # Define fallback components if import fails
    class MCPServer:
        def __init__(self, *args, **kwargs):
            logger.warning("Using stub implementation of MCPServer")
            self.controllers = {}
            self.models = {}
            
        def register_with_app(self, app, prefix=""):
            return False
    
    class AsyncMCPServer:
        def __init__(self, *args, **kwargs):
            logger.warning("Using stub implementation of AsyncMCPServer")
            
        async def __aenter__(self):
            return self
            
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    
    class MCPCacheManager:
        def __init__(self, *args, **kwargs):
            logger.warning("Using stub implementation of MCPCacheManager")
            self.memory_cache = {}
            self.running = True
            
        def put(self, key, value, metadata=None):
            self.memory_cache[key] = value
            return True
            
        def get(self, key):
            return self.memory_cache.get(key)
            
        def stop(self):
            self.running = False
            
    __all__ = ["MCPServer", "AsyncMCPServer", "MCPCacheManager"]
''')
            else:
                # For other __init__.py files, create a simpler bridge
                rel_path = os.path.relpath(root, target_dir)
                module_path = rel_path.replace('/', '.')
                source_module = f"mcp_server.{module_path}" if module_path != '.' else "mcp_server"
                
                with open(init_file, 'w') as f:
                    f.write(f'''"""
Bridge module for {module_path} package.
This file was created by the import_fixer.py script.
"""

import logging
import importlib

# Configure logging
logger = logging.getLogger(__name__)

# Import from real module
try:
    _real_module = importlib.import_module("ipfs_kit_py.{source_module}")
    
    # Import all public members
    if hasattr(_real_module, "__all__"):
        __all__ = _real_module.__all__
        
        # Import all listed names
        for name in __all__:
            try:
                globals()[name] = getattr(_real_module, name)
            except AttributeError:
                logger.warning(f"Could not import {{name}} from ipfs_kit_py.{source_module}")
    else:
        # Import all non-private names
        __all__ = []
        for name in dir(_real_module):
            if not name.startswith("_"):
                try:
                    globals()[name] = getattr(_real_module, name)
                    __all__.append(name)
                except AttributeError:
                    pass
                    
    logger.debug(f"Successfully imported from ipfs_kit_py.{source_module}")
except ImportError as e:
    logger.warning(f"Failed to import from ipfs_kit_py.{source_module}: {{e}}")
    __all__ = []
''')
            
            count += 1
            logger.info(f"Created __init__.py: {init_file}")
    
    return count

# Main function to fix imports
def fix_imports():
    """Fix all the broken imports."""
    # Remove any existing symbolic links
    removed = remove_symlinks(MCP_PATH)
    logger.info(f"Removed {removed} symbolic links")
    
    # Create the MCP directory if it doesn't exist
    os.makedirs(MCP_PATH, exist_ok=True)
    
    # Copy the directory structure
    copy_directory_structure(MCP_SERVER_PATH, MCP_PATH)
    
    # Create bridge modules
    bridge_count = create_bridge_modules(MCP_SERVER_PATH, MCP_PATH)
    logger.info(f"Created {bridge_count} bridge modules")
    
    # Create __init__.py files
    init_count = create_init_files(MCP_PATH)
    logger.info(f"Created {init_count} __init__.py files")
    
    logger.info("Import fixing completed successfully!")
    return True

if __name__ == "__main__":
    # Execute the import fixer
    success = fix_imports()
    sys.exit(0 if success else 1)