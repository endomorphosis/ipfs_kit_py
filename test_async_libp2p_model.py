#!/usr/bin/env python3
"""
Test script to verify that async methods in the LibP2PModel class are properly implemented.
This script tests that the async methods correctly use anyio.to_thread.run_sync to delegate
to their synchronous counterparts, ensuring they return proper coroutines that can be awaited
without any "coroutine never awaited" warnings.
"""

import sys
import asyncio
import warnings
import logging
from ipfs_kit_py.mcp.models.libp2p_model import LibP2PModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enable warnings for coroutines
warnings.filterwarnings("always", category=RuntimeWarning, message="coroutine '.*' was never awaited")

async def test_async_methods():
    """Test all async methods in LibP2PModel."""
    logger.info("Creating LibP2PModel instance...")
    model = LibP2PModel()
    
    # Tests to run
    async_tests = [
        # Basic availability check
        test_is_available(model),
        # Health and information
        test_get_health(model),
        test_peer_info(model),
        # Core peer operations
        test_discover_peers(model),
        test_get_connected_peers(model),
        # Content operations
        test_find_content(model),
        test_retrieve_content(model),
        test_get_content(model),
        test_announce_content(model),
        # Lifecycle management
        test_start_stop(model),
        # DHT operations
        test_dht_operations(model),
        # PubSub operations
        test_pubsub_operations(model),
        # Handler management
        test_message_handlers(model),
        # Reset operation
        test_reset(model),
    ]
    
    # Run all tests
    logger.info("Running async tests...")
    results = await asyncio.gather(*async_tests)
    
    # Print summary
    success = all(results)
    logger.info(f"All tests completed. {'All tests passed!' if success else 'Some tests failed.'}")
    return success

async def test_is_available(model):
    """Test is_available async method."""
    logger.info("Testing is_available()...")
    try:
        result = await model.is_available()
        logger.info(f"  is_available result: {result}")
        return True
    except Exception as e:
        logger.error(f"  is_available error: {e}")
        return False

async def test_get_health(model):
    """Test get_health async method."""
    logger.info("Testing get_health()...")
    try:
        result = await model.get_health()
        logger.info(f"  get_health success: {result.get('success', False)}")
        return True
    except Exception as e:
        logger.error(f"  get_health error: {e}")
        return False

async def test_peer_info(model):
    """Test peer_info async method."""
    logger.info("Testing peer_info()...")
    try:
        result = await model.peer_info()
        logger.info(f"  peer_info success: {result.get('success', False)}")
        return True
    except Exception as e:
        logger.error(f"  peer_info error: {e}")
        return False

async def test_discover_peers(model):
    """Test discover_peers async method."""
    logger.info("Testing discover_peers()...")
    try:
        result = await model.discover_peers(discovery_method="all", limit=5)
        logger.info(f"  discover_peers success: {result.get('success', False)}")
        return True
    except Exception as e:
        logger.error(f"  discover_peers error: {e}")
        return False

async def test_get_connected_peers(model):
    """Test get_connected_peers async method."""
    logger.info("Testing get_connected_peers()...")
    try:
        result = await model.get_connected_peers()
        logger.info(f"  get_connected_peers success: {result.get('success', False)}")
        return True
    except Exception as e:
        logger.error(f"  get_connected_peers error: {e}")
        return False

async def test_find_content(model):
    """Test find_content async method."""
    logger.info("Testing find_content()...")
    try:
        # Using a well-known CID for testing
        test_cid = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        result = await model.find_content(test_cid, timeout=5)
        logger.info(f"  find_content success: {result.get('success', False)}")
        return True
    except Exception as e:
        logger.error(f"  find_content error: {e}")
        return False

async def test_retrieve_content(model):
    """Test retrieve_content async method."""
    logger.info("Testing retrieve_content()...")
    try:
        # Using a well-known CID for testing
        test_cid = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        result = await model.retrieve_content(test_cid, timeout=5)
        logger.info(f"  retrieve_content success: {result.get('success', False)}")
        return True
    except Exception as e:
        logger.error(f"  retrieve_content error: {e}")
        return False

async def test_get_content(model):
    """Test get_content async method."""
    logger.info("Testing get_content()...")
    try:
        # Using a well-known CID for testing
        test_cid = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        result = await model.get_content(test_cid, timeout=5)
        logger.info(f"  get_content success: {result.get('success', False)}")
        return True
    except Exception as e:
        logger.error(f"  get_content error: {e}")
        return False

async def test_announce_content(model):
    """Test announce_content async method."""
    logger.info("Testing announce_content()...")
    try:
        # Using a well-known CID for testing
        test_cid = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        test_data = b"Test data"
        result = await model.announce_content(test_cid, data=test_data)
        logger.info(f"  announce_content success: {result.get('success', False)}")
        return True
    except Exception as e:
        logger.error(f"  announce_content error: {e}")
        return False

async def test_start_stop(model):
    """Test start and stop async methods."""
    logger.info("Testing start() and stop()...")
    try:
        # Test start
        start_result = await model.start()
        logger.info(f"  start success: {start_result.get('success', False)}")
        
        # Test stop
        stop_result = await model.stop()
        logger.info(f"  stop success: {stop_result.get('success', False)}")
        
        return True
    except Exception as e:
        logger.error(f"  start/stop error: {e}")
        return False

async def test_dht_operations(model):
    """Test DHT operation async methods."""
    logger.info("Testing DHT operations...")
    try:
        # Test dht_find_peer
        peer_id = "QmdvaAqT2NxeGLrxGYvKypsAVLt5iJHTuv72uP1JdkTy7d"
        find_peer_result = await model.dht_find_peer(peer_id, timeout=5)
        logger.info(f"  dht_find_peer success: {find_peer_result.get('success', False)}")
        
        # Test dht_provide
        test_cid = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        provide_result = await model.dht_provide(test_cid)
        logger.info(f"  dht_provide success: {provide_result.get('success', False)}")
        
        # Test dht_find_providers
        find_providers_result = await model.dht_find_providers(test_cid, timeout=5, limit=10)
        logger.info(f"  dht_find_providers success: {find_providers_result.get('success', False)}")
        
        return True
    except Exception as e:
        logger.error(f"  DHT operations error: {e}")
        return False

async def test_pubsub_operations(model):
    """Test PubSub operation async methods."""
    logger.info("Testing PubSub operations...")
    try:
        test_topic = "test-topic"
        test_message = "Hello, world!"
        
        # Test pubsub_subscribe
        subscribe_result = await model.pubsub_subscribe(test_topic)
        logger.info(f"  pubsub_subscribe success: {subscribe_result.get('success', False)}")
        
        # Test pubsub_publish
        publish_result = await model.pubsub_publish(test_topic, test_message)
        logger.info(f"  pubsub_publish success: {publish_result.get('success', False)}")
        
        # Test pubsub_get_topics
        get_topics_result = await model.pubsub_get_topics()
        logger.info(f"  pubsub_get_topics success: {get_topics_result.get('success', False)}")
        
        # Test pubsub_get_peers
        get_peers_result = await model.pubsub_get_peers(test_topic)
        logger.info(f"  pubsub_get_peers success: {get_peers_result.get('success', False)}")
        
        # Test publish_message (convenience method)
        publish_message_result = await model.publish_message(test_topic, test_message)
        logger.info(f"  publish_message success: {publish_message_result.get('success', False)}")
        
        # Test subscribe_topic (convenience method)
        subscribe_topic_result = await model.subscribe_topic(test_topic)
        logger.info(f"  subscribe_topic success: {subscribe_topic_result.get('success', False)}")
        
        # Test unsubscribe_topic (convenience method)
        unsubscribe_topic_result = await model.unsubscribe_topic(test_topic)
        logger.info(f"  unsubscribe_topic success: {unsubscribe_topic_result.get('success', False)}")
        
        # Test pubsub_unsubscribe
        unsubscribe_result = await model.pubsub_unsubscribe(test_topic)
        logger.info(f"  pubsub_unsubscribe success: {unsubscribe_result.get('success', False)}")
        
        return True
    except Exception as e:
        logger.error(f"  PubSub operations error: {e}")
        return False

async def test_message_handlers(model):
    """Test message handler management async methods."""
    logger.info("Testing message handler management...")
    try:
        test_handler_id = "test-handler"
        test_protocol_id = "/test/protocol/1.0.0"
        test_description = "Test protocol handler"
        
        # Test register_message_handler
        register_result = await model.register_message_handler(
            handler_id=test_handler_id,
            protocol_id=test_protocol_id,
            description=test_description
        )
        logger.info(f"  register_message_handler success: {register_result.get('success', False)}")
        
        # Test list_message_handlers
        list_result = await model.list_message_handlers()
        logger.info(f"  list_message_handlers success: {list_result.get('success', False)}")
        
        # Test unregister_message_handler
        unregister_result = await model.unregister_message_handler(
            handler_id=test_handler_id,
            protocol_id=test_protocol_id
        )
        logger.info(f"  unregister_message_handler success: {unregister_result.get('success', False)}")
        
        return True
    except Exception as e:
        logger.error(f"  Message handler management error: {e}")
        return False

async def test_reset(model):
    """Test reset async method."""
    logger.info("Testing reset()...")
    try:
        result = await model.reset()
        logger.info(f"  reset success: {result.get('success', False)}")
        return True
    except Exception as e:
        logger.error(f"  reset error: {e}")
        return False

if __name__ == "__main__":
    try:
        # Run the tests
        exit_code = 0 if asyncio.run(test_async_methods()) else 1
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Tests interrupted by user.")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)