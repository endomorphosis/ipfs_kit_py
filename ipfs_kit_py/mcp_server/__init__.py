"""
MCP Server module initialization.

NOTE: The MCP server structure has been consolidated. This module exists for backward
compatibility. All code has been moved to ipfs_kit_py.mcp.
"""

import logging
import importlib
import sys
import os
from types import ModuleType

logger = logging.getLogger(__name__)

# Direct imports for backward compatibility
try:
    # Directly import and re-export the MCPServer class for backward compatibility
    from ipfs_kit_py.mcp.server_bridge import MCPServer, MCPCacheManager, AsyncMCPServer
    from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
    from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
    
    logger.info("Successfully imported MCPServer and related classes for backward compatibility")
    
    # Make these available at the module level
    __all__ = ['MCPServer', 'MCPCacheManager', 'AsyncMCPServer', 'IPFSController', 'IPFSModel']
except ImportError as e:
    logger.error(f"Failed to import from ipfs_kit_py.mcp: {e}")

# Define the mapping between old paths and new paths
MODULE_MAPPING = {
    'ipfs_kit_py.mcp_server.controllers': 'ipfs_kit_py.mcp.controllers',
    'ipfs_kit_py.mcp_server.models': 'ipfs_kit_py.mcp.models',
    'ipfs_kit_py.mcp_server.storage': 'ipfs_kit_py.mcp.storage_manager',
    'ipfs_kit_py.mcp_server.persistence': 'ipfs_kit_py.mcp.persistence',
    'ipfs_kit_py.mcp_server.api': 'ipfs_kit_py.mcp.api',
    'ipfs_kit_py.mcp_server.extensions': 'ipfs_kit_py.mcp.extensions',
    'ipfs_kit_py.mcp_server.server_bridge': 'ipfs_kit_py.mcp.server_bridge'
}

# Create a server_bridge module directly in sys.modules
sys.modules['ipfs_kit_py.mcp_server.server_bridge'] = sys.modules[__name__]

class RedirectModule(ModuleType):
    """
    A module that redirects imports from old paths to new paths.
    """
    def __init__(self, name, new_path):
        super().__init__(name)
        self.new_path = new_path

    def __getattr__(self, name):
        # Load the real module and get the attribute from it
        real_module = importlib.import_module(self.new_path)
        return getattr(real_module, name)

# Handle submodule imports explicitly
def handle_submodule_import(name):
    """
    Handle imports for submodules of redirected modules.

    Args:
        name: The full module name to import

    Returns:
        The imported module or None if not handled
    """
    for old_prefix, new_prefix in MODULE_MAPPING.items():
        if name.startswith(old_prefix + '.'):
            # Extract the submodule path
            suffix = name[len(old_prefix):]
            new_name = new_prefix + suffix

            try:
                # Try to import from the new location
                module = importlib.import_module(new_name)
                logger.info(f"Successfully redirected import from {name} to {new_name}")
                return module
            except ImportError as e:
                logger.warning(f"Failed to import {new_name}: {e}")
                # Continue to the original import - don't return None here

    return None

# Override the built-in import function
try:
    if isinstance(__builtins__, dict):
        original_import = __builtins__['__import__']
    else:
        original_import = getattr(__builtins__, '__import__')
except (AttributeError, TypeError):
    # Fallback to built-in import
    original_import = __import__

def import_hook(name, globals=None, locals=None, fromlist=(), level=0):
    """
    Import hook that redirects imports from old paths to new paths.
    """
    # Check if this is a direct import of a redirected module
    if name in MODULE_MAPPING:
        try:
            new_path = MODULE_MAPPING[name]
            module = importlib.import_module(new_path)
            logger.info(f"Successfully redirected direct import from {name} to {new_path}")
            return module
        except ImportError as e:
            logger.warning(f"Failed to redirect direct import from {name} to {MODULE_MAPPING[name]}: {e}")
            # Continue with original import

    # Check if this is a submodule import of a redirected module
    submodule = handle_submodule_import(name)
    if submodule:
        return submodule

    # Fall back to the original import function
    return original_import(name, globals, locals, fromlist, level)

# Install the import hook
try:
    if isinstance(__builtins__, dict):
        __builtins__['__import__'] = import_hook
    else:
        setattr(__builtins__, '__import__', import_hook)
except (AttributeError, TypeError):
    logger.warning("Could not install import hook. Some backward compatibility may be limited.")

# Redirect imports for this module
__path__ = []
__package__ = 'ipfs_kit_py.mcp_server'

# Display warning message about consolidated structure
logger.info("Successfully redirected import to the new consolidated structure")
