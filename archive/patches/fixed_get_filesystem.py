"""Utility module providing an improved implementation of the get_filesystem method.

This module contains an enhanced implementation of the get_filesystem method that can be
used in the ipfs_kit_py classes to provide access to the FSSpec filesystem interface.
It offers improved error handling, configuration management, and backward compatibility.
"""
import logging
from typing import Any, Dict, List, Optional, Union

# Initialize logger
logger = logging.getLogger(__name__)

# Flag to track if FSSpec is available
FSSPEC_AVAILABLE = False
try:
    import fsspec
    FSSPEC_AVAILABLE = True
except ImportError:
    FSSPEC_AVAILABLE = False


def get_filesystem(
    self,
    *,
    gateway_urls: Optional[List[str]] = None,
    use_gateway_fallback: Optional[bool] = None, 
    gateway_only: Optional[bool] = None,
    cache_config: Optional[Dict[str, Any]] = None,
    enable_metrics: Optional[bool] = None,
    return_mock: bool = False,  # For backward compatibility and testing
    **kwargs
) -> Optional[Any]:
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
        return_mock: If True, return a mock filesystem when dependencies are missing instead of raising an error
        **kwargs: Additional parameters to pass to the filesystem

    Returns:
        FSSpec-compatible filesystem interface for IPFS, or a mock filesystem if dependencies are missing
        and return_mock is True

    Raises:
        ImportError: If FSSpec or IPFSFileSystem are not available and return_mock is False
        IPFSConfigurationError: If there's a problem with the configuration
    """
    # Return cached filesystem instance if available
    if hasattr(self, "_filesystem") and self._filesystem is not None:
        return self._filesystem
    
    # Define MockIPFSFileSystem for testing and backward compatibility
    class MockIPFSFileSystem:
        def __init__(self, **kwargs):
            self.protocol = "ipfs"
            self.kwargs = kwargs
            logger.debug(f"Created MockIPFSFileSystem with {len(kwargs)} parameters")
            
        def __call__(self, *args, **kwargs):
            return None
            
        def cat(self, path, **kwargs):
            return b""
            
        def ls(self, path, **kwargs):
            return []
            
        def info(self, path, **kwargs):
            return {"name": path, "size": 0, "type": "file"}
            
        def open(self, path, mode="rb", **kwargs):
            from io import BytesIO
            return BytesIO(b"")
    
    # Check if fsspec is available
    FSSPEC_AVAILABLE = False
    try:
        import fsspec
        FSSPEC_AVAILABLE = True
    except ImportError:
        FSSPEC_AVAILABLE = False
        logger.warning("FSSpec is not available. Please install fsspec to use the filesystem interface.")
        if not return_mock:
            raise ImportError("fsspec is not available. Please install fsspec to use this feature.")
    
    # Try to import IPFSFileSystem if fsspec is available
    HAVE_IPFSFS = False
    if FSSPEC_AVAILABLE:
        try:
            # Try relative import first, then absolute import
            try:
                from .ipfs_fsspec import IPFSFileSystem
            except ImportError:
                from ipfs_kit_py.ipfs_fsspec import IPFSFileSystem
            HAVE_IPFSFS = True
        except ImportError:
            HAVE_IPFSFS = False
            logger.warning(
                "ipfs_fsspec.IPFSFileSystem is not available. Please ensure your installation is complete."
            )
            if not return_mock:
                raise ImportError("ipfs_fsspec.IPFSFileSystem is not available. Please ensure your installation is complete.")
    
    # If dependencies are missing and return_mock is True, return the mock filesystem
    if not FSSPEC_AVAILABLE or not HAVE_IPFSFS:
        if return_mock:
            logger.info("Using mock filesystem due to missing dependencies")
            return MockIPFSFileSystem(**kwargs)
        else:
            # This should never be reached due to the earlier raises, but included for safety
            raise ImportError("Required dependencies for filesystem interface are not available")

    # Prepare configuration with clear precedence:
    # 1. Explicit parameters to this method
    # 2. Values from kwargs
    # 3. Values from config
    # 4. Default values
    fs_kwargs = {}
    
    # Process each parameter with the same pattern to maintain clarity
    param_mapping = {
        "gateway_urls": gateway_urls,
        "use_gateway_fallback": use_gateway_fallback,
        "gateway_only": gateway_only,
        "cache_config": cache_config,
        "enable_metrics": enable_metrics,
        "ipfs_path": kwargs.get("ipfs_path"),
        "socket_path": kwargs.get("socket_path"),
        "use_mmap": kwargs.get("use_mmap")
    }
    
    config_mapping = {
        "cache_config": "cache",  # Handle special case where config key differs
    }
    
    default_values = {
        "role": "leecher",
        "use_mmap": True
    }
    
    # Build configuration with proper precedence
    for param, value in param_mapping.items():
        if value is not None:
            # Explicit parameter was provided
            fs_kwargs[param] = value
        elif param in kwargs:
            # Value is in kwargs
            fs_kwargs[param] = kwargs[param]
        elif param in config_mapping and hasattr(self, "config") and config_mapping[param] in self.config:
            # Special case for differently named config keys
            fs_kwargs[param] = self.config[config_mapping[param]]
        elif hasattr(self, "config") and param in self.config:
            # Regular config parameter
            fs_kwargs[param] = self.config[param]
        elif param in default_values:
            # Use default value if available
            fs_kwargs[param] = default_values[param]
    
    # Special case for role which needs a slightly different logic
    if "role" not in fs_kwargs:
        if "role" in kwargs:
            fs_kwargs["role"] = kwargs["role"]
        elif hasattr(self, "config"):
            fs_kwargs["role"] = self.config.get("role", "leecher")
        else:
            fs_kwargs["role"] = "leecher"
    
    # Add any remaining kwargs that weren't explicitly handled
    for key, value in kwargs.items():
        if key not in fs_kwargs:
            fs_kwargs[key] = value

    # Try to create the filesystem
    try:
        # Create the filesystem
        self._filesystem = IPFSFileSystem(**fs_kwargs)
        logger.info("IPFSFileSystem initialized successfully")
        return self._filesystem
    except Exception as e:
        logger.error(f"Failed to initialize IPFSFileSystem: {e}")
        if return_mock:
            # Return the mock implementation as fallback for backward compatibility
            logger.warning("Falling back to mock filesystem due to initialization error")
            return MockIPFSFileSystem(**kwargs)
        else:
            # Re-raise the exception with context to help with debugging
            raise Exception(f"Failed to initialize IPFSFileSystem: {str(e)}") from e
