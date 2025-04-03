"""
Utility module to provide a fixed implementation of the get_filesystem method.

This module contains an implementation of the get_filesystem method that can be
used in the ipfs_kit class to provide access to the FSSpec filesystem interface.
"""

# Flag to track if FSSpec is available
FSSPEC_AVAILABLE = False
try:
    import fsspec

    FSSPEC_AVAILABLE = True
except ImportError:
    FSSPEC_AVAILABLE = False


def get_filesystem(self, **kwargs):
    """
    Get an FSSpec-compatible filesystem for IPFS.

    Args:
        gateway_urls: List of IPFS gateway URLs to use
        use_gateway_fallback: Whether to use gateways as fallback when local daemon is unavailable
        gateway_only: Whether to use only gateways (no local daemon)
        cache_config: Configuration for the cache system
        enable_metrics: Whether to enable performance metrics

    Returns:
        FSSpec-compatible filesystem interface for IPFS
    """
    if not FSSPEC_AVAILABLE:
        raise ImportError("fsspec is not available. Please install fsspec to use this feature.")

    # Initialize the filesystem on first access
    if not hasattr(self, "_filesystem") or self._filesystem is None:
        from .ipfs_fsspec import IPFSFileSystem

        # Prepare configuration
        fs_kwargs = {}

        # Add gateway configuration if provided
        if "gateway_urls" in kwargs:
            fs_kwargs["gateway_urls"] = kwargs["gateway_urls"]

        # Add gateway fallback configuration if provided
        if "use_gateway_fallback" in kwargs:
            fs_kwargs["use_gateway_fallback"] = kwargs["use_gateway_fallback"]

        # Add gateway-only mode configuration if provided
        if "gateway_only" in kwargs:
            fs_kwargs["gateway_only"] = kwargs["gateway_only"]

        # Add cache configuration if provided
        if "cache_config" in kwargs:
            fs_kwargs["cache_config"] = kwargs["cache_config"]

        # Add metrics configuration if provided
        if "enable_metrics" in kwargs:
            fs_kwargs["enable_metrics"] = kwargs["enable_metrics"]

        # Create the filesystem
        self._filesystem = IPFSFileSystem(**fs_kwargs)

    return self._filesystem
