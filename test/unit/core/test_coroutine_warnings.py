#!/usr/bin/env python3
"""
Test script to verify our fixes for coroutine warnings in the libp2p implementations.
This script specifically tests the async/sync method compatibility between controller and model.
"""

import anyio
import logging
import sys
import warnings

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

# Set up warning capture
def capture_warnings():
    captured_warnings = []

    def custom_showwarning(message, category, filename, lineno, file=None, line=None):
        captured_warnings.append((message, category, filename, lineno))
        # Also print to stderr for visibility
        print(f"WARNING: {message}", file=sys.stderr)

    original_showwarning = warnings.showwarning
    warnings.showwarning = custom_showwarning

    return captured_warnings, original_showwarning

async def test_libp2p_controller_model_compatibility():
    """Test that controller and model async methods work together properly."""
    from ipfs_kit_py.mcp.controllers.libp2p_controller import LibP2PController
    from ipfs_kit_py.mcp.models.libp2p_model import LibP2PModel
    from fastapi import Request
    from ipfs_kit_py.mcp.controllers.libp2p_controller import (
        PeerDiscoveryRequest, PeerConnectionRequest, PeerDisconnectRequest,
        PubSubPublishRequest, DHTFindPeerRequest, DHTProvideRequest, DHTFindProvidersRequest
    )

    logger.info("Initializing LibP2PModel...")
    model = LibP2PModel()

    logger.info("Initializing LibP2PController with model...")
    controller = LibP2PController(model)

    # Capture warnings during test execution
    captured_warnings, original_showwarning = capture_warnings()

    try:
        logger.info("Testing controller.health_check() method...")
        health_result = await controller.health_check()
        logger.info(f"health_check result: {health_result}")

        # Create request objects for post methods
        logger.info("Testing controller.discover_peers() method...")
        discover_request = PeerDiscoveryRequest(discovery_method="mDNS", limit=5)
        discover_result = await controller.discover_peers(discover_request)
        logger.info(f"discover_peers result: {discover_result}")

        logger.info("Testing controller.get_peers() method...")
        get_peers_result = await controller.get_peers(method="all", limit=10)
        logger.info(f"get_peers result: {get_peers_result}")

        logger.info("Testing controller.connect_peer() method...")
        connect_request = PeerConnectionRequest(peer_addr="/ip4/127.0.0.1/tcp/4001/p2p/QmPeerID")
        connect_result = await controller.connect_peer(connect_request)
        logger.info(f"connect_peer result: {connect_result}")

        logger.info("Testing controller.disconnect_peer() method...")
        disconnect_request = PeerDisconnectRequest(peer_id="QmPeerID")
        disconnect_result = await controller.disconnect_peer(disconnect_request)
        logger.info(f"disconnect_peer result: {disconnect_result}")

        logger.info("Testing controller.get_peer_info_endpoint() method...")
        peer_info_result = await controller.get_peer_info_endpoint()
        logger.info(f"get_peer_info_endpoint result: {peer_info_result}")

        logger.info("Testing controller.publish_message() method...")
        publish_request = PubSubPublishRequest(topic="test-topic", message="Hello libp2p!")
        publish_result = await controller.publish_message(publish_request)
        logger.info(f"publish_message result: {publish_result}")

        logger.info("Testing controller.dht_find_peer() method...")
        dht_find_peer_request = DHTFindPeerRequest(peer_id="QmPeerID", timeout=30)
        dht_find_peer_result = await controller.dht_find_peer(dht_find_peer_request)
        logger.info(f"dht_find_peer result: {dht_find_peer_result}")

        logger.info("Testing controller.dht_provide() method...")
        dht_provide_request = DHTProvideRequest(cid="QmTestCID")
        dht_provide_result = await controller.dht_provide(dht_provide_request)
        logger.info(f"dht_provide result: {dht_provide_result}")

        logger.info("Testing controller.dht_find_providers() method...")
        dht_find_providers_request = DHTFindProvidersRequest(cid="QmTestCID", timeout=30, limit=20)
        dht_find_providers_result = await controller.dht_find_providers(dht_find_providers_request)
        logger.info(f"dht_find_providers result: {dht_find_providers_result}")

        # Check if we got any coroutine warnings
        coroutine_warnings = [w for w in captured_warnings
                             if isinstance(w[0], Warning) and "coroutine" in str(w[0])]

        if coroutine_warnings:
            logger.error(f"Found {len(coroutine_warnings)} coroutine warnings:")
            for w in coroutine_warnings:
                logger.error(f"  - {w[0]} (in {w[2]}:{w[3]})")
            return False
        else:
            logger.info("No coroutine warnings detected! Fix is working correctly.")
            return True

    finally:
        # Restore original warning behavior
        warnings.showwarning = original_showwarning

async def main():
    logger.info("Starting libp2p controller/model async method tests...")
    success = await test_libp2p_controller_model_compatibility()

    if success:
        logger.info("All tests passed successfully!")
        return 0
    else:
        logger.error("Tests failed - coroutine warnings detected!")
        return 1

if __name__ == "__main__":
    exit_code = anyio.run(main())
    sys.exit(exit_code)
