"""MCP Server

This module provides the Multi-Content Protocol (MCP) server implementation.
"""

import logging
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)


class MCPServer:
    """
    Multi-Content Protocol (MCP) Server
    
    Provides a unified interface for interacting with various content-addressed storage
    systems and protocols.
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        ipfs_host: str = "127.0.0.1",
        ipfs_port: int = 5001,
        storage_backends: Optional[List[str]] = None,
        enable_libp2p: bool = False,
        enable_webrtc: bool = False,
        enable_wasm: bool = False,
        loglevel: str = "info",
        config_path: Optional[str] = None,
        debug_mode: Optional[bool] = None,  # Added for backward compatibility
    ):
        """Initialize the MCP Server."""
        self.host = host
        self.port = port
        self.ipfs_host = ipfs_host
        self.ipfs_port = ipfs_port
        self.storage_backends = storage_backends or ["ipfs"]
        self.enable_libp2p = enable_libp2p
        self.enable_webrtc = enable_webrtc
        self.enable_wasm = enable_wasm
        
        # Handle debug_mode for backward compatibility
        if debug_mode is not None:
            logger.info(f"Using debug_mode={debug_mode} (backward compatibility)")
            self.loglevel = "debug" if debug_mode else "info"
            self.debug_mode = debug_mode  # Store for compatibility
        else:
            self.loglevel = loglevel
            self.debug_mode = self.loglevel.lower() == "debug"  # Derive debug_mode from loglevel
            
        self.config_path = config_path
        
        self.controllers = {}
        self.models = {}
        
        self._initialize_logging()
        self._initialize_models()
        self._initialize_controllers()
    
    def _initialize_logging(self) -> None:
        """Initialize logging for the MCP Server."""
        numeric_level = getattr(logging, self.loglevel.upper(), None)
        if not isinstance(numeric_level, int):
            numeric_level = logging.INFO
        
        logging.basicConfig(
            level=numeric_level,
            format='%(asctime)s [%(levelname)8s] %(name)s: %(message)s',
            datefmt='%H:%M:%S'
        )
    
    def _initialize_models(self) -> None:
        """Initialize storage and protocol models."""
        logger.info("Initializing MCP models")
        
        # Initialize IPFS model if needed
        if "ipfs" in self.storage_backends:
            try:
                from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
                self.models["ipfs"] = IPFSModel(
                    ipfs_host=self.ipfs_host,
                    ipfs_port=self.ipfs_port
                )
                logger.info("IPFS model initialized")
            except ImportError as e:
                logger.warning(f"Could not initialize IPFS model: {e}")
        
        # Initialize Filecoin model if needed
        if "filecoin" in self.storage_backends:
            try:
                from ipfs_kit_py.mcp.models.storage.filecoin_model import FilecoinModel
                self.models["filecoin"] = FilecoinModel()
                logger.info("Filecoin model initialized")
            except ImportError as e:
                logger.warning(f"Could not initialize Filecoin model: {e}")
        
        # Initialize libp2p model if enabled
        if self.enable_libp2p:
            try:
                from ipfs_kit_py.mcp.models.libp2p_model import LibP2PModel
                self.models["libp2p"] = LibP2PModel()
                logger.info("libp2p model initialized")
            except ImportError as e:
                logger.warning(f"Could not initialize libp2p model: {e}")
        
        # Initialize WebRTC model if enabled
        if self.enable_webrtc:
            try:
                from ipfs_kit_py.mcp.models.webrtc_model import WebRTCModel
                self.models["webrtc"] = WebRTCModel()
                logger.info("WebRTC model initialized")
            except ImportError as e:
                logger.warning(f"Could not initialize WebRTC model: {e}")
    
    def _initialize_controllers(self) -> None:
        """Initialize controllers for models."""
        logger.info("Initializing MCP controllers")
        
        # Initialize IPFS controller if needed
        if "ipfs" in self.models:
            try:
                from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
                self.controllers["ipfs"] = IPFSController(self.models["ipfs"])
                logger.info("IPFS controller initialized")
            except ImportError as e:
                logger.warning(f"Could not initialize IPFS controller: {e}")
        
        # Initialize Filecoin controller if needed
        if "filecoin" in self.models:
            try:
                from ipfs_kit_py.mcp.controllers.storage.filecoin_controller import FilecoinController
                self.controllers["filecoin"] = FilecoinController(self.models["filecoin"])
                logger.info("Filecoin controller initialized")
            except ImportError as e:
                logger.warning(f"Could not initialize Filecoin controller: {e}")
        
        # Initialize libp2p controller if needed
        if "libp2p" in self.models:
            try:
                from ipfs_kit_py.mcp.controllers.libp2p_controller import LibP2PController
                self.controllers["libp2p"] = LibP2PController(self.models["libp2p"])
                logger.info("libp2p controller initialized")
            except ImportError as e:
                logger.warning(f"Could not initialize libp2p controller: {e}")
        
        # Initialize WebRTC controller if needed
        if "webrtc" in self.models:
            try:
                from ipfs_kit_py.mcp.controllers.webrtc_controller import WebRTCController
                self.controllers["webrtc"] = WebRTCController(self.models["webrtc"])
                logger.info("WebRTC controller initialized")
            except ImportError as e:
                logger.warning(f"Could not initialize WebRTC controller: {e}")
    
    def start(self) -> None:
        """Start the MCP Server."""
        logger.info(f"Starting MCP Server on {self.host}:{self.port}")
        # Add server startup logic here
    
    def stop(self) -> None:
        """Stop the MCP Server."""
        logger.info("Stopping MCP Server")
        # Add server shutdown logic here