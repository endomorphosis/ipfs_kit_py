#!/usr/bin/env python3
"""
Test cluster daemon startup with the new peer ID generation.
"""

import sys
import os
import asyncio
sys.path.insert(0, os.path.dirname(__file__))

from ipfs_kit_py.ipfs_cluster_daemon_manager import IPFSClusterDaemonManager

async def test_cluster_startup():
    """Test starting the cluster daemon with properly generated peer IDs."""
    print("Testing IPFS Cluster daemon startup...")
    
    # Create daemon manager
    daemon_manager = IPFSClusterDaemonManager()
    
    # Test auto-healing first
    print("\n--- Testing Auto-Healing ---")
    heal_result = daemon_manager.config.auto_heal_cluster_config()
    print(f"Auto-heal result: {heal_result['success']}")
    print(f"Actions taken: {heal_result['actions_taken']}")
    if heal_result.get('new_peer_id'):
        print(f"New peer ID: {heal_result['new_peer_id']}")
    
    # Test configuration validation
    print("\n--- Testing Configuration Validation ---")
    validation_result = daemon_manager._validate_configuration()
    print(f"Configuration valid: {validation_result['valid']}")
    if not validation_result['valid']:
        print(f"Issues: {validation_result['issues']}")
    if validation_result['warnings']:
        print(f"Warnings: {validation_result['warnings']}")
    
    # Test configuration existence
    print("\n--- Testing Configuration Existence ---")
    config_result = daemon_manager.config.ensure_config_exists()
    print(f"Config exists: {config_result['success']}")
    if config_result.get('created_config'):
        print("✓ New configuration created")
    
    # Check if we have valid identity
    try:
        with open(daemon_manager.config.identity_path, 'r') as f:
            import json
            identity = json.load(f)
            peer_id = identity.get('id')
            print(f"Current peer ID: {peer_id}")
            print(f"Peer ID valid: {daemon_manager.config._validate_peer_id(peer_id)}")
    except Exception as e:
        print(f"Error reading identity: {e}")
    
    # Try to start the daemon
    print("\n--- Testing Daemon Startup ---")
    try:
        start_result = await daemon_manager.start_cluster_service()
        print(f"Startup result: {start_result['success']}")
        print(f"Status: {start_result['status']}")
        if start_result.get('pid'):
            print(f"PID: {start_result['pid']}")
        if start_result.get('errors'):
            print(f"Errors: {start_result['errors']}")
        
        # If started, get status and then stop
        if start_result['success']:
            print("\n--- Getting Daemon Status ---")
            status = await daemon_manager.get_cluster_service_status()
            print(f"Running: {status['running']}")
            print(f"API responsive: {status['api_responsive']}")
            
            print("\n--- Stopping Daemon ---")
            stop_result = await daemon_manager.stop_cluster_service()
            print(f"Stop result: {stop_result['success']}")
        
    except Exception as e:
        print(f"Error during daemon startup: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_cluster_startup())
