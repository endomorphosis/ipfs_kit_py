"""
MCP Server implementation with AnyIO support that integrates with the existing IPFS Kit APIs.

This server provides:
- A structured approach to handling IPFS operations
- Debug capabilities for test-driven development
- Integration with the existing API infrastructure
- AnyIO support for better async compatibility
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

# Configure logger
logger = logging.getLogger(__name__)

# Import AnyIO for async compatibility
import anyio

# Import existing API components
from ipfs_kit_py.api import app as main_app
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Internal imports - use AnyIO versions where available
try:
    from ipfs_kit_py.mcp.models.ipfs_model_anyio import IPFSModelAnyIO as IPFSModel
except ImportError:
    from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
    logger.warning("Using synchronous IPFSModel instead of AnyIO version")

try:
    from ipfs_kit_py.mcp.controllers.ipfs_controller_anyio import IPFSControllerAnyIO as IPFSController
except ImportError:
    from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
    logger.warning("Using synchronous IPFSController instead of AnyIO version")

try:
    from ipfs_kit_py.mcp.controllers.cli_controller_anyio import CliControllerAnyIO as CliController
except ImportError:
    from ipfs_kit_py.mcp.controllers.cli_controller import CliController
    logger.warning("Using synchronous CliController instead of AnyIO version")

try:
    from ipfs_kit_py.mcp.controllers.credential_controller_anyio import CredentialControllerAnyIO as CredentialController
except ImportError:
    from ipfs_kit_py.mcp.controllers.credential_controller import CredentialController
    logger.warning("Using synchronous CredentialController instead of AnyIO version")

# Import credential manager
from ipfs_kit_py.credential_manager import CredentialManager

# Import storage manager with AnyIO support
from ipfs_kit_py.mcp.models.storage_manager_anyio import StorageManagerAnyIO as StorageManager

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
    
# Try to import AnyIO version of WebRTC controller first, then fall back to synchronous version
try:
    from ipfs_kit_py.mcp.controllers.webrtc_controller_anyio import WebRTCControllerAnyIO as WebRTCController
    HAS_WEBRTC_CONTROLLER = True
    logger.info("Using AnyIO-compatible WebRTC controller")
except ImportError:
    try:
        from ipfs_kit_py.mcp.controllers.webrtc_controller import WebRTCController
        HAS_WEBRTC_CONTROLLER = True
        logger.warning("Using synchronous WebRTC controller instead of AnyIO version")
    except ImportError:
        HAS_WEBRTC_CONTROLLER = False

# Try to import AnyIO version of LibP2P controller first, then fall back to synchronous version
try:
    from ipfs_kit_py.mcp.controllers.libp2p_controller_anyio import LibP2PControllerAnyIO as LibP2PController
    HAS_LIBP2P_CONTROLLER = True
    logger.info("Using AnyIO-compatible LibP2P controller")
except ImportError:
    try:
        from ipfs_kit_py.mcp.controllers.libp2p_controller import LibP2PController
        HAS_LIBP2P_CONTROLLER = True
        logger.warning("Using synchronous LibP2P controller instead of AnyIO version")
    except ImportError:
        HAS_LIBP2P_CONTROLLER = False
    
try:
    from ipfs_kit_py.mcp.controllers.peer_websocket_controller import PeerWebSocketController
    HAS_PEER_WEBSOCKET_CONTROLLER = True
except ImportError:
    HAS_PEER_WEBSOCKET_CONTROLLER = False
    
# Import storage controllers with AnyIO support
try:
    from ipfs_kit_py.mcp.controllers.storage.s3_controller_anyio import S3ControllerAnyIO as S3Controller
    HAS_S3_CONTROLLER = True
except ImportError:
    try:
        from ipfs_kit_py.mcp.controllers.storage.s3_controller import S3Controller
        HAS_S3_CONTROLLER = True
        logger.warning("Using synchronous S3Controller instead of AnyIO version")
    except ImportError:
        HAS_S3_CONTROLLER = False

try:
    from ipfs_kit_py.mcp.controllers.storage.huggingface_controller_anyio import HuggingFaceControllerAnyIO as HuggingFaceController
    HAS_HUGGINGFACE_CONTROLLER = True
except ImportError:
    try:
        from ipfs_kit_py.mcp.controllers.storage.huggingface_controller import HuggingFaceController
        HAS_HUGGINGFACE_CONTROLLER = True
        logger.warning("Using synchronous HuggingFaceController instead of AnyIO version")
    except ImportError:
        HAS_HUGGINGFACE_CONTROLLER = False

try:
    from ipfs_kit_py.mcp.controllers.storage.storacha_controller_anyio import StorachaControllerAnyIO as StorachaController
    HAS_STORACHA_CONTROLLER = True
except ImportError:
    try:
        from ipfs_kit_py.mcp.controllers.storage.storacha_controller import StorachaController
        HAS_STORACHA_CONTROLLER = True
        logger.warning("Using synchronous StorachaController instead of AnyIO version")
    except ImportError:
        HAS_STORACHA_CONTROLLER = False

try:
    from ipfs_kit_py.mcp.controllers.storage.filecoin_controller_anyio import FilecoinControllerAnyIO as FilecoinController
    HAS_FILECOIN_CONTROLLER = True
except ImportError:
    try:
        from ipfs_kit_py.mcp.controllers.storage.filecoin_controller import FilecoinController
        HAS_FILECOIN_CONTROLLER = True
        logger.warning("Using synchronous FilecoinController instead of AnyIO version")
    except ImportError:
        HAS_FILECOIN_CONTROLLER = False

try:
    from ipfs_kit_py.mcp.controllers.storage.lassie_controller_anyio import LassieControllerAnyIO as LassieController
    HAS_LASSIE_CONTROLLER = True
except ImportError:
    try:
        from ipfs_kit_py.mcp.controllers.storage.lassie_controller import LassieController
        HAS_LASSIE_CONTROLLER = True
        logger.warning("Using synchronous LassieController instead of AnyIO version")
    except ImportError:
        HAS_LASSIE_CONTROLLER = False
    
from ipfs_kit_py.mcp.persistence.cache_manager import MCPCacheManager

# Logger already configured at the top of the file

class MCPServer:
    """
    Model-Controller-Persistence Server for IPFS Kit with AnyIO support.
    
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
        try:
            os.makedirs(self.persistence_path, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create persistence directory at {self.persistence_path}: {e}")
            # Use a temporary directory as fallback
            import tempfile
            self.persistence_path = tempfile.mkdtemp(prefix="mcp_server_anyio_")
            logger.warning(f"Using temporary directory for persistence: {self.persistence_path}")
            
        # Initialize result tracking for component initialization
        self.initialization_results = {
            "success": True,
            "errors": [],
            "warnings": []
        }

        # Initialize core components
        cache_config = getattr(self, 'config', {}).get("cache", {})
        
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
            kit_options = {}
            if self.isolation_mode:
                # Use isolated IPFS path for testing
                kit_options["metadata"] = {
                    "ipfs_path": os.path.join(self.persistence_path, "ipfs"),
                    "role": "leecher",  # Use lightweight role for testing
                    "test_mode": True
                }
            
            # Enable automatic daemon management
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
                
            # Initialize Storage Bridge Model if available
            try:
                if hasattr(self.storage_manager, "storage_bridge"):
                    # Add storage bridge to the models dictionary
                    self.models["storage_bridge"] = self.storage_manager.storage_bridge
                    logger.info("Storage Bridge Model added")
            except Exception as e:
                logger.warning(f"Failed to add Storage Bridge: {e}")
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
        # Core controllers (IPFS, CLI, Credentials)
        try:
            self.controllers["ipfs"] = IPFSController(self.models["ipfs"])
            logger.info("IPFS Controller added")
        except Exception as e:
            logger.error(f"Failed to initialize IPFS controller: {e}")
            self.initialization_results["errors"].append(f"IPFS controller initialization failed: {e}")
            self.initialization_results["success"] = False
        
        try:
            self.controllers["cli"] = CliController(self.models["ipfs"])
            logger.info("CLI Controller added")
        except Exception as e:
            logger.error(f"Failed to initialize CLI controller: {e}")
            self.initialization_results["errors"].append(f"CLI controller initialization failed: {e}")
            self.initialization_results["success"] = False
        
        try:
            self.controllers["credentials"] = CredentialController(self.credential_manager)
            logger.info("Credentials Controller added")
        except Exception as e:
            logger.error(f"Failed to initialize credentials controller: {e}")
            self.initialization_results["errors"].append(f"Credentials controller initialization failed: {e}")
            self.initialization_results["success"] = False
        
    def _init_storage_controllers(self):
        """Initialize storage controllers with proper error handling."""
        # Initialize the StorageManagerController first (handles /storage/status endpoint)
        try:
            # Import AnyIO version if available, otherwise use sync version
            try:
                from ipfs_kit_py.mcp.controllers.storage_manager_controller_anyio import StorageManagerControllerAnyIO as StorageManagerController
                logger.info("Using AnyIO-compatible StorageManager controller")
            except ImportError:
                try:
                    from ipfs_kit_py.mcp.controllers.storage_manager_controller import StorageManagerController
                    logger.warning("Using synchronous StorageManagerController instead of AnyIO version")
                except ImportError:
                    logger.error("StorageManagerController not found - storage status endpoint will not be available")
                    StorageManagerController = None

            # Initialize and add the controller if available
            if StorageManagerController is not None:
                self.controllers["storage_manager"] = StorageManagerController(self.storage_manager)
                logger.info("Storage Manager Controller added")
        except Exception as e:
            logger.error(f"Failed to initialize Storage Manager controller: {e}")
            self.initialization_results["errors"].append(f"Storage Manager controller initialization failed: {e}")
            self.initialization_results["success"] = False
        
        # Storage controllers
        storage_controllers = [
            ("storage_s3", HAS_S3_CONTROLLER, lambda: S3Controller(self.models["storage_s3"])),
            ("storage_huggingface", HAS_HUGGINGFACE_CONTROLLER, lambda: HuggingFaceController(self.models["storage_huggingface"])),
            ("storage_storacha", HAS_STORACHA_CONTROLLER, lambda: StorachaController(self.models["storage_storacha"])),
            ("storage_filecoin", HAS_FILECOIN_CONTROLLER, lambda: FilecoinController(self.models["storage_filecoin"])),
            ("storage_lassie", HAS_LASSIE_CONTROLLER, lambda: LassieController(self.models["storage_lassie"]))
        ]
        
        for controller_name, has_controller, constructor in storage_controllers:
            if has_controller and controller_name.split('_')[1] in self.models:
                try:
                    self.controllers[controller_name] = constructor()
                    logger.info(f"{controller_name.split('_')[1].capitalize()} Controller added")
                except Exception as e:
                    logger.warning(f"Failed to initialize {controller_name} controller: {e}")
                    self.initialization_results["warnings"].append(f"{controller_name} controller initialization failed: {e}")
    
    def _init_optional_controllers(self):
        """Initialize optional controllers with proper error handling."""
        # Optional controllers that use the IPFS model
        optional_controllers = [
            ("distributed", HAS_DISTRIBUTED_CONTROLLER, lambda: DistributedController(self.models["ipfs"])),
            ("fs_journal", HAS_FS_JOURNAL_CONTROLLER, lambda: FsJournalController(self.models["ipfs"])),
            ("peer_websocket", HAS_PEER_WEBSOCKET_CONTROLLER, lambda: PeerWebSocketController(self.models["ipfs"])),
            ("webrtc", HAS_WEBRTC_CONTROLLER, lambda: WebRTCController(self.models["ipfs"]))
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
        
        # LibP2P controller requires special handling for model initialization
        if HAS_LIBP2P_CONTROLLER:
            try:
                # Initialize LibP2P model if it doesn't exist
                if "libp2p" not in self.models and hasattr(self.models["ipfs"], "get_libp2p_model"):
                    try:
                        # Try to get the LibP2P model from the IPFS model if it supports it
                        libp2p_model = self.models["ipfs"].get_libp2p_model()
                        if libp2p_model:
                            self.models["libp2p"] = libp2p_model
                            logger.info("LibP2P Model initialized from IPFS model")
                    except Exception as e:
                        logger.warning(f"Error initializing LibP2P model: {e}")
                        self.initialization_results["warnings"].append(f"LibP2P model initialization failed: {e}")
                
                # Initialize LibP2P controller if the model is available
                if "libp2p" in self.models:
                    self.controllers["libp2p"] = LibP2PController(self.models["libp2p"])
                    logger.info("LibP2P Controller added")
                else:
                    logger.warning("LibP2P Controller not added: LibP2P model not available")
                    self.initialization_results["warnings"].append("LibP2P Controller not added: model not available")
            except Exception as e:
                logger.warning(f"Failed to initialize LibP2P controller: {e}")
                self.initialization_results["warnings"].append(f"LibP2P controller initialization failed: {e}")
                # Optional controller, doesn't affect overall success
    
    def _create_router(self) -> APIRouter:
        """Create FastAPI router for MCP endpoints."""
        router = APIRouter(prefix="", tags=["mcp"])
        
        # Register core endpoints
        router.add_api_route("/health", self.health_check, methods=["GET"])
        router.add_api_route("/debug", self.get_debug_state, methods=["GET"])
        router.add_api_route("/operations", self.get_operation_log, methods=["GET"])
        
        # Daemon management endpoints (admin only)
        router.add_api_route("/daemon/start/{daemon_type}", self.start_daemon, methods=["POST"])
        router.add_api_route("/daemon/stop/{daemon_type}", self.stop_daemon, methods=["POST"])
        router.add_api_route("/daemon/status", self.get_daemon_status, methods=["GET"])
        router.add_api_route("/daemon/monitor/start", self.start_daemon_monitor, methods=["POST"])
        router.add_api_route("/daemon/monitor/stop", self.stop_daemon_monitor, methods=["POST"])
        
        # Register controller endpoints
        self.controllers["ipfs"].register_routes(router)
        self.controllers["cli"].register_routes(router)
        self.controllers["credentials"].register_routes(router)
        
        # Register optional controllers
        if "distributed" in self.controllers:
            self.controllers["distributed"].register_routes(router)
            
        if "webrtc" in self.controllers:
            self.controllers["webrtc"].register_routes(router)
            
        if "libp2p" in self.controllers:
            self.controllers["libp2p"].register_routes(router)
            
        if "peer_websocket" in self.controllers:
            self.controllers["peer_websocket"].register_routes(router)
            
        if "fs_journal" in self.controllers:
            self.controllers["fs_journal"].register_routes(router)
            
        # Register storage controllers
        if "storage_s3" in self.controllers:
            self.controllers["storage_s3"].register_routes(router)
            
        if "storage_huggingface" in self.controllers:
            self.controllers["storage_huggingface"].register_routes(router)
            
        if "storage_storacha" in self.controllers:
            self.controllers["storage_storacha"].register_routes(router)
            
        if "storage_filecoin" in self.controllers:
            self.controllers["storage_filecoin"].register_routes(router)
            
        if "storage_lassie" in self.controllers:
            self.controllers["storage_lassie"].register_routes(router)
        
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
        
    def register_controllers(self) -> APIRouter:
        """Register all controllers with a router.
        
        This method is primarily for testing purposes and similar to _create_router,
        but it assumes the router and controllers are already set up.
        
        Returns:
            The router with controllers registered
        """
        if not hasattr(self, 'router') or not self.router:
            self.router = APIRouter(prefix="", tags=["mcp"])
            
        # Register core endpoints
        self.router.add_api_route("/health", self.health_check, methods=["GET"])
        
        # Always add debug endpoints - they'll return error responses when debug mode is disabled
        self.router.add_api_route("/debug", self.get_debug_state, methods=["GET"])
        self.router.add_api_route("/operations", self.get_operation_log, methods=["GET"])

        # Daemon management endpoints (admin only)
        self.router.add_api_route("/daemon/start/{daemon_type}", self.start_daemon, methods=["POST"])
        self.router.add_api_route("/daemon/stop/{daemon_type}", self.stop_daemon, methods=["POST"])
        self.router.add_api_route("/daemon/status", self.get_daemon_status, methods=["GET"])
        self.router.add_api_route("/daemon/monitor/start", self.start_daemon_monitor, methods=["POST"])
        self.router.add_api_route("/daemon/monitor/stop", self.stop_daemon_monitor, methods=["POST"])

        # Register controller endpoints in a specific order to ensure dependencies are met
        # First register IPFS controller
        if "ipfs" in self.controllers and hasattr(self.controllers["ipfs"], 'register_routes'):
            self.controllers["ipfs"].register_routes(self.router)
            logger.info("Registered IPFS controller routes")
        
        # Next register CLI and Credentials controllers
        if "cli" in self.controllers and hasattr(self.controllers["cli"], 'register_routes'):
            self.controllers["cli"].register_routes(self.router)
            logger.info("Registered CLI controller routes")
            
        if "credentials" in self.controllers and hasattr(self.controllers["credentials"], 'register_routes'):
            self.controllers["credentials"].register_routes(self.router)
            logger.info("Registered Credentials controller routes")
            
        # Explicitly register storage manager controller
        if "storage_manager" in self.controllers and hasattr(self.controllers["storage_manager"], 'register_routes'):
            try:
                logger.info("Registering Storage Manager controller routes...")
                self.controllers["storage_manager"].register_routes(self.router)
                logger.info("Successfully registered Storage Manager controller routes")
                
                # Check if the routes were actually registered
                routes_added = False
                for route in self.router.routes:
                    if '/storage/status' in route.path:
                        routes_added = True
                        logger.info(f"Storage status route found: {route.path}")
                        break
                
                if not routes_added:
                    logger.error("Storage Manager routes were not added correctly!")
                    
                    # Try to add the route directly as a fallback
                    try:
                        storage_controller = self.controllers["storage_manager"]
                        self.router.add_api_route(
                            "/storage/status",
                            storage_controller.handle_status_request_async,
                            methods=["GET"],
                            summary="Storage Status",
                            description="Get status of all storage backends"
                        )
                        logger.info("Added /storage/status route directly as a fallback")
                    except Exception as e:
                        logger.error(f"Error adding fallback route: {e}")
                        
                    # If that fails, add a fallback route that returns a fixed response
                    if not routes_added:
                        try:
                            async def fallback_storage_status():
                                """Emergency fallback for storage status endpoint."""
                                start_time = time.time()
                                return {
                                    "success": True,
                                    "operation_id": f"storage_status_{int(start_time * 1000)}",
                                    "backends": {},
                                    "available_count": 0,
                                    "total_count": 0,
                                    "duration_ms": (time.time() - start_time) * 1000,
                                    "fallback": True
                                }
                            
                            self.router.add_api_route(
                                "/storage/status",
                                fallback_storage_status,
                                methods=["GET"],
                                summary="Storage Status (Fallback)",
                                description="Fallback storage status endpoint"
                            )
                            logger.info("Added emergency fallback /storage/status route")
                        except Exception as e:
                            logger.error(f"Error adding emergency fallback route: {e}")
            except Exception as e:
                logger.error(f"Error registering Storage Manager controller routes: {e}")
                
                # If registration failed completely, add a fallback route that returns a fixed response
                try:
                    async def fallback_storage_status():
                        """Emergency fallback for storage status endpoint."""
                        start_time = time.time()
                        return {
                            "success": True,
                            "operation_id": f"storage_status_{int(start_time * 1000)}",
                            "backends": {},
                            "available_count": 0,
                            "total_count": 0,
                            "duration_ms": (time.time() - start_time) * 1000,
                            "fallback": True
                        }
                    
                    self.router.add_api_route(
                        "/storage/status",
                        fallback_storage_status,
                        methods=["GET"],
                        summary="Storage Status (Fallback)",
                        description="Fallback storage status endpoint"
                    )
                    logger.info("Added emergency fallback /storage/status route")
                except Exception as e:
                    logger.error(f"Error adding emergency fallback route: {e}")
        else:
            logger.error("Storage Manager controller not found in controllers or doesn't have register_routes method")
            
            # If controller not found, add a fallback route that returns a fixed response
            try:
                async def fallback_storage_status():
                    """Emergency fallback for storage status endpoint."""
                    start_time = time.time()
                    return {
                        "success": True,
                        "operation_id": f"storage_status_{int(start_time * 1000)}",
                        "backends": {},
                        "available_count": 0,
                        "total_count": 0,
                        "duration_ms": (time.time() - start_time) * 1000,
                        "fallback": True
                    }
                
                self.router.add_api_route(
                    "/storage/status",
                    fallback_storage_status,
                    methods=["GET"],
                    summary="Storage Status (Fallback)",
                    description="Fallback storage status endpoint"
                )
                logger.info("Added emergency fallback /storage/status route (no controller)")
            except Exception as e:
                logger.error(f"Error adding emergency fallback route: {e}")
            
        # Now register all other controllers
        for name, controller in self.controllers.items():
            if name not in ["ipfs", "cli", "credentials", "storage_manager"] and hasattr(controller, 'register_routes'):
                try:
                    controller.register_routes(self.router)
                    logger.info(f"Registered {name} controller routes")
                except Exception as e:
                    logger.error(f"Error registering {name} controller routes: {e}")
                
        # Log all registered routes for debugging
        logger.info("All registered routes:")
        for route in self.router.routes:
            if hasattr(route, 'methods'):
                logger.info(f"  {route.path} - {route.methods}")
            else:
                # Handle WebSocket routes or other route types that don't have methods
                route_type = route.__class__.__name__
                logger.info(f"  {route.path} - [{route_type}]")
                
        return self.router
    
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
        """
        Health check endpoint.
        
        Returns information about the MCP server status, including daemon status
        and automatic daemon management configuration.
        """
        # Build basic health information
        health_info = {
            "success": True,
            "status": "ok",
            "timestamp": time.time(),
            "server_id": self.instance_id,
            "debug_mode": self.debug_mode,
            "isolation_mode": self.isolation_mode
        }
        
        # Add daemon status information if available
        try:
            # Check if the ipfs_kit has the necessary daemon status methods
            if hasattr(self.ipfs_kit, 'check_daemon_status'):
                daemon_status = self.ipfs_kit.check_daemon_status()
                daemons = daemon_status.get("daemons", {})
                
                # Check IPFS daemon status
                if "ipfs" in daemons:
                    health_info["ipfs_daemon_running"] = daemons["ipfs"].get("running", False)
                
                # Check cluster daemon status
                if "ipfs_cluster_service" in daemons:
                    health_info["ipfs_cluster_daemon_running"] = daemons["ipfs_cluster_service"].get("running", False)
            
            # Add auto-retry configuration status
            if hasattr(self.ipfs_kit, 'auto_start_daemons'):
                health_info["auto_start_daemons_enabled"] = self.ipfs_kit.auto_start_daemons
            
            # Add daemon health monitor status
            if hasattr(self.ipfs_kit, 'is_daemon_health_monitor_running'):
                health_info["daemon_health_monitor_running"] = self.ipfs_kit.is_daemon_health_monitor_running()
        except Exception as e:
            # Don't fail the health check if daemon status check fails
            health_info["daemon_status_check_error"] = str(e)
        
        # Add information about controllers
        # Using simplified format to match test expectations - just boolean values
        controllers_info = {}
        for controller_name, controller in self.controllers.items():
            # Set controller availability to True by default
            controllers_info[controller_name] = True
            
            # If the controller has get_health method, try to use it
            if hasattr(controller, 'get_health') and callable(controller.get_health):
                try:
                    controller_health = await controller.get_health()
                    # If get_health returns a dictionary with available key, use that value
                    if isinstance(controller_health, dict) and "available" in controller_health:
                        controllers_info[controller_name] = controller_health["available"]
                except Exception as e:
                    # If health check fails, set availability to False
                    controllers_info[controller_name] = False
        
        # Add controllers to health info
        health_info["controllers"] = controllers_info
        
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
        
        persistence_info = {
            "cache_info": self.cache_manager.get_cache_info()
        }
        
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
        
        # Check if ipfs_kit has the required method
        if not hasattr(self.ipfs_kit, '_start_daemon'):
            return {
                "success": False,
                "error": "This version of ipfs_kit does not support manual daemon control",
                "error_type": "UnsupportedOperation"
            }
        
        # Try to start the daemon
        try:
            # Note: Using internal _start_daemon method since it's what the auto-retry functionality uses
            result = self.ipfs_kit._start_daemon(daemon_type)
            
            # Log the action
            if result.get("success", False):
                logger.info(f"Manually started {daemon_type} daemon")
            else:
                logger.warning(f"Failed to manually start {daemon_type} daemon: {result.get('error', 'Unknown error')}")
            
            return result
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
        
        # Check if ipfs_kit has the required method
        if not hasattr(self.ipfs_kit, '_stop_daemon'):
            return {
                "success": False,
                "error": "This version of ipfs_kit does not support manual daemon control",
                "error_type": "UnsupportedOperation"
            }
        
        # Try to stop the daemon
        try:
            # Note: Using internal _stop_daemon method as a direct way to stop the daemon
            result = self.ipfs_kit._stop_daemon(daemon_type)
            
            # Log the action
            if result.get("success", False):
                logger.info(f"Manually stopped {daemon_type} daemon")
            else:
                logger.warning(f"Failed to manually stop {daemon_type} daemon: {result.get('error', 'Unknown error')}")
            
            return result
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
        if not hasattr(self.ipfs_kit, 'check_daemon_status'):
            return {
                "success": False,
                "error": "This version of ipfs_kit does not support daemon status checking",
                "error_type": "UnsupportedOperation"
            }
        
        # Check if method takes daemon_type parameter
        import inspect
        sig = inspect.signature(self.ipfs_kit.check_daemon_status)
        
        # Get status for each daemon type
        if len(sig.parameters) > 1:
            # Method takes daemon_type parameter - call for each type
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
            # Method doesn't take daemon_type parameter - call once
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
        
        # Get monitor status
        monitor_running = False
        if hasattr(self.ipfs_kit, 'is_daemon_health_monitor_running'):
            monitor_running = self.ipfs_kit.is_daemon_health_monitor_running()
        
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
    
    async def shutdown(self):
        """Shutdown the server and clean up resources."""
        logger.info("MCP Server shutting down")
        
        # Stop daemon health monitor first to prevent daemon restarts during shutdown
        if hasattr(self.ipfs_kit, 'stop_daemon_health_monitor'):
            try:
                logger.info("Stopping daemon health monitor...")
                self.ipfs_kit.stop_daemon_health_monitor()
                logger.info("Daemon health monitor stopped")
            except Exception as e:
                logger.error(f"Error stopping daemon health monitor: {e}")
        
        # Stop cache manager cleanup thread
        if hasattr(self.cache_manager, 'stop_cleanup_thread'):
            try:
                logger.info("Stopping cache cleanup thread...")
                self.cache_manager.stop_cleanup_thread()
                logger.info("Cache cleanup thread stopped")
            except Exception as e:
                logger.error(f"Error stopping cache cleanup thread: {e}")
                
        # Save cache metadata
        try:
            logger.info("Saving cache metadata...")
            self.cache_manager._save_metadata()
            logger.info("Cache metadata saved")
        except Exception as e:
            logger.error(f"Error saving cache metadata during shutdown: {e}")
        
        # Make sure any in-memory credential changes are persisted
        if hasattr(self, 'credential_manager'):
            try:
                logger.info("Ensuring credential persistence...")
                # The credential manager automatically persists changes, but we can
                # explicitly save by re-adding the credentials that are in cache
                for cred_key, cred_record in self.credential_manager.credential_cache.items():
                    if "_" in cred_key:
                        service, name = cred_key.split("_", 1)
                        self.credential_manager.add_credential(
                            service, name, cred_record["credentials"]
                        )
                logger.info("Credentials persisted")
            except Exception as e:
                logger.error(f"Error persisting credentials during shutdown: {e}")
            
        # Special handling for peer WebSocket controller to ensure async resources are cleaned up
        if "peer_websocket" in self.controllers:
            try:
                peer_ws_controller = self.controllers["peer_websocket"]
                
                # Use the controller's shutdown method
                if hasattr(peer_ws_controller, "shutdown"):
                    logger.info("Shutting down peer WebSocket controller...")
                    
                    # Create anyio scope for async shutdown
                    try:
                        # Run the shutdown method with anyio
                        await anyio.to_thread.run_sync(peer_ws_controller.shutdown)
                        
                        logger.info("Peer WebSocket controller shutdown complete")
                    except Exception as e:
                        logger.error(f"Error in peer WebSocket controller shutdown: {e}")
                        
                        # Fallback to direct cleanup if shutdown method failed
                        if hasattr(peer_ws_controller, "peer_websocket_server") and peer_ws_controller.peer_websocket_server:
                            try:
                                # Check if it's a callable method or an attribute
                                if callable(peer_ws_controller.peer_websocket_server.stop):
                                    await anyio.to_thread.run_sync(peer_ws_controller.peer_websocket_server.stop)
                                peer_ws_controller.peer_websocket_server = None
                                logger.info("Peer WebSocket server stopped directly")
                            except Exception as server_error:
                                logger.error(f"Error stopping peer WebSocket server directly: {server_error}")
                                
                        if hasattr(peer_ws_controller, "peer_websocket_client") and peer_ws_controller.peer_websocket_client:
                            try:
                                # Check if it's a callable method or an attribute
                                if callable(peer_ws_controller.peer_websocket_client.stop):
                                    await anyio.to_thread.run_sync(peer_ws_controller.peer_websocket_client.stop)
                                peer_ws_controller.peer_websocket_client = None
                                logger.info("Peer WebSocket client stopped directly")
                            except Exception as client_error:
                                logger.error(f"Error stopping peer WebSocket client directly: {client_error}")
                else:
                    logger.error("Peer WebSocket controller does not have a shutdown method")
            
            except Exception as e:
                logger.error(f"Error during peer WebSocket shutdown: {e}")
                
        # Special handling for LibP2P controller to ensure resources are cleaned up
        if "libp2p" in self.controllers:
            try:
                libp2p_controller = self.controllers["libp2p"]
                
                # Use the controller's shutdown method if available
                if hasattr(libp2p_controller, "shutdown"):
                    logger.info("Shutting down LibP2P controller...")
                    
                    try:
                        # Run the shutdown method with anyio
                        await anyio.to_thread.run_sync(libp2p_controller.shutdown)
                        
                        logger.info("LibP2P controller shutdown complete")
                    except Exception as e:
                        logger.error(f"Error in LibP2P controller shutdown: {e}")
                        
                        # Try to stop the model directly if controller shutdown failed
                        if hasattr(self.models, "libp2p") and hasattr(self.models["libp2p"], "stop"):
                            try:
                                await anyio.to_thread.run_sync(self.models["libp2p"].stop)
                                logger.info("LibP2P model stopped directly")
                            except Exception as model_error:
                                logger.error(f"Error stopping LibP2P model directly: {model_error}")
            
            except Exception as e:
                logger.error(f"Error during LibP2P shutdown: {e}")
            
        # Shutdown all controllers
        for controller_name, controller in self.controllers.items():
            if hasattr(controller, 'shutdown'):
                try:
                    logger.info(f"Shutting down {controller_name} controller...")
                    
                    # Check if shutdown is an async method or not
                    if hasattr(controller.shutdown, '__await__'):
                        # This is an async method, call it directly
                        await controller.shutdown()
                    else:
                        # For synchronous methods, run them in a thread using anyio
                        await anyio.to_thread.run_sync(controller.shutdown)
                        
                    logger.info(f"{controller_name} controller shutdown complete")
                except Exception as e:
                    logger.error(f"Error shutting down {controller_name} controller: {e}")
            
        # Log final state
        logger.info("MCP Server shutdown complete")
    
    # Make shutdown available as a synchronous method as well for backward compatibility
    def sync_shutdown(self):
        """Synchronous version of shutdown for backward compatibility."""
        # Create an anyio task group to run the async shutdown
        async def run_shutdown():
            await self.shutdown()
            
        # Run the async shutdown in a new event loop
        anyio.run(run_shutdown)
        
    def __del__(self):
        """Ensure resources are cleaned up when the server is deleted."""
        # Use anyio to run the async shutdown
        try:
            anyio.run(self.shutdown)
        except Exception:
            # If anyio fails, try the synchronous version
            try:
                self.sync_shutdown()
            except Exception as e:
                # Last resort, just log the error
                logger.error(f"Error during server shutdown in __del__: {e}")

# Command-line interface setup (used when running as script and for testing)
import argparse
import uvicorn

# Create argument parser (available for tests)
parser = argparse.ArgumentParser(description="MCP Server for IPFS Kit with AnyIO support")
parser.add_argument("--debug", action="store_true", help="Enable debug mode")
parser.add_argument("--isolation", action="store_true", help="Enable isolation mode")
parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)")
parser.add_argument("--port", type=int, default=8000, help="Port to run the server on")
parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
parser.add_argument("--persistence-path", help="Path for persistence files")
parser.add_argument("--api-prefix", default="/api/v0/mcp", help="Prefix for API endpoints")
parser.add_argument("--backend", default="asyncio", choices=["asyncio", "trio"], help="AnyIO backend to use")

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
        description="Model-Controller-Persistence Server for IPFS Kit with AnyIO support",
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
    print(f"Debug mode: {args.debug}, Isolation mode: {args.isolation}, AnyIO backend: {args.backend}")
    
    # Configure Uvicorn
    config = uvicorn.Config(
        app=app, 
        host=args.host, 
        port=args.port, 
        log_level=args.log_level.lower()
    )
    server = uvicorn.Server(config)
    
    # Set environment variable for AnyIO backend
    import os
    os.environ["ANYIO_BACKEND"] = args.backend
    
    # When using Trio, we don't use the AnyIO approach directly
    # because Uvicorn has better support for asyncio
    if args.backend == "trio":
        print(f"IMPORTANT: Running server with asyncio backend instead of trio for better compatibility.")
        print(f"Trio support will be emulated by using anyio.")
        anyio.run(server.serve, backend="asyncio")
    else:
        # For asyncio, we can use the standard approach
        anyio.run(server.serve, backend=args.backend)

if __name__ == "__main__":
    """
    Run the MCP server as a standalone application.
    """
    main()