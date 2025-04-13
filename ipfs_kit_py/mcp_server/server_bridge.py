"""
Import bridge between old MCP structure and new MCP server structure.
This module allows existing code to continue working while the transition
to the new structure is in progress.
"""

import sys
import logging
import tempfile
import os
import shutil
from pathlib import Path
import importlib.util

# Set up logging
logger = logging.getLogger(__name__)

# First try to import from new structure
try:
    from ipfs_kit_py.mcp_server.server import MCPServer as NewMCPServer
    from ipfs_kit_py.mcp_server.server import AsyncMCPServer as NewAsyncMCPServer
    logger.debug("Successfully imported from new MCP server structure")
    
    # Create wrapper classes to ensure compatibility with old code
    class MCPServer:
        """Compatibility wrapper for new MCPServer implementation."""
        
        def __init__(self, debug_mode=False, log_level="INFO", persistence_path=None, isolation_mode=False):
            """
            Initialize the MCP Server with compatibility for the old interface.
            
            Args:
                debug_mode: Enable debug mode for more detailed logging and debug endpoints
                log_level: Logging level (INFO, DEBUG, WARNING, ERROR)
                persistence_path: Path for persistent storage
                isolation_mode: Run in isolation mode (no external dependencies)
            """
            # Store the original parameters
            self.debug_mode = debug_mode
            self.log_level = log_level
            self.isolation_mode = isolation_mode
            self.persistence_path = persistence_path or tempfile.mkdtemp(prefix="mcp_server_")
            
            # Operation log for debug mode
            self.operation_log = []
            
            # Convert parameters to the format expected by the new implementation
            config = {
                "debug": {
                    "enabled": debug_mode,
                    "log_level": log_level
                },
                "persistence": {
                    "path": self.persistence_path
                },
                "isolation": {
                    "enabled": isolation_mode
                }
            }
            
            # Create the new server instance
            self._server = NewMCPServer(config)
            
            # Set up compatibility attributes
            self._initialize_compatibility_attributes()
        
        def _initialize_compatibility_attributes(self):
            """Initialize attributes for compatibility with the old interface."""
            # Create stub cache manager
            from ipfs_kit_py.mcp_server.models.storage import MCPCacheManager
            self.cache_manager = MCPCacheManager(
                base_path=self.persistence_path,
                debug_mode=self.debug_mode
            )
            
            # Create stub models and controllers dictionaries
            self.models = {
                "ipfs": self._server.ipfs_controller  # Using controller as a proxy for model
            }
            
            self.controllers = {
                "ipfs": self._server.ipfs_controller
            }
            
            logger.debug("Initialized compatibility attributes for MCPServer")
        
        def cleanup(self):
            """Clean up resources, for compatibility with old interface."""
            try:
                # Run the stop method
                if hasattr(self._server, 'graceful_shutdown'):
                    self._server.graceful_shutdown()
                
                # Stop cache manager
                if hasattr(self, 'cache_manager') and self.cache_manager:
                    if hasattr(self.cache_manager, 'stop'):
                        self.cache_manager.stop()
                
                # Remove persistence directory if it's a temp dir
                if hasattr(self, 'persistence_path') and self.persistence_path and \
                   self.persistence_path.startswith(tempfile.gettempdir()):
                    try:
                        shutil.rmtree(self.persistence_path, ignore_errors=True)
                    except Exception as e:
                        logger.warning(f"Error cleaning up persistence directory: {e}")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
        
        def log_operation(self, operation_type, details=None):
            """Log an operation if in debug mode."""
            if not self.debug_mode:
                return
            
            self.operation_log.append({
                "timestamp": import time; time.time(),
                "operation": operation_type,
                "details": details
            })
            
            logger.debug(f"Operation logged: {operation_type}")
        
        async def health_check(self):
            """Health check endpoint for compatibility."""
            try:
                result = await self._server.check_health()
                
                # Format result for compatibility
                return {
                    "status": "healthy" if result.get("success", False) else "unhealthy",
                    "components": {
                        "cache": True,  # Assume cache is running
                        "models": {"ipfs": True},  # Assume models are available
                        "debug_mode": self.debug_mode,
                        "isolation_mode": self.isolation_mode
                    }
                }
            except Exception as e:
                logger.error(f"Health check error: {e}")
                return {
                    "status": "error",
                    "error": str(e)
                }
        
        async def get_debug_state(self):
            """Get debug state information."""
            if not self.debug_mode:
                return {"error": "Debug mode not enabled", "success": False}
            
            # Get cache stats
            cache_stats = self.cache_manager.get_stats() if hasattr(self.cache_manager, 'get_stats') else {}
            
            # Get model stats
            model_stats = {}
            for name, model in self.models.items():
                if hasattr(model, "get_stats"):
                    model_stats[name] = model.get_stats()
            
            return {
                "success": True,
                "debug_mode": self.debug_mode,
                "isolation_mode": self.isolation_mode,
                "cache_stats": cache_stats,
                "model_stats": model_stats,
                "operation_log_size": len(self.operation_log),
                "components": {
                    "cache": hasattr(self.cache_manager, 'running') and self.cache_manager.running,
                    "models": {name: True for name in self.models}
                }
            }
        
        async def get_operation_log(self):
            """Get operation log."""
            if not self.debug_mode:
                return {"error": "Debug mode not enabled", "success": False}
            
            return {
                "success": True,
                "log": self.operation_log
            }
        
        def register_with_app(self, app, prefix=""):
            """Register the MCP server with a FastAPI app."""
            try:
                # Check for FastAPI
                import importlib.util
                fastapi_spec = importlib.util.find_spec("fastapi")
                if fastapi_spec is None:
                    logger.warning("FastAPI not available, cannot register with app")
                    return False
                
                from fastapi import APIRouter, Request
                
                # Create router
                self.router = APIRouter()
                
                # Health check
                self.router.add_api_route("/health", self.health_check, methods=["GET"])
                
                # Debug endpoints
                if self.debug_mode:
                    self.router.add_api_route("/debug", self.get_debug_state, methods=["GET"])
                    self.router.add_api_route("/logs", self.get_operation_log, methods=["GET"])
                
                # Add middleware for debug mode
                if self.debug_mode:
                    @app.middleware("http")
                    async def debug_middleware(request: Request, call_next):
                        # Log request
                        self.log_operation(
                            "http_request",
                            {
                                "method": request.method,
                                "url": str(request.url),
                                "headers": dict(request.headers)
                            }
                        )
                        
                        # Process request
                        response = await call_next(request)
                        
                        # Log response
                        self.log_operation(
                            "http_response",
                            {
                                "status_code": response.status_code,
                                "headers": dict(response.headers)
                            }
                        )
                        
                        return response
                
                # Register routes
                app.include_router(self.router, prefix=prefix)
                return True
            
            except Exception as e:
                logger.error(f"Error registering with app: {e}")
                return False
    
    class AsyncMCPServer(NewAsyncMCPServer):
        """Compatibility wrapper for new AsyncMCPServer implementation."""
        pass
        
except ImportError as e:
    logger.warning(f"Failed to import from new MCP server structure: {e}")
    # Fallback to old structure - these should be defined in the old module
    # but we need a circular reference protection
    try:
        # Only attempt to import from the old module if it's different than the current one
        if __name__ != "ipfs_kit_py.mcp.server":
            from ipfs_kit_py.mcp.server import MCPServer, AsyncMCPServer
            logger.debug("Using old MCP structure as fallback")
        else:
            raise ImportError("Cannot import from self to avoid circular reference")
    except ImportError:
        # If we can't import from the old structure either, create minimal stubs
        logger.error("Failed to import MCPServer from any location, using stub implementation")
        
        class MCPServer:
            """Stub implementation for MCPServer when neither new nor old structures are available."""
            def __init__(self, debug_mode=False, log_level="INFO", persistence_path=None, isolation_mode=False):
                self.debug_mode = debug_mode
                self.log_level = log_level
                self.persistence_path = persistence_path or tempfile.mkdtemp(prefix="mcp_server_")
                self.isolation_mode = isolation_mode
                self.operation_log = []
                self.models = {}
                self.controllers = {}
                logger.warning("Using stub MCPServer implementation")
            
            def cleanup(self):
                pass
            
            def log_operation(self, operation_type, details=None):
                pass
            
            async def health_check(self):
                return {"status": "stub_implementation"}
            
            def register_with_app(self, app, prefix=""):
                return False
        
        class AsyncMCPServer:
            """Stub implementation for AsyncMCPServer."""
            def __init__(self, *args, **kwargs):
                pass
            
            async def __aenter__(self):
                return self
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

# Import time module needed by log_operation
import time

# Define a cache manager for compatibility
class MCPCacheManager:
    """Compatibility stub for the MCPCacheManager class."""
    
    def __init__(self, base_path=None, memory_limit=100*1024*1024, disk_limit=1024*1024*1024, debug_mode=False):
        self.base_path = base_path or tempfile.mkdtemp(prefix="mcp_cache_")
        self.memory_limit = memory_limit
        self.disk_limit = disk_limit
        self.debug_mode = debug_mode
        self.memory_cache = {}
        self.running = True
        
        # Stats
        self.stats = {
            "memory_hits": 0,
            "disk_hits": 0,
            "misses": 0,
            "memory_evictions": 0,
            "disk_evictions": 0,
            "put_operations": 0,
            "get_operations": 0,
            "memory_size": 0,
            "disk_size": 0
        }
    
    def put(self, key, value, metadata=None):
        self.stats["put_operations"] += 1
        self.memory_cache[key] = value
        return True
    
    def get(self, key):
        self.stats["get_operations"] += 1
        if key in self.memory_cache:
            self.stats["memory_hits"] += 1
            return self.memory_cache.get(key)
        self.stats["misses"] += 1
        return None
    
    def delete(self, key):
        if key in self.memory_cache:
            del self.memory_cache[key]
        return True
    
    def clear(self):
        self.memory_cache.clear()
        return True
    
    def get_stats(self):
        return self.stats
    
    def stop(self):
        self.running = False

# Add MCPCacheManager to the exports
__all__ = ['MCPServer', 'AsyncMCPServer', 'MCPCacheManager']