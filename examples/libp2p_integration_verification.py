#!/usr/bin/env python3
"""
LibP2P Integration Verification

This script verifies the successful integration of all libp2p patches into the codebase.
It demonstrates:
1. The fixed HAS_LIBP2P variable in libp2p_model.py
2. The added execute_command method to IPFSModel
3. The integrated mock implementations in libp2p_mocks.py
4. The protocol extensions applied through apply_libp2p_protocol_extensions

This verification script confirms that all components work together correctly
after the integration process.
"""

import os
import sys
import json
from datetime import datetime

# Adjust path for running from examples directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
from ipfs_kit_py.libp2p.libp2p_mocks import apply_libp2p_mocks, patch_mcp_command_handlers
from ipfs_kit_py.libp2p import apply_protocol_extensions


def print_step(step_num, description):
    """Print a numbered verification step."""
    print(f"\n[Step {step_num}] {description}")
    print("=" * (len(description) + 10))


def print_result(test_name, success, details=None):
    """Print test result in a consistent format."""
    status = "PASSED" if success else "FAILED"
    print(f"  {test_name}: {status}")
    if details:
        print(f"    Details: {details}")


def verify_libp2p_integration():
    """Verify the libp2p integration."""
    print("\nLIBP2P INTEGRATION VERIFICATION")
    print("===============================")
    print(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    all_tests_passed = True

    # Step 1: Initialize components
    print_step(1, "Initializing components")
    try:
        # Initialize ipfs_kit with worker role
        kit = ipfs_kit(metadata={"role": "worker"})
        print_result("Initialize ipfs_kit", True)

        # Apply libp2p mocks
        apply_libp2p_mocks()
        print_result("Apply libp2p mocks", True)

        # Patch MCP command handlers
        patch_mcp_command_handlers()
        print_result("Patch MCP command handlers", True)

        # Apply protocol extensions
        apply_protocol_extensions(IPFSModel)
        print_result("Apply protocol extensions", True)

        # Create IPFSModel
        ipfs_model = IPFSModel()
        print_result("Create IPFSModel", True)
    except Exception as e:
        print_result("Initialization", False, f"Error: {str(e)}")
        all_tests_passed = False
        return False

    # Step 2: Verify execute_command method
    print_step(2, "Verifying execute_command method")
    try:
        # Verify the method exists
        if hasattr(ipfs_model, 'execute_command'):
            print_result("Method exists", True)

            # Test with a libp2p command
            result = ipfs_model.execute_command('libp2p_get_node_id')
            if result.get('success', False):
                print_result("Command execution", True, f"Got peer ID: {result.get('result', {}).get('node_id', '')}")
            else:
                print_result("Command execution", False, f"Failed: {json.dumps(result)}")
                all_tests_passed = False
        else:
            print_result("Method exists", False, "IPFSModel does not have execute_command method")
            all_tests_passed = False
    except Exception as e:
        print_result("execute_command test", False, f"Error: {str(e)}")
        all_tests_passed = False

    # Step 3: Verify libp2p peer object access through execute_command
    print_step(3, "Verifying libp2p functionality through commands")
    try:
        # Test get_node_id command (already tested in step 2, but repeated here for clarity)
        result = ipfs_model.execute_command('libp2p_get_node_id')
        if result.get('success', False):
            print_result("Get node ID", True, f"Node ID: {result.get('result', {}).get('node_id', '')}")
        else:
            print_result("Get node ID", False, f"Failed: {json.dumps(result)}")
            all_tests_passed = False
    except Exception as e:
        print_result("Command test", False, f"Error: {str(e)}")
        all_tests_passed = False

    # Step 4: Verify protocol extensions
    print_step(4, "Verifying protocol extensions")
    try:
        # Test subscribe capabilities (GossipSub)
        result = ipfs_model.execute_command('libp2p_subscribe', topic="test-topic")
        if result.get('success', False):
            print_result("Protocol extensions - GossipSub", True, f"Subscribed to topic: test-topic")
        else:
            print_result("Protocol extensions - GossipSub", False, f"Failed: {json.dumps(result)}")
            all_tests_passed = False

        # Test publish capabilities (GossipSub)
        result = ipfs_model.execute_command('libp2p_publish', topic="test-topic", message="Test message")
        if result.get('success', False):
            print_result("Protocol extensions - Publish", True, f"Published to topic: test-topic")
        else:
            print_result("Protocol extensions - Publish", False, f"Failed: {json.dumps(result)}")
            all_tests_passed = False

        # Test content announcement
        result = ipfs_model.execute_command('libp2p_announce_content', cid="QmTestCID")
        if result.get('success', False):
            print_result("Protocol extensions - Content Announcement", True, f"Announced CID: QmTestCID")
        else:
            print_result("Protocol extensions - Content Announcement", False, f"Failed: {json.dumps(result)}")
            all_tests_passed = False
    except Exception as e:
        print_result("Protocol extensions test", False, f"Error: {str(e)}")
        all_tests_passed = False

    # Step 5: Verify connection operations
    print_step(5, "Verifying connection operations")
    try:
        # Connect to a peer
        peer_addr = "/ip4/127.0.0.1/tcp/4001/p2p/QmTest123"
        result = ipfs_model.execute_command('libp2p_connect_peer', peer_addr=peer_addr)
        if result.get('success', False):
            print_result("Connect peer", True, f"Connected to: {peer_addr}")
        else:
            print_result("Connect peer", False, f"Failed: {json.dumps(result)}")
            all_tests_passed = False

        # List connected peers
        result = ipfs_model.execute_command('libp2p_get_peers')
        if result.get('success', False):
            print_result("Get peers", True, f"Found peers: {result.get('peers', [])}")
        else:
            print_result("Get peers", False, f"Failed: {json.dumps(result)}")
            all_tests_passed = False
    except Exception as e:
        print_result("Connection test", False, f"Error: {str(e)}")
        all_tests_passed = False

    # Final summary
    print("\nVERIFICATION SUMMARY")
    print("===================")
    if all_tests_passed:
        print("✅ ALL TESTS PASSED - LibP2P integration is complete and working correctly!")
    else:
        print("❌ SOME TESTS FAILED - Please check the specific errors above.")

    print(f"\nCompleted at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return all_tests_passed


if __name__ == "__main__":
    verify_libp2p_integration()
