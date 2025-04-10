#!/usr/bin/env python3
"""
Simple test script for verifying basic libp2p functionality.

This script tests only the essential libp2p features to ensure 
the compatibility layers are working correctly.
"""

import os
import sys
import logging
import time
import asyncio
import json
import uuid
import tempfile
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("libp2p_simple_test")

def check_libp2p_imports():
    """Check if all needed libp2p components are available."""
    logger.info("Checking libp2p imports...")
    
    # Check if the flag is set
    from ipfs_kit_py.libp2p import HAS_LIBP2P
    logger.info(f"HAS_LIBP2P flag: {HAS_LIBP2P}")
    
    # Try to import the main libp2p package
    try:
        import libp2p
        logger.info(f"libp2p import: SUCCESS (version: {getattr(libp2p, '__version__', 'unknown')})")
    except ImportError as e:
        logger.error(f"libp2p import: FAILED - {e}")
        return False
        
    # Check if we can import various libp2p components
    components = [
        "libp2p.crypto.keys",
        "libp2p.peer.peerinfo",
    ]
    
    for component in components:
        try:
            __import__(component)
            logger.info(f"Import {component}: SUCCESS")
        except ImportError as e:
            logger.error(f"Import {component}: FAILED - {e}")
    
    return HAS_LIBP2P

def test_key_generation():
    """Test if we can generate and use key pairs correctly."""
    logger.info("Testing key generation...")
    
    # Import our compatibility components
    from ipfs_kit_py.libp2p.crypto_compat import generate_key_pair, serialize_private_key
    
    try:
        # Generate a key pair
        key_pair = generate_key_pair()
        logger.info(f"Generated key pair: {key_pair}")
        
        # Test private key
        private_key = key_pair.private_key
        public_key = key_pair.public_key
        
        # Test serialization
        private_key_bytes = serialize_private_key(private_key)
        logger.info(f"Serialized private key: {len(private_key_bytes)} bytes")
        
        # Test public key serialization
        public_key_bytes = public_key.serialize()
        logger.info(f"Serialized public key: {len(public_key_bytes)} bytes")
        
        return True
    except Exception as e:
        logger.error(f"Error testing key generation: {e}", exc_info=True)
        return False

def test_host_creation():
    """Test if we can create a libp2p host."""
    logger.info("Testing host creation...")
    
    # Import our compatibility components
    from ipfs_kit_py.libp2p import compatible_new_host
    from ipfs_kit_py.libp2p.crypto_compat import generate_key_pair
    
    try:
        # Generate a key pair
        key_pair = generate_key_pair()
        
        # Create a host
        host = compatible_new_host(
            key_pair=key_pair,
            listen_addrs=["/ip4/127.0.0.1/tcp/0"],  # Random port
        )
        
        logger.info(f"Created host with ID: {host.get_id()}")
        logger.info(f"Host addresses: {[str(addr) for addr in host.get_addrs()]}")
        
        return True
    except Exception as e:
        logger.error(f"Error creating host: {e}", exc_info=True)
        return False

def test_libp2p_peer():
    """Test if our libp2p_peer implementation works."""
    logger.info("Testing IPFSLibp2pPeer...")
    
    try:
        # Import the peer class
        from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer
        
        # Create a temporary directory for peer identity
        temp_dir = tempfile.mkdtemp()
        identity_path = os.path.join(temp_dir, "peer_identity")
        
        try:
            # Create a peer instance
            peer = IPFSLibp2pPeer(
                identity_path=identity_path,
                bootstrap_peers=None,  # No bootstrap peers
                role="worker", 
                enable_mdns=False,
            )
            
            # Check if peer initialization worked
            peer_id = peer.get_peer_id()
            logger.info(f"Created peer with ID: {peer_id}")
            
            # Test basic functionality
            test_protocol = "/ipfs-kit-test/1.0.0"
            
            async def test_protocol_handler(stream):
                """Test protocol handler."""
                data = await stream.read()
                logger.info(f"Received data: {data.decode()}")
                await stream.write(b"Test response")
                await stream.close()
            
            # Register protocol handler
            success = peer.register_protocol_handler(test_protocol, test_protocol_handler)
            logger.info(f"Protocol handler registration: {'success' if success else 'failed'}")
            
            # Test DHT functionality
            test_cid = "QmTestCID123"
            
            # We use anyio.run for async functions
            import anyio
            
            # Test DHT provide
            async def test_dht_provide():
                result = await peer.dht.provide(test_cid)
                logger.info(f"DHT provide result: {result}")
                return result
                
            provide_result = anyio.run(test_dht_provide)
            
            # Test storage and retrieval
            test_content = b"Test content for storage"
            store_result = peer.store_bytes(test_cid, test_content)
            logger.info(f"Content storage result: {store_result}")
            
            # Retrieve content
            retrieved_content = peer.get_stored_bytes(test_cid)
            content_match = retrieved_content == test_content
            logger.info(f"Content retrieval success: {content_match}")
            
            # Close peer
            peer.close()
            logger.info("Peer closed successfully")
            
            return provide_result and store_result and content_match
            
        finally:
            # Clean up
            shutil.rmtree(temp_dir)
    
    except Exception as e:
        logger.error(f"Error testing libp2p peer: {e}", exc_info=True)
        return False

def run_libp2p_test():
    """Run tests to verify libp2p functionality."""
    logger.info("Starting libp2p functionality tests...")
    
    # Step 1: Check imports
    import_result = check_libp2p_imports()
    logger.info(f"Import check result: {'SUCCESS' if import_result else 'FAILED'}")
    
    if not import_result:
        logger.error("Critical imports missing, cannot continue")
        return False
    
    # Step 2: Test key generation
    key_result = test_key_generation()
    logger.info(f"Key generation test result: {'SUCCESS' if key_result else 'FAILED'}")
    
    # Step 3: Test host creation
    host_result = test_host_creation()
    logger.info(f"Host creation test result: {'SUCCESS' if host_result else 'FAILED'}")
    
    # Step 4: Test IPFSLibp2pPeer implementation
    peer_result = test_libp2p_peer()
    logger.info(f"IPFSLibp2pPeer test result: {'SUCCESS' if peer_result else 'FAILED'}")
    
    # Overall result
    overall_result = import_result and key_result and host_result and peer_result
    
    if overall_result:
        logger.info("All libp2p functionality tests PASSED!")
    else:
        logger.error("Some libp2p functionality tests FAILED")
    
    return overall_result

if __name__ == "__main__":
    result = run_libp2p_test()
    sys.exit(0 if result else 1)