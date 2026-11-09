"""
IPFS Kit LibP2P Integration

This module implements the integration between IPFSKit and the enhanced
libp2p discovery mechanism, allowing direct P2P content retrieval when
content is not found in the local cache or IPFS daemon.

The integration uses dependency injection to avoid circular imports, where the
IPFSKit class is passed as a parameter rather than being imported directly.
This allows the libp2p functionality to be seamlessly integrated without
creating import cycles.
"""

import logging
import time
import importlib.util
from typing import Any, Dict, Optional, Union, Type, Callable

# Import the libp2p dependency flag
from . import HAS_LIBP2P

# Configure logger
logger = logging.getLogger(__name__)


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
    if hasattr(ipfs_kit_cls, 'get_filesystem'):
        original_get_filesystem = ipfs_kit_cls.get_filesystem
    else:
        # Create a basic implementation if it doesn't exist
        logger = logging.getLogger(__name__)
        logger.warning("get_filesystem method not found, creating a basic implementation")

        def original_get_filesystem(self, **kwargs):
            """Basic implementation of get_filesystem."""
            return None

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
                # Use safer import with better error handling
                try:
                    # Try direct import first
                    from ..libp2p_peer import IPFSLibp2pPeer, HAS_LIBP2P as PEER_HAS_LIBP2P
                    
                    if not PEER_HAS_LIBP2P:
                        logger = getattr(self, "logger", logging.getLogger(__name__))
                        logger.warning("Cannot create libp2p peer: dependencies not available")
                        return fs
                        
                    self.libp2p_peer = IPFSLibp2pPeer(role=getattr(self, "role", "leecher"))
                    logger = getattr(self, "logger", logging.getLogger(__name__))
                    logger.debug(f"Created libp2p peer with role {getattr(self, 'role', 'leecher')}")
                    
                except ImportError:
                    # If direct import fails, try importlib for more controlled import
                    logger = getattr(self, "logger", logging.getLogger(__name__))
                    logger.debug("Direct import failed, trying importlib")
                    
                    spec = importlib.util.find_spec("ipfs_kit_py.libp2p_peer")
                    if spec is None:
                        logger.warning("libp2p_peer module not found")
                        return fs
                        
                    libp2p_peer_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(libp2p_peer_module)
                    
                    if not getattr(libp2p_peer_module, "HAS_LIBP2P", False):
                        logger.warning("Cannot create libp2p peer: dependencies not available")
                        return fs
                        
                    IPFSLibp2pPeer = getattr(libp2p_peer_module, "IPFSLibp2pPeer")
                    self.libp2p_peer = IPFSLibp2pPeer(role=getattr(self, "role", "leecher"))
                    logger.debug(f"Created libp2p peer with role {getattr(self, 'role', 'leecher')} using importlib")
                    
            except Exception as e:
                logger = getattr(self, "logger", logging.getLogger(__name__))
                logger.warning(f"Failed to create libp2p peer: {str(e)}")
                return fs

        # Register the libp2p peer with this IPFSKit instance
        try:
            # Get the register_libp2p_with_ipfs_kit function
            # We avoid direct imports to prevent circular dependencies
            from . import register_libp2p_with_ipfs_kit as register_func
            
            # Register the peer with the kit
            result = register_func(self, self.libp2p_peer, extend_cache=True)
            
            logger = getattr(self, "logger", logging.getLogger(__name__))
            if result:
                logger.info("Successfully registered libp2p integration with IPFSKit")
            else:
                logger.warning("Registration function returned None or False")

        except Exception as e:
            logger = getattr(self, "logger", logging.getLogger(__name__))
            logger.error(f"Failed to register libp2p integration: {str(e)}", exc_info=True)

        return fs

    # Replace the get_filesystem method
    ipfs_kit_cls.get_filesystem = enhanced_get_filesystem

    return ipfs_kit_cls


def apply_ipfs_kit_integration(ipfs_kit_class=None):
    """Apply the IPFSKit integration using dependency injection.

    This function extends the provided IPFSKit class with libp2p integration.
    Instead of importing the class (which causes circular imports), it accepts
    the class as a parameter. This allows for a clean separation of concerns
    and avoids circular dependencies between modules.

    Args:
        ipfs_kit_class: The IPFSKit class to extend. If None, no integration is performed.

    Returns:
        Type: The extended IPFSKit class if successful, original class otherwise
        
    Example:
        from ipfs_kit_py.ipfs_kit import IPFSKit
        from ipfs_kit_py.libp2p import apply_ipfs_kit_integration
        
        # Extend the class
        enhanced_kit_class = apply_ipfs_kit_integration(IPFSKit)
    """
    logger = logging.getLogger(__name__)
    
    # Check if libp2p is available
    if not HAS_LIBP2P:
        logger.warning("Cannot apply IPFSKit integration: libp2p is not available")
        return ipfs_kit_class

    try:
        # If no class is provided, we can't do the integration
        if ipfs_kit_class is None:
            logger.info("No IPFSKit class provided, returning None")
            return None
            
        # Validate that we have a class and not an instance
        if not isinstance(ipfs_kit_class, type):
            logger.warning(f"Expected a class but got {type(ipfs_kit_class).__name__} instance, returning as is")
            return ipfs_kit_class

        # Check if get_filesystem method exists before extending
        if not hasattr(ipfs_kit_class, "get_filesystem"):
            logger.warning("IPFSKit class does not have get_filesystem method, adding a basic implementation")

            # Add a basic implementation of get_filesystem
            def basic_get_filesystem(self, **kwargs):
                """Basic implementation of get_filesystem for testing.
                
                This is a fallback implementation when the original class
                doesn't have a get_filesystem method.
                
                Returns:
                    None: This implementation always returns None
                """
                logger = getattr(self, "logger", logging.getLogger(__name__))
                logger.info("Using basic get_filesystem implementation")
                return None

            ipfs_kit_class.get_filesystem = basic_get_filesystem
            logger.debug("Added basic get_filesystem implementation")

        # Check if the class is already extended
        if hasattr(ipfs_kit_class, "_libp2p_integrated") and ipfs_kit_class._libp2p_integrated:
            logger.info(f"Class {ipfs_kit_class.__name__} is already extended with libp2p integration")
            return ipfs_kit_class

        # Extend the class
        extended_class = extend_ipfs_kit_class(ipfs_kit_class)
        
        # Mark the class as extended
        setattr(extended_class, "_libp2p_integrated", True)
        
        logger.info(f"Successfully applied libp2p integration to {extended_class.__name__}")
        return extended_class

    except Exception as e:
        logger.error(f"Failed to apply IPFSKit integration: {str(e)}", exc_info=True)
        # Return the original class if integration fails
        return ipfs_kit_class
