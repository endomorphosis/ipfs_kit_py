#!/usr/bin/env python3
"""
Test script to verify IPFS peer ID generation and validation.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from ipfs_kit_py.ipfs_cluster_daemon_manager import IPFSClusterConfig

def test_peer_id_generation():
    """Test peer ID generation and validation."""
    print("Testing IPFS peer ID generation and validation...")
    
    # Create config instance
    config = IPFSClusterConfig()
    
    # Generate several peer IDs
    for i in range(5):
        print(f"\n--- Test {i+1} ---")
        
        # Generate peer ID
        peer_id = config._generate_proper_peer_id()
        print(f"Generated peer ID: {peer_id}")
        print(f"Length: {len(peer_id)}")
        
        # Validate peer ID
        is_valid = config._validate_peer_id(peer_id)
        print(f"Validation result: {'✓ VALID' if is_valid else '✗ INVALID'}")
        
        # Check format
        if peer_id.startswith("12D3KooW"):
            print("✓ Correct prefix")
        else:
            print("✗ Wrong prefix")
    
    # Test with known invalid peer IDs
    print("\n--- Testing invalid peer IDs ---")
    invalid_ids = [
        "12D3KooW5e85c8b05573d26336007c20deaf638e775003208c4fb06690",  # Truncated
        "invalid_peer_id",  # Wrong format
        "12D3KooW",  # Too short
        "",  # Empty
    ]
    
    for invalid_id in invalid_ids:
        is_valid = config._validate_peer_id(invalid_id)
        print(f"'{invalid_id}': {'✗ Correctly rejected' if not is_valid else '✓ Incorrectly accepted'}")

def test_identity_generation():
    """Test full identity generation."""
    print("\n\n=== Testing Identity Generation ===")
    
    config = IPFSClusterConfig()
    result = config._generate_identity_config()
    
    if result["success"]:
        identity = result["identity"]
        print("✓ Identity generation successful")
        print(f"Peer ID: {identity['id']}")
        print(f"Private key length: {len(identity['private_key'])}")
        print(f"Addresses: {identity['addresses']}")
        
        # Validate the generated peer ID
        is_valid = config._validate_peer_id(identity['id'])
        print(f"Generated peer ID validation: {'✓ VALID' if is_valid else '✗ INVALID'}")
    else:
        print("✗ Identity generation failed")
        print(f"Errors: {result['errors']}")

def test_auto_heal():
    """Test auto-healing functionality."""
    print("\n\n=== Testing Auto-Heal Functionality ===")
    
    config = IPFSClusterConfig()
    result = config.auto_heal_cluster_config()
    
    print(f"Auto-heal success: {result['success']}")
    print(f"Actions taken: {result['actions_taken']}")
    if result.get('errors'):
        print(f"Errors: {result['errors']}")
    if result.get('new_peer_id'):
        print(f"New peer ID: {result['new_peer_id']}")

if __name__ == "__main__":
    test_peer_id_generation()
    test_identity_generation()
    test_auto_heal()
    print("\n✓ All tests completed!")
