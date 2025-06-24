#!/usr/bin/env python3
"""
LibP2P Protocol Integration Example

This example demonstrates the complete protocol integration in ipfs_kit_py's
libp2p implementation. It shows how the various components work together:

1. Enhanced Protocol Negotiation with semantic versioning and capabilities
2. GossipSub Protocol for efficient publish/subscribe messaging
3. Recursive and Delegated Routing for content discovery
4. Kademlia DHT for distributed content routing

The example creates a network of peers that communicate using these protocols
and demonstrates content routing, pub/sub messaging, and protocol negotiation.

This example requires the libp2p dependencies to be installed:
pip install libp2p multiaddr base58 cryptography semver
"""

import os
import sys
import time
import json
import anyio
import logging
import argparse
import random
from typing import Dict, List, Optional, Set, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("protocol-integration-example")

# Import libp2p components
try:
    from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer
    from ipfs_kit_py.libp2p.protocol_integration import (
        apply_protocol_extensions,
        get_available_extensions
    )
except ImportError:
    logger.error("Failed to import required modules. Make sure ipfs_kit_py is installed.")
    sys.exit(1)

# Dictionary to simulate content storage
CONTENT_STORE = {}

# Define protocol handlers
async def echo_protocol_handler(stream):
    """Simple echo protocol that echoes back received data."""
    logger.info(f"Handling stream with echo protocol")

    try:
        while True:
            data = await stream.read(1024)
            if not data:
                break

            logger.info(f"Echo: received {len(data)} bytes")
            await stream.write(data)

    except Exception as e:
        logger.error(f"Error in echo protocol: {e}")
    finally:
        await stream.close()

async def content_request_handler(stream):
    """Handler for content request protocol."""
    logger.info(f"Handling content request")

    try:
        # Read request
        data = await stream.read(4096)
        if not data:
            await stream.close()
            return

        # Parse request
        request = json.loads(data.decode('utf-8'))
        cid = request.get('cid')

        response = {'success': False}

        # Check if we have the content
        if cid and cid in CONTENT_STORE:
            content = CONTENT_STORE[cid]
            response = {
                'success': True,
                'cid': cid,
                'content': content
            }

        # Send response
        await stream.write(json.dumps(response).encode('utf-8'))

    except Exception as e:
        logger.error(f"Error handling content request: {e}")
    finally:
        await stream.close()

async def create_peer(role="leecher", bootstrap_peers=None):
    """Create and configure a peer with protocol extensions."""
    # Display available extensions
    extensions = get_available_extensions()
    logger.info(f"Available protocol extensions: {extensions}")

    # Create the peer
    peer = IPFSLibp2pPeer(role=role)

    # Apply protocol extensions
    peer = apply_protocol_extensions(peer)

    # Register protocol handlers with capabilities
    peer.register_protocol_with_capabilities(
        "/echo/1.0.0",
        echo_protocol_handler,
        ["text", "binary"]
    )

    peer.register_protocol_with_capabilities(
        "/content-request/1.0.0",
        content_request_handler,
        ["ipfs-content", "fetch"]
    )

    # Start the peer
    await peer.start()

    # Connect to bootstrap peers if provided
    if bootstrap_peers:
        for addr in bootstrap_peers:
            logger.info(f"Connecting to bootstrap peer: {addr}")
            await peer.connect_peer(addr)

    # Log peer information
    peer_id = peer.get_peer_id()
    addresses = peer.get_addrs()

    logger.info(f"Peer ID: {peer_id}")
    logger.info(f"Addresses: {addresses}")

    return peer

async def store_and_announce_content(peer, content_id, content):
    """Store content locally and announce it to the network."""
    # Store locally
    CONTENT_STORE[content_id] = content

    # Announce content availability via DHT
    if hasattr(peer, 'provide'):
        try:
            logger.info(f"Announcing content {content_id} availability via DHT")
            success = await peer.provide(content_id)
            logger.info(f"DHT announcement {'successful' if success else 'failed'}")
        except Exception as e:
            logger.error(f"Error announcing content: {e}")

    # Also announce via GossipSub
    if hasattr(peer, 'publish'):
        try:
            topic = f"content-announcements"
            announcement = {
                "peer_id": peer.get_peer_id(),
                "cid": content_id,
                "timestamp": time.time()
            }

            logger.info(f"Publishing content announcement to {topic}")
            await peer.publish(topic, json.dumps(announcement).encode('utf-8'))
        except Exception as e:
            logger.error(f"Error publishing announcement: {e}")

async def find_and_fetch_content(peer, content_id):
    """Find and fetch content from the network."""
    logger.info(f"Searching for content: {content_id}")

    # First, try to find via DHT
    if hasattr(peer, 'find_providers'):
        try:
            logger.info(f"Looking up providers via DHT")
            providers = await peer.find_providers(content_id)

            if providers:
                logger.info(f"Found {len(providers)} providers via DHT: {providers}")

                # Try to fetch from first provider
                for provider_id in providers:
                    try:
                        # Connect to provider if needed
                        if not peer.is_peer_connected(provider_id):
                            logger.info(f"Connecting to provider {provider_id}")
                            success = await peer.connect_peer(provider_id)
                            if not success:
                                logger.warning(f"Failed to connect to provider {provider_id}")
                                continue

                        # Open stream for content request
                        logger.info(f"Requesting content from {provider_id}")
                        stream = await peer.new_stream(provider_id, "/content-request/1.0.0")

                        # Send request
                        request = {
                            "cid": content_id,
                            "requester": peer.get_peer_id()
                        }
                        await stream.write(json.dumps(request).encode('utf-8'))

                        # Read response
                        data = await stream.read(4096)
                        await stream.close()

                        if data:
                            response = json.loads(data.decode('utf-8'))
                            if response.get('success'):
                                logger.info(f"Successfully retrieved content from DHT provider")
                                # Store locally
                                CONTENT_STORE[content_id] = response.get('content')
                                return response.get('content')
                    except Exception as e:
                        logger.error(f"Error fetching from provider {provider_id}: {e}")
                        continue
        except Exception as e:
            logger.error(f"Error in DHT lookup: {e}")

    # If DHT failed, try recursive routing
    if hasattr(peer, 'find_content_recursively'):
        try:
            logger.info(f"Trying recursive routing")
            result = await peer.find_content_recursively(content_id)
            if result and 'provider' in result:
                provider_id = result['provider']

                logger.info(f"Found provider via recursive routing: {provider_id}")
                # Similar fetch logic as above
                try:
                    # Connect to provider if needed
                    if not peer.is_peer_connected(provider_id):
                        success = await peer.connect_peer(provider_id)
                        if not success:
                            logger.warning(f"Failed to connect to provider {provider_id}")
                        else:
                            # Fetch content as above
                            stream = await peer.new_stream(provider_id, "/content-request/1.0.0")
                            request = {"cid": content_id, "requester": peer.get_peer_id()}
                            await stream.write(json.dumps(request).encode('utf-8'))
                            data = await stream.read(4096)
                            await stream.close()

                            if data:
                                response = json.loads(data.decode('utf-8'))
                                if response.get('success'):
                                    logger.info(f"Successfully retrieved content via recursive routing")
                                    # Store locally
                                    CONTENT_STORE[content_id] = response.get('content')
                                    return response.get('content')
                except Exception as e:
                    logger.error(f"Error fetching via recursive routing: {e}")
        except Exception as e:
            logger.error(f"Error in recursive routing: {e}")

    # As a last resort, broadcast a request over GossipSub
    if hasattr(peer, 'publish') and hasattr(peer, 'subscribe'):
        try:
            logger.info(f"Broadcasting content request via GossipSub")

            # Set up a response handler
            content_response = None
            response_event = anyio.Event()

            async def handle_content_response(peer_id, message):
                nonlocal content_response
                try:
                    data = json.loads(message.decode('utf-8'))
                    if data.get('cid') == content_id and data.get('content'):
                        logger.info(f"Received content response via GossipSub from {peer_id}")
                        content_response = data.get('content')
                        response_event.set()
                except Exception as e:
                    logger.error(f"Error processing content response: {e}")

            # Subscribe to responses
            response_topic = f"content-responses-{peer.get_peer_id()}"
            await peer.subscribe(response_topic, handle_content_response)

            # Publish request
            request_topic = "content-requests"
            request = {
                "cid": content_id,
                "requester": peer.get_peer_id(),
                "response_topic": response_topic,
                "timestamp": time.time()
            }
            await peer.publish(request_topic, json.dumps(request).encode('utf-8'))

            # Wait for response with timeout
            try:
                await anyio.wait_for(response_event.wait(), timeout=10.0)

                if content_response:
                    logger.info(f"Successfully retrieved content via GossipSub")
                    # Store locally
                    CONTENT_STORE[content_id] = content_response
                    return content_response
            except anyio.TimeoutError:
                logger.warning(f"No response received via GossipSub within timeout")

            # Unsubscribe from response topic
            await peer.unsubscribe(response_topic)

        except Exception as e:
            logger.error(f"Error in GossipSub request: {e}")

    logger.warning(f"Failed to find content {content_id}")
    return None

async def setup_content_request_handler(peer):
    """Set up handler for content requests over GossipSub."""
    if not hasattr(peer, 'subscribe'):
        logger.warning("Peer does not support PubSub")
        return

    # Handler for content requests
    async def handle_content_request(peer_id, message):
        try:
            data = json.loads(message.decode('utf-8'))
            cid = data.get('cid')
            requester = data.get('requester')
            response_topic = data.get('response_topic')

            if cid and requester and response_topic and cid in CONTENT_STORE:
                logger.info(f"Have requested content {cid}, responding via {response_topic}")

                # Publish response
                response = {
                    "cid": cid,
                    "content": CONTENT_STORE[cid],
                    "provider": peer.get_peer_id(),
                    "timestamp": time.time()
                }

                await peer.publish(response_topic, json.dumps(response).encode('utf-8'))
        except Exception as e:
            logger.error(f"Error handling content request: {e}")

    # Subscribe to content requests
    request_topic = "content-requests"
    await peer.subscribe(request_topic, handle_content_request)
    logger.info(f"Subscribed to content requests on {request_topic}")

async def demonstrate_protocol_negotiation(peer, target_peer_id):
    """Demonstrate protocol negotiation with another peer."""
    logger.info(f"Demonstrating protocol negotiation with {target_peer_id}")

    try:
        # Negotiate best echo protocol version
        logger.info("Selecting best protocol version...")
        best_version = await peer.select_best_protocol_version(
            target_peer_id,
            "/echo",
            "1.0.0"  # Minimum acceptable version
        )

        logger.info(f"Best protocol version: {best_version}")

        # Check protocol capabilities
        if best_version:
            capabilities = await peer.get_protocol_capabilities(
                target_peer_id,
                best_version
            )

            logger.info(f"Protocol capabilities: {capabilities}")

            # Test the protocol
            logger.info(f"Testing protocol {best_version}...")
            stream = await peer.new_stream(target_peer_id, best_version)

            # Send and receive data
            test_message = f"Hello from {peer.get_peer_id()}!"
            await stream.write(test_message.encode('utf-8'))
            response = await stream.read(1024)

            logger.info(f"Received response: {response.decode('utf-8')}")
            await stream.close()
    except Exception as e:
        logger.error(f"Error in protocol negotiation: {e}")

async def run_publisher_node(bootstrap_peer=None):
    """Run a node that publishes content to the network."""
    logger.info("Starting publisher node")

    # Create and start peer
    peer = await create_peer(role="worker", bootstrap_peers=[bootstrap_peer] if bootstrap_peer else None)

    # Generate some test content
    content_ids = []
    for i in range(5):
        content_id = f"content-{i}-{random.randint(1000, 9999)}"
        content = f"This is test content #{i} from {peer.get_peer_id()}"

        # Store and announce content
        await store_and_announce_content(peer, content_id, content)
        content_ids.append(content_id)

        # Wait a bit between announcements
        await anyio.sleep(1)

    # Set up content request handler
    await setup_content_request_handler(peer)

    # Listen for content requests and keep providing content
    logger.info(f"Publisher node running with {len(content_ids)} content items: {content_ids}")

    try:
        while True:
            # Periodically re-announce content
            for content_id in content_ids:
                await store_and_announce_content(peer, content_id, CONTENT_STORE[content_id])

            # Wait before next announcement cycle
            await anyio.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutting down publisher node...")
    finally:
        await peer.stop()

async def run_consumer_node(bootstrap_peer, publisher_content_ids=None):
    """Run a node that consumes content from the network."""
    logger.info("Starting consumer node")

    # Create and start peer
    peer = await create_peer(role="leecher", bootstrap_peers=[bootstrap_peer] if bootstrap_peer else None)

    # Wait for DHT to be initialized if available
    if hasattr(peer, 'initialize_kademlia'):
        await peer.initialize_kademlia()
        await anyio.sleep(5)  # Give some time for DHT operations to start

    # Set up GossipSub subscriptions if available
    if hasattr(peer, 'subscribe'):
        # Subscribe to content announcements
        async def handle_announcement(peer_id, message):
            try:
                data = json.loads(message.decode('utf-8'))
                cid = data.get('cid')
                provider = data.get('peer_id')

                logger.info(f"Received content announcement: {cid} from {provider}")

                # Optionally fetch announced content
                if cid not in CONTENT_STORE:
                    logger.info(f"Fetching newly announced content: {cid}")
                    content = await find_and_fetch_content(peer, cid)
                    if content:
                        logger.info(f"Successfully fetched announced content: {cid}")
            except Exception as e:
                logger.error(f"Error handling announcement: {e}")

        # Subscribe to announcements
        await peer.subscribe("content-announcements", handle_announcement)
        logger.info("Subscribed to content announcements")

    # Set up content request handler
    await setup_content_request_handler(peer)

    # If we have specific content IDs to fetch, try to fetch them
    if publisher_content_ids:
        for content_id in publisher_content_ids:
            logger.info(f"Attempting to fetch content: {content_id}")
            content = await find_and_fetch_content(peer, content_id)

            if content:
                logger.info(f"Successfully fetched content: {content}")
            else:
                logger.warning(f"Failed to fetch content: {content_id}")

            # Wait a bit between fetches
            await anyio.sleep(2)

    # Keep running and listening for announcements
    try:
        while True:
            await anyio.sleep(10)
            logger.info(f"Consumer has {len(CONTENT_STORE)} content items")
    except KeyboardInterrupt:
        logger.info("Shutting down consumer node...")
    finally:
        await peer.stop()

async def run_demo():
    """Run a complete demonstration of protocol integration."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="LibP2P Protocol Integration Example")
    parser.add_argument('--role', choices=['bootstrap', 'publisher', 'consumer'],
                        default='bootstrap', help='Node role to run')
    parser.add_argument('--peer', help='Bootstrap peer multiaddress')
    parser.add_argument('--content', help='Content IDs to fetch (comma-separated)')
    args = parser.parse_args()

    # Run the appropriate node type
    if args.role == 'bootstrap':
        # Run a bootstrap node
        logger.info("Starting bootstrap node")
        peer = await create_peer(role="master")

        # Display connection information
        peer_id = peer.get_peer_id()
        addresses = peer.get_addrs()

        print("\n" + "="*50)
        print(f"BOOTSTRAP NODE INFORMATION")
        print(f"Peer ID: {peer_id}")
        print(f"Connect using: {addresses[0]}/p2p/{peer_id}")
        print("="*50 + "\n")

        # Keep running
        try:
            while True:
                await anyio.sleep(60)

                # Log connected peers
                if hasattr(peer, 'kad_routing_table') and peer.kad_routing_table:
                    peer_count = len(peer.kad_routing_table.get_peers())
                    logger.info(f"DHT has {peer_count} peers")
        except KeyboardInterrupt:
            logger.info("Shutting down bootstrap node...")
        finally:
            await peer.stop()

    elif args.role == 'publisher':
        # Run a publisher node
        if not args.peer:
            logger.error("Publisher mode requires --peer argument with bootstrap peer address")
            return

        await run_publisher_node(bootstrap_peer=args.peer)

    elif args.role == 'consumer':
        # Run a consumer node
        if not args.peer:
            logger.error("Consumer mode requires --peer argument with bootstrap peer address")
            return

        # Parse content IDs if provided
        content_ids = None
        if args.content:
            content_ids = args.content.split(',')

        await run_consumer_node(bootstrap_peer=args.peer, publisher_content_ids=content_ids)

if __name__ == "__main__":
    try:
        anyio.run(run_demo())
    except KeyboardInterrupt:
        print("\nExiting...")
