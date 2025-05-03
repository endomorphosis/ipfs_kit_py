"""
MCP Server implementation for fastapi.

This module provides the MCP Server implementation that can be used with FastAPI.
"""

import os
import sys
import time
import uuid
import json
import logging
import traceback
import asyncio
import threading
from typing import Dict, Any, List, Optional, Callable, Union, Type

from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Import MCP components
from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
from ipfs_kit_py.mcp.controllers.storage_manager_controller import StorageManagerController
from ipfs_kit_py.mcp.models.storage_manager import StorageManager
from ipfs_kit_py.mcp.models.libp2p_model import LibP2PModel
from ipfs_kit_py.mcp.controllers.libp2p_controller import LibP2PController
from ipfs_kit_py.mcp.controllers.filecoin_controller import FilecoinController
from ipfs_kit_py.mcp.controllers.storage.huggingface_controller import HuggingFaceController
from ipfs_kit_py.mcp.controllers.storage.storacha_controller import StorachaController
from ipfs_kit_py.mcp.controllers.storage.lassie_controller import LassieController
from ipfs_kit_py.mcp.controllers.storage.s3_controller import S3Controller

# Configure logger
logger = logging.getLogger(__name__)


class MCPServer:
    """MCP Server implementation for FastAPI."""

    def __init__(self, debug_mode: bool = False, log_level: str = "INFO", 
                 isolation_mode: bool = True, persistence_path: Optional[str] = None,
                 skip_daemon: bool = True, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the MCP Server.
        
        Args:
            debug_mode: Enable debug mode
            log_level: Logging level
            isolation_mode: Run in isolation mode (no external services)
            persistence_path: Path for persistent storage
            skip_daemon: Skip starting IPFS daemon
            config: Configuration dictionary
        """
        # Generate a unique ID for this server instance
        self.server_id = str(uuid.uuid4())
        
        # Store configuration
        self.debug_mode = debug_mode
        self.log_level = log_level.upper() if log_level else "INFO"
        self.isolation_mode = isolation_mode
        self.persistence_path = persistence_path
        self.skip_daemon = skip_daemon
        self.config = config or {}
        
        # Configure IPFS host and port settings
        self.ipfs_host = self.config.get("ipfs_host", "127.0.0.1")
        self.ipfs_port = self.config.get("ipfs_port", 5001)
        self.ipfs_protocol = self.config.get("ipfs_protocol", "http")
        
        # Setup logging
        self._setup_logging()
        
        # Initialize containers for models and controllers
        self.models: Dict[str, Any] = {}
        self.controllers: Dict[str, Any] = {}
        
        # Shutdown flag for cleanup thread
        self.shutdown_flag = threading.Event()
        
        # Initialize components
        self._init_components()
        
        # Global exception handler for better error reporting
        self._register_exception_handler()
        
        # Create operation log
        self.operation_log: List[Dict[str, Any]] = []
        
        # Create router
        self.router = APIRouter()
        
        # Add basic endpoints
        self._add_basic_endpoints()
        
        # Start cache cleanup thread
        self._start_cache_cleanup_thread()
        
        logger.info(f"Initialized MCPServer: {self.server_id} (loglevel={log_level.lower()})")

    def _setup_logging(self):
        """Set up logging configuration."""
        logging_level = getattr(logging, self.log_level.upper(), logging.INFO)
        if self.debug_mode and logging_level > logging.DEBUG:
            logging_level = logging.DEBUG
        
        # Configure root logger
        logging.basicConfig(
            level=logging_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler()
            ]
        )

    def _init_components(self):
        """Initialize all MCP components."""
        # Initialize IPFS Model
        try:
            # Create config for IPFS model
            ipfs_config = {
                "debug": self.debug_mode,
                "isolation": self.isolation_mode,
                "log_level": self.log_level
            }
            
            # Correctly initialize the IPFS model with the config parameter
            ipfs_model = IPFSModel(
                ipfs_kit_instance=None,  # Will be initialized later if needed
                config=ipfs_config
            )
            self.models['ipfs'] = ipfs_model
            
            # Initialize storage manager model
            storage_manager = StorageManager(ipfs_model=ipfs_model,
                                           debug_mode=self.debug_mode,
                                           isolation_mode=self.isolation_mode,
                                           log_level=self.log_level)
            self.models['storage_manager'] = storage_manager
            
            # Initialize LibP2P model with correct parameters
            # LibP2PModel doesn't accept debug_mode or config
            libp2p_model = LibP2PModel(
                host="0.0.0.0",
                port=4001
            )
            self.models['libp2p'] = libp2p_model
            
            # Initialize IPFS Controller - it only accepts ipfs_model
            ipfs_controller = IPFSController(ipfs_model=ipfs_model)
            self.controllers['ipfs'] = ipfs_controller
            
            # Initialize Storage Manager Controller
            storage_controller = StorageManagerController(storage_manager=storage_manager)
            self.controllers['storage_manager'] = storage_controller
            
            # For storage-related controllers, check if the model is available in storage_manager first
            # Initialize each controller with the parameters it expects
            
            if 'filecoin' in storage_manager.storage_models:
                filecoin_model = storage_manager.storage_models['filecoin']
                # FilecoinController expects debug_mode, isolation_mode, log_level, storage_manager
                filecoin_controller = FilecoinController(
                    debug_mode=self.debug_mode,
                    isolation_mode=self.isolation_mode,
                    log_level=self.log_level,
                    storage_manager=storage_manager
                )
                self.controllers['filecoin'] = filecoin_controller
                logger.info("Filecoin controller initialized")
            else:
                logger.warning("Skipping Filecoin controller initialization: model not available")
            
            if 'huggingface' in storage_manager.storage_models:
                huggingface_model = storage_manager.storage_models['huggingface']
                # HuggingFaceController only expects huggingface_model
                huggingface_controller = HuggingFaceController(huggingface_model=huggingface_model)
                # Create a router for the controller
                huggingface_router = APIRouter()
                huggingface_controller.register_routes(huggingface_router)
                huggingface_controller.router = huggingface_router
                self.controllers['huggingface'] = huggingface_controller
                logger.info("HuggingFace controller initialized")
            else:
                logger.warning("Skipping HuggingFace controller initialization: model not available")
            
            if 'storacha' in storage_manager.storage_models:
                storacha_model = storage_manager.storage_models['storacha']
                # Check StorachaController's expected parameters
                storacha_controller = StorachaController(storacha_model=storacha_model)
                # Create a router for the controller if it doesn't have one
                if not hasattr(storacha_controller, 'router'):
                    storacha_router = APIRouter()
                    if hasattr(storacha_controller, 'register_routes'):
                        storacha_controller.register_routes(storacha_router)
                    storacha_controller.router = storacha_router
                self.controllers['storacha'] = storacha_controller
                logger.info("Storacha controller initialized")
            else:
                logger.warning("Skipping Storacha controller initialization: model not available")
            
            if 'lassie' in storage_manager.storage_models:
                lassie_model = storage_manager.storage_models['lassie']
                # Check LassieController's expected parameters
                lassie_controller = LassieController(lassie_model=lassie_model)
                # Create a router for the controller if it doesn't have one
                if not hasattr(lassie_controller, 'router'):
                    lassie_router = APIRouter()
                    if hasattr(lassie_controller, 'register_routes'):
                        lassie_controller.register_routes(lassie_router)
                    lassie_controller.router = lassie_router
                self.controllers['lassie'] = lassie_controller
                logger.info("Lassie controller initialized")
            else:
                logger.warning("Skipping Lassie controller initialization: model not available")
            
            if 's3' in storage_manager.storage_models:
                s3_model = storage_manager.storage_models['s3']
                # Check S3Controller's expected parameters
                s3_controller = S3Controller(s3_model=s3_model)
                # Create a router for the controller if it doesn't have one
                if not hasattr(s3_controller, 'router'):
                    s3_router = APIRouter()
                    if hasattr(s3_controller, 'register_routes'):
                        s3_controller.register_routes(s3_router)
                    s3_controller.router = s3_router
                self.controllers['s3'] = s3_controller
                logger.info("S3 controller initialized")
            else:
                logger.warning("Skipping S3 controller initialization: model not available")
            
            # Initialize LibP2P Controller
            libp2p_controller = LibP2PController(libp2p_model=libp2p_model)
            self.controllers['libp2p'] = libp2p_controller
            
        except Exception as e:
            logger.error(f"Error initializing MCP components: {e}")
            logger.error(traceback.format_exc())
            raise

    def _add_basic_endpoints(self):
        """Add basic endpoints to the router."""
        @self.router.get("/health")
        async def health():
            """Health check endpoint."""
            # Collect health data from all registered models
            health_data = {
                "status": "ok",
                "timestamp": time.time(),
                "server_id": self.server_id,
                "debug_mode": self.debug_mode,
                "isolation_mode": self.isolation_mode,
                "log_level": self.log_level,
                "models": list(self.models.keys()),
                "controllers": list(self.controllers.keys()),
                "storage_backends": {}
            }
            
            # Add storage backend status if available
            if "storage_manager" in self.models:
                storage_manager = self.models["storage_manager"]
                backends = storage_manager.get_available_backends()
                
                for backend_name, is_available in backends.items():
                    health_data["storage_backends"][backend_name] = {
                        "available": is_available
                    }
                    
                    # Add additional info if available
                    if is_available and backend_name in storage_manager.storage_models:
                        model = storage_manager.storage_models[backend_name]
                        # Safely check if the model has isolation_mode attribute
                        isolation_mode = getattr(model, 'isolation_mode', True)  # Default to True if not present
                        health_data["storage_backends"][backend_name].update({
                            "simulation": isolation_mode,
                            "real_implementation": not isolation_mode
                        })
            
            return health_data
            
        @self.router.get("/version")
        async def version():
            """Version information endpoint."""
            return {
                "server_id": self.server_id,
                "version": "1.0.0",
                "api_version": "v0"
            }
            
        @self.router.get("/debug")
        async def debug():
            """Debug information endpoint."""
            if not self.debug_mode:
                return {"message": "Debug mode is disabled"}
                
            debug_info = {
                "server_id": self.server_id,
                "debug_mode": self.debug_mode,
                "isolation_mode": self.isolation_mode,
                "log_level": self.log_level,
                "models": {},
                "controllers": {},
                "operation_log": self.operation_log[-50:] if self.operation_log else []
            }
            
            # Add model info
            for name, model in self.models.items():
                debug_info["models"][name] = {
                    "type": type(model).__name__,
                    "debug_mode": getattr(model, "debug_mode", None),
                    "isolation_mode": getattr(model, "isolation_mode", None)
                }
                
            # Add controller info
            for name, controller in self.controllers.items():
                debug_info["controllers"][name] = {
                    "type": type(controller).__name__,
                    "debug_mode": getattr(controller, "debug_mode", None),
                    "isolation_mode": getattr(controller, "isolation_mode", None)
                }
                
            return debug_info
            
        @self.router.get("/log")
        async def log():
            """Operation log endpoint."""
            return {
                "server_id": self.server_id,
                "operation_log": self.operation_log[-50:] if self.operation_log else []
            }

    def register_with_app(self, app: FastAPI, prefix: str = "/api/v0/mcp"):
        """
        Register MCP server with a FastAPI app.
        
        Args:
            app: FastAPI application to register with
            prefix: API prefix for MCP server endpoints
        """
        # Register MCP routes with the app
        app.include_router(self.router, prefix=prefix)
        
        # Also add routes at root level (without controller prefix) for basic endpoints
        root_router = APIRouter()
        
        @root_router.get("/health", status_code=200)
        async def root_health():
            health_endpoint = next((route for route in self.router.routes if route.path == "/health"), None)
            if health_endpoint:
                return await health_endpoint.endpoint({})
            return {"status": "healthy", "message": "MCP Server is running"}
                
        @root_router.get("/version", status_code=200)
        async def root_version():
            version_endpoint = next((route for route in self.router.routes if route.path == "/version"), None)
            if version_endpoint:
                return await version_endpoint.endpoint({})
            return {"version": "1.0.0", "api_version": "v0"}
        
        app.include_router(root_router)
        
        # Register controller routes
        logger.info(f"Registering MCP routes with app using prefix: {prefix}")
        for name, controller in self.controllers.items():
            logger.info(f"Registering routes for controller: {name}")
            
            if hasattr(controller, 'router'):
                app.include_router(controller.router, prefix=f"{prefix}/{name}")
            else:
                logger.warning(f"Controller {name} has no router attribute")
        
        # Add CORS middleware if not already added
        if app.user_middleware and not any(m.cls == CORSMiddleware for m in app.user_middleware):
            app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
            
        # Add a global exception handler for improved error reporting
        @app.exception_handler(Exception)
        async def global_exception_handler(request: Request, exc: Exception):
            """Global exception handler for the API."""
            # Log the error with traceback
            logger.error(f"Unhandled exception in API request: {str(exc)}")
            logger.error(traceback.format_exc())
            
            # Include details in debug mode
            detail = str(exc)
            if self.debug_mode:
                detail = f"{str(exc)}\n{traceback.format_exc()}"
                
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "detail": detail,
                    "timestamp": time.time()
                }
            )
            
        logger.info("MCP Server successfully registered with FastAPI app")

    def _register_exception_handler(self):
        """Register a global exception handler for improved error logging."""
        # This is a no-op method since the actual exception handler is registered
        # when the server is attached to a FastAPI app in register_with_app()
        logger.debug("Exception handler will be registered when attached to FastAPI app")
        pass

    def _start_cache_cleanup_thread(self):
        """Start a background thread to clean up expired cache entries."""
        # No-op method for now, can be implemented if cache cleanup is needed
        logger.debug("Cache cleanup thread is a no-op in this implementation")
        pass
    
    def register_model(self, name: str, model: Any):
        """
        Register a model with the server.
        
        Args:
            name: Name to register the model under
            model: Model instance to register
        """
        logger.info(f"Registering model: {name}")
        self.models[name] = model
        
    def register_controller(self, name: str, controller: Any):
        """
        Register a controller with the server.
        
        Args:
            name: Name to register the controller under
            controller: Controller instance to register
        """
        logger.info(f"Registering controller: {name}")
        self.controllers[name] = controller

# MCP Tool handling
async def tool_handler(request: Request):
    """Handle MCP tool requests."""
    data = await request.json()
    
    tool_name = data.get("name")
    server_name = data.get("server", "default")
    args = data.get("args", {})
    
    if not tool_name:
        return JSONResponse(
            status_code=400,
            content={"error": "Tool name is required"}
        )
    
    # Find the tool implementation
    try:
        # Try to get the tool from controllers
        for controller_name, controller in controllers.items():
            if hasattr(controller, tool_name):
                tool_impl = getattr(controller, tool_name)
                if callable(tool_impl):
                    # Call the tool with args
                    result = await tool_impl(**args)
                    return JSONResponse(content=result)
        
        # If not found in controllers, try model methods
        for model_name, model in models.items():
            if hasattr(model, tool_name):
                tool_impl = getattr(model, tool_name)
                if callable(tool_impl):
                    # Call the tool with args
                    result = await tool_impl(**args)
                    return JSONResponse(content=result)
        
        # If still not found, check extensions
        if hasattr(extensions, tool_name):
            tool_impl = getattr(extensions, tool_name)
            if callable(tool_impl):
                # Call the tool with args
                result = await tool_impl(**args)
                return JSONResponse(content=result)
        
        # Tool not found
        return JSONResponse(
            status_code=404,
            content={"error": f"Tool '{tool_name}' not found"}
        )
    except Exception as e:
        # Log the error
        logger.error(f"Error executing tool '{tool_name}': {e}")
        logger.error(traceback.format_exc())
        
        # Return error response
        return JSONResponse(
            status_code=500,
            content={"error": f"Error executing tool: {str(e)}"}
        )

# MCP Tool handling
async def tool_handler(request: Request):
    """Handle MCP tool requests."""
    data = await request.json()
    
    tool_name = data.get("name")
    server_name = data.get("server", "default")
    args = data.get("args", {})
    
    if not tool_name:
        return JSONResponse(
            status_code=400,
            content={"error": "Tool name is required"}
        )
    
    # Find the tool implementation
    try:
        # Try to get the tool from controllers
        for controller_name, controller in controllers.items():
            if hasattr(controller, tool_name):
                tool_impl = getattr(controller, tool_name)
                if callable(tool_impl):
                    # Call the tool with args
                    result = await tool_impl(**args)
                    return JSONResponse(content=result)
        
        # If not found in controllers, try model methods
        for model_name, model in models.items():
            if hasattr(model, tool_name):
                tool_impl = getattr(model, tool_name)
                if callable(tool_impl):
                    # Call the tool with args
                    result = await tool_impl(**args)
                    return JSONResponse(content=result)
        
        # If still not found, check extensions
        if hasattr(extensions, tool_name):
            tool_impl = getattr(extensions, tool_name)
            if callable(tool_impl):
                # Call the tool with args
                result = await tool_impl(**args)
                return JSONResponse(content=result)
        
        # Tool not found
        return JSONResponse(
            status_code=404,
            content={"error": f"Tool '{tool_name}' not found"}
        )
    except Exception as e:
        # Log the error
        logger.error(f"Error executing tool '{tool_name}': {e}")
        logger.error(traceback.format_exc())
        
        # Return error response
        return JSONResponse(
            status_code=500,
            content={"error": f"Error executing tool: {str(e)}"}
        )
