#!/usr/bin/env python3
"""
Test script to verify that the ipfs_py class can be imported from ipfs_client.py
"""

import os
import sys

def test_ipfs_client_import():
    """Test if ipfs_py can be imported from ipfs_client"""
    print("Testing import of ipfs_py from ipfs_client...")
    try:
        from ipfs_kit_py.ipfs_client import ipfs_py
        print("SUCCESS: Successfully imported ipfs_py from ipfs_client")
        print(f"ipfs_py class: {ipfs_py}")
        return True
    except ImportError as e:
        print(f"ERROR: Failed to import ipfs_py from ipfs_client: {e}")
        return False

def test_ipfs_backend_import():
    """Test if IPFSBackend can initialize with ipfs_py"""
    print("\nTesting IPFSBackend initialization with ipfs_py...")
    try:
        from ipfs_kit_py.mcp.storage_manager.backends.ipfs_backend import IPFSBackend
        backend = IPFSBackend(resources={}, metadata={})
        print("SUCCESS: Successfully initialized IPFSBackend")
        mock_status = getattr(backend.ipfs, "_mock_implementation", None)
        if mock_status:
            print("NOTE: Using mock implementation (normal when IPFS daemon isn't running)")
        else:
            print("SUCCESS: Using real ipfs_py implementation")
        return True
    except Exception as e:
        print(f"ERROR: Failed to initialize IPFSBackend: {e}")
        return False

if __name__ == "__main__":
    test_ipfs_client_import()
    test_ipfs_backend_import()