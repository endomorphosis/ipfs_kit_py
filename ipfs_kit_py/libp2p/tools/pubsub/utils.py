"""
PubSub utilities for libp2p compatibility.

This module provides pubsub utilities that may be missing from the current libp2p version.
"""

import logging

logger = logging.getLogger(__name__)

def create_pubsub(host, router_type="gossipsub"):
    """Create a pubsub instance with the given router type."""
    try:
        if router_type == "gossipsub":
            from libp2p.pubsub.gossipsub import GossipSub
            return GossipSub(host_id=host.get_id(), router=None)
        elif router_type == "floodsub":
            from libp2p.pubsub.floodsub import FloodSub
            return FloodSub(host_id=host.get_id())
        else:
            logger.warning(f"Unknown router type: {router_type}, falling back to floodsub")
            from libp2p.pubsub.floodsub import FloodSub
            return FloodSub(host_id=host.get_id())
    except Exception as e:
        logger.error(f"Failed to create pubsub: {e}")
        return None

logger.debug("libp2p tools.pubsub.utils module loaded")
