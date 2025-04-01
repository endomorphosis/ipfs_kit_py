"""
High-Level API for IPFS Kit.

This module provides a simplified, user-friendly API for common IPFS operations,
with declarative configuration and plugin architecture for extensibility.

Key features:
1. Simplified API: High-level methods for common operations
2. Declarative Configuration: YAML/JSON configuration support
3. Plugin Architecture: Extensible design for custom functionality
4. Multi-language Support: Generates SDKs for Python, JavaScript, and Rust
5. Unified Interface: Consistent interface across all components

This high-level API serves as the main entry point for most users,
abstracting away the complexity of the underlying components.
"""

import os
import sys
import time
import json
import yaml
import logging
import importlib
import inspect
import tempfile
from typing import Dict, List, Tuple, Optional, Union, Any, Callable
from pathlib import Path

# Internal imports
try:
    # First try relative imports (when used as a package)
    from .ipfs_kit import ipfs_kit # Corrected import from .ipfs_kit_bak
    from .ipfs_fsspec import IPFSFileSystem
    from .error import IPFSError, IPFSValidationError, IPFSConfigurationError
    from .validation import validate_parameters
except ImportError:
    # For development/testing
    import os
    import sys
    # Add parent directory to path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from ipfs_kit_py.ipfs_kit import ipfs_kit # Corrected import from ipfs_kit_bak
    from ipfs_kit_py.ipfs_fsspec import IPFSFileSystem
    from ipfs_kit_py.error import IPFSError, IPFSValidationError, IPFSConfigurationError
    from ipfs_kit_py.validation import validate_parameters

# Optional imports
try:
    from . import ai_ml_integration
    AI_ML_AVAILABLE = True
except ImportError:
    AI_ML_AVAILABLE = False

# Configure logger
logger = logging.getLogger(__name__)


class IPFSSimpleAPI:
    """
    Simplified high-level API for IPFS operations.
    
    This class provides an intuitive interface for common IPFS operations,
    abstracting away the complexity of the underlying components.
    """
    
    def __init__(self, config_path: Optional[str] = None, **kwargs):
        """
        Initialize the high-level API with optional configuration file.
        
        Args:
            config_path: Path to YAML/JSON configuration file
            **kwargs: Additional configuration parameters that override file settings
        """
        # Initialize configuration
        self.config = self._load_config(config_path)
        
        # Override with kwargs
        if kwargs:
            self.config.update(kwargs)
            
        # Initialize the IPFS Kit
        resources = self.config.get("resources")
        metadata = self.config.get("metadata", {})
        metadata["role"] = self.config.get("role", "leecher")
        
        self.kit = ipfs_kit(
            resources=resources,
            metadata=metadata
        )
        
        # Initialize filesystem access
        try:
            # Initialize IPFSFileSystem directly
            cache_config = self.config.get("cache", {})
            ipfs_path = self.config.get("ipfs_path", "~/.ipfs") # Get IPFS path from config or default
            socket_path = self.config.get("socket_path") # Get socket path if configured
            use_mmap = self.config.get("use_mmap", True) # Get mmap setting

            self.fs = IPFSFileSystem(
                ipfs_path=ipfs_path,
                socket_path=socket_path,
                role=self.config.get("role", "leecher"),
                cache_config=cache_config,
                use_mmap=use_mmap
            )
            logger.info("IPFSFileSystem initialized successfully.")
        except (ImportError, AttributeError, Exception) as e:
            logger.warning(f"Failed to initialize filesystem: {e}")
            self.fs = None
        
        # Load plugins
        self.plugins = {}
        if "plugins" in self.config:
            self._load_plugins(self.config["plugins"])
            
        # Initialize extension registry
        self.extensions = {}
            
        logger.info(f"IPFSSimpleAPI initialized with role: {self.config.get('role', 'leecher')}")
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """
        Load configuration from file with fallbacks.
        
        Args:
            config_path: Path to YAML/JSON configuration file
            
        Returns:
            Dictionary of configuration parameters
        """
        config = {}
        
        # Default locations if not specified
        if not config_path:
            # Try standard locations
            standard_paths = [
                "./ipfs_config.yaml",
                "./ipfs_config.json",
                "~/.ipfs_kit/config.yaml",
                "~/.ipfs_kit/config.json",
                "/etc/ipfs_kit/config.yaml",
                "/etc/ipfs_kit/config.json",
            ]
            
            for path in standard_paths:
                expanded_path = os.path.expanduser(path)
                if os.path.exists(expanded_path):
                    config_path = expanded_path
                    break
        
        # Load from file if available
        if config_path and os.path.exists(os.path.expanduser(config_path)):
            expanded_path = os.path.expanduser(config_path)
            try:
                with open(expanded_path, 'r') as f:
                    if expanded_path.endswith(('.yaml', '.yml')):
                        config = yaml.safe_load(f)
                    else:
                        config = json.load(f)
                logger.info(f"Loaded configuration from {expanded_path}")
            except Exception as e:
                logger.warning(f"Error loading configuration from {expanded_path}: {e}")
                config = {}
        
        # Default configuration
        default_config = {
            "role": "leecher",
            "resources": {
                "max_memory": "1GB",
                "max_storage": "10GB",
            },
            "cache": {
                "memory_size": "100MB",
                "disk_size": "1GB",
                "disk_path": "~/.ipfs_kit/cache",
            },
            "timeouts": {
                "api": 30,
                "gateway": 60,
                "peer_connect": 30,
            },
            "logging": {
                "level": "INFO",
                "file": None,
            },
        }
        
        # Merge default with loaded config (loaded config takes precedence)
        merged_config = {**default_config, **config}
        
        return merged_config
    
    def _load_plugins(self, plugin_configs: List[Dict[str, Any]]):
        """
        Load and initialize plugins from configuration.
        
        Args:
            plugin_configs: List of plugin configurations
        """
        for plugin_config in plugin_configs:
            plugin_name = plugin_config.get("name")
            plugin_path = plugin_config.get("path")
            plugin_enabled = plugin_config.get("enabled", True)
            
            if not plugin_enabled:
                logger.info(f"Plugin {plugin_name} is disabled, skipping")
                continue
                
            if not plugin_name or not plugin_path:
                logger.warning(f"Invalid plugin configuration: {plugin_config}")
                continue
                
            try:
                # Import the plugin module
                if plugin_path.startswith("."):
                    # Relative import
                    plugin_module = importlib.import_module(plugin_path, package="ipfs_kit_py")
                else:
                    # Absolute import
                    plugin_module = importlib.import_module(plugin_path)
                
                # Get the plugin class
                plugin_class = getattr(plugin_module, plugin_name)
                
                # Initialize the plugin
                plugin_instance = plugin_class(
                    ipfs_kit=self.kit,
                    config=plugin_config.get("config", {})
                )
                
                # Register plugin
                self.plugins[plugin_name] = plugin_instance
                
                # Register plugin methods as extensions
                for method_name, method in inspect.getmembers(plugin_instance, predicate=inspect.ismethod):
                    if not method_name.startswith('_'):  # Only public methods
                        self.extensions[f"{plugin_name}.{method_name}"] = method
                
                logger.info(f"Plugin {plugin_name} loaded successfully")
                
            except Exception as e:
                logger.error(f"Error loading plugin {plugin_name} from {plugin_path}: {e}")
    
    def register_extension(self, name: str, func: Callable):
        """
        Register a custom extension function.
        
        Args:
            name: Name of the extension
            func: Function to register
        """
        self.extensions[name] = func
        logger.info(f"Extension {name} registered")
    
    def add(self, content, **kwargs) -> Dict[str, Any]:
        """
        Add content to IPFS.
        
        Args:
            content: Content to add (bytes, string, file path, or file-like object)
            **kwargs: Additional parameters
                - pin: Whether to pin the content (default: True)
                - wrap_with_directory: Whether to wrap with a directory (default: False)
                - chunker: Chunking algorithm (default: "size-262144")
                - hash: Hash algorithm (default: "sha2-256")
                
        Returns:
            Dictionary with operation result including CID
        """
        # Validate parameters
        validate_parameters(kwargs, {
            'pin': {'type': bool, 'default': True},
            'wrap_with_directory': {'type': bool, 'default': False},
            'chunker': {'type': str, 'default': 'size-262144'},
            'hash': {'type': str, 'default': 'sha2-256'},
        })
        
        # Handle different content types
        if isinstance(content, (str, bytes)) and os.path.exists(str(content)):
            # It's a file path
            # Need to pass as a positional argument, not named parameter
            kwargs_copy = kwargs.copy()
            result = self.kit.ipfs_add_path(str(content), **kwargs_copy)
        elif isinstance(content, str):
            # It's a string - create a temporary file and add it
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(content.encode('utf-8'))
                temp_file_path = temp_file.name
            try:
                # Need to pass as a positional argument, not named parameter
                kwargs_copy = kwargs.copy()
                result = self.kit.ipfs_add_path(temp_file_path, **kwargs_copy)
            finally:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
        elif isinstance(content, bytes):
            # It's bytes - create a temporary file and add it
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name
            try:
                # Need to pass as a positional argument, not named parameter
                kwargs_copy = kwargs.copy()
                result = self.kit.ipfs_add_path(temp_file_path, **kwargs_copy)
            finally:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
        elif hasattr(content, 'read'):
            # It's a file-like object - read it and add as bytes
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(content.read())
                temp_file_path = temp_file.name
            try:
                # Need to pass as a positional argument, not named parameter
                kwargs_copy = kwargs.copy()
                result = self.kit.ipfs_add_path(temp_file_path, **kwargs_copy)
            finally:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
        else:
            raise IPFSValidationError(f"Unsupported content type: {type(content)}")
        
        return result
    
    def get(self, cid: str, **kwargs) -> bytes:
        """
        Get content from IPFS by CID.
        
        Args:
            cid: Content identifier
            **kwargs: Additional parameters
                - timeout: Timeout in seconds (default: from config)
                
        Returns:
            Content as bytes
        """
        # Validate parameters
        validate_parameters(kwargs, {
            'timeout': {'type': int, 'default': self.config.get('timeouts', {}).get('api', 30)},
        })
        
        return self.kit.ipfs_cat(cid, **kwargs)
    
    def pin(self, cid: str, **kwargs) -> Dict[str, Any]:
        """
        Pin content to local node.
        
        Args:
            cid: Content identifier
            **kwargs: Additional parameters
                - recursive: Whether to pin recursively (default: True)
                
        Returns:
            Dictionary with operation result
        """
        # Validate parameters
        validate_parameters(kwargs, {
            'recursive': {'type': bool, 'default': True},
        })
        
        return self.kit.ipfs_pin_add(cid, **kwargs)
    
    def unpin(self, cid: str, **kwargs) -> Dict[str, Any]:
        """
        Unpin content from local node.
        
        Args:
            cid: Content identifier
            **kwargs: Additional parameters
                - recursive: Whether to unpin recursively (default: True)
                
        Returns:
            Dictionary with operation result
        """
        # Validate parameters
        validate_parameters(kwargs, {
            'recursive': {'type': bool, 'default': True},
        })
        
        return self.kit.ipfs_pin_rm(cid, **kwargs)
    
    def list_pins(self, **kwargs) -> Dict[str, Any]:
        """
        List pinned content.
        
        Args:
            **kwargs: Additional parameters
                - type: Pin type filter (default: "all")
                - quiet: Whether to return only CIDs (default: False)
                
        Returns:
            Dictionary with operation result including pins
        """
        # Validate parameters
        validate_parameters(kwargs, {
            'type': {'type': str, 'default': 'all', 'choices': ['all', 'direct', 'indirect', 'recursive']},
            'quiet': {'type': bool, 'default': False},
        })
        
        return self.kit.ipfs_pin_ls(**kwargs)
    
    def publish(self, cid: str, key: str = "self", **kwargs) -> Dict[str, Any]:
        """
        Publish content to IPNS.
        
        Args:
            cid: Content identifier
            key: IPNS key to use (default: "self")
            **kwargs: Additional parameters
                - lifetime: IPNS record lifetime (default: "24h")
                - ttl: IPNS record TTL (default: "1h")
                
        Returns:
            Dictionary with operation result including IPNS name
        """
        # Validate parameters
        validate_parameters(kwargs, {
            'lifetime': {'type': str, 'default': '24h'},
            'ttl': {'type': str, 'default': '1h'},
        })
        
        return self.kit.ipfs_name_publish(cid, key=key, **kwargs)
    
    def resolve(self, name: str, **kwargs) -> Dict[str, Any]:
        """
        Resolve IPNS name to CID.
        
        Args:
            name: IPNS name to resolve
            **kwargs: Additional parameters
                - recursive: Whether to resolve recursively (default: True)
                - timeout: Timeout in seconds (default: from config)
                
        Returns:
            Dictionary with operation result including resolved path
        """
        # Validate parameters
        validate_parameters(kwargs, {
            'recursive': {'type': bool, 'default': True},
            'timeout': {'type': int, 'default': self.config.get('timeouts', {}).get('api', 30)},
        })
        
        return self.kit.ipfs_name_resolve(name, **kwargs)
    
    def connect(self, peer: str, **kwargs) -> Dict[str, Any]:
        """
        Connect to a peer.
        
        Args:
            peer: Peer multiaddress
            **kwargs: Additional parameters
                - timeout: Timeout in seconds (default: from config)
                
        Returns:
            Dictionary with operation result
        """
        # Validate parameters
        validate_parameters(kwargs, {
            'timeout': {'type': int, 'default': self.config.get('timeouts', {}).get('peer_connect', 30)},
        })
        
        return self.kit.ipfs_swarm_connect(peer, **kwargs)
    
    def peers(self, **kwargs) -> Dict[str, Any]:
        """
        List connected peers.
        
        Args:
            **kwargs: Additional parameters
                - verbose: Whether to return verbose information (default: False)
                - latency: Whether to include latency information (default: False)
                - direction: Whether to include connection direction (default: False)
                
        Returns:
            Dictionary with operation result including peers
        """
        # Validate parameters
        validate_parameters(kwargs, {
            'verbose': {'type': bool, 'default': False},
            'latency': {'type': bool, 'default': False},
            'direction': {'type': bool, 'default': False},
        })
        
        return self.kit.ipfs_swarm_peers(**kwargs)
    
    def open(self, path: str, mode: str = "rb", **kwargs):
        """
        Open a file-like object for IPFS content.
        
        Args:
            path: IPFS path or CID
            mode: File mode (default: "rb")
            **kwargs: Additional parameters passed to filesystem
                
        Returns:
            File-like object
        """
        # Make sure path has ipfs:// prefix
        if not path.startswith(("ipfs://", "ipns://")):
            path = f"ipfs://{path}"
            
        return self.fs.open(path, mode, **kwargs)
    
    def read(self, path: str, **kwargs) -> bytes:
        """
        Read content from IPFS path.
        
        Args:
            path: IPFS path or CID
            **kwargs: Additional parameters
                
        Returns:
            Content as bytes
        """
        # Make sure path has ipfs:// prefix
        if not path.startswith(("ipfs://", "ipns://")):
            path = f"ipfs://{path}"
            
        return self.fs.cat(path, **kwargs)
    
    def exists(self, path: str, **kwargs) -> bool:
        """
        Check if path exists in IPFS.
        
        Args:
            path: IPFS path or CID
            **kwargs: Additional parameters
                
        Returns:
            True if path exists, False otherwise
        """
        # Make sure path has ipfs:// prefix
        if not path.startswith(("ipfs://", "ipns://")):
            path = f"ipfs://{path}"
            
        return self.fs.exists(path, **kwargs)
    
    def ls(self, path: str, **kwargs) -> List[Dict[str, Any]]:
        """
        List directory contents.
        
        Args:
            path: IPFS path or CID
            **kwargs: Additional parameters
                - detail: Whether to return detailed information (default: True)
                
        Returns:
            List of file/directory entries
        """
        # Validate parameters
        validate_parameters(kwargs, {
            'detail': {'type': bool, 'default': True},
        })
        
        # Make sure path has ipfs:// prefix
        if not path.startswith(("ipfs://", "ipns://")):
            path = f"ipfs://{path}"
            
        return self.fs.ls(path, **kwargs)
    
    def cluster_add(self, content, **kwargs) -> Dict[str, Any]:
        """
        Add content to IPFS cluster.
        
        Args:
            content: Content to add (bytes, string, file path, or file-like object)
            **kwargs: Additional parameters
                - replication_factor: Replication factor (default: -1 for all nodes)
                - name: Optional name for the content
                
        Returns:
            Dictionary with operation result including CID
        """
        # Validate parameters
        validate_parameters(kwargs, {
            'replication_factor': {'type': int, 'default': -1},
            'name': {'type': str, 'default': None},
        })
        
        # Only available in master or worker roles
        if self.config.get("role") == "leecher":
            raise IPFSError("Cluster operations not available in leecher role")
        
        # Handle different content types as in the add method
        if isinstance(content, (str, bytes)) and os.path.exists(str(content)):
            # It's a file path
            result = self.kit.cluster_add_file(str(content), **kwargs)
        elif isinstance(content, str):
            # It's a string
            result = self.kit.cluster_add(content.encode('utf-8'), **kwargs)
        elif isinstance(content, bytes):
            # It's bytes
            result = self.kit.cluster_add(content, **kwargs)
        elif hasattr(content, 'read'):
            # It's a file-like object
            result = self.kit.cluster_add(content.read(), **kwargs)
        else:
            raise IPFSValidationError(f"Unsupported content type: {type(content)}")
        
        return result
    
    def cluster_pin(self, cid: str, **kwargs) -> Dict[str, Any]:
        """
        Pin content to IPFS cluster.
        
        Args:
            cid: Content identifier
            **kwargs: Additional parameters
                - replication_factor: Replication factor (default: -1 for all nodes)
                - name: Optional name for the content
                
        Returns:
            Dictionary with operation result
        """
        # Validate parameters
        validate_parameters(kwargs, {
            'replication_factor': {'type': int, 'default': -1},
            'name': {'type': str, 'default': None},
        })
        
        # Only available in master or worker roles
        if self.config.get("role") == "leecher":
            raise IPFSError("Cluster operations not available in leecher role")
        
        return self.kit.cluster_pin_add(cid, **kwargs)
    
    def cluster_status(self, cid: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Get cluster pin status.
        
        Args:
            cid: Content identifier (optional, if not provided, returns status for all pins)
            **kwargs: Additional parameters
                
        Returns:
            Dictionary with operation result including pin status
        """
        # Only available in master or worker roles
        if self.config.get("role") == "leecher":
            raise IPFSError("Cluster operations not available in leecher role")
        
        if cid:
            return self.kit.cluster_status(cid, **kwargs)
        else:
            return self.kit.cluster_status_all(**kwargs)
    
    def cluster_peers(self, **kwargs) -> Dict[str, Any]:
        """
        List cluster peers.
        
        Args:
            **kwargs: Additional parameters
                
        Returns:
            Dictionary with operation result including peers
        """
        # Only available in master or worker roles
        if self.config.get("role") == "leecher":
            raise IPFSError("Cluster operations not available in leecher role")
        
        return self.kit.cluster_peers(**kwargs)
    
    def ai_model_add(self, model, metadata: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """
        Add a machine learning model to the registry.
        
        Args:
            model: Machine learning model instance
            metadata: Model metadata
            **kwargs: Additional parameters
                
        Returns:
            Dictionary with operation result including CID
        """
        if not AI_ML_AVAILABLE:
            raise IPFSError("AI/ML integration not available")
        
        return self.kit.ai_model_add(model, metadata, **kwargs)
    
    def ai_model_get(self, model_id: str, **kwargs) -> Dict[str, Any]:
        """
        Get a machine learning model from the registry.
        
        Args:
            model_id: Model identifier or CID
            **kwargs: Additional parameters
                
        Returns:
            Dictionary with operation result including model
        """
        if not AI_ML_AVAILABLE:
            raise IPFSError("AI/ML integration not available")
        
        return self.kit.ai_model_get(model_id, **kwargs)
    
    def ai_dataset_add(self, dataset, metadata: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """
        Add a dataset to the registry.
        
        Args:
            dataset: Dataset instance or path
            metadata: Dataset metadata
            **kwargs: Additional parameters
                
        Returns:
            Dictionary with operation result including CID
        """
        if not AI_ML_AVAILABLE:
            raise IPFSError("AI/ML integration not available")
        
        return self.kit.ai_dataset_add(dataset, metadata, **kwargs)
    
    def ai_dataset_get(self, dataset_id: str, **kwargs) -> Dict[str, Any]:
        """
        Get a dataset from the registry.
        
        Args:
            dataset_id: Dataset identifier or CID
            **kwargs: Additional parameters
                
        Returns:
            Dictionary with operation result including dataset
        """
        if not AI_ML_AVAILABLE:
            raise IPFSError("AI/ML integration not available")
        
        return self.kit.ai_dataset_get(dataset_id, **kwargs)
    
    def call_extension(self, extension_name: str, *args, **kwargs) -> Any:
        """
        Call a registered extension.
        
        Args:
            extension_name: Name of the extension
            *args: Positional arguments
            **kwargs: Keyword arguments
                
        Returns:
            Result of the extension function
        """
        if extension_name not in self.extensions:
            raise IPFSError(f"Extension not found: {extension_name}")
        
        extension_func = self.extensions[extension_name]
        return extension_func(*args, **kwargs)
    
    def __call__(self, method_name: str, *args, **kwargs) -> Any:
        """
        Call a method by name.
        
        This enables declarative API calls from configuration or remote clients.
        
        Args:
            method_name: Name of the method to call
            *args: Positional arguments
            **kwargs: Keyword arguments
                
        Returns:
            Result of the method call
        """
        if hasattr(self, method_name) and callable(getattr(self, method_name)):
            return getattr(self, method_name)(*args, **kwargs)
        elif "." in method_name:
            # It's an extension
            return self.call_extension(method_name, *args, **kwargs)
        else:
            raise IPFSError(f"Method not found: {method_name}")
    
    def generate_sdk(self, language: str, output_dir: str) -> Dict[str, Any]:
        """
        Generate SDK for a specific language.
        
        Args:
            language: Target language ("python", "javascript", "rust")
            output_dir: Output directory
                
        Returns:
            Dictionary with operation result
        """
        if language not in ["python", "javascript", "rust"]:
            raise IPFSValidationError(f"Unsupported language: {language}")
        
        output_path = os.path.expanduser(output_dir)
        os.makedirs(output_path, exist_ok=True)
        
        # Get all public methods
        methods = []
        for method_name in dir(self):
            if not method_name.startswith('_') and callable(getattr(self, method_name)):
                method = getattr(self, method_name)
                if method.__doc__:
                    methods.append({
                        "name": method_name,
                        "doc": method.__doc__,
                        "signature": str(inspect.signature(method)),
                    })
        
        # Generate SDK files
        if language == "python":
            return self._generate_python_sdk(methods, output_path)
        elif language == "javascript":
            return self._generate_javascript_sdk(methods, output_path)
        elif language == "rust":
            return self._generate_rust_sdk(methods, output_path)
    
    def _generate_python_sdk(self, methods: List[Dict[str, Any]], output_path: str) -> Dict[str, Any]:
        """
        Generate Python SDK.
        
        Args:
            methods: List of method definitions
            output_path: Output directory
                
        Returns:
            Dictionary with operation result
        """
        # Create SDK directory structure
        sdk_path = os.path.join(output_path, "ipfs_kit_sdk")
        os.makedirs(sdk_path, exist_ok=True)
        
        # Create __init__.py
        with open(os.path.join(sdk_path, "__init__.py"), "w") as f:
            f.write("""\"\"\"
IPFS Kit Python SDK.

This SDK provides a simplified interface to IPFS Kit.
\"\"\"

from .client import IPFSClient

__version__ = "0.1.0"
""")
        
        # Create client.py
        with open(os.path.join(sdk_path, "client.py"), "w") as f:
            f.write("""\"\"\"
IPFS Kit Client.

This module provides a client for interacting with IPFS Kit.
\"\"\"

import os
import json
import yaml
import requests
from typing import Dict, List, Optional, Union, Any

class IPFSClient:
    \"\"\"
    Client for interacting with IPFS Kit.
    
    This client provides a simplified interface to IPFS Kit,
    with methods for common operations.
    \"\"\"
    
    def __init__(self, config_path: Optional[str] = None, api_url: Optional[str] = None, **kwargs):
        \"\"\"
        Initialize the IPFS Kit client.
        
        Args:
            config_path: Path to YAML/JSON configuration file
            api_url: URL of the IPFS Kit API server
            **kwargs: Additional configuration parameters
        \"\"\"
        # Initialize configuration
        self.config = self._load_config(config_path)
        
        # Override with kwargs
        if kwargs:
            self.config.update(kwargs)
            
        # Set API URL
        self.api_url = api_url or self.config.get("api_url", "http://localhost:8000")
        
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        \"\"\"
        Load configuration from file with fallbacks.
        
        Args:
            config_path: Path to YAML/JSON configuration file
            
        Returns:
            Dictionary of configuration parameters
        \"\"\"
        config = {}
        
        # Default locations if not specified
        if not config_path:
            # Try standard locations
            standard_paths = [
                "./ipfs_config.yaml",
                "./ipfs_config.json",
                "~/.ipfs_kit/config.yaml",
                "~/.ipfs_kit/config.json",
            ]
            
            for path in standard_paths:
                expanded_path = os.path.expanduser(path)
                if os.path.exists(expanded_path):
                    config_path = expanded_path
                    break
        
        # Load from file if available
        if config_path and os.path.exists(os.path.expanduser(config_path)):
            expanded_path = os.path.expanduser(config_path)
            try:
                with open(expanded_path, 'r') as f:
                    if expanded_path.endswith(('.yaml', '.yml')):
                        config = yaml.safe_load(f)
                    else:
                        config = json.load(f)
            except Exception as e:
                print(f"Error loading configuration from {expanded_path}: {e}")
                config = {}
        
        return config
""")
        
            # Add methods
            for method in methods:
                # Skip internal methods and non-API methods
                if method["name"] in ["generate_sdk", "_generate_python_sdk", "_generate_javascript_sdk", "_generate_rust_sdk"]:
                    continue
                    
                f.write(f"""
    def {method["name"]}(self, *args, **kwargs):
        {method["doc"]}
        # Make API request
        response = requests.post(
            f"{'{self.api_url}'}/api/{method["name"]}",
            json={"args": args, "kwargs": kwargs}
        )
        
        # Check for errors
        response.raise_for_status()
        
        return response.json()
""")
        
        # Create setup.py
        with open(os.path.join(output_path, "setup.py"), "w") as f:
            f.write("""from setuptools import setup, find_packages

setup(
    name="ipfs_kit_sdk",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.28.0",
        "pyyaml>=6.0",
    ],
    author="IPFS Kit Team",
    author_email="author@example.com",
    description="SDK for IPFS Kit",
    keywords="ipfs, sdk",
    url="https://github.com/example/ipfs_kit_sdk",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.8",
)
""")
        
        # Create README.md
        with open(os.path.join(output_path, "README.md"), "w") as f:
            f.write("""# IPFS Kit Python SDK

This SDK provides a simplified interface to IPFS Kit.

## Installation

```bash
pip install ipfs_kit_sdk
```

## Usage

```python
from ipfs_kit_sdk import IPFSClient

# Initialize client
client = IPFSClient()

# Add content to IPFS
result = client.add("Hello, IPFS!")
print(f"Added content with CID: {result['cid']}")

# Get content from IPFS
content = client.get(result['cid'])
print(f"Retrieved content: {content}")
```

## Configuration

You can configure the client with a YAML or JSON file:

```yaml
# config.yaml
api_url: "http://localhost:8000"
timeouts:
  api: 30
  gateway: 60
```

```python
client = IPFSClient(config_path="config.yaml")
```

Or with parameters:

```python
client = IPFSClient(api_url="http://localhost:8000")
```

## Available Methods

""")
            
            # Add method documentation
            for method in methods:
                # Skip internal methods and non-API methods
                if method["name"] in ["generate_sdk", "_generate_python_sdk", "_generate_javascript_sdk", "_generate_rust_sdk"]:
                    continue
                    
                f.write(f"""### {method["name"]}{method["signature"]}

{method["doc"]}

```python
result = client.{method["name"]}(...)
```

""")
        
        return {
            "success": True,
            "output_path": output_path,
            "language": "python",
            "files_generated": [
                os.path.join(sdk_path, "__init__.py"),
                os.path.join(sdk_path, "client.py"),
                os.path.join(output_path, "setup.py"),
                os.path.join(output_path, "README.md"),
            ]
        }
    
    def _generate_javascript_sdk(self, methods: List[Dict[str, Any]], output_path: str) -> Dict[str, Any]:
        """
        Generate JavaScript SDK.
        
        Args:
            methods: List of method definitions
            output_path: Output directory
                
        Returns:
            Dictionary with operation result
        """
        # Create SDK directory structure
        sdk_path = os.path.join(output_path, "ipfs-kit-sdk")
        os.makedirs(sdk_path, exist_ok=True)
        os.makedirs(os.path.join(sdk_path, "src"), exist_ok=True)
        
        # Create package.json
        with open(os.path.join(sdk_path, "package.json"), "w") as f:
            f.write("""{
  "name": "ipfs-kit-sdk",
  "version": "0.1.0",
  "description": "SDK for IPFS Kit",
  "main": "src/index.js",
  "scripts": {
    "test": "echo \\"Error: no test specified\\" && exit 1"
  },
  "keywords": [
    "ipfs",
    "sdk"
  ],
  "author": "IPFS Kit Team",
  "license": "MIT",
  "dependencies": {
    "axios": "^1.3.4",
    "js-yaml": "^4.1.0"
  }
}
""")
        
        # Create src/index.js
        with open(os.path.join(sdk_path, "src", "index.js"), "w") as f:
            f.write("""/**
 * IPFS Kit JavaScript SDK.
 * 
 * This SDK provides a simplified interface to IPFS Kit.
 */

const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');
const axios = require('axios');

class IPFSClient {
  /**
   * Initialize the IPFS Kit client.
   * 
   * @param {Object} options - Configuration options
   * @param {string} options.configPath - Path to YAML/JSON configuration file
   * @param {string} options.apiUrl - URL of the IPFS Kit API server
   */
  constructor(options = {}) {
    // Initialize configuration
    this.config = this._loadConfig(options.configPath);
    
    // Override with options
    if (options) {
      this.config = { ...this.config, ...options };
    }
    
    // Set API URL
    this.apiUrl = options.apiUrl || this.config.apiUrl || 'http://localhost:8000';
    
    // Create axios instance
    this.client = axios.create({
      baseURL: this.apiUrl,
      timeout: (this.config.timeouts && this.config.timeouts.api) || 30000,
    });
  }
  
  /**
   * Load configuration from file with fallbacks.
   * 
   * @param {string} configPath - Path to YAML/JSON configuration file
   * @returns {Object} Configuration parameters
   * @private
   */
  _loadConfig(configPath) {
    let config = {};
    
    // Default locations if not specified
    if (!configPath) {
      // Try standard locations
      const standardPaths = [
        './ipfs_config.yaml',
        './ipfs_config.json',
        '~/.ipfs_kit/config.yaml',
        '~/.ipfs_kit/config.json',
      ];
      
      for (const p of standardPaths) {
        const expandedPath = p.startsWith('~') 
          ? path.join(process.env.HOME, p.substring(1)) 
          : p;
          
        if (fs.existsSync(expandedPath)) {
          configPath = expandedPath;
          break;
        }
      }
    }
    
    // Load from file if available
    if (configPath && fs.existsSync(configPath)) {
      try {
        const content = fs.readFileSync(configPath, 'utf8');
        
        if (configPath.endsWith('.yaml') || configPath.endsWith('.yml')) {
          config = yaml.load(content);
        } else {
          config = JSON.parse(content);
        }
      } catch (error) {
        console.error(`Error loading configuration from ${configPath}: ${error.message}`);
        config = {};
      }
    }
    
    return config;
  }
  
  /**
   * Make an API request.
   * 
   * @param {string} method - Method name
   * @param {Array} args - Positional arguments
   * @param {Object} kwargs - Keyword arguments
   * @returns {Promise<Object>} API response
   * @private
   */
  async _request(method, args = [], kwargs = {}) {
    try {
      const response = await this.client.post(`/api/${method}`, {
        args,
        kwargs,
      });
      
      return response.data;
    } catch (error) {
      if (error.response) {
        throw new Error(`API error: ${error.response.data.message || error.response.statusText}`);
      } else if (error.request) {
        throw new Error('No response from server');
      } else {
        throw new Error(`Request error: ${error.message}`);
      }
    }
  }
""")
        
            # Add methods
            for method in methods:
                # Skip internal methods and non-API methods
                if method["name"] in ["generate_sdk", "_generate_python_sdk", "_generate_javascript_sdk", "_generate_rust_sdk"]:
                    continue
                    
                # Convert Python docstring to JSDoc
                docstring = method["doc"].strip()
                docstring = docstring.replace("Args:", "@param")
                docstring = docstring.replace("Returns:", "@returns")
                
                f.write(f"""
  /**
   * {docstring}
   */
  async {method["name"]}(...args) {{
    // Extract kwargs if last argument is an object
    let kwargs = {{}};
    if (args.length > 0 && typeof args[args.length - 1] === 'object') {{
      kwargs = args.pop();
    }}
    
    return this._request('{method["name"]}', args, kwargs);
  }}
""")
            
            f.write("""
}

module.exports = { IPFSClient };
""")
        
        # Create README.md
        with open(os.path.join(sdk_path, "README.md"), "w") as f:
            f.write("""# IPFS Kit JavaScript SDK

This SDK provides a simplified interface to IPFS Kit.

## Installation

```bash
npm install ipfs-kit-sdk
```

## Usage

```javascript
const { IPFSClient } = require('ipfs-kit-sdk');

// Initialize client
const client = new IPFSClient();

// Add content to IPFS
async function addContent() {
  try {
    const result = await client.add("Hello, IPFS!");
    console.log(`Added content with CID: ${result.cid}`);
    
    // Get content from IPFS
    const content = await client.get(result.cid);
    console.log(`Retrieved content: ${content}`);
  } catch (error) {
    console.error(error);
  }
}

addContent();
```

## Configuration

You can configure the client with a YAML or JSON file:

```yaml
# config.yaml
apiUrl: "http://localhost:8000"
timeouts:
  api: 30
  gateway: 60
```

```javascript
const client = new IPFSClient({ configPath: "config.yaml" });
```

Or with parameters:

```javascript
const client = new IPFSClient({ apiUrl: "http://localhost:8000" });
```

## Available Methods

""")
            
            # Add method documentation
            for method in methods:
                # Skip internal methods and non-API methods
                if method["name"] in ["generate_sdk", "_generate_python_sdk", "_generate_javascript_sdk", "_generate_rust_sdk"]:
                    continue
                    
                # Convert Python docstring to markdown
                docstring = method["doc"].strip()
                
                f.write(f"""### {method["name"]}

{docstring}

```javascript
const result = await client.{method["name"]}(...);
```

""")
        
        return {
            "success": True,
            "output_path": output_path,
            "language": "javascript",
            "files_generated": [
                os.path.join(sdk_path, "package.json"),
                os.path.join(sdk_path, "src", "index.js"),
                os.path.join(sdk_path, "README.md"),
            ]
        }
    
    def _generate_rust_sdk(self, methods: List[Dict[str, Any]], output_path: str) -> Dict[str, Any]:
        """
        Generate Rust SDK.
        
        Args:
            methods: List of method definitions
            output_path: Output directory
                
        Returns:
            Dictionary with operation result
        """
        # Create SDK directory structure
        sdk_path = os.path.join(output_path, "ipfs-kit-sdk")
        os.makedirs(sdk_path, exist_ok=True)
        os.makedirs(os.path.join(sdk_path, "src"), exist_ok=True)
        
        # Create Cargo.toml
        with open(os.path.join(sdk_path, "Cargo.toml"), "w") as f:
            f.write("""[package]
name = "ipfs-kit-sdk"
version = "0.1.0"
edition = "2021"
authors = ["IPFS Kit Team"]
description = "SDK for IPFS Kit"
license = "MIT"
repository = "https://github.com/example/ipfs-kit-sdk"

[dependencies]
reqwest = { version = "0.11", features = ["json"] }
tokio = { version = "1", features = ["full"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
serde_yaml = "0.9"
anyhow = "1.0"
thiserror = "1.0"
async-trait = "0.1"
bytes = "1.4"
[dev-dependencies]
tokio-test = "0.4"
""")
        
        # Create src/lib.rs
        with open(os.path.join(sdk_path, "src", "lib.rs"), "w") as f:
            f.write("""//! IPFS Kit Rust SDK.
//!
//! This SDK provides a simplified interface to IPFS Kit.

use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Error type for IPFS Kit SDK.
#[derive(Error, Debug)]
pub enum IPFSError {
    /// Network error.
    #[error("Network error: {0}")]
    Network(#[from] reqwest::Error),
    
    /// Configuration error.
    #[error("Configuration error: {0}")]
    Config(String),
    
    /// API error.
    #[error("API error: {0}")]
    Api(String),
    
    /// IO error.
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    
    /// Serialization error.
    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),
    
    /// YAML parsing error.
    #[error("YAML parsing error: {0}")]
    Yaml(#[from] serde_yaml::Error),
}

/// Configuration for IPFS Kit client.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    /// API URL.
    #[serde(default = "default_api_url")]
    pub api_url: String,
    
    /// Timeouts.
    #[serde(default)]
    pub timeouts: Timeouts,
}

/// Timeout configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Timeouts {
    /// API timeout in seconds.
    #[serde(default = "default_api_timeout")]
    pub api: u64,
    
    /// Gateway timeout in seconds.
    #[serde(default = "default_gateway_timeout")]
    pub gateway: u64,
}

fn default_api_url() -> String {
    "http://localhost:8000".to_string()
}

fn default_api_timeout() -> u64 {
    30
}

fn default_gateway_timeout() -> u64 {
    60
}

impl Default for Config {
    fn default() -> Self {
        Self {
            api_url: default_api_url(),
            timeouts: Timeouts::default(),
        }
    }
}

impl Default for Timeouts {
    fn default() -> Self {
        Self {
            api: default_api_timeout(),
            gateway: default_gateway_timeout(),
        }
    }
}

/// Request for API method call.
#[derive(Debug, Serialize)]
struct ApiRequest {
    /// Positional arguments.
    args: Vec<serde_json::Value>,
    
    /// Keyword arguments.
    kwargs: HashMap<String, serde_json::Value>,
}

/// Client for IPFS Kit.
#[derive(Debug, Clone)]
pub struct IPFSClient {
    /// Configuration.
    config: Config,
    
    /// HTTP client.
    client: Client,
}

impl IPFSClient {
    /// Create a new IPFS Kit client with default configuration.
    pub fn new() -> Result<Self> {
        Self::with_config(Config::default())
    }
    
    /// Create a new IPFS Kit client with custom configuration.
    pub fn with_config(config: Config) -> Result<Self> {
        let client = Client::builder()
            .timeout(std::time::Duration::from_secs(config.timeouts.api))
            .build()
            .context("Failed to create HTTP client")?;
        
        Ok(Self { config, client })
    }
    
    /// Load configuration from a file.
    pub fn from_file<P: AsRef<Path>>(path: P) -> Result<Self> {
        let path = path.as_ref();
        let content = fs::read_to_string(path)
            .with_context(|| format!("Failed to read config file: {}", path.display()))?;
        
        let config = if path.extension().and_then(|e| e.to_str()) == Some("yaml")
            || path.extension().and_then(|e| e.to_str()) == Some("yml")
        {
            serde_yaml::from_str(&content)
                .with_context(|| format!("Failed to parse YAML config: {}", path.display()))?
        } else {
            serde_json::from_str(&content)
                .with_context(|| format!("Failed to parse JSON config: {}", path.display()))?
        };
        
        Self::with_config(config)
    }
    
    /// Load configuration from standard locations.
    pub fn from_standard_locations() -> Result<Self> {
        let standard_paths = [
            "ipfs_config.yaml",
            "ipfs_config.json",
            "~/.ipfs_kit/config.yaml",
            "~/.ipfs_kit/config.json",
        ];
        
        for path_str in &standard_paths {
            let path = if path_str.starts_with("~/") {
                if let Some(home) = dirs::home_dir() {
                    home.join(&path_str[2..])
                } else {
                    continue;
                }
            } else {
                PathBuf::from(path_str)
            };
            
            if path.exists() {
                return Self::from_file(path);
            }
        }
        
        // Fall back to default configuration
        Self::new()
    }
    
    /// Make an API request.
    async fn request(
        &self,
        method: &str,
        args: Vec<serde_json::Value>,
        kwargs: HashMap<String, serde_json::Value>,
    ) -> Result<serde_json::Value> {
        let url = format!("{}/api/{}", self.config.api_url, method);
        
        let request = ApiRequest { args, kwargs };
        
        let response = self
            .client
            .post(&url)
            .json(&request)
            .send()
            .await
            .with_context(|| format!("Failed to send request to {}", url))?;
        
        if !response.status().is_success() {
            let status = response.status();
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
                
            return Err(IPFSError::Api(format!(
                "API error ({}): {}",
                status, error_text
            ))
            .into());
        }
        
        let result = response
            .json()
            .await
            .context("Failed to parse API response")?;
            
        Ok(result)
    }
""")
            
            # Add methods
            for method in methods:
                # Skip internal methods and non-API methods
                if method["name"] in ["generate_sdk", "_generate_python_sdk", "_generate_javascript_sdk", "_generate_rust_sdk"]:
                    continue
                    
                # Convert method name to snake_case
                rust_method_name = ''.join(['_' + c.lower() if c.isupper() else c for c in method["name"]]).lstrip('_')
                
                # Parse signature to extract parameters
                signature = method["signature"].strip('()')
                params = []
                for param in signature.split(','):
                    if '=' in param:
                        name, default = param.split('=', 1)
                        params.append((name.strip(), default.strip()))
                    elif param.strip():
                        params.append((param.strip(), None))
                
                # Convert Python docstring to Rust doc comment
                doclines = []
                for line in method["doc"].strip().split('\n'):
                    doclines.append(f"    /// {line}")
                docstring = '\n'.join(doclines)
                
                f.write(f"""
{docstring}
    pub async fn {rust_method_name}(
        &self,
        // Parameters would go here in a real implementation
    ) -> Result<serde_json::Value> {{
        let args = vec![];
        let mut kwargs = HashMap::new();
        
        // Add parameters to args or kwargs as appropriate
        
        self.request("{method["name"]}", args, kwargs).await
    }}
""")
            
            f.write("""
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_client_creation() {
        let client = IPFSClient::new().unwrap();
        assert_eq!(client.config.api_url, "http://localhost:8000");
    }
    
    // Add more tests as needed
}
""")
        
        # Create README.md
        with open(os.path.join(sdk_path, "README.md"), "w") as f:
            f.write("""# IPFS Kit Rust SDK

This SDK provides a simplified interface to IPFS Kit.

## Installation

Add this to your `Cargo.toml`:

```toml
[dependencies]
ipfs-kit-sdk = "0.1.0"
```

## Usage

```rust
use ipfs_kit_sdk::IPFSClient;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize client
    let client = IPFSClient::new()?;
    
    // Add content to IPFS
    let result = client.add("Hello, IPFS!").await?;
    println!("Added content with CID: {}", result["cid"]);
    
    // Get content from IPFS
    let content = client.get(&result["cid"].as_str().unwrap()).await?;
    println!("Retrieved content: {}", content);
    
    Ok(())
}
```

## Configuration

You can configure the client with a YAML or JSON file:

```yaml
# config.yaml
api_url: "http://localhost:8000"
timeouts:
  api: 30
  gateway: 60
```

```rust
let client = IPFSClient::from_file("config.yaml")?;
```

Or with custom configuration:

```rust
use ipfs_kit_sdk::{Config, IPFSClient, Timeouts};

let config = Config {
    api_url: "http://localhost:8000".to_string(),
    timeouts: Timeouts {
        api: 30,
        gateway: 60,
    },
};

let client = IPFSClient::with_config(config)?;
```

## Available Methods

""")
            
            # Add method documentation
            for method in methods:
                # Skip internal methods and non-API methods
                if method["name"] in ["generate_sdk", "_generate_python_sdk", "_generate_javascript_sdk", "_generate_rust_sdk"]:
                    continue
                    
                # Convert method name to snake_case
                rust_method_name = ''.join(['_' + c.lower() if c.isupper() else c for c in method["name"]]).lstrip('_')
                
                # Convert Python docstring to markdown
                docstring = method["doc"].strip()
                
                f.write(f"""### {rust_method_name}

{docstring}

```rust
let result = client.{rust_method_name}(...).await?;
```

""")
        
        return {
            "success": True,
            "output_path": output_path,
            "language": "rust",
            "files_generated": [
                os.path.join(sdk_path, "Cargo.toml"),
                os.path.join(sdk_path, "src", "lib.rs"),
                os.path.join(sdk_path, "README.md"),
            ]
        }
    
    def save_config(self, config_path: str) -> Dict[str, Any]:
        """
        Save current configuration to file.
        
        Args:
            config_path: Path to save configuration
                
        Returns:
            Dictionary with operation result
        """
        config_path = os.path.expanduser(config_path)
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            # Save configuration
            with open(config_path, 'w') as f:
                if config_path.endswith(('.yaml', '.yml')):
                    yaml.dump(self.config, f, default_flow_style=False)
                else:
                    json.dump(self.config, f, indent=2)
                    
            return {
                "success": True,
                "path": config_path,
                "message": f"Configuration saved to {config_path}"
            }
        except Exception as e:
            return {
                "success": False,
                "path": config_path,
                "error": str(e),
                "message": f"Failed to save configuration to {config_path}: {e}"
            }


class PluginBase:
    """
    Base class for plugins.
    
    All plugins should inherit from this class and implement
    their functionality as methods.
    """
    
    def __init__(self, ipfs_kit, config=None):
        """
        Initialize the plugin.
        
        Args:
            ipfs_kit: IPFS Kit instance
            config: Plugin configuration
        """
        self.ipfs_kit = ipfs_kit
        self.config = config or {}
    
    def get_name(self):
        """
        Get the plugin name.
        
        Returns:
            Plugin name
        """
        return self.__class__.__name__


# Create a singleton instance for easy import
ipfs = IPFSSimpleAPI()
