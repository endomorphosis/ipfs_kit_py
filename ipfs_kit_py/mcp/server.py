"""
Import bridge for MCP server module.
This file redirects imports from ipfs_kit_py.mcp.server to ipfs_kit_py.mcp_server.server
"""

import sys
import logging
import importlib

# Configure logging
logger = logging.getLogger(__name__)

# Import from the new module location
try:
    # Get the real module
    _real_module = importlib.import_module('ipfs_kit_py.mcp_server.server')
    
    # Get all symbols from the real module
    if hasattr(_real_module, '__all__'):
        __all__ = _real_module.__all__
    else:
        __all__ = [name for name in dir(_real_module) if not name.startswith('_')]
    
    # Import all symbols into this namespace
    for name in __all__:
        globals()[name] = getattr(_real_module, name)
    
    # Import the MCPServer class directly since it's commonly used
    if hasattr(_real_module, 'MCPServer'):
        MCPServer = _real_module.MCPServer
        if 'MCPServer' not in __all__:
            __all__.append('MCPServer')
        
    logger.debug(f"Successfully imported server module from mcp_server")
    
except ImportError as e:
    logger.error(f"Failed to import server from mcp_server: {e}")
    
    # Define a minimal MCPServer stub for backward compatibility
    class MCPServer:
        def __init__(self, *args, **kwargs):
            logger.warning("Using stub implementation of MCPServer from server.py")
            self.controllers = {}
            self.models = {}
            
        def register_with_app(self, app, prefix=""):
            return False
            
    __all__ = ['MCPServer']