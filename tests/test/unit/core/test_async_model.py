#!/usr/bin/env python3
"""
Simple test script to verify our fixes for coroutine warnings in the libp2p model.
This script specifically tests the async versions of model methods.
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

async def test_libp2p_model_async_methods():
    """Test that the async methods in the libp2p model work correctly."""
    from ipfs_kit_py.mcp.models.libp2p_model import LibP2PModel
    
    logger.info("Initializing LibP2PModel...")
    model = LibP2PModel()
    
    # Capture warnings during test execution
    captured_warnings, original_showwarning = capture_warnings()
    
    try:
        logger.info("Testing is_available() async method...")
        is_available = await model.is_available()
        logger.info(f"is_available result: {is_available}")
        
        logger.info("Testing get_health() async method...")
        health_result = await model.get_health()
        logger.info(f"get_health result: {health_result}")
        
        logger.info("Testing discover_peers() async method...")
        discover_result = await model.discover_peers(discovery_method="mDNS", limit=5)
        logger.info(f"discover_peers result: {discover_result}")
        
        logger.info("Testing peer_info() async method...")
        peer_info_result = await model.peer_info()
        logger.info(f"peer_info result: {peer_info_result}")
        
        logger.info("Testing connect_peer() async method...")
        connect_result = await model.connect_peer("/ip4/127.0.0.1/tcp/4001/p2p/QmPeerID")
        logger.info(f"connect_peer result: {connect_result}")
        
        logger.info("Testing disconnect_peer() async method...")
        disconnect_result = await model.disconnect_peer(peer_id="QmPeerID")
        logger.info(f"disconnect_peer result: {disconnect_result}")
        
        logger.info("Testing publish_message() async method...")
        publish_result = await model.publish_message(topic="test-topic", message="Hello libp2p!")
        logger.info(f"publish_message result: {publish_result}")
        
        logger.info("Testing dht_find_peer() async method...")
        dht_find_peer_result = await model.dht_find_peer(peer_id="QmPeerID", timeout=30)
        logger.info(f"dht_find_peer result: {dht_find_peer_result}")
        
        logger.info("Testing dht_provide() async method...")
        dht_provide_result = await model.dht_provide(cid="QmTestCID")
        logger.info(f"dht_provide result: {dht_provide_result}")
        
        logger.info("Testing dht_find_providers() async method...")
        dht_find_providers_result = await model.dht_find_providers(cid="QmTestCID", timeout=30, limit=20)
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
    logger.info("Starting libp2p model async method tests...")
    success = await test_libp2p_model_async_methods()
    
    if success:
        logger.info("All tests passed successfully!")
        return 0
    else:
        logger.error("Tests failed - coroutine warnings detected!")
        return 1

if __name__ == "__main__":
    exit_code = anyio.run(main())
    sys.exit(exit_code)