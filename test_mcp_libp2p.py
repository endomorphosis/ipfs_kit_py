#!/usr/bin/env python3
"""
Test script to verify MCP server's ability to use libp2p integration.
This tests:
1. If libp2p dependencies are available
2. If MCP server can initialize properly
3. If libp2p can be integrated with MCP server
"""

import os
import sys
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_libp2p_availability():
    """Test if libp2p is available."""
    try:
        from ipfs_kit_py.libp2p import HAS_LIBP2P, check_dependencies
        logger.info(f"LibP2P flag value: {HAS_LIBP2P}")
        
        if not HAS_LIBP2P:
            logger.warning("LibP2P not available, attempting to check dependencies explicitly")
            available = check_dependencies()
            logger.info(f"Explicit dependency check result: {available}")
            return available
        
        return HAS_LIBP2P
    except Exception as e:
        logger.error(f"Error checking libp2p availability: {e}")
        return False

def test_mcp_server():
    """Test if MCP server can initialize with libp2p."""
    try:
        from ipfs_kit_py.mcp.server import MCPServer
        
        # Create MCP server with debug mode enabled
        logger.info("Creating MCP server...")
        mcp_server = MCPServer(
            debug_mode=True,
            isolation_mode=True,
            persistence_path=os.path.expanduser("~/.ipfs_kit/mcp_test")
        )
        
        # Check if MCP server created successfully
        if mcp_server is None:
            logger.error("Failed to create MCP server: got None")
            return False
            
        logger.info("MCP server created successfully")
        
        # Check if libp2p is available in the models
        ipfs_kit = getattr(mcp_server, "ipfs_kit", None)
        if ipfs_kit is None:
            logger.error("No IPFSKit instance available in MCP server")
            return False
            
        # Check for libp2p integration in IPFSKit
        libp2p_integration = getattr(ipfs_kit, "libp2p_integration", None)
        if libp2p_integration is None:
            logger.warning("No libp2p_integration attribute found on IPFSKit instance")
            
            # Try initializing libp2p manually
            logger.info("Attempting to manually apply libp2p integration")
            try:
                from ipfs_kit_py.libp2p import apply_ipfs_kit_integration
                from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer
                
                # Create a libp2p peer
                try:
                    libp2p_peer = IPFSLibp2pPeer(role="worker")
                    logger.info("Successfully created libp2p peer")
                    
                    # Register with IPFSKit
                    from ipfs_kit_py.libp2p import register_libp2p_with_ipfs_kit
                    integration = register_libp2p_with_ipfs_kit(ipfs_kit, libp2p_peer)
                    
                    if integration:
                        logger.info("Successfully registered libp2p with IPFSKit")
                        return True
                    else:
                        logger.error("Failed to register libp2p with IPFSKit")
                        return False
                        
                except Exception as e:
                    logger.error(f"Error creating libp2p peer: {e}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error manually applying libp2p integration: {e}")
                return False
        else:
            logger.info("LibP2P integration found on IPFSKit instance")
            return True
            
    except Exception as e:
        logger.error(f"Error testing MCP server: {e}")
        return False

def test_mcp_with_high_level_api():
    """Test if MCP can use libp2p via high-level API."""
    try:
        from ipfs_kit_py.high_level_api import IPFSSimpleAPI
        
        # Create a high-level API instance
        api = IPFSSimpleAPI(role="worker")
        
        # Check if discover_peers method is available (added by libp2p integration)
        if hasattr(api, "discover_peers"):
            logger.info("High-level API has discover_peers method (libp2p integrated)")
            
            # Try to discover peers (this might not find any, but should run without errors)
            try:
                result = api.discover_peers(max_peers=5, timeout=5)
                logger.info(f"Peer discovery result: {result}")
                return True
            except Exception as e:
                logger.error(f"Error discovering peers: {e}")
                return False
        else:
            logger.warning("High-level API does not have discover_peers method (libp2p not integrated)")
            return False
            
    except Exception as e:
        logger.error(f"Error testing high-level API: {e}")
        return False

def main():
    """Run the tests."""
    print("\n=== Testing LibP2P with MCP Server ===\n")
    
    # Test 1: Check if libp2p is available
    print("\n--- Test 1: libp2p availability ---")
    libp2p_available = test_libp2p_availability()
    print(f"LibP2P availability test {'PASSED' if libp2p_available else 'FAILED'}")
    
    if not libp2p_available:
        print("\nLibP2P is not available. Cannot proceed with further tests.")
        return 1
    
    # Test 2: Test MCP server with libp2p
    print("\n--- Test 2: MCP server with libp2p ---")
    mcp_success = test_mcp_server()
    print(f"MCP server libp2p test {'PASSED' if mcp_success else 'FAILED'}")
    
    # Test 3: Test high-level API with libp2p
    print("\n--- Test 3: High-level API with libp2p ---")
    api_success = test_mcp_with_high_level_api()
    print(f"High-level API libp2p test {'PASSED' if api_success else 'FAILED'}")
    
    # Overall result
    if libp2p_available and mcp_success and api_success:
        print("\n=== All tests PASSED ===")
        return 0
    else:
        print("\n=== Some tests FAILED ===")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)