"""
IPFS Kit LibP2P Integration

This module implements the integration between IPFSKit and the enhanced
libp2p discovery mechanism, allowing direct P2P content retrieval when
content is not found in the local cache or IPFS daemon.
"""

import logging
import time
from typing import Any, Dict, Optional

# Import local modules
from .p2p_integration import register_libp2p_with_ipfs_kit


def extend_ipfs_kit_class(ipfs_kit_cls):
    """Extend the IPFSKit class with libp2p miss handler functionality.

    This function adds the _handle_content_miss_with_libp2p method to the
    IPFSKit class, which is called by the cache manager when content is
    not found in any cache tier.

    Args:
        ipfs_kit_cls: The IPFSKit class to extend
    """
    # Make sure the class doesn't already have the method
    if hasattr(ipfs_kit_cls, "_handle_content_miss_with_libp2p"):
        return

    def _handle_content_miss_with_libp2p(self, cid):
        """Handle content cache miss by attempting to retrieve directly from peers.

        This method is called by the cache manager when content is not found in
        local cache or from the IPFS daemon. It attempts to retrieve the content
        directly from peers using libp2p connections.

        Args:
            cid: Content identifier to retrieve

        Returns:
            Content bytes if found, None otherwise
        """
        logger = getattr(self, "logger", logging.getLogger(__name__))
        logger.debug(f"Attempting to retrieve content {cid} directly via libp2p")

        # Check if we have libp2p integration
        if not hasattr(self, "libp2p_integration"):
            logger.debug("LibP2P integration not available")
            return None

        start_time = time.time()
        content = self.libp2p_integration.handle_cache_miss(cid)

        if content:
            elapsed = time.time() - start_time
            logger.info(f"Successfully retrieved {cid} via libp2p in {elapsed:.2f}s")
            return content
        else:
            logger.debug(f"Failed to retrieve {cid} via libp2p")
            return None

    # Add the method to the class
    ipfs_kit_cls._handle_content_miss_with_libp2p = _handle_content_miss_with_libp2p

    # Modify the get_filesystem method to include libp2p integration
    original_get_filesystem = ipfs_kit_cls.get_filesystem

    def enhanced_get_filesystem(
        self,
        socket_path=None,
        cache_config=None,
        use_mmap=True,
        enable_metrics=True,
        gateway_urls=None,
        gateway_only=False,
        use_gateway_fallback=False,
        use_libp2p=True,
    ):
        """Create a filesystem interface for IPFS using FSSpec with libp2p integration.

        This extends the original get_filesystem method to include libp2p integration
        for enhanced content routing and direct peer-to-peer content retrieval.

        Args:
            socket_path: Path to Unix socket for high-performance communication
            cache_config: Configuration for the tiered cache system
            use_mmap: Whether to use memory-mapped files for large content
            enable_metrics: Whether to collect performance metrics
            gateway_urls: List of IPFS gateway URLs to use (e.g. ["https://ipfs.io/ipfs/"])
            gateway_only: If True, only use gateways (ignore local daemon)
            use_gateway_fallback: If True, try gateways if local daemon fails
            use_libp2p: Whether to enable libp2p integration for content retrieval

        Returns:
            An IPFSFileSystem instance that implements the fsspec interface,
            or None if fsspec is not available
        """
        # Call the original method to create the filesystem
        fs = original_get_filesystem(
            self,
            socket_path,
            cache_config,
            use_mmap,
            enable_metrics,
            gateway_urls,
            gateway_only,
            use_gateway_fallback,
        )

        # If filesystem creation failed or libp2p integration not requested, return as is
        if not fs or not use_libp2p:
            return fs

        # Check if we have a libp2p peer
        if not hasattr(self, "libp2p_peer"):
            # Try to create a libp2p peer if not already available
            try:
                from ..libp2p_peer import IPFSLibp2pPeer

                self.libp2p_peer = IPFSLibp2pPeer(role=getattr(self, "role", "leecher"))
            except (ImportError, Exception) as e:
                logger = getattr(self, "logger", logging.getLogger(__name__))
                logger.warning(f"Failed to create libp2p peer: {e}")
                return fs

        # Register the libp2p peer with this IPFSKit instance
        try:
            # Import register function here to avoid circular imports
            from .p2p_integration import register_libp2p_with_ipfs_kit

            register_libp2p_with_ipfs_kit(self, self.libp2p_peer, extend_cache=True)

            logger = getattr(self, "logger", logging.getLogger(__name__))
            logger.info("Registered libp2p integration with IPFSKit")

        except Exception as e:
            logger = getattr(self, "logger", logging.getLogger(__name__))
            logger.error(f"Failed to register libp2p integration: {e}")

        return fs

    # Replace the get_filesystem method
    ipfs_kit_cls.get_filesystem = enhanced_get_filesystem

    return ipfs_kit_cls


def apply_ipfs_kit_integration():
    """Apply the IPFSKit integration to the ipfs_kit module.

    This function:
    1. Imports the ipfs_kit module
    2. Extends the IPFSKit class with libp2p integration
    3. Returns True if successful, False otherwise
    """
    try:
        # Import the ipfs_kit module
        import sys
        from importlib import import_module

        # Try different import paths
        module_paths = [
            "ipfs_kit_py.ipfs_kit",  # Standard import path
            "ipfs_kit",  # Alternative path
        ]

        ipfs_kit_module = None
        for path in module_paths:
            try:
                ipfs_kit_module = import_module(path)
                break
            except ImportError:
                continue

        if not ipfs_kit_module:
            raise ImportError("Could not import ipfs_kit module")

        # Find the IPFSKit class
        ipfs_kit_class = None
        for attr_name in dir(ipfs_kit_module):
            if attr_name.lower() in ("ipfs_kit", "ipfskit"):
                ipfs_kit_class = getattr(ipfs_kit_module, attr_name)
                break

        if not ipfs_kit_class:
            raise ValueError("Could not find IPFSKit class in module")

        # Extend the class
        extend_ipfs_kit_class(ipfs_kit_class)

        return True

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to apply IPFSKit integration: {e}")
        return False
