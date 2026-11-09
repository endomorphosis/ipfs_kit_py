#!/usr/bin/env python3
"""
Test script for the Storacha storage backend.

This script tests the functionality of the Storacha storage backend
with the updated endpoint configuration.
"""

import os
import sys
import json
import time
import subprocess

# Set up environment variables
os.environ["STORACHA_API_KEY"] = "mock_storacha_key"
os.environ["STORACHA_API_URL"] = "https://up.storacha.network/bridge"

# Import the storage implementation
from storacha_storage import StorachaStorage

def print_json(data):
    """Print JSON data in a readable format."""
    print(json.dumps(data, indent=2))

def main():
    """Main test function."""
    print("\n===== TESTING STORACHA STORAGE BACKEND =====\n")
    
    # Initialize storage backend
    print("Initializing Storacha storage backend...")
    storage = StorachaStorage()
    
    # Test connection status
    print("\n----- Testing Connection Status -----")
    status = storage.status()
    print_json(status)
    
    # If connection fails, try mock mode
    if not status.get("success", False):
        print("\nConnection to real Storacha API failed. Testing with mock mode...")
        os.environ["MCP_USE_STORACHA_MOCK"] = "true"
        storage = StorachaStorage()
        status = storage.status()
        print_json(status)
    
    # Create a test file and add it to IPFS
    print("\n----- Creating Test Content -----")
    test_file = "storacha_test_file.txt"
    with open(test_file, "w") as f:
        f.write(f"Test file for Storacha integration at {time.time()}")
    
    # Add to IPFS
    try:
        result = subprocess.run(
            ["ipfs", "add", "-q", test_file],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            test_cid = result.stdout.strip()
            print(f"Added test file to IPFS with CID: {test_cid}")
        else:
            print("Failed to add test file to IPFS")
            return
    except Exception as e:
        print(f"Error adding test file to IPFS: {e}")
        return
    finally:
        # Clean up test file
        try:
            os.remove(test_file)
        except:
            pass
    
    # Test storing content
    print("\n----- Testing from_ipfs (Store to Storacha) -----")
    store_result = storage.from_ipfs(test_cid, replication=3)
    print_json(store_result)
    
    # If storage succeeded, test retrieving and checking status
    if store_result.get("success", False):
        storage_id = store_result.get("storage_id")
        
        # Test checking status
        if storage_id:
            print("\n----- Testing check_status -----")
            status_result = storage.check_status(storage_id)
            print_json(status_result)
        
            # Test retrieving content
            print("\n----- Testing to_ipfs (Retrieve from Storacha) -----")
            retrieve_result = storage.to_ipfs(storage_id)
            print_json(retrieve_result)
    
    print("\n===== TEST COMPLETE =====\n")

if __name__ == "__main__":
    main()