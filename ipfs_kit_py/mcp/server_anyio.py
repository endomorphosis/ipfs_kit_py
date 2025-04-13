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

# Import AsyncEventLoopHandler for task handling during shutdown
from .models.ipfs_model import AsyncEventLoopHandler

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
    
    # Import essential modules at the class level to ensure availability during shutdown
    import os
    import json
    import logging
    
    # Cache for backend detection to improve performance
    _backend_cache = None
    
    @staticmethod
    def get_backend():
        """
        Determine the current async backend with caching to improve performance.
        
        Returns:
            String name of the backend ("asyncio", "trio", etc.) or None if not in async context.
        """
        # Use cached result if available - static method so we use class variable
        if MCPServer._backend_cache is not None:
            return MCPServer._backend_cache
            
        try:
            import sniffio
            backend = sniffio.current_async_library()
            # Cache the result to avoid repeated lookups
            MCPServer._backend_cache = backend
            return backend
        except ImportError:
            logger.debug("sniffio not available, can't detect async backend")
            # Cache None result
            MCPServer._backend_cache = None
            return None
        except Exception as e:
            # Handle AsyncLibraryNotFoundError which will happen outside of async context
            if type(e).__name__ == "AsyncLibraryNotFoundError":
                # Cache None result
                MCPServer._backend_cache = None
                return None
            # For other exceptions, log and return None but don't cache
            logger.debug(f"Error detecting async backend: {e}")
            return None
    
    def __init__(self, 
                debug_mode: bool = False, 
                log_level: str = "INFO",
                persistence_path: str = None,
                isolation_mode: bool = False,
                skip_daemon: bool = False,
                config: Dict[str, Any] = None):
        """
        Initialize the MCP Server.
        
        Args:
            debug_mode: Enable detailed debug logging and debug endpoints
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            persistence_path: Path for MCP server persistence files
            isolation_mode: Run in isolated mode without affecting host system
            skip_daemon: If True, don't auto-start IPFS daemon
            config: Optional configuration dictionary for components
        """
        self.debug_mode = debug_mode
        self.isolation_mode = isolation_mode
        self.persistence_path = persistence_path or os.path.expanduser("~/.ipfs_kit/mcp")
        self.instance_id = str(uuid.uuid4())
        self.config = config or {}
        self.skip_daemon = skip_daemon
        
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
        if not hasattr(self, 'config'):
            self.config = {}
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
            kit_options = {}
            if self.isolation_mode:
                # Use isolated IPFS path for testing
                isolated_path = os.path.join(self.persistence_path, "ipfs")
                kit_options["metadata"] = {
                    "ipfs_path": isolated_path,
                    "role": "leecher",  # Use lightweight role for testing
                    "test_mode": True
                }
                
                # Ensure repository is initialized before trying to start daemon
                if not os.path.exists(os.path.join(isolated_path, "config")):
                    logger.info(f"Initializing isolated IPFS repository at {isolated_path}")
                    try:
                        os.makedirs(isolated_path, exist_ok=True)
                        import subprocess
                        # Initialize with minimal profile for faster startup
                        init_result = subprocess.run(
                            ["ipfs", "init", "--profile=test"],
                            env={"IPFS_PATH": isolated_path, "PATH": os.environ["PATH"]},
                            capture_output=True,
                            text=True
                        )
                        if init_result.returncode != 0:
                            logger.warning(f"Failed to initialize repository: {init_result.stderr}")
                    except Exception as e:
                        logger.warning(f"Error initializing repository: {e}")
            
            # Initialize IPFS repo lock handling
            if self.isolation_mode:
                isolated_path = kit_options.get("metadata", {}).get("ipfs_path")
                if isolated_path:
                    # Check for and handle stale lock files
                    lock_path = os.path.join(isolated_path, "repo.lock")
                    if os.path.exists(lock_path):
                        logger.warning(f"Found existing lock file at {lock_path}, attempting to clean up")
                        try:
                            # Read lock file to get PID
                            with open(lock_path, 'r') as f:
                                try:
                                    pid = int(f.read().strip())
                                    logger.info(f"Lock file contains PID: {pid}")
                                    
                                    # Check if process is actually running
                                    try:
                                        os.kill(pid, 0)  # This will raise OSError if process doesn't exist
                                        logger.warning(f"Process with PID {pid} is still running")
                                    except OSError:
                                        # Process doesn't exist, lock is stale and can be removed
                                        logger.info(f"Process with PID {pid} is not running, removing stale lock file")
                                        os.remove(lock_path)
                                except (ValueError, IOError) as e:
                                    # Invalid content in lock file
                                    logger.warning(f"Invalid lock file content: {e}")
                                    os.remove(lock_path)
                        except Exception as e:
                            logger.error(f"Error handling lock file: {e}")
            
            # First attempt: Based on skip_daemon setting
            try:
                # Determine if we should auto-start the daemon based on skip_daemon
                auto_start = not self.skip_daemon
                
                if auto_start:
                    logger.info("First attempt: Initializing IPFS kit without daemon auto-start")
                    self.ipfs_kit = ipfs_kit(
                        metadata=kit_options.get("metadata"),
                        auto_start_daemons=False  # Start manually for better control
                    )
                    logger.info("IPFS kit initialized successfully without auto-start")
                    
                    # Now explicitly start the daemon with force=True to handle locks
                    if hasattr(self.ipfs_kit, 'ipfs') and hasattr(self.ipfs_kit.ipfs, 'daemon_start'):
                        logger.info("Explicitly starting IPFS daemon with force=True")
                        start_result = self.ipfs_kit.ipfs.daemon_start(force=True)
                        
                        if start_result.get("success", False):
                            logger.info("IPFS daemon started successfully with explicit call")
                        else:
                            logger.warning(f"Failed to start IPFS daemon explicitly: {start_result.get('error', 'Unknown error')}")
                    else:
                        logger.warning("IPFS kit instance doesn't have expected daemon_start method")
                else:
                    # Skip daemon based on command-line option
                    logger.info("Initializing IPFS kit with daemon auto-start disabled (--skip-daemon)")
                    self.ipfs_kit = ipfs_kit(
                        metadata=kit_options.get("metadata"),
                        auto_start_daemons=False  # Respect --skip-daemon option
                    )
                    logger.info("IPFS kit initialized successfully with daemon auto-start disabled")
            
            except Exception as e:
                logger.error(f"Error initializing IPFS kit with first approach: {e}")
                
                # Second attempt: Try with automatic daemon management if not skipped
                try:
                    auto_start = not self.skip_daemon
                    logger.info(f"Second attempt: Initializing IPFS kit with auto_start_daemons={auto_start}")
                    self.ipfs_kit = ipfs_kit(
                        metadata=kit_options.get("metadata"),
                        auto_start_daemons=auto_start  # Use skip_daemon parameter to determine auto-start
                    )
                    
                    # Check if daemon started successfully if auto-start is enabled
                    if auto_start:
                        daemon_status = self.ipfs_kit.check_daemon_status()
                        if not daemon_status.get("success", False) or not daemon_status.get("daemons", {}).get("ipfs", {}).get("running", False):
                            logger.warning("IPFS daemon failed to start automatically, retrying with auto_start_daemons=False")
                            # Retry without daemon auto-start as last resort
                            self.ipfs_kit = ipfs_kit(
                                metadata=kit_options.get("metadata"),
                                auto_start_daemons=False  # Skip daemon startup
                            )
                            logger.info("IPFS kit initialized without daemon auto-start")
                except Exception as inner_e:
                    logger.error(f"Error initializing IPFS kit with auto-start: {inner_e}")
                    logger.warning("Final fallback: IPFS kit without daemon auto-start")
                    # Final fallback
                    self.ipfs_kit = ipfs_kit(
                        metadata=kit_options.get("metadata"),
                        auto_start_daemons=False  # Skip daemon startup on error
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

            # Properly initialize StorageManagerAnyIO using async method if needed
            backend = self.get_backend()
            
            # Create the storage manager first
            self.storage_manager = StorageManager(
                ipfs_model=self.models["ipfs"],
                cache_manager=self.cache_manager,
                credential_manager=self.credential_manager,
                resources=resources,
                metadata=metadata
            )
            
            # Storage manager initialization task reference to prevent coroutine warnings
            self.storage_manager_init_task = None
            
            # Handle async initialization if we're in an async context
            if backend:
                # We're in an async context, should use async initialization
                logger.info(f"Initializing StorageManagerAnyIO in async mode (backend: {backend})")
                
                # Create a function to run the async initialization with better error handling
                async def initialize_async():
                    try:
                        logger.info("Starting async storage model initialization")
                        await self.storage_manager._init_storage_models_async()
                        logger.info("Async storage model initialization completed successfully")
                    except Exception as e:
                        logger.error(f"Error in async storage model initialization: {e}")
                        logger.warning("Falling back to synchronous initialization")
                        # Fall back to synchronous initialization
                        try:
                            # Use anyio.to_thread to ensure async safe operation
                            await anyio.to_thread.run_sync(self.storage_manager._init_storage_models_sync)
                            logger.info("Synchronous storage model initialization completed as fallback")
                        except Exception as sync_e:
                            logger.error(f"Error in synchronous storage model initialization: {sync_e}")
                            logger.warning("Storage initialization may be incomplete. Some models may not be available.")
                
                # Attempt to run the async initialization while keeping a reference to the task
                try:
                    # Schedule the task properly in the current event loop based on the backend
                    if backend == "asyncio":
                        import asyncio
                        # Use create_task to run the initialization in the background but keep a reference
                        init_task = asyncio.create_task(initialize_async())
                        # Add completion callback to clear the reference when done
                        init_task.add_done_callback(
                            lambda t: logger.info("Storage manager initialization task completed")
                        )
                        # Store reference to prevent "coroutine was never awaited" warning
                        self.storage_manager_init_task = init_task
                        logger.info("Created asyncio task for storage model initialization")
                    elif backend == "trio":
                        import trio
                        # Try to use trio's nursery pattern if possible, otherwise use system task
                        try:
                            # Store token as a reference to prevent "coroutine was never awaited" warnings
                            token = trio.lowlevel.current_trio_token()
                            trio.lowlevel.spawn_system_task(initialize_async)
                            self.storage_manager_init_task = token
                            logger.info("Created trio task for storage model initialization")
                        except AttributeError:
                            # If lowlevel access not available, try higher-level API
                            logger.warning("Trio lowlevel API not available, using alternate approach")
                            try:
                                # Create a background task with trio nursery
                                # This is a workaround to ensure task is created even if we're not in a nursery
                                async def create_trio_task():
                                    async with trio.open_nursery() as nursery:
                                        nursery.start_soon(initialize_async)
                                
                                # Run the task creation right away
                                token = trio.lowlevel.current_trio_token()
                                trio.lowlevel.spawn_system_task(create_trio_task)
                                self.storage_manager_init_task = token
                                logger.info("Created trio nursery task for storage model initialization")
                            except Exception as trio_ex:
                                logger.error(f"Failed to create trio task: {trio_ex}")
                                # Fall back to synchronous init if we can't create a trio task
                                self.storage_manager._init_storage_models_sync()
                    else:
                        logger.warning(f"Unknown async backend: {backend}, falling back to sync initialization")
                        self.storage_manager._init_storage_models_sync()
                except (ImportError, RuntimeError) as e:
                    logger.warning(f"Could not create async task: {e}. Using synchronous initialization.")
                    # Fall back to synchronous initialization
                    self.storage_manager._init_storage_models_sync()
            else:
                # Not in an async context, use normal initialization
                logger.info("Using synchronous storage model initialization")
                try:
                    self.storage_manager._init_storage_models_sync()
                    logger.info("Synchronous storage model initialization completed")
                except Exception as e:
                    logger.error(f"Error in synchronous storage model initialization: {e}")
            
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
            # Check whether we're in an async context
            backend = self.get_backend() if hasattr(self, 'get_backend') else None
            StorageManagerController = None

            # Import AnyIO version if in async context, otherwise use sync version
            if backend:
                # We're in an async context, try to use AnyIO version
                try:
                    from ipfs_kit_py.mcp.controllers.storage_manager_controller_anyio import StorageManagerControllerAnyIO as StorageManagerController
                    logger.info(f"Using AnyIO-compatible StorageManager controller (backend: {backend})")
                except ImportError:
                    logger.warning("StorageManagerControllerAnyIO not found, falling back to sync version")
            
            # If not in async context or AnyIO import failed, try the sync version
            if StorageManagerController is None:
                try:
                    from ipfs_kit_py.mcp.controllers.storage_manager_controller import StorageManagerController
                    logger.warning("Using synchronous StorageManagerController" + 
                                 (" (despite being in async context)" if backend else ""))
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
        
        # Store initialization tasks to prevent "coroutine was never awaited" warnings
        if not hasattr(self, 'controller_init_tasks'):
            self.controller_init_tasks = {}
            
        for controller_name, has_controller, constructor in storage_controllers:
            if has_controller and (controller_name in self.models or 
                                 (len(controller_name.split('_')) > 1 and 
                                  controller_name.split('_')[1] in self.models)):
                try:
                    # Create the controller
                    controller = constructor()
                    self.controllers[controller_name] = controller
                    logger.info(f"{controller_name.split('_')[1].capitalize()} Controller added")
                    
                    # Handle potential async initialization methods
                    if hasattr(controller, 'initialize_async') and callable(controller.initialize_async):
                        # We need to handle async initialization properly
                        backend = self.get_backend()
                        
                        if backend == "asyncio":
                            import asyncio
                            # Create a task for async initialization with better error handling
                            async def init_storage_controller_async():
                                try:
                                    logger.info(f"Starting async initialization of {controller_name} controller")
                                    await controller.initialize_async()
                                    logger.info(f"{controller_name} controller async initialization completed successfully")
                                except Exception as e:
                                    logger.error(f"Error in async initialization of {controller_name} controller: {e}")
                                    # Try synchronous initialization as fallback if available
                                    if hasattr(controller, 'initialize') and callable(controller.initialize):
                                        try:
                                            # Use anyio to safely run sync method from async context
                                            await anyio.to_thread.run_sync(controller.initialize)
                                            logger.info(f"Fallback to sync initialization for {controller_name} controller succeeded")
                                        except Exception as sync_e:
                                            logger.error(f"Fallback sync initialization also failed for {controller_name} controller: {sync_e}")
                                finally:
                                    logger.info(f"{controller_name} controller initialization task completed")
                            
                            # Create task with proper cleanup
                            init_task = asyncio.create_task(init_storage_controller_async())
                            # Add cleanup callback to prevent resource leaks
                            init_task.add_done_callback(
                                lambda t: self.controller_init_tasks.pop(controller_name, None)
                                if hasattr(self, 'controller_init_tasks') else None
                            )
                            # Store reference to prevent "coroutine was never awaited" warning
                            self.controller_init_tasks[controller_name] = init_task
                            logger.info(f"Created asyncio task for {controller_name} controller initialization")
                        elif backend == "trio":
                            import trio
                            # Use trio's system task for initialization with improved error handling
                            async def init_storage_controller_trio():
                                try:
                                    logger.info(f"Starting async initialization of {controller_name} controller (trio)")
                                    await controller.initialize_async()
                                    logger.info(f"{controller_name} controller async initialization completed successfully (trio)")
                                except Exception as e:
                                    logger.error(f"Error in async initialization of {controller_name} controller (trio): {e}")
                                    # Try synchronous initialization as fallback if available
                                    if hasattr(controller, 'initialize') and callable(controller.initialize):
                                        try:
                                            # Use anyio to safely run sync method from async context
                                            await anyio.to_thread.run_sync(controller.initialize)
                                            logger.info(f"Fallback to sync initialization for {controller_name} controller succeeded (trio)")
                                        except Exception as sync_e:
                                            logger.error(f"Fallback sync initialization also failed for {controller_name} controller (trio): {sync_e}")
                                finally:
                                    logger.info(f"{controller_name} controller initialization task completed (trio)")
                            
                            # Use a try-except block to handle potential trio API issues
                            try:
                                # Store token as a reference to prevent "coroutine was never awaited" warnings
                                token = trio.lowlevel.current_trio_token()
                                trio.lowlevel.spawn_system_task(init_storage_controller_trio)
                                self.controller_init_tasks[controller_name] = token
                                logger.info(f"Created trio task for {controller_name} controller initialization")
                            except AttributeError:
                                # If lowlevel API not available, try alternate approach
                                logger.warning(f"Trio lowlevel API not available for {controller_name} controller, trying alternate approach")
                                try:
                                    # Create a background task with trio nursery
                                    async def create_trio_task():
                                        async with trio.open_nursery() as nursery:
                                            nursery.start_soon(init_storage_controller_trio)
                                    
                                    # Run the task creation
                                    token = object()  # Just a placeholder reference
                                    if hasattr(trio, 'from_thread') and hasattr(trio.from_thread, 'run'):
                                        trio.from_thread.run(create_trio_task)
                                    else:
                                        # Last resort - just run directly
                                        import asyncio
                                        asyncio.create_task(init_storage_controller_trio())
                                        
                                    self.controller_init_tasks[controller_name] = token
                                    logger.info(f"Created alternate trio task for {controller_name} controller initialization")
                                except Exception as trio_ex:
                                    logger.error(f"Failed to create trio task for {controller_name} controller: {trio_ex}")
                                    # Fall back to sync method
                                    if hasattr(controller, 'initialize') and callable(controller.initialize):
                                        controller.initialize()
                                        logger.info(f"Used direct synchronous initialization for {controller_name} controller as trio fallback")
                        else:
                            # Not in an async context or unknown backend
                            # Fall back to sync initialization if available
                            if hasattr(controller, 'initialize') and callable(controller.initialize):
                                controller.initialize()
                                logger.info(f"Used synchronous initialization for {controller_name} controller")
                            else:
                                logger.warning(f"No suitable initialization method found for {controller_name} controller")
                    # Check for normal initialize method
                    elif hasattr(controller, 'initialize') and callable(controller.initialize):
                        controller.initialize()
                        logger.info(f"Initialized {controller_name} controller with synchronous method")
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
        
        # Store initialization tasks to prevent "coroutine was never awaited" warnings
        if not hasattr(self, 'controller_init_tasks'):
            self.controller_init_tasks = {}
        
        for name, has_controller, constructor in optional_controllers:
            if has_controller and "ipfs" in self.models:
                try:
                    # Create the controller
                    controller = constructor()
                    self.controllers[name] = controller
                    logger.info(f"{name.capitalize()} Controller added")
                    
                    # Handle potential async initialization methods
                    if hasattr(controller, 'initialize_async') and callable(controller.initialize_async):
                        # We need to handle async initialization properly
                        backend = self.get_backend()
                        
                        if backend == "asyncio":
                            import asyncio
                            # Create a task for async initialization with improved error handling
                            async def init_controller_async():
                                try:
                                    logger.info(f"Starting async initialization of {name} controller")
                                    await controller.initialize_async()
                                    logger.info(f"{name} controller async initialization completed successfully")
                                except Exception as e:
                                    logger.error(f"Error in async initialization of {name} controller: {e}")
                                    # Try synchronous initialization as fallback if available
                                    if hasattr(controller, 'initialize') and callable(controller.initialize):
                                        try:
                                            # Use anyio to safely run sync method from async context
                                            await anyio.to_thread.run_sync(controller.initialize)
                                            logger.info(f"Fallback to sync initialization for {name} controller succeeded")
                                        except Exception as sync_e:
                                            logger.error(f"Fallback sync initialization also failed for {name} controller: {sync_e}")
                            
                            # Create and configure the task
                            init_task = asyncio.create_task(init_controller_async())
                            # Add cleanup callback to prevent resource leaks
                            init_task.add_done_callback(
                                lambda t: logger.info(f"{name} controller initialization task completed")
                            )
                            # Store reference to prevent "coroutine was never awaited" warning
                            self.controller_init_tasks[name] = init_task
                            logger.info(f"Created asyncio task for {name} controller initialization")
                        elif backend == "trio":
                            import trio
                            # Use trio's system task for initialization with improved error handling
                            async def init_controller_trio():
                                try:
                                    logger.info(f"Starting async initialization of {name} controller (trio)")
                                    await controller.initialize_async()
                                    logger.info(f"{name} controller async initialization completed successfully (trio)")
                                except Exception as e:
                                    logger.error(f"Error in async initialization of {name} controller (trio): {e}")
                                    # Try synchronous initialization as fallback if available
                                    if hasattr(controller, 'initialize') and callable(controller.initialize):
                                        try:
                                            # Use anyio to safely run sync method from async context
                                            await anyio.to_thread.run_sync(controller.initialize)
                                            logger.info(f"Fallback to sync initialization for {name} controller succeeded (trio)")
                                        except Exception as sync_e:
                                            logger.error(f"Fallback sync initialization also failed for {name} controller (trio): {sync_e}")
                                finally:
                                    logger.info(f"{name} controller initialization task completed (trio)")
                            
                            # Use a try-except block to handle potential trio API issues
                            try:
                                # Store token as a reference to prevent "coroutine was never awaited" warnings
                                token = trio.lowlevel.current_trio_token()
                                trio.lowlevel.spawn_system_task(init_controller_trio)
                                self.controller_init_tasks[name] = token
                                logger.info(f"Created trio task for {name} controller initialization")
                            except AttributeError:
                                # If lowlevel API not available, try alternate approach
                                logger.warning(f"Trio lowlevel API not available for {name} controller, trying alternate approach")
                                try:
                                    # Create a background task with trio nursery
                                    async def create_trio_task():
                                        async with trio.open_nursery() as nursery:
                                            nursery.start_soon(init_controller_trio)
                                    
                                    # Run the task creation
                                    token = object()  # Just a placeholder reference
                                    if hasattr(trio, 'from_thread') and hasattr(trio.from_thread, 'run'):
                                        trio.from_thread.run(create_trio_task)
                                    else:
                                        # Last resort - just run directly and hope for the best
                                        asyncio.create_task(init_controller_trio())
                                        
                                    self.controller_init_tasks[name] = token
                                    logger.info(f"Created alternate trio task for {name} controller initialization")
                                except Exception as trio_ex:
                                    logger.error(f"Failed to create trio task for {name} controller: {trio_ex}")
                                    # Fall back to sync method
                                    if hasattr(controller, 'initialize') and callable(controller.initialize):
                                        controller.initialize()
                                        logger.info(f"Used direct synchronous initialization for {name} controller as trio fallback")
                        else:
                            # Not in an async context or unknown backend
                            # Fall back to sync initialization if available
                            if hasattr(controller, 'initialize') and callable(controller.initialize):
                                controller.initialize()
                                logger.info(f"Used synchronous initialization for {name} controller")
                            else:
                                logger.warning(f"No suitable initialization method found for {name} controller")
                    # Check for normal initialize method
                    elif hasattr(controller, 'initialize') and callable(controller.initialize):
                        controller.initialize()
                        logger.info(f"Initialized {name} controller with synchronous method")
                
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
                    libp2p_controller = LibP2PController(self.models["libp2p"])
                    self.controllers["libp2p"] = libp2p_controller
                    logger.info("LibP2P Controller added")
                    
                    # Handle potential async initialization
                    if hasattr(libp2p_controller, 'initialize_async') and callable(libp2p_controller.initialize_async):
                        backend = self.get_backend()
                        
                        if backend == "asyncio":
                            import asyncio
                            # Create and track async init task
                            init_task = asyncio.create_task(libp2p_controller.initialize_async())
                            self.controller_init_tasks["libp2p"] = init_task
                            logger.info("Created asyncio task for LibP2P controller initialization")
                        elif backend == "trio":
                            import trio
                            # Use trio's system task
                            token = trio.lowlevel.current_trio_token()
                            trio.lowlevel.spawn_system_task(libp2p_controller.initialize_async)
                            self.controller_init_tasks["libp2p"] = token
                            logger.info("Created trio task for LibP2P controller initialization")
                    elif hasattr(libp2p_controller, 'initialize') and callable(libp2p_controller.initialize):
                        libp2p_controller.initialize()
                        logger.info("LibP2P Controller initialized with synchronous method")
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
                
                # Process request with error handling
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
                        "error_type": type(e).__name__,
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
            except Exception as e:
                logger.error(f"Error registering Storage Manager controller routes: {e}")
                
                # Add a simple fallback route for storage status
                try:
                    async def fallback_storage_status():
                        """Fallback for storage status endpoint."""
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
                    logger.info("Added fallback /storage/status route")
                except Exception as e:
                    logger.error(f"Error adding fallback route: {e}")
        else:
            logger.warning("Storage Manager controller not found in controllers or doesn't have register_routes method")
            
            # Add a simple fallback route for storage status
            try:
                async def fallback_storage_status():
                    """Fallback for storage status endpoint."""
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
                logger.info("Added fallback /storage/status route")
            except Exception as e:
                logger.error(f"Error adding fallback route: {e}")
            
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
        # Track registration success
        registration_success = True
        errors = []
        
        # Normalize prefix to ensure it starts with / but doesn't end with /
        if not prefix:
            prefix = "/mcp"  # Default prefix
        
        if not prefix.startswith('/'):
            prefix = '/' + prefix
        
        if prefix.endswith('/'):
            prefix = prefix[:-1]
            
        logger.info(f"Using normalized API prefix: {prefix}")
        
        # Mount the router
        try:
            app.include_router(self.router, prefix=prefix)
            logger.info(f"MCP Server router registered at prefix: {prefix}")
            
            # Add internal health check endpoint
            @app.get(f"{prefix}/__internal_health")
            async def internal_health_check():
                """Internal health check endpoint for monitoring."""
                return {
                    "status": "ok", 
                    "timestamp": time.time(), 
                    "server_id": id(self),
                    "controllers": list(self.controllers.keys())
                }
            logger.info(f"Internal health check endpoint registered at {prefix}/__internal_health")
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
            # Check size first to avoid growing too large before truncating
            if len(self.operation_log) >= 1000:
                self.operation_log = self.operation_log[-999:]  # Keep space for the new entry
            
            # Add the new operation
            self.operation_log.append(operation)
    
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
        
        # Track any shutdown errors to report at the end
        shutdown_errors = []
        
        # Helper function to safely await async methods
        async def safe_await(method, description, default_result=None):
            """Safely await an async method with proper error handling."""
            try:
                # Check if method is async (different ways)
                is_async = False
                coroutine_function = False
                
                # Check for __await__ attribute (awaitable object)
                if hasattr(method, '__await__'):
                    is_async = True
                
                # Use asyncio.iscoroutinefunction for more reliable detection
                try:
                    import asyncio
                    if asyncio.iscoroutinefunction(method):
                        is_async = True
                        coroutine_function = True
                except (ImportError, AttributeError):
                    pass
                
                if is_async:
                    # Direct await for async methods
                    if coroutine_function:
                        # The method is a coroutine function, call it
                        result = await method()
                    else:
                        # The method already returns an awaitable object
                        result = await method
                else:
                    # Run sync methods in a thread
                    result = await anyio.to_thread.run_sync(method)
                
                logger.info(f"Successfully executed {description}")
                return result
            except anyio.get_cancelled_exc_class() as e:
                # Task cancellation is not an error during shutdown
                logger.info(f"Task cancelled during {description}")
                return default_result
            except Exception as e:
                error_msg = f"Error during {description}: {str(e)}"
                logger.error(error_msg)
                shutdown_errors.append(error_msg)
                return default_result
                
        # Stop daemon health monitor first to prevent daemon restarts during shutdown
        if hasattr(self.ipfs_kit, 'stop_daemon_health_monitor'):
            try:
                logger.info("Stopping daemon health monitor...")
                self.ipfs_kit.stop_daemon_health_monitor()
                logger.info("Daemon health monitor stopped")
            except Exception as e:
                error_msg = f"Error stopping daemon health monitor: {str(e)}"
                logger.error(error_msg)
                shutdown_errors.append(error_msg)
        
        # Stop cache manager cleanup thread
        if hasattr(self.cache_manager, 'stop_cleanup_thread'):
            try:
                logger.info("Stopping cache cleanup thread...")
                self.cache_manager.stop_cleanup_thread()
                logger.info("Cache cleanup thread stopped")
            except Exception as e:
                error_msg = f"Error stopping cache cleanup thread: {str(e)}"
                logger.error(error_msg)
                shutdown_errors.append(error_msg)
                
        # Save cache metadata
        try:
            logger.info("Saving cache metadata...")
            # Check if _save_metadata is a callable method
            if hasattr(self.cache_manager, '_save_metadata') and callable(self.cache_manager._save_metadata):
                # Don't import os here - it's already imported at the module level
                # and causes conflicts with the cache_manager's own import
                
                self.cache_manager._save_metadata()
                logger.info("Cache metadata saved")
            else:
                logger.warning("Cache manager does not have _save_metadata method")
        except Exception as e:
            error_msg = f"Error saving cache metadata during shutdown: {str(e)}"
            logger.error(error_msg)
            shutdown_errors.append(error_msg)
        
        # Make sure any in-memory credential changes are persisted
        if hasattr(self, 'credential_manager'):
            try:
                logger.info("Ensuring credential persistence...")
                # Check if credential_cache is an attribute and credential_manager has add_credential method
                if (hasattr(self.credential_manager, 'credential_cache') and 
                    hasattr(self.credential_manager, 'add_credential') and
                    callable(self.credential_manager.add_credential)):
                    # The credential manager automatically persists changes, but we can
                    # explicitly save by re-adding the credentials that are in cache
                    for cred_key, cred_record in self.credential_manager.credential_cache.items():
                        if "_" in cred_key:
                            service, name = cred_key.split("_", 1)
                            self.credential_manager.add_credential(
                                service, name, cred_record["credentials"]
                            )
                    logger.info("Credentials persisted")
                else:
                    logger.warning("Credential manager does not have expected methods or attributes")
            except Exception as e:
                error_msg = f"Error persisting credentials during shutdown: {str(e)}"
                logger.error(error_msg)
                shutdown_errors.append(error_msg)
        
        # Create a list of controllers that need special shutdown handling
        special_controllers = [
            # (controller_name, cleanup_priority)
            # Higher priority means shutdown first
            ("peer_websocket", 10),
            ("webrtc", 9),
            ("libp2p", 8),
            # Other controllers with standard shutdown
        ]
            
        # Sort controllers by priority (highest first)
        special_controllers.sort(key=lambda x: x[1], reverse=True)
        
        # Handle special controllers first
        for controller_name, _ in special_controllers:
            if controller_name in self.controllers:
                controller = self.controllers[controller_name]
                
                # Check if controller has a shutdown method
                if hasattr(controller, "shutdown") and callable(controller.shutdown):
                    logger.info(f"Shutting down {controller_name} controller...")
                    
                    # Use the safe_await helper to handle the method
                    await safe_await(
                        controller.shutdown, 
                        f"shutdown of {controller_name} controller"
                    )
                else:
                    logger.warning(f"{controller_name} controller does not have a shutdown method")
                    # Attempt fallback cleanup based on controller type
                    await self._fallback_controller_cleanup(controller_name, controller)
        
        # Now handle remaining controllers
        for controller_name, controller in self.controllers.items():
            # Skip controllers that were already handled
            if any(controller_name == sc[0] for sc in special_controllers):
                continue
                
            # Check if controller has a shutdown method
            if hasattr(controller, 'shutdown') and callable(controller.shutdown):
                logger.info(f"Shutting down {controller_name} controller...")
                
                # Use the safe_await helper to handle the method
                await safe_await(
                    controller.shutdown, 
                    f"shutdown of {controller_name} controller"
                )
        
        # Special handling for models that need explicit cleanup
        model_classes_with_cleanup = [
            # Format: (model_key, method_name)
            ("ipfs", "shutdown_async"),  # Use our new async shutdown method
            ("libp2p", "stop"),
            ("storage_filecoin", "close_client"),
            ("storage_s3", "close_session")
        ]
        
        for model_key, method_name in model_classes_with_cleanup:
            if model_key in self.models:
                model = self.models[model_key]
                if hasattr(model, method_name) and callable(getattr(model, method_name)):
                    logger.info(f"Cleaning up {model_key} model...")
                    method = getattr(model, method_name)
                    
                    # Use the safe_await helper to handle the method
                    await safe_await(
                        method, 
                        f"cleanup of {model_key} model with {method_name}"
                    )
        
        # Properly shutdown the storage_manager if it exists
        if hasattr(self, 'storage_manager') and self.storage_manager is not None:
            logger.info("Shutting down Storage Manager...")
            
            # Cancel storage manager initialization task if it exists and is running
            if hasattr(self, 'storage_manager_init_task') and self.storage_manager_init_task is not None:
                try:
                    # Different task cancellation based on the event loop type
                    backend = self.get_backend()
                    if backend == "asyncio" and hasattr(self.storage_manager_init_task, 'cancel'):
                        self.storage_manager_init_task.cancel()
                        logger.debug("Cancelled asyncio storage manager initialization task")
                    elif backend == "trio":
                        # For trio, we can't directly cancel system tasks, but we mark it as handled
                        logger.debug("Marked trio storage manager initialization task as handled")
                except Exception as e:
                    logger.debug(f"Non-critical error cancelling storage manager init task: {e}")
            
            # Use the newly implemented shutdown_async method if available
            if hasattr(self.storage_manager, 'shutdown_async') and callable(self.storage_manager.shutdown_async):
                await safe_await(
                    self.storage_manager.shutdown_async,
                    "async shutdown of storage manager"
                )
            # Fall back to reset_async method if shutdown_async is not available (backward compatibility)
            elif hasattr(self.storage_manager, 'reset_async') and callable(self.storage_manager.reset_async):
                await safe_await(
                    self.storage_manager.reset_async,
                    "async reset of storage manager"
                )
            # Fall back to synchronous shutdown/reset methods as a last resort 
            elif hasattr(self.storage_manager, 'shutdown') and callable(self.storage_manager.shutdown):
                await safe_await(
                    self.storage_manager.shutdown,
                    "sync shutdown of storage manager"
                )
            elif hasattr(self.storage_manager, 'reset') and callable(self.storage_manager.reset):
                await safe_await(
                    self.storage_manager.reset,
                    "sync reset of storage manager"
                )
            
            # Even if the shutdown methods are called, do an extra cleanup of all models
            # to ensure everything is properly released
            if hasattr(self.storage_manager, 'storage_models'):
                try:
                    for model_name in list(self.storage_manager.storage_models.keys()):
                        try:
                            # Try to clear any resources in storage models explicitly
                            model = self.storage_manager.storage_models[model_name]
                            if hasattr(model, 'shutdown') and callable(getattr(model, 'shutdown')):
                                await safe_await(
                                    model.shutdown,
                                    f"shutdown of storage model {model_name}"
                                )
                            elif hasattr(model, 'close') and callable(getattr(model, 'close')):
                                await safe_await(
                                    model.close,
                                    f"close of storage model {model_name}"
                                )
                            elif hasattr(model, 'reset') and callable(getattr(model, 'reset')):
                                await safe_await(
                                    model.reset,
                                    f"reset of storage model {model_name}"
                                )
                        except Exception as e:
                            logger.debug(f"Non-critical error during explicit storage model {model_name} cleanup: {e}")
                    
                    # Clear the storage_models dictionary after all models have been shut down
                    if hasattr(self.storage_manager, 'storage_models'):
                        self.storage_manager.storage_models.clear()
                        logger.debug("Cleared storage manager models dictionary")
                except Exception as e:
                    logger.debug(f"Non-critical error during final storage models cleanup: {e}")
        
        # Cancel controller initialization tasks if they exist to prevent "coroutine was never awaited" warnings
        if hasattr(self, 'controller_init_tasks') and self.controller_init_tasks:
            logger.info(f"Cancelling {len(self.controller_init_tasks)} controller initialization tasks")
            for controller_name, task in list(self.controller_init_tasks.items()):
                try:
                    # Different cancellation based on the event loop type
                    backend = self.get_backend()
                    if backend == "asyncio" and hasattr(task, 'cancel'):
                        task.cancel()
                        logger.debug(f"Cancelled asyncio initialization task for {controller_name} controller")
                    elif backend == "trio":
                        # For trio, we can't directly cancel system tasks, but we mark it as handled
                        logger.debug(f"Marked trio initialization task for {controller_name} controller as handled")
                        
                    # Remove task from dictionary
                    del self.controller_init_tasks[controller_name]
                except Exception as e:
                    logger.debug(f"Non-critical error cancelling initialization task for {controller_name} controller: {e}")
            
            # Clear the tasks dictionary
            self.controller_init_tasks.clear()
        
        # Make sure to set is_shutting_down flag on all controllers that have it
        # This will help with cleanup in case the controller's shutdown method is called elsewhere
        for controller_name, controller in self.controllers.items():
            if hasattr(controller, "is_shutting_down") and isinstance(controller.is_shutting_down, bool):
                controller.is_shutting_down = True
                logger.debug(f"Set is_shutting_down flag on {controller_name} controller")
        
        # Final cleanup: clear references to help with garbage collection
        try:
            logger.info("Performing final reference cleanup...")
            # Clear any references that might prevent proper garbage collection
            for controller_name in list(self.controllers.keys()):
                try:
                    # Only log at debug level to avoid cluttering shutdown logs
                    logger.debug(f"Clearing references for {controller_name} controller")
                    
                    # Check if controller has a clear_references method
                    controller = self.controllers[controller_name]
                    if hasattr(controller, "clear_references") and callable(controller.clear_references):
                        try:
                            # Use anyio to call it safely
                            await safe_await(
                                controller.clear_references,
                                f"clear_references of {controller_name} controller"
                            )
                        except Exception as e:
                            logger.debug(f"Non-critical error clearing references for {controller_name}: {e}")
                except Exception as e:
                    logger.debug(f"Non-critical error during reference cleanup for {controller_name}: {e}")
        except Exception as e:
            logger.warning(f"Non-critical error during final reference cleanup: {e}")
        
        # Final log with summary
        if shutdown_errors:
            logger.warning(f"MCP Server shutdown completed with {len(shutdown_errors)} errors")
            for i, error in enumerate(shutdown_errors):
                logger.warning(f"Shutdown error {i+1}: {error}")
        else:
            logger.info("MCP Server shutdown completed successfully")
    
    async def _fallback_controller_cleanup(self, controller_name, controller):
        """Attempt fallback cleanup for a controller if normal shutdown fails."""
        try:
            # Generic function to safely call shutdown methods with proper async handling
            async def safe_call_shutdown_method(obj, method_name, obj_desc):
                """Safely call a shutdown method with proper async/sync handling."""
                if not hasattr(obj, method_name):
                    return False
                
                method = getattr(obj, method_name)
                if not callable(method):
                    return False
                
                try:
                    # More comprehensive check if method is async
                    is_async = False
                    coroutine_function = False
                    
                    # Check for __await__ attribute (awaitable object)
                    if hasattr(method, '__await__'):
                        is_async = True
                    
                    # Use asyncio.iscoroutinefunction for more reliable detection
                    try:
                        import asyncio
                        if asyncio.iscoroutinefunction(method):
                            is_async = True
                            coroutine_function = True
                    except (ImportError, AttributeError):
                        pass
                    
                    if is_async:
                        # Direct await for async methods
                        if coroutine_function:
                            # The method is a coroutine function, just call it
                            await method()
                        else:
                            # The method already returns an awaitable object
                            await method
                    else:
                        # Run sync methods in a thread
                        await anyio.to_thread.run_sync(method)
                    
                    logger.info(f"Successfully called {method_name}() on {obj_desc}")
                    return True
                except asyncio.CancelledError:
                    # This is normal during shutdown
                    logger.info(f"Coroutine {method_name}() on {obj_desc} was cancelled during shutdown")
                    return True
                except Exception as e:
                    logger.error(f"Error calling {method_name}() on {obj_desc}: {e}")
                    return False
            
            # Special handler for cleanup of task groups
            async def cleanup_task_group(obj, attr_name, obj_desc):
                """Safely clean up task groups and cancel scopes."""
                if not hasattr(obj, attr_name):
                    return False
                
                task_object = getattr(obj, attr_name)
                if task_object is None:
                    return False
                
                try:
                    # Handle different types of task objects
                    if hasattr(task_object, 'cancel'):
                        # It's a standard task
                        task_object.cancel()
                        logger.info(f"Cancelled task in {obj_desc}")
                        return True
                    elif hasattr(task_object, 'cancel_scope'):
                        # It's a task with cancel scope
                        task_object.cancel_scope.cancel()
                        logger.info(f"Cancelled task scope in {obj_desc}")
                        return True
                    elif isinstance(task_object, dict) and task_object.get('type') in ('task_group', 'manual'):
                        # It's our dictionary-based task tracking
                        logger.info(f"Noted dict-based task in {obj_desc} of type {task_object.get('type')}")
                        # Mark as no longer pending
                        task_object['pending'] = False
                        return True
                    else:
                        # Try to set a flag
                        if hasattr(obj, 'is_shutting_down') and isinstance(obj.is_shutting_down, bool):
                            obj.is_shutting_down = True
                            logger.info(f"Set is_shutting_down flag on {obj_desc}")
                            return True
                except Exception as e:
                    logger.error(f"Error cleaning up task in {obj_desc}: {e}")
                
                return False
                
            # Special handler for cleanup of event loops
            async def cleanup_event_loop_thread(controller, attr_name="event_loop_thread"):
                """Attempt to safely clean up event loop threads."""
                if not hasattr(controller, attr_name):
                    return False
                    
                thread_obj = getattr(controller, attr_name)
                if thread_obj is None:
                    return False
                    
                try:
                    # Try to access event_loop attribute if it exists
                    if hasattr(thread_obj, "event_loop") and thread_obj.event_loop:
                        try:
                            # Set shutdown flag if it exists
                            if hasattr(thread_obj.event_loop, "should_exit"):
                                thread_obj.event_loop.should_exit = True
                                logger.info("Set should_exit flag on event loop")
                            
                            # Try to call shutdown if it exists
                            if hasattr(thread_obj.event_loop, "shutdown"):
                                await safe_call_shutdown_method(
                                    thread_obj.event_loop,
                                    "shutdown",
                                    "event loop"
                                )
                                
                            # Try to call stop if it exists
                            if hasattr(thread_obj.event_loop, "stop"):
                                await safe_call_shutdown_method(
                                    thread_obj.event_loop,
                                    "stop",
                                    "event loop"
                                )
                        except Exception as e:
                            logger.error(f"Error shutting down event loop: {e}")
                            
                    # Try to join thread with timeout if it's a Thread object
                    if hasattr(thread_obj, "join") and callable(thread_obj.join):
                        try:
                            # Join with timeout to avoid hanging
                            thread_obj.join(timeout=1.0)
                            logger.info(f"Successfully joined {attr_name} thread")
                            return True
                        except Exception as e:
                            logger.error(f"Error joining {attr_name} thread: {e}")
                            
                    # Set thread to None to help with garbage collection
                    setattr(controller, attr_name, None)
                    logger.info(f"Cleared {attr_name} reference")
                    return True
                except Exception as e:
                    logger.error(f"Error cleaning up {attr_name}: {e}")
                    return False
            
            # Peer WebSocket controller fallback cleanup
            if controller_name == "peer_websocket":
                # Check for cleanup task first
                await cleanup_task_group(controller, "cleanup_task", "peer_websocket controller")
                
                # Set shutdown flag if exists
                if hasattr(controller, "is_shutting_down"):
                    controller.is_shutting_down = True
                
                if hasattr(controller, "peer_websocket_server") and controller.peer_websocket_server:
                    # Try to stop server with different possible method names
                    for method_name in ["stop", "shutdown", "close"]:
                        if await safe_call_shutdown_method(
                            controller.peer_websocket_server, 
                            method_name, 
                            "peer_websocket_server"
                        ):
                            break
                    
                    # Clear reference regardless of shutdown success
                    controller.peer_websocket_server = None
                    logger.info("Cleared peer_websocket_server reference")
                        
                if hasattr(controller, "peer_websocket_client") and controller.peer_websocket_client:
                    # Try to stop client with different possible method names
                    for method_name in ["stop", "disconnect", "close"]:
                        if await safe_call_shutdown_method(
                            controller.peer_websocket_client, 
                            method_name, 
                            "peer_websocket_client"
                        ):
                            break
                    
                    # Clear reference regardless of shutdown success
                    controller.peer_websocket_client = None
                    logger.info("Cleared peer_websocket_client reference")
                
                # Check for event loop thread and try to clean it up
                await cleanup_event_loop_thread(controller)
                
                # Clear references to connection maps if they exist
                for attr_name in ["connections", "peers", "peer_map"]:
                    if hasattr(controller, attr_name) and isinstance(getattr(controller, attr_name), dict):
                        getattr(controller, attr_name).clear()
                        logger.info(f"Cleared peer_websocket {attr_name} dictionary")
            
            # WebRTC controller fallback cleanup
            elif controller_name == "webrtc":
                # First check for cleanup task and cancel it properly
                await cleanup_task_group(controller, "cleanup_task", "webrtc controller")
                
                # Set shutdown flag if exists
                if hasattr(controller, "is_shutting_down"):
                    controller.is_shutting_down = True
                    logger.info("Set is_shutting_down flag on WebRTC controller")
                
                # Try to call final cleanup method if available
                if hasattr(controller, "_perform_final_cleanup") and callable(controller._perform_final_cleanup):
                    try:
                        logger.info("Calling WebRTC controller's _perform_final_cleanup method")
                        await controller._perform_final_cleanup()
                    except Exception as e:
                        logger.error(f"Error in WebRTC _perform_final_cleanup: {e}")
                
                # Close all streaming servers with dedicated method if available
                if hasattr(controller, "close_all_streaming_servers") and callable(controller.close_all_streaming_servers):
                    try:
                        logger.info("Calling WebRTC controller's close_all_streaming_servers method")
                        await controller.close_all_streaming_servers()
                    except Exception as e:
                        logger.error(f"Error in WebRTC close_all_streaming_servers: {e}")
                
                # Direct cleanup of members
                if hasattr(controller, "webrtc_server") and controller.webrtc_server:
                    # Try to stop server with different possible method names
                    for method_name in ["stop", "shutdown", "close"]:
                        if await safe_call_shutdown_method(
                            controller.webrtc_server, 
                            method_name, 
                            "webrtc_server"
                        ):
                            break
                    
                    # Clear reference regardless of shutdown success
                    controller.webrtc_server = None
                    logger.info("Cleared webrtc_server reference")
                
                # Close any open peer connections
                if hasattr(controller, "peer_connections") and isinstance(controller.peer_connections, dict):
                    for peer_id, connection in list(controller.peer_connections.items()):
                        if connection is None:
                            continue
                            
                        # Try multiple method names for closing connections
                        for method_name in ["close", "disconnect", "stop"]:
                            if await safe_call_shutdown_method(
                                connection, 
                                method_name, 
                                f"WebRTC connection to peer {peer_id}"
                            ):
                                break
                                
                        # Remove from dict regardless of close success
                        controller.peer_connections.pop(peer_id, None)
                    
                    # Clear dictionaries after iteration to prevent issues
                    if hasattr(controller, "active_streaming_servers"):
                        controller.active_streaming_servers.clear()
                    if hasattr(controller, "active_connections"):
                        controller.active_connections.clear()
                
                # Check for event loop thread and try to clean it up
                await cleanup_event_loop_thread(controller)
                
                # Clean up any media tracks if they exist
                if hasattr(controller, "tracks") and isinstance(controller.tracks, dict):
                    for track_id, track in list(controller.tracks.items()):
                        if track is None:
                            continue
                            
                        # Try to stop track
                        for method_name in ["stop", "close"]:
                            if await safe_call_shutdown_method(
                                track,
                                method_name,
                                f"WebRTC track {track_id}"
                            ):
                                break
                                
                        # Remove from dict regardless of close success
                        controller.tracks.pop(track_id, None)
                    
                    # Clear dictionary after iteration
                    controller.tracks.clear()
                    logger.info("Cleared WebRTC tracks dictionary")
                
                # Finally try model close method
                if hasattr(self.ipfs_model, "close_all_webrtc_connections"):
                    try:
                        logger.info("Calling model's close_all_webrtc_connections method")
                        await anyio.to_thread.run_sync(self.ipfs_model.close_all_webrtc_connections)
                    except Exception as e:
                        logger.error(f"Error in model's close_all_webrtc_connections: {e}")
            
            # LibP2P controller fallback cleanup
            elif controller_name == "libp2p":
                # First check for cleanup task and cancel it
                await cleanup_task_group(controller, "cleanup_task", "libp2p controller")
                
                # Set shutdown flag if exists
                if hasattr(controller, "is_shutting_down"):
                    controller.is_shutting_down = True
                
                # Try to stop the model directly if controller shutdown failed
                if "libp2p" in self.models and self.models["libp2p"] is not None:
                    # Try different method names for stopping/closing the model
                    for method_name in ["stop", "close", "shutdown"]:
                        if await safe_call_shutdown_method(
                            self.models["libp2p"], 
                            method_name, 
                            "LibP2P model"
                        ):
                            break
                
                # Also try to clean up any host or peer references in the controller
                for attr_name in ["host", "peer", "swarm"]:
                    if hasattr(controller, attr_name) and getattr(controller, attr_name) is not None:
                        obj = getattr(controller, attr_name)
                        # Try different method names
                        for method_name in ["stop", "close", "shutdown"]:
                            if await safe_call_shutdown_method(
                                obj, 
                                method_name, 
                                f"LibP2P {attr_name}"
                            ):
                                break
                
                # Check for event loop thread and try to clean it up
                await cleanup_event_loop_thread(controller)
            
            # Storage controllers fallback cleanup for any controller using "storage_" prefix
            elif controller_name.startswith("storage_"):
                backend_name = controller_name.replace("storage_", "")
                model_key = f"storage_{backend_name}"
                
                # Try to properly close any connections on the model
                if model_key in self.models and self.models[model_key] is not None:
                    model = self.models[model_key]
                    
                    # Try different possible cleanup method names
                    for method_name in ["close_client", "close_session", "close", "disconnect"]:
                        if await safe_call_shutdown_method(
                            model, 
                            method_name, 
                            f"{backend_name} storage model"
                        ):
                            break
            
            logger.info(f"Fallback cleanup completed for {controller_name} controller")
        except Exception as e:
            logger.error(f"Error during fallback cleanup for {controller_name} controller: {e}")
    
    # Make shutdown available as a synchronous method as well for backward compatibility
    def sync_shutdown(self):
        """
        Synchronous version of shutdown for backward compatibility.
        
        This method provides a synchronous interface to shut down the server and clean up
        all resources, with improved handling of async contexts and specialized controllers.
        It features:
        - Support for both asyncio and trio in various contexts
        - Enhanced detection of existing event loops
        - Automatic detection of coroutine vs. awaitable objects
        - Specialized cleanup for WebRTC and PeerWebSocket controllers
        - Comprehensive fallback for manual cleanup if async shutdown fails
        """
        # Ensure cache manager cleanup is handled properly even if async shutdown fails
        should_manual_cleanup = True
        
        # Create an anyio task group to run the async shutdown
        async def run_shutdown():
            try:
                await self.shutdown()
                # If we get here, the shutdown was successful
                nonlocal should_manual_cleanup
                should_manual_cleanup = False
            except Exception as e:
                logger.error(f"Error in async shutdown: {e}")
                # Let the outer try/except handle manual cleanup
        
        try:
            # Try to determine if we're already in an async context
            backend = self.get_backend()
            
            if backend is None:
                # We're not in an async context, use anyio.run
                try:
                    anyio.run(run_shutdown)
                    should_manual_cleanup = False  # If we get here, shutdown was successful
                except RuntimeError as e:
                    # Handle case when anyio.run fails
                    logger.warning(f"Could not use anyio.run: {e}")
                    # Fall through to manual cleanup
            else:
                # We're already in an async context
                logger.info(f"Already in async context ({backend}), using appropriate method")
                
                if backend == "asyncio":
                    # Use asyncio's run_until_complete
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Cannot use run_until_complete in a running loop
                            logger.warning("Loop is running, cannot use run_until_complete. Creating separate task.")
                            # Create a task and make sure to store it to prevent "coroutine was never awaited" warnings
                            shutdown_task = asyncio.create_task(run_shutdown())
                            # Store task in attributes to prevent it from being garbage collected
                            # before it completes and to avoid "coroutine was never awaited" warnings
                            if not hasattr(self, '_shutdown_tasks'):
                                self._shutdown_tasks = []
                            self._shutdown_tasks.append(shutdown_task)
                            logger.warning("Shutdown task created but cannot be awaited. Some resources may not be properly cleaned up.")
                        else:
                            # We can use run_until_complete
                            loop.run_until_complete(run_shutdown())
                            should_manual_cleanup = False  # If we get here, shutdown was successful
                    except RuntimeError:
                        # If we can't get the loop, create a new one just for shutdown
                        logger.warning("No running event loop, creating new one just for shutdown")
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(run_shutdown())
                            should_manual_cleanup = False  # If we get here, shutdown was successful
                        finally:
                            loop.close()
                elif backend == "trio":
                    # In trio, we need a different approach
                    try:
                        import trio
                        
                        # Use trio.from_thread.run for more robust execution
                        try:
                            # This is the most direct way to run async code from a sync context in trio
                            trio.from_thread.run(run_shutdown)
                            should_manual_cleanup = False
                        except (RuntimeError, AttributeError) as e:
                            # If direct run fails, try with nursery (if in nursery context)
                            if hasattr(trio, 'RunFinishedError') and isinstance(e, trio.RunFinishedError):
                                logger.warning(f"Direct trio.from_thread.run failed with RunFinishedError, trying with nursery")
                            else:
                                logger.warning(f"Direct trio.from_thread.run failed: {e}, trying with nursery")
                            
                            # Use trio nursery if we're in a trio context
                            async def trio_wrapper():
                                async with trio.open_nursery() as nursery:
                                    nursery.start_soon(run_shutdown)
                            
                            # This will fail if we're not in the right trio context
                            trio.from_thread.run(trio_wrapper)
                            should_manual_cleanup = False
                    except (ImportError, RuntimeError, AttributeError) as e:
                        logger.warning(f"Could not properly run shutdown in trio context: {e}")
                        # Fall through to manual cleanup
                else:
                    logger.error(f"Unknown async backend: {backend}. Will perform manual cleanup.")
        except RuntimeError as e:
            # If we get a "Already running" error, we're in an async context
            if "already running" in str(e):
                logger.warning("Cannot use anyio.run in an existing event loop. Using alternate approach.")
                
                # Try to determine current async library
                backend = self.get_backend()
                if backend == "asyncio":
                    # Use asyncio's run_until_complete
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Cannot use run_until_complete in a running loop
                            logger.warning("Loop is running, cannot use run_until_complete. Creating separate task.")
                            # Create a task and store it to prevent "coroutine was never awaited" warnings
                            shutdown_task = asyncio.create_task(run_shutdown())
                            # Store task in attributes to prevent it from being garbage collected
                            if not hasattr(self, '_shutdown_tasks'):
                                self._shutdown_tasks = []
                            self._shutdown_tasks.append(shutdown_task)
                            logger.warning("Shutdown task created but cannot be awaited. Some resources may not be properly cleaned up.")
                        else:
                            # We can use run_until_complete
                            loop.run_until_complete(run_shutdown())
                            should_manual_cleanup = False  # If we get here, shutdown was successful
                    except RuntimeError:
                        # If we can't get the loop, create a new one just for shutdown
                        logger.warning("No running event loop, creating new one just for shutdown")
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(run_shutdown())
                            should_manual_cleanup = False  # If we get here, shutdown was successful
                        finally:
                            loop.close()
                elif backend == "trio":
                    # In trio, we need a different approach
                    try:
                        import trio
                        
                        # Try to use trio.from_thread.run first (more reliable)
                        try:
                            trio.from_thread.run(run_shutdown)
                            should_manual_cleanup = False
                        except (RuntimeError, AttributeError) as e:
                            # If direct run fails, try with nursery
                            if hasattr(trio, 'RunFinishedError') and isinstance(e, trio.RunFinishedError):
                                logger.warning(f"Direct trio.from_thread.run failed with RunFinishedError, trying with nursery")
                            else:
                                logger.warning(f"Direct trio.from_thread.run failed: {e}, trying with nursery")
                            
                            # Try to use trio nursery if we're in a trio context
                            async def trio_wrapper():
                                async with trio.open_nursery() as nursery:
                                    nursery.start_soon(run_shutdown)
                            
                            # This will fail if we're not in the right trio context
                            trio.from_thread.run(trio_wrapper)
                            should_manual_cleanup = False
                    except (ImportError, RuntimeError, AttributeError) as e:
                        logger.warning(f"Could not properly run shutdown in trio context: {e}")
                        # Fall through to manual cleanup
                else:
                    logger.error(f"Unknown async backend: {backend}")
            else:
                logger.error(f"Error in sync_shutdown: {e}")
        except Exception as e:
            logger.error(f"Error during synchronous shutdown: {e}")
        
        # Perform manual cleanup if async shutdown failed or couldn't be run
        if should_manual_cleanup:
            logger.warning("Performing manual resource cleanup after failed async shutdown")
            try:
                # Signal shutdown for all controllers that have an is_shutting_down flag
                for controller_name, controller in self.controllers.items():
                    if hasattr(controller, "is_shutting_down") and isinstance(controller.is_shutting_down, bool):
                        try:
                            controller.is_shutting_down = True
                            logger.debug(f"Set is_shutting_down flag on {controller_name} controller during manual cleanup")
                        except Exception as e:
                            logger.debug(f"Error setting shutdown flag on {controller_name}: {e}")
                
                # Clean up cache manager
                if hasattr(self, 'cache_manager') and self.cache_manager:
                    try:
                        if hasattr(self.cache_manager, 'stop_cleanup_thread'):
                            self.cache_manager.stop_cleanup_thread()
                            logger.info("Successfully stopped cache cleanup thread during manual cleanup")
                        
                        if hasattr(self.cache_manager, '_save_metadata'):
                            self.cache_manager._save_metadata()
                            logger.info("Successfully saved cache metadata during manual cleanup")
                            
                        if hasattr(self.cache_manager, '_close_mmap_files'):
                            self.cache_manager._close_mmap_files()
                            logger.info("Successfully closed memory-mapped files during manual cleanup")
                            
                    except Exception as e:
                        logger.error(f"Error during manual cache manager cleanup: {e}")
                
                # Special handling for storage_manager
                if hasattr(self, 'storage_manager') and self.storage_manager:
                    logger.info("Manually cleaning up storage_manager")
                    
                    # Cancel storage manager initialization task if it exists
                    if hasattr(self, 'storage_manager_init_task') and self.storage_manager_init_task is not None:
                        try:
                            # Different cancellation based on the event loop type
                            backend = self.get_backend()
                            if backend == "asyncio" and hasattr(self.storage_manager_init_task, 'cancel'):
                                self.storage_manager_init_task.cancel()
                                logger.debug("Cancelled asyncio storage manager initialization task during manual cleanup")
                        except Exception as e:
                            logger.debug(f"Non-critical error cancelling storage manager init task: {e}")
                    
                    # Try to use the synchronous shutdown method if available
                    try:
                        if hasattr(self.storage_manager, 'shutdown') and callable(self.storage_manager.shutdown):
                            self.storage_manager.shutdown()
                            logger.info("Successfully called synchronous shutdown on storage_manager")
                        elif hasattr(self.storage_manager, 'reset') and callable(self.storage_manager.reset):
                            self.storage_manager.reset()
                            logger.info("Successfully called synchronous reset on storage_manager")
                    except Exception as e:
                        logger.error(f"Error during manual storage manager shutdown: {e}")
                    
                    # Additional direct cleanup for storage models
                    if hasattr(self.storage_manager, 'storage_models'):
                        try:
                            # Try to close/reset/shutdown each model
                            for model_name in list(self.storage_manager.storage_models.keys()):
                                try:
                                    model = self.storage_manager.storage_models[model_name]
                                    # Try different cleanup methods in order of preference
                                    if hasattr(model, 'shutdown') and callable(model.shutdown):
                                        model.shutdown()
                                    elif hasattr(model, 'close') and callable(model.close):
                                        model.close()
                                    elif hasattr(model, 'reset') and callable(model.reset):
                                        model.reset()
                                    logger.debug(f"Manually cleaned up storage model {model_name}")
                                except Exception as e:
                                    logger.debug(f"Non-critical error during manual cleanup of storage model {model_name}: {e}")
                            
                            # Clear storage models dictionary
                            self.storage_manager.storage_models.clear()
                            logger.debug("Cleared storage_models dictionary during manual cleanup")
                        except Exception as e:
                            logger.error(f"Error during manual storage models cleanup: {e}")
                
                # Cancel controller initialization tasks
                if hasattr(self, 'controller_init_tasks') and self.controller_init_tasks:
                    for controller_name, task in list(self.controller_init_tasks.items()):
                        try:
                            # Different cancellation depending on async backend
                            backend = self.get_backend()
                            if backend == "asyncio" and hasattr(task, 'cancel'):
                                task.cancel()
                                logger.debug(f"Manually cancelled asyncio task for {controller_name} controller")
                            # Nothing to do for trio tasks during manual cleanup
                            
                            # Remove from dictionary
                            del self.controller_init_tasks[controller_name]
                        except Exception as e:
                            logger.debug(f"Non-critical error cancelling task for {controller_name}: {e}")
                    
                    # Clear the dictionary
                    self.controller_init_tasks.clear()
                    logger.debug("Cleared controller initialization tasks dictionary")
                
                # Manual cleanup for IPFS model background tasks
                if "ipfs" in self.models:
                    try:
                        logger.info("Manually cleaning up IPFS model background tasks")
                        ipfs_model = self.models["ipfs"]
                        
                        # Use synchronous shutdown if available
                        if hasattr(ipfs_model, "shutdown") and callable(ipfs_model.shutdown):
                            logger.info("Calling IPFS model synchronous shutdown")
                            ipfs_model.shutdown()
                        
                        # Set shutting down flag
                        if hasattr(ipfs_model, "is_shutting_down"):
                            ipfs_model.is_shutting_down = True
                            
                        # Clear any tracked background tasks to prevent "coroutine was never awaited" warnings
                        if hasattr(ipfs_model, "_background_tasks"):
                            for task in list(ipfs_model._background_tasks):
                                try:
                                    # Different cancellation depending on async backend
                                    backend = self.get_backend()
                                    if backend == "asyncio" and hasattr(task, 'cancel'):
                                        task.cancel()
                                        logger.debug("Cancelled IPFS model background task")
                                except Exception as e:
                                    logger.debug(f"Non-critical error cancelling IPFS model task: {e}")
                            
                            # Clear the set
                            ipfs_model._background_tasks.clear()
                            logger.debug("Cleared IPFS model background tasks set")
                            
                        # Also clean up class-level background tasks in AsyncEventLoopHandler
                        if hasattr(AsyncEventLoopHandler, "_background_tasks"):
                            for task in list(AsyncEventLoopHandler._background_tasks):
                                try:
                                    # Different cancellation depending on async backend
                                    backend = self.get_backend()
                                    if backend == "asyncio" and hasattr(task, 'cancel'):
                                        task.cancel()
                                        logger.debug("Cancelled AsyncEventLoopHandler background task")
                                except Exception as e:
                                    logger.debug(f"Non-critical error cancelling AsyncEventLoopHandler task: {e}")
                            
                            # Clear the set
                            AsyncEventLoopHandler._background_tasks.clear()
                            logger.debug("Cleared AsyncEventLoopHandler background tasks set")
                    except Exception as e:
                        logger.error(f"Error during manual IPFS model cleanup: {e}")
                
                # Special handling for WebRTC and PeerWebSocket controllers
                for controller_name in ['webrtc', 'peer_websocket']:
                    if controller_name in self.controllers:
                        controller = self.controllers[controller_name]
                        logger.info(f"Manual cleanup for {controller_name} controller")
                        
                        # Set shutting_down flag
                        if hasattr(controller, "is_shutting_down"):
                            controller.is_shutting_down = True
                            
                        # Handle WebRTC server and connections
                        if controller_name == 'webrtc':
                            try:
                                # Cancel any running or pending tasks
                                for task_attr in ["_task", "_cleanup_task", "_monitor_task"]:
                                    if hasattr(controller, task_attr) and getattr(controller, task_attr):
                                        logger.info(f"Cancelling WebRTC {task_attr}")
                                        setattr(controller, task_attr, None)
                                
                                # Clean up any task groups
                                if hasattr(controller, "_task_group") and controller._task_group:
                                    logger.info("Cancelling WebRTC task group")
                                    controller._task_group = None
                                
                                # Manually clean up any streaming servers
                                if hasattr(controller, "active_streaming_servers"):
                                    for server_id in list(controller.active_streaming_servers.keys()):
                                        try:
                                            logger.info(f"Manually stopping WebRTC server {server_id}")
                                            # Try calling the controller's method first if it exists
                                            if hasattr(controller, "stop_streaming_server") and callable(controller.stop_streaming_server):
                                                # Call directly - it's synchronous in this context
                                                result = controller.stop_streaming_server(server_id=server_id)
                                                if result and isinstance(result, dict) and not result.get("success", False):
                                                    logger.warning(f"Failed to stop server via controller: {result.get('error', 'Unknown error')}")
                                                    # Fall back to model method
                                                    if hasattr(self.models["ipfs"], "stop_webrtc_streaming"):
                                                        self.models["ipfs"].stop_webrtc_streaming(server_id=server_id)
                                            # If no controller method, use model method directly
                                            elif hasattr(self.models["ipfs"], "stop_webrtc_streaming"):
                                                self.models["ipfs"].stop_webrtc_streaming(server_id=server_id)
                                        except Exception as e:
                                            logger.error(f"Error stopping WebRTC server {server_id}: {e}")
                                    
                                    # Clear the dictionary
                                    controller.active_streaming_servers.clear()
                                
                                # Close all connections
                                if hasattr(self.models["ipfs"], "close_all_webrtc_connections"):
                                    logger.info("Manually closing all WebRTC connections")
                                    self.models["ipfs"].close_all_webrtc_connections()
                                
                                # Clear connection tracking
                                for conn_attr in ["active_connections", "active_streams", "peer_connections", "tracks"]:
                                    if hasattr(controller, conn_attr) and getattr(controller, conn_attr):
                                        try:
                                            getattr(controller, conn_attr).clear()
                                            logger.debug(f"Cleared WebRTC {conn_attr} dictionary")
                                        except Exception as e:
                                            logger.error(f"Error clearing WebRTC {conn_attr}: {e}")
                                
                                # Clean up any event handlers
                                if hasattr(controller, "event_handlers"):
                                    controller.event_handlers.clear()
                            except Exception as e:
                                logger.error(f"Error in manual WebRTC cleanup: {e}")
                        
                        # Handle PeerWebSocket cleanup
                        elif controller_name == 'peer_websocket':
                            try:
                                # Cancel any running or pending tasks
                                for task_attr in ["_discovery_task", "_heartbeat_task", "_monitor_task"]:
                                    if hasattr(controller, task_attr) and getattr(controller, task_attr):
                                        logger.info(f"Cancelling PeerWebSocket {task_attr}")
                                        setattr(controller, task_attr, None)
                                
                                # Stop server if running
                                if hasattr(controller, "peer_websocket_server") and controller.peer_websocket_server:
                                    logger.info("Manually stopping PeerWebSocket server")
                                    # Try calling stop method first if it exists
                                    if hasattr(controller.peer_websocket_server, "stop") and callable(controller.peer_websocket_server.stop):
                                        try:
                                            # Directly call sync version if available
                                            if hasattr(controller.peer_websocket_server, "stop_sync") and callable(controller.peer_websocket_server.stop_sync):
                                                controller.peer_websocket_server.stop_sync()
                                            else:
                                                # Can't await in sync context, just clear reference
                                                pass
                                        except Exception as e:
                                            logger.error(f"Error stopping PeerWebSocket server: {e}")
                                    # Clear the reference
                                    controller.peer_websocket_server = None
                                
                                # Stop client if running
                                if hasattr(controller, "peer_websocket_client") and controller.peer_websocket_client:
                                    logger.info("Manually stopping PeerWebSocket client")
                                    # Try calling stop method first if it exists
                                    if hasattr(controller.peer_websocket_client, "stop") and callable(controller.peer_websocket_client.stop):
                                        try:
                                            # Directly call sync version if available
                                            if hasattr(controller.peer_websocket_client, "stop_sync") and callable(controller.peer_websocket_client.stop_sync):
                                                controller.peer_websocket_client.stop_sync()
                                            else:
                                                # Can't await in sync context, just clear reference
                                                pass
                                        except Exception as e:
                                            logger.error(f"Error stopping PeerWebSocket client: {e}")
                                    # Clear the reference
                                    controller.peer_websocket_client = None
                                    
                                # Clean up connection tracking
                                for conn_attr in ["connections", "pending_connections", "discovered_peers"]:
                                    if hasattr(controller, conn_attr) and getattr(controller, conn_attr):
                                        try:
                                            getattr(controller, conn_attr).clear()
                                            logger.debug(f"Cleared PeerWebSocket {conn_attr} dictionary")
                                        except Exception as e:
                                            logger.error(f"Error clearing PeerWebSocket {conn_attr}: {e}")
                            except Exception as e:
                                logger.error(f"Error in manual PeerWebSocket cleanup: {e}")
                
                # Try to call synchronous shutdown methods on other controllers that have them
                for controller_name, controller in self.controllers.items():
                    # Skip controllers handled above
                    if controller_name in ['webrtc', 'peer_websocket']:
                        continue
                        
                    # Try sync_shutdown if it exists
                    if hasattr(controller, 'sync_shutdown') and callable(controller.sync_shutdown):
                        try:
                            logger.info(f"Calling sync_shutdown on {controller_name} controller")
                            controller.sync_shutdown()
                            logger.info(f"Successfully called sync_shutdown on {controller_name} controller")
                        except Exception as e:
                            logger.error(f"Error calling sync_shutdown on {controller_name}: {e}")
                
                logger.info("Manual resource cleanup completed")
            except Exception as e:
                logger.error(f"Error during manual resource cleanup: {e}")
                # Continue anyway, as we're already in a shutdown/cleanup state
    
    def __del__(self):
        """Ensure resources are cleaned up when the server is deleted."""
        # Use anyio to run the async shutdown
        try:
            # Try to log the fact we're cleaning up in __del__
            # This might fail if the logger is already destroyed
            try:
                logger.info("Server being cleaned up by garbage collector")
            except:
                pass
                
            # Try async shutdown
            self.sync_shutdown()
        except Exception as e:
            # If shutdown fails, try to log the error
            try:
                logger.error(f"Error during server shutdown in __del__: {e}")
            except:
                # Can't even log, so just give up silently
                pass

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
parser.add_argument("--skip-daemon", action="store_true", help="Skip IPFS daemon initialization (run in daemon-less mode)")

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
        isolation_mode=args.isolation,
        skip_daemon=args.skip_daemon
    )
    
    # Register MCP server with app
    mcp_server.register_with_app(app, prefix=args.api_prefix)
    
    # Run the server
    print(f"Starting MCP server at http://{args.host}:{args.port} with API prefix {args.api_prefix}")
    print(f"Debug mode: {args.debug}, Isolation mode: {args.isolation}, Skip daemon: {args.skip_daemon}, AnyIO backend: {args.backend}")
    
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
        print(f"Trio support will be emulated by using asyncio.")
        anyio.run(server.serve, backend="asyncio")
    else:
        # For asyncio, we can use the standard approach
        anyio.run(server.serve, backend=args.backend)

if __name__ == "__main__":
    """
    Run the MCP server as a standalone application.
    """
    main()