#!/usr/bin/env python3
"""
IPFS DHT Operations Demo

This script demonstrates how to use the enhanced DHT (Distributed Hash Table) 
operations in the IPFS backend, which improve network participation capabilities.

Usage:
    python ipfs_dht_demo.py [operation]

Operations:
    - provide: Announce to the network that we are providing a specific CID
    - find_providers: Find peers providing a specific CID
    - find_peer: Find information about a specific peer
    - query: Query the DHT for a specific key
    - all: Run all demo operations (default)
"""

import os
import sys
import time
import json
import argparse
from typing import Dict, Any

# Ensure parent directory is in path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import the IPFS backend
import ipfs_backend


def print_result(title: str, result: Dict[str, Any]) -> None:
    """Print operation result with formatting."""
    print(f"\n=== {title} ===")
    
    if result.get("success", False):
        print("✅ Operation succeeded")
    else:
        print("❌ Operation failed")
    
    # Print details
    for key, value in result.items():
        if key != "details":
            if isinstance(value, dict) or isinstance(value, list):
                print(f"{key}: {json.dumps(value, indent=2)}")
            else:
                print(f"{key}: {value}")
    
    # Print performance stats
    if "details" in result and "stats" in result.get("details", {}):
        print("\nPerformance stats:")
        stats = result["details"]["stats"]
        for stat_key, stat_value in stats.items():
            print(f"  {stat_key}: {stat_value}")


def demo_provide(backend, cid=None):
    """Demo the DHT provide operation."""
    # Use provided CID or store some test content
    if not cid:
        # Store some test content first
        test_content = f"DHT provide test content at {time.time()}"
        store_result = backend.store(test_content)
        if not store_result.get("success", False):
            print("❌ Failed to store test content")
            return
        
        cid = store_result["identifier"]
        print(f"Stored test content with CID: {cid}")
    
    # Provide the content
    result = backend.dht_provide(cid, recursive=True)
    print_result("DHT Provide Operation", result)


def demo_find_providers(backend, cid=None):
    """Demo the DHT find providers operation."""
    # Use provided CID or a known CID
    if not cid:
        cid = "QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn"  # IPFS default empty directory
        print(f"Using default IPFS empty directory CID: {cid}")
    
    # Find providers
    result = backend.dht_find_providers(cid, num_providers=5, timeout=30)
    print_result("DHT Find Providers Operation", result)
    
    if result.get("success", False) and len(result.get("providers", [])) > 0:
        print(f"\nFound {len(result['providers'])} providers for CID: {cid}")
        for idx, provider in enumerate(result["providers"]):
            print(f"Provider {idx+1}: {provider.get('id')}")
            if 'addresses' in provider:
                for addr in provider.get('addresses', []):
                    print(f"  Address: {addr}")
    else:
        print(f"\nNo providers found for CID: {cid}")


def demo_find_peer(backend, peer_id=None):
    """Demo the DHT find peer operation."""
    # Use provided peer ID or a known bootstrap node
    if not peer_id:
        # Use a common IPFS bootstrap node
        peer_id = "QmSoLer265NRgSp2LA3dPaeykiS1J6DifTC88f5uVQKNAd"
        print(f"Using IPFS bootstrap node peer ID: {peer_id}")
    
    # Find peer
    result = backend.dht_find_peer(peer_id, timeout=30)
    print_result("DHT Find Peer Operation", result)
    
    if result.get("success", False):
        print(f"\nFound peer {peer_id} with {len(result.get('addresses', []))} addresses:")
        for addr in result.get("addresses", []):
            print(f"  Address: {addr}")
    else:
        print(f"\nFailed to find peer: {peer_id}")


def demo_query(backend, key=None):
    """Demo the DHT query operation."""
    # Use provided key or a default key
    if not key:
        # Use IPNS key format
        key = "/ipns/QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn"
        print(f"Using sample DHT key: {key}")
    
    # Query DHT
    result = backend.dht_query(key, timeout=30)
    print_result("DHT Query Operation", result)
    
    if result.get("success", False):
        print(f"\nReceived {len(result.get('responses', []))} responses for key: {key}")
        for idx, response in enumerate(result.get("responses", [])):
            print(f"Response {idx+1} from peer: {response.get('id')}")
            if 'value' in response:
                print(f"  Value: {response.get('value')}")
    else:
        print(f"\nNo responses for key: {key}")


def main():
    """Run the demonstration script."""
    parser = argparse.ArgumentParser(description="Demo IPFS DHT operations")
    parser.add_argument(
        "operation", 
        nargs="?", 
        default="all",
        choices=["provide", "find_providers", "find_peer", "query", "all"],
        help="DHT operation to demonstrate"
    )
    parser.add_argument(
        "--cid", 
        help="CID to use for provide or find_providers operations"
    )
    parser.add_argument(
        "--peer", 
        help="Peer ID to use for find_peer operation"
    )
    parser.add_argument(
        "--key", 
        help="Key to use for query operation"
    )
    
    args = parser.parse_args()
    
    print("IPFS DHT Operations Demo")
    print("========================")
    
    # Initialize the backend
    backend = ipfs_backend.get_instance()
    
    if not backend.is_available():
        print("❌ IPFS backend is not available (using mock implementation)")
        print("This script requires a real IPFS node. Please install and run IPFS daemon.")
        return 1
    
    print(f"IPFS backend initialized: {backend.get_name()}")
    
    # Run the requested demo
    if args.operation == "provide" or args.operation == "all":
        demo_provide(backend, args.cid)
    
    if args.operation == "find_providers" or args.operation == "all":
        demo_find_providers(backend, args.cid)
    
    if args.operation == "find_peer" or args.operation == "all":
        demo_find_peer(backend, args.peer)
    
    if args.operation == "query" or args.operation == "all":
        demo_query(backend, args.key)
    
    print("\nDemo completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())