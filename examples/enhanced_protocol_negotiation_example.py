#!/usr/bin/env python3
"""
Enhanced Protocol Negotiation Example

This example demonstrates the enhanced protocol negotiation system in ipfs_kit_py's
libp2p implementation. It shows how to:

1. Create a peer with enhanced protocol negotiation
2. Register protocols with specific capabilities
3. Negotiate protocols with semantic versioning support
4. Query protocol capabilities

This example requires the libp2p dependencies to be installed:
pip install libp2p multiaddr base58 cryptography semver
"""

import anyio
import logging
import sys
from typing import Optional, List, Set, Dict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("enhanced-protocol-example")

# Import libp2p components
try:
    from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer
    from ipfs_kit_py.libp2p import apply_enhanced_protocol_negotiation, get_enhanced_protocol_negotiation
except ImportError:
    logger.error("Failed to import required modules. Make sure ipfs_kit_py is installed.")
    sys.exit(1)

# Define example protocol handlers
async def echo_protocol_handler(stream):
    """Simple echo protocol that just echoes back any received data."""
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

async def chat_protocol_handler(stream):
    """Simple chat protocol that prefixes responses."""
    logger.info(f"Handling stream with chat protocol")
    
    try:
        while True:
            data = await stream.read(1024)
            if not data:
                break
                
            message = data.decode('utf-8')
            logger.info(f"Chat: received message: {message}")
            
            # Create a response
            response = f"Server: I received your message: {message}"
            await stream.write(response.encode('utf-8'))
            
    except Exception as e:
        logger.error(f"Error in chat protocol: {e}")
    finally:
        await stream.close()

async def json_protocol_handler(stream):
    """Protocol that handles JSON messages."""
    logger.info(f"Handling stream with JSON protocol")
    
    try:
        import json
        
        while True:
            # Read until newline delimiter
            data = await stream.read(1024)
            if not data:
                break
                
            # Parse JSON
            try:
                message = json.loads(data.decode('utf-8'))
                logger.info(f"JSON: received message: {message}")
                
                # Create a response
                import time
                response = {
                    "status": "ok",
                    "received": message,
                    "timestamp": time.time()
                }
                
                # Send JSON response with newline
                await stream.write((json.dumps(response) + '\n').encode('utf-8'))
                
            except json.JSONDecodeError:
                error_resp = {"status": "error", "message": "Invalid JSON"}
                await stream.write((json.dumps(error_resp) + '\n').encode('utf-8'))
                
    except Exception as e:
        logger.error(f"Error in JSON protocol: {e}")
    finally:
        await stream.close()

async def run_server():
    """Run a libp2p server with enhanced protocol negotiation."""
    # Create a peer with enhanced protocol negotiation
    peer = IPFSLibp2pPeer(role="worker")
    
    # Apply enhanced protocol negotiation
    peer = apply_enhanced_protocol_negotiation(peer)
    
    # Register protocols with capabilities
    peer.register_protocol_with_capabilities(
        protocol_id="/echo/1.0.0", 
        handler_fn=echo_protocol_handler,
        capabilities=["text", "binary"]
    )
    
    peer.register_protocol_with_capabilities(
        protocol_id="/chat/1.1.0", 
        handler_fn=chat_protocol_handler,
        capabilities=["text", "user-friendly"]
    )
    
    peer.register_protocol_with_capabilities(
        protocol_id="/json/1.0.0", 
        handler_fn=json_protocol_handler,
        capabilities=["structured", "json-schema"]
    )
    
    # Register multiple versions of a protocol
    peer.register_protocol_with_capabilities(
        protocol_id="/ipfs/kad/1.0.0", 
        handler_fn=echo_protocol_handler,  # Just for example
        capabilities=["basic-dht"]
    )
    
    peer.register_protocol_with_capabilities(
        protocol_id="/ipfs/kad/2.0.0", 
        handler_fn=echo_protocol_handler,  # Just for example
        capabilities=["basic-dht", "provider-records", "value-store"]
    )
    
    # Start the peer
    await peer.start()
    
    # Print peer information
    peer_id = peer.get_peer_id()
    addresses = peer.get_addrs()
    
    logger.info(f"Peer ID: {peer_id}")
    logger.info(f"Listening on: {addresses}")
    logger.info("Supported protocols:")
    
    for protocol_id, capabilities in peer.protocol_capabilities.items():
        logger.info(f"  - {protocol_id}: {', '.join(capabilities)}")
    
    # Keep the server running
    try:
        while True:
            await anyio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
    finally:
        await peer.stop()

async def run_client(server_peer_id: str, server_addr: str):
    """Run a libp2p client that connects to the server."""
    # Create a peer with enhanced protocol negotiation
    peer = IPFSLibp2pPeer(role="leecher")
    
    # Apply enhanced protocol negotiation
    peer = apply_enhanced_protocol_negotiation(peer)
    
    # Start the peer
    await peer.start()
    
    logger.info(f"Client peer ID: {peer.get_peer_id()}")
    
    try:
        # Connect to the server
        logger.info(f"Connecting to server: {server_peer_id} at {server_addr}")
        success = await peer.connect_peer(server_addr)
        
        if not success:
            logger.error("Failed to connect to server")
            return
            
        logger.info("Connected to server")
        
        # Demonstrate protocol version negotiation
        logger.info("Selecting best version of /ipfs/kad protocol...")
        best_version = await peer.select_best_protocol_version(
            server_peer_id,
            "/ipfs/kad",
            "1.0.0"  # Minimum version we accept
        )
        
        logger.info(f"Selected version: {best_version}")
        
        # Demonstrate capability query
        logger.info("Querying capabilities of chat protocol...")
        chat_capabilities = await peer.get_protocol_capabilities(
            server_peer_id,
            "/chat/1.1.0"
        )
        
        logger.info(f"Chat protocol capabilities: {chat_capabilities}")
        
        # Test the echo protocol
        logger.info("Opening stream with echo protocol...")
        echo_stream = await peer.new_stream(server_peer_id, "/echo/1.0.0")
        
        # Send and receive data
        test_message = b"Hello, Echo Protocol!"
        await echo_stream.write(test_message)
        response = await echo_stream.read(1024)
        
        logger.info(f"Echo response: {response.decode('utf-8')}")
        await echo_stream.close()
        
        # Test the chat protocol
        logger.info("Opening stream with chat protocol...")
        chat_stream = await peer.new_stream(server_peer_id, "/chat/1.1.0")
        
        # Send and receive data
        chat_message = "Hello from the client!"
        await chat_stream.write(chat_message.encode('utf-8'))
        chat_response = await chat_stream.read(1024)
        
        logger.info(f"Chat response: {chat_response.decode('utf-8')}")
        await chat_stream.close()
        
    except Exception as e:
        logger.error(f"Client error: {e}")
    finally:
        await peer.stop()

async def main():
    """Main function to run the example."""
    # Check if libp2p dependencies are available
    negotiation = get_enhanced_protocol_negotiation()
    if not negotiation:
        logger.error("Enhanced protocol negotiation is not available.")
        logger.error("Make sure libp2p and its dependencies are installed.")
        return
        
    # Parse command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == "client":
        if len(sys.argv) < 4:
            logger.error("Client mode requires peer ID and address arguments.")
            logger.error("Usage: python enhanced_protocol_negotiation_example.py client <peer_id> <multiaddr>")
            return
            
        server_peer_id = sys.argv[2]
        server_addr = sys.argv[3]
        await run_client(server_peer_id, server_addr)
    else:
        # Default to server mode
        await run_server()

if __name__ == "__main__":
    anyio.run(main())