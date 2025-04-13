#!/usr/bin/env python3
"""
LibP2P MCP Server Integration Test

This script tests the integration between libp2p and the MCP server,
verifying that the libp2p controller can properly start and use the
libp2p peer.

Usage:
    python test_mcp_libp2p.py [--verbose]
"""

import os
import sys
import logging
import argparse
import time
import json
import anyio
from pprint import pprint

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import MCP server components
try:
    from ipfs_kit_py.mcp.server import MCPServer
    from ipfs_kit_py.mcp.controllers.libp2p_controller import LibP2PController
    HAS_MCP = True
except ImportError as e:
    logger.error(f"Failed to import MCP server: {e}")
    HAS_MCP = False

# Try to import FastAPI for testing the server
try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    HAS_FASTAPI = True
except ImportError as e:
    logger.error(f"Failed to import FastAPI: {e}")
    HAS_FASTAPI = False

def run_libp2p_verification():
    """Run libp2p installation verification step."""
    logger.info("\nStep 1: Verifying libp2p installation...")
    
    # Import the verification function
    try:
        from install_libp2p import verify_libp2p_functionality
        result = verify_libp2p_functionality()
        if result:
            logger.info("✅ libp2p functionality verification passed")
        else:
            logger.error("❌ libp2p functionality verification failed")
        return result
    except ImportError as e:
        logger.error(f"❌ Could not import verification function: {e}")
        return False

def verify_crypto_compat():
    """Verify the crypto_compat module functionality."""
    logger.info("\nStep 2: Verifying crypto_compat module...")
    
    try:
        from ipfs_kit_py.libp2p.crypto_compat import (
            generate_key_pair, 
            serialize_private_key, 
            PREFERRED_KEY_GENERATION_METHOD
        )
        
        logger.info(f"Preferred key generation method: {PREFERRED_KEY_GENERATION_METHOD}")
        
        # Try to generate a key pair
        key_pair = generate_key_pair()
        logger.info(f"Generated key pair: {type(key_pair)}")
        
        # Try to serialize the private key
        key_data = serialize_private_key(key_pair.private_key)
        logger.info(f"Serialized private key: {len(key_data)} bytes")
        
        logger.info("✅ crypto_compat functionality verification passed")
        return True
    except Exception as e:
        logger.error(f"❌ crypto_compat verification failed: {e}")
        return False

def test_libp2p_peer():
    """Test the LibP2P peer functionality directly."""
    logger.info("\nStep 3: Testing LibP2P peer directly...")
    
    try:
        from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer
        
        # Create a peer for testing
        peer = IPFSLibp2pPeer(
            role="leecher",
            enable_mdns=False,  # Disable mDNS for testing
            metadata={"test_mode": True}
        )
        
        # Get peer ID
        peer_id = peer.get_peer_id()
        logger.info(f"Peer ID: {peer_id}")
        
        # Get listen addresses
        addresses = peer.get_listen_addresses()
        logger.info(f"Listen addresses: {addresses}")
        
        # Close the peer
        peer.close()
        
        logger.info("✅ LibP2P peer test passed")
        return True
    except Exception as e:
        logger.error(f"❌ LibP2P peer test failed: {e}")
        return False

def test_mcp_server():
    """Test the MCP server with LibP2P integration."""
    if not HAS_MCP or not HAS_FASTAPI:
        logger.error("❌ MCP server or FastAPI not available")
        return False
        
    logger.info("\nStep 4: Testing MCP server with LibP2P integration...")
    
    try:
        # Create a FastAPI app for testing
        app = FastAPI(title="IPFS MCP Test Server")
        
        # Create MCP server
        mcp_server = MCPServer(
            debug_mode=True,
            log_level="DEBUG",
            isolation_mode=True
        )
        
        # Register with FastAPI app
        mcp_server.register_with_app(app, prefix="/mcp")
        
        # Create test client
        client = TestClient(app)
        
        # Test health endpoint
        logger.info("Testing health endpoint...")
        response = client.get("/mcp/health")
        logger.info(f"Health response status: {response.status_code}")
        assert response.status_code == 200
        
        # Test libp2p health endpoint
        logger.info("Testing libp2p health endpoint...")
        response = client.get("/mcp/libp2p/health")
        logger.info(f"LibP2P health response status: {response.status_code}")
        
        # Print response if successful
        if response.status_code == 200:
            health_data = response.json()
            logger.info(f"LibP2P available: {health_data.get('libp2p_available', False)}")
            logger.info(f"Peer initialized: {health_data.get('peer_initialized', False)}")
            logger.info(f"Peer ID: {health_data.get('peer_id')}")
            logger.info(f"Role: {health_data.get('role')}")
        
        # Test peer discovery endpoint
        logger.info("Testing peer discovery endpoint...")
        response = client.post(
            "/mcp/libp2p/discover",
            json={"discovery_method": "bootstrap", "limit": 5}
        )
        logger.info(f"Discovery response status: {response.status_code}")
        
        if response.status_code == 200:
            discovery_data = response.json()
            logger.info(f"Discovery success: {discovery_data.get('success', False)}")
            logger.info(f"Discovered peers: {discovery_data.get('peer_count', 0)}")
        
        logger.info("✅ MCP server test passed")
        return True
    except Exception as e:
        logger.error(f"❌ MCP server test failed: {e}")
        return False

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Test LibP2P MCP server integration")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        # Set log level for relevant modules
        logging.getLogger("ipfs_kit_py").setLevel(logging.DEBUG)
    
    # Run verification steps
    logger.info("=== LibP2P MCP Server Integration Test ===")
    
    # Step 1: Verify libp2p installation
    libp2p_ok = run_libp2p_verification()
    
    # Step 2: Verify crypto_compat
    crypto_ok = verify_crypto_compat()
    
    # Step 3: Test LibP2P peer
    peer_ok = test_libp2p_peer()
    
    # Step 4: Test MCP server
    mcp_ok = test_mcp_server()
    
    # Summarize results
    logger.info("\n=== Test Results ===")
    logger.info(f"libp2p verification: {'✅ Passed' if libp2p_ok else '❌ Failed'}")
    logger.info(f"crypto_compat verification: {'✅ Passed' if crypto_ok else '❌ Failed'}")
    logger.info(f"LibP2P peer test: {'✅ Passed' if peer_ok else '❌ Failed'}")
    logger.info(f"MCP server test: {'✅ Passed' if mcp_ok else '❌ Failed'}")
    
    # Overall result
    if libp2p_ok and crypto_ok and peer_ok and mcp_ok:
        logger.info("\n🎉 All tests passed! LibP2P is fully integrated with the MCP server.")
        return 0
    else:
        logger.error("\n❌ Some tests failed. See above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())