"""
MCP Server Bridge implementation.

This module provides classes for interfacing with the MCP server architecture.
It replaces the previous implementation that required importing from ipfs_kit_py.mcp_server.
"""

import sys
import logging
import os
import json
import time
import uuid
from typing import Dict, Any, Optional, List, Callable, Union

# Configure logging
logger = logging.getLogger(__name__)

class MCPCacheManager:
    """Simple cache manager for MCP data."""
    
    def __init__(self, cache_dir: Optional[str] = None, ttl: int = 3600):
        """
        Initialize the cache manager.
        
        Args:
            cache_dir: Optional directory for file-based caching
            ttl: Time-to-live for cache entries in seconds (default: 1 hour)
        """
        self.memory_cache = {}
        self.running = True
        self.ttl = ttl
        self.cache_dir = cache_dir
        
        # Create cache directory if specified and doesn't exist
        if self.cache_dir and not os.path.exists(self.cache_dir):
            try:
                os.makedirs(self.cache_dir, exist_ok=True)
                logger.info(f"Created cache directory: {self.cache_dir}")
            except Exception as e:
                logger.warning(f"Failed to create cache directory: {e}")
                self.cache_dir = None
    
    def put(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Store a value in the cache.
        
        Args:
            key: Cache key
            value: Value to store
            metadata: Optional metadata dict
            
        Returns:
            True if successful
        """
        if not self.running:
            return False
            
        # Store in memory cache
        entry = {
            "value": value,
            "timestamp": time.time(),
            "metadata": metadata or {}
        }
        self.memory_cache[key] = entry
        
        # Store in file cache if configured
        if self.cache_dir:
            try:
                cache_path = os.path.join(self.cache_dir, f"{key}.json")
                with open(cache_path, "w") as f:
                    json.dump(entry, f)
            except Exception as e:
                logger.warning(f"Failed to write to file cache: {e}")
                
        return True
    
    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            The cached value or None if not found or expired
        """
        if not self.running:
            return None
            
        # Check memory cache first
        entry = self.memory_cache.get(key)
        if entry:
            # Check if expired
            if time.time() - entry["timestamp"] > self.ttl:
                del self.memory_cache[key]
                return None
            return entry["value"]
            
        # Check file cache if configured
        if self.cache_dir:
            try:
                cache_path = os.path.join(self.cache_dir, f"{key}.json")
                if os.path.exists(cache_path):
                    with open(cache_path, "r") as f:
                        entry = json.load(f)
                    
                    # Check if expired
                    if time.time() - entry["timestamp"] > self.ttl:
                        os.remove(cache_path)
                        return None
                        
                    # Store in memory cache for faster access next time
                    self.memory_cache[key] = entry
                    return entry["value"]
            except Exception as e:
                logger.warning(f"Failed to read from file cache: {e}")
                
        return None
    
    def stop(self):
        """Stop the cache manager."""
        self.running = False
        self.memory_cache.clear()


class MCPServer:
    """
    Server implementation for the Model-Controller-Persistence architecture.
    This is the base synchronous implementation.
    """
    
    def __init__(self, 
                name: str = "mcp-server",
                description: str = "MCP Server",
                host: str = "0.0.0.0",
                port: int = 8000,
                config: Optional[Dict[str, Any]] = None,
                debug_mode: Optional[bool] = None,
                loglevel: str = "info",
                isolation_mode: bool = False,
                persistence_path: Optional[str] = None,
                ipfs_host: str = "127.0.0.1",
                ipfs_port: int = 5001,
                storage_backends: Optional[List[str]] = None,
                **kwargs):
        """
        Initialize the MCP server.
        
        Args:
            name: Server name
            description: Server description
            host: Host to bind to
            port: Port to bind to
            config: Optional configuration dictionary
            debug_mode: Optional debug mode flag (for backward compatibility)
            loglevel: Logging level to use
            isolation_mode: If True, server operates in isolation mode
            persistence_path: Path for persisting data
            ipfs_host: IPFS daemon host
            ipfs_port: IPFS daemon port
            storage_backends: List of storage backends to enable
            **kwargs: Additional keyword arguments for future compatibility
        """
        self.name = name
        self.description = description
        self.host = host
        self.port = port
        self.config = config or {}
        self.controllers = {}
        self.models = {}
        self.running = False
        self.isolation_mode = isolation_mode
        self.persistence_path = persistence_path
        self.ipfs_host = ipfs_host
        self.ipfs_port = ipfs_port
        self.storage_backends = storage_backends or ["ipfs"]
        
        # Initialize cache manager with persistence path if provided
        if persistence_path:
            self.cache_manager = MCPCacheManager(cache_dir=persistence_path)
        else:
            self.cache_manager = MCPCacheManager()
        
        # Handle debug_mode for backward compatibility
        if debug_mode is not None:
            logger.info(f"Using debug_mode={debug_mode} (backward compatibility)")
            self.loglevel = "debug" if debug_mode else "info"
            self.debug_mode = debug_mode  # Store for compatibility
        else:
            self.loglevel = loglevel
            self.debug_mode = self.loglevel.lower() == "debug"  # Derive debug_mode from loglevel
        
        # Set up logging level
        numeric_level = getattr(logging, self.loglevel.upper(), None)
        if not isinstance(numeric_level, int):
            numeric_level = logging.INFO
            
        root_logger = logging.getLogger()
        root_logger.setLevel(numeric_level)
        
        logger.info(f"Initialized MCPServer: {name} (loglevel={self.loglevel})")
    
    def register_controller(self, controller_name: str, controller: Any) -> bool:
        """
        Register a controller with the server.
        
        Args:
            controller_name: Name of the controller
            controller: Controller instance
            
        Returns:
            True if successful
        """
        if controller_name in self.controllers:
            logger.warning(f"Controller {controller_name} already registered, replacing")
            
        self.controllers[controller_name] = controller
        logger.info(f"Registered controller: {controller_name}")
        return True
    
    def register_model(self, model_name: str, model: Any) -> bool:
        """
        Register a model with the server.
        
        Args:
            model_name: Name of the model
            model: Model instance
            
        Returns:
            True if successful
        """
        if model_name in self.models:
            logger.warning(f"Model {model_name} already registered, replacing")
            
        self.models[model_name] = model
        logger.info(f"Registered model: {model_name}")
        return True
    
    def register_with_app(self, app, prefix: str = "") -> bool:
        """
        Register routes with a web application.
        
        Args:
            app: Web application instance (e.g., FastAPI, Starlette)
            prefix: URL prefix for all routes
            
        Returns:
            True if successful
        """
        try:
            # This is just a stub implementation - in a real implementation,
            # we would register routes with the web application
            logger.info(f"Registering MCP routes with app using prefix: {prefix}")
            
            # Check for controllers that implement register_routes method
            for name, controller in self.controllers.items():
                if hasattr(controller, "register_routes") and callable(controller.register_routes):
                    logger.info(f"Registering routes for controller: {name}")
                    controller.register_routes(app, prefix)
            
            return True
        except Exception as e:
            logger.error(f"Failed to register with app: {e}")
            return False
    
    def start(self):
        """Start the server."""
        if self.running:
            logger.warning("Server already running")
            return
            
        logger.info(f"Starting MCP server on {self.host}:{self.port}")
        self.running = True
    
    def stop(self):
        """Stop the server."""
        if not self.running:
            logger.warning("Server not running")
            return
            
        logger.info("Stopping MCP server")
        self.running = False
        
        # Stop cache manager
        if self.cache_manager:
            self.cache_manager.stop()
            
    def shutdown(self):
        """Alias for stop() for backward compatibility."""
        return self.stop()


class AsyncMCPServer:
    """
    Asynchronous server implementation for the Model-Controller-Persistence architecture.
    """
    
    def __init__(self, 
                name: str = "async-mcp-server",
                description: str = "Async MCP Server",
                host: str = "0.0.0.0",
                port: int = 8000,
                config: Optional[Dict[str, Any]] = None,
                debug_mode: Optional[bool] = None,
                loglevel: str = "info",
                isolation_mode: bool = False,
                persistence_path: Optional[str] = None,
                ipfs_host: str = "127.0.0.1",
                ipfs_port: int = 5001,
                storage_backends: Optional[List[str]] = None,
                **kwargs):
        """
        Initialize the async MCP server.
        
        Args:
            name: Server name
            description: Server description
            host: Host to bind to
            port: Port to bind to
            config: Optional configuration dictionary
            debug_mode: Optional debug mode flag (for backward compatibility)
            loglevel: Logging level to use
            isolation_mode: If True, server operates in isolation mode
            persistence_path: Path for persisting data
            ipfs_host: IPFS daemon host
            ipfs_port: IPFS daemon port
            storage_backends: List of storage backends to enable
            **kwargs: Additional keyword arguments for future compatibility
        """
        self.name = name
        self.description = description
        self.host = host
        self.port = port
        self.config = config or {}
        self.controllers = {}
        self.models = {}
        self.running = False
        self.isolation_mode = isolation_mode
        self.persistence_path = persistence_path
        self.ipfs_host = ipfs_host
        self.ipfs_port = ipfs_port
        self.storage_backends = storage_backends or ["ipfs"]
        
        # Initialize cache manager with persistence path if provided
        if persistence_path:
            self.cache_manager = MCPCacheManager(cache_dir=persistence_path)
        else:
            self.cache_manager = MCPCacheManager()
        
        # Handle debug_mode for backward compatibility
        if debug_mode is not None:
            logger.info(f"Using debug_mode={debug_mode} (backward compatibility)")
            self.loglevel = "debug" if debug_mode else "info"
            self.debug_mode = debug_mode  # Store for compatibility
        else:
            self.loglevel = loglevel
            self.debug_mode = self.loglevel.lower() == "debug"  # Derive debug_mode from loglevel
        
        # Set up logging level
        numeric_level = getattr(logging, self.loglevel.upper(), None)
        if not isinstance(numeric_level, int):
            numeric_level = logging.INFO
            
        root_logger = logging.getLogger()
        root_logger.setLevel(numeric_level)
        
        logger.info(f"Initialized AsyncMCPServer: {name} (loglevel={self.loglevel})")
    
    async def register_controller(self, controller_name: str, controller: Any) -> bool:
        """
        Register a controller with the server.
        
        Args:
            controller_name: Name of the controller
            controller: Controller instance
            
        Returns:
            True if successful
        """
        if controller_name in self.controllers:
            logger.warning(f"Controller {controller_name} already registered, replacing")
            
        self.controllers[controller_name] = controller
        logger.info(f"Registered controller: {controller_name}")
        return True
    
    async def register_model(self, model_name: str, model: Any) -> bool:
        """
        Register a model with the server.
        
        Args:
            model_name: Name of the model
            model: Model instance
            
        Returns:
            True if successful
        """
        if model_name in self.models:
            logger.warning(f"Model {model_name} already registered, replacing")
            
        self.models[model_name] = model
        logger.info(f"Registered model: {model_name}")
        return True
    
    async def register_with_app(self, app, prefix: str = "") -> bool:
        """
        Register routes with a web application.
        
        Args:
            app: Web application instance (e.g., FastAPI, Starlette)
            prefix: URL prefix for all routes
            
        Returns:
            True if successful
        """
        try:
            # This is just a stub implementation - in a real implementation,
            # we would register routes with the web application
            logger.info(f"Registering async MCP routes with app using prefix: {prefix}")
            
            # Check for controllers that implement register_routes method
            for name, controller in self.controllers.items():
                if hasattr(controller, "register_routes") and callable(controller.register_routes):
                    logger.info(f"Registering routes for controller: {name}")
                    # Use await if the method is async
                    if hasattr(controller.register_routes, "__await__"):
                        await controller.register_routes(app, prefix)
                    else:
                        controller.register_routes(app, prefix)
            
            return True
        except Exception as e:
            logger.error(f"Failed to register with app: {e}")
            return False
    
    async def start(self):
        """Start the async server."""
        if self.running:
            logger.warning("Server already running")
            return
            
        logger.info(f"Starting async MCP server on {self.host}:{self.port}")
        self.running = True
    
    async def stop(self):
        """Stop the async server."""
        if not self.running:
            logger.warning("Server not running")
            return
            
        logger.info("Stopping async MCP server")
        self.running = False
        
        # Stop cache manager
        if self.cache_manager:
            self.cache_manager.stop()
            
    async def shutdown(self):
        """Alias for stop() for backward compatibility."""
        return await self.stop()
    
    def shutdown(self):
        """Non-async alias for stop() for backward compatibility in teardown methods."""
        if self.running:
            logger.warning("Using non-async shutdown method on AsyncMCPServer - this may not fully clean up")
            self.running = False
            if self.cache_manager:
                self.cache_manager.stop()
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()


# Define public exports
__all__ = ['MCPServer', 'AsyncMCPServer', 'MCPCacheManager']
