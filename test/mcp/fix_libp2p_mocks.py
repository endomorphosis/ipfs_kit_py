"""
Fix script for libp2p mocks used in MCP tests.

This script provides mock objects and patching for libp2p functionality
to allow tests to run without requiring actual libp2p connections.
"""

import logging
import sys
from unittest.mock import MagicMock, patch

# Configure logger
logger = logging.getLogger(__name__)

def apply_libp2p_mocks():
    """
    Apply mocks to libp2p modules to facilitate testing.
    
    This function patches various libp2p components to return mock objects
    instead of requiring actual network connections.
    """
    logger.info("Applying libp2p mocks for testing")
    
    # Create mock objects
    mock_stream = MagicMock()
    mock_stream.read.return_value = b""
    mock_stream.write.return_value = None
    mock_stream.close.return_value = None
    
    mock_conn = MagicMock()
    mock_conn.get_streams.return_value = []
    mock_conn.new_stream.return_value = mock_stream
    
    mock_host = MagicMock()
    mock_host.get_id.return_value = b"mock_peer_id"
    mock_host.get_addrs.return_value = ["/ip4/127.0.0.1/tcp/1234"]
    mock_host.new_stream.return_value = mock_stream
    mock_host.get_network.return_value.connections.values.return_value = [mock_conn]
    
    mock_dht = MagicMock()
    mock_dht.find_providers.return_value = []
    mock_dht.find_peer.return_value = None
    mock_dht.get_public_key.return_value = None
    
    # Apply patches
    modules_to_patch = [
        "libp2p.host.host_interface.IHost",
        "libp2p.peer.id.ID",
        "libp2p.network.stream.net_stream_interface.INetStream",
        "libp2p.kademlia.kad_dht.KadDHT",
    ]
    
    patches = {}
    for module_path in modules_to_patch:
        try:
            patcher = patch(module_path)
            mock_obj = patcher.start()
            patches[module_path] = patcher
            logger.debug(f"Successfully patched {module_path}")
        except Exception as e:
            logger.warning(f"Failed to patch {module_path}: {e}")
    
    # Patch specific MCP imports
    try:
        # Patch EnhancedContentRouter import
        enhanced_cr_patcher = patch("ipfs_kit_py.libp2p.enhanced_content_routing.EnhancedContentRouter")
        mock_ecr = enhanced_cr_patcher.start()
        mock_ecr.return_value = MagicMock()
        patches["enhanced_content_router"] = enhanced_cr_patcher
        logger.debug("Successfully patched EnhancedContentRouter")
    except Exception as e:
        logger.warning(f"Failed to patch EnhancedContentRouter: {e}")
    
    return patches

def cleanup_libp2p_mocks(patches):
    """
    Clean up applied patches.
    
    Args:
        patches: Dictionary of applied patchers to be stopped
    """
    logger.info("Cleaning up libp2p mocks")
    
    for module_path, patcher in patches.items():
        try:
            patcher.stop()
            logger.debug(f"Successfully stopped patch for {module_path}")
        except Exception as e:
            logger.warning(f"Error stopping patch for {module_path}: {e}")

if __name__ == "__main__":
    # Configure logging to stdout
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )
    
    logger.info("Running libp2p mocks fix script")
    patches = apply_libp2p_mocks()
    logger.info(f"Applied {len(patches)} patches to libp2p modules")