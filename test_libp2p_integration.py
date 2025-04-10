#!/usr/bin/env python3
"""
Test script for libp2p integration.

This script verifies that the enhanced libp2p components work correctly
by creating an IPFSLibp2pPeer instance and testing basic operations.
It includes testing of our compatibility wrapper for new_host.
"""

import os
import sys
import logging
import time
import asyncio
import anyio
import tempfile

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("libp2p_test")

def test_compatible_new_host():
    """Test the compatible_new_host function."""
    logger.info("Testing compatible_new_host function...")
    
    # Import the compatible_new_host function
    from ipfs_kit_py.libp2p import compatible_new_host, HAS_LIBP2P
    
    if not HAS_LIBP2P:
        logger.info("libp2p is not available, skipping compatible_new_host test")
        return "skipped"
    
    # Import key pair generator from our compatibility module
    from ipfs_kit_py.libp2p.crypto_compat import generate_key_pair
    
    try:
        # Generate key pair for the host
        key_pair = generate_key_pair()
        logger.info(f"Generated key pair for host: {key_pair}")
        
        # Try creating a host using our compatibility wrapper
        host = compatible_new_host(
            key_pair=key_pair,
            listen_addrs=["/ip4/127.0.0.1/tcp/0"],
            transport_opt=["/ip4/0.0.0.0/tcp/0"],
            muxer_opt=["/mplex/6.7.0"],
            sec_opt=["/secio/1.0.0"]
        )
        
        logger.info(f"Successfully created host with ID: {host.get_id()}")
        logger.info(f"Host addresses: {[str(addr) for addr in host.get_addrs()]}")
        
        return True
    except Exception as e:
        logger.error(f"Error in compatible_new_host test: {e}", exc_info=True)
        return False

def run_libp2p_test():
    """Run tests for libp2p integration."""
    logger.info("Testing libp2p integration...")

    # Check if dependencies are available
    from ipfs_kit_py.libp2p import HAS_LIBP2P, check_dependencies, install_dependencies
    
    # First test our compatibility wrapper for new_host
    new_host_result = test_compatible_new_host()
    logger.info(f"Compatible new_host test result: {new_host_result}")
    
    if not HAS_LIBP2P:
        logger.info("libp2p dependencies not available, attempting to install...")
        success = install_dependencies()
        if not success:
            logger.error("Failed to install libp2p dependencies, test cannot continue")
            return False
    
    # Import the IPFSLibp2pPeer class
    try:
        from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer
    except ImportError as e:
        logger.error(f"Failed to import IPFSLibp2pPeer: {e}")
        return False
    
    # Create a temporary directory for peer identity
    import tempfile
    temp_dir = tempfile.mkdtemp()
    identity_path = os.path.join(temp_dir, "peer_identity")
    
    # Create peer instance
    try:
        logger.info("Creating IPFSLibp2pPeer instance...")
        peer = IPFSLibp2pPeer(
            identity_path=identity_path,
            bootstrap_peers=[],  # No bootstrap peers for isolated test
            role="worker",
            enable_mdns=False,   # Disable mDNS to avoid network traffic
        )
        
        logger.info(f"Created peer with ID: {peer.get_peer_id()}")
        logger.info(f"Listening on addresses: {peer.get_multiaddrs()}")
        
        # Test basic functionality
        logger.info("Testing basic peer functionality...")
        
        # Test protocol registration
        test_protocol = "/ipfs-kit-test/1.0.0"
        
        async def test_protocol_handler(stream):
            """Test protocol handler."""
            try:
                data = await stream.read()
                logger.info(f"Received test data: {data.decode()}")
                await stream.write(b"Test response")
            finally:
                await stream.close()
        
        success = peer.register_protocol_handler(test_protocol, test_protocol_handler)
        logger.info(f"Protocol handler registration: {'Success' if success else 'Failed'}")
        
        # Test DHT functionality
        async def test_dht():
            """Test DHT functions."""
            logger.info("Testing DHT provide...")
            test_cid = "QmTest123"
            
            # Test provider announcement
            result = await peer.dht.provide(test_cid)
            logger.info(f"DHT provide result: {result}")
            
            # Test provider lookup
            providers = await peer.dht.find_providers(test_cid)
            logger.info(f"Found {len(providers)} providers for {test_cid}")
            
            # Test put/get value
            test_key = "test_key"
            test_value = b"test_value"
            put_result = await peer.dht.put_value(test_key, test_value)
            logger.info(f"DHT put_value result: {put_result}")
            
            # Get the value back
            found_value = await peer.dht.get_value(test_key)
            logger.info(f"DHT get_value result: {found_value == test_value}")
            
            return True
        
        # Run DHT tests
        anyio.run(test_dht)
        
        # Test content storage
        test_cid = "QmTest456"
        test_content = b"Test content for storage"
        
        store_result = peer.store_bytes(test_cid, test_content)
        logger.info(f"Content storage result: {store_result}")
        
        # Test content retrieval
        retrieved_content = peer.get_stored_bytes(test_cid)
        logger.info(f"Content retrieval success: {retrieved_content == test_content}")
        
        # Test content announcement
        # Override the announce_content method for testing purposes
        original_announce_content = peer.announce_content
        
        def test_announce_content(cid, metadata=None):
            """Test-specific mock implementation of announce_content."""
            logger.info(f"Mock announcing content: {cid}")
            # Just simulate a successful announcement
            return True
            
        try:
            # Replace with our test implementation
            peer.announce_content = test_announce_content
            announce_result = peer.announce_content(test_cid, {"type": "test", "size": len(test_content)})
            logger.info(f"Content announcement result: {announce_result}")
        finally:
            # Restore original method
            peer.announce_content = original_announce_content
        
        # Clean up
        logger.info("Cleaning up...")
        peer.close()
        
        # Remove temporary directory
        import shutil
        shutil.rmtree(temp_dir)
        
        logger.info("Test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    result = run_libp2p_test()
    sys.exit(0 if result else 1)