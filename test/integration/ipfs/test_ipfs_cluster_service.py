#!/usr/bin/env python3
"""
Test script for IPFS Cluster Service initialization.

This script tests the automatic initialization of the IPFS cluster service
during the first run, verifying that the configuration files and directories
are created correctly.
"""

import json
import os
import pprint
import shutil
import sys
import time

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the ipfs_cluster_service module
from ipfs_kit_py.ipfs_cluster_service import ipfs_cluster_service

def cleanup_test_environment():
    """Remove existing cluster configuration for clean testing."""
    cluster_path = os.path.expanduser("~/.ipfs-cluster")
    if os.path.exists(cluster_path):
        print(f"Removing existing cluster configuration at {cluster_path}")
        shutil.rmtree(cluster_path, ignore_errors=True)
    else:
        print("No existing cluster configuration found.")

def verify_configuration():
    """Verify that the cluster configuration files were created correctly."""
    cluster_path = os.path.expanduser("~/.ipfs-cluster")

    # Check if directory exists
    if not os.path.exists(cluster_path):
        print(f"ERROR: Cluster directory {cluster_path} does not exist!")
        return False

    # Check for required files
    required_files = ["service.json", "identity.json"]
    for filename in required_files:
        file_path = os.path.join(cluster_path, filename)
        if not os.path.exists(file_path):
            print(f"ERROR: Required file {filename} does not exist!")
            return False
        else:
            print(f"Found required file: {filename}")

            # Validate JSON files
            try:
                with open(file_path, 'r') as f:
                    content = json.load(f)
                print(f"  Successfully parsed {filename} as JSON")
            except json.JSONDecodeError as e:
                print(f"ERROR: {filename} is not valid JSON: {e}")
                return False

    # Check for required subdirectories
    required_dirs = ["raft", "datastore", "peerstore"]
    for dirname in required_dirs:
        dir_path = os.path.join(cluster_path, dirname)
        if not os.path.exists(dir_path):
            print(f"WARNING: Recommended directory {dirname} does not exist!")
        else:
            print(f"Found required directory: {dirname}")

    return True

def test_initialization():
    """Test the automatic initialization of IPFS cluster service."""
    print("Creating IPFS cluster service instance...")
    # Create instance with metadata
    metadata = {
        "role": "master",
        "ipfs_path": os.path.expanduser("~/.ipfs")
    }

    # Initialize the service
    cluster_service = ipfs_cluster_service(resources={}, metadata=metadata)

    # Start the service to trigger initialization
    print("\nCalling ipfs_cluster_service_start()...")
    result = cluster_service.ipfs_cluster_service_start()

    # Print results
    print("\nResult from ipfs_cluster_service_start():")
    pprint.pprint(result)

    # Verify configuration
    print("\nVerifying configuration...")
    config_valid = verify_configuration()

    if config_valid:
        print("\nSUCCESS: IPFS cluster service initialization passed!")
    else:
        print("\nFAILURE: IPFS cluster service initialization has issues!")

    return result

if __name__ == "__main__":
    # Check if cleanup is requested
    cleanup = len(sys.argv) > 1 and sys.argv[1] == "--cleanup"

    if cleanup:
        cleanup_test_environment()

    # Run the test
    start_time = time.time()

    result = test_initialization()

    end_time = time.time()
    elapsed = end_time - start_time

    print(f"\nTest completed in {elapsed:.2f} seconds")
    print(f"Initialization status: {result.get('initialization', 'unknown')}")

    if result.get("success", False):
        print("IPFS Cluster Service is running!")

        # Stop the service
        print("\nStopping IPFS Cluster Service...")
        metadata = {
            "role": "master",
            "ipfs_path": os.path.expanduser("~/.ipfs")
        }
        cluster_service = ipfs_cluster_service(resources={}, metadata=metadata)
        stop_result = cluster_service.ipfs_cluster_service_stop()

        print("Stop result:")
        pprint.pprint(stop_result)
    else:
        print("IPFS Cluster Service did not successfully start")
