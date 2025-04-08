"""
MCP Server implementation that integrates with the existing IPFS Kit APIs.

This server provides:
- A structured approach to handling IPFS operations
- Debug capabilities for test-driven development
- Integration with the existing API infrastructure
"""

import logging
import time
import uuid
import os
import json
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

# Import existing API components
from ipfs_kit_py.api import app as main_app
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Internal imports
from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
from ipfs_kit_py.mcp.persistence.cache_manager import MCPCacheManager

# Configure logger
logger = logging.getLogger(__name__)

class MCPServer:
    """
    Model-Controller-Persistence Server for IPFS Kit.
    
    This server provides a structured approach to handling IPFS operations,
    with built-in debugging capabilities for test-driven development.
    """
    
    def __init__(self, 
                debug_mode: bool = False, 
                log_level: str = "INFO",
                persistence_path: str = None,
                isolation_mode: bool = False):
        """
        Initialize the MCP Server.
        
        Args:
            debug_mode: Enable detailed debug logging and debug endpoints
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            persistence_path: Path for MCP server persistence files
            isolation_mode: Run in isolated mode without affecting host system
        """
        self.debug_mode = debug_mode
        self.isolation_mode = isolation_mode
        self.persistence_path = persistence_path or os.path.expanduser("~/.ipfs_kit/mcp")
        self.instance_id = str(uuid.uuid4())
        
        # Configure logging
        self._setup_logging(log_level)
        
        # Initialize components
        self._init_components()
        
        # Create FastAPI router
        self.router = self._create_router()
        
        # Session tracking for debugging
        self.sessions = {}
        self.operation_log = []
        
        logger.info(f"MCP Server initialized with ID: {self.instance_id}")
        if debug_mode:
            logger.info("Debug mode enabled")
        if isolation_mode:
            logger.info("Isolation mode enabled")
    
    def _setup_logging(self, log_level: str):
        """Configure logging for the MCP server."""
        level = getattr(logging, log_level.upper())
        
        # Create handler for MCP-specific logs
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)-8s] [MCP:%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        # Configure logger
        logger.setLevel(level)
        logger.addHandler(handler)
        
        # Log startup info
        logger.info(f"MCP Server logging initialized at level {log_level}")
    
    def _init_components(self):
        """Initialize MCP components."""
        # Create directories if needed
        os.makedirs(self.persistence_path, exist_ok=True)
        
        # Initialize core components
        self.cache_manager = MCPCacheManager(
            base_path=os.path.join(self.persistence_path, "cache"),
            debug_mode=self.debug_mode
        )
        
        # Initialize IPFS kit instance
        kit_options = {}
        if self.isolation_mode:
            # Use isolated IPFS path for testing
            kit_options["metadata"] = {
                "ipfs_path": os.path.join(self.persistence_path, "ipfs"),
                "role": "leecher",  # Use lightweight role for testing
                "test_mode": True
            }
        
        self.ipfs_kit = ipfs_kit(metadata=kit_options.get("metadata"))
        
        # Initialize MVC components
        self.models = {
            "ipfs": IPFSModel(self.ipfs_kit, self.cache_manager)
        }
        self.controllers = {
            "ipfs": IPFSController(self.models["ipfs"])
        }
        self.persistence = self.cache_manager
    
    def _create_router(self) -> APIRouter:
        """Create FastAPI router for MCP endpoints."""
        router = APIRouter(prefix="", tags=["mcp"])
        
        # Register core endpoints
        router.add_api_route("/health", self.health_check, methods=["GET"])
        router.add_api_route("/debug", self.get_debug_state, methods=["GET"])
        router.add_api_route("/operations", self.get_operation_log, methods=["GET"])
        
        # Register IPFS controller endpoints
        self.controllers["ipfs"].register_routes(router)
        
        # Define debug middleware function to be attached when registering with app
        self.debug_middleware = None
        if self.debug_mode:
            async def debug_middleware(request: Request, call_next: Callable):
                """Debug middleware to log requests and responses."""
                start_time = time.time()
                session_id = request.headers.get("X-MCP-Session-ID", str(uuid.uuid4()))
                
                # Log request
                self._log_operation({
                    "type": "request",
                    "session_id": session_id,
                    "path": request.url.path,
                    "method": request.method,
                    "timestamp": start_time
                })
                
                # Process request
                response = await call_next(request)
                
                # Log response
                process_time = time.time() - start_time
                status_code = response.status_code
                
                self._log_operation({
                    "type": "response",
                    "session_id": session_id,
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": status_code,
                    "process_time": process_time,
                    "timestamp": time.time()
                })
                
                # Add debug headers
                response.headers["X-MCP-Session-ID"] = session_id
                response.headers["X-MCP-Process-Time"] = f"{process_time:.6f}"
                
                return response
                
            self.debug_middleware = debug_middleware
        
        return router
    
    def register_with_app(self, app: FastAPI, prefix: str = "/mcp"):
        """
        Register MCP server with a FastAPI application.
        
        Args:
            app: FastAPI application instance
            prefix: URL prefix for MCP endpoints
        """
        # Mount the router
        app.include_router(self.router, prefix=prefix)
        
        # Add debug middleware if enabled
        if self.debug_mode and self.debug_middleware:
            app.middleware("http")(self.debug_middleware)
        
        logger.info(f"MCP Server registered with FastAPI app at prefix: {prefix}")
    
    def _log_operation(self, operation: Dict[str, Any]):
        """Log an operation for debugging purposes."""
        if self.debug_mode:
            self.operation_log.append(operation)
            
            # Keep log size reasonable
            if len(self.operation_log) > 1000:
                self.operation_log = self.operation_log[-1000:]
    
    async def health_check(self):
        """Health check endpoint."""
        return {
            "success": True,
            "status": "ok",
            "timestamp": time.time(),
            "server_id": self.instance_id,
            "debug_mode": self.debug_mode,
            "isolation_mode": self.isolation_mode
        }
    
    async def get_debug_state(self):
        """Get debug information about the server state."""
        if not self.debug_mode:
            return {
                "success": False,
                "error": "Debug mode not enabled",
                "error_type": "DebugDisabled"
            }
        
        # Get state from components
        server_info = {
            "server_id": self.instance_id,
            "debug_mode": self.debug_mode,
            "isolation_mode": self.isolation_mode,
            "start_time": self.operation_log[0]["timestamp"] if self.operation_log else time.time(),
            "operation_count": len(self.operation_log),
            "session_count": len(self.sessions)
        }
        
        models_info = {}
        for name, model in self.models.items():
            if hasattr(model, "get_stats"):
                models_info[name] = model.get_stats()
        
        persistence_info = {
            "cache_info": self.cache_manager.get_cache_info()
        }
        
        return {
            "success": True,
            "server_info": server_info,
            "models": models_info,
            "persistence": persistence_info,
            "timestamp": time.time()
        }
    
    async def get_operation_log(self):
        """Get operation log for debugging."""
        if not self.debug_mode:
            return {
                "success": False,
                "error": "Debug mode not enabled",
                "error_type": "DebugDisabled"
            }
        
        return {
            "success": True,
            "operations": self.operation_log,
            "count": len(self.operation_log),
            "timestamp": time.time()
        }
    
    def reset_state(self):
        """Reset server state for testing."""
        # Clear operation log
        self.operation_log = []
        
        # Clear sessions
        self.sessions = {}
        
        # Clear cache
        self.cache_manager.clear()
        
        # Reset models if they have reset methods
        for model in self.models.values():
            if hasattr(model, "reset"):
                model.reset()
        
        logger.info("MCP Server state reset")