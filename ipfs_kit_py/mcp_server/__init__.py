"""
Compatibility module for IPFS backend implementations.

This module provides compatibility for code that might be importing from
the old paths prior to the server architecture consolidation.
"""

import sys
import logging
import warnings

logger = logging.getLogger(__name__)

# Emit a deprecation warning
warnings.warn(
    "You are importing from the deprecated ipfs_kit_py.mcp_server path. "
    "Please update your imports to use ipfs_kit_py.mcp.storage_manager.backends instead.",
    DeprecationWarning, 
    stacklevel=2
)

# Import from the new location
try:
    from ipfs_kit_py.mcp.storage_manager.backends.ipfs_backend import IPFSBackend
    from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType
    
    # Re-export the classes
    __all__ = ['IPFSBackend', 'StorageBackendType']
    
    logger.info("Successfully redirected import to the new consolidated structure")
except ImportError as e:
    logger.error(f"Failed to import from new structure: {e}")
    raise ImportError(
        "The MCP server structure has been consolidated. The 'mcp_server' directory "
        "has been removed, and all code has been moved to 'ipfs_kit_py.mcp'. "
        "Please update your imports accordingly."
    ) from e