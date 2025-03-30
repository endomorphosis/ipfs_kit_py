"""
Example of using the enhanced libp2p integration with IPFS Kit.

This example demonstrates how to:
1. Initialize the libp2p peer with discovery
2. Integrate it with the IPFSKit instance
3. Retrieve content directly via P2P connections
4. Handle cache misses with direct P2P content retrieval
"""

import os
import sys
import time
import logging
import tempfile

# Ensure package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer
from ipfs_kit_py.libp2p.p2p_integration import register_libp2p_with_ipfs_kit
from ipfs_kit_py.libp2p.ipfs_kit_integration import apply_ipfs_kit_integration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

def setup_ipfs_with_libp2p():
    """Set up IPFS Kit with integrated libp2p peer."""
    print("Setting up IPFS Kit with libp2p integration...")
    
    # Create IPFS Kit instance
    kit = ipfs_kit()
    
    # Create libp2p peer
    try:
        libp2p_peer = IPFSLibp2pPeer(
            role="leecher",
            bootstrap_peers=[
                # Add some public bootstrap peers
                "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN",
                "/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa"
            ]
        )
        print("Created libp2p peer successfully")
    except Exception as e:
        print(f"Could not create libp2p peer: {e}")
        print("Continuing without libp2p peer")
        return kit, None
    
    # Register libp2p peer with IPFS Kit
    integration = register_libp2p_with_ipfs_kit(kit, libp2p_peer)
    print("Registered libp2p peer with IPFS Kit")
    
    return kit, libp2p_peer

def add_test_content(kit):
    """Add some test content to IPFS."""
    print("\nAdding test content to IPFS...")
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(b"Hello from IPFS Kit with enhanced libp2p integration!")
        temp_file_path = temp_file.name
    
    # Add the file to IPFS
    result = kit.ipfs_add_file(temp_file_path)
    
    # Clean up
    os.unlink(temp_file_path)
    
    if result['success']:
        cid = result['Hash']
        print(f"Added test content with CID: {cid}")
        return cid
    else:
        print(f"Failed to add test content: {result}")
        return None

def retrieve_content_via_filesystem(kit, cid):
    """Retrieve content via the filesystem interface."""
    print("\nRetrieving content via filesystem interface...")
    
    # Get the filesystem interface with libp2p integration
    fs = kit.get_filesystem(use_libp2p=True)
    
    if not fs:
        print("Failed to create filesystem interface")
        return None
    
    print("Created filesystem interface with libp2p integration")
    
    # Retrieve the content
    try:
        content = fs.cat(cid)
        print(f"Retrieved content: {content}")
        return content
    except Exception as e:
        print(f"Failed to retrieve content: {e}")
        return None

def test_libp2p_direct_retrieval(kit, libp2p_peer, cid):
    """Test direct content retrieval using libp2p."""
    if not libp2p_peer or not hasattr(kit, 'libp2p_integration'):
        print("\nSkipping direct libp2p retrieval test (no libp2p integration)")
        return
    
    print("\nTesting direct content retrieval using libp2p...")
    
    # Try to retrieve the content directly using libp2p
    try:
        content = kit.libp2p_integration.handle_cache_miss(cid)
        
        if content:
            print(f"Successfully retrieved content directly via libp2p: {content}")
        else:
            print("Failed to retrieve content directly via libp2p")
            
    except Exception as e:
        print(f"Error during direct libp2p retrieval: {e}")

def show_stats(kit):
    """Show statistics from the libp2p integration."""
    if not hasattr(kit, 'libp2p_integration'):
        print("\nNo libp2p integration statistics available")
        return
    
    print("\nLibP2P Integration Statistics:")
    
    stats = kit.libp2p_integration.get_stats()
    
    print(f"  Cache misses: {stats.get('cache_misses', 0)}")
    print(f"  Cache misses handled: {stats.get('cache_misses_handled', 0)}")
    print(f"  Cache misses failed: {stats.get('cache_misses_failed', 0)}")
    print(f"  Success rate: {stats.get('success_rate', 0):.2f}")
    
    avg_time = stats.get('average_retrieve_time', 0)
    if avg_time:
        print(f"  Average retrieval time: {avg_time:.2f}s")
    
    # Show discovery metrics if available
    discovery_metrics = stats.get('discovery_metrics', {})
    if discovery_metrics:
        print("\nDiscovery Metrics:")
        print(f"  Successful retrievals: {discovery_metrics.get('successful_retrievals', 0)}")
        print(f"  Failed retrievals: {discovery_metrics.get('failed_retrievals', 0)}")
        print(f"  Total bytes retrieved: {discovery_metrics.get('total_bytes_retrieved', 0)}")

def main():
    """Run the example."""
    print("IPFS Kit with Enhanced LibP2P Integration Example")
    print("================================================")
    
    # Ensure the IPFSKit class is extended with libp2p integration
    apply_ipfs_kit_integration()
    
    # Set up IPFS with libp2p
    kit, libp2p_peer = setup_ipfs_with_libp2p()
    
    # Add test content
    cid = add_test_content(kit)
    if not cid:
        print("Cannot continue without test content")
        return
    
    # Retrieve content via filesystem
    content = retrieve_content_via_filesystem(kit, cid)
    
    # Test direct libp2p retrieval
    test_libp2p_direct_retrieval(kit, libp2p_peer, cid)
    
    # Show statistics
    show_stats(kit)
    
    print("\nExample completed!")

if __name__ == "__main__":
    main()