"""
Test script for verifying libp2p protocol extensions.

This script creates an IPFSLibp2pPeer instance and verifies that the
GossipSub protocol methods and enhanced DHT discovery methods are available
and working properly.
"""

import anyio
import json
import logging
import sys
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_gossipsub_and_enhanced_discovery():
    """Test GossipSub protocol and enhanced DHT discovery methods."""
    logger.info("Testing libp2p protocol extensions...")

    try:
        from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer
        from ipfs_kit_py.libp2p import apply_protocol_extensions_to_instance

        # Check if libp2p is available
        try:
            import libp2p
            logger.info("libp2p is available")
        except ImportError:
            logger.error("libp2p is not available. Install libp2p-py first.")
            return False

        # Create a peer instance
        peer = IPFSLibp2pPeer(
            role="worker",
            bootstrap_peers=[
                "/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ"
            ],
            enable_mdns=True
        )

        # Verify methods - GossipSub
        has_gossipsub = hasattr(peer, "publish_to_topic") and \
                       hasattr(peer, "subscribe_to_topic") and \
                       hasattr(peer, "unsubscribe_from_topic") and \
                       hasattr(peer, "get_topic_peers") and \
                       hasattr(peer, "list_topics")

        # Verify methods - Enhanced DHT Discovery
        has_enhanced_dht = hasattr(peer, "integrate_enhanced_dht_discovery") and \
                          hasattr(peer, "find_providers_enhanced")

        if has_gossipsub and has_enhanced_dht:
            logger.info("✅ Protocol extensions are already applied to the IPFSLibp2pPeer class")
        else:
            logger.info("Protocol extensions not detected, applying them manually...")

            # Apply the extensions to the instance
            peer = apply_protocol_extensions_to_instance(peer)

            # Re-check for methods
            has_gossipsub = hasattr(peer, "publish_to_topic") and \
                           hasattr(peer, "subscribe_to_topic") and \
                           hasattr(peer, "unsubscribe_from_topic") and \
                           hasattr(peer, "get_topic_peers") and \
                           hasattr(peer, "list_topics")

            has_enhanced_dht = hasattr(peer, "integrate_enhanced_dht_discovery") and \
                              hasattr(peer, "find_providers_enhanced")

            if has_gossipsub and has_enhanced_dht:
                logger.info("✅ Successfully applied protocol extensions")
            else:
                logger.error("❌ Failed to apply protocol extensions")
                return False

        # Test GossipSub functionality
        logger.info("Testing GossipSub functionality...")

        # Subscribe to a test topic
        test_topic = "ipfs-kit-test-topic"

        def message_handler(msg):
            """Handler for incoming messages."""
            logger.info(f"Received message on {test_topic}: {msg}")

        # Subscribe to topic
        subscribe_result = peer.subscribe_to_topic(test_topic, message_handler)
        logger.info(f"Subscribe result: {json.dumps(subscribe_result, indent=2)}")

        # List topics
        topics_result = peer.list_topics()
        logger.info(f"Topics list: {json.dumps(topics_result, indent=2)}")

        # Publish to topic
        # Use ID instead of peer_id
        peer_id = getattr(peer, "id", "unknown-peer")
        test_message = f"Test message from {peer_id} at {time.time()}"
        publish_result = peer.publish_to_topic(test_topic, test_message)
        logger.info(f"Publish result: {json.dumps(publish_result, indent=2)}")

        # Get topic peers
        time.sleep(1)  # Allow time for message propagation
        peers_result = peer.get_topic_peers(test_topic)
        logger.info(f"Topic peers: {json.dumps(peers_result, indent=2)}")

        # Unsubscribe from topic
        unsubscribe_result = peer.unsubscribe_from_topic(test_topic)
        logger.info(f"Unsubscribe result: {json.dumps(unsubscribe_result, indent=2)}")

        # Test enhanced DHT discovery
        logger.info("Testing enhanced DHT discovery functionality...")

        # Integrate enhanced discovery
        integration_result = peer.integrate_enhanced_dht_discovery()
        logger.info(f"Integration result: {json.dumps(integration_result, indent=2)}")

        # Test finding providers for a known CID (example: IPFS README)
        readme_cid = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
        providers_result = peer.find_providers_enhanced(readme_cid, count=5, timeout=30)
        logger.info(f"Providers result: {json.dumps(providers_result, indent=2)}")

        logger.info("All protocol extension tests completed!")
        return True

    except Exception as e:
        logger.error(f"Error testing protocol extensions: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = test_gossipsub_and_enhanced_discovery()
    sys.exit(0 if success else 1)
