"""
Import bridge for MCP server_bridge module.
This file redirects imports from ipfs_kit_py.mcp.server_bridge to ipfs_kit_py.mcp_server.server_bridge
"""

import sys
import logging
import importlib

# Configure logging
logger = logging.getLogger(__name__)

# Import from the new module location
try:
    # Get the real module
    _real_module = importlib.import_module('ipfs_kit_py.mcp_server.server_bridge')
    
    # Get all symbols from the real module
    if hasattr(_real_module, '__all__'):
        __all__ = _real_module.__all__
    else:
        __all__ = [name for name in dir(_real_module) if not name.startswith('_')]
    
    # Import all symbols into this namespace
    for name in __all__:
        globals()[name] = getattr(_real_module, name)
    
    # Import key classes directly
    if hasattr(_real_module, 'MCPServer'):
        MCPServer = _real_module.MCPServer
        if 'MCPServer' not in __all__:
            __all__.append('MCPServer')
    
    if hasattr(_real_module, 'AsyncMCPServer'):
        AsyncMCPServer = _real_module.AsyncMCPServer
        if 'AsyncMCPServer' not in __all__:
            __all__.append('AsyncMCPServer')
    
    if hasattr(_real_module, 'MCPCacheManager'):
        MCPCacheManager = _real_module.MCPCacheManager
        if 'MCPCacheManager' not in __all__:
            __all__.append('MCPCacheManager')
        
    logger.debug(f"Successfully imported server_bridge module from mcp_server")
    
except ImportError as e:
    logger.error(f"Failed to import server_bridge from mcp_server: {e}")
    
    # Define minimal stubs for backward compatibility
    class MCPServer:
        def __init__(self, *args, **kwargs):
            logger.warning("Using stub implementation of MCPServer from server_bridge.py")
            self.controllers = {}
            self.models = {}
            
        def register_with_app(self, app, prefix=""):
            return False
    
    class AsyncMCPServer:
        def __init__(self, *args, **kwargs):
            logger.warning("Using stub implementation of AsyncMCPServer from server_bridge.py")
        
        async def __aenter__(self):
            return self
            
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    
    class MCPCacheManager:
        def __init__(self, *args, **kwargs):
            logger.warning("Using stub implementation of MCPCacheManager from server_bridge.py")
            self.memory_cache = {}
            self.running = True
            
        def put(self, key, value, metadata=None):
            self.memory_cache[key] = value
            return True
            
        def get(self, key):
            return self.memory_cache.get(key)
            
        def stop(self):
            self.running = False
            
    __all__ = ['MCPServer', 'AsyncMCPServer', 'MCPCacheManager']