"""
Example demonstrating peer discovery functionality in the IPFS Kit High-Level API with AnyIO.

This example shows how to:
1. Initialize the high-level API with libp2p integration using AnyIO
2. Discover peers in the network
3. Connect to specific peers
4. Get connected peer information
5. Request content directly from peers
6. Use AnyIO for async operations with backend flexibility
"""

import os
import sys
import time
import logging
import json
import anyio

# Ensure package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ipfs_kit_py.high_level_api import IPFSSimpleAPI
# Import the AnyIO version of the libp2p integration
from ipfs_kit_py.high_level_api.libp2p_integration_anyio import apply_high_level_api_integration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

async def initialize_api():
    """Initialize the high-level API with libp2p integration using AnyIO."""
    print("Initializing high-level API with libp2p integration (AnyIO version)...")
    
    # Apply the high-level API integration
    apply_high_level_api_integration()
    
    # Create a high-level API instance with leecher role (least resource intensive)
    api = IPFSSimpleAPI(role="leecher")
    print("High-level API initialized")
    
    return api

def print_formatted_result(result, title=None):
    """Print a formatted result dictionary."""
    if title:
        print(f"\n{title}")
        print("=" * len(title))
    
    # Remove content field for cleaner output if it exists and is large
    if "content" in result and isinstance(result["content"], bytes) and len(result["content"]) > 100:
        content_preview = result["content"][:50]
        result = result.copy()
        result["content"] = f"{content_preview}... ({len(result['content'])} bytes)"
    
    # Format as JSON for nice output
    print(json.dumps(result, indent=2, default=str))

async def demonstrate_peer_discovery(api):
    """Demonstrate peer discovery functionality using AnyIO."""
    print("\nDemonstrating peer discovery...")
    
    # Get our own peer ID
    peer_id_result = api.get_libp2p_peer_id()
    print_formatted_result(peer_id_result, "Our Peer ID")
    
    # Discover peers in the network
    # We'll use a short timeout since this is just a demo
    print("\nDiscovering peers using AnyIO timeouts...")
    
    discovery_result = {}
    # Use anyio timeout primitives
    with anyio.move_on_after(10):  # 10 second timeout
        discovery_result = api.discover_peers(discovery_method="all", max_peers=5)
    
    print_formatted_result(discovery_result, "Discovered Peers")
    
    # If we found peers, try to connect to one
    if discovery_result.get("success", False) and discovery_result.get("peers", []):
        for peer in discovery_result["peers"]:
            if "addresses" in peer and peer["addresses"]:
                # Try to connect to the first address
                address = peer["addresses"][0]
                print(f"\nTrying to connect to peer {peer['id']} at {address}...")
                
                # Use anyio timeout for connection attempt
                with anyio.move_on_after(5):  # 5 second timeout
                    connection_result = api.connect_to_peer(address)
                    print_formatted_result(connection_result, "Connection Result")
                    if connection_result["success"]:
                        break  # Stop after first successful connection
    
    # Get connected peers
    connected_peers_result = api.get_connected_peers()
    print_formatted_result(connected_peers_result, "Connected Peers")
    
    return discovery_result

async def request_content_from_peers(api, discovery_result, cid):
    """Request content from discovered peers using AnyIO timeouts."""
    print(f"\nRequesting content {cid} from peers...")
    
    if not discovery_result.get("success", False) or not discovery_result.get("peers", []):
        print("No peers available to request content from")
        return
    
    # Try to request content from each peer
    for peer in discovery_result["peers"]:
        peer_id = peer["id"]
        print(f"\nRequesting content from peer {peer_id}...")
        
        try:
            # Use anyio timeout for content request
            with anyio.move_on_after(5):  # 5 second timeout
                content_result = api.request_content_from_peer(peer_id, cid)
                print_formatted_result(content_result, f"Content from {peer_id}")
                
                # If successful, stop trying
                if content_result["success"]:
                    break
        except Exception as e:
            print(f"Error requesting content from {peer_id}: {e}")

async def run_example():
    """Run the example with AnyIO."""
    print("IPFS Kit High-Level API Peer Discovery Example with AnyIO")
    print("========================================================")
    
    # Initialize the API
    api = await initialize_api()
    
    # Add a test file to IPFS
    print("\nAdding a test file to IPFS...")
    file_content = b"Hello from IPFS Kit High-Level API with AnyIO!"
    add_result = api.add_content(file_content)
    print_formatted_result(add_result, "Add Result")
    
    if not add_result["success"]:
        print("Failed to add test content, exiting")
        return
    
    # Get the CID of the added content
    cid = add_result["cid"]
    
    # Demonstrate peer discovery
    discovery_result = await demonstrate_peer_discovery(api)
    
    # Request content from peers
    await request_content_from_peers(api, discovery_result, cid)
    
    print("\nExample completed!")

def main():
    """Entry point that runs the async example."""
    # Run the example using anyio.run, which works with both
    # async-io and trio backends
    anyio.run(run_example)

if __name__ == "__main__":
    main()