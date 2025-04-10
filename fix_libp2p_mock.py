#!/usr/bin/env python3
"""
Fix for libp2p mocking in tests.

This script adds necessary mock targets for proper testing of libp2p functionality
in the test_mcp_communication.py file.
"""

import sys
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_libp2p_mock")

def add_mock_attributes():
    """
    Add mock attributes to the libp2p_peer module for testing.
    """
    try:
        import ipfs_kit_py.libp2p_peer
        
        # Import necessary libraries that need to be mocked
        import libp2p
        
        # Add missing mock targets to the module
        logger.info("Adding mock targets to ipfs_kit_py.libp2p_peer")
        
        # Add new_host for mocking directly to the module
        if not hasattr(ipfs_kit_py.libp2p_peer, 'new_host'):
            ipfs_kit_py.libp2p_peer.new_host = libp2p.new_host
            logger.info("Added new_host mock target")
        
        # Add KademliaServer for mocking
        if not hasattr(ipfs_kit_py.libp2p_peer, 'KademliaServer'):
            from libp2p.kademlia.network import KademliaServer
            ipfs_kit_py.libp2p_peer.KademliaServer = KademliaServer
            logger.info("Added KademliaServer mock target")
            
        # Add pubsub_utils.create_pubsub for mocking
        if not hasattr(ipfs_kit_py.libp2p_peer, 'pubsub_utils'):
            import libp2p.tools.pubsub.utils as pubsub_utils
            ipfs_kit_py.libp2p_peer.pubsub_utils = pubsub_utils
            logger.info("Added pubsub_utils mock target")
        
        return True
    except ImportError as e:
        logger.error(f"Error importing libp2p: {e}")
        logger.info("Creating simulation mode attributes instead")
        return simulate_libp2p_attributes()
    except Exception as e:
        logger.error(f"Error adding mock attributes: {e}")
        return False

def simulate_libp2p_attributes():
    """
    Create simulation mode attributes when libp2p is not available.
    """
    try:
        import ipfs_kit_py.libp2p_peer
        from unittest.mock import MagicMock
        
        # Create mock objects
        mock_new_host = MagicMock()
        mock_kademlia = MagicMock()
        mock_pubsub = MagicMock()
        
        # Add to module
        ipfs_kit_py.libp2p_peer.new_host = mock_new_host
        ipfs_kit_py.libp2p_peer.KademliaServer = mock_kademlia
        ipfs_kit_py.libp2p_peer.pubsub_utils = MagicMock()
        ipfs_kit_py.libp2p_peer.pubsub_utils.create_pubsub = mock_pubsub
        
        logger.info("Added simulation mock attributes to ipfs_kit_py.libp2p_peer")
        return True
    except Exception as e:
        logger.error(f"Error creating simulation attributes: {e}")
        return False

if __name__ == "__main__":
    success = add_mock_attributes()
    if success:
        logger.info("Successfully added mock attributes to libp2p_peer module")
        sys.exit(0)
    else:
        logger.error("Failed to add mock attributes")
        sys.exit(1)