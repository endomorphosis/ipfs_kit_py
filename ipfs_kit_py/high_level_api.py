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

import importlib
import inspect
import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path
from io import IOBase
from typing import Any, BinaryIO, Callable, Dict, List, Optional, Tuple, Union, TypeVar, Literal

import yaml

# Internal imports
try:
    # First try relative imports (when used as a package)
    from .error import IPFSConfigurationError, IPFSError, IPFSValidationError
    from .ipfs_kit import IPFSKit, ipfs_kit  # Import both the function and the class
    from .validation import validate_parameters

    # Try to import FSSpec integration
    try:
        from .ipfs_fsspec import HAVE_FSSPEC, IPFSFileSystem
    except ImportError:
        HAVE_FSSPEC = False
except ImportError:
    # For development/testing
    import os
    import sys

    # Add parent directory to path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from ipfs_kit_py.error import IPFSConfigurationError, IPFSError, IPFSValidationError
    from ipfs_kit_py.ipfs_kit import IPFSKit, ipfs_kit  # Import both the function and the class
    from ipfs_kit_py.validation import validate_parameters

    # Try to import FSSpec integration
    try:
        from ipfs_kit_py.ipfs_fsspec import HAVE_FSSPEC, IPFSFileSystem
    except ImportError:
        HAVE_FSSPEC = False

# Optional imports
try:
    from . import ai_ml_integration

    AI_ML_AVAILABLE = True
except ImportError:
    AI_ML_AVAILABLE = False

try:
    from . import integrated_search

    INTEGRATED_SEARCH_AVAILABLE = True
except ImportError:
    INTEGRATED_SEARCH_AVAILABLE = False

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

        self.kit = ipfs_kit(resources=resources, metadata=metadata)

        # Ensure ipfs_add_file method is available
        if not hasattr(self.kit, "ipfs_add_file"):
            # Add the method if it doesn't exist
            def ipfs_add_file(file_path, **kwargs):
                """Add a file to IPFS."""
                if not hasattr(self.kit, "ipfs"):
                    return {"success": False, "error": "IPFS instance not initialized"}
                return self.kit.ipfs.add(file_path, **kwargs)

            # Add the method to the kit instance
            self.kit.ipfs_add_file = ipfs_add_file

        # Initialize filesystem access through the get_filesystem method
        self.fs = self.get_filesystem()

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
                with open(expanded_path, "r") as f:
                    if expanded_path.endswith((".yaml", ".yml")):
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
                    ipfs_kit=self.kit, config=plugin_config.get("config", {})
                )

                # Register plugin
                self.plugins[plugin_name] = plugin_instance

                # Register plugin methods as extensions
                for method_name, method in inspect.getmembers(
                    plugin_instance, predicate=inspect.ismethod
                ):
                    if not method_name.startswith("_"):  # Only public methods
                        self.extensions[f"{plugin_name}.{method_name}"] = method

                logger.info(f"Plugin {plugin_name} loaded successfully")

            except Exception as e:
                logger.error(f"Error loading plugin {plugin_name} from {plugin_path}: {e}")

    def register_extension(
        self, 
        name: str, 
        func: Callable,
        *,
        overwrite: bool = True
    ) -> Dict[str, Any]:
        """
        Register a custom extension function.

        Args:
            name: Name of the extension to register
            func: Function to register as an extension
            overwrite: Whether to overwrite an existing extension with the same name

        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the registration succeeded
                - "name": The name of the registered extension
                - "exists": Whether the extension was already registered
                - "overwritten": Whether an existing extension was overwritten

        Raises:
            IPFSValidationError: If overwrite is False and extension already exists
        """
        result = {
            "success": False,
            "name": name,
            "exists": name in self.extensions,
            "overwritten": False
        }
        
        if name in self.extensions and not overwrite:
            raise IPFSValidationError(f"Extension {name} already exists and overwrite=False")
            
        if name in self.extensions:
            result["overwritten"] = True
            
        self.extensions[name] = func
        logger.info(f"Extension {name} registered")
        
        result["success"] = True
        return result

    def get_filesystem(
        self, 
        *,
        gateway_urls: Optional[List[str]] = None,
        use_gateway_fallback: Optional[bool] = None, 
        gateway_only: Optional[bool] = None,
        cache_config: Optional[Dict[str, Any]] = None,
        enable_metrics: Optional[bool] = None,
        **kwargs
    ) -> Optional["IPFSFileSystem"]:
        """
        Get an FSSpec-compatible filesystem for IPFS.

        This method returns a filesystem object that implements the fsspec interface,
        allowing standard filesystem operations on IPFS content.

        Args:
            gateway_urls: List of IPFS gateway URLs to use (e.g., ["https://ipfs.io", "https://cloudflare-ipfs.com"])
            use_gateway_fallback: Whether to use gateways as fallback when local daemon is unavailable
            gateway_only: Whether to use only gateways (no local daemon)
            cache_config: Configuration for the cache system (dict with memory_size, disk_size, disk_path etc.)
            enable_metrics: Whether to enable performance metrics
            **kwargs: Additional parameters to pass to the filesystem

        Returns:
            FSSpec-compatible filesystem interface for IPFS, or None if fsspec is not available

        Raises:
            IPFSConfigurationError: If there's a problem with the configuration
        """
        if not HAVE_FSSPEC:
            logger.warning(
                "FSSpec is not available. Please install fsspec to use the filesystem interface."
            )
            return None

        # Prepare configuration from both config and kwargs
        fs_kwargs = {}

        # Add configuration from self.config with kwargs taking precedence
        if "ipfs_path" in kwargs:
            fs_kwargs["ipfs_path"] = kwargs["ipfs_path"]
        elif "ipfs_path" in self.config:
            fs_kwargs["ipfs_path"] = self.config["ipfs_path"]

        if "socket_path" in kwargs:
            fs_kwargs["socket_path"] = kwargs["socket_path"]
        elif "socket_path" in self.config:
            fs_kwargs["socket_path"] = self.config["socket_path"]

        if "role" in kwargs:
            fs_kwargs["role"] = kwargs["role"]
        else:
            fs_kwargs["role"] = self.config.get("role", "leecher")

        # Add cache configuration if provided
        if "cache_config" in kwargs:
            fs_kwargs["cache_config"] = kwargs["cache_config"]
        elif "cache" in self.config:
            fs_kwargs["cache_config"] = self.config["cache"]

        # Add use_mmap configuration if provided
        if "use_mmap" in kwargs:
            fs_kwargs["use_mmap"] = kwargs["use_mmap"]
        else:
            fs_kwargs["use_mmap"] = self.config.get("use_mmap", True)

        # Add metrics configuration if provided
        if "enable_metrics" in kwargs:
            fs_kwargs["enable_metrics"] = kwargs["enable_metrics"]
        else:
            fs_kwargs["enable_metrics"] = self.config.get("enable_metrics", True)

        # Add gateway configuration if provided
        if "gateway_urls" in kwargs:
            fs_kwargs["gateway_urls"] = kwargs["gateway_urls"]
        elif "gateway_urls" in self.config:
            fs_kwargs["gateway_urls"] = self.config["gateway_urls"]

        # Add gateway fallback configuration if provided
        if "use_gateway_fallback" in kwargs:
            fs_kwargs["use_gateway_fallback"] = kwargs["use_gateway_fallback"]
        elif "use_gateway_fallback" in self.config:
            fs_kwargs["use_gateway_fallback"] = self.config["use_gateway_fallback"]

        # Add gateway-only mode configuration if provided
        if "gateway_only" in kwargs:
            fs_kwargs["gateway_only"] = kwargs["gateway_only"]
        elif "gateway_only" in self.config:
            fs_kwargs["gateway_only"] = self.config["gateway_only"]

        try:
            # Create the filesystem
            filesystem = IPFSFileSystem(**fs_kwargs)
            logger.info("IPFSFileSystem initialized successfully")
            return filesystem
        except Exception as e:
            logger.error(f"Failed to initialize IPFSFileSystem: {e}")
            return None

    def add(
        self, 
        content: Union[bytes, str, Path, 'BinaryIO'],
        *,
        pin: bool = True,
        wrap_with_directory: bool = False, 
        chunker: str = "size-262144",
        hash: str = "sha2-256",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Add content to IPFS.
        
        This method adds content to IPFS and returns the content identifier (CID)
        along with additional metadata about the operation.

        Args:
            content: Content to add, which can be:
                - bytes: Raw binary data
                - str: Text content or a file path
                - Path: A Path object pointing to a file
                - BinaryIO: A file-like object opened in binary mode
            pin: Whether to pin the content to ensure persistence
            wrap_with_directory: Whether to wrap the content in a directory
            chunker: Chunking algorithm used to split content
                Valid options include: "size-262144", "rabin", "rabin-min-size-X"
            hash: Hashing algorithm used for content addressing
                Valid options include: "sha2-256", "sha2-512", "sha3-512", "blake2b-256"
            **kwargs: Additional implementation-specific parameters

        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "cid": The content identifier of the added content
                - "size": Size of the content in bytes
                - "name": Original filename if a file was added
                - "hash": The full multihash of the content
                - "timestamp": When the content was added
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon fails
            IPFSAddError: If the content cannot be added
            IPFSTimeoutError: If the operation times out
            IPFSValidationError: If parameters are invalid
        """
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "pin": pin,
            "wrap_with_directory": wrap_with_directory,
            "chunker": chunker,
            "hash": hash,
            **kwargs  # Any additional kwargs override the defaults
        }

        # Handle different content types
        if isinstance(content, (str, bytes, Path)) and os.path.exists(str(content)):
            # It's a file path
            # Need to pass as a positional argument, not named parameter
            kwargs_copy = kwargs_with_defaults.copy()
            result = self.kit.ipfs_add_file(str(content), **kwargs_copy)
        elif isinstance(content, str):
            # It's a string - create a temporary file and add it
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(content.encode("utf-8"))
                temp_file_path = temp_file.name
            try:
                # Need to pass as a positional argument, not named parameter
                kwargs_copy = kwargs_with_defaults.copy()
                result = self.kit.ipfs_add_file(temp_file_path, **kwargs_copy)
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
                kwargs_copy = kwargs_with_defaults.copy()
                result = self.kit.ipfs_add_file(temp_file_path, **kwargs_copy)
            finally:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
        elif hasattr(content, "read"):
            # It's a file-like object - read it and add as bytes
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(content.read())
                temp_file_path = temp_file.name
            try:
                # Need to pass as a positional argument, not named parameter
                kwargs_copy = kwargs_with_defaults.copy()
                result = self.kit.ipfs_add_file(temp_file_path, **kwargs_copy)
            finally:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
        else:
            raise IPFSValidationError(f"Unsupported content type: {type(content)}")

        return result

    def get(
        self, 
        cid: str, 
        *, 
        timeout: Optional[int] = None,
        **kwargs
    ) -> bytes:
        """
        Get content from IPFS by CID.
        
        This method retrieves content from IPFS using its content identifier (CID).
        It attempts to fetch the content from the local node first, and if not available,
        it will fetch from the IPFS network.

        Args:
            cid: Content identifier (CID) in any valid format (v0 or v1)
            timeout: Maximum time in seconds to wait for content retrieval
                If None, the default timeout from config will be used
            **kwargs: Additional implementation-specific parameters
                
        Returns:
            bytes: The raw content data

        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon fails
            IPFSContentNotFoundError: If the content cannot be found
            IPFSTimeoutError: If the operation times out
            IPFSValidationError: If the CID format is invalid
        """
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "timeout": timeout if timeout is not None else self.config.get("timeouts", {}).get("api", 30),
            **kwargs  # Any additional kwargs override the defaults
        }

        result = self.kit.ipfs_cat(cid=cid, **kwargs_with_defaults)

        # If result is a dictionary, try to extract content
        if isinstance(result, dict):
            if "data" in result:
                return result["data"]
            elif "content" in result:
                return result["content"]
            elif "success" in result and result["success"] and "value" in result:
                return result["value"]
            else:
                # Could not extract bytes, return original result as bytes if possible
                try:
                    import json

                    return json.dumps(result).encode("utf-8")
                except:
                    # Last resort, convert to string and encode
                    return str(result).encode("utf-8")

        # Convert non-bytes to bytes if needed
        if not isinstance(result, bytes):
            try:
                return str(result).encode("utf-8")
            except:
                return b"Unable to convert result to bytes"

        # Already bytes
        return result

    def pin(
        self, 
        cid: str, 
        *, 
        recursive: bool = True,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Pin content to the local IPFS node.
        
        Pinning prevents content from being garbage-collected and ensures
        it persists in the local IPFS repository even if not recently used.

        Args:
            cid: Content identifier (CID) to pin
            recursive: Whether to recursively pin the entire DAG
                When True (default), pins the entire DAG under this CID
                When False, pins only the direct block
            timeout: Maximum time in seconds to wait for the pin operation
                If None, the default timeout from config will be used
            **kwargs: Additional implementation-specific parameters
                
        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "cid": The content identifier that was pinned
                - "pins": List of CIDs that were pinned (when recursive=True)
                - "timestamp": When the content was pinned
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon fails
            IPFSPinningError: If the content cannot be pinned
            IPFSTimeoutError: If the operation times out
            IPFSValidationError: If the CID format is invalid
        """
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "recursive": recursive,
            "timeout": timeout if timeout is not None else self.config.get("timeouts", {}).get("api", 30),
            **kwargs  # Any additional kwargs override the defaults
        }

        return self.kit.ipfs_pin_add(cid, **kwargs_with_defaults)

    def unpin(
        self, 
        cid: str, 
        *, 
        recursive: bool = True,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Unpin content from the local IPFS node.
        
        Unpinning allows content to be garbage-collected if not otherwise referenced,
        freeing up space in the repository.

        Args:
            cid: Content identifier (CID) to unpin
            recursive: Whether to recursively unpin the entire DAG
                When True (default), unpins the entire DAG under this CID
                When False, unpins only the direct block
            timeout: Maximum time in seconds to wait for the unpin operation
                If None, the default timeout from config will be used
            **kwargs: Additional implementation-specific parameters
                
        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "cid": The content identifier that was unpinned
                - "timestamp": When the content was unpinned
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon fails
            IPFSPinningError: If the content cannot be unpinned
            IPFSTimeoutError: If the operation times out
            IPFSValidationError: If the CID format is invalid
            IPFSContentNotFoundError: If the CID is not pinned
        """
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "recursive": recursive,
            "timeout": timeout if timeout is not None else self.config.get("timeouts", {}).get("api", 30),
            **kwargs  # Any additional kwargs override the defaults
        }

        return self.kit.ipfs_pin_rm(cid, **kwargs_with_defaults)

    def list_pins(
        self, 
        *, 
        type: str = "all",
        quiet: bool = False,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        List pinned content in the local IPFS node.
        
        This method retrieves information about content that is currently pinned
        in the IPFS repository.

        Args:
            type: Type of pins to list 
                Options are:
                - "direct": Only direct pins
                - "recursive": Only recursive pins
                - "indirect": Only indirect pins (referenced by recursive pins)
                - "all": All pins (default)
            quiet: Whether to return only CIDs without pin types
            timeout: Maximum time in seconds to wait for the operation
                If None, the default timeout from config will be used
            **kwargs: Additional implementation-specific parameters
                
        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "pins": Dictionary mapping CIDs to pin types
                - "count": Total number of pins found
                - "timestamp": When the list was generated
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon fails
            IPFSTimeoutError: If the operation times out
        """
        # Validate pin type
        if type not in ["all", "direct", "indirect", "recursive"]:
            raise IPFSValidationError(f"Invalid pin type: {type}. Must be one of: all, direct, indirect, recursive")
            
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "type": type,
            "quiet": quiet,
            "timeout": timeout if timeout is not None else self.config.get("timeouts", {}).get("api", 30),
            **kwargs  # Any additional kwargs override the defaults
        }

        return self.kit.ipfs_pin_ls(**kwargs_with_defaults)

    def publish(
        self, 
        cid: str, 
        key: str = "self", 
        *, 
        lifetime: str = "24h",
        ttl: str = "1h",
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Publish content to IPNS (InterPlanetary Name System).
        
        IPNS allows you to create mutable pointers to IPFS content, providing
        a way to maintain the same address while updating the content it points to.

        Args:
            cid: Content identifier to publish
            key: Name of the key to use 
                - "self": Uses the node's own peer ID (default)
                - Any other named key previously generated with `ipfs key gen`
            lifetime: Time duration the record will be valid for
                Example values: "24h", "7d", "1m"
            ttl: Time duration the record should be cached
                Example values: "1h", "30m", "5m"
            timeout: Maximum time in seconds to wait for the publish operation
                If None, the default timeout from config will be used
            **kwargs: Additional implementation-specific parameters
                
        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "name": The IPNS name (a peer ID hash)
                - "value": The CID that the name points to
                - "validity": Time duration for which the record is valid
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon fails
            IPFSTimeoutError: If the operation times out
            IPFSValidationError: If parameters are invalid
            IPFSKeyError: If the specified key does not exist
        """
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "lifetime": lifetime,
            "ttl": ttl,
            "timeout": timeout if timeout is not None else self.config.get("timeouts", {}).get("api", 60),  # IPNS publishing can take longer
            **kwargs  # Any additional kwargs override the defaults
        }

        return self.kit.ipfs_name_publish(cid, key=key, **kwargs_with_defaults)

    def resolve(
        self, 
        name: str, 
        *, 
        recursive: bool = True,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Resolve IPNS name to CID.
        
        This method resolves an IPNS name (PeerID hash or domain with dnslink)
        to its current content identifier (CID).

        Args:
            name: IPNS name to resolve, which can be one of:
                - Peer ID hash (e.g., 'k51qzi5uqu5...')
                - Domain with dnslink (e.g., 'ipfs.io')
                - Path prefixed with '/ipns/' (e.g., '/ipns/ipfs.io')
            recursive: Whether to recursively resolve until finding a non-IPNS path
                When True (default), follows IPNS redirections until reaching an IPFS path
                When False, resolves only a single level of IPNS
            timeout: Maximum time in seconds to wait for the resolve operation
                If None, the default timeout from config will be used
            **kwargs: Additional implementation-specific parameters
                
        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "path": The resolved path (typically an /ipfs/ path)
                - "value": The resolved CID or content path
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon fails
            IPFSTimeoutError: If the operation times out
            IPFSValidationError: If the name format is invalid
            IPFSNameResolutionError: If the name cannot be resolved
        """
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "recursive": recursive,
            "timeout": timeout if timeout is not None else self.config.get("timeouts", {}).get("api", 30),
            **kwargs  # Any additional kwargs override the defaults
        }

        return self.kit.ipfs_name_resolve(name, **kwargs_with_defaults)

    def connect(
        self, 
        peer: str, 
        *, 
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Connect to a peer on the IPFS network.
        
        This method establishes a direct connection to a peer using its multiaddress.
        
        Args:
            peer: Peer multiaddress in the format:
                - "/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ"
                - "/dns4/example.com/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ"
            timeout: Maximum time in seconds to wait for the connection operation
                If None, the default timeout from config will be used
            **kwargs: Additional implementation-specific parameters
                
        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "peer": The peer ID that was connected to
                - "addresses": List of addresses that were connected to
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to the peer fails
            IPFSTimeoutError: If the operation times out
            IPFSValidationError: If the multiaddress format is invalid
        """
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "timeout": timeout if timeout is not None else self.config.get("timeouts", {}).get("peer_connect", 30),
            **kwargs  # Any additional kwargs override the defaults
        }

        return self.kit.ipfs_swarm_connect(peer, **kwargs_with_defaults)

    def peers(
        self, 
        *, 
        verbose: bool = False,
        latency: bool = False,
        direction: bool = False,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        List peers currently connected to the local IPFS node.
        
        This method retrieves information about peers the local node is connected to,
        including their peer IDs and connection details.

        Args:
            verbose: Whether to include additional information about peers
                When True, includes more detailed connection information
                When False (default), returns basic peer information
            latency: Whether to include latency information for each peer
                When True, measures and includes connection latency
                When False (default), omits latency information
            direction: Whether to include connection direction information
                When True, indicates whether the connection is inbound or outbound
                When False (default), omits direction information
            timeout: Maximum time in seconds to wait for the operation
                If None, the default timeout from config will be used
            **kwargs: Additional implementation-specific parameters
                
        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "peers": List of connected peers with their information
                - "count": Total number of connected peers
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon fails
            IPFSTimeoutError: If the operation times out
        """
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "verbose": verbose,
            "latency": latency,
            "direction": direction,
            "timeout": timeout if timeout is not None else self.config.get("timeouts", {}).get("api", 30),
            **kwargs  # Any additional kwargs override the defaults
        }

        return self.kit.ipfs_swarm_peers(**kwargs_with_defaults)

    def open(
        self, 
        path: str, 
        mode: str = "rb", 
        *, 
        cache: bool = True,
        size_hint: Optional[int] = None,
        **kwargs
    ) -> 'IOBase':
        """
        Open a file-like object for IPFS content.
        
        This method provides a file-like interface to IPFS content, allowing
        standard Python file operations on IPFS data.

        Args:
            path: IPFS path or CID
                Can be a raw CID (e.g., "QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")
                Or a full IPFS path (e.g., "/ipfs/QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")
            mode: File mode for opening the content
                Currently only read modes are supported: "r" (text) and "rb" (binary)
            cache: Whether to cache the content for faster repeated access
                When True (default), stores content in the tiered cache system
                When False, always fetches content from the IPFS network
            size_hint: Optional hint about the file size for optimization
                Providing this can improve performance for large files
            **kwargs: Additional parameters passed to the underlying filesystem
                
        Returns:
            IOBase: A file-like object supporting standard file operations
                For binary mode ("rb"), returns a file-like object with read() method
                For text mode ("r"), returns a file-like object with encoding support
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon fails
            IPFSTimeoutError: If the operation times out
            IPFSContentNotFoundError: If the content cannot be found
            ValueError: If an unsupported mode is specified (only read modes supported)
        """
        # Make sure path has ipfs:// prefix
        if not path.startswith(("ipfs://", "ipns://")):
            path = f"ipfs://{path}"
            
        # Get the filesystem interface
        fs = self.get_filesystem()
        if fs is None:
            raise IPFSError("Failed to initialize filesystem interface")
        
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "cache": cache,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add size hint if provided
        if size_hint is not None:
            kwargs_with_defaults["size"] = size_hint
            
        # Open the file
        return fs.open(path, mode, **kwargs_with_defaults)

    def read(
        self, 
        path: str, 
        *, 
        cache: bool = True,
        timeout: Optional[int] = None,
        **kwargs
    ) -> bytes:
        """
        Read content from IPFS path.
        
        This is a convenience method that opens a file and reads all its content at once.
        For more control over large files, use the open() method instead.

        Args:
            path: IPFS path or CID
                Can be a raw CID (e.g., "QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")
                Or a full IPFS path (e.g., "/ipfs/QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")
            cache: Whether to cache the content for faster repeated access
                When True (default), stores content in the tiered cache system
                When False, always fetches content from the IPFS network
            timeout: Maximum time in seconds to wait for the read operation
                If None, the default timeout from config will be used
            **kwargs: Additional parameters passed to the underlying filesystem
                
        Returns:
            bytes: The complete content data as bytes
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon fails
            IPFSTimeoutError: If the operation times out
            IPFSContentNotFoundError: If the content cannot be found
        """
        # Make sure path has ipfs:// prefix
        if not path.startswith(("ipfs://", "ipns://")):
            path = f"ipfs://{path}"
            
        # Get the filesystem interface
        fs = self.get_filesystem()
        if fs is None:
            raise IPFSError("Failed to initialize filesystem interface")
            
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "cache": cache,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add timeout if provided
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout
            
        # Read the content
        return fs.cat(path, **kwargs_with_defaults)

    def exists(
        self, 
        path: str, 
        *,
        timeout: Optional[int] = None,
        **kwargs
    ) -> bool:
        """
        Check if path exists in IPFS.
        
        This method verifies whether a given path or CID exists and is 
        accessible in the IPFS network.

        Args:
            path: IPFS path or CID
                Can be a raw CID (e.g., "QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")
                Or a full IPFS path (e.g., "/ipfs/QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")
            timeout: Maximum time in seconds to wait for the operation
                If None, the default timeout from config will be used
            **kwargs: Additional parameters passed to the underlying filesystem
                
        Returns:
            bool: True if path exists and is accessible, False otherwise
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon fails
            IPFSTimeoutError: If the operation times out
        """
        # Make sure path has ipfs:// prefix
        if not path.startswith(("ipfs://", "ipns://")):
            path = f"ipfs://{path}"
            
        # Get the filesystem interface
        fs = self.get_filesystem()
        if fs is None:
            raise IPFSError("Failed to initialize filesystem interface")
            
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add timeout if provided
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout
            
        # Check if path exists
        return fs.exists(path, **kwargs_with_defaults)

    def ls(
        self, 
        path: str, 
        *,
        detail: bool = True,
        timeout: Optional[int] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        List directory contents in IPFS.
        
        This method retrieves the contents of a directory in IPFS.

        Args:
            path: IPFS path or CID
                Can be a raw CID (e.g., "QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")
                Or a full IPFS path (e.g., "/ipfs/QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")
            detail: Whether to include detailed metadata for each entry
                When True (default), returns full metadata objects
                When False, returns a simplified list of names
            timeout: Maximum time in seconds to wait for the operation
                If None, the default timeout from config will be used
            **kwargs: Additional parameters passed to the underlying filesystem
                
        Returns:
            List[Dict[str, Any]]: A list of directory entries with metadata
                Each entry includes:
                - "name": Name of the entry
                - "type": Type of entry ("file", "directory", "symlink", etc.)
                - "size": Size in bytes (for files)
                - "cid": Content identifier for the entry
                - Additional metadata if detail=True
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon fails
            IPFSTimeoutError: If the operation times out
            IPFSContentNotFoundError: If the path cannot be found
            IPFSValidationError: If the path is not a directory
        """
        # Make sure path has ipfs:// prefix
        if not path.startswith(("ipfs://", "ipns://")):
            path = f"ipfs://{path}"
            
        # Get the filesystem interface
        fs = self.get_filesystem()
        if fs is None:
            raise IPFSError("Failed to initialize filesystem interface")
            
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "detail": detail,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add timeout if provided
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout
            
        # List directory contents
        return fs.ls(path, **kwargs_with_defaults)

    def cluster_add(
        self, 
        content: Union[bytes, str, Path, 'BinaryIO'],
        *, 
        replication_factor: int = -1,
        name: Optional[str] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Add content to IPFS cluster.
        
        This method adds content to IPFS through the cluster service,
        which ensures the content is replicated according to the cluster policy.

        Args:
            content: Content to add, which can be:
                - bytes: Raw binary data
                - str: Text content or a file path
                - Path: A Path object pointing to a file
                - BinaryIO: A file-like object opened in binary mode
            replication_factor: Number of nodes to replicate the content to
                Default is -1, which means replicate to all nodes in the cluster
                Value of 0 means use the cluster's default replication factor
                Positive values specify exact number of replicas
            name: Optional name to associate with the content
                Useful for identifying the content in the cluster status
            timeout: Maximum time in seconds to wait for the add operation
                If None, the default timeout from config will be used
                Note that cluster operations may take longer than regular IPFS operations
            **kwargs: Additional implementation-specific parameters
                
        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "cid": The content identifier of the added content
                - "size": Size of the content in bytes
                - "name": Original filename or provided name
                - "replication_factor": Requested replication factor
                - "allocations": List of peer IDs where content is allocated
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon or cluster fails
            IPFSClusterError: If there's an issue with the cluster operation
            IPFSTimeoutError: If the operation times out
            IPFSValidationError: If parameters are invalid
            
        Note:
            This method requires a running IPFS cluster service and the node must be
            configured as part of a cluster. It will not work on standalone IPFS nodes
            or on nodes with role="leecher".
        """
        # Only available in master or worker roles
        if self.config.get("role") == "leecher":
            raise IPFSError("Cluster operations not available in leecher role")
            
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "replication_factor": replication_factor,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add name if provided
        if name is not None:
            kwargs_with_defaults["name"] = name
            
        # Add timeout if provided
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout

        # Handle different content types as in the add method
        if isinstance(content, (str, bytes, Path)) and os.path.exists(str(content)):
            # It's a file path
            result = self.kit.cluster_add_file(str(content), **kwargs_with_defaults)
        elif isinstance(content, str):
            # It's a string
            result = self.kit.cluster_add(content.encode("utf-8"), **kwargs_with_defaults)
        elif isinstance(content, bytes):
            # It's bytes
            result = self.kit.cluster_add(content, **kwargs_with_defaults)
        elif hasattr(content, "read"):
            # It's a file-like object
            result = self.kit.cluster_add(content.read(), **kwargs_with_defaults)
        else:
            raise IPFSValidationError(f"Unsupported content type: {type(content)}")

        return result

    def cluster_pin(
        self, 
        cid: str, 
        *,
        replication_factor: int = -1,
        name: Optional[str] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Pin content to IPFS cluster.
        
        This method ensures content is pinned across the IPFS cluster according
        to the specified replication factor.

        Args:
            cid: Content identifier to pin
            replication_factor: Number of nodes to replicate the content to
                Default is -1, which means replicate to all nodes in the cluster
                Value of 0 means use the cluster's default replication factor
                Positive values specify exact number of replicas
            name: Optional name to associate with the pin
                Useful for identifying the content in the cluster status
            timeout: Maximum time in seconds to wait for the pin operation
                If None, the default timeout from config will be used
                Note that cluster operations may take longer than regular IPFS operations
            **kwargs: Additional implementation-specific parameters
                
        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "cid": The content identifier that was pinned
                - "replication_factor": Requested replication factor
                - "allocations": List of peer IDs where content is allocated
                - "status": Current status of the pin operation
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon or cluster fails
            IPFSClusterError: If there's an issue with the cluster operation
            IPFSTimeoutError: If the operation times out
            IPFSValidationError: If the CID format is invalid
            
        Note:
            This method requires a running IPFS cluster service and the node must be
            configured as part of a cluster. It will not work on standalone IPFS nodes
            or on nodes with role="leecher".
        """
        # Only available in master or worker roles
        if self.config.get("role") == "leecher":
            raise IPFSError("Cluster operations not available in leecher role")
            
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "replication_factor": replication_factor,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add name if provided
        if name is not None:
            kwargs_with_defaults["name"] = name
            
        # Add timeout if provided
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout

        return self.kit.cluster_pin_add(cid, **kwargs_with_defaults)

    def cluster_status(
        self, 
        cid: Optional[str] = None, 
        *,
        local: bool = False,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get cluster pin status for one or all pinned items.
        
        This method retrieves the status of pins in the IPFS cluster, showing
        which nodes have successfully pinned each content item.

        Args:
            cid: Content identifier to check status for
                If None (default), returns status for all pins in the cluster
            local: Whether to show only the local peer status
                When True, only returns status for the current node
                When False (default), returns status across all cluster nodes
            timeout: Maximum time in seconds to wait for the status operation
                If None, the default timeout from config will be used
            **kwargs: Additional implementation-specific parameters
                
        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "status": Status information for pins
                    - If cid is provided: detailed status for that CID
                    - If cid is None: map of CIDs to their status information
                - "peer_count": Number of peers in the cluster
                - "cid_count": Number of CIDs with status
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon or cluster fails
            IPFSClusterError: If there's an issue with the cluster operation
            IPFSTimeoutError: If the operation times out
            IPFSValidationError: If the CID format is invalid (when provided)
            
        Note:
            This method requires a running IPFS cluster service and the node must be
            configured as part of a cluster. It will not work on standalone IPFS nodes
            or on nodes with role="leecher".
        """
        # Only available in master or worker roles
        if self.config.get("role") == "leecher":
            raise IPFSError("Cluster operations not available in leecher role")
            
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "local": local,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add timeout if provided
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout
            
        # Call the appropriate method based on whether a CID was provided
        if cid:
            return self.kit.cluster_status(cid, **kwargs_with_defaults)
        else:
            return self.kit.cluster_status_all(**kwargs_with_defaults)

    def cluster_peers(
        self, 
        *,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        List all peers in the IPFS cluster.
        
        This method retrieves information about all peers that are part of the
        IPFS cluster, including their connection status and metadata.

        Args:
            timeout: Maximum time in seconds to wait for the operation
                If None, the default timeout from config will be used
            **kwargs: Additional implementation-specific parameters
                
        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "peers": List of peer information including:
                    - "id": Peer ID
                    - "addresses": List of multiaddresses for the peer
                    - "name": Peer name if available
                    - "version": Peer software version
                    - "cluster_peers": List of other peers this peer is connected to
                - "peer_count": Total number of peers in the cluster
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon or cluster fails
            IPFSClusterError: If there's an issue with the cluster operation
            IPFSTimeoutError: If the operation times out
            
        Note:
            This method requires a running IPFS cluster service and the node must be
            configured as part of a cluster. It will not work on standalone IPFS nodes
            or on nodes with role="leecher".
        """
        # Only available in master or worker roles
        if self.config.get("role") == "leecher":
            raise IPFSError("Cluster operations not available in leecher role")
            
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add timeout if provided
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout
            
        return self.kit.cluster_peers(**kwargs_with_defaults)

    def ai_model_add(
        self, 
        model: Union[str, Path, bytes, object], 
        metadata: Optional[Dict[str, Any]] = None, 
        *,
        pin: bool = True,
        replicate: bool = False,
        framework: Optional[str] = None,
        version: Optional[str] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Add a machine learning model to the registry.
        
        This method stores ML models in IPFS with appropriate metadata for 
        later retrieval and use. Models can be serialized files, directory 
        structures, or in-memory model objects depending on the framework.

        Args:
            model: The model to add, which can be:
                - str: Path to model file or directory
                - Path: Path object pointing to model file or directory
                - bytes: Serialized model data
                - object: In-memory model object (framework-specific)
            metadata: Model metadata dictionary with information like:
                - "name": Model name
                - "description": Model description
                - "tags": List of tags for categorization
                - "license": License information
                - "source": Where the model came from
                - "metrics": Performance metrics
                - Any other custom fields for your workflow
            pin: Whether to pin the model to ensure it persists
                When True (default), pins the model to the local node
                When False, the model may be garbage collected eventually
            replicate: Whether to replicate the model to the cluster
                When True, uses cluster pinning to distribute the model
                When False (default), stores only on the local node
            framework: The ML framework the model belongs to
                Examples: "pytorch", "tensorflow", "sklearn", "onnx"
                If None, attempts to detect from the model object
            version: Version string for the model
                If None, uses current timestamp as version
            timeout: Maximum time in seconds to wait for the operation
                If None, the default timeout from config will be used
                Note that model storage can take longer than regular content
            **kwargs: Additional implementation-specific parameters
                
        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "model_cid": The content identifier for the model
                - "metadata_cid": The content identifier for the metadata
                - "registry_cid": The content identifier for the registry entry
                - "size": Total size of the model in bytes
                - "framework": The framework detected or specified
                - "version": The version used for this model
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon fails
            IPFSTimeoutError: If the operation times out
            IPFSValidationError: If parameters are invalid
            IPFSAIError: If there's an issue with the AI/ML operation
            
        Note:
            Different ML frameworks may have specific serialization requirements.
            For PyTorch, the model should be saved with torch.save().
            For TensorFlow, models should be in SavedModel format.
            For scikit-learn, models should be pickled or joblib dumps.
        """
        if not AI_ML_AVAILABLE:
            raise IPFSError("AI/ML integration not available")
            
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "pin": pin,
            "replicate": replicate,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add framework if provided
        if framework is not None:
            kwargs_with_defaults["framework"] = framework
            
        # Add version if provided
        if version is not None:
            kwargs_with_defaults["version"] = version
            
        # Add timeout if provided
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout
            
        return self.kit.ai_model_add(model, metadata, **kwargs_with_defaults)

    def ai_model_get(
        self, 
        model_id: str, 
        *, 
        local_only: bool = False,
        load_to_memory: bool = True,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get a machine learning model from the registry.
        
        This method retrieves a previously stored ML model and its metadata
        from IPFS, optionally loading it into memory as a usable model object.

        Args:
            model_id: Model identifier (CID or registry reference)
                Can be the direct CID of the model
                Or a model name/version combination from the registry
            local_only: Whether to only check the local node for the model
                When True, only returns the model if available locally
                When False (default), retrieves from the network if needed
            load_to_memory: Whether to load the model into memory
                When True (default), deserializes the model into a usable object
                When False, returns paths to the model files without loading
            timeout: Maximum time in seconds to wait for the operation
                If None, the default timeout from config will be used
                Note that large models may take longer to retrieve
            **kwargs: Additional implementation-specific parameters
                
        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "model": The deserialized model object (if load_to_memory=True)
                - "model_path": Path to the downloaded model files (if load_to_memory=False)
                - "metadata": Model metadata including framework, version, etc.
                - "size": Size of the model in bytes
                - "framework": The ML framework the model belongs to
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon fails
            IPFSTimeoutError: If the operation times out
            IPFSContentNotFoundError: If the model cannot be found
            IPFSAIError: If there's an issue with the AI/ML operation
            
        Note:
            Different ML frameworks may have specific deserialization requirements.
            For PyTorch, the model will be loaded using torch.load().
            For TensorFlow, SavedModel format will be loaded.
            For scikit-learn, models will be unpickled from joblib or pickle formats.
        """
        if not AI_ML_AVAILABLE:
            raise IPFSError("AI/ML integration not available")
            
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "local_only": local_only,
            "load_to_memory": load_to_memory,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add timeout if provided
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout
            
        return self.kit.ai_model_get(model_id, **kwargs_with_defaults)

    def ai_dataset_add(
        self, 
        dataset: Union[str, Path, Dict[str, Any], "DataFrame", "Dataset"],
        *,
        metadata: Optional[Dict[str, Any]] = None,
        pin: bool = True,
        replicate: bool = False,
        format: Optional[str] = None,
        chunk_size: Optional[int] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Add a dataset to the registry for AI/ML applications.
        
        This method adds a dataset to IPFS and registers it in the dataset registry,
        making it available for machine learning model training and evaluation.
        It supports various input formats including files, paths, DataFrames,
        and other structured data formats.

        Args:
            dataset: The dataset to add, which can be:
                - str: Path to a local dataset file or directory
                - Path: Path object pointing to a dataset file or directory
                - Dict[str, Any]: Dictionary containing dataset data
                - DataFrame: Pandas DataFrame object
                - Dataset: HuggingFace Dataset or similar object
            metadata: Dictionary of metadata about the dataset, including:
                - name: Name of the dataset (required)
                - description: Description of the dataset
                - features: List of feature names
                - target: Target column name (for supervised learning)
                - rows: Number of rows in the dataset
                - columns: Number of columns in the dataset
                - tags: List of tags for categorization
                - license: License information
                - source: Source of the dataset
            pin: Whether to pin the dataset to local node for persistence
            replicate: Whether to replicate the dataset across the cluster
            format: Format of the dataset (csv, parquet, jsonl, etc.)
            chunk_size: Size in bytes for chunking large datasets
            timeout: Operation timeout in seconds
            **kwargs: Additional implementation-specific parameters

        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "cid": The content identifier of the added dataset
                - "dataset_name": Name of the dataset
                - "version": Version string of the dataset
                - "format": Detected or specified format
                - "stats": Dictionary with dataset statistics
                - "size": Size of the dataset in bytes
                - "timestamp": When the dataset was added
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon fails
            IPFSAddError: If the dataset cannot be added
            IPFSTimeoutError: If the operation times out
            IPFSValidationError: If parameters are invalid
            ImportError: If AI/ML integration is not available
        """
        if not AI_ML_AVAILABLE:
            raise IPFSError("AI/ML integration not available")
            
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "pin": pin,
            "replicate": replicate,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add format if provided
        if format is not None:
            kwargs_with_defaults["format"] = format
            
        # Add chunk_size if provided
        if chunk_size is not None:
            kwargs_with_defaults["chunk_size"] = chunk_size
            
        # Add timeout if provided
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout

        return self.kit.ai_dataset_add(dataset, metadata, **kwargs_with_defaults)

    def ai_dataset_get(
        self, 
        dataset_id: str, 
        *, 
        decode: bool = True,
        return_path: bool = False,
        target_path: Optional[str] = None,
        version: Optional[str] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get a dataset from the registry for AI/ML applications.
        
        This method retrieves a dataset from IPFS by its identifier or CID,
        and loads it into memory or saves it to disk depending on the options.
        The dataset can be returned as a DataFrame, native object, or a path
        to the downloaded files.

        Args:
            dataset_id: Dataset identifier (name) or Content Identifier (CID)
            decode: Whether to decode/parse the dataset into a usable format 
                   or just return the raw data
            return_path: Whether to return a local path to the dataset instead of loading it
            target_path: Specific path where the dataset should be saved
            version: Specific version of the dataset to retrieve
            timeout: Operation timeout in seconds
            **kwargs: Additional implementation-specific parameters
                - format_hint: Hint about the dataset format for proper parsing
                - columns: Specific columns to load (for tabular data)
                - transforms: Data transformations to apply during loading
                - sample: Whether to load only a sample (with optional sample size)

        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "dataset": The loaded dataset object (if decode=True)
                - "data": Raw dataset data (if decode=False)
                - "local_path": Path to the dataset (if return_path=True)
                - "format": Detected format of the dataset
                - "metadata": Dictionary with dataset metadata
                - "stats": Dictionary with dataset statistics
                - "timestamp": When the dataset was retrieved
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon fails
            IPFSGetError: If the dataset cannot be retrieved
            IPFSTimeoutError: If the operation times out
            IPFSValidationError: If parameters are invalid
            ImportError: If AI/ML integration is not available
        """
        if not AI_ML_AVAILABLE:
            raise IPFSError("AI/ML integration not available")
            
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "decode": decode,
            "return_path": return_path,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add target_path if provided
        if target_path is not None:
            kwargs_with_defaults["target_path"] = target_path
            
        # Add version if provided
        if version is not None:
            kwargs_with_defaults["version"] = version
            
        # Add timeout if provided
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout

        return self.kit.ai_dataset_get(dataset_id, **kwargs_with_defaults)

    def ai_data_loader(
        self, 
        dataset_cid: str, 
        *, 
        batch_size: int = 32,
        shuffle: bool = True,
        prefetch: int = 2, 
        framework: Optional[Literal["pytorch", "tensorflow"]] = None,
        num_workers: Optional[int] = None,
        drop_last: bool = False,
        transform: Optional[Callable] = None,
        target_transform: Optional[Callable] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a data loader for an IPFS-stored dataset.

        Creates an IPFSDataLoader instance for efficient loading of ML datasets from IPFS,
        with background prefetching and framework-specific conversions. This provides a 
        standardized way to load datasets from IPFS into ML training and inference pipelines.

        Args:
            dataset_cid: Content identifier for the dataset
            batch_size: Number of samples per batch
            shuffle: Whether to shuffle the dataset
            prefetch: Number of batches to prefetch asynchronously
            framework: Target framework for conversion ('pytorch', 'tensorflow', or None)
            num_workers: Number of worker processes for data loading (None = auto)
            drop_last: Whether to drop the last incomplete batch in epoch
            transform: Optional transform to apply to the features
            target_transform: Optional transform to apply to the targets
            timeout: Operation timeout in seconds
            **kwargs: Additional implementation-specific parameters
                - pin_dataset: Whether to pin the dataset during loading (default: True)
                - collate_fn: Custom collation function for batching
                - sampler: Custom sampling strategy
                - persistent_workers: Keep worker processes alive between iterations
                - generator: Random number generator for shuffling

        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "loader": The data loader object compatible with the specified framework
                - "dataset_info": Information about the dataset
                - "batch_shape": Typical shape of batches produced by this loader
                - "num_batches": Estimated number of batches per epoch
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon fails
            IPFSGetError: If the dataset cannot be retrieved
            IPFSTimeoutError: If the operation times out
            IPFSValidationError: If parameters are invalid
            ImportError: If AI/ML integration is not available
        """
        if not AI_ML_AVAILABLE:
            raise IPFSError("AI/ML integration not available")

        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "batch_size": batch_size,
            "shuffle": shuffle,
            "prefetch": prefetch,
            "framework": framework,
            "drop_last": drop_last,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add num_workers if provided
        if num_workers is not None:
            kwargs_with_defaults["num_workers"] = num_workers
            
        # Add transform if provided
        if transform is not None:
            kwargs_with_defaults["transform"] = transform
            
        # Add target_transform if provided
        if target_transform is not None:
            kwargs_with_defaults["target_transform"] = target_transform
            
        # Add timeout if provided
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout

        return self.kit.ai_data_loader(dataset_cid=dataset_cid, **kwargs_with_defaults)

    def ai_langchain_create_vectorstore(
        self, 
        documents: List["Document"], 
        *, 
        embedding_model: Optional[Union[str, "Embeddings"]] = None,
        collection_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        persist: bool = True,
        similarity_metric: str = "cosine",
        search_method: str = "hnsw",
        index_parameters: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a Langchain vector store backed by IPFS storage.
        
        This method creates a vector store from Langchain documents, generating embeddings
        and storing both the original documents and their vector representations in IPFS.
        The vector store can be used for semantic search, retrieval-augmented generation,
        and other LLM-based applications.

        Args:
            documents: List of Langchain Document objects to add to the vector store
            embedding_model: Name of embedding model to use or initialized Embeddings instance
                - If string: name of a HuggingFace model or "openai", "cohere", etc.
                - If object: instance of Langchain's Embeddings class
            collection_name: Custom name for the vector collection
                - If None: auto-generated based on document contents
            metadata: Additional metadata about the vector collection
            persist: Whether to persist the vector store to IPFS
            similarity_metric: Similarity measurement to use ("cosine", "l2", "dot", "jaccard")
            search_method: Vector search algorithm to use 
                - "hnsw": Hierarchical Navigable Small World (fast approximate search)
                - "flat": Exact exhaustive search (slower but more accurate)
                - "ivf": Inverted File Index (good balance of speed and accuracy)
            index_parameters: Additional parameters for the vector index 
                - For HNSW: "ef_construction", "M" (graph parameters)
                - For IVF: "nlist" (cluster count)
            timeout: Operation timeout in seconds
            **kwargs: Additional implementation-specific parameters
                - chunk_size: Text chunk size for document splitting
                - chunk_overlap: Overlap between chunks when splitting
                - normalize_embeddings: Whether to normalize embedding vectors
                - max_concurrency: Maximum concurrent embedding operations

        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "vectorstore": The created vector store object
                - "collection_name": Name of the created collection
                - "document_count": Number of documents in the store
                - "embedding_dim": Dimension of the embedding vectors
                - "cid": Content identifier for the persisted vector store
                - "stats": Performance statistics and index parameters
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            ImportError: If AI/ML integration or LangChain is not available
            ValueError: If invalid parameters are provided
        """
        if not AI_ML_AVAILABLE:
            raise IPFSError("AI/ML integration not available")

        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "embedding_model": embedding_model,
            "collection_name": collection_name,
            "persist": persist,
            "similarity_metric": similarity_metric,
            "search_method": search_method,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add metadata if provided
        if metadata is not None:
            kwargs_with_defaults["metadata"] = metadata
            
        # Add index_parameters if provided
        if index_parameters is not None:
            kwargs_with_defaults["index_parameters"] = index_parameters
            
        # Add timeout if provided
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout

        return self.kit.ai_langchain_create_vectorstore(documents=documents, **kwargs_with_defaults)

    def ai_langchain_load_documents(
        self, 
        path_or_cid: str, 
        *, 
        file_types: Optional[List[str]] = None,
        recursive: bool = True,
        loader_params: Optional[Dict[str, Any]] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        text_splitter: Optional[Any] = None,
        metadata_extractor: Optional[Callable] = None,
        exclude_patterns: Optional[List[str]] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Load documents from IPFS into Langchain format.
        
        This method loads content from IPFS (by path or CID) and converts it into
        Langchain Document objects, which can be used for LLM applications like
        retrieval-augmented generation, vector indexing, and chain creation.
        
        It automatically detects file types and uses appropriate loaders for each,
        with support for text, PDF, HTML, Markdown, CSV, and many other formats.

        Args:
            path_or_cid: Path or CID to load documents from
            file_types: List of file extensions to include (e.g., ["pdf", "txt", "md"])
                - If None: All supported file types will be loaded
            recursive: Whether to recursively traverse directories
            loader_params: Specific parameters for document loaders
                - Depends on file type, e.g., PDF loader parameters
            chunk_size: Maximum size of text chunks when splitting documents 
            chunk_overlap: Number of characters of overlap between chunks
            text_splitter: Custom text splitter instance for document chunking
                - Overrides chunk_size and chunk_overlap if provided
            metadata_extractor: Function to extract additional metadata from files
            exclude_patterns: List of glob patterns for files to exclude
            timeout: Operation timeout in seconds
            **kwargs: Additional implementation-specific parameters
                - encoding: Character encoding for text files
                - include_hidden: Whether to include hidden files
                - max_depth: Maximum depth for recursive directory traversal
                - language: Document language for specialized loaders

        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "documents": List of loaded Langchain Document objects
                - "document_count": Number of documents loaded
                - "file_count": Number of files processed
                - "file_types": Dictionary mapping file types to counts
                - "total_characters": Total character count across all documents
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon fails
            IPFSGetError: If the content cannot be retrieved
            ImportError: If AI/ML integration or LangChain is not available
            NotImplementedError: If document loader for a file type is not available
        """
        if not AI_ML_AVAILABLE:
            raise IPFSError("AI/ML integration not available")

        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "recursive": recursive,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add file_types if provided
        if file_types is not None:
            kwargs_with_defaults["file_types"] = file_types
            
        # Add loader_params if provided
        if loader_params is not None:
            kwargs_with_defaults["loader_params"] = loader_params
            
        # Add chunk_size if provided
        if chunk_size is not None:
            kwargs_with_defaults["chunk_size"] = chunk_size
            
        # Add chunk_overlap if provided
        if chunk_overlap is not None:
            kwargs_with_defaults["chunk_overlap"] = chunk_overlap
            
        # Add text_splitter if provided
        if text_splitter is not None:
            kwargs_with_defaults["text_splitter"] = text_splitter
            
        # Add metadata_extractor if provided
        if metadata_extractor is not None:
            kwargs_with_defaults["metadata_extractor"] = metadata_extractor
            
        # Add exclude_patterns if provided
        if exclude_patterns is not None:
            kwargs_with_defaults["exclude_patterns"] = exclude_patterns
            
        # Add timeout if provided
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout

        return self.kit.ai_langchain_load_documents(path_or_cid=path_or_cid, **kwargs_with_defaults)

    def ai_llama_index_create_index(
        self, 
        documents: List["Document"], 
        *, 
        index_type: str = "vector_store",
        embedding_model: Optional[Union[str, "BaseEmbedding"]] = None,
        index_name: Optional[str] = None,
        persist: bool = True,
        service_context: Optional[Any] = None,
        storage_context: Optional[Any] = None,
        index_settings: Optional[Dict[str, Any]] = None,
        similarity_top_k: int = 4,
        node_parser: Optional[Any] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a LlamaIndex index from documents using IPFS storage.
        
        This method builds a LlamaIndex data structure from documents, with automatic
        storage in IPFS. LlamaIndex provides advanced indexing capabilities for
        retrieval-augmented generation and other LLM applications, with flexible
        query capabilities and efficient retrieval.

        Args:
            documents: List of LlamaIndex Document objects to add to the index
            index_type: Type of index to create
                - "vector_store": Vector store index for semantic search (default)
                - "keyword_table": Keyword-based lookup index
                - "list": Simple list index 
                - "tree": Hierarchical tree index
                - "knowledge_graph": Knowledge graph index
            embedding_model: Name of embedding model to use or initialized embedding instance
                - If string: name of a model like "text-embedding-ada-002"
                - If object: instance of LlamaIndex BaseEmbedding class
            index_name: Custom name for the index
                - If None: auto-generated based on index type and content
            persist: Whether to persist the index to IPFS
            service_context: Custom LlamaIndex ServiceContext for customizing LLM/embeddings
            storage_context: Custom StorageContext for customizing document/index storage
            index_settings: Additional settings specific to the chosen index type
                - For vector_store: "dim", "metric", "index_factory"
                - For keyword_table: "use_stemmer", "lowercase_tokens"
                - For tree: "branch_factor", "max_tree_depth"
            similarity_top_k: Default number of similar items to retrieve in queries
            node_parser: Custom NodeParser for document chunking and node creation
            timeout: Operation timeout in seconds
            **kwargs: Additional implementation-specific parameters
                - chunk_size: Size of text chunks for indexing
                - chunk_overlap: Overlap between text chunks
                - include_metadata: Whether to include metadata in index
                - embed_model_args: Additional arguments for embedding model

        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "index": The created LlamaIndex index object
                - "index_name": Name of the created index
                - "index_type": Type of index created
                - "document_count": Number of documents in the index
                - "node_count": Number of nodes in the index
                - "cid": Content identifier for the persisted index
                - "metadata": Additional metadata about the index
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            ImportError: If AI/ML integration or LlamaIndex is not available
            ValueError: If invalid parameters are provided
        """
        if not AI_ML_AVAILABLE:
            raise IPFSError("AI/ML integration not available")

        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "index_type": index_type,
            "embedding_model": embedding_model,
            "index_name": index_name,
            "persist": persist,
            "similarity_top_k": similarity_top_k,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add service_context if provided
        if service_context is not None:
            kwargs_with_defaults["service_context"] = service_context
            
        # Add storage_context if provided
        if storage_context is not None:
            kwargs_with_defaults["storage_context"] = storage_context
            
        # Add index_settings if provided
        if index_settings is not None:
            kwargs_with_defaults["index_settings"] = index_settings
            
        # Add node_parser if provided
        if node_parser is not None:
            kwargs_with_defaults["node_parser"] = node_parser
            
        # Add timeout if provided
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout

        return self.kit.ai_llama_index_create_index(documents=documents, **kwargs_with_defaults)

    def ai_llama_index_load_documents(
        self, 
        path_or_cid: str, 
        *, 
        file_types: Optional[List[str]] = None,
        recursive: bool = True,
        loader_params: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
        metadata_extractor: Optional[Callable] = None,
        exclude_patterns: Optional[List[str]] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        node_parser: Optional[Any] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Load documents from IPFS into LlamaIndex format.
        
        This method loads content from IPFS (by path or CID) and converts it into
        LlamaIndex Document objects. LlamaIndex provides advanced document handling
        capabilities for retrieval-augmented generation, query parsing, and efficient
        embeddings management with its own document model.

        Args:
            path_or_cid: Path or CID to load documents from
            file_types: List of file extensions to include (e.g., ["pdf", "txt", "md"])
                - If None: All supported file types will be loaded
            recursive: Whether to recursively traverse directories
            loader_params: Specific parameters for document loaders
                - Depends on file type, e.g., PDF loader parameters
            include_metadata: Whether to include file metadata in document objects
            metadata_extractor: Function to extract additional metadata from files
            exclude_patterns: List of glob patterns for files to exclude
            chunk_size: Maximum size of text chunks when splitting documents
            chunk_overlap: Number of characters of overlap between chunks
            node_parser: Custom NodeParser for document processing and chunking
                - Overrides chunk_size and chunk_overlap if provided
            timeout: Operation timeout in seconds
            **kwargs: Additional implementation-specific parameters
                - include_hidden: Whether to include hidden files
                - exclude_hidden: Whether to exclude hidden files (default: True)
                - show_progress: Whether to show progress bar during loading
                - detect_language: Automatically detect document language
                - file_metadata: Additional metadata to apply to all loaded files
                - max_docs: Maximum number of documents to load

        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "documents": List of loaded LlamaIndex Document objects
                - "document_count": Number of documents loaded
                - "file_count": Number of files processed
                - "file_types": Dictionary mapping file types to counts
                - "total_characters": Total character count across all documents
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSConnectionError: If connection to IPFS daemon fails
            IPFSGetError: If the content cannot be retrieved
            ImportError: If AI/ML integration or LlamaIndex is not available
            NotImplementedError: If document loader for a file type is not available
        """
        if not AI_ML_AVAILABLE:
            raise IPFSError("AI/ML integration not available")

        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "recursive": recursive,
            "include_metadata": include_metadata,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add file_types if provided
        if file_types is not None:
            kwargs_with_defaults["file_types"] = file_types
            
        # Add loader_params if provided
        if loader_params is not None:
            kwargs_with_defaults["loader_params"] = loader_params
            
        # Add metadata_extractor if provided
        if metadata_extractor is not None:
            kwargs_with_defaults["metadata_extractor"] = metadata_extractor
            
        # Add exclude_patterns if provided
        if exclude_patterns is not None:
            kwargs_with_defaults["exclude_patterns"] = exclude_patterns
            
        # Add chunk_size if provided
        if chunk_size is not None:
            kwargs_with_defaults["chunk_size"] = chunk_size
            
        # Add chunk_overlap if provided
        if chunk_overlap is not None:
            kwargs_with_defaults["chunk_overlap"] = chunk_overlap
            
        # Add node_parser if provided
        if node_parser is not None:
            kwargs_with_defaults["node_parser"] = node_parser
            
        # Add timeout if provided
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout

        return self.kit.ai_llama_index_load_documents(path_or_cid=path_or_cid, **kwargs_with_defaults)

    def ai_distributed_training_submit_job(
        self, 
        config: Dict[str, Any], 
        *, 
        num_workers: Optional[int] = None,
        priority: Literal["low", "normal", "high", "critical"] = "normal",
        notify_on_completion: bool = False,
        wait_for_completion: bool = False,
        worker_selection: Optional[List[str]] = None,
        resources_per_worker: Optional[Dict[str, Union[int, float]]] = None,
        timeout: Optional[int] = None,
        checkpoint_interval: Optional[int] = None,
        validation_split: Optional[float] = None,
        test_split: Optional[float] = None,
        shuffle_data: Optional[bool] = None,
        data_augmentation: Optional[Dict[str, Any]] = None,
        early_stopping: Optional[Dict[str, Any]] = None,
        gradient_accumulation: Optional[int] = None,
        mixed_precision: Optional[bool] = None,
        log_level: Optional[Literal["debug", "info", "warning", "error"]] = None,
        allow_simulation: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Submit a distributed training job to the IPFS cluster.
        
        This method submits a machine learning training job to be distributed across
        worker nodes in the IPFS cluster. It supports both training from scratch and
        fine-tuning existing models, with automatic data partitioning and result 
        aggregation.

        Args:
            config: Training job configuration dictionary with these keys:
                - model_name: Name for the model being trained (required)
                - dataset_cid: CID of the dataset to use for training (required)
                - model_cid: (optional) CID of a base model for fine-tuning
                - model_type: Type of model to train (e.g., "classification", "regression")
                - hyperparameters: Dictionary of training hyperparameters 
                    - learning_rate, batch_size, epochs, optimizer, etc.
                - framework: ML framework to use ("pytorch", "tensorflow", "jax", etc.)
                - evaluation_metrics: List of metrics to track during training
                - loss_function: Loss function to use for training
                - architecture: Model architecture details or configuration
            num_workers: Number of worker nodes to use for distributed training
                - If None: Uses all available worker nodes in the cluster
            priority: Job priority level ("low", "normal", "high", "critical")
            notify_on_completion: Whether to send notification when job completes
            wait_for_completion: Whether to block until job completes
            worker_selection: List of specific worker node IDs to use
            resources_per_worker: Resource requirements for each worker
                - cpu_cores: Minimum CPU cores required
                - memory_gb: Minimum RAM in GB required
                - gpu_count: Minimum GPUs required
                - disk_space_gb: Minimum disk space in GB
            timeout: Job timeout in seconds (after which job is cancelled)
            checkpoint_interval: Interval in seconds between model checkpoints
            validation_split: Portion of data to use for validation (0.0 to 1.0)
            test_split: Portion of data to use for testing (0.0 to 1.0)
            shuffle_data: Whether to shuffle training data
            data_augmentation: Data augmentation settings dictionary
            early_stopping: Early stopping configuration dictionary
                - patience: Number of epochs to wait for improvement
                - min_delta: Minimum change to qualify as improvement
                - monitor: Metric to monitor for improvement
            gradient_accumulation: Number of batches to accumulate gradients over
            mixed_precision: Whether to use mixed precision training
            log_level: Logging verbosity level ("debug", "info", "warning", "error")
            allow_simulation: Whether to allow simulated responses if AI/ML integration is unavailable
            **kwargs: Additional implementation-specific parameters

        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "operation": Name of the operation ("ai_distributed_training_submit_job")
                - "timestamp": Time when the operation was performed
                - "job_id": Unique identifier for the submitted job
                - "submitted_at": Timestamp when the job was submitted
                - "worker_count": Number of worker nodes assigned to the job
                - "estimated_duration": Estimated job duration in seconds
                - "estimated_start_time": Estimated job start time
                - "status": Initial job status ("queued", "starting", "running")
                - "job_config": Submitted job configuration
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSValidationError: If job configuration is invalid
            IPFSClusterError: If cluster is not available
            ImportError: If AI/ML integration is not available and allow_simulation=False
        """
        # Validate config has required fields
        if not isinstance(config, dict):
            raise IPFSValidationError("config must be a dictionary")
        
        if "model_name" not in config:
            raise IPFSValidationError("config must contain 'model_name'")
            
        if "dataset_cid" not in config:
            raise IPFSValidationError("config must contain 'dataset_cid'")
            
        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            if allow_simulation:
                # Return simulated response
                import uuid
                import time
                
                job_id = f"sim-{uuid.uuid4()}"
                current_time = time.time()
                
                return {
                    "success": True,
                    "operation": "ai_distributed_training_submit_job",
                    "timestamp": current_time,
                    "job_id": job_id,
                    "submitted_at": current_time,
                    "worker_count": num_workers or 3,  # Simulate 3 workers by default
                    "estimated_duration": 3600,  # Simulate 1 hour duration
                    "estimated_start_time": current_time + 30,  # Simulate 30s delay
                    "status": "queued",
                    "job_config": config,
                    "simulated": True
                }
            else:
                raise IPFSError("AI/ML integration not available")

        # Build kwargs dictionary with explicit parameters
        kwargs_with_defaults = {
            "priority": priority,
            "notify_on_completion": notify_on_completion,
            "wait_for_completion": wait_for_completion,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add optional parameters if provided
        if num_workers is not None:
            kwargs_with_defaults["num_workers"] = num_workers
            
        if worker_selection is not None:
            kwargs_with_defaults["worker_selection"] = worker_selection
            
        if resources_per_worker is not None:
            kwargs_with_defaults["resources_per_worker"] = resources_per_worker
            
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout
            
        if checkpoint_interval is not None:
            kwargs_with_defaults["checkpoint_interval"] = checkpoint_interval
            
        if validation_split is not None:
            kwargs_with_defaults["validation_split"] = validation_split
            
        if test_split is not None:
            kwargs_with_defaults["test_split"] = test_split
            
        if shuffle_data is not None:
            kwargs_with_defaults["shuffle_data"] = shuffle_data
            
        if data_augmentation is not None:
            kwargs_with_defaults["data_augmentation"] = data_augmentation
            
        if early_stopping is not None:
            kwargs_with_defaults["early_stopping"] = early_stopping
            
        if gradient_accumulation is not None:
            kwargs_with_defaults["gradient_accumulation"] = gradient_accumulation
            
        if mixed_precision is not None:
            kwargs_with_defaults["mixed_precision"] = mixed_precision
            
        if log_level is not None:
            kwargs_with_defaults["log_level"] = log_level

        # Pass to underlying implementation
        return self.kit.ai_distributed_training_submit_job(config=config, **kwargs_with_defaults)

    def ai_distributed_training_get_status(
        self, 
        job_id: str, 
        *, 
        include_metrics: bool = True,
        include_logs: bool = False,
        include_checkpoints: bool = False,
        worker_details: bool = True,
        metrics_limit: Optional[int] = None,
        log_level: Optional[Literal["debug", "info", "warning", "error"]] = None,
        log_limit: Optional[int] = None,
        checkpoint_limit: Optional[int] = None,
        timeout: Optional[int] = None,
        allow_simulation: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get the status of a distributed training job.
        
        This method retrieves the current status of a previously submitted distributed
        training job, including progress metrics, worker allocation, and resource usage.
        It can optionally include detailed logs and checkpoint information.

        Args:
            job_id: Unique identifier of the job to query
            include_metrics: Whether to include training metrics in the result
            include_logs: Whether to include training logs in the result
            include_checkpoints: Whether to include checkpoint information
            worker_details: Whether to include detailed worker node information
            metrics_limit: Maximum number of metric data points to return
            log_level: Minimum log level to include ("debug", "info", "warning", "error")
            log_limit: Maximum number of log entries to return
            checkpoint_limit: Maximum number of checkpoints to include
            timeout: Operation timeout in seconds
            allow_simulation: Whether to allow simulated responses if AI/ML integration is unavailable
            **kwargs: Additional implementation-specific parameters

        Returns:
            Dict[str, Any]: Dictionary containing job status information with these keys:
                - "success": bool indicating if the operation succeeded
                - "operation": Name of the operation ("ai_distributed_training_get_status")
                - "timestamp": Time when the operation was performed
                - "job_id": The queried job's identifier
                - "status": Current job status ("queued", "starting", "running", "complete", "failed", "cancelled")
                - "progress": Overall job progress as a percentage (0-100)
                - "elapsed_time": Time elapsed since job started in seconds
                - "remaining_time": Estimated time remaining in seconds
                - "worker_count": Number of worker nodes assigned to the job
                - "active_workers": Number of currently active worker nodes
                - "metrics": Training metrics if requested (loss, accuracy, etc.)
                - "logs": Training logs if requested
                - "checkpoints": Available checkpoint information if requested
                - "worker_details": Detailed worker information if requested
                - "resource_usage": Current CPU, memory, and GPU usage
                - "errors": Any errors encountered during training
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSValidationError: If job_id is invalid
            ImportError: If AI/ML integration is not available and allow_simulation=False
        """
        # Validate job_id
        if not job_id:
            raise IPFSValidationError("job_id must not be empty")
        
        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            if allow_simulation:
                # Return simulated response
                import time
                import random
                
                current_time = time.time()
                if job_id.startswith("sim-"):
                    # Generate a realistic simulated training job status
                    # This provides a way to test client code without real cluster
                    progress = random.randint(10, 95)
                    elapsed_time = random.randint(300, 1800)  # 5-30 minutes
                    
                    # Calculate remaining time based on progress
                    total_time = elapsed_time / (progress / 100) if progress > 0 else 3600
                    remaining_time = max(0, total_time - elapsed_time)
                    
                    # Set a reasonable status based on the progress
                    if progress < 20:
                        status = "starting"
                    elif progress < 95:
                        status = "running"
                    else:
                        status = "complete"
                        progress = 100
                        remaining_time = 0
                    
                    # Generate metrics if requested
                    metrics = None
                    if include_metrics:
                        metrics = {
                            "loss": max(0.1, 2.0 - (progress / 100) * 1.9),  # Decreasing loss
                            "accuracy": min(0.99, 0.5 + (progress / 100) * 0.5),  # Increasing accuracy
                            "learning_rate": 0.001 * (0.95 ** (progress // 10)),  # Decaying LR
                            "epochs_completed": progress // 5,
                            "batches_completed": progress * 10,
                            "samples_processed": progress * 500
                        }
                    
                    # Generate logs if requested
                    logs = None
                    if include_logs:
                        logs = []
                        log_entries = min(log_limit or 10, 10)
                        for i in range(log_entries):
                            logs.append({
                                "timestamp": current_time - (log_entries - i) * 60,
                                "level": random.choice(["info", "debug"] + (["warning"] if i % 5 == 0 else [])),
                                "message": f"Training progress: {progress - (log_entries - i) * random.randint(1, 5)}%"
                            })
                    
                    # Generate checkpoint info if requested
                    checkpoints = None
                    if include_checkpoints:
                        checkpoints = []
                        checkpoint_count = min(checkpoint_limit or 3, 3)
                        for i in range(checkpoint_count):
                            epoch = progress // 5 - (checkpoint_count - i)
                            if epoch >= 0:
                                checkpoints.append({
                                    "checkpoint_id": f"ckpt-{job_id}-{epoch}",
                                    "epoch": epoch,
                                    "timestamp": current_time - (checkpoint_count - i) * 300,
                                    "metrics": {
                                        "loss": max(0.1, 2.0 - (epoch / 20) * 1.9),
                                        "accuracy": min(0.99, 0.5 + (epoch / 20) * 0.5)
                                    }
                                })
                    
                    # Generate worker details if requested
                    worker_info = None
                    worker_count = random.randint(2, 5)
                    active_workers = max(1, int(worker_count * (progress / 100)))
                    
                    if worker_details:
                        worker_info = []
                        for i in range(worker_count):
                            is_active = i < active_workers
                            worker_info.append({
                                "worker_id": f"worker-{i+1}",
                                "status": "active" if is_active else "idle",
                                "progress": progress + random.randint(-5, 5) if is_active else 0,
                                "resources": {
                                    "cpu_usage": random.uniform(0.7, 0.9) if is_active else random.uniform(0.1, 0.3),
                                    "memory_usage": random.uniform(0.6, 0.8) if is_active else random.uniform(0.1, 0.4),
                                    "gpu_usage": random.uniform(0.5, 0.95) if is_active else 0.0
                                }
                            })
                    
                    return {
                        "success": True,
                        "operation": "ai_distributed_training_get_status",
                        "timestamp": current_time,
                        "job_id": job_id,
                        "status": status,
                        "progress": progress,
                        "elapsed_time": elapsed_time,
                        "remaining_time": remaining_time,
                        "worker_count": worker_count,
                        "active_workers": active_workers,
                        "metrics": metrics,
                        "logs": logs,
                        "checkpoints": checkpoints,
                        "worker_details": worker_info,
                        "resource_usage": {
                            "cpu_average": sum(w["resources"]["cpu_usage"] for w in worker_info) / len(worker_info) if worker_info else 0.5,
                            "memory_average": sum(w["resources"]["memory_usage"] for w in worker_info) / len(worker_info) if worker_info else 0.4,
                            "gpu_average": sum(w["resources"]["gpu_usage"] for w in worker_info) / len(worker_info) if worker_info else 0.3
                        },
                        "errors": [],
                        "simulated": True
                    }
                else:
                    # Unknown job ID for simulation
                    return {
                        "success": False,
                        "operation": "ai_distributed_training_get_status",
                        "timestamp": current_time,
                        "error": f"Job with ID '{job_id}' not found",
                        "error_type": "not_found",
                        "simulated": True
                    }
            else:
                raise IPFSError("AI/ML integration not available")

        # Build kwargs dictionary with explicit parameters
        kwargs_with_defaults = {
            "include_metrics": include_metrics,
            "include_logs": include_logs,
            "include_checkpoints": include_checkpoints,
            "worker_details": worker_details,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add optional parameters if provided
        if metrics_limit is not None:
            kwargs_with_defaults["metrics_limit"] = metrics_limit
            
        if log_level is not None:
            kwargs_with_defaults["log_level"] = log_level
            
        if log_limit is not None:
            kwargs_with_defaults["log_limit"] = log_limit
            
        if checkpoint_limit is not None:
            kwargs_with_defaults["checkpoint_limit"] = checkpoint_limit
            
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout

        # Pass to underlying implementation
        return self.kit.ai_distributed_training_get_status(job_id=job_id, **kwargs_with_defaults)

    def ai_distributed_training_aggregate_results(
        self, 
        job_id: str, 
        *, 
        aggregation_method: Literal["best_model", "model_averaging", "ensemble", "federation"] = "best_model",
        evaluation_dataset_cid: Optional[str] = None,
        include_metrics: bool = True,
        include_model_details: bool = True,
        save_aggregated_model: bool = True,
        ensemble_strategy: Optional[Literal["voting", "averaging", "stacking"]] = None,
        averaging_weights: Optional[Dict[str, float]] = None,
        selection_metric: Optional[str] = None,
        selection_mode: Optional[Literal["maximize", "minimize"]] = None,
        evaluation_batch_size: Optional[int] = None,
        timeout: Optional[int] = None,
        allow_simulation: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Aggregate results from a distributed training job.
        
        This method combines results from multiple worker nodes that participated in 
        a distributed training job. It can perform model averaging, ensemble creation,
        or best model selection based on validation metrics.

        Args:
            job_id: Unique identifier of the job to aggregate results from
            aggregation_method: Method to use for aggregation
                - "best_model": Select the best performing model (default)
                - "model_averaging": Average model weights across workers
                - "ensemble": Create an ensemble from all worker models
                - "federation": Apply federated learning aggregation
            evaluation_dataset_cid: Optional CID of dataset to use for evaluation
                - If provided, models will be evaluated on this dataset
                - If None, validation metrics from training are used
            include_metrics: Whether to include evaluation metrics in results
            include_model_details: Whether to include detailed model information
            save_aggregated_model: Whether to save the aggregated model to IPFS
            ensemble_strategy: Strategy for ensemble creation if using ensemble method
                - "voting": Use majority voting (for classification)
                - "averaging": Average predictions (for regression/probability)
                - "stacking": Train a meta-model on worker model predictions
            averaging_weights: Custom weights for model averaging
                - Dictionary mapping worker IDs to weight values
                - If None, equal weights are used for all workers
            selection_metric: Metric to use for best model selection
                - e.g., "accuracy", "f1", "loss", "mean_squared_error"
                - If None, uses default metric based on model type
            selection_mode: Whether to maximize or minimize the selection metric
                - "maximize": Higher is better (accuracy, f1, etc.)
                - "minimize": Lower is better (loss, error, etc.)
            evaluation_batch_size: Batch size for evaluation
            timeout: Operation timeout in seconds
            allow_simulation: Whether to allow simulated responses if AI/ML integration is unavailable
            **kwargs: Additional implementation-specific parameters

        Returns:
            Dict[str, Any]: Dictionary containing aggregation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "operation": Name of the operation ("ai_distributed_training_aggregate_results")
                - "timestamp": Time when the operation was performed 
                - "job_id": The original job's identifier
                - "aggregation_method": Method used for aggregation
                - "model_cid": CID of the aggregated model (if save_aggregated_model=True)
                - "metrics": Evaluation metrics for the aggregated model
                - "worker_contributions": Information about each worker's contribution
                - "aggregation_time": Time taken for aggregation in seconds
                - "model_details": Detailed model information if requested
                - "parameters": Parameter counts and architecture information
                - "size_bytes": Size of the aggregated model in bytes
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSValidationError: If job_id is invalid or job is not complete
            ImportError: If AI/ML integration is not available and allow_simulation=False
        """
        # Validate job_id
        if not job_id:
            raise IPFSValidationError("job_id must not be empty")
        
        # Validate aggregation_method
        valid_aggregation_methods = ["best_model", "model_averaging", "ensemble", "federation"]
        if aggregation_method not in valid_aggregation_methods:
            raise IPFSValidationError(
                f"Invalid aggregation_method: {aggregation_method}. "
                f"Must be one of: {', '.join(valid_aggregation_methods)}"
            )
        
        # Check ensemble_strategy if using ensemble aggregation
        if aggregation_method == "ensemble" and ensemble_strategy:
            valid_ensemble_strategies = ["voting", "averaging", "stacking"]
            if ensemble_strategy not in valid_ensemble_strategies:
                raise IPFSValidationError(
                    f"Invalid ensemble_strategy: {ensemble_strategy}. "
                    f"Must be one of: {', '.join(valid_ensemble_strategies)}"
                )
        
        # Check selection_mode if provided
        if selection_mode:
            valid_selection_modes = ["maximize", "minimize"]
            if selection_mode not in valid_selection_modes:
                raise IPFSValidationError(
                    f"Invalid selection_mode: {selection_mode}. "
                    f"Must be one of: {', '.join(valid_selection_modes)}"
                )
        
        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            if allow_simulation:
                # Return simulated response
                import time
                import random
                import uuid
                
                current_time = time.time()
                if job_id.startswith("sim-"):
                    # Generate a realistic simulated aggregation result
                    aggregation_time = random.uniform(5.0, 30.0)
                    worker_count = random.randint(2, 5)
                    
                    # Generate model CID if saving
                    model_cid = f"Qm{''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=44))}" if save_aggregated_model else None
                    
                    # Generate metrics based on aggregation method
                    metrics = None
                    if include_metrics:
                        if aggregation_method == "best_model":
                            # Best model metrics should be good
                            accuracy = random.uniform(0.85, 0.95)
                            metrics = {
                                "accuracy": accuracy,
                                "precision": accuracy - random.uniform(0.01, 0.05),
                                "recall": accuracy - random.uniform(0.01, 0.05),
                                "f1": accuracy - random.uniform(0.01, 0.03),
                                "loss": random.uniform(0.1, 0.3)
                            }
                        elif aggregation_method == "model_averaging":
                            # Averaged model metrics should be decent
                            accuracy = random.uniform(0.80, 0.92)
                            metrics = {
                                "accuracy": accuracy,
                                "precision": accuracy - random.uniform(0.02, 0.07),
                                "recall": accuracy - random.uniform(0.02, 0.07),
                                "f1": accuracy - random.uniform(0.02, 0.05),
                                "loss": random.uniform(0.2, 0.4)
                            }
                        elif aggregation_method == "ensemble":
                            # Ensemble metrics should be the best
                            accuracy = random.uniform(0.88, 0.97)
                            metrics = {
                                "accuracy": accuracy,
                                "precision": accuracy - random.uniform(0.00, 0.03),
                                "recall": accuracy - random.uniform(0.00, 0.03),
                                "f1": accuracy - random.uniform(0.00, 0.02),
                                "loss": random.uniform(0.08, 0.25)
                            }
                        else:  # federation
                            # Federation metrics between best and average
                            accuracy = random.uniform(0.82, 0.94)
                            metrics = {
                                "accuracy": accuracy,
                                "precision": accuracy - random.uniform(0.01, 0.06),
                                "recall": accuracy - random.uniform(0.01, 0.06),
                                "f1": accuracy - random.uniform(0.01, 0.04),
                                "loss": random.uniform(0.15, 0.35)
                            }
                    
                    # Generate worker contributions
                    worker_contributions = []
                    for i in range(worker_count):
                        # Worker ID
                        worker_id = f"worker-{i+1}"
                        
                        # Worker performance varies
                        perf_variance = random.uniform(-0.1, 0.1)
                        worker_acc = max(0.5, min(0.99, (metrics["accuracy"] if metrics else 0.85) + perf_variance))
                        
                        # Worker contribution percentage
                        if aggregation_method == "best_model":
                            # One worker contributes 100%, others 0%
                            contribution = 100.0 if i == 0 else 0.0
                        elif aggregation_method == "model_averaging":
                            # Even contributions or based on averaging_weights
                            if averaging_weights and worker_id in averaging_weights:
                                # Use provided weights
                                contribution = averaging_weights[worker_id] * 100.0
                            else:
                                # Equal weights
                                contribution = 100.0 / worker_count
                        elif aggregation_method == "ensemble":
                            # Contributions vary by performance
                            contribution = 100.0 * (worker_acc / (worker_count * (metrics["accuracy"] if metrics else 0.85)))
                        else:  # federation
                            # Contributions based on data quantity and quality
                            contribution = 100.0 / worker_count + random.uniform(-5.0, 5.0)
                            contribution = max(0.1, min(50.0, contribution))
                        
                        worker_contributions.append({
                            "worker_id": worker_id,
                            "contribution_percentage": contribution,
                            "metrics": {
                                "accuracy": worker_acc,
                                "loss": random.uniform(0.1, 0.5)
                            },
                            "samples_processed": random.randint(1000, 5000),
                            "training_time": random.uniform(300, 1800)
                        })
                    
                    # Normalize contributions to sum to 100%
                    if aggregation_method not in ["best_model"]:
                        total_contribution = sum(w["contribution_percentage"] for w in worker_contributions)
                        if total_contribution > 0:
                            for worker in worker_contributions:
                                worker["contribution_percentage"] = (worker["contribution_percentage"] / total_contribution) * 100.0
                    
                    # Model details
                    model_details = None
                    if include_model_details:
                        model_details = {
                            "framework": random.choice(["pytorch", "tensorflow", "sklearn"]),
                            "architecture": "ResNet50" if random.random() > 0.5 else "Transformer",
                            "parameters": random.randint(1000000, 50000000),
                            "layers": random.randint(10, 100),
                            "optimizer": random.choice(["Adam", "SGD", "AdamW"]),
                            "learning_rate": 0.001,
                            "input_shape": [random.randint(1, 16), 224, 224, 3],
                            "output_shape": [random.randint(1, 16), random.choice([10, 100, 1000])],
                            "quantized": random.random() > 0.7,
                            "pruned": random.random() > 0.8
                        }
                    
                    return {
                        "success": True,
                        "operation": "ai_distributed_training_aggregate_results",
                        "timestamp": current_time,
                        "job_id": job_id,
                        "aggregation_method": aggregation_method,
                        "model_cid": model_cid,
                        "metrics": metrics,
                        "worker_contributions": worker_contributions,
                        "aggregation_time": aggregation_time,
                        "model_details": model_details,
                        "parameters": model_details["parameters"] if model_details else random.randint(1000000, 50000000),
                        "size_bytes": random.randint(10000000, 500000000),
                        "simulated": True
                    }
                else:
                    # Unknown job ID for simulation
                    return {
                        "success": False,
                        "operation": "ai_distributed_training_aggregate_results",
                        "timestamp": current_time,
                        "error": f"Job with ID '{job_id}' not found",
                        "error_type": "not_found",
                        "simulated": True
                    }
            else:
                raise IPFSError("AI/ML integration not available")

        # Build kwargs dictionary with explicit parameters
        kwargs_with_defaults = {
            "aggregation_method": aggregation_method,
            "include_metrics": include_metrics,
            "include_model_details": include_model_details,
            "save_aggregated_model": save_aggregated_model,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add optional parameters if provided
        if evaluation_dataset_cid is not None:
            kwargs_with_defaults["evaluation_dataset_cid"] = evaluation_dataset_cid
            
        if ensemble_strategy is not None:
            kwargs_with_defaults["ensemble_strategy"] = ensemble_strategy
            
        if averaging_weights is not None:
            kwargs_with_defaults["averaging_weights"] = averaging_weights
            
        if selection_metric is not None:
            kwargs_with_defaults["selection_metric"] = selection_metric
            
        if selection_mode is not None:
            kwargs_with_defaults["selection_mode"] = selection_mode
            
        if evaluation_batch_size is not None:
            kwargs_with_defaults["evaluation_batch_size"] = evaluation_batch_size
            
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout

        # Pass to underlying implementation
        return self.kit.ai_distributed_training_aggregate_results(job_id=job_id, **kwargs_with_defaults)

    def ai_benchmark_model(
        self, 
        model_cid: str, 
        *, 
        benchmark_type: Literal["inference", "training"] = "inference",
        batch_sizes: List[int] = [1, 8, 32],
        hardware_configs: Optional[List[Dict[str, Any]]] = None,
        precision: List[Literal["fp32", "fp16", "bf16", "int8", "int4"]] = ["fp32"],
        metrics: List[str] = ["latency", "throughput"],
        dataset_cid: Optional[str] = None,
        input_shapes: Optional[Dict[str, List[int]]] = None,
        iterations: int = 10,
        warmup_iterations: int = 3,
        framework: Optional[str] = None,
        compiler_options: Optional[Dict[str, Any]] = None,
        execution_providers: Optional[List[str]] = None,
        profiling_level: Optional[Literal["basic", "detailed", "full"]] = None,
        report_format: Optional[Literal["json", "csv", "html", "md"]] = None,
        distributed: bool = False,
        timeout: Optional[int] = None,
        allow_simulation: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Benchmark model performance for inference or training workloads.
        
        This method evaluates the performance characteristics of a machine learning model
        across various hardware configurations, batch sizes, and precision modes. It can
        measure both inference and training performance with customizable metrics.

        Args:
            model_cid: Content identifier of the model to benchmark
            benchmark_type: Type of benchmark to perform
                - "inference": Measure model inference performance (default)
                - "training": Measure model training performance
            batch_sizes: List of batch sizes to test
            hardware_configs: List of hardware configurations to test
                - Each config is a dict with keys like "device", "num_threads", etc.
                - If None: Uses the current hardware configuration only
            precision: List of precision modes to test
                - Common values: "fp32", "fp16", "int8", "bf16"
            metrics: List of metrics to measure during benchmarking
                - For inference: "latency", "throughput", "memory", "energy"
                - For training: "throughput", "time_per_epoch", "memory_usage"
            dataset_cid: Optional CID of dataset to use for benchmarking
                - If None: Uses synthetic data generated based on model inputs
            input_shapes: Dictionary mapping input names to their shapes
                - Only required for models with dynamic input shapes
                - Example: {"input_ids": [1, 128], "attention_mask": [1, 128]}
            iterations: Number of iterations to run for each configuration
            warmup_iterations: Number of warmup iterations before measurement
            framework: ML framework the model belongs to
                - If None: Automatically detected from model format
            compiler_options: Options for model compilation or optimization
                - Examples: {"opt_level": 3, "target": "cuda"}
            execution_providers: List of execution providers to test
                - Examples: ["CUDAExecutionProvider", "CPUExecutionProvider"]
            profiling_level: Detail level for performance profiling
                - "basic": Essential metrics only
                - "detailed": Includes layer-by-layer breakdown
                - "full": Comprehensive profiling with memory usage
            report_format: Format for the benchmark report
                - Options: "json", "csv", "html", "md" (markdown)
            distributed: Whether to run benchmark in distributed mode
            timeout: Operation timeout in seconds
            allow_simulation: Whether to allow simulated responses if AI/ML integration is unavailable
            **kwargs: Additional implementation-specific parameters

        Returns:
            Dict[str, Any]: Dictionary containing benchmark results with these keys:
                - "success": bool indicating if the operation succeeded
                - "operation": Name of the operation ("ai_benchmark_model")
                - "timestamp": Time when the operation was performed
                - "model_cid": CID of the benchmarked model
                - "model_info": Basic information about the model
                - "configurations": List of tested configurations 
                - "results": Detailed benchmark results
                    - For each configuration: metrics, statistics, resource usage
                - "summary": Summary statistics and comparisons
                - "recommendations": Recommended configuration based on results
                - "benchmark_duration": Total time taken for benchmarking
                - "errors": Any errors encountered during benchmarking
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSGetError: If model cannot be retrieved
            IPFSValidationError: If provided parameters are invalid
            ImportError: If AI/ML integration is not available and allow_simulation=False
        """
        # Validate model_cid
        if not model_cid:
            raise IPFSValidationError("model_cid must not be empty")
            
        # Validate benchmark_type
        valid_benchmark_types = ["inference", "training"]
        if benchmark_type not in valid_benchmark_types:
            raise IPFSValidationError(
                f"Invalid benchmark_type: {benchmark_type}. "
                f"Must be one of: {', '.join(valid_benchmark_types)}"
            )
            
        # Validate batch_sizes
        if not batch_sizes:
            raise IPFSValidationError("batch_sizes must not be empty")
            
        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            if allow_simulation:
                # Return simulated response
                import time
                import random
                import uuid
                
                current_time = time.time()
                
                # Generate model info
                model_info = {
                    "name": f"Model-{model_cid[:8]}",
                    "framework": framework or random.choice(["pytorch", "tensorflow", "onnx"]),
                    "size_bytes": random.randint(10000000, 500000000),
                    "parameters": random.randint(1000000, 100000000),
                    "inputs": {
                        "input1": {"shape": [batch_sizes[0], 3, 224, 224], "dtype": "float32"},
                        "input2": {"shape": [batch_sizes[0], 1], "dtype": "int64"} if random.random() > 0.7 else None
                    }
                }
                
                # Generate configurations
                configurations = []
                for bs in batch_sizes:
                    for prec in precision:
                        config = {
                            "id": f"config-{uuid.uuid4()}",
                            "batch_size": bs,
                            "precision": prec,
                            "hardware": {"device": "CPU", "num_threads": 4} if not hardware_configs else hardware_configs[0]
                        }
                        configurations.append(config)
                
                # Generate benchmark results
                results = []
                for config in configurations:
                    # Base latency and throughput values that scale realistically
                    bs = config["batch_size"]
                    prec_factor = 1.0 if config["precision"] == "fp32" else (
                        0.7 if config["precision"] == "fp16" else 0.5  # Faster for lower precision
                    )
                    
                    base_latency_ms = 10.0 * bs * prec_factor
                    latency_ms = base_latency_ms * (1 + random.uniform(-0.1, 0.1))
                    
                    throughput_samples_sec = 1000 * bs / latency_ms
                    
                    # Memory usage scales with batch size and precision
                    memory_mb = model_info["size_bytes"] / 1000000 * (
                        bs / 4  # Memory scales with batch size
                    ) * (1.0 if config["precision"] == "fp32" else 0.5)  # Half for fp16
                    
                    # Per-iteration results
                    iteration_results = []
                    for i in range(iterations):
                        # Add some variance between iterations
                        iter_variance = random.uniform(-0.05, 0.05)
                        iteration_results.append({
                            "iteration": i,
                            "latency_ms": latency_ms * (1 + iter_variance),
                            "throughput_samples_sec": throughput_samples_sec * (1 - iter_variance),
                            "memory_mb": memory_mb * (1 + random.uniform(-0.02, 0.02))
                        })
                    
                    # Overall stats
                    result = {
                        "config_id": config["id"],
                        "batch_size": bs,
                        "precision": config["precision"],
                        "hardware": config["hardware"],
                        "metrics": {
                            "latency_ms": {
                                "mean": latency_ms,
                                "min": min(r["latency_ms"] for r in iteration_results),
                                "max": max(r["latency_ms"] for r in iteration_results),
                                "p50": latency_ms * 0.98,
                                "p95": latency_ms * 1.05,
                                "p99": latency_ms * 1.10
                            },
                            "throughput_samples_sec": {
                                "mean": throughput_samples_sec,
                                "min": min(r["throughput_samples_sec"] for r in iteration_results),
                                "max": max(r["throughput_samples_sec"] for r in iteration_results)
                            },
                            "memory_usage_mb": {
                                "mean": memory_mb,
                                "peak": memory_mb * 1.2
                            }
                        },
                        "iterations": iteration_results
                    }
                    
                    # Add energy metrics if requested
                    if "energy" in metrics:
                        result["metrics"]["energy_joules"] = {
                            "mean": latency_ms * bs * 0.01,  # Simplified energy calculation
                            "total": latency_ms * bs * 0.01 * iterations
                        }
                    
                    results.append(result)
                
                # Generate summary
                best_throughput_config = max(results, key=lambda r: r["metrics"]["throughput_samples_sec"]["mean"])
                best_latency_config = min(results, key=lambda r: r["metrics"]["latency_ms"]["mean"])
                
                summary = {
                    "best_throughput": {
                        "config_id": best_throughput_config["config_id"],
                        "batch_size": best_throughput_config["batch_size"],
                        "precision": best_throughput_config["precision"],
                        "throughput": best_throughput_config["metrics"]["throughput_samples_sec"]["mean"]
                    },
                    "best_latency": {
                        "config_id": best_latency_config["config_id"],
                        "batch_size": best_latency_config["batch_size"],
                        "precision": best_latency_config["precision"],
                        "latency": best_latency_config["metrics"]["latency_ms"]["mean"]
                    },
                    "overall_recommendation": best_throughput_config["config_id"] if benchmark_type == "training" else best_latency_config["config_id"]
                }
                
                # Generate recommendations
                if benchmark_type == "inference":
                    recommendation_text = f"For optimal inference performance, use batch size {best_latency_config['batch_size']} with {best_latency_config['precision']} precision"
                else:
                    recommendation_text = f"For optimal training throughput, use batch size {best_throughput_config['batch_size']} with {best_throughput_config['precision']} precision"
                
                # Complete simulated response
                return {
                    "success": True,
                    "operation": "ai_benchmark_model",
                    "timestamp": current_time,
                    "model_cid": model_cid,
                    "model_info": model_info,
                    "benchmark_type": benchmark_type,
                    "configurations": configurations,
                    "results": results,
                    "summary": summary,
                    "recommendations": {
                        "text": recommendation_text,
                        "recommended_config": best_latency_config if benchmark_type == "inference" else best_throughput_config
                    },
                    "benchmark_duration": sum(len(batch_sizes) * len(precision) * iterations * r["metrics"]["latency_ms"]["mean"] / 1000 for r in results),
                    "simulated": True
                }
            else:
                raise IPFSError("AI/ML integration not available")

        # Build kwargs dictionary with explicit parameters
        kwargs_with_defaults = {
            "benchmark_type": benchmark_type,
            "batch_sizes": batch_sizes,
            "precision": precision,
            "metrics": metrics,
            "iterations": iterations,
            "warmup_iterations": warmup_iterations,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add optional parameters if provided
        if hardware_configs is not None:
            kwargs_with_defaults["hardware_configs"] = hardware_configs
            
        if dataset_cid is not None:
            kwargs_with_defaults["dataset_cid"] = dataset_cid
            
        if input_shapes is not None:
            kwargs_with_defaults["input_shapes"] = input_shapes
            
        if framework is not None:
            kwargs_with_defaults["framework"] = framework
            
        if compiler_options is not None:
            kwargs_with_defaults["compiler_options"] = compiler_options
            
        if execution_providers is not None:
            kwargs_with_defaults["execution_providers"] = execution_providers
            
        if profiling_level is not None:
            kwargs_with_defaults["profiling_level"] = profiling_level
            
        if report_format is not None:
            kwargs_with_defaults["report_format"] = report_format
            
        if distributed:
            kwargs_with_defaults["distributed"] = distributed
            
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout

        # Pass to underlying implementation
        return self.kit.ai_benchmark_model(model_cid=model_cid, **kwargs_with_defaults)

    def ai_deploy_model(
        self, 
        model_cid: str, 
        deployment_config: Dict[str, Any], 
        *, 
        environment: Literal["production", "staging", "development"] = "production",
        wait_for_ready: bool = False,
        endpoint_id: Optional[str] = None,
        auto_scale: bool = True,
        deployment_timeout: Optional[int] = None,
        post_deployment_tests: bool = True,
        monitoring_enabled: bool = True,
        security_config: Optional[Dict[str, Any]] = None,
        network_config: Optional[Dict[str, Any]] = None,
        logging_config: Optional[Dict[str, Any]] = None,
        custom_metrics: Optional[List[Dict[str, Any]]] = None,
        alert_config: Optional[Dict[str, Any]] = None,
        allow_simulation: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Deploy a model to an inference endpoint for online serving.
        
        This method deploys a machine learning model to an inference endpoint for serving,
        configuring the necessary resources, scaling policies, and optimizations. It can
        create new endpoints or update existing ones with new model versions.

        Args:
            model_cid: Content identifier of the model to deploy
            deployment_config: Configuration dictionary for deployment with these keys:
                - name: Name for the deployment/endpoint
                - description: Description of the deployed model service
                - version: Version string for this deployment
                - resources: Resource requirements
                    - cpu: CPU requirements (cores or vCPUs)
                    - memory: Memory requirements (in MB or GB)
                    - gpu: GPU requirements (count and type)
                    - disk: Disk space requirements (in GB)
                - scaling: Scaling configuration for the deployment
                    - min_replicas: Minimum number of replicas
                    - max_replicas: Maximum number of replicas
                    - target_concurrency: Target requests per instance
                - framework: ML framework for the model
                - optimization: Optimization settings
                    - compilation: Whether to compile the model 
                    - precision: Precision mode for deployment
                    - quantization: Whether to quantize the model
            environment: Target deployment environment
                - "production": For production workloads with high reliability
                - "staging": For pre-production testing
                - "development": For development and testing
            wait_for_ready: Whether to wait for deployment to be ready
            endpoint_id: Existing endpoint ID to update with new model
                - If None: Creates a new endpoint
                - If provided: Updates the specified endpoint with new model
            auto_scale: Whether to enable autoscaling based on traffic
            deployment_timeout: Timeout in seconds for deployment operation
            post_deployment_tests: Whether to run health checks after deployment
            monitoring_enabled: Whether to enable performance monitoring
            security_config: Security settings for the endpoint
                - authentication: Authentication method ("none", "api_key", "oauth")
                - encryption: Whether to enable TLS encryption
                - allowed_ips: List of allowed IP addresses/ranges
                - rate_limiting: Rate limiting configuration
            network_config: Network and routing configuration
                - public_access: Whether the endpoint is publicly accessible
                - vpc_config: Virtual Private Cloud configuration
                - cors: Cross-Origin Resource Sharing settings
                - custom_domain: Custom domain name for the endpoint
            logging_config: Logging and monitoring settings
                - log_level: Verbosity level for logs ("debug", "info", "warn", "error")
                - retention_days: Number of days to retain logs
                - request_logging: Whether to log request and response bodies
            custom_metrics: Custom metrics to collect from the deployment
                - Each metric is a dictionary with name, type, and other properties
            alert_config: Alert configuration for the deployment
                - thresholds: Performance thresholds for alerts
                - notification_channels: Where to send alerts
                - schedule: When to check for alert conditions
            allow_simulation: Whether to allow simulated responses if AI/ML integration is unavailable
            **kwargs: Additional implementation-specific parameters

        Returns:
            Dict[str, Any]: Dictionary containing deployment information with these keys:
                - "success": bool indicating if the operation succeeded
                - "operation": Name of the operation ("ai_deploy_model")
                - "timestamp": Time when the operation was performed
                - "endpoint_id": Identifier for the deployed endpoint
                - "endpoint_url": URL for accessing the deployed endpoint
                - "deployment_status": Current status of the deployment
                - "model_cid": CID of the deployed model
                - "deployment_timestamp": When the model was deployed
                - "scaling_status": Current scaling status and configuration
                - "resources": Allocated resources for the deployment
                - "metrics": Initial performance metrics if available
                - "logs_url": URL for accessing deployment logs
                - "monitor_url": URL for monitoring the deployment
                - "estimated_cost": Estimated cost for running the deployment
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSGetError: If the model cannot be retrieved
            IPFSValidationError: If deployment configuration is invalid
            ImportError: If AI/ML integration is not available and allow_simulation=False
        """
        # Validate model_cid
        if not model_cid:
            raise IPFSValidationError("model_cid must not be empty")
            
        # Validate deployment_config
        if not deployment_config:
            raise IPFSValidationError("deployment_config must not be empty")
            
        if not isinstance(deployment_config, dict):
            raise IPFSValidationError("deployment_config must be a dictionary")
            
        # Validate environment
        valid_environments = ["production", "staging", "development"]
        if environment not in valid_environments:
            raise IPFSValidationError(
                f"Invalid environment: {environment}. "
                f"Must be one of: {', '.join(valid_environments)}"
            )
            
        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            if allow_simulation:
                # Return simulated response
                import time
                import random
                import uuid
                
                current_time = time.time()
                
                # Generate a fake endpoint ID if none provided
                endpoint_id_val = endpoint_id or f"endpoint-{uuid.uuid4()}"
                
                # Extract deployment name from config or generate one
                deployment_name = deployment_config.get("name", f"deployment-{model_cid[:8]}")
                
                # Generate domain based on environment and name
                domain_base = "api.example.org" if network_config and network_config.get("custom_domain") else "ai-deploy.ipfs-kit.org"
                endpoint_domain = network_config and network_config.get("custom_domain") or f"{deployment_name}.{environment}.{domain_base}"
                
                # Determine status based on wait_for_ready
                if wait_for_ready:
                    status = "running"
                else:
                    status = random.choice(["deploying", "pending", "scaling_up"])
                
                # Extract resource config or create default
                resource_config = deployment_config.get("resources", {
                    "cpu": "2",
                    "memory": "4Gi",
                    "gpu": "0",
                    "disk": "10Gi"
                })
                
                # Scaling config
                scaling_config = deployment_config.get("scaling", {
                    "min_replicas": 1,
                    "max_replicas": 5,
                    "target_concurrency": 10
                })
                
                # Current scaling status
                current_replicas = scaling_config.get("min_replicas", 1)
                
                # Initial metrics
                metrics = None
                if monitoring_enabled:
                    metrics = {
                        "initialization_time_ms": random.randint(500, 3000),
                        "memory_usage_mb": random.randint(200, 2000),
                        "cpu_usage_percent": random.randint(10, 50),
                        "gpu_memory_usage_mb": 0 if not resource_config.get("gpu") else random.randint(100, 1000)
                    }
                
                # Cost estimation
                cost = {
                    "estimated_hourly_cost": random.uniform(0.1, 2.0),
                    "currency": "USD",
                    "estimate_details": {
                        "compute_cost": random.uniform(0.05, 1.5),
                        "storage_cost": random.uniform(0.01, 0.3),
                        "network_cost": random.uniform(0.01, 0.2)
                    }
                }
                
                # URLs
                logs_url = f"https://logs.{domain_base}/deployments/{endpoint_id_val}"
                monitor_url = f"https://monitor.{domain_base}/deployments/{endpoint_id_val}"
                
                return {
                    "success": True,
                    "operation": "ai_deploy_model",
                    "timestamp": current_time,
                    "endpoint_id": endpoint_id_val,
                    "endpoint_url": f"https://{endpoint_domain}/v1/predict",
                    "deployment_status": status,
                    "model_cid": model_cid,
                    "deployment_name": deployment_name,
                    "environment": environment,
                    "deployment_timestamp": current_time,
                    "scaling_status": {
                        "current_replicas": current_replicas,
                        "target_replicas": current_replicas,
                        "min_replicas": scaling_config.get("min_replicas", 1),
                        "max_replicas": scaling_config.get("max_replicas", 5),
                        "target_concurrency": scaling_config.get("target_concurrency", 10),
                        "auto_scaling": auto_scale
                    },
                    "resources": resource_config,
                    "metrics": metrics,
                    "logs_url": logs_url,
                    "monitor_url": monitor_url,
                    "estimated_cost": cost,
                    "simulated": True
                }
            else:
                raise IPFSError("AI/ML integration not available")

        # Build kwargs dictionary with explicit parameters
        kwargs_with_defaults = {
            "environment": environment,
            "wait_for_ready": wait_for_ready,
            "auto_scale": auto_scale,
            "post_deployment_tests": post_deployment_tests,
            "monitoring_enabled": monitoring_enabled,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add optional parameters if provided
        if endpoint_id is not None:
            kwargs_with_defaults["endpoint_id"] = endpoint_id
            
        if deployment_timeout is not None:
            kwargs_with_defaults["deployment_timeout"] = deployment_timeout
            
        if security_config is not None:
            kwargs_with_defaults["security_config"] = security_config
            
        if network_config is not None:
            kwargs_with_defaults["network_config"] = network_config
            
        if logging_config is not None:
            kwargs_with_defaults["logging_config"] = logging_config
            
        if custom_metrics is not None:
            kwargs_with_defaults["custom_metrics"] = custom_metrics
            
        if alert_config is not None:
            kwargs_with_defaults["alert_config"] = alert_config

        # Pass to underlying implementation
        return self.kit.ai_deploy_model(
            model_cid=model_cid, deployment_config=deployment_config, **kwargs_with_defaults
        )

    def ai_optimize_model(
        self, 
        model_cid: str, 
        *, 
        target_platform: str = "cpu",
        optimization_level: str = "O1",
        quantization: Union[bool, str] = False,
        precision: Optional[str] = None,
        max_batch_size: Optional[int] = None,
        dynamic_shapes: bool = False,
        timeout: Optional[int] = None,
        evaluation_dataset_cid: Optional[str] = None,
        calibration_dataset_cid: Optional[str] = None,
        preserve_accuracy: bool = True,
        source_framework: Optional[str] = None,
        allow_custom_ops: bool = False,
        allow_simulation: bool = True,
        optimization_config: Optional[Dict[str, Any]] = None,
        compute_resource_limit: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Optimize a model for inference performance or deployment efficiency.
        
        This method applies various optimization techniques to machine learning models
        to improve inference speed, reduce memory footprint, or enable deployment on
        specific hardware targets. Common optimizations include quantization, pruning,
        operator fusion, and platform-specific optimizations.

        Args:
            model_cid: Content identifier of the model to optimize
            target_platform: Target hardware platform for optimization
                - "cpu": General CPU optimization
                - "gpu": GPU acceleration (CUDA/ROCm)
                - "tpu": Tensor Processing Unit optimization
                - "mobile": Mobile device optimization
                - "web": WebAssembly/WebGL optimization
                - "edge": Edge device optimization
                - "custom": Custom target (specify in optimization_config)
            optimization_level: Optimization aggressiveness level
                - "O0": No optimization (debugging)
                - "O1": Conservative optimizations (safest)
                - "O2": Balanced optimizations
                - "O3": Aggressive optimizations (best performance)
            quantization: Whether to perform quantization to reduce model size
                - False: No quantization
                - True: Default quantization
                - "int8": 8-bit integer quantization
                - "int4": 4-bit integer quantization
                - "fp16": 16-bit floating point
            precision: Numerical precision for quantization
                - "fp32": 32-bit floating point
                - "fp16": 16-bit floating point
                - "bf16": Brain floating point format
                - "int8": 8-bit integer quantization
            max_batch_size: Maximum batch size to optimize for
            dynamic_shapes: Whether to support dynamic input shapes
            timeout: Timeout for optimization process in seconds
            evaluation_dataset_cid: CID of dataset to use for accuracy evaluation
            calibration_dataset_cid: CID of dataset to use for quantization calibration
            preserve_accuracy: Whether to prioritize accuracy over performance
            source_framework: Framework the source model belongs to
                - If None: Automatically detected from model format
            allow_custom_ops: Whether to allow custom operators in the optimized model
            allow_simulation: Whether to allow simulated responses when AI/ML integration is unavailable
            optimization_config: Additional configuration dictionary for advanced optimization settings
                - target_format: Target format for optimization 
                    - Examples: "onnx", "tensorrt", "openvino", "coreml", "tflite"
                - optimizations: List of specific optimizations to apply
                    - Examples: "pruning", "distillation", "fusion"
                - compression: Compression settings
                    - Examples: "pruning_level", "weight_sharing", "huffman_coding"
            compute_resource_limit: Maximum resources to use for optimization
                - cpu_cores: Maximum CPU cores to use
                - memory_gb: Maximum memory in GB to use
                - gpu_memory_gb: Maximum GPU memory to use
            **kwargs: Additional implementation-specific parameters
                - backend_config: Backend-specific optimization parameters
                - fallback_operations: List of operations to exclude from optimization
                - benchmark_after_optimization: Whether to benchmark after optimization
                - save_intermediate_results: Whether to save intermediate models
                - compile_options: Additional options for model compilation

        Returns:
            Dict[str, Any]: Dictionary containing optimization results with these keys:
                - "success": bool indicating if the operation succeeded
                - "operation": The name of the operation ("ai_optimize_model")
                - "timestamp": Time when the operation was performed
                - "original_cid": CID of the original model
                - "optimized_cid": CID of the optimized model
                - "target_platform": Hardware platform the model is optimized for
                - "optimization_level": Level of optimization applied
                - "quantization": Quantization type if applied
                - "metrics": Performance improvement metrics
                    - size_reduction: Percentage reduction in model size
                    - latency_improvement: Percentage improvement in inference speed
                    - memory_footprint_reduction: Reduction in memory usage
                    - original_size_bytes: Size of the original model
                    - optimized_size_bytes: Size of the optimized model
                - "accuracy_impact": Effect on model accuracy if evaluated
                - "optimization_time": Time taken for optimization in seconds
                
        Raises:
            IPFSError: Base class for all IPFS-related errors
            IPFSGetError: If the model cannot be retrieved
            IPFSValidationError: If optimization configuration is invalid
            ImportError: If AI/ML integration is not available
            ValueError: If parameters are invalid
        """
        # Parameter validation for critical parameters
        valid_platforms = ["cpu", "gpu", "tpu", "mobile", "web", "edge", "custom"]
        if target_platform not in valid_platforms:
            raise ValueError(f"Invalid target_platform: {target_platform}. Must be one of: {', '.join(valid_platforms)}")

        valid_opt_levels = ["O0", "O1", "O2", "O3"]
        if optimization_level not in valid_opt_levels:
            raise ValueError(f"Invalid optimization_level: {optimization_level}. Must be one of: {', '.join(valid_opt_levels)}")
        
        # Handle simulation case for when AI/ML is not available
        if not AI_ML_AVAILABLE:
            if not allow_simulation:
                return {
                    "success": False,
                    "operation": "ai_optimize_model",
                    "timestamp": time.time(),
                    "error": "AI/ML integration not available and simulation not allowed",
                    "error_type": "IntegrationUnavailableError"
                }
                
            # Return simulated response
            return {
                "success": True,
                "operation": "ai_optimize_model",
                "timestamp": time.time(),
                "original_cid": model_cid,
                "optimized_cid": f"Qm{os.urandom(16).hex()}",
                "target_platform": target_platform,
                "optimization_level": optimization_level,
                "quantization": quantization,
                "precision": precision,
                "max_batch_size": max_batch_size,
                "dynamic_shapes": dynamic_shapes,
                "metrics": {
                    "size_reduction": "45%",
                    "latency_improvement": "30%",
                    "original_size_bytes": 2458000,
                    "optimized_size_bytes": 1351900,
                    "memory_footprint_reduction": "40%"
                },
                "accuracy_impact": "negligible",
                "optimization_time": 15.2,
                "simulation_note": "AI/ML integration not available, using simulated response"
            }

        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "target_platform": target_platform,
            "optimization_level": optimization_level,
            "quantization": quantization,
            "preserve_accuracy": preserve_accuracy,
            "allow_custom_ops": allow_custom_ops,
            "dynamic_shapes": dynamic_shapes,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add optional parameters if provided
        if precision is not None:
            kwargs_with_defaults["precision"] = precision
        if max_batch_size is not None:
            kwargs_with_defaults["max_batch_size"] = max_batch_size
        if timeout is not None:
            kwargs_with_defaults["timeout"] = timeout
        if compute_resource_limit is not None:
            kwargs_with_defaults["compute_resource_limit"] = compute_resource_limit
        if evaluation_dataset_cid is not None:
            kwargs_with_defaults["evaluation_dataset_cid"] = evaluation_dataset_cid
        if calibration_dataset_cid is not None:
            kwargs_with_defaults["calibration_dataset_cid"] = calibration_dataset_cid
        if source_framework is not None:
            kwargs_with_defaults["source_framework"] = source_framework
        
        # Create optimization config if not provided
        if optimization_config is None:
            optimization_config = {
                "target_hardware": target_platform,
                "optimizations": []
            }
            # Add quantization if specified
            if quantization:
                optimization_config["optimizations"].append("quantization")
                optimization_config["precision"] = precision if precision else ("int8" if quantization == True else quantization)
        
        try:
            # Forward to underlying implementation
            result = self.kit.ai_optimize_model(
                model_cid=model_cid, 
                optimization_config=optimization_config, 
                **kwargs_with_defaults
            )
            
            # Ensure result has operation and timestamp for consistency
            if "operation" not in result:
                result["operation"] = "ai_optimize_model"
            if "timestamp" not in result:
                result["timestamp"] = time.time()
                
            return result
            
        except Exception as e:
            logger.error(f"Error optimizing model: {str(e)}")
            return {
                "success": False,
                "operation": "ai_optimize_model",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "model_cid": model_cid
            }
        

    def hybrid_search(
        self,
        *,
        query_text: Optional[str] = None,
        query_vector: Optional[List[float]] = None,
        metadata_filters: Optional[List[Tuple[str, str, Any]]] = None,
        entity_types: Optional[List[str]] = None,
        hop_count: int = 1,
        top_k: int = 10,
        similarity_threshold: float = 0.0,
        search_mode: str = "hybrid",
        rerank_results: bool = False,
        generate_llm_context: bool = False,
        format_type: str = "text",
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Perform hybrid search combining metadata filtering, vector similarity, and graph traversal.
        
        This method integrates the Arrow metadata index with the IPLD Knowledge Graph
        to provide a unified search experience that combines efficient metadata
        filtering with semantic vector search and graph traversal, delivering highly
        relevant results for complex queries.

        Args:
            query_text: Text query for semantic search
                - If provided alone: Will be converted to a vector embedding
                - If provided with query_vector: Used for filtering and result display
            query_vector: Vector embedding for similarity search 
                - If provided alone: Used directly for vector similarity
                - If provided with query_text: Used as-is without re-encoding query_text
            metadata_filters: List of filters in format [(field, op, value)]
                - field: Field name to filter on
                - op: Operator ("==", "!=", ">", "<", ">=", "<=", "in", "contains")
                - value: Value to filter by
                - Example: [("tags", "contains", "ai"), ("size", ">", 1000)]
            entity_types: List of entity types to include in results
                - Examples: ["model", "dataset", "document", "code"]
                - If None: All entity types are included
            hop_count: Number of graph traversal hops for related entities
                - Higher values explore more of the graph but increase search time
            top_k: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0.0-1.0) for inclusion
            search_mode: Type of search to perform
                - "hybrid": Combines vector, metadata, and graph (default)
                - "vector": Vector similarity only
                - "metadata": Metadata filtering only
                - "graph": Graph traversal focused
            rerank_results: Whether to rerank results using a cross-encoder model
            generate_llm_context: Whether to generate formatted context for LLMs
            format_type: Format for LLM context if generated
                - "text": Plain text format
                - "json": JSON structure
                - "markdown": Markdown format with headers
            timeout: Operation timeout in seconds
            **kwargs: Additional implementation-specific parameters
                - embedding_model: Model to use for embedding generation
                - max_tokens_per_doc: Maximum tokens to include per document
                - exclude_fields: Fields to exclude from results
                - include_fields: Fields to include in results (overrides exclude_fields)
                - cache_vectors: Whether to cache generated vectors
                - debug_info: Whether to include debug information in results

        Returns:
            Dict[str, Any]: Dictionary containing search results with these keys:
                - "success": bool indicating if the operation succeeded
                - "results": List of search results with their metadata and scores
                    - Each result contains entity information and similarity score
                - "result_count": Number of results returned
                - "query": Original text query if provided
                - "search_stats": Statistics about the search operation
                    - "time_ms": Total search time in milliseconds
                    - "nodes_explored": Number of graph nodes explored
                    - "metadata_filter_time_ms": Time spent on metadata filtering
                    - "vector_search_time_ms": Time spent on vector search
                - "llm_context": Formatted context for LLMs (if requested)
                
        Raises:
            IPFSError: If integrated search is not available
            ValueError: If both query_text and query_vector are None
            ImportError: If required components are missing
        """
        if not INTEGRATED_SEARCH_AVAILABLE:
            raise IPFSError(
                "Integrated search not available. Make sure integrated_search module is accessible."
            )

        # Import the necessary components
        from .integrated_search import MetadataEnhancedGraphRAG

        try:
            # Update kwargs with explicit parameters
            kwargs_with_defaults = {
                "search_mode": search_mode,
                "similarity_threshold": similarity_threshold,
                "rerank_results": rerank_results,
                **kwargs  # Any additional kwargs override the defaults
            }
            
            # Add timeout if provided
            if timeout is not None:
                kwargs_with_defaults["timeout"] = timeout

            # Initialize the integrated search component
            enhanced_rag = MetadataEnhancedGraphRAG(ipfs_client=self.kit)

            # Perform the search
            results = enhanced_rag.hybrid_search(
                query_text=query_text,
                query_vector=query_vector,
                metadata_filters=metadata_filters,
                entity_types=entity_types,
                hop_count=hop_count,
                top_k=top_k,
                **kwargs_with_defaults
            )

            # Create the base response
            response = {
                "success": True,
                "results": results,
                "result_count": len(results),
                "query": query_text,
                "search_stats": enhanced_rag.get_last_search_stats()
            }

            # Generate LLM context if requested
            if generate_llm_context:
                context = enhanced_rag.generate_llm_context(
                    query=query_text or "User query",
                    search_results=results,
                    format_type=format_type,
                )
                response["llm_context"] = context

            return response

        except Exception as e:
            return {
                "success": False, 
                "error": str(e), 
                "error_type": type(e).__name__,
                "query": query_text
            }

    def load_embedding_model(
        self,
        *,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        model_type: str = "sentence-transformer",
        use_ipfs_cache: bool = True,
        device: Optional[str] = None,
        normalize_embeddings: bool = True,
        max_seq_length: Optional[int] = None,
        trust_remote_code: bool = False,
        revision: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Load a custom embedding model from Hugging Face Hub, with IPFS caching.

        This method provides access to state-of-the-art embedding models from
        Hugging Face, with efficient caching in IPFS for distributed access.
        Models can be used for generating vector embeddings for semantic search.

        Args:
            model_name: Name of the Hugging Face model to use
            model_type: Type of model ("sentence-transformer", "transformers", "clip")
            use_ipfs_cache: Whether to cache the model in IPFS for distribution
            device: Device to run the model on ("cpu", "cuda", "cuda:0", etc.)
            normalize_embeddings: Whether to normalize embedding vectors to unit length
            max_seq_length: Maximum sequence length for tokenizer (model-specific default if None)
            trust_remote_code: Whether to trust remote code when loading models
            revision: Specific model revision to load (e.g., commit hash or branch name)
            **kwargs: Additional model-specific parameters for initialization

        Returns:
            Dictionary with operation result including the embedding model and information:
                - "success": Whether the operation succeeded
                - "model": The loaded embedding model instance, if successful
                - "model_info": Dictionary with model information:
                    - "model_name": Name of the loaded model
                    - "model_type": Type of the model
                    - "vector_dimension": Dimension of the embedding vectors
                    - "model_cid": CID of the cached model in IPFS
                    - "device": Device the model is loaded on
                    - "cached_in_ipfs": Whether the model is cached in IPFS
                - "message": Success message with model name
                - "error": Error message if operation failed
                - "error_type": Type of error if operation failed
        """
        if not AI_ML_AVAILABLE:
            return {
                "success": False,
                "error": "AI/ML integration not available",
                "error_type": "ImportError",
            }

        try:
            # Import the necessary components
            from .ai_ml_integration import CustomEmbeddingModel

            logger.info(f"Loading embedding model {model_name} of type {model_type}")

            # Update kwargs with explicit parameters
            kwargs_with_defaults = {
                "model_name": model_name,
                "model_type": model_type,
                "use_ipfs_cache": use_ipfs_cache,
                "normalize_embeddings": normalize_embeddings,
                "trust_remote_code": trust_remote_code,
                **kwargs  # Any additional kwargs override the defaults
            }
            
            # Add optional parameters if provided
            if device is not None:
                kwargs_with_defaults["device"] = device
                
            if max_seq_length is not None:
                kwargs_with_defaults["max_seq_length"] = max_seq_length
                
            if revision is not None:
                kwargs_with_defaults["revision"] = revision

            # Create the embedding model
            embedding_model = CustomEmbeddingModel(
                ipfs_client=self.kit,
                **kwargs_with_defaults
            )

            # Get model information
            model_info = {
                "model_name": embedding_model.model_name,
                "model_type": embedding_model.model_type,
                "vector_dimension": embedding_model.vector_dim,
                "model_cid": embedding_model.model_cid,
                "device": embedding_model.device or "cpu",
                "cached_in_ipfs": embedding_model.model_cid is not None,
            }

            return {
                "success": True,
                "model": embedding_model,
                "model_info": model_info,
                "message": f"Successfully loaded {model_name}",
            }

        except Exception as e:
            return {"success": False, "error": str(e), "error_type": type(e).__name__}

    def generate_embeddings(
        self,
        texts: Union[str, List[str]],
        *,
        model: Optional[Any] = None,
        model_name: Optional[str] = None,
        batch_size: int = 32,
        normalize: bool = True,
        output_format: str = "numpy",
        show_progress: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate vector embeddings for text using a Hugging Face model.

        This method converts text to vector embeddings that can be used for
        semantic search, clustering, and other NLP tasks. It supports both
        single texts and batches of texts for efficient processing.

        Args:
            texts: Text string or list of text strings to embed
            model: Optional custom embedding model instance (from load_embedding_model)
            model_name: Optional name of model to load if model not provided
            batch_size: Batch size for efficient processing of multiple texts
            normalize: Whether to normalize embedding vectors to unit length
            output_format: Format for the embeddings ("numpy", "list", "tensor")
            show_progress: Whether to display a progress bar during processing
            **kwargs: Additional parameters passed to the embedding model

        Returns:
            Dictionary with operation result including embeddings:
                - "success": Whether the operation succeeded
                - "embedding": Vector for a single input text
                - "embeddings": List of vectors for multiple input texts
                - "count": Number of embeddings generated 
                - "dimension": Dimensionality of embedding vectors
                - "model_name": Name of the model used
                - "output_format": Format of the embedding vectors
                - "error": Error message if operation failed
                - "error_type": Type of error if operation failed
        """
        if not AI_ML_AVAILABLE:
            return {
                "success": False,
                "error": "AI/ML integration not available",
                "error_type": "ImportError",
            }

        try:
            # Handle single text vs list of texts
            is_single = isinstance(texts, str)
            texts_list = [texts] if is_single else texts

            # Get or create embedding model
            embedding_model = model
            if embedding_model is None:
                # Try to load specified model or default
                # Update kwargs with the explicit parameters
                load_kwargs = {
                    "model_name": model_name or "sentence-transformers/all-MiniLM-L6-v2",
                    "normalize_embeddings": normalize,
                    **{k: v for k, v in kwargs.items() if k not in ["normalize", "output_format", "show_progress"]}
                }
                model_result = self.load_embedding_model(**load_kwargs)
                if not model_result["success"]:
                    return model_result
                embedding_model = model_result["model"]

            # Generate embeddings with batch processing and progress bar if requested
            generation_kwargs = {
                "batch_size": batch_size,
                "normalize": normalize,
                "output_format": output_format,
                "show_progress": show_progress
            }
            
            # Add any additional kwargs
            for k, v in kwargs.items():
                if k not in generation_kwargs:
                    generation_kwargs[k] = v
                    
            embeddings = embedding_model.generate_embeddings(texts_list, **generation_kwargs)

            # Prepare result dictionary with common fields
            result = {
                "success": True,
                "model_name": embedding_model.model_name,
                "output_format": output_format,
                "dimension": len(embeddings[0]) if embeddings else 0,
            }
            
            # Return appropriate result format based on input type
            if is_single:
                result["embedding"] = embeddings[0]
            else:
                result["embeddings"] = embeddings
                result["count"] = len(embeddings)
                
            return result

        except Exception as e:
            return {"success": False, "error": str(e), "error_type": type(e).__name__}

    def create_search_connector(
        self, 
        *,
        model_registry: Optional[Any] = None,
        dataset_manager: Optional[Any] = None,
        embedding_model: Optional[Any] = None,
        embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        embedding_model_type: str = "sentence-transformer",
        enable_caching: bool = True,
        cache_ttl: int = 3600,
        search_timeout: int = 60,
        connector_name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create an AI/ML search connector for integrated search capabilities.

        This creates a connector that bridges our hybrid search capabilities with
        AI/ML frameworks like Langchain and LlamaIndex, enabling specialized search
        for models, datasets, and AI assets.

        Args:
            model_registry: Optional existing ModelRegistry instance
            dataset_manager: Optional existing DatasetManager instance
            embedding_model: Optional custom embedding model instance
            embedding_model_name: Name of Hugging Face model to use for embeddings
            embedding_model_type: Type of model to use for embeddings
            enable_caching: Whether to cache search results for performance
            cache_ttl: Time-to-live for cached results in seconds
            search_timeout: Timeout for search operations in seconds
            connector_name: Optional name for the search connector instance
            **kwargs: Additional configuration parameters for the connector

        Returns:
            Dictionary with operation result including search connector:
                - "success": Whether the operation succeeded
                - "connector": The search connector instance, if successful
                - "message": Success message, if successful
                - "error": Error message if operation failed
                - "error_type": Type of error if operation failed
                - "configuration": Dictionary of the connector's configuration
        """
        if not INTEGRATED_SEARCH_AVAILABLE or not AI_ML_AVAILABLE:
            raise IPFSError("Integrated search or AI/ML integration not available")

        try:
            # Import necessary components
            from .integrated_search import AIMLSearchConnector, MetadataEnhancedGraphRAG

            # Create the hybrid search instance
            hybrid_search = MetadataEnhancedGraphRAG(ipfs_client=self.kit)

            # Update kwargs with explicit parameters
            kwargs_with_defaults = {
                "ipfs_client": self.kit,
                "hybrid_search": hybrid_search,
                "model_registry": model_registry,
                "dataset_manager": dataset_manager,
                "embedding_model": embedding_model,
                "embedding_model_name": embedding_model_name,
                "embedding_model_type": embedding_model_type,
                "enable_caching": enable_caching,
                "cache_ttl": cache_ttl,
                "search_timeout": search_timeout,
                **kwargs  # Any additional kwargs override the defaults
            }
            
            # Add connector name if provided
            if connector_name is not None:
                kwargs_with_defaults["connector_name"] = connector_name

            # Create the AI/ML search connector
            connector = AIMLSearchConnector(**kwargs_with_defaults)

            # Build configuration dictionary for return value
            configuration = {
                "embedding_model_name": embedding_model_name,
                "embedding_model_type": embedding_model_type,
                "enable_caching": enable_caching,
                "cache_ttl": cache_ttl,
                "search_timeout": search_timeout,
                "connector_name": connector_name or f"connector-{id(connector)}"
            }

            return {
                "success": True,
                "connector": connector,
                "message": "AI/ML search connector created successfully",
                "configuration": configuration
            }
        except Exception as e:
            return {"success": False, "error": str(e), "error_type": type(e).__name__}

    def create_search_benchmark(
        self, 
        *,
        output_dir: Optional[str] = None,
        search_connector: Optional[Any] = None,
        benchmark_name: Optional[str] = None,
        num_runs_default: int = 5,
        include_visualization: bool = True,
        save_raw_data: bool = True,
        generate_report: bool = True,
        report_format: str = "markdown",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a search benchmarking tool for performance testing.

        This creates a benchmarking tool that can measure the performance of
        different search strategies in the integrated search system, helping
        users optimize their query patterns.

        Args:
            output_dir: Directory for benchmark results (default: ~/.ipfs_benchmarks)
            search_connector: Optional existing AIMLSearchConnector instance
            benchmark_name: Optional name for the benchmark run set
            num_runs_default: Default number of runs for each benchmark test
            include_visualization: Whether to generate visualization plots
            save_raw_data: Whether to save the raw benchmark data
            generate_report: Whether to generate a benchmark report
            report_format: Format for the report output ("markdown", "html", "json")
            **kwargs: Additional configuration parameters for the benchmark

        Returns:
            Dictionary with operation result including benchmark tool:
                - "success": Whether the operation succeeded
                - "benchmark": The benchmark tool instance, if successful
                - "message": Success message, if successful
                - "error": Error message if operation failed
                - "error_type": Type of error if operation failed
                - "configuration": Dictionary of the benchmark configuration
        """
        if not INTEGRATED_SEARCH_AVAILABLE:
            raise IPFSError("Integrated search not available")

        try:
            # Import necessary components
            from .integrated_search import MetadataEnhancedGraphRAG, SearchBenchmark

            # Update kwargs with explicit parameters
            kwargs_with_defaults = {
                "ipfs_client": self.kit,
                "search_connector": search_connector,
                "num_runs_default": num_runs_default,
                "include_visualization": include_visualization,
                "save_raw_data": save_raw_data,
                "generate_report": generate_report,
                "report_format": report_format,
                **kwargs  # Any additional kwargs override the defaults
            }
            
            # Add optional parameters if provided
            if output_dir is not None:
                kwargs_with_defaults["output_dir"] = output_dir
                
            if benchmark_name is not None:
                kwargs_with_defaults["benchmark_name"] = benchmark_name

            # Create the benchmark tool
            benchmark = SearchBenchmark(**kwargs_with_defaults)

            # Build configuration dictionary for return value
            configuration = {
                "output_dir": output_dir or benchmark.output_dir,
                "benchmark_name": benchmark_name or benchmark.benchmark_name,
                "num_runs_default": num_runs_default,
                "include_visualization": include_visualization,
                "save_raw_data": save_raw_data,
                "generate_report": generate_report,
                "report_format": report_format
            }

            return {
                "success": True,
                "benchmark": benchmark,
                "message": "Search benchmark tool created successfully",
                "configuration": configuration
            }

        except Exception as e:
            return {"success": False, "error": str(e), "error_type": type(e).__name__}

    def run_search_benchmark(
        self, 
        *,
        benchmark_type: str = "full", 
        num_runs: int = 5, 
        output_dir: Optional[str] = None,
        save_results: bool = True,
        custom_filters: Optional[List[Any]] = None,
        custom_queries: Optional[List[str]] = None,
        custom_test_cases: Optional[List[Dict[str, Any]]] = None,
        benchmark_name: Optional[str] = None,
        include_visualization: bool = True,
        search_connector: Optional[Any] = None,
        compare_with_previous: bool = False,
        include_system_info: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run performance benchmarks for the integrated search system.

        This method measures the performance characteristics of different search
        strategies, helping users optimize their query patterns and understand
        the performance implications of different search approaches.

        Args:
            benchmark_type: Type of benchmark to run ("full", "metadata", "vector", "hybrid")
            num_runs: Number of times to run each benchmark
            output_dir: Directory to save benchmark results
            save_results: Whether to save results to disk
            custom_filters: Custom metadata filters for metadata benchmark
            custom_queries: Custom text queries for vector benchmark
            custom_test_cases: Custom test cases for hybrid benchmark
            benchmark_name: Optional name for this benchmark run
            include_visualization: Whether to generate visualization plots
            search_connector: Optional existing search connector to use
            compare_with_previous: Whether to compare with previous benchmark runs
            include_system_info: Whether to include system information in the report
            **kwargs: Additional parameters for the benchmark

        Returns:
            Dictionary with benchmark results and statistics:
                - "success": Whether the operation succeeded
                - "benchmark_type": Type of benchmark that was run
                - "results": Dictionary of benchmark results by test case
                - "summary": Summary statistics across all test cases
                - "visualization_paths": Paths to generated visualization files
                - "report_path": Path to the generated report file
                - "error": Error message if operation failed
                - "error_type": Type of error if operation failed
                - "benchmark_id": Unique identifier for this benchmark run
        """
        if not INTEGRATED_SEARCH_AVAILABLE:
            raise IPFSError("Integrated search not available")

        # Validation of benchmark_type already moved to parameter declaration with typing

        # Check that benchmark_type is valid
        if benchmark_type not in ["full", "metadata", "vector", "hybrid"]:
            raise IPFSValidationError(f"Unknown benchmark type: {benchmark_type}")

        try:
            # Import necessary components
            from .integrated_search import SearchBenchmark

            # Update benchmark params with explicit parameters
            benchmark_params = {
                "ipfs_client": self.kit,
                "num_runs_default": num_runs,
                "include_visualization": include_visualization,
                "save_raw_data": save_results,
                "include_system_info": include_system_info
            }
            
            # Add optional parameters if provided
            if output_dir is not None:
                benchmark_params["output_dir"] = output_dir
                
            if benchmark_name is not None:
                benchmark_params["benchmark_name"] = benchmark_name
                
            if search_connector is not None:
                benchmark_params["search_connector"] = search_connector

            # Create benchmark instance
            benchmark = SearchBenchmark(**benchmark_params)

            # Set up run parameters
            run_params = {
                "num_runs": num_runs,
                "save_results": save_results,
                "compare_with_previous": compare_with_previous,
                **kwargs  # Forward any additional parameters
            }
            
            # Run the requested benchmark
            if benchmark_type == "full":
                # Run full benchmark suite
                results = benchmark.run_full_benchmark_suite(**run_params)

            elif benchmark_type == "metadata":
                # Run metadata search benchmark
                results = benchmark.benchmark_metadata_search(
                    filters_list=custom_filters, **run_params
                )

            elif benchmark_type == "vector":
                # Run vector search benchmark
                results = benchmark.benchmark_vector_search(
                    queries=custom_queries, **run_params
                )

            else:  # hybrid
                # Run hybrid search benchmark
                results = benchmark.benchmark_hybrid_search(
                    test_cases=custom_test_cases, **run_params
                )

            # Generate report and visualizations only if requested
            report_path = None
            visualization_paths = []
            
            if include_visualization:
                visualization_paths = benchmark.generate_visualizations(results)
                
            # Generate report if requested
            if kwargs.get("generate_report", True):
                report_path = benchmark.generate_benchmark_report(
                    results, 
                    format=kwargs.get("report_format", "markdown"),
                    include_visualizations=include_visualization
                )

            # Build enhanced result dictionary
            summary = {
                "total_test_cases": len(results),
                "average_latency_ms": benchmark.calculate_average_latency(results),
                "max_latency_ms": benchmark.get_max_latency(results),
                "min_latency_ms": benchmark.get_min_latency(results),
                "total_runtime_seconds": benchmark.calculate_total_runtime(results),
                "benchmark_completed_at": time.time(),
            }
            
            if compare_with_previous and hasattr(benchmark, "comparison_results"):
                summary["comparison"] = benchmark.comparison_results
                
            # Return comprehensive results with report and visualization information
            return {
                "success": True,
                "benchmark_type": benchmark_type,
                "benchmark_id": benchmark.benchmark_id,
                "results": results,
                "summary": summary,
                "report_path": report_path,
                "visualization_paths": visualization_paths,
                "output_directory": benchmark.output_dir,
                "benchmark_name": benchmark.benchmark_name,
                "run_configuration": {
                    "num_runs": num_runs,
                    "save_results": save_results,
                    "include_visualization": include_visualization,
                    "compare_with_previous": compare_with_previous
                }
            }

        except Exception as e:
            return {"success": False, "error": str(e), "error_type": type(e).__name__}

    def call_extension(
        self, 
        extension_name: str, 
        *args,
        **kwargs
    ) -> Any:
        """
        Call a registered extension function by name.

        This method invokes an extension function that was previously registered
        with the API using register_extension().

        Args:
            extension_name: Name of the extension to call
            *args: Positional arguments to pass to the extension function
            **kwargs: Keyword arguments to pass to the extension function

        Returns:
            Any: Result from the extension function, type depends on the specific extension

        Raises:
            IPFSError: If the extension is not found
            Exception: Any exception raised by the extension function
        """
        if extension_name not in self.extensions:
            raise IPFSError(f"Extension not found: {extension_name}")

        extension_func = self.extensions[extension_name]
        
        try:
            return extension_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error calling extension '{extension_name}': {str(e)}")
            raise

    def open_file(
        self, 
        path: str,
        *,
        mode: str = "rb",
        buffer_size: Optional[int] = None,
        cache_type: Optional[str] = None,
        compression: Optional[str] = None,
        encoding: Optional[str] = None,
        errors: Optional[str] = None,
        **kwargs
    ) -> Union[BinaryIO, IOBase]:
        """
        Open a file in IPFS through the FSSpec interface.

        This method provides a convenient way to open files directly, similar to
        Python's built-in open() function.

        Args:
            path: Path or CID to open, can use ipfs:// schema
            mode: Mode to open the file in, currently only read modes are supported
                Valid values: "rb" (binary read) or "r" (text read)
            buffer_size: Size of buffer for buffered reading
            cache_type: Type of cache to use (None, "readahead", "mmap", etc.)
            compression: Compression format to use (None, "gzip", "bz2", etc.)  
            encoding: Text encoding when using text mode (default: 'utf-8')
            errors: How to handle encoding errors (default: 'strict')
            **kwargs: Additional options passed to the underlying filesystem

        Returns:
            Union[BinaryIO, IOBase]: File-like object for the IPFS content
                - If mode="rb": Returns a binary file-like object
                - If mode="r": Returns a text file-like object

        Raises:
            ImportError: If FSSpec is not available
            IPFSError: If the file cannot be opened
            ValueError: If an invalid mode is specified

        Example:
            ```python
            # Open a file by CID
            with api.open_file("QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx") as f:
                content = f.read()

            # Open with ipfs:// URL
            with api.open_file("ipfs://QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx") as f:
                content = f.read()
                
            # Open as text
            with api.open_file(
                "QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx", 
                mode="r", 
                encoding="utf-8"
            ) as f:
                text = f.read()
            ```
        """
        # Validate mode
        if not mode.startswith("r"):
            raise ValueError(f"Unsupported mode: {mode}. Only read modes are supported.")
            
        # Update kwargs with explicit parameters
        kwargs_with_defaults = kwargs.copy()
        if buffer_size is not None:
            kwargs_with_defaults["buffer_size"] = buffer_size
        if cache_type is not None:
            kwargs_with_defaults["cache_type"] = cache_type
        if compression is not None:
            kwargs_with_defaults["compression"] = compression
        if encoding is not None:
            kwargs_with_defaults["encoding"] = encoding
        if errors is not None:
            kwargs_with_defaults["errors"] = errors
            
        # Initialize filesystem if needed
        if not self.fs:
            self.fs = self.get_filesystem(**kwargs)

        if not self.fs:
            raise ImportError("FSSpec filesystem interface is not available")

        # Ensure path has ipfs:// prefix if it's a CID
        if not path.startswith("ipfs://") and not path.startswith("/"):
            path = f"ipfs://{path}"

        try:
            return self.fs.open(path, mode=mode, **kwargs_with_defaults)
        except Exception as e:
            logger.error(f"Error opening file {path}: {str(e)}")
            raise IPFSError(f"Failed to open file: {str(e)}") from e

    def read_file(
        self, 
        path: str,
        *,
        compression: Optional[str] = None,
        buffer_size: Optional[int] = None,
        cache_type: Optional[str] = None,
        max_size: Optional[int] = None,
        **kwargs
    ) -> bytes:
        """
        Read the entire contents of a file from IPFS.

        Args:
            path: Path or CID of the file to read
            compression: Compression format if file is compressed (None, "gzip", "bz2", etc.)
            buffer_size: Size of buffer for buffered reading
            cache_type: Type of cache to use (None, "readahead", "mmap", etc.)
            max_size: Maximum size in bytes to read (None for no limit)
            **kwargs: Additional options passed to the filesystem

        Returns:
            bytes: Contents of the file as bytes
            
        Raises:
            IPFSError: If the file cannot be read
            ImportError: If FSSpec is not available
        """
        # Update kwargs with explicit parameters
        kwargs_with_defaults = kwargs.copy()
        if compression is not None:
            kwargs_with_defaults["compression"] = compression
        if buffer_size is not None:
            kwargs_with_defaults["buffer_size"] = buffer_size
        if cache_type is not None:
            kwargs_with_defaults["cache_type"] = cache_type
            
        try:
            with self.open_file(path, **kwargs_with_defaults) as f:
                if max_size is not None:
                    return f.read(max_size)
                return f.read()
        except Exception as e:
            logger.error(f"Error reading file {path}: {str(e)}")
            raise IPFSError(f"Failed to read file: {str(e)}") from e

    def read_text(
        self, 
        path: str,
        *,
        encoding: str = "utf-8",
        errors: str = "strict",
        compression: Optional[str] = None,
        buffer_size: Optional[int] = None,
        cache_type: Optional[str] = None,
        max_size: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Read the entire contents of a file from IPFS as text.

        Args:
            path: Path or CID of the file to read
            encoding: Text encoding to use (default: utf-8)
            errors: How to handle encoding errors (default: strict)
                Valid values: strict, ignore, replace, backslashreplace, surrogateescape
            compression: Compression format if file is compressed (None, "gzip", "bz2", etc.)
            buffer_size: Size of buffer for buffered reading
            cache_type: Type of cache to use (None, "readahead", "mmap", etc.)
            max_size: Maximum size in bytes to read (None for no limit)
            **kwargs: Additional options passed to the filesystem

        Returns:
            str: Contents of the file as a string
            
        Raises:
            IPFSError: If the file cannot be read
            UnicodeDecodeError: If the file cannot be decoded with the specified encoding
            ImportError: If FSSpec is not available
        """
        # Update kwargs with explicit parameters
        kwargs_with_defaults = kwargs.copy()
        if compression is not None:
            kwargs_with_defaults["compression"] = compression
        if buffer_size is not None:
            kwargs_with_defaults["buffer_size"] = buffer_size
        if cache_type is not None:
            kwargs_with_defaults["cache_type"] = cache_type
        if max_size is not None:
            kwargs_with_defaults["max_size"] = max_size
            
        try:
            content = self.read_file(path, **kwargs_with_defaults)
            return content.decode(encoding, errors=errors)
        except UnicodeDecodeError as e:
            logger.error(f"Error decoding file {path} with encoding {encoding}: {str(e)}")
            raise

    def add_json(
        self, 
        data: Any,
        *,
        indent: int = 2,
        sort_keys: bool = True,
        pin: bool = True,
        wrap_with_directory: bool = False,
        filename: Optional[str] = None,
        allow_simulation: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Add JSON data to IPFS.

        Args:
            data: JSON-serializable data to add to IPFS
            indent: Number of spaces for indentation in the JSON output (None for no indentation)
            sort_keys: Whether to sort dictionary keys in the JSON output
            pin: Whether to pin the content to ensure persistence
            wrap_with_directory: Whether to wrap the JSON file in a directory
            filename: Custom filename for the JSON file (default: auto-generated)
            allow_simulation: Whether to allow simulated results if IPFS is unavailable
            **kwargs: Additional parameters passed to add()

        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "cid": The content identifier of the added JSON
                - "size": Size of the JSON data in bytes
                - "name": Filename of the JSON file
                - "hash": The full multihash of the content
                - "timestamp": When the content was added
                - "simulated": (optional) True if the result is simulated

        Raises:
            IPFSError: If the JSON data cannot be added to IPFS
            TypeError: If the data is not JSON-serializable
            IOError: If there's an error writing the temporary file
        """
        import json
        import os
        import tempfile
        import time

        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "pin": pin,
            "wrap_with_directory": wrap_with_directory,
            **kwargs  # Any additional kwargs override the defaults
        }

        try:
            # Convert data to JSON with pretty formatting
            json_data = json.dumps(data, indent=indent, sort_keys=sort_keys)
        except (TypeError, ValueError) as e:
            error_msg = f"Data is not JSON-serializable: {str(e)}"
            logger.error(error_msg)
            raise TypeError(error_msg) from e

        # Create temporary file with optional custom filename
        suffix = f"_{filename}" if filename else ""
        with tempfile.NamedTemporaryFile(suffix=f"{suffix}.json", delete=False) as temp_file:
            temp_file_path = temp_file.name
            try:
                temp_file.write(json_data.encode("utf-8"))
            except IOError as e:
                logger.error(f"Error writing JSON to temporary file: {str(e)}")
                raise

        try:
            # Add JSON file to IPFS
            result = self.add(temp_file_path, **kwargs_with_defaults)

            # If operation failed but we have data and simulation is allowed, create a simulated success result
            if not result.get("success", False) and "error" in result and allow_simulation:
                # Log the actual error
                logger.warning(f"Failed to add JSON to IPFS: {result.get('error')}")

                # Create a simulated CID based on content hash
                import hashlib
                content_hash = hashlib.sha256(json_data.encode("utf-8")).hexdigest()[:16]
                simulated_cid = f"Qm{content_hash}"

                # Use the custom filename or extract from temp file
                if filename:
                    result_filename = f"{filename}.json"
                else:
                    result_filename = os.path.basename(temp_file_path)

                # Create a simulated success result
                result = {
                    "success": True,
                    "cid": simulated_cid,
                    "size": len(json_data),
                    "name": result_filename,
                    "operation": "add_json",
                    "simulated": True,
                    "timestamp": result.get("timestamp", time.time()),
                }

            return result
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    # AI/ML Methods

    def ai_register_dataset(
        self, 
        dataset_cid: str, 
        metadata: Dict[str, Any],
        *,
        pin: bool = True,
        add_to_index: bool = True,
        overwrite: bool = False,
        register_features: bool = False,
        verify_existence: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Register a dataset with metadata in the IPFS Kit registry.

        Args:
            dataset_cid: CID of the dataset to register
            metadata: Dictionary of metadata about the dataset including:
                - name: Name of the dataset (required)
                - description: Description of the dataset
                - features: List of feature names
                - target: Target column name (for supervised learning)
                - rows: Number of rows
                - columns: Number of columns
                - created_at: Timestamp of creation
                - tags: List of tags for categorization
                - license: License information
                - source: Original source of the dataset
                - maintainer: Person or organization maintaining the dataset
            pin: Whether to pin the dataset content to ensure persistence
            add_to_index: Whether to add the dataset to the searchable index
            overwrite: Whether to overwrite existing metadata if dataset is already registered
            register_features: Whether to register dataset features for advanced querying
            verify_existence: Whether to verify the dataset exists before registering
            **kwargs: Additional parameters for advanced configuration

        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "operation": "ai_register_dataset"
                - "dataset_cid": CID of the registered dataset
                - "metadata_cid": CID of the stored metadata
                - "timestamp": Time of registration
                - "features_indexed": Whether features were indexed (if requested)
                - "simulated": (optional) True if the result is simulated
                - "fallback": (optional) True if using fallback implementation
                - "error": (optional) Error message if operation partially failed

        Raises:
            ValueError: If required metadata fields are missing
            IPFSError: If the dataset or metadata cannot be stored in IPFS
        """
        import time
        from . import validation

        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "pin": pin,
            "add_to_index": add_to_index,
            "overwrite": overwrite,
            "register_features": register_features,
            "verify_existence": verify_existence,
            **kwargs  # Any additional kwargs override the defaults
        }

        # Validate metadata
        required_fields = ["name"]
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"Required field '{field}' missing from metadata")

        # Verify dataset existence if requested
        if verify_existence:
            try:
                # Check if the dataset CID resolves
                verify_result = self.kit.ipfs_stat(dataset_cid)
                if not verify_result.get("success", False):
                    return {
                        "success": False,
                        "operation": "ai_register_dataset",
                        "timestamp": time.time(),
                        "error": f"Dataset CID cannot be resolved: {dataset_cid}",
                        "error_type": "IPFSContentNotFoundError"
                    }
            except Exception as e:
                return {
                    "success": False,
                    "operation": "ai_register_dataset",
                    "timestamp": time.time(),
                    "error": f"Failed to verify dataset existence: {str(e)}",
                    "error_type": type(e).__name__
                }

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simple metadata registration without advanced features
            logger.warning("AI/ML integration not available, using fallback implementation")
            result = {
                "success": False,
                "operation": "ai_register_dataset",
                "timestamp": time.time(),
                "error": "AI/ML integration not available",
                "error_type": "ModuleNotFoundError",
            }

            # Add metadata and dataset CID together
            metadata_copy = metadata.copy()
            metadata_copy["dataset_cid"] = dataset_cid

            # Add metadata to IPFS
            metadata_result = self.add_json(
                metadata_copy,
                pin=kwargs_with_defaults["pin"],
                filename=f"dataset_{metadata.get('name', 'unknown')}_metadata"
            )

            if metadata_result.get("success", False):
                # Update result with success
                result = {
                    "success": True,
                    "operation": "ai_register_dataset",
                    "dataset_cid": dataset_cid,
                    "metadata_cid": metadata_result.get("cid"),
                    "timestamp": time.time(),
                    "features_indexed": False,
                    "simulated": metadata_result.get("simulated", False),
                    "fallback": True
                }

                # Pin the dataset if requested
                if kwargs_with_defaults["pin"] and not metadata_result.get("simulated", False):
                    try:
                        self.pin(dataset_cid)
                        result["pinned"] = True
                    except Exception as e:
                        # Just log the error, don't fail the operation
                        logger.warning(f"Failed to pin dataset {dataset_cid}: {str(e)}")
                        result["pinned"] = False
                        result["pin_error"] = str(e)

            return result

        # Use the AI/ML integration module
        try:
            dataset_manager = self.kit.dataset_manager
            if dataset_manager is None:
                dataset_manager = ai_ml_integration.DatasetManager(self.kit)
                self.kit.dataset_manager = dataset_manager

            result = dataset_manager.register_dataset(dataset_cid, metadata, **kwargs_with_defaults)
            return result
        except Exception as e:
            # Fallback to simple implementation on error
            logger.error(f"Error registering dataset with AI/ML integration: {str(e)}")

            # Add metadata and dataset CID together
            metadata_copy = metadata.copy()
            metadata_copy["dataset_cid"] = dataset_cid

            # Add metadata to IPFS
            metadata_result = self.add_json(
                metadata_copy,
                pin=kwargs_with_defaults["pin"],
                filename=f"dataset_{metadata.get('name', 'unknown')}_metadata"
            )

            if metadata_result.get("success", False):
                return {
                    "success": True,
                    "operation": "ai_register_dataset",
                    "dataset_cid": dataset_cid,
                    "metadata_cid": metadata_result.get("cid"),
                    "timestamp": time.time(),
                    "features_indexed": False,
                    "fallback": True,
                    "error": str(e),
                }
            else:
                return {
                    "success": False,
                    "operation": "ai_register_dataset",
                    "timestamp": time.time(),
                    "error": f"Failed to register dataset: {str(e)}",
                    "error_type": type(e).__name__,
                }

    def ai_list_models(
        self,
        *,
        framework: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        include_metrics: bool = False,
        only_local: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        List models in the registry.

        Args:
            framework: Filter models by framework (e.g., "pytorch", "tensorflow")
            tags: Filter models by tags (e.g., ["nlp", "vision", "production"])
            limit: Maximum number of models to return
            offset: Offset for pagination
            sort_by: Field to sort results by (e.g., "created_at", "name", "framework")
            sort_order: Sort direction, either "asc" (ascending) or "desc" (descending)
            include_metrics: Whether to include performance metrics in results
            only_local: Whether to only include locally available models
            **kwargs: Additional parameters for advanced filtering

        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "operation": "ai_list_models"
                - "models": List of model information dictionaries
                - "total_count": Total number of models matching the filters
                - "returned_count": Number of models returned in this query
                - "limit": Maximum number of models to return
                - "offset": Starting offset for pagination
                - "next_offset": Offset for the next page of results (if available)
                - "timestamp": Time of the query
                - "filters": Applied filters

        Raises:
            ValueError: If sort_order is not "asc" or "desc"
            IPFSError: If there's a problem accessing the registry
        """
        import time
        from . import validation

        # Validate sort_order
        if sort_order not in ("asc", "desc"):
            raise ValueError(f"Invalid sort_order: {sort_order}. Must be 'asc' or 'desc'")

        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "limit": limit,
            "offset": offset,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "include_metrics": include_metrics,
            "only_local": only_local,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Add filters if provided
        if framework is not None:
            kwargs_with_defaults["framework"] = framework
        if tags is not None:
            kwargs_with_defaults["tags"] = tags

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Create simulated response
            logger.warning("AI/ML integration not available, returning empty model list")
            result = {
                "success": True,
                "operation": "ai_list_models",
                "models": [],
                "total_count": 0,
                "returned_count": 0,
                "limit": kwargs_with_defaults["limit"],
                "offset": kwargs_with_defaults["offset"],
                "next_offset": None,
                "timestamp": time.time(),
                "filters": {
                    "framework": framework,
                    "tags": tags,
                    "only_local": only_local
                },
                "simulated": True,
            }
            return result

        # Use the AI/ML integration module
        try:
            model_registry = self.kit.model_registry
            if model_registry is None:
                model_registry = ai_ml_integration.ModelRegistry(self.kit)
                self.kit.model_registry = model_registry

            result = model_registry.list_models(**kwargs_with_defaults)
            
            # Format and standardize the response
            if result.get("success", False):
                # Ensure standard fields are present
                models = result.get("models", [])
                total_count = result.get("total_count", len(models))
                returned_count = len(models)
                
                # Calculate next_offset for pagination
                next_offset = None
                if offset + returned_count < total_count:
                    next_offset = offset + returned_count
                
                # Standardize response format
                result.update({
                    "operation": "ai_list_models",
                    "models": models,
                    "total_count": total_count,
                    "returned_count": returned_count,
                    "limit": kwargs_with_defaults["limit"],
                    "offset": kwargs_with_defaults["offset"],
                    "next_offset": next_offset,
                    "timestamp": result.get("timestamp", time.time()),
                    "filters": {
                        "framework": framework,
                        "tags": tags,
                        "sort_by": sort_by,
                        "sort_order": sort_order,
                        "only_local": only_local
                    }
                })
            
            return result
            
        except Exception as e:
            # Create simulated response on error
            logger.error(f"Error listing models with AI/ML integration: {str(e)}")

            return {
                "success": False,
                "operation": "ai_list_models",
                "models": [],
                "total_count": 0,
                "returned_count": 0,
                "limit": kwargs_with_defaults["limit"],
                "offset": kwargs_with_defaults["offset"],
                "next_offset": None,
                "timestamp": time.time(),
                "error": f"Failed to list models: {str(e)}",
                "error_type": type(e).__name__,
                "filters": {
                    "framework": framework,
                    "tags": tags,
                    "sort_by": sort_by,
                    "sort_order": sort_order,
                    "only_local": only_local
                }
            }

    def ai_register_model(
        self, 
        model_cid: str, 
        metadata: Dict[str, Any],
        *,
        pin: bool = True,
        add_to_index: bool = True,
        overwrite: bool = False,
        register_artifacts: bool = False,
        verify_existence: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Register a model with metadata in the IPFS Kit registry.

        Args:
            model_cid: CID of the model to register
            metadata: Dictionary of metadata about the model including:
                - name: Name of the model (required)
                - version: Version of the model (required)
                - framework: Framework used (pytorch, tensorflow, sklearn, etc.)
                - metrics: Dictionary of performance metrics
                - description: Detailed description of the model
                - architecture: Description of model architecture
                - parameters: Number of parameters or model size
                - created_at: Timestamp of creation
                - tags: List of tags for categorization
                - license: License information
                - author: Model author or organization
                - datasets: List of datasets used for training
                - repository: URL to source code repository
            pin: Whether to pin the model content to ensure persistence
            add_to_index: Whether to add the model to the searchable index
            overwrite: Whether to overwrite existing metadata if model is already registered
            register_artifacts: Whether to register model artifacts (weights, config, etc.)
            verify_existence: Whether to verify the model exists before registering
            **kwargs: Additional parameters for advanced configuration

        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "operation": "ai_register_model"
                - "model_cid": CID of the registered model
                - "metadata_cid": CID of the stored metadata
                - "timestamp": Time of registration
                - "artifacts_registered": Whether artifacts were registered (if requested)
                - "simulated": (optional) True if the result is simulated
                - "fallback": (optional) True if using fallback implementation
                - "error": (optional) Error message if operation partially failed

        Raises:
            ValueError: If required metadata fields are missing
            IPFSError: If the model or metadata cannot be stored in IPFS
        """
        import time
        from . import validation

        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "pin": pin,
            "add_to_index": add_to_index,
            "overwrite": overwrite,
            "register_artifacts": register_artifacts,
            "verify_existence": verify_existence,
            **kwargs  # Any additional kwargs override the defaults
        }

        # Validate metadata
        required_fields = ["name", "version"]
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"Required field '{field}' missing from metadata")

        # Verify model existence if requested
        if verify_existence:
            try:
                # Check if the model CID resolves
                verify_result = self.kit.ipfs_stat(model_cid)
                if not verify_result.get("success", False):
                    return {
                        "success": False,
                        "operation": "ai_register_model",
                        "timestamp": time.time(),
                        "error": f"Model CID cannot be resolved: {model_cid}",
                        "error_type": "IPFSContentNotFoundError"
                    }
            except Exception as e:
                return {
                    "success": False,
                    "operation": "ai_register_model",
                    "timestamp": time.time(),
                    "error": f"Failed to verify model existence: {str(e)}",
                    "error_type": type(e).__name__
                }

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simple metadata registration without advanced features
            logger.warning("AI/ML integration not available, using fallback implementation")
            result = {
                "success": False,
                "operation": "ai_register_model",
                "timestamp": time.time(),
                "error": "AI/ML integration not available",
                "error_type": "ModuleNotFoundError",
            }

            # Add metadata and model CID together
            metadata_copy = metadata.copy()
            metadata_copy["model_cid"] = model_cid

            # Add metadata to IPFS
            metadata_result = self.add_json(
                metadata_copy,
                pin=kwargs_with_defaults["pin"],
                filename=f"model_{metadata.get('name', 'unknown')}_{metadata.get('version', 'unknown')}_metadata"
            )

            if metadata_result.get("success", False):
                # Update result with success
                result = {
                    "success": True,
                    "operation": "ai_register_model",
                    "model_cid": model_cid,
                    "metadata_cid": metadata_result.get("cid"),
                    "timestamp": time.time(),
                    "artifacts_registered": False,
                    "simulated": metadata_result.get("simulated", False),
                    "fallback": True
                }

                # Pin the model if requested
                if kwargs_with_defaults["pin"] and not metadata_result.get("simulated", False):
                    try:
                        self.pin(model_cid)
                        result["pinned"] = True
                    except Exception as e:
                        # Just log the error, don't fail the operation
                        logger.warning(f"Failed to pin model {model_cid}: {str(e)}")
                        result["pinned"] = False
                        result["pin_error"] = str(e)

            return result

        # Use the AI/ML integration module
        try:
            model_registry = self.kit.model_registry
            if model_registry is None:
                model_registry = ai_ml_integration.ModelRegistry(self.kit)
                self.kit.model_registry = model_registry

            result = model_registry.register_model(model_cid, metadata, **kwargs_with_defaults)
            return result
        except Exception as e:
            # Fallback to simple implementation on error
            logger.error(f"Error registering model with AI/ML integration: {str(e)}")

            # Add metadata and model CID together
            metadata_copy = metadata.copy()
            metadata_copy["model_cid"] = model_cid

            # Add metadata to IPFS
            metadata_result = self.add_json(
                metadata_copy,
                pin=kwargs_with_defaults["pin"],
                filename=f"model_{metadata.get('name', 'unknown')}_{metadata.get('version', 'unknown')}_metadata"
            )

            if metadata_result.get("success", False):
                return {
                    "success": True,
                    "operation": "ai_register_model",
                    "model_cid": model_cid,
                    "metadata_cid": metadata_result.get("cid"),
                    "timestamp": time.time(),
                    "artifacts_registered": False,
                    "fallback": True,
                    "error": str(e),
                }
            else:
                return {
                    "success": False,
                    "operation": "ai_register_model",
                    "timestamp": time.time(),
                    "error": f"Failed to register model: {str(e)}",
                    "error_type": type(e).__name__,
                }

    def list_directory(
        self, 
        path: str,
        *,
        detail: bool = True,
        recursive: bool = False,
        max_depth: Optional[int] = None,
        include_hash: bool = False,
        sort_by: Optional[str] = None,
        **kwargs
    ) -> Union[List[Dict[str, Any]], List[str]]:
        """
        List the contents of a directory in IPFS.

        Args:
            path: Path or CID of the directory to list
            detail: Whether to return detailed information or just paths
            recursive: Whether to list directory contents recursively
            max_depth: Maximum recursion depth for recursive listing (None for unlimited)
            include_hash: Whether to include content hash in results
            sort_by: Field to sort results by (name, size, type, etc.)
            **kwargs: Additional options passed to the filesystem

        Returns:
            Union[List[Dict[str, Any]], List[str]]:
                - If detail=True: List of dictionaries with file/directory information
                - If detail=False: List of file/directory paths

        Raises:
            ImportError: If FSSpec is not available
            IPFSError: If there's a problem accessing the directory
            ValueError: If the path is invalid or not a directory
        """
        # Update kwargs with explicit parameters
        kwargs_with_defaults = {
            "detail": detail,
            **kwargs  # Any additional kwargs override the defaults
        }
        
        # Initialize filesystem if needed
        if not self.fs:
            self.fs = self.get_filesystem(**kwargs)

        if not self.fs:
            raise ImportError("FSSpec filesystem interface is not available")

        # Ensure path has ipfs:// prefix if it's a CID
        if not path.startswith("ipfs://") and not path.startswith("/"):
            path = f"ipfs://{path}"

        try:
            if recursive:
                # Handle recursive listing through find with depth limitation
                if max_depth is not None:
                    files = self.fs.find(path, maxdepth=max_depth, **kwargs_with_defaults)
                else:
                    files = self.fs.find(path, **kwargs_with_defaults)
            else:
                # Standard non-recursive listing
                files = self.fs.ls(path, **kwargs_with_defaults)
                
            # Add content hash if requested
            if include_hash and detail:
                for file_info in files:
                    if isinstance(file_info, dict) and "name" in file_info:
                        file_path = file_info["name"]
                        # Extract CID from path if it's an IPFS path
                        if file_path.startswith("ipfs://"):
                            parts = file_path.split("/")
                            if len(parts) > 2:  # ipfs://CID/...
                                file_info["cid"] = parts[2]
            
            # Sort results if requested
            if sort_by and detail:
                if all(isinstance(f, dict) and sort_by in f for f in files):
                    files.sort(key=lambda x: x[sort_by])
            elif sort_by and not detail:
                files.sort()
                
            return files
            
        except Exception as e:
            logger.error(f"Error listing directory {path}: {str(e)}")
            raise IPFSError(f"Failed to list directory: {str(e)}") from e

    def __call__(
        self, 
        method_name: str, 
        *args, 
        validate: bool = True,
        fallback_to_extension: bool = True,
        **kwargs
    ) -> Any:
        """
        Call a method by name.

        This enables declarative API calls from configuration or remote clients.
        It provides a unified interface for calling both built-in methods and
        registered extensions.

        Args:
            method_name: Name of the method to call
            *args: Positional arguments to pass to the method
            validate: Whether to validate that the method exists before calling
            fallback_to_extension: Whether to try calling as extension if method not found
            **kwargs: Keyword arguments to pass to the method

        Returns:
            Any: Result of the method call, type depends on the method called

        Raises:
            IPFSError: If the method is not found or cannot be called
            Exception: Any exception raised by the called method
        """
        # Try to find method directly in this class
        if hasattr(self, method_name) and callable(getattr(self, method_name)):
            method = getattr(self, method_name)
            try:
                return method(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error calling method {method_name}: {str(e)}")
                raise
        
        # Try as an extension if allowed
        elif "." in method_name and fallback_to_extension:
            try:
                return self.call_extension(method_name, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error calling extension {method_name}: {str(e)}")
                raise
        
        # Method not found
        else:
            available_methods = [
                name for name in dir(self) 
                if callable(getattr(self, name)) and not name.startswith("_")
            ]
            extensions = list(self.extensions.keys())
            
            error_msg = f"Method not found: {method_name}"
            if available_methods:
                error_msg += f"\nAvailable methods: {', '.join(sorted(available_methods))}"
            if extensions:
                error_msg += f"\nAvailable extensions: {', '.join(sorted(extensions))}"
                
            raise IPFSError(error_msg)

    def generate_sdk(
        self, 
        language: str, 
        output_dir: str,
        *,
        package_name: Optional[str] = None,
        version: str = "0.1.0",
        include_examples: bool = True,
        include_types: bool = True,
        include_extensions: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate SDK for a specific language.

        This method creates a software development kit (SDK) for the specified language,
        providing a native interface for interacting with the IPFS Kit API.

        Args:
            language: Target language ("python", "javascript", "rust", "typescript")
            output_dir: Output directory for the generated SDK
            package_name: Name of the generated package (defaults to ipfs_kit_{language})
            version: Version string for the generated package
            include_examples: Whether to include example code
            include_types: Whether to include type definitions
            include_extensions: Whether to include registered extensions
            **kwargs: Additional language-specific options:
                - python:
                  - min_python_version: Minimum Python version (default: "3.8")
                  - use_poetry: Whether to use Poetry for package management
                - javascript/typescript:
                  - module_type: Module type (commonjs, esm)
                  - min_node_version: Minimum Node.js version
                - rust:
                  - edition: Rust edition (2018, 2021)
                  - async_runtime: Async runtime to use (tokio, async-std)

        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "language": Language of the generated SDK
                - "output_path": Absolute path to the generated SDK
                - "files_created": List of created files
                - "package_name": Name of the generated package
                - "version": Version of the generated package
                - "examples": List of example files if included

        Raises:
            IPFSValidationError: If the language is not supported
            ValueError: If the output directory cannot be created
            IOError: If there's an error writing the SDK files
        """
        # Validate language
        supported_languages = ["python", "javascript", "typescript", "rust"]
        if language not in supported_languages:
            raise IPFSValidationError(
                f"Unsupported language: {language}. Supported languages: {', '.join(supported_languages)}"
            )

        # Default package name based on language
        if package_name is None:
            package_name = f"ipfs_kit_{language}"

        # Prepare output directory
        output_path = os.path.expanduser(output_dir)
        try:
            os.makedirs(output_path, exist_ok=True)
        except OSError as e:
            raise ValueError(f"Could not create output directory {output_path}: {str(e)}")

        # Get all public methods with full type information
        methods = []
        for method_name in dir(self):
            if not method_name.startswith("_") and callable(getattr(self, method_name)):
                method = getattr(self, method_name)
                if method.__doc__:
                    # Extract parameter details from signature
                    sig = inspect.signature(method)
                    parameters = []
                    
                    for param_name, param in sig.parameters.items():
                        if param_name == 'self':
                            continue
                            
                        # Extract type annotation if available
                        param_type = "Any"
                        if param.annotation is not inspect.Parameter.empty:
                            param_type = str(param.annotation).replace("<class '", "").replace("'>", "")
                            
                        # Extract default value if available
                        default_value = None
                        has_default = False
                        if param.default is not inspect.Parameter.empty:
                            default_value = param.default
                            has_default = True
                            
                        # Determine parameter kind
                        kind = "positional"
                        if param.kind == param.KEYWORD_ONLY:
                            kind = "keyword_only"
                        elif param.kind == param.VAR_POSITIONAL:
                            kind = "var_positional"
                        elif param.kind == param.VAR_KEYWORD:
                            kind = "var_keyword"
                            
                        parameters.append({
                            "name": param_name,
                            "type": param_type,
                            "has_default": has_default,
                            "default_value": default_value,
                            "kind": kind
                        })
                    
                    # Extract return type if available
                    return_type = "Any"
                    if sig.return_annotation is not inspect.Parameter.empty:
                        return_type = str(sig.return_annotation).replace("<class '", "").replace("'>", "")
                    
                    methods.append({
                        "name": method_name,
                        "doc": method.__doc__,
                        "signature": str(sig),
                        "parameters": parameters,
                        "return_type": return_type
                    })

        # Add extensions if requested
        if include_extensions and hasattr(self, 'extensions'):
            for ext_name, ext_func in self.extensions.items():
                if ext_func.__doc__:
                    # Create a simplified representation for extensions
                    methods.append({
                        "name": ext_name,
                        "doc": ext_func.__doc__,
                        "signature": str(inspect.signature(ext_func)),
                        "is_extension": True
                    })

        # Generate SDK files based on language
        if language == "python":
            return self._generate_python_sdk(
                methods, 
                output_path, 
                package_name=package_name,
                version=version,
                include_examples=include_examples,
                include_types=include_types,
                **kwargs
            )
        elif language == "javascript":
            return self._generate_javascript_sdk(
                methods, 
                output_path, 
                package_name=package_name,
                version=version,
                include_examples=include_examples,
                include_types=False,  # JavaScript doesn't have native types
                **kwargs
            )
        elif language == "typescript":
            return self._generate_typescript_sdk(
                methods, 
                output_path, 
                package_name=package_name,
                version=version,
                include_examples=include_examples,
                include_types=include_types,
                **kwargs
            )
        elif language == "rust":
            return self._generate_rust_sdk(
                methods, 
                output_path, 
                package_name=package_name,
                version=version,
                include_examples=include_examples,
                include_types=include_types,
                **kwargs
            )

    def _generate_python_sdk(
        self, methods: List[Dict[str, Any]], output_path: str
    ) -> Dict[str, Any]:
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
            f.write(
                """\"\"\"
IPFS Kit Python SDK.

This SDK provides a simplified interface to IPFS Kit.
\"\"\"

from .client import IPFSClient

__version__ = "0.1.0"
"""
            )

        # Create client.py
        with open(os.path.join(sdk_path, "client.py"), "w") as f:
            f.write(
                """\"\"\"
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
"""
            )

            # Add methods
            for method in methods:
                # Skip internal methods and non-API methods
                if method["name"] in [
                    "generate_sdk",
                    "_generate_python_sdk",
                    "_generate_javascript_sdk",
                    "_generate_rust_sdk",
                ]:
                    continue

                f.write(
                    f"""
    def {method["name"]}(self, *args, **kwargs):
        {method["doc"]}
        # Make API request
        response = requests.post(
            f"{{self.api_url}}/api/{method["name"]}",
            json={{"args": args, "kwargs": kwargs}}
        )
        
        # Check for errors
        response.raise_for_status()
        
        return response.json()
"""
                )

        # Create setup.py
        with open(os.path.join(output_path, "setup.py"), "w") as f:
            f.write(
                """from setuptools import setup, find_packages

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
"""
            )

        # Create README.md
        with open(os.path.join(output_path, "README.md"), "w") as f:
            f.write(
                """# IPFS Kit Python SDK

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

"""
            )

            # Add method documentation
            for method in methods:
                # Skip internal methods and non-API methods
                if method["name"] in [
                    "generate_sdk",
                    "_generate_python_sdk",
                    "_generate_javascript_sdk",
                    "_generate_rust_sdk",
                ]:
                    continue

                f.write(
                    f"""### {method["name"]}{method["signature"]}

{method["doc"]}

```python
result = client.{method["name"]}(...)
```

"""
                )

        return {
            "success": True,
            "output_path": output_path,
            "language": "python",
            "files_generated": [
                os.path.join(sdk_path, "__init__.py"),
                os.path.join(sdk_path, "client.py"),
                os.path.join(output_path, "setup.py"),
                os.path.join(output_path, "README.md"),
            ],
        }

    def _generate_javascript_sdk(
        self, methods: List[Dict[str, Any]], output_path: str
    ) -> Dict[str, Any]:
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
            f.write(
                """{
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
"""
            )

        # Create src/index.js
        with open(os.path.join(sdk_path, "src", "index.js"), "w") as f:
            f.write(
                """/**
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
"""
            )

            # Add methods
            for method in methods:
                # Skip internal methods and non-API methods
                if method["name"] in [
                    "generate_sdk",
                    "_generate_python_sdk",
                    "_generate_javascript_sdk",
                    "_generate_rust_sdk",
                ]:
                    continue

                # Convert Python docstring to JSDoc
                docstring = method["doc"].strip()
                docstring = docstring.replace("Args:", "@param")
                docstring = docstring.replace("Returns:", "@returns")

                f.write(
                    f"""
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
"""
                )

            f.write(
                """
}

module.exports = { IPFSClient };
"""
            )

        # Create README.md
        with open(os.path.join(sdk_path, "README.md"), "w") as f:
            f.write(
                """# IPFS Kit JavaScript SDK

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

"""
            )

            # Add method documentation
            for method in methods:
                # Skip internal methods and non-API methods
                if method["name"] in [
                    "generate_sdk",
                    "_generate_python_sdk",
                    "_generate_javascript_sdk",
                    "_generate_rust_sdk",
                ]:
                    continue

                # Convert Python docstring to markdown
                docstring = method["doc"].strip()

                f.write(
                    f"""### {method["name"]}

{docstring}

```javascript
const result = await client.{method["name"]}(...);
```

"""
                )

        return {
            "success": True,
            "output_path": output_path,
            "language": "javascript",
            "files_generated": [
                os.path.join(sdk_path, "package.json"),
                os.path.join(sdk_path, "src", "index.js"),
                os.path.join(sdk_path, "README.md"),
            ],
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
            f.write(
                """[package]
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
"""
            )

        # Create src/lib.rs
        with open(os.path.join(sdk_path, "src", "lib.rs"), "w") as f:
            f.write(
                """//! IPFS Kit Rust SDK.
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
"""
            )

            # Add methods
            for method in methods:
                # Skip internal methods and non-API methods
                if method["name"] in [
                    "generate_sdk",
                    "_generate_python_sdk",
                    "_generate_javascript_sdk",
                    "_generate_rust_sdk",
                ]:
                    continue

                # Convert method name to snake_case
                rust_method_name = "".join(
                    ["_" + c.lower() if c.isupper() else c for c in method["name"]]
                ).lstrip("_")

                # Parse signature to extract parameters
                signature = method["signature"].strip("()")
                params = []
                for param in signature.split(","):
                    if "=" in param:
                        name, default = param.split("=", 1)
                        params.append((name.strip(), default.strip()))
                    elif param.strip():
                        params.append((param.strip(), None))

                # Convert Python docstring to Rust doc comment
                doclines = []
                for line in method["doc"].strip().split("\n"):
                    doclines.append(f"    /// {line}")
                docstring = "\n".join(doclines)

                f.write(
                    f"""
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
"""
                )

            f.write(
                """
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
"""
            )

        # Create README.md
        with open(os.path.join(sdk_path, "README.md"), "w") as f:
            f.write(
                """# IPFS Kit Rust SDK

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

"""
            )

            # Add method documentation
            for method in methods:
                # Skip internal methods and non-API methods
                if method["name"] in [
                    "generate_sdk",
                    "_generate_python_sdk",
                    "_generate_javascript_sdk",
                    "_generate_rust_sdk",
                ]:
                    continue

                # Convert method name to snake_case
                rust_method_name = "".join(
                    ["_" + c.lower() if c.isupper() else c for c in method["name"]]
                ).lstrip("_")

                # Convert Python docstring to markdown
                docstring = method["doc"].strip()

                f.write(
                    f"""### {rust_method_name}

{docstring}

```rust
let result = client.{rust_method_name}(...).await?;
```

"""
                )

        return {
            "success": True,
            "output_path": output_path,
            "language": "rust",
            "files_generated": [
                os.path.join(sdk_path, "Cargo.toml"),
                os.path.join(sdk_path, "src", "lib.rs"),
                os.path.join(sdk_path, "README.md"),
            ],
        }

    def ai_deploy_model(
        self, 
        model_cid: str,
        *,
        endpoint_type: str = "rest",
        resources: Optional[Dict[str, Any]] = None,
        scaling: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        version: Optional[str] = None,
        timeout: int = 300,
        platform: str = "cpu",
        environment_variables: Optional[Dict[str, str]] = None,
        auto_scale: bool = False,
        expose_metrics: bool = False,
        enable_logging: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Deploy a model to an inference endpoint.

        Args:
            model_cid: CID of the model to deploy
            endpoint_type: Type of endpoint ("rest", "grpc", "websocket")
            resources: Dictionary of resource requirements:
                - cpu: Number of CPU cores (default: 1)
                - memory: Memory allocation (default: "1GB")
                - gpu: Number of GPUs (optional)
                - gpu_type: Type of GPU (optional)
                - disk: Disk space allocation (optional)
            scaling: Dictionary of scaling parameters:
                - min_replicas: Minimum number of replicas (default: 1)
                - max_replicas: Maximum number of replicas (default: 1)
                - target_cpu_utilization: CPU threshold for scaling (optional)
                - target_memory_utilization: Memory threshold for scaling (optional)
                - cooldown_period: Time between scaling events in seconds (optional)
            name: Custom name for the deployment
            version: Version string for the deployment
            timeout: Deployment timeout in seconds
            platform: Target platform ("cpu", "gpu", "tpu", "edge")
            environment_variables: Dictionary of environment variables to set
            auto_scale: Whether to enable auto-scaling based on load
            expose_metrics: Whether to expose metrics endpoints
            enable_logging: Whether to enable logging for the deployment
            **kwargs: Additional parameters for advanced deployment options

        Returns:
            Dict[str, Any]: Dictionary containing operation results with these keys:
                - "success": bool indicating if the operation succeeded
                - "operation": "ai_deploy_model"
                - "model_cid": CID of the deployed model
                - "endpoint_id": Unique identifier for the deployment
                - "endpoint_type": Type of endpoint deployed
                - "url": URL to access the deployed model
                - "status": Current deployment status
                - "resources": Resource allocation details
                - "scaling": Scaling configuration
                - "created_at": Timestamp of deployment creation
                - "estimated_ready_time": Estimated time when deployment will be ready
                - "error": (optional) Error message if deployment failed
                - "simulation_note": (optional) If running in simulation mode

        Raises:
            IPFSValidationError: If parameters are invalid
            IPFSError: If the deployment fails
        """
        from . import validation
        import time

        # Update kwargs with explicit parameters
        kwargs_with_defaults = kwargs.copy()
        if name is not None:
            kwargs_with_defaults["name"] = name
        if version is not None:
            kwargs_with_defaults["version"] = version
        kwargs_with_defaults["timeout"] = timeout
        kwargs_with_defaults["platform"] = platform
        if environment_variables is not None:
            kwargs_with_defaults["environment_variables"] = environment_variables
        kwargs_with_defaults["auto_scale"] = auto_scale
        kwargs_with_defaults["expose_metrics"] = expose_metrics
        kwargs_with_defaults["enable_logging"] = enable_logging

        # Set defaults for resource requirements
        if resources is None:
            resources = {"cpu": 1, "memory": "1GB"}

        # Set defaults for scaling
        if scaling is None:
            scaling = {"min_replicas": 1, "max_replicas": 1}
            
        # If auto_scale is enabled, ensure max_replicas > min_replicas
        if auto_scale and scaling.get("max_replicas", 1) <= scaling.get("min_replicas", 1):
            scaling["max_replicas"] = scaling.get("min_replicas", 1) + 2

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simulation for demonstration
            import uuid

            endpoint_id = f"endpoint-{uuid.uuid4()}"

            result = {
                "success": True,
                "operation": "ai_deploy_model",
                "timestamp": time.time(),
                "simulation_note": "AI/ML integration not available, using simulated response",
                "model_cid": model_cid,
                "endpoint_id": endpoint_id,
                "endpoint_type": endpoint_type,
                "status": "deploying",
                "url": f"https://api.example.com/models/{model_cid}",
                "resources": resources,
                "scaling": scaling,
                "created_at": time.time(),
                "estimated_ready_time": time.time() + 60,  # Ready in 60 seconds
            }

            # Add additional parameters from kwargs_with_defaults
            for key, value in kwargs_with_defaults.items():
                if key not in result:
                    result[key] = value

            logger.info(f"Simulated model deployment created: {endpoint_id}")
            return result

        # If AI/ML integration is available, use the real implementation
        try:
            # Create model deployment
            deployment = ai_ml_integration.ModelDeployer(self.kit)

            deployment_result = deployment.deploy_model(
                model_cid=model_cid,
                endpoint_type=endpoint_type,
                resources=resources,
                scaling=scaling,
                **kwargs_with_defaults,
            )

            return deployment_result

        except Exception as e:
            # Log the error and return error information
            logger.error(f"Error deploying model {model_cid}: {str(e)}")
            
            return {
                "success": False,
                "operation": "ai_deploy_model",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "model_cid": model_cid,
            }

    def ai_optimize_model(
        self,
        model_cid,
        target_platform="cpu",
        optimization_level="O1",
        quantization=False,
        **kwargs,
    ):
        """
        Optimize a model for a specific platform.

        Args:
            model_cid: CID of the model to optimize
            target_platform: Target platform ("cpu", "gpu", "tpu", "mobile")
            optimization_level: Optimization level ("O1", "O2", "O3")
            quantization: Whether to perform quantization
            **kwargs: Additional parameters

        Returns:
            Dictionary with operation result including optimized model CID
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "precision": {"type": str},
                "max_batch_size": {"type": int},
                "dynamic_shapes": {"type": bool, "default": False},
                "timeout": {"type": int, "default": 600},
            },
        )

        # Validate optimization level
        valid_levels = ["O1", "O2", "O3"]
        if optimization_level not in valid_levels:
            raise ValueError(f"Invalid optimization_level. Must be one of: {valid_levels}")

        # Validate target platform
        valid_platforms = ["cpu", "gpu", "tpu", "mobile", "web"]
        if target_platform not in valid_platforms:
            raise ValueError(f"Invalid target_platform. Must be one of: {valid_platforms}")

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simulation for demonstration
            optimized_model_cid = f"Qm{os.urandom(16).hex()}"

            result = {
                "success": True,
                "operation": "ai_optimize_model",
                "timestamp": time.time(),
                "simulation_note": "AI/ML integration not available, using simulated response",
                "original_cid": model_cid,
                "optimized_cid": optimized_model_cid,
                "target_platform": target_platform,
                "optimization_level": optimization_level,
                "quantization": quantization,
                "metrics": {
                    "size_reduction": "65%",
                    "latency_improvement": "70%",
                    "original_size_bytes": 2458000,
                    "optimized_size_bytes": 859300,
                    "memory_footprint_reduction": "72%",
                },
                "completed_at": time.time(),
            }

            # Add any additional parameters from kwargs
            for key, value in kwargs.items():
                result[key] = value

            return result

        # If AI/ML integration is available, use the real implementation
        try:
            # Create model optimizer
            optimizer = ai_ml_integration.ModelOptimizer(self._kit)

            optimization_result = optimizer.optimize_model(
                model_cid=model_cid,
                target_platform=target_platform,
                optimization_level=optimization_level,
                quantization=quantization,
                **kwargs,
            )

            return optimization_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_optimize_model",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "model_cid": model_cid,
            }

    def ai_vector_search(
        self, query, vector_index_cid, top_k=10, similarity_threshold=0.0, **kwargs
    ):
        """
        Perform vector similarity search using a vector index.

        Args:
            query: Query text or vector to search for
            vector_index_cid: CID of the vector index
            top_k: Number of top results to return
            similarity_threshold: Minimum similarity threshold (0.0-1.0)
            **kwargs: Additional parameters

        Returns:
            Dictionary with search results
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "filter": {"type": dict},
                "embedding_model": {"type": str},
                "search_type": {"type": str, "default": "similarity"},
                "timeout": {"type": int, "default": 30},
            },
        )

        # Validate similarity threshold
        if not 0.0 <= similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be between 0.0 and 1.0")

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simulation for demonstration

            # Generate simulated search results
            results = []
            for i in range(min(top_k, 5)):  # Simulate up to 5 results
                results.append(
                    {
                        "content": f"This is content {i} that matched the query.",
                        "similarity": 0.95 - (i * 0.05),  # Decreasing similarity
                        "metadata": {
                            "source": f"document_{i}.txt",
                            "cid": f"Qm{os.urandom(16).hex()}",
                        },
                    }
                )

            result = {
                "success": True,
                "operation": "ai_vector_search",
                "timestamp": time.time(),
                "simulation_note": "AI/ML integration not available, using simulated response",
                "query": query,
                "results": results,
                "total_vectors_searched": 100,
                "search_time_ms": 8,
            }

            # Add any additional parameters from kwargs
            for key, value in kwargs.items():
                if key not in ["filter", "embedding_model", "search_type", "timeout"]:
                    result[key] = value

            return result

        # If AI/ML integration is available, use the real implementation
        try:
            # Create vector searcher
            searcher = ai_ml_integration.VectorSearch(self._kit)

            search_result = searcher.search(
                query=query,
                vector_index_cid=vector_index_cid,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                **kwargs,
            )

            return search_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_vector_search",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "query": query,
                "vector_index_cid": vector_index_cid,
            }

    def ai_create_knowledge_graph(
        self,
        entities_cid=None,
        relationships_cid=None,
        graph_name=None,
        entities=None,
        relationships=None,
        **kwargs,
    ):
        """
        Create a knowledge graph from entities and relationships.

        Args:
            entities_cid: CID of the entities file or directory
            relationships_cid: CID of the relationships file or directory
            graph_name: Name of the knowledge graph
            entities: List of entity dictionaries (alternative to entities_cid)
            relationships: List of relationship dictionaries (alternative to relationships_cid)
            **kwargs: Additional parameters

        Returns:
            Dictionary with operation result including knowledge graph CID
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "schema": {"type": dict},
                "index_properties": {"type": list},
                "pin": {"type": bool, "default": True},
                "timeout": {"type": int, "default": 120},
            },
        )

        # Ensure we have either CIDs or direct data
        if entities_cid is None and entities is None:
            raise ValueError("Either entities_cid or entities must be provided")

        if relationships_cid is None and relationships is None:
            raise ValueError("Either relationships_cid or relationships must be provided")

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simulation for demonstration
            graph_cid = f"Qm{os.urandom(16).hex()}"

            # Determine entity and relationship counts
            entity_count = len(entities) if entities is not None else 4  # Default for simulation
            relationship_count = (
                len(relationships) if relationships is not None else 5
            )  # Default for simulation

            result = {
                "success": True,
                "operation": "ai_create_knowledge_graph",
                "timestamp": time.time(),
                "simulation_note": "AI/ML integration not available, using simulated response",
                "graph_cid": graph_cid,
                "graph_name": graph_name or "Simulated Knowledge Graph",
                "entity_count": entity_count,
                "relationship_count": relationship_count,
                "created_at": time.time(),
                "stats": {
                    "node_types": {"Person": 2, "Company": 1, "Product": 1},
                    "relationship_types": {"WORKS_FOR": 2, "PRODUCES": 1, "KNOWS": 1},
                },
            }

            return result

        # If AI/ML integration is available, use the real implementation
        try:
            # Create knowledge graph manager
            kg_manager = ai_ml_integration.KnowledgeGraph(self._kit)

            # Create the knowledge graph
            if entities_cid is not None and relationships_cid is not None:
                # Create from CIDs
                graph_result = kg_manager.create_from_cids(
                    entities_cid=entities_cid,
                    relationships_cid=relationships_cid,
                    graph_name=graph_name,
                    **kwargs,
                )
            else:
                # Create from direct data
                graph_result = kg_manager.create_from_data(
                    entities=entities, relationships=relationships, graph_name=graph_name, **kwargs
                )

            return graph_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_create_knowledge_graph",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "graph_name": graph_name,
            }

    def ai_get_endpoint_status(self, endpoint_id, **kwargs):
        """
        Get the status of a deployed model endpoint.

        Args:
            endpoint_id: ID of the endpoint to check
            **kwargs: Additional parameters

        Returns:
            Dictionary with endpoint status information
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "include_metrics": {"type": bool, "default": True},
                "timeout": {"type": int, "default": 30},
            },
        )

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simulation for demonstration
            result = {
                "success": True,
                "operation": "ai_get_endpoint_status",
                "timestamp": time.time(),
                "simulation_note": "AI/ML integration not available, using simulated response",
                "endpoint_id": endpoint_id,
                "status": "ready",  # One of: deploying, ready, error, scaling, updating
                "url": f"https://api.example.com/models/{endpoint_id.split('-')[1]}",
                "metrics": {
                    "requests_per_second": 0.5,
                    "average_latency_ms": 42,
                    "success_rate": 0.99,
                },
                "resources": {"cpu_usage": "5%", "memory_usage": "256MB", "replicas": 1},
                "last_updated": time.time() - 300,  # 5 minutes ago
            }

            return result

        # If AI/ML integration is available, use the real implementation
        try:
            # Create model deployment
            deployment = ai_ml_integration.ModelDeployer(self._kit)

            status_result = deployment.get_endpoint_status(endpoint_id=endpoint_id, **kwargs)

            return status_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_get_endpoint_status",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "endpoint_id": endpoint_id,
            }

    def ai_test_inference(self, endpoint_id, data, **kwargs):
        """
        Test a deployed model with inference data.

        Args:
            endpoint_id: ID of the endpoint to test
            data: Input data for the model
            **kwargs: Additional parameters

        Returns:
            Dictionary with inference results
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "model_version": {"type": str},
                "timeout": {"type": int, "default": 60},
                "return_raw": {"type": bool, "default": False},
            },
        )

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simulation for demonstration
            result = {
                "success": True,
                "operation": "ai_test_inference",
                "timestamp": time.time(),
                "simulation_note": "AI/ML integration not available, using simulated response",
                "endpoint_id": endpoint_id,
                "predictions": [0.78, 0.22],  # Simple binary classification example
                "latency_ms": 42,
                "model_version": kwargs.get("model_version", "1.0.0"),
            }

            return result

        # If AI/ML integration is available, use the real implementation
        try:
            # Create model deployment
            deployment = ai_ml_integration.ModelDeployer(self._kit)

            inference_result = deployment.test_inference(
                endpoint_id=endpoint_id, data=data, **kwargs
            )

            return inference_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_test_inference",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "endpoint_id": endpoint_id,
            }

    def ai_update_deployment(self, endpoint_id, model_cid, **kwargs):
        """
        Update a deployed model with a new version.

        Args:
            endpoint_id: ID of the endpoint to update
            model_cid: CID of the new model version
            **kwargs: Additional parameters

        Returns:
            Dictionary with update operation result
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "version": {"type": str},
                "strategy": {"type": str, "default": "rolling"},
                "timeout": {"type": int, "default": 300},
            },
        )

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simulation for demonstration
            result = {
                "success": True,
                "operation": "ai_update_deployment",
                "timestamp": time.time(),
                "simulation_note": "AI/ML integration not available, using simulated response",
                "endpoint_id": endpoint_id,
                "previous_model_cid": f"Qm{os.urandom(16).hex()}",
                "new_model_cid": model_cid,
                "status": "updating",
                "update_strategy": kwargs.get("strategy", "rolling"),
                "updated_at": time.time(),
                "estimated_completion_time": time.time() + 30,  # 30 seconds to update
            }

            return result

        # If AI/ML integration is available, use the real implementation
        try:
            # Create model deployment
            deployment = ai_ml_integration.ModelDeployer(self._kit)

            update_result = deployment.update_endpoint(
                endpoint_id=endpoint_id, model_cid=model_cid, **kwargs
            )

            return update_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_update_deployment",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "endpoint_id": endpoint_id,
                "model_cid": model_cid,
            }

    def ai_distributed_training_submit_job(
        self, training_task, worker_count=1, priority=1, **kwargs
    ):
        """
        Submit a distributed training job.

        Args:
            training_task: Dictionary describing the training task
            worker_count: Number of worker nodes to allocate
            priority: Job priority (1-10, higher is more important)
            **kwargs: Additional parameters

        Returns:
            Dictionary with job submission result
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "timeout": {"type": int, "default": 3600},
                "resources": {"type": dict},
                "dependencies": {"type": list},
                "notify_on_completion": {"type": bool, "default": False},
            },
        )

        # Validate priority
        if not 1 <= priority <= 10:
            raise ValueError("priority must be between 1 and 10")

        # Validate worker count
        if worker_count < 1:
            raise ValueError("worker_count must be at least 1")

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simulation for demonstration
            import uuid

            job_id = str(uuid.uuid4())

            result = {
                "success": True,
                "operation": "ai_distributed_training_submit_job",
                "timestamp": time.time(),
                "simulation_note": "AI/ML integration not available, using simulated response",
                "job_id": job_id,
                "worker_count": worker_count,
                "priority": priority,
                "status": "queued",
                "submitted_at": time.time(),
                "estimated_start_time": time.time() + 5,  # 5 seconds from now
                "task": training_task,
            }

            return result

        # If AI/ML integration is available, use the real implementation
        try:
            # Create distributed training manager
            training_manager = ai_ml_integration.DistributedTraining(self._kit)

            job_result = training_manager.submit_job(
                training_task=training_task, worker_count=worker_count, priority=priority, **kwargs
            )

            return job_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_distributed_training_submit_job",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
            }

    def ai_distributed_training_get_status(self, job_id, **kwargs):
        """
        Get the status of a distributed training job.

        Args:
            job_id: ID of the job to check
            **kwargs: Additional parameters

        Returns:
            Dictionary with job status information
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "include_metrics": {"type": bool, "default": True},
                "include_logs": {"type": bool, "default": False},
                "timeout": {"type": int, "default": 30},
            },
        )

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simulation for demonstration
            result = {
                "success": True,
                "operation": "ai_distributed_training_get_status",
                "timestamp": time.time(),
                "simulation_note": "AI/ML integration not available, using simulated response",
                "job_id": job_id,
                "status": "running",
                "progress": {
                    "total_tasks": 10,
                    "completed_tasks": 4,
                    "percentage": 40,
                    "active_workers": 3,
                },
                "metrics": {
                    "current_epoch": 4,
                    "loss": 0.342,
                    "accuracy": 0.78,
                    "elapsed_time_seconds": 120,
                },
                "start_time": time.time() - 120,  # Started 2 minutes ago
                "estimated_completion_time": time.time() + 180,  # Will complete in 3 minutes
            }

            return result

        # If AI/ML integration is available, use the real implementation
        try:
            # Create distributed training manager
            training_manager = ai_ml_integration.DistributedTraining(self._kit)

            status_result = training_manager.get_job_status(job_id=job_id, **kwargs)

            return status_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_distributed_training_get_status",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "job_id": job_id,
            }

    def ai_distributed_training_cancel_job(self, job_id, **kwargs):
        """
        Cancel a distributed training job.

        Args:
            job_id: ID of the job to cancel
            **kwargs: Additional parameters

        Returns:
            Dictionary with job cancellation result
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "reason": {"type": str},
                "save_partial_results": {"type": bool, "default": True},
                "timeout": {"type": int, "default": 60},
            },
        )

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simulation for demonstration
            result = {
                "success": True,
                "operation": "ai_distributed_training_cancel_job",
                "timestamp": time.time(),
                "simulation_note": "AI/ML integration not available, using simulated response",
                "job_id": job_id,
                "cancelled_at": time.time(),
                "previous_status": "running",
                "current_status": "cancelled",
                "reason": kwargs.get("reason", "User requested cancellation"),
                "partial_results_cid": (
                    f"Qm{os.urandom(16).hex()}"
                    if kwargs.get("save_partial_results", True)
                    else None
                ),
            }

            return result

        # If AI/ML integration is available, use the real implementation
        try:
            # Create distributed training manager
            training_manager = ai_ml_integration.DistributedTraining(self._kit)

            cancel_result = training_manager.cancel_job(job_id=job_id, **kwargs)

            return cancel_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_distributed_training_cancel_job",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "job_id": job_id,
            }

    def ai_distributed_training_aggregate_results(self, job_id, **kwargs):
        """
        Aggregate results from a distributed training job.

        Args:
            job_id: ID of the job to aggregate results for
            **kwargs: Additional parameters

        Returns:
            Dictionary with aggregated results
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "aggregation_method": {"type": str, "default": "model_averaging"},
                "save_to_registry": {"type": bool, "default": True},
                "timeout": {"type": int, "default": 300},
            },
        )

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simulation for demonstration
            model_cid = f"Qm{os.urandom(16).hex()}"

            result = {
                "success": True,
                "operation": "ai_distributed_training_aggregate_results",
                "timestamp": time.time(),
                "simulation_note": "AI/ML integration not available, using simulated response",
                "job_id": job_id,
                "model_cid": model_cid,
                "metrics": {
                    "final_loss": 0.12,
                    "final_accuracy": 0.92,
                    "training_time_seconds": 350,
                },
                "partial_results": [
                    {
                        "worker_id": f"worker-{i}",
                        "batch_range": f"{i*10}-{(i+1)*10-1}",
                        "metrics": {"loss": 0.12 + (i * 0.01), "accuracy": 0.92 - (i * 0.01)},
                    }
                    for i in range(3)
                ],
                "aggregation_method": kwargs.get("aggregation_method", "model_averaging"),
                "completed_at": time.time(),
            }

            return result

        # If AI/ML integration is available, use the real implementation
        try:
            # Create distributed training manager
            training_manager = ai_ml_integration.DistributedTraining(self._kit)

            aggregation_result = training_manager.aggregate_results(job_id=job_id, **kwargs)

            return aggregation_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_distributed_training_aggregate_results",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "job_id": job_id,
            }

    def ai_langchain_load_documents(self, docs_cid, recursive=True, filter_pattern=None, **kwargs):
        """
        Load documents from IPFS using Langchain document loaders.

        Args:
            docs_cid: CID of the document or directory to load
            recursive: Whether to recursively load documents from subdirectories
            filter_pattern: File pattern to filter (e.g., "*.txt", "*.pdf")
            **kwargs: Additional parameters

        Returns:
            Dictionary with loaded documents
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "encoding": {"type": str, "default": "utf-8"},
                "chunk_size": {"type": int},
                "chunk_overlap": {"type": int},
                "max_documents": {"type": int},
                "timeout": {"type": int, "default": 300},
            },
        )

        # Check if Langchain integration is available
        langchain_available = False
        try:
            import langchain

            langchain_available = True
        except ImportError:
            pass

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE or not langchain_available:
            # Fallback to simulation for demonstration
            # Create simulated document list
            documents = []
            for i in range(3):  # Simulate 3 documents
                documents.append(
                    {
                        "id": f"doc-{i}",
                        "content": f"This is sample document {i} for testing Langchain integration with IPFS Kit.\n"
                        f"It contains information about topic {i} that can be retrieved using LLMs.\n"
                        f"This document discusses various aspects of machine learning and IPFS integration.\n",
                        "metadata": {
                            "source": f"document_{i}.txt",
                            "cid": docs_cid,
                            "path": f"{docs_cid}/document_{i}.txt",
                        },
                    }
                )

            result = {
                "success": True,
                "operation": "ai_langchain_load_documents",
                "timestamp": time.time(),
                "simulation_note": "AI/ML or Langchain not available, using simulated response",
                "documents": documents,
                "count": len(documents),
                "filter_pattern": filter_pattern,
                "recursive": recursive,
            }

            return result

        # If AI/ML and Langchain integration is available, use the real implementation
        try:
            # Create Langchain integration
            langchain_manager = ai_ml_integration.LangchainIntegration(self._kit)

            load_result = langchain_manager.load_documents(
                docs_cid=docs_cid, recursive=recursive, filter_pattern=filter_pattern, **kwargs
            )

            return load_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_langchain_load_documents",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "docs_cid": docs_cid,
            }

    def ai_langchain_create_vectorstore(
        self, documents, embedding_model, vector_store_type="faiss", **kwargs
    ):
        """
        Create a vector store from documents using Langchain.

        Args:
            documents: List of documents to vectorize
            embedding_model: Name or path of embedding model to use
            vector_store_type: Type of vector store to create (faiss, chroma, etc.)
            **kwargs: Additional parameters

        Returns:
            Dictionary with vector store information
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "persist": {"type": bool, "default": True},
                "index_name": {"type": str},
                "distance_metric": {"type": str, "default": "cosine"},
                "timeout": {"type": int, "default": 600},
            },
        )

        # Check if Langchain integration is available
        langchain_available = False
        try:
            import langchain

            langchain_available = True
        except ImportError:
            pass

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE or not langchain_available:
            # Fallback to simulation for demonstration
            result = {
                "success": True,
                "operation": "ai_langchain_create_vectorstore",
                "timestamp": time.time(),
                "simulation_note": "AI/ML or Langchain not available, using simulated response",
                "vector_store_type": vector_store_type,
                "embedding_model": embedding_model,
                "embedding_dimensions": 384 if "MiniLM" in embedding_model else 768,
                "document_count": len(documents) if isinstance(documents, list) else 3,
                "vector_store": f"Simulated {vector_store_type.upper()} vector store",
            }

            return result

        # If AI/ML and Langchain integration is available, use the real implementation
        try:
            # Create Langchain integration
            langchain_manager = ai_ml_integration.LangchainIntegration(self._kit)

            vectorstore_result = langchain_manager.create_vectorstore(
                documents=documents,
                embedding_model=embedding_model,
                vector_store_type=vector_store_type,
                **kwargs,
            )

            return vectorstore_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_langchain_create_vectorstore",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
            }

    def ai_langchain_query(self, vectorstore_cid, query, top_k=2, **kwargs):
        """
        Query a vector store using Langchain.

        Args:
            vectorstore_cid: CID of the vector store to query
            query: Query text
            top_k: Number of top results to return
            **kwargs: Additional parameters

        Returns:
            Dictionary with query results
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "embedding_model": {"type": str},
                "similarity_threshold": {"type": float, "default": 0.0},
                "max_tokens": {"type": int},
                "timeout": {"type": int, "default": 60},
            },
        )

        # Validate similarity threshold
        similarity_threshold = kwargs.get("similarity_threshold", 0.0)
        if not 0.0 <= similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be between 0.0 and 1.0")

        # Check if Langchain integration is available
        langchain_available = False
        try:
            import langchain

            langchain_available = True
        except ImportError:
            pass

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE or not langchain_available:
            # Fallback to simulation for demonstration
            # Create simulated results
            results = []
            for i in range(min(top_k, 3)):  # Simulate up to top_k results (max 3)
                results.append(
                    {
                        "content": f"This is sample document {i} for testing Langchain integration with IPFS Kit.\n"
                        f"It contains information about topic {i} that can be retrieved using LLMs.\n"
                        f"This document discusses various aspects of machine learning and IPFS integration.\n",
                        "metadata": {"source": f"document_{i}.txt", "cid": vectorstore_cid},
                        "similarity": 0.95 - (i * 0.09),  # Decreasing similarity scores
                    }
                )

            result = {
                "success": True,
                "operation": "ai_langchain_query",
                "timestamp": time.time(),
                "simulation_note": "AI/ML or Langchain not available, using simulated response",
                "query": query,
                "results": results,
                "count": len(results),
            }

            return result

        # If AI/ML and Langchain integration is available, use the real implementation
        try:
            # Create Langchain integration
            langchain_manager = ai_ml_integration.LangchainIntegration(self._kit)

            query_result = langchain_manager.query(
                vectorstore_cid=vectorstore_cid, query=query, top_k=top_k, **kwargs
            )

            return query_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_langchain_query",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "query": query,
                "vectorstore_cid": vectorstore_cid,
            }

    def ai_llama_index_load_documents(
        self, docs_cid, recursive=True, filter_pattern=None, **kwargs
    ):
        """
        Load documents from IPFS using LlamaIndex document loaders.

        Args:
            docs_cid: CID of the document or directory to load
            recursive: Whether to recursively load documents from subdirectories
            filter_pattern: File pattern to filter (e.g., "*.txt", "*.pdf")
            **kwargs: Additional parameters

        Returns:
            Dictionary with loaded documents
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "encoding": {"type": str, "default": "utf-8"},
                "chunk_size": {"type": int},
                "chunk_overlap": {"type": int},
                "max_documents": {"type": int},
                "timeout": {"type": int, "default": 300},
            },
        )

        # Check if LlamaIndex integration is available
        llama_index_available = False
        try:
            import llama_index

            llama_index_available = True
        except ImportError:
            pass

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE or not llama_index_available:
            # Fallback to simulation for demonstration
            # Create simulated document list
            documents = []
            for i in range(3):  # Simulate 3 documents
                documents.append(
                    {
                        "id": f"llamadoc-{i}",
                        "content": f"This is sample document {i} for testing LlamaIndex integration with IPFS Kit.\n"
                        f"It contains information about topic {i} that can be retrieved using LLMs.\n"
                        f"This document discusses various aspects of machine learning and IPFS integration.\n",
                        "metadata": {
                            "source": f"llama_doc_{i}.txt",
                            "cid": docs_cid,
                            "path": f"{docs_cid}/llama_doc_{i}.txt",
                        },
                    }
                )

            result = {
                "success": True,
                "operation": "ai_llama_index_load_documents",
                "timestamp": time.time(),
                "simulation_note": "AI/ML or LlamaIndex not available, using simulated response",
                "documents": documents,
                "count": len(documents),
                "filter_pattern": filter_pattern,
                "recursive": recursive,
            }

            return result

        # If AI/ML and LlamaIndex integration is available, use the real implementation
        try:
            # Create LlamaIndex integration
            llama_index_manager = ai_ml_integration.LlamaIndexIntegration(self._kit)

            load_result = llama_index_manager.load_documents(
                docs_cid=docs_cid, recursive=recursive, filter_pattern=filter_pattern, **kwargs
            )

            return load_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_llama_index_load_documents",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "docs_cid": docs_cid,
            }

    def ai_llama_index_create_index(
        self, documents, index_type="vector_store", embed_model=None, **kwargs
    ):
        """
        Create an index from documents using LlamaIndex.

        Args:
            documents: List of documents to index
            index_type: Type of index to create
            embed_model: Embedding model to use
            **kwargs: Additional parameters

        Returns:
            Dictionary with index information
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "persist": {"type": bool, "default": True},
                "index_name": {"type": str},
                "service_context": {"type": dict},
                "timeout": {"type": int, "default": 600},
            },
        )

        # Check if LlamaIndex integration is available
        llama_index_available = False
        try:
            import llama_index

            llama_index_available = True
        except ImportError:
            pass

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE or not llama_index_available:
            # Fallback to simulation for demonstration
            result = {
                "success": True,
                "operation": "ai_llama_index_create_index",
                "timestamp": time.time(),
                "simulation_note": "AI/ML or LlamaIndex not available, using simulated response",
                "index_type": index_type,
                "embedding_model": embed_model or "simulated-embeddings",
                "document_count": len(documents) if isinstance(documents, list) else 3,
                "index": f"Simulated LlamaIndex {index_type} index",
            }

            return result

        # If AI/ML and LlamaIndex integration is available, use the real implementation
        try:
            # Create LlamaIndex integration
            llama_index_manager = ai_ml_integration.LlamaIndexIntegration(self._kit)

            index_result = llama_index_manager.create_index(
                documents=documents, index_type=index_type, embed_model=embed_model, **kwargs
            )

            return index_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_llama_index_create_index",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
            }

    def ai_llama_index_query(self, index_cid, query, response_mode="compact", **kwargs):
        """
        Query an index using LlamaIndex.

        Args:
            index_cid: CID of the index to query
            query: Query text
            response_mode: Response mode (compact, tree, etc.)
            **kwargs: Additional parameters

        Returns:
            Dictionary with query results
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "similarity_top_k": {"type": int, "default": 2},
                "embed_model": {"type": str},
                "llm": {"type": dict},
                "max_tokens": {"type": int},
                "timeout": {"type": int, "default": 60},
            },
        )

        # Check if LlamaIndex integration is available
        llama_index_available = False
        try:
            import llama_index

            llama_index_available = True
        except ImportError:
            pass

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE or not llama_index_available:
            # Fallback to simulation for demonstration
            # Create simulated source nodes
            source_nodes = []
            for i in range(2):  # Simulate 2 source nodes
                source_nodes.append(
                    {
                        "content": f"This is sample document {i} for testing LlamaIndex integration with IPFS Kit.\n"
                        f"It contains information about topic {i} that can be retrieved using LLMs.\n"
                        f"This document discusses various aspects of machine learning and IPFS integration.\n",
                        "metadata": {"source": f"llama_doc_{i}.txt", "cid": index_cid},
                        "score": 0.92 - (i * 0.07),
                    }
                )

            result = {
                "success": True,
                "operation": "ai_llama_index_query",
                "timestamp": time.time(),
                "simulation_note": "AI/ML or LlamaIndex not available, using simulated response",
                "query": query,
                "response": "The documents discuss various aspects of machine learning and IPFS integration across different topics.",
                "source_nodes": source_nodes,
                "response_mode": response_mode,
            }

            return result

        # If AI/ML and LlamaIndex integration is available, use the real implementation
        try:
            # Create LlamaIndex integration
            llama_index_manager = ai_ml_integration.LlamaIndexIntegration(self._kit)

            query_result = llama_index_manager.query(
                index_cid=index_cid, query=query, response_mode=response_mode, **kwargs
            )

            return query_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_llama_index_query",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "query": query,
                "index_cid": index_cid,
            }

    def ai_benchmark_model(self, model_cid, dataset_cid, metrics=None, **kwargs):
        """
        Benchmark a model on a dataset.

        Args:
            model_cid: CID of the model to benchmark
            dataset_cid: CID of the dataset to use for benchmarking
            metrics: List of metrics to calculate (accuracy, f1_score, etc.)
            **kwargs: Additional parameters

        Returns:
            Dictionary with benchmark results
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "batch_size": {"type": int, "default": 32},
                "num_workers": {"type": int, "default": 4},
                "device": {"type": str, "default": "cpu"},
                "timeout": {"type": int, "default": 600},
            },
        )

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simulation for demonstration
            # Set default metrics if not provided
            if metrics is None:
                metrics = ["accuracy", "f1_score", "latency"]

            # Create simulated benchmark result
            result = {
                "success": True,
                "operation": "ai_benchmark_model",
                "timestamp": time.time(),
                "simulation_note": "AI/ML integration not available, using simulated response",
                "model_cid": model_cid,
                "dataset_cid": dataset_cid,
                "metrics": {
                    metric: 0.8
                    + (0.05 * (hash(metric) % 10) / 10)  # Random-ish but deterministic value
                    for metric in metrics
                    if metric != "latency_ms"
                },
                "benchmark_id": f"bench-{os.urandom(4).hex()}",
                "completed_at": time.time(),
            }

            # Add latency metric if requested
            if "latency" in metrics or "latency_ms" in metrics:
                result["metrics"]["latency_ms"] = 120

            return result

        # If AI/ML integration is available, use the real implementation
        try:
            # Create model manager
            model_manager = ai_ml_integration.ModelManager(self._kit)

            benchmark_result = model_manager.benchmark_model(
                model_cid=model_cid, dataset_cid=dataset_cid, metrics=metrics, **kwargs
            )

            return benchmark_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_benchmark_model",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "model_cid": model_cid,
                "dataset_cid": dataset_cid,
            }

    def ai_data_loader(self, dataset_cid, batch_size=32, shuffle=True, **kwargs):
        """
        Create a data loader for a dataset.

        Args:
            dataset_cid: CID of the dataset to load
            batch_size: Batch size for the data loader
            shuffle: Whether to shuffle the dataset
            **kwargs: Additional parameters

        Returns:
            Dictionary with data loader information
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "framework": {"type": str},
                "num_workers": {"type": int, "default": 4},
                "pin_memory": {"type": bool, "default": True},
                "prefetch_factor": {"type": int, "default": 2},
                "timeout": {"type": int, "default": 60},
            },
        )

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simulation for demonstration
            result = {
                "success": True,
                "operation": "ai_data_loader",
                "timestamp": time.time(),
                "simulation_note": "AI/ML integration not available, using simulated response",
                "dataset_cid": dataset_cid,
                "batch_size": batch_size,
                "shuffle": shuffle,
                "framework": kwargs.get("framework", "generic"),
                "loader": f"Simulated data loader for {dataset_cid}",
            }

            return result

        # If AI/ML integration is available, use the real implementation
        try:
            # Create dataset manager
            dataset_manager = ai_ml_integration.DatasetManager(self._kit)

            loader_result = dataset_manager.create_data_loader(
                dataset_cid=dataset_cid, batch_size=batch_size, shuffle=shuffle, **kwargs
            )

            return loader_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_data_loader",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "dataset_cid": dataset_cid,
            }

    def ai_hybrid_search(
        self, query, vector_index_cid, keyword_weight=0.3, vector_weight=0.7, top_k=3, **kwargs
    ):
        """
        Perform hybrid search combining vector and keyword search.

        Args:
            query: Query text
            vector_index_cid: CID of the vector index
            keyword_weight: Weight for keyword search results (0.0-1.0)
            vector_weight: Weight for vector search results (0.0-1.0)
            top_k: Number of top results to return
            **kwargs: Additional parameters

        Returns:
            Dictionary with hybrid search results
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "filter": {"type": dict},
                "embedding_model": {"type": str},
                "similarity_threshold": {"type": float, "default": 0.0},
                "timeout": {"type": int, "default": 60},
            },
        )

        # Validate weights
        if not 0.0 <= keyword_weight <= 1.0:
            raise ValueError("keyword_weight must be between 0.0 and 1.0")

        if not 0.0 <= vector_weight <= 1.0:
            raise ValueError("vector_weight must be between 0.0 and 1.0")

        # Check weights sum to approximately 1.0
        if abs(keyword_weight + vector_weight - 1.0) > 0.01:
            raise ValueError("keyword_weight and vector_weight should sum to approximately 1.0")

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simulation for demonstration
            # Create simulated hybrid search results
            results = []
            for i in range(min(top_k, 3)):  # Simulate up to top_k results (max 3)
                results.append(
                    {
                        "content": f"This is document {i} about topic {i % 3}.\n"
                        f"It contains information that might be relevant to search queries.\n"
                        f"Keywords: topic{i % 3}, example, document{i}\n",
                        "vector_score": 0.89 - (i * 0.03),
                        "keyword_score": 0.76 - (i * 0.06),
                        "combined_score": 0.85 - (i * 0.04),
                        "metadata": {
                            "source": f"document_{i}.txt",
                            "cid": f"Qm{os.urandom(16).hex()}",
                        },
                    }
                )

            result = {
                "success": True,
                "operation": "ai_hybrid_search",
                "timestamp": time.time(),
                "simulation_note": "AI/ML integration not available, using simulated response",
                "query": query,
                "results": results,
                "weights": {"vector": vector_weight, "keyword": keyword_weight},
                "search_time_ms": 12,
            }

            return result

        # If AI/ML integration is available, use the real implementation
        try:
            # Create search manager
            search_manager = ai_ml_integration.SearchManager(self._kit)

            search_result = search_manager.hybrid_search(
                query=query,
                vector_index_cid=vector_index_cid,
                keyword_weight=keyword_weight,
                vector_weight=vector_weight,
                top_k=top_k,
                **kwargs,
            )

            return search_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_hybrid_search",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "query": query,
                "vector_index_cid": vector_index_cid,
            }

    def ai_create_embeddings(
        self, docs_cid, embedding_model, recursive=True, filter_pattern=None, **kwargs
    ):
        """
        Create embeddings for documents using a specified model.

        Args:
            docs_cid: CID of the document or directory to process
            embedding_model: Name or path of embedding model to use
            recursive: Whether to recursively process documents from subdirectories
            filter_pattern: File pattern to filter (e.g., "*.txt", "*.pdf")
            **kwargs: Additional parameters

        Returns:
            Dictionary with embedding information and result CID
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "chunk_size": {"type": int},
                "chunk_overlap": {"type": int},
                "batch_size": {"type": int, "default": 32},
                "index_type": {"type": str, "default": "hnsw"},
                "timeout": {"type": int, "default": 600},
            },
        )

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simulation for demonstration
            embedding_cid = f"Qm{os.urandom(16).hex()}"

            result = {
                "success": True,
                "operation": "ai_create_embeddings",
                "timestamp": time.time(),
                "simulation_note": "AI/ML integration not available, using simulated response",
                "cid": embedding_cid,
                "embedding_count": 5,
                "dimensions": 384 if "MiniLM" in embedding_model else 768,
                "embedding_model": embedding_model,
                "documents": [f"{docs_cid}/{i}.txt" for i in range(5)],
                "index_type": kwargs.get("index_type", "hnsw"),
            }

            return result

        # If AI/ML integration is available, use the real implementation
        try:
            # Create embedding manager
            embedding_manager = ai_ml_integration.EmbeddingManager(self._kit)

            embedding_result = embedding_manager.create_embeddings(
                docs_cid=docs_cid,
                embedding_model=embedding_model,
                recursive=recursive,
                filter_pattern=filter_pattern,
                **kwargs,
            )

            return embedding_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_create_embeddings",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "docs_cid": docs_cid,
            }

    def ai_create_vector_index(self, embedding_cid, index_type="hnsw", params=None, **kwargs):
        """
        Create a vector search index from embeddings.

        Args:
            embedding_cid: CID of the embeddings to index
            index_type: Type of index to create (hnsw, flat, ivf, etc.)
            params: Parameters for the index creation
            **kwargs: Additional parameters

        Returns:
            Dictionary with vector index information
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "metric_type": {"type": str, "default": "cosine"},
                "persist": {"type": bool, "default": True},
                "optimize_for": {"type": str, "default": "recall"},
                "timeout": {"type": int, "default": 300},
            },
        )

        # Set default params if not provided
        if params is None:
            params = {"M": 16, "efConstruction": 200, "efSearch": 50}

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simulation for demonstration
            index_cid = f"Qm{os.urandom(16).hex()}"

            result = {
                "success": True,
                "operation": "ai_create_vector_index",
                "timestamp": time.time(),
                "simulation_note": "AI/ML integration not available, using simulated response",
                "cid": index_cid,
                "index_type": index_type,
                "dimensions": 384,  # Default dimension
                "vector_count": 5,  # Default count
                "parameters": params,
                "metadata": {
                    "embedding_model": "simulated-embeddings",
                    "documents_cid": f"Qm{os.urandom(16).hex()}",
                },
            }

            return result

        # If AI/ML integration is available, use the real implementation
        try:
            # Create embedding manager
            embedding_manager = ai_ml_integration.EmbeddingManager(self._kit)

            index_result = embedding_manager.create_vector_index(
                embedding_cid=embedding_cid, index_type=index_type, params=params, **kwargs
            )

            return index_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_create_vector_index",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "embedding_cid": embedding_cid,
            }

    def ai_query_knowledge_graph(self, graph_cid, query, query_type="cypher", **kwargs):
        """
        Query a knowledge graph.

        Args:
            graph_cid: CID of the knowledge graph to query
            query: Query string (syntax depends on query_type)
            query_type: Query language type (cypher, sparql, etc.)
            **kwargs: Additional parameters

        Returns:
            Dictionary with query results
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "limit": {"type": int, "default": 100},
                "parameters": {"type": dict},
                "timeout": {"type": int, "default": 60},
            },
        )

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simulation for demonstration
            # Create simulated query result for demonstration
            # Different behavior based on query type

            if query_type == "cypher" and "MATCH (p:Person)" in query:
                # Simulate a person query
                results = [
                    {
                        "p": {"id": "entity1", "type": "Person", "name": "John Doe", "age": 30},
                        "r": {
                            "from": "entity1",
                            "to": "entity2",
                            "type": "WORKS_FOR",
                            "since": 2020,
                        },
                        "c": {
                            "id": "entity2",
                            "type": "Company",
                            "name": "Acme Corp",
                            "industry": "Technology",
                        },
                    },
                    {
                        "p": {"id": "entity4", "type": "Person", "name": "Jane Smith", "age": 28},
                        "r": {
                            "from": "entity4",
                            "to": "entity2",
                            "type": "WORKS_FOR",
                            "since": 2019,
                        },
                        "c": {
                            "id": "entity2",
                            "type": "Company",
                            "name": "Acme Corp",
                            "industry": "Technology",
                        },
                    },
                ]
            elif query_type == "cypher" and "MATCH (c:Company)" in query:
                # Simulate a company query
                results = [
                    {
                        "c": {
                            "id": "entity2",
                            "type": "Company",
                            "name": "Acme Corp",
                            "industry": "Technology",
                        },
                        "p": {
                            "id": "entity3",
                            "type": "Product",
                            "name": "Widget X",
                            "price": 99.99,
                        },
                    }
                ]
            else:
                # Generic simulation
                results = [{"result": f"Simulated result for query: {query[:20]}..."}]

            result = {
                "success": True,
                "operation": "ai_query_knowledge_graph",
                "timestamp": time.time(),
                "simulation_note": "AI/ML integration not available, using simulated response",
                "query": query,
                "query_type": query_type,
                "results": results,
                "execution_time_ms": 8,
            }

            return result

        # If AI/ML integration is available, use the real implementation
        try:
            # Create knowledge graph manager
            kg_manager = ai_ml_integration.KnowledgeGraph(self._kit)

            query_result = kg_manager.query(
                graph_cid=graph_cid, query=query, query_type=query_type, **kwargs
            )

            return query_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_query_knowledge_graph",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "query": query,
                "graph_cid": graph_cid,
            }

    def ai_calculate_graph_metrics(self, graph_cid, metrics=None, **kwargs):
        """
        Calculate metrics for a knowledge graph.

        Args:
            graph_cid: CID of the knowledge graph
            metrics: List of metrics to calculate
            **kwargs: Additional parameters

        Returns:
            Dictionary with graph metrics
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "focus_entities": {"type": list},
                "timeout": {"type": int, "default": 300},
            },
        )

        # Set default metrics if not provided
        if metrics is None:
            metrics = ["centrality", "clustering_coefficient"]

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simulation for demonstration
            # Create simulated metrics result
            metrics_result = {
                "centrality": {
                    "entity1": 0.67,  # John Doe
                    "entity2": 1.0,  # Acme Corp (highest centrality)
                    "entity3": 0.33,  # Widget X
                    "entity4": 0.67,  # Jane Smith
                },
                "clustering_coefficient": {
                    "entity1": 0.33,
                    "entity2": 0,
                    "entity3": 0,
                    "entity4": 0.5,
                },
                "average_path_length": 1.67,
                "graph_density": 0.33,
            }

            # Remove metrics that weren't requested
            metrics_result = {k: v for k, v in metrics_result.items() if k in metrics}

            result = {
                "success": True,
                "operation": "ai_calculate_graph_metrics",
                "timestamp": time.time(),
                "simulation_note": "AI/ML integration not available, using simulated response",
                "graph_cid": graph_cid,
                "metrics": metrics_result,
                "calculation_time_ms": 15,
            }

            return result

        # If AI/ML integration is available, use the real implementation
        try:
            # Create knowledge graph manager
            kg_manager = ai_ml_integration.KnowledgeGraph(self._kit)

            metrics_result = kg_manager.calculate_metrics(
                graph_cid=graph_cid, metrics=metrics, **kwargs
            )

            return metrics_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_calculate_graph_metrics",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "graph_cid": graph_cid,
            }

    def ai_expand_knowledge_graph(
        self, graph_cid, seed_entity, data_source, expansion_type, max_entities=5, **kwargs
    ):
        """
        Expand a knowledge graph with additional entities and relationships.

        Args:
            graph_cid: CID of the knowledge graph to expand
            seed_entity: Entity ID to start expansion from
            data_source: Source of expansion data
            expansion_type: Type of expansion to perform
            max_entities: Maximum number of new entities to add
            **kwargs: Additional parameters

        Returns:
            Dictionary with expanded graph information
        """
        from . import validation

        # Validate parameters
        validation.validate_parameters(
            kwargs,
            {
                "max_hops": {"type": int, "default": 2},
                "relationship_types": {"type": list},
                "timeout": {"type": int, "default": 600},
            },
        )

        # Check if AI/ML integration is available
        if not AI_ML_AVAILABLE:
            # Fallback to simulation for demonstration
            new_graph_cid = f"Qm{os.urandom(16).hex()}"

            # Create simulated expansion entities and relationships
            added_entities = []
            added_relationships = []

            for i in range(min(max_entities, 3)):  # Add up to max_entities (max 3)
                entity_id = f"entity{i+5}"  # Start from entity5

                if expansion_type == "competitors" and i < 2:
                    # Add competitor companies
                    added_entities.append(
                        {
                            "id": entity_id,
                            "type": "Company",
                            "name": f"Company {chr(65+i)}",  # Company A, Company B
                            "industry": "Technology",
                        }
                    )

                    # Add relationship to seed entity
                    added_relationships.append(
                        {
                            "from": seed_entity,
                            "to": entity_id,
                            "type": "COMPETES_WITH",
                            "market_overlap": 0.7 - (i * 0.3),
                        }
                    )
                else:
                    # Add person
                    added_entities.append(
                        {
                            "id": entity_id,
                            "type": "Person",
                            "name": f"Person {chr(65+i)}",  # Person A, Person B
                            "age": 30 + i,
                        }
                    )

                    # Add relationship to a company
                    if i > 0 and len(added_entities) > 1:
                        company_entity = added_entities[0]["id"]  # Use first company
                        added_relationships.append(
                            {
                                "from": entity_id,
                                "to": company_entity,
                                "type": "WORKS_FOR",
                                "since": 2020 - i,
                                "position": f"Role {i}",
                            }
                        )

            result = {
                "success": True,
                "operation": "ai_expand_knowledge_graph",
                "timestamp": time.time(),
                "simulation_note": "AI/ML integration not available, using simulated response",
                "original_graph_cid": graph_cid,
                "expanded_graph_cid": new_graph_cid,
                "seed_entity": seed_entity,
                "data_source": data_source,
                "expansion_type": expansion_type,
                "added_entities": added_entities,
                "added_relationships": added_relationships,
                "entity_count": 7,  # Original 4 + 3 new ones
                "relationship_count": 7,  # Original 4 + 3 new ones
            }

            return result

        # If AI/ML integration is available, use the real implementation
        try:
            # Create knowledge graph manager
            kg_manager = ai_ml_integration.KnowledgeGraph(self._kit)

            expansion_result = kg_manager.expand_graph(
                graph_cid=graph_cid,
                seed_entity=seed_entity,
                data_source=data_source,
                expansion_type=expansion_type,
                max_entities=max_entities,
                **kwargs,
            )

            return expansion_result

        except Exception as e:
            # Return error information
            return {
                "success": False,
                "operation": "ai_expand_knowledge_graph",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__,
                "graph_cid": graph_cid,
                "seed_entity": seed_entity,
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
            with open(config_path, "w") as f:
                if config_path.endswith((".yaml", ".yml")):
                    yaml.dump(self.config, f, default_flow_style=False)
                else:
                    json.dump(self.config, f, indent=2)

            return {
                "success": True,
                "path": config_path,
                "message": f"Configuration saved to {config_path}",
            }
        except Exception as e:
            return {
                "success": False,
                "path": config_path,
                "error": str(e),
                "message": f"Failed to save configuration to {config_path}: {e}",
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
# This is disabled during import to prevent test failures
# Applications should create their own instance when needed
# ipfs = IPFSSimpleAPI()
