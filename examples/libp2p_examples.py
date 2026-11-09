#!/usr/bin/env python3
"""
Examples of using the implemented libp2p modules.

This script demonstrates how to use the custom libp2p modules
developed for the ipfs_kit_py project.
"""

import anyio
import logging
import sys
import time
import json
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("libp2p_examples")

# Import our custom modules
try:
    from ipfs_kit_py.libp2p.network.stream.net_stream_interface import (
        INetStream, NetStream, StreamError, StreamHandler
    )
    from ipfs_kit_py.libp2p.tools.pubsub.utils import (
        Topic, Message, PubSubManager
    )
    from ipfs_kit_py.libp2p.kademlia import (
        KademliaRoutingTable, KademliaNode, DHTDatastore,
        K_VALUE, ALPHA_VALUE
    )
    from ipfs_kit_py.libp2p.tools.constants import (
        PROTOCOL_KAD_DHT, PROTOCOL_BITSWAP
    )
    MODULES_AVAILABLE = True
except ImportError as e:
    logger.error(f"Error importing modules: {e}")
    MODULES_AVAILABLE = False

async def demo_pubsub():
    """Demonstrate PubSub functionality."""
    logger.info("==== PubSub Demo ====")
    
    # Create a PubSub manager
    pubsub = PubSubManager("test-peer-id")
    
    # Define a message handler
    async def message_handler(message):
        logger.info(f"Received message: {message.data.decode('utf-8')}")
    
    # Subscribe to a topic
    topic = await pubsub.subscribe("test-topic")
    
    # Register handler with the topic
    await topic.subscribe(message_handler)
    
    # Publish messages
    for i in range(3):
        message = f"Test message {i}"
        logger.info(f"Publishing: {message}")
        await pubsub.publish("test-topic", message)
        
        # Wait a bit to let the message be processed
        await anyio.sleep(0.1)
    
    # Unsubscribe
    await pubsub.unsubscribe("test-topic")
    logger.info("Unsubscribed from topic")
    
    # Try publishing after unsubscribe (should not be received)
    await pubsub.publish("test-topic", "This should not be received")
    
    logger.info("PubSub demo completed")

async def demo_kademlia():
    """Demonstrate Kademlia DHT functionality."""
    logger.info("==== Kademlia DHT Demo ====")
    
    # Create a Kademlia node
    node = KademliaNode("test-peer-id")
    
    # Start the node
    await node.start()
    
    # Add some peers
    for i in range(5):
        peer_id = f"peer-{i}"
        peer_info = {
            "addrs": [f"/ip4/127.0.0.1/tcp/400{i}"],
            "protocols": [PROTOCOL_KAD_DHT, PROTOCOL_BITSWAP]
        }
        node.add_peer(peer_id, peer_info)
        logger.info(f"Added peer: {peer_id}")
    
    # Store a value
    test_key = "test-key"
    test_value = b"Hello, DHT!"
    success = await node.put_value(test_key, test_value)
    logger.info(f"Stored value: {success}")
    
    # Retrieve the value
    value = await node.get_value(test_key)
    logger.info(f"Retrieved value: {value.decode('utf-8')}")
    
    # Announce as provider
    await node.provide(test_key)
    logger.info(f"Announced as provider for: {test_key}")
    
    # Find providers
    providers = await node.find_providers(test_key)
    logger.info(f"Found {len(providers)} providers for {test_key}")
    
    # Find closest peers
    closest = node.get_closest_peers(test_key)
    logger.info(f"Found {len(closest)} closest peers to {test_key}")
    
    # Stop the node
    await node.stop()
    logger.info("Kademlia node stopped")

async def demo_netstream():
    """Demonstrate NetStream functionality with a mock implementation."""
    logger.info("==== NetStream Demo ====")
    
    # Create mock reader and writer
    reader = anyio.StreamReader()
    writer = MockStreamWriter()
    
    # Create a NetStream
    stream = NetStream(reader, writer, "/test/protocol/1.0.0", "test-peer-id")
    
    # Add some data to the reader
    reader.feed_data(b"Hello, Stream!")
    reader.feed_eof()
    
    # Read from the stream
    data = await stream.read()
    logger.info(f"Read from stream: {data.decode('utf-8')}")
    
    # Write to the stream
    bytes_written = await stream.write(b"Response data")
    logger.info(f"Wrote {bytes_written} bytes to stream")
    logger.info(f"Stream writer received: {writer.get_written_data().decode('utf-8')}")
    
    # Close the stream
    await stream.close()
    logger.info("Stream closed")
    
    # Create a stream handler
    async def handle_stream(stream):
        data = await stream.read()
        logger.info(f"Handler received: {data.decode('utf-8')}")
        await stream.write(b"Handler response")
        await stream.close()
    
    # Create a stream handler
    handler = StreamHandler("/test/protocol/1.0.0", handle_stream)
    
    # Create a new stream to test the handler
    reader = anyio.StreamReader()
    writer = MockStreamWriter()
    stream = NetStream(reader, writer, "/test/protocol/1.0.0", "other-peer-id")
    
    # Add test data
    reader.feed_data(b"Test handler data")
    reader.feed_eof()
    
    # Handle the stream
    await handler.handle_stream(stream)
    logger.info(f"Handler wrote: {writer.get_written_data().decode('utf-8')}")

class MockStreamWriter:
    """Mock implementation of anyio.StreamWriter for testing."""
    
    def __init__(self):
        self.buffer = bytearray()
        self.closed = False
    
    def write(self, data):
        """Write data to the buffer."""
        self.buffer.extend(data)
    
    async def drain(self):
        """Mock drain operation."""
        await anyio.sleep(0)
    
    def close(self):
        """Close the writer."""
        self.closed = True
    
    async def wait_closed(self):
        """Wait for the writer to close."""
        await anyio.sleep(0)
    
    def get_written_data(self):
        """Get the data written to the buffer."""
        return bytes(self.buffer)

async def main():
    """Run all demos."""
    if not MODULES_AVAILABLE:
        logger.error("Required modules are not available. Exiting.")
        return
    
    try:
        # Run the PubSub demo
        await demo_pubsub()
        print()
        
        # Run the Kademlia demo
        await demo_kademlia()
        print()
        
        # Run the NetStream demo
        await demo_netstream()
        
    except Exception as e:
        logger.error(f"Error running demos: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Create and run the event loop
    loop = anyio.get_event_loop()
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()