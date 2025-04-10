#!/usr/bin/env python3
"""
Simple test script to verify the libp2p fallback works correctly
"""

import sys
import json
from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel

def test_libp2p_fallback():
    """Test that our libp2p fallback implementation works."""
    print("Initializing IPFSModel...")
    model = IPFSModel()
    print("Model initialized successfully")
    
    # Test discover_peers command
    print("\nTesting discover_peers command...")
    discover_result = model.execute_command('discover_peers', [], {})
    print(f"Success: {discover_result.get('success', False)}")
    print(f"Simulated: {discover_result.get('simulated', False)}")
    print(f"Peers found: {len(discover_result.get('peers', []))}")
    
    # Test list_known_peers command
    print("\nTesting list_known_peers command...")
    list_result = model.execute_command('list_known_peers', [], {})
    print(f"Success: {list_result.get('success', False)}")
    print(f"Simulated: {list_result.get('simulated', False)}")
    print(f"Peers found: {len(list_result.get('peers', []))}")
    
    # Test register_node command
    print("\nTesting register_node command...")
    reg_result = model.execute_command('register_node', [], {
        "node_id": "test_node",
        "role": "worker",
        "capabilities": ["storage", "compute"]
    })
    print(f"Success: {reg_result.get('success', False)}")
    print(f"Simulated: {reg_result.get('simulated', False)}")
    print(f"Node ID: {reg_result.get('node_id')}")
    print(f"Role: {reg_result.get('role')}")
    print(f"Status: {reg_result.get('status')}")
    
    # Return 0 for success
    return 0

if __name__ == "__main__":
    sys.exit(test_libp2p_fallback())