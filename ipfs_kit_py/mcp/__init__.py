"""
Bridge module to support transitioning from old to new MCP structure.
This allows code to continue importing from ipfs_kit_py.mcp.*
while the actual implementation lives in ipfs_kit_py.mcp_server.
"""

import logging
import importlib
import sys
from types import ModuleType

# Configure logging
logger = logging.getLogger(__name__)

# Define mapping of old module paths to new module paths
MODULE_MAPPING = {
    'ipfs_kit_py.mcp.server': 'ipfs_kit_py.mcp_server.server',
    'ipfs_kit_py.mcp.server_bridge': 'ipfs_kit_py.mcp_server.server_bridge',
    'ipfs_kit_py.mcp.server_anyio': 'ipfs_kit_py.mcp_server.server_anyio',
    'ipfs_kit_py.mcp.server_real': 'ipfs_kit_py.mcp_server.server_real',
    'ipfs_kit_py.mcp.server_storage': 'ipfs_kit_py.mcp_server.server_storage',
    'ipfs_kit_py.mcp.server_enhanced': 'ipfs_kit_py.mcp_server.server_enhanced',
    'ipfs_kit_py.mcp.server_fixed': 'ipfs_kit_py.mcp_server.server_fixed',
    'ipfs_kit_py.mcp.server_webrtc': 'ipfs_kit_py.mcp_server.server_webrtc',
    'ipfs_kit_py.mcp.utils': 'ipfs_kit_py.mcp_server.utils',
    'ipfs_kit_py.mcp.utils.file_watcher': 'ipfs_kit_py.mcp_server.utils.file_watcher',
    'ipfs_kit_py.mcp.utils.dashboard': 'ipfs_kit_py.mcp_server.utils.dashboard',
    'ipfs_kit_py.mcp.models': 'ipfs_kit_py.mcp_server.models',
    'ipfs_kit_py.mcp.models.ipfs_model': 'ipfs_kit_py.mcp_server.models.ipfs_model',
    'ipfs_kit_py.mcp.models.ipfs_model_anyio': 'ipfs_kit_py.mcp_server.models.ipfs_model_anyio',
    'ipfs_kit_py.mcp.models.storage': 'ipfs_kit_py.mcp_server.models.storage',
    'ipfs_kit_py.mcp.controllers': 'ipfs_kit_py.mcp_server.controllers',
    'ipfs_kit_py.mcp.persistence': 'ipfs_kit_py.mcp_server.persistence',
}

# Create a module finder that redirects imports
class MCPImportFinder:
    """Import finder that redirects old mcp imports to new mcp_server imports."""
    
    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        """Find module spec, redirecting if necessary."""
        if fullname in MODULE_MAPPING:
            # Get the real module name
            real_name = MODULE_MAPPING[fullname]
            
            # Import the real module
            try:
                real_module = importlib.import_module(real_name)
                
                # Create a loader that will return the real module
                loader = importlib.machinery.SourcelessFileLoader(fullname, real_module.__file__)
                
                # Create and return the spec
                return importlib.machinery.ModuleSpec(fullname, loader)
            except ImportError:
                logger.warning(f"Failed to import {real_name} for {fullname}")
                return None
        
        # For modules that start with our prefix but aren't in mapping
        if fullname.startswith('ipfs_kit_py.mcp.') and not fullname == 'ipfs_kit_py.mcp':
            # Try to derive the new path
            submodule = fullname.replace('ipfs_kit_py.mcp.', '')
            real_name = f'ipfs_kit_py.mcp_server.{submodule}'
            
            try:
                real_module = importlib.import_module(real_name)
                loader = importlib.machinery.SourcelessFileLoader(fullname, real_module.__file__)
                return importlib.machinery.ModuleSpec(fullname, loader)
            except ImportError:
                # Not found in new structure, let normal import handle it
                return None
        
        # Not handled by this finder
        return None

# Register our import finder
sys.meta_path.insert(0, MCPImportFinder)

# Import key classes directly for backward compatibility
try:
    from ipfs_kit_py.mcp_server.server_bridge import MCPServer, AsyncMCPServer, MCPCacheManager
    logger.info("Successfully imported MCP components from mcp_server")
except ImportError as e:
    logger.error(f"Failed to import from mcp_server: {e}")
    # Create stub implementations
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
    
    class MCPCacheManager:
        def __init__(self, *args, **kwargs):
            logger.warning("Using stub implementation of MCPCacheManager")
            
# Export these classes
__all__ = ["MCPServer", "AsyncMCPServer", "MCPCacheManager"]