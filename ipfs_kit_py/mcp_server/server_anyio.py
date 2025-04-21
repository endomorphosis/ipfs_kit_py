"""
MCP Server Bridge module for AnyIO.

This module provides compatibility with the old MCP server structure by bridging
to the new consolidated structure in ipfs_kit_py.mcp.
"""

import logging
import importlib
from typing import Dict, List, Any, Optional, Union

logger = logging.getLogger(__name__)

try:
    # Try to import the Server class from the new location
    from ipfs_kit_py.mcp.server_anyio import Server
    HAS_NEW_SERVER = True
except ImportError:
    logger.warning("Could not import Server from ipfs_kit_py.mcp.server_anyio")
    HAS_NEW_SERVER = False

class MCPServer:
    """
    Compatibility bridge for MCP Server with AnyIO support.
    
    This class provides backward compatibility with the old MCP server API
    by forwarding calls to the new Server class.
    """
    
    def __init__(self, debug_mode: bool = False, api_port: int = 5001, 
                 backend_configs: Optional[Dict[str, Any]] = None,
                 config_path: Optional[str] = None,
                 **kwargs):
        """
        Initialize the MCP Server compatibility bridge.
        
        Args:
            debug_mode: Enable debug mode
            api_port: API port for the server
            backend_configs: Storage backend configurations
            config_path: Path to configuration file
            **kwargs: Additional keyword arguments
        """
        self.debug_mode = debug_mode
        self.api_port = api_port
        self.backend_configs = backend_configs or {}
        
        # Set up logging level based on debug mode
        log_level = "DEBUG" if debug_mode else "INFO"
        kwargs.setdefault("loglevel", log_level)
        
        # Map port parameter
        kwargs.setdefault("port", api_port)
        
        # Create the actual server instance if available
        if HAS_NEW_SERVER:
            self.server = Server(**kwargs)
            
            # Add storage backends from backend_configs
            if backend_configs:
                for backend_name, config in backend_configs.items():
                    self.register_storage_backend(backend_name, config)
        else:
            logger.warning("New Server class not available. Creating mock MCPServer instance.")
            self.server = None
            self._is_running = False
            self.controllers = {}
            self.storage_backends = {}
    
    async def start(self, **kwargs):
        """Start the MCP server."""
        if hasattr(self, 'server') and self.server:
            return await self.server.start(**kwargs)
        logger.warning("Server not available. Could not start.")
        self._is_running = True
        return True
    
    async def stop(self, **kwargs):
        """Stop the MCP server."""
        if hasattr(self, 'server') and self.server:
            return await self.server.stop(**kwargs)
        logger.warning("Server not available. Could not stop.")
        self._is_running = False
        return True
    
    async def get_ipfs_controller(self):
        """Get the IPFS controller."""
        if hasattr(self, 'server') and self.server:
            return await self.server.get_ipfs_controller()
        return self.controllers.get('ipfs')
    
    async def get_filecoin_controller(self):
        """Get the Filecoin controller."""
        if hasattr(self, 'server') and self.server:
            return await self.server.get_filecoin_controller()
        return self.controllers.get('filecoin')
    
    async def get_libp2p_controller(self):
        """Get the libp2p controller."""
        if hasattr(self, 'server') and self.server:
            return await self.server.get_libp2p_controller()
        return self.controllers.get('libp2p')
    
    async def get_storage_manager_controller(self):
        """Get the storage manager controller."""
        if hasattr(self, 'server') and self.server:
            return await self.server.get_storage_manager_controller()
        return self.controllers.get('storage_manager')
    
    async def register_storage_backend(self, name: str, config: Dict[str, Any]):
        """Register a storage backend."""
        if hasattr(self, 'server') and self.server:
            return await self.server.register_storage_backend(name, config)
        self.storage_backends[name] = config
        return True
    
    async def unregister_storage_backend(self, name: str):
        """Unregister a storage backend."""
        if hasattr(self, 'server') and self.server:
            return await self.server.unregister_storage_backend(name)
        if name in self.storage_backends:
            del self.storage_backends[name]
            return True
        return False
    
    async def get_storage_backends(self):
        """Get a list of registered storage backends."""
        if hasattr(self, 'server') and self.server:
            return await self.server.get_storage_backends()
        return list(self.storage_backends.keys())
    
    # Legacy alias methods
    get_ipfs = get_ipfs_controller
    get_filecoin = get_filecoin_controller
    get_libp2p = get_libp2p_controller
    get_storage_manager = get_storage_manager_controller
    start_server = start
    stop_server = stop
    add_storage_backend = register_storage_backend
    remove_storage_backend = unregister_storage_backend
    list_storage_backends = get_storage_backends
    
    @classmethod
    def create_default_server(cls, **kwargs):
        """Create a default MCP server with sensible defaults."""
        return cls(**kwargs)