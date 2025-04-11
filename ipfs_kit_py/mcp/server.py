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
from ipfs_kit_py.mcp.controllers.cli_controller import CliController
from ipfs_kit_py.mcp.controllers.credential_controller import CredentialController

# Import credential manager
from ipfs_kit_py.credential_manager import CredentialManager

# Import storage manager
from ipfs_kit_py.mcp.models.storage_manager import StorageManager
from ipfs_kit_py.mcp.models.storage_bridge import StorageBridgeModel
from ipfs_kit_py.mcp.controllers.storage_manager_controller import StorageManagerController

# Import storage controllers
try:
    from ipfs_kit_py.mcp.controllers.storage.s3_controller import S3Controller
    HAS_S3_CONTROLLER = True
except ImportError:
    HAS_S3_CONTROLLER = False

try:
    from ipfs_kit_py.mcp.controllers.storage.huggingface_controller import HuggingFaceController
    HAS_HUGGINGFACE_CONTROLLER = True
except ImportError:
    HAS_HUGGINGFACE_CONTROLLER = False

try:
    from ipfs_kit_py.mcp.controllers.storage.storacha_controller import StorachaController
    HAS_STORACHA_CONTROLLER = True
except ImportError:
    HAS_STORACHA_CONTROLLER = False

try:
    from ipfs_kit_py.mcp.controllers.storage.filecoin_controller import FilecoinController
    HAS_FILECOIN_CONTROLLER = True
except ImportError:
    HAS_FILECOIN_CONTROLLER = False

try:
    from ipfs_kit_py.mcp.controllers.storage.lassie_controller import LassieController
    HAS_LASSIE_CONTROLLER = True
except ImportError:
    HAS_LASSIE_CONTROLLER = False

# Import Aria2 controller
try:
    from ipfs_kit_py.mcp.controllers.aria2_controller import Aria2Controller
    from ipfs_kit_py.mcp.models.aria2_model import Aria2Model
    from ipfs_kit_py.aria2_kit import aria2_kit
    HAS_ARIA2_CONTROLLER = True
except ImportError:
    HAS_ARIA2_CONTROLLER = False

# Import LibP2P controller
try:
    from ipfs_kit_py.mcp.controllers.libp2p_controller import LibP2PController
    from ipfs_kit_py.mcp.models.libp2p_model import LibP2PModel
    from ipfs_kit_py.libp2p import HAS_LIBP2P
    HAS_LIBP2P_CONTROLLER = True
except ImportError:
    HAS_LIBP2P_CONTROLLER = False

# Import MCP Discovery controller
try:
    from ipfs_kit_py.mcp.controllers.mcp_discovery_controller import MCPDiscoveryController
    from ipfs_kit_py.mcp.models.mcp_discovery_model import MCPDiscoveryModel
    HAS_MCP_DISCOVERY_CONTROLLER = True
except ImportError:
    HAS_MCP_DISCOVERY_CONTROLLER = False

# Import optional controllers
try:
    from ipfs_kit_py.mcp.controllers.fs_journal_controller import FsJournalController
    HAS_FS_JOURNAL_CONTROLLER = True
except ImportError:
    HAS_FS_JOURNAL_CONTROLLER = False

try:
    from ipfs_kit_py.mcp.controllers.distributed_controller import DistributedController
    HAS_DISTRIBUTED_CONTROLLER = True
except ImportError:
    HAS_DISTRIBUTED_CONTROLLER = False

try:
    from ipfs_kit_py.mcp.controllers.webrtc_controller import WebRTCController
    HAS_WEBRTC_CONTROLLER = True
except ImportError:
    HAS_WEBRTC_CONTROLLER = False

try:
    from ipfs_kit_py.mcp.controllers.peer_websocket_controller import PeerWebSocketController
    HAS_PEER_WEBSOCKET_CONTROLLER = True
except ImportError:
    HAS_PEER_WEBSOCKET_CONTROLLER = False

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
                isolation_mode: bool = False,
                config: Dict[str, Any] = None,
                ipfs_kit_instance=None):
        """
        Initialize the MCP Server.

        Args:
            debug_mode: Enable detailed debug logging and debug endpoints
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            persistence_path: Path for MCP server persistence files
            isolation_mode: Run in isolated mode without affecting host system
            config: Optional configuration dictionary for components
            ipfs_kit_instance: Optional pre-initialized IPFS Kit instance
        """
        self.ipfs_kit_instance = ipfs_kit_instance
        self.debug_mode = debug_mode
        self.isolation_mode = isolation_mode
        self.persistence_path = persistence_path or os.path.expanduser("~/.ipfs_kit/mcp")
        self.instance_id = str(uuid.uuid4())
        self.config = config or {}

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
        try:
            os.makedirs(self.persistence_path, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create persistence directory at {self.persistence_path}: {e}")
            # Use a temporary directory as fallback
            import tempfile
            self.persistence_path = tempfile.mkdtemp(prefix="mcp_server_")
            logger.warning(f"Using temporary directory for persistence: {self.persistence_path}")
            
        # Initialize result tracking for component initialization
        self.initialization_results = {
            "success": True,
            "errors": [],
            "warnings": []
        }

        # Initialize core components
        cache_config = self.config.get("cache", {})

        # Extract core cache settings from config
        memory_limit = cache_config.get("memory_cache_size", 100 * 1024 * 1024)  # Default 100MB
        disk_limit = cache_config.get("local_cache_size", 1024 * 1024 * 1024)  # Default 1GB

        # Initialize cache manager, providing the config as a parameter if supported
        try:
            # Try the new constructor signature with config parameter
            self.cache_manager = MCPCacheManager(
                base_path=os.path.join(self.persistence_path, "cache"),
                debug_mode=self.debug_mode,
                config=cache_config
            )
        except Exception as e:
            logger.warning(f"Error initializing cache manager with config: {e}")
            self.initialization_results["warnings"].append(f"Cache manager initialization with config failed: {e}")
            
            # Fall back to older constructor without config parameter
            try:
                logger.info("Falling back to legacy cache manager initialization")
                self.cache_manager = MCPCacheManager(
                    base_path=os.path.join(self.persistence_path, "cache"),
                    memory_limit=memory_limit,
                    disk_limit=disk_limit,
                    debug_mode=self.debug_mode
                )
            except Exception as e:
                logger.error(f"Failed to initialize cache manager: {e}")
                self.initialization_results["success"] = False
                self.initialization_results["errors"].append(f"Cache manager initialization failed: {e}")
                # Use a minimal in-memory cache as fallback
                from collections import OrderedDict
                class MinimalCache:
                    def __init__(self):
                        self.cache = OrderedDict()
                        self.get_cache_info = lambda: {"type": "minimal", "size": len(self.cache)}
                        self.put = lambda k, v, **kwargs: self.cache.update({k: v})
                        self.get = lambda k, **kwargs: self.cache.get(k)
                        self.clear = lambda: self.cache.clear()
                        self._save_metadata = lambda: None
                        
                self.cache_manager = MinimalCache()
                logger.warning("Using minimal in-memory cache as fallback")

        # Initialize credential manager
        try:
            self.credential_manager = CredentialManager(
                config={
                    "credential_store": "file",  # Use file-based storage for server persistence
                    "credential_file_path": os.path.join(self.persistence_path, "credentials.json"),
                    "encrypt_file_credentials": True
                }
            )
        except Exception as e:
            logger.error(f"Failed to initialize credential manager: {e}")
            self.initialization_results["success"] = False
            self.initialization_results["errors"].append(f"Credential manager initialization failed: {e}")
            # Create a minimal credential manager for basic functionality
            class MinimalCredentialManager:
                def __init__(self):
                    self.credential_cache = {}
                    self.config = {"credential_store": "memory"}
                    self.list_credentials = lambda: []
                    self.add_credential = lambda s, n, c: self.credential_cache.update({f"{s}_{n}": {"credentials": c}})
                    self.get_credential = lambda s, n: None
                    
            self.credential_manager = MinimalCredentialManager()
            logger.warning("Using minimal in-memory credential manager as fallback")

        # Initialize IPFS kit instance with automatic daemon management
        try:
            if self.ipfs_kit_instance:
                # Use the provided IPFS kit instance
                logger.info("Using provided IPFS kit instance")
                self.ipfs_kit = self.ipfs_kit_instance
            else:
                # Create a new IPFS kit instance
                kit_options = {}
                if self.isolation_mode:
                    # Use isolated IPFS path for testing
                    kit_options["metadata"] = {
                        "ipfs_path": os.path.join(self.persistence_path, "ipfs"),
                        "role": "leecher",  # Use lightweight role for testing
                        "test_mode": True
                    }

                # Enable automatic daemon management
                logger.info("Creating new IPFS kit instance")
                self.ipfs_kit = ipfs_kit(
                    metadata=kit_options.get("metadata"),
                    auto_start_daemons=True  # Automatically start daemons when needed
                )
        except Exception as e:
            logger.error(f"Failed to initialize IPFS kit: {e}")
            self.initialization_results["success"] = False
            self.initialization_results["errors"].append(f"IPFS kit initialization failed: {e}")
            # Create minimal ipfs_kit instance for basic functionality
            class MinimalIPFSKit:
                def __init__(self):
                    self.resources = {}
                    self.metadata = {}
                    
            self.ipfs_kit = MinimalIPFSKit()
            logger.warning("Using minimal IPFS kit as fallback")

        # Start daemon health monitoring to ensure they keep running
        if not self.debug_mode and hasattr(self.ipfs_kit, 'start_daemon_health_monitor'):
            try:
                self.ipfs_kit.start_daemon_health_monitor(
                    check_interval=60,  # Check health every minute
                    auto_restart=True   # Automatically restart failed daemons
                )
            except Exception as e:
                logger.warning(f"Failed to start daemon health monitor: {e}")
                self.initialization_results["warnings"].append(f"Daemon health monitor failed: {e}")

        # Initialize models dictionary
        self.models = {}
        
        # Initialize IPFS model
        try:
            self.models["ipfs"] = IPFSModel(
                ipfs_kit_instance=self.ipfs_kit,
                cache_manager=self.cache_manager,
                credential_manager=self.credential_manager
            )
            logger.info("IPFS Model initialized")
        except Exception as e:
            logger.error(f"Failed to initialize IPFS model: {e}")
            self.initialization_results["success"] = False
            self.initialization_results["errors"].append(f"IPFS model initialization failed: {e}")
            # Create a minimal IPFS model for basic functionality
            class MinimalIPFSModel:
                def __init__(self):
                    self.get_stats = lambda: {"status": "minimal"}
                    self.reset = lambda: None
                    
            self.models["ipfs"] = MinimalIPFSModel()
            logger.warning("Using minimal IPFS model as fallback")

        # Initialize Storage Manager with proper error handling
        try:
            # Extract resources and metadata from ipfs_kit if available
            resources = getattr(self.ipfs_kit, 'resources', {})
            metadata = getattr(self.ipfs_kit, 'metadata', {})

            self.storage_manager = StorageManager(
                ipfs_model=self.models["ipfs"],
                cache_manager=self.cache_manager,
                credential_manager=self.credential_manager,
                resources=resources,
                metadata=metadata
            )
            logger.info("Storage Manager initialized")
            
            # Add models from storage manager to models dictionary
            for name, model in self.storage_manager.get_all_models().items():
                self.models[f"storage_{name}"] = model
                logger.info(f"Storage model {name} added")
                
            # Initialize Storage Bridge Model
            try:
                self.storage_bridge = StorageBridgeModel(
                    ipfs_model=self.models["ipfs"],
                    backends=self.storage_manager.get_all_models(),
                    cache_manager=self.cache_manager
                )
                
                # Add storage bridge to the models dictionary
                self.models["storage_bridge"] = self.storage_bridge
                logger.info("Storage Bridge Model added")
                
                # Integrate the storage bridge with the storage manager
                self.storage_manager.storage_bridge = self.storage_bridge
                logger.info("Storage Bridge Model integrated with Storage Manager")
            except Exception as e:
                logger.warning(f"Failed to initialize Storage Bridge: {e}")
                self.initialization_results["warnings"].append(f"Storage Bridge initialization failed: {e}")
                
        except Exception as e:
            logger.error(f"Failed to initialize Storage Manager: {e}")
            self.initialization_results["success"] = False
            self.initialization_results["errors"].append(f"Storage Manager initialization failed: {e}")
            
            # Create minimal versions for basic functionality
            class MinimalStorageManager:
                def __init__(self):
                    self.get_all_models = lambda: {}
                    self.get_available_backends = lambda: []
                    self.get_stats = lambda: {"status": "minimal"}
                    self.reset = lambda: None
                    self.storage_bridge = None
                    
            self.storage_manager = MinimalStorageManager()
            logger.warning("Using minimal Storage Manager as fallback")

        # Initialize controllers with proper error handling
        self.controllers = {}
        
        # Initialize core controllers
        self._init_core_controllers()
        
        # Initialize storage controllers
        self._init_storage_controllers()
        
        # Initialize optional controllers
        self._init_optional_controllers()

        # Set the persistence manager
        self.persistence = self.cache_manager
        
        # Log initialization results
        if not self.initialization_results["success"]:
            logger.warning(f"MCP Server initialized with errors: {len(self.initialization_results['errors'])} errors, "
                          f"{len(self.initialization_results['warnings'])} warnings")
        elif self.initialization_results["warnings"]:
            logger.info(f"MCP Server initialized with {len(self.initialization_results['warnings'])} warnings")
        else:
            logger.info("MCP Server initialized successfully")
            
    def _init_core_controllers(self):
        """Initialize the core controllers with proper error handling."""
        # Core controllers (IPFS, CLI, Credentials, Storage Manager)
        core_controllers = [
            ("ipfs", lambda: IPFSController(self.models["ipfs"])),
            ("cli", lambda: CliController(self.models["ipfs"])),
            ("credentials", lambda: CredentialController(self.credential_manager)),
            ("storage_manager", lambda: StorageManagerController(self.storage_manager))
        ]
        
        for name, constructor in core_controllers:
            try:
                self.controllers[name] = constructor()
                logger.info(f"{name.capitalize()} Controller added")
            except Exception as e:
                logger.error(f"Failed to initialize {name} controller: {e}")
                self.initialization_results["errors"].append(f"{name} controller initialization failed: {e}")
                # Core controllers are required, so mark initialization as failed
                self.initialization_results["success"] = False
    
    def _init_storage_controllers(self):
        """Initialize storage controllers with proper error handling."""
        # Storage controllers
        storage_controllers = [
            ("storage_s3", HAS_S3_CONTROLLER, lambda: S3Controller(self.models["storage_s3"])),
            ("storage_huggingface", HAS_HUGGINGFACE_CONTROLLER, lambda: HuggingFaceController(self.models["storage_huggingface"])),
            ("storage_storacha", HAS_STORACHA_CONTROLLER, lambda: StorachaController(self.models["storage_storacha"])),
            ("storage_filecoin", HAS_FILECOIN_CONTROLLER, lambda: FilecoinController(self.models["storage_filecoin"])),
            ("storage_lassie", HAS_LASSIE_CONTROLLER, lambda: LassieController(self.models["storage_lassie"]))
        ]
        
        for controller_name, has_controller, constructor in storage_controllers:
            if has_controller and controller_name in self.models:
                try:
                    self.controllers[controller_name] = constructor()
                    logger.info(f"{controller_name.split('_')[1].capitalize()} Controller added")
                except Exception as e:
                    logger.warning(f"Failed to initialize {controller_name} controller: {e}")
                    self.initialization_results["warnings"].append(f"{controller_name} controller initialization failed: {e}")
    
    def _init_optional_controllers(self):
        """Initialize optional controllers with proper error handling."""
        # Aria2 Controller with model creation
        if HAS_ARIA2_CONTROLLER:
            try:
                # Initialize Aria2 model
                self.models["aria2"] = Aria2Model(
                    aria2_kit_instance=None,  # Will be created by the model
                    cache_manager=self.cache_manager,
                    credential_manager=self.credential_manager
                )
                # Initialize and add Aria2 controller
                self.controllers["aria2"] = Aria2Controller(self.models["aria2"])
                logger.info("Aria2 Controller added")
            except Exception as e:
                logger.warning(f"Failed to initialize Aria2 controller: {e}")
                self.initialization_results["warnings"].append(f"Aria2 controller initialization failed: {e}")
                # Clean up model if controller initialization failed
                if "aria2" in self.models:
                    del self.models["aria2"]
                    
        # LibP2P Controller with model creation
        if HAS_LIBP2P_CONTROLLER:
            try:
                # Extract resources and metadata
                resources = getattr(self.ipfs_kit, 'resources', {})
                metadata = getattr(self.ipfs_kit, 'metadata', {})
                
                # Initialize LibP2P model
                self.models["libp2p"] = LibP2PModel(
                    libp2p_peer_instance=None,  # Will be created by the model
                    cache_manager=self.cache_manager,
                    credential_manager=self.credential_manager,
                    resources=resources,
                    metadata=metadata
                )
                # Initialize and add LibP2P controller
                self.controllers["libp2p"] = LibP2PController(self.models["libp2p"])
                logger.info("LibP2P Controller added")
            except Exception as e:
                logger.warning(f"Failed to initialize LibP2P controller: {e}")
                self.initialization_results["warnings"].append(f"LibP2P controller initialization failed: {e}")
                # Clean up model if controller initialization failed
                if "libp2p" in self.models:
                    del self.models["libp2p"]
        
        # MCP Discovery Controller with model creation
        if HAS_MCP_DISCOVERY_CONTROLLER:
            try:
                # Extract resources and metadata
                resources = getattr(self.ipfs_kit, 'resources', {})
                metadata = getattr(self.ipfs_kit, 'metadata', {})
                
                # Get role from metadata if available, otherwise use "master"
                role = metadata.get("role", "master")
                
                # Initialize MCP Discovery model
                self.models["mcp_discovery"] = MCPDiscoveryModel(
                    server_id=self.instance_id,
                    role=role,  # Use role from metadata or default to master
                    libp2p_model=self.models.get("libp2p"),  # Safely get libp2p model if available
                    ipfs_model=self.models.get("ipfs"),  # Safely get ipfs model if available
                    cache_manager=self.cache_manager,
                    credential_manager=self.credential_manager,
                    resources=resources,
                    metadata=metadata
                )
                # Initialize and add MCP Discovery controller
                self.controllers["mcp_discovery"] = MCPDiscoveryController(self.models["mcp_discovery"])
                logger.info("MCP Discovery Controller added")
            except Exception as e:
                logger.warning(f"Failed to initialize MCP Discovery controller: {e}")
                self.initialization_results["warnings"].append(f"MCP Discovery controller initialization failed: {e}")
                # Clean up model if controller initialization failed
                if "mcp_discovery" in self.models:
                    del self.models["mcp_discovery"]
        
        # Optional controllers that use the IPFS model
        optional_controllers = [
            ("distributed", HAS_DISTRIBUTED_CONTROLLER, lambda: DistributedController(self.models["ipfs"])),
            ("webrtc", HAS_WEBRTC_CONTROLLER, lambda: WebRTCController(self.models["ipfs"])),
            ("peer_websocket", HAS_PEER_WEBSOCKET_CONTROLLER, lambda: PeerWebSocketController(self.models["ipfs"])),
            ("fs_journal", HAS_FS_JOURNAL_CONTROLLER, lambda: FsJournalController(self.models["ipfs"]))
        ]
        
        for name, has_controller, constructor in optional_controllers:
            if has_controller and "ipfs" in self.models:
                try:
                    self.controllers[name] = constructor()
                    logger.info(f"{name.capitalize()} Controller added")
                except Exception as e:
                    logger.warning(f"Failed to initialize {name} controller: {e}")
                    self.initialization_results["warnings"].append(f"{name} controller initialization failed: {e}")
                    # Optional controllers don't affect overall success

    def get_router(self) -> APIRouter:
        """Get an API router with all controller routes registered.

        Returns:
            FastAPI router with all registered controller routes
        """
        return self._create_router()
        
    def register_controllers(self) -> APIRouter:
        """Register all controllers with a router.
        
        This method is primarily for testing purposes and similar to _create_router,
        but it assumes the router and controllers are already set up.
        
        Returns:
            The router with controllers registered
        """
        if not hasattr(self, 'router') or not self.router:
            self.router = APIRouter(prefix="", tags=["mcp"])
        
        # Register core endpoints with error handling
        core_endpoints = [
            ("/health", self.health_check, ["GET"]),
            ("/debug", self.get_debug_state, ["GET"]),
            ("/operations", self.get_operation_log, ["GET"]),
            ("/daemon/start/{daemon_type}", self.start_daemon, ["POST"]),
            ("/daemon/stop/{daemon_type}", self.stop_daemon, ["POST"]),
            ("/daemon/status", self.get_daemon_status, ["GET"]),
            ("/daemon/monitor/start", self.start_daemon_monitor, ["POST"]),
            ("/daemon/monitor/stop", self.stop_daemon_monitor, ["POST"])
        ]
        
        errors = []
        
        for path, endpoint, methods in core_endpoints:
            try:
                self.router.add_api_route(path, endpoint, methods=methods)
                logger.debug(f"Registered core endpoint: {methods[0]} {path}")
            except Exception as e:
                error_msg = f"Failed to register core endpoint {path}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Register controller routes using our robust method
        self._register_controller_routes(self.router)
                
        # If we had any errors, log them together
        if errors:
            logger.error(f"Failed to register {len(errors)} core endpoints: {errors}")
                
        return self.router

    def _create_router(self) -> APIRouter:
        """Create FastAPI router for MCP endpoints."""
        router = APIRouter(prefix="", tags=["mcp"])

        # Register core endpoints with error handling
        core_endpoints = [
            ("/health", self.health_check, ["GET"]),
            ("/debug", self.get_debug_state, ["GET"]),
            ("/operations", self.get_operation_log, ["GET"]),
            ("/daemon/start/{daemon_type}", self.start_daemon, ["POST"]),
            ("/daemon/stop/{daemon_type}", self.stop_daemon, ["POST"]),
            ("/daemon/status", self.get_daemon_status, ["GET"]),
            ("/daemon/monitor/start", self.start_daemon_monitor, ["POST"]),
            ("/daemon/monitor/stop", self.stop_daemon_monitor, ["POST"])
        ]
        
        for path, endpoint, methods in core_endpoints:
            try:
                router.add_api_route(path, endpoint, methods=methods)
                logger.debug(f"Registered core endpoint: {methods[0]} {path}")
            except Exception as e:
                logger.error(f"Failed to register core endpoint {path}: {e}")
                # Core endpoints are essential, so we should track this error
                self.initialization_results["errors"].append(f"Failed to register core endpoint {path}: {e}")

        # Register controller endpoints with proper error handling
        self._register_controller_routes(router)

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
                try:
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
                except Exception as e:
                    # Log error and return a 500 response
                    process_time = time.time() - start_time
                    logger.error(f"Error in middleware: {e}")
                    
                    self._log_operation({
                        "type": "error",
                        "session_id": session_id,
                        "path": request.url.path,
                        "method": request.method,
                        "error": str(e),
                        "process_time": process_time,
                        "timestamp": time.time()
                    })
                    
                    # Create error response
                    from fastapi.responses import JSONResponse
                    error_response = JSONResponse(
                        status_code=500,
                        content={
                            "success": False,
                            "error": "Internal server error",
                            "error_type": "UnhandledException",
                            "timestamp": time.time()
                        }
                    )
                    
                    # Add debug headers
                    error_response.headers["X-MCP-Session-ID"] = session_id
                    error_response.headers["X-MCP-Process-Time"] = f"{process_time:.6f}"
                    
                    return error_response

            self.debug_middleware = debug_middleware

        return router
        
    def _register_controller_routes(self, router: APIRouter):
        """Register all controller routes with error handling.
        
        Args:
            router: The FastAPI router to register routes with
        """
        # Define all controllers to register
        core_controllers = ["ipfs", "cli", "credentials", "storage_manager"]
        storage_controllers = [
            "storage_s3", "storage_huggingface", "storage_storacha", 
            "storage_filecoin", "storage_lassie"
        ]
        optional_controllers = [
            "distributed", "webrtc", "peer_websocket", "fs_journal",
            "aria2", "libp2p", "mcp_discovery"
        ]
        
        # Register core controllers (required for functionality)
        for controller_name in core_controllers:
            if controller_name in self.controllers:
                try:
                    controller = self.controllers[controller_name]
                    if hasattr(controller, 'register_routes') and callable(controller.register_routes):
                        controller.register_routes(router)
                        logger.info(f"Registered routes for {controller_name} controller")
                    else:
                        logger.warning(f"{controller_name} controller does not have a register_routes method")
                        self.initialization_results["warnings"].append(
                            f"{controller_name} controller does not have a register_routes method"
                        )
                except Exception as e:
                    logger.error(f"Failed to register routes for {controller_name} controller: {e}")
                    self.initialization_results["errors"].append(
                        f"Failed to register routes for {controller_name} controller: {e}"
                    )
            else:
                logger.error(f"Core controller {controller_name} not found, required for functionality")
                self.initialization_results["errors"].append(f"Core controller {controller_name} not found")
                
        # Register storage controllers (optional, but important)
        for controller_name in storage_controllers:
            if controller_name in self.controllers:
                try:
                    controller = self.controllers[controller_name]
                    if hasattr(controller, 'register_routes') and callable(controller.register_routes):
                        controller.register_routes(router)
                        logger.info(f"Registered routes for {controller_name} controller")
                    else:
                        logger.warning(f"{controller_name} controller does not have a register_routes method")
                        self.initialization_results["warnings"].append(
                            f"{controller_name} controller does not have a register_routes method"
                        )
                except Exception as e:
                    logger.warning(f"Failed to register routes for {controller_name} controller: {e}")
                    self.initialization_results["warnings"].append(
                        f"Failed to register routes for {controller_name} controller: {e}"
                    )
                    
        # Register optional controllers (nice to have)
        for controller_name in optional_controllers:
            if controller_name in self.controllers:
                try:
                    controller = self.controllers[controller_name]
                    if hasattr(controller, 'register_routes') and callable(controller.register_routes):
                        controller.register_routes(router)
                        logger.info(f"Registered routes for {controller_name} controller")
                    else:
                        logger.warning(f"{controller_name} controller does not have a register_routes method")
                        self.initialization_results["warnings"].append(
                            f"{controller_name} controller does not have a register_routes method"
                        )
                except Exception as e:
                    logger.warning(f"Failed to register routes for {controller_name} controller: {e}")
                    self.initialization_results["warnings"].append(
                        f"Failed to register routes for {controller_name} controller: {e}"
                    )

    def register_with_app(self, app: FastAPI, prefix: str = "/mcp"):
        """
        Register MCP server with a FastAPI application.

        Args:
            app: FastAPI application instance
            prefix: URL prefix for MCP endpoints
        """
        # Track registration success
        registration_success = True
        errors = []
        
        # Mount the router
        try:
            app.include_router(self.router, prefix=prefix)
            logger.info(f"MCP Server router registered at prefix: {prefix}")
        except Exception as e:
            error_msg = f"Failed to register MCP router at prefix {prefix}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
            registration_success = False

        # Add debug middleware if enabled
        if self.debug_mode and self.debug_middleware:
            try:
                app.middleware("http")(self.debug_middleware)
                logger.info(f"Debug middleware added to FastAPI app")
            except Exception as e:
                error_msg = f"Failed to register debug middleware: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                # Non-critical error, continue with registration
        else:
            logger.info(f"Debug mode is disabled, middleware not added")

        # For compatibility with tests that expect endpoints at /api/v0/..., register these endpoints directly
        # This ensures we respond to both /mcp/... and /api/v0/... endpoints
        if prefix != "/api/v0":
            try:
                # Create compatibility router
                api_v0_router = APIRouter(prefix="/api/v0", tags=["mcp-api-v0"])
                
                # Core endpoints for test compatibility
                compat_endpoints = [
                    ("/health", self.health_check, ["GET"]),
                    ("/debug", self.get_debug_state, ["GET"]),
                    ("/operations", self.get_operation_log, ["GET"]),
                    ("/daemon/status", self.get_daemon_status, ["GET"])
                ]
                
                # Register compatibility endpoints with error handling
                for path, endpoint, methods in compat_endpoints:
                    try:
                        api_v0_router.add_api_route(path, endpoint, methods=methods)
                        logger.debug(f"Registered compatibility endpoint: {methods[0]} /api/v0{path}")
                    except Exception as e:
                        error_msg = f"Failed to register compatibility endpoint /api/v0{path}: {e}"
                        logger.warning(error_msg)
                        # Non-critical error for backward compatibility, continue with registration
                
                # Include compatibility router in the app
                app.include_router(api_v0_router)
                logger.info(f"MCP Server also registered at /api/v0 for test compatibility")
            except Exception as e:
                error_msg = f"Failed to register compatibility router at /api/v0: {e}"
                logger.warning(error_msg)
                errors.append(error_msg)
                # Non-critical error, continue with registration

        # Register error handler for global exception handling
        try:
            @app.exception_handler(Exception)
            async def global_exception_handler(request: Request, exc: Exception):
                """Global exception handler for unhandled exceptions."""
                error_id = str(uuid.uuid4())
                logger.error(f"Unhandled exception in request {request.url.path} [{error_id}]: {exc}")
                
                # Log detailed information in debug mode
                if self.debug_mode:
                    import traceback
                    logger.debug(f"Exception traceback [{error_id}]:\n{traceback.format_exc()}")
                    
                    # Log the request details
                    try:
                        body = await request.body()
                        logger.debug(f"Request details [{error_id}]:\n"
                                   f"URL: {request.url}\n"
                                   f"Headers: {request.headers}\n"
                                   f"Body: {body.decode('utf-8', errors='replace')[:1000]}")
                    except Exception as e:
                        logger.debug(f"Could not log request details [{error_id}]: {e}")
                
                # Return standardized error response
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "error": "Internal server error",
                        "error_type": type(exc).__name__,
                        "error_id": error_id,
                        "timestamp": time.time()
                    }
                )
            
            logger.info("Registered global exception handler for improved error reporting")
        except Exception as e:
            error_msg = f"Failed to register global exception handler: {e}"
            logger.warning(error_msg)
            errors.append(error_msg)
            # Non-critical error, continue with registration

        # Log overall registration results
        if registration_success:
            logger.info(f"MCP Server successfully registered with FastAPI app")
            
            # Log any non-critical errors
            if errors:
                logger.warning(f"MCP Server registered with {len(errors)} non-critical errors")
                for i, error in enumerate(errors):
                    logger.warning(f"Non-critical error {i+1}: {error}")
        else:
            logger.error(f"MCP Server registration failed with FastAPI app")
            for i, error in enumerate(errors):
                logger.error(f"Error {i+1}: {error}")
            
        # Record registration results in initialization results if available
        if hasattr(self, 'initialization_results'):
            self.initialization_results["api_registration"] = {
                "success": registration_success,
                "errors": errors,
                "prefix": prefix,
                "timestamp": time.time()
            }

    def _log_operation(self, operation: Dict[str, Any]):
        """Log an operation for debugging purposes."""
        if self.debug_mode:
            self.operation_log.append(operation)

            # Keep log size reasonable
            if len(self.operation_log) > 1000:
                self.operation_log = self.operation_log[-1000:]

    async def health_check(self):
        """
        Health check endpoint.

        Returns information about the MCP server status, including daemon status,
        controller availability, and initialization results.
        """
        # Record start time to track health check execution time
        start_time = time.time()
        
        # Build basic health information
        health_info = {
            "success": True,
            "status": "ok",
            "timestamp": start_time,
            "server_id": self.instance_id,
            "debug_mode": self.debug_mode,
            "isolation_mode": self.isolation_mode
        }
        
        # Add initialization results if available
        if hasattr(self, 'initialization_results'):
            # Add basic information from initialization results
            initialization_success = self.initialization_results.get("success", True)
            error_count = len(self.initialization_results.get("errors", []))
            warning_count = len(self.initialization_results.get("warnings", []))
            
            health_info["initialization"] = {
                "success": initialization_success,
                "error_count": error_count,
                "warning_count": warning_count
            }
            
            # Update overall status based on initialization results
            if not initialization_success:
                health_info["status"] = "degraded"
                if error_count > 0:
                    # Include the most recent errors for diagnostics
                    health_info["initialization"]["recent_errors"] = self.initialization_results["errors"][-5:]

        # Add daemon status information if available
        daemon_info = {}
        try:
            # Check if the ipfs_kit has the necessary daemon status methods
            if hasattr(self.ipfs_kit, 'check_daemon_status'):
                try:
                    daemon_status = self.ipfs_kit.check_daemon_status()
                    daemons = daemon_status.get("daemons", {})

                    # Check each daemon's status
                    daemon_names = ["ipfs", "ipfs_cluster_service", "ipfs_cluster_follow"]
                    for daemon_name in daemon_names:
                        if daemon_name in daemons:
                            daemon_info[daemon_name] = {
                                "running": daemons[daemon_name].get("running", False),
                                "pid": daemons[daemon_name].get("pid")
                            }
                            
                            # Add detailed status if available
                            if "status" in daemons[daemon_name]:
                                daemon_info[daemon_name]["status"] = daemons[daemon_name]["status"]
                            
                            # Add error information if available
                            if "error" in daemons[daemon_name]:
                                daemon_info[daemon_name]["error"] = daemons[daemon_name]["error"]
                                
                            # Check if any daemons are not running
                            if daemon_name == "ipfs" and not daemons[daemon_name].get("running", False):
                                health_info["status"] = "degraded"  # IPFS daemon is critical
                                health_info["success"] = False
                except Exception as e:
                    daemon_info["status_check_error"] = str(e)
                    daemon_info["error_type"] = type(e).__name__
                    health_info["status"] = "degraded"  # Can't check daemon status
            else:
                daemon_info["status"] = "unknown"  # Can't check daemon status

            # Add auto-retry configuration status
            if hasattr(self.ipfs_kit, 'auto_start_daemons'):
                daemon_info["auto_start_daemons_enabled"] = self.ipfs_kit.auto_start_daemons

            # Add daemon health monitor status
            if hasattr(self.ipfs_kit, 'is_daemon_health_monitor_running'):
                try:
                    daemon_info["health_monitor_running"] = self.ipfs_kit.is_daemon_health_monitor_running()
                except Exception as e:
                    daemon_info["health_monitor_error"] = str(e)
        except Exception as e:
            # Don't fail the health check if daemon status check fails
            daemon_info["status_check_error"] = str(e)
            daemon_info["error_type"] = type(e).__name__
        
        # Add daemon info to health info
        health_info["daemons"] = daemon_info

        # Add information about controllers
        controllers_info = {}
        controller_errors = 0
        
        for controller_name, controller in self.controllers.items():
            # Initialize with basic information
            controllers_info[controller_name] = {
                "available": True  # Default to available
            }
            
            # If the controller has get_health method, try to use it
            if hasattr(controller, 'get_health') and callable(controller.get_health):
                try:
                    controller_health = await controller.get_health()
                    
                    # If get_health returns a dictionary with status information
                    if isinstance(controller_health, dict):
                        # Add basic availability
                        if "available" in controller_health:
                            controllers_info[controller_name]["available"] = controller_health["available"]
                            
                        # Add status if available
                        if "status" in controller_health:
                            controllers_info[controller_name]["status"] = controller_health["status"]
                            
                        # Add error information if available
                        if "error" in controller_health:
                            controllers_info[controller_name]["error"] = controller_health["error"]
                            controllers_info[controller_name]["available"] = False
                            controller_errors += 1
                            
                        # Add additional metrics if available
                        for key in ["operation_count", "success_count", "error_count"]:
                            if key in controller_health:
                                controllers_info[controller_name][key] = controller_health[key]
                    else:
                        # If not a dict, just use the result directly as available status
                        controllers_info[controller_name]["available"] = bool(controller_health)
                        
                except Exception as e:
                    # If health check fails, log the error and mark as unavailable
                    controllers_info[controller_name]["available"] = False
                    controllers_info[controller_name]["error"] = str(e)
                    controllers_info[controller_name]["error_type"] = type(e).__name__
                    controller_errors += 1
            else:
                # No health check method, so just mark as available (best effort)
                controllers_info[controller_name]["available"] = True
                controllers_info[controller_name]["health_check"] = "not_implemented"
        
        # Update overall status based on controller health
        if controller_errors > 0:
            if controller_errors == len(self.controllers):
                # All controllers have errors
                health_info["status"] = "critical"
                health_info["success"] = False
            else:
                # Some controllers have errors
                health_info["status"] = "degraded"
        
        # Add controllers to health info
        health_info["controllers"] = controllers_info
        
        # Add cache status information if available
        if hasattr(self, 'cache_manager') and hasattr(self.cache_manager, 'get_cache_info'):
            try:
                cache_info = self.cache_manager.get_cache_info()
                health_info["cache"] = cache_info
            except Exception as e:
                health_info["cache"] = {
                    "status": "error",
                    "error": str(e),
                    "error_type": type(e).__name__
                }
        
        # Add execution time for the health check itself
        health_info["execution_time_ms"] = round((time.time() - start_time) * 1000, 2)

        return health_info

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
            "session_count": len(self.sessions),
            "persistence_path": self.persistence_path
        }

        # Add daemon management information
        daemon_info = {}
        if hasattr(self.ipfs_kit, 'auto_start_daemons'):
            daemon_info["auto_start_daemons"] = self.ipfs_kit.auto_start_daemons

        if hasattr(self.ipfs_kit, 'check_daemon_status'):
            try:
                daemon_status_result = self.ipfs_kit.check_daemon_status()
                daemon_info["daemon_status"] = daemon_status_result.get("daemons", {})
            except Exception as e:
                daemon_info["daemon_status_error"] = str(e)

        if hasattr(self.ipfs_kit, 'is_daemon_health_monitor_running'):
            daemon_info["health_monitor_running"] = self.ipfs_kit.is_daemon_health_monitor_running()

        if hasattr(self.ipfs_kit, 'daemon_restart_history'):
            daemon_info["restart_history"] = self.ipfs_kit.daemon_restart_history

        server_info["daemon_management"] = daemon_info

        models_info = {}
        for name, model in self.models.items():
            if hasattr(model, "get_stats"):
                models_info[name] = model.get_stats()

        # Add storage manager stats
        if hasattr(self, "storage_manager"):
            models_info["storage_manager"] = self.storage_manager.get_stats()

        persistence_info = {
            "cache_info": self.cache_manager.get_cache_info()
        }

        # Add storage backends information
        storage_info = {
            "available_backends": getattr(self.storage_manager, "get_available_backends", lambda: {})()
        }
        
        # Add storage bridge information if available
        if hasattr(self, "storage_bridge"):
            storage_info["storage_bridge"] = self.storage_bridge.get_stats()

        # Add credential information (without sensitive data)
        credential_info = {
            "enabled": hasattr(self, "credential_manager"),
            "services": []
        }

        if hasattr(self, "credential_manager"):
            # Get count of credentials per service
            credential_counts = {}
            for cred in self.credential_manager.list_credentials():
                service = cred["service"]
                if service not in credential_counts:
                    credential_counts[service] = 0
                credential_counts[service] += 1

            credential_info["services"] = [
                {"service": service, "credential_count": count}
                for service, count in credential_counts.items()
            ]
            credential_info["total_count"] = sum(credential_counts.values())
            credential_info["store_type"] = self.credential_manager.config["credential_store"]

        return {
            "success": True,
            "server_info": server_info,
            "models": models_info,
            "persistence": persistence_info,
            "storage": storage_info,
            "credentials": credential_info,
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

    async def start_daemon(self, daemon_type: str):
        """
        Manually start a specific daemon.

        Args:
            daemon_type: Type of daemon to start ('ipfs', 'ipfs_cluster_service', 'ipfs_cluster_follow')
        """
        # Validate daemon type
        valid_types = ['ipfs', 'ipfs_cluster_service', 'ipfs_cluster_follow']
        if daemon_type not in valid_types:
            return {
                "success": False,
                "error": f"Invalid daemon type: {daemon_type}. Must be one of: {', '.join(valid_types)}",
                "error_type": "InvalidDaemonType"
            }

        # Implementation for starting daemon even if _start_daemon isn't available
        try:
            # First check if daemon is already running
            daemon_status = None
            if hasattr(self.ipfs_kit, 'check_daemon_status'):
                try:
                    # Check if method takes daemon_type parameter
                    import inspect
                    sig = inspect.signature(self.ipfs_kit.check_daemon_status)

                    if len(sig.parameters) > 1:
                        # Method takes daemon_type parameter
                        daemon_status = self.ipfs_kit.check_daemon_status(daemon_type)
                    else:
                        # Method doesn't take daemon_type parameter
                        daemon_status = self.ipfs_kit.check_daemon_status()

                    daemons = daemon_status.get("daemons", {})
                    if daemon_type in daemons and daemons[daemon_type].get("running", False):
                        return {
                            "success": True,
                            "status": "already_running",
                            "daemon_type": daemon_type,
                            "message": f"{daemon_type} daemon is already running",
                            "timestamp": time.time()
                        }
                except Exception as e:
                    logger.warning(f"Error checking daemon status: {e}")

            # If _start_daemon method is available, use it
            if hasattr(self.ipfs_kit, '_start_daemon'):
                result = self.ipfs_kit._start_daemon(daemon_type)

                # Log the action
                if result.get("success", False):
                    logger.info(f"Manually started {daemon_type} daemon")
                else:
                    logger.warning(f"Failed to manually start {daemon_type} daemon: {result.get('error', 'Unknown error')}")

                return result

            # Fall back to using ipfs.py's daemon start method for IPFS daemon
            if daemon_type == 'ipfs' and hasattr(self.ipfs_kit, 'ipfs') and hasattr(self.ipfs_kit.ipfs, 'start_daemon'):
                # Use the IPFS daemon start method
                try:
                    result = self.ipfs_kit.ipfs.start_daemon()
                    if result.get("success", False):
                        logger.info("Manually started IPFS daemon")
                    return result
                except Exception as e:
                    logger.error(f"Error starting IPFS daemon: {e}")
                    return {
                        "success": False,
                        "error": f"Error starting IPFS daemon: {str(e)}",
                        "error_type": "DaemonStartError"
                    }

            # For cluster daemons, try to find appropriate start method if available
            if daemon_type == 'ipfs_cluster_service' and hasattr(self.ipfs_kit, 'ipfs_cluster_service') and hasattr(self.ipfs_kit.ipfs_cluster_service, 'start_daemon'):
                try:
                    result = self.ipfs_kit.ipfs_cluster_service.start_daemon()
                    if result.get("success", False):
                        logger.info("Manually started IPFS Cluster service daemon")
                    return result
                except Exception as e:
                    logger.error(f"Error starting IPFS Cluster service daemon: {e}")
                    return {
                        "success": False,
                        "error": f"Error starting IPFS Cluster service daemon: {str(e)}",
                        "error_type": "DaemonStartError"
                    }

            if daemon_type == 'ipfs_cluster_follow' and hasattr(self.ipfs_kit, 'ipfs_cluster_follow') and hasattr(self.ipfs_kit.ipfs_cluster_follow, 'start_daemon'):
                try:
                    result = self.ipfs_kit.ipfs_cluster_follow.start_daemon()
                    if result.get("success", False):
                        logger.info("Manually started IPFS Cluster follow daemon")
                    return result
                except Exception as e:
                    logger.error(f"Error starting IPFS Cluster follow daemon: {e}")
                    return {
                        "success": False,
                        "error": f"Error starting IPFS Cluster follow daemon: {str(e)}",
                        "error_type": "DaemonStartError"
                    }

            # If we get here, we couldn't find an appropriate method to start the daemon
            return {
                "success": False,
                "error": f"No method available to start {daemon_type} daemon",
                "error_type": "UnsupportedOperation"
            }

        except Exception as e:
            logger.error(f"Error starting {daemon_type} daemon: {e}")
            return {
                "success": False,
                "error": f"Error starting {daemon_type} daemon: {str(e)}",
                "error_type": "DaemonStartError"
            }

    async def stop_daemon(self, daemon_type: str):
        """
        Manually stop a specific daemon.

        Args:
            daemon_type: Type of daemon to stop ('ipfs', 'ipfs_cluster_service', 'ipfs_cluster_follow')
        """
        # Validate daemon type
        valid_types = ['ipfs', 'ipfs_cluster_service', 'ipfs_cluster_follow']
        if daemon_type not in valid_types:
            return {
                "success": False,
                "error": f"Invalid daemon type: {daemon_type}. Must be one of: {', '.join(valid_types)}",
                "error_type": "InvalidDaemonType"
            }

        # Implementation for stopping daemon even if _stop_daemon isn't available
        try:
            # Check if daemon is running
            daemon_running = False
            daemon_pid = None
            if hasattr(self.ipfs_kit, 'check_daemon_status'):
                try:
                    # Check if method takes daemon_type parameter
                    import inspect
                    sig = inspect.signature(self.ipfs_kit.check_daemon_status)

                    if len(sig.parameters) > 1:
                        # Method takes daemon_type parameter
                        daemon_status = self.ipfs_kit.check_daemon_status(daemon_type)
                    else:
                        # Method doesn't take daemon_type parameter
                        daemon_status = self.ipfs_kit.check_daemon_status()

                    daemons = daemon_status.get("daemons", {})
                    if daemon_type in daemons:
                        daemon_running = daemons[daemon_type].get("running", False)
                        daemon_pid = daemons[daemon_type].get("pid")
                except Exception as e:
                    logger.warning(f"Error checking daemon status: {e}")

            # If daemon is not running, return success
            if not daemon_running and daemon_pid is None:
                return {
                    "success": True,
                    "status": "not_running",
                    "daemon_type": daemon_type,
                    "message": f"{daemon_type} daemon is not running",
                    "timestamp": time.time()
                }

            # If _stop_daemon method is available, use it
            if hasattr(self.ipfs_kit, '_stop_daemon'):
                result = self.ipfs_kit._stop_daemon(daemon_type)

                # Log the action
                if result.get("success", False):
                    logger.info(f"Manually stopped {daemon_type} daemon")
                else:
                    logger.warning(f"Failed to manually stop {daemon_type} daemon: {result.get('error', 'Unknown error')}")

                return result

            # Fall back to using ipfs.py's daemon stop method for IPFS daemon
            if daemon_type == 'ipfs' and hasattr(self.ipfs_kit, 'ipfs') and hasattr(self.ipfs_kit.ipfs, 'stop_daemon'):
                # Use the IPFS daemon stop method
                try:
                    result = self.ipfs_kit.ipfs.stop_daemon()
                    if result.get("success", False):
                        logger.info("Manually stopped IPFS daemon")
                    return result
                except Exception as e:
                    logger.error(f"Error stopping IPFS daemon: {e}")
                    return {
                        "success": False,
                        "error": f"Error stopping IPFS daemon: {str(e)}",
                        "error_type": "DaemonStopError"
                    }

            # For cluster daemons, try to find appropriate stop method if available
            if daemon_type == 'ipfs_cluster_service' and hasattr(self.ipfs_kit, 'ipfs_cluster_service') and hasattr(self.ipfs_kit.ipfs_cluster_service, 'stop_daemon'):
                try:
                    result = self.ipfs_kit.ipfs_cluster_service.stop_daemon()
                    if result.get("success", False):
                        logger.info("Manually stopped IPFS Cluster service daemon")
                    return result
                except Exception as e:
                    logger.error(f"Error stopping IPFS Cluster service daemon: {e}")
                    return {
                        "success": False,
                        "error": f"Error stopping IPFS Cluster service daemon: {str(e)}",
                        "error_type": "DaemonStopError"
                    }

            if daemon_type == 'ipfs_cluster_follow' and hasattr(self.ipfs_kit, 'ipfs_cluster_follow') and hasattr(self.ipfs_kit.ipfs_cluster_follow, 'stop_daemon'):
                try:
                    result = self.ipfs_kit.ipfs_cluster_follow.stop_daemon()
                    if result.get("success", False):
                        logger.info("Manually stopped IPFS Cluster follow daemon")
                    return result
                except Exception as e:
                    logger.error(f"Error stopping IPFS Cluster follow daemon: {e}")
                    return {
                        "success": False,
                        "error": f"Error stopping IPFS Cluster follow daemon: {str(e)}",
                        "error_type": "DaemonStopError"
                    }

            # If we have a PID, try to kill the process directly (last resort)
            if daemon_pid:
                import signal
                import os

                try:
                    # Try to terminate process gracefully
                    os.kill(daemon_pid, signal.SIGTERM)
                    logger.info(f"Sent SIGTERM to {daemon_type} daemon (PID: {daemon_pid})")

                    # Give it a moment to shut down
                    import time
                    time.sleep(2)

                    # Check if it's still running
                    try:
                        os.kill(daemon_pid, 0)  # This will raise OSError if process is not running
                        # Process is still running, force kill
                        os.kill(daemon_pid, signal.SIGKILL)
                        logger.info(f"Sent SIGKILL to {daemon_type} daemon (PID: {daemon_pid})")
                    except OSError:
                        # Process is no longer running
                        pass

                    return {
                        "success": True,
                        "status": "stopped",
                        "daemon_type": daemon_type,
                        "message": f"{daemon_type} daemon stopped via process signal",
                        "pid": daemon_pid,
                        "timestamp": time.time()
                    }
                except Exception as e:
                    logger.error(f"Error killing {daemon_type} daemon process: {e}")
                    return {
                        "success": False,
                        "error": f"Error killing {daemon_type} daemon process: {str(e)}",
                        "error_type": "ProcessKillError"
                    }

            # If we get here, we couldn't find an appropriate method to stop the daemon
            return {
                "success": False,
                "error": f"No method available to stop {daemon_type} daemon",
                "error_type": "UnsupportedOperation"
            }

        except Exception as e:
            logger.error(f"Error stopping {daemon_type} daemon: {e}")
            return {
                "success": False,
                "error": f"Error stopping {daemon_type} daemon: {str(e)}",
                "error_type": "DaemonStopError"
            }

    async def get_daemon_status(self):
        """
        Get status of all known daemons.
        """
        daemon_types = ['ipfs', 'ipfs_cluster_service', 'ipfs_cluster_follow']
        status_results = {}

        # Check if ipfs_kit has the required method
        if hasattr(self.ipfs_kit, 'check_daemon_status'):
            # Check if method takes daemon_type parameter
            import inspect
            sig = inspect.signature(self.ipfs_kit.check_daemon_status)

            if len(sig.parameters) > 1:
                # Method takes daemon_type parameter - get status for each daemon type
                for daemon_type in daemon_types:
                    try:
                        status = self.ipfs_kit.check_daemon_status(daemon_type)
                        status_results[daemon_type] = status
                    except Exception as e:
                        status_results[daemon_type] = {
                            "success": False,
                            "error": str(e),
                            "error_type": "StatusCheckError"
                        }
            else:
                # Method doesn't take daemon_type parameter - get all statuses at once
                try:
                    all_status = self.ipfs_kit.check_daemon_status()
                    daemons = all_status.get("daemons", {})
                    for daemon_type in daemon_types:
                        if daemon_type in daemons:
                            status_results[daemon_type] = daemons[daemon_type]
                        else:
                            status_results[daemon_type] = {
                                "success": False,
                                "error": f"No status found for {daemon_type}",
                                "error_type": "MissingDaemonStatus"
                            }
                except Exception as e:
                    for daemon_type in daemon_types:
                        status_results[daemon_type] = {
                            "success": False,
                            "error": str(e),
                            "error_type": "StatusCheckError"
                        }
        else:
            # Fall back to checking daemon status manually
            # This implementation handles the case when check_daemon_status isn't available
            for daemon_type in daemon_types:
                try:
                    # Create basic status structure
                    daemon_status = {
                        "success": False,
                        "running": False,
                        "pid": None,
                        "last_checked": time.time()
                    }

                    # Check IPFS daemon using ipfs.py module if available
                    if daemon_type == 'ipfs' and hasattr(self.ipfs_kit, 'ipfs'):
                        ipfs_obj = self.ipfs_kit.ipfs

                        # Check if daemon is running by trying to get id
                        try:
                            # Try to get IPFS ID - this will typically error if daemon is not running
                            if hasattr(ipfs_obj, 'get_id'):
                                id_result = ipfs_obj.get_id()
                                if id_result.get("success", False):
                                    daemon_status["success"] = True
                                    daemon_status["running"] = True
                                    daemon_status["id"] = id_result.get("id")

                            # Try to get daemon PID if available
                            if hasattr(ipfs_obj, 'get_daemon_pid'):
                                pid_result = ipfs_obj.get_daemon_pid()
                                if pid_result and isinstance(pid_result, int):
                                    daemon_status["pid"] = pid_result
                                elif isinstance(pid_result, dict) and pid_result.get("success", False):
                                    daemon_status["pid"] = pid_result.get("pid")
                        except Exception as e:
                            daemon_status["error"] = str(e)
                            daemon_status["error_type"] = type(e).__name__

                    # Check IPFS Cluster daemons if available
                    elif daemon_type == 'ipfs_cluster_service' and hasattr(self.ipfs_kit, 'ipfs_cluster_service'):
                        cluster_obj = self.ipfs_kit.ipfs_cluster_service

                        # Check if daemon is running by trying to get peers
                        try:
                            if hasattr(cluster_obj, 'check_running'):
                                running_result = cluster_obj.check_running()
                                daemon_status["success"] = True
                                daemon_status["running"] = running_result.get("success", False)
                                if "pid" in running_result:
                                    daemon_status["pid"] = running_result["pid"]
                        except Exception as e:
                            daemon_status["error"] = str(e)
                            daemon_status["error_type"] = type(e).__name__

                    elif daemon_type == 'ipfs_cluster_follow' and hasattr(self.ipfs_kit, 'ipfs_cluster_follow'):
                        follow_obj = self.ipfs_kit.ipfs_cluster_follow

                        # Check if daemon is running by trying to check status
                        try:
                            if hasattr(follow_obj, 'check_running'):
                                running_result = follow_obj.check_running()
                                daemon_status["success"] = True
                                daemon_status["running"] = running_result.get("success", False)
                                if "pid" in running_result:
                                    daemon_status["pid"] = running_result["pid"]
                        except Exception as e:
                            daemon_status["error"] = str(e)
                            daemon_status["error_type"] = type(e).__name__

                    # Store the status for this daemon type
                    status_results[daemon_type] = daemon_status

                except Exception as e:
                    status_results[daemon_type] = {
                        "success": False,
                        "error": str(e),
                        "error_type": "StatusCheckError"
                    }

        # Get monitor status
        monitor_running = False
        if hasattr(self.ipfs_kit, 'is_daemon_health_monitor_running'):
            monitor_running = self.ipfs_kit.is_daemon_health_monitor_running()

        # Add IPFS path information if we can determine it
        for daemon_type in daemon_types:
            # For IPFS daemon
            if daemon_type == 'ipfs' and hasattr(self.ipfs_kit, 'ipfs'):
                if hasattr(self.ipfs_kit.ipfs, 'ipfs_path'):
                    status_results[daemon_type]["ipfs_path"] = self.ipfs_kit.ipfs.ipfs_path

        return {
            "success": True,
            "daemon_status": status_results,
            "daemon_monitor_running": monitor_running,
            "auto_start_daemons": getattr(self.ipfs_kit, 'auto_start_daemons', False),
            "timestamp": time.time()
        }

    async def start_daemon_monitor(self, check_interval: int = 60):
        """
        Start the daemon health monitoring system.

        Args:
            check_interval: How often to check daemon status (in seconds)
        """
        # Check if ipfs_kit has the required method
        if not hasattr(self.ipfs_kit, 'start_daemon_health_monitor'):
            return {
                "success": False,
                "error": "This version of ipfs_kit does not support daemon health monitoring",
                "error_type": "UnsupportedOperation"
            }

        # Check if already running
        if hasattr(self.ipfs_kit, 'is_daemon_health_monitor_running') and self.ipfs_kit.is_daemon_health_monitor_running():
            return {
                "success": False,
                "error": "Daemon health monitor is already running",
                "error_type": "AlreadyRunning"
            }

        # Try to start the monitor
        try:
            self.ipfs_kit.start_daemon_health_monitor(
                check_interval=check_interval,
                auto_restart=True
            )

            logger.info(f"Started daemon health monitor with check interval {check_interval}s")

            return {
                "success": True,
                "message": f"Daemon health monitor started with {check_interval}s check interval",
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error starting daemon health monitor: {e}")
            return {
                "success": False,
                "error": f"Error starting daemon health monitor: {str(e)}",
                "error_type": "MonitorStartError"
            }

    async def stop_daemon_monitor(self):
        """
        Stop the daemon health monitoring system.
        """
        # Check if ipfs_kit has the required method
        if not hasattr(self.ipfs_kit, 'stop_daemon_health_monitor'):
            return {
                "success": False,
                "error": "This version of ipfs_kit does not support daemon health monitoring",
                "error_type": "UnsupportedOperation"
            }

        # Check if actually running
        if hasattr(self.ipfs_kit, 'is_daemon_health_monitor_running') and not self.ipfs_kit.is_daemon_health_monitor_running():
            return {
                "success": False,
                "error": "Daemon health monitor is not running",
                "error_type": "NotRunning"
            }

        # Try to stop the monitor
        try:
            self.ipfs_kit.stop_daemon_health_monitor()

            logger.info("Stopped daemon health monitor")

            return {
                "success": True,
                "message": "Daemon health monitor stopped",
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error stopping daemon health monitor: {e}")
            return {
                "success": False,
                "error": f"Error stopping daemon health monitor: {str(e)}",
                "error_type": "MonitorStopError"
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

        # Reset daemon restart history if available
        if hasattr(self.ipfs_kit, 'reset_daemon_restart_history'):
            try:
                self.ipfs_kit.reset_daemon_restart_history()
                logger.info("Daemon restart history reset")
            except Exception as e:
                logger.error(f"Error resetting daemon restart history: {e}")

        logger.info("MCP Server state reset")

    def _close_logger_handlers(self):
        """Safely close all handlers attached to our logger.

        This prevents 'I/O operation on closed file' errors during shutdown.
        """
        # Use a local reference to avoid potential attribute errors
        local_logger = logger
        if not hasattr(local_logger, 'handlers'):
            return
            
        # Get a copy of handlers to avoid modification during iteration
        handlers_copy = list(local_logger.handlers)
        for handler in handlers_copy:
            try:
                # Flush any remaining logs
                if hasattr(handler, 'flush'):
                    handler.flush()
                # Close the handler
                if hasattr(handler, 'close'):
                    handler.close()
                # Remove the handler from the logger
                if handler in local_logger.handlers:
                    local_logger.removeHandler(handler)
            except Exception:
                # Ignore errors during handler cleanup
                pass

    def shutdown(self, close_logger=True):
        """Shutdown the server and clean up resources.

        Args:
            close_logger: Whether to close logger handlers after shutdown
        """
        # Check if we're already in interpreter shutdown
        if self._is_interpreter_shutting_down():
            # During interpreter shutdown, just silently clean up without logging
            try:
                self._close_logger_handlers()
            except Exception:
                pass
            return

        # Define a safe logging function
        def safe_log(level, message):
            """Log message safely, avoiding errors during shutdown"""
            try:
                if level == 'info':
                    logger.info(message)
                elif level == 'error':
                    logger.error(message)
                elif level == 'warning':
                    logger.warning(message)
            except Exception:
                # If logging fails, silently continue
                pass

        # Start with a message that we're shutting down
        safe_log('info', "MCP Server shutting down")

        # Stop daemon health monitor first to prevent daemon restarts during shutdown
        if hasattr(self.ipfs_kit, 'stop_daemon_health_monitor'):
            try:
                safe_log('info', "Stopping daemon health monitor...")
                self.ipfs_kit.stop_daemon_health_monitor()
                safe_log('info', "Daemon health monitor stopped")
            except Exception as e:
                safe_log('error', f"Error stopping daemon health monitor: {e}")

        # Stop cache manager cleanup thread
        if hasattr(self.cache_manager, 'stop_cleanup_thread'):
            try:
                safe_log('info', "Stopping cache cleanup thread...")
                self.cache_manager.stop_cleanup_thread()
                safe_log('info', "Cache cleanup thread stopped")
            except Exception as e:
                safe_log('error', f"Error stopping cache cleanup thread: {e}")

        # Save cache metadata
        try:
            safe_log('info', "Saving cache metadata...")
            self.cache_manager._save_metadata()
            safe_log('info', "Cache metadata saved")
        except Exception as e:
            safe_log('error', f"Error saving cache metadata during shutdown: {e}")

        # Make sure any in-memory credential changes are persisted
        if hasattr(self, 'credential_manager'):
            try:
                safe_log('info', "Ensuring credential persistence...")
                # The credential manager automatically persists changes, but we can
                # explicitly save by re-adding the credentials that are in cache
                for cred_key, cred_record in self.credential_manager.credential_cache.items():
                    if "_" in cred_key:
                        service, name = cred_key.split("_", 1)
                        self.credential_manager.add_credential(
                            service, name, cred_record["credentials"]
                        )
                safe_log('info', "Credentials persisted")
            except Exception as e:
                safe_log('error', f"Error persisting credentials during shutdown: {e}")

        # Special handling for peer WebSocket and WebRTC controllers to ensure async resources are cleaned up
        for controller_name in ["peer_websocket", "webrtc"]:
            if controller_name in self.controllers:
                try:
                    controller = self.controllers[controller_name]

                    # Use the controller's shutdown method
                    if hasattr(controller, "shutdown"):
                        safe_log('info', f"Shutting down {controller_name} controller...")

                        # Create event loop for async shutdown
                        import asyncio
                        try:
                            # Try to get existing event loop, create a new one if needed
                            try:
                                loop = asyncio.get_event_loop()
                            except RuntimeError:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)

                            # Run the shutdown method
                            if asyncio.iscoroutinefunction(controller.shutdown):
                                loop.run_until_complete(controller.shutdown())
                            else:
                                controller.shutdown()

                            safe_log('info', f"{controller_name} controller shutdown complete")
                        except Exception as e:
                            safe_log('error', f"Error in {controller_name} controller shutdown: {e}")

                            # Fallback to direct cleanup if shutdown method failed
                            if controller_name == "peer_websocket":
                                # Handle peer WebSocket specific cleanup
                                if hasattr(controller, "peer_websocket_server") and controller.peer_websocket_server:
                                    try:
                                        if not loop.is_closed():
                                            loop.run_until_complete(controller.peer_websocket_server.stop())
                                        controller.peer_websocket_server = None
                                        safe_log('info', "Peer WebSocket server stopped directly")
                                    except Exception as server_error:
                                        safe_log('error', f"Error stopping peer WebSocket server directly: {server_error}")

                                if hasattr(controller, "peer_websocket_client") and controller.peer_websocket_client:
                                    try:
                                        if not loop.is_closed():
                                            loop.run_until_complete(controller.peer_websocket_client.stop())
                                        controller.peer_websocket_client = None
                                        safe_log('info', "Peer WebSocket client stopped directly")
                                    except Exception as client_error:
                                        safe_log('error', f"Error stopping peer WebSocket client directly: {client_error}")

                            elif controller_name == "webrtc":
                                # Handle WebRTC specific cleanup
                                if hasattr(controller, "close_all_streaming_servers"):
                                    try:
                                        if not loop.is_closed():
                                            if asyncio.iscoroutinefunction(controller.close_all_streaming_servers):
                                                loop.run_until_complete(controller.close_all_streaming_servers())
                                            else:
                                                controller.close_all_streaming_servers()
                                        safe_log('info', "WebRTC streaming servers stopped directly")
                                    except Exception as srv_error:
                                        safe_log('error', f"Error stopping WebRTC streaming servers directly: {srv_error}")

                                # Access model to perform additional cleanup
                                if hasattr(controller, "ipfs_model") and hasattr(controller.ipfs_model, "close_all_webrtc_connections"):
                                    try:
                                        if not loop.is_closed():
                                            if asyncio.iscoroutinefunction(controller.ipfs_model.close_all_webrtc_connections):
                                                loop.run_until_complete(controller.ipfs_model.close_all_webrtc_connections())
                                            else:
                                                controller.ipfs_model.close_all_webrtc_connections()
                                        safe_log('info', "WebRTC connections closed directly")
                                    except Exception as conn_error:
                                        safe_log('error', f"Error closing WebRTC connections directly: {conn_error}")
                    else:
                        safe_log('error', f"{controller_name} controller does not have a shutdown method")

                except Exception as e:
                    safe_log('error', f"Error during {controller_name} controller shutdown: {e}")

        # Shutdown all controllers
        for controller_name, controller in self.controllers.items():
            if hasattr(controller, 'shutdown'):
                try:
                    safe_log('info', f"Shutting down {controller_name} controller...")
                    # Check if it's an async shutdown method that needs to be awaited
                    import inspect
                    if inspect.iscoroutinefunction(controller.shutdown):
                        # Use sync_shutdown for async controllers if available
                        if hasattr(controller, 'sync_shutdown'):
                            controller.sync_shutdown()
                        else:
                            # Create event loop and run the coroutine if no sync version
                            import asyncio
                            try:
                                loop = asyncio.get_event_loop()
                            except RuntimeError:
                                # Create a new event loop if no event loop is set
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                            loop.run_until_complete(controller.shutdown())
                    else:
                        # Regular synchronous shutdown
                        controller.shutdown()
                    safe_log('info', f"{controller_name} controller shutdown complete")
                except Exception as e:
                    safe_log('error', f"Error shutting down {controller_name} controller: {e}")

        # Shutdown storage models
        if hasattr(self, "storage_manager"):
            try:
                safe_log('info', "Shutting down storage models...")

                # Reset all storage models to save their state
                self.storage_manager.reset()
                
                # Reset storage bridge if it exists
                if hasattr(self, "storage_bridge"):
                    try:
                        safe_log('info', "Shutting down storage bridge...")
                        self.storage_bridge.reset()
                        safe_log('info', "Storage bridge shutdown complete")
                    except Exception as e:
                        safe_log('error', f"Error shutting down storage bridge: {e}")

                # Close any open connections
                for name, model in self.storage_manager.get_all_models().items():
                    if hasattr(model, "shutdown"):
                        try:
                            safe_log('info', f"Shutting down {name} storage model...")
                            model.shutdown()
                            safe_log('info', f"{name} storage model shutdown complete")
                        except Exception as e:
                            safe_log('error', f"Error shutting down {name} storage model: {e}")

                safe_log('info', "Storage models shutdown complete")
            except Exception as e:
                safe_log('error', f"Error shutting down storage manager: {e}")

        # Log final state
        safe_log('info', "MCP Server shutdown complete")

        # Close logger handlers if requested
        if close_logger:
            self._close_logger_handlers()

    def _is_interpreter_shutting_down(self):
        """Check if the Python interpreter is shutting down.

        During interpreter shutdown, some modules might be unloaded,
        making it unsafe to perform certain operations.
        """
        import sys
        import gc

        # Check if sys.modules is being cleared, a sign of interpreter shutdown
        if hasattr(sys, 'modules') and sys.modules is None:
            return True

        # Check if logging module is being unloaded
        if getattr(logging, '_handlerList', None) is None:
            return True

        # Check if we're in the final garbage collection phase
        if not hasattr(sys, 'argv'):
            return True

        # Check if any file handlers have closed file descriptors
        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler) or isinstance(handler, logging.StreamHandler):
                try:
                    # Check if the stream is closed
                    if handler.stream.closed:
                        return True
                except (AttributeError, ValueError):
                    # If we can't access the stream, it's likely being shut down
                    return True

        return False

    def __del__(self):
        """Ensure resources are cleaned up when the server is deleted."""
        try:
            # First check if we're in interpreter shutdown
            if self._is_interpreter_shutting_down():
                # Just close logger handlers without any other cleanup
                try:
                    self._close_logger_handlers()
                except Exception:
                    pass
                return

            # If not in interpreter shutdown, do a full shutdown
            # Use close_logger=True to prevent logging after shutdown
            self.shutdown(close_logger=True)
        except Exception:
            # Last resort - if anything fails during __del__, just pass
            # We can't safely log or handle errors during __del__
            pass

# Command-line interface setup (used when running as script and for testing)
import argparse
import uvicorn

# Create argument parser (available for tests)
parser = argparse.ArgumentParser(description="MCP Server for IPFS Kit")
parser.add_argument("--debug", action="store_true", help="Enable debug mode")
parser.add_argument("--isolation", action="store_true", help="Enable isolation mode")
parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)")
parser.add_argument("--port", type=int, default=8000, help="Port to run the server on")
parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
parser.add_argument("--persistence-path", help="Path for persistence files")
parser.add_argument("--api-prefix", default="/api/v0/mcp", help="Prefix for API endpoints")

def main(args=None):
    """
    Run the MCP server with the specified arguments.

    Args:
        args: Command-line arguments (for testing)
    """
    # Parse arguments
    if args is None:
        args = parser.parse_args()
    else:
        args = parser.parse_args(args)

    # Create FastAPI app
    app = FastAPI(
        title="IPFS MCP Server",
        description="Model-Controller-Persistence Server for IPFS Kit",
        version="0.1.0"
    )

    # Create MCP server
    mcp_server = MCPServer(
        debug_mode=args.debug,
        log_level=args.log_level,
        persistence_path=args.persistence_path,
        isolation_mode=args.isolation
    )

    # Register MCP server with app
    mcp_server.register_with_app(app, prefix=args.api_prefix)

    # Run the server
    print(f"Starting MCP server at http://{args.host}:{args.port} with API prefix {args.api_prefix}")
    print(f"Debug mode: {args.debug}, Isolation mode: {args.isolation}")
    uvicorn.run(app, host=args.host, port=args.port)

if __name__ == "__main__":
    """
    Run the MCP server as a standalone application.
    """
    main()
